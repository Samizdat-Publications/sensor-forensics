# NEXT-SESSION.md

Last updated: 11/02/2026 (weekly quota about 25 percent after Stewart's reset)

## Where we are

- Tagged: cp-01, cp-02, cp-03, cp-04 (passed on the third independent check), cp-06 (passed on the third check). Reviews in `artifacts/review/`.
- CP-05 (the app) and CP-07 (exports and wrap) are drafted (`checkpoints/CP-05.md`, `CP-07.md`); CP-05's independent check was running at the end of the session (`artifacts/review/CP-05-review.md` when done). CP-07's check comes after the FLIR1 discriminators are in.
- Owner rulings D-010 to D-014, D-017; lab decisions D-015, D-016, D-018, D-019 (PR107 re-tiered: PURSUE is now 0 Full, 16 Bounded, 118 Not viable). Open questions: Q-003 (publish later?), Q-008 (FLIR1 scoring judgment calls; defaults in use).
- Results, in short (details in `docs/results/`):
  - GOFAST: about 13,200 ft at 3.3 to 4.4 nmi; balloon, slow flier and glare on a slow target fit the same path; not separable. Without the size exclusion the glare model leads.
  - GIMBAL: with the exclusions a balloon-like drifter leads both totals at both fields of view, by small margins; without them the free path leads. Not separable (recovery). Every physical model needs 12 nmi or more; aircrew say 6 to 8; radar range would settle it.
  - FLIR1: free path leads at the rotation noise measured from the data (11.86 deg); above 12.75 deg a glare model leads (refits at 13.0 and 15.65 deg confirm). Conditional.
  - PURSUE: 8 bounded clips analyzed; gate labels are gate widths in metres; PR149's speed bound reproduced; PR113's ladder is a pitch ladder.
- Case files (`exports/cases/*.json`) use one decisiveness rule; no Navy video has a decisive leader.
- Recordings: `artifacts/movies/gimbal_framelock_60s.mp4` (CP-05), `artifacts/movies/highlights_2min.mp4` (CP-07).

## Do next (in order)

1. If `solve.discriminators flir1` finished: `.venv\Scripts\python.exe -m solve.discriminators --report`, write the FLIR1 "settle" text in `data/discriminators/notes.yaml` (cases.flir1.settle and results_page_settle.flir1), regenerate `docs/results/flir1.md` (`python -m solve.results_flir1`), re-export and validate the cases, run the gate, commit.
2. CP-05: act on its review; fix, recheck if sent back, tag cp-05.
3. CP-07: independent check (validation, recording, README commands), fix, tag cp-07.
4. Update `.tower/status.json` and this file; tell Stewart the run is complete.

## House rules for this run

- Commit after every result (quota can run out mid-task).
- When Stewart runs another heavy project, run at BelowNormal priority with one thread, or pause.
- Never `git add -A` or `git add .`; commit messages via `git commit -F`; no em dashes in reader-facing text.
