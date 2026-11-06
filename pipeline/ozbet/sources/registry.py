"""Hangi adapter'ın hangi rolde, hangi öncelikle kullanılacağı.

Roller:
  FIXTURE_SOURCES    .fixtures(client, day) -> list[Fixture]          (sıra = öncelik)
  XG_SOURCES         .league_xg(client, day) -> {league_id: [{date, home, away, hxg, axg}]}
  NEWS_SOURCES       .team_news(client, day, fixtures) -> {team_key: TeamNews}
  PREDICTION_SOURCES .predictions(client, day, fixtures) -> list[Prediction]
  RESULT_SOURCES     .results(client, day) -> {(date, hkey, akey): {"ft":[h,a], "ht":[h,a]}}
                     .archive_feed(client, day) -> list[Fixture]  (opsiyonel; birikimli sonuç arşivini besler)
  ELO_SOURCES        .elo(client, day) -> clubelo.EloTable
  extra_history      football-data.co.uk'ta olmayan ligler (1. Lig): soccerstats, birikimli arşiv, API-Football
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from .. import config
from ..teams import similar, team_key
from . import api_football, archive, clubelo, forebet, freesupertips, iddaa, nesine, news_rss, soccerstats, sportytrader, transfermarkt, understat


@dataclass
class Src:
    id: str
    name: str
    fixtures: Callable | None = None
    league_xg: Callable | None = None
    team_news: Callable | None = None
    predictions: Callable | None = None
    results: Callable | None = None
    archive_feed: Callable | None = None
    elo: Callable | None = None


FIXTURE_SOURCES = [
    Src("nesine", "Nesine iddaa bülteni (kod, MBS, oran)", fixtures=nesine.fixtures),
    Src("iddaa", "iddaa.com resmi bülten (oran, MBS)", fixtures=iddaa.fixtures),
    Src("api_football", "API-Football (yedek, anahtar gerekir)", fixtures=api_football.fixtures),
]
XG_SOURCES = [Src("understat", "Understat (xG, 5 büyük lig)", league_xg=understat.league_xg)]
NEWS_SOURCES = [
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
    # Not: Flashscore sonuçları birikimli arşivi (data/archive) besliyordu; kullanım şartları nedeniyle kapatıldı.
    # Mevcut arşiv dosyaları okunmaya devam eder.
]
# Kullanım şartları veya robots.txt otomatik erişimi yasakladığı için devre dışı bırakılan kaynaklar.
# Kod silinmez; durum sayfasında "Atlandı" olarak gerekçesiyle görünür.
DISABLED = [
    ("flashscore", "Flashscore (fikstür, sonuç, eksik oyuncu)",
     "Devre dışı: kullanım şartları otomatik istek ve veri çıkarmayı yasaklıyor (md. 2.9-2.10)."),
]
ELO_SOURCES = [Src("clubelo", "ClubElo (kulüp Elo puanları, lig-arası düzeltme)", elo=clubelo.ratings)]
# football-data.co.uk'ta geçmişi olmayan ve soccerstats sonuç sayfasından okunan ligler
SOCCERSTATS_HISTORY = {"TR2": "turkey2"}


def extra_history(client, board, today, data_dir=None) -> dict:
    """football-data.co.uk'ta olmayan ligler (ör. 1. Lig) için geçmiş satırları.

    Aday kaynaklar (her biri StatusBoard ile sarılı): soccerstats sonuç sayfası, birikimli flashscore arşivi
    (data/archive, en az ARCHIVE_MIN_MATCHES maç), API-Football (anahtar varsa). Takım adları kaynaklar arasında
    farklı yazılabildiğinden kaynaklar KARIŞTIRILMAZ: lig başına en çok satırı olan tek kaynak seçilir.
    """
    data_dir = data_dir or config.DATA_DIR
    cands: dict[str, list[tuple[str, list[dict]]]] = {}
    for lid, code in SOCCERSTATS_HISTORY.items():
        rows = board.run(f"soccerstats_{lid.lower()}", f"SoccerStats sonuçlar ({config.LEAGUE_BY_ID[lid].name} geçmişi)",
                         lambda c=code: soccerstats.results_history(client, c, today))
        if rows:
            cands.setdefault(lid, []).append(("soccerstats", rows))
    arch = board.run("archive_history", "Birikimli sonuç arşivi (modele giren ligler)",
                     lambda: {lid: archive.history_rows(data_dir, lid) for lid in archive.leagues(data_dir)},
                     empty_is_partial=False,
                     count=lambda d: sum(len(v) for v in d.values() if len(v) >= config.ARCHIVE_MIN_MATCHES))
    for lid, rows in (arch or {}).items():
        if len(rows) >= config.ARCHIVE_MIN_MATCHES:
            cands.setdefault(lid, []).append(("arşiv", rows))
    if arch:
        small = {lid: len(v) for lid, v in arch.items() if len(v) < config.ARCHIVE_MIN_MATCHES}
        if small:
            board.note("archive_history", "Henüz eşik altında: " + ", ".join(
                f"{k} {v}/{config.ARCHIVE_MIN_MATCHES}" for k, v in sorted(small.items())))
    got = board.run("api_football_history", "API-Football geçmiş (1. Lig vb., anahtar gerekir)",
                    lambda: api_football.history(client, today),
                    count=lambda d: sum(len(v) for v in d.values()))
    for lid, rows in (got or {}).items():
        cands.setdefault(lid, []).append(("api-football", rows))
    return {lid: max(lst, key=lambda x: len(x[1]))[1] for lid, lst in cands.items()}


def rss_news(client, board, fixtures) -> dict:
    """RSS/Atom haber akışları (takım haberleri + etiketler). Hata olursa boş döner, akış durmaz."""
    got = board.run("news_rss", "Haber akışları (RSS/Atom: A Spor, NTV Spor, Fotomaç, TRT, AA, ESPN, Sky...)",
                    lambda: news_rss.collect(client, fixtures),
                    count=lambda d: sum(len(v["items"]) for v in d["teams"].values()))
    if got and got.get("feeds_failed"):
        board.note("news_rss", f"{got['feeds_ok']} akış okundu; okunamayan: {', '.join(got['feeds_failed'][:10])}")
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
