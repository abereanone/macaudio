"""Per-item content redactions, applied by import_catalog.py (durable across
re-imports). Keyed by item slug.

  drop_audio:  True  -> publish the transcript but no playable/downloadable MP3
  remove_text: [..]  -> substrings stripped from the transcript before indexing
"""
REDACTIONS = {
    "2022-06-12-elder-quals-part-2": {
        "drop_audio": True,
        "remove_text": ["I think especially with Harquin "],
    },
}
