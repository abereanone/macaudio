// YouTube thumbnail generator (1280x720) for the sermon archive.
// Same palette, mark and type as tools/make_brand.mjs, so a thumbnail in a
// YouTube search result reads as the same brand as the site's OG card.
//
// Usage:
//   node tools/make_thumb.mjs --out x.png --title "..." [--passage "Jonah 2:1-7"]
//                             [--series "Jonah"] [--part "Part 3"] [--date 2024-05-12]
import sharp from "sharp";

const a = {};
for (let i = 2; i < process.argv.length; i += 2) a[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
if (!a.out || !a.title) { console.error("need --out and --title"); process.exit(1); }

const W = 1280, H = 720;
const C = { bgTop: "#15241b", bgBot: "#0b110d", green1: "#a7e3c4", green2: "#4fae85",
            amber1: "#e7bd6f", amber2: "#cf972f", text: "#eaf3ed", muted: "#9bb0a2" };

const esc = (s) => String(s ?? "").replace(/[<>&'"]/g, (c) =>
  ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c]));

// Georgia bold is ~0.52em average per char; good enough to wrap a sermon title.
function wrap(text, size, maxW, maxLines) {
  const words = String(text).split(/\s+/), lines = [];
  let cur = "";
  const width = (s) => s.length * size * 0.52;
  for (const w of words) {
    const test = cur ? cur + " " + w : w;
    if (width(test) > maxW && cur) { lines.push(cur); cur = w; } else cur = test;
  }
  if (cur) lines.push(cur);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = kept[maxLines - 1].replace(/[,;:]?$/, "") + "\u2026";
    return kept;
  }
  return lines;
}

// Title shrinks a step at a time rather than overflowing the card.
let size = 86, lines = wrap(a.title, size, 1030, 3);
while (lines.length > 2 && size > 54) { size -= 8; lines = wrap(a.title, size, 1030, 3); }

const bars = [170, 290, 410, 290, 170];
const mark = bars.map((h, i) => {
  const x = 96 + i * 22, sc = 0.20;
  return `<rect x="${x}" y="${196 - h * sc}" width="12" height="${h * sc}" rx="5"
           fill="${i === 2 ? C.amber1 : C.green2}"/>`;
}).join("");

const MONTHS = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"];
function fmtDate(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || "");
  if (!m) return d || null;
  return `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}`;
}

const meta = [a.series && a.part ? `${a.series} \u00b7 ${a.part}`
            : a.series || null,
              fmtDate(a.date)].filter(Boolean).join("  \u00b7  ");

const blockTop = 336;
const titleSvg = lines.map((l, i) =>
  `<text x="96" y="${blockTop + i * (size + 14)}" font-family="Georgia, 'Times New Roman', serif"
     font-weight="700" font-size="${size}" fill="${C.text}">${esc(l)}</text>`).join("");

const afterTitle = blockTop + (lines.length - 1) * (size + 14);

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0" stop-color="${C.bgTop}"/><stop offset="1" stop-color="${C.bgBot}"/>
    </linearGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect x="0" y="0" width="${W}" height="6" fill="${C.amber2}" opacity="0.9"/>
  ${mark}
  <text x="232" y="196" font-family="Georgia, serif" font-style="italic"
        font-size="40" fill="${C.green1}">Michael Coughlin</text>
  ${titleSvg}
  ${a.passage ? `<text x="98" y="${afterTitle + 78}" font-family="Georgia, serif" font-style="italic"
        font-size="46" fill="${C.green1}">${esc(a.passage)}</text>` : ""}
  ${meta ? `<text x="98" y="${afterTitle + (a.passage ? 140 : 78)}"
        font-family="Segoe UI, Arial, sans-serif" font-size="30" fill="${C.muted}">${esc(meta)}</text>` : ""}
  <text x="96" y="672" font-family="Segoe UI, Arial, sans-serif" font-size="28"
        font-weight="600" fill="${C.amber1}">audio.michaelcoughlin.net</text>
</svg>`;

await sharp(Buffer.from(svg)).png().toFile(a.out);
console.log(`wrote ${a.out}  (${lines.length} title line(s) at ${size}px)`);
