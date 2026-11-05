import { Link } from 'react-router-dom';
import type { MarketKey, Match } from '../lib/types';
import { fmtTime, odd, pct } from '../lib/format';
import { marketLabel, marketWins } from '../lib/markets';
import { ProbBar } from './charts';
import { Badge, Stars } from './ui';
import { AddToCoupon } from './AddToCoupon';

const ODDS_COLS: { k: MarketKey; t: string }[] = [
  { k: '1', t: '1' }, { k: 'X', t: 'X' }, { k: '2', t: '2' },
  { k: 'O2.5', t: 'Ü2.5' }, { k: 'U2.5', t: 'A2.5' }, { k: 'BTTS_Y', t: 'KG V' }, { k: 'BTTS_N', t: 'KG Y' },
];

export function provenanceText(m: Match): string | null {
  const p = m.provenance;
  if (!p) return null;
  const parts = Object.entries(p).map(([k, v]) => `${PROV_LABEL[k] ?? k}: ${v.source} ${fmtTime(v.t)}`);
  return parts.length ? parts.join(' · ') : null;
}
export const PROV_LABEL: Record<string, string> = { odds: 'Oran', stats: 'İstatistik', squad: 'Kadro', consensus: 'Konsensüs', fixtures: 'Bülten', results: 'Sonuç' };

export function MatchCard({ m, date }: { m: Match; date: string }) {
  const finished = m.status === 'finished' && m.result;
  const live = m.status === 'live';
  const pick = m.pick;
  const pickWon = finished && pick ? marketWins(pick.market, m.result!.ft[0], m.result!.ft[1]) : null;
  const prov = provenanceText(m);
  const href = `/mac/${date}/${encodeURIComponent(m.id)}`;
  const alarms = m.market?.drop_alarms ?? [];

  return (
    <article className="panel overflow-visible">
      <div className="flex items-start gap-3 px-3.5 pt-3">
        <div className="w-12 shrink-0 pt-0.5">
          <div className={`display text-lg font-semibold leading-none num ${live ? 'text-loss' : ''}`}>{live ? 'CANLI' : fmtTime(m.kickoff)}</div>
          {m.code && <div className="mt-1 text-[12px] text-muted num">#{m.code}</div>}
          {m.mbs != null && <div className="mt-1"><Badge title="Minimum bahis sayısı">MBS {m.mbs}</Badge></div>}
        </div>
        <Link to={href} className="min-w-0 flex-1 group" aria-label={`${m.home.name} – ${m.away.name} maç detayı`}>
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[16px] font-semibold group-hover:text-accent">{m.home.name}</span>
            {finished && <span className="display text-xl font-bold num">{m.result!.ft[0]}</span>}
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[16px] font-semibold group-hover:text-accent">{m.away.name}</span>
            {finished && <span className="display text-xl font-bold num">{m.result!.ft[1]}</span>}
          </div>
          {finished && m.result!.ht && <div className="text-[12px] text-muted num">İY {m.result!.ht[0]}-{m.result!.ht[1]} · MS</div>}
        </Link>
        <AddToCoupon match={m} date={date} compact />
      </div>

      {/* Oranlar */}
      <div className="mt-3 px-3.5">
        {m.odds ? (
          <div className="grid grid-cols-7 gap-1 text-center num">
            {ODDS_COLS.map((c) => {
              const v = m.odds?.[c.k];
              const alarm = alarms.includes(c.k);
              return (
                <div key={c.k} className={`rounded-[5px] py-1 ${alarm ? 'ring-1 ring-warn' : ''} ${pick?.market === c.k ? 'bg-accent/10' : 'bg-sunken'}`}>
                  <div className="text-[11px] text-muted leading-tight">{c.t}</div>
                  <div className="text-[14px] font-semibold leading-tight">{v != null ? odd(v) : '–'}</div>
                </div>
              );
            })}
          </div>
        ) : <p className="text-sm text-muted">Oran yok</p>}
      </div>

      {/* Model */}
      <div className="px-3.5 mt-3">
        {m.model ? (
          <>
            <ProbBar probs={m.model.probs} home={m.home.name} away={m.away.name} />
            <div className="mt-1.5 flex gap-4 text-[13px] text-muted num">
              <span>2.5 Üst <b className="text-ink font-semibold">{pct(m.model.probs['O2.5'])}</b></span>
              <span>KG Var <b className="text-ink font-semibold">{pct(m.model.probs['BTTS_Y'])}</b></span>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted rounded-md bg-sunken px-3 py-2">Veri yetersiz – model çalıştırılmadı</p>
        )}
      </div>

      {m.consensus?.summary?.[0] && (
        <p className="px-3.5 mt-2 text-[13px] text-muted">{m.consensus.summary[0].text}</p>
      )}

      {/* Tercih */}
      <div className="mt-3 mx-3.5 flex items-center gap-3 border-t border-line pt-3">
        {pick ? (
          <>
            <div className="min-w-0">
              <div className="text-[12px] text-muted">OZBET Tercihi</div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="display text-lg font-semibold leading-tight">{pick.label || marketLabel(pick.market)}</span>
                <span className="text-sm num text-muted">{pct(pick.p)}{pick.odds != null && ` · ${odd(pick.odds)}`}</span>
                {pickWon != null && <Badge tone={pickWon ? 'win' : 'loss'}>{pickWon ? 'Tuttu' : 'Tutmadı'}</Badge>}
              </div>
            </div>
            <div className="ml-auto flex flex-col items-end gap-1">
              <Stars n={pick.stars} />
              {m.value?.length ? <Badge tone="accent">Değerli</Badge> : <span className="text-[12px] text-muted">{m.value_note || 'değer yok'}</span>}
            </div>
          </>
        ) : (
          <span className="text-sm text-muted">Tercih yok</span>
        )}
      </div>

      {(alarms.length > 0 || m.flags?.length > 0) && (
        <div className="px-3.5 mt-2 flex flex-wrap gap-1.5">
          {alarms.length > 0 && <Badge tone="warn" title="Sabahtan bu yana belirgin oran düşüşü">Düşen oran: {alarms.map(marketLabel).join(', ')}</Badge>}
          {m.flags?.map((f) => <Badge key={f}>{f}</Badge>)}
        </div>
      )}

      <div className="px-3.5 pb-3 pt-2 flex items-end justify-between gap-3">
        <p className="text-[11px] text-muted leading-snug">{prov ?? 'Kaynak bilgisi yok'}</p>
        <Link to={href} className="tap shrink-0 inline-flex items-center text-sm font-semibold text-accent">Detay</Link>
      </div>
    </article>
  );
}
