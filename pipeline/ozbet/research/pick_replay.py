"""Tercih seçicisi sağlama koşusu (AYAR ARACI DEĞİL): eski "en yüksek olasılık" kuralı ile yeni beklenen değer
seçicisini data/ altındaki bitmiş maçlarda yan yana koşar; n, isabet, ortalama oran ve düz 1 birim ROI basar.

    cd pipeline && python -m ozbet.research.pick_replay [--data DIR] [--json]

Örneklem birkaç günlük (≈140 maç) olduğundan sonuçlar yalnız "kod beklenen yönde mi çalışıyor" sorusuna cevaptır;
eşikler (PICK_MIN_ODDS/PICK_MAX_ODDS/PICK_MIN_EV) bu örnekleme göre ayarlanmamalıdır. Karne güveni (trust) geçmişe
dönük bilinmediği için iki kural da trust=1 ile koşar; yeni kuralda değer listesi yeni value.find_value ile üretilir.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from .. import config
from ..agents import commentator, value
from ..markets import LABELS, all_labels, all_probs, settle

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
ALL_LABELS = all_labels()


def legacy_choose_pick(m: dict) -> dict | None:
    """Eski kural (kıyas için birebir kopya): değer varsa o, yoksa harman olasılığı en yüksek tekil market;
    0.55 altındaysa çifte şans."""
    model = m.get("model")
    if not model or model.get("source") == "piyasa":
        return None
    p = dict(model["probs"])
    odds = m.get("odds") or {}
    imp = ((m.get("market") or {}).get("implied")) or {}
    for k, q in imp.items():
        if k in p:
            p[k] = config.MODEL_WEIGHT * p[k] + (1 - config.MODEL_WEIGHT) * q
    if m.get("value"):
        v = m["value"][0]
        return {"market": v["market"], "label": ALL_LABELS[v["market"]], "p": v["model_p"], "odds": v["odds"]}
    cands = [(k, p[k]) for k in ["1", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N"] if k in p]
    k, pk = max(cands, key=lambda t: t[1])
    if pk < 0.55:
        dk, dp = max(((k2, p[k2]) for k2 in ("1X", "X2")), key=lambda t: t[1])
        if dp >= 0.70 and dp - pk > 0.15:
            k, pk = dk, dp
    return {"market": k, "label": LABELS[k], "p": round(pk, 4), "odds": odds.get(k)}


def finished_matches(data_dir: Path) -> list[dict]:
    """Gün dosyalarındaki sonucu belli, gerçek modeli olan maçlar (aynı maç birden çok dosyadaysa ilki)."""
    seen, out = set(), []
    for f in sorted(data_dir.glob("*.json")):
        if not DAY_RE.match(f.name):
            continue
        for m in json.loads(f.read_text(encoding="utf-8")).get("matches", []):
            ft = (m.get("result") or {}).get("ft")
            model = m.get("model")
            if not ft or not model or model.get("source") == "piyasa" or m["id"] in seen:
                continue
            seen.add(m["id"])
            out.append(m)
    return out


def new_pick(m: dict) -> dict | None:
    m = copy.deepcopy(m)
    cup = any(f.startswith(("Kupa/çapraz lig", "Kupa:")) for f in m.get("flags", []))
    m["value"] = [] if cup else value.find_value(all_probs(m["model"]), m.get("odds"),
                                                 (m.get("market") or {}).get("implied"), None, m.get("league"))
    mode, config.PICK_MODE = config.PICK_MODE, "ev"   # replay "ev" (bant) kuralını ölçer; sinyal kipi geçmişte veri taşımaz
    try:
        pk = commentator.choose_pick(m)
    finally:
        config.PICK_MODE = mode
    if pk:
        pk["stars"] = commentator.stars(m, pk, {})
    return pk


def summarize(rows: list[dict], seed: int = 7) -> dict:
    """rows: [{"market","p","odds","won",...}] → n, isabet, ort. olasılık/oran, düz ROI ve bootstrap %95 GA."""
    n = len(rows)
    if not n:
        return {"n": 0}
    priced = [r for r in rows if r.get("odds")]
    prof = [(r["odds"] - 1) if r["won"] else -1.0 for r in priced]
    out = {"n": n, "hit": round(sum(r["won"] for r in rows) / n, 4),
           "avg_p": round(sum(r["p"] for r in rows) / n, 4), "n_priced": len(priced)}
    if priced:
        rnd = random.Random(seed)
        boot = sorted(sum(rnd.choices(prof, k=len(prof))) / len(prof) for _ in range(2000))
        out.update({"avg_odds": round(sum(r["odds"] for r in priced) / len(priced), 3),
                    "roi": round(sum(prof) / len(prof), 4),
                    "roi_ci95": [round(boot[49], 3), round(boot[1949], 3)]})
    return out


def replay(data_dir: Path) -> dict:
    ms = finished_matches(data_dir)
    res = {"old": [], "new": []}
    for m in ms:
        ft, ht = m["result"]["ft"], m["result"].get("ht")
        for name, pk in (("old", legacy_choose_pick(m)), ("new", new_pick(m))):
            won = settle(pk["market"], ft, ht) if pk else None
            if pk and won is not None:
                res[name].append({**pk, "won": bool(won), "league": m.get("league")})
    out = {"matches": len(ms), "config": {"MODEL_WEIGHT": config.MODEL_WEIGHT, "PICK_MIN_ODDS": config.PICK_MIN_ODDS,
                                          "PICK_MAX_ODDS": config.PICK_MAX_ODDS, "PICK_MIN_EV": config.PICK_MIN_EV,
                                          "calibration_module": value._cal is not None}}
    for name, rows in res.items():
        by = defaultdict(list)
        for r in rows:
            by[r["market"]].append(r)
        out[name] = {"all": summarize(rows), "pass": len(ms) - len(rows),
                     "by_market": {k: summarize(v) for k, v in sorted(by.items(), key=lambda t: -len(t[1]))}}
    new = res["new"]
    out["new"]["by_kind"] = {k: summarize([r for r in new if r["kind"] == k]) for k in ("deger", "denge")}
    out["new"]["value_labelled"] = summarize([r for r in new if r["is_value"]])
    out["new"]["by_stars"] = {str(s): summarize([r for r in new if r.get("stars") == s]) for s in range(1, 6)
                              if any(r.get("stars") == s for r in new)}
    return out


def _line(name: str, s: dict) -> str:
    if not s.get("n"):
        return f"  {name:<14} n=0"
    t = f"  {name:<14} n={s['n']:<4} isabet={s['hit']:.1%}  ort.p={s['avg_p']:.3f}"
    if "roi" in s:
        t += f"  ort.oran={s['avg_odds']:.2f}  ROI={s['roi']:+.1%}  %95 GA [{s['roi_ci95'][0]:+.2f}, {s['roi_ci95'][1]:+.2f}]"
    return t


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(config.DATA_DIR))
    ap.add_argument("--json", action="store_true", help="özeti JSON olarak bas")
    args = ap.parse_args(argv)
    out = replay(Path(args.data))
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return out
    print(f"Bitmiş, modelli maç: {out['matches']}  |  ayar: {out['config']}")
    print("UYARI: küçük örneklem — sağlama amaçlıdır, eşik ayarı için kullanılmaz.")
    for name, title in (("old", "ESKİ kural (en yüksek olasılık)"), ("new", "YENİ kural (bantta en yüksek EV)")):
        r = out[name]
        print(f"\n{title} — pas: {r['pass']}")
        print(_line("toplam", r["all"]))
        for k, s in r["by_market"].items():
            print(_line(ALL_LABELS.get(k, k), s))
        if name == "new":
            for k, s in r["by_kind"].items():
                print(_line(f"tür={k}", s))
            print(_line("değer etiketli", r["value_labelled"]))
            for k, s in r["by_stars"].items():
                print(_line(f"{k} yıldız", s))
    return out


if __name__ == "__main__":
    main()
