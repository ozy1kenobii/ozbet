# OZBET

Her gün kendi kendine güncellenen, telefonda ve masaüstünde çalışan futbol maç analiz ve simülasyon sitesi.
Sunucu yok: Python veri hattı GitHub Actions'ta çalışır, sonuçları `data/*.json` olarak depoya yazar,
React PWA bu JSON'ları okur ve GitHub Pages'te yayınlanır. Günlük kullanımda yapay zekâ kredisi harcanmaz.

> İstatistiksel tahmindir, sonuç garantisi yoktur. 18+, sorumlu oyna.

**Site:** https://ozy1kenobii.github.io/ozbet/

---

## Kurulum (bir kerelik)

1. **Pages'i aç:** Depo → *Settings → Pages → Build and deployment → Source: **GitHub Actions***.
2. **Actions izinleri:** *Settings → Actions → General → Workflow permissions → **Read and write permissions*** (veri commit'i için).
3. **İlk çalıştırma:** *Actions → "OZBET – veri hattı ve yayın" → Run workflow*. İsterseniz "Backtest de çalıştırılsın mı?" kutusunu işaretleyin.
4. Telefonda siteyi açıp tarayıcı menüsünden **Ana ekrana ekle** deyin (PWA, uygulama adı "OZBET").

### Opsiyonel gizli anahtarlar (*Settings → Secrets and variables → Actions*)
| Secret | Ne işe yarar | Yoksa |
|---|---|---|
| `LLM_API_KEY` | Maç başına kısa LLM yorumu (varsayılan model `claude-haiku-4-5`, `LLM_MODEL` ile değiştirilebilir) | Kural tabanlı Türkçe yorum (tam çalışır) |
| `API_FOOTBALL_KEY` | API-Football yedeği | Atlanır |
| `FOOTBALL_DATA_ORG_KEY` | (ileride) football-data.org yedeği | Atlanır |

Sistem hiçbir anahtar olmadan tam çalışır.

---

## Zamanlama
| Türkiye saati | Ne yapar |
|---|---|
| 08:30 | Günün bülteni, model, yorumlar + dünün maçlarının karnesi |
| 13:30 | Oran ve kadro güncellemesi (oran hareketi / düşen oran alarmı) |
| 18:30 | Oran ve kadro güncellemesi |
| Pazartesi 06:00 | Son 2 sezonun backtest raporu (`data/backtest.json`) |

GitHub zamanlanmış işleri yoğun saatlerde 5-30 dk geciktirebilir.

---

## Mimari
Ayrıntılı şema: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Kaynak araştırması: [`docs/SOURCES_RESEARCH.md`](docs/SOURCES_RESEARCH.md).

```
pipeline/ozbet/
  sources/     her site için bir adapter (ortak şemaya çevirir)
  agents/      bülten, istatistik, kadro, konsensüs, piyasa, simülasyon, yorumcu, değer, karne
  model/       Dixon-Coles + Monte Carlo
  run.py       günlük çalıştırma      backtest.py  geçmiş sezon testi
web/           Vite + React + Tailwind PWA
data/          pipeline çıktısı (Actions commit eder)
```

### Model
- **Zaman ağırlıklı Dixon-Coles** (ξ = 0,0019/gün ≈ 1 yıl yarı ömür), lig başına, son 3 sezon football-data.co.uk sonuçlarıyla.
- **xG harmanı** (5 büyük lig, understat erişilebilirse): λ = 0,65·λ_gol + 0,35·λ_xG.
- **İç saha avantajı** lig bazında tahmin edilir; **kadro düzeltmesi**: kilit eksik başına kendi λ × 0,94, rotasyon riski × 0,97.
- **Avrupa kupaları**: takımlar kendi liglerinden bulunur; ClubElo puanı varsa kazanma beklentisi Elo farkından
  (iç saha +63), toplam gol iki takımın lig modellerinden alınır ve λ'lar bu iki değerden çözülür (güven "orta").
  Elo yoksa yaklaşık lig gücü katsayısı kullanılır. Kupada değer etiketi verilmez.
- **10.000 Monte Carlo** simülasyonu (iki yarı ayrı, Dixon-Coles τ önem ağırlığı): 1/X/2, Ü/A 1,5-2,5-3,5, KG, İY/MS, en olası 5 skor, toplam gol dağılımı.
- **Değer**: model olasılığı − marjı temizlenmiş ima olasılığı ≥ %5 → "Değerli". Fark %20'yi aşarsa bu muhtemelen veri/eşleme hatasıdır: değer etiketi verilmez, uyarı konur, yıldız ≤ 2.
- **Karne geri beslemesi**: son 90 günde bir markette isabet, modelin beklediğinin altında kalırsa (≥ 20 tahmin) o marketin model olasılığı piyasaya doğru büzülür ve yıldızı düşer.

### Backtest sonucu (5 Kasım 2026, son 2 tamamlanmış sezon, 6 lig, 3.985 maç)
| | Brier (1X2, düşük = iyi) | Log-loss |
|---|---|---|
| OZBET modeli (saf) | 0,5895 | 0,9885 |
| Model %25 + piyasa %75 harmanı | 0,5767 | – |
| Kapanış oranları (marjsız) | **0,5732** | **0,9648** |

**Dürüst sonuç:** Model, piyasa kapanış oranlarını yenemiyor; hiçbir model ağırlığı/eşik kombinasyonu "değerli bahis"
etiketlerinde geçmişte kâr üretmedi (ROI −%4 … −%14). Bu yüzden:
- "Değerli" etiketi en tutucu ayarla verilir (p = 0,25·model + 0,75·piyasa, eşik %5) ve nadiren çıkar.
- OZBET Tercihi, oranı olan maçlarda bu harmanlanmış olasılıktan seçilir.
- Avrupa kupası ve lig dışı maçlarda değer etiketi hiç verilmez.
- Güncel rapor her pazartesi `data/backtest.json`'a ve sitedeki *Karne* sayfasına yazılır.

---

## Veri kaynakları

| Kaynak | Rol | Durum / not |
|---|---|---|
| **Nesine** bülten JSON | iddaa maç kodu, MBS, oranlar | ✅ Canlıda çalışıyor (5 Kasım: ~1.100 maç). Sonuç uç noktası yok. |
| **iddaa.com** sportsbookv2 (eklendi) | Resmi bülten, oran, MBS | ✅ Canlıda çalışıyor. Nesine düşerse yerine geçer. |
| **football-data.co.uk** (eklendi) | Geçmiş sonuçlar, şut/korner/kart, açılış ve kapanış oranları; fixtures.csv oran yedeği | ✅ Çalışıyor (12.475 geçmiş maç). Model eğitimi ve backtest'in omurgası. Site verinin kişisel kullanım için olduğunu belirtir; günde en fazla birkaç dosya iner, önbelleklenir, ham veri yeniden yayınlanmaz. |
| **Flashscore** | (eskiden) fikstür yedeği, sonuçlar, eksik oyuncular | ⛔ **Kapalı (6 Kasım 2026):** kullanım şartları otomatik istek ve veri çıkarmayı yasaklıyor (md. 2.9–2.10). Adapter kodu duruyor ama çalıştırılmıyor; daha önce biriken `data/archive` sonuçları okunmaya devam eder. |
| **SoccerStats** | Ü2,5 % ve KG % eğilimleri (konsensüse "istatistik oyu") | ⏳ Yalnızca kapsadığı liglerde maç olan günlerde çalışır; ilk Süper Lig gününde doğrulanacak. |
| **Forebet** | Matematiksel tahmin | ❌ **Engelli:** Cloudflare bot koruması GitHub Actions isteklerini reddediyor (HTTP 403). Koruma aşılmaya çalışılmaz; kaynak "eksik" görünür. |
| **SportyTrader** | Uzman tahmini (metinden market çıkarımı) | ✅ Çalışıyor (günde en fazla 20 maç sayfası). |
| **FreeSuperTips** | İpucu | ✅ Çalışıyor. Süper Lig kapsamı zayıf, çoğunlukla büyük ligler/UEFA. |
| **Understat** (eklendi) | xG (5 büyük lig) | ❌ Site bakımda (5 Kasım 2026); açılınca kendiliğinden devreye girer. Süper Lig'i kapsamaz. |
| **Transfermarkt** (eklendi) | Sakatlık listesi | ⏳ İlk büyük lig gününde denenecek; DataDome GitHub Actions IP'lerini sık engelliyor. |
| **API-Football** (eklendi) | Yedek | Ücretsiz katman **güncel sezonu vermiyor** (yalnız 2022-2024) → pratikte yalnızca anahtar + ücretli plan ile işe yarar. |
| football-data.org | — | Ücretsiz katmanda Süper Lig yok; eklenmedi. |
| **ClubElo** (`api.clubelo.com/{tarih}`, eklendi) | Kulüp Elo puanları → Avrupa kupası / çapraz lig maçlarında λ düzeltmesi; maç kartında `elo` | ⏳ **Canlıda doğrulanmadı.** CSV biçimi açık kaynak kütüphanelerin (soccerdata, penaltyblog) belgelerinden alındı; bu ortamdan siteye erişilemedi. Günde 1 istek, 24 saat önbellek. robots.txt izin vermezse kaynak "eksik" görünür ve model eski lig gücü katsayısına döner. |
| **SoccerStats sonuçlar** (`results.asp?league=turkey2`, eklendi) | 1. Lig geçmişi (bu sezon + 2 önceki sezon) | ⏳ **Canlıda doğrulanmadı.** robots.txt yalnızca `/*/info/` yasaklıyor; sayfa yapısı WebFetch ile görüldü (bu sezon İY skorlu, eski sezonlar İY'siz). Yapı değişirse "partial" görünür. |
| **TFF** (`tff.org`, eklendi) | 1. Lig güncel sezon sonuçları (`pageID=142`, son 2 haftada İY skoru maç sayfasındaki gol dakikalarından) + Süper Lig hakem atamaları (`pageID=198` → maç sayfası; TR1 geçmişine `referee`, bugünkü maçlara hakem → kart modeli) | ⏳ **Canlıda doğrulanmadı.** **Kullanım şartı: yalnızca ticari olmayan kullanım ve kaynak gösterme** — sitede "Kaynak: TFF (tff.org)" yazılır, ham veri yeniden yayınlanmaz. robots.txt kontrolü açık, istekler arası ≥5 sn, çalıştırma başına en fazla 40 maç sayfası, biten maç sayfaları kalıcı önbellekte. Hafta ve maç sayfası yapı dökümü her çalıştırmada `.cache/debug/tff-*.txt`. |
| **Birikimli sonuç arşivi** (eklendi) | Flashscore'un günlük sonuçlarını `data/archive/results-{LIG}.json`'a ekler; ≥ 60 maç olan lig modele girer | ⏳ İlk günlerde boş; 1. Lig için ~6 hafta içinde eşik dolar. Kendi verimiz, dış bağımlılığı yalnızca flashscore. |

**Her çalıştırmada her kaynağın gerçek durumu** sitedeki *Kaynaklar* sayfasında ve `data/status.json`'da görünür
(`ok` / `partial` / `missing` + hata notu). Bir kaynak çökerse akış durmaz; maç kartlarında hangi verinin hangi kaynaktan,
hangi saatte geldiği yazar.

### Bilinen sınırlar (dürüst liste)
- Bu ortamdan sitelere erişim yoktu; adapter'lar açık kaynak projelerden doğrulanmış uç noktalara ve seçicilere göre yazıldı
  ve **sahte verilerle** test edildi. **İlk Actions çalıştırmasında** bazı kaynakların `missing/partial` çıkması beklenir;
  Kaynaklar sayfası hangisinin düzeltilmesi gerektiğini gösterir.
- **1. Lig** geçmiş verisi football-data.co.uk'ta yok; SoccerStats sonuç sayfası (canlıda doğrulanmadı) ve birikimli
  flashscore arşivi (60 maç eşiği) ile kapatılmaya çalışılıyor. İkisi de yoksa 1. Lig maçları "Veri yetersiz" görünür.
- Avrupa kupası olasılıkları ClubElo'ya dayanır; Elo'su bulunamayan (adı eşleşmeyen) takımlarda kaba lig gücü katsayısına düşülür.

---

## Bakım
| Belirti | Ne yapılır |
|---|---|
| Kaynaklar sayfasında bir kaynak sürekli **missing** | Notundaki hataya bakın. HTTP 403/429 → site engelliyor; bekleyin veya o kaynağı `pipeline/ozbet/sources/registry.py`'den çıkarın. "yapı değişmiş" → ilgili adapter'daki seçiciyi güncelleyin. |
| Flashscore boş dönüyor | Tarayıcıda flashscore açıp ağ sekmesinde `/x/feed/` isteğindeki `x-fsign` değerini alın, *Settings → Variables* altında `FLASHSCORE_FSIGN` olarak ekleyin ve workflow `env`'ine verin. |
| Bir takım iki farklı adla görünüyor / modelsiz kalıyor | `pipeline/ozbet/teams.py` içindeki `ALIASES` sözlüğüne yazımı ekleyin. |
| Site güncellenmiyor | *Actions* sekmesinde son çalıştırmanın kırmızı adımına bakın; *Run workflow* ile elle yeniden çalıştırın. |
| Yeni sezon | Bir şey gerekmez; sezon kodları tarihten otomatik hesaplanır. |

## Yerel geliştirme
```bash
cd pipeline && pip install -r requirements.txt && python -m pytest -q   # testler
python -m ozbet.run --date 2026-11-05                                    # günlük çalıştırma (internet gerekir)
python -m ozbet.backtest                                                 # backtest raporu
cd ../web && npm ci && npm run dev:sample                                # örnek veriyle arayüz
```

## Kaynak sağlığı ve veri kalitesi (Faz 1)
- Her çalıştırmada kaynak durumları `data/health.json`'a eklenir (son 42 çalıştırma ≈ 14 gün). Daha önce çalışan bir kaynak **üst üste 2 çalıştırma** veri getirmezse sitede kırmızı **alarm** çıkar (ana sayfa + Kaynaklar). Hiç çalışmamış kaynaklar "kronik" (bilinen engel) olarak ayrı gösterilir.
- Geçici hatalar (bağlantı kopması, zaman aşımı, 5xx) aynı çalıştırmada 20 sn sonra bir kez daha denenir; engeller (403, robots.txt) yeniden denenmez.
- **Doğrulama:** aralık dışı oranlar (1,01–100), marjı tutarsız market grupları, eksik MS oranları, bozuk/çelişen skorlar, tekrar eden maçlar ayıklanır; sayıları Kaynaklar sayfasında görünür.
- **Kalite raporu:** Nesine↔iddaa maç eşleşme oranı, geçmiş veride bulunamayan takımlar (sözlüğe eklenecek adaylar), tanınmayan lig adları, oran/model kapsamı.


### Şut tabanlı güç (Faz 2, 6 Kasım 2026)
İsabetli şut (football-data.co.uk HST/AST) üretme/yeme güçleri gol modeliyle aynı yöntemle bulunur, ligin gol/isabetli şut oranıyla beklenen gole çevrilir ve %40 ağırlıkla gol modeline katılır. Backtest (6 lig, 3.985 maç): log-loss 0,9885 → 0,9851, Brier 0,5895 → 0,5871, 2.5 Ü/A Brier 0,2459 → 0,2437; altı ligin hepsinde iyileşme. Piyasa kapanış oranı (Brier 0,5732) hâlâ daha iyi; fark kapandı ama yenilmedi.
