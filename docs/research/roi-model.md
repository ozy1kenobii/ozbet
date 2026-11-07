# Model olasılık kalitesi ve ROI (model ajanı)

Kod: `pipeline/ozbet/research/model_eval.py` — `cd pipeline && python -m ozbet.research.model_eval --fd /home/claude/fd [--cache DIR] [--out f.json] [--test]`
(tam koşu ~45 sn). Protokol: `/home/claude/fd-PROTOKOL.md`.

## Yöntem
- 10 lig, haftalık walk-forward Dixon-Coles (eğitim penceresi: hafta başından önceki 1100 gün, yalnız geçmiş maçlar).
- Değerlendirme kümesi: model tahmini + Pinnacle açılış + Pinnacle kapanış (1X2 ve 2.5) olan maçlar.
  Geliştirme 2122–2324 (n=10 852), doğrulama 2425 (n=3 552), kilitli test 2526+2627 (n=1 686; 2627'de kapanış oranı yok,
  2526'da kısmen var → test fiilen 2526'nın kapanışlı maçları).
- Piyasa girdisi yalnız AÇILIŞ Pinnacle (yoksa Avg) Shin. Kapanış yalnız kıyas.
- Denenen yapılandırma sayısı: 28 DC (7 hiperparametre × 4 şut harmanı) + 19 harman + 21 (eşik × fiyat) = 68. Çok denemede şans kazancı beklenir.

## Doğrulama 2425 (log-loss 1X2 / Brier / Ü-A 2.5 log-loss)
| | 1X2 LL | Brier | Ü/A LL |
|---|---|---|---|
| Üretim DC (ξ=0.0019, L2 0.5, şut 0.4) | 0.9890 | 0.5900 | 0.6771 |
| En iyi DC (ξ=0.0028, şut 0.4) | 0.9886 | 0.5898 | 0.6778 |
| Üretim harmanı α=0.25 | 0.9722 | 0.5788 | 0.6708 |
| Stacking (koşullu logit, seçilen) | **0.9688** | 0.5768 | 0.6703 |
| Piyasa açılış (Pinnacle Shin) | 0.9698 | 0.5773 | 0.6704 |
| Piyasa kapanış (Pinnacle Shin) | 0.9661 | 0.5746 | 0.6677 |

Hiperparametreler (ξ 0.0012/0.0028, L2 0.2/1.0, takım bazlı ev avantajı, promote öncülü) farkı ≤0.0005 — gürültü düzeyi.
Şut harmanı 0.4 yerinde. λ-harmanı (açılış oranından ters çözülmüş λ) doğrusal harmandan kötü.
Doğrusal harmanda α küçüldükçe iyileşir (α=0 en iyi): DC piyasaya bilgi eklemiyor.
Stacking katsayıları: model log p ağırlığı **−0.24**, piyasa **+1.30** → kazanç büyük ölçüde açılış piyasasının
yeniden kalibrasyonundan (keskinleştirme) geliyor; yalnız-piyasa kalibrasyonu da 0.9689.

## Kilitli test (tek koşu, sonrasında değişiklik yok)
| | 1X2 LL | Brier | Ü/A LL |
|---|---|---|---|
| Üretim DC | 0.9940 | 0.5927 | 0.6882 |
| Üretim harmanı α=0.25 | 0.9764 | 0.5818 | 0.6801 |
| Seçilen stacking | **0.9705** | 0.5789 | 0.6798 |
| Piyasa açılış | 0.9733 | 0.5801 | 0.6793 |
| Piyasa kapanış | 0.9723 | 0.5795 | 0.6764 |

1X2'de stacking açılışı ve kapanışı test edilen örnekte geçti (fark ~0.002–0.003, n=1 686 → istatistiksel olarak zayıf). Ü/A'da piyasayı geçemedi.

## ROI (seçilen olasılık, kural EV = p·oran − 1 ≥ e; e doğrulamada seçildi, n≥150 şartı)
| Fiyat | e | Test bahis | İsabet | Ort. oran | ROI | %95 GA | CLV (Pinnacle) |
|---|---|---|---|---|---|---|---|
| Max | 0.06 | 157 | %40.1 | 3.32 | +9.6% | [−13.1%, +33.5%] | −2.8% |
| Avg | 0.04 | 40 | %40.0 | 2.96 | −14.8% | [−49%, +22%] | −3.9% |
| iddaa benzetimi | — | 0 | | | | | |

- iddaa benzetimi (%20/%18 marj): doğrulamada hiçbir eşikte ≥150 bahis yok; testte 0 bahis. Model+piyasa, iddaa marjını aşan değer bulamıyor.
- Max'te pozitif ROI'nin GA'sı sıfırı kapsıyor ve CLV negatif → güvenilmez; Max fiyatı iddaa'da yok.
- Mevcut üretim kuralı (α=0.25, ima farkı ≥0.05) testte 19 bahis, iddaa fiyatıyla −5.8% (n çok küçük).
- Sezon kırılımı: test fiilen yalnız 2526 (en kötü sezon = tek sezon). Lig kırılımı JSON çıktısında (`by_league`).

## Sonuç ve üretim
- DC modeli piyasaya bilgi eklemiyor; hiperparametre ayarı anlamlı fark yaratmadı. **Üretime dokunulmadı.**
- Stacking'in kazancı açılış Pinnacle oranının kalibrasyonundan geliyor ve modelin katsayısı negatif; üretim iddaa oranından
  ima olasılık kullandığı için doğrudan taşınamaz, ve iddaa fiyatında değer bahsi üretmediği için ROI'ye etkisi yok.
- Öneri (test edilmedi, kanıt yalnız doğrulama): `MODEL_WEIGHT` düşük tutulmalı (doğrulamada 0.25 → 0.1 → 0 her adım daha iyi);
  değer etiketi iddaa'da kâr vaat etmemeli.
