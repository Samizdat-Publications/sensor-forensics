# NEXT-SESSION.md

Last updated: 10/31/2026 (paused at Stewart's 65% weekly quota cap, right after CP-01)

## Where we are

- Plan approved (D-009), in _PLAN.md. Repo `Samizdat-Publications/sensor-forensics` (private); folder `C:\Users\stewa\Documents\Claude\Sensor forensics\` (D-008). Venv `.venv` (Python 3.12). `tools/gate.py` passes (81 tests, skip detection via JUnit).
- **CP-01 passed** (`checkpoints/CP-01.md`, tag cp-01). Audits in `docs/audit/`, disagreements and findings in `docs/prior-work/`, PURSUE index/triage/file map in `data/pursue/`.
- **M1 nearly done, CP-02 open.** Per-frame readings: `data/derived/{gimbal,gofast}/symbology_final.csv` (the solver reads only this), transition flags `transitions.csv`, image cues `image_track.csv` (bank, object, background motion). Correction tool: `.\.venv\Scripts\python.exe -m extract.correct.server gimbal`.
- **Blind check result** (`artifacts/cp02/blind/ADJUDICATION.md`): raw 8/1800 disagreements; adjudicated 1 clear reader error, 2 verifier misreads, 5 interlaced transition frames. The verifier (`artifacts/review/CP-01-02-review.md`) judged the 1 percent per-field target missed for GIMBAL azimuth (3/100) and GOFAST clock (2/100) and said the "none wrong" claim rested on a detector checked on the same frames. That claim is withdrawn; treat the strict rates as the logged result.
- **M2 started:** `solve/frames.py`, `solve/atmosphere.py`, `solve/jet.py`, `solve/sensor_atflir.py` (exact port of Sitrec's pod geometry; golden test reproduces Sitrec's frame-435 horizon to 1e-9).
- Frames are in `data/frames/` and videos in `data/videos/` (both gitignored; regenerate with `tools/fetch_videos.py` and `python -m extract.frames`). PURSUE clips in `data/pursue/raw/` (gitignored, about 15 GB).

## Do next (in order)

1. CP-02 must-fix: (a) draw a fresh blind sample on a new seed (`tools/sample_frames.py --seed 7 --n 100 gimbal gofast`, use a different seed per video) and have a fresh verifier transcribe it; score with `tools/score_blind.py`; log the raw and strict rates honestly; mark GIMBAL azimuth and GOFAST clock low-confidence at changes if they still miss 1 percent. (b) Investigate `tests/test_correct.py` intermittent failures (verifier saw 3 of 8 failing). (c) Write `checkpoints/CP-02.md` including the Sitrec agreement numbers (`data/derived/<case>/symbology_sitrec_check.json`), run the independent check, tag cp-02.
2. M1 leftovers: FLIR1 symbology reading (small glyphs; use the 2007 copy as a cross-check).
3. M2: weather (ARCO-ERA5 anonymous Zarr, IGRA soundings), line-of-sight fit with interval readouts, pixel-aspect question, trajectory families, reproductions (tolerances are stated in _PLAN.md).
4. Check `mcp__ccd_session_mgmt__get_usage` between items; Stewart sets the quota cap per run.
