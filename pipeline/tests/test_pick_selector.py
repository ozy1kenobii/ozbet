"""OZBET Tercihi: beklenen değer seçicisi, oran bandı, pas, yıldız ve değer eşiği testleri."""
import pytest

from ozbet import config
from ozbet.agents import commentator, market, value

SCHEMA = {"market", "label", "p", "odds", "ev", "fair_odds", "stars", "is_value", "kind", "blended"}


@pytest.fixture(autouse=True)
def plain_blend(monkeypatch):
    """Kalibrasyon/lig profili modülleri olsa da olmasa da testler MODEL_WEIGHT harmanıyla (α=1) koşar."""
    monkeypatch.setattr(value, "_cal", None)
    monkeypatch.setattr(commentator, "_league_tier", None)


def _m(probs, odds, **kw):
    mk = market.implied(odds)
    return {"home": {"name": "A"}, "away": {"name": "B"}, "league": "TR1", "odds": odds, "market": mk,
            "model": {"probs": probs, "data_quality": "high", "lambda_home": 1.4, "lambda_away": 1.1},
            "value": [], "flags": [], **kw}


ODDS = {"1": 1.45, "X": 4.2, "2": 6.0, "O2.5": 1.80, "U2.5": 1.80, "BTTS_Y": 1.70, "BTTS_N": 1.90}
PROBS = {"1": 0.70, "X": 0.18, "2": 0.12, "O2.5": 0.56, "U2.5": 0.44, "BTTS_Y": 0.55, "BTTS_N": 0.45,
         "1X": 0.88, "X2": 0.30, "12": 0.82}


def test_low_odds_favourite_is_never_the_pick():
    m = _m(PROBS, ODDS)   # MS 1: p 0.70, oran 1.45, EV +0.015 — ama taban oranın altında
    pk = commentator.choose_pick(m)
    assert pk["market"] == "O2.5" and pk["odds"] >= config.PICK_MIN_ODDS
    assert pk["ev"] == pytest.approx(0.56 * 1.80 - 1, abs=1e-4) and pk["fair_odds"] == round(1 / 0.56, 2)
    assert pk["kind"] == "deger" and pk["blended"] is True and "pick_note" not in m


def test_band_ceiling_min_prob_and_double_chance_excluded():
    odds = {"1": 3.9, "X": 3.3, "2": 1.85, "1X": 1.75, "X2": 1.20, "12": 1.25}
    probs = {"1": 0.40, "X": 0.32, "2": 0.28, "1X": 0.72, "X2": 0.60, "12": 0.68}
    m = _m(probs, odds)
    # MS 1 (3.9) tavanın üstünde, MS X olasılığı 0.33 altında, ÇŞ 1X (EV +0.26) aday değil, MS 2 EV çok düşük
    assert commentator.choose_pick(m) is None
    assert m["pick_note"] == commentator.NOTE_NO_EV
    assert {c["market"] for c in commentator.pick_candidates(m)} == set()


def test_pass_when_ev_below_threshold_and_note_cleared_on_pick(monkeypatch):
    probs = {**PROBS, "O2.5": 0.50, "U2.5": 0.50}   # en iyi EV 0.50·1.80−1 = −0.10 < −0.06
    m = _m(probs, ODDS)
    assert commentator.choose_pick(m) is None and m["pick_note"].startswith("Pas:")
    monkeypatch.setattr(config, "PICK_MIN_EV", -0.12)
    pk = commentator.choose_pick(m)
    assert pk and pk["kind"] == "denge" and pk["ev"] < 0 and "pick_note" not in m


def test_no_odds_or_market_model_gives_note():
    m = _m(PROBS, ODDS)
    m["odds"], m["market"] = None, None
    assert commentator.choose_pick(m) is None and m["pick_note"] == commentator.NOTE_NO_ODDS
    m = _m(PROBS, ODDS)
    m["model"]["source"] = "piyasa"
    assert commentator.choose_pick(m) is None and m["pick_note"] == commentator.NOTE_NO_MODEL


def test_tie_break_prefers_higher_probability():
    odds = {"1": 2.50, "X": 3.3, "2": 2.9, "O2.5": 1.70, "U2.5": 2.10}
    probs = {"1": 0.402, "X": 0.30, "2": 0.298, "O2.5": 0.588, "U2.5": 0.412}
    m = _m(probs, odds)   # EV: MS 1 +0.005, 2.5 Üst −0.0004 → fark < PICK_EV_TIE → olasılığı yüksek olan
    assert commentator.choose_pick(m)["market"] == "O2.5"
    probs["1"] = 0.43     # EV +0.075: fark belirgin → EV kazanır
    assert commentator.choose_pick(_m(probs, odds))["market"] == "1"


def test_raw_gap_guard_and_blend_and_trust(monkeypatch):
    odds = {"1": 2.0, "X": 3.5, "2": 4.0}
    imp = market.implied(odds)["implied"]
    m = _m({"1": imp["1"] + 0.25, "X": 0.2, "2": 0.1}, odds)   # ham fark > MAX_EDGE → veri hatası sayılır
    assert commentator.choose_pick(m) is None
    monkeypatch.setattr(config, "MODEL_WEIGHT", 0.25)
    m = _m({"1": imp["1"] + 0.16, "X": 0.2, "2": 0.1}, odds)
    pk = commentator.choose_pick(m)
    assert pk["p"] == pytest.approx(imp["1"] + 0.04, abs=1e-4)          # 0.25 · ham fark
    assert commentator.choose_pick(m, {"1": 0.5})["p"] == pytest.approx(imp["1"] + 0.02, abs=1e-4)


def test_combo_market_can_be_pick_and_can_be_disabled(monkeypatch):
    combo = {f"{a}&{b}": 9.0 for a in ("BTTS_Y", "BTTS_N") for b in ("O2.5", "U2.5")}
    combo["BTTS_Y&O2.5"] = 2.2
    odds = {**ODDS, **combo}
    m = _m({**PROBS, "O2.5": 0.50, "U2.5": 0.50}, odds)
    m["model"]["extra"] = {"BTTS_Y&O2.5": 0.50, "BTTS_Y&U2.5": 0.1, "BTTS_N&O2.5": 0.1, "BTTS_N&U2.5": 0.3}
    pk = commentator.choose_pick(m)
    assert pk["market"] == "BTTS_Y&O2.5" and pk["label"] == "KG Var & 2.5 Üst"
    monkeypatch.setattr(config, "PICK_INCLUDE_COMBOS", False)
    assert commentator.choose_pick(m) is None


def test_experimental_corner_keys_never_candidates():
    odds = {**ODDS, "C_O9.5": 2.0, "C_U9.5": 2.0}
    m = _m({**PROBS, "O2.5": 0.50, "U2.5": 0.50}, odds)
    m["model"]["corners"] = {"probs": {"C_O9.5": 0.65, "C_U9.5": 0.35}}
    assert commentator.choose_pick(m) is None


def test_annotate_schema_value_flag_and_comment():
    m = _m(PROBS, ODDS)
    m["value"] = value.find_value(PROBS, ODDS, m["market"]["implied"])
    commentator.annotate(m, {}, use_llm=False)
    pk = m["pick"]
    assert set(pk) == SCHEMA and pk["is_value"] is True and 1 <= pk["stars"] <= 5
    assert "OZBET tercihi 2.5 Üst" in m["comment"] and not commentator.has_banned(m["comment"])
    m2 = _m({**PROBS, "O2.5": 0.50, "U2.5": 0.50}, ODDS)
    commentator.annotate(m2, {}, use_llm=False)
    assert m2["pick"] is None and m2["pick_note"] and "OZBET tercihi yok" in m2["comment"]


def test_stars_follow_ev_not_raw_probability():
    m = _m(PROBS, ODDS)
    hi_p = {"market": "1", "p": 0.80, "odds": 1.15, "ev": -0.08, "is_value": False}     # "garanti" görünen favori
    good = {"market": "O2.5", "p": 0.56, "odds": 1.80, "ev": 0.008, "is_value": False}
    assert commentator.stars(m, hi_p, {}) < commentator.stars(m, good, {})
    assert commentator.stars(m, hi_p, {}) <= 3                                           # EV < 0 → en çok 3
    assert commentator.stars(m, good, {"O2.5": 0.7}) < commentator.stars(m, good, {})    # karne güveni düşükse −1


def test_stars_caps_tier_c_and_low_quality(monkeypatch):
    m = _m(PROBS, ODDS)
    pk = {"market": "O2.5", "p": 0.60, "odds": 1.80, "ev": 0.08, "is_value": True}
    assert commentator.stars(m, pk, {}) >= 4
    monkeypatch.setattr(commentator, "_league_tier", lambda lid: "C")
    assert commentator.stars(m, pk, {}) <= 2
    monkeypatch.setattr(commentator, "_league_tier", None)
    m["flags"] = ["Kupa: Elo tabanlı lig-arası düzeltme"]
    assert commentator.stars(m, pk, {}) <= 2


def test_value_threshold_coherent_with_blend(monkeypatch):
    """α=0.25'te eski eşik (harman farkı ≥ 0.05) ham fark ≥ 0.20 isterdi ve MAX_EDGE ile çelişirdi; yeni eşik
    kalibre olasılıkta 0.02 → ham fark 0.08–0.20 aralığı ulaşılabilir, ama EV > 0 şartı etiketi nadir tutar."""
    monkeypatch.setattr(config, "MODEL_WEIGHT", 0.25)
    assert config.VALUE_EDGE_CAL <= config.MODEL_WEIGHT * value.MAX_EDGE
    low = {"1": 1.95, "X": 3.6, "2": 4.2}                      # düşük marjlı (~%3) oran: değer çıkabilir
    imp = market.implied(low)["implied"]
    v = value.find_value({"1": imp["1"] + 0.16, "X": 0.2, "2": 0.1}, low, imp)
    assert v and v[0]["market"] == "1" and v[0]["edge"] == pytest.approx(0.04, abs=1e-3) and v[0]["ev"] > 0
    assert value.find_value({"1": imp["1"] + 0.06, "X": 0.2, "2": 0.1}, low, imp) == []   # 0.015 < eşik
    assert value.find_value({"1": imp["1"] + 0.21, "X": 0.2, "2": 0.1}, low, imp) == []   # ham fark koruması
    iddaa = {"1": 1.80, "X": 3.1, "2": 3.6}                    # ~%16 marj: aynı ham fark EV'yi pozitife çıkarmaz
    imp = market.implied(iddaa)["implied"]
    assert value.find_value({"1": imp["1"] + 0.16, "X": 0.2, "2": 0.1}, iddaa, imp) == []


def test_calibration_module_is_used_when_present(monkeypatch):
    seen = []
    monkeypatch.setattr(value, "_cal", lambda mk, mp, ip, lg=None: seen.append((mk, lg)) or 0.58)
    pk = commentator.choose_pick(_m(PROBS, ODDS))
    assert pk["market"] == "BTTS_N" and pk["p"] == 0.58 and ("O2.5", "TR1") in seen   # 0.58·1.90 en yüksek EV
    monkeypatch.setattr(value, "_cal", lambda *a, **k: 1 / 0)                          # hata → harmana düşer
    assert commentator.choose_pick(_m(PROBS, ODDS))["market"] == "O2.5"


def test_replay_script_runs_on_tmp_data(tmp_path):
    import json
    from ozbet.research import pick_replay
    m = _m(PROBS, ODDS, id="x1", result={"ft": [2, 1], "ht": [1, 0]})
    (tmp_path / "2026-11-05.json").write_text(json.dumps({"date": "2026-11-05", "matches": [m]}))
    out = pick_replay.replay(tmp_path)
    assert out["matches"] == 1 and out["old"]["all"]["n"] == 1 and out["new"]["all"]["n"] == 1
    assert out["old"]["by_market"]["1"]["hit"] == 1.0 and out["new"]["by_market"]["O2.5"]["roi"] == pytest.approx(0.8)
