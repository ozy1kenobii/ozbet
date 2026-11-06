"""Piyasa Ajanı: marjı temizlenmiş ima olasılık, oran hareketi, düşen oran alarmı."""
from __future__ import annotations

from .. import config
from ..markets import all_groups


def shin(odds: list[float]) -> list[float]:
    """Shin (1993) marj temizleme: bahisçinin 'içeriden bilgi' payı z ile, marjın sürpriz (yüksek oran)
    tarafına orantısız yüklendiğini varsayar. Favori-sürpriz yanlılığını orantısal yöntemden iyi düzeltir
    (Štrumbelj 2014). z, olasılıkların toplamı 1 olacak şekilde ikiye bölmeyle çözülür."""
    pi = [1 / o for o in odds]
    S = sum(pi)
    if S <= 1.0:
        return [x / S for x in pi]
    def probs(z):
        return [((z * z + 4 * (1 - z) * x * x / S) ** 0.5 - z) / (2 * (1 - z)) for x in pi]
    lo, hi = 0.0, 0.4
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(probs(mid)) > 1:
            lo = mid
        else:
            hi = mid
    p = probs((lo + hi) / 2)
    t = sum(p)
    return [x / t for x in p]


def implied(odds: dict[str, float] | None, method: str = "shin") -> dict | None:
    if not odds:
        return None
    imp, margin = {}, {}
    for g, keys in all_groups().items():
        if all(odds.get(k) and odds[k] > 1.0 for k in keys):
            raw = [1 / odds[k] for k in keys]
            s = sum(raw)
            margin[g] = round(s - 1, 4)
            fair = shin([odds[k] for k in keys]) if method == "shin" else [r / s for r in raw]
            for k, r in zip(keys, fair):
                imp[k] = round(r, 4)
    if "1" in imp:
        imp["1X"] = round(imp["1"] + imp["X"], 4)
        imp["X2"] = round(imp["X"] + imp["2"], 4)
        imp["12"] = round(imp["1"] + imp["2"], 4)
    # Çifte şans oranları bülten tarafından ayrıca verilmişse onlar için ham ima olasılık
    return {"implied": imp, "margin": margin, "method": method} if imp else None


def movement(history: list[dict]) -> tuple[dict[str, float], list[str]]:
    """history: [{"t":..., "1":2.1, ...}] kronolojik. İlk görülen → son oran oransal değişim."""
    if len(history) < 2:
        return {}, []
    first, last = history[0], history[-1]
    mv, alarms = {}, []
    for k, v in last.items():
        if k == "t" or not isinstance(v, (int, float)):
            continue
        f = first.get(k)
        if isinstance(f, (int, float)) and f > 1:
            ch = round(v / f - 1, 4)
            if abs(ch) >= 0.01:
                mv[k] = ch
            if ch <= -config.DROP_ALARM:
                alarms.append(k)
    return mv, alarms
