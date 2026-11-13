# Kalibre olasılık (model/calibration.py)

Kod: `pipeline/ozbet/model/calibration.py` — `calibrated_prob(market, model_p, implied_p, league=None)` ve
`calibrated_group(probs, implied, keys)`. Bu dosyanın tabloları:
`cd pipeline && python -m ozbet.research.calibration_eval --md ../docs/research/kalibrasyon.md`

## Yöntem
- Logit uzayında harman: `logit(p) = logit(q) + w·g(d)`, `d = logit(model) − logit(piyasa)`.
- Aile bazında model ağırlığı `w`: Maç sonucu 0.15, Toplam gol 0.10, KG Var/Yok 0.05, Takım golü 0.05, Yarılar 0.15, Kombine 0.10, Diğer 0.10.
- Seçim yanlılığı (kazananın laneti): model piyasadan yukarıdaysa fark `g(d) = T·tanh(d/T)`, T = 0.5 ile doyurulur;
  aşağıdaysa aynen kalır. Seçici çok sayıda gürültülü tahminin en büyüğünü aldığı için yukarı sapma şişkindir.
- Piyasa yoksa model, marketin uzun dönem taban oranına doğru büzülür (logit farkının %60'ı korunur).
- Grup (1/X/2, 2.5 Üst/Alt, KG Var/Yok) `calibrated_group` ile yeniden 1'e normalleştirilir.

## Ağırlıklar nereden geliyor
Ağırlıklar bu örneğe **uydurulmadı**; araştırma öncüllerinden seçilmiş tutucu sabitlerdir:
- `roi-model.md`: doğrulamada doğrusal harman ağırlığı 0.25 → 0.1 → 0 her adımda daha iyi; Dixon-Coles piyasaya
  bilgi eklemiyor → genel düzey 0.25'in altında (0.15).
- `piyasa-model.md`: KG ve toplam gol dağılımında piyasa-tabanlı λ lig modelinden iyi (doğrulama n=3.547) →
  KG 0.05, toplam gol 0.10. Canlı karnede de modelin en zayıf olduğu aileler bunlar ve takım golü
  (log-loss 0.6866 / 0.6452) → 0.05; yarılarda fark en küçük → 0.15.
- Stacking'deki piyasa keskinleştirmesi (katsayı 1.30) Pinnacle açılış oranına aitti; iddaa ima olasılığına
  taşınamadığı için uygulanmadı.

## Akıl sağlığı kontrolü — canlı veri (5 gün, 138 maç)
Gözlem = model olasılığı, marjsız piyasa olasılığı ve sonucu olan her market. Düşük değer iyi.

### Log-loss
| Aile | n | Ham model | Harman 0.25 | Kalibre | Piyasa |
|---|---|---|---|---|---|
| Maç sonucu | 1032 | 0.5967 | 0.5850 | 0.5841 | 0.5838 |
| Toplam gol | 1226 | 0.6083 | 0.5977 | 0.5966 | 0.5964 |
| KG Var/Yok | 276 | 0.6998 | 0.6792 | 0.6753 | 0.6746 |
| Takım golü | 348 | 0.6866 | 0.6530 | 0.6464 | 0.6452 |
| Yarılar | 2107 | 0.4887 | 0.4852 | 0.4850 | 0.4851 |
| Kombine | 1436 | 0.4487 | 0.4379 | 0.4363 | 0.4358 |
| **Hepsi** | 6425 | 0.5397 | 0.5296 | 0.5283 | 0.5280 |

### Brier
| Aile | n | Ham model | Harman 0.25 | Kalibre | Piyasa |
|---|---|---|---|---|---|
| Maç sonucu | 1032 | 0.2044 | 0.1996 | 0.1993 | 0.1993 |
| Toplam gol | 1226 | 0.2115 | 0.2068 | 0.2064 | 0.2063 |
| KG Var/Yok | 276 | 0.2528 | 0.2431 | 0.2413 | 0.2410 |
| Takım golü | 348 | 0.2461 | 0.2304 | 0.2273 | 0.2268 |
| Yarılar | 2107 | 0.1611 | 0.1597 | 0.1596 | 0.1596 |
| Kombine | 1436 | 0.1420 | 0.1385 | 0.1380 | 0.1379 |
| **Hepsi** | 6425 | 0.1819 | 0.1778 | 0.1773 | 0.1772 |

### Modelin piyasadan çok yüksek olduğu dilim (model − piyasa ≥ 0.08): ortalama olasılık
| Dilim | n | Gerçekleşen | Ham model | Harman 0.25 | Kalibre | Piyasa |
|---|---|---|---|---|---|---|
| Maç sonucu | 127 | %28.3 | %46.4 | %37.2 | %35.3 | %34.1 |
| Toplam gol | 124 | %29.8 | %47.5 | %38.7 | %36.6 | %35.8 |
| KG Var/Yok | 26 | %26.9 | %53.7 | %45.1 | %42.7 | %42.2 |
| Takım golü | 52 | %32.7 | %55.7 | %46.2 | %43.4 | %43.0 |
| Yarılar | 56 | %25.0 | %38.0 | %30.7 | %29.3 | %28.3 |
| Kombine | 40 | %7.5 | %34.5 | %26.4 | %24.3 | %23.7 |
| **Hepsi** | 425 | %26.8 | %46.1 | %37.4 | %35.3 | %34.4 |

### Seçicinin seçtiği marketler (OZBET Tercihi): ortalama olasılık
| Dilim | n | Gerçekleşen | Ham model | Harman 0.25 | Kalibre | Piyasa |
|---|---|---|---|---|---|---|
| **Hepsi** | 138 | %63.8 | %61.1 | %64.2 | %64.8 | %65.2 |
| BTTS_Y | 60 | %56.7 | %58.9 | %61.0 | %61.6 | %61.7 |
| 1 | 19 | %79.0 | %60.6 | %66.3 | %67.2 | %68.2 |
| O2.5 | 16 | %62.5 | %65.4 | %69.0 | %69.8 | %70.2 |
| U2.5 | 16 | %56.2 | %59.4 | %58.1 | %57.8 | %57.6 |
| 2 | 14 | %71.4 | %55.8 | %65.4 | %66.9 | %68.6 |

## Uyarılar
- Örnek çok küçük: 5 gün, 138 maç. Aynı maçın marketleri birbirine bağımlı olduğu için
  etkin örnek, tablodaki n'den çok daha küçüktür; aileler arası farklar gürültü düzeyinde olabilir.
- Bu tablo yalnız yön kontrolüdür: kalibre olasılığın ham modelden ve 0.25 harmanından kötü olmadığını gösterir.
  Parametre seçimi için kullanılmadı.
- Kalibre olasılık piyasaya çok yakındır; iddaa marjı (~%20) düşünüldüğünde pozitif beklenen değer nadiren çıkar.
  Bu beklenen sonuçtur: araştırma iddaa fiyatında değer bulamadı. Kâr vaadi yoktur.
- **Tercihlerdeki iyimserlik bununla düzelmez.** Seçilen KG Var tercihlerinde ham model zaten piyasadan düşüktü;
  yüksek tahmini veren piyasanın kendisi (son tablo). Kalibre olasılık piyasaya yaklaştığı için o dilimde
  ortalama olasılık değişmiyor. Fark küçük örnekte (n=60, standart hata ~6 puan) gürültüyle de açıklanabilir;
  kalıcıysa çözüm harman değil, seçim kuralıdır (en yüksek olasılığı seçmek yerine farklı ölçüt).
- Model piyasadan çok yüksekse (üçüncü tablo) gerçekleşen oran piyasanın bile altında: yukarı sapmayı kısmak
  doğru yönde, ama bu dilimde de n küçük.
