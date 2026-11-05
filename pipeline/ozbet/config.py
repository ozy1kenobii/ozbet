"""Merkezi yapılandırma: ligler, eşikler, yollar."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=3), name="Europe/Istanbul")  # Türkiye sabit UTC+3

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("OZBET_DATA_DIR", ROOT / "data"))
CACHE_DIR = Path(os.environ.get("OZBET_CACHE_DIR", ROOT / ".cache"))

USER_AGENT = os.environ.get(
    "OZBET_USER_AGENT",
    "Mozilla/5.0 (compatible; OZBET-bot/0.1; personal non-commercial stats project)",
)
REQUEST_DELAY_S = float(os.environ.get("OZBET_DELAY", "2.5"))  # aynı alan adına istekler arası
REQUEST_TIMEOUT_S = 25

MC_SIMS = 10_000
VALUE_EDGE = 0.05          # model_p - ima_p eşiği
DROP_ALARM = 0.07          # oranda %7+ düşüş → alarm
TIME_DECAY_XI = 0.0019     # Dixon-Coles zaman ağırlığı (gün başına) ~ yarı ömür ~365 gün
MIN_TEAM_MATCHES = 6       # bundan az maçı olan takım için "düşük veri"
XG_BLEND = 0.35
# Değer hesabında model ağırlığı: p = α·model + (1-α)·piyasa. Backtest ızgarasıyla seçilir (data/backtest.json "grid").
MODEL_WEIGHT = float(os.environ.get("OZBET_MODEL_WEIGHT", "0.25"))
# 5 Kasım 2026 backtest'i (6 lig, 2 sezon, 3985 maç): Brier model 0.5895, α=0.25 harman 0.5767, kapanış piyasası 0.5732.
# Hiçbir α/eşik kombinasyonu kârlı çıkmadı → en tutucu ayar seçildi.            # xG varsa λ = (1-w)*λ_gol + w*λ_xG


@dataclass(frozen=True)
class League:
    id: str
    name: str
    country: str
    priority: int
    fd_code: str | None = None          # football-data.co.uk ana lig kodu
    fd_extra: str | None = None         # football-data.co.uk "new" lig dosyası (ülke kodu)
    understat: str | None = None        # understat lig adı
    soccerstats: str | None = None      # soccerstats league= parametresi
    aliases: tuple[str, ...] = field(default_factory=tuple)  # bülten/kaynak lig adları
    cup: bool = False


LEAGUES: list[League] = [
    League("TR1", "Süper Lig", "Türkiye", 1, fd_code="T1", soccerstats="turkey",
           aliases=("türkiye süper lig", "turkey super lig", "süper lig", "trendyol süper lig", "tur süper lig")),
    League("TR2", "1. Lig", "Türkiye", 2, soccerstats="turkey2",
           aliases=("türkiye 1. lig", "turkey 1. lig", "1. lig", "trendyol 1. lig", "tff 1. lig")),
    League("ENG1", "Premier Lig", "İngiltere", 3, fd_code="E0", understat="EPL", soccerstats="england",
           aliases=("ingiltere premier lig", "premier league", "england premier league", "premier lig")),
    League("ESP1", "La Liga", "İspanya", 4, fd_code="SP1", understat="La_liga", soccerstats="spain",
           aliases=("ispanya la liga", "laliga", "la liga", "spain laliga", "ispanya laliga")),
    League("ITA1", "Serie A", "İtalya", 5, fd_code="I1", understat="Serie_A", soccerstats="italy",
           aliases=("italya serie a", "serie a", "italy serie a")),
    League("GER1", "Bundesliga", "Almanya", 6, fd_code="D1", understat="Bundesliga", soccerstats="germany",
           aliases=("almanya bundesliga", "bundesliga", "germany bundesliga")),
    League("FRA1", "Ligue 1", "Fransa", 7, fd_code="F1", understat="Ligue_1", soccerstats="france",
           aliases=("fransa ligue 1", "ligue 1", "france ligue 1")),
    League("UCL", "Şampiyonlar Ligi", "Avrupa", 8, cup=True,
           aliases=("uefa şampiyonlar ligi", "şampiyonlar ligi", "champions league", "uefa champions league")),
    League("UEL", "Avrupa Ligi", "Avrupa", 9, cup=True,
           aliases=("uefa avrupa ligi", "avrupa ligi", "europa league", "uefa europa league")),
    League("UECL", "Konferans Ligi", "Avrupa", 10, cup=True,
           aliases=("uefa konferans ligi", "konferans ligi", "conference league", "uefa europa conference league")),
]
LEAGUE_BY_ID = {lg.id: lg for lg in LEAGUES}

# Ek (opsiyonel) ligler: bültende varsa ve football-data.co.uk'ta geçmiş verisi varsa modellenir.
EXTRA_FD_LEAGUES = {
    # Takma adlar: Nesine "Ülke Lig" (ör. "Romanya 2. Lig", "Fransa Ulusal Lig"), iddaa.com "ülke + yarışma adı".
    # Rakamlı yazımlar yalnızca aynı rakamla eşleşir (league_for); "Portekiz 2. Lig" POR1'e asla düşmez.
    # Belirsiz yazımlar (ör. "Hollanda 1. Lig" = Eerste Divisie olabilir, "İngiltere 1. Lig" = League One olabilir) bilerek yok.
    "E1": ("ENG2", "Championship", "İngiltere", (
        "ingiltere championship", "championship", "ingiltere şampiyonluk ligi", "ingiltere championship ligi",
        "efl championship", "ingiltere efl championship", "england championship")),
    "D2": ("GER2", "2. Bundesliga", "Almanya", (
        "almanya 2. bundesliga", "2. bundesliga", "almanya bundesliga 2", "germany 2. bundesliga")),
    "I2": ("ITA2", "Serie B", "İtalya", ("italya serie b", "serie b", "italy serie b")),
    "SP2": ("ESP2", "La Liga 2", "İspanya", (
        "ispanya la liga 2", "segunda división", "laliga2", "ispanya laliga 2", "ispanya 2. lig",
        "ispanya segunda", "ispanya segunda división", "ispanya laliga hypermotion", "spain segunda división")),
    "F2": ("FRA2", "Ligue 2", "Fransa", ("fransa ligue 2", "ligue 2", "fransa 2. lig", "france ligue 2")),
    "N1": ("NED1", "Eredivisie", "Hollanda", (
        "hollanda eredivisie", "eredivisie", "netherlands eredivisie", "hollanda eredivisie ligi")),
    "P1": ("POR1", "Liga Portugal", "Portekiz", (
        "portekiz liga portugal", "liga portugal", "primeira liga", "portekiz süper lig", "portekiz 1. lig",
        "portekiz premier lig", "portekiz primeira liga", "portekiz liga portugal betclic", "liga portugal betclic",
        "portugal liga portugal")),
    "B1": ("BEL1", "Pro League", "Belçika", (
        "belçika pro league", "jupiler pro league", "pro league", "belçika pro lig", "belçika 1. lig",
        "belçika birinci lig a", "belçika jupiler pro lig", "belçika jupiler lig", "belçika jupiler pro league", "belgium pro league",
        "belçika first division a")),
    "SC0": ("SCO1", "Premiership", "İskoçya", (
        "iskoçya premiership", "scottish premiership", "iskoçya premier lig", "iskoçya premier ligi",
        "scotland premiership")),
    "G1": ("GRE1", "Super League", "Yunanistan", (
        "yunanistan süper lig", "greece super league", "yunanistan süper ligi", "yunanistan super league",
        "yunanistan super league 1", "greece super league 1")),
}
for i, (code, (lid, name, country, al)) in enumerate(EXTRA_FD_LEAGUES.items()):
    lg = League(lid, name, country, 20 + i, fd_code=code, aliases=al)
    LEAGUES.append(lg)
    LEAGUE_BY_ID[lid] = lg

# ClubElo (lig-arası Elo düzeltmesi)
ELO_HFA = 63.0             # iç saha avantajı (Elo puanı); clubelo.com ülkeye göre ~50-80 arası kullanır
ELO_DEFAULT_TOTAL = 2.6    # lig modeli olmayan iki takım için varsayılan toplam gol beklentisi
# Birikimli sonuç arşivi (data/archive/results-{LIG}.json): tek başına modele girmesi için gereken en az maç
ARCHIVE_MIN_MATCHES = 60

LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
FOOTBALL_DATA_ORG_KEY = os.environ.get("FOOTBALL_DATA_ORG_KEY")


def season_codes(today) -> list[str]:
    """football-data.co.uk sezon kodları: içinde bulunulan + önceki 2 sezon (ör. '2627','2526','2425')."""
    start = today.year if today.month >= 7 else today.year - 1
    out = []
    for k in range(3):
        y = start - k
        out.append(f"{y % 100:02d}{(y + 1) % 100:02d}")
    return out
