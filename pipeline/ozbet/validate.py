"""Veri doğrulama: kaynaklardan gelen saçma değerleri modele ve siteye girmeden ayıklar.

Kurallar bilerek basit ve açıklanabilir tutuldu; her ayıklama bir sayaçta toplanır ve status.json'a yazılır.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from .markets import GROUPS, all_groups

ODDS_MIN, ODDS_MAX = 1.01, 100.0
MARGIN_MIN, MARGIN_MAX = -0.02, 0.45   # marj negatifse arbitraj = veri hatası; %45 üstü bozuk satır
MAX_GOALS = 15


class Report:
    def __init__(self):
        self.c: Counter = Counter()

    def add(self, key: str, n: int = 1):
        if n:
            self.c[key] += n

    def as_dict(self) -> dict[str, int]:
        return dict(sorted(self.c.items()))


def clean_odds(odds: dict[str, float] | None, rep: Report | None = None) -> dict[str, float]:
    """Aralık dışı oranları ve marjı tutarsız market gruplarını atar."""
    if not odds:
        return {}
    out = {}
    for k, v in odds.items():
        try:
            v = float(v)
        except (TypeError, ValueError):
            rep and rep.add("oran_sayi_degil")
            continue
        if ODDS_MIN <= v <= ODDS_MAX:
            out[k] = v
        else:
            rep and rep.add("oran_aralik_disi")
    for g, keys in all_groups().items():
        if all(k in out for k in keys):
            margin = sum(1 / out[k] for k in keys) - 1
            # çok seçenekli ek marketlerde (ör. MS & Ü/A, 6 seçenek) marj doğal olarak daha yüksek
            hi = MARGIN_MAX if g in GROUPS else MARGIN_MAX + 0.08 * (len(keys) - 2)
            if not (MARGIN_MIN <= margin <= hi):
                for k in keys:
                    out.pop(k, None)
                rep and rep.add(f"marj_tutarsiz_{g}")
        elif any(k in out for k in keys) and g == "1x2":
            # 1X2'nin yalnız bir kısmı geldiyse (ör. sadece 1 ve 2) yanlış eşleşme şüphesi → grubu at
            for k in keys:
                out.pop(k, None)
            rep and rep.add("eksik_1x2")
    return out


def clean_result(res: dict | None, rep: Report | None = None) -> dict | None:
    if not res or not res.get("ft"):
        return None
    try:
        h, a = (int(x) for x in res["ft"])
    except (TypeError, ValueError):
        rep and rep.add("skor_bozuk")
        return None
    if not (0 <= h <= MAX_GOALS and 0 <= a <= MAX_GOALS):
        rep and rep.add("skor_aralik_disi")
        return None
    ht = res.get("ht")
    if ht:
        try:
            hh, ha = (int(x) for x in ht)
            if hh > h or ha > a or hh < 0 or ha < 0:
                rep and rep.add("iy_skor_tutarsiz")
                ht = None
            else:
                ht = [hh, ha]
        except (TypeError, ValueError):
            ht = None
    return {"ft": [h, a], "ht": ht}


def valid_fixture(f, today: date, rep: Report | None = None) -> bool:
    """Takım adları dolu ve farklı, başlama saati bugün-1 ile bugün+3 arasında."""
    h, a = (f.home or "").strip(), (f.away or "").strip()
    if not h or not a or h.lower() == a.lower():
        rep and rep.add("fikstur_takim_bozuk")
        return False
    d = f.kickoff.date()
    if not (today - timedelta(days=1) <= d <= today + timedelta(days=3)):
        rep and rep.add("fikstur_tarih_disi")
        return False
    return True


def clean_fixtures(fixtures: list, today: date, rep: Report) -> list:
    out = []
    for f in fixtures:
        if not valid_fixture(f, today, rep):
            continue
        f.odds = clean_odds(f.odds, rep)
        if f.result:
            f.result = clean_result(f.result, rep)
            if not f.result:
                f.status = "scheduled" if f.status == "finished" else f.status
        out.append(f)
    return out


def clean_history(rows: list[dict], rep: Report) -> list[dict]:
    """Geçmiş maç satırları: bozuk skorlar atılır, aynı maç (tarih+takımlar) bir kez tutulur, İY tutarsızsa silinir."""
    seen, out = set(), []
    for r in rows:
        try:
            hg, ag = int(r["hg"]), int(r["ag"])
        except (KeyError, TypeError, ValueError):
            rep.add("gecmis_skor_bozuk")
            continue
        if not (0 <= hg <= MAX_GOALS and 0 <= ag <= MAX_GOALS) or r.get("home") == r.get("away"):
            rep.add("gecmis_satir_bozuk")
            continue
        key = (r["date"], r["home"], r["away"])
        if key in seen:
            rep.add("gecmis_tekrar")
            continue
        seen.add(key)
        if r.get("hthg") is not None and r.get("htag") is not None and (r["hthg"] > hg or r["htag"] > ag):
            r = {**r, "hthg": None, "htag": None}
            rep.add("gecmis_iy_tutarsiz")
        out.append(r)
    return out


def dedupe_matches(matches: list[dict], rep: Report) -> list[dict]:
    seen, out = set(), []
    for m in matches:
        if m["id"] in seen:
            rep.add("mac_tekrar")
            continue
        seen.add(m["id"])
        out.append(m)
    return out
