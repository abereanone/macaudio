"""Transcribe audio with Groq's Whisper large-v3 (OpenAI-compatible API).

Writes one .txt beside each source mp3 (same name, same folder) — exactly
where tools/import_catalog.py looks for a transcript. Long files are split
into chunks with ffmpeg (Groq caps upload size), each transcribed, then
stitched into paragraphs. Resumable (skips files that already have a .txt)
and logs failures to transcribe_failures.csv.

Setup: put GROQ_API_KEY=... in this repo's .dev.vars (gitignored), or
export it as an env var.

Usage:
  # Armor of God folder (default)
  python tools/transcribe_groq.py

  # Any other folder
  python tools/transcribe_groq.py --input "C:/path/to/folder"

  # Smoke test first
  python tools/transcribe_groq.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402
from textfmt import paragraphize  # noqa: E402

import requests

REPO = Path(__file__).resolve().parent.parent
DEV_VARS = REPO / ".dev.vars"
HERE = Path(__file__).resolve().parent
TRANSCRIBE_FAILURES = HERE / "transcribe_failures.csv"
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

DEFAULT_INPUT = r"C:\Users\mac\Proton Drive\abereanone\My files\02_Bible-Teaching\Armor of God"

# --- Vocabulary prompt -------------------------------------------------------
# Whisper accepts a prompt that biases spelling toward the words in it. Groq
# caps this prompt at 896 characters, so keep church + speaker + book names
# and pack in as many terms as fit.
PROMPT_CHAR_CAP = 890
CHURCH_NAME = "LaRue Baptist Church"
DEFAULT_SPEAKER = "Michael Coughlin"
KEY_TERMS = [
    "gospel", "grace", "covenant", "righteousness", "justification",
    "sanctification", "propitiation", "atonement", "eschatology",
    "Yahweh", "Messiah", "principalities", "powers", "armor",
]


def build_prompt() -> str:
    head = f"{CHURCH_NAME}. Speaker: {DEFAULT_SPEAKER}. "
    tail = f"Books: {', '.join(scripture.CANONICAL_BOOKS)}."
    room = PROMPT_CHAR_CAP - len(head) - len(tail) - len("Terms: . ")
    picked: list[str] = []
    for t in KEY_TERMS:
        if len(", ".join(picked + [t])) <= room:
            picked.append(t)
        else:
            break
    terms = f"Terms: {', '.join(picked)}. " if picked else ""
    return head + terms + tail


def load_dev_vars() -> dict[str, str]:
    out: dict[str, str] = {}
    if DEV_VARS.exists():
        for line in DEV_VARS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def api_key() -> str:
    key = os.environ.get("GROQ_API_KEY") or load_dev_vars().get("GROQ_API_KEY", "")
    if not key:
        raise SystemExit(f"Missing GROQ_API_KEY — set it as an env var or in {DEV_VARS}")
    return key


def split_chunks(src: Path, work: Path, chunk_seconds: int) -> list[Path]:
    """Re-encode to 16kHz mono and segment into chunk_*.mp3 (small, Whisper-ready)."""
    pattern = str(work / "chunk_%03d.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
         "-c:a", "libmp3lame", "-b:a", "64k",
         "-f", "segment", "-segment_time", str(chunk_seconds), pattern],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return [c for c in sorted(work.glob("chunk_*.mp3")) if c.stat().st_size >= 10240]


def gap_paragraphs(segments: list[dict], gap: float = 2.0) -> str:
    """Join Whisper segments; new paragraph after a pause > gap seconds."""
    out, buf, prev_end = [], [], None
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if prev_end is not None and (seg.get("start", 0) - prev_end) > gap and buf:
            out.append(" ".join(buf)); buf = []
        buf.append(text); prev_end = seg.get("end", prev_end)
    if buf:
        out.append(" ".join(buf))
    return "\n\n".join(out)


def transcribe_chunk(chunk: Path, model: str, key: str, prompt: str, retries: int = 4) -> str:
    data = {"model": model, "response_format": "verbose_json", "language": "en",
             "temperature": "0", "prompt": prompt}
    for attempt in range(retries):
        try:
            with chunk.open("rb") as f:
                resp = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (chunk.name, f, "audio/mpeg")},
                    data=data,
                    timeout=300,
                )
            if resp.status_code == 200:
                body = resp.json()
                segs = body.get("segments") or []
                return gap_paragraphs(segs) if segs else (body.get("text") or "").strip()
            if resp.status_code in (408, 409, 429, 500, 502, 503, 504, 524):
                time.sleep(2 ** attempt * 2)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise RuntimeError(f"{type(e).__name__}: {e}")
            time.sleep(2 ** attempt * 2)
    raise RuntimeError("exhausted retries")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=DEFAULT_INPUT)
    p.add_argument("--model", default="whisper-large-v3")
    p.add_argument("--chunk-seconds", type=int, default=1500)
    p.add_argument("--ext", default="mp3,m4a,wav,flac")
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true", help="list files to transcribe; no API calls")
    args = p.parse_args()

    in_dir = Path(args.input)
    exts = {f".{e.strip().lower().lstrip('.')}" for e in args.ext.split(",")}
    files = sorted(f for f in in_dir.iterdir() if f.is_file() and f.suffix.lower() in exts)
    pending = [f for f in files if not f.with_suffix(".txt").exists()]

    if args.dry_run:
        print(f"DRY RUN — {len(files)} audio files in {in_dir}; "
              f"{len(files) - len(pending)} already have a transcript, {len(pending)} pending.\n")
        for f in pending:
            print(f"  {f.name}  ->  {f.with_suffix('.txt').name}")
        return

    if not pending:
        print(f"Nothing to do — all {len(files)} file(s) in {in_dir} already have a .txt.")
        return

    key = api_key()
    prompt = build_prompt()
    print(f"{len(pending)} file(s) to transcribe via Groq {args.model} in {in_dir}\n")

    failures = []
    for i, src in enumerate(pending, 1):
        out = src.with_suffix(".txt")
        print(f"  [{i}/{len(pending)}] {src.name}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                chunks = split_chunks(src, Path(tmp), args.chunk_seconds)
                parts = []
                for c in chunks:
                    parts.append(transcribe_chunk(c, args.model, key, prompt))
                    if args.delay:
                        time.sleep(args.delay)
            out.with_suffix(".txt.part").write_text(paragraphize("\n\n".join(parts)), encoding="utf-8")
            out.with_suffix(".txt.part").replace(out)
            print(f"      -> {out.name}")
        except Exception as e:
            print(f"      FAIL: {e}")
            failures.append({"file": src.name, "detail": str(e)[:300]})

    if failures:
        with TRANSCRIBE_FAILURES.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "detail"]); w.writeheader(); w.writerows(failures)
        print(f"\n{len(failures)} failed — logged to {TRANSCRIBE_FAILURES.name}; rerun to retry.")
    else:
        print("\nAll done.")


if __name__ == "__main__":
    main()
