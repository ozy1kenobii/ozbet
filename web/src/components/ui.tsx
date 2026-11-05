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

/** Güven yıldızları: dolu = vurgu rengi, boş = ince çerçeve. Her yerde aynı bileşen. */
export function Stars({ n, size = 14 }: { n: number; size?: number }) {
  const v = Math.max(0, Math.min(5, Math.round(n)));
  return (
    <span className="inline-flex items-center gap-[1px] shrink-0" role="img" aria-label={`Güven: 5 üzerinden ${v} yıldız`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <svg key={i} width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="M10 1.8l2.5 5.3 5.8.7-4.3 4 1.1 5.7L10 14.7l-5.1 2.8 1.1-5.7-4.3-4 5.8-.7z"
            className={i < v ? 'fill-accent' : 'fill-none stroke-muted/50'}
            strokeWidth={1.5}
          />
        </svg>
      ))}
    </span>
  );
}

const FORM_MAP: Record<FormLetter, { t: string; cls: string; full: string }> = {
  W: { t: 'G', cls: 'bg-win text-on-status', full: 'Galibiyet' },
  D: { t: 'B', cls: 'bg-draw text-on-status', full: 'Beraberlik' },
  L: { t: 'M', cls: 'bg-loss text-on-status', full: 'Mağlubiyet' },
};

export function FormStrip({ form }: { form: FormLetter[] | null | undefined }) {
  if (!form || !form.length) return <span className="text-muted text-sm">Veri yok</span>;
  return (
    <span className="inline-flex gap-1" aria-label={`Form: ${form.map((f) => FORM_MAP[f]?.full ?? f).join(', ')}`}>
      {form.map((f, i) => (
        <span key={i} className={`grid h-6 w-6 place-items-center rounded-[4px] text-xs font-bold ${FORM_MAP[f]?.cls ?? 'bg-sunken text-muted'}`} aria-hidden="true">
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

/* ---------- Skeleton yükleme durumları ---------- */

function Sk({ className = '' }: { className?: string }) {
  return <div className={`skel ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="panel px-3.5 py-3" aria-hidden="true">
      <div className="flex gap-3">
        <div className="w-11 space-y-1.5"><Sk className="h-4 w-10" /><Sk className="h-3 w-8" /></div>
        <div className="flex-1 space-y-2"><Sk className="h-4 w-3/4" /><Sk className="h-4 w-2/3" /></div>
      </div>
      <Sk className="mt-3 h-9 w-full" />
    </div>
  );
}

export function Loading({ variant = 'list' }: { variant?: 'list' | 'detail' | 'page' }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Yükleniyor</span>
      {variant === 'detail' ? (
        <div className="space-y-4" aria-hidden="true">
          <Sk className="h-4 w-40" />
          <Sk className="h-9 w-3/4" /><Sk className="h-9 w-2/3" />
          <Sk className="h-11 w-full" />
          <Sk className="h-28 w-full" />
          <Sk className="h-48 w-full" />
        </div>
      ) : variant === 'page' ? (
        <div className="space-y-3" aria-hidden="true">
          <Sk className="h-8 w-40" /><Sk className="h-24 w-full" /><Sk className="h-40 w-full" />
        </div>
      ) : (
        <div className="space-y-2.5">
          <Sk className="h-24 w-full" />
          <Sk className="mt-5 h-5 w-32" />
          {[0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}
        </div>
      )}
    </div>
  );
}

/* ---------- Rozetler ---------- */

export type Tone = 'neutral' | 'accent' | 'warn' | 'loss' | 'win';

const ICONS = {
  value: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  drop: 'M12 4v15M6 13l6 6 6-6',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  cross: 'M6 6l12 12M18 6L6 18',
  live: '',
} as const;
export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 12 }: { name: IconName; size?: number }) {
  if (name === 'live') return <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="currentColor" /></svg>;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

/**
 * Rozet sistemi:
 *  - çerçeveli (varsayılan): bilgi etiketi (Değerli, Düşen oran, MBS, bayraklar)
 *  - solid: biten maçın sonucu (Tuttu / Tutmadı) — her zaman ikonlu
 */
export function Badge({ children, tone = 'neutral', title, icon, solid = false }: { children: ReactNode; tone?: Tone; title?: string; icon?: IconName; solid?: boolean }) {
  const cls = solid
    ? { neutral: 'bg-muted text-bg border-transparent', accent: 'bg-accent text-accent-ink border-transparent', warn: 'bg-warn text-on-status border-transparent', loss: 'bg-loss text-on-status border-transparent', win: 'bg-win text-on-status border-transparent' }[tone]
    : { neutral: 'border-line text-muted', accent: 'border-accent/50 text-accent bg-accent/5', warn: 'border-warn/50 text-warn bg-warn/5', loss: 'border-loss/50 text-loss', win: 'border-win/50 text-win' }[tone];
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded border px-1.5 text-[12px] font-semibold leading-5 ${cls}`}>
      {icon && <Icon name={icon} />}{children}
    </span>
  );
}

/** Tuttu / Tutmadı: ikon + renk (renk körlüğü için ikon şart). */
export function ResultBadge({ won }: { won: boolean }) {
  return <Badge tone={won ? 'win' : 'loss'} solid icon={won ? 'check' : 'cross'}>{won ? 'Tuttu' : 'Tutmadı'}</Badge>;
}

export const ValueBadge = ({ title }: { title?: string }) => <Badge tone="accent" icon="value" title={title ?? 'Model olasılığı piyasanın belirgin üstünde'}>Değerli</Badge>;
export const DropBadge = ({ children }: { children?: ReactNode }) => <Badge tone="warn" icon="drop" title="Sabahtan bu yana belirgin oran düşüşü">{children ?? 'Düşen oran'}</Badge>;

export function Section({ title, children, aside, id }: { title: string; children: ReactNode; aside?: ReactNode; id?: string }) {
  return (
    <section className="mt-8 scroll-mt-32" id={id}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
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

export function Chevron({ open, size = 16 }: { open: boolean; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} aria-hidden="true"
      className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}><path d="M6 9l6 6 6-6" /></svg>
  );
}
