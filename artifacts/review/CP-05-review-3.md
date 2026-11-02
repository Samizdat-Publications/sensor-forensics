# CP-05 (M4, the web app): third check

Reviewer: independent checker, 11/02/2026, HEAD cbe726e, working tree clean.

## Verdict: PASS

Both second-check must-fixes are fixed and show in screenshots taken after the code changes (app.css 01:51, cockpit.js and range.js 01:50, all 1440 and 1920 shots 01:52, recording 01:55). The 60 s recording is still 60 s and frame-locked. The JS tests pass. No em dashes in checkpoints/CP-05.md.

## Acceptance criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| Screenshots of every view | Pass | All five views are present for all three cases at 1440 and 1920 (artifacts/cp05/). I reopened gimbal_range, gofast_range, flir1_range, gimbal_cockpit, gofast_cockpit, flir1_cockpit and gimbal_compare at 1440. All render normally. |
| 60 s GIMBAL recording, re-render locked to the original | Pass | artifacts/movies/gimbal_framelock_60s.mp4 is 1440 x 900, 29.97 fps, 1799 frames, 60.03 s. I pulled frames at three times. At t = 10 s the counter reads 0300 (expected 299.7). At t = 33 s it reads 0990 (expected 989.0; within one frame of the seek). At t = 50 s it reads 0881 (expected 647 + 15.6 x 14.985 = 880.8), the "Original" header says "frame 881", and the "Half speed, frames 647 to 1030" caption is shown. The re-render blob sits at the frame centre. |

## Second-check must-fixes

| Must-fix | Verdict | Evidence |
|---|---|---|
| A. Chart reference labels read cleanly over the data curves | Pass | range.js `chart()` now gathers band, threshold and Mach-curve labels into a `labels` array and draws them in `<g class="labels">` after the curves and markers (line 83). app.css:233 gives them a 6 px `ink-1` halo (`paint-order: stroke`). In 3x crops of gimbal_range_1440.png, "2.3 below the best: likelihood ratio 10" is now fully legible. Curve fragments show only in the gaps between words, not across the glyphs. "airliners, 400 to 500 kt", "Mach 1", "birds" and "balloon" also read cleanly. The same holds in gofast_range_1440.png and flir1_range_1440.png ("airliners" over the white probe curve). |
| B. The cockpit strip names the object metric for what it is | Pass | cockpit.js:239 now reads "Object offset from frame centre (same for every hypothesis), median", with a tooltip that says it does not test any hypothesis. The per-frame item is now "object offset". This is visible in gimbal_cockpit_1440 (1.9 px, 1,031 frames), gofast_cockpit_1440 (1.4 px, 771) and flir1_cockpit_1440 (5.8 px, 1,655). The values match framelock.json as reported by the second check. |

## Other checks

- `node --test tests/js/geom.test.mjs tests/js/scoring.test.mjs`: 14 tests, 14 pass, 0 fail.
- checkpoints/CP-05.md: 0 U+2014 characters and 0 `&mdash;` entities.

## Must-fix

None.

## Nice-to-fix (cosmetic, not blocking)

1. The range-chart cursor line is drawn after the labels (range.js:84), so it crosses a label when the slider sits under one. In gofast_range_1440.png it passes through "the" in "2.3 below the best" and through "drifts" in the balloon label. Both stay readable. Drawing the cursor before `<g class="labels">` would fix it.
2. The halo does not cover the spaces between words, so dashed curves still show in those gaps (for example in GIMBAL's "best: likelihood" and FLIR1's "airliners,  400"). A filled background rect behind each label would remove this.
3. The strip is still titled "Frame lock" while its object metric is not a lock measure. The metric's own label now says this, so it is acceptable.
4. In gimbal_compare_1440.png the x-axis title "time in the clip, s" under the two lower charts is cut off by the transport bar at 1440 x 900. The view scrolls, so this is minor.
