"""Hangi adapter'ın hangi rolde, hangi öncelikle kullanılacağı.

Roller:
  FIXTURE_SOURCES    .fixtures(client, day) -> list[Fixture]          (sıra = öncelik)
  XG_SOURCES         .league_xg(client, day) -> {league_id: [{date, home, away, hxg, axg}]}
  NEWS_SOURCES       .team_news(client, day, fixtures) -> {team_key: TeamNews}
  PREDICTION_SOURCES .predictions(client, day, fixtures) -> list[Prediction]
  RESULT_SOURCES     .results(client, day) -> {(date, hkey, akey): {"ft":[h,a], "ht":[h,a]}}
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from .. import config
from ..teams import similar, team_key
from . import api_football, flashscore, forebet, freesupertips, iddaa, nesine, soccerstats, sportytrader, transfermarkt, understat


@dataclass
class Src:
    id: str
    name: str
    fixtures: Callable | None = None
    league_xg: Callable | None = None
    team_news: Callable | None = None
    predictions: Callable | None = None
    results: Callable | None = None


FIXTURE_SOURCES = [
    Src("nesine", "Nesine iddaa bülteni (kod, MBS, oran)", fixtures=nesine.fixtures),
    Src("iddaa", "iddaa.com resmi bülten (oran, MBS)", fixtures=iddaa.fixtures),
    Src("flashscore", "Flashscore (fikstür)", fixtures=flashscore.fixtures),
    Src("api_football", "API-Football (yedek, anahtar gerekir)", fixtures=api_football.fixtures),
]
XG_SOURCES = [Src("understat", "Understat (xG, 5 büyük lig)", league_xg=understat.league_xg)]
NEWS_SOURCES = [
    Src("flashscore_news", "Flashscore (sakat/cezalı)", team_news=flashscore.team_news),
    Src("transfermarkt", "Transfermarkt (sakatlık listesi)", team_news=transfermarkt.team_news),
]
PREDICTION_SOURCES = [
    Src("forebet", "Forebet (matematiksel tahmin)", predictions=forebet.predictions),
    Src("sportytrader", "SportyTrader (uzman tahmini)", predictions=sportytrader.predictions),
    Src("freesupertips", "FreeSuperTips (ipucu)", predictions=freesupertips.predictions),
    Src("soccerstats", "SoccerStats (lig istatistik eğilimi)", predictions=soccerstats.predictions),
]
RESULT_SOURCES = [
    Src("nesine_results", "Nesine (sonuçlar)", results=nesine.results),
    Src("flashscore_results", "Flashscore (sonuçlar)", results=flashscore.results),
]


def extra_history(client, board, today) -> dict:
    """football-data.co.uk'ta olmayan ligler için (ör. 1. Lig) API yedeği."""
    got = board.run("api_football_history", "API-Football geçmiş (1. Lig vb., anahtar gerekir)",
                    lambda: api_football.history(client, today),
                    count=lambda d: sum(len(v) for v in d.values()))
    return got or {}


def results_from_history(hist: dict[str, list[dict]]) -> dict:
    out = {}
    for rows in hist.values():
        for r in rows:
            out[(r["date"].isoformat(), team_key(r["home"]), team_key(r["away"]))] = {
                "ft": [r["hg"], r["ag"]],
                "ht": [r["hthg"], r["htag"]] if r.get("hthg") is not None else None,
            }
    return out


def lookup_result(results: dict, kickoff_iso: str, home: str, away: str):
    """Tarih ±1 gün; önce anahtar eşleşmesi, sonra bulanık eşleşme."""
    d = datetime.fromisoformat(kickoff_iso).date()
    hk, ak = team_key(home), team_key(away)
    days = [(d + timedelta(days=k)).isoformat() for k in (0, -1, 1)]
    for ds in days:
        r = results.get((ds, hk, ak))
        if r:
            return r
    for (ds, h, a), r in results.items():
        if ds in days and similar(home, _from_key(h)) and similar(away, _from_key(a)):
            return r
    return None


def _from_key(k: str) -> str:
    base, _, tag = k.partition("--")
    name = base.replace("-", " ")
    return f"{name} {tag.replace('w', 'women').replace('res', 'reserves')}" if tag else name
