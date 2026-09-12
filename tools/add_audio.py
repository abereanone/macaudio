"""Give an existing video-only catalog item its audio.

Some messages went straight to someone's YouTube channel and were never recorded
to audio here, so the item has a video_url but no r2_key and no transcript --
nothing to play on the site, and nothing to search. This pulls the audio down
from that video, files it with the rest of the source audio, uploads it to R2,
points the item at it, and transcribes it.

add_sermon.py cannot do this: it CREATES an item. This updates one that already
exists, and leaves its title, date, category and series alone.

Usage:
  python tools/add_audio.py --slug SLUG                 # from the item's video_url
  python tools/add_audio.py --slug SLUG --audio F.mp3   # from a file you already have
  python tools/add_audio.py --slug SLUG --dry-run
  python tools/add_audio.py --list                      # every item missing audio
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import load_dev_vars  # noqa: E402
from add_sermon import transcribe_file  # noqa: E402

WIN = sys.platform == "win32"
DB = "macaudio"
BUCKET = "macaudio"
AUDIO_DIR = Path(r"C:\Users\mac\Proton Drive\abereanone\My files\02_Bible-Teaching\TeachingPreaching")
# Matches the rest of the corpus: speech, mono, small.
MP3_BITRATE = "64k"
CACHE = "public, max-age=31536000, immutable"


def cf_env() -> dict:
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def rows(command: str) -> list[dict]:
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", DB, "--remote", "--json", "--command", command],
        cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit("d1 query failed:\n" + (out.stderr or out.stdout))
    return json.loads(out.stdout[out.stdout.index("["):])[0].get("results", [])


def run(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"{what} failed:\n" + (r.stderr or r.stdout)[-1500:])


def probe(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def safe_stem(title: str, date: str | None) -> str:
    stem = re.sub(r'[\\/:*?"<>|]+', "", title).strip(" .")
    stem = re.sub(r"\s+", " ", stem)[:80].strip()
    return f"{stem} - {(date or '').replace('-', '')}".strip(" -")


def main() -> None:
    p = argparse.ArgumentParser(description="Attach audio to an existing video-only item.")
    p.add_argument("--slug")
    p.add_argument("--audio", default=None, help="use this file instead of downloading")
    p.add_argument("--list", action="store_true", help="show items with no audio and exit")
    p.add_argument("--no-transcript", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.list:
        found = rows("SELECT slug, title, category, recorded_on, duration_sec, video_url "
                     "FROM items WHERE r2_key IS NULL ORDER BY recorded_on DESC")
        print(f"  {len(found)} item(s) with no audio:\n")
        for r in found:
            d = r.get("duration_sec") or 0
            print(f"    {r['recorded_on']}  {d//60:>3}:{d%60:02d}  {r['category']:<10} "
                  f"{r['title'][:46]:<46} {'video' if r['video_url'] else 'NO VIDEO'}")
            print(f"      {r['slug']}")
        return

    if not a.slug:
        sys.exit("Need --slug (or --list).")

    found = rows("SELECT id, slug, title, category, recorded_on, duration_sec, r2_key, "
                 f"source_path, video_url FROM items WHERE slug={q(a.slug)}")
    if not found:
        sys.exit(f"No item with slug {a.slug}")
    it = found[0]
    if it.get("r2_key"):
        sys.exit(f"{a.slug} already has audio at {it['r2_key']}. Refusing to overwrite.")

    dest = AUDIO_DIR / f"{safe_stem(it['title'], it['recorded_on'])}.mp3"
    r2_key = f"audio/{a.slug}.mp3"   # category-free, per docs/youtube-pipeline.md

    print(f"\n  {it['title']}")
    print(f"  slug      {a.slug}   ({it['category']}, {it['recorded_on']})")
    print(f"  source    {'--audio ' + a.audio if a.audio else it.get('video_url') or '(none)'}")
    print(f"  file      {dest}")
    print(f"  r2_key    {r2_key}")
    if a.dry_run:
        print("\n--- DRY RUN, nothing written ---")
        return

    # ---- 1) get the audio ---------------------------------------------------
    if a.audio:
        src = Path(a.audio)
        if not src.exists():
            sys.exit(f"No such file: {src}")
        if src.resolve() != dest.resolve():
            run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1",
                 "-c:a", "libmp3lame", "-b:a", MP3_BITRATE, str(dest)], "audio convert")
    else:
        if not it.get("video_url"):
            sys.exit("Item has no video_url and no --audio was given.")
        if dest.exists():
            print(f"  (already downloaded: {dest.name})")
        else:
            print("  downloading audio from the video ...")
            run(["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "5",
                 "--no-warnings", "--postprocessor-args", f"-ac 1 -b:a {MP3_BITRATE}",
                 "-o", str(dest.with_suffix(".%(ext)s")), it["video_url"]], "yt-dlp")
    if not dest.exists():
        sys.exit(f"Expected audio at {dest} but it is not there.")

    dur = int(round(probe(dest)))
    size = dest.stat().st_size
    print(f"  audio     {dur//60}:{dur%60:02d}  ({size/1048576:.0f} MB)")
    if it.get("duration_sec") and abs(dur - it["duration_sec"]) > 60:
        print(f"  NOTE: catalog said {it['duration_sec']//60}:{it['duration_sec']%60:02d}; "
              f"updating to the audio's real length.")

    # ---- 2) upload ----------------------------------------------------------
    print("  uploading to R2 ...")
    run(["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{r2_key}",
         "--file", str(dest), "--content-type", "audio/mpeg",
         "--cache-control", CACHE, "--remote"], "R2 upload")

    # ---- 3) point the item at it -------------------------------------------
    sql = (f"UPDATE items SET r2_key={q(r2_key)}, duration_sec={dur}, "
           f"source_path={q(str(dest))} WHERE id={it['id']};")
    sql_file = HERE / f"_add_audio_{a.slug}.sql"
    sql_file.write_text(sql + "\n", encoding="utf-8")
    try:
        run(["npx", "wrangler", "d1", "execute", DB, "--remote", f"--file={sql_file}"], "d1 update")
    finally:
        sql_file.unlink(missing_ok=True)
    print("  item updated.")

    # ---- 4) transcribe + index ---------------------------------------------
    if a.no_transcript:
        print(f"\n  skipped transcript. Later:  python tools/attach_transcript.py "
              f"--slug {a.slug} --remote")
    else:
        transcribe_file(dest)
        run([sys.executable, str(HERE / "attach_transcript.py"), "--slug", a.slug, "--remote"],
            "attach_transcript")

    # An item that just gained audio deserves its own share card too. Non-fatal:
    # a NULL og_key falls back to the site default, so a failure here costs a
    # nicer preview, not a working page.
    print("  generating the Open Graph card ...")
    if subprocess.run([sys.executable, str(HERE / "make_og.py"), "--slug", a.slug],
                      cwd=REPO, shell=WIN, env=cf_env(),
                      capture_output=True, text=True).returncode != 0:
        print(f"  card step failed -- rerun later: python tools/make_og.py --slug {a.slug}")

    print(f"\nDone -> https://teaching.michaelcoughlin.net/listen/{a.slug}")


if __name__ == "__main__":
    main()
