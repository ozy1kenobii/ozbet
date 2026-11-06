"""Belirsiz iddaa market türlerinin her çalıştırmada veriyle çözülmesi.

iddaa bülteni bazı market türlerini ad vermeden, aynı seçeneklerle gönderir:
  st 36 / 88   → biri "İlk yarı sonucu", diğeri "İkinci yarı sonucu" (ikisi de "1 | 0 | 2")
  st 603 / 604 → biri "Ev sahibi gol Alt/Üst", diğeri "Deplasman gol Alt/Üst"
  st 100       → handikaplı MS; çizginin (sov) ev sahibine mi rakibe mi ait olduğu
  st 698 / 699 → biri "MS & KG"; diğerinin anlamı belirsiz
Tahminle eşlemek yerine, modelli maçlarda her iki olası eşlemenin marjı temizlenmiş oranlara uyumu ölçülür
(ortalama kare hata). Açıkça daha iyi olan seçilir; fark net değilse o market kullanılmaz.
Model ile piyasa arasında doğal farklar olsa da, ilk yarı / ikinci yarı veya ev / deplasman ayrımı bu farklardan
çok daha büyüktür; bu yüzden karar güvenilirdir. Karar ve hatalar status.json'a yazılır.
"""
from __future__ import annotations

import logging

from ..markets import all_probs

log = logging.getLogger("ozbet.market_map")

RES = {"1": "1", "0": "X", "2": "2"}
MIN_N = 8          # karar için en az bu kadar maç
RATIO = 0.7        # en iyi hipotezin hatası diğerinin ≤ %70'i olmalı


def _norm(d: dict[str, float]) -> dict[str, float]:
    inv = {k: 1 / v for k, v in d.items() if v and v > 1}
    s = sum(inv.values())
    return {k: v / s for k, v in inv.items()} if s else {}


def _three(raw_list) -> dict[str, float] | None:
    for r in raw_list or []:
        o = r.get("o") or {}
        if set(o) >= {"1", "0", "2"}:
            return {RES[k]: o[k] for k in ("1", "0", "2")}
    return None


def _ou_lines(raw_list) -> dict[str, dict[str, float]]:
    out = {}
    for r in raw_list or []:
        o = r.get("o") or {}
        try:
            ln = f'{float(str(r.get("sov")).replace(",", ".")):.1f}'
        except ValueError:
            continue
        if o.get("Üst") and o.get("Alt"):
            out[ln] = {"O": o["Üst"], "U": o["Alt"]}
    return out


def _sqerr(imp: dict[str, float], model: dict[str, float], keys: dict[str, str]) -> float | None:
    """keys: implied anahtarı → model anahtarı"""
    pairs = [(imp[a], model[b]) for a, b in keys.items() if a in imp and b in model]
    if not pairs:
        return None
    return sum((x - y) ** 2 for x, y in pairs) / len(pairs)


def _decide(errs: dict[str, list[float]]) -> tuple[str | None, dict]:
    tot = {h: (sum(v) / len(v) if v else None) for h, v in errs.items()}
    n = min((len(v) for v in errs.values()), default=0)
    rep = {"n": n, "mse": {h: (round(v, 5) if v is not None else None) for h, v in tot.items()}}
    if n < MIN_N or any(v is None for v in tot.values()):
        rep["decision"] = None
        rep["why"] = "yetersiz örnek"
        return None, rep
    best = min(tot, key=lambda h: tot[h])
    others = [v for h, v in tot.items() if h != best]
    if all(tot[best] <= RATIO * v for v in others):
        rep["decision"] = best
        return best, rep
    rep["decision"] = None
    rep["why"] = "hipotezler arasında fark net değil"
    return None, rep


def resolve(samples: list[tuple[dict, dict]]) -> tuple[dict, dict]:
    """samples: (iddaa_raw, model) çiftleri. Döner: (karar sözlüğü, rapor)."""
    errs = {
        "half": {"36=HT": [], "36=2H": []},
        "team": {"603=H": [], "603=A": []},
        "hcp": {"sov=ev": [], "sov=dep": []},
        "mskg": {"698": [], "699": []},
    }
    for raw, model in samples:
        p = all_probs(model)
        # İY / 2Y sonucu
        a, b = _three(raw.get("36")), _three(raw.get("88"))
        if a and b:
            ia, ib = _norm(a), _norm(b)
            ht = {k: f"HT_{k}" for k in "1X2"}; h2 = {k: f"2H_{k}" for k in "1X2"}
            e1 = (_sqerr(ia, p, ht) or 0) + (_sqerr(ib, p, h2) or 0)
            e2 = (_sqerr(ia, p, h2) or 0) + (_sqerr(ib, p, ht) or 0)
            errs["half"]["36=HT"].append(e1); errs["half"]["36=2H"].append(e2)
        # Takım golleri
        la, lb = _ou_lines(raw.get("603")), _ou_lines(raw.get("604"))
        e1 = e2 = 0.0; used = False
        for side_map, lines in (((("H", "A")), la), ((("A", "H")), lb)):
            for ln, o in lines.items():
                imp = _norm(o)
                for hyp_side, acc in ((side_map[0], "e1"), (side_map[1], "e2")):
                    k = f"{hyp_side}_O{ln}"
                    if k in p:
                        used = True
                        d = (imp["O"] - p[k]) ** 2
                        if acc == "e1":
                            e1 += d
                        else:
                            e2 += d
        if used:
            errs["team"]["603=H"].append(e1); errs["team"]["603=A"].append(e2)
        # Handikap işareti
        for r in raw.get("100") or []:
            o = r.get("o") or {}
            try:
                s = int(float(str(r.get("sov"))))
            except ValueError:
                continue
            if abs(s) > 2 or s == 0 or not set(o) >= {"1", "0", "2"}:
                continue
            imp = _norm({RES[k]: o[k] for k in ("1", "0", "2")})
            for hyp, h in (("sov=ev", s), ("sov=dep", -s)):
                e = _sqerr(imp, p, {r_: f"HCP{h:+d}_{r_}" for r_ in "1X2"})
                if e is not None:
                    errs["hcp"][hyp].append(e)
        # MS & KG
        for st in ("698", "699"):
            for r in raw.get(st) or []:
                o = r.get("o") or {}
                imp = {}
                for name, v in o.items():
                    res, _, kg = name.partition(" ve ")
                    if res in RES and kg in ("Var", "Yok"):
                        imp[f"{RES[res]}&BTTS_{'Y' if kg == 'Var' else 'N'}"] = v
                if len(imp) == 6:
                    e = _sqerr(_norm(imp), p, {k: k for k in imp})
                    if e is not None:
                        errs["mskg"][st].append(e)
    decisions, report = {}, {}
    for name, e in errs.items():
        if name == "mskg":
            # Yalnız birini eşlemek için: en iyi olan aynı zamanda mutlak olarak da makul olmalı
            d, rep = _decide(e)
            if d and rep["mse"][d] is not None and rep["mse"][d] > 0.01:
                rep["decision"], rep["why"] = None, "en iyi eşleme bile modelle uyumsuz"
                d = None
        else:
            d, rep = _decide(e)
        decisions[name] = d
        report[name] = rep
    return decisions, report


def apply(raw: dict | None, odds: dict[str, float], dec: dict) -> int:
    """Karar verilen eşlemelere göre ham marketleri odds sözlüğüne ekler; eklenen anahtar sayısını döner."""
    if not raw:
        return 0
    before = len(odds)
    def put(k, v):
        if v and k not in odds:
            odds[k] = v
    if dec.get("half"):
        ht_st, h2_st = ("36", "88") if dec["half"] == "36=HT" else ("88", "36")
        for st, pre in ((ht_st, "HT_"), (h2_st, "2H_")):
            t = _three(raw.get(st))
            if t:
                for k, v in t.items():
                    put(f"{pre}{k}", v)
    if dec.get("team"):
        hst, ast = ("603", "604") if dec["team"] == "603=H" else ("604", "603")
        for st, side in ((hst, "H"), (ast, "A")):
            for ln, o in _ou_lines(raw.get(st)).items():
                if ln in ("0.5", "1.5", "2.5"):
                    put(f"{side}_O{ln}", o["O"]); put(f"{side}_U{ln}", o["U"])
    if dec.get("hcp"):
        for r in raw.get("100") or []:
            o = r.get("o") or {}
            try:
                s = int(float(str(r.get("sov"))))
            except ValueError:
                continue
            h = s if dec["hcp"] == "sov=ev" else -s
            if h in (-2, -1, 1, 2) and set(o) >= {"1", "0", "2"}:
                for k in ("1", "0", "2"):
                    put(f"HCP{h:+d}_{RES[k]}", o[k])
    if dec.get("mskg"):
        for r in raw.get(dec["mskg"]) or []:
            for name, v in (r.get("o") or {}).items():
                res, _, kg = name.partition(" ve ")
                if res in RES and kg in ("Var", "Yok"):
                    put(f"{RES[res]}&BTTS_{'Y' if kg == 'Var' else 'N'}", v)
    return len(odds) - before
