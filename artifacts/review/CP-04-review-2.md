# CP-04 independent review, second check

Reviewer: independent check, 11/02/2026. Commit reviewed: 69b5938 ("CP-04 must-fixes ..."). First review: `artifacts/review/CP-04-review.md`.

Gate rerun by the reviewer: `.venv\Scripts\python.exe tools\gate.py` gives 284 tests, 0 failures, 0 errors, 0 skipped, node exit 0, GATE PASS.

**Overall: SEND BACK.** The four must-fixes were really done in code and in the results, and the totals table in CP-04 matches `results.json` cell for cell. But the rotation noise rule (b) left one hidden sensitivity the sweep cannot show: at FLIR1 the leader flips from the free path to the glare models if the rotation sigma is about 10 percent larger than the value used. The FLIR1 sweep only goes downward. There are also three wording errors in reader-facing text and one wrong number in the plain-words section.

## Acceptance criteria

| Criterion | Verdict | Reason (evidence) |
|---|---|---|
| 1. A results table per video with per-criterion scores and range curves | Partial | Tables: pass. `docs/results/gofast.md`, `gimbal.md` (both FOVs) and `flir1.md` show both totals, both ways, k, best-fit objects and per-criterion scores for both fits. I recomputed all 34 cells of CP-04's totals table from `data/derived/*/results.json` and they all match. `scores_no_exclusions.csv` sums match `results.json` `no_exclusions` for GOFAST and both GIMBAL FOVs. Range curves: GIMBAL and FLIR1 pass. GOFAST does not. The grid in `solve/range_curves.py:33` (0.5, 1, 2, 3, 5, ...) has no point near the on-screen 3.85 nmi. The best grid point is -8,063 (H-WIT at 3 nmi, `data/derived/gofast/range_curves.csv` row 54), against -1,028 to -1,065 for the main fits. So the GOFAST total-versus-range panels in `docs/results/gofast_range_curves.png` show only one spike, and their x tick labels overlap. The line "Ranges within 2.3 log units ... 3.0 to 3.0 nmi" for every hypothesis (gofast.md, Per-hypothesis curves) is misleading. |
| 2. Equal treatment: one scoring path, no name branching, same geometry, scoring and testimony for all | Pass | One public path (`solve/score.py`: `score`, `fit`, `run_case`). `tests/test_equal_treatment.py` passes: it scans every `solve/*.py` for id and label literals and for `.id`/`.label` compares, checks that renaming or reordering leaves scores unchanged, checks that fits are name-blind, and checks that every hypothesis gets the same claim set. My own grep found branches only on rotation `kind` (glare against physical, the design's stated split, `likelihoods.py:188-191`) and in reporting code (`results_report.py:513, 727`; `results_flir1.py:254`; `recovery.py:309`). Testimony at GIMBAL: 9 rows for every hypothesis, with the same claims and weights. Rotation noise, folds, knot list and n_eff come from the case, so they are identical for all (`score.py:258-269`). |

## First review's must-fix items

| Item | Verdict | Evidence |
|---|---|---|
| (a) Totals with and without the post-hoc exclusions | Pass | Code: `load_case(exclusions=False)` (`case_data.py:499-507`) and `score._run_both` (`score.py:895-913`) do a full refit through the same path. Results: `no_exclusions` blocks in GOFAST and GIMBAL `results.json`, plus `scores_no_exclusions.csv` (GOFAST 120 rows, GIMBAL 216 rows). Tables and a plain sentence appear on each page (gimbal.md:84-116, gofast.md, Rule X section). FLIR1 has no weight override (size and brightness pass Rules B, D-016 and D-017 there), so it reports "identical", and `scores.csv` shows weight 1 on every criterion. CP-04 now says the exclusions decide the GIMBAL ranking (H-WIT first and H-BAL fifth without them) and that GOFAST flips to H-ART. Both statements match the files. |
| (b) Rotation noise from data, sigma sweep, H-WIT BIC (k above n) resolved | **Partial** | Done: data-only sigma (`case_data.py` `_rotation_noise`; `gimbal.yaml` and `flir1.yaml` `noise_method: two_threshold`). Blocked cross-validation of the free rotation terms (`likelihoods.py:152-217`, dof 0). Every k is now below n: H-WIT k = 16 against n = 45.5 at GIMBAL. GIMBAL sweep: leader stable from 0.88 to 3 deg (gimbal.md:205-214), and H-BAL's lead over the glare models grows with sigma. **Not done:** the FLIR1 sweep uses the same 0.88 to 3.0 deg grid (`score.py:733`), entirely below FLIR1's sigma of 11.86 deg (flir1.md:127-136), so it cannot test the direction that matters. I rescored FLIR1's stored best fits at larger sigmas with the scorer's own `rotation_terms` (not refitted). Physics-only: at 12.5 deg, H-WIT -2,594.2 against H-ART -2,603.3; at 13.0 deg, H-ART -2,595.7 against H-WIT -2,603.8. Testimony-weighted: H-ART -2,686.8 against H-WIT -2,688.3 at 13.0 deg. At 15.6 deg (the glare fit's own held-out RMS), the glare models lead by about 73 (physics-only). The estimate itself is also doubtful at FLIR1. The "measurement noise" (11.86 deg) is larger than the physical fit's whole held-out residual RMS (8.4 deg, flir1.md:120), so the two-threshold assumption of equal, independent errors fails, as REVIEW-M3 section 8 already concedes for GIMBAL in the other direction (0.25 deg, "underestimates"). GIMBAL's sweep also stops at 3.0 deg, below the held-out RMS of 3.66 deg (minor: the trend there is monotone). |
| (c) G-T25 1,000,000 ft sentinel removed, no double scoring with G-T11 | Pass | `models/base.py:153-172`: the radius is NaN for a path that does not reverse, and the cap line is gone. `testimony.py` (the `given` block, around lines 387-444) contributes 0 when the condition is false. `scorable.yaml` G-T25 has `given: {quantity: stops_and_reverses, value: true}`. Results: every GIMBAL fit that does not reverse shows G-T25 = 0.0 with `applies: False`, and H-WIT (which reverses at both FOVs) scores -0.38 and -0.40. G-T11 alone scores the reversal (-2.3 against -0.1). No other radius cap remains in `solve/`. |
| (d) Per-hypothesis range curves with ERA5 winds, each video | Partial | `solve/range_curves.py` refits both totals at fixed range for every hypothesis with a range parameter. `results.json` environment is ERA5 for all three cases. CSVs and PNGs exist for all three videos, with H-CLOSE limited to its prior. GIMBAL and FLIR1 are informative (gimbal.md:322-364, flir1.md:202-223). GOFAST: see criterion 1 (the grid misses the on-screen range). |

## Other findings (no criterion covers them)

1. **Misleading sentence, gimbal.md:237.** Produced by `results_report.py:792-797`: "changes the rotation score by -71.4 after its penalty. That is a likelihood ratio under 100". The "under 100" refers to the 3.5-unit glare-against-physical gap, not to the -71.4 that comes just before it (a factor of about e^71). Read as written, it is false.
2. **The two GIMBAL FOVs give opposite readings for the same criterion.** At 0.35 deg the rotation "does not clearly separate" (gimbal.md:237). At 0.7 deg "the pod geometry predicts the rotation better" (gimbal.md:284). The 3.5 and 5.0 log-unit gaps fall on either side of a hard 4.6 threshold (`results_report.py:794`), and both are computed at a sigma (0.68 deg) that is 5 times below the held-out residual (3.6 deg). CP-04 says it does not separate. The 0.7 deg page should say the same.
3. **Wrong number in CP-04's plain words.** "testimony-weighted: 11.8 to 21 nmi at 0.7 deg, 15.7 to 21 nmi at 0.35 deg". At 0.35 deg the H-WIT testimony-weighted fit is at 13.8 nmi (gimbal.md:58), and H-WIT is a physical model (rotation kind physical), so the range is 13.8 to 21.2.
4. **Pre-registration claim again unverifiable.** CP-04 ("methods written into REVIEW-M3.md section 7 before they were run"), REVIEW-M3.md:148 and D-018 all make this claim. Section 7, D-018 and every result were committed together in 69b5938, so git cannot confirm it. This is the same pattern the first review failed. The rules were demanded by the review, so the claim carries little weight, but it should be stated as unverifiable or removed.
5. REVIEW-M3.md:199 says "H-SLOW (0.7 deg) fits that do reverse". In `results.json`, H-SLOW does not reverse at 0.7 deg; H-WIT reverses at both FOVs.
6. Floor values print as numbers. `LOG_FLOOR = -1e6` (`likelihoods.py:32`) in the constraint prior gives FLIR1 H-SLOW -1,008,845.6 (prior row -1,000,500) and GIMBAL range-curve entries of -2,000,390. The ranks do not change, but these magnitudes mean "outside the altitude constraint", not a likelihood.
7. FLIR1 range-curve points beat the main fits: H-AC -2,618.0 at 1 nmi against -2,620.6, and H-WIT -2,580.9 at 2 nmi against -2,582.3, even though the curves use fewer starts. The main fits are short of their optimum by up to 2.6. This does not change the FLIR1 ranks at sigma 11.86, but it should be disclosed.
8. `score.py:973` discards the no-exclusion rows in `--part` mode, and `_write_variants` never writes `scores_no_exclusions.csv`. So the documented `--part ... --merge` workflow would leave a stale CSV. The shipped GIMBAL CSV is consistent, because it was made by `run_case`.
9. QUESTIONS.md:14 still lists Q-008 as "Needed by CP-04, Open". CP-04 says CP-05.
10. Em dashes: none (U+2014, U+2013 and entity forms) in CP-04.md, docs/results/*.md, scoring.md or DECISIONS.md.

## Must-fix (send back)

1. **FLIR1 rotation sigma sensitivity.** Extend the FLIR1 sweep upward to bracket 11.86 deg (for example 8, 10, 12, 13, 15, 20 deg), refitted or at least rescored. Report the crossover (about 13 deg), and condition CP-04's FLIR1 plain words and flir1.md "In short" on it. Also state that the two-threshold estimate exceeds the physical fit's residual RMS at FLIR1. The current "leader at each sigma: H-WIT" line (flir1.md:136) gives false comfort.
2. **GOFAST range curve.** Add grid points around the on-screen range (for example 3.5, 3.85, 4.0, 4.5 nmi through the case's `range_curve_nmi`), or state on gofast.md and in CP-04 that the per-hypothesis total curve is not informative on GOFAST because the range is read on screen. Fix the "3.0 to 3.0 nmi" line and the overlapping tick labels.
3. **gimbal.md rotation wording:** move or reword the "likelihood ratio under 100" sentence so it refers to the 3.5 gap, and make the 0.7 deg paragraph agree with CP-04 (no separation at a sigma that understates the held-out residual fivefold).
4. **CP-04 plain words:** 0.35 deg testimony-weighted range is 13.8 to 21 nmi, not 15.7 to 21.
5. **Pre-registration wording** in CP-04, REVIEW-M3 section 7 and D-018: say the timing cannot be confirmed from git (same commit as the results), or drop the claim.

## Nice-to-fix

- Extend GIMBAL's sweep to the held-out RMS (about 3.7 deg).
- Correct REVIEW-M3.md:199 (H-WIT at both FOVs, not H-SLOW).
- Label floor-dominated totals (LOG_FLOOR) as "outside constraint" in tables and range curves.
- Disclose the FLIR1 optimizer shortfall (range-curve points above the main fits).
- Write and merge `scores_no_exclusions.csv` in the `--part`/`--merge` path.
- Update Q-008's "Needed by" in QUESTIONS.md.

## Files

- C:\Users\stewa\Documents\Claude\Sensor forensics\checkpoints\CP-04.md
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\results\flir1.md (lines 116-140)
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\results\gimbal.md (lines 58, 237, 284)
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\results\gofast.md (per-hypothesis curves), gofast_range_curves.png
- C:\Users\stewa\Documents\Claude\Sensor forensics\solve\score.py (lines 733, 973)
- C:\Users\stewa\Documents\Claude\Sensor forensics\solve\range_curves.py (line 33)
- C:\Users\stewa\Documents\Claude\Sensor forensics\solve\results_report.py (lines 792-803)
- Reviewer's rescoring script (read-only): C:\Users\stewa\AppData\Local\Temp\claude\C--Users-stewa-Documents-Claude-Sensor-forensics\425b57e2-f1bc-42a3-a213-5a4ce9211fe6\scratchpad\flir_sweep.py
