"""iddaa.com resmi sportsbookv2 JSON API'si (anahtarsız). Oran ve MBS için birincil kaynak.

events:        https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0&version=0
competitions:  https://sportsbookv2.iddaa.com/sportsbook/competitions
Market alt tipleri (st): 1 = Maç Sonucu ("1","0","2"), 101 = Alt/Üst (sov çizgi), 89 = KG ("Var","Yok").
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from .. import config
from ..agents.bulletin import league_for
from ..http import PoliteClient
from .base import Fixture, now_iso

BASE = "https://sportsbookv2.iddaa.com/sportsbook"
HDR = {"Accept": "application/json"}


def _num(v):
    try:
        f = float(str(v).replace(",", "."))
        return f if f > 1.0 else None
    except (TypeError, ValueError):
        return None


def parse_markets(markets: list[dict]) -> dict[str, float]:
    odds: dict[str, float] = {}
    for m in markets or []:
        st = m.get("st")
        opts = {str(o.get("n", "")).strip(): _num(o.get("odd")) for o in m.get("o", [])}
        if st == 1:
            for src, dst in (("1", "1"), ("0", "X"), ("2", "2")):
                if opts.get(src):
                    odds[dst] = opts[src]
        elif st == 101:
            try:
                line = f'{float(str(m.get("sov", "")).replace(",", ".")):.1f}'   # "2.50" → "2.5"
            except ValueError:
                continue
            if line in ("1.5", "2.5", "3.5"):
                if opts.get("Üst"):
                    odds[f"O{line}"] = opts["Üst"]
                if opts.get("Alt"):
                    odds[f"U{line}"] = opts["Alt"]
        elif st == 89:
            if opts.get("Var"):
                odds["BTTS_Y"] = opts["Var"]
            if opts.get("Yok"):
                odds["BTTS_N"] = opts["Yok"]
    return odds


def parse_events(events: list[dict], comps: dict, day: date | None, t: str) -> list[Fixture]:
    out = []
    for e in events:
        try:
            ko = datetime.fromtimestamp(int(e["d"]), tz=timezone.utc).astimezone(config.TZ)
        except (KeyError, TypeError, ValueError):
            continue
        if day and not (0 <= (ko.date() - day).days <= 3):   # bugün + rotasyon için 3 gün
            continue
        raw = comps.get(e.get("ci"), "")
        out.append(Fixture(
            league_id=league_for(raw), league_name_raw=raw, kickoff=ko,
            home=str(e.get("hn", "")).strip(), away=str(e.get("an", "")).strip(),
            source="iddaa.com", fetched_at=t,
            mbs=int(e["mbc"]) if str(e.get("mbc", "")).isdigit() else None,
            odds=parse_markets(e.get("m", [])),
            status="live" if e.get("il") else "scheduled",
            extra={"iddaa_id": e.get("i")},
        ))
    return [f for f in out if f.home and f.away]


def fixtures(client: PoliteClient, day: date) -> list[Fixture]:
    t = now_iso()
    cj = client.get_json(f"{BASE}/competitions", ttl=12 * 3600, headers=HDR)
    comps = {}
    for c in (cj.get("data") or []):
        name = c.get("n", "")
        country = c.get("cn") or ""
        comps[c.get("i")] = f"{country} {name}".strip() if country and country.lower() not in name.lower() else name
    ej = client.get_json(f"{BASE}/events", params={"st": 1, "type": 0, "version": 0}, ttl=15 * 60, headers=HDR)
    if not ej.get("isSuccess", True):
        raise RuntimeError("iddaa: isSuccess=false")
    try:
        from . import market_catalog
        try:
            mc = client.get_json(f"{BASE}/get_market_config", ttl=24 * 3600, headers=HDR)
        except Exception:  # noqa: BLE001
            mc = None
        market_catalog.dump("iddaa", market_catalog.iddaa((ej.get("data") or {}).get("events", []), mc))
    except Exception:  # noqa: BLE001
        pass
    return parse_events((ej.get("data") or {}).get("events", []), comps, day, t)
