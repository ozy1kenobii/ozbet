import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { MarketKey, Match } from './types';
import { readLS, writeLS } from './storage';
import { allProbs, isMarketKey, marketLabel, marketWins } from './markets';

export interface Selection {
  key: string;              // matchId|market
  matchId: string;
  date: string;
  market: string;
  label: string;
  home: string;
  away: string;
  league: string;
  league_name: string;
  kickoff: string;
  p: number | null;         // model olasılığı
  odds: number | null;
  score_matrix: number[][] | null;
}

const KEY = 'ozbet-kupon-v1';

interface Ctx {
  items: Selection[];
  add: (m: Match, date: string, market: string) => void;
  remove: (key: string) => void;
  clear: () => void;
  has: (matchId: string, market: string) => boolean;
}

const CouponCtx = createContext<Ctx | null>(null);

export function CouponProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Selection[]>(() => {
    const v = readLS<Selection[]>(KEY, []);
    return Array.isArray(v) ? v.filter((x) => x && typeof x.key === 'string') : [];
  });
  useEffect(() => { writeLS(KEY, items); }, [items]);

  const add = useCallback((m: Match, date: string, market: string) => {
    const key = `${m.id}|${market}`;
    setItems((cur) => cur.some((x) => x.key === key) ? cur : [...cur, {
      key, matchId: m.id, date, market, label: marketLabel(market),
      home: m.home.name, away: m.away.name, league: m.league, league_name: m.league_name, kickoff: m.kickoff,
      p: allProbs(m)[market] ?? null,
      odds: m.odds?.[market] ?? null,
      score_matrix: m.model?.score_matrix ?? null,
    }]);
  }, []);
  const remove = useCallback((key: string) => setItems((cur) => cur.filter((x) => x.key !== key)), []);
  const clear = useCallback(() => setItems([]), []);
  const has = useCallback((id: string, mk: string) => items.some((x) => x.key === `${id}|${mk}`), [items]);

  const v = useMemo(() => ({ items, add, remove, clear, has }), [items, add, remove, clear, has]);
  return <CouponCtx.Provider value={v}>{children}</CouponCtx.Provider>;
}

export function useCoupon(): Ctx {
  const c = useContext(CouponCtx);
  if (!c) throw new Error('CouponProvider eksik');
  return c;
}

/** Skor matrisinden birden fazla marketin aynı anda tutma olasılığı (0..5 x 0..5; 5+ kuyruğu dahil değil). */
export function jointFromMatrix(matrix: number[][], markets: MarketKey[]): { p: number; covered: number } {
  let p = 0, covered = 0;
  for (let h = 0; h < matrix.length; h++) {
    const row = matrix[h] ?? [];
    for (let a = 0; a < row.length; a++) {
      const v = Number(row[a]) || 0;
      covered += v;
      if (markets.every((mk) => marketWins(mk, h, a))) p += v;
    }
  }
  return { p, covered };
}

export interface CouponAnalysis {
  groups: { matchId: string; title: string; items: Selection[]; p: number | null; method: 'tek' | 'matris' | 'carpim'; tail: number | null; contradictory: boolean }[];
  jointP: number | null;
  totalOdds: number | null;
  ev: number | null;
  missingOdds: Selection[];
  missingP: Selection[];
  correlated: boolean;
  crowded: { league: string; time: string; count: number }[];
}

export function analyze(items: Selection[]): CouponAnalysis {
  const byMatch = new Map<string, Selection[]>();
  for (const s of items) {
    const arr = byMatch.get(s.matchId) ?? [];
    arr.push(s);
    byMatch.set(s.matchId, arr);
  }
  const groups: CouponAnalysis['groups'] = [];
  let correlated = false;
  for (const [matchId, its] of byMatch) {
    const title = `${its[0].home} – ${its[0].away}`;
    if (its.length === 1) {
      groups.push({ matchId, title, items: its, p: its[0].p, method: 'tek', tail: null, contradictory: false });
      continue;
    }
    correlated = true;
    const mat = its.find((x) => x.score_matrix && x.score_matrix.length)?.score_matrix ?? null;
    if (mat && its.every((x) => isMarketKey(x.market))) {
      const { p, covered } = jointFromMatrix(mat, its.map((x) => x.market as MarketKey));
      groups.push({ matchId, title, items: its, p, method: 'matris', tail: Math.max(0, 1 - covered), contradictory: p <= 1e-9 });
    } else {
      const ps = its.map((x) => x.p);
      const p = ps.every((x) => x != null) ? (ps as number[]).reduce((a, b) => a * b, 1) : null;
      groups.push({ matchId, title, items: its, p, method: 'carpim', tail: null, contradictory: false });
    }
  }
  const gp = groups.map((g) => g.p);
  const jointP = items.length && gp.every((x) => x != null) ? (gp as number[]).reduce((a, b) => a * b, 1) : null;
  const missingOdds = items.filter((x) => x.odds == null);
  const missingP = items.filter((x) => x.p == null);
  const totalOdds = items.length && !missingOdds.length ? items.reduce((a, b) => a * (b.odds as number), 1) : null;
  const ev = jointP != null && totalOdds != null ? jointP * totalOdds - 1 : null;

  // Aynı lig + aynı başlama saati
  const slot = new Map<string, { league: string; time: string; ids: Set<string> }>();
  for (const s of items) {
    const k = `${s.league}|${s.kickoff}`;
    const e = slot.get(k) ?? { league: s.league_name || s.league, time: s.kickoff, ids: new Set<string>() };
    e.ids.add(s.matchId);
    slot.set(k, e);
  }
  const crowded = [...slot.values()].filter((e) => e.ids.size >= 3).map((e) => ({ league: e.league, time: e.time, count: e.ids.size }));

  return { groups, jointP, totalOdds, ev, missingOdds, missingP, correlated, crowded };
}
