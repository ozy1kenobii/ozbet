import { useState } from 'react';
import type { Match, Pick, Sharp, SquadSignal } from '../lib/types';
import { odd, pct, signedPct } from '../lib/format';
import { marketLabel } from '../lib/markets';
import { SHARP_EXPLAIN, SHARP_SOURCE, fairOdds, pickEv } from '../lib/pick';
import { Badge, Chevron } from './ui';

/** "Pas: ..." → "..." (başlık ayrı gösterildiği için ön ek atılır) */
export const pasText = (note: string | null | undefined) => {
  const t = (note ?? '').replace(/^\s*pas\s*[:–—-]\s*/i, '').trim();
  return t ? t.charAt(0).toLocaleUpperCase('tr') + t.slice(1) : '';
};

/** Analizi yapılmış ama tercih çıkmamış maç mı? (piyasa modeli "analizli" sayılmaz) */
export const isPas = (m: Match) => !m.pick && (!!m.pick_note || (!!m.model && m.model.source !== 'piyasa'));

/** Model olasılığı · adil oran · beklenen değer — kartta ve detayda aynı üçlü. */
export function PickMetrics({ pick, size = 'sm' }: { pick: Pick; size?: 'sm' | 'lg' }) {
  const ev = pickEv(pick);
  const fair = fairOdds(pick);
  const dd = size === 'lg' ? 'text-xl font-semibold text-ink' : 'text-[14px] font-semibold text-ink';
  return (
    <dl className={`grid grid-cols-3 num ${size === 'lg' ? 'gap-x-5' : 'gap-x-2'}`}>
      <div><dt className="t-micro">{pick.basis === 'keskin' ? 'Keskin piyasa' : 'Model'}</dt><dd className={dd}>{pct(pick.p)}</dd></div>
      <div title="Adil oran = 1 / olasılık (sinyal seçiminde keskin piyasanın marjsız olasılığı). İddaa oranı bundan yüksekse beklenen değer pozitiftir.">
        <dt className="t-micro">Adil oran</dt><dd className={dd}>{odd(fair)}</dd>
      </div>
      <div title="Beklenen değer = olasılık × oran − 1. Uzun dönem ortalamasıdır; tek maç için bir şey söylemez.">
        <dt className="t-micro">Beklenen değer</dt><dd className={dd}>{ev != null ? signedPct(ev) : '–'}</dd>
      </div>
    </dl>
  );
}

/** Dokununca açıklaması açılan "Keskin piyasa farkı" rozeti. */
export function SharpNote({ sharp, detail = false }: { sharp: Sharp | null | undefined; detail?: boolean }) {
  const [open, setOpen] = useState(false);
  const b = sharp?.best;
  if (!sharp || !b) return null;
  const src = SHARP_SOURCE[sharp.source] ?? sharp.source;
  return (
    <>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="inline-flex items-center gap-1 rounded border border-accent/50 bg-accent/5 px-1.5 text-[12px] font-semibold leading-5 text-accent min-h-[28px]">
        Keskin piyasa farkı <span className="num">{signedPct(b.edge)}</span>
        <Chevron open={open} size={12} />
      </button>
      {open && (
        <div className="basis-full rounded-md bg-sunken px-3 py-2 text-[13px] leading-snug" role="note">
          <p className="num">
            <b>{marketLabel(b.market)}</b>: iddaa <b>{odd(b.odds)}</b> · keskin piyasada adil oran <b>{b.fair_p > 0 ? odd(1 / b.fair_p) : '–'}</b> ({pct(b.fair_p, 1)})
            {src && <span className="text-muted"> · kaynak: {src}</span>}
          </p>
          <p className="mt-1 text-muted">{SHARP_EXPLAIN}</p>
          {detail && Object.keys(sharp.edge ?? {}).length > 1 && (
            <p className="mt-1 text-muted num">
              Diğer marketler: {Object.entries(sharp.edge).filter(([k]) => k !== b.market).map(([k, v]) => `${marketLabel(k)} ${signedPct(v)}`).join(' · ')}
            </p>
          )}
        </div>
      )}
    </>
  );
}

export function FreshSquadBadge({ signal }: { signal: SquadSignal | null | undefined }) {
  if (!signal?.fresh) return null;
  return <Badge tone="warn" title={signal.text || 'Son saatlerde gelen kadro haberi'}>Taze kadro haberi</Badge>;
}
