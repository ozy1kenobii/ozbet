"""Kadro etkisi testleri: büyüklük, tavan, tekilleştirme, eskilik indirimi, sinyal alanı, Transfermarkt kilit kuralı."""
from datetime import date, datetime, timedelta

import pytest

from ozbet import config
from ozbet.agents import simulation, squad
from ozbet.sources import news_rss as N
from ozbet.sources import transfermarkt as T
from ozbet.sources.base import Fixture, MissingPlayer, TeamNews

KO = datetime(2026, 11, 8, 20, 0, tzinfo=config.TZ)
NOW = KO - timedelta(hours=3)


@pytest.fixture(autouse=True)
def _no_rss_leak(monkeypatch):
    monkeypatch.setattr(N, "LAST", None)     # başka testin haber önbelleği sinyale sızmasın


def fx(home, away, lg="TR1", ko=KO):
    return Fixture(lg, "", ko, home, away, "test", "")


def ab(name, key=False, days=None, reason="sakat"):
    return T.Absence(name, reason, key=key, since=(KO.date() - timedelta(days=days)) if days is not None else None)


def side(*players, **kw):
    rows = [{"name": p.name, "reason": p.reason, "key": p.key,
             **({"days_out": (KO.date() - p.since).days} if p.since else {})} for p in players]
    return {"missing": rows, "rotation_risk": False, "coach_change": False, **kw}


def rss_item(title, source, hours_before_now, tags):
    return {"title": title, "url": f"https://example.com/{abs(hash((title, source)))}", "source": source,
            "published": (NOW - timedelta(hours=hours_before_now)).isoformat(timespec="seconds"), "tags": tags}


# ---------- büyüklük ve tavan ----------
def test_single_key_absence_is_a_few_percent():
    own, opp = squad.impact(side(ab("Yıldız", key=True, days=2)))
    assert own == pytest.approx(-0.03) and opp == pytest.approx(0.015)
    own2, opp2 = squad.impact(side(ab("Yedek", days=2)))
    assert -0.01 < own2 < 0 < opp2 < 0.005


def test_hard_cap_on_total_adjustment():
    many = [ab(f"Kilit {c}", key=True, days=1) for c in "ABCDEF"] + [ab(f"Diğer {c}", days=1) for c in "GHIJKL"]
    own, opp = squad.impact(side(*many, rotation_risk=True))
    assert own == -squad.CAP_OWN and opp == squad.CAP_OPP
    o, x, notes = squad.multipliers(side(*many, rotation_risk=True))
    assert o == pytest.approx(0.94) and x == pytest.approx(1.03) and notes == ["rotasyon riski"]
    # elle yazılmış/bozuk bir adjustment da tavanı aşamaz
    o, x, _ = squad.multipliers({"missing": [], "adjustment": -0.5, "opp_adjustment": 0.4})
    assert o == pytest.approx(1 - squad.CAP_OWN) and x == pytest.approx(1 + squad.CAP_OPP)


def test_sign_and_empty():
    assert squad.impact(None) == (0.0, 0.0)
    assert squad.multipliers(None) == (1.0, 1.0, [])
    o, x, notes = squad.multipliers({"missing": [], "rotation_risk": False, "coach_change": True})
    assert (o, x) == (1.0, 1.0) and notes == ["teknik direktör değişikliği"]     # TD değişikliği λ'yı değiştirmez


# ---------- eskilik indirimi ----------
def test_staleness_discount():
    fresh, _ = squad.impact(side(ab("A", key=True, days=3)))
    mid, _ = squad.impact(side(ab("A", key=True, days=14)))
    stale, _ = squad.impact(side(ab("A", key=True, days=60)))
    unknown, _ = squad.impact(side(ab("A", key=True)))
    assert fresh < mid < unknown < stale < 0
    assert stale == pytest.approx(-squad.W_KEY * squad.F_STALE)      # 3 haftadan eski: dörtte bir
    assert unknown == pytest.approx(-squad.W_KEY * squad.F_UNKNOWN)
    doubt, _ = squad.impact(side(ab("A", key=True, days=3, reason="şüpheli")))
    assert doubt == pytest.approx(fresh * squad.DOUBT_FACTOR)


# ---------- tekilleştirme ----------
@pytest.mark.parametrize("a,b,same", [
    ("Victor Osimhen", "V. Osimhen", True), ("Osimhen", "Victor Osimhen", True),
    ("Orkun Kökçü", "Orkun Kokcu", True), ("Emre Mor", "Emre Akbaba", False),
    ("Arda Güler", "Ahmet Güler", False), ("A. Güler", "Arda Güler", True),
])
def test_same_player(a, b, same):
    assert squad.same_player(a, b) is same


def test_same_player_from_two_sources_counted_once():
    a = {"gs": TeamNews("Galatasaray", "flashscore", "t", [MissingPlayer("V. Osimhen", "şüpheli")])}
    b = {"gs": TeamNews("Galatasaray", "transfermarkt", "t", [ab("Victor Osimhen", key=True, days=2), ab("Icardi", days=40)])}
    merged = squad.merge_team_news(a, b)
    news = {N.team_key("Galatasaray"): merged["gs"]}
    out = squad.build("Galatasaray", "Fenerbahçe", KO, "TR1", news, [fx("Galatasaray", "Fenerbahçe")], now=NOW)
    names = [p["name"] for p in out["home"]["missing"]]
    assert names == ["Victor Osimhen", "Icardi"]
    osi = out["home"]["missing"][0]
    assert osi["key"] is True and osi["reason"] == "sakat" and osi["days_out"] == 2
    assert out["home"]["adjustment"] == pytest.approx(-(0.03 + 0.0075 * 0.25), abs=1e-4)
    assert out["source"] == "flashscore"


# ---------- simülasyon bağlantısı ----------
def test_simulation_uses_squad_multipliers():
    s = side(*[ab(f"K{c}", key=True, days=1) for c in "ABC"])
    own, opp, _ = simulation._squad_mult(s)
    assert own == pytest.approx(0.94) and opp == pytest.approx(1.03)       # eski kural 0,83 / 1,06 veriyordu
    out = squad.build("Galatasaray", "Fenerbahçe", KO, "TR1",
                      {N.team_key("Galatasaray"): TeamNews("Galatasaray", "x", "t", [ab("Tek", key=True, days=1)])},
                      [fx("Galatasaray", "Fenerbahçe")], now=NOW)
    own, opp, _ = simulation._squad_mult(out["home"])
    assert own == pytest.approx(1 + out["home"]["adjustment"]) and opp == pytest.approx(1 + out["home"]["opp_adjustment"])
    assert out["home"]["adjustment"] == pytest.approx(-0.03) and isinstance(out["home"]["adjustment"], float)


def test_existing_keys_kept():
    news = {N.team_key("Galatasaray"): TeamNews("Galatasaray", "flashscore", "t", [MissingPlayer("X", "cezalı", True)])}
    out = squad.build("Galatasaray", "Fenerbahçe", KO, "TR1", news, [fx("Galatasaray", "Fenerbahçe")], now=NOW)
    assert set(out) == {"home", "away", "source", "fetched_at", "signal"} and out["away"] is None
    assert {"missing", "rotation_risk", "coach_change", "adjustment"} <= set(out["home"])
    assert {"name", "reason", "key"} <= set(out["home"]["missing"][0])
    assert squad.build("A", "B", KO, "TR1", {}, []) is None


# ---------- sinyal ----------
def _rss(home_items=(), away_items=(), home="Çorum FK", away="Fenerbahçe"):
    return {"teams": {N.team_key(home): {"items": list(home_items), "coach_change": False},
                      N.team_key(away): {"items": list(away_items), "coach_change": False}},
            "fetched_at": "2026-11-08T17:00:00+03:00"}


def test_signal_strong_fresh_two_independent_sources():
    rss = _rss([rss_item("Çorum FK'da sakatlık depremi! 6-8 hafta yok", "NTV Spor", 2, ["sakat"]),
                rss_item("Arca Çorum FK'dan sakatlık açıklaması geldi", "Fotomaç", 3, ["sakat"])])
    out = squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", {}, [], rss=rss, now=NOW)
    sig = out["signal"]
    assert sig["strength"] == "güçlü" and sig["fresh"] is True and sig["side"] == "home"
    assert sig["text"].startswith("Çorum FK:") and "2 bağımsız kaynak" in sig["text"]
    assert out["home"] is None and out["away"] is None and out["source"] == "haber_rss"   # başlık λ'yı değiştirmez
    assert set(sig) == {"strength", "fresh", "side", "text"}


def test_signal_same_group_copies_are_not_confirmation():
    a = "Beşiktaş'ta sarı kart gören Orkun Kökçü cezalı duruma düştü!"
    rss = _rss([rss_item(a, "A Spor", 2, ["ceza"]),
                rss_item("Beşiktaş'ta Orkun Kökçü cezalı duruma düştü!", "Fotomaç", 2, ["ceza"])],
               home="Beşiktaş", away="Göztepe")
    sig = squad.build("Beşiktaş", "Göztepe", KO, "TR1", {}, [], rss=rss, now=NOW)["signal"]
    assert sig["strength"] == "orta" and sig["fresh"] is True and "1 bağımsız kaynak" in sig["text"]


def test_signal_old_news_weak_and_untagged_none():
    rss = _rss([rss_item("Çorum FK'da sakatlık şoku", "AA", 50, ["sakat"])])
    sig = squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", {}, [], rss=rss, now=NOW)["signal"]
    assert sig["strength"] == "zayıf" and sig["fresh"] is False and sig["side"] == "home"
    rss = _rss([rss_item("Çorum FK - Fenerbahçe maçı hangi kanalda?", "A Spor", 2, []),
                rss_item("Transferde sıcak gelişme", "A Spor", 2, ["transfer"])])
    assert squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", {}, [], rss=rss, now=NOW) is None


def test_signal_ignores_news_published_after_kickoff():
    late = {"title": "Fenerbahçe'de kırmızı kart şoku", "url": "https://example.com/l", "source": "AA",
            "published": (KO + timedelta(hours=1)).isoformat(), "tags": ["ceza"]}
    assert squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", {}, [], rss=_rss(away_items=[late]),
                       now=KO + timedelta(hours=3)) is None


def test_signal_from_absence_list_and_sides():
    news = {N.team_key("Fenerbahçe"): TeamNews("Fenerbahçe", "transfermarkt", "t", [ab("Yeni Kilit", key=True, days=0)]),
            N.team_key("Çorum FK"): TeamNews("Çorum FK", "transfermarkt", "t", [ab("Eski", key=True, days=90)])}
    out = squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", news, [], now=NOW)
    sig = out["signal"]
    assert sig["strength"] == "güçlü" and sig["fresh"] is True and sig["side"] == "away" and "Yeni Kilit" in sig["text"]
    # yalnız uzun süreli eksik: zayıf, taze değil
    only_old = squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", {N.team_key("Çorum FK"): news[N.team_key("Çorum FK")]},
                           [], now=NOW)["signal"]
    assert only_old["strength"] == "zayıf" and only_old["fresh"] is False and only_old["side"] == "home"
    # iki taraf eşit güçte → side None
    both = {N.team_key("Fenerbahçe"): TeamNews("Fenerbahçe", "haber_rss", "t", coach_change=True),
            N.team_key("Çorum FK"): TeamNews("Çorum FK", "haber_rss", "t", coach_change=True)}
    s2 = squad.build("Çorum FK", "Fenerbahçe", KO, "TR1", both, [], now=NOW)["signal"]
    assert s2["strength"] == "orta" and s2["side"] is None and "Çorum FK" in s2["text"] and "Fenerbahçe" in s2["text"]


def test_signal_rotation_only_is_weak():
    fixtures = [fx("Galatasaray", "Göztepe"), fx("Galatasaray", "Ajax", "UCL", KO + timedelta(days=2))]
    out = squad.build("Galatasaray", "Göztepe", KO, "TR1", {}, fixtures, now=NOW)
    assert out["home"]["rotation_risk"] and out["home"]["adjustment"] == pytest.approx(-0.015)
    assert out["signal"]["strength"] == "zayıf" and "rotasyon riski" in out["signal"]["text"]


# ---------- Transfermarkt: tarih ve kilit kuralı ----------
def test_transfermarkt_dates_and_key_rule():
    day = date(2026, 11, 13)
    assert T.split_dates(T.parse_dates("05.11.2026 12 Ara 2026 1/3/2001"), day) == (date(2026, 11, 5), date(2026, 12, 12))
    assert T.split_dates([], day) == (None, None)
    vals = [0.5e6] * 6 + [2e6] * 3 + [20e6, 30e6, 40e6]
    thr = T.key_threshold(vals)
    assert thr == 20e6
    assert T.key_threshold([3e6, 4e6]) == 5e6                      # az veri: temkinli sabit eşik
    rows = [{"name": "Kaleci", "reason": "sakat", "value": 40e6, "position": "Kaleci", "dates": []},
            {"name": "Forvet", "reason": "sakat", "value": 30e6, "position": "Santrafor", "dates": [date(2026, 11, 10)]},
            {"name": "Forvet", "reason": "sakat", "value": 30e6, "position": "Santrafor", "dates": []},
            {"name": "Kanat", "reason": "sakat", "value": 25e6, "position": "Sol Kanat", "dates": [date(2026, 8, 1)]},
            {"name": "Stoper", "reason": "sakat", "value": 22e6, "position": "Stoper", "dates": []},
            {"name": "Genç", "reason": "sakat", "value": 2e6, "position": "Orta saha", "dates": []}]
    abs_ = T.build_absences(rows, thr, day)
    assert [a.name for a in abs_] == ["Kaleci", "Forvet", "Kanat", "Stoper", "Genç"]     # aynı oyuncu tek kez
    assert [a.key for a in abs_] == [False, True, True, False, False]                     # kaleci değil, en çok 2
    assert abs_[1].since == date(2026, 11, 10) and abs_[2].since == date(2026, 8, 1)
    html = """<table class="items"><tbody><tr>
      <td><table class="inline-table"><tr><td class="hauptlink"><a>Ali Veli</a></td></tr><tr><td>Santrafor</td></tr></table></td>
      <td class="zentriert"><img class="tiny_wappen" alt="Galatasaray"/></td><td class="zentriert">27</td>
      <td class="zentriert">05.11.2026</td><td class="zentriert">12.12.2026</td><td class="rechts">12,50 mil. €</td>
    </tr></tbody></table>"""
    assert T.parse_injuries(html) == {"Galatasaray": [("Ali Veli", "sakat", 12.5e6)]}
    r = T.parse_rows(html)["Galatasaray"][0]
    assert r["position"] == "Santrafor" and r["dates"] == [date(2026, 11, 5), date(2026, 12, 12)]
