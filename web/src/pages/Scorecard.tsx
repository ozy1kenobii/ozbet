import { useBacktest, useScorecard } from '../lib/data';
import type { Backtest, BacktestSummary, ScoreBlock } from '../lib/types';
import { fmtDateTime, fmtShortDate, num, odd, pct, signedNum, signedPct } from '../lib/format';
import { Calibration, LineChart } from '../components/charts';
import { Badge, Empty, Loading, Section } from '../components/ui';
import { marketLabel } from '../lib/markets';

export default function Scorecard() {
  const sc = useScorecard();
  const bt = useBacktest();
  return (
    <div>
      <h1 className="display text-[32px] font-bold leading-tight">Karne</h1>
      <p className="text-sm text-muted">Biten maçlarda OZBET Tercihlerinin sonuçları. Sanal kasa: her tercihe 1 birim.</p>
      {sc.state === 'loading' && <div className="mt-4"><Loading /></div>}
      {sc.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {sc.state === 'ready' && (() => {
        const d = sc.data;
        const bank = d.bankroll ?? [];
        return (
          <>
            <p className="mt-1 text-[12px] text-muted num">Güncelleme {fmtDateTime(d.generated_at)}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Block title="Tüm zamanlar" b={d.overall} />
              <Block title="Son 30 gün" b={d.last30} />
            </div>

            {bank.length > 1 && (
              <Section title="Kasa eğrisi">
                <div className="panel p-4">
                  <LineChart ariaLabel="Sanal kasa eğrisi" height={150} baseline={bank[0].balance}
                    series={[{ name: 'Kasa', cls: 'stroke-accent', values: bank.map((b) => b.balance) }]}
                    yFormat={(v) => v.toFixed(0)} xLabels={[fmtShortDate(bank[0].date), fmtShortDate(bank[bank.length - 1].date)]} />
                  <p className="mt-1 text-[12px] text-muted num">Başlangıç {num(bank[0].balance, 0)} → son {num(bank[bank.length - 1].balance, 1)} birim</p>
                </div>
              </Section>
            )}

            {d.calibration?.length > 0 && (
              <Section title="Kalibrasyon" aside={<span className="text-[12px] text-muted">Kesikli çizgi: ideal</span>}>
                <div className="panel p-4">
                  <Calibration bins={d.calibration} />
                  <p className="mt-2 text-[13px] text-muted max-w-[60ch]">Noktalar köşegene ne kadar yakınsa, modelin verdiği yüzdeler o kadar gerçekçi. Nokta büyüklüğü örneklem sayısını gösterir.</p>
                </div>
              </Section>
            )}

            <div className="grid gap-x-6 md:grid-cols-2">
              {d.by_league?.length > 0 && (
                <Section title="Lig bazında">
                  <div className="panel px-2 py-1 overflow-x-auto">
                    <table className="tbl">
                      <thead><tr><th>Lig</th><th className="text-right">n</th><th className="text-right">İsabet</th><th className="text-right">ROI</th></tr></thead>
                      <tbody>{d.by_league.map((l) => (
                        <tr key={l.league}><td className="font-medium">{l.name}</td><td className="text-right">{l.n}</td><td className="text-right">{pct(l.hit_rate)}</td><td className={`text-right ${roiCls(l.roi)}`}>{signedPct(l.roi)}</td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </Section>
              )}
              {d.by_market?.length > 0 && (
                <Section title="Market bazında">
                  <div className="panel px-2 py-1 overflow-x-auto">
                    <table className="tbl">
                      <thead><tr><th>Market</th><th className="text-right">n</th><th className="text-right">İsabet</th><th className="text-right">ROI</th><th className="text-right" title="Kötü giden marketlerde güven katsayısı düşer">Güven kats.</th></tr></thead>
                      <tbody>{d.by_market.map((mk) => (
                        <tr key={mk.market}><td className="font-medium">{mk.label || marketLabel(mk.market)}</td><td className="text-right">{mk.n}</td><td className="text-right">{pct(mk.hit_rate)}</td><td className={`text-right ${roiCls(mk.roi)}`}>{signedPct(mk.roi)}</td><td className={`text-right ${mk.trust < 1 ? 'text-warn font-semibold' : ''}`}>{num(mk.trust)}</td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </Section>
              )}
            </div>

            {d.recent?.length > 0 && (
              <Section title="Son puanlanan tahminler">
                <ul className="panel divide-y divide-line text-sm">
                  {d.recent.map((r, i) => (
                    <li key={i} className="flex items-center gap-3 px-4 py-2.5">
                      <span className="w-20 shrink-0 text-muted num">{fmtShortDate(r.date)}</span>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate font-medium">{r.match}</span>
                        <span className="text-muted num">{r.pick}{r.odds != null && ` · ${odd(r.odds)}`} · {r.score}</span>
                      </span>
                      <Badge tone={r.won ? 'win' : 'loss'}>{r.won ? 'Tuttu' : 'Tutmadı'}</Badge>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </>
        );
      })()}

      {bt.state === 'ready' && <BacktestView b={bt.data} />}
    </div>
  );
}

const roiCls = (r: number | null | undefined) => (r == null ? '' : r > 0 ? 'text-win font-semibold' : r < 0 ? 'text-loss' : '');

function Block({ title, b }: { title: string; b: ScoreBlock | undefined }) {
  if (!b) return null;
  return (
    <section className="panel p-4" aria-label={title}>
      <h2 className="display text-lg font-semibold">{title} <span className="text-sm font-medium text-muted num">· {b.n} tahmin</span></h2>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 num">
        <div><dt className="text-[13px] text-muted">İsabet</dt><dd className="display text-[28px] font-bold leading-none">{pct(b.hit_rate, 1)}</dd></div>
        <div><dt className="text-[13px] text-muted">ROI</dt><dd className={`display text-[28px] font-bold leading-none ${roiCls(b.roi)}`}>{signedPct(b.roi)}</dd></div>
        <div><dt className="text-[13px] text-muted">Brier (1X2)</dt><dd className="text-lg font-semibold">{b.brier_1x2 != null ? num(b.brier_1x2, 3) : '–'}</dd></div>
        <div><dt className="text-[13px] text-muted">Sanal kasa kâr</dt><dd className={`text-lg font-semibold ${roiCls(b.profit)}`}>{signedNum(b.profit, 1)} <span className="text-sm text-muted font-normal">/ {b.staked} birim</span></dd></div>
      </dl>
    </section>
  );
}

function BtRow({ name, s }: { name: string; s: BacktestSummary }) {
  const better = (a: number | null, b: number | null) => a != null && b != null && a < b;
  return (
    <tr>
      <td className="font-medium">{name}</td>
      <td className="text-right">{s.n}</td>
      <td className={`text-right ${better(s.model_brier, s.market_brier) ? 'text-win font-semibold' : ''}`}>{s.model_brier != null ? num(s.model_brier, 3) : '–'}</td>
      <td className="text-right text-muted">{s.market_brier != null ? num(s.market_brier, 3) : '–'}</td>
      <td className={`text-right ${better(s.model_logloss, s.market_logloss) ? 'text-win font-semibold' : ''}`}>{s.model_logloss != null ? num(s.model_logloss, 3) : '–'}</td>
      <td className="text-right text-muted">{s.market_logloss != null ? num(s.market_logloss, 3) : '–'}</td>
      <td className={`text-right ${s.roi_value_bets != null ? roiCls(s.roi_value_bets) : ''}`}>{s.roi_value_bets != null ? signedPct(s.roi_value_bets) : '–'}</td>
      <td className="text-right">{s.n_value_bets}</td>
    </tr>
  );
}

function BacktestView({ b }: { b: Backtest }) {
  return (
    <Section title="Backtest (geçmiş 2 sezon)" aside={<span className="text-[12px] text-muted num">{fmtDateTime(b.generated_at)}</span>}>
      <p className="mb-2 text-[13px] text-muted">Sezonlar: {b.seasons?.join(', ') || '–'} · Ligler: {b.leagues?.join(', ') || '–'}. Düşük Brier ve log-loss daha iyidir; modelin piyasayı geçtiği hücreler yeşil.</p>
      <div className="panel px-2 py-1 overflow-x-auto">
        <table className="tbl min-w-[640px]">
          <thead><tr><th>Kapsam</th><th className="text-right">n</th><th className="text-right">Brier model</th><th className="text-right">Brier piyasa</th><th className="text-right">Log-loss model</th><th className="text-right">Log-loss piyasa</th><th className="text-right">Değerli ROI</th><th className="text-right">Değerli n</th></tr></thead>
          <tbody>
            {b.summary && <BtRow name="Genel" s={b.summary} />}
            {b.by_league?.map((l) => <BtRow key={l.league} name={l.name ?? l.league} s={l} />)}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
