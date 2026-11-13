# Kadro / haber etkisi — denetim ve düzeltme (ajan 6)

Kapsam: `agents/squad.py`, `sources/news_rss.py`, `sources/transfermarkt.py`. Veri: `data/2026-11-05 … 11-15.json`
(11 gün dosyası, 2.120 maç satırı, 190'ı bitmiş). Ağ erişimi yok; RSS/Transfermarkt canlı denenmedi.

## 1. Denetim bulguları (sayılarla)

| Ölçü | Değer |
|---|---|
| `squad` dolu maç | 2 / 2.120 (%0,09) — ikisi de yalnız `coach_change` |
| `adjustment ≠ 0` olan taraf | **0** |
| Eksik oyuncu listesi (`missing`) dolu maç | **0** (Flashscore kullanım şartları nedeniyle kapalı; Transfermarkt her çalıştırmada 0 satır) |
| Rotasyon riski işaretli maç | 0 |
| Haber (`news`) iliştirilen maç | 45 / 2.120 (186 başlık) |
| Kadro etiketi (sakat/ceza/td) taşıyan başlık | 15 / 186 |
| …bunlardan yanlış takıma yazılmış | **6 / 15 (%40)** |
| …bunlardan maç başladıktan sonra yayımlanmış | 4 / 15 |

**Düzeltilmiş maçlar daha iyi mi tahmin edildi? Ölçülemiyor: n = 0.** Depodaki hiçbir maçta λ kadro yüzünden
değişmedi; karnedeki 138 tercihin hiçbiri kadro düzeltmesi görmedi. TD değişikliği bayraklı bitmiş maç n = 2
(1 tercih tuttu, 1 tutmadı) — hiçbir şey söylemez. Yani kadro ajanı bugüne kadar modele **hiç bilgi vermedi**;
gollerdeki aşırı iyimserliğin kaynağı burası değil.

Kod denetimi (eski hâl):
- **Büyüklük gerçek dışıydı.** Kilit oyuncu başına −%6 (3'e kadar → −%17), diğer eksik başına −%1,5 (4'e kadar),
  rotasyon −%3; toplam **−%24**, rakibe **+%7**. Veri gelseydi tek maçta λ dörtte bir düşecekti.
- **"Kilit" tanımı yanlıştı.** Transfermarkt'ta "takımın sakatları içinde en değerli 4, ≥1 mn €": beş büyük ligde
  hemen her sakat kilit çıkar; kadrodaki yerine, mevkiye bakılmıyordu. Flashscore'da hiç kilit yoktu.
- **Eskilik yoktu.** Sezonluk sakat ile dün sakatlanan aynı ağırlıktaydı; uzun süreli yokluk son sonuçlarda
  (Dixon-Coles) ve oranda zaten var → çifte sayım.
- **Yön:** kendi λ ↓ ve rakip λ ↑ birlikte uygulanıyordu (tek yön değil) — korundu, küçültüldü.
- **`adjustment` alanını simülasyon okumuyordu;** `simulation._squad_mult` aynı listeyi kendisi yeniden
  hesaplıyordu (alan yalnız web'de gösteriliyordu).
- **Kaynaklar arası:** `run.py` "ilk kaynak kazanır" kullanıyor (çifte sayım yok, birleşim de yok); aynı
  listede iki yazımla geçen oyuncu iki kez sayılırdı.
- **Yanlış takım:** başlıkta geçen her takıma aynı etiket yazılıyordu. Örnekler (canlı veri):
  "Çorum FK'da sakatlık depremi" → Fenerbahçe'ye de `sakat`; "injury-hit Hearts" → Celtic'e; "Beşiktaş -
  Gençlerbirliği maçında kırmızı kart" → Gençlerbirliği'ne `ceza`; başka takımın hocasının "Freiburg maçı öncesi
  sakatlık açıklaması" → Freiburg'a.
- **Kaçan gerçek haberler:** "Osimhen ameliyat edildi", "bıçak altına yatan", "6-8 hafta yok", "kadrosunda yok"
  hiçbir etiket almıyordu.
- **72 saat penceresi** gösterim için makul; ama taze (≤24 sa) ile bayat ayrımı ve maç-sonrası haber ayrımı yoktu.

## 2. Ne değişti

**λ düzeltmesi (`squad.impact`, `squad.multipliers`)**

| Durum | Kendi λ | Rakip λ |
|---|---|---|
| Kilit saha oyuncusu eksik | −%3 | +%1,5 |
| Diğer eksik | −%0,75 | +%0,375 |
| Şüpheli | yarım ağırlık | |
| Rotasyon riski | −%1,5 | +%0,75 |
| TD değişikliği, haber başlığı | 0 | 0 |
| **Sert tavan (hepsi dahil)** | **−%6** | **+%3** |

Eskilik çarpanı: ≤7 gün ×1,0 · 8–21 gün ×0,6 · >21 gün ×0,25 · tarih bilinmiyor ×0,5.
Büyüklükler ölçülmüş değil, **temkinli varsayımdır**: tek bir oyuncunun takım gol beklentisine katkısının yüzde
birkaç mertebesinde olduğu genel kabulüne ve "emin olmadığın bilgiyle modeli az oynat" ilkesine dayanır; depoda
bunu sınayacak veri yok (n = 0).

- `adjustment` anlamı/işareti/tipi aynı (kendi λ oransal değişim, ≤ 0); yeni `opp_adjustment` (≥ 0) eklendi.
- Oyuncu satırına veri varsa `since` (ISO tarih) ve `days_out` eklenir; `name/reason/key` aynen duruyor.
- Aynı oyuncu tek kez sayılır (`same_player`: "V. Osimhen" = "Victor Osimhen"); `merge_team_news` iki kaynağı
  çifte sayımsız birleştirir (run.py henüz çağırmıyor).
- **Simülasyon bağı:** `simulation.py` bu ajanın kapsamı dışında olduğu için `squad.py` içe aktarılırken
  `simulation._squad_mult = squad.multipliers` atanır. Kalıcı çözüm simulation.py'de tek satırlık doğrudan çağrı.

**Transfermarkt:** kilit = kaleci değil + değer ligin sakat listesinde üst çeyrek (en az 1 mn €) + takım başına
en çok 2. Satırdaki tarihlerden `since`/`until` okunur. Sayfa burada denenemedi; tarih sütunu bulunamazsa
"tarih bilinmiyor ×0,5" devreye girer.

**Haber eşleme (`news_rss.team_tags`):** sakat/ceza/td/kadro etiketleri yalnız haberin **öznesi** olan takıma
yazılır. "X maçı öncesi / X karşısında / X zaferi sonrası / ex-X / A v B" bağlam sayılır; iki özne varsa
bulunma eki ("X'da") ya da anahtar kelimeye ≤4 kelime uzaklıktaki tek takım; belirsizse **hiç kimseye**.
Depodaki 6 yanlış etiketin 6'sı kalktı, kaçan 2 gerçek haber ("ameliyat", "bıçak altına") yakalandı.
TD sinyali de artık yalnız özne takıma gider. Aynı haberin kopya başlıkları (A Spor/Fotomaç) tek sayılır.

**`squad.signal` (yeni):**
```jsonc
"signal": {"strength": "yok|zayıf|orta|güçlü", "fresh": true, "side": "home|away|null",
           "text": "Çorum FK: son 24 saatte 2 sakatlık haberi (2 bağımsız kaynak) — taze haber, oranlara henüz yansımamış olabilir."}
```
- güçlü: son 24 saatte ≥2 **bağımsız** kaynaktan kadro haberi, ya da 0–1 günlük kilit eksik.
- orta: tek kaynaklı taze haber, ≤21 günlük/tarihsiz kilit eksik, TD değişikliği.
- zayıf: 24–72 saatlik haber, uzun süreli/kilit olmayan eksik, yalnız rotasyon riski.
- `fresh`: haber ya da yokluk ilk kez son 24 saatte görüldü (maç başladıysa başlama saatine göre).
- Maç başladıktan sonra yayımlanan haber sayılmaz. A Spor + Fotomaç aynı grup → tek kaynak.
- `squad` null ise sinyal "yok" demektir. Yalnız başlık sinyali varsa `squad = {home:null, away:null,
  source:"haber_rss", signal:{…}}` döner (web'in "Eksik oyuncular" bölümü bu durumda zaten gizli).

Depo verisinde yeniden oynatma (2.120 satır): yok 2.116 · orta 2 · güçlü 2 · taze 3. Güçlü ikisi:
Galatasaray (Osimhen ameliyatı, 3 kaynak) ve Çorum FK (sakatlık, 2 kaynak).

## 3. Sınırlar

- **Kanıt yok.** Hem eski hem yeni büyüklükler sınanmadı; sinyal n = 4. Bu değişiklik isabeti artırdığını
  göstermez, yalnız veri geldiğinde modelin aşırı tepki vermesini önler ve okura bakılacak yeri gösterir.
- Başlıktan oyuncu adı, mevki ya da "oynayacak/oynamayacak" yönü çıkarılmaz ("sakatlık açıklaması" iyi haber de
  olabilir). Bu yüzden başlıklar λ'yı değiştirmez; sinyal bir **uyarıdır, tahmin değildir**.
- Eksik listesi kaynağı fiilen yok (Flashscore kapalı, Transfermarkt 0 satır). Kaynak gelene kadar λ düzeltmesi
  yalnız rotasyon riskinden gelir; o da depoda hiç tetiklenmedi.
- Kök eşleşmesi kaba: "ameliyathane" de `sakat` alır; iki özneli başlıklarda etiket düşebilir (isabet > kapsama).
- "İlk görülme" çalıştırmalar arası saklanmıyor; tazelik yayın saatinden/sakatlık tarihinden ölçülür.
- Cezalı listesi için Transfermarkt'ın ayrı sayfası çekilmiyor (doğrulanamadı, eklenmedi).
- Oranlar kadro haberini çoğu zaman modelden önce fiyatlar; `fresh` yalnız "henüz yansımamış **olabilir**" der.
