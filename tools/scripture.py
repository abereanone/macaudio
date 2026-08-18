"""Scripture reference parsing for the sermon scripture index.

parse_refs(text) finds references like:
  John 8:12-20   Genesis 11:1-9   1 Corinthians 13   Romans 8:1   Ps 23
returning structured {book, chapter, verse_start, verse_end, ref_text}.
Book aliases cover abbreviations and "First/Second/Third" + numeric forms.

Used for the PRIMARY passage (first line of each sermon body) and, later, for
references mined from transcripts (regex; an LLM pass is the chosen higher-recall
path per SERMON_IMPORT_PLAN.md §7B).
"""
from __future__ import annotations

import re

# Canonical book -> list of aliases (lowercased, no trailing dot). The canonical
# name itself is always accepted.
_BOOKS: dict[str, list[str]] = {
    "Genesis": ["gen", "ge", "gn"],
    "Exodus": ["exod", "exo", "ex"],
    "Leviticus": ["lev", "lv"],
    "Numbers": ["num", "nm", "nu"],
    "Deuteronomy": ["deut", "dt"],
    "Joshua": ["josh", "jos"],
    "Judges": ["judg", "jdg"],
    "Ruth": ["rth", "ru"],
    "1 Samuel": ["1 sam", "1sam", "1 sm", "first samuel", "i samuel"],
    "2 Samuel": ["2 sam", "2sam", "2 sm", "second samuel", "ii samuel"],
    "1 Kings": ["1 kgs", "1kgs", "1 ki", "first kings", "i kings"],
    "2 Kings": ["2 kgs", "2kgs", "2 ki", "second kings", "ii kings"],
    "1 Chronicles": ["1 chron", "1 chr", "1chr", "first chronicles", "i chronicles"],
    "2 Chronicles": ["2 chron", "2 chr", "2chr", "second chronicles", "ii chronicles"],
    "Ezra": ["ezr"],
    "Nehemiah": ["neh"],
    "Esther": ["esth", "est"],
    "Job": ["jb"],
    "Psalms": ["psalm", "pss", "ps", "psa", "psalms"],
    "Proverbs": ["prov", "prv", "pr"],
    "Ecclesiastes": ["eccles", "eccl", "ecc", "qoh"],
    "Song of Solomon": ["song", "song of songs", "sos", "canticles"],
    "Isaiah": ["isa", "is"],
    "Jeremiah": ["jer", "jr"],
    "Lamentations": ["lam"],
    "Ezekiel": ["ezek", "eze"],
    "Daniel": ["dan", "dn"],
    "Hosea": ["hos"],
    "Joel": ["joe", "jl"],
    "Amos": ["am"],
    "Obadiah": ["obad", "ob"],
    "Jonah": ["jon"],
    "Micah": ["mic", "mc"],
    "Nahum": ["nah", "na"],
    "Habakkuk": ["hab", "hb"],
    "Zephaniah": ["zeph", "zep"],
    "Haggai": ["hag", "hg"],
    "Zechariah": ["zech", "zec"],
    "Malachi": ["mal"],
    "Matthew": ["matt", "mt"],
    "Mark": ["mrk", "mk", "mr"],
    "Luke": ["luk", "lk"],
    "John": ["john", "jhn", "jn", "joh"],
    "Acts": ["act"],
    "Romans": ["rom", "rm"],
    "1 Corinthians": ["1 cor", "1cor", "first corinthians", "i corinthians"],
    "2 Corinthians": ["2 cor", "2cor", "second corinthians", "ii corinthians"],
    "Galatians": ["gal"],
    "Ephesians": ["eph"],
    "Philippians": ["phil", "php"],
    "Colossians": ["col"],
    "1 Thessalonians": ["1 thess", "1 thes", "1thess", "first thessalonians", "i thessalonians"],
    "2 Thessalonians": ["2 thess", "2 thes", "2thess", "second thessalonians", "ii thessalonians"],
    "1 Timothy": ["1 tim", "1tim", "first timothy", "i timothy"],
    "2 Timothy": ["2 tim", "2tim", "second timothy", "ii timothy"],
    "Titus": ["tit"],
    "Philemon": ["philem", "phlm"],
    "Hebrews": ["heb"],
    "James": ["jas", "jm"],
    "1 Peter": ["1 pet", "1pet", "1 pt", "first peter", "i peter"],
    "2 Peter": ["2 pet", "2pet", "2 pt", "second peter", "ii peter"],
    "1 John": ["1 jn", "1jn", "1 jhn", "first john", "i john"],
    "2 John": ["2 jn", "2jn", "2 jhn", "second john", "ii john"],
    "3 John": ["3 jn", "3jn", "3 jhn", "third john", "iii john"],
    "Jude": ["jud"],
    "Revelation": ["rev", "rv", "apocalypse", "revelations"],
}

CANONICAL_BOOKS: list[str] = list(_BOOKS.keys())

# Build alias -> canonical (longest alias first so "1 cor" beats "cor"-like noise).
_ALIAS: dict[str, str] = {}
for _canon, _aliases in _BOOKS.items():
    _ALIAS[_canon.lower()] = _canon
    for _a in _aliases:
        _ALIAS[_a] = _canon

# Match the longest book phrases first.
_BOOK_ALTS = sorted(_ALIAS.keys(), key=len, reverse=True)
_BOOK_PATTERN = "|".join(re.escape(b) for b in _BOOK_ALTS)

# Separators between chapter and verse: ":" / "." (John 8:12, Ps 119.28) or the
# spoken "verse(s)" keyword (John chapter 8 verse 12). Range: dash / "through"
# / "thru" / "to".
_CV_SEP = r"(?:\s*[:.]\s*|\s*,?\s*verses?\s+)"
_RANGE = r"(?:\s*(?:[-–]|through|thru|to)\s*(?P<END>\d{1,3}))?"

# A named book reference, e.g. "John 8:12-20", "1 Corinthians 13", "Ps 23:1",
# "Romans chapter 8 verse 28", "Joh 3.22-36", "Psalm119.28".
_BOOKREF = (
    rf"(?P<book>{_BOOK_PATTERN})\.?\s*(?:chapters?\s+)?"
    r"(?P<chapter>\d{1,3})"
    rf"(?:{_CV_SEP}(?P<vstart>\d{{1,3}}){_RANGE.replace('END', 'vend')})?"
)
# A *bare* reference with no book beside it — resolved against the current book/
# chapter context while scanning: "chapter 8", "chapter 8 verse 28",
# "verse 28", "verses 5 through 7". This is how preachers actually walk a
# passage ("turn to Romans 8 … verse 4 … verse 5 …").
_BARECHAP = (
    r"chapters?\s+(?P<bchap>\d{1,3})"
    rf"(?:{_CV_SEP}(?P<bchapv>\d{{1,3}}))?"
)
_BAREVERSE = (
    r"verses?\s+(?P<bvstart>\d{1,3})"
    rf"{_RANGE.replace('END', 'bvend')}"
)
_REF_RE = re.compile(rf"\b(?:{_BOOKREF}|{_BARECHAP}|{_BAREVERSE})", re.IGNORECASE)


def parse_refs(text: str, unique: bool = True) -> list[dict]:
    """Return structured references found in `text`, in order. De-duplicated by
    default; pass unique=False to keep every occurrence (for frequency counts).

    Context-tracking: a bare "verse 6" / "chapter 2" with no book beside it is
    resolved against the most recently named book (and chapter), so a preacher
    walking a passage verse-by-verse indexes at verse granularity instead of
    losing everything after the first mention.
    """
    out: list[dict] = []
    seen: set[tuple] = set()
    cur_book: str | None = None
    cur_chap: int | None = None
    for m in _REF_RE.finditer(text or ""):
        if m.group("book"):
            canon = _ALIAS.get(m.group("book").lower().rstrip("."))
            if not canon:
                continue
            book = cur_book = canon
            chapter = cur_chap = int(m.group("chapter"))
            vstart = int(m.group("vstart")) if m.group("vstart") else None
            vend = int(m.group("vend")) if m.group("vend") else None
        elif m.group("bchap"):
            if not cur_book:
                continue  # a "chapter N" before any book is named — no context
            book = cur_book
            chapter = cur_chap = int(m.group("bchap"))
            vstart = int(m.group("bchapv")) if m.group("bchapv") else None
            vend = None
        elif m.group("bvstart"):
            if not cur_book or not cur_chap:
                continue  # a "verse N" with no established book+chapter
            book, chapter = cur_book, cur_chap
            vstart = int(m.group("bvstart"))
            vend = int(m.group("bvend")) if m.group("bvend") else None
        else:
            continue
        key = (book, chapter, vstart, vend)
        if unique and key in seen:
            continue
        seen.add(key)
        ref = {"book": book, "chapter": chapter, "verse_start": vstart, "verse_end": vend}
        ref["ref_text"] = format_ref(ref)
        out.append(ref)
    return out


def format_ref(ref: dict) -> str:
    """Canonical display string, e.g. 'John 3:22-36', 'Psalms 119:28', 'Romans 8'."""
    s = f"{ref['book']} {ref['chapter']}"
    if ref.get("verse_start"):
        s += f":{ref['verse_start']}"
        if ref.get("verse_end"):
            s += f"-{ref['verse_end']}"
    return s


def parse_primary(line: str) -> dict | None:
    """Parse the first reference from a sermon's primary-passage line.

    Strips a trailing translation tag like '(ESV)'. Returns the single primary
    ref or None when the line isn't a recognizable reference (e.g. the Good
    Works Inc. presentation).
    """
    cleaned = re.sub(r"\([^)]*\)\s*$", "", line or "").strip()
    refs = parse_refs(cleaned)
    return refs[0] if refs else None
