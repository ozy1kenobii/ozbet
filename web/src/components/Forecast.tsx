import type { Forecast, ForecastConf, Match } from '../lib/types';
import { pct } from '../lib/format';
import { Badge, ResultBadge } from './ui';

/** Tahmin Motoru çıktısı: her maç için oranlardan çözülen maç sonu tahmini (olasılıktır, kesinlik değil). */
export const OUTCOME_SHORT: Record<string, string> = { '1': 'MS 1', X: 'MS X', '2': 'MS 2' };
export const CONF_LABEL: Record<ForecastConf, string> = { 'yüksek': 'Güven yüksek', orta: 'Güven orta', 'düşük': 'Güven düşük' };
const CONF_TONE: Record<ForecastConf, 'accent' | 'neutral' | 'warn'> = { 'yüksek': 'accent', orta: 'neutral', 'düşük': 'warn' };
export const CONF_EXPLAIN =
  'Güven, tahmin edilen sonucun olasılığına göre verilir: yüksek %60 ve üzeri, orta %45–60, düşük %45 altı. Geçmiş ölçümde yüksek güvenli tahminlerin yaklaşık dörtte üçü, düşük güvenlilerin yaklaşık beşte ikisi tuttu. Olasılıktır; kesinlik değildir.';
const BASIS: Record<string, string> = {
  piyasa: 'iddaa oranlarından çözüldü',
  'piyasa+model': 'iddaa oranları + lig modeli',
  model: 'lig modeli (oran yok)',
  'kısmi': 'maç sonu oranı yok; eldeki marketlerden kısmi çözüm',
};
export const basisText = (f: Forecast) => BASIS[f.basis] ?? f.basis;

export function outcomeName(f: Forecast, m: Match): string {
  return f.outcome === '1' ? m.home.name : f.outcome === '2' ? m.away.name : 'Beraberlik';
}

/** Biten maçta tahmin tuttu mu (maç sonu). */
export function forecastHit(m: Match): boolean | null {
  const f = m.forecast;
  if (!f || m.status !== 'finished' || !m.result) return null;
  const [h, a] = m.result.ft;
  return f.outcome === (h > a ? '1' : h === a ? 'X' : '2');
}

const goalsLabel = (k: string) => (k === 'O2.5' ? '2,5 Üst' : '2,5 Alt');
const bttsLabel = (k: string) => (k === 'BTTS_Y' ? 'KG Var' : 'KG Yok');

/** 1-X-2 olasılık çubuğu */
export function ProbBar({ f }: { f: Forecast }) {
  const seg = (k: '1' | 'X' | '2') => (
    <span key={k} style={{ width: `${Math.max(4, f.probs[k] * 100)}%` }}
      className={`h-full ${f.outcome === k ? 'bg-accent' : 'bg-ink/15'} ${k === 'X' ? 'mx-px' : ''}`} />
  );
  return (
    <span className="flex h-1.5 w-full overflow-hidden rounded-full" role="img"
      aria-label={`Ev sahibi ${pct(f.probs['1'])}, beraberlik ${pct(f.probs.X)}, deplasman ${pct(f.probs['2'])}`}>
      {(['1', 'X', '2'] as const).map(seg)}
    </span>
  );
}

/** Maç kartındaki tahmin bloğu */
export function ForecastStrip({ m }: { m: Match }) {
  const f = m.forecast;
  if (!f) return null;
  const hit = forecastHit(m);
  return (
    <span className="block rounded-md bg-ink/[.04] px-2.5 pt-2 pb-2">
      <span className="flex items-center gap-2">
        <span className="t-micro shrink-0">Tahmin</span>
        <span className="display text-[19px] font-bold leading-none truncate">{OUTCOME_SHORT[f.outcome]} · {outcomeName(f, m)}</span>
        <span className="ml-auto shrink-0 display text-[22px] font-bold leading-none num">{pct(f.p)}</span>
      </span>
      <span className="mt-1.5 block"><ProbBar f={f} /></span>
      <span className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-muted num">
        {hit != null ? <ResultBadge won={hit} /> : <Badge tone={CONF_TONE[f.confidence]} title={CONF_EXPLAIN}>{CONF_LABEL[f.confidence]}</Badge>}
        {f.scores?.[0] && <span>Skor <b className="text-ink font-semibold">{f.scores[0].score}</b> {pct(f.scores[0].p)}</span>}
        {f.goals && <span>{goalsLabel(f.goals.market)} {pct(f.goals.p)}</span>}
        {f.btts && <span>{bttsLabel(f.btts.market)} {pct(f.btts.p)}</span>}
        {f.move && <span className={f.move.delta > 0 ? 'text-ink' : 'text-warn'} title="Oran hareketi: tahmin edilen sonucun olasılığı açılıştan bu yana">{f.move.delta > 0 ? '↑' : '↓'} {Math.abs(f.move.delta * 100).toFixed(1)} puan</span>}
      </span>
    </span>
  );
}

/** Maç detayındaki tahmin paneli */
export function ForecastPanel({ m }: { m: Match }) {
  const f = m.forecast;
  if (!f) return null;
  const hit = forecastHit(m);
  const rows: [string, string, number][] = [
    ['1', m.home.name, f.probs['1']], ['X', 'Beraberlik', f.probs.X], ['2', m.away.name, f.probs['2']],
  ];
  return (
    <section className="panel px-4 py-3.5" aria-labelledby="tahmin-baslik">
      <div className="flex items-center gap-2">
        <h2 id="tahmin-baslik" className="h-section">Maç sonu tahmini</h2>
        <span className="ml-auto">{hit != null ? <ResultBadge won={hit} /> : <Badge tone={CONF_TONE[f.confidence]} title={CONF_EXPLAIN}>{CONF_LABEL[f.confidence]}</Badge>}</span>
      </div>
      <p className="mt-2 flex items-baseline gap-2.5">
        <span className="display text-[26px] font-bold leading-tight">{OUTCOME_SHORT[f.outcome]} · {outcomeName(f, m)}</span>
        <span className="ml-auto display text-[30px] font-bold leading-none num">{pct(f.p)}</span>
      </p>
      <dl className="mt-3 space-y-1.5">
        {rows.map(([k, name, p]) => (
          <div key={k} className="flex items-center gap-2 text-[14px]">
            <dt className={`w-[42%] truncate ${f.outcome === k ? 'font-semibold' : 'text-muted'}`}>{name}</dt>
            <dd className="flex-1 flex items-center gap-2">
              <span className="h-2 flex-1 rounded-full bg-ink/10 overflow-hidden"><span className={`block h-full ${f.outcome === k ? 'bg-accent' : 'bg-ink/30'}`} style={{ width: `${p * 100}%` }} /></span>
              <span className="w-10 text-right num">{pct(p)}</span>
            </dd>
          </div>
        ))}
      </dl>
      <dl className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[14px] sm:grid-cols-4">
        {f.scores && <div><dt className="t-micro">En olası skorlar</dt><dd className="num">{f.scores.map((s) => `${s.score} ${pct(s.p)}`).join(' · ')}</dd></div>}
        {f.xg && <div><dt className="t-micro">Gol beklentisi</dt><dd className="num">{f.xg[0].toFixed(2)} – {f.xg[1].toFixed(2)}</dd></div>}
        {f.goals && <div><dt className="t-micro">Toplam gol</dt><dd className="num">{goalsLabel(f.goals.market)} {pct(f.goals.p)}</dd></div>}
        {f.btts && <div><dt className="t-micro">Karşılıklı gol</dt><dd className="num">{bttsLabel(f.btts.market)} {pct(f.btts.p)}</dd></div>}
        {f.dc && <div><dt className="t-micro">En olası çifte şans</dt><dd className="num">{f.dc.market} {pct(f.dc.p)}</dd></div>}
        {f.move && <div><dt className="t-micro">Oran hareketi</dt><dd className="num">Tahmin {f.move.dir} ({f.move.delta > 0 ? '+' : '−'}{Math.abs(f.move.delta * 100).toFixed(1)} puan)</dd></div>}
      </dl>
      <p className="mt-3 t-meta">
        Kaynak: {basisText(f)}. En olası skor bile genelde %10–15 olasılıktadır. {CONF_EXPLAIN}
      </p>
    </section>
  );
}
