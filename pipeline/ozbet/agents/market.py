"""Piyasa Ajanı: marjı temizlenmiş ima olasılık, oran hareketi, düşen oran alarmı."""
from __future__ import annotations

from .. import config
from ..markets import GROUPS


def implied(odds: dict[str, float] | None) -> dict | None:
    if not odds:
        return None
    imp, margin = {}, {}
    for g, keys in GROUPS.items():
        if all(odds.get(k) and odds[k] > 1.0 for k in keys):
            raw = [1 / odds[k] for k in keys]
            s = sum(raw)
            margin[g] = round(s - 1, 4)
            for k, r in zip(keys, raw):
                imp[k] = round(r / s, 4)   # orantısal marj temizliği
    if "1" in imp:
        imp["1X"] = round(imp["1"] + imp["X"], 4)
        imp["X2"] = round(imp["X"] + imp["2"], 4)
        imp["12"] = round(imp["1"] + imp["2"], 4)
    # Çifte şans oranları bülten tarafından ayrıca verilmişse onlar için ham ima olasılık
    return {"implied": imp, "margin": margin} if imp else None


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
