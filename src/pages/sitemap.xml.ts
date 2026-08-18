import type { APIRoute } from "astro";
import { getDB, all } from "@lib/db";

// Built at request time rather than by @astrojs/sitemap. This site is
// `output: "server"`, so /listen/[slug] is one handler backed by D1 -- at build
// time there is no list of recordings to walk, and a build-time sitemap would
// quietly contain only the handful of static pages. Querying D1 here also means
// a newly published recording appears without a redeploy.

const SITE = "https://teaching.michaelcoughlin.net";

// Static pages worth indexing. /listen is deliberately absent: it 302s to "/".
const STATIC_PATHS = ["/", "/about", "/scripture/"];

function xmlEscape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** D1 stores dates as YYYY-MM-DD or a datetime; <lastmod> wants the date part. */
function isoDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value.trim());
  return match ? match[1] : null;
}

function urlEntry(loc: string, lastmod: string | null): string {
  return (
    "  <url>\n" +
    `    <loc>${xmlEscape(loc)}</loc>\n` +
    (lastmod ? `    <lastmod>${lastmod}</lastmod>\n` : "") +
    "  </url>"
  );
}

export const GET: APIRoute = async (context) => {
  const db = getDB(context.locals);

  // published = 1 is the same gate /listen/[slug] enforces, so the sitemap can
  // never advertise a recording that the page itself would 404 on.
  const items = await all<{ slug: string; recorded_on: string | null; created_at: string | null }>(
    db,
    `SELECT slug, recorded_on, created_at
       FROM items
      WHERE published = 1 AND slug IS NOT NULL AND slug <> ''
      ORDER BY COALESCE(recorded_on, created_at) DESC`
  );

  const today = new Date().toISOString().slice(0, 10);

  const entries = [
    ...STATIC_PATHS.map((path) => urlEntry(SITE + path, today)),
    // `items` has no updated_at, so the recording date is the honest lastmod;
    // created_at covers the rows that never got one.
    ...items.map((item) =>
      urlEntry(`${SITE}/listen/${encodeURIComponent(item.slug)}`,
        isoDate(item.recorded_on) ?? isoDate(item.created_at))
    ),
  ];

  const xml =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    entries.join("\n") +
    "\n</urlset>\n";

  return new Response(xml, {
    headers: {
      "content-type": "application/xml; charset=utf-8",
      // Crawlers refetch this often; an hour keeps D1 out of the hot path
      // without letting a new recording sit unlisted for long.
      "cache-control": "public, max-age=3600",
    },
  });
};
