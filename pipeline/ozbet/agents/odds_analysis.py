"""Benzer oranlı geçmiş maçlar ("oran arşivi") — Türk oran analizi sitelerinin yöntemi, dürüst kurulumla.

Yöntem (docs/research/05-oran-analizi.md):
- Eşleşme ham oranla DEĞİL, marjı Shin ile temizlenmiş olasılıkla yapılır (iddaa marjı ~%20, football-data
  ortalaması ~%7; aynı oran farklı olasılık demektir).
- Arşiv: football-data.co.uk kapanış oranları (12k+ maç). Bugünkü maçın (p1, p2) noktasına en yakın k maç,
  en fazla 0,03 uzaklıkta. Önce aynı lig; yetmezse tüm ligler.
- Her market için gözlenen sıklık + Wilson %95 güven aralığı + aynı maçların ortalama piyasa olasılığı.
- Kilitli test (benzer-oran-istat): benzer maçların dağılımı ima olasılıktan DAHA İYİ tahmin etmiyor. Bu yüzden
  "değer/dikkat çekici" etiketi yok; yalnız nötr not: "piyasayla uyumlu" ya da "fark GA dışında".
- Ek: toplam gol dağılımı (0..5+) ve skor ızgarası (0-4 × 0-4) yüzde olarak.
- Örneklem 100'ün altındaysa gösterilmez; 300'ün altındaysa "düşük güven".
Bu kutu yeni bir tahmin üretmez; geçmişte benzer fiyatlanan maçların ne olduğunu gösterir.
"""
from __future__ import annotations

import math

import numpy as np

from .market import implied

K = 400
MAX_DIST = 0.03
MIN_N = 100
LOW_N = 300
IDDAA_MIN_N = 30
GRID = 5            # skor ızgarası 0..4 × 0..4
GOAL_BINS = 6       # toplam gol 0,1,2,3,4,5+
DISCLAIMER = ("Geçmişte benzer oranla fiyatlanan maçların sonuç dağılımı. Yeni bir tahmin değildir; testte bu "
              "dağılım piyasanın marjsız olasılığından daha iyi tahmin etmedi.")
NOTE_OK = "piyasayla uyumlu"
NOTE_OUT = "fark GA dışında (çoklu karşılaştırmada rastlantı olabilir)"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def rows_from_iddaa(archive_rows: list[dict]) -> dict[str, list[dict]]:
    """iddaa arşivi satırları → Pool girdisi (kapanış yoksa açılış oranı; yalnız sonuçlu satırlar)."""
    out: dict[str, list[dict]] = {}
    for r in archive_rows:
        if not r.get("ft"):
            continue
        odds = r.get("c") or r.get("o") or {}
        out.setdefault(r.get("lg") or "OTHER", []).append(
            {"date": r.get("d"), "hg": r["ft"][0], "ag": r["ft"][1], "odds_close": odds})
    return out


class Pool:
    def __init__(self, hist: dict[str, list[dict]]):
        rows = []
        for lid, lst in hist.items():
            for r in lst:
                odds = r.get("odds_close") or r.get("odds_open") or {}
                mk = implied(odds)
                if not mk or "1" not in mk["implied"]:
                    continue
                q = mk["implied"]
                hg, ag = int(r["hg"]), int(r["ag"])
                d = r.get("date")
                rows.append((lid, str(d.isoformat() if hasattr(d, "isoformat") else d or ""),
                             q["1"], q["X"], q["2"], q.get("O2.5", np.nan),
                             1 if hg > ag else 0, 1 if hg == ag else 0, 1 if hg < ag else 0,
                             1 if hg + ag > 2 else 0, 1 if hg + ag <= 2 else 0,
                             min(hg + ag, GOAL_BINS - 1),
                             hg * GRID + ag if hg < GRID and ag < GRID else -1))
        self.n = len(rows)
        if not rows:
            self.lid = np.array([]); self.dates = np.array([]); self.P = np.zeros((0, 4)); self.Y = np.zeros((0, 5))
            self.G = np.zeros(0, int); self.S = np.zeros(0, int)
            return
        self.lid = np.array([r[0] for r in rows])
        self.dates = np.array([r[1] for r in rows])
        self.P = np.array([r[2:6] for r in rows], float)          # p1, pX, p2, pO2.5
        self.Y = np.array([r[6:11] for r in rows], float)          # 1, X, 2, O2.5, U2.5
        self.G = np.array([r[11] for r in rows], int)              # toplam gol kovası
        self.S = np.array([r[12] for r in rows], int)              # skor hücresi (-1: ızgara dışı)

    def _nearest(self, mask, p1, p2):
        idx = np.where(mask)[0]
        if not len(idx):
            return idx
        d = np.hypot(self.P[idx, 0] - p1, self.P[idx, 2] - p2)
        ok = d <= MAX_DIST
        idx, d = idx[ok], d[ok]
        return idx[np.argsort(d)[:K]]

    def analyze(self, imp: dict | None, league: str | None, min_n: int = MIN_N) -> dict | None:
        if not imp or "1" not in imp or self.n == 0:
            return None
        p1, p2 = imp["1"], imp["2"]
        scope = "lig"
        idx = self._nearest(self.lid == league, p1, p2) if league else np.array([], int)
        if len(idx) < LOW_N:
            idx = self._nearest(np.ones(self.n, bool), p1, p2)
            scope = "tüm ligler"
        n = len(idx)
        if n < min_n:
            return {"status": "az_ornek", "n": n, "disclaimer": DISCLAIMER}
        ds = sorted(x for x in self.dates[idx] if x)
        out = {"status": "ok" if n >= LOW_N else "dusuk_guven", "n": n, "scope": scope,
               "match_point": {"1": round(p1, 3), "X": round(imp["X"], 3), "2": round(p2, 3)},
               "date_range": [ds[0][:10], ds[-1][:10]] if ds else None,
               "markets": [], "disclaimer": DISCLAIMER}
        P, Y = self.P[idx], self.Y[idx]
        vo = P[:, 3][~np.isnan(P[:, 3])]
        po = float(vo.mean()) if len(vo) >= min_n else None
        for j, key in enumerate(("1", "X", "2", "O2.5", "U2.5")):
            k = int(Y[:, j].sum())
            lo, hi = wilson(k, n)
            mkt = float(P[:, j].mean()) if j < 3 else (po if j == 3 else (1 - po if po is not None else None))
            out["markets"].append({
                "market": key, "observed": round(k / n, 4), "ci": [round(lo, 4), round(hi, 4)],
                "market_p": round(mkt, 4) if mkt is not None else None,
                "note": None if mkt is None else (NOTE_OK if lo <= mkt <= hi else NOTE_OUT),
            })
        g = np.bincount(self.G[idx], minlength=GOAL_BINS)
        out["goals"] = [round(int(c) / n, 4) for c in g]
        s = self.S[idx]
        cells = np.bincount(s[s >= 0], minlength=GRID * GRID)
        out["scores"] = [[round(int(cells[h * GRID + a]) / n, 4) for a in range(GRID)] for h in range(GRID)]
        out["scores_other"] = round(int((s < 0).sum()) / n, 4)
        return out
