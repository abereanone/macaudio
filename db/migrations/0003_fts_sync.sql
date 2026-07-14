-- Keep item_fts (the FTS5 search table) in sync automatically.
--
-- item_fts is a plain (non-external-content) FTS5 table holding COPIES of each
-- item's title, speaker name, passage_ref and transcript text. Before this it
-- was only ever populated by full rebuilds (import.sql) or by hand, so any
-- single-row edit — a rename, a re-transcribe, an added sermon — had to
-- remember to touch item_fts too, or search would silently go stale (that was
-- the "two tables" footgun behind the manual rename fixes).
--
-- These triggers make ordinary INSERT/UPDATE/DELETE on `items` and
-- `item_transcripts` maintain item_fts. Because triggers now OWN item_fts, the
-- bulk seed (tools/import_catalog.py -> db/import.sql) and the single-item
-- tools (tools/add_sermon.py, tools/attach_transcript.py) no longer write it
-- themselves — doing so would double-insert rows.
--
-- Known limitation: none of the maintained columns include free-form data that
-- changes outside items/item_transcripts/speakers.name, so those three cover
-- every edit path. Idempotent (DROP IF EXISTS) so it is safe to re-run.

DROP TRIGGER IF EXISTS items_fts_ai;
DROP TRIGGER IF EXISTS items_fts_au;
DROP TRIGGER IF EXISTS items_fts_ad;
DROP TRIGGER IF EXISTS item_transcripts_fts_ai;
DROP TRIGGER IF EXISTS item_transcripts_fts_au;
DROP TRIGGER IF EXISTS item_transcripts_fts_ad;
DROP TRIGGER IF EXISTS speakers_fts_au;

-- New item -> add its search row (transcript filled in later, if any).
CREATE TRIGGER items_fts_ai AFTER INSERT ON items BEGIN
  INSERT INTO item_fts (item_id, title, speaker, passage_ref, transcript)
  SELECT new.id, new.title,
         COALESCE((SELECT name FROM speakers WHERE id = new.speaker_id), ''),
         COALESCE(new.passage_ref, ''),
         COALESCE((SELECT text FROM item_transcripts WHERE item_id = new.id), '');
END;

-- Deleted item -> drop its search row.
CREATE TRIGGER items_fts_ad AFTER DELETE ON items BEGIN
  DELETE FROM item_fts WHERE item_id = old.id;
END;

-- Edited title / passage / speaker -> rebuild the search row (FTS5 has no
-- in-place column UPDATE that recomputes cleanly, so delete + re-insert).
CREATE TRIGGER items_fts_au AFTER UPDATE OF title, passage_ref, speaker_id ON items BEGIN
  DELETE FROM item_fts WHERE item_id = old.id;
  INSERT INTO item_fts (item_id, title, speaker, passage_ref, transcript)
  SELECT new.id, new.title,
         COALESCE((SELECT name FROM speakers WHERE id = new.speaker_id), ''),
         COALESCE(new.passage_ref, ''),
         COALESCE((SELECT text FROM item_transcripts WHERE item_id = new.id), '');
END;

-- Transcript attached / changed / removed -> update the transcript column.
CREATE TRIGGER item_transcripts_fts_ai AFTER INSERT ON item_transcripts BEGIN
  UPDATE item_fts SET transcript = new.text WHERE item_id = new.item_id;
END;

CREATE TRIGGER item_transcripts_fts_au AFTER UPDATE ON item_transcripts BEGIN
  UPDATE item_fts SET transcript = new.text WHERE item_id = new.item_id;
END;

CREATE TRIGGER item_transcripts_fts_ad AFTER DELETE ON item_transcripts BEGIN
  UPDATE item_fts SET transcript = '' WHERE item_id = old.item_id;
END;

-- Speaker renamed -> refresh the copied name on all of their items.
CREATE TRIGGER speakers_fts_au AFTER UPDATE OF name ON speakers BEGIN
  UPDATE item_fts SET speaker = new.name
  WHERE item_id IN (SELECT id FROM items WHERE speaker_id = new.id);
END;
