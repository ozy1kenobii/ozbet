import { useState } from 'react';
import { useBacktest, useScorecard } from '../lib/data';
import type { Backtest, BacktestGridRow, BacktestSummary, ScoreBlock } from '../lib/types';
import { fmtDateTime, fmtShortDate, num, odd, pct, signedNum, signedPct } from '../lib/format';
import { Calibration, LineChart } from '../components/charts';
import { Empty, Loading, ResultBadge, Section } from '../components/ui';
import { marketLabel } from '../lib/markets';

export default function Scorecard() {
  const sc = useScorecard();
  const bt = useBacktest();
  return (
    <div>
      <h1 className="display text-[32px] font-bold leading-tight">Karne</h1>
      <p className="t-meta">Biten maçlarda OZBET Tercihlerinin sonuçları. Sanal kasa: her tercihe 1 birim.</p>
      {bt.state === 'ready' && <HonestBox b={bt.data} />}
      {(sc.state === 'loading' || bt.state === 'loading') && <div className="mt-4"><Loading variant="page" /></div>}
      {sc.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {sc.state === 'ready' && (() => {
        const d = sc.data;
        if (!d.overall?.n && !d.recent?.length) {
          return <div className="mt-4"><Empty title="Henüz puanlanan tahmin yok">Maçlar bittikçe OZBET Tercihlerinin sonuçları burada birikecek. Aşağıdaki backtest, modelin geçmiş sezonlardaki durumunu gösteriyor.</Empty></div>;
        }
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
                      <ResultBadge won={r.won} />
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

/** Dürüst özet: model piyasa kapanış oranlarını yenebildi mi? */
function HonestBox({ b }: { b: Backtest }) {
  const s = b.summary;
  if (!s || s.model_brier == null || s.market_brier == null) return null;
  const beat = s.model_brier < s.market_brier;
  const roi = s.roi_value_bets;
  return (
    <section className={`mt-4 rounded-lg border-2 p-4 ${beat ? 'border-win/60' : 'border-warn/70'} bg-surface`} aria-label="Model performansı özeti">
      <p className="display text-[22px] md:text-[26px] font-bold leading-tight">
        {beat ? 'Model piyasa kapanış oranlarını yendi' : 'Model piyasa kapanış oranlarını yenemedi'}
      </p>
      <p className="mt-1 text-[15px] num">
        Brier model <b>{num(s.model_brier, 3)}</b> / piyasa <b>{num(s.market_brier, 3)}</b>
        <span className="text-muted"> · düşük olan daha iyi · {s.n.toLocaleString('tr-TR')} maç</span>
      </p>
      <p className="mt-2 t-meta max-w-[68ch]">
        {beat
          ? 'Geçmiş sezonlarda model olasılıkları kapanış oranlarından daha isabetli çıktı. Yine de bu geleceği garanti etmez.'
          : `Geçmiş ${b.seasons?.length ?? ''} sezonda modelin olasılıkları, bürolara göre daha az isabetliydi${roi != null ? ` ve “değerli” etiketli bahisler ${signedPct(roi)} getiri verdi (${s.n_value_bets.toLocaleString('tr-TR')} bahis)` : ''}. Tercihleri bir görüş olarak okuyun, oranları her zaman piyasayla karşılaştırın.`}
      </p>
    </section>
  );
}

const fmtAlpha = (a: number | string) => {
  const v = Number(a);
  return v === 1 ? 'Yalnız model' : `%${Math.round(v * 100)} model`;
};

function BlendTable({ blend, market }: { blend: Record<string, number>; market: number | null }) {
  const rows = Object.entries(blend).map(([a, v]) => ({ a: Number(a), v })).filter((r) => isFinite(r.a) && r.v != null).sort((x, y) => y.a - x.a);
  if (!rows.length) return null;
  const best = Math.min(...rows.map((r) => r.v));
  return (
    <div className="panel px-2 py-1 overflow-x-auto">
      <table className="tbl">
        <thead><tr><th>Karışım (α)</th><th className="text-right">Brier</th><th className="text-right">Piyasaya fark</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.a}>
              <td className="font-medium">{fmtAlpha(r.a)}<span className="text-muted font-normal"> · α {num(r.a, 2)}</span></td>
              <td className={`text-right ${r.v === best ? 'font-bold' : ''}`}>{num(r.v, 4)}</td>
              <td className={`text-right ${market != null && r.v < market ? 'text-win font-semibold' : 'text-muted'}`}>{market != null ? signedNum(r.v - market, 4) : '–'}</td>
            </tr>
          ))}
          {market != null && <tr><td className="text-muted">Piyasa kapanış</td><td className="text-right text-muted">{num(market, 4)}</td><td /></tr>}
        </tbody>
      </table>
    </div>
  );
}

function GridTable({ grid }: { grid: BacktestGridRow[] }) {
  const alphas = [...new Set(grid.map((g) => g.alpha))].sort((a, b) => b - a);
  const edges = [...new Set(grid.map((g) => g.edge))].sort((a, b) => a - b);
  const cell = (a: number, e: number) => grid.find((g) => g.alpha === a && g.edge === e);
  return (
    <div className="panel px-2 py-1 overflow-x-auto">
      <table className="tbl min-w-[420px]">
        <thead>
          <tr><th>α / eşik</th>{edges.map((e) => <th key={e} className="text-right">≥ {pct(e, 0)}</th>)}</tr>
        </thead>
        <tbody>
          {alphas.map((a) => (
            <tr key={a}>
              <th scope="row" className="font-medium text-ink whitespace-nowrap">{num(a, 2)}</th>
              {edges.map((e) => {
                const c = cell(a, e);
                return (
                  <td key={e} className="text-right whitespace-nowrap">
                    {c && c.bets > 0 ? (
                      <>
                        <span className={`block font-semibold ${roiCls(c.roi)}`}>{signedPct(c.roi)}</span>
                        <span className="block t-micro">{c.bets.toLocaleString('tr-TR')} bahis</span>
                      </>
                    ) : <span className="text-muted">–</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BacktestView({ b }: { b: Backtest }) {
  const scopes = [
    { id: '', name: 'Genel', blend: b.blend_brier, grid: b.grid, market: b.summary?.market_brier ?? null },
    ...(b.by_league ?? []).map((l) => ({ id: l.league, name: l.name ?? l.league, blend: l.blend_brier, grid: l.grid, market: l.market_brier })),
  ].filter((x) => (x.blend && Object.keys(x.blend).length) || x.grid?.length);
  const [scopeId, setScopeId] = useState('');
  const sc = scopes.find((x) => x.id === scopeId) ?? scopes[0];
  return (
    <>
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
      {b.method && <p className="mt-2 t-meta max-w-[68ch]">{b.method}</p>}
    </Section>

    {sc && scopes.length > 1 && (
      <div className="mt-8 flex items-center gap-2">
        <label htmlFor="bt-kapsam" className="t-meta">Kapsam</label>
        <select id="bt-kapsam" value={sc.id} onChange={(e) => setScopeId(e.target.value)}
          className="min-h-[44px] rounded-md border border-line bg-surface px-3 text-[15px] font-medium">
          {scopes.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
      </div>
    )}
    {sc && (
      <div className="grid gap-x-6 lg:grid-cols-2">
        {sc.blend && Object.keys(sc.blend).length > 0 && (
          <Section title="Model–piyasa karışımı">
            <p className="mb-2 t-meta">α, model olasılığının ağırlığı; kalanı piyasa kapanış olasılığı. Brier ne kadar düşükse o kadar isabetli.</p>
            <BlendTable blend={sc.blend} market={sc.market ?? null} />
          </Section>
        )}
        {sc.grid && sc.grid.length > 0 && (
          <Section title="Değer eşiği taraması">
            <p className="mb-2 t-meta">Her hücre: α karışımı ve en az bu fark (model − piyasa) ile seçilen bahislerin getirisi.</p>
            <GridTable grid={sc.grid} />
          </Section>
        )}
      </div>
    )}
    </>
  );
}
