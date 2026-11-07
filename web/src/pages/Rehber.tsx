import { Link } from 'react-router-dom';
import { useJson, useBacktest } from '../lib/data';
import type { DayFile } from '../lib/types';
import { Loading, Section } from '../components/ui';
import { num } from '../lib/format';

type Desc = { what: string; how: string; ex: string };

const SIDE = (s: string) => (s === '1' ? 'ev sahibi' : s === '2' ? 'deplasman' : 'beraberlik');
const RES = (s: string) => (s === '1' ? 'ev sahibi kazanır' : s === '2' ? 'deplasman kazanır' : 'berabere biter');

/** Market anahtarından kısa açıklama, sonuçlanma kuralı ve örnek üretir. */
export function describe(k: string): Desc {
  let m: RegExpMatchArray | null;
  if (/^[1X2]$/.test(k)) return { what: `Maç sonucu: ${RES(k)}.`, how: 'Normal süre (90 dk + uzatma) skoruna bakılır.', ex: k === '1' ? '2-1 → kazanır' : k === 'X' ? '1-1 → kazanır' : '0-1 → kazanır' };
  if (/^(1X|X2|12)$/.test(k)) return { what: `Çifte şans: iki sonuçtan biri (${k.split('').map(SIDE).join(' veya ')}).`, how: 'İki sonuçtan biri gerçekleşirse kazanır.', ex: k === '12' ? '0-0 → kaybeder' : k === '1X' ? '1-1 → kazanır' : '2-1 → kaybeder' };
  if ((m = k.match(/^HCP([+-]\d)_([1X2])$/))) {
    const h = Number(m[1]);
    return { what: `Handikap: ev sahibinin skoruna ${h > 0 ? '+' : ''}${h} eklenir, sonra ${RES(m[2])}.`, how: 'Handikaplı skor üzerinden maç sonucu.', ex: `2-1 → handikaplı ${2 + h}-1` };
  }
  if ((m = k.match(/^(HT_|H_|A_|C_|K_)?([OU])(\d\.5)$/))) {
    const who = { HT_: 'İlk yarıda toplam gol', H_: 'Ev sahibinin golü', A_: 'Deplasmanın golü', C_: 'Toplam korner', K_: 'Toplam kart', '': 'Toplam gol' }[m[1] ?? ''];
    const up = m[2] === 'O';
    const line = Number(m[3]);
    return { what: `${who} ${num(line, 1)} ${up ? 'üstü' : 'altı'}.`, how: `${who} ${up ? `en az ${Math.ceil(line)}` : `en çok ${Math.floor(line)}`} olursa kazanır.`, ex: `${up ? Math.ceil(line) : Math.floor(line)} → kazanır` };
  }
  if (k === 'BTTS_Y' || k === 'BTTS_N') return { what: `Karşılıklı gol ${k.endsWith('Y') ? 'var' : 'yok'}.`, how: k.endsWith('Y') ? 'İki takım da en az bir gol atarsa kazanır.' : 'Takımlardan en az biri gol atamazsa kazanır.', ex: '1-1 → ' + (k.endsWith('Y') ? 'kazanır' : 'kaybeder') };
  if (k === 'HT_BTTS_Y' || k === 'HT_BTTS_N') return { what: `İlk yarıda karşılıklı gol ${k.endsWith('Y') ? 'var' : 'yok'}.`, how: 'Yalnız ilk yarı skoruna bakılır.', ex: 'İY 1-1 → ' + (k.endsWith('Y') ? 'kazanır' : 'kaybeder') };
  if ((m = k.match(/^G(\d)-(\d)$/))) return { what: `Toplam gol ${m[1]} ile ${m[2]} arası.`, how: 'Toplam gol bu aralıktaysa kazanır.', ex: `${m[2]} gol → kazanır` };
  if (k === 'G6+') return { what: 'Toplam 6 veya daha fazla gol.', how: 'Toplam gol ≥ 6 ise kazanır.', ex: '4-2 → kazanır' };
  if (k === 'ODD' || k === 'EVEN') return { what: `Toplam gol ${k === 'ODD' ? 'tek' : 'çift'}.`, how: '0 gol çift sayılır.', ex: `2-1 → ${k === 'ODD' ? 'kazanır' : 'kaybeder'}` };
  if ((m = k.match(/^(HT|2H)_([1X2])$/))) return { what: `${m[1] === 'HT' ? 'İlk' : 'İkinci'} yarı sonucu: ${RES(m[2])}.`, how: m[1] === 'HT' ? 'İlk yarı skoruna bakılır.' : 'Yalnız ikinci yarıda atılan gollere bakılır.', ex: m[1] === 'HT' ? 'İY 1-0 → MS ne olursa olsun İY 1' : 'İY 1-0, MS 1-2 → 2. yarı 0-2' };
  if ((m = k.match(/^MGH_([1X2])$/))) return { what: `En çok gol ${m[1] === '1' ? 'ilk yarıda' : m[1] === '2' ? 'ikinci yarıda' : 'iki yarıda eşit'} atılır.`, how: 'İki yarının gol sayıları karşılaştırılır.', ex: 'İY 1-0, MS 1-0 → ilk yarı' };
  if (k === 'BOTH_HALVES_O0.5') return { what: 'İki yarıda da en az bir gol.', how: 'Her iki yarıda gol olursa kazanır.', ex: 'İY 1-0, MS 1-1 → kazanır' };
  if ((m = k.match(/^([HA])_WIN_HALF$/))) return { what: `${m[1] === 'H' ? 'Ev sahibi' : 'Deplasman'} en az bir yarıyı kazanır.`, how: 'Yarılardan birinde rakibinden çok gol atması yeter.', ex: 'İY 0-0, MS 1-0 → ev sahibi kazanır' };
  if ((m = k.match(/^([HA])_WIN_NIL$/))) return { what: `${m[1] === 'H' ? 'Ev sahibi' : 'Deplasman'} gol yemeden kazanır.`, how: 'Kazanmalı ve rakip gol atmamalı.', ex: m[1] === 'H' ? '2-0 → kazanır' : '0-1 → kazanır' };
  if ((m = k.match(/^HTFT_([1X2])\/([1X2])$/))) return { what: `İlk yarı ${SIDE(m[1])}, maç sonu ${SIDE(m[2])}.`, how: 'İki tahmin de tutmalı.', ex: `İY ${m[1] === '1' ? '1-0' : m[1] === '2' ? '0-1' : '0-0'}, MS ${m[2] === '1' ? '2-1' : m[2] === '2' ? '1-2' : '1-1'} → kazanır` };
  if ((m = k.match(/^([1X2])&(.+)$/))) { const b = describe(m[2]); return { what: `Maç sonucu ${SIDE(m[1])} ve ${b.what.charAt(0).toLowerCase()}${b.what.slice(1)}`, how: 'İki koşul birlikte tutmalı.', ex: m[1] === '1' ? '3-1 → maç sonucu tutar' : '' }; }
  if ((m = k.match(/^(BTTS_[YN])&(.+)$/))) { const a = describe(m[1]), b = describe(m[2]); return { what: `${a.what.replace(/\.$/, '')} ve ${b.what.charAt(0).toLowerCase()}${b.what.slice(1)}`, how: 'İki koşul birlikte tutmalı.', ex: '2-1 → KG var ve 2.5 üst' }; }
  if ((m = k.match(/^(CR|KR)_([1X2])$/))) return { what: `${m[1] === 'CR' ? 'Korner' : 'Kart'} sayısında ${m[2] === 'X' ? 'eşitlik' : `${SIDE(m[2])} önde`}.`, how: 'Takımların sayıları karşılaştırılır.', ex: '' };
  return { what: '', how: '', ex: '' };
}

export default function Rehber() {
  const day = useJson<DayFile>('latest.json');
  const bt = useBacktest();
  const s = bt.state === 'ready' ? bt.data.summary : null;
  return (
    <div className="max-w-3xl">
      <h1 className="display text-[32px] font-bold leading-tight">Rehber</h1>
      <p className="t-meta">Marketler, sayıların anlamı, yöntem ve sorumlu oyun. Sorularınızın çoğu burada.</p>
      <nav className="mt-3 flex flex-wrap gap-2 text-[14px]" aria-label="Rehber bölümleri">
        {[['sayilar', 'Sayılar nasıl okunur'], ['yontem', 'Yöntem'], ['sozluk', 'Market sözlüğü'], ['sorumlu', 'Sorumlu oyun']].map(([id, t]) => (
          <a key={id} href={`#${id}`} className="tap inline-flex items-center rounded-full border border-line px-3 text-muted hover:text-ink">{t}</a>
        ))}
      </nav>

      <Section title="Sayılar nasıl okunur" id="sayilar">
        <dl className="panel divide-y divide-line text-[15px]">
          {[
            ['Model olasılığı', 'OZBET modelinin bu sonucun gerçekleşme ihtimali için verdiği yüzde. %40, benzer 10 maçtan yaklaşık 4’ünde gerçekleşmesi beklenir demektir.'],
            ['Piyasa olasılığı (marjsız)', 'Oranlardan hesaplanan ihtimal. Bürolar oranlara kâr payı (marj) koyar; bu payı Shin yöntemiyle temizleriz, böylece olasılıkların toplamı %100 olur.'],
            ['Fark', 'Model olasılığı eksi piyasa olasılığı. Pozitifse model bu sonuca piyasadan daha çok ihtimal veriyor.'],
            ['Değer etiketi', 'Fark belirli eşiği (5 puan) geçtiğinde ve iddaa oranıyla beklenen getiri pozitif olduğunda verilir. Bu bir fırsat iddiası değil; modelin piyasadan ayrıştığı yerleri gösterir.'],
            ['Yıldız (1–5)', 'Tercihe duyulan güven: veri kalitesi, farkın büyüklüğü ve o marketin karnedeki geçmiş performansı birlikte değerlendirilir. Karnede kötü giden marketlerde yıldız düşer.'],
            ['Güven aralığı', 'Simülasyon ve veri belirsizliğinden doğan aralık. Aralık genişse olasılığı yaklaşık bir değer olarak okuyun.'],
            ['Benzer oranlı geçmiş maçlar', 'Marjı temizlenmiş olasılığı bugünkü maça yakın (±3 puan) geçmiş maçlarda sonucun ne sıklıkla çıktığı, %95 güven aralığı ve piyasa olasılığıyla. Ham oranla eşleştirmiyoruz: iddaa marjı (~%20) arşivdeki kapanış marjından (~%7) çok yüksek, aynı ham oran arşivde neredeyse hiç yok. Testimizde bu dağılım marjsız olasılıktan daha iyi tahmin etmedi; bir tahmin ya da değer işareti değildir.'],
          ].map(([t, d]) => (
            <div key={t} className="px-4 py-3"><dt className="font-semibold">{t}</dt><dd className="mt-0.5 text-muted">{d}</dd></div>
          ))}
        </dl>
        <p className="mt-3 rounded-lg border-2 border-warn/70 bg-surface p-3 text-[14px]"><b>Korner ve kart deneyseldir.</b> Bu marketlerin olasılıkları gösterilir ama değer etiketi almaz ve karnede puanlanmaz; sonuç verisi ile iddaa sayım kurallarının uyumu henüz doğrulanmadı.</p>
      </Section>

      <Section title="Yöntem özeti" id="yontem">
        <div className="panel p-4 space-y-2 text-[15px]">
          <p><b>Dixon-Coles modeli:</b> her takımın hücum ve savunma gücü geçmiş maçlardan tahmin edilir; düşük skorlu sonuçlar için düzeltme uygulanır.</p>
          <p><b>Şut tabanlı güç (%40):</b> takım gücünün %40’ı attığı/yediği şutlardan, %60’ı gollerden gelir. Şutlar golden daha az şansa bağlıdır.</p>
          <p><b>10.000 simülasyon:</b> her maç 10.000 kez simüle edilir; bütün marketlerin olasılıkları bu simülasyonlardan çıkar.</p>
          <p><b>Piyasa harmanı (%25 model):</b> yayımlanan olasılık %25 model, %75 marjsız piyasa olasılığıdır. Backtest, bu karışımın tek başına modelden daha isabetli olduğunu gösterdi.</p>
          <p><b>Backtest sonucu:</b> {s && s.model_brier != null && s.market_brier != null
            ? <>{s.n.toLocaleString('tr-TR')} maçta model Brier {num(s.model_brier, 3)}, piyasa {num(s.market_brier, 3)} (düşük olan daha iyi).{s.roi_value_bets != null && <> “Değerli” bahislerin getirisi %{num(s.roi_value_bets * 100, 1)}.</>}</>
            : 'geçmiş sezonlarda model ile piyasa kapanış oranları karşılaştırıldı.'}</p>
          <p className="rounded-md bg-sunken p-3 font-semibold">Açıkça söyleyelim: model piyasayı yenemiyor. Kapanış oranları modelimizden daha isabetli. OZBET’i bir kazanç aracı olarak değil, maçları sayılarla okumanın bir yolu olarak kullanın.</p>
          <p className="t-meta">Ayrıntılar ve canlı sonuçlar: <Link to="/karne" className="text-accent underline underline-offset-2">Karne</Link>.</p>
        </div>
      </Section>

      <Section title="Market sözlüğü" id="sozluk">
        {day.state === 'loading' && <Loading variant="page" />}
        {day.state !== 'loading' && !(day.state === 'ready' && day.data.market_categories?.length) && <p className="panel px-4 py-3 text-sm text-muted">Market listesi şu an yüklenemedi.</p>}
        {day.state === 'ready' && (day.data.market_categories ?? []).map((c) => (
          <details key={c.id} className="panel mb-2 group" open={c.id === 'ms'}>
            <summary className="tap cursor-pointer list-none px-4 py-3 font-semibold flex items-center justify-between">
              {c.title}<span className="text-sm font-normal text-muted num">{c.keys.length} market</span>
            </summary>
            {(c.id === 'korner' || c.id === 'kart') && <p className="px-4 pb-2 text-[13px] text-warn font-medium">Deneysel: değer etiketi almaz, karnede puanlanmaz.</p>}
            <ul className="divide-y divide-line border-t border-line">
              {c.keys.map((k) => {
                const d = describe(k);
                return (
                  <li key={k} className="px-4 py-2.5 text-[14px]">
                    <p className="font-semibold">{day.data.market_labels?.[k] ?? k}</p>
                    {d.what && <p className="text-muted">{d.what} {d.how}</p>}
                    {d.ex && <p className="t-micro num">Örnek: {d.ex}</p>}
                  </li>
                );
              })}
            </ul>
          </details>
        ))}
      </Section>

      <Section title="Sorumlu oyun" id="sorumlu">
        <div className="panel p-4 space-y-2 text-[15px]">
          <p><b>18 yaşından küçükler bahis oynayamaz.</b> Bu site 18 yaş ve üzeri içindir.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Kayıpları kovalamayın. Kaybettiğinizi geri almak için oynamak, kaybı büyütür.</li>
            <li>Başlamadan önce bütçe ve süre sınırı koyun; sınıra ulaştığınızda bırakın.</li>
            <li>Yalnız kaybetmeyi göze alabileceğiniz parayla oynayın; borç alarak oynamayın.</li>
            <li>Bahis bir gelir kaynağı değildir. Uzun vadede büro marjı oyuncunun aleyhine işler.</li>
          </ul>
          <p className="rounded-md bg-sunken p-3">Kontrolü kaybettiğinizi düşünüyorsanız yardım alın: <b>Yeşilay Danışmanlık Merkezi (YEDAM) – 115 danışma hattı</b>. Ücretsiz ve gizlidir.</p>
          <p className="t-meta">OZBET hiçbir bahis sitesiyle bağlantılı değildir, reklam almaz ve bahis oynatmaz.</p>
        </div>
      </Section>
    </div>
  );
}
