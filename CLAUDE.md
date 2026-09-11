# macaudio

Astro + Cloudflare Workers site (D1 + R2) hosting Michael Coughlin's sermon
archive. Live at teaching.michaelcoughlin.net; audio served from
audio.michaelcoughlin.net.

## Ignore `tools/.obsolete/`

Retired code, kept tracked for history only. **Do not read it, cite it, or
factor it into a change.** It is not part of the system. See its README.

Most importantly: `import_catalog.py` (the full-reseed rebuild) is retired.
**There will be no re-import.** Do not propose one, and do not design around
one being possible.

## The catalog is maintained one item at a time

| Task | Tool |
|---|---|
| Add one recording (R2 upload + D1 insert + transcript) | `tools/add_sermon.py` |
| Video link / downloadable handouts | `tools/attach_extras.py` |
| (Re)index a transcript | `tools/attach_transcript.py` |
| Correct a primary passage | `tools/fix_passage.py` |
| Audit passages across the catalog | `tools/audit_passages.py` |
| Copy production into the local dev DB | `tools/sync_local_db.py` |

All of them default to **production**; `--local` targets dev D1. Credentials
come from `.dev.vars` (the token can see several Cloudflare accounts, so tools
must inject `CLOUDFLARE_ACCOUNT_ID` via `cf_env()` or wrangler stops to ask).

## `items.r2_key` is the only source of truth for audio URLs

The page builds `MEDIA_BASE_URL + item.r2_key`; nothing re-derives the path.

Keys are **category-free** — `audio/<slug>.<ext>`. They used to be
`audio/<category>/<slug>.<ext>`, which made every re-categorization either a
copy-object dance or a silent 404. Category is now ordinary metadata, changeable
with a plain `UPDATE`. Items created under the old scheme keep their old keys and
work fine; mixed conventions in the bucket are expected and correct.

## Passage detection

`attach_transcript.py` sets the primary passage to the FIRST scripture reference
in the transcript. That is wrong for topical sermons, which often open on an
unrelated verse. Pass `--passage` explicitly when the text is known, or correct
it afterwards with `fix_passage.py`.

## Putting sermons on YouTube

In progress. **Read `docs/youtube-pipeline.md` before touching
`tools/make_video.py` or `tools/make_thumb.mjs`** — it records what is built,
what was measured, and which decisions are already settled (and why).

| Task | Tool |
|---|---|
| Render one item to an upload-ready MP4 + thumbnail | `tools/make_video.py --slug SLUG` |
| Title card / thumbnail on its own | `tools/make_thumb.mjs` |

Uploads are **manual**, by choice: an unaudited YouTube API project locks every
upload to private permanently, with no appeal. Do not propose the API uploader
without addressing that first.

## Previewing locally

`npx wrangler pages dev ./dist` (after `npx astro build`) -- it is a **Pages**
project, so `wrangler dev` refuses it. That serves the LOCAL D1, which drifts
from production; run `tools/sync_local_db.py` first or a filter with no local
matches looks broken when it is fine.

`wrangler d1 export` cannot dump this database ("cannot export databases with
Virtual Tables (fts5)"), which is why that tool replays the base tables over the
query API instead. It never copies `item_fts` -- the 0003_fts_sync triggers own
it and rebuild it on insert.
