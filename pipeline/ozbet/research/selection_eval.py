"""Seçim ve kupon stratejisi değerlendirmesi (model AYNI: Dixon-Coles + piyasa harmanı, MODEL_WEIGHT).

    python -m ozbet.research.selection_eval --fd /home/claude/fd [--out ../docs/research/selection_eval.json]

Protokol (/home/claude/fd-PROTOKOL.md):
  - Geliştirme 2021–2324 (1920 yalnız eğitim), haftalık walk-forward; model yalnız o haftadan önceki maçlarla.
  - Doğrulama 2425: kural seçimi (en iyi 3).  KİLİTLİ TEST 2526+2627: yalnız seçilen 3 kural, bir kez.
  - ROI üç fiyatla: Max açılış, Avg açılış, iddaa benzetimi (Pinnacle açılış → Shin adil p → Shin tersiyle
    %20 (1X2/çifte şans) / %18 (2.5 A/Ü) marj).  Asıl ölçüt iddaa benzetimi.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import pickle
import random
from datetime import timedelta

import numpy as np

from .. import config
from ..agents.market import shin
from ..model.dixon_coles import clamp_rho, fit, score_matrix
from ..markets import probs_from_matrix
from ..sources.football_data import _num, _parse_date, _read_csv

LEAGUES = ["T1", "E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1"]
SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
DEV, VAL, TEST = {"2021", "2122", "2223", "2324"}, {"2425"}, {"2526", "2627"}
MARGIN_1X2, MARGIN_OU = 0.20, 0.18
W = config.MODEL_WEIGHT
MARKETS = ["1", "X", "2", "1X", "X2", "O2.5", "U2.5"]
GROUP = {"1": "1X2", "X": "1X2", "2": "1X2", "1X": "DC", "X2": "DC", "O2.5": "OU", "U2.5": "OU"}
PRICES = ("max", "avg", "iddaa")


# ---------------------------------------------------------------- fiyatlar
def shin_inverse(p: list[float], margin: float) -> list[float]:
    """Adil olasılıklardan Shin modeline göre marjlı oran: π_i = sqrt(S(z p_i + (1-z) p_i²)), Σπ = S."""
    S = 1.0 + margin
    lo, hi = 0.0, 0.5
    for _ in range(60):
        z = (lo + hi) / 2
        if sum(math.sqrt(z * x + (1 - z) * x * x) for x in p) < math.sqrt(S):
            lo = z
        else:
            hi = z
    z = (lo + hi) / 2
    return [1 / math.sqrt(S * (z * x + (1 - z) * x * x)) for x in p]


def dc_odds(a: float, b: float) -> float:
    """İki sonucun oranından sentetik çifte şans oranı (aynı marj)."""
    return 1 / (1 / a + 1 / b)


def iddaa_dc(pa: float, pb: float, margin: float = MARGIN_1X2) -> float:
    """iddaa çifte şans: adil olasılık toplamı, iki yollu Shin tersiyle %margin."""
    q = pa + pb
    return shin_inverse([q, 1 - q], margin)[0]


# ---------------------------------------------------------------- veri
def _trip(r, keys):
    v = [_num(r.get(k)) for k in keys]
    return v if all(x and x > 1 for x in v) else None


def _pair(r, a, b):
    x, y = _num(r.get(a)), _num(r.get(b))
    return [x, y] if x and y and x > 1 and y > 1 else None


def load(fd_dir: str) -> dict[str, list[dict]]:
    out = {}
    for lg in LEAGUES:
        rows = []
        for s in SEASONS:
            fn = os.path.join(fd_dir, f"{lg}_{s}.csv")
            if not os.path.exists(fn):
                continue
            with open(fn, encoding="utf-8", errors="replace") as fh:
                df = _read_csv(fh.read())
            for r in df.to_dict("records"):
                d = _parse_date(r.get("Date"))
                hg, ag = _num(r.get("FTHG")), _num(r.get("FTAG"))
                if d is None or hg is None or ag is None or not isinstance(r.get("HomeTeam"), str):
                    continue
                rows.append({"date": d, "season": s, "league": lg, "home": r["HomeTeam"].strip(),
                             "away": r["AwayTeam"].strip(), "hg": int(hg), "ag": int(ag),
                             "ps": _trip(r, ("PSH", "PSD", "PSA")), "psc": _trip(r, ("PSCH", "PSCD", "PSCA")) or _trip(r, ("AvgCH", "AvgCD", "AvgCA")),
                             "avg": _trip(r, ("AvgH", "AvgD", "AvgA")), "max": _trip(r, ("MaxH", "MaxD", "MaxA")),
                             "pou": _pair(r, "P>2.5", "P<2.5"),
                             "pouc": _pair(r, "PC>2.5", "PC<2.5") or _pair(r, "AvgC>2.5", "AvgC<2.5"),
                             "avgou": _pair(r, "Avg>2.5", "Avg<2.5"),
                             "maxou": _pair(r, "Max>2.5", "Max<2.5")})
        for x in rows:   # Pinnacle açılışı yoksa (2526 ortasından sonra) adil olasılık Avg açılıştan
            x["fair_src"] = "PS" if x["ps"] else "Avg"
            x["ps"] = x["ps"] or x["avg"]
            x["pou"] = x["pou"] or x["avgou"]
        out[lg] = sorted(rows, key=lambda x: x["date"])
    return out


def won(k: str, hg: int, ag: int) -> bool:
    return {"1": hg > ag, "X": hg == ag, "2": hg < ag, "1X": hg >= ag, "X2": hg <= ag,
            "O2.5": hg + ag > 2, "U2.5": hg + ag < 3}[k]


def candidates(r: dict, mp: dict) -> list[dict]:
    """Bir maçtaki 7 seçim: model p, piyasa adil q (Pinnacle açılış Shin), harman, üç fiyat, CLV."""
    out = []
    if r["ps"] and r["avg"] and r["max"]:
        q = shin(r["ps"]); qd = dict(zip(("1", "X", "2"), q))
        idd = dict(zip(("1", "X", "2"), shin_inverse(q, MARGIN_1X2)))
        avg = dict(zip(("1", "X", "2"), r["avg"])); mx = dict(zip(("1", "X", "2"), r["max"]))
        clo = dict(zip(("1", "X", "2"), r["psc"])) if r["psc"] else None
        op = dict(zip(("1", "X", "2"), r["ps"]))
        for k, (a, b) in (("1X", ("1", "X")), ("X2", ("X", "2"))):
            qd[k] = qd[a] + qd[b]; idd[k] = iddaa_dc(qd[a], qd[b])
            avg[k] = dc_odds(avg[a], avg[b]); mx[k] = dc_odds(mx[a], mx[b]); op[k] = dc_odds(op[a], op[b])
            if clo:
                clo[k] = dc_odds(clo[a], clo[b])
        fav_m = max(("1", "X", "2"), key=lambda k: mp[k]); fav_q = max(("1", "X", "2"), key=lambda k: qd[k])
        for k in ("1", "X", "2", "1X", "X2"):
            m = mp[k] if k in mp else (mp[k[0]] + mp[k[1]])
            agree = (k == fav_m == fav_q) if k in ("1", "X", "2") else (fav_m in k and fav_q in k)
            out.append(_cand(r, k, m, qd[k], {"max": mx[k], "avg": avg[k], "iddaa": idd[k]},
                             (op[k] / clo[k] - 1) if clo else None, agree))
    if r["pou"] and r["avgou"] and r["maxou"]:
        q = shin(r["pou"]); idd = shin_inverse(q, MARGIN_OU)
        clo = r["pouc"]
        for i, k in enumerate(("O2.5", "U2.5")):
            m = mp[k]
            agree = (m > 0.5) == (q[i] > 0.5)
            out.append(_cand(r, k, m, q[i], {"max": r["maxou"][i], "avg": r["avgou"][i], "iddaa": idd[i]},
                             (r["pou"][i] / clo[i] - 1) if clo else None, agree))
    return out


def _cand(r, k, m, q, price, clv, agree):
    pb = W * m + (1 - W) * q
    return {"date": r["date"], "season": r["season"], "league": r["league"], "match": f"{r['home']}-{r['away']}",
            "k": k, "g": GROUP[k], "m": m, "q": q, "p": pb, "raw": m - q, "edge": pb - q,
            "price": price, "clv": clv, "agree": agree, "won": won(k, r["hg"], r["ag"])}


def predict_league(rows: list[dict]) -> list[dict]:
    seasons_eval = DEV | VAL | TEST
    test = [r for r in rows if r["season"] in seasons_eval]
    if not test:
        return []
    out = []
    week = test[0]["date"]
    last = test[-1]["date"]
    while week <= last:
        nxt = week + timedelta(days=7)
        cur = [x for x in test if week <= x["date"] < nxt]
        if cur:
            past = [x for x in rows if week - timedelta(days=1100) <= x["date"] < week]
            model = fit(past, week, config.TIME_DECAY_XI)
            if model:
                for r in cur:
                    if r["home"] not in model.attack or r["away"] not in model.attack:
                        continue
                    if min(model.n_matches.get(r["home"], 0), model.n_matches.get(r["away"], 0)) < config.MIN_TEAM_MATCHES:
                        continue
                    lh, la = model.lambdas(r["home"], r["away"])
                    mp = probs_from_matrix(score_matrix(lh, la, clamp_rho(model.rho, lh, la)))
                    out.extend(candidates(r, mp))
        week = nxt
    return out


def all_candidates(fd_dir: str, cache: str | None) -> list[dict]:
    if cache and os.path.exists(cache):
        with open(cache, "rb") as fh:
            return pickle.load(fh)
    data = load(fd_dir)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 1) as ex:
        res = list(ex.map(predict_league, [data[lg] for lg in LEAGUES]))
    c = [x for r in res for x in r]
    if cache:
        with open(cache, "wb") as fh:
            pickle.dump(c, fh)
    return c


# ---------------------------------------------------------------- kurallar
def make_rules():
    rules = []
    for g in ("1X2", "DC", "OU", "ALL"):
        for lo, hi in ((1.0, 1.6), (1.6, 2.2), (2.2, 3.5), (3.5, 99.0), (1.0, 99.0)):
            for e in (0.0, 0.01, 0.02, 0.03):
                for ev in (False, True):
                    for ag in (False, True):
                        rules.append({"group": g, "odds": (lo, hi), "edge": e, "ev_avg": ev, "agree": ag,
                                      "leagues": "all"})
    return rules


def rule_name(r):
    return (f"{r['group']} oran[{r['odds'][0]:.1f},{r['odds'][1]:.1f}) edge≥{r['edge']:.2f}"
            f"{' EV(Avg)>0' if r['ev_avg'] else ''}{' uyum' if r['agree'] else ''}"
            f"{' lig:' + ','.join(r['leagues']) if r['leagues'] != 'all' else ''}")


def baseline_rule(c):
    """Sitedeki mevcut value.py mantığı (iddaa fiyatıyla): ham fark ≤ 0.20, harman edge ≥ 0.05, p ≥ 0.25, EV>0."""
    return c["raw"] <= 0.20 and c["edge"] >= config.VALUE_EDGE and c["p"] >= 0.25 and c["p"] * c["price"]["iddaa"] > 1


def select(cands: list[dict], rule) -> list[dict]:
    """Kurala uyan seçimler; maç başına en yüksek edge'li tek seçim."""
    best = {}
    for c in cands:
        if callable(rule):
            ok = rule(c)
        else:
            o = c["price"]["iddaa"]
            ok = ((rule["group"] == "ALL" or c["g"] == rule["group"]) and rule["odds"][0] <= o < rule["odds"][1]
                  and c["raw"] <= 0.20 and c["edge"] >= rule["edge"] and c["edge"] > 0
                  and (not rule["ev_avg"] or c["p"] * c["price"]["avg"] > 1)
                  and (not rule["agree"] or c["agree"])
                  and (rule["leagues"] == "all" or c["league"] in rule["leagues"]))
        if ok:
            key = (c["date"], c["match"])
            if key not in best or c["edge"] > best[key]["edge"]:
                best[key] = c
    return sorted(best.values(), key=lambda c: c["date"])


def profit(c, price="iddaa"):
    return c["price"][price] - 1 if c["won"] else -1.0


def stats(sel: list[dict], boot: int = 0, seed: int = 7) -> dict:
    n = len(sel)
    if not n:
        return {"n": 0}
    out = {"n": n, "hit": round(sum(c["won"] for c in sel) / n, 4)}
    for pr in PRICES:
        pf = np.array([profit(c, pr) for c in sel])
        out[f"roi_{pr}"] = round(float(pf.mean()), 4)
        out[f"odds_{pr}"] = round(float(np.mean([c["price"][pr] for c in sel])), 3)
        if boot and pr == "iddaa" or (boot and pr == "max"):
            rng = np.random.default_rng(seed)
            bs = rng.choice(pf, size=(boot, n), replace=True).mean(axis=1)
            out[f"ci_{pr}"] = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    cl = [c["clv"] for c in sel if c["clv"] is not None]
    out["clv"] = round(float(np.mean(cl)), 4) if cl else None
    out["exp_roi_iddaa"] = round(float(np.mean([c["p"] * c["price"]["iddaa"] - 1 for c in sel])), 4)
    return out


def breakdown(sel, key):
    keys = sorted({c[key] for c in sel})
    return {k: stats([c for c in sel if c[key] == k]) for k in keys}


# ---------------------------------------------------------------- kupon
def combos(sel: list[dict], size: int, seed: int = 1) -> dict:
    """Aynı gün oynanan farklı maçlardan rastgele size'lı kombineler (her seçim en çok bir kombinede)."""
    rng = random.Random(seed)
    by_day = {}
    for c in sel:
        by_day.setdefault(c["date"], []).append(c)
    res = {pr: [] for pr in PRICES}
    hits = 0
    n = 0
    for d, lst in by_day.items():
        lst = lst[:]
        rng.shuffle(lst)
        for i in range(0, len(lst) - size + 1, size):
            legs = lst[i:i + size]
            w = all(c["won"] for c in legs)
            hits += w; n += 1
            for pr in PRICES:
                o = math.prod(c["price"][pr] for c in legs)
                res[pr].append(o - 1 if w else -1.0)
    if not n:
        return {"n": 0}
    return {"n": n, "hit": round(hits / n, 4), **{f"roi_{pr}": round(float(np.mean(v)), 4) for pr, v in res.items()}}


def theoretical_combo(margin: float, legs: int) -> float:
    """Her bacak adil olsa (EV=1/(1+m) civarı) kombinenin beklenen ROI'si: (1/(1+m))^n − 1."""
    return round((1 / (1 + margin)) ** legs - 1, 4)


# ---------------------------------------------------------------- stake
def bankroll(sel, mode: str, start=100.0, frac=0.25, flat=1.0, price="iddaa", cap=0.05):
    b, peak, mdd = start, start, 0.0
    for c in sel:
        o = c["price"][price]
        if mode == "flat":
            s = min(flat, b)
        else:
            f = (c["p"] * o - 1) / (o - 1)
            s = max(0.0, min(frac * f, cap)) * b
        if s <= 0:
            continue
        b += s * (o - 1) if c["won"] else -s
        peak = max(peak, b); mdd = max(mdd, (peak - b) / peak if peak else 0)
        if b <= start * 0.01:
            b = 0.0; mdd = 1.0
            break
    return b, mdd


def stake_sim(sel, paths=1000, seed=3, price="iddaa"):
    rng = random.Random(seed)
    out = {}
    for mode in ("flat", "kelly"):
        fin, dd, ruin = [], [], 0
        for i in range(paths):
            s = sel[:] if i == 0 else [rng.choice(sel) for _ in sel]
            b, m = bankroll(s, mode, price=price)
            fin.append(b); dd.append(m); ruin += b < 50
        out[mode] = {"final_median": round(float(np.median(fin)), 1), "final_actual": round(fin[0], 1),
                     "maxdd_actual": round(dd[0], 3), "maxdd_median": round(float(np.median(dd)), 3),
                     "p_lose_half": round(ruin / paths, 3)}
    return out


# ---------------------------------------------------------------- ana akış
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fd", default="/home/claude/fd")
    ap.add_argument("--cache", default=None, help="tahmin önbelleği (pickle)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cands = all_candidates(a.fd, a.cache)
    dev = [c for c in cands if c["season"] in DEV]
    val = [c for c in cands if c["season"] in VAL]
    test = [c for c in cands if c["season"] in TEST]
    rep = {"n_candidates": {"dev": len(dev), "val": len(val), "test": len(test)}, "model_weight": W}

    rep["baseline_site_rule"] = {s: stats(select(x, baseline_rule)) for s, x in
                                 (("dev", dev), ("val", val))}

    # 1) kural ızgarası — dev'de lig filtresi türet (dev'de iddaa ROI'si en iyi 5 lig) → ikinci varyant
    rules = make_rules()
    grid = []
    for r in rules:
        sd = select(dev, r)
        good = [lg for lg, s in sorted(breakdown(sd, "league").items(), key=lambda t: -t[1].get("roi_iddaa", -9))
                if s["n"] >= 50][:5]
        for rr in (r, dict(r, leagues=good)):
            if rr["leagues"] != "all" and not good:
                continue
            sdd = sd if rr["leagues"] == "all" else [c for c in sd if c["league"] in good]
            grid.append({"rule": rr, "name": rule_name(rr), "dev": stats(sdd), "val": stats(select(val, rr))})
    rep["n_rules_tried"] = len(grid)
    elig = [g for g in grid if g["dev"]["n"] >= 300 and g["val"]["n"] >= 150]
    elig.sort(key=lambda g: -g["val"]["roi_iddaa"])
    top = elig[:3]
    rep["val_top10"] = [{"name": g["name"], "dev": g["dev"], "val": g["val"]} for g in elig[:10]]
    rep["n_eligible"] = len(elig)

    # KİLİTLİ TEST — yalnız seçilen 3 kural, bir kez
    rep["locked_test"] = []
    for g in top:
        st = select(test, g["rule"])
        rep["locked_test"].append({"name": g["name"], "rule": {**g["rule"], "odds": list(g["rule"]["odds"])},
                                   "val": g["val"], "test": stats(st, boot=2000),
                                   "by_season": breakdown(st, "season"), "by_league": breakdown(st, "league")})
        g["test_sel"] = st
    rep["baseline_site_rule"]["test"] = stats(select(test, baseline_rule), boot=2000)

    # 4) yüksek isabet modu: harman p eşiği, maç başına en olası seçim (değer şartı yok)
    hi = []
    for thr in (0.50, 0.60, 0.70, 0.75, 0.80, 0.85):
        for nm, part in (("val", val), ("test", test)):
            s = select(part, lambda c, t=thr: c["p"] >= t)
            # maç başına en yüksek p'li seçim
            best = {}
            for c in part:
                if c["p"] >= thr:
                    k = (c["date"], c["match"])
                    if k not in best or c["p"] > best[k]["p"]:
                        best[k] = c
            hi.append({"p_min": thr, "set": nm, **stats(sorted(best.values(), key=lambda c: c["date"]))})
    rep["high_hit"] = hi

    # 2) kombine etkisi — test seçimleri ve tüm "en olası" seçimler üzerinde
    rep["combo_theory"] = {f"{m:.2f}": {str(n): theoretical_combo(m, n) for n in (1, 2, 3, 4, 5)}
                           for m in (0.05, 0.18, 0.20)}
    base_pool = top[0]["test_sel"] if top else []
    hp = [c for c in test if c["p"] >= 0.70]
    rep["combo_empirical"] = {
        "top_rule_test": {str(n): combos(base_pool, n) for n in (1, 2, 3)},
        "p70_test": {str(n): combos(select(hp, lambda c: True), n) for n in (1, 2, 3)},
    }

    # 3) stake — kilitli testte en iyi kuralın seçimleri ile
    if base_pool:
        rep["stake"] = stake_sim(base_pool)                 # iddaa fiyatı: Kelly EV<0 → bahis yok
        rep["stake_max"] = stake_sim(base_pool, price="max")  # üst sınır fiyatla karşılaştırma
    out = a.out or os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "research", "selection_eval.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ("n_candidates", "n_rules_tried", "n_eligible", "baseline_site_rule")},
                     ensure_ascii=False, default=str))
    for t in rep["locked_test"]:
        print("TEST", t["name"], json.dumps(t["test"], default=str), "VAL", json.dumps(t["val"], default=str))
    return rep


if __name__ == "__main__":
    main()
