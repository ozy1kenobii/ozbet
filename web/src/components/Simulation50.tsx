// 50 örnek maç akışı: özet, 50 hücreli ızgara, seçilen koşunun gol çizgisi, "Yeniden oynat".
// Yalnızca gösterim içindir; olasılıklar 10.000 simülasyondan gelir. Dış kütüphane yok.
import { useEffect, useRef, useState } from 'react';
import type { SampleGoal, SampleRun, SampleRuns } from '../lib/types';

type Res = '1' | 'X' | '2';
const res = (r: SampleRun): Res => (r.ft[0] > r.ft[1] ? '1' : r.ft[0] === r.ft[1] ? 'X' : '2');

// ProbBar ile aynı renk dili: ev = vurgu, beraberlik = gri, deplasman = mürekkep
const CELL: Record<Res, string> = {
  '1': 'bg-accent text-accent-ink border-accent',
  X: 'bg-draw/30 text-ink border-draw/40',
  '2': 'bg-ink text-bg border-ink',
};
const SYM: Record<Res, string> = { '1': '1', X: '=', '2': '2' };
const RES_LABEL: Record<Res, string> = { '1': 'ev galibiyeti', X: 'beraberlik', '2': 'deplasman galibiyeti' };

function reducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** "45+2" → 45.4 gibi çizgi konumu; 90+e çizginin sağına taşar */
function pos(min: SampleGoal['min']): { x: number; label: string } {
  if (typeof min === 'number') return { x: min, label: `${min}'` };
  const [b, e] = String(min).split('+').map(Number);
  return { x: b === 45 ? 45 + (e || 0) * 0.2 : b + (e || 0), label: `${b}+${e}'` };
}

export function Simulation50({ data, home, away }: { data: SampleRuns; home: string; away: string }) {
  const runs = data.runs ?? [];
  const n = runs.length;
  const [sel, setSel] = useState<number>(0);
  const [shown, setShown] = useState<number>(n);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);
  if (!n) return null;

  const playing = shown < n;
  const replay = () => {
    if (timer.current) window.clearInterval(timer.current);
    if (reducedMotion()) { setShown(n); setSel(n - 1); return; }
    setShown(0);
    let k = 0;
    timer.current = window.setInterval(() => {
      k += 1;
      setShown(k); setSel(k - 1);
      if (k >= n && timer.current) { window.clearInterval(timer.current); timer.current = null; }
    }, 55);
  };

  const s = data.summary;
  const cur = runs[Math.min(sel, n - 1)];
  return (
    <div className="panel p-4">
      {/* Özet */}
      <div className="grid grid-cols-3 gap-2 text-center" role="group" aria-label={`${n} koşunun sonuçları`}>
        {([['1', home, 'bg-accent'], ['X', 'Beraberlik', 'bg-draw/50'], ['2', away, 'bg-ink']] as const).map(([k, name, dot]) => (
          <div key={k} className="rounded-md bg-sunken px-2 py-2 min-w-0">
            <div className="display text-[28px] font-bold leading-none num">{s[k]}</div>
            <div className="mt-1 flex items-center justify-center gap-1 text-[12px] text-muted min-w-0">
              <span className={`h-2 w-2 shrink-0 rounded-sm ${dot}`} aria-hidden="true" />
              <span className="truncate">{name}</span>
            </div>
          </div>
        ))}
      </div>
      <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm num">
        <div className="flex gap-1.5"><dt className="text-muted">2.5 Üst</dt><dd className="font-semibold">{s['O2.5']}/{n}</dd></div>
        <div className="flex gap-1.5"><dt className="text-muted">KG Var</dt><dd className="font-semibold">{s.BTTS_Y}/{n}</dd></div>
        {s.top_scores?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <dt className="text-muted">En sık</dt>
            {s.top_scores.map(([sc, c]) => (
              <dd key={sc} className="rounded border border-line px-1.5 leading-6"><b>{sc}</b> <span className="text-muted">×{c}</span></dd>
            ))}
          </div>
        )}
      </dl>

      {/* Izgara */}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-[12px] text-muted">Bir hücreye dokun: o koşunun gol akışı açılır.</p>
        <button type="button" className="btn btn-ghost shrink-0" onClick={replay} disabled={playing} aria-label="50 koşuyu yeniden oynat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.3-5.7M4 4v4h4" /></svg>
          {playing ? `${shown}/${n}` : 'Yeniden oynat'}
        </button>
      </div>
      <ul className="mt-2 grid grid-cols-10 gap-1" aria-label={`${n} örnek koşu`}>
        {runs.map((r, idx) => {
          const k = res(r);
          const on = idx === sel;
          const vis = idx < shown;
          return (
            <li key={r.i}>
              <button type="button" onClick={() => { setSel(idx); }} aria-pressed={on} disabled={!vis}
                aria-label={`Koşu ${r.i}: ${r.ft[0]}–${r.ft[1]}, ${RES_LABEL[k]}`}
                className={`relative block w-full h-10 rounded-[4px] border text-[12px] font-semibold num leading-none transition-[opacity,transform] duration-150
                  ${vis ? CELL[k] : 'bg-sunken border-line text-transparent'} ${vis ? 'opacity-100 scale-100' : 'opacity-40 scale-90'}
                  ${on && vis ? 'ring-2 ring-offset-1 ring-offset-surface ring-warn' : ''}`}>
                <span className="absolute left-[3px] top-[2px] text-[9px] font-bold opacity-75" aria-hidden="true">{SYM[k]}</span>
                <span className="block pt-2" aria-hidden="true">{r.ft[0]}-{r.ft[1]}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-muted">
        <span><b>1</b> ev kazanır</span><span><b>=</b> beraberlik</span><span><b>2</b> deplasman kazanır</span>
      </p>

      {/* Seçili koşu */}
      {cur && <RunTimeline run={cur} home={home} away={away} />}

      <p className="mt-3 rounded-md bg-sunken px-3 py-2 text-[12px] text-muted">{data.note}</p>
    </div>
  );
}

function RunTimeline({ run, home, away }: { run: SampleRun; home: string; away: string }) {
  const W = 340, padL = 8, padR = 8, X0 = 0, X1 = 96;
  const x = (v: number) => padL + ((v - X0) / (X1 - X0)) * (W - padL - padR);
  // Yakın golleri üst üste bindirmemek için kademe
  const placed: { g: SampleGoal; x: number; label: string; lvl: number; score: string }[] = [];
  let hs = 0, as = 0;
  for (const g of run.goals) {
    const p = pos(g.min);
    if (g.side === 'home') hs++; else as++;
    // aynı taraftaki yakın gol etiketleri çakışmasın: boş ilk kademeyi seç
    const busy = new Set(placed.filter((q) => q.g.side === g.side && Math.abs(q.x - p.x) < 10).map((q) => q.lvl));
    let lvl = 0; while (busy.has(lvl)) lvl++;
    placed.push({ g, x: p.x, label: p.label, lvl: Math.min(lvl, 2), score: `${hs}–${as}` });
  }
  const mid = 50, H = 108;
  return (
    <div className="mt-4 border-t border-line pt-3" aria-live="polite">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="text-[12px] text-muted num">Koşu #{run.i}</span>
        <span className="display text-xl font-semibold num">{home} {run.ft[0]}–{run.ft[1]} {away}</span>
        <span className="text-[12px] text-muted num">İY {run.ht[0]}–{run.ht[1]}</span>
      </div>
      <p className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-muted">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-accent" aria-hidden="true" />{home} üstte</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-ink" aria-hidden="true" />{away} altta</span>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full h-auto" role="img"
        aria-label={run.goals.length ? `Gol akışı: ${placed.map((p) => `${p.label} ${p.g.side === 'home' ? home : away}`).join(', ')}` : 'Golsüz maç'}>
        <rect x={x(0)} y={mid - 2} width={x(90) - x(0)} height={4} rx={2} className="fill-sunken" />
        <rect x={x(90)} y={mid - 2} width={x(X1) - x(90)} height={4} rx={2} className="fill-line" />
        <line x1={x(45.5)} x2={x(45.5)} y1={mid - 9} y2={mid + 9} className="stroke-muted" strokeDasharray="2 2" />
        {[15, 30, 60, 75].map((t) => (
          <line key={t} x1={x(t)} x2={x(t)} y1={mid - 3} y2={mid + 3} className="stroke-line" />
        ))}
        {[0, 15, 30, 45, 60, 75, 90].map((t) => (
          <text key={t} x={x(t === 45 ? 45.5 : t)} y={H - 2} textAnchor={t === 0 ? 'start' : 'middle'} fontSize="8.5" className="fill-muted">
            {t === 45 ? 'İY' : `${t}'`}
          </text>
        ))}
        {placed.map((p, k) => {
          const up = p.g.side === 'home';
          const cx = x(p.x);
          const cy = up ? mid - 13 - p.lvl * 13 : mid + 13 + p.lvl * 13;
          const right = p.x > 78;
          return (
            <g key={k}>
              <line x1={cx} x2={cx} y1={mid} y2={cy} className={up ? 'stroke-accent' : 'stroke-ink'} strokeWidth={1.25} />
              <circle cx={cx} cy={cy} r={4.5} className={up ? 'fill-accent' : 'fill-ink'} />
              <text x={right ? cx - 7 : cx + 7} y={cy + 3} textAnchor={right ? 'end' : 'start'} fontSize="9" className="fill-ink num" fontWeight={600}>{p.label}</text>
            </g>
          );
        })}
      </svg>
      {run.goals.length ? (
        <ol className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[13px] num">
          {placed.map((p, k) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${p.g.side === 'home' ? 'bg-accent' : 'bg-ink'}`} aria-hidden="true" />
              <span className="text-muted">{p.label}</span>
              <span className="font-medium">{p.g.side === 'home' ? home : away}</span>
              <span className="font-semibold">{p.score}</span>
            </li>
          ))}
        </ol>
      ) : <p className="mt-1 text-[13px] text-muted">Bu koşuda gol yok.</p>}
    </div>
  );
}
