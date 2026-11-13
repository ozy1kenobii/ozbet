"""Kapanış oranı değeri (CLV): tercihin oranı maç başlayana kadar kısaldı mı?

İsabet ve ROI birkaç yüz bahiste çoğunlukla gürültüdür; CLV aynı soruya çok daha az örnekle cevap verir:
kapanış fiyatı piyasanın en bilgili halidir, tercihlerimiz düzenli olarak kapanıştan iyi fiyat alıyorsa
seçimde bilgi vardır, almıyorsa yoktur. Kâr vaadi değildir (iddaa marjı ~%20); yalnız dürüst bir erken sinyaldir.

Tanımlar (pozitif = iyi, oran bizim aldığımızdan sonra kısalmış):
- Ham:      clv_raw = oran_tercih / oran_kapanış − 1
- Marjsız:  clv     = adil_p_kapanış / adil_p_tercih − 1   (iki fiyat grubundan da marj Shin ile temizlenir;
                      marj değişimi hareket sanılmasın diye asıl ölçü budur)
Marj temizlenemiyorsa (grup eksik, eski satırda diğer oranlar yok) ham CLV kullanılır ve method="raw" yazılır.

Kaynaklar: tercih anı = history satırı (odds + markets[].o), kapanış = iddaa arşivi satırındaki "c"
(başlama saatinden ÖNCE görülen son oranlar). Arşivin "o" alanı (ilk görülen oran) ile ayrıca
açılış→kapanış CLV'si de hesaplanır: gün dosyası her çalıştırmada yeniden yazıldığı için history'deki
oran çoğu maçta zaten son çalıştırmanın oranıdır ve kapanışa eşit çıkar.
"""
from __future__ import annotations

from collections import defaultdict

from ..markets import all_groups, all_labels
from .market import shin

DC = {"1X": ("1", "X"), "X2": ("X", "2"), "12": ("1", "2")}   # çifte şans → 1X2 bileşenleri
METHOD_FAIR, METHOD_RAW = "shin", "raw"


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1.0


def _group_of() -> dict[str, list[str]]:
    return {k: keys for keys in all_groups().values() for k in keys}


def fair_prob(market: str, odds: dict | None, group_of: dict[str, list[str]] | None = None) -> float | None:
    """Marketin marjsız olasılığı; grubun tüm oranları yoksa None."""
    if not odds:
        return None
    if market in DC:   # çifte şans: 1X2 grubunun adil olasılıklarının toplamı
        keys = ["1", "X", "2"]
        if not all(_ok(odds.get(k)) for k in keys):
            return None
        fp = dict(zip(keys, shin([float(odds[k]) for k in keys])))
        return fp[DC[market][0]] + fp[DC[market][1]]
    keys = (group_of or _group_of()).get(market)
    if not keys or not all(_ok(odds.get(k)) for k in keys):
        return None
    return dict(zip(keys, shin([float(odds[k]) for k in keys])))[market]


def _pair(market: str, o_pick: float, grp_pick: dict | None, close: dict, group_of) -> dict:
    """Tek fiyat çifti için ham + (mümkünse) marjsız CLV."""
    o_close = float(close[market])
    raw = o_pick / o_close - 1
    fp = fair_prob(market, grp_pick, group_of)
    fc = fair_prob(market, close, group_of)
    if fp and fc:
        return {"clv": round(fc / fp - 1, 4), "clv_raw": round(raw, 4), "method": METHOD_FAIR,
                "fair_p_pick": round(fp, 4), "fair_p_close": round(fc, 4)}
    return {"clv": round(raw, 4), "clv_raw": round(raw, 4), "method": METHOD_RAW}


def compute(market: str, odds_pick: float | None, pick_odds: dict | None, arch: dict | None) -> dict:
    """Bir tercih için CLV.
    pick_odds: tercih anındaki oranlar (marj temizliği için; yoksa ham CLV'ye düşülür).
    arch: iddaa arşivi satırı. Dönen sözlükte her zaman "status" var:
      ok | no_odds (tercihte oran yok) | no_archive | no_close (başlamadan önce oran görülmemiş) | no_market."""
    if not _ok(odds_pick):
        return {"status": "no_odds"}
    if not arch:
        return {"status": "no_archive"}
    close = arch.get("c") or {}
    if not close:
        return {"status": "no_close"}
    if not _ok(close.get(market)):
        return {"status": "no_market"}
    group_of = _group_of()
    grp = dict(pick_odds or {})
    grp[market] = odds_pick   # tercihin kendi oranı her zaman satırdaki orandır
    out = {"status": "ok", "odds_pick": float(odds_pick), "odds_close": float(close[market]),
           **_pair(market, float(odds_pick), grp if pick_odds else None, close, group_of),
           "n_snap": arch.get("n_snap", 0)}
    # açılış → kapanış: yalnız kapanış açılıştan sonra alınmışsa anlamlı
    opening = arch.get("o") or {}
    if _ok(opening.get(market)) and (arch.get("n_snap") or 0) >= 2 and arch.get("ts_o") != arch.get("ts_c"):
        op = _pair(market, float(opening[market]), opening, close, group_of)
        out["open"] = {"odds_open": float(opening[market]), "clv": op["clv"], "clv_raw": op["clv_raw"],
                       "method": op["method"]}
    return out


def annotate(rows: list[dict], archive_rows: list[dict]) -> int:
    """History satırlarına (tercihi olanlara) r["clv"] sözlüğünü yazar; hesaplanabilen satır sayısını döndürür."""
    by_id = {a["id"]: a for a in archive_rows if a.get("id")}
    n = 0
    for r in rows:
        if "won" not in r or "pick" not in r:
            continue
        grp = {e["m"]: e["o"] for e in (r.get("markets") or []) if e.get("o")}
        r["clv"] = compute(r["pick"], r.get("odds"), grp or None, by_id.get(r.get("id")))
        n += r["clv"]["status"] == "ok"
    return n


def value_of(row: dict) -> float | None:
    """Satırın CLV'si (marjsız, yoksa ham); hesaplanamadıysa None."""
    c = row.get("clv")
    return c.get("clv") if isinstance(c, dict) and c.get("status") == "ok" else None


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) + 0.0 if xs else None   # +0.0: "-0.0" yazılmasın


def _ci(xs: list[float]) -> list[float] | None:
    """Ortalama için normal yaklaşımlı %95 aralık; n<2 ise None."""
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    h = 1.96 * (sum((x - m) ** 2 for x in xs) / (n - 1) / n) ** 0.5
    return [round(m - h, 4) + 0.0, round(m + h, 4) + 0.0]


def summarize(rows: list[dict]) -> dict:
    """Karne için CLV özeti. Tüm ortalamalar tercih başına eşit ağırlıklı."""
    ok = [r for r in rows if value_of(r) is not None]
    vals = [r["clv"]["clv"] for r in ok]
    by = defaultdict(list)
    for r in ok:
        by[r["pick"]].append(r["clv"]["clv"])
    labels = all_labels()
    op = [r["clv"]["open"] for r in ok if r["clv"].get("open")]
    miss = defaultdict(int)
    for r in rows:
        c = r.get("clv")
        if isinstance(c, dict) and c.get("status") != "ok":
            miss[c["status"]] += 1
    return {
        "n": len(ok),
        "avg_clv": _mean(vals),
        "avg_clv_ci": _ci(vals),
        "avg_clv_raw": _mean([r["clv"]["clv_raw"] for r in ok]),
        "beat_close_rate": round(sum(v > 0 for v in vals) / len(vals), 4) if vals else None,
        "by_market": sorted(({"market": k, "label": labels.get(k, k), "n": len(v), "avg_clv": _mean(v)}
                             for k, v in by.items()), key=lambda x: -x["n"]),
        # ek alanlar: ölçünün ne kadar bilgi taşıdığını okumak için
        "n_fair": sum(r["clv"]["method"] == METHOD_FAIR for r in ok),      # marjı temizlenebilen
        "n_raw_only": sum(r["clv"]["method"] == METHOD_RAW for r in ok),   # ham CLV'ye düşülen
        "n_unchanged": sum(r["clv"]["odds_pick"] == r["clv"]["odds_close"] for r in ok),   # fiyat hiç oynamamış
        "missing": dict(miss),
        "open": {"n": len(op), "avg_clv": _mean([o["clv"] for o in op]), "avg_clv_ci": _ci([o["clv"] for o in op]),
                 "avg_clv_raw": _mean([o["clv_raw"] for o in op]),
                 "beat_close_rate": round(sum(o["clv"] > 0 for o in op) / len(op), 4) if op else None},
    }
