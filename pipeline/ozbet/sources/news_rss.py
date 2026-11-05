"""Haber Toplama: herkese açık RSS/Atom akışlarından takım haberleri (ek bağımlılık yok, LLM yok).

Akış:
  1. Genel spor akışlarını çek (FEEDS) + öncelikli lig takımları için kulüp akışları (TEAM_FEEDS, en fazla 30).
  2. Her haberin başlık + özetinde günün maçlarındaki takım adlarını ara (kelime sınırı + belirsiz ad kuralları).
  3. Başlık + özetten açıklanabilir anahtar kelime kurallarıyla etiket çıkar (sakat, ceza, td, kadro, transfer).
  4. Takım başına son 72 saatten en fazla 6 haber; son 7 günde başlığında takım geçen "td" haberi → coach_change.

JSON'a yalnızca başlık, bağlantı, kaynak adı, yayın zamanı ve etiketler yazılır; özet sadece etiketleme ve
eşleme için bellekte kullanılır. Kaynak listesi ve gerekçeler: docs/NEWS_SOURCES.md
"""
from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.entities import name2codepoint

from .. import config
from ..teams import ALIASES, _ascii, canonical, normalize, team_key, variant
from .base import now_iso

log = logging.getLogger("ozbet.news")

TTL = 2 * 3600          # akış önbelleği: 2 saat
WINDOW_H = 72           # gösterilecek haberler
COACH_WINDOW_D = 7      # td sinyali
PER_TEAM = 6
MAX_TEAM_FEEDS = 30

# (id, ad, url, dil) — doğrulama durumu docs/NEWS_SOURCES.md'de
FEEDS: list[tuple[str, str, str, str]] = [
    ("aspor_futbol", "A Spor", "https://www.aspor.com.tr/rss/futbol.xml", "tr"),
    ("aspor_superlig", "A Spor", "https://www.aspor.com.tr/rss/spor-toto-super-lig.xml", "tr"),
    ("fotomac_superlig", "Fotomaç", "https://www.fotomac.com.tr/rss/superlig.xml", "tr"),
    ("ntvspor_futbol", "NTV Spor", "https://www.ntvspor.net/rss/kategori/futbol", "tr"),
    ("ntvspor_dunya", "NTV Spor", "https://www.ntvspor.net/rss/kategori/dunyadan-futbol", "tr"),
    ("trthaber_spor", "TRT Haber", "https://www.trthaber.com/spor_articles.rss", "tr"),
    ("aa_spor", "AA", "https://www.aa.com.tr/tr/rss/default?cat=spor", "tr"),
    ("haberturk_spor", "Habertürk", "https://www.haberturk.com/rss/spor.xml", "tr"),
    ("espn_soccer", "ESPN", "https://www.espn.com/espn/rss/soccer/news", "en"),
    ("sky_football", "Sky Sports", "https://www.skysports.com/rss/11095", "en"),
    ("bbc_football", "BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml", "en"),
    ("guardian_football", "The Guardian", "https://www.theguardian.com/football/rss", "en"),
]

# Kulüp akışları (yayıncıların kendi RSS sayfalarında listelenen adresler). Kanonik ad → (kaynak, url)
_AS = "https://www.aspor.com.tr/rss/{}.xml"
_FM = "https://www.fotomac.com.tr/rss/{}.xml"
TEAM_FEEDS: dict[str, tuple[str, str]] = {
    "Galatasaray": ("A Spor", _AS.format("galatasaray")),
    "Fenerbahçe": ("A Spor", _AS.format("fenerbahce")),
    "Beşiktaş": ("A Spor", _AS.format("besiktas")),
    "Trabzonspor": ("A Spor", _AS.format("trabzonspor")),
    "Başakşehir": ("A Spor", _AS.format("basaksehir")),
    "Alanyaspor": ("A Spor", _AS.format("alanyaspor")),
    "Amedspor": ("A Spor", _AS.format("amed-sportif-faaliyetler")),
    "Çaykur Rizespor": ("A Spor", _AS.format("rizespor")),
    "Çorum FK": ("A Spor", _AS.format("corum-fk")),
    "Erzurumspor": ("A Spor", _AS.format("erzurumspor")),
    "Eyüpspor": ("A Spor", _AS.format("eyupspor")),
    "Gaziantep FK": ("A Spor", _AS.format("gaziantep")),
    "Gençlerbirliği": ("A Spor", _AS.format("genclerbirligi")),
    "Göztepe": ("A Spor", _AS.format("goztepe")),
    "Kasımpaşa": ("A Spor", _AS.format("kasimpasa")),
    "Konyaspor": ("A Spor", _AS.format("konyaspor")),
    "Kocaelispor": ("A Spor", _AS.format("kocaelispor")),
    "Samsunspor": ("A Spor", _AS.format("samsunspor")),
    "Antalyaspor": ("Fotomaç", _FM.format("antalyaspor")),
    "Kayserispor": ("Fotomaç", _FM.format("kayserispor")),
    "Fatih Karagümrük": ("Fotomaç", _FM.format("karagumruk")),
    "Sivasspor": ("Fotomaç", _FM.format("sivasspor")),
    "Ankaragücü": ("Fotomaç", _FM.format("ankaragucu")),
}


# ---------------- ayrıştırma ----------------
@dataclass
class Item:
    title: str
    url: str
    source: str
    published: datetime | None
    summary: str = ""          # yalnızca etiketleme/eşleme için; JSON'a yazılmaz
    team_hint: str | None = None   # kulüp akışından geldiyse o takımın anahtarı


_ENTITY = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)([A-Za-z][A-Za-z0-9]*;)?")


def _fix_entities(text: str) -> str:
    """XML'de tanımsız HTML varlıklarını (&nbsp; vb.) sayısala çevirir, çıplak &'yi kaçırır."""
    def rep(m):
        name = (m.group(1) or "")[:-1]
        if name and name in name2codepoint:
            return f"&#{name2codepoint[name]};"
        return "&amp;" + (m.group(1) or "")
    return _ENTITY.sub(rep, text)


def _repair(text: str) -> str:
    """Yarıda kesilmiş akışı son tam <item>/<entry>'den sonra kapatır."""
    for close, tail in (("</item>", "</channel></rss>"), ("</entry>", "</feed>")):
        i = text.rfind(close)
        if i != -1:
            return text[: i + len(close)] + tail
    return text


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _child(el, *names):
    for c in el:
        if _local(c.tag) in names:
            return c
    return None


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.TZ)
    return dt


def _safe_url(u: str) -> str | None:
    u = (u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else None


def parse_feed(text: str, source: str) -> list[Item]:
    """RSS 2.0 ve Atom; ad alanından bağımsız. Bozuk akışta onarım dener, yine olmazsa [] döner."""
    text = _fix_entities(text.lstrip("﻿ \r\n\t"))
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        try:
            root = ET.fromstring(_repair(text))
        except ET.ParseError as e:
            log.info("Akış ayrıştırılamadı (%s): %s", source, e)
            return []
    out: list[Item] = []
    for el in root.iter():
        kind = _local(el.tag)
        if kind == "item":                       # RSS
            link = _text(_child(el, "link"))
            if not link:
                g = _child(el, "guid")
                if g is not None and g.get("isPermaLink", "true") != "false":
                    link = _text(g)
            date_s = _text(_child(el, "pubdate")) or _text(_child(el, "date"))
            summ = _text(_child(el, "description"))
        elif kind == "entry":                    # Atom
            link = ""
            for c in el:
                if _local(c.tag) == "link" and c.get("rel", "alternate") == "alternate":
                    link = c.get("href") or _text(c)
                    break
            date_s = _text(_child(el, "published")) or _text(_child(el, "updated"))
            summ = _text(_child(el, "summary")) or _text(_child(el, "content"))
        else:
            continue
        title = strip_html(_text(_child(el, "title")))[:200]
        url = _safe_url(html.unescape(link))
        if not title or not url:
            continue
        out.append(Item(title, url, source, parse_date(date_s), strip_html(summ)[:1500]))
    return out


# ---------------- takım eşleme ----------------
def text_norm(s: str) -> str:
    """Eşleme için metin: ASCII küçük harf, noktalama → boşluk. (Gürültü kelimeleri SİLİNMEZ: 'AS Roma' korunur.)"""
    s = _ascii(s).replace("'", " ").replace("’", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return f" {re.sub(r'\s+', ' ', s).strip()} "


# Tek başına geçtiğinde başka anlama da gelen adlar: şehir, sıradan kelime veya birden çok kulübün ortak parçası.
AMBIGUOUS = {
    "roma", "inter", "milan", "city", "united", "real", "paris", "athletic", "sporting", "lyon", "nice", "lens",
    "como", "porto", "napoli", "nottingham", "frankfurt", "leipzig", "bodrum", "manisa", "hatay", "corum", "igdir",
    "erzurum", "gaziantep", "rayo", "celta", "torino", "genoa", "parma", "leeds", "wolves", "spurs",
    "racing", "union", "nacional", "national", "olympic", "deportivo", "dynamo", "dinamo", "rapid", "rangers",
    "victoria", "metz", "brest", "angers", "lorient",
}
# Ünlü/kulüp olmayan ama takım adını içeren ifadeler: önce maskelenir, içindeki kısa ad eşleşmez.
BLOCK_PHRASES = [
    "inter miami", "milan cortina", "real madrid", "real betis", "real sociedad", "real valladolid", "real oviedo",
    "real mallorca", "real salt lake", "paris fc", "paris saint germain", "manchester city", "manchester united",
    "athletic bilbao", "atletico madrid", "sporting lizbon", "sporting cp", "sporting lisbon", "sporting kansas city",
    "new york city", "roma open", "inter milan", "inter turku", "milano cortina",
]
# Belirsiz ad bu öneklerden biriyle geçerse kulüp kabul edilir ("AS Roma", "FC Porto").
CLUB_PREFIX = {"as", "ac", "fc", "ss", "ssc", "sc", "afc", "cf", "sl", "sk", "fk", "rc"}
# Yalnız son kelimeyle yedek terim üretirken kullanılmayacak genel kelimeler
GENERIC = {"united", "city", "town", "county", "rovers", "wanderers", "albion", "athletic", "sporting", "real",
           "madrid", "milan", "manchester", "olympique", "eintracht", "borussia", "atletico", "hotspur",
           "belediyespor", "spor", "sports", "football", "calcio", "saint", "germain", "demirspor"}
SAFE_SHORT = {"psg"}
LEAGUE_CONTEXT = {
    "TR1": ["super lig"], "TR2": ["1 lig"], "ENG1": ["premier lig", "premier league"],
    "ESP1": ["la liga", "laliga"], "ITA1": ["serie a"], "GER1": ["bundesliga"], "FRA1": ["ligue 1"],
    "UCL": ["sampiyonlar ligi", "champions league"], "UEL": ["avrupa ligi", "europa league"],
    "UECL": ["konferans ligi", "conference league"],
}


def team_terms(name: str) -> set[str]:
    """Bir takımın metinde aranacak normalize terimleri (kanonik ad + sözlükteki tüm yazımlar)."""
    canon = canonical(name)
    names = {name, canon, *ALIASES.get(canon, [])}
    terms = {normalize(n) for n in names}
    terms = {t for t in terms if t and (len(t) >= 4 or t in SAFE_SHORT)}
    if canon not in ALIASES:   # sözlükte yoksa: ayırt edici son kelime yedeği ("Ankara Keçiörengücü" → keciorengucu)
        toks = normalize(canon).split()
        if len(toks) > 1 and len(toks[-1]) >= 7 and toks[-1] not in GENERIC | AMBIGUOUS:
            terms.add(toks[-1])
    return terms


@dataclass
class TeamIndex:
    """Günün A takımları için terim → takım anahtarı dizini."""
    terms: dict[str, str] = field(default_factory=dict)      # terim → team_key
    names: dict[str, str] = field(default_factory=dict)      # team_key → görünen ad
    opponent: dict[str, str] = field(default_factory=dict)   # team_key → rakip team_key
    league: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_fixtures(cls, fixtures) -> "TeamIndex":
        ix = cls()
        for f in fixtures:
            if not config.LEAGUE_BY_ID.get(f.league_id or ""):   # yalnız tanımlı ligler (bilinmeyen liglerde
                continue                                        # sıradan kelime adlı takımlar yanlış pozitif üretir)
            if variant(f.home) or variant(f.away):   # U19/kadın/rezerv: haber eşleme yapılmaz
                continue
            hk, ak = team_key(f.home), team_key(f.away)
            for k, nm, opp in ((hk, f.home, ak), (ak, f.away, hk)):
                ix.names.setdefault(k, nm)
                ix.opponent.setdefault(k, opp)
                ix.league.setdefault(k, f.league_id)
                for t in team_terms(nm):
                    ix.terms.setdefault(t, k)
        return ix

    def match(self, text: str) -> set[str]:
        """Metinde geçen takım anahtarları. Uzun ifadeler önce eşleşir ve maskelenir."""
        s = text_norm(text)
        hits: dict[str, list[str]] = {}       # team_key → eşleşen terimler
        phrases = sorted(set(self.terms) | set(BLOCK_PHRASES), key=lambda t: (-len(t), t))
        for ph in phrases:
            pat = f" {ph} "
            if pat not in s:
                continue
            for mt in re.finditer(re.escape(pat), s):
                pre = s[:mt.start()].split()[-1:] or [""]
                if ph in self.terms:
                    hits.setdefault(self.terms[ph], []).append(ph if pre[0] not in CLUB_PREFIX else f"{pre[0]} {ph}")
            s = s.replace(pat, " " + "#" * len(ph) + " ")   # maske (kelime sınırları korunur)
        out = set()
        for k, ts in hits.items():
            if any(" " in t or t not in AMBIGUOUS for t in ts):
                out.add(k)
        # belirsiz tek kelimeler: rakip veya lig bağlamı varsa kabul
        for k, ts in hits.items():
            if k in out:
                continue
            ctx = text_norm(text)
            if self.opponent.get(k) in hits or any(f" {w} " in ctx for w in LEAGUE_CONTEXT.get(self.league.get(k) or "", [])):
                out.add(k)
        return out


# Futbol dışı / altyapı / kadın takımı haberleri: aynı kulüp adı geçse de A takımına yazılmaz.
NON_FOOTBALL = re.compile(
    r" (?:basketbol\w*|basketball|voleybol\w*|volleyball|hentbol\w*|handball|euroleague|eurocup|nba|wnba|"
    r"beko|sultanlar ligi|kadin futbol\w*|kadinlar|women s|wsl|u1[5-9]|u2[0-3]|genclik ligi|futsal|e spor\w*|esports) ")


def is_football(title: str, summary: str = "") -> bool:
    return not NON_FOOTBALL.search(text_norm(title + " . " + summary[:400]))


# ---------------- etiketleme ----------------
def _rx(*pats):
    return re.compile("|".join(f"(?:{p})" for p in pats))


# Kurallar ASCII'ye çevrilmiş küçük harfli metne uygulanır (ı→i, ş→s, ğ→g ...). \b kelime başı; Türkçe ekler için kök.
TAG_RULES: dict[str, re.Pattern] = {
    "sakat": _rx(r"\bsakat(?!at)\w*", r"\binjur\w*", r"\bruled out\b", r"\bsidelined\b", r"\bhamstring\b"),
    "ceza": _rx(r"\bcezal\w*", r"\bkirmizi kart\w*", r"\bmen cezas\w*", r"\bsuspen(?:ded|sion)\b",
                r"\bban(?:ned)?\b", r"\bpfdk\b"),
    "kadro": _rx(r"\bkadroya alinmad\w*", r"\bkadro disi\w*", r"\bkadrodan cikar\w*", r"\brotasyon\w*",
                 r"\bkamp kadro\w*", r"\brotation\b", r"\brested\b"),
    "transfer": _rx(r"\btransfer\w*", r"\bbonservis\w*", r"\bkiralik\b", r"\bsign(?:s|ed|ing)\b", r"\bloan\b"),
}
_TD_ROLE = _rx(r"\bteknik direktor\w*", r"\bteknik adam\w*", r"\bhoca\w*", r"\bmanager\b", r"\bhead coach\b",
               r"\bcoach\b", r"\bboss\b")
_TD_CHANGE = _rx(r"\bistifa\w*", r"\bgorevden alin\w*", r"\byollar\w* ayir\w*", r"\bayrild\w*", r"\bveda\w*",
                 r"\bgetiril\w*", r"\batand\w*", r"\bsacked\b", r"\bappointed\b",
                 r"\bresign\w*", r"\bdismissed\b", r"\bparted? ways\b", r"\bnew (?:manager|head coach|boss)\b")
_TD_STRONG = _rx(r"\bgorevden alindi\w*", r"\bsacked\b", r"\byeni (?:teknik direktor|hoca)\w*")


def tag(text: str) -> list[str]:
    """Açıklanabilir anahtar kelime etiketleri. 'td' yalnızca rol + değişim kelimesi birlikte geçerse."""
    s = text_norm(text)
    tags = [t for t, rx in TAG_RULES.items() if rx.search(s)]
    if _TD_STRONG.search(s) or (_TD_ROLE.search(s) and _TD_CHANGE.search(s)):
        tags.insert(0, "td")
    order = ["sakat", "ceza", "td", "kadro", "transfer"]
    return sorted(tags, key=order.index)


# ---------------- toplama ----------------
def _dedupe_key(it: Item) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii(it.title))[:80]


def assign(items: list[Item], ix: TeamIndex, now: datetime) -> dict[str, dict]:
    """team_key → {"items":[...72s, en çok 6], "coach_change": bool}"""
    cutoff, coach_cut = now - timedelta(hours=WINDOW_H), now - timedelta(days=COACH_WINDOW_D)
    future = now + timedelta(hours=1)
    per: dict[str, list[tuple[Item, list[str]]]] = {}
    coach: set[str] = set()
    for it in items:
        if it.published is None or not (coach_cut <= it.published <= future):
            continue
        if not is_football(it.title, it.summary):
            continue
        teams = ix.match(it.title + " . " + it.summary)
        if it.team_hint:
            teams.add(it.team_hint)
        if not teams:
            continue
        tags = tag(it.title + " . " + it.summary)
        if "td" in tags:
            in_title = ix.match(it.title) | ({it.team_hint} if it.team_hint else set())
            coach |= in_title
        if it.published < cutoff:
            continue
        for k in teams:
            per.setdefault(k, []).append((it, tags))
    out = {}
    for k in set(per) | coach:
        seen_u, seen_t, rows = set(), set(), []
        for it, tags in sorted(per.get(k, []), key=lambda p: p[0].published, reverse=True):
            dk = _dedupe_key(it)
            if it.url in seen_u or dk in seen_t:
                continue
            seen_u.add(it.url); seen_t.add(dk)
            rows.append({"title": it.title, "url": it.url, "source": it.source,
                         "published": it.published.astimezone(config.TZ).isoformat(timespec="seconds"),
                         "tags": tags})
            if len(rows) >= PER_TEAM:
                break
        out[k] = {"items": rows, "coach_change": k in coach}
    return out


def team_feed_targets(fixtures, limit: int = MAX_TEAM_FEEDS) -> list[tuple[str, str, str]]:
    """(team_key, kaynak, url) — öncelikli lig sırasıyla, en fazla `limit` takım."""
    def prio(f):
        lg = config.LEAGUE_BY_ID.get(f.league_id or "")
        return (lg.priority if lg else 99, f.kickoff)
    out, seen = [], set()
    for f in sorted(fixtures, key=prio):
        if not config.LEAGUE_BY_ID.get(f.league_id or ""):
            continue
        for nm in (f.home, f.away):
            if variant(nm):
                continue
            k, c = team_key(nm), canonical(nm)
            if k in seen or c not in TEAM_FEEDS:
                continue
            seen.add(k)
            out.append((k, *TEAM_FEEDS[c]))
            if len(out) >= limit:
                return out
    return out


def collect(client, fixtures, now: datetime | None = None) -> dict:
    """Ana giriş. Dönüş: {"teams": {team_key: {...}}, "fetched_at", "feeds_ok", "feeds_failed":[...]}"""
    now = now or datetime.now(config.TZ)
    ix = TeamIndex.from_fixtures(fixtures)
    items: list[Item] = []
    ok, failed = 0, []
    if not ix.names:
        return {"teams": {}, "fetched_at": now_iso(), "feeds_ok": 0, "feeds_failed": []}
    jobs = [(fid, name, url, None) for fid, name, url, _ in FEEDS]
    jobs += [(f"team:{k}", name, url, k) for k, name, url in team_feed_targets(fixtures)]
    for fid, name, url, hint in jobs:
        try:
            got = parse_feed(client.get(url, ttl=TTL), name)
            if not got:
                failed.append(f"{fid}(boş)")
                continue
            for it in got:
                it.team_hint = hint
            items += got
            ok += 1
        except Exception as e:  # noqa: BLE001 — tek akış diğerlerini durdurmasın
            failed.append(f"{fid}({type(e).__name__})")
    if ok == 0:
        raise RuntimeError("Hiçbir haber akışı okunamadı: " + ", ".join(failed[:8]))
    return {"teams": assign(items, ix, now), "fetched_at": now_iso(), "feeds_ok": ok, "feeds_failed": failed}


def for_match(home: str, away: str, rss: dict | None) -> dict | None:
    """Maça iliştirilecek "news" bloğu; iki tarafta da haber yoksa None."""
    teams = (rss or {}).get("teams") or {}
    h = (teams.get(team_key(home)) or {}).get("items") or []
    a = (teams.get(team_key(away)) or {}).get("items") or []
    if not h and not a:
        return None
    return {"home": h, "away": a, "fetched_at": rss.get("fetched_at")}


def coach_change_keys(rss: dict | None) -> set[str]:
    return {k for k, v in ((rss or {}).get("teams") or {}).items() if v.get("coach_change")}
