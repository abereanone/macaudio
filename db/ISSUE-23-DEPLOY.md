# Issue #23 — The Ten Commandments series: deploy notes

Branch: `issue-23-ten-commandments`

## What changed

**Schema / pipeline / UI (in git):**
- `db/migrations/0002_add_series_part.sql` — adds `items.series_part`.
- `tools/import_catalog.py` — emits `series_part`; reads a new optional
  `series_part` override field.
- `tools/overrides.py` — per-sermon `series_part` (commandment label) + corrected
  `passage` (the actual opening Scripture reading) for the 38 series sermons;
  `drop` for 3 duplicate recordings; removes "Elder Qualifications - Part 2" from
  the collection.
- `src/pages/listen/index.astro`, `src/pages/listen/[slug].astro`,
  `src/styles/global.css` — render the commandment label as a `.badge-part`.

**Content (NOT in git — `db/import.sql` is gitignored; lives in the source `.txt`
transcripts on Proton Drive + the regenerated import.sql):**
- Commandment label + corrected main-passage for all 38 sermons.
- Voice-preserving grammar/clarity cleanup of all 38 transcripts (fixed dropped
  contractions/possessives, a few meaning-inverting slips, scripture misquotes,
  duplicated/garbled words; broke up the worst run-ons). Targeted edits only —
  no wholesale rewrites, no dropped content.

## Data-quality findings applied
- Dropped 3 raw re-upload duplicates of the feed-correct cbcoh copies:
  `202111226JesusTheBoy`, `20220104HonorYourParents`, `CoarseJestingFinal`
  (dupes of "Did Jesus Break the 5th?", "The 5th Commandment Applied",
  "Does the Bible Whisper?"). Reversible: remove the `drop` overrides.
- "Elder Qualifications - Part 2" was misfiled into the series via its ID3 album
  (it's the week after the series ended; Part 1 has no collection). Cleared its
  collection.
- Series trimmed 42 → 38 sermons.

## Deploy to production (run from repo root, after review)

```sh
# 1) regenerate import.sql from the (now corrected) source transcripts + overrides
python tools/import_catalog.py

# 2) add the new column to the remote DB (local already has it)
$env:CLOUDFLARE_ACCOUNT_ID = "6481c7e370bbed874eb7679096eb1612"
npx wrangler d1 execute macaudio --remote --file ./db/migrations/0002_add_series_part.sql

# 3) reseed the remote DB (idempotent DELETE+INSERT; applies labels, passages,
#    corrected transcripts, dedup, and rebuilds item_fts)
npm run db:import:remote

# 4) deploy the site (UI badge)
npm run deploy
```

Verify after: each Ten Commandments sermon shows a commandment-label badge, the
"Main passage" matches the opening reading, and the series lists 38 messages.
