"""Faz 2: ek gol marketleri, korner/kart modeli, market sonuçlandırma, genişletilmiş piyasa/değer hesabı."""
import datetime as dt

import numpy as np
import pytest

from ozbet import validate
from ozbet.agents import market, value
from ozbet.markets import EXTRA_GROUPS, EXTRA_LABELS, all_groups, all_labels, all_probs, settle
from ozbet.model import counts
from ozbet.model.dixon_coles import score_matrix
from ozbet.model.simulate import simulate


@pytest.fixture(scope="module")
def sim():
    return simulate(1.7, 1.1, -0.06, 0.44, 10_000, seed=7)


def test_extra_keys_labelled_and_groups_sum_to_one(sim):
    e = sim["extra"]
    assert set(e) == set(EXTRA_LABELS)
    for g, ks in EXTRA_GROUPS.items():
        assert abs(sum(e[k] for k in ks) - 1) < 1e-3, g


def test_extra_consistent_with_score_matrix(sim):
    m = score_matrix(1.7, 1.1, -0.06, 12)
    h = np.arange(13)[:, None]; a = np.arange(13)[None, :]
    exact = {
        "ODD": m[(h + a) % 2 == 1].sum(), "G2-3": m[((h + a) >= 2) & ((h + a) <= 3)].sum(),
        "HCP-1_1": m[(h - a - 1) > 0].sum(), "H_O1.5": m[h.repeat(13, 1) > 1].sum(),
        "1&O2.5": m[(h > a) & ((h + a) > 2)].sum(), "H_WIN_NIL": m[(h > a) & (a == 0)].sum(),
    }
    for k, v in exact.items():
        assert abs(sim["extra"][k] - v) < 0.02, k


def test_half_markets_sane(sim):
    e = sim["extra"]
    assert e["HT_X"] > sim["probs"]["X"]           # ilk yarıda beraberlik daha olası
    assert e["HT_O0.5"] < sim["probs"]["O0.5"] if "O0.5" in sim["probs"] else e["HT_O0.5"] < e["O0.5"]
    assert e["MGH_2"] > e["MGH_1"]                  # ikinci yarı daha gollü (ht_share < 0.5)


@pytest.mark.parametrize("mk,ft,ht,exp", [
    ("HT_X", [2, 1], [0, 0], True), ("2H_1", [2, 1], [0, 1], True), ("MGH_2", [3, 1], [1, 0], True),
    ("HCP-1_X", [2, 1], None, True), ("HCP+1_2", [0, 2], None, True), ("G4-5", [3, 2], None, True),
    ("EVEN", [1, 1], None, True), ("A_U0.5", [2, 0], None, True), ("X&BTTS_Y", [1, 1], None, True),
    ("BTTS_N&U2.5", [1, 0], None, True), ("H_WIN_HALF", [1, 1], [1, 0], True), ("HT_1", [2, 0], None, None),
    ("C_O9.5", [1, 0], [0, 0], None),
])
def test_settle(mk, ft, ht, exp):
    assert settle(mk, ft, ht) is exp


def _rows(seed=3, n=16):
    rng = np.random.default_rng(seed)
    g = rng.normal(0, .15, n); al = rng.normal(0, .1, n)
    rows, d0 = [], dt.date(2025, 8, 1)
    refs = {f"R{i}": 1 + (0.3 if i == 0 else 0) for i in range(8)}
    for k in range(3):
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                ref = f"R{(i + j + k) % 8}"
                mh = np.exp(np.log(5.3) + .1 + g[i] + al[j]); ma = np.exp(np.log(5.3) + g[j] + al[i])
                rows.append(dict(date=d0 + dt.timedelta(days=len(rows) // 5), home=f"t{i}", away=f"t{j}",
                                 hc=rng.negative_binomial(mh / .4, 1 / 1.4), ac=rng.negative_binomial(ma / .4, 1 / 1.4),
                                 hy=rng.poisson(2.0 * refs[ref]), ay=rng.poisson(2.2 * refs[ref]), hr=0, ar=0,
                                 referee=ref))
    return rows, g


def test_corner_model_recovers_strength_and_dispersion():
    rows, g = _rows()
    ref = rows[-1]["date"] + dt.timedelta(days=1)
    C = counts.fit(rows, ref, 0.0, "corners")
    assert np.corrcoef([C.gen[f"t{i}"] for i in range(len(g))], g)[0, 1] > 0.85
    assert 1.15 < C.phi < 1.7
    p = counts.predict(C, "t0", "t1", None, "k")
    assert abs(p["probs"]["C_O9.5"] + p["probs"]["C_U9.5"] - 1) < 1e-6
    assert p["probs"]["C_O7.5"] > p["probs"]["C_O9.5"] > p["probs"]["C_O11.5"]
    assert abs(sum(p["probs"][k] for k in ("CR_1", "CR_X", "CR_2")) - 1) < 1e-6


def test_card_model_referee_effect():
    rows, _ = _rows()
    ref = rows[-1]["date"] + dt.timedelta(days=1)
    K = counts.fit(rows, ref, 0.0, "cards")
    assert K.ref_factor["R0"] > 1.15 and abs(K.ref_factor["R3"] - 1) < 0.15
    strict = counts.predict(K, "t0", "t1", "R0", "k")
    plain = counts.predict(K, "t0", "t1", "Bilinmeyen Hakem", "k")
    assert strict["exp_total"] > plain["exp_total"] and plain["referee_factor"] is None
    assert counts.fit(rows[:50], ref, 0.0, "cards") is None   # az veri → model yok


def test_implied_and_value_cover_extra_markets(sim):
    model = {**sim, "corners": {"probs": {"C_O9.5": 0.6, "C_U9.5": 0.4}}}
    odds = {"1": 1.9, "X": 3.4, "2": 4.0, "HT_1": 2.6, "HT_X": 2.1, "HT_2": 4.6, "ODD": 1.85, "EVEN": 1.85,
            "C_O9.5": 1.85, "C_U9.5": 1.85}
    mk = market.implied(odds)
    assert {"HT_1", "ODD", "C_O9.5"} <= set(mk["implied"]) and "ht1x2" in mk["margin"]
    probs = all_probs(model)
    assert "C_O9.5" in probs and "HT_1" in probs and "1" in probs
    v = value.find_value({**probs, "C_O9.5": 0.66}, odds, mk["implied"])
    assert any(x["market"] == "C_O9.5" for x in v)
    assert set(all_groups()) >= set(EXTRA_GROUPS) and "Korner 9.5 Üst" in all_labels().values()


def test_validation_relaxes_margin_for_many_way_groups():
    rep = validate.Report()
    six = {f"{r}&{m}": 4.6 for r in "1X2" for m in ("O2.5", "U2.5")}   # marj ≈ %30
    assert len(validate.clean_odds(six, rep)) == 6
    assert len(validate.clean_odds({"ODD": 1.3, "EVEN": 1.3}, rep)) == 0   # 2 yollu marj %54 → at
