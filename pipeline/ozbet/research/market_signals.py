"""Piyasa sinyalleri araştırması (model yok; yalnız oranlar).

    python -m ozbet.research.market_signals --fd /home/claude/fd [--locked]

Bölme (fd-PROTOKOL): geliştirme 1920–2324, doğrulama 2425 (kural seçimi), kilitli test 2526+2627.
Kural seçimi YALNIZ 2425'te, iddaa benzetimi ROI'sine göre (n>=150) yapılır; --locked bu tek kuralı
testte bir kez koşar. Fiyatlar: Max, Avg, iddaa benzetimi (Pinnacle açılış/kapanış → Shin adil →
Shin tersiyle %20 (1X2) / %18 (2-yol) marj).
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..agents.market import shin

LEAGUES = ["T1", "E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1"]
DEV = ["1920", "2021", "2122", "2223", "2324"]
VAL = ["2425"]
TEST = ["2526", "2627"]
MARGIN = {"1x2": 0.20, "ou": 0.18, "ah": 0.18}
SEL = {"1x2": ["H", "D", "A"], "ou": ["O", "U"], "ah": ["H", "A"]}
COLS = {  # (market, sel) -> {prefix: column}; açılış / kapanış
    ("1x2", "H"): dict(PS="PSH", Max="MaxH", Avg="AvgH", PSC="PSCH", MaxC="MaxCH", AvgC="AvgCH"),
    ("1x2", "D"): dict(PS="PSD", Max="MaxD", Avg="AvgD", PSC="PSCD", MaxC="MaxCD", AvgC="AvgCD"),
    ("1x2", "A"): dict(PS="PSA", Max="MaxA", Avg="AvgA", PSC="PSCA", MaxC="MaxCA", AvgC="AvgCA"),
    ("ou", "O"): dict(PS="P>2.5", Max="Max>2.5", Avg="Avg>2.5", PSC="PC>2.5", MaxC="MaxC>2.5", AvgC="AvgC>2.5"),
    ("ou", "U"): dict(PS="P<2.5", Max="Max<2.5", Avg="Avg<2.5", PSC="PC<2.5", MaxC="MaxC<2.5", AvgC="AvgC<2.5"),
    ("ah", "H"): dict(PS="PAHH", Max="MaxAHH", Avg="AvgAHH", PSC="PCAHH", MaxC="MaxCAHH", AvgC="AvgCAHH"),
    ("ah", "A"): dict(PS="PAHA", Max="MaxAHA", Avg="AvgAHA", PSC="PCAHA", MaxC="MaxCAHA", AvgC="AvgCAHA"),
}


def shin_inverse(p: list[float], margin: float) -> list[float]:
    """Adil olasılıklardan Shin modeliyle marjlı oran: π_i ∝ sqrt(z p_i + (1-z) p_i²), Σπ = 1+margin."""
    def pis(z):
        r = [math.sqrt(z * x + (1 - z) * x * x) for x in p]
        s = sum(r)
        return [x * s for x in r]
    lo, hi = 0.0, 0.99
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(pis(mid)) < 1 + margin:
            lo = mid
        else:
            hi = mid
    return [1 / x for x in pis((lo + hi) / 2)]


def ah_return(line: float, gh: int, ga: int, side: str) -> float:
    """AH bahsi (AHh ev sahibi çizgisi): çeyrek çizgi iki yarım bahse bölünür. Dönüş (kazanç payı, iade payı)."""
    lines = [line - 0.25, line + 0.25] if abs(line * 4) % 2 == 1 else [line]
    win = push = 0.0
    for ln in lines:
        d = (gh - ga) + ln if side == "H" else (ga - gh) - ln
        if d > 0:
            win += 1 / len(lines)
        elif d == 0:
            push += 1 / len(lines)
    return win, push


def load(fd: Path) -> pd.DataFrame:
    frames = []
    for lg in LEAGUES:
        for s in DEV + VAL + TEST:
            f = fd / f"{lg}_{s}.csv"
            if f.exists():
                d = pd.read_csv(f, encoding="utf-8-sig", on_bad_lines="skip")
                d = d.assign(lg=lg, season=s)
                frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["FTHG", "FTAG"])
    df["dt"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.sort_values(["lg", "season", "dt"])
    first = df.groupby(["lg", "season"])["dt"].transform("min")
    df["week"] = ((df["dt"] - first).dt.days // 7) + 1
    return df


def long_table(df: pd.DataFrame) -> pd.DataFrame:
    """Her (maç, market, seçim) bir satır: açılış/kapanış fiyatları, iddaa benzetimi, kazanç payı."""
    out = []
    for mk, sels in SEL.items():
        cols = [COLS[(mk, s)] for s in sels]
        need = [c["PS"] for c in cols] + [c["PSC"] for c in cols]
        if mk == "ah":
            need += ["AHh", "AHCh"]
        sub = df.dropna(subset=need)
        for _, r in sub.iterrows():
            po = [r[c["PS"]] for c in cols]
            pc = [r[c["PSC"]] for c in cols]
            if min(po + pc) <= 1.0:
                continue
            fo, fc = shin(po), shin(pc)
            io, ic = shin_inverse(fo, MARGIN[mk]), shin_inverse(fc, MARGIN[mk])
            gh, ga = int(r["FTHG"]), int(r["FTAG"])
            for i, s in enumerate(sels):
                if mk == "1x2":
                    win, push = float(r["FTR"] == s), 0.0
                elif mk == "ou":
                    win, push = float((gh + ga > 2.5) == (s == "O")), 0.0
                else:
                    if r["AHh"] != r["AHCh"]:  # çizgi kaydıysa açılış-kapanış oranları karşılaştırılamaz
                        continue
                    win, push = ah_return(float(r["AHh"]), gh, ga, s)
                c = cols[i]
                out.append(dict(lg=r["lg"], season=r["season"], week=r["week"], mk=mk, sel=s,
                                ps=po[i], psc=pc[i], fair=fo[i], fairc=fc[i],
                                max=r.get(c["Max"], np.nan), avg=r.get(c["Avg"], np.nan),
                                maxc=r.get(c["MaxC"], np.nan), avgc=r.get(c["AvgC"], np.nan),
                                idd=io[i], iddc=ic[i], win=win, push=push))
    return pd.DataFrame(out)


def pnl(odds: np.ndarray, win: np.ndarray, push: np.ndarray) -> np.ndarray:
    return win * (odds - 1) - (1 - win - push)


def summarize(b: pd.DataFrame, price: str, close: str, rng=np.random.default_rng(7)) -> dict:
    b = b.dropna(subset=[price])
    if len(b) == 0:
        return dict(n=0)
    p = pnl(b[price].values, b["win"].values, b["push"].values)
    boots = [p[rng.integers(0, len(p), len(p))].mean() for _ in range(2000)]
    by_season = b.assign(p=p).groupby("season")["p"].mean()
    clv = (b[price] / b[close] - 1).mean() if close in b else np.nan
    return dict(n=len(b), hit=b["win"].mean(), odds=b[price].mean(), roi=p.mean(),
                lo=np.percentile(boots, 2.5), hi=np.percentile(boots, 97.5), clv=clv,
                worst=f"{by_season.idxmin()} {by_season.min():+.3f}" if len(by_season) else "")


# ---- Kurallar: her biri (uzun tablo) -> bahis maskesi + kullanılacak fiyat sütunları --------------
def rules():
    R = {}
    # 1) Keskin vs yumuşak: Pinnacle açılış adil × fiyat > 1+e (fiyat açılışta alınır)
    for e in (0.0, 0.02, 0.04):
        for pr in ("max", "avg", "idd"):
            R[f"S1 fair*{pr}>1+{e}"] = (lambda t, e=e, pr=pr: t["fair"] * t[pr] > 1 + e, pr)
    # 2) Hareket: PS açılış→kapanış düşüş >= d; kapanışta (hareketten sonra) oyna
    for d in (0.03, 0.05, 0.08, 0.12):
        R[f"S2 drop>={d} @close"] = (lambda t, d=d: t["psc"] / t["ps"] - 1 <= -d, "close")
        # Varsayımsal: yumuşak fiyat (iddaa) Pinnacle'ın hareketini GECİKMELİ izlerse açılış fiyatı hâlâ alınabilir.
        # Gerçekleştirilebilir değil (canlı gecikme verisi yok) → seçimden hariç ("H:" öneki).
        R[f"H:S2 drop>={d} @open(lag)"] = (lambda t, d=d: t["psc"] / t["ps"] - 1 <= -d, "open")
        R[f"S2 rise>={d} @close"] = (lambda t, d=d: t["psc"] / t["ps"] - 1 >= d, "close")
    # 3) Favori–sürpriz: oran aralığı × market
    for mk in SEL:
        for lo, hi in ((1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 100.0)):
            R[f"S3 {mk} ps[{lo},{hi})"] = (lambda t, mk=mk, lo=lo, hi=hi:
                                          (t["mk"] == mk) & (t["ps"] >= lo) & (t["ps"] < hi), "open")
    # 4) Sezon başı (ilk 5 hafta) favori/sürpriz
    R["S4 week<=5 fav(ps<2) 1x2"] = (lambda t: (t["week"] <= 5) & (t["mk"] == "1x2") & (t["ps"] < 2), "open")
    R["S4 week<=5 dog(ps>=3) 1x2"] = (lambda t: (t["week"] <= 5) & (t["mk"] == "1x2") & (t["ps"] >= 3), "open")
    return R


PRICES = {"open": [("max", "maxc"), ("avg", "avgc"), ("idd", "iddc")],
          "close": [("maxc", "maxc"), ("avgc", "avgc"), ("iddc", "iddc")]}


def evaluate(t: pd.DataFrame, name: str, rule) -> list[dict]:
    fn, pr = rule
    b = t[fn(t)]
    if pr in ("max", "avg", "idd"):
        pairs = [(pr, pr + "c")]
    else:
        pairs = PRICES[pr]
    return [dict(rule=name, price=p, **summarize(b, p, c)) for p, c in pairs]


def fmt(rows: list[dict]) -> str:
    h = "| kural | fiyat | n | isabet | ort.oran | ROI | %95 GA | CLV | en kötü sezon |\n|---|---|---|---|---|---|---|---|---|\n"
    for r in rows:
        if not r.get("n"):
            h += f"| {r['rule']} | {r['price']} | 0 | | | | | | |\n"
            continue
        h += (f"| {r['rule']} | {r['price']} | {r['n']} | {r['hit']:.3f} | {r['odds']:.2f} | {r['roi']:+.3f} | "
              f"[{r['lo']:+.3f}, {r['hi']:+.3f}] | {r['clv']:+.3f} | {r['worst']} |\n")
    return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fd", type=Path, required=True)
    ap.add_argument("--locked", action="store_true", help="seçilen tek kuralı kilitli testte koş")
    a = ap.parse_args(argv)
    t = long_table(load(a.fd))
    R = rules()
    parts = {"dev": t[t.season.isin(DEV)], "val": t[t.season.isin(VAL)], "test": t[t.season.isin(TEST)]}
    print(f"# Toplam seçim satırı: {len(t)}; kural sayısı: {len(R)} (× fiyat → {sum(len(evaluate(parts['val'].head(0), k, v)) for k, v in R.items())} yapılandırma)\n")
    res = {}
    for part in ("dev", "val"):
        rows = [r for k, v in R.items() for r in evaluate(parts[part], k, v)]
        res[part] = rows
        print(f"## {part}\n\n" + fmt(rows))
    # Seçim: doğrulamada iddaa-benzetimi ROI'si en yüksek, n>=150, geliştirmede de ROI>0 olan kural
    dev_roi = {(r["rule"], r["price"]): r.get("roi", -1) for r in res["dev"]}
    cand = [r for r in res["val"] if r["price"] in ("idd", "iddc") and r.get("n", 0) >= 150
            and not r["rule"].startswith("H:")]
    cand.sort(key=lambda r: r["roi"], reverse=True)
    best = cand[0]
    print(f"\n## Seçilen kural (doğrulama, iddaa): {best['rule']} ROI {best['roi']:+.3f} "
          f"(geliştirme ROI {dev_roi[(best['rule'], best['price'])]:+.3f})\n")
    # Avg/Max'te en iyi kural (iddaa dışı bilgi amaçlı)
    cand2 = [r for r in res["val"] if r["price"] in ("avg", "avgc") and r.get("n", 0) >= 150
            and not r["rule"].startswith("H:")]
    cand2.sort(key=lambda r: r["roi"], reverse=True)
    best2 = cand2[0]
    print(f"## Seçilen kural (doğrulama, Avg): {best2['rule']} ROI {best2['roi']:+.3f}\n")
    if a.locked:
        rule = R[best["rule"]]
        print("## KİLİTLİ TEST (2526+2627) — tek kural, tek koşu\n\n" + fmt(evaluate(parts["test"], best["rule"], rule)))
        b = parts["test"][rule[0](parts["test"])]
        col = "iddc" if rule[1] == "close" else "idd"
        b = b.assign(pl=pnl(b[col].values, b["win"].values, b["push"].values))
        print(f"\nLig/sezon kırılımı ({col}):\n")
        print(b.groupby("lg")["pl"].agg(["count", "mean"]).round(3).to_markdown())
        print(b.groupby("season")["pl"].agg(["count", "mean"]).round(3).to_markdown())

if __name__ == "__main__":
    main()
