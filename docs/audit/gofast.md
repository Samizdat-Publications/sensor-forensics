# GOFAST: data audit (M0)

Audited 10/30/2026 from the NAVAIR 2020 copy (Wayback capture of the NAVAIR FOIA file).

## The copy

| Item | Value |
|---|---|
| File | `data/videos/GOFAST_navy2020.wmv` (gitignored) |
| SHA-256 | see `data/videos/MANIFEST.json` (`c858b22d8370...`) |
| Codec, size | WMV (wmv1), 640 x 480 |
| Frame rate | 30000/1001 (29.97 fps) |
| Decoded frames | 1031, 0 exact duplicates (`data/derived/gofast/frames_meta.json`) |
| Duration | 34.515 s |
| Provenance | Wayback copy of `navair.navy.mil/foia/.../3 - GOFAST.wmv` (NAVAIR itself refuses scripted requests) |

Evidence images: `artifacts/cp01/gofast_fields.png` (every text field cropped from 8 frames evenly spaced from f0 to f1030, 3x) and `artifacts/cp01/gofast_horizon_object.png` (horizon bars, reticle, object and ocean background at 6 frames). Layout used: `extract/layouts/gofast.yaml`.

## Readable on screen, frame by frame

Values below were read by eye from the evidence image. M1 reads every frame.

| Quantity | Screen text | Resolution | First to last (f0 to f1030) | Notes |
|---|---|---|---|---|
| Pod azimuth | `35° L` | 1 deg | 35 L to 58 L | Left of the nose throughout |
| Pod elevation | `-22°` | 1 deg | -22 to -36 | Looking down at the sea |
| Range | `4.3 RNG` | 0.1 nmi | blank until f368, then 4.4 to 3.3 (M1 reading) | Appears with the laser symbology (`LTD/R`) |
| Closure rate | `210 Vc` | 10 kt | blank until f368, then 220 to 150 (M1 reading) | Not among the inputs of Sitrec's GOFAST sitch (`docs/prior-work/sitrec.md`, GOFAST inputs table) or AARO's analysis (`docs/prior-work/aaro-gofast.md`, inputs) |
| Jet altitude | `25000 B` | 10 ft | 25000 to 25010 | `B` likely barometric |
| Indicated airspeed | `252` | 1 kt | 252 to 259 | Under `ADV-W4 OK` |
| Mach | `M 0.61` | 0.01 | 0.61 to 0.62 | |
| Clock | `4220A` | 1 s | 42:20 to 42:54 | Minutes and seconds; 34 s span matches the 34.5 s clip; gives an on-screen timebase |
| Zoom | `Z 1.0` | | 1.0 throughout | NAR field of view, 0.7 deg at 1.0x (cited in DATA, to source at M2) |
| Sensor | `IR` | | IR throughout | |
| Polarity | `BLK` | | BLK, briefly `WHT` near f736 | Image inversion changes apparent brightness and size |
| Bank (graphic) | horizon bars | analog | level at f0 to f400, banked by f1030 | Bank angle measured from the bar angle in M1 |
| Object in image | small target in the reticle | pixel | tracked near center | Position, size and brightness per frame in M1 |
| Background | ocean surface texture | pixel | moving | Parallax check on the line of sight in M1 |

Other symbols seen, not used for geometry: `NAR`, `OPR`, `RTCL`, `TACT`, `L+S`, `SLAVE`, `BST`, `LST 1688 1688` (laser codes), `LTD/R`, `UFC`, `SETUP`, `G1`, `DCLTR`, `ADV-W4 OK`.

## Inferred (computed, labeled inferred)

- True airspeed of the jet, from IAS or Mach plus temperature (weather data).
- Object altitude and horizontal position, from range, elevation and jet altitude (Earth curvature included).
- Object velocity, from the change of position with time, and independently from closure rate (Vc) combined with the jet's velocity along the line of sight.
- Bank angle and turn rate, from the horizon bars.
- Wind at the object's altitude, from reanalysis.

## Unknown

- Jet heading and absolute position (no heading or coordinates on screen).
- What the range source is: the `LTD/R` symbol points to the laser ranger; to be confirmed from ATFLIR documentation.
- The exact date and place (January 2015, Atlantic off the US East Coast per public accounts; to be sourced).
- Radar data and the uncut video.

## Internal consistency check already available

Range falls from 4.4 nmi (about f350) to 3.3 nmi (f1022): 1.1 nmi in about 22.4 s, an average closing speed of about 177 kt. The on-screen closure rate falls from 220 to 150 kt over the same span (average about 180). The two independent readouts agree. M2 uses this as a test.

## Verdict

**Reconstructable to tight bounds.** Range, both pod angles, jet altitude and speed are all on screen frame by frame, with an on-screen clock and a closure rate as cross-checks. The object's altitude and speed can be computed with uncertainty set mainly by the 0.1 nmi range steps, the 1 deg angle steps, and the unknown jet heading (which matters for ground speed but not for altitude). The hypotheses (balloon or object drifting with the wind, bird, fast object) can be scored directly against these numbers.
