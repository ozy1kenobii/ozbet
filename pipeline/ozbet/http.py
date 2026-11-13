"""Nazik HTTP istemcisi: alan adı başına gecikme, disk önbelleği, robots.txt kontrolü.

Dayanıklılık (kaynak onarımı, bkz. docs/research/kaynak-onarimi.md):
  * Geçici hatalar (bağlantı, zaman aşımı, 5xx, 408) üstel geri çekilmeyle yeniden denenir; `Retry-After` dikkate
    alınır. Kalıcı hatalar (404 vb.) ve engeller (401/403/429/451, bot doğrulama sayfası) yeniden DENENMEZ.
  * `validate`: yanıt içerik denetimi. 200 dönen bakım/doğrulama sayfaları önbelleğe yazılmaz; daha önce yazılmış
    bozuk kopya da atılır (Understat bakım sayfası 30 gün önbellekte kalıyordu).
  * `stale`: istek başarısız olursa en çok bu kadar saniye eski son iyi kopya döner ve `STALE`'e işlenir
    (dünkü Elo, birkaç günlük xG kabul edilebilir). Bayat kopya hiçbir zaman sessizce kullanılmaz.
  * Engel hafızası: bir alan adı aynı çalıştırmada üst üste 2 kez engellerse o çalıştırmada bir daha istek
    atılmaz; bu durum 3 çalıştırma tekrarlarsa alan adı 6 saatten başlayıp 72 saate kadar katlanan süreyle
    dinlendirilir. Engel AŞILMAZ; yalnızca boşuna istek atılmaz.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
import urllib.robotparser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests

from . import config

log = logging.getLogger("ozbet.http")

BACKOFF_BASE_S = 2.0        # 2 sn, 4 sn, 8 sn ... (+ %25'e kadar rastgele pay)
BACKOFF_MAX_S = 30.0
BLOCK_RUN_LIMIT = 2         # aynı çalıştırmada üst üste bu kadar engel → o alan adına istek kesilir
BLOCK_STRIKES = 3           # bu kadar çalıştırma üst üste engel → çalıştırmalar arası dinlendirme başlar
BLOCK_COOLDOWN_S = 6 * 3600
BLOCK_COOLDOWN_MAX_S = 72 * 3600

# Bu süreçte bayat (süresi geçmiş) önbellek kopyasıyla karşılanan istekler: {alan adı: yaş (saat)}.
# health.py çalıştırma özetine yazar; böylece "veri var ama eski" durumu görünür olur.
STALE: dict[str, float] = {}


class Blocked(Exception):
    """robots.txt veya sunucu tarafından engellendi."""


class BadContent(Exception):
    """HTTP 200 döndü ama içerik beklenen veri değil (bakım sayfası, boş gövde...)."""


def block_reason(status: int, body: str) -> str | None:
    """Yanıt bir engel/bot doğrulaması ise insanın anlayacağı gerekçe, değilse None."""
    head = (body or "")[:6000].lower()
    if "just a moment" in head and "challenge" in head:
        return f"HTTP {status}: Cloudflare bot doğrulama sayfası (aşılmaz)"
    if "you have been blocked" in head or "attention required" in head:
        return f"HTTP {status}: Cloudflare güvenlik duvarı bu istemciyi engelliyor"
    if status in (401, 403, 429, 451):
        return f"HTTP {status}"
    if status == 202 and not (body or "").strip():
        return "HTTP 202 boş gövde: bot doğrulaması (WAF) bekleniyor"
    return None


def _retry_after(resp) -> float | None:
    try:
        return max(0.0, float(resp.headers.get("Retry-After", "")))
    except (TypeError, ValueError, AttributeError):
        return None


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
        self.stale: dict[str, float] = {}              # {url: yaş (sn)} — bu istemcinin bayat kopyayla dönen istekleri
        self._blocks: dict[str, int] = {}              # alan adı → bu çalıştırmada üst üste engel sayısı
        self._block_file = self.cache_dir / "_engeller.json"

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

    # --- önbellek ---
    def cached(self, url: str, *, params=None, max_age: float,
               validate: Callable[[str], bool] | None = None) -> tuple[str, float] | None:
        """Ağa çıkmadan önbellekteki kopya: (metin, yaş sn) veya None. Boş/geçersiz kopya yok sayılır."""
        cp = self._cache_path(url, params)
        try:
            age = time.time() - cp.stat().st_mtime
            if age > max_age:
                return None
            text = cp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if len(text.strip()) < 20 or (validate and not _valid(validate, text)):
            return None
        return text, max(0.0, age)

    def _stale(self, url: str, params, stale: float, validate, why: Exception) -> str | None:
        got = self.cached(url, params=params, max_age=stale, validate=validate) if stale > 0 else None
        if not got:
            return None
        text, age = got
        host = urlparse(url).netloc
        self.stale[url] = age
        STALE[host] = round(max(STALE.get(host, 0.0), age / 3600), 1)
        log.warning("%s alınamadı (%s); %.1f saat önceki önbellek kopyası kullanılıyor", url, why, age / 3600)
        self.recent = (self.recent + [(url + " [bayat önbellek]", 200, text[:150_000])])[-60:]
        return text

    # --- engel hafızası ---
    def _load_blocks(self) -> dict:
        try:
            d = json.loads(self._block_file.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_blocks(self, d: dict):
        try:
            self._block_file.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def block_wait(self, host: str) -> float:
        """Alan adı dinlendiriliyorsa kalan saniye, değilse 0."""
        rec = self._load_blocks().get(host)
        if not rec or rec.get("n", 0) < BLOCK_STRIKES:
            return 0.0
        cool = min(BLOCK_COOLDOWN_S * 2 ** (rec["n"] - BLOCK_STRIKES), BLOCK_COOLDOWN_MAX_S)
        return max(0.0, rec.get("t", 0) + cool - time.time())

    def _note_block(self, host: str, reason: str):
        self._blocks[host] = self._blocks.get(host, 0) + 1
        if self._blocks[host] == BLOCK_RUN_LIMIT:      # çalıştırma başına en çok bir "vuruş"
            d = self._load_blocks()
            rec = d.get(host) or {"n": 0}
            d[host] = {"n": rec.get("n", 0) + 1, "t": time.time(), "reason": reason[:120]}
            self._save_blocks(d)

    def _note_ok(self, host: str):
        if self._blocks.pop(host, None) is not None or self._block_file.exists():
            d = self._load_blocks()
            if host in d:
                del d[host]
                self._save_blocks(d)

    def _check_block(self, host: str, url: str):
        if self._blocks.get(host, 0) >= BLOCK_RUN_LIMIT:
            raise Blocked(f"{host} bu çalıştırmada {BLOCK_RUN_LIMIT} kez engelledi; yeni istek atılmıyor: {url}")
        left = self.block_wait(host)
        if left > 0:
            rec = self._load_blocks()[host]
            raise Blocked(f"{host} {rec['n']} çalıştırmadır engelliyor ({rec.get('reason', '')}); "
                          f"{left / 3600:.0f} saat sonra yeniden denenecek: {url}")

    # --- istek ---
    def get(self, url: str, *, params=None, headers=None, ttl: float = 3600,
            check_robots: bool = True, retries: int = 2, stale: float = 0,
            validate: Callable[[str], bool] | None = None) -> str:
        """ttl: taze önbellek süresi (sn). stale: istek başarısız olursa kabul edilen en eski kopya yaşı (sn).
        validate: içerik denetimi; False/istisna → BadContent (önbelleğe yazılmaz)."""
        cp = self._cache_path(url, params)
        if ttl > 0 and cp.exists() and time.time() - cp.stat().st_mtime < ttl:
            text = cp.read_text(encoding="utf-8", errors="replace")
            if len(text.strip()) < 20 or (validate and not _valid(validate, text)):
                # eski sürümün önbelleğe yazdığı boş yanıt / bakım sayfası → at, yeniden iste
                cp.unlink(missing_ok=True)
                return self._fetch(url, cp, params, headers, ttl, check_robots, retries, 0, validate)
            self.recent = (self.recent + [(url + " [önbellek]", 200, text[:150_000])])[-60:]
            return text
        return self._fetch(url, cp, params, headers, ttl, check_robots, retries, stale, validate)

    def _fetch(self, url, cp, params, headers, ttl, check_robots, retries, stale, validate) -> str:
        try:
            return self._network(url, cp, params, headers, ttl, check_robots, retries, validate)
        except Exception as e:  # noqa: BLE001 — bayat kopya varsa onunla devam, yoksa aynı hata
            text = self._stale(url, params, stale, validate, e)
            if text is None:
                raise
            return text

    def _network(self, url, cp, params, headers, ttl, check_robots, retries, validate) -> str:
        host = urlparse(url).netloc
        self._check_block(host, url)
        if check_robots and not self.allowed(url):
            raise Blocked(f"robots.txt izin vermiyor: {url}")
        err: Exception | None = None
        for attempt in range(retries + 1):
            self._wait(host)
            wait = None
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT_S)
                self.recent = (self.recent + [(r.url, r.status_code, r.text[:150_000])])[-60:]
                why = block_reason(r.status_code, r.text)
                if why:
                    self._note_block(host, why)
                    raise Blocked(f"{why}: {url}")
                if r.status_code < 500 and r.status_code != 408:
                    r.raise_for_status()               # 404/410 vb.: kalıcı, yeniden deneme yok
                    text = r.text
                    if validate and not _valid(validate, text):
                        raise BadContent(f"beklenen içerik gelmedi (HTTP {r.status_code}, {len(text)} bayt): {url}")
                    self._note_ok(host)
                    if ttl > 0 and len(text.strip()) >= 20:   # "0" gibi boş/hata yanıtları önbelleğe girmesin
                        cp.write_text(text, encoding="utf-8")
                    return text
                wait = _retry_after(r)
                r.raise_for_status()
            except (Blocked, BadContent):
                raise
            except requests.RequestException as e:
                resp = getattr(e, "response", None)
                code = getattr(resp, "status_code", None)
                if code is not None and code < 500 and code != 408:
                    raise
                err = e
            if attempt < retries:
                back = min(BACKOFF_BASE_S * 2 ** attempt, BACKOFF_MAX_S)
                back = min(wait, BACKOFF_MAX_S) if wait is not None else back * (1 + random.random() / 4)
                log.info("%s geçici hata (%s); %.1f sn sonra yeniden (%d/%d)", url, err, back, attempt + 1, retries)
                time.sleep(back)
        raise err  # type: ignore[misc]

    def get_json(self, url: str, **kw):
        return json.loads(self.get(url, **kw))


def _valid(validate: Callable[[str], bool], text: str) -> bool:
    try:
        return bool(validate(text))
    except Exception:  # noqa: BLE001 — denetleyicinin kendi hatası "geçersiz içerik" sayılır
        return False
