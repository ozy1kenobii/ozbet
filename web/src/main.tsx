import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App';
import { CouponProvider } from './lib/coupon';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <CouponProvider>
        <App />
      </CouponProvider>
    </HashRouter>
  </React.StrictMode>,
);

// Service worker kaydı (yalnızca build'de; dev'de devre dışı)
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  import('virtual:pwa-register').then(({ registerSW }) => registerSW({ immediate: true })).catch(() => {});
}
