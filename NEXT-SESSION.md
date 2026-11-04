# NEXT-SESSION.md

Last updated: 11/04/2026. The M0 to M6 plan is complete, the project is published (D-020), and the live lab was reworked after Stewart's first look (D-021).

## Where we are

- All seven checkpoints passed an independent check and are tagged: cp-01 to cp-07. CP-04, CP-05, CP-06 and CP-07 each passed on the third check after being sent back twice. Reviews in `artifacts/review/`.
- Start with `README.md` (plain-words findings, how to open the app, one-line PowerShell commands) and `docs/results/`.
- Owner rulings D-010 to D-014, D-017, D-020 (publish); lab decisions D-015, D-016, D-018, D-019. Open question (default in use): Q-008 (FLIR1 scoring judgment calls).
- Public face: repo public on GitHub (MIT), `showcase.json` status v1, landing page `site/` at https://sensor-forensics.pages.dev with the lab at /lab/. Rebuild with `tools/build_site.py` (`--deploy` to publish); clips come from `tools/showcase_media.py`. Hub entry on samizdatpublications.com is made from the Github Hub folder.
- 11/04/2026 lab rework (D-021; plan in the session's plan file, checks in `tests/js/onboarding.test.mjs` and `tests/test_app_video.py`):
  - loads in two stages behind a loading screen, with a watchdog that retries stalled requests (`app/js/data.js`); predictions load per field of view (`predictions_<variant>.json`);
  - Play runs an H.264 copy of the frames (`app/data/video/`, built by `tools/build_app_data.py`, gitignored) and the video drives the frame clock (`app/js/player.js`), with a speed control;
  - God's-eye shows one explanation at a time, aligned on the jet's nose, with trails and labels; the range stays put while playing;
  - plain mode by default ("All numbers" for the old display), a verdict card, a welcome card, a guided tour per video (`app/js/tours.js`), a glossary and per-view introductions;
  - fixes from a runtime sweep: God's-eye blank after a case change, ledger sliders and rows, layout at 1280, one curved-Earth altitude everywhere, FLIR1's "99.9" placeholder, shared range-slider limits.
  - `tools/build_site.py` adds cache headers and sends the lab videos through the byte-range function (`functions/lab/data/video/`).
- Results in short:
  - GOFAST: about 13,200 ft at 3.3 to 4.4 nmi; balloon, slow flier and glare on a slow target fit the same path and cannot be separated; without the size exclusion the glare model leads.
  - GIMBAL: with the data-quality exclusions a balloon-like drifter leads by small margins, without them the free path leads; not separable (recovery test). At 0.35 deg every leading physical fit is 15 nmi or more away at the end (at 0.7 deg a balloon fits at 9 to 14); aircrew say 6 to 8. A radar range good to about 2 nmi would settle it.
  - FLIR1: free path leads at the measured rotation noise (11.86 deg); above 12.75 deg a glare model leads (refits confirm). A radar closure rate near the end, good to about 17 kt, would settle glare against the free path.
  - PURSUE: 0 Full, 16 Bounded, 118 Not viable; 8 bounded clips analyzed (gate labels are gate widths in metres; PR149's speed bound reproduced; PR113's scale is a pitch ladder).
- Case files: `exports/cases/*.json` (schema v0.1); no Navy video has a decisive leader under the one rule applied to all.
- Recordings: `artifacts/movies/gimbal_framelock_60s.mp4`, `artifacts/movies/highlights_2min.mp4`.

## Possible next work (none started; Stewart decides)

1. The 8 deferred Bounded PURSUE clips (D-013).
2. Cosmetic app items logged in `checkpoints/CP-05.md` (cursor over chart labels, compare-view axis title at 1440).
3. Rerun if new data appears: a released radar track for GIMBAL or FLIR1 would be scored as a new criterion through the same path.

## House rules

- Commit after every result; never `git add -A` or `git add .`; commit messages via `git commit -F`; no em dashes in reader-facing text.
- When Stewart runs another heavy project, run at BelowNormal priority with one thread, or pause.
