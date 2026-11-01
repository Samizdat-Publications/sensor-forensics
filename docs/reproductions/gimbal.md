# GIMBAL reproductions (M2.7)

Prepared 10/31/2026. Code: `solve/repro_gimbal.py` (`python -m solve.repro_gimbal`). Numbers: `docs/reproductions/gimbal.json`. Plots: `gimbal_topview.png`, `gimbal_range.png`, `gimbal_speed.png`, `gimbal_altitude.png` in this folder. Golden tests: `tests/test_repro_gimbal.py`.

Two published reconstructions are rebuilt from their own stated inputs, then rerun with this lab's measured inputs, changing one input at a time so every difference is tied to an input or assumption.

- **A.** Peings and von Rennenkampff 2023 (P&vR), "best-guess" close path, 8 to 6.8 nmi, plus their Fig. A7 check of a level path near 30 nmi.
- **B.** A Sitrec-style distant path: 32 nmi start, constant air speed 340 kt.

## Summary

| Run | Verdict against the stated tolerance | Main reason for any miss |
|---|---|---|
| A, close path | Passes 8 of 9 checks. Misses the frame of minimum ground speed: f830 against the published f720 (tolerance 60 frames). | P&vR's cloud-motion correction to the azimuth is not given numerically and is left out. Steering the jet with Sitrec's cloud-matched turn rate instead puts the minimum at f690, inside tolerance. |
| A7, level path at 18,700 ft | Range near 30 nmi and the 300 kt start both pass. The end speed is 532 kt against the published 450 kt, a fail. | Same cause. With the cloud-matched turn rate the speed rises smoothly from 319 to 461 kt, and every check passes. |
| B, Sitrec-style far path with the bank turn rate (as specified) | Fails its own premise. The 340 kt constant-air-speed path has no solution on 145 frames (14 percent), most of them in f875 to f1030. Where it exists, it is level (within 81 ft) and stays near 32 nmi. | The turn rate. With a port of Sitrec's default "Match Clouds" turn rate, only 1 frame has no solution. The path is then straight (within 0.05 nmi), level (19,083 to 19,031 ft), steady (281 to 287 kt over the ground) and ends at 32.8 nmi. |

**Biggest single source of difference: where the jet's turn rate comes from**, either the bank angle (P&vR, Sitrec's alternative) or the cloud motion (Sitrec's default, and in effect P&vR's azimuth correction). The bank-derived and cloud-matched rates agree on the total heading change within 1.3 deg (-64.9 vs -63.7 deg over the clip). They differ by up to 0.6 deg/s at the start and about 0.4 deg/s near the end, and that difference in timing is enough to decide whether a steady distant path exists. For the close path, the next-largest factor is the jet's true airspeed, which moves the end range by up to 0.5 nmi.

## Inputs

### A: P&vR close path (from their stated inputs)

| Input | Value used | Source / note |
|---|---|---|
| TAS | Displayed IAS (238 to 242 kt, lab readout) mapped linearly onto their 363 to 369 kt, per frame | P&vR p. 6: "for each selected frame, the corresponding TAS value from that interval is used". A constant 365 kt (Fig. 3 caption) is a sensitivity run. |
| Bank | Sitrec `GimbalData.csv` column 3 `bank_angle`, sampled every 10 frames | **Stand-in.** P&vR extract their own bank every 10 frames; theirs is not published. |
| Turn rate | ROT = 1091 tan(bank) / TAS (deg/s, kt) | P&vR Eq. 1 |
| Integration | Forward Euler, 10-frame steps at 30 fps, heading starting at 0; beta_k = beta_(k-1) + ROT_(k-1) dt, then x_k = x_(k-1) + TAS dt sin(beta_k) | P&vR Eqs. 2 and 3. Whether the step uses the old or the new heading is not stated. |
| Wind | 120 kt from 35 deg left of the initial heading. The jet ground track adds it; the sight lines are built in the air mass. | P&vR pp. 6 to 8 |
| Azimuth | 50-frame **centered** moving average of Sitrec's raw integer `azimuth` (column 4) | P&vR p. 8. Their cloud-motion correction is not quantified and is **omitted**; they call the uncorrected version "noisier, although qualitatively similar" (p. 15). A trailing average is a sensitivity run. |
| Elevation | -2.00 rising linearly to -1.95 deg | P&vR p. 8 |
| FOV | 0.35 deg (no effect on the path) | P&vR p. 8 |
| Object | Straight line in the air-frame top view, starting 8 nmi along the first sight line, heading -20 deg (15 deg off the upwind direction), intersected with every sight line | P&vR pp. 10 to 13 |
| Altitude | Spherical Earth, exact (flat-Earth value also reported) | Lab standard; flat Earth adds 18 ft to the climb |
| Speed | Savitzky-Golay derivative (order 2, 21 samples = 200 frames) of the along-line position | See "Speed smoothing" below |

### A7: P&vR Fig. A7 level path

The jet track and sight lines are as in A, but every frame. The object sits at 18,700 ft on every sight line. The altitude comes from range x sin(el), on a **flat Earth**: P&vR reconstruct in 2-D, and only a flat Earth puts 18,700 ft near 30 nmi; on a sphere it is 34.7 nmi. The air speed is the derivative of the position, with a 100-frame centered average. Start = mean over f50 to f150; end = mean over f881 to f981, clear of the averaging edges.

### B: Sitrec-style far path

| Input | Value used | Source / note |
|---|---|---|
| Turn rate | "From Bank and Speed": g tan(bank) / V, g = 9.77468, V = 351 kt, bank = minus CSV `bank_angle` | SitGimbal.js alternative. Sitrec's default "Match Clouds" is run separately as an approximate port (below). |
| TAS | 351 kt | SitGimbal.js |
| Heading, jet wind | 315 deg true; 120 kt from 270 | SitGimbal.js |
| Azimuth | Minus CSV `gaussian_smoothed_azimuth` | Sitrec default |
| Elevation | -2.01 + 0.025 f / 1031 | SitGimbal.js |
| Angle convention | Level (world-levelled Az/El relative to the jet's heading); jet pitch does not enter the sight line | Sitrec |
| Object | 32 nmi along the first sight line; constant AIR speed 340 kt through a target wind of 65 kt from 274. Each frame takes the far intersection; a frame with no intersection uses the closest point and is flagged. | Port of CNodeLOSTraverseConstantSpeed |
| Earth | Spherical altitude, no refraction | Sitrec uses WGS84, no refraction |

**"Match Clouds" approximate port** (`cloud_turn_rate`): this is a line-by-line port of `CNodeTurnRateFromClouds.recalculate` (EUS frame, WGS84 radius, cloud tops at 11,740 ft, 351 kt). Its one approximation is the hand-keyed cloud-speed curve: Sitrec evaluates the keyed points with its curve editor, which is not ported. Here the eight points are sorted by frame and joined by a monotone cubic.

### C: lab inputs

| Input | Lab value | Compared with |
|---|---|---|
| TAS | On-screen Mach (0.58 / 0.59) x ISA speed of sound at the displayed altitude, 100-frame average: 349 to 355 kt. With P&vR's -25 C (ISA +9.5 K): 356 to 362 kt. | P&vR 363 to 369; Sitrec 351 |
| Turn formula | g0 = 9.80665 exact (P&vR's 1091 corresponds to g = 9.796; the difference is negligible) | P&vR 1091; Sitrec 9.77468 with a fixed 351 kt |
| Bank | `data/derived/gimbal/image_track.csv` horizon bars. They run about 8.5 percent steeper than Sitrec's (FINDINGS-LOG); tan(bank) is about 3.3 percent larger on average. | Sitrec CSV |
| Azimuth | Each integer readout is the center of a +/-0.5 deg interval, and the display refreshes every 6 frames (phase 3). Data points are the interval centers in value and time, shifted 3 frames for display latency. A smoothing spline is relaxed to the smoothest curve that stays inside every interval at every display update (155 constraints, maximum violation 0.500 deg, RMS 0.05 deg against the centers). It runs on average 0.12 deg right of Sitrec's Gaussian curve (maximum 0.40 deg). | P&vR 50-frame average; Sitrec Gaussian |
| Elevation | -2 (readout); sensitivity -2.5 and -1.5 (the edges of the readout interval) | P&vR -2.00 to -1.95; Sitrec -2.01 to -1.985 |
| Frames | 1031 at 29.97 fps, lab numbering (lab = Sitrec + 1; lab series are shifted by one frame when swapped into a Sitrec-numbered run) | P&vR 30 fps |
| Wind | Westerly reading (P&vR -35 deg relative; Sitrec 270 with heading 315, i.e. -45 deg). Also the literal audio reading, "120 knots to the west" taken as blowing toward the west (from 090; with heading 315 that is +135 deg relative). | |

## Results against the published values

### A: close path (tolerances stated in advance: positions 0.2 nmi, minimum-ground-speed frame 60 frames, speeds 15 percent)

| Quantity | Published (P&vR) | Reproduced | Pass |
|---|---|---|---|
| Jet end, no wind (Fig. 3) | about (-1.65, 2.87) nmi | (-1.63, 2.90), off by 0.04 nmi | yes |
| Jet end, 120 kt wind (Fig. 3) | about (-1.0, 1.9) nmi | (-0.97, 1.96), off by 0.07 nmi | yes |
| Start range | 8.0 nmi | 8.00 (by construction) | yes |
| End range | 6.8 nmi | 6.64 | yes (0.16 off) |
| Air speed at start | about 400 kt | 373 | yes (-7 percent) |
| Ground speed at start | about 300 kt | 259 | yes (-14 percent, near the edge) |
| Air speed under 50 kt | near f900 | Air velocity reverses at f880 (minimum 14 kt) | yes |
| Ground speed minimum | near 0 at about f720 | 32 kt at **f830** | **no** (110 frames late) |
| Ground speed at end | over 120 kt | 462 | yes |
| Altitude change (not a stated tolerance) | about +250 ft (+300 in their Sitrec comparison) | +306 (flat Earth +324) | info |

The minimum ground speed cannot reach zero on this path. The object flies 15 deg off the upwind direction, so the crosswind part of the wind is left over: 120 sin 15 deg = 31 kt. P&vR's "near 0" is that minimum.

### A7: level path at 18,700 ft (stated tolerance: speeds 15 percent; range within 1.5 nmi of 30)

| Quantity | Published | Reproduced | Pass | With cloud-matched turn rate |
|---|---|---|---|---|
| Range | near 30 nmi | 29.7 to 30.5 | yes | 29.7 to 30.5 |
| Air speed, start | about 300 kt | 318 | yes | 319 |
| Air speed, end | about 450 kt | 532 (473 at f700) | **no** | 461, passes |

### B: Sitrec-style far path

Sitrec prints no GIMBAL result, so no published number exists for this path. The criterion was stated before the run from Sitrec's construction and from P&vR's description of it ("the LOS flatten near 30 Nm" so a level path can be drawn, p. 16): the 340 kt constant-air-speed path must exist (no-intersection frames under 5 percent), stay within 30 to 34 nmi, and be level within 500 ft.

| Quantity | Bank turn rate (as specified) | "Match Clouds" port (Sitrec default) |
|---|---|---|
| End range | 32.17 nmi (range 31.98 to 32.49) | 32.84 nmi (32.00 to 32.84) |
| Altitude | 19,083 to 19,141 ft (spread 81 ft) | 19,083 to 19,031 ft (spread 52 ft) |
| No-intersection frames | 145: f1 to f18, f237, f875 to f924, f955 to f1030 | 1 (f1) |
| Air heading (100-frame average) | wanders over 105 deg | 242 to 248 deg (span 9 deg) |
| Ground speed | 195 to 526 kt | 281 to 287 kt |
| Largest deviation from a straight line | 0.21 nmi (frames with a solution) | 0.05 nmi |
| Straight and steady? | No | Yes: a straight, level, constant-speed track heading about 245 deg, moving away |
| Criterion | **fails** (path does not exist on 14 percent of frames) | passes |

## Lab-input results

| Run | Result |
|---|---|
| A, all lab inputs (lab TAS, bank, interval azimuth, el -2, 29.97 fps, wind -35, same 8 nmi start and heading) | End range **5.99 nmi** (published 6.8; out of tolerance). Air speed 428 kt at start; reverses at f810. Ground speed 313 kt at start. The ground speed sits at a 31 to 35 kt floor from about f400 to f600; the minimum lands at f400. Climbs 401 ft. |
| A, all lab, el -2.5 / -1.5 | Positions and speeds unchanged; climb 508 / 295 ft |
| A, all lab, TAS at -25 C (356 to 362 kt) | End range 6.19 nmi |
| A7, all lab | 252 kt at start, 366 at f700, 636 at the end (flat Earth, 29.7 nmi) |
| B, all lab inputs, bank turn rate | 286 no-intersection frames (f362 to f472, f860 to f1030): fails its premise, worse than the Sitrec bank run |
| B, all lab inputs, cloud-matched turn rate (computed from the lab azimuth) | 0 no-intersection frames; straight within 0.04 nmi; air heading 243 to 248 deg; 282 to 286 kt over the ground; 32.0 to 32.84 nmi; descends 130 ft (19,117 to 18,987 ft) |
| B, lab clouds, el -2.5 / -1.5 | Same track; altitude 17,421 to 17,247 / 20,813 to 20,728 ft (about 1,700 ft per half degree) |

## Attribution of differences (one input changed at a time)

### A (from the reproduction: end 6.64 nmi, ground-speed minimum f830, reversal f880, air speed at start 373 kt)

| Change | End range (nmi) | Ground-speed minimum frame | Reversal frame | Air speed at start (kt) | Climb (ft) |
|---|---|---|---|---|---|
| TAS constant 365 | 6.58 | 820 | 870 | 385 | 318 |
| TAS 351 (Sitrec) | 6.15 | 660 | 840 | 316 | 401 |
| TAS lab Mach, ISA (349 to 355) | 6.16 | 790 | 850 | 306 | 399 |
| TAS lab Mach, -25 C | 6.37 | 810 | 860 | 341 | 359 |
| Turn formula with exact g | 6.63 | 830 | 880 | 371 | 309 |
| Turn formula Sitrec (9.77468, fixed 351 kt) | 6.13 | 730 | 850 | 335 | 406 |
| **Turn rate from clouds (Sitrec port)** | 6.33 | **690** | 870 | 384 | 366 |
| Bank from the lab | 6.28 | 790 | 850 | 357 | 375 |
| Azimuth, trailing 50-frame average | 6.58 | 860 | 940 | 66 (edge artifact) | 318 |
| Azimuth, Sitrec Gaussian | 6.72 | 830 | 880 | 385 | 291 |
| Azimuth, lab interval spline | 6.84 | 830 | 880 | 511 | 268 |
| Azimuth + 1 deg linear ramp (a stand-in for a cloud correction) | 6.80 | 830 | 890 | 399 | 274 |
| Elevation -2.0 / -2.5 / -1.5 constant | 6.64 | 830 | 880 | 373 | 271 / 343 / 199 |
| 29.97 fps instead of 30 | 6.63 | 830 | 880 | 372 | 309 |
| Wind from 270 with heading 315 (-45 deg; object heading -30) | 7.43 | 840 | 880 | 513 | 153 |
| Literal "to the west" wind (+135 deg; object heading +150, the same line flown the other way) | 7.43 | 910 | 880 | 513 | 153 |
| Speed smoothing 11 / 31 samples | 6.64 | 850 / 810 | 870 / 880 | 236 / 339 | 306 |

Reading the table:

- **End range** (P&vR's 13 percent size-change constraint rests on it) is very sensitive to the jet's turn. TAS enters the turn rate as 1/TAS, so the change from 365 to 351 kt moves the end by 0.43 nmi. A 3 percent difference in tan(bank) moves it by 0.36 nmi; the object heading or the wind direction moves it by up to 0.8 nmi. The lab's lower TAS and steeper bank each pull the end inward. The lab azimuth pushes it outward. Together they give 5.99 nmi.
- **The frame of minimum ground speed** is set by when the along-line air speed falls through 116 kt. It does not respond to the azimuth smoothing, the elevation or a linear azimuth ramp. It does respond to the turn rate (TAS 351: f660; cloud-matched: f690). P&vR's unquantified cloud correction is the most likely reason the reproduction misses f720.
- **Elevation** changes only the climb, and only through the readout interval: -2.5 to -1.5 deg gives 343 to 199 ft. Their -2.00 to -1.95 drift adds about 35 ft against a constant -2.
- **Wind direction** changes the object heading through P&vR's "15 deg off the wind" rule. With the Sitrec westerly the end range becomes 7.43 nmi and the start air speed 513 kt. The literal reading flips the ground-speed story: the ground speed starts at 629 kt and falls toward the end, the opposite of the SA-display account.

### B (from the bank-rate reproduction: 145 frames with no solution)

| Change | No-solution frames | End range (nmi) | Altitude start / end (ft) | Air heading span (deg) |
|---|---|---|---|---|
| **Turn rate from clouds** | **1** | 32.84 | 19,083 / 19,039 | 9 |
| TAS 365 | 151 | 32.02 | 19,083 / 19,164 | 119 |
| TAS lab Mach | 152 | 32.12 | 19,083 / 19,149 | 104 |
| Bank from the lab | 258 | 31.67 | 19,083 / 19,218 | 96 |
| Azimuth lab spline (bank turn rate) | 141 | 32.25 | 19,083 / 19,130 | 101 |
| Azimuth lab spline with cloud turn rate | 1 | 32.84 | 19,083 / 19,039 | 7 |
| Elevation -2.0 / -2.5 / -1.5 constant | 145 | 32.17 | 19,117 / 17,421 / 20,813 at start | 105 |
| Literal wind (jet from 090, target from 094), bank turn rate | 143 | 31.00 | 19,083 / 19,323 | 116 |
| Literal wind with cloud turn rate | 1 | 31.81 | 19,083 / 19,197 | 10 (ground speed about 400 kt) |

Only the turn-rate source decides whether a steady distant path exists. TAS, azimuth smoothing and wind leave that answer unchanged. The elevation sets the altitude (about 3,400 ft for each 1 deg) and nothing else. The lab bank makes the bank-rate run worse because its turn rate is larger.

### A7

| Change | Speed start / f700 / end (kt) |
|---|---|
| Reproduction | 318 / 473 / 532 |
| Spherical Earth (34.7 to 36.0 nmi) | 368 / 530 / 606 |
| Sitrec geometry (ground frame, speed relative to the 65 kt target wind) | 224 / 324 / 518 |
| Turn rate from clouds | 319 / 437 / 461 (passes) |
| TAS lab | 321 / 425 / 628 |
| Bank lab | 317 / 438 / 604 |
| Azimuth lab spline | 325 / 481 / 502 |
| All lab | 252 / 366 / 636 |

## Speed smoothing (chosen after the first run, said plainly)

The first run used raw sample-to-sample differences. Those were dominated by the 1-degree steps of the integer readout, which survive a 50-frame average, and they swung by up to about 300 kt within 100 frames. P&vR's plotted speeds are smooth, presumably because of their cloud correction. The primary metric was therefore set to a 200-frame Savitzky-Golay derivative, and the 100- and 300-frame variants are reported above. The end range, the reversal frame and the climb do not depend on this choice; the start speeds change by up to 140 kt and the frame of minimum ground speed by 20 frames.

## What remains unexplained

1. **P&vR's cloud-motion azimuth correction.** It is described only as a term that "gradually adjusts" the azimuth to match about 9 scanned fields of view (p. 8). The cloud-matched turn rate reproduces its apparent effect (the minimum frame and the A7 speeds), but that is Sitrec's method, not theirs. Their repository (github.com/ypeings/Gimbal-UAP) was not read. It would settle this.
2. **Their bank series.** Sitrec's bank stands in for P&vR's own extraction every 10 frames. A 3 percent difference in tan(bank) is worth 0.36 nmi of end range.
3. **The ground speed at start**, 259 against "about 300" kt, passes only narrowly. A +1 deg azimuth ramp gives 285 kt and an end range of 6.80 nmi. That is consistent with a correction of that size, but not proof of it.
4. **The cloud-speed curve** in the Match Clouds port is approximate (Sitrec's curve-editor evaluation is not ported). The keyed values are Sitrec's hand fit to another analyst's cloud measurements. The lab has its own background-motion measurement (`image_track.csv`, `bg_dx`), and the M2 line-of-sight refinement should replace the hand-keyed curve with it.
5. **Display convention of the azimuth readout.** The lab spline assumes rounding to the nearest degree and a 3-frame display latency. If the readout truncates, every lab azimuth shifts by up to 0.5 deg. The lab spline already sits 0.12 deg right of Sitrec's curve; a 3-frame latency at the typical 1.8 deg/s rate is worth about 0.18 deg, the same order.
6. **The lab bank scale** (8.5 percent steeper than Sitrec's, open in FINDINGS-LOG; a pixel-aspect cause is suspected) feeds directly into the turn rate. Until it is settled, lab-input turn rates carry about a 3 percent uncertainty.
7. **Temperature.** The lab TAS uses ISA (-34.5 C at 25,000 ft) because the ERA5 temperature is not yet in the lab. P&vR's -25 C adds about 7 kt and moves the lab end range from 5.99 to 6.19 nmi.

## What this says about the disagreement table

- **G4 (TAS)** and **G5 (turn rate)** are the inputs that matter most. G5 also decides the far path. With the bank-derived rate, no steady 32 nmi path exists in the last 150 frames, and the A7 level path needs speeds well above 450 kt. With the cloud-matched rate, a straight, level, constant-speed track at about 32 nmi fits every frame. The bank-derived and cloud-matched rates agree on the total turn but not on its timing. The lab test that decides between them is the measured background motion against each jet track (M2 line-of-sight refinement).
- **G6 (elevation)** changes altitudes only, as expected: about 3,400 ft per degree at 32 nmi and 140 ft per degree for the close path's climb.
- **G7 (azimuth smoothing)** moves the close-path end range by 0.1 to 0.2 nmi and does not change any conclusion.
- **G9 (wind)**: under the literal "to the west" reading, the close path's ground speed falls instead of rising through the clip, which contradicts the account of a reversal on the SA display. With the cloud-matched turn rate the far path stays straight under either reading.
