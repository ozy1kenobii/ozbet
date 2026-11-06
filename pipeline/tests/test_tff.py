"""tff.org ayrıştırıcıları — elle yazılmış iki farklı HTML yapısı (tablo / div), ağ kapalı."""
from datetime import date, datetime

from ozbet import config
from ozbet.sources import registry, tff
from ozbet.sources.base import Fixture, StatusBoard

# Yapı A: ASP.NET tablo (WebFetch ile görülen düzen), güncel hafta bağlantısız
WEEK_TABLE = """<html><body>
<div id="haftalar"><span>1. Devre</span>
<a href="https://www.tff.org/Default.aspx?pageID=142&hafta=1#macctl00_MPane">1</a>
<a href="https://www.tff.org/Default.aspx?pageID=142&hafta=12#grpctl00">12</a>
<span>«</span><b>13.Hafta</b><span>»</span>
<a href="https://www.tff.org/Default.aspx?pageID=142&hafta=14#macctl00">14</a>
<span>2. Devre</span><a href="Default.aspx?pageID=142&hafta=20">20</a></div>
<table class="MasterTable">
<tr><td><b>30.10.2026 20:00</b></td>
<td><a href="https://www.tff.org/Default.aspx?pageId=28&kulupID=964">TURKA ESENLER EROKSPOR</a></td>
<td><a href="https://www.tff.org/Default.aspx?pageId=29&macId=318215"><b>3 - 2</b></a></td>
<td><a href="https://www.tff.org/Default.aspx?pageId=28&kulupID=1">KEÇTAŞ ANKARA KEÇİÖRENGÜCÜ</a></td>
<td><a href="https://www.tff.org/Default.aspx?pageId=29&macId=318215">Detaylar</a></td></tr>
<tr><td><b>31.10.2026 19:00</b></td>
<td><a href="Default.aspx?pageId=28&kulupID=2861">MANİSA FUTBOL KULÜBÜ</a></td>
<td><a href="Default.aspx?pageId=29&macId=318216">2 - 1</a></td>
<td><a href="Default.aspx?pageId=28&kulupID=5">BATMAN PETROL SPOR A.Ş.</a></td></tr>
<tr><td><b>09.11.2026 19:00</b></td>
<td><a href="Default.aspx?pageId=28&kulupID=6">BURSASPOR</a></td>
<td><a href="Default.aspx?pageId=29&macId=318300">-</a></td>
<td><a href="Default.aspx?pageId=28&kulupID=7">BANDIRMA SPOR</a></td></tr>
</table></body></html>"""

# Yapı B: div düzeni, tarihsiz (tarih maç sayfasından gelir), takım adları bağlantısız span
WEEK_DIV = """<html><body>
<ul class="weeks"><li><a href="?pageID=198&hafta=10">10</a></li><li><a href="?pageID=198&hafta=11">11</a></li>
<li class="active">11. Hafta</li></ul>
<div class="mac"><span class="ev">GALATASARAY A.Ş.</span>
<a class="skor" href="Default.aspx?pageId=29&amp;macId=317790">2 - 2</a>
<span class="dep">ARCA ÇORUM FK</span></div>
<div class="mac"><span class="ev">FENERBAHÇE A.Ş.</span>
<a class="skor" href="Default.aspx?pageId=29&amp;macId=317791">-</a>
<span class="dep">KASIMPAŞA A.Ş.</span></div>
</body></html>"""

MATCH_IDS = """<html><body>
<span id="lblTarih">14.08.2026 - 21:30</span>
<a>ALİ SAMİ YEN SPOR KOMPLEKSİ RAMS PARK - İSTANBUL -</a>
<div id="hakemler"><a>BATUHAN KOLAK(Hakem)</a><br><a>FURKAN ÜRÜN(1. Yardımcı Hakem)</a>
<a>ASEN ALBAYRAK(Dördüncü Hakem)</a></div>
<div id="Goller1"><a>VICTOR JAMES OSIMHEN,45+2.dk (F)</a><a>VICTOR JAMES OSIMHEN,90.dk (H)</a></div>
<div id="Goller2"><a>ALEXANDROS KYZIRIDIS,59.dk (F)</a><a>JESUS ANDRES RAMIREZ DIAZ,61.dk (F)</a></div>
<div>Sarı Kart YUNUS AKGÜN 32.dk</div>
</body></html>"""

# gol kapsayıcısı belirsiz; belge sırası ev → dep
MATCH_FLAT = """<html><body><p>31.10.2026 - 19:00</p>
<p>ÖRNEK HAKEM ADI (Hakem)</p>
<table><tr><td>A OYUNCU,12.dk (F)</td></tr><tr><td>B OYUNCU,50.dk (P)</td></tr>
<tr><td>C OYUNCU,44.dk (K)</td></tr></table></body></html>"""


def test_week_list_and_current():
    weeks, cur = tff.parse_weeks(WEEK_TABLE)
    assert cur == 13 and {1, 12, 13, 14, 20} <= set(weeks)
    weeks, cur = tff.parse_weeks(WEEK_DIV)
    assert cur == 11 and weeks == [10, 11]


def test_parse_week_table():
    ms = {m["mac_id"]: m for m in tff.parse_week(WEEK_TABLE)}
    assert set(ms) == {"318215", "318216", "318300"}
    m = ms["318215"]
    assert (m["home"], m["away"], m["hg"], m["ag"], m["date"]) == (
        "TURKA ESENLER EROKSPOR", "KEÇTAŞ ANKARA KEÇİÖRENGÜCÜ", 3, 2, date(2026, 10, 30))
    assert ms["318300"]["hg"] is None


def test_parse_week_div():
    ms = {m["mac_id"]: m for m in tff.parse_week(WEEK_DIV)}
    assert ms["317790"]["home"] == "GALATASARAY A.Ş." and ms["317790"]["away"] == "ARCA ÇORUM FK"
    assert (ms["317790"]["hg"], ms["317790"]["ag"]) == (2, 2) and ms["317790"]["date"] is None
    assert ms["317791"]["hg"] is None


def test_match_referee_date_and_ht():
    pm = tff.parse_match(MATCH_IDS)
    assert pm["referee"] == "BATUHAN KOLAK" and pm["date"] == date(2026, 8, 14)
    assert pm["home_goals"] == [45.5, 90.0] and pm["away_goals"] == [59.0, 61.0]
    assert tff.ht_from_goals(pm["home_goals"], pm["away_goals"], 2, 2) == [1, 0]
    flat = tff.parse_match(MATCH_FLAT)
    assert flat["referee"] == "ÖRNEK HAKEM ADI"
    assert tff.ht_from_goals(flat["home_goals"], flat["away_goals"], 2, 1, flat["_all_goals"]) == [1, 1]
    # sayı tutmazsa İY yok
    assert tff.ht_from_goals(None, None, 3, 1, flat["_all_goals"]) is None


def test_clean_name_and_season():
    assert tff.clean_name("GALATASARAY A.Ş.") == "Galatasaray"
    assert tff.clean_name("MANİSA FUTBOL KULÜBÜ") == "Manisa"
    assert tff.season_code(date(2026, 11, 1)) == "2627"


class FakeClient:
    """URL → HTML; robots kontrolü ve gecikme yok (delay=0 → tff_client aynen kullanır)."""
    delay = 0

    def __init__(self, pages):
        self.pages, self.calls = pages, []
        self.recent = []

    def _cache_path(self, url, params):
        from pathlib import Path
        return Path("/nonexistent/x")

    def get(self, url, **kw):
        self.calls.append(url)
        for k, v in self.pages.items():
            if url.endswith(k):
                return v
        raise RuntimeError("yok: " + url)


def test_tr2_history_rows_and_budget():
    c = FakeClient({"pageID=142": WEEK_TABLE, "hafta=1": "<html></html>", "hafta=12": "<html></html>",
                    "hafta=13": WEEK_TABLE, "macId=318215": MATCH_IDS, "macId=318216": MATCH_FLAT})
    rows = tff.tr2_history(c, date(2026, 11, 6))
    assert len(rows) == 2
    r = {x["tff_id"]: x for x in rows}
    assert r["318215"]["src"] == "tff.org" and r["318215"]["season"] == "2627"
    assert r["318215"]["home"] == "Turka Esenler Erokspor"
    assert r["318216"]["hthg"] == 1 and r["318216"]["htag"] == 1   # son 2 hafta → maç sayfasından İY
    assert r["318215"]["hthg"] is None                               # gol sayısı tutmuyor (2+2 ≠ 3+2)
    assert set(r["318215"]) >= {"date", "season", "home", "away", "hg", "ag", "hthg", "htag", "odds_open",
                                "odds_close", "src"}
    b = tff.Budget(0)
    c2 = FakeClient(dict(c.pages))
    rows = tff.tr2_history(c2, date(2026, 11, 6), budget=b)
    assert not any("macId" in u for u in c2.calls) and all(x["hthg"] is None for x in rows)


def test_referees_and_matching():
    c = FakeClient({"pageID=198": WEEK_DIV, "hafta=10": "<html></html>", "hafta=11": WEEK_DIV,
                    "macId=317790": MATCH_IDS,
                    "macId=317791": "<p>07.11.2026 - 20:00</p><p>ATANAN HAKEM(Hakem)</p>"})
    refs = tff.tr1_referees(c, date(2026, 11, 6))
    by = {r["home"]: r for r in refs}
    assert by["Galatasaray"]["referee"] == "BATUHAN KOLAK" and by["Galatasaray"]["played"]
    assert by["Fenerbahçe"]["referee"] == "ATANAN HAKEM" and not by["Fenerbahçe"]["played"]
    # geçmiş satır: tarih ±1 gün + farklı yazım
    hist = [{"date": date(2026, 8, 15), "home": "Galatasaray", "away": "Corum", "hg": 2, "ag": 2},
            {"date": date(2026, 8, 20), "home": "Galatasaray", "away": "Corum", "hg": 1, "ag": 0}]
    assert tff.attach_referees_history(hist, refs) == 1
    assert hist[0]["referee"] == "BATUHAN KOLAK" and "referee" not in hist[1]
    fx = [Fixture("TR1", "Süper Lig", datetime(2026, 11, 7, 20, tzinfo=config.TZ), "Fenerbahce", "Kasimpasa",
                  "nesine", "t"),
          Fixture("TR2", "1. Lig", datetime(2026, 11, 7, 20, tzinfo=config.TZ), "Fenerbahce", "Kasimpasa",
                  "nesine", "t")]
    assert tff.attach_referees_fixtures(fx, refs) == 1
    assert fx[0].extra["referee"] == "ATANAN HAKEM" and "referee" not in fx[1].extra
    assert tff.referee_map(refs)[("2026-11-07", "fenerbahce", "kasimpasa")] == "ATANAN HAKEM"


def test_registry_wrapped_no_network(tmp_path):
    """Ağ kapalıyken kaynaklar 'missing' olur, akış durmaz."""
    from ozbet.http import PoliteClient
    board = StatusBoard()
    client = PoliteClient(cache_dir=tmp_path, delay=0)
    assert registry.tff_referees(client, board, date(2026, 11, 6), {}, []) == []
    assert board.items["tff_referees"].status == "missing"
    registry.extra_history(client, board, date(2026, 11, 6), data_dir=tmp_path)
    assert board.items["tff_tr2"].status == "missing"
    assert "TFF" in board.items["tff_tr2"].name
