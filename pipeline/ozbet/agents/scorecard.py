"""Karne Ajanı: biten maçları puanlar; isabet, Brier, kalibrasyon, lig/market kırılımı, sanal kasa ROI.
Kötü giden marketler için 'trust' katsayısı üretir (Değer ve Yorumcu ajanları kullanır).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..markets import LABELS, all_labels, settle

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
        if model:
            p = model["probs"]
            o = {"1": hg > ag, "X": hg == ag, "2": hg < ag}
            row["brier_1x2"] = round(sum((p[k] - (1.0 if o[k] else 0.0)) ** 2 for k in o), 4)
            row["p1x2"] = {k: p[k] for k in ("1", "X", "2")}
            row["outcome_1x2"] = next(k for k, v in o.items() if v)
        pk = m.get("pick")
        won = settle(pk["market"], [hg, ag], res.get("ht")) if pk else None
        if pk and won is not None:   # sonucu belirlenemeyen market (ör. İY skoru yok) puanlanmaz
            row.update({"pick": pk["market"], "pick_label": pk["label"], "p": pk["p"], "odds": pk.get("odds"),
                        "stars": pk.get("stars"), "is_value": pk.get("is_value", False), "won": won})
        graded.append(row)
    return graded


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
        if "won" in r and r["date"] >= cut:
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
