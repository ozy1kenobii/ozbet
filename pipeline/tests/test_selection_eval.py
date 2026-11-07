from datetime import date

from ozbet.agents.market import shin
from ozbet.research import selection_eval as se


def test_shin_inverse_roundtrip_and_margin():
    p = [0.5, 0.28, 0.22]
    o = se.shin_inverse(p, 0.20)
    assert abs(sum(1 / x for x in o) - 1.20) < 1e-6
    back = shin(o)
    assert all(abs(a - b) < 1e-4 for a, b in zip(p, back))
    # Shin: marjın daha büyük payı sürprize yüklenir
    assert p[2] * o[2] < p[0] * o[0]


def test_combo_theory():
    assert se.theoretical_combo(0.20, 1) == round(1 / 1.2 - 1, 4)
    assert se.theoretical_combo(0.20, 3) < se.theoretical_combo(0.20, 2) < se.theoretical_combo(0.20, 1) < 0


def _c(k, edge, won=True, odds=2.0, d=date(2025, 1, 1), m="A-B"):
    return {"date": d, "season": "2526", "league": "E0", "match": m, "k": k, "g": se.GROUP[k], "m": 0.5 + edge * 4,
            "q": 0.5, "p": 0.5 + edge, "raw": edge * 4, "edge": edge, "agree": True, "won": won, "clv": 0.0,
            "price": {"max": odds, "avg": odds, "iddaa": odds}}


def test_select_one_per_match_and_stats():
    rule = {"group": "ALL", "odds": (1.0, 99.0), "edge": 0.0, "ev_avg": False, "agree": False, "leagues": "all"}
    sel = se.select([_c("1", 0.01), _c("O2.5", 0.03, won=False)], rule)
    assert len(sel) == 1 and sel[0]["k"] == "O2.5"
    s = se.stats(sel)
    assert s["n"] == 1 and s["roi_iddaa"] == -1.0


def test_site_baseline_rule_needs_raw_edge_at_cap():
    # MODEL_WEIGHT=0.25 iken harman edge ≥ 0.05 için ham fark ≥ 0.20 gerekir; MAX_EDGE 0.20 → neredeyse hiç seçim yok
    c = _c("1", 0.049, odds=2.5)
    assert not se.baseline_rule(c)


def test_kelly_skips_negative_ev():
    sel = [_c("1", 0.01, odds=1.5, m=f"m{i}") for i in range(10)]  # p=0.51, 1.5 oran → EV<0
    b, dd = se.bankroll(sel, "kelly")
    assert b == 100.0 and dd == 0.0
