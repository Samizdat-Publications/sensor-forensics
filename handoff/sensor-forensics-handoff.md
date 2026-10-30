# Handoff package: sensor-forensics

All package files except the shared boilerplate (AUTONOMY.md, CP template, Claude Code settings and agents, which match the other handoffs plus the control tower status rule), concatenated for reading in claude.ai. The working copy is the zip.

---

## FILE: KICKOFF.md

````
# KICKOFF: Sensor Forensics Lab (for Stewart)

A forensic reconstruction of the Navy targeting-pod videos (GIMBAL, GOFAST, FLIR1 "Tic Tac") and the 2026 PURSUE releases. It reads the telemetry burned into each video frame, rebuilds the jet's flight path and the camera's line of sight in 3D, then tests every competing explanation (distant aircraft, balloon, bird, close fast object, sensor artifacts like glare and gimbal rotation) against the same footage. The radar data stays classified, so the lab shows what each possible range implies instead of pretending to know the range.

## 1. One-time setup (PowerShell)

Extract the zip into `C:\Users\stewa\Documents\Claude\Claude Code Ideas\handoffs\`, then:

```powershell
cd "C:\Users\stewa\Documents\Claude"
Copy-Item -Recurse "C:\Users\stewa\Documents\Claude\Claude Code Ideas\handoffs\sensor-forensics" "C:\Users\stewa\Documents\Claude\sensor-forensics"
cd "C:\Users\stewa\Documents\Claude\sensor-forensics"
git init -b main
Move-Item "claude-setup" ".claude"
```

## 2. Start Claude Code in the folder

1. Open a new Claude Code session on `C:\Users\stewa\Documents\Claude\sensor-forensics`.
2. Accept the folder trust prompt.
3. For planning: `/model opus`, then `/effort max`.
4. Switch to plan mode (Shift+Tab).

## 3. Paste this prompt

```
You are taking over a new project from a handoff package: the Sensor Forensics Lab, a forensic reconstruction of the Navy GIMBAL, GOFAST, and FLIR1 videos and the 2026 PURSUE sensor videos. Read CLAUDE.md and follow its boot order, starting with AUTONOMY.md.

The rule that governs everything: this is a hypothesis-testing lab. Every explanation, mundane or anomalous, is run through the same geometry and physics and scored against the same frame-by-frame evidence. Where the public data can't decide between explanations, the lab must say so and show exactly which missing measurement would decide it. Reproduce the existing published analyses first (Mick West's open-source Sitrec models, and the 2023 GIMBAL flight path paper by Graves and colleagues), so we know where and why they disagree.

Start with a data audit at M0: for each video, list exactly which quantities are readable on screen frame by frame, which are inferred, and which are unknown. Then produce the execution plan for M0 through M6 in _PLAN.md. For each milestone give the work items in order, which ones you will delegate to the worker subagent, what runs in the background, how you will prove each acceptance criterion, and the top risks with a fallback for each. List any gaps you see in SPEC.md or ENGINE.md and the default you will use for each.

When I approve the plan, execute autonomously per AUTONOMY.md: post a checkpoint message at every CP, keep going without waiting for my replies, log questions with defaults in QUESTIONS.md, and stop only for a true blocker. Start with M0.
```

## 4. Approve and let it run

1. Approve with the auto mode (or auto-accept edits) option, then `/effort high`.
2. Optional `/goal`:
   ```
   /goal Every milestone M0 through M6 in _PLAN.md is marked [x] with its checkpoint file written, or BLOCKED.md describes a true blocker and no unblocked work remains
   ```
````

---

## FILE: CLAUDE.md

````
# CLAUDE.md: Sensor Forensics Lab

## Boot order (every session, and after every compaction)

1. AUTONOMY.md
2. NEXT-SESSION.md
3. _PLAN.md
4. DECISIONS.md
5. QUESTIONS.md
6. ENGINE.md
7. SPEC.md
8. DATA.md

## Mission

Reconstruct, as forensically as the public data allows, what the sensors saw in:

- **GIMBAL** (January 2015, F/A-18F, ATFLIR pod, infrared)
- **GOFAST** (January 2015, ATFLIR, infrared, with range on screen)
- **FLIR1 / "Tic Tac"** (November 2004, USS Nimitz group)
- **The PURSUE sensor videos** released by the Department of War in 2026 (112 videos across five tranches), where the on-screen data allows it.

For each video: rebuild the jet's path, the camera's line of sight and field of view per frame, and the family of possible object trajectories, then score each explanation against the footage and the witness testimony.

## People and authority

- **Owner:** Stewart Gregerson. He wants forensic testing of hypotheses, not confirmation of any belief. His rulings outrank everything.
- **References:** the released videos and their on-screen symbology; public ATFLIR and F/A-18 documentation; Sitrec (Mick West, open source on GitHub; check its license before reusing code); Graves et al. 2023, "Reconstruction of Potential Flight Paths for the January 2015 Gimbal UAP" (arXiv 2306.08773); Haqq-Misra 2026, "Limits on Kinematic Inference from the PURSUE Airborne Sensor Videos" (arXiv 2608.12445); aircrew public testimony (Graves, Fravor, Dietrich, and others) as constraints with stated uncertainty.

## Standing rules

- **Same geometry, same scoring for every hypothesis.** No per-hypothesis fudge factors.
- **Read the frame, don't guess it.** Every on-screen number is extracted per frame with a confidence; inferred values are labeled inferred.
- **Show the range problem honestly.** Where range is unknown, results are curves over range, not a single answer.
- **Credit and compare prior work.** Reproduce Sitrec and the 2023 paper; document every point of agreement and disagreement and why.
- No emdashes anywhere Stewart reads.
````

---

## FILE: _PLAN.md

````
# _PLAN.md: Sensor Forensics Lab

Status legend: [ ] open, [~] in progress, [x] done (with evidence in a checkpoint file).

## M0 Data audit (ends at CP-01)

- [ ] Repo hygiene. Private GitHub repo `Samizdat-Publications/sensor-forensics`.
- [ ] Get official copies of GIMBAL, GOFAST, FLIR1; index the PURSUE releases.
- [ ] Per video: a table of readable, inferred, and unknown quantities. PURSUE triage: which clips have enough symbology to reconstruct.
- [ ] Read and summarize Sitrec's approach, the 2023 GIMBAL paper, and the 2026 PURSUE paper; list their points of disagreement.

**CP-01 acceptance:** the audit tables; the PURSUE triage list; the disagreement list. A plain verdict on how far each video can be reconstructed.

## M1 Symbology extraction (ends at CP-02)

- [ ] OCR and template matching per frame; correction tool; confidence values.

**CP-02 acceptance:** per-frame tables for GOFAST and GIMBAL, with 100 randomly sampled frames hand-checked by the verifier (error rate logged).

## M2 Geometry solver (ends at CP-03)

- [ ] Jet path, line of sight, trajectory families over range.
- [ ] Reproduce Sitrec's GOFAST result and the 2023 paper's GIMBAL path from their stated inputs.

**CP-03 acceptance:** reproductions within a stated tolerance, or a documented explanation of the difference.

## M3 Hypotheses and scoring (ends at CP-04)

- [ ] All hypotheses in SPEC.md; scoring; discriminator analysis.
- [ ] GOFAST, GIMBAL, FLIR1 results.

**CP-04 acceptance:** a results table per video with per-criterion scores and the range curves; the verifier checks equal treatment of hypotheses.

## M4 App (ends at CP-05)

- [ ] Design pass, then cockpit, god's-eye, range explorer, compare, evidence ledger views.

**CP-05 acceptance:** screenshots of every view; a 60-second recording of GIMBAL with the synthetic re-render locked to the original.

## M5 PURSUE cases (ends at CP-06)

- [ ] Reconstruct every PURSUE clip the triage marked viable, through the same pipeline.

**CP-06 acceptance:** a results table for each viable clip; a list of non-viable clips with the reason.

## M6 Exports and wrap (ends at CP-07)

- [ ] Export each case to the UFO Case Files format; README for a non-programmer.

**CP-07 acceptance:** exported cases validate against the case files schema; a 2-minute highlight recording.
````

---

## FILE: SPEC.md

````
# SPEC.md: Sensor Forensics Lab

## Pipeline per video

1. **Ingest:** official copy, frame extraction, hash.
2. **Symbology extraction:** OCR and template matching of every on-screen field per frame; manual correction tool; confidence per value.
3. **Jet reconstruction:** jet path from altitude, airspeed, bank and heading cues (horizon line, turn rate), with uncertainty.
4. **Line of sight:** per-frame vectors from pod angles, corrected for jet attitude; field of view from zoom.
5. **Object track in image:** position, size, orientation, brightness of the object per frame; background motion (clouds, ocean) for independent checks of camera motion.
6. **Trajectory families:** for each candidate range (or range profile), solve the object's 3D path; compute speed, acceleration, altitude.
7. **Hypotheses:** each is a physical model with parameters:
   - distant aircraft (jet exhaust glare), balloon drifting with measured winds, bird, a close small object, a fast object at the aircrew-reported range, sensor artifacts (glare that rotates with the pod's derotation, focus and zoom effects)
   - plus any hypothesis Stewart adds (Q-001)
8. **Scoring:** how well each hypothesis reproduces the observed line of sight, angular rate, apparent size, rotation, brightness, and background motion, plus consistency with testimony (weighted, adjustable).
9. **Discriminators:** for each pair of top hypotheses, the measurement that would separate them (for example, radar range at one timestamp).

## The experience (three.js web app)

- **Cockpit view:** the original video beside a synthetic re-render from the reconstructed geometry, frame-locked, with a difference overlay.
- **God's-eye view:** the jet, the line-of-sight fan, and each hypothesis's object path in 3D, with a range slider.
- **Range explorer:** speed, altitude, and acceleration of the object as functions of assumed range, with physically notable thresholds marked (balloon drift speed, bird speeds, airliner speeds, sonic speed).
- **Compare analyses:** Sitrec's solution, the 2023 paper's solution, and the lab's, side by side.
- **Evidence ledger:** every number, its source frame, and its confidence.
- Design pass with Claude Design if available, else the frontend-design skill.

## Exports

Each case exports in the UFO Case Files format (shared with Stewart's case files project) so it appears there too.
````

---

## FILE: DATA.md

````
# DATA.md: public data (verify at M0)

| Source | What it gives | Notes |
|---|---|---|
| GIMBAL, GOFAST, FLIR1 videos (officially released by the Navy and DoD in 2020) | Frame-by-frame symbology: pod azimuth and elevation angles, jet altitude, airspeed or Mach, time, field of view or zoom, sensor mode; GOFAST shows range | Get the highest-quality official copies; record hashes |
| Audio on GIMBAL and GOFAST | Aircrew comments | Transcribe with timestamps |
| PURSUE releases (war.gov/UFO, 2026) | 112 sensor videos from targeting pods and turrets; redactions limit on-screen data | Triage which ones have enough symbology; the 2026 Haqq-Misra paper notes one clip (DOW-UAP-PR113) has depression-angle markings that reconstruct the field of view |
| Aircrew testimony | Claimed ranges, formation of objects, radar observations | Constraints with uncertainty, never ground truth |
| Weather | Upper-air winds and temperatures for the dates and areas (reanalysis data such as ERA5) | Needed for balloon and drift hypotheses |
| Air traffic | Commercial flight history is generally not available for those dates offshore; test "distant airliner" hypotheses geometrically and with published route structures | Note what can't be checked |
| ATFLIR and F/A-18 documentation | Pod gimbal limits and derotation behavior, field of view per zoom level, symbology meaning | Public manuals and reputable analyses; cite each |

**What's missing (and why it matters):** the radar tracks (range, altitude, speed), the full uncut videos, the navigation data from the jets, and the other ships' sensors. The lab expresses conclusions as functions of these unknowns.
````

---

## FILE: ENGINE.md

````
# ENGINE.md: binding engineering contract

Change this file only through a DECISIONS.md entry.

## Stack

- **Extraction and solving:** Python 3.11+ (opencv, numpy, scipy, an OCR engine, pandas); deterministic, tested.
- **App:** three.js (vendored, pinned), ES modules, no bundler; static, local preview; Playwright for screenshots.
- **Reuse:** if Sitrec's license allows, reuse or port pieces with attribution; otherwise reimplement from its documented methods and compare outputs.

## Repo layout

```
extract/       frame extraction, symbology OCR, correction tool
solve/         jet path, line of sight, trajectory families, hypotheses, scoring
app/           three.js web app
data/videos/   official videos (gitignored if large), hashes committed
data/derived/  per-frame tables (committed when small)
tests/  tools/  artifacts/  checkpoints/
```

## Rules

- Every derived number traces to frames and a method.
- Hypotheses are data files; no per-hypothesis code paths beyond their physical model.
- No emdashes in UI strings.
````

---

## FILE: DECISIONS.md

````
# DECISIONS.md: owner rulings and binding choices

Newest at the bottom. Stewart's rulings are marked (owner ruling) and outrank everything.

- D-001 (owner ruling, 10/30/2026): Build as forensic a recreation of GIMBAL and GOFAST as the public data allows; test hypotheses, don't confirm a belief.
- D-002 (10/30/2026): Include FLIR1 and the 2026 PURSUE sensor videos where the on-screen data allows reconstruction.
- D-003 (10/30/2026): Reproduce prior public analyses first and document disagreements.
- D-004 (10/30/2026): Repo `Samizdat-Publications/sensor-forensics`, private.
````

---

## FILE: QUESTIONS.md

````
# QUESTIONS.md: open questions for Stewart

None of these block work. Answer by typing `Q-xxx: <answer>` in the session, or by writing under the question.

| ID | Question | Why it matters | Default in use | Rework if different | Needed by | Status |
|---|---|---|---|---|---|---|
| Q-001 | Any specific hypothesis or analyst's claim you want tested? Name the source. | Scope | The SPEC.md list | Low | CP-04 | Open |
| Q-002 | How much weight should aircrew testimony get by default (you can change it live)? | Scoring | Low, adjustable in the app | None | CP-04 | Open |
| Q-003 | Publish results on the hub later? | Sharing | Private | None | CP-07 | Open |

## Answers from the control tower
````

---

## FILE: NEXT-SESSION.md

````
# NEXT-SESSION.md

Last updated: 10/30/2026 (handoff package, before the first session)

## Where we are

Nothing has been built yet.

## Do next

1. Follow the CLAUDE.md boot order.
2. Produce the execution plan (plan mode). After Stewart approves it, start M0 and run autonomously per AUTONOMY.md.
````

---

## FILE: .gitignore

````
data/videos/*.mp4
data/videos/*.mov
data/frames/
node_modules/
__pycache__/
*.pyc
.venv/
.env
.env.*
!.env.example
artifacts/movies/frames/
````

---

## FILE: .tower/status.json

````
{
  "project": "sensor-forensics",
  "title": "Sensor Forensics",
  "updated": "2026-10-30T15:30:00-04:00",
  "milestone": "M0",
  "milestone_title": "Not started",
  "progress": {
    "done": 0,
    "total": 0
  },
  "last_checkpoint": null,
  "headline": "Handoff package ready; waiting for the first planning session.",
  "needs_stewart": [],
  "blocked": false,
  "blocker": null,
  "highlights": []
}
````
