"""Build the shared background montage that sermon videos loop over.

Takes the clips in .video/source/, normalises them, crossfades each into the
next, then crossfades the montage's own tail back into its head so it loops with
no visible seam and nothing ever plays backwards. (Reversing a clip to hide a
loop point reads as distracting -- see docs/youtube-pipeline.md.)

The montage carries NO title: it is background only, built once and reused by
every sermon. make_video.py overlays each sermon's own title onto it.

Usage:
  python tools/make_montage.py                 # all clips in .video/source
  python tools/make_montage.py --fade 2.0 --crf 25
  python tools/make_montage.py --out .video/loops/background.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / ".video" / "source"
W, H, FPS = 1280, 720, 24


def probe_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def run(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"{what} failed:\n" + (r.stderr or r.stdout)[-2000:])


def main() -> None:
    p = argparse.ArgumentParser(description="Build the shared background montage.")
    p.add_argument("--src", default=str(SRC_DIR))
    p.add_argument("--out", default=str(REPO / ".video" / "loops" / "background.mp4"))
    p.add_argument("--fade", type=float, default=1.5, help="crossfade seconds")
    p.add_argument("--crf", type=int, default=25)
    p.add_argument("--slow", type=float, default=1.0,
                   help="slow every clip by this factor to lengthen the loop. "
                        "Locked-off footage tolerates 2x invisibly; it is the "
                        "cheapest way to make the visual loop recur less often.")
    a = p.parse_args()

    src = Path(a.src)
    clips = sorted(x for x in src.glob("*.mp4"))
    if not clips:
        sys.exit(f"No .mp4 clips in {src}")
    d = a.fade
    durs = [probe_duration(c) * a.slow for c in clips]
    if any(x <= 2 * d for x in durs):
        sys.exit(f"Every clip must be longer than 2x the {d}s crossfade.")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".chain.mp4")

    print(f"  {len(clips)} clip(s), {d}s crossfades:")
    for c, x in zip(clips, durs):
        print(f"    {x:6.1f}s  {c.name}")

    # ---- pass 1: normalise + crossfade each clip into the next --------------
    # Clips arrive at different sizes and frame rates (720p24, 1440p30, ...), and
    # xfade requires identical geometry and timebase on both sides.
    parts, labels = [], []
    for i, _ in enumerate(clips):
        parts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setpts={a.slow}*PTS,fps={FPS},setsar=1,format=yuv420p[n{i}]")
        labels.append(f"[n{i}]")

    chain, offset = labels[0], 0.0
    for i in range(1, len(clips)):
        offset += durs[i - 1] - d
        nxt = f"[x{i}]"
        parts.append(f"{chain}{labels[i]}xfade=transition=fade:duration={d}:offset={offset:.3f}{nxt}")
        chain = nxt
    chain_len = sum(durs) - d * (len(clips) - 1)

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    cmd += ["-filter_complex", ";".join(parts), "-map", chain,
            "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf),
            "-pix_fmt", "yuv420p", "-an", str(tmp)]
    print(f"\n  pass 1: crossfade chain -> {chain_len:.1f}s")
    run(cmd, "montage chain")

    # ---- pass 2: seal the loop by blending the tail back into the head ------
    # out[0..d] ramps from the chain's tail to its head, so playback running off
    # the end lands continuously on the start. Final length = chain - d.
    end = chain_len
    final_len = end - d
    seal = (
        f"[0:v]split=3[c1][c2][c3];"
        f"[c1]trim=0:{d},setpts=PTS-STARTPTS[h];"
        f"[c2]trim={end - d:.3f}:{end:.3f},setpts=PTS-STARTPTS[tl];"
        f"[h][tl]blend=all_expr='A*(T/{d})+B*(1-T/{d})'[mix];"
        f"[c3]trim={d}:{end - d:.3f},setpts=PTS-STARTPTS[body];"
        f"[mix][body]concat=n=2:v=1[v]")
    print(f"  pass 2: seal the loop     -> {final_len:.1f}s")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-filter_complex", seal,
         "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
         "-pix_fmt", "yuv420p", "-g", str(FPS * 10), "-keyint_min", str(FPS * 10),
         "-sc_threshold", "0", "-an", str(out)], "montage seal")
    tmp.unlink(missing_ok=True)

    # record which clips went in, so make_video.py can credit exactly these
    (out.with_suffix(".clips.json")).write_text(
        json.dumps([c.name for c in clips], indent=2), encoding="utf-8")

    got = probe_duration(out)
    size = out.stat().st_size / 1048576
    print(f"\n  {out}  {got/60:.1f} min, {size:.0f} MB")
    print(f"  title will appear once every {got/60:.1f} min when looped")


if __name__ == "__main__":
    main()
