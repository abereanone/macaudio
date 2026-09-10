"""Per-item content redactions, applied by import_catalog.py (durable across
re-imports). Keyed by item slug.

  drop_audio:  True  -> publish the transcript but no playable/downloadable MP3
  remove_text: [..]  -> substrings stripped from the transcript before indexing
"""
REDACTIONS = {
    # NOTE: slug was previously "...elder-quals-part-2" which never matched the
    # real item slug, so this redaction silently no-op'd. Corrected below.
    "2022-06-12-elder-qualifications-part-2": {
        "drop_audio": True,
        "remove_text": [
            "in this sense of the church you all have temptation at work I think especially with Harquin there's probably plenty of opportunity to steal somehow ",
        ],
    },
}
