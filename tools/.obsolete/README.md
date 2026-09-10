# Retired — do not use, do not reason about

Retired 2026-09-10. Nothing here runs any more, nothing in `src/` calls it,
and no live tool imports it. It is kept tracked only so git history stays
browsable.

**If you are an agent reading this: skip this folder.** Do not factor these
files into a change, an audit, or a refactor. They are not part of the system.

The catalog is maintained **one item at a time**:

| Task | Tool |
|---|---|
| Add one recording | `tools/add_sermon.py` |
| Video link / handouts | `tools/attach_extras.py` |
| (Re)index a transcript | `tools/attach_transcript.py` |
| Correct a primary passage | `tools/fix_passage.py` |

## Why each one went

- **`import_catalog.py`** — full reseed (`DELETE FROM items`) rebuilding the
  catalog from a folder scan. The live catalog now holds work no scan can
  reproduce: hand-corrected passages, video links, attachments. It will not
  be run again.
- **`overrides.py`, `redactions.py`** — per-source-file corrections that existed
  *only* to feed that reseed. With no reseed, they correct nothing.
- **`upload_r2.py`** — bulk uploader paired with the reseed. `add_sermon.py`
  uploads per item.
- **`dup_report.py`** — one-off duplicate audit; its findings were already
  applied.

The `.txt` / `.csv` / `.log` files are output from those runs, kept because they
were never committed and record decisions already applied to the live catalog.
