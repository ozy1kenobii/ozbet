"""Flashscore — fikstür, sonuç (dün) ve mümkünse eksik oyuncular.

Düz metin feed: https://d.flashscore.com.tr/x/feed/f_1_{gün_ofseti}_3_tr_1  (x-fsign başlığı gerekli)
Kayıt ayırıcı '~', alan '¬', anahtar/değer '÷'. ZA = lig başlığı, AA = maç id, AD = epoch,
AE/AF = ev/dep, AG/AH = skor, AB = durum (1 başlamadı, 2 canlı, 3 bitti), BA/BB = İY skoru.

x-fsign değeri zamanla değişebilir: FLASHSCORE_FSIGN ortam değişkeniyle güncellenebilir.
Eksik oyuncu feed'i belgelenmemiş; Playwright varsa maç sayfası "Eksik oyuncular" bölümü okunur,
yoksa bu rol boş döner (kaynak durumu 'partial' görünür).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

from .. import config
from ..agents.bulletin import league_for
from ..http import PoliteClient
from ..teams import team_key
from .base import Fixture, MissingPlayer, TeamNews, now_iso

log = logging.getLogger("ozbet.flashscore")
HOSTS = ["https://d.flashscore.com.tr", "https://d.flashscore.com"]
FSIGN = os.environ.get("FLASHSCORE_FSIGN") or "SW9D1eZo"


def parse_feed(text: str, t: str) -> list[Fixture]:
    out, league_raw = [], ""
    for rec in text.split("~"):
        fields = {}
        for part in rec.split("¬"):
            if "÷" in part:
                k, v = part.split("÷", 1)
                fields.setdefault(k, v)
        if "ZA" in fields:
            league_raw = fields["ZA"]          # "TÜRKİYE: Süper Lig"
            continue
        if "AA" not in fields or "AE" not in fields:
            continue
        try:
            ko = datetime.fromtimestamp(int(fields["AD"]), tz=timezone.utc).astimezone(config.TZ)
        except (KeyError, ValueError):
            continue
        st = fields.get("AB")
        res = None
        if st == "3" and fields.get("AG", "").isdigit() and fields.get("AH", "").isdigit():
            ht = None
            if fields.get("BA", "").isdigit() and fields.get("BB", "").isdigit():
                ht = [int(fields["BA"]), int(fields["BB"])]
            res = {"ft": [int(fields["AG"]), int(fields["AH"])], "ht": ht}
        raw = league_raw.replace(":", " ")
        out.append(Fixture(league_for(raw), league_raw, ko, fields["AE"], fields["AF"], "flashscore", t,
                           status="finished" if res else ("live" if st == "2" else "scheduled"), result=res,
                           extra={"flashscore_id": fields["AA"]}))
    return out


def _feed(client: PoliteClient, offset: int, ttl: float) -> str:
    err = None
    for host in HOSTS:
        lang = "tr" if host.endswith(".tr") else "en"
        try:
            return client.get(f"{host}/x/feed/f_1_{offset}_3_{lang}_1", ttl=ttl,
                              headers={"x-fsign": FSIGN, "Referer": host.replace("d.", "www.") + "/"})
        except Exception as e:  # noqa: BLE001
            err = e
    raise err  # type: ignore[misc]


def fixtures(client: PoliteClient, day: date) -> list[Fixture]:
    offset = (day - datetime.now(config.TZ).date()).days
    fx = parse_feed(_feed(client, offset, ttl=20 * 60), now_iso())
    return [f for f in fx if f.kickoff.date() == day]


def results(client: PoliteClient, day: date) -> dict:
    offset = (day - datetime.now(config.TZ).date()).days
    if offset < -7:
        return {}
    out = {}
    for f in parse_feed(_feed(client, offset, ttl=6 * 3600), now_iso()):
        if f.result:
            out[(f.kickoff.date().isoformat(), team_key(f.home), team_key(f.away))] = f.result
    return out


def team_news(client: PoliteClient, day: date, fixtures_today: list[Fixture]) -> dict:
    """Playwright ile öncelikli lig maçlarının 'Eksik oyuncular' bölümünü okur (en fazla 25 maç)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright kurulu değil; eksik oyuncu verisi alınamadı")
    targets = [f for f in fixtures_today if f.extra.get("flashscore_id") and f.league_id][:25]
    if not targets:
        return {}
    out, t = {}, now_iso()
    with sync_playwright() as p:
        br = p.chromium.launch()
        page = br.new_page(user_agent=config.USER_AGENT, locale="tr-TR")
        for f in targets:
            url = f"https://www.flashscore.com.tr/mac/{f.extra['flashscore_id']}/#/mac-ozeti/kadrolar"
            try:
                page.goto(url, timeout=30000)
                page.wait_for_timeout(int(config.REQUEST_DELAY_S * 1000))
                sections = page.locator("section", has_text="Eksik oyuncular")
                if sections.count() == 0:
                    continue
                cols = sections.first.locator("div[class*='lf__side']")
                for side, team in ((0, f.home), (1, f.away)):
                    if cols.count() <= side:
                        continue
                    players = []
                    for row in cols.nth(side).locator("div[class*='lf__participant']").all()[:12]:
                        name = (row.locator("[class*='lf__participantName'], a").first.inner_text() or "").strip()
                        reason_txt = (row.inner_text() or "").lower()
                        reason = "cezalı" if ("ceza" in reason_txt or "kart" in reason_txt) else \
                                 ("şüpheli" if "şüphe" in reason_txt else "sakat")
                        if name:
                            players.append(MissingPlayer(name, reason, key=False))
                    if players:
                        out[team_key(team)] = TeamNews(team, "flashscore", t, players)
            except Exception as e:  # noqa: BLE001
                log.info("flashscore eksik oyuncu %s: %s", url, e)
        br.close()
    return out
