# CP-04 independent review, third check

Reviewer: independent check, 11/02/2026. Commit reviewed: 8631b09 ("CP-04 second-check fixes ..."), working tree clean. Earlier checks: `artifacts/review/CP-04-review.md`, `artifacts/review/CP-04-review-2.md` (read for the must-fix list only; every item below was rechecked against code and data files).

Gate rerun by the reviewer: `.venv\Scripts\python.exe tools\gate.py` gives 290 tests, 0 failures, 0 errors, 0 skipped, node exit 0, GATE PASS.

**Overall: PASS.** All five must-fixes from the second check are done in code and in the result files, not only in prose. I reproduced the FLIR1 crossover independently through the main scorer. Every number I checked in CP-04 matches `results.json`, the score CSVs and `sigma_refit.json`, apart from one rounding slip of 0.05. What is left is wording, listed under nice-to-fix.

## Acceptance criteria

| Criterion | Verdict | Reason (evidence) |
|---|---|---|
| 1. A results table per video (GOFAST, GIMBAL, FLIR1) with per-criterion scores and range curves | Pass | `docs/results/gofast.md`, `gimbal.md` (both FOVs) and `flir1.md` give both totals both ways, per-criterion rows for both fits, best-fit objects and per-hypothesis range curves. CP-04's totals table (CP-04.md:38-55) matches `data/derived/{gofast,gimbal,flir1_navy}/results.json` for every row I checked (all GOFAST, GIMBAL main and `no_exclusions`, FLIR1). GOFAST's curve now has points at 3.5, 3.7, 3.85, 4.0 and 4.5 nmi (`range_curves.csv`: H-BAL -1,177.4 / -1,032.5 / -1,300.5 at 3.7 / 3.85 / 4.0), and the PNG ticks are readable. |
| 2. Equal treatment: one scoring path, no name branching, same geometry, scoring and testimony for all | Pass | The new code (`score.py` `sweep_sigmas`, `leader_crossovers`, `rotation_sigma_sweep`, `refit_at_rotation_sigma`, `resweep`; `case_data.py:292-299, 432-435`; `tools/sigma_refit.py`) has no hypothesis-id literals or `.id`/`.label` compares. The sigma override is set in `load_case` for the whole case. `_fit_pair` builds the same task `(case, variant, True, h, sigma)` for every hypothesis. `leader_crossovers` takes ids only as opaque keys, and `tests/test_sigma_sweep.py::test_crossover_ignores_the_name` checks that. The only branches are on rotation `kind` (`likelihoods.py:188-190, 243`; `score.py:654-655`), the design's glare/physical split, plus reporting code that filters dataframes by hypothesis. `tests/test_equal_treatment.py` passes. |

## Second check's must-fixes

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | FLIR1 sigma sweep brackets 11.86 deg, crossover reported, refits, conditional wording | Pass | Grid in `flir1_navy/results.json` runs 0.88 to 23.72 deg and includes 8.44, 13.05, 15.65. Crossovers stored: physics-only H-WIT to H-ART at 12.754 and H-ART to H-AC at 14.8; testimony-weighted H-WIT to H-ART at 12.958. **Reproduced independently.** I rebuilt the case with `load_case("flir1", rotation_sigma_deg=s)` and called `score.score()` on the stored best fits, not the sweep helper. Physics-only: H-WIT leads at 12.70 (-2,598.06 against H-ART -2,599.97) and H-ART leads at 12.80 (-2,598.46 against -2,599.98). Testimony-weighted: H-WIT leads at 12.95 (by 0.23) and H-ART at 13.00 (by 1.5). H-ART/H-AC swap between 14.7 and 14.9. `sigma_refit.json` holds full refits at 13.0 and 15.65 through `_fit_pair`, with the override noted as case-level. The numbers in CP-04.md:75 and flir1.md:152-159 match the file. Conditional wording: CP-04.md:71 and flir1.md:12-14 both say 11.86 exceeds the physical held-out RMS of 8.4 deg and that FLIR1 does not decide physical against glare. |
| 2 | GOFAST range curve near 3.85 nmi, can/cannot sentence, ticks | Pass | `solve/cases/gofast.yaml` `range_curves_extra_nmi`; `range_curves.py` `grid_for`, the same for every hypothesis. gofast.md:158-160 lists the peak points and says the curve "confirms where the readout puts the object; it does not separate the hypotheses". The same point is made in CP-04.md:69. The PNG has clean ticks (0.5, 1, 2, 3, 5). The total panels are still near-spikes, but the page explains why. |
| 3 | gimbal.md rotation wording | Pass | gimbal.md:246 and :302 both give the gap (3.5 and 5.0) and then the same "not a clear separation" sentence. One rule produces it: `results_report.py:868-873` (held-out RMS / sigma >= 2). The "likelihood ratio under 100" sentence now names its own gap (`results_report.py:874-875`) and does not fire at GIMBAL. The -71.4 deadband figure stands alone. |
| 4 | CP-04 plain words 13.8 to 21 nmi at 0.35 deg; all numbers rechecked | Pass | CP-04.md:70 gives "13.8 to 21.2 nmi at 0.35 deg, 11.8 to 20.6 at 0.7". This matches gimbal.md:52-73 (H-WIT 13.8 to H-SLOW 21.2; H-BAL 11.8 to H-SLOW 20.6). Also checked: the 6.2 / 0.3 leads, the 3.5 / 5.0 gaps, "within 4.7" (physics-only gaps 3.8 to 4.7), the 0.53 / 0.535 / 0.657 crossovers, the FLIR1 34 to 38 gap, the 268 rotation gap, 108 for the pitch bound, the recovery counts (4 of 6, 2 of 6) and the shortfalls (2.6, 1.5, 2,309). One slip: CP-04.md:71 says "by 77.6"; `sigma_refit.json` gives 77.548 (77.5). |
| 5 | Pre-registration timing unverifiable | Pass | CP-04.md:13, REVIEW-M3.md:148 and DECISIONS.md:22 (D-018) each say git cannot confirm the order (69b5938) and that the rules were requested by the review. |

## Other checks

- Plain words against recovery: GOFAST ("cannot tell them apart"), GIMBAL ("not a discrimination"; glare data won by the balloon 4 of 6 and 2 of 6) and FLIR1 (glare/physical split holds, one H-CLOSE set won by H-WIT) match `docs/results/recovery.md`. FLIR1's plain words claim less than recovery does, because they defer to the sigma doubt. Nothing overclaims.
- Em dashes (U+2014, `&mdash;`, `&#8212;`): none in CP-04.md, docs/results/*.md, README.md or DECISIONS.md.
- Second check's nice-to-fix items: floor labels "outside the constraint" are present; optimizer shortfall is disclosed on all three pages; `--part` writes and `--merge` merges `scores_no_exclusions_part_*.csv` (`score.py:1017-1025, 1139-1147`); Q-008 needed by CP-05; REVIEW-M3.md:199 is corrected; GIMBAL's sweep reaches 3.68 deg.

## Must-fix

None.

## Nice-to-fix

1. REVIEW-M3.md:3 still says the section 0 rules were written "BEFORE any of the measurements they decide were made". The first review found that git cannot confirm this (7d20dfb committed the rules and the results together). Give it the same "cannot be confirmed from git" wording as section 7.
2. CP-04.md:71 says "by 77.6"; the file value is 77.5 (77.548).
3. flir1.md:12 rounds the crossovers to 12.8 and 13.0 deg, while flir1.md:148 and CP-04 say 12.75 and 12.96. Use two decimals, so the 13.0 crossover is not confused with the 13.0 deg refit.
4. CP-04.md:81 and :85 say the app data "needs rebuilding", but this commit rebuilt it (`app/data/flir1/results.json` carries the crossovers; `app/data/gofast/range_curves.json` has 3.85).
5. `results_flir1.py:63` hard-codes "from the free-path object to a glare model" instead of deriving it from `leader_below` / `leader_above`. It is correct today but would go stale on a rerun.
6. FLIR1: the rescored sweep puts H-AC in the physics-only lead from 14.8 deg, while the refit at 15.65 has H-ART ahead (-2,578.6 against -2,581.6). Both are glare models and the difference is within optimizer noise. Add a one-line note.

## Files

- C:\Users\stewa\Documents\Claude\Sensor forensics\checkpoints\CP-04.md
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\results\flir1.md, gimbal.md, gofast.md, gofast_range_curves.png, REVIEW-M3.md
- C:\Users\stewa\Documents\Claude\Sensor forensics\data\derived\flir1_navy\results.json, sigma_refit.json
- C:\Users\stewa\Documents\Claude\Sensor forensics\solve\score.py, case_data.py, range_curves.py, results_report.py, results_flir1.py
- Reviewer's crossover reproduction (read-only): C:\Users\stewa\AppData\Local\Temp\claude\C--Users-stewa-Documents-Claude-Sensor-forensics\425b57e2-f1bc-42a3-a213-5a4ce9211fe6\scratchpad\r3\xover.py
