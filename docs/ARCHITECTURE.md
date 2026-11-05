# OZBET – Mimari

```
ozbet/
├─ pipeline/                 Python veri boru hattı (GitHub Actions'ta koşar)
│  ├─ ozbet/
│  │  ├─ config.py           Ligler, eşikler, saatler
│  │  ├─ http.py             Nazik HTTP: gecikme, disk önbelleği, robots.txt, User-Agent
│  │  ├─ teams.py            Takım adı sözlüğü + rapidfuzz bulanık eşleme
│  │  ├─ markets.py          Market anahtarları ve Türkçe etiketler
│  │  ├─ sources/            Her site için bir adapter → ortak şema
│  │  ├─ model/              Dixon-Coles + Monte Carlo
│  │  ├─ agents/             Bülten, İstatistik, Kadro, Konsensüs, Piyasa,
│  │  │                      Simülasyon, Yorumcu, Değer, Karne
│  │  ├─ run.py              Günlük çalıştırma (python -m ozbet.run)
│  │  └─ backtest.py         Geçmiş sezon backtest raporu
│  └─ tests/
├─ web/                      Vite + React + Tailwind PWA (sadece JSON okur)
├─ data/                     Pipeline çıktısı (Actions commit eder)
│  ├─ latest.json
│  ├─ YYYY-MM-DD.json
│  ├─ index.json             Mevcut günlerin listesi
│  ├─ scorecard.json         Karne
│  ├─ status.json            Kaynak durumları
│  ├─ backtest.json          Backtest raporu
│  ├─ history/               Puanlanmış geçmiş tahminler (YYYY-MM-DD.json)
│  └─ archive/               Birikimli sonuç arşivi (results-{LIG}.json) — model girdisi, frontend okumaz
└─ .github/workflows/        pipeline.yml (08:30/13:30/18:30 TR) + deploy
```

## Akış
1. **Bülten Ajanı** günün maçlarını ve oranlarını toplar (nesine → iddaa → football-data.co.uk fixtures.csv → flashscore).
2. **İstatistik Ajanı** geçmiş sonuçlardan (football-data.co.uk CSV + xG kaynakları) form, gol, KG, Ü/A, korner, kart, H2H hesaplar.
3. **Kadro & Haber Ajanı** eksikleri ve rotasyon riskini çıkarır → λ düzeltmesi.
4. **Simülasyon Ajanı** Dixon-Coles (zaman ağırlıklı) + xG harmanı + iç saha + kadro düzeltmesi, 10.000 Monte Carlo.
5. **Piyasa Ajanı** marjı temizlenmiş ima olasılık, sabah→akşam oran hareketi, düşen oran alarmı.
6. **Konsensüs Ajanı** forebet / sportytrader / freesupertips (+ model + piyasa) uzlaşması.
7. **Değer Ajanı** model_p − ima_p ≥ %5 ise "Değerli".
8. **Yorumcu Ajanı** kural tabanlı Türkçe yorum (LLM_API_KEY varsa kısa LLM yorumu) + OZBET Tercihi + yıldız.
9. **Karne Ajanı** biten maçları puanlar; kötü giden marketlerin güvenini düşürür.

Bir kaynak hata verirse `status.json`'da `missing` olarak işaretlenir, akış devam eder.

## Market anahtarları
`1, X, 2, 1X, X2, 12, O1.5, U1.5, O2.5, U2.5, O3.5, U3.5, BTTS_Y, BTTS_N`
HT/FT anahtarları: `1/1, 1/X, 1/2, X/1, X/X, X/2, 2/1, 2/X, 2/2`

## Gün dosyası şeması (data/YYYY-MM-DD.json ve latest.json)
```jsonc
{
  "schema_version": 1,
  "date": "2026-11-05",
  "generated_at": "2026-11-05T08:31:12+03:00",
  "run_label": "08:30",
  "sources": [ {"id":"nesine","name":"Nesine bülten","status":"ok|partial|missing","fetched_at":"...","note":"..."} ],
  "leagues": [ {"id":"TR1","name":"Süper Lig","country":"Türkiye","priority":1} ],
  "matches": [ Match ]
}
```

### Match
```jsonc
{
  "id": "TR1-20261105-galatasaray-fenerbahce",
  "code": "1234" ,            // iddaa maç kodu veya null
  "mbs": 1,                   // veya null
  "league": "TR1", "league_name": "Süper Lig", "league_priority": 1,
  "kickoff": "2026-11-05T20:00:00+03:00",
  "home": {"name":"Galatasaray"}, "away": {"name":"Fenerbahçe"},
  "status": "scheduled|live|finished",
  "result": {"ft":[2,1], "ht":[1,0]} ,            // veya null
  "odds": {"1":2.10,"X":3.40,"2":3.20,"O2.5":1.80,"U2.5":2.00,"BTTS_Y":1.70,"BTTS_N":2.05},   // eksik market yoksa anahtar yok; tamamen yoksa null
  "odds_history": [ {"t":"2026-11-05T08:31:00+03:00","1":2.20,"X":3.30,"2":3.10} ],
  "market": {
    "implied": {"1":0.45,"X":0.28,"2":0.27,"O2.5":0.53,"U2.5":0.47},
    "margin": {"1x2":0.061,"ou25":0.05},
    "movement": {"1":-0.045},            // ilk görülen → son oran, oransal değişim
    "drop_alarms": ["1"]
  },                                     // veya null
  "model": {
    "lambda_home":1.62, "lambda_away":1.08, "sims":10000, "rho":-0.08,
    "probs": {"1":0.48, "X":0.26, "2":0.26, "1X":0.74, "...":0},
    "htft": {"1/1":0.30, "...":0},
    "top_scores": [ {"score":"1-0","p":0.11} ],
    "score_matrix": [[0.07,0.06,"..."]],   // 6x6, [ev][dep], 0..5
    "total_goals": [0.07,0.19,0.26,0.22,0.14,0.07,0.05],   // 0..5, son eleman 6+
    "data_quality": "high|medium|low",   // Elo'lu çapraz lig/kupa maçı: "medium"
    "method": "league|elo|league_strength", // lig modeli | Elo tabanlı lig-arası | yedek lig gücü katsayısı
    "notes": ["xG harmanı kullanıldı"]
  },                                     // veri yoksa null
  "stats": {
    "home": {"form":["W","D","L"], "venue_form":["W","W"], "gf_avg":1.8, "ga_avg":0.9,
             "venue_gf_avg":2.1, "venue_ga_avg":0.6, "xg_avg":null, "xga_avg":null,
             "btts_pct":0.5, "o25_pct":0.6, "clean_sheets_venue":5, "venue_n":6,
             "corners_avg":5.4, "cards_avg":2.1, "n":10},
    "away": { "...": "aynı" },
    "h2h": [ {"date":"2026-03-01","home":"Fenerbahçe","away":"Galatasaray","score":"1-1"} ]
  },
  "squad": {
    "home": {"missing":[{"name":"X","reason":"sakat|cezalı|şüpheli","key":true}], "rotation_risk":false, "coach_change":false, "adjustment":0.0},
    "away": { "...": "aynı" },
    "source": "flashscore", "fetched_at": "..."
  },                                     // veya null
  "consensus": {
    "sources": [ {"source":"forebet","picks":{"1X2":"1","OU25":"O2.5","BTTS":"BTTS_Y"},"probs":{"1":0.5,"X":0.27,"2":0.23},"fetched_at":"..."} ],
    "summary": [ {"market":"BTTS_Y","agree":4,"total":5,"text":"5 kaynaktan 4'ü KG Var diyor"} ]
  },
  "value": [ {"market":"O2.5","model_p":0.58,"implied_p":0.52,"odds":1.80,"edge":0.06,"ev":0.044} ],
  "value_note": "Değer yok",             // value boşsa
  "pick": {"market":"O2.5","label":"2.5 Üst","p":0.58,"odds":1.80,"stars":3,"is_value":true},   // veya null
  "comment": "Türkçe 4-6 cümle",
  "comment_source": "kural|llm",
  "elo": {"home":1850, "away":1720, "source":"clubelo", "date":"2026-11-05"},   // ClubElo'da iki takım da bulunursa; yoksa anahtar yok
  "flags": ["Düşük veri", "Oran yok"],
  "provenance": { "odds": {"source":"nesine","t":"..."}, "stats": {"source":"football-data.co.uk","t":"..."} }
}
```

### Kupa / çapraz lig maçları (Elo tabanlı düzeltme)
`agents/simulation.py`: kupa maçında takımlar farklı lig modellerindeyse (ya da biri hiç modelde yoksa) ve
ClubElo puanı varsa:
1. `We = 1/(1+10^(-(Elo_ev + HFA - Elo_dep)/400))`, `HFA = config.ELO_HFA = 63` (tarafsız sahada 0).
2. Toplam gol `T`: iki takımın kendi lig modellerinden, ortalama rakibe karşı `e^(μ+a) + e^(μ+d)` ortalaması
   (ikisi de modelde yoksa `ELO_DEFAULT_TOTAL = 2,6`).
3. `λ_ev + λ_dep = T` kısıtıyla Dixon-Coles skor matrisinde `P(1) + ½P(X) = We` olacak gol farkı ikiye bölmeyle çözülür.

Bayrak: `"Kupa: Elo tabanlı lig-arası düzeltme"` (Elo yoksa eski `"Kupa/çapraz lig: model düşük güvenli, değer etiketi
verilmez"`). Her iki durumda da kupada değer etiketi verilmez, yıldız ≤ 2. Elo yoksa eski `LEAGUE_STRENGTH` yolu çalışır.

## data/archive/results-{LIG}.json (birikimli sonuç arşivi)
Her çalıştırmada flashscore sonuç feed'inden dünün (ve işlenmemiş son 7 günün) biten maçları, `league_for` ile
belirlenen lige eklenir. Kupa, eşlenemeyen, kadın/altyapı ligleri girmez. Tekrar yok (tarih + takım anahtarı + flashscore id).
```jsonc
{
  "league": "TR2", "updated_at": "2026-11-06T08:31:00+03:00",
  "days": ["2026-11-05"],                    // işlenmiş feed günleri
  "rows": [ {"date":"2026-11-05","home":"Boluspor","away":"Manisa FK","ft":[1,2],"ht":[1,0],
             "src":"flashscore","fs_id":"abc123"} ]   // ht yoksa null
}
```
`registry.extra_history`, football-data.co.uk'ta olmayan ligler için kaynak adaylarını toplar
(soccerstats sonuç sayfası, ≥ `ARCHIVE_MIN_MATCHES = 60` maçlı arşiv, API-Football) ve takım adı yazımları karışmasın
diye lig başına **en çok satırı olan tek kaynağı** seçer. Ana ligler (football-data.co.uk) her zaman önceliklidir.

## data/scorecard.json
```jsonc
{
  "generated_at": "...",
  "overall": {"n":120, "hit_rate":0.54, "brier_1x2":0.198, "roi":0.031, "staked":120, "profit":3.7},
  "last30": { "...": "aynı" },
  "by_league": [ {"league":"TR1","name":"Süper Lig","n":40,"hit_rate":0.55,"roi":0.02} ],
  "by_market": [ {"market":"O2.5","label":"2.5 Üst","n":30,"hit_rate":0.6,"roi":0.08,"trust":1.0} ],
  "calibration": [ {"bin":"0.5-0.6","predicted":0.55,"observed":0.53,"n":44} ],
  "bankroll": [ {"date":"2026-11-01","balance":100.0} ],
  "recent": [ {"date":"...","match":"A - B","pick":"2.5 Üst","odds":1.8,"won":true,"score":"2-1"} ]
}
```

## data/index.json
`{"dates":["2026-11-05","2026-11-04"], "latest":"2026-11-05"}`
