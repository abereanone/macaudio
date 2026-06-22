"""Build the macaudio catalog (v2) — dedup + ID3-tag/feed-driven metadata.

Metadata priority: feeds (c:\\code\\feeds) > ID3 tags > filename parsing.
- Series/collection comes from the matching feed (1 Peter, Ten Commandments,
  Psalm 51, Hebrews, The Church, 1 John) or a non-generic ID3 album.
- Speaker comes from the 1 John feed (per episode) or the ID3 artist.
- Main-text passage comes from a scripture ref in the (feed/ID3) title, else a
  transcript scan constrained to the series' book, else the dominant chapter.
- DEDUPE: one row per recording (norm title + year), preferring the clean
  cbcoh copy over CBC-top / Be-A-Berean(old) twins.

    python tools/import_catalog.py             # build db/import.sql
    python tools/import_catalog.py --apply      # build + apply to local D1
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402
try:
    from redactions import REDACTIONS  # noqa: E402
except ImportError:
    REDACTIONS = {}
try:
    from overrides import OVERRIDES  # noqa: E402
except ImportError:
    OVERRIDES = {}

# Series name normalization (collapse tag/feed variants to one display name).
COLLECTION_NORMALIZE = {
    "Communion": "Communion Message",
    "Communion Message": "Communion Message",
    "Communion Messages": "Communion Message",
    "Communion Messages at CBC": "Communion Message",
    "BAB": "Be a Berean podcast",
    "1 Peter at CovenantBibleOhio.com": "1 Peter",
}

REPO = Path(__file__).resolve().parent.parent
IMPORT_SQL = REPO / "db" / "import.sql"
FEEDS = Path(r"C:/code/feeds")
PROTON = Path(r"C:/Users/mac/Proton Drive/abereanone/My files")
BT = PROTON / "02_Bible-Teaching"
DEFAULT_SPEAKER = "Michael Coughlin"
MICHAEL_ONLY = True  # this is Michael's audio site — exclude items he didn't speak
# Two files on the SAME recording date whose durations are within this many
# seconds are treated as the same recording (a re-encode / silence-clipped copy).
# True dups are within seconds; a sermon vs its communion message on the same day
# differ by 20-40 min, so this comfortably separates them.
DUP_DURATION_TOL = 120
GENERIC_ALBUMS = {"", "covenant bible church", "covenantbibleohio.com", "lbc"}
# ID3 artist values that aren't real people (recorder/software defaults).
BAD_ARTIST = re.compile(r"freeswitch|mod_conference|my recording|untitled|^track ?\d|^unknown", re.I)

# Source folders in DEDUPE PRIORITY order (first wins when the same recording
# appears more than once). (folder, category, recursive, kind)
TARGETS = [
    (BT / "CBC Sermons" / "cbcoh", "sermon", True, "cbcoh"),
    (BT / "CBC Sermons", "sermon", False, "cbc"),
    (PROTON / "rawdio" / "lbc", "class", False, "onejohn"),
    (BT / "BEABEREAN", "podcast", True, "bab"),
    (BT / "Open Airs", "open_air", True, "openair"),
]

# Feed file -> series/collection name (only feeds that cover macaudio content).
FEED_SERIES = {
    "lbc1John.xml": "1 John",
    "1Peter.xml": "1 Peter",
    "10Commandments.xml": "The Ten Commandments",
    "Ps51.xml": "Psalm 51",
    "Hebrews.xml": "Hebrews",
    "churchdiscipline.xml": "The Church",
}


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "item"


def split_camel(s: str) -> str:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", s)
    return re.sub(r"[_]+", " ", s).strip()


def iso_from_yyyymmdd(d: str) -> str | None:
    m = re.match(r"(\d{4})(\d{2})(\d{2})", d)
    if not m:
        return None
    y, mo, da = m.groups()
    if 1990 <= int(y) <= 2099 and 1 <= int(mo) <= 12 and 1 <= int(da) <= 31:
        return f"{y}-{mo}-{da}"
    return None


def norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", (s or "").lower())
    s = re.sub(r"\bprocessed\b|\bpart\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def read_tags(p: Path) -> dict:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags",
                              "-of", "default=noprint_wrappers=1", str(p)],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception:
        out = ""
    d = {}
    for line in out.splitlines():
        if line.startswith("TAG:") and "=" in line:
            k, v = line[4:].split("=", 1)
            d.setdefault(k.strip().lower(), v.strip())
        elif line.startswith("duration=") and "__dur__" not in d:
            try:
                d["__dur__"] = float(line.split("=", 1)[1])
            except ValueError:
                pass
    return d


def book_of(name: str) -> str | None:
    """Canonical Bible book if `name` is/contains one (e.g. '1 Peter', 'Psalm 51')."""
    refs = scripture.parse_refs((name or "") + " 1")
    return refs[0]["book"] if refs else None


def load_feeds() -> dict:
    """decoded enclosure basename (lower) -> {series, title, speaker, passage}."""
    out: dict[str, dict] = {}
    for fx in sorted(FEEDS.glob("*.xml")):
        series = FEED_SERIES.get(fx.name)
        x = fx.read_text(encoding="utf-8", errors="replace")
        for it in re.findall(r"<item>(.*?)</item>", x, re.S):
            tm = re.search(r"<title>(.*?)</title>", it, re.S)
            em = re.search(r'<enclosure[^>]*url="([^"]+\.mp3)"', it, re.I)
            if not em:
                continue
            base = urllib.parse.unquote(em.group(1).rsplit("/", 1)[-1]).lower()
            title = html.unescape(re.sub(r"<[^>]+>", "", tm.group(1)).strip()) if tm else ""
            speaker = None
            m = re.match(r"^([A-Z][\w.'’ ]+?):\s*(.+)$", title)  # "Speaker: rest"
            if m:
                speaker, title = m.group(1).strip(), m.group(2).strip()
            refs = scripture.parse_refs(title)
            passage = scripture.format_ref(refs[0]) if refs else None
            out[base] = {"series": series, "title": title, "speaker": speaker, "passage": passage}
    return out


def cbcoh_meta(stem: str):
    """category + speaker from a cbcoh filename ('DATE - Type - Title - Speaker (..)')."""
    parts = [p.strip() for p in stem.split(" - ")]
    if len(parts) >= 3 and re.match(r"\d{4}-\d{2}-\d{2}$", parts[0]):
        typ = parts[1]
        spk = re.sub(r"\s*\(.*$|_\d+kbps.*$", "", parts[-1]).strip() if len(parts) >= 4 else None
        cat = "conference" if "conference" in typ.lower() else ("class" if ("class" in typ.lower() or "study" in typ.lower()) else "sermon")
        return cat, (spk or None), parts[0]
    return "sermon", None, None


def detect_primary(text: str, prefer_book: str | None = None) -> dict | None:
    refs = scripture.parse_refs(text or "", unique=False)
    if prefer_book:
        refs = [r for r in refs if r["book"] == prefer_book] or refs
    if not refs:
        return None
    counts: Counter = Counter()
    first: dict = {}
    for i, r in enumerate(refs):
        k = (r["book"], r["chapter"])
        counts[k] += 1
        first.setdefault(k, i)
    book, chapter = max(counts, key=lambda k: (counts[k], -first[k]))
    if counts[(book, chapter)] < 2:
        return None
    return {"book": book, "chapter": chapter, "ref_text": f"{book} {chapter}"}


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    feeds = load_feeds()
    rows = []
    used_slugs: set[str] = set()
    seen_identity: dict = {}   # (norm title, year) -> {slug, path}
    seen_recordings: dict[str, list[tuple[float, str]]] = {}  # date -> [(duration_sec, path)]
    dropped: list[dict] = []   # duplicate files not imported
    excluded: list[dict] = []  # non-Michael items excluded from the site
    audio_exts = {".mp3", ".m4a", ".wav", ".flac"}
    skipped_dup = 0

    for folder, category, recursive, kind in TARGETS:
        if not folder.exists():
            continue
        walk = folder.rglob("*") if recursive else folder.iterdir()
        for f in sorted(walk):
            if not f.is_file() or f.suffix.lower() not in audio_exts:
                continue
            stem = f.stem
            tags = read_tags(f)
            feed = feeds.get(f.name.lower())

            # category + cbcoh speaker
            cat = category
            cb_speaker = cb_date = None
            if kind == "cbcoh":
                cat, cb_speaker, cb_date = cbcoh_meta(stem)

            # title (html.unescape fixes feed entities like "David &amp; Bathsheba")
            title = html.unescape((feed and feed["title"]) or tags.get("title") or split_camel(stem))
            # speaker: feed (per-episode, e.g. 1 John) > cbcoh filename > ID3 artist > default
            artist = tags.get("artist", "")
            artist_ok = artist and artist.lower() not in GENERIC_ALBUMS and not BAD_ARTIST.search(artist)
            speaker = (feed and feed["speaker"]) or cb_speaker or (artist if artist_ok else None) or DEFAULT_SPEAKER
            # collection: feed series > non-generic ID3 album
            album = tags.get("album", "")
            collection = (feed and feed["series"]) or (album if album.lower() not in GENERIC_ALBUMS else None)
            # date: filename > cbcoh date (both PRECISE day) > ID3 year (NOT precise)
            date = None
            mfn = re.search(r"(\d{8})", stem)
            if mfn:
                date = iso_from_yyyymmdd(mfn.group(1))
            date = date or cb_date
            date_precise = date is not None   # a real day, not a YYYY-01-01 guess
            if not date and tags.get("date", "")[-4:].isdigit():
                date = f"{tags['date'][-4:]}-01-01"
            duration = tags.get("__dur__")    # seconds (float) or None

            transcript = (f.with_suffix(".txt").read_text(encoding="utf-8")
                          if f.with_suffix(".txt").exists() else None)
            r2_key = None  # set after dedupe + redaction decision below

            # passage: feed > scripture ref in title > book-constrained transcript > heuristic
            passage_ref = None
            primary = None
            if feed and feed["passage"]:
                passage_ref = feed["passage"]
                pr = scripture.parse_refs(passage_ref)
                primary = {**pr[0], "ref_text": passage_ref} if pr else None
            if not primary:
                tr = scripture.parse_refs(title)
                if tr:
                    primary = {**tr[0], "ref_text": scripture.format_ref(tr[0])}
                    passage_ref = primary["ref_text"]
            if not primary and transcript:
                primary = detect_primary(transcript, prefer_book=book_of(collection))
                passage_ref = primary["ref_text"] if primary else None

            # per-file metadata overrides (tools/overrides.py)
            ov = OVERRIDES.get(stem)
            if ov and ov.get("drop"):
                # explicit drop (e.g. an unrelated-name duplicate the auto-dedupe
                # can't catch). Record it so its source shows up in delete_dupes.bat.
                dropped.append({"dropped": str(f), "kept_path": "(dropped via overrides.py)", "title": title})
                skipped_dup += 1
                continue
            if ov:
                title = ov.get("title", title)
                date = ov.get("recorded_on", date)
                speaker = ov.get("speaker", speaker)
                collection = ov.get("collection", collection)
                cat = ov.get("category", cat)
                for find, repl in ov.get("replace_text", []):
                    if transcript:
                        transcript = transcript.replace(find, repl)
                if "passage" in ov:
                    pr = scripture.parse_refs(ov["passage"])
                    primary = ({**pr[0], "ref_text": ov["passage"]} if pr
                               else {"book": ov["passage"], "chapter": None, "ref_text": ov["passage"]})
                    passage_ref = ov["passage"]
            if collection:
                collection = COLLECTION_NORMALIZE.get(collection, collection)
            # Michael's site only: exclude items he didn't speak (reversible — just not in the catalog)
            if MICHAEL_ONLY and "michael coughlin" not in (speaker or "").lower():
                excluded.append({"path": str(f), "speaker": speaker, "title": title})
                continue

            # DEDUPE on (normalized title, year)
            identity = (norm(title), (date or "")[:4])
            if identity[0] and identity in seen_identity:
                kept = seen_identity[identity]
                dropped.append({"dropped": str(f), "kept_path": kept["path"], "title": title})
                skipped_dup += 1
                continue
            slug = slugify((date + "-" if date else "") + title)
            n = 1
            while slug in used_slugs:
                n += 1
                slug = f"{slugify((date + '-' if date else '') + title)}-{n}"
            used_slugs.add(slug)
            if identity[0]:
                seen_identity[identity] = {"slug": slug, "path": str(f)}

            # apply redactions by slug
            red = REDACTIONS.get(slug)
            if red:
                for t in red.get("remove_text", []):
                    if transcript:
                        transcript = transcript.replace(t, "")
                if not red.get("drop_audio"):
                    r2_key = f"audio/{cat}/{slug}.mp3"
            else:
                r2_key = f"audio/{cat}/{slug}.mp3"

            rows.append({
                "slug": slug, "title": title, "category": cat, "speaker": speaker,
                "collection": collection, "recorded_on": date, "passage_ref": passage_ref,
                "primary": primary, "r2_key": r2_key, "source_path": str(f),
                "transcript": transcript,
            })

    # ---- build SQL ----
    speakers = sorted({r["speaker"] for r in rows if r["speaker"]})
    coll_map: dict[str, str] = {}   # title -> category (one row per series; slug is unique)
    for r in rows:
        if r["collection"]:
            coll_map.setdefault(r["collection"], r["category"])
    collections = sorted(coll_map.items())
    # NOTE: no PRAGMA / BEGIN TRANSACTION / COMMIT — D1's HTTP API (`wrangler d1
    # execute --remote`) rejects explicit transactions, and we want a single file
    # that applies cleanly both --local and --remote so deploys are just correct.
    # The leading DELETEs keep the reseed idempotent.
    lines = ["DELETE FROM scripture_refs;", "DELETE FROM item_transcripts;",
             "DELETE FROM item_fts;", "DELETE FROM items;",
             "DELETE FROM collections;", "DELETE FROM speakers;", "", "-- speakers"]
    for s in speakers:
        lines.append(f"INSERT INTO speakers (name, slug, is_primary) VALUES ({q(s)}, {q(slugify(s))}, {1 if s == DEFAULT_SPEAKER else 0});")
    lines += ["", "-- collections"]
    for title, cat in collections:
        lines.append(f"INSERT INTO collections (slug, title, category) VALUES ({q(slugify(title))}, {q(title)}, {q(cat)});")
    lines += ["", "-- items"]
    for r in rows:
        coll = f"(SELECT id FROM collections WHERE slug={q(slugify(r['collection']))})" if r["collection"] else "NULL"
        spk = f"(SELECT id FROM speakers WHERE name={q(r['speaker'])})" if r["speaker"] else "NULL"
        tstatus = "done" if r["transcript"] else "none"
        lines.append(
            f"INSERT INTO items (slug, title, category, speaker_id, collection_id, recorded_on, passage_ref, r2_key, source_path, transcript_status) "
            f"VALUES ({q(r['slug'])}, {q(r['title'])}, {q(r['category'])}, {spk}, {coll}, {q(r['recorded_on'])}, {q(r['passage_ref'])}, {q(r['r2_key'])}, {q(r['source_path'])}, {q(tstatus)});")
    lines += ["", "-- transcripts + scripture refs"]
    for r in rows:
        sid = f"(SELECT id FROM items WHERE slug={q(r['slug'])})"
        if r["primary"]:
            p = r["primary"]
            lines.append(f"INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
                         f"VALUES ({sid}, {q(p['book'])}, {q(p['chapter'])}, {q(p.get('verse_start'))}, {q(p.get('verse_end'))}, 1, {q(p['ref_text'])}, 'primary');")
        if r["transcript"]:
            lines.append(f"INSERT INTO item_transcripts (item_id, text, model) VALUES ({sid}, {q(r['transcript'])}, 'groq large-v3');")
            for ref in scripture.parse_refs(r["transcript"]):
                lines.append(f"INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
                             f"VALUES ({sid}, {q(ref['book'])}, {q(ref['chapter'])}, {q(ref['verse_start'])}, {q(ref['verse_end'])}, 0, {q(ref['ref_text'])}, 'transcript');")
    lines += ["", "INSERT INTO item_fts (item_id, title, speaker, passage_ref, transcript) "
              "SELECT i.id, i.title, COALESCE(sp.name,''), COALESCE(i.passage_ref,''), COALESCE(t.text,'') "
              "FROM items i LEFT JOIN speakers sp ON sp.id=i.speaker_id LEFT JOIN item_transcripts t ON t.item_id=i.id;"]

    IMPORT_SQL.parent.mkdir(parents=True, exist_ok=True)
    IMPORT_SQL.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- dedupe artifacts for review (delete script is NOT run automatically) ----
    tools = Path(__file__).resolve().parent
    rep = [f"{len(dropped)} duplicate recordings were NOT imported.",
           "Each DROP is the same recording as the KEEP we kept (prefers the clean cbcoh copy).",
           "Review, then run tools/delete_dupes.bat to delete the DROP .mp3 + .txt.", ""]
    dl = ["@echo off",
          "REM Deletes duplicate source audio (.mp3) + transcript (.txt) NOT used by the site.",
          "REM Review tools/deduped_report.txt first. Nothing here ran automatically.", ""]
    for d in sorted(dropped, key=lambda x: x["dropped"]):
        rep += [f"KEEP: {d['kept_path']}", f"DROP: {d['dropped']}", ""]
        dp = Path(d["dropped"])
        dl.append(f'del /f /q "{dp}"')
        dl.append(f'del /f /q "{dp.with_suffix(".txt")}"')
    dl += ["", f"echo Deleted {len(dropped)} duplicate mp3 + txt pairs."]
    (tools / "deduped_report.txt").write_text("\n".join(rep), encoding="utf-8")
    (tools / "delete_dupes.bat").write_text("\r\n".join(dl) + "\r\n", encoding="utf-8")

    # non-Michael exclusions (removed from the site; source files only deleted on approval)
    nm = [f"{len(excluded)} items excluded from the site (speaker is not Michael Coughlin):", ""]
    nd = ["@echo off", "REM Delete source files of non-Michael items. Review first; not auto-run.", ""]
    for e in sorted(excluded, key=lambda x: x["path"]):
        nm.append(f"{e['speaker']:24} | {e['title']}")
        nm.append(f"    {e['path']}")
        p = Path(e["path"])
        nd.append(f'del /f /q "{p}"')
        nd.append(f'del /f /q "{p.with_suffix(".txt")}"')
    (tools / "nonmichael_report.txt").write_text("\n".join(nm), encoding="utf-8")
    (tools / "delete_nonmichael.bat").write_text("\r\n".join(nd) + "\r\n", encoding="utf-8")

    n_tx = sum(1 for r in rows if r["transcript"])
    n_pass = sum(1 for r in rows if r["passage_ref"])
    print(f"import.sql: {len(rows)} items (deduped {skipped_dup}), {len(speakers)} speakers, "
          f"{len(collections)} collections, {n_tx} transcripts, {n_pass} with passage")
    print(f"  dedupe review -> tools/deduped_report.txt ; delete script (NOT run) -> tools/delete_dupes.bat")

    if "--apply" in sys.argv:
        print("applying to LOCAL d1 (binding DB) ...")
        subprocess.run(["npx", "wrangler", "d1", "execute", "DB", "--local", f"--file={IMPORT_SQL}", "--yes"],
                       cwd=REPO, check=True, shell=(sys.platform == "win32"))


if __name__ == "__main__":
    main()
