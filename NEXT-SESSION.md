# NEXT-SESSION.md

Last updated: 11/01/2026 (overnight pause requested by Stewart: the jump-sim project needs the CPU)

## Where we are

- Checkpoints passed and tagged: cp-01 (data audit), cp-02 (symbology, fresh blind sample), cp-03 (geometry and reproductions, with documented differences and the field-of-view condition). Reviews in `artifacts/review/`.
- Owner rulings D-010 to D-014 (testimony high weight with a physics-only total beside it; PURSUE frozen to 8 clips; schema v0.1 here); lab decisions D-015 (25 percent floor on recalled numbers; H-WIT range free) and D-016 (size criterion only for resolved objects; rounding convention shared).
- M3 under way: single scoring path (`solve/score.py`), hypotheses as data (`solve/hypotheses/`), testimony likelihoods (`solve/testimony.py`, 160 claims in `data/testimony/`), weather (`solve/weather.py`, ERA5 1 deg plus IGRA), FLIR1 readouts done (range line is a constant 99.9 placeholder from frame 973).
- GOFAST scored (`docs/results/gofast.md`). GIMBAL scored but PROVISIONAL (`docs/results/gimbal.md` banner): brightness criterion audit, equal range priors, ERA5 turn rate, point-spread width.
- A review worker was resolving those four items and running the model-recovery test at below-normal priority when Stewart paused for the night. Check `docs/results/REVIEW-M3.md`, `docs/results/recovery.md`, and `git status` for its output; if it is missing or partial, rerun those items (low priority if anything else is running).

## Do next (in order)

1. Finish and commit the M3 review items and recovery test (see above).
2. FLIR1 scoring through the same path (`solve/cases/flir1.yaml`), testimony included.
3. Discriminators per video (`docs/results/<case>.md`), equal-treatment review, CP-04 with an independent check.
4. Then M4 app, M5 (8 frozen PURSUE clips), M6 exports and schema v0.1.

## House rules for this run

- Check `mcp__ccd_session_mgmt__get_usage` between items; Stewart sets the quota cap per run.
- When Stewart runs another heavy project, run at BelowNormal priority with one thread, or pause.
