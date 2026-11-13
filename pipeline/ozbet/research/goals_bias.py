"""Gol yanlılığı araştırması: model gol marketlerinde gerçekten iyimser mi, yanlılık nereden geliyor?

    cd pipeline && python -m ozbet.research.goals_bias [--data ../data] [--out rapor.json]

Üç bağımsız parça (oran gerekmez, yalnız depo içi veri):
1. Arşiv walk-forward: data/archive/results-*.json üzerinde lig başına haftalık yürüyen tahmin. Her hafta, o haftadan
   ÖNCEKİ maçlarla üretim modeli (dixon_coles.fit, config.TIME_DECAY_XI) kurulur ve hafta tahmin edilir.
   Ölçülenler: Ü1.5/Ü2.5/Ü3.5, KG Var, ev Ü1.5, dep Ü1.5, 0-0, beraberlik (tahmin vs gözlenen, n, standart hata),
   ortalama λ toplamı vs gerçek gol, 1X2 log-loss. Arşivi ince ligler atlanır (MIN_TRAIN / MIN_TEST).
2. Canlı örnek: data/YYYY-MM-DD.json içindeki BİTMİŞ ve modeli olan TÜM maçlar (yalnız tercihler değil).
   model.method / data_quality / not (şut harmanı, xG harmanı, kadro) kırılımı.
3. Canlı tekrar oynatma (replay): kayıtlı λ'lar üzerinde toplam gol büzmesinin (dixon_coles.shrink_total) etkisi,
   maç bazında eşli bootstrap güven aralığıyla; ve tercihlerin (seçilmiş örnek) ayrıştırması:
   seviye yanlılığı (tüm maçlar) ↔ seçim etkisi / "kazananın laneti" (yalnız tercihler).

Sonuçlar: docs/research/gol-yanliligi.md
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from .. import config
from ..model import dixon_coles as dc

MIN_TRAIN = 60      # ilk tahminden önce gereken maç (config.ARCHIVE_MIN_MATCHES ile aynı mantık)
MIN_TEST = 30       # lig raporu için en az tahmin edilen maç
MIN_LEAGUE_LIVE = 5  # canlı replay'de lig taban seviyesi için en az maç; azsa havuz ortalaması
EVENTS = ("O1.5", "O2.5", "O3.5", "BTTS_Y", "H_O1.5", "A_O1.5", "0-0", "X")
GOAL_EVENTS = ("O1.5", "O2.5", "O3.5", "BTTS_Y")
TEAM_EVENTS = ("H_O1.5", "A_O1.5")
SHRINK_NOTE = "Toplam gol beklentisi lig ortalamasına büzüldü"   # agents.simulation.TOTAL_SHRINK_NOTE ile aynı


# ---------------------------------------------------------------- ortak
def event_probs(lh: float, la: float, rho: float) -> dict[str, float]:
    """Dixon-Coles skor matrisinden (Monte Carlo gürültüsü olmadan) olay olasılıkları."""
    m = dc.score_matrix(lh, la, dc.clamp_rho(rho, lh, la))
    i, j = np.indices(m.shape)
    t = i + j
    return {"O1.5": float(m[t > 1].sum()), "O2.5": float(m[t > 2].sum()), "O3.5": float(m[t > 3].sum()),
            "BTTS_Y": float(m[(i > 0) & (j > 0)].sum()), "H_O1.5": float(m[i > 1].sum()),
            "A_O1.5": float(m[j > 1].sum()), "0-0": float(m[0, 0]), "X": float(np.trace(m)),
            "1": float(m[i > j].sum()), "2": float(m[i < j].sum())}


def event_obs(hg: int, ag: int) -> dict[str, bool]:
    t = hg + ag
    return {"O1.5": t > 1, "O2.5": t > 2, "O3.5": t > 3, "BTTS_Y": hg > 0 and ag > 0, "H_O1.5": hg > 1,
            "A_O1.5": ag > 1, "0-0": t == 0, "X": hg == ag, "1": hg > ag, "2": hg < ag}


def _ll(p: float, y: bool) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return -math.log(p if y else 1 - p)


def make_record(lh: float, la: float, probs: dict[str, float], hg: int, ag: int, **extra) -> dict:
    """Tek maç kaydı: tahmin (p), gözlem (y) ve log-loss'lar."""
    obs = event_obs(hg, ag)
    res = "1" if hg > ag else ("X" if hg == ag else "2")
    rec = {"lh": lh, "la": la, "hg": hg, "ag": ag,
           "p": {k: probs[k] for k in EVENTS if probs.get(k) is not None},
           "y": {k: bool(obs[k]) for k in EVENTS}}
    rec["ll_1x2"] = -math.log(max(probs[res], 1e-6)) if all(probs.get(k) is not None for k in "1X2") else None
    rec.update(extra)
    return rec


def summarize(records: list[dict]) -> dict:
    """Tahmin vs gözlenen oranlar (n, standart hata, z), ortalama λ vs gol, log-loss'lar."""
    n = len(records)
    if not n:
        return {"n": 0}
    lam = np.array([r["lh"] + r["la"] for r in records])
    goals = np.array([r["hg"] + r["ag"] for r in records], float)
    se_g = float(goals.std(ddof=1) / math.sqrt(n)) if n > 1 else None
    out = {"n": n,
           "lambda_sum": round(float(lam.mean()), 3), "goals": round(float(goals.mean()), 3),
           "goals_se": round(se_g, 3) if se_g is not None else None,
           "lambda_home": round(float(np.mean([r["lh"] for r in records])), 3),
           "goals_home": round(float(np.mean([r["hg"] for r in records])), 3),
           "lambda_away": round(float(np.mean([r["la"] for r in records])), 3),
           "goals_away": round(float(np.mean([r["ag"] for r in records])), 3),
           "events": {}}
    for k in EVENTS:
        rs = [r for r in records if k in r["p"]]
        if not rs:
            continue
        p = np.array([r["p"][k] for r in rs]); y = np.array([r["y"][k] for r in rs], float)
        se = math.sqrt(max(float(np.mean(p * (1 - p))), 1e-12) / len(rs))   # model doğruysa gözlenen oranın SE'si
        out["events"][k] = {"n": len(rs), "pred": round(float(p.mean()), 4), "obs": round(float(y.mean()), 4),
                            "se": round(se, 4), "z": round(float((p.mean() - y.mean()) / se), 2),
                            "logloss": round(float(np.mean([_ll(a, b) for a, b in zip(p, y)])), 4)}
    for name, keys in (("ll_goal", GOAL_EVENTS), ("ll_team", TEAM_EVENTS)):
        v = [out["events"][k]["logloss"] for k in keys if k in out["events"]]
        out[name] = round(float(np.mean(v)), 4) if v else None
    l1 = [r["ll_1x2"] for r in records if r.get("ll_1x2") is not None]
    out["ll_1x2"] = round(float(np.mean(l1)), 4) if l1 else None
    return out


# ---------------------------------------------------------------- 1) arşiv walk-forward
def load_archive(archive_dir: Path) -> dict[str, list[dict]]:
    """results-{LIG}.json → {lig: [{date, home, away, hg, ag, hthg, htag}]} (tarihe göre sıralı)."""
    out: dict[str, list[dict]] = {}
    for f in sorted(Path(archive_dir).glob("results-*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = []
        for r in doc.get("rows", []):
            ft = r.get("ft")
            if not ft or len(ft) != 2 or not r.get("date"):
                continue
            ht = r.get("ht") or [None, None]
            rows.append({"date": date.fromisoformat(r["date"]), "home": r["home"], "away": r["away"],
                         "hg": int(ft[0]), "ag": int(ft[1]), "hthg": ht[0], "htag": ht[1]})
        rows.sort(key=lambda r: r["date"])
        out[doc.get("league") or f.stem.replace("results-", "")] = rows
    return out


def walk_forward(rows: list[dict], shrink: float = 1.0, min_train: int = MIN_TRAIN,
                 xi: float | None = None) -> list[dict]:
    """Haftalık yürüyen tahmin. Her haftanın maçları, pazartesiden ÖNCEKİ maçlarla kurulan modelle tahmin edilir.

    shrink: dixon_coles.shrink_total k değeri (1.0 = büzme yok = eski üretim modeli).
    İki takımı da modelde olmayan maçlar atlanır (yeni çıkan takım).
    """
    xi = config.TIME_DECAY_XI if xi is None else xi
    rows = sorted(rows, key=lambda r: r["date"])
    weeks: dict[date, list[dict]] = defaultdict(list)
    for r in rows:
        weeks[r["date"] - timedelta(days=r["date"].weekday())].append(r)
    recs = []
    for monday in sorted(weeks):
        past = [r for r in rows if r["date"] < monday]
        if len(past) < min_train:
            continue
        R = dc.fit(past, monday, xi)
        if R is None:
            continue
        for r in weeks[monday]:
            if r["home"] not in R.attack or r["away"] not in R.attack:
                continue
            lh, la = R.lambdas(r["home"], r["away"])
            lh, la = dc.shrink_total(lh, la, R.base_level(), shrink)
            recs.append(make_record(lh, la, event_probs(lh, la, R.rho), r["hg"], r["ag"], date=r["date"].isoformat()))
    return recs


def archive_report(archive_dir: Path, shrinks: tuple[float, ...] = (1.0, dc.TOTAL_SHRINK),
                   min_train: int = MIN_TRAIN, min_test: int = MIN_TEST) -> dict:
    """Lig başına ve havuzlanmış walk-forward özeti; her shrink değeri için ayrı (önce/sonra kıyası)."""
    leagues = load_archive(archive_dir)
    out = {"min_train": min_train, "min_test": min_test, "leagues": {}, "skipped": {}, "pooled": {}}
    pooled: dict[float, list[dict]] = defaultdict(list)
    for lg, rows in leagues.items():
        base = walk_forward(rows, 1.0, min_train) if len(rows) >= min_train + min_test else []
        if len(base) < min_test:
            out["skipped"][lg] = {"rows": len(rows), "predicted": len(base),
                                  "reason": f"arşiv ince: {len(rows)} maç (eğitim ≥{min_train} + test ≥{min_test} gerekir)"}
            continue
        out["leagues"][lg] = {}
        for k in shrinks:
            recs = base if k == 1.0 else walk_forward(rows, k, min_train)
            out["leagues"][lg][f"k={k:g}"] = summarize(recs)
            pooled[k] += recs
    out["pooled"] = {f"k={k:g}": summarize(pooled[k]) for k in shrinks if pooled.get(k)}
    out["total_rows"] = sum(len(v) for v in leagues.values())
    return out


# ---------------------------------------------------------------- 2) canlı örnek
def load_live(data_dir: Path) -> list[dict]:
    """Gün dosyalarındaki bitmiş + modeli olan tüm maçlar (aynı maç birden çok dosyadaysa son görülen)."""
    seen: dict[str, dict] = {}
    for f in sorted(Path(data_dir).glob("20??-??-??.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for m in doc.get("matches", []):
            res, mod = m.get("result") or {}, m.get("model") or {}
            if not res.get("ft") or mod.get("lambda_home") is None or mod.get("source") == "piyasa":
                continue
            seen[m["id"]] = dict(m, _date=doc.get("date"))
    return list(seen.values())


def live_record(m: dict) -> dict:
    """Kayıtlı model çıktısından kayıt (olasılıklar üretimde yazılan Monte Carlo değerleridir)."""
    mod = m["model"]
    probs = dict(mod.get("probs") or {})
    ex = mod.get("extra") or {}
    for k in TEAM_EVENTS:
        probs[k] = ex.get(k)
    sm = mod.get("score_matrix")
    probs["0-0"] = sm[0][0] if sm else None
    notes = mod.get("notes") or []
    hg, ag = m["result"]["ft"]
    return make_record(mod["lambda_home"], mod["lambda_away"], probs, int(hg), int(ag),
                       league=m.get("league"), date=m.get("_date"), rho=mod.get("rho", 0.0),
                       method=mod.get("method"), quality=mod.get("data_quality"),
                       shot=any("Şut" in x for x in notes), xg=any("xG" in x for x in notes),
                       squad=any("Kadro" in x or "rotasyon" in x for x in notes),
                       shrunk=any(SHRINK_NOTE in x for x in notes))


def live_report(matches: list[dict]) -> dict:
    recs = [live_record(m) for m in matches]
    out = {"all": summarize(recs), "splits": {}}
    splits = {
        "method": lambda r: r["method"], "data_quality": lambda r: r["quality"],
        "sut_harmani": lambda r: "var" if r["shot"] else "yok", "xg_harmani": lambda r: "var" if r["xg"] else "yok",
        "kadro_duzeltmesi": lambda r: "var" if r["squad"] else "yok",
    }
    for name, fn in splits.items():
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in recs:
            groups[str(fn(r))].append(r)
        out["splits"][name] = {g: summarize(v) for g, v in sorted(groups.items())}
    return out


# ---------------------------------------------------------------- 3) canlı replay: toplam gol büzmesi
def replay_shrink(matches: list[dict], ks: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25, 0.0),
                  n_boot: int = 4000, seed: int = 7) -> dict:
    """Kayıtlı λ'lar üzerinde shrink_total etkisi (yalnız method == "league" ve henüz büzülmemiş maçlar).

    Lig taban seviyesi üretimde e^(μ+h/2)'dir; gün dosyasında μ olmadığından burada ligin örnekteki maçlarının
    √(λ_ev·λ_dep) geometrik ortalaması kullanılır (≥ MIN_LEAGUE_LIVE maç; azsa havuz). Taban yalnız TAHMİNLERDEN
    hesaplanır, sonuçlar kullanılmaz → sızıntı yok. Fark için eşli bootstrap (maç bazında) %95 GA.
    """
    recs = [r for r in (live_record(m) for m in matches) if r["method"] == "league" and not r["shrunk"]]
    if not recs:
        return {"n": 0}
    logs: dict[str, list[float]] = defaultdict(list)
    for r in recs:
        logs[r["league"]].append(0.5 * math.log(r["lh"] * r["la"]))
    pool = math.exp(float(np.mean([x for v in logs.values() for x in v])))
    base = {lg: (math.exp(float(np.mean(v))) if len(v) >= MIN_LEAGUE_LIVE else pool) for lg, v in logs.items()}
    per: dict[float, list[dict]] = {}
    for k in ks:
        per[k] = []
        for r in recs:
            lh, la = dc.shrink_total(r["lh"], r["la"], base[r["league"]], k)
            per[k].append(make_record(lh, la, event_probs(lh, la, r["rho"]), r["hg"], r["ag"], date=r["date"]))
    out = {"n": len(recs), "k": {f"{k:g}": summarize(per[k]) for k in ks}, "diff_vs_k1": {}, "by_date": {}}
    if 1.0 not in per:
        return out
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(recs), (n_boot, len(recs)))

    def per_match(rs, keys):
        if keys == "1x2":
            return np.array([r["ll_1x2"] for r in rs])
        return np.array([np.mean([_ll(r["p"][e], r["y"][e]) for e in keys]) for r in rs])

    for k in ks:
        if k == 1.0:
            continue
        out["diff_vs_k1"][f"{k:g}"] = {}
        for name, keys in (("gol", GOAL_EVENTS), ("takim", TEAM_EVENTS), ("1x2", "1x2")):
            d = per_match(per[k], keys) - per_match(per[1.0], keys)
            bs = d[idx].mean(axis=1)
            lo, hi = np.percentile(bs, [2.5, 97.5])
            out["diff_vs_k1"][f"{k:g}"][name] = {"d": round(float(d.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
                                                 "p_better": round(float((bs < 0).mean()), 3)}
    for dt in sorted({r["date"] for r in recs}):
        ii = [i for i, r in enumerate(recs) if r["date"] == dt]
        out["by_date"][dt] = {"n": len(ii), **{f"{k:g}": round(float(per_match([per[k][i] for i in ii], GOAL_EVENTS).mean()), 4)
                                               for k in ks}}
    return out


# ---------------------------------------------------------------- 4) eğim ve tercih ayrıştırması (karne geçmişi)
def _slope(p: np.ndarray, y: np.ndarray) -> float | None:
    """Kalibrasyon eğimi: logit(y) = a + b·logit(p). b≈1 iyi; b<1 → tahminler gereğinden fazla açık (gürültü)."""
    from scipy.optimize import minimize
    if len(p) < 30 or y.min() == y.max():
        return None
    x = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    f = lambda t: float(np.sum(np.logaddexp(0, t[0] + t[1] * x) - y * (t[0] + t[1] * x)))  # noqa: E731
    return round(float(minimize(f, [0.0, 1.0]).x[1]), 2)


def load_history(data_dir: Path) -> list[dict]:
    rows = []
    for f in sorted((Path(data_dir) / "history").glob("*.json")):
        try:
            rows += json.loads(f.read_text(encoding="utf-8")).get("rows", [])
        except (OSError, ValueError):
            continue
    return rows


def history_report(rows: list[dict], markets: tuple[str, ...] = ("O1.5", "O2.5", "O3.5", "BTTS_Y", "H_O1.5", "A_O1.5",
                                                                 "1", "X", "2")) -> dict:
    """Karne geçmişinden (model p, piyasa q, sonuç): tüm maçlarda seviye + eğim; tercihlerde seçim etkisi.

    Tercih olasılığı p_tercih = MODEL_WEIGHT·model + (1−MODEL_WEIGHT)·piyasa harmanıdır. Ayrıştırma:
      seviye yanlılığı = tüm maçlarda (model p − gözlenen)      → modelin gerçek yanlılığı
      seçim etkisi     = tercihlerde (p_tercih − gözlenen) − seviye yanlılığı  → kazananın laneti + piyasa payı
    """
    out = {"markets": {}, "picks": {}}
    by: dict[str, list[tuple]] = defaultdict(list)
    for r in rows:
        for e in r.get("markets") or []:
            if e.get("q") is not None:
                by[e["m"]].append((e["p"], e["q"], float(bool(e["won"]))))
    for k in markets:
        if len(by.get(k, [])) < 30:
            continue
        p, q, y = np.array(by[k]).T
        out["markets"][k] = {
            "n": len(p), "model": round(float(p.mean()), 4), "market": round(float(q.mean()), 4),
            "obs": round(float(y.mean()), 4), "se": round(math.sqrt(float(y.mean() * (1 - y.mean())) / len(y)), 4),
            "model_logloss": round(float(np.mean([_ll(a, b) for a, b in zip(p, y)])), 4),
            "market_logloss": round(float(np.mean([_ll(a, b) for a, b in zip(q, y)])), 4),
            "model_sd": round(float(p.std()), 4), "market_sd": round(float(q.std()), 4),
            "model_slope": _slope(p, y), "market_slope": _slope(q, y)}
    picks: dict[str, list[tuple]] = defaultdict(list)
    for r in rows:
        if r.get("pick") is None or r.get("won") is None:
            continue
        e = next((e for e in r.get("markets") or [] if e["m"] == r["pick"]), {})
        picks[r["pick"]].append((r["p"], e.get("p", np.nan), e.get("q", np.nan), float(bool(r["won"]))))
    for k, v in sorted(picks.items(), key=lambda kv: -len(kv[1])):
        a = np.array(v, float)
        pp, mp, mq, y = (float(np.nanmean(a[:, i])) for i in range(4))
        d = {"n": len(a), "pick_p": round(pp, 4), "model_p": round(mp, 4), "market_p": round(mq, 4), "obs": round(y, 4),
             "gap": round(pp - y, 4), "se": round(math.sqrt(max(y * (1 - y), 1e-9) / len(a)), 4)}
        if k in out["markets"]:
            lvl = out["markets"][k]["model"] - out["markets"][k]["obs"]
            d["level_bias_all"] = round(lvl, 4)
            d["selection_effect"] = round(d["gap"] - lvl, 4)
        out["picks"][k] = d
    return out


# ---------------------------------------------------------------- CLI
def _fmt_summary(title: str, s: dict) -> str:
    if not s.get("n"):
        return f"{title}: veri yok"
    ev = "  ".join(f"{k} {v['pred']:.3f}/{v['obs']:.3f}(z{v['z']:+.1f})" for k, v in s["events"].items())
    return (f"{title}: n={s['n']}  λ={s['lambda_sum']:.2f} gol={s['goals']:.2f}±{s['goals_se'] or 0:.2f}  {ev}  "
            f"LL gol={s['ll_goal']} takım={s['ll_team']} 1X2={s['ll_1x2']}")


def run(data_dir: Path) -> dict:
    live = load_live(data_dir)
    return {"archive": archive_report(Path(data_dir) / "archive"), "live": live_report(live),
            "replay": replay_shrink(live), "history": history_report(load_history(data_dir)),
            "total_shrink": dc.TOTAL_SHRINK}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Gol yanlılığı araştırması")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    rep = run(Path(a.data))
    ar = rep["archive"]
    print(f"== Arşiv walk-forward (toplam {ar['total_rows']} maç; eğitim ≥{ar['min_train']}, test ≥{ar['min_test']})")
    for lg, by_k in ar["leagues"].items():
        for k, s in by_k.items():
            print(_fmt_summary(f"  {lg} {k}", s))
    for k, s in ar["pooled"].items():
        print(_fmt_summary(f"  HAVUZ {k}", s))
    if ar["skipped"]:
        print("  atlanan ligler: " + ", ".join(f"{lg}({v['rows']})" for lg, v in ar["skipped"].items()))
    print("== Canlı örnek (bitmiş tüm maçlar; tahmin/gözlenen)")
    print(_fmt_summary("  tümü", rep["live"]["all"]))
    for name, groups in rep["live"]["splits"].items():
        for g, s in groups.items():
            print(_fmt_summary(f"  {name}={g}", s))
    rp = rep["replay"]
    print(f"== Canlı replay: toplam gol büzmesi (n={rp.get('n', 0)}, yalnız lig modeli, henüz büzülmemiş maçlar)")
    for k, s in (rp.get("k") or {}).items():
        print(f"  k={k}: LL gol={s['ll_goal']} takım={s['ll_team']} 1X2={s['ll_1x2']}  λ={s['lambda_sum']}")
    for k, d in (rp.get("diff_vs_k1") or {}).items():
        print(f"  k={k} − k=1: " + "  ".join(f"{n} {v['d']:+.4f} GA{v['ci95']}" for n, v in d.items()))
    print("== Karne geçmişi: model vs piyasa (tüm maçlar) ve tercihler")
    for k, v in rep["history"]["markets"].items():
        print(f"  {k}: n={v['n']} model={v['model']:.3f} piyasa={v['market']:.3f} gözlenen={v['obs']:.3f}±{v['se']:.3f} "
              f"eğim model={v['model_slope']} piyasa={v['market_slope']} LL {v['model_logloss']}/{v['market_logloss']}")
    for k, v in rep["history"]["picks"].items():
        print(f"  tercih {k}: n={v['n']} p={v['pick_p']:.3f} (model {v['model_p']:.3f}, piyasa {v['market_p']:.3f}) "
              f"gözlenen={v['obs']:.3f}±{v['se']:.3f} seviye={v.get('level_bias_all')} seçim={v.get('selection_effect')}")
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


if __name__ == "__main__":
    main()
