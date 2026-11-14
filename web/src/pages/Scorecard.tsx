import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useBacktest, useScorecard } from '../lib/data';
import type { ForecastAgg, ForecastCard, ClvBlock, OddsBandRow, Backtest, BacktestGridRow, BacktestSummary, CalibBin, Scorecard as ScorecardT, ScoreBlock, ShotBlendRow } from '../lib/types';
import { fmtDateTime, fmtShortDate, num, odd, pct, signedNum, signedPct } from '../lib/format';
import { Calibration, LineChart } from '../components/charts';
import { Empty, Loading, ResultBadge, Section } from '../components/ui';
import { marketLabel } from '../lib/markets';
import { comboRoi } from '../lib/coupon';

export default function Scorecard() {
  const sc = useScorecard();
  const bt = useBacktest();
  return (
    <div>
      <h1 className="display text-[32px] font-bold leading-tight">Karne</h1>
      <p className="t-meta">Biten maçlarda OZBET Tercihlerinin sonuçları. Sanal kasa: her tercihe 1 birim. Terimler için <Link to="/rehber" className="text-accent underline underline-offset-2">Rehber</Link>.</p>
      {bt.state === 'ready' && <HonestBox b={bt.data} />}
      <ComboMarginBox />
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

            {d.overall?.n > 0 && d.overall.n < SMALL_N * 3 && (
              <p className="mt-2 t-meta max-w-[68ch]">
                <b className="text-ink">Örneklem küçük ({d.overall.n} tahmin).</b> Bu sayıda sonuçta isabet ve ROI şansla kolayca yön değiştirir; sayıları bir eğilim olarak değil, ara durum olarak okuyun.
              </p>
            )}
            <ForecastBox f={d.forecast} />
            <OddsBands rows={d.by_odds_band} />
            <ClvBox c={d.clv} />

            <AllMarkets d={d} />

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

            <div className="grid gap-x-6 md:grid-cols-2 [&>*]:min-w-0">
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
                        {(r.ev != null || r.clv != null) && (
                          <span className="block t-micro num">
                            {r.ev != null && <>Beklenen değer {signedPct(r.ev)}</>}{r.ev != null && r.clv != null && ' · '}{r.clv != null && <>CLV {signedPct(r.clv)}</>}
                          </span>
                        )}
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
      {bt.state === 'ready' && <BacktestExtras b={bt.data} />}
      <p className="mt-8 t-meta">Marketlerin ve sayıların nasıl okunacağı: <Link to="/rehber" className="text-accent underline underline-offset-2">Rehber</Link>.</p>
    </div>
  );
}

const roiCls = (r: number | null | undefined) => (r == null ? '' : r > 0 ? 'text-win font-semibold' : r < 0 ? 'text-loss' : '');

/** Bu sayının altındaki örneklemler "az örnek" olarak işaretlenir. */
const SMALL_N = 50;
const SmallN = ({ n }: { n: number }) => (n < SMALL_N ? <span className="ml-1 rounded border border-warn/50 px-1 text-[11px] font-semibold text-warn whitespace-nowrap" title={`n < ${SMALL_N}: sonuç şansa çok açık`}>az örnek</span> : null);

function Block({ title, b }: { title: string; b: ScoreBlock | undefined }) {
  if (!b) return null;
  const ci = b.roi_ci;
  const ciSpansZero = ci ? ci[0] <= 0 && ci[1] >= 0 : false;
  return (
    <section className="panel p-4" aria-label={title}>
      <h2 className="display text-lg font-semibold">{title} <span className="text-sm font-medium text-muted num">· {b.n} tahmin</span><SmallN n={b.n} /></h2>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 num">
        <div><dt className="text-[13px] text-muted">İsabet</dt><dd className="display text-[28px] font-bold leading-none">{pct(b.hit_rate, 1)}</dd></div>
        <div>
          <dt className="text-[13px] text-muted">ROI</dt>
          <dd className={`display text-[28px] font-bold leading-none ${roiCls(b.roi)}`}>{signedPct(b.roi)}</dd>
          {ci && <dd className="mt-1 text-[12px] text-muted whitespace-nowrap">aralık {signedPct(ci[0], 0)} … {signedPct(ci[1], 0)}</dd>}
        </div>
        <div><dt className="text-[13px] text-muted">Brier (1X2)</dt><dd className="text-lg font-semibold">{b.brier_1x2 != null ? num(b.brier_1x2, 3) : '–'}</dd></div>
        <div><dt className="text-[13px] text-muted">Sanal kasa kâr</dt><dd className={`text-lg font-semibold ${roiCls(b.profit)}`}>{signedNum(b.profit, 1)} <span className="text-sm text-muted font-normal">/ {b.staked} birim</span></dd></div>
      </dl>
      {ci && (
        <p className="mt-2 t-micro max-w-[60ch]">
          ROI güven aralığı: gerçek uzun dönem getirinin büyük olasılıkla bulunduğu aralık.
          {ciSpansZero ? ' Aralık sıfırı içeriyor; bu örneklemle kâr ya da zarar yönü söylenemez.' : ''}
        </p>
      )}
    </section>
  );
}

/** Oran bandına göre sonuçlar: yüksek isabet, başabaş isabetin altındaysa yine zarar eder. */
function ForecastBox({ f }: { f: ForecastCard | null | undefined }) {
  if (!f || !f.n) return null;
  const rows: [string, ForecastAgg][] = [
    ...f.by_conf.map((r) => [`Maç sonu · güven ${r.conf}`, r] as [string, ForecastAgg]),
    ['Maç sonu · tümü', f], ['2,5 Alt/Üst', f.goals], ['Karşılıklı gol', f.btts], ['Tam skor', f.score],
  ];
  return (
    <Section title="Tahmin isabeti" aside={<span className="text-[12px] text-muted num">{f.n} maç</span>}>
      <div className="panel px-2 py-1 overflow-x-auto">
        <table className="tbl">
          <thead><tr>
            <th>Tahmin</th><th className="text-right">n</th><th className="text-right">İsabet</th>
            <th className="text-right" title="Tahminlerin ortalama olasılığı; isabet buna yakınsa tahmin dürüst demektir">Beklenen</th>
          </tr></thead>
          <tbody>{rows.filter(([, r]) => r && r.n > 0).map(([t, r]) => (
            <tr key={t}>
              <td>{t}</td><td className="text-right num">{r.n}</td>
              <td className="text-right num font-semibold">{r.hit_rate != null ? pct(r.hit_rate) : '–'}
                {r.hit_ci && <span className="block text-[11px] font-normal text-muted">{pct(r.hit_ci[0])}–{pct(r.hit_ci[1])}</span>}</td>
              <td className="text-right num text-muted">{r.avg_p != null ? pct(r.avg_p) : '–'}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="mt-2 t-meta max-w-[68ch]">
        Her maç için verilen maç sonu tahmininin tutma oranı; altındaki aralık %95 güven aralığıdır. Tahmin isabeti kazanç demek değildir:
        yüksek olasılıklı sonuçların oranı düşüktür ve iddaa marjı (~%20) isabetten bağımsız işler.
        {f.n_retro ? ` ${f.n_retro} maç, tahmin bloğu eklenmeden önceki oranlardan geriye dönük puanlandı.` : ''}
      </p>
    </Section>
  );
}

function OddsBands({ rows }: { rows: OddsBandRow[] | null | undefined }) {
  if (!rows?.length) return null;
  return (
    <Section title="Oran bandına göre" aside={<span className="text-[12px] text-muted">1 birim / tahmin</span>}>
      <div className="panel px-2 py-1 overflow-x-auto">
        <table className="tbl">
          <thead><tr>
            <th>Oran bandı</th><th className="text-right">n</th><th className="text-right">İsabet</th>
            <th className="text-right" title="Bu ortalama oranla zarar etmemek için gereken isabet: 1 / ortalama oran">Başabaş</th>
            <th className="text-right">ROI</th>
          </tr></thead>
          <tbody>{rows.map((r) => {
            const be = r.avg_odds ? 1 / r.avg_odds : null;
            const small = r.n < SMALL_N;
            return (
              <tr key={r.band} className={small ? 'text-muted' : ''}>
                <td>
                  <span className="block font-medium whitespace-nowrap">{r.band}</span>
                  <span className="block t-micro whitespace-nowrap">ort. oran {odd(r.avg_odds)}</span>
                </td>
                <td className="text-right whitespace-nowrap">{r.n}{small && <span className="block text-[11px] font-semibold text-warn">az örnek</span>}</td>
                <td className="text-right whitespace-nowrap">{pct(r.hit_rate)}{r.avg_p != null && <span className="block t-micro" title="Modelin ortalama olasılığı">model {pct(r.avg_p)}</span>}</td>
                <td className="text-right">{pct(be)}</td>
                <td className={`text-right ${small ? '' : roiCls(r.roi)}`}>{signedPct(r.roi)}</td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
      <p className="mt-2 t-meta max-w-[68ch]">
        Başabaş = 1 / ortalama oran. İsabet bunun altındaysa, yüzde ne kadar yüksek görünürse görünsün o bant zarar eder. “Az örnek” satırlarında (n &lt; {SMALL_N}) ROI renklendirilmez; birkaç maç sonucu tersine çevirebilir.
      </p>
    </Section>
  );
}

/** Kapanış oranı değeri (CLV) */
function ClvBox({ c }: { c: ClvBlock | null | undefined }) {
  if (!c || !c.n) return null;
  const mk = (c.by_market ?? []).filter((x) => x.n > 0);
  return (
    <Section title="Kapanış oranı değeri (CLV)" aside={<span className="text-[12px] text-muted num">{c.n} tahmin</span>}>
      <div className="panel p-4">
        <p className="text-[14px] max-w-[68ch]">
          CLV, tercihi yayımladığımız andaki oranın maç başlamadan önceki son (kapanış) orana göre ne kadar iyi olduğunu ölçer; artı değer, piyasanın sonradan bizim yönümüze geldiğini gösterir.
        </p>
        <dl className="mt-3 grid grid-cols-3 gap-x-3 num">
          <div><dt className="text-[13px] text-muted">Ortalama CLV</dt><dd className="display text-[26px] font-bold leading-none">{signedPct(c.avg_clv)}</dd></div>
          <div><dt className="text-[13px] text-muted">Kapanışı geçen</dt><dd className="display text-[26px] font-bold leading-none">{pct(c.beat_close_rate)}</dd></div>
          {c.avg_clv_raw != null && <div><dt className="text-[13px] text-muted">Ham CLV</dt><dd className="display text-[26px] font-bold leading-none text-muted">{signedPct(c.avg_clv_raw)}</dd></div>}
        </dl>
        {c.avg_clv_raw != null && <p className="mt-1 t-micro">Ham: oranların doğrudan karşılaştırması. Ortalama CLV: büro marjı ayıklandıktan sonra.</p>}
        {mk.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Market</th><th className="text-right">n</th><th className="text-right">Ort. CLV</th></tr></thead>
              <tbody>{mk.map((x) => (
                <tr key={x.market} className={x.n < SMALL_N ? 'text-muted' : ''}>
                  <td className="font-medium">{x.label || marketLabel(x.market)}<SmallN n={x.n} /></td><td className="text-right">{x.n}</td><td className="text-right">{signedPct(x.avg_clv)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <p className="mt-3 t-meta max-w-[68ch]">
          Sonuçlar şansa çok açıktır; CLV daha az örnekle anlam kazanır ama o da bir gösterge, kâr garantisi değil.{c.n < SMALL_N * 2 ? ` ${c.n} tahmin henüz az; ortalama birkaç maçla değişebilir.` : ''}
        </p>
      </div>
    </Section>
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

/** Kombine marj etkisi: iddaa marjı bacak sayısıyla çarpılır (docs/research/roi-secim.md). */
function ComboMarginBox() {
  const rows = [1, 2, 3, 4, 5];
  return (
    <section className="mt-4 rounded-lg border-2 border-warn/70 bg-surface p-4" aria-label="Kombine marj etkisi">
      <p className="display text-[20px] font-bold leading-tight">Kombine, beklenen kaybı büyütür</p>
      <p className="mt-1 t-meta max-w-[68ch]">
        iddaa 1X2 marjı ≈ %20, 2.5 Alt/Üst ≈ %18. Olasılıklar adil olsa bile her bacak ≈ 1/1,20 dönüş verir ve kombinede bu çarpılır.
      </p>
      <table className="mt-2 text-sm num">
        <thead><tr className="text-muted"><th className="pr-4 text-left font-medium">Bacak</th>{rows.map((n) => <th key={n} className="pr-4 font-medium">{n === 1 ? 'Tekli' : `${n}’li`}</th>)}</tr></thead>
        <tbody>
          <tr><td className="pr-4 text-muted">%20 marj</td>{rows.map((n) => <td key={n} className="pr-4 text-loss">{signedPct(comboRoi(0.2, n))}</td>)}</tr>
          <tr><td className="pr-4 text-muted">%5 marj (iyi büro)</td>{rows.map((n) => <td key={n} className="pr-4">{signedPct(comboRoi(0.05, n))}</td>)}</tr>
        </tbody>
      </table>
      <p className="mt-2 t-meta max-w-[68ch]">
        Kilitli testte (2025–27, 10 lig) en iyi seçim kuralları bile iddaa benzeri fiyatla zarar etti; %70+ olasılıklı seçimler %81 tuttu ama
        tekli ≈ −%10, 2’li ≈ −%19, 3’lü ≈ −%26 getirdi. Yüksek isabet, kâr demek değildir.
      </p>
    </section>
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
          ? 'Geçmiş sezonlarda model olasılıkları kapanış oranlarından daha isabetli çıktı. Geçmiş başarı gelecekte de süreceği anlamına gelmez.'
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
      <div className="grid gap-x-6 lg:grid-cols-2 [&>*]:min-w-0">
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

const MIN_N = 30;

function NotEnough({ n, what }: { n: number; what: string }) {
  return (
    <p className="panel px-4 py-3 text-sm text-muted">
      Henüz yeterli maç yok (n={n}). Karne yeni başladı; {what} ilk anlamlı puanlar birkaç gün içinde oluşacak.
    </p>
  );
}

/** Tüm marketler: kategori tablosu, iki serili kalibrasyon ve değerli bahis karnesi. */
function AllMarkets({ d }: { d: ScorecardT }) {
  const cats = d.by_category ?? [];
  const total = cats.reduce((a, c) => a + c.n, 0);
  const cm = d.calibration_markets;
  const vb = d.value_bets;
  if (!d.by_category && !cm && !vb) return null;
  return (
    <>
      <Section title="Kategori bazında model ve piyasa" aside={<span className="text-[12px] text-muted num">{total} market sonucu</span>}>
        {total < MIN_N ? <NotEnough n={total} what="kategori karşılaştırmasında" /> : (
          <>
            <p className="mb-2 t-meta max-w-[68ch]">Oranı olan bütün marketler (korner ve kart hariç; sonuç verisi yok). Düşük Brier ve log-loss daha iyidir; modelin piyasadan iyi olduğu hücreler yeşil.</p>
            <div className="panel px-2 py-1 overflow-x-auto">
              <table className="tbl min-w-[520px]">
                <thead><tr><th>Kategori</th><th className="text-right">n</th><th className="text-right">Brier model</th><th className="text-right">Brier piyasa</th><th className="text-right">Log-loss model</th><th className="text-right">Log-loss piyasa</th></tr></thead>
                <tbody>{cats.map((c) => (
                  <tr key={c.category}>
                    <td className="font-medium">{c.title}</td><td className="text-right">{c.n}</td>
                    <td className={`text-right ${c.model_brier < c.market_brier ? 'text-win font-semibold' : ''}`}>{num(c.model_brier, 3)}</td>
                    <td className="text-right text-muted">{num(c.market_brier, 3)}</td>
                    <td className={`text-right ${c.model_logloss < c.market_logloss ? 'text-win font-semibold' : ''}`}>{num(c.model_logloss, 3)}</td>
                    <td className="text-right text-muted">{num(c.market_logloss, 3)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            {cats.some((c) => c.n < MIN_N) && <p className="mt-1 t-micro">n &lt; {MIN_N} olan satırlar henüz gürültülü; tek tek yorumlamayın.</p>}
          </>
        )}
      </Section>

      {cm && (
        <Section title="Tüm marketler kalibrasyonu" aside={<span className="text-[12px] text-muted">Kesikli çizgi: ideal</span>}>
          {total < MIN_N ? <NotEnough n={total} what="kalibrasyon grafiğinde" /> : (
            <div className="panel p-4">
              <DualCalibration model={cm.model} market={cm.market} />
              <p className="mt-2 text-[13px] text-muted max-w-[60ch]">Her kova (0–10%, 10–20% …) için ortalama tahmin ve gerçekleşen oran. Nokta köşegene ne kadar yakınsa olasılıklar o kadar gerçekçi. n&lt;5 olan kovalar çizilmez.</p>
            </div>
          )}
        </Section>
      )}

      {vb && (
        <Section title="Değerli bahis karnesi">
          {vb.n < MIN_N ? <NotEnough n={vb.n} what="değerli bahislerde" /> : (
            <div className="panel p-4">
              <dl className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-2 num">
                <div><dt className="text-[13px] text-muted">Bahis</dt><dd className="display text-[26px] font-bold leading-none">{vb.n}</dd></div>
                <div><dt className="text-[13px] text-muted">İsabet</dt><dd className="display text-[26px] font-bold leading-none">{pct(vb.hit_rate, 1)}</dd></div>
                <div><dt className="text-[13px] text-muted">ROI</dt><dd className={`display text-[26px] font-bold leading-none ${roiCls(vb.roi)}`}>{signedPct(vb.roi)}</dd></div>
                <div><dt className="text-[13px] text-muted">Ort. oran</dt><dd className="text-lg font-semibold">{vb.avg_odds != null ? odd(vb.avg_odds) : '–'}</dd></div>
              </dl>
            </div>
          )}
          <p className="mt-2 t-meta max-w-[68ch]">“Değerli” etiketi alan her market, iddaa oranıyla 1 birim oynanmış sayılır. Tercih karnesinden ayrıdır.</p>
        </Section>
      )}
    </>
  );
}

function DualCalibration({ model, market }: { model: CalibBin[]; market: CalibBin[] }) {
  const S = 280, p = 34;
  const sc = (v: number) => p + v * (S - p - 10);
  const sy = (v: number) => S - p - v * (S - p - 10);
  const series = [
    { name: 'Model', bins: model.filter((b) => b.n >= 5), line: 'stroke-accent', fill: 'fill-accent', dash: undefined },
    { name: 'Piyasa', bins: market.filter((b) => b.n >= 5), line: 'stroke-muted', fill: 'fill-muted', dash: '3 2' },
  ];
  return (
    <div>
      <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[360px] h-auto mx-auto" role="img"
        aria-label={series.map((s) => `${s.name}: ${s.bins.map((b) => `tahmin ${pct(b.predicted)} gerçekleşen ${pct(b.observed)}`).join(', ')}`).join('; ')}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={sc(0)} x2={sc(1)} y1={sy(t)} y2={sy(t)} className="stroke-line" strokeWidth={0.75} />
            <text x={p - 4} y={sy(t) + 3} textAnchor="end" fontSize="9" className="fill-muted">{t * 100}</text>
            <text x={sc(t)} y={S - p + 13} textAnchor="middle" fontSize="9" className="fill-muted">{t * 100}</text>
          </g>
        ))}
        <line x1={sc(0)} y1={sy(0)} x2={sc(1)} y2={sy(1)} className="stroke-muted" strokeDasharray="4 4" strokeWidth={1} />
        {series.map((s) => {
          const pts = [...s.bins].sort((a, b) => a.predicted - b.predicted);
          return (
            <g key={s.name}>
              <polyline points={pts.map((b) => `${sc(b.predicted)},${sy(b.observed)}`).join(' ')} fill="none" className={s.line} strokeWidth={1.75} strokeDasharray={s.dash} />
              {pts.map((b) => (
                <circle key={b.bin} cx={sc(b.predicted)} cy={sy(b.observed)} r={s.name === 'Model' ? 4 : 3} className={s.fill}>
                  <title>{`${s.name} ${b.bin}: tahmin ${pct(b.predicted)}, gerçekleşen ${pct(b.observed)}, n=${b.n}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        <text x={sc(0.5)} y={S - 4} textAnchor="middle" fontSize="10" className="fill-muted">Tahmin edilen %</text>
        <text x={10} y={sy(0.5)} textAnchor="middle" fontSize="10" className="fill-muted" transform={`rotate(-90 10 ${sy(0.5)})`}>Gerçekleşen %</text>
      </svg>
      <div className="mt-2 flex justify-center gap-5 text-[13px]">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-accent" />Model</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-muted" />Piyasa (marjsız)</span>
      </div>
    </div>
  );
}

function Compare({ label, a, aName, b, bName, note }: { label: string; a: number; aName: string; b: number; bName: string; note: string }) {
  const better = a < b;
  return (
    <div className="panel p-4">
      <p className="font-semibold">{label}</p>
      <dl className="mt-2 grid grid-cols-2 gap-3 num">
        <div><dt className="text-[13px] text-muted">{aName}</dt><dd className={`text-xl font-bold ${better ? 'text-win' : ''}`}>{num(a, 4)}</dd></div>
        <div><dt className="text-[13px] text-muted">{bName}</dt><dd className={`text-xl font-bold ${!better ? 'text-win' : ''}`}>{num(b, 4)}</dd></div>
      </dl>
      <p className="mt-2 t-meta">Fark {signedNum(a - b, 4)}. {note}</p>
    </div>
  );
}

/** backtest.json yeni alanları: şut harmanı ızgarası, marj yöntemi ve beraberlik düzeltmesi. Alan yoksa gizli. */
function BacktestExtras({ b }: { b: Backtest }) {
  const s = b.summary;
  const grid: ShotBlendRow[] = b.shot_blend ?? [];
  const prop = s?.market_brier_proportional, dc = s?.model_brier_drawcal;
  if (!grid.length && prop == null && dc == null) return null;
  const best = b.shot_blend_best;
  return (
    <div>
      {grid.length > 0 && (
        <Section title="Şut tabanlı güç ağırlığı (w)">
          <p className="mb-2 t-meta max-w-[68ch]">Takım gücü λ = (1−w)·gol + w·şut. Her satır aynı maçlarda farklı w ile modelin skoru; düşük daha iyi.</p>
          <div className="panel px-2 py-1 overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>w</th><th className="text-right">n</th><th className="text-right">Brier 1X2</th><th className="text-right">Log-loss</th><th className="text-right">2.5 Ü/A Brier</th></tr></thead>
              <tbody>{grid.map((g) => (
                <tr key={g.w} className={g.w === best ? 'font-semibold' : ''}>
                  <td>{num(g.w, 2)}{g.w === best && <span className="ml-1.5 rounded bg-accent px-1.5 py-0.5 text-[11px] text-accent-ink">en iyi</span>}</td>
                  <td className="text-right">{g.n.toLocaleString('tr-TR')}</td><td className="text-right">{num(g.brier, 4)}</td>
                  <td className="text-right">{num(g.logloss, 4)}</td><td className="text-right">{num(g.ou25_brier, 4)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
      )}
      {(prop != null || dc != null) && (
        <Section title="Yöntem karşılaştırmaları">
          <div className="grid gap-3 md:grid-cols-2">
            {prop != null && s?.market_brier != null && (
              <Compare label="Piyasa marjı temizleme" aName="Shin" a={s.market_brier} bName="Orantılı" b={prop}
                note="Piyasa olasılığı oranlardan iki yöntemle çıkarıldı; yeşil olan daha isabetli." />
            )}
            {dc != null && s?.model_brier != null && (
              <Compare label="Beraberlik düzeltmesi" aName="Düzeltmeli" a={dc} bName="Ham model" b={s.model_brier}
                note="Modelin beraberlik olasılığı geçmiş verilere göre düzeltildiğinde Brier." />
            )}
          </div>
        </Section>
      )}
    </div>
  );
}
