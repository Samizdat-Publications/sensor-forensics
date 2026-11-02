# NEXT-SESSION.md

Last updated: 11/02/2026. The M0 to M6 plan is complete.

## Where we are

- All seven checkpoints passed an independent check and are tagged: cp-01 to cp-07. CP-04, CP-05, CP-06 and CP-07 each passed on the third check after being sent back twice. Reviews in `artifacts/review/`.
- Start with `README.md` (plain-words findings, how to open the app, one-line PowerShell commands) and `docs/results/`.
- Owner rulings D-010 to D-014, D-017; lab decisions D-015, D-016, D-018, D-019. Open questions (defaults in use): Q-003 (publish later? private), Q-008 (FLIR1 scoring judgment calls).
- Results in short:
  - GOFAST: about 13,200 ft at 3.3 to 4.4 nmi; balloon, slow flier and glare on a slow target fit the same path and cannot be separated; without the size exclusion the glare model leads.
  - GIMBAL: with the data-quality exclusions a balloon-like drifter leads by small margins, without them the free path leads; not separable (recovery test). At 0.35 deg every leading physical fit is 15 nmi or more away at the end (at 0.7 deg a balloon fits at 9 to 14); aircrew say 6 to 8. A radar range good to about 2 nmi would settle it.
  - FLIR1: free path leads at the measured rotation noise (11.86 deg); above 12.75 deg a glare model leads (refits confirm). A radar closure rate near the end, good to about 17 kt, would settle glare against the free path.
  - PURSUE: 0 Full, 16 Bounded, 118 Not viable; 8 bounded clips analyzed (gate labels are gate widths in metres; PR149's speed bound reproduced; PR113's scale is a pitch ladder).
- Case files: `exports/cases/*.json` (schema v0.1); no Navy video has a decisive leader under the one rule applied to all.
- Recordings: `artifacts/movies/gimbal_framelock_60s.mp4`, `artifacts/movies/highlights_2min.mp4`.

## Possible next work (none started; Stewart decides)

1. The 8 deferred Bounded PURSUE clips (D-013).
2. Publishing (Q-003): a public build would need a review of what may be redistributed (videos are official releases; testimony is paraphrased).
3. Cosmetic app items logged in `checkpoints/CP-05.md` (cursor over chart labels, compare-view axis title at 1440).
4. Rerun if new data appears: a released radar track for GIMBAL or FLIR1 would be scored as a new criterion through the same path.

## House rules

- Commit after every result; never `git add -A` or `git add .`; commit messages via `git commit -F`; no em dashes in reader-facing text.
- When Stewart runs another heavy project, run at BelowNormal priority with one thread, or pause.
