"""Puan Durumu Ajanı: içinde bulunulan sezonun tablosu (genel + iç saha + deplasman), yalnız geçmiş satırlardan.

Kaynak football-data.co.uk olduğu için tablo gerçek puan durumundan birkaç gün geride kalabilir;
`updated` alanı tablodaki en son maçın tarihidir. Puan silme/ceza gibi idari kararlar bu veride yoktur.
Sıralama: puan, averaj, atılan gol, takım adı.
"""
from __future__ import annotations

from datetime import date

from .. import config


def _res(gf: int, ga: int) -> str:
    return "W" if gf > ga else ("D" if gf == ga else "L")


def _table(games: list[dict], venue: str | None) -> list[dict]:
    acc: dict[str, dict] = {}
    for r in sorted(games, key=lambda r: r["date"]):
        for side in ("home", "away"):
            if venue and side != venue:
                continue
            team = r[side]
            gf, ga = (r["hg"], r["ag"]) if side == "home" else (r["ag"], r["hg"])
            t = acc.setdefault(team, {"team": team, "o": 0, "g": 0, "b": 0, "m": 0, "ag": 0, "yg": 0, "_f": []})
            res = _res(gf, ga)
            t["o"] += 1; t["ag"] += gf; t["yg"] += ga
            t[{"W": "g", "D": "b", "L": "m"}[res]] += 1
            t["_f"].append(res)
    out = []
    for t in acc.values():
        f = t.pop("_f")
        t["av"] = t["ag"] - t["yg"]
        t["p"] = 3 * t["g"] + t["b"]
        t["form"] = list(reversed(f[-5:]))   # en yeni başta (stats.team_stats ile aynı yön)
        out.append(t)
    out.sort(key=lambda t: (-t["p"], -t["av"], -t["ag"], t["team"]))
    for i, t in enumerate(out, 1):
        t["pos"] = i
    return out


def season_rows(rows: list[dict], today: date) -> tuple[str | None, list[dict]]:
    """Geçerli sezonun (config.season_codes(today)[0]) bugünden önce oynanmış maçları.
    Geçerli sezonda hiç maç yoksa (sezon yeni başlamadı) satırlardaki en yeni sezona düşer."""
    played = [r for r in rows if r.get("date") and r["date"] < today and r.get("season")]
    if not played:
        return None, []
    cur = config.season_codes(today)[0]
    games = [r for r in played if r["season"] == cur]
    if not games:
        cur = max({r["season"] for r in played}, key=lambda s: int(s[:2]))
        games = [r for r in played if r["season"] == cur]
    return cur, games


def build(rows: list[dict], today: date) -> dict | None:
    season, games = season_rows(rows, today)
    if not games:
        return None
    return {"season": season, "updated": max(r["date"] for r in games).isoformat(),
            "rows": _table(games, None), "home": _table(games, "home"), "away": _table(games, "away")}


def position(table: dict | None, team: str | None) -> dict | None:
    if not table or not team:
        return None
    for t in table["rows"]:
        if t["team"] == team:
            return {"team": team, "pos": t["pos"], "pts": t["p"], "played": t["o"]}
    return None
