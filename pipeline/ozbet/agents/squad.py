"""Kadro & Haber Ajanı: sakat/cezalı listesi, rotasyon riski (Avrupa maçına sıkışma), TD değişikliği.

λ düzeltmesi (ayrıntı ve gerekçe: docs/research/kadro-etkisi.md):
  - Kilit saha oyuncusu eksiği: kendi gol beklentisi −%3, rakibinki +%1,5 (oyuncu başına).
  - Diğer eksik: −%0,75 / +%0,375.   Şüpheli: yarım ağırlık.   Rotasyon riski: −%1,5 / +%0,75.
  - Eskilik indirimi: yokluk ≤7 gün ×1,0 · 8–21 gün ×0,6 · >21 gün ×0,25 (sonuçlara ve oranlara zaten yansımış)
    · tarihi bilinmiyorsa ×0,5.
  - Sert tavan: kendi λ en çok −%6, rakip λ en çok +%3 (rotasyon dahil).
  - TD değişikliği ve haber başlıkları λ'yı DEĞİŞTİRMEZ (yön/büyüklük bilinmiyor); yalnız `signal` alanına girer.

`adjustment` alanının anlamı değişmedi: kendi λ'sına uygulanan oransal değişim (≤ 0). Yeni `opp_adjustment`
rakibin λ'sına uygulanan oransal değişimdir (≥ 0).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .. import config
from ..teams import _ascii, team_key

# ---- büyüklükler (oransal; 0.03 = %3) ----
W_KEY = 0.03
W_OTHER = 0.0075
W_ROTATION = 0.015
OPP_RATIO = 0.5            # rakip λ artışı = kendi λ azalışının yarısı
DOUBT_FACTOR = 0.5         # "şüpheli" oyuncu
CAP_OWN = 0.06             # kendi λ'sında toplam azalış tavanı
CAP_OPP = 0.03             # rakip λ'sında toplam artış tavanı
RECENT_DAYS = 7
STALE_DAYS = 21
F_RECENT, F_MID, F_STALE, F_UNKNOWN = 1.0, 0.6, 0.25, 0.5

FRESH_H = 24               # "taze" haber/yokluk penceresi (saat)
SIGNAL_TAGS = ("sakat", "ceza", "kadro", "td")
STRENGTHS = ("yok", "zayıf", "orta", "güçlü")
# Aynı yayın grubunun siteleri birbirinin haberini kopyalar: bağımsız doğrulama sayılmaz.
SOURCE_GROUP = {"A Spor": "turkuvaz", "Fotomaç": "turkuvaz", "NTV Spor": "ntv", "BBC Sport": "bbc"}
TAG_WORD = {"sakat": "sakatlık", "ceza": "ceza", "kadro": "kadro", "td": "teknik direktör"}


def rotation_risk(team: str, kickoff, all_fixtures) -> bool:
    """Takımın ±3 gün içinde bir Avrupa kupası maçı varsa (ve bu maç kupa maçı değilse) rotasyon riski."""
    k = team_key(team)
    for f in all_fixtures:
        lg = config.LEAGUE_BY_ID.get(f.league_id or "")
        if not lg or not lg.cup:
            continue
        if k not in (team_key(f.home), team_key(f.away)):
            continue
        dt = abs(f.kickoff - kickoff)
        if timedelta(hours=12) < dt <= timedelta(days=3):
            return True
    return False


def add_coach_signals(news: dict[str, object], coach_keys: set[str], fixtures) -> int:
    """Haber akışı sinyali: son 7 günde başlığında takım geçen "td" etiketli haber → coach_change = True.
    Mevcut TeamNews varsa yalnız bayrağı açar; yoksa eksik listesi boş bir TeamNews ekler. Oyuncu adı çıkarılmaz."""
    from ..sources.base import TeamNews, now_iso
    names = {}
    for f in fixtures:
        names.setdefault(team_key(f.home), f.home)
        names.setdefault(team_key(f.away), f.away)
    n = 0
    for k in coach_keys:
        cur = news.get(k)
        if cur is not None:
            cur.coach_change = True
        elif k in names:
            news[k] = TeamNews(names[k], "haber_rss", now_iso(), coach_change=True)
        else:
            continue
        n += 1
    return n


# ---------------- oyuncu tekilleştirme ----------------
def _name_tokens(name: str) -> list[str]:
    return re.sub(r"[^a-z ]+", " ", _ascii(name)).split()


def same_player(a: str, b: str) -> bool:
    """'V. Osimhen' = 'Victor Osimhen' = 'Osimhen'. Soyad aynı olmalı; ön ad varsa baş harfi çelişmemeli."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    if ta[-1] != tb[-1]:
        return False
    if len(ta) == 1 or len(tb) == 1:
        return True
    return ta[0][0] == tb[0][0] and (len(ta[0]) == 1 or len(tb[0]) == 1 or ta[0] == tb[0])


def dedupe_missing(players: list[dict]) -> list[dict]:
    """Aynı oyuncu iki kez (iki kaynak / iki yazım) sayılmaz. Birleşen kayıtta kilit bayrağı VE en eski başlangıç
    tarihi korunur; 'şüpheli' kesin bir nedenle (sakat/cezalı) çakışırsa kesin olan kalır."""
    out: list[dict] = []
    for p in players:
        cur = next((q for q in out if same_player(q["name"], p["name"])), None)
        if cur is None:
            out.append(dict(p))
            continue
        cur["key"] = bool(cur.get("key") or p.get("key"))
        if cur.get("reason") == "şüpheli" and p.get("reason") != "şüpheli":
            cur["reason"] = p.get("reason")
        if len(p["name"]) > len(cur["name"]):
            cur["name"] = p["name"]
        ds = [d for d in (cur.get("since"), p.get("since")) if d]
        if ds:
            cur["since"] = min(ds)
    return out


def merge_team_news(*sources: dict) -> dict:
    """Birden çok kaynağın {team_key: TeamNews} sözlüğünü birleştirir: eksik listeleri birleşir (build() aynı
    oyuncuyu tekilleştirir), ilk kaynak adı korunur. run.py şu an 'ilk kaynak kazanır' kullanıyor; bu yardımcı
    iki kaynak aynı takımı verdiğinde çifte sayım olmadan birleştirmek içindir."""
    out: dict = {}
    for src in sources:
        for k, v in (src or {}).items():
            cur = out.get(k)
            if cur is None:
                out[k] = v
                continue
            cur.missing = list(cur.missing) + list(v.missing)
            cur.coach_change = bool(cur.coach_change or v.coach_change)
    return out


# ---------------- λ etkisi ----------------
def stale_factor(days_out: int | None) -> float:
    """Yokluğun yaşı → ağırlık. Uzun süredir yok olan oyuncunun etkisi son maç sonuçlarında ve oranda zaten var."""
    if days_out is None:
        return F_UNKNOWN
    if days_out <= RECENT_DAYS:
        return F_RECENT
    if days_out <= STALE_DAYS:
        return F_MID
    return F_STALE


def impact(side: dict | None) -> tuple[float, float]:
    """(kendi λ oransal değişimi ≤ 0, rakip λ oransal değişimi ≥ 0) — tavanlı."""
    if not side:
        return 0.0, 0.0
    total = 0.0
    for p in dedupe_missing(side.get("missing") or []):
        w = W_KEY if p.get("key") else W_OTHER
        if p.get("reason") == "şüpheli":
            w *= DOUBT_FACTOR
        total += w * stale_factor(p.get("days_out"))
    if side.get("rotation_risk"):
        total += W_ROTATION
    own = min(total, CAP_OWN)
    opp = min(total * OPP_RATIO, CAP_OPP)
    return -round(own, 4), round(opp, 4)


def multipliers(side: dict | None) -> tuple[float, float, list[str]]:
    """(kendi λ çarpanı, rakip λ çarpanı, notlar) — simulation._squad_mult ile aynı imza.
    build() çıktısında hazır `adjustment`/`opp_adjustment` varsa onları kullanır; yoksa listeden hesaplar."""
    if not side:
        return 1.0, 1.0, []
    if isinstance(side.get("adjustment"), (int, float)) and isinstance(side.get("opp_adjustment"), (int, float)):
        own = max(-CAP_OWN, min(0.0, float(side["adjustment"])))
        opp = max(0.0, min(CAP_OPP, float(side["opp_adjustment"])))
    else:
        own, opp = impact(side)
    notes = []
    if side.get("rotation_risk"):
        notes.append("rotasyon riski")
    if side.get("coach_change"):
        notes.append("teknik direktör değişikliği")
    return 1.0 + own, 1.0 + opp, notes


# ---------------- sinyal ----------------
def _rank(s: str) -> int:
    return STRENGTHS.index(s)


def _parse_dt(s) -> datetime | None:
    if isinstance(s, datetime):
        return s
    try:
        dt = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=config.TZ)


def _stories(items: list[dict], ref: datetime, kickoff: datetime) -> list[dict]:
    """Kadro etiketli, maç ÖNCESİ yayımlanmış haberleri 'hikâye'lere toplar (aynı haberin kopyaları tek hikâye).
    Hikâye: {"tags", "first" (ilk görülme), "groups" (bağımsız kaynak grupları)}."""
    from ..sources.news_rss import same_story
    out: list[dict] = []
    for it in items or []:
        tags = [t for t in (it.get("tags") or []) if t in SIGNAL_TAGS]
        pub = _parse_dt(it.get("published"))
        if not tags or pub is None or pub > kickoff or pub > ref + timedelta(hours=1):
            continue      # maç başladıktan sonraki haber (canlı anlatım, maçta görülen kart) maç öncesi bilgi değildir
        grp = SOURCE_GROUP.get(it.get("source") or "", it.get("source") or "?")
        cur = next((s for s in out if set(tags) & set(s["tags"]) and any(same_story(it["title"], t) for t in s["titles"])), None)
        if cur is None:
            out.append({"tags": list(tags), "first": pub, "groups": {grp}, "titles": [it.get("title") or ""]})
        else:
            cur["first"] = min(cur["first"], pub)
            cur["groups"].add(grp)
            cur["titles"].append(it.get("title") or "")
    return out


def side_signal(team: str, side: dict | None, items: list[dict], ref: datetime, kickoff: datetime) -> dict:
    """Tek taraf için {"strength","fresh","text"}."""
    stories = _stories(items, ref, kickoff)
    fresh_cut = ref - timedelta(hours=FRESH_H)
    fresh = [s for s in stories if s["first"] >= fresh_cut]
    old = [s for s in stories if s["first"] < fresh_cut]
    missing = (side or {}).get("missing") or []
    keys = [p for p in missing if p.get("key") and (p.get("days_out") is None or p["days_out"] <= STALE_DAYS)]
    fresh_abs = [p for p in missing if p.get("days_out") is not None and p["days_out"] <= 1]
    fresh_key = [p for p in fresh_abs if p.get("key")]
    confirmed = len(set().union(*(s["groups"] for s in fresh))) >= 2 if fresh else False   # ≥2 bağımsız kaynak

    parts: list[str] = []
    strength = "yok"
    if fresh_key or confirmed:
        strength = "güçlü"
    elif fresh or keys or fresh_abs or (side or {}).get("coach_change"):
        strength = "orta"
    elif old or missing or (side or {}).get("rotation_risk"):
        strength = "zayıf"

    if fresh_key:
        parts.append("yeni kilit eksik: " + ", ".join(p["name"] for p in fresh_key[:2]))
    elif keys:
        parts.append("kilit eksik: " + ", ".join(p["name"] for p in keys[:2]))
    if fresh:
        tags = [t for t in SIGNAL_TAGS if any(t in s["tags"] for s in fresh)]
        ngrp = len(set().union(*(s["groups"] for s in fresh)))
        parts.append(f"son {FRESH_H} saatte {len(fresh)} {'/'.join(TAG_WORD[t] for t in tags)} haberi"
                     f" ({ngrp} bağımsız kaynak)")
    elif old:
        parts.append(f"{FRESH_H} saatten eski {len(old)} kadro haberi")
    if (side or {}).get("coach_change") and not any("td" in s["tags"] for s in fresh):
        parts.append("teknik direktör değişikliği")
    if (side or {}).get("rotation_risk"):
        parts.append("rotasyon riski")
    if not parts and missing:
        parts.append(f"{len(missing)} eksik (uzun süreli ya da tarihi bilinmiyor)")
    return {"strength": strength, "fresh": bool(fresh or fresh_abs),
            "text": f"{team}: {', '.join(parts)}" if parts else ""}


def build_signal(home: str, away: str, kickoff: datetime, sides: dict, news_block: dict | None,
                 now: datetime | None = None) -> dict:
    """Maç için özet kadro sinyali:
    {"strength": "yok|zayıf|orta|güçlü", "fresh": bool, "side": "home|away|None", "text": kısa Türkçe cümle}.
    Haber başlığı yokluğu DOĞRULAMAZ (oyuncu adı/yönü çıkarılmaz); metin bu yüzden "haber" der, "eksik" demez."""
    now = now or datetime.now(config.TZ)
    ref = min(now, kickoff) if kickoff else now      # maç başladıysa tazelik başlama saatine göre ölçülür
    res = {}
    for sd, team in (("home", home), ("away", away)):
        res[sd] = side_signal(team, sides.get(sd), (news_block or {}).get(sd) or [], ref, kickoff or now)
    rh, ra = _rank(res["home"]["strength"]), _rank(res["away"]["strength"])
    if rh == ra == 0:
        return {"strength": "yok", "fresh": False, "side": None, "text": "Güncel kadro haberi yok."}
    if rh == ra:
        side, strength = None, res["home"]["strength"]
        fresh = res["home"]["fresh"] or res["away"]["fresh"]
        text = "; ".join(t for t in (res["home"]["text"], res["away"]["text"]) if t)
    else:
        side = "home" if rh > ra else "away"
        strength, fresh, text = res[side]["strength"], res[side]["fresh"], res[side]["text"]
    if fresh:
        text += " — taze haber, oranlara henüz yansımamış olabilir"
    return {"strength": strength, "fresh": bool(fresh), "side": side, "text": text + "."}


# ---------------- ana giriş ----------------
def _missing_rows(n, ref: date) -> list[dict]:
    rows = []
    for p in getattr(n, "missing", []) or []:
        row = {"name": p.name, "reason": p.reason, "key": bool(p.key)}
        since = getattr(p, "since", None)
        if isinstance(since, date):
            row["since"] = since
        rows.append(row)
    rows = dedupe_missing(rows)
    for row in rows:
        since = row.pop("since", None)
        if since is not None:
            row["since"] = since.isoformat()
            row["days_out"] = max(0, (ref - since).days)
    return rows


def build(home: str, away: str, kickoff, league_id, news: dict[str, object], all_fixtures,
          rss: dict | None = None, now: datetime | None = None) -> dict | None:
    """news: team_key → TeamNews.  rss: news_rss.collect() çıktısı (verilmezse son collect() sonucu kullanılır).
    Dönüş None ise kadro bilgisi de sinyal de yoktur (sinyal "yok" sayılır)."""
    lg = config.LEAGUE_BY_ID.get(league_id or "")
    out, src, t = {}, None, None
    ref_day = kickoff.date() if isinstance(kickoff, datetime) else date.today()
    for side, team in (("home", home), ("away", away)):
        n = news.get(team_key(team))
        rot = False if (lg and lg.cup) else rotation_risk(team, kickoff, all_fixtures)
        if n is None and not rot:
            out[side] = None
            continue
        out[side] = {"missing": _missing_rows(n, ref_day), "rotation_risk": rot,
                     "coach_change": bool(getattr(n, "coach_change", False))}
        if n is not None and (src is None or n.missing):   # eksik listesi veren kaynak önceliklidir
            src, t = n.source, n.fetched_at
    for side in ("home", "away"):
        if out.get(side):
            own, opp = impact(out[side])
            out[side]["adjustment"] = own          # kendi λ'sına uygulanan oransal değişim (≤ 0)
            out[side]["opp_adjustment"] = opp      # rakibin λ'sına uygulanan oransal değişim (≥ 0)
    # sinyal: RSS haber başlıkları + eksik listesi
    from ..sources import news_rss
    if rss is None:
        rss = news_rss.LAST
    try:
        blk = news_rss.for_match(home, away, rss) if rss else None
    except Exception:  # noqa: BLE001 — sinyal hiçbir zaman akışı durdurmaz
        blk = None
    signal = build_signal(home, away, kickoff, out, blk, now)
    if not out.get("home") and not out.get("away"):
        if signal["strength"] == "yok":
            return None
        src, t = "haber_rss", (rss or {}).get("fetched_at")
    out["source"], out["fetched_at"] = src, t
    out["signal"] = signal
    return out
