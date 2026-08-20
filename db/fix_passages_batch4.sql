-- Batch 4/5 (final). Most of the remainder are podcast episodes, interviews and
-- reviews with no preaching text at all -- those keep their chapter-level ref
-- rather than get a fabricated verse range.
-- SKIPPED id=266: podcast on scripture memory; no single text
-- SKIPPED id=270: author interview
-- SKIPPED id=273: listener-question podcast
-- SKIPPED id=274: Refuting the Friendly Atheist podcast
-- SKIPPED id=275: Refuting the Friendly Atheist podcast
-- SKIPPED id=276: Refuting the Friendly Atheist podcast
-- SKIPPED id=277: missionary interview
-- SKIPPED id=280: movie review
-- SKIPPED id=283: Refuting the Friendly Atheist podcast
-- SKIPPED id=287: podcast, personal update + topical
-- SKIPPED id=288: Bible Thumping Wingnut guest episode
-- SKIPPED id=292: church-update podcast
-- SKIPPED id=300: re-posted TGC interview
-- SKIPPED id=310: open-air evangelism message; text not identified in window
UPDATE items SET passage_ref='Revelation 8:3-4' WHERE id=230;
DELETE FROM scripture_refs WHERE item_id=230 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (230, 'Revelation', 8, 3, 4, 1, 'Revelation 8:3-4', 'primary');
UPDATE items SET passage_ref='Hebrews 4:9-13' WHERE id=236;
DELETE FROM scripture_refs WHERE item_id=236 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (236, 'Hebrews', 4, 9, 13, 1, 'Hebrews 4:9-13', 'primary');
UPDATE items SET passage_ref='LBCF 30.7' WHERE id=253;
DELETE FROM scripture_refs WHERE item_id=253 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (253, 'LBCF', 30, 7, NULL, 1, 'LBCF 30.7', 'primary');
UPDATE items SET passage_ref='Psalms 51:1-6' WHERE id=257;
DELETE FROM scripture_refs WHERE item_id=257 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (257, 'Psalms', 51, 1, 6, 1, 'Psalms 51:1-6', 'primary');
UPDATE items SET passage_ref='Psalms 51:7-12' WHERE id=258;
DELETE FROM scripture_refs WHERE item_id=258 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (258, 'Psalms', 51, 7, 12, 1, 'Psalms 51:7-12', 'primary');
UPDATE items SET passage_ref='Psalms 51:13-19' WHERE id=259;
DELETE FROM scripture_refs WHERE item_id=259 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (259, 'Psalms', 51, 13, 19, 1, 'Psalms 51:13-19', 'primary');
UPDATE items SET passage_ref='Acts 20:15-38' WHERE id=264;
DELETE FROM scripture_refs WHERE item_id=264 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (264, 'Acts', 20, 15, 38, 1, 'Acts 20:15-38', 'primary');
UPDATE items SET passage_ref='Philippians 4:6-7' WHERE id=265;
DELETE FROM scripture_refs WHERE item_id=265 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (265, 'Philippians', 4, 6, 7, 1, 'Philippians 4:6-7', 'primary');
UPDATE items SET passage_ref='Psalms 22:1-31' WHERE id=279;
DELETE FROM scripture_refs WHERE item_id=279 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (279, 'Psalms', 22, 1, 31, 1, 'Psalms 22:1-31', 'primary');
UPDATE items SET passage_ref='Matthew 1:18-25' WHERE id=301;
DELETE FROM scripture_refs WHERE item_id=301 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (301, 'Matthew', 1, 18, 25, 1, 'Matthew 1:18-25', 'primary');
UPDATE items SET passage_ref='Ephesians 6:10-20' WHERE id=311;
DELETE FROM scripture_refs WHERE item_id=311 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (311, 'Ephesians', 6, 10, 20, 1, 'Ephesians 6:10-20', 'primary');
UPDATE items SET passage_ref='Ephesians 6:10-20' WHERE id=312;
DELETE FROM scripture_refs WHERE item_id=312 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (312, 'Ephesians', 6, 10, 20, 1, 'Ephesians 6:10-20', 'primary');
