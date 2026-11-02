# CP-07 independent review (M6: exports and wrap)

Reviewer: independent checkpoint reviewer, 11/02/2026, at commit cbe726e. Nothing in the repo was edited except this file.

## Verdict per criterion

| Criterion | Verdict | Evidence |
|---|---|---|
| 1. The exported cases validate against the case files schema | **PASS** | `.venv\Scripts\python.exe tools\validate_cases.py` prints 4 passed, 0 failed, exit 0. The validator is a real 2020-12 check: `Draft202012Validator.check_schema(schema)` then `iter_errors` per file. Six deliberately broken copies of `gimbal.json` in my scratch area: 5 FAIL as they should (missing `verdict`, `schema_version` 9.9, `decisive` as a string, bad `sha256`, empty `commit`); the one with an extra top-level field PASSES, which is by design (`additionalProperties: true`, stated in `schemas\README.md`). A fresh re-export at HEAD to scratch is identical to the committed files in every key except `provenance`, so the files are current. |
| 1a. Verdict rule as claimed, same for every case, not stronger than the results | **PASS** | `build_verdict` in `tools\export_cases.py` is the rule CP-07 states (LR 10 margin AND no flip from the no-exclusion refit, from a rotation-noise crossover within 0.5x to 2x of the data-only sigma, or from the recovery test), one code path for all three videos. Checked against `data\derived\*\results.json` and `recovery*.csv`: GIMBAL 0.35 deg H-BAL -355.557 vs H-SLOW -359.313 (margin 3.757); no-exclusion refit leader H-WIT 35.33; crossover 0.53 deg (main 0.675) to H-AC; H-BAL wins data from H-AC, H-ART, H-SLOW, H-WIT. GOFAST H-BAL -1028.506 vs H-ART -1034.375 (5.87); no-exclusion leader H-ART; recovery H-ART, H-SLOW, H-WIT. FLIR1 H-WIT -2582.33 vs H-ART -2616.63 (34.30); exclusions identical; nearest crossover above 11.86 deg is 12.754 to H-ART; H-WIT wins H-CLOSE-made data. All match the case files, and all three are `decisive: false`, which matches `docs\results\gimbal.md`, `gofast.md`, `flir1.md` and `recovery.md`. Nothing is stronger than the results. |
| 1b. Hashes, provenance, PURSUE counts | **PASS** (with a note) | Video SHA-256 in the case files equal `data\videos\MANIFEST.json` for all four sources, and I re-hashed GIMBAL and GOFAST on disk: match. Testimony YAML and `triage.csv` hashes match my own hashes. `triage.csv`: 134 rows, 16 Bounded, 118 Not viable, 0 Full; `pursue-triage.json` says the same. Provenance commit is `1453f10` with `working_tree_clean: false`: honest, but the exports were written before `c5af379` committed their FLIR1 discriminators input, so that commit alone does not reproduce them (see nice-to-fix). |
| 2. A 2-minute highlight recording | **PARTIAL** | `ffprobe`: 120.07 s, 1440 x 900, H.264, 15 fps, 1801 frames. I pulled one frame from each of the 14 segments: captions are legible (white on a dark box) and the views match the captions' subjects. But three captions claim more than the results pages (must-fix 1 to 3 below). |
| 3. README for a non-programmer | **PARTIAL** | The five views and "How to read a range curve" are clear and in plain words. Every command is one line, fenced `powershell`, starts with `cd "C:\Users\stewa\Documents\Claude\Sensor forensics";`, chains with `;`, no `&&` or bash syntax, and every script and argument exists (`tools\serve.py`, `tools\fetch_videos.py`, `extract.frames <video> <case>`, `tools\build_app_data.py`, `tools\gate.py`, `solve.score gimbal --procs 6`). But the scripts and files inside the commands are relative (`tools\serve.py`, `data\videos\GIMBAL_navy2020.wmv`), not full paths as M6 and Stewart's standing rule require (`schemas\README.md` does it right). The GIMBAL and GOFAST plain-words bullets carry the same overclaims as the captions. |
| No em dashes | **PASS** | 0 occurrences of U+2014 or `&mdash;` in `README.md`, `checkpoints\CP-07.md`, `schemas\README.md`, the schema, `tools\record_highlights.py` captions, and the four case files. |

Tests: `tools\gate.py` rerun by the reviewer: GATE PASS (290 pytest, 0 skipped; node tests pass).

## Overall: SEND BACK

The case files are solid. The recording and README overstate three findings in exactly the place a reader looks first.

## Must-fix

1. **GIMBAL range claim** (caption segment 6 in `tools\record_highlights.py` SEGMENTS, and the GIMBAL bullet in `README.md`): "Every physical model needs about 12 nmi or more ... A radar range would settle it." `docs\results\gimbal.md` line 457: at 0.35 deg every physical model is at 15 nmi or more near the end and a radar range of 10 nmi or less would rule out all four; "At 0.7 deg this does not hold: the balloon fits at 9.0 to 13.6 nmi." The "about 12" figure is the 0.7 deg value (11.9, G-T13 table) paired with the 0.35 deg conclusion. Also H-CLOSE, a physical model, fits at 2.0 nmi (it fails on other criteria). Say which field of view, and that radar settles it only at 0.35 deg.
2. **GOFAST wind claim** (caption segment 11 and the GOFAST bullet in `README.md`): "an independent wind would separate them" / "is the measurement that would". `docs\results\gofast.md` lines 205 and 206: a wind good to 3.9 kt separates the balloon from the free path both ways, the slow flier only one way, and "The slow flier and the glare-on-a-target model are the same physics on GOFAST" with no measurement separating them. The README bullet also omits the main case-file sensitivity: without the D-016 size exclusion the glare-on-a-target model leads.
3. **Prior work caption** (segment 9): "Prior work reproduced from its own inputs" while the frame shown says "a reproduction check fails" in red for both Peings and von Rennenkampff paths (only Sitrec passes). Say reproductions were attempted and which pass.
4. **README commands with full paths**: put the full path on every script and file argument, e.g. `.\.venv\Scripts\python.exe "C:\Users\stewa\Documents\Claude\Sensor forensics\tools\serve.py"`, as `schemas\README.md` already does.

After 1 to 3, `tools\record_highlights.py --assemble-only` should be enough (captions are drawn at assembly); then re-probe the duration.

## Nice-to-fix

- Re-export from a clean tree at the CP-07 tag so `provenance.commit` reproduces the files and `working_tree_clean` is true.
- The FLIR1 verdict says data made by H-CLOSE were won by H-WIT, "so this data cannot tell those explanations apart", yet on the real video H-CLOSE is about 1.7 million log units behind. The phrase is about the synthetic recovery test; reword it ("in synthetic tests, ...") or limit the recovery reason to explanations that are close on the real data. The verdict does not change (the sigma crossover alone makes FLIR1 not decisive).
- GOFAST has no rotation criterion, so the rotation-noise check does not apply, but the case file does not say so. Add a condition line so the reader knows all three checks were considered.
- Verdict sentences mix IDs and labels ("H-AC leads instead" next to "Balloon drifting with the wind"). Use labels throughout.
- The schema's `decisive` description and `schemas\README.md` give only the LR 10 condition; add the three robustness checks so another project reading the schema applies the same rule.
- `README.md` has no command for exporting and validating the case files or for rebuilding the recording; link `schemas\README.md` or add the two lines. Prose paths (`docs/results/`, `DECISIONS.md`) are relative; Stewart's rule prefers full paths there too.
- Captions sit over the timeline strip at the bottom; harmless, but they hide the track rows during the tour.

## Gate

Rerun by the reviewer at cbe726e: `pytest: 290 tests, 0 failures, 0 errors, 0 skipped`, `node --test: exit 0`, `GATE PASS`.
