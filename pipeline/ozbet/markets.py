"""Market anahtarları, etiketler ve skor matrisinden olasılık hesabı."""
from __future__ import annotations

import numpy as np

LABELS = {
    "1": "MS 1", "X": "MS X", "2": "MS 2",
    "1X": "ÇŞ 1X", "X2": "ÇŞ X2", "12": "ÇŞ 12",
    "O1.5": "1.5 Üst", "U1.5": "1.5 Alt",
    "O2.5": "2.5 Üst", "U2.5": "2.5 Alt",
    "O3.5": "3.5 Üst", "U3.5": "3.5 Alt",
    "BTTS_Y": "KG Var", "BTTS_N": "KG Yok",
}
MAIN_MARKETS = list(LABELS)
# Birbirini dışlayan market grupları (marj temizliği için)
GROUPS = {
    "1x2": ["1", "X", "2"],
    "ou15": ["O1.5", "U1.5"],
    "ou25": ["O2.5", "U2.5"],
    "ou35": ["O3.5", "U3.5"],
    "btts": ["BTTS_Y", "BTTS_N"],
}
HTFT_KEYS = [f"{a}/{b}" for a in "1X2" for b in "1X2"]


def outcome_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if market == "1": return hg > ag
    if market == "X": return hg == ag
    if market == "2": return hg < ag
    if market == "1X": return hg >= ag
    if market == "X2": return hg <= ag
    if market == "12": return hg != ag
    if market.startswith("O"): return t > float(market[1:])
    if market.startswith("U"): return t < float(market[1:])
    if market == "BTTS_Y": return hg > 0 and ag > 0
    if market == "BTTS_N": return hg == 0 or ag == 0
    raise KeyError(market)


def probs_from_matrix(m: np.ndarray) -> dict[str, float]:
    """Skor olasılık matrisinden (ev x dep) tüm marketler."""
    m = m / m.sum()
    n = m.shape[0]
    h = np.arange(n)[:, None]
    a = np.arange(n)[None, :]
    tot = h + a
    p = {
        "1": float(m[h > a].sum()), "X": float(np.trace(m)), "2": float(m[h < a].sum()),
    }
    p["1X"] = p["1"] + p["X"]; p["X2"] = p["X"] + p["2"]; p["12"] = p["1"] + p["2"]
    for line in (1.5, 2.5, 3.5):
        o = float(m[tot > line].sum())
        p[f"O{line}"] = o; p[f"U{line}"] = 1 - o
    y = float(m[1:, 1:].sum())
    p["BTTS_Y"] = y; p["BTTS_N"] = 1 - y
    return p
