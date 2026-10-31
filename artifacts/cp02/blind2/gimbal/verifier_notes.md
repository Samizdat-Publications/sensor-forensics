# Blind transcription notes: gimbal

Verifier: independent blind reader. Read from sheet_00 to sheet_09 only; no other project files opened.

Method: each cell viewed at 3x source size, plus each cell split into its two interlace row sets (even source rows and odd source rows, line-doubled), with higher-zoom autocontrast crops for doubtful cells. Every cell was read on its own.

Output: verifier.csv, 800 rows (100 frames x 8 fields), no duplicate (frame, field).

Conventions: azimuth as 42L / 7R; elevation as -2; mach without the W prefix; clock written with A only when an A is visible; a slash marks a two-value (interlaced) cell, listed in the order of the two row sets (first set / second set), which is not necessarily old / new.

## Two-value cells (5, all azimuth)
- f602 azimuth: 23L/22L
- f692 azimuth: 17L/16L
- f758 azimuth: 12L/11L
- f956 azimuth: 2R/3R
- f1010 azimuth: 5R/6R

## Ambiguous cells (best reading written)
- f377 azimuth: 35L (could be 36L; second digit 5 or 6)
- f491 azimuth: 29L (could be 23L)
- f509 azimuth: 28L (could be 23L)
- f426 clock: 5259A (could be 5258A)
- f493 mach: 0.58 (could be 0.59; 8 vs 9 on a small low-contrast glyph)

## Other observations
- f3-f52 clock: no A suffix visible (A appears from f93 on); written without A.
- f93-f211 airspeed: small bright mark above third digit (artifact), digits read consistently in both row sets.
- f371: interlace striping across all fields; even rows show black background, odd rows grey background (polarity/background flip mid-frame). Values identical in both row sets (36L, 241, 5257A, 25010, WHT), so single values written.
- Mach 8 vs 9 is the hardest distinction on this sheet in general (low contrast, small glyph).
- f797 and f813 clock: no A suffix shown (5311, 5312); written without A.
- f880 mach: reads 0.58 (closed lower loop), after 0.59 through f863.
- Elevation reads -2 in every sampled frame; zoom reads 2.0 in every frame.
- Polarity WHT from f3 to f371, BLK from f377 on; the display background turns grey at the same point.
- Altitude alternates between 25010 and 25000 (25000 at f209, f211, f377 to f445, f518, f522).
- Mach 0.58 through f493, 0.59 from f506 to f863, 0.58 again from f880 (8 vs 9 checked at high zoom at each change).
- Legibility: altitude, zoom, polarity and clock are clear; azimuth on the grey background (f377 to f1023) is lower contrast; the mach last digit is the hardest glyph.
