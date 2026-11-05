// OZBET ikon üretici: SVG kaynaklarından PNG ikonlar üretir.
// Kullanım: npm run icons
import { Resvg } from '@resvg/resvg-js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pub = path.join(root, 'public');
const iconsDir = path.join(pub, 'icons');
fs.mkdirSync(iconsDir, { recursive: true });

const BG = '#2340C8';
const INK = '#FFFFFF';
const ACCENT = '#C9D3FF';

// Sade, yazı tabanlı işaret: "OZ" monogramı, altında ince vurgu çizgisi ve "BET".
// Harfler path olarak çizilir (font bağımlılığı yok).
function mark({ size, pad, radius, withWord = true }) {
  const s = size;
  const inner = s - pad * 2;
  const u = inner / 100; // 100 birimlik ızgara
  const x0 = pad, y0 = pad;
  const sw = 13 * u; // kontur kalınlığı
  // "O": yuvarlatılmış dikdörtgen kontur
  const oX = x0 + 10 * u, oY = y0 + (withWord ? 14 : 22) * u, oW = 36 * u, oH = 48 * u;
  // "Z": üç parçalı çoklu çizgi
  const zX = x0 + 54 * u, zY = oY, zW = 32 * u, zH = oH;
  const word = withWord
    ? `<rect x="${x0 + 10 * u}" y="${oY + oH + 9 * u}" width="${80 * u}" height="${4 * u}" fill="${ACCENT}"/>`
      + `<text x="${x0 + 50 * u}" y="${oY + oH + 30 * u}" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="${15 * u}" letter-spacing="${6 * u}" fill="${INK}">BET</text>`
    : `<rect x="${x0 + 10 * u}" y="${oY + oH + 10 * u}" width="${80 * u}" height="${5 * u}" fill="${ACCENT}"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}">
  <rect width="${s}" height="${s}" rx="${radius}" fill="${BG}"/>
  <rect x="${oX + sw / 2}" y="${oY + sw / 2}" width="${oW - sw}" height="${oH - sw}" rx="${(oW - sw) / 2}" fill="none" stroke="${INK}" stroke-width="${sw}"/>
  <path d="M${zX} ${zY + sw / 2} H${zX + zW} L${zX} ${zY + zH - sw / 2} H${zX + zW}" fill="none" stroke="${ACCENT}" stroke-width="${sw}" stroke-linejoin="bevel" stroke-linecap="butt"/>
  ${word}
</svg>`;
}

function render(svg, out, width) {
  const png = new Resvg(svg, { fitTo: { mode: 'width', value: width }, font: { loadSystemFonts: true } }).render().asPng();
  fs.writeFileSync(out, png);
  console.log('yazıldı', path.relative(root, out));
}

const fav = mark({ size: 64, pad: 4, radius: 14, withWord: false });
fs.writeFileSync(path.join(pub, 'favicon.svg'), fav);
console.log('yazıldı public/favicon.svg');

const std = mark({ size: 512, pad: 40, radius: 96 });
fs.writeFileSync(path.join(iconsDir, 'icon.svg'), std);
render(std, path.join(iconsDir, 'icon-192.png'), 192);
render(std, path.join(iconsDir, 'icon-512.png'), 512);
// Maskable: güvenli alan için daha fazla iç boşluk, köşe yuvarlama yok
render(mark({ size: 512, pad: 104, radius: 0 }), path.join(iconsDir, 'icon-maskable-512.png'), 512);
render(mark({ size: 180, pad: 18, radius: 0 }), path.join(iconsDir, 'apple-touch-icon.png'), 180);
