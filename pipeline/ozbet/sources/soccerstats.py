"""SoccerStats — lig gol eğilimleri (trends.asp): takım başı 2.5+ (Ü2.5 %) ve BTS (KG %).

Bu bir tahmin sitesi değil; konsensüse "istatistik eğilimi" oyu olarak girer:
iki takımın ortalama 2.5+ yüzdesi ≥ %55 → 2.5 Üst, ≤ %40 → 2.5 Alt; BTS ≥ %55 → KG Var, ≤ %40 → KG Yok.
Tablolar başlık metnine göre (pandas.read_html) seçilir; sınıf adlarına bağımlı değildir.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd

from .. import config
from ..http import PoliteClient
from ..teams import TeamMatcher
from .base import Prediction, now_iso

BASE = "https://www.soccerstats.com"


def _pct(v):
    try:
        return float(str(v).replace("%", "").strip()) / 100
    except ValueError:
        return None


def league_trends(client: PoliteClient, code: str) -> dict[str, dict]:
    html = client.get(f"{BASE}/trends.asp", params={"league": code}, ttl=12 * 3600)
    tables = pd.read_html(io.StringIO(html))
    out = {}
    for tb in tables:
        cols = [str(c[-1] if isinstance(c, tuple) else c).strip() for c in tb.columns]
        if "2.5+" not in cols or "BTS" not in cols:
            continue
        tb.columns = cols
        name_col = next((c for c in cols if not c.replace(".", "").replace("+", "").isdigit()
                         and c not in ("GP", "Avg", "BTS", "CS", "FTS", "WTN", "LTN", "#")), cols[0])
        for _, r in tb.iterrows():
            team = str(r[name_col]).strip()
            o25, bts = _pct(r["2.5+"]), _pct(r["BTS"])
            if team and team.lower() != "nan" and o25 is not None and bts is not None:
                out.setdefault(team, {"o25": o25, "bts": bts})
        if out:
            break
    return out


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    t = now_iso()
    out = []
    by_league: dict[str, list] = {}
    for f in fixtures:
        lg = config.LEAGUE_BY_ID.get(f.league_id or "")
        if lg and lg.soccerstats and f.kickoff.date() == day:
            by_league.setdefault(lg.soccerstats, []).append(f)
    if not by_league:
        return []
    errors = 0
    for code, fx in by_league.items():
        try:
            tr = league_trends(client, code)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        tm = TeamMatcher(list(tr))
        for f in fx:
            h, a = tm.match(f.home), tm.match(f.away)
            if not h or not a:
                continue
            o = (tr[h]["o25"] + tr[a]["o25"]) / 2
            b = (tr[h]["bts"] + tr[a]["bts"]) / 2
            picks = {}
            if o >= 0.55: picks["OU25"] = "O2.5"
            elif o <= 0.40: picks["OU25"] = "U2.5"
            if b >= 0.55: picks["BTTS"] = "BTTS_Y"
            elif b <= 0.40: picks["BTTS"] = "BTTS_N"
            if picks:
                out.append(Prediction("soccerstats", f.home, f.away, day.isoformat(), t, picks,
                                      probs={"O2.5": round(o, 3), "BTTS_Y": round(b, 3)},
                                      note=f"Ü2.5 ort. %{round(o*100)}, KG ort. %{round(b*100)}"))
    if errors == len(by_league):
        raise RuntimeError("soccerstats: hiçbir lig tablosu okunamadı")
    return out
