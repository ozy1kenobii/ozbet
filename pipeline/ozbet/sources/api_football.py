"""API-Football (api-sports.io) — ücretsiz katman yedeği. API_FOOTBALL_KEY yoksa sessizce atlanır.

Ücretsiz katman günlük ~100 istek; bu yüzden yalnızca: günün fikstürü (1 istek) ve 1. Lig geçmişi
(sezon başına 1 istek, 24 saat önbellek) kullanılır.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from .. import config
from ..http import PoliteClient
from .base import Fixture, now_iso

BASE = "https://v3.football.api-sports.io"
# API-Football lig kimlikleri
LEAGUE_IDS = {"TR1": 203, "TR2": 204, "ENG1": 39, "ESP1": 140, "ITA1": 135, "GER1": 78, "FRA1": 61,
              "UCL": 2, "UEL": 3, "UECL": 848}
ID_TO_LEAGUE = {v: k for k, v in LEAGUE_IDS.items()}


class NoKey(Exception):
    pass


def _get(client: PoliteClient, path: str, params: dict, ttl: float):
    if not config.API_FOOTBALL_KEY:
        raise NoKey("API_FOOTBALL_KEY tanımlı değil (opsiyonel yedek)")
    text = client.get(BASE + path, params=params, ttl=ttl, check_robots=False,
                      headers={"x-apisports-key": config.API_FOOTBALL_KEY})
    data = json.loads(text)
    if data.get("errors"):
        raise RuntimeError(str(data["errors"])[:200])
    return data.get("response", [])


def fixtures(client: PoliteClient, day: date) -> list[Fixture]:
    if not config.API_FOOTBALL_KEY:
        return []
    resp = _get(client, "/fixtures", {"date": day.isoformat(), "timezone": "Europe/Istanbul"}, ttl=3 * 3600)
    out, t = [], now_iso()
    for r in resp:
        lid = ID_TO_LEAGUE.get(r["league"]["id"])
        ko = datetime.fromisoformat(r["fixture"]["date"]).astimezone(config.TZ)
        st = r["fixture"]["status"]["short"]
        res = None
        if st in ("FT", "AET", "PEN") and r["goals"]["home"] is not None:
            ht = r.get("score", {}).get("halftime") or {}
            res = {"ft": [r["goals"]["home"], r["goals"]["away"]],
                   "ht": [ht.get("home"), ht.get("away")] if ht.get("home") is not None else None}
        out.append(Fixture(lid, f'{r["league"]["country"]} {r["league"]["name"]}', ko,
                           r["teams"]["home"]["name"], r["teams"]["away"]["name"], "api-football", t,
                           status="finished" if res else ("live" if st in ("1H", "HT", "2H", "ET") else "scheduled"),
                           result=res))
    return out


def history(client: PoliteClient, today: date) -> dict[str, list[dict]]:
    """football-data.co.uk'ta olmayan 1. Lig için son 2 sezon sonuçları."""
    if not config.API_FOOTBALL_KEY:
        return {}
    start = today.year if today.month >= 7 else today.year - 1
    rows = []
    for season in (start, start - 1):
        for r in _get(client, "/fixtures", {"league": LEAGUE_IDS["TR2"], "season": season, "status": "FT"},
                      ttl=24 * 3600):
            ht = r.get("score", {}).get("halftime") or {}
            rows.append({
                "date": datetime.fromisoformat(r["fixture"]["date"]).astimezone(config.TZ).date(),
                "season": str(season), "home": r["teams"]["home"]["name"], "away": r["teams"]["away"]["name"],
                "hg": r["goals"]["home"], "ag": r["goals"]["away"],
                "hthg": ht.get("home"), "htag": ht.get("away"), "odds_open": {}, "odds_close": {},
                "src": "api-football",
            })
    return {"TR2": rows} if rows else {}
