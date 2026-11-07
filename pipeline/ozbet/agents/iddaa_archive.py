"""iddaa oran arşivi — her çalıştırmada bültendeki maçların oranlarını ay parçalı dosyalara birleştirir.

Dosya: data/iddaa_archive/YYYY-MM.json  {"month": "YYYY-MM", "rows": [satır, ...]}
Satır: id, code, d (gün), ko (başlama ISO), lg, lgn, h, a, hk, ak (team_key),
       o {açılış: ilk görülen tüm marketler}, c {kapanış: ko'dan ÖNCE görülen son oranlar},
       ts_o, ts_c, n_snap (ko öncesi oranlı görülme sayısı), ft [h,a]|null, ht [h,a]|null, rsrc, rts
Kurallar: açılış bir kez yazılır; kapanış yalnız ko'dan önceki çalıştırmalarda güncellenir.
Manifest: data/iddaa_archive/index.json  {"months": {"YYYY-MM": {"rows": N, "resulted": M}}, "rows", "resulted", "updated"}
Sonuç doldurma: son 7 gündeki ft'si boş, başlamış satırlar registry.lookup_result ile (football-data/TFF/arşiv).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from ..teams import team_key

DIR = "iddaa_archive"
FILL_DAYS = 7


def _path(data: Path, month: str) -> Path:
    return data / DIR / f"{month}.json"


def load_month(data: Path, month: str) -> dict[str, dict]:
    p = _path(data, month)
    if not p.exists():
        return {}
    try:
        return {r["id"]: r for r in json.loads(p.read_text("utf-8")).get("rows", [])}
    except Exception:  # noqa: BLE001
        return {}


def save_month(data: Path, month: str, rows: dict[str, dict]) -> None:
    p = _path(data, month)
    p.parent.mkdir(parents=True, exist_ok=True)
    lst = sorted(rows.values(), key=lambda r: (r["ko"], r["id"]))
    p.write_text(json.dumps({"month": month, "rows": lst}, ensure_ascii=False, separators=(",", ":")), "utf-8")


def merge_row(rows: dict[str, dict], m: dict, odds: dict | None, now: datetime) -> dict:
    """Bir maçı arşiv sözlüğüne birleştirir. m: run.py maç sözlüğü (id, code, kickoff, league, ...)."""
    ts = now.isoformat(timespec="seconds")
    ko = datetime.fromisoformat(m["kickoff"])
    r = rows.get(m["id"])
    if r is None:
        h, a = m["home"]["name"], m["away"]["name"]
        r = {"id": m["id"], "code": m.get("code"), "d": m["kickoff"][:10], "ko": m["kickoff"],
             "lg": m.get("league"), "lgn": m.get("league_name"), "h": h, "a": a, "hk": team_key(h), "ak": team_key(a),
             "o": {}, "c": {}, "ts_o": None, "ts_c": None, "n_snap": 0, "ft": None, "ht": None, "rsrc": None, "rts": None}
        rows[m["id"]] = r
    if odds:
        clean = {k: round(float(v), 2) for k, v in odds.items() if isinstance(v, (int, float)) and v > 1}
        if clean and not r["o"]:
            r["o"], r["ts_o"] = clean, ts                      # açılış: bir kez
        if clean and now < ko:
            r["c"], r["ts_c"] = clean, ts                      # kapanış: yalnız başlamadan önce
            r["n_snap"] += 1
    return r


def update(data: Path, matches: list[dict], odds_by_id: dict[str, dict], now: datetime) -> int:
    by_month: dict[str, list[dict]] = {}
    for m in matches:
        by_month.setdefault(m["kickoff"][:7], []).append(m)
    n = 0
    for month, lst in by_month.items():
        rows = load_month(data, month)
        for m in lst:
            merge_row(rows, m, odds_by_id.get(m["id"]) or m.get("odds"), now)
            n += 1
        save_month(data, month, rows)
    return n


def fill_results(data: Path, today: date, now: datetime, sources: list[tuple[str, dict]], lookup) -> int:
    """sources: [(kaynak adı, {(gün, hk, ak): {"ft":..,"ht":..}})] öncelik sırasıyla; lookup=registry.lookup_result."""
    start = today - timedelta(days=FILL_DAYS)
    months = sorted({(start + timedelta(days=i)).isoformat()[:7] for i in range(FILL_DAYS + 1)})
    filled = 0
    for month in months:
        rows = load_month(data, month)
        changed = False
        for r in rows.values():
            if r.get("ft") or not (start.isoformat() <= r["d"] <= today.isoformat()):
                continue
            if datetime.fromisoformat(r["ko"]) > now:
                continue
            for name, res in sources:
                got = lookup(res, r["ko"], r["h"], r["a"]) if res else None
                if got and got.get("ft"):
                    r["ft"], r["ht"] = list(got["ft"]), (list(got["ht"]) if got.get("ht") else None)
                    r["rsrc"], r["rts"] = name, now.isoformat(timespec="seconds")
                    filled += 1; changed = True
                    break
        if changed:
            save_month(data, month, rows)
    return filled


def all_rows(data: Path) -> list[dict]:
    out = []
    for p in sorted((data / DIR).glob("????-??.json")):
        out += list(load_month(data, p.stem).values())
    return out


def write_index(data: Path, now: datetime) -> dict:
    months = {}
    for p in sorted((data / DIR).glob("????-??.json")):
        rows = load_month(data, p.stem).values()
        months[p.stem] = {"rows": len(rows), "resulted": sum(1 for r in rows if r.get("ft"))}
    idx = {"months": months, "rows": sum(v["rows"] for v in months.values()),
           "resulted": sum(v["resulted"] for v in months.values()), "updated": now.isoformat(timespec="seconds")}
    (data / DIR).mkdir(parents=True, exist_ok=True)
    (data / DIR / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), "utf-8")
    return idx
