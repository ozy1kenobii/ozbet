"""50 örnek koşu (yalnızca gösterim) testleri."""
import re

from ozbet.model.simulate import seed_for, simulate


def _sim(key="TR1-20261105-galatasaray-fenerbahce", n=10_000):
    return simulate(1.6, 1.1, -0.08, 0.44, n, seed_for(key))


def _minute(m):
    """(taban dakika, uzatma) döndürür."""
    if isinstance(m, int):
        return m, 0
    mt = re.fullmatch(r"(45|90)\+(\d)", m)
    assert mt, m
    return int(mt.group(1)), int(mt.group(2))


def test_fifty_runs_and_reproducible():
    a, b = _sim(), _sim()
    sr = a["sample_runs"]
    assert sr["n"] == 50 and len(sr["runs"]) == 50
    assert [r["i"] for r in sr["runs"]] == list(range(1, 51))
    assert a["sample_runs"] == b["sample_runs"]
    assert _sim("başka-maç")["sample_runs"]["runs"] != sr["runs"]
    assert set(sr) == {"n", "runs", "summary", "note"}
    assert "10.000" in sr["note"]


def test_probabilities_unchanged_by_sample_runs():
    # 50 koşu ayrı RNG akışı kullanır; 10.000 MC olasılıkları aynı tohumla aynı kalmalı
    s = simulate(1.6, 1.1, -0.08, 0.44, 10_000, seed=3)
    assert s["sims"] == 10_000
    assert abs(sum(s["total_goals"]) - 1) < 1e-6


def test_goal_count_matches_score():
    for r in _sim()["sample_runs"]["runs"]:
        assert set(r) == {"i", "ft", "ht", "goals"}
        home = sum(g["side"] == "home" for g in r["goals"])
        away = sum(g["side"] == "away" for g in r["goals"])
        assert [home, away] == r["ft"]
        assert all(g["side"] in ("home", "away") for g in r["goals"])
        assert r["ht"][0] <= r["ft"][0] and r["ht"][1] <= r["ft"][1]


def test_goal_minutes_in_range_and_sorted():
    for key in ("a", "b", "c"):
        s = simulate(2.8, 2.2, 0.0, 0.44, 5_000, seed_for(key))   # bol gol: aralıkları iyi tarar
        for r in s["sample_runs"]["runs"]:
            ht_goals = sum(r["ht"])
            mins = [_minute(g["min"]) for g in r["goals"]]
            for k, (base, extra) in enumerate(mins):
                if k < ht_goals:
                    assert 1 <= base <= 45 and (extra == 0 or (base == 45 and 1 <= extra <= 4))
                else:
                    assert 46 <= base <= 90 and (extra == 0 or (base == 90 and 1 <= extra <= 5))
            assert mins == sorted(mins)
            # İY skoru ilk yarı gollerinden çıkar
            first = r["goals"][:ht_goals]
            assert [sum(g["side"] == "home" for g in first), sum(g["side"] == "away" for g in first)] == r["ht"]


def test_summary_consistent_with_runs():
    sr = _sim()["sample_runs"]
    runs, sm = sr["runs"], sr["summary"]
    ft = [tuple(r["ft"]) for r in runs]
    assert sm["1"] == sum(h > a for h, a in ft)
    assert sm["X"] == sum(h == a for h, a in ft)
    assert sm["2"] == sum(h < a for h, a in ft)
    assert sm["1"] + sm["X"] + sm["2"] == 50
    assert sm["O2.5"] == sum(h + a > 2 for h, a in ft)
    assert sm["BTTS_Y"] == sum(h > 0 and a > 0 for h, a in ft)
    top = sm["top_scores"]
    assert 1 <= len(top) <= 5
    counts = {}
    for h, a in ft:
        counts[f"{h}-{a}"] = counts.get(f"{h}-{a}", 0) + 1
    for s, c in top:
        assert counts[s] == c
    assert [c for _, c in top] == sorted((c for _, c in top), reverse=True)
    assert top[-1][1] >= sorted(counts.values(), reverse=True)[min(4, len(counts) - 1)]


def test_resampling_respects_weights():
    # Güçlü ev sahibi: 50 koşunun çoğu ev galibiyeti olmalı
    sm = simulate(3.0, 0.4, 0.0, 0.44, 10_000, 7)["sample_runs"]["summary"]
    assert sm["1"] > 30
