"""Korner ve kart modelleri (football-data.co.uk HC/AC, HY/AY/HR/AR, Referee kolonlarından).

Yöntem (gol modelinin aynısı, sayım verisine uyarlanmış):
  log μ_ev  = c + h + üret_ev + izin_dep        (ör. ev sahibinin korner sayısı)
  log μ_dep = c     + üret_dep + izin_ev
Zaman ağırlıklı Poisson MLE (dixon_coles.fit_poisson) ile güçler bulunur. Korner ve kart sayıları Poisson'dan
daha dağınık olduğu için toplam üzerinde negatif binom kullanılır: Var = φ·μ, φ lig artıklarından tahmin edilir.
Kartlarda hakem etkisi: hakemin maç başı kart ortalaması / lig ortalaması, az maçlı hakem için ortalamaya
büzülerek (k=10 maç) çarpan olarak uygulanır. Kart sayısı = sarı + kırmızı (iddaa "toplam kart" sayımı).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from scipy.stats import nbinom, poisson

from .dixon_coles import fit_poisson

CORNER_LINES = (7.5, 8.5, 9.5, 10.5, 11.5)
CARD_LINES = (2.5, 3.5, 4.5, 5.5)
REF_SHRINK = 10
MIN_ROWS = 80


@dataclass
class CountModel:
    kind: str
    teams: list[str]
    gen: dict[str, float]
    allow: dict[str, float]
    c: float
    h: float
    phi: float
    league_avg: float
    ref_factor: dict[str, float] = field(default_factory=dict)
    ref_n: dict[str, int] = field(default_factory=dict)

    def means(self, home: str, away: str, referee: str | None = None) -> tuple[float, float, float]:
        mh = float(np.exp(self.c + self.h + self.gen.get(home, 0.0) + self.allow.get(away, 0.0)))
        ma = float(np.exp(self.c + self.gen.get(away, 0.0) + self.allow.get(home, 0.0)))
        f = self.ref_factor.get((referee or "").strip(), 1.0) if self.kind == "cards" else 1.0
        return mh * f, ma * f, f


def _values(r: dict, kind: str):
    if kind == "corners":
        return r.get("hc"), r.get("ac")
    hy, ay = r.get("hy"), r.get("ay")
    if hy is None or ay is None:
        return None, None
    return hy + (r.get("hr") or 0), ay + (r.get("ar") or 0)


def fit(rows: list[dict], ref_date: date, xi: float, kind: str) -> CountModel | None:
    use = []
    for r in rows:
        if r["date"] >= ref_date:
            continue
        a, b = _values(r, kind)
        if a is not None and b is not None:
            use.append((r, float(a), float(b)))
    if len(use) < MIN_ROWS:
        return None
    teams = sorted({r["home"] for r, _, _ in use} | {r["away"] for r, _, _ in use})
    ix = {t: i for i, t in enumerate(teams)}
    hi = np.array([ix[r["home"]] for r, _, _ in use]); ai = np.array([ix[r["away"]] for r, _, _ in use])
    y_h = np.array([a for _, a, _ in use]); y_a = np.array([b for _, _, b in use])
    days = np.array([(ref_date - r["date"]).days for r, _, _ in use], float)
    w = np.exp(-xi * np.clip(days, 0, None))
    c, h, g, al = fit_poisson(hi, ai, y_h, y_a, w, len(teams), l2=1.0)
    mu_h = np.exp(c + h + g[hi] + al[ai]); mu_a = np.exp(c + g[ai] + al[hi])
    tot, mu = y_h + y_a, mu_h + mu_a
    phi = float(np.clip(np.sum(w * (tot - mu) ** 2 / mu) / np.sum(w), 1.0, 3.0))
    league_avg = float(np.average(tot, weights=w))
    ref_factor, ref_n = {}, {}
    if kind == "cards":
        by: dict[str, list[float]] = {}
        for (r, a, b), m in zip(use, mu):
            ref = (r.get("referee") or "").strip()
            if ref:
                by.setdefault(ref, []).append((a + b) / m)   # gözlenen / takımlardan beklenen
        for ref, ratios in by.items():
            n = len(ratios)
            ref_factor[ref] = round(float((sum(ratios) + REF_SHRINK) / (n + REF_SHRINK)), 3)
            ref_n[ref] = n
    return CountModel(kind, teams, dict(zip(teams, g.tolist())), dict(zip(teams, al.tolist())),
                      float(c), float(h), phi, league_avg, ref_factor, ref_n)


def _dist(mu: float, phi: float):
    if phi <= 1.02:
        return poisson(mu)
    n = mu / (phi - 1)
    return nbinom(n, n / (n + mu))


def predict(m: CountModel, home: str, away: str, referee: str | None, key: str) -> dict:
    mh, ma, f = m.means(home, away, referee)
    total = _dist(mh + ma, m.phi)
    lines = CORNER_LINES if m.kind == "corners" else CARD_LINES
    pre = "C" if m.kind == "corners" else "K"
    probs = {}
    for ln in lines:
        o = float(total.sf(ln))
        probs[f"{pre}_O{ln}"] = round(o, 4)
        probs[f"{pre}_U{ln}"] = round(1 - o, 4)
    # hangi takım daha çok: iki takımın sayısı ayrı NB, Monte Carlo
    rng = np.random.default_rng(int(hashlib.sha1((key + m.kind).encode()).hexdigest()[:8], 16))
    def draw(mu):
        d = _dist(mu, m.phi)
        return d.rvs(size=20000, random_state=rng)
    a, b = draw(mh), draw(ma)
    probs[f"{pre}R_1"] = round(float((a > b).mean()), 4)
    probs[f"{pre}R_X"] = round(float((a == b).mean()), 4)
    probs[f"{pre}R_2"] = round(float((a < b).mean()), 4)
    out = {"exp_home": round(mh, 2), "exp_away": round(ma, 2), "exp_total": round(mh + ma, 2),
           "league_avg": round(m.league_avg, 2), "dispersion": round(m.phi, 2), "probs": probs}
    if m.kind == "cards":
        out["referee"] = referee or None
        out["referee_factor"] = f if referee and referee in m.ref_factor else None
        out["referee_matches"] = m.ref_n.get(referee or "", 0)
    return out


LABELS = {
    **{f"C_{o}{ln}": f"Korner {ln} {'Üst' if o == 'O' else 'Alt'}" for o in "OU" for ln in CORNER_LINES},
    **{f"K_{o}{ln}": f"Kart {ln} {'Üst' if o == 'O' else 'Alt'}" for o in "OU" for ln in CARD_LINES},
    "CR_1": "En çok korner: Ev", "CR_X": "En çok korner: Eşit", "CR_2": "En çok korner: Dep",
    "KR_1": "En çok kart: Ev", "KR_X": "En çok kart: Eşit", "KR_2": "En çok kart: Dep",
}
GROUPS = {
    **{f"c_ou{ln}": [f"C_O{ln}", f"C_U{ln}"] for ln in CORNER_LINES},
    **{f"k_ou{ln}": [f"K_O{ln}", f"K_U{ln}"] for ln in CARD_LINES},
    "cr": ["CR_1", "CR_X", "CR_2"], "kr": ["KR_1", "KR_X", "KR_2"],
}
