const TZ = 'Europe/Istanbul';

const timeFmt = new Intl.DateTimeFormat('tr-TR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
const dateTimeFmt = new Intl.DateTimeFormat('tr-TR', {
  timeZone: TZ, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
});
const longDateFmt = new Intl.DateTimeFormat('tr-TR', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const shortDateFmt = new Intl.DateTimeFormat('tr-TR', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' });

function safe(d: string | null | undefined): Date | null {
  if (!d) return null;
  const x = new Date(d);
  return isNaN(x.getTime()) ? null : x;
}

export const fmtTime = (iso: string | null | undefined) => { const d = safe(iso); return d ? timeFmt.format(d) : '–'; };
export const fmtDateTime = (iso: string | null | undefined) => { const d = safe(iso); return d ? dateTimeFmt.format(d) : '–'; };
/** "2026-11-05" → "Perşembe, 5 Kasım" */
export const fmtDay = (ymd: string) => { const d = safe(ymd + 'T12:00:00Z'); return d ? longDateFmt.format(d) : ymd; };
/** Bugün/Yarın/2 gün sonra etiketi (İstanbul saatine göre), yoksa boş. */
export function relDay(ymd: string): string {
  const now = new Date(Date.now() + 3 * 3600_000).toISOString().slice(0, 10);
  const diff = Math.round((Date.parse(ymd + 'T00:00:00Z') - Date.parse(now + 'T00:00:00Z')) / 86400_000);
  return diff === 0 ? 'Bugün' : diff === 1 ? 'Yarın' : diff === 2 ? '2 gün sonra' : diff === -1 ? 'Dün' : '';
}
export const fmtShortDate = (ymd: string) => { const d = safe(ymd.slice(0, 10) + 'T12:00:00Z'); return d ? shortDateFmt.format(d) : ymd; };

export function pct(p: number | null | undefined, digits = 0): string {
  if (p == null || !isFinite(p)) return '–';
  return `%${(p * 100).toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function signedPct(p: number | null | undefined, digits = 1): string {
  if (p == null || !isFinite(p)) return '–';
  const s = p > 0 ? '+' : p < 0 ? '−' : '';
  return `${s}%${Math.abs(p * 100).toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function num(n: number | null | undefined, digits = 2): string {
  if (n == null || !isFinite(n)) return '–';
  return n.toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !isFinite(n)) return '–';
  const s = n > 0 ? '+' : n < 0 ? '−' : '';
  return s + Math.abs(n).toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function odd(n: number | null | undefined): string {
  return num(n, 2);
}

const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', hourCycle: 'h23' });
/** Europe/Istanbul saatine göre saat (0–23); geçersizse null */
export const istHour = (iso: string | null | undefined) => { const d = safe(iso); return d ? Number(hourFmt.format(d)) : null; };
