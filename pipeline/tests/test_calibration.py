"""Kalibre olasılık (model/calibration.py) ve değerlendirme betiği testleri."""
import json
import math

import pytest

from ozbet.model import calibration as cal
from ozbet.model.calibration import calibrated_group, calibrated_prob, family
from ozbet.research import calibration_eval as ce

MARKETS = ["1", "X", "2", "1X", "O2.5", "U2.5", "BTTS_Y", "BTTS_N", "H_O1.5", "HT_1", "HTFT_1/X", "1&O2.5", "C_O9.5"]
GRID = [i / 50 for i in range(1, 50)]


def test_family_mapping():
    assert family("1") == family("X2") == family("HCP-1_X") == "ms"
    assert family("O2.5") == family("U3.5") == family("G2-3") == family("G6+") == family("ODD") == "gol"
    assert family("BTTS_Y") == family("BTTS_N") == "kg"
    assert family("H_O1.5") == family("A_U0.5") == family("H_WIN_NIL") == "takim"
    assert family("HT_1") == family("2H_X") == family("HTFT_1/X") == family("1/X") == family("HT_BTTS_Y") == "yari"
    assert family("MGH_1") == family("H_WIN_HALF") == family("BOTH_HALVES_O0.5") == "yari"
    assert family("1&O2.5") == family("BTTS_Y&U2.5") == "kombi"
    assert family("C_O9.5") == family("KR_1") == family("bilinmeyen") == "diger"


def test_every_known_market_has_a_weighted_family():
    from ozbet.markets import categories
    for c in categories():
        for k in c["keys"]:
            assert family(k) in cal.FAMILY_WEIGHT, k
    # araştırma öncülü: hiçbir aile eski 0.25 harmanından ağır değil; KG ve takım golü en düşük
    assert max(cal.FAMILY_WEIGHT.values()) < 0.25
    assert cal.FAMILY_WEIGHT["kg"] < cal.FAMILY_WEIGHT["ms"]
    assert cal.FAMILY_WEIGHT["gol"] < cal.FAMILY_WEIGHT["ms"]


@pytest.mark.parametrize("market", MARKETS)
def test_bounds(market):
    for mp in (0.0, 1e-9, 0.001, 0.5, 0.999, 1.0):
        for ip in (None, 0.0, 1e-9, 0.004, 0.5, 0.996, 1.0, float("nan")):
            p = calibrated_prob(market, mp, ip)
            assert 0.01 <= p <= 0.99, (market, mp, ip, p)


@pytest.mark.parametrize("market", MARKETS)
def test_monotone_in_model_p(market):
    for ip in (None, 0.15, 0.5, 0.8):
        vals = [calibrated_prob(market, mp, ip) for mp in GRID]
        assert all(b >= a for a, b in zip(vals, vals[1:])), (market, ip)
        if ip is not None and cal.model_weight(market) > 0:
            assert vals[-1] > vals[0]


@pytest.mark.parametrize("market", MARKETS)
def test_monotone_in_implied_p(market):
    for mp in (0.1, 0.5, 0.9):
        vals = [calibrated_prob(market, mp, ip) for ip in GRID]
        assert all(b > a for a, b in zip(vals, vals[1:])), (market, mp)


def test_agreement_returns_market_and_result_lies_between():
    assert calibrated_prob("1", 0.47, 0.47) == pytest.approx(0.47, abs=1e-9)
    for mp, ip in ((0.7, 0.5), (0.3, 0.5), (0.9, 0.2), (0.05, 0.6)):
        p = calibrated_prob("O2.5", mp, ip)
        assert min(mp, ip) <= p <= max(mp, ip)
        assert abs(p - ip) < abs(p - mp)          # piyasaya modelden daha yakın


def test_closer_to_market_than_old_linear_blend():
    for k in ("1", "O2.5", "BTTS_Y", "H_O1.5"):
        for mp, ip in ((0.70, 0.55), (0.40, 0.55), (0.62, 0.50)):
            old = 0.25 * mp + 0.75 * ip
            assert abs(calibrated_prob(k, mp, ip) - ip) < abs(old - ip)


def test_btts_and_totals_weighted_below_1x2():
    mp, ip = 0.65, 0.50
    ms, gol, kg = (calibrated_prob(k, mp, ip) for k in ("1", "O2.5", "BTTS_Y"))
    assert ip < kg < gol < ms < mp


def test_selection_shrink_is_asymmetric():
    # aynı logit farkı: yukarı sapma, aşağı sapmadan daha az taşınır
    lo = lambda p: math.log(p / (1 - p))
    ip = 0.5
    up = calibrated_prob("1", 0.85, ip)      # d = +1.73
    down = calibrated_prob("1", 0.15, ip)    # d = −1.73
    assert lo(up) - lo(ip) < lo(ip) - lo(down)
    # aşağı sapma tam ağırlıkla
    assert lo(down) - lo(ip) == pytest.approx(cal.FAMILY_WEIGHT["ms"] * (lo(0.15) - lo(ip)), abs=1e-9)


def test_selection_shrink_saturates_and_small_gaps_pass():
    assert cal.shrink_excess(-0.8) == -0.8
    assert cal.shrink_excess(0.0) == 0.0
    assert cal.shrink_excess(0.05) == pytest.approx(0.05, rel=0.01)       # küçük fark neredeyse aynen
    assert cal.shrink_excess(5.0) <= cal.EXCESS_CAP
    # pay küçülür: fark büyüdükçe korunan oran azalır
    r = [cal.shrink_excess(d) / d for d in (0.1, 0.5, 1.0, 2.0)]
    assert all(b < a for a, b in zip(r, r[1:]))
    # model ne kadar uçarsa uçsun kazanç sınırlı: w·T logit
    lo = lambda p: math.log(p / (1 - p))
    p = calibrated_prob("1", 0.99, 0.40)
    assert lo(p) - lo(0.40) <= cal.FAMILY_WEIGHT["ms"] * cal.EXCESS_CAP + 1e-9


def test_fallback_without_market_shrinks_to_base_rate():
    base = cal.BASE_RATE["BTTS_Y"]
    hi, lo_ = calibrated_prob("BTTS_Y", 0.75, None), calibrated_prob("BTTS_Y", 0.30, None)
    assert base < hi < 0.75 and 0.30 < lo_ < base
    assert calibrated_prob("BTTS_Y", base, None) == pytest.approx(base, abs=1e-9)
    # taban oranı bilinmeyen market: yalnız 0.5 üstü kırpılır
    assert calibrated_prob("HTFT_1/1", 0.22, None) == pytest.approx(0.22)
    assert 0.5 < calibrated_prob("H_O0.5", 0.80, None) < 0.80
    # geçersiz piyasa değeri = piyasa yok
    assert calibrated_prob("1", 0.6, 0.0) == calibrated_prob("1", 0.6, None) == calibrated_prob("1", 0.6, 1.0)


def test_league_factor_scales_weight(monkeypatch):
    base = calibrated_prob("1", 0.7, 0.5, "TR1")
    assert base == calibrated_prob("1", 0.7, 0.5)
    monkeypatch.setitem(cal.LEAGUE_FACTOR, "TR1", 0.0)
    assert calibrated_prob("1", 0.7, 0.5, "TR1") == pytest.approx(0.5)
    assert calibrated_prob("1", 0.7, 0.5, "ENG1") == base


@pytest.mark.parametrize("keys,probs,implied", [
    (["1", "X", "2"], {"1": 0.60, "X": 0.22, "2": 0.18}, {"1": 0.45, "X": 0.28, "2": 0.27}),
    (["O2.5", "U2.5"], {"O2.5": 0.69, "U2.5": 0.31}, {"O2.5": 0.55, "U2.5": 0.45}),
    (["BTTS_Y", "BTTS_N"], {"BTTS_Y": 0.61, "BTTS_N": 0.39}, {"BTTS_Y": 0.52, "BTTS_N": 0.48}),
    (["1", "X", "2"], {"1": 0.60, "X": 0.22, "2": 0.18}, {}),
])
def test_group_normalises(keys, probs, implied):
    g = calibrated_group(probs, implied, keys)
    assert list(g) == keys
    assert sum(g.values()) == pytest.approx(1.0, abs=1e-12)
    assert all(0 < v < 1 for v in g.values())
    for k in keys:   # normalleştirme küçük bir düzeltmedir
        assert g[k] == pytest.approx(calibrated_prob(k, probs[k], implied.get(k)), abs=0.02)
    assert max(g, key=g.get) == max(keys, key=lambda k: calibrated_prob(k, probs[k], implied.get(k)))


def test_group_edge_cases():
    assert calibrated_group({}, {"1": 0.5}, ["1", "X", "2"]) == {}
    g = calibrated_group({"1": 0.5, "2": 0.2}, None, ["1", "X", "2"])
    assert set(g) == {"1", "2"} and sum(g.values()) == pytest.approx(1.0)
    probs, implied = {"O2.5": 0.6, "U2.5": 0.4, "1": 0.5}, {"O2.5": 0.5, "U2.5": 0.5}
    assert set(calibrated_group(probs, implied, ["O2.5", "U2.5"])) == {"O2.5", "U2.5"}
    assert probs == {"O2.5": 0.6, "U2.5": 0.4, "1": 0.5}      # girdi değişmez


# ---------------------------------------------------------------- değerlendirme betiği
def _rows():
    mk = lambda m, p, q, won: {"m": m, "p": p, "q": q, "o": 1.8, "won": won}
    return [
        {"id": "a", "date": "2026-11-05", "league": "TR1", "pick": "BTTS_Y",
         "markets": [mk("1", 0.60, 0.45, False), mk("BTTS_Y", 0.62, 0.55, True), mk("O2.5", 0.5, 0.5, True),
                     {"m": "X", "p": 0.2, "o": 3.4, "won": False}]},          # q yok → sayılmaz
        {"id": "b", "date": "2026-11-06", "league": "ENG1",
         "markets": [mk("1", 0.30, 0.40, True), mk("H_O1.5", 0.7, 0.5, False), mk("1&O2.5", 0.3, 0.2, False)]},
    ]


def test_evaluate_counts_and_ordering():
    res = ce.evaluate(_rows())
    assert res["n_matches"] == 2 and res["n_days"] == 2
    assert res["overall"]["n"] == 6
    fam = {f["family"]: f for f in res["by_family"]}
    assert fam["ms"]["n"] == 2 and fam["kg"]["n"] == 1 and fam["takim"]["n"] == 1 and fam["kombi"]["n"] == 1
    assert res["picks"]["BTTS_Y"]["n"] == 1 and res["picks"]["hepsi"]["n"] == 1
    assert res["excess"]["hepsi"]["n"] == 3                       # 1 (0.15), H_O1.5 (0.20), 1&O2.5 (0.10)
    for f in fam.values():
        assert set(f["logloss"]) == set(ce.METHODS) and all(v > 0 for v in f["logloss"].values())
    # p == q olan gözlemde dört yöntem aynı
    ps = ce.four_probs("O2.5", 0.5, 0.5)
    assert len({round(v, 9) for v in ps.values()}) == 1
    md = ce.render_md(res)
    assert "| Maç sonucu | 2 |" in md and "Uyarılar" in md


def test_load_rows_dedups_history_and_day_files(tmp_path):
    (tmp_path / "history").mkdir()
    (tmp_path / "history" / "2026-11-05.json").write_text(json.dumps({"rows": _rows()[:1]}), encoding="utf-8")
    (tmp_path / "history" / "bozuk.json").write_text("{", encoding="utf-8")
    match = lambda mid, res: {"id": mid, "league": "TR1", "result": res, "odds": {"1": 2.0, "X": 3.3, "2": 3.6},
                              "model": {"probs": {"1": 0.5, "X": 0.26, "2": 0.24}},
                              "market": {"implied": {"1": 0.46, "X": 0.28, "2": 0.26}},
                              "pick": {"market": "1"}}
    day = {"date": "2026-11-06", "matches": [match("a", {"ft": [1, 0]}), match("c", {"ft": [2, 1]}),
                                             match("d", None)]}
    (tmp_path / "2026-11-06.json").write_text(json.dumps(day), encoding="utf-8")
    (tmp_path / "scorecard.json").write_text("{}", encoding="utf-8")
    rows = ce.load_rows(tmp_path)
    assert [r["id"] for r in rows] == ["a", "c"]
    assert rows[1]["pick"] == "1" and {e["m"] for e in rows[1]["markets"]} == {"1", "X", "2"}
    res = ce.main(["--data", str(tmp_path), "--md", str(tmp_path / "k.md"), "--json", str(tmp_path / "k.json")])
    assert res["n_matches"] == 2 and (tmp_path / "k.md").read_text(encoding="utf-8").startswith("# Kalibre")
    assert json.loads((tmp_path / "k.json").read_text(encoding="utf-8"))["overall"]["n"] == 6
