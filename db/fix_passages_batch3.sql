-- Batch 3/5. Includes the three LBCF confession lessons, whose primary was a
-- guessed Bible verse (Romans 13 / Matthew 28 / Exodus 20) rather than the
-- confession chapter they actually teach.
-- SKIPPED id=58: topical college talk; no text named
-- SKIPPED id=181: recites Philippians from memory, chapter never stated
-- SKIPPED id=193: DUPLICATE of #126 Jonah's 3 Rs
-- SKIPPED id=196: DUPLICATE of #124 Salvation Yahweh
-- SKIPPED id=197: raw title 'Sermon 20200920'; says 1 Peter 1 but no verses
-- SKIPPED id=209: whole-book review, spans all 5 chapters
-- SKIPPED id=215: podcast interview about a book, no preaching text
-- SKIPPED id=216: podcast interview, no preaching text
-- SKIPPED id=221: topical conference talk on evangelism
-- SKIPPED id=222: topical conference talk on suffering
-- SKIPPED id=225: children's class, no single text
UPDATE items SET passage_ref='John 3:1-8' WHERE id=99;
DELETE FROM scripture_refs WHERE item_id=99 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (99, 'John', 3, 1, 8, 1, 'John 3:1-8', 'primary');
UPDATE items SET passage_ref='1 Timothy 3:1-7' WHERE id=130;
DELETE FROM scripture_refs WHERE item_id=130 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (130, '1 Timothy', 3, 1, 7, 1, '1 Timothy 3:1-7', 'primary');
UPDATE items SET passage_ref='Psalms 110:1-7' WHERE id=157;
DELETE FROM scripture_refs WHERE item_id=157 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (157, 'Psalms', 110, 1, 7, 1, 'Psalms 110:1-7', 'primary');
UPDATE items SET passage_ref='1 Corinthians 15:41-50' WHERE id=194;
DELETE FROM scripture_refs WHERE item_id=194 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (194, '1 Corinthians', 15, 41, 50, 1, '1 Corinthians 15:41-50', 'primary');
UPDATE items SET passage_ref='1 Peter 1:15-21' WHERE id=198;
DELETE FROM scripture_refs WHERE item_id=198 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (198, '1 Peter', 1, 15, 21, 1, '1 Peter 1:15-21', 'primary');
UPDATE items SET passage_ref='2 Timothy 3:1-5' WHERE id=199;
DELETE FROM scripture_refs WHERE item_id=199 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (199, '2 Timothy', 3, 1, 5, 1, '2 Timothy 3:1-5', 'primary');
UPDATE items SET passage_ref='1 John 5:1-2' WHERE id=201;
DELETE FROM scripture_refs WHERE item_id=201 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (201, '1 John', 5, 1, 2, 1, '1 John 5:1-2', 'primary');
UPDATE items SET passage_ref='1 John 5:1-5' WHERE id=202;
DELETE FROM scripture_refs WHERE item_id=202 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (202, '1 John', 5, 1, 5, 1, '1 John 5:1-5', 'primary');
UPDATE items SET passage_ref='1 John 5:3-10' WHERE id=203;
DELETE FROM scripture_refs WHERE item_id=203 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (203, '1 John', 5, 3, 10, 1, '1 John 5:3-10', 'primary');
UPDATE items SET passage_ref='1 John 5:6-13' WHERE id=204;
DELETE FROM scripture_refs WHERE item_id=204 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (204, '1 John', 5, 6, 13, 1, '1 John 5:6-13', 'primary');
UPDATE items SET passage_ref='1 John 5:13-16' WHERE id=205;
DELETE FROM scripture_refs WHERE item_id=205 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (205, '1 John', 5, 13, 16, 1, '1 John 5:13-16', 'primary');
UPDATE items SET passage_ref='1 John 5:14-15' WHERE id=206;
DELETE FROM scripture_refs WHERE item_id=206 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (206, '1 John', 5, 14, 15, 1, '1 John 5:14-15', 'primary');
UPDATE items SET passage_ref='1 John 5:16-20' WHERE id=207;
DELETE FROM scripture_refs WHERE item_id=207 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (207, '1 John', 5, 16, 20, 1, '1 John 5:16-20', 'primary');
UPDATE items SET passage_ref='1 John 5:21' WHERE id=208;
DELETE FROM scripture_refs WHERE item_id=208 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (208, '1 John', 5, 21, NULL, 1, '1 John 5:21', 'primary');
UPDATE items SET passage_ref='Acts 2:1-13' WHERE id=210;
DELETE FROM scripture_refs WHERE item_id=210 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (210, 'Acts', 2, 1, 13, 1, 'Acts 2:1-13', 'primary');
UPDATE items SET passage_ref='LBCF 24.3' WHERE id=212;
DELETE FROM scripture_refs WHERE item_id=212 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (212, 'LBCF', 24, 3, NULL, 1, 'LBCF 24.3', 'primary');
UPDATE items SET passage_ref='LBCF 28.1' WHERE id=219;
DELETE FROM scripture_refs WHERE item_id=219 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (219, 'LBCF', 28, 1, NULL, 1, 'LBCF 28.1', 'primary');
UPDATE items SET passage_ref='LBCF 22.7' WHERE id=220;
DELETE FROM scripture_refs WHERE item_id=220 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (220, 'LBCF', 22, 7, NULL, 1, 'LBCF 22.7', 'primary');
UPDATE items SET passage_ref='Hebrews 1:1-4' WHERE id=226;
DELETE FROM scripture_refs WHERE item_id=226 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (226, 'Hebrews', 1, 1, 4, 1, 'Hebrews 1:1-4', 'primary');
UPDATE items SET passage_ref='Hebrews 1:5-6' WHERE id=227;
DELETE FROM scripture_refs WHERE item_id=227 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (227, 'Hebrews', 1, 5, 6, 1, 'Hebrews 1:5-6', 'primary');
UPDATE items SET passage_ref='Hebrews 1:7-14' WHERE id=228;
DELETE FROM scripture_refs WHERE item_id=228 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (228, 'Hebrews', 1, 7, 14, 1, 'Hebrews 1:7-14', 'primary');
