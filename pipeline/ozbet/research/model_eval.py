"""Model olasılık kalitesi araştırması (protokol: /home/claude/fd-PROTOKOL.md).

    python -m ozbet.research.model_eval --fd /home/claude/fd [--test]

Aşamalar
1. Walk-forward (haftalık) Dixon-Coles tahminleri, birkaç hiperparametre yapılandırması
   (ξ, L2, takım bazlı ev avantajı, promote takım öncülü, isabetli şut harmanı).
   Eğitim penceresi: hafta başından önceki son 1100 gün; yalnız geçmiş maçlar.
2. Piyasa girdisi: Pinnacle AÇILIŞ oranı (Shin). Kapanış yalnız kıyas.
   - doğrusal harman  p = α·model + (1-α)·piyasa
   - λ-harmanı: açılış oranından ters çözülmüş (λh, λa) ile log-λ harmanı
   - stacking: koşullu logit  P(k) ∝ exp(c_k + β_m·log p_m,k + β_q·log q_k [+ lig/oran aralığı etkileşimi yok])
     2.5 Alt/Üst için ikili logit (logit p_m, logit q). Stacking 2122–2324 tahminleriyle kurulur.
3. Seçim doğrulama (2425) log-loss'una göre. Kilitli test (2526+2627) yalnız --test ile, tek yapılandırma.
4. Değer kuralı: EV = p·oran − 1 ≥ e; e doğrulamada (iddaa benzetimi fiyatı) seçilir. ROI üç fiyatla.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.stats import poisson

LEAGUES = ["T1", "E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1"]
SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
DEV, VAL, TEST = ("2122", "2223", "2324"), ("2425",), ("2526", "2627")
IDDAA_MARGIN = {"1x2": 0.20, "ou": 0.18}
G = 11


# ---------------------------------------------------------------- veri
def _f(x):
    try:
        v = float(x)
        return v if v > 1.0 else np.nan
    except (TypeError, ValueError):
        return np.nan


def _date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def load(fd: Path, lg: str) -> dict:
    rows = []
    for s in SEASONS:
        p = fd / f"{lg}_{s}.csv"
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                d = _date(r.get("Date") or "")
                if not d or not r.get("FTHG") or not r.get("HomeTeam"):
                    continue
                try:
                    hg, ag = int(r["FTHG"]), int(r["FTAG"])
                except ValueError:
                    continue
                g = lambda *ks: [_f(r.get(k)) for k in ks]  # noqa: E731
                rows.append(dict(
                    season=s, date=np.datetime64(d, "D"), home=r["HomeTeam"].strip(), away=r["AwayTeam"].strip(),
                    hg=hg, ag=ag,
                    hst=_f(r.get("HST")) if r.get("HST") not in (None, "") else np.nan,
                    ast=_f(r.get("AST")) if r.get("AST") not in (None, "") else np.nan,
                    ps=g("PSH", "PSD", "PSA"), psc=g("PSCH", "PSCD", "PSCA"),
                    mx=g("MaxH", "MaxD", "MaxA"), av=g("AvgH", "AvgD", "AvgA"),
                    pou=g("P>2.5", "P<2.5"), pcou=g("PC>2.5", "PC<2.5"),
                    mxou=g("Max>2.5", "Max<2.5"), avou=g("Avg>2.5", "Avg<2.5"),
                ))
    rows.sort(key=lambda r: r["date"])
    # HST/AST 0 olabilir: _f >1 filtresi yerine ham değer
    teams = sorted({r["home"] for r in rows} | {r["away"] for r in rows})
    ix = {t: i for i, t in enumerate(teams)}
    A = lambda k: np.array([r[k] for r in rows], float)  # noqa: E731
    out = dict(lg=lg, n_teams=len(teams), season=np.array([r["season"] for r in rows]),
               date=np.array([r["date"] for r in rows]), hi=np.array([ix[r["home"]] for r in rows]),
               ai=np.array([ix[r["away"]] for r in rows]), hg=A("hg"), ag=A("ag"))
    for k in ("ps", "psc", "mx", "av", "pou", "pcou", "mxou", "avou"):
        out[k] = np.array([r[k] for r in rows], float)
    out["hst"], out["ast"] = _shots(fd, lg, rows)
    return out


def _shots(fd, lg, rows):
    m = {}
    for s in SEASONS:
        p = fd / f"{lg}_{s}.csv"
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                d = _date(r.get("Date") or "")
                try:
                    m[(d, (r.get("HomeTeam") or "").strip())] = (float(r["HST"]), float(r["AST"]))
                except (KeyError, TypeError, ValueError):
                    pass
    hs = np.array([m.get((r["date"].astype(object), r["home"]), (np.nan, np.nan))[0] for r in rows])
    as_ = np.array([m.get((r["date"].astype(object), r["home"]), (np.nan, np.nan))[1] for r in rows])
    return hs, as_


# ---------------------------------------------------------------- olasılık yardımcıları
def shin_v(odds: np.ndarray) -> np.ndarray:
    """Vektörel Shin: odds (N,K) → adil olasılık (N,K); NaN satırlar NaN."""
    pi = 1 / odds
    S = pi.sum(1, keepdims=True)
    lo = np.zeros_like(S); hi = np.full_like(S, 0.4)

    def pr(z):
        return (np.sqrt(z * z + 4 * (1 - z) * pi * pi / S) - z) / (2 * (1 - z))
    for _ in range(50):
        mid = (lo + hi) / 2
        big = pr(mid).sum(1, keepdims=True) > 1
        lo = np.where(big, mid, lo); hi = np.where(big, hi, mid)
    p = pr((lo + hi) / 2)
    p = p / p.sum(1, keepdims=True)
    return np.where(S <= 1, pi / S, p)


def shin_inverse(p: np.ndarray, margin: float) -> np.ndarray:
    """Adil olasılıktan Shin modeliyle toplamı 1+margin olan ima olasılık → oran."""
    S = 1 + margin
    lo = np.zeros((len(p), 1)); hi = np.full((len(p), 1), 0.5)
    for _ in range(50):
        z = (lo + hi) / 2
        s = np.sqrt(S * ((1 - z) * p * p + z * p)).sum(1, keepdims=True)
        big = s > S
        hi = np.where(big, z, hi); lo = np.where(big, lo, z)
    z = (lo + hi) / 2
    pi = np.sqrt(S * ((1 - z) * p * p + z * p))
    return 1 / pi


def tau_m(lh, la, rho):
    rho = np.broadcast_to(rho, lh.shape)
    t = np.ones((len(lh), G, G))
    t[:, 0, 0] = 1 - lh * la * rho
    t[:, 0, 1] = 1 + lh * rho
    t[:, 1, 0] = 1 + la * rho
    t[:, 1, 1] = 1 - rho
    return np.clip(t, 1e-6, None)


def probs(lh, la, rho):
    """(N,) λ'lar → 1X2 (N,3) ve Üst2.5 (N,)."""
    x = np.arange(G)
    m = poisson.pmf(x[None, :, None], lh[:, None, None]) * poisson.pmf(x[None, None, :], la[:, None, None])
    rho = np.broadcast_to(rho, lh.shape)
    lo = np.maximum(-1 / lh, -1 / la); hi = np.minimum(1 / (lh * la), 1)
    r = np.clip(rho, lo + 1e-6, hi - 1e-6)
    m = m * tau_m(lh, la, r)
    m /= m.sum((1, 2), keepdims=True)
    i, j = np.meshgrid(x, x, indexing="ij")
    p1 = (m * (i > j)).sum((1, 2)); px = (m * (i == j)).sum((1, 2)); p2 = (m * (i < j)).sum((1, 2))
    po = (m * (i + j > 2)).sum((1, 2))
    return np.stack([p1, px, p2], 1), po


class LambdaInverter:
    """Açılış oranından (1X2 + 2.5 Ü/A Shin) λh, λa'yı ızgara+KD-ağaç ile ters çözer (ρ=-0.05)."""

    def __init__(self):
        g = np.arange(0.15, 4.0, 0.02)
        LH, LA = np.meshgrid(g, g, indexing="ij")
        self.lh, self.la = LH.ravel(), LA.ravel()
        p, po = probs(self.lh, self.la, np.full(self.lh.shape, -0.05))
        self.tree = cKDTree(np.c_[p[:, 0], p[:, 2], po])

    def __call__(self, q, qo):
        qo = np.where(np.isnan(qo), 0.5, qo)
        _, k = self.tree.query(np.c_[q[:, 0], q[:, 2], qo])
        return self.lh[k], self.la[k]


# ---------------------------------------------------------------- DC kurulumu
def fit_poisson(hi, ai, hg, ag, w, n, l2, team_home, prior_a, prior_d, p0=None, l2_home=2.0):
    """[μ, h, a(n), d(n), (hteam(n))]; L2 öncül merkezi prior_a/prior_d (promote takımı için)."""
    def f(p):
        mu, h = p[0], p[1]
        a = p[2:2 + n]; d = p[2 + n:2 + 2 * n]
        ht = p[2 + 2 * n:] if team_home else None
        lh = mu + h + a[hi] + d[ai] + (ht[hi] if team_home else 0)
        la = mu + a[ai] + d[hi]
        eh, ea = np.exp(lh), np.exp(la)
        nll = np.sum(w * (eh - hg * lh)) + np.sum(w * (ea - ag * la))
        nll += l2 * (np.sum((a - prior_a) ** 2) + np.sum((d - prior_d) ** 2))
        rh, ra = w * (eh - hg), w * (ea - ag)
        g = np.zeros_like(p)
        g[0] = rh.sum() + ra.sum(); g[1] = rh.sum()
        g[2:2 + n] = np.bincount(hi, rh, n) + np.bincount(ai, ra, n) + 2 * l2 * (a - prior_a)
        g[2 + n:2 + 2 * n] = np.bincount(ai, rh, n) + np.bincount(hi, ra, n) + 2 * l2 * (d - prior_d)
        if team_home:
            nll += l2_home * np.sum(ht ** 2)
            g[2 + 2 * n:] = np.bincount(hi, rh, n) + 2 * l2_home * ht
        return nll, g
    k = 2 + 2 * n + (n if team_home else 0)
    if p0 is None or len(p0) != k:
        p0 = np.zeros(k); p0[0] = np.log(max((w @ hg + w @ ag) / (2 * w.sum()), 0.1))
    return minimize(f, p0, jac=True, method="L-BFGS-B").x


def fit_rho(lh, la, hg, ag, w):
    low = (hg <= 1) & (ag <= 1)
    lh, la, x, y, w = lh[low], la[low], hg[low], ag[low], w[low]
    rs = np.linspace(-0.25, 0.15, 41)
    best, br = np.inf, 0.0
    for r in rs:
        t = np.where((x == 0) & (y == 0), 1 - lh * la * r,
            np.where((x == 0) & (y == 1), 1 + lh * r, np.where((x == 1) & (y == 0), 1 + la * r, 1 - r)))
        v = -np.sum(w * np.log(np.clip(t, 1e-6, None)))
        if v < best:
            best, br = v, r
    return br


def walk_forward(D: dict, cfg: dict, eval_seasons) -> dict:
    """Haftalık yürüyen tahmin. Döner: idx, lh, la, rho, (şut) slh, sla."""
    xi, l2, th, promo = cfg["xi"], cfg["l2"], cfg.get("team_home", False), cfg.get("promo", 0.0)
    n = D["n_teams"]
    ev = np.where(np.isin(D["season"], eval_seasons))[0]
    out = {k: np.full(len(D["date"]), np.nan) for k in ("lh", "la", "rho", "slh", "sla", "cnt")}
    if not len(ev):
        return out
    dates = D["date"]
    p0 = s0 = None
    week = dates[ev[0]]
    last = dates[ev[-1]]
    while week <= last:
        nxt = week + np.timedelta64(7, "D")
        tgt = ev[(dates[ev] >= week) & (dates[ev] < nxt)]
        if len(tgt):
            tr = np.where((dates < week) & (dates >= week - np.timedelta64(1100, "D")))[0]
            if len(tr) >= 60:
                hi, ai = D["hi"][tr], D["ai"][tr]
                age = (week - dates[tr]).astype(float)
                w = np.exp(-xi * age)
                cnt = np.bincount(hi, minlength=n) + np.bincount(ai, minlength=n)
                # promote öncülü: hedef haftadaki, son 365 günde ligde <10 maçı olan takım
                recent = tr[age <= 365]
                rc = np.bincount(D["hi"][recent], minlength=n) + np.bincount(D["ai"][recent], minlength=n)
                new = (rc < 10).astype(float)
                pa, pd_ = -promo * new, promo * new
                p0 = fit_poisson(hi, ai, D["hg"][tr], D["ag"][tr], w, n, l2, th, pa, pd_, p0)
                mu, h = p0[0], p0[1]; a = p0[2:2 + n]; d = p0[2 + n:2 + 2 * n]
                ht = p0[2 + 2 * n:] if th else np.zeros(n)
                lh_tr = np.exp(mu + h + a[hi] + d[ai] + ht[hi]); la_tr = np.exp(mu + a[ai] + d[hi])
                rho = fit_rho(lh_tr, la_tr, D["hg"][tr], D["ag"][tr], w)
                th_, ta_ = D["hi"][tgt], D["ai"][tgt]
                # promote takım hiç maçı yoksa a=prior (L2 merkezi) — fit zaten oraya çeker
                out["lh"][tgt] = np.exp(mu + h + a[th_] + d[ta_] + ht[th_])
                out["la"][tgt] = np.exp(mu + a[ta_] + d[th_])
                out["rho"][tgt] = rho
                out["cnt"][tgt] = np.minimum(cnt[th_], cnt[ta_])
                ok = ~np.isnan(D["hst"][tr]) & ~np.isnan(D["ast"][tr])
                if ok.sum() >= 60 and cfg.get("shots", True):
                    t2 = tr[ok]
                    s0 = fit_poisson(D["hi"][t2], D["ai"][t2], D["hst"][t2], D["ast"][t2], w[ok], n, l2,
                                     False, pa, pd_, s0)
                    conv = (w[ok] @ (D["hg"][t2] + D["ag"][t2])) / max(w[ok] @ (D["hst"][t2] + D["ast"][t2]), 1e-9)
                    sa, sd = s0[2:2 + n], s0[2 + n:]
                    out["slh"][tgt] = np.exp(s0[0] + s0[1] + sa[th_] + sd[ta_]) * conv
                    out["sla"][tgt] = np.exp(s0[0] + sa[ta_] + sd[th_]) * conv
        week = nxt
    return out


# ---------------------------------------------------------------- stacking
def _ll(P, y):
    return -np.mean(np.log(np.clip(P[np.arange(len(y)), y], 1e-12, None)))


def _brier(P, y):
    Y = np.eye(P.shape[1])[y]
    return np.mean(((P - Y) ** 2).sum(1))


def stack_feats(pm, q, spread):
    lpm, lq = np.log(np.clip(pm, 1e-6, 1)), np.log(np.clip(q, 1e-6, 1))
    return lpm, lq, spread


def stack_fit(pm, q, spread, y, reg=1e-3):
    """P_k ∝ exp(c_k + (b_m + b_ms·s)·log pm_k + (b_q + b_qs·s)·log q_k) ; s = oran aralığı (fav. gücü)."""
    lpm, lq, s = stack_feats(pm, q, spread)

    def P(th):
        c = np.array([0.0, th[0], th[1]])
        bm = th[2] + th[3] * s[:, None]; bq = th[4] + th[5] * s[:, None]
        z = c + bm * lpm + bq * lq
        z -= z.max(1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(1, keepdims=True)

    def f(th):
        return _ll(P(th), y) + reg * np.sum(th[[3, 5]] ** 2)
    th = minimize(f, np.array([0, 0, 0.3, 0, 0.7, 0]), method="BFGS").x
    return th, P


def stack_apply(th, pm, q, spread):
    lpm, lq, s = stack_feats(pm, q, spread)
    c = np.array([0.0, th[0], th[1]])
    z = c + (th[2] + th[3] * s[:, None]) * lpm + (th[4] + th[5] * s[:, None]) * lq
    z -= z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def ou_fit(pm, q, y):
    X = np.c_[np.ones_like(pm), logit(pm), logit(q)]

    def f(b):
        z = X @ b
        return np.mean(np.logaddexp(0, z) - y * z)
    return minimize(f, np.array([0, 0.3, 0.7]), method="BFGS").x


def ou_apply(b, pm, q):
    return 1 / (1 + np.exp(-(np.c_[np.ones_like(pm), logit(pm), logit(q)] @ b)))


# ---------------------------------------------------------------- ROI
def bootstrap_ci(r, B=2000, seed=0):
    if len(r) < 2:
        return (None, None)
    rng = np.random.default_rng(seed)
    m = r[rng.integers(0, len(r), (B, len(r)))].mean(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def bets(p, odds, won, edge, pmin=0.0):
    """EV = p·oran − 1 ≥ edge. p, odds, won: (N,K). Döner: maske (N,K)."""
    return (p * odds - 1 >= edge) & (p >= pmin) & ~np.isnan(odds) & ~np.isnan(p)


def roi_table(mask, odds, won, clv_open, clv_close, season, lg):
    o = odds[mask]; wv = won[mask]
    r = np.where(wv, o - 1, -1.0)
    n = int(mask.sum())
    if not n:
        return {"n": 0}
    lo, hi = bootstrap_ci(r)
    co, cc = clv_open[mask], clv_close[mask]
    ok = ~np.isnan(co) & ~np.isnan(cc)
    ss, ll_ = season[mask], lg[mask]
    by_s = {}
    for s in np.unique(ss):
        k = ss == s
        by_s[str(s)] = {"n": int(k.sum()), "roi": round(float(r[k].mean()), 4)}
    by_l = {}
    for l_ in np.unique(ll_):
        k = ll_ == l_
        by_l[str(l_)] = {"n": int(k.sum()), "roi": round(float(r[k].mean()), 4)}
    worst = min(by_s.items(), key=lambda kv: kv[1]["roi"])
    return {"n": n, "hit": round(float(wv.mean()), 4), "avg_odds": round(float(o.mean()), 3),
            "roi": round(float(r.mean()), 4), "ci95": [None if lo is None else round(lo, 4), None if hi is None else round(hi, 4)],
            "clv_pinnacle": round(float((co[ok] / cc[ok] - 1).mean()), 4) if ok.any() else None,
            "by_season": by_s, "by_league": by_l, "worst_season": worst[0]}


# ---------------------------------------------------------------- ana akış
CONFIGS = {
    "base":      dict(xi=0.0019, l2=0.5),
    "xi0012":    dict(xi=0.0012, l2=0.5),
    "xi0028":    dict(xi=0.0028, l2=0.5),
    "l2_02":     dict(xi=0.0019, l2=0.2),
    "l2_10":     dict(xi=0.0019, l2=1.0),
    "teamhome":  dict(xi=0.0019, l2=0.5, team_home=True),
    "promo":     dict(xi=0.0019, l2=0.5, promo=0.25),
}
SHOT_WS = (0.0, 0.2, 0.4, 0.6)
ALPHAS = (1.0, 0.5, 0.25, 0.1, 0.0)
EDGES = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15)


def build(fd: Path, configs, cache: Path | None):
    seasons = DEV + VAL + TEST
    allD = [load(fd, lg) for lg in LEAGUES]
    pred = {}
    for name, cfg in configs.items():
        cp = cache / f"wf_{name}.npz" if cache else None
        if cp and cp.exists():
            pred[name] = dict(np.load(cp)); continue
        t = time.time()
        parts = [walk_forward(D, dict(cfg, shots=(name == "base")), seasons) for D in allD]
        pred[name] = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
        if cp:
            np.savez(cp, **pred[name])
        print(f"[wf] {name}: {time.time() - t:.0f} s", flush=True)
    cat = lambda k: np.concatenate([D[k] for D in allD])  # noqa: E731
    base = {k: cat(k) for k in ("season", "hg", "ag", "ps", "psc", "mx", "av", "pou", "pcou", "mxou", "avou")}
    base["lg"] = np.concatenate([np.full(len(D["date"]), D["lg"]) for D in allD])
    return base, pred


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fd", default="/home/claude/fd")
    ap.add_argument("--cache", default=None, help="walk-forward ara sonuç klasörü (npz)")
    ap.add_argument("--test", action="store_true", help="KİLİTLİ testi koş (yalnız bir kez)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cache = Path(a.cache) if a.cache else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    B, P = build(Path(a.fd), CONFIGS, cache)
    hg, ag, season = B["hg"], B["ag"], B["season"]
    y = np.where(hg > ag, 0, np.where(hg == ag, 1, 2)); yo = (hg + ag > 2).astype(float)
    # piyasa: Pinnacle açılış (yoksa Avg) Shin; kapanış Pinnacle Shin
    op = np.where(np.isnan(B["ps"]).any(1, keepdims=True), B["av"], B["ps"])
    opo = np.where(np.isnan(B["pou"]).any(1, keepdims=True), B["avou"], B["pou"])
    q, qo = shin_v(op), shin_v(opo)[:, 0]
    qc, qco = shin_v(B["psc"]), shin_v(B["pcou"])[:, 0]
    spread = np.abs(q[:, 0] - q[:, 2])
    inv = LambdaInverter()
    have = ~np.isnan(q).any(1) & ~np.isnan(qc).any(1) & ~np.isnan(qo) & ~np.isnan(qco)
    have &= ~np.isnan(P["base"]["lh"])
    for k in P:
        have &= ~np.isnan(P[k]["lh"])
    have &= ~np.isnan(P["base"]["slh"])
    mlh, mla = np.full(len(y), np.nan), np.full(len(y), np.nan)
    mlh[have], mla[have] = inv(q[have], qo[have])

    dev = have & np.isin(season, DEV); val = have & np.isin(season, VAL); tst = have & np.isin(season, TEST)
    print(f"maç: dev={dev.sum()} val={val.sum()} test={tst.sum()}")
    res = {"n": {"dev": int(dev.sum()), "val": int(val.sum()), "test": int(tst.sum())}, "val": {}}

    def score(name, p3, po, m):
        return {"ll": round(_ll(p3[m], y[m]), 4), "brier": round(_brier(p3[m], y[m]), 4),
                "ou_ll": round(float(-np.mean(yo[m] * np.log(po[m]) + (1 - yo[m]) * np.log(1 - po[m]))), 4),
                "ou_brier": round(float(np.mean((po[m] - yo[m]) ** 2)), 4)}

    cand = {}   # ad → fonksiyon(maske) → (p3, po)
    full = np.ones(len(y), bool)

    def model_probs(cfg, w):
        pr = P[cfg]; bp = P["base"]
        lh = (1 - w) * pr["lh"] + w * bp["slh"]; la = (1 - w) * pr["la"] + w * bp["sla"]
        p3 = np.full((len(y), 3), np.nan); po = np.full(len(y), np.nan)
        p3[have], po[have] = probs(lh[have], la[have], pr["rho"][have])
        return p3, po

    tbl = []
    res["market_open"] = score("q", q, qo, val); res["market_close"] = score("qc", qc, qco, val)
    MP = {}
    for cfg in CONFIGS:
        for w in SHOT_WS:
            MP[(cfg, w)] = model_probs(cfg, w)
            s = score(cfg, *MP[(cfg, w)], val)
            tbl.append({"config": cfg, "shot_w": w, **s})
    tbl.sort(key=lambda r: r["ll"])
    res["val"]["dc_grid"] = tbl
    best_dc = (tbl[0]["config"], tbl[0]["shot_w"])
    res["best_dc"] = best_dc
    print("en iyi DC:", tbl[0], "\nmevcut (base,0.4):", [r for r in tbl if r["config"] == "base" and r["shot_w"] == 0.4][0])

    # harmanlar (her biri hem mevcut üretim modeli hem en iyi DC ile)
    for tag, key in (("prod", ("base", 0.4)), ("best", best_dc)):
        pm, pmo = MP[key]
        for al in ALPHAS:
            cand[f"{tag}_lin{al}"] = (al * pm + (1 - al) * q, al * pmo + (1 - al) * qo)
        # λ-harmanı (log-λ)
        pr = P[key[0]]; bp = P["base"]
        lh = (1 - key[1]) * pr["lh"] + key[1] * bp["slh"]; la = (1 - key[1]) * pr["la"] + key[1] * bp["sla"]
        for al in (0.5, 0.25, 0.1):
            p3 = np.full((len(y), 3), np.nan); po = np.full(len(y), np.nan)
            blh = np.exp(al * np.log(lh) + (1 - al) * np.log(mlh)); bla = np.exp(al * np.log(la) + (1 - al) * np.log(mla))
            p3[have], po[have] = probs(blh[have], bla[have], pr["rho"][have])
            cand[f"{tag}_lam{al}"] = (p3, po)
        # stacking (dev'de kurulur)
        th, _ = stack_fit(pm[dev], q[dev], spread[dev], y[dev])
        b = ou_fit(pmo[dev], qo[dev], yo[dev])
        p3 = np.full((len(y), 3), np.nan); po = np.full(len(y), np.nan)
        p3[have] = stack_apply(th, pm[have], q[have], spread[have]); po[have] = ou_apply(b, pmo[have], qo[have])
        cand[f"{tag}_stack"] = (p3, po)
        res[f"{tag}_stack_params"] = {"1x2": np.round(th, 4).tolist(), "ou": np.round(b, 4).tolist()}
        # yalnız piyasa kalibrasyonu (kontrol)
    th_q, _ = stack_fit(q[dev], q[dev], spread[dev], y[dev])
    p3 = np.full((len(y), 3), np.nan); p3[have] = stack_apply(th_q, q[have], q[have], spread[have])
    cand["market_recal"] = (p3, qo)
    bt = []
    for k, (p3, po) in cand.items():
        bt.append({"cand": k, **score(k, p3, po, val)})
    bt.sort(key=lambda r: r["ll"] + r["ou_ll"])
    res["val"]["blends"] = bt
    for r in bt[:8]:
        print(r)

    # ---- değer kuralı: iddaa benzetimi fiyatıyla doğrulamada eşik seçimi
    sel = bt[0]["cand"]
    res["selected"] = sel
    p3, po = cand[sel]
    pk = np.c_[p3, po, 1 - po]
    won = np.c_[y == 0, y == 1, y == 2, yo == 1, yo == 0]
    prices = {
        "max": np.c_[B["mx"], B["mxou"]],
        "avg": np.c_[B["av"], B["avou"]],
        "iddaa": np.c_[np.where(have[:, None], shin_inverse(np.nan_to_num(q, nan=1 / 3), IDDAA_MARGIN["1x2"]), np.nan),
                       np.where(have[:, None], shin_inverse(np.c_[np.nan_to_num(qo, nan=.5), 1 - np.nan_to_num(qo, nan=.5)],
                                                            IDDAA_MARGIN["ou"]), np.nan)],
    }
    clv_o = np.c_[B["ps"], B["pou"]]; clv_c = np.c_[B["psc"], B["pcou"]]
    lgv = B["lg"]
    edges_val = {}
    for pname, odds in prices.items():
        rows = []
        for e in EDGES:
            m = bets(pk, odds, won, e) & val[:, None]
            r = roi_table(m, odds, won, clv_o, clv_c, np.repeat(season[:, None], 5, 1), np.repeat(lgv[:, None], 5, 1))
            rows.append({"edge": e, **{k: r.get(k) for k in ("n", "hit", "avg_odds", "roi", "ci95")}})
        res["val"][f"roi_{pname}"] = rows
        ok = [r for r in rows if (r["n"] or 0) >= 150]
        edges_val[pname] = max(ok, key=lambda r: r["roi"])["edge"] if ok else EDGES[-1]
    res["edge_selected"] = edges_val
    res["configs_tried"] = {"dc": len(tbl), "blends": len(bt), "edges": len(EDGES) * 3}

    if a.test:
        res["test"] = {"model_dc": score("dc", *MP[best_dc], tst), "model_prod": score("prod", *MP[("base", 0.4)], tst),
                       "prod_lin0.25": score("x", *cand["prod_lin0.25"], tst),
                       "selected": score(sel, p3, po, tst),
                       "market_open": score("q", q, qo, tst), "market_close": score("qc", qc, qco, tst)}
        for pname, odds in prices.items():
            m = bets(pk, odds, won, edges_val[pname]) & tst[:, None]
            res["test"][f"roi_{pname}"] = roi_table(m, odds, won, clv_o, clv_c, np.repeat(season[:, None], 5, 1),
                                                    np.repeat(lgv[:, None], 5, 1))
            # mevcut üretim kuralı kıyası: prod_lin0.25, edge 0.05 (ima olasılık farkı) — aynı fiyat
            pp3, ppo = cand["prod_lin0.25"]
            ppk = np.c_[pp3, ppo, 1 - ppo]; qk = np.c_[q, qo, 1 - qo]
            m2 = (ppk - qk >= 0.05) & ~np.isnan(odds) & tst[:, None]
            res["test"][f"roi_{pname}_prod_rule"] = roi_table(m2, odds, won, clv_o, clv_c,
                                                              np.repeat(season[:, None], 5, 1), np.repeat(lgv[:, None], 5, 1))
        print(json.dumps(res["test"], indent=1, ensure_ascii=False))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    main()
