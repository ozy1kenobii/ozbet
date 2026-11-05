import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import fs from 'node:fs';
import path from 'node:path';

/**
 * Geliştirme sunucusunda veri klasörünü /data altında servis eder.
 * Varsayılan: repo kökündeki ../data
 * OZBET_DATA_DIR=sample-data ile web/sample-data (ÖRNEK VERİ) kullanılır.
 * Build'e veri kopyalanmaz; CI deploy sırasında data/ → dist/data/ kopyalar.
 */
function serveDataDir(): Plugin {
  const dir = path.resolve(__dirname, process.env.OZBET_DATA_DIR ?? '../data');
  const handler = (req: import('node:http').IncomingMessage, res: import('node:http').ServerResponse, next: () => void) => {
    const url = (req.url ?? '').split('?')[0];
    const m = url.match(/\/data\/(.+)$/);
    if (!m) return next();
    const rel = decodeURIComponent(m[1]);
    const file = path.resolve(dir, rel);
    if (!file.startsWith(dir + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.statusCode = 404;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end('{"error":"not found"}');
      return;
    }
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    fs.createReadStream(file).pipe(res);
  };
  return {
    name: 'ozbet-serve-data',
    configureServer(server) {
      server.config.logger.info(`  ozbet: /data → ${dir}`);
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      if (process.env.OZBET_DATA_DIR) server.middlewares.use(handler);
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [
    serveDataDir(),
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: null,
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'OZBET',
        short_name: 'OZBET',
        description: 'İstatistiksel futbol maç analizi ve olasılık tahminleri',
        lang: 'tr',
        start_url: './',
        scope: './',
        display: 'standalone',
        theme_color: '#2340C8',
        background_color: '#2340C8',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        globIgnores: ['data/**'],
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/\/data\//],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => /\/data\/[^/]+\.json$/.test(url.pathname),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'ozbet-data',
              networkTimeoutSeconds: 6,
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  build: { target: 'es2020', cssCodeSplit: true },
});
