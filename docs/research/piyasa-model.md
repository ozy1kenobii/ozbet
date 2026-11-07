# Piyasa-tabanlı model (market_lambda) ve iddaa iç tutarlılık tarayıcısı

## Yöntem
- iddaa 1X2 + Alt/Üst 1.5/2.5/3.5 + KG oranları → Shin ile adil olasılık (grup bazında).
- Dixon-Coles skor matrisi (0..10 gol) için (λ_ev, λ_dep, ρ), Σ KL(adil ‖ model) en küçüklenerek uydurulur.
  En az 1X2 + bir gol marketi gerekir. İY 1X2 / İY Alt-Üst varsa ht_share ayrıca uydurulur (yoksa 0.44).
- Bu λ'larla `simulate()` (10.000 MC) → skor matrisi, İY/MS, 50 örnek koşu, tüm ek marketler.
- Lig modeli olmayan maçta `m.model` (source="piyasa", not: "Piyasa oranlarından türetildi; bağımsız tahmin değildir").
  Lig modeli olan maçta `m.market_model` (yalnız kıyas). Piyasa modelinden **değer etiketi, tercih, konsensüs oyu
  ve karne (scorecard) satırı üretilmez** — piyasayı kendisiyle kıyaslamak olur.

## Doğrulama (football-data, Pinnacle açılış 1X2 + 2.5 A/Ü → λ; lig modeli = model_eval walk-forward "base")
Ortalama log-kayıp (düşük iyi). Kilitli test sezonları (2526, 2627) kullanılmadı; parametre ayarı yapılmadı.
İY için iki model de aynı ht_share=0.44 (veride İY oranı yok).

| Market | Geliştirme 2021–2324 (n=14.542) piyasa | lig modeli | Doğrulama 2425 (n=3.547) piyasa | lig modeli |
|---|---|---|---|---|
| 1X2 (uydurulan) | 0.9774 | 0.9995 | 0.9696 | 0.9918 |
| 2.5 A/Ü (uydurulan) | 0.6743 | 0.6885 | 0.6704 | 0.6800 |
| KG Var/Yok | **0.6839** | 0.6931 | **0.6866** | 0.6917 |
| Toplam gol (0..5, 6+) | **1.8062** | 1.8278 | **1.7951** | 1.8105 |
| Tam skor (0..5², diğer) | **2.8635** | 2.9075 | **2.8392** | 2.8764 |
| İY sonucu | **1.0319** | 1.0441 | **1.0293** | 1.0387 |

1X2 ve 2.5 satırları girdiyle aynı marketler (doğal olarak iyi); asıl ölçüt uydurmaya girmeyen KG, toplam gol
dağılımı, tam skor ve İY sonucudur — dördünde de piyasa-tabanlı λ lig modelinden iyi. Yani piyasanın 1X2+A/Ü
bilgisi, skor dağılımına açıldığında da modelimizden daha iyi kalibre.
Tekrar: `python -m ozbet.research.market_model_eval --fd /home/claude/fd` (~2 dk).

## İç tutarlılık tarayıcısı (`m.consistency`)
iddaa'nın ek market oranları (KG×MS, MS&A/Ü, gol aralığı, handikap, tek/çift, İY, İY/MS, takım golü…) piyasa-tabanlı
adil olasılıkla kıyaslanır; EV = p·oran − 1. En yüksek EV'li ilk 5 satır "En iyi fiyatlı seçenekler" olarak gösterilir.
Bu **değerli bahis değildir**: EV'ler genelde negatiftir (ör. bugün −%1…−%11); yalnız "bu maçta marjı en düşük" satırlardır.
p<0.03 satırlar atlanır (simülasyon gürültüsü). 0-0 gibi düşük skor satırları ρ'ya duyarlıdır.
**Backtest mümkün değil**: geçmiş iddaa ek market oranları yok (football-data yalnız 1X2, 2.5, AH veriyor).

## Bugünkü veri (data/latest.json, 2026-11-06 bülteni)
231 maçtan 21'inde lig modeli var; kalan 210'un 194'üne piyasa modeli eklenebiliyor (16'sında 1X2 veya gol marketi yok).
