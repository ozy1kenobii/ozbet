import type { IddaaArchiveInfo, OddsAnalysis } from '../lib/types';
import { fmtShortDate, pct } from '../lib/format';

const LABEL: Record<string, string> = { '1': 'MS 1', X: 'MS X', '2': 'MS 2', 'O2.5': '2.5 Üst', 'U2.5': '2.5 Alt' };
const GOAL_LABELS = ['0', '1', '2', '3', '4', '5+'];

export const HONESTY = [
  'Benzer oranlı geçmiş maçların sonuç dağılımı; yeni bir tahmin değildir.',
  'Testimizde bu dağılım, oranın marjsız olasılığından daha iyi tahmin etmedi.',
  'Farklar çoğunlukla örneklem gürültüsüdür; tek başına seçim gerekçesi olarak kullanma.',
];

export const RAW_ODDS_NOTE = 'Eşleşme ham oranla değil, büro marjı (Shin) temizlenmiş olasılıkla yapılır: iddaa marjı '
  + '(~%20) football-data kapanış marjından (~%7) çok yüksek olduğundan aynı ham oran arşivde neredeyse hiç bulunmaz.';

export function scopeText(a: OddsAnalysis): string {
  const r = a.date_range ? ` · ${fmtShortDate(a.date_range[0])}–${fmtShortDate(a.date_range[1])}` : '';
  return `${a.n} maç · ${a.scope ?? ''}${a.status === 'dusuk_guven' ? ' · düşük güven' : ''}${r}`;
}

export function IddaaArchiveStrip({ info }: { info?: IddaaArchiveInfo | null }) {
  if (!info) return null;
  return (
    <p className="rounded-md bg-sunken px-3 py-2 text-[12px] text-muted">
      iddaa arşivi: <b className="text-ink num">{info.rows}</b> maç kayıtlı, <b className="text-ink num">{info.resulted}</b> sonuçlu;
      aynı oranlı ≥{info.min_n} iddaa maçı olunca iddaa arşivine geçilecek.
    </p>
  );
}

export function OddsArchiveDetail({ a, source = 'football-data.co.uk kapanış oranları' }: { a: OddsAnalysis | null | undefined; source?: string }) {
  if (!a) return <p className="rounded-md bg-sunken px-4 py-3 text-sm text-muted">Bu maç için oran yok; arşiv eşleşmesi yapılamadı.</p>;
  if (a.status === 'az_ornek' || !a.markets) {
    return <p className="rounded-md bg-sunken px-4 py-3 text-sm text-muted">Bu oran bölgesinde arşivde yeterli maç yok ({a.n} &lt; 100); dağılım gösterilmiyor.</p>;
  }
  const gmax = Math.max(...(a.goals ?? [0]), 0.0001);
  const smax = Math.max(...(a.scores ?? [[0]]).flat(), 0.0001);
  return (
    <div className="space-y-3">
      <p className="text-[12px] text-muted num">{scopeText(a)} · kaynak: {source}</p>
      <div className="grid grid-cols-3 gap-2">
        {a.markets.map((x) => (
          <div key={x.market} className={`panel px-2.5 py-2 ${x.market === 'O2.5' ? 'col-start-1' : ''}`}>
            <div className="text-[12px] font-semibold text-muted">{LABEL[x.market] ?? x.market}</div>
            <div className="num text-xl font-bold leading-tight">{pct(x.observed, 1)}</div>
            <div className="text-[11px] text-muted num">GA {pct(x.ci[0], 0)}–{pct(x.ci[1], 0)}</div>
            <div className="text-[11px] text-muted num">piyasa {x.market_p != null ? pct(x.market_p, 1) : '–'}</div>
            {x.note && <div className="mt-0.5 text-[10.5px] leading-snug text-muted">{x.note}</div>}
          </div>
        ))}
      </div>
      {a.goals && (
        <div className="panel px-3 py-2.5">
          <div className="text-[13px] font-semibold mb-1.5">Toplam gol dağılımı</div>
          <div className="flex items-end gap-1.5 h-24" role="img" aria-label={`Toplam gol: ${a.goals.map((g, i) => `${GOAL_LABELS[i]} gol ${pct(g, 0)}`).join(', ')}`}>
            {a.goals.map((g, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                <span className="text-[11px] num text-muted">{pct(g, 0)}</span>
                <div className="w-full rounded-t bg-accent/70" style={{ height: `${Math.max(2, (g / gmax) * 70)}%` }} />
              </div>
            ))}
          </div>
          <div className="flex gap-1.5 mt-1">{GOAL_LABELS.map((l) => <span key={l} className="flex-1 text-center text-[11px] text-muted num">{l}</span>)}</div>
        </div>
      )}
      {a.scores && (
        <div className="panel px-3 py-2.5">
          <div className="text-[13px] font-semibold mb-1.5">Skor dağılımı (ev satır × dep sütun)</div>
          <table className="w-full text-center text-[12px] num border-separate" style={{ borderSpacing: 2 }}>
            <thead><tr><th className="text-muted font-normal w-6" />{[0, 1, 2, 3, 4].map((c) => <th key={c} className="text-muted font-normal">{c}</th>)}</tr></thead>
            <tbody>
              {a.scores.map((row, h) => (
                <tr key={h}>
                  <th className="text-muted font-normal">{h}</th>
                  {row.map((v, c) => (
                    <td key={c} className="rounded py-1.5" style={{ background: `rgb(var(--accent) / ${((v / smax) * 0.28).toFixed(3)})` }}>
                      {pct(v, 1)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {a.scores_other != null && <p className="mt-1 text-[11px] text-muted num">Izgara dışı skorlar (5+ gol tek takım): {pct(a.scores_other, 1)}</p>}
        </div>
      )}
      <p className="text-[12px] text-muted">{a.disclaimer} GA: Wilson %95 güven aralığı. Piyasa: aynı maçların marjsız (Shin) ortalama olasılığı. Marjsız olasılığı bugünkü maça en yakın (±3 puan) en çok 400 maç; önce aynı lig, 300'den azsa tüm ligler.</p>
    </div>
  );
}
