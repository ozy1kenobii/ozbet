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


def extra_markets(h1, a1, h2, a2, w) -> dict[str, float]:
    """iddaa'daki ek gol marketleri — hepsi aynı ağırlıklı 10.000 simülasyondan (Dixon-Coles τ dahil).

    Anahtarlar markets.EXTRA_LABELS ile aynıdır.
    """
    hg, ag = h1 + h2, a1 + a2
    t, t1, t2 = hg + ag, h1 + a1, h2 + a2
    P = lambda mask: float(w[mask].sum())  # noqa: E731
    out: dict[str, float] = {}
    # İlk yarı sonucu ve İY gol
    out["HT_1"], out["HT_X"], out["HT_2"] = P(h1 > a1), P(h1 == a1), P(h1 < a1)
    for ln in (0.5, 1.5, 2.5):
        out[f"HT_O{ln}"] = P(t1 > ln); out[f"HT_U{ln}"] = 1 - out[f"HT_O{ln}"]
    # İkinci yarı sonucu
    out["2H_1"], out["2H_X"], out["2H_2"] = P(h2 > a2), P(h2 == a2), P(h2 < a2)
    # En çok gol olacak yarı
    out["MGH_1"], out["MGH_X"], out["MGH_2"] = P(t1 > t2), P(t1 == t2), P(t1 < t2)
    # Toplam gol ek çizgiler
    for ln in (0.5, 4.5, 5.5):
        out[f"O{ln}"] = P(t > ln); out[f"U{ln}"] = 1 - out[f"O{ln}"]
    # Gol aralığı ve tek/çift
    out["G0-1"], out["G2-3"], out["G4-5"], out["G6+"] = P(t <= 1), P((t >= 2) & (t <= 3)), P((t >= 4) & (t <= 5)), P(t >= 6)
    out["ODD"] = P(t % 2 == 1); out["EVEN"] = 1 - out["ODD"]
    # Takım golleri
    for side, g in (("H", hg), ("A", ag)):
        for ln in (0.5, 1.5, 2.5):
            out[f"{side}_O{ln}"] = P(g > ln); out[f"{side}_U{ln}"] = 1 - out[f"{side}_O{ln}"]
    # Handikaplı MS (iddaa usulü 3 yollu: ev sahibine -1/-2 veya +1/+2 gol)
    for hc in (-2, -1, 1, 2):
        d = hg - ag + hc
        tag = f"{hc:+d}"
        out[f"HCP{tag}_1"], out[f"HCP{tag}_X"], out[f"HCP{tag}_2"] = P(d > 0), P(d == 0), P(d < 0)
    # MS + Alt/Üst 2.5 ve MS + KG
    res = {"1": hg > ag, "X": hg == ag, "2": hg < ag}
    both = (hg > 0) & (ag > 0)
    for r, m in res.items():
        out[f"{r}&O2.5"] = P(m & (t > 2)); out[f"{r}&U2.5"] = P(m & (t <= 2))
        out[f"{r}&BTTS_Y"] = P(m & both); out[f"{r}&BTTS_N"] = P(m & ~both)
    # KG + Alt/Üst 2.5
    out["BTTS_Y&O2.5"] = P(both & (t > 2)); out["BTTS_Y&U2.5"] = P(both & (t <= 2))
    out["BTTS_N&O2.5"] = P(~both & (t > 2)); out["BTTS_N&U2.5"] = P(~both & (t <= 2))
    # Her iki yarıda gol / ilk yarı KG
    out["HT_BTTS_Y"] = P((h1 > 0) & (a1 > 0)); out["HT_BTTS_N"] = 1 - out["HT_BTTS_Y"]
    out["BOTH_HALVES_O0.5"] = P((t1 > 0) & (t2 > 0))
    # Ev / deplasman yarı kazanır
    out["H_WIN_HALF"] = P((h1 > a1) | (h2 > a2)); out["A_WIN_HALF"] = P((a1 > h1) | (a2 > h2))
    # Gol yemeden kazanır
    out["H_WIN_NIL"] = P((hg > ag) & (ag == 0)); out["A_WIN_NIL"] = P((ag > hg) & (hg == 0))
    return out


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
        "extra": {k: round(v, 4) for k, v in extra_markets(h1, a1, h2, a2, w).items()},
    }
