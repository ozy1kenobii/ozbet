import { Link } from 'react-router-dom';
import type { MarketKey, Match } from '../lib/types';
import { fmtTime, odd, pct } from '../lib/format';
import { marketLabel, marketWins, isMarketKey } from '../lib/markets';
import { Badge, DropBadge, Icon, ResultBadge, Stars, ValueBadge } from './ui';
import { AddToCoupon } from './AddToCoupon';
import { FreshSquadBadge, PickMetrics, SharpNote, isPas, pasText } from './PickBits';
import { pickEv } from '../lib/pick';
import { ForecastStrip } from './Forecast';
import { signedPct } from '../lib/format';

/** Kartta gösterilen sakin oran satırı */
const ODDS_COLS: { k: MarketKey; t: string }[] = [
  { k: '1', t: '1' }, { k: 'X', t: 'X' }, { k: '2', t: '2' }, { k: 'O2.5', t: 'Ü2,5' },
];

export const PROV_LABEL: Record<string, string> = { news: 'Haber', fixture: 'Bülten', odds: 'Oran', stats: 'İstatistik', squad: 'Kadro', model: 'Model', predictions: 'Tahmin siteleri', consensus: 'Konsensüs', fixtures: 'Bülten', results: 'Sonuç' };

/** Provenance içindeki farklı kaynak adlarının sayısı (virgülle birleşik olanlar ayrılır). */
export function sourceCount(m: Match): number {
  const p = m.provenance;
  if (!p) return 0;
  const set = new Set<string>();
  for (const v of Object.values(p)) for (const s of String(v?.source ?? '').split(',')) if (s.trim()) set.add(s.trim().toLowerCase());
  return set.size;
}

export function pickResult(m: Match): boolean | null {
  if (m.status !== 'finished' || !m.result || !m.pick) return null;
  // Ek marketlerin (İY, korner...) sonucu karnede veri hattınca belirlenir; kartta yalnız ana marketler gösterilir
  if (!isMarketKey(m.pick.market)) return null;
  return marketWins(m.pick.market, m.result.ft[0], m.result.ft[1]);
}

export function matchHref(date: string, m: Match) {
  return `/mac/${date}/${encodeURIComponent(m.id)}`;
}

export function KickoffCell({ m }: { m: Match }) {
  if (m.status === 'live') return <span className="inline-flex items-center gap-1 text-loss font-bold"><Icon name="live" size={8} />Canlı</span>;
  return <>{fmtTime(m.kickoff)}</>;
}

export function MatchCard({ m, date, showLeague = false }: { m: Match; date: string; showLeague?: boolean }) {
  const finished = m.status === 'finished' && m.result;
  const pick = m.pick;
  const won = pickResult(m);
  const href = matchHref(date, m);
  const alarms = m.market?.drop_alarms ?? [];
  const nSrc = sourceCount(m);
  const isValue = (m.value?.length ?? 0) > 0;
  const ev = pickEv(pick);
  const hasSharp = !!m.sharp?.best;
  const fresh = !!m.squad?.signal?.fresh;
  const hasNews = [...(m.news?.home ?? []), ...(m.news?.away ?? [])].some((n) => n.tags?.some((t) => t === 'sakat' || t === 'ceza' || t === 'td'));

  return (
    <article className="panel relative">
      <div className="flex items-stretch gap-3 pl-3.5 pr-1.5 pt-2.5">
        <div className="w-11 shrink-0 pt-[3px] num">
          <div className="text-[15px] font-semibold leading-none"><KickoffCell m={m} /></div>
          {m.code && <div className="mt-1.5 t-micro">{m.code}</div>}
        </div>
        <Link to={href} className="min-w-0 flex-1 group pb-1" aria-label={`${m.home.name} – ${m.away.name} maç detayı`}>
          {showLeague && <div className="t-micro truncate mb-0.5">{m.league_name}</div>}
          {[m.home.name, m.away.name].map((name, i) => {
            const pos = m.table?.[i === 0 ? 'home' : 'away']?.pos;
            return (
            <div key={i} className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-[16px] font-semibold leading-6 group-hover:text-accent">
                {name}{pos != null && <span className="ml-1.5 text-[12px] font-normal text-muted num" title="Lig sırası">{pos}.</span>}
              </span>
              {finished && <span className="display text-lg font-bold leading-6 num">{m.result!.ft[i]}</span>}
            </div>
            );
          })}
        </Link>
        <div className="shrink-0"><AddToCoupon match={m} date={date} compact /></div>
      </div>

      {m.forecast && <Link to={href} tabIndex={-1} className="mx-3.5 mt-1.5 block"><ForecastStrip m={m} /></Link>}
      {pick ? (
        <Link to={href} tabIndex={-1} aria-hidden="true" className="mx-3.5 mt-1.5 block rounded-md bg-accent/[.07] px-2.5 pt-2 pb-1.5">
          <span className="flex items-center gap-2">
            <span className="t-micro shrink-0">Tercih</span>
            <span className="display text-[20px] font-bold leading-none truncate">{pick.label || marketLabel(pick.market)}</span>
            <span className="ml-auto shrink-0">{won != null ? <ResultBadge won={won} /> : <Stars n={pick.stars} size={12} />}</span>
            <span className="shrink-0 display text-[26px] font-bold leading-none num" title="iddaa oranı">{pick.odds != null ? odd(pick.odds) : '–'}</span>
          </span>
          <span className="mt-1.5 block"><PickMetrics pick={pick} /></span>
        </Link>
      ) : m.forecast ? null : isPas(m) ? (
        <Link to={href} tabIndex={-1} className="mx-3.5 mt-1.5 flex items-baseline gap-2 rounded-md border border-dashed border-line px-2.5 py-1.5">
          <span className="display text-[17px] font-semibold leading-none text-muted shrink-0">Pas</span>
          <span className="t-meta min-w-0">{pasText(m.pick_note) || 'Ölçütlere uyan seçim yok.'}</span>
        </Link>
      ) : m.model?.source === 'piyasa' ? (
        <p className="mx-3.5 mt-1.5"><Badge tone="neutral" title="Olasılıklar iddaa oranlarından türetildi; bağımsız tahmin değildir">Piyasa modeli</Badge></p>
      ) : m.model ? null : (
        <p className="mx-3.5 mt-1 t-micro">Model yok – yalnız oranlar</p>
      )}
      {/* Erişilebilir tercih özeti (görsel satır aria-hidden) */}
      {pick && <span className="sr-only">OZBET Tercihi {pick.label || marketLabel(pick.market)}{pick.odds != null ? `, oran ${odd(pick.odds)}` : ''}, model {pct(pick.p)}{ev != null ? `, beklenen değer ${signedPct(ev)}` : ''}, güven {pick.stars} yıldız{won != null ? (won ? ', tuttu' : ', tutmadı') : ''}</span>}

      {(isValue || alarms.length > 0 || hasNews || hasSharp || fresh) && (
        <div className="mx-3.5 mt-2 flex flex-wrap items-center gap-1.5">
          {isValue && <ValueBadge />}
          <SharpNote sharp={m.sharp} />
          <FreshSquadBadge signal={m.squad?.signal} />
          {hasNews && <Badge tone="warn" title="Sakatlık, ceza veya teknik direktör haberi var">Haber</Badge>}
          {alarms.length > 0 && <DropBadge>Düşen oran: {alarms.map(marketLabel).join(', ')}</DropBadge>}
        </div>
      )}

      <div className="mx-3.5 mt-2 mb-2.5 flex items-center gap-3 text-[13px] num">
        {m.odds ? (
          <dl className="flex flex-wrap gap-x-3 text-muted" aria-label="Oranlar">
            {ODDS_COLS.map((c) => {
              const v = m.odds?.[c.k];
              if (v == null) return null;
              const alarm = alarms.includes(c.k);
              const picked = pick?.market === c.k;
              return (
                <div key={c.k} className="flex gap-1">
                  <dt>{c.t}</dt>
                  <dd className={`${alarm ? 'text-warn font-semibold' : picked ? 'text-ink font-semibold' : 'text-ink/80'}`}>
                    {alarm && <span aria-label="düşen oran">↓</span>}{odd(v)}
                  </dd>
                </div>
              );
            })}
          </dl>
        ) : <span className="text-muted">Oran yok</span>}
        {m.mbs != null && <span className="text-muted" title="Minimum bahis sayısı">MBS {m.mbs}</span>}
        <Link to={href} className="ml-auto shrink-0 text-muted hover:text-accent" aria-label={`${nSrc} kaynak – maç detayında`}>
          {nSrc ? `${nSrc} kaynak` : 'Kaynak yok'}
        </Link>
      </div>
    </article>
  );
}

/** Öne çıkanlar şeridindeki küçük kart */
export function HighlightCard({ m, date, reason }: { m: Match; date: string; reason: 'pick' | 'drop' | 'value' }) {
  const pick = m.pick;
  const alarms = m.market?.drop_alarms ?? [];
  return (
    <Link to={matchHref(date, m)}
      className="snap-start shrink-0 w-[72%] max-w-[260px] sm:w-auto sm:max-w-none panel px-3 py-2.5 flex flex-col gap-1 hover:border-accent">
      <div className="flex items-center gap-2 t-micro num">
        <span className="font-semibold text-ink"><KickoffCell m={m} /></span>
        <span className="truncate">{m.league_name}</span>
      </div>
      <div className="text-[15px] font-semibold leading-tight">
        <span className="block truncate">{m.home.name}</span>
        <span className="block truncate">{m.away.name}</span>
      </div>
      <div className="mt-auto pt-1 flex items-center gap-2 min-h-[24px]">
        {pick && reason !== 'drop' ? (
          <>
            <span className="display text-[18px] font-bold leading-none truncate">{pick.label || marketLabel(pick.market)}</span>
            <span className="text-[15px] font-semibold num">{pick.odds != null ? odd(pick.odds) : pct(pick.p)}</span>
            {pickEv(pick) != null && <span className="ml-auto text-[12px] text-muted num whitespace-nowrap" title="Beklenen değer">BD {signedPct(pickEv(pick))}</span>}
          </>
        ) : reason === 'drop' ? (
          <DropBadge>{alarms.map((k) => `${marketLabel(k)} ${m.odds?.[k] != null ? odd(m.odds[k]) : ''}`.trim()).join(', ')}</DropBadge>
        ) : null}
      </div>
      {reason === 'value' && <div><ValueBadge /></div>}
      {reason === 'pick' && alarms.length > 0 && <div><DropBadge /></div>}
    </Link>
  );
}

