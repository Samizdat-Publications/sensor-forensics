# FLIR1 ("Tic Tac"): data audit (M0)

Audited 10/30/2026 from two copies.

## The copies

| Item | NAVAIR 2020 copy (canonical) | 2007 copy (`f4.mpg`) |
|---|---|---|
| File | `data/videos/FLIR1_navy2020.mp4` | `data/videos/FLIR1_2007_f4.mpg` |
| Provenance | Wayback copy of `navair.navy.mil/foia/.../1 - FLIR.mp4` | Wayback copy of `vision-unlimited.de/extern/f4.mpg` (captured 02/09/2007); not an official release |
| Codec, size | H.264, 352 x 264 | MPEG-1, 352 x 240 |
| Frame rate | 30/1 | 60000/1001 container rate |
| Decoded frames | 2288 (3 exact duplicates) | 2289 (2 exact duplicates) |
| Duration | 76.3 s | 76.5 s |

Side-by-side crops of the same moment (f300) in both copies: `artifacts/cp01/flir1_copies_crops_f300.png`. The two are about equally legible. The 2007 copy is squeezed vertically (240 lines) and no sharper, so the official copy is canonical; the 2007 copy is kept as a cross-check for any digit that is unreadable in the official one. Frame alignment between the copies is done in M1.

Evidence images: `artifacts/cp01/flir1_fields.png` (every text field from 8 frames, f0 to f2287, 3x) and `artifacts/cp01/flir1_horizon_object.png` (horizon bars and target at 7 frames). Layout: `extract/layouts/flir1.yaml`. Glyphs are only 5 to 6 px tall, so per-frame reading needs temporal smoothing and hand-checked templates.

## Readable on screen, frame by frame

| Quantity | Screen text | Resolution | Range over the clip | Confidence |
|---|---|---|---|---|
| Pod azimuth | `3° R` | 1 deg | 4 R, through 0, to about 8 L | Medium (small glyphs) |
| Pod elevation | `6°` | 1 deg | +6 to +5 (looking slightly up) | Medium |
| Zoom | `1.0` / `2.0` on the zoom ladder | | switches between 1.0 and 2.0 | Medium |
| Field of view mode | `NAR` (with a brief MFOV/WFOV per Sitrec) | | | Low at this size |
| Sensor | `IR` / `TV` | | IR, TV for a stretch, IR again | Medium |
| Jet altitude | `19990 B` | 10 ft | about 19,990 to 20,000 | Medium |
| Indicated airspeed | `253` | 1 kt | about 240 to 253 (strip shows 251, 252, 249, 248, 243, 245, 249, 253) | Low to medium |
| Mach | `M 0.5x` | 0.01 | second digit hard to read | Low |
| Clock | `4135` | 1 s | about 41:35 to 42:5x | Low to medium |
| Polarity | `WHT` | | | Low |
| Bank (graphic) | horizon bars | analog | | Medium |
| Object in image | bright target in the track brackets | pixel | | Medium; the glare shape rotates (Sitrec glare-angle table) |

Not on screen: closure rate. (The M0 line "no RNG field anywhere in the clip" was wrong: a `99.9 RNG 99` line appears from frame 973 on; see the M1 section below.)

## Inferred

- Jet true airspeed from IAS or Mach plus temperature.
- Turn rate from bank.
- Field of view from the zoom and mode (0.7 deg at NAR 1x, 0.35 deg at NAR 2x; MFOV 3 deg; WFOV 6 deg, to source at M2).

## Unknown

- **Range**: none on screen, so the object's distance, speed and size are curves over assumed range.
- Jet heading and position; the exact time and place (November 2004, off Southern California per public accounts; to be sourced).
- Radar data from USS Princeton and the other aircraft.
- Which aircraft and pilot recorded the clip (public accounts differ; testimony file in M3).

## Verdict

**Line of sight reconstructable with lower confidence; range not determined.** Both pod angles, altitude, speed and bank are on screen but small, so extraction needs care. With no range and an object held near the center of the frame, the clip constrains direction and angular motion only; distance, speed and size come out as functions of assumed range. Background motion is weak (featureless sky in much of the clip), which removes the parallax check that helps GIMBAL. Expected to be the weakest of the three Navy videos.

## M1 reading (10/31/2026)

Every frame read with `python -m extract.flir1_read` (extract/symbology.py with FLIR1 templates, cells upsampled 4x; method in the module docstrings), then `extract.merge` and `extract.transitions`. Outputs in `data/derived/flir1_navy/`: `symbology.csv`, `symbology_final.csv`, `symbology_summary.json`, `symbology_f4.csv`, `copy_alignment.csv`, `symbology_sitrec_check.json`, `transitions.csv`. Templates and labels: `extract/templates/flir1_navy/`.

**Range line.** A `99.9 RNG 99` line sits right of center at rows 85 to 91 (x 221 to 279), absent in frames 0 to 972 and present, unchanged, in every frame from 973 to 2287 (1315 frames read as 99.9; the two glyphs after RNG match the 9 templates at NCC 0.99). It never shows any other value, so it reads as a placeholder (no laser range), not a measured range; range stays unknown. The only other transient text on the right is `,WA OK` after `HDG,BALT` (frames about 1125 to 1500 and 1875 to 2250, letters only) and the `B` after the altitude, which comes and goes.

**FOV mode.** NAR except frames 2169 to 2220, where a 4-letter word (MFOV or WFOV) shows. The first letter is not resolvable at this size, and the word does not visibly change at Sitrec's MFOV to WFOV keyframe (2206); it is recorded as `xFOV`. Polarity reads WHT throughout.

**Copies.** The 2007 copy maps onto the official one by a pure vertical scale (0.9091) and lags it by 0 to 3 frames (offset -1 from frame 1, -2 from 986, -3 from 1988). Sitrec's AZ, EL, Mode and FOV keyframes follow the 2007 copy's frame numbering: with that mapping, azimuth and elevation agree on 100% of frames.
