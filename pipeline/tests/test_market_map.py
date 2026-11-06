"""Belirsiz iddaa marketlerinin veriyle çözülmesi ve iddaa ek market ayrıştırması."""
import numpy as np
import pytest

from ozbet.agents import market_map
from ozbet.markets import all_probs
from ozbet.model.simulate import simulate
from ozbet.sources import iddaa

INV = {"1": "1", "X": "0", "2": "2"}


def _odds(p, margin=0.08):
    return round(1 / (p * (1 + margin)), 2)


def _raw(model, swap_half=False, swap_team=False, hcp_dep=False, mskg_st="698", noise=0.0, rng=None):
    """Modelin olasılıklarından (biraz gürültüyle) iddaa ham marketleri üret. swap_* = gerçek kod anlamı ters."""
    p = all_probs(model)
    jit = (lambda x: min(0.97, max(0.03, x + rng.normal(0, noise)))) if noise else (lambda x: x)
    raw = {}
    ht, h2 = ("88", "36") if swap_half else ("36", "88")
    raw[ht] = [{"sov": None, "o": {INV[k]: _odds(jit(p[f"HT_{k}"])) for k in "1X2"}}]
    raw[h2] = [{"sov": None, "o": {INV[k]: _odds(jit(p[f"2H_{k}"])) for k in "1X2"}}]
    hs, as_ = ("604", "603") if swap_team else ("603", "604")
    for st, side in ((hs, "H"), (as_, "A")):
        raw[st] = [{"sov": "1.5", "o": {"Üst": _odds(jit(p[f"{side}_O1.5"])), "Alt": _odds(jit(p[f"{side}_U1.5"]))}}]
    sov = "1" if hcp_dep else "-1"     # gerçek: ev sahibine -1
    raw["100"] = [{"sov": sov, "o": {INV[k]: _odds(jit(p[f"HCP-1_{k}"])) for k in "1X2"}}]
    names = {f"{r}&BTTS_{y}": f"{INV[r]} ve {'Var' if y == 'Y' else 'Yok'}" for r in "1X2" for y in "YN"}
    raw[mskg_st] = [{"sov": None, "o": {n: _odds(jit(p[k])) for k, n in names.items()}}]
    other = "699" if mskg_st == "698" else "698"
    raw[other] = [{"sov": None, "o": {n: 6.0 for n in names.values()}}]   # anlamsız market
    return raw


@pytest.fixture(scope="module")
def models():
    rng = np.random.default_rng(1)
    out = []
    for i in range(14):
        lh, la = rng.uniform(0.8, 2.2), rng.uniform(0.6, 1.8)
        out.append(simulate(lh, la, -0.05, 0.44, 4000, seed=i))
    return out


@pytest.mark.parametrize("swap_half,swap_team,hcp_dep,mskg", [
    (False, False, False, "698"), (True, True, True, "699"),
])
def test_resolve_finds_true_mapping(models, swap_half, swap_team, hcp_dep, mskg):
    rng = np.random.default_rng(5)
    samples = [(_raw(m, swap_half, swap_team, hcp_dep, mskg, noise=0.03, rng=rng), m) for m in models]
    dec, rep = market_map.resolve(samples)
    assert dec["half"] == ("36=2H" if swap_half else "36=HT")
    assert dec["team"] == ("603=A" if swap_team else "603=H")
    assert dec["hcp"] == ("sov=dep" if hcp_dep else "sov=ev")
    assert dec["mskg"] == mskg
    odds = {}
    n = market_map.apply(samples[0][0], odds, dec)
    assert n > 10 and {"HT_1", "2H_X", "H_O1.5", "A_U1.5", "HCP-1_1", "1&BTTS_Y"} <= set(odds)
    # doğru eşleşmede ev sahibi İY oranı, modelin İY olasılığına yakın
    p = all_probs(samples[0][1])
    assert abs(1 / odds["HT_1"] / 1.08 - p["HT_1"]) < 0.08


def test_resolve_refuses_with_few_samples(models):
    dec, rep = market_map.resolve([(_raw(m), m) for m in models[:3]])
    assert all(v is None for v in dec.values()) and rep["half"]["why"] == "yetersiz örnek"


def test_iddaa_extra_parsing():
    ms = [
        {"st": 60, "sov": "0.5", "o": [{"n": "Alt", "odd": 3.1}, {"n": "Üst", "odd": 1.3}]},
        {"st": 91, "o": [{"n": "Tek", "odd": 1.9}, {"n": "Çift", "odd": 1.8}]},
        {"st": 4, "o": [{"n": "0-1 gol", "odd": 4.0}, {"n": "2-3 gol", "odd": 2.0}, {"n": "4-5 gol", "odd": 3.6}, {"n": "6+ gol", "odd": 12.0}]},
        {"st": 6, "o": [{"n": "1.", "odd": 3.2}, {"n": "Eşit", "odd": 3.3}, {"n": "2.", "odd": 2.0}]},
        {"st": 7, "sov": "2.5", "o": [{"n": f"{r} ve {ou}", "odd": 5.0} for r in "102" for ou in ("Alt", "Üst")]},
        {"st": 700, "sov": "2.5", "o": [{"n": f"{ou} ve {kg}", "odd": 3.5} for ou in ("Alt", "Üst") for kg in ("Var", "Yok")]},
        {"st": 90, "o": [{"n": f"{a}/{b}", "odd": 9.0} for a in "102" for b in "102"]},
        {"st": 48, "sov": "9.5", "o": [{"n": "Alt", "odd": 1.9}, {"n": "Üst", "odd": 1.8}]},
        {"st": 49, "sov": "4.5", "o": [{"n": "Alt", "odd": 1.7}, {"n": "Üst", "odd": 2.0}]},
        {"st": 36, "o": [{"n": "1", "odd": 3.0}, {"n": "0", "odd": 2.0}, {"n": "2", "odd": 4.0}]},
    ]
    od = iddaa.parse_markets(ms)
    for k in ("HT_O0.5", "HT_U0.5", "ODD", "EVEN", "G0-1", "G6+", "MGH_X", "X&O2.5", "2&U2.5",
              "BTTS_Y&O2.5", "BTTS_N&U2.5", "HTFT_X/2", "HTFT_1/1", "C_O9.5", "K_U4.5"):
        assert k in od, k
    assert "HT_1" not in od and od["__raw__"]["36"][0]["o"]["0"] == 2.0   # belirsiz → ham
