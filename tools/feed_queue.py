"""Queue catalog items for the published podcast feeds, and release them one at a time.

The feeds in C:/code/feeds are live and have subscribers. A feed publishes
whatever is in the file, so adding seven episodes and pushing would drop seven
downloads on everyone at once. Work is therefore done in two steps:

  queue    build the <item> block now, into the gitignored queue file
  --next   move ONE queued block into its real feed, ready to commit and push

The queue sits in C:/code/feeds but is GITIGNORED there. Cloudflare Pages
deploys from the repository, so an untracked file never reaches the web -- the
queue stays beside the feeds without being published with them.

Feeds are edited as TEXT, never parsed and re-serialised -- an ElementTree
round-trip would reformat every existing entry and churn the whole file. The
<guid> is the enclosure URL, matching the existing entries; podcast apps key on
it, so an existing episode's URL must never change.

Usage:
  python tools/feed_queue.py --slug SLUG [--feed mcassortedsermons.xml]
  python tools/feed_queue.py --list
  python tools/feed_queue.py --next            # release one
  python tools/feed_queue.py --next --count 2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from transcribe_groq import load_dev_vars  # noqa: E402

WIN = sys.platform == "win32"
DB = "macaudio"
FEEDS_DIR = Path(r"C:\code\feeds")
# Lives in the feeds repo for convenience, but gitignored there: Pages deploys
# from the repo, so an untracked file is never published.
PENDING = FEEDS_DIR / "feed_pending.xml"
DEFAULT_FEED = "mcassortedsermons.xml"
MEDIA_BASE = "https://audio.michaelcoughlin.net"

LF = "\n"
CRLF = "\r\n"

START = "<!-- QUEUED feed={feed} slug={slug} -->"
START_RE = re.compile(
    r"<!-- QUEUED feed=(?P<feed>\S+) slug=(?P<slug>\S+) -->\n(?P<body>.*?)<!-- /QUEUED -->\n",
    re.DOTALL)
END = "<!-- /QUEUED -->"


def read_keep_newlines(path: Path) -> tuple[str, str]:
    """Read a file without translating newlines, and report which kind it uses.

    Python's default text IO rewrites LF as CRLF on Windows. Doing that to a
    feed turned a one-episode addition into a 461-line diff -- every existing
    entry rewritten. These files are LF; preserve whatever they already are."""
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    bare_lf = raw.count(b"\n") - crlf
    return raw.decode("utf-8"), (CRLF if crlf > bare_lf else LF)


def write_keep_newlines(path: Path, text: str, nl: str) -> None:
    flat = text.replace(CRLF, LF)
    path.write_bytes((flat if nl == LF else flat.replace(LF, CRLF)).encode("utf-8"))


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


def esc(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rfc2822(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            .strftime("%a, %d %b %Y %H:%M:%S GMT"))


def hms(sec: int) -> str:
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def read_pending() -> str:
    if PENDING.exists():
        return PENDING.read_bytes().decode("utf-8").replace(CRLF, LF)
    return ("<!-- Queued podcast entries. NOT a feed and not served.\n"
            "     Release one with: python tools/feed_queue.py --next -->\n")


def write_pending(text: str) -> None:
    PENDING.write_bytes(text.replace(CRLF, LF).encode("utf-8"))


def cmd_queue(a) -> None:
    found = rows(
        "SELECT i.slug, i.title, i.description, i.recorded_on, i.duration_sec, i.r2_key "
        f"FROM items i WHERE i.slug='{a.slug}'")
    if not found:
        sys.exit(f"No item with slug {a.slug}")
    it = found[0]
    if not it.get("r2_key") and not a.url:
        sys.exit(f"{a.slug} has no audio yet -- run tools/add_audio.py first.")

    feed_name = a.feed or DEFAULT_FEED
    feed = FEEDS_DIR / feed_name
    if not feed.exists():
        sys.exit(f"No such feed: {feed}")

    url = a.url or f"{MEDIA_BASE}/{it['r2_key']}"
    pending = read_pending()
    if url in pending:
        print(f"  already queued: {it['title']}")
        return
    if url in read_keep_newlines(feed)[0]:
        print(f"  already published in {feed_name}: {it['title']}")
        return

    # length is the real byte count -- podcast clients show it as the download size
    try:
        head = requests.head(url, allow_redirects=True, timeout=30)
        length = int(head.headers.get("content-length") or 0)
    except Exception as e:
        sys.exit(f"Could not reach {url}: {type(e).__name__}")
    if not length:
        sys.exit(f"{url} returned no content-length -- is the audio uploaded?")

    desc = a.description or it.get("description") or it["title"]
    block = (
        "\t\t<item>\n"
        f"\t\t\t<title>{esc(it['title'])}</title>\n"
        f"\t\t\t<description>{esc(desc)}</description>\n"
        f'\t\t\t<enclosure url="{esc(url)}" type="audio/mpeg" length="{length}"/>\n'
        f"\t\t\t<itunes:duration>{hms(int(it.get('duration_sec') or 0))}</itunes:duration>\n"
        f"\t\t\t<guid>{esc(url)}</guid>\n"
        f"\t\t\t<pubDate>{rfc2822(it['recorded_on'])}</pubDate>\n"
        f"\t\t\t<link>{esc(url)}</link>\n"
        "\t\t</item>\n"
    )
    write_pending(pending + START.format(feed=feed_name, slug=a.slug) + "\n" + block + END + "\n")
    print(f"  queued for {feed_name}: {it['title']}  ({length/1048576:.0f} MB, "
          f"{hms(int(it.get('duration_sec') or 0))})")


def cmd_list(_a) -> None:
    items = list(START_RE.finditer(read_pending()))
    if not items:
        print("  queue is empty.")
        return
    print(f"  {len(items)} queued:\n")
    for i, m in enumerate(items, 1):
        title = re.search(r"<title>(.*?)</title>", m.group("body"))
        print(f"    {i}. [{m.group('feed')}] {title.group(1) if title else m.group('slug')}")
    print("\n  release the next with: python tools/feed_queue.py --next")


def cmd_next(a) -> None:
    pending = read_pending()
    released = 0
    for _ in range(max(1, a.count)):
        m = START_RE.search(pending)
        if not m:
            print("  queue is now empty." if released else "  queue is empty.")
            break
        feed = FEEDS_DIR / m.group("feed")
        if not feed.exists():
            sys.exit(f"No such feed: {feed}")
        block = m.group("body")
        xml, nl = read_keep_newlines(feed)
        flat = xml.replace(CRLF, LF)

        idx = flat.rfind("</item>")
        if idx != -1:
            cut = flat.index("\n", idx) + 1
        else:
            cut = flat.rfind("\t</channel>")
            if cut == -1:
                cut = flat.rfind("</channel>")
            if cut == -1:
                sys.exit(f"{feed.name}: found neither </item> nor </channel>.")
        flat = flat[:cut] + block + flat[cut:]

        stamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        flat, n = re.subn(r"<lastBuildDate>.*?</lastBuildDate>",
                          f"<lastBuildDate>{stamp}</lastBuildDate>", flat, count=1)
        if not n:
            print(f"  NOTE: {feed.name} has no <lastBuildDate> to update.")

        title = re.search(r"<title>(.*?)</title>", block)
        label = title.group(1) if title else m.group("slug")
        if a.dry_run:
            print(f"  would release -> {feed.name}: {label}")
        else:
            write_keep_newlines(feed, flat, nl)
            pending = pending[:m.start()] + pending[m.end():]
            write_pending(pending)
            print(f"  released -> {feed.name}: {label}")
        released += 1

    if released and not a.dry_run:
        print('\n  now: cd /c/code/feeds && git add -A && git commit -m "add episode" && git push')


def main() -> None:
    p = argparse.ArgumentParser(description="Queue and release podcast feed entries.")
    p.add_argument("--slug")
    p.add_argument("--feed", default=None, help=f"target feed (default {DEFAULT_FEED})")
    p.add_argument("--url", default=None, help="enclosure URL (default: the R2 copy)")
    p.add_argument("--description", default=None)
    p.add_argument("--list", action="store_true")
    p.add_argument("--next", action="store_true", help="release queued entries into their feeds")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.list:
        cmd_list(a)
    elif a.next:
        cmd_next(a)
    elif a.slug:
        cmd_queue(a)
    else:
        p.error("need --slug, --list or --next")


if __name__ == "__main__":
    main()
