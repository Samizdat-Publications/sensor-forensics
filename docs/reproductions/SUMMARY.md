# Reproductions of prior analyses (CP-03)

10/31/2026. Tolerances written into _PLAN.md before any run: line-of-sight residual at most 0.1 deg (not applicable to these path reproductions, which construct positions on the sight lines); positions within 0.2 nmi or 3 percent of range, whichever is larger; GOFAST altitude within 300 ft and speed within 5 kt. The extra GIMBAL checks (speeds within 15 percent, minimum-ground-speed frame within 60 frames) were set at M2 when the GIMBAL runs were specified, not before the plan was approved. Details: `gofast.json`, `gimbal.md` / `gimbal.json`, `gimbal_turn_rate.md`. Golden tests: `tests/test_repro_gofast.py`, `tests/test_repro_gimbal.py`, `tests/test_sensor_atflir.py`.

## Results

| Analysis | From its own stated inputs | Result vs published | Verdict |
|---|---|---|---|
| Sitrec pod geometry (GIMBAL frame 435 horizon) | Sitrec's GimbalData.csv | -28.43948837191162 deg, identical to Sitrec's locked test value | Pass (exact) |
| Sitrec GOFAST (default two-point track) | Sitrec's AZ/El/RNG/tilt CSVs and sitch defaults | 13,192 / 13,243 ft and 63 kt toward 90 deg vs 13,151 / 13,208 ft and about 64 kt toward about 93 deg | Pass (41 ft, 1 kt) |
| Peings and von Rennenkampff 2023, GIMBAL close path | Their stated inputs, with Sitrec's bank column standing in for their bank extraction and their unquantified cloud correction omitted | 8.00 to 6.64 nmi (published 8.0 to 6.8); start air speed 373 kt (about 400), ground 259 kt (about 300); air velocity reverses at f880 (about 900); climbs 306 ft (about 250); minimum ground speed at f830 vs f720 | Pass on 7 of 8 checks (the start range is fixed by construction and not counted); the miss is attributed (below) |
| P&vR Fig. A7, level path near 30 nmi at 18,700 ft | Same | Speed 318 to 532 kt vs 300 to 450 kt (flat Earth only puts 18,700 ft near 30 nmi) | Partial; with the cloud turn rate 319 to 461 kt over an end window that stops 50 frames early (speed climbs to about 700 kt in the last 50 frames) |
| Sitrec GIMBAL distant path (340 kt constant air speed from 32 nmi) | Sitrec's documented "From Bank and Speed" alternative | No solution on 145 of 1031 frames | Fails as specified; attributed (below) |
| Same, with Sitrec's default cloud-matched turn rate | Port of Sitrec's cloud-speed logic | Straight within 0.05 nmi, level 19,083 to 19,031 ft, ends 32.8 nmi, 281 to 287 kt ground speed | Pass, conditional on a 0.35 deg field of view (see below) |

## Explanations of the differences

1. **The turn-rate source decides GIMBAL (attributed, not resolved).** The bank-derived coordinated-turn rate and Sitrec's cloud-matched rate agree on the total turn (-64.9 vs -63.7 deg) but differ in timing by up to 0.6 deg/s. The lab measured the cloud motion itself and inverted it for the turn rate (`gimbal_turn_rate.md`). With the consensus field of view of 0.35 deg, its timing matches Sitrec's cloud curve (RMS 0.029 deg/s) rather than the bank rate (0.106 deg/s); note that the azimuth history dominates both cloud-based estimates, so part of that agreement is built in. With the cloud-derived rate the P&vR close path's minimum ground speed moves to f650 to f660 (70 frames from the published f720, just outside the 60-frame check) and its end range becomes 6.24 nmi (published 6.8; outside the 0.2 nmi check), so the cloud rate trades one failed check for another. The 340 kt distant path exists on every frame in all 40 sampled turn histories.
   **Field-of-view condition (independent review, `artifacts/review/CP-03-review.md`):** with a 0.7 deg field of view instead of 0.35 deg, the cloud-derived rate changes, its RMS against Sitrec's curve rises to 0.132 deg/s, and the distant path has no solution on 433 frames. Both prior analyses use 0.35 deg (documented consensus for NAR at 2x; P&vR test 0.7 as a sensitivity), and a joint fit of image scale with Sitrec's bank column gives 1,191 px/deg, within 2 percent of the 0.35 deg assumption; with our own bank the same fit gives an implausible 0.248 deg. So the distant-path result holds at 0.35 deg and fails at 0.7 deg; the field of view is a discriminating unknown.
2. **P&vR's true airspeed (363 to 369 kt) is about 10 kt higher than a standard conversion** of the same readouts (352 to 360 kt from IAS or Mach). With lab inputs the close path ends at 5.99 nmi instead of 6.64: 0.48 nmi from the TAS, 0.36 nmi from the bank, 0.20 nmi from the azimuth smoothing.
3. **P&vR's cloud-motion azimuth correction is not given numerically**, so it could not be reproduced; they report the uncorrected version as "qualitatively similar".
4. **GOFAST with the lab's own readings** gives about 13,230 to 13,290 ft and about 72 kt over the ground under Sitrec's assumed jet heading and wind. The roughly 9 kt difference comes from the lab using true airspeed from the on-screen Mach for the turn rate (Sitrec uses a fixed 351 kt) and the measured bank. The object's speed through the air depends on the wind at 13,000 ft, which the weather step supplies.

## What remains open

- Jet heading and wind for GIMBAL and GOFAST are placeholders until the ERA5 results are in (M2.2).
- The bank magnitude (about 3 percent high, or a warmer-than-standard day) waits for the ERA5 temperature at 25,000 ft.
- FLIR1 has no numeric prior result to reproduce (Sitrec's FLIR1 sitch is a visual recreation only).
