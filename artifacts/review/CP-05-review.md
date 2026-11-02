# CP-05 independent review (M4, the web app)

Reviewer: independent checker, 11/02/2026, commit 541d233 (working tree had the FLIR1 discriminators job running; left alone).

## Verdict: SEND BACK

The app works and the recording really is frame-locked. Three problems need fixing: the Range explorer draws invalid ranges as real numbers, it can't be read at 1440 x 900, and CP-05 misdescribes what the object frame-lock number measures.

## Per criterion

| Criterion | Verdict | Evidence |
|---|---|---|
| Screenshots of every view | Partial | All 30 view shots plus 4 state shots exist (11/02 01:19 to 01:20), and every view renders without errors. Rail totals match `data/derived/<case>/results.json` for GIMBAL 0.35 and 0.70, GOFAST and FLIR1. The ledger's "Refit without exclusions" column matches `no_exclusions` (for example GIMBAL 0.35 H-WIT 35.3 / -22.6, H-BAL -115.1 / -261.7; 0.70 H-WIT 35.4 / -20.7). The "Read first" flags are correct: GIMBAL has 4 (2 scorer flags, Rule X with H-WIT leading, and "below 0.53 deg H-AC"), GOFAST has 2 (Rule X, H-ART), FLIR1 has 1 ("above 12.75 deg H-ART", where the crossover is 12.754). The Range explorer, however, is broken (must-fix 1 and 2). |
| 60 s GIMBAL recording, re-render locked | Pass | ffprobe: 60.03 s, 1440 x 900, h264, 1799 frames = 1031 + 2 x 384. I read the on-screen counter at t = 1, 10, 20, 30, 34.3, 34.5, 40, 47, 55 and 59.9 s and got 30, 300, 600, 900, 1028, 648, 731, 836, 956 and 1029, which equals the timing formula in both parts. The video pixels match the captured PNG of that same index and not its neighbours. `tools/record_gimbal.py` waits for `state.frame === i` and for `ck-img` to load `f{i:06d}.jpg`, then waits two animation frames before each shot, and cockpit `draw()` renders synchronously on a frame change. |

Tests: `node --test` passed 14/14. `tools/gate.py` gave GATE PASS (290 pytest tests, 0 skipped), even with the concurrent job running.
Em dashes: none in CP-05.md, app/index.html, app/js, app/css, app/data or docs/design/app.md.
Frame-lock table: matches framelock.json (horizon 2.12 to 2.53 px, H-CLOSE 5.01 to 5.81 px; object 1.86 / 1.41 / 5.80 px).

## Must-fix

1. **Range explorer plots invalid grid points as data.** In `app/data/gofast/range_curves.json`, the rows at 10 to 60 nmi have `valid_* = 0` and null values. `range.js` computes `p[key] * scale`, which turns null into 0, and `clamp1` then raises that to 1. GOFAST's charts therefore show every hypothesis at 1 kt air speed and 0 ft altitude from 10 to 60 nmi, when these points are geometrically impossible (the object would be below sea level). Drop the invalid points or mark them.
2. **Range explorer can't be read at 1440 x 900.** All three `*_range_1440.png` shots show the four charts scaled down to roughly 60 percent of their panels, because the SVG is at least 150 px tall but sits in a shorter box. The text is about 6 px high and labels overlap: in GOFAST and FLIR1, "Mach 1 (ISA...)" sits on top of "airliners, 400 to 500 kt". The 1920 shots are readable.
3. **CP-05's explanation of the object error is wrong.** In `geom.predictedImage` and `tools/app_predictions.py`, the camera looks along obj - jet, so the predicted object always projects onto the picture centre (317.5, 239.5 or 173.5, 131.5). The object number is just the measured blob's distance from the picture centre, so it is the same for every hypothesis by construction. It does not test the pod model or the re-render. CP-05 needs to say so, and to say that GOFAST and FLIR1 therefore have no frame-lock measure that depends on the hypothesis. The FLIR1 explanation ("small, low contrast") is unsupported and may really be the pod's tracking offset.

## Nice-to-fix

- At 1440 x 900, GIMBAL's two key flags (Rule X with H-WIT leading, and the rotation crossover) are below the fold in the rail, and the second flag is cut off mid-line in every 1440 GIMBAL shot.
- The rail shows the envelope totals -1,078.9* (GOFAST H-WIT) and -1,008,845.0* (FLIR1 H-SLOW), while results.json has -1,079.1 and -1,008,845.6. The asterisk is explained only in a tooltip, and the ledger shows the same numbers with no asterisk. CP-05 says "client totals equal Python" without mentioning this. The parity test's relative tolerance of 1e-6 hides the FLIR1 gap of 0.6.
- The rail says "1 flags".
- 14 stale `shell_*.png` files from 11/01 sit in artifacts/cp05 and are not listed in CP-05. Remove or label them.
- The GOFAST Rule X flag names H-ART, which is outside GOFAST's design set. Say so.
- The "Half speed" caption in the recording covers the timeline lanes.

Not checked: a live click-through in a browser, every 1920 shot one by one (sampled 2), and the compare views for GOFAST and FLIR1.
