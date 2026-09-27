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
| Items with audio and no `video_url` | **257** |
| Total runtime | **171 hours** (avg 40 min) |
| Source MP3s already on this PC | 256 of 257 |
| The one exception | `2026-07-27-speak-for-the-voiceless` — `source_path` points at a file that's gone; `make_video.py` falls back to pulling it from R2 |

Re-measure these rather than trusting them: every upload moves them. The query
is in the "Checking scope" note at the foot of this file.

## What exists now

**`tools/make_video.py --slug SLUG`** — renders one item to `.video/out/`:

- `<YouTube title>.mp4` — the upload. Named for the title, so the upload form
  prefills it.
- `thumbnail.png` — 1280x720, drag onto the thumbnail slot
- `description.txt` — paste into the description; includes the footage credits
- `captions.txt` — plain transcript. Superseded in practice by `captions.srt`
  from `make_captions.py`; see Captions below.

Measured on a 35-minute sermon: **67 seconds, 37 MB**. Whole library ≈ 5 hours
and ~10 GB.

**`tools/make_thumb.mjs`** — the card generator. Reuses the palette, waveform
mark and type of `tools/make_brand.mjs`, so a YouTube search result reads as the
same brand as the site's OG card. Handles one-word and 47-character titles.
`--overlay` produces a transparent version with a dark scrim, for compositing
over footage, and `--light` switches to dark type on a pale scrim. Both are now
wired into `make_video.py`, which calls the card generator itself and picks the
palette from a luma measurement — see "Choosing footage" below.

**`tools/make_montage.py`** — builds the looping background a sermon plays over.
`--clips` names the footage explicitly, in the order the scenes play; with no
`--clips` it takes everything in `.video/source/` alphabetically. `--slow 2.0`
halves the speed of locked-off footage invisibly, which is the cheapest way to
lengthen a loop. Any common container is accepted (`VIDEO_EXTS`), not just mp4.

**`tools/make_captions.py`** — the timed `.srt`. See Captions below; this is a
required step, not an optional one.

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
- **There is NO title page at the start of a `--background` render**, and that
  is deliberate (asked and settled 2026-09-22). The title fades in at 6s, holds
  to 22s, is gone by 25s, and returns once per loop. Expect to open on bare
  footage; it looks like a bug and is not. The full-screen held card is the
  *other* look, the one you get with no `--background` at all. If you ever do
  want a page on the front, `tools/prepend_title.py` adds one by stream copy in
  seconds — but it must run BEFORE `make_captions.py`, since a prepended card
  shifts every cue (use its `--audio` flag against the finished MP4).
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

### Scene structure — BUILT 2026-09-22

The first attempt crossfaded short clips continuously (a 57s montage looping 37
times through a 35-minute sermon) and showed the title once every few cycles.
The visual loop recurring every ~minute is what reads as repetitive -- the title
cadence was right, the footage cadence was never discussed.

`make_montage.py` + `make_video.py` now do what is described below. Aim each
montage at **3-4 minutes**: `make_video.py` repeats it to `--title-every`
minutes (default 4) and shows the title once per cycle, so the montage length
sets both cadences at once.

**What is wanted:**

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

**How the overlay avoids the fade trap.** Rather than stacking fades, the
master carries exactly ONE fade in/out pair and is then stream-looped under the
audio. Recurrence comes from the loop, never from chained fades. If you ever do
need several appearances inside one master, use one overlay INPUT per
appearance, each with a single fade pair, chained as successive `overlay`
filters -- separate streams, so they cannot erase each other.

### What footage costs

| | Per 35-min sermon | Library (257) |
|---|---|---|
| Title card only | 37 MB | ~10 GB |
| Moving footage (crf 26, ~1.5 Mbps) | 416 MB | ~95 GB |
| **Real still footage, crf 25 (measured)** | **~200 MB** | **~58 GB** |

The last row is measured, not projected: the four Armor of God renders came in
at 4.1-6.4 MB/min (164-289 MB for 36-45 min), averaging 5.75 MB/min. Still
footage costs well under half the moving-footage estimate, exactly as expected
-- the encoder only spends bits where something moves, and a locked-off clip
slowed 2x moves very little.

### Clip brief

Locked-off camera, one small moving element, **30s+ preferred** (longer clips
mean longer loops mean rarer titles), 1080p, consistent exposure, no people,
text, logos or landmarks. Strip audio (`-an`) — stock clips often carry a music
bed that trips Content ID. Sources: coverr.co, pexels.com/videos,
pixabay.com/videos, mixkit.co, mazwai.com. Check each clip's licence on its own
page. Drop raw downloads in `.video/source/`.

**Every clip needs a line in `.video/source/credits.tsv` the moment it lands.**
`make_video.py` copies that line into the description; a clip with no line is
credited nowhere, and the run only prints a warning you will miss. The file's
own header documents the format rules -- the important one is that a line
without a TAB is skipped silently, so a malformed entry fails exactly like a
missing one. Filenames must match disk exactly, case included.

## Choosing footage — settled 2026-09-22

**Footage is chosen per sermon, not shared per category.** The alternative was
one montage per category, stream-copied across everything in it; that is
cheaper, but it makes 154 sermons look identical. Per-sermon costs one montage
encode each (~1 min) and is worth it. `--clips` exists for exactly this.

**Clips can only share a montage if they sit on the same side of luma 110.**
This is the constraint that decides every grouping, and it is easy to miss.
`make_video.py` takes ONE luma reading of the whole montage and picks one
palette from it. Mix a dark clip (48) with a bright one (124) and the average
(~86) selects the dark palette -- cream type -- which then sits unreadable over
the bright scene for a quarter of the loop. Group within a band; never across.

Measure a clip before using it:

    ffmpeg -v error -i CLIP -f null - -vf "fps=2,
      scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,
      crop=iw*0.62:ih:0:0,signalstats,
      metadata=print:key=lavfi.signalstats.YAVG:file=-"

Average the YAVG values. Under 110 is the dark band (cream type), over is the
light band (dark type). The `fps=2` and `scale` are only there for speed -- the
crop to the left 62% is what matters, because that is where the title sits.

**Three clips at `--slow 2.0` lands on the 3-4 minute target**, given clips of
20-60s. Fewer than three and the loop is too short; the footage starts reading
as repetitive well before the title does.

**Look at the frames before choosing.** Filenames lie about what is in a clip:
one named for a campus turned out to be a moving crowd with a LIBRARY sign in
shot, and a coffee-shop clip has a lit CAFE sign -- both against the Clip brief.
A contact sheet of mid-points is quick:

    ffmpeg -y -ss MID -i CLIP -frames:v 1 -vf scale=426:240 f.png   # per clip
    ffmpeg -y -i "%02d.png" -filter_complex tile=3x3:margin=6:padding=6 sheet.png

## The whole sequence for one sermon

    python tools/make_montage.py --slow 2.0 --clips A B C --out .video/loops/<slug>.mp4
    python tools/make_video.py --slug <slug> --background .video/loops/<slug>.mp4
    python tools/make_captions.py --slug <slug>

That leaves `.video/out/<slug>/` holding the MP4, `thumbnail.png`,
`description.txt`, `captions.txt` and `captions.srt` -- everything the upload
form needs. Check the render printed `OK` on its duration line; it compares the
result against `items.duration_sec` and that is the guard against the
`-shortest` class of bug.

After upload:

    python tools/attach_extras.py --slug <slug> --video URL --remote

## Open questions

**1. RESOLVED** — the title fades in and out; see Style above.

**2. RESOLVED** — footage is no longer the blocker. 16 clips in
`.video/source/` as of 2026-09-22, all credited.

**3. RESOLVED** — per sermon; see "Choosing footage" above.

**4. RESOLVED** — `mean_luma_behind_text()` in `make_video.py` measures the
montage and picks the palette. It prints the reading and the choice on every
run; read that line, because it is the only signal that a badly grouped montage
is about to get the wrong type.

**5. The light band is thin.** Only 3 of the 16 clips measure over 110
(horseField 112, butterfly_flower 118, butterfly.mov 124). Three is the minimum
for a montage, so every sermon assigned to the light band currently gets the
same footage. More bright clips would fix it.

**6. Campus footage is still short.** `college_students.mp4` is the only one,
and it fights the Clip brief (crowd, LIBRARY sign, real motion). The OSU Marion
series is the obvious home for campus footage and cannot be given a montage of
its own yet.

## Still to build

- **Batch runner with a state file** — which have MP4s, which are uploaded, which
  have `video_url` written back. Same pattern as the existing `uploaded_r2.log`.
  This is what makes a-couple-a-day survivable over weeks.
- **Write the URL back.** After upload, `tools/attach_extras.py --slug SLUG
  --video URL --remote` fills `items.video_url`, and the sermon page grows its
  video button automatically.

## Metadata plan

| Field | Source |
|---|---|
| Title | `items.title`, plus series and part when present (YouTube caps at 100 chars). **Check it before uploading:** `youtube_title()` appends the series part only when the title does not already contain it, so "Put on These - Part 1" in series part 3 comes out as "Put on These - Part 1 \| Armor of God - Part 3" — two different part numbers in one title. Not wrong, but confusing in a search result; fix it in the upload form or in `items.series_part`. |
| Description | passage, series, date, and a link back to `teaching.michaelcoughlin.net/listen/<slug>` |
| Playlist | `collections.title` — 1 Peter, Hebrews, Ten Commandments map straight across |
| Captions | **Run `tools/make_captions.py --slug SLUG` for every upload.** It writes a timed `captions.srt` into the package. |

### Captions — corrected 2026-09-22

This entry used to read "YouTube auto-syncs a plain transcript with no timings,
no SRT work needed", and that is wrong in practice. Auto-sync kept refusing the
plain text, so every upload since 2026-09-11 has used a real timed `.srt`. The
`make_captions.py` docstring still calls itself a fallback; treat it as the
standard step.

Two different files, easy to confuse:

| file | written by | what it is |
|---|---|---|
| `captions.txt` | `make_video.py` | plain transcript, no timings, for the "Without timing" auto-sync path. Kept because it costs nothing. |
| `captions.srt` | `make_captions.py` | the real timed subtitles. **This is the one to upload.** |

`make_captions.py` re-runs the audio through Groq Whisper and keeps the
per-segment timestamps that `transcribe_groq.py` discards when it stores
paragraph text in `item_transcripts`. It is therefore a paid API call and takes
a few minutes per sermon, not seconds. It prints `N cues, last ends X min, audio
is Y min` -- if those two durations disagree by more than a rounding error, the
chunk offsets have drifted and the subtitles will run progressively early.

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

## Checking scope

The numbers at the top of this file go stale with every upload. To re-measure:

    python - <<'EOF'
    import sys; sys.path.insert(0, "tools")
    from make_video import rows
    from pathlib import Path
    rs = rows("SELECT slug, source_path, duration_sec FROM items "
              "WHERE (video_url IS NULL OR video_url='') AND r2_key IS NOT NULL")
    tot = sum(r["duration_sec"] or 0 for r in rs)
    miss = [r for r in rs if not (r.get("source_path") and Path(r["source_path"]).exists())]
    print(f"{len(rs)} need video, {tot/3600:.0f} h, {len(rs)-len(miss)} with local audio")
    EOF

Note `attach_extras.py` defaults to **local** D1 and needs `--remote` for
production -- the opposite of most tools in `tools/`, which default to
production and take `--local`. Forgetting it writes the link to the dev database
and the live page does not change.
