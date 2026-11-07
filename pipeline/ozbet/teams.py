"""Takım adı eşleme: elle sözlük + normalleştirme + rapidfuzz bulanık eşleme.

"Fenerbahçe" = "Fenerbahce" = "Fenerbahçe SK" = "Fenerbahce A.S."
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from rapidfuzz import fuzz, process

_TR = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                     "ç": "c", "Ç": "c", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u",
                     # NFKD'nin ayrıştırmadığı harfler (İskandinav/Polonya/Almanya): yoksa "Brøndby" → "brndby"
                     "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ß": "ss", "ł": "l", "Ł": "l",
                     "đ": "d", "Đ": "d"})
_NOISE = re.compile(
    r"\b(fc|fk|sk|cf|afc|ac|as|a\.?s\.?|jk|bk|cfc|sc|sv|ssc|ss|vfb|vfl|tsg|1\.|calcio|club|kulubu|futbol|football|de|the)\b"
)

# kanonik ad → bilinen yazımlar (normalize edilmeden önce; normalleştirme ayrıca uygulanır)
ALIASES: dict[str, list[str]] = {
    # football-data "new" ligleri (İngilizce adlar ↔ yerel yazımlar)
    "FC Copenhagen": ["FC Copenhagen", "Copenhagen", "København", "FC København", "F.C. København",
                      "Kopenhag"],
    "Djurgarden": ["Djurgarden", "Djurgårdens IF", "Djurgardens IF", "Djurgården"],
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
    "Dresden": ["Dynamo Dresden", "SG Dynamo Dresden"],
    "Greuther Furth": ["G. Furth", "Greuther Fürth", "SpVgg Greuther Fürth", "Fürth"],
    "Derby": ["Derby County"],
}


def _ascii(name: str) -> str:
    s = name.translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower()


# Altyapı / kadın / rezerv takım etiketleri: etiketi farklı iki ad ASLA eşleşmez.
_VARIANT_RX = [
    (re.compile(r"\bu\s?-?(1[5-9]|2[0-3])\b"), lambda m: f"u{m.group(1)}"),
    (re.compile(r"\b(kadin|kadinlar|women|womens|ladies|feminino|femenino|feminine|frauen|femminile|w)\b|\(k\)|\(w\)"),
     lambda m: "w"),
    (re.compile(r"\b(reserves?|res|castilla|youth|akademi|altyapi|primavera|jong)\b"), lambda m: "res"),
    (re.compile(r"\s(ii|b|c)\s*$"), lambda m: m.group(1)),
]


def variant(name: str) -> str:
    """'' = A takımı; aksi halde 'u19', 'w', 'res', 'ii', 'b' gibi etiket."""
    s = _ascii(name)
    tags = []
    for rx, fn in _VARIANT_RX:
        m = rx.search(s)
        if m:
            tags.append(fn(m))
    return "+".join(sorted(set(tags)))


def _strip_variant(s: str) -> str:
    for rx, _ in _VARIANT_RX:
        s = rx.sub(" ", s)
    return s


def normalize(name: str) -> str:
    s = _strip_variant(_ascii(name))
    s = s.replace("&", " ").replace("'", "").replace(".", ". ")
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
    """Kaynaklar arası birleştirme anahtarı (altyapı/kadın etiketi dahil)."""
    base = normalize(canonical(name)).replace(" ", "-")
    v = variant(name)
    return f"{base}--{v}" if v else base


def similar(a: str, b: str) -> bool:
    """İki takım adı aynı takım mı? Etiketler eşit olmalı; bulanık eşleşmede hem token_set hem ratio yüksek olmalı."""
    if variant(a) != variant(b):
        return False
    if team_key(a) == team_key(b):
        return True
    na, nb = normalize(canonical(a)), normalize(canonical(b))
    if not na or not nb:
        return False
    return fuzz.token_set_ratio(na, nb) >= 85 and fuzz.ratio(na, nb) >= 72


class TeamMatcher:
    """Belirli bir aday kümesine (ör. o ligin geçmiş verisindeki takımlar) eşleme.
    Adaylar A takımlarıdır; etiketli adlar (U19, kadın, B...) yalnızca aynı etiketli adaylarla eşleşir."""

    def __init__(self, candidates: list[str], threshold: int = 85):
        self.candidates = list(dict.fromkeys(candidates))
        self.threshold = threshold
        self._keys = {team_key(c): c for c in self.candidates}
        self._norm: dict[str, dict[str, str]] = {}
        for c in self.candidates:
            self._norm.setdefault(variant(c), {})[normalize(canonical(c))] = c

    def match(self, name: str) -> str | None:
        k = team_key(name)
        if k in self._keys:
            return self._keys[k]
        pool = self._norm.get(variant(name), {})
        n = normalize(canonical(name))
        if not n or not pool:
            return None
        best = process.extractOne(n, list(pool), scorer=fuzz.token_set_ratio)
        if best and best[1] >= self.threshold and fuzz.ratio(n, best[0]) >= 72:
            return pool[best[0]]
        return None
