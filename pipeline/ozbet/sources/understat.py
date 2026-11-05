"""Understat — 5 büyük lig maç bazlı xG.

İki biçimi de destekler:
  1) Yeni JSON uç noktası:  /getLeagueData/{LIG}/{SEZON}  (X-Requested-With başlığı ile)
  2) Eski HTML sayfası:     /league/{LIG}/{SEZON} içinde  datesData = JSON.parse('\\x7B...')
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


def season_matches(client: PoliteClient, league: str, season_start: int, ttl: float = 6 * 3600) -> list[dict]:
    try:
        text = client.get(f"{BASE}/getLeagueData/{league}/{season_start}", ttl=ttl,
                          headers={"X-Requested-With": "XMLHttpRequest",
                                   "Referer": f"{BASE}/league/{league}/{season_start}"})
        data = json.loads(text)
        dates = data.get("dates") or data.get("datesData")
        if dates:
            return _parse_dates(dates)
    except Exception:  # noqa: BLE001 — eski biçime düş
        pass
    html = client.get(f"{BASE}/league/{league}/{season_start}", ttl=ttl)
    m = _RX.search(html)
    if not m:
        raise RuntimeError("understat: datesData bulunamadı (sayfa yapısı değişmiş)")
    raw = codecs.decode(m.group(1), "unicode_escape")
    return _parse_dates(json.loads(raw))


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
                errors.append(f"{lg.id}/{s}: {type(e).__name__}")
        if rows:
            out[lg.id] = rows
    if not out and errors:
        raise RuntimeError("; ".join(errors[:4]))
    return out
