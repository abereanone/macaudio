-- Series sweep: runs whose members were never linked to a collection because
-- their titles name the topic, not the series. Same failure that left the Jonah
-- run (17) and Refuting the Friendly Atheist (8) orphaned.
--
-- 1) The 1689 Confession. Ten teachings walking the London Baptist Confession
--    chapter by chapter, spread across podcast and sermon categories, with no
--    collection at all. series_part is the chapter/paragraph each one covers.
INSERT OR IGNORE INTO collections (slug, title, category)
  VALUES ('1689-confession', 'The 1689 Confession', 'podcast');
UPDATE items SET collection_id=(SELECT id FROM collections WHERE slug='1689-confession')
  WHERE id IN (10,56,212,214,217,218,219,220,223,253);
UPDATE items SET series_part='Chapter 1.2'  WHERE id=223;
UPDATE items SET series_part='Chapter 8.5'  WHERE id=10;
UPDATE items SET series_part='Chapter 19'   WHERE id=217;
UPDATE items SET series_part='Chapter 22.7' WHERE id=220;
UPDATE items SET series_part='Chapter 24.3' WHERE id=212;
UPDATE items SET series_part='Chapter 26'   WHERE id=214;
UPDATE items SET series_part='Chapter 28.1' WHERE id=219;
UPDATE items SET series_part='Chapter 30.6' WHERE id=56;
UPDATE items SET series_part='Chapter 30.7' WHERE id=253;
UPDATE items SET series_part='Chapter 32.3' WHERE id=218;

-- The four that still had no reference at all get theirs, so an "LBCF 26"
-- search resolves them like any verse lookup.
UPDATE items SET passage_ref='LBCF 26'   WHERE id=214;
UPDATE items SET passage_ref='LBCF 19'   WHERE id=217;
UPDATE items SET passage_ref='LBCF 32.3' WHERE id=218;
UPDATE items SET passage_ref='LBCF 1.2'  WHERE id=223;
DELETE FROM scripture_refs WHERE item_id IN (214,217,218,223) AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES
  (214,'LBCF',26,NULL,NULL,1,'LBCF 26','primary'),
  (217,'LBCF',19,NULL,NULL,1,'LBCF 19','primary'),
  (218,'LBCF',32,3,NULL,1,'LBCF 32.3','primary'),
  (223,'LBCF',1,2,NULL,1,'LBCF 1.2','primary');

-- 2) Elder Qualifications: a two-part sermon series (1 Timothy 3) with no collection.
INSERT OR IGNORE INTO collections (slug, title, category)
  VALUES ('elder-qualifications', 'Elder Qualifications', 'sermon');
UPDATE items SET collection_id=(SELECT id FROM collections WHERE slug='elder-qualifications')
  WHERE id IN (112,130);
UPDATE items SET series_part='Part 1' WHERE id=112;
UPDATE items SET series_part='Part 2' WHERE id=130;

-- 3) Living in the New Covenant: a two-session conference series.
INSERT OR IGNORE INTO collections (slug, title, category)
  VALUES ('living-in-the-new-covenant', 'Living in the New Covenant', 'conference');
UPDATE items SET collection_id=(SELECT id FROM collections WHERE slug='living-in-the-new-covenant')
  WHERE id IN (221,222);
UPDATE items SET series_part='Evangelism' WHERE id=221;
UPDATE items SET series_part='Suffering'  WHERE id=222;
