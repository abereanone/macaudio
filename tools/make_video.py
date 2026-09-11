"""Render one catalog item to an upload-ready YouTube package.

Two looks, depending on whether --background is given:

  no --background   the sermon's own title card, held for the whole message.
                    Tiny (~37 MB for 35 min) and renders in about a minute.

  --background M    M is a looping montage from tools/make_montage.py. The
                    sermon's title fades in and out ONCE per cycle; the cycle is
                    repeated to --title-every minutes, encoded once, then
                    stream-copied under the audio.

Only ONE fade in/out pair may be applied to the overlay. Chaining a second
fade=t=in after a fade=t=out silently erases the FIRST appearance, because a
fade-in forces alpha to 0 for every timestamp before its start. Recurrence comes
from the loop repeating, not from stacking fades.

Audio is always re-encoded (AAC) so loudnorm can run: the corpus spans 15 years
of different rooms and recorders, and without normalising it listeners ride the
volume knob between sermons.

Output: .video/out/<slug>/ holding everything an upload needs --

  <Title>.mp4       named as the YouTube title, so the upload form prefills it
  thumbnail.png     drag onto the thumbnail slot
  description.txt   paste into the description (includes footage credits)
  captions.txt      drag into Subtitles; YouTube auto-syncs plain text

Usage:
  python tools/make_video.py --slug SLUG
  python tools/make_video.py --slug SLUG --background .video/loops/background.mp4
  python tools/make_video.py --slug SLUG --background B --title-every 4 --dry-run
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
BUCKET = "macaudio"
SITE = "https://teaching.michaelcoughlin.net"
CREDITS = REPO / ".video" / "source" / "credits.tsv"

# Applies to the teaching itself. Stock footage keeps its own licence, which is
# why the Footage credits sit below this line rather than above it.
DEDICATION = ('Sermon content dedicated to the Public Domain in accordance with '
              'Matthew 10:8 - "Freely you have received, freely shall you give."')

# YouTube normalises to about -14 LUFS; matching it means YouTube leaves the
# audio alone instead of pulling it down.
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"

# A held still only needs a keyframe every 20s. At 2s GOPs the same card costs
# 122 kbps (31 MB per sermon); at these settings it costs 18 kbps (5 MB).
CARD_SECONDS, CARD_FPS = 20, 10

# When the title shows within each cycle.
TITLE_IN, TITLE_IN_D, TITLE_HOLD, TITLE_OUT_D = 6.0, 2.0, 14.0, 3.0

# Above this mean luma behind the text, use dark type on a pale scrim.
LIGHT_THRESHOLD = 110


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


def mean_luma_behind_text(path: Path) -> float | None:
    """Average luma of the left 62% of frame -- where the title sits. Decides
    light vs dark type from the footage instead of by eye."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", "crop=iw*0.62:ih:0:0,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
         "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    vals = [float(m.group(1)) for m in re.finditer(r"YAVG=([\d.]+)", r.stdout or "")]
    return sum(vals) / len(vals) if vals else None


def youtube_title(title: str, series: str | None, part: str | None) -> str:
    """Title, with the series appended only when it adds something. Many titles
    already carry the series and part, and blindly appending produced "Union with
    Christ - Part 1 | Union with Christ - Part 1". Capped at YouTube's 100."""
    t = title.strip()
    low = t.lower()
    if series and series.strip().lower() not in low:
        tail = f"{series} - {part}" if part and part.strip().lower() not in low else series
        t = f"{t} | {tail}"
    return t[:100]


def safe_filename(name: str) -> str:
    """YouTube prefills the title from the filename, so the file is named for the
    title -- minus the characters Windows will not allow in one, and the middle
    dot, which survives on disk but renders as a replacement character in
    terminals and upload forms."""
    name = name.replace("·", "-")
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', "-", name)).strip(" .") or "sermon"


def load_credits(clips: list[str]) -> list[str]:
    if not CREDITS.exists():
        return []
    table = {}
    for line in CREDITS.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "\t" in line:
            k, _, v = line.partition("\t")
            table[k.strip()] = v.strip()
    seen, out = set(), []
    for c in clips:
        line = table.get(c)
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def format_captions(text: str, width: int = 42) -> str:
    """Reflow a transcript into short lines for YouTube's auto-sync.

    Auto-sync treats each LINE as a caption cue. The stored transcript is
    paragraph-shaped -- lines over 1,200 characters, with blank lines between --
    and handing that to YouTube makes the caption track fail to update. Collapse
    the whitespace and wrap at word boundaries into subtitle-sized lines, which
    is the shape the feature expects. Sentence ends start a new line where the
    transcript is punctuated; much of it is not, so wrapping carries the rest."""
    import textwrap
    out: list[str] = []
    for chunk in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        if chunk:
            out.extend(textwrap.wrap(chunk, width=width) or [chunk])
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Render one item to a YouTube upload package.")
    p.add_argument("--slug", required=True)
    p.add_argument("--background", default=None, help="montage from make_montage.py")
    p.add_argument("--title-every", type=float, default=4.0, help="minutes between title appearances")
    p.add_argument("--out-dir", default=str(REPO / ".video" / "out"))
    p.add_argument("--crf", type=int, default=25)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    found = rows(
        "SELECT i.id, i.slug, i.title, i.passage_ref, i.recorded_on, i.category, i.duration_sec, "
        "i.source_path, i.r2_key, i.series_part, c.title AS series "
        f"FROM items i LEFT JOIN collections c ON c.id=i.collection_id WHERE i.slug={q(a.slug)}")
    if not found:
        sys.exit(f"No item with slug {a.slug}")
    it = found[0]

    yt_title = youtube_title(it["title"], it.get("series"), it.get("series_part"))

    pkg = Path(a.out_dir) / a.slug
    pkg.mkdir(parents=True, exist_ok=True)
    mp4 = pkg / f"{safe_filename(yt_title)}.mp4"
    png = pkg / "thumbnail.png"
    desc_f = pkg / "description.txt"
    caps_f = pkg / "captions.txt"
    card = pkg / "_card.mp4"
    master = pkg / "_master.mp4"
    overlay = pkg / "_overlay.png"

    # audio: prefer the local source; fall back to pulling the object from R2
    src = Path(it["source_path"]) if it.get("source_path") else None
    if src is None or not src.exists():
        if not it.get("r2_key"):
            sys.exit("No local source_path and no r2_key -- nothing to render.")
        src = pkg / f"{a.slug}{Path(it['r2_key']).suffix}"
        print(f"  local source missing; pulling {it['r2_key']} from R2")
        if not a.dry_run:
            r = subprocess.run(["npx", "wrangler", "r2", "object", "get", f"{BUCKET}/{it['r2_key']}",
                                "--remote", "--file", str(src)],
                               cwd=REPO, shell=WIN, env=cf_env(), capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit("R2 get failed:\n" + (r.stderr or r.stdout))

    bg = Path(a.background) if a.background else None
    if bg and not bg.exists():
        sys.exit(f"No montage at {bg} -- run tools/make_montage.py first.")

    light = False
    cycles = 1
    if bg:
        luma = mean_luma_behind_text(bg)
        light = bool(luma is not None and luma > LIGHT_THRESHOLD)
        bg_len = probe(bg)
        cycles = max(1, round((a.title_every * 60) / bg_len))
        print(f"  montage   {bg.name}  {bg_len:.0f}s x {cycles} = {bg_len*cycles/60:.1f} min/cycle")
        print(f"  luma      {luma:.0f} behind the text -> {'LIGHT (dark type)' if light else 'DARK (cream type)'}")

    print(f"\n  slug      {a.slug}")
    print(f"  title     {yt_title}")
    print(f"  package   {pkg}")
    if a.dry_run:
        print("\n--- DRY RUN, nothing written ---")
        return

    audio_dur = probe(src)
    if not audio_dur:
        sys.exit(f"Could not read a duration from {src}")

    # ---- thumbnail (always the opaque card) --------------------------------
    base = ["node", str(HERE / "make_thumb.mjs"), "--title", it["title"]]
    for flag, key in (("--passage", "passage_ref"), ("--series", "series"),
                      ("--part", "series_part"), ("--date", "recorded_on")):
        if it.get(key):
            base += [flag, str(it[key])]
    run(base + ["--out", str(png)], "thumbnail")

    if bg:
        # ---- transparent overlay, then one title fade per cycle ------------
        ov = base + ["--out", str(overlay), "--overlay", "1"]
        if light:
            ov += ["--light", "1"]
        run(ov, "overlay card")

        out_d = TITLE_IN + TITLE_IN_D + TITLE_HOLD
        print(f"\n  building {cycles}-cycle master, title {TITLE_IN:.0f}s-{out_d + TITLE_OUT_D:.0f}s ...")
        run(["ffmpeg", "-y", "-v", "error",
             "-stream_loop", str(cycles - 1), "-i", str(bg),
             "-loop", "1", "-i", str(overlay),
             "-filter_complex",
             f"[1:v]format=rgba,"
             f"fade=t=in:st={TITLE_IN}:d={TITLE_IN_D}:alpha=1,"
             f"fade=t=out:st={out_d}:d={TITLE_OUT_D}:alpha=1[ov];"
             f"[0:v][ov]overlay=0:0:shortest=1[v]",
             "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
             "-pix_fmt", "yuv420p", "-g", "240", "-keyint_min", "240", "-sc_threshold", "0",
             "-an", str(master)], "master encode")
        loop_src = master
    else:
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(CARD_FPS),
             "-i", str(png), "-t", str(CARD_SECONDS),
             "-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "26",
             "-pix_fmt", "yuv420p", "-r", str(CARD_FPS),
             "-g", str(CARD_SECONDS * CARD_FPS), "-keyint_min", str(CARD_SECONDS * CARD_FPS),
             "-sc_threshold", "0", str(card)], "card encode")
        loop_src = card

    # ---- loop it under the audio without re-encoding a frame ---------------
    print("  rendering (video copied, audio normalised) ...")
    run(["ffmpeg", "-y", "-v", "error",
         "-stream_loop", "-1", "-i", str(loop_src),
         "-i", str(src),
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy",
         "-af", LOUDNORM,
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
         "-t", f"{audio_dur:.3f}",
         "-movflags", "+faststart", str(mp4)], "ffmpeg render")
    for junk in (card, master, overlay):
        junk.unlink(missing_ok=True)

    # ---- description, with footage credits ---------------------------------
    desc = [it["title"], ""]
    if it.get("passage_ref"):
        desc.append(f"Scripture: {it['passage_ref']}")
    if it.get("series"):
        desc.append(f"Series: {it['series']}" + (f" ({it['series_part']})" if it.get("series_part") else ""))
    if it.get("recorded_on"):
        desc.append(f"Preached: {it['recorded_on']}")
    desc += ["", "Michael Coughlin", f"Full audio archive: {SITE}/listen/{a.slug}",
             "", DEDICATION]

    if bg:
        manifest = bg.with_suffix(".clips.json")
        clips = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
        credits = load_credits(clips)
        if credits:
            desc += ["", "Footage:"] + credits
        missing = [c for c in clips if not load_credits([c])]
        if missing:
            print(f"  WARNING: no credit line in credits.tsv for: {', '.join(missing)}")
    desc_f.write_text("\n".join(desc) + "\n", encoding="utf-8")

    # ---- captions: YouTube auto-syncs plain text, no timings needed ---------
    tr = rows(f"SELECT t.text FROM item_transcripts t WHERE t.item_id={it['id']}")
    if tr and tr[0].get("text"):
        caps_f.write_text(format_captions(tr[0]["text"]), encoding="utf-8")
    else:
        caps_f.unlink(missing_ok=True)
        print("  (no transcript -- captions.txt not written)")

    got = probe(mp4)
    want = it.get("duration_sec") or 0
    size_mb = mp4.stat().st_size / 1048576
    ok = abs(got - want) <= 1.5 if want else True
    print(f"\n  video     {got/60:.1f} min ({size_mb:.0f} MB)   expected {want/60:.1f} min  "
          f"{'OK' if ok else '*** DURATION MISMATCH ***'}")
    print(f"\nPackage -> {pkg}")
    for f in sorted(pkg.iterdir()):
        print(f"    {f.name}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
