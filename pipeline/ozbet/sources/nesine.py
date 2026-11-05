"""Nesine bülten JSON'u — iddaa maç kodu (C), MBS ve oranlar.

https://cdnbulten.nesine.com/api/bulten/getprebultenfull  →  sg.EA[] (maçlar), sg.LA[] (ligler)
MTID: 1 Maç Sonucu (N 1/2/3), 3 Çifte Şans, 5 İY/MS, 11 1.5 A/Ü, 12 2.5 A/Ü (N1=Alt, N2=Üst), 38 KG (N1=Var, N2=Yok)
Nesine'nin herkese açık bir "biten maç sonucu" uç noktası bulunamadı → results() boş döner, sonuçlar
football-data.co.uk ve flashscore'dan gelir.
"""
from __future__ import annotations

from datetime import date, datetime

from .. import config
from ..agents.bulletin import league_for
from ..http import PoliteClient
from .base import Fixture, now_iso

URL = "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"

# MTID → {N: market}
MAP = {
    1: {1: "1", 2: "X", 3: "2"},
    3: {1: "1X", 2: "12", 3: "X2"},
    11: {1: "U1.5", 2: "O1.5"},
    12: {1: "U2.5", 2: "O2.5"},
    38: {1: "BTTS_Y", 2: "BTTS_N"},
}
EXPECTED_N = {1: 3, 3: 3, 11: 2, 12: 2, 38: 2}


def parse_markets(ma: list[dict]) -> tuple[dict[str, float], int | None]:
    odds, mbs = {}, None
    for m in ma or []:
        mt = m.get("MTID")
        if mt not in MAP:
            continue
        oca = m.get("OCA") or []
        if len(oca) != EXPECTED_N[mt]:   # beklenmeyen yapı → atla (yanlış eşlemeyi önler)
            continue
        for o in oca:
            k = MAP[mt].get(o.get("N"))
            try:
                v = float(o.get("O"))
            except (TypeError, ValueError):
                continue
            if k and v > 1.0:
                odds[k] = v
        if mt == 1 and m.get("MBS") is not None:
            try:
                mbs = int(m["MBS"])
            except (TypeError, ValueError):
                pass
    return odds, mbs


def _kickoff(e) -> datetime | None:
    if e.get("ESD"):
        try:
            return datetime.fromtimestamp(int(e["ESD"]) / 1000, tz=config.TZ)
        except (TypeError, ValueError, OSError):
            pass
    try:
        return datetime.strptime(f'{e["D"]} {e["T"]}', "%d.%m.%Y %H:%M").replace(tzinfo=config.TZ)
    except (KeyError, ValueError):
        return None


def parse(doc: dict, day: date | None, t: str) -> list[Fixture]:
    sg = doc.get("sg") or {}
    leagues = {l.get("LID"): l.get("N", "") for l in (sg.get("LA") or [])}
    out = []
    for e in sg.get("EA") or []:
        if e.get("TYPE") == -1 or not e.get("MA") or not e.get("HN"):
            continue
        if e.get("GT") not in (None, 1):   # yalnız futbol
            continue
        ko = _kickoff(e)
        if ko is None or (day and not (0 <= (ko.date() - day).days <= 3)):
            continue
        odds, mbs = parse_markets(e["MA"])
        raw = leagues.get(e.get("LC"), "") or str(e.get("LN", ""))
        out.append(Fixture(league_for(raw) if raw else None, raw, ko, e["HN"].strip(), e["AN"].strip(),
                           "nesine", t, code=str(e.get("C")) if e.get("C") else None, mbs=mbs, odds=odds,
                           extra={"betradar": e.get("BRID")}))
    return out


def fixtures(client: PoliteClient, day: date) -> list[Fixture]:
    doc = client.get_json(URL, ttl=15 * 60, headers={"Accept": "application/json"})
    return parse(doc, day, now_iso())


def results(client: PoliteClient, day: date) -> dict:
    return {}
