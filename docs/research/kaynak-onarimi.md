# Kaynak onarımı – teşhis ve sonuç (13 Kasım 2026)

Kanıt: `data/health.json` (6–13 Kasım, 40 çalıştırma), `data/status.json` notları ve iş akışının `teshis` dalına
yazdığı sayfa yapı dökümleri (13 Kasım 13:40 UTC). Hiçbir sitede robots.txt, kullanım şartı, Cloudflare/WAF
doğrulaması veya giriş duvarı aşılmadı; engelleyen kaynak ya kapatıldı ya da gerekçesiyle "eksik" bırakıldı.

## Kaynak kaynak

| Kaynak | Belirti | Neden (kanıt) | Yapılan | Sahibin yapacağı |
|---|---|---|---|---|
| **Understat** (xG) | 40/40 "missing", not: `understat bakımda` | Site bakımda: her iki adres de HTTP 200 ile 26 KB'lık "We will come back soon" sayfası döndürüyor (13 Kasım'da elle de doğrulandı). Ek hata: bu sayfa önbelleğe yazılıyordu (geçmiş sezonlarda **30 gün**); site dönse bile kaynak haftalarca "bakımda" görünecekti. | İçerik denetimi: bakım sayfası önbelleğe girmez, eski bozuk kopya atılır. İstek başarısız olursa ≤14 günlük son iyi kopya kullanılır ve "bayat" diye işaretlenir. Site kapalıyken tek istekte bırakılır. JSON ve eski HTML ayrıştırıcıları ayrıldı ve test edildi. | Yok. Site dönünce kendiliğinden düzelir. Şu an önbellekte iyi kopya olmadığı için xG **gelmiyor**; model şut tabanlı vekile düşüyor. |
| **ClubElo** (Elo) | 40/40 "missing", not: `502 Bad Gateway` | Sunucu tarafı arıza: `http://api.clubelo.com/{tarih}` boş gövdeyle 502 veriyor. Adres ve düz http doğru. İleri tarihli çalıştırmalar gelecek tarihi (ör. 15 Kasım) ayrıca istiyordu. | Üstel geri çekilmeli yeniden deneme; gelecek tarih yerine bugünün tablosu (tek istek); sunucu yanıt vermezse ≤7 günlük önbellek tablosu kullanılır, maç kartındaki `elo.date` gerçek tablo tarihini gösterir. | Yok. Sunucu dönünce düzelir; o güne kadar kupa/çapraz lig maçları eski lig-gücü yoluyla hesaplanır. |
| **Forebet** | 40/40 "missing", HTTP 403 | Cloudflare "managed challenge". Depodaki araştırma zaten "veri çekilmeyecek" diyor. | **Kapatıldı** (`registry.DISABLED`). Konsensüse girmez, sağlıkta "kapalı" sayılır, alarm/hata üretmez. Açma anahtarı yok. | Yok. |
| **SoccerStats** (eğilim + 1. Lig geçmişi) | `soccerstats_tr2` 40/40 "missing"; `soccerstats` "missing" → "partial" | Cloudflare güvenlik duvarı: HTTP 403 "Sorry, you have been blocked" (trends.asp ve results.asp). GitHub Actions istemcisi engelli. | **Varsayılan olarak kapatıldı**; 1. Lig geçmişi TFF'den geliyor (yalnız güncel sezon). Engel görülünce diğer sezonlar artık denenmiyor. | İsteğe bağlı: engellenmeyen bir ağdan (ev bilgisayarı) çalıştırılacaksa `OZBET_ENABLE_SOURCES=soccerstats`. Actions'ta açmayın. |
| **SportyTrader** | 39 çalıştırma "ok", son çalıştırmada "missing: maç linki bulunamadı" | Not yanıltıcıydı: liste sayfaları HTTP 403 + Cloudflare "Just a moment..." döndürdü; adapter engeli yutup "yapı değişti" diyordu. | Engel artık `Blocked: ... bot doğrulaması` olarak görünür; yapı değişikliği ayrı mesajla raporlanır. Doğrulama aşılmaz. Engel 3 çalıştırma sürerse alan adı 6→72 saat dinlendirilir, kalkınca kendiliğinden döner. | Yok. Engel kalıcı olursa (1 hafta) kapatılması önerilir. |
| **FreeSuperTips** | "ok" | — | Engel durumunda kalan sayfalar istenmez; hata mesajı netleştirildi. | Yok. |
| **Flashscore** | "skipped" | Arıza değil: kullanım şartları (md. 2.9-2.10) nedeniyle bilinçli kapalı. | Değişmedi; sağlıkta hata sayılmıyor. | Yok. |
| **API-Football** | "partial: veri dönmedi" | Anahtar tanımlı değil (beklenen). Not yanıltıcıydı. | Anahtar yoksa gerekçeli "kapalı" görünür. | İsteğe bağlı: GitHub → Settings → Secrets and variables → Actions → **`API_FOOTBALL_KEY`** secret'ı. 1. Lig için çok sezonlu geçmiş sağlar. |
| **Transfermarkt** | "partial: veri dönmedi" | Sayfa HTTP **202 + boş gövde** döndürüyor (bot doğrulaması bekleyen WAF). Adapter bu ajanın kapsamında değil. | `http.py` bu yanıtı artık engel sayar: durum "missing: HTTP 202 boş gövde: bot doğrulaması" olur (gerekçe görünür). Aşılmaz. | Karar: kadro bilgisi Actions'tan gelmeyecekse kaynağın kapatılması (transfermarkt.py sahibi ajan). |

## Ortak iyileştirmeler
- **`http.py`**: geçici hatalarda (bağlantı, zaman aşımı, 5xx) 2-4-8 sn geri çekilme + `Retry-After`; 404 gibi kalıcı
  hatalar ve engeller yeniden denenmez. `validate=` içerik denetimi, `stale=` bayat kopya izni, `cached()` ağsız okuma.
  Engel hafızası `.cache/http/_engeller.json` (Actions önbelleğiyle taşınır).
- **`health.py`**: `status.json → health.inputs` ve `health.json → runs[].inputs`:
  `xg`, `elo`, `squad`, `news` (bool), `consensus_sources` / `consensus_total`, `missing` (gerekçeli liste),
  `stale` (alan adı → saat), `degraded`. Eski anahtarlar aynen duruyor. Kapalı kaynakların `streak`i 0'dır.
- **Henüz bağlanmadı** (`run.py` bu ajanın kapsamı dışında): maç kartlarına "xG yok / Elo yok" etiketi basmak için
  `health.inputs` özetinin gün dosyasına da yazılması ve web'de gösterilmesi gerekir.

## Buradan doğrulanamayanlar
- Understat JSON ucunun (`/getLeagueData/{lig}/{sezon}`) bugünkü alan adları: site bakımda olduğu için canlı
  görülemedi; ayrıştırıcı `dates`/`datesData` ikisini de kabul eder, eski HTML yolu yedekte.
- ClubElo sunucusunun ne zaman döneceği ve gelecek tarihe ne yanıt verdiği.
- SoccerStats ve SportyTrader robots.txt / kullanım şartlarının güncel metni (bu oturumda açılamadı).
  SportyTrader fikstürleri (tests/fixtures) adapter belgesindeki yapıya göre sentetiktir, canlı sayfayla karşılaştırılmadı.
