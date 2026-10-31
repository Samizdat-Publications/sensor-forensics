# Where the prior analyses disagree, and why

Compiled 10/30/2026 for CP-01. Sources: Sitrec v1 at commit `83891bf` (`sitrec.md`), Peings and von Rennenkampff 2023 (`peings-vonrennenkampff-2023.md`, "P&vR"), AARO's GOFAST case resolution (`aaro-gofast.md`), Haqq-Misra and Kopparapu 2026 (`haqq-misra-kopparapu-2026.md`, "H-M&K"), logicbear's notebooks (`logicbear-uap-nb.md`), and this lab's own M0 audit (`docs/audit/`). Page and line citations are in those files.

Each row says what differs, the cause, how much it matters, and what would settle it. "Lab test" names the milestone where this lab checks it.

## GIMBAL

| # | Point | Sitrec | P&vR 2023 | Cause of the difference | Why it matters | What would settle it | Lab test |
|---|---|---|---|---|---|---|---|
| G1 | **Range** | Default "far" sitch starts at 32 nmi (constant air speed 340 kt); a near variant at 6 nmi exists. No range is stated as a result. | Starts at 8 nmi, ends at 6.8 nmi | Range is not on screen. Sitrec explores the distant-jet hypothesis; P&vR take the aircrew's "within 10 nmi, 6 to 8 nmi" and a measured 15 percent growth in apparent size | Every speed, altitude and maneuver claim follows from the range | Radar range at any timestamp. Without it: the size-growth test (G8) and line-of-sight consistency over range | M2 range curves, M3 discriminators |
| G2 | **Does the object stop and reverse?** | Not stated: the repo prints no speed profile for either variant (`sitrec.md`, Results). P&vR's own reproduction of a level path near 30 nmi needs air speed rising from 300 to 450 kt (P&vR p. 16, Fig. A7) | Yes at 8 nmi: ground speed near 0 at about frame 720, a "vertical U-turn" in the air frame | Follows from G1: the same lines of sight imply different motion at different ranges | This is the "anomalous maneuver" claim | Range (G1) | M2 families over range |
| G3 | **Why the image rotates** | Glare fixed in the pod optics, rotated in the image by the derotation mechanism as the pod rolls; steps when the pod roll jumps | Physical rotation of the object; P&vR do not model pod roll or derotation, and cite the ATFLIR patent and two unnamed experts against stepwise roll | Different sensor models; only Sitrec implements one | Decides whether the rotation is evidence about the object at all | Whether the background (clouds, horizon) rotates with the steps, and whether a pod-roll model predicts the step times from the on-screen angles alone | M2 sensor model, M3 rotation criterion |
| G4 | **Jet true airspeed** | 351 kt ("from CAS of 241") | 363 to 369 kt (IAS 238 to 242 at -25 C, e6bx calculator) | The paper's conversion; this lab's standard conversion gives 352 to 360 kt from IAS and about 352 to 359 kt from the on-screen Mach 0.58 to 0.59 | About 4 percent on the jet path length, which shifts every line of sight's origin | Settled by computation: the lab finds about 352 to 360 kt (`tests/test_atmosphere.py`) | M2 sensitivity run |
| G5 | **Jet turn rate** | Default is solved to match a hand-keyed cloud-speed curve; bank-based rate is an option (and reads a fixed 351 kt) | From bank every 10 frames, ROT = 1091 tan(bank)/TAS | Different evidence chosen to drive the jet's heading | Turn rate sets the lines-of-sight geometry, which is what range inference rests on | Agreement between bank-derived and cloud-derived turn rates; disagreement would point to pitch, sideslip or bank-reading error | M1 bank extraction, M2 jet model |
| G6 | **Elevation** | -2.01 rising to -1.985 deg (hand fit) | -2.0 rising to -1.95 deg (hand fit to the cloud line) | The display shows whole degrees only (-2, so anywhere from -1.5 to -2.5); both fits are judgment calls | At 30 nmi, 0.5 deg of elevation is about 1,600 ft of object altitude; also decides whether a level path exists | Cloud-line and horizon geometry measured in the frames, treated as an interval constraint, not a point | M1 image cues, M2 interval treatment |
| G7 | **Azimuth smoothing** | Gaussian smoothing (contributor "Markus") of the integer readout | 50-frame moving average plus an unquantified cloud-motion adjustment | Integer readout updating every other frame; both smooth differently | Smoothing choices change implied angular rates, which drive inferred accelerations | Interval-aware fit of the readout, constrained by background motion | M2 line-of-sight fit |
| G8 | **Apparent size change** | Treated as glare; size not tied to range | Grows about 15 percent, read as a 13 percent decrease in range | Different hypotheses about what the bright blob is | A real object's size scales as 1/range; a glare's does not | Size measured within one polarity, with the brightness trend alongside | M1 object track, M3 size criterion |
| G9 | **Wind** | Jet: 120 kt from 270; object: 65 kt from 274 (far) or 120 kt from 280 (near); jet heading 315 | 120 kt, 35 deg left of the jet's initial heading (absolute heading not given) | Audio "120 knots" plus different reanalysis reads; date unresolved (01/21, 01/24 or 01/25/2015) | Wind sets ground track and what "stationary" means | ERA5 for each candidate date at the stated area | M2 weather ensemble |
| G10 | **Angle convention** | Az/El treated as world-levelled angles relative to the jet's velocity; jet pitch 3.6 deg scaled by 1/cos(bank) | Az described as relative to boresight but applied to the heading track; pitch ignored | Neither documents the ATFLIR's convention from a primary source | A few tenths of a degree, which matters at 30 nmi | Implement both conventions; test against horizon and cloud geometry | M2 sensor model |
| G11 | **Frame indexing** | 1031 frames at 29.97 fps | "1034 frames at 30 fps", samples at frames 1, 11, ... 1031 | Different copies or counting | Misaligned comparisons by a few frames | This lab's copy decodes to 1031 frames; offsets found against Sitrec's per-frame azimuth | M1 cross-check |
| G12 | **"Fleet" on radar** | Cosmetic five-object fleet in the sitch | Treated as consistent with the aircrew account | Testimony only; no radar data released | Context for the hypotheses, not a measurement | Radar data | M3 testimony (low weight, Q-002) |
| G13 | **Field of view** | 0.35 deg | 0.35 deg (0.7 tested) | Documentation conflicts | Sets object size estimates | Cited ATFLIR documentation | M2 sensor data file |

## GOFAST

| # | Point | Sitrec | AARO | Cause | Why it matters | What would settle it | Lab test |
|---|---|---|---|---|---|---|---|
| F1 | **Object altitude** | About 13,150 to 13,210 ft (from a 2024 headless run; the repo prints no result) | 13,000 ft assessed (13,219 and 13,150 ft computed) | Agree within about 200 ft; small differences from smoothing and Earth model | Low: both rule out a sea-skimming object | Agreement already; the lab adds curvature and refraction explicitly | M2 reproduction |
| F2 | **Object speed** | Ground speed about 66 kt roughly downwind; air speed about 2 kt against a 65 kt wind | Intrinsic 5 to 92 mph; ground 72 to 161 mph depending on heading relative to wind | Sitrec fixes a jet heading and winds; AARO spans the unknown heading | Decides "balloon drifting with the wind" vs "object under its own power" | Jet heading (not shown) and the wind at 13,000 ft on the date | M2 weather, M3 wind-drift model |
| F3 | **Closure rate (Vc)** | Not among the GOFAST sitch inputs (AZ, El, RNG and tilt CSVs only: `sitrec.md`, GOFAST inputs) | Not among the stated inputs (pointing angles and range: `aaro-gofast.md`, Inputs) | Not explained by either source | Range rate is an independent check on the object's speed along the line of sight | The lab reads Vc every frame and tests it against range change and the jet's velocity | M1, M2 |
| F4 | **Inputs** | Azimuth from a hand-drawn editor curve by default, not the CSV; turn rate reads 351 kt while the jet moves at 369 kt | Two sample instants and a continuous path | Implementation choices | Small, about 5 percent on turn rate | Reproduce both from their own inputs | M2 |

## FLIR1

| # | Point | Sitrec | Others | Cause | What would settle it |
|---|---|---|---|---|---|
| T1 | **What the object is** | Visual recreation only (straight jet path, constant air speed object at an assumed 10 nmi); no numeric conclusion in the repo | Aircrew testimony (a fast, maneuvering object); public "distant plane" readings | No range on screen; jet path unknown (bank 0 assumed) | Radar data; failing that, results as curves over range (this lab, M3) |

## PURSUE

| # | Point | H-M&K 2026 | This lab | Cause |
|---|---|---|---|---|
| P1 | **How many videos** | 112 across Releases 01, 02, 04, 05 (none in 03) | 134 across Releases 01 to 06 in the official database as of 10/30/2026 | Later releases (R06), FBI and local law enforcement clips in R03 and R06 |
| P2 | **Kinematic inference** | No clip supplies range, own speed, aspect and field angle together, so speed cannot be inferred | Agrees as a starting point; triage looks for clips where on-screen symbology or a scene reference supplies some of the four | Same principle; the lab's job is to check clip by clip |
| P3 | **PR113 scale** | Burned-in 5 to 35 scale assumed to be depression angle, giving about 54 deg horizontal field of view | To be tested against the horizon in the clip (M5) | Assumption stated by the authors |

## Points of agreement worth stating

- Range is the decisive missing quantity for GIMBAL and FLIR1 (Sitrec, P&vR and H-M&K all say so).
- Sitrec and P&vR reproduce each other's close-range GIMBAL paths ("remarkably consistent", P&vR p. 16); P&vR also find the roughly 30 nmi solution, but describe it as not steady.
- Sitrec and AARO agree that GOFAST's object is at about 13,000 ft, so the "skimming the sea" impression is parallax.
