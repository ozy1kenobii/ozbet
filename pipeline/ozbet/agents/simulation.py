"""Simülasyon Ajanı: lig başına Dixon-Coles (+ xG harmanı) → kadro düzeltmesi → 10.000 Monte Carlo."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np

from .. import config
from ..model.dixon_coles import Ratings, fit, score_matrix
from ..model.simulate import seed_for, simulate
from ..teams import TeamMatcher

log = logging.getLogger("ozbet.sim")

# Elo yoksa kullanılan YEDEK: Avrupa kupaları için kaba lig gücü (log ölçek, Premier Lig = 0). UEFA katsayılarından esinlenen yaklaşık değerler.
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
    corners: object | None = None   # model.counts.CountModel
    cards: object | None = None

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
    from ..model import counts
    try:
        cm = counts.fit(past, ref, config.TIME_DECAY_XI, "corners")
        km = counts.fit(past, ref, config.TIME_DECAY_XI, "cards")
    except Exception as e:  # noqa: BLE001
        log.warning("Korner/kart modeli %s kurulamadı: %s", league_id, e)
        cm = km = None
    return LeagueModel(league_id, g, x, TeamMatcher(g.teams), cm, km)


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


# ---------------- Elo tabanlı lig-arası düzeltme ----------------
# Yaklaşım (basit ve belgeli):
#  1) Elo kazanma beklentisi  We = 1 / (1 + 10^(-(Elo_ev + HFA - Elo_dep)/400)),  HFA ≈ 63 (tarafsız sahada 0).
#     Elo'da We bir "beklenen puan"dır: P(ev kazanır) + ½·P(beraberlik).
#  2) Toplam gol beklentisi T iki takımın KENDİ lig modellerinden gelir: her takım için ortalama bir rakibe karşı
#     maç başı atılan + yenen gol, T_takım = e^(μ_L + a) + e^(μ_L + d); T = iki takımın ortalaması.
#     Böylece lig-arası güç farkı toplam gol seviyesini bozmaz (güç yalnızca Elo'dan gelir), ama "gollü takım"
#     bilgisi korunur.
#  3) λ_ev + λ_dep = T kısıtıyla, Dixon-Coles skor matrisinden hesaplanan P(1) + ½·P(X) = We olacak şekilde
#     beklenen gol farkı D = λ_ev − λ_dep ikiye bölme (bisection) ile çözülür. P(1)+½P(X), D'ye göre monoton artar.
#  Neden: Elo'yu doğrudan gol farkına çeviren ampirik katsayılar ligden lige değişir; bu yöntem Elo'nun kendi
#  tanımını (beklenen puan) birebir korur ve tek serbest parametre olarak HFA'yı bırakır.


def elo_expectation(elo_home: float, elo_away: float, neutral: bool = False) -> float:
    dr = elo_home - elo_away + (0.0 if neutral else config.ELO_HFA)
    return 1.0 / (1.0 + 10 ** (-dr / 400.0))


def team_total(R: Ratings, team: str) -> float:
    """Takımın kendi liginde ortalama rakibe karşı maç başı toplam gol beklentisi (iç saha etkisi hariç)."""
    return float(np.exp(R.mu + R.attack[team]) + np.exp(R.mu + R.defense[team]))


def lambdas_from_elo(total: float, we: float, rho: float = 0.0) -> tuple[float, float]:
    """λ_ev + λ_dep = total ve P(1) + ½P(X) = we sağlayan (λ_ev, λ_dep)."""
    total = float(min(max(total, 1.2), 5.0))
    we = float(min(max(we, 0.02), 0.98))

    def score(share: float) -> float:
        lh, la = total * share, total * (1 - share)
        m = score_matrix(lh, la, rho, max_goals=10)
        return float(np.tril(m, -1).sum() + 0.5 * np.trace(m))

    lo, hi = 0.03, 0.97
    for _ in range(40):
        mid = (lo + hi) / 2
        if score(mid) < we:
            lo = mid
        else:
            hi = mid
    share = (lo + hi) / 2
    return total * share, total * (1 - share)


def _find_team(name: str, models: dict[str, LeagueModel]):
    for lid, M in models.items():
        t = M.team(name)
        if t:
            return lid, M, t
    return None


def predict(home_name: str, away_name: str, league_id: str | None, models: dict[str, LeagueModel],
            squad: dict | None, key: str, neutral: bool = False, elo: dict | None = None,
            referee: str | None = None) -> dict | None:
    """elo: {"home":1850,"away":1720,...} (clubelo). Çapraz lig/kupa maçında varsa lig gücü katsayısı yerine kullanılır."""
    lg = config.LEAGUE_BY_ID.get(league_id) if league_id else None
    notes: list[str] = []
    sim_elo = False
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
        # Kupa / bilinmeyen lig: takımları kendi liglerinde bul
        found = [_find_team(home_name, models), _find_team(away_name, models)]
        same_league = all(found) and found[0][0] == found[1][0]
        cup_like = lg is None or lg.cup
        # Elo yalnızca gerçekten lig-arası durumlarda: kupa/lig dışı maç ya da iki takım farklı lig modellerinde.
        # Modeli olmayan bir lig maçı (ör. geçmişi henüz olmayan 1. Lig) Elo'yla "uydurulmaz".
        if elo and elo.get("home") and elo.get("away") and not same_league and (cup_like or all(found)):
            # Elo tabanlı lig-arası düzeltme (bkz. yukarıdaki açıklama)
            tots = [team_total(M.goals, t) for (_, M, t) in (f for f in found if f)]
            total = float(np.mean(tots)) if tots else config.ELO_DEFAULT_TOTAL
            known = [M.goals for (_, M, _t) in (f for f in found if f)]
            rho = float(np.mean([R.rho for R in known])) if known else -0.05
            hts = float(np.mean([R.ht_share for R in known])) if known else 0.44
            we = elo_expectation(float(elo["home"]), float(elo["away"]), neutral)
            lh, la = lambdas_from_elo(total, we, rho)
            nh = found[0][1].goals.n_matches.get(found[0][2], 0) if found[0] else 0
            na = found[1][1].goals.n_matches.get(found[1][2], 0) if found[1] else 0
            quality = "medium"   # Elo'lu lig-arası maç: "orta" (kural); toplam gol varsayılansa notlarda belirtilir
            notes.append(f"Elo tabanlı lig-arası düzeltme (ClubElo {elo['home']}–{elo['away']}, beklenen puan {we:.2f})")
            if not all(found):
                notes.append("Takımlardan biri/ikisi lig modelinde yok: toplam gol beklentisi "
                             + ("diğer takımın liginden" if tots else "varsayılan değerden") + " alındı")
            sim_elo = True
        else:
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
                notes.append("Farklı ligler: yaklaşık lig gücü katsayısı kullanıldı (Elo yok)")

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
    sim["method"] = "elo" if sim_elo else ("league_strength" if cross else "league")
    if not cross:
        from ..model import counts
        for kind, cmod in (("corners", M.corners), ("cards", M.cards)):
            if cmod is not None and h in cmod.gen and a in cmod.gen:
                try:
                    sim[kind] = counts.predict(cmod, h, a, referee if kind == "cards" else None, key)
                except Exception as e:  # noqa: BLE001
                    log.info("%s tahmini %s: %s", kind, key, e)
    return sim
