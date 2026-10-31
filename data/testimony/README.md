# Testimony constraints (work item M3.3, D-010 and D-011)

This folder holds the public statements of the aircrew and radar operators involved in GIMBAL, GOFAST and FLIR1 ("Tic Tac"), broken into single factual assertions the lab can test against its geometry. Written 10/31/2026.

## Files

| File | Event | Claims |
|---|---|---|
| `gimbal.yaml` | GIMBAL, January 2015 (ids `G-T01` ...) | 23 |
| `gofast.yaml` | GOFAST, January 2015 (ids `F-T01` ...) | 3 |
| `flir1.yaml` | FLIR1 "Tic Tac", USS Nimitz group, 11/14/2004 (ids `T-T01` ...) | 71 |
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
| `location_in_source` | hearing: printed page and PDF page; Day interview: mm:ss from the transcript; Lex Fridman: hh:mm:ss as printed on HappyScribe; articles: section; forum posts: post number |
| `claim` | plain paraphrase of one factual assertion |
| `quote` | optional, exact, under 15 words, only where the wording was seen verbatim |
| `quantity` | what measurable thing it constrains (range, altitude, speed, acceleration, size, shape, number of objects, duration, heading, wind, radar track behavior, time of day, sensor used) |
| `value` | number or range with units as stated, with this worker's derived rates marked where given |
| `uncertainty` | the band and why (memory 15 to 20 years later, relayed, estimate) |
| `applies_to` | events the claim bears on (extra field) |
| `conflicts_with` | ids of claims it contradicts; the relation is symmetric (extra rule) |
| `notes` | context, cross-references, cautions |

`firsthand_detail`, `verification` and `applies_to` are additions to the format in the work item.

## How to use the claims (D-010, D-011)

- Weight comes from `solve/scoring.yaml` (default 1.0, adjustable live; the physics-only total always shows next to the testimony-weighted total). The YAML itself carries no weights.
- Prefer claims with `firsthand: true` and `verification` starting `read directly`. Treat `relayed:` claims and claims sourced to the unverified CVW-11 log or the 2009 "executive summary" as hints, not constraints.
- Many claims are numerically in conflict (for example 28,000 ft vs 80,000 ft vs 20,000 ft, 40 vs 60 miles to the CAP point, 0.78 s vs "under half a second" vs "several seconds"). Do not average them. Test each reading separately and report which witnesses a hypothesis satisfies.
- Quantities worth testing against the videos: GIMBAL range (6 to 8 nmi, G-T13; under 10 nmi, G-T12), the fleet size (G-T07, G-T01), the wind (G-T20) and the stop-and-reverse timing (G-T10, G-T11); FLIR1 size (about 40 ft), the object speed estimates (about 120 kt, 100 kt, 300 to 500 kt, 600 to 700 kt), altitude of the object (28,000, 20,000, 12,000, 4,000 ft) and the video duration claims (10 s, 76 s, 90 s, 8 to 10 min).

## Copyright and honesty rules followed

- No transcript text is stored. Each claim is a paraphrase plus at most one quote under 15 words.
- Quotes were checked against the local copy of the hearing transcript, the Mick West and Kevin Day transcript, the CBS articles and the arXiv paper. Quotes from page-reading tool summaries that could not be checked were dropped (the note says so).
- Nothing here is a finding about what the object was. The claims are what people said, with their stated or inferred uncertainty.
