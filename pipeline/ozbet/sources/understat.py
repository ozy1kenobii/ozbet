"""Understat — 5 büyük lig maç bazlı xG.

İki biçimi de destekler:
  1) Yeni JSON uç noktası:  /getLeagueData/{LIG}/{SEZON}  (X-Requested-With başlığı ile)
  2) Eski HTML sayfası:     /league/{LIG}/{SEZON} içinde  datesData = JSON.parse('\\x7B...')

Kasım 2026 teşhisi: site bakımda; her iki adres de HTTP 200 ile "We will come back soon" sayfası döndürüyor.
Bu sayfa eskiden önbelleğe yazılıyordu (geçmiş sezonlarda 30 gün) ve site geri gelse bile kaynak "bakımda"
görünmeye devam ediyordu. Artık yanıtlar içerik denetiminden geçer (bakım sayfası önbelleğe girmez, eski bozuk
kopya atılır) ve istek başarısız olursa en çok STALE_S eski son iyi kopya kullanılır (xG birkaç gün eski olabilir).
"""
from __future__ import annotations

import codecs
import json
import re
from datetime import date, datetime

from .. import config
from ..http import PoliteClient

BASE = "https://understat.com"
_RX = re.compile(r"datesData\s*=\s*JSON\.parse\('(.+?)'\)", re.S)
STALE_S = 14 * 86400      # site kapalıyken kabul edilen en eski xG kopyası


class Maintenance(RuntimeError):
    """Site bakım sayfası döndürüyor."""


def is_maintenance(text: str) -> bool:
    return "come back soon" in text[:60_000].lower()


def _json_ok(text: str) -> bool:
    return text.lstrip()[:1] in ("{", "[") and not is_maintenance(text)


def _html_ok(text: str) -> bool:
    return bool(_RX.search(text))


def _parse_dates(items) -> list[dict]:
    out = []
    for it in items:
        if not it.get("isResult"):
            continue
        try:
            d = datetime.strptime(it["datetime"][:10], "%Y-%m-%d").date()
            out.append({"date": d, "home": it["h"]["title"], "away": it["a"]["title"],
                        "hxg": round(float(it["xG"]["h"]), 3), "axg": round(float(it["xG"]["a"]), 3)})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def parse_json(text: str) -> list[dict]:
    """getLeagueData yanıtı: {"teams":..., "players":..., "dates":[...]} (eski adıyla datesData)."""
    data = json.loads(text)
    dates = (data.get("dates") or data.get("datesData")) if isinstance(data, dict) else data
    if isinstance(dates, str):          # bazı sürümlerde iç içe JSON metni
        dates = json.loads(dates)
    return _parse_dates(dates or [])


def parse_html(html: str) -> list[dict]:
    m = _RX.search(html)
    if not m:
        raise RuntimeError("understat: datesData bulunamadı (sayfa yapısı değişmiş)")
    return _parse_dates(json.loads(codecs.decode(m.group(1), "unicode_escape")))


def season_matches(client: PoliteClient, league: str, season_start: int, ttl: float = 6 * 3600) -> list[dict]:
    maint = False
    try:
        text = client.get(f"{BASE}/getLeagueData/{league}/{season_start}", ttl=ttl, stale=STALE_S,
                          validate=_json_ok,
                          headers={"X-Requested-With": "XMLHttpRequest",
                                   "Referer": f"{BASE}/league/{league}/{season_start}"})
        rows = parse_json(text)
        if rows:
            return rows
    except Exception as e:  # noqa: BLE001 — eski biçime düş
        maint = _is_maint_error(client, e)
    html_url = f"{BASE}/league/{league}/{season_start}"
    cached = getattr(client, "cached", None)
    if maint and not (cached and cached(html_url, max_age=STALE_S, validate=_html_ok)):
        # site kapalı ve eski biçimin de iyi kopyası yok: ikinci isteği boşuna yapma
        raise Maintenance("understat bakımda (site 'We will come back soon' sayfası döndürüyor)")
    try:
        html = client.get(html_url, ttl=ttl, stale=STALE_S, validate=_html_ok)
    except Exception as e:  # noqa: BLE001
        if _is_maint_error(client, e):
            raise Maintenance("understat bakımda (site 'We will come back soon' sayfası döndürüyor)") from e
        raise
    return parse_html(html)


def _is_maint_error(client, e: Exception) -> bool:
    """İçerik denetimine takılan son yanıt bakım sayfası mı?"""
    if type(e).__name__ != "BadContent":
        return False
    recent = getattr(client, "recent", None) or []
    return bool(recent) and is_maintenance(recent[-1][2])


def league_xg(client: PoliteClient, today: date) -> dict[str, list[dict]]:
    start = today.year if today.month >= 7 else today.year - 1
    out: dict[str, list[dict]] = {}
    errors = []
    for lg in config.LEAGUES:
        if not lg.understat:
            continue
        rows = []
        for s in (start, start - 1, start - 2):
            try:
                rows += season_matches(client, lg.understat, s, ttl=6 * 3600 if s == start else 30 * 86400)
            except Exception as e:  # noqa: BLE001
                if isinstance(e, Maintenance) and not out and not rows:
                    raise   # site kapalı ve önbellekte iyi kopya yok: kalan istekleri boşuna yapma
                errors.append(f"{lg.id}/{s}: {type(e).__name__}: {str(e)[:80]}")
                if isinstance(e, Maintenance):
                    break
        if rows:
            out[lg.id] = rows
    if not out and errors:
        raise RuntimeError("; ".join(errors[:4]))
    return out
