"""Karne Ajanı: biten maçları puanlar; isabet, Brier, kalibrasyon, lig/market kırılımı, sanal kasa ROI.
Kötü giden marketler için 'trust' katsayısı üretir (Değer ve Yorumcu ajanları kullanır).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .. import config
import math

from ..markets import LABELS, all_labels, all_probs, categories, settle

START_BANK = 100.0


def grade_day(day_doc: dict, results: dict[str, dict]) -> list[dict]:
    """results: match_id → {"ft":[h,a], "ht":[h,a]}. Gün dokümanındaki maçlara sonucu yazar ve puanlanmış satırları döndürür."""
    graded = []
    for m in day_doc.get("matches", []):
        res = m.get("result") or results.get(m["id"])
        if res and res.get("ft"):
            m["result"] = res
            m["status"] = "finished"
        else:
            continue
        hg, ag = res["ft"]
        row = {"id": m["id"], "date": day_doc["date"], "league": m["league"], "league_name": m.get("league_name"),
               "match": f'{m["home"]["name"]} - {m["away"]["name"]}', "score": f"{hg}-{ag}"}
        model = m.get("model")
        if model and model.get("source") != "piyasa":   # piyasa-tabanlı model piyasayla kıyaslanmaz
            p = model["probs"]
            o = {"1": hg > ag, "X": hg == ag, "2": hg < ag}
            row["brier_1x2"] = round(sum((p[k] - (1.0 if o[k] else 0.0)) ** 2 for k in o), 4)
            row["p1x2"] = {k: p[k] for k in ("1", "X", "2")}
            row["outcome_1x2"] = next(k for k, v in o.items() if v)
        mk = market_rows(m, [hg, ag], res.get("ht"))
        if mk:
            row["markets"] = mk
        pk = m.get("pick")
        won = settle(pk["market"], [hg, ag], res.get("ht")) if pk else None
        if pk and won is not None:   # sonucu belirlenemeyen market (ör. İY skoru yok) puanlanmaz
            row.update({"pick": pk["market"], "pick_label": pk["label"], "p": pk["p"], "odds": pk.get("odds"),
                        "stars": pk.get("stars"), "is_value": pk.get("is_value", False), "won": won})
        graded.append(row)
    return graded


def market_rows(m: dict, ft: list[int], ht: list[int] | None) -> list[dict]:
    """Oranı ve model olasılığı olan tüm marketleri sonuçlandırır (korner/kart gibi sonucu bilinmeyenler atlanır).
    Kısa alanlar: m=market, p=model, q=piyasa (marjsız ima), o=oran, won, v=değerli bahis mi."""
    odds = m.get("odds") or {}
    if (m.get("model") or {}).get("source") == "piyasa":
        return []
    probs = all_probs(m.get("model"))
    implied = (m.get("market") or {}).get("implied") or {}
    vals = {v["market"] for v in (m.get("value") or [])}
    out = []
    for k, o in odds.items():
        p = probs.get(k)
        if not o or p is None:
            continue
        won = settle(k, ft, ht)
        if won is None:
            continue
        e = {"m": k, "p": round(float(p), 4), "o": o, "won": won}
        if implied.get(k) is not None:
            e["q"] = round(float(implied[k]), 4)
        if k in vals:
            e["v"] = True
        out.append(e)
    return out


def _cat_of() -> dict[str, str]:
    return {k: c["id"] for c in categories() for k in c["keys"]}


def _ll(p: float, y: int) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return -math.log(p if y else 1 - p)


def market_calibration(rows: list[dict]) -> dict:
    """Tüm marketler kalibrasyonu: kategori bazında model/piyasa Brier ve log-loss + kovalar."""
    cat_of, titles = _cat_of(), {c["id"]: c["title"] for c in categories()}
    acc = defaultdict(lambda: {"n": 0, "mb": 0.0, "qb": 0.0, "ml": 0.0, "ql": 0.0})
    bins = {s: defaultdict(lambda: [0.0, 0, 0]) for s in ("model", "market")}
    for r in rows:
        for e in r.get("markets") or []:
            if e.get("q") is None:
                continue
            y = int(bool(e["won"]))
            a = acc[cat_of.get(e["m"], "diger")]
            a["n"] += 1
            a["mb"] += (e["p"] - y) ** 2; a["qb"] += (e["q"] - y) ** 2
            a["ml"] += _ll(e["p"], y); a["ql"] += _ll(e["q"], y)
            for s, p in (("model", e["p"]), ("market", e["q"])):
                b = bins[s][min(9, int(p * 10))]
                b[0] += p; b[1] += 1; b[2] += y
    order = [c["id"] for c in categories()] + ["diger"]
    by_cat = [{"category": c, "title": titles.get(c, "Diğer"), "n": a["n"],
               "model_brier": round(a["mb"] / a["n"], 4), "market_brier": round(a["qb"] / a["n"], 4),
               "model_logloss": round(a["ml"] / a["n"], 4), "market_logloss": round(a["ql"] / a["n"], 4)}
              for c, a in sorted(acc.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)]
    calib = {s: [{"bin": f"{b/10:.1f}-{(b+1)/10:.1f}", "predicted": round(t / n, 4), "observed": round(o / n, 4), "n": n}
                 for b, (t, n, o) in sorted(bb.items())] for s, bb in bins.items()}
    return {"by_category": by_cat, "calibration_markets": calib}


def value_bets(rows: list[dict]) -> dict:
    """Değerli bahis karnesi: değer etiketi alan her market, iddaa oranıyla 1 birim."""
    vb = [e for r in rows for e in (r.get("markets") or []) if e.get("v") and e.get("o")]
    if not vb:
        return {"n": 0, "hit_rate": None, "profit": 0.0, "roi": None, "avg_odds": None}
    profit = sum((e["o"] - 1) if e["won"] else -1 for e in vb)
    return {"n": len(vb), "hit_rate": round(sum(e["won"] for e in vb) / len(vb), 4), "profit": round(profit, 2),
            "roi": round(profit / len(vb), 4), "avg_odds": round(sum(e["o"] for e in vb) / len(vb), 3)}


def _agg(rows: list[dict]) -> dict:
    picks = [r for r in rows if "won" in r]
    bets = [r for r in picks if r.get("odds")]
    brs = [r["brier_1x2"] for r in rows if "brier_1x2" in r]
    profit = sum((r["odds"] - 1) if r["won"] else -1 for r in bets)
    return {
        "n": len(picks),
        "hit_rate": round(sum(r["won"] for r in picks) / len(picks), 4) if picks else None,
        "avg_p": round(sum(r["p"] for r in picks) / len(picks), 4) if picks else None,
        "brier_1x2": round(sum(brs) / len(brs), 4) if brs else None,
        "staked": len(bets), "profit": round(profit, 2),
        "roi": round(profit / len(bets), 4) if bets else None,
        "value_n": sum(1 for r in bets if r.get("is_value")),
        "value_roi": (round(sum((r["odds"] - 1) if r["won"] else -1 for r in bets if r.get("is_value"))
                            / max(1, sum(1 for r in bets if r.get("is_value"))), 4)
                      if any(r.get("is_value") for r in bets) else None),
    }


def trust_from(rows: list[dict], today: date, window_days: int = 90, min_n: int = 20) -> dict[str, float]:
    cut = (today - timedelta(days=window_days)).isoformat()
    by = defaultdict(list)
    for r in rows:
        if r["date"] < cut:
            continue
        mk = r.get("markets")
        if mk:   # tüm marketler (tercih de bunların içinde)
            for e in mk:
                by[e["m"]].append(e)
        elif "won" in r:   # eski satırlar: yalnız tercih
            by[r["pick"]].append(r)
    out = {}
    for mk, rs in by.items():
        if len(rs) >= min_n:
            hit = sum(x["won"] for x in rs) / len(rs)
            exp = sum(x["p"] for x in rs) / len(rs)
            out[mk] = round(max(0.6, min(1.1, 1 + 3 * (hit - exp))), 3)
    return out


def build_scorecard(rows: list[dict], today: date) -> dict:
    rows = sorted(rows, key=lambda r: r["date"])
    cut30 = (today - timedelta(days=30)).isoformat()
    by_league, by_market = defaultdict(list), defaultdict(list)
    for r in rows:
        by_league[(r["league"], r.get("league_name"))].append(r)
        if "pick" in r:
            by_market[r["pick"]].append(r)
    trust = trust_from(rows, today)
    # kalibrasyon: tüm 1X2 olasılıkları
    bins = defaultdict(lambda: [0.0, 0, 0])
    for r in rows:
        if "p1x2" in r:
            for k, p in r["p1x2"].items():
                b = min(9, int(p * 10))
                bins[b][0] += p; bins[b][1] += 1; bins[b][2] += int(r["outcome_1x2"] == k)
    calib = [{"bin": f"{b/10:.1f}-{(b+1)/10:.1f}", "predicted": round(s / n, 4), "observed": round(o / n, 4), "n": n}
             for b, (s, n, o) in sorted(bins.items()) if n >= 5]
    bal, curve, by_day = START_BANK, [], defaultdict(float)
    for r in rows:
        if "won" in r and r.get("odds"):
            by_day[r["date"]] += (r["odds"] - 1) if r["won"] else -1
    for d in sorted(by_day):
        bal += by_day[d]
        curve.append({"date": d, "balance": round(bal, 2)})
    recent = [{"date": r["date"], "match": r["match"], "pick": r.get("pick_label"), "odds": r.get("odds"),
               "p": r.get("p"), "won": r.get("won"), "score": r["score"], "league": r["league"]}
              for r in reversed(rows) if "won" in r][:50]
    return {
        "generated_at": None,
        "overall": _agg(rows),
        "last30": _agg([r for r in rows if r["date"] >= cut30]),
        "by_league": sorted(({"league": k[0], "name": k[1], **_agg(v)} for k, v in by_league.items()),
                            key=lambda x: -x["n"]),
        "by_market": sorted(({"market": k, "label": all_labels().get(k, k), **_agg(v), "trust": trust.get(k, 1.0)}
                             for k, v in by_market.items()), key=lambda x: -x["n"]),
        "trust": trust,
        "calibration": calib,
        **market_calibration(rows),
        "value_bets": value_bets(rows),
        "bankroll": curve,
        "recent": recent,
    }


def load_history(data_dir: Path) -> list[dict]:
    rows = []
    for p in sorted((data_dir / "history").glob("*.json")):
        try:
            rows += json.loads(p.read_text(encoding="utf-8")).get("rows", [])
        except (json.JSONDecodeError, OSError):
            continue
    return rows
