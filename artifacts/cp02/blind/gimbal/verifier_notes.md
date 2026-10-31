# GIMBAL blind transcription notes (independent verifier)

Method: each sheet read at full size, plus enlarged (1.6x) crops of the airspeed, clock and azimuth columns. Every cell read on its own. No cell marked "?"; every value below is a best reading.

## Ambiguous cells (frame, field: written value, alternatives)

### airspeed (last digit 8 vs 9 is the main trouble spot)
- f4: 239 (alt 238)
- f12: 239 (alt 238)
- f24: 238 (alt 239)
- f74: 238 (alt 239)
- f79: 238 (alt 239)
- f89: 239 (alt 238)
- f93: 238 (alt 239)
- f107: 239 (alt 238)
- f219: 239 (alt 238)

### azimuth
- f141: 48L (alt 49L)
- f152: 48L (second digit smeared by interlace; alt 43L, 49L)
- f413: 34L (low contrast on bright background; alt 33L)
- f470: 30L (second digit smeared; alt 31L, 33L)
- f632: 20L (second digit smeared; alt 21L, 23L)
- f812: 8L (digit smeared; alt 3L)

### clock
- f322: 5256A (alt 5255A)
- f342: 5256A (alt 5255A, 5258A)
- f619: 5305A (alt 5306A)
- f620: 5306A (alt 5305A)
- f4, f12, f24: written 5245, 5245, 5246 with no trailing A: no A is visible in the crop (it is either absent or cut off).
- f793, f795, f797: 5311; f812, f813: 5312. Same situation, no trailing A visible.

## General observations
- elevation (-2), mach (0.58 / 0.59), zoom (2.0) and polarity are clean throughout.
- mach reads 0.58 for f4 to f484, 0.59 for f495 to f870, then 0.58 again from f878.
- altitude flips between 25010 and 25000. Each cell was legible on its own.
- polarity WHT renders like "#HT" (the W is blobby) up to f358. BLK from f413 on.
- From f413 on (BLK polarity) the azimuth crop has a bright grey background with low-contrast text. That is the hardest field on this case, along with the last airspeed digit.
- The third clock digit sometimes renders as a 4 with a tick (for example 5254A).
