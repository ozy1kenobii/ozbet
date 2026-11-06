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
from ..teams import _NOISE, _VARIANT_RX, _ascii, normalize, similar, team_key


def _lnorm(raw: str) -> str:
    """Lig adı normalleştirme: takım normalleştirmesinden farkı, sondaki 'B'/'C'/'II' harfini SİLMEMESİ
    ("Serie B" ≠ "Serie C"). Kadın/altyapı ligleri league_for'da en başta elenir."""
    s = _ascii(raw).replace("&", " ").replace("'", "").replace(".", ". ")
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def league_for(raw: str) -> str | None:
    """Kaynaktaki lig adını OZBET lig kimliğine eşler."""
    a = _ascii(raw)
    # Altyapı / kadın / rezerv ligleri asla A takım ligine eşlenmez ("Süper Lig Kadınlar", "U19 Ligi")
    if any(rx.search(a) for rx, _ in _VARIANT_RX[:3]):
        return None
    n = _lnorm(raw)
    if not n:
        return None
    for lg in config.LEAGUES:
        for a in lg.aliases:
            if _lnorm(a) == n:
                return lg.id
    # Yalnızca çok yakın yazımlar; sayı/etiket farkı (ör. "Premier League 2", U21, kadın) asla eşleşmez
    raw_l = raw.lower()
    if re.search(r"(kad[ıi]n|women|u\d\d|gen[çc]|rezerv|reserve|youth|amat[öo]r|2\b|ii\b)", raw_l) and \
            not any(_lnorm(a) == n for lg in config.LEAGUES for a in lg.aliases):
        return None
    digits = re.findall(r"\d+", n)
    best, score = None, 0
    for lg in config.LEAGUES:
        for a in lg.aliases:
            na = _lnorm(a)
            if re.findall(r"\d+", na) != digits:
                continue
            # Tek/iki harflik ayırıcı farkı ("Serie B" ↔ "Serie C", "Lig A" ↔ "Lig B") asla bulanık eşleşmez
            if any(len(t) <= 2 for t in set(na.split()) ^ set(n.split())):
                continue
            s = fuzz.ratio(na, n)
            if s > score:
                best, score = lg.id, s
    return best if score >= 93 else None


def same_match(a: Fixture, b: Fixture) -> bool:
    if abs(a.kickoff - b.kickoff) > timedelta(hours=3):
        return False
    return similar(a.home, b.home) and similar(a.away, b.away)


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
            for k, v in f.extra.items():          # ör. flashscore_id → eksik oyuncu sayfası için gerekli
                if (k.endswith("_id") or k in ("referee", "iddaa_raw")) and v is not None:
                    hit.extra.setdefault(k, v)
    return out


def match_id(f: Fixture) -> str:
    # lig kimliği bilerek ID'de yok: bir çalıştırmada lig bulunamayıp sonrakinde bulunursa maç çiftlenmesin
    return f"{f.kickoff:%Y%m%d}-{team_key(f.home)}-{team_key(f.away)}"
