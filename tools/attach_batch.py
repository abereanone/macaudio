"""Attach many files to many items in one pass, from a manifest.

attach_extras.py handles one item per invocation, which is right when you are
hanging an outline off a message you just published. It is the wrong shape for
a back-catalogue sweep: a folder of years of notes matched to slugs by hand,
then twenty near-identical commands typed one at a time.

This reads a TSV and does the sweep. Each row is:

    slug <TAB> kind <TAB> title <TAB> source path

Blank lines and lines starting with '#' are ignored. Rows are grouped by
(slug, kind) because attach_extras takes one --kind for all its --notes, then
handed off to it verbatim — so the R2 key convention, the upsert on r2_key, the
MIME table and the credential loading all stay in exactly one place.

Usage:
  python tools/attach_batch.py tools/attachments.tsv --remote --dry-run
  python tools/attach_batch.py tools/attachments.tsv --remote

Re-running is safe: attach_extras upserts on r2_key, so a corrected file
re-uploaded under the same name replaces its row instead of duplicating it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRAS = HERE / "attach_extras.py"


def read_manifest(path: Path) -> list[tuple[str, str, str, Path]]:
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            sys.exit(f"{path}:{n}: need 4 tab-separated fields, got {len(parts)}")
        slug, kind, title, src = (p.strip() for p in parts)
        # A ':' in the title would be eaten by attach_extras' PATH:Title split.
        if ":" in title:
            sys.exit(f"{path}:{n}: title may not contain ':' ({title!r})")
        p = Path(src)
        if not p.exists():
            sys.exit(f"{path}:{n}: file not found: {src}")
        out.append((slug, kind, title, p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Bulk-attach files from a TSV manifest.")
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--remote", action="store_true", help="production D1 + R2 (default: local)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = read_manifest(a.manifest)
    groups: OrderedDict[tuple[str, str], list[tuple[str, Path]]] = OrderedDict()
    for slug, kind, title, src in rows:
        groups.setdefault((slug, kind), []).append((title, src))

    print(f"{len(rows)} file(s) across {len({s for s, _ in groups})} item(s), "
          f"{len(groups)} call(s) to attach_extras\n")

    failed = []
    for (slug, kind), files in groups.items():
        cmd = [sys.executable, str(EXTRAS), "--slug", slug, "--kind", kind]
        for title, src in files:
            cmd += ["--notes", f"{src}:{title}"]
        if a.remote:
            cmd.append("--remote")
        if a.dry_run:
            cmd.append("--dry-run")
        print(f"--- {slug}  [{kind}]  {len(files)} file(s)")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            failed.append((slug, kind))
            print(f"    FAILED (exit {r.returncode})")
        print()

    if failed:
        print("Failed groups:")
        for slug, kind in failed:
            print(f"  {slug} [{kind}]")
        sys.exit(1)
    print("All groups attached.")


if __name__ == "__main__":
    main()
