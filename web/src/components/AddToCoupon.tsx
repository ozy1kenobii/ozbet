import { useEffect, useRef, useState } from 'react';
import type { Match } from '../lib/types';
import { MARKET_ORDER, marketLabel } from '../lib/markets';
import { odd, pct } from '../lib/format';
import { useCoupon } from '../lib/coupon';

/** "+" düğmesi: market seçerek kupona ekler. */
export function AddToCoupon({ match, date, compact = false }: { match: Match; date: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const { add, remove, has } = useCoupon();
  const ref = useRef<HTMLDivElement>(null);
  const markets = MARKET_ORDER.filter((k) => match.model?.probs?.[k] != null || match.odds?.[k] != null);
  const count = markets.filter((k) => has(match.id, k)).length;

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey); };
  }, [open]);

  if (!markets.length) return null;
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); }}
        aria-expanded={open}
        aria-label={`${match.home.name} – ${match.away.name} kupona ekle`}
        className={`tap grid place-items-center rounded-md border ${count ? 'border-accent bg-accent text-accent-ink' : 'border-line text-ink bg-surface'} ${compact ? '' : 'px-3'}`}
      >
        {count ? <span className="text-sm font-bold num">+{count}</span> : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Market seç" className="absolute right-0 top-[calc(100%+6px)] z-20 w-[min(300px,calc(100vw-32px))] panel shadow-lg p-2"
          onClick={(e) => e.stopPropagation()}>
          <p className="px-2 pt-1 pb-2 text-sm text-muted">Kupona eklenecek marketi seç</p>
          <ul className="grid grid-cols-2 gap-1.5">
            {markets.map((k) => {
              const on = has(match.id, k);
              return (
                <li key={k}>
                  <button type="button" aria-pressed={on}
                    onClick={(e) => { e.preventDefault(); on ? remove(`${match.id}|${k}`) : add(match, date, k); }}
                    className={`w-full min-h-[48px] rounded-md border px-2.5 py-1.5 text-left ${on ? 'border-accent bg-accent text-accent-ink' : 'border-line hover:border-accent'}`}>
                    <span className="block text-sm font-semibold">{marketLabel(k)}</span>
                    <span className={`block text-xs num ${on ? '' : 'text-muted'}`}>{pct(match.model?.probs?.[k])} · {match.odds?.[k] != null ? odd(match.odds[k]) : 'oran yok'}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
