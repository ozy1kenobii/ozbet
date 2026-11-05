"""football-data.co.uk adapter'ı — geçmiş sonuçlar, istatistikler, açılış/kapanış oranları ve
yaklaşan fikstür (fixtures.csv, oranlarıyla). Ücretsiz, CSV, model eğitimi ve backtest'in omurgası.
"""
from __future__ import annotations

import io
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from .. import config
from ..http import PoliteClient
from .base import Fixture, now_iso

log = logging.getLogger("ozbet.fd")
BASE = "https://www.football-data.co.uk"
UK = ZoneInfo("Europe/London")
CODE_TO_LEAGUE = {lg.fd_code: lg.id for lg in config.LEAGUES if lg.fd_code}


def _num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _parse_date(s: str) -> date | None:
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _odds_from_row(r, closing: bool = False) -> dict[str, float]:
    """Ortalama (Avg) oranları tercih eder, yoksa B365/Pinnacle."""
    c = "C" if closing else ""
    out = {}
    trip = [(f"Avg{c}H", f"Avg{c}D", f"Avg{c}A"), (f"B365{c}H", f"B365{c}D", f"B365{c}A"),
            (f"PS{c}H", f"PS{c}D", f"PS{c}A")]
    for h, d, a in trip:
        if all(_num(r.get(k)) for k in (h, d, a)):
            out.update({"1": _num(r[h]), "X": _num(r[d]), "2": _num(r[a])})
            break
    for o, u in [(f"Avg{c}>2.5", f"Avg{c}<2.5"), (f"B365{c}>2.5", f"B365{c}<2.5"), (f"P{c}>2.5", f"P{c}<2.5")]:
        if _num(r.get(o)) and _num(r.get(u)):
            out.update({"O2.5": _num(r[o]), "U2.5": _num(r[u])})
            break
    return out


def _read_csv(text: str) -> pd.DataFrame:
    # Bazı dosyalarda BOM ve sondaki boş kolonlar var
    df = pd.read_csv(io.StringIO(text.lstrip("﻿")), encoding_errors="replace", on_bad_lines="skip")
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def history(client: PoliteClient, fd_code: str, seasons: list[str]) -> list[dict]:
    """Belirtilen sezonların oynanmış maçları (en yeniden eskiye değil, karışık; sıralama çağıranda)."""
    rows: list[dict] = []
    for i, s in enumerate(seasons):
        url = f"{BASE}/mmz4281/{s}/{fd_code}.csv"
        ttl = 3 * 3600 if i == 0 else 30 * 86400   # içinde bulunulan sezon sık güncellenir
        try:
            text = client.get(url, ttl=ttl)
        except Exception as e:  # sezon dosyası henüz yoksa
            log.info("fd %s %s alınamadı: %s", fd_code, s, e)
            continue
        df = _read_csv(text)
        for _, r in df.iterrows():
            d = _parse_date(r.get("Date"))
            hg, ag = _num(r.get("FTHG")), _num(r.get("FTAG"))
            if d is None or hg is None or ag is None or not isinstance(r.get("HomeTeam"), str):
                continue
            rows.append({
                "date": d, "season": s, "home": r["HomeTeam"].strip(), "away": r["AwayTeam"].strip(),
                "hg": int(hg), "ag": int(ag),
                "hthg": None if _num(r.get("HTHG")) is None else int(_num(r.get("HTHG"))),
                "htag": None if _num(r.get("HTAG")) is None else int(_num(r.get("HTAG"))),
                "hs": _num(r.get("HS")), "as": _num(r.get("AS")),
                "hst": _num(r.get("HST")), "ast": _num(r.get("AST")),
                "hc": _num(r.get("HC")), "ac": _num(r.get("AC")),
                "hy": _num(r.get("HY")), "ay": _num(r.get("AY")),
                "hr": _num(r.get("HR")), "ar": _num(r.get("AR")),
                "odds_open": _odds_from_row(r), "odds_close": _odds_from_row(r, closing=True),
                "src": "football-data.co.uk",
            })
    return rows


def fixtures(client: PoliteClient, day: date) -> list[Fixture]:
    """fixtures.csv: önümüzdeki günlerin ana lig maçları + ortalama oranlar."""
    text = client.get(f"{BASE}/fixtures.csv", ttl=2 * 3600)
    df = _read_csv(text)
    out, t = [], now_iso()
    for _, r in df.iterrows():
        d = _parse_date(r.get("Date"))
        if d is None:
            continue
        tm = str(r.get("Time") or "12:00").strip()
        try:
            hh, mm = (int(x) for x in tm.split(":")[:2])
        except ValueError:
            hh, mm = 12, 0
        ko = datetime(d.year, d.month, d.day, hh, mm, tzinfo=UK).astimezone(config.TZ)
        if ko.date() != day:
            continue
        code = str(r.get("Div", "")).strip()
        out.append(Fixture(
            league_id=CODE_TO_LEAGUE.get(code), league_name_raw=code, kickoff=ko,
            home=str(r["HomeTeam"]).strip(), away=str(r["AwayTeam"]).strip(),
            source="football-data.co.uk", fetched_at=t, odds=_odds_from_row(r),
        ))
    return out
