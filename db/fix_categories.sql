-- Taxonomy fix: category = content TYPE, not distribution channel.
-- Some series aired via the Be A Berean podcast feed and got category='podcast'
-- even though they're really sermons / a conference / open-air preaching.
-- Also drops two collections that merely duplicated a category pill.
--
-- category has no CHECK constraint; item_fts has no category/collection columns,
-- so no FTS rebuild is needed. Idempotent (re-running is a no-op once applied).
--
-- Run:
--   $env:CLOUDFLARE_ACCOUNT_ID = "6481c7e370bbed874eb7679096eb1612"
--   npx wrangler d1 execute DB --remote --file ./db/fix_categories.sql
--   npx wrangler d1 execute DB --local  --file ./db/fix_categories.sql

-- 1) Re-file series to their true content type (keep the collection itself).
UPDATE items SET category = 'sermon'
  WHERE collection_id = (SELECT id FROM collections WHERE slug = 'hebrews');
UPDATE items SET category = 'conference'
  WHERE collection_id = (SELECT id FROM collections WHERE slug = 'fca-retreat-2019');
UPDATE items SET category = 'open_air'
  WHERE collection_id = (SELECT id FROM collections WHERE slug = 'open-air-preaching');

-- 2) Drop redundant collections (they just mirror a category pill).
--    Null the items' link first, then remove the now-empty collections.
UPDATE items SET collection_id = NULL
  WHERE collection_id IN (SELECT id FROM collections WHERE slug IN ('be-a-berean-podcast', 'open-air-preaching'));
DELETE FROM collections WHERE slug IN ('be-a-berean-podcast', 'open-air-preaching');
