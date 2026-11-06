# 06 — TFF ve alternatif kaynaklar: 1. Lig sonuçları ve Süper Lig hakem verisi

Tarih: 2026-11-06. Etiketler: [Y] bu araştırmada WebFetch ile görüldü, [O] ikincil kaynak veya genel bilgi, [D] doğrulanamadı.
Sorun: TR2 (1. Lig) için kurallara uygun ücretsiz sonuç kaynağı yok. Flashscore şartlar, ls.nesine.com robots nedeniyle elendi. TR1'de hakem verisi yok.

## 1. www.tff.org

### 1.1 Erişim izni
- **robots.txt:** `https://www.tff.org/robots.txt` ve `https://tff.org/robots.txt` araçla açılamadı, istemci hatası döndü [Y]. İçerik **doğrulanamadı** [D]. Pipeline ilk çalışmada robots.txt'i kendisi okumalı, okuyamazsa logda belirtmeli. Disallow varsa TFF kullanılmamalı.
- **Kullanım Şartları** (`Default.aspx?pageID=179`) [Y]:
  - "izin alınmadan ve kaynak gösterilmeden kullanılamaz, değiştirilemez, kopyalanamaz, çoğaltılamaz, yeniden yayımlanamaz"
  - "Sitede yer alan bilgiler, kaynak gösterilmek suretiyle yayımlanabilir; ancak bu bilgiler **ticari amaçlarla kullanılamaz**."
  - "kişisel ve ticari olmayan kullanım amaçlarıyla bu sitenin olanaklarından yararlanılabilir"
  - "dışarıdan müdahaleye yönelik her türlü girişim hukuken yasaklanmıştır". Sistem izleniyor. Bot veya scraping için açık bir madde **yok**.
- **Kopya Hakları** (`/Copyright.htm`) [Y]: Metin, fotoğraf ve belgeler izinsiz ve kaynaksız kullanılamaz. Kişisel ve ticari olmayan kullanıma izin var.
- **Altbilgi:** "Tüm hakları Türkiye Futbol Federasyonu'na aittir." [Y]
- **Yorum** [O, hukuki tavsiye değildir]: Skor, tarih, stat ve hakem adı gibi bilgiler olgusal ve kamuya açık resmi bilgilerdir. Telif daha çok metin, fotoğraf ve tasarımı korur. Yine de TFF şartları iki koşul koyuyor:
  1. **kaynak gösterme**,
  2. **ticari olmayan kullanım**.

  OZBET reklamsız ve ücretsiz kaldıkça bu koşullara uygun okunabilir. Reklam, abonelik ya da bahis ortaklığı gelirse koşul ihlal edilir ve TFF'den yazılı izin gerekir. Sayfa HTML'i depoya kopyalanmamalı. Yalnızca türetilmiş alanlar (skor, hakem adı) saklanmalı ve sitede "Kaynak: TFF" yazmalı.

### 1.2 URL kalıpları [Y]
| Amaç | URL | Not |
|---|---|---|
| Süper Lig, güncel sezon | `Default.aspx?pageID=198&hafta=N` (N=1..34) | Sezon parametresi yok, yalnızca güncel sezon. Görülen sezon 2026-27. |
| 1. Lig, güncel sezon | `Default.aspx?pageID=142&hafta=N` (N=1..38) | Fikstür, skor ve puan durumu (`#grp`) aynı sayfada. |
| 1. Lig arşiv dizini | `default.aspx?pageID=563` | Her sezon kendi pageID'sine sahip (aşağıda). |
| Süper Lig arşiv dizini | `default.aspx?pageID=545` | Sezon pageID'leri bu çalışmada listelenmedi [D]. |
| Maç detayı | `Default.aspx?pageId=29&macId={id}` | Skor, goller (dakika), hakem kadrosu, stat, tarih ve saat. |
| Kulüp / kişi | `pageId=28&kulupId=`, `kisiId=` | |
| PFDK listesi / karar | `pageID=238`, `pageID=246&ftxtID=` | DEEP_RESEARCH §3'te incelendi. |
| Hakem atama haberi | `pageID=248&ftxtID=` | DEEP_RESEARCH §1.2'ye göre serbest metin. |

- **1. Lig arşiv pageID'leri** (pageID=563'ten okundu) [Y]:
  - 2025-26=1772, 2024-25=1731, 2023-24=1649, 2022-23=1629, 2021-22=1580, 2020-21=1530, 2019-20=1502, 2018-19=1469.
  - Daha eski sezonlar 1060 ile 1441 arasında. 2007-08 öncesi sezonlar tff.org.tr alan adında.
  - Arşiv sayfalarında `&hafta=N` parametresinin çalıştığı **doğrulanamadı** [D]. İlk uygulamada kontrol edilmeli.
- **Örnek maçlar** [Y]:
  - 1. Lig: macId 318092 (Antalyaspor 4-3 Keçiörengücü, 1. hafta) ve 318212 (Bursaspor 3-0 Bandırmaspor, 13. hafta). 1. Lig'de görülen macId aralığı 318xxx.
  - Süper Lig: macId 317790 (Galatasaray 2-2 Arca Çorum, 14.08.2026). Süper Lig'de görülen aralık 317xxx.
  - Oynanmamış maçta skor yerine "-" yazıyor.
- **Maç detayında görülen alanlar** (317790) [Y]:
  - Skor ve gol dakikaları.
  - Hakem, 1. ve 2. yardımcı, 4. hakem, VAR, AVAR, gözlemci, temsilciler.
  - Stat ve şehir; tarih ve saat (14.08.2026 21:30).
  - Kartlar ve ilk 11'ler (DEEP_RESEARCH §1.2).
- **İY skoru:** Ayrı bir alan olarak **görülmedi** [Y]. Gol dakikalarından türetilebilir: 45+ dakikalı goller ilk yarıya sayılır. Uzatma dakikası gösteriminin biçimi doğrulanmalı [D].
- **HTML seçicileri:** Araç ham HTML vermedi. Tablo id ve class adları **doğrulanamadı** [D].
  - Fikstür anchor'ı `macctl00_MPane_m_142_12495_ctnr_m_142_12495` biçiminde [Y]. Bu, ASP.NET WebForms'un ürettiği id'lere işaret ediyor. Bu id'ler sezon değişince değişebilir.
  - Öneri: Seçici yerine `a[href*="macId="]` linklerini regex ile toplayın. Ardından her maç sayfasından `macId` ve skoru okuyun.
- **Sayfa boyutu:** Haftalık sayfa yaklaşık 140-170 bin karakter metin içeriyor [Y], yani ağır bir sayfa.

### 1.3 Açık kaynak scraper'lar
- `siriiuss/TFF-Leagues-Scraper` / `TFF-api` ([dokümantasyon](https://siriiuss.github.io/TFF-Leagues-Scraper/)): Yalnızca puan durumu topluyor. URL ve seçici ayrıntısı dokümanda yok. Lisans belirtilmemiş [Y].
- `morphykutay/trendyol-super-lig-puan-cetveli-tff` ([ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fmorphykutay%2Ftrendyol-super-lig-puan-cetveli-tff)): Puan cetveli. İçeriği incelenmedi [D].
- `pageId=29&macId` kullanan, maç detayına inen bir GitHub projesi **bulunamadı**. Seçici örneği yok.

### 1.4 Engel riski ve sıklık
- GitHub Actions IP'leri (Azure) için engel kaydı bulunamadı [D].
- Altyapı ASP.NET. CDN/WAF görülmedi, ancak bu doğrulanmadı [D].
- Şartlardaki "izlenmektedir" ifadesi nedeniyle düşük hız ve açık bir User-Agent kullanılmalı. Örnek: `OZBET-bot/1.0 (+repo URL)`.
- **Önerilen sıklık:**
  - Hafta sayfası: Lig başına günde 1 kez, yalnızca son 2 hafta.
  - Maç detayı: Yalnızca yeni biten maçlar, istekler arası en az 5 sn. Yaklaşık 9+10 maç/hafta, yani haftada 20-40 istek.
  - Arşivin geriye doldurulması bir kez yapılmalı. Saatte 300 istek altında kalınmalı ve sonuç `data/` altında önbelleğe alınmalı.
  - Aynı macId bir daha istenmemeli.

## 2. Alternatifler
| Aday | Erişim izni | Alanlar | Güncellik | Actions engel riski | Sıklık |
|---|---|---|---|---|---|
| **openfootball/europe `turkey/`** ([repo](https://github.com/openfootball/europe)) | **CC0-1.0**, kısıtsız [Y] | Tarih, takımlar, skor. İY skoru dosyaya göre değişir. Hakem yok [O]. | Klasör içeriği ve son commit **doğrulanamadı**. Araç dizini açmadı [D]. Gönüllü güncelleme, gecikme olası [O]. | Çok düşük (raw.githubusercontent) | Günde 1 |
| **Wikipedia sezon sayfaları** (ör. [2025–26 TFF 1. Lig](https://en.wikipedia.org/wiki/2025%E2%80%9326_TFF_1._Lig)) | Metin CC BY-SA. Atıf ve aynı lisans gerekir [O]. robots.txt araçla okunamadı [D]. Wikimedia API'si açık User-Agent istiyor [O]. | 20x20 ev/deplasman skor matrisi var, sezon tam. **Tarih, İY skoru ve hakem yok** [Y]. | Sezon içinde gönüllü güncelleme, birkaç gün gecikebilir [O]. | Düşük (API ile) | Günde 1 (`action=parse`) |
| **worldfootball.net** | WebFetch'e `robots_disallowed` döndü [Y]. Şartlar incelenmedi. | Hakem ve İY skoru var [O] | — | — | **Kullanma** |
| **transfermarkt** | Araç siteyi engelli gösterdi (SITE_BLOCKED) [Y]. Şartlar ve robots **doğrulanamadı**. Otomatik toplamaya karşı bilinen bir tutumu var [O]. | Hakem, İY skoru [O] | — | Yüksek [O] | **Kullanma** |
| **Süper Lig resmi sitesi** | Bu çalışmada incelenmedi [D] | — | — | — | — |
| **football-data.co.uk** | Mevcut kaynak | T1 var. T2 yok [O]. 2025/26 T1'de `Referee` kolonu yok (SOURCES_RESEARCH §3). | — | — | — |

## 3. Öneri
1. **1. Lig sonuç arşivi:**
   - Birincil kaynak **tff.org**:
     - Arşiv için sezon pageID'leri (1772, 1731, 1649...) ve hafta sayfaları kullanılmalı.
     - Güncel sezon için `pageID=142&hafta=N`.
     - Skor hafta sayfasından okunmalı. İY skoru gerekiyorsa maç detayındaki gol dakikalarından türetilmeli.
   - Koşullar:
     - (a) Pipeline robots.txt'i okuyabilmeli ve Disallow bulunmamalı.
     - (b) OZBET ticari değil kalmalı. Reklam varsa TFF'den izin alınmalı.
     - (c) Sitede "Kaynak: TFF" atfı bulunmalı.
     - (d) §1.4'teki sıklık uygulanmalı.
   - Çapraz kontrol ve yedek: **openfootball** (CC0, risksiz). Önce `turkey/` klasöründe 1. Lig dosyalarının güncel olup olmadığı doğrulanmalı.
   - Wikipedia skor matrisi yalnızca sezon sonu doğrulaması için uygun. Tarih bilgisi olmadığından Dixon-Coles zaman ağırlığına uymaz.
2. **Süper Lig hakem verisi:**
   - **tff.org maç detayı** (`pageId=29&macId`) kullanılmalı. Hakem, VAR ve kartlar burada yapılandırılmış biçimde var. Başka uygun ücretsiz kaynak bulunamadı.
   - Hafta başına yaklaşık 9 istek yeterli. Atama haberleri serbest metin, gerek yok.
   - Maç öncesi hakemi için maç detay sayfası atama sonrası dolduruluyor olabilir, ancak bu doğrulanmadı [D].
   - Fayda esas olarak kart marketinde (DEEP_RESEARCH §1.2).
3. **Uygun olmayan kaynaklar:** worldfootball.net, transfermarkt, Flashscore ve ls.nesine.com.
4. **Uygulamadan önce açık noktalar:**
   - tff.org robots.txt içeriği.
   - Arşivde `hafta` parametresinin çalışması.
   - HTML seçicileri.
   - openfootball `turkey/` klasörünün güncelliği.
   - Süper Lig arşiv pageID'leri.

   Bunlar ilk uygulama denemesinde doğrulanmalı. Denemenin logu bu dosyaya eklenmeli.
