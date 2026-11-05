"""Nazik HTTP istemcisi: alan adı başına gecikme, disk önbelleği, robots.txt kontrolü."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config

log = logging.getLogger("ozbet.http")


class Blocked(Exception):
    """robots.txt veya sunucu tarafından engellendi."""


class PoliteClient:
    def __init__(self, cache_dir: Path | None = None, delay: float | None = None):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        })
        self.delay = config.REQUEST_DELAY_S if delay is None else delay
        self.cache_dir = cache_dir or config.CACHE_DIR / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.recent: list[tuple[str, int, str]] = []   # (url, http durum, gövde başı) — teşhis için

    # --- robots.txt ---
    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=config.REQUEST_TIMEOUT_S)
                if r.status_code >= 400:
                    self._robots[base] = None  # robots yok → izinli
                else:
                    rp.parse(r.text.splitlines())
                    self._robots[base] = rp
            except requests.RequestException:
                self._robots[base] = None
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(config.USER_AGENT, url)

    def _wait(self, host: str):
        last = self._last.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.delay:
                time.sleep(self.delay - gap)
        self._last[host] = time.monotonic()

    def _cache_path(self, url: str, params) -> Path:
        key = url + "?" + json.dumps(params or {}, sort_keys=True)
        return self.cache_dir / hashlib.sha1(key.encode()).hexdigest()

    def get(self, url: str, *, params=None, headers=None, ttl: float = 3600,
            check_robots: bool = True, retries: int = 2) -> str:
        cp = self._cache_path(url, params)
        if ttl > 0 and cp.exists() and time.time() - cp.stat().st_mtime < ttl:
            text = cp.read_text(encoding="utf-8", errors="replace")
            if len(text.strip()) < 20:   # eski sürümün önbelleğe yazdığı boş yanıt → yok say
                cp.unlink(missing_ok=True)
                return self.get(url, params=params, headers=headers, ttl=0, check_robots=check_robots,
                                retries=retries)
            self.recent = (self.recent + [(url + " [önbellek]", 200, text[:150_000])])[-60:]
            return text
        if check_robots and not self.allowed(url):
            raise Blocked(f"robots.txt izin vermiyor: {url}")
        host = urlparse(url).netloc
        err: Exception | None = None
        for attempt in range(retries + 1):
            self._wait(host)
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT_S)
                self.recent = (self.recent + [(r.url, r.status_code, r.text[:150_000])])[-60:]
                if r.status_code in (401, 403, 429, 451):
                    raise Blocked(f"HTTP {r.status_code}: {url}")
                r.raise_for_status()
                text = r.text
                if ttl > 0 and len(text.strip()) >= 20:   # "0" gibi boş/hata yanıtları önbelleğe girmesin
                    cp.write_text(text, encoding="utf-8")
                return text
            except Blocked:
                raise
            except requests.RequestException as e:
                err = e
                time.sleep(2 * (attempt + 1))
        raise err  # type: ignore[misc]

    def get_json(self, url: str, **kw):
        return json.loads(self.get(url, **kw))
