import { statusSources, useStatus } from '../lib/data';
import { fmtDateTime } from '../lib/format';
import { Dot, Empty, Loading } from '../components/ui';

const LABEL: Record<string, string> = { ok: 'Çalışıyor', partial: 'Kısmi', missing: 'Eksik', skipped: 'Atlandı' };

export default function Sources() {
  const st = useStatus();
  return (
    <div>
      <h1 className="display text-[32px] font-bold leading-tight">Kaynaklar</h1>
      <p className="text-sm text-muted">Son çalıştırmada her veri kaynağının durumu. Eksik bir kaynak akışı durdurmaz; ilgili alanlar boş kalır.</p>
      {st.state === 'loading' && <div className="mt-4"><Loading /></div>}
      {st.state === 'empty' && <div className="mt-4"><Empty /></div>}
      {st.state === 'ready' && (() => {
        const list = statusSources(st.data);
        const gen = !Array.isArray(st.data) ? st.data.generated_at : undefined;
        if (!list.length) return <div className="mt-4"><Empty /></div>;
        return (
          <>
            {gen && <p className="mt-1 text-[12px] text-muted num">Güncelleme {fmtDateTime(gen)}</p>}
            <ul className="mt-4 panel divide-y divide-line">
              {list.map((s) => (
                <li key={s.id} className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <Dot s={s.status} />
                    <span className="font-semibold">{s.name}</span>
                    <span className="text-[12px] text-muted">{s.id}</span>
                    <span className={`ml-auto text-sm font-semibold ${s.status === 'ok' ? 'text-win' : s.status === 'partial' ? 'text-warn' : 'text-loss'}`}>{LABEL[s.status] ?? s.status}</span>
                  </div>
                  <div className="mt-0.5 pl-5 flex flex-wrap gap-x-4 text-[13px] text-muted">
                    <span className="num">Çekilme: {s.fetched_at ? fmtDateTime(s.fetched_at) : '–'}</span>
                    {s.note && <span>{s.note}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </>
        );
      })()}
    </div>
  );
}
