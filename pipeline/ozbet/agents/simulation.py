"""Simülasyon Ajanı: lig başına Dixon-Coles (+ xG harmanı) → kadro düzeltmesi → 10.000 Monte Carlo."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np

from .. import config
from ..model.dixon_coles import Ratings, fit
from ..model.simulate import seed_for, simulate
from ..teams import TeamMatcher

log = logging.getLogger("ozbet.sim")

# Avrupa kupaları için kaba lig gücü (log ölçek, Premier Lig = 0). UEFA katsayılarından esinlenen yaklaşık değerler.
LEAGUE_STRENGTH = {
    "ENG1": 0.0, "ESP1": -0.03, "ITA1": -0.05, "GER1": -0.05, "FRA1": -0.10,
    "POR1": -0.18, "NED1": -0.18, "BEL1": -0.22, "TR1": -0.25, "SCO1": -0.32, "GRE1": -0.30,
    "ENG2": -0.35, "ESP2": -0.45, "ITA2": -0.45, "GER2": -0.40, "FRA2": -0.50, "TR2": -0.55,
}


@dataclass
class LeagueModel:
    league_id: str
    goals: Ratings
    xg: Ratings | None
    matcher: TeamMatcher

    def team(self, name: str) -> str | None:
        return self.matcher.match(name)


def build(league_id: str, rows: list[dict], ref: date) -> LeagueModel | None:
    past = [r for r in rows if r["date"] < ref]
    g = fit(past, ref, config.TIME_DECAY_XI)
    if g is None:
        return None
    x = None
    if sum(1 for r in past if r.get("hxg") is not None) >= 60:
        x = fit(past, ref, config.TIME_DECAY_XI, use_xg=True)
    return LeagueModel(league_id, g, x, TeamMatcher(g.teams))


def _squad_mult(sq: dict | None) -> tuple[float, float, list[str]]:
    """(kendi λ çarpanı, rakip λ çarpanı, notlar)"""
    if not sq:
        return 1.0, 1.0, []
    notes = []
    keys = [m for m in sq.get("missing", []) if m.get("key")]
    others = [m for m in sq.get("missing", []) if not m.get("key")]
    own = 0.94 ** min(len(keys), 3) * 0.985 ** min(len(others), 4)
    opp = 1.02 ** min(len(keys), 3)
    if sq.get("rotation_risk"):
        own *= 0.97; opp *= 1.01; notes.append("rotasyon riski")
    if sq.get("coach_change"):
        notes.append("teknik direktör değişikliği")
    return own, opp, notes


def predict(home_name: str, away_name: str, league_id: str | None, models: dict[str, LeagueModel],
            squad: dict | None, key: str, neutral: bool = False) -> dict | None:
    lg = config.LEAGUE_BY_ID.get(league_id) if league_id else None
    notes: list[str] = []
    cross = lg is None or lg.cup or league_id not in models

    if not cross:
        M = models[league_id]
        h, a = M.team(home_name), M.team(away_name)
        if not h or not a:
            return None
        R = M.goals
        lh, la = R.lambdas(h, a, neutral)
        if M.xg is not None and h in M.xg.attack and a in M.xg.attack:
            xh, xa = M.xg.lambdas(h, a, neutral)
            w = config.XG_BLEND
            lh, la = (1 - w) * lh + w * xh, (1 - w) * la + w * xa
            notes.append("xG harmanı kullanıldı")
        nh, na = R.n_matches.get(h, 0), R.n_matches.get(a, 0)
        rho, hts = R.rho, R.ht_share
        quality = "high" if min(nh, na) >= 15 else ("medium" if min(nh, na) >= config.MIN_TEAM_MATCHES else "low")
    else:
        # Kupa / bilinmeyen lig: takımları kendi liglerinde bul, lig gücüyle düzelt
        found = []
        for name in (home_name, away_name):
            hit = None
            for lid, M in models.items():
                t = M.team(name)
                if t:
                    hit = (lid, M, t); break
            found.append(hit)
        if not all(found):
            return None
        (lh_id, Mh, h), (la_id, Ma, a) = found
        sh, sa = LEAGUE_STRENGTH.get(lh_id, -0.4), LEAGUE_STRENGTH.get(la_id, -0.4)
        mu = (Mh.goals.mu + Ma.goals.mu) / 2
        home_adv = 0.0 if neutral else (Mh.goals.home + Ma.goals.home) / 2
        lh = float(np.exp(mu + home_adv + Mh.goals.attack[h] + Ma.goals.defense[a] + (sh - sa)))
        la = float(np.exp(mu + Ma.goals.attack[a] + Mh.goals.defense[h] + (sa - sh)))
        rho = (Mh.goals.rho + Ma.goals.rho) / 2
        hts = (Mh.goals.ht_share + Ma.goals.ht_share) / 2
        nh, na = Mh.goals.n_matches.get(h, 0), Ma.goals.n_matches.get(a, 0)
        quality = "medium" if min(nh, na) >= 15 else "low"
        if lh_id != la_id:
            notes.append("Farklı ligler: yaklaşık lig gücü katsayısı kullanıldı")

    oh, xh_, nh_ = _squad_mult((squad or {}).get("home"))
    oa, xa_, na_ = _squad_mult((squad or {}).get("away"))
    lh *= oh * xa_
    la *= oa * xh_
    if oh < 1 or oa < 1:
        notes.append("Kadro eksikleri λ'ya yansıtıldı")
    notes += [f"Ev: {n}" for n in nh_] + [f"Deplasman: {n}" for n in na_]

    sim = simulate(lh, la, rho, hts, config.MC_SIMS, seed_for(key))
    sim["data_quality"] = quality
    sim["notes"] = notes
    sim["n_matches"] = {"home": nh, "away": na}
    return sim
