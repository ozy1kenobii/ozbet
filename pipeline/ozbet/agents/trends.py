"""Trend / Seri Ajanı: takımların son maçlarından kural tabanlı tek cümlelik seri kartları.

Kartlar geçmişi özetler, tahmin değildir. Gürültüyü azaltmak için yalnızca şu kartlar üretilir:
  - en az MIN_N maçlık pencerede oran ≥ %80 ya da ≤ %20, veya
  - seri uzunluğu ≥ MIN_STREAK.
Her kart bir markete bağlanır; kartta o marketin model olasılığı ve bültendeki oranı da yer alır.
"""
from __future__ import annotations

from datetime import date

from ..model.counts import CARD_LINES, CORNER_LINES

MIN_N = 5
HI, LO = 0.80, 0.20
MIN_STREAK = 4
MAX_CARDS = 6
DISCLAIMER = "Trend kartları geçmiş maçları özetler, tahmin değildir."

VENUE_TXT = {"home": "iç saha", "away": "deplasman"}


def _persp(r: dict, team: str) -> dict:
    h = r["home"] == team
    gf, ga = (r["hg"], r["ag"]) if h else (r["ag"], r["hg"])
    ht = None if r.get("hthg") is None or r.get("htag") is None else r["hthg"] + r["htag"]
    cor = None if r.get("hc") is None or r.get("ac") is None else r["hc"] + r["ac"]
    crd = None
    if r.get("hy") is not None and r.get("ay") is not None:
        crd = r["hy"] + r["ay"] + 2 * ((r.get("hr") or 0) + (r.get("ar") or 0))
    return {"gf": gf, "ga": ga, "ht": ht, "cor": cor, "crd": crd}


def _past(rows, team, before, venue=None):
    out = [r for r in rows if r["date"] < before and team in (r["home"], r["away"])]
    if venue:
        out = [r for r in out if r[venue] == team]
    return sorted(out, key=lambda r: r["date"], reverse=True)


# (anahtar, koşul, (yüksekte metin, market), (düşükte metin, market) | None — 'gol attı' gibi sıradan durumlar kart olmaz); market'te {s}=H/A takım, {o}=rakip
RATE_RULES = [
    ("o25", lambda p: p["gf"] + p["ga"] > 2, ("2.5 Üst bitti", "O2.5"), ("2.5 Alt bitti", "U2.5")),
    ("btts", lambda p: p["gf"] > 0 and p["ga"] > 0, ("KG Var bitti", "BTTS_Y"), ("KG Yok bitti", "BTTS_N")),
    ("fts", lambda p: p["gf"] == 0, ("gol atamadı", "{s}_U0.5"), None),
    ("cs", lambda p: p["ga"] == 0, ("gol yemedi", "{o}_U0.5"), None),
    ("ht", lambda p: p["ht"] is not None and p["ht"] > 0, ("İY 0.5 Üst bitti", "HT_O0.5"), ("ilk yarı golsüz bitti", "HT_U0.5")),
]


def _window_text(name, venue, k, n):
    scope = f"son {n} {VENUE_TXT[venue]} maçının" if venue else f"son {n} maçının"
    return f"{name}, {scope} {k}'{_suffix(k)}"


def _suffix(k: int) -> str:
    """Sayıya iyelik + bulunma eki: 1'inde, 2'sinde, 3'ünde, 6'sında, 9'unda, 10'unda."""
    if k % 10 == 0:
        return {10: "unda", 20: "sinde", 30: "unda", 40: "ında", 50: "sinde"}.get(k, "ında")
    return {1: "inde", 2: "sinde", 3: "ünde", 4: "ünde", 5: "inde", 6: "sında", 7: "sinde", 8: "inde", 9: "unda"}[k % 10]


def team_cards(rows, team, name, side, before, league_avg=None) -> list[dict]:
    """side: bugünkü maçta 'home' ya da 'away'. Aday kartlar (güç puanıyla)."""
    s, o = ("H", "A") if side == "home" else ("A", "H")
    out = []
    windows = [(side, 6), (None, 6), (None, 10)]
    for key, cond, hi, lo in RATE_RULES:
        best = None
        for venue, n in windows:
            ps = [_persp(r, team) for r in _past(rows, team, before, venue)[:n]]
            if key == "ht":
                ps = [p for p in ps if p["ht"] is not None]
            if len(ps) < MIN_N:
                continue
            hits = sum(1 for p in ps if cond(p))
            rate = hits / len(ps)
            if rate >= HI:
                txt, mk, k = hi[0], hi[1], hits
            elif rate <= LO and lo:
                txt, mk, k = lo[0], lo[1], len(ps) - hits
            else:
                continue
            score = abs(rate - 0.5) + 0.02 * len(ps) + (0.03 if venue else 0)
            if best is None or score > best["_s"]:
                best = {"team": side, "kind": key, "text": f"{_window_text(name, venue, k, len(ps))} {txt}",
                        "market": mk.format(s=s, o=o), "hits": k, "n": len(ps), "_s": score}
        if best:
            out.append(best)
    out += _streaks(rows, team, name, side, before)
    if league_avg:
        out += _counts(rows, team, name, side, before, league_avg)
    return out


def _streaks(rows, team, name, side, before):
    ps = [_persp(r, team) for r in _past(rows, team, before, side)]
    out = []
    unbeaten = next((i for i, p in enumerate(ps) if p["gf"] < p["ga"]), len(ps))
    winless = next((i for i, p in enumerate(ps) if p["gf"] > p["ga"]), len(ps))
    v = VENUE_TXT[side]
    # ev sahibi yenilmez → 1X; deplasman yenilmez → X2; galibiyetsizlikte tersi
    if unbeaten >= MIN_STREAK:
        out.append({"team": side, "kind": "unbeaten", "text": f"{name}, {v}da son {unbeaten} maçtır yenilmiyor",
                    "market": "1X" if side == "home" else "X2", "hits": unbeaten, "n": unbeaten,
                    "_s": 0.3 + 0.03 * unbeaten})
    if winless >= MIN_STREAK:
        out.append({"team": side, "kind": "winless", "text": f"{name}, {v}da son {winless} maçtır kazanamıyor",
                    "market": "X2" if side == "home" else "1X", "hits": winless, "n": winless,
                    "_s": 0.3 + 0.03 * winless})
    return out


def _line(avg: float, lines) -> float:
    return min(lines, key=lambda ln: abs(ln - avg))


def _counts(rows, team, name, side, before, league_avg):
    out = []
    ps = [_persp(r, team) for r in _past(rows, team, before)[:10]]
    for key, field, lines, thr, word, pre in (("corners", "cor", CORNER_LINES, 2.0, "korner", "C"),
                                              ("cards", "crd", CARD_LINES, 1.0, "kart", "K")):
        avg_l = league_avg.get(key)
        vals = [p[field] for p in ps if p[field] is not None]
        if avg_l is None or len(vals) < MIN_N:
            continue
        avg_t = sum(vals) / len(vals)
        if abs(avg_t - avg_l) < thr:
            continue
        ln = _line(avg_l, lines)
        hits = sum(1 for v in vals if v > ln)
        rate = hits / len(vals)
        if avg_t > avg_l and rate >= HI:
            mk, k, yon = f"{pre}_O{ln}", hits, "üstünde"
        elif avg_t < avg_l and rate <= LO:
            mk, k, yon = f"{pre}_U{ln}", len(vals) - hits, "altında"
        else:
            continue
        ust = "Üst" if mk[2] == "O" else "Alt"
        out.append({"team": side, "kind": key,
                    "text": (f"{name} maçlarında {word} ortalaması {avg_t:.1f}, lig ortalamasının ({avg_l:.1f}) "
                             f"belirgin {yon}; son {len(vals)} maçın {k}'{_suffix(k)} {word} {ln} {ust}"),
                    "market": mk, "hits": k, "n": len(vals), "_s": abs(rate - 0.5) + 0.1})
    return out


def h2h_cards(rows, a, b, before, n=6):
    games = sorted((r for r in rows if r["date"] < before and {r["home"], r["away"]} == {a, b}),
                   key=lambda r: r["date"], reverse=True)[:n]
    if len(games) < MIN_N:
        return []
    out = []
    for key, cond, hi, lo in RATE_RULES[:2]:
        hits = sum(1 for r in games if cond({"gf": r["hg"], "ga": r["ag"], "ht": None}))
        rate = hits / len(games)
        if rate >= HI:
            txt, mk, k = hi[0], hi[1], hits
        elif rate <= LO:
            txt, mk, k = lo[0], lo[1], len(games) - hits
        else:
            continue
        out.append({"team": "both", "kind": f"h2h_{key}",
                    "text": f"Aralarındaki son {len(games)} maçın {k}'{_suffix(k)} {txt}",
                    "market": mk, "hits": k, "n": len(games), "_s": abs(rate - 0.5)})
    return out


def league_averages(rows: list[dict]) -> dict:
    cor = [r["hc"] + r["ac"] for r in rows if r.get("hc") is not None and r.get("ac") is not None]
    crd = [r["hy"] + r["ay"] + 2 * ((r.get("hr") or 0) + (r.get("ar") or 0))
           for r in rows if r.get("hy") is not None and r.get("ay") is not None]
    return {"corners": sum(cor) / len(cor) if len(cor) >= 30 else None,
            "cards": sum(crd) / len(crd) if len(crd) >= 30 else None}


def build(rows: list[dict], th: str, ta: str, home_name: str, away_name: str, before: date,
          probs: dict | None = None, odds: dict | None = None, league_avg: dict | None = None) -> list[dict]:
    cands = (team_cards(rows, th, home_name, "home", before, league_avg)
             + team_cards(rows, ta, away_name, "away", before, league_avg)
             + h2h_cards(rows, th, ta, before))
    cands.sort(key=lambda c: -c["_s"])
    out, seen = [], set()
    for c in cands:
        sig = (c["team"], c["market"])
        if sig in seen:
            continue
        seen.add(sig)
        c.pop("_s"); c.pop("kind", None)
        p = (probs or {}).get(c["market"])
        c["p"] = round(float(p), 4) if p is not None else None
        o = (odds or {}).get(c["market"])
        c["odds"] = o
        out.append(c)
        if len(out) >= MAX_CARDS:
            break
    return out
