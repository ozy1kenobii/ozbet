"""FreeSuperTips — ipucu sayfaları.

Hub: https://www.freesupertips.com/predictions/
Maç: /predictions/{ev}-vs-{dep}-predictions-betting-tips-match-previews/  (H4 başlıklarında ipuçları)
Süper Lig kapsamı zayıf; ağırlıkla büyük Avrupa ligleri ve UEFA maçları.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import PoliteClient
from .base import Prediction, now_iso
from .predictions_common import picks_from_text

BASE = "https://www.freesupertips.com"
LINK = re.compile(r"/predictions/([a-z0-9-]+?)-vs-([a-z0-9-]+?)-predictions-betting-tips-match-previews(?:-\d+)?/?$")
MAX_PAGES = 20


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    soup = BeautifulSoup(client.get(f"{BASE}/predictions/", ttl=3 * 3600), "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].replace(BASE, "")
        if LINK.search(href) and href not in links:
            links.append(href)
    if not links:
        raise RuntimeError("freesupertips: maç linki bulunamadı")
    out, t = [], now_iso()
    for href in links[:MAX_PAGES]:
        m = LINK.search(href)
        home, away = (x.replace("-", " ").title() for x in m.groups())
        try:
            page = BeautifulSoup(client.get(BASE + href, ttl=6 * 3600), "lxml")
        except Exception:  # noqa: BLE001
            continue
        picks: dict[str, str] = {}
        tips = []
        for h4 in page.find_all("h4")[:6]:
            txt = h4.get_text(" ", strip=True)
            got = picks_from_text(txt, home, away)
            if got:
                tips.append(txt)
                for k, v in got.items():
                    picks.setdefault(k, v)
        if picks:
            out.append(Prediction("freesupertips", home, away, day.isoformat(), t, picks, note="; ".join(tips)[:160]))
    return out
