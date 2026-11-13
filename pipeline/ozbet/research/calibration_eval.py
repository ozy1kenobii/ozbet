"""Kalibre olasılık (model/calibration.py) akıl sağlığı kontrolü — yalnız depodaki canlı veriyle.

    cd pipeline && python -m ozbet.research.calibration_eval [--data ../data] [--md ../docs/research/kalibrasyon.md]
                                                             [--json out.json]

Veri: data/history/*.json puanlanmış satırlar + data/YYYY-MM-DD.json içinde biten ve geçmişte olmayan maçlar.
Model olasılığı (p), marjsız piyasa olasılığı (q) ve sonucu olan her market bir gözlemdir.
Kıyaslanan dört olasılık: ham model, üretimdeki doğrusal harman (0.25·p + 0.75·q), kalibre (calibrated_prob), piyasa.

UYARI: örnek birkaç gün / ~140 maçtır ve aynı maçın marketleri birbirine bağımlıdır. Buradan parametre UYDURULMAZ;
ağırlıklar araştırma öncüllerinden gelir (docs/research/roi-model.md), bu betik yalnız yön kontrolüdür.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from ..agents.scorecard import market_rows
from ..model import calibration as cal

OLD_WEIGHT = 0.25          # üretimdeki doğrusal harman (config.MODEL_WEIGHT varsayılanı); kıyas için sabit
METHODS = ("model", "harman", "kalibre", "piyasa")
FAMILY_TITLE = {"ms": "Maç sonucu", "gol": "Toplam gol", "kg": "KG Var/Yok", "takim": "Takım golü",
                "yari": "Yarılar", "kombi": "Kombine", "diger": "Diğer"}
EXCESS_GAP = 0.08          # "model piyasadan çok yüksek" dilimi: p − q ≥ 0.08
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def load_rows(data_dir: Path) -> list[dict]:
    """Satır: {"id","date","league","markets":[{m,p,q,o,won}], "pick"?}. Aynı maç bir kez sayılır (geçmiş öncelikli)."""
    rows, seen = [], set()
    for p in sorted((data_dir / "history").glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for r in doc.get("rows", []):
            if r.get("markets") and r.get("id") not in seen:
                seen.add(r["id"])
                rows.append(r)
    for p in sorted(data_dir.glob("*.json")):
        if not _DAY.match(p.name):
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for m in doc.get("matches", []):
            res = m.get("result") or {}
            if m.get("id") in seen or not res.get("ft"):
                continue
            mk = market_rows(m, res["ft"], res.get("ht"))
            if mk:
                seen.add(m["id"])
                row = {"id": m["id"], "date": doc.get("date"), "league": m.get("league"), "markets": mk}
                if (m.get("pick") or {}).get("market"):
                    row["pick"] = m["pick"]["market"]
                rows.append(row)
    return rows


def _ll(p: float, y: int) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return -math.log(p if y else 1 - p)


def four_probs(market: str, p: float, q: float, league: str | None = None) -> dict[str, float]:
    return {"model": p, "harman": OLD_WEIGHT * p + (1 - OLD_WEIGHT) * q,
            "kalibre": cal.calibrated_prob(market, p, q, league), "piyasa": q}


class _Acc:
    def __init__(self):
        self.n, self.hit = 0, 0
        self.ll = dict.fromkeys(METHODS, 0.0)
        self.br = dict.fromkeys(METHODS, 0.0)
        self.sp = dict.fromkeys(METHODS, 0.0)

    def add(self, ps: dict[str, float], y: int):
        self.n += 1
        self.hit += y
        for k, p in ps.items():
            self.ll[k] += _ll(p, y)
            self.br[k] += (p - y) ** 2
            self.sp[k] += p

    def out(self) -> dict:
        n = self.n
        return {"n": n, "observed": round(self.hit / n, 4),
                "logloss": {k: round(v / n, 4) for k, v in self.ll.items()},
                "brier": {k: round(v / n, 4) for k, v in self.br.items()},
                "avg_p": {k: round(v / n, 4) for k, v in self.sp.items()}}


def evaluate(rows: list[dict]) -> dict:
    fam, excess, picks = defaultdict(_Acc), defaultdict(_Acc), defaultdict(_Acc)
    total = _Acc()
    matches, days = set(), set()
    for r in rows:
        used = False
        for e in r.get("markets") or []:
            if e.get("q") is None or e.get("p") is None or e.get("won") is None:
                continue
            used = True
            y = int(bool(e["won"]))
            ps = four_probs(e["m"], e["p"], e["q"], r.get("league"))
            f = cal.family(e["m"])
            fam[f].add(ps, y)
            total.add(ps, y)
            if e["p"] - e["q"] >= EXCESS_GAP:        # kazananın laneti dilimi
                excess[f].add(ps, y)
                excess["hepsi"].add(ps, y)
            if r.get("pick") == e["m"]:              # seçicinin gerçekten seçtiği marketler
                picks[e["m"]].add(ps, y)
                picks["hepsi"].add(ps, y)
        if used:
            matches.add(r.get("id"))
            days.add(r.get("date"))
    order = list(FAMILY_TITLE)
    return {
        "n_matches": len(matches), "n_days": len(days), "days": sorted(d for d in days if d),
        "weights": dict(cal.FAMILY_WEIGHT), "excess_cap": cal.EXCESS_CAP, "old_weight": OLD_WEIGHT,
        "overall": total.out() if total.n else None,
        "by_family": [{"family": f, "title": FAMILY_TITLE[f], **fam[f].out()} for f in order if f in fam],
        "excess": {k: a.out() for k, a in excess.items()},
        "picks": {k: a.out() for k, a in sorted(picks.items(), key=lambda kv: -kv[1].n)},
    }


# ---------------------------------------------------------------- rapor
def _row(title: str, a: dict, metric: str) -> str:
    v = a[metric]
    return f"| {title} | {a['n']} | " + " | ".join(f"{v[k]:.4f}" for k in METHODS) + " |"


def _prow(title: str, a: dict) -> str:
    v = a["avg_p"]
    return (f"| {title} | {a['n']} | %{a['observed'] * 100:.1f} | "
            + " | ".join(f"%{v[k] * 100:.1f}" for k in METHODS) + " |")


def render_md(res: dict) -> str:
    w = res["weights"]
    head = "| Aile | n | Ham model | Harman 0.25 | Kalibre | Piyasa |\n|---|---|---|---|---|---|"
    phead = "| Dilim | n | Gerçekleşen | Ham model | Harman 0.25 | Kalibre | Piyasa |\n|---|---|---|---|---|---|---|"
    L = [
        "# Kalibre olasılık (model/calibration.py)",
        "",
        "Kod: `pipeline/ozbet/model/calibration.py` — `calibrated_prob(market, model_p, implied_p, league=None)` ve",
        "`calibrated_group(probs, implied, keys)`. Bu dosyanın tabloları:",
        "`cd pipeline && python -m ozbet.research.calibration_eval --md ../docs/research/kalibrasyon.md`",
        "",
        "## Yöntem",
        "- Logit uzayında harman: `logit(p) = logit(q) + w·g(d)`, `d = logit(model) − logit(piyasa)`.",
        "- Aile bazında model ağırlığı `w`: "
        + ", ".join(f"{FAMILY_TITLE[k]} {v:.2f}" for k, v in w.items()) + ".",
        f"- Seçim yanlılığı (kazananın laneti): model piyasadan yukarıdaysa fark `g(d) = T·tanh(d/T)`, T = {res['excess_cap']}"
        " ile doyurulur;",
        "  aşağıdaysa aynen kalır. Seçici çok sayıda gürültülü tahminin en büyüğünü aldığı için yukarı sapma şişkindir.",
        "- Piyasa yoksa model, marketin uzun dönem taban oranına doğru büzülür (logit farkının %60'ı korunur).",
        "- Grup (1/X/2, 2.5 Üst/Alt, KG Var/Yok) `calibrated_group` ile yeniden 1'e normalleştirilir.",
        "",
        "## Ağırlıklar nereden geliyor",
        "Ağırlıklar bu örneğe **uydurulmadı**; araştırma öncüllerinden seçilmiş tutucu sabitlerdir:",
        "- `roi-model.md`: doğrulamada doğrusal harman ağırlığı 0.25 → 0.1 → 0 her adımda daha iyi; Dixon-Coles piyasaya",
        "  bilgi eklemiyor → genel düzey 0.25'in altında (0.15).",
        "- `piyasa-model.md`: KG ve toplam gol dağılımında piyasa-tabanlı λ lig modelinden iyi (doğrulama n=3.547) →",
        "  KG 0.05, toplam gol 0.10. Canlı karnede de modelin en zayıf olduğu aileler bunlar ve takım golü",
        "  (log-loss 0.6866 / 0.6452) → 0.05; yarılarda fark en küçük → 0.15.",
        "- Stacking'deki piyasa keskinleştirmesi (katsayı 1.30) Pinnacle açılış oranına aitti; iddaa ima olasılığına",
        "  taşınamadığı için uygulanmadı.",
        "",
        f"## Akıl sağlığı kontrolü — canlı veri ({res['n_days']} gün, {res['n_matches']} maç)",
        "Gözlem = model olasılığı, marjsız piyasa olasılığı ve sonucu olan her market. Düşük değer iyi.",
        "",
        "### Log-loss",
        head,
    ]
    L += [_row(a["title"], a, "logloss") for a in res["by_family"]]
    if res["overall"]:
        L.append(_row("**Hepsi**", res["overall"], "logloss"))
    L += ["", "### Brier", head]
    L += [_row(a["title"], a, "brier") for a in res["by_family"]]
    if res["overall"]:
        L.append(_row("**Hepsi**", res["overall"], "brier"))
    L += ["", f"### Modelin piyasadan çok yüksek olduğu dilim (model − piyasa ≥ {EXCESS_GAP:.2f}): ortalama olasılık",
          phead]
    ex = res["excess"]
    for f in list(FAMILY_TITLE) + ["hepsi"]:
        if f in ex:
            L.append(_prow(FAMILY_TITLE.get(f, "**Hepsi**"), ex[f]))
    L += ["", "### Seçicinin seçtiği marketler (OZBET Tercihi): ortalama olasılık", phead]
    for k, a in res["picks"].items():
        if k == "hepsi" or a["n"] >= 10:
            L.append(_prow("**Hepsi**" if k == "hepsi" else k, a))
    L += [
        "",
        "## Uyarılar",
        f"- Örnek çok küçük: {res['n_days']} gün, {res['n_matches']} maç. Aynı maçın marketleri birbirine bağımlı olduğu için",
        "  etkin örnek, tablodaki n'den çok daha küçüktür; aileler arası farklar gürültü düzeyinde olabilir.",
        "- Bu tablo yalnız yön kontrolüdür: kalibre olasılığın ham modelden ve 0.25 harmanından kötü olmadığını gösterir.",
        "  Parametre seçimi için kullanılmadı.",
        "- Kalibre olasılık piyasaya çok yakındır; iddaa marjı (~%20) düşünüldüğünde pozitif beklenen değer nadiren çıkar.",
        "  Bu beklenen sonuçtur: araştırma iddaa fiyatında değer bulamadı. Kâr vaadi yoktur.",
        "- **Tercihlerdeki iyimserlik bununla düzelmez.** Seçilen KG Var tercihlerinde ham model zaten piyasadan düşüktü;",
        "  yüksek tahmini veren piyasanın kendisi (son tablo). Kalibre olasılık piyasaya yaklaştığı için o dilimde",
        "  ortalama olasılık değişmiyor. Fark küçük örnekte (n=60, standart hata ~6 puan) gürültüyle de açıklanabilir;",
        "  kalıcıysa çözüm harman değil, seçim kuralıdır (en yüksek olasılığı seçmek yerine farklı ölçüt).",
        "- Model piyasadan çok yüksekse (üçüncü tablo) gerçekleşen oran piyasanın bile altında: yukarı sapmayı kısmak",
        "  doğru yönde, ama bu dilimde de n küçük.",
        "",
    ]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    root = Path(__file__).resolve().parents[3]
    ap.add_argument("--data", type=Path, default=root / "data")
    ap.add_argument("--md", type=Path, default=None, help="Markdown raporu bu dosyaya yaz")
    ap.add_argument("--json", type=Path, default=None, help="Ham sonuçları JSON olarak yaz")
    a = ap.parse_args(argv)
    res = evaluate(load_rows(a.data))
    md = render_md(res)
    if a.md:
        a.md.write_text(md, encoding="utf-8")
    if a.json:
        a.json.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(md)
    return res


if __name__ == "__main__":
    main()
