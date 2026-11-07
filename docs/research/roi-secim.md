# Seçim ve kupon stratejisi — ROI araştırması

Betik: `cd pipeline && python -m ozbet.research.selection_eval --fd /home/claude/fd` → `docs/research/selection_eval.json`.
Model değişmedi: haftalık walk-forward Dixon-Coles (son 1100 gün, ξ=0.0019) + piyasa harmanı `p = 0.25·model + 0.75·q`,
q = Pinnacle açılış oranından Shin ile adil olasılık. 10 lig (T1 E0 E1 SP1 I1 D1 F1 N1 P1 B1).

Bölme: geliştirme 2021–2324 (1920 yalnız eğitim), doğrulama 2425, **kilitli test 2526+2627** (bir kez, 3 kural).
Fiyatlar: Max açılış (üst sınır), Avg açılış, **iddaa benzetimi** (adil p → Shin tersi, 1X2/çifte şans %20, 2.5 A/Ü %18).

**Protokolden sapma (açıkça):** football-data'da Pinnacle açılış oranı 2526 sezon ortasından sonra yok (2627'de hiç yok).
İlk koşuda bu maçlar düşünce test n çok küçüktü (≈46). Bu maçlarda adil olasılık Avg açılıştan alınarak yeniden koşuldu.
Kural seçimi yalnız doğrulamaya bağlı olduğundan seçilen 3 kural değişmedi; parametre değişmedi. Sonuçlar iki koşuda da negatif.

## 1. Mevcut site kuralı
`value.py`: ham fark ≤ 0.20 (MAX_EDGE), harman edge ≥ 0.05, EV>0. MODEL_WEIGHT 0.25 iken harman edge = 0.25 × ham fark,
yani edge ≥ 0.05 için ham fark ≥ 0.20 gerekir → MAX_EDGE ile çakışır. **Geliştirme, doğrulama ve testte 0 bahis.**
Sitede "değerli" etiketi pratikte hiç çıkmıyor; bu bir yapılandırma çelişkisidir (düzeltme model/eşik ajanının alanı).

## 2. Seçim filtreleri (527 kural denendi)
Izgara: market grubu (1X2 / çifte şans / 2.5 A/Ü / hepsi) × iddaa oran aralığı (5) × harman edge (0, .01, .02, .03)
× EV(Avg)>0 × model–piyasa uyumu × lig filtresi (geliştirmede en iyi 5 lig). Maç başına en yüksek edge'li tek seçim.
Uygun: geliştirmede n ≥ 300, doğrulamada n ≥ 150 → 250 kural; doğrulama iddaa ROI'sine göre en iyi 3 seçildi.
527 denemede rastlantısal "kazanan" beklenir — doğrulamada en iyiler bile iddaa fiyatıyla negatifti.

| Kural | Doğrulama n / isabet / ROI iddaa | **Test** n | isabet | ROI Max | ROI Avg | **ROI iddaa** [%95 GA] | CLV |
|---|---|---|---|---|---|---|---|
| 1X2, EV(Avg)>0, uyum, lig B1 SP1 T1 E1 I1 | 199 / %52.8 / −5.2% | 103 | %41.7 | −3.8% | −9.0% | **−17.8%** [−37.4, +1.3] | −0.9% |
| aynısı, edge ≥ 0.01 | 197 / %52.3 / −6.0% | 101 | %41.6 | −5.8% | −8.9% | **−17.6%** [−36.7, +2.2] | −0.9% |
| 1X2, iddaa oranı < 1.60, lig B1 P1 T1 E0 I1 | 210 / %69.5 / −6.6% | 233 | %67.0 | −1.8% | −5.4% | **−11.9%** [−19.9, −3.7] | −0.1% |

İlk iki kural n < 150 → güvenilmez. En kötü sezon 2526 (−19.6% / −19.3% / −14.4%). Lig kırılımında pozitif lig yok.
**Kilitli testte üstün çıkan kural yok**, bu yüzden `value.py`/`commentator.py`'ye bayrak eklenmedi.
Not: Max fiyatta geliştirme/doğrulamada küçük artılar (+1…+7%) testte sıfırın altına indi; CLV negatif → gerçek bir üstünlük işareti yok.

## 3. Yüksek isabet modu (maç başına en olası seçim, harman p ≥ eşik — çoğu çifte şans)

| p eşiği | Doğr. n / isabet / ROI iddaa | Test n | isabet | ROI Max | ROI Avg | ROI iddaa | ort. iddaa oranı |
|---|---|---|---|---|---|---|---|
| ≥ 0.60 | 3487 / %79.1 / −9.8% | 4308 | %77.7 | −1.3% | −4.6% | −10.4% | 1.17 |
| ≥ 0.70 | 2655 / %82.5 / −9.2% | 3133 | %81.3 | −1.3% | −4.5% | −10.0% | 1.12 |
| ≥ 0.80 | 1292 / %88.8 / −8.1% | 1376 | %88.5 | −0.3% | −3.6% | −8.6% | 1.04 |
| ≥ 0.85 | 706 / %92.5 / −7.5% | 753 | %91.6 | −0.4% | −3.8% | −8.4% | 1.00 |

İsabet %92'ye çıksa da ROI iddaa fiyatıyla −%8…−%10 arasında kalır: isabet yükseldikçe oran da düşer, marj aynı kalır.
p ≥ 0.85 seçimlerinin iddaa benzeri oranı ≈ 1.00 — oynanabilir bile değil.

## 4. Kombine (iddaa'da marjlar çarpılır)
Teorik beklenen ROI = (1/(1+m))ⁿ − 1:

| marj | tekli | 2'li | 3'lü | 4'lü | 5'li |
|---|---|---|---|---|---|
| %20 (iddaa 1X2) | −16.7% | −30.6% | −42.1% | −51.8% | −59.8% |
| %18 (iddaa A/Ü) | −15.3% | −28.2% | −39.1% | −48.4% | −56.3% |
| %5 (iyi büro) | −4.8% | −9.3% | −13.6% | −17.7% | −21.7% |

Ampirik (kilitli test, aynı gün farklı maçlardan rastgele kombine, p ≥ 0.70 havuzu, iddaa fiyatı):
tekli n=3133 isabet %80.5 ROI −9.7% · 2'li n=1495 isabet %64.1 ROI −19.3% · 3'lü n=955 isabet %52.2 ROI −26.2%.
MBS: football-data'da MBS yok; MBS 2/3 olan maç tekli oynanamaz, kombineye zorlar → yukarıdaki tablo kadar ek kayıp.
Öneri: MBS 1 maçlarda tekli; kombine zorunluysa en az bacak.

## 5. Stake (kilitli test, en iyi kuralın 103 seçimi, başlangıç 100 birim, 1000 bootstrap yol)
- iddaa fiyatı: düz 1 birim → son 81.6 (max düşüş %25, yarıyı kaybetme olasılığı %0.1). **1/4 Kelly hiç bahis açmadı**:
  harman olasılıkla iddaa fiyatında EV hep negatif, Kelly payı 0. Bu doğru davranış — Kelly "oynama" diyor.
- Max fiyat (üst sınır): düz → 96.1 (max düşüş %18.6); 1/4 Kelly (tek bahis ≤ %5) → 101.1 (max düşüş %16), iflas olasılığı ≈ 0.
  Kelly yalnız gerçekten pozitif EV varsa işe yarar; burada sonuç gürültü düzeyinde.

## Sonuç
Seçim filtresi, lig seçimi, uyum şartı veya "yüksek isabet" modu iddaa benzeri fiyatla kilitli testte ROI'yi pozitife çıkarmadı
(en iyi: −%8…−%12). Kazanma yüzdesi yükseltilebilir (%90+), ROI yükseltilemez; asıl kayıp kaynağı ~%20 marj ve kombinede çarpılması.
Sitede kupon asistanına ve karneye "kombine marj etkisi" uyarısı/hesabı eklendi.
