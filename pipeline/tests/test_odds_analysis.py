import datetime as dt

import numpy as np

from ozbet.agents import market, odds_analysis as oa


def test_shin_vs_proportional():
    o = [1.30, 4.6, 8.5]
    p = market.shin(o)
    assert abs(sum(p) - 1) < 1e-9
    s = sum(1 / x for x in o)
    prop = [1 / x / s for x in o]
    assert p[0] > prop[0] and p[2] < prop[2]          # marj sürpriz tarafından daha çok düşülür
    assert market.implied({"1": 2.0, "X": 3.4, "2": 3.6})["method"] == "shin"


def test_wilson():
    lo, hi = oa.wilson(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert oa.wilson(0, 0) == (0.0, 1.0)


def _hist(n=3000, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        p1 = rng.uniform(0.2, 0.75); px = 0.27; p2 = 1 - p1 - px
        if p2 < 0.05:
            continue
        o = {"1": round(1 / (p1 * 1.06), 2), "X": round(1 / (px * 1.06), 2), "2": round(1 / (p2 * 1.06), 2)}
        # favori-sürpriz yanlılığı: gerçek ev olasılığı piyasadan biraz yüksek
        u = rng.random(); t = p1 + 0.03
        res = "1" if u < t else ("X" if u < t + px else "2")
        hg, ag = {"1": (2, 0), "X": (1, 1), "2": (0, 1)}[res]
        rows.append({"date": dt.date(2025, 1, 1), "home": "a", "away": "b", "hg": hg, "ag": ag,
                     "odds_close": o, "odds_open": o})
    return {"TR1": rows}


def test_pool_analyze_finds_bias_and_ci():
    pool = oa.Pool(_hist())
    out = pool.analyze({"1": 0.5, "X": 0.27, "2": 0.23}, "TR1")
    assert out["status"] in ("ok", "dusuk_guven") and out["n"] >= oa.MIN_N
    m1 = next(x for x in out["markets"] if x["market"] == "1")
    assert m1["ci"][0] <= m1["observed"] <= m1["ci"][1]
    assert abs(m1["market_p"] - 0.5) < 0.03
    assert m1["observed"] > m1["market_p"]                  # yanlılık yönü doğru bulunur
    assert abs(sum(x["observed"] for x in out["markets"][:3]) - 1) < 1e-6


def test_pool_small_sample():
    pool = oa.Pool({"TR1": _hist(200)["TR1"]})
    out = pool.analyze({"1": 0.9, "X": 0.06, "2": 0.04}, "TR1")
    assert out["status"] == "az_ornek"


def test_pool_goals_scores_and_no_notable():
    pool = oa.Pool(_hist())
    out = pool.analyze({"1": 0.5, "X": 0.27, "2": 0.23}, "TR1")
    assert [x["market"] for x in out["markets"]] == ["1", "X", "2", "O2.5", "U2.5"]
    assert all("notable" not in x and "diff" not in x for x in out["markets"])
    assert all(x["note"] in (None, oa.NOTE_OK, oa.NOTE_OUT) for x in out["markets"])
    assert len(out["goals"]) == 6 and abs(sum(out["goals"]) - 1) < 1e-3
    assert len(out["scores"]) == 5 and all(len(r) == 5 for r in out["scores"])
    assert abs(sum(map(sum, out["scores"])) + out["scores_other"] - 1) < 1e-3
    # sentetik skorlar: 2-0, 1-1, 0-1 → toplam gol 2 ya da 1
    assert out["goals"][0] == 0 and out["goals"][3] == 0
    assert abs(out["scores"][2][0] - out["markets"][0]["observed"]) < 1e-3
    assert out["date_range"] == ["2025-01-01", "2025-01-01"]


def test_rows_from_iddaa_only_resulted():
    rows = [{"lg": "TR1", "d": "2026-11-07", "ft": [1, 0], "o": {"1": 2.0}, "c": {"1": 1.9}},
            {"lg": "TR1", "d": "2026-11-07", "ft": None, "o": {"1": 2.0}, "c": {}}]
    h = oa.rows_from_iddaa(rows)
    assert len(h["TR1"]) == 1 and h["TR1"][0]["odds_close"] == {"1": 1.9}
