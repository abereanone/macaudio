-- audio.michaelcoughlin.net — catalog schema (D1 / SQLite).
-- Public audio archive: sermons, classes, conferences, open-air, podcast (Be A Berean).

PRAGMA foreign_keys = ON;

-- Speakers / preachers. Primarily Michael; guests credited.
CREATE TABLE speakers (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  slug        TEXT NOT NULL UNIQUE,
  bio         TEXT,
  is_primary  INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Collections = series / podcast / class groupings (1 John, Be A Berean, 1689…).
CREATE TABLE collections (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,
  title       TEXT NOT NULL,
  category    TEXT,                  -- default category for items in it
  description TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A single audio recording.
CREATE TABLE items (
  id            INTEGER PRIMARY KEY,
  slug          TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  category      TEXT NOT NULL DEFAULT 'sermon',  -- sermon | class | conference | open_air | podcast
  speaker_id    INTEGER REFERENCES speakers(id) ON DELETE SET NULL,
  collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
  recorded_on   TEXT,                 -- YYYY-MM-DD
  passage_ref   TEXT,                 -- main scripture, freeform
  description   TEXT,
  r2_key        TEXT,                 -- object key in MEDIA bucket
  duration_sec  INTEGER,
  source_path   TEXT UNIQUE,          -- original file path (idempotency key)
  transcript_status TEXT NOT NULL DEFAULT 'none',  -- none | done
  published     INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_speaker ON items(speaker_id);
CREATE INDEX idx_items_collection ON items(collection_id);
CREATE INDEX idx_items_date ON items(recorded_on);

CREATE TABLE item_transcripts (
  item_id    INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  text       TEXT NOT NULL,
  model      TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Scripture index: main text (is_primary=1, source='primary') + references
-- mentioned in the transcript (is_primary=0, source='transcript').
CREATE TABLE scripture_refs (
  id          INTEGER PRIMARY KEY,
  item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  book        TEXT NOT NULL,
  chapter     INTEGER,
  verse_start INTEGER,
  verse_end   INTEGER,
  is_primary  INTEGER NOT NULL DEFAULT 0,
  ref_text    TEXT,
  source      TEXT NOT NULL DEFAULT 'transcript'
);
CREATE INDEX idx_scripture_item ON scripture_refs(item_id);
CREATE INDEX idx_scripture_book ON scripture_refs(book);
CREATE INDEX idx_scripture_primary ON scripture_refs(is_primary);

-- Full-text search over title + speaker + passage + transcript.
CREATE VIRTUAL TABLE item_fts USING fts5(item_id UNINDEXED, title, speaker, passage_ref, transcript);
