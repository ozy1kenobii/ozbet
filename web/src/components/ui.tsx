import type { ReactNode } from 'react';
import type { FormLetter } from '../lib/types';

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`display inline-flex items-baseline font-bold text-[26px] leading-none tracking-tight ${className}`} aria-label="OZBET">
      <span className="text-ink">OZ</span>
      <span className="text-accent">BET</span>
    </span>
  );
}

export function Stars({ n, size = 14 }: { n: number; size?: number }) {
  const v = Math.max(0, Math.min(5, Math.round(n)));
  return (
    <span className="inline-flex items-center gap-[2px]" role="img" aria-label={`Güven: 5 üzerinden ${v}`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <svg key={i} width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="M10 1.8l2.5 5.3 5.8.7-4.3 4 1.1 5.7L10 14.7l-5.1 2.8 1.1-5.7-4.3-4 5.8-.7z"
            className={i < v ? 'fill-accent' : 'fill-none stroke-line'}
            strokeWidth={1.4}
          />
        </svg>
      ))}
    </span>
  );
}

const FORM_MAP: Record<FormLetter, { t: string; cls: string; full: string }> = {
  W: { t: 'G', cls: 'bg-win text-white', full: 'Galibiyet' },
  D: { t: 'B', cls: 'bg-draw text-white', full: 'Beraberlik' },
  L: { t: 'M', cls: 'bg-loss text-white', full: 'Mağlubiyet' },
};

export function FormStrip({ form }: { form: FormLetter[] | null | undefined }) {
  if (!form || !form.length) return <span className="text-muted text-sm">Veri yok</span>;
  return (
    <span className="inline-flex gap-1" aria-label={`Form: ${form.map((f) => FORM_MAP[f]?.full ?? f).join(', ')}`}>
      {form.map((f, i) => (
        <span key={i} className={`grid h-6 w-6 place-items-center rounded-[4px] text-xs font-semibold ${FORM_MAP[f]?.cls ?? 'bg-sunken text-muted'}`} aria-hidden="true">
          {FORM_MAP[f]?.t ?? '?'}
        </span>
      ))}
    </span>
  );
}

export function Empty({ title = 'Henüz veri yok', children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="panel px-5 py-10 text-center">
      <p className="display text-2xl font-semibold">{title}</p>
      <p className="mt-2 text-sm text-muted max-w-sm mx-auto">
        {children ?? 'Veri boru hattı bu dosyayı henüz üretmedi. Bir sonraki çalıştırmadan sonra burada görünecek.'}
      </p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Yükleniyor">
      {[0, 1, 2].map((i) => <div key={i} className="h-28 rounded-lg bg-sunken animate-pulse" />)}
    </div>
  );
}

export function Badge({ children, tone = 'neutral', title }: { children: ReactNode; tone?: 'neutral' | 'accent' | 'warn' | 'loss' | 'win'; title?: string }) {
  const cls = {
    neutral: 'border-line text-muted',
    accent: 'border-accent text-accent',
    warn: 'border-warn/60 text-warn',
    loss: 'border-loss/60 text-loss',
    win: 'border-win/60 text-win',
  }[tone];
  return <span title={title} className={`inline-flex items-center rounded border px-1.5 py-[1px] text-[12px] font-semibold leading-5 ${cls}`}>{children}</span>;
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="mt-7">
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h2 className="h-section">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Dot({ s }: { s: string }) {
  const cls = s === 'ok' ? 'bg-win' : s === 'partial' || s === 'skipped' ? 'bg-warn' : 'bg-loss';
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${cls}`} aria-hidden="true" />;
}
