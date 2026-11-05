# Haber kaynakları (RSS/Atom)

Haber Toplama Ajanı (`pipeline/ozbet/sources/news_rss.py`) yalnızca yayıncıların **herkese açık RSS/Atom
akışlarını** okur. LLM kullanılmaz, HTML sayfası kazınmaz. Kontrol tarihi: **5 Kasım 2026**.

Kurallar:
- `PoliteClient` her istekten önce robots.txt'yi kontrol eder, alan adı başına gecikme uygular, akışlar **2 saat**
  önbellekte tutulur (günde 3 çalıştırma → akış başına günde en fazla 3 istek).
- JSON'a yalnızca **başlık, bağlantı, kaynak adı, yayın zamanı ve etiketler** yazılır. Özet (`description`/`summary`)
  sadece bellekte, takım eşleme ve etiketleme için kullanılır; haber metni kopyalanmaz.
- Bir akış hata verirse atlanır; hepsi hata verirse `status.json`'da `news_rss` → `missing`, akış devam eder.

## Doğrulama yöntemi
WebFetch ile her URL'nin gerçekten `<rss>` veya Atom `<feed>` döndürdüğü, öğe sayısı ve en yeni öğenin tarihi
kontrol edildi; ardından alan adının `robots.txt` dosyası okundu. "Kesik" notu, araç çıktısının uzun akışı
kısaltmasıdır; ayrıştırıcı yarıda kalmış akışı son tam öğeye kadar kurtarır.

## Kullanılan genel akışlar (`FEEDS`)

| Kaynak | URL | Dil | Kapsam | robots.txt (`User-agent: *`) | Doğrulama |
|---|---|---|---|---|---|
| A Spor – Futbol | https://www.aspor.com.tr/rss/futbol.xml | tr | Türk + Avrupa futbolu | `/rss` engelli değil | ✅ RSS 2.0, 44 öğe, en yeni 05.11.2026 |
| A Spor – Süper Lig | https://www.aspor.com.tr/rss/spor-toto-super-lig.xml | tr | Süper Lig | engelli değil | ✅ RSS 2.0, en yeni 05.11.2026, özet var |
| Fotomaç – Süper Lig | https://www.fotomac.com.tr/rss/superlig.xml | tr | Süper Lig | engelli değil | ✅ RSS 2.0, 41 öğe, en yeni 05.11.2026 |
| NTV Spor – Futbol | https://www.ntvspor.net/rss/kategori/futbol | tr | Türk futbolu | yalnız `/arama/` engelli | ✅ **Atom**, 20 kayıt, en yeni 05.11.2026 |
| NTV Spor – Dünyadan Futbol | https://www.ntvspor.net/rss/kategori/dunyadan-futbol | tr | Avrupa futbolu | engelli değil | ✅ Atom, 20 kayıt, en yeni 05.11.2026 |
| TRT Haber – Spor | https://www.trthaber.com/spor_articles.rss | tr | Genel spor (çoğu futbol) | `Allow: /` | ✅ RSS 2.0, 49 öğe, en yeni 05.11.2026 |
| AA – Spor | https://www.aa.com.tr/tr/rss/default?cat=spor | tr | Genel spor | `Allow: /` (`/api/` hariç) | ✅ RSS 2.0, 30 öğe, en yeni 03.11.2026 |
| Habertürk – Spor | https://www.haberturk.com/rss/spor.xml | tr | Spor (30 öğenin 27'si futbol) | `/rss` engelli değil | ✅ RSS 2.0, 30 öğe, en yeni 05.11.2026 |
| ESPN – Soccer | https://www.espn.com/espn/rss/soccer/news | en | Dünya futbolu | `/espn/rss/` engelli değil | ✅ RSS 2.0, 21 öğe, en yeni 02.11.2026 |
| Sky Sports – Football | https://www.skysports.com/rss/11095 | en | İngiliz/Avrupa futbolu | `/rss/` engelli değil | ✅ RSS 2.0, 20 öğe, en yeni 04.11.2026 |
| BBC Sport – Football | https://feeds.bbci.co.uk/sport/football/rss.xml | en | İngiliz/Avrupa futbolu | — | ⚠️ Araştırma aracından erişilemedi (site engeli); URL feeder.co listesinden. **Canlıda doğrulanmalı.** |
| The Guardian – Football | https://www.theguardian.com/football/rss | en | İngiliz/Avrupa futbolu | — | ⚠️ Araştırma aracından erişilemedi; URL kalıbı (`/bölüm/rss`) feeder.co'dan. **Canlıda doğrulanmalı.** |

Notlar:
- Sky Sports `rss/12040` genel spor akışıdır (golf, F1 dahil); futbol için `rss/11095` seçildi.
- Habertürk ve TRT akışlarında basketbol vb. haberler de var; ayrıştırıcı "basketbol, Euroleague, voleybol, kadın,
  U19…" geçen haberleri futbol dışı sayıp eler (Galatasaray/Fenerbahçe basketbol takımları yanlış eşleşmesin).

## Takım akışları (`TEAM_FEEDS`, öncelikli lig maçları, en fazla 30 takım/çalıştırma)
Yayıncıların kendi RSS sayfalarında listelenen kulüp akışları. Takım akışından gelen haber o takıma yazılır.

- A Spor (`https://www.aspor.com.tr/rss/<kulüp>.xml`): galatasaray, fenerbahce, besiktas, trabzonspor, basaksehir,
  alanyaspor, amed-sportif-faaliyetler, rizespor, corum-fk, erzurumspor, eyupspor, gaziantep, genclerbirligi,
  goztepe, kasimpasa, konyaspor, kocaelispor, samsunspor. Liste: https://www.aspor.com.tr/rss-bilgi —
  `galatasaray.xml` doğrulandı (RSS 2.0, en yeni 05.11.2026); diğerleri aynı kalıp, canlıda doğrulanmalı.
- Fotomaç (`https://www.fotomac.com.tr/rss/<kulüp>.xml`): antalyaspor, kayserispor, karagumruk, sivasspor,
  ankaragucu. Liste: https://www.fotomac.com.tr/rss — `galatasaray.xml` doğrulandı (05.11.2026).

## Değerlendirilip kullanılmayanlar

| Kaynak | Sonuç |
|---|---|
| TRT Spor (trtspor.com.tr) | `/rss`, `/rss/futbol.xml` istemci hatası döndü; herkese açık RSS sayfası bulunamadı. Yerine **TRT Haber Spor** akışı (https://www.trthaber.com/sitene_ekle.html) kullanılıyor. |
| Fanatik | `/rss`, `/rss/futbol`, `/rss/anasayfa.xml` istemci hatası; robots.txt RSS'ten söz etmiyor, yayınlanmış akış bulunamadı. |
| Sporx | `/rss/`, `/rss/futbol.xml`, `/rss/sondakika.xml` istemci hatası; robots.txt yalnız sitemap listeliyor. Sitemap haber akışı değil → kullanılmadı. |
| Fotomaç `anasayfa.xml`, `futbol.xml`, `avrupadanfutbol.xml`, `son24saat.xml` | Akış dönüyor ama **güncellenmiyor** (en yeni öğeler Mayıs 2025 / Eylül–Ekim 2026). Bunun yerine güncel `superlig.xml` ve kulüp akışları. |
| A Spor `anasayfa.xml` | Çalışıyor ama futbol.xml ile büyük ölçüde örtüşüyor; istek sayısını düşürmek için alınmadı. |

## Google News RSS arama (`news.google.com/rss/search?q=...`) — KULLANILMIYOR
Karar: **kullanılmaz.** Gerekçe:
1. **robots.txt:** `news.google.com` robots kuralları bu yolu otomatik istemcilere kapatıyor: araştırma aracımızın
   hem `news.google.com/robots.txt` hem de örnek arama isteği (`/rss/search?q=Galatasaray...`) "robots_disallowed"
   ile reddedildi. `PoliteClient` robots kontrolü yaptığı için kod içinde de engellenirdi.
2. **Belgelenmiş/resmi API değil:** Google bu akışları artık tanıtmıyor; üçüncü taraf rehberler bile yalnız
   "kişisel, ticari olmayan kullanım" ve sık sorguda IP engeli uyarısı yapıyor
   (https://www.codewords.ai/blog/google-news-rss).
3. **Google Hizmet Şartları** (30 Temmuz 2026 sürümü) otomatik erişimde robots.txt gibi makine okunur talimatlara
   uyulmasını şart koşuyor (özet: https://conductatlas.com/platform/google/google-terms-of-service/prohibited-conduct-automated-access-and-ai-training-restrictions/).
4. Takım bazlı arama ihtiyacı yayıncıların **kulüp akışlarıyla** (A Spor, Fotomaç) karşılanıyor.

## Eşleme ve etiket kuralları (özet)
- Takım adı: `teams.normalize/canonical` + ALIASES yazımları, kelime sınırıyla. Uzun ifadeler önce eşleşip maskelenir
  ("Inter Miami", "Real Madrid", "Milan Cortina", "Manchester United" içindeki kısa ad eşleşmez).
- Belirsiz tek kelimeler (Roma, Inter, Milan, City, Paris, Porto, Iğdır…) yalnızca kulüp önekiyle ("AS Roma"),
  aynı metinde rakip takımla veya lig adıyla birlikte geçerse kabul edilir.
- Altyapı/kadın takımı maçları ve tanımlı lig dışındaki maçlar için haber eşlemesi yapılmaz.
- Etiketler (ASCII'ye çevrilmiş metinde kök eşleşmesi): `sakat`, `ceza`, `td` (rol kelimesi + değişim kelimesi
  birlikte, ya da "görevden alındı/sacked"), `kadro`, `transfer`. Kurallar `news_rss.TAG_RULES` içinde.
- Son 72 saat, takım başına en fazla 6 haber, başlığa göre tekilleştirme.
- `coach_change`: son 7 günde **başlığında** takım geçen `td` etiketli haber varsa. Oyuncu adı çıkarılmaz.
