-- Data fix: correct misspelled blog name "pathios" -> "patheos" in seeded
-- transcripts. Two forms occur ("friendlyatheist.pathios.com" and a bare
-- "...at pathios.com"), so we replace the token itself to catch every form.
--
-- item_fts has no triggers (it's populated by a manual INSERT...SELECT in
-- import.sql), so the FTS copy of the transcript must be updated too or search
-- will still match the typo. Both statements are idempotent (REPLACE + guard),
-- safe to re-run, and apply to whichever DB you target (--local / --remote).
--
-- Run:
--   $env:CLOUDFLARE_ACCOUNT_ID = "6481c7e370bbed874eb7679096eb1612"
--   npx wrangler d1 execute DB --remote --file ./db/fix_pathios.sql
--   npx wrangler d1 execute DB --local  --file ./db/fix_pathios.sql

UPDATE item_transcripts
SET    text = REPLACE(text, 'pathios', 'patheos')
WHERE  text LIKE '%pathios%';

UPDATE item_fts
SET    transcript = REPLACE(transcript, 'pathios', 'patheos')
WHERE  transcript LIKE '%pathios%';
