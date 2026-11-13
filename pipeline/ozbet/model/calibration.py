"""Kalibre olasılık: tercih ve değer hesabında kullanılacak TEK olasılık.

Neden: canlı karnede model her kategoride piyasadan kötü (log-loss: ms 0.5967/0.5838, gol 0.6251/0.6108,
takım 0.6866/0.6452); modelin piyasadan yukarı saptığı yerde gerçekleşen oran piyasanın da altında kalıyor.
Araştırma (docs/research/roi-model.md): doğrusal harmanda model ağırlığı küçüldükçe sonuç iyileşiyor
(0.25 → 0.1 → 0), Dixon-Coles piyasaya bilgi eklemiyor.

Tasarım (üç adım, hepsi logit uzayında):
  1. Aile bazında model ağırlığı w (FAMILY_WEIGHT): logit(p) = logit(q) + w · g(d),  d = logit(model) − logit(piyasa).
  2. Seçim yanlılığı büzmesi (kazananın laneti): seçici çok sayıda gürültülü tahminin en büyüğünü aldığı için
     modelin piyasadan YUKARI sapması sistematik olarak şişkindir. d > 0 iken g(d) = T·tanh(d/T) ile doyurulur
     (küçük fark ≈ aynen, büyük fark en çok T). d ≤ 0 iken g(d) = d (aşağı sapma kısılmaz → tutucu taraf).
  3. Piyasa yoksa (implied None) model, marketin taban oranına doğru büzülür (NO_MARKET_KEEP).

Ağırlıklar veriye UYDURULMADI: araştırma öncüllerinden seçilmiş tutucu sabitlerdir; birkaç günlük canlı örnek yalnız
akıl sağlığı kontrolüdür (docs/research/kalibrasyon.md, research/calibration_eval.py).
Saf fonksiyonlar; import sırasında G/Ç yok.
"""
from __future__ import annotations

import math

# Çıktı sınırları
P_MIN, P_MAX = 0.01, 0.99
_EPS = 1e-6

# Aile bazında model ağırlığı (logit uzayı). Üretimdeki doğrusal harman 0.25 idi; araştırma "daha düşük daha iyi" diyor.
#   ms    : 1X2 / çifte şans / handikap — modelin en çok sınandığı yer, yine de piyasa önde → 0.15
#   gol   : toplam gol (Alt/Üst, gol aralığı, tek/çift) — piyasa-tabanlı λ toplam gol dağılımında modelden iyi → 0.10
#   kg    : KG Var/Yok — piyasa-model.md'de piyasa önde, canlıda log-loss farkı büyük (0.6998 / 0.6746); tercihlerin çoğu burada → 0.05
#   takim : takım golü — piyasa ile en büyük log-loss farkı (0.6866 / 0.6452) → 0.05
#   yari  : ilk yarı / ikinci yarı / İY-MS — fark en küçük (0.4887 / 0.4851) → 0.15
#   kombi : MS&A/Ü, MS&KG, KG&A/Ü — iki marketin hatası çarpılır → 0.10
#   diger : korner/kart vb. deneysel → 0.10
FAMILY_WEIGHT: dict[str, float] = {
    "ms": 0.15, "gol": 0.10, "kg": 0.05, "takim": 0.05, "yari": 0.15, "kombi": 0.10, "diger": 0.10,
}

# Seçim yanlılığı: modelin piyasadan yukarı logit farkı en çok bu kadar sayılır (0.5 logit ≈ p=0.5 civarında 12 puan).
EXCESS_CAP = 0.5

# Lig bazında ağırlık çarpanı (kanıt birikince doldurulur; şimdilik boş = hepsi 1.0).
LEAGUE_FACTOR: dict[str, float] = {}

# Piyasa olasılığı yokken: modelin taban orana göre logit farkının korunan payı.
NO_MARKET_KEEP = 0.6

# Uzun dönem taban oranlar (Avrupa ligleri kaba ortalaması). Listede olmayan markette taban bilinmez:
# p ≤ 0.5 ise dokunulmaz, p > 0.5 ise 0.5'e doğru büzülür (yalnız aşırı güven kırpılır).
BASE_RATE: dict[str, float] = {
    "1": 0.44, "X": 0.26, "2": 0.30, "1X": 0.70, "X2": 0.56, "12": 0.74,
    "O1.5": 0.75, "U1.5": 0.25, "O2.5": 0.51, "U2.5": 0.49, "O3.5": 0.29, "U3.5": 0.71,
    "BTTS_Y": 0.52, "BTTS_N": 0.48,
}

_HALF_PREFIX = ("HT_", "2H_", "MGH_", "HTFT_", "BOTH_HALVES")
_TEAM_PREFIX = ("H_", "A_")
_GOAL_PREFIX = ("O", "U", "G")
_OTHER_PREFIX = ("C_", "K_", "CR_", "KR_")


def family(market: str) -> str:
    """Market anahtarı → aile (ms | gol | kg | takim | yari | kombi | diger)."""
    k = market or ""
    if k.startswith(_OTHER_PREFIX):
        return "diger"
    if "&" in k:
        return "kombi"
    if k.startswith(_HALF_PREFIX) or k.endswith("_WIN_HALF") or (len(k) == 3 and k[1] == "/"):
        return "yari"          # çıplak "1/X" İY/MS anahtarları da buraya
    if k.startswith("BTTS"):
        return "kg"
    if k.startswith(_TEAM_PREFIX):
        return "takim"
    if k in ("1", "X", "2", "1X", "X2", "12") or k.startswith("HCP"):
        return "ms"
    if k in ("ODD", "EVEN") or (k.startswith(_GOAL_PREFIX) and any(c.isdigit() for c in k)):
        return "gol"
    return "diger"


def _logit(p: float) -> float:
    p = min(1 - _EPS, max(_EPS, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    e = math.exp(x)
    return e / (1 + e)


def _clip(p: float) -> float:
    return min(P_MAX, max(P_MIN, p))


def _valid(p) -> bool:
    return isinstance(p, (int, float)) and not isinstance(p, bool) and p == p and 0.0 < p < 1.0


def shrink_excess(d: float) -> float:
    """Seçim yanlılığı büzmesi: yukarı sapma doyurulur, aşağı sapma aynen kalır. Monoton, d=0'da sürekli."""
    return EXCESS_CAP * math.tanh(d / EXCESS_CAP) if d > 0 else d


def model_weight(market: str, league: str | None = None) -> float:
    """Marketin (ve varsa ligin) logit uzayındaki model ağırlığı, [0, 0.5] aralığına kırpılır."""
    w = FAMILY_WEIGHT.get(family(market), FAMILY_WEIGHT["diger"])
    if league:
        w *= LEAGUE_FACTOR.get(league, 1.0)
    return min(0.5, max(0.0, w))


def calibrated_prob(market: str, model_p: float, implied_p: float | None, league: str | None = None) -> float:
    """Tercih ve değer için tek olasılık. model_p: ham model; implied_p: marjı temizlenmiş piyasa (yoksa None).
    Her iki girdide monoton artan; çıktı (0.01, 0.99) aralığında."""
    mp = min(1 - _EPS, max(_EPS, float(model_p)))
    if not _valid(implied_p):
        # Piyasa yok: taban orana doğru büz
        base = BASE_RATE.get(market)
        if base is None:
            if mp <= 0.5:
                return _clip(mp)
            base = 0.5
        lb = _logit(base)
        return _clip(_sigmoid(lb + NO_MARKET_KEEP * (_logit(mp) - lb)))
    lq = _logit(float(implied_p))
    d = _logit(mp) - lq
    return _clip(_sigmoid(lq + model_weight(market, league) * shrink_excess(d)))


def calibrated_group(probs: dict, implied: dict | None, keys: list[str], league: str | None = None) -> dict:
    """Birbirini dışlayan grup (1/X/2, 2.5 Üst/Alt, KG Var/Yok) için kalibre olasılıklar, toplamı 1 olacak şekilde.
    probs'ta olmayan anahtar atlanır; hiçbiri yoksa boş sözlük döner."""
    implied = implied or {}
    raw = {k: calibrated_prob(k, probs[k], implied.get(k), league) for k in keys if probs.get(k) is not None}
    s = sum(raw.values())
    if not raw or s <= 0:
        return {}
    return {k: v / s for k, v in raw.items()}
