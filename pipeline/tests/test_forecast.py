"""Tahmin Motoru testleri: her maçta çalışma, kısmi uydurma, güven kademesi, puanlama."""
from ozbet.agents import forecast, scorecard

ODDS = {"1": 1.55, "X": 3.9, "2": 5.2, "O2.5": 1.75, "U2.5": 1.85, "BTTS_Y": 1.8, "BTTS_N": 1.8}


def _mm(lh=1.8, la=0.9):
    return {"lambda_home": lh, "lambda_away": la, "rho": -0.05, "source": "piyasa", "probs": {}}


def test_market_match_gets_full_forecast():
    m = {"odds": ODDS, "model": _mm(), "odds_history": []}
    fc = forecast.build(m)
    assert fc["outcome"] == "1" and fc["basis"] == "piyasa" and fc["confidence"] == "yüksek"
    assert abs(sum(fc["probs"].values()) - 1) < 0.01 and fc["margin"] > 0
    assert len(fc["scores"]) == 3 and fc["goals"]["market"] in ("O2.5", "U2.5") and fc["btts"]["p"] >= 0.5
    assert fc["dc"]["market"] == "1X" and "Tahmin:" in fc["text"]
    for bad in ("kesin", "banko", "garanti"):
        assert bad not in fc["text"].lower()


def test_confidence_tiers():
    assert forecast.confidence(0.61) == "yüksek" and forecast.confidence(0.5) == "orta" and forecast.confidence(0.44) == "düşük"


def test_partial_fit_without_1x2_group():
    # yalnız çifte şans + KG + 3.5 Alt/Üst açılmış maç (bültende gerçek örnek)
    m = {"odds": {"1X": 1.25, "BTTS_Y": 1.7, "BTTS_N": 1.95, "O3.5": 2.6, "U3.5": 1.4}, "model": None}
    fc = forecast.build(m)
    assert fc and fc["basis"] == "kısmi" and fc["confidence"] == "düşük" and fc["outcome"] in ("1", "X", "2")
    assert fc["probs"]["1"] + fc["probs"]["X"] > 0.6 and "kısmi" in fc["text"]


def test_no_strength_info_returns_none():
    assert forecast.build({"odds": {"O2.5": 1.8, "U2.5": 1.9}, "model": None}) is None
    assert forecast.build({"odds": {}, "model": None}) is None
    assert forecast.build({"odds": {"1": "x", "X": None, "2": float("nan")}, "model": None}) is None


def test_league_model_is_blended_but_market_anchored():
    model = {"source": None, "probs": {"1": 0.30, "X": 0.30, "2": 0.40}, "lambda_home": 1.1, "lambda_away": 1.3, "rho": 0}
    fc = forecast.build({"odds": ODDS, "model": model, "market_model": _mm(), "league": "TR1"})
    q = forecast.fair_1x2(ODDS)
    assert fc["basis"] == "piyasa+model" and fc["outcome"] == "1" and abs(fc["probs"]["1"] - q["1"]) < 0.06
    assert fc["lambda_source"] == "piyasa"


def test_move_from_own_snapshots():
    hist = [{"t": "a", "1": 1.9, "X": 3.5, "2": 4.0}, {"t": "b", "1": 1.55, "X": 3.9, "2": 5.2}]
    fc = forecast.build({"odds": ODDS, "model": _mm(), "odds_history": hist})
    assert fc["move"]["dir"] == "güçleniyor" and fc["move"]["delta"] > 0.015


def test_grade_and_scorecard_summary():
    fc = forecast.build({"odds": ODDS, "model": _mm()})
    g = forecast.grade(fc, [2, 0])
    assert g["hit"] is True and g["ou_hit"] in (True, False) and "score_hit" in g
    assert forecast.grade(None, [1, 0]) is None
    retro = forecast.grade_from_markets([{"m": "1", "q": 0.6}, {"m": "X", "q": 0.25}, {"m": "2", "q": 0.15},
                                         {"m": "O2.5", "q": 0.55}], "0-1")
    assert retro["o"] == "1" and retro["hit"] is False and retro["retro"] and retro["ou_hit"] is False
    s = forecast.summarize([{"fc": g}, {"fc": retro}, {}], scorecard.wilson_ci)
    assert s["n"] == 2 and s["hit_rate"] == 0.5 and s["n_retro"] == 1 and len(s["by_conf"]) == 3
