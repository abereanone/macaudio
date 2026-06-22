"""Per-source-file metadata corrections, keyed by the audio file STEM (filename
without extension). Applied by import_catalog.py over the auto-derived metadata.
Fields (all optional): title, recorded_on (YYYY-MM-DD), speaker, collection,
category, passage (display + primary scripture ref; may be book-level like '1 John'),
drop (True -> skip this file entirely; for duplicates the auto-dedupe can't catch
because the filenames are unrelated).
"""
OVERRIDES = {
    # Duplicate recording of "Elder Qualifications - Part 2" (2022-06-12), saved
    # under the raw recorder name DM620479.MP3. The titles are unrelated so the
    # (title, year) dedupe can't merge it — drop it explicitly.
    "DM620479": {"drop": True},
    # Elder Qualifications - Part 2: the transcript-frequency heuristic mis-picked
    # Mark 11; the sermon's main text is 1 Timothy 3. (Audio is dropped via
    # redactions.py — published as transcript-only.)
    "20220612ElderQualsPart2": {"passage": "1 Timothy 3"},
    # Raw recorder copy of the 1 John Review — same recording as 20251228LBCSS1John;
    # this metadata makes it dedupe-merge into the published Review.
    "251228_0937": {
        "title": "1 John Review", "recorded_on": "2025-12-28",
        "speaker": "Michael Coughlin", "collection": "1 John",
        "category": "class", "passage": "1 John",
    },
    "20251228LBCSS1John": {"passage": "1 John"},  # the published Review — book-level main text
    # Open-air preaching that aired on the podcast — file by content type.
    "BAB 006 Homosexual Pride Parade Preaching June 2019": {"category": "open_air"},
    "BAB 074 Hunger and Thirst": {
        "passage": "Matthew 5:6",
        # context-targeted (don't touch "Matthew 5, 6, and 7" earlier in the transcript)
        "replace_text": [["But in Matthew 5, 6,", "But in Matthew 5:6,"]],
    },
}
