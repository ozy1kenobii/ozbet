"""Piyasa-tabanlı λ: iddaa oranlarından (Shin ile adil olasılık) Dixon-Coles (λ_ev, λ_dep, ρ) uydurma.

Amaç: geçmiş verisi olmayan maçlarda da skor matrisi / İY-MS / ek marketler üretmek. Sonuç bağımsız bir
tahmin DEĞİLDİR; piyasanın 1X2 + Alt/Üst (+KG) fiyatlarının tutarlı bir skor dağılımına açılmış hâlidir.
Bu yüzden bu modelle "değer" etiketi üretilmez (piyasayı kendisiyle kıyaslamak olur).

Uydurma: Σ_grup KL(adil ‖ model) en küçüklenir; parametreler log λ_ev, log λ_dep, ρ (sınırlı).
İY oranı (İY 1X2 / İY Alt-Üst) varsa ht_share ayrıca 1-B uydurulur, yoksa 0.44.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

from ..agents.market import shin
from ..markets import probs_from_matrix
from .dixon_coles import clamp_rho, tau

NOTE = "Piyasa oranlarından türetildi; bağımsız tahmin değildir."
DEFAULT_HT_SHARE = 0.44
N = 11   # 0..10 gol
GOAL_GROUPS = {"ou15": ("O1.5", "U1.5"), "ou25": ("O2.5", "U2.5"), "ou35": ("O3.5", "U3.5"),
               "btts": ("BTTS_Y", "BTTS_N")}
HT_GROUPS = {"ht1x2": ("HT_1", "HT_X", "HT_2"), "ht_ou0.5": ("HT_O0.5", "HT_U0.5"),
             "ht_ou1.5": ("HT_O1.5", "HT_U1.5"), "ht_ou2.5": ("HT_O2.5", "HT_U2.5")}


def fair_probs(odds: dict, groups: dict) -> dict[str, dict[str, float]]:
    out = {}
    for g, keys in groups.items():
        vals = [odds.get(k) for k in keys]
        if all(isinstance(v, (int, float)) and v > 1.0 for v in vals):
            out[g] = dict(zip(keys, shin(vals)))
    return out


def score_matrix(lh: float, la: float, rho: float) -> np.ndarray:
    g = np.arange(N)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    m *= tau(g[:, None], g[None, :], lh, la, rho)
    return m / m.sum()


def _model_group_probs(m: np.ndarray) -> dict[str, float]:
    return probs_from_matrix(m)


def _kl(target: dict[str, dict[str, float]], p: dict[str, float]) -> float:
    s = 0.0
    for grp in target.values():
        for k, q in grp.items():
            s += q * math.log(max(q, 1e-9) / max(p[k], 1e-9))
    return s


def fit_lambdas(fair: dict[str, dict[str, float]]) -> tuple[float, float, float, float]:
    """fair: {"1x2": {...}, "ou25": {...}, ...} → (λ_ev, λ_dep, ρ, kalan KL)."""
    p1, p2 = fair["1x2"]["1"], fair["1x2"]["2"]
    tot0 = 2.6
    if "ou25" in fair:   # Poisson toplamdan kaba başlangıç
        o = fair["ou25"]["O2.5"]
        tot0 = float(minimize_scalar(lambda t: (1 - poisson.cdf(2, t) - o) ** 2, bounds=(0.3, 7), method="bounded").x)
    d0 = math.log(max(p1, 0.02) / max(p2, 0.02)) * 0.6
    x0 = [math.log(tot0 / 2) + d0 / 2, math.log(tot0 / 2) - d0 / 2, -0.05]

    def f(x):
        lh, la = math.exp(x[0]), math.exp(x[1])
        rho = clamp_rho(x[2], lh, la)
        return _kl(fair, _model_group_probs(score_matrix(lh, la, rho)))

    r = minimize(f, x0, method="L-BFGS-B", bounds=[(-3, 2.2), (-3, 2.2), (-0.25, 0.25)])
    lh, la = math.exp(r.x[0]), math.exp(r.x[1])
    return lh, la, clamp_rho(float(r.x[2]), lh, la), float(r.fun)


def fit_ht_share(lh: float, la: float, ht_fair: dict[str, dict[str, float]]) -> float:
    if not ht_fair:
        return DEFAULT_HT_SHARE
    g = np.arange(N)

    def f(s):
        m = np.outer(poisson.pmf(g, lh * s), poisson.pmf(g, la * s))
        h, a = g[:, None], g[None, :]
        t = h + a
        p = {"HT_1": m[h > a].sum(), "HT_X": np.trace(m), "HT_2": m[h < a].sum()}
        for ln in (0.5, 1.5, 2.5):
            p[f"HT_O{ln}"] = m[t > ln].sum(); p[f"HT_U{ln}"] = 1 - p[f"HT_O{ln}"]
        return _kl(ht_fair, p)

    return float(minimize_scalar(f, bounds=(0.30, 0.55), method="bounded").x)


def from_odds(odds: dict | None) -> dict | None:
    """iddaa oran sözlüğünden {lambda_home, lambda_away, rho, ht_share, fit_kl, used} ya da None.
    Gerekli: 1X2 + en az bir gol marketi (Alt/Üst 1.5/2.5/3.5 veya KG)."""
    if not odds:
        return None
    fair = fair_probs(odds, {"1x2": ("1", "X", "2"), **GOAL_GROUPS})
    if "1x2" not in fair or len(fair) < 2:
        return None
    lh, la, rho, kl = fit_lambdas(fair)
    ht_fair = fair_probs(odds, HT_GROUPS)
    hs = fit_ht_share(lh, la, ht_fair)
    return {"lambda_home": lh, "lambda_away": la, "rho": rho, "ht_share": hs, "fit_kl": kl,
            "used": sorted(fair) + sorted(ht_fair)}


def build_model(odds: dict | None, seed: int, sims: int = 10_000) -> dict | None:
    """Piyasa-tabanlı tam model sözlüğü (simulate çıktısı + kaynak notları)."""
    from .simulate import simulate
    fit = from_odds(odds)
    if not fit:
        return None
    sim = simulate(fit["lambda_home"], fit["lambda_away"], fit["rho"], fit["ht_share"], sims, seed)
    sim.update({
        "source": "piyasa", "method": "market", "data_quality": "market",
        "ht_share": round(fit["ht_share"], 3), "fit_kl": round(fit["fit_kl"], 5), "fit_markets": fit["used"],
        "notes": [NOTE], "n_matches": {"home": 0, "away": 0},
    })
    return sim


# ---------------------------------------------------------------- iç tutarlılık
def consistency(odds: dict | None, model: dict | None, top: int = 5) -> list[dict]:
    """Ana marketler dışındaki iddaa oranlarını piyasa-tabanlı adil olasılıkla kıyaslar.
    EV = p·oran − 1 (genelde negatif). En yüksek EV'li ilk `top` satır: "bu maçta fiyatı en iyi seçenekler"."""
    if not odds or not model:
        return []
    from ..markets import all_labels, all_probs
    p = all_probs(model)
    skip = {"1", "X", "2", "1X", "X2", "12", "O1.5", "U1.5", "O2.5", "U2.5", "O3.5", "U3.5", "BTTS_Y", "BTTS_N"}
    labels = all_labels()
    rows = []
    for k, o in odds.items():
        if k in skip or k.startswith(("C_", "K_", "CR_", "KR_")) or not isinstance(o, (int, float)) or o <= 1:
            continue
        q = p.get(k)
        if q is None or q < 0.03:   # çok küçük olasılıklarda simülasyon gürültüsü EV'yi bozar
            continue
        rows.append({"market": k, "label": labels.get(k, k), "odds": round(float(o), 2),
                     "fair_p": round(float(q), 4), "ev": round(float(q) * o - 1, 4)})
    rows.sort(key=lambda r: -r["ev"])
    return rows[:top]
