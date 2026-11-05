# OZBET — Veri Kaynakları Teknik Araştırması

Tarih: 2026-11-05 · Hazırlayan: Veri Kaynağı Ajanı (WebSearch + WebFetch ile; shell/curl kullanılmadı)

Güven etiketi: **[YÜKSEK]** = canlı yanıtta ya da açık kaynak kodda birebir görüldü · **[ORTA]** = tek ikincil kaynak veya kısmi gözlem · **[DÜŞÜK]** = tahmin/çıkarım, doğrulanmalı · **BULUNAMADI** = kanıt yok, uydurulmadı.

Genel kural (tüm adapter'lar): gerçekçi `User-Agent`, istekler arasında ≥2–5 sn gecikme, yanıtları önbelleğe alma (ETag/versiyon alanları varsa kullan), 403/429'da üstel geri çekilme, GitHub Actions IP'lerinin bazı sitelerde (Transfermarkt, Forebet, Flashscore) engellenebileceğini varsay.

---

## 1. Nesine (iddaa bülteni)

### Endpoint'ler
| Amaç | URL | Güven |
|---|---|---|
| Maç öncesi tam bülten | `https://cdnbulten.nesine.com/api/bulten/getprebultenfull` | **[YÜKSEK]** — WebFetch ile canlı JSON alındı; ayrıca [durmusesad/kg-tahmin scraper.py](https://raw.githubusercontent.com/durmusesad/kg-tahmin/main/scraper.py) ve [uurcantnt/nesine-bot src/bulletin.py](https://raw.githubusercontent.com/uurcantnt/nesine-bot/main/src/bulletin.py) |
| Eski host (2021) | `https://bulten.nesine.com/api/bulten/getprebultenfull` | [ORTA] — [r10.net konusu](https://www.r10.net/sorum-var/2779537-nesineden-oranlar-nasil-cekilebilir.html) |
| Canlı bülten | `https://bulten.nesine.com/api/bulten/getlivebultenfull` (nesine-bot) ve `.../getlivebultenv3?eventVersion=0&oddVersion=0` (kg-tahmin) | [ORTA-YÜKSEK] — iki repo |
| Canlı skor / sonuç | `https://ls.nesine.com/api/v2/Bet/GetLiveBetResultsWithVersion?v=0` → `d[]` içinde `C`/`NID`, `ST`, `ES[]` (`T` devre 1/2/3, `H`, `A` gol), `MDT[]` | [ORTA] — [kg-tahmin scraper.py](https://raw.githubusercontent.com/durmusesad/kg-tahmin/main/scraper.py) |
| Maç sonucu (bitmiş maçlar) | **BULUNAMADI** — nesine-bot README'si açıkça "sonuç endpoint'i bulunamadı" diyor ([README](https://raw.githubusercontent.com/uurcantnt/nesine-bot/main/README.md)). Sonuçlar için football-data.co.uk / API-Football kullanılmalı. | — |

### Header'lar [YÜKSEK]
```
User-Agent: Mozilla/5.0 (... ) Chrome/12x Safari/537.36   # ZORUNLU: yoksa CDN 403 döner (nesine-bot kod yorumu)
Accept: application/json
```
Kaynak: [nesine-bot bulletin.py](https://raw.githubusercontent.com/uurcantnt/nesine-bot/main/src/bulletin.py), [kg-tahmin scraper.py](https://raw.githubusercontent.com/durmusesad/kg-tahmin/main/scraper.py). API anahtarı gerekmez.

### JSON yapısı
Üst seviye (canlı gözlem [YÜKSEK]):
```
{ "sg": { "eventVersion", "marketVersion", "oddVersion", "drawNo", "FB", "EA": [ ...event... ], "LA"?: [...] } }
```
- `oddVersion` değişmediyse veri değişmemiştir → yazma/işlem atlanabilir (nesine-bot bu şekilde kullanıyor).
- `sg.LA[]` lig listesi: `LID` (lig id), `N` (lig adı); event'teki `LC` ile eşleşir [ORTA — iki repoda kodda var; benim aldığım kesik yanıtta görünmedi].

Event (`EA[]`) alanları:
| Alan | Anlam | Güven |
|---|---|---|
| `C` | Maç kodu (iddaa kodu) | YÜKSEK |
| `NID` | Numerik id (genelde `C` ile aynı) | YÜKSEK (canlı) |
| `HN` / `AN` | Ev / deplasman takım adı | YÜKSEK (iki repo kodu) |
| `LC` | Lig kodu → `LA[].LID` | YÜKSEK |
| `D` / `T` | Tarih `"DD.MM.YYYY"` / saat `"HH:MM"` (TR saati) | YÜKSEK (canlı) |
| `ESD` | Başlangıç epoch **ms** (tercih edilen) | YÜKSEK |
| `DAY` | Gün adı | YÜKSEK (canlı) |
| `TYPE` | Tür (−1 = outright/özel) ; `GT` oyun tipi (kg-tahmin `GT != 1` olanları eler) | ORTA |
| `MA[]` | Maç marketleri (normal maçlarda) | YÜKSEK (kod) |
| `MSA[]` | Özel/outright marketler ("Şampiyon kim olur?" vb.) — canlı yanıtta outright event'lerde `MA` boş, `MSA` dolu | YÜKSEK (canlı) |
| `BRID` | Betradar id (eşleştirme için faydalı) | ORTA (canlı) |
| `ENN` | Outright event adı ("Türkiye 1. Lig - ...") | YÜKSEK (canlı) |
| `LE`, `NS`, `CE`, `HPI`, `API` | Canlı/başlamadı/iptal bayrakları, popülerlik | DÜŞÜK (anlam tahmini) |

Market (`MA[]`) alanları:
| Alan | Anlam | Güven |
|---|---|---|
| `MTID` | Market tip id | YÜKSEK (kod) |
| `SOV` | Özel oran değeri / çizgi (MS'te 0.0; handikap vb.) | YÜKSEK |
| `MBS` | Minimum bahis sayısı (market düzeyinde) | YÜKSEK (nesine-bot `simplify`: `"mbs" ← MBS`; canlı yanıtta `MSA` içinde de var) |
| `MS`, `MV` | Market durumu, versiyon | ORTA |
| `OCA[]` | Seçenekler: `N` (seçenek no, 1'den başlar), `O` (ondalık oran), `ON` (ad, outright'larda) | YÜKSEK |

Not: MBS event düzeyinde değil, **market düzeyinde** (`MA[].MBS`). Outright `MSA` kayıtlarında market tipi anahtarı `MT` (MTID değil).

### MTID tablosu [YÜKSEK — nesine-bot'un Nesine `CCAll.min.js`'ten çıkardığı katalog]
Kaynak: [nesine-bot data/market_katalog.json](https://raw.githubusercontent.com/uurcantnt/nesine-bot/main/data/market_katalog.json), [src/catalog.py](https://raw.githubusercontent.com/uurcantnt/nesine-bot/main/src/catalog.py)

| MTID | Market | Seçenekler (`N` sırası) |
|---|---|---|
| 1 | Maç Sonucu | 1=MS1, 2=MSX, 3=MS2 |
| 3 | Çifte Şans | 1=1-X, 2=1-2, 3=X-2 |
| 5 | İlk Yarı / Maç Sonucu | 1/1,1/X,1/2,X/1,X/X,X/2,2/1,2/X,2/2 (N=1..9) |
| 7 | 1. Yarı Sonucu | 1, X, 2 |
| 8 | 1. Yarı Çifte Şans | 1-X, 1-2, X-2 |
| 9 | 2. Yarı Sonucu | 1, X, 2 |
| 11 | 1,5 Gol Alt/Üst | 1=Alt, 2=Üst |
| 12 | **2,5 Gol Alt/Üst** | 1=Alt, 2=Üst |
| 14 | 1. Yarı 1,5 Gol Alt/Üst | Alt, Üst |
| 38 | **Karşılıklı Gol** | 1=Var, 2=Yok |
| 43 | Toplam Gol Aralığı | 0-1, 2-3, 4-5, 6+ |
| 801 | İY + MS Karşılıklı Gol | N=3 "Evet/Evet" |
| 6 | Handikaplı MS (SOV=handikap) | HMS1, HMSX, HMS2 |
| 53/55/56 | Canlı: MS / Çifte Şans / Kalan MS | — (55 eşlemesi repo yazarınca "kanıtlanamadı") |

Uyarı: Katalogda İY/MS adlı başka MTID'ler de var (143, 850); asıl market için 5'i kullanın ve seçenek sayısını (9) doğrulayın. Seçeneklerin `N` → etiket sırası katalogdaki listeye göre; adapter'da "seçenek sayısı = beklenen" kontrolü koyun (nesine-bot böyle yapıyor).

### Kullanım şartları / robots
- `nesine.com/robots.txt`: `*` için CDN/API alt alanları, kupon/bülten sayfaları, sonuç/istatistik sayfaları **disallow**; Googlebot/GPTBot/ClaudeBot gibi isimli botlara geniş izin, bazılarına 1 sn crawl-delay ([robots.txt](https://www.nesine.com/robots.txt)). `cdnbulten` için ayrı robots bulunamadı. Yani endpoint teknik olarak açık ama robots niyeti API alt alanlarını taramamak yönünde → **düşük frekans** (ör. 15 dk'da bir, nesine-bot da 15 dk cache kullanıyor: [Asistan PR #68](https://github.com/senirlioglu/Asistan/pull/68)) ve kişisel kullanım önerilir.

---

## 2. iddaa.com (resmi) — sportsbookv2 JSON API

Herkese açık, anahtarsız JSON API **var** [YÜKSEK — canlı yanıt alındı].

| Amaç | URL | Güven |
|---|---|---|
| Maç listesi + marketler | `https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0&version=0` (`st=1` futbol) | YÜKSEK (canlı + [sezginn07/iddaa lib/iddaa.js](https://raw.githubusercontent.com/sezginn07/iddaa/main/lib/iddaa.js)) |
| Ligler | `https://sportsbookv2.iddaa.com/sportsbook/competitions` | YÜKSEK (canlı) |
| Market sözlüğü | `https://sportsbookv2.iddaa.com/sportsbook/get_market_config` → `data.m["{t}_{st}"] = {i, n, mt, st, ...}` | YÜKSEK (canlı; yanıt çok büyük, ad eşleme kısmi) |

Header: zorunlu header görülmedi (sezginn07 düz `fetch` kullanıyor); yine de UA + `Accept: application/json` gönderin.

### Yapı
- Kök: `{ "isSuccess": true, "data": { "isdiff": false, "version": <n>, "events": [...] } }` — `version` sonraki çağrıda `version=` parametresine verilerek diff alınabilir [ORTA, parametre adından çıkarım].
- Event: `i` (event id), `hn` / `an` (ev/dep), `d` (epoch **saniye**), `ci` (competition id → competitions `i`), `mbc` (MBS, event düzeyi), `il` (canlı bayrağı), `bri` (Betradar id), `v`, `s`, `oc` (market sayısı), `m[]` (marketler).
- Market: `i`, `t` (market grup tipi: 1/2…), `st` (alt tip = market türü), `sov` (çizgi, ör. `"2.5"`; sadece bazı marketlerde), `mbc`, `s`, `v`, `o[]`.
- Seçenek: `no`, `n` (ad), `odd` (oran), `wodd`.
- Competition: `i`, `cid` (ülke kodu "TR"), `si` (spor, "1"=futbol), `n`, `sn`, `cref`. **Süper Lig: `i=584`** (`n`="Türkiye Süper Lig") [YÜKSEK — canlı].

### Market `st` eşlemesi (canlı yanıttaki seçenek adlarından + sezginn07 kodundan)
| Market | `st` | Seçenek `n` | Güven |
|---|---|---|---|
| Maç Sonucu | 1 | "1","0","2" (X = "0") | YÜKSEK |
| Alt/Üst (çizgi `sov`) | 101 | "Alt","Üst" — `sov=="2.5"` seç | YÜKSEK |
| KG Var/Yok | 89 | "Var","Yok" | YÜKSEK |
| İY/MS | 90 | "1/1","1/0",…,"2/2" (9 seçenek) | ORTA (seçeneklerden çıkarım) |
| Çifte Şans | 92 **veya** 77 | "1 ve 0","1 ve 2","0 ve 2" | DÜŞÜK — iki adayın ikisinin de seçenekleri aynı; `get_market_config`'te `"2_92"`/`"2_77"` adına bakıp doğrulayın |
| İY Alt/Üst | 60 | Alt/Üst | ORTA (sezginn07 yorumu `"2_60"`) |
| İY KG | 720 | Var/Yok | ORTA (`"2_720"`) |
| Toplam gol aralığı | 4 | "0-1 gol"…"6+ gol" | ORTA |
| st=100 | 1/0/2 ama MS değil (sezginn07 bilinçli dışlıyor) | — | ORTA |

### robots
`iddaa.com/robots.txt`: sadece `*/mac-detay/*` ve `/dosyalar/bayimalzemeleri/` disallow; AI botlarına `Allow: /` ([robots.txt](https://www.iddaa.com/robots.txt)). `sportsbookv2` alt alanı için robots bulunamadı. **Öneri:** iddaa resmi API, Nesine'den daha temiz ve daha az kısıtlı — birincil oran kaynağı olarak düşünülebilir, Nesine ikincil/çapraz kontrol.

---

## 3. football-data.co.uk

### URL formatları [YÜKSEK]
- Ana ligler sezon dosyası: `https://www.football-data.co.uk/mmz4281/{YYZZ}/{DIV}.csv` — ör. `mmz4281/2526/T1.csv`, `mmz4281/2627/T1.csv` (2026/27 dosyası mevcut). Türkiye kodu **`T1`**, 1994/95'ten beri ([turkeym.php](https://www.football-data.co.uk/turkeym.php)).
- Diğer ana lig kodları (standart, sitenin ülke sayfalarından): E0,E1,E2,E3,EC, SC0–SC3, D1,D2, I1,I2, SP1,SP2, F1,F2, N1, B1, P1, G1, T1 [T1/yapı YÜKSEK; diğer kodlar ORTA — tek tek sayfa açılmadı, [data.php](https://www.football-data.co.uk/data.php) ülke sayfalarını listeliyor].
- Yaklaşan maçlar: `https://www.football-data.co.uk/fixtures.csv` (+ `.xlsx`) ([matches.php](https://www.football-data.co.uk/matches.php)). Ek ligler için `matches_new_leagues.php` sayfası var; CSV adı (`new_league_fixtures.csv`?) **doğrulanamadı** [DÜŞÜK]. fixtures.csv içeriği WebFetch'le okunamadı; kolonlarının sezon dosyasıyla aynı (FTHG/FTAG boş) olduğu varsayımı [ORTA].
- Oran toplama zamanı: hafta sonu maçları Cuma 17:00 UK, hafta içi Salı 13:00 UK'ye kadar ([matches.php](https://www.football-data.co.uk/matches.php)). → Kapanış oranları maç sonrası sezon dosyasına eklenir.
- "Ekstra ligler": `https://www.football-data.co.uk/new/{CCC}.csv` (ör. `new/BRA.csv`). **Türkiye ekstra liglerde değil** (Arjantin, Avusturya, Brezilya, Çin, Danimarka, Finlandiya, İrlanda, Japonya, Meksika, Norveç, Polonya, Romanya, Rusya, İsveç, İsviçre, ABD) — `new/TUR.csv` yok [YÜKSEK, [data.php](https://www.football-data.co.uk/data.php)].

### 2025/26 T1.csv başlığı (canlı okundu) [YÜKSEK]
```
Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,
B365H,B365D,B365A,BFDH,BFDD,BFDA,BMGMH,BMGMD,BMGMA,BVH,BVD,BVA,BWH,BWD,BWA,CLH,CLD,CLA,LBH,LBD,LBA,
PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,BFEH,BFED,BFEA,
B365>2.5,B365<2.5,P>2.5,P<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,BFE>2.5,BFE<2.5,
AHh,B365AHH,B365AHA,PAHH,PAHA,MaxAHH,MaxAHA,AvgAHH,AvgAHA,BFEAHH,BFEAHA,
B365CH,B365CD,B365CA,BFDCH,BFDCD,BFDCA,BMGMCH,BMGMCD,BMGMCA,BVCH,BVCD,BVCA,BWCH,BWCD,BWCA,
CLCH,CLCD,CLCA,LBCH,LBCD,LBCA,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,BFECH,BFECD,BFECA,
B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,MaxC>2.5,MaxC<2.5,AvgC>2.5,AvgC<2.5,BFEC>2.5,BFEC<2.5,
AHCh,B365CAHH,B365CAHA,PCAHH,PCAHA,MaxCAHH,MaxCAHA,AvgCAHH,AvgCAHA,BFECAHH,BFECAHA
```
Örnek satır: `T1,08/08/2025,19:30,Gaziantep,Galatasaray,0,3,A,...` → `Date` = `dd/mm/YYYY` (4 haneli yıl; notes.txt `dd/mm/yy` diyor → ikisini de parse edin).

Önemli: İstenen tüm kolonlar mevcut: `AvgH/AvgD/AvgA`, `Avg>2.5/Avg<2.5`, `AvgCH/AvgCD/AvgCA`, `AvgC>2.5/AvgC<2.5`, `PSCH/PSCD/PSCA` (Pinnacle kapanış), `PC>2.5/PC<2.5`. Kapanış kuralı: bahisçi/Max/Avg kodundan sonra `C` ([notes.txt](https://www.football-data.co.uk/notes.txt)).
Güncel bahisçi seti (2025/26): B365, BFD (Betfred), BMGM (BetMGM), BV (BetVictor), BW, CL (Coral?), LB (Ladbrokes), PS (Pinnacle), BFE (Betfair Exchange). Eski BbAv*/BbMx* (BetBrain) kolonları yok → eski sezonlarla birleştirirken kolon adlarını opsiyonel tutun. `AHh` 2019/20'den beri ([notes.txt](https://www.football-data.co.uk/notes.txt)).

### new/*.csv formatı [YÜKSEK]
Başlık: `Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,BFECH,BFECD,BFECA,B365CH,B365CD,B365CA` (+ isimsiz boş kolonlar) — tüm sezonlar tek dosyada, **sadece 1X2 kapanış**, Ü/A yok ([new/BRA.csv](https://www.football-data.co.uk/new/BRA.csv)).

### Şartlar
Site, verilerin özel kişiler için olduğunu, ticari kullanım ve otomatik bot/scraper/AI eğitimi için olmadığını belirtiyor ([data.php](https://www.football-data.co.uk/data.php)). → Haftada birkaç kez, tek dosya indirme; yeniden dağıtım yok.

---

## 4. understat.com

**Durum (2026-11-05):** Site WebFetch'te "We will come back soon" mesajı döndürdü — geçici bakım/kapalı olabilir [YÜKSEK gözlem; kalıcılığı bilinmiyor]. Adapter opsiyonel ve hata toleranslı olmalı.

### Veri erişimi — AJAX endpoint'e geçiş [YÜKSEK]
Eski yöntem (lig sayfasındaki `var datesData = JSON.parse('\x5B...')` hex kaçışlı gömülü JSON) güncel kütüphanelerde terk edilmiş; artık XHR endpoint kullanılıyor:
```
GET https://understat.com/getLeagueData/{LEAGUE}/{SEASON}
Headers:
  X-Requested-With: XMLHttpRequest
  Referer: https://understat.com/league/{LEAGUE}/{SEASON}
  User-Agent: <tarayıcı UA>
  Accept: application/json
```
- `{LEAGUE}`: EPL, La_liga, Bundesliga, Serie_A, Ligue_1, RFPL — **Süper Lig yok** (understat yalnızca bu 6 ligi kapsar) [ORTA — genel bilgi, bu oturumda doğrulanmadı].
- `{SEASON}`: başlangıç yılı (2025/26 → `2025`).
- Yanıt: `{ "teams": {id: {...}}, "players": [...], "dates": [...] }`.
- Kaynaklar: [understatAPI league.py](https://collinb9.github.io/understatAPI/_modules/understatapi/endpoints/league.html) (v0.7.0, Ara 2025 sürümü — [PyPI](https://pypi.org/project/understatapi)), [footix understat.py](https://footix.readthedocs.io/en/latest/_modules/footix/data_io/understat.html), [goalgorithm-mcp data_fetcher.py](https://glama.ai/mcp/servers/@tohoanganhai/goalgorithm-mcp/blob/db5c2d231482f7e7fc146f61185199ec95839b52/src/goalgorithm_mcp/data_fetcher.py), [Apify notları](https://apify.com/jungle_synthesizer/understat-xg-league-team-stats-scraper.md).

### Alanlar
- `dates[]` (maç): `id`, `datetime`, `isResult`, `h.title`, `a.title`, `goals.h/a`, `xG.h/a`, `forecast.w/d/l` [YÜKSEK — footix].
- `teams{id}`: `title`, `history[]` → maç başı `xG`, `xGA` [YÜKSEK]; ayrıca `npxG`, `npxGA`, `ppda`, `deep`, `scored`, `missed`, `xpts`, `h_a`, `date` [ORTA — Apify çıktı alanlarından ve eski bilinen yapıdan; bu oturumda ham JSON görülmedi].
- Maç şut verisi: `https://understat.com/match/{id}` sayfasında hâlâ gömülü `var shotsData = JSON.parse('...')` (footix) [ORTA].
- robots.txt: site kapalı olduğu için okunamadı → BULUNAMADI.

---

## 5. forebet.com

WebFetch ile siteye erişilemedi (client_error; büyük olasılıkla Cloudflare/bot koruması) — robots.txt de okunamadı [YÜKSEK gözlem]. GitHub Actions'tan düz `requests` ile de engellenme olasılığı yüksek → Playwright gerekebilir.

### URL'ler
- Günlük tahminler: `https://www.forebet.com/en/football-tips-and-predictions-for-today` [YÜKSEK — [999Samurai/predictions-scraper](https://raw.githubusercontent.com/999Samurai/predictions-scraper/main/scraper.py)]
- Lig sayfası örüntüsü: `https://www.forebet.com/en/predictions-world/world-cup` görüldü ([SO arşivi](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/74793611/trying-to-scrape-text-from-forebets-com)). Süper Lig için `.../en/football-tips-and-predictions-for-turkey/super-lig` denendi, doğrulanamadı [DÜŞÜK].
- Ü/A ve BTTS sayfaları: `.../en/football-predictions/under-over-25-goals` ve `.../en/football-predictions/both-to-score` benzeri — **BULUNAMADI/doğrulanmadı** [DÜŞÜK].

### HTML seçiciler
| Seçici | İçerik | Güven |
|---|---|---|
| `div.rcnt` (ör. `rcnt tr_1`, `tr_0`) | Maç satırı | YÜKSEK (iki kaynak) |
| `span.homeTeam`, `span.awayTeam` | Takımlar | ORTA (SO cevabı) |
| `meta[itemprop="name"]` (`content`) | Maç adı | ORTA (999Samurai) |
| `span.date_bah` | Tarih | ORTA |
| `span.forepr` | Tahmin (1/X/2) | YÜKSEK (iki kaynak) |
| `div.ex_sc.tabonly` | Tahmini skor | ORTA |
| `tnmscn` | Takım linki kapsayıcısı | ORTA |
| `fprc` (olasılık yüzdeleri), `avg_sc` | **Doğrulanamadı** | DÜŞÜK |

Olasılık alanları mevcut (Apify aktörü 1/X/2 ve Ü/A 2.5 yüzdelerini, `predictedScore`, `averageGoals` çıkarıyor — [julian.thurian/forebet-predictions-scraper](https://apify.com/julian.thurian/forebet-predictions-scraper)), ancak sınıf adları teyit edilmedi. **Öneri:** ilk çalıştırmada HTML'i kaydedip seçicileri yerinde doğrulayın.

---

## 6. soccerstats.com

### URL'ler [YÜKSEK — sayfalar WebFetch ile açıldı]
| Sayfa | URL | İçerik |
|---|---|---|
| Lig ana | `https://www.soccerstats.com/latest.asp?league=turkey` | Puan tablosu (#, Team, GP, W, D, L, GF, GA, GD, Pts, Form, PPG, last 8, CS, SR…), iç/dış saha tabloları |
| **Gol istatistikleri** | `https://www.soccerstats.com/trends.asp?league=turkey` | Başlık "Goals statistics"; takım başı `GP`, `Avg`, `0.5+`…`5.5+` (yüzde; **2.5+ = Ü2.5%**), **`BTS`** (KG%), `CS`, `FTS`, `WTN`, `LTN`; Total/Last 8/Home/Away filtreleri |
| Sonuçlar | `https://www.soccerstats.com/results.asp?league=turkey&pmtype=bydate` | Ay başlıkları altında tarih, "Home vs Away", `Res.` (`0:1`), `HT` (`(0:0)`) |

- Lig kodu `league=` parametresi (ör. `turkey`, `england`, `england4`) — [Apify SoccerStats](https://apify.com/automation-lab/soccerstats-football-stats-scraper).
- Bazı bölümler üyelik gerektiriyor ("full table is for members") → tablo kesik gelebilir [YÜKSEK].
- Tablo id/class adları (ör. `#btable`, `tr.trow*`) **doğrulanamadı** [DÜŞÜK] — `pandas.read_html` ile başlık metnine ("GP", "BTS", "2.5+") göre tablo seçmek daha dayanıklı.
- robots.txt: `*` için `/cdn-cgi/`, `/js/`, `.php`, resimler ve "1000" içeren URL'ler disallow; Content-Signal: AI eğitimi hayır, arama/AI girdi evet; ClaudeBot/GPTBot'a tam izin ([robots.txt](https://www.soccerstats.com/robots.txt)). `.asp` sayfaları serbest.

---

## 7. Flashscore

### Feed API [ORTA — birden çok kaynak, ama x-fsign değeri değişebilir]
- Header: `x-fsign: SW9D1eZo` — 2020'den beri birçok kaynakta aynı değer ([furas.pl](https://blog.furas.pl/python-scaping-how-to-scrape-flashscore.com.html), [DxDiagDx gist](https://gist.github.com/DxDiagDx/6277d7a055fef53436077b2eb2330c7d), [simbirsky README](https://github.com/simbirsky/flashscore-football-parser/blob/main/README.md)). Değer sayfanın JS'inden okunup güncellenmeli; Playwright ile sayfa açıp `/x/feed/` isteklerini dinlemek en güvenli.
- Host'lar: `https://d.flashscore.com/x/feed/{feed}`, `https://d.flashscore.ru.com/x/feed/...`, `https://local-ruua.flashscore.ninja/46/x/feed/...` (proje/dil'e göre değişiyor).
- Feed örnekleri:
  - Günlük maç listesi: `f_1_{gün_ofseti}_3_{dil}_1` (ör. `f_1_0_3_en_1`; `1`=futbol, `0`=bugün, `-1`=dün) [ORTA]
  - Maç özeti: `df_sui_1_{eventId}` [ORTA]
  - Puan tablosu: `ss_1_{tournamentId}_{stageId}_table_overall` [ORTA]
  - Oranlar: `https://46.ds.lsapp.eu/pq_graphql?_hash=ope&eventId=...&projectId=46&geoIpCode=..` [DÜŞÜK]
- Yanıt formatı: düz metin; kayıtlar `¬` ile ayrılır, anahtar/değer `÷` ile; `~` yeni kayıt başlatır. `AA` = event id, `AD` = epoch, `AE`/`AF` = ev/dep takım, `AG`/`AH` = skor ([DxDiagDx gist](https://gist.github.com/DxDiagDx/6277d7a055fef53436077b2eb2330c7d)) [ORTA].

### Sakat/cezalı ("Missing players")
- Feed adı **BULUNAMADI** (`df_li_1_*` = lineups olduğu tahmin ediliyor [DÜŞÜK]). Crawlora MCP'de ayrı bir `flashscore_match_missing_players` aracı var ("eksik ve şüpheli oyuncular + sebep") ve lineups aracı "sağlayıcının ham ayrılmış metin feed'ini" döndürüyor → missing players lineup feed'i içinde ya da ayrı bir feed'de [ORTA varlık / DÜŞÜK isim] ([lineups](https://glama.ai/mcp/servers/Crawlora-org/crawlora-mcp/tools/flashscore_match_lineups), [missing](https://glama.ai/mcp/servers/Crawlora-org/crawlora-mcp/tools/flashscore_match_missing_players)).
- Alternatif: takım `/squad/` sayfasındaki sakatlık rozetleri (Puppeteer Stealth + residential proxy öneriliyor) ([Apify injuries actor](https://apify.com/harry.automazione/flashscore-injuries-suspensions)).
- **Playwright önerisi:** maç sayfasını `#/match-summary/lineups` (veya "Kadrolar") sekmesiyle aç, `page.on("response")` ile `/x/feed/` yanıtlarını yakala, "Missing players"/"Eksik oyuncular" başlığını DOM'da ara. Bu kesin seçici değil, doğrulanmalı.
- robots.txt: `*` için `/football/.../live|finished|scheduled`, `/standings/`, `/draw/` disallow; **`/x/feed/` için kural yok**; birçok AI botu tamamen engelli ([robots.txt](https://www.flashscore.com/robots.txt)). Kullanım şartları ticari scraping'i büyük olasılıkla yasaklıyor (ToS okunmadı).

---

## 8. SportyTrader ve FreeSuperTips

### SportyTrader [ORTA]
- Maç tahmini URL'si: `https://www.sportytrader.com/en/betting-tips/{ev-slug}-{dep-slug}-{id}/` (ör. `/en/betting-tips/galatasaray-eyupspor-231097/`) — arama sonuçlarında çok sayıda Süper Lig örneği var.
- Lig liste sayfası URL'si **doğrulanamadı** (`/en/betting-tips/football/turkey/super-lig-210/` denendi, erişilemedi) [DÜŞÜK].
- Tahmin metni: üstte "Prediction :" etiketinin yanında tek satır (ör. "Galatasaray to win and over 3.5"), altta "Our {Ev} vs {Dep} Prediction" başlıklı bölüm; oran gösterilmiyor ([örnek sayfa](https://www.sportytrader.com/en/betting-tips/galatasaray-eyupspor-231097/)). CSS sınıfı/JSON-LD doğrulanamadı → metin tabanlı ("Prediction" etiketi) çıkarım.
- robots.txt: `/async/`, `/widgets/`, `/book/`, `/{dil}/preview/`, üye alanları disallow; `/en/betting-tips/` serbest ([robots.txt](https://www.sportytrader.com/robots.txt)).

### FreeSuperTips [ORTA]
- Hub: `https://www.freesupertips.com/predictions/`
- Maç sayfası: `https://www.freesupertips.com/predictions/{ev}-vs-{dep}-predictions-betting-tips-match-previews/` (tekrarda `-2` eki).
- Tahminler H4 başlıklarında bahis adı olarak ("Besiktas to Win", "Besiktas 3-1"), yanında kesirli oran ("5/4" + "odds when tipped") ve "Reason for tip" paragrafı ([örnek](https://www.freesupertips.com/predictions/celtic-vs-besiktas-predictions-betting-tips-match-previews/)). JSON-LD görülmedi.
- **Süper Lig kapsamı zayıf**: listede yer alıyor ama özel sayfa yok, çoğunlukla büyük Avrupa ligleri/UEFA maçları.
- robots.txt: `/team/`, `/tag/`, `/stat-details/`, `/redirect/` vb. disallow; `/predictions/` serbest ([robots.txt](https://www.freesupertips.com/robots.txt)).

---

## 9. Resmi ücretsiz API'ler

### API-Football (api-sports.io) [YÜKSEK]
- Base: `https://v3.football.api-sports.io/` · Header: `x-apisports-key: <KEY>` (RapidAPI üzerinden ise `x-rapidapi-key`) ([başlangıç rehberi](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide), [sezginn07 proxy.mjs](https://raw.githubusercontent.com/sezginn07/iddaa/main/server/proxy.mjs)).
- Free: **100 istek/gün**, tüm endpoint ve ligler ([pricing](https://www.api-football.com/pricing)); dakika limiti sayfada yazmıyor — `X-RateLimit-*` yanıt header'larını izleyin.
- **Kritik kısıt:** Free plan güncel sezonu vermiyor: hata `{"plan": "Free plans do not have access to this season, try from 2022 to 2024."}` (Ekim 2026'da raporlanmış) ([GitHub issue](https://github.com/anthonyevans29/Sports-Predictor/issues/554)) → 2025/26 ve 2026/27 Süper Lig maçları/sakatlıkları ücretsiz planda **alınamaz**; yalnız tarihsel model eğitimi için kullanılabilir.
- Endpoint örnekleri: `/fixtures?league={id}&season={yyyy}`, `/standings`, `/injuries?fixture=` veya `?league=&season=`, `/odds`, `/predictions?fixture=`. Süper Lig league id **203** [ORTA — yaygın bilgi, bu oturumda doğrulanmadı].

### football-data.org [YÜKSEK]
- Base: `https://api.football-data.org/v4` · Header: `X-Auth-Token: <KEY>` ([ingestr dokümanı](https://getbruin.com/docs/ingestr/supported-sources/football-data-org.html)).
- Free: **10 istek/dk**, 12 yarışma: Premier League, Championship, Bundesliga, Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga, Brasileirão, Şampiyonlar Ligi, Dünya Kupası, Avrupa Şampiyonası ([coverage](https://www.football-data.org/coverage), [pricing](https://www.football-data.org/pricing)). Kodlar (PL, ELC, BL1, SA, PD, FL1, DED, PPL, BSA, CL, WC, EC) [ORTA — sayfa kod göstermiyor].
- **Süper Lig ücretsiz değil** (coverage tablosunda var, free listesinde yok). Free: fikstür, tablo, gecikmeli skor; kadro/oran/canlı yok.

---

## 10. Transfermarkt

- Lig sakatlık sayfası: lig ana URL'sinde `startseite` → `verletztespieler` + `/plus/1`:
  `https://www.transfermarkt.com/super-lig/verletztespieler/wettbewerb/TR1/plus/1` (Süper Lig kodu `TR1`) [YÜKSEK örüntü — [worldfootballR tm_league_injuries.R](https://rdrr.io/github/JaseZiv/worldfootballR/src/R/tm_league_injuries.R); TR1 kodu ORTA]
- Cezalılar: `startseite` → `sperrenausfaelle` + `/plus/1` (ilk `div.box` = cezalılar, ikinci = kart sınırındakiler) ([tm_league_suspensions.R](https://rdrr.io/github/JaseZiv/worldfootballR/src/R/tm_league_suspensions.R)).
- Oyuncu sakatlık geçmişi: profil URL'sinde `profil` → `verletzungen` + `/plus/1` ([tm_player_injury_history.R](https://rdrr.io/github/JaseZiv/worldfootballR/src/R/tm_player_injury_history.R)).
- Seçiciler (sakatlık tablosu): `#yw1 tbody` satırları; oyuncu `.inline-table .hauptlink a`, kulüp `.tiny_wappen[alt]`, sakatlık `td.links`, başlangıç `.links + td`, dönüş `.links ~ .zentriert + td.zentriert`, değer `td.rechts`. Cezalılar: `table.items tbody tr`, sebep `td:nth-child(4)`, since/until 5/6, kaçırılan maç 7.
- **Engelleme:** WebFetch "SITE_BLOCKED" döndü; transfermarkt-scraper projesi GitHub Actions isteklerinin **DataDome** tarafından engellendiğini ve Bright Data Web Unlocker'a düştüğünü yazıyor ([dcaribou/transfermarkt-scraper](https://github.com/dcaribou/transfermarkt-scraper)) [YÜKSEK]. → GitHub Actions'tan güvenilmez; düşük öncelik veya yerel/elle çalıştırma.

---

## Özet öncelik önerisi
1. **Oran (bugün/yarın):** iddaa `sportsbookv2` (birincil) + Nesine `getprebultenfull` (çapraz kontrol).
2. **Tarihsel sonuç + kapanış oranı:** football-data.co.uk `mmz4281/{sezon}/T1.csv`.
3. **Form/Ü-A/KG yüzdeleri:** soccerstats `trends.asp?league=turkey`.
4. **xG:** understat (Süper Lig yok, şu an site kapalı) — sadece büyük 5 lig için.
5. **Tahmin siteleri (forebet, sportytrader, freesupertips):** düşük güven seçiciler, Playwright + ilk çalıştırmada HTML doğrulama.
6. **Sakatlık:** Transfermarkt (engelli) / Flashscore (feed adı belirsiz) / API-Football (güncel sezon free'de yok) → hepsi zayıf; en makul yol Flashscore + Playwright.
