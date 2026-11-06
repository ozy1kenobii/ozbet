import datetime as dt

from ozbet import config
from ozbet.agents import standings, stats, trends

TODAY = dt.date(2026, 11, 6)
SEASON = config.season_codes(TODAY)[0]


def g(d, h, a, hg, ag, season=SEASON, **kw):
    r = {"date": dt.date(2026, 9, 1) + dt.timedelta(days=d), "season": season, "home": h, "away": a,
         "hg": hg, "ag": ag, "hthg": None, "htag": None, "hc": None, "ac": None, "hy": None, "ay": None}
    r.update(kw)
    return r


def test_standings_points_and_goal_difference_tiebreak():
    rows = [g(0, "A", "B", 3, 0), g(1, "C", "D", 1, 0), g(2, "B", "C", 1, 1), g(3, "D", "A", 2, 2),
            g(-400, "D", "A", 9, 0, season="2526"),            # eski sezon sayılmaz
            g(100, "A", "C", 5, 0)]                              # bugünden sonra: sayılmaz
    t = standings.build(rows, TODAY)
    assert t["season"] == SEASON and t["updated"] == "2026-09-04"
    r = {x["team"]: x for x in t["rows"]}
    # A ve C 4 puan; A averajı +3, C +1 → A önde
    assert r["A"]["p"] == 4 and r["C"]["p"] == 4 and r["A"]["pos"] == 1 and r["C"]["pos"] == 2
    assert (r["A"]["o"], r["A"]["g"], r["A"]["b"], r["A"]["m"], r["A"]["ag"], r["A"]["yg"], r["A"]["av"]) == (2, 1, 1, 0, 5, 2, 3)
    assert r["A"]["form"] == ["D", "W"]
    home = {x["team"]: x for x in t["home"]}
    assert home["A"]["o"] == 1 and home["A"]["p"] == 3 and "A" in {x["team"] for x in t["away"]}
    assert standings.position(t, "C") == {"team": "C", "pos": 2, "pts": 4, "played": 2}
    assert standings.position(t, "Z") is None


def test_standings_falls_back_to_latest_season_before_kickoff():
    rows = [g(-300, "A", "B", 1, 0, season="2526")]
    t = standings.build(rows, TODAY)
    assert t["season"] == "2526" and t["rows"][0]["team"] == "A"


def _team_rows(results, team="X", venue="home"):
    rows = []
    for i, (gf, ga) in enumerate(results):
        opp = f"O{i}"
        rows.append(g(i, team, opp, gf, ga) if venue == "home" else g(i, opp, team, ga, gf))
    return rows


def test_trend_thresholds():
    # son 6 iç saha: 5'i 2.5 Üst (%83) → kart; KG 3/6 (%50) → kart yok
    rows = _team_rows([(3, 1), (2, 1), (4, 0), (1, 0), (3, 0), (2, 2)][::-1])
    cards = trends.team_cards(rows, "X", "Ekip", "home", TODAY)
    mk = {c["market"]: c for c in cards}
    assert "O2.5" in mk and mk["O2.5"]["hits"] == 5 and mk["O2.5"]["n"] == 6
    assert "BTTS_Y" not in mk and "BTTS_N" not in mk
    assert "son 6 iç saha maçının 5'inde 2.5 Üst" in mk["O2.5"]["text"]
    # 6 maçtır yenilmiyor → 1X serisi
    assert mk["1X"]["hits"] == 6
    # 4 maçtan az → oran kartı yok
    assert not [c for c in trends.team_cards(rows[:4], "X", "Ekip", "home", TODAY) if c["market"] == "O2.5"]


def test_trend_streak_and_ht_and_limits():
    rows = _team_rows([(2, 0)] + [(0, 1)] * 4, venue="away")          # en yeni 4 deplasman maçı kayıp
    for r, ht in zip(rows, [0, 1, 1, 1, 1]):
        r["hthg"], r["htag"] = ht, 0
    cards = trends.team_cards(rows, "X", "Ekip", "away", TODAY)
    mk = {c["market"]: c for c in cards}
    assert mk["1X"]["hits"] == 4 and "kazanamıyor" in mk["1X"]["text"]
    assert mk["A_U0.5"]["hits"] == 4 and mk["A_U0.5"]["n"] == 5      # 5 maçın 4'ünde gol atamadı
    assert mk["HT_O0.5"]["hits"] == 4
    out = trends.build(rows, "Y", "X", "Rakip", "Ekip", TODAY, {"1X": 0.4}, {"1X": 2.1})
    assert len(out) <= trends.MAX_CARDS
    c = next(c for c in out if c["market"] == "1X")
    assert c["p"] == 0.4 and c["odds"] == 2.1 and c["team"] == "away"
    for c in out:
        assert set(c) >= {"team", "text", "market", "hits", "n"}
        low = c["text"].lower()
        assert not any(w in low for w in ("kesin", "banko", "garanti"))


def test_trend_corners_vs_league_average():
    rows = [g(i, "X", f"O{i}", 1, 1, hc=8.0, ac=6.0) for i in range(6)]
    cards = trends.team_cards(rows, "X", "Ekip", "home", TODAY, {"corners": 9.6, "cards": None})
    c = next(c for c in cards if c["market"].startswith("C_"))
    assert c["market"] == "C_O9.5" and c["hits"] == 6


def test_h2h_summary():
    rows = [g(0, "A", "B", 2, 1), g(1, "B", "A", 0, 3), g(2, "A", "B", 1, 1), g(3, "B", "A", 2, 0),
            g(4, "A", "C", 5, 5)]
    s = stats.h2h_summary(rows, "A", "B", TODAY)
    assert s == {"n": 4, "home_wins": 2, "draws": 1, "away_wins": 1, "avg_goals": 2.5, "btts": 2, "o25": 2}
    assert stats.h2h_summary(rows, "A", "Z", TODAY) is None
