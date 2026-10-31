# GOFAST blind transcription notes (independent verifier)

Method: each sheet read from two enlarged crops (azimuth to airspeed at 1.45x; mach to polarity at 1.6x). Every cell read on its own. No cell marked "?"; every value below is a best reading.

Empty range and closure cells are written as the literal word `blank`, following the sample.json instruction ("write 'blank' if the crop is empty"). Range and closure are blank for f4 to f358 and populated from f413.

## Ambiguous cells (frame, field: written value, alternatives)

### airspeed
- f4: 252 (last digit badly smeared; alt 253, 251)
- f192: 253 (alt 252)
- f194: 253 (alt 252)
- f972, f996, f1001, f1005, f1010: 258 (alt 259)

### closure
- f793, f795, f797, f812, f813, f829, f855: 170 (middle digit smeared by interlace; alt 180, 110). Each closure crop cuts off partway through the trailing V/W.

### clock
- f232: 4228 (last digit garbled; alt 4223). No A visible.
- f322: 4231A (third and fourth digits garbled; alt 4230A)
- f484: 4236A (alt 4235A)
- f495: 4236A (alt 4235A)
- f194: 4226 and f206, f207, f219: 4227. No trailing A visible in these crops.

### azimuth
- f495: 48L (alt 49L)
- f504: 48L (alt 49L)
- f620: 49L (alt 43L)

### elevation
- f141: -24 (second digit smeared; alt -23). From f141 to f232, -24 shows the 4 with a tick but reads as 24.

### altitude
- f682: 25010 (fourth digit garbled by interlace; alt 25000)
- f694: 25010 (fourth digit garbled by interlace; alt 25000)

## General observations
- mach reads 0.61 through f795 and 0.62 from f797 on. zoom is 1.0 throughout.
- polarity is BLK except f642 to f782, which read WHT (it renders like "#HT").
- The clock's first digit is a 4 with a tick, as expected. It reads 4220A at f4 and 4253A at f1010.
- Overall, GOFAST is noisier than GIMBAL (horizontal interlace streaks). The hardest fields are the last digit of airspeed, the closure middle digit (170 period) and the garbled clock frames.
