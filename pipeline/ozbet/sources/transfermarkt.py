"""Transfermarkt — lig sakatlık ve ceza listeleri.

Not: Site DataDome koruması kullanıyor ve GitHub Actions IP'lerini sıklıkla engelliyor. Engellenirse kaynak
'missing' görünür, akış devam eder.

'Kilit' oyuncu (sezgisel, bkz. docs/research/kadro-etkisi.md): kaleci olmayan, piyasa değeri ligin sakat
listesindeki değerlerin üst çeyreğinde (ve en az 1 mn €) olan, takım başına en çok 2 oyuncu. Eski kural
("takımın sakatları içinde ilk 4, ≥1 mn €") büyük liglerde neredeyse her sakatı kilit sayıyordu.
Satırda tarih bulunursa `since` (sakatlığın başlangıcı) ve `until` (beklenen dönüş) doldurulur; Kadro Ajanı
3 haftadan eski yoklukları indirimli sayar (sonuçlara ve oranlara zaten yansımıştır).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..teams import team_key
from .base import MissingPlayer, TeamNews, now_iso

BASE = "https://www.transfermarkt.com.tr"
LEAGUES = {"TR1": ("super-lig", "TR1"), "ENG1": ("premier-league", "GB1"), "ESP1": ("laliga", "ES1"),
           "ITA1": ("serie-a", "IT1"), "GER1": ("bundesliga", "L1"), "FRA1": ("ligue-1", "FR1")}


def _value(txt: str) -> float:
    t = txt.lower().replace(",", ".")
    m = re.search(r"([\d.]+)\s*(mil|m|bin|k|th)?", t)
    if not m:
        return 0.0
    v = float(m.group(1)) if m.group(1).replace(".", "").isdigit() else 0.0
    return v * (1e6 if (m.group(2) or "").startswith("m") else 1e3 if m.group(2) else 1)


KEY_MIN_VALUE = 1e6       # mutlak alt sınır (€)
KEY_QUANTILE = 0.75       # lig sakat listesinde değer yüzdeliği
KEY_PER_TEAM = 2
_GK = re.compile(r"kaleci|torwart|goalkeeper|keeper", re.I)
_MONTHS = {m: i for i, ms in enumerate([
    ("oca", "jan"), ("şub", "sub", "feb"), ("mar", "mär"), ("nis", "apr"), ("may", "mai"), ("haz", "jun"),
    ("tem", "jul"), ("ağu", "agu", "aug"), ("eyl", "sep"), ("eki", "oct", "okt"), ("kas", "nov"),
    ("ara", "dec", "dez")], 1) for m in ms}
_DATE_NUM = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})\.?\s+([A-Za-zÇĞİÖŞÜçğıöşüä]{3})[a-zçğıöşüä]*\.?\s+(\d{4})\b")


@dataclass
class Absence(MissingPlayer):
    """MissingPlayer + (varsa) tarih/değer bilgisi. Ek alanlar isteğe bağlıdır; Kadro Ajanı getattr ile okur."""
    since: date | None = None      # yokluğun başladığı gün
    until: date | None = None      # beklenen dönüş
    value: float = 0.0             # piyasa değeri (€)
    position: str = ""


def parse_dates(text: str) -> list[date]:
    """Metindeki tarihleri çıkarır: 05.11.2026, 5/11/2026, "5 Kas 2026", "Nov 5, 2026" değil (TR sitesi)."""
    out = []
    for d, m, y in _DATE_NUM.findall(text):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mon, y in _DATE_TXT.findall(text):
        mi = _MONTHS.get(mon.lower())
        if mi:
            try:
                out.append(date(int(y), mi, int(d)))
            except ValueError:
                pass
    return out


def split_dates(dates: list[date], day: date) -> tuple[date | None, date | None]:
    """(since, until): bugüne kadar olan en yeni tarih başlangıç, gelecekteki en yakın tarih dönüş.
    3 yıldan eski tarihler (doğum tarihi vb.) yok sayılır."""
    past = [d for d in dates if day - timedelta(days=3 * 365) <= d <= day]
    fut = [d for d in dates if d > day]
    return (max(past) if past else None), (min(fut) if fut else None)


def parse_injuries(html: str) -> dict[str, list[tuple[str, str, float]]]:
    """Geriye uyumlu: kulüp → [(oyuncu, neden, değer)]."""
    return {club: [(r["name"], r["reason"], r["value"]) for r in rows] for club, rows in parse_rows(html).items()}


def parse_rows(html: str) -> dict[str, list[dict]]:
    """Kulüp → [{"name","reason","value","position","dates":[date...]}]"""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, list] = {}
    for tr in soup.select("#yw1 tbody tr, table.items tbody tr"):
        a = tr.select_one(".hauptlink a")
        club = tr.select_one("img.tiny_wappen")
        if not a or not club:
            continue
        val = tr.select_one("td.rechts")
        inner = tr.select("table.inline-table tr")
        pos = inner[1].get_text(" ", strip=True) if len(inner) > 1 else ""
        dates = []
        for td in tr.find_all("td", recursive=False):
            if td.select_one("table"):      # oyuncu hücresi (ad/mevki) tarih taşımaz
                continue
            dates += parse_dates(td.get_text(" ", strip=True))
        out.setdefault(club.get("alt", "").strip(), []).append(
            {"name": a.get_text(strip=True), "reason": "sakat", "value": _value(val.get_text() if val else ""),
             "position": pos, "dates": dates})
    return out


def key_threshold(values: list[float]) -> float:
    """Lig sakat listesindeki değerlerin üst çeyrek sınırı (en az KEY_MIN_VALUE). Az veri varsa 5× alt sınır."""
    vals = sorted(v for v in values if v > 0)
    if len(vals) < 8:
        return KEY_MIN_VALUE * 5
    return max(KEY_MIN_VALUE, vals[min(len(vals) - 1, int(KEY_QUANTILE * len(vals)))])


def build_absences(rows: list[dict], threshold: float, day: date) -> list[Absence]:
    """Bir kulübün satırlarından Absence listesi: aynı oyuncu tek kez, kilit = değer ≥ eşik, kaleci değil, ilk 2."""
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: -r["value"]):
        nk = re.sub(r"\s+", " ", r["name"].strip().lower())
        if nk in seen:      # sayfada aynı oyuncu iki satırda (iki ayrı sakatlık) görünebilir
            continue
        seen.add(nk)
        uniq.append(r)
    out, nkey = [], 0
    for r in uniq:
        is_key = nkey < KEY_PER_TEAM and r["value"] >= threshold and not _GK.search(r.get("position") or "")
        nkey += is_key
        since, until = split_dates(r.get("dates") or [], day)
        out.append(Absence(r["name"], r["reason"], key=bool(is_key), since=since, until=until,
                           value=r["value"], position=r.get("position") or ""))
    return out


def team_news(client: PoliteClient, day: date, fixtures) -> dict:
    needed = {f.league_id for f in fixtures if f.league_id in LEAGUES}
    out, t = {}, now_iso()
    for lid in needed:
        slug, code = LEAGUES[lid]
        html = client.get(f"{BASE}/{slug}/verletztespieler/wettbewerb/{code}/plus/1", ttl=12 * 3600)
        by_club = parse_rows(html)
        thr = key_threshold([r["value"] for rows in by_club.values() for r in rows])
        for club, rows in by_club.items():
            out[team_key(club)] = TeamNews(club, "transfermarkt", t, build_absences(rows, thr, day))
    return out
