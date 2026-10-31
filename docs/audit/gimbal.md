# GIMBAL: data audit (M0)

Audited 10/30/2026 from the NAVAIR 2020 copy (Wayback capture of the NAVAIR FOIA file).

## The copy

| Item | Value |
|---|---|
| File | `data/videos/GIMBAL_navy2020.wmv` (gitignored) |
| SHA-256 | see `data/videos/MANIFEST.json` (`78a347be1bd1...`) |
| Codec, size | WMV (wmv1), 640 x 480 |
| Frame rate | 30000/1001 (29.97 fps) |
| Decoded frames | 1031, 0 exact duplicates (`data/derived/gimbal/frames_meta.json`) |
| Provenance | Wayback copy of `navair.navy.mil/foia/.../2 - GIMBAL.wmv` |

Published frame counts disagree (1031, 1033 and 1034 in different analyses); this copy decodes to exactly 1031 with ffmpeg 9.0.2. Any frame-indexed comparison with Sitrec's `GimbalData.csv` or the 2023 paper must first find the offset (M1).

Evidence images: `artifacts/cp01/gimbal_fields.png` (every text field from 8 frames, f0 to f1030, 3x) and `artifacts/cp01/gimbal_horizon_object.png` (horizon bars and the object at 7 frames). Layout: `extract/layouts/gimbal.yaml`.

## Readable on screen, frame by frame

| Quantity | Screen text | Resolution | First to last (f0 to f1030) | Notes |
|---|---|---|---|---|
| Pod azimuth | `54° L` | 1 deg | 54 L, through 0, to 7 R | Whole degrees; reported elsewhere to update every other frame (M1 measures) |
| Pod elevation | `- 2°` | 1 deg | -2 throughout | Whole degrees only: the true value is anywhere from -1.5 to -2.5, a key limit on range |
| Jet altitude | `25010 B` | 10 ft | 25,000 to 25,010 | |
| Indicated airspeed | `238` | 1 kt | 238 to 242 | |
| Mach | `M 0.58` | 0.01 | 0.58 to 0.59 | Independent of the IAS route to true airspeed |
| Clock | `5245` / `5250A` | 1 s | 52:45 to 53:19 | 34 s span matches the clip |
| Zoom | `Z 2.0` | | 2.0 throughout | NAR 2x, field of view 0.35 deg (to source at M2) |
| Sensor | `IR` | | IR throughout | |
| Polarity | `WHT` then `BLK` | | WHT to about f370, then BLK | Brightness and apparent size must be compared within one polarity |
| Bank (graphic) | horizon bars | analog | tilted left-end-high throughout | Left bank; angle measured per frame in M1 |
| Object in image | glare shape in track brackets | pixel | rotates during the clip | Orientation, size, brightness per frame in M1 |
| Background | cloud tops (lower left, from about f400) | pixel | moving | Independent check of the line-of-sight rate (logicbear's method) |

## Inferred

- True airspeed: from Mach (0.58 to 0.59) and from IAS (238 to 242) plus temperature. At 25,000 ft both give about 352 to 360 kt; the 2023 paper uses 363 to 369 kt (see `docs/prior-work/FINDINGS-LOG.md`).
- Turn rate and heading change: from bank angle and true airspeed (coordinated turn assumed).
- World-frame line of sight: from azimuth, elevation, bank and pitch, under an assumed angle convention (M2 tests two).
- Wind: the crew audio reportedly mentions 120 knots; reanalysis (ERA5) checks it.

## Unknown

- **Range**: nothing on screen gives distance. All object speeds and sizes are curves over assumed range.
- Jet heading and absolute position; exact date and place (January 2015, Atlantic off the US East Coast per public accounts; to be sourced).
- Pitch / angle of attack (not shown; default 4 deg plus or minus 2 deg).
- Radar data ("a whole fleet of them" on the audio is testimony, not data), the uncut video.

## Verdict

**Line of sight reconstructable; range is not.** Pod angles, airspeed, Mach, altitude, bank and a clock are all readable, and the left turn gives the geometry some leverage on range (the same line-of-sight history fits different paths at different ranges, and the turn makes some of them implausible). But elevation is shown only in whole degrees and stays at -2, which leaves a wide band of distances open. Results will be curves over range, with cloud motion as the main independent check. Rotation of the glare relative to the bank and pod angles can be tested directly, because both are on screen.
