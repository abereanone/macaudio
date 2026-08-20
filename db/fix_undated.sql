-- Undated / raw-filename items: real titles, dates and passages from the
-- transcripts and the source files' mtime.
-- mtime is trustworthy for the open-air set: for the five whose filename
-- already carried a date, mtime matches it exactly. That also resolves the
-- '2015-19-26' filename typo on #305 (month 19) -> 2015-09-26, the same day
-- as its two sibling open-airs.
-- #301/302 are the 2014 Big Ten Championship (Ohio State v Wisconsin, Dec 6
-- 2014) -- the preacher opens 'Good afternoon Buckeyes and Badgers fans'.
-- NOT dated: #181 and #194 are .m4a guest sermons whose mtime (2024, 2023) is
-- plainly a later copy, not the recording date. Left undated rather than guessed.
UPDATE items SET recorded_on='2022-02-13' WHERE id=157;
UPDATE items SET title='If Any Encouragement in Christ', passage_ref='Philippians 2:1-13' WHERE id=181;
DELETE FROM scripture_refs WHERE item_id=181 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (181, 'Philippians', 2, 1, 13, 1, 'Philippians 2:1-13', 'primary');
UPDATE items SET title='Bible Bee: Acts 2', recorded_on='2021-06-15' WHERE id=210;
UPDATE items SET title='Things Above Us Roundtable 34', recorded_on='2020-01-31' WHERE id=297;
UPDATE items SET recorded_on='2020-01-04' WHERE id=300;
UPDATE items SET title='Big Ten Open-Air: The Birth of Christ', recorded_on='2014-12-06' WHERE id=301;
UPDATE items SET title='Big Ten Open-Air: The Resurrection', recorded_on='2014-12-06', passage_ref='1 Corinthians 15:1-8' WHERE id=302;
DELETE FROM scripture_refs WHERE item_id=302 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (302, '1 Corinthians', 15, 1, 8, 1, '1 Corinthians 15:1-8', 'primary');
UPDATE items SET title='Open-Air: A Living Hope', recorded_on='2015-09-26', passage_ref='1 Peter 1:1-9' WHERE id=303;
DELETE FROM scripture_refs WHERE item_id=303 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (303, '1 Peter', 1, 1, 9, 1, '1 Peter 1:1-9', 'primary');
UPDATE items SET title='Fools Become Friends', recorded_on='2015-09-26', passage_ref='Psalms 14:1-7' WHERE id=304;
DELETE FROM scripture_refs WHERE item_id=304 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (304, 'Psalms', 14, 1, 7, 1, 'Psalms 14:1-7', 'primary');
UPDATE items SET title='The Precious Blood of Christ', recorded_on='2015-09-26', passage_ref='1 Peter 1:18-19' WHERE id=305;
DELETE FROM scripture_refs WHERE item_id=305 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (305, '1 Peter', 1, 18, 19, 1, '1 Peter 1:18-19', 'primary');
UPDATE items SET title='Chili on a Chilly Day', recorded_on='2015-02-28' WHERE id=306;
UPDATE items SET title='Talking with Kurt Downtown', recorded_on='2011-01-05' WHERE id=307;
UPDATE items SET title='The Heart That Loves Sinners', recorded_on='2015-06-19', passage_ref='Psalms 117:1-2' WHERE id=310;
DELETE FROM scripture_refs WHERE item_id=310 AND is_primary=1;
INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) VALUES (310, 'Psalms', 117, 1, 2, 1, 'Psalms 117:1-2', 'primary');
