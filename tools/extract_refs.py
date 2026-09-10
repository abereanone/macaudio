"""LLM scripture-reference extraction for the sermon index.

The regex parser (scripture.py) only catches explicit "Book Chapter:Verse" and
verse walk-throughs where the book stays put. It misses — and sometimes
mis-attributes — the way preachers actually talk: "verse 26 of Romans 1",
"the fifth chapter of Galatians", "a few verses later Paul says...".

This tool reads each transcript with a Groq LLM and returns a clean, verse-level
list of every passage the preacher actually reads or cites, then writes them to
scripture_refs as the source='llm' transcript references (is_primary=0). It does
NOT touch the primary passage (is_primary=1) — that stays as set by
attach_transcript.py / fix_passage.py.

Only references actually present in the text are kept: results are validated
against the canonical book list and anything the model invents is dropped.

FREE-TIER REALITY (measured 2026-07-28)
---------------------------------------
Groq's free tier caps *tokens per day* per model — llama-3.3-70b-versatile is
100,000 TPD — and caps tokens per minute well below the size of a typical
sermon (avg ~8.4k tokens; TPM is 12k for 70b, 8k for most others). The corpus is
~2.66M tokens, so a single-model run needs ~27 days. This tool therefore:

  * CHUNKS each transcript to fit the current model's TPM, with overlap so a
    verse walk-through isn't broken at a seam (validated: chunked extraction
    reproduced the full-text reference set exactly).
  * POOLS several models, each with its own daily budget, rotating when one is
    exhausted. Note groq/compound* are backed by llama-3.3-70b and share its
    budget, so they are deliberately excluded.
  * WRITES AFTER EVERY ITEM and RESUMES, so a multi-day run never loses work.

Usage:
  # prototype: print refs, write nothing
  python tools/extract_refs.py --remote --dry-run --slug 2021-11-12-self-control
  # full catalog, resumable — rerun daily until it reports 0 remaining
  python tools/extract_refs.py --remote
  # check progress without calling the API
  python tools/extract_refs.py --remote --status
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402
from transcribe_groq import api_key  # noqa: E402

import requests

REPO = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"
CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
CACHE_PATH = REPO / "tools" / ".transcript_cache.json"
PROGRESS_PATH = REPO / "tools" / ".extract_progress.json"

# Models with independent daily budgets, best-first. TPM is discovered at
# runtime from response headers; these are the measured fallbacks.
# groq/compound and groq/compound-mini are EXCLUDED: they proxy to
# llama-3.3-70b-versatile and drain the same TPD pool.
MODEL_POOL = [
    ("llama-3.3-70b-versatile", 12000),
    ("openai/gpt-oss-120b", 8000),
    ("qwen/qwen3.6-27b", 8000),
    ("openai/gpt-oss-20b", 8000),
]

CHARS_PER_TOKEN = 3.4        # measured against these transcripts; 4 overshot TPM
PROMPT_OVERHEAD_TOKENS = 900  # instructions + system + reply headroom
OVERLAP_CHARS = 1200          # keeps verse walk-throughs intact across a seam

SYSTEM = (
    "You extract Bible scripture references from sermon transcripts. You return "
    "only references that are actually present in the given text — you never add "
    "cross-references from your own knowledge."
)

INSTRUCTIONS = f"""\
From the sermon transcript below, list EVERY scripture reference the preacher
reads, quotes, cites, or directs listeners to. Include references spoken in
non-standard ways, for example:
  - "verse 26 of Romans 1"          -> Romans 1:26
  - "the fifth chapter of Galatians" -> Galatians 5
  - "First John chapter 4 verse 8"   -> 1 John 4:8
  - a walk-through where the book is named once and then "verse 5 ... verse 6
    ..." continues in the same chapter -> one ref per verse discussed.

Rules:
- Only include references that are genuinely in the text. If the preacher merely
  alludes to a story with no locatable chapter/verse, skip it. Do NOT invent or
  infer references.
- Resolve a bare "verse N" / "chapter N" to whatever book/chapter is under
  discussion at that point in the transcript. If the excerpt opens with a
  "[context: ...]" note, use it to resolve references before the first named book.
- Book names MUST be exactly one of these canonical names:
  {", ".join(scripture.CANONICAL_BOOKS)}.
  Use "1 John", "2 Peter", etc. for numbered books.
- Merge a contiguous verse span into one ref via verse_end. A single verse has
  verse_end null. A whole chapter with no verse has verse_start and verse_end
  null.
- Deduplicate identical references.

Return ONLY a JSON object of this exact shape (no prose):
{{"refs": [{{"book": "Romans", "chapter": 1, "verse_start": 26, "verse_end": 27}}]}}
"""

_BOOKCHAP_RE = re.compile(
    rf"\b(?P<book>{scripture._BOOK_PATTERN})\.?\s*(?:chapters?\s+)?(?P<chapter>\d{{1,3}})?",
    re.IGNORECASE,
)
_THINK_RE = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ONE_REF_RE = re.compile(
    r'\{[^{}]*?"book"\s*:\s*"[^"]+"[^{}]*?\}', re.DOTALL)


def _balanced_objects(s: str):
    """Yield each top-level {...} span, so a stray brace in prose can't corrupt us."""
    depth = start = 0
    in_str = esc = False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                yield s[start:i + 1]
            elif depth < 0:
                depth = 0


def parse_model_json(content: str) -> list[dict]:
    """Pull the refs array out of whatever the model actually sent.

    Handles: clean JSON, markdown fences, <think> preambles, and responses
    truncated mid-array (salvaged ref-by-ref rather than thrown away).
    """
    if not content:
        raise BadOutput("empty response")
    # Closed <think> blocks go; an unterminated one is left to the brace scanner,
    # which is string-aware and simply skips objects that carry no "refs" key.
    text = _THINK_RE.sub("", content)
    text = re.sub(r"```(?:json)?|```", "", text)

    try:
        return json.loads(text).get("refs", [])
    except (ValueError, AttributeError):
        pass

    for cand in _balanced_objects(text):
        if '"refs"' not in cand:
            continue
        try:
            return json.loads(cand).get("refs", [])
        except ValueError:
            continue

    # Truncated mid-array: recover the complete ref objects that did arrive.
    salvaged = []
    for m in _ONE_REF_RE.finditer(text):
        try:
            salvaged.append(json.loads(m.group(0)))
        except ValueError:
            continue
    if salvaged:
        return salvaged
    raise BadOutput("no parseable refs in response")


try:                          # sermon titles aren't all ASCII; cp1252 would raise
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def log(msg: str = "") -> None:
    """Progress must survive a killed multi-day run — never let it sit in a buffer."""
    print(msg, flush=True)


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def d1_json(command: str, remote: bool) -> list:
    mode = "--remote" if remote else "--local"
    out = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, "--json", "--command", command],
        cwd=REPO, capture_output=True, text=True, shell=WIN, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit(f"d1 query failed:\n{out.stderr or out.stdout}")
    return json.loads(out.stdout[out.stdout.index("["):])


def d1_apply(sql: str, remote: bool) -> bool:
    mode = "--remote" if remote else "--local"
    path = REPO / "tools" / "_extract_refs.sql"
    path.write_text(sql, encoding="utf-8")
    res = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "macaudio", mode, f"--file={path}"],
        cwd=REPO, shell=WIN, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    path.unlink(missing_ok=True)
    if res.returncode != 0:
        log(f"    D1 WRITE FAILED: {(res.stderr or res.stdout)[:300]}")
        return False
    return True


# --------------------------------------------------------------------------
# chunking
# --------------------------------------------------------------------------

def governing_ref(text: str, upto: int) -> str | None:
    """The most recent 'Book [chapter]' named before `upto`, for a chunk breadcrumb."""
    last = None
    for m in _BOOKCHAP_RE.finditer(text, 0, upto):
        canon = scripture._ALIAS.get(m.group("book").lower().rstrip("."))
        if canon:
            last = canon + (f" {m.group('chapter')}" if m.group("chapter") else "")
    return last


def chunk_text(text: str, max_chars: int, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Sequential chunks split on sentence boundaries, overlapped, each carrying a
    breadcrumb naming the book/chapter in play when the chunk starts."""
    if len(text) <= max_chars:
        return [text]
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            bounds = list(re.finditer(r"[.!?]\s", text[start:end]))
            if bounds:
                end = start + bounds[-1].end()
        ctx = governing_ref(text, start) if start else None
        head = f"[context: the preacher is currently in {ctx}]\n" if ctx else ""
        out.append(head + text[start:end])
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return out


# --------------------------------------------------------------------------
# model pool
# --------------------------------------------------------------------------

class Pool:
    """Rotates across models, tracking which have hit their daily cap."""

    def __init__(self, models: list[tuple[str, int]]):
        self.tpm = {m: t for m, t in models}
        self.order = [m for m, _ in models]
        self.exhausted: dict[str, float] = {}   # model -> unix ts when it frees up
        self.idx = 0

    def available(self) -> list[str]:
        now = time.time()
        for m, until in list(self.exhausted.items()):
            if now >= until:
                del self.exhausted[m]
        return [m for m in self.order if m not in self.exhausted]

    def current(self) -> str | None:
        avail = self.available()
        if not avail:
            return None
        self.idx %= len(avail)
        return avail[self.idx]

    def rotate(self) -> None:
        self.idx += 1

    def mark_exhausted(self, model: str, seconds: float) -> None:
        if model in self.tpm:
            self.exhausted[model] = time.time() + seconds
            log(f"    -> {model} daily cap reached; back in {seconds/3600:.1f}h")

    def soonest_reset(self) -> float | None:
        return min(self.exhausted.values()) if self.exhausted else None


_MODEL_IN_ERROR = re.compile(r"for model `([^`]+)`")


def call_groq(text: str, model: str, key: str, pool: Pool, max_wait: float,
              strict_json: bool = True) -> list[dict]:
    """One extraction call. Raises Exhausted when the model's daily cap is hit."""
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": INSTRUCTIONS + "\n\n--- TRANSCRIPT ---\n" + text},
        ],
    }
    if strict_json:
        body["response_format"] = {"type": "json_object"}
    if "gpt-oss" in model:
        # Reasoning tokens bill against the same daily cap and can crowd the
        # JSON out of the completion entirely. We need extraction, not analysis.
        body["reasoning_effort"] = "low"
        body["max_completion_tokens"] = 8000
    for attempt in range(6):
        try:
            r = requests.post(CHAT_URL, headers={"Authorization": f"Bearer {key}"},
                              json=body, timeout=300)
        except requests.RequestException as e:
            if attempt == 5:
                raise RuntimeError(f"{type(e).__name__}: {e}")
            time.sleep(2 ** attempt * 2)
            continue

        if r.status_code == 200:
            # A model's real TPM ceiling, straight from the response.
            lim = r.headers.get("x-ratelimit-limit-tokens")
            if lim and lim.isdigit():
                pool.tpm[model] = int(lim)
            return parse_model_json(r.json()["choices"][0]["message"].get("content"))

        msg = ""
        try:
            msg = r.json().get("error", {}).get("message", "")
        except ValueError:
            msg = r.text[:200]

        if r.status_code == 429:
            # The message names the model that actually hit the wall, which for
            # proxied models is NOT the one we asked for.
            named = _MODEL_IN_ERROR.search(msg)
            blamed = named.group(1) if named else model
            wait = float(r.headers.get("retry-after", 0) or 0)
            if "per day" in msg or "TPD" in msg or wait > max_wait:
                raise Exhausted(blamed, wait or 6 * 3600)
            log(f"    TPM limit, waiting {wait or 30:.0f}s")
            time.sleep((wait or 30) + 1)
            continue

        if r.status_code == 413:
            raise TooLarge(msg)

        if r.status_code == 400 and "JSON" in msg:
            # Some models choke on strict json_object mode. Retry once in prose
            # mode — the 200 path already digs JSON out of surrounding text.
            if strict_json:
                log("    strict JSON rejected; retrying in prose mode")
                return call_groq(text, model, key, pool, max_wait, strict_json=False)
            raise BadOutput(msg)

        if r.status_code in (408, 409, 500, 502, 503, 504, 524):
            time.sleep(2 ** attempt * 2)
            continue

        raise RuntimeError(f"HTTP {r.status_code}: {msg[:200]}")
    raise RuntimeError("exhausted retries")


class Exhausted(Exception):
    def __init__(self, model: str, seconds: float):
        super().__init__(f"{model} daily cap")
        self.model, self.seconds = model, seconds


class TooLarge(Exception):
    pass


class BadOutput(Exception):
    """This model won't produce usable JSON for this text — try another."""


# --------------------------------------------------------------------------

def clean_refs(raw: list[dict]) -> list[dict]:
    """Validate against canonical books; coerce ints; dedup; canonical ref_text."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for r in raw:
        if not isinstance(r, dict):
            continue
        canon = scripture._ALIAS.get(str(r.get("book", "")).strip().lower().rstrip("."))
        if not canon:
            continue
        try:
            chapter = int(r["chapter"]) if r.get("chapter") not in (None, "") else None
        except (ValueError, TypeError, KeyError):
            continue
        if chapter is None:
            continue

        def _int(x):
            try:
                return int(x) if x not in (None, "") else None
            except (ValueError, TypeError):
                return None
        vs, ve = _int(r.get("verse_start")), _int(r.get("verse_end"))
        if ve is not None and vs is not None and ve < vs:
            vs, ve = ve, vs
        if ve is not None and ve == vs:
            ve = None   # models like to emit 3:3-3; that's just 3:3
        key = (canon, chapter, vs, ve)
        if key in seen:
            continue
        seen.add(key)
        ref = {"book": canon, "chapter": chapter, "verse_start": vs, "verse_end": ve}
        ref["ref_text"] = scripture.format_ref(ref)
        out.append(ref)
    out.sort(key=lambda r: (scripture.CANONICAL_BOOKS.index(r["book"]), r["chapter"] or 0,
                            r["verse_start"] or 0))
    return out


def write_sql(item_id: int, refs: list[dict]) -> str:
    """Replace this item's transcript-level refs with the LLM set.

    Only clears existing rows when there is something to put back, so a bad or
    empty model response can never destroy the regex-derived refs.
    """
    if not refs:
        return ""
    lines = [f"DELETE FROM scripture_refs WHERE item_id={item_id} AND is_primary=0;"]
    for r in refs:
        lines.append(
            "INSERT INTO scripture_refs (item_id, book, chapter, verse_start, verse_end, is_primary, ref_text, source) "
            f"VALUES ({item_id}, {q(r['book'])}, {q(r['chapter'])}, {q(r['verse_start'])}, "
            f"{q(r['verse_end'])}, 0, {q(r['ref_text'])}, 'llm');"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# corpus + progress
# --------------------------------------------------------------------------

def load_corpus(remote: bool, refresh: bool) -> list[dict]:
    if CACHE_PATH.exists() and not refresh:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    log("fetching transcripts from D1 ...")
    sql = ("SELECT i.id, i.slug, i.title, t.text FROM items i "
           "JOIN item_transcripts t ON t.item_id=i.id ORDER BY i.id")
    rows = d1_json(sql, remote)[0]["results"]
    CACHE_PATH.write_text(json.dumps(rows), encoding="utf-8")
    log(f"  cached {len(rows)} transcripts -> {CACHE_PATH.name}")
    return rows


def load_done(remote: bool) -> set[int]:
    """Completed items: anything already carrying llm refs in D1, plus the local
    ledger (which also remembers items that legitimately produced zero refs)."""
    done: set[int] = set()
    try:
        rows = d1_json("SELECT DISTINCT item_id FROM scripture_refs WHERE source='llm'", remote)
        done |= {int(r["item_id"]) for r in rows[0]["results"]}
    except SystemExit:
        raise
    except Exception as e:
        log(f"  (could not read llm refs from D1: {e})")
    if PROGRESS_PATH.exists():
        try:
            done |= set(json.loads(PROGRESS_PATH.read_text(encoding="utf-8")).get("done", []))
        except (ValueError, OSError):
            pass
    return done


def save_done(done: set[int]) -> None:
    PROGRESS_PATH.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")


# --------------------------------------------------------------------------

def process_item(row: dict, pool: Pool, key: str, max_wait: float) -> list[dict] | None:
    """Extract refs for one sermon, chunking to fit whichever model is available.
    Returns None if every model is exhausted (caller should stop)."""
    text = row["text"] or ""
    merged: list[dict] = []
    seen: set[tuple] = set()
    failed: set[str] = set()   # models that produced nothing usable for this item
    shrink = 1.0

    while True:
        model = pool.current()
        if model is None:
            return None
        avail = set(pool.available())
        if avail and failed >= avail:
            raise RuntimeError(f"every available model failed on this item ({sorted(failed)})")
        budget_tokens = max(pool.tpm.get(model, 6000) - PROMPT_OVERHEAD_TOKENS, 1000)
        max_chars = int(budget_tokens * CHARS_PER_TOKEN * shrink)
        pieces = chunk_text(text, max_chars)
        log(f"    model={model}  {len(pieces)} chunk(s)")
        try:
            for n, piece in enumerate(pieces, 1):
                refs = clean_refs(call_groq(piece, model, key, pool, max_wait))
                for r in refs:
                    k = (r["book"], r["chapter"], r["verse_start"], r["verse_end"])
                    if k not in seen:
                        seen.add(k)
                        merged.append(r)
                if n < len(pieces):
                    time.sleep(1)
            merged.sort(key=lambda r: (scripture.CANONICAL_BOOKS.index(r["book"]),
                                       r["chapter"] or 0, r["verse_start"] or 0))
            return merged
        except Exhausted as e:
            pool.mark_exhausted(e.model, e.seconds)
            merged, seen = [], set()   # restart this item cleanly on the next model
            continue
        except TooLarge:
            merged, seen = [], set()
            if shrink > 0.45:
                # Our char-per-token estimate was optimistic for this text —
                # shrink and stay on this model rather than give up its budget.
                shrink *= 0.7
                log(f"    chunk over TPM; retrying at {shrink:.0%} chunk size")
            else:
                log("    chunk still too large; rotating")
                failed.add(model)
                pool.rotate()
                shrink = 1.0
            continue
        except BadOutput as e:
            log(f"    unusable output from {model} ({e}); rotating")
            failed.add(model)
            pool.rotate()
            shrink = 1.0
            merged, seen = [], set()
            continue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", default=[], help="limit to slug(s); repeatable")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", help="force a single model instead of the pool")
    ap.add_argument("--remote", action="store_true", help="read/write prod D1 (default: local)")
    ap.add_argument("--dry-run", action="store_true", help="print refs, write nothing")
    ap.add_argument("--status", action="store_true", help="report progress and exit")
    ap.add_argument("--refresh", action="store_true", help="re-fetch transcripts from D1")
    ap.add_argument("--redo", action="store_true", help="ignore progress and reprocess")
    ap.add_argument("--delay", type=float, default=1.0, help="pause between items")
    ap.add_argument("--max-wait", type=float, default=300,
                    help="a 429 asking for longer than this counts as a daily cap")
    a = ap.parse_args()

    rows = load_corpus(a.remote, a.refresh)
    if a.slug:
        rows = [r for r in rows if r["slug"] in set(a.slug)]
    done = set() if (a.redo or a.dry_run) else load_done(a.remote)
    todo = [r for r in rows if r["id"] not in done]
    if a.limit:
        todo = todo[:a.limit]

    log(f"corpus {len(rows)} | done {len(done)} | remaining {len(rows) - len(done)}")
    if a.status:
        chars = sum(len(r["text"] or "") for r in rows if r["id"] not in done)
        toks = int(chars / CHARS_PER_TOKEN)
        log(f"~{toks:,} tokens of work left "
            f"(~{toks // 500_000 + 1} day(s) at ~500k/day pooled)")
        return
    if not todo:
        log("nothing to do — extraction is complete.")
        return

    key = api_key()
    models = [(a.model, 8000)] if a.model else MODEL_POOL
    pool = Pool(models)
    log(f"processing {len(todo)} item(s) across {len(models)} model(s)\n")

    ok = failed = 0
    for i, row in enumerate(todo, 1):
        log(f"[{i}/{len(todo)}] {row['title']}  [{row['slug']}]  {len(row['text'] or ''):,} chars")
        try:
            refs = process_item(row, pool, key, a.max_wait)
        except Exception as e:
            log(f"    FAIL: {type(e).__name__}: {e}")
            failed += 1
            continue

        if refs is None:
            reset = pool.soonest_reset()
            log("\nAll models have hit their daily cap.")
            if reset:
                log(f"Earliest reset: {time.strftime('%Y-%m-%d %H:%M', time.localtime(reset))}")
            log(f"Progress saved — {ok} item(s) written this session. "
                "Rerun the same command to resume.")
            break

        log(f"    {len(refs)} refs: " + ", ".join(r["ref_text"] for r in refs[:24])
            + (" ..." if len(refs) > 24 else ""))

        if a.dry_run:
            continue

        sql = write_sql(row["id"], refs)
        if sql and not d1_apply(sql, a.remote):
            failed += 1
            continue
        # Durable after every single item: a kill here loses at most one sermon.
        done.add(row["id"])
        save_done(done)
        ok += 1
        if a.delay:
            time.sleep(a.delay)

    log(f"\nwritten this session: {ok} | failed: {failed} | "
        f"remaining overall: {len(rows) - len(done)}")
    if failed:
        log("rerun the same command to retry failures.")


if __name__ == "__main__":
    main()
