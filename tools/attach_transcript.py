"""Attach a transcript (+ scripture refs) to an existing catalog item.

Reads the item's transcript .txt (same stem as its source_path, or --txt),
scans it for scripture refs, sets the primary passage (first ref found,
or --passage to override), and updates item_transcripts / scripture_refs /
item_fts / items.transcript_status for that one item — both --local and,
once Cloudflare auth is sorted, --remote.

Usage:
  python tools/attach_transcript.py --slug 2026-07-13-armor-of-god-part-1
  python tools/attach_transcript.py --slug ... --passage "Ephesians 6" --remote
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def d1(args_list: list[str], remote: bool) -> dict:
    mode = "--remote" if remote else "--local"
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, "--json", *args_list],
        cwd=REPO, capture_output=True, text=True, shell=WIN, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit(f"d1 command failed:\n{out.stderr}")
    txt = out.stdout[out.stdout.index("["):]
    return json.loads(txt)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--txt", default=None, help="transcript path (default: source_path with .txt)")
    p.add_argument("--passage", default=None, help="override the detected primary passage")
    p.add_argument("--remote", action="store_true", help="apply to remote D1 (default: local)")
    args = p.parse_args()
    remote = args.remote

    rows = d1(["--command", f"SELECT id, source_path FROM items WHERE slug={q(args.slug)}"], remote)
    results = rows[0]["results"]
    if not results:
        sys.exit(f"No item with slug {args.slug}")
    item_id, source_path = results[0]["id"], results[0]["source_path"]

    txt_path = Path(args.txt) if args.txt else Path(source_path).with_suffix(".txt")
    if not txt_path.exists():
        sys.exit(f"Transcript not found: {txt_path}")
    text = txt_path.read_text(encoding="utf-8")

    refs = scripture.parse_refs(text)
    if args.passage:
        pr = scripture.parse_refs(args.passage)
        primary = {**pr[0], "ref_text": args.passage} if pr else {"book": args.passage, "chapter": None, "ref_text": args.passage}
    else:
        primary = refs[0] if refs else None

    # item_fts is maintained by the 0003_fts_sync triggers: the item_transcripts
    # INSERT below fills its transcript column, and the items UPDATE rebuilds the
    # row. Nothing here writes item_fts directly.
    lines = [
        f"DELETE FROM item_transcripts WHERE item_id={item_id};",
        f"DELETE FROM scripture_refs WHERE item_id={item_id};",
        f"INSERT INTO item_transcripts (item_id, text, model) VALUES ({item_id}, {q(text)}, 'groq whisper-large-v3');",
        f"UPDATE items SET transcript_status='done'"
        + (f", passage_ref={q(primary['ref_text'])}" if primary else "")
        + f" WHERE id={item_id};",
    ]
    if primary:
        lines.append(
            f"INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
            f"VALUES ({item_id}, {q(primary['book'])}, {q(primary.get('chapter'))}, {q(primary.get('verse_start'))}, "
            f"{q(primary.get('verse_end'))}, 1, {q(primary['ref_text'])}, 'primary');"
        )
    for r in refs:
        lines.append(
            f"INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
            f"VALUES ({item_id}, {q(r['book'])}, {q(r['chapter'])}, {q(r['verse_start'])}, {q(r['verse_end'])}, 0, {q(r['ref_text'])}, 'transcript');"
        )

    sql_path = REPO / "tools" / f"_attach_{args.slug}.sql"
    sql_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mode = "--remote" if remote else "--local"
    res = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, f"--file={sql_path}"],
        cwd=REPO, shell=WIN,
    )
    sql_path.unlink(missing_ok=True)
    if res.returncode != 0:
        sys.exit("apply failed")
    print(f"Attached transcript ({len(text.split())} words), {len(refs)} scripture refs, "
          f"primary passage {primary['ref_text'] if primary else '(none)'} -> {mode[2:]} D1.")


if __name__ == "__main__":
    main()
