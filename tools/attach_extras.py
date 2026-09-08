"""Attach a video link and/or downloadable files to an existing catalog item.

The companion to attach_transcript.py: that one indexes the spoken word, this
one hangs the extras off a message that is already live — a YouTube/Rumble link
to video of the same teaching, and files people can download (teacher outline,
student handout, slides).

Usage:
  # look at what an item already has
  python tools/attach_extras.py --slug 2026-08-30-evangelism-training-seminar --list --remote

  # a video link (no upload, pure SQL)
  python tools/attach_extras.py --slug SLUG --video "https://youtu.be/abc123" --remote

  # attach files (uploads to R2, then inserts the rows)
  python tools/attach_extras.py --slug SLUG --remote \
      --notes "C:/code/macaudio/.videos/theGospel-TEACHER.docx:Teacher outline" \
      --notes "C:/code/macaudio/.videos/theGospel-STUDENT.docx:Student handout"

  # corrections
  python tools/attach_extras.py --slug SLUG --video "" --remote        # clear the link
  python tools/attach_extras.py --slug SLUG --remove-file 3 --remote   # id from --list

Flags:
  --slug SLUG        the item to touch (required)
  --video URL        set items.video_url; pass "" to clear it
  --notes PATH[:T]   file to attach, optional ":Title" for the button label.
                     Repeatable. Re-attaching the same filename REPLACES it.
  --kind K           notes | handout | slides | outline   (default: notes)
  --remove-file ID   delete one attachment (row + R2 object)
  --list             show current extras and exit
  --remote           act on production D1 + R2 (default: local dev)
  --dry-run          print the R2 commands and SQL; change nothing

Credentials come from .dev.vars (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID),
the same file every other tool here reads.

R2 key convention:  files/<slug>/<filename>
Deliberately no category segment — audio keys embed the category, which is why
re-categorizing an item silently 404s its audio. Attachment keys depend only on
the slug, which doesn't change.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import load_dev_vars  # noqa: E402

WIN = sys.platform == "win32"
BUCKET = "macaudio"
DB = "macaudio"
KINDS = {"notes", "handout", "slides", "outline"}

# Attachments get a SHORT cache, unlike audio's immutable year. Outlines get
# corrected and re-uploaded under the same key; a year-long immutable cache
# would hide the fix from anyone who already downloaded the page.
CACHE = "public, max-age=86400"

CT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".epub": "application/epub+zip",
    ".zip": "application/zip",
}


# ---- helpers ---------------------------------------------------------------

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


def d1(command: str | None, remote: bool, file: Path | None = None) -> list | None:
    mode = "--remote" if remote else "--local"
    args = ["npx", "wrangler", "d1", "execute", DB, mode, "--json"]
    args += [f"--file={file}"] if file else ["--command", command]
    out = subprocess.run(
        args, cwd=REPO, shell=WIN, env=cf_env(),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit("d1 command failed:\n" + (out.stderr or out.stdout or ""))
    return json.loads(out.stdout[out.stdout.index("["):])


def rows(command: str, remote: bool) -> list[dict]:
    return (d1(command, remote) or [{}])[0].get("results", [])


def safe_name(name: str) -> str:
    """Filesystem name -> R2-safe filename. Keeps the extension and the stem's
    shape (so 'theGospel-TEACHER.docx' stays recognizable in the URL)."""
    stem, dot, ext = name.rpartition(".")
    stem = stem or name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.") or "file"
    return f"{stem}.{ext.lower()}" if dot else stem


def default_title(path: Path) -> str:
    """Button label derived from the filename when none is given.
    theGospel-TEACHER.docx -> 'Teacher outline';  handout-2.pdf -> 'Handout 2'."""
    stem = path.stem
    upper = stem.upper()
    for tag, label in (("TEACHER", "Teacher outline"), ("STUDENT", "Student handout"),
                       ("SLIDES", "Slides"), ("OUTLINE", "Outline"), ("HANDOUT", "Handout")):
        if tag in upper:
            return label
    words = re.sub(r"[_-]+", " ", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)).split()
    return " ".join(words).strip().capitalize() or "Download"


def parse_notes_arg(raw: str) -> tuple[Path, str | None]:
    """'C:/path/file.docx:Teacher outline' -> (Path, 'Teacher outline').
    Splits on the LAST colon, and never on a Windows drive colon ('C:')."""
    head, sep, tail = raw.rpartition(":")
    if sep and len(head) > 1 and not re.fullmatch(r"[A-Za-z]", head[-1] if len(head) == 1 else ""):
        # a real title only if the head still looks like a path (has a separator
        # or an extension) and the tail isn't a drive-letter remnant
        if ("/" in head or "\\" in head or "." in Path(head).name) and tail and not tail[0].isdigit():
            return Path(head.strip('"')), tail.strip()
    return Path(raw.strip('"')), None


def valid_video_url(url: str) -> str:
    """Only http(s) survives. An unvalidated href goes straight into the page as
    a link — 'javascript:...' would be an XSS hole on a site we paste into by hand."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        sys.exit(f"Refusing that video link - must be an http(s) URL: {url!r}")
    return url


def r2_put(key: str, src: Path, remote: bool, dry: bool) -> None:
    cmd = ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}",
           "--file", str(src), "--content-type", CT.get(src.suffix.lower(), "application/octet-stream"),
           "--cache-control", CACHE] + (["--remote"] if remote else [])
    if dry:
        print("  would upload:  " + " ".join(cmd))
        return
    out = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit(f"R2 upload failed for {key}:\n" + (out.stderr or out.stdout))
    print(f"  uploaded  {key}  ({src.stat().st_size:,} bytes)")


def r2_delete(key: str, remote: bool, dry: bool) -> None:
    cmd = ["npx", "wrangler", "r2", "object", "delete", f"{BUCKET}/{key}"] + (["--remote"] if remote else [])
    if dry:
        print("  would delete:  " + " ".join(cmd))
        return
    out = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        # The DB row is the source of truth for the site; a stranded object is
        # cheap. Warn, don't abort.
        print(f"  WARNING: R2 delete failed for {key} (row still removed):\n"
              + (out.stderr or out.stdout).strip()[:200])
    else:
        print(f"  deleted   {key}")


def show(item: dict, remote: bool) -> None:
    print(f"\n  {item['slug']}  (id {item['id']})")
    print(f"  video   {item.get('video_url') or '(none)'}")
    files = rows(f"SELECT id, kind, title, r2_key, size_bytes FROM item_files "
                 f"WHERE item_id={item['id']} ORDER BY sort, id", remote)
    if not files:
        print("  files   (none)")
    for f in files:
        size = f"{f['size_bytes']:,}b" if f.get("size_bytes") else "?"
        # ASCII only: the Windows console is cp1252 and turns an em-dash to mojibake.
        print(f"  file {f['id']:>4}  [{f['kind']}] {f['title']}  ->  {f['r2_key']}  ({size})")
    print()


# ---- main ------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Attach a video link and/or files to an existing item.")
    p.add_argument("--slug", required=True)
    p.add_argument("--video", default=None, help='URL, or "" to clear')
    p.add_argument("--notes", action="append", default=[], metavar="PATH[:Title]")
    p.add_argument("--kind", default="notes", choices=sorted(KINDS))
    p.add_argument("--remove-file", type=int, default=None, metavar="ID")
    p.add_argument("--list", action="store_true", help="show current extras and exit")
    p.add_argument("--remote", action="store_true", help="production D1 + R2 (default: local)")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    remote, dry = a.remote, a.dry_run

    found = rows(f"SELECT id, slug, video_url FROM items WHERE slug={q(a.slug)}", remote)
    if not found:
        sys.exit(f"No item with slug {a.slug} in {'remote' if remote else 'local'} D1.")
    item = found[0]
    item_id = item["id"]

    if a.list:
        show(item, remote)
        return
    if a.video is None and not a.notes and a.remove_file is None:
        sys.exit("Nothing to do — pass --video, --notes, --remove-file, or --list.")

    sql: list[str] = []

    # --- video link ---------------------------------------------------------
    if a.video is not None:
        if a.video.strip() == "":
            sql.append(f"UPDATE items SET video_url=NULL WHERE id={item_id};")
            print("  video   -> cleared")
        else:
            url = valid_video_url(a.video.strip())
            sql.append(f"UPDATE items SET video_url={q(url)} WHERE id={item_id};")
            print(f"  video   -> {url}")

    # --- remove an attachment ----------------------------------------------
    if a.remove_file is not None:
        gone = rows(f"SELECT id, r2_key, title FROM item_files "
                    f"WHERE id={a.remove_file} AND item_id={item_id}", remote)
        if not gone:
            sys.exit(f"No attachment id {a.remove_file} on {a.slug} "
                     f"(run with --list to see the ids).")
        r2_delete(gone[0]["r2_key"], remote, dry)
        sql.append(f"DELETE FROM item_files WHERE id={a.remove_file} AND item_id={item_id};")
        print(f"  removed -> {gone[0]['title']}")

    # --- attachments --------------------------------------------------------
    if a.notes:
        nxt = rows(f"SELECT COALESCE(MAX(sort), 0) AS m FROM item_files WHERE item_id={item_id}", remote)
        sort = (nxt[0]["m"] if nxt else 0) + 1
        for raw in a.notes:
            src, title = parse_notes_arg(raw)
            if not src.exists():
                sys.exit(f"File not found: {src}")
            title = title or default_title(src)
            key = f"files/{a.slug}/{safe_name(src.name)}"
            mime = CT.get(src.suffix.lower(), "application/octet-stream")
            size = src.stat().st_size
            r2_put(key, src, remote, dry)
            # r2_key is UNIQUE: re-attaching the same filename REPLACES the row
            # rather than duplicating it, which makes a corrected outline a
            # one-command fix.
            sql.append(
                "INSERT INTO item_files (item_id, kind, title, r2_key, mime, size_bytes, sort) VALUES ("
                f"{item_id}, {q(a.kind)}, {q(title)}, {q(key)}, {q(mime)}, {q(size)}, {q(sort)}) "
                "ON CONFLICT(r2_key) DO UPDATE SET "
                f"item_id=excluded.item_id, kind=excluded.kind, title=excluded.title, "
                f"mime=excluded.mime, size_bytes=excluded.size_bytes;")
            print(f"  file    -> [{a.kind}] {title}")
            sort += 1

    sql_text = "\n".join(sql) + "\n"
    if dry:
        print("\n--- DRY RUN: would execute SQL ---\n" + sql_text)
        return

    sql_file = HERE / f"_extras_{a.slug}.sql"
    sql_file.write_text(sql_text, encoding="utf-8")
    try:
        d1(None, remote, file=sql_file)
    finally:
        sql_file.unlink(missing_ok=True)

    after = rows(f"SELECT id, slug, video_url FROM items WHERE id={item_id}", remote)[0]
    show(after, remote)
    base = "https://teaching.michaelcoughlin.net" if remote else "http://localhost:4321"
    print(f"Done -> {base}/listen/{a.slug}")


if __name__ == "__main__":
    main()
