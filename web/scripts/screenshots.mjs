// Örnek veriyle ekran görüntüsü alır. Önce: npm run build && OZBET_DATA_DIR=sample-data npx vite preview --port 4179
// Kullanım: node scripts/screenshots.mjs [chromePath]
import { chromium } from 'playwright';
import fs from 'node:fs';
const exe = process.argv[2] || process.env.CHROME_PATH;
const base = process.env.BASE_URL || 'http://localhost:4179/';
fs.mkdirSync('screenshots', { recursive: true });
const browser = await chromium.launch(exe ? { executablePath: exe, args: ['--no-sandbox'] } : {});
const errors = [];
const id = 'TR1-20261105-galatasaray-fenerbahce';
const pages = [
  ['ana', '#/'],
  ['mac-detay', `#/mac/2026-11-05/${id}`],
  ['karne', '#/karne'],
  ['kaynaklar', '#/kaynaklar'],
];
for (const [vpName, vp, scheme] of [['mobil', { width: 390, height: 844 }, 'light'], ['masaustu', { width: 1280, height: 900 }, 'light'], ['mobil-koyu', { width: 390, height: 844 }, 'dark']]) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 2, colorScheme: scheme, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(`${vpName}: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`${vpName} console: ${m.text()}`); });
  for (const [n, h] of pages) {
    if (vpName === 'mobil-koyu' && !['ana', 'mac-detay'].includes(n)) continue;
    await page.goto(base + h, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `screenshots/${n}-${vpName}.png`, fullPage: true });
    console.log('kaydedildi', `screenshots/${n}-${vpName}.png`);
  }
  // Kupon: aynı maçtan iki seçim ekle (korelasyon uyarısı)
  if (vpName !== 'mobil-koyu') {
    await page.goto(base + `#/mac/2026-11-05/${id}`, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /kupona ekle/ }).first().click();
    await page.getByRole('dialog').getByRole('button', { name: /^MS 1/ }).click();
    await page.getByRole('dialog').getByRole('button', { name: /^2\.5 Üst/ }).click();
    await page.keyboard.press('Escape');
    await page.goto(base + '#/', { waitUntil: 'networkidle' });
    const btn = page.getByRole('button', { name: /Arsenal – Chelsea kupona ekle/ });
    await btn.click();
    await page.getByRole('dialog').getByRole('button', { name: /^MS 1/ }).click();
    await page.goto(base + '#/kupon', { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `screenshots/kupon-${vpName}.png`, fullPage: true });
    console.log('kaydedildi', `screenshots/kupon-${vpName}.png`);
  }
  await ctx.close();
}
await browser.close();
if (errors.length) { console.log('HATALAR:\n' + errors.join('\n')); process.exitCode = 1; } else console.log('Konsol hatası yok');
