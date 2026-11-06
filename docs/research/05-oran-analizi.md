# 05 — Oran Analizi: Yöntemler, Literatür ve OZBET Tasarımı (Ajan 5)

Etiketler: **[Y]** kaynakta doğrulandı · **[O]** kaynakta var ama bu oturumda tam metin doğrulanamadı · **[D]** benim tasarım önerim veya aritmetiğim. Tarih: 6 Kasım 2026.
Türk sitelerinin vitrin incelemesi başka ajanda. Bu belge yöntemi, doğrulanabilirliği ve bizim veriyle nasıl test edileceğini ele alıyor.

---

## 0. Kısa sonuç

1. "Benzer oranlı geçmiş maçlar" tablosu yeni bir bilgi üretmez. Ölçtüğü şey, **piyasanın o olasılık bölgesindeki kalibrasyonudur**: ima olasılık ile gerçekleşen frekans arasındaki fark. Bu fark da büyük ölçüde favori-sürpriz yanlılığıdır (FLB). Dürüst sunum, "geçmişte %X kazandı" demek değil, **"piyasa ima olasılığı ile geçmiş frekans arasındaki fark, güven aralığıyla birlikte"** göstermektir [D].
2. Eşleşme ham oranla değil, **marjı temizlenmiş olasılık uzayında** yapılmalı. iddaa marjı (~%19–23, bkz. DEEP_RESEARCH §0) ile football-data Avg marjı (~%7) aynı ham oranı çok farklı olasılıklara çevirir [Y/D].
3. Oran hareketinin bilgi değeri literatürde var, ama **hareketin kendisi kapanış oranına zaten yansır**. Hareketten kâr ancak hareket *tamamlanmadan* daha iyi bir fiyattan oynanırsa mümkündür. Bu yüzden düşen oran alarmının ölçütü "isabet oranı" değil, **CLV**'dir [Y: Kaunitz vd.; D].
4. iddaa marjı yüksek olduğundan bu analizlerin çoğu "değer bulma" değil, **bilgi/şeffaflık** özelliği olarak sunulmalı [D].

---

## 1. "Benzer oranlı geçmiş maçlar" yöntemi

### 1.1 Gerçekte neyi ölçer?
- Oranlar zaten bir olasılık tahminidir. Aynı oranlı 500 maçta ev sahibi %48 kazandıysa ve marjı temizlenmiş ima olasılık %47 ise, tablo bize yalnızca "piyasa bu bölgede iyi kalibre" bilgisini verir. Maça özgü hiçbir şey söylemez [D].
- Tablonun tek sistematik içeriği **FLB**'dir. Whelan (UCD WP23/16), **football-data.co.uk kapanış Avg oranlarıyla** (84.230 maç, 22 lig, 2011/12–2021/22) en düşük olasılık dilimindeki bahislerin 1 birimde ~0,83 döndürdüğünü (−%17), en yüksek dilimin ise yaklaşık −%2 kaybettiğini buldu. Ortalama overround %6,9 [Y] ([Whelan 2023](https://www.ucd.ie/economics/t4media/WP23_16.pdf)). Aynı yazar bunu içeriden bilgiye değil, bahisçi görüş ayrılığı ile bahisçinin pazar gücüne bağlıyor [Y] (aynı kaynak). Ders notu: [Whelan, Efficiencies and FLB](https://www.karlwhelan.com/Teaching/BettingMarkets/10.EfficienciesandFavourite-LongshotBias.pdf) [O].
- FLB yüzünden **orantısal marj temizliği** (bizim `market.implied`) sürprizlerin olasılığını sistematik olarak fazla gösterir. Shin yöntemi bu yanlılığı modelleyerek dağıtır. Štrumbelj'in karşılaştırması "On determining probability forecasts from betting odds" (IJF) Shin'in basit normalizasyondan daha iyi olasılık verdiğini raporluyor [O] ([EconBiz kaydı](https://econbiz.de/Record/on-determining-probability-forecasts-from-betting-odds-%C5%A1trumbelj-erik/10010517776)). Python uygulaması: [mberk/shin](https://www.github.com/mberk/shin) [Y, depo var]. Yöntemler arası karşılaştırma ve R paketi: [implied paketi](https://www.r-bloggers.com/the-probabilities-implied-by-bookmaker-odds-introducing-the-implied-package/) [O].
- Ek kaynak: oran-tek başına modellerin GLM'lerle karşılaştırması ([arXiv 2604.17194](https://arxiv.org/pdf/2604.17194)) [O]. DEEP_RESEARCH §0'daki Serie A çalışması: piyasa Brier'ı DC'den iyi, harmanda modele ağırlık 0 ([arXiv 2608.11505](https://arxiv.org/abs/2608.11505)) [Y, DEEP_RESEARCH'ten].

**Sonuç:** Yöntemin dürüst hali şudur: *"Piyasanın bu olasılık bölgesinde geçmişte ne kadar isabetli olduğunu"* göstermek. Gösterilecek büyüklük sapmadır, `Δ = frekans − ima_p`, Wilson aralığıyla birlikte. Aralık 0'ı içeriyorsa etiket "piyasa ile uyumlu" olur [D].

### 1.2 Marj farkı → olasılık uzayında eşleşme
- Ham oran eşleşmesi yanlıştır. Örnek [D, aritmetik]: iddaa 1=2,00 / X=3,10 / 2=3,30 için Σ1/o ≈ 1,126 olur, orantısal p1 ≈ 0,444. Football-data'da Avg 1=2,00 olan bir maçta (overround ~%6) p1 ≈ 0,47. Aynı "2,00" iki farklı olasılık demek.
- Kural [D]: her iki tarafta da aynı yöntemle (önerim **Shin**, yedek: orantısal) `(pH, pD, pA)` hesapla. Eşleşmeyi bu üçlü üzerinde yap. Σ=1 olduğu için 2 boyutlu bir uzay yeter: `(pH, pA)`.
- iddaa'nın yüksek marjı Shin'de büyük bir z (içeriden bilgi payı) üretir. Shin'in varsayımı (marjın bilgi asimetrisinden doğduğu) iddaa gibi tekel ve yasal tavanlı bir fiyatlamada tam oturmayabilir [D]. Bu yüzden iki yöntemin farkı `method_spread` olarak çıktıya yazılsın. Fark 2 puanı geçerse kullanıcıya "olasılık dönüşümü belirsiz" denilsin.
- Referans uzayı **PSC (Pinnacle kapanış)** olmalı, AvgC değil. Pinnacle marjı ~%2, FLB etkisi daha küçük [Y marj: [Pinnacle destek](https://pinnaclesports.freshdesk.com/support/solutions/articles/1000189654-how-do-i-calculate-betting-margins-)]. PSC yoksa AvgC kullanılsın. `_odds_from_row` şu an Avg'yi öncelikli seçiyor. Benzerlik modülü PS/PSC'yi ayrı okumalı [Y, kod okuması].

### 1.3 Tolerans ve örneklem
- Sabit tolerans (ör. "oran ±0,05") düşük oranda dar, yüksek oranda geniş kalır. Olasılık uzayında **k-en yakın komşu** daha dengelidir [D]:
  - Mesafe: `d = sqrt((pH−pH*)² + (pA−pA*)²)`.
  - Hedef: `k = 400`. Üst sınır: `d ≤ 0,03`. 400'e ulaşılamazsa elde edilen n raporlanır.
  - Ağırlık: üçgen çekirdek `w = 1 − d/d_max`. Wilson için etkin örneklem `n_eff = (Σw)²/Σw²` kullanılır.
- Örneklem büyüklüğü [D, aritmetik; Wilson aralık yarı genişliği ≈ 1,96·sqrt(p(1−p)/n), p=0,45]:

| n | ±yarı genişlik | Uyarı |
|---|---|---|
| 50 | ~13,8 puan | "Çok az örnek, gösterme" |
| 100 | ~9,8 | "Düşük güven" |
| 200 | ~6,9 | "Orta" |
| 400 | ~4,9 | Varsayılan hedef |
| 1000 | ~3,1 | İyi |

  Piyasa sapmaları (FLB) birkaç puan düzeyindedir (Whelan'da en uç dilimde bile getiri farkı %15, olasılık farkı birkaç puan). Bu yüzden **n<400 ile anlamlı bir sapma tespiti neredeyse imkânsız**. Kullanıcıya bunu açıkça söylemek gerekir [D].
- Wilson aralığı: Wald yerine Wilson tercih edilir. Küçük n ve uç p'de kapsama oranı çok daha iyidir [Y] ([Brown, Cai, DasGupta 2001](https://projecteuclid.org/download/pdf_1/euclid.ss/1009213286); [Agresti & Coull 1998](https://math.unm.edu/~james/Agresti1998.pdf)). 1/X/2 üç sonuçlu olduğundan her sonuç için ayrı bir Wilson aralığı verilir. Aralıklar eşzamanlı değildir; bu not edilmeli [D].

### 1.4 Lig ve sezon etkisi
- İç saha avantajı ve beraberlik oranı ligden lige değişir. COVID'li seyircisiz sezonlarda (2020/21) iç saha avantajının düştüğü genel olarak bilinir; bu oturumda kaynak doğrulanmadı [O].
- Öneri [D]:
  1. Havuz önceliği şöyle olsun: aynı lig → aynı "lig ailesi" (ör. 2. ligler) → tüm ligler. Hangi düzeyin kullanıldığı `pool` alanına yazılsın.
  2. Sezon ağırlığı DC ile aynı olsun: `exp(−ξ·gün)`, ξ=0,0019.
  3. 2020/21 ayrı bayrakla işaretlensin; varsayılan olarak ağırlığı 0,5.
  4. Çıktıda havuzun beraberlik ve iç saha oranı ile o ligin genel oranı yan yana gösterilsin.

### 1.5 Ü/A ve KG dağılımı
- Ü/A 2,5 için ayrı bir eşleşme yapılır. Eşleşme marjı temizlenmiş `p_over` (football-data `PC>2.5`/`AvgC>2.5`) üzerinden, 1 boyutlu olarak ±0,02 aralığında yapılır. Sonuç FTHG+FTAG'den hesaplanır [D].
- KG (karşılıklı gol): football-data'da KG oranı yoktur. Kodumuzda bu sütun okunmuyor ve bilinen CSV şemasında da bulunmuyor [Y, kod; O şema]. Sonuç ise skordan hesaplanabilir (FTHG>0 ve FTAG>0). Bu yüzden KG frekansı **1X2+Ü/A komşuluğunun** sonucu olarak raporlanır, KG oranıyla eşleşme yapılmaz. iddaa'nın KG oranıyla karşılaştırma bölüm 3'teki λ tutarlılığıyla yapılır [D].
- Ek dağılım: aynı komşuluktan en sık 5 skor (ilgi çekici, ama n=400'de tek skor frekansı ~±3 puan belirsizdir) [D].

---

## 2. Oran hareketi

### 2.1 Literatür
- **Kaunitz, Zhong, Kreiner (2017):** Bahisçilerin ortalama oranından konsensüs olasılığı hesaplanıyor ve α≈0,05 marj payı düşülüyor. Herhangi bir bahisçinin en yüksek oranı bu adil değerin üstündeyse bahis oynanıyor. Kapanış verisinde (479.440 maç) %3,5 getiri, **maçtan 1–5 saat önceki hareket verisinde %9,9** elde edilmiş. Gerçek parayla %8,5; birleşik sonuç p=0,089 ile ancak sınırda anlamlı. Hesaplar kısa sürede limitlenmiş [Y] ([arXiv 1710.02824](https://arxiv.org/abs/1710.02824)).
  → Ders: değer, **konsensüs ile geride kalan bahisçi arasındaki gecikmede**. iddaa günde birkaç kez güncellenen merkezi bir fiyat. Pinnacle'a göre gecikmeli olup olmadığı **bizim veriyle ölçülebilir** (§2.3-C).
- **Simon (2024, Management Science):** 3.681 MLB maçı, 4 bahisçi, açılış→kapanış. Tahminler çoğunlukla güvenilir. Yine de zayıf form verimlilik reddediliyor: hareketler **aşırı tepki** gösteriyor (negatif otokorelasyon) ve kapanış her zaman daha isabetli değil [Y] ([IDEAS/RePEc](https://ideas.repec.org/a/inm/ormnsc/v70y2024i12p8583-8611.html)). Futbol değil; aktarım bir hipotezdir [D].
- **Whelan (2023):** İçeriden bilginin oranlara etkisini ve FLB'yi futbolda inceliyor [Y] ([WP23/16](https://www.ucd.ie/economics/t4media/WP23_16.pdf)).
- **CLV:** Pinnacle ve J. Buchdahl yazıları "kapanış oranını yenmek uzun vadeli başarının en iyi göstergesidir" savını yayıyor. Pinnacle'ın özgün makalesine bu oturumda erişilemedi; aramada yalnızca üçüncü taraf özetler çıktı [O]. Akademik dayanağı dolaylıdır: kapanış oranının en iyi olasılık tahmini olması (DEEP_RESEARCH §0: piyasa Brier < DC). Eğer kapanış adil olasılığa en yakın tahminse, ondan iyi fiyat alan bahis beklentide pozitiftir [D, mantıksal çıkarım]. Kaunitz vd. de stratejilerini fiilen bu mantıkla kurmuş.
- **"Sharp vs soft" (Trademate, RebelBetting):** Keskin bir bahisçinin (Pinnacle) marjı temizlenmiş oranı "adil" kabul ediliyor; yumuşak bahisçide bunun üstünde kalan oran "değer" sayılıyor. Bu, Kaunitz yöntemiyle aynı iskelet. Ürünlerin kendi sayfaları bu oturumda doğrulanmadı [O]. OddsPortal "dropping odds" sayfası eşik veya zaman penceresi tanımı vermiyor [Y] ([OddsPortal](https://www.oddsportal.com/dropping-odds/)). Ayrıca OddsPortal otomatik çekmeyi yasaklıyor (DEEP_RESEARCH §4.4).

### 2.2 Düşen oran alarmının tahmin gücü — ne beklemeli?
- Mevcut `movement()` ham oran oranı kullanıyor: `v/f − 1 ≤ −DROP_ALARM`. Sorunlar [Y kod / D]:
  1. Marj değişimi bütün oranları birlikte oynatabilir. Hareket **marjı temizlenmiş olasılıkta** ölçülmeli: `Δp = p_son − p_ilk`.
  2. 1'de düşüş, 2'de mekanik bir yükseliş demektir. Bunlar ayrı alarmlar sayılmamalı.
  3. "İlk görülen" anlık görüntü günden güne değişir (08:30 / 13:30 / 18:30). Zaman damgası (`t`) ve maça kalan süre kaydedilmeli.
- Beklenti [D]: Düşen tarafın kazanma frekansı yükselir; ama **kapanış ima olasılığına** göre fazlası olmamalı. Alarmın kullanıcıya faydası "tahmin" değil, "bahis yapılacaksa daha erken, daha iyi fiyat" bilgisidir. Ancak iddaa kullanıcısı zaten iddaa'nın *güncel* fiyatını görüyor. Alarm geldiğinde fiyat çoktan düşmüş oluyor.

### 2.3 Backtest planı (football-data: PS→PSC, Avg→AvgC, Max→MaxC)
**Veri:** 12.000+ maç; açılış ve kapanış sütunları (PSH/PSD/PSA, PSCH/…, AvgH/…, AvgCH/…, >2.5/<2.5 karşılıkları). Not: football-data'nın açılış oranı, maç haftasının belirli bir anında toplanıyor; kapanış sütunları ise 2019/20 civarında eklendi. Bu bilgi sitenin notes.txt dosyasından doğrulanmalı [O].

**A. Hareket bilgi taşıyor mu?** (açılış vs kapanış kalibrasyonu)
- Her maç için Shin ile `p_open`, `p_close` hesaplanır.
- Ölçütler: Brier, log-loss, RPS. Fark için maç bazında eşleştirilmiş **bootstrap %95 GA** (1000 tekrar).
- Beklenti: kapanış daha iyi. İyi değilse veri hatası aranmalı.

**B. Düşen oran sinyali kapanışın ötesinde bilgi taşıyor mu?**
- Sinyal: `Δp = p_close − p_open`. Eşikler: `Δp ≥ +0,02, +0,03, +0,05, +0,08`. Ham oran eşdeğeri %3/5/8/10 de raporlanır ki sitelerle kıyaslanabilsin.
- Kova bazında: gerçekleşen frekans − `p_close`, Wilson GA ile. Lojistik regresyon: `y ~ logit(p_close) + Δp`. Δp katsayısının 0'dan farkı test edilir.
- **Doğru hipotez:** katsayı ≈ 0, yani bilgi kapanışa tam yansımış. Pozitif çıkarsa yetersiz tepki, negatif çıkarsa Simon tarzı aşırı tepki var demektir.

**C. iddaa ile Pinnacle kapanışı (OZBET'e özgü, asıl değerli test)**
- `data/odds/` anlık görüntüleri, maç bittikten sonra football-data CSV'sindeki PSC ile eşleştirilir (takım adı eşleme tablosu gerekir).
- Ölçüt: **iddaa CLV** = `o_iddaa · p_PSC_Shin − 1`. Ayrıca iddaa adil olasılığı ile PSC adil olasılığı arasındaki fark ve bu farkın anlık görüntü saatine göre değişimi.
- Soru: iddaa, Pinnacle hareketini gecikmeli mi izliyor? 08:30 görüntüsünde iddaa adil p'si ile PSC farkı, 18:30'dakinden büyükse cevap evet. Bu takvimle örneklem birkaç haftada birikir (günde ~70 maç).
- Beklenti: yüksek marj yüzünden CLV neredeyse her zaman negatif. Raporlanacak şey, "CLV>0" olan nadir durumların sıklığı ve dağılımı.

**D. Strateji simülasyonu (yalnızca bilgi amaçlı)**
- Açılışta Max oranla, `Max·p_PSC > 1` ise oyna. Getiri ve CLV raporlanır. Bu, Kaunitz'in bizim veride yeniden üretimidir.
- Not: Gerçek kapanış, karar anında bilinmez. Bu yüzden simülasyon "kâhin üst sınırı" olarak etiketlenmeli.

**Tuzaklar** [D]:
- *Bakış öncesi sızıntı:* PSC'yi karar anında kullanmak.
- *Çoklu test:* 4 eşik × 3 sonuç × N lig → Benjamini-Hochberg düzeltmesi uygulanmalı ya da önceden kayıtlı tek bir birincil hipotez seçilmeli.
- *Marj değişimi:* ham oran hareketini sinyal sanmak.
- *Seçilim:* yalnızca PS'si olan maçlar (alt ligler eksik olabilir).
- *Tarih kayması:* kapanış sütunları olmayan eski sezonlar.
- *Lig içi korelasyon:* aynı gün ve aynı ligdeki maçlar bağımsız değildir. Bootstrap tarih bloklarıyla yapılmalı.
- *Survivorship:* iptal veya ertelenen maçlar.
- *Tek kitap farkı:* Avg her ligde farklı sayıda bahisçi içerir.

---

## 3. Piyasa içi tutarsızlık: örtük λ'lar

- Bağımsız Poisson varsayımıyla [D, standart türetme]:
  - 1X2 adil olasılıklarından `(pH, pA)` iki denklem verir, bilinmeyen iki: `(λh, λa)`. Bunlar sayısal olarak çözülür (Nelder-Mead veya Newton; ızgara başlangıcı 0,2–4,0). pX bir **artık kontrol** olarak kalır: `pX_model − pX_piyasa`.
  - Ü/A 2,5'ten: `P(T≤2) = e^{−Λ}(1+Λ+Λ²/2)`. Buradan tek boyutlu kök bulunarak toplam `Λ_ou` çıkar.
  - KG'den: `P(KG var) = (1−e^{−λh})(1−e^{−λa})`.
- Tutarlılık ölçüleri:
  - `gap_total = Λ_ou − (λh+λa)` (gol cinsinden)
  - `gap_btts = p_KG_piyasa − p_KG(λh, λa)`
  - `gap_draw` (yukarıdaki pX artığı)
- **Uyarı:** Bağımsız Poisson beraberliği ve 0-0'ı eksik tahmin eder; Dixon-Coles'un ρ düzeltmesinin nedeni budur (DEEP_RESEARCH §2.1). Bu yüzden ham boşluklar sıfır ortalamalı değildir; **lig bazında sistematik bir sapma** taşır [D]. Çözüm: geçmiş veride (football-data'da 1X2 ve Ü/A var, KG yok) `gap_total` dağılımı lig bazında hesaplanır. Maçın boşluğu **z-skoru** olarak raporlanır: `(gap − medyan_lig)/MAD_lig`.
- **Değer işareti mi?** Hipotez şu: |z|>2 olan maçlarda, iki marketten hangisi "yanlışsa" ona ters bahis kapanışa göre iyi fiyat verir. Bu, §2.3-B'deki gibi test edilebilir. Kapanış Ü/A sonucuna göre frekans − ima_p hesaplanır, `y ~ logit(p_ou) + z` [D]. Literatürde futbol için bu özel tutarsızlık testini bu oturumda bulamadım [O, boşluk].
- iddaa'da her marketin marjı ayrı (1X2 ~%23, Ü/A ~%19, DEEP_RESEARCH §0) ve marj dağılımı yöntemi belirsiz. Bu yüzden iddaa içi boşluklar büyük olasılıkla **marj dağıtım gürültüsüdür**. Varsayılan sunum "bilgi" düzeyinde kalmalı: "Ü/A marketi, 1X2'ye göre daha fazla gol bekliyor (+0,3 gol)". "Değerli" etiketi verilmemeli [D].

---

## 4. Algoritma taslağı — `pipeline/ozbet/agents/odds_analysis.py` (YAZILMADI)

### 4.1 Fonksiyonlar
```python
def fair_probs(odds: dict[str, float], group: str = "1X2",
               method: Literal["shin", "proportional", "power"] = "shin") -> dict | None
    # -> {"p": {"1":..,"X":..,"2":..}, "margin": float, "shin_z": float|None}

def build_history_index(rows: list[dict], ref: Literal["PSC", "AvgC", "PS", "Avg"] = "PSC") -> HistIndex
    # rows: football_data.history() çıktısı + açılış/kapanış PS/Avg/Max ayrı alanlar
    # HistIndex: numpy dizileri pH,pA,p_over, y_res(0/1/2), goals_h, goals_a, league, date, weight

def similar_matches(idx: HistIndex, p: dict, league: str, today: date,
                    k: int = 400, d_max: float = 0.03, xi: float = 0.0019) -> Neighbourhood
    # havuz seçimi: lig -> lig ailesi -> tümü; n_eff hesaplar

def wilson(successes: float, n: float, z: float = 1.96) -> tuple[float, float]

def summarise(nb: Neighbourhood, p_market: dict) -> dict   # 1X2, Ü/A, KG, skorlar, Δ ve GA

def movement_fair(history: list[dict], method="shin") -> dict
    # ilk/son anlık görüntü, Δp (adil), Δmarj, kick-off'a kalan saat; mevcut market.movement'ı değiştirmez

def implied_lambdas(p1x2: dict, p_over: float | None, p_btts: float | None) -> dict
    # {"lh","la","total_1x2","total_ou","gap_total","gap_draw","gap_btts"}

def consistency_z(gaps: dict, league_stats: dict) -> dict

def analyse_match(match: dict, idx: HistIndex, league_stats: dict, odds_hist: list[dict]) -> dict
    # match.odds_analysis'i üretir; istisnada {"status":"error","reason":...}
```

### 4.2 JSON şeması (`match.odds_analysis`)
```json
{
  "version": 1,
  "status": "ok | insufficient | error",
  "fair": {"method": "shin", "p": {"1":0.47,"X":0.27,"2":0.26}, "margin": 0.226,
           "method_spread": 0.012},
  "similar": {
    "ref": "PSC", "pool": "league|family|all", "n": 400, "n_eff": 352.4, "d_max_used": 0.021,
    "outcomes": {"1": {"freq":0.49,"ci":[0.44,0.54],"market_p":0.47,"delta":0.02},
                 "X": {...}, "2": {...}},
    "over25": {"freq":0.52,"ci":[0.47,0.57],"market_p":0.50},
    "btts":   {"freq":0.51,"ci":[0.46,0.56],"market_p":0.49},
    "top_scores": [{"s":"1-1","freq":0.12}],
    "warning": null
  },
  "movement": {"from":"2026-11-06T09:36+03:00","to":"2026-11-06T18:30+03:00",
               "dp": {"1":0.018,"X":-0.004,"2":-0.014}, "dmargin": 0.003,
               "alarm": {"side":"1","dp":0.018,"threshold":0.03,"fired":false}},
  "consistency": {"lh":1.52,"la":1.05,"total_1x2":2.57,"total_ou":2.71,
                  "gap_total":0.14,"z_total":0.9,"gap_btts":-0.01,"gap_draw":0.02,
                  "note_tr": "Ü/A marketi 1X2'ye göre biraz daha fazla gol bekliyor."},
  "disclaimer_tr": "Geçmiş benzer oranlar piyasanın kalibrasyonunu gösterir; maç tahmini değildir."
}
```
Uyarı kuralları [D]:
- `n_eff<100` → `status:"insufficient"`, kartta gösterilmez.
- `100≤n_eff<400` → "düşük güven" uyarısı.
- `|delta|`, GA 0'ı içeriyorsa "piyasa ile uyumlu" yazılır; renkli vurgu yapılmaz.

### 4.3 Test planı (pytest, sentetik veriyle — gerçek veri yok)
1. `fair_probs`: Σp=1. Marj 0 iken bütün yöntemler aynı sonucu verir. Shin, orantısala göre favoriye daha yüksek p verir (FLB yönü). `mberk/shin` ile birkaç vakada sayısal eşleşme (tolerans 1e-4).
2. `wilson`: n=0 → (0,1). Bilinen değerler: 50/100 → (0,404; 0,596).
3. `similar_matches`: sentetik ızgarada k ve d_max sınırları; havuz düşüşü lig → aile → tümü; ağırlıklar ve n_eff.
4. **Kalibrasyon simülasyonu:** Sonuçlar bilinen p'lerden örneklenir. `delta` GA'ları %95 civarında 0'ı kapsamalı (1000 tekrar, kapsama 0,93–0,97).
5. `implied_lambdas`: bilinen (λh, λa) → Poisson olasılıkları → geri çözüm, hata <1e-3. `gap_total`≈0.
6. `movement_fair`: marjın tek başına değiştiği seri → `dp`≈0, alarm yok.
7. Şema: `analyse_match` çıktısı JSON-şema doğrulamasından geçmeli. Eksik Ü/A → `over25:null` olur, hata vermez.
8. Backtest betiği (§2.3) ayrı bir modül (`backtest_odds.py`); çıktısı `data/odds_backtest.json`, haftalık.

---

## 5. Kaynaklar (bu belgede kullanılan)
- Whelan 2023, UCD WP23/16: https://www.ucd.ie/economics/t4media/WP23_16.pdf
- Kaunitz, Zhong, Kreiner 2017: https://arxiv.org/abs/1710.02824
- Simon 2024, Management Science 70(12): https://ideas.repec.org/a/inm/ormnsc/v70y2024i12p8583-8611.html
- Štrumbelj, olasılık dönüşümü (kayıt): https://econbiz.de/Record/on-determining-probability-forecasts-from-betting-odds-%C5%A1trumbelj-erik/10010517776
- Shin Python: https://www.github.com/mberk/shin · implied (R): https://www.r-bloggers.com/the-probabilities-implied-by-bookmaker-odds-introducing-the-implied-package/
- Brown–Cai–DasGupta 2001: https://projecteuclid.org/download/pdf_1/euclid.ss/1009213286 · Agresti–Coull 1998: https://math.unm.edu/~james/Agresti1998.pdf
- Pinnacle marj: https://pinnaclesports.freshdesk.com/support/solutions/articles/1000189654-how-do-i-calculate-betting-margins-
- OddsPortal dropping odds: https://www.oddsportal.com/dropping-odds/
- arXiv 2604.17194: https://arxiv.org/pdf/2604.17194 · arXiv 2608.11505 (DEEP_RESEARCH'ten)
- Doğrulanamayanlar: Pinnacle'ın özgün CLV makalesi (site hata verdi), Trademate/RebelBetting ürün sayfaları, football-data notes.txt.
