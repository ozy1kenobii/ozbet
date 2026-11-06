"""Değer Ajanı: model olasılığı, marjı temizlenmiş ima olasılığı eşik kadar aşıyorsa 'Değerli'."""
from __future__ import annotations

from .. import config

MAX_EDGE = 0.20
EXPERIMENTAL = ("C_", "K_", "CR_", "KR_")
VALUE_MARKETS = ["1", "X", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N", "O1.5", "U1.5", "O3.5", "U3.5"]


def find_value(model_probs: dict | None, odds: dict | None, implied: dict | None,
               trust: dict[str, float] | None = None) -> list[dict]:
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
        mp = config.MODEL_WEIGHT * mp + (1 - config.MODEL_WEIGHT) * ip   # piyasa ile harman (backtest'e göre)
        if mp - ip > MAX_EDGE:   # ham fark aşırı → büyük olasılıkla veri/eşleme hatası; büzülme bunu gizlemesin
            continue
        t = (trust or {}).get(k, 1.0)
        # Karnede kötü giden markette model olasılığı ima olasılığa doğru büzülür
        mp_adj = ip + (mp - ip) * min(t, 1.0)
        edge = mp_adj - ip
        # iddaa marjı yüksek (~%20): marjsız ima olasılığı aşmak yetmez, gerçek orandan beklenen değer de pozitif olmalı
        if edge >= config.VALUE_EDGE and mp_adj >= 0.25 and mp_adj * o - 1 > 0:
            out.append({"market": k, "model_p": round(mp_adj, 4), "implied_p": round(ip, 4),
                        "odds": o, "edge": round(edge, 4), "ev": round(mp_adj * o - 1, 4)})
    out.sort(key=lambda v: -v["ev"])
    return out
