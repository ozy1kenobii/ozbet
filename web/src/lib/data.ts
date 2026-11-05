import { useEffect, useState } from 'react';
import type { Backtest, DayFile, IndexFile, Scorecard, Source, StatusFile } from './types';

/** Tüm veri yolları base'e göre görelidir: data/*.json */
const BASE = 'data/';

export type Loadable<T> =
  | { state: 'loading' }
  | { state: 'empty' }            // dosya yok / 404 / bozuk
  | { state: 'ready'; data: T };

const cache = new Map<string, Promise<unknown | null>>();

async function fetchJson<T>(file: string): Promise<T | null> {
  try {
    const res = await fetch(BASE + file, { cache: 'no-cache' });
    if (!res.ok) return null;
    const ct = res.headers.get('content-type') ?? '';
    // SPA fallback'in HTML döndürmesine karşı koruma
    if (ct.includes('text/html')) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function loadJson<T>(file: string): Promise<T | null> {
  let p = cache.get(file);
  if (!p) {
    p = fetchJson<T>(file);
    cache.set(file, p);
    // Başarısız yüklemeyi önbellekte tutma, bir sonraki ziyarette tekrar dene
    p.then((v) => { if (v == null) cache.delete(file); });
  }
  return p as Promise<T | null>;
}

export function useJson<T>(file: string | null): Loadable<T> {
  const [s, setS] = useState<Loadable<T>>({ state: 'loading' });
  useEffect(() => {
    let alive = true;
    if (!file) { setS({ state: 'empty' }); return; }
    setS({ state: 'loading' });
    loadJson<T>(file).then((d) => { if (alive) setS(d == null ? { state: 'empty' } : { state: 'ready', data: d }); });
    return () => { alive = false; };
  }, [file]);
  return s;
}

export const useIndex = () => useJson<IndexFile>('index.json');
export const useScorecard = () => useJson<Scorecard>('scorecard.json');
export const useBacktest = () => useJson<Backtest>('backtest.json');
export const useStatus = () => useJson<StatusFile>('status.json');

/** Tarih verilirse gün dosyası, yoksa latest.json */
export function useDay(date: string | null | undefined): Loadable<DayFile> {
  return useJson<DayFile>(date ? `${date}.json` : 'latest.json');
}

export function statusSources(s: StatusFile | undefined): Source[] {
  if (!s) return [];
  return Array.isArray(s) ? s : s.sources ?? [];
}

export function useOnline(): boolean {
  const [on, setOn] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  useEffect(() => {
    const up = () => setOn(true);
    const down = () => setOn(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => { window.removeEventListener('online', up); window.removeEventListener('offline', down); };
  }, []);
  return on;
}
