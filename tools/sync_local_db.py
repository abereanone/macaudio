"""Copy production D1 into the LOCAL dev database, so local preview is truthful.

`wrangler d1 export` refuses this database -- "cannot export databases with
Virtual Tables (fts5)" -- because of the item_fts search index. So this reads the
base tables over the query API and replays them locally instead.

item_fts is NOT copied. The 0003_fts_sync triggers own it, and they fire on
INSERT, so loading items and item_transcripts in order rebuilds the search index
locally for free. Copying it would double-insert.

Writes ONLY to --local. Production is read from and never touched.

Usage:
  python tools/sync_local_db.py
  python tools/sync_local_db.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import load_dev_vars  # noqa: E402

WIN = sys.platform == "win32"
DB = "macaudio"

# Parents before children: speakers/collections are referenced by items, and
# items by the rest. Deletes run in reverse.
TABLES = ["speakers", "collections", "items", "item_transcripts",
          "scripture_refs", "item_files"]


def cf_env() -> dict:
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def d1(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["npx", "wrangler", "d1", "execute", DB] + args,
                          cwd=REPO, shell=WIN, env=cf_env(), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def query(sql: str) -> list[dict]:
    out = d1(["--remote", "--json", "--command", sql])
    if out.returncode != 0:
        sys.exit("remote query failed:\n" + (out.stderr or out.stdout))
    return json.loads(out.stdout[out.stdout.index("["):])[0].get("results", [])


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    p = argparse.ArgumentParser(description="Copy production D1 into local dev D1.")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    sql: list[str] = ["PRAGMA defer_foreign_keys = true;"]
    for t in reversed(TABLES):
        sql.append(f"DELETE FROM {t};")
    # item_fts is trigger-owned, but the stale local rows belong to items that
    # are about to be deleted; clear it so nothing survives the swap.
    sql.append("DELETE FROM item_fts;")

    counts = {}
    for t in TABLES:
        rows = query(f"SELECT * FROM {t}")
        counts[t] = len(rows)
        print(f"  {t:<18} {len(rows):>5} rows")
        for r in rows:
            cols = ", ".join(r.keys())
            vals = ", ".join(lit(v) for v in r.values())
            sql.append(f"INSERT INTO {t} ({cols}) VALUES ({vals});")

    body = "\n".join(sql) + "\n"
    out_file = REPO / "tools" / "_sync_local.sql"
    size_mb = len(body.encode("utf-8")) / 1048576
    print(f"\n  {sum(counts.values()):,} rows, {size_mb:.1f} MB of SQL")

    if a.dry_run:
        print("\n--- DRY RUN: not applied ---")
        print("\n".join(body.splitlines()[:6]))
        return

    out_file.write_text(body, encoding="utf-8")
    try:
        print("  applying to LOCAL ...")
        r = d1(["--local", f"--file={out_file}"])
        if r.returncode != 0:
            sys.exit("local apply failed:\n" + (r.stderr or r.stdout)[-2000:])
    finally:
        out_file.unlink(missing_ok=True)

    # confirm, including that the triggers rebuilt the search index
    check = d1(["--local", "--json", "--command",
                "SELECT (SELECT COUNT(*) FROM items) items, "
                "(SELECT COUNT(*) FROM items WHERE video_url IS NOT NULL) with_video, "
                "(SELECT COUNT(*) FROM item_transcripts) transcripts, "
                "(SELECT COUNT(*) FROM item_fts) fts"])
    if check.returncode != 0:
        sys.exit("verification query failed:\n" + (check.stderr or check.stdout))
    got = json.loads(check.stdout[check.stdout.index("["):])[0]["results"][0]
    print(f"\n  local now: {got['items']} items, {got['with_video']} with video, "
          f"{got['transcripts']} transcripts, {got['fts']} search rows")
    if got["fts"] != got["items"]:
        print("  WARNING: search rows != items; the fts triggers may not be installed locally.")


if __name__ == "__main__":
    main()
