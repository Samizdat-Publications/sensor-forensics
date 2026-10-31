# AARO, Case "Go Fast": Case Resolution and Appendix A

- **Title:** All-domain Anomaly Resolution Office (AARO), U.S. Department of Defense, Case: "Go Fast", Case Resolution (pp. 1-4), plus Appendix A: "Estimating UAP Location, Speed, and Heading from 'Go Fast' FLIR Video Data" (pp. 5-26)
- **Authors:** AARO (no individual authors named in the PDF)
- **Date:** Case Resolution dated 02/06/2025 (p. 1); Appendix A dated "February 2025" (p. 5); PDF creation date 02/10/2025 (file metadata). Marked UNCLASSIFIED. The analysis itself was done "In 2024" (p. 5).
- **URLs:** Official: https://www.aaro.mil/Portals/136/PDFs/case_resolution_reports/AARO_GoFast_Case_Resolution_Card_Methodology_Final.pdf (cited by Haqq-Misra and Kopparapu as their ref. [2]; this host returned HTTP 403 "Access Denied" to curl in this task). Copy actually read: https://www.theblackvault.com/documentarchive/wp-content/uploads/2025/02/AARO_GoFast_Case_Resolution_Card_Methodology_Final.pdf (fetched through the web-fetch tool; 26 pages, 2.1 MB). Black Vault announcement page: https://www.theblackvault.com/documentarchive/pentagon-releases-aaro-report-on-go-fast-video-analysis/ (not opened; found via search).
- **Version:** single issue, Final (file name says "Final")
- **License:** U.S. Government work, no license text in the document.
- **Prepared:** 10/30/2026. Page numbers are PDF page numbers (the document's own page numbers are identical). The tables were read from the rendered page images where the text layer was garbled (Table I, p. 7). Figures (plots) were not inspected.

## Inputs

### Source video and data (pp. 4, 6)

| Item | Value | Page |
|---|---|---|
| Video | the public 34-second FLIR video, compressed Windows Media (.wmv), Navy FOIA "3 - GOFAST.wmv" (ref. 4) | pp. 4, 6, 26 |
| Why only the public video | "the original file and its accompanying metadata are no longer available" | p. 4 |
| Metadata | no aircraft georeferenced position or heading in the file | p. 6 |
| Time reference | on-screen clock values, written as "4232 seconds" etc. (these are the OSD mm:ss readings 42:32, 42:39, 42:52 treated as seconds; inference from the use of 4239 and 4252 as t1 and t2 with 13 s between them) | pp. 6-7 |
| Acquisition | "From 4232 seconds until the end of the video, the tracker acquired a target track on the UAP, enabling the range to be reported" | p. 6 |
| Display fields used | sensor azimuth, sensor elevation, range to target, F/A-18 altitude, speed (Mach), relative frame time; bank from the horizon/roll indicator lines. "The sensor pod display shows most of these values as integers" | p. 6 |
| Frame rate | 30 Hz, 0.033 s between frames | p. 13 |
| Date, place | "January 2015", "Eastern coast of Florida"; exact date, time, position and heading unknown (pp. 1, 4). The cover page calls the object height "reported: near ocean's surface" | pp. 1, 4 |

### Table I, quantities at the two analysed instants (p. 7)

| Parameter | t1 (OSD 4239, converted 0 s) | t2 (OSD 4252, converted 13 s) |
|---|---|---|
| Sensor azimuth | 49 deg (left, "L", a negative angle in the coordinate system, p. 10) | 57 deg (left) |
| Sensor elevation | -29 deg | -35 deg |
| Range to target | 4.0 NM = 7,408 m | 3.4 NM = 6,297 m (the text on p. 11 prints 6,279 m) |
| Aircraft altitude | 25,000 ft = 7,620 m | 25,010 ft = 7,623 m |
| Aircraft speed (Mach number shown) | 0.61 M = 188 m/s | 0.62 M = 191 m/s |
| Speed-of-sound assumption | 601 kt at 25,000 ft (M = 1) (NASA Mach calculator, ref. 5) | same |
| Bank angle | about 14 deg, constant over t1 to t2, measured from the yellow lines drawn over the level-flight and roll indicator lines | p. 7 |
| Average altitude / speed used | 7,621 m; about 190 m/s | p. 7 |

### Winds (p. 17; summary p. 2)

| Altitude | Speed | Direction (from) | Source |
|---|---|---|---|
| 25,000 ft (7,620 m), aircraft | 101 kt = 52.0 m/s (p. 1 and p. 2 say 116 mph) | 255 deg (west-southwest) | historical wind database, "within 15-20 minutes of the time reported with the Go Fast event" (ref. "9" in text; the reference list item 8 is https://earth.nullschool.net) |
| 13,000 ft (3,692 m as printed on p. 17; 3,962 m elsewhere), object | 60 kt = 30.9 m/s (69 mph) | 265 deg (west) | same |
| Direction at object altitude used in Table III | jet-altitude direction plus 10 deg | | p. 22 |

"No information on atmospheric conditions was provided with the UAP report or video, only a time and general location" (p. 17).

## Conventions and assumptions

- Coordinate system follows NGA MISB ST 0601.19 (03/02/2023), ref. 3: aircraft longitudinal axis = +x (forward), transverse = +y (right), vertical = +z (pointing down); the jet is placed at the origin at t1 heading +x (pp. 7-8, Figs. 4 and 5).
- Pointing: start with a unit vector along +x scaled by the range; rotate about y by the sensor elevation, then about z by the sensor azimuth (negative for left) (Eqs. 1 to 5, pp. 9-10). Bank "is included in the elevation and angles of the sensor and not treated separately" (p. 9). Altitude of the object = aircraft altitude minus the z component.
- The jet is flown in a level, constant-bank, constant-speed arc: radius of curvature Rc = v^2 / (g tan(B)) (Eq. 6, p. 10), g = 9.81 m/s^2, v = 190 m/s, B = 14 deg, giving Rc = 14,759 m. Distance flown in 13 s = 2,470 m, 2.66 percent of a circle, yaw = -9.6 deg (counter-clockwise, left) (p. 11). Displacement at t2 = [2,461, -207, 0] m (Eqs. 7 and 8, p. 11).
- The aircraft's true heading and position are unknown, so the analysis is relative to the jet's t1 heading and all wind directions relative to the jet heading from 0 to 360 deg in 1 deg steps are explored (pp. 2, 4, 18, 20).
- Wind is added vectorially to the jet's velocity as a constant over the 13 s interval (p. 18); the target is treated as moving in its own air mass (intrinsic speed = ground speed minus wind at object altitude, p. 2 Fig. 1).
- Tailwind = jet heading 0 deg (along +x), left crosswind = 90, headwind = 180, right crosswind = 270, defined at the t1 location in the same frame (p. 18).
- Speed of sound: 601 kt at 25,000 ft (ISA-consistent; inference).
- The MISB document standard does not require the sensor to be an FMV source; AARO says these pod videos were "not intended to support intelligence or other rigorous analysis" (p. 5).

## Method

1. Pick a 13-second window (OSD 42:39 to 42:52) where bank, altitude and airspeed are nearly constant (p. 6).
2. Position of the object at t1 by rotating the LOS (range 7,408 m) by El -29 and Az -49 deg: [4,251, -4,890, 3,591] m (ahead, left, below), so object altitude 4,029 m = 13,219 ft (pp. 9-10).
3. Jet position and yaw at t2 from the constant-bank arc (above), object position at t2 by rotating by El -35, Az -57, then by the jet's yaw -9.6 deg and adding the jet's displacement: [4,510, -4,941, 3,612] m, altitude 4,008 m = 13,150 ft (pp. 11-12).
4. Distance between the two points: 265 m in 13 s, about 20 m/s = 45 mph; heading -11.14 deg from the +x axis, i.e. the same general direction as the jet (-9.6 deg yaw) but about 9 times slower (pp. 12-13).
5. Frame-by-frame version for all frames 4239 to 4252: values for Az, El and range are recorded where the displayed integer changes ("change frames"; at the change frame the true value is taken as the new integer, e.g. 51.0 or 50.5) and a second-order polynomial is fitted to those points (fit equations and R^2 are on the figures, pp. 14-15); the jet path from the arc; object path from each frame's LOS and range (pp. 13-16).
6. Winds: add the jet's wind (52 m/s from 255) to the jet path, recompute the object path; repeat for tailwind, headwind and left/right crosswinds and then for all wind directions at 1 deg steps (pp. 17-20, Figs. 10 to 14).
7. Compute at each wind direction: UAP distance travelled, UAP heading vs wind direction at the object altitude, and intrinsic speed = speed relative to the air mass (pp. 20-22, Table III).
8. Cross-check: AARO also analysed approximately 4233 to 4236 (target acquired, jet "mostly level") and got "similar" results; higher uncertainty from the shorter segment (p. 26).

## Results

### Headline (Case Resolution, pp. 1-3)

| Quantity | Value | Page |
|---|---|---|
| Object altitude (assessed) | 13,000 ft (about 3,962 m); "high confidence ... it required only the sensor pointing angles and range to target. This calculation does not depend on the absolute position of the F/A-18 or wind speed" | pp. 1, 25 |
| Object altitude, computed | 13,219 ft at t1, 13,150 ft at t2; frame-by-frame path rises about 10 m (30 ft) then curves down at the end | pp. 10, 12, 15-16 |
| Object speed (assessed, intrinsic/airspeed) | 5 mph to 92 mph, from 2 m/s to 41.3 m/s | pp. 1, 3 |
| Object speed (true, ground) | about 32 m/s (72 mph) to 72 m/s (161 mph), depending on heading relative to wind | p. 1 |
| Relative-to-jet, no wind | two-point: 265 m, 20.4 m/s (45.6 mph); continuous path: 226 m, 17.4 m/s (38.9 mph); heading -11.14 deg | pp. 13, 17 (Table II) |
| Heading vs wind | deviated as much as 32 deg (32.1 deg per the Fig. 2 caption) from the wind direction; most simulations significantly less; never against the wind | pp. 1, 3 |
| Object size | one metre or less, comparable to a small drone or bird, from pixel analysis by an Intelligence Community partner; AARO itself "could not determine the object's size" | p. 4 |
| Object shape (assessed) | "Spherical or oblate ellipsoid" | p. 1 |
| Conclusion | "high confidence the object did not demonstrate anomalous performance characteristics"; the apparent high speed is "attributable to motion parallax"; AARO "cannot definitively identify the object" | pp. 1, 3, 26 |

### Table III, wind scenarios (p. 22; summary p. 3)

Wind at the jet 52 m/s (101 kt); wind at the object 30.9 m/s.

| Case (wind relative to jet at t1) | UAP distance travelled (m) | Wind heading at object altitude (deg) | UAP heading (deg) | UAP heading minus wind heading (deg) | Intrinsic speed (m/s) |
|---|---|---|---|---|---|
| 0 deg (tailwind) | 928.8 | 10 | -2.3 | -12.3 | 41.25 |
| 90 deg (from the left) | 687 | 100 | 68.4 | -31.6 | 26.50 |
| 180 deg (headwind) | 425.7 | 190 | 185 | -5.0 | 2.00 |
| 270 deg (from the right) | 756.3 | 280 | 289.5 | +9.5 | 27.70 |

The page 3 summary gives the same four cases as: headwind 2.0 m/s (5 mph) faster than the wind, 5 deg off-wind; left crosswind 26.5 m/s (59 mph), 31.5 deg off-wind; tailwind 41.3 m/s (92 mph), 12.3 deg; right crosswind 27.7 m/s (62 mph), 9.5 deg. The table column order above was recovered from the garbled text layer by matching these numbers; verify against the page image before quoting.

The conclusions (p. 25) add: for the headwind the object heads within 5 deg of the wind and less than 2 m/s (4.5 mph, 3.9 kt) faster; at other angles it is as far as 27.0 deg from the wind direction and as much as 40 m/s (89 mph, 78 kt) faster. "These quantitative results should not be used literally, but only to qualitatively evaluate the UAP properties" (p. 25).

## Caveats stated by the authors

- "AARO could not calculate a single speed or heading for the object because the aircraft's calculated flight path depends on its exact heading" (p. 4); hence the 0 to 360 deg sweep.
- Display values (range, Az, El) "are only accurate to a single decimal place" or integers; calculations "include a small margin of error" (pp. 4, 6).
- "All analytic results are relative to the accuracy of the F/A-18's estimated flight path. It is not possible to state the accuracy for certain without knowing the exact path of the UAP" (footnote 7, p. 17).
- Accuracy limited "by the precision and accuracy of the data and assumptions made regarding the flight parameters of the F/A-18 (e.g., the curved flight path)" (p. 24).
- "Calculations of the UAP's exact position and heading were not possible given that the true track data in latitude and longitude of the F/A-18 were not provided nor were the atmospheric conditions" (p. 24).
- "Although a complete set of data to fully solve for the location, speed, and heading of the 'Go Fast' UAP was not available at the time of this writing, AARO has high confidence that the UAP did not exhibit anomalous or even exceptional behavior" (p. 26).
- Video footage from these pod platforms "often contains compression artifacts or lacks the necessary metadata" (p. 5).

## Open points (ambiguous or unstated)

1. **Internal inconsistencies.** (a) Wind units are mixed (m/s, kt, mph) across pp. 1-2 and 17 but consistent (52 m/s = 101 kt = 116 mph). (b) Object altitude: 13,000 ft is 3,962 m (pp. 20, 25) but 3,692 m appears on pp. 17 and 22 (a transposition). (c) Range at t2: 6,297 m in Table I and Eq. 9, 6,279 m in the text on p. 11. (d) The Case Resolution says heading deviation up to 32 deg (p. 1, 32.1 deg Fig. 2 caption p. 3; -31.6 deg in Table III), but the conclusions say "27.0" (p. 25). (e) "Speed assessed 5 mph - 92 mph" (intrinsic) vs "about 32 m/s (72 mph) to 72 m/s (161 mph)" (true) both appear in the same box on p. 1; the 72 and 161 mph pair likely corresponds to ground speed for the tailwind vs headwind cases, but this mapping is not explained.
2. **Time base.** "4232 seconds" is a display clock, not elapsed seconds; which video frame is t1 is not stated. Using the Sitrec CSVs (range 4.0 NM and 3.4 NM, Az -49 and -57, El -29 and -35) the lab finds frames about 569 and 950 (see `sitrec.md`, 10/30/2026 recomputation).
3. **Origin of the wind data.** The text cites a "historical database [ref 9]" but the reference list has only 8 items; the item for it appears to be earth.nullschool.net (item 8). The exact date, time and position used for the wind lookup are not given.
4. **Bank angle** 14 deg measured from the display; Sitrec's recorded bank for the same interval is about 12 to 13 deg left (lab recomputation from `Go Fast Tilt tracking.csv`, frames 569 to 950). The AARO measurement method (the yellow lines in Fig. 3) is described only qualitatively.
5. **Speed of sound.** 601 kt is used at 25,000 ft; temperature is not stated. Peings and von Rennenkampff used -25 C for GIMBAL; an ISA profile gives about 602 kt.
6. **Target size.** The "one metre or less" figure comes from an unnamed Intelligence Community partner; method details not given.
7. **Different search summaries.** A web-search summary (not verified against the PDF) reported a November 2024 Senate Armed Services briefing slide with a single figure of about 45 mph / 39 kt at 13,000 ft, and a date given as 2016 in some AARO slides and in DefenseScoop coverage. The 2015 date in this PDF is "January 2015". Not opened here.
8. **No flight log.** True heading, true position and exact time of the event remain unknown; AARO and any later analysis must treat the jet heading relative to the wind as a free parameter.
9. **Comparison with Sitrec** (default sitch, jet wind 120 kt from 270, target wind 65 kt from 274): object altitude 13,150 to 13,210 ft (AARO 13,150 to 13,219 ft); object ground speed about 33 m/s = 64 to 66 kt, essentially wind-borne (air speed about 2 kt vs the 65 kt target wind). AARO's intrinsic-speed range is 2 to 41 m/s depending on jet heading; Sitrec's default fixes jet heading at 262 deg true and uses a 120 kt jet-level wind rather than AARO's 101 kt. See `sitrec.md` for how those numbers were obtained (the speed is a lab recomputation, not a Sitrec printout).
