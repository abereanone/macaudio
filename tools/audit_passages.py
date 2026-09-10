"""Audit primary passages against transcript content.

attach_transcript.py sets an item's primary passage to the FIRST scripture ref
in its transcript. That is wrong whenever a sermon opens with a call-to-worship
or illustration verse before reaching its real text. This tool flags likely
mis-detections so they can be reviewed by hand (then fixed with fix_passage.py).

For each transcribed item it counts every scripture ref in the transcript and
compares the stored passage_ref against the most-cited book (and book+chapter).
It reports items where:
  * the stored book is NOT the transcript's dominant book, or
  * the stored book/chapter is cited far less than the dominant book/chapter.

Heuristic, not authoritative: skim the list and judge each. Sort is by how
lopsided the mismatch is (most suspicious first).

Usage:
  python tools/audit_passages.py --remote            # human-readable report
  python tools/audit_passages.py --remote --csv out.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"


def fetch_all(remote: bool) -> list[dict]:
    mode = "--remote" if remote else "--local"
    sql = ("SELECT i.id, i.slug, i.title, i.passage_ref, t.text "
           "FROM items i JOIN item_transcripts t ON t.item_id=i.id "
           "ORDER BY i.id")
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, "--json", "--command", sql],
        cwd=REPO, capture_output=True, text=True, shell=WIN, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit(f"d1 query failed:\n{out.stderr or out.stdout}")
    return json.loads(out.stdout[out.stdout.index("["):])[0]["results"]


def analyze(row: dict) -> dict | None:
    """Return an audit record for a row, or None if nothing looks off."""
    text = row.get("text") or ""
    refs = scripture.parse_refs(text, unique=False)
    if not refs:
        return None

    book_counts = Counter(r["book"] for r in refs)
    chap_counts = Counter((r["book"], r["chapter"]) for r in refs if r["chapter"])
    dom_book, dom_book_n = book_counts.most_common(1)[0]
    dom_chap, dom_chap_n = (chap_counts.most_common(1)[0] if chap_counts else ((None, None), 0))

    stored = scripture.parse_refs(row.get("passage_ref") or "")
    stored_book = stored[0]["book"] if stored else None
    stored_chap = stored[0].get("chapter") if stored else None

    stored_book_n = book_counts.get(stored_book, 0)
    stored_chap_n = chap_counts.get((stored_book, stored_chap), 0)

    # Flag when the stored book isn't the dominant one, or the stored book+chapter
    # is cited noticeably less than the dominant book+chapter.
    book_mismatch = stored_book != dom_book
    chap_weak = dom_chap[0] and (stored_book, stored_chap) != dom_chap and stored_chap_n * 2 < dom_chap_n
    if not (book_mismatch or chap_weak):
        return None

    # suspicion score: how much more the dominant text is cited than the stored one
    score = (dom_book_n - stored_book_n) + (dom_chap_n - stored_chap_n)
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "stored": row.get("passage_ref") or "",
        "stored_cites": stored_book_n,
        "dominant_book": dom_book,
        "dominant_book_cites": dom_book_n,
        "dominant_chapter": f"{dom_chap[0]} {dom_chap[1]}" if dom_chap[0] else "",
        "dominant_chapter_cites": dom_chap_n,
        "score": score,
        "book_mismatch": book_mismatch,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", action="store_true")
    ap.add_argument("--csv", help="also write full report to this CSV")
    a = ap.parse_args()

    rows = fetch_all(a.remote)
    flagged = [r for r in (analyze(x) for x in rows) if r]
    flagged.sort(key=lambda r: (-r["score"], r["slug"]))

    print(f"\n{len(rows)} transcribed items; {len(flagged)} flagged as possibly mis-detected.\n")
    print(f"{'stored passage':<22} {'dominant book':<16} {'dominant chapter':<18} title")
    print("-" * 100)
    for r in flagged:
        star = "**" if r["book_mismatch"] else "  "
        print(f"{star}{r['stored']:<20} "
              f"{r['dominant_book']+' ('+str(r['dominant_book_cites'])+')':<16} "
              f"{r['dominant_chapter']+' ('+str(r['dominant_chapter_cites'])+')':<18} "
              f"{r['title']}  [{r['slug']}]")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(flagged[0].keys()) if flagged else
                               ["id", "slug", "title", "stored", "dominant_book", "dominant_chapter", "score"])
            w.writeheader()
            w.writerows(flagged)
        print(f"\nFull report -> {a.csv}")
    print("\n** = stored book differs from the transcript's most-cited book (strongest signal).")
    print("Review each, then correct with:  python tools/fix_passage.py --remote --slug <slug> --passage \"<ref>\"")


if __name__ == "__main__":
    main()
