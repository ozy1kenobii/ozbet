"""Kaynak sağlık geçmişi ve uyarılar.

data/health.json son HEALTH_WINDOW_RUNS çalıştırmanın kaynak durumlarını tutar. Her kaynak için:
  history  – son 14 çalıştırmanın durumu (eskiden yeniye)
  streak   – üst üste kaç çalıştırmadır veri gelmiyor
  ok_rate  – penceredeki çalışma oranı
  last_ok  – en son veri getirdiği zaman
  level    – ok | uyari | alarm | kronik | kapali
Alarm kuralı: daha önce çalışan bir kaynak üst üste ≥2 çalıştırma veri getirmezse "alarm".
Penceredeki hiçbir çalıştırmada çalışmamışsa "kronik" (bilinen engel; gürültü yapmasın diye alarm sayılmaz).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

SHOW = 14


def _working(st: dict) -> bool:
    return st.get("status") == "ok" or (st.get("status") == "partial" and st.get("items", 0) > 0)


def update(path: Path, run_time: str, run_label: str, sources: list[dict], quality: dict) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {"runs": []}
    runs = doc.get("runs", [])
    runs.append({"t": run_time, "label": run_label,
                 "sources": {s["id"]: [s["status"], s.get("items", 0)] for s in sources},
                 "quality": {k: quality.get(k) for k in ("league_mapped_pct", "team_match_pct",
                                                         "odds_coverage_pct", "cross_source_match_pct")}})
    runs = runs[-config.HEALTH_WINDOW_RUNS:]
    doc["runs"] = runs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=0), encoding="utf-8")
    return summarize(runs, sources)


def summarize(runs: list[dict], current: list[dict]) -> dict:
    out: dict[str, dict] = {}
    alerts: list[str] = []
    for s in current:
        sid = s["id"]
        seq = []
        last_ok = None
        for r in runs:
            v = r["sources"].get(sid)
            if v is None:
                continue
            st = {"status": v[0], "items": v[1]}
            if st["status"] == "skipped":
                seq.append("skipped")
                continue
            ok = _working(st)
            seq.append("ok" if ok else ("partial" if st["status"] == "partial" else "missing"))
            if ok:
                last_ok = r["t"]
        scored = [x for x in seq if x != "skipped"]
        streak = 0
        for x in reversed(scored):
            if x == "ok":
                break
            streak += 1
        ok_rate = round(sum(1 for x in scored if x == "ok") / len(scored), 3) if scored else None
        if s["status"] == "skipped":
            level = "kapali"
        elif streak == 0:
            level = "ok"
        elif last_ok is None:
            level = "kronik"
        elif streak >= 2:
            level = "alarm"
            alerts.append(f"{s['name']}: {streak} çalıştırmadır veri gelmiyor (son başarılı: {last_ok[:16].replace('T', ' ')})")
        else:
            level = "uyari"
        out[sid] = {"history": seq[-SHOW:], "streak": streak, "ok_rate": ok_rate, "last_ok": last_ok, "level": level}
    return {"sources": out, "alerts": alerts, "runs": len(runs)}
