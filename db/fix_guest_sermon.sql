-- #197 "Sermon 20200920" was a raw filename with a wrong primary (Ephesians 2)
-- and no series. It is Andrew Beebe guest-preaching at Covenant Bible Church on
-- 2020-09-20, continuing the 1 Peter series -- confirmed by Michael's own
-- back-reference the following week (#9): "Last week, Brother Andrew covered the
-- verses preceding, 13 through 16 ... You shall be holy, for I am holy."
-- The speaker had been set to Michael Coughlin by the importer's default.
INSERT OR IGNORE INTO speakers (name, slug, is_primary) VALUES ('Andrew Beebe', 'andrew-beebe', 0);
UPDATE items SET
  title='Be Holy, For I Am Holy',
  passage_ref='1 Peter 1:13-16',
  speaker_id=(SELECT id FROM speakers WHERE slug='andrew-beebe'),
  collection_id=(SELECT id FROM collections WHERE slug='1-peter')
WHERE id=197;
DELETE FROM scripture_refs WHERE item_id=197 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source)
  VALUES (197,'1 Peter',1,13,16,1,'1 Peter 1:13-16','primary');
