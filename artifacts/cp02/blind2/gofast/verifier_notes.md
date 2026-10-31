# Blind transcription notes: gofast

Verifier: independent blind reader. Read from sheet_00 to sheet_09 only; no other project files opened.

Method: each cell viewed at 3x source size, plus each cell split into its two interlace row sets (even source rows and odd source rows, line-doubled), with higher-zoom autocontrast crops for doubtful cells. Every cell was read on its own.

Output: verifier.csv, 1000 rows (100 frames x 10 fields), no duplicate (frame, field).

Conventions: azimuth as 42L; elevation as -26; range as 4.3 and closure as 210 (V dropped); range and closure left as an empty value when the cell shows only background; mach without the W prefix; clock written with A only when an A is visible; a slash marks a two-value (interlaced) cell, listed in the order of the two row sets (first set / second set), which is not necessarily old / new.

## Two-value cells (8)
- f4 airspeed: 252/251
- f964 airspeed: 257/258
- f82 clock: 4222A/4223A
- f772 clock: 4245A/4246A (moderate confidence; one row set's last digit is unclear but leans 5, the other is clearly 6)
- f952 clock: 4251A/4252A
- f634 altitude: 25000/25010
- f676 altitude: 25000/25010
- f772 altitude: 25010/25000

## Ambiguous cells (best reading written)
- f634 closure: 180 (one row set looks closer to 190)

## Other observations
- Range and closure: written as empty when the cell shows only background (no symbology).
- f199 and f203 clock: no A suffix shown (4226, 4227); written without A.
- f219 to f241 clock: no A suffix shown (4227, 4228); written without A.
- Range and closure first appear at f378 (4.4, 220V).
- Polarity changes BLK to WHT between f634 and f639 (cell background also turns grey from f639).
- f740 airspeed reads 255 while f744 and f758 read 254 (each checked at high zoom).
- f763 mach reads 0.62 while f772 and f791 read 0.61; 0.62 again from f805 (checked at high zoom).
- Closure 180: in one row set the 8 renders like a 9; read as 180 from the full cell.
- f1027 airspeed: 259 (9 vs 8 checked at high zoom).
- Range and closure are empty from f4 to f351 (34 frames each).
- Zoom reads 1.0 in every frame. Polarity BLK to f634, WHT f639 to f772, BLK from f791.
- Legibility: generally good; the main difficulties are 8 vs 9 (closure, clock, airspeed last digit) and 5 vs 6 in the clock last digit.
