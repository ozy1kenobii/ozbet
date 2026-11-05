import datetime as dt

import numpy as np
import pytest

from ozbet.agents import commentator, consensus, market, scorecard, value
from ozbet.agents.bulletin import league_for, merge, same_match
from ozbet.markets import outcome_won, probs_from_matrix
from ozbet.model.dixon_coles import fit, score_matrix, tau
from ozbet.model.simulate import simulate
from ozbet.sources.base import Fixture, StatusBoard
from ozbet.teams import TeamMatcher, canonical, team_key
from ozbet import config


# ---------- takım eşleme ----------
@pytest.mark.parametrize("a,b", [
    ("Fenerbahçe", "Fenerbahce"), ("Fenerbahçe SK", "Fenerbahce"), ("Beşiktaş JK", "Besiktas"),
    ("RAMS Başakşehir", "Buyuksehyr"), ("Ç. Rizespor", "Rizespor"), ("Man Utd", "Manchester United"),
    ("Gaziantep FK", "Gaziantep"), ("Atlético de Madrid", "Ath Madrid"),
])
def test_team_key_aliases(a, b):
    assert team_key(a) == team_key(b)


def test_matcher_fuzzy_and_no_false_positive():
    tm = TeamMatcher(["Galatasaray", "Fenerbahce", "Man City", "Man United", "Goztepe", "Kasimpasa"])
    assert tm.match("Göztepe A.Ş.") == "Goztepe"
    assert tm.match("Kasımpaşa SK") == "Kasimpasa"
    assert tm.match("Manchester City") == "Man City"
    assert tm.match("Manchester United") == "Man United"
    assert tm.match("Real Madrid") is None


# ---------- marketler ----------
def test_probs_from_matrix_consistency():
    m = score_matrix(1.5, 1.1, -0.05)
    p = probs_from_matrix(m)
    assert abs(p["1"] + p["X"] + p["2"] - 1) < 1e-9
    assert abs(p["O2.5"] + p["U2.5"] - 1) < 1e-9
    assert p["O1.5"] > p["O2.5"] > p["O3.5"]
    assert abs(p["1X"] - (p["1"] + p["X"])) < 1e-9


def test_outcome_won():
    assert outcome_won("O2.5", 2, 1) and not outcome_won("U2.5", 2, 1)
    assert outcome_won("BTTS_Y", 1, 1) and outcome_won("BTTS_N", 2, 0)
    assert outcome_won("X2", 0, 0) and not outcome_won("1X", 0, 1)


def test_tau_identity():
    assert tau(2, 3, 1.2, 1.0, -0.1) == 1.0
    assert tau(1, 1, 1.2, 1.0, -0.1) == pytest.approx(1.1)


# ---------- model ----------
def _synthetic(seed=1, n=18, rounds=3):
    rng = np.random.default_rng(seed)
    att = rng.normal(0, .3, n); de = rng.normal(0, .25, n)
    mu, h = np.log(1.3), 0.25
    rows, d0 = [], dt.date(2024, 8, 1)
    for _ in range(rounds):
        for i in range(n):
            for j in range(n):
                if i != j:
                    lh = np.exp(mu + h + att[i] + de[j]); la = np.exp(mu + att[j] + de[i])
                    hg, ag = rng.poisson(lh), rng.poisson(la)
                    rows.append(dict(date=d0 + dt.timedelta(days=len(rows) // 6), home=f"T{i}", away=f"T{j}",
                                     hg=int(hg), ag=int(ag), hthg=int(hg // 2), htag=int(ag // 2), season="x"))
    return rows, att


def test_fit_recovers_strengths():
    rows, att = _synthetic()
    R = fit(rows, rows[-1]["date"] + dt.timedelta(days=1), xi=0.0, l2=0.01)
    est = np.array([R.attack[f"T{i}"] for i in range(len(att))])
    assert np.corrcoef(est, att)[0, 1] > 0.85
    assert 0.1 < R.home < 0.4


def test_simulation_matches_exact():
    s = simulate(1.6, 1.1, -0.08, 0.44, 10_000, seed=3)
    e = probs_from_matrix(score_matrix(1.6, 1.1, -0.08))
    for k in ("1", "X", "2", "O2.5", "BTTS_Y"):
        assert abs(s["probs"][k] - e[k]) < 0.02
    assert abs(sum(s["htft"].values()) - 1) < 1e-3
    assert abs(sum(s["total_goals"]) - 1) < 1e-6
    assert len(s["score_matrix"]) == 6 and len(s["top_scores"]) == 5


# ---------- piyasa / değer ----------
def test_implied_removes_margin():
    mk = market.implied({"1": 2.0, "X": 3.4, "2": 3.6, "O2.5": 1.85, "U2.5": 1.95})
    imp = mk["implied"]
    assert abs(imp["1"] + imp["X"] + imp["2"] - 1) < 1e-3
    assert mk["margin"]["1x2"] > 0


def test_movement_drop_alarm():
    mv, al = market.movement([{"t": "a", "1": 2.20}, {"t": "b", "1": 2.00}])
    assert mv["1"] == pytest.approx(-0.0909, abs=1e-3) and al == ["1"]


def test_value_threshold_and_trust():
    probs = {"1": 0.53, "X": 0.26, "2": 0.21}
    odds = {"1": 2.2, "X": 3.4, "2": 4.0}
    imp = market.implied(odds)["implied"]
    v = value.find_value(probs, odds, imp)
    assert v and v[0]["market"] == "1"
    assert not value.find_value(probs, odds, imp, trust={"1": 0.6})  # kötü karne → büzülür


# ---------- konsensüs / yorum ----------
def test_consensus_phrase():
    assert consensus.phrase(4, 5, "BTTS_Y") == "5 kaynaktan 4'ü KG Var diyor"
    assert consensus.phrase(3, 3, "1") == "3 kaynağın tümü MS 1 diyor"


def test_comment_has_no_banned_words_and_pick():
    s = simulate(1.9, 0.8, -0.05, 0.44, 10_000, 1)
    m = {"home": {"name": "A"}, "away": {"name": "B"}, "model": {**s, "data_quality": "high"},
         "odds": None, "value": [], "flags": [],
         "stats": {"home": {"venue_form": list("WWWWDL"), "clean_sheets_venue": 4, "failed_to_score_venue": 0,
                            "o25_pct": 0.7, "btts_pct": 0.5},
                   "away": {"venue_form": list("LLDLWL"), "clean_sheets_venue": 0, "failed_to_score_venue": 3,
                            "o25_pct": 0.6, "btts_pct": 0.4}},
         "consensus": consensus.build([], s["probs"], None)}
    commentator.annotate(m, {}, use_llm=False)
    assert m["pick"] and 1 <= m["pick"]["stars"] <= 5
    low = m["comment"].lower()
    assert not any(b in low for b in ("kesin", "banko", "garanti"))
    assert 3 <= m["comment"].count(".") <= 8


# ---------- bülten ----------
def _fx(h, a, hour=20, src="x", lid=None, odds=None):
    return Fixture(lid, "Süper Lig", dt.datetime(2026, 11, 5, hour, 0, tzinfo=config.TZ), h, a, src, "t",
                   odds=odds or {})


def test_merge_fills_odds():
    prim = [_fx("Fenerbahçe", "Beşiktaş", lid="TR1")]
    other = [_fx("Fenerbahce", "Besiktas", src="fd", odds={"1": 2.0})]
    out = merge(prim, other)
    assert len(out) == 1 and out[0].odds["1"] == 2.0
    assert out[0].extra["odds_sources"]["1"] == "fd"


def test_same_match_time_guard():
    assert not same_match(_fx("A FC", "B FC", 14), _fx("A FC", "B FC", 20))


def test_league_for():
    assert league_for("Türkiye Süper Lig") == "TR1"
    assert league_for("İngiltere Premier Lig") == "ENG1"
    assert league_for("Türkiye Süper Lig Kadınlar") is None


# ---------- karne ----------
def test_scorecard_roundtrip():
    s = simulate(1.6, 1.0, 0, 0.44, 2000, 1)
    doc = {"date": "2026-11-01", "matches": [{
        "id": "m1", "league": "TR1", "league_name": "Süper Lig", "home": {"name": "A"}, "away": {"name": "B"},
        "model": s, "pick": {"market": "1", "label": "MS 1", "p": 0.5, "odds": 2.0, "stars": 3, "is_value": True}}]}
    rows = scorecard.grade_day(doc, {"m1": {"ft": [2, 0], "ht": [1, 0]}})
    assert rows[0]["won"] is True and doc["matches"][0]["status"] == "finished"
    card = scorecard.build_scorecard(rows, dt.date(2026, 11, 5))
    assert card["overall"]["roi"] == 1.0 and card["bankroll"][-1]["balance"] == 101.0


def test_statusboard_never_raises():
    b = StatusBoard()
    assert b.run("x", "X", lambda: 1 / 0) is None
    assert b.items["x"].status == "missing"


# ---------- denetçi bulguları (regresyon) ----------
@pytest.mark.parametrize("q", ["Galatasaray U19", "Galatasaray Kadın", "Bayern Munich II", "Celta Vigo B",
                               "Paris FC", "Inter Miami", "Real Madrid Castilla"])
def test_no_youth_women_reserve_or_lookalike_match(q):
    tm = TeamMatcher(["Galatasaray", "Bayern Munich", "Celta", "Paris SG", "Inter", "Real Madrid"])
    assert tm.match(q) is None


def test_same_match_rejects_youth_and_lookalikes():
    assert not same_match(_fx("Galatasaray", "Fenerbahçe"), _fx("Galatasaray U19", "Fenerbahçe U19"))
    assert not same_match(_fx("Inter", "Roma"), _fx("Inter Miami", "Roma"))
    assert same_match(_fx("Fenerbahçe SK", "Beşiktaş JK"), _fx("Fenerbahce", "Besiktas"))


@pytest.mark.parametrize("raw,exp", [("Premier League 2", None), ("UEFA Youth League", None),
                                     ("Türkiye Süper Lig Kadınlar", None), ("Italya Serie B", "ITA2"),
                                     ("TÜRKİYE: Süper Lig", "TR1"), ("Almanya 2. Bundesliga", "GER2")])
def test_league_for_strict(raw, exp):
    assert league_for(raw) == exp


def test_banned_words_turkish_uppercase():
    assert commentator.has_banned("Bu maç KESİN biter") and commentator.has_banned("GARANTİ")
    assert not commentator.has_banned("Olasılık %55")


def test_max_edge_checked_before_trust_shrink():
    odds = {"1": 2.0, "X": 3.5, "2": 4.0}
    imp = market.implied(odds)["implied"]
    probs = {"1": imp["1"] + 0.30, "X": 0.1, "2": 0.1}
    assert value.find_value(probs, odds, imp, trust={"1": 0.6}) == []


def test_rho_bounds_keep_tau_positive():
    from ozbet.model.dixon_coles import clamp_rho
    r = clamp_rho(0.3, 2.5, 1.5)
    assert tau(0, 0, 2.5, 1.5, r) > 0 and r <= 1 / (2.5 * 1.5)
    s = simulate(2.5, 1.5, 0.3, 0.44, 5000, 1)
    assert s["score_matrix"][0][0] >= 0 and abs(sum(s["total_goals"]) - 1) < 1e-6


def test_value_blend_weight(monkeypatch):
    monkeypatch.setattr(config, "MODEL_WEIGHT", 0.4)
    odds = {"1": 2.2, "X": 3.4, "2": 4.0}
    imp = market.implied(odds)["implied"]
    # ham fark 0.10 → harmanla 0.04 < %5 eşik → değer yok
    assert value.find_value({"1": imp["1"] + 0.10, "X": 0.2, "2": 0.2}, odds, imp) == []
    v = value.find_value({"1": imp["1"] + 0.15, "X": 0.2, "2": 0.2}, odds, imp)
    assert v and abs(v[0]["edge"] - 0.06) < 1e-3


def test_merge_carries_source_ids():
    a = _fx("Fenerbahçe", "Beşiktaş", lid="TR1")
    b = _fx("Fenerbahce", "Besiktas", src="flashscore")
    b.extra["flashscore_id"] = "abc"
    assert merge([a], [b])[0].extra["flashscore_id"] == "abc"
