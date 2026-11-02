# PURSUE bounded clips (M5, D-013)

## Status (11/01/2026)

Done: all eight D-013 clips analysed; label tests, range-size-speed curves (`data/derived/pursue/<clip>/curves.csv`), plots (`docs/results/pursue/<clip>.png`), per-clip `summary.json` and `data/derived/pursue/m5_summary.json`. Tests: `tests/test_pursue_m5.py`.
Frame extraction (`extract/frames.py`, case = clip id lowercased, `frames.csv` and `frames_meta.json` under `data/derived/pursue/<clip>/`): finished for all eight clips (11/02/2026: PR044 9,360 frames, PR052 11,893, PR059 8,733, PR078 8,958, PR089 8,955, PR111 1,807, PR113 5,291, PR149 1,545). The gate-clip analysis read the same decoded frames straight from the official files, in the same order, before the PNG sets were complete.
Open: an independent spot check (CP-06); PR113 pixel aspect (two indicators disagree, see below).

## How to read this page

No PURSUE clip gives a range, so every result is a curve: object size and speed as functions of an assumed range, or of the ratio of the object's range to the range at which the clip's scale holds (a ship, or the tracker gate). Where a field of view would turn a scale into a range, the range is given as a function of the assumed field of view. Speeds are the component across the line of sight, relative to the sensor platform (or to the reference, where stated): a lower bound on the full relative speed.

## Results table

| Clip | Scale | What was measured | Verdict on the scale | What it bounds | Confidence |
|---|---|---|---|---|---|
| PR044 | Tracker gate, metre label | 65 label readings; gate 108 to 304 px | Gate width in metres: label follows gate size (log-log slope 1.08, r 0.94 over a 2.8x size change; from frame 6030 to 6090 the gate grows 144 to 304 px while the label goes 23M to 33M); a range reading is ruled out | 0.083 to 0.111 m/px at the gate. Object (white speck, 8 to 11 px at half maximum) 0.8 to 1.1 m across and roughly 1 to 14 m/s (median 4) across the line of sight if at the gate's range; both scale with the range ratio. Gate range 10.2 km if HFOV is 1 deg, 2.0 km if 5 deg | High (reading), low (speed: detection jumps) |
| PR052 | Tracker gate, metre label | 3 gate sizes by eye (glitched video) | Gate width: 29M box 486 px, 33M brackets 600 px, 46M brackets 909 px within 0.8 s and no zoom (0.051 to 0.060 m/px) | Elongated objects on the sea about 105 px long: 5.3 to 6.3 m if at the gate's range (objects on the water, so a ratio near 1 is likely) | Medium |
| PR059 | Tracker gate, metre label | 10 readings where the scene does not zoom | Gate width: label shrinks with the gate, 36M at 153 px to 7M at 30 px (slope 0.99, r 0.996 over 5.2x); range reading ruled out | 0.23 to 0.27 m/px. Object 14 x 18 px at half maximum (saturated, so an upper value): 3.7 to 4.4 m at ratio 1. While locked (43 to 95 s) it is almost fixed to the terrain (0.8 px/s, about 0.2 m/s at ratio 1); before lock it crossed about 64 px/s (about 16 m/s at ratio 1, by eye) | High (reading), medium (size) |
| PR078 | Tracker gate, metre label | 11 readings, fixed 156 px box | Not discriminating by itself (the gate never resizes at fixed zoom, and at a fixed gate size both readings scale with range); width reading applied from PR044, PR059, PR052 | 0.096 to 0.135 m/px; object only a few px, so no size curve | Low to medium |
| PR089 | Tracker gate, metre label | 10 readings, 92 and 156 px boxes minutes apart | As PR078: applied, not tested | 0.128 to 0.207 m/px; object a few px | Low to medium |
| PR111 | Elevation readout and "NNM" label | Elevation and label every 15th frame (121 samples), 6 gate sizes | The label is not gate size (slope 0.15, r 0.26 over a 14x gate change). Within each of four tracking segments, label x sin abs(el) is constant to 1 to 4 percent, inside the whole-degree rounding (3 to 6 percent): the label behaves like slant range to a level plane | Heights below the sensor, in label units: A 8.5, B 71.4, C 17.1, D 71.7. B and D agree, as two looks at the sea would. If "M" is metres and B, D are the sea: platform about 71 m above the sea; object A at about 63 m and C at about 54 m altitude; horizontal closing 1.7 (A) and 3.6 (C) per s against 10 to 18 per s for the sea points. Object curves: object altitude = platform altitude minus 8.5 (A) or 17.1 (C) | Medium |
| PR113 | Burned-in ladder | Ladder spacing and angle on 267 sampled frames; object track on 4 frames | A HUD pitch ladder, not a depression scale: dive lines numbered downward (0 to 16 s), the 0 deg horizon line near 10 s, climb lines numbered upward after, rolling with the aircraft. If conformal, 36.11 px per degree vertically (180.3 to 181.3 px per 5 deg) | The object (frames 407 to 410) moves 142.5 px/frame (H&K: 142), 28 x 26 px. Square pixels: 2.07 rad/s (H&K 2.10); with the fitted pixel aspect 1.31: 1.83 rad/s and HFOV 39 deg instead of 51 (H&K 54). Transverse speed passes Mach 1 at a range of 165 to 207 m; size about 1.2 to 1.4 m per 100 m of range | Medium |
| PR149 | Cargo ship | Object track over 83 frames; ship waterline length | Ship scale valid (seen near broadside; foreshortening would only lower the true m/px) | Ship 926 px (H&K 920). Object 603 px/s in the frame, 622 px/s relative to the ship. Bound: 98 to 130 m/s (frame) or 101 to 134 m/s (relative to the ship) for a 150 to 200 m ship, at a range ratio of 1; 78 to 130 m/s for 120 to 200 m. H&K's 99 to 132 m/s is reproduced. The object stays below the ship's waterline in the image, so an object above the sea is nearer than the ship and the ratio-1 value is a true maximum. Cross-track extent 8 px: at most 1.0 to 1.7 m at ratio 1 | Medium to high |

## Notes per clip

**Gate clips.** Under the width reading, label = range x gate angle, so the label falls as the platform closes even at a fixed gate size (PR044's 12M to 9M over 60 s, PR078's 21M to 18M, PR089's 24M to 20M); that trend alone cannot separate the two readings. The test that does is a change of gate size with the scene scale held: PR044, PR059 and PR052 pass it cleanly. The metres refer to the range the tracker used (the tracked point, or the terrain under the line of sight); an object off that range has its size and speed scaled by the range ratio, which is why the curves are drawn over that ratio. Field of view is unpublished for all five, so the gate's range is a curve over the assumed field of view.

**PR111.** The six gate shapes (small square, large square, H, two tall bars, diamond) change size by 14x while the label varies smoothly, so the label is not a gate size. The elevation readout jumps back from -19 to -14 deg between frames 1485 and 1500 (a cut or a new line of sight). Objects A and C cannot be given a speed: there is no azimuth, so the platform's motion along each line of sight is unknown.

**PR113.** Haqq-Misra and Kopparapu's scale survives the reinterpretation only if the HUD ladder is conformal, which is the usual design but is not documented for this aircraft. The image is not square-pixelled: rung spacing grows with roll as an x-stretched image predicts, and a fit over 89 clean samples gives a stretch of 1.31 +- 0.02 (close to 4:3 shown as 16:9), but only rolls up to 14 deg were measurable; the round reticle, measured by eye, suggests about 1.8. Both say the horizontal field of view is smaller than 54 deg (39 or 28 deg) and the object's angular rate 12 to 21 percent lower. No natural horizon is visible (terrain fills the view near the ladder's horizon line), so a depression-angle reading cannot be tested against one. Background shift across frames 406 to 411 measured under 0.1 px/frame.

**PR149.** Our track is longer than the paper's (83 frames, 2.7 s, against "43 frames spanning 3.2 s"). The ship is a geared cargo vessel with four deck cranes; its class was not identified, so the band is widened to 120 to 200 m alongside the paper's 150 to 200 m.

## Files

Per clip under `data/derived/pursue/<clip>/`: `readings_manual.csv` (by-eye readings), `gate_scan.csv` (gate clips), `object_track.csv`, `ship_track.csv` (PR149), `ladder_auto.csv` and `dark_movers.csv` (PR113), `curves.csv` (columns curve, x_name, x, y_name, y, y_lo, y_hi), `summary.json`. Inputs for the gate clips: `data/derived/pursue/gate_clip_inputs.json`. Code: `extract/pursue_m5.py`, `tools/pursue_m5.py`, `tools/pursue_m5_analyse.py`, `tools/pursue_m5_scan.py`, `tools/pursue_m5_darkscan.py`.

## The other 126 clips: triaged, not pursued (D-013)

Scope was frozen by D-013; the nine other Bounded clips remain candidates for later work. Reasons are the triage reasons from `data/pursue/triage.csv`.

| Clip | Triage tier | Triage reason |
|---|---|---|
| DOW-UAP-PR019 | Not viable | Every text field is blacked out and the only scale is a crosshair with corner brackets of unstated angular size; the view is overhead terrain with no known-size or known-distance reference. |
| DOW-UAP-PR021 | Not viable | Text fields are blacked out, brackets have no stated angular size, and the two contrast areas DVIDS describes are not discernible in the sampled frames over uniform terrain. |
| DOW-UAP-PR022 | Not viable | Heavy blacked-out overlays, an unlabeled green line and error ellipse, and no readable angle, altitude or range; the vehicle-like object on the ground is not the object of interest. |
| DOW-UAP-PR023 | Not viable | Text fields are blacked out and the brackets have no stated angular size; the contrast area DVIDS says leaves the top right at about 6 s is not discernible in the sampled frames. |
| DOW-UAP-PR024 | Not viable | Thin crosshair with no tick marks over featureless sky; the image is a rotated, cropped square inside a black frame, and no angle, range or altitude readout is shown. |
| DOW-UAP-PR026 | Not viable | Text fields are blacked out and the only candidate is a point-like white speck in cloud or haze with no scale or reference. |
| DOW-UAP-PR027 | Not viable | Text fields are blacked out; the coast and harbor scene is on screen only before the object appears, and afterward the object is a point-like speck over featureless water with uncalibrated brackets. |
| DOW-UAP-PR028 | Not viable | Split-screen SWIR and EO view with all text blacked out; the object is a small point-like speck in cloud with uncalibrated brackets and no reference object. |
| DOW-UAP-PR029 | Not viable | Sea-surface view with a square track box and corner brackets that carry no stated size or angle, and a tiny object with no known-size reference. |
| DOW-UAP-PR030 | Bounded | A green tick-marked crosshair is in focus for the whole 10 s and a dark object with a red-orange core crosses the frame at about 6 to 7 s, so an angular scale can be set once the tick spacing is known. |
| DOW-UAP-PR031 | Not viable | Text fields blacked out; the overhead compound view has no readable scale and the multi-colored object that DVIDS says crosses the top edge in the first second is only a faint pink smear. |
| DOW-UAP-PR032 | Not viable | Text fields blacked out; the object that DVIDS places near the top center at 2 to 4 s is not discernible, and brackets have no stated angular size. |
| DOW-UAP-PR033 | Not viable | Text fields blacked out; a saturated red blob appears over a building roof for about 2 s but its nature is unclear and no angular scale or known-size object is established. |
| DOW-UAP-PR034 | Not viable | Text fields blacked out and the track-box size readout appears covered by a black box; over open water the object is not discernible at sample density and no scale is available. |
| DOW-UAP-PR035 | Not viable | Low-resolution file with text blacked out; the object is a white speck in sky and cloud, then lost over land, and the coast has no known size or distance. |
| DOW-UAP-PR036 | Not viable | Every numeric field is blacked out; the green tick ladders have no stated spacing, and a small boat seen at about 4 s leaves before the object (a point-like speck over open sea) is tracked. |
| DOW-UAP-PR037 | Bounded | A small crewed boat sits in the frame for the full clip beside a faint point-like object that crosses the frame at about 6.5 to 8 s, so the boat can serve as an approximate size and range scale for the object. |
| DOW-UAP-PR038 | Not viable | Text blacked out; a star-shaped bright object is tracked against a featureless background with no scale, reference or readable angle. |
| DOW-UAP-PR039 | Not viable | Text blacked out; the faint contrast area DVIDS describes at 3 to 5 s is not discernible in the sampled frames, though an oblique coastal industrial site is in view. |
| DOW-UAP-PR040 | Not viable | Text blacked out; the only object cue is a reporter-added white circle labeled U/I SMALL THERMAL SIGNATURE around a barely visible speck in haze, with no scale. |
| DOW-UAP-PR041 | Not viable | Text blacked out; the object is a point-like white speck over sea haze with uncalibrated brackets. |
| DOW-UAP-PR042 | Not viable | Text blacked out; a point-like speck over haze and water is tracked with no scale or known-size reference. |
| DOW-UAP-PR043 | Not viable | Text blacked out; a faint contrast patch crosses for about 2 s over distant terrain with a hazy horizon, and nothing gives a known size or distance. |
| DOW-UAP-PR045 | Not viable | The display is covered by large black boxes; a long crosshair with a red ring and a pink ellipse carry no readable angle, and the object is a small blob in cloud. |
| DOW-UAP-PR046 | Not viable | A football-shaped object with projections is clearly visible and centered, but the brackets have no stated angular size and nothing else gives a scale. |
| DOW-UAP-PR047 | Not viable | The display is mostly blacked out; three small contrast areas hold a fixed arrangement near center, with a crosshair and red ring of unstated size and no other reference. |
| DOW-UAP-PR048 | Bounded | From about 40 s the view contains an offshore wind-turbine array of regular known-size structures, with small bright specks tracked near them, so turbine height and spacing can set a scale and range bound for the specks. |
| DOW-UAP-PR049 | Not viable | Text blacked out; the scene is nearly black with two small bright points and faint streaks, with uncalibrated brackets and no reference object. |
| DOW-UAP-PR050 | Not viable | Only a crosshair, small corner ticks and unlabelled blue markers remain, and the sea surface gives no scale; the objects are streaks of unknown size. |
| DOW-UAP-PR051 | Not viable | Display fields are blacked out; only the north arrow, crosshair and corner ticks remain, with no scale reference around the single bright object. |
| DOW-UAP-PR053 | Not viable | Display fields are blacked out and no discrete object is discernible in sampled frames; the scene is a nadir view of houses and cars. |
| DOW-UAP-PR054 | Not viable | Zoomed close-ups of a bright object with only an intermittent large crosshair; no angular scale, no scene reference of known size. |
| DOW-UAP-PR055 | Not viable | Dark round contrast against a cloud deck; the original segment has a plain crosshair with all fields covered, and clouds give no scale. |
| DOW-UAP-PR056 | Not viable | Blue crosshair, corner ticks and a north arrow over open sea; no angular scale or known-size reference. |
| DOW-UAP-PR057a | Not viable | Orange crosshair, ticks and north arrow with all fields covered; the contrast area is faint and the scene is clouds then sea with no scale. |
| DOW-UAP-PR057b | Not viable | Same file as PR057a: crosshair, ticks and north arrow only, faint contrast area, no scale reference. |
| DOW-UAP-PR058 | Bounded | Offshore wind turbines appear in the same frames as the object (about 385-470 s, a bright dot beside a tower at 425 s), giving a size reference once the turbine model is known; numeric fields are covered. |
| DOW-UAP-PR060 | Not viable | Mountain or desert terrain from above with fields covered; only a crosshair, ticks and north arrow remain, and any object is a few pixels with no scale. |
| DOW-UAP-PR061 | Not viable | Mountain or desert terrain from above with fields covered; only a crosshair, ticks and north arrow remain, and any object is a few pixels with no scale. |
| DOW-UAP-PR062 | Not viable | Mountain or desert terrain from above with fields covered; only a crosshair, ticks and north arrow remain, and any object is a few pixels with no scale. |
| DOW-UAP-PR063 | Not viable | Mountain or desert terrain from above with fields covered; only a crosshair, ticks and north arrow remain, and any object is a few pixels with no scale. |
| DOW-UAP-PR064 | Not viable | Short urban clip where the contrast event (00:14-00:15) is not discernible and fields are covered; no angular scale. |
| DOW-UAP-PR065 | Not viable | Hazy colour sky with no symbology and no discernible object in sampled frames. |
| DOW-UAP-PR066 | Not viable | Cloud scene with a crosshair and ticks, fields covered; no angular scale. The first contrast area looks like a small aircraft silhouette. |
| DOW-UAP-PR067 | Not viable | A surfaced submarine and wakes are visible, but no UAP is discernible in sampled frames and fields are covered. |
| DOW-UAP-PR068 | Not viable | Square-format display with a large ring crosshair and arcs, every field covered; unstated angular scale and a featureless gray background. |
| DOW-UAP-PR069 | Not viable | Targeting-style reticle with a track box over clouds then sea; text fields covered and the angular value is unstated. |
| DOW-UAP-PR070 | Not viable | Small bright object under a crosshair and track box on a featureless background; no scale or reference. |
| DOW-UAP-PR071 | Not viable | Crosshair and track box on a featureless gray field with all fields covered; no scale. |
| DOW-UAP-PR072 | Not viable | Night phone video of a luminous phenomenon with light beams; no symbology and the horizon is not usable without camera pose. |
| DOW-UAP-PR073 | Not viable | Portrait-format display, heavily blacked out, with a crosshair and box; no scale reference. |
| DOW-UAP-PR074 | Not viable | Cyan crosshair, ticks and north arrow over sea and cloud; fields covered and no scale. |
| DOW-UAP-PR075 | Not viable | Crosshair and ticks with fields covered over clouds and sea; no scale. |
| DOW-UAP-PR076 | Not viable | Orange crosshair and ticks with fields covered; the contrast area (01:52-02:55) is small and the farmland and buildings give no usable scale. |
| DOW-UAP-PR077 | Not viable | Blue crosshair and ticks over a textured gray field with fields covered; two tiny contrast areas and no scale. |
| DOW-UAP-PR079 | Not viable | Cyan crosshair and ticks on a flat gray field with fields covered; two small contrast areas and no scale. |
| DOW-UAP-PR080 | Not viable | Eight brief contrast crossings (about 1 s each per DVIDS) are not resolved in the sampled frames; fields are covered and no scale is tied to the objects. |
| DOW-UAP-PR081 | Not viable | Village scene with no reticle in the sampled frames and the one contrast event (00:58-01:03) not discernible; fields covered. |
| DOW-UAP-PR082 | Not viable | Faint crosshair and ticks over haze and terrain with fields covered; no scale tied to the contrast patch (00:28-00:29). |
| DOW-UAP-PR083 | Not viable | A dark round object is visible against terrain and sky at about 77-111 s, but only a crosshair and north arrow remain with no scale reference. |
| DOW-UAP-PR084 | Not viable | Cloud-covered town seen through a small window; one short contrast crossing (00:25-00:27) is not discernible and only a compass N remains. |
| DOW-UAP-PR085 | Not viable | Cyan crosshair and ticks on a flat gray field with fields covered; a few tiny bright dots and no scale. |
| DOW-UAP-PR086 | Not viable | A bright spot over open sea with a plain crosshair and a small arrow icon in the upper left; fields are covered and the horizon appears only once. |
| DOW-UAP-PR087 | Not viable | Three short contrast events (1:23, 2:53, 4:22) over open sea; an offshore platform is in the clip but not in the frames with the objects. |
| DOW-UAP-PR088 | Not viable | Blue crosshair and ticks over a gray field with fields covered; contrast events are tiny and unscaled. |
| DOW-UAP-PR090 | Not viable | Farmland from above with a small crosshair and ticks, fields covered; a bright blob near the centre is tracked but no angular scale or range is given. |
| DOW-UAP-PR091 | Not viable | Ships and an oil platform appear at times, but the tracked contrast (about 03:08-03:48) appears to be a small vessel with a wake; fields covered and no scale for an unexplained object. |
| DOW-UAP-PR092 | Not viable | Crosshair and ticks over sea ripples with fields covered; the object is tiny and unscaled. |
| DOW-UAP-PR093 | Not viable | Crosshair and ticks over a dark gradient field with fields covered; tiny contrast areas and no scale. |
| DOW-UAP-PR094 | Not viable | Orange crosshair and ticks over sea and sky with fields covered; the object is a faint point and the ship at the start is not near it. |
| DOW-UAP-PR095 | Not viable | Crosshair and ticks over sea with fields covered; two bright streaks at about 45-100 s with no scale reference. |
| DOW-UAP-PR096 | Not viable | Hazy farmland with faint crosshair and ticks, fields covered; two tiny dark specks with no scale. |
| DOW-UAP-PR097 | Not viable | Cyan crosshair and ticks with fields covered; bright specks over a hazy field and no scale. |
| DOW-UAP-PR098 | Not viable | Crosshair and ticks with a large blacked-out panel over sea; a loose group of bright points in 17.6 min, no scale. |
| DOW-UAP-PR099 | Not viable | A harbour with warships is seen at the start, but the objects are small dark spots over open sea at 150-265 s with no scale reference in frame. |
| DOW-UAP-PR100 | Not viable | Steep view of open sea with only reticle brackets and a north marker; every readout is blacked out and there is no known-size object or scale. |
| DOW-UAP-PR101 | Not viable | Sky and cloud view with reticle brackets and a north marker only; readouts are blacked out and cloud shapes give no known size or distance. |
| DOW-UAP-PR102 | Not viable | Brackets and north marker only over sea texture then sky; readouts blacked out, no scale or known-size reference. |
| DOW-UAP-PR103 | Not viable | Auto-track box and reticle brackets over banded cloud; readouts are blacked out and there is no scale or known-size reference. |
| DOW-UAP-PR104 | Not viable | Reticle brackets and a north marker over a flat background; readouts are blacked out and the six-pointed dark shape gives no scale. |
| DOW-UAP-PR105 | Not viable | Cloud-only imagery (including a cloud-top deck seen from above) with brackets and a north marker; readouts blacked out and no scale. |
| DOW-UAP-PR106 | Not viable | Only 5 s long; an uncalibrated tick crosshair with side bars and no angle, range or altitude readout, over a featureless background with a tiny object near the top. |
| DOW-UAP-PR107 | Bounded | A legible elevation readout (about -3 deg stepping to -9 deg, then -11 deg) and a bank-style horizon bracket are visible, but there is no azimuth, altitude or range; with the sea surface this gives a line of sight angle only. |
| DOW-UAP-PR108 | Not viable | Pillar-boxed display with an uncalibrated tick crosshair and side bars; no readout is legible and no discrete object is visible in the sampled frames. |
| DOW-UAP-PR109 | Not viable | Banded cloud scene with an uncalibrated tick crosshair and side bars and no readout; the object is a tiny dot. |
| DOW-UAP-PR110 | Not viable | Same display layout as PR106 with an uncalibrated tick crosshair and side bars, no readout, and a featureless background; the object is only a few pixels until it is inside the tracking box. |
| DOW-UAP-PR112 | Not viable | Thin crosshair and north marker only, all readouts blacked out; the shoreline in the first seconds is unlocated and gives no known size. |
| DOW-UAP-PR114 | Not viable | Cropped display with a crosshair, a tracking box and two unlabelled diagonal bars; the readout strip along the bottom is entirely blacked out and nothing gives a scale. |
| DOW-UAP-PR115 | Not viable | Only a crosshair and north arrow over sea and cloud, with all readouts blacked out and no scale. |
| DOW-UAP-PR116 | Not viable | A dark object in a tracking gate (two vertical bars) over a featureless background; the gate is not a calibrated scale and nothing else gives size or range. |
| DOW-UAP-PR117 | Not viable | Tick-marked reticle is visible but the angular spacing of the ticks is not stated on screen, and no discrete object is discernible against the textured background. |
| DOW-UAP-PR118 | Not viable | Tick-marked reticle with uncalibrated spacing; no discrete object discernible in the sampled frames. Official report D101 describes cold orbs about 4 ft across, but that is a claim, not a measurement. |
| DOW-UAP-PR119 | Not viable | Only 2.8 s long; shows ring and triangle markers near the reticle that look like display symbols rather than isolated targets, and tick spacing is uncalibrated. |
| DOW-UAP-PR120 | Bounded | Tick-marked reticle in view for the whole clip with a small target visible and the sensor zooming, so size-range-speed curves can be drawn if the tick spacing is calibrated; report D101 gives a claimed 4 ft object size. |
| DOW-UAP-PR121 | Bounded | Tick-marked reticle with a pair of dark dots tracked across 34 s and zoom changes, giving a field-of-view scale for range-size-speed curves once tick spacing is calibrated. |
| DOW-UAP-PR122 | Bounded | Tick-marked reticle with dot pairs visible over 26 s of pan and zoom, giving a field-of-view scale for range-size-speed curves once tick spacing is calibrated. |
| DOW-UAP-PR123 | Not viable | Only an unlabeled crosshair; no angle, range or altitude readout, and the horizon and sea texture give no known size or distance. |
| DOW-UAP-PR124 | Not viable | Only an unlabeled crosshair; horizon and sea clutter are visible but no altitude, range or FOV is given, so no scale can be set. |
| DOW-UAP-PR125 | Not viable | Unlabeled crosshair over a featureless background; no readout, scale or scene reference. |
| DOW-UAP-PR126 | Not viable | Low-light hand-held video of point lights with no symbology and no recognizable scene. |
| DOW-UAP-PR127 | Not viable | Low-light hand-held video of point lights with no symbology and no recognizable scene. |
| DOW-UAP-PR133 | Not viable | Readouts are blacked out and the scene is haze followed by rugged terrain with no known-size object or scale. |
| DOW-UAP-PR134 | Bounded | All text readouts are blacked out, so no line of sight, but the sensor looks at a dense town with roads, a canal and buildings of roughly standard size, plus a tracked contrast, allowing rough range-size curves. |
| DOW-UAP-PR135 | Not viable | Readouts are blacked out; the opening shows a lattice tower on a small islet, but the lights appear later against open sea with no scene reference. |
| DOW-UAP-PR136 | Not viable | Text readouts are blacked out and the scene is steep rugged terrain with no known-size object or known distance; the sensor pans and zooms. |
| DOW-UAP-PR140 | Not viable | Readouts and the track area are blacked out; rocky terrain and flat desert have no known-size object or scale. |
| DOW-UAP-PR141 | Not viable | Split IR and EO display with readouts blacked out; terrain and desert give no known size or scale. |
| DOW-UAP-PR142 | Not viable | Text readouts are blacked out and the view is nearly static; the contrast that DVIDS says crosses at 5 to 8 s is not discernible in the sampled frames, and the FOV and ship size are unknown. |
| DOW-UAP-PR143 | Not viable | A dark spiky point at the centre of a textured grey background with brackets and a north marker only; readouts are blacked out. |
| DOW-UAP-PR144 | Not viable | Brackets and north marker over sea and cloud; readouts are blacked out and there is no scale. |
| DOW-UAP-PR148 | Not viable | A small vessel with a wake is visible only in the first 13 s; later the target is a dark dot over sea texture, and the vessel class and zoom are unknown, so no reliable scale exists. |
| DOW-UAP-PR150 | Not viable | Blue brackets and a focus box over cloud and sky with readouts blacked out; no scale. |
| DOW-UAP-PR151 | Not viable | Sea texture and cloud with brackets and a north marker; readouts and the frame edges are blacked out and nothing gives a scale. |
| DOW-UAP-PR152 | Not viable | Cumulus-cloud imagery with a focus box and brackets; readouts blacked out and no scale or known size. |
| DOW-UAP-PR159 | Not viable | Historical film with no symbology and no scene reference; in the sampled frames there is only underexposed blue sky with dust specks. |
| FBI-UAP-PR001 | Not viable | Visible-light handheld phone video of a few tiny lights against a black frame, with no symbology, no background to register against and no known-size or measured distance. |
| FBI-UAP-PR002 | Not viable | Visible-light handheld phone video of two red lights against a black frame, with no symbology and no background reference; the 2,500 ft figure is the witness's estimate. |
| FBI-UAP-PR003 | Not viable | Portrait phone video of a single bright light against a dark treeline and sky; the only distance is the witness's 2,700 ft estimate and the lens, zoom and crop are not stated. |
| FBI-UAP-PR004 | Not viable | Portrait phone video of two red orbs among tree branches with a handheld, shaky camera; distances (25 ft altitude, 1 m diameter) are witness claims and the phone field of view is not stated. |
| FBI-UAP-PR005 | Not viable | Officially described as an artistic digital recreation of a witness account, not sensor footage, so there is no measurement to reconstruct. |
| FBI-UAP-PR006 | Not viable | Officially described as an artistic digital recreation of a witness account, not sensor footage, so there is no measurement to reconstruct. |
| FBI-UAP-PR007 | Not viable | Hand-held thermal view of sky and a cloud edge with no symbology, no scale and no known-size or known-distance reference. |
| LLE-UAP-PR001 | Not viable | Night phone video with point lights in the sky; no symbology, and the lower half is blurred by the release, leaving no recognizable scene reference. |
| LLE-UAP-PR002 | Not viable | 15-minute night phone video of a single point light over a blurred foreground with wires; no symbology or known-size reference. |
| LLE-UAP-PR003 | Not viable | Night phone video of one light moving behind overhead wires; no symbology or scene reference of known size. |
| LLE-UAP-PR004 | Not viable | Night phone video of one or two faint point lights in a dark sky; no symbology or scene reference. |
