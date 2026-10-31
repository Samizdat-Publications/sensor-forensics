# Limits on Kinematic Inference from the PURSUE Airborne Sensor Videos

- **Title:** Limits on Kinematic Inference from the PURSUE Airborne Sensor Videos
- **Authors:** Jacob Haqq-Misra (Blue Marble Space, Seattle) and Ravi Kopparapu (NASA Goddard Space Flight Center) (p. 1)
- **Date:** v1 submitted 08/12/2026; v2 last revised 08/28/2026 (arXiv abstract page, https://arxiv.org/abs/2608.12445). Category physics.pop-ph.
- **URL:** https://arxiv.org/abs/2608.12445 ; PDF https://arxiv.org/pdf/2608.12445 (v2 read, 14 pages)
- **Version read:** v2 (the PDF header reads "arXiv:2608.12445v2 [physics.pop-ph] 28 Aug 2026")
- **License:** not stated in the PDF.
- **Prepared:** 10/30/2026. Page numbers are PDF page numbers (identical to printed page numbers).
- **Related data file written by this task:** `data/reference/haqq-misra-appendix.csv` (112 rows: clip_id, release, dvids_url, notes), extracted from the paper's Table 2 and its embedded hyperlinks. `release` is the paper's "Tranche" column.

## What the paper is and is not

It is a limits-of-inference argument: it asks which quantities are needed to turn an image-plane rate into a physical speed, then checks that no PURSUE sensor video supplies them. It does NOT reconstruct jet paths, lines of sight or object trajectories, and it gives no per-clip symbology reading (no OCR of on-screen Az, El, range, speed or altitude). The only per-clip analyses are PR113 and PR149. For the other 110 clips the appendix gives only sensor modality, tranche, field-of-view behavior and number of objects (Sec. III, pp. 6-7; Table 2, pp. 11-13).

## Inputs

### The four required quantities (abstract, p. 1; Sec. II, pp. 3-6)

| Quantity | Symbol | What the paper says is available in PURSUE | Source |
|---|---|---|---|
| (1) Range to the object | R | "the PURSUE sensor videos do not include even a single reported range" | p. 3 |
| (2) Velocity of the observing aircraft | v_own | absent from all 112 videos | p. 7 |
| (3) Aspect angle between the object path and observer | theta (derived from range rate: tan theta = omega R / abs(dR/dt)) | absent from all 112 videos | pp. 3, 7 |
| (4) Field angle / field of view of the camera | FOV, or angular scale k (px/rad) | unreported for all but PR113 (graticule) | pp. 6-7 |

Quantities the files do supply: frame rate f and frame size W x H from the container; measurable pixel rate v_px (only for "transit" events) and image extent p (p. 3, p. 7).

### Equations (pp. 3-6)

| Eq. | Content |
|---|---|
| (1) | omega = v_px f / k (line-of-sight angular rate, rad/s; k = angular scale in px/rad) |
| (2) | omega R = abs(v_obj - v_own) sin(theta) |
| (3) | v_obj = v_own + (omega R / sin theta) u_hat |
| (4), (5) | angular size alpha = p / k; physical size s = R tan(alpha) which is about R alpha for tens of pixels |
| (6) | pixel offset x = f_px tan(phi) (rectilinear lens) |
| (7) | f_px = (W/2) / tan(FOV/2) |
| (8) | k = d x / d phi = f_px sec^2(phi) = (W/2) sec^2(phi) / tan(FOV/2), i.e. the scale varies across the frame |
| (9) | small-angle form k = W / FOV at the centre |
| (10) | with a known-size reference object in the same frame: abs(v_obj - v_own) sin(theta) = v_px f (R_obj / R_ref) (l_ref / p_ref), k cancels, only the range ratio R_obj / R_ref remains |
| (11) | PR149 bound: abs(v_obj - v_own) sin(theta) <= (99 to 132 m/s) x (R_obj / R_ref) |

Numerical illustrations of the scale problem: at FOV = 54 deg the small-angle form overstates the central scale by 8 percent, and k varies by 34 percent between the centre of the frame and its corner (p. 6).

## Conventions and assumptions

- A "transit" clip has an object that crosses the field of view against the background; "tracked" has an object held in the field of view (often jittering about the centre); "both" has both types of segment (pp. 6-7). For tracked objects v_px is near 0 by design because the pod slews to null the image motion; "this near-zero rate is a property of the sensor rather than of the object" (p. 7).
- Small-angle approximation is used only where stated (Eq. 5, Eq. 9); the full rectilinear form (Eq. 8) is the reference.
- PR113 assumes the burned-in graticule is a depression-angle scale in degrees and extrapolates the scale linearly across the frame (p. 7). Both the scale and the FOV "are derived from image analysis rather than released data" (p. 8).
- PR149 assumes the ship is a "Handymax"-class carrier of 150 to 200 m length; the projected hull of 920 px is the scale (pp. 9-10).
- Velocities relate to the object relative to the sensor platform, not the ground: "the transverse term omega R is therefore unrecoverable for tracked objects" (p. 7).

## Method

1. For every one of the (then) 112 sensor videos, review the frame constants, whether Az, El, FOV or scale, range and platform velocity are present, and sort by behavior (transit/tracked/both) and number of objects (p. 6).
2. Derive the omega-to-velocity relation (Eqs. 1 to 3) and the angular scale from the lens model (Eqs. 6 to 9).
3. Demonstrate with two clips where something is measurable: PR113 (graticule gives k, so omega) and PR149 (ship gives a size reference, so a relative-speed upper bound) (Secs. IV and V).
4. Conclude that range, platform velocity, aspect angle and FOV are all needed and are absent (Sec. VI, p. 11).

Tooling note: "Analysis tooling was developed with the assistance of Claude Opus 5" (Acknowledgments, p. 14; ref. [7]).

## Results

### Per-release (tranche) video counts, computed from Table 2 (pp. 11-13)

The paper does not print a per-tranche count table; the counts below come from the appendix itself (every row has a tranche number) and reproduce the paper's Table 1 totals exactly (112 = 43 transit + 33 tracked + 36 both; 79 single-object + 33 multiple-object).

| Tranche (release) | Clips | Transit | Tracked | Both | Sensor modality counts |
|---|---|---|---|---|---|
| 1 | 27 | 11 | 10 | 6 | Infrared 26, Electro-optical 1 |
| 2 | 50 | 24 | 9 | 17 | Infrared 26, Infrared and electro-optical 14, ATFLIR (channel unstated) 7, Electro-optical 3 |
| 3 | 0 | none listed | none listed | none listed | none listed (see Open points) |
| 4 | 19 | 6 | 3 | 10 | Infrared 16, Infrared and EO 1, ATFLIR channel unstated 1, EO 1 |
| 5 | 16 | 2 | 11 | 3 | Infrared 13, Infrared and EO 1, EO 2 |
| Total | 112 | 43 | 33 | 36 | Infrared 81, Infrared and EO 16, ATFLIR channel unstated 8, EO 7 |

The paper's text states "five tranches" were released between "late 2025 and mid-2026" (p. 2) and cites "tranches 1-5" (ref. [1]). Only tranches 1, 2, 4 and 5 contain sensor videos in Table 2. The lab's CLAUDE.md counts 134 videos across Releases 01 to 06 as of 10/30/2026 (D-005); the paper covers an earlier, smaller set (112 sensor videos at 08/2026).

### Table 1 (p. 7)

| Field-of-view behavior | Clips | One object | Multiple objects |
|---|---|---|---|
| Transit | 43 | 34 | 9 |
| Tracked | 33 | 26 | 7 |
| Both | 36 | 19 | 17 |
| Total | 112 | 79 | 33 |

(The printed table in the PDF text layer is misaligned; the numbers above match the per-clip appendix recount.)

### DOW-UAP-PR113 (Sec. IV, pp. 7-9; Figs. 3, 4)

| Quantity | Value | Page |
|---|---|---|
| Release / place and year | Tranche 4; "Western United States, 1996" | p. 7; Table 2 p. 13 |
| Sensor, frame | Infrared, 1920 x 1080 px at 30 fps | p. 7 |
| Object | compact dark body, directly visible for 0.1 s across four progressive frames; linear path; "enters near the upper right corner and exits near the lower left corner" (release caption) | p. 7 |
| Image rate | v_px = 142 px/frame = 2.2 frame-widths per second | p. 7 |
| Image extent | 25 px | pp. 8-9 |
| Graticule | burned-in angular graticule labeled "5 to 35" (read "5-35"), 35.4 px per unit; assumed to be depression-angle degrees | p. 7 |
| Angular scale | k = 35.4 px/deg = 2.03 x 10^3 px/rad | p. 7 |
| Implied FOV | about 54 deg horizontal (linear extrapolation) | p. 7 |
| Angular rate of the line of sight | omega about 2.10 rad/s (about 120 deg/s) | p. 8 |
| Constraint | speed relative to the aircraft = omega R / sin(theta); spans orders of magnitude; subsonic for a near-field object, supersonic beyond a few hundred metres for every aspect angle; transverse motion (theta = 90 deg) is a hard lower bound | p. 8; Fig. 4 p. 9 |
| Size ambiguity | the 25 px extent is consistent with a bird at close range or a 37 m craft at 3 km | p. 8 |
| Abstract wording | cannot distinguish "a bird flying at close range and a large craft traveling at Mach 5 a kilometer away" | p. 1 |
| Missing for a physical speed | R, theta, v_own | p. 8 |

### DOW-UAP-PR149 (Sec. V, pp. 9-10; Fig. 5)

| Quantity | Value | Page |
|---|---|---|
| Release / place and year | Tranche 5; "Middle East, 2023" | p. 9; Table 2 p. 13 |
| Sensor, frame | Infrared, 1920 x 1028 at 30 fps | p. 9 |
| Object | compact object crossing from lower right to lower left, "tracked over 43 frames spanning 3.2 s on a path straight to 2.6 px rms"; a carrier ship is visible beneath the object | p. 9 |
| Image rate | v_px = 20.2 px/frame | p. 9 |
| Reference | ship projected hull 920 px; ship class "Handymax", about 150 to 200 m (ref. [6]) | pp. 9-10 |
| Object motion in ship lengths | 0.657 to 0.689 ship-lengths per second; crosses the whole hull in under 1.6 s | p. 10 |
| Upper bound | abs(v_obj - v_own) sin(theta) <= 99 to 132 m/s x (R_obj / R_ref), equal to 0.3 to 0.4 Mach, maximum when object and ship are at the same range | p. 10 (Eq. 11) |
| If the object is above the ship | relative velocity below the limit | p. 10 |
| Size/speed pairs offered as plausible | a 0.08 m body at 12 m/s, or a 0.15 m body at 22.5 m/s | p. 10 |
| Conclusion for the clip | supersonic relative velocities can be excluded; velocity and identity not further constrained | p. 10 |

### Discussion and conclusions (Sec. VI, p. 11)

- "The PURSUE sensor videos can neither demonstrate nor exclude anomalous kinematics."
- GOFAST was resolvable because the released video "included all on-screen sensor information without redactions"; AARO's other cases are resolvable because AARO has classified data. PURSUE videos have most or all of this redacted.
- Useful data that would help: platform velocity (flight logs), sensor FOV and LOS pointing metadata, range records or a correlated radar track.
- The videos may retain value for "the morphology of the reported objects", "the phenomenology of sensor artifacts" and "sharpening the data requests" (p. 11).

### Cross-references to GOFAST (Introduction and Sec. II, pp. 2-3)

- The paper cites AARO's GOFAST analysis (their ref. [2], Feb. 2025) as the resolved precedent: "trigonometric reduction using its on-screen telemetry showed the apparent motion to be dominated by parallax from the sensor aircraft, with the object's implied speed consistent with wind-borne drift" (p. 2).
- It notes that AARO computed omega by "reading the pod's own azimuth and elevation off the on-screen display frame by frame" and that "even in the GOFAST case, the trajectory of the aircraft was unknown, so the analysis could only report a relative velocity" (pp. 3-4).

## Clip-by-clip symbology assessment

None is given. The only clip-level information is the Table 2 appendix (identifier, DVIDS link, sensor modality, tranche, behavior, number of objects). The paper says each video "was individually reviewed, each assessed for the availability of every variable in Eqs. (1)-(3)" (p. 6), but the outcomes are summarized only as "no video contains complete information" and "all videos fall short" (p. 7). It states that the angular scale and FOV are unreported in every file (p. 7), that observer velocity and aspect angle are absent from all 112, and that range is not reported in any (p. 3). It does not list which clips show an Az/El/range readout at all; it says that information "is either redacted or unavailable in all of the PURSUE sensor videos" (p. 3).

Therefore this lab cannot import a per-clip symbology table from this paper; it must extract its own. The appendix is useful as a clip index with DVIDS record links (copied to `data/reference/haqq-misra-appendix.csv`).

## Appendix CSV notes

- 112 rows, one per row of Table 2. Columns: `clip_id` (exactly as printed, including the inconsistent zero-padding such as `DOW-UAP-PR19`, `DOW-UAP-PR024`, `DOW-UAP-PR050` and the suffix in `DOW-UAP-PR057a`; one row is `FBI-UAP-PR007`), `release` (the paper's tranche, 1, 2, 4 or 5), `dvids_url` (hyperlink embedded on the identifier, form https://www.dvidshub.net/video/<id>), `notes` (`sensor=...; behavior=...; number=...`).
- Extracted programmatically from the PDF link annotations and the same-row words; counts reproduce Table 1 exactly (79/33 and 43/33/36).
- The identifier scheme in the paper may not equal the lab's own clip ids (DATA.md); mapping must be done by DVIDS id or title.

## Caveats stated by the authors

- PR113: "Both of these quantities are derived from image analysis rather than released data, and both rest on the stated assumption that the graticule is a depression-angle scale in degrees" (p. 8).
- PR113: "the object's physical velocity remains undetermined" even with k known (p. 8).
- PR149: only an upper limit; the range ratio R_obj/R_ref "remains unknown" (p. 10).
- "A single camera records angles alone, so neither R nor v_own can be recovered from the imagery by any amount of analytical effort" (p. 7).
- Without unredacted videos or corroborating data the clips cannot "fully resolve unidentified cases or conclusively indicate anomalous velocities" (p. 1).

## Open points (ambiguous or unstated)

1. PR149 internal inconsistency: "43 frames spanning 3.2 s" at 30 fps would be 1.43 s; 3.2 s corresponds to 96 frames at 30 fps. Which is correct is not stated. The image rate 20.2 px/frame gives 606 px/s, which over a 920 px hull is 0.66 ship-lengths/s, consistent with the quoted 0.657 to 0.689 range, and "crossing the entire hull in under 1.6 s" is consistent with 1.5 s.
2. PR149 bound arithmetic: 0.657 to 0.689 hull-lengths/s times 150 to 200 m gives 98.6 to 137.8 m/s; the paper prints 99 to 132 m/s (0.3 to 0.4 Mach). The pairing of lengths and rates used is not stated.
3. The graticule label "5-35" is not described in detail (which axis, what each tick is). "35.4 px per unit" and the assumption of degrees drive the whole PR113 analysis.
4. Tranche 3 has no sensor videos in Table 2, although the text says five tranches were released; whether tranche 3 contained no sensor videos or was categorized differently is not stated.
5. The paper's identifiers (`DOW-UAP-PR19`, etc.) are not uniformly zero-padded; whether PR19 and PR019 are the same clip is not stated. All 112 identifiers in the table are unique.
6. "Infrared, ATFLIR channel unstated" (8 clips) means the authors could not tell IR from EO for those clips.
7. The paper treats all frame sizes as a "frame constant", but the clip frame rate (30 fps) is container-reported; no check against the original sensor rate (for ATFLIR 30 Hz NTSC-like vs 29.97) is given.
8. GOFAST's own pixel scale (0.7 deg, 480 px) is not used; the paper mentions GOFAST only as precedent.
9. The paper cites AARO's Feb. 2025 report; see `aaro-gofast.md` for what that report actually gives and where it differs.
