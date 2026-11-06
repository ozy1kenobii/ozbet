import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { DayFile, Match } from '../lib/types';
import { allProbs, marketLabel, setMarketLabels } from '../lib/markets';
import { fmtTime, odd, pct } from '../lib/format';
import { readLS, writeLS } from '../lib/storage';
import { matchHref } from './MatchCard';
import { Chevron } from './ui';

/** Sık oynanan marketler — kısa liste; tam liste "Tümü" ile açılır. */
const QUICK = ['O2.5', 'U2.5', 'BTTS_Y', 'HT_O0.5', 'O1.5', '1', '2', 'HCP-1_1', 'H_O1.5', 'A_O0.5',
  'C_O9.5', 'C_U9.5', 'K_O4.5', 'K_U3.5', 'HT_X', '1&O2.5'];
const LS = 'ozbet-tarayici-v1';

export function MarketScanner({ day }: { day: DayFile }) {
  setMarketLabels(day.market_labels);
  const saved = readLS<{ mk: string; open: boolean; odds: boolean }>(LS, { mk: 'O2.5', open: false, odds: true });
  const [mk, setMk] = useState(saved.mk);
  const [open, setOpen] = useState(saved.open);
  const [onlyOdds, setOnlyOdds] = useState(saved.odds);
  const save = (p: Partial<typeof saved>) => writeLS(LS, { mk, open, odds: onlyOdds, ...p });

  const all = useMemo(() => {
    const keys = new Set<string>();
    for (const m of day.matches) for (const k of Object.keys(allProbs(m))) keys.add(k);
    const cats = day.market_categories ?? [];
    const ordered = cats.flatMap((c) => c.keys).filter((k) => keys.has(k));
    return ordered.length ? ordered : [...keys];
  }, [day]);

  const rows = useMemo(() => {
    const out: { m: Match; p: number; o?: number; imp?: number }[] = [];
    for (const m of day.matches) {
      if (m.status !== 'scheduled') continue;   // canlı/biten maçta maç öncesi olasılık yanıltır
      const p = allProbs(m)[mk];
      if (p == null) continue;
      const o = (m.odds as Record<string, number | undefined> | null)?.[mk];
      if (onlyOdds && o == null) continue;
      out.push({ m, p, o, imp: (m.market?.implied as Record<string, number | undefined> | undefined)?.[mk] });
    }
    return out.sort((a, b) => b.p - a.p).slice(0, 12);
  }, [day, mk, onlyOdds]);

  if (!all.length) return null;
  const quick = QUICK.filter((k) => all.includes(k));
  return (
    <section className="mt-6">
      <button className="flex w-full items-baseline gap-2 text-left" aria-expanded={open}
        onClick={() => { setOpen(!open); save({ open: !open }); }}>
        <h2 className="h-section">Market tarayıcı</h2>
        <span className="t-meta">bir market seç, en olası maçları gör</span>
        <span className="ml-auto self-center"><Chevron open={open} size={16} /></span>
      </button>
      {open && (
        <div className="mt-2">
          <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
            {quick.map((k) => (
              <button key={k} className="chip shrink-0" aria-pressed={k === mk} onClick={() => { setMk(k); save({ mk: k }); }}>{marketLabel(k)}</button>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <label className="text-sm">
              <span className="sr-only">Market</span>
              <select className="min-h-[40px] rounded-md border border-line bg-surface px-2 text-sm" value={mk}
                onChange={(e) => { setMk(e.target.value); save({ mk: e.target.value }); }}>
                {all.map((k) => <option key={k} value={k}>{marketLabel(k)}</option>)}
              </select>
            </label>
            <button className="chip" aria-pressed={onlyOdds} onClick={() => { setOnlyOdds(!onlyOdds); save({ odds: !onlyOdds }); }}>Sadece oranı olanlar</button>
          </div>
          {rows.length === 0 ? (
            <p className="mt-3 text-sm text-muted">Bu market için {onlyOdds ? 'oranı olan ' : ''}maç yok.</p>
          ) : (
            <div className="mt-2 panel px-2 py-1 overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>Maç</th><th className="text-right">Model</th><th className="text-right">Piyasa</th><th className="text-right">Oran</th></tr></thead>
                <tbody>
                  {rows.map(({ m, p, o, imp }) => (
                    <tr key={m.id}>
                      <td>
                        <Link to={matchHref(day.date, m)} className="font-medium hover:text-accent">{m.home.name} – {m.away.name}</Link>
                        <div className="t-micro text-muted num">{fmtTime(m.kickoff)} · {m.league_name}{m.code ? ` · ${m.code}` : ''}</div>
                      </td>
                      <td className="text-right font-semibold num">{pct(p, 0)}</td>
                      <td className="text-right text-muted num">{pct(imp, 0)}</td>
                      <td className="text-right num">{o != null ? odd(o) : '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-1 text-[12px] text-muted">Sıralama model olasılığına göredir; yüksek olasılık düşük oran demektir, tek başına değer göstergesi değildir.</p>
        </div>
      )}
    </section>
  );
}
