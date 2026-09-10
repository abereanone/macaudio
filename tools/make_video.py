"""Render one catalog item to an upload-ready YouTube MP4 + thumbnail.

The video is a looping background clip; the audio is the sermon. The background
is stream-COPIED (never re-encoded), so a 40-minute video takes seconds -- the
loop is encoded once, in .video/loops/<category>.mp4, and reused.

Audio IS re-encoded (AAC) so the MP4 is broadly compatible, which also lets us
run loudnorm. The corpus spans 15 years of different rooms and recorders, so
without normalisation listeners ride the volume knob between sermons.

Outputs, into --out-dir (default .video/out):
  <slug>.mp4    the upload
  <slug>.png    1280x720 thumbnail (tools/make_thumb.mjs)
  <slug>.txt    title + description to paste into YouTube

Usage:
  python tools/make_video.py --slug 2024-05-12-suffering-saints-seek-a-savior
  python tools/make_video.py --slug SLUG --dry-run
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
BUCKET = "macaudio"
SITE = "https://teaching.michaelcoughlin.net"

# YouTube normalises to about -14 LUFS; matching it means YouTube leaves the
# audio alone instead of pulling it down.
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


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


def run(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"{what} failed:\n" + (r.stderr or r.stdout)[-1500:])


def probe(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def main() -> None:
    p = argparse.ArgumentParser(description="Render one item to a YouTube MP4 + thumbnail.")
    p.add_argument("--slug", required=True)
    p.add_argument("--out-dir", default=str(REPO / ".video" / "out"))
    p.add_argument("--loops-dir", default=str(REPO / ".video" / "loops"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    found = rows(
        "SELECT i.slug, i.title, i.passage_ref, i.recorded_on, i.category, i.duration_sec, "
        "i.source_path, i.r2_key, i.series_part, c.title AS series "
        f"FROM items i LEFT JOIN collections c ON c.id=i.collection_id WHERE i.slug={q(a.slug)}")
    if not found:
        sys.exit(f"No item with slug {a.slug}")
    it = found[0]

    loop = Path(a.loops_dir) / f"{it['category']}.mp4"
    if not loop.exists():
        loop = Path(a.loops_dir) / "sermon.mp4"
        if not loop.exists():
            sys.exit(f"No loop for category {it['category']} and no sermon.mp4 fallback in {a.loops_dir}")

    out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    mp4, png, txt = (out_dir / f"{a.slug}.mp4", out_dir / f"{a.slug}.png", out_dir / f"{a.slug}.txt")

    # audio: prefer the local source; fall back to pulling the object from R2
    src = Path(it["source_path"]) if it.get("source_path") else None
    if src is None or not src.exists():
        if not it.get("r2_key"):
            sys.exit("No local source_path and no r2_key -- nothing to render.")
        src = out_dir / f"{a.slug}{Path(it['r2_key']).suffix}"
        print(f"  local source missing; pulling {it['r2_key']} from R2")
        if not a.dry_run:
            r = subprocess.run(["npx", "wrangler", "r2", "object", "get", f"{BUCKET}/{it['r2_key']}",
                                "--remote", "--file", str(src)],
                               cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit("R2 get failed:\n" + (r.stderr or r.stdout))

    bits = [it["title"]]
    if it.get("series") and it.get("series_part"):
        bits.append(f"{it['series']} \u00b7 {it['series_part']}")
    elif it.get("series"):
        bits.append(it["series"])
    yt_title = " | ".join(bits)[:100]   # YouTube hard-caps titles at 100 chars

    desc = [it["title"], ""]
    if it.get("passage_ref"):
        desc.append(f"Scripture: {it['passage_ref']}")
    if it.get("series"):
        desc.append(f"Series: {it['series']}" + (f" ({it['series_part']})" if it.get("series_part") else ""))
    if it.get("recorded_on"):
        desc.append(f"Preached: {it['recorded_on']}")
    desc += ["", "Michael Coughlin", f"Full audio archive: {SITE}/listen/{a.slug}", ""]

    print(f"\n  slug      {a.slug}")
    print(f"  category  {it['category']}   loop {loop.name}")
    print(f"  audio     {src}")
    print(f"  title     {yt_title}")
    print(f"  outputs   {mp4.name}, {png.name}, {txt.name}")
    if a.dry_run:
        print("\n--- DRY RUN, nothing written ---")
        return

    # -shortest is NOT frame-accurate with a stream-copied video: it flushes to a
    # packet boundary and leaves several seconds of background running past the
    # end of the audio. Cap the output at the audio's real duration instead.
    audio_dur = probe(src)
    if not audio_dur:
        sys.exit(f"Could not read a duration from {src}")

    ff = ["ffmpeg", "-y", "-v", "error",
          "-stream_loop", "-1", "-i", str(loop),
          "-i", str(src),
          "-map", "0:v", "-map", "1:a",
          "-c:v", "copy",                       # background is never re-encoded
          "-af", LOUDNORM,
          "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
          "-t", f"{audio_dur:.3f}",
          "-movflags", "+faststart", str(mp4)]
    print("\n  rendering (background copied, audio normalised) ...")
    run(ff, "ffmpeg render")

    thumb = ["node", str(HERE / "make_thumb.mjs"), "--out", str(png), "--title", it["title"]]
    for flag, key in (("--passage", "passage_ref"), ("--series", "series"),
                      ("--part", "series_part"), ("--date", "recorded_on")):
        if it.get(key):
            thumb += [flag, str(it[key])]
    run(thumb, "thumbnail")

    txt.write_text(yt_title + "\n\n" + "\n".join(desc), encoding="utf-8")

    got, want = probe(mp4), it.get("duration_sec") or 0
    size_mb = mp4.stat().st_size / 1048576
    ok = abs(got - want) <= 1.5 if want else True
    print(f"  video     {got/60:.1f} min ({size_mb:.0f} MB)   expected {want/60:.1f} min  "
          f"{'OK' if ok else '*** DURATION MISMATCH ***'}")
    print(f"\nDone -> {mp4}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
