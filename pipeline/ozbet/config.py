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
SOURCE_RETRIES = 1          # geçici hata (bağlantı/5xx) alan kaynak aynı çalıştırmada bir kez daha denenir
RETRY_DELAY_S = float(os.environ.get("OZBET_RETRY_DELAY", "20"))
HEALTH_WINDOW_RUNS = 42     # sağlık geçmişi: ~14 gün x 3 çalıştırma
VALUE_EDGE = 0.05          # model_p - ima_p eşiği
DROP_ALARM = 0.07          # oranda %7+ düşüş → alarm
TIME_DECAY_XI = 0.0019     # Dixon-Coles zaman ağırlığı (gün başına) ~ yarı ömür ~365 gün
MIN_TEAM_MATCHES = 6       # bundan az maçı olan takım için "düşük veri"
XG_BLEND = 0.35
DRAW_CALIBRATION = os.environ.get("OZBET_DRAW_CAL", "0") == "1"   # backtest sonucuna göre açılır
# Şut tabanlı güç ağırlığı: λ = (1-w)·λ_gol + w·λ_şut. Backtest ızgarasıyla seçilir (data/backtest.json "shot_blend").
SHOT_BLEND = float(os.environ.get("OZBET_SHOT_BLEND", "0.4"))
# 6 Kasım 2026 backtest (6 lig, 3985 maç): log-loss 0.9885 → 0.9851, Brier 0.5895 → 0.5871, Ü2.5 Brier 0.2459 → 0.2437;
# 6 ligin hepsinde iyileşme, en iyi 0.35–0.5 arası.
# Değer hesabında model ağırlığı: p = α·model + (1-α)·piyasa. Backtest ızgarasıyla seçilir (data/backtest.json "grid").
MODEL_WEIGHT = float(os.environ.get("OZBET_MODEL_WEIGHT", "0.25"))
# 5 Kasım 2026 backtest'i (6 lig, 2 sezon, 3985 maç): Brier model 0.5895, α=0.25 harman 0.5767, kapanış piyasası 0.5732.
# Hiçbir α/eşik kombinasyonu kârlı çıkmadı → en tutucu ayar seçildi.            # xG varsa λ = (1-w)*λ_gol + w*λ_xG

# --- OZBET Tercihi (beklenen değer seçicisi) ---
# Tercih artık "en yüksek olasılık" değil, oran bandı içinde en yüksek beklenen değer (EV = p·oran − 1).
# Bant: 1.60 altı oran asla tercih olmaz (düşük oran kovalamayı keser); 3.50 üstü iddaa'da en pahalı bölge
# (favori–sürpriz yanlılığı, docs/research/roi-piyasa.md S3). Kâr vaadi değildir: iddaa marjı ~%19.
PICK_MIN_ODDS = float(os.environ.get("OZBET_PICK_MIN_ODDS", "1.60"))
PICK_MAX_ODDS = float(os.environ.get("OZBET_PICK_MAX_ODDS", "3.50"))
# En iyi adayın EV'si bunun altındaysa "Pas". −0.06: ortalama marj kaybından (≈ −0.15) belirgin iyi olan seçimler.
PICK_MIN_EV = float(os.environ.get("OZBET_PICK_MIN_EV", "-0.06"))
PICK_MIN_PROB = float(os.environ.get("OZBET_PICK_MIN_PROB", "0.33"))   # bundan düşük olasılıklı market tercih olmaz
# Kombine marketler (MS&A/Ü, MS&KG, KG&A/Ü) aday olsun mu? Harman ağırlığı yalnız 1X2 ve 2.5 A/Ü'de backtest edildi;
# kombinelerde kalibrasyon kanıtı yok (pick_replay'de zayıf göründü) → gerekirse OZBET_PICK_COMBOS=0 ile kapatılır.
PICK_INCLUDE_COMBOS = os.environ.get("OZBET_PICK_COMBOS", "1") == "1"
PICK_EV_TIE = 0.01         # EV farkı bundan küçükse "eşit" sayılır, yüksek olasılıklı aday seçilir
# Değer etiketi eşiği KALİBRE (harmanlanmış) olasılık üzerinden: p_kalibre − ima_p. Eski VALUE_EDGE (0.05) harmanlı
# farka uygulanınca α=0.25'te ham fark ≥ 0.20 gerektiriyor ve MAX_EDGE (0.20) ile çelişiyordu (roi-secim.md §1).
# 0.02 → α=0.25'te ham fark ≥ 0.08; asıl sıkı şart yine gerçek orandan EV > 0.
VALUE_EDGE_CAL = float(os.environ.get("OZBET_VALUE_EDGE_CAL", "0.02"))


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
    "SC1": ("SCO2", "Championship", "İskoçya", (
        "iskoçya championship", "scottish championship", "scotland championship")),
    # "İngiltere 1. Lig"/"2. Lig" belirsiz (Championship de olabilir) → yalnız açık adlar
    "E2": ("ENG3", "League One", "İngiltere", (
        "ingiltere league one", "league one", "efl league one", "england league one")),
    "E3": ("ENG4", "League Two", "İngiltere", (
        "ingiltere league two", "league two", "efl league two", "england league two")),
}
for i, (code, (lid, name, country, al)) in enumerate(EXTRA_FD_LEAGUES.items()):
    lg = League(lid, name, country, 20 + i, fd_code=code, aliases=al)
    LEAGUES.append(lg)
    LEAGUE_BY_ID[lid] = lg

# football-data.co.uk "new leagues" dosyaları (new/{KOD}.csv): tek dosya, tüm sezonlar, YALNIZ en üst lig.
# İY skoru ve şut yok → model ht_share varsayılanıyla ve şut harmanı olmadan çalışır.
# summer=True: takvim yılı sezonu ("2025"); False: "2025/2026".
# Türkçe takma adlar yalnız bültende (Nesine) görülmüş yazımlardır; ikinci kademeler ("Danimarka 1. Lig",
# "Avusturya 2. Lig", "Polonya 1. Lig", "İsviçre Challenge Ligi") bilerek EŞLENMEZ.
NEW_FD_LEAGUES = {
    "AUT": ("AUT1", "Bundesliga", "Avusturya", False, (
        "avusturya bundesliga", "austria bundesliga")),
    "DNK": ("DEN1", "Superliga", "Danimarka", False, (
        "danimarka süper ligi", "denmark superliga")),
    "SWZ": ("SUI1", "Super League", "İsviçre", False, ("switzerland super league",)),
    "POL": ("POL1", "Ekstraklasa", "Polonya", False, ("polonya ekstraklasa", "poland ekstraklasa")),
    "ROU": ("ROU1", "Liga 1", "Romanya", False, ("romanya 1. lig", "romania liga 1")),
    "RUS": ("RUS1", "Premier Lig", "Rusya", False, ("rusya premier lig", "russia premier league")),
    "NOR": ("NOR1", "Eliteserien", "Norveç", True, ("norveç eliteserien", "norway eliteserien")),
    "SWE": ("SWE1", "Allsvenskan", "İsveç", True, ("isveç allsvenskan", "sweden allsvenskan")),
    "FIN": ("FIN1", "Veikkausliiga", "Finlandiya", True, ("finlandiya veikkausliiga", "finland veikkausliiga")),
    "IRL": ("IRL1", "Premier Division", "İrlanda", True, ("ireland premier division",)),
    "USA": ("USA1", "MLS", "ABD", True, ("abd mls", "usa mls", "major league soccer")),
    "BRA": ("BRA1", "Serie A", "Brezilya", True, ("brezilya serie a", "brazil serie a")),
    "ARG": ("ARG1", "Liga Profesional", "Arjantin", True, (
        "arjantin primera lpf", "arjantin primera lpf, kapanış", "arjantin primera lpf, açılış",
        "argentina liga profesional")),
    "MEX": ("MEX1", "Liga MX", "Meksika", False, ("mexico liga mx",)),
    "JPN": ("JPN1", "J1 League", "Japonya", True, ("japan j1 league",)),
    "CHN": ("CHN1", "Super League", "Çin", True, ("china super league",)),
}
for i, (code, (lid, name, country, _summer, al)) in enumerate(NEW_FD_LEAGUES.items()):
    lg = League(lid, name, country, 40 + i, fd_extra=code, aliases=al)
    LEAGUES.append(lg)
    LEAGUE_BY_ID[lid] = lg
SUMMER_FD = {code for code, v in NEW_FD_LEAGUES.items() if v[3]}

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


def summer_years(seasons: list[str]) -> list[int]:
    """season_codes çıktısını takvim yılı sezonlarına çevirir: '2627','2526','2425' → 2027, 2026, 2025, 2024.
    Sezon kodunun başlangıç yılı + (en yeni kod için) bir sonraki yıl; dosyada olmayan yıl zaten boş döner."""
    if not seasons:
        return []
    ys = [2000 + int(s[:2]) for s in seasons]
    return sorted({ys[0] + 1, *ys}, reverse=True)


def summer_label(year: int) -> str:
    """Takvim yılı sezonunu satır 'season' etiketine çevirir (2026 → '2627'), standings ile uyumlu."""
    return f"{year % 100:02d}{(year + 1) % 100:02d}"
