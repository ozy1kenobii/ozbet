import type { Match, Pick } from './types';
import { readLS, writeLS } from './storage';

/** Seçim oran bandı: bu aralığın dışındaki oranlar "Günün seçimleri"nde gösterilmez. */
export const BAND_MIN = 1.6;
export const BAND_MAX = 3.5;
export const MIN_ODDS_OPTIONS = [1.4, 1.6, 1.8, 2.0, 2.5] as const;

const MIN_ODDS_KEY = 'ozbet-min-oran';
export function loadMinOdds(): number {
  const v = Number(readLS<number>(MIN_ODDS_KEY, BAND_MIN));
  return (MIN_ODDS_OPTIONS as readonly number[]).includes(v) ? v : BAND_MIN;
}
export const saveMinOdds = (v: number) => writeLS(MIN_ODDS_KEY, v);

/** Beklenen değer (1 birim için): p·oran − 1. Eski gün dosyalarında alan yoksa hesaplanır. */
export function pickEv(p: Pick | null | undefined): number | null {
  if (!p) return null;
  if (p.ev != null && isFinite(p.ev)) return p.ev;
  if (p.odds == null || !isFinite(p.odds) || !isFinite(p.p)) return null;
  return p.p * p.odds - 1;
}

/** Adil oran: 1/p — modelin olasılığına göre marjsız oran. */
export function fairOdds(p: Pick | null | undefined): number | null {
  if (!p) return null;
  if (p.fair_odds != null && isFinite(p.fair_odds)) return p.fair_odds;
  return p.p > 0 ? 1 / p.p : null;
}

export const inBand = (odds: number | null | undefined, min = BAND_MIN, max = BAND_MAX) =>
  odds != null && odds >= min - 1e-9 && odds <= max + 1e-9;

/** Günün seçimleri sırası: önce oynanmamış maçlar, sonra beklenen değer (yüksekten düşüğe). */
export function byEv(a: Match, b: Match): number {
  const fa = a.status === 'finished' ? 1 : 0, fb = b.status === 'finished' ? 1 : 0;
  return fa - fb
    || (pickEv(b.pick) ?? -9) - (pickEv(a.pick) ?? -9)
    || (b.pick?.stars ?? 0) - (a.pick?.stars ?? 0)
    || a.kickoff.localeCompare(b.kickoff);
}

export const SHARP_SOURCE: Record<string, string> = { pinnacle: 'Pinnacle', betfair: 'Betfair', avg: 'büro ortalaması' };
export const SHARP_EXPLAIN =
  'iddaa oranı, uluslararası keskin piyasanın marjsız fiyatına göre yüksek görünüyor. Keskin piyasa genelde en isabetli fiyattır; fark gerçek bir avantaj olabilir, ama geç gelen bir haber ya da veri gecikmesi de olabilir. Bu bir hipotezdir, garanti değildir.';
