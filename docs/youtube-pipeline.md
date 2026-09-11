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
over footage, and `--light` switches to dark type on a pale scrim. Neither is
wired into `make_video.py` yet — the prototype composited them by hand.

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

## Style — settled 2026-09-11

Approved after several rounds. Do not re-litigate these:

- **No ping-pong / reverse loops.** Reversed motion reads as distracting. The
  seam is hidden instead by crossfading the clip's tail into its own head
  (`trim` + `blend`, ~2s), which loops cleanly without playing anything
  backwards.
- **Footage should be nearly still.** Locked-off camera, one small thing moving
  — leaves, steam, flame, rain. Not drone shots, pans or dollies. Slowing a
  moving clip down is a poor substitute: the whole frame still drifts.
- **The title fades in and out**, rather than sitting on screen throughout.
- **Scenes crossfade into other scenes** across a montage.
- **Light or dark palette is chosen by measurement, not taste.** Sample the
  luma of the region the text occupies (`crop` + `signalstats` YAVG); above
  ~110 use `--light` (dark type on a pale scrim), below it the dark palette.
  The Coverr mountain clip measured 126 and got the light treatment.

### Two traps found the hard way

**Only ONE fade in/out pair per overlay.** Chaining a second
`fade=t=in:...:alpha=1` after a `fade=t=out` silently erases the *first*
appearance — a fade-in forces alpha to 0 for all timestamps before its start.
The title vanished entirely from a whole render because of this. Recurrence
comes from the loop repeating, not from stacking fades.

**Loop length IS the title cadence.** The title reappears once per loop, so a
54-second loop shows it every 54 seconds — far too often. Showing it every 4-5
minutes needs a montage that long, which means several clips or long ones. This
is the main reason more footage is needed.

### Scene structure — CORRECTED 2026-09-11, not yet built

What was built is wrong. It crossfades short clips continuously (a 57s montage
looping 37 times through a 35-minute sermon) and shows the title once every few
cycles. The visual loop recurring every ~minute is what reads as repetitive --
the title cadence was right, the footage cadence was never discussed.

**What is actually wanted:**

    coffee shop  ~4 min  ->  title fades in/out  ->  next scene ~4 min
    ->  title  ->  next scene ~4 min  ->  title  ->  (repeat)

So each SCENE holds for about four minutes, and the title appears at each scene
change. With three clips that is a ~12-minute cycle, repeating under three times
in a 35-minute sermon, and each scene is seen about three times instead of 37.

**How to build it:**

1. Per clip, build a seamless self-loop (tail crossfaded into head, as now) and
   repeat it to ~4 minutes. The clips are 20-30s, so each holds for 6-12 passes;
   they are nearly static (motion 0.18-1.19) so `--slow 2.0` halves that.
2. Crossfade each 4-minute block into the next.
3. Overlay the title near each scene change.

**Step 3 needs a different overlay technique.** The title must appear several
times per master, and fade pairs CANNOT be chained on one overlay stream -- a
second `fade=t=in` erases the first appearance (see the trap above). Use one
overlay INPUT per appearance, each carrying a single fade in/out pair, chained
as successive `overlay` filters. Separate streams, so they do not interfere.

### What footage costs

| | Per 35-min sermon | Library (233) |
|---|---|---|
| Title card only | 37 MB | ~10 GB |
| Moving footage (crf 26, ~1.5 Mbps) | 416 MB | ~95 GB |

Genuinely still footage should land well below the moving-footage figure, since
the encoder only spends bits where something moves. Worth re-measuring once real
clips exist.

### Clip brief

Locked-off camera, one small moving element, **30s+ preferred** (longer clips
mean longer loops mean rarer titles), 1080p, consistent exposure, no people,
text, logos or landmarks. Strip audio (`-an`) — stock clips often carry a music
bed that trips Content ID. Sources: coverr.co, pexels.com/videos,
pixabay.com/videos, mixkit.co, mazwai.com. Check each clip's licence on its own
page. Drop raw downloads in `.video/source/`.

## Open questions

**1. RESOLVED** — the title fades in and out; see Style above.

**2. Footage — the live blocker.** One clip exists (a Coverr drone shot, too
moving to be the final look). Needs 3+ that match the Clip brief above.

**3. Are scenes shared across a category, or per sermon?** Undecided. Shared
means one montage encoded per category and stream-copied for every sermon in it
— much cheaper. Per-sermon means more variety but an encode each.

**4. Light/dark is automatic in principle** (measure, then pick) but the
measurement is not yet wired into `make_video.py` — it was run by hand for the
prototype.

## Still to build

- **Batch runner with a state file** — which have MP4s, which are uploaded, which
  have `video_url` written back. Same pattern as the existing `uploaded_r2.log`.
  This is what makes a-couple-a-day survivable over weeks.
- **Montage builder** — the real missing piece. Take N clips from
  `.video/source/`, scale to 720p, strip audio, crossfade each into the next,
  crossfade the last back into the first (tail-into-head via `trim` + `blend`,
  NOT reverse), overlay the title with ONE fade in/out pair, and encode once.
  `make_video.py` then stream-copies that montage under the audio, as it already
  does with the title card.
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
