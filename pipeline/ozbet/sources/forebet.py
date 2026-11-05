"""Forebet — günlük matematiksel tahminler.

https://www.forebet.com/en/football-tips-and-predictions-for-today
Doğrulanmış seçiciler: div.rcnt (satır), span.forepr (1/X/2 tahmini), span.homeTeam / span.awayTeam.
Olasılık yüzdeleri (div.fprc span) doğrulanamadı → varsa okunur, yoksa yalnızca tahmin kullanılır.
Bot koruması olabilir; Playwright varsa HTTP 403'te tarayıcıyla yeniden denenir.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import Blocked, PoliteClient
from .base import Prediction, now_iso

URL = "https://www.forebet.com/en/football-tips-and-predictions-for-today"


def _fetch_browser(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page()
        pg.goto(url, timeout=45000)
        pg.wait_for_timeout(3000)
        html = pg.content()
        br.close()
    return html


def parse(html: str, day: date, t: str) -> list[Prediction]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for row in soup.select("div.rcnt"):
        ht, at = row.select_one(".homeTeam"), row.select_one(".awayTeam")
        if not ht or not at:
            meta = row.select_one('meta[itemprop="name"]')
            if not meta or " vs " not in meta.get("content", ""):
                continue
            home, away = [x.strip() for x in meta["content"].split(" vs ", 1)]
        else:
            home, away = ht.get_text(" ", strip=True), at.get_text(" ", strip=True)
        d = row.select_one(".date_bah")
        if d:
            m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", d.get_text())
            if m and date(int(m.group(3)), int(m.group(1)), int(m.group(2))) != day:
                continue
        picks, probs = {}, {}
        fp = row.select_one(".forepr")
        if fp and fp.get_text(strip=True) in ("1", "X", "2"):
            picks["1X2"] = fp.get_text(strip=True)
        pr = [s.get_text(strip=True) for s in row.select(".fprc span")]
        if len(pr) == 3 and all(x.isdigit() for x in pr):
            vals = [int(x) / 100 for x in pr]
            if 0.9 <= sum(vals) <= 1.1:
                probs = dict(zip(("1", "X", "2"), vals))
        sc = row.select_one(".ex_sc")
        if sc:
            m = re.search(r"(\d)\s*-\s*(\d)", sc.get_text())
            if m:
                x, y = int(m.group(1)), int(m.group(2))
                picks["OU25"] = "O2.5" if x + y > 2 else "U2.5"
                picks["BTTS"] = "BTTS_Y" if x > 0 and y > 0 else "BTTS_N"
        if picks or probs:
            out.append(Prediction("forebet", home, away, day.isoformat(), t, picks, probs))
    return out


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    try:
        html = client.get(URL, ttl=3 * 3600)
    except Blocked:
        html = _fetch_browser(URL)
    return parse(html, day, now_iso())
