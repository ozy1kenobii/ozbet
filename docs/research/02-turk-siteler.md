# 02 — Türkiye'deki iddaa tahmin, oran analizi ve istatistik siteleri

Hazırlayan: Ajan 2 · Tarih: 6 Kasım 2026 · Yöntem: WebSearch + WebFetch (yalnızca okuma, veri çekilmedi).
Kapsam dışı (başka ajanda): iddaaorananalizi.com, iddaaorantahmin.com, huhsports.com, spordb.com.

> Tüm özetler kendi cümlelerimizledir. "Görülmedi" = WebFetch'in döndürdüğü metinde yoktu; sitede hiç olmadığı anlamına gelmez
> (çoğu site JS ile yükleniyor). Robots.txt bulguları 6 Kasım 2026 tarihli WebFetch çıktısıdır.

## 1. Arama özeti
Kullanılan sorgular: "iddaa oran analizi maç tahmin istatistik", "kg var / korner istatistik maç simülasyonu",
"düşen oranlar takip banko analiz", "bahisanaliz oranı düşen maçlar", "nesine istatistik merkezi",
"maç analizi form h2h alt üst yüzdesi", "benzer oranlar analizi geçmiş aynı oranlı maçlar", "mackolik tahmin Opta".
Gözlem: Türkçe aramalarda sonuçların büyük kısmı spam/yasa dışı bahis tanıtım sayfası (ör. "deneme bonusu" içerikli
alan adları, ilgisiz kurumların alt sayfalarına yerleştirilmiş bahis metinleri). Bunlar rapora alınmadı.
Bir forum başlığı kullanıcıların izlediği siteleri listeliyor (çoğu yabancı: forebet, soccervista, fctables, totalcorner, footystats)
— https://forum.donanimhaber.com/takip-ettiginiz-iddaa-sitelerini-tahmincileri-bu-baslik-altinda-toplayalim--66729520-16

**En belirgin Türk nişi:** "benzer oran arşivi" siteleri (bugünkü oranla aynı/yakın oranlı geçmiş maçların sonuç dağılımı).
En az 5 ayrı site bu fikirle para kazanıyor (aşağıda #11, #13–#16).

## 2. Site profilleri

### A. Büyük platformlar (bayi / medya)

**1. Mackolik** — https://www.mackolik.com/iddaa
- Özellik: iddaa programı (kod, 1X2, ÇŞ, A/Ü 2,5 ve diğer oranlar), gün/saat/lig filtresi, canlı sonuç, puan durumu, fikstür, istatistik, iddaa haberleri, TV programı.
- Veri mantığı: lisanslı veri; Mackolik'i alan Perform Group 2013'te Opta'yı da satın aldı (https://webrazzi.com/2013/07/10/perform-group-opta-satin-almasi/). İddaa sayfasında tahmin/düşen oran görülmedi.
- Fikir: maç koduyla arama ve takıma tıklayınca detay — bülten→takım akışı çok sade.
- Kalite: güvenilir veri, tahmin iddiası yok. Belirli bir bahis şirketine yönlendirme görülmedi.
- robots.txt (https://www.mackolik.com/robots.txt): `*` için izin, `/api/` ve `/_nuxt/` kapalı; GPTBot, CCBot, Google-Extended, Amazonbot ve **anthropic-ai tamamen engelli**. → Otomatik erişim/yapay zekâ kullanımı istenmiyor.

**2. Sahadan** — https://www.sahadan.com/
- Özellik: canlı skor (sayfa yenilemeden gol/kırmızı kart), iddaa programı (kod, saat, oran), anlık gol bildirimi, puan durumu, fikstür, "maç öncesi analiz", "tahmin bilgileri".
- Maç başına ayrı bir "/tahmin" sayfası var; arama sonucunda başlığı "Maç Analizi ve İstatistiksel Tahminler" olarak görünüyor
  (https://www.sahadan.com/mac/aek-vs-real-madrid/5sd3mtbev6bvpnd9oi9klkmxg/tahmin). Sayfa WebFetch ile açılamadı (client_error); yöntem doğrulanamadı.
- Fikir: maç kartında "Tahmin" sekmesi — istatistiksel tahmini maç detayının bir sekmesi yapmak.
- robots.txt (https://www.sahadan.com/robots.txt): Mackolik ile aynı; **anthropic-ai, GPTBot, CCBot vb. tamamen engelli**.

**3. Nesine (iddaa bayisi)** — https://www.nesine.com/iddaa/istatistik
- Özellik: bülten, lig/tarih filtresi, "Oran Değişimi Tercihleri" ayarı, editör ve üye yorumları, bahis türü bilgi ekranı. Bu sayfada form/H2H/korner verisi görülmedi.
- Fikir: **bahis türü açıklama ekranı** (her market ne demek) ve oran değişimi bildirim tercihleri.
- Not: lisanslı bayi; site doğrudan bahis oynatır (OZBET bunu yapmaz ve link vermemeli).
- robots.txt (https://www.nesine.com/robots.txt): genel gruba çok sayıda Disallow (hesap, kupon, bazı /iddaa/ listeleri); **ClaudeBot, anthropic-ai, GPTBot vb. için açıkça `Allow: /`**, dosyada "LLM'ler kullanabilir" yorumu ve llms.txt var. (OZBET'in mevcut Nesine bülten JSON kullanımı ayrıca kullanım şartlarıyla değerlendirilmeli; ToS sayfası bu çalışmada okunmadı.)

**4. iddaa.com (resmi)** — https://www.iddaa.com/
- Özellik: lig analiz (puan durumu/fikstür), yazar yorumları, popüler bahisler ve hazır kuponlar, canlı sonuç, kural/yardım sayfaları ("Kral oran nedir" vb.), **Sorumlu Oyun** bağlantısı.
- Fikir: "popüler bahisler" (oynanma yoğunluğu) — kitle davranışı göstergesi; sorumlu oyun bölümünün görünür yerleşimi.
- robots.txt (https://www.iddaa.com/robots.txt): `*/mac-detay/*` kapalı; Claude dahil AI botlarına (`claudebot`, `claude-user`, `claude-code` …) **`Allow: /`**.

**5. Bilyoner** — https://www.bilyoner.com/
- Özellik: meta açıklamada "yapay zeka iddaa tahminleri" ve "uzman yorumları"; robots.txt'ten Tribün (sosyal takip), favoriler, "sana özel maçlar" bölümleri anlaşılıyor.
- Fikir: kişiselleştirilmiş maç listesi (favori lig/takım).
- robots.txt (https://www.bilyoner.com/robots.txt): hesap/kupon yolları kapalı; botlara özel kural yok; `Content-Signal: search=yes, ai-train=no, ai-input=yes`.

**6. Misli** — https://www.misli.com/
- Özellik: medya ortaklarında yayınlanan "Misli'den Günün Tüyoları": her maç için tek bir çarpıcı istatistik (ör. "iç sahadaki 13 maçın 12'si KG Var", "son 6 lig maçında 1,5 Üst", H2H galibiyet serisi)
  (https://www.fanatik.com.tr/iddaa/kadikoydeki-fenerbahce-besiktas-derbilerinde-kg-var-bahsi-one-cikiyor-iste-misliden-gunun-tuyolari-2618700). xG/xA gibi ileri metrikler üyelere kapalı.
- Ligi başına üç **yapay zekâ yorumcu karakter** (Asya, İskandinav, Amerika ligleri); AI olduğu açıkça yazıyor ama "%71 başarı" iddiası doğrulanmamış (https://www.fanatik.com.tr/iddaa/mislide-yeni-donem-yapay-zeka-destekli-futbol-yazarlari-takimimiza-katildi-2627693).
- Fikir: **"tek cümlelik trend kartı"** (seri + iç/dış saha ayrımı) — çok okunur, kural tabanlı üretilebilir.
- Kalite/hukuk: haberler bahis platformu tanıtımı niteliğinde ("heyecan Misli'de"). Lisanslı bayi olsa da OZBET bu tonu kopyalamamalı.
- robots.txt (https://www.misli.com/robots.txt): tek `*` grubu; kupon/hesap/Misli Arena yolları kapalı, AI botlarına özel kural yok.

**7. Oley** — https://www.oley.com/
- Özellik: Tüyolar, "Zirvedekiler" sıralaması, Sosyoleyci (sosyal), Popüler Kuponlar (oran + kupon bedeli), canlı skor, 1X2 oranları + ek bahis sayısı.
- Fikir: tahminci sıralaması (leaderboard) — OZBET'te kendi modelinin karnesi zaten bunun dürüst karşılığı.
- robots.txt (https://www.oley.com/robots.txt): `/statistic`, `/api/`, `/tracker`, `/sosyoley/` kapalı; AI botlarına özel kural yok.

**8. FutbolArena** — https://www.futbolarena.com/
- Özellik: haber/transfer/video, Analiz bölümü, Dünkü Maçlar; İstatistik sayfası Sportradar bağlantısı içeriyor (https://www.futbolarena.com/istatistik).
- **İddaa ve Canlı Skor menü bağlantıları bilyoner.com'a gidiyor** — medya → bayi yönlendirmesi örneği.
- robots.txt (https://www.futbolarena.com/robots.txt): geniş izin; reklam ve canlı anlatım yolları kapalı.

**9. TFF** — https://www.tff.org/default.aspx?pageID=198
- Özellik: resmi Süper Lig puan cetveli (O-G-B-M-A-Y-Av-P), haftalık fikstür ve skorlar, maç "Detaylar", gol krallığı.
- Fikir: resmi kaynak doğrulaması (puan durumu çapraz kontrol). Bahis içeriği yok.
- robots.txt: WebFetch ile alınamadı (client_error) → **izin durumu bilinmiyor**, otomatik erişim planlanmamalı.

**10. Transfermarkt.com.tr** — https://www.transfermarkt.com.tr/
- WebFetch "SITE_BLOCKED" döndü; robots.txt ve içerik doğrulanamadı. README'ye göre OZBET sakatlık listesi için deniyor ve DataDome engeli var.
  Bu çalışma yeni bilgi eklemiyor; **robots/ToS kontrolü manuel yapılmalı**.

### B. Bağımsız analiz siteleri (Türkçe)

**11. Derin Tahmin** — https://www.derintahmin.com/
- Özellik: takım karşılaştırma, 2,5 A/Ü analizi, bülten analizi, "dünün analiz sonuçları"; 2012'den beri ~130 bin maç.
- Veri mantığı: oranları geçmiş maçlarla **4 kademeli eşleştirme** (tam eşleşme → yakın kombinasyon → baskın oran → tekil) ve sabit ağırlıklarla birleştirme. "Yapay zekâ" deniyor, ağırlıklar açıklanmıyor; "±%3 hata payı" iddiası dayanaksız.
- Fikir: **eşleşme kalitesine göre kademeli benzer-oran analizi** (az örnekte geniş toleransa düş).
- Ücret: VIP 119 ₺/ay, 799 ₺/yıl. Bahis oynatmadığını yazıyor ama "Sistem Tavsiyesi/MS 1" etiketleri tavsiye diliyle çelişiyor.
- robots.txt (https://www.derintahmin.com/robots.txt): `*` izinli; yalnız `/api.php`, `/datascraper.db`, cache json kapalı.

**12. iddaaTahmin11** — https://www.iddaatahmin11.com/
- Özellik: günlük tahmin, banko kupon, "Ne Oynadılar", **"Oranı Düşen Maçlar"**, canlı sonuç, at yarışı.
- Veri mantığı: form, gol ortalaması, sakat/cezalı, hava, oran hareketi değerlendirildiği söyleniyor; "%73 başarı oranı" iddiasının dönemi/örneklemi yok.
- **Hukuki risk:** kuponlarda "… ile Oyna" butonları ve bayi bağlantıları, ücretli kupon; ticari ilişki açıklanmamış. OZBET'in kaçınması gereken örnek.
- robots.txt (https://www.iddaatahmin11.com/robots.txt): `/istatistik/`, `/macdetay.php`, `/takim/` vb. kapalı; ClaudeBot dahil AI botlarına Allow ama aynı Disallow'lar geçerli.

**13. Oran Analizim** — https://www.orananalizim.tr/
- Özellik: oran girip benzer oranlı geçmiş maçların sonuç dağılımı (örnek: 62 benzer maçta ev sahibi %48), **tolerans seçimi ±0,05/±0,10/±0,20**, kapanış oranına göre eşleşme, lig ve tarih aralığı filtresi, kaydedilip paylaşılabilen filtreler, toplu analiz, kupon simülatörü, "güven endeksi".
- Kalite: veritabanı büyüklüğü sayfada tutarsız (128K…350K). Abonelikli (Whop, iadesiz).
- robots.txt (https://www.orananalizim.tr/robots.txt): `ai-train=no`; ClaudeBot/anthropic-ai aynı dosyada hem `Disallow: /` hem `Allow: /` — çelişkili, **izin yok kabul edilmeli**.

**14. OranAnalizi.com (OddsTips tanıtımı)** — https://orananalizi.com/
- Özellik: iddaa + Bet365 + 24'ten fazla bookmaker açılış/kapanış arşivi (800 bin+ maç iddiası), manuel/akıllı/otomatik analiz, "AI Oran Radarı", H2H + benzer oranlı maç kıyası.
- Kalite/hukuk: sayfa referans linkleriyle OddsTips'e yönlendiriyor; yurt dışı bookmaker adları (Bet365) Türkiye'de lisanssız operatörler — tanıtım riski.
- robots.txt (https://orananalizi.com/robots.txt): hiçbir Disallow yok.

**15. ORANANALİZ** — https://www.orananaliz.com/
- Özellik: 10 yıllık 700 bin+ maç arşivi, "Tam" ve "Yaklaşık (±%5)" eşleşme, F1–F7 hazır filtreler (Üst 2,5, KG Var, İY gol, ev favori…), kendi filtresini kaydetme, açılış-kapanış kaydı ve "Navigasyon Modu" ile oran hareketi.
- Ücret: ücretsiz demo (günlük 3 filtre testi), tam erişim PRO.
- robots.txt (https://www.orananaliz.com/robots.txt): `/analiz/`, `/api/` kapalı; AI botlarına bilinçli `Allow: /` (GEO amaçlı).

**16. Oranlarla Kazan** — https://www.oranlarlakazan.net/
- Özellik: yurt dışı bahis bürolarının güncel/geçmiş oranları, İY/MS skorları, 2021'den beri arşiv, 4 filtreli analiz tablosu, **hakem analizi**, kupon hazırlama; ücretli üyelik.
- Hukuk: Bet365/1xbet verisi ve "Bet365 Kupon Yap" özelliği — lisanssız operatör adı/tanıtımı riski.
- robots.txt (https://www.oranlarlakazan.net/robots.txt): boş Disallow (her şey açık, Yoast).

**17. İddaaCetveli** — http://www.iddaacetveli.com/iddaa_analiz_sistemi.php
- Arama sonucunda "benzer oran" kategorisinde çıktı; WebFetch **robots_disallowed** döndü → içerik incelenmedi, otomatik erişim yok kabul edildi.
  (Aynı durum: grispor.com — robots_disallowed.)

## 3. Yaygın ve ayırt edici özellikler

**Neredeyse herkeste (kullanıcı beklentisi):**
| Özellik | Görüldüğü siteler |
|---|---|
| Kodlu günlük bülten + 1X2/A-Ü/KG oranları, lig/saat filtresi | Mackolik, Sahadan, Nesine, iddaa.com, Oley, iddaaTahmin11 |
| Canlı skor / dünün sonuçları | Mackolik, Sahadan, iddaa.com, Oley, FutbolArena, iddaaTahmin11, Derin Tahmin (VIP) |
| Puan durumu + fikstür | Mackolik, Sahadan, iddaa.com, TFF |
| Yorum/tüyo (editör, yazar veya AI) | Nesine, iddaa.com, Bilyoner, Misli, Oley, iddaaTahmin11 |
| Banko/hazır kupon | iddaa.com, Oley, iddaaTahmin11, Oran Analizim |
| 18+ / "garanti yok" uyarısı | iddaa.com, iddaaTahmin11, Oran Analizim, OranAnalizi.com, ORANANALİZ |

**Ayırt edici:**
| Özellik | Siteler | Değerlendirme |
|---|---|---|
| Benzer oran arşivi analizi (tolerans, tarih, lig filtresi) | Derin Tahmin, Oran Analizim, OranAnalizi.com, ORANANALİZ, Oranlarla Kazan | Türk pazarının en çok para ödenen nişi |
| Kaydedilebilir/hazır filtre şablonları (F1–F7) | ORANANALİZ, Oran Analizim | Kullanıcıyı geri getiriyor |
| Oranı düşen maçlar / açılış-kapanış hareketi | iddaaTahmin11, ORANANALİZ, Nesine (ayar) | OZBET'te var |
| Tek cümlelik trend/seri kartları | Misli tüyoları | Ucuz, çok okunur |
| AI yorumcu karakterleri | Misli, Bilyoner | OZBET'te LLM yorum var |
| Hakem analizi | Oranlarla Kazan | Kart marketleri için |
| "Popüler bahisler / ne oynadılar" | iddaa.com, Oley, iddaaTahmin11 | Veri yalnız bayilerde |
| Tahminci/tahmin sıralaması | Oley (Zirvedekiler) | — |
| Doğrulanabilir, yöntemi açık geçmiş performans | **Hiçbirinde görülmedi** (yalnızca kaynaksız "%71/%73" iddiaları) | OZBET'in en güçlü farkı: karne + backtest |
| Olasılık modeli + Monte Carlo + skor dağılımı | Açık yöntemle hiçbirinde görülmedi (Sahadan "/tahmin" doğrulanamadı) | OZBET'te var |

## 4. Hukuki ve etik notlar (7258 sayılı Kanun)
- Lisanssız/yurt dışı operatör adı, linki veya "kupon yap" butonu (OranAnalizi.com, Oranlarla Kazan) → yasa dışı bahis reklamı riski. OZBET hiçbir operatörün adını tanıtım amaçlı kullanmamalı, link vermemeli.
- Lisanslı bayilere bile "… ile Oyna" yönlendirmesi (iddaaTahmin11, FutbolArena→Bilyoner) ticari ilişki/reklam sayılabilir; OZBET'te yönlendirme butonu olmamalı.
- Kaynaksız "%73 başarı", "banko", "kazanma şansını artırın" dili yanıltıcı; OZBET'in dürüst karnesiyle çelişir, kopyalanmamalı.
- Aramada görülen spam alan adları ("deneme bonusu" içerikleri) yasa dışı reklam ağına ait; kaynak olarak kullanılmamalı.
- Ücretli kupon satışı tüketici hukuku açısından ayrıca riskli; OZBET ücretsiz ve tavsiye niteliği taşımayan dille kalmalı.

## 5. OZBET ile karşılaştırma
OZBET'te var (README): Dixon-Coles + 10.000 MC, 1X2 / Ü-A 1,5-2,5-3,5 / KG / İY-MS / en olası 5 skor, değer etiketi,
oran hareketi ve düşen oran alarmı, kadro düzeltmesi, kaynak konsensüsü, LLM veya kural tabanlı yorum, karne, haftalık backtest,
kaynak durumu sayfası, PWA, 18+ uyarısı.

| Beklenen/ayırt edici özellik | Rakiplerde | OZBET |
|---|---|---|
| Bülten + oran + filtre | Yaygın | Var |
| Olasılık + skor dağılımı | Nadir | Var (güçlü fark) |
| Düşen oran | 3 site | Var |
| Doğrulanabilir karne | Yok | Var (güçlü fark) |
| Benzer oran arşivi analizi | 5 site | **Yok** |
| Trend/seri kartları (son N maç, iç/dış ayrımı) | Misli + çoğu istatistik sitesi | **Yok** (yorumda dağınık olabilir) |
| H2H geçmişi | Derin Tahmin, OranAnalizi.com | **Yok** (README'de geçmiyor) |
| Puan durumu / fikstür | 4 site | **Yok** |
| Korner / kart istatistiği | Oranlarla Kazan (hakem), Misli (ileri metrik) | **Yok** (veri football-data.co.uk'ta mevcut) |
| Hakem analizi | 1 site | Yok |
| Kayıtlı filtre / favori lig-takım | ORANANALİZ, Oran Analizim, Bilyoner | **Yok** |
| Market açıklama sözlüğü | Nesine, iddaa.com | **Yok** |
| Sorumlu oyun sayfası/bağlantısı | iddaa.com | Yalnız kısa uyarı |
| Canlı skor | Yaygın | Yok (günde 3 güncelleme; kapsam dışı kalmalı) |
| Popüler bahisler | 3 site (bayi verisi) | Yok (veri yok, alınmamalı) |

## 6. OZBET'te eksik olan ve alınması önerilen özellikler
| # | Özellik | Kaç sitede var | Veri kaynağı önerimiz | Emek |
|---|---|---|---|---|
| 1 | Benzer oran analizi: maçın marjsız kapanış/açılış oranına ±tolerans içinde geçmiş maçların 1X2, Ü2,5, KG dağılımı + örneklem sayısı; model olasılığıyla yan yana | 5 | football-data.co.uk açılış/kapanış oranları (12.475 maç zaten önbellekte); kendi `archive` | M |
| 2 | Trend kartları: "son 6 iç saha maçında 5 KG Var" gibi otomatik, kaynaklı tek cümleler (iç/dış ayrı) | 2+ | football-data.co.uk + flashscore arşivi; kural tabanlı üretim | S |
| 3 | H2H özeti (son 5–10 karşılaşma, gol ortalaması) | 2 | football-data.co.uk geçmiş sonuçları | S |
| 4 | Puan durumu + form şeridi (G/B/M son 5) | 4 | Kendi sonuç verimizden hesap (dış kaynak gereksiz) | S |
| 5 | Korner ve kart beklentisi (takım ort. + Poisson; Ü/A korner ve kart olasılığı) | 2 | football-data.co.uk HC/AC, HY/AY/HR/AR sütunları | M |
| 6 | Hakem kart profili | 1 | football-data.co.uk `Referee` sütunu (yalnız İngiltere ligleri) | M |
| 7 | Kayıtlı filtre / favori lig-takım (cihazda) | 3 | localStorage, sunucu gerekmez | S |
| 8 | Market sözlüğü (KG, İY/MS, MBS, handikap nedir) | 2 | Kendi metnimiz | S |
| 9 | Sorumlu oyun sayfası (yardım hattı bilgisi, limit önerileri) ve "tavsiye değildir" sabit bandı | 1 (iddaa.com) | Kendi metnimiz; resmi kaynaklara bağlantı | S |
| 10 | Benzer-oran sonucunu modelin karnesi gibi backtest etmek (rakiplerde olmayan dürüstlük katmanı) | 0 | backtest.py genişletmesi | M |

Alınmaması önerilenler: bayi/operatör yönlendirme butonları, ücretli/"banko" kupon, kaynaksız başarı yüzdesi, popüler bahis verisi
(yalnız bayilerde var, kazınamaz), Mackolik/Sahadan/Transfermarkt/Oran Analizim/İddaaCetveli/grispor içeriğine otomatik erişim
(robots.txt AI botlarını engelliyor veya doğrulanamadı).
