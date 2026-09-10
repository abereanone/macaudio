"""Upload each catalog item's source audio to R2 under its r2_key.

Reads (r2_key, source_path) from the LOCAL D1 catalog, uploads every item that
has an r2_key (drop_audio items have NULL and are skipped) to the `macaudio`
bucket via `wrangler r2 object put --remote`. Resumable: each successful key is
recorded in tools/uploaded_r2.log and skipped on re-run.

    set CLOUDFLARE_ACCOUNT_ID=6481c7e370bbed874eb7679096eb1612   (PowerShell: $env:...)
    python tools/upload_r2.py            # upload missing files
    python tools/upload_r2.py --dry-run  # list what would upload

Note: the bytes are served at MEDIA_BASE_URL (media.michaelcoughlin.net); that
R2 public custom domain must be connected for playback, but upload works now.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUCKET = "macaudio"
LOG = Path(__file__).resolve().parent / "uploaded_r2.log"
WIN = sys.platform == "win32"
CT = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".flac": "audio/flac"}
CACHE = "public, max-age=31536000, immutable"


def catalog() -> list[dict]:
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "DB", "--local", "--json",
         "--command", "SELECT r2_key, source_path FROM items WHERE r2_key IS NOT NULL ORDER BY r2_key"],
        cwd=REPO, capture_output=True, text=True, shell=WIN,
        encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit("d1 query failed:\n" + out.stderr)
    # wrangler prints a banner before the JSON array; grab from the first '['.
    txt = out.stdout[out.stdout.index("["):]
    return json.loads(txt)[0]["results"]


def main() -> None:
    dry = "--dry-run" in sys.argv
    rows = catalog()
    done = set(LOG.read_text(encoding="utf-8").split("\n")) if LOG.exists() else set()
    todo = [r for r in rows if r["r2_key"] not in done]
    print(f"{len(rows)} items with audio; {len(rows) - len(todo)} already uploaded; {len(todo)} to go.")

    ok = fail = 0
    for i, r in enumerate(todo, 1):
        key, src = r["r2_key"], Path(r["source_path"])
        if not src.exists():
            print(f"  [{i}/{len(todo)}] MISSING SOURCE, skipping: {src}")
            fail += 1
            continue
        ct = CT.get(src.suffix.lower(), "application/octet-stream")
        mb = src.stat().st_size / 1048576
        print(f"  [{i}/{len(todo)}] {key}  ({mb:.1f} MB)")
        if dry:
            continue
        res = subprocess.run(
            ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}",
             "--file", str(src), "--content-type", ct, "--cache-control", CACHE, "--remote"],
            cwd=REPO, capture_output=True, text=True, shell=WIN,
            encoding="utf-8", errors="replace",
        )
        if res.returncode == 0:
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(key + "\n")
            ok += 1
        else:
            print("      FAILED:", (res.stderr or res.stdout).strip().splitlines()[-1:])
            fail += 1

    print(f"done. uploaded {ok}, failed/skipped {fail}." + (" (dry run)" if dry else ""))


if __name__ == "__main__":
    main()
