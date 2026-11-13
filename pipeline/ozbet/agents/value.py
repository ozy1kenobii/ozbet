"""Değer Ajanı: kalibre olasılık, marjı temizlenmiş ima olasılığı eşik kadar aşıyor VE gerçek orandan
beklenen değer pozitifse 'Değerli'. iddaa marjı ~%19 olduğundan etiket bilerek nadirdir; kâr vaadi değildir."""
from __future__ import annotations

from .. import config

MAX_EDGE = 0.20
EXPERIMENTAL = ("C_", "K_", "CR_", "KR_")
VALUE_MARKETS = ["1", "X", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N", "O1.5", "U1.5", "O3.5", "U3.5"]

try:   # kalibrasyon modülü (model/calibration.py) varsa o kullanılır; yoksa MODEL_WEIGHT harmanı
    from ..model.calibration import calibrated_prob as _cal
except Exception:  # noqa: BLE001 — modül yok/bozuk: eski harmana düş
    _cal = None


def calibrated(market: str, model_p: float, implied_p: float | None, league: str | None = None) -> float:
    """Tercih ve değer hesabının ortak olasılığı: kalibrasyon modülü, yoksa p = α·model + (1-α)·piyasa."""
    if _cal is not None:
        try:
            return min(max(float(_cal(market, model_p, implied_p, league)), 0.0), 1.0)
        except Exception:  # noqa: BLE001 — kalibrasyon hatası tercihi düşürmesin
            pass
    if implied_p is None:
        return model_p
    return config.MODEL_WEIGHT * model_p + (1 - config.MODEL_WEIGHT) * implied_p


def shrink(p: float, implied_p: float, trust: float) -> float:
    """Karnede kötü giden markette olasılık ima olasılığa doğru büzülür (trust < 1)."""
    return implied_p + (p - implied_p) * min(trust, 1.0)


def find_value(model_probs: dict | None, odds: dict | None, implied: dict | None,
               trust: dict[str, float] | None = None, league: str | None = None) -> list[dict]:
    if not model_probs or not odds or not implied:
        return []
    out = []
    # Korner/kart marketleri değer etiketi almaz: iddaa'nın sayım kuralı (ör. kırmızı kart kaç sayılır) ile
    # football-data verisinin uyumu karnede doğrulanana kadar deneysel. Olasılıkları yine gösterilir.
    keys = VALUE_MARKETS + [k for k in implied if k not in VALUE_MARKETS and k not in ("1X", "X2", "12")
                            and not k.startswith(EXPERIMENTAL)]
    for k in keys:
        o, ip, mp = odds.get(k), implied.get(k), model_probs.get(k)
        if not (o and ip and mp):
            continue
        if mp - ip > MAX_EDGE:   # HAM model farkı aşırı → büyük olasılıkla veri/eşleme hatası (kalibrasyondan ÖNCE)
            continue
        p = shrink(calibrated(k, mp, ip, league), ip, (trust or {}).get(k, 1.0))
        edge = p - ip
        # Eşik kalibre olasılık üzerinde (VALUE_EDGE_CAL): harman ağırlığıyla çelişmez. iddaa marjı yüksek olduğu
        # için marjsız ima olasılığı aşmak yetmez; gerçek orandan beklenen değer de pozitif olmalı (asıl sıkı şart).
        if edge >= config.VALUE_EDGE_CAL and p >= 0.25 and p * o - 1 > 0:
            out.append({"market": k, "model_p": round(p, 4), "implied_p": round(ip, 4),
                        "odds": o, "edge": round(edge, 4), "ev": round(p * o - 1, 4)})
    out.sort(key=lambda v: -v["ev"])
    return out
