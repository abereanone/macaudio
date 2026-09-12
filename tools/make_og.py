"""Generate a per-sermon Open Graph card and point the item at it.

Every page shares /og-default.png today, so a shared sermon link previews as the
generic archive card. This renders that sermon's own card -- title, passage,
series, date, in the site's brand -- uploads it to R2 and records the key in
items.og_key.

Stored rather than derived: a NULL og_key means "use the default", which is
always correct, whereas a computed URL would 404 for anything not yet generated
and a broken image previews worse than the generic card.

Reuses tools/make_thumb.mjs, so these are the same cards as the YouTube
thumbnails -- 1280x720. Base.astro sends the real dimensions with them.

Resumable: items that already have an og_key are skipped unless --force, so an
interrupted run can simply be re-run.

Usage:
  python tools/make_og.py --slug SLUG          # one item
  python tools/make_og.py --all                # everything missing a card
  python tools/make_og.py --all --limit 5      # a few, to check
  python tools/make_og.py --all --force        # regenerate existing ones too
  python tools/make_og.py --all --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import load_dev_vars  # noqa: E402

WIN = sys.platform == "win32"
DB = "macaudio"
BUCKET = "macaudio"
# Short, unlike audio's immutable year: a corrected title should show up in new
# shares within a day rather than being cached for a year under the same key.
CACHE = "public, max-age=86400"


def cf_env() -> dict:
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def q(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def rows(command: str) -> list[dict]:
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", DB, "--remote", "--json", "--command", command],
        cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit("d1 query failed:\n" + (out.stderr or out.stdout))
    return json.loads(out.stdout[out.stdout.index("["):])[0].get("results", [])


def run(cmd: list[str], what: str) -> bool:
    r = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"    {what} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        return False
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Generate per-item Open Graph cards.")
    p.add_argument("--slug")
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--force", action="store_true", help="regenerate items that already have a card")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if not a.slug and not a.all:
        sys.exit("need --slug or --all")

    where = f"i.slug={q(a.slug)}" if a.slug else ("1=1" if a.force else "i.og_key IS NULL")
    items = rows(
        "SELECT i.id, i.slug, i.title, i.passage_ref, i.recorded_on, i.series_part, "
        "c.title AS series FROM items i "
        f"LEFT JOIN collections c ON c.id=i.collection_id WHERE {where} "
        "ORDER BY i.recorded_on DESC")
    if a.limit:
        items = items[:a.limit]
    if not items:
        print("  nothing to do -- every item already has a card.")
        return

    print(f"  {len(items)} card(s) to generate\n")
    if a.dry_run:
        for it in items[:10]:
            print(f"    og/{it['slug']}.png   {it['title'][:50]}")
        if len(items) > 10:
            print(f"    ... and {len(items) - 10} more")
        return

    ok = fail = 0
    sql: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, it in enumerate(items, 1):
            png = Path(tmp) / f"{it['slug']}.png"
            cmd = ["node", str(HERE / "make_thumb.mjs"), "--out", str(png), "--title", it["title"]]
            for flag, key in (("--passage", "passage_ref"), ("--series", "series"),
                              ("--part", "series_part"), ("--date", "recorded_on")):
                if it.get(key):
                    cmd += [flag, str(it[key])]
            if not run(cmd, "render"):
                fail += 1
                continue

            key = f"og/{it['slug']}.png"
            if not run(["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}",
                        "--file", str(png), "--content-type", "image/png",
                        "--cache-control", CACHE, "--remote"], "upload"):
                fail += 1
                continue

            sql.append(f"UPDATE items SET og_key={q(key)} WHERE id={it['id']};")
            ok += 1
            print(f"  [{n:>3}/{len(items)}] {png.stat().st_size/1024:>5.0f} KB  {it['title'][:52]}")

            # flush periodically so an interrupted run keeps what it finished
            if len(sql) >= 25:
                _apply(sql)
                sql = []

    if sql:
        _apply(sql)
    print(f"\n  generated {ok}, failed {fail}")


def _apply(sql: list[str]) -> None:
    f = HERE / "_og_keys.sql"
    f.write_text("\n".join(sql) + "\n", encoding="utf-8")
    try:
        r = subprocess.run(["npx", "wrangler", "d1", "execute", DB, "--remote", f"--file={f}"],
                           cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            sys.exit("d1 update failed:\n" + (r.stderr or r.stdout)[-800:])
        print(f"    -> recorded {len(sql)} og_key(s)")
    finally:
        f.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
