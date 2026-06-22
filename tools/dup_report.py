"""Find likely duplicate audio across the feeds (c:\\code\\feeds) and the local
source folders. Read-only report — changes nothing."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from collections import defaultdict

FEEDS = Path(r"C:/code/feeds")
PROTON = Path(r"C:/Users/mac/Proton Drive/abereanone/My files")
BT = PROTON / "02_Bible-Teaching"
SOURCES = [BT / "CBC Sermons", BT / "BEABEREAN", BT / "Open Airs", PROTON / "rawdio" / "lbc"]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def feed_items():
    rows = []
    for fx in sorted(FEEDS.glob("*.xml")):
        x = fx.read_text(encoding="utf-8", errors="replace")
        for it in re.findall(r"<item>(.*?)</item>", x, re.S):
            t = re.search(r"<title>(.*?)</title>", it, re.S)
            e = re.search(r'<enclosure[^>]*url="([^"]+)"', it)
            url = e.group(1) if e else ""
            rows.append({"feed": fx.name, "title": (t.group(1).strip() if t else ""),
                         "url": url, "base": url.rsplit("/", 1)[-1]})
    return rows


def tags(p: Path) -> dict:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags",
                              "-of", "default=noprint_wrappers=1", str(p)],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        out = ""
    d = {}
    for line in out.splitlines():
        if line.startswith("TAG:") and "=" in line:
            k, v = line[4:].split("=", 1)
            d[k.strip().lower()] = v.strip()
    return d


def main():
    print("=" * 70)
    print("1) SAME MP3 REFERENCED BY MULTIPLE FEEDS")
    feeds = feed_items()
    by_base = defaultdict(set)
    for r in feeds:
        if r["base"]:
            by_base[r["base"]].add(r["feed"])
    dup_feeds = {b: fs for b, fs in by_base.items() if len(fs) > 1}
    if dup_feeds:
        for b, fs in sorted(dup_feeds.items()):
            print(f"  {b}  →  {', '.join(sorted(fs))}")
    else:
        print("  (none)")
    print(f"  [feeds: {len(set(r['feed'] for r in feeds))}, episodes: {len(feeds)}]")

    print("=" * 70)
    print("2) LOCAL AUDIO: same filename in more than one folder")
    local = []
    for src in SOURCES:
        if src.exists():
            for f in src.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".mp3", ".m4a", ".wav"}:
                    local.append(f)
    by_name = defaultdict(list)
    for f in local:
        by_name[f.name.lower()].append(f)
    for n, fs in sorted(by_name.items()):
        if len(fs) > 1:
            for f in fs:
                print(f"  {f}")
            print()

    print("=" * 70)
    print("3) LOCAL 'Processed' / raw pairs in CBC Sermons (same stem)")
    stems = {f.stem.lower(): f for f in local}
    for f in local:
        s = f.stem.lower()
        if s.endswith("processed"):
            base = s[: -len("processed")].strip()
            if base in stems:
                print(f"  {stems[base].name}  ==  {f.name}")

    print("=" * 70)
    print("4) SAME RECORDING ACROSS FOLDERS (by ID3 title + year) — CBC vs BEABEREAN etc.")
    print("    (reading tags; may take a moment)")
    info = []
    for f in local:
        if "CBC Sermons" in str(f) or "BEABEREAN" in str(f):
            t = tags(f)
            key = (norm(t.get("title", "")), (t.get("date", "") or "")[-4:])
            if t.get("title"):
                info.append((key, f, t))
    groups = defaultdict(list)
    for key, f, t in info:
        if key[0]:
            groups[key].append((f, t))
    found = False
    for key, items in sorted(groups.items()):
        if len(items) > 1:
            found = True
            print(f"  ── same title+year ({len(items)} copies):")
            for f, t in items:
                print(f"     {t.get('title','?')} | album={t.get('album','')} | {t.get('date','')} | {f.parent.name}/{f.name}")
            print()
    if not found:
        print("  (no cross-folder ID3 title+year matches)")


if __name__ == "__main__":
    main()
