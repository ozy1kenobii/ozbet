"""SportyTrader — uzman tahminleri.

Liste: https://www.sportytrader.com/en/betting-tips/football/  → maç linkleri /en/betting-tips/{ev}-{dep}-{id}/
Maç sayfası: "Prediction :" etiketinin yanındaki tek satırlık tahmin metni.
İstek sayısını düşük tutmak için yalnızca öncelikli liglere benzeyen ilk 20 maç sayfası okunur.

13 Kasım 2026 teşhisi: liste sayfaları HTTP 403 + Cloudflare "Just a moment..." doğrulama sayfası döndürmeye başladı
(önceki 39 çalıştırma sorunsuzdu). Doğrulama aşılmaz; engel artık "maç linki bulunamadı" diye yanlış raporlanmaz,
Blocked olarak gerekçesiyle görünür. http.py engel hafızası tekrarlayan engelde alan adını dinlendirir.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import Blocked, PoliteClient
from .base import Prediction, now_iso
from .predictions_common import picks_from_text

BASE = "https://www.sportytrader.com"
LISTS = [f"{BASE}/en/betting-tips/football/", f"{BASE}/en/betting-tips/"]
LINK = re.compile(r"^/en/betting-tips/([a-z0-9-]+)-(\d{5,})/?$")
MAX_PAGES = 20


_TIP_WORDS = re.compile(r"\b(win|draw|over|under|both teams|btts|goals?)\b", re.I)


def parse_match(html: str) -> tuple[str, str, str] | None:
    """Takımlar <title>/h1'den ('X vs Y Prediction - ...'); tahmin: 'Prediction' içeren satırı izleyen,
    bahis ifadesi içeren ilk kısa satır."""
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "") or \
            (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
    tm = re.search(r"^(.+?)\s+vs\.?\s+(.+?)\s+(?:prediction|betting tips|odds)\b", title, re.I)
    if not tm:
        return None
    home, away = tm.group(1).strip(), tm.group(2).strip()
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    lines = [l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if re.search(r"\bprediction\b", line, re.I) and len(line) < 140:
            # aynı satırda ':' sonrası veya sonraki 3 satır
            cands = [line.split(":", 1)[1]] if ":" in line else []
            cands += lines[i + 1:i + 4]
            for c in cands:
                c = c.strip()
                if 3 < len(c) < 120 and _TIP_WORDS.search(c) and "odds" not in c.lower():
                    return home, away, c
    return None


def parse_links(html: str) -> list[str]:
    links = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        href = a["href"].replace(BASE, "").split("?")[0].split("#")[0]
        if LINK.match(href) and href not in links:
            links.append(href)
    return links


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    links, blocked, failed, read = [], None, [], 0
    for u in LISTS:
        try:
            html = client.get(u, ttl=3 * 3600)
        except Blocked as e:
            blocked = e
            continue
        except Exception as e:  # noqa: BLE001
            failed.append(f"{type(e).__name__}: {str(e)[:80]}")
            continue
        read += 1
        links = parse_links(html)
        if links:
            break
    if not links:
        if blocked and not read:
            # Site bot doğrulamasıyla erişimi reddediyor; doğrulamayı aşmaya çalışmıyoruz.
            raise Blocked(f"SportyTrader liste sayfası engelli (bot doğrulaması aşılmaz): {blocked}") from blocked
        if failed and not read:
            raise RuntimeError("sportytrader: liste sayfası alınamadı — " + "; ".join(failed[:2]))
        raise RuntimeError("sportytrader: liste sayfası okundu ama maç linki bulunamadı (sayfa yapısı değişmiş; "
                           "LINK deseni güncellenmeli)")
    out, t = [], now_iso()
    for href in links[:MAX_PAGES]:
        try:
            got = parse_match(client.get(BASE + href, ttl=6 * 3600))
        except Blocked:
            break       # maç sayfaları da engelli: kalan istekleri boşuna yapma
        except Exception:  # noqa: BLE001
            continue
        if got:
            home, away, tip = got
            picks = picks_from_text(tip, home, away)
            if picks:
                out.append(Prediction("sportytrader", home, away, day.isoformat(), t, picks, note=tip[:120]))
    return out
