"""Bülten Ajanı: farklı kaynaklardan gelen fikstürleri tek bültende birleştirir.

Öncelik: iddaa kodu/MBS ve oranlar için Nesine/iddaa; lig/saat için onlar yoksa flashscore;
oran yedeği olarak football-data.co.uk fixtures.csv (Avg oranlar).
"""
from __future__ import annotations

import re
from datetime import timedelta

from rapidfuzz import fuzz

from .. import config
from ..sources.base import Fixture
from ..teams import canonical, normalize, team_key


def league_for(raw: str) -> str | None:
    """Kaynaktaki lig adını OZBET lig kimliğine eşler."""
    n = normalize(raw)
    if not n:
        return None
    for lg in config.LEAGUES:
        for a in lg.aliases:
            if normalize(a) == n:
                return lg.id
    # "Türkiye Süper Lig" gibi ön/son eklere tolerans; kadın/genç/2. lig ayrımı
    if re.search(r"\b(kadin|women|u\d\d|genc|rezerv|reserve|youth|amator)\b", n):
        return None
    best, score = None, 0
    for lg in config.LEAGUES:
        for a in lg.aliases:
            s = fuzz.token_sort_ratio(normalize(a), n)
            if s > score:
                best, score = lg.id, s
    return best if score >= 90 else None


def same_match(a: Fixture, b: Fixture) -> bool:
    if abs(a.kickoff - b.kickoff) > timedelta(hours=3):
        return False
    if team_key(a.home) == team_key(b.home) and team_key(a.away) == team_key(b.away):
        return True
    sh = fuzz.token_set_ratio(normalize(canonical(a.home)), normalize(canonical(b.home)))
    sa = fuzz.token_set_ratio(normalize(canonical(a.away)), normalize(canonical(b.away)))
    return sh >= 85 and sa >= 85 and sh + sa >= 180


def merge(primary: list[Fixture], *others: list[Fixture]) -> list[Fixture]:
    """primary listedeki maçlar korunur; diğer listeler eksik alanları (oran, lig, sonuç) doldurur,
    primary'de olmayan ve kapsanan liglere ait maçlar eklenir."""
    out = list(primary)
    for lst in others:
        for f in lst:
            hit = next((m for m in out if same_match(m, f)), None)
            if hit is None:
                if f.league_id:
                    out.append(f)
                continue
            hit.league_id = hit.league_id or f.league_id
            added = [k for k in f.odds if k not in hit.odds]
            for k in added:
                hit.odds[k] = f.odds[k]
            if added:
                hit.extra.setdefault("odds_sources", {}).update({k: f.source for k in added})
            hit.code = hit.code or f.code
            hit.mbs = hit.mbs or f.mbs
            if f.result and not hit.result:
                hit.result, hit.status = f.result, f.status
            hit.extra.setdefault("also_in", []).append(f.source)
    return out


def match_id(f: Fixture) -> str:
    return f"{f.league_id or 'OTHER'}-{f.kickoff:%Y%m%d}-{team_key(f.home)}-{team_key(f.away)}"
