// Gerçek veriyle v2 ekran görüntüleri.
// Önce: npm run build && mkdir -p dist/data && cp -r ../data/. dist/data/ && npx vite preview --port 4182 --strictPort
// Kullanım: node scripts/screenshots-v2.mjs [chromePath]
import { chromium } from 'playwright';
import fs from 'node:fs';
const exe = process.argv[2] || process.env.CHROME_PATH || '/usr/bin/google-chrome';
const base = process.env.BASE_URL || 'http://localhost:4182/';
const date = process.env.OZBET_DATE || JSON.parse(fs.readFileSync('../data/index.json', 'utf8')).latest;
const day = JSON.parse(fs.readFileSync(`../data/${date}.json`, 'utf8'));
const m = day.matches.find((x) => x.model && x.pick) ?? day.matches[0];
fs.mkdirSync('screenshots', { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox'] });
const errors = [];
const pages = [['ana', '#/'], ['mac-detay', `#/mac/${date}/${encodeURIComponent(m.id)}`], ['karne', '#/karne']];
const vps = [['390', { width: 390, height: 844 }, 'light'], ['1280', { width: 1280, height: 900 }, 'light'], ['390-koyu', { width: 390, height: 844 }, 'dark']];
for (const [vpName, vp, scheme] of vps) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: vpName.startsWith('390') ? 2 : 1, colorScheme: scheme, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(`${vpName}: ${e.message}`));
  page.on('console', (x) => { if (x.type() === 'error') errors.push(`${vpName} console: ${x.text()}`); });
  for (const [n, h] of pages) {
    if (vpName === '390-koyu' && n === 'karne') continue;
    await page.goto(base + h, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    const out = `screenshots/v2-${n}-${vpName}.png`;
    await page.screenshot({ path: out, fullPage: true });
    console.log('kaydedildi', out);
    if (n === 'mac-detay' && vpName === '390') {
      await page.mouse.wheel(0, 900);
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'screenshots/v2-mac-detay-390-kaydirilmis.png' });
      console.log('kaydedildi screenshots/v2-mac-detay-390-kaydirilmis.png');
    }
  }
  await ctx.close();
}
await browser.close();
if (errors.length) { console.log('HATALAR:\n' + errors.join('\n')); process.exitCode = 1; } else console.log('Konsol hatası yok');
