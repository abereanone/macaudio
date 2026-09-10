# Putting the sermon archive on YouTube

Working notes for the video pipeline. Written 2026-09-10 to hand off between
conversations — read this before changing `tools/make_video.py` or
`tools/make_thumb.mjs`.

## The goal

Generate a video for **every catalog item that has audio but no video**, and
upload them to the channel by hand, a couple at a time. No deadline.

Scope, measured against production D1:

| | |
|---|---|
| Items with audio and no `video_url` | **233** |
| Total runtime | **160 hours** (avg 41 min) |
| Source MP3s already on this PC | 232 of 233 |
| The one exception | `2026-08-09-union-with-christ-part-1` — `source_path` points at a file that's gone; `make_video.py` falls back to pulling it from R2 |

## What exists now

**`tools/make_video.py --slug SLUG`** — renders one item to `.video/out/`:

- `<slug>.mp4` — the upload
- `<slug>.png` — 1280x720 thumbnail, also used as the video's title card
- `<slug>.txt` — title and description to paste into YouTube

Measured on a 35-minute sermon: **67 seconds, 37 MB**. Whole library ≈ 5 hours
and ~10 GB.

**`tools/make_thumb.mjs`** — the card generator. Reuses the palette, waveform
mark and type of `tools/make_brand.mjs`, so a YouTube search result reads as the
same brand as the site's OG card. Handles one-word and 47-character titles.
`--overlay` produces a transparent version with a dark scrim, for compositing
over footage. Nothing calls `--overlay` yet.

`.video/` is gitignored — loops, MP4s and thumbnails are large and regenerable.

## Decisions already made, and why

**The video is the sermon's own title card, held.** Not an abstract background.
A viewer landing mid-video sees the title, passage, series and date. The first
attempt used a flat green gradient loop; it looked like nothing and cost *more*.

**Card spec: 20 seconds at 10fps with a matching 200-frame GOP.** This is the
whole trick. A held still costs **18 kbps** at these settings but **122 kbps**
at 2-second GOPs, because every loop restart is an I-frame — 5 MB per sermon
versus 31 MB. Measured across four settings before choosing.

**The card is encoded once, then stream-copied.** `-stream_loop -1` plus
`-c:v copy` means the video side of a 35-minute sermon costs ~0.3s. Run time is
set entirely by the audio pass (~34x realtime).

**Audio is re-encoded to AAC so loudnorm can run.** The corpus spans 15 years of
different rooms and recorders; without normalising, listeners ride the volume
knob between sermons. Target -14 LUFS, which is YouTube's own, so YouTube leaves
it alone. Measured on the first render: **-18.3 → -15.6 LUFS**, true peak pulled
from **-0.28 → -4.16 dBTP**.

**`-shortest` is NOT frame-accurate against a stream-copied video.** It flushed
7.3 seconds of card past the end of the audio. The render is capped with an
explicit `-t` from the audio's probed duration, then verified against
`items.duration_sec` before the tool reports success. Do not reintroduce
`-shortest` here.

**Uploads are manual.** The YouTube Data API is *not* the blocker people expect:
`videos.insert` costs 1 unit from its own bucket, 100 uploads/day. The blocker is
that **uploads from an unaudited API project are locked to private, permanently,
with no appeal** — the owner cannot flip them public in Studio. Passing Google's
audit is the only remedy, and the audit targets services with users, not one
person uploading their own sermons. Manual upload sidesteps this entirely, and
suits the "a couple at a time" pace anyway.

## Open questions

**1. Does the title stay on screen the whole time?** This is the only real fork
left.

| | Text throughout | Text on thumbnail only |
|---|---|---|
| Video | re-encoded per sermon | montage stream-copied, shared |
| Per sermon | ~2–3 min (NVENC) | ~1 min, audio-bound |
| Library | one overnight batch | ~5 hours |

A middle option exists: title card for the first 30 seconds, then fade into
pure footage — an encoded intro concatenated onto a copied body, which keeps
copy speed for ~95% of the file.

**2. Footage.** Nothing sourced yet. Free and licence-clean: Pexels Videos,
Pixabay, Coverr, Mixkit — check each clip's licence individually. Want dark,
low-contrast, slow, no cuts, no people/text/logos, 10–20s, 1080p. Strip the
audio (`-an`): stock clips often carry a music bed that trips Content ID.
Drop raw downloads in `.video/source/`.

**3. One scene or many?** Rather than looping a single clip, assemble a montage
per category (several scenes with crossfades, a few minutes long), encoded once
and reused across every sermon in that category.

**4. Light or dark text — decide automatically.** Measure the average brightness
of the region where the text actually sits and pick the palette from it. No flag.
Note that footage brightness *changes over time*, so a light treatment still
needs a pale scrim or the text vanishes when a cloud moves.

## Still to build

- **Batch runner with a state file** — which have MP4s, which are uploaded, which
  have `video_url` written back. Same pattern as the existing `uploaded_r2.log`.
  This is what makes a-couple-a-day survivable over weeks.
- **Footage prep tool** — scale to 720p, trim, strip audio, ping-pong
  (`split` → `reverse` → `concat`, which makes *any* clip loop seamlessly), and
  encode to the spec the renderer expects.
- **Write the URL back.** After upload, `tools/attach_extras.py --slug SLUG
  --video URL --remote` fills `items.video_url`, and the sermon page grows its
  video button automatically.

## Metadata plan

| Field | Source |
|---|---|
| Title | `items.title`, plus series and part when present (YouTube caps at 100 chars) |
| Description | passage, series, date, and a link back to `teaching.michaelcoughlin.net/listen/<slug>` |
| Playlist | `collections.title` — 1 Peter, Hebrews, Ten Commandments map straight across |
| Captions | **YouTube auto-syncs a plain transcript with no timings.** Most items already have one. No SRT work needed. |

## Context worth knowing

The channel is **@wpuymac — 77 subscribers, 73 videos**. Of the 24 items that
already carry a `video_url`, only 4 are on that channel; the other 20 live on
13 other people's channels (HeritageRestored, Providence Church Mansfield, LBC
LIVE, BTWN, Aletheia and others).

This was raised as an argument for pacing uploads and for shipping a **podcast
RSS feed** — the site publishes none today, despite having 242 MP3s in R2 with
durations, categories and series already modelled. That remains unbuilt and is
a separate piece of work. The decision to proceed with video was made with this
on the table.
