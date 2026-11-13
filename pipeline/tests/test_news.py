"""Haber Toplama (RSS/Atom) testleri — ağ yok, fixture akışlarla."""
from datetime import datetime, timedelta

import pytest

from ozbet import config
from ozbet.agents import commentator, squad
from ozbet.sources import news_rss as N
from ozbet.sources.base import Fixture, MissingPlayer, TeamNews

NOW = datetime(2026, 11, 5, 18, 0, tzinfo=config.TZ)


def _rfc(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0300")


RSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="https://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Futbol</title><link>https://example.com</link><description>d</description>
<item><title><![CDATA[Galatasaray'da Icardi sakatlandı]]></title><link>https://example.com/a?x=1&amp;y=2</link>
 <description><![CDATA[<img src="x.jpg"/> Arjantinli golcü antrenmanda sakatlık yaşadı&nbsp;ve maçta yok.]]></description>
 <pubDate>{_rfc(NOW - timedelta(hours=5))}</pubDate></item>
<item><title>Fenerbahçe'de teknik direktör görevine yeni isim getirildi</title><link>https://example.com/b</link>
 <description>Kulüp açıklama yaptı.</description><pubDate>{_rfc(NOW - timedelta(days=4))}</pubDate></item>
<item><title>Eski haber: Galatasaray kampa girdi</title><link>https://example.com/c</link>
 <pubDate>{_rfc(NOW - timedelta(hours=80))}</pubDate></item>
<item><title>Başlıksız bağlantı yok</title><pubDate>{_rfc(NOW)}</pubDate></item>
<item><title>Fenerbahçe Beko Euroleague'de kazandı</title><link>https://example.com/d</link>
 <pubDate>{_rfc(NOW - timedelta(hours=2))}</pubDate></item>
<item><title>Kırık</title><link>javascript:alert(1)</link><pubDate>{_rfc(NOW)}</pubDate></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>ntvspor.net</title><link rel="alternate">https://www.ntvspor.net</link>
<entry><title>Roma, Inter karşısında kırmızı kart gördü</title>
 <link rel="alternate" href="https://example.com/e"/><link rel="enclosure" href="https://example.com/e.jpg"/>
 <published>2026-11-05T15:00:00+03:00</published><summary>Serie A maçında oyuncu cezalı duruma düştü.</summary></entry>
<entry><title>Manchester City manager sacked after defeat</title><link href="https://example.com/f"/>
 <updated>2026-11-04T10:00:00Z</updated><summary>Club statement.</summary></entry>
</feed>"""


def fx(home, away, lg="TR1"):
    return Fixture(lg, "", NOW + timedelta(hours=2), home, away, "test", "")


# ---------- ayrıştırma ----------
def test_parse_rss():
    items = N.parse_feed(RSS, "Örnek")
    titles = [i.title for i in items]
    assert "Galatasaray'da Icardi sakatlandı" in titles
    assert "Başlıksız bağlantı yok" not in titles          # bağlantısız öğe atlanır
    assert "Kırık" not in titles                           # http(s) olmayan bağlantı atlanır
    a = items[0]
    assert a.url == "https://example.com/a?x=1&y=2"
    assert a.source == "Örnek" and a.published == NOW - timedelta(hours=5)
    assert "<img" not in a.summary and "sakatlık" in a.summary   # &nbsp; varlığı ayrıştırmayı bozmaz


def test_parse_atom():
    items = N.parse_feed(ATOM, "NTV Spor")
    assert [i.url for i in items] == ["https://example.com/e", "https://example.com/f"]
    assert items[0].published.isoformat() == "2026-11-05T15:00:00+03:00"
    assert items[1].published.utcoffset() == timedelta(0)   # <updated> yedeği
    assert "cezalı" in items[0].summary


def test_parse_truncated_and_garbage():
    cut = RSS[: RSS.index("<item><title>Eski haber")] + "<item><title>Yarım"
    items = N.parse_feed(cut, "x")
    assert len(items) == 2                                 # son tam öğeye kadar kurtarılır
    assert N.parse_feed("<html><body>RSS sayfası</body></html>", "x") == []
    assert N.parse_feed("not xml at all", "x") == []


def test_parse_date_formats():
    assert N.parse_date("Mon, 2 Nov 2026 11:52:53 EST").utcoffset() == timedelta(hours=-5)
    assert N.parse_date("2026-11-05T15:00:00Z").utcoffset() == timedelta(0)
    assert N.parse_date("2026-11-05T15:00:00").tzinfo is not None
    assert N.parse_date("dün") is None and N.parse_date(None) is None


# ---------- takım eşleme ----------
@pytest.fixture
def ix():
    return N.TeamIndex.from_fixtures([
        fx("Galatasaray", "Fenerbahçe"), fx("Roma", "Inter", "ITA1"), fx("Manchester City", "Arsenal", "ENG1"),
        fx("Iğdır FK", "Ankara Keçiörengücü", "TR2"), fx("Paris Saint-Germain", "Milan", "UCL"),
    ])


@pytest.mark.parametrize("text,expected", [
    ("Galatasaray'da Icardi sakatlandı", {"galatasaray"}),
    ("Fenerbahce Istanbul açıklama yaptı", {"fenerbahce"}),
    ("Man City beat Arsenal", {"manchester-city", "arsenal"}),
    ("AS Roma, yeni sezona hazır", {"roma"}),                 # kulüp öneki
    ("Inter, Roma deplasmanında", {"inter", "roma"}),         # iki belirsiz ad, rakip bağlamı
    ("Roma'da Serie A heyecanı", {"roma"}),                   # lig bağlamı
    ("Keçiörengücü'nde yeni dönem", {"keciorengucu"}),        # sözlük dışı adın ayırt edici kelimesi
    ("PSG, Milan'ı ağırlıyor", {"paris-saint-germain", "milan"}),
])
def test_match_positive(ix, text, expected):
    assert ix.match(text) == expected


@pytest.mark.parametrize("text", [
    "Roma'da tarihi gün: Papa açıklama yaptı",       # şehir
    "Inter Miami sign new forward",                  # başka kulüp
    "City centre traffic chaos",                     # sıradan kelime
    "Manchester United news today",                  # City ≠ United
    "Milan Cortina 2026 kış olimpiyatları",          # olimpiyat
    "Paris'te moda haftası",                         # şehir
    "Galatasaraylı taraftarlar yürüdü",              # kelime sınırı (ek almış farklı kelime)
    "Real Madrid kazandı",                            # günün maçı değil
    "Iğdır'da kar yağışı",                            # belirsiz şehir adı, bağlam yok
])
def test_match_false_positives(ix, text):
    assert ix.match(text) == set()


def test_youth_and_women_teams_not_indexed():
    ix = N.TeamIndex.from_fixtures([fx("Galatasaray U19", "Fenerbahçe U19"), fx("Galatasaray (K)", "Beşiktaş (K)")])
    assert ix.match("Galatasaray sakat") == set()


def test_unknown_league_not_indexed():
    ix = N.TeamIndex.from_fixtures([fx("Union", "Victoria", None)])
    assert ix.names == {}


# ---------- etiketleme ----------
@pytest.mark.parametrize("text,tags", [
    ("Galatasaray'da Icardi sakatlandı", ["sakat"]),
    ("Yıldız oyuncunun sakatlığı ciddi", ["sakat"]),
    ("Salah ruled out with hamstring injury", ["sakat"]),
    ("Kırmızı kart gören Osimhen cezalı duruma düştü", ["ceza"]),
    ("Player suspended for three matches", ["ceza"]),
    ("PFDK'dan Fenerbahçe'ye ceza", ["ceza"]),               # disiplin kurulu = ceza bağlamı
    ("Teknik direktör istifa etti", ["td"]),
    ("Kasımpaşa hocası ile yollarını ayırdı", ["td"]),
    ("Manager sacked after defeat", ["td"]),
    ("Chelsea appointed new head coach", ["td"]),
    ("Yıldız oyuncu kadroya alınmadı, rotasyon bekleniyor", ["kadro"]),
    ("Milli takım kamp kadrosu açıklandı", ["kadro"]),
    ("Transferde sıcak gelişme", ["transfer"]),
    ("Hoca: Maçı kazanmak istiyoruz", []),                    # rol var, değişim yok → td değil
    ("Takım antrenmanda", []),
    ("Sakatat fiyatları", []),                                # 'sakat' kökü ama farklı kelime
    ("Banner advertising", []),                               # 'ban' kelime sınırı
])
def test_tags(text, tags):
    assert N.tag(text) == tags


# ---------- 72 saat / td penceresi / birleştirme ----------
def test_assign_window_and_limits(ix):
    items = N.parse_feed(RSS, "Örnek") + N.parse_feed(ATOM, "NTV Spor")
    # aynı başlık farklı kaynaktan (tekilleştirilmeli)
    items.append(N.Item("Galatasaray'da Icardi sakatlandı!", "https://example.com/dup", "Başka",
                        NOW - timedelta(hours=1)))
    for i in range(10):
        items.append(N.Item(f"Galatasaray haber {i}", f"https://example.com/g{i}", "x", NOW - timedelta(hours=10 + i)))
    out = N.assign(items, ix, NOW)
    gs = out["galatasaray"]["items"]
    assert len(gs) == N.PER_TEAM
    assert all(NOW - datetime.fromisoformat(g["published"]) <= timedelta(hours=72) for g in gs)
    assert not any("Eski haber" in g["title"] for g in gs)          # 80 saatlik haber düşer
    assert sum("Icardi" in g["title"] for g in gs) == 1              # tekilleştirme
    assert gs[0]["published"] >= gs[-1]["published"]                 # yeniden eskiye
    assert set(gs[0]) == {"title", "url", "source", "published", "tags"}   # özet JSON'a yazılmaz
    # Fenerbahçe: td haberi 4 gün önce → 72 saatte gösterilmez ama coach_change açılır
    assert out["fenerbahce"]["coach_change"] is True
    assert out["fenerbahce"]["items"] == []                          # basketbol haberi elendi
    assert out["manchester-city"]["coach_change"] is True
    assert out["roma"]["items"][0]["tags"] == ["ceza"]
    assert out["inter"]["coach_change"] is False


def test_coach_change_needs_team_in_title(ix):
    it = N.Item("Teknik direktör istifa etti", "https://example.com/z", "x", NOW - timedelta(days=1),
                summary="Galatasaray maçı sonrası açıklama")
    out = N.assign([it], ix, NOW)
    # takım yalnızca özette geçiyor → ne haber ne TD sinyali o takıma yazılır
    assert "galatasaray" not in out


def test_team_feed_hint_and_limit():
    fixtures = [fx("Galatasaray", "Fenerbahçe"), fx("Beşiktaş", "Göztepe"), fx("Arsenal", "Chelsea", "ENG1")]
    t = N.team_feed_targets(fixtures)
    assert [k for k, _, _ in t] == ["galatasaray", "fenerbahce", "besiktas", "goztepe"]
    assert len(N.team_feed_targets(fixtures, limit=2)) == 2
    ix = N.TeamIndex.from_fixtures(fixtures)
    it = N.Item("Okan Buruk'tan açıklama", "https://example.com/h", "A Spor", NOW, team_hint="galatasaray")
    assert N.assign([it], ix, NOW)["galatasaray"]["items"][0]["source"] == "A Spor"


class FakeClient:
    def __init__(self, bodies):
        self.bodies, self.calls = bodies, []

    def get(self, url, **kw):
        self.calls.append((url, kw.get("ttl")))
        if url in self.bodies:
            return self.bodies[url]
        raise OSError("ağ yok")


def test_collect_and_for_match():
    url = N.FEEDS[0][2]
    c = FakeClient({url: RSS})
    got = N.collect(c, [fx("Galatasaray", "Fenerbahçe")], now=NOW)
    assert got["feeds_ok"] == 1 and got["feeds_failed"]
    assert all(ttl == N.TTL for _, ttl in c.calls)
    assert sum(1 for u, _ in c.calls if "/rss/" in u and ("galatasaray" in u or "fenerbahce" in u)) == 2
    blk = N.for_match("Galatasaray", "Fenerbahçe", got)
    assert blk["home"][0]["tags"] == ["sakat"] and blk["away"] == [] and blk["fetched_at"]
    assert N.for_match("Arsenal", "Chelsea", got) is None
    assert N.coach_change_keys(got) == {"fenerbahce"}
    with pytest.raises(RuntimeError):
        N.collect(FakeClient({}), [fx("Galatasaray", "Fenerbahçe")], now=NOW)


# ---------- kadro sinyali + yorum ----------
def test_squad_coach_signal_merges():
    fixtures = [fx("Galatasaray", "Fenerbahçe")]
    news = {"galatasaray": TeamNews("Galatasaray", "flashscore", "t", [MissingPlayer("Oyuncu", "sakat", True)])}
    assert squad.add_coach_signals(news, {"galatasaray", "fenerbahce", "bilinmeyen"}, fixtures) == 2
    assert news["galatasaray"].coach_change and news["galatasaray"].missing   # mevcut kayıt korunur
    assert news["fenerbahce"].missing == [] and news["fenerbahce"].source == "haber_rss"
    out = squad.build("Galatasaray", "Fenerbahçe", NOW, "TR1", news, fixtures)
    assert out["home"]["coach_change"] and out["away"]["coach_change"]
    assert out["source"] == "flashscore"


def test_comment_news_sentence_and_limit():
    m = {"home": {"name": "Galatasaray"}, "away": {"name": "Fenerbahçe"},
         "news": {"home": [{"tags": ["sakat"]}, {"tags": ["sakat", "transfer"]}, {"tags": []}],
                  "away": [{"tags": ["transfer"]}]}}
    assert commentator.news_sentence(m) == "Son 3 günde Galatasaray ile ilgili 2 sakatlık haberi var."
    m["news"]["away"].append({"tags": ["td"]})
    assert "Fenerbahçe ile ilgili 1 teknik direktör" in commentator.news_sentence(m)
    assert commentator.news_sentence({"home": {"name": "A"}, "away": {"name": "B"}}) is None
    full = dict(m, model=None, stats={}, squad={})
    text = commentator.rule_comment(full)
    assert "Son 3 günde Galatasaray" in text
    assert text.count(".") <= 6


def test_title_only_matching_and_nicknames():
    import datetime as _dt
    from ozbet import config as _c
    from ozbet.sources import news_rss as nr
    from ozbet.sources.base import Fixture
    ko = _dt.datetime(2026, 11, 5, 20, 45, tzinfo=_c.TZ)
    fx = [Fixture("UEL", "", ko, "Celtic", "Beşiktaş", "x", "t"), Fixture("UEL", "", ko, "Crystal Palace", "Hoffenheim", "x", "t")]
    ix = nr.TeamIndex.from_fixtures(fx)
    assert ix.match("Kartal, Celtic ile ilk kez karşılaşıyor!") == {nr.team_key("Celtic"), nr.team_key("Beşiktaş")}
    assert ix.match("Avrupa Ligi'nde bu akşam") == set()


# ---------- takıma özel etiket (özne tespiti): isabet > kapsama ----------
@pytest.fixture
def ix2():
    return N.TeamIndex.from_fixtures([
        fx("Çorum FK", "Fenerbahçe"), fx("Celtic", "Hearts", "SCO1"), fx("Galatasaray", "Amed Sportif Faaliyetler"),
        fx("Beşiktaş", "Gençlerbirliği"), fx("Trabzonspor", "Freiburg", "UECL"), fx("Roma", "Inter", "ITA1"),
        fx("Stuttgart", "Liverpool", "UCL"),
    ])


@pytest.mark.parametrize("title,expected", [
    # canlı veriden: rakip yalnız "… maçı öncesi" bağlamında geçiyor → etiket yalnız özne takıma
    ("Arca Çorum FK'dan Fenerbahçe maçı öncesi sakatlık açıklaması!", {"corum": ["sakat"], "fenerbahce": []}),
    ("Fenerbahçe maçına saatler kala Çorum FK'da sakatlık depremi! 6-8 hafta yok",
     {"corum": ["sakat"], "fenerbahce": []}),
    ("Podcast: Celtic under pressure & injury-hit Hearts head for Europe", {"celtic": [], "hearts": ["sakat"]}),
    ("Galatasaray'da Stuttgart zaferi sonrası sakatlık krizi", {"galatasaray": ["sakat"], "stuttgart": []}),
    ("Roma, Inter karşısında kırmızı kart gördü", {"roma": ["ceza"], "inter": []}),
    # fikstür çifti: kimin kart gördüğü belli değil → hiçbirine yazılmaz
    ("Beşiktaş - Gençlerbirliği maçında kırmızı kart! İşte o pozisyon", {"besiktas": [], "genclerbirligi": []}),
    # tek takım geçiyor ama o da yalnız bağlam (başka takımın hocası konuşuyor) → etiket yok
    ("Thomas Reis'tan Freiburg maçı öncesi sakatlık açıklaması!", {"freiburg": []}),
    # tek özne
    ("Beşiktaş'ta sarı kart gören Orkun Kökçü cezalı duruma düştü!", {"besiktas": ["ceza"]}),
    # kadro dışı etiketler (transfer) eskisi gibi iki takıma da yazılır
    ("Fenerbahçe ve Galatasaray transfer yarışında", {"fenerbahce": ["transfer"], "galatasaray": ["transfer"]}),
])
def test_team_tags_subject_only(ix2, title, expected):
    assert N.team_tags(title, ix2) == expected


def test_team_feed_hint_gets_tag_only_without_other_subject(ix2):
    t = "Thomas Reis'tan Freiburg maçı öncesi sakatlık açıklaması!"
    assert N.team_tags(t, ix2, "trabzonspor") == {"trabzonspor": ["sakat"], "freiburg": []}
    # kulüp akışından gelse de başlığın öznesi başka takımsa etiket o takıma gider
    t2 = "Galatasaray'da sakatlık depremi"
    assert N.team_tags(t2, ix2, "fenerbahce") == {"galatasaray": ["sakat"], "fenerbahce": []}


@pytest.mark.parametrize("text,tags", [
    ("Galatasaray'ın yıldızı Victor Osimhen, ameliyat edildi", ["sakat"]),
    ("Yıldız oyuncu 6-8 hafta yok", ["sakat"]),
    ("Osimhen maç kadrosunda yok", ["kadro"]),
    ("Kaptan derbide forma giyemeyecek", ["kadro"]),
    ("Ameliyathane değil saha: takım antrenmanda", ["sakat"]),   # bilinen sınır: kök eşleşmesi (belgelendi)
    ("Hafta sonu maç yok", []),
])
def test_absence_tags(text, tags):
    assert N.tag(text) == tags


def test_same_story_and_cross_source_dedupe(ix2):
    a = "Beşiktaş'ta sarı kart gören Orkun Kökçü cezalı duruma düştü!"
    b = "Beşiktaş'ta Orkun Kökçü cezalı duruma düştü!"
    assert N.same_story(a, b)
    assert not N.same_story(a, "Beşiktaş milli araya 3 puanla girdi")
    assert not N.same_story("Galatasaray haber 1", "Galatasaray haber 2")     # kısa başlık: yalnız birebir
    items = [N.Item(a, "https://example.com/1", "A Spor", NOW - timedelta(hours=2)),
             N.Item(b, "https://example.com/2", "Fotomaç", NOW - timedelta(hours=3))]
    rows = N.assign(items, ix2, NOW)["besiktas"]["items"]
    assert len(rows) == 1 and rows[0]["source"] == "A Spor"


def test_coach_change_only_for_subject_team(ix2):
    it = N.Item("Fenerbahçe maçı öncesi Çorum FK'da teknik direktör istifa etti", "https://example.com/t", "x",
                NOW - timedelta(days=2))
    out = N.assign([it], ix2, NOW)
    assert out["corum"]["coach_change"] is True
    assert out["fenerbahce"]["coach_change"] is False
