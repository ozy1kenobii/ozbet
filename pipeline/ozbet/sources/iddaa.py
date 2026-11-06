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
        else:
            _extra(st, m, opts, odds)
    return odds


def _line(m) -> str | None:
    try:
        return f'{float(str(m.get("sov", "")).replace(",", ".")):.1f}'
    except ValueError:
        return None


# Seçenek adlarından kesin tanınan ek marketler (6 Kasım 2026 katalog dökümü, docs/research/market-katalog.md)
_RES = {"1": "1", "0": "X", "2": "2"}
_GOALS = {"0-1 gol": "G0-1", "2-3 gol": "G2-3", "4-5 gol": "G4-5", "6+ gol": "G6+"}
_HALF = {"1.": "MGH_1", "Eşit": "MGH_X", "2.": "MGH_2"}
# Anlamı kodla birlikte değişen (belirsiz) market türleri: ham olarak saklanır, run.py'deki çözümleyici eşler
AMBIGUOUS_ST = {36, 88, 603, 604, 100, 698, 699}


def _extra(st, m, opts, odds):
    ln = _line(m)
    if st == 60 and ln in ("0.5", "1.5", "2.5"):             # İY Alt/Üst
        _ou(odds, f"HT_", ln, opts)
    elif st == 91:                                             # Tek / Çift
        _put(odds, "ODD", opts.get("Tek")); _put(odds, "EVEN", opts.get("Çift"))
    elif st == 4 and set(opts) == set(_GOALS):                 # Toplam gol aralığı
        for k, v in _GOALS.items():
            _put(odds, v, opts[k])
    elif st == 6 and set(opts) == set(_HALF):                  # En çok gol olacak yarı
        for k, v in _HALF.items():
            _put(odds, v, opts[k])
    elif st == 7 and ln == "2.5" and len(opts) == 6:           # MS & Alt/Üst 2.5
        for name, v in opts.items():
            r, _, ou = name.partition(" ve ")
            if r in _RES and ou in ("Alt", "Üst"):
                _put(odds, f"{_RES[r]}&{'O' if ou == 'Üst' else 'U'}2.5", v)
    elif st == 700 and ln == "2.5" and len(opts) == 4:         # Alt/Üst 2.5 & KG
        for name, v in opts.items():
            ou, _, kg = name.partition(" ve ")
            if ou in ("Alt", "Üst") and kg in ("Var", "Yok"):
                _put(odds, f"BTTS_{'Y' if kg == 'Var' else 'N'}&{'O' if ou == 'Üst' else 'U'}2.5", v)
    elif st == 90 and len(opts) == 9:                          # İY/MS
        for name, v in opts.items():
            a, _, b = name.partition("/")
            if a in _RES and b in _RES:
                _put(odds, f"HTFT_{_RES[a]}/{_RES[b]}", v)
    elif st == 720:                                            # İY KG
        _put(odds, "HT_BTTS_Y", opts.get("Var")); _put(odds, "HT_BTTS_N", opts.get("Yok"))
    elif st == 48 and ln:                                      # Korner Alt/Üst
        _ou(odds, "C_", ln, opts)
    elif st == 49 and ln:                                      # Kart Alt/Üst
        _ou(odds, "K_", ln, opts)
    elif st in AMBIGUOUS_ST:
        raw = odds.setdefault("__raw__", {})                   # type: ignore[assignment]
        raw.setdefault(str(st), []).append({"sov": m.get("sov"), "o": {k: v for k, v in opts.items() if v}})


def _put(odds, key, v):
    if v:
        odds[key] = v


def _ou(odds, pre, ln, opts):
    _put(odds, f"{pre}O{ln}", opts.get("Üst")); _put(odds, f"{pre}U{ln}", opts.get("Alt"))


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
            odds=(od := parse_markets(e.get("m", []))) and {k: v for k, v in od.items() if k != "__raw__"},
            status="live" if e.get("il") else "scheduled",
            extra={"iddaa_id": e.get("i"), "iddaa_raw": od.get("__raw__") or None},
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
