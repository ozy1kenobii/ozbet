"""Veri genişletme: ClubElo, Elo tabanlı lig-arası λ, birikimli sonuç arşivi, soccerstats 1. Lig geçmişi, lig takma adları.
Ağ yok: örnek yanıtlar (fixture) üzerinden ayrıştırma ve akış testleri."""
import datetime as dt
import json

import numpy as np
import pytest

from ozbet import config
from ozbet.agents import simulation
from ozbet.agents.bulletin import league_for
from ozbet.markets import probs_from_matrix
from ozbet.model.dixon_coles import score_matrix
from ozbet.sources import archive, clubelo, flashscore, registry, soccerstats
from ozbet.sources.base import Fixture, StatusBoard

from .test_e2e import TR_TEAMS, synth_history

TODAY = dt.date(2026, 11, 5)

# ---------------- ClubElo ----------------
# api.clubelo.com/{tarih} biçimi (soccerdata/penaltyblog belgelerindeki örneklerle aynı başlık)
CLUBELO_CSV = """﻿Rank,Club,Country,Level,Elo,From,To
1,Bayern,GER,1,2087.53,2026-11-02,2026-11-05
2,Real Madrid,ESP,1,2078.10,2026-11-02,2026-11-05
5,Man City,ENG,1,1990.2,2026-11-02,2026-11-05
14,Milan,ITA,1,1850.4,2026-11-02,2026-11-05
40,Galatasaray,TUR,1,1795.6,2026-11-03,2026-11-06
55,Fenerbahce,TUR,1,1760.0,2026-11-03,2026-11-06
58,Besiktas,TUR,1,1740.0,2026-11-03,2026-11-06
None,Bueyueksehir,TUR,1,1560.9,2026-11-03,2026-11-07
None,Ankaraguecue,TUR,2,1380.0,2026-11-03,2026-11-07
60,Leverkusen,GER,1,1880.0,2026-11-02,2026-11-05
61,Marseille,FRA,1,1790.0,2026-11-02,2026-11-05
70,St Gillis,BEL,1,1720.0,2026-11-02,2026-11-05
71,Celta,ESP,1,1700.0,2026-11-02,2026-11-05
80,Ferencvaros,HUN,1,1600.0,2026-11-02,2026-11-05
81,Koebenhavn,DEN,1,1680.0,2026-11-02,2026-11-05
82,Crvena Zvezda,SRB,1,1690.0,2026-11-02,2026-11-05
None,Galatasaray,TUR,0,1000.0,1900-01-01,1900-01-02
"""


def test_clubelo_parse_and_lookup():
    rows = clubelo.parse_csv(CLUBELO_CSV)
    assert rows[0] == {"club": "Bayern", "country": "GER", "level": 1, "elo": 2087.53}
    t = clubelo.EloTable(rows, "2026-11-05")
    assert t.lookup("AC Milan")["club"] == "Milan"
    assert t.lookup("Başakşehir")["club"] == "Bueyueksehir"
    assert t.lookup("RAMS Başakşehir", "TR1")["club"] == "Bueyueksehir"
    assert t.lookup("U. S. Gilloise")["club"] == "St Gillis"
    assert t.lookup("Kızıl Yıldız")["club"] == "Crvena Zvezda"
    assert t.lookup("Kopenhag")["club"] == "Koebenhavn"
    assert t.lookup("Fenerbahçe SK")["club"] == "Fenerbahce"
    assert t.lookup("Manchester City")["club"] == "Man City"
    assert t.lookup("Ankaragücü")["club"] == "Ankaraguecue"
    # ülke kısıtı: TR1 maçında Alman takımı aranmaz
    assert t.lookup("Leverkusen", "TR1") is None
    # altyapı/kadın takımları A takımın Elo'sunu almaz
    assert t.lookup("Galatasaray U19") is None and t.lookup("Fenerbahçe Kadın") is None
    p = t.pair("AC Milan", "Ferencvaros")
    assert p["home"] == 1850 and p["away"] == 1600 and p["source"] == "clubelo" and p["date"] == "2026-11-05"


def test_clubelo_empty_raises():
    class C:
        def get(self, url, **kw):
            assert url == "http://api.clubelo.com/2026-11-05" and kw["ttl"] == 24 * 3600
            return "Rank,Club,Country,Level,Elo,From,To\n"
    with pytest.raises(RuntimeError):
        clubelo.ratings(C(), TODAY)
    b = StatusBoard()
    assert b.run("clubelo", "ClubElo", lambda: clubelo.ratings(C(), TODAY)) is None
    assert b.items["clubelo"].status == "missing"


# ---------------- Elo → λ ----------------
def test_elo_expectation():
    assert simulation.elo_expectation(1500, 1500, neutral=True) == pytest.approx(0.5)
    assert simulation.elo_expectation(1500, 1500) == pytest.approx(1 / (1 + 10 ** (-config.ELO_HFA / 400)))
    assert simulation.elo_expectation(1900, 1500, neutral=True) == pytest.approx(10 / 11)


@pytest.mark.parametrize("total,we", [(2.6, 0.5), (2.6, 0.75), (3.1, 0.3), (2.2, 0.9)])
def test_lambdas_from_elo_solves_constraints(total, we):
    lh, la = simulation.lambdas_from_elo(total, we, rho=-0.05)
    assert lh + la == pytest.approx(total, rel=1e-6)
    p = probs_from_matrix(score_matrix(lh, la, -0.05))
    assert p["1"] + 0.5 * p["X"] == pytest.approx(we, abs=1e-3)


def _models():
    tr = synth_history(TR_TEAMS, 1)
    eng = synth_history(["Arsenal", "Chelsea", "Liverpool", "Man City", "Everton", "Fulham", "Brentford",
                         "Wolves", "Burnley", "Leeds"], 2)
    return {"TR1": simulation.build("TR1", tr, TODAY), "ENG1": simulation.build("ENG1", eng, TODAY)}


def test_predict_cup_uses_elo_and_falls_back():
    models = _models()
    elo = {"home": 1795, "away": 1990, "source": "clubelo", "date": "2026-11-05"}
    s = simulation.predict("Galatasaray", "Manchester City", "UCL", models, None, "k", elo=elo)
    assert s["method"] == "elo" and s["data_quality"] == "medium"
    assert any("Elo tabanlı" in n for n in s["notes"])
    we = simulation.elo_expectation(1795, 1990)
    assert s["probs"]["1"] + 0.5 * s["probs"]["X"] == pytest.approx(we, abs=0.02)
    # toplam gol iki takımın kendi lig modellerinden
    tot = np.mean([simulation.team_total(models["TR1"].goals, "Galatasaray"),
                   simulation.team_total(models["ENG1"].goals, "Man City")])
    assert s["lambda_home"] + s["lambda_away"] == pytest.approx(tot, rel=0.01)
    # Elo yok → eski lig gücü yolu
    s2 = simulation.predict("Galatasaray", "Manchester City", "UCL", models, None, "k")
    assert s2["method"] == "league_strength" and any("lig gücü" in n for n in s2["notes"])
    # Elo var ama takımlardan biri hiçbir lig modelinde yok → yine Elo ile (toplam gol diğer ligden)
    s3 = simulation.predict("Galatasaray", "Ferencvaros", "UEL", models, None, "k",
                            elo={"home": 1795, "away": 1600})
    assert s3 and s3["method"] == "elo"
    # Aynı lig modelindeki iki takım kupada karşılaşırsa lig modeli yolu (Elo gereksiz)
    s4 = simulation.predict("Galatasaray", "Fenerbahce", "UCL", models, None, "k", elo={"home": 1795, "away": 1760})
    assert s4["method"] == "league_strength"
    # Lig maçında (model var) Elo yok sayılır
    s5 = simulation.predict("Galatasaray", "Fenerbahce", "TR1", models, None, "k", elo={"home": 1795, "away": 1760})
    assert s5["method"] == "league"


def test_predict_league_without_model_is_not_invented_from_elo():
    """Geçmişi olmayan lig maçı (ör. 1. Lig) Elo'yla uydurulmaz."""
    assert simulation.predict("Boluspor", "Manisa FK", "TR2", _models(), None, "k",
                              elo={"home": 1400, "away": 1390}) is None


# ---------------- Lig takma adları ----------------
@pytest.mark.parametrize("raw,exp", [
    ("Hollanda Eredivisie", "NED1"), ("Portekiz Liga Portugal", "POR1"), ("Portekiz Süper Lig", "POR1"),
    ("Portekiz 1. Lig", "POR1"), ("Belçika Pro Lig", "BEL1"), ("Belçika 1. Lig", "BEL1"),
    ("BELÇİKA: Jupiler Pro League", "BEL1"), ("İskoçya Premiership", "SCO1"), ("İskoçya Premier Lig", "SCO1"),
    ("Yunanistan Süper Lig", "GRE1"), ("Yunanistan Süper Ligi", "GRE1"), ("İngiltere Championship", "ENG2"),
    ("İspanya 2. Lig", "ESP2"), ("Fransa 2. Lig", "FRA2"), ("Türkiye 1. Lig", "TR2"), ("TÜRKİYE: 1. Lig", "TR2"),
    ("Italya Serie B", "ITA2"),
    # ayrımlar korunur
    ("Portekiz 2. Lig", None), ("Türkiye 2. Lig", None), ("Türkiye 1. Lig Kadınlar", None),
    ("Hollanda Eredivisie Kadınlar", None), ("Belçika Pro League U21", None), ("Romanya 2. Lig", None),
    ("Katar 2. Lig", None), ("İtalya Serie C", None), ("Belçika Birinci Lig B", None),
    ("İskoçya Championship", "SCO2"), ("Fransa Ulusal Lig", None), ("Hollanda 1. Lig", None),
    ("UEFA Avrupa Ligi Günlük Bahisler", None),
])
def test_league_aliases(raw, exp):
    assert league_for(raw.replace(":", " ")) == exp


# ---------------- Birikimli sonuç arşivi ----------------
def _fs_feed(day, rows):
    ts = lambda h: int(dt.datetime(day.year, day.month, day.day, h, 0, tzinfo=dt.timezone.utc).timestamp())
    parts = ["SA÷1¬~ZA÷TÜRKİYE: 1. Lig¬ZEE÷x¬"]
    for i, (h, a, hg, ag, hth, hta) in enumerate(rows):
        parts.append(f"~AA÷id{day:%m%d}{i}¬AD÷{ts(15)}¬AB÷3¬AE÷{h}¬AF÷{a}¬AG÷{hg}¬AH÷{ag}¬BA÷{hth}¬BB÷{hta}¬")
    parts.append("~ZA÷TÜRKİYE: Süper Lig Kadınlar¬ZEE÷y¬")
    parts.append(f"~AA÷kad{day:%m%d}¬AD÷{ts(12)}¬AB÷3¬AE÷Galatasaray¬AF÷Fenerbahçe¬AG÷1¬AH÷0¬")
    parts.append("~ZA÷AVRUPA: Avrupa Ligi - Lig Aşaması¬ZEE÷z¬")
    parts.append(f"~AA÷uel{day:%m%d}¬AD÷{ts(18)}¬AB÷3¬AE÷Celtic¬AF÷Beşiktaş¬AG÷1¬AH÷1¬")
    parts.append("~ZA÷TÜRKİYE: Süper Lig¬ZEE÷w¬")
    parts.append(f"~AA÷live{day:%m%d}¬AD÷{ts(19)}¬AB÷2¬AE÷Samsunspor¬AF÷Konyaspor¬AG÷0¬AH÷0¬")
    return "".join(parts)


def test_archive_accumulates_without_duplicates(tmp_path):
    y = TODAY - dt.timedelta(days=1)
    feeds = {y: _fs_feed(y, [("Boluspor", "Manisa FK", 1, 2, 1, 2), ("Sarıyer", "Bodrum FK", 1, 4, 0, 3)]),
             y - dt.timedelta(days=1): _fs_feed(y - dt.timedelta(days=1), [("Iğdır FK", "Pendikspor", 2, 0, 1, 0)])}
    calls = []

    def feed(d):
        calls.append(d)
        if d not in feeds:
            raise ConnectionError("yok")
        return [f for f in flashscore.parse_feed(feeds[d], "t") if f.result and f.kickoff.date() == d]

    added = archive.update(tmp_path, TODAY, feed)
    assert added == {"TR2": 3}
    doc = json.loads((tmp_path / "archive" / "results-TR2.json").read_text())
    r = next(x for x in doc["rows"] if x["home"] == "Boluspor")
    assert r["date"] == y.isoformat() and r["ft"] == [1, 2] and r["ht"] == [1, 2] and r["src"] == "flashscore"
    # kadın ligi ve kupa maçı arşive girmez, canlı maç girmez
    assert not (tmp_path / "archive" / "results-UEL.json").exists()
    assert {p.name for p in (tmp_path / "archive").iterdir()} == {"results-TR2.json"}
    # ikinci çalıştırma: tekrar yok, işlenmiş eski günler yeniden indirilmez (dün hep yeniden okunur)
    calls.clear()
    assert archive.update(tmp_path, TODAY, feed) == {}
    assert len(json.loads((tmp_path / "archive" / "results-TR2.json").read_text())["rows"]) == 3
    assert calls[0] == y and (y - dt.timedelta(days=1)) not in calls


def test_archive_history_threshold(tmp_path, monkeypatch):
    rows = synth_history(TR_TEAMS[:10], 3)[:59]
    doc = {"league": "TR2", "days": [], "rows": [
        {"date": r["date"].isoformat(), "home": r["home"], "away": r["away"], "ft": [r["hg"], r["ag"]],
         "ht": [r["hthg"], r["htag"]], "src": "flashscore"} for r in rows]}
    archive.save(tmp_path, "TR2", doc)
    monkeypatch.setattr(registry, "SOCCERSTATS_HISTORY", {})
    monkeypatch.setattr(config, "API_FOOTBALL_KEY", None)
    b = StatusBoard()
    assert registry.extra_history(None, b, TODAY, tmp_path) == {}
    assert "59/60" in (b.items["archive_history"].note or "")
    doc["rows"].append({"date": "2026-11-01", "home": "Boluspor", "away": "Manisa FK", "ft": [1, 0], "ht": None})
    archive.save(tmp_path, "TR2", doc)
    got = registry.extra_history(None, StatusBoard(), TODAY, tmp_path)
    assert len(got["TR2"]) == 60
    r = got["TR2"][-1]
    assert r["date"] == dt.date(2026, 11, 1) and r["hg"] == 1 and r["hthg"] is None and r["season"] == "2627"
    assert simulation.build("TR2", got["TR2"], TODAY) is not None


# ---------------- soccerstats 1. Lig sonuçları ----------------
SS_CURRENT = """<html><body><table><tr><td>
<table>
<tr><td colspan=5>August</td></tr>
<tr><td><a href="#">Fri 7 Aug</a></td><td><a href="#">Boluspor vs Manisa FK</a></td><td></td>
    <td><a href="#">1:2</a></td><td><a href="#">(1:2)</a></td></tr>
<tr><td><a href="#">Sat 8 Aug</a></td><td><a href="#">Bandırmaspor vs Istanbulspor</a></td><td></td>
    <td><a href="#">3:0</a></td><td><a href="#">(2:0)</a></td></tr>
<tr><td colspan=5>October</td></tr>
<tr><td>Wed 14 Oct</td><td>Umraniyespor vs Boluspor</td><td></td><td>pp.</td><td><a href="pmatch.asp">x</a></td></tr>
<tr><td>Wed 14 Oct</td><td>Antalyaspor vs Kayserispor</td><td></td><td>0:4</td><td>(0:3)</td></tr>
<tr><td>Sat 7 Nov</td><td>Sivasspor vs Bodrum FK</td><td></td><td>19:00</td><td></td></tr>
<tr><td>Sat 3 Jan</td><td>Igdır FK vs Sarıyer SK</td><td></td><td>2:2</td><td>(1:1)</td></tr>
</table></td></tr></table></body></html>"""

SS_OLD = """<table>
<tr><td>Fri 9 Aug</td><td>Sakaryaspor</td><td><b>1:1</b></td><td>Keciorengucu</td><td>-</td><td>2</td><td>+</td></tr>
<tr><td>Sat 10 Aug</td><td>Istanbulspor</td><td><b>3:2</b></td><td>Manisa BB</td><td>+</td><td>5</td><td>+</td></tr>
<tr><td>Mon 10 Mar</td><td>Y. Malatyaspor</td><td><b>0:3</b></td><td>Pendikspor</td><td>+</td><td>3</td><td>-</td></tr>
</table>"""


def test_soccerstats_results_current_layout():
    rows = soccerstats.parse_results(SS_CURRENT, 2026)
    got = {(r["date"].isoformat(), r["home"], r["away"]): (r["hg"], r["ag"], r["hthg"], r["htag"]) for r in rows}
    assert got == {("2026-08-07", "Boluspor", "Manisa FK"): (1, 2, 1, 2),
                   ("2026-08-08", "Bandırmaspor", "Istanbulspor"): (3, 0, 2, 0),
                   ("2026-10-14", "Antalyaspor", "Kayserispor"): (0, 4, 0, 3),
                   ("2027-01-03", "Igdır FK", "Sarıyer SK"): (2, 2, 1, 1)}
    assert all(r["season"] == "2627" and r["src"] == "soccerstats" for r in rows)


def test_soccerstats_results_old_layout_and_urls():
    rows = soccerstats.parse_results(SS_OLD, 2024)
    assert [(r["date"].isoformat(), r["home"], r["away"], r["hg"], r["ag"], r["hthg"]) for r in rows] == [
        ("2024-08-09", "Sakaryaspor", "Keciorengucu", 1, 1, None),
        ("2024-08-10", "Istanbulspor", "Manisa BB", 3, 2, None),
        ("2025-03-10", "Y. Malatyaspor", "Pendikspor", 0, 3, None)]
    asked = []

    class C:
        def get(self, url, params=None, ttl=0, **kw):
            asked.append((params["league"], ttl))
            if params["league"] == "turkey2_2025":
                raise ConnectionError("x")
            return SS_CURRENT if params["league"] == "turkey2" else SS_OLD
    out = soccerstats.results_history(C(), "turkey2", TODAY)
    assert [a[0] for a in asked] == ["turkey2", "turkey2_2026", "turkey2_2025"]
    assert all(r["date"] < TODAY for r in out) and len(out) == 3 + 3  # 2027 tarihli satır gelecekte → atlanır


# ---------------- uçtan uca: Elo alanı, kupa bayrağı, arşiv dosyası ----------------
def test_run_with_elo_and_archive(tmp_path, monkeypatch):
    from ozbet import run
    from ozbet.sources import football_data, nesine
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    tr = synth_history(TR_TEAMS, 1)
    eng = synth_history(["Arsenal", "Chelsea", "Liverpool", "Man City", "Everton", "Fulham", "Brentford",
                         "Wolves", "Burnley", "Leeds"], 2)
    monkeypatch.setattr(football_data, "history",
                        lambda c, code, s: tr if code == "T1" else (eng if code == "E0" else []))
    monkeypatch.setattr(football_data, "fixtures", lambda c, d: [])
    doc = {"sg": {"LA": [{"LID": 1, "N": "UEFA Şampiyonlar Ligi"}, {"LID": 7, "N": "Türkiye Süper Lig"}], "EA": [
        {"C": "500", "HN": "Galatasaray", "AN": "Manchester City", "LC": 1, "D": "05.11.2026", "T": "22:00",
         "MA": [{"MTID": 1, "MBS": 1, "OCA": [{"N": 1, "O": 4.2}, {"N": 2, "O": 3.9}, {"N": 3, "O": 1.8}]}]},
        {"C": "501", "HN": "Fenerbahçe", "AN": "Beşiktaş", "LC": 7, "D": "05.11.2026", "T": "19:00",
         "MA": [{"MTID": 1, "MBS": 1, "OCA": [{"N": 1, "O": 2.0}, {"N": 2, "O": 3.4}, {"N": 3, "O": 3.6}]}]}]}}
    monkeypatch.setattr(registry, "FIXTURE_SOURCES",
                        [registry.Src("nesine", "Nesine", fixtures=lambda c, d: nesine.parse(doc, d, "t"))])
    for k in ("XG_SOURCES", "NEWS_SOURCES", "PREDICTION_SOURCES"):
        monkeypatch.setattr(registry, k, [])
    monkeypatch.setattr(registry, "SOCCERSTATS_HISTORY", {})
    monkeypatch.setattr(config, "API_FOOTBALL_KEY", None)
    y = TODAY - dt.timedelta(days=1)
    fs = lambda c, d: ([f for f in flashscore.parse_feed(_fs_feed(d, [("Boluspor", "Manisa FK", 1, 2, 1, 2)]), "t")
                        if f.result and f.kickoff.date() == d] if d == y else [])
    monkeypatch.setattr(registry, "RESULT_SOURCES",
                        [registry.Src("flashscore_results", "Flashscore", results=lambda c, d: {}, archive_feed=fs)])
    table = clubelo.EloTable(clubelo.parse_csv(CLUBELO_CSV), "2026-11-05")
    monkeypatch.setattr(registry, "ELO_SOURCES", [registry.Src("clubelo", "ClubElo", elo=lambda c, d: table)])

    out = run.main(["--date", "2026-11-05", "--no-llm"])
    ms = {m["code"]: m for m in out["matches"]}
    cup = ms["500"]
    assert cup["elo"] == {"home": 1796, "away": 1990, "source": "clubelo", "date": "2026-11-05"}
    assert cup["model"]["method"] == "elo" and cup["model"]["data_quality"] == "medium"
    assert run.CUP_FLAG_ELO in cup["flags"] and cup["value"] == []
    assert cup["value_note"] == "Kupa maçı – değer etiketi verilmez" and cup["pick"]["stars"] <= 2
    lg = ms["501"]
    assert lg["elo"]["home"] == 1760 and lg["model"]["method"] == "league"
    assert not any(f.startswith("Kupa") for f in lg["flags"])
    st = {s["id"]: s for s in out["sources"]}
    assert st["clubelo"]["status"] == "ok" and st["flashscore_results_archive"]["status"] == "ok"
    arch = json.loads((tmp_path / "archive" / "results-TR2.json").read_text())
    assert arch["rows"][0]["home"] == "Boluspor" and arch["rows"][0]["ft"] == [1, 2]


def test_run_elo_source_down_falls_back(tmp_path, monkeypatch):
    """ClubElo çökerse akış durmaz, kupa maçı eski lig gücü yolu + eski bayrakla devam eder."""
    from ozbet import run
    from ozbet.sources import football_data, nesine
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    tr = synth_history(TR_TEAMS, 1)
    monkeypatch.setattr(football_data, "history", lambda c, code, s: tr if code == "T1" else [])
    monkeypatch.setattr(football_data, "fixtures", lambda c, d: [])
    doc = {"sg": {"LA": [{"LID": 1, "N": "UEFA Şampiyonlar Ligi"}], "EA": [
        {"C": "600", "HN": "Galatasaray", "AN": "Trabzonspor", "LC": 1, "D": "05.11.2026", "T": "22:00",
         "MA": [{"MTID": 1, "MBS": 1, "OCA": [{"N": 1, "O": 2.0}, {"N": 2, "O": 3.4}, {"N": 3, "O": 3.6}]}]}]}}
    monkeypatch.setattr(registry, "FIXTURE_SOURCES",
                        [registry.Src("nesine", "Nesine", fixtures=lambda c, d: nesine.parse(doc, d, "t"))])
    for k in ("XG_SOURCES", "NEWS_SOURCES", "PREDICTION_SOURCES", "RESULT_SOURCES"):
        monkeypatch.setattr(registry, k, [])
    monkeypatch.setattr(registry, "SOCCERSTATS_HISTORY", {})
    monkeypatch.setattr(config, "API_FOOTBALL_KEY", None)

    def boom(c, d):
        raise ConnectionError("clubelo kapalı")
    monkeypatch.setattr(registry, "ELO_SOURCES", [registry.Src("clubelo", "ClubElo", elo=boom)])
    out = run.main(["--date", "2026-11-05", "--no-llm"])
    m = out["matches"][0]
    assert "elo" not in m and m["model"]["method"] == "league_strength"
    assert run.CUP_FLAG in m["flags"]
    assert {s["id"]: s["status"] for s in out["sources"]}["clubelo"] == "missing"
