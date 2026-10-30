# _PLAN.md: Sensor Forensics Lab

Status legend: [ ] open, [~] in progress, [x] done (with evidence in a checkpoint file).

Approved by Stewart on 10/30/2026. This is the execution plan for M0 to M6; status is tracked on the checkbox items.

## Context

Stewart handed over a Cowork package (`sensor-forensics.zip` plus `sensor-forensics-handoff.md` in `C:\Users\stewa\Documents\Claude\Sensor forensics\`). It asks for a hypothesis-testing lab that rebuilds the GIMBAL, GOFAST and FLIR1 Navy videos and the 2026 PURSUE videos in 3D, scores every explanation with the same geometry, physics and frame evidence, reproduces prior work first, and says plainly where the public data can't decide. The kickoff asks for a preliminary data audit, a full M0 to M6 plan in `_PLAN.md`, and the gaps in SPEC.md and ENGINE.md with the default for each. After approval the run goes autonomously per AUTONOMY.md.

Tags used below: **[me]** orchestrator (high effort); **[W]** worker subagent (Sonnet, medium effort); **[W+]** worker on Opus for heavy math or design; **[bg]** background job; **[V]** fresh verifier subagent (Opus, high effort).

## Facts found while planning (all verified 10/30/2026)

- **Toolchain:** Python 3.14 is the default, with 3.12.14 available through uv. Also installed: ffmpeg 9.0.2, Node 24.19, git 2.53, and gh (logged in as Samizdat-Publications, repo scope). Python packages present: numpy, scipy, pandas, opencv, scikit-image, playwright 1.63 and pytest. Tesseract is missing. The GPU is an RTX 5070 Ti (12 GB). C: has 107 GB free.
- **Handoff errors to fix:**
  - The 2023 GIMBAL paper (arXiv 2306.08773) is by **Yannick Peings and Marik von Rennenkampff**. Graves is a cited witness, not an author.
  - The 2026 paper (arXiv 2608.12445) is by **Haqq-Misra and Kopparapu**.
  - PURSUE now has **134 videos across Releases 01 to 06**. Release 07 is documents only. The six official CloudFront zips total about 15 GB and need no login. Most on-screen sensor data in PURSUE is redacted. PR113 is the only clip the paper names as having a usable scale.
- **Sitrec:**
  - v1 is MIT licensed. The license of Sitrec2 code is unconfirmed, so any port pins to a v1 commit.
  - Per-frame and keyframe data ship in the repo: `data/gimbal/GimbalData.csv` (azimuth, bank, glare angle per frame), the GOFAST AZ/EL/RNG keyframe CSVs, and the FLIR1 AZ/EL/FOV/Mode CSVs.
  - logicbear's `0x1beef/uap_nb` (MIT) refines GIMBAL with cloud motion.
- **Video copies:**
  - GIMBAL and GOFAST: the best copies are the NAVAIR FOIA 2020 `.wmv` files (640x480, 29.97 fps, about 34 s, WMV7). Published frame counts disagree (1031, 1033, 1034).
  - FLIR1: the official `.mp4` is worse than a 2007 `F4.MPG` copy on archive.org.
- **Symbology:**
  - Azimuth and elevation are whole degrees, and GIMBAL azimuth updates every other frame.
  - GOFAST RNG steps by 0.1 nmi, from 4.4 down to 3.3.
  - ATFLIR field of view: NAR 0.7 deg at 1x and 0.35 deg at 2x, MFOV 3 deg, WFOV 6 deg.
  - No public transcript of the aircrew audio exists.
- **Winds:** ERA5 is available with no account through Google's anonymous ARCO-ERA5 Zarr store. IGRA radiosonde files (Jacksonville, Newport, Wallops, San Diego) download over plain HTTP.
- **Local setup:**
  - No UFO Case Files schema exists anywhere yet. Stewart says that project is planned but not deployed.
  - The control tower is not built yet. Its spec discovers any folder directly under `Documents\Claude` that has a CLAUDE.md or `.git`, so this folder name works.
- **Lessons from the sister projects (kessler-cascade, stand-in-the-door):**
  - Set `MSYS_NO_PATHCONV=1` for capture commands.
  - Headless Chrome may not get the GPU. The fallback is a headed Chrome window placed off-screen.
  - Never use `git add -A` or `git add .`. Write commit messages to a file and use `git commit -F`.
  - A skipped gate counts as a fail.
  - Kill processes by PID only. Run at most about 6 concurrent jobs.
  - Check usage and stop near 98% of the weekly quota.
  - Never move a pushed tag.

## Preliminary data audit (confirmed frame by frame in M0)

| Video | Readable on screen, per frame | Inferred | Unknown |
|---|---|---|---|
| GIMBAL | pod azimuth (whole degrees, every 2nd frame), elevation (whole degrees, about -2), IAS, Mach, altitude, NAR Z 2.0, IR polarity, artificial horizon (bank), object position, shape, orientation and brightness, cloud motion | TAS (from IAS or Mach plus temperature), turn rate (from bank), heading history (unknown start), wind ("120 knots" on the audio plus ERA5), FOV 0.35 deg (documentation), world-frame line of sight (needs the angle convention and pitch) | range, absolute position and heading, object size, radar data, uncut video |
| GOFAST | azimuth, elevation, RNG (0.1 nmi steps after lock), altitude, speed, zoom, horizon, ocean background motion | object altitude and speed (from RNG plus elevation), wind | what the RNG source is (laser or radar), absolute position |
| FLIR1 | azimuth, elevation, mode IRW/TV, FOV changes (NAR 1x/2x, a brief MFOV/WFOV), object shape and orientation | whether the jet's speed and altitude show (M0 checks) | range, the jet's path, radar data |
| PURSUE | mostly redacted. PR113 has a 5 to 35 scale (about 54 deg horizontal FOV, assumed to mark depression angle). PR149 has a ship of known size | per clip in triage | per clip in triage |

**Expected verdicts (to confirm at CP-01):**
- **GOFAST:** reconstructable to tight bounds, because range is on screen.
- **GIMBAL:** the line of sight is reconstructable, but range is not. Results become curves over range, weakly constrained by the jet's turn and cloud parallax.
- **FLIR1:** the weakest of the three.
- **PURSUE:** mostly in the "bounded" tier or not viable.

## Setup S0 (first execution step after approval)

- [ ] 1. **Folder:** stay in `C:\Users\stewa\Documents\Claude\Sensor forensics\`, not the kickoff's `...\sensor-forensics`. Claude Code keys session history by exact path, and the global rule forbids moving or renaming folders. The repo name stays `sensor-forensics`. This is logged as Q-004.
- [ ] 2. **Unpack the package:**
   - Copy the package files into the project root.
   - Merge `claude-setup\settings.json` and `agents\` into the existing `.claude\`. Leave the healthcare plugin's `.claude\data\` untouched and gitignored.
   - Move the zip and the handoff `.md` into `handoff\`.
- [ ] 3. **Settings:** add deny rules for `git add -A` and `git add .`.
- [ ] 4. **.gitignore:** add `*.wmv *.mpg *.zip *.mkv *.webm`, `data/pursue/raw/`, `app/data/frames/`, `.claude/data/` and `.claude/settings.local.json`.
- [ ] 5. **Write the docs:**
   - `_PLAN.md` gets this plan.
   - DECISIONS.md gets entries for:
     - D-005: the citation and count corrections.
     - D-006: ENGINE pins Python 3.12 through uv, because rapidocr needs Python below 3.13 and the default 3.14 risks missing wheels.
     - D-007: a `schemas/` and `docs/` layout addition.
     - D-008: the folder choice.
   - Correct the citations in CLAUDE.md.
- [ ] 6. **Git and GitHub:**
   - `git init -b main`, with explicit `git add <paths>`.
   - `gh repo create Samizdat-Publications/sensor-forensics --private --source . --remote origin --push` (authorized by D-004).
- [ ] 7. **Python environment:**
   - `uv venv --python 3.12`, plus `pyproject.toml` and `uv.lock`.
   - Packages: numpy, scipy, pandas, opencv-python-headless, scikit-image, matplotlib, pytest, pyyaml, jsonschema, xarray, zarr, gcsfs, rapidocr, faster-whisper, playwright, yt-dlp.
   - No system-wide installs (Tesseract is skipped; rapidocr is the second OCR vote).
- [ ] 8. **Gate script:** `tools/gate.py` runs pytest plus the node parity tests. Any skipped test counts as a fail.
- [ ] 9. **Status files:** update `.tower/status.json` and NEXT-SESSION.md.

Every deliverable path is printed and checked to start with `C:\Users\stewa\Documents\` before saving.

## M0 Data audit (ends at CP-01)

- [ ] 1. **[me]** Setup S0 above.
- [ ] 2. **[W] then [bg]** `tools/fetch_videos.py`:
   - Downloads the NAVAIR GIMBAL.wmv, GOFAST.wmv and FLIR.mp4, the 2007 F4.MPG from the Wayback Machine, and the TTSA 2017 copies for comparison.
   - Records SHA-256, ffprobe data (codec, fps, frame count, duration), source URL and access date in `data/videos/MANIFEST.json`, which is committed.
- [ ] 3. **[W] then [bg]** PURSUE:
   - `tools/pursue_index.py` scrapes the official war.gov/UFO listing (ID, release, agency, date, location, title, URL) into `data/pursue/index.csv`.
   - Then it downloads the six zips one at a time with resume, hashes each zip and each clip, extracts the clips, runs ffprobe on each, and deletes the zips once the hashes are recorded.
   - `tools/contact_sheet.py` makes a 16-frame sheet per clip plus 3 full-resolution frames.
- [ ] 4. **[W] x up to 5 in parallel** PURSUE triage, about 27 clips per worker:
   - Each clip gets a row in `data/pursue/triage.csv`: which symbology fields are visible, redaction state, sensor family guess, scene references (horizon, ship, coastline, clouds, objects of known size), tier and reason.
   - Tiers:
     - **Full:** per-frame line of sight is possible.
     - **Bounded:** a field-of-view scale or a known reference exists, so the clip gets range-size-speed curves only.
     - **Not viable.**
   - Unclear clips go to me.
- [ ] 5. **[me]** Frame-level audit of GIMBAL, GOFAST and FLIR1. I view sample frames myself and write `docs/audit/<video>.md`, covering for each field:
   - location, quantization, update cadence and first/last frame;
   - duplicate or dropped frame check;
   - copy-to-copy alignment and which copy is canonical;
   - readable, inferred and unknown tables with crop images in `artifacts/cp01/`.
- [ ] 6. **[W]** Prior-work summaries with page or line citations in `docs/prior-work/`:
   - Sitrec v1: method per sitch, conventions and pinned commit;
   - Peings and von Rennenkampff 2023;
   - Haqq-Misra and Kopparapu 2026;
   - logicbear's cloud-motion notebooks;
   - AARO's GOFAST analysis.
- [ ] 7. **[me]** `docs/prior-work/DISAGREEMENTS.md` lists every point where the analyses differ, with the cause of each: range, whether the object "stops", rotation as glare versus attitude, wind, elevation precision, angle reference frame, jet turn rate, the size change, the "fleet" radar claim, and the four-input limit.
- [ ] 8. **[bg]** faster-whisper on the GPU transcribes the GIMBAL and GOFAST audio. Output goes to `data/derived/<video>/audio.json` with word confidences, labeled inferred.
- [ ] 9. **[me]** A plain verdict per video. Then **[V]**, then CP-01.

**CP-01 acceptance:** the audit tables; the PURSUE triage list; the disagreement list; a plain verdict on how far each video can be reconstructed.

**How I prove it:**
- Every "readable" row cites frame numbers and a crop image. The verifier opens a sample of the crops.
- `triage.csv` has one row per clip in the official index, and a script checks the row count.
- Every disagreement cites both sources.

**Background:** downloads (about 15 GB), contact sheets, transcription.

**Risks and fallbacks:**
- **NAVAIR links dead or blocked:** use the Black Vault and Wayback copies, checked identical by hash or by frame difference, with provenance recorded.
- **CloudFront throttling or disk pressure:** download one zip at a time with resume and delete each zip after hashing. Fall back to per-clip DVIDS downloads through yt-dlp, then the GitHub mirrors (hash-compared where possible).
- **Triage misses small symbology:** the full-resolution frames plus a verifier spot check of 15% catch it.

## M1 Symbology extraction (ends at CP-02)

- [ ] 1. **[W]** `extract/frames.py`:
   - ffmpeg to PNG for every frame, with the ffmpeg version recorded;
   - duplicate-frame detection;
   - a frame-to-time map;
   - a frame-set hash.
   - Test: frame counts match ffprobe.
- [ ] 2. **[me]** Field layouts as data files in `extract/layouts/atflir_*.yaml`: ROI per field, glyph cell geometry, value grammar and update cadence.
- [ ] 3. **[me spec, W build]** Glyph matcher:
   - I hand-label about 30 frames per video in `data/labels/`, plus synthetic glyph renders.
   - Each character is matched by normalized cross-correlation, and its confidence is the margin between the best and second-best match.
   - rapidocr gives a second vote.
   - A temporal filter catches impossible jumps.
   - Output is `data/derived/<video>/symbology.csv` (frame, field, value, confidence, method).
   - Test: at least 99% accuracy on held-out labeled frames.
- [ ] 4. **[W]** Image cues, written to `image_track.csv`:
   - horizon line angle (bank);
   - object centroid, size, orientation (second moments) and brightness;
   - background motion from phase correlation on masked tiles (clouds for GIMBAL, ocean for GOFAST).
   - Tests: synthetic rotated-line and moving-texture fixtures.
- [ ] 5. **[W]** Correction tool in `extract/correct/`: a static page plus a small Python standard-library server.
   - It shows each crop with its value and saves edits to `corrections.json`, recording the source as manual and the time.
   - Corrections override other values when the tables are merged.
   - Test: a Playwright round trip.
- [ ] 6. **[me]** Cross-check against the Sitrec CSVs, field by field. Every disagreement gets reviewed in the correction tool.
- [ ] 7. **[bg]** Full extraction runs for GIMBAL, GOFAST and FLIR1.
- [ ] 8. **[V] blind check:**
   - `tools/sample_frames.py --seed 2026 --n 100` picks 100 frames per video for GIMBAL and GOFAST (200 total).
   - Review sheets show raw crops only, never the extracted values.
   - The verifier types its own readings into a CSV.
   - `tools/score_blind.py` reports the error rate per field.

**CP-02 acceptance:** per-frame tables for GOFAST and GIMBAL, with 100 randomly sampled frames per video hand-checked blind by the verifier and the error rate logged. Target: at most 1% per digit field.

**How I prove it:** the blind-check CSVs, the score report, and the Sitrec agreement report in `checkpoints/CP-02.md`.

**Risks and fallbacks:**
- **Compression smears the glyphs:** per-video templates, temporal constraints and the correction tool.
- **Error rate above target after 3 fix attempts:** log the true rate and mark those fields low-confidence. The uncertainty carries into the solver.

## M2 Geometry solver (ends at CP-03)

- [ ] 1. **[me]** `solve/frames.py`:
   - spherical Earth (ECEF and local ENU frames) with a standard-refraction toggle;
   - SI units inside the code, feet, knots and mph on display.
   - Curvature matters: about 800 ft of drop at 30 nmi.
- [ ] 2. **[bg + W]** `solve/weather.py`:
   - an ARCO-ERA5 slice (wind and temperature by pressure level) for each case's window, plus IGRA soundings as a measured check;
   - a wind profile file per case, with its source.
- [ ] 3. **[me]** `solve/jet.py`:
   - TAS from IAS or Mach plus temperature;
   - turn rate from bank, assuming a coordinated turn;
   - heading integrated from an unknown starting heading;
   - ground track from wind;
   - pitch from angle of attack (4 deg plus or minus 2 deg);
   - an uncertainty ensemble.
- [ ] 4. **[me]** `solve/sensor_atflir.py`:
   - two conventions for azimuth and elevation (body frame, or relative to the local horizon), both kept and reported;
   - pod roll and pitch gimbal kinematics and derotation;
   - FOV by zoom from `data/sensors/atflir.yaml`, with citations;
   - round-trip tests.
- [ ] 5. **[me]** Line of sight per frame:
   - Whole-degree readouts are treated as intervals, not exact points.
   - The smooth line of sight is refined with the background flow (logicbear's method).
   - The horizon and cloud evidence decide between the two angle conventions.
- [ ] 6. **[me spec, W+ build]** `solve/families.py`:
   - **constant velocity:** bearings-only target motion analysis; its likelihood as a function of range is the range curve;
   - **constant altitude;**
   - **wind drift;**
   - **stationary in the air mass.**
   - Outputs go to `data/derived/<video>/families/` on a range grid from 0.5 to 60 nmi.
- [ ] 7. **[me]** Reproductions, written up in `docs/reproductions/`:
   - Sitrec GOFAST from Sitrec's own inputs;
   - Sitrec GIMBAL's far path;
   - Peings and von Rennenkampff's GIMBAL path (8 to 6.8 nmi, TAS 363 to 369 kt, wind 120 kt, elevation -1.95 deg, azimuth smoothed over 50 frames).
   - Then each is rerun with this lab's M1 inputs, and every difference is attributed to a specific input or assumption with a sensitivity run.

**CP-03 acceptance:** reproductions within a stated tolerance, or a documented explanation of the difference.

**Tolerance, stated now:**
- line-of-sight RMS residual at most 0.1 deg;
- positions within 0.2 nmi or 3% of range, whichever is larger;
- GOFAST altitude within 300 ft and speed within 5 kt of the published values (pinned at M2 from Sitrec's code and AARO's report).

**How I prove it:** overlay plots plus residual tables. Golden tests lock in the reproductions.

**Risks and fallbacks:**
- **Angle convention ambiguous:** run both conventions and let the data choose. This is likely the crux of the prior disagreement.
- **A prior input is missing:** read the Sitrec source (MIT) for its exact inputs. For the paper, run sensitivity sweeps and document what had to be assumed.
- **Exact date or place is uncertain:** run a wind ensemble over plausible dates and areas, bounded by the "120 knots" on the audio.

## M3 Hypotheses and scoring (ends at CP-04)

- [ ] 1. **[me]** `solve/score.py` is one scoring entry point for every hypothesis.
   - **Criteria:** line of sight (quantization-aware), angular rate, apparent size, rotation, brightness trend (relative only, since there is no radiometric calibration), background-motion consistency, and testimony.
   - Each criterion is a log-likelihood using the uncertainties measured in M1, scaled by an effective sample size (frames are autocorrelated).
   - A BIC penalty for free parameters, applied the same way to every hypothesis.
   - Weights live in `solve/scoring.yaml`. Testimony defaults to 0.25 (Q-002), and all weights are adjustable live in the app.
- [ ] 2. **[me spec, W+ build]** Physical models in `solve/models/` (point target, wind drifter, flapping bird, close small object, distant aircraft with exhaust glare, fast object at the reported range, sensor artifacts):
   - Glare rotation is locked to pod derotation. Size is independent of range for glare and scales as 1/range for real objects.
   - Hypotheses are YAML data in `solve/hypotheses/`, with parameter priors and cited sources.
- [ ] 3. **[W]** `data/testimony/*.yaml`: each claim with its source, quote location and uncertainty band. These are constraints, never ground truth.
- [ ] 4. **[me] + [bg]** Model-recovery test:
   - Synthetic observations are generated from each hypothesis, with M1's real quantization and noise, and run through the full scorer.
   - The result is a confusion matrix showing which hypotheses this data can tell apart even in principle.
   - This is the honest answer to "the data can't decide".
- [ ] 5. **[bg]** Runs for GOFAST, GIMBAL and FLIR1:
   - best-fit parameters and per-criterion scores;
   - range curves of speed, altitude and acceleration, with thresholds marked (balloon drift, birds, airliners, Mach 1).
- [ ] 6. **[me]** Discriminators for each top pair: the single measurement and the precision that would separate them (for example, radar range at a given timestamp, to a given precision). Written to `docs/results/<video>.md`.
- [ ] 7. **[me]** Equal-treatment tests:
   - an AST scan that fails if any `solve/` code branches on a hypothesis name;
   - a rename and permutation invariance test;
   - a single scoring path.

**CP-04 acceptance:** a results table per video with per-criterion scores and range curves; the verifier checks that the hypotheses are treated equally.

**How I prove it:** the results tables and plots, the confusion matrix, and the equal-treatment test output. The verifier gets the code paths and tests, not my narrative.

**Risks and fallbacks:**
- **Flexible hypotheses overfit:** the BIC penalty plus the recovery test.
- **Correlated frames inflate confidence:** the effective-sample-size correction.
- **Perceived bias:** the equal-treatment tests plus a written rationale for every score.

## M4 App (ends at CP-05)

- [ ] 1. **[me]** Design pass:
   - Claude Design through the DesignSync tool if it is available, otherwise the frontend-design skill.
   - A sober instrument-panel look.
   - Mockups go in `docs/design/`, and I review them myself.
- [ ] 2. **[W]** App shell:
   - three.js vendored and pinned in `app/vendor/three/`, with its LICENSE;
   - ES modules and no bundler;
   - a view router;
   - `tools/build_app_data.py` (JSON exports plus JPEG frame sequences) and `tools/serve.py`.
- [ ] 3. **[W]** Cockpit view:
   - an image-sequence player keyed by frame index, so it locks frame-accurately (no `<video>` seeking);
   - the three.js re-render placed beside it, with a difference overlay.
- [ ] 4. **[W]** God's-eye view: the jet, the line-of-sight fan, and the paths for each hypothesis, with a range slider.
- [ ] 5. **[W]** Range explorer:
   - SVG charts interpolated from the Python range grid;
   - a node parity test against the Python numbers.
- [ ] 6. **[W]** Compare-analyses view: Sitrec, Peings and von Rennenkampff, and the lab, side by side.
- [ ] 7. **[W]** Evidence ledger: every number with its source frame, method and confidence. Clicking a row opens the frame. Live weight sliders re-score from the per-criterion log-likelihoods.
- [ ] 8. **[bg]** Playwright screenshots of every view, with headed off-screen Chrome as the fallback.
   - A frame-stepped capture is assembled into a 60-second GIMBAL recording: one real-time pass plus a half-speed pass.
   - A frame-lock metric reports the median pixel error between the re-render and the original (horizon and object position).
- [ ] 9. **[me]** I look at every screenshot myself and fix problems. Then **[V]**, then CP-05.

**CP-05 acceptance:** screenshots of every view; a 60-second recording of GIMBAL with the synthetic re-render locked to the original.

**Risks and fallbacks:**
- **No GPU in headless mode:** headed off-screen Chrome.
- **Drift in the frame lock:** a deterministic capture mode keyed to the frame index.
- **No design tool available:** the frontend-design skill.

## M5 PURSUE cases (ends at CP-06)

- [ ] 1. **[me]** Freeze the PURSUE index at the start of M5. It includes any release published after 10/30/2026 (Q-005).
- [ ] 2. **[me]** One layout and sensor data file per sensor family. Where a sensor's FOV is unpublished, FOV becomes a parameter in the curves.
- [ ] 3. **[W] x up to 5 in parallel**, one per Full-tier clip: run the same extract, solve and score pipeline and write a case folder. I review each one.
- [ ] 4. **[W]** Bounded-tier clips get range-size-speed degeneracy curves from the same range-explorer code (the Haqq-Misra and Kopparapu style). For PR113, the depression-angle assumption is tested against the horizon.
- [ ] 5. **[V]** A spot check, then CP-06.

**CP-06 acceptance:**
- a results table for each viable clip;
- a list of the clips that are not viable, each with its reason;
- a table of the Bounded-tier clips (an addition to the original criteria).

**Risks and fallbacks:**
- **Redaction leaves few or no Full-tier clips:** the Bounded tier plus an honest list of non-viable clips, which still meets the acceptance criteria.
- **Unfamiliar turret symbology:** a layout file per family, plus labeling in the correction tool.

## M6 Exports and wrap (ends at CP-07)

- [ ] 1. **[me]** Case-file format:
   - `schemas/ufo-case-file.schema.json` v0.1 (JSON Schema 2020-12). Its contents: case, sources with hashes, platform and sensor, observables, hypotheses with scores, discriminators, range-curve links, provenance and commit.
   - It is built for the future Case Files project to adopt (Q-006). If that project's spec appears first, I align to it.
- [ ] 2. **[W]** `tools/export_cases.py` writes the cases, and `tools/validate_cases.py` checks them with jsonschema.
- [ ] 3. **[W]** A README for a non-programmer:
   - what each view shows and how to read a range curve;
   - one-line PowerShell 5.1 commands with full paths.
- [ ] 4. **[bg]** A 2-minute highlight recording. Then **[V]**, then CP-07.

**CP-07 acceptance:** the exported cases validate against the case files schema; a 2-minute highlight recording.

## Gaps in SPEC.md and ENGINE.md, with the default for each

| Gap | Default |
|---|---|
| The citations and PURSUE count are wrong | D-005 corrections (see above) |
| Earth model and coordinate frames | Spherical Earth with a refraction toggle; SI units inside the code, feet, knots and mph on display |
| Reference frame of the ATFLIR angles and derotation behavior | Implement both conventions; the data chooses; report both |
| Whole-degree quantization | Interval measurements, never exact points |
| "Same scoring" across hypotheses with different numbers of free parameters | Log-likelihood plus a BIC penalty, the same for every hypothesis; effective sample size for correlated frames |
| Physical parameters for bird, close object and distant aircraft | Cited priors in the hypothesis YAML files |
| Brightness criterion | Relative trend only, since there is no radiometric calibration |
| Unknown jet pitch | Angle of attack 4 deg plus or minus 2 deg, with sensitivity runs |
| Source of wind data | ARCO-ERA5 (no account), cross-checked with IGRA soundings |
| No public transcript of the audio | faster-whisper with word confidences, labeled inferred |
| FLIR1's official copy is the worse one | Keep both copies, aligned; the canonical one is whichever reads more clearly; provenance labeled |
| Trajectory "range profile" is undefined | Four named families (see M2) |
| PURSUE has a middle case between viable and not viable | Add the Bounded tier |
| How the app locks to the original video | Image sequences, not `<video>` seeking |
| The case-file schema doesn't exist | v0.1 in this repo (Q-006) |
| Python version | 3.12 pinned through uv (D-006) |
| Sitrec2 license is unclear | Port only from a pinned Sitrec v1 commit, with a NOTICE file |
| Testimony format | YAML claims with a source, a quote location and an uncertainty band |
| Hosting | Local only, private (Q-003) |

**New questions:**
- Q-004: is the folder location OK?
- Q-005: freeze the PURSUE scope at the start of M5?
- Q-006: is case-file schema v0.1 OK?

None of these block work.

## Verification (end to end)

- `tools/gate.py` (pytest plus the node parity tests) passes at every checkpoint, with no skipped tests.
- The independent verifier checks every CP against the acceptance criteria in `_PLAN.md`.
- The tests that matter most for trust:
  - blind transcription accuracy (CP-02);
  - golden reproductions (CP-03);
  - the model-recovery confusion matrix and the equal-treatment tests (CP-04);
  - the frame-lock metric (CP-05);
  - schema validation (CP-07).
- I view every screenshot and recording myself before posting a checkpoint.
- Usage is checked between milestones, and the run pauses cleanly near 98% of the weekly quota. At most 6 jobs run at once, and processes are killed by PID only.
