import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useDay } from '../lib/data';
import type { OddsAnalysis, CountPrediction, HtFtKey, MarketCategory, MarketKey, Match, TeamStats } from '../lib/types';
import { fmtDateTime, fmtShortDate, fmtTime, num, odd, pct, signedPct } from '../lib/format';
import { HTFT_KEYS, MARKET_GROUPS, allProbs, marketLabel, setMarketLabels } from '../lib/markets';
import { useCoupon } from '../lib/coupon';
import { Bars, Heatmap, LineChart, ProbBar } from '../components/charts';
import { Badge, DropBadge, Empty, FormStrip, Loading, ResultBadge, Section, Stars, ValueBadge } from '../components/ui';
import { AddToCoupon } from '../components/AddToCoupon';
import { PROV_LABEL, pickResult } from '../components/MatchCard';
import { Simulation50 } from '../components/Simulation50';
import { NewsList } from '../components/NewsList';
import { OddsArchiveDetail } from '../components/OddsArchive';
import { H2HSummaryStrip, StandingsSection, TrendsSection } from '../components/FormExtras';
import type { LeagueStandings } from '../lib/types';

export default function MatchDetail() {
  const { date = '', id = '' } = useParams();
  const day = useDay(date);
  if (day.state === 'loading') return <Loading variant="detail" />;
  if (day.state === 'empty') return <Empty />;
  const m = day.data.matches?.find((x) => x.id === decodeURIComponent(id));
  if (!m) return <Empty title="Maç bulunamadı">Bu gün dosyasında böyle bir maç yok. <Link className="text-accent font-semibold" to="/">Bültene dön</Link></Empty>;
  setMarketLabels(day.data.market_labels);
  return <Detail m={m} date={day.data.date} cats={day.data.market_categories} table={day.data.standings?.[m.league]} />;
}

/**
 * Bölüm atlama sekmeleri. Her sekme, DOM'daki ilk mevcut çapaya gider;
 * hiçbiri yoksa sekme gizlenir (ör. Simulation50 / NewsList henüz eklenmemişse).
 */
const TABS: { label: string; anchors: string[] }[] = [
  { label: 'Özet', anchors: ['ozet'] },
  { label: 'Olasılıklar', anchors: ['olasiliklar'] },
  { label: 'Simülasyon', anchors: ['sim50'] },
  { label: 'Form', anchors: ['form'] },
  { label: 'Kadro/Haber', anchors: ['kadro', 'haberler'] },
  { label: 'Kaynaklar', anchors: ['kaynaklar'] },
];
const STICKY_OFFSET = 128; // uygulama başlığı (56) + yapışkan maç başlığı

function useSectionTabs(root: React.RefObject<HTMLElement>) {
  const [avail, setAvail] = useState<{ label: string; id: string }[]>([]);
  const [active, setActive] = useState<string>('ozet');
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const scan = () => {
      const next = TABS.map((t) => ({ label: t.label, id: t.anchors.find((a) => el.querySelector(`#${a}`)) ?? '' })).filter((t) => t.id);
      setAvail((prev) => (prev.map((p) => p.id).join() === next.map((p) => p.id).join() ? prev : next));
    };
    scan();
    // Sonradan eklenen bölümler (lazy bileşenler) için DOM'u izle
    const mo = new MutationObserver(scan);
    mo.observe(el, { childList: true, subtree: true });
    return () => mo.disconnect();
  }, [root]);
  useEffect(() => {
    const onScroll = () => {
      let cur = avail[0]?.id ?? '';
      for (const t of avail) {
        const n = document.getElementById(t.id);
        if (n && n.getBoundingClientRect().top - STICKY_OFFSET - 8 <= 0) cur = t.id;
      }
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4 && avail.length) cur = avail[avail.length - 1].id;
      setActive(cur);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [avail]);
  return { avail, active };
}

function Detail({ m, date, cats, table }: { m: Match; date: string; cats?: MarketCategory[]; table?: LeagueStandings }) {
  const finished = m.status === 'finished' && m.result;
  const rootRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLElement>(null);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const { avail, active } = useSectionTabs(rootRef);
  const [compact, setCompact] = useState(false);
  const won = pickResult(m);

  useEffect(() => {
    const h = headRef.current;
    if (!h || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => setCompact(!e.isIntersecting), { rootMargin: '-56px 0px 0px 0px' });
    io.observe(h);
    return () => io.disconnect();
  }, []);
  // Etkin sekmeyi yatay şeritte görünür tut
  useEffect(() => {
    const b = tabBarRef.current?.querySelector<HTMLElement>(`[data-tab="${active}"]`);
    const bar = tabBarRef.current;
    if (b && bar) bar.scrollTo({ left: b.offsetLeft - bar.clientWidth / 2 + b.clientWidth / 2, behavior: 'auto' });
  }, [active]);

  const jump = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - STICKY_OFFSET + 4, behavior: reduce ? 'auto' : 'smooth' });
  };

  const hasStats = !!m.stats;
  const hasSquad = !!m.squad && !!(m.squad.home || m.squad.away);
  const hasConsensus = !!m.consensus && ((m.consensus.sources?.length ?? 0) > 0 || (m.consensus.summary?.length ?? 0) > 0);
  const hasProv = !!m.provenance && Object.keys(m.provenance).length > 0;

  return (
    <div ref={rootRef}>
      <Link to={date ? `/gun/${date}` : '/'} className="tap -ml-1 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
        Bülten
      </Link>

      {/* Büyük başlık */}
      <header ref={headRef}>
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 t-meta">
          <span className="font-semibold text-ink">{m.league_name}</span>
          <span className="num">{fmtDateTime(m.kickoff)}</span>
          {m.code && <span className="num">Kod {m.code}</span>}
          {m.mbs != null && <span className="num">MBS {m.mbs}</span>}
          {m.status === 'live' && <Badge tone="loss" icon="live">Canlı</Badge>}
        </div>
        <div className="mt-1.5 flex items-center gap-3">
          <h1 className="display flex-1 min-w-0 text-[30px] md:text-[42px] leading-[1.05] font-bold">
            <span className="block truncate">{m.home.name}</span>
            <span className="block truncate">{m.away.name}</span>
          </h1>
          {finished ? (
            <div className="text-right">
              <div className="display text-[42px] md:text-[54px] font-bold leading-none num">{m.result!.ft[0]}–{m.result!.ft[1]}</div>
              {m.result!.ht && <div className="t-meta num">İY {m.result!.ht[0]}–{m.result!.ht[1]}</div>}
            </div>
          ) : (
            <AddToCoupon match={m} date={date} />
          )}
        </div>
      </header>

      {/* Yapışkan maç başlığı + bölüm sekmeleri */}
      <div className="sticky top-14 z-20 -mx-4 mt-3 bg-bg/95 backdrop-blur border-b border-line">
        <div className={`px-4 overflow-hidden transition-[max-height,opacity] duration-200 ${compact ? 'max-h-12 opacity-100' : 'max-h-0 opacity-0'}`} aria-hidden={!compact}>
          <div className="flex items-center gap-2 h-10 text-[14px]">
            <span className="num t-meta shrink-0">{m.status === 'live' ? 'Canlı' : fmtTime(m.kickoff)}</span>
            <span className="min-w-0 truncate font-semibold">{m.home.name} – {m.away.name}</span>
            {finished && <span className="display font-bold text-lg num shrink-0">{m.result!.ft[0]}–{m.result!.ft[1]}</span>}
            {m.pick && (
              <span className="ml-auto shrink-0 flex items-center gap-1.5">
                <span className="display text-[16px] font-bold">{m.pick.label || marketLabel(m.pick.market)}</span>
                {won != null ? <ResultBadge won={won} /> : <Stars n={m.pick.stars} size={11} />}
              </span>
            )}
          </div>
        </div>
        {avail.length > 1 && (
          <nav aria-label="Bölümler">
            <div ref={tabBarRef} className="flex overflow-x-auto no-scrollbar px-2">
              {avail.map((t) => (
                <button key={t.id} data-tab={t.id} onClick={() => jump(t.id)} aria-current={active === t.id ? 'true' : undefined}
                  className={`shrink-0 min-h-[44px] px-3 text-[14px] font-semibold border-b-2 -mb-px ${active === t.id ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink'}`}>
                  {t.label}
                </button>
              ))}
            </div>
          </nav>
        )}
      </div>

      {/* ÖZET */}
      <section id="ozet" className="scroll-mt-32" aria-label="Özet">
        <PickBox m={m} />
        {finished && <div className="mt-3"><AddToCoupon match={m} date={date} /></div>}
        {m.comment && (
          <div className="mt-4">
            <p className="text-[16px] leading-relaxed max-w-[68ch]">{m.comment}</p>
            <p className="mt-1 t-micro">{m.comment_source === 'llm' ? 'Dil modeli yorumu' : 'Kural tabanlı yorum'}</p>
          </div>
        )}
      </section>

      {/* OLASILIKLAR */}
      <section id="olasiliklar" className="scroll-mt-32" aria-label="Olasılıklar">
        {m.model ? <ModelSections m={m} /> : (
          <p className="mt-6 rounded-md bg-sunken px-4 py-3 text-sm text-muted">Veri yetersiz – model çalıştırılmadı. Aşağıda yalnızca piyasa oranları var.</p>
        )}
        <CountsPanel m={m} />
        <MarketTable m={m} date={date} cats={cats} />
        <OddsArchive m={m} />
        <OddsMovement m={m} />
      </section>

      {/* SİMÜLASYON: <section id="sim50"> Olasılıklar bölümündeki model bloğunun içinde render edilir. */}

      {/* FORM */}
      {(hasStats || (m.trends?.length ?? 0) > 0) && (
        <section id="form" className="scroll-mt-32" aria-label="Form ve istatistik">
          <StandingsSection m={m} table={table} />
          <TrendsSection m={m} date={date} />
          <StatsSection m={m} />
        </section>
      )}

      {/* KADRO / HABER */}
      {hasSquad && (
        <section id="kadro" className="scroll-mt-32" aria-label="Kadro">
          <SquadSection m={m} />
        </section>
      )}
      {/* HABERLER — kendi kökü <section id="haberler">; veri yoksa render edilmez */}
      <NewsList m={m} />

      {/* KAYNAKLAR */}
      {(hasConsensus || hasProv || (m.model?.notes?.length ?? 0) > 0) && (
        <section id="kaynaklar" className="scroll-mt-32" aria-label="Kaynaklar">
          <ConsensusSection m={m} />
          {(hasProv || (m.model?.notes?.length ?? 0) > 0) && (
            <Section title="Veri kaynakları">
              {hasProv && (
                <ul className="panel divide-y divide-line text-sm">
                  {Object.entries(m.provenance!).map(([k, v]) => (
                    <li key={k} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-4 py-2.5">
                      <span className="w-28 shrink-0 text-muted">{PROV_LABEL[k] ?? k}</span>
                      <span className="font-medium min-w-0 flex-1">{v.source}</span>
                      <span className="t-micro num">{fmtDateTime(v.t)}</span>
                    </li>
                  ))}
                </ul>
              )}
              {m.model?.notes?.length ? <p className="mt-2 t-meta">Model notları: {m.model.notes.join('; ')}</p> : null}
            </Section>
          )}
        </section>
      )}
    </div>
  );
}

function PickBox({ m }: { m: Match }) {
  const p = m.pick;
  const won = pickResult(m);
  const alarms = m.market?.drop_alarms ?? [];
  return (
    <div className="mt-4 rounded-lg border-2 border-accent bg-surface p-4" role="group" aria-label="OZBET Tercihi">
      {p ? (
        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <div>
            <div className="t-meta">OZBET Tercihi</div>
            <div className="display text-[34px] font-bold leading-none mt-1">{p.label || marketLabel(p.market)}</div>
          </div>
          <dl className="flex gap-6 num">
            <div><dt className="t-micro">Model</dt><dd className="text-xl font-semibold">{pct(p.p)}</dd></div>
            <div><dt className="t-micro">Oran</dt><dd className="text-xl font-semibold">{p.odds != null ? odd(p.odds) : '–'}</dd></div>
            <div><dt className="t-micro">Güven</dt><dd className="pt-1.5"><Stars n={p.stars} size={16} /></dd></div>
          </dl>
          <div className="ml-auto">
            {won != null ? <ResultBadge won={won} /> : m.value?.length ? <ValueBadge /> : <span className="t-meta">{m.value_note || 'Değer yok'}</span>}
          </div>
        </div>
      ) : <p className="text-muted">Bu maç için tercih üretilmedi.</p>}
      {m.value?.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tbl mt-3">
            <thead><tr><th>Değerli market</th><th className="text-right">Model</th><th className="text-right">Piyasa</th><th className="text-right">Fark</th><th className="text-right">Oran</th><th className="text-right">EV</th></tr></thead>
            <tbody>
              {m.value.map((v) => (
                <tr key={v.market}>
                  <td className="font-medium">{marketLabel(v.market)}</td>
                  <td className="text-right">{pct(v.model_p, 1)}</td><td className="text-right">{pct(v.implied_p, 1)}</td>
                  <td className="text-right text-accent font-semibold">{signedPct(v.edge)}</td><td className="text-right">{odd(v.odds)}</td>
                  <td className="text-right">{signedPct(v.ev)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(m.flags?.length > 0 || alarms.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {alarms.map((k) => <DropBadge key={k}>Düşen oran: {marketLabel(k)}</DropBadge>)}
          {m.flags?.map((f) => <Badge key={f}>{f}</Badge>)}
        </div>
      )}
    </div>
  );
}

function ModelSections({ m }: { m: Match }) {
  const md = m.model!;
  const tg = md.total_goals ?? [];
  const isMarket = md.source === 'piyasa';
  return (
    <>
      {isMarket && (
        <div className="mt-6 rounded-md border border-line bg-sunken px-4 py-3 text-[14px]" role="note">
          <p className="font-semibold">Piyasa modeli</p>
          <p className="mt-0.5 text-muted">Bu maç için geçmiş veri yok. Olasılıklar iddaa'nın 1X2 ve Alt/Üst oranlarından (marj Shin yöntemiyle temizlenerek) türetildi; bağımsız tahmin değildir, bu yüzden değer etiketi ve tercih verilmez.</p>
        </div>
      )}
      <ConsistencyBox m={m} />
      <Section title={isMarket ? 'Piyasa modeli olasılıkları' : 'Model olasılıkları'} aside={<span className="text-[12px] text-muted num">λ {num(md.lambda_home)} – {num(md.lambda_away)} · {md.sims?.toLocaleString('tr-TR')} simülasyon</span>}>
        <div className="panel p-4">
          <ProbBar probs={md.probs} home={m.home.name} away={m.away.name} />
          <div className="mt-1.5 flex justify-between text-[13px] text-muted"><span>{m.home.name}</span><span>Beraberlik</span><span>{m.away.name}</span></div>
          <p className="mt-2 text-[13px] text-muted">{isMarket ? 'Kaynak: iddaa oranları (piyasa)' : <>Veri kalitesi: {{ high: 'yüksek', medium: 'orta', low: 'düşük' }[md.data_quality as string] ?? md.data_quality}</>}</p>
        </div>
      </Section>

      <div className="grid gap-x-6 md:grid-cols-2">
        {md.score_matrix?.length ? (
          <Section title="Skor olasılıkları">
            <div className="panel p-3"><Heatmap matrix={md.score_matrix} home={m.home.name} away={m.away.name} /></div>
          </Section>
        ) : null}
        {md.sample_runs?.runs?.length ? (
          <section id="sim50" className="md:col-span-2 md:order-last">
            <Section title="50 Maç Simülasyonu" aside={<span className="text-[12px] text-muted">Örnek koşular</span>}>
              <Simulation50 data={md.sample_runs} home={m.home.name} away={m.away.name} />
            </Section>
          </section>
        ) : null}
        <div>
          {md.top_scores?.length ? (
            <Section title="En olası 5 skor">
              <ol className="panel divide-y divide-line">
                {md.top_scores.slice(0, 5).map((s, i) => (
                  <li key={s.score} className="flex items-center gap-3 px-4 py-2">
                    <span className="w-5 text-muted text-sm num">{i + 1}</span>
                    <span className="display text-xl font-semibold num w-14">{s.score}</span>
                    <span className="flex-1 h-2 rounded bg-sunken overflow-hidden"><span className="block h-full bg-accent" style={{ width: `${(s.p / md.top_scores[0].p) * 100}%` }} /></span>
                    <span className="w-14 text-right num text-sm font-semibold">{pct(s.p, 1)}</span>
                  </li>
                ))}
              </ol>
            </Section>
          ) : null}
          {tg.length ? (
            <Section title="Toplam gol dağılımı">
              <div className="panel p-4"><Bars values={tg} labels={tg.map((_, i) => (i === tg.length - 1 ? `${i}+` : String(i)))} /></div>
            </Section>
          ) : null}
        </div>
      </div>

      {md.htft && Object.keys(md.htft).length > 0 && (
        <Section title="İlk yarı / maç sonu">
          <div className="panel p-3 overflow-x-auto md:max-w-md">
            <table className="tbl text-center">
              <thead><tr><th className="text-left">İY ↓ / MS →</th><th className="text-center">1</th><th className="text-center">X</th><th className="text-center">2</th></tr></thead>
              <tbody>
                {(['1', 'X', '2'] as const).map((h) => (
                  <tr key={h}>
                    <th scope="row" className="font-semibold text-ink">{h}</th>
                    {(['1', 'X', '2'] as const).map((f) => {
                      const k = `${h}/${f}` as HtFtKey;
                      const v = md.htft[k];
                      const max = Math.max(...HTFT_KEYS.map((x) => md.htft[x] ?? 0));
                      return <td key={f} className={v != null && v === max ? 'font-bold text-accent' : ''}>{pct(v, 1)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </>
  );
}

function MarketTable({ m, date, cats }: { m: Match; date: string; cats?: MarketCategory[] }) {
  const probs = allProbs(m);
  const imp = (m.market?.implied ?? {}) as Record<string, number | undefined>;
  const odds = (m.odds ?? {}) as Record<string, number | undefined>;
  const has = (k: string) => probs[k] != null || imp[k] != null || odds[k] != null;
  const base: MarketCategory[] = cats?.length ? cats
    : MARKET_GROUPS.map((g, i) => ({ id: `g${i}`, title: g.title, keys: g.keys as string[] }));
  const tabs = base.map((c) => ({ ...c, keys: c.keys.filter(has) })).filter((c) => c.keys.length);
  const [tab, setTab] = useState<string>('');
  const { add, remove, has: inCoupon } = useCoupon();
  if (!tabs.length) return null;
  const cur = tabs.find((t) => t.id === tab) ?? tabs[0];
  const valueSet = new Set<string>((m.value ?? []).map((v) => v.market));
  const withOdds = (c: MarketCategory) => c.keys.filter((k) => odds[k] != null).length;
  return (
    <Section title="Tüm marketler" aside={<span className="text-[12px] text-muted">Model · Piyasa (marjsız) · Oran</span>}>
      <div className="-mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Market kategorisi">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === cur.id} onClick={() => setTab(t.id)}
            className={`chip shrink-0 ${t.id === cur.id ? 'chip-on' : ''}`}>
            {t.title}{withOdds(t) > 0 && <span className="ml-1 num opacity-70">{withOdds(t)}</span>}
          </button>
        ))}
      </div>
      <div className="panel px-2 py-1 overflow-x-auto md:max-w-2xl">
        <table className="tbl">
          <thead><tr><th>Market</th><th className="text-right">Model</th><th className="text-right">Piyasa</th><th className="text-right">Fark</th><th className="text-right">Oran</th><th className="w-10"><span className="sr-only">Kupon</span></th></tr></thead>
          <tbody>
            {cur.keys.map((k) => {
              const d = probs[k] != null && imp[k] != null ? probs[k]! - imp[k]! : null;
              const on = inCoupon(m.id, k);
              return (
                <tr key={k}>
                  <td className="font-medium">{marketLabel(k)} {valueSet.has(k) && <ValueBadge />}</td>
                  <td className="text-right font-semibold">{pct(probs[k], 1)}</td>
                  <td className="text-right text-muted">{pct(imp[k], 1)}</td>
                  <td className={`text-right ${d != null && d >= 0.05 ? 'text-accent font-semibold' : 'text-muted'}`}>{d != null ? signedPct(d) : '–'}</td>
                  <td className="text-right">{odds[k] != null ? odd(odds[k]!) : '–'}</td>
                  <td className="text-right">
                    <button type="button" aria-pressed={on} aria-label={`${marketLabel(k)} kupona ${on ? 'eklendi' : 'ekle'}`}
                      onClick={() => (on ? remove(`${m.id}|${k}`) : add(m, date, k))}
                      className={`h-8 w-8 rounded-md border text-sm font-bold ${on ? 'border-accent bg-accent text-accent-ink' : 'border-line'}`}>{on ? '✓' : '+'}</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 text-[12px] text-muted">Oranı olmayan satırlarda yalnızca model olasılığı gösterilir; bu marketler bugünkü bültende yok ya da eşleşmedi.</p>
      {m.market?.margin && Object.keys(m.market.margin).length > 0 && (
        <p className="mt-1 text-[12px] text-muted num">Büro marjı: {Object.entries(m.market.margin).slice(0, 6).map(([k, v]) => `${k === '1x2' ? '1X2' : k === 'ou25' ? 'Ü/A 2.5' : k} ${pct(v, 1)}`).join(' · ')}</p>
      )}
    </Section>
  );
}

function OddsArchive({ m }: { m: Match }) {
  const a: OddsAnalysis | null | undefined = m.odds_analysis;
  if (!a) return null;
  return (
    <Section title="Benzer oranlı geçmiş maçlar" aside={<Link to="/benzer-oran" className="text-[12px] text-accent">Tümü</Link>}>
      <div className="md:max-w-2xl"><OddsArchiveDetail a={a} /></div>
    </Section>
  );
}

function CountBlock({ title, c, unit }: { title: string; c: CountPrediction; unit: string }) {
  const diff = c.exp_total - c.league_avg;
  return (
    <div className="panel px-4 py-3">
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">{title}</span>
        <span className="t-micro text-muted num">lig ort. {num(c.league_avg, 1)}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-3">
        <span className="num text-3xl font-bold">{num(c.exp_total, 1)}</span>
        <span className="text-sm text-muted num">ev {num(c.exp_home, 1)} · dep {num(c.exp_away, 1)} {unit}</span>
      </div>
      <div className={`text-[12px] ${Math.abs(diff) >= 0.7 ? 'font-semibold text-accent' : 'text-muted'}`}>
        Lig ortalamasının {diff >= 0 ? 'üstünde' : 'altında'} ({diff >= 0 ? '+' : ''}{num(diff, 1)})
      </div>
      {c.referee && (
        <div className="mt-1 text-[12px] text-muted">
          Hakem: <b className="text-ink">{c.referee}</b>
          {c.referee_factor != null ? ` · kart eğilimi ×${num(c.referee_factor, 2)} (${c.referee_matches} maç)` : ' · geçmiş verisi yok'}
        </div>
      )}
    </div>
  );
}

function CountsPanel({ m }: { m: Match }) {
  const c = m.model?.corners, k = m.model?.cards;
  if (!c && !k) return null;
  return (
    <Section title="Korner ve kart beklentisi" aside={<span className="text-[12px] text-muted">Negatif binom model · football-data.co.uk</span>}>
      <div className="grid gap-2 md:grid-cols-2 md:max-w-2xl">
        {c && <CountBlock title="Korner" c={c} unit="korner" />}
        {k && <CountBlock title="Kart (sarı + kırmızı)" c={k} unit="kart" />}
      </div>
    </Section>
  );
}

function OddsMovement({ m }: { m: Match }) {
  const h = m.odds_history ?? [];
  const mv = m.market?.movement ?? {};
  if (h.length < 2 && !Object.keys(mv).length) return null;
  const keys: { k: MarketKey; cls: string }[] = [
    { k: '1', cls: 'stroke-accent' }, { k: 'X', cls: 'stroke-muted' }, { k: '2', cls: 'stroke-ink' },
  ];
  const present = keys.filter((x) => h.some((s) => s[x.k] != null));
  return (
    <Section title="Oran hareketi">
      <div className="panel p-4">
        {h.length >= 2 && present.length > 0 && (
          <>
            <LineChart ariaLabel="Oran hareketi grafiği: ilk görülen orana göre yüzde değişim" height={130} baseline={0}
              yFormat={(v) => signedPct(v, 0)}
              series={present.map((x) => {
                const first = h.find((s) => s[x.k] != null)?.[x.k] ?? null;
                return { name: x.k, cls: x.cls, values: h.map((s) => (s[x.k] != null && first ? s[x.k]! / first - 1 : null)) };
              })}
              xLabels={[fmtTime(h[0].t), fmtTime(h[h.length - 1].t)]} />
            <p className="text-[12px] text-muted">İlk görülen orana göre değişim. Düşen oran, piyasanın o sonuca daha çok inandığını gösterir.</p>
            <div className="mt-1 flex gap-4 text-[13px]">
              {present.map((x) => (
                <span key={x.k} className="flex items-center gap-1.5">
                  <svg width="16" height="4" aria-hidden="true"><line x1="0" x2="16" y1="2" y2="2" className={x.cls} strokeWidth="3" /></svg>{marketLabel(x.k)}
                </span>
              ))}
            </div>
          </>
        )}
        {Object.keys(mv).length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2 text-sm num">
            {Object.entries(mv).map(([k, v]) => (
              <li key={k} className={`rounded-md border px-2.5 py-1 ${m.market?.drop_alarms?.includes(k as MarketKey) ? 'border-warn text-warn' : 'border-line'}`}>
                {marketLabel(k)} <b>{signedPct(v as number)}</b>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

const STAT_ROWS: { label: string; k: keyof TeamStats; fmt: (v: number) => string }[] = [
  { label: 'Attığı gol ort.', k: 'gf_avg', fmt: (v) => num(v) },
  { label: 'Yediği gol ort.', k: 'ga_avg', fmt: (v) => num(v) },
  { label: 'İç/dış attığı ort.', k: 'venue_gf_avg', fmt: (v) => num(v) },
  { label: 'İç/dış yediği ort.', k: 'venue_ga_avg', fmt: (v) => num(v) },
  { label: 'xG ort.', k: 'xg_avg', fmt: (v) => num(v) },
  { label: 'xGA ort.', k: 'xga_avg', fmt: (v) => num(v) },
  { label: 'KG Var %', k: 'btts_pct', fmt: (v) => pct(v) },
  { label: '2.5 Üst %', k: 'o25_pct', fmt: (v) => pct(v) },
  { label: 'Korner ort.', k: 'corners_avg', fmt: (v) => num(v, 1) },
  { label: 'Kart ort.', k: 'cards_avg', fmt: (v) => num(v, 1) },
];

function StatsSection({ m }: { m: Match }) {
  const s = m.stats;
  if (!s) return null;
  const val = (t: TeamStats, k: keyof TeamStats) => { const v = t?.[k]; return typeof v === 'number' ? v : null; };
  return (
    <>
      <Section title="Form">
        <div className="panel divide-y divide-line">
          {([['home', m.home.name, 'İç saha'], ['away', m.away.name, 'Deplasman']] as const).map(([side, name, venue]) => (
            <div key={side} className="px-4 py-3">
              <div className="font-semibold">{name}</div>
              <div className="mt-1.5 grid grid-cols-[88px_1fr] gap-y-1.5 items-center text-sm">
                <span className="text-muted">Genel</span><FormStrip form={s[side]?.form} />
                <span className="text-muted">{venue}</span><FormStrip form={s[side]?.venue_form} />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="İstatistik karşılaştırma">
        <div className="panel px-2 py-1 overflow-x-auto md:max-w-2xl">
          <table className="tbl">
            <thead><tr><th className="text-right w-1/3">{m.home.name}</th><th className="text-center"></th><th className="w-1/3">{m.away.name}</th></tr></thead>
            <tbody>
              {STAT_ROWS.map((r) => {
                const a = val(s.home, r.k), b = val(s.away, r.k);
                if (a == null && b == null) return null;
                return (
                  <tr key={r.k}>
                    <td className="text-right font-semibold">{a != null ? r.fmt(a) : '–'}</td>
                    <td className="text-center text-muted text-[13px]">{r.label}</td>
                    <td className="font-semibold">{b != null ? r.fmt(b) : '–'}</td>
                  </tr>
                );
              })}
              <tr>
                <td className="text-right font-semibold">{s.home?.clean_sheets_venue ?? '–'}{s.home?.venue_n ? <span className="text-muted font-normal"> / {s.home.venue_n}</span> : null}</td>
                <td className="text-center text-muted text-[13px]">Gol yemeden (iç/dış)</td>
                <td className="font-semibold">{s.away?.clean_sheets_venue ?? '–'}{s.away?.venue_n ? <span className="text-muted font-normal"> / {s.away.venue_n}</span> : null}</td>
              </tr>
            </tbody>
          </table>
          <p className="px-2 pb-2 text-[12px] text-muted">Örneklem: son {s.home?.n ?? '–'} / {s.away?.n ?? '–'} maç</p>
        </div>
      </Section>

      <Section title="Aralarındaki maçlar">
        <H2HSummaryStrip m={m} />
        {s.h2h?.length ? (
          <ul className="panel divide-y divide-line text-sm">
            {s.h2h.map((g, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-24 text-muted num shrink-0">{fmtShortDate(g.date)}</span>
                <span className="flex-1 min-w-0 truncate text-right">{g.home}</span>
                <span className="display text-lg font-semibold num w-12 text-center">{g.score}</span>
                <span className="flex-1 min-w-0 truncate">{g.away}</span>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">Yakın tarihte karşılaşma yok</p>}
      </Section>
    </>
  );
}

function SquadSection({ m }: { m: Match }) {
  const q = m.squad;
  if (!q || (!q.home && !q.away)) return null;
  return (
    <Section title="Eksik oyuncular" aside={q ? <span className="text-[12px] text-muted">{q.source} · {fmtTime(q.fetched_at)}</span> : undefined}>
      {(
        <div className="grid gap-3 md:grid-cols-2">
          {([['home', m.home.name], ['away', m.away.name]] as const).map(([side, name]) => {
            const t = q[side];
            return (
              <div key={side} className="panel p-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{name}</span>
                  {t?.rotation_risk && <Badge tone="warn">Rotasyon riski</Badge>}
                  {t?.coach_change && <Badge tone="warn">Teknik direktör değişti</Badge>}
                  {t?.adjustment ? <span className="ml-auto text-[12px] text-muted num">λ düzeltme {signedPct(t.adjustment)}</span> : null}
                </div>
                {t?.missing?.length ? (
                  <ul className="mt-2 space-y-1.5 text-sm">
                    {t.missing.map((p) => (
                      <li key={p.name} className="flex items-center gap-2">
                        <span className={p.key ? 'font-semibold' : ''}>{p.name}</span>
                        {p.key && <Badge tone="accent" title="Kilit oyuncu">Kilit</Badge>}
                        <span className={`ml-auto text-[13px] ${p.reason === 'cezalı' ? 'text-loss' : p.reason === 'şüpheli' ? 'text-warn' : 'text-muted'}`}>{p.reason}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-2 text-sm text-muted">Bilinen eksik yok</p>}
              </div>
            );
          })}
        </div>
      )}
    </Section>
  );
}

const PICK_GROUP_LABEL: Record<string, string> = { '1X2': 'MS', OU25: 'Ü/A 2.5', BTTS: 'KG' };

function ConsensusSection({ m }: { m: Match }) {
  const c = m.consensus;
  if (!c || (!c.sources?.length && !c.summary?.length)) return null;
  const pickKeys = [...new Set(c.sources.flatMap((s) => Object.keys(s.picks ?? {})))];
  return (
    <Section title="Kaynak tahminleri">
      {c.summary?.length > 0 && (
        <ul className="mb-3 space-y-1.5">
          {c.summary.map((s) => (
            <li key={s.market} className="flex items-center gap-3 text-sm">
              <span className="w-20 shrink-0 font-semibold">{marketLabel(s.market)}</span>
              <span className="flex gap-[3px]" aria-hidden="true">
                {Array.from({ length: s.total }, (_, i) => <span key={i} className={`h-3 w-3 rounded-sm ${i < s.agree ? 'bg-accent' : 'bg-sunken border border-line'}`} />)}
              </span>
              <span className="text-muted">{s.text}</span>
            </li>
          ))}
        </ul>
      )}
      {c.sources?.length > 0 && (
        <div className="panel px-2 py-1 overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr><th>Kaynak</th>{pickKeys.map((k) => <th key={k}>{PICK_GROUP_LABEL[k] ?? k}</th>)}<th className="text-right">1</th><th className="text-right">X</th><th className="text-right">2</th></tr>
            </thead>
            <tbody>
              {c.sources.map((s) => (
                <tr key={s.source}>
                  <td className="font-medium">{s.source}</td>
                  {pickKeys.map((k) => <td key={k}>{s.picks?.[k] ? marketLabel(s.picks[k]) : '–'}</td>)}
                  <td className="text-right">{pct(s.probs?.['1'])}</td><td className="text-right">{pct(s.probs?.['X'])}</td><td className="text-right">{pct(s.probs?.['2'])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function ConsistencyBox({ m }: { m: Match }) {
  const rows = m.consistency ?? [];
  if (!rows.length) return null;
  return (
    <div className="mt-4 panel p-4">
      <p className="font-semibold text-[14px]">En iyi fiyatlı seçenekler</p>
      <p className="mt-0.5 text-[12px] text-muted">Bu maçta iddaa'nın ek marketleri arasında marjı en düşük satırlar (1X2 + Alt/Üst'ten türetilen adil olasılığa göre). Değerli bahis anlamına gelmez; beklenen getiri genelde yine negatiftir.</p>
      <table className="mt-2 w-full text-[13px] num">
        <thead><tr className="text-muted text-left"><th className="font-normal">Market</th><th className="font-normal text-right">Oran</th><th className="font-normal text-right">Adil olasılık</th><th className="font-normal text-right">Beklenen getiri</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.market}><td>{r.label}</td><td className="text-right">{r.odds.toFixed(2)}</td><td className="text-right">%{(r.fair_p * 100).toFixed(1)}</td><td className="text-right">{r.ev >= 0 ? '+' : ''}{(r.ev * 100).toFixed(1)}%</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
