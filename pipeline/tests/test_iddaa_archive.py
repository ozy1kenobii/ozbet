from datetime import date, datetime

from ozbet import config
from ozbet.agents import iddaa_archive as ia
from ozbet.sources import registry

TZ = config.TZ


def _m(odds, ko="2026-11-07T20:00:00+03:00"):
    return {"id": "x1", "code": "123", "kickoff": ko, "league": "TR1", "league_name": "Süper Lig",
            "home": {"name": "Galatasaray"}, "away": {"name": "Fenerbahçe"}, "odds": odds}


def test_merge_open_kept_close_frozen_after_ko(tmp_path):
    t1 = datetime(2026, 11, 7, 10, 0, tzinfo=TZ)
    t2 = datetime(2026, 11, 7, 19, 30, tzinfo=TZ)
    t3 = datetime(2026, 11, 7, 22, 30, tzinfo=TZ)
    ia.update(tmp_path, [_m({"1": 2.0, "X": 3.3, "KGV": 1.8})], {}, t1)
    ia.update(tmp_path, [_m({"1": 1.9, "X": 3.4})], {}, t2)
    ia.update(tmp_path, [_m({"1": 1.5, "X": 4.0})], {}, t3)        # maç başladı → kapanış değişmez
    r = ia.load_month(tmp_path, "2026-11")["x1"]
    assert r["o"] == {"1": 2.0, "X": 3.3, "KGV": 1.8} and r["ts_o"].startswith("2026-11-07T10:00")
    assert r["c"] == {"1": 1.9, "X": 3.4} and r["ts_c"].startswith("2026-11-07T19:30")
    assert r["n_snap"] == 2 and r["hk"] and r["ft"] is None
    idx = ia.write_index(tmp_path, t3)
    assert idx["months"]["2026-11"] == {"rows": 1, "resulted": 0}


def test_fill_results(tmp_path):
    t1 = datetime(2026, 11, 7, 10, 0, tzinfo=TZ)
    ia.update(tmp_path, [_m({"1": 2.0})], {}, t1)
    hist = {"TR1": [{"date": date(2026, 11, 7), "home": "Galatasaray", "away": "Fenerbahçe", "hg": 2, "ag": 1,
                     "hthg": 1, "htag": 0}]}
    # başlamadan önce doldurulmaz
    assert ia.fill_results(tmp_path, date(2026, 11, 7), t1, [("fd", registry.results_from_history(hist))],
                           registry.lookup_result) == 0
    later = datetime(2026, 11, 8, 9, 0, tzinfo=TZ)
    n = ia.fill_results(tmp_path, date(2026, 11, 8), later, [("empty", {}), ("fd", registry.results_from_history(hist))],
                        registry.lookup_result)
    r = ia.load_month(tmp_path, "2026-11")["x1"]
    assert n == 1 and r["ft"] == [2, 1] and r["ht"] == [1, 0] and r["rsrc"] == "fd"
    assert ia.write_index(tmp_path, later)["resulted"] == 1


def test_nesine_results_removed():
    assert not any("nesine" in s.id for s in registry.RESULT_SOURCES)
