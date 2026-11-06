import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { statusSources, useDay, useIndex, useStatus } from '../lib/data';
import { fmtDay, fmtTime, istHour, odd } from '../lib/format';
import type { DayFile, Match, Source } from '../lib/types';
import { HighlightCard, KickoffCell, MatchCard, matchHref } from '../components/MatchCard';
import { Chevron, Dot, Empty, Loading } from '../components/ui';
import { readLS, writeLS } from '../lib/storage';

const FILTER_KEY = 'ozbet-filtre-v2';
type TimeFilter = 'soon' | 'evening' | 'all';
interface Filters { time: TimeFilter; strong: boolean; value: boolean; open: Record<string, boolean> }
const DEFAULTS: Filters = { time: 'all', strong: false, value: false, open: {} };

function loadFilters(): Filters {
  const v = readLS<Partial<Filters>>(FILTER_KEY, DEFAULTS) ?? DEFAULTS;
  return {
    time: v.time === 'soon' || v.time === 'evening' ? v.time : 'all',
    strong: !!v.strong,
    value: !!v.value,
    open: v.open && typeof v.open === 'object' && !Array.isArray(v.open) ? v.open : {},
  };
}

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

/* ---------- yardımcılar ---------- */

const OTHER_ID = '__diger';
const isOther = (m: Match) => (m.league_priority ?? 99) >= 99 || m.league === 'OTHER';
const byKickoff = (a: Match, b: Match) => a.kickoff.localeCompare(b.kickoff) || a.home.name.localeCompare(b.home.name, 'tr');
const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLocaleLowerCase('tr').replace(/ı/g, 'i');

function timeOk(m: Match, t: TimeFilter, now: number): boolean {
  if (t === 'all') return true;
  if (m.status === 'finished') return false;
  if (t === 'soon') {
    if (m.status === 'live') return true;
    const k = Date.parse(m.kickoff);
    return isFinite(k) && k >= now - 5 * 60_000 && k <= now + 2 * 3600_000;
  }
  const h = istHour(m.kickoff);
  return h != null && h >= 18;
}

interface Group { id: string; name: string; priority: number; modeled: Match[]; plain: Match[]; total: number }

function DayView({ day }: { day: DayFile }) {
  const [f, setF] = useState<Filters>(loadFilters);
  const [q, setQ] = useState('');
  const upd = (n: Filters) => { setF(n); writeLS(FILTER_KEY, n); };
  const now = Date.now();

  const matches = useMemo(() => (Array.isArray(day.matches) ? day.matches : []), [day]);
  const qf = fold(q.trim());

  const filtered = matches.filter((m) =>
    timeOk(m, f.time, now) &&
    (!f.strong || (m.pick?.stars ?? 0) >= 4) &&
    (!f.value || (m.value?.length ?? 0) > 0) &&
    (!qf || fold(m.home.name).includes(qf) || fold(m.away.name).includes(qf)));

  const groups = useMemo(() => {
    const leagueMeta = new Map((day.leagues ?? []).map((l) => [l.id, l]));
    const map = new Map<string, Group>();
    for (const m of filtered) {
      const other = isOther(m);
      const id = other ? OTHER_ID : m.league;
      const meta = leagueMeta.get(m.league);
      const g = map.get(id) ?? { id, name: other ? 'Diğer ligler' : meta?.name ?? m.league_name, priority: other ? 999 : meta?.priority ?? m.league_priority ?? 50, modeled: [], plain: [], total: 0 };
      (m.model || m.pick ? g.modeled : g.plain).push(m);
      g.total++;
      map.set(id, g);
    }
    for (const g of map.values()) { g.modeled.sort(byKickoff); g.plain.sort(byKickoff); }
    return [...map.values()].sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name, 'tr'));
  }, [filtered, day.leagues]);

  // Grup varsayılanı: modelli maçı olan lig açık, "Diğer ligler" kapalı. Arama varken hepsi açık.
  const isOpen = (g: Group) => !!qf || (f.open[g.id] ?? (g.id !== OTHER_ID && g.modeled.length > 0));
  const toggle = (g: Group) => upd({ ...f, open: { ...f.open, [g.id]: !isOpen(g) } });
  const plainKey = (g: Group) => `${g.id}:modelsiz`;
  const plainOpen = (g: Group) => !!qf || g.id === OTHER_ID || (f.open[plainKey(g)] ?? false);
  const anyFilter = f.time !== 'all' || f.strong || f.value || !!qf;

  return (
    <div>
      <SourceSummary day={day} />
      <Highlights day={day} now={now} />

      {/* Araç çubuğu */}
      <div className="mt-6 space-y-2">
        <div className="relative">
          <label htmlFor="ara" className="sr-only">Takım ara</label>
          <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>
          <input id="ara" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Takım ara"
            autoComplete="off" enterKeyHint="search"
            className="w-full min-h-[44px] rounded-md border border-line bg-surface pl-10 pr-3 text-[16px] placeholder:text-muted focus:border-accent outline-none" />
        </div>
        <div className="-mx-4 px-4 flex items-center gap-2 overflow-x-auto no-scrollbar" role="group" aria-label="Filtreler">
          <div className="seg shrink-0" role="group" aria-label="Saat">
            {([['soon', 'Yakında'], ['evening', 'Bu akşam'], ['all', 'Tümü']] as const).map(([k, t]) => (
              <button key={k} aria-pressed={f.time === k} onClick={() => upd({ ...f, time: k })}
                title={k === 'soon' ? 'Önümüzdeki 2 saat ve canlı' : k === 'evening' ? '18.00 ve sonrası' : undefined}>{t}</button>
            ))}
          </div>
          <button className="chip shrink-0" aria-pressed={f.strong} onClick={() => upd({ ...f, strong: !f.strong })}>4+ yıldız</button>
          <button className="chip shrink-0" aria-pressed={f.value} onClick={() => upd({ ...f, value: !f.value })}>Değerli</button>
        </div>
      </div>

      <p className="mt-3 t-meta num" aria-live="polite">
        {anyFilter ? `${filtered.length} / ${matches.length} maç` : `${matches.length} maç`} · {day.run_label} çalıştırması, güncelleme {fmtTime(day.generated_at)}
      </p>

      {!matches.length && <div className="mt-4"><Empty title="Bu gün için maç yok" /></div>}
      {matches.length > 0 && !groups.length && (
        <div className="mt-4">
          <Empty title="Filtreye uyan maç yok">
            {f.time === 'soon' ? 'Önümüzdeki 2 saatte başlayan maç yok. ' : ''}
            <button className="text-accent font-semibold underline-offset-2 hover:underline" onClick={() => { setQ(''); upd({ ...f, time: 'all', strong: false, value: false }); }}>Filtreleri temizle</button>
          </Empty>
        </div>
      )}

      <div className="mt-2">
        {groups.map((g) => {
          const open = isOpen(g);
          const picks = g.modeled.filter((m) => m.pick).length;
          return (
            <section key={g.id} className="border-t border-line first:border-t-0" aria-labelledby={`lig-${g.id}`}>
              <h2 id={`lig-${g.id}`}>
                <button className="w-full min-h-[52px] flex items-center gap-2 text-left" aria-expanded={open} onClick={() => toggle(g)}>
                  <span className="display text-[22px] font-semibold leading-none truncate">{g.name}</span>
                  <span className="text-sm text-muted num shrink-0">
                    {g.total}{picks > 0 && ` · ${picks} tercih`}{g.id === OTHER_ID && ' · modelsiz'}
                  </span>
                  <span className="ml-auto text-muted"><Chevron open={open} /></span>
                </button>
              </h2>
              {open && (
                <div className="pb-4">
                  {g.modeled.length > 0 && (
                    <div className="grid gap-2.5 md:grid-cols-2">
                      {g.modeled.map((m) => <MatchCard key={m.id} m={m} date={day.date} showLeague={g.id === OTHER_ID} />)}
                    </div>
                  )}
                  {g.plain.length > 0 && (
                    g.id === OTHER_ID || plainOpen(g) ? (
                      <div className={g.modeled.length ? 'mt-3' : ''}>
                        {g.modeled.length > 0 && g.id !== OTHER_ID && (
                          <button className="tap t-meta inline-flex items-center gap-1" aria-expanded onClick={() => upd({ ...f, open: { ...f.open, [plainKey(g)]: false } })}>
                            Modelsiz {g.plain.length} maç <Chevron open />
                          </button>
                        )}
                        <PlainList ms={g.plain} date={day.date} showLeague={g.id === OTHER_ID} />
                      </div>
                    ) : (
                      <button className="mt-2 tap w-full rounded-md border border-dashed border-line t-meta inline-flex items-center justify-center gap-1"
                        aria-expanded={false} onClick={() => upd({ ...f, open: { ...f.open, [plainKey(g)]: true } })}>
                        Modelsiz {g.plain.length} maçı göster <Chevron open={false} />
                      </button>
                    )
                  )}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

/** Modelsiz maçlar: yoğun satır listesi (saat, takımlar, 1-X-2) */
function PlainList({ ms, date, showLeague }: { ms: Match[]; date: string; showLeague: boolean }) {
  return (
    <ul className="panel divide-y divide-line">
      {ms.map((m) => {
        const alarms = m.market?.drop_alarms ?? [];
        return (
          <li key={m.id}>
            <Link to={matchHref(date, m)} className="flex items-center gap-3 px-3.5 py-2 min-h-[52px] hover:bg-sunken/60">
              <span className="w-11 shrink-0 text-[14px] font-semibold num"><KickoffCell m={m} /></span>
              <span className="min-w-0 flex-1">
                {showLeague && <span className="block t-micro truncate">{m.league_name}</span>}
                <span className="block truncate text-[15px] leading-tight">{m.home.name} – {m.away.name}</span>
              </span>
              {m.status === 'finished' && m.result ? (
                <span className="display text-lg font-bold num">{m.result.ft[0]}–{m.result.ft[1]}</span>
              ) : m.odds ? (
                <span className="shrink-0 text-[13px] num text-muted flex gap-2">
                  {(['1', 'X', '2'] as const).map((k) => (
                    <span key={k} className={alarms.includes(k) ? 'text-warn font-semibold' : ''}>{alarms.includes(k) && '↓'}{m.odds?.[k] != null ? odd(m.odds[k]) : '–'}</span>
                  ))}
                </span>
              ) : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/* ---------- Günün öne çıkanları ---------- */

function Highlights({ day, now }: { day: DayFile; now: number }) {
  const items = useMemo(() => {
    const ms = (day.matches ?? []).filter((m) => m.status !== 'finished');
    const seen = new Set<string>();
    const out: { m: Match; reason: 'pick' | 'drop' | 'value' }[] = [];
    const push = (m: Match, reason: 'pick' | 'drop' | 'value') => { if (!seen.has(m.id)) { seen.add(m.id); out.push({ m, reason }); } };
    ms.filter((m) => m.pick)
      .sort((a, b) => (b.pick!.stars - a.pick!.stars) || (b.pick!.p - a.pick!.p))
      .slice(0, 5).forEach((m) => push(m, 'pick'));
    ms.filter((m) => (m.value?.length ?? 0) > 0)
      .sort((a, b) => Math.max(...b.value.map((v) => v.edge)) - Math.max(...a.value.map((v) => v.edge)))
      .slice(0, 4).forEach((m) => push(m, 'value'));
    // Düşen oran: önce modelli maçlar, sonra yakın başlama saati
    ms.filter((m) => (m.market?.drop_alarms?.length ?? 0) > 0)
      .sort((a, b) => (Number(!!b.model) - Number(!!a.model)) || Math.abs(Date.parse(a.kickoff) - now) - Math.abs(Date.parse(b.kickoff) - now))
      .slice(0, 4).forEach((m) => push(m, 'drop'));
    return out;
  }, [day, now]);

  if (!items.length) return null;
  const nPick = items.filter((x) => x.reason === 'pick').length;
  const nDrop = (day.matches ?? []).filter((m) => m.status !== 'finished' && (m.market?.drop_alarms?.length ?? 0) > 0).length;
  return (
    <section className="mt-5" aria-labelledby="one-cikanlar">
      <div className="flex items-baseline gap-2">
        <h2 id="one-cikanlar" className="h-section">Günün öne çıkanları</h2>
        <span className="t-meta num">{nPick} tercih{nDrop > 0 && ` · ${nDrop} düşen oran`}</span>
      </div>
      <div className="mt-2.5 -mx-4 px-4 flex gap-2.5 overflow-x-auto snap-x snap-mandatory no-scrollbar pb-1 sm:mx-0 sm:px-0 sm:grid sm:grid-cols-3 lg:grid-cols-4 sm:overflow-visible">
        {items.map(({ m, reason }) => <HighlightCard key={m.id} m={m} date={day.date} reason={reason} />)}
      </div>
    </section>
  );
}

function SourceSummary({ day }: { day: DayFile }) {
  const st = useStatus();
  const [open, setOpen] = useState(false);
  const fromStatus = st.state === 'ready' ? statusSources(st.data) : [];
  const sources: Source[] = fromStatus.length ? fromStatus : day.sources ?? [];
  if (!sources.length) return null;
  const ok = sources.filter((s) => s.status === 'ok').length;
  const partial = sources.filter((s) => s.status === 'partial').length;
  const missing = sources.filter((s) => s.status === 'missing').length;
  const alerts = st.state === 'ready' && !Array.isArray(st.data) ? st.data.health?.alerts ?? [] : [];
  return (
    <div className="mt-2">
      <button className="w-full min-h-[40px] flex items-center gap-3 text-left t-meta" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="flex items-center gap-1.5"><Dot s="ok" /> <b className="num text-ink">{ok}</b> kaynak çalışıyor</span>
        {partial > 0 && <span className="flex items-center gap-1.5"><Dot s="partial" /> <b className="num text-ink">{partial}</b> kısmi</span>}
        {missing > 0 && <span className="flex items-center gap-1.5"><Dot s="missing" /> <b className="num text-ink">{missing}</b> eksik</span>}
        <span className="ml-auto"><Chevron open={open} size={14} /></span>
      </button>
      {alerts.length > 0 && (
        <Link to="/kaynaklar" className="mt-1 flex items-center gap-2 rounded-md border border-loss/40 bg-loss/10 px-3 py-2 text-[13px] font-semibold text-loss">
          <span aria-hidden="true">⚠</span> {alerts.length} kaynakta alarm: veri gelmiyor — ayrıntılar
        </Link>
      )}
      {open && (
        <ul className="panel px-3.5 py-2 text-sm space-y-1.5">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <Dot s={s.status} /><span className="font-medium">{s.name}</span>
              <span className="ml-auto t-micro num">{s.fetched_at ? fmtTime(s.fetched_at) : '–'}</span>
            </li>
          ))}
          <li><Link to="/kaynaklar" className="tap inline-flex items-center text-accent font-semibold">Tüm kaynak ayrıntıları</Link></li>
        </ul>
      )}
    </div>
  );
}

