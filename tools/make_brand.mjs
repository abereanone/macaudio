// Brand asset generator for audio.michaelcoughlin.net (MC Audio).
// Emits master SVGs (favicon/logo) + rasterizes every PNG size + the OG card.
// Run: node tools/make_brand.mjs   (sharp ships with Astro)
import sharp from "sharp";
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PUB = join(ROOT, "public");
const ASSETS = join(ROOT, "src", "assets");
mkdirSync(ASSETS, { recursive: true });

// --- palette (matches src/styles/global.css dark theme) ---------------------
const C = {
  bgTop: "#15241b",
  bgBot: "#0b110d",
  border: "#2c4a3b",
  green1: "#a7e3c4",
  green2: "#4fae85",
  amber1: "#e7bd6f",
  amber2: "#cf972f",
};

// 5-bar waveform — symmetric, center tallest, center bar amber. Reads at 16px.
const BARS = [
  { h: 170, amber: false },
  { h: 290, amber: false },
  { h: 410, amber: true },
  { h: 290, amber: false },
  { h: 170, amber: false },
];

function barsSvg({ cx = 256, cy = 256, area = 320, bw = 44, rx = 22 } = {}) {
  const n = BARS.length;
  const x0 = cx - area / 2;
  const gap = (area - n * bw) / (n - 1);
  return BARS.map((b, i) => {
    const x = x0 + i * (bw + gap);
    const y = cy - b.h / 2;
    const fill = b.amber ? "url(#amber)" : "url(#green)";
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw}" height="${b.h}" rx="${rx}" fill="${fill}"/>`;
  }).join("\n    ");
}

const GRADS = `
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${C.bgTop}"/>
      <stop offset="1" stop-color="${C.bgBot}"/>
    </linearGradient>
    <linearGradient id="green" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${C.green1}"/>
      <stop offset="1" stop-color="${C.green2}"/>
    </linearGradient>
    <linearGradient id="amber" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${C.amber1}"/>
      <stop offset="1" stop-color="${C.amber2}"/>
    </linearGradient>
  </defs>`;

// Master emblem: rounded tile + waveform.
const emblem = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="MC Audio">${GRADS}
  <rect x="0" y="0" width="512" height="512" rx="116" fill="url(#bg)"/>
  <rect x="5" y="5" width="502" height="502" rx="112" fill="none" stroke="${C.border}" stroke-width="4"/>
  <g>
    ${barsSvg()}
  </g>
</svg>`;

writeFileSync(join(PUB, "favicon.svg"), emblem);
writeFileSync(join(PUB, "logo.svg"), emblem);
writeFileSync(join(ASSETS, "logo.svg"), emblem);

// --- PNG icons --------------------------------------------------------------
const png = (size) => sharp(Buffer.from(emblem)).resize(size, size).png();
const icons = [
  ["favicon-16.png", 16],
  ["favicon-32.png", 32],
  ["favicon-48.png", 48],
  ["apple-touch-icon.png", 180],
  ["icon-192.png", 192],
  ["icon-512.png", 512],
];

// --- Open Graph card 1200x630 ----------------------------------------------
const OG_W = 1200, OG_H = 630;
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="${OG_W}" height="${OG_H}" viewBox="0 0 ${OG_W} ${OG_H}">
  ${GRADS.replace('id="bg" x1="0" y1="0" x2="0" y2="1"', 'id="bg" x1="0" y1="0" x2="1" y2="1"')}
  <rect width="${OG_W}" height="${OG_H}" fill="url(#bg)"/>
  <!-- faint waveform field along the bottom -->
  <g opacity="0.10" fill="${C.green1}">
    ${Array.from({ length: 48 }, (_, i) => {
      const x = 40 + i * 24;
      const h = 30 + Math.round(120 * Math.abs(Math.sin(i * 0.7)) + (i % 3) * 20);
      return `<rect x="${x}" y="${OG_H - 40 - h}" width="9" height="${h}" rx="4"/>`;
    }).join("\n    ")}
  </g>
  <!-- emblem -->
  <g transform="translate(90,150)">
    <rect width="200" height="200" rx="46" fill="url(#bg)"/>
    <rect x="2" y="2" width="196" height="196" rx="44" fill="none" stroke="${C.border}" stroke-width="3"/>
    <g transform="translate(20,20) scale(0.3125)">${barsSvg()}</g>
  </g>
  <!-- text -->
  <text x="330" y="232" font-family="Georgia, 'Times New Roman', serif" font-weight="700" font-size="92" fill="#eaf3ed">Michael Coughlin</text>
  <text x="334" y="300" font-family="Georgia, serif" font-style="italic" font-size="44" fill="${C.green1}">Audio Archive</text>
  <text x="334" y="372" font-family="Segoe UI, Arial, sans-serif" font-size="30" fill="#9bb0a2">Sermons &#183; Classes &#183; Conferences &#183; Open-air preaching</text>
  <text x="90" y="585" font-family="Segoe UI, Arial, sans-serif" font-size="28" font-weight="600" fill="${C.amber1}">audio.michaelcoughlin.net</text>
</svg>`;

const tasks = [
  ...icons.map(([name, size]) => png(size).toFile(join(PUB, name)).then(() => name)),
  sharp(Buffer.from(og)).png().toFile(join(PUB, "og-default.png")).then(() => "og-default.png"),
];

const done = await Promise.all(tasks);
console.log("wrote: favicon.svg, logo.svg, src/assets/logo.svg, " + done.join(", "));
