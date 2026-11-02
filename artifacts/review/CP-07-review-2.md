# CP-07 independent review, second check (M6: exports and wrap)

Reviewer: independent checkpoint reviewer, 11/02/2026, at commit 354f250 ("CP-07 fixes"). Nothing in the repo was edited except this file. The working tree was clean before and after every command I ran.

## The first review's must-fixes

| Must-fix | Verdict | Evidence |
|---|---|---|
| 1. GIMBAL range claim (caption 6, README GIMBAL bullet) | **PASS** | Caption now reads "At 0.35 deg every leading physical fit is 15 nmi or more away (at 0.7 deg a balloon fits at 9 to 14); aircrew say 6 to 8". README: "At the documented 0.35 deg field of view, every leading physical model puts the object 15 nmi or more away by the end of the clip ... At 0.7 deg it would not: there a balloon fits at 9 to 14 nmi." Matches `docs\results\gimbal.md` line 457 (15 nmi or more at 0.35 deg; balloon 9.0 to 13.6 nmi at 0.7 deg) and the discriminators table (H-BAL vs H-SLOW at 0.7 deg: 8.98 to 13.6 nmi). "6 to 8" matches `data\testimony\gimbal.yaml` (Graves, 6 to 8 nmi, plus or minus 2). "Leading" correctly leaves out H-CLOSE, which fits at 2 nmi but is 14,000 log units behind. |
| 2. GOFAST wind claim (caption 11, README GOFAST bullet) | **PASS** | Caption now drops the wind claim: "A balloon, a slow flier and a glare on a slow target fit the same path; this data cannot tell them apart", which is the case-file verdict's own sentence (recovery: data made by H-ART, H-SLOW, H-WIT also won by H-BAL). README bullet: wind good to about 4 kt separates balloon from free path, balloon from slow flier "only one way", "nothing kinematic separates the slow flier from a glare on a slow target", and "Without one data-quality rule (... D-016) the glare model leads instead of the balloon." Matches `docs\results\gofast.md` lines 205 to 207. |
| 3. Compare-view caption | **PASS** | Caption: "Prior work rerun from its own inputs: Sitrec reproduces; Peings and von Rennenkampff 2023 only in part". The frame under it (65 s and 69 s) shows both P&vR columns with "a reproduction check fails" in red, some rows matching (start range 8.0 / 8.0, 30.0 / 29.7 nmi) and some not (end speed 450 vs 532 kt), and Sitrec "reproduction checks pass". "Only in part" is accurate. But see new must-fix 1: the README still says the opposite. |
| 4. README commands | **PASS** | All 7 fenced blocks are `powershell`, one line, start with `cd "C:\Users\stewa\Documents\Claude\Sensor forensics";`, use the full path to `.venv\Scripts\python.exe`, to every script and to every video file; `;` chaining only, no `&&` or `\|\|`. Ran in Windows PowerShell 5.1.26100 via `powershell.exe -NoProfile`: the validate_cases pattern (4 passed, 0 failed, exit 0); README line 85 verbatim from a .ps1 file (`pytest: 290 tests, 0 failures, 0 errors, 0 skipped`, `node --test: exit 0`, `GATE PASS`). I also ran README line 79 (build_app_data) verbatim by mistake: it completed, wrote nothing ("0 written, ... up to date"), and `git status` stayed clean, so the committed app data are reproducible. |

## Criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| 1. Case files validate | **PASS** | `.venv\Scripts\python.exe tools\validate_cases.py`: PASS flir1, gimbal, gofast, pursue-triage; 4 passed, 0 failed, exit 0 (rerun directly and through PowerShell 5.1). |
| 2. 2-minute highlight recording | **PASS** | `ffprobe`: 120.07 s, 1440 x 900, 15 fps, 1801 frames. Segment boundaries computed from SEGMENTS put the changed captions at 41.4 to 47.4 s, 60.4 to 69.4 s and 82.7 to 90.7 s. Frames pulled at 44.4, 64.9, 69 and 86.7 s show the new text, white on a dark box, fully legible, not clipped. One frame from each of the other 10 segments: all captions legible and match their views. The FLIR1 caption at 107 to 108 s ("free path at 11.9 deg, a glare above about 13 deg") matches `docs\results\flir1.md` (crossover 12.75 deg physics-only, 12.96 testimony-weighted) and the on-screen flag. No caption overclaims against `docs\results\*.md`. |
| 3. README for a non-programmer | **PARTIAL** | The four findings bullets now match the results pages, and the commands are right. One overclaim remains (must-fix 1). |
| No em dashes | **PASS** | 0 U+2014 and 0 `&mdash;` in `README.md`, `checkpoints\CP-07.md`, `tools\record_highlights.py` (captions), `schemas\README.md` and the three video case files (counted in Python, UTF-8). |

## Overall: SEND BACK (one line)

Everything the first review asked for is fixed and verified. One sentence in the README repeats, in the views list, the exact overclaim that must-fix 3 removed from the recording.

## Must-fix

1. `README.md`, "The five views", item 4: "Mick West's Sitrec and the 2023 Peings and von Rennenkampff paper, each reproduced from its own inputs, beside this lab's numbers." The same view shows "a reproduction check fails" for both Peings and von Rennenkampff paths, and `docs\reproductions\SUMMARY.md` grades them Partial. Reword to match the caption, for example "each rerun from its own inputs (Sitrec's checks pass; the 2023 paper's pass only in part), beside this lab's numbers." No re-recording needed.

## Nice-to-fix (not blocking)

- The app's compare panel is titled "Prior work: published and reproduced" (seen on screen in segment 9). It names the two columns, but "published and lab rerun" would avoid the same reading.
- "Sitrec reproduces" holds for the locked test value and the cloud-matched turn rate; `docs\reproductions\SUMMARY.md` row 13 records that Sitrec's documented "From Bank and Speed" alternative fails as specified. The caption is consistent with the screen, so this is a note, not a fix.
- Carried over from the first review and still open: provenance re-export from a clean tree, the FLIR1 "cannot tell those explanations apart" wording for H-CLOSE, a GOFAST line saying the rotation check does not apply, labels instead of IDs in verdict sentences, the full `decisive` rule in the schema description, README commands for export/validate and for rebuilding the recording, and full paths in README prose (`docs/results/`, `DECISIONS.md`).
