# 04 – İstatistik platformlarının maç analiz sayfaları ve OZBET maç detay şablonu

Ajan 4 · 6 Kasım 2026 · Kapsam: SofaScore, FotMob, Flashscore, WhoScored, FBref, Understat, Opta Analyst, Mackolik, Sahadan, ESPN, BBC Sport.

**Yöntem ve dürüstlük notu.** Shell'in internet erişimi yok. Bu yüzden robots.txt dosyaları, kullanım şartları ve literatür WebFetch/WebSearch ile kontrol edildi.
Sayfa bölümleri (1. başlık) için platformların maç sayfaları canlı olarak açılmadı. Bu kısım, platformların bilinen genel düzenine dayanıyor
ve **[G]** etiketiyle işaretlendi (G = genel gözlem, bu oturumda doğrulanmadı). Bir platform API'sini ya da sayfasını ileride okuyacak her ajan
önce bu satırları kendi gözüyle teyit etmeli. **[D]** etiketi, bu oturumda kaynağı açılarak doğrulanmış bilgiyi gösterir.

---

## 1. Platform bazında maç öncesi bölümleri

Kısaltmalar: 11 = muhtemel 11, Eks = eksikler, Form = form/momentum, H2H, Karş = takım karşılaştırma metrikleri,
Puan = oyuncu puanı, Hak = hakem, Hava = hava durumu, Oy = taraftar oyu, Oran = bahis oranı.

| Platform | 11 / Eks | Form | H2H | Karş. metrik | Puan | Hak | Hava | Oy | Oran | Veri tedarikçisi |
|---|---|---|---|---|---|---|---|---|---|---|
| SofaScore [G] | var / var | son 5 + "pregame form", momentum grafiği (canlı) | var | sezon ort. şut, topa sahip olma, xG (büyük ligler) | var (6,5 tabanlı) | var (kart ort.) | yok/yer yer | var ("Who will win?") | var (partner) | "veri sağlayıcılarımız" deniyor, isim yok [D] |
| FotMob [G] | var / var | son 5, takım formu | var | xG, xGA, şut, top. sah. (Opta'lı liglerde) | var | var | yer yer | var | yer yer | ToS'ta isim geçmiyor [D] |
| Flashscore [G] | var / var (eksik oyuncu listesi) | son maçlar, form | var | sınırlı | sınırlı | var | yok | yok | var (çok bahisçi) | kendi ağı (Livesport) – teyit edilmedi |
| WhoScored [G] | var / var (sakat/cezalı) | var | var | şut, top. sah., pas %, hava topu, "güçlü/zayıf yönler" | var (Opta tabanlı) | var | yok | yok | var (oddschecker ile aynı grupta) [D] | Opta [G]; FairPlay Sports Media ağı [D] |
| FBref [G] | maç raporu sonrası kadro | maç günlükleri | var | Ocak 2026'dan beri gelişmiş (Opta) veriler kaldırıldı [D] | yok | var | yok | yok | yok | Opta erişimi 20.01.2026'da sona erdi [D] |
| Understat [G] | maç sonrası | xG trendi | sınırlı | xG, xGA, npxG, PPDA, deep | yok | yok | yok | yok | yok | kendi xG modeli; site şu an "geri döneceğiz" sayfası veriyor [D] |
| Opta Analyst [D] | yok (metin içinde) | var | var | şut, gol, dönüşüm, xG farkı | ayrı makale (Opta Player Ratings) | yok | yok | yok | yok | Opta (kendisi) |
| Mackolik [G] | var / var | var | var | temel (gol ort., Ü/A %) | yok/sınırlı | var | yok | var (tahmin) | var (iddaa) | Perform Group 2013'te Mackolik sahibiydi [D]; bugünkü tedarikçi teyit edilmedi |
| Sahadan [G] | var / var | var | var | temel | yok | var | yok | yok | var (iddaa) | teyit edilmedi |
| ESPN [G] | var | var | var | sezon şut/top. sah. | yok | yer yer | yok | yok | yer yer (ABD) | teyit edilmedi |
| BBC Sport [G] | var (maç günü) | son 6 | var | maç içi top. sah./şut | taraftar puanı (maç sonu) | yer yer | yok | yok | yok | teyit edilmedi |

Kaynaklar:
- SofaScore puan mantığı (6,5 başlangıç, maç içinde ~60 güncelleme, "data providers" ifadesi): https://www.sofascore.com/news/sofascore-rating
- WhoScored'un FairPlay Sports Media ağında oddschecker ile birlikte olması: https://www.fairplaysportsmedia.com/insights/ai-predictive/player-ratings-infrastructure-whoscored-b2b-data-layer
- FBref'ten Opta verisinin 20 Ocak 2026'da kaldırılması: https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html
- Opta Analyst ön izleme içeriği (simülasyon olasılığı, form, H2H, xG farkı; oran yok): https://theanalyst.com/2025/04/premier-league-match-predictions
- Opta Player Ratings: https://theanalyst.com/eu/2023/07/introducing-opta-player-ratings-premier-league-star-players-in-2022-23/
- Mackolik–Perform–Opta ilişkisi: https://webrazzi.com/2013/07/09/perform-group-opta-talip-oldu/ , https://en.wikipedia.org/wiki/Stats_Perform
- Understat erişim durumu (6 Kasım 2026'da robots.txt yerine bakım sayfası döndü): https://understat.com/robots.txt

**Ortak veri modeli (çıkarım).** Bütün büyük platformlar aynı iskeleti kuruyor: `Match` (lig, tarih, saha, hakem) → `Lineup`
(muhtemel/kesin 11, eksikler, gerekçe) → `TeamForm` (son N maç, iç/dış ayrımı) → `H2H[]` → `TeamSeasonStats` (ortalamalar) →
`PlayerRating` → `Prediction` (model olasılığı ve/veya taraftar oyu) → `Odds`. Aralarındaki fark verinin derinliğinde: olay verisi
(Opta veya kendi toplama ağları) olanlar xG, PPDA ve oyuncu puanı veriyor. Olmayanlar (Mackolik, Sahadan, Flashscore) sonuç ve oran
merkezli kalıyor. OZBET'in mevcut `Match` şeması ikinci gruba yakın ama model çıktısı tarafında birinciden zengin.

---

## 2. Hangi metrik tahmin gücü taşıyor, hangisi süs?

| Metrik | Hüküm | Gerekçe ve kaynak |
|---|---|---|
| Kapanış oranı (marjsız) | **En güçlü tek gösterge** | Ortalama bahisçi olasılığı gerçek sonuçlarla çok yakın örtüşüyor; yazarlar yalnızca oranların kendisiyle küçük kâr elde etti, ama gerçek para örneği küçük ve p≈0,089. https://arxiv.org/pdf/1710.02824 . OZBET'in kendi backtest'i de aynı sonucu veriyor (README: kapanış Brier 0,5732 < model 0,5895). |
| İsabetli şut, toplam şut, korner | **Güçlü** | Gözlenen maç istatistikleri, gol sayısından daha bilgi verici; isabetli şut en bilgilisi. Oran olasılığına eklendiğinde bile katkı sağlıyor. https://arxiv.org/pdf/2001.09097 (Wheatcroft). Bu sütunlar football-data.co.uk'te zaten var. |
| xG / xGA (son 10-20 maç) | **Güçlü, gol üzerinde ek bilgi** | xG, gelecekteki gol farkını gerçekleşen golden daha istikrarlı tahmin eden bir "şut kalitesi" ölçüsü olarak literatürde yaygın kabul görüyor (ör. https://pmc.ncbi.nlm.nih.gov/articles/PMC10075453 – bu oturumda tam metin açılamadı, captcha). Wheatcroft xG'yi doğrudan test etmedi; bu yüzden OZBET'teki 0,35 ağırlık backtest'le ayarlanmalı. |
| Eksik/kilit oyuncu | **Orta–güçlü** ama ölçmesi zor | Piyasa bunu hızla fiyatlıyor; ham "eksik sayısı" yerine oyuncunun dakika payı/değeri ile ağırlıklandırılmalı (Transfermarkt değeri, dcaribou veri seti). Doğrudan literatür kaynağı bu oturumda bulunmadı. |
| Elo / güç puanı | **Güçlü** (özellikle lig dışı maçlarda) | OZBET zaten ClubElo kullanıyor; clubelo.com/API bu oturumda okunamadı. |
| Form (son 5 G/B/M) | **Zayıf**, çoğunlukla süs | Kısa seri gürültülü; xG ve Elo'nun içinde zaten var. Gösterilebilir ama modele ayrı girdi olmamalı. Bu hüküm için tek bir kaynak bulunamadı, çıkarımdır. |
| H2H | **Zayıf**, süs | Örneklem çok küçük, kadrolar değişiyor. Çıkarımdır, doğrudan kaynak bulunamadı. |
| Topa sahip olma | **Zayıf**, bağlama bağlı | Topa sahip olmayla kazanma arasındaki ilişki tutarsız ve skor durumuna bağlı (FIFA araştırma serisi: https://www.fifatrainingcentre.com/en/community/fifa-research/possession-analysis/part-1-1-the-relationship-between-possession-and-winning.php ; sistematik derleme: https://pmc.ncbi.nlm.nih.gov/articles/PMC8929629 – tam metin captcha nedeniyle okunamadı). |
| PPDA | **Stil göstergesi**, doğrudan sonuç tahmini zayıf | Pres yoğunluğunu anlatıyor. Kart/faul ve korner marketleri için bağlam olarak işe yarar; 1X2 için kanıt bulunamadı. |
| Hakem | **Kart marketi için orta**, 1X2 için süs | Ev sahibi seyircisi hakemlerin kart kararlarını etkiliyor; seyircisiz 2020-21 sezonunda bu etki kayboldu. https://www.wlv.ac.uk/news-and-events/latest-news/2022/november-2022/research-shows-crowds-hold-the-cards-in-referees-decisions.php . football-data.co.uk İngiltere için `Referee` sütunu veriyor. |
| Hava durumu | **Süs** (aşırı koşullar hariç) | Bu oturumda Ü/A üzerinde güçlü etki gösteren güvenilir bir çalışma bulunamadı. "Bilgi" kutusu olarak kalsın. |
| Oyuncu puanı (6,5 tabanlı vb.) | **Süs / geriye dönük** | Maç içinde oluşan, tescilli algoritmalar; maç öncesi tahmin için girdi değil. https://www.sofascore.com/news/sofascore-rating |
| Taraftar oyu | **Süs**; en fazla "kalabalık görüşü" | Piyasa oranı aynı bilgiyi daha iyi taşıyor. OZBET'in konsensüs ajanı zaten bunun daha iyi bir karşılığı. |

---

## 3. Veri tedarikçileri ve ücretsiz/yasal karşılıklar

- **Opta / Stats Perform**: FBref, WhoScored ve Opta Analyst'in temeli. Lisansı pahalı ve sıkı: Opta, Ocak 2026'da Sports Reference'ın
  erişimini kesip verinin silinmesini istedi; aynı dönemde Stats Perform FIFA'nın resmi bahis verisi dağıtıcısı oldu.
  https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html
- **Sportradar / Genius**: bahis odaklı resmi veri. Ücretli; bu oturumda ücretsiz katman araştırılmadı.
- **StatsBomb**: ticari ürünün yanında GitHub'da açık veri var. https://github.com/statsbomb/open-data
- **Wyscout (Hudl)**: 2017/18 sezonuna ait 5 büyük lig + DK 2018 + Euro 2016 olay verisi, CC BY 4.0, figshare.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6817871 , https://figshare.com/collections/Soccer_match_event_dataset/4415000/2

Ücretsiz verilerin hiçbiri canlı Süper Lig xG'si sağlamıyor. Gerçekçi yasal yol şu: **sonuç + şut + korner + kart + hakem + oran**
için football-data.co.uk, **kadro değeri ve dakika** için dcaribou/transfermarkt-datasets, **fikstür** için openfootball, **xG modeli
eğitmek** için StatsBomb/Wyscout açık olay verisi. Bu verilerle kendi basit xG'mizi kurabiliriz (şut konumu → olasılık), ama canlı Süper Lig
şut konumu verisi yasal ve ücretsiz bir kaynakta yok. Kısa vadede xG yalnızca "5 büyük lig, kaynak erişilebilirse" kalmalı.

### Veri seti ayrıntıları
- **football-data.co.uk**: Ev/deplasman şut, isabetli şut, korner, faul, sarı/kırmızı, ofsayt, hakem (İngiltere), çok sayıda bahisçinin
  açılış ve kapanış oranları (Pinnacle, B365, Max/Avg, Ü/A 2,5, Asya handikap). Notlar sayfasında açık bir lisans metni yok; kaynak gösterip
  makul kullanım uygun. https://www.football-data.co.uk/notes.txt . Türkiye (T1) dahil; Türkiye dosyalarında maç istatistiği sütunları
  yok ya da sınırlı olabilir, teyit edilmeli [G].
- **openfootball/football.json**: CC0 (kamu malı). İngiltere 4 lig, Almanya 3, İspanya/İtalya/Fransa 2'şer lig; 2010-11'den 2026-27'ye.
  Son iki sezon her gün 05:00 UTC'de GitHub Action ile güncelleniyor. https://github.com/openfootball/football.json
- **StatsBomb Open Data**: araştırma ve kişisel ilgi için serbest; yayında StatsBomb'u kaynak göstermek ve logosunu koymak gerekiyor.
  Lisans ayrıntısı LICENSE.pdf'te (bu oturumda açılmadı). Kapsam `data/competitions.json`'da. https://github.com/statsbomb/open-data
- **Wyscout public dataset**: CC BY 4.0, 1.941 maç, ~3,25 milyon olay, statik (2017/18). https://pmc.ncbi.nlm.nih.gov/articles/PMC6817871
- **dcaribou/transfermarkt-datasets**: CC0, 12 tablo (maçlar, kadrolar, dizilişler, oyuncu değerleri, transferler), 88 bin+ maç.
  **Güncellemeler durdu**: veri 6 Temmuz 2026'da kalıyor, 2026/27 kadroları yok. Erişim: Kaggle, DuckDB dosyası, zip, uzaktaki CSV'ler.
  https://github.com/dcaribou/transfermarkt-datasets
- **worldfootballR / worldfootballR_data**: R paketi (FBref, Transfermarkt, Understat). FotMob desteği, FotMob kullanım şartları değiştiği için
  kaldırıldı. Veri deposu 18 Eylül 2025'te arşivlendi ve bakımı bitti. https://github.com/JaseZiv/worldfootballR
- **soccerdata (Python)**: ClubElo, ESPN, FBref, football-data.co.uk, Sofascore, SoFIFA, Understat, WhoScored kazıyıcıları. Paket,
  kullanıcının sitelerin şartlarına uymasını istiyor ve sorumluluk kabul etmiyor. Yani bir kazıyıcının pakette bulunması, o siteden veri
  çekmenin yasal olduğu anlamına gelmiyor. https://pypi.org/project/soccerdata/
- **Kaggle**: Toplu setlerin çoğu yukarıdakilerin kopyası (ör. dcaribou "player-scores"). Lisansı her sette ayrı kontrol edilmeli.
- **TFF resmi istatistikler**: tff.org'da maç raporu, kadro ve hakem atamaları yayımlanıyor (haftalık hakem listeleri basına TFF
  duyurusuyla geçiyor: https://www.cnnturk.com/spor/futbol/tff-duyurdu-iste-haftanin-hakemleri-2179908). Açık lisans, API veya
  robots.txt bu oturumda doğrulanamadı. Hakem bilgisi için en güvenilir resmi kaynak, ama otomatik erişimden önce şartları okunmalı.

---

## 4. robots.txt ve kullanım şartları

| Site | robots.txt (6 Kasım 2026) | Kullanım şartı | OZBET kararı |
|---|---|---|---|
| FotMob | `User-agent: *` için `/api/*` yasak; yalnızca Googlebot, Bingbot, Qwantbot, AmazonAdBot API'ye girebiliyor [D] https://www.fotmob.com/robots.txt | Kazıma, bot, toplu çekme ve izinsiz ticari kullanım açıkça yasak; lisans kişisel ve ticari olmayan kullanım için [D] https://www.fotmob.com/tos.txt | **ÇEKİLMEYECEK** (teyit edildi) |
| SofaScore | robots.txt bu oturumda alınamadı (istemci hatası) | Şart metni bu oturumda okunamadı. Ticari kazıyıcı hizmetlerinin varlığı yasal olduğunu göstermez | **ÇEKİLMEYECEK** (görev kuralı; ayrıca teyit edilemedi) |
| OddsPortal | `*/match-event/*`, `*/feed/*`, `ajax-*` uçları, takım ve "nextgames-odds" uçları, 1998-2024 yıllı URL'ler yasak [D] https://www.oddsportal.com/robots.txt | Okunmadı | **ÇEKİLMEYECEK** |
| Flashscore | `/live/`, `/finished/`, `/scheduled/`, `/standings/`, gün kaydırmalı URL'ler herkese yasak; birçok yapay zekâ botu tamamen engelli [D] https://www.flashscore.com/robots.txt | Okunmadı | Mevcut "son yedek" kullanımı yeniden değerlendirilmeli (bkz. not) |
| WhoScored | Yalnızca hesap, tahmin ve kullanıcı yolları yasak [D] https://www.whoscored.com/robots.txt | Okunmadı; Opta lisanslı veri | Önerilmez: lisanslı veri yeniden yayımlanamaz |
| FBref / Sports Reference | robots.txt alınamadı | Siteyi yavaşlatan otomatik erişim, rakip veri tabanı veya hizmet kurmak, ve yapay zekâ modellerine girdi olarak kullanmak yasak [D] https://www.sports-reference.com/data_use.html | **ÇEKİLMEYECEK**; zaten Opta verisi kalktı |
| Understat | robots.txt yerine bakım sayfası [D] | Okunmadı | Hâlihazırda "erişilebilirse" kipinde; kesintiye dayanıklı kalmalı |

**Not (Flashscore):** ARCHITECTURE.md'de Flashscore bülten için son yedek ve kadro kaynağı olarak geçiyor. robots.txt, `/live/`,
`/finished/` ve `/scheduled/` gibi liste sayfalarını açıkça kapatıyor. Maç sayfaları ve iç uçlar için kullanım şartları ayrıca
okunmalı; okununcaya kadar Flashscore adapter'ını devre dışı bırakmak en güvenli yol. Karar ana oturuma ait.

---

## 5. OZBET maç detay sayfası v3 şablonu

Sıra, "en çok karar etkileyen bilgi önce" ilkesine göre. Her bölüm `Match` şemasındaki alana bağlı. Yeni alanlar **yeni** diye işaretli.

| # | Bölüm | Gösterilecek veri | Kaynak (yasal) | Not |
|---|---|---|---|---|
| 1 | Başlık şeridi | Lig, saat, iddaa kodu, MBS, stat, **hakem (yeni)** | Nesine/iddaa (mevcut); hakem: TFF duyurusu / football-data `Referee` | Hakemsiz de çalışmalı |
| 2 | OZBET Tercihi + güven | Harman olasılık (0,25 model + 0,75 piyasa), yıldız, "Değerli" etiketi | Mevcut model + piyasa | Uyarı metni sabit |
| 3 | Olasılık paneli | 1/X/2, Ü/A, KG; **model – piyasa – konsensüs** üç sütun yan yana | Mevcut `model`, `market`, konsensüs | Literatürde en güçlü bölüm budur |
| 4 | Oran hareketi | Açılış → son oran çizgisi, düşen oran alarmı | Mevcut `odds_history` | |
| 5 | Kadro durumu | Muhtemel 11 (varsa), eksikler + **önem ağırlığı (yeni)**: dakika payı / piyasa değeri | Eksik: mevcut kadro ajanı; ağırlık: transfermarkt-datasets (6 Tem 2026'ya kadar) | Muhtemel 11 için yasal ücretsiz kaynak yok; yoksa bölümü gizle |
| 6 | Takım karşılaştırma | **Tahmin gücü sırasıyla**: Elo, xG/xGA (5 lig), isabetli şut ve şut ortalaması (**yeni**), korner, gol ort., Ü/A %, KG % | football-data.co.uk (şut/korner), Understat (erişilirse), ClubElo | Topa sahip olma ve PPDA yok (yasal kaynak yok, gücü zayıf) |
| 7 | Skor dağılımı | En olası 5 skor, 6×6 ısı haritası, toplam gol dağılımı, İY/MS | Mevcut `model` | |
| 8 | Form | Son 5 genel + iç/dış saha, gol çizgisi | football-data / openfootball | Küçük, "bilgi" stilinde |
| 9 | Kart ve korner köşesi (**yeni**) | Takım kart ort., hakemin maç başına kart ort. (varsa), korner ort. | football-data `HY/AY/HR/AR/HC/AC/Referee` | Kart/korner marketi eklenirse modele girdi |
| 10 | H2H | Son 5-6 maç | Mevcut `stats.h2h` | Altta, "küçük örneklem" notuyla |
| 11 | Haberler | Mevcut `news` | Mevcut haber ajanı | |
| 12 | Model notları ve veri kalitesi | `data_quality`, `method`, kaynak durumu, eksik kaynak uyarısı | `status.json` | Şeffaflık |
| – | Bilinçli olarak YOK | Oyuncu puanı, taraftar oyu, hava durumu | – | Tahmin gücü yok ya da yasal kaynak yok |

Şema eklentisi önerisi: `match.referee: {name, cards_pg?, n?}`, `stats.{home,away}.shots_avg`, `sot_avg`, `elo`,
`squad.*.missing[].weight`. Hepsi opsiyonel olmalı; yoksa UI bölümü gizlesin.

---

## 6. Ücretsiz/yasal veri setleri tablosu

| Ad | Kapsam | Lisans | Güncellik | Erişim | OZBET'e katkısı | Emek |
|---|---|---|---|---|---|---|
| football-data.co.uk | ~20+ Avrupa ligi (T1 dahil), çok sezon; sonuç, şut, korner, kart, hakem (ENG), açılış/kapanış oranları | Açık lisans metni yok; kaynak gösterilerek kullanım | Sezon içinde düzenli (mevcut sistem kullanıyor) | CSV indirme | Şut/isabetli şut/korner/kart/hakem girdileri, kapanış oranıyla backtest | S |
| openfootball/football.json | ENG 4, GER 3, ESP/ITA/FRA 2 lig; 2010-11 → 2026-27 | CC0 | Günlük 05:00 UTC (son 2 sezon) | GitHub raw JSON | Fikstür/sonuç yedeği, ad eşleme | S |
| StatsBomb Open Data | Seçili turnuvalar/sezonlar (competitions.json) | Kendi lisansı (LICENSE.pdf); atıf + logo şartı | Ara ara yeni sezon eklenir | GitHub JSON, `statsbombpy` | Kendi xG modelini eğitmek | M |
| Wyscout public (Pappalardo vd.) | 5 büyük lig 2017/18, DK 2018, Euro 2016; 1.941 maç | CC BY 4.0 | Statik | figshare JSON | xG/olay modeli eğitimi, doğrulama | M |
| dcaribou/transfermarkt-datasets | 88 bin+ maç, kadrolar, dizilişler, piyasa değerleri, transferler | CC0 | **Durdu** (6 Tem 2026'ya kadar) | Kaggle, DuckDB, zip, uzak CSV | Eksik oyuncu önem ağırlığı, kadro değeri | M |
| worldfootballR_data | FBref/Transfermarkt hazır tablolar | Belirtilmemiş | **Arşivlendi** (18 Eyl 2025) | GitHub | Sadece tarihsel; önerilmez | – |
| soccerdata (Python paketi) | 8 kaynak için kazıyıcı | Paket açık kaynak; veriler kaynağın şartına bağlı | Paket güncel | pip | Yalnızca ClubElo ve football-data okuyucusu olarak; FBref/Sofascore/WhoScored modülleri kullanılmaz | S |
| Kaggle setleri | Değişken | Set bazında | Değişken | Kaggle API | Ek tarihsel veri; lisans tek tek kontrol | S–M |
| ClubElo | Avrupa kulüpleri, günlük Elo | Bu oturumda doğrulanamadı | Günlük | CSV API (mevcut) | Güç puanı, kupa maçları | S (mevcut) |
| TFF resmi | Süper Lig kadro, hakem, maç raporu | Doğrulanmadı | Haftalık | Web sayfası (API yok) | Süper Lig hakem ataması | M |

---

## Kaynakça (ek)
- Wheatcroft, maç istatistikleriyle tahmin: https://arxiv.org/pdf/2001.09097
- Kaunitz vd., bahisçi oranları: https://arxiv.org/pdf/1710.02824
- Wyscout veri seti makalesi: https://pmc.ncbi.nlm.nih.gov/articles/PMC6817871
