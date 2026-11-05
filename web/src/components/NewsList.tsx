import type { Match, NewsItem } from '../lib/types';
import { fmtTime } from '../lib/format';
import { Badge } from './ui';

const TAG_LABEL: Record<string, string> = { sakat: 'Sakatlık', ceza: 'Ceza', td: 'Teknik direktör', kadro: 'Kadro', transfer: 'Transfer' };
const TAG_TONE: Record<string, 'warn' | 'loss' | 'neutral'> = { sakat: 'warn', ceza: 'loss', td: 'warn' };

export function ago(iso: string, now = Date.now()): string {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  const h = Math.max(0, Math.floor((now - t) / 3_600_000));
  if (h < 1) return 'az önce';
  if (h < 24) return `${h} saat önce`;
  return `${Math.floor(h / 24)} gün önce`;
}

function Item({ n }: { n: NewsItem }) {
  return (
    <li className="py-2 border-t border-line first:border-t-0">
      <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-[15px] font-medium leading-snug hover:text-accent">
        {n.title}
      </a>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-muted">
        <span>{n.source}</span>
        <span aria-hidden="true">·</span>
        <time dateTime={n.published}>{ago(n.published)}</time>
        {n.tags?.map((t) => <Badge key={t} tone={TAG_TONE[t] ?? 'neutral'}>{TAG_LABEL[t] ?? t}</Badge>)}
      </div>
    </li>
  );
}

/** Maç detayında iki takımın güncel haberleri. Veri yoksa hiçbir şey çizmez. */
export function NewsList({ m }: { m: Match }) {
  const n = m.news;
  if (!n || (!n.home?.length && !n.away?.length)) return null;
  return (
    <section id="haberler" className="mt-7">
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h2 className="h-section">Haberler</h2>
        <span className="text-[12px] text-muted">RSS · {fmtTime(n.fetched_at)} · son 72 saat</span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {([['home', m.home.name], ['away', m.away.name]] as const).map(([side, name]) => {
          const items = n[side] ?? [];
          return (
            <div key={side} className="panel p-4 min-w-0">
              <div className="font-semibold">{name}</div>
              {items.length ? <ul className="mt-1">{items.map((x) => <Item key={x.url} n={x} />)}</ul>
                : <p className="mt-2 text-sm text-muted">Güncel haber yok</p>}
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[12px] text-muted">Başlıklar yayıncıların RSS akışlarından; bağlantılar kaynak siteye gider. Etiketler anahtar kelimeyle otomatik çıkarılır.</p>
    </section>
  );
}
