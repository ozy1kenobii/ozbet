"""Faz 1: doğrulama, sağlık geçmişi, yeniden deneme, kalite raporu, Flashscore'un kapalı olması."""
import datetime as dt
import json

import pytest
import requests

from ozbet import config, health, validate
from ozbet.http import Blocked
from ozbet.sources import registry
from ozbet.sources.base import Fixture, StatusBoard

TODAY = dt.date(2026, 11, 6)


def fx(h="A", a="B", day=TODAY, odds=None, result=None):
    return Fixture("TR1", "x", dt.datetime(day.year, day.month, day.day, 20, tzinfo=config.TZ), h, a, "nesine", "t",
                   odds=odds or {}, result=result)


# ---------- doğrulama ----------
def test_clean_odds_drops_out_of_range_and_bad_margin():
    rep = validate.Report()
    good = {"1": 2.1, "X": 3.3, "2": 3.4, "O2.5": 1.8, "U2.5": 1.95}
    assert validate.clean_odds(good, rep) == good
    assert validate.clean_odds({"1": 0.9, "X": 3.3, "2": 3.4}, rep) == {}          # 1 aralık dışı → 1X2 eksik → grup atılır
    arb = validate.clean_odds({"1": 3.0, "X": 4.0, "2": 4.0, "O2.5": 1.8, "U2.5": 1.95}, rep)
    assert "1" not in arb and arb["O2.5"] == 1.8                                    # marj negatif (arbitraj) → 1X2 atılır
    assert rep.as_dict()["marj_tutarsiz_1x2"] == 1 and rep.as_dict()["oran_aralik_disi"] == 1


def test_clean_result_and_fixture_rules():
    rep = validate.Report()
    assert validate.clean_result({"ft": [2, 1], "ht": [3, 0]}, rep) == {"ft": [2, 1], "ht": None}
    assert validate.clean_result({"ft": [40, 1]}, rep) is None
    assert not validate.valid_fixture(fx("Galatasaray", "galatasaray"), TODAY, rep)
    assert not validate.valid_fixture(fx(day=TODAY + dt.timedelta(days=9)), TODAY, rep)
    assert validate.valid_fixture(fx(), TODAY, rep)


def test_clean_history_dedupes_and_fixes_ht():
    rep = validate.Report()
    r = {"date": TODAY, "home": "A", "away": "B", "hg": 1, "ag": 0, "hthg": 2, "htag": 0}
    out = validate.clean_history([r, dict(r), {**r, "away": "A"}, {**r, "hg": "x"}], rep)
    assert len(out) == 1 and out[0]["hthg"] is None
    assert rep.as_dict() == {"gecmis_iy_tutarsiz": 1, "gecmis_satir_bozuk": 1, "gecmis_skor_bozuk": 1, "gecmis_tekrar": 1}


# ---------- yeniden deneme ----------
def test_retry_only_on_transient(monkeypatch):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("koptu")
        return [1, 2]
    b = StatusBoard()
    assert b.run("x", "X", flaky) == [1, 2] and calls["n"] == 2 and b.items["x"].status == "ok"

    calls["n"] = 0

    def blocked():
        calls["n"] += 1
        raise Blocked("403")
    assert b.run("y", "Y", blocked) is None and calls["n"] == 1   # engel yeniden denenmez


# ---------- sağlık ----------
def _src(sid, status, items):
    return {"id": sid, "name": sid.upper(), "status": status, "items": items}


def test_health_levels(tmp_path):
    p = tmp_path / "health.json"
    seq = [("ok", 5), ("ok", 5), ("missing", 0), ("missing", 0)]
    out = None
    for i, (s, n) in enumerate(seq):
        out = health.update(p, f"2026-11-0{i+1}T08:30:00+03:00", "08:30",
                            [_src("a", s, n), _src("never", "missing", 0), _src("good", "ok", 3),
                             _src("off", "skipped", 0)], {})
    a = out["sources"]["a"]
    assert a["level"] == "alarm" and a["streak"] == 2 and a["ok_rate"] == 0.5
    assert a["history"] == ["ok", "ok", "missing", "missing"]
    assert out["sources"]["never"]["level"] == "kronik"
    assert out["sources"]["good"]["level"] == "ok"
    assert out["sources"]["off"]["level"] == "kapali"
    assert len(out["alerts"]) == 1 and "A:" in out["alerts"][0]
    assert len(json.loads(p.read_text())["runs"]) == 4


def test_health_window_trim(tmp_path):
    p = tmp_path / "h.json"
    for i in range(config.HEALTH_WINDOW_RUNS + 5):
        out = health.update(p, f"t{i}", "08:30", [_src("a", "ok", 1)], {})
    assert out["runs"] == config.HEALTH_WINDOW_RUNS and len(out["sources"]["a"]["history"]) == health.SHOW


# ---------- Flashscore kapalı ----------
def test_flashscore_disabled_everywhere():
    roles = (registry.FIXTURE_SOURCES + registry.NEWS_SOURCES + registry.RESULT_SOURCES)
    assert not any("flashscore" in s.id for s in roles)
    assert any(sid == "flashscore" for sid, _, _ in registry.DISABLED)
