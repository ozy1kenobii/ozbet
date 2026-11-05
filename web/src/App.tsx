import { lazy, Suspense, useEffect } from 'react';
import { NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { Logo, Loading } from './components/ui';
import { useTheme } from './lib/theme';
import { useOnline } from './lib/data';
import { useCoupon } from './lib/coupon';

const Home = lazy(() => import('./pages/Home'));
const MatchDetail = lazy(() => import('./pages/MatchDetail'));
const Coupon = lazy(() => import('./pages/Coupon'));
const Scorecard = lazy(() => import('./pages/Scorecard'));
const Sources = lazy(() => import('./pages/Sources'));

const NAV = [
  { to: '/', label: 'Bülten', icon: 'M4 5h16M4 10h16M4 15h10M4 20h7' },
  { to: '/kupon', label: 'Kupon', icon: 'M5 3h14v18l-3.5-2-3.5 2-3.5-2L5 21zM9 8h6M9 12h6' },
  { to: '/karne', label: 'Karne', icon: 'M4 20V10M10 20V4M16 20v-7M22 20H2' },
  { to: '/kaynaklar', label: 'Kaynaklar', icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18' },
];

function NavIcon({ d }: { d: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function CountBadge({ n }: { n: number }) {
  if (!n) return null;
  return (
    <span className="ml-1 inline-grid min-w-[20px] h-5 place-items-center rounded-full bg-accent px-1 text-[11px] font-bold text-accent-ink num" aria-label={`${n} seçim`}>
      {n}
    </span>
  );
}

export default function App() {
  const { isDark, toggle } = useTheme();
  const online = useOnline();
  const { items } = useCoupon();
  const loc = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);

  return (
    <div className="min-h-screen flex flex-col">
      {!online && (
        <div className="bg-warn text-white text-center text-[13px] font-medium py-1.5 px-4" role="status">
          Çevrimdışı – son kaydedilen veri
        </div>
      )}
      <header className="sticky top-0 z-30 bg-bg/95 backdrop-blur border-b border-line">
        <div className="mx-auto max-w-5xl px-4 h-14 flex items-center gap-4">
          <NavLink to="/" className="tap flex items-center" aria-label="OZBET ana sayfa"><Logo /></NavLink>
          <nav className="hidden md:flex items-center gap-1 ml-4" aria-label="Ana menü">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'}
                className={({ isActive }) => `tap inline-flex items-center px-3 rounded-md text-[15px] font-medium ${isActive ? 'text-accent' : 'text-muted hover:text-ink'}`}>
                {n.label}{n.to === '/kupon' && <CountBadge n={items.length} />}
              </NavLink>
            ))}
          </nav>
          <button onClick={toggle} className="tap ml-auto grid place-items-center rounded-md text-muted hover:text-ink"
            aria-label={isDark ? 'Açık temaya geç' : 'Koyu temaya geç'} title={isDark ? 'Açık tema' : 'Koyu tema'}>
            {isDark ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true"><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" /></svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" /></svg>
            )}
          </button>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-5xl px-4 pt-4 pb-6">
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/gun/:date" element={<Home />} />
            <Route path="/mac/:date/:id" element={<MatchDetail />} />
            <Route path="/kupon" element={<Coupon />} />
            <Route path="/karne" element={<Scorecard />} />
            <Route path="/kaynaklar" element={<Sources />} />
            <Route path="*" element={<p className="text-muted py-10 text-center">Sayfa bulunamadı.</p>} />
          </Routes>
        </Suspense>
      </main>

      <footer className="border-t border-line mt-4 pb-24 md:pb-6">
        <div className="mx-auto max-w-5xl px-4 py-5 text-[13px] text-muted space-y-1">
          <p>İstatistiksel tahmindir, sonuç garantisi yoktur. 18+, sorumlu oyna.</p>
          <p>© OZBET</p>
        </div>
      </footer>

      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-surface border-t border-line" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }} aria-label="Alt menü">
        <ul className="grid grid-cols-4">
          {NAV.map((n) => (
            <li key={n.to}>
              <NavLink to={n.to} end={n.to === '/'}
                className={({ isActive }) => `flex flex-col items-center justify-center h-16 gap-0.5 text-[12px] font-medium ${isActive ? 'text-accent' : 'text-muted'}`}>
                <span className="relative">
                  <NavIcon d={n.icon} />
                  {n.to === '/kupon' && items.length > 0 && (
                    <span className="absolute -top-1.5 -right-3 min-w-[18px] h-[18px] rounded-full bg-accent text-accent-ink text-[10px] font-bold grid place-items-center px-1 num" aria-label={`${items.length} seçim`}>{items.length}</span>
                  )}
                </span>
                {n.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
