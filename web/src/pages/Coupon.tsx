import { Link } from 'react-router-dom';
import { analyze, useCoupon } from '../lib/coupon';
import { fmtDateTime, fmtTime, odd, pct, signedPct } from '../lib/format';

export default function Coupon() {
  const { items, remove, clear } = useCoupon();
  const a = analyze(items);

  if (!items.length) {
    return (
      <div>
        <h1 className="display text-[32px] font-bold leading-tight">Kupon asistanı</h1>
        <div className="mt-4 panel px-5 py-10 text-center">
          <p className="display text-2xl font-semibold">Kuponun boş</p>
          <p className="mt-2 text-sm text-muted">Bültende bir maç kartındaki + düğmesine dokunup market seçerek ekle.</p>
          <Link to="/" className="btn btn-primary mt-4">Bültene git</Link>
        </div>
      </div>
    );
  }

  const evTone = a.ev == null ? 'text-muted' : a.ev > 0 ? 'text-win' : 'text-loss';

  return (
    <div>
      <div className="flex items-center gap-3">
        <h1 className="display text-[32px] font-bold leading-tight">Kupon asistanı</h1>
        <button className="btn btn-ghost ml-auto" onClick={() => { if (confirm('Tüm seçimler kaldırılsın mı?')) clear(); }}>Temizle</button>
      </div>

      <section className="mt-4 panel p-4" aria-label="Kupon özeti">
        <dl className="grid grid-cols-3 gap-3 num">
          <div><dt className="text-[13px] text-muted">Birleşik olasılık</dt><dd className="display text-[28px] font-bold leading-tight">{pct(a.jointP, 1)}</dd></div>
          <div><dt className="text-[13px] text-muted">Toplam oran</dt><dd className="display text-[28px] font-bold leading-tight">{a.totalOdds != null ? odd(a.totalOdds) : '–'}</dd></div>
          <div><dt className="text-[13px] text-muted">Beklenen değer</dt><dd className={`display text-[28px] font-bold leading-tight ${evTone}`}>{a.ev != null ? signedPct(a.ev) : '–'}</dd></div>
        </dl>
        <p className="mt-2 text-[12px] text-muted">EV = birleşik olasılık × toplam oran − 1. Pozitif EV modele göre değerli, yine de sonuç garantisi yoktur.</p>
      </section>

      {(a.correlated || a.crowded.length > 0 || a.missingOdds.length > 0 || a.missingP.length > 0) && (
        <ul className="mt-3 space-y-2" aria-label="Uyarılar">
          {a.groups.filter((g) => g.items.length > 1).map((g) => (
            <li key={g.matchId} className="rounded-md border border-warn/60 px-3.5 py-2.5 text-sm">
              <b className="text-warn">Korelasyonlu seçim: aynı maç</b> — {g.title}.{' '}
              {g.method === 'matris'
                ? <>Birleşik olasılık skor matrisinden tam hesaplandı: <b className="num">{pct(g.p, 1)}</b>{g.tail != null && g.tail > 0.0005 ? <> (5+ gollü skorlar matriste olmadığından yaklaşık %{(g.tail * 100).toFixed(1)}’lik kuyruk dışarıda kaldı)</> : null}.</>
                : <>Skor matrisi olmadığından çarpımla hesaplandı; bu seçimler bağımlı olduğu için sonuç yanıltıcı olabilir.</>}
              {g.contradictory && <> Bu seçimler birlikte gerçekleşemez.</>}
            </li>
          ))}
          {a.crowded.map((c) => (
            <li key={c.league + c.time} className="rounded-md border border-line px-3.5 py-2.5 text-sm text-muted">
              Aynı saatte ({fmtTime(c.time)}) {c.league} ligisinden {c.count} seçim var; hepsi aynı anda oynanıyor, riskini dağıtmayı düşün.
            </li>
          ))}
          {a.missingOdds.length > 0 && (
            <li className="rounded-md border border-line px-3.5 py-2.5 text-sm text-muted">
              Oranı olmayan seçim var ({a.missingOdds.map((s) => `${s.home} ${s.label}`).join(', ')}): EV hesaplanamaz.
            </li>
          )}
          {a.missingP.length > 0 && (
            <li className="rounded-md border border-line px-3.5 py-2.5 text-sm text-muted">
              Model olasılığı olmayan seçim var: birleşik olasılık hesaplanamaz.
            </li>
          )}
        </ul>
      )}

      <ul className="mt-4 space-y-2">
        {items.map((s) => {
          const ev = s.p != null && s.odds != null ? s.p * s.odds - 1 : null;
          return (
            <li key={s.key} className="panel flex items-center gap-3 pl-4 pr-1.5 py-2">
              <Link to={`/mac/${s.date}/${encodeURIComponent(s.matchId)}`} className="min-w-0 flex-1">
                <div className="text-[12px] text-muted num">{s.league_name} · {fmtDateTime(s.kickoff)}</div>
                <div className="font-semibold truncate">{s.home} – {s.away}</div>
                <div className="flex gap-3 text-sm num">
                  <span className="display text-[17px] font-semibold text-accent">{s.label}</span>
                  <span className="text-muted">Model <b className="text-ink">{pct(s.p, 1)}</b></span>
                  <span className="text-muted">Oran <b className="text-ink">{s.odds != null ? odd(s.odds) : 'yok'}</b></span>
                  {ev != null && <span className={ev > 0 ? 'text-win' : 'text-muted'}>EV {signedPct(ev)}</span>}
                </div>
              </Link>
              <button className="tap grid place-items-center rounded-md text-muted hover:text-loss" onClick={() => remove(s.key)} aria-label={`${s.home} – ${s.away} ${s.label} seçimini kaldır`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[12px] text-muted">Seçimler bu cihazda saklanır. Olasılık ve oranlar ekleme anındaki değerlerdir.</p>
    </div>
  );
}
