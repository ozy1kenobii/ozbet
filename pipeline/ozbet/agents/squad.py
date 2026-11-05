"""Kadro & Haber Ajanı: sakat/cezalı listesi, rotasyon riski (Avrupa maçına sıkışma), TD değişikliği."""
from __future__ import annotations

from datetime import timedelta

from .. import config
from ..teams import team_key


def rotation_risk(team: str, kickoff, all_fixtures) -> bool:
    """Takımın ±3 gün içinde bir Avrupa kupası maçı varsa (ve bu maç kupa maçı değilse) rotasyon riski."""
    k = team_key(team)
    for f in all_fixtures:
        lg = config.LEAGUE_BY_ID.get(f.league_id or "")
        if not lg or not lg.cup:
            continue
        if k not in (team_key(f.home), team_key(f.away)):
            continue
        dt = abs(f.kickoff - kickoff)
        if timedelta(hours=12) < dt <= timedelta(days=3):
            return True
    return False


def add_coach_signals(news: dict[str, object], coach_keys: set[str], fixtures) -> int:
    """Haber akışı sinyali: son 7 günde başlığında takım geçen "td" etiketli haber → coach_change = True.
    Mevcut TeamNews varsa yalnız bayrağı açar; yoksa eksik listesi boş bir TeamNews ekler. Oyuncu adı çıkarılmaz."""
    from ..sources.base import TeamNews, now_iso
    names = {}
    for f in fixtures:
        names.setdefault(team_key(f.home), f.home)
        names.setdefault(team_key(f.away), f.away)
    n = 0
    for k in coach_keys:
        cur = news.get(k)
        if cur is not None:
            cur.coach_change = True
        elif k in names:
            news[k] = TeamNews(names[k], "haber_rss", now_iso(), coach_change=True)
        else:
            continue
        n += 1
    return n


def build(home: str, away: str, kickoff, league_id, news: dict[str, object], all_fixtures) -> dict | None:
    """news: team_key → TeamNews"""
    lg = config.LEAGUE_BY_ID.get(league_id or "")
    out, src, t = {}, None, None
    for side, team in (("home", home), ("away", away)):
        n = news.get(team_key(team))
        rot = False if (lg and lg.cup) else rotation_risk(team, kickoff, all_fixtures)
        if n is None and not rot:
            out[side] = None
            continue
        missing = [{"name": p.name, "reason": p.reason, "key": p.key} for p in getattr(n, "missing", [])]
        out[side] = {"missing": missing, "rotation_risk": rot,
                     "coach_change": bool(getattr(n, "coach_change", False))}
        if n is not None and (src is None or n.missing):   # eksik listesi veren kaynak önceliklidir
            src, t = n.source, n.fetched_at
    if not out.get("home") and not out.get("away"):
        return None
    from .simulation import _squad_mult
    for side in ("home", "away"):
        if out.get(side):
            own, _, _ = _squad_mult(out[side])
            out[side]["adjustment"] = round(own - 1, 4)   # kendi λ'sına uygulanan oransal değişim
    out["source"], out["fetched_at"] = src, t
    return out
