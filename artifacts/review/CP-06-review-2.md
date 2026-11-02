# CP-06 independent review, second check (M5, PURSUE)

Reviewer: independent checkpoint check, 11/02/2026, at commit 8631b09. Scope: `checkpoints/CP-06.md`, `docs/results/pursue.md`, `docs/audit/pursue.md`, `docs/audit/VERDICTS.md`, `README.md`, `data/pursue/*`, `data/derived/pursue/*`, `tests/test_pursue_m5.py`, PR044 frames. The CP-04 files (solve/, GIMBAL, GOFAST, FLIR1) were not judged.

## What I checked myself

- `data/pursue/triage.csv` against `data/pursue/index.csv` with my own script: 134 rows each, same ID set, no duplicates; tiers 0 Full, 16 Bounded, 118 Not viable. `tools/check_pursue_index.py` agrees.
- `docs/results/pursue.md`: the "All 16 Bounded clips" table has 16 rows, exactly the Bounded set in `triage.csv`, with reasons identical to the CSV. "The other 126 clips" has 126 rows; tier and reason match `triage.csv` for all 126 (0 mismatches); with the 8 analyzed clips that covers all 134. PR107 appears as Not viable (re-tiered, D-019) at `pursue.md:151`.
- Recomputed from the per-clip `summary.json` files: PR044 slope 1.083, r 0.943, 0.083 to 0.111 m/px, size band 0.67 to 1.22 m, speed 1.24 / 4.27 / 13.7 m/s, gate range 10.2 km at 1 deg (0.0926 m/px over 1920 px); PR052 slope 0.746; PR111 heights 8.5 / 71.4 / 17.1 / 71.7, object altitudes 63.0 and 54.4; PR113 HFOV 51.2 / 39.2 / 28.5 deg, Mach 1 at 165 / 186 / 207 m; PR149 97.7 to 130.3 and 100.7 to 134.2 m/s, cross size 1.04 to 1.73 m. All match the text to its stated precision.
- PR044 frames 6030, 6060, 6090, 6100 to 6106 and `gate_scan.csv`: 144 px box with no label at 6030; 23M on the 231 px box at 6060; 33M on the 304 px box at 6090; the gate snaps 304 to 108 px between frames 6095 and 6100; the label still reads 33M on the 108 px box at 6100 to 6103 and reads 12M by 6106. The corrected pairing in `pursue.md:17` is right.
- `.venv\Scripts\python.exe -m pytest tests\test_pursue_m5.py -q`: 15 passed.
- U+2014 (and its HTML entities): 0 in `checkpoints/CP-06.md`, `docs/results/pursue.md`, every `docs/audit/*.md`, `README.md`, `DECISIONS.md`.

## Verdict per criterion

| Criterion | Verdict | Evidence and reason |
|---|---|---|
| 1. A results table for each viable clip | Partial | The table (`pursue.md:15-24`) is now correct for all 8 and every number reproduces, but `CP-06.md:22` cites `data/derived/pursue/m5_summary.json` as backing evidence, and that file still carries the wrong PR044 pairing (`m5_summary.json:274`: "Gate grows 144 to 304 px with label 23M to 33M (6030 to 6090)"). |
| 2. A list of the not-viable clips, each with its reason | Pass | `pursue.md:63-194`: 126 rows (118 Not viable plus 8 deferred Bounded), identical to `triage.csv`; 134 rows, one per index clip. |
| 3. A table of the Bounded-tier clips | Pass | `pursue.md:40-61`: one 16-row table, analyzed or deferred under D-013, matching the Bounded set in `triage.csv` exactly. |

## The first review's must-fixes

| Must-fix | Verdict | Evidence |
|---|---|---|
| 1. PR044 pairing; test rests on 3 gate sizes | Partial | Fixed in `pursue.md:17`, `pursue.md:28`, `CP-06.md:13` and `dow-uap-pr044/summary.json:15`. But `summary.json` was edited by hand: the generator input `data/derived/pursue/gate_clip_inputs.json:7` still has the old wrong notes, `tools/pursue_m5_analyse.py:408` copies them into every gate clip's `summary.json` and `m5_summary.json`, and `m5_summary.json:274` still shows them. Rerunning `tools/pursue_m5.py analyse` would put the error back into `summary.json` and drop the hand-added `object_size_at_ratio1_m_full_extent_band` key, which no code produces. |
| 2. PR052 slope 0.75, no "cleanly" | Pass | `CP-06.md:13` and `pursue.md:28` give slope 0.75, by eye, supporting; "cleanly" appears nowhere. |
| 3. True reason no clip is Full | Pass | `CP-06.md:22` and `CP-06.md:30`: no clip shows azimuth; PR111 has elevation and a slant-range-like label but no azimuth. `README.md:21` agrees. |
| 4. PR113 field of view attributed to pixel aspect and conformal ladder; 51 against 54 | Pass | `CP-06.md:15`, `CP-06.md:30`, `pursue.md:23`, `pursue.md:32`. |
| 5. One Bounded table; PR107 re-tier consistent everywhere | Partial | The table, `triage.csv`, `pursue.md:42` and `:151`, `docs/audit/pursue.md:17-20` and `:31`, `CP-06.md:9`, `VERDICTS.md:10` (counts column), `README.md:21` and D-019 all say 16 / 118. But `docs/audit/VERDICTS.md:10` goes on to say "Seventeen carry a scale". |

## Nice-to-fix items from the first review

- PR149 maximum qualified: done in `pursue.md:24` and `CP-06.md:16`. `dow-uap-pr149/summary.json` `geometry_note` is still unqualified.
- PR044 size 0.7 to 1.2 m as an upper value: done (`pursue.md:17`, `CP-06.md:30`, which also keeps "low-confidence" on the speed).
- PR111 segments C and B: done (`pursue.md:22`, `CP-06.md:48`).
- "Longer" track wording: done (`pursue.md:34`). Status date: done (`pursue.md:3`). Stale audit sentence: done (`docs/audit/pursue.md:38`).

## Other findings (not blocking)

1. `docs/audit/pursue.md:22` still explains "Why nothing is Full" by redacted fields alone, not by the missing azimuth that CP-06 now names.
2. In `triage.csv`, the PR107 notes still say "Becomes Full only if platform altitude or range is taken from another source". That conflicts with the no-azimuth rule, and with Not viable, which allows no curves.
3. On PR044, the label lags the gate snap by about 4 to 6 frames: 33M shows on the 108 px box at frames 6100 to 6103. The wording "snaps ... within 0.17 s" is accurate about the gate, but the lag could be noted.
4. PR113's "12 to 21 percent lower": against our own square-pixel rate the drops are 11.7 and 20.4 percent, so "12 to 20". Against H&K's 2.10 rad/s they are 13 and 22.

## Overall: SEND BACK

Both items below are small, but one is a regression trap and the other is a count the check was asked to confirm.

### Must-fix

1. Put the corrected PR044 notes, the 3-gate-size statement and the 0.67 to 1.22 m full-extent band into `data/derived/pursue/gate_clip_inputs.json` (or into the code), then rerun the analysis. `m5_summary.json` and `dow-uap-pr044/summary.json` must then agree with `pursue.md:17`, and a rerun must reproduce them. Check `git diff` afterwards to confirm that nothing else moved.
2. `docs/audit/VERDICTS.md:10`: change "Seventeen carry a scale" to "Sixteen". Consider stating there that PR107 (elevation only) no longer counts.
