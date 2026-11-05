"""Monte Carlo maç simülasyonu (Dixon-Coles τ ile önem ağırlıklı).

Her yarı ayrı Poisson: İY λ·s, İKY λ·(1-s). Tam skor üzerinde τ(x,y) ağırlığı uygulanır,
böylece hem İY/MS hem de Dixon-Coles düşük skor düzeltmesi tutarlı olur.
"""
from __future__ import annotations

import hashlib

import numpy as np

from ..markets import HTFT_KEYS, probs_from_matrix
from .dixon_coles import clamp_rho, tau


def seed_for(key: str) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


SAMPLE_N = 50
SAMPLE_NOTE = "50 örnek koşu yalnızca gösterim içindir; olasılıklar 10.000 simülasyondan hesaplanır."


def _minutes(rng: np.random.Generator, k: int, lo: int, hi: int, extra_max: int) -> list[tuple[int, int]]:
    """k gol için (dakika, uzatma) çiftleri: uniform lo..hi, %10 olasılıkla hi+1..hi+extra_max."""
    base = rng.integers(lo, hi + 1, k)
    stoppage = rng.random(k) < 0.10
    extra = rng.integers(1, extra_max + 1, k)
    return [(hi, int(e)) if st else (int(b), 0) for b, st, e in zip(base, stoppage, extra)]


def _fmt_min(m: int, e: int) -> int | str:
    return f"{m}+{e}" if e else m


def sample_runs(h1, a1, h2, a2, w, seed: int, n: int = SAMPLE_N) -> dict:
    """10.000'lik ağırlıklı örneklemden ağırlığa göre n maç seçer ve gol dakikalarını üretir.

    Yalnızca gösterim içindir; olasılıklar bu koşulardan hesaplanmaz.
    """
    rng = np.random.default_rng([seed, n, 0x5A])   # ana Monte Carlo akışından bağımsız, maç tohumuna bağlı
    idx = rng.choice(len(w), size=n, replace=True, p=w)
    runs = []
    res = {"1": 0, "X": 0, "2": 0}
    o25 = btts = 0
    scores: dict[str, int] = {}
    for i, j in enumerate(idx, start=1):
        hh1, aa1, hh2, aa2 = int(h1[j]), int(a1[j]), int(h2[j]), int(a2[j])
        goals = []
        for (hk, ak, lo, hi, ex) in ((hh1, aa1, 1, 45, 4), (hh2, aa2, 46, 90, 5)):
            sides = ["home"] * hk + ["away"] * ak
            mins = _minutes(rng, hk + ak, lo, hi, ex)
            half = sorted(zip(mins, sides), key=lambda t: (t[0][0], t[0][1]))
            goals += [{"min": _fmt_min(*m), "side": sd} for m, sd in half]
        hg, ag = hh1 + hh2, aa1 + aa2
        runs.append({"i": i, "ft": [hg, ag], "ht": [hh1, aa1], "goals": goals})
        res["1" if hg > ag else "X" if hg == ag else "2"] += 1
        o25 += hg + ag > 2
        btts += hg > 0 and ag > 0
        key = f"{hg}-{ag}"
        scores[key] = scores.get(key, 0) + 1
    top = sorted(scores.items(), key=lambda t: (-t[1], t[0]))[:5]
    return {
        "n": n, "runs": runs,
        "summary": {**res, "O2.5": int(o25), "BTTS_Y": int(btts), "top_scores": [[s, c] for s, c in top]},
        "note": SAMPLE_NOTE,
    }


def simulate(lh: float, la: float, rho: float, ht_share: float = 0.44,
             n: int = 10_000, seed: int = 0) -> dict:
    rho = clamp_rho(rho, lh, la)   # kupa çapraz λ'larında τ negatife düşmesin
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
        "sample_runs": sample_runs(h1, a1, h2, a2, w, seed),
    }
