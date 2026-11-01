# NEXT-SESSION.md

Last updated: 11/01/2026 (weekly quota at 99 percent; Stewart will reset it)

## Where we are

- Tagged: cp-01, cp-02, cp-03. Reviews in `artifacts/review/`.
- Owner rulings D-010 to D-014, D-017; lab decisions D-015, D-016. Open questions: Q-003 (publish later?), Q-008 (FLIR1 scoring judgment calls; defaults in use).
- M3 scoring done for all three Navy videos through one path (`solve/score.py`), both totals reported, testimony weighted high (D-011):
  - GOFAST (`docs/results/gofast.md`): balloon, slow mover, glare-on-slow-target fit one path at about 13,200 ft; data cannot separate them (recovery test).
  - GIMBAL (`docs/results/gimbal.md`, both fields of view): physics-only led by the balloon model, testimony-weighted by the free path; free-path data is always won by the balloon model (not separable); rotation separates glare from physical objects.
  - FLIR1 (`docs/results/flir1.md`): free path leads both totals; glare models lose on rotation.
  - Recovery matrices: `docs/results/recovery.md`. Review decisions: `docs/results/REVIEW-M3.md`.
- M4 started: app shell committed (`app/`, three.js 0.170.0 vendored; `tools/build_app_data.py`, `tools/serve.py`; design in `docs/design/app.md`; screenshots in `artifacts/cp05/`).
- A discriminators worker (M3.6) may have left uncommitted files: `solve/discriminators.py`, `tests/test_discriminators.py`, `data/derived/<case>/discriminators.json`, `docs/results/discriminators.md`. Check `git status`; run `tools/gate.py`; commit if green, otherwise finish it.

## Do next (in order)

0. CP-04 was SENT BACK (`artifacts/review/CP-04-review.md`). Must-fix before tagging: (a) report every video's results both with and without the post-hoc data-quality exclusions (D-016/D-017/brightness), since they were not decided blind; (b) rotation-noise sensitivity for GIMBAL (sigma 0.88 vs the 1.96 deg physical residual; review says glare wins the criterion above about 1.3 deg) and fix H-WIT having more parameters (49) than the BIC sample size (45); (c) replace the G-T25 1,000,000 ft sentinel (solve/models/base.py:152) with a proper treatment and avoid double-scoring with G-T11; (d) per-hypothesis curves over range with the final winds (or state their absence); then rerun the independent check and tag cp-04. CP-04.md wording already corrected.

1. Finish/commit M3.6 discriminators (see above), add a FLIR1 section.
2. Rebuild app data (`tools/build_app_data.py --no-frames`) since GIMBAL/FLIR1 results changed; rerun the node parity test.
3. CP-04: write `checkpoints/CP-04.md` (results tables per video with per-criterion scores and range curves; equal-treatment evidence: `tests/test_equal_treatment.py`), run an independent check (verifier agent), fix, tag cp-04.
4. M4 views (cockpit re-render frame-locked, god's-eye, range explorer, compare, ledger), screenshots, the 60 s GIMBAL recording, CP-05.
5. M5 (8 frozen PURSUE clips), M6 (schema v0.1, exports, README, 2-minute recording).

## House rules for this run

- Commit after every result (quota can run out mid-task).
- When Stewart runs another heavy project, run at BelowNormal priority with one thread, or pause.
