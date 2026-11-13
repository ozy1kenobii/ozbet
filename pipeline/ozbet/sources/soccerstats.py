"""SoccerStats — lig gol eğilimleri (trends.asp): takım başı 2.5+ (Ü2.5 %) ve BTS (KG %).

Bu bir tahmin sitesi değil; konsensüse "istatistik eğilimi" oyu olarak girer:
iki takımın ortalama 2.5+ yüzdesi ≥ %55 → 2.5 Üst, ≤ %40 → 2.5 Alt; BTS ≥ %55 → KG Var, ≤ %40 → KG Yok.
Tablolar başlık metnine göre (pandas.read_html) seçilir; sınıf adlarına bağımlı değildir.

VARSAYILAN OLARAK DEVRE DIŞI (registry): Kasım 2026'da sitenin Cloudflare güvenlik duvarı GitHub Actions'tan gelen
her isteğe HTTP 403 "Sorry, you have been blocked" döndürüyor (trends.asp ve results.asp, 40/40 çalıştırma).
Engel aşılmaz. 1. Lig geçmişi TFF'den (tff_tr2) geliyor. Engellenmeyen bir ağdan çalıştırılıyorsa
OZBET_ENABLE_SOURCES=soccerstats ile yeniden açılabilir.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd

from .. import config
from ..http import Blocked, PoliteClient
from ..teams import TeamMatcher
from .base import Prediction, now_iso

BASE = "https://www.soccerstats.com"


def _pct(v):
    try:
        return float(str(v).replace("%", "").strip()) / 100
    except ValueError:
        return None


def league_trends(client: PoliteClient, code: str) -> dict[str, dict]:
    html = client.get(f"{BASE}/trends.asp", params={"league": code}, ttl=12 * 3600)
    tables = pd.read_html(io.StringIO(html))
    out = {}
    for tb in tables:
        cols = [str(c[-1] if isinstance(c, tuple) else c).strip() for c in tb.columns]
        if "2.5+" not in cols or "BTS" not in cols:
            continue
        tb.columns = cols
        name_col = next((c for c in cols if not c.replace(".", "").replace("+", "").isdigit()
                         and c not in ("GP", "Avg", "BTS", "CS", "FTS", "WTN", "LTN", "#")), cols[0])
        for _, r in tb.iterrows():
            team = str(r[name_col]).strip()
            o25, bts = _pct(r["2.5+"]), _pct(r["BTS"])
            if team and team.lower() != "nan" and o25 is not None and bts is not None:
                out.setdefault(team, {"o25": o25, "bts": bts})
        if out:
            break
    return out


def predictions(client: PoliteClient, day: date, fixtures=()) -> list[Prediction]:
    t = now_iso()
    out = []
    by_league: dict[str, list] = {}
    for f in fixtures:
        lg = config.LEAGUE_BY_ID.get(f.league_id or "")
        if lg and lg.soccerstats and f.kickoff.date() == day:
            by_league.setdefault(lg.soccerstats, []).append(f)
    if not by_league:
        return []
    errors, blocked = 0, None
    for code, fx in by_league.items():
        try:
            tr = league_trends(client, code)
        except Blocked as e:
            blocked = e
            break       # site engelliyor: diğer ligleri de boşuna isteme
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        tm = TeamMatcher(list(tr))
        for f in fx:
            h, a = tm.match(f.home), tm.match(f.away)
            if not h or not a:
                continue
            o = (tr[h]["o25"] + tr[a]["o25"]) / 2
            b = (tr[h]["bts"] + tr[a]["bts"]) / 2
            picks = {}
            if o >= 0.55: picks["OU25"] = "O2.5"
            elif o <= 0.40: picks["OU25"] = "U2.5"
            if b >= 0.55: picks["BTTS"] = "BTTS_Y"
            elif b <= 0.40: picks["BTTS"] = "BTTS_N"
            if picks:
                out.append(Prediction("soccerstats", f.home, f.away, day.isoformat(), t, picks,
                                      probs={"O2.5": round(o, 3), "BTTS_Y": round(b, 3)},
                                      note=f"Ü2.5 ort. %{round(o*100)}, KG ort. %{round(b*100)}"))
    if blocked and not out:
        raise Blocked(f"SoccerStats erişimi engelliyor (aşılmaz): {blocked}") from blocked
    if errors == len(by_league):
        raise RuntimeError("soccerstats: hiçbir lig tablosu okunamadı (trends.asp tablo başlıkları '2.5+'/'BTS' "
                           "değişmiş olabilir)")
    return out


# ---------------- Sonuç geçmişi (football-data.co.uk'ta olmayan ligler, ör. 1. Lig) ----------------
# Sayfa: results.asp?league=turkey2&pmtype=bydate (içinde bulunulan sezon), results.asp?league=turkey2_{YYYY}
# (YYYY = sezonun BİTİŞ yılı: turkey2_2026 = 2025/26). robots.txt yalnızca /*/info/ yolunu yasaklıyor (Kasım 2026).
# Kasım 2026 yapısı (WebFetch ile görüldü): satır başına tarih hücresi "Fri 7 Aug" (yıl yok), maç hücresi
# "Boluspor vs Manisa FK", skor "1:2", İY "(1:2)"; eski sezon sayfalarında ev | skor | deplasman ayrı hücreler ve İY yok.
# Ayrıştırıcı hücre metinlerine göre çalışır, sınıf adlarına bağımlı değildir.
import re as _re
from datetime import date as _date

_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                      "nov", "dec"), 1)}
_DATE_RX = _re.compile(r"^(?:mon|tue|wed|thu|fri|sat|sun)\w*\.?\s+(\d{1,2})\s+([a-z]{3})\w*$", _re.I)
_SCORE_RX = _re.compile(r"^(\d{1,2})\s*[:\-]\s*(\d{1,2})$")
_HT_RX = _re.compile(r"^\(\s*(\d{1,2})\s*[:\-]\s*(\d{1,2})\s*\)$")


def _season_start(today: _date) -> int:
    return today.year if today.month >= 7 else today.year - 1


def parse_results(html: str, season_start: int, season: str | None = None) -> list[dict]:
    """soccerstats sonuç sayfasını football_data.history() satır biçimine çevirir."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()
    season = season or f"{season_start % 100:02d}{(season_start + 1) % 100:02d}"
    for tr in soup.find_all("tr"):
        if tr.find("tr"):          # iç içe tablo kabı → yalnız en içteki satırlar
            continue
        cells = [_re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip() for td in tr.find_all(["td", "th"])]
        di = next((i for i, c in enumerate(cells) if _DATE_RX.match(c)), None)
        si = next((i for i, c in enumerate(cells) if _SCORE_RX.match(c) and (di is None or i > di)), None)
        if di is None or si is None:
            continue
        dm = _DATE_RX.match(cells[di])
        mon = _MONTHS.get(dm.group(2).lower()[:3])
        if not mon:
            continue
        year = season_start if mon >= 7 else season_start + 1
        try:
            d = _date(year, mon, int(dm.group(1)))
        except ValueError:
            continue
        between = [c for c in cells[di + 1:si] if c]
        vs = next((c for c in between if _re.search(r"\s+vs\.?\s+", c)), None)
        if vs:
            home, away = (x.strip() for x in _re.split(r"\s+vs\.?\s+", vs, maxsplit=1))
        else:
            after = [c for c in cells[si + 1:] if c]
            if not between or not after:
                continue
            home, away = between[-1], after[0]
        if not home or not away or _SCORE_RX.match(away):
            continue
        sm = _SCORE_RX.match(cells[si])
        hg, ag = int(sm.group(1)), int(sm.group(2))
        b = cells[si].split(":")[-1].strip()
        if hg > 12 or ag > 12 or (len(b) == 2 and b.startswith("0")):   # "19:00"/"12:05" başlama saati, skor değil
            continue
        ht = next((_HT_RX.match(c) for c in cells[si + 1:] if _HT_RX.match(c)), None)
        key = (d, home, away)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"date": d, "season": season, "home": home, "away": away, "hg": hg, "ag": ag,
                     "hthg": int(ht.group(1)) if ht else None, "htag": int(ht.group(2)) if ht else None,
                     "odds_open": {}, "odds_close": {}, "src": "soccerstats"})
    return rows


def results_history(client: PoliteClient, code: str, today: _date, seasons: int = 3) -> list[dict]:
    """İçinde bulunulan + önceki (seasons-1) sezonun oynanmış maçları. Eski sezonlar 30 gün önbellekte."""
    start = _season_start(today)
    out: list[dict] = []
    errors = []
    for k in range(seasons):
        s0 = start - k
        league = code if k == 0 else f"{code}_{s0 + 1}"
        try:
            html = client.get(f"{BASE}/results.asp", params={"league": league, "pmtype": "bydate"},
                              ttl=12 * 3600 if k == 0 else 30 * 86400)
        except Blocked as e:
            if not out:
                raise Blocked(f"SoccerStats erişimi engelliyor (aşılmaz): {e}") from e
            errors.append(f"{league}: Blocked")
            break
        except Exception as e:  # noqa: BLE001 — eski sezon sayfası yoksa diğerleriyle devam
            errors.append(f"{league}: {type(e).__name__}")
            continue
        got = [r for r in parse_results(html, s0) if r["date"] < today]
        out += got
    if not out and errors:
        raise RuntimeError("soccerstats sonuç sayfaları okunamadı: " + "; ".join(errors))
    return out
