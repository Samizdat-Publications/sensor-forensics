# App design: Sensor Forensics Lab (M4.1)

Status: design pass done 11/01/2026 with the frontend-design skill (Claude Design was not available). Mockups: `docs/design/mockup.html`, screenshots `docs/design/mock_*.png` at 1440x900 and 1920x1080. The shell in `app/` implements this layout; screenshots of it are in `artifacts/cp05/shell_*.png`.

## What the app is for

A reader (Stewart first, then anyone checking the work) steps through a sensor video frame by frame and sees, at every moment, what was on screen, how sure the lab is of each reading, what geometry follows from it, and how each explanation scores. The look is an instrument panel in a lab, not a dashboard: dark, quiet, every number in a fixed-width face, color only where it carries meaning.

The one memorable element is the **evidence tape** at the bottom: a frame scrubber whose thin tracks show, for every frame, how well each readout was read and whether the object was found. Scrubbing it is how you navigate, and it shows at a glance where the evidence is weak. Everything else stays disciplined around it.

## Layout

```
+-------------------------------------------------------------------------------------------+
| Sensor Forensics Lab | GIMBAL  GOFAST  FLIR1 | Field of view [0.35|0.70] |  1 Cockpit  2 God's-eye  3 Range  4 Compare  5 Ledger |
+--------------------------------------------------------------+----------------------------+
|                                                              | Scores                     |
|                       main view                              |  Testimony weight [==o===] |
|                (one of the five, full height)                |  H-WIT   phys  | testimony |
|                                                              |  H-BAL   ...   | ...       |
|                                                              | Read first (flags)         |
|                                                              | On screen at frame N       |
+--------------------------------------------------------------+----------------------------+
| 0719 / 1030      |  0s     5s     10s     15s     20s    25s    30s                        |
| 00:23.99 29.97fps|  Scored    ====|=====|==|=|=|=====                                     |
| |< <  >  >|      |  Azimuth   ##|#|###|##### (red = confidence < 0.30)                     |
|                  |  ...       Object                                                       |
+-------------------------------------------------------------------------------------------+
```

- Header 52 px, tape 118 px (128 px at 1800 px and wider), rail 392 px (452 px wide screens, 340 px under 1280 px). The main view takes the rest.
- Content is left aligned; numbers are right aligned in their columns so digits line up.
- The rail is on every view, because D-011 says every result shows both totals; the reader should never have to go looking for them.

## The five views

1. **Cockpit.** Original frame (left) and the three.js re-render from the reconstructed geometry (right), same size, frame-locked by index (an image-sequence player; never `<video>` seeking). The right panel has a three-way switch: Re-render, Difference (measured features solid grey, predicted features dashed white, over a dimmed original) and Blink. A strip above both reports the frame-lock error (median pixel error of horizon and object position). Planned refinement: crop both panels to the active picture (the source frames are 640x480 with a black surround), so the footage fills the panel.
2. **God's-eye.** 3D scene with orbit controls: the jet path, the line-of-sight fan over the clip, and each hypothesis's object path. A range slider moves a point along the current sight line and lists the angles-only fit at that range (air speed, ground speed, altitude, vertical speed, sight-line fit) from the Python range grid. A side column holds the controls and the readout; the scene gets the width.
3. **Range explorer.** Three charts side by side, sharing the x axis (assumed range, nmi): air speed, altitude, peak acceleration. Dashed reference lines with plain labels: balloon (0 kt air speed, drifting with the wind), fast birds (about 45 kt), airliner cruise (about 450 kt), speed of sound at the altitude (ISA), 1 g and 9 g. A shaded band marks the range interval the hypotheses' best fits occupy. One range slider drives a cursor through all three.
4. **Compare analyses.** A table: each prior analysis (Peings and von Rennenkampff 2023 close and distant paths, Sitrec; for GOFAST, Sitrec and AARO) with "published" and "lab reproduction" side by side and a pass or fail mark from the reproduction checks; below it, the lab's best fit per hypothesis at the live weight. M4.6 adds the three solutions drawn in one 3D frame, each disagreement linked to `docs/prior-work/DISAGREEMENTS.md`.
5. **Evidence ledger.** Left: every number with its frame, value, confidence, method and source file; the current frame's rows are marked; clicking a row moves the whole app to that frame. Right: the weights, one slider per criterion, the same for every hypothesis; criteria held at 0 by a ruling say why inline (D-016, D-017, Rule B). Under the score table in the shell, the per-criterion log-likelihoods of the selected hypothesis, for both fits.

## Navigation and routing

- Hash route: `#/<case>/<view>?f=<frame>&v=<variant>&w=<testimony weight>&h=<hypothesis>`. Every state worth sharing is in the URL, so a link reopens exactly what you saw.
- **Case switcher**: three large toggle buttons in the header (case name plus date), pressed state shown by a white underline. Switching keeps the view; the frame goes to the case's reference frame. A case that has not been scored yet (FLIR1 today) still opens: readouts, cues and frames work, and the rail says plainly that no totals exist yet.
- **Field of view switch**: appears only when a case was scored at more than one field of view (GIMBAL: 0.35 deg and 0.70 deg). The two runs are never mixed; the switch swaps the whole result set.
- **View tabs**: numbered 1 to 5 because the numbers are the keyboard shortcuts.

## Shared timeline (the evidence tape)

- Transport: first frame, back one, play or pause, forward one; large frame counter, time code and frame rate in monospace.
- Tracks, top to bottom: a seconds ruler; **Scored** (the frame window the scoring used, the reference frame, white ticks at the measured image-rotation steps); one track per key readout (azimuth, elevation, range where present, air speed, altitude), where lightness is read confidence and red marks frames below 0.30 (the threshold in `symbology_summary.json`); **Object** (lightness is signal to noise, red where the object was not found).
- Click or drag anywhere on the tracks to seek. The amber playhead is the only amber on the page besides keyboard focus.

## Both totals and the testimony weight (D-011)

- The rail's score table has two numeric columns per hypothesis: **Physics only** (cyan, does not move with the slider) and **With testimony** (lavender, recomputed live). Each shows the total, the gap to the best ("best" for the leader) and the rank; a thin bar under each shows the gap on a log scale, so a gap of thousands reads as far without flattening gaps of a few units.
- The testimony weight slider sits directly above the table, 0 to 2 in steps of 0.05, labelled "0 physics only", with a Default button that returns to 1.0. The slider and its value use the testimony color, so the connection is visible without a legend; a legend is there anyway.
- Totals are recomputed in the browser from each criterion's log-likelihood (`app/js/scoring.js`). Python stores two fits per hypothesis (at the default weight and at 0); at any other weight the live total is the better of the two stored fits evaluated at that weight. Where a stored fit beats the solver's own fit (two cases today), the total shows an asterisk with the margin on hover; nothing is hidden.
- A note under the table: higher is better, a gap of 2.3 is a likelihood ratio of 10, and this is not a verdict on what the object was.

## Tokens

Color (defined once in `app/css/app.css` `:root`):

| Token | Hex | Use |
|---|---|---|
| `--ink-0` | #10151b | page, behind footage |
| `--ink-1` | #171e26 | panels, rail, header, tape |
| `--ink-2` | #1f2832 | hovered or selected rows, inputs |
| `--rule` / `--rule-strong` | #2e3a47 / #445466 | hairlines, axes |
| `--text` | #e8ecf0 | readouts |
| `--text-2` | #a3afbb | labels |
| `--text-3` | #848f9c | notes, units, ranks |
| `--phys` | #63b6d9 | physics-only total only |
| `--testi` | #c7a4ec | testimony-weighted total and its slider only |
| `--cue` | #f2b84b | playhead, keyboard focus, current-frame marker |
| `--warn` | #e8705f | low confidence, object not found, failed check |
| `--ok` | #7cbf8e | passed check |

The graphite carries a cold blue cast so the grey infrared footage reads as the warmest, most important thing on the screen. Cyan and lavender were picked to be distinguishable under the common color-vision deficiencies (they differ in lightness and in the blue-yellow axis) and are never used for anything else.

Type:

- UI: Bahnschrift (Windows' DIN face, the lettering of signage and instrument placards), falling back to DIN Alternate, Barlow, Segoe UI. No web fonts: the app runs offline from `127.0.0.1`.
- Numbers: Cascadia Mono, falling back to Consolas and the system monospace, with tabular figures, and a true minus sign.
- Scale: 11, 12, 13 (body), 15, 19, 26 px; one step larger at 1800 px and wider. Sentence case everywhere; no all-caps labels except the case names, which are the videos' own names.

Units and words: feet, knots with mph beside them, nautical miles with statute miles beside them, ft/min; dates MM/DD/YYYY; no em dashes; "not stated" for a value prior work did not publish, "n/a" for one that does not apply, "blank" for an empty readout cell.

## Accessibility

- Keyboard: `1` to `5` switch views; Left and Right step one frame (Shift for ten), `,` and `.` too; Home and End jump to the ends; Space or `k` plays and pauses. The tape is a focusable slider with `aria-valuenow` and a spoken value ("frame 719, 00:23.99"). Score rows are focusable and Enter selects a hypothesis.
- Focus is a 2 px amber outline on every control.
- Contrast on `--ink-1` (computed, WCAG formula): text 14.1:1, labels 7.5:1, notes 5.1:1 (4.5:1 on the selected-row color), so every text color meets WCAG AA; cyan 7.4:1, lavender 8.0:1, amber 9.4:1, warn 5.5:1, ok 7.8:1. The note color started at #75828f (4.3:1) and was lightened after this check.
- Color is never the only signal: low confidence is also printed as a number; pass and fail are words; the two totals sit in labelled columns.
- `prefers-reduced-motion` turns off transitions; the only motion is playback, which the reader starts.

## Review notes (what changed while iterating on the screenshots)

- Field-of-view labels read "3.5 deg" from the variant id; fixed to 0.35 deg and 0.70 deg.
- The first cockpit mockup used three panels (original, re-render, difference); at both sizes each panel was too narrow for 4:3 footage. Changed to two large panels with the difference as a mode of the re-render panel.
- The difference overlay first reused cyan and lavender; changed to grey and dashed white, because those two colors mean the two totals and nothing else.
- Panel headers wrapped at 1440 px; titles and the mode switch no longer wrap, and the source note truncates instead.
- Lab best-fit table cells wrapped mid-number; numeric cells no longer wrap.
- The FLIR1 header showed an empty field-of-view control (a CSS rule overrode `hidden`); fixed globally.

## Build status (M4.3 to M4.7, 11/01/2026)

Done (not committed):

- **Exporter.** `tools/build_app_data.py` now also writes `predictions.json` (via `tools/app_predictions.py`: every stored fit re-evaluated on every frame by the scorer's own `solve.score.predict` and `rotation_terms`, read-only), `testimony.json` (every claim, source, use), `range_curves.json` (from `data/derived/<case>/range_curves.csv` when the scorer writes it), per-variant `excluded_criteria`, and an `extras` pass-through of any new results field (both-ways totals, rotation-noise sensitivity), plus `artifacts/cp05/framelock.json`.
- **Cockpit.** Original frame and three.js re-render, both cropped to the active picture, frame-locked by index. Camera at the jet along the predicted sight line, frame field of view, rolled to the predicted image horizon; object at its 3D position with predicted size and rotation; level lines; polarity as on screen. Modes Re-render, Difference, Blink. Frame-lock strip: median horizon error (GIMBAL, measured from the cloud-deck motion direction, 15-frame running median) and median object-position error. GIMBAL 0.35 deg: horizon 2.4 to 5.7 px, object 1.9 px; GOFAST object 1.4 px, FLIR1 object 5.8 px, horizon n/a (no horizon reference in that footage).
- **God's-eye.** Jet path, sight-line fan every 30 frames, each hypothesis's path in its own color (each aligned to its own jet, the heading being a fitted nuisance), fixed-range path from the range slider with its kinematics, angles-only probe readout, scale bar in nmi, show and hide per hypothesis.
- **Range explorer.** Air speed (log), altitude, peak acceleration (log), sight-line misfit against range; reference bands (balloon, birds 15 to 60 kt, airliners 400 to 500 kt), Mach 1 at altitude, 1 g and 9 g; best-fit markers and band; shared range cursor; per-hypothesis curves drawn automatically when `range_curves.csv` appears.
- **Evidence ledger.** Virtualized table of every reading (click opens the frame in the cockpit), testimony claims tab, one weight slider per criterion, exclusions add-back, both totals as weighted now and with exclusions added back, per-criterion breakdown, "More from the scorer".
- **Compare.** Published vs reproduced table with check marks, range and altitude over the clip (lab per frame, prior work at the frames it states), lab best fits.
- **Tests.** `tests/js/geom.test.mjs` (JS vs Python image position and frame lock, camera basis, projection, range interpolation vs the Python grid, path kinematics, ISA); new export tests in `tests/test_build_app_data.py`.

Remaining: the 60-second GIMBAL recording (M4.8); a 3D overlay of prior-work paths (only their stated endpoints are drawn, since the reproductions do not export per-frame paths).
