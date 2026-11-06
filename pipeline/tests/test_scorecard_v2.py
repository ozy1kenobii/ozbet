from datetime import date

from ozbet.agents import scorecard


def _match(mid="m1", value=()):
    return {
        "id": mid, "league": "TR1", "league_name": "Süper Lig",
        "home": {"name": "A"}, "away": {"name": "B"},
        "odds": {"1": 2.0, "X": 3.4, "2": 3.8, "HT_1": 2.9, "O2.5": 1.9, "C_O9.5": 1.8, "HTFT_1/1": 3.5},
        "model": {"probs": {"1": 0.5, "X": 0.27, "2": 0.23, "O2.5": 0.55},
                  "extra": {"HT_1": 0.31}, "htft": {"1/1": 0.3},
                  "corners": {"probs": {"C_O9.5": 0.5}}},
        "market": {"implied": {"1": 0.47, "X": 0.28, "2": 0.25, "HT_1": 0.29, "O2.5": 0.5, "C_O9.5": 0.52,
                               "HTFT_1/1": 0.27}},
        "value": [{"market": k} for k in value],
        "pick": {"market": "1", "label": "MS 1", "p": 0.5, "odds": 2.0},
    }


def _grade(ft, ht, value=(), d="2026-11-05", mid="m1"):
    doc = {"date": d, "matches": [_match(mid, value)]}
    return scorecard.grade_day(doc, {mid: {"ft": ft, "ht": ht}})


def test_markets_settled_and_corner_skipped():
    row = _grade([2, 1], [1, 0])[0]
    mk = {e["m"]: e for e in row["markets"]}
    assert set(mk) == {"1", "X", "2", "HT_1", "O2.5", "HTFT_1/1"}   # korner sonucu yok → atlanır
    assert mk["HT_1"] == {"m": "HT_1", "p": 0.31, "q": 0.29, "o": 2.9, "won": True}
    assert mk["O2.5"]["won"] and mk["HTFT_1/1"]["won"] and not mk["X"]["won"]


def test_ht_markets_skipped_without_ht():
    row = _grade([2, 1], None)[0]
    ms = {e["m"] for e in row["markets"]}
    assert "HT_1" not in ms and "HTFT_1/1" not in ms and "1" in ms


def test_by_category_and_buckets():
    rows = _grade([2, 1], [1, 0]) + _grade([0, 0], [0, 0], mid="m2")
    card = scorecard.build_scorecard(rows, date(2026, 11, 6))
    cats = {c["category"]: c for c in card["by_category"]}
    assert set(cats) == {"ms", "gol", "yari"}
    ms = cats["ms"]
    assert ms["n"] == 6
    # MS 1: (0.5-1)^2 + (0.5-0)^2 ; X: 0.27^2+(0.73)^2 ; 2: 0.23^2*2
    exp = ((0.25 + 0.25) + (0.0729 + 0.5329) + 2 * 0.0529) / 6
    assert abs(ms["model_brier"] - round(exp, 4)) < 1e-4
    assert ms["market_logloss"] > 0 and ms["model_logloss"] > 0
    cm = card["calibration_markets"]
    assert sum(b["n"] for b in cm["model"]) == sum(c["n"] for c in card["by_category"])
    for b in cm["market"]:
        lo, hi = map(float, b["bin"].split("-"))
        assert lo <= b["predicted"] <= hi and 0 <= b["observed"] <= 1


def test_value_bets_scored_with_iddaa_odds():
    rows = _grade([2, 1], [1, 0], value=("HT_1", "X"))
    vb = scorecard.build_scorecard(rows, date(2026, 11, 6))["value_bets"]
    assert vb["n"] == 2 and vb["hit_rate"] == 0.5
    assert vb["profit"] == round(1.9 - 1, 2) and vb["roi"] == round(0.9 / 2, 4)


def test_value_bets_empty():
    vb = scorecard.build_scorecard([], date(2026, 11, 6))["value_bets"]
    assert vb["n"] == 0 and vb["roi"] is None


def test_trust_works_for_new_markets():
    rows = []
    for i in range(25):   # İY 1: model 0.31 der, hiç tutmaz → güven düşer
        rows += _grade([0, 1], [0, 1], d="2026-11-01", mid=f"m{i}")
    t = scorecard.trust_from(rows, date(2026, 11, 6))
    assert t["HT_1"] < 1.0 and t["HT_1"] >= 0.6
    assert "HTFT_1/1" in t and "C_O9.5" not in t
    # eski (markets alanı olmayan) satırlar hâlâ tercih üzerinden çalışır
    old = [{"date": "2026-11-01", "pick": "O2.5", "p": 0.6, "won": False} for _ in range(20)]
    assert scorecard.trust_from(old, date(2026, 11, 6))["O2.5"] == 0.6
