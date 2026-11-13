"""Kaynak onarımı: geri çekilmeli yeniden deneme, içerik denetimi, bayat önbellek, engel hafızası,
Understat/ClubElo/SportyTrader ayrıştırıcıları, kapatılan kaynaklar ve sağlık özetindeki model girdileri.

tests/fixtures altındaki dosyalar sentetiktir; yapıları teşhis dökümlerinden (teshis dalı) ve adapter
belgelerinden alınmıştır. Gerçek site içeriği kopyalanmamıştır.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

import pytest
import requests

from ozbet import health, http as ozhttp
from ozbet.http import BadContent, Blocked, PoliteClient
from ozbet.sources import clubelo, freesupertips, registry, soccerstats, sportytrader, understat
from ozbet.sources.base import StatusBoard

FX = Path(__file__).parent / "fixtures"


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


class Resp:
    def __init__(self, status=200, text="", headers=None, url="http://x"):
        self.status_code, self.text, self.headers, self.url = status, text, headers or {}, url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} hata", response=self)


class Session:
    """Sıradaki yanıtları (veya url → yanıt eşlemesini) döndüren sahte oturum; istekleri sayar."""
    def __init__(self, *queue, by_url=None):
        self.queue, self.by_url, self.calls = list(queue), by_url or {}, []
        self.headers = {}

    def get(self, url, **kw):
        self.calls.append(url)
        for frag, r in self.by_url.items():
            if frag in url:
                r = r(url) if callable(r) else r
                break
        else:
            r = self.queue.pop(0) if self.queue else Resp(200, "x" * 40)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def sleeps(monkeypatch):
    got = []
    monkeypatch.setattr(ozhttp.time, "sleep", got.append)
    monkeypatch.setattr(ozhttp.random, "random", lambda: 0.0)
    return got


@pytest.fixture(autouse=True)
def clean_stale():
    ozhttp.STALE.clear()
    yield
    ozhttp.STALE.clear()


def client_with(tmp_path, *queue, by_url=None) -> PoliteClient:
    c = PoliteClient(cache_dir=tmp_path, delay=0)
    c.s = Session(*queue, by_url=by_url)
    return c


def age(c: PoliteClient, url: str, hours: float, params=None):
    p = c._cache_path(url, params)
    t = time.time() - hours * 3600
    os.utime(p, (t, t))


# ---------------- geri çekilme ----------------
def test_backoff_exponential_then_success(tmp_path, sleeps):
    ok = "Rank,Club,Country,Level,Elo\n1,A,ENG,1,1500\n"
    c = client_with(tmp_path, Resp(502), requests.ConnectionError("koptu"), Resp(200, ok))
    assert c.get("http://e.test/a", check_robots=False, retries=2) == ok
    assert sleeps == [2.0, 4.0] and len(c.s.calls) == 3


def test_backoff_gives_up_and_honours_retry_after(tmp_path, sleeps):
    c = client_with(tmp_path, Resp(503, headers={"Retry-After": "7"}), Resp(503, headers={"Retry-After": "999"}),
                    Resp(502))
    with pytest.raises(requests.HTTPError):
        c.get("http://e.test/a", check_robots=False, retries=2)
    assert sleeps == [7.0, ozhttp.BACKOFF_MAX_S] and len(c.s.calls) == 3


def test_permanent_error_not_retried(tmp_path, sleeps):
    c = client_with(tmp_path, Resp(404))
    with pytest.raises(requests.HTTPError):
        c.get("http://e.test/yok", check_robots=False)
    assert len(c.s.calls) == 1 and sleeps == []


# ---------------- içerik denetimi + bayat önbellek ----------------
def test_validate_keeps_maintenance_page_out_of_cache(tmp_path, sleeps):
    url = "https://understat.test/getLeagueData/EPL/2026"
    c = client_with(tmp_path, Resp(200, fx("understat_bakim.html")))
    with pytest.raises(BadContent):
        c.get(url, check_robots=False, validate=understat._json_ok)
    assert not c._cache_path(url, None).exists()
    # eski sürümün yazdığı bozuk kopya: taze görünse de atılır ve yeniden istenir
    c._cache_path(url, None).write_text(fx("understat_bakim.html"), encoding="utf-8")
    c.s = Session(Resp(200, fx("understat_league.json")))
    assert c.get(url, check_robots=False, ttl=30 * 86400, validate=understat._json_ok).startswith("{")
    assert len(c.s.calls) == 1


def test_stale_cache_used_on_failure_and_marked(tmp_path, sleeps):
    url = "http://api.clubelo.test/2026-11-05"
    c = client_with(tmp_path, Resp(200, fx("clubelo.csv")))
    assert c.get(url, check_robots=False, ttl=3600) == fx("clubelo.csv")
    age(c, url, 30)
    c.s = Session(by_url={"clubelo": Resp(502)})
    assert c.get(url, check_robots=False, ttl=3600, stale=3 * 86400, retries=1) == fx("clubelo.csv")
    assert c.stale[url] == pytest.approx(30 * 3600, rel=0.01)
    assert ozhttp.STALE["api.clubelo.test"] == pytest.approx(30.0, abs=0.2)
    assert c.cached(url, max_age=86400) is None and c.cached(url, max_age=2 * 86400)[0] == fx("clubelo.csv")
    # izin verilen bayatlık aşılmışsa ya da stale istenmemişse hata aynen çıkar
    with pytest.raises(requests.HTTPError):
        c.get(url, check_robots=False, ttl=3600, stale=3600, retries=0)
    with pytest.raises(requests.HTTPError):
        c.get(url, check_robots=False, ttl=3600, retries=0)


# ---------------- engel: aşılmaz, yeniden denenmez, alan adı dinlendirilir ----------------
def test_block_reason_detection():
    assert "doğrulama" in ozhttp.block_reason(403, fx("cloudflare_challenge.html"))
    assert "doğrulama" in ozhttp.block_reason(503, fx("cloudflare_challenge.html"))
    assert "güvenlik duvarı" in ozhttp.block_reason(403, fx("cloudflare_blocked.html"))
    assert "202" in ozhttp.block_reason(202, "")
    assert ozhttp.block_reason(200, "<html>normal sayfa</html>") is None
    assert ozhttp.block_reason(502, "") is None


def test_blocked_not_retried_and_host_rested(tmp_path, sleeps, monkeypatch):
    blocked = Resp(403, fx("cloudflare_challenge.html"))
    c = client_with(tmp_path, by_url={"st.test": blocked})
    for path in ("a", "b"):
        with pytest.raises(Blocked, match="Cloudflare bot doğrulama"):
            c.get(f"https://st.test/{path}", check_robots=False)
    assert len(c.s.calls) == 2 and sleeps == []
    with pytest.raises(Blocked, match="yeni istek atılmıyor"):       # aynı çalıştırma: 3. istek ağa çıkmaz
        c.get("https://st.test/c", check_robots=False)
    assert len(c.s.calls) == 2
    # üç çalıştırma üst üste engel → çalıştırmalar arası dinlendirme
    for _ in range(ozhttp.BLOCK_STRIKES - 1):
        c2 = client_with(tmp_path, by_url={"st.test": blocked})
        assert c2.block_wait("st.test") == 0
        for path in ("a", "b"):
            with pytest.raises(Blocked):
                c2.get(f"https://st.test/{path}", check_robots=False)
    c3 = client_with(tmp_path, by_url={"st.test": Resp(200, "y" * 50)})
    assert 0 < c3.block_wait("st.test") <= ozhttp.BLOCK_COOLDOWN_S
    with pytest.raises(Blocked, match="çalıştırmadır engelliyor"):
        c3.get("https://st.test/a", check_robots=False)
    assert c3.s.calls == []
    # süre dolunca yeniden denenir; başarı hafızayı siler
    real = time.time()
    monkeypatch.setattr(ozhttp.time, "time", lambda: real + ozhttp.BLOCK_COOLDOWN_S + 60)
    assert c3.get("https://st.test/a", check_robots=False, ttl=0) == "y" * 50
    assert c3.block_wait("st.test") == 0 and "st.test" not in c3._load_blocks()


def test_single_block_does_not_rest_host(tmp_path, sleeps):
    c = client_with(tmp_path, Resp(403, "yasak"), Resp(200, "z" * 50))
    with pytest.raises(Blocked):
        c.get("https://n.test/sonuc", check_robots=False)
    assert c.get("https://n.test/bulten", check_robots=False) == "z" * 50      # tek engel bülteni kesmez
    assert c._load_blocks() == {}


def test_empty_202_is_blocked_with_reason(tmp_path, sleeps):
    b = StatusBoard()
    c = client_with(tmp_path, by_url={"tm.test": Resp(202, "")})
    assert b.run("transfermarkt", "TM", lambda: c.get("https://tm.test/x", check_robots=False)) is None
    assert b.items["transfermarkt"].status == "missing" and "bot doğrulaması" in b.items["transfermarkt"].note


# ---------------- Understat ----------------
def test_understat_parsers():
    rows = understat.parse_json(fx("understat_league.json"))
    assert rows == understat.parse_html(fx("understat_league.html"))
    assert len(rows) == 2          # oynanmamış maç girmez
    assert rows[0] == {"date": dt.date(2026, 11, 1), "home": "Arsenal", "away": "Chelsea", "hxg": 1.834, "axg": 0.912}
    assert understat.is_maintenance(fx("understat_bakim.html"))
    assert not understat._json_ok(fx("understat_bakim.html")) and not understat._html_ok(fx("understat_bakim.html"))
    with pytest.raises(RuntimeError, match="datesData"):
        understat.parse_html("<html><body>yeni tasarım</body></html>")


def test_understat_maintenance_clear_note_single_request(tmp_path, sleeps):
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404), "understat.com": Resp(200, fx("understat_bakim.html"))})
    b = StatusBoard()
    assert b.run("understat", "Understat", lambda: understat.league_xg(c, dt.date(2026, 11, 13))) is None
    st = b.items["understat"]
    assert st.status == "missing" and "bakımda" in st.note and "come back soon" in st.note
    assert len([u for u in c.s.calls if "robots" not in u]) == 1      # site kapalı: tek istekte bırakılır
    assert list(tmp_path.glob("[0-9a-f]*")) == []                     # bakım sayfası önbelleğe girmedi


def test_understat_html_fallback_and_stale_copy(tmp_path, sleeps):
    def site(url):
        return Resp(404) if "getLeagueData" in url else Resp(200, fx("understat_league.html"))
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404), "understat.com": site})
    rows = understat.season_matches(c, "EPL", 2026)        # JSON ucu yok → eski HTML biçimi
    assert len(rows) == 2 and rows[1]["home"] == "Liverpool"
    # ertesi gün site bakımda: 3 günlük kopya kullanılır ve işaretlenir
    age(c, "https://understat.com/league/EPL/2026", 72)
    c.s = Session(by_url={"understat.com": Resp(200, fx("understat_bakim.html"))})
    assert understat.season_matches(c, "EPL", 2026) == rows
    assert ozhttp.STALE["understat.com"] == pytest.approx(72.0, abs=0.2)
    # kopya 14 günden eskiyse kullanılmaz
    age(c, "https://understat.com/league/EPL/2026", 15 * 24)
    with pytest.raises(understat.Maintenance):
        understat.season_matches(c, "EPL", 2026)


# ---------------- ClubElo ----------------
def test_clubelo_falls_back_to_cached_day(tmp_path, sleeps):
    day = dt.date(2026, 11, 5)
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404), "clubelo": Resp(200, fx("clubelo.csv"))})
    t = clubelo.ratings(c, day)
    assert len(t) == 4 and t.stale_days == 0 and t.date == "2026-11-05"
    age(c, "http://api.clubelo.com/2026-11-05", 26)
    c.s = Session(by_url={"clubelo": Resp(502)})
    t2 = clubelo.ratings(c, day + dt.timedelta(days=1))
    assert t2.stale_days == 1 and t2.date == "2026-11-05" and t2.lookup("Galatasaray")["elo"] == 1796.4
    assert ozhttp.STALE["api.clubelo.com"] >= 24
    assert t2.pair("Galatasaray", "Fenerbahce")["date"] == "2026-11-05"       # maç kartında gerçek tablo tarihi
    # önbellekte hiç kopya yoksa asıl hata görünür
    b = StatusBoard()
    c3 = client_with(tmp_path / "bos", by_url={"robots.txt": Resp(404), "clubelo": Resp(502)})
    assert b.run("clubelo", "ClubElo", lambda: clubelo.ratings(c3, day)) is None
    assert "502" in b.items["clubelo"].note


def test_clubelo_future_day_asks_today(tmp_path, sleeps):
    from ozbet import config
    today = dt.datetime.now(config.TZ).date()
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404), "clubelo": Resp(200, fx("clubelo.csv"))})
    t = clubelo.ratings(c, today + dt.timedelta(days=2))
    assert t.date == today.isoformat() and c.s.calls[-1].endswith("/" + today.isoformat())


# ---------------- SportyTrader / FreeSuperTips / SoccerStats ----------------
def test_sportytrader_parsers():
    assert sportytrader.parse_links(fx("sportytrader_liste.html")) == [
        "/en/betting-tips/arsenal-chelsea-385001/", "/en/betting-tips/galatasaray-fenerbahce-385002/"]
    assert sportytrader.parse_match(fx("sportytrader_mac.html")) == ("Arsenal", "Chelsea",
                                                                     "Arsenal to win and over 2.5 goals")
    assert sportytrader.parse_links(fx("cloudflare_challenge.html")) == []


def test_sportytrader_end_to_end_and_block_note(tmp_path, sleeps):
    ok = client_with(tmp_path / "ok", by_url={"robots.txt": Resp(404),
                                              "/football/": Resp(200, fx("sportytrader_liste.html")),
                                              "-38500": Resp(200, fx("sportytrader_mac.html"))})
    preds = sportytrader.predictions(ok, dt.date(2026, 11, 21))
    assert len(preds) == 2 and preds[0].picks == {"1X2": "1", "OU25": "O2.5"}
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404),
                                      "sportytrader": Resp(403, fx("cloudflare_challenge.html"))})
    b = StatusBoard()
    assert b.run("sportytrader", "ST", lambda: sportytrader.predictions(c, dt.date(2026, 11, 13))) is None
    note = b.items["sportytrader"].note
    assert note.startswith("Blocked") and "engelli" in note and "maç linki bulunamadı" not in note
    assert len([u for u in c.s.calls if "robots" not in u]) == 2
    # sayfa okundu ama desen tutmuyorsa: yapı değişikliği diye raporlanır
    c2 = client_with(tmp_path / "yapi", by_url={"robots.txt": Resp(404),
                                                "sportytrader": Resp(200, "<html><body>" + "a" * 60 + "</body></html>")})
    with pytest.raises(RuntimeError, match="LINK deseni"):
        sportytrader.predictions(c2, dt.date(2026, 11, 13))


def test_freesupertips_and_soccerstats_report_block(tmp_path, sleeps):
    c = client_with(tmp_path, by_url={"robots.txt": Resp(404), "": Resp(403, fx("cloudflare_blocked.html"))})
    with pytest.raises(Blocked, match="güvenlik duvarı"):
        freesupertips.predictions(c, dt.date(2026, 11, 13))
    with pytest.raises(Blocked, match="SoccerStats erişimi engelliyor"):
        soccerstats.results_history(c, "turkey2", dt.date(2026, 11, 13))
    assert len([u for u in c.s.calls if "soccerstats" in u and "robots" not in u]) == 1   # 3 sezon denenmez


# ---------------- kapatılan kaynaklar ----------------
def test_disabled_sources_not_run():
    off = {sid: note for sid, _, note in registry.DISABLED}
    assert "forebet" in off and "Cloudflare" in off["forebet"]
    assert "forebet" not in {s.id for s in registry.PREDICTION_SOURCES}
    assert {s.id for s in registry.PREDICTION_SOURCES} >= {"sportytrader", "freesupertips"}
    if not registry.SOCCERSTATS_ON:
        assert {"soccerstats", "soccerstats_tr2"} <= set(off) and registry.SOCCERSTATS_HISTORY == {}
        assert "soccerstats" not in {s.id for s in registry.PREDICTION_SOURCES}
        assert "OZBET_ENABLE_SOURCES" in off["soccerstats"]
    ids = [s.id for s in registry.FIXTURE_SOURCES]
    assert ids[:2] == ["nesine", "iddaa"] and (("api_football" in ids) != ("api_football" in off))


def test_api_football_history_skipped_without_key(tmp_path, monkeypatch):
    from ozbet import config
    monkeypatch.setattr(config, "API_FOOTBALL_KEY", None)
    b = StatusBoard()
    registry.extra_history(PoliteClient(cache_dir=tmp_path, delay=0), b, dt.date(2026, 11, 6), data_dir=tmp_path)
    st = b.items["api_football_history"]
    assert st.status == "skipped" and "API_FOOTBALL_KEY" in st.note


# ---------------- sağlık: model girdileri ----------------
def _src(sid, status, items, note=None):
    return {"id": sid, "name": sid.upper(), "status": status, "items": items, "note": note}


def test_health_inputs_reflect_run(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "PREDICTION_SOURCES", [registry.Src("sportytrader", "ST"),
                                                         registry.Src("freesupertips", "FST")])
    srcs = [_src("understat", "missing", 0, "RuntimeError: understat bakımda"), _src("clubelo", "ok", 620),
            _src("sportytrader", "missing", 0, "Blocked: HTTP 403"), _src("freesupertips", "ok", 20),
            _src("forebet", "skipped", 0, "Devre dışı"), _src("transfermarkt", "partial", 0, "Veri dönmedi"),
            _src("news_rss", "ok", 12)]
    ozhttp.STALE["api.clubelo.com"] = 26.0
    out = health.update(tmp_path / "health.json", "2026-11-13T08:30:00+03:00", "08:30", srcs, {})
    inp = out["inputs"]
    assert inp["xg"] is False and inp["elo"] is True and inp["squad"] is False and inp["news"] is True
    assert inp["consensus_sources"] == 1 and inp["consensus_total"] == 2 and inp["degraded"] is True
    assert inp["stale"] == {"api.clubelo.com": 26.0}
    assert any(m.startswith("xG (Understat) yok") and "bakımda" in m for m in inp["missing"])
    assert any("kadro" in m for m in inp["missing"]) and not any("Elo" in m for m in inp["missing"])
    # eski anahtarlar yerinde
    assert set(out) >= {"sources", "alerts", "runs", "inputs"}
    assert set(out["sources"]["clubelo"]) == {"history", "streak", "ok_rate", "last_ok", "level"}
    import json
    run = json.loads((tmp_path / "health.json").read_text())["runs"][-1]
    assert run["inputs"] == {"xg": False, "elo": True, "consensus_sources": 1, "squad": False, "news": True,
                             "stale": {"api.clubelo.com": 26.0}}
    assert run["sources"]["clubelo"] == ["ok", 620] and "quality" in run


def test_health_disabled_source_is_not_a_failure(tmp_path):
    p = tmp_path / "health.json"
    for i in range(3):
        health.update(p, f"t{i}", "08:30", [_src("forebet", "missing", 0), _src("a", "ok", 1)], {})
    out = health.update(p, "t3", "08:30", [_src("forebet", "skipped", 0), _src("a", "ok", 1)], {})
    f = out["sources"]["forebet"]
    assert f["level"] == "kapali" and f["streak"] == 0 and f["ok_rate"] is None and out["alerts"] == []
    assert f["history"] == ["missing", "missing", "missing", "skipped"]
    full = health.inputs([_src("understat", "ok", 900), _src("clubelo", "ok", 600), _src("freesupertips", "ok", 20),
                          _src("transfermarkt", "ok", 30), _src("news_rss", "ok", 5)], stale={})
    assert full["degraded"] is False and full["missing"] == [] and full["stale"] == {}
