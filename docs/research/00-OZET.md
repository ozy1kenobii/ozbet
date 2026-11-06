# Faz 3 – Benzer siteler araştırması: özet ve öncelik listesi (6 Kasım 2026)

Ayrıntılar: [01 örnek siteler](01-ornek-siteler.md) · [02 Türk siteleri](02-turk-siteler.md) ·
[03 uluslararası tahmin](03-uluslararasi-tahmin.md) · [04 istatistik platformları](04-istatistik-platformlari.md) ·
[05 oran analizi](05-oran-analizi.md)

## Ana bulgular
1. ~40 site incelendi. **Hiçbiri doğrulanabilir başarı ölçümü (Brier, kalibrasyon, ROI) yayımlamıyor**; "%71 başarı" gibi kaynaksız iddialar yaygın. OZBET'in karnesi ve backtest'i en net fark.
2. Türkiye'ye özgü en güçlü niş: **benzer oran arşivi** (5 site ücretli). Yöntem: yakın oranlı geçmiş maçların sonuç dağılımı. Doğru kurulum: marjı temizlenmiş olasılıkta en yakın k maç, Wilson güven aralığı, örneklem uyarısı. Yeni bilgi değil, piyasanın o bölgedeki yanlılığını gösterir (favori-sürpriz yanlılığı).
3. Tahmin gücü sırası (literatür): marjsız kapanış oranı > isabetli şut/şut/korner > xG/Elo > form, H2H, topla oynama, oy, hava (büyük ölçüde süs).
4. Büyük modeller (Opta Supercomputer) piyasa oranını girdi olarak kullanıyor → OZBET'in %75 piyasa harmanını destekliyor. FiveThirtyEight SPI yöntemi ve 2016-23 arşivi açık.
5. Yeni özelliklerin verisinin çoğu **elimizde**: football-data.co.uk açılış/kapanış oranları (Pinnacle dahil), şut, korner, kart, hakem kolonları.

## Veri çekilmeyecek kaynaklar (şartlar/robots karşı)
iddaaorananalizi.com, Mackolik, Sahadan, FotMob, OddsPortal, Sports Reference/FBref, Forebet (Cloudflare), SofaScore. Lisanssız bahis şirketine yönlendiren öğeler hiçbir şekilde alınmaz.
**Kontrol edilecek:** Flashscore robots.txt maç sayfalarını kapatıyor; adapter ayrı veri sunucusunu robots kontrolüyle kullanıyor — kullanım şartları incelenip gerekirse yedeğe çekilecek.

## Öncelik listesi
| # | Özellik | Veri kaynağı | Emek |
|---|---|---|---|
| 1 | Benzer oranlı geçmiş maçlar kutusu (1X2, Ü/A 2.5, KG) — Shin marj temizleme, k-komşu, Wilson aralığı | football-data.co.uk (12k+ maç, PS/PSC) | M |
| 2 | Trend/seri kartları ("son 6 iç saha maçının 5'i Üst") | Mevcut geçmiş veri | S |
| 3 | Puan durumu, H2H ve form şeridi iyileştirmesi | Mevcut geçmiş veri | S |
| 4 | Korner ve kart beklentisi + hakem kart eğilimi | football-data (HC/AC, HY/AY, Referee) | M |
| 5 | Şut tabanlı güç (xG vekili) modele | football-data (HS/AS, HST/AST) | M |
| 6 | Oran hareketi: marjsız olasılıkta ölçüm, CLV raporu, sahte ikinci alarmların ayıklanması | data/odds arşivi + PSC | S-M |
| 7 | Lig bazında beraberlik kalibrasyonu, sezon başı ortalamaya geri çekilme | Mevcut | S-M |
| 8 | SPI arşiviyle benchmark (Karne'de "OZBET vs 538 vs piyasa") | FiveThirtyEight açık veri (lisans teyidi) | S |
| 9 | ClubElo konsensüs oyu + Avrupa maçları (zaten kodda, sunucu düzelince) | api.clubelo.com | S |
| 10 | Faktör aç/kapa simülasyonu (SporDB fikri: iç saha, eksikler, form) | Mevcut model | M |
| 11 | Market sözlüğü ve sorumlu oyun sayfası | — | S |
