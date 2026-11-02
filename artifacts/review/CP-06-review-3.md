# CP-06 independent review, third check (M5, PURSUE)

Reviewer: independent checkpoint check, 11/02/2026, at commit 59123d8. Scope: the two must-fixes and four non-blocking items from `artifacts/review/CP-06-review-2.md`, then a quick recheck of the three criteria. Only this file was written.

## What I ran myself

- `.venv\Scripts\python.exe -m tools.pursue_m5 analyse`: analysed all 8 clips. `git status` / `git diff --stat` afterwards: no change to any file under `data/derived/pursue/` (not `m5_summary.json`, not `dow-uap-pr044/summary.json`, not the other seven). The only modified file was `_PLAN.md` (CP-04 checkboxes and a PASSED line), which the analysis code does not touch (no reference to `_PLAN` in `tools/pursue_m5*.py`); it is a concurrent edit by the orchestrator, not output of the rerun.
- `.venv\Scripts\python.exe -m pytest tests\test_pursue_m5.py -q`: 15 passed, exit 0.
- My own script on `data/pursue/triage.csv` and `index.csv`: 134 rows each, same ID set; tiers Bounded 16, Not viable 118, Full 0.
- My own script on `docs/results/pursue.md`: "All 16 Bounded clips" has 16 rows, all Bounded in the CSV; "The other 126 clips" has 126 rows; all 142 reasons are identical to the CSV; tiers match except PR107, which reads "Not viable (re-tiered from Bounded, D-019)" (`pursue.md:151`), an annotation of the correct tier.
- U+2014 and its HTML entities: 0 in `checkpoints/CP-06.md`, `docs/results/pursue.md`, every `docs/audit/*.md`, `README.md`.

## Second review's must-fixes

| Must-fix | Verdict | Evidence |
|---|---|---|
| 1. PR044 correction lives in the generator; rerun reproduces; 0.67 to 1.22 m band generated | Pass | `gate_clip_inputs.json:7` holds the corrected notes (23M on 231 px at 6060, 33M on 304 px at 6090, snap to 108 px, unlabelled 144 px box at 6030). `tools/pursue_m5_analyse.py:106-108` computes `object_size_at_ratio1_m_full_extent_band` as smallest extent x smallest m/px to largest x largest (8 x 0.0833 = 0.667, 11 x 0.111 = 1.222), driven by `object_extent_px_range` [8, 11] in the inputs. Rerun left `m5_summary.json` (notes at :274, band at :288-290) and `dow-uap-pr044/summary.json` (:15, band) byte-identical. |
| 2. VERDICTS says Sixteen and gives the true reason nothing is Full | Pass | `docs/audit/VERDICTS.md:10`: "No clip shows the pod azimuth ... (PR111 keeps elevation and a slant-range-like label). Sixteen carry a scale". Counts column 16 / 118 with the 17 / 117 history and D-019. |

## Second review's non-blocking items

| Item | Verdict | Evidence |
|---|---|---|
| Audit "Why nothing is Full" | Pass | `docs/audit/pursue.md:22`: no clip shows the pod azimuth; PR111 has elevation and a slant-range-like label but no azimuth. |
| PR107 triage note | Pass | `triage.csv:89` notes: altitude from elsewhere would give only a range to the sea point, and "with no azimuth it could not become Full". |
| PR149 geometry_note qualified | Pass | `dow-uap-pr149/summary.json:68`: maximum holds over frames 15 to 89; frames 90 to 97 only if the waterline tilt is camera roll. Survives the rerun. |
| "12 to 20 percent" | Pass | `CP-06.md:15`, `CP-06.md:30`, `pursue.md:32`. No "12 to 21" left. |

## Criteria (quick recheck)

| Criterion | Verdict | Reason |
|---|---|---|
| 1. A results table for each viable clip | Pass | 0 Full; the 8 D-013 clips each have a row in `pursue.md:15-24`, and the backing `m5_summary.json` now agrees with the text and is reproduced by the code. |
| 2. A list of the not-viable clips, each with its reason | Pass | `pursue.md:67-194`: 126 rows (118 Not viable incl. PR107, plus 8 deferred Bounded), reasons identical to `triage.csv`; with the 8 analyzed, all 134 covered. |
| 3. A table of the Bounded-tier clips | Pass | `pursue.md:44-61`: one 16-row table, exactly the CSV's Bounded set. Counts 0 / 16 / 118 agree across `triage.csv`, `pursue.md`, `docs/audit/pursue.md:16-18`, `VERDICTS.md:10`, `CP-06.md:9`, `README.md:21`. |

## Minor observations (not blocking)

1. PR044 label lag: the generator notes (`gate_clip_inputs.json:7`) and `pursue.md:17` say the gate snaps to 108 px "within 0.17 s and reads 12M"; per the second review's frame check, 33M stays on the 108 px box for frames 6100 to 6103 and 12M appears by 6106. Accurate about the gate, slightly compressed about the label.
2. Hedging differs: `pursue.md:32` says "The image is not square-pixelled"; `CP-06.md:15` says "probably not". The evidence (fit to rolls up to 14 deg, an eye estimate of 1.8) supports "probably".
3. `CP-06.md:22-24` Result column still reads "To be judged by the independent check"; fill in at sign-off.

## Overall: PASS

No must-fix items.
