"""Monte Carlo maç simülasyonu (Dixon-Coles τ ile önem ağırlıklı).

Her yarı ayrı Poisson: İY λ·s, İKY λ·(1-s). Tam skor üzerinde τ(x,y) ağırlığı uygulanır,
böylece hem İY/MS hem de Dixon-Coles düşük skor düzeltmesi tutarlı olur.
"""
from __future__ import annotations

import hashlib

import numpy as np

from ..markets import HTFT_KEYS, probs_from_matrix
from .dixon_coles import tau


def seed_for(key: str) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


def simulate(lh: float, la: float, rho: float, ht_share: float = 0.44,
             n: int = 10_000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    h1 = rng.poisson(lh * ht_share, n); a1 = rng.poisson(la * ht_share, n)
    h2 = rng.poisson(lh * (1 - ht_share), n); a2 = rng.poisson(la * (1 - ht_share), n)
    hg = h1 + h2; ag = a1 + a2
    w = tau(hg, ag, lh, la, rho)
    w = w / w.sum()

    cap = 6  # matris 0..5, sonrası ayrı
    m = np.zeros((cap + 4, cap + 4))
    np.add.at(m, (np.minimum(hg, cap + 3), np.minimum(ag, cap + 3)), w)
    probs = probs_from_matrix(m)

    def res(x, y):
        return np.where(x > y, "1", np.where(x == y, "X", "2"))
    ht = res(h1, a1); ft = res(hg, ag)
    htft = {k: 0.0 for k in HTFT_KEYS}
    keys = np.char.add(np.char.add(ht, "/"), ft)
    for k in HTFT_KEYS:
        htft[k] = float(w[keys == k].sum())

    small = m[:cap, :cap]
    flat = [(f"{i}-{j}", float(small[i, j])) for i in range(cap) for j in range(cap)]
    flat.sort(key=lambda t: -t[1])
    tot = hg + ag
    total_goals = [float(w[tot == k].sum()) for k in range(6)] + [float(w[tot >= 6].sum())]
    return {
        "lambda_home": round(lh, 3), "lambda_away": round(la, 3), "sims": n, "rho": round(rho, 4),
        "probs": {k: round(v, 4) for k, v in probs.items()},
        "htft": {k: round(v, 4) for k, v in htft.items()},
        "top_scores": [{"score": s, "p": round(p, 4)} for s, p in flat[:5]],
        "score_matrix": [[round(float(x), 4) for x in row] for row in small],
        "total_goals": [round(x, 4) for x in total_goals],
    }
