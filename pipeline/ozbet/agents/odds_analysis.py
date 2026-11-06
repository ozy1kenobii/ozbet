"""Benzer oranlı geçmiş maçlar ("oran arşivi") — Türk oran analizi sitelerinin yöntemi, dürüst kurulumla.

Yöntem (docs/research/05-oran-analizi.md):
- Eşleşme ham oranla DEĞİL, marjı Shin ile temizlenmiş olasılıkla yapılır (iddaa marjı ~%20, football-data
  ortalaması ~%7; aynı oran farklı olasılık demektir).
- Arşiv: football-data.co.uk kapanış oranları (12k+ maç). Bugünkü maçın (p1, p2) noktasına en yakın k maç,
  en fazla 0,03 uzaklıkta. Önce aynı lig; yetmezse tüm ligler.
- Her market için gözlenen sıklık + Wilson %95 güven aralığı + aynı maçların ortalama piyasa olasılığı.
  "Fark" = gözlenen − piyasa: piyasanın bu olasılık bölgesindeki tarihsel yanılgısı (favori-sürpriz yanlılığı).
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
DISCLAIMER = ("Geçmişte benzer oranla fiyatlanan maçların sonuç dağılımı. Yeni bir tahmin değildir; piyasanın bu "
              "olasılık bölgesindeki tarihsel isabetini gösterir.")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


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
                hg, ag = r["hg"], r["ag"]
                rows.append((lid, q["1"], q["X"], q["2"], q.get("O2.5", np.nan),
                             1 if hg > ag else 0, 1 if hg == ag else 0, 1 if hg < ag else 0,
                             1 if hg + ag > 2 else 0, 1 if hg > 0 and ag > 0 else 0))
        self.n = len(rows)
        if not rows:
            self.lid = np.array([]); self.P = np.zeros((0, 4)); self.Y = np.zeros((0, 5))
            return
        self.lid = np.array([r[0] for r in rows])
        self.P = np.array([r[1:5] for r in rows], float)          # p1, pX, p2, pO2.5
        self.Y = np.array([r[5:] for r in rows], float)            # 1, X, 2, O2.5, KG

    def _nearest(self, mask, p1, p2):
        idx = np.where(mask)[0]
        if not len(idx):
            return idx
        d = np.hypot(self.P[idx, 0] - p1, self.P[idx, 2] - p2)
        ok = d <= MAX_DIST
        idx, d = idx[ok], d[ok]
        return idx[np.argsort(d)[:K]]

    def analyze(self, imp: dict | None, league: str | None) -> dict | None:
        if not imp or "1" not in imp or self.n == 0:
            return None
        p1, p2 = imp["1"], imp["2"]
        scope = "lig"
        idx = self._nearest(self.lid == league, p1, p2) if league else np.array([], int)
        if len(idx) < LOW_N:
            idx = self._nearest(np.ones(self.n, bool), p1, p2)
            scope = "tüm ligler"
        n = len(idx)
        if n < MIN_N:
            return {"status": "az_ornek", "n": n, "disclaimer": DISCLAIMER}
        out = {"status": "ok" if n >= LOW_N else "dusuk_guven", "n": n, "scope": scope,
               "match_point": {"1": round(p1, 3), "X": round(imp["X"], 3), "2": round(p2, 3)},
               "markets": [], "disclaimer": DISCLAIMER}
        P, Y = self.P[idx], self.Y[idx]
        for j, key in enumerate(("1", "X", "2", "O2.5", "BTTS_Y")):
            k = int(Y[:, j].sum())
            lo, hi = wilson(k, n)
            mkt = None
            if j < 3:
                mkt = float(P[:, j].mean())
            elif j == 3:
                v = P[:, 3][~np.isnan(P[:, 3])]
                mkt = float(v.mean()) if len(v) >= MIN_N else None
            out["markets"].append({
                "market": key, "observed": round(k / n, 4), "ci": [round(lo, 4), round(hi, 4)],
                "market_p": round(mkt, 4) if mkt is not None else None,
                "diff": round(k / n - mkt, 4) if mkt is not None else None,
                # fark güven aralığının dışında mı (piyasa olasılığı CI'ın dışında kalıyor)
                "notable": bool(mkt is not None and not (lo <= mkt <= hi)),
            })
        return out
