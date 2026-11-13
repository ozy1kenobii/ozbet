"""Lig profili ve veri kademesi (A/B/C).

İki soruya cevap verir:
1. Bu lig yapısal olarak nasıl? (maç başı gol, beraberlik oranı, iç saha avantajı, KG, 2.5 Üst)
   → `league_profile`, `draw_prior`, `goals_prior`
2. Bu ligdeki bir tahmine ne kadar veri dayanıyor? → `league_tier`, `tier_reason`

Veri: yalnız `data/archive/results-{LIG}.json` (birikimli sonuç arşivi). Dosyalar ilk çağrıda TEMBEL okunur ve
süreç boyunca önbellekte kalır; import sırasında dosya okunmaz. Dosya/dizin yoksa ya da bozuksa hata vermez:
profil None, kademe yalnız config'e göre belirlenir.

Büzme (shrinkage): her gözlem, örneklem büyüklüğüne göre havuz öncülüne çekilir:

    değer = (n · gözlem + K · öncül) / (n + K)

- Oranlar (beraberlik, ev/deplasman galibiyeti, KG, 2.5 Üst) ve iç saha gol farkı: K = PRIOR_K_RATE = 200 maç.
  Gerekçe: K ≈ p(1-p)/τ²; p ≈ 0,26 ve ligler arası standart sapma τ ≈ 0,03 için ≈ 210.
- Maç başı gol: K = PRIOR_K_GOALS = 60 maç (maç başı gol varyansı ≈ 2,7, ligler arası τ ≈ 0,2 → ≈ 68).
Yani 10 maçlık bir ligde beraberlik oranının yalnız ~%5'i ligin kendi verisidir; 200 maçta yarısı, 800 maçta %80'i.

Havuz öncülü: sabit taban (BASE_PRIOR: Avrupa liglerinin uzun dönem YAKLAŞIK ortalamaları) + tüm arşiv satırları,
taban POOL_K = 500 maç ağırlığında. Arşiv küçükken öncül tabana yakındır, arşiv büyüdükçe kendi verisine kayar.

Kademe kuralı (`league_tier`), sırayla:
  C  ← kimlik boş / "OTHER" / kupa (config `cup=True`: UCL, UEL, UECL)
  A  ← config'te football-data.co.uk ANA lig dosyası olan lig (`fd_code`: 3 sezon, İY skoru, şut verisi)
       VEYA arşivde ≥ TIER_A_MIN_MATCHES (300) maç
  B  ← config'te tanımlı diğer lig (`fd_extra` "new leagues" dosyası: şut/İY yok; ya da TR2 gibi yalnız soccerstats)
       VEYA arşivde ≥ config.ARCHIVE_MIN_MATCHES (60) maç
  C  ← geri kalan her şey (hiçbir dosyada olmayan kimlikler, kadın/altyapı ligleri, eşlenemeyen bülten ligleri)
Kademe bir VERİ YETERLİLİĞİ etiketidir, kârlılık iddiası değildir (bkz. docs/research/lig-profili.md).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from . import config

# Büzme güçleri (sözde maç sayısı)
PRIOR_K_RATE = 200.0
PRIOR_K_GOALS = 60.0
POOL_K = 500.0
TIER_A_MIN_MATCHES = 300

# Sabit taban: Avrupa liglerinin uzun dönem yaklaşık ortalamaları (kesin ölçüm değil, başlangıç noktası).
BASE_PRIOR = {
    "goals_avg": 2.70,
    "draw_rate": 0.26,
    "home_win_rate": 0.44,
    "away_win_rate": 0.30,
    "btts_rate": 0.52,
    "o25_rate": 0.52,
    "home_adv": 0.30,
}
_METRICS = tuple(BASE_PRIOR)

_lock = threading.Lock()
_cache: dict[str, dict] = {}      # arşiv dizini → {"leagues": {lig: ham toplamlar}, "pool": {...}}
_load_count = 0                   # test/teşhis: diskten kaç kez yüklendi


def default_archive_dir() -> Path:
    """Depo köküne göre data/archive (bu dosyanın konumundan çözülür; çalışma dizininden bağımsız)."""
    return Path(__file__).resolve().parents[2] / "data" / "archive"


def clear_cache() -> None:
    """Önbelleği boşaltır (testler ve arşiv aynı süreçte güncellendiğinde)."""
    with _lock:
        _cache.clear()


def _score(row) -> tuple[int, int] | None:
    try:
        ft = row["ft"]
        h, a = int(ft[0]), int(ft[1])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return (h, a) if h >= 0 and a >= 0 else None


def _raw(rows) -> dict:
    """Satırlardan ham toplamlar. Bozuk satır ve aynı (tarih, ev, deplasman) tekrarları atlanır."""
    t = {"n": 0, "goals": 0, "draws": 0, "home": 0, "away": 0, "btts": 0, "o25": 0, "gd": 0, "updated": None}
    seen = set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        sc = _score(r)
        if sc is None:
            continue
        key = (r.get("date"), r.get("home"), r.get("away"))
        if key in seen:
            continue
        seen.add(key)
        h, a = sc
        t["n"] += 1
        t["goals"] += h + a
        t["draws"] += h == a
        t["home"] += h > a
        t["away"] += h < a
        t["btts"] += h > 0 and a > 0
        t["o25"] += h + a >= 3
        t["gd"] += h - a
        d = r.get("date")
        if isinstance(d, str) and (t["updated"] is None or d > t["updated"]):
            t["updated"] = d
    return t


def _observed(t: dict) -> dict:
    n = t["n"]
    return {
        "goals_avg": t["goals"] / n, "draw_rate": t["draws"] / n, "home_win_rate": t["home"] / n,
        "away_win_rate": t["away"] / n, "btts_rate": t["btts"] / n, "o25_rate": t["o25"] / n,
        "home_adv": t["gd"] / n,
    }


def _k(metric: str) -> float:
    return PRIOR_K_GOALS if metric == "goals_avg" else PRIOR_K_RATE


def shrink(observed: float, n: float, prior: float, k: float) -> float:
    """(n·gözlem + k·öncül) / (n + k). n=0 → öncül; n → ∞ → gözlem."""
    n = max(0.0, float(n))
    if n + k <= 0:
        return prior
    return (n * observed + k * prior) / (n + k)


def _load(archive_dir: Path | str | None) -> dict:
    global _load_count
    d = Path(archive_dir) if archive_dir is not None else default_archive_dir()
    key = str(d)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            return hit
        leagues: dict[str, dict] = {}
        try:
            files = sorted(d.glob("results-*.json"))
        except OSError:
            files = []
        for p in files:
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict):
                continue
            lid = p.stem[len("results-"):]
            t = _raw(doc.get("rows"))
            if lid and t["n"] > 0:
                leagues[lid] = t
        # Havuz öncülü: sabit taban + tüm arşiv (taban POOL_K maç ağırlığında)
        n_all = sum(t["n"] for t in leagues.values())
        pool = dict(BASE_PRIOR)
        if n_all:
            tot = {k: sum(t[k] for t in leagues.values()) for k in ("goals", "draws", "home", "away", "btts", "o25", "gd")}
            obs = _observed({"n": n_all, **tot})
            pool = {m: shrink(obs[m], n_all, BASE_PRIOR[m], POOL_K) for m in _METRICS}
        out = {"leagues": leagues, "pool": pool, "pool_n": n_all}
        _cache[key] = out
        _load_count += 1
        return out


def pooled_prior(archive_dir: Path | str | None = None) -> dict:
    """Havuz öncülü (sabit taban + tüm arşiv). Kopya döner."""
    data = _load(archive_dir)
    return {**{m: round(v, 4) for m, v in data["pool"].items()}, "n": data["pool_n"]}


def archive_matches(league_id, archive_dir: Path | str | None = None) -> int:
    """Ligin arşivdeki geçerli maç sayısı (yoksa 0)."""
    if not isinstance(league_id, str):
        return 0
    t = _load(archive_dir)["leagues"].get(league_id)
    return t["n"] if t else 0


def league_profile(league_id, archive_dir: Path | str | None = None) -> dict | None:
    """Ligin büzülmüş yapısal profili; arşivde maçı yoksa None.

    {"n", "goals_avg", "draw_rate", "home_win_rate", "away_win_rate", "btts_rate", "o25_rate", "home_adv", "updated"}
    home_adv = maç başı (ev golü − deplasman golü). Üç sonuç oranı aynı K ile büzüldüğü için toplamı 1'dir.
    """
    if not isinstance(league_id, str):
        return None
    data = _load(archive_dir)
    t = data["leagues"].get(league_id)
    if not t:
        return None
    obs, pool, n = _observed(t), data["pool"], t["n"]
    out = {"n": n}
    for m in _METRICS:
        out[m] = round(shrink(obs[m], n, pool[m], _k(m)), 4)
    out["updated"] = t["updated"]
    return out


def draw_prior(league_id, archive_dir: Path | str | None = None) -> float:
    """Ligin beraberlik öncülü (büzülmüş); lig bilinmiyorsa havuz öncülü."""
    p = league_profile(league_id, archive_dir)
    return p["draw_rate"] if p else round(_load(archive_dir)["pool"]["draw_rate"], 4)


def goals_prior(league_id, archive_dir: Path | str | None = None) -> float:
    """Ligin maç başı gol öncülü (büzülmüş); lig bilinmiyorsa havuz öncülü."""
    p = league_profile(league_id, archive_dir)
    return p["goals_avg"] if p else round(_load(archive_dir)["pool"]["goals_avg"], 4)


def _tier_info(league_id, archive_dir) -> tuple[str, str]:
    """(kademe, kural kodu). Kodlar tier_reason metinlerine çevrilir."""
    if not isinstance(league_id, str) or not league_id.strip() or league_id.strip().upper() == "OTHER":
        return "C", "unknown"
    lid = league_id.strip()
    lg = config.LEAGUE_BY_ID.get(lid)
    if lg is not None and lg.cup:
        return "C", "cup"
    n = archive_matches(lid, archive_dir)
    if lg is not None and lg.fd_code:
        return "A", "fd_main"
    if n >= TIER_A_MIN_MATCHES:
        return "A", "archive_long"
    if lg is not None:
        return "B", "fd_extra" if lg.fd_extra else "config_thin"
    if n >= config.ARCHIVE_MIN_MATCHES:
        return "B", "archive_mid"
    return "C", "thin"


def league_tier(league_id, archive_dir: Path | str | None = None) -> str:
    """Veri kademesi: "A" | "B" | "C". Kural modül başlığında. Bilinmeyen her kimlik "C" döner."""
    return _tier_info(league_id, archive_dir)[0]


def tier_reason(league_id, archive_dir: Path | str | None = None) -> str:
    """Arayüz için kısa Türkçe açıklama."""
    tier, code = _tier_info(league_id, archive_dir)
    n = archive_matches(league_id, archive_dir)
    text = {
        "fd_main": "Uzun ve sık geçmiş: 3 sezonluk maç, şut ve ilk yarı verisiyle lig modeli",
        "archive_long": f"Arşivde {n} maç: lig modeli için yeterli geçmiş",
        "fd_extra": "Lig modeli var ama veri daha sığ: şut ve ilk yarı verisi yok",
        "config_thin": "Lig modeli tek ve ince bir sonuç kaynağına dayanıyor",
        "archive_mid": f"Arşivde {n} maç: kullanılabilir ama ince geçmiş",
        "cup": "Kupa / lig-arası maç: takımlar farklı liglerden, model Elo veya lig gücü yedeğiyle çalışır",
        "unknown": "Tanımsız lig: geçmiş veri yok, tahmin yalnız piyasa oranına dayanır",
        "thin": (f"Arşivde yalnız {n} maç: lig modeli için yetersiz" if n
                 else "Bu lig için geçmiş veri yok, tahmin yalnız piyasa oranına dayanır"),
    }[code]
    return f"{tier} kademe · {text}"


def all_tiers(archive_dir: Path | str | None = None) -> dict[str, str]:
    """Config'teki ve arşivdeki tüm liglerin kademesi (doküman/teşhis için)."""
    ids = list(config.LEAGUE_BY_ID) + [l for l in _load(archive_dir)["leagues"] if l not in config.LEAGUE_BY_ID]
    return {lid: league_tier(lid, archive_dir) for lid in ids}
