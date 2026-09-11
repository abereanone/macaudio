"""Generate a timed .srt subtitle file for one catalog item.

The fallback for when YouTube's "Without timing" auto-sync refuses a plain
transcript. Re-runs the audio through Groq Whisper and KEEPS the per-segment
timestamps, which tools/transcribe_groq.py discards when it stores paragraph
text in item_transcripts.

Long audio is split into chunks, so each chunk's timestamps restart at zero.
Offsets are accumulated from each chunk's PROBED duration rather than from the
requested chunk length, because ffmpeg's segmenter lands near the requested
boundary, not exactly on it -- assuming the nominal length would drift the
subtitles progressively later through a 40-minute sermon.

Usage:
  python tools/make_captions.py --slug SLUG
  python tools/make_captions.py --slug SLUG --out somewhere/captions.srt
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import GROQ_URL, api_key, build_prompt, split_chunks  # noqa: E402

WIN = sys.platform == "win32"
DB = "macaudio"
CHUNK_SECONDS = 1500
MODEL = "whisper-large-v3"
WRAP = 42          # characters per subtitle line
MAX_LINES = 2      # cues longer than this get split across cues


def cf_env() -> dict:
    from transcribe_groq import load_dev_vars
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


def probe(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def segments_for(chunk: Path, key: str, prompt: str, retries: int = 4) -> list[dict]:
    """Like transcribe_chunk, but returns the segments instead of joined text."""
    data = {"model": MODEL, "response_format": "verbose_json", "language": "en",
            "temperature": "0", "prompt": prompt}
    for attempt in range(retries):
        try:
            with chunk.open("rb") as f:
                resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"},
                                     files={"file": (chunk.name, f, "audio/mpeg")},
                                     data=data, timeout=300)
            if resp.status_code == 200:
                return resp.json().get("segments") or []
            if resp.status_code in (408, 409, 429, 500, 502, 503, 504, 524):
                time.sleep(2 ** attempt * 2)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise RuntimeError(f"{type(e).__name__}: {e}")
            time.sleep(2 ** attempt * 2)
    raise RuntimeError("exhausted retries")


def ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segs: list[dict]) -> str:
    """Segments -> SRT. A long segment is split across several cues so no cue
    carries more than MAX_LINES lines, with its time span divided by length."""
    out, n = [], 0
    for seg in segs:
        text = " ".join((seg.get("text") or "").split())
        if not text:
            continue
        start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
        if end <= start:
            end = start + 1.5
        lines = textwrap.wrap(text, width=WRAP) or [text]
        groups = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
        total = sum(len(" ".join(g)) for g in groups) or 1
        cursor = start
        for g in groups:
            share = (end - start) * (len(" ".join(g)) / total)
            n += 1
            out.append(f"{n}\n{ts(cursor)} --> {ts(min(cursor + share, end))}\n" + "\n".join(g) + "\n")
            cursor += share
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="Generate a timed .srt for one item.")
    p.add_argument("--slug", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--chunk-seconds", type=int, default=CHUNK_SECONDS)
    a = p.parse_args()

    found = rows("SELECT slug, title, duration_sec, source_path, r2_key FROM items "
                 f"WHERE slug='{a.slug}'")
    if not found:
        sys.exit(f"No item with slug {a.slug}")
    it = found[0]

    src = Path(it["source_path"]) if it.get("source_path") else None
    if src is None or not src.exists():
        sys.exit(f"Source audio not found locally for {a.slug}: {it.get('source_path')}")

    out = Path(a.out) if a.out else REPO / ".video" / "out" / a.slug / "captions.srt"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"  {it['title']}")
    print(f"  audio  {src}")

    key, prompt = api_key(), build_prompt()
    all_segs: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        chunks = split_chunks(src, Path(tmp), a.chunk_seconds)
        print(f"  {len(chunks)} chunk(s); transcribing with timestamps ...")
        offset = 0.0
        for i, c in enumerate(chunks, 1):
            segs = segments_for(c, key, prompt)
            for s in segs:
                s["start"] = float(s.get("start", 0)) + offset
                s["end"] = float(s.get("end", 0)) + offset
            all_segs.extend(segs)
            dur = probe(c)
            print(f"    chunk {i}: {len(segs):>4} segments, +{dur:.1f}s (offset now {offset + dur:.1f}s)")
            offset += dur

    if not all_segs:
        sys.exit("Whisper returned no segments.")

    srt = to_srt(all_segs)
    out.write_text(srt, encoding="utf-8")

    last = all_segs[-1]["end"]
    want = it.get("duration_sec") or 0
    cues = srt.count(" --> ")
    print(f"\n  {cues} cues, last ends {last/60:.1f} min, audio is {want/60:.1f} min")
    if want and abs(last - want) > 30:
        print("  WARNING: last cue is far from the end of the audio -- check for drift.")
    print(f"\nDone -> {out}")


if __name__ == "__main__":
    main()
