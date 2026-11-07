import numpy as np
import pytest
from scipy.stats import poisson

from ozbet.markets import probs_from_matrix
from ozbet.model import market_lambda as ml


def _odds_from(lh, la, rho, margin=0.0, ht_share=None):
    p = probs_from_matrix(ml.score_matrix(lh, la, rho))
    odds = {}
    for keys in (("1", "X", "2"), ("O1.5", "U1.5"), ("O2.5", "U2.5"), ("O3.5", "U3.5"), ("BTTS_Y", "BTTS_N")):
        for k in keys:
            odds[k] = 1 / (p[k] * (1 + margin))
    if ht_share:
        g = np.arange(11)
        m = np.outer(poisson.pmf(g, lh * ht_share), poisson.pmf(g, la * ht_share))
        h, a = g[:, None], g[None, :]
        for k, v in (("HT_1", m[h > a].sum()), ("HT_X", np.trace(m)), ("HT_2", m[h < a].sum())):
            odds[k] = 1 / v
    return odds


@pytest.mark.parametrize("lh,la,rho", [(1.6, 1.1, -0.08), (0.9, 1.4, -0.02), (2.4, 0.6, -0.1)])
def test_recovers_known_lambdas(lh, la, rho):
    fit = ml.from_odds(_odds_from(lh, la, rho))
    assert fit["lambda_home"] == pytest.approx(lh, rel=0.02)
    assert fit["lambda_away"] == pytest.approx(la, rel=0.02)
    assert fit["rho"] == pytest.approx(rho, abs=0.02)
    assert fit["fit_kl"] < 1e-5


def test_recovers_with_margin_and_ht_share():
    fit = ml.from_odds(_odds_from(1.5, 1.2, -0.05, margin=0.08, ht_share=0.41))
    assert fit["lambda_home"] == pytest.approx(1.5, rel=0.06)
    assert fit["lambda_away"] == pytest.approx(1.2, rel=0.06)
    assert fit["ht_share"] == pytest.approx(0.41, abs=0.01)


def test_missing_markets():
    assert ml.from_odds(None) is None
    assert ml.from_odds({"1": 2.0, "X": 3.2, "2": 3.6}) is None          # gol marketi yok
    assert ml.from_odds({"O2.5": 1.9, "U2.5": 1.9}) is None              # 1X2 yok
    only = {k: v for k, v in _odds_from(1.4, 1.0, -0.05).items() if k in ("1", "X", "2", "BTTS_Y", "BTTS_N")}
    fit = ml.from_odds(only)                                              # yalnız 1X2 + KG yeterli
    assert fit and fit["ht_share"] == ml.DEFAULT_HT_SHARE
    assert 0.9 < fit["lambda_home"] / fit["lambda_away"] < 2.2


def test_extreme_odds():
    o = {"1": 1.03, "X": 21.0, "2": 51.0, "O2.5": 1.25, "U2.5": 3.9}
    fit = ml.from_odds(o)
    assert fit["lambda_home"] > 2.5 and fit["lambda_away"] < 0.7
    o = {"1": 1.01, "X": 0, "2": 101.0, "O2.5": 1.9, "U2.5": 1.9}   # bozuk X oranı → 1X2 grubu yok
    assert ml.from_odds(o) is None


def test_build_model_and_consistency():
    odds = _odds_from(1.5, 1.1, -0.05, margin=0.07)
    odds.update({"ODD": 1.80, "EVEN": 1.80, "G2-3": 1.5, "HT_1": 3.0})
    mdl = ml.build_model(odds, seed=3, sims=4000)
    assert mdl["source"] == "piyasa" and ml.NOTE in mdl["notes"]
    assert len(mdl["sample_runs"]["runs"]) == 50 and "HCP-1_1" in mdl["extra"]
    rows = ml.consistency(odds, mdl)
    assert rows and all(r["market"] not in ("1", "O2.5", "BTTS_Y") for r in rows)
    assert rows == sorted(rows, key=lambda r: -r["ev"])
    assert ml.consistency(odds, None) == []
