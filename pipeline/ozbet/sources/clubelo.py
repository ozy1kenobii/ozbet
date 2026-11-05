"""ClubElo (http://api.clubelo.com) — günlük kulüp Elo puanları (ücretsiz CSV API).

Uç nokta: GET http://api.clubelo.com/{YYYY-MM-DD}  → o gün geçerli tüm kulüplerin Elo'su.
CSV başlığı: Rank,Club,Country,Level,Elo,From,To   (Rank "None" olabilir; Country 3 harfli: TUR, ENG, ...)
Format, soccerdata (ClubElo.read_by_date) ve penaltyblog belgelerinden doğrulandı; bu ortamdan siteye erişilemedi.

Kullanım kuralları: günde 1 istek (24 saat disk önbelleği), PoliteClient robots.txt'yi kontrol eder;
robots izin vermezse Blocked → StatusBoard 'missing' işaretler ve simülasyon eski lig-gücü yoluna düşer.

Takım adları ASCII ve Almanca usulü harf çevirili: "Bueyueksehir", "Ankaraguecue", "Koebenhavn", "St Gillis".
Eşleme: TeamMatcher + (ue→u, oe→o, ae→a) alternatif yazımlar + aşağıdaki Türkçe ad ipuçları.
Lig maçlarında aday kümesi ülkeye göre daraltılır (yanlış eşleşme riskini azaltır).
"""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date

from ..http import PoliteClient
from ..teams import TeamMatcher, _ascii, normalize

log = logging.getLogger("ozbet.clubelo")
BASE = "http://api.clubelo.com"

# OZBET lig kimliği → ClubElo ülke kodu (lig maçlarında aday kümesini daraltmak için)
LEAGUE_COUNTRY = {
    "TR1": "TUR", "TR2": "TUR", "ENG1": "ENG", "ENG2": "ENG", "ESP1": "ESP", "ESP2": "ESP",
    "ITA1": "ITA", "ITA2": "ITA", "GER1": "GER", "GER2": "GER", "FRA1": "FRA", "FRA2": "FRA",
    "NED1": "NED", "POR1": "POR", "BEL1": "BEL", "SCO1": "SCO", "GRE1": "GRE",
}

# Bültendeki (Türkçe/kısaltılmış) yazım → ClubElo adı. Anahtar normalize() edilmiş haldedir.
# Yalnızca ClubElo yazımından emin olunan ya da zararsız (eşleşmezse etkisiz) ipuçları.
HINTS = {
    "kizil yildiz": "Crvena Zvezda", "crvena zvezda": "Crvena Zvezda", "red star belgrade": "Crvena Zvezda",
    "sparta prag": "Sparta Praha", "slavia prag": "Slavia Praha", "sparta prague": "Sparta Praha",
    "slavia prague": "Slavia Praha", "kopenhag": "Koebenhavn", "copenhagen": "Koebenhavn",
    "kobenhavn": "Koebenhavn", "levski sofya": "Levski", "levski sofia": "Levski",
    "cska sofya": "CSKA Sofia", "d zagreb": "Dinamo Zagreb", "dinamo zagreb": "Dinamo Zagreb",
    "r sociedad": "Sociedad", "real sociedad": "Sociedad", "u s gilloise": "St Gillis",
    "union saint gilloise": "St Gillis", "union sg": "St Gillis", "j bialystok": "Jagiellonia",
    "jagiellonia bialystok": "Jagiellonia", "lech poznan": "Lech", "viktoria plzen": "Plzen",
    "bayern munih": "Bayern", "bayern munich": "Bayern", "bayern munchen": "Bayern",
    "b dortmund": "Dortmund", "borussia dortmund": "Dortmund", "basaksehir": "Bueyueksehir",
    "istanbul basaksehir": "Bueyueksehir", "rams basaksehir": "Bueyueksehir",
    "kayserispor": "Kayseri", "karagumruk": "Karaguemruek", "fatih karagumruk": "Karaguemruek",
    "ankaragucu": "Ankaraguecue", "nk celje": "Celje", "sturm graz": "Sturm Graz",
    "kuopion": "KuPS", "k almaty": "Kairat", "kairat almaty": "Kairat",
}

_FOLD = str.maketrans({"ø": "o", "Ø": "O", "æ": "a", "Æ": "A", "å": "a", "Å": "A", "ß": "ss", "đ": "d", "Đ": "D"})


def _fold(name: str) -> str:
    return name.translate(_FOLD)


def _alt(name: str) -> str | None:
    """ClubElo'nun Almanca usulü çevirisini sadeleştirir: Bueyueksehir → Buyuksehir, Koebenhavn → Kobenhavn."""
    s = re.sub(r"(?<=[A-Za-z])ue", "u", name)
    s = re.sub(r"(?<=[A-Za-z])oe", "o", s)
    s = re.sub(r"(?<=[A-Za-z])ae", "a", s)
    return s if s != name else None


def parse_csv(text: str) -> list[dict]:
    out = []
    rd = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    for r in rd:
        r = {str(k).strip().lower(): (v or "").strip() for k, v in r.items() if k}
        try:
            elo = float(r.get("elo", ""))
        except ValueError:
            continue
        club = r.get("club")
        if not club:
            continue
        lvl = r.get("level", "")
        out.append({"club": club, "country": r.get("country") or None, "level": int(lvl) if lvl.isdigit() else None,
                    "elo": elo})
    return out


class EloTable:
    def __init__(self, rows: list[dict], day: str, source: str = "clubelo"):
        self.rows: dict[str, dict] = {}
        for r in rows:                      # aynı ad iki kez gelirse ilki (sıralamada üstteki) korunur
            self.rows.setdefault(r["club"], r)
        self.date = day
        self.source = source
        self._matchers: dict[str | None, tuple[TeamMatcher, dict[str, str]]] = {}

    def __len__(self):
        return len(self.rows)

    def _matcher(self, country: str | None):
        if country not in self._matchers:
            alias: dict[str, str] = {}
            for club, r in self.rows.items():
                if country and r["country"] != country:
                    continue
                alias[club] = club
                a = _alt(club)
                if a and a not in alias:
                    alias[a] = club
            self._matchers[country] = (TeamMatcher(list(alias)), alias)
        return self._matchers[country]

    def lookup(self, name: str, league_id: str | None = None) -> dict | None:
        """Takımın Elo kaydı veya None. league_id lig maçı ise aday kümesi o ülkeyle sınırlanır."""
        country = LEAGUE_COUNTRY.get(league_id or "")
        q = _fold(name)
        hint = HINTS.get(normalize(q)) or HINTS.get(normalize(_ascii(q)))
        if hint and hint in self.rows and (not country or self.rows[hint]["country"] == country):
            return self.rows[hint]
        tm, alias = self._matcher(country)
        hit = tm.match(q)
        return self.rows[alias[hit]] if hit else None

    def pair(self, home: str, away: str, league_id: str | None = None) -> dict | None:
        """Maç kartı için {"home","away","source","date"}; iki takımdan biri bulunamazsa None."""
        h, a = self.lookup(home, league_id), self.lookup(away, league_id)
        if not h or not a or h is a:
            return None
        return {"home": round(h["elo"]), "away": round(a["elo"]), "source": self.source, "date": self.date,
                "home_club": h["club"], "away_club": a["club"]}


def ratings(client: PoliteClient, day: date) -> EloTable:
    """Günde 1 istek; 24 saat önbellek. Boş/başlık-yalnız yanıt hata sayılır."""
    ds = day.isoformat()
    text = client.get(f"{BASE}/{ds}", ttl=24 * 3600)
    rows = parse_csv(text)
    if not rows:
        raise RuntimeError("ClubElo yanıtı boş veya beklenmeyen biçimde")
    return EloTable(rows, ds)
