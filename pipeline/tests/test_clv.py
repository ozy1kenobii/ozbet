import json
from datetime import date

import pytest

from ozbet.agents import clv, scorecard
from ozbet.agents.market import shin


def _arch(mid="m1", o=None, c=None, n_snap=3):
    return {"id": mid, "o": o or {}, "c": c or {}, "ts_o": "2026-11-07T09:00:00+03:00",
            "ts_c": "2026-11-07T19:00:00+03:00" if c else None, "n_snap": n_snap if c else 0}


PICK = {"1": 2.10, "X": 3.20, "2": 3.10, "O2.5": 1.70, "U2.5": 1.75}
CLOSE = {"1": 1.90, "X": 3.30, "2": 3.50, "O2.5": 1.70, "U2.5": 1.75}


def test_clv_margin_free_and_raw():
    r = clv.compute("1", 2.10, PICK, _arch(c=CLOSE))
    fp = shin([2.10, 3.20, 3.10])[0]
    fc = shin([1.90, 3.30, 3.50])[0]
    assert r["status"] == "ok" and r["method"] == "shin"
    assert r["clv"] == pytest.approx(fc / fp - 1, abs=1e-4)
    assert r["clv_raw"] == pytest.approx(2.10 / 1.90 - 1, abs=1e-4)
    assert r["clv"] > 0   # oran kısaldı → kapanışı yendik


def test_clv_negative_when_odds_drift_and_zero_when_unchanged():
    assert clv.compute("2", 3.10, PICK, _arch(c=CLOSE))["clv"] < 0
    same = clv.compute("O2.5", 1.70, PICK, _arch(c=CLOSE))
    assert same["clv"] == 0 and same["clv_raw"] == 0


def test_margin_change_alone_is_not_clv():
    # kapanışta yalnız marj büyüdü (iki taraf da aynı oranda kısaldı): ham CLV pozitif görünür, marjsız ≈ 0
    r = clv.compute("O2.5", 1.80, {"O2.5": 1.80, "U2.5": 1.80}, _arch(c={"O2.5": 1.70, "U2.5": 1.70}))
    assert r["clv_raw"] > 0.05 and abs(r["clv"]) < 1e-6


def test_double_chance_uses_1x2_fair_probs():
    r = clv.compute("1X", 1.30, {**PICK, "1X": 1.30}, _arch(c={**CLOSE, "1X": 1.25}))
    fp = shin([2.10, 3.20, 3.10]); fc = shin([1.90, 3.30, 3.50])
    assert r["method"] == "shin"
    assert r["clv"] == pytest.approx((fc[0] + fc[1]) / (fp[0] + fp[1]) - 1, abs=1e-4)


def test_missing_data_statuses():
    assert clv.compute("1", None, PICK, _arch(c=CLOSE)) == {"status": "no_odds"}
    assert clv.compute("1", 2.1, PICK, None) == {"status": "no_archive"}
    assert clv.compute("1", 2.1, PICK, _arch(o=PICK)) == {"status": "no_close"}      # ko öncesi oran yok
    assert clv.compute("HT_1", 2.9, PICK, _arch(c=CLOSE)) == {"status": "no_market"}  # market arşivde yok


def test_fallback_to_raw_when_group_incomplete():
    # kapanışta grup eksik (X yok) → marj temizlenemez
    r = clv.compute("1", 2.10, PICK, _arch(c={"1": 1.90, "2": 3.50}))
    assert r["method"] == "raw" and r["clv"] == r["clv_raw"] == pytest.approx(0.1053, abs=1e-4)
    # tercih anında diğer oranlar yok (eski satır)
    r = clv.compute("1", 2.10, None, _arch(c=CLOSE))
    assert r["method"] == "raw" and r["clv"] == r["clv_raw"]
    # grubu tanımsız market
    r = clv.compute("ZZZ", 2.0, {"ZZZ": 2.0}, _arch(c={"ZZZ": 1.8}))
    assert r["method"] == "raw" and r["clv"] == pytest.approx(0.1111, abs=1e-4)


def test_open_clv_only_with_later_close():
    r = clv.compute("1", 2.0, PICK, _arch(o={"1": 2.3, "X": 3.1, "2": 2.9}, c=CLOSE))
    assert r["open"]["odds_open"] == 2.3 and r["open"]["clv"] > r["clv"] > 0
    assert "open" not in clv.compute("1", 2.0, PICK, _arch(o=CLOSE, c=CLOSE, n_snap=1))


def _row(mid, pick="1", odds=2.10, won=True, p=0.5, d="2026-11-08", markets=True, **kw):
    r = {"id": mid, "date": d, "league": "TR1", "league_name": "Süper Lig", "match": "A - B", "score": "1-0",
         "pick": pick, "pick_label": "MS 1", "p": p, "odds": odds, "won": won, **kw}
    if markets:
        r["markets"] = [{"m": k, "p": 0.4, "o": v, "won": False} for k, v in PICK.items()]
    return r


def test_scorecard_clv_block_and_recent():
    rows = [_row("m1"), _row("m2", pick="2", odds=3.10, won=False, ev=0.07), _row("m3"), _row("m4", markets=False)]
    arch = [_arch("m1", c=CLOSE), _arch("m2", c=CLOSE), _arch("m4", c=CLOSE)]   # m3 arşivde yok
    card = scorecard.build_scorecard(rows, date(2026, 11, 10), archive_rows=arch)
    c = card["clv"]
    assert c["n"] == 3 and c["n_fair"] == 2 and c["n_raw_only"] == 1 and c["missing"] == {"no_archive": 1}
    assert c["beat_close_rate"] == round(2 / 3, 4)
    assert c["avg_clv_raw"] == pytest.approx((2 * (2.1 / 1.9 - 1) + (3.1 / 3.5 - 1)) / 3, abs=1e-3)
    bm = {m["market"]: m for m in c["by_market"]}
    assert bm["1"]["n"] == 2 and bm["2"]["n"] == 1 and bm["2"]["avg_clv"] < 0 and bm["1"]["label"] == "MS 1"
    rec = {(r["date"], r["odds"], r["clv"] is None) for r in card["recent"]}
    assert len(card["recent"]) == 4 and any(x[2] for x in rec)
    assert [r.get("ev") for r in card["recent"] if "ev" in r] == [0.07]
    json.dumps(card)   # JSON'a yazılabilir


def test_scorecard_clv_empty_and_existing_keys_kept():
    card = scorecard.build_scorecard([], date(2026, 11, 10))
    assert card["clv"]["n"] == 0 and card["clv"]["avg_clv"] is None and card["clv"]["beat_close_rate"] is None
    assert card["clv"]["by_market"] == []
    for k in ("overall", "last30", "by_league", "by_market", "trust", "calibration", "by_category",
              "calibration_markets", "value_bets", "bankroll", "recent"):
        assert k in card
    assert card["overall"]["roi_ci"] is None and card["overall"]["hit_ci"] is None


def test_load_history_annotates_from_archive(tmp_path):
    (tmp_path / "history").mkdir(); (tmp_path / "iddaa_archive").mkdir()
    (tmp_path / "history" / "2026-11-08.json").write_text(json.dumps({"date": "2026-11-08", "rows": [_row("m1")]}))
    a = {**_arch("m1", c=CLOSE), "ko": "2026-11-08T20:00:00+03:00"}
    (tmp_path / "iddaa_archive" / "2026-11.json").write_text(json.dumps({"month": "2026-11", "rows": [a]}))
    rows = scorecard.load_history(tmp_path)
    assert rows[0]["clv"]["status"] == "ok"
    assert scorecard.build_scorecard(rows, date(2026, 11, 10))["clv"]["n"] == 1
    # arşiv hiç yoksa karne yine çalışır
    (tmp_path / "iddaa_archive" / "2026-11.json").unlink()
    assert scorecard.load_history(tmp_path)[0]["clv"] == {"status": "no_archive"}


def test_by_odds_band():
    rows = [_row("a", odds=1.45, won=True, p=0.7), _row("b", odds=1.60, won=False, p=0.6),
            _row("c", odds=1.99, won=True, p=0.5), _row("d", odds=2.0, won=True, p=0.5),
            _row("e", odds=2.75, won=False, p=0.3), _row("f", odds=3.5, won=True, p=0.3),
            _row("g", odds=3.51, won=False, p=0.2)]
    bands = scorecard.build_scorecard(rows, date(2026, 11, 10))["by_odds_band"]
    assert [b["band"] for b in bands] == ["<1.60", "1.60-2.00", "2.00-2.75", "2.75-3.50", ">3.50"]
    assert [b["n"] for b in bands] == [1, 2, 1, 2, 1]
    b = bands[1]
    assert b["hit_rate"] == 0.5 and b["avg_p"] == 0.55 and b["avg_odds"] == 1.795
    assert b["roi"] == round((0.99 - 1) / 2, 4)
    assert bands[3]["roi"] == round((2.5 - 1) / 2, 4) and bands[4]["roi"] == -1.0
    assert all(set(x) >= {"band", "n", "hit_rate", "avg_p", "avg_odds", "roi"} for x in bands)
    empty = scorecard.odds_bands([])
    assert len(empty) == 5 and all(x["n"] == 0 and x["hit_rate"] is None and x["roi"] is None for x in empty)


def test_wilson_interval():
    lo, hi = scorecard.wilson_ci(88, 138)
    assert lo == pytest.approx(0.5548, abs=1e-3) and hi == pytest.approx(0.7131, abs=1e-3)
    assert scorecard.wilson_ci(0, 0) is None
    lo, hi = scorecard.wilson_ci(1, 1)
    assert 0.15 < lo < 0.25 and hi == 1.0      # n=1'de %100 isabet "kesin" değildir
    lo0, hi0 = scorecard.wilson_ci(0, 10)
    assert lo0 == 0.0 and 0.2 < hi0 < 0.35


def test_roi_interval_contains_roi_and_is_deterministic():
    rows = [_row(f"m{i}", odds=1.5, won=i % 3 != 0) for i in range(60)]
    o = scorecard.build_scorecard(rows, date(2026, 11, 10))["overall"]
    lo, hi = o["roi_ci"]
    assert lo < o["roi"] < hi and hi - lo > 0.2          # 60 bahiste aralık geniştir
    assert scorecard.build_scorecard(rows, date(2026, 11, 10))["overall"]["roi_ci"] == [lo, hi]
    big = [(_row(f"m{i}", odds=1.5, won=i % 3 != 0)) for i in range(2400)]
    lo2, hi2 = scorecard._agg(big)["roi_ci"]
    assert hi2 - lo2 < (hi - lo) / 4                       # n büyüdükçe daralır
    assert scorecard.roi_ci([0.5]) is None and scorecard.roi_ci([]) is None
    l30 = scorecard.build_scorecard(rows, date(2026, 11, 10))["last30"]
    assert l30["roi_ci"] == [lo, hi] and l30["hit_ci"][0] < l30["hit_rate"] < l30["hit_ci"][1]


def test_trust_shrinks_by_sample_size():
    def trust(n, hit_n, p=0.5):
        rows = [{"date": "2026-11-01", "pick": "EVEN", "p": p, "won": i < hit_n} for i in range(n)]
        return scorecard.trust_from(rows, date(2026, 11, 6)).get("EVEN")
    assert trust(19, 0) is None                           # min_n korunur
    t20, t100, t400, t4000 = trust(20, 8), trust(100, 40), trust(400, 160), trust(4000, 1600)
    assert 1.0 > t20 > t100 > t400 > t4000 >= 0.7         # aynı −0.10 sapma, n arttıkça etkisi büyür
    assert t20 > 0.95 and t100 > 0.85                     # küçük örnek 1.0'a yakın kalır
    assert t4000 == pytest.approx(1 + 3 * -0.10, abs=0.02)  # büyük n'de eski formüle yaklaşır
    assert trust(100, 60) > 1.0 and trust(100, 50) == 1.0
    assert trust(5000, 0) == 0.6 and trust(5000, 5000) == 1.1   # sınırlar aynı
    assert all(0.6 <= v <= 1.1 for v in (t20, t100, t400, t4000))
