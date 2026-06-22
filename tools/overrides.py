"""Per-source-file metadata corrections, keyed by the audio file STEM (filename
without extension). Applied by import_catalog.py over the auto-derived metadata.
Fields (all optional): title, recorded_on (YYYY-MM-DD), speaker, collection,
category, passage (display + primary scripture ref; may be book-level like '1 John').
"""
OVERRIDES = {
    # Raw recorder copy of the 1 John Review — same recording as 20251228LBCSS1John;
    # this metadata makes it dedupe-merge into the published Review.
    "251228_0937": {
        "title": "1 John Review", "recorded_on": "2025-12-28",
        "speaker": "Michael Coughlin", "collection": "1 John",
        "category": "class", "passage": "1 John",
    },
    "20251228LBCSS1John": {"passage": "1 John"},  # the published Review — book-level main text
    "BAB 074 Hunger and Thirst": {
        "passage": "Matthew 5:6",
        # context-targeted (don't touch "Matthew 5, 6, and 7" earlier in the transcript)
        "replace_text": [["But in Matthew 5, 6,", "But in Matthew 5:6,"]],
    },
}
