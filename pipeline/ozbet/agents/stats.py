"""İstatistik Ajanı: form, gol ortalamaları, xG, KG/Ü2.5 yüzdeleri, korner/kart, H2H."""
from __future__ import annotations

from datetime import date

import numpy as np


def _res(gf, ga):
    return "W" if gf > ga else ("D" if gf == ga else "L")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 2) if xs else None


def team_stats(rows: list[dict], team: str, before: date, venue: str, n: int = 10) -> dict:
    """venue: 'home' veya 'away' — bu maçtaki konumu; iç/dış form o konuma göre."""
    past = sorted((r for r in rows if r["date"] < before and team in (r["home"], r["away"])),
                  key=lambda r: r["date"], reverse=True)
    last = past[:n]
    ven = [r for r in past if (r["home"] if venue == "home" else r["away"]) == team][:n]

    def persp(r):
        h = r["home"] == team
        gf, ga = (r["hg"], r["ag"]) if h else (r["ag"], r["hg"])
        xg = r.get("hxg") if h else r.get("axg")
        xga = r.get("axg") if h else r.get("hxg")
        cor = r.get("hc") if h else r.get("ac")
        y, rd = (r.get("hy"), r.get("hr")) if h else (r.get("ay"), r.get("ar"))
        cards = None if y is None else y + 2 * (rd or 0)
        return gf, ga, xg, xga, cor, cards

    P = [persp(r) for r in last]
    V = [persp(r) for r in ven]
    out = {
        "n": len(last),
        "form": [_res(p[0], p[1]) for p in P],
        "venue_form": [_res(p[0], p[1]) for p in V],
        "venue_n": len(V),
        "gf_avg": _mean([p[0] for p in P]), "ga_avg": _mean([p[1] for p in P]),
        "venue_gf_avg": _mean([p[0] for p in V]), "venue_ga_avg": _mean([p[1] for p in V]),
        "xg_avg": _mean([p[2] for p in P]), "xga_avg": _mean([p[3] for p in P]),
        "btts_pct": round(sum(1 for p in P if p[0] > 0 and p[1] > 0) / len(P), 2) if P else None,
        "o25_pct": round(sum(1 for p in P if p[0] + p[1] > 2) / len(P), 2) if P else None,
        "clean_sheets_venue": sum(1 for p in V if p[1] == 0),
        "failed_to_score_venue": sum(1 for p in V if p[0] == 0),
        "corners_avg": _mean([p[4] for p in P]),
        "cards_avg": _mean([p[5] for p in P]),
        "last_match_date": past[0]["date"].isoformat() if past else None,
    }
    return out


def h2h(rows: list[dict], a: str, b: str, before: date, n: int = 6) -> list[dict]:
    games = sorted((r for r in rows if r["date"] < before and {r["home"], r["away"]} == {a, b}),
                   key=lambda r: r["date"], reverse=True)[:n]
    return [{"date": r["date"].isoformat(), "home": r["home"], "away": r["away"],
             "score": f'{r["hg"]}-{r["ag"]}'} for r in games]


def h2h_summary(rows: list[dict], a: str, b: str, before: date, n: int = 6) -> dict | None:
    """Son n karşılaşmanın özeti; galibiyetler bugünkü maçın ev sahibi (a) ve deplasmanı (b) açısından sayılır
    (eski maçta kimin evinde oynandığından bağımsız)."""
    games = sorted((r for r in rows if r["date"] < before and {r["home"], r["away"]} == {a, b}),
                   key=lambda r: r["date"], reverse=True)[:n]
    if not games:
        return None
    aw = sum(1 for r in games if (r["hg"] > r["ag"] and r["home"] == a) or (r["ag"] > r["hg"] and r["away"] == a))
    dr = sum(1 for r in games if r["hg"] == r["ag"])
    return {"n": len(games), "home_wins": aw, "draws": dr, "away_wins": len(games) - aw - dr,
            "avg_goals": round(sum(r["hg"] + r["ag"] for r in games) / len(games), 2),
            "btts": sum(1 for r in games if r["hg"] > 0 and r["ag"] > 0),
            "o25": sum(1 for r in games if r["hg"] + r["ag"] > 2)}
