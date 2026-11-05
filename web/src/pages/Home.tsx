import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { statusSources, useDay, useIndex, useStatus } from '../lib/data';
import { fmtDay, fmtTime } from '../lib/format';
import type { DayFile, Match, Source } from '../lib/types';
import { MatchCard } from '../components/MatchCard';
import { Dot, Empty, Loading } from '../components/ui';
import { readLS, writeLS } from '../lib/storage';

const FILTER_KEY = 'ozbet-filtre-v1';
interface Filters { leagues: string[]; strong: boolean; value: boolean }

export default function Home() {
  const { date: routeDate } = useParams();
  const nav = useNavigate();
  const idx = useIndex();
  const dates = idx.state === 'ready' ? [...idx.data.dates].sort().reverse() : [];
  const latest = idx.state === 'ready' ? idx.data.latest : null;
  const date = routeDate ?? null;
  const day = useDay(date);

  const shownDate = day.state === 'ready' ? day.data.date : date ?? latest ?? '';
  const pos = dates.indexOf(shownDate);
  const older = pos >= 0 && pos < dates.length - 1 ? dates[pos + 1] : null;
  const newer = pos > 0 ? dates[pos - 1] : null;
  const go = (d: string | null) => d && nav(d === latest ? '/' : `/gun/${d}`);

  return (
    <div>
      <div className="flex items-center gap-2">
        <button className="tap btn-ghost rounded-md grid place-items-center disabled:opacity-35" disabled={!older} onClick={() => go(older)} aria-label="Önceki gün">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
        </button>
        <div className="flex-1 min-w-0">
          <label htmlFor="gun" className="sr-only">Gün seç</label>
          {dates.length > 0 ? (
            <select id="gun" value={shownDate} onChange={(e) => go(e.target.value)}
              className="w-full min-h-[44px] rounded-md border border-line bg-surface px-3 display text-xl font-semibold appearance-none text-center">
              {!dates.includes(shownDate) && shownDate && <option value={shownDate}>{fmtDay(shownDate)}</option>}
              {dates.map((d) => <option key={d} value={d}>{fmtDay(d)}{d === latest ? ' (son)' : ''}</option>)}
            </select>
          ) : (
            <div className="min-h-[44px] grid place-items-center display text-xl font-semibold">{shownDate ? fmtDay(shownDate) : 'Bülten'}</div>
          )}
        </div>
        <button className="tap btn-ghost rounded-md grid place-items-center disabled:opacity-35" disabled={!newer} onClick={() => go(newer)} aria-label="Sonraki gün">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M9 5l7 7-7 7" /></svg>
        </button>
      </div>

      {day.state === 'loading' && <div className="mt-4"><Loading /></div>}
      {day.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {day.state === 'ready' && <DayView day={day.data} />}
    </div>
  );
}

function DayView({ day }: { day: DayFile }) {
  const [f, setF] = useState<Filters>(() => {
    const v = readLS<Filters>(FILTER_KEY, { leagues: [], strong: false, value: false });
    return { leagues: Array.isArray(v.leagues) ? v.leagues : [], strong: !!v.strong, value: !!v.value };
  });
  const upd = (n: Filters) => { setF(n); writeLS(FILTER_KEY, n); };

  const matches = Array.isArray(day.matches) ? day.matches : [];
  const leagues = useMemo(() => {
    const map = new Map<string, { id: string; name: string; priority: number; n: number }>();
    for (const l of day.leagues ?? []) map.set(l.id, { id: l.id, name: l.name, priority: l.priority, n: 0 });
    for (const m of matches) {
      const e = map.get(m.league) ?? { id: m.league, name: m.league_name, priority: m.league_priority ?? 99, n: 0 };
      e.n++; map.set(m.league, e);
    }
    return [...map.values()].filter((l) => l.n > 0).sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name, 'tr'));
  }, [day, matches]);

  const activeLeagues = f.leagues.filter((id) => leagues.some((l) => l.id === id));
  const filtered = matches.filter((m) =>
    (!activeLeagues.length || activeLeagues.includes(m.league)) &&
    (!f.strong || (m.pick?.stars ?? 0) >= 4) &&
    (!f.value || (m.value?.length ?? 0) > 0));

  const groups = leagues
    .map((l) => ({ l, ms: filtered.filter((m) => m.league === l.id).sort(byKickoff) }))
    .filter((g) => g.ms.length);

  const toggleLeague = (id: string) =>
    upd({ ...f, leagues: activeLeagues.includes(id) ? activeLeagues.filter((x) => x !== id) : [...activeLeagues, id] });

  return (
    <div>
      <SourceSummary day={day} />

      <div className="mt-4 -mx-4 px-4 flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Lig filtresi">
        <button className="chip shrink-0" aria-pressed={!activeLeagues.length} onClick={() => upd({ ...f, leagues: [] })}>Tümü</button>
        {leagues.map((l) => (
          <button key={l.id} className="chip shrink-0" aria-pressed={activeLeagues.includes(l.id)} onClick={() => toggleLeague(l.id)}>
            {l.name} <span className="opacity-70 num">{l.n}</span>
          </button>
        ))}
      </div>
      <div className="mt-2 flex gap-2 flex-wrap" role="group" aria-label="Ek filtreler">
        <button className="chip" aria-pressed={f.strong} onClick={() => upd({ ...f, strong: !f.strong })}>Sadece yüksek güven</button>
        <button className="chip" aria-pressed={f.value} onClick={() => upd({ ...f, value: !f.value })}>Sadece değerli</button>
      </div>

      <p className="mt-3 text-[13px] text-muted">
        {filtered.length} / {matches.length} maç · {day.run_label} çalıştırması, güncelleme {fmtTime(day.generated_at)}
      </p>

      {!matches.length && <div className="mt-4"><Empty title="Bu gün için maç yok" /></div>}
      {matches.length > 0 && !groups.length && (
        <div className="mt-4"><Empty title="Filtreye uyan maç yok">Filtreleri gevşetin ya da “Tümü”ne dokunun.</Empty></div>
      )}

      {groups.map(({ l, ms }) => (
        <section key={l.id} className="mt-6" aria-labelledby={`lig-${l.id}`}>
          <h2 id={`lig-${l.id}`} className="display text-[22px] font-semibold leading-none mb-2.5 flex items-baseline gap-2">
            {l.name}<span className="text-sm font-medium text-muted num">{ms.length}</span>
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {ms.map((m) => <MatchCard key={m.id} m={m} date={day.date} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

const byKickoff = (a: Match, b: Match) => a.kickoff.localeCompare(b.kickoff) || a.home.name.localeCompare(b.home.name, 'tr');

function SourceSummary({ day }: { day: DayFile }) {
  const st = useStatus();
  const [open, setOpen] = useState(false);
  const fromStatus = st.state === 'ready' ? statusSources(st.data) : [];
  const sources: Source[] = fromStatus.length ? fromStatus : day.sources ?? [];
  if (!sources.length) return null;
  const ok = sources.filter((s) => s.status === 'ok').length;
  const partial = sources.filter((s) => s.status === 'partial').length;
  const missing = sources.filter((s) => s.status === 'missing').length;
  return (
    <div className="mt-3 panel">
      <button className="w-full min-h-[44px] px-3.5 flex items-center gap-3 text-left text-sm" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="flex items-center gap-1.5"><Dot s="ok" /> <b className="num">{ok}</b> çalışıyor</span>
        {partial > 0 && <span className="flex items-center gap-1.5"><Dot s="partial" /> <b className="num">{partial}</b> kısmi</span>}
        <span className="flex items-center gap-1.5"><Dot s="missing" /> <b className="num">{missing}</b> eksik</span>
        <span className="ml-auto text-muted">{open ? 'Gizle' : 'Kaynaklar'}</span>
      </button>
      {open && (
        <ul className="border-t border-line px-3.5 py-2 text-sm space-y-1.5">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <Dot s={s.status} /><span className="font-medium">{s.name}</span>
              <span className="ml-auto text-[12px] text-muted num">{s.fetched_at ? fmtTime(s.fetched_at) : '–'}</span>
            </li>
          ))}
          <li><Link to="/kaynaklar" className="tap inline-flex items-center text-accent font-semibold">Tüm kaynak ayrıntıları</Link></li>
        </ul>
      )}
    </div>
  );
}
