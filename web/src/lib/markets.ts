import type { HtFtKey, MarketKey } from './types';

export const MARKET_LABELS: Record<MarketKey, string> = {
  '1': 'MS 1',
  X: 'MS X',
  '2': 'MS 2',
  '1X': 'ÇŞ 1X',
  X2: 'ÇŞ X2',
  '12': 'ÇŞ 12',
  'O1.5': '1.5 Üst',
  'U1.5': '1.5 Alt',
  'O2.5': '2.5 Üst',
  'U2.5': '2.5 Alt',
  'O3.5': '3.5 Üst',
  'U3.5': '3.5 Alt',
  BTTS_Y: 'KG Var',
  BTTS_N: 'KG Yok',
};

export const MARKET_ORDER: MarketKey[] = [
  '1', 'X', '2', '1X', 'X2', '12',
  'O1.5', 'U1.5', 'O2.5', 'U2.5', 'O3.5', 'U3.5',
  'BTTS_Y', 'BTTS_N',
];

export const MARKET_GROUPS: { title: string; keys: MarketKey[] }[] = [
  { title: 'Maç sonucu', keys: ['1', 'X', '2'] },
  { title: 'Çifte şans', keys: ['1X', 'X2', '12'] },
  { title: 'Alt / Üst', keys: ['O1.5', 'U1.5', 'O2.5', 'U2.5', 'O3.5', 'U3.5'] },
  { title: 'Karşılıklı gol', keys: ['BTTS_Y', 'BTTS_N'] },
];

export const HTFT_KEYS: HtFtKey[] = ['1/1', '1/X', '1/2', 'X/1', 'X/X', 'X/2', '2/1', '2/X', '2/2'];

export function marketLabel(key: string): string {
  return (MARKET_LABELS as Record<string, string>)[key] ?? key;
}

/** Skor (ev, dep) verilen market için kazanır mı? Skor matrisi ile tam olasılık hesabında kullanılır. */
export function marketWins(key: MarketKey, h: number, a: number): boolean {
  const t = h + a;
  switch (key) {
    case '1': return h > a;
    case 'X': return h === a;
    case '2': return h < a;
    case '1X': return h >= a;
    case 'X2': return h <= a;
    case '12': return h !== a;
    case 'O1.5': return t > 1.5;
    case 'U1.5': return t < 1.5;
    case 'O2.5': return t > 2.5;
    case 'U2.5': return t < 2.5;
    case 'O3.5': return t > 3.5;
    case 'U3.5': return t < 3.5;
    case 'BTTS_Y': return h > 0 && a > 0;
    case 'BTTS_N': return h === 0 || a === 0;
  }
}

export function isMarketKey(k: string): k is MarketKey {
  return (MARKET_ORDER as string[]).includes(k);
}
