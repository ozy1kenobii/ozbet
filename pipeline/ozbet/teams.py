"""Takım adı eşleme: elle sözlük + normalleştirme + rapidfuzz bulanık eşleme.

"Fenerbahçe" = "Fenerbahce" = "Fenerbahçe SK" = "Fenerbahce A.S."
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from rapidfuzz import fuzz, process

_TR = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                     "ç": "c", "Ç": "c", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u"})
_NOISE = re.compile(
    r"\b(fc|fk|sk|cf|afc|ac|as|a\.?s\.?|jk|bk|cfc|sc|sv|ssc|ss|vfb|vfl|tsg|1\.|calcio|club|kulubu|futbol|football|de|the)\b"
)

# kanonik ad → bilinen yazımlar (normalize edilmeden önce; normalleştirme ayrıca uygulanır)
ALIASES: dict[str, list[str]] = {
    # Süper Lig
    "Galatasaray": ["Galatasaray", "Galatasaray AS", "Galatasaray A.Ş."],
    "Fenerbahçe": ["Fenerbahce", "Fenerbahçe SK", "Fenerbahce Istanbul"],
    "Beşiktaş": ["Besiktas", "Beşiktaş JK", "Besiktas JK"],
    "Trabzonspor": ["Trabzonspor"],
    "Başakşehir": ["Basaksehir", "Buyuksehyr", "Istanbul Basaksehir", "RAMS Başakşehir", "Rams Basaksehir",
                   "İstanbul Başakşehir", "Medipol Başakşehir"],
    "Kasımpaşa": ["Kasimpasa"],
    "Göztepe": ["Goztepe"],
    "Çaykur Rizespor": ["Rizespor", "Ç. Rizespor", "Caykur Rizespor"],
    "Gaziantep FK": ["Gaziantep", "Gazisehir Gaziantep", "Gaziantep F.K."],
    "Kocaelispor": ["Kocaelispor"],
    "Gençlerbirliği": ["Genclerbirligi", "Genclerbirligi Ankara"],
    "Fatih Karagümrük": ["Karagumruk", "F. Karagümrük", "Fatih Karagumruk"],
    "Samsunspor": ["Samsunspor"],
    "Eyüpspor": ["Eyupspor", "Ikas Eyüpspor"],
    "Antalyaspor": ["Antalyaspor", "Onvo Antalyaspor"],
    "Alanyaspor": ["Alanyaspor", "Corendon Alanyaspor"],
    "Konyaspor": ["Konyaspor", "Tümosan Konyaspor"],
    "Kayserispor": ["Kayserispor", "Zecorner Kayserispor"],
    "Sivasspor": ["Sivasspor"],
    "Hatayspor": ["Hatayspor"],
    "Adana Demirspor": ["Ad. Demirspor", "Adana Demirspor"],
    "Bodrum FK": ["Bodrumspor", "Bodrum", "Sipay Bodrum FK"],
    "Amedspor": ["Amed SK", "Amedspor", "Amed Sportif"],
    "Pendikspor": ["Pendikspor"],
    "Ankaragücü": ["Ankaragucu", "MKE Ankaragücü"],
    "Erzurumspor": ["Erzurum", "Erzurumspor FK", "Erzurum BB"],
    "Manisa FK": ["Manisa", "Manisa FK"],
    "Bandırmaspor": ["Bandirmaspor"],
    "Iğdır FK": ["Igdir", "Iğdır FK"],
    "Sakaryaspor": ["Sakaryaspor"],
    "Boluspor": ["Boluspor"],
    "Ümraniyespor": ["Umraniyespor"],
    "Keçiörengücü": ["Keciorengucu", "Ankara Keçiörengücü"],
    "Esenler Erokspor": ["Erokspor", "Esenler Erokspor"],
    "Çorum FK": ["Corum", "Çorum FK"],
    "Serik Belediyespor": ["Serik Belediyespor", "Serikspor"],
    "Sarıyer": ["Sariyer"],
    # Büyük Avrupa kulüpleri (yaygın yazım farkları)
    "Manchester United": ["Man United", "Manchester Utd", "Man Utd"],
    "Manchester City": ["Man City", "Manchester C."],
    "Tottenham": ["Tottenham Hotspur", "Spurs"],
    "Wolverhampton": ["Wolves", "Wolverhampton Wanderers"],
    "Newcastle": ["Newcastle United", "Newcastle Utd"],
    "Nottingham Forest": ["Nott'm Forest", "Nottm Forest", "Nottingham"],
    "West Ham": ["West Ham United"],
    "Brighton": ["Brighton & Hove Albion", "Brighton Hove"],
    "Leeds": ["Leeds United"],
    "Sheffield United": ["Sheffield Utd", "Sheff Utd"],
    "Atlético Madrid": ["Ath Madrid", "Atletico Madrid", "Atl. Madrid", "Atlético de Madrid"],
    "Athletic Bilbao": ["Ath Bilbao", "Athletic Club"],
    "Real Sociedad": ["Sociedad"],
    "Betis": ["Real Betis"],
    "Celta Vigo": ["Celta", "RC Celta"],
    "Espanyol": ["Espanol", "RCD Espanyol"],
    "Rayo Vallecano": ["Vallecano", "Rayo"],
    "Inter": ["Inter Milan", "Internazionale", "Inter Milano"],
    "Milan": ["AC Milan"],
    "Roma": ["AS Roma"],
    "Napoli": ["SSC Napoli"],
    "Bayern Münih": ["Bayern Munich", "Bayern München", "FC Bayern"],
    "Borussia Dortmund": ["Dortmund", "B. Dortmund"],
    "Leverkusen": ["Bayer Leverkusen", "B. Leverkusen"],
    "Borussia M'gladbach": ["M'gladbach", "Monchengladbach", "B. Mönchengladbach", "Gladbach"],
    "Eintracht Frankfurt": ["Ein Frankfurt", "Frankfurt"],
    "RB Leipzig": ["Leipzig", "RasenBallsport Leipzig"],
    "Paris Saint-Germain": ["Paris SG", "PSG", "Paris Saint Germain"],
    "Olympique Marsilya": ["Marseille", "Olympique Marseille", "Marsilya"],
    "Olympique Lyon": ["Lyon", "Olympique Lyonnais"],
    "St Etienne": ["Saint-Etienne", "St. Etienne"],
}


def normalize(name: str) -> str:
    s = name.translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " ").replace("'", "").replace(".", ". ")
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for canon, alts in ALIASES.items():
        for a in [canon, *alts]:
            idx[normalize(a)] = canon
    return idx


def canonical(name: str) -> str:
    """Sözlükte varsa kanonik adı, yoksa kırpılmış özgün adı döndürür."""
    return _alias_index().get(normalize(name), name.strip())


def team_key(name: str) -> str:
    """Kaynaklar arası birleştirme anahtarı."""
    return normalize(canonical(name)).replace(" ", "-")


class TeamMatcher:
    """Belirli bir aday kümesine (ör. o ligin geçmiş verisindeki takımlar) eşleme."""

    def __init__(self, candidates: list[str], threshold: int = 84):
        self.candidates = list(dict.fromkeys(candidates))
        self.threshold = threshold
        self._keys = {team_key(c): c for c in self.candidates}
        self._norm = {normalize(canonical(c)): c for c in self.candidates}

    def match(self, name: str) -> str | None:
        k = team_key(name)
        if k in self._keys:
            return self._keys[k]
        n = normalize(canonical(name))
        if not n:
            return None
        best = process.extractOne(n, list(self._norm), scorer=fuzz.token_set_ratio)
        if best and best[1] >= self.threshold:
            # token_set_ratio alt küme eşleşmesinde çok cömert: uzunluk farkını da kontrol et
            alt = fuzz.ratio(n, best[0])
            if alt >= 60 or best[1] == 100 and min(len(n), len(best[0])) >= 5:
                return self._norm[best[0]]
        return None
