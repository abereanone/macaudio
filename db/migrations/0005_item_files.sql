-- Downloadable attachments for an item: teaching outlines, handouts, slides.
--
-- A table rather than a `notes_key` column on items because the teaching flow
-- produces PAIRS — e.g. theGospel-TEACHER.docx + theGospel-STUDENT.docx — and a
-- single column would force a choice between them.
--
-- r2_key convention:  files/<item slug>/<filename>
-- Note there is NO category segment, unlike audio's audio/<category>/<slug>.<ext>.
-- That was a real bug: audio keys are derived from a MUTABLE field, so
-- re-categorizing an item silently 404s its audio. Attachment keys depend only
-- on the slug.
--
-- Attachments are NOT indexed in item_fts. If that's ever wanted it needs new
-- triggers on this table — 0003_fts_sync's triggers own item_fts and know
-- nothing about it.
CREATE TABLE item_files (
  id         INTEGER PRIMARY KEY,
  item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL DEFAULT 'notes',   -- notes | handout | slides | outline
  title      TEXT NOT NULL,                   -- button label, e.g. "Teacher outline"
  r2_key     TEXT NOT NULL UNIQUE,
  mime       TEXT,
  size_bytes INTEGER,
  sort       INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_item_files_item ON item_files(item_id);
