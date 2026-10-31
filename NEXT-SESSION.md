# NEXT-SESSION.md

Last updated: 10/30/2026 21:05 (M0 in progress)

## Where we are

- Plan approved (D-009), in _PLAN.md. Repo `Samizdat-Publications/sensor-forensics` (private), folder `C:\Users\stewa\Documents\Claude\Sensor forensics\` (D-008).
- S0 done: venv on Python 3.12 (`.venv`), `tools/gate.py` passes.
- Videos: all four copies downloaded via Wayback (NAVAIR refuses scripted requests; never spoof headers). Manifest: `data/videos/MANIFEST.json`. Frames extracted to `data/frames/` (gitignored); indexes in `data/derived/<case>/`.
- Audits written: `docs/audit/gimbal.md`, `gofast.md`, `flir1.md`, with evidence strips in `artifacts/cp01/`.
- PURSUE index: `data/pursue/index.csv` (134 clips), built from the official CSV read in the built-in browser (war.gov refuses scripted requests). Notes in `data/pursue/INDEX-NOTES.md`.
- PURSUE zips downloading via `tools/pursue_fetch.py` (resumable, re-run it if it stopped). Log: `artifacts/tmp_pursue_fetch.log`. Network was slow on 10/30.
- Started: `solve/frames.py`, `solve/atmosphere.py` (tested). Findings so far: `docs/prior-work/FINDINGS-LOG.md`.
- A worker was writing `docs/prior-work/*.md` and downloading Sitrec data CSVs to `data/reference/sitrec/`; check whether those files exist.

## Do next

1. Finish M0: prior-work summaries (check/finish), `docs/prior-work/DISAGREEMENTS.md`, audio transcription (`tools/transcribe.py`), PURSUE contact sheets and triage once clips are on disk, verdicts, then CP-01.
2. If PURSUE downloads are still incomplete at CP-01 time, triage what is on disk and mark the rest "pending download" in the triage list.
