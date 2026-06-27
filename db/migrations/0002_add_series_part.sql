-- Per-item series label (e.g. "1st Commandment · Part 1", "Introduction",
-- "Preface"). Lets listeners see at a glance where a message falls within a
-- structured series. First used by "The Ten Commandments" (Exodus 20) so each
-- sermon shows which commandment it expounds; NULL for items without one.
ALTER TABLE items ADD COLUMN series_part TEXT;
