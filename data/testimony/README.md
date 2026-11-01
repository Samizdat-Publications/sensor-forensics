# Testimony constraints (work items M3.3 and M3.3b, D-010 and D-011)

This folder holds the public statements of the aircrew and radar operators involved in GIMBAL, GOFAST and FLIR1 ("Tic Tac"), broken into single factual assertions the lab can test against its geometry. Written 10/31/2026. M3.3b (same day) added the long-form podcast and video interviews, read through YouTube's automatic captions (text only); see the section below.

## Files

| File | Event | Claims |
|---|---|---|
| `gimbal.yaml` | GIMBAL, January 2015 (ids `G-T01` ...) | 41 (G-T24 to G-T41 are from M3.3b) |
| `gofast.yaml` | GOFAST, January 2015 (ids `F-T01` ...) | 11 (F-T04 to F-T11 are from M3.3b) |
| `flir1.yaml` | FLIR1 "Tic Tac", USS Nimitz group, 11/14/2004 (ids `T-T01` ...) | 108 (T-T72 to T-T108 are from M3.3b) |
| `SOURCES.md` | every source used, URL, access date, what could not be reached | |

GOFAST has almost no GOFAST-specific testimony in public sources. The East Coast class-of-objects claims in `gimbal.yaml` whose `applies_to` includes GOFAST also bear on it; the header of `gofast.yaml` lists their ids.

## Fields (every claim)

| Field | Meaning |
|---|---|
| `id` | event prefix (G, F or T) + `-T` + number |
| `witness` | name and role at the time (or the document, when no person is named) |
| `firsthand` | true if the witness saw or sensed it themselves; false if relaying someone else or a document |
| `firsthand_detail` | on which sensor or display (naked eye, SPY-1 console, ATFLIR, SA page at the debrief), or who is being relayed |
| `source` | `title`, `outlet`, `date` (MM/DD/YYYY; where the day is unknown the date says so), `url` |
| `verification` | `read directly: ...` (this worker read the text) or `relayed: ...` (the text was seen only through a forum, article or tool summary; the original was not opened) |
| `location_in_source` | hearing: printed page and PDF page; Day interview: mm:ss from the transcript; Lex Fridman: hh:mm:ss as printed on HappyScribe; articles: section; forum posts: post number; M3.3b podcasts and videos: hh:mm:ss of the YouTube auto-caption cue (the video time, to within a few seconds) |
| `claim` | plain paraphrase of one factual assertion |
| `quote` | optional, exact, under 15 words, only where the wording was seen verbatim |
| `quantity` | what measurable thing it constrains (range, altitude, speed, acceleration, size, shape, number of objects, duration, heading, wind, radar track behavior, time of day, sensor used) |
| `value` | number or range with units as stated, with this worker's derived rates marked where given |
| `uncertainty` | the band and why (memory 15 to 20 years later, relayed, estimate) |
| `applies_to` | events the claim bears on (extra field) |
| `conflicts_with` | ids of claims it contradicts; the relation is symmetric (extra rule) |
| `notes` | context, cross-references, cautions |
| `also_in` | (optional, M3.3b) the same witness repeating the same fact in another source: a list of `source`, `url`, `location_in_source`, `verification`, `note`. The note carries any change of value (for example a second estimate). A different value from the same witness is a new claim with `conflicts_with`, not an `also_in` entry |

`firsthand_detail`, `verification`, `applies_to` and `also_in` are additions to the format in the work item.

## How to use the claims (D-010, D-011)

- Weight comes from `solve/scoring.yaml` (default 1.0, adjustable live; the physics-only total always shows next to the testimony-weighted total). The YAML itself carries no weights.
- Prefer claims with `firsthand: true` and `verification` starting `read directly`. Treat `relayed:` claims and claims sourced to the unverified CVW-11 log or the 2009 "executive summary" as hints, not constraints.
- Many claims are numerically in conflict (for example 28,000 ft vs 80,000 ft vs 20,000 ft, 40 vs 60 miles to the CAP point, 0.78 s vs "under half a second" vs "several seconds"). Do not average them. Test each reading separately and report which witnesses a hypothesis satisfies.
- Quantities worth testing against the videos (M3.3b additions in the next bullet): GIMBAL range (6 to 8 nmi, G-T13; under 10 nmi, G-T12), the fleet size (G-T07, G-T01), the wind (G-T20) and the stop-and-reverse timing (G-T10, G-T11); FLIR1 size (about 40 ft), the object speed estimates (about 120 kt, 100 kt, 300 to 500 kt, 600 to 700 kt), altitude of the object (28,000, 20,000, 12,000, 4,000 ft) and the video duration claims (10 s, 76 s, 90 s, 8 to 10 min).
- New in M3.3b and testable against the geometry: the Gimbal reversal as a vertical U-turn within about 500 ft (G-T25; contrast G-T11, "no radius"), fleet of 4 to 6 with 0.5 to 1.5 mi spacing (G-T26), the Gimbal object about 100 kt (G-T28; contrast G-T09, 120 kt), black-hot polarity of the Gimbal clip (G-T29), the recording jet's 242 kt (G-T28), the Go Fast range about 5 mi against the on-screen 3.4 (F-T04), the Go Fast jet about 10,000 ft (F-T05), the Go Fast object reading colder than the ocean (F-T09, F-T10), the FLIR1 jet at about 20,000 ft and 250 kt on altitude hold (T-T75), the 99.9 range field as a jamming indicator (T-T77, T-T78), the pod tracker bars widening and recentering before the object leaves the frame (T-T81), Underwood's 10 to 15 mile range estimate at departure (also_in on T-T60), the Princeton CAP-point transit time ("seconds" T-T94, 30 to 40 s T-T35, "less than a minute" T-T10), and the 0.78 s surface drop from about 20,000 ft (T-T106 and also_in on T-T42).
- Wind: Gimbal audio 120 kt (G-T20), Graves up to 120 kt (G-T32), the hearing's category four winds (G-T04), Fravor's 90 and 70 kt (G-T36). The FLIR1 sea state wind is 5 to 10 kt (T-T87). These do not agree; test each.

## Long-form interviews (M3.3b)

- 24 YouTube videos were attempted; 19 yielded captions (the table is in `SOURCES.md`, section E). Five could not be fetched because YouTube returned HTTP 429 (Too Many Requests) to the caption request, repeatedly, from the second batch on, and no workaround was attempted; they are listed in section F.
- Method: `yt-dlp --skip-download --write-auto-subs --write-subs --sub-langs "en.*" --sub-format vtt`. Only caption text was fetched, never video or audio. The caption files are kept in `artifacts/tmp/captions/` (gitignored) and nothing from them is copied into tracked files except short paraphrases and, in the `quote` field, at most one verified phrase of under 15 words per claim. Every `quote` was machine-checked as a substring of the caption text.
- Auto-captions mis-hear, mostly numbers. Where a key word looked wrong the claim is a paraphrase and the note says so (for example, Day's "0.78 seconds" appears as "78 seconds" in two captions and is read cleanly in a third; the Voorhis/SCU caption is badly garbled and its claim is marked low weight).
- A claim repeating an earlier one (same witness, same fact) was added to the earlier claim's `also_in` list. A different value from the same witness, or a different witness, is a new claim with `conflicts_with` filled in both directions.
- Where a speaker gives a number twice and the numbers differ (Fravor 90 vs 70 kt wind, 50 vs 100 ft near miss; Day 28,000 vs 20,000 ft; Graves 300 vs 350 miles), both are recorded and flagged against each other.

## Copyright and honesty rules followed

- No transcript text is stored in tracked files. Each claim is a paraphrase plus at most one quote under 15 words.
- Quotes were checked against the local copy of the hearing transcript, the Mick West and Kevin Day transcript, the CBS articles and the arXiv paper. Quotes from page-reading tool summaries that could not be checked were dropped (the note says so).
- Nothing here is a finding about what the object was. The claims are what people said, with their stated or inferred uncertainty.
