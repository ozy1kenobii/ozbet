"""Birikimli sonuç arşivi: data/archive/results-{LIG}.json

Pipeline her çalıştırmada sonuç feed'inden (flashscore, dün ve kaçırılan son 7 gün) biten maçları lig bazında
bu dosyalara ekler. Tekrarlı kayıt olmaz (anahtar: tarih + takım anahtarları). Lig, feed'deki lig başlığından
`bulletin.league_for` ile belirlenir; eşlenemeyen ligler, kupalar, kadın/altyapı ligleri arşive girmez.

Dosya şeması:
{
  "league": "TR2", "updated_at": "...",
  "days": ["2026-11-04", ...],                   # feed'i işlenmiş günler (tekrar indirmemek için)
  "rows": [{"date":"2026-11-04","home":"Boluspor","away":"Manisa FK","ft":[1,2],"ht":[1,0],
            "src":"flashscore","fs_id":"abc"}]
}
`history_rows()` bunları football_data.history() satır biçimine çevirir; en az ARCHIVE_MIN_MATCHES maç olan
ligler registry.extra_history üzerinden modele girer.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from .. import config
from ..teams import team_key
from .base import Fixture, now_iso

log = logging.getLogger("ozbet.archive")
BACKFILL_DAYS = 7      # flashscore feed'i en fazla 7 gün geriye gider


def path_for(data_dir: Path, league_id: str) -> Path:
    return Path(data_dir) / "archive" / f"results-{league_id}.json"


def load(data_dir: Path, league_id: str) -> dict:
    p = path_for(data_dir, league_id)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and isinstance(doc.get("rows"), list):
            doc.setdefault("days", [])
            return doc
    except (OSError, ValueError):
        pass
    return {"league": league_id, "updated_at": None, "days": [], "rows": []}


def save(data_dir: Path, league_id: str, doc: dict):
    p = path_for(data_dir, league_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(p)


def _key(d: str, home: str, away: str) -> tuple[str, str, str]:
    return d, team_key(home), team_key(away)


def merge_rows(doc: dict, fixtures: Iterable[Fixture]) -> int:
    """Biten maçları dokümana ekler; eklenen satır sayısını döndürür (tekrarlar atlanır)."""
    seen = {_key(r["date"], r["home"], r["away"]) for r in doc["rows"]}
    ids = {r.get("fs_id") for r in doc["rows"] if r.get("fs_id")}
    added = 0
    for f in fixtures:
        if not f.result or not f.result.get("ft"):
            continue
        d = f.kickoff.date().isoformat()
        k = _key(d, f.home, f.away)
        fid = f.extra.get("flashscore_id")
        if k in seen or (fid and fid in ids):
            continue
        ht = f.result.get("ht")
        doc["rows"].append({"date": d, "home": f.home, "away": f.away,
                            "ft": [int(f.result["ft"][0]), int(f.result["ft"][1])],
                            "ht": [int(ht[0]), int(ht[1])] if ht and None not in ht else None,
                            "src": f.source, **({"fs_id": fid} if fid else {})})
        seen.add(k)
        if fid:
            ids.add(fid)
        added += 1
    doc["rows"].sort(key=lambda r: (r["date"], r["home"]))
    return added


def archivable(league_id: str | None) -> bool:
    lg = config.LEAGUE_BY_ID.get(league_id or "")
    return bool(lg and not lg.cup)


def update(data_dir: Path, today: date, feed: Callable[[date], list[Fixture]],
           backfill: int = BACKFILL_DAYS) -> dict[str, int]:
    """feed(gün) → o günün flashscore fikstürleri (sonuçlu). Dünden geriye, işlenmemiş günleri işler.
    Dün her zaman yeniden okunur (geç biten maçlar için); daha eskiler yalnızca daha önce işlenmediyse.
    Dönüş: {lig: eklenen satır}."""
    docs: dict[str, dict] = {}
    added: dict[str, int] = {}
    done_any = set()
    for lg in config.LEAGUES:
        if not lg.cup:
            p = path_for(data_dir, lg.id)
            if p.exists():
                docs[lg.id] = load(data_dir, lg.id)
                done_any.update(docs[lg.id].get("days", []))
    for k in range(1, backfill + 1):
        day = today - timedelta(days=k)
        ds = day.isoformat()
        if k > 1 and ds in done_any:
            continue
        try:
            fx = feed(day)
        except Exception as e:  # noqa: BLE001 — eski günler alınamazsa sorun değil
            if k == 1:
                raise
            log.info("arşiv: %s alınamadı: %s", ds, e)
            continue
        by_lg: dict[str, list[Fixture]] = {}
        for f in fx:
            if f.result and f.kickoff.date() == day and archivable(f.league_id):
                by_lg.setdefault(f.league_id, []).append(f)
        for lid, lst in by_lg.items():
            doc = docs.setdefault(lid, load(data_dir, lid))
            n = merge_rows(doc, lst)
            if n:
                added[lid] = added.get(lid, 0) + n
        for doc in docs.values():
            if ds not in doc["days"]:
                doc["days"] = sorted({*doc["days"], ds})[-400:]
        done_any.add(ds)
    t = now_iso()
    for lid, doc in docs.items():
        doc["updated_at"] = t
        save(data_dir, lid, doc)
    return added


def _season(d: date) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def history_rows(data_dir: Path, league_id: str) -> list[dict]:
    """Arşivi football_data.history() satır biçimine çevirir."""
    out = []
    for r in load(data_dir, league_id)["rows"]:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            hg, ag = int(r["ft"][0]), int(r["ft"][1])
        except (KeyError, ValueError, TypeError, IndexError):
            continue
        ht = r.get("ht") or [None, None]
        out.append({"date": d, "season": _season(d), "home": r["home"], "away": r["away"], "hg": hg, "ag": ag,
                    "hthg": ht[0], "htag": ht[1], "odds_open": {}, "odds_close": {},
                    "src": f"arşiv ({r.get('src', '?')})"})
    return out


def leagues(data_dir: Path) -> list[str]:
    d = Path(data_dir) / "archive"
    if not d.is_dir():
        return []
    return sorted(p.stem.removeprefix("results-") for p in d.glob("results-*.json"))
