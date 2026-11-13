# Keskin piyasa farkı (S1) — canlı hipotez kaydı

Kod: `pipeline/ozbet/agents/sharp_edge.py` · Test: `pipeline/tests/test_sharp_edge.py` · Önceki araştırma: `roi-piyasa.md` (S1 ve "Öneri").

## Sinyal nedir
Aynı maç için iki fiyat karşılaştırılır:

- **Gerçek iddaa oranı** (Nesine / iddaa.com bülteni; yedek kaynaktan doldurulan oranlar kıyasa girmez),
- **Keskin piyasanın adil olasılığı**: football-data.co.uk `fixtures.csv` bahisçi kolonlarından, marjı Shin yöntemiyle
  (`agents/market.shin`) temizlenmiş olasılık. Öncelik: Pinnacle (`PS*`) → Betfair borsası (`BFE*`) → piyasa ortalaması (`Avg*`).

`fark = iddaa_oranı × adil_olasılık − 1 − pay`. Pay: Pinnacle 0; Betfair ve Avg için 0,02 (borsa komisyonu, yalnız "back"
fiyatının görülmesi, Avg'nin keskin olmaması). Marketler: 1X2 ve 2.5 Alt/Üst.

Bir seçim ancak şu koşulların hepsi sağlanırsa öne çıkarılır (`sharp.best` + "Keskin piyasa farkı" bayrağı):
fark ≥ +0,01 (tampon), iddaa oranı ≥ 1,60 (düşük oranlı "garanti" maç kovalanmaz), maçtaki hiçbir fark > 0,15 değil.
0,15'i aşan fark fırsat sayılmaz; yanlış eşleşme ya da bayat oran işareti olarak nota yazılır.
Eşleşme güveni: iki takım adı da benzer, başlama saati ≤ 90 dk farklı, tek aday satır.

## Neden hipotez, kanıt değil
- Backtest bu sinyali **sınayamadı**: iddaa oranı Pinnacle'dan benzetildiği için `adil × iddaa > 1` tanım gereği imkânsızdı (n=0).
- iddaa marjı 1X2'de ~%20 düzeyinde ölçüldü; pozitif fark seyrek olmalı. Görülen bir pozitif farkın en olası açıklamaları
  gerçek fiyat hatası **değil**: (a) `fixtures.csv` oranları anlık değil, dosyanın son güncellemesine ait — arada sakatlık/kadro
  haberiyle çizgi kaymış olabilir; (b) Betfair/Avg yedeği Pinnacle kadar keskin değil; (c) takım/saat eşleşme hatası.
- Keskin piyasa da yanılır; adil olasılık bir tahmindir. Az sayıda maçta pozitif sonuç şansla da oluşur.
- Bu nedenle sitede "kazandırır" denmez; yalnız "iddaa fiyatı keskin piyasadan yüksek" bilgisi verilir. Kâr vaadi yoktur.

## Nasıl puanlanacak
Her çalıştırma, karşılaştırılan **tüm** marketlerin farkını (`sharp.edge`, negatifler dahil) gün dosyasına yazar. Sonuçlar
geldikçe (karne/arşiv) aşağıdakiler hesaplanacak:

| ölçü | tanım |
|---|---|
| n | `best` verilen ve sonuçlanan seçim sayısı |
| isabet | kazanan / n; beklenen isabetle (ortalama `fair_p`) karşılaştırılır |
| ROI | Σ(kazanırsa oran − 1, kaybederse −1) / n — düz 1 birim, **iddaa oranıyla** |
| %95 GA | ROI için bootstrap (maç bazında yeniden örnekleme) |
| kalibrasyon | fark dilimlerine göre (≤0, 0–0,01, 0,01–0,05, 0,05–0,15) gerçekleşen ROI; fark büyüdükçe ROI artıyor mu |
| kaynak kırılımı | pinnacle / betfair / avg ayrı ayrı |

Karar kuralı (önceden yazılıyor, sonuçlara göre değiştirilmeyecek): **n ≥ 300** olmadan yorum yok; ROI %95 GA alt sınırı > 0
olmadan "çalışıyor" denmez. Eşikler (0,01 / 1,60 / 0,15 / paylar) veri görülerek ayarlanırsa yeni dönemde yeniden sınanır.
Seçimlerin `best` anındaki oranı esas alınır (ilk görüldüğü çalıştırma); sonradan değişen oranla geriye dönük puanlama yapılmaz.

## Kapsam sınırları
- Yalnız `fixtures.csv`'de bulunan ligler (football-data.co.uk ana ligleri; çalıştırma başına ~20 maç). Süper Lig dosyada varsa
  kapsanır; 1. Lig, kupalar, Avrupa kupaları ve diğer ligler **kapsam dışı**.
- 2026-27 dosyalarında `PS*` kolonları olmayabilir → pratikte referans çoğunlukla Betfair, o da yoksa Avg.
- Referansın alındığı an bilinmiyor (CSV'de zaman damgası yok); `sharp.fetched_at` dosyanın indirildiği andır.
- Yalnız 1X2 ve 2.5 Alt/Üst. Asya handikapı kolonları ayrıştırılıyor (`books`) ama iddaa karşılığı olmadığı için kullanılmıyor.
- Günde beklenen `best` sayısı düşük (çoğu gün 0); n ≥ 300'e ulaşmak aylar sürebilir.
- Bu ortamda football-data.co.uk'a erişilemediği için ayrıştırıcı gerçek dosyayla değil, belgelenmiş kolon adları ve sentetik
  satırlarla sınandı; ilk canlı çalıştırmada durum sayfasındaki "Keskin piyasa farkı" satırı kontrol edilmeli.

## Veri şeması
```jsonc
"sharp": {
  "source": "pinnacle|betfair|avg",
  "fair": {"1":0.452,"X":0.268,"2":0.280,"O2.5":0.52,"U2.5":0.48},
  "edge": {"1":-0.12,"X":-0.14,"2":0.03,"O2.5":-0.11,"U2.5":-0.10},   // pay düşülmüş
  "best": {"market":"2","edge":0.03,"odds":3.70,"fair_p":0.280},        // ya da null
  "fetched_at": "...",
  "allowance": 0.02,        // yalnız > 0 ise
  "source_ou25": "avg",     // yalnız Alt/Üst referansı farklıysa
  "notes": ["..."]          // yalnız olağan dışı fark varsa
}
```
Veri ya da güvenli eşleşme yoksa `sharp` anahtarı hiç yazılmaz.
