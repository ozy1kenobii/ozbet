"""Adapter'ların ortak tipleri ve kaynak durum takibi."""
from __future__ import annotations

import logging
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable

from .. import config

log = logging.getLogger("ozbet.sources")


def now_iso() -> str:
    return datetime.now(config.TZ).isoformat(timespec="seconds")


@dataclass
class Fixture:
    league_id: str | None
    league_name_raw: str
    kickoff: datetime
    home: str
    away: str
    source: str
    fetched_at: str
    code: str | None = None
    mbs: int | None = None
    odds: dict[str, float] = field(default_factory=dict)
    status: str = "scheduled"
    result: dict | None = None   # {"ft":[h,a], "ht":[h,a]}
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Prediction:
    source: str
    home: str
    away: str
    date: str                     # YYYY-MM-DD
    fetched_at: str
    picks: dict[str, str] = field(default_factory=dict)   # {"1X2":"1","OU25":"O2.5","BTTS":"BTTS_Y"}
    probs: dict[str, float] = field(default_factory=dict)
    note: str | None = None


@dataclass
class MissingPlayer:
    name: str
    reason: str   # sakat | cezalı | şüpheli
    key: bool = False


@dataclass
class TeamNews:
    team: str
    source: str
    fetched_at: str
    missing: list[MissingPlayer] = field(default_factory=list)
    coach_change: bool = False


@dataclass
class SourceStatus:
    id: str
    name: str
    status: str = "missing"      # ok | partial | missing | skipped
    fetched_at: str | None = None
    note: str | None = None
    items: int = 0


class StatusBoard:
    def __init__(self):
        self.items: dict[str, SourceStatus] = {}

    def run(self, sid: str, name: str, fn: Callable[[], Any], *, empty_is_partial: bool = True,
            count: Callable[[Any], int] = lambda x: len(x) if hasattr(x, "__len__") else 1):
        """Kaynağı çalıştırır; hata olursa pipeline'ı durdurmaz, 'missing' işaretler."""
        st = SourceStatus(sid, name)
        self.items[sid] = st
        try:
            out = fn()
            st.fetched_at = now_iso()
            st.items = count(out) if out is not None else 0
            if st.items == 0:
                st.status = "partial" if empty_is_partial else "ok"
                st.note = st.note or "Veri dönmedi (sayfa yapısı değişmiş veya bugün maç yok olabilir)"
            else:
                st.status = "ok"
            return out
        except Exception as e:  # noqa: BLE001 — bilinçli: tek kaynak tüm akışı durdurmamalı
            st.status = "missing"
            st.fetched_at = now_iso()
            st.note = f"{type(e).__name__}: {str(e)[:180]}"
            log.warning("Kaynak %s başarısız: %s\n%s", sid, e, traceback.format_exc(limit=3))
            return None

    def skip(self, sid: str, name: str, note: str):
        self.items[sid] = SourceStatus(sid, name, "skipped", now_iso(), note)

    def note(self, sid: str, text: str):
        if sid in self.items:
            self.items[sid].note = text

    def as_list(self):
        return [asdict(s) for s in self.items.values()]

    def ok(self, sid: str) -> bool:
        s = self.items.get(sid)
        return bool(s and s.status in ("ok", "partial") and s.items > 0)
