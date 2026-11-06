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

# Ek marketler (model.extra) — iddaa terimleriyle
EXTRA_LABELS: dict[str, str] = {
    "HT_1": "İY 1", "HT_X": "İY X", "HT_2": "İY 2",
    "HT_O0.5": "İY 0.5 Üst", "HT_U0.5": "İY 0.5 Alt", "HT_O1.5": "İY 1.5 Üst", "HT_U1.5": "İY 1.5 Alt",
    "HT_O2.5": "İY 2.5 Üst", "HT_U2.5": "İY 2.5 Alt",
    "2H_1": "2Y 1", "2H_X": "2Y X", "2H_2": "2Y 2",
    "MGH_1": "Çok gol: 1. yarı", "MGH_X": "Çok gol: eşit", "MGH_2": "Çok gol: 2. yarı",
    "O0.5": "0.5 Üst", "U0.5": "0.5 Alt", "O4.5": "4.5 Üst", "U4.5": "4.5 Alt", "O5.5": "5.5 Üst", "U5.5": "5.5 Alt",
    "G0-1": "Toplam gol 0-1", "G2-3": "Toplam gol 2-3", "G4-5": "Toplam gol 4-5", "G6+": "Toplam gol 6+",
    "ODD": "Toplam gol tek", "EVEN": "Toplam gol çift",
    **{f"{s}_{o}{ln}": f"{'Ev' if s == 'H' else 'Dep'} {ln} {'Üst' if o == 'O' else 'Alt'}"
       for s in "HA" for o in "OU" for ln in (0.5, 1.5, 2.5)},
    **{f"HCP{h:+d}_{r}": f"Hnd ({h:+d}) {'1' if r == '1' else 'X' if r == 'X' else '2'}"
       for h in (-2, -1, 1, 2) for r in "1X2"},
    **{f"{r}&{m}": f"MS {r} & {lab}" for r in "1X2" for m, lab in
       (("O2.5", "2.5 Üst"), ("U2.5", "2.5 Alt"), ("BTTS_Y", "KG Var"), ("BTTS_N", "KG Yok"))},
    "BTTS_Y&O2.5": "KG Var & 2.5 Üst", "BTTS_Y&U2.5": "KG Var & 2.5 Alt",
    "BTTS_N&O2.5": "KG Yok & 2.5 Üst", "BTTS_N&U2.5": "KG Yok & 2.5 Alt",
    "HT_BTTS_Y": "İY KG Var", "HT_BTTS_N": "İY KG Yok", "BOTH_HALVES_O0.5": "İki yarıda da gol",
    "H_WIN_HALF": "Ev bir yarıyı kazanır", "A_WIN_HALF": "Dep bir yarıyı kazanır",
    "H_WIN_NIL": "Ev gol yemeden kazanır", "A_WIN_NIL": "Dep gol yemeden kazanır",
}
# Birbirini dışlayan ek gruplar (marj temizliği için)
EXTRA_GROUPS: dict[str, list[str]] = {
    "ht1x2": ["HT_1", "HT_X", "HT_2"], "2h1x2": ["2H_1", "2H_X", "2H_2"], "mgh": ["MGH_1", "MGH_X", "MGH_2"],
    "goals_range": ["G0-1", "G2-3", "G4-5", "G6+"], "oddeven": ["ODD", "EVEN"],
    "htbtts": ["HT_BTTS_Y", "HT_BTTS_N"],
    "ms_ou25": [f"{r}&{m}" for r in "1X2" for m in ("O2.5", "U2.5")],
    "ms_btts": [f"{r}&{m}" for r in "1X2" for m in ("BTTS_Y", "BTTS_N")],
    "btts_ou25": ["BTTS_Y&O2.5", "BTTS_Y&U2.5", "BTTS_N&O2.5", "BTTS_N&U2.5"],
    **{f"ht_ou{ln}": [f"HT_O{ln}", f"HT_U{ln}"] for ln in (0.5, 1.5, 2.5)},
    **{f"ou{ln}": [f"O{ln}", f"U{ln}"] for ln in (0.5, 4.5, 5.5)},
    **{f"{s}_ou{ln}": [f"{s}_O{ln}", f"{s}_U{ln}"] for s in "HA" for ln in (0.5, 1.5, 2.5)},
    **{f"hcp{h:+d}": [f"HCP{h:+d}_1", f"HCP{h:+d}_X", f"HCP{h:+d}_2"] for h in (-2, -1, 1, 2)},
}
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


def all_groups() -> dict[str, list[str]]:
    from .model import counts
    return {**GROUPS, **EXTRA_GROUPS, **counts.GROUPS}


def all_labels() -> dict[str, str]:
    from .model import counts
    return {**LABELS, **EXTRA_LABELS, **counts.LABELS}


def all_probs(model: dict | None) -> dict[str, float]:
    """Modelin bütün market olasılıkları tek sözlükte: ana + ek gol + korner + kart."""
    if not model:
        return {}
    out = dict(model.get("probs") or {})
    out.update(model.get("extra") or {})
    for kind in ("corners", "cards"):
        out.update((model.get(kind) or {}).get("probs") or {})
    return out


def settle(market: str, ft: list[int], ht: list[int] | None = None) -> bool | None:
    """Bir marketin sonucu. Ana marketler yalnız MS skoruyla; ek gol marketleri İY skoru da gerektirir
    (aynı simülasyon formülleri tek maça uygulanır). Korner/kart için sonuç verisi yoksa None."""
    import numpy as np
    hg, ag = int(ft[0]), int(ft[1])
    if market in LABELS:
        return outcome_won(market, hg, ag)
    if market not in EXTRA_LABELS:
        return None
    needs_ht = market.startswith(("HT_", "2H_", "MGH_", "BOTH_HALVES")) or "WIN_HALF" in market
    if not ht or ht[0] is None:
        if needs_ht:
            return None
        ht = [0, 0]   # yalnız MS skoruna bağlı marketlerde İY değeri sonucu etkilemez
    from .model.simulate import extra_markets
    h1, a1 = np.array([int(ht[0])]), np.array([int(ht[1])])
    v = extra_markets(h1, a1, np.array([hg]) - h1, np.array([ag]) - a1, np.array([1.0]))
    return bool(round(v[market]))


def categories() -> list[dict]:
    """Arayüzdeki "Tüm marketler" sekmeleri: başlık + sıralı market anahtarları."""
    from .model import counts
    line = lambda pre, lines: [f"{pre}{o}{ln}" for ln in lines for o in "OU"]  # noqa: E731
    return [
        {"id": "ms", "title": "Maç sonucu", "keys": ["1", "X", "2", "1X", "X2", "12",
                                                     *[f"HCP{h:+d}_{r}" for h in (-1, 1, -2, 2) for r in "1X2"]]},
        {"id": "gol", "title": "Gol", "keys": [*line("", (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)),
                                               "BTTS_Y", "BTTS_N", "G0-1", "G2-3", "G4-5", "G6+", "ODD", "EVEN"]},
        {"id": "takim", "title": "Takım golü", "keys": [*line("H_", (0.5, 1.5, 2.5)), *line("A_", (0.5, 1.5, 2.5)),
                                                        "H_WIN_NIL", "A_WIN_NIL"]},
        {"id": "yari", "title": "Yarılar", "keys": ["HT_1", "HT_X", "HT_2", *line("HT_", (0.5, 1.5, 2.5)),
                                                    "HT_BTTS_Y", "HT_BTTS_N", "2H_1", "2H_X", "2H_2",
                                                    "MGH_1", "MGH_X", "MGH_2", "BOTH_HALVES_O0.5",
                                                    "H_WIN_HALF", "A_WIN_HALF"]},
        {"id": "kombi", "title": "Kombine", "keys": [*[f"{r}&{m}" for r in "1X2" for m in ("O2.5", "U2.5")],
                                                     *[f"{r}&{m}" for r in "1X2" for m in ("BTTS_Y", "BTTS_N")],
                                                     "BTTS_Y&O2.5", "BTTS_Y&U2.5", "BTTS_N&O2.5", "BTTS_N&U2.5"]},
        {"id": "korner", "title": "Korner", "keys": [*line("C_", counts.CORNER_LINES), "CR_1", "CR_X", "CR_2"]},
        {"id": "kart", "title": "Kart", "keys": [*line("K_", counts.CARD_LINES), "KR_1", "KR_X", "KR_2"]},
    ]
