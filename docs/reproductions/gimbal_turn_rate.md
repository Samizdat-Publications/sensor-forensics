# GIMBAL jet turn rate from the lab's own cloud measurement (M2.5)

Prepared 10/31/2026. Code: `solve/cloud_motion.py` (forward model and inversion), `solve/turn_rate_gimbal.py` (`python -m solve.turn_rate_gimbal`). Tests: `tests/test_cloud_motion.py`. Per-frame output: `data/derived/gimbal/turn_rate.csv`. All numbers: `data/derived/gimbal/turn_rate_summary.json`. Plot: `gimbal_turn_rate.png` in this folder.

## Answer

**The lab's cloud measurement supports the timing of Sitrec's cloud-matched turn rate (c), not the bank-derived rate (a).** Over frames 45 to 985, with every history smoothed over 3 s:

| History | RMS difference from the lab cloud rate (deg/s) | Frames inside the lab's 95% band | Total heading change (deg) |
|---|---|---|---|
| (d) lab cloud motion (this work) | | | **-64.96** (95%: -65.88 to -64.52) |
| (a) bank, lab horizon bars | 0.106 (max 0.27) | 47% | -67.03 (outside the band) |
| (b) bank, Sitrec's bank column | 0.083 (max 0.20) | 36% | -64.99 (inside) |
| (c) Sitrec "Match Clouds" (hand-keyed curve, as ported) | **0.029** (max 0.17, at Sitrec's start-up transient) | **84%** | -63.65 (0.9 deg outside) |

The lab band is about +/-0.045 deg/s wide (median half-width). The bank-derived rates miss it in both directions: Sitrec's bank turns too slowly by up to 0.1 deg/s around f250 and f800, the lab bank too fast by up to 0.12 deg/s around f400, and both, by far the largest miss, too fast by 0.17 to 0.25 deg/s from the roll-out at f870 to the end. Sitrec's hand-keyed curve tracks the lab's measurement to 0.02 deg/s (a nearly constant offset) everywhere after its first 60 frames.

The total turn tells a slightly different story: the lab clouds agree with Sitrec's bank column (b) and put Sitrec's cloud rate 0.9 deg short and the lab bank 2 deg long. So: **the cloud timing matches (c); the cloud total matches (b)**, and the lab bank (a) fails on both.

## What was measured, and why it is decisive

The pod holds the object, so the line of sight (LOS) has the world bearing heading + az. The cloud deck behind the object moves across the picture along the image horizon at

    h = -(omega + daz/dt) + p        (deg/s, + = clouds move right)

where omega is the jet's turn rate and p the parallax of the deck from the jet's motion relative to the cloud air mass. For GIMBAL, omega is about -2 deg/s and daz/dt about +1.8 deg/s, but h is only 0.16 deg/s at the start and 0.03 deg/s at the end, so the clouds measure their small difference. A turn-rate error of 0.1 deg/s would make the clouds move 4 px/frame faster or slower than measured; the bank rates predict cloud motion that swings between -2 and +13 px/frame, while the measured motion falls smoothly from 6.4 to 1.1 px/frame (panel 3 of the plot). The bank-predicted cloud motion misses the measured one by 4.3 px/frame RMS (lab bank) and 3.4 px/frame (Sitrec bank); Sitrec's curve by 1.2 px/frame.

Inversion: omega = -h - daz/dt + p. The azimuth readout (with the measured background) carries most of the information, so its uncertainty dominates the band. The measured background term adds up to 3.44 deg over the clip (9.8 fields of view of 0.35 deg; Peings and von Rennenkampff counted "about 9"), parallax -0.63 deg, and the azimuth changes 60.88 deg: total -3.44 - 60.88 - 0.63 = -64.95 deg.

## Method and assumptions

1. **Forward model** (`solve/cloud_motion.py`): spherical Earth (effective radius optional for refraction), the deck a sphere at h_c, the jet at 25,000 ft moving with TAS along its heading plus the jet-level wind minus the cloud-level wind. Each frame the tracked texture is the deck point seen slightly below the LOS; it is held fixed while the jet moves to the next frame and its angular offset from the new LOS gives the image motion, rotated by the image horizon angle theta (`sensor_atflir.human_horizon`, jet pitch 3.6 deg) and scaled to pixels. Unit tests: straight flight looking ahead (no sideways motion), pure turn (clouds move at -omega; a compensating azimuth sweep freezes them), parallax against the first-order formula for decks at 8,000, 11,740 and 18,000 ft with and without refraction, and recovery of a varying turn rate from synthetic pixel motion (error under 0.01 deg/s).
2. **Measurement**: `image_track.csv` `bg_dx`, `bg_dy` (whole active picture, centered on the optical axis, so image rotation adds nothing there); the lower-left cloud tile (`cloud_dx`, `cloud_dy`, corrected for the image rotation about the picture center) is the cross-check and agrees to 0.003 deg/s RMS. Outliers beyond 5 robust sigmas from a 31-frame running median are dropped (21 frames), then a 31-frame mean. **The measured motion runs along the predicted image horizon**: its direction matches theta to +0.4 deg on average (rms 3 deg per frame), and the motion across the horizon is 0.001 deg/s RMS. That check cannot separate the bank scale from the jet pitch (both rotate theta by about 1 deg).
3. **Image scale (assumption)**: the active picture of our copies spans columns 104.5 to 530.5 and rows 26.5 to 454.5 (426 x 428 px). The 0.35 deg field (NAR Z2.0) is taken to span that square picture: 1,217 px/deg across and 1,223 px/deg down. The reticle's 4 to 5 percent x stretch is a +/-5 percent sensitivity (it changes the rate by 0.001 deg/s). If 0.35 deg spanned the full 640 px frame instead, the total turn would be -63.8 deg and the rate would move 0.036 deg/s RMS; that reading is not plausible because the picture is plainly 426 px wide. Data check: fitting the image scale jointly with a coordinated turn from Sitrec's bank lagged 24 frames returns 1,191 px/deg, i.e. 0.358 deg over the picture width, within 2 percent of 0.35. With the lab bank the same fit returns an implausible 0.248 deg (and a turn scale of 0.95), another sign that the lab bank's magnitude is too large for its TAS.
4. **Cloud height and distance (not constrained by the data)**: the cloud tops seen just below the object sit at the deck horizon, so h_c is tied to the elevation: a deck horizon 0.03 deg below an LOS at -2.0 deg means h_c = 11,866 ft without refraction or about 7,500 ft with standard refraction (readout interval -2.5 to -1.5 deg: 4,600 to 17,500 ft). The texture is 130 to 245 km away (nominal 186 km at 11,740 ft, 0.04 deg below the deck horizon). Over 8,000 to 18,000 ft the turn rate moves by 0.003 to 0.010 deg/s RMS and the total by under 0.3 deg: too little for the data to calibrate h_c, and too little to matter.
5. **Azimuth**: the lab's interval-constrained spline (`repro_gimbal.interval_azimuth`). The readout **rounds**: "0" is held 19 frames between "-1" (17) and "1" (17); truncation toward zero would hold "0" about twice as long. For the band the azimuth is rebuilt from the half-degree crossing times, each uniform within the 6 frames before it was displayed, with a common display latency of 0 to 6 frames.
6. **Winds and heading (placeholders)**: heading 315 at f0, jet wind 120 kt from 270, cloud wind 17 kt from 240 (Sitrec). They enter only the parallax: no jet wind, no cloud wind, or the literal "to the west" reading each move the rate by under 0.008 deg/s RMS.
7. **Band**: 300 Monte Carlo draws over the azimuth crossings and latency, h_c 8,000 to 18,000 ft with or without refraction, texture 0.01 to 0.12 deg below the deck horizon, scale +/-5 percent, aspect 1.00 to 1.05, cloud wind 0 to 40 kt from any direction, jet wind from 240 to 300, heading 295 to 335, pitch 2 to 6 deg, whole picture or cloud tile. `omega_cloud_lab_lo` and `_hi` are the 2.5 and 97.5 percentiles after the same 3 s smoothing as `omega_cloud_lab`.
8. **Histories compared**: (a) and (b) use g0 tan(bank) / TAS with the same lab TAS (on-screen Mach x ISA speed of sound, 349 to 355 kt), so only the bank differs; (b) is Sitrec's column shifted one frame to lab numbering. (c) is `repro_gimbal.cloud_turn_rate` on Sitrec's Gaussian azimuth (351 kt, 11,740 ft, no wind), shifted to lab numbering. Its first 60 frames are a start-up transient of Sitrec's iteration (the rate starts at 0).

The measured cloud speed itself is 1.28 times Sitrec's hand-keyed curve in the median (equal at the start, 0.093 against 0.073 deg/s at f600, 0.043 against 0.023 at f900). The turn rates still agree because Sitrec's parallax (a deck-horizon point at 227 km with no wind) and Gaussian azimuth offset most of it.

## Why the bank and the clouds disagree

| Candidate | Test | Result |
|---|---|---|
| Bank scale (horizon bars read too large) | Best constant factor on the bank angle | Lab bank x0.975 (RMS 0.106 to 0.085); Sitrec bank x1.00 (no change). The clouds prefer Sitrec's magnitude. |
| TAS (temperature) | ISA + 9.5 K (P&vR's -25 C), 2.7 percent more TAS | Lab bank total -65.73 deg, inside the band; RMS 0.089. A 3 percent bank scale and a 3 percent TAS error are indistinguishable here; the ERA5 temperature decides. |
| Display lag of the horizon bars | Best lag with and without scale | 24 to 27 frames (0.8 to 0.9 s) with the bars lagging: RMS 0.050 (Sitrec bank, 24 frames, scale 1.00) and 0.048 (lab bank, 27 frames, scale 0.97), about the band half-width; lag alone leaves the lab bank at 0.084. But the best lag is not one number: 46 to 54 frames over f150 to 420, 20 to 24 over f450 to 860, 12 to 14 at the final roll-out. A latency common to all symbology cannot produce it (the azimuth would share it), and extra azimuth latency gives the opposite sign. |
| Sideslip (uncoordinated turn) | Not testable with this data alone | After the roll-out the bars hold -31 deg for 100 frames while the clouds say the jet turns 0.2 deg/s slower than g tan(bank) / V (an equivalent bank of about 28 deg). A side force of about 0.07 g (a few degrees of sideslip) would do it; the F/A-18's flight controls normally coordinate turns. Open. |
| Pitch and angle of attack | g tan(bank) / V holds for a level coordinated turn whatever the AoA; the body-frame azimuth convention (readout in the wing plane) was tested | Body-frame azimuth: total -61.3 deg and RMS 0.28 to 0.36 against every history. Rejected; the levelled convention stands. |
| Readout rounding vs truncation | Duration of "0" | Rounding (see Method 5). |

Established: the bank-derived rate is too fast overall for the lab bank (scale or TAS, about 3 percent) and its timing is off by 0.5 to 1.5 s at the roll changes, with a persistent excess after the final roll-out. Not established: whether the timing error is display lag, sideslip, or something in how the bars are generated. Even with the best lag and scale, the bank rate leaves 0.05 deg/s RMS and fails the distant-path test (below).

## Rerun of the key GIMBAL results with the lab cloud rate

The clouds fix the LOS bearing (heading + az), so each run's turn rate is re-derived with that run's own azimuth series. Swapping a turn rate between azimuth series breaks that link (with Sitrec's azimuth and the lab-azimuth rate, the distant path picks up 44 no-solution frames; re-derived, 27).

**P&vR close path (A).** Ground-speed minimum at **f660** (P&vR's inputs, rate re-derived with their 50-frame averaged azimuth) and **f650** (all lab inputs); over 40 Monte Carlo histories f620 to f670 (median f650). Published: about f720. For comparison: Sitrec's bank f830, Sitrec's cloud port f690, the lab bank f400 (a flat floor). With P&vR's inputs the start air speed becomes 398 kt and the start ground speed 284 kt (published about 400 and 300; the bank reproduction gave 373 and 259), air-velocity reversal f870 (about f900 published), end range 6.24 nmi (6.8 published; the reproduction with Sitrec's bank gave 6.64), climb 383 ft.

**Sitrec-style distant path (B), 340 kt constant air speed from 32 nmi.** All lab inputs with the lab cloud rate: **no frame without a solution** (0 in 40 of 40 Monte Carlo histories), **straight within 0.076 nmi** (0.06 to 0.10 over the histories), 32.0 to 32.7 nmi, 258 to 295 kt over the ground, descending 109 ft (19,117 to 19,008 ft). The air heading starts and ends at 239 deg but wanders over 35 deg in between (26 to 42 deg over the histories; 9 deg with Sitrec's cloud port). With Sitrec's inputs and the re-derived rate: 27 no-solution frames, straight within 0.09 nmi. With bank rates: 286 (lab) and 145 (Sitrec) no-solution frames; the lab bank advanced by the best 24-frame lag still has 241.

**Constant-velocity range curve** (M2.6 setup: heading 315, wind 120 kt from 270, placeholders):

| Turn rate | Azimuth | Lowest misfit | Misfit at 8 nmi | Ground speed at 8 nmi (1 sigma) | Ground speed at 30 nmi (1 sigma) |
|---|---|---|---|---|---|
| (a) lab bank | integer readout | grid edge 60 nmi, 0.345 deg | 1.20 deg | 749 kt (470 to 1,029) | 906 kt (831 to 981) |
| (d) lab clouds | integer readout | **32.5 nmi**, 0.315 deg (interval-aware 1 sigma: 27 to 41 nmi) | 0.78 deg | 1,309 kt (1,021 to 1,597) | 1,709 kt (1,518 to 1,899) |
| (c) Sitrec clouds | integer readout | 27 nmi, 0.301 deg | 0.80 deg | 2,856 kt | 128 kt (52 to 297) |
| (a) lab bank | lab spline | grid edge 60 nmi, 0.17 deg floor | 1.26 deg | 1,076 kt | 1,479 kt |
| (d) lab clouds | lab spline | **27 nmi, 0.035 deg** (1 sigma 27 to 28 nmi) | 0.79 deg | 1,695 kt (1,317 to 2,073) | 478 kt (459 to 496), misfit 0.037 deg |

With the lab cloud rate the misfit has a real minimum near 27 to 33 nmi instead of running to the grid edge, and with the smooth azimuth a constant-velocity path there fits the sight lines to 0.035 deg, while no constant-velocity path within 60 nmi fits better than 0.17 deg with the bank rate. A constant-velocity path at 8 nmi misses by 0.78 deg, beyond the +/-0.5 deg readout interval, under every turn rate. **The implied speeds at fixed range are not robust**: near 30 nmi the velocity component along the sight line is barely constrained, so the point value swings between neighboring ranges (161 kt at 27 nmi, 478 at 30, 745 at 32.5 with the spline) and the quoted 1 sigma ranges, from the local curvature, understate it. The 340 kt constant-air-speed path of run B (about 280 kt over the ground) fits the same sight lines exactly. Read the range of the minimum, not the speed.

## Consequences

- G5 (turn rate) is settled in favor of the cloud-matched timing: the lab's independent measurement reproduces Sitrec's hand-keyed curve's turn rate to 0.03 deg/s and its distant-path result (a straight, level, steady 340 kt path near 32 nmi on every frame). It does not adopt Sitrec's curve: the lab's measured cloud speed is 28 percent faster in the median, and the agreement in turn rate comes through different parallax and azimuth choices.
- The P&vR close path keeps its shape with the lab cloud rate, but its ground-speed minimum moves to f650 to f660, 60 to 70 frames before the published f720 and the first glare step at about f728.
- The bank-scale question (FINDINGS-LOG) is narrowed: in tan(bank) / TAS, the clouds agree with Sitrec's bank at ISA TAS, or with the lab bank at about ISA + 9.5 K. The ERA5 temperature (solve/weather.py) decides which.
- Placeholders still in force: heading 315, winds. They move the cloud rate by under 0.01 deg/s but do move the range curves and paths.
