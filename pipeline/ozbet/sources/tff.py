"""TFF (tff.org): 1. Lig (TR2) güncel sezon sonuçları ve Süper Lig (TR1) hakem atamaları.

Kaynak: TFF (tff.org). Kullanım şartı: ticari olmayan kullanım ve kaynak gösterme (README'ye bakın).

Sayfalar (WebFetch ile görülen yapı, 6 Kasım 2026):
  Hafta sayfası  Default.aspx?pageID=142&hafta=N  (1. Lig)   /  pageID=198&hafta=N (Süper Lig)
    - hafta bağlantıları: href "...pageID=142&hafta=N#mac..." ; güncel hafta bağlantısız "13.Hafta" metni
    - maç satırı: "30.10.2026 20:00" | ev takımı (kulupID bağlantısı) | "3 - 2" (macId bağlantısı) | deplasman
  Maç sayfası    Default.aspx?pageId=29&macId=N
    - "14.08.2026 - 21:30", "BATUHAN KOLAK(Hakem)", goller "OYUNCU,53.dk (F)", takım başına ayrı liste

Ayrıştırıcı esnektir: önce `a[href*=macId]` bağlantılarının bulunduğu tablo satırı / ortak üst öğe okunur,
olmazsa düz metin üzerinde "tarih ev skor dep" deseni aranır. Kurallar: robots.txt kontrolü açık, istekler arası
en az 5 sn, çalıştırma başına en fazla MAX_MATCH_PAGES maç sayfası (önbellekten gelenler sayılmaz), biten maç
sayfaları kalıcı önbellekte (biten maç değişmez).
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Iterable

from bs4 import BeautifulSoup

from ..http import PoliteClient
from rapidfuzz import fuzz

from ..teams import TeamMatcher, canonical, normalize, similar, team_key

log = logging.getLogger("ozbet.tff")

BASE = "https://www.tff.org/Default.aspx"
PAGE_TR2 = 142
PAGE_TR1 = 198
SOURCE = "tff.org"
ATTRIBUTION = "Kaynak: TFF (tff.org)"
MIN_DELAY_S = 5.0
MAX_MATCH_PAGES = 40
HT_WEEKS = 2                 # İY skoru (maç sayfasından) yalnızca son 2 hafta için
REF_WEEKS_BACK = 6           # hakem için güncel haftadan geriye en fazla bu kadar hafta
TTL_FINISHED = 400 * 86400   # biten maç / eski hafta: pratikte kalıcı
TTL_RECENT = 6 * 3600        # güncel/son haftalar, oynanmamış maçlar

_MAC_RX = re.compile(r"macId=(\d+)", re.I)
_HAFTA_RX = re.compile(r"hafta=(\d+)", re.I)
_SCORE_RX = re.compile(r"^\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*$")
_DATE_RX = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_CUR_WEEK_RX = re.compile(r"(\d{1,2})\s*\.\s*Hafta", re.I)
_REF_RX = re.compile(r"([A-ZÇĞİÖŞÜÂÎÛa-zçğıöşüâîû][^()\n<>]{2,60}?)\s*\(\s*Hakem\s*\)")
_GOAL_RX = re.compile(r",\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*\.?\s*dk", re.I)
_NOISE_SUFFIX = re.compile(
    r"\b(A\.?\s?Ş\.?|FUTBOL KULÜBÜ|FUTBOL KULUBU|SPOR KULÜBÜ|FUTBOL A\.?\s?Ş\.?|KULÜBÜ)\s*$", re.I)

# Teşhis: son okunan hafta ve maç sayfası (run.py bunları .cache/debug/tff-*.txt olarak yazar)
SAMPLES: dict[str, tuple[str, int, str]] = {}


# ---------------------------------------------------------------- istemci
def tff_client(client: PoliteClient) -> PoliteClient:
    """tff.org için ≥5 sn gecikmeli ayrı istemci (aynı önbellek dizini). Gecikmesi 0 olan istemci (çevrimdışı mod,
    test) olduğu gibi kullanılır."""
    if getattr(client, "delay", 1) == 0:
        return client
    c = getattr(client, "_tff", None)
    if c is None:
        c = PoliteClient(cache_dir=client.cache_dir, delay=max(MIN_DELAY_S, client.delay))
        client._tff = c  # type: ignore[attr-defined]
    return c


def week_url(page_id: int, week: int | None = None) -> str:
    return f"{BASE}?pageID={page_id}" + (f"&hafta={week}" if week else "")


def match_url(mac_id: str) -> str:
    return f"{BASE}?pageId=29&macId={mac_id}"


def _cached(client, url: str, ttl: float) -> bool:
    try:
        import time
        p = client._cache_path(url, None)
        return p.exists() and time.time() - p.stat().st_mtime < ttl
    except Exception:  # noqa: BLE001
        return False


class Budget:
    """Çalıştırma başına ağdan çekilen maç sayfası sınırı (önbellek isabetleri sayılmaz)."""

    def __init__(self, n: int = MAX_MATCH_PAGES):
        self.left = n

    def fetch(self, client, mac_id: str, ttl: float) -> str | None:
        url = match_url(mac_id)
        if not _cached(client, url, ttl):
            if self.left <= 0:
                return None
            self.left -= 1
        html = client.get(url, ttl=ttl, check_robots=True)
        SAMPLES["mac"] = (url, 200, html)
        return html


# ---------------------------------------------------------------- yardımcılar
def clean_name(raw: str) -> str:
    """'GALATASARAY A.Ş.' → 'Galatasaray'. Sponsor önekleri kalır (kaynak içinde tutarlı; eşleme bulanık)."""
    s = re.sub(r"\s+", " ", raw or "").strip(" -")
    for _ in range(2):
        s = _NOISE_SUFFIX.sub("", s).strip(" .-")
    if s.isupper():
        s = " ".join(_tr_title(w) for w in s.split(" "))
    return s


def _tr_title(w: str) -> str:
    if not w:
        return w
    low = w.replace("I", "ı").replace("İ", "i").lower()
    head = {"i": "İ", "ı": "I"}.get(low[0], low[0].upper())
    return head + low[1:]


def _parse_date(text: str) -> date | None:
    m = _DATE_RX.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def season_code(d: date) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


# ---------------------------------------------------------------- hafta sayfası
def parse_weeks(html: str) -> tuple[list[int], int | None]:
    """(sayfadaki hafta numaraları, güncel hafta). Güncel hafta: bağlantısız 'N.Hafta' metni ya da URL'deki hafta."""
    weeks = sorted({int(w) for w in _HAFTA_RX.findall(html) if 0 < int(w) <= 60})
    soup = BeautifulSoup(html, "html.parser")
    cur = None
    for node in soup.find_all(string=_CUR_WEEK_RX):
        if node.find_parent("a") is None:
            cur = int(_CUR_WEEK_RX.search(node).group(1))
            break
    if cur and cur not in weeks:
        weeks = sorted({*weeks, cur})
    return weeks, cur


def _team_texts(row) -> list[str]:
    """Satırdaki takım adı adayları: önce macId/hafta dışı bağlantılar, yoksa yaprak hücre metinleri."""
    def ok(t: str) -> bool:
        return bool(t) and not _SCORE_RX.match(t) and not _DATE_RX.search(t) and \
            t.lower() not in ("detaylar", "detay", "-") and not re.fullmatch(r"[\d:.\s«»-]+", t) and \
            not re.search(r"\bhafta\b", t, re.I) and len(t) >= 2
    links = [x.get_text(" ", strip=True) for x in row.find_all("a")
             if not re.search(r"macId|hafta=", x.get("href", ""), re.I)]
    teams = [t for t in links if ok(t)]
    if len(teams) >= 2:
        return teams
    leaves = [c.get_text(" ", strip=True) for c in row.find_all(["td", "span", "div", "b", "strong", "p"])
              if not c.find(["td", "span", "div", "b", "strong", "p", "a"])]
    return [t for t in leaves if ok(t)]


def _row_of(a, mid: str):
    """Maç satırı: bu macId dışında macId içermeyen ve en az iki takım adı barındıran en yakın üst öğe."""
    p = a.parent
    for _ in range(6):
        if p is None:
            break
        ids = {m for x in p.find_all("a") for m in _MAC_RX.findall(x.get("href", ""))}
        if ids - {mid}:
            return None
        if len(_team_texts(p)) >= 2:
            return p
        p = p.parent
    return None


def parse_week(html: str, page_date_hint: date | None = None) -> list[dict]:
    """Hafta sayfasındaki maçlar: [{mac_id, date|None, home, away, hg|None, ag|None}] (macId'ye göre tekil)."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, dict] = {}
    for a in soup.select("a[href*=macId], a[href*=macid], a[href*=MacId]"):
        m = _MAC_RX.search(a.get("href", ""))
        if not m:
            continue
        mid = m.group(1)
        row = _row_of(a, mid)
        if row is None:
            continue
        teams = _team_texts(row)
        if len(teams) < 2:
            continue
        # skor: macId bağlantılarından birinin metni (Detaylar değil)
        hg = ag = None
        for x in row.find_all("a"):
            if _MAC_RX.search(x.get("href", "")):
                sm = _SCORE_RX.match(x.get_text(" ", strip=True))
                if sm:
                    hg, ag = int(sm.group(1)), int(sm.group(2))
                    break
        if hg is None:
            for t in row.find_all(string=_SCORE_RX):
                sm = _SCORE_RX.match(t)
                hg, ag = int(sm.group(1)), int(sm.group(2))
                break
        d = _parse_date(row.get_text(" ", strip=True))
        rec = out.get(mid)
        if rec is None or (rec["date"] is None and d):
            out[mid] = {"mac_id": mid, "date": d, "home": teams[0], "away": teams[1], "hg": hg, "ag": ag}
    return list(out.values())


# ---------------------------------------------------------------- maç sayfası
def _text_lines(soup) -> list[str]:
    return [t.strip() for t in soup.get_text("\n").split("\n") if t.strip()]


def parse_match(html: str) -> dict:
    """{date, referee, home_goals:[dk], away_goals:[dk], ht:[h,a]|None}. Gol dakikası '45+2' → 45.5 (ilk yarı)."""
    soup = BeautifulSoup(html, "html.parser")
    lines = _text_lines(soup)
    text = "\n".join(lines)
    out: dict = {"date": None, "referee": None, "home_goals": None, "away_goals": None, "ht": None}
    m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})\s*-?\s*\d{1,2}:\d{2}", text) or _DATE_RX.search(text)
    if m:
        out["date"] = _parse_date(m.group(0))
    for ln in lines:
        rm = _REF_RX.search(ln)
        if rm and "Yardımcı" not in ln[:rm.end()] and "Dördüncü" not in ln[:rm.end()]:
            out["referee"] = re.sub(r"\s+", " ", rm.group(1)).strip(" :-")
            break
    # goller: id/sınıfında "gol" geçen kapsayıcılar (ev, dep sırasıyla)
    found = [el for el in soup.find_all(attrs={"id": re.compile("gol", re.I)}) +
             soup.find_all(class_=re.compile("gol", re.I)) if _goal_minutes(el.get_text("\n"))]
    found = list(dict.fromkeys(found))
    inner = [el for el in found if not any(o is not el and el in o.parents for o in found)]
    inner = [el for el in inner if not any(o is not el and o in el.parents for o in inner)]
    if len(inner) == 2:
        out["home_goals"], out["away_goals"] = (_goal_minutes(el.get_text("\n")) for el in inner)
    out["_all_goals"] = _goal_minutes(text)
    return out


def _goal_minutes(text: str) -> list[float]:
    res = []
    for line in text.split("\n"):
        if re.search(r"kart", line, re.I):
            continue
        for gm in _GOAL_RX.finditer(line):
            base = int(gm.group(1))
            res.append(base + 0.5 if gm.group(2) else float(base))
    return res


def ht_from_goals(home_goals, away_goals, hg=None, ag=None, all_goals=None):
    """İY skoru gol dakikalarından. Takım listeleri yoksa belge sırasındaki tüm goller (önce ev) FT skoruna göre
    bölünür; sayı tutmazsa None."""
    if home_goals is None or away_goals is None:
        if all_goals is None or hg is None or ag is None or len(all_goals) != hg + ag:
            return None
        home_goals, away_goals = all_goals[:hg], all_goals[hg:]
    if hg is not None and ag is not None and (len(home_goals) != hg or len(away_goals) != ag):
        return None
    first = lambda xs: sum(1 for x in xs if x <= 45.5)  # noqa: E731
    return [first(home_goals), first(away_goals)]


# ---------------------------------------------------------------- hafta gezinme
def _week_page(client, page_id: int, week: int | None, cur: int | None) -> str:
    old = cur is not None and week is not None and week < cur - 2
    url = week_url(page_id, week)
    html = client.get(url, ttl=TTL_FINISHED if old else TTL_RECENT, check_robots=True)
    SAMPLES.setdefault("hafta", (url, 200, html))
    return html


def _collect(client, page_id: int, weeks_wanted, cur) -> dict[int, list[dict]]:
    by_week = {}
    for w in weeks_wanted:
        try:
            by_week[w] = parse_week(_week_page(client, page_id, w, cur))
        except Exception as e:  # noqa: BLE001
            if w == cur:
                raise
            log.info("tff hafta %s/%s alınamadı: %s", page_id, w, e)
    return by_week


def tr2_history(client: PoliteClient, today: date, budget: Budget | None = None) -> list[dict]:
    """1. Lig güncel sezon oynanmış maçları, football_data.history() satır biçiminde."""
    c = tff_client(client)
    budget = budget or Budget()
    first = c.get(week_url(PAGE_TR2), ttl=TTL_RECENT, check_robots=True)
    SAMPLES["hafta"] = (week_url(PAGE_TR2), 200, first)
    weeks, cur = parse_weeks(first)
    if not weeks:
        return []
    cur = cur or max(weeks)
    wanted = [w for w in weeks if w <= cur]
    by_week = _collect(c, PAGE_TR2, wanted, cur)
    rows, seen = [], set()
    for w in sorted(by_week, reverse=True):
        for mt in by_week[w]:
            if mt["mac_id"] in seen or mt["hg"] is None:
                continue
            recent = w > cur - HT_WEEKS
            d, ht = mt["date"], None
            if (d is None or recent):
                html = budget.fetch(c, mt["mac_id"], TTL_FINISHED)
                if html:
                    pm = parse_match(html)
                    d = d or pm["date"]
                    if recent:
                        ht = ht_from_goals(pm["home_goals"], pm["away_goals"], mt["hg"], mt["ag"], pm["_all_goals"])
            if d is None or d > today:
                continue
            seen.add(mt["mac_id"])
            rows.append({"date": d, "season": season_code(d), "home": clean_name(mt["home"]),
                         "away": clean_name(mt["away"]), "hg": mt["hg"], "ag": mt["ag"],
                         "hthg": ht[0] if ht else None, "htag": ht[1] if ht else None,
                         "odds_open": {}, "odds_close": {}, "src": SOURCE, "tff_id": mt["mac_id"]})
    rows.sort(key=lambda r: (r["date"], r["home"]))
    return rows


def tr1_referees(client: PoliteClient, today: date, budget: Budget | None = None,
                 weeks_back: int = REF_WEEKS_BACK) -> list[dict]:
    """Süper Lig hakemleri: güncel hafta (oynanmamış maçlar dahil) ve önceki haftalar.
    [{date, home, away, referee, played}] — en yeni haftadan geriye; bütçe bitince durur."""
    c = tff_client(client)
    budget = budget or Budget()
    first = c.get(week_url(PAGE_TR1), ttl=TTL_RECENT, check_robots=True)
    weeks, cur = parse_weeks(first)
    if not weeks:
        return []
    cur = cur or max(weeks)
    wanted = [w for w in sorted(weeks, reverse=True) if cur - weeks_back <= w <= cur + 1]
    out = []
    for w in wanted:
        try:
            matches = parse_week(_week_page(c, PAGE_TR1, w, cur))
        except Exception as e:  # noqa: BLE001
            if w == cur:
                raise
            log.info("tff TR1 hafta %s: %s", w, e)
            continue
        for mt in matches:
            played = mt["hg"] is not None and (mt["date"] is None or mt["date"] <= today)
            html = budget.fetch(c, mt["mac_id"], TTL_FINISHED if played and mt["date"] and
                                mt["date"] < today - timedelta(days=1) else TTL_RECENT)
            if not html:
                continue
            pm = parse_match(html)
            d = mt["date"] or pm["date"]
            if pm["referee"] and d:
                out.append({"date": d, "home": clean_name(mt["home"]), "away": clean_name(mt["away"]),
                            "referee": pm["referee"], "played": played})
        if budget.left <= 0:
            break
    return out


# ---------------------------------------------------------------- zenginleştirme
def referee_map(refs: Iterable[dict]) -> dict[tuple[str, str, str], str]:
    return {(r["date"].isoformat(), team_key(r["home"]), team_key(r["away"])): r["referee"] for r in refs}


def _find(refs: list[dict], d: date, home: str, away: str) -> str | None:
    days = {d + timedelta(days=k) for k in (-1, 0, 1)}
    hk, ak = team_key(home), team_key(away)
    cands = [r for r in refs if r["date"] in days]
    for r in cands:
        if team_key(r["home"]) == hk and team_key(r["away"]) == ak:
            return r["referee"]
    for r in cands:
        if similar(home, r["home"]) and similar(away, r["away"]):
            return r["referee"]
    loose = [r for r in cands if _loose(home, r["home"]) and _loose(away, r["away"])]
    if len(loose) == 1:
        return loose[0]["referee"]
    if cands:
        tm = TeamMatcher([r["home"] for r in cands] + [r["away"] for r in cands], threshold=80)
        mh, ma = tm.match(home), tm.match(away)
        for r in cands:
            if mh == r["home"] and ma == r["away"]:
                return r["referee"]
    return None


def _loose(a: str, b: str) -> bool:
    """Aynı gün ±1 içinde gevşek eşleşme: sponsor önekli/kısaltmalı adlar ('Arca Çorum FK' ~ 'Corum')."""
    if similar(a, b):
        return True
    na, nb = normalize(canonical(a)), normalize(canonical(b))
    return bool(na and nb) and fuzz.token_set_ratio(na, nb) >= 90


def attach_referees_history(rows: list[dict], refs: list[dict]) -> int:
    """TR1 geçmiş satırlarına (referee boşsa) hakem ekler; eklenen sayı."""
    n = 0
    if not refs:
        return 0
    lo = min(r["date"] for r in refs) - timedelta(days=1)
    for row in rows:
        if row.get("referee") or row["date"] < lo:
            continue
        ref = _find(refs, row["date"], row["home"], row["away"])
        if ref:
            row["referee"] = ref
            n += 1
    return n


def attach_referees_fixtures(fixtures, refs: list[dict], league_id: str = "TR1") -> int:
    n = 0
    for f in fixtures:
        if f.league_id != league_id or f.extra.get("referee"):
            continue
        ref = _find(refs, f.kickoff.date(), f.home, f.away)
        if ref:
            f.extra["referee"] = ref
            f.extra["referee_source"] = ATTRIBUTION
            n += 1
    return n
