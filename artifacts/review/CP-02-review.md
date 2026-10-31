# CP-02 independent review (round 2)

Date: 10/31/2026. Reviewer: independent checkpoint reviewer.

| Criterion | Verdict | Reason |
|---|---|---|
| 1. Round-2 sample | Pass | Seeds 7 (GIMBAL) and 11 (GOFAST) differ from 2026 and from each other; `np.random.default_rng(seed).choice` reproduces both frame lists exactly; overlap with round 1 is 14 and 13 frames (expected by chance); verifier.csv has 800 and 1000 rows, no duplicate (frame, field); lab outputs (Oct 30-31 02:01) predate the draw (Oct 31 19:08). |
| 2. Scoring fairness | Pass | Reruns reproduce score.json byte for byte (git clean): round 2 GIMBAL 1/800 (f377 azimuth), GOFAST 0/1000, raw = with flags. 13 verifier a/b cells (5 GIMBAL, 8 GOFAST), 13 lab-flagged cells in sample (11 shared); every a/b cell passes on the lab's single value, the 2 flagged single-value cells also match the lab's main value, so flags rescue 0 cells. Leniency is material only in round 1: flags cover 58 GIMBAL and 66 GOFAST frames (5.6% and 6.4%) and rescue 6 of 8 round-1 cells including f194, a known clean lab error. |
| 3. Spot-check images | Pass | adjudication_f377.png shows a genuinely ambiguous 35/36; 30 cells checked on GIMBAL sheet_07, sheet_04 and GOFAST sheet_06 (azimuth, clock A suffix, airspeed 241/255, mach 0.58/0.62, f676 interlaced altitude) all match verifier.csv. |
| 4. CP-02.md claims | Partial | Numbers check out, but "Commit / tag: see git show cp-02" points to a tag that does not exist (only cp-01); "every field at or under 1 percent" is a point estimate with GIMBAL azimuth exactly at the limit (95% upper bound about 5% on 1/100); the transition detector missed 2 of 5 GIMBAL azimuth two-value cells (f956, f1010), which is not mentioned. |
| 5. Gate | Pass | `tools/gate.py`: 81 tests, 0 failures, 0 errors, 0 skipped, GATE PASS. |

## Must-fix
1. Create the `cp-02` tag or correct the reference in `checkpoints/CP-02.md`.
2. In CP-02.md, state that GIMBAL azimuth sits at the 1% limit on n=100, and that the detector missed f956 and f1010 (recall 3 of 5 on GIMBAL azimuth in round 2).
3. Do not cite round-1 "with flags" figures as an error rate: they hide f194.
