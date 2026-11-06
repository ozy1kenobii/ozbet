"""Zaman ağırlıklı Dixon-Coles modeli.

log λ_ev  = μ + h + a_ev  + d_dep
log λ_dep = μ     + a_dep + d_ev
Gol sayıları bağımsız Poisson; düşük skorlar (0-0, 1-0, 0-1, 1-1) Dixon-Coles τ(ρ) ile düzeltilir.
Ağırlık: w = exp(-ξ · gün_farkı). Hücum/savunma parametrelerine küçük L2 cezası → az maçlı takımlar ortalamaya çekilir.

Uygulama iki adımlı: (1) ağırlıklı Poisson MLE (analitik gradyan, L-BFGS), (2) λ'lar sabitken ρ için 1-B MLE.
Bu, tam ortak tahminle pratikte aynı sonucu verir ve çok daha hızlıdır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize, minimize_scalar


def tau(x, y, lam, mu, rho):
    x = np.asarray(x); y = np.asarray(y)
    t = np.ones(np.broadcast(x, y, lam, mu).shape, dtype=float)
    t = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, t)
    t = np.where((x == 0) & (y == 1), 1 + lam * rho, t)
    t = np.where((x == 1) & (y == 0), 1 + mu * rho, t)
    t = np.where((x == 1) & (y == 1), 1 - rho, t)
    return np.clip(t, 1e-6, None)


@dataclass
class Ratings:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    mu: float
    home: float
    rho: float = 0.0
    n_matches: dict[str, float] = field(default_factory=dict)   # ağırlıksız maç sayısı
    ht_share: float = 0.44
    draw_adj: float = 1.0          # lig beraberlik düzeltmesi: gözlenen / modelin beklediği beraberlik

    def lambdas(self, home: str, away: str, neutral: bool = False,
                att_adj: tuple[float, float] = (0.0, 0.0),
                def_adj: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
        ah = self.attack.get(home, 0.0) + att_adj[0]
        aa = self.attack.get(away, 0.0) + att_adj[1]
        dh = self.defense.get(home, 0.0) + def_adj[0]
        da = self.defense.get(away, 0.0) + def_adj[1]
        h = 0.0 if neutral else self.home
        return float(np.exp(self.mu + h + ah + da)), float(np.exp(self.mu + aa + dh))


def fit_poisson(home_idx, away_idx, hg, ag, w, n_teams, l2=0.5):
    """Ağırlıklı Poisson MLE. Parametreler: [μ, h, a_0..a_{n-1}, d_0..d_{n-1}]. hg/ag gerçek değerli olabilir (xG)."""
    hi = np.asarray(home_idx); ai = np.asarray(away_idx)
    hg = np.asarray(hg, float); ag = np.asarray(ag, float); w = np.asarray(w, float)
    n = n_teams

    def f(p):
        mu, h = p[0], p[1]
        a = p[2:2 + n]; d = p[2 + n:]
        lh = mu + h + a[hi] + d[ai]
        la = mu + a[ai] + d[hi]
        eh = np.exp(lh); ea = np.exp(la)
        nll = np.sum(w * (eh - hg * lh)) + np.sum(w * (ea - ag * la))
        nll += l2 * (np.sum(a ** 2) + np.sum(d ** 2))
        rh = w * (eh - hg); ra = w * (ea - ag)
        g = np.zeros_like(p)
        g[0] = rh.sum() + ra.sum()
        g[1] = rh.sum()
        ga = np.bincount(hi, rh, n) + np.bincount(ai, ra, n) + 2 * l2 * a
        gd = np.bincount(ai, rh, n) + np.bincount(hi, ra, n) + 2 * l2 * d
        g[2:2 + n] = ga; g[2 + n:] = gd
        return nll, g

    p0 = np.zeros(2 + 2 * n)
    mean_goals = max(1e-3, (np.sum(w * hg) + np.sum(w * ag)) / (2 * max(w.sum(), 1e-9)))
    p0[0] = np.log(mean_goals)
    res = minimize(f, p0, jac=True, method="L-BFGS-B")
    p = res.x
    a = p[2:2 + n]; d = p[2 + n:]
    # kimlik: ortalama hücum = 0, ortalama savunma = 0 (μ'ye aktar)
    ma, md = a.mean(), d.mean()
    return p[0] + ma + md, p[1], a - ma, d - md


def fit_rho(lh, la, hg, ag, w):
    hg = np.asarray(hg); ag = np.asarray(ag)
    low = (hg <= 1) & (ag <= 1)
    if low.sum() < 10:
        return 0.0
    lh, la, x, y, ww = np.asarray(lh)[low], np.asarray(la)[low], hg[low], ag[low], np.asarray(w)[low]

    def nll(r):
        return -np.sum(ww * np.log(tau(x, y, lh, la, r)))

    lo, hi = rho_bounds(lh, la)
    res = minimize_scalar(nll, bounds=(max(lo, -0.3), min(hi, 0.3)), method="bounded")
    return float(res.x)


def rho_bounds(lh, la):
    """Dixon-Coles (1997): max(-1/λ, -1/μ) ≤ ρ ≤ min(1/(λμ), 1), tüm maçlar için aynı anda."""
    lh = np.atleast_1d(np.asarray(lh, float)); la = np.atleast_1d(np.asarray(la, float))
    lo = float(np.max(np.maximum(-1 / lh, -1 / la)))
    hi = float(min(np.min(1 / (lh * la)), 1.0))
    return lo + 1e-6, hi - 1e-6


def clamp_rho(rho: float, lh: float, la: float) -> float:
    lo, hi = rho_bounds(lh, la)
    return float(min(max(rho, lo), hi))


def fit(matches, ref_date, xi: float, l2: float = 0.5, use_xg: bool = False) -> Ratings | None:
    """matches: dict listesi {date(np.datetime64 veya date), home, away, hg, ag, [hxg, axg], [hthg, htag]}"""
    if use_xg:
        matches = [m for m in matches if m.get("hxg") is not None and m.get("axg") is not None]
    if len(matches) < 30:
        return None
    teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
    ix = {t: i for i, t in enumerate(teams)}
    hi = np.array([ix[m["home"]] for m in matches]); ai = np.array([ix[m["away"]] for m in matches])
    hg = np.array([m["hxg"] if use_xg else m["hg"] for m in matches], float)
    ag = np.array([m["axg"] if use_xg else m["ag"] for m in matches], float)
    days = np.array([(ref_date - m["date"]).days for m in matches], float)
    w = np.exp(-xi * np.clip(days, 0, None))
    mu, h, a, d = fit_poisson(hi, ai, hg, ag, w, len(teams), l2=l2)
    rho = 0.0
    if not use_xg:
        lh = np.exp(mu + h + a[hi] + d[ai]); la = np.exp(mu + a[ai] + d[hi])
        rho = fit_rho(lh, la, hg.astype(int), ag.astype(int), w)
    counts = {t: 0 for t in teams}
    for m in matches:
        counts[m["home"]] += 1; counts[m["away"]] += 1
    # İlk yarı gol payı
    hts = [(m["hthg"] + m["htag"], m["hg"] + m["ag"]) for m in matches
           if m.get("hthg") is not None and m.get("htag") is not None]
    ht_share = 0.44
    if len(hts) > 50:
        s_ht = sum(a for a, _ in hts); s_ft = sum(b for _, b in hts)
        if s_ft > 0:
            ht_share = float(np.clip(s_ht / s_ft, 0.35, 0.5))
    draw_adj = 1.0
    from .. import config as _cfg
    if not use_xg and getattr(_cfg, "DRAW_CALIBRATION", False):
        draw_adj = estimate_draw_adj(np.exp(mu + h + a[hi] + d[ai]), np.exp(mu + a[ai] + d[hi]), rho,
                                     hg.astype(int) == ag.astype(int), w)
    return Ratings(teams, dict(zip(teams, a.tolist())), dict(zip(teams, d.tolist())),
                   float(mu), float(h), rho, counts, ht_share, draw_adj)


def draw_prob(lh: float, la: float, rho: float) -> float:
    return float(np.trace(score_matrix(lh, la, clamp_rho(rho, lh, la))))


def estimate_draw_adj(lh, la, rho, is_draw, w, lo: float = 0.85, hi: float = 1.20) -> float:
    """Zaman ağırlıklı gözlenen beraberlik oranı / modelin beklediği. Bağımsız Poisson + DC τ beraberliği
    sistematik olarak eksik tahmin edebilir (FiveThirtyEight SPI de beraberliği şişirir). Uç değerlere kırpılır."""
    pred = np.array([draw_prob(x, y, rho) for x, y in zip(lh, la)])
    obs = np.asarray(is_draw, float)
    r = float(np.sum(w * obs) / max(np.sum(w * pred), 1e-9))
    return float(np.clip(r, lo, hi))


def apply_draw_adj(m: np.ndarray, adj: float) -> np.ndarray:
    if adj == 1.0:
        return m
    m = m.copy()
    np.fill_diagonal(m, np.diag(m) * adj)
    return m / m.sum()


def score_matrix(lh: float, la: float, rho: float, max_goals: int = 10) -> np.ndarray:
    from scipy.stats import poisson
    x = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(x, lh), poisson.pmf(x, la))
    t = tau(x[:, None], x[None, :], lh, la, rho)
    m = m * t
    return m / m.sum()


def fit_shots(matches, ref_date, xi: float):
    """İsabetli şut (HST/AST) üretme/yeme güçleri + lig dönüşüm oranı (gol / isabetli şut).

    Döner: (Ratings, conv) — Ratings.lambdas() beklenen isabetli şutu verir; × conv = şut tabanlı beklenen gol.
    """
    rows = [dict(m, hxg=m["hst"], axg=m["ast"]) for m in matches
            if m.get("hst") is not None and m.get("ast") is not None and m["date"] < ref_date]
    if len(rows) < 60:
        return None, None
    R = fit(rows, ref_date, xi, use_xg=True)
    if R is None:
        return None, None
    w = np.exp(-xi * np.clip(np.array([(ref_date - m["date"]).days for m in rows], float), 0, None))
    goals = np.array([m["hg"] + m["ag"] for m in rows], float)
    sot = np.array([m["hst"] + m["ast"] for m in rows], float)
    conv = float(np.sum(w * goals) / max(np.sum(w * sot), 1e-9))
    return R, conv
