# 03 — Uluslararası tahmin sitelerinin yöntemleri

Tarih: 2026-11-06 · Ajan 3 · Araçlar: WebSearch ve WebFetch. Okunan depo dosyaları: README.md, docs/DEEP_RESEARCH.md, data/backtest.json.

Etiketler: **[Y]** birincil kaynakta görüldü · **[O]** ikincil kaynak veya kısmi bilgi · **[D]** çıkarım · **[KANITSIZ]** sitenin kendi iddiası, doğrulanabilir ölçüm yok.
Erişim notu: `clubelo.com/System`, `clubelo.com/API` ve `clubelo.com/robots.txt` sayfalarını fetch aracı açamadı (client_error / robots_disallowed). `windrawwin.com` ve `predictz.com` da açılmadı. Bu siteler için ikincil kaynak kullanıldı ve bu durum ayrıca belirtildi.

---

## 0. Kısa sonuç

- Ücretsiz "tahmin" sitelerinin büyük kısmı (Forebet, Vitibet, Zulubet, Statarea, PredictZ, WinDrawWin) yöntemini ve başarısını **yayımlamıyor**. Yalnızca "matematiksel model/AI" diyorlar, Brier/ROI vermiyorlar. Konsensüs kaynağı olarak değerleri **düşük**, çünkü bağımsız bilgi taşıdıkları kanıtlanmamış.
- Yöntemi açık olan üç ciddi model var: **FiveThirtyEight SPI** (Poisson ve xG kompoziti, 2023'te kapandı ama arşivi açık), **ClubElo** (Elo, ücretsiz CSV API) ve **eloratings.net** (milli takımlar). **Opta Supercomputer** ise girdilerini açıklıyor (bahis oranları ve Opta Power Rankings) ama formülünü açıklamıyor.
- OZBET için en önemli ders zaten backtest'te görünüyor: Opta'nın kendi "süper bilgisayarı" da **piyasa oranlarını girdi olarak kullanıyor**. Bu, bizim %25 model + %75 piyasa harmanımızın doğru yönde olduğunu destekliyor [Y] ([Opta](https://theanalyst.com/articles/opta-football-predictions)).

---

## 1. Site site inceleme

### 1.1 FiveThirtyEight SPI (arşiv) — en ayrıntılı açık yöntem
Kaynak: [Metodoloji](https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/) [Y]
- **Rating:** Her takımın bir hücum değeri (ortalama rakibe karşı nötr sahada atması beklenen gol) ve bir savunma değeri (yemesi beklenen gol) var. SPI, bu ikisinden türetilir: maç sonsuz kez oynansa takımın alacağı puan payı.
- **Maç performansı = üç metriğin ortalaması:**
  1. *Düzeltilmiş gol:* Rakip eksikken atılan gol ~0,8 sayılır. 70. dakikadan sonra önde iken atılan goller kayan ölçekle en düşük 0,5'e kadar indirilir. Toplam, gerçek gol ortalamasını tutacak şekilde yeniden ölçeklenir.
  2. *Şut xG'si:* Mesafe, açı ve vücut bölümü, ayrıca şutörün geçmiş bitiriciliği.
  3. *Şut dışı xG:* Rakip ceza sahası yakınındaki pas, top kapma, çalım ve müdahaleler, tarihsel gol oranlarıyla değerlendirilir.
  - Ağustos 2018'den sonra ham skor bu kompozite doğrudan girmiyor.
- **Güncelleme:** Her maçtan sonra yapılır. Beklentiye göre fark ve rakip gücüne göre ayarlanır. Takım kazansa bile kötü oynadıysa puan kaybedebilir.
- **Sezon başı:** Geçen sezon sonu SPI'si ile **Transfermarkt piyasa değeri** (lig ortalamasına oranla) harmanlanır. Takım düzeyinde açık bir "ortalamaya geri çekilme" katsayısı yayımlanmamış. **Lig gücü** ise piyasa değeri tabanlı tahmine doğru geri çekiliyor (Massey yöntemi, 5 yıllık ligler arası maçlar).
- **Maç tahmini:** Rating'lerden iki λ hesaplanır. Bu λ'lar lige özgü iç saha avantajı ve maçın önemiyle ayarlanır. **Bağımsız Poisson** skor matrisi kurulur ve **beraberlik hücreleri ~%9 şişirilir** (lige göre değişir).
- **Maç önemi:** Bir takım için önemli olan maç o takımın beklentisini artırır. İki taraf için de önemsiz maçta belirsizlik artar.
- **Sezon simülasyonu:** 20.000 koşu. Rating'ler simülasyon içinde de güncellenir ("sıcak" simülasyon).
- **Kadro etkisi:** Kadro düzeyinde ayrıca bir düzeltme metinde tarif edilmiyor. Oyuncu etkisi yalnızca şut ve pas xG düzeltmelerine gömülü.
- **Başarı:** Metodoloji sayfasında Brier veya ROI rakamı yok. **Arşiv veri:** `spi_matches.csv` (2016'dan bu yana maç bazında prob1/probtie/prob2, proj_score, xg, nsxg) ve `spi_global_rankings.csv` [Y] ([datahub](https://datahub.io/fivethirtyeight/soccer-spi), [R paketi belgesi](https://fivethirtyeightdata.github.io/fivethirtyeightdata/reference/spi_matches.html)). Modeller Haziran 2023'te güncellenmeyi bıraktı [O] ([From the Byline](https://fromthebyline.substack.com/p/fivethirtyeight-is-dead-long-live)). Lisans datahub sayfasında yazmıyor. FiveThirtyEight'in GitHub deposunda kontrol edilmeli [D].
- **OZBET'e uygulanabilirlik:** Arşiv, 2016–2023 için **ücretsiz bir benchmark** sağlıyor. Aynı maçlarda SPI'nin Brier'ı ile bizim Dixon-Coles'un Brier'ı karşılaştırılabilir (TR1 kapsamı arşivde olabilir, doğrulanmalı [D]).

### 1.2 Opta Analyst "Supercomputer" ve Opta Power Rankings
- **Yöntem:** Her maç için 1X2 olasılıkları **bahis piyasası oranları ve Opta Power Rankings** kullanılarak hesaplanır. Kalan fikstür "binlerce kez" simüle edilir ve takım başına sıra olasılıkları çıkarılır [Y] ([Opta tahmin sayfası](https://theanalyst.com/articles/opta-football-predictions)). Harman ağırlıkları ve simülasyon sayısı yayımlanmamış.
- **Power Rankings:** 0–100 ölçeği, 13.500'den fazla erkek kulübü ve 562 lig, **günlük** güncelleme [Y] ([Opta PR](https://theanalyst.com/articles/who-are-the-best-football-team-in-the-world-opta-power-rankings)). Formül ayrı bir "Explained" makalesinde. Elo tabanlı olduğu yaygın biçimde söyleniyor ama bunu birincil kaynakta doğrulayamadım [D].
- **Başarı:** Yayımlanmış bir Brier/ROI ölçümü yok [KANITSIZ: "supercomputer" bir pazarlama adı]. Yöntemin ayrıntısı açıklanmıyor [O] ([From the Byline](https://fromthebyline.substack.com/p/fivethirtyeight-is-dead-long-live)).
- **Ayırt edici özellik:** Sezon sonu sıra olasılığı ısı tablosu (1.–20.), şampiyonluk, Avrupa ve küme düşme yüzdeleri.
- **OZBET dersi:** Modeli piyasayla harmanla, sonra **sezon simülasyonunda** harmanlanmış maç olasılıklarını kullan.

### 1.3 ClubElo (clubelo.com)
- **Yöntem:** Elo. Win expectancy W = 1/(1+10^(−Δ/400)) ve güncelleme E₁ = E₀ + K·(R − W). Parametreler **K = 20** ve ölçek 400. Formül iç saha avantajını ve gol farkını hesaba katıyor. Sistem sıfır toplamlı [O] ([arXiv 2304.09078, ClubElo'yu özetliyor](https://arxiv.org/pdf/2304.09078)). İç saha ve gol farkı katsayılarının sayısal değeri `clubelo.com/System` sayfasında. Bu sayfa fetch aracıyla açılamadı, bu yüzden değerleri **buraya yazmadım** (uydurmamak için).
- **Girdiler:** Yalnızca maç sonuçları (skor, saha). Her maçtan sonra güncellenir, günlük tablo yayımlanır.
- **API:** `http://api.clubelo.com` ücretsiz **CSV API** [O] ([soccerdata belgesi](https://soccerdata.readthedocs.io/en/latest/reference/clubelo.html)). Topluluk kütüphaneleri tarih bazlı sıralama (`/YYYY-MM-DD`), takım geçmişi (`/<TakımAdı>`) ve fikstür olasılıkları (`/Fixtures`) uç noktalarını kullanıyor [O] ([ScraperFC](https://scraperfc.readthedocs.io/en/latest/clubelo.html)). Lisans ve kullanım şartları API sayfasında. Açılamadığı için **doğrulanmadı**. Atıf yaparak düşük frekansla (günde 1) çekmek makul görünüyor [D].
- **Başarı:** Yayımlanmış Brier yok. Bir eleştiriye göre gerçek maç veya sezon projeksiyonu yerine uzun vadeli gücü izliyor [O] ([From the Byline](https://fromthebyline.substack.com/p/fivethirtyeight-is-dead-long-live)). Fixtures CSV'si ise maç olasılığı veriyor [O].
- **OZBET dersi:** README'ye göre OZBET Avrupa kupalarında ClubElo'yu zaten kullanıyor. Elo farkını Dixon-Coles λ'sına **ikinci bir öncül (prior)** olarak eklemek ligler arası maçlarda bilgi katabilir.

### 1.4 World Football Elo Ratings (eloratings.net) — milli takımlar
Kaynak: [Wikipedia özeti](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) [O] (eloratings.net/about sayfası binary döndü).
- Rn = Ro + K·G·(W − We), We = 1/(10^(−dr/400)+1). Ev sahibine **+100** puan eklenir.
- K değerleri: Dünya Kupası finalleri 60, kıta şampiyonaları 50, elemeler ve büyük turnuvalar 40, diğer turnuvalar 30, hazırlık maçları 20.
- Gol farkı çarpanı G: 1 farkla galibiyet veya beraberlik = 1, 2 fark = 1,5, N≥3 için G = (11+N)/8.
- Herkese açık bir JSON/CSV API belgelenmemiş. Sayfalar TSV benzeri veri dosyalarından yükleniyor olabilir [D]. Kullanım izni doğrulanmadı.
- **OZBET dersi:** Milli maçlar (Uluslar Ligi, elemeler) için hazır, açık bir formül. **K'yı maç önemine göre değiştirmek** ve **G çarpanı**, ClubElo uyarlamasında da kullanılabilir.

### 1.5 Infogol / Timeform (xG)
- Opta verisiyle kurulmuş özel bir xG modeli (şut konumu ve türü, atak tipi). Maç başına 1X2 yüzdesi verir. Betfair Sportsbook oranlarıyla karşılaştırıp "Value" işaretler. Takım rating'leriyle simülasyon, xG'ye dayalı "beklenen" puan tablosu ve sezon sonu tahmini sunar [Y] ([Timeform/Infogol](https://timeform.com/football)).
- Başarı ölçümü yayımlanmamış [KANITSIZ]. xGscore ayrıca incelenemedi.
- **Ders:** "Beklenen tablo" (xG puanı ile gerçek puan arasındaki fark) şans ve regresyon göstergesi olarak sitede iyi bir özellik olur.

### 1.6 Kickform
- Münster Üniversitesi'nden Prof. Andreas Heuer'in araştırmasına dayanıyor. Girdiler: gol pozisyonları, topa sahip olma, **piyasa değeri**, maç günü ve iç saha. Sonradan izleme (tracking) verisi ve "packing" eklendiği söyleniyor [Y, şirket basın bülteni] ([PRNewswire 2017](https://prnewswire.co.uk/news-releases/kickform-professor-of-physics-has-built-a-new-algorithm-for-the-worlds-best-soccer-prediction-664134583.html)).
- "Bahisçileri geçtik" iddiası sayı vermiyor **[KANITSIZ]**.
- **Ders:** Heuer'in bulgusu, gol yerine **şut ve pozisyon sayılarının** daha kararlı bir güç ölçüsü olduğu. Bu, DEEP_RESEARCH §0'daki SOT bulgusuyla uyumlu.

### 1.7 Dectech
- Aramada yöntem veya canlı ürün sayfası bulunamadı. Kaynaksız bir şey yazmıyorum. **Durum: doğrulanamadı.**

### 1.8 FootyStats
- Tahmin sayfası "örtük olasılık ve gerçek bahisçi oranlarından hesaplanan AI/Makine Öğrenmesi tabanlı tahminler" diyor. Maç başına 2–3 "en değerli" market seçiyor [Y] ([FootyStats predictions](https://footystats.org/predictions/)). Model başarısı yayımlanmamış. Sayfada yalnızca kullanıcı tahmin liderliği var **[KANITSIZ]**.
- Güçlü yanı istatistik tabloları (Ü/A, KG, korner, kart yüzdeleri). Ücretli API'si var ama tahmin sayfası API'den söz etmiyor.

### 1.9 Forebet
- SSS: "Yapay zekâ ile geçmiş futbol verisini analiz edip olasılık hesaplar." Canlı tahmin dakikada bir güncellenir. Biten maçları yeşil/kırmızı işaretler ama toplam isabet vermez. Ücretsizdir ve "yalnızca bilgi amaçlıdır" [Y] ([Forebet SSS](https://www.forebet.com/en/faq)). **[KANITSIZ]** başarı.
- Ayırt edici: tahmini skor, ortalama gol, hava durumu, canlı tahmin güncellemesi.

### 1.10 Vitibet
- Kendine özgü bir "INDEX katsayısı" ile iki takımın şansını değerlendirdiğini söylüyor. Formülü ve ölçeği açıklanmıyor. Ü/A "PROB." yüzdesinin kaynağı belirsiz [Y] ([Vitibet](https://www.vitibet.com/)). **[KANITSIZ]**.

### 1.11 Zulubet
- Maç başına 1X2 yüzdesi, oran ve tavsiye var. Yöntem açıklanmıyor. Yüzdeler oranlardan türetilmiş gibi görünmüyor (örneğin beraberlik %10'a karşılık 5,91 oranı ≈ %17) [Y] ([Zulubet](https://www.zulubet.com/)). **[KANITSIZ]**.

### 1.12 Statarea
- 1/X/2, Ü/A 2,5 ve KG yüzdeleri, yazar yorumu ve kullanıcı tahmin sıralaması sunuyor. Yüzdelerin kaynağı (model mi, oy mu) açıklanmıyor [Y] ([Statarea](https://www.statarea.com/)). **[KANITSIZ]**.

### 1.13 PredictZ ve WinDrawWin
- İki site de fetch ile açılamadı. Yöntem açıklaması bulunamadı. Bunlar, yalnızca skor tahmini ve form tablosu sunan sitelerdir [D]. **Doğrulanamadı. Konsensüse eklenmesi önerilmez.**

### 1.14 Betaminic
- Tahmin sitesi değil, bir **strateji kurucu** (Betamin Builder). 111 lig ve 100 binden fazla maç üzerinde kural tabanlı filtrelerle geçmiş getiri gösteriyor. Ayrı bir ürün olan ShootingBets (oran hareketi alarmı) için "37.661 bahis, yield 11,92" iddiası var. Bağımsız doğrulaması yok [Y, sitenin iddiası] ([Betaminic](https://www.betaminic.com/)) **[KANITSIZ]**.
- **Ders:** Oran **düşüşü (dropping odds) alarmı** hem burada hem OZBET'te var. Strateji kurucu fikri, OZBET backtest grid'inin kullanıcıya açılmış hâli gibi düşünülebilir.

### 1.15 BetExplorer ve OddsPortal (oran toplayıcı)
- Model yok. Çok bahisçili oran karşılaştırma, açılış/kapanış oranı ve oran hareketi grafiği sunuyorlar.
- OddsPortal robots.txt: `*` için arama, AJAX, profil, maç olay sayfaları ve **1998–2024 yıllı arşiv URL'leri** yasak [Y] ([robots](https://www.oddsportal.com/robots.txt)). Arşiv kazıma açıkça engelli. BetExplorer robots notu için bkz. DEEP_RESEARCH §1.5.
- **Öneri:** Oran geçmişi için football-data.co.uk yeterli (DEEP_RESEARCH). Bu siteler kazınmamalı.

### 1.16 Eklenen kayda değer kaynaklar
- **Twenty First Group:** B2B projeksiyon modeli. Yalnızca sosyal medyada paylaşılıyor ve yöntemi açık değil [O] ([From the Byline](https://fromthebyline.substack.com/p/fivethirtyeight-is-dead-long-live)).
- **Reading Üniversitesi EconScoreCast:** Akademik skor modeli. Girdiler: hücum ve savunma geçmişi, form, iç saha, **milli ara ve Avrupa maçı yorgunluğu**, hafta içi akşam maçı. Kalan fikstürü simüle ederken her simüle maçtan sonra tahminleri günceller [Y] ([Reading](https://blogs.reading.ac.uk/econscorecast/about/)). Resmî bir Brier ölçümü yok.
- **Sportmonks Predictions API:** Ücretli. Maç başına olasılık uç noktası sunuyor (1X2, Ü/A, KG, doğru skor) [O] ([docs](https://docs.sportmonks.com/football/tutorials-and-guides/tutorials/odds-and-predictions/predictions/probabilities)). Konsensüse ücretli seçenek olarak alınabilir. Yöntem açık değil.
- **Uyarlanmış Glicko-2 (arXiv 2607.01722, 2026):** Rating, belirsizlik ve oynaklık. Gol farkı ve "baskınlık" (maç istatistiği) ağırlığı, **sezon geçişinde yapısal şok** (belirsizliği büyütme) ve beraberlik için ordered-logit kullanıyor. EPL holdout'ta Brier 0,1587'ye karşı piyasa 0,1543 (+%2,8 fark), RPS 0,2041'e karşı 0,1996. Sezon ortasından simülasyonda puan MAE'si 5,49 [Y] ([arXiv](https://arxiv.org/abs/2607.01722)). (Brier burada sınıf başına ortalama ölçekte. Bizim 0,57 ölçeğimizle doğrudan kıyaslanamaz.)

---

## 2. OZBET'e uygulanabilir ayrıntı: SPI, Opta, ClubElo

**A. Sezon başı geri çekilme (SPI ve Glicko fikri):**
SPI, sezon başında önceki rating'i piyasa değeriyle harmanlıyor [Y]. OZBET'te Dixon-Coles'un hücum ve savunma parametreleri zaman ağırlığıyla (ξ=0,0019) zaten yavaşça unutuluyor, ama yaz arasındaki **kadro değişimi** modele girmiyor. Öneri [D]:
`att_başlangıç = w·att_geçen + (1−w)·att_değer`, burada `att_değer`, lig içi log(Transfermarkt kadro değeri) sırasına regresyonla bulunur. w değeri 0,6–0,8 arasında backtest ile seçilir. Yükselen takımlar için bu formül zorunlu (geçmiş veri ya yok ya da alt ligden geliyor). Glicko yaklaşımına göre sezon geçişinde rating belirsizliği de büyütülmeli: ilk 5–6 haftada piyasa ağırlığı daha yüksek tutulabilir [D, arXiv 2607.01722'den esinlenme].

**B. Beraberlik şişirme:** SPI bağımsız Poisson + ~%9 beraberlik şişirmesi kullanıyor. OZBET'in Dixon-Coles ρ parametresi bunun karşılığı. TR1'de beraberlik kalibrasyon grafiği (tahmin ile gerçekleşen X oranı) kontrol edilmeli. Yetersizse lig bazında çarpan eklenebilir. Ucuz bir iş.

**C. Kompozit performans (SPI):** Rating güncellemesinde gol yerine `(düz. gol + xG + şut dışı xG)/3` kullanılıyor. OZBET'te de README'ye göre λ = 0,65·gol + 0,35·xG harmanı var. Ek olarak SPI'nin **"geç gol/öndeyken gol indirimi"** ve **"kırmızı kart sonrası gol indirimi"** football-data verisiyle bile kısmen uygulanabilir. Dakika verisi gerektiği için API-Football'dan olay verisi gerekir [D].

**D. Maç önemi (SPI):** Sezon sonu "iki taraf için de önemsiz" maçlarda varyansı büyüt (λ'ları ortalamaya çek). Önem, bizim sezon simülasyonundan çıkar: maçın sonucu takımın şampiyonluk, Avrupa veya küme düşme olasılığını ne kadar değiştiriyor.

**E. Opta modeli:** Maç olasılığı = piyasa + rating. Sezon simülasyonu bu harmanla çalışır. OZBET'te sezon simülasyonu varsa maç olasılıklarına %25/%75 harmanı uygulanmalı. Opta gibi binlerce koşu yerine SPI gibi 20.000 koşu ve **simülasyon içi rating güncellemesi** kullanılmalı.

**F. ClubElo / eloratings:** Ligler arası (UEFA kupaları) maçta lig gücü sorunu var. SPI bunu Massey yöntemi ve piyasa değeri çekimiyle çözüyor, ClubElo ise tek bir küresel havuzla. Öneri: Avrupa maçında `p_Elo = 1/(1+10^(−(Δ+HFA)/400))` hesaplanır, Dixon-Coles'tan gelen p ile ortalanır, sonra piyasa harmanı uygulanır. HFA'nın sayısal değeri ClubElo sayfasından doğrulanmalı. Milli maçlarda eloratings formülü (ev +100, K 20–60, G çarpanı) kullanılabilir.

**G. Kadro etkisi:** İncelenen sitelerin hiçbiri oyuncu bazlı kadro etkisini açık formülle yayımlamıyor. SPI'de bu yalnızca şut ve pas düzeltmesi olarak var. OZBET'in mevcut sabit çarpanı (kilit eksik ×0,94) makul ama kanıtsız. Bir sonraki adım, oyuncu dakika payı × takım xG katkısı tabanlı bir düzeltme olabilir [D].

---

## 3. Herkese açık ve ücretsiz veri akışları

| Kaynak | Akış | Durum |
|---|---|---|
| ClubElo | `api.clubelo.com` CSV (sıralama, takım geçmişi, fikstür olasılıkları) | Ücretsiz [O]. Şartlar sayfası açılamadı. Günde 1 çekiş ve atıf önerilir |
| FiveThirtyEight SPI | `spi_matches.csv`, `spi_global_rankings.csv` (2016–2023 arşiv) | Açık veri [Y]. Lisansı GitHub'dan doğrula. Yalnızca geçmiş benchmark |
| eloratings.net | Belgelenmiş API yok | İzin doğrulanmadı. Yalnızca formül alınmalı |
| Opta Analyst | API yok, makale içi tablo | Ticari içerik, kazınmamalı |
| Forebet, Vitibet, Zulubet, Statarea, PredictZ, WinDrawWin | API yok | ToS ve izin doğrulanmadı, yöntem kanıtsız. Konsensüse alınmamalı |
| OddsPortal / BetExplorer | API yok | robots.txt arşivi engelliyor [Y] |
| Sportmonks | Ücretli Predictions API | Lisanslı. Ücret karşılığı izinli |

---

## (a) OZBET modeline alınacak yöntemler

| # | Yöntem | Beklenen etki | Emek | Dayanak |
|---|---|---|---|---|
| 1 | Sezon başı geri çekilme: önceki rating + kadro değeri (Transfermarkt) harmanı, yükselen takım öncülü | İlk 6 haftada Brier iyileşmesi. Yükselen takımlarda büyük etki [D] | M | [SPI](https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/) |
| 2 | Lig bazında beraberlik kalibrasyonu (ρ kontrolü ve gerekirse X çarpanı) | X olasılığında kalibrasyon, küçük Brier kazancı | S | SPI ~%9 beraberlik şişirmesi |
| 3 | Sezon simülasyonu: 20.000 koşu, simülasyon içi rating güncellemesi, harmanlanmış (piyasa) maç olasılığı | Sıra, şampiyonluk ve küme düşme tablosu. Kullanıcı özelliği | M | [SPI](https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/), [Opta](https://theanalyst.com/articles/opta-football-predictions) |
| 4 | Maç önemi: önemsiz maçta λ'ları ortalamaya çekme | Sezon sonu maçlarda küçük iyileşme | M | SPI |
| 5 | ClubElo öncülü ile Avrupa kupası harmanı (Elo + DC + piyasa) | Ligler arası maçlarda iyileşme | S | [arXiv 2304.09078](https://arxiv.org/pdf/2304.09078), [soccerdata](https://soccerdata.readthedocs.io/en/latest/reference/clubelo.html) |
| 6 | Milli maçlar için eloratings formülü (ev +100, K 20–60, G=(11+N)/8) | Milli maçlarda kapsamın açılması | S | [Wikipedia](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) |
| 7 | Kompozit performans: geç gol ve kırmızı kart indirimi + şut dışı xG | Rating kararlılığı. Etkisi küçük-orta [D] | L | SPI |
| 8 | SPI arşiviyle benchmark (2016–23 aynı maçlar) | Doğrudan ölçüm, model kararlarına dayanak | S | [datahub](https://datahub.io/fivethirtyeight/soccer-spi) |
| 9 | "Beklenen tablo" (xG puanı ile gerçek puan farkı) görünümü | Kullanıcı özelliği ve regresyon sinyali | S | [Infogol](https://timeform.com/football) |
| 10 | Yorgunluk ve milli ara değişkeni | Küçük etki, test edilmeli | M | [Reading EconScoreCast](https://blogs.reading.ac.uk/econscorecast/about/) |

## (b) Konsensüse eklenebilecek, izinli tahmin kaynakları

| Kaynak | Ne verir | İzin | Not |
|---|---|---|---|
| ClubElo `/Fixtures` CSV | Maç başına olasılık (Elo tabanlı) | Ücretsiz API [O]. Şartlar doğrulanmalı | Bağımsız ve yöntemi açık. **Önerilir** |
| ClubElo sıralama CSV | Takım Elo'su | Aynı | Öncül ve kupa maçları için |
| FiveThirtyEight SPI arşivi | 2016–23 olasılıkları | Açık veri [Y]. Lisans GitHub'da | Yalnızca backtest benchmark'ı, canlı değil |
| Pinnacle / piyasa kapanışı (football-data.co.uk) | Marjı temizlenmiş olasılık | Kişisel kullanım | Zaten %75 ağırlıkla kullanılıyor |
| Sportmonks Predictions | Çok marketli olasılık | Ücretli lisans | Bütçe olursa. Yöntem kapalı |
| Forebet, Vitibet, Zulubet, Statarea, PredictZ, WinDrawWin, FootyStats AI | 1X2 yüzdeleri | API yok, ToS doğrulanmadı | **Önerilmez:** yöntemi ve başarısı kanıtsız, kazıma riski var |
