"""Keskin Fark Ajanı (S1 hipotezi): GERÇEK iddaa oranı × keskin piyasanın adil olasılığı − 1.

docs/research/roi-piyasa.md, canlıda sınanabilecek tek hipotezi şöyle bıraktı: iddaa'nın fiyatı keskin uluslararası
piyasadan saparsa (iddaa_oranı × adil_olasılık > 1) o seçimde beklenen değer pozitif OLABİLİR. Backtest bunu
sınayamadı (iddaa oranı Pinnacle'dan benzetilmişti). Bu ajan sinyali her çalıştırmada KAYDEDER ki ileride gerçek
sonuçlarla puanlanabilsin; kanıtlanmış bir kazanç iddiası DEĞİLDİR (bkz. docs/research/keskin-fark.md).

Keskin referans: football-data.co.uk fixtures.csv bahisçi kolonları (Fixture.extra["books"]).
Öncelik: Pinnacle (PS) > Betfair borsası (BFE, komisyon payı düşülür) > piyasa ortalaması (Avg).
Marj temizleme: agents.market.shin (tekrar yazılmadı).

Maça eklenen blok (veri yoksa anahtar hiç eklenmez):
    m["sharp"] = {"source": "pinnacle"|"betfair"|"avg", "fair": {k: p}, "edge": {k: e},
                  "best": {"market", "edge", "odds", "fair_p"} | None, "fetched_at": "...",
                  "allowance": 0.02,            # yalnız > 0 ise: edge'den düşülen güvenlik payı
                  "source_ou25": "avg",         # yalnız Alt/Üst referansı 1X2'ninkinden farklıysa
                  "notes": ["..."]}             # yalnız not varsa (ör. olağan dışı fark)
`edge` karşılaştırılan HER marketi içerir (negatifler dahil) → S1 sonradan eksiksiz puanlanabilir.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .. import config
from ..sources.base import Fixture, SourceStatus, now_iso
from ..teams import similar, team_key
from .market import shin

FLAG = "Keskin piyasa farkı"
MIN_EDGE = 0.01        # güvenlik tamponu: bunun altındaki fark gürültü sayılır
MIN_ODDS = 1.60        # düşük oranlı "garanti" maç kovalanmaz
MAX_EDGE = 0.15        # bundan büyük fark gerçek fırsat değil, büyük olasılıkla yanlış eşleşme / bayat oran
MAX_KICKOFF_DIFF = timedelta(minutes=90)   # iki kaynağın başlama saati en çok bu kadar ayrışabilir
# (kaynak adı, books anahtarı, edge'den düşülen pay). Betfair: borsa komisyonu + yalnız "back" fiyatı görülüyor.
# Avg: yumuşak bahisçilerin ortalaması, keskin değil → aynı ihtiyat payı.
REFERENCES = (("pinnacle", "PS", 0.0), ("betfair", "BFE", 0.02), ("avg", "Avg", 0.02))
GROUPS = {"1x2": ("1", "X", "2"), "ou25": ("O2.5", "U2.5")}
# Referans oranların makul toplam ima olasılığı; dışındaysa satır bozuk/eksik sayılır
MIN_BOOK_SUM, MAX_BOOK_SUM = 0.97, 1.15
IDDAA_SOURCES = {"nesine", "iddaa.com", "iddaa"}

IMPLAUSIBLE = "Keskin fark olağan dışı büyük (> %{:.0f}): yanlış eşleşme ya da bayat oran olabilir, sinyal verilmedi"


def find_fixture(kickoff: datetime, home: str, away: str, fd_fixtures: list[Fixture] | None) -> Fixture | None:
    """fixtures.csv satırını güvenle eşler: iki takım adı da benzer + başlama saati yakın + TEK aday.
    Saat kolonu okunamadıysa (12:00 varsayımı) yalnız aynı gün ve birebir takım anahtarı kabul edilir."""
    hits = []
    for f in fd_fixtures or []:
        if not (f.extra or {}).get("books"):
            continue
        if not (similar(home, f.home) and similar(away, f.away)):
            continue
        if f.extra.get("time_known", True):
            if abs(f.kickoff - kickoff) > MAX_KICKOFF_DIFF:
                continue
        elif not (f.kickoff.date() == kickoff.date() and team_key(home) == team_key(f.home)
                  and team_key(away) == team_key(f.away)):
            continue
        hits.append(f)
    return hits[0] if len(hits) == 1 else None   # birden fazla aday = emin değiliz


def _fair_group(books: dict, keys: tuple[str, ...]):
    """Öncelik sırasına göre ilk geçerli referansın Shin adil olasılıkları → (kaynak, pay, {k: p}) ya da None."""
    for name, bk, allow in REFERENCES:
        d = books.get(bk) or {}
        odds = [d.get(k) for k in keys]
        if not all(isinstance(o, (int, float)) and o > 1.0 for o in odds):
            continue
        if not MIN_BOOK_SUM <= sum(1 / o for o in odds) <= MAX_BOOK_SUM:
            continue
        return name, allow, dict(zip(keys, shin(odds)))
    return None


def compute(iddaa_odds: dict[str, float] | None, books: dict | None, fetched_at: str | None = None) -> dict | None:
    """iddaa oranları + referans bahisçi oranları → `sharp` bloğu. Karşılaştırılacak market yoksa None."""
    if not iddaa_odds or not books:
        return None
    fair: dict[str, float] = {}
    edge: dict[str, float] = {}
    srcs: dict[str, tuple[str, float]] = {}
    for g, keys in GROUPS.items():
        # iddaa tarafında grubun tamamı gerçek orana sahip olmalı (yarım grup = şüpheli veri)
        if not all(isinstance(iddaa_odds.get(k), (int, float)) and iddaa_odds[k] > 1.0 for k in keys):
            continue
        ref = _fair_group(books, keys)
        if not ref:
            continue
        name, allow, probs = ref
        srcs[g] = (name, allow)
        for k in keys:
            fair[k] = round(probs[k], 4)
            edge[k] = round(iddaa_odds[k] * probs[k] - 1 - allow, 4)
    if not edge:
        return None
    main = srcs.get("1x2") or srcs["ou25"]
    out: dict = {"source": main[0], "fair": fair, "edge": edge, "best": None,
                 "fetched_at": fetched_at or now_iso()}
    if "1x2" in srcs and "ou25" in srcs and srcs["ou25"][0] != main[0]:
        out["source_ou25"] = srcs["ou25"][0]
    allow_max = max(a for _, a in srcs.values())
    if allow_max > 0:
        out["allowance"] = allow_max
    if max(edge.values()) > MAX_EDGE:
        # Tek bir market bile inandırıcı değilse eşleşmenin tamamına güvenilmez: hiçbir seçim öne çıkarılmaz
        out["notes"] = [IMPLAUSIBLE.format(MAX_EDGE * 100)]
        return out
    # Bant üst sınırı burada da uygulanır: bant dışı (çok yüksek oranlı) bir fark, bant içindeki farkı gölgelemesin
    cands = [k for k, e in edge.items() if e >= MIN_EDGE and MIN_ODDS <= iddaa_odds[k] <= config.PICK_MAX_ODDS]
    if cands:
        k = max(cands, key=lambda x: edge[x])
        out["best"] = {"market": k, "edge": edge[k], "odds": round(iddaa_odds[k], 2), "fair_p": fair[k]}
    return out


def real_iddaa_odds(f: Fixture) -> dict[str, float]:
    """Fikstürün GERÇEK iddaa oranları: birincil kaynak Nesine/iddaa olmalı; yedek kaynaktan (football-data Avg)
    doldurulmuş anahtarlar çıkarılır — yoksa referans kendisiyle kıyaslanmış olur."""
    filled = (f.extra or {}).get("odds_sources", {})
    primary_ok = f.source in IDDAA_SOURCES
    return {k: v for k, v in (f.odds or {}).items()
            if (filled.get(k) in IDDAA_SOURCES if k in filled else primary_ok)}


def attach(m: dict, f: Fixture, fd_fixtures: list[Fixture] | None) -> dict | None:
    """run.py kancası: maça `sharp` bloğunu ve varsa bayrağı ekler. Veri/eşleşme yoksa hiçbir şey eklemez."""
    if m.get("status") == "finished" or f.result:
        return None
    odds = real_iddaa_odds(f)
    if not odds:
        return None
    fx = find_fixture(f.kickoff, f.home, f.away, fd_fixtures)
    if fx is None:
        return None
    blk = compute(odds, fx.extra.get("books"), fx.fetched_at)
    if not blk:
        return None
    m["sharp"] = blk
    if blk["best"] and FLAG not in m.setdefault("flags", []):
        m["flags"].append(FLAG)
    m.setdefault("provenance", {})["sharp"] = {
        "source": f"football-data.co.uk fixtures.csv ({blk['source']}) × iddaa oranı", "t": blk["fetched_at"]}
    return blk


def status(matches: list[dict]) -> SourceStatus:
    """Durum sayfası satırı. Kıyaslanacak maç olmayan gün 'skipped' (kaynak arızası değil, kapsam sınırı)."""
    blocks = [m["sharp"] for m in matches if m.get("sharp")]
    name = "Keskin piyasa farkı (iddaa × Pinnacle/Betfair adil olasılık; hipotez, kanıtlanmış kazanç değil)"
    if not blocks:
        return SourceStatus("sharp_edge", name, "skipped", now_iso(),
                            "Bugün fixtures.csv ile güvenle eşleşen gerçek iddaa oranlı maç yok.")
    by: dict[str, int] = {}
    for b in blocks:
        by[b["source"]] = by.get(b["source"], 0) + 1
    n_best = sum(1 for b in blocks if b.get("best"))
    n_odd = sum(1 for b in blocks if b.get("notes"))
    note = (f"{len(blocks)} maç kıyaslandı (" + ", ".join(f"{k} {v}" for k, v in sorted(by.items())) +
            f"); {n_best} maçta fark eşiği aşıldı" + (f"; {n_odd} maç olağan dışı fark nedeniyle elendi" if n_odd else "")
            + ". Referans oranlar fixtures.csv'nin son güncellemesine aittir (anlık değil).")
    return SourceStatus("sharp_edge", name, "ok", now_iso(), note, len(blocks))
