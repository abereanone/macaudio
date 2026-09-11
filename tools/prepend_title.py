"""Prepend a title page to an existing sermon VIDEO, without re-encoding it.

For messages that were filmed, not just recorded: the video already exists, it
just needs a branded title page on the front and a description to paste.

The card is encoded to match the source's exact codec parameters -- resolution,
frame rate, pixel format, H.264 profile, and a silent AAC track at the same
sample rate and channel count -- so the two can be joined with the concat
demuxer and `-c copy`. A 400 MB sermon is therefore copied, not re-encoded, and
the whole job takes seconds instead of an hour.

Metadata comes from the catalog when --slug is given, or from flags when the
message is not in the catalog yet.

Usage:
  python tools/prepend_title.py --video IN.mp4 --slug SLUG
  python tools/prepend_title.py --video IN.mp4 --title "..." --passage "Colossians 1:9-11" --date 2026-04-26
  python tools/prepend_title.py --video IN.mp4 --slug SLUG --seconds 6
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

WIN = sys.platform == "win32"
DB = "macaudio"
SITE = "https://teaching.michaelcoughlin.net"
DEDICATION = ('Sermon content dedicated to the Public Domain in accordance with '
              'Matthew 10:8 - "Freely you have received, freely shall you give."')


def cf_env() -> dict:
    env = dict(os.environ)
    dv = load_dev_vars()
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if dv.get(k) and not env.get(k):
            env[k] = dv[k]
    return env


def rows(command: str) -> list[dict]:
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", DB, "--remote", "--json", "--command", command],
        cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit("d1 query failed:\n" + (out.stderr or out.stdout))
    return json.loads(out.stdout[out.stdout.index("["):])[0].get("results", [])


def run(cmd: list[str], what: str) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=REPO, shell=WIN, env=cf_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"{what} failed:\n" + (r.stderr or r.stdout)[-1500:])
    return r


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"ffprobe failed on {path}")
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        sys.exit(f"No video stream in {path}")
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    return {
        "w": int(v["width"]), "h": int(v["height"]),
        "fps": (float(num) / float(den)) if float(den) else 30.0,
        "pix_fmt": v.get("pix_fmt", "yuv420p"),
        "profile": (v.get("profile") or "Main").lower(),
        "duration": float(d["format"].get("duration", 0)),
        "a_rate": int(a["sample_rate"]) if a else 44100,
        "a_ch": int(a["channels"]) if a else 2,
        "has_audio": a is not None,
    }


def youtube_title(title: str, series: str | None, part: str | None) -> str:
    """Title, with the series appended only when it adds something.

    Many titles already carry the series and part ("Union with Christ - Part 1"),
    and blindly appending produced "Union with Christ - Part 1 | Union with
    Christ - Part 1". YouTube caps titles at 100 characters."""
    t = title.strip()
    low = t.lower()
    if series and series.strip().lower() not in low:
        tail = f"{series} - {part}" if part and part.strip().lower() not in low else series
        t = f"{t} | {tail}"
    return t[:100]


def safe_filename(name: str) -> str:
    """Windows-illegal characters out, and the middle dot too -- it survives on
    disk but renders as a replacement character in terminals and upload forms."""
    name = name.replace("·", "-")
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', "-", name)).strip(" .") or "sermon"


def main() -> None:
    p = argparse.ArgumentParser(description="Prepend a title page to a sermon video.")
    p.add_argument("--video", required=True)
    p.add_argument("--slug", default=None, help="pull metadata from the catalog")
    p.add_argument("--title", default=None)
    p.add_argument("--passage", default=None)
    p.add_argument("--series", default=None)
    p.add_argument("--part", default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--seconds", type=float, default=5.0, help="title page length")
    p.add_argument("--out-dir", default=None)
    a = p.parse_args()

    src = Path(a.video)
    if not src.exists():
        sys.exit(f"No such video: {src}")

    meta = {"title": a.title, "passage": a.passage, "series": a.series,
            "part": a.part, "date": a.date, "slug": a.slug}
    if a.slug:
        found = rows(
            "SELECT i.slug, i.title, i.passage_ref, i.recorded_on, i.series_part, "
            "c.title AS series FROM items i LEFT JOIN collections c ON c.id=i.collection_id "
            f"WHERE i.slug='{a.slug}'")
        if not found:
            sys.exit(f"No item with slug {a.slug}")
        it = found[0]
        meta = {"title": a.title or it["title"], "passage": a.passage or it["passage_ref"],
                "series": a.series or it.get("series"), "part": a.part or it.get("series_part"),
                "date": a.date or it["recorded_on"], "slug": it["slug"]}
    if not meta["title"]:
        sys.exit("Need --title (or --slug to look one up).")

    info = probe(src)
    print(f"  source    {info['w']}x{info['h']} @ {info['fps']:.3f}fps  {info['pix_fmt']}  "
          f"{info['profile']}  {info['duration']/60:.1f} min")
    if not info["has_audio"]:
        sys.exit("Source has no audio track; concat would desync. Aborting.")

    yt_title = youtube_title(meta["title"], meta.get("series"), meta.get("part"))

    out_dir = Path(a.out_dir) if a.out_dir else src.parent / "out" / (meta["slug"] or safe_filename(meta["title"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "thumbnail.png"
    card = out_dir / "_card.mp4"
    listf = out_dir / "_concat.txt"
    final = out_dir / f"{safe_filename(yt_title)}.mp4"
    desc_f = out_dir / "description.txt"

    # ---- title card --------------------------------------------------------
    cmd = ["node", str(HERE / "make_thumb.mjs"), "--out", str(png), "--title", meta["title"]]
    for flag, key in (("--passage", "passage"), ("--series", "series"),
                      ("--part", "part"), ("--date", "date")):
        if meta.get(key):
            cmd += [flag, str(meta[key])]
    run(cmd, "thumbnail")

    # ---- card encoded to the source's exact parameters ---------------------
    # concat with -c copy only works if both files agree on codec, resolution,
    # frame rate, pixel format and audio layout. Anything off and the join either
    # fails or desyncs, so every one of these is copied from the probe.
    run(["ffmpeg", "-y", "-v", "error",
         "-loop", "1", "-framerate", f"{info['fps']:.6f}", "-i", str(png),
         "-f", "lavfi", "-i",
         f"anullsrc=channel_layout={'stereo' if info['a_ch'] == 2 else 'mono'}:"
         f"sample_rate={info['a_rate']}",
         "-t", str(a.seconds),
         "-c:v", "libx264", "-profile:v", info["profile"], "-preset", "slow",
         "-tune", "stillimage", "-crf", "20", "-pix_fmt", info["pix_fmt"],
         "-r", f"{info['fps']:.6f}", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
         "-c:a", "aac", "-b:a", "128k", "-ar", str(info["a_rate"]), "-ac", str(info["a_ch"]),
         "-shortest", str(card)], "card encode")

    # ---- join without touching the sermon's bytes --------------------------
    listf.write_text(f"file '{card.resolve().as_posix()}'\nfile '{src.resolve().as_posix()}'\n",
                     encoding="utf-8")
    print(f"  joining   {a.seconds:.0f}s card + {info['duration']/60:.1f} min sermon (stream copy) ...")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listf),
         "-c", "copy", "-movflags", "+faststart", str(final)], "concat")
    card.unlink(missing_ok=True)
    listf.unlink(missing_ok=True)

    # ---- description -------------------------------------------------------
    desc = [meta["title"], ""]
    if meta.get("passage"):
        desc.append(f"Scripture: {meta['passage']}")
    if meta.get("series"):
        desc.append(f"Series: {meta['series']}" + (f" ({meta['part']})" if meta.get("part") else ""))
    if meta.get("date"):
        desc.append(f"Preached: {meta['date']}")
    desc += ["", "Michael Coughlin"]
    if meta.get("slug"):
        desc.append(f"Full audio archive: {SITE}/listen/{meta['slug']}")
    desc += ["", DEDICATION]
    desc_f.write_text("\n".join(desc) + "\n", encoding="utf-8")

    got = probe(final)["duration"]
    want = info["duration"] + a.seconds
    size = final.stat().st_size / 1048576
    ok = abs(got - want) <= 1.5
    print(f"  result    {got/60:.1f} min ({size:.0f} MB)  expected {want/60:.1f} min  "
          f"{'OK' if ok else '*** LENGTH MISMATCH ***'}")
    print(f"\nPackage -> {out_dir}")
    for f in sorted(out_dir.iterdir()):
        print(f"    {f.name}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
