import { statusSources, useStatus } from '../lib/data';
import { fmtDateTime } from '../lib/format';
import { Dot, Empty, Loading } from '../components/ui';
import type { HealthLevel, QualityReport, SourceHealth } from '../lib/types';

const LABEL: Record<string, string> = { ok: 'Çalışıyor', partial: 'Kısmi', missing: 'Eksik', skipped: 'Kapalı' };
const LEVEL: Record<HealthLevel, { t: string; cls: string }> = {
  ok: { t: 'Sağlıklı', cls: 'text-win' },
  uyari: { t: 'Son çalıştırmada veri yok', cls: 'text-warn' },
  alarm: { t: 'Alarm', cls: 'text-loss' },
  kronik: { t: 'Hiç çalışmadı (bilinen engel)', cls: 'text-muted' },
  kapali: { t: 'Bilerek kapalı', cls: 'text-muted' },
};
const VALIDATION: Record<string, string> = {
  oran_aralik_disi: 'Aralık dışı oran (1,01–100)',
  oran_sayi_degil: 'Sayı olmayan oran',
  marj_tutarsiz_1x2: 'Marjı tutarsız MS oranları',
  marj_tutarsiz_ou15: 'Marjı tutarsız 1.5 A/Ü',
  marj_tutarsiz_ou25: 'Marjı tutarsız 2.5 A/Ü',
  marj_tutarsiz_ou35: 'Marjı tutarsız 3.5 A/Ü',
  marj_tutarsiz_btts: 'Marjı tutarsız KG',
  eksik_1x2: 'Eksik MS oranı (1/X/2 tam değil)',
  fikstur_takim_bozuk: 'Takım adı boş/aynı',
  fikstur_tarih_disi: 'Tarih aralığı dışı maç',
  skor_bozuk: 'Bozuk skor', skor_aralik_disi: 'Aralık dışı skor', iy_skor_tutarsiz: 'İY skoru MS ile çelişiyor',
  gecmis_skor_bozuk: 'Geçmiş: bozuk skor', gecmis_satir_bozuk: 'Geçmiş: bozuk satır',
  gecmis_tekrar: 'Geçmiş: tekrar eden maç', gecmis_iy_tutarsiz: 'Geçmiş: İY tutarsız',
  mac_tekrar: 'Bültende tekrar eden maç',
};

const pct = (v: number | null | undefined) => (v == null ? '–' : `%${Math.round(v * 100)}`);

function History({ h }: { h: SourceHealth }) {
  return (
    <span className="inline-flex items-center gap-[3px]" aria-label={`Son ${h.history.length} çalıştırma`}>
      {h.history.map((x, i) => (
        <span key={i} title={LABEL[x] ?? x}
          className={`h-3 w-1.5 rounded-sm ${x === 'ok' ? 'bg-win' : x === 'partial' ? 'bg-warn' : x === 'skipped' ? 'bg-line' : 'bg-loss'}`} />
      ))}
    </span>
  );
}

function Metric({ label, v, hint, warn }: { label: string; v: string; hint: string; warn?: boolean }) {
  return (
    <div className="panel px-3 py-2.5">
      <div className="t-micro text-muted">{label}</div>
      <div className={`num text-xl font-bold ${warn ? 'text-warn' : ''}`}>{v}</div>
      <div className="text-[12px] text-muted leading-snug">{hint}</div>
    </div>
  );
}

function Quality({ q }: { q: QualityReport }) {
  const low = (v: number | null | undefined, t: number) => v != null && v < t;
  const val = Object.entries(q.validation ?? {});
  const unmatched = Object.entries(q.unmatched_teams ?? {});
  return (
    <section className="mt-6">
      <h2 className="display text-xl font-bold">Veri kalitesi (son çalıştırma)</h2>
      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
        <Metric label="Kaynaklar arası eşleşme" v={pct(q.cross_source_match_pct)} warn={low(q.cross_source_match_pct, 0.85)}
          hint={q.cross_source?.joined != null ? `Nesine ve iddaa'daki ${q.cross_source.joined} maç tek maç olarak birleşti` : 'Nesine ↔ iddaa aynı maçı buluyor mu'} />
        <Metric label="Takım eşleşmesi" v={pct(q.team_match_pct)} warn={low(q.team_match_pct, 0.95)}
          hint="Bültendeki takımın geçmiş veride bulunma oranı" />
        <Metric label="Lig tanıma" v={pct(q.league_mapped_pct)} hint="Kapsanan liglere atanan maç oranı" />
        <Metric label="Oran / model kapsamı" v={`${pct(q.odds_coverage_pct)} / ${pct(q.model_coverage_pct)}`}
          hint="Kapsanan liglerde oranı ve modeli olan maçlar" />
      </div>
      {unmatched.length > 0 && (
        <div className="mt-3 panel px-4 py-3 text-sm">
          <div className="font-semibold">Geçmiş veride bulunamayan takımlar</div>
          <p className="text-[12px] text-muted">Bu takımlar için model çalışmaz; çoğu yeni yükselen takım ya da farklı yazımdır (sözlüğe eklenebilir).</p>
          <ul className="mt-1 space-y-0.5">{unmatched.map(([lg, names]) => <li key={lg}><b>{lg}:</b> {names.join(', ')}</li>)}</ul>
        </div>
      )}
      <div className="mt-3 panel px-4 py-3 text-sm">
        <div className="font-semibold">Doğrulamada ayıklananlar</div>
        {val.length === 0 ? <p className="text-muted">Ayıklanan kayıt yok.</p> : (
          <ul className="mt-1 grid gap-x-4 gap-y-0.5 md:grid-cols-2">
            {val.map(([k, n]) => <li key={k} className="flex"><span>{VALIDATION[k] ?? k}</span><b className="num ml-auto">{n}</b></li>)}
          </ul>
        )}
      </div>
      {q.unknown_leagues?.length > 0 && (
        <details className="mt-3 panel px-4 py-3 text-sm">
          <summary className="cursor-pointer font-semibold">Tanınmayan lig adları ({q.unknown_leagues.length})</summary>
          <p className="mt-1 text-muted">{q.unknown_leagues.join(' · ')}</p>
        </details>
      )}
    </section>
  );
}

export default function Sources() {
  const st = useStatus();
  return (
    <div>
      <h1 className="display text-[32px] font-bold leading-tight">Kaynaklar</h1>
      <p className="text-sm text-muted">Her veri kaynağının son durumu ve son 14 çalıştırmalık geçmişi. Eksik bir kaynak akışı durdurmaz; ilgili alanlar boş kalır.</p>
      {st.state === 'loading' && <div className="mt-4"><Loading /></div>}
      {st.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {st.state === 'ready' && (() => {
        const list = statusSources(st.data);
        const obj = Array.isArray(st.data) ? undefined : st.data;
        const hs = obj?.health?.sources ?? {};
        const alerts = obj?.health?.alerts ?? [];
        if (!list.length) return <div className="mt-4"><Empty /></div>;
        return (
          <>
            {obj?.generated_at && <p className="mt-1 text-[12px] text-muted num">Güncelleme {fmtDateTime(obj.generated_at)}</p>}
            {alerts.length > 0 && (
              <div className="mt-3 rounded-md border border-loss/40 bg-loss/10 px-4 py-3 text-sm" role="alert">
                <div className="font-bold text-loss">⚠ Alarm: daha önce çalışan kaynaktan veri gelmiyor</div>
                <ul className="mt-1 list-disc pl-5">{alerts.map((a) => <li key={a}>{a}</li>)}</ul>
              </div>
            )}
            <ul className="mt-4 panel divide-y divide-line">
              {list.map((s) => {
                const h = hs[s.id];
                return (
                  <li key={s.id} className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <Dot s={s.status} />
                      <span className="font-semibold">{s.name}</span>
                      <span className={`ml-auto text-sm font-semibold ${s.status === 'ok' ? 'text-win' : s.status === 'partial' ? 'text-warn' : s.status === 'skipped' ? 'text-muted' : 'text-loss'}`}>{LABEL[s.status] ?? s.status}</span>
                    </div>
                    {h && h.history.length > 0 && (
                      <div className="mt-1 pl-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
                        <History h={h} />
                        <span className="num text-muted">Çalışma oranı {pct(h.ok_rate)}</span>
                        <span className={LEVEL[h.level].cls}>{LEVEL[h.level].t}{h.streak > 1 && h.level !== 'kapali' ? ` · ${h.streak} çalıştırma` : ''}</span>
                      </div>
                    )}
                    <div className="mt-0.5 pl-5 flex flex-wrap gap-x-4 text-[13px] text-muted">
                      <span className="num">Çekilme: {s.fetched_at ? fmtDateTime(s.fetched_at) : '–'}</span>
                      {(s.items ?? 0) > 0 && <span className="num">{s.items} kayıt</span>}
                      {s.note && <span>{s.note}</span>}
                    </div>
                  </li>
                );
              })}
            </ul>
            {obj?.quality && <Quality q={obj.quality} />}
          </>
        );
      })()}
    </div>
  );
}
