# CP-05 independent review, second check (M4, the web app)

Reviewer: independent checker, 11/02/2026, HEAD 1453f10 (fixes in 5ef32a8). Working tree had the FLIR1 discriminators job's files modified; left alone.

## Verdict: SEND BACK (two small fixes)

All three first-check must-fixes are substantially fixed: invalid grid points are gone, the range charts are full size at 1440 x 900, and CP-05's frame-lock text is now correct. Two things are left. Reference labels in the range charts are still struck through by data curves; the worst case is GIMBAL's misfit threshold label. And the app's own cockpit strip still shows the object number as a "Frame lock" measure, the same misreading that CP-05 now corrects.

## Per criterion

| Criterion | Verdict | Evidence |
|---|---|---|
| Screenshots of every view | Pass (with must-fix A) | The six range shots were retaken at 11/02 01:40, after range.js (01:39) and app.css (01:38). All three 1440 range shots now show four full-size 250 px chart panels with roughly 11 px text, and the view scrolls to the readout. The 1920 GOFAST shot is clean. The other 1440 shots spot-checked (flir1_cockpit) render normally. The 5ef32a8 CSS diff changes only `.rg` and `.rg-charts`, so the other views cannot have regressed. |
| 60 s GIMBAL recording, re-render locked | Pass (carried) | The first check passed it and the fix commit did not change it. I did not re-examine it. |

## First-check must-fixes

| Must-fix | Verdict | Evidence |
|---|---|---|
| 1. Range explorer must not draw invalid grid points | Pass | `curves()` in range.js now drops points with `valid`/`valid_physics_only` false, a non-finite total, or a total at or below -5e5. That is the same `FLOOR_TOTAL` as solve/results_report.py:35. I reran the filter on app/data/<case>/range_curves.json. GOFAST H-WIT and H-ART now stop at 7.5 nmi, with the null rows at 10 to 60 nmi dropped, and H-AC stops at 3.0 nmi (it hits the floor at 3.5 and beyond). FLIR1 H-SLOW and H-CLOSE draw nothing, because every point is at the floor. gofast_range_1440.png and _1920.png now end the x axis at about 8.4 nmi, with no 1 kt or 0 ft plateau. One remaining sub-1 kt point is real data: GIMBAL H-BAL is 0.03 to 0.98 kt from 10 to 45 nmi, which is genuine balloon drift, and `clamp1` draws it at 1 kt on the log axis under the "air speed near 0" band. |
| 2. Range explorer readable at 1440 x 900, no label overlaps | Partial | The size and legibility problems are fixed. "Mach 1" no longer sits on the "airliners" label. But labels are still struck through by data curves. In gimbal_range_1440.png the Sight-line misfit label "2.3 below the best: likelihood ratio 10" has three dashed hypothesis curves running along its full length, because the curves level off at that line, and it is hard to read (zoomed crop checked). In the same shot "Mach 1" and "airliners, 400 to 500 kt" are crossed by the orange, white and grey curves. In flir1_range_1440.png the white probe curve runs through "airliners". GOFAST's "balloon: drifts..." label and its threshold label are cut by the cursor and curves, but stay readable. |
| 3. CP-05 frame-lock explanation correct | Pass in CP-05, Partial in the app (must-fix B) | CP-05.md lines 38 to 42 now say what the data show. The object number is the blob's offset from the frame centre and is the same for every hypothesis by construction. framelock.json confirms this: every row has the same object median (GIMBAL 1.857 for all fits in both variants, GOFAST 1.411, FLIR1 5.803). Only GIMBAL has hypothesis-dependent horizon values (2.12 to 2.53 px, and H-CLOSE 5.01 to 5.81). GOFAST and FLIR1 horizon values are null, as CP-05 says. The unsupported FLIR1 "low contrast" reason is gone; Known issues now says "cause not investigated". However, the cockpit strip (app/js/views/cockpit.js:236 to 239, visible in flir1_cockpit_1440.png) still reads "Frame lock: H-WIT ... Object position, median 5.8 px", with no hint that this number does not depend on the hypothesis. |

## Nice-to-fix items from the first check

- Asterisked totals: now explained in CP-05 Known issues (GOFAST H-WIT -1,078.9 against -1,079.1; FLIR1 H-SLOW by 0.6). Done.
- "1 flags": rail.js:63 now pluralizes; flir1 shots show "1 flag". Done.
- Stale shell_*.png: removed in 5ef32a8 (14 deletions); artifacts/cp05 now holds only the 34 listed shots and framelock.json. Done.
- GIMBAL "Read first" flags below the fold at 1440: disclosed in CP-05 Known issues. Accepted.

## Checks run

- `node --test tests/js/geom.test.mjs tests/js/scoring.test.mjs`: 14 of 14 pass.
- Em dashes (U+2014): none in checkpoints/CP-05.md, app/js/views/range.js, app/js/rail.js or app/css/app.css.

## Must-fix

A. **Make the reference labels in the range charts readable over the data.** Give them a background-coloured halo, for example SVG `paint-order: stroke` with a stroke in the panel colour, or draw them after the curves, or move the threshold label off the asymptote. Then retake gimbal_range_1440.png, gimbal_range_1920.png and flir1_range_1440.png. The GIMBAL misfit threshold label is the one that has to become clearly legible.

B. **Say in the app that the object number does not test the hypothesis.** In the cockpit strip, either label the object metric as the blob's offset from the frame centre, the same for every hypothesis (a short note or tooltip is enough), or move it out of the "Frame lock" group, so that the app matches CP-05. Then retake the cockpit shots.

## Nice-to-fix (new)

- In the range readout table, a hypothesis with no valid solution at the cursor range disappears without a word (GOFAST H-AC and H-CLOSE at 4.0 nmi; FLIR1 H-SLOW and H-CLOSE at any range). Show a row saying "no valid solution at this range" instead.
- The legend lists FLIR1 H-SLOW and H-CLOSE with the per-hypothesis curves, but neither has a curve to draw (every grid point is at the likelihood floor). Only their best-fit markers appear.

Not checked: a live click-through in a browser, the recording (carried from the first check), and every 1920 shot (sampled gofast_range_1920).
