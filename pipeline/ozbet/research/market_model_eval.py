"""Piyasa-tabanlı λ doğrulaması: Pinnacle açılış 1X2 + 2.5 A/Ü → (λ, ρ) uydur → gol marketleri kalibrasyonu,
lig Dixon-Coles modeli (walk-forward, base) ile kıyas. Kilitli test sezonları (2526, 2627) KULLANILMAZ.

    python -m ozbet.research.market_model_eval --fd /home/claude/fd
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import poisson

from ..model import market_lambda as ml
from ..model.dixon_coles import clamp_rho
from . import model_eval as me

SEASONS_DEV, SEASONS_VAL = ["2021", "2122", "2223", "2324"], ["2425"]
HT_SHARE = ml.DEFAULT_HT_SHARE


def _ht(fd: Path, lg: str) -> dict:
    out = {}
    for s in SEASONS_DEV + SEASONS_VAL:
        p = fd / f"{lg}_{s}.csv"
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                d = me._date(r.get("Date") or "")
                try:
                    out[(np.datetime64(d, "D"), r["HomeTeam"].strip())] = (int(r["HTHG"]), int(r["HTAG"]))
                except (TypeError, ValueError, KeyError):
                    pass
    return out


def _metrics(lh, la, rho, hg, ag, ht):
    """Tek maç için log-kayıplar (doğal log)."""
    m = ml.score_matrix(lh, la, clamp_rho(rho, lh, la))
    g = np.arange(ml.N)
    tot = g[:, None] + g[None, :]
    eps = 1e-12
    out = {}
    p1, px = m[g[:, None] > g[None, :]].sum(), np.trace(m)
    p = {"1": p1, "X": px, "2": 1 - p1 - px}
    out["1x2"] = -np.log(max(p["1" if hg > ag else "X" if hg == ag else "2"], eps))
    po = m[tot > 2.5].sum()
    out["ou25"] = -np.log(max(po if hg + ag > 2 else 1 - po, eps))
    py = m[1:, 1:].sum()
    out["btts"] = -np.log(max(py if hg > 0 and ag > 0 else 1 - py, eps))
    tg = [m[tot == k].sum() for k in range(6)] + [m[tot >= 6].sum()]
    out["total"] = -np.log(max(tg[min(hg + ag, 6)], eps))
    sc = m[hg, ag] if hg <= 5 and ag <= 5 else 1 - m[:6, :6].sum()
    out["score"] = -np.log(max(sc, eps))
    if ht:
        mh = np.outer(poisson.pmf(g, lh * HT_SHARE), poisson.pmf(g, la * HT_SHARE))
        q = {"1": mh[g[:, None] > g[None, :]].sum(), "X": np.trace(mh)}
        q["2"] = 1 - q["1"] - q["X"]
        out["ht"] = -np.log(max(q["1" if ht[0] > ht[1] else "X" if ht[0] == ht[1] else "2"], eps))
    return out


def run(fd: Path) -> dict:
    res = {}
    for lg in me.LEAGUES:
        D = me.load(fd, lg)
        wf = me.walk_forward(D, dict(me.CONFIGS["base"], shots=False), SEASONS_DEV + SEASONS_VAL)
        HT = _ht(fd, lg)
        teams = _teams(fd, lg)   # load() ile aynı sıralı takım listesi (İY eşlemesi için)
        for i in range(len(D["date"])):
            s = str(D["season"][i])
            if s not in SEASONS_DEV + SEASONS_VAL or np.isnan(wf["lh"][i]):
                continue
            ps, pou = D["ps"][i], D["pou"][i]
            if np.isnan(ps).any() or np.isnan(pou).any():
                continue
            fit = ml.from_odds({"1": ps[0], "X": ps[1], "2": ps[2], "O2.5": pou[0], "U2.5": pou[1]})
            if not fit:
                continue
            hg, ag = int(D["hg"][i]), int(D["ag"][i])
            ht = HT.get((D["date"][i], teams[int(D["hi"][i])]))
            mk = _metrics(fit["lambda_home"], fit["lambda_away"], fit["rho"], hg, ag, ht)
            lgm = _metrics(wf["lh"][i], wf["la"][i], wf["rho"][i], hg, ag, ht)
            split = "val" if s in SEASONS_VAL else "dev"
            bucket = res.setdefault(split, {"n": 0, "n_ht": 0, "market": {}, "league": {}})
            bucket["n"] += 1
            bucket["n_ht"] += "ht" in mk
            for src, d in (("market", mk), ("league", lgm)):
                for k, v in d.items():
                    bucket[src][k] = bucket[src].get(k, 0.0) + float(v)
    for b in res.values():
        for src in ("market", "league"):
            b[src] = {k: round(v / (b["n_ht"] if k == "ht" else b["n"]), 4) for k, v in b[src].items()}
    return res


def _teams(fd: Path, lg: str) -> list[str]:
    s = set()
    for se in me.SEASONS:
        p = fd / f"{lg}_{se}.csv"
        if p.exists():
            with p.open(encoding="utf-8-sig", errors="replace") as fh:
                for r in csv.DictReader(fh):
                    if r.get("FTHG") and r.get("HomeTeam") and me._date(r.get("Date") or ""):
                        try:
                            int(r["FTHG"]); int(r["FTAG"])
                        except ValueError:
                            continue
                        s |= {r["HomeTeam"].strip(), r["AwayTeam"].strip()}
    return sorted(s)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fd", default="/home/claude/fd")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    r = run(Path(a.fd))
    print(json.dumps(r, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
