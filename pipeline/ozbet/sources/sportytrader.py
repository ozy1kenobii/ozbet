"""SportyTrader — uzman tahminleri.

Liste: https://www.sportytrader.com/en/betting-tips/football/  → maç linkleri /en/betting-tips/{ev}-{dep}-{id}/
Maç sayfası: "Prediction :" etiketinin yanındaki tek satırlık tahmin metni.
İstek sayısını düşük tutmak için yalnızca öncelikli liglere benzeyen ilk 20 maç sayfası okunur.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import PoliteClient
from .base import Prediction, now_iso
from .predictions_common import picks_from_text

BASE = "https://www.sportytrader.com"
LISTS = [f"{BASE}/en/betting-tips/football/", f"{BASE}/en/betting-tips/"]
LINK = re.compile(r"^/en/betting-tips/([a-z0-9-]+)-(\d{5,})/?$")
MAX_PAGES = 20


def parse_match(html: str) -> tuple[str, str, str] | None:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    m = re.search(r"Prediction\s*:?\s*\n?\s*([^\n]{4,120})", text)
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    tm = re.search(r"(.+?)\s+(?:vs\.?|-)\s+(.+?)(?:\s+(?:prediction|betting tips|odds).*)?$", title, re.I)
    if not m or not tm:
        return None
    return tm.group(1).strip(), tm.group(2).strip(), m.group(1).strip()


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    links = []
    for u in LISTS:
        try:
            soup = BeautifulSoup(client.get(u, ttl=3 * 3600), "lxml")
        except Exception:  # noqa: BLE001
            continue
        for a in soup.find_all("a", href=True):
            href = a["href"].replace(BASE, "")
            if LINK.match(href) and href not in links:
                links.append(href)
        if links:
            break
    if not links:
        raise RuntimeError("sportytrader: maç linki bulunamadı (liste sayfası yapısı değişmiş olabilir)")
    out, t = [], now_iso()
    for href in links[:MAX_PAGES]:
        try:
            got = parse_match(client.get(BASE + href, ttl=6 * 3600))
        except Exception:  # noqa: BLE001
            continue
        if got:
            home, away, tip = got
            picks = picks_from_text(tip, home, away)
            if picks:
                out.append(Prediction("sportytrader", home, away, day.isoformat(), t, picks, note=tip[:120]))
    return out
