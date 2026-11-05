# OZBET — Derin Araştırma Raporu

Tarih: 2026-11-05 · Hazırlayan: Derin Araştırma Ajanı (yalnızca WebSearch + WebFetch; ek olarak depodaki `data/latest.json` ve `data/backtest.json` okundu)

Güven etiketleri: **[Y]** yüksek = birincil kaynakta / canlı sayfada görüldü · **[O]** orta = ikincil kaynak, özet ya da kısmi gözlem · **[D]** düşük = çıkarım, doğrulanmalı. Kaynağı bulunamayan iddia yazılmadı. ClubElo, RSS haber toplama ve TR2 sonuç arşivi başka ajanlarda; burada yalnızca ek notlar var.

---

## 0. Önce şu iki bulgu (en önemli kısım)

1. **Modelimiz, yayınlanmış Dixon-Coles sonuçlarıyla aynı seviyede. Piyasayla aradaki fark yapısal.** 2026'da yayımlanan bir Serie A çalışması (19 sezon, test n=2.660) Dixon-Coles için Brier **0,5862**, Shin yöntemiyle marjı temizlenmiş kapanış oranı için **0,5717** buldu. Fark 0,0145. Bizde fark 0,5895'e karşı 0,5732, yani 0,0163. Aynı çalışmada piyasayla log-opinion-pool kurulduğunda modele düşen optimal ağırlık **0,000** çıkıyor. Şut isabeti (SOT) eklenmiş varyant gol modeline bilgi katıyor (ağırlık 0,35), ama piyasaya karşı yine 0 ağırlık alıyor. [Y] [arXiv 2608.11505](https://arxiv.org/abs/2608.11505)
   → Bizim `blend_brier` serimiz (1,0 → 0,25 ağırlıkta 0,5895 → 0,5767) aynı şeyi gösteriyor: ağırlık sıfıra yaklaştıkça sonuç iyileşiyor.
2. **iddaa marjı, "değer" eşiğini fiilen kapatıyor. Backtest ise bunu ölçmüyor.**
   - `data/latest.json` (5 Kasım, 74 maç) üzerinden hesapladığım 1X2 marjı: medyan **%23,0**. MBS1 olan UEL/UECL maçlarında **%18,7**, MBS3 maçlarda **%23,3**. Ü/A 2,5 marjı medyan **%19,0**. [Y, kendi verimiz. O gün Süper Lig maçı yoktu.]
   - Pinnacle kendi futbol marjını 1X2'de **~%2**, toplam gol marketinde %2,5 olarak veriyor ve sektör ortalaması için %6 diyor. [Y] [Pinnacle destek](https://pinnaclesports.freshdesk.com/support/solutions/articles/1000189654-how-do-i-calculate-betting-margins-)
   - `backtest.json` yönteminde değer bahsi **football-data `Avg` oranlarıyla** oynanıyor. Bu oranların marjı birkaç yüzde düzeyinde. Aynı bahisler iddaa oranıyla oynansaydı, ROI kabaca **ek −%12…−%17** kötüleşirdi. Bu, ~%19–23 marjdan türetilmiş bir çıkarım [O].
   - **Kod riski:** `pipeline/ozbet/agents/value.py`, "Değerli" etiketini `model_p − ima_p ≥ 0,05` koşuluyla veriyor. Buradaki `ima_p` marjı temizlenmiş olasılık. Bu kural `ev > 0` şartını aramıyor. Örnek: ima_p=0,50, marj=%20 ve model_p=0,55 iken iddaa oranı ≈1,67 olur ve EV = 0,55×1,67−1 ≈ **−%8**. Yani model doğru olsa bile etiket negatif beklentili bahse verilebilir. [Y, kod okuması + aritmetik]

---

## 1. Ücretsiz ve otomatik erişilebilir ek veri kaynakları

### 1.1 xG / şut verisi
| Kaynak | Uç nokta / URL | Alanlar | robots / ToS | GH Actions engel riski | OZBET faydası |
|---|---|---|---|---|---|
| **football-data.co.uk (zaten var)** | `mmz4281/{YYZZ}/T1.csv` vb. | `HS/AS` (şut), `HST/AST` (isabetli şut), `HC/AC` (korner), `HY/AY/HR/AR`, notes.txt'e göre "mevcutsa" `Referee` | Kişisel kullanım, bot/ticari kullanım yok [Y] ([data.php](https://www.football-data.co.uk/data.php), [notes.txt](https://www.football-data.co.uk/notes.txt)) | Düşük, zaten çalışıyor | **En yüksek.** Süper Lig dahil 6 ligde şut ve isabetli şut var, yani "xG vekili" hiç yeni kaynak gerektirmeden kurulabilir |
| **FotMob** | `www.fotmob.com/api/matchDetails?matchId=`, `/api/leagues?id=`, `/api/matches?date=YYYYMMDD` ([Public-FotMob-API](https://gh.r-mj.com/pseudo-r/Public-FotMob-API)) [O] | Şut haritası + `expectedGoals`, takım ve oyuncu xG, kadrolar, hakem ([Apify aktör açıklaması](https://apify.com/abotapi/fotmob-scraper.md)) [O]. Süper Lig lig sayfası mevcut: id **71** ([fotmob.com/leagues/71](https://www.fotmob.com/leagues/71/stats/super-lig)) [Y] | robots.txt `User-agent: *` için `Disallow: /api/*` [Y] ([robots](https://www.fotmob.com/robots.txt)). ToS robot, spider ve "sistematik/düzenli/toplu veri çekmeyi" yasaklıyor, lisans kişisel ve ticari olmayan kullanımla sınırlı [Y] ([tos.txt](https://www.fotmob.com/tos.txt)). İmzalı `X-Fm-Req` başlığı istenebiliyor; sır anahtarı JS'te gömülü [O] ([analiz](https://viktornilsson.github.io/security/2024/11/01/fotmob-auth.html)). worldfootballR, FotMob fonksiyonlarını ToS değişikliği sonrası kaldırdı [O] ([reddit](https://reddit.rtrace.io/r/sportsanalytics/comments/1csr21n/worldfootballr_and_fotmob)) | Orta-yüksek | Teknik olarak Süper Lig xG'sinin tek ücretsiz yolu, fakat **ToS ve robots açıkça karşı.** Önerilmez |
| **fbref** | `fbref.com/en/comps/26/...` | Opta, **20 Ocak 2026**'da gelişmiş verilere erişimi sonlandırdı ve verilerin silinmesini istedi. Temel istatistikler duruyor [Y] ([Awful Announcing](https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html), [veri ekosistemi haritası](https://withqwerty-www.pages.dev/stories/data-ecosystem-sources)). Süper Lig sayfasında xG kolonu yok [Y] ([fbref Süper Lig](https://fbref.com/en/comps/26/Super-Lig-Stats)) | — | — | **xG kaynağı olarak artık işe yaramaz.** penaltyblog/soccerdata gibi kütüphanelerin fbref xG kazıyıcıları da bu yüzden boş döner [O] |
| **Sofascore** | `api.sofascore.com/api/v1/...` (kütüphaneler üzerinden) | Maç istatistikleri, xG, kadrolar, hakem istatistikleri (maç sayısı, sarı/kırmızı kart, penaltı) ([Crawlora aracı](https://glama.ai/mcp/servers/Crawlora-org/crawlora-mcp/tools/sofascore_referee_statistics)) [O] | robots okunamadı. Cloudflare ve TLS parmak izi kontrolü var; düz `requests` 403 alıyor, `curl_cffi` taklidi gerekiyor [O] ([pysofascore](https://pypi.org/project/pysofascore/)). Eylül 2026'dan beri eski Chrome UA'larına `403 {"reason":"challenge"}` dönüyor; veri merkezi IP'leri ilk istekte sık reddediliyor [O] ([Apify changelog](https://apify.com/incognito_mode/sofascore-season-stats-scraper/changelog.md)) | **Yüksek** (Actions = veri merkezi IP'si) | Koruma aşmak gerekir; projenin "korumayı aşma" ilkesine aykırı. Önerilmez |
| **FootyStats** | Web: `footystats.org/turkey/super-lig/xg`. API: anahtarlı | Takım xG, xGA, xG farkı (web) [Y] ([sayfa](https://footystats.org/turkey/super-lig/xg)). API'nin ücretsiz planı **yalnızca Premier League** kapsıyor, saatte 180 istek [Y] ([API](https://footystats.org/api/)) | robots `*` için `/api/*`, `/matches?*`, `/team-stats?*` gibi yolları kapatıyor. Lig xG sayfası yasaklı listede değil [Y] ([robots](https://footystats.org/robots.txt)). Kart, korner ve Ü/A tabloları Premium arkasında [Y] | Orta | Haftada 1 kez lig xG tablosu (sezon toplamı) okunabilir. Maç bazlı xG değil, bu yüzden model girdisi olarak sınırlı |
| **Understat** | (mevcut adapter) | — | Bakımda; Süper Lig yok | — | Değişiklik yok |

**Sonuç:** Süper Lig için ToS'a uygun, maç bazlı, ücretsiz bir xG kaynağı **bulunamadı**. En dürüst ve en ucuz yol: football-data'daki `HST/AST` (+`HS/AS`) ile şut tabanlı güç hesabı (§2.3).

### 1.2 Hakem istatistikleri
- **TFF maç detay sayfası** [Y]: `https://www.tff.org/Default.aspx?pageId=29&macId={id}`. Oynanmış bir maçta (macId=317790) şunlar görüldü: hakem, 1. ve 2. yardımcı, 4. hakem, **VAR/AVAR**, gözlemci, stat adı, goller (dakika ile), **kartlar (dakika ile)**, ilk 11'ler, yedekler, değişiklikler. Oynanmamış maçta ise yalnızca stat, tarih ve `stadId` var. Haftalık fikstür sayfasındaki `macId` linkleri buraya bağlanıyor ([fikstür](https://tff.org/Default.aspx?498pg=12&pageID=80)). Hakem atamaları ayrı bir haber olarak yayımlanıyor (`pageID=248&ftxtID=...`) [Y]. robots.txt okunamadı.
  - Fayda: Hakem başına maç başı kart ve penaltı ortalaması, TR1 için **ücretsiz ve resmi** kaynaktan kurulabilir. Aynı sayfa ilk 11 arşivi de sağlar (§3). 1. Lig maçları da aynı sistemde; TR2 arşivi ajanı için not.
- **football-data `Referee` kolonu:** notes.txt'te "mevcutsa" diye geçiyor; lig listesi verilmemiş [O]. Bildiğim kadarıyla İngiltere dosyalarında var, T1'de yok. 2025/26 T1 başlığında `Referee` kolonu bulunmuyor [Y, SOURCES_RESEARCH.md §3].
- **Model değeri:** Kart marketleri iddaa'da var. 1X2 ve gol marketlerine etkisi literatürde zayıf. Hakem etkisi daha çok kartlarda görülüyor (ev sahibine daha az kart, kısmen skor durumuyla açıklanıyor) [Y] ([Buraimo, Forrest & Simmons 2010, JRSS-A](https://econpapers.repec.org/RePEc:bla:jorssa:v:173:y:2010:i:2:p:431-449)). OZBET kart marketi sunmuyorsa öncelik düşük.

### 1.3 Hava durumu — Open-Meteo
- Uç nokta [Y]: `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m,precipitation,wind_speed_10m&timezone=auto` (`forecast_days` 0–16). Geçmiş tahmin için `https://historical-forecast-api.open-meteo.com/v1/forecast`, 2022'den itibaren ([docs](https://open-meteo.com/en/docs), [historical-forecast](https://open-meteo.com/en/docs/historical-forecast-api)).
- Şartlar [Y]: Anahtar gerekmez. Günde <10.000, saatte 5.000, dakikada 600 çağrı. **Ticari olmayan kullanım şartı var:** abonelik ya da reklam içeren site ticari sayılıyor. CC BY 4.0 atıf zorunlu ([terms](https://open-meteo.com/en/terms)). GH Actions engel riski düşük.
- **Stat koordinatı:** TFF maç sayfasındaki `stadId` + stat adı, bir kez elle hazırlanmış `stadiums.json` (Wikipedia "List of football stadiums in Turkey" ile) [O] ([Wikipedia](https://en.wikipedia.org/wiki/List_of_football_stadiums_in_Turkey)). Wikidata SPARQL (P115 "home venue", P625 koordinat) da bir seçenek, ancak bu oturumda doğrulanmadı [D].
- **Fayda: düşük.** Gol sayısında mevsimsellik var: EFL alt liglerinde zirve (Ekim, 2,67) ile dip (Şubat-Mart, 2,45) arası ~0,2 gol ve Ü2,5 oranında ~6 puan fark. Bu doğrudan hava ölçümü değil [O] ([Racing Post, Pullein](https://www.racingpost.com/sport/opinion/scores-change-with-the-weather-at-lower-altitudes-in-the-efl-agNLS6y4suYc/)). Piyasa bu bilgiyi büyük olasılıkla fiyatlıyor. Yalnızca maç kartında "yağış/rüzgâr" bilgi rozeti olarak değerli.

### 1.4 Dinlenme günü, yorgunluk ve seyahat
- **Veri:** Ek kaynak gerekmiyor. Flashscore fikstürü ve football-data tarihleriyle "son maçtan bu yana gün" ve "son 14 günde maç sayısı" hesaplanabilir. Seyahat için stat koordinatları üzerinden haversine mesafesi.
- **Kanıt:** Scoppa'nın Dünya Kupası ve Euro verisiyle yaptığı çalışma, güncel turnuva yapısında dinlenme günü farkının **anlamlı etkisi olmadığını** buldu. Etki yalnızca rakiplerden birinin ≤3 gün dinlendiği durumda ortaya çıkıyor [Y] ([IZA DP 7519 / J. Sports Econ. 2015](https://www.iza.org/publications/dp/7519)). Kulüp düzeyinde Avrupa kupası yorgunluğu üzerine 20 yıllık bir çalışmanın özeti "her zaman kötü sonuç anlamına gelmez" diyor; sayısal sonuçlarını okuyamadım [D] ([kayıt](https://lida.sport-iat.de/dfb/Record/4078166?lng=en)).
- **Fayda: düşük-orta.** Ucuz bir özellik. Etkisini 2 sezonluk backtest'te ölçmeden modele sokmayın.

### 1.5 Oran geçmişi
| Kaynak | Durum | robots / ToS | Not |
|---|---|---|---|
| **OddsPortal** | Sonuç sayfası WebFetch'le açıldı, 1X2 oranları HTML'de var [O] ([TR sonuçları](https://www.oddsportal.com/football/turkey/super-lig/results/)) | robots `*` için `ajax-*`, `feed`, `match-event` yollarını ve **`-1998…-2024` yıl içeren URL'leri** kapatıyor [Y] ([robots](https://www.oddsportal.com/robots.txt)). ToS 2.11 "kazıma, toplama, yeniden oluşturma"yı ve otomatik isteklerle sunucuya yük bindirmeyi yasaklıyor; veriler veritabanı olarak korunuyor [Y] ([terms](https://www.oddsportal.com/terms/)) | OddsHarvester (Playwright) gibi araçlar var [O] ([GitHub](https://github.com/jordantete/OddsHarvester)), ama ToS'a aykırı. **Önerilmez** |
| **BetExplorer** | Süper Lig ve **1. Lig 2026/27** sonuç sayfaları erişilebilir. Liste sayfasında oran hücreleri boş, oranlar maç detayında; veri kaynağı OddsPortal [O] ([1. Lig](https://www.betexplorer.com/football/turkey/1-lig/results/)) | robots `/bookmaker/` yolunu ve `year`, `stage`, `match` gibi parametreleri kapatıyor [Y] ([robots](https://www.betexplorer.com/robots.txt)). ToS okunamadı | TR2 arşiv ajanına not: geçmiş sonuç listesi buradan da teyit edilebilir. Oran için önerilmez |
| **football-data.co.uk** | Kapanış + Pinnacle (`PSCH…`) + ortalama/maks. oran zaten var [Y] | Kişisel kullanım | **Oran geçmişi ihtiyacının tamamını zaten karşılıyor** (TR1 + 5 lig) |
| **Kendi arşivimiz** | `data/odds/*.json` günde 3 iddaa ve Nesine oran anlık görüntüsü | — | iddaa'nın kendi kapanışına göre CLV için tek kaynak. Saklanmaya devam etmeli |

### 1.6 Sakatlık ve cezalı alternatifleri
| Kaynak | Durum |
|---|---|
| **TFF PFDK kararları** (resmi) | Liste: `https://www.tff.org/Default.aspx?pageId=238`, 39 sayfa. Karar metni: `default.aspx?pageID=246&ftxtID={id}` (ör. 29.10.2026 → `ftxtID=51771`) [Y] ([liste](https://www.tff.org/Default.aspx?pageId=238), [örnek karar](https://www.tff.org/default.aspx?pageID=246&ftxtID=51771)). Yapılandırılabilirlik için §3. |
| **TFF maç sayfası** | İlk 11 ve yedekler maçtan sonra yayımlanıyor. Kart birikimi oradan sayılabilir [Y]. |
| **Transfermarkt / Flashscore** | Mevcut adapter'lar. DataDome ve feed belirsizliği nedeniyle zayıf (SOURCES_RESEARCH §7, §10). |
| **FotMob / Sofascore** | Kadro ve sakatlık var, ama §1.1'deki ToS ve bot engeli sorunları aynen geçerli. |
| **Spor haber siteleri** ("X. hafta sakat ve cezalı listesi": Fanatik, DHA, haberler.com) | Haftalık metin haberleri yayımlanıyor [O] ([örnek](https://www.fanatik.com.tr/futbol/super-lig-13-hafta-sakat-ve-cezali-listesi-2104908)). RSS ajanının işi; burada yalnızca anahtar kelime notu: "sakat ve cezalı", "eksik", "kart sınırında". |

---

## 2. Modeli piyasaya yaklaştıracak yöntemler (literatür)

### 2.1 Dağılım ailesi: bivariate Poisson, Skellam, Weibull
- **Bivariate ve bağımsız Poisson:** Ley, Van de Wiele ve Van Eetvelde (2019) on modeli karşılaştırdı; en iyiler bivariate ve bağımsız Poisson. Premier League'de bivariate model RPS'te **%0,13 daha kötü** (0,19786 → 0,19811), milli takımlarda %0,007 daha iyi. Kovaryans sıfıra yakın [Y] ([arXiv 1705.09575](https://arxiv.org/pdf/1705.09575v2)). → **Beklenen Brier kazancı ≈ 0.** Dixon-Coles'tan geçmeye değmez.
- **Skellam (gol farkı):** Karlis ve Ntzoufras (2009), Bayesçi bir model. footBayes paketinde hazır [Y] ([footBayes](https://search.r-project.org/CRAN/refmans/footBayes/html/stan_foot.html)). Doğrudan Ü/A üretmez; OZBET'in çok marketli simülasyonu için uygun değil.
- **Bivariate Weibull count + copula:** Boshnakov, Kharrat ve McHale (2017, IJF) Poisson'a göre daha iyi uyum ve 1X2 ile Ü/A 2,5'te pozitif getiri raporluyor. Özetten sayı alınamadı [O] ([RePEc](https://econpapers.repec.org/RePEc:eee:intfor:v:33:y:2017:i:2:p:458-466)). `penaltyblog` bunu, Dixon-Coles'u, negatif binom ve ZIP modellerini hazır sunuyor [Y] ([docs](https://penaltyblog.readthedocs.io/en/latest/models/overview.html)). → Ucuz bir A/B testi olabilir; beklenti küçük.
- **Dinamik bivariate Poisson (state-space):** Koopman ve Lit (2015, JRSS-A) EPL'de bahisçiye karşı "anlamlı pozitif getiri" raporluyor. 2010-12 verisi; sonraki yıllarda piyasa verimliliği arttı [O] ([RePEc](https://econpapers.repec.org/RePEc:bla:jorssa:v:178:y:2015:i:1:p:167-186)).

### 2.2 Rating'ler: pi-rating, Elo, Elo-Poisson
- **pi-rating** (Constantinou ve Fenton 2013): iki Elo varyantını "belirgin şekilde" geçiyor ve 5 EPL sezonunda marja rağmen kâr raporluyor [Y] ([RePEc özeti](https://econpapers.repec.org/RePEc:bpj:jqsprt:v:9:y:2013:i:1:p:37-50:n:4)).
- **Elo** (Hvattum ve Arntzen 2010): Elo tabanlı ordered-logit; yayınlanmış oranlara karşı **negatif** beklenen getiri [O] ([RePEc](https://econpapers.repec.org/RePEc:eee:intfor:v:26:y::i:3:p:460-470), [ikincil atıf](https://core.ac.uk/download/77039391.pdf)).
- **2017 Soccer Prediction Challenge** (52 lig): Birinci, **pi-rating + PageRank-rating + elle türetilmiş özellikler + gradient boosted trees** yaklaşımı oldu [Y] ([Hubáček vd. 2019](https://ida.fel.cvut.cz/papers/hubacek2019learning.html), [yarışma özeti](https://link.springer.com/article/10.1007/s10994-018-5763-8)).
- `penaltyblog` Elo, pi, Massey ve Colley rating'lerini hazır içeriyor [Y] ([docs](https://penaltyblog.readthedocs.io/en/latest/)). ClubElo entegrasyonu başka ajanda.

### 2.3 Şut ve xG tabanlı güç, gol tabanlı güce karşı
- **Wheatcroft (2020, IJF):** 10 lig ve 12 yılda şut ve korner tabanlı "GAP rating"ler, Ü/A 2,5'te **golden daha iyi** tahmin ediyor. Yalnızca şut ve korner kullanıldığında **bahis başına ~%0,8** ortalama kâr [Y] ([LSE](https://researchonline.lse.ac.uk/id/eprint/103712)). Aynı yazarın 1X2 çalışmasında, oranlar modele dahilken tahmin edilen **goller AIC'ye neredeyse hiçbir şey katmıyor**. Şut ve korner ise ~132 AIC birimi iyileşme sağlıyor. Seviye bahiste en iyi kombinasyon +%1,85; yalnızca gol kullanan kombinasyon −%1,63 [Y] ([arXiv 2001.09097](https://ar5iv.arxiv.org/html/2001.09097)). Yazar, kârın son sezonlarda azaldığını not ediyor.
- **xG'nin öngörü gücü:** Big-5 ve MLS'te (25.416 takım-maç) sezon içi xG oranı, gelecekteki gol oranını R²>0,5 seviyesinde **9. haftada**, gol oranı ise **11. haftada** açıklamaya başlıyor. İsabetli şut 12. haftada bu eşiğe ulaşıyor [O] ([ElHabr 2024](https://r-bloggers.com/2024/06/expected-goals-gamestate-and-predictiveness-2)).
- Serie A 2026 çalışması: SOT varyantı gol modeline bilgi katıyor (ağırlık 0,35), piyasaya karşı katmıyor [Y] ([arXiv 2608.11505](https://arxiv.org/abs/2608.11505)).
- → **Sonuç:** Şut verisi modeli *gol modeline göre* iyileştirir. Piyasayı geçmeye yetmesi beklenmemeli.

### 2.4 Piyasa oranını öncül olarak kullanmak ve marj temizleme
- **Egidi, Pauli ve Torelli (2018):** Hiyerarşik Bayesçi Poisson'da takımın gol hızı, geçmiş veri ile bahis oranlarından türetilen bilginin **konveks birleşimi** [Y] ([arXiv 1802.08848](https://arxiv.org/abs/1802.08848)). OZBET'in `p = 0,25·model + 0,75·piyasa` harmanı bunun kaba bir hali; λ düzeyinde harmanlamak tüm marketlere (Ü/A, KG, skor) tutarlı yayılır.
- **Kaunitz, Zhong ve Kreiner (2017):** Ortalama oranı "konsensüs olasılık" olarak alıp en yüksek oranla karşılaştıran basit bir strateji: tarihsel %3,5, gerçek parada %8,5 getiri, ardından **hesaplar kısıtlandı** [Y] ([arXiv 1710.02824](https://pdf.arxiv.org/pdf/1710.02824)). iddaa tek fiyat verdiği ve marjı %19–23 olduğu için bu strateji Türkiye'de uygulanamaz. Ders şu: piyasa konsensüsü bilgi kaynağıdır, rakip değil.
- **Marj temizleme:** Basit normalizasyon (1/oran ÷ toplam) yanlı olasılık üretiyor. Shin yöntemi ve regresyon yöntemleri arasındaki fark çelişen sonuçlara yol açacak kadar büyük [Y] ([Štrumbelj 2016](https://econpapers.repec.org/RePEc:sae:jospec:v:17:y:2016:i:1:p:12-26)). Shin yöntemi standart normalizasyondan daha isabetli [O] ([shin paketi](https://www.github.com/mberk/shin), Štrumbelj 2014 atfı). **iddaa'nın %20'lik marjında bu fark %2-5'lik marjdakinden çok daha büyük**, çünkü favori/sürpriz yanlılığı marj arttıkça büyür [D, çıkarım]. `market.py` şu an orantılı normalizasyon yapıyor.

### 2.5 Kalibrasyon
- **Walsh ve Joshi (2024, NBA):** Modeli doğruluğa göre değil **kalibrasyona göre seçmek**, ortalama ROI'de **+%34,69'a karşı −%35,17** fark yaratmış [Y] ([Bath](https://researchportal.bath.ac.uk/en/publications/machine-learning-for-sports-betting-should-model-selection-be-bas/)). Futbol değil, ama ilke aynı.
- **Isotonic regresyon** küçük veride aşırı öğreniyor. **Beta kalibrasyonu** lojistik kalibrasyondan daha iyi ve uygulaması kadar kolay; özdeşlik dönüşümünü de içerdiği için iyi kalibre modeli bozmaz [Y] ([Kull vd. 2017, AISTATS](https://mlanthology.org/aistats/2017/kull2017aistats-beta)). Lig başına ~300 maç/sezon ölçeğinde isotonic riskli. Tek parametreli **temperature** ya da beta tercih edilmeli. Serie A çalışmasında temperature 0,99 çıktı, yani DC zaten iyi kalibre [Y].
- **Metrik:** Wheatcroft (2019), simülasyonda log-loss'un (ignorance) Brier'den ve RPS'ten daha az örnekle doğru modeli seçtiğini gösteriyor ve log-loss'u öneriyor [Y] ([arXiv 1908.08980](https://arxiv.org/pdf/1908.08980)). → Model seçiminde log-loss birincil metrik olsun, Brier ikincil.

### 2.6 Zaman ağırlığı ξ
- OZBET: ξ = 0,0019/gün, yarı ömür ≈ 365 gün.
- Literatürdeki aralık geniş. Bir derleme 0,001–0,006/gün veriyor (yarı ömür ~116–693 gün) [O] ([kb](https://sports-models-kb.pages.dev/dixon-coles-original-paper)). Ley vd. RPS'e göre EPL'de **200 gün yarı ömür** buldu [Y] ([arXiv 1705.09575](https://arxiv.org/pdf/1705.09575v2)). Bir blog EPL için ξ=0,012 buldu, ama sayı vermiyor ve tek kaynak [D] ([blog](https://artiebits.vercel.app/blog/improving-poisson-model-using-time-weighting)).
- → Bizim yarı ömrümüz literatürün uzun ucunda. **Lig başına ξ ızgara araması** (0,001–0,008) ve log-loss ile seçim ucuz bir iş. Kazanç tahmini düşük-orta [D].

### 2.7 Tipik Brier etkileri (yayınlarla)
| İyileştirme | Ölçülen etki | Kaynak |
|---|---|---|
| DC → bivariate Poisson | RPS ±%0,1, pratikte 0 | Ley vd. 2019 [Y] |
| DC'ye piyasa eklemek (log-pool) | Model ağırlığı 0 → **Brier piyasa düzeyine iner (−0,0145)** | Serie A 2026 [Y]; bizde 0,25 harman: −0,0128 |
| Goller → +şut/korner | Gol modeline göre anlamlı (AIC −132); piyasaya göre ~0; O/U'da ~%0,8/bahis | Wheatcroft 2020 [Y], Serie A 2026 [Y] |
| Normalizasyon → Shin | Yanlılık azalır. Brier sayısı bulunamadı | Štrumbelj 2016 [Y/O] |
| Kalibrasyon (temperature) | İyi kalibre DC'de ≈0 (T=0,99) | Serie A 2026 [Y] |
| ξ ayarı | Sayı bulunamadı | — |

**Dürüst sonuç:** Hiçbir yayın, ücretsiz verilerle kapanış oranını Brier'de istikrarlı biçimde geçen bir futbol modeli göstermiyor. Gerçekçi hedef, piyasaya eşit ve iyi kalibre bir olasılık ile **piyasa olmayan maçlarda** (TR2, kupalar) güvenilir bir model.

### 2.8 Bizim için en yüksek getiri/emek oranına sahip ilk 3 adım
1. **"Piyasa öncül + doğru EV" düzeltmesi (S).** (a) iddaa ve Nesine oranlarını Shin (ya da power) yöntemiyle temizle. (b) Backtest'te değer bahislerini, football-data `Avg` yerine **iddaa benzeri marjla** (ör. kendi `data/odds` arşivimizle ya da Avg'yi %20 marja ölçekleyerek) değerlendir. (c) `value.py`'de `ev = p·o − 1 > 0` şartını zorunlu yap. Beklenen fayda: yanlış "Değerli" etiketleri kalkar. Kullanıcı açısından en büyük dürüstlük kazancı budur.
2. **Şut tabanlı λ (S-M).** football-data `HST/AST/HS/AS` ile lig başına "SOT oranı" ya da basit bir xG vekili hesapla. λ = a·λ_gol + b·λ_şut ve ağırlıkları backtest'te log-loss ile seç. Süper Lig'e "xG benzeri" bilgi getirmenin ToS'a uygun tek yolu bu. Beklenen fayda: saf modelde Brier iyileşmesi küçük (tahmin 0,002–0,005 [D]). Ü/A marketinde daha belirgin olabilir (Wheatcroft).
3. **Log-loss ile lig başına ξ ve harman ağırlığı + temperature kalibrasyonu (S).** Mevcut haftalık backtest'e bir ızgara ekle; ölçütleri log-loss ve güvenilirlik eğrisi olsun. Beklenen fayda: küçük ama ölçülebilir. Aşırı öğrenmeye karşı haftalık yeniden kurulum zaten var.

---

## 3. Haber ve kadro bilgisi

- **Kadro bildirimi zamanı:** Premier League ve UEFA'da kadrolar maçtan **75 dk önce**, EFL'de 60 dk önce yayımlanıyor [Y, kural metinlerine atıf] ([derleme](https://ontourfootball.com/news/confirmed-lineups-when-team-news-actually-drops-and-how-to-get-it-in-time)). TFF için eşdeğer kural bulunamadı. OZBET'in 18:30 çalışması, 20:00 sonrası maçların kesin 11'ini kaçırır. Bu yapısal bir sınır.
- **TFF maç sayfası** (`pageId=29&macId=`): Maçtan sonra ilk 11, yedekler, kartlar (dakika) ve değişiklikler yayımlanıyor [Y]. Oynanmamış maçta "Esame bilgileri kulüpler tarafından girilmektedir" notu var [Y]. → Maç öncesi muhtemel 11 için değil, **geçmiş ilk 11 ve süre arşivi** için iyi. Bu arşivden "oyuncu X son 5 maçta ilk 11'de" gibi kilit oyuncu ağırlıkları türetilebilir.
- **TFF PFDK kararları:** Liste sayfası (`pageId=238`) yapılandırılmış: başlık, tarih, `ftxtID` linki [Y]. Karar metni ise **serbest metin**: numaralı maddeler, kalın büyük harfle kulüp ya da oyuncu adı, maç, madde no ve yaptırım ("N RESMİ MÜSABAKADAN MEN", para cezası, ihtar). Tablo yok [Y] ([örnek](https://www.tff.org/default.aspx?pageID=246&ftxtID=51771)).
  - **Yapılandırılabilir mi?** Kısmen evet [O]. Regex taslağı: madde başı `^\d+-`, kişi/kulüp için büyük harf blok, yaptırım için `(\d+)\s+RESMİ\s+MÜSABAKADAN\s+MEN`. Liste sayfası haftalık taranıp yeni `ftxtID`'ler alınabilir. Ancak **sarı kart birikimi cezaları PFDK metninde yer almıyor** (örnek kararda sarı kart geçmiyor [Y]). Bunlar ancak TFF maç sayfalarındaki kartları sayarak hesaplanabilir. Süper Lig'de kaç sarı kartın ceza getirdiğini birincil kaynakta doğrulayamadım [D]. Futbol Disiplin Talimatı Haziran 2025'te değiştirildi; bilinçli kart görmeye 2 maç men cezası (md. 37) var [O] ([A Spor](https://www.aspor.com.tr/spor-toto-super-lig/2025/06/04/tff-futbol-disiplin-talimatinda-yapilan-degisiklikleri-duyurdu)).
- **Kulüp siteleri:** galatasaray.org robots.txt'i HTML döndü, yani okunamadı [Y gözlem]. Kulüp sitelerinde yapılandırılmış sakatlık sayfası bulunamadı. Bilgi haber metni olarak geliyor. RSS ajanının konusu.
- **Bağlam notu:** 2025 bahis skandalında 102 Süper Lig ve 1. Lig oyuncusuna 45 gün–12 ay arası ceza verildi; 2. ve 3. Lig'de toplu cezalar oldu [O] ([Wikipedia arşivi](https://wiki.krisyotam.com/content/wikipedia_en_all_nopic_2026-03/2025_Turkish_referee_betting_scandal)). Alt liglerin kadro istikrarı bu nedenle düşük; TR2 modelinde geçmiş verinin ağırlığı azaltılmalı [D].

---

## 4. Türk piyasasına özgü konular

### 4.1 MBS (Minimum Bahis Sayısı)
- MBS, kuponda o maçın en az kaç maçlık kombinasyonla oynanabileceğini gösterir. Kuponun MBS'si, içindeki en yüksek MBS'dir [O, genel bilgi; bu oturumda resmi kural metni açılamadı].
- Ağustos 2019'dan beri 5 büyük lig, ŞL, UEL ve **Süper Lig MBS1 (tek maç)**. Bültene ilk kez giren ligler MBS3 [O] ([Posta 2019](https://www.posta.com.tr/spor/ilk-hafta-iddaada-86-tek-mac-ve-canli-bahis-misli-comda-2199944)). Bugünkü verimiz: 39 maç MBS1, 4 maç MBS2, 38 maç MBS3 [Y].
- MBS veride iki düzeyde geliyor: market düzeyinde (Nesine `MA[].MBS`) ve event düzeyinde (iddaa `mbc`) [Y, SOURCES_RESEARCH §1–2].
- **Değere etkisi:** MBS3 bir maçı oynamak için 3 maçlık kupon gerekir. Kombinin beklenen getirisi, her ayağın getirisinin çarpımıdır. Ayak başı ~%19 marjla (geri ödeme ≈ 1/1,19 ≈ %84) 3'lü kuponun geri ödemesi ≈ 0,84³ ≈ **%59** [Y, aritmetik]. OZBET bunu kartta "bu maç tek başına oynanamaz; kombine edildiğinde beklenen kayıp büyür" diye göstermeli. MBS3 maçlarına "Değerli" etiketi verilmemesi önerilir.

### 4.2 Nesine ve iddaa oran farkları
- Oranları merkezi olarak iddaa (Spor Toto adına işletmeci) belirliyor. Nesine, Misli ve Bilyoner gibi bayi platformları aynı bülteni sunuyor; zaman zaman kampanya oranları uyguluyorlar [O].
  - Misli "Şampiyon Oran": seçili maçlarda +0,02–0,03 puan (~%1–2) [Y, örnek oranlar] ([Fanatik 2024](https://www.fanatik.com.tr/iddaa/mislide-sampiyon-oran-farki-70-bin-tl-yerine-78-bin-tl-kazandi-2540599)).
  - iddaa "Kral Oranlar": yalnızca fiziki bayiler ve iddaa.com'da, seçili maçlarda [Y] ([Milliyet 2021](https://www.milliyet.com.tr/skorer/super-lig-heyecani-kral-oranlarla-iddaa-bayilerinde-6649805)).
- Nesine'ye özel sistematik bir oran farkına dair kaynak **bulunamadı**. Öneri: Adapter'lar iki kaynağın oranlarını ayrı alanlarda saklasın, fark >%1 ise "kampanya oranı" rozeti gösterilsin. Günde 3 anlık görüntüyle bir hafta içinde ölçülebilir.
- %1–2'lik kampanya artışı %19–23'lük marjı kapatmaz.

### 4.3 Marj karşılaştırması ve değer eşiği
| Operatör | 1X2 marjı | Kaynak |
|---|---|---|
| Pinnacle | ~%2 (Ü/A %2,5) | [Y] [Pinnacle](https://pinnaclesports.freshdesk.com/support/solutions/articles/1000189654-how-do-i-calculate-betting-margins-) |
| "Sektör ortalaması" (Pinnacle'ın iddiası) | ~%6 | [O] aynı kaynak |
| **iddaa / Nesine (5 Kasım)** | MBS1 kupa maçları %18,7, MBS3 %23,3, medyan %23,0. Ü/A %19,0 | [Y] `data/latest.json` |

- **Yasal çerçeve:** Bir yılda dağıtılan ikramiye hasılatın %40'ından az olamaz. Üst sınır %83'tü; 2023 sonu düzenlemesiyle %90 ([memurlar, teklif aşaması](https://www.memurlar.net/haber/1083619)) ya da %93 ([Diken, 7491 s. Kanun](https://www.diken.com.tr/?p=1391655)) oldu. Kaynaklar çelişiyor [O]. 2017'de fiili ikramiye payı ~%59'du [O] ([Dünya](https://www.dunya.com/kose-yazisi/iddaanin-spora-katki-iddiasi/434184)). Spor Toto ikramiye oranını yıllık ortalama içinde oyun bazında belirleyebiliyor [Y] ([Hasılat Dağıtım Yön. md. 4](https://www.lexpera.com.tr/mevzuat/yonetmelikler/spor-toto-teskilat-baskanligi-hasilat-dagitim-yonetmeligi)).
- **Değer eşiğine etkisi** [Y, aritmetik]. Orantılı marj m için iddaa oranı o ≈ 1/(p_adil·(1+m)) olur. Pozitif EV için gerçek olasılığın p_adil·(1+m)'yi aşması gerekir. Mutlak eşik ≈ **p·m**:
  - p=0,50, m=0,20 → model, adil olasılığı **≥10 puan** aşmalı (şu anki eşik 5 puan).
  - p=0,25, m=0,20 → ≥5 puan, ama bu bölgede favori/sürpriz yanlılığı nedeniyle orantılı varsayım iyimser kalır [D].
  - Backtest, modelin adil olasılığı ortalamada bile tutturamadığını gösteriyor (Brier farkı 0,016). Bu nedenle **iddaa'da istikrarlı pozitif EV beklemek gerçekçi değil.**
- Öneri: "Değerli" etiketi `p_harman·o_iddaa > 1,02` olsun (EV>%2 güvenlik payı) ve yalnızca MBS1 maçlara verilsin. Etiket ayrıca "model ile piyasa arasındaki fark" anlamında yeniden adlandırılabilir ("Model farkı").

### 4.4 Türkiye'de yasal çerçeve — kısa not (**hukuki tavsiye değildir**)
- **7258 s. Kanun md. 5/1-ç:** Yasa dışı bahsin **reklamını yapmak ya da başka yollarla oynamaya teşvik etmek** suçtur: 1–3 yıl hapis ve 3.000 güne kadar adli para cezası. Örnekler: yasa dışı siteye link, promosyon kodu, bonus paylaşımı, tahmin/kupon gruplarından yönlendirme. Haber, eleştirinin ve **yasal oyunların** (Spor Toto/iddaa) tanıtımı bu suçun kapsamı dışında. 5651 s. Kanun md. 8 uyarınca erişim engeli verilebilir [O, avukat blogu, Ekim 2026] ([kaynak](https://hukukcularevi.com/bahis-reklami-suc-mu-7258-reklam-tesvik-sosyal-medya-erisim-engeli-5651/)).
- **Yasal oyunun tanıtımı da sınırlı:** Uygulama Yönetmeliği md. 31/1-e (RG 13.02.2026, 33167) pazarlama ve tanıtımı **Teşkilatın ya da sanal bayilerin** yapabileceğini, 18 yaş altını hedeflemeyeceğini ve **sporla ilgili mecralarla sınırlı** olacağını düzenliyor [Y] ([alomaliye](https://www.alomaliye.com/2026/02/13/spor-musabakalarina-dayali-sabit-ihtimalli-ve-musterek-bahis-oyunlari-uygulama-yonetmeligi/)). Kişisel bir site bu yetkili listede değil.
- **OZBET için pratik çıkarımlar** [D, hukuki yorum değildir]:
  - Hiçbir bahis sitesine, yasal sanal bayiler dahil, link, affiliate kodu, banner ya da reklam koymayın. Reklam, Open-Meteo şartlarına göre siteyi "ticari" de yapar.
  - Dili "istatistiksel tahmin" çerçevesinde tutun; "oyna", "kazan", "banko" gibi teşvik içeren ifadelerden kaçının. commentator.py'deki yasaklı kelime filtresi bu açıdan iyi bir temel.
  - 18+ ve sorumlu oyun uyarısını koruyun.
  - Site herkese açık bir GitHub Pages adresinde. "Kişisel kullanım" savunusunu güçlendirmek için `noindex` meta etiketi, arama motorlarına kapatma ya da basit bir erişim kapısı düşünülebilir.
  - **Veri lisansları:** football-data (kişisel kullanım, yeniden dağıtım yok), FotMob ve OddsPortal (otomatik çekme yasak) ile Open-Meteo (CC BY atıf) şartları ayrı ayrı bağlayıcı. Ham veriyi depoda yeniden yayımlamayın; depo herkese açıksa `data/` altındaki türetilmiş çıktılar dışında ham CSV commit edilmemeli.

---

## 5. Diğer ajanlara kısa notlar
- **TR2 arşivi:** TFF fikstür ve maç sayfaları (`pageId=29&macId=`) 1. Lig için de resmi skor, kart ve kadro sağlıyor. BetExplorer 1. Lig 2026/27 listesi de erişilebilir (13 hafta) [O]. football-data'da TR2 yok [Y].
- **ClubElo:** Ek bilgi bulunamadı. `penaltyblog` ClubElo okuyucusu içeriyor [Y] ([docs](https://penaltyblog.readthedocs.io/en/latest/)).
- **RSS:** Sakat ve cezalı haberleri için anahtar kalıplar: "sakat ve cezalı", "kart sınırında", "X maçı öncesi N eksik".

---

## OZBET için önerilen yol haritası

| # | Adım | Emek | Beklenen fayda | Dayanak |
|---|---|---|---|---|
| 1 | `value.py`: EV>0 (tercihen >%2) şartı; MBS≥2 maçlarda "Değerli" yok; etiket adı "Model farkı" | **S** | Negatif EV'li "Değerli" etiketleri biter. En yüksek dürüstlük kazancı | §0, §4.3 aritmetiği; [Pinnacle marj](https://pinnaclesports.freshdesk.com/support/solutions/articles/1000189654-how-do-i-calculate-betting-margins-) |
| 2 | Marj temizlemeyi Shin (ya da power) yöntemine geçir (`market.py`); `shin` paketi veya 20 satırlık kendi uygulaması | **S** | iddaa'nın %20 marjında ima olasılıkları daha doğru olur; piyasa harmanı iyileşir | [Štrumbelj 2016](https://econpapers.repec.org/RePEc:sae:jospec:v:17:y:2016:i:1:p:12-26), [shin](https://www.github.com/mberk/shin) |
| 3 | Backtest'te değer ROI'sini iddaa marjıyla da raporla (Avg'yi %20 marja ölçekle + `data/odds` arşiviyle iddaa-CLV) | **S** | Karne sayfası gerçek iddaa koşullarını gösterir | §0; `backtest.json` `method` alanı |
| 4 | Şut tabanlı λ: football-data `HST/AST/HS/AS` ile xG vekili ve λ harmanı; ağırlık log-loss ile seçilir | **M** | Saf modelde küçük Brier iyileşmesi, Ü/A'da daha belirgin. Süper Lig'e ToS'a uygun "xG" | [Wheatcroft 2020](https://researchonline.lse.ac.uk/id/eprint/103712), [arXiv 2001.09097](https://ar5iv.arxiv.org/html/2001.09097), [arXiv 2608.11505](https://arxiv.org/abs/2608.11505) |
| 5 | Lig başına ξ ızgara araması (0,001–0,008) + temperature/beta kalibrasyonu; birincil metrik log-loss | **S** | Küçük ama ölçülebilir; güvenilirlik eğrisi Karne'ye eklenir | [Ley vd. 2019](https://arxiv.org/pdf/1705.09575v2), [Kull vd. 2017](https://mlanthology.org/aistats/2017/kull2017aistats-beta), [Wheatcroft 2019](https://arxiv.org/pdf/1908.08980) |
| 6 | Harmanı olasılık yerine λ düzeyinde yap (piyasa 1X2 ve Ü/A'dan λ geri çözümü, ardından DC λ ile konveks birleşim) | **M** | Skor, KG ve İY/MS marketleri piyasayla tutarlı hale gelir | [Egidi vd. 2018](https://arxiv.org/abs/1802.08848) |
| 7 | TFF maç sayfası adapter'ı (`pageId=29&macId=`): hakem, kartlar, ilk 11, stat; haftalık + hakem kart ortalaması | **M** | Resmi hakem ve kadro arşivi; kart birikimi takibi; TR2 için de veri | §1.2, §3 [TFF örnek maç](https://www.tff.org/Default.aspx?pageId=29&macId=317790) |
| 8 | PFDK liste ve karar metni ayrıştırıcısı (regex: "N RESMİ MÜSABAKADAN MEN") → `suspensions.json` | **M** | Ceza kaynaklı eksikler resmi kaynaktan gelir (sarı kart birikimi hariç) | [PFDK listesi](https://www.tff.org/Default.aspx?pageId=238) |
| 9 | Dinlenme günü (≤3 gün bayrağı) ve seyahat mesafesi özelliği + Open-Meteo rozeti (stat koordinatı tablosu) | **S-M** | Model etkisi düşük; kartta bilgi değeri. Backtest'te ölçülmeden modele sokulmaz | [Scoppa 2015](https://www.iza.org/publications/dp/7519), [Open-Meteo şartları](https://open-meteo.com/en/terms) |
| 10 | (Deneysel) pi-rating + GBM ya da Weibull-copula'yı `penaltyblog` ile A/B test et; yalnızca log-loss iyileşirse al | **L** | Belirsiz; literatürde yarışma birinciliği var ama piyasayı geçme kanıtı zayıf | [Hubáček vd. 2019](https://ida.fel.cvut.cz/papers/hubacek2019learning.html), [Boshnakov vd. 2017](https://econpapers.repec.org/RePEc:eee:intfor:v:33:y:2017:i:2:p:458-466), [penaltyblog](https://penaltyblog.readthedocs.io/en/latest/models/overview.html) |

**Yapılmaması önerilenler:** FotMob, Sofascore ve OddsPortal otomatik çekimi (ToS ve robots açıkça karşı, Actions IP'leri engelleniyor); fbref xG (Ocak 2026'dan beri yok); Cloudflare veya DataDome atlatma; siteye reklam ya da bahis linki eklemek.
