"""Backtest: geçmiş 2 tamamlanmış sezonda yürüyen pencere (walk-forward).

Her hafta modeli yalnızca o tarihten ÖNCEKİ maçlarla yeniden kurar, o haftanın maçlarını tahmin eder.
Karşılaştırma: piyasa KAPANIŞ oranlarından (marjı temizlenmiş) ima olasılık — en zor referans.
Değer bahisleri: kapanış öncesi ortalama oranından (Avg; football-data.co.uk'un toplama anı) tek birim, model_p - ima_p ≥ eşik.

    python -m ozbet.backtest              # data/backtest.json yazar
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import date, datetime, timedelta

from . import config
from .agents.market import implied
from .http import PoliteClient
from .markets import outcome_won, probs_from_matrix
from .model.dixon_coles import clamp_rho, fit, score_matrix
from .sources import football_data as fd
from .sources.base import now_iso

log = logging.getLogger("ozbet.backtest")


def _brier(p, o):
    return sum((p[k] - (1.0 if o == k else 0.0)) ** 2 for k in ("1", "X", "2"))


def _ll(p, o):
    return -math.log(max(p[o], 1e-9))


def run_league(rows: list[dict], test_seasons: list[str], edge: float = config.VALUE_EDGE) -> dict | None:
    rows = sorted(rows, key=lambda r: r["date"])
    test = [r for r in rows if r["season"] in test_seasons]
    if len(test) < 50:
        return None
    acc = {"n": 0, "mb": 0.0, "kb": 0.0, "ml": 0.0, "kl": 0.0, "ou_mb": 0.0, "ou_kb": 0.0, "ou_n": 0,
           "bets": 0, "profit": 0.0, "clv_sum": 0.0, "clv_n": 0}
    ALPHAS, EDGES = (1.0, 0.6, 0.4, 0.25), (0.03, 0.05, 0.08, 0.10)
    grid = {(a, e): [0, 0.0] for a in ALPHAS for e in EDGES}
    blend_brier = {a: 0.0 for a in ALPHAS}
    start = test[0]["date"]
    week = start
    model = None
    while week <= test[-1]["date"]:
        nxt = week + timedelta(days=7)
        model = fit([r for r in rows if r["date"] < week], week, config.TIME_DECAY_XI)
        for r in (x for x in test if week <= x["date"] < nxt):
            if model is None or r["home"] not in model.attack or r["away"] not in model.attack:
                continue
            if model.n_matches.get(r["home"], 0) < config.MIN_TEAM_MATCHES or \
               model.n_matches.get(r["away"], 0) < config.MIN_TEAM_MATCHES:
                continue
            close = implied(r["odds_close"]) or implied(r["odds_open"])
            if not close or "1" not in close["implied"]:
                continue
            lh, la = model.lambdas(r["home"], r["away"])
            p = probs_from_matrix(score_matrix(lh, la, clamp_rho(model.rho, lh, la)))
            o = "1" if r["hg"] > r["ag"] else ("X" if r["hg"] == r["ag"] else "2")
            q = close["implied"]
            acc["n"] += 1
            acc["mb"] += _brier(p, o); acc["kb"] += _brier(q, o)
            acc["ml"] += _ll(p, o); acc["kl"] += _ll(q, o)
            if "O2.5" in q:
                ov = 1.0 if r["hg"] + r["ag"] > 2 else 0.0
                acc["ou_mb"] += (p["O2.5"] - ov) ** 2; acc["ou_kb"] += (q["O2.5"] - ov) ** 2; acc["ou_n"] += 1
            # değer bahisleri: kapanış öncesi ortalama oran (Avg)
            op = implied(r["odds_open"])
            if op and "1" in op["implied"]:
                qo = op["implied"]
                for a in ALPHAS:
                    pb = {k: a * p[k] + (1 - a) * qo[k] for k in ("1", "X", "2")}
                    blend_brier[a] += _brier(pb, o)
                    for k in ("1", "X", "2", "O2.5", "U2.5"):
                        if k not in qo or k not in r["odds_open"]:
                            continue
                        pk = a * p[k] + (1 - a) * qo[k]
                        for e in EDGES:
                            if pk - qo[k] >= e:
                                g = grid[(a, e)]
                                g[0] += 1
                                g[1] += (r["odds_open"][k] - 1) if outcome_won(k, r["hg"], r["ag"]) else -1
            if op:
                for k in ("1", "X", "2", "O2.5", "U2.5"):
                    if k in op["implied"] and k in r["odds_open"] and p[k] - op["implied"][k] >= edge:
                        acc["bets"] += 1
                        acc["profit"] += (r["odds_open"][k] - 1) if outcome_won(k, r["hg"], r["ag"]) else -1
                        if k in (r["odds_close"] or {}):
                            acc["clv_sum"] += r["odds_open"][k] / r["odds_close"][k] - 1; acc["clv_n"] += 1
        week = nxt
    n = acc["n"]
    if not n:
        return None
    return {
        "n": n,
        "model_brier": round(acc["mb"] / n, 4), "market_brier": round(acc["kb"] / n, 4),
        "model_logloss": round(acc["ml"] / n, 4), "market_logloss": round(acc["kl"] / n, 4),
        "ou25_model_brier": round(acc["ou_mb"] / acc["ou_n"], 4) if acc["ou_n"] else None,
        "ou25_market_brier": round(acc["ou_kb"] / acc["ou_n"], 4) if acc["ou_n"] else None,
        "n_value_bets": acc["bets"],
        "roi_value_bets": round(acc["profit"] / acc["bets"], 4) if acc["bets"] else None,
        "avg_clv": round(acc["clv_sum"] / acc["clv_n"], 4) if acc["clv_n"] else None,
        "blend_brier": {str(a): round(v / n, 4) for a, v in blend_brier.items()},
        "grid": [{"alpha": a, "edge": e, "bets": g[0], "profit": round(g[1], 2),
                  "roi": round(g[1] / g[0], 4) if g[0] else None} for (a, e), g in grid.items()],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="TR1,ENG1,ESP1,ITA1,GER1,FRA1")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    today = datetime.now(config.TZ).date()
    cur, s1, s2 = config.season_codes(today)
    # eğitim için bir sezon daha geriye git
    y = int("20" + s2[:2]) - 1
    s3 = f"{y % 100:02d}{(y + 1) % 100:02d}"
    client = PoliteClient()
    out = {"generated_at": now_iso(), "seasons": [s2, s1], "train_extra": s3, "leagues": [], "by_league": [],
           "method": "Haftalık yeniden kurulan zaman ağırlıklı Dixon-Coles; kıyas: marjı temizlenmiş kapanış oranı. "
                     "Değer bahisleri kapanış öncesi ortalama orandan (Avg) tek birim; CLV = Avg/kapanış − 1."}
    tot = {"n": 0}
    for lid in args.leagues.split(","):
        lg = config.LEAGUE_BY_ID[lid]
        try:
            rows = fd.history(client, lg.fd_code, [s1, s2, s3])
        except Exception as e:  # noqa: BLE001
            log.warning("%s: %s", lid, e); continue
        res = run_league(rows, [s1, s2])
        if res:
            out["leagues"].append(lid)
            out["by_league"].append({"league": lid, "name": lg.name, **res})
            log.info("%s %s", lid, res)
    bl = out["by_league"]
    if bl:
        n = sum(b["n"] for b in bl)
        w = lambda k: round(sum(b[k] * b["n"] for b in bl) / n, 4)  # noqa: E731
        bets = sum(b["n_value_bets"] for b in bl)
        out["summary"] = {
            "n": n, "model_brier": w("model_brier"), "market_brier": w("market_brier"),
            "model_logloss": w("model_logloss"), "market_logloss": w("market_logloss"),
            "n_value_bets": bets,
            "roi_value_bets": round(sum((b["roi_value_bets"] or 0) * b["n_value_bets"] for b in bl) / bets, 4) if bets else None,
        }
    if bl and all("grid" in b for b in bl):
        agg = {}
        for b in bl:
            for g in b["grid"]:
                k = (g["alpha"], g["edge"])
                x = agg.setdefault(k, [0, 0.0]); x[0] += g["bets"]; x[1] += g["profit"]
        out["grid"] = [{"alpha": a, "edge": e, "bets": x[0], "profit": round(x[1], 2),
                        "roi": round(x[1] / x[0], 4) if x[0] else None} for (a, e), x in sorted(agg.items())]
        n = sum(b["n"] for b in bl)
        out["blend_brier"] = {a: round(sum(b["blend_brier"][a] * b["n"] for b in bl) / n, 4)
                              for a in bl[0]["blend_brier"]}
    (config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "backtest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    main()
