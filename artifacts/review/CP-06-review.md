# CP-06 independent review (M5, PURSUE)

Reviewer: independent checkpoint check, 11/02/2026. Scope: `checkpoints/CP-06.md`, `docs/results/pursue.md`, `docs/audit/pursue.md`, `data/pursue/*`, `data/derived/pursue/*`, `docs/results/pursue/*.png`, `tests/test_pursue_m5.py`, and a handful of frames under `data/frames/dow-uap-*`. The solve/ and M3/M4 files the other worker is editing were not judged.

## What I checked myself

- `data/pursue/triage.csv` against `data/pursue/index.csv` with my own script: 134 rows each, no duplicates, same ID set both ways; tiers 117 Not viable, 17 Bounded, 0 Full. `tools/check_pursue_index.py` agrees.
- Every clip outside the 8 appears exactly once in `docs/results/pursue.md:44-171` (126 rows). Tier and reason match `triage.csv` exactly for all 126, and none is blank. The 9 deferred Bounded clips are PR030, PR037, PR048, PR058, PR107, PR120, PR121, PR122 and PR134.
- I recomputed from the per-clip files:
  - PR044 slope 1.083, r 0.943, 0.083 to 0.111 m/px; speed 1.24 / 4.27 / 13.7 m/s; gate range 10.2 km at 1 deg HFOV.
  - PR059 slope 0.988, r 0.996, 0.231 to 0.273 m/px.
  - PR052 slope 0.746 (from `summary.json`).
  - PR111 label x sin|el|: std/mean A 3.6, B 3.2, C 4.2, D 1.0 percent; heights 8.5 / 71.4 / 17.1 to 17.4 / 71.6.
  - PR113: 36.11 px/deg; 2.066, 1.825 and 1.644 rad/s; HFOV 51.2, 39.2 and 28.5 deg over 1850 px; Mach 1 (340 m/s) reached at 165 to 207 m; 12 to 21 percent lower rate.
  - PR149: 603.3 and 621.6 px/s; 97.7 to 130.3, 100.7 to 134.2 and 78.2 to 130.3 m/s; 8 px wide, so 1.04 to 1.73 m.
  - All of these match `pursue.md` to the stated precision.
- I looked at the frames:
  - PR044 frames 6030, 6060, 6090 and 6120: no label on the 144 px box; 23M, 33M and 12M on the 231, 304 and 108 px boxes; the scene does not zoom.
  - PR059 frames 1100, 1170, 1230 and 1260: labels 36M, 18M, 10M and 7M on shrinking brackets; terrain features keep their size.
  - PR113 frames 150, 300 and 408: a HUD pitch ladder (dive numbers rising downward at 5 s, climb lines over a horizon bar at 10 s, rolled at 13.6 s), about 180 px per 5 deg.
  - PR149 frames 20, 90 and 97.
- Plots: I opened PR044, PR111, PR113 and PR149. Axes are labelled and the plots agree with `curves.csv`.
- Tests: `.venv\Scripts\python.exe -m pytest tests\test_pursue_m5.py -q` gave 15 passed. I did not run the full gate, because another worker is editing solve/.
- No U+2014 in either `checkpoints/CP-06.md` or `docs/results/pursue.md`.

## Verdict per criterion

| Criterion | Verdict | Evidence and reason |
|---|---|---|
| 1. A results table for each viable clip | Partial | The table exists for all 8 (`pursue.md:15-24`) and every number I spot-checked reproduces. But the table misstates the headline test in two places. (a) `pursue.md:17` (and `summary.json` notes) says the gate grows "144 to 304 px while the label goes 23M to 33M". In fact the 144 px box at frame 6030 carries no label: 23M sits on the 231 px box (`readings_manual.csv` row 6060, and confirmed by eye). Also, "65 readings, r 0.94 over 2.8x" comes from only 3 distinct gate sizes, and 63 of the 65 readings are on the fixed 108 px gate. (b) `pursue.md:28` says PR052 passes the test "cleanly", but its own `summary.json` gives a slope of 0.75 from 3 by-eye sizes that mix box height, bracket height and an assumed-square bracket width. The width reading still stands on PR044 and PR059, which I confirmed on frames. |
| 2. A list of the not-viable clips, each with its reason | Pass | `pursue.md:40-171` lists all 117 Not viable clips plus the 9 deferred Bounded ones, each with the triage tier and reason, identical to `triage.csv` (134 rows, one per index clip). |
| 3. A table of the Bounded-tier clips | Partial | There is no single Bounded table. The 8 analyzed clips sit in the results table, and the other 9 are scattered through the 126-row list among 117 Not viable rows (`CP-06.md:24`). Also, PR107's own reason (`pursue.md:128`) says the clip gives "a line of sight angle only", with no scale. That does not meet the Bounded rule in `TRIAGE-SCHEMA.md` (a field-of-view scale or a known-size reference; when unsure, pick the lower tier). |

## Other findings

1. **The zero-Full justification contradicts the PR111 result.** `CP-06.md:22` says "pod angles, altitude and range are redacted on every military clip", and `CP-06.md:30` says "the numbers that would fix the line of sight and the range are redacted". Yet PR111 shows elevation, and CP-06 itself finds its label behaves like slant range (`CP-06.md:14`). The audit (`docs/audit/pursue.md:29`) says that finding "would then be the only Full candidate". PR111 stays Bounded for the right reason, namely no azimuth (`pursue.md:30`), but CP-06 states the wrong reason.
2. **Plain words misattribute PR113.** `CP-06.md:30`: "PR113's angular scale is a pitch ladder and implies a narrower field of view and a slower angular rate". The ladder alone gives 36.1 px/deg, almost the paper's 35.4, and 51 deg with square pixels. The narrower field of view and the slower rate come from the pixel-aspect estimate (1.31 fitted, about 1.8 by eye, still unresolved) and need a conformal ladder. Separately, `CP-06.md:15` compares our 39 deg over 1850 px with the paper's 54 deg over 1920 px. The like-for-like comparison is 51 against 54, which is what `pursue.md:23` does.
3. **PR149's "true maximum" depends on unstated geometry.** The object's last frames (90 to 97, y 681 to 661) are left of the stern and at or above the stern's waterline row, which is about 670 at x about 480 in frame 97. "Below the waterline" holds only if the sloped waterline is extrapolated, which assumes the slope is camera roll rather than the ship's heading. If the bow is nearer instead, those few frames have a range ratio of about 1 or slightly above. The claim should name this assumption, or restrict itself to frames 15 to 89. It is also the maximum of the cross-line-of-sight component only, not of the total speed. `pursue.md:11` says so, but `CP-06.md:16` reads as an unqualified maximum.
4. **PR044 size band.** It applies the m/px range to the 9.5 px midpoint only. With the stated 8 to 11 px it is 0.67 to 1.22 m. The resolvedness test of D-016 is not applied to any PURSUE size: an 8 to 11 px hot speck may be unresolved, in which case the size is an upper value, as PR059 and PR149 already say for their own sizes. The plain words drop the "low confidence" flag on PR044's 1 to 14 m/s (speed from detection jumps).
5. **PR111 segment C** has a std/mean of 4.2 percent against a rounding half-width of 3.9 percent, and the plot shows it rising monotonically. "Inside the whole-degree rounding" (`pursue.md:22`) is marginal for C. Segment B (n 4, 1 deg of elevation change) carries almost no test power.
6. Minor:
   - `pursue.md:34` calls our track "longer" while giving 2.7 s against the paper's 3.2 s; it is longer in frames only.
   - `pursue.md:3` is headed "Status (11/01/2026)" but reports 11/02 work.
   - `docs/audit/pursue.md:36` still says "M5 takes those 17 through the same code", which D-013 superseded.

## Overall: SEND BACK

The data, the arithmetic, the frames and the tests hold up well. The fixes are text and one small table, but they correct misstatements of evidence in the headline finding and in the plain words.

### Must-fix

1. `pursue.md:17` and the PR044 `summary.json` notes: correct the pairing (no label at 144 px; 23M at 231 px, 33M at 304 px, 12M at 108 px). State that the test rests on 3 gate sizes, with the decisive step being 33M to 12M as the gate snaps from 304 to 108 px in 0.17 s at fixed zoom.
2. `pursue.md:28` and `CP-06.md:13`: report PR052's slope of 0.75 and drop "cleanly" for PR052 (supporting evidence, by eye).
3. `CP-06.md:22` and `CP-06.md:30`: replace "pod angles, altitude and range are redacted on every clip" with the true reason no clip is Full: no clip shows azimuth, and PR111 has elevation and a slant-range-like label but no azimuth.
4. `CP-06.md:30` (and `CP-06.md:15`): attribute PR113's narrower field of view and slower rate to the pixel aspect, conditional on a conformal ladder and with the aspect unresolved. Compare 39 against 51 like-for-like, with the paper's 54 noted.
5. Add one 17-row Bounded table (clip, scale source, analyzed or deferred under D-013). Re-tier PR107 to Not viable, or justify in its notes why an elevation readout alone counts as Bounded.

### Nice-to-fix

- PR149: name the camera-roll assumption behind "below the waterline", or limit it to frames 15 to 89. Say "maximum of the cross-line-of-sight component".
- PR044: give the size as 0.7 to 1.2 m, or as an upper value if unresolved. Apply or cite D-016 for PURSUE sizes. Keep "low confidence" on the speed in the plain words.
- PR111: note that segment C is marginal against rounding, and that B is a weak test.
- Fix the "longer" track wording, the status date and the stale audit sentence.
