"""Transfermarkt — lig sakatlık ve ceza listeleri.

Not: Site DataDome koruması kullanıyor ve GitHub Actions IP'lerini sıklıkla engelliyor. Engellenirse kaynak
'missing' görünür, akış devam eder. Piyasa değeri en yüksek oyuncular 'kilit' sayılır (takım içi ilk 4).
"""
from __future__ import annotations

import re
from datetime import date

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


def parse_injuries(html: str) -> dict[str, list[tuple[str, str, float]]]:
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, list] = {}
    for tr in soup.select("#yw1 tbody tr, table.items tbody tr"):
        a = tr.select_one(".hauptlink a")
        club = tr.select_one("img.tiny_wappen")
        if not a or not club:
            continue
        val = tr.select_one("td.rechts")
        out.setdefault(club.get("alt", "").strip(), []).append(
            (a.get_text(strip=True), "sakat", _value(val.get_text() if val else "")))
    return out


def team_news(client: PoliteClient, day: date, fixtures) -> dict:
    needed = {f.league_id for f in fixtures if f.league_id in LEAGUES}
    out, t = {}, now_iso()
    for lid in needed:
        slug, code = LEAGUES[lid]
        html = client.get(f"{BASE}/{slug}/verletztespieler/wettbewerb/{code}/plus/1", ttl=12 * 3600)
        for club, players in parse_injuries(html).items():
            players.sort(key=lambda p: -p[2])
            mp = [MissingPlayer(n, r, key=(i < 4 and v >= 1e6)) for i, (n, r, v) in enumerate(players)]
            out[team_key(club)] = TeamNews(club, "transfermarkt", t, mp)
    return out
