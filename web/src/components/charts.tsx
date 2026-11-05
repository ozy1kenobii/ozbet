// Hafif SVG/CSS grafikler — dış grafik kütüphanesi yok.
import type { Model } from '../lib/types';
import { pct } from '../lib/format';

/** 1/X/2 yatay yığılmış çubuk */
export function ProbBar({ probs, home, away }: { probs: Model['probs']; home?: string; away?: string }) {
  const p1 = probs['1'] ?? 0, px = probs['X'] ?? 0, p2 = probs['2'] ?? 0;
  const tot = p1 + px + p2 || 1;
  const segs = [
    { k: '1', v: p1, cls: 'bg-accent text-accent-ink', name: home ?? 'Ev' },
    { k: 'X', v: px, cls: 'bg-draw/35 text-ink', name: 'Beraberlik' },
    { k: '2', v: p2, cls: 'bg-ink text-bg', name: away ?? 'Deplasman' },
  ];
  return (
    <div>
      <div className="flex h-7 w-full overflow-hidden rounded-[5px]" role="img"
        aria-label={`Model: ${segs.map((s) => `${s.k} ${pct(s.v)}`).join(', ')}`}>
        {segs.map((s) => (
          <div key={s.k} className={`${s.cls} flex items-center justify-center text-[13px] font-semibold num whitespace-nowrap overflow-hidden`}
            style={{ width: `${(s.v / tot) * 100}%` }}>
            {s.v / tot >= 0.12 ? `${s.k} ${pct(s.v)}` : ''}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Skor olasılık ısı haritası: satır = ev golü, sütun = dep golü */
export function Heatmap({ matrix, home, away }: { matrix: number[][]; home: string; away: string }) {
  const n = 6;
  const max = Math.max(...matrix.flat().map(Number).filter(isFinite), 0.0001);
  return (
    <div className="overflow-x-auto">
      <table className="num mx-auto border-separate" style={{ borderSpacing: 3 }} aria-label="Skor olasılık ısı haritası">
        <caption className="sr-only">Satırlar {home} golü, sütunlar {away} golü</caption>
        <thead>
          <tr>
            <th className="text-[11px] font-medium text-muted text-left pr-1 align-bottom" scope="col">
              <span className="block leading-tight">{abbr(home)} ↓</span>
              <span className="block leading-tight">{abbr(away)} →</span>
            </th>
            {Array.from({ length: n }, (_, a) => <th key={a} scope="col" className="text-xs font-semibold text-muted w-12">{a}</th>)}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: n }, (_, h) => (
            <tr key={h}>
              <th scope="row" className="text-xs font-semibold text-muted pr-1 text-right">{h}</th>
              {Array.from({ length: n }, (_, a) => {
                const v = Number(matrix[h]?.[a] ?? 0);
                const t = Math.sqrt(v / max);
                return (
                  <td key={a} className="h-11 w-12 rounded-[4px] text-center text-[12px] font-medium"
                    style={{ background: `rgb(var(--accent) / ${0.06 + t * 0.94})`, color: t > 0.55 ? 'rgb(var(--accent-ink))' : 'rgb(var(--ink))' }}
                    title={`${h}-${a}: ${pct(v, 1)}`}>
                    {v >= 0.005 ? (v * 100).toLocaleString('tr-TR', { maximumFractionDigits: v >= 0.1 ? 0 : 1, minimumFractionDigits: v >= 0.1 ? 0 : 1 }) : '·'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-center text-xs text-muted">Hücreler yüzde olarak. 5 üstü goller dahil değil.</p>
    </div>
  );
}

function abbr(s: string) { return s.length > 9 ? s.slice(0, 8) + '.' : s; }

/** Dikey çubuklar (toplam gol dağılımı) */
export function Bars({ values, labels }: { values: number[]; labels: string[] }) {
  const max = Math.max(...values, 0.0001);
  return (
    <div className="flex items-end gap-2 h-36" role="img" aria-label={labels.map((l, i) => `${l} gol ${pct(values[i])}`).join(', ')}>
      {values.map((v, i) => (
        <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
          <span className="text-[12px] num text-muted mb-1">{pct(v)}</span>
          <div className="w-full rounded-t-[3px] bg-accent" style={{ height: `${(v / max) * 100}%`, minHeight: 2 }} />
          <span className="mt-1 text-xs font-semibold">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

/** Basit çizgi grafiği (oran hareketi, kasa eğrisi) */
export function LineChart({
  series, height = 120, yFormat = (v: number) => v.toFixed(2), xLabels, baseline, ariaLabel,
}: {
  series: { name: string; values: (number | null)[]; cls: string }[];
  height?: number; yFormat?: (v: number) => string; xLabels?: [string, string]; baseline?: number; ariaLabel: string;
}) {
  const W = 320, H = height, padL = 40, padR = 8, padT = 8, padB = xLabels ? 20 : 8;
  const all = series.flatMap((s) => s.values).filter((v): v is number => v != null && isFinite(v));
  if (baseline != null) all.push(baseline);
  if (!all.length) return null;
  let lo = Math.min(...all), hi = Math.max(...all);
  if (hi - lo < 1e-9) { lo -= 0.05 * (Math.abs(lo) || 1); hi += 0.05 * (Math.abs(hi) || 1); }
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const len = Math.max(...series.map((s) => s.values.length));
  const x = (i: number) => padL + (len <= 1 ? (W - padL - padR) / 2 : (i / (len - 1)) * (W - padL - padR));
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={ariaLabel}>
      <line x1={padL} x2={W - padR} y1={y(hi - pad)} y2={y(hi - pad)} className="stroke-line" strokeDasharray="2 3" />
      <line x1={padL} x2={W - padR} y1={y(lo + pad)} y2={y(lo + pad)} className="stroke-line" strokeDasharray="2 3" />
      <text x={padL - 5} y={y(hi - pad) + 4} textAnchor="end" className="fill-muted" fontSize="10">{yFormat(hi - pad)}</text>
      <text x={padL - 5} y={y(lo + pad) + 4} textAnchor="end" className="fill-muted" fontSize="10">{yFormat(lo + pad)}</text>
      {baseline != null && <line x1={padL} x2={W - padR} y1={y(baseline)} y2={y(baseline)} className="stroke-muted" strokeWidth={1} />}
      {series.map((s) => {
        const pts = s.values.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean);
        const last = [...s.values].reverse().find((v) => v != null);
        const li = s.values.lastIndexOf(last ?? null);
        return (
          <g key={s.name}>
            <polyline points={pts.join(' ')} fill="none" className={s.cls} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {last != null && <circle cx={x(li)} cy={y(last)} r={3} className={s.cls.replace('stroke-', 'fill-')} />}
          </g>
        );
      })}
      {xLabels && (
        <>
          <text x={padL} y={H - 4} className="fill-muted" fontSize="10">{xLabels[0]}</text>
          <text x={W - padR} y={H - 4} textAnchor="end" className="fill-muted" fontSize="10">{xLabels[1]}</text>
        </>
      )}
    </svg>
  );
}

/** Kalibrasyon: tahmin (x) vs gerçekleşen (y), köşegen referans; nokta alanı n'e göre */
export function Calibration({ bins }: { bins: { bin: string; predicted: number; observed: number; n: number }[] }) {
  const S = 260, p = 32;
  const sc = (v: number) => p + v * (S - p - 10);
  const sy = (v: number) => S - p - v * (S - p - 10);
  const maxN = Math.max(...bins.map((b) => b.n), 1);
  const sorted = [...bins].sort((a, b) => a.predicted - b.predicted);
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[340px] h-auto mx-auto" role="img"
      aria-label={`Kalibrasyon: ${sorted.map((b) => `tahmin ${pct(b.predicted)} gerçekleşen ${pct(b.observed)}`).join('; ')}`}>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={sc(0)} x2={sc(1)} y1={sy(t)} y2={sy(t)} className="stroke-line" strokeWidth={0.75} />
          <text x={p - 4} y={sy(t) + 3} textAnchor="end" fontSize="9" className="fill-muted">{t * 100}</text>
          <text x={sc(t)} y={S - p + 13} textAnchor="middle" fontSize="9" className="fill-muted">{t * 100}</text>
        </g>
      ))}
      <line x1={sc(0)} y1={sy(0)} x2={sc(1)} y2={sy(1)} className="stroke-muted" strokeDasharray="4 4" />
      <polyline points={sorted.map((b) => `${sc(b.predicted)},${sy(b.observed)}`).join(' ')} fill="none" className="stroke-accent" strokeWidth={1.5} />
      {sorted.map((b) => (
        <circle key={b.bin} cx={sc(b.predicted)} cy={sy(b.observed)} r={3 + 5 * Math.sqrt(b.n / maxN)} className="fill-accent" fillOpacity={0.85}>
          <title>{`${b.bin}: tahmin ${pct(b.predicted)}, gerçekleşen ${pct(b.observed)}, n=${b.n}`}</title>
        </circle>
      ))}
      <text x={sc(0.5)} y={S - 4} textAnchor="middle" fontSize="10" className="fill-muted">Tahmin edilen %</text>
      <text x={10} y={sy(0.5)} textAnchor="middle" fontSize="10" className="fill-muted" transform={`rotate(-90 10 ${sy(0.5)})`}>Gerçekleşen %</text>
    </svg>
  );
}
