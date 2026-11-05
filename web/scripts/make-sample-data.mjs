// ÖRNEK VERİ üretici — web/sample-data/ altına şemaya uyan UYDURMA veri yazar.
// Takım adları gerçek olabilir, TÜM SAYILAR UYDURMADIR. Gerçek sitede asla gösterilmez.
// Kullanım: node scripts/make-sample-data.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'sample-data');
fs.mkdirSync(out, { recursive: true });

let seed = 42;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
const r2 = (x, d = 2) => Math.round(x * 10 ** d) / 10 ** d;
const fact = (n) => (n <= 1 ? 1 : n * fact(n - 1));
const pois = (l, k) => Math.exp(-l) * l ** k / fact(k);

function model(lh, la, quality = 'high') {
  const N = 11;
  const M = [];
  for (let h = 0; h < N; h++) { M.push([]); for (let a = 0; a < N; a++) M[h].push(pois(lh, h) * pois(la, a)); }
  const tau = (h, a, rho) => (h === 0 && a === 0 ? 1 - lh * la * rho : h === 0 && a === 1 ? 1 + lh * rho : h === 1 && a === 0 ? 1 + la * rho : h === 1 && a === 1 ? 1 - rho : 1);
  const rho = -0.08;
  let s = 0; for (let h = 0; h < N; h++) for (let a = 0; a < N; a++) { M[h][a] *= tau(h, a, rho); s += M[h][a]; }
  for (let h = 0; h < N; h++) for (let a = 0; a < N; a++) M[h][a] /= s;
  const sum = (f) => { let t = 0; for (let h = 0; h < N; h++) for (let a = 0; a < N; a++) if (f(h, a)) t += M[h][a]; return t; };
  const p = {
    '1': sum((h, a) => h > a), X: sum((h, a) => h === a), '2': sum((h, a) => h < a),
  };
  p['1X'] = p['1'] + p.X; p.X2 = p.X + p['2']; p['12'] = p['1'] + p['2'];
  for (const L of [1.5, 2.5, 3.5]) { const o = sum((h, a) => h + a > L); p[`O${L}`] = o; p[`U${L}`] = 1 - o; }
  p.BTTS_Y = sum((h, a) => h > 0 && a > 0); p.BTTS_N = 1 - p.BTTS_Y;
  for (const k in p) p[k] = r2(p[k], 3);
  const matrix = M.slice(0, 6).map((row) => row.slice(0, 6).map((v) => r2(v, 4)));
  const scores = [];
  for (let h = 0; h < 6; h++) for (let a = 0; a < 6; a++) scores.push({ score: `${h}-${a}`, p: r2(M[h][a], 3) });
  scores.sort((x, y) => y.p - x.p);
  const tg = [0, 1, 2, 3, 4, 5].map((t) => sum((h, a) => h + a === t));
  tg.push(1 - tg.reduce((x, y) => x + y, 0));
  // İY/MS: yaklaşık, İY λ'ları %45
  const hl = lh * 0.45, al = la * 0.45;
  const ht = { '1': 0, X: 0, '2': 0 };
  for (let h = 0; h < 6; h++) for (let a = 0; a < 6; a++) { const v = pois(hl, h) * pois(al, a); ht[h > a ? '1' : h === a ? 'X' : '2'] += v; }
  const htT = ht['1'] + ht.X + ht['2'];
  const cond = { '1': { '1': 0.78, X: 0.15, '2': 0.07 }, X: { '1': p['1'] * 0.95, X: 0, '2': p['2'] * 0.95 }, '2': { '1': 0.1, X: 0.18, '2': 0.72 } };
  cond.X.X = 1 - cond.X['1'] - cond.X['2'];
  const htft = {};
  for (const a of ['1', 'X', '2']) for (const b of ['1', 'X', '2']) htft[`${a}/${b}`] = r2((ht[a] / htT) * cond[a][b], 3);
  return {
    lambda_home: lh, lambda_away: la, sims: 10000, rho,
    probs: p, htft, top_scores: scores.slice(0, 5), score_matrix: matrix,
    total_goals: tg.map((v) => r2(v, 3)), data_quality: quality,
    notes: quality === 'low' ? ['Az maç örneklemi', 'xG verisi yok'] : ['xG harmanı kullanıldı', 'Zaman ağırlıklı Dixon-Coles'],
  };
}

function oddsFrom(p, margin = 1.06) {
  const o = {};
  for (const k of ['1', 'X', '2', 'O2.5', 'U2.5', 'BTTS_Y', 'BTTS_N', 'O1.5', 'U1.5', 'O3.5', 'U3.5', '1X', 'X2', '12']) {
    const noise = 1 + (rnd() - 0.5) * 0.14;
    o[k] = r2(Math.max(1.03, 1 / (p[k] * margin * noise)));
  }
  return o;
}
function implied(odds) {
  const im = {};
  const norm = (keys) => { const t = keys.reduce((s, k) => s + 1 / odds[k], 0); keys.forEach((k) => (im[k] = r2(1 / odds[k] / t, 3))); return t - 1; };
  const m1 = norm(['1', 'X', '2']); const m2 = norm(['O2.5', 'U2.5']); norm(['BTTS_Y', 'BTTS_N']);
  norm(['O1.5', 'U1.5']); norm(['O3.5', 'U3.5']);
  return { im, margin: { '1x2': r2(m1, 3), ou25: r2(m2, 3) } };
}

const LEAGUES = [
  { id: 'TR1', name: 'Süper Lig', country: 'Türkiye', priority: 1 },
  { id: 'TR2', name: '1. Lig', country: 'Türkiye', priority: 2 },
  { id: 'UCL', name: 'Şampiyonlar Ligi', country: 'Avrupa', priority: 3 },
  { id: 'ENG1', name: 'Premier Lig', country: 'İngiltere', priority: 4 },
  { id: 'ESP1', name: 'La Liga', country: 'İspanya', priority: 5 },
];
const LN = Object.fromEntries(LEAGUES.map((l) => [l.id, l]));
const F = (s) => s.split('');

function slug(s) { return s.toLowerCase().replace(/ç/g, 'c').replace(/ğ/g, 'g').replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ş/g, 's').replace(/ü/g, 'u').replace(/[^a-z0-9]+/g, '-'); }

function teamStats(base) {
  const f = () => ['W', 'D', 'L'][Math.floor(rnd() * 3)];
  return {
    form: Array.from({ length: 5 }, f), venue_form: Array.from({ length: 5 }, f),
    gf_avg: r2(base + rnd() * 0.6), ga_avg: r2(0.7 + rnd() * 0.9),
    venue_gf_avg: r2(base + rnd() * 0.8), venue_ga_avg: r2(0.6 + rnd() * 0.9),
    xg_avg: r2(base * 0.95 + rnd() * 0.4), xga_avg: r2(0.8 + rnd() * 0.7),
    btts_pct: r2(0.35 + rnd() * 0.3), o25_pct: r2(0.4 + rnd() * 0.3),
    clean_sheets_venue: Math.floor(rnd() * 5), venue_n: 6,
    corners_avg: r2(4 + rnd() * 3, 1), cards_avg: r2(1.5 + rnd() * 1.5, 1), n: 10,
  };
}

function match(date, spec) {
  const { lg, h, a, time, lh, la, code = null, mbs = 1, noOdds, noModel, noSquad, finished, quality = 'high', alarm, flags = [], lowStats, boost } = spec;
  const kickoff = `${date}T${time}:00+03:00`;
  const md = noModel ? null : model(lh, la, quality);
  const p = md?.probs ?? model(lh, la).probs;
  const odds = noOdds ? null : oddsFrom(p);
  if (odds && boost) for (const b of [].concat(boost)) odds[b] = r2(odds[b] * 1.2);
  let market = null, history = null, value = [];
  if (odds) {
    const { im, margin } = implied(odds);
    const first = { t: `${date}T08:31:00+03:00`, '1': r2(odds['1'] * (alarm ? 1.09 : 1.02)), X: r2(odds.X * 0.99), '2': r2(odds['2'] * (alarm ? 0.95 : 0.99)) };
    const mid = { t: `${date}T13:31:00+03:00`, '1': r2((first['1'] + odds['1']) / 2), X: r2((first.X + odds.X) / 2), '2': r2((first['2'] + odds['2']) / 2) };
    const last = { t: `${date}T18:31:00+03:00`, '1': odds['1'], X: odds.X, '2': odds['2'] };
    history = [first, mid, last];
    const movement = {}; for (const k of ['1', 'X', '2']) movement[k] = r2(last[k] / first[k] - 1, 3);
    market = { implied: im, margin, movement, drop_alarms: alarm ? ['1'] : [] };
    if (md) for (const k of Object.keys(im)) {
      const edge = md.probs[k] - im[k];
      if (edge >= 0.05) value.push({ market: k, model_p: md.probs[k], implied_p: im[k], odds: odds[k], edge: r2(edge, 3), ev: r2(md.probs[k] * odds[k] - 1, 3) });
    }
    value.sort((x, y) => y.edge - x.edge); value = value.slice(0, 2);
  }
  let pick = null;
  if (md) {
    const cand = value[0]?.market ?? ['1X', 'O1.5', 'X2', 'BTTS_Y', 'O2.5', 'U2.5'].sort((x, y) => md.probs[y] - md.probs[x])[0];
    const pp = md.probs[cand];
    const stars = Math.max(1, Math.min(5, Math.round((pp - 0.45) * 10 + (value.length ? 2 : 0) - (quality === 'low' ? 2 : 0))));
    const LBL = { '1': 'MS 1', X: 'MS X', '2': 'MS 2', '1X': 'ÇŞ 1X', X2: 'ÇŞ X2', '12': 'ÇŞ 12', 'O1.5': '1.5 Üst', 'U1.5': '1.5 Alt', 'O2.5': '2.5 Üst', 'U2.5': '2.5 Alt', 'O3.5': '3.5 Üst', 'U3.5': '3.5 Alt', BTTS_Y: 'KG Var', BTTS_N: 'KG Yok' };
    pick = { market: cand, label: LBL[cand], p: pp, odds: odds?.[cand] ?? null, stars, is_value: value.some((v) => v.market === cand) };
  }
  const f = [...flags];
  if (!odds) f.push('Oran yok');
  if (quality === 'low') f.push('Düşük veri');
  const t = `${date}T18:31:00+03:00`;
  const cs = md ? [
    { source: 'forebet', picks: { '1X2': p['1'] > p['2'] ? '1' : '2', OU25: p['O2.5'] > 0.5 ? 'O2.5' : 'U2.5', BTTS: p.BTTS_Y > 0.5 ? 'BTTS_Y' : 'BTTS_N' }, probs: { '1': r2(p['1'] + 0.03), X: r2(p.X - 0.02), '2': r2(p['2'] - 0.01) }, fetched_at: t },
    { source: 'sportytrader', picks: { '1X2': p['1'] > p['2'] ? '1' : 'X', OU25: 'O2.5', BTTS: 'BTTS_Y' }, probs: null, fetched_at: t },
    { source: 'freesupertips', picks: { '1X2': p['1'] > p['2'] ? '1' : '2', BTTS: p.BTTS_Y > 0.48 ? 'BTTS_Y' : 'BTTS_N' }, probs: null, fetched_at: t },
  ] : [];
  const agreeB = Math.max(1, Math.min(5, Math.round(p.BTTS_Y * 8 - 1)));
  const SUF = { 1: "'i", 2: "'si", 3: "'ü", 4: "'ü", 5: "'i" };
  return {
    id: `${lg}-${date.replace(/-/g, '')}-${slug(h)}-${slug(a)}`,
    code, mbs, league: lg, league_name: LN[lg].name, league_priority: LN[lg].priority,
    kickoff, home: { name: h }, away: { name: a },
    status: finished ? 'finished' : 'scheduled',
    result: finished ? { ft: finished.ft, ht: finished.ht } : null,
    odds: odds ? Object.fromEntries(Object.entries(odds).filter(([k]) => ['1', 'X', '2', 'O2.5', 'U2.5', 'BTTS_Y', 'BTTS_N', 'O1.5', 'U1.5', 'O3.5', 'U3.5'].includes(k))) : null,
    odds_history: history, market, model: md,
    stats: lowStats ? { home: { ...teamStats(1.1), xg_avg: null, xga_avg: null, n: 4 }, away: { ...teamStats(1.0), xg_avg: null, xga_avg: null, n: 4 }, h2h: [] }
      : { home: teamStats(1.4), away: teamStats(1.1), h2h: [
        { date: '2026-03-01', home: a, away: h, score: '1-1' }, { date: '2025-10-19', home: h, away: a, score: '2-0' }, { date: '2025-02-23', home: a, away: h, score: '3-2' },
      ] },
    squad: noSquad ? null : {
      home: { missing: [{ name: 'Örnek Oyuncu A', reason: 'sakat', key: true }, { name: 'Örnek Oyuncu B', reason: 'şüpheli', key: false }], rotation_risk: lg === 'UCL', coach_change: false, adjustment: -0.04 },
      away: { missing: [{ name: 'Örnek Oyuncu C', reason: 'cezalı', key: false }], rotation_risk: false, coach_change: false, adjustment: 0.0 },
      source: 'flashscore', fetched_at: t,
    },
    consensus: md ? { sources: cs, summary: [{ market: 'BTTS_Y', agree: agreeB, total: 5, text: `5 kaynaktan ${agreeB}${SUF[agreeB]} KG Var diyor` }] } : null,
    value, ...(value.length ? {} : { value_note: 'Değer yok' }),
    pick,
    comment: md ? `ÖRNEK VERİ. ${h} iç sahada son maçlarında üretken; model ev sahibi için ${(md.lambda_home).toFixed(2)}, ${a} için ${(md.lambda_away).toFixed(2)} gol beklentisi hesaplıyor. Piyasa ile model arasındaki en büyük fark ${value[0] ? value[0].market + ' marketinde' : 'anlamlı düzeyde değil'}. Kadro eksikleri λ değerine küçük bir düzeltme olarak yansıtıldı. Bu bir olasılık tahminidir; sürpriz her zaman mümkündür.` : null,
    comment_source: md ? 'kural' : null,
    flags: f,
    provenance: {
      ...(odds ? { odds: { source: 'nesine', t } } : {}),
      stats: { source: 'football-data.co.uk', t: `${date}T08:31:00+03:00` },
      ...(noSquad ? {} : { squad: { source: 'flashscore', t } }),
    },
  };
}

const D = '2026-11-05', D0 = '2026-11-04';
const sources = (date) => [
  { id: 'nesine', name: 'Nesine bülten', status: 'ok', fetched_at: `${date}T18:31:00+03:00`, note: null },
  { id: 'iddaa', name: 'iddaa.com', status: 'partial', fetched_at: `${date}T18:31:20+03:00`, note: 'Bazı maçlarda KG oranı yok' },
  { id: 'football-data', name: 'football-data.co.uk', status: 'ok', fetched_at: `${date}T08:31:00+03:00`, note: null },
  { id: 'flashscore', name: 'Flashscore kadro', status: 'ok', fetched_at: `${date}T18:32:00+03:00`, note: null },
  { id: 'forebet', name: 'Forebet', status: 'ok', fetched_at: `${date}T18:32:30+03:00`, note: null },
  { id: 'sportytrader', name: 'SportyTrader', status: 'ok', fetched_at: `${date}T18:32:40+03:00`, note: null },
  { id: 'freesupertips', name: 'FreeSuperTips', status: 'missing', fetched_at: null, note: 'Zaman aşımı (örnek)' },
  { id: 'understat', name: 'Understat xG', status: 'ok', fetched_at: `${date}T08:33:00+03:00`, note: null },
];

const today = [
  { lg: 'TR1', h: 'Galatasaray', a: 'Fenerbahçe', time: '20:00', lh: 1.62, la: 1.08, code: '1234', mbs: 1, alarm: true, boost: 'BTTS_Y' },
  { lg: 'TR1', h: 'Trabzonspor', a: 'Başakşehir', time: '17:00', lh: 1.45, la: 1.05, code: '1235', mbs: 1 },
  { lg: 'TR1', h: 'Samsunspor', a: 'Kasımpaşa', time: '14:30', lh: 1.3, la: 1.2, code: '1236', mbs: 2, finished: { ft: [2, 1], ht: [1, 0] } },
  { lg: 'TR2', h: 'Erzurumspor', a: 'Bandırmaspor', time: '13:30', lh: 1.25, la: 0.95, code: '1240', mbs: 3, noOdds: true, noSquad: true, quality: 'low', lowStats: true },
  { lg: 'TR2', h: 'Iğdır FK', a: 'Ankara Keçiörengücü', time: '16:00', lh: 1.1, la: 1.0, code: null, mbs: null, noModel: true, noOdds: true, noSquad: true, lowStats: true, flags: ['Düşük veri'] },
  { lg: 'UCL', h: 'Real Madrid', a: 'Liverpool', time: '23:00', lh: 1.55, la: 1.45, code: '1301', mbs: 1, boost: ['O2.5', 'BTTS_Y'] },
  { lg: 'UCL', h: 'Bayern München', a: 'Paris Saint-Germain', time: '23:00', lh: 1.75, la: 1.35, code: '1302', mbs: 1 },
  { lg: 'UCL', h: 'Inter', a: 'Benfica', time: '23:00', lh: 1.6, la: 0.95, code: '1303', mbs: 1, noSquad: true },
  { lg: 'UCL', h: 'Club Brugge', a: 'Galatasaray', time: '20:45', lh: 1.35, la: 1.25, code: '1300', mbs: 1 },
  { lg: 'ENG1', h: 'Arsenal', a: 'Chelsea', time: '22:00', lh: 1.7, la: 1.1, code: '1401', mbs: 1, boost: '1' },
  { lg: 'ENG1', h: 'Brentford', a: 'Everton', time: '22:00', lh: 1.4, la: 1.15, code: '1402', mbs: 2, noOdds: true },
  { lg: 'ESP1', h: 'Real Betis', a: 'Sevilla', time: '22:00', lh: 1.4, la: 1.1, code: '1501', mbs: 1, boost: 'U2.5' },
];
const yesterday = [
  { lg: 'TR1', h: 'Beşiktaş', a: 'Göztepe', time: '19:00', lh: 1.7, la: 0.9, code: '1101', finished: { ft: [3, 1], ht: [1, 1] } },
  { lg: 'ENG1', h: 'Manchester City', a: 'Tottenham', time: '22:00', lh: 2.0, la: 1.0, code: '1102', finished: { ft: [1, 1], ht: [0, 1] } },
  { lg: 'ESP1', h: 'Barcelona', a: 'Villarreal', time: '23:00', lh: 2.1, la: 1.05, code: '1103', finished: { ft: [2, 0], ht: [1, 0] } },
];

function day(date, specs, label) {
  return { schema_version: 1, date, generated_at: `${date}T18:33:05+03:00`, run_label: label, sources: sources(date), leagues: LEAGUES, matches: specs.map((s) => match(date, s)) };
}
const write = (f, o) => { fs.writeFileSync(path.join(out, f), JSON.stringify(o, null, 2) + '\n'); console.log('yazıldı sample-data/' + f); };

const d1 = day(D, today, '18:30');
write(`${D}.json`, d1);
write('latest.json', d1);
write(`${D0}.json`, day(D0, yesterday, '18:30'));
write('index.json', { dates: [D, D0], latest: D });
write('status.json', { generated_at: `${D}T18:33:05+03:00`, sources: sources(D) });

// Karne — uydurma
let bal = 100; const bankroll = [];
for (let i = 0; i < 30; i++) {
  const dt = new Date(Date.UTC(2026, 9, 7 + i)); bal += (rnd() - 0.46) * 3.2;
  bankroll.push({ date: dt.toISOString().slice(0, 10), balance: r2(bal, 1) });
}
write('scorecard.json', {
  generated_at: `${D}T18:33:05+03:00`,
  overall: { n: 120, hit_rate: 0.54, brier_1x2: 0.198, roi: 0.031, staked: 120, profit: 3.7 },
  last30: { n: 41, hit_rate: 0.56, brier_1x2: 0.193, roi: r2((bal - 100) / 41, 3), staked: 41, profit: r2(bal - 100, 1) },
  by_league: [
    { league: 'TR1', name: 'Süper Lig', n: 40, hit_rate: 0.55, roi: 0.02 },
    { league: 'TR2', name: '1. Lig', n: 18, hit_rate: 0.47, roi: -0.06 },
    { league: 'UCL', name: 'Şampiyonlar Ligi', n: 16, hit_rate: 0.56, roi: 0.05 },
    { league: 'ENG1', name: 'Premier Lig', n: 26, hit_rate: 0.58, roi: 0.07 },
    { league: 'ESP1', name: 'La Liga', n: 20, hit_rate: 0.5, roi: -0.01 },
  ],
  by_market: [
    { market: 'O2.5', label: '2.5 Üst', n: 30, hit_rate: 0.6, roi: 0.08, trust: 1.0 },
    { market: 'BTTS_Y', label: 'KG Var', n: 24, hit_rate: 0.54, roi: 0.01, trust: 1.0 },
    { market: '1X', label: 'ÇŞ 1X', n: 28, hit_rate: 0.71, roi: -0.02, trust: 0.9 },
    { market: '1', label: 'MS 1', n: 22, hit_rate: 0.45, roi: -0.09, trust: 0.75 },
    { market: 'U2.5', label: '2.5 Alt', n: 16, hit_rate: 0.56, roi: 0.04, trust: 1.0 },
  ],
  calibration: [
    { bin: '0.3-0.4', predicted: 0.36, observed: 0.31, n: 12 }, { bin: '0.4-0.5', predicted: 0.46, observed: 0.44, n: 28 },
    { bin: '0.5-0.6', predicted: 0.55, observed: 0.53, n: 44 }, { bin: '0.6-0.7', predicted: 0.65, observed: 0.68, n: 26 },
    { bin: '0.7-0.8', predicted: 0.74, observed: 0.70, n: 10 },
  ],
  bankroll,
  recent: [
    { date: D0, match: 'Beşiktaş - Göztepe', pick: '2.5 Üst', odds: 1.72, won: true, score: '3-1' },
    { date: D0, match: 'Manchester City - Tottenham', pick: 'MS 1', odds: 1.55, won: false, score: '1-1' },
    { date: D0, match: 'Barcelona - Villarreal', pick: 'ÇŞ 1X', odds: 1.18, won: true, score: '2-0' },
    { date: '2026-11-03', match: 'Konyaspor - Alanyaspor', pick: 'KG Var', odds: 1.80, won: true, score: '1-2' },
    { date: '2026-11-03', match: 'Getafe - Valencia', pick: '2.5 Alt', odds: 1.62, won: false, score: '2-2' },
  ],
});
write('backtest.json', {
  generated_at: '2026-11-01T03:10:00+03:00',
  seasons: ['2024-25', '2025-26'],
  leagues: ['TR1', 'ENG1', 'ESP1'],
  summary: { n: 2140, model_brier: 0.201, market_brier: 0.197, model_logloss: 0.992, market_logloss: 0.981, roi_value_bets: 0.018, n_value_bets: 412 },
  by_league: [
    { league: 'TR1', name: 'Süper Lig', n: 612, model_brier: 0.205, market_brier: 0.207, model_logloss: 1.004, market_logloss: 1.009, roi_value_bets: 0.041, n_value_bets: 151 },
    { league: 'ENG1', name: 'Premier Lig', n: 760, model_brier: 0.198, market_brier: 0.192, model_logloss: 0.981, market_logloss: 0.968, roi_value_bets: -0.012, n_value_bets: 128 },
    { league: 'ESP1', name: 'La Liga', n: 768, model_brier: 0.200, market_brier: 0.195, model_logloss: 0.990, market_logloss: 0.974, roi_value_bets: 0.022, n_value_bets: 133 },
  ],
});
fs.writeFileSync(path.join(out, 'README.txt'), 'ÖRNEK VERİ — tüm sayılar uydurmadır. Yalnızca npm run dev:sample ile geliştirme içindir; gerçek sitede kullanılmaz.\nYeniden üretmek için: node scripts/make-sample-data.mjs\n');
