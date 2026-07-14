"""Add ONE sermon to the live catalog — the easy path for a weekly upload.

Unlike import_catalog.py (which rebuilds the WHOLE catalog from a folder/feed
scan and starts with DELETE FROM items), this adds a single recording without
touching anything else. Run it after you teach:

    python tools/add_sermon.py

It asks for the audio file + a few facts, then in one shot:
  1. reads the duration (ffprobe),
  2. makes a unique slug,
  3. uploads the audio to R2 (bucket `macaudio`, key audio/<cat>/<slug>.<ext>),
  4. inserts the item — creating the series/collection + speaker if new — and a
     title-only search row, so it's LIVE and title-searchable immediately, then
  5. transcribes it (Groq Whisper), extracts scripture refs, and rebuilds its
     full-text search row  (delegated to attach_transcript.py).

Credentials come from this repo's .dev.vars (CLOUDFLARE_API_TOKEN,
CLOUDFLARE_ACCOUNT_ID, GROQ_API_KEY) — same file the other tools use.

Flags (all optional; anything not passed is prompted for):
  --audio PATH  --title T  --series S  --part P  --date YYYY-MM-DD
  --passage REF  --category sermon|class|conference|open_air|podcast
  --speaker NAME  --no-transcript   audio + item only, index transcript later
  --local          write to the LOCAL dev D1 instead of production
  --dry-run        show the slug, R2 command, and SQL; write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import scripture  # noqa: E402
from transcribe_groq import (  # noqa: E402
    build_prompt, load_dev_vars, split_chunks, transcribe_chunk,
)
from textfmt import paragraphize  # noqa: E402

WIN = sys.platform == "win32"
BUCKET = "macaudio"
DB = "macaudio"
DEFAULT_SPEAKER = "Michael Coughlin"
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac"}
CATEGORIES = {"sermon", "class", "conference", "open_air", "podcast"}
CT = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".flac": "audio/flac"}
CACHE = "public, max-age=31536000, immutable"


# ---- helpers ---------------------------------------------------------------

def slugify(s: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "item"


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def cf_env() -> dict:
    """os.environ + Cloudflare creds from .dev.vars, so wrangler works headless."""
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def d1(command: str | None, remote: bool, file: Path | None = None, capture=True) -> dict | None:
    mode = "--remote" if remote else "--local"
    args = ["npx", "wrangler", "d1", "execute", DB, mode, "--json"]
    args += [f"--file={file}"] if file else ["--command", command]
    out = subprocess.run(
        args, cwd=REPO, shell=WIN, env=cf_env(),
        capture_output=capture, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit("d1 command failed:\n" + (out.stderr or out.stdout or ""))
    if not capture:
        return None
    return json.loads(out.stdout[out.stdout.index("["):])


def probe_duration(p: Path) -> int | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        return int(float(out)) if out else None
    except Exception:
        return None


def unique_slug(base: str, remote: bool, dry: bool) -> str:
    if dry:
        return base
    taken = {r["slug"] for r in
             (d1(f"SELECT slug FROM items WHERE slug LIKE {q(base + '%')}", remote) or [{}])[0].get("results", [])}
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


def ask(prompt: str, default: str | None = None, required: bool = False) -> str | None:
    label = f"{prompt} [{default}]: " if default else f"{prompt}: "
    while True:
        val = input(label).strip()
        if not val:
            val = default
        if val or not required:
            return val or None
        print("  (required)")


# ---- transcription (single file) -------------------------------------------

def transcribe_file(src: Path) -> Path:
    """Transcribe one audio file to <src>.txt (cached; reused by attach_transcript)."""
    txt = src.with_suffix(".txt")
    if txt.exists():
        print(f"  transcript already exists: {txt.name}")
        return txt
    key = load_dev_vars().get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
    if not key:
        sys.exit("Missing GROQ_API_KEY (set it in .dev.vars) — or rerun with --no-transcript.")
    prompt = build_prompt()
    print("  transcribing via Groq Whisper (a few minutes for a full sermon) ...")
    with tempfile.TemporaryDirectory() as tmp:
        chunks = split_chunks(src, Path(tmp), 1500)
        parts = [transcribe_chunk(c, "whisper-large-v3", key, prompt) for c in chunks]
    txt.write_text(paragraphize("\n\n".join(parts)), encoding="utf-8")
    print(f"  -> {txt.name} ({len(' '.join(parts).split())} words)")
    return txt


# ---- main ------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Add one sermon to the catalog.")
    p.add_argument("--audio")
    p.add_argument("--title")
    p.add_argument("--series")
    p.add_argument("--part")
    p.add_argument("--date")
    p.add_argument("--passage")
    p.add_argument("--category")
    p.add_argument("--speaker")
    p.add_argument("--no-transcript", action="store_true")
    p.add_argument("--local", action="store_true", help="write to local dev D1, not production")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    remote = not a.local
    dry = a.dry_run

    # --- collect metadata (prompt for anything not passed) ---
    audio = a.audio or ask("Audio file", required=True)
    src = Path(audio.strip('"'))
    if not dry and (not src.exists() or src.suffix.lower() not in AUDIO_EXTS):
        sys.exit(f"Not an audio file that exists: {src}")

    title = a.title or ask("Title", required=True)
    series = a.series if a.series is not None else ask("Series (blank for none)")
    part = a.part if a.part is not None else ask("Part label (e.g. 'Part 1', blank for none)")
    recorded = a.date or ask("Date", default=date.today().isoformat())
    passage = a.passage if a.passage is not None else ask("Passage (blank = detect from transcript)")
    category = (a.category or ask("Category", default="sermon")) or "sermon"
    if category not in CATEGORIES:
        sys.exit(f"category must be one of {sorted(CATEGORIES)}")
    speaker = a.speaker or ask("Speaker", default=DEFAULT_SPEAKER)

    ext = src.suffix.lower()
    duration = probe_duration(src) if src.exists() else None
    base = slugify(f"{recorded}-{title}" if recorded else title)
    slug = unique_slug(base, remote, dry)
    r2_key = f"audio/{category}/{slug}{ext}"
    coll_slug = slugify(series) if series else None

    print(f"\n  slug       {slug}")
    print(f"  r2_key     {r2_key}")
    print(f"  duration   {duration if duration is not None else '?'} sec")
    print(f"  series     {series or '(none)'}   part {part or '(none)'}")
    print(f"  target     {'PRODUCTION (remote)' if remote else 'local dev'} D1 + R2\n")

    # --- build the insert SQL ---
    sql = []
    if speaker:
        sql.append(f"INSERT OR IGNORE INTO speakers (name, slug, is_primary) "
                   f"VALUES ({q(speaker)}, {q(slugify(speaker))}, {1 if speaker == DEFAULT_SPEAKER else 0});")
    if coll_slug:
        sql.append(f"INSERT OR IGNORE INTO collections (slug, title, category) "
                   f"VALUES ({q(coll_slug)}, {q(series)}, {q(category)});")
    coll_expr = f"(SELECT id FROM collections WHERE slug={q(coll_slug)})" if coll_slug else "NULL"
    spk_expr = f"(SELECT id FROM speakers WHERE name={q(speaker)})" if speaker else "NULL"
    # The item's search row is created automatically by the 0003_fts_sync
    # trigger on this INSERT (title + speaker + passage; transcript filled in by
    # the attach step below). Do not INSERT into item_fts here — it would double.
    sql.append(
        "INSERT INTO items (slug, title, category, speaker_id, collection_id, recorded_on, "
        "passage_ref, r2_key, duration_sec, source_path, transcript_status, series_part) VALUES ("
        f"{q(slug)}, {q(title)}, {q(category)}, {spk_expr}, {coll_expr}, {q(recorded)}, "
        f"{q(passage)}, {q(r2_key)}, {q(duration)}, {q(str(src))}, 'none', {q(part)});")
    sql_text = "\n".join(sql) + "\n"

    r2_cmd = ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{r2_key}",
              "--file", str(src), "--content-type", CT.get(ext, "application/octet-stream"),
              "--cache-control", CACHE] + (["--remote"] if remote else [])

    if dry:
        print("--- DRY RUN: would upload ---\n  " + " ".join(r2_cmd))
        print("\n--- DRY RUN: would execute SQL ---\n" + sql_text)
        print(f"--- then {'transcribe + index' if not a.no_transcript else 'skip transcript'} ---")
        return

    # --- 1) upload audio to R2 ---
    print("uploading audio to R2 ...")
    up = subprocess.run(r2_cmd, cwd=REPO, shell=WIN, env=cf_env(),
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if up.returncode != 0:
        sys.exit("R2 upload failed:\n" + (up.stderr or up.stdout))
    print("  uploaded.")

    # --- 2) insert item (+ collection/speaker + title search row) ---
    print(f"inserting item into {'remote' if remote else 'local'} D1 ...")
    sql_file = HERE / f"_add_{slug}.sql"
    sql_file.write_text(sql_text, encoding="utf-8")
    d1(None, remote, file=sql_file, capture=False)
    sql_file.unlink(missing_ok=True)
    print("  item is live.")

    # --- 3) transcribe + index (delegated to attach_transcript.py) ---
    if not a.no_transcript:
        transcribe_file(src)
        cmd = [sys.executable, str(HERE / "attach_transcript.py"), "--slug", slug]
        if passage:
            cmd += ["--passage", passage]
        if remote:
            cmd += ["--remote"]
        print("attaching transcript + scripture refs + search index ...")
        if subprocess.run(cmd, cwd=REPO, env=cf_env()).returncode != 0:
            print("  transcript step failed — item is still live; "
                  f"rerun later:  python tools/attach_transcript.py --slug {slug}"
                  + (" --remote" if remote else ""))

    base_url = "https://teaching.michaelcoughlin.net" if remote else "http://localhost:4321"
    print(f"\nDone. {base_url}/listen/{slug}")


if __name__ == "__main__":
    main()
