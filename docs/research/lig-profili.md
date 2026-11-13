# Lig profili ve veri kademesi (A/B/C)

Kod: `pipeline/ozbet/league_profile.py` · Test: `pipeline/tests/test_league_profile.py`
Veri tarihi: 13 Kasım 2026 (karne: 5–9 Kasım, 138 puanlanmış tercih).

## Ne işe yarar
- `league_tier(lig)` → `"A" | "B" | "C"`: tahminin arkasında ne kadar veri olduğunu söyler. **Kârlılık etiketi değildir.**
- `tier_reason(lig)` → arayüz için kısa Türkçe açıklama (ör. `B kademe · Lig modeli var ama veri daha sığ: şut ve ilk yarı verisi yok`).
- `league_profile(lig)` → `{n, goals_avg, draw_rate, home_win_rate, away_win_rate, btts_rate, o25_rate, home_adv, updated}`; arşivde maç yoksa `None`.
- `draw_prior(lig)`, `goals_prior(lig)` → büzülmüş lig değeri; lig bilinmiyorsa havuz öncülü.
- Yardımcılar: `pooled_prior()`, `archive_matches(lig)`, `all_tiers()`, `clear_cache()`.

## Kademe kuralı (sırayla uygulanır)
| Sıra | Koşul | Kademe |
|---|---|---|
| 1 | Kimlik boş, metin değil ya da `OTHER` | C |
| 2 | `config`'te kupa (`cup=True`: UCL, UEL, UECL) | C |
| 3 | `config`'te football-data.co.uk ana lig dosyası var (`fd_code`: 3 sezon, İY skoru, şut) | A |
| 4 | Arşivde ≥ 300 maç (`TIER_A_MIN_MATCHES`) | A |
| 5 | `config`'te tanımlı diğer lig (`fd_extra` dosyası: şut/İY yok; ya da yalnız soccerstats, ör. TR2) | B |
| 6 | Arşivde ≥ 60 maç (`config.ARCHIVE_MIN_MATCHES`) | B |
| 7 | Geri kalan her şey (dosyalarda olmayan kimlik, kadın/altyapı, eşlenemeyen bülten ligi) | C |

Kupa, arşivi ne kadar büyük olursa olsun C kalır (takımlar farklı liglerden gelir; model Elo ya da lig gücü yedeğiyle çalışır).

## Büzme
`değer = (n·gözlem + K·öncül) / (n + K)`
- Oranlar ve iç saha gol farkı: **K = 200 maç**. Maç başı gol: **K = 60 maç**.
- Havuz öncülü = sabit taban (gol 2,70 · beraberlik 0,26 · ev 0,44 · deplasman 0,30 · KG 0,52 · 2.5Ü 0,52 · iç saha +0,30; yaklaşık
  Avrupa ortalamaları) + tüm arşiv; taban 500 maç ağırlığında. Bugünkü havuz (arşiv 97 maç): gol 2,77 · beraberlik 0,246 · iç saha +0,35.
- Üç sonuç oranı aynı K ile büzüldüğü için toplamı 1'dir.

## Ligler
| Kademe | Sayı | Ligler |
|---|---|---|
| A | 19 | TR1, ENG1, ESP1, ITA1, GER1, FRA1, ENG2, GER2, ITA2, ESP2, FRA2, NED1, POR1, BEL1, SCO1, GRE1, SCO2, ENG3, ENG4 |
| B | 17 | TR2, AUT1, DEN1, SUI1, POL1, ROU1, RUS1, NOR1, SWE1, FIN1, IRL1, USA1, BRA1, ARG1, MEX1, JPN1, CHN1 |
| C | 3 + tümü | UCL, UEL, UECL, `OTHER` ve tanımsız her kimlik |

Arşivdeki maç sayısı (n) ve büzülmüş profil — **n çok küçük, değerler fiilen havuz öncülüdür**:

| Lig | Kademe | n | Gol | Beraberlik | İç saha | Son maç |
|---|---|---|---|---|---|---|
| ITA1 | A | 12 | 2,92 | 0,237 | +0,35 | 2026-11-02 |
| BEL1 | A | 10 | 2,89 | 0,239 | +0,35 | 2026-11-04 |
| ESP1 | A | 10 | 2,80 | 0,235 | +0,36 | 2026-11-02 |
| ITA2 | A | 10 | 2,70 | 0,258 | +0,38 | 2026-11-01 |
| GER1 | A | 9 | 2,81 | 0,250 | +0,34 | 2026-11-01 |
| GER2 | A | 9 | 2,77 | 0,240 | +0,34 | 2026-11-01 |
| NED1 | A | 9 | 2,93 | 0,240 | +0,36 | 2026-11-01 |
| POR1 | A | 9 | 2,68 | 0,240 | +0,37 | 2026-11-02 |
| TR1 | A | 9 | 2,91 | 0,245 | +0,37 | 2026-11-02 |
| GRE1 | A | 7 | 2,76 | 0,243 | +0,37 | 2026-11-02 |
| SCO1 | A | 3 | 2,75 | 0,248 | +0,36 | 2026-11-01 |

Diğer 28 ligin arşivi yok (n = 0): `league_profile` → `None`, öncüller havuz değeri.

## Kanıt: kademeler kaliteyi ayırıyor mu?
Kaynak: `data/history/*.json` (karnenin ham satırları; toplamlar `scorecard.json` ile birebir: n=138, isabet %63,8, ort. p %64,2, ROI −%15,3).
1X2 Brier/log-loss: model `p1x2` ile aynı satırdaki marjı temizlenmiş iddaa olasılığı (`q`, toplamı 1'e ölçeklenmiş).

| Kademe | Tercih n | İsabet (±1 SH) | Ort. p | Ort. oran | ROI | Model Brier / LL | Piyasa Brier / LL |
|---|---|---|---|---|---|---|---|
| A | 127 | %64,6 (±4,2) | %64,3 | 1,36 | −%14,3 | 0,581 / 0,975 | 0,558 / 0,940 |
| B | 4 | %50,0 (±25) | %59,1 | 1,48 | −%25,5 | 0,703 / 1,123 | 0,620 / 1,022 |
| C | 7 | %57,1 (±19) | %65,2 | 1,28 | −%27,3 | 0,642 / 1,068 | 0,745 / 1,218 |
| Toplam | 138 | %63,8 (±4,1) | %64,2 | 1,36 | −%15,3 | 0,587 / 0,984 | 0,570 / 0,957 |

**Sonuç: ayırmıyor — daha doğrusu ölçülemiyor.** B (n=4) ve C (n=7) için isabetin standart hatası 19–25 puan; A ile fark
yönü beklendiği gibi ama gürültüden ayırt edilemez. Karnenin 44 `by_league` satırının 24'ü `OTHER` ve hepsinde n=0;
tercih alan 20 ligin 17'si A, 1'i B (TR2), 2'si C (UEL, UECL).

Ek gözlemler:
- **Backtest** (`data/backtest.json`, 2 sezon, 3 985 maç): yalnız 6 lig var ve hepsi A. Model Brier 0,5895 / LL 0,9885, kapanış
  piyasası 0,5727 / 0,9639. Yani en iyi verili kademede bile model piyasanın gerisinde; B ve C için backtest yok.
- **Gün dosyaları** (5–15 Kasım, 2 120 maç): model yöntemi kademeyle örtüşüyor — A: 138 lig modeli, 40 yalnız piyasa, 7 modelsiz;
  B: 40 lig modeli, 28 yalnız piyasa, 2 modelsiz; C: 34 lig gücü yedeği, 1 416 yalnız piyasa, 415 modelsiz. Tercih yalnız lig
  modeli (A 138, B 40) ya da lig gücü yedeği (C 34) olan maçlara verilmiş. Bu, kademenin veri derinliğini doğru etiketlediğini
  gösterir; isabeti öngördüğünü göstermez.
- A içinde 6 büyük lig (n=55, isabet %72,7 ±6,0) ile diğer 11 A ligi (n=72, %58,3 ±5,8) arasında fark görünüyor, ama fark
  ~1,7 standart hata, 5 günlük tek örneklem ve sonradan bakılmış bir bölme. Buna dayanarak lig filtresi **önerilmez**.

## Uyarılar
- 138 tercih, 5 gün. Kademe başına anlamlı bir isabet farkı (ör. 5 puan) görmek için kademe başına kabaca 350+ tercih gerekir.
- Örneklemde seçilen lig filtreleri daha önce örneklem dışında tutmadı (`roi-secim.md`, `roi-model.md`); burada da
  "kârlı lig" listesi çıkarılmadı. Kademe yalnız veri yeterliliğine dayanır, sonuçlara bakılarak ayarlanmadı.
- Tüm kademelerde ROI negatif; iddaa marjı (~%20) kademe farkından büyük. Kademe A bir kazanç vaadi değildir.
- Lig profilleri bugün ~10 maça dayanıyor, yani ligler arası yapısal fark (beraberlik, gol) henüz veride yok. Arşivi besleyen
  flashscore sonuç akışı kapalı (`sources/registry.py`); arşiv büyümezse profil öncülde kalır. Uzun dönem lig sabitleri için
  football-data geçmişinden profil üretmek ayrı bir iş olur (bu ortamda o veri yok, sayı uydurulmadı).
- Önbellek süreç boyunca tutulur; arşiv aynı süreçte güncellenirse `clear_cache()` çağrılmalı.
