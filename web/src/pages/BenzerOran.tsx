import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDay } from '../lib/data';
import { fmtDay, fmtTime, pct } from '../lib/format';
import type { Match } from '../lib/types';
import { readLS, writeLS } from '../lib/storage';
import { Chevron, Empty, Loading } from '../components/ui';
import { HONESTY, IddaaArchiveStrip, OddsArchiveDetail, RAW_ODDS_NOTE, scopeText } from '../components/OddsArchive';
import { matchHref } from '../components/MatchCard';

const SCOPE_KEY = 'ozbet-kapsam';   // Bülten sayfasıyla ortak
type Scope = 'analyzed' | 'all';
const isAnalyzed = (m: Match) => !!m.model && m.model.source !== 'piyasa';

export default function BenzerOran() {
  const day = useDay(null);
  const [scope, setScopeState] = useState<Scope>(() => (readLS<string>(SCOPE_KEY, 'analyzed') === 'all' ? 'all' : 'analyzed'));
  const setScope = (s: Scope) => { setScopeState(s); writeLS(SCOPE_KEY, s); };
  const [league, setLeague] = useState<string>('');
  const [open, setOpen] = useState<string | null>(null);

  const all = useMemo(() => (day.state === 'ready' ? day.data.matches.filter((m) => m.market?.implied?.['1'] != null) : []), [day]);
  const scoped = scope === 'analyzed' ? all.filter(isAnalyzed) : all;
  const leagues = useMemo(() => {
    const seen = new Map<string, string>();
    for (const m of scoped) if (!seen.has(m.league)) seen.set(m.league, m.league === 'OTHER' ? 'Diğer ligler' : m.league_name);
    return [...seen.entries()];
  }, [scoped]);
  const list = (league ? scoped.filter((m) => m.league === league) : scoped).slice().sort((a, b) => a.kickoff.localeCompare(b.kickoff));

  return (
    <div>
      <h1 className="display text-2xl font-bold">Benzer Oran</h1>
      <ul className="mt-2 rounded-md border border-line bg-surface px-3 py-2 text-[13px] text-muted space-y-0.5">
        {HONESTY.map((t) => <li key={t}>{t}</li>)}
      </ul>
      {day.state === 'loading' && <div className="mt-4"><Loading /></div>}
      {day.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {day.state === 'ready' && (
        <>
          <p className="mt-2 text-[13px] text-muted">{fmtDay(day.data.date)} · {list.length} maç</p>
          <div className="mt-2"><IddaaArchiveStrip info={day.data.iddaa_archive} /></div>
          <div className="mt-3 seg w-full flex" role="tablist" aria-label="Maç kapsamı">
            {([['analyzed', 'Analizli', all.filter(isAnalyzed).length], ['all', 'Tüm bülten', all.length]] as const).map(([k, t, n]) => (
              <button key={k} className="flex-1" role="tab" aria-selected={scope === k} aria-pressed={scope === k} onClick={() => { setScope(k); setLeague(''); }}>
                {t} <span className="num">({n})</span>
              </button>
            ))}
          </div>
          <label className="sr-only" htmlFor="lig">Lig</label>
          <select id="lig" value={league} onChange={(e) => setLeague(e.target.value)}
            className="mt-2 w-full min-h-[44px] rounded-md border border-line bg-surface px-3 text-[15px]">
            <option value="">Tüm ligler</option>
            {leagues.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          {list.length === 0 && <p className="mt-4 text-sm text-muted">Bu seçimde oranlı maç yok.</p>}
          <ul className="mt-3 space-y-2">
            {list.map((m) => <Row key={m.id} m={m} date={day.data.date} open={open === m.id} toggle={() => setOpen(open === m.id ? null : m.id)} />)}
          </ul>
          <p className="mt-4 text-[12px] text-muted">{RAW_ODDS_NOTE}</p>
        </>
      )}
    </div>
  );
}

function Row({ m, date, open, toggle }: { m: Match; date: string; open: boolean; toggle: () => void }) {
  const imp = m.market?.implied ?? {};
  const a = m.odds_analysis;
  const ok = a && a.status !== 'az_ornek' && a.markets;
  const obs = (k: string) => a?.markets?.find((x) => x.market === k)?.observed;
  return (
    <li className="panel">
      <button className="w-full text-left px-3 py-2.5" onClick={toggle} aria-expanded={open}>
        <div className="flex items-center gap-2">
          <span className="num text-[13px] text-muted w-11 shrink-0">{fmtTime(m.kickoff)}</span>
          <span className="flex-1 min-w-0 truncate font-semibold text-[15px]">{m.home.name} – {m.away.name}</span>
          <Chevron open={open} />
        </div>
        <div className="mt-1 grid grid-cols-[44px_1fr] gap-x-2 text-[12px] num">
          <span className="text-muted">Piyasa</span>
          <span>1 {pct(imp['1'], 0)} · X {pct(imp['X'], 0)} · 2 {pct(imp['2'], 0)}</span>
          <span className="text-muted">Arşiv</span>
          {ok ? <span>1 {pct(obs('1'), 0)} · X {pct(obs('X'), 0)} · 2 {pct(obs('2'), 0)} <span className="text-muted">· n={a!.n}</span></span>
              : <span className="text-muted">yetersiz örneklem (n={a?.n ?? 0})</span>}
        </div>
      </button>
      {open && (
        <div className="border-t border-line px-3 py-3">
          <div className="mb-2 flex items-center justify-between text-[12px]">
            <span className="text-muted truncate">{m.league === 'OTHER' ? 'Diğer' : m.league_name}</span>
            <Link to={matchHref(date, m)} className="text-accent shrink-0">Maç detayı</Link>
          </div>
          <OddsArchiveDetail a={a} />
          {m.odds_analysis_iddaa && m.odds_analysis_iddaa.status !== 'az_ornek' && (
            <div className="mt-4">
              <div className="text-[13px] font-semibold">iddaa arşivi</div>
              <p className="text-[12px] text-muted num">{scopeText(m.odds_analysis_iddaa)}</p>
              <OddsArchiveDetail a={m.odds_analysis_iddaa} source="iddaa arşivi (kapanış, yoksa açılış)" />
            </div>
          )}
        </div>
      )}
    </li>
  );
}
