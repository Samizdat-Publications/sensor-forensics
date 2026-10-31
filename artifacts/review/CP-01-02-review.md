# CP-01 and CP-02 independent review

Reviewer: independent checkpoint reviewer, 10/31/2026. No project files were modified. Images viewed: 17 (3 CP-01 field strips, 12 PURSUE contact sheets, adjudication.png, 1 blind sheet).

## Verdicts

| Checkpoint | Criterion | Verdict | Reason |
|---|---|---|---|
| CP-01 | Audit tables | Partial | I checked 25 values (GIMBAL 9, GOFAST 10, FLIR1 6) against the field strips and all matched, but rows cite only "f0 to f1030" plus one strip image, the GOFAST and FLIR1 bank, object and background rows have no crop image (`gofast_layout_f400.png` exists but nothing cites it), and gofast.md contradicts itself and the data (it says range is "blank until about f368, then 4.3" and also "4.4 nmi (about f350)"; the CSV has 4.4 from f368, and closure starts at 220, not 210). |
| CP-01 | PURSUE triage list | Pass | All 134 index clip_ids appear exactly once in triage.csv, `check_pursue_index.py` exits 0, every file and sheet exists, and file_map agrees. In my seed-31 sample (4 Bounded plus 8 Not viable) I agree with 10 of the 12 tiers and flag 2 as inconsistent (listed below). The row-count check promised in the plan is not in any script: `check_pursue_index.py` reads only index.csv, so I did that check by hand. |
| CP-01 | Disagreement list | Partial | I confirmed 12 rows against sitrec.md, peings-vonrennenkampff-2023.md and aaro-gofast.md (G1, G3 to G9, G11, G13, F1, F2), but two rows fail: G2's Sitrec column ("far path roughly steady") contradicts sitrec.md, which says the repo prints no speed profile, and contradicts the doc's own agreement section. F3 ("Vc not used" by Sitrec and AARO) has no source: neither summary mentions Vc. |
| CP-01 | Plain verdict per video | Pass | VERDICTS.md gives a clear verdict for each video, consistent with the audits and the triage counts (17 Bounded, 117 Not viable). The exception is the "Vc that no prior analysis used" claim: it is stated as fact, while gofast.md still says "to confirm at M2". |
| CP-02 | Per-frame tables, GOFAST and GIMBAL | Pass | Both tables have 1031 frames with every field on every frame (9 fields for GIMBAL, 11 for GOFAST) and no nulls or duplicates. The clock rises steadily with no jumps, GOFAST range falls 4.4 to 3.3 and closure 220 to 150, the azimuths are monotone with 1 deg steps, and transitions.csv is present. |
| CP-02 | 100 frames per video checked blind, error rate logged | Pass | sample.json shows only crops (no values leaked), each verifier.csv has 800 or 1000 cells, and rerunning `score_blind.py` reproduces score.json exactly (GIMBAL 5/800, GOFAST 3/1000). |
| CP-02 | Target: at most 1% per digit field | Fail | Raw rates miss the target for GIMBAL azimuth (3%), GIMBAL airspeed (2%) and GOFAST clock (2%). Even on the strictest reading after adjudication, GIMBAL azimuth (3/100) and GOFAST clock (2/100) still miss. The "none is a wrong value" conclusion rests on a transition detector whose 1.3 threshold was checked against the same 200 frames, and that detector flags f194, which looks like a clean frame read wrong. |
| CP-02 | Adjudication (8 cases) | Pass | I agree with all 8 from adjudication.png: f4 and f12 read 238 (verifier misread); f152, f812, f694, f322 and f682 show visible interlace mixes; f194 cleanly reads 45 (a lab error). |
| CP-02 | Tests (`tools/gate.py`) | Partial | The gate printed GATE PASS (81 passed, 0 skipped, confirmed with `-o addopts=""`), but its skip check cannot fire. Pyproject addopts `-q` plus the gate's own `-q` makes `-qq`, which drops pytest's summary line, so the gate greps a progress bar. Also, `tests/test_correct.py` failed 3 times in 8 runs (socket TimeoutError and ConnectionAbortedError). |

## Must-fix

1. CP-02 target. Run a fresh blind sample with a new seed after the transition fix and report that rate. Otherwise apply the plan's fallback: log the raw rate as the CP-02 number and mark GIMBAL azimuth and airspeed and GOFAST clock low-confidence. Remove the claim that none of the 8 disagreements is a wrong value (f194 is). Supporting evidence: the GIMBAL Sitrec azimuth agreement is only 97.3% (28 diffs), consistent with about 3% azimuth error.
2. Write `checkpoints/CP-02.md` with the Sitrec agreement report, as the plan promises (only CP-TEMPLATE.md exists). Write CP-01.md as well.
3. Gate. Make skip detection work (for example, drop the gate's `-q`, or parse a junit report). Fix the flaky correction-server tests.
4. DISAGREEMENTS.md. Source or correct G2's Sitrec column. Cite F3 or soften it to "not found in the Sitrec code or the AARO report, to confirm", and make VERDICTS.md match.
5. Audit rows. Add crop images and frame numbers for the bank, object and background rows (GOFAST, FLIR1). Correct the GOFAST range and closure start values (4.4 at f368; 220).
6. Add the triage row-count check to a script.

## Nice-to-fix

- Triage consistency. PR036 (tick ladders, visible objects, a boat in view at 4 s) is Not viable, while PR030 and PR120 are Bounded on uncalibrated ticks. PR119 and PR120 share a display but get different tiers, with clip length as the only reason, and length is not a tier rule. I could not see the `north_arrow` token's arrow in PR119 or PR120. PR036's "horizon" scene token is a symbology line, not a scene horizon.
- PR111 lists `range` as visible although the notes say the label is unverified, and under the tier rule that token alone would make the clip Full.
- The two videos have identical sample frame lists (same seed and same length), and the `sensor` field is never blind-checked.
- The confidence column has a median of exactly 0.5 for azimuth, clock, elevation and closure, which looks capped.
- The clock's "A" suffix toggles mid-second (f72, f793). The verifier says the crop may cut it off.
- FLIR1 IAS "about 250 to 253": the strip suggests values near 245 to 249 in mid-clip.
- sitrec.md lines 156 and 249 disagree on which sitch holds the 30 NM track. F1's Sitrec altitudes come from a Sitrec HEAD notebook run from about 11/2024, not the pinned commit 83891bf.
- The index.csv column `stated_duration_s` is missing from the column list in INDEX-NOTES.md.
- No em dashes were found in docs/, data/pursue/*.md or artifacts/cp02/*.md.
