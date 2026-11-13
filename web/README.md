# OZBET web

Vite + React 18 + TypeScript + Tailwind CSS 3 ile yapılmış, mobil öncelikli PWA. Sunucu yok; site yalnızca `data/*.json` dosyalarını okur. Veri şeması: `../docs/ARCHITECTURE.md`.

## Komutlar

| Komut | Ne yapar |
|---|---|
| `npm install` | Bağımlılıkları kurar |
| `npm run dev` | Geliştirme sunucusu; repo kökündeki `../data` klasörünü `/data` altında servis eder |
| `npm run dev:sample` | Aynısı, ama **örnek veri** (`web/sample-data/`) ile (`OZBET_DATA_DIR=sample-data`) |
| `npm run build` | `tsc --noEmit` + üretim derlemesi → `dist/` (veri kopyalanmaz) |
| `npm run preview` | `dist/` önizlemesi. Örnek veriyle: `OZBET_DATA_DIR=sample-data npm run preview` |
| `npm run icons` | `scripts/make-icons.mjs`: SVG'den PNG ikonlar + `public/favicon.svg` (@resvg/resvg-js) |
| `npm run sample-data` | `sample-data/` klasörünü yeniden üretir |
| `npm run screenshots` | Playwright ile ekran görüntüleri (önizleme sunucusu 4179'da açık olmalı; Chrome yolu argüman ya da `CHROME_PATH` ile verilebilir) |
| `node scripts/screenshots-v2.mjs` | Gerçek veriyle `screenshots/v2-*.png` (önizleme 4182’de, `dist/data` kopyalanmış olmalı) |
| `npm run typecheck` | Yalnızca tip kontrolü |

## Veri yolu sözleşmesi

Tüm yollar sayfaya göre görelidir (`vite.config` → `base: './'`, yönlendirme `HashRouter`), bu yüzden GitHub Pages alt yolunda da çalışır.

| Yol | İçerik |
|---|---|
| `data/index.json` | `{"dates": [...], "latest": "YYYY-MM-DD"}`: tarih seçici |
| `data/latest.json` | Son gün dosyası (ana sayfa varsayılanı) |
| `data/YYYY-MM-DD.json` | Gün dosyası (`/#/gun/YYYY-MM-DD`, `/#/mac/YYYY-MM-DD/:id`) |
| `data/scorecard.json` | Karne |
| `data/status.json` | Kaynak durumları: `{generated_at, sources: Source[]}` ya da doğrudan `Source[]` |
| `data/backtest.json` | Backtest raporu (`generated_at, seasons, leagues, summary, by_league[]`) |

Bir dosya yoksa, 404 dönüyorsa ya da bozuksa ilgili bölüm "Henüz veri yok" gösterir; uygulama çökmez. Opsiyonel alanlar (`odds`, `model`, `squad`, `market`, `consensus`, `pick`, `result`) `null` olabilir.

## Çevrimdışı / PWA

- `vite-plugin-pwa` (generateSW): uygulama kabuğu precache edilir.
- `data/*.json` için **NetworkFirst** runtime önbelleği (`ozbet-data`): ağ yoksa son başarılı yanıt gösterilir, üstte "Çevrimdışı – son kaydedilen veri" bandı çıkar.
- Service worker yalnızca üretim derlemesinde kaydedilir.

## Deploy notu

Derlemeye veri **kopyalanmaz**. CI, deploy sırasında şunu yapmalıdır:

```bash
cd web && npm ci && npm run build
cp -r ../data dist/data       # data/ → web/dist/data/
# ardından web/dist/ GitHub Pages'e yüklenir
```

## Örnek veri

`web/sample-data/` içindeki dosyalar **örnek veridir**: takım adları gerçek, tüm sayılar, oyuncu adları ve yorumlar uydurmadır. Yalnızca `npm run dev:sample` ve ekran görüntüleri içindir; deploy edilmez ve gerçek sitede gösterilmez.

## Yapı

```
src/
  lib/types.ts      Şema tipleri (ARCHITECTURE.md ile birebir alan adları)
  lib/markets.ts    Market anahtarları → Türkçe etiketler, skor→market kuralları
  lib/data.ts       JSON yükleme (404 → boş durum), çevrimiçi durumu
  lib/coupon.tsx    Kupon durumu (localStorage) + birleşik olasılık / EV / korelasyon
  lib/pick.ts       Seçim yardımcıları: oran bandı (1,60–3,50), beklenen değer, adil oran, EV sıralaması, en düşük oran ayarı
  lib/format.ts     Europe/Istanbul saatleri, % ve oran biçimleri (tr-TR)
  components/       MatchCard, PickBits (Model/adil oran/beklenen değer üçlüsü, Keskin piyasa rozeti, Pas), AddToCoupon, SVG grafikler (çubuk, ısı haritası, çizgi, kalibrasyon)
  pages/            Home, MatchDetail, Coupon, Scorecard, Sources (her biri lazy chunk)
```

Kupon notu: aynı maçtan birden fazla seçim varsa birleşik olasılık, maçın `score_matrix` verisinden tam hesaplanır (0–5 gol; 5+ kuyruğu dahil değildir, arayüzde not olarak gösterilir). Matris yoksa çarpım kullanılır ve uyarı verilir.

## Seçim görünümü

Ana sayfa varsayılanı **Günün seçimleri**: oranı seçili alt sınır (varsayılan 1,60; `localStorage: ozbet-min-oran`) ile 3,50 arasında olan tercihler, beklenen değere (`pick.ev`, yoksa `p·oran − 1`) göre sıralanır. Düşük oranlı tercihler gizlenir ve sayısı altta yazılır; “Tüm maçlar” eski lig lig görünümdür (`ozbet-gorunum`). Yeni alanların hepsi (`pick.ev/fair_odds/kind/blended`, `pick_note`, `sharp`, `squad.signal`, `scorecard.clv/by_odds_band/overall.roi_ci`, `recent[].clv/ev`) opsiyoneldir; eski gün dosyaları bozulmaz.
