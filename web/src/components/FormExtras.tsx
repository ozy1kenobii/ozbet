import { useState } from 'react';
import type { LeagueStandings, Match, StandingRow } from '../lib/types';
import { fmtShortDate, num, odd, pct } from '../lib/format';
import { allProbs, marketLabel } from '../lib/markets';
import { useCoupon } from '../lib/coupon';
import { FormStrip, Section } from './ui';

const VIEWS = [
  { k: 'rows', t: 'Genel' },
  { k: 'home', t: 'İç saha' },
  { k: 'away', t: 'Deplasman' },
] as const;
type ViewKey = (typeof VIEWS)[number]['k'];
const WINDOW = 3;

function seasonLabel(s: string) {
  return s.length === 4 ? `20${s.slice(0, 2)}/${s.slice(2)}` : s;
}

/** Puan durumu: iki takımın satırı vurgulu; varsayılan olarak yalnız çevrelerindeki ±3 sıra. */
export function StandingsSection({ m, table }: { m: Match; table?: LeagueStandings }) {
  const [view, setView] = useState<ViewKey>('rows');
  const [full, setFull] = useState(false);
  if (!table || !m.table) return null;
  const names = new Set([m.table.home.team, m.table.away.team]);
  const rows: StandingRow[] = table[view] ?? [];
  const marks = rows.filter((r) => names.has(r.team)).map((r) => r.pos);
  const keep = (r: StandingRow) => full || marks.some((p) => Math.abs(r.pos - p) <= WINDOW);
  const shown = rows.filter(keep);
  const cut = shown.length < rows.length;

  return (
    <Section title="Puan durumu"
      aside={<span className="text-[12px] text-muted num">{seasonLabel(table.season)} · son maç {fmtShortDate(table.updated)}</span>}>
      <div className="-mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1 pb-1" role="group" aria-label="Tablo türü">
        {VIEWS.map((v) => (
          <button key={v.k} type="button" aria-pressed={view === v.k} onClick={() => setView(v.k)}
            className="chip shrink-0">{v.t}</button>
        ))}
      </div>
      <div className="panel px-1 py-1 overflow-x-auto md:max-w-3xl">
        <table className="tbl num text-[13px]">
          <thead>
            <tr>
              <th className="w-7 text-right">#</th><th>Takım</th>
              <th className="text-right" title="Oynanan">O</th>
              <th className="text-right hidden sm:table-cell" title="Galibiyet">G</th>
              <th className="text-right hidden sm:table-cell" title="Beraberlik">B</th>
              <th className="text-right hidden sm:table-cell" title="Mağlubiyet">M</th>
              <th className="text-right hidden sm:table-cell" title="Attığı gol">AG</th>
              <th className="text-right hidden sm:table-cell" title="Yediği gol">YG</th>
              <th className="text-right" title="Averaj">AV</th>
              <th className="text-right" title="Puan">P</th>
              <th className="hidden md:table-cell">Son 5</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const hi = names.has(r.team);
              const gap = i > 0 && r.pos - shown[i - 1].pos > 1;
              return (
                <tr key={r.team} className={`${hi ? 'bg-accent/[.08] font-semibold' : ''} ${gap ? 'border-t-2 border-dashed border-line' : ''}`}>
                  <td className="text-right text-muted">{r.pos}</td>
                  <td className={`max-w-[150px] truncate ${hi ? 'text-accent' : ''}`}>{r.team}</td>
                  <td className="text-right">{r.o}</td>
                  <td className="text-right hidden sm:table-cell">{r.g}</td>
                  <td className="text-right hidden sm:table-cell">{r.b}</td>
                  <td className="text-right hidden sm:table-cell">{r.m}</td>
                  <td className="text-right hidden sm:table-cell">{r.ag}</td>
                  <td className="text-right hidden sm:table-cell">{r.yg}</td>
                  <td className="text-right">{r.av > 0 ? `+${r.av}` : r.av}</td>
                  <td className="text-right font-bold">{r.p}</td>
                  <td className="hidden md:table-cell"><span className="inline-block scale-[.8] origin-left"><FormStrip form={r.form} /></span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        {(cut || full) && (
          <button type="button" onClick={() => setFull((f) => !f)} className="tap text-sm font-semibold text-accent">
            {full ? 'Kısa tablo' : `Tam tablo (${rows.length} takım)`}
          </button>
        )}
        <p className="text-[12px] text-muted">
          Kaynak football-data.co.uk sonuçları; resmi tablodan birkaç gün geride olabilir, puan silme gibi kararlar yansımaz.
        </p>
      </div>
    </Section>
  );
}

/** Trend/seri kartları: her kart bir markete bağlı; model olasılığı, oran ve kupona ekle. */
export function TrendsSection({ m, date }: { m: Match; date: string }) {
  const { add, remove, has } = useCoupon();
  const list = m.trends ?? [];
  if (!list.length) return null;
  const probs = allProbs(m);
  const odds = (m.odds ?? {}) as Record<string, number | undefined>;
  const tag = { home: m.home.name, away: m.away.name, both: 'Aralarında' } as const;
  return (
    <Section title="Trendler" aside={<span className="text-[12px] text-muted">Geçmiş seriler · tahmin değildir</span>}>
      <ul className="grid gap-2 md:grid-cols-2">
        {list.map((t) => {
          const p = t.p ?? probs[t.market] ?? null;
          const o = t.odds ?? odds[t.market] ?? null;
          const on = has(m.id, t.market);
          return (
            <li key={`${t.team}-${t.market}`} className="panel px-3.5 py-3 flex flex-col gap-2">
              <div className="flex items-baseline gap-2">
                <span className="t-micro truncate">{tag[t.team]}</span>
                <span className="ml-auto t-micro num shrink-0">{t.hits}/{t.n}</span>
              </div>
              <p className="text-[15px] leading-snug">{t.text}</p>
              <div className="mt-auto flex items-center gap-2.5 text-[13px] num">
                <span className="font-semibold">{marketLabel(t.market)}</span>
                <span className="text-muted">Model <b className="text-ink">{p != null ? pct(p) : '–'}</b></span>
                <span className="text-muted">Oran <b className="text-ink">{o != null ? odd(o) : '–'}</b></span>
                <button type="button" aria-pressed={on} aria-label={`${marketLabel(t.market)} kupona ${on ? 'eklendi' : 'ekle'}`}
                  onClick={() => (on ? remove(`${m.id}|${t.market}`) : add(m, date, t.market))}
                  className={`ml-auto h-8 w-8 shrink-0 rounded-md border text-sm font-bold ${on ? 'border-accent bg-accent text-accent-ink' : 'border-line'}`}>{on ? '✓' : '+'}</button>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-1.5 text-[12px] text-muted">
        Trend kartları geçmiş maçları özetler, tahmin değildir. Bir serinin sürmesi beklenmez; karar için model olasılığına ve orana bakın.
        Yalnız en az 5 maçta %80 ve üstü / %20 ve altı oranlar ya da 4+ maçlık seriler gösterilir.
      </p>
    </Section>
  );
}

/** H2H özet şeridi: bugünkü ev sahibi / beraberlik / deplasman + gol özetleri. */
export function H2HSummaryStrip({ m }: { m: Match }) {
  const s = m.stats?.h2h_summary;
  if (!s || !s.n) return null;
  const seg = [
    { v: s.home_wins, t: m.home.name, cls: 'bg-accent' },
    { v: s.draws, t: 'Beraberlik', cls: 'bg-muted/60' },
    { v: s.away_wins, t: m.away.name, cls: 'bg-ink/70' },
  ];
  return (
    <div className="panel mb-2 px-4 py-3">
      <div className="flex h-2 overflow-hidden rounded bg-sunken" aria-hidden="true">
        {seg.map((x, i) => x.v > 0 && <span key={i} className={x.cls} style={{ width: `${(x.v / s.n) * 100}%` }} />)}
      </div>
      <div className="mt-2 grid grid-cols-3 text-center text-[13px]">
        {seg.map((x, i) => (
          <div key={i} className="min-w-0">
            <div className="display text-xl font-bold num">{x.v}</div>
            <div className="truncate text-muted">{x.t}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[13px] text-muted num text-center">
        Son {s.n} maç · ort. <b className="text-ink">{num(s.avg_goals, 1)}</b> gol · KG Var <b className="text-ink">{s.btts}/{s.n}</b> · 2.5 Üst <b className="text-ink">{s.o25}/{s.n}</b>
      </p>
    </div>
  );
}
