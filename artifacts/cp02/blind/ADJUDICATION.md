# CP-02 blind check: result and adjudication

Date: 10/31/2026.

## How it was done

- `tools/sample_frames.py --seed 2026 --n 100` picked 100 frames per video (GIMBAL and GOFAST) and rendered sheets of raw field crops (4x) with frame numbers only, never our readings.
- A fresh verifier subagent (Opus), told not to open any derived data or code, typed every cell into `<case>/verifier.csv`, with notes on ambiguous cells in `<case>/verifier_notes.md`.
- `tools/score_blind.py` compared the two after the same normalization: `<case>/score.json`.

## Raw result (as scored, before any adjudication)

| Video | Cells | Disagreements | Rate |
|---|---|---|---|
| GIMBAL | 800 (8 fields) | 5 | 0.63% |
| GOFAST | 1000 (10 fields) | 3 | 0.30% |
| Both | 1800 | 8 | 0.44% |

Per field (raw): GIMBAL azimuth 3/100, airspeed 2/100, all others 0/100. GOFAST clock 2/100, altitude 1/100, all others 0/100 (including range and closure).

Against the target of at most 1% per digit field, four fields miss on the raw count: GIMBAL azimuth and airspeed, GOFAST clock (and GOFAST altitude sits exactly at 1%).

## Adjudication (each disagreement checked by eye with the frames before and after)

Evidence image: `adjudication.png` (the frame in red, its neighbors in gray, 5x).

| Video, frame, field | Verifier | Lab | Finding |
|---|---|---|---|
| GIMBAL f4 airspeed | 239 | 238 | Crop reads 238 (the verifier noted 8 vs 9 as ambiguous). Lab correct. |
| GIMBAL f12 airspeed | 239 | 238 | Same. Lab correct. |
| GIMBAL f152 azimuth | 48L | 47L | Transition frame: the interlaced fields show 48 and 47 together (48 before, 47 after). Both readings are defensible. |
| GIMBAL f194 azimuth | 45L | 46L | Frame reads 45 (46 before, 45 after). **Lab error**: one frame late on a change. |
| GIMBAL f812 azimuth | 8L | 7L | Transition frame (8 before, 7 after), interlaced mix. |
| GOFAST f694 altitude | 25010 | 25000 | Transition frame (25010 before, 25000 after). |
| GOFAST f322 clock | 4231A | 4230A | Transition frame (4230 before, 4231 after). |
| GOFAST f682 clock | 4243A | 4242A | Transition frame (4242 before, 4243 after). |

So: 1 clear lab error, 2 verifier misreads, 5 frames where the display changed between the two interlaced fields of a single frame, so the frame genuinely contains two values.

## Adjusted error rates

- Clear lab errors: 1 of 1800 cells (0.06%); GIMBAL azimuth 1/100.
- Counting the 5 transition frames as lab errors (the strictest reading): 6 of 1800 (0.33%); GIMBAL azimuth 3/100, GOFAST clock 2/100, GOFAST altitude 1/100.

## What changes because of this

1. Transition frames are real and frequent enough to matter: at each change of a readout, one frame can carry both values. The reader now has to flag them (method `transition`, both values recorded) rather than pick one. Logged as an M1 fix item.
2. The solver already treats each readout as an interval valid between 6-frame display updates (see `docs/prior-work/FINDINGS-LOG.md`), so a one-frame ambiguity at a change does not move the geometry.
3. No correction was applied to the sampled frames only (that would bias the estimate); fixes go into the reader and apply to every frame.

## Fix applied (10/31/2026)

`extract/transitions.py` compares each field crop's even and odd rows with the frames before and after; a frame whose rows split between its two neighbors is flagged as a transition, with both values (`data/derived/<case>/transitions.csv`). Result: all 5 adjudicated transition frames are flagged (split ratios 1.49 to 4.09 against a threshold of 1.3), and so is f194 (the one clear reader error), whose interval then contains the true value. The flag is conservative: 58 of 256 change-adjacent frames in GIMBAL and 75 of 259 in GOFAST are marked, and each marked frame is treated by the solver as "either value". Tests: `tests/test_transitions.py`.

Withdrawn claim (10/31/2026): an earlier version said that with transition frames read as "either value" none of the 8 disagreements is a wrong value. That hides the f194 reader error (the detector also flags f194) and was checked on the same frames. Round-1 rates are quoted raw only. Round 2 (`artifacts/cp02/blind2/`) is the independent measurement.
