# 01 — Örnek Siteler İncelemesi (Ajan 1)

Tarih: 2026-11-06. Yöntem: WebFetch + WebSearch (tarayıcı/ağ isteği izleme yok, bu yüzden XHR/API çağrıları **görülemedi**).
Sitelerin içeriği kopyalanmadı; aşağıdakiler kendi cümlelerimle özettir. OZBET bu sitelerin hiçbirinden veri **çekmeyecek**, yalnızca fikir alacak.

Kısaltmalar: MS = maç sonucu 1X2, KG = karşılıklı gol, Ü/A = üst/alt, İY = ilk yarı.

---

## 1. iddaaorananalizi.com (marka adı: OranAnalizTV)

En ayrıntılı incelenebilen site. Dört üst menü var: Analiz, Tahminler, Spor Toto ve Keşfet. Sayfalar "Ücretsiz" ya da "VIP" diye işaretli. Kaynak: https://iddaaorananalizi.com

### 1.1 Özellikler
- Açılış ve kapanış oran analizi (çoğu VIP), "Oran Radarı" ve "Düşen Oranlar" (açılıştan bu yana düşen oranlar).
- "Akıllı araçlar": Oto Analiz, En İyi Filtre Bul, DNA/Parmak İzi, Oran DNA Motoru, Skor Analiz V2.
- Korner, kart ve basketbol analizleri ile korner/kart Ü/A arşivleri.
- Günlük tahminler, "market listeleri", kuponlar, "JARVIS AI" seçimleri ve Spor Toto kolonları.
- Herkese açık **performans sayfası** (kayıplar dahil), üyelerin gönderdiği "kazanan kupon" görselleri, aylık para ödüllü "VIP Arena" yarışması ve maç kaydetme için "Analiz Masam".
- Ücretli üyelik paketleri aylık, 3, 6 ve 12 aylık. Kaynak: https://iddaaorananalizi.com

### 1.2 Maç sayfası düzeni (örnek: https://iddaaorananalizi.com/mac/u-chile-cd-antofagasta-2026-11-06)
1. Başlık: turnuva, saat ve durum.
2. "Oranlar ne anlatıyor": favori taraf ve oranının ima ettiği olasılık. Örnekte 1.19 için %84 yazıyor ve bu değerin marj içerdiği belirtiliyor. Kapanış kaydı yoksa oran hareketinin hesaplanamadığını söylüyor.
3. Maç bilgi kutusu: ülke, tarih ve market sayısı.
4. Oran tablosu: açılış, kapanış ve değişim sütunları. Örnekte yalnız MS açılışı vardı.
5. Takım istatistikleri: arşivdeki maç öncesi son N maç. Galibiyet/beraberlik/mağlubiyet, atılan ve yenilen gol ortalaması, Ü2.5 x/N, KG x/N ve form harfleri gösteriliyor. Takımlar ayrı ayrı sayılıyor; örnekte biri 10, diğeri 8 maçtı.
6. H2H: örneklem sayısı açıkça yazıyor (örnekte n=1) ve geçmişin sonucu belirlemediğine dair uyarı var.
7. "Geçmiş Oran Analizi": **üyelere kilitli**, sayılar herkese açık sayfada görülemedi.
8. Tahmin bloğu yok. Sayfa, oran özetinin öneri olmadığını açıkça yazıyor.

### 1.3 Veri mantığı ve yöntem (çözümleme)
- **Benzer oran eşleştirme:** Seçilen oran tam değer olarak değil, dar bir **aralık (bant)** olarak aranıyor. Arşivde açılışı bu bantta olan ve sonucu belli maçlar bulunuyor. Her market için gerçekleşme sayılıp yüzdeye çevriliyor ve marketin **genel taban oranıyla** (base rate) yan yana gösteriliyor. Bant genişliği **açıklanmamış**; sayfa yalnızca dar bandın örneklemi küçülttüğünü, geniş bandın ise farklı maçları karıştırdığını anlatıyor. Kaynak: https://iddaaorananalizi.com/metodoloji
- **Örneklem:** Her yüzdenin yanında maç sayısı var. Küçük örneklemde yüzde gizleniyor ya da soluk gösteriliyor. Metodoloji sayfası eşik vermiyor (https://iddaaorananalizi.com/metodoloji). Ana sayfadaki performans istatistiklerinde ise 10'un altı "az örneklem" sayılıyor (https://iddaaorananalizi.com).
- **Tarih aralığı:** Genel bir pencere yok, her aracın kendi sayfasında yazıyor. Navigasyon metnine göre "En İyi Filtre Bul" son 13 günü kullanıyor (https://iddaaorananalizi.com/metodoloji). Arşivin kapsamı:
  - Açılış oranları 2024-01-01 → 2026-09-04, 113.554 kayıt.
  - Kapanış oranları 2025-01-01 → 2026-09-03, 100.573 kayıt. Aynı sayfanın başka bir yerinde "2020'den beri kesintisiz" yazıyor; çelişkili.
  - 969'dan fazla lig kodu var.
  - Kaynak: https://iddaaorananalizi.com/veri. Ana sayfa ise yaklaşık 180.301 maç, 124.818 açılış oranı ve 1.000'den fazla lig diyor (https://iddaaorananalizi.com). Rakamlar tutarsız.
- **Marketler:** Arşivde MS, birden çok eşikte Ü/A, KG, handikap, çifte şans ve toplam gol aralıkları var; hepsi tam maç ve İY için (https://iddaaorananalizi.com/veri). Metodoloji sayfası açıkça yalnız MS'i anlatıyor. **Çoklu oran kombinasyonu** (MS + KG + Ü/A birlikte) "Oran DNA" aracında "benzer çoklu-market oran profili" olarak geçiyor, ama ayrıntısı görülemedi (https://iddaaorananalizi.com/metodoloji).
- **Oran hareketi:** Açılış, maçın bültene girdiği ilk oran; kapanış, başlama öncesi son oran. Aradaki fark "düşen oran kazanır" gibi bir kural olarak değil, ölçüm olarak sunuluyor (https://iddaaorananalizi.com/metodoloji).
- **Marj ölçümü:** Eylül 2026'da 1X2 ima olasılıklarının toplamı açılışta yaklaşık %116,5, kapanışta yaklaşık %121,9 ölçülmüş (https://iddaaorananalizi.com/metodoloji). OZBET'in marj temizleme modülü için faydalı bir dış referans.
- **Veri kaynağı:** Oranlar iddaa bülteninin açılış/kapanış oranları. SSS'ye göre bunlar yöneticinin yüklediği resmi Excel dosyasından içe aktarılıyor. Skorlar bir spor veri sağlayıcısından geliyor (adı verilmemiş). Korner ve kart verisi ayrı bir istatistik sağlayıcısından alınıyor. Eksik veri sıfır sayılmıyor, hesaptan çıkarılıyor. Kaynaklar: https://iddaaorananalizi.com/sss ve https://iddaaorananalizi.com/metodoloji
- **Model:** Çekirdek yöntem tahmin değil, geçmiş sonuç sayımı. Bazı araçlar yapay zekâ veya istatistik modeli kullanıyor. Site, kendi ölçümlerine göre oranlara karşı kalıcı bir avantaj iddia etmediğini yazıyor (https://iddaaorananalizi.com/metodoloji).

### 1.4 Güçlü ve zayıf yanlar, dürüstlük
- **Güçlü yanlar:**
  - Örneklem sayısını her yüzdenin yanında gösteriyor.
  - Taban oranla karşılaştırıyor.
  - Eksik veriyi hesaptan çıkarıyor.
  - Kayıplar dahil herkese açık performans sayfası var. Başarı "kazanan / (kazanan + kaybeden)" ile hesaplanıyor (https://iddaaorananalizi.com/sss).
  - "Banko" dili görülmedi.
  - 18+ uyarısı ve Yeşilay 115 bağlantısı var.
- **Zayıf yanlar:**
  - Bant genişliği ve küçük örneklem eşiği gizli.
  - Kaynak ve kayıt sayıları sayfalar arasında tutarsız.
  - Performans rakamları farklı pencerelerde ve açıklamasız veriliyor. Ana sayfada %76,7 (30 kayıt), performans sayfasında %79,3 (305 kayıt) ve tahminlerde 22 kayıtta %68,2 var (https://iddaaorananalizi.com).
  - Başarı yüzdesi orana göre ağırlıklandırılmamış; kârlılığı (ROI, CLV) göstermiyor.
  - Kupon görselleri ve yorumlar doğrulanmamış.
  - Ödüllü yarışma bahis teşvikine yakın duruyor.
- **Kullanım şartları ve robots.txt:**
  - robots.txt genel sayfalara `Allow: /` veriyor; `/api`, `/admin` ve hesap yollarını kapatıyor (https://iddaaorananalizi.com/robots.txt).
  - Kullanım şartlarının 7. maddesi içeriğin ve veri tablolarının izinsiz kopyalanmasını, **toplu çekilmesini (scraping)** ve ticari kullanımını yasaklıyor. 8. madde otomatik araçlarla aşırı istek göndermeyi yasaklıyor (https://iddaaorananalizi.com/kullanim-kosullari).
  - **Sonuç: otomatik veri alımına izin yok. OZBET buradan veri çekmeyecek.**

---

## 2. iddaaorantahmin.com

- `https://www.iddaaorantahmin.com` ve `http://iddaaorantahmin.com` WebFetch ile iki kez denendi; ikisinde de site istemci hatası döndü. **İçerik, maç sayfası, metodoloji, robots.txt ve kullanım şartları görülemedi.**
- Üçüncü taraf bir güvenlik tarayıcısına göre alan adı 2018-12-01'de kaydedilmiş, Cloudflare arkasında ve kendini iddaa tahmini, sonuç ve oran sitesi olarak tanıtıyor (https://gridinsoft.com/online-virus-scanner/url/iddaaorantahmin-com). Bu ikincil bir kaynak; yöntem hakkında bilgi vermiyor.
- **Öneri:** Kullanıcı siteyi tarayıcıda açıp birkaç ekran görüntüsü paylaşırsa yöntem çıkarılabilir. Bu tamamlanana kadar siteden çıkarım yapılmamalı.
- **robots.txt ve kullanım şartları:** Görülemedi, bu yüzden izin varsayılmamalı. **Veri çekilmeyecek.**

---

## 3. huhsports.com/tr (HuhSports)

Kaynak: https://www.huhsports.com/tr

### 3.1 Özellikler ve yapı
- **Tahminler:** günün maçları, lig filtreleri (Süper Lig, büyük 5 lig, Şampiyonlar Ligi) ve "en çok favorilenen / kaçınılan" tahmin sıralamaları.
- **İstatistikler:** takım, form, lig ve oyuncu sayfaları.
- **Diğer:** puan durumları, NFL bölümü, futbol bilgi oyunları (trivia, gizemli oyuncu vb.), TV rehberi, topluluk ve yapay zekâ kuponları, haberler ve uygulama kurulum sayfası.
- Ana sayfada oran, H2H ve xG **görülmedi**. Bir maç sayfası bağlantısı bulunamadığı için **maç sayfasının düzeni görülemedi**. Lig filtreli tahmin listesi örneği: https://www.huhsports.com/tr/predictions?leagueID=52

### 3.2 Veri mantığı
- "Nasıl çalışır" sayfasına göre dört ayrı algoritma MS ve toplam gol için ortak tahmin üretiyor. Ardından uzmanlar sakatlık, ceza, kadro, fikstür yoğunluğu, motivasyon, saha ve hava ile hakem profiline bakıp küçük düzeltmeler yapıyor. Yalnız uzmanın onayladığı tahminler yayınlanıyor (https://www.huhsports.com/tr/how-it-works).
- **Model girdileri:** sezon geneli atılan ve yenilen goller, gol atamadığı ve gol yemediği maçlar, iç saha / deplasman ayrımı, son 6 veya 8 maçlık form, güçlü ve zayıf rakiplere karşı sonuçlar, H2H. Ağırlıklar, model tipi ve eğitim yöntemi **açıklanmamış**. Oran geçmişi eşleştirmesi ya da xG kullanıldığına dair bir ifade yok (https://www.huhsports.com/tr/how-it-works).
- **Veri kaynağı:** Belirtilmemiş. Ağ istekleri görülemedi.

### 3.3 Güçlü ve zayıf yanlar, dürüstlük
- **Güçlü yanlar:**
  - Kapsamlı bir oyunlaştırma ve topluluk katmanı var.
  - Uzman düzeltmesi için kontrol listesi mantıklı; OZBET'in kadro ve haber ajanıyla örtüşüyor.
  - Sayfa, %75'in bile sürekli kazanç için yetmeyebileceğini kabul ediyor.
- **Zayıf yanlar:**
  - Tek algoritmanın %50, dört algoritmanın birlikte %75'e kadar çıkabileceği iddiası **ölçülmüş bir kayıt, örneklem ya da dönem olmadan** veriliyor (https://www.huhsports.com/tr/how-it-works).
  - Olasılık kalibrasyonu yok, şeffaf bir karne yok.
- **robots.txt:** WebFetch istemci hatası verdi, **görülemedi** (https://www.huhsports.com/robots.txt). Kullanım şartları sayfası da bulunamadı. İzin varsayılmamalı; **veri çekilmeyecek.**

---

## 4. spordb.com

Kaynaklar: https://www.spordb.com ve https://www.spordb.com/hakkimizda/

### 4.1 Özellikler ve yapı
- 2016'dan beri yayında (hakkımızda sayfasına göre).
- **Sunulanlar:**
  - Canlı skor ve canlı istatistik.
  - "Akıllı canlı kupon" ve "akıllı canlı analiz".
  - Oran araçları: Oran Matik, Oran Değişimleri ve Oran Analiz İpuçları.
  - İddaa programı.
  - Maç simülasyonu.
  - "ST Analiz" (futbol ve basketbol).
  - Puan durumları, sakat ve cezalı listeleri, takım form serileri.
  - Forum, yazarlar, haberler, Gold üyelik ve mobil uygulamalar.
- Ana sayfa çoğunlukla haber akışından oluşuyor. Bireysel maç sayfası yerine haber ve önizleme sayfaları bulundu (örnek: https://www.spordb.com/haber/galatasaray---vfb-stuttgart-mac-onizlemesi/46118/). **Bir analiz veya maç detay sayfasının bölüm sırası görülemedi.**

### 4.2 Veri mantığı
- **Maç simülasyonu:** Her maç 18 faktöre dayanıyor. Kullanıcı faktörleri açıp kapatıp simülasyonu çalıştırabiliyor. Çıktılar İY skoru, MS skoru, Ü/A, KG var/yok ve beklenen kart ve penaltı. Faktörlerin geçmiş maçlarda test edildiği söyleniyor, ama ağırlıklar ve birleştirme yöntemi açıklanmamış (https://www.spordb.com/iddaa-tahminleri/).
- **ST Analiz:** MS, AÜ (2.5), KG, TG, İYMS, İY ve HYFG sekmeleri, tarih seçici ve "değerler şu saatte güncellendi" notu var. Yöntem, örneklem ve tarih aralığı sayfada **yazmıyor** (https://www.spordb.com/analiz/futbol/ms/).
- **Oran değişimleri ve oran analiz ipuçları** sayfaları var, ama içerikleri bu incelemede **görülemedi**.
- **Veri kaynağı:** Belirtilmemiş; yalnızca "istatistikler ve diğer faktörler" deniyor (https://www.spordb.com/hakkimizda/).

### 4.3 Güçlü ve zayıf yanlar, dürüstlük
- **Güçlü yanlar:**
  - Kullanıcının faktörleri açıp kapatabildiği etkileşimli simülasyon fikri ilgi çekici.
  - Geniş market yelpazesi (İYMS, kart, penaltı).
  - Sakat ve cezalı listeleri.
- **Zayıf yanlar:**
  - Hiçbir yerde ölçülmüş başarı yok.
  - "Eşi benzeri olmayan sistem" ve "en doğru, en hızlı" gibi kanıtsız tanıtım dili kullanılıyor (https://www.spordb.com/iddaa-tahminleri/, https://www.spordb.com/hakkimizda/).
  - Uygulama yorumlarındaki kazanç anlatıları doğrulanmamış.
  - "Sonuçlar ileride lig lig yayınlanacak" deniyor, ama yayınlanmamış.
- **Kullanım şartları ve robots.txt:**
  - robots.txt `User-agent: * / Allow: /` diyor (https://www.spordb.com/robots.txt).
  - Ancak site altbilgisi izinsiz içerik kopyalamayı ve dağıtmayı yasaklıyor (https://www.spordb.com/hakkimizda/).
  - robots.txt'nin izin vermesi, içeriğin yeniden kullanımına izin anlamına gelmez. **Veri çekilmeyecek.**

---

## 5. Karşılaştırmalı çıkarımlar

- **Saf "oran analizi" yöntemi:** Açılış oranı bandı → arşivde aynı banttaki maçlar → market bazında gerçekleşme yüzdesi, n ve taban oran. Bu, istatistiksel olarak bir **ampirik kalibrasyon tablosu**dur. Oranın ima ettiği olasılık ile gerçekleşen frekans arasındaki fark, ancak n büyükse ve marj temizlenmişse anlamlıdır.
- OZBET bunu daha dürüst yapabilir:
  - Wilson güven aralığı gösterilir.
  - Marjsız ima olasılığı yanına konur.
  - Bant genişliği açıkça yazılır.
  - Eşik altı örneklemde yüzde gösterilmez.
- Hiçbir site olasılık **kalibrasyonu**, Brier/log-loss ya da CLV yayınlamıyor. OZBET'in karnesi bu konuda zaten bir farklılaştırıcı.
- Hiçbirinde xG görülmedi. Dört sitenin hiçbirinin veri sağlayıcısı açıkça adlandırılmamış.

## 6. Her özellik için yasal ve ücretsiz kaynak

- **Benzer açılış oranlı maçların sonuç dağılımı (MS):**
  - football-data.co.uk CSV'lerinde maç başı ve kapanış ortalama/Pinnacle oranları ile sonuçlar var. Bu veri, OZBET'in kaynak araştırmasında kişisel kullanım kapsamında not edilmiş (/home/claude/ozbet/docs/DEEP_RESEARCH.md §1.5).
  - iddaa'ya özgü açılış oranı için `data/odds/*.json` arşivimiz kullanılır. Şu an yalnızca 2026-11-05 ve 2026-11-06 var; anlamlı örneklem için aylar gerekir.
- **Ü/A ve KG oran bandı:** football-data.co.uk'ta 2.5 Ü/A oranları var. KG oranı bu dosyalarda yok; bizim arşivimizde birikecek. Arada KG için Dixon-Coles olasılığının kendi bandı kullanılabilir.
- **Oran hareketi ve düşen oran:** Kendi arşivimizdeki 08:30, 13:30 ve 18:30 görüntüleri ile football-data.co.uk'taki açılış ve kapanış sütunları.
- **Takım son N maç kutusu (G/B/M, gol ortalaması, Ü2.5 ve KG oranı) ile H2H (n ile birlikte):** football-data.co.uk sonuçları. Bunlar zaten modelde kullanılıyor.
- **Uzman düzeltme kontrol listesi** (HuhSports'taki gibi): Mevcut kadro ve haber ajanımız ile hakem ve hava kaynakları (DEEP_RESEARCH §1.2 ve §1.3).
- **Etkileşimli faktör aç/kapa simülasyonu** (SporDB'deki gibi): İstemci tarafında λ çarpanlarıyla yeniden Poisson hesabı. Dış veri gerekmez.
- **Kart ve korner beklentisi:** football-data.co.uk'ta HC/AC (korner) ve HY/AY/HR/AR (kart) sütunları büyük ligler için mevcut.

## OZBET'e alınacaklar (öncelik sıralı)

| # | Özellik | Esin kaynağı | Veri kaynağı (ücretsiz, yasal) | Emek |
|---|---|---|---|---|
| 1 | "Benzer oranlı maçlar ne oldu" kutusu (MS): oran bandı, gerçekleşme yüzdesi, n, Wilson aralığı, marjsız ima olasılığı ve taban oran; n < 30 ise yüzde gizlenir | iddaaorananalizi | football-data.co.uk (TR1 ve büyük 5 lig, son 3+ sezon) | M |
| 2 | Ü2.5 için aynı kutu (KG için önce model bandı, arşiv biriktikçe gerçek oran bandı) | iddaaorananalizi | football-data.co.uk Ü/A oranları ve `data/odds` arşivi | S |
| 3 | Maç sayfasına "Oranlar ne anlatıyor" satırı: ham ve marjsız ima olasılığı ile marj yüzdesi | iddaaorananalizi | Mevcut iddaa ve Nesine oranları | S |
| 4 | Takım son N maç kutusu ve n'li H2H, "geçmiş sonucu belirlemez" notuyla | iddaaorananalizi | football-data.co.uk (mevcut) | S |
| 5 | Açılış → kapanış hareket tablosu ve düşen oran listesi; kural değil ölçüm olarak, CLV ile karneye bağlı | iddaaorananalizi / SporDB | `data/odds` arşivi (günde 3 görüntü) | S |
| 6 | Karnede başarı yüzdesinin yanında ROI, Brier ve kalibrasyon; tüm pencerelerin tarih aralığı açıkça yazılır | Rakiplerin eksikliği | `data/scorecard.json` | M |
| 7 | Çok-marketli "oran profili" eşleştirme (MS + Ü/A oran vektörüne en yakın k maç) | iddaaorananalizi (Oran DNA) | football-data.co.uk | M |
| 8 | Etkileşimli "faktör aç/kapa" simülasyonu (kadro, iç saha, xG harmanı) | SporDB | İstemci tarafında λ yeniden hesabı | M |
| 9 | Kart ve korner beklentisi | SporDB / iddaaorananalizi | football-data.co.uk HC/AC ve HY/AY sütunları (büyük ligler) | M |
| 10 | Yorum öncesi kontrol listesi: sakatlık, fikstür yoğunluğu, hakem ve hava | HuhSports | Mevcut kadro ve haber ajanı, Open-Meteo | S |
| 11 | Topluluk, oyun ve kupon paylaşımı | HuhSports | — (kapsam dışı, düşük öncelik) | L |

Uyarı: Bu dört sitenin hiçbirinden otomatik veri alınmayacak. iddaaorananalizi kullanım şartlarında scraping'i açıkça yasaklıyor; SporDB içerik kopyalamayı yasaklıyor; diğer iki sitenin şartları görülemedi.
