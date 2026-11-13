# Gol yanlılığı: model gollerde gerçekten iyimser mi?

Kod: `pipeline/ozbet/research/goals_bias.py` — `cd pipeline && python -m ozbet.research.goals_bias [--out rapor.json]`
Veri: yalnız depo (13.11.2026): `data/archive` 97 maç, gün dosyalarında bitmiş + modelli 138 maç (5–9 Kasım), `data/history`.
Kâr vaadi yok; örnek küçük, aşağıdaki her sayı n ve belirsizliğiyle okunmalı.

## Kısa cevap
1. **Model gol seviyesinde iyimser değil.** Tüm maçlarda (yalnız tercihler değil) ortalama λ toplamı 2,83, gerçek gol 2,81 ± 0,15.
2. **Karnedeki fark seçilmiş örnekten ve piyasa payından geliyor.** Tercih olasılığı %25 model + %75 iddaa iması; KG Var
   tercihlerinde model %58,9, piyasa %61,7, gözlenen %56,7. Model piyasadan *daha az* iyimserdi.
3. **Asıl kusur seviye değil ayrıştırma:** modelin maçlar arası toplam gol farkları sonucu neredeyse hiç ayırt etmedi
   (Ü2.5 kalibrasyon eğimi 0,11; KG −0,01; piyasada 0,64 / 0,97). 1X2'de eğim ≥ 1 — sorun yalnız "gollü/golsüz maç" bileşeninde.
4. **Düzeltme:** √(λ_ev·λ_dep) lig taban seviyesine yarı yarıya büzüldü (k = 0,5), λ_ev/λ_dep oranı korunuyor.

## Bulgular

### Tüm bitmiş maçlar (n = 138) — tahmin / gözlenen
| | Tahmin | Gözlenen | z |
|---|---|---|---|
| Toplam gol (λ) | 2,83 | 2,81 ± 0,15 | +0,1 |
| Ü1.5 | %76,8 | %76,1 | +0,2 |
| Ü2.5 | %53,0 | %53,6 | −0,1 |
| Ü3.5 | %31,5 | %26,8 | +1,2 |
| KG Var | %54,7 | %56,5 | −0,4 |
| Ev Ü1.5 | %42,8 | %39,7 | +0,8 |
| Dep Ü1.5 | %38,0 | %42,0 | −1,0 |
| 0-0 | %7,0 | %5,1 | +0,9 |
| Beraberlik | %25,2 | %23,9 | +0,3 |

Hiçbiri |z| ≥ 2 değil. Ü3.5 fazlası ve 0-0 fazlası aynı anda görülüyor (Poisson'dan dar dağılım yönünde) ama n = 138'de anlamsız.
Aynı maçlarda iddaa iması Ü2.5 %57,3, KG %57,3 (gözlenen %53,6 / %56,5): iyimser olan taraf piyasa imasıydı.

### Kırılımlar
| Grup | n | λ | Gol | Not |
|---|---|---|---|---|
| Lig modeli | 131 | 2,82 | 2,85 ± 0,16 | yansız |
| Lig gücü katsayısı (kupa, Elo yok) | 7 | 2,94 | 2,14 ± 0,55 | n çok küçük |
| Veri kalitesi yüksek / orta | 92 / 46 | 2,79 / 2,89 | 2,87 / 2,70 | fark gürültü içinde |
| Şut harmanı var / yok | 127 / 11 | 2,81 / 2,97 | 2,84 / 2,46 | "yok" grubu n = 11 |
| xG harmanı, kadro düzeltmesi | 0 | — | — | örnekte hiç devreye girmemiş, ölçülemedi |

### Tercihler: seviye ↔ seçim ayrıştırması
| Tercih | n | Tercih p | Model | Piyasa | Gözlenen | Seviye yanlılığı (tüm maçlar) | Seçim etkisi |
|---|---|---|---|---|---|---|---|
| KG Var | 60 | %61,0 | %58,9 | %61,7 | %56,7 ± 6,4 | −1,8 puan | +6,1 puan |
| Ü2.5 | 16 | %69,0 | %65,4 | %70,2 | %62,5 ± 12,1 | −0,6 puan | +7,1 puan |

Seçim etkisi = kazananın laneti + harmandaki piyasa payı. İkisi de standart hatanın (6–12 puan) içinde; "model iyimser" denemez.

### Arşiv walk-forward
Çalıştırıldı, **hiçbir lig eşiği geçmedi**: 11 ligde toplam 97 maç (lig başına 3–12; gereken eğitim ≥ 60 + test ≥ 30).
Araç hazır (lig başına ve havuz, k = 1 ve k = 0,5 yan yana); arşiv büyüdükçe aynı komut önce/sonra tablosunu üretir.
football-data.co.uk bu ortamdan erişilemediği için büyük geçmiş backtest koşulamadı.

## Yapılan değişiklik: toplam gol büzmesi
`dixon_coles.shrink_total` + `Ratings.base_level`; `agents/simulation.predict` lig yolunda, harmanlardan sonra ve kadro
düzeltmesinden önce uygulanır. Taban = e^(μ + h/2) (ligin ortalama eşleşmesi). `OZBET_TOTAL_SHRINK=1` ile kapatılır.
Model notuna "Toplam gol beklentisi lig ortalamasına büzüldü" eklenir; `simulate()` şeması aynı.

Kanıt: kayıtlı canlı λ'lar üzerinde tekrar oynatma (lig modeli, n = 131; taban = ligin örnekteki tahmin ortalaması,
sonuç kullanılmadan). Log-loss, düşük olan iyi; fark için maç bazında eşli bootstrap %95 GA.

| | Önce (k = 1) | Sonra (k = 0,5) | Fark | %95 GA |
|---|---|---|---|---|
| Gol (Ü1.5, Ü2.5, Ü3.5, KG ort.) | 0,6385 | 0,6253 | −0,0132 | [−0,0244, −0,0027] |
| Takım golü (ev/dep Ü1.5 ort.) | 0,6458 | 0,6349 | −0,0108 | [−0,0188, −0,0031] |
| 1X2 | 0,9781 | 0,9766 | −0,0015 | [−0,0059, +0,0029] |
| Ortalama λ toplamı | 2,819 | 2,802 | | gerçek 2,85 |

İyileşme n ≥ 20 olan üç günün üçünde de aynı yönde (6/7/8 Kasım, n = 20, 58, 52); tek maçlık 9 Kasım'da ters. k küçüldükçe kazanç sürüyor (k = 0: −0,0194) ama
GA sıfıra değiyor; n = 131 ile tam büzme aşırı uyum olur, bu yüzden temkinli orta değer k = 0,5 seçildi.
Sınır: k aynı 131 maçta denendi (5 değer), tek hafta, gerçek walk-forward yok. Arşiv dolunca yeniden bakılmalı.
Not: `backtest.py` ve `model_eval.py` kendi λ hesabını kullanır, büzmeyi görmez.

## Dokunulmayanlar ve neden
- **Toplam gol seviyesi / lig taban oranı:** yanlılık yok (2,83 vs 2,81), düzeltme gereksiz.
- **ρ ve düşük skor (0-0, 1-0):** 0-0 %7,0 vs %5,1, z = +0,9; yön "eksik 0-0" değil. Kanıt yok.
- **Zaman ağırlığı, L2, ev avantajı:** ev λ 1,48 / gol 1,41, dep 1,34 / 1,40 — fark SE içinde. Yeniden kurup sınayacak veri yok.
- **Şut harmanı (0,4):** 127 maça karşı 11; ayrıştırılamıyor. Toplam gol gürültüsünün kaynağı olabilir, ölçülemedi.
- **xG harmanı, kadro çarpanları:** canlı örnekte hiç tetiklenmemiş; kanıt olmadan değiştirilmedi.
- **Kupa / lig gücü yolu:** n = 7 (λ 2,94 vs gol 2,14) — izlenmeli, karar için yetersiz.
- **Korner/kart (counts.py):** bu çalışmanın verisi yok.
