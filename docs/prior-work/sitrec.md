# Sitrec (Mick West): GIMBAL, GOFAST and FLIR1 sitches

- **Title:** Sitrec ("Situation recreation"), web application, GIMBAL / GOFAST / FLIR1 sitches
- **Author:** Mick West, with input from Metabunk members (README.md:11)
- **Date of pinned snapshot:** main as of 09/16/2025
- **URL:** https://github.com/MickWest/sitrec
- **Commit pinned:** `83891bf95eba1642b52362672cace0729e778727`
- **License:** MIT (LICENSE, "Copyright (c) 2023-2024 Mick West"). README.md:3-7 states "Sitrec has reached end of life", that development continues as Sitrec2 at https://github.com/MickWest/sitrec2, and that "Sitrec verion 1 remains MIT licensed" (sic). The Sitrec2 license was NOT checked and may differ. Only the v1 repo at the pinned commit is covered here. Reuse of v1 code or data with attribution is permitted by the MIT text (copy in `data/reference/sitrec/NOTICE.md`).
- **Prepared:** 10/30/2026, by reading the files at the pinned commit and one 2024 notebook that ran Sitrec headless (see "Provenance of numbers").

## How to read the citations

Every file is cited as `file:line` and resolves to
`https://github.com/MickWest/sitrec/blob/83891bf95eba1642b52362672cace0729e778727/<path>#L<line>`.

| Short name | Path at the pinned commit |
|---|---|
| SitGimbal.js | `src/sitch/SitGimbal.js` |
| SitGoFast.js | `src/sitch/SitGoFast.js` |
| SitFlir1.js | `data/flir1/SitFlir1.js` |
| JetStuff.js | `src/JetStuff.js` |
| JetHorizon.js | `src/JetHorizon.js` |
| JetUtils.js | `src/JetUtils.js` |
| par.js | `src/par.js` |
| CNodeJetTrack.js | `src/nodes/CNodeJetTrack.js` |
| CNodeTurnRateBS.js | `src/nodes/CNodeTurnRateBS.js` |
| CNodeTurnRateFromClouds.js | `src/nodes/CNodeTurnRateFromClouds.js` |
| CNodeLOSTrackAzEl.js | `src/nodes/CNodeLOSTrackAzEl.js` |
| CNodeLOSTraverse.js | `src/nodes/CNodeLOSTraverse.js` |
| CNodeLOSTraverseConstantSpeed.js | `src/nodes/CNodeLOSTraverseConstantSpeed.js` |
| CNodeInterpolateTwoFramesTrack.js | `src/nodes/CNodeInterpolateTwoFramesTrack.js` |
| CNodeWind.js | `src/nodes/CNodeWind.js` |
| CNodeSwitch.js | `src/nodes/CNodeSwitch.js` |
| LLA-ECEF-ENU.js | `src/LLA-ECEF-ENU.js` |
| SphericalMath.js | `src/SphericalMath.js` |
| SituationSetup.js | `src/SituationSetup.js` |
| utils.js | `src/utils.js` |
| CUnits.js | `src/CUnits.js` |
| gimbal.test.js | `test/console/gimbal.test.js` |

## Provenance of numbers (read this first)

Sitrec does not hard-code its trajectory results. Object altitude, speed and range are computed live from the inputs below. The pinned repo contains exactly one locked numeric output for GIMBAL (the horizon angle at frame 435, gimbal.test.js:20). Therefore this file separates three kinds of numbers:

1. **STATED in code**: a literal in a source file (cited file:line).
2. **OBSERVED**: printed by an actual Sitrec run. The only such source found is the 2024 notebook https://github.com/0x1beef/uap_nb (`src/gofast_ranging.ipynb` cell 8 output, `src/gimbal_object_data.ipynb` cell 17 output; pinned at its commit `7c8852df564ad6090d7d362ca1427eb590a005b0`), which ran a Sitrec HEAD of about 11/2024 headless. That is NOT the pinned 09/16/2025 commit; the sitch inputs it loads are the same CSV names.
3. **RECOMPUTED by this lab** (10/30/2026): a Python re-implementation of the SitGoFast default pipeline from the pinned CSVs (flat-Earth approximation, so a few metres of curvature drop are ignored). Marked "LAB RECOMPUTATION". It is not a Sitrec printout. The scratch script is not part of the repo; reproduce it from the "Method" section before relying on it.

## Inputs

### Common to GIMBAL and GOFAST (jet model)

| Quantity | Value | Source location |
|---|---|---|
| Frame rate | 29.97 fps | SitGimbal.js:46, SitGoFast.js:65 |
| Frames | 1031 (0 to 1030) | SitGimbal.js:47, SitGoFast.js:66 |
| Jet position origin | lat 28.5, lon -79.5 ("arbitrary lat/lon, off the coast of Florida") | SitGimbal.js:59-61, SitGoFast.js:74-76 |
| Jet altitude | 25,000 ft constant (slider 24,500 to 25,500) | SitGimbal.js:65, SitGoFast.js:80 |
| Earth model for tracks | Sphere of radius 6,378,137 m (WGS84 equatorial radius used as a sphere; local up = unit vector from a centre at (0, -R, 0)); no refraction adjustment | LLA-ECEF-ENU.js:37-40, SphericalMath.js:176-180, CNodeJetTrack.js:48 |
| Earth radius for cloud/horizon nodes | `radiusMiles` = 3963.190592 statute miles (same WGS84 equatorial radius) | LLA-ECEF-ENU.js:40, SituationSetup.js:57 |
| Gravity in turn-rate formula | g = 9.77468 m/s^2 ("local gravity at 36 deg latitude, 25000 feet") | CNodeTurnRateBS.js:10 |
| Turn-rate formula | rate = degrees(g * tan(bank) / V), V in m/s | CNodeTurnRateBS.js:9-13 |
| Local (jet) wind | 120 kt from 270 deg (GIMBAL), 120 kt from 270 deg (GOFAST) | SitGimbal.js:415-416, SitGoFast.js:136-141 |
| Target wind | 65 kt from 274 deg (GIMBAL far and GOFAST); 120 kt from 280 deg (GIMBAL near) | SitGimbal.js:413-414, 519-520; SitGoFast.js:128-133 |
| Wind sign convention | `from` = true compass heading the wind comes from; per frame the jet position is advanced by `speed/fps` along its heading, then the wind displacement (`knots/fps` along the downwind direction) is added | CNodeWind.js:17, 92-105; CNodeJetTrack.js:68-74 |

### GIMBAL (SitGimbal.js, "Gimbal (Far)" = default `SitGimbal`)

| Quantity | Value | Source location |
|---|---|---|
| Jet true airspeed (TAS) | 351 kt default (slider 320 to 360). Code comment: "351 from CAS of 241 (239-242)" | SitGimbal.js:699; CNodeJetTrack.js:68-69 comments; par.js:63 (`TAS: 351`) |
| Jet initial heading | 315 deg true | SitGimbal.js:853-860 |
| Jet bank (roll) | Recorded: CSV column 3 `bank_angle` negated (22.6 to 38.2 deg, left bank). Alternative: user constant -35 deg | SitGimbal.js:714-722; GimbalData.csv col 3 |
| Turn rate (default) | `Match Clouds` = first input of the switch, so it is the default; alternatives `From Bank and Speed`, user constants | SitGimbal.js:789-813; CNodeSwitch.js:22, 106-112 (default = first key) |
| Turn-rate-from-clouds target | A hand-keyed cloud angular-speed curve (`cloudSpeedEditor`), points `[0,-0.155, 181.334,-0.132, 433.866,-0.091, 354.555,-0.102, 718.438,-0.055, 632.133,-0.069, 1030,-0.013, 897.667,-0.023]` ("trying to match TheCholla's measurements of cloud speed") | SitGimbal.js:758-774 |
| Cloud-top altitude | 11,740 ft | JetStuff.js:1038-1043 |
| Cloud wind | 17 kt from 240 deg | SitGimbal.js:411-412 |
| Azimuth (default) | `Az Markus Smoothed` = minus CSV column 5 `gaussian_smoothed_azimuth` (54 to -6.4 in file, so -54 to +6.4 in Sitrec: negative = left of nose) | SitGimbal.js:643-646, 667-678; GimbalData.csv col 5 |
| Azimuth alternatives | `Az Editor` curve, `Az Unsmoothed` (minus col 4, integer-valued raw), `Linear` (-54 at frame 18 to +7 at frame 1023) | SitGimbal.js:667-678 |
| Elevation | `el(f) = elStart + elRise * f/frames`, elStart = -2.01, elRise = 0.025, so -2.010 at frame 0 to about -1.985 at frame 1030 | SitGimbal.js:700-709 |
| Pod FOV in look view | 0.35 deg (look camera `fov: 0.35`) | SitGimbal.js:86, 409 |
| Jet pitch | par.jetPitch = 3.6 deg, scaled by 1/cos(abs(bank)) when `scaleJetPitch` is true | par.js:12, 51; JetUtils.js:11-19 |
| Glare/derotation angle (default) | `Markus Keyframe` = minus CSV column 13 `KF Deg Adj` (-48.72 to 65.46 in file); other options: unsmoothed col 1, moving average (6 frames) of col 1, `Markus Smoothed` col 6, `MickKeyframe` from GimbalRotKeyframes.csv | SitGimbal.js:727-742 (default string at 737); GimbalData.csv; GimbalRotKeyframes.csv |
| Pod-roll start offset | `par.glareStartAngle` initial 90 - 32.3 = 57.7 deg, then auto-tuned by `calculateGlareStartAngle()` | par.js:29; JetHorizon.js:120-164 |
| Initial glare rotation ramp | 6 deg, removed linearly over frames 0 to 697 ("go from +6 to +0") | par.js:30; JetUtils.js:118-124 |
| `deroFromGlare` | true for GIMBAL (the glare/derotation angle drives the pod, not the ideal-derotation geometry) | SitGimbal.js:121; JetHorizon.js:175-181 |
| Object (far) start distance | 32 NM along the first LOS | SitGimbal.js:397; unit "big" = NM when the Nautical system is active (CUnits.js:15-20); the 2024 notebook log prints "CUnits: changeUnits: nautical" at startup (gofast_ranging.ipynb cell 7 output), but the pinned sitch files do not set the unit system themselves |
| Object (far) speed | 340 kt, default traverse `Const Air Spd` (constant air speed, wind = target wind) | SitGimbal.js:401-402; JetStuff.js:661-669 (speedScaled); CNodeLOSTraverseConstantSpeed.js:147-150 |
| Object (near) start distance and speed | 6 NM, 320 kt, default traverse `Straight Line`, `relativeHeading` 10 deg, target size 1 (sphere diameter, "around 22 feet" per the code comment) | SitGimbal.js:503-508, 505, 524 |
| Object (near sitch) extra "FAR" path | `FARLOSTraverseConstantSpeed`: start distance 55,560 m (30.0 NM exactly), ground speed (airSpeed false), 320 kt | SitGimbal.js:526, 532-541 |
| Fleet ("5 objects") | 5 `CNodeFleeter` objects, turn rate 8 deg/s, acceleration 2 (far) / 4 (near), spacing 0.7 / 0.99, offsets in NM; cosmetic, tied to the aircrew "fleet" remark | SitGimbal.js:176-205, 386-392, 482-487 |
| Date and time | Not set anywhere in the GIMBAL sitch (no `startTime`; compare SitFlir1.js:17) | SitGimbal.js (absence) |

### GOFAST (SitGoFast.js)

| Quantity | Value | Source location |
|---|---|---|
| Jet TAS | 369 kt (slider 320 to 410) | SitGoFast.js:240 |
| Jet TAS used in turn-rate formula | `par.TAS` = 351 kt (CNodeWatch on `par`), NOT the 369 kt that moves the jet | SitGoFast.js:263-269; par.js:63 |
| Jet initial heading | 262 deg ("was 314") | SitGoFast.js:86, 313-320 |
| Bank | Recorded: minus `Bank Angle` (column 12, index from 0) of `Go Fast Tilt tracking.csv`, rolling average 50 frames; alternative user constant -11 deg | SitGoFast.js:170, 244-259 |
| Azimuth | Keyframe CSV `Go Fast AZ.csv` expanded to 1031 frames (`Az Gimbal Video`); alternatives `Az Editor` curve, `Linear` (-43 at 383 to -57 at 982). Default = first key in the switch = `Az Editor` (the regression curve), not the CSV | SitGoFast.js:171, 223-237; CNodeSwitch.js:106-112 |
| Elevation | `Go Fast El.csv` expanded, rolling average 50 | SitGoFast.js:172, 241 |
| Range | `Go Fast RNG.csv` (NM) expanded, rolling average 50 | SitGoFast.js:173, 347-353 |
| Default object traverse | First menu key = `Two point from RNG` (`LOSTwoPoint`): object position = jet position + LOS * range(frame) at `aFrame` = 375 and `bFrame` = 1030, then linear in between | SitGoFast.js:67-68, 356-379; CNodeLOSTraverse.js:25-36; CNodeInterpolateTwoFramesTrack.js:19-27 |
| Other traverse options | `Gofast RNG values` (per-frame range), `Constant Speed`, `Constant Altitude`, `Starting Altitude`, `Straight Line`, `Windblown Object` | SitGoFast.js:370-379 |
| Default object size | 3 ft sphere | SitGoFast.js:72, 113 |
| Look FOV | 0.7 deg | SitGoFast.js:96 |
| Clock start | `timeStartMin: 42, timeStartSec: 32` on the ATFLIR overlay ("4232") | SitGoFast.js:499-501 |
| Date | Not set in the sitch (AARO says "January 2015") | SitGoFast.js (absence) |

### FLIR1 (SitFlir1.js)

| Quantity | Value | Source location |
|---|---|---|
| Date and time | 11/14/2004, "approximately between 12:00 PM and 1:00 PM PST (20:00 and 21:00 UTC)", `startTime` 2004-11-14T20:30:00.000Z | SitFlir1.js:15-18 |
| Frames, fps | 2289 frames, 29.97 fps | SitFlir1.js:8-9 |
| Jet position | lat 31.205, lon -117.870, altitude 20,000 ft | SitFlir1.js:257-259 |
| Jet TAS | 333 kt (slider 320 to 360) | SitFlir1.js:185 |
| Initial heading | 227 deg | SitFlir1.js:270 |
| Bank, turn rate | User bank 0 deg only; user turn rate 0 deg/s; i.e. a straight jet path with wind | SitFlir1.js:220-228, 272-282 |
| Wind | Target 100 kt from 0 deg (north), local 70 kt from 0 deg; "lock" ties them together when `lockWind` is on (default off) | SitFlir1.js:266-268 |
| Azimuth | `FLIR1 AZ.csv` keyframes (+4 to -8); editor curve default (first menu key) | SitFlir1.js:193-218 |
| Elevation | Interpolate 5.7 (elStart) to 5.0 (elEnd) deg, sign flag off | SitFlir1.js:186-191 |
| Object | Procedural "tictac" geometry, radius 2.8, totalLength 12 (units not stated in the file), model "F/A-18F" also available | SitFlir1.js:381-406 |
| Default traverse | `Constant Air Speed`; start distance 10 | SitFlir1.js:12, 306-317 |
| Angle of attack for the F/A-18F model | 3.8 deg | SitFlir1.js:408 |
| Terrain | lat 31.605, lon -117.870, zoom 7, 6 tiles | SitFlir1.js:26 |

## Conventions and assumptions (verbatim from code)

- Local frame is EUS (East, Up, South); heading 0 = north; `jetFwd` is rotated about local up by `-radians(turnRate/fps)` per frame, so a negative turn rate turns LEFT (CNodeJetTrack.js:81, 93).
- LOS construction: start from forward `(0,0,-1)`; rotate about X by `el` (negative = looking down); rotate about up by `-az` (so negative az = left of nose); then apply a frame whose Y is local up (gravity) and whose forward is the jet's forward vector (CNodeLOSTrackAzEl.js:26-61). Azimuth is therefore relative to the jet's velocity vector (heading), not the true boresight; crab angle from crosswind is not modelled.
- Bank enters the geometry only through (a) the turn rate (CNodeTurnRateBS) and (b) the pod horizon / derotation calculation (JetUtils.js:21-89). The LOS itself is built in the gravity-aligned frame, i.e. Az/El are treated as world-levelled angles, with roll absorbed by the pod.
- Wind is applied to the jet as a uniform displacement; the target has its own uniform wind (`targetWind`). "Const Air Spd" removes the target wind when measuring speed (CNodeLOSTraverseConstantSpeed.js:147-150).
- GIMBAL azimuth sign: the CSV stores positive azimuth for "left"; Sitrec negates it on load (SitGimbal.js:643-646, 670). A consumer reading the CSV directly must apply the same negation.
- GOFAST bank sign: CSV `Bank Angle` is negated on load (SitGoFast.js:170). The CSV has 1030 data rows (frames 0 to 1029) while the sitch expects 1031 frames; behaviour at frame 1030 depends on the node's clamping (not verified).

## Method

### Jet path (both sitches)

`CNodeJetTrack` integrates the jet one frame at a time on a sphere: advance along forward by `TAS/fps`, add the wind displacement, rotate forward about the local up by the turn rate, re-orthogonalise (CNodeJetTrack.js:58-94).

GIMBAL default turn rate is not the bank formula but `CNodeTurnRateFromClouds` ("Match Clouds"): for each frame it computes how fast a point on the horizon at cloud-top altitude (11,740 ft) would sweep across the LOS if the turn rate were the previous value, subtracts the Az change, and sets the next turn rate so the angular cloud speed matches the keyed `cloudSpeedEditor` curve (CNodeTurnRateFromClouds.js:39-110; comment block lines 7-21). So the GIMBAL jet path is steered by the cloud-speed target, not by the recorded bank (bank is used only for horizon/derotation). Recorded bank (`From Bank and Speed`) is an alternative (SitGimbal.js:789-813).

### ATFLIR pod, derotation and glare (GIMBAL)

- Pod attitude from Az/El: `EAJP2PR(el, az, jetPitch)` converts the world Az/El plus jet pitch to the pod pitch and total (global) roll; pod roll = total roll - jet roll (JetHorizon.js:63-67; JetUtils.js:143-161).
- Reference frame: pod chain is jet frame (roll about Z, pitch about X) then EOSU roll (about Z) then ball pitch (about X) (JetHorizon.js:25-42, 31-34).
- Horizon in the pod image: `getHumanHorizonFromPitchRollAzEl` rotates the Az/El unit vector into the jet frame and returns the angle between the camera's horizon vector and the real horizon (JetUtils.js:21-89). This is the "human horizon" series. Test value: frame 435 gives -28.43948837191162 (gimbal.test.js:12-22; inputs at that frame printed by the same test). The notebook run printed human horizon -16.623859 at frame 0 and -29.591246 at frame 1030 (OBSERVED, `gimbal_object_data.ipynb` cell 17).
- Derotation / glare rotation: with `deroFromGlare` true, the rotation of the target image relative to the horizon is driven by the `glareAngle` series (default `Markus Keyframe`, CSV col 13) plus `par.glareStartAngle`, with a 6 deg ramp over frames 0-697 (JetUtils.js:111-126). `getPodRollFromGlareAngleFrame` runs a binary search on pod roll so the modelled pod horizon equals (needed derotation + human horizon) (JetHorizon.js:48-114).
- `calculateGlareStartAngle()` sets the offset by assuming the pod is not rolling during the first 650 frames, minimising the mean mismatch, then scans +/-5 deg in 0.2 deg steps minimising the maximum angular error over every 5th frame (JetHorizon.js:116-164). The code comment calls the first step "a bit ad-hoc and does not really work" (JetHorizon.js:132).
- Glare sprite: the glare is drawn as a sprite rotated by `-deroNeeded + glareStartAngle` in the pod's-eye view (JetStuff.js:1285-1292). `Sit.showGlare` is true for the Far sitch and false for the Near sitch (SitGimbal.js:394, 489).

### Object path (GIMBAL)

- Far (default): the object starts 32 NM out along the frame-0 LOS and each later position is the point on that frame's LOS at which the object has moved exactly `340 kt / fps` in air-relative terms (binary search on a sphere radius around the last position, pick the far intersection when "moving away") (SitGimbal.js:397-402; CNodeLOSTraverseConstantSpeed.js:21-159). Where no intersection exists, the closest point on the LOS is used and the segment is flagged `bad` (lines 128-145).
- Near: 6 NM start, 320 kt, `Straight Line` along `targetActualHeading` = initialHeading 315 + relativeHeading 10 (SitGimbal.js:503-508, 524; JetStuff.js:706-757, heading comment block and `targetActualHeading`).
- The README and sitch files do NOT print the resulting object altitude, range at the end, or speed profile for either variant.
- What Sitrec states about the far geometry is only that the 30 NM variant is drawn as a yellow constant-ground-speed track (SitGimbal.js:532-553). The Peings paper reports the LOS "flatten at about 30 Nm" in Sitrec and a Sitrec straight-line example at 9 NM (see `docs/prior-work/peings-vonrennenkampff-2023.md`, Section IV.B, pages 16 and 18). The pinned repo does not state which ranges give a level path.

### Object path (GOFAST)

Default `Two point from RNG` (SitGoFast.js:356-379): at each frame the object lies on the LOS at the smoothed on-screen range; the track used is the straight line through the positions at frames 375 and 1030 (CNodeInterpolateTwoFramesTrack.js:19-27). Frame 375 is the first frame with a displayed range after target acquisition (aFrame 375, SitGoFast.js:67; a commented-out highlight in JetStuff.js:539 labels frame 369 "GoFast first frame with RNG"; the overlay clock starts at 42:32, SitGoFast.js:499-501; `uap_nb` uses first_track 338 and first_range 370, gofast_ranging.ipynb cell 14).

## Results

### GOFAST

OBSERVED (0x1beef/uap_nb `gofast_ranging.ipynb` cell 8, Sitrec HEAD circa 11/2024, default traverse): jet at frame 0 = (-8.4e-11, 7620.0, -6.4 ...) m; jet at frame 1030 = (-4265.1, 7618.46, 1256.6) m; target at frame 0 = (-6367.77, 4008.54, 6036.0 ...) m; target at frame 1030 = (-5229.30, 4025.88, 6105.96 ...) m (EUS: x east, y up, z south).

Derived from those printed numbers (this lab): target y 4008.5 m and 4025.9 m = 13,151 ft and 13,208 ft; horizontal travel about 1,140 m in 1030 frames / 29.97 fps = 34.37 s, i.e. about 33.2 m/s = about 64 kt = about 74 mph ground speed, heading roughly east (x increases, z increases slowly south, about 93 deg true). Object altitude about 13,150 to 13,210 ft.

LAB RECOMPUTATION (Python, pinned CSVs, defaults: TAS 369, turn-rate TAS 351, bank from tilt CSV, jet wind 120 kt from 270, heading 262, flat Earth, two-point frames 375 and 1030, rolling-average 50 on El, RNG and bank, linear keyframe expansion):

| Case | Altitude at frame 375 / 1030 | Ground speed | Ground heading | Air speed w.r.t. target wind 65 kt from 274 |
|---|---|---|---|---|
| Sitrec defaults | 13,178 ft / 13,214 ft | 33.8 m/s = 65.7 kt = 75.6 mph | 95 deg | 1.6 kt |
| Bank held at -11 deg (user option) | same | 44.1 m/s = 85.8 kt | 108 deg | 28.0 kt |
| Jet wind set to 0 | same | 28.2 m/s = 54.9 kt | 264 deg | 119.4 kt |

Range at frame 375 is 4.35 NM (rolling-averaged) and at 1030 is 3.30 NM. The default result (ground speed about 66 kt, heading about downwind, air speed about 2 kt) agrees with the OBSERVED notebook output within rounding. Interpretation stated by Sitrec's design: the object is wind-borne at about 13,000 ft (the 120 kt jet wind vs 65 kt target wind difference is what moves the answer). The pinned repo contains no prose conclusion; this is read off the default traverse and the 65 kt target wind (SitGoFast.js:128-133).

Cross-check against AARO (see `aaro-gofast.md`): AARO's two sample instants (OSD 42:39 and 42:52, range 4.0 and 3.4 NM, Az L49 and L57, El -29 and -35) correspond to Sitrec frames about 569 and 950 (LAB RECOMPUTATION from the same CSVs: Az -49.3 and -57.1, El -29.1 and -34.8, range 4.00 and 3.40).

### GIMBAL

- No object altitude, range or speed is stated in the pinned repo for either variant. STATED values are only the inputs (far: 32 NM start, 340 kt constant air speed; near: 6 NM, 320 kt straight line; near-sitch extra track at 30 NM, 320 kt ground speed).
- The only locked output is the pod-horizon test (gimbal.test.js:20). Any "range" for Sitrec GIMBAL is a function of the slider values, not a result.
- Not recomputed in this lab. The reason: the default jet path requires reproducing the `cloudSpeedEditor` regression spline and `CNodeTurnRateFromClouds` iteration, the pod calibration and the unseen CNodeCurveEdit evaluation. Do not quote a Sitrec GIMBAL altitude or end range from this file.

### FLIR1

Sitrec does not conclude anything numeric for FLIR1 in `SitFlir1.js`. It is a visual recreation: straight jet path (bank 0, turn 0) at 333 kt TAS, 20,000 ft, heading 227, winds 100 kt (target) and 70 kt (local) from north, azimuth keyframed from the on-screen reading (+4 to -8), elevation 5.7 to 5.0 deg, with the target moved at constant air speed by default and its start distance 10 (NM) (SitFlir1.js:12, 185-317). The accompanying look-view effects (blur, noise, IR/TV levels) emulate the video look. There is no comparison metric.

## Data files

All CSVs are copied unmodified to `data/reference/sitrec/data/<dir>/` (same subpath as the repo). BOM is present on most. "n" = data rows.

### data/gimbal/

| File | n | Columns (header as in file) | Notes |
|---|---|---|---|
| GimbalData.csv | 1031 | `0 time`, `1 glare_angle`, `2 glare_angle_wrt_horizon`, `3 bank_angle`, `4 azimuth`, `5 gaussian_smoothed_azimuth`, `6 smoothed_glare_angle`, `7 Y bump`, `8 Markus KF Rad`, `Pip Angle`, `Pip`, `d-Pip`, `12 KF Deg`, `13 KF Deg Adj`, `Frame` | time 0 to 34.37 s (step 0.0333667 = 1/29.97). glare_angle -51.52 to 87.79 (frame 0: -46.93, last: 64.93). bank_angle 22.6 to 38.2. azimuth 54 to -7 (integer). gaussian_smoothed_azimuth 53.79 to -6.4. KF Deg and KF Deg Adj identical in this file (-48.72 to 65.46); "Markus" is the contributor who made the keyframe fit. Y bump 207.7 to 216.4 (pixel row of the object). |
| GimbalPIPKeyframes.csv | 932 | `Frame`, `X pixels`, `Y pixels`, `centerx`, `centery`, `offx`, `offy`, `atn2` | Object centre pixel track (X 150 to 328.5, Y 119 to 40.5), offsets from the frame centre (317.5, 242.4), atan2 angle -53.62 to 3.13 deg. centerx/centery only filled in row 0. Used via column 7 expansion and a 10-frame rolling average (SitGimbal.js:129-131). |
| GimbalPipSmoothed.csv | 1031 | (index), `Pip Angle` | Smoothed pip (cue dot) angle -53.46 to 2.99 deg. Not loaded by the sitch file. |
| GimbalPosKeyframes.csv | 74 | `Frame`, `X pixels`, `Y pixels`, `Z pixels` | Keyframed object position in video pixels (X 314.8 to 333.5, Y 234.8 to 244, Z 0), frames 0 to 1014. Not loaded by SitGimbal.js. |
| GimbalRotKeyframes.csv | 31 | `Frame`, `degrees` | Mick West's keyframed glare/object rotation, 52.28 at frame 0 flat to frame 698, then to -65.49 at frame 1001. Loaded as `GimbalCSV2` and offered as glare option `MickKeyframe` (SitGimbal.js:126-127, 733). |

### data/gofast/

| File | n | Columns | Notes |
|---|---|---|---|
| Go Fast AZ.csv | 24 | `Frame`, `Az` | Keyframes of the displayed azimuth, -35 at frame 0 to -58 at frame 983 (negative = left), one step per displayed degree change. |
| Go Fast El.csv | 15 | `Frame`, `El` | Displayed elevation, -22 at frame 0 to -36 at frame 1030. |
| Go Fast RNG.csv | 13 | `Frame`, `RNG` | Displayed range in NM: 5.0 at frame 0 (value carried back from the first reading; first displayed range is near frame 369 to 375), 4.4 at 350, 4.0 at 569, 3.4 at 950, 3.3 at 1022. |
| Go Fast Tilt tracking.csv | 1030 | `Frame`,`X pixels`,`Y pixels`,(blank),(blank),`Frame`,`X pixels`,`Y pixels`,(blank),`offx`,`offy`,`len`,`Bank Angle`,(blank),`Cue Angle` | Two tracked points per frame (the bank-indicator line ends, in video pixels), their offset vector and its length; `Bank Angle` -2.36 to 20.17 deg (frame 0: -1.53, last: 20.17); column 13 (unnamed) is small; `Cue Angle` 35.9 to 66.9 deg. Frames 0 to 1029. |

### data/flir1/

| File | n | Columns | Notes |
|---|---|---|---|
| FLIR1 AZ.csv | 16 | `Frame`, `Az` | Displayed azimuth +4 (frame 0) to -8 (frame 2187); one trailing comma on the 1149 row. |
| FLIR1 EL.csv | 2 | `Frame`, `El` | 6 at frame 0, 5 at frame 681. (SitFlir1.js:186-190 instead uses 5.7 to 5.0 sliders; the CSV is not loaded there.) |
| FLIR1 Glare Angle.csv | 5 | `Frame`, `Glare` | 0 to frame 1473, then 135 at 1500/1501, 245 at 1673 (pod/glare rotation keyframes). Not loaded by SitFlir1.js. |
| Flir1 FOV Data.csv | 13 | `Frame`, `Mode`, `FOV`, `Zoom` | FOV mode NAR/MFOV/WFOV and zoom 1 or 2 by frame; `Mode` empty. Loaded as `DataFile` (SitFlir1.js:29, 344-346). |
| Flir1 Mode Data.csv | 5 | `Frame`, `Mode` | Sensor mode: IRW at 0, TV at 536, IRW at 1236. Loaded only in commented code (SitFlir1.js:345). |

## Caveats stated by the author

- README.md:3-7: v1 is end of life; documentation is for Sitrec1 and "will be increasingly out of date for Sitrec2".
- README.md:15: goal is real-time interactive analysis; interactivity and ability to explore parameters, not a fixed answer.
- Code comment on the horizon calibration: "a bit ad-hoc and does not really work" (JetHorizon.js:132).
- Code comment on straight-line traversal: "currently very simplistic and does not work with noisy data" (JetStuff.js:754).
- Code comment on wind precision: "CNodeHeading.getValueFrame is limited in accuracy in larger sitches" (printed in the notebook log).

## Open points (ambiguous or unstated)

1. **GIMBAL TAS.** Sitrec uses 351 kt (SitGimbal.js:699; comment "351 from CAS of 241"). Peings and von Rennenkampff use 363 to 369 kt for IAS 238 to 242 at 25,000 ft and -25 C (their page 6). The temperature assumption is not stated in Sitrec. This changes jet path length by about 4 to 5 percent.
2. **Turn-rate speed mismatch.** In both sitches the bank-based turn rate reads `par.TAS` = 351 (par.js:63), while the jet moves at `jetTAS` (369 in GOFAST). Likely unintended; the effect is about 5 percent on turn rate in GOFAST. In GIMBAL both default to 351.
3. **GIMBAL default turn rate** is a cloud-speed-matching solve with hand-keyed points, not recorded bank. Whether published Sitrec GIMBAL conclusions used this setting is not stated in the repo.
4. **GOFAST azimuth default** is `Az Editor` (a regression curve), not the CSV, because the switch has no `default` and picks the first key (SitGoFast.js:223-237; CNodeSwitch.js:22, 106-112). The editor points (SitGoFast.js:213) were not compared to the CSV here. The lab recomputation used the CSV.
5. **Range units.** `startDistance` and `range` are in the Sitrec "big" unit; the Nautical system is selected in the notebook logs. The pinned files do not set units explicitly in the sitch; verify before reuse.
6. **Air temperature, ISA vs measured, and any geopotential vs geometric altitude** are not modelled in the pinned code.
7. **No date/time for GIMBAL or GOFAST** is encoded; wind values (270/120 kt local, 274/65 kt target) are fixed numbers with no cited source in the code. The GOFAST target wind (65 kt from 274) is of similar order to AARO's 60 kt at 13,000 ft from 265 (see `aaro-gofast.md`) but is not cited to it.
8. **Pod FOV.** Sitrec uses 0.35 deg for GIMBAL (NAR2) and 0.7 deg for GOFAST (NAR); Peings and von Rennenkampff note that documentation conflicts between 0.35 and 0.7 deg (their page 15).
9. **Frame count and frame rate** (1031 at 29.97 fps) vs the 2023 paper (1034 frames at 30 fps, 103 or 104 sampling points) differ; the paper's frame indexing offset is unstated.
10. **GIMBAL fleet and "far/near" naming** are Sitrec UI choices; the 30 NM track exists only in the Near sitch as `FARLOSTraverseConstantSpeed`.
11. **Sitrec2** (the current line) may contain different physics or numbers; not examined.
