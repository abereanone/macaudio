"""Correct the primary passage of one or more items.

The auto-detector in attach_transcript.py sets an item's primary passage to the
FIRST scripture reference found in its transcript. When a sermon opens with a
call-to-worship or illustration verse before reaching its real text, that first
ref is wrong. This tool fixes a known-bad primary passage by hand:

  - updates items.passage_ref (which rebuilds the item's item_fts row via the
    0003_fts_sync trigger), and
  - replaces the is_primary=1 / source='primary' row in scripture_refs with the
    corrected book/chapter/verses.

Transcript-mined refs (source='transcript') are left untouched.

Usage:
  # fix the two 2 Peter 1 virtue sermons (default set below):
  python tools/fix_passage.py --remote
  # or target any slug with any ref:
  python tools/fix_passage.py --remote --slug 2021-11-13-steadfastness --passage "2 Peter 1:5-7"
  python tools/fix_passage.py --remote --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402
from transcribe_groq import load_dev_vars  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"

# slug -> corrected primary passage. Both sermons expound the virtue chain of
# 2 Peter 1:5-7; the detector had mis-grabbed Galatians 5 / Matthew 5.
DEFAULT_FIXES = {
    "2021-11-12-self-control": "2 Peter 1:5-7",
    "2021-11-13-steadfastness": "2 Peter 1:5-7",
}


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def cf_env() -> dict:
    """os.environ + Cloudflare creds from .dev.vars, so wrangler works headless.
    Without this, a token that can see more than one account makes wrangler stop
    and ask which one -- fatal in a non-interactive run."""
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def d1_json(command: str, remote: bool) -> list:
    mode = "--remote" if remote else "--local"
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, "--json", "--command", command],
        cwd=REPO, capture_output=True, text=True, shell=WIN, env=cf_env(),
        encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit(f"d1 query failed:\n{out.stderr or out.stdout}")
    return json.loads(out.stdout[out.stdout.index("["):])


def d1_file(sql: str, remote: bool) -> None:
    mode = "--remote" if remote else "--local"
    path = REPO / "tools" / "_fix_passage.sql"
    path.write_text(sql, encoding="utf-8")
    res = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, f"--file={path}"],
        cwd=REPO, shell=WIN, env=cf_env(),
    )
    path.unlink(missing_ok=True)
    if res.returncode != 0:
        sys.exit("apply failed")


def build_sql(item_id: int, passage: str) -> str:
    """SQL to set an item's primary passage to `passage`."""
    refs = scripture.parse_refs(passage)
    p = refs[0] if refs else {"book": passage, "chapter": None, "verse_start": None, "verse_end": None}
    return "\n".join([
        f"UPDATE items SET passage_ref={q(passage)} WHERE id={item_id};",
        f"DELETE FROM scripture_refs WHERE item_id={item_id} AND is_primary=1;",
        "INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
        f"VALUES ({item_id}, {q(p['book'])}, {q(p.get('chapter'))}, {q(p.get('verse_start'))}, "
        f"{q(p.get('verse_end'))}, 1, {q(passage)}, 'primary');",
    ]) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Fix an item's primary passage.")
    ap.add_argument("--slug", help="single slug to fix (with --passage)")
    ap.add_argument("--passage", help="corrected passage ref, e.g. '2 Peter 1:5-7'")
    ap.add_argument("--remote", action="store_true", help="apply to production D1 (default: local)")
    ap.add_argument("--dry-run", action="store_true", help="print SQL, change nothing")
    a = ap.parse_args()
    remote = a.remote

    if a.slug:
        if not a.passage:
            sys.exit("--slug requires --passage")
        fixes = {a.slug: a.passage}
    else:
        fixes = DEFAULT_FIXES

    all_sql = []
    for slug, passage in fixes.items():
        rows = d1_json(f"SELECT id, title, passage_ref FROM items WHERE slug={q(slug)}", remote)
        res = rows[0]["results"]
        if not res:
            sys.exit(f"No item with slug {slug}")
        item_id, title, old = res[0]["id"], res[0]["title"], res[0]["passage_ref"]
        print(f"  {slug}: {title!r}  {old!r} -> {passage!r}")
        all_sql.append(build_sql(item_id, passage))

    sql = "\n".join(all_sql)
    if a.dry_run:
        print("\n--- DRY RUN, SQL not applied ---\n" + sql)
        return

    d1_file(sql, remote)
    print(f"\nApplied to {'remote' if remote else 'local'} D1.")


if __name__ == "__main__":
    main()
