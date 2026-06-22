"""Transcript formatting helpers."""
from __future__ import annotations

import re

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=["\'(]?[A-Z0-9])')


def paragraphize(text: str, min_chars: int = 350, max_sentences: int = 6) -> str:
    """Re-flow a transcript into readable paragraphs.

    Whisper output is punctuated + capitalized but barely broken into paragraphs
    (only on long pauses), so a single 'paragraph' can run thousands of chars.
    This regroups by sentence: start a new paragraph once the current one has at
    least 3 sentences AND ~min_chars, or hits max_sentences. Existing newlines
    are flattened first so it works on already-stitched transcripts too.
    """
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    if not text:
        return ""
    sentences = _SENT_SPLIT.split(text)
    paras: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for s in sentences:
        cur.append(s)
        cur_len += len(s)
        if (len(cur) >= 3 and cur_len >= min_chars) or len(cur) >= max_sentences:
            paras.append(" ".join(cur))
            cur, cur_len = [], 0
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)
