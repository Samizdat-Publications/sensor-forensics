# REVIEW-M3: resolving the four review items on the provisional GIMBAL scoring

Work item of 10/31/2026. Each fix below is justified by a data-quality test or by the pre-registered design (`docs/design/scoring.md`, binding), never by its effect on the ranking. The decision rules in section 0 were written into this file BEFORE any of the measurements they decide were made, and before any rerun of the totals.

## 0. Decision rules, stated before measuring

### Rule B (brightness criterion: is it range-informative?)

The brightness criterion (design: "Integrated contrast within one polarity, relative trend only") is kept only if the measured brightness can carry range information. Measured per video on the scored window, within each polarity segment the scorer uses (at least 20 frames), with y = ln(integrated contrast), the series the scorer fits:

- **B1 saturation.** On a frame the blob is saturated if at least 3 of its pixels sit within 2 gray levels of the video's clip code on the object's side (white-hot: the brightest code of the clip; black-hot: the darkest). If the blob is saturated on more than half of the scored frames, the criterion is not range-informative.
- **B2 gain and level.** y (centered in each segment) is regressed by least squares on frame-level gain and level proxies, also centered per segment: the natural logs of the median level and of the robust contrast (1.4826 x MAD) of the whole active picture, and of the same two numbers in a fixed background region (GIMBAL: the lower-left cloud tile the turn rate was measured in; GOFAST: the same tile position, ocean). If those proxies explain more than half of the variance of y (R squared above 0.5, adjusted for 4 regressors with the criterion's own n_eff), the criterion is not range-informative.
- **B3 zoom and polarity.** A zoom change inside a polarity segment would change the blob's scale for every source; if one occurs and is not modeled, the criterion is not range-informative. The WHT/BLK switch is already handled by normalizing within each segment (no fix needed unless B2 fails in only one segment).
- **Decision.** If B1, B2 or B3 fails, the brightness criterion carries weight 0 for every hypothesis (still computed and reported, not in any total). Otherwise it stays in the totals with its measured noise. Steps that appear at the same frame in the object's brightness and in the frame-level level or contrast are listed as supporting evidence; they do not change the decision on their own. The same rule is applied to GOFAST.
- Known conservative bias: if the scene's level happens to drift in step with a genuine range trend, B2 removes a criterion that was informative. That error removes information; it cannot create a preference.

### Rule R (range priors)

Every hypothesis gets the same range support, 0.5 to 60 nmi, log-uniform, except where the binding design table defines the hypothesis by its range: H-CLOSE ("range 0.05 to 2 nmi") is a statement of what the hypothesis is, so its range stays as designed (otherwise it would duplicate H-SLOW). Physical limits act only through each model's own altitude and speed priors, applied identically by the scorer as a uniform prior on the object's altitude over the scored window (a hypothesis-agnostic `constraints` block in the YAML, with a soft edge only for the optimizer). Bounds are set from sources, written into the YAMLs, before any rerun.

### Rule T (turn rate with ERA5)

A substitution of inputs, no decision threshold: the placeholder winds and the ISA temperature in the GIMBAL cloud-derived turn rate are replaced by ERA5 (jet level and cloud-deck level) at 01/25/2015 02:30Z for the nominal history, and by draws over 01/24 18Z to 01/25 06Z for the band. The scorer then uses the recomputed history and band. The change in the turn rate and its band is reported whatever its direction.

### Rule P (point-spread width and D-016)

The point-spread width is measured on each video and expressed in the same blob metric the size criterion uses (the low-threshold major axis of an unresolved source), by passing a synthetic point source of the measured width through the same moment code. D-016's test (major axis at least 3 times the point-spread width) is then applied with the WIDEST point-spread width the video's measurements allow (the upper bound), so an object is called resolved only if it is resolved for every point-spread width consistent with the data. If the measurements cannot bound the width from above, the object is not called resolved.

## 1. Brightness criterion audit (Rule B)

**What was tested.** `extract/frame_levels.py` measured, on every frame of both videos, the median level and robust contrast of the whole active picture and of the fixed background tile (symbology, reticle and a 60 px box around the object masked), and rebuilt the object's low-threshold blob from `image_track.csv` to read its extreme raw code. `solve/brightness_audit.py` applied Rule B on the frames the brightness criterion scores. Zoom is constant in both clips (GIMBAL 2.0 on all 1,031 frames, GOFAST 1.0), so B3 cannot fail.

**Evidence, GIMBAL** (`data/derived/gimbal/brightness_audit.json`, `frame_levels.csv`):

- The clip codes of this copy are 185 (brightest) and 0 (darkest).
- White-hot segment (f0 to f371): the blob's brightest pixel is 158 to 175, never at the clip; saturated on 0 percent of frames.
- Black-hot segment (f372 to f1030, 659 frames): the blob's darkest pixel is code 0 on every frame, with a median of 162 of its 225 pixels at the clip. The measured peak contrast equals the local background level on every frame (median 70 and 70): the core is clipped to black, so the "integrated contrast" is the background level times the clipped area, not the object's signal.
- B1: saturated on 64 percent of the scored frames (limit 50 percent): **fails**.
- B2: the four frame-level proxies explain 15 percent of the variance (adjusted 14 percent, limit 50 percent): passes overall; within the black-hot segment alone they explain 56 percent.
- Steps at the same frame in the object's brightness and the frame level: f371 (the polarity switch) and f868.

**Evidence, GOFAST** (`data/derived/gofast/brightness_audit.json`):

- Black-hot labeled segments (f368 to f636, f784 to f1030): the object is brighter than the ocean, its brightest pixel 92 to 185 (median 162), saturated on 0 percent of frames.
- White-hot labeled segment (f638 to f782, 145 frames): the object is darker than the ocean and clipped at code 0 (median 14 of 23 pixels at the clip) on all of them.
- B1: saturated on 22 percent of the scored frames: passes. B2: adjusted R squared 0.02: passes.

**Decision.** GIMBAL: the brightness criterion is not range-informative (B1); it carries weight 0 for every hypothesis at both fields of view, still computed and shown. GOFAST: kept with its measured noise, as the pre-stated rule requires. Recorded but not acted on, because the rule did not provide for it: the GOFAST white-hot segment (22 percent of its frames) is saturated too, so that part of the GOFAST brightness series is not radiometric. Wiring: `image.brightness_audit` in both case YAMLs; `solve/case_data.py` reads the decision. A criterion with weight 0 also no longer counts in the BIC n (n_eff total), so "reported, not in any total" now holds for the complexity penalty too (before, D-016's weight-0 size row was still counted there).

## 2. Equal range priors (Rule R)

**What changed** (YAMLs edited before any rerun; sources in each file):

| Hypothesis | Range support before | Range support now | Physical limit (constraint on the object's altitude over the scored window, or speed prior) |
|---|---|---|---|
| H-AC | none (parameterized by altitude 15,000 to 45,000 ft) | 0.5 to 60 nmi | altitude 15,000 to 45,000 ft; airspeed 250 to 520 kt (unchanged) |
| H-ART | 0.05 to 60 | 0.5 to 60 | airspeed 0 to 600 kt (unchanged) |
| H-BAL | 0.3 to 25 | 0.5 to 60 | velocity = ERA5 wind plus the shared wind error (unchanged); no altitude limit (balloons float from the surface to far above these sight lines) |
| H-SLOW | 0.1 to 25 | 0.5 to 60 | airspeed 0 to 60 kt (unchanged); altitude 0 to 20,000 ft (Dolbeer 2006: bird-strike heights fall about 32 percent per 1,000 ft above 500 ft, so well under 0.1 percent are above 20,000 ft; DJI Phantom 3 service ceiling 6,000 m) |
| H-WIT | 0.5 to 60 | 0.5 to 60 | none (by design) |
| H-CLOSE | 0.05 to 2 | 0.05 to 2 (unchanged) | the binding design defines this hypothesis by its range; with 0.5 to 60 it would duplicate H-SLOW |

**Reasoning.** A range bound is not a physical statement about a bird, a balloon or an aircraft; the earlier caps (25 nmi) were hit by the GIMBAL fits, so part of the ranking came from where the prior box ended. What a hypothesis physically rules out is an altitude or a speed, so the limits now act there, through one hypothesis-agnostic mechanism (`constraints` in the YAML, `solve/score.py::constraint_log_prior`: a uniform prior on a testimony-vocabulary quantity, reported in the prior row). H-AC keeps the same number of free parameters (range replaces altitude). Correction made during the work, before any GIMBAL total was read: the first GOFAST rerun used a 100 ft soft edge, and the H-AC fit traded a 1,300 ft violation of its altitude floor for a better range-readout fit, because a 100 ft Gaussian edge costs only about 90 log units there. A uniform prior has zero density outside its support, so the edge is now 1 ft (effectively hard) and every run was restarted with it.

## 3. GIMBAL turn rate with ERA5 (Rule T)

**What was done.** `python -m solve.turn_rate_gimbal --era5` (new `era5_variant`) reran the lab's cloud inversion with ERA5 (box centre) in place of the placeholders: jet-level wind at the jet's pressure altitude, cloud-deck wind at the deck height, TAS from the on-screen Mach with the ERA5 jet-level temperature. The Monte Carlo band (300 draws) now draws a time uniformly in 01/24 18Z to 01/25 06Z and uses ERA5 at that time (plus 5 kt per wind component) instead of "120 kt from 240 to 300" and "0 to 40 kt from anywhere"; everything else in the band is unchanged (azimuth crossing times, deck 8,000 to 18,000 ft, texture distance, image scale and aspect, jet pitch, whole picture or cloud tile, and the jet's initial heading 295 to 335 deg, which is still not on screen). Output: `data/derived/gimbal/turn_rate_era5_fov035.csv`, `turn_rate_era5_fov070.csv`, `turn_rate_era5_summary.json`; the case YAML now points at them (the placeholder files are kept).

**Evidence.**

| | 0.35 deg | 0.7 deg |
|---|---|---|
| ERA5 at 02:30Z | jet level 99 kt from 261, cloud deck (11,740 ft) 50 kt from 264, ISA +8.8 K | same |
| Placeholders it replaces | 120 kt from 270, 17 kt from 240, ISA | same |
| Spread over the window (2.5 to 97.5 percent of draws) | jet 82 to 107 kt from 245 to 266; deck 35 to 87 kt; ISA +8.0 to +9.7 K | same |
| Total heading change, placeholder to ERA5 | -64.96 to -65.13 deg | -68.38 to -68.56 deg |
| ERA5 band of the total heading change (95 percent) | -65.64 to -64.84 deg | -69.16 to -68.10 deg |
| Shift of the nominal history (rms, frames 45 to 985) | 0.0051 deg/s (an almost constant -0.005 deg/s) | 0.0054 deg/s |
| Band median half-width, placeholder to ERA5 | 0.045 to 0.043 deg/s | 0.046 to 0.044 deg/s |
| Frames where the ERA5 history leaves the old band | 0 percent | 0 percent |

**Decision.** The ERA5 history and band replace the placeholder ones in scoring. The change is small (about a tenth of the band's half-width), as the lab had estimated: the cloud-deck wind is three times the placeholder, but its parallax term is small at the deck's distance.

## 4. Point-spread width and D-016 (Rule P)

**What was measured** (`extract/psf.py`, `data/derived/<case>/psf.json`), as FWHM in display px:

| Measurement | GOFAST | GIMBAL |
|---|---|---|
| Symbology line spread (recording chain only: a LOWER bound) | 1.4 px across horizontal strokes, 2.8 px across vertical strokes | 1.3 px, 2.7 px |
| The object's own half-maximum minor axis, unsaturated frames (UPPER bound) | 3.3 px | 9.8 px (white-hot segment) |
| GOFAST's point source carried over by the documented zoom (UPPER bound) | n/a | 0.35 deg: NAR 2.0 is a 2x digital zoom of the 0.7 deg optical field (P&vR p. 8), so 2 x 3.3 = 6.6 px; 0.7 deg: no digital zoom, 3.3 px |
| Widest point-spread width allowed (smallest upper bound) | 3.3 px | 6.6 px (0.35 deg), 3.3 px (0.7 deg) |
| Same, in the size criterion's metric (low-threshold major axis of a synthetic point source) | 5.5 px | 9.8 px (0.35 deg), 5.5 px (0.7 deg) |
| Blob major axis in that metric (median, scored window) | 6.4 px | 24.6 px |
| D-016 ratio, major axis / point-spread width (resolved if at least 3) | 1.2: **unresolved** | 0.35 deg: 2.5, **not resolved**; 0.7 deg: 4.5, **resolved** |

Compact scene features were examined as a tighter upper bound and rejected: on GIMBAL the only high-contrast compact features lie on a straight moving track (symbology); on GOFAST they cannot be told apart from compression noise.

**Decision.** D-016 applied as written: the apparent-size criterion carries weight 0 on GOFAST (newly: D-016 applies to every video, and the GOFAST case had no point-spread width before) and on GIMBAL at 0.35 deg, and full weight on GIMBAL at 0.7 deg. Wiring: `image.psf_file` in both case YAMLs (per sensor variant for GIMBAL). Open, not decided here: at 0.7 deg the GIMBAL size series in the black-hot segment comes from the same clipped blob that failed Rule B, and the glare models' size prediction uses the measured brightness; D-016 does not cover saturation, so a rule for the size criterion under saturation is left to Stewart (the results page shows the totals with and without it).

## 5. Reruns through the single scoring path

`python -m solve.score gimbal --part fov035`, `--part fov070`, `--merge`; `python -m solve.score gofast`; then `python -m solve.results_report` for both. Full fit settings (400 random points, 10 starts), both totals for every hypothesis. GOFAST now also uses ERA5 (its earlier page ran on the placeholder radiosonde because the ERA5 profile file was missing at the time); wind uncertainty 5 kt instead of 20.

**GIMBAL** (physics-only / testimony-weighted totals; mean range of the physics-only fit):

| Hypothesis | 0.35 deg physics-only | 0.35 deg testimony-weighted | range (nmi) | 0.7 deg physics-only | 0.7 deg testimony-weighted | range (nmi) |
|---|---|---|---|---|---|---|
| H-BAL | -146.1 (1) | -208.6 (2) | 22.8 | -156.3 (5) | -226.3 (5) | 22.5 |
| H-SLOW | -149.8 (2) | -219.0 (3) | 24.8 (on its 20,000 ft ceiling) | -143.8 (4) | -214.2 (4) | 25.3 |
| H-WIT | -168.9 (3) | -191.8 (1) | 59.8 (range bound) | -62.5 (1) | -101.9 (1) | 63.0 (range bound) |
| H-ART | -225.2 (4) | -285.5 (4) | 41.0 | -107.3 (2) | -157.7 (2) | 21.7 |
| H-AC | -225.2 (5) | -308.8 (5) | 39.3 | -107.3 (3) | -180.9 (3) | 21.7 |
| H-CLOSE | -14,617.7 (6) | -14,667.7 (6) | 1.9 (range bound) | -15,154.0 (6) | -15,208.1 (6) | 1.9 |

What the totals now rest on: at 0.35 deg, the azimuth and elevation readouts, the image rotation and the turn-rate band (size and brightness weight 0); at 0.7 deg, the same plus the apparent size. The rotation criterion is the main separator between glare and physical models: the free physical rotation (32 knots) beats the pod-derotation glare by about 130 log units before penalties. At 0.7 deg the resolved-size criterion favors H-WIT and the glare models (it adds about 120 to each, against 15 to 31 for H-BAL and H-SLOW).

Sensitivity of the BIC change (weight-0 criteria no longer counted in the BIC n: 45 instead of 360 at 0.35 deg, 106 instead of 360 at 0.7 deg): with the old n every total drops by 0.5 k ln(n_old / n_new) (about 1.0 k at 0.35 deg and 0.6 k at 0.7 deg), and no rank changes in any of the four columns (largest: H-WIT physics-only at 0.35 deg, -168.9 to -219.5, still third).

**GOFAST** (frames 368 to 1030; physics-only / testimony-weighted; mean range):

| Hypothesis | physics-only | testimony-weighted | range (nmi) |
|---|---|---|---|
| H-BAL | -1,028.5 (1) | -1,042.2 (1) | 3.85 |
| H-ART | -1,034.4 (2) | -1,048.1 (2) | 3.85 |
| H-SLOW | -1,034.4 (3) | -1,048.1 (3) | 3.85 |
| H-WIT | -1,065.3 (4) | -1,079.1 (4) | 3.84 |
| H-AC | -20,092.2 (5) | -20,108.9 (5) | 3.24 (on its 15,000 ft floor) |
| H-CLOSE | -48,799.0 (6) | -48,823.8 (6) | 2.02 (range bound) |

H-BAL, H-ART and H-SLOW fit the same path (3.85 nmi, 13,212 ft, about 53 kt over the ground toward 88 to 93 deg); H-BAL leads by the penalty for two fewer parameters (5.9). With the size criterion at weight 0 (D-016) the glare model's earlier lead (it came from the size row) is gone.

**Banner.** All four review items are resolved, so the PROVISIONAL banner is removed from `docs/results/gimbal.md`; the page instead points here and to the recovery test, and lists the open size-under-saturation item in its sensitivity section.

## 6. Model-recovery test (M3.4)

`solve/recovery.py`; tables in `docs/results/recovery.md`, rows in `data/derived/<case>/recovery.csv`. Synthetic data from each hypothesis at three parameter sets (its physics-only best fit, and its best fit at about 0.6 and 1.6 times that range), two noise draws each, with the real display quantization and cadence, the real measurement noise (each series' own residual, circularly shifted) and the same weight-0 criteria; every hypothesis fitted by the single scoring path with the real runs' fit settings (physics-only). GIMBAL was run at 0.35 deg only (36 data sets); GOFAST 34 data sets (H-AC has no far set: it would break its altitude floor).

**GIMBAL, 0.35 deg.** The rotation criterion cleanly splits the two groups: data from a glare model were always won by a glare model, data from a physical model always by a physical model. Inside the groups: H-AC and H-ART are the same model here and tie (leads 0.0 to 0.1), so the data cannot tell a distant aircraft from a glare on any target; H-BAL and H-CLOSE are recovered every time (H-BAL by 2.9 to 10, H-CLOSE by 13 to 34); data made by H-SLOW and by H-WIT are always won by H-BAL (H-SLOW behind by 2.4 to 3.8, i.e. the penalty for its two extra parameters: a 60 kt flier at 20 to 40 nmi is not distinguishable from a balloon; H-WIT's fitted paths are nearly straight, so its spline is not earned). So on the real data, H-BAL's physics-only lead over H-SLOW (3.7) is exactly what data from either would give, and its lead over H-WIT says only that no curved path is required.

**GOFAST.** With size at weight 0 (D-016) and no rotation criterion, H-AC, H-ART, H-SLOW and H-CLOSE are the same point-target physics and differ only by priors. H-ART, with the widest airspeed prior (0 to 600 kt) and the same parameter count, wins most data sets made by the others, including all made by H-CLOSE and H-AC (by 11 to 19 when the fits converge; the BIC penalty counts parameters, not prior width). At the best-fit (real-data-like) sets, H-BAL won the data made by H-ART, H-BAL, H-SLOW and H-WIT. So GOFAST's range readout fixes where the object was (3.85 nmi, 13,200 ft), but the data cannot say whether it was a balloon, a slow flier or a glare on a slow target; H-BAL's 5.9 lead is a parsimony margin, not a discrimination. The optimizer check flags 8 GOFAST data sets where the true model's own fit stopped below its true-parameter total (mostly H-CLOSE at its 2 nmi bound and H-WIT's spline); those cells understate the truth.

**Not run** (recorded as the next step, under the coordinator's resource limit for this machine): GIMBAL at 0.7 deg, where the resolved size criterion also counts.

## 7. CP-04 must-fix methods, stated before running (11/01/2026)

The independent check on CP-04 (`artifacts/review/CP-04-review.md`) sent it back. The methods below were written into this file before any of them was computed on the real data; the results follow in section 8.

### Rule X (post-hoc exclusions reported both ways)

The three data-quality exclusions (Rule B brightness audit, D-016 resolved size, D-017 saturated size) were not decided blind: D-017 was ruled with both 0.7 deg rankings visible, and the brightness and size reviews were prompted by provisional rankings. So every case is now fitted twice through the same path: once with the exclusions (the default, as before) and once with every pre-registered criterion at its design weight (scoring.yaml, all 1.0; the BIC n then counts those criteria's n_eff again). Both sets of totals, each at its own refitted best fit, are reported side by side in each results page and in results.json (`no_exclusions` block per run), with a plain sentence on which ranks change. Nothing else differs between the two runs. Other measurement-validity rules that are not weight changes (FLIR1's unresolved-FOV frames, the rotation quality rule) are kept in both runs.

### Rule N (rotation measurement noise, from the data only)

The rotation sigma is the measurement's own error, estimated without any model of the object:

1. Two independent thresholdings of the same blob on the same frame (`obj_hi_angle_deg` and `obj_lo_angle_deg`) each measure the same axial orientation. Their difference, wrapped to plus or minus 90 deg, with its mean removed per scored segment (a constant per-segment bias is absorbed by the segment offset every model gets), has variance 2 sigma^2 if the two errors are independent and equal. So sigma_thr = SD(diff) / sqrt(2), over the criterion's own scored frames.
2. The frame-to-frame scatter of the scored series, 1.4826 MAD(first differences) / sqrt(2) (`likelihoods.robust_sigma_from_diffs`), is the white part of the noise. A noise estimate cannot be below it.
3. sigma = max(sigma_thr, sigma_ff). The two-threshold difference also contains slow, shape-dependent errors that a running median or a frame difference cannot see, which is why it is the primary estimate. The previous value (scatter about a 9-frame running median, 0.88 deg at GIMBAL) is kept and reported.

The same rule, on the same columns, applies to GIMBAL and FLIR1 and to every hypothesis. The rotation criterion and all totals are refitted at this sigma. A sensitivity sweep at 0.88, 1.3, 2.0 and 3.0 deg rescored at each run's best-fit parameters (rotation criterion and both totals; not refitted, stated as such) is reported for both cases.

### Rule C (complexity of fitted splines that BIC cannot count)

BIC is not valid where a fit's free terms approach or exceed the sample size: the physical rotation spline (up to 33 terms) against a rotation n_eff of 23, and H-WIT's total k of 49 against a BIC n of 45. The rotation criterion's free terms (any model's: a glare's offset, a physical object's smooth spline, the shared segment offsets) are fitted by linear least squares, so they are now scored by blocked cross-validation instead of being counted in k:

- the scored frames are cut into contiguous blocks of length ceil(n / n_eff) frames (the decorrelation length the data's own n_eff implies; GIMBAL about 45 frames), assigned to 5 folds in turn;
- for each fold the free terms are fitted on the other folds and the held-out frames are predicted; the criterion's log-likelihood is the sum of the held-out Gaussian log densities, scaled by n_eff / n as before;
- the physical spline's knot count is chosen from the same list by the largest cross-validated log-likelihood (no penalty term, since held-out data already charge flexibility);
- these terms then count 0 in k. The parameters fitted by the nonlinear optimizer (ranges, speeds, headings, the shared nuisances and H-WIT's 12 path-knot values) stay in k exactly as before; with the rotation terms out of k, every model's k is below the BIC n (H-WIT: 16 against 45).

The rule is identical for every model with a rotation criterion (glare and physical alike). It is a lab decision within the design's line "splines count their effective degrees of freedom": a held-out likelihood is the effective-degrees-of-freedom charge measured directly.

### Rule G (G-T25, reversal radius)

The vocabulary quantity `reversal_radius_ft` is now defined only for a path that stops and reverses (the `stops_and_reverses` definition used by G-T11): the radius of the tightest turn within 3 s of a frame where that test fires. For a path that does not reverse it is undefined, and G-T25 is conditional (`given: stops_and_reverses = true`): it scores the turn radius only for a path that reverses, and contributes 0 otherwise. Whether the object reversed at all is scored once, by G-T11. The likelihood factors as P(reverses) x P(radius | reverses), so the maneuver is not scored twice and no sentinel value enters any total. The 1,000,000 ft cap is removed.

### Rule K (range curves)

For every hypothesis that has a range parameter, at fixed reference ranges 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45 and 60 nmi (inside its own prior only; H-CLOSE stops at 2 nmi), the remaining parameters are refitted (both totals, with the exclusions, ERA5 winds; fewer random starts than the main fit, stated in the CSV) and the implied mean air and ground speed, mean altitude and largest acceleration over the clip are recorded, with the no-exclusion physics-only total rescored at the same parameters. Output: `data/derived/<case>/range_curves.csv` and `docs/results/<case>_range_curves.png`.

## CP-04 fix status (working notes, 11/01/2026 evening)

- (a) Rule X, both ways: DONE in code (`load_case(exclusions=False)`, `score._run_both`, `no_exclusions` block in results.json, `scores_no_exclusions.csv`, tables in results pages). Reruns: all three done (section 8).
- (b) Rule N sigma and Rule C cross-validation: DONE in code (`likelihoods.cv_folds`, `rotation_fit(folds=...)`, case YAMLs `noise_method: two_threshold`, `cv_folds: 5`; sweep in `rotation_sigma_sweep`). Rule N gives 0.675 deg at GIMBAL (two-threshold 0.25 deg, frame-to-frame 0.675 deg) and 11.9 deg at FLIR1. Results in section 8.
- (c) Rule G, G-T25 conditional: DONE (`models/base.py`, `testimony.py` `given`, `scorable.yaml`, tests).
- (d) Rule K, range curves: DONE for all three videos; CP-04 cites them.
- DONE: recovery and discriminators reruns for GIMBAL, recovery for FLIR1, "What would settle it" text (kept in `data/discriminators/notes.yaml`, key `results_page_settle`), FLIR1 pitch-bound diagnostic (`tools/pitch_check.py`), CP-04.md. Gate: see CP-04.

## 8. CP-04 must-fix results (11/01/2026)

All three videos refitted through the single path (`python -m solve.score <case> --procs 6`), both ways.

**Rule N.** GIMBAL: two-threshold disagreement 0.25 deg (the two thresholds see nearly the same contour, so their errors are correlated and this underestimates), frame-to-frame scatter 0.675 deg, so sigma = 0.675 deg, below the earlier 0.88 deg. FLIR1: two-threshold 11.86 deg, frame-to-frame 1.21 deg, sigma 11.86 deg (earlier 7.51). The rule was applied as written; the sweep (0.88 to 3 deg) is on the GIMBAL and FLIR1 pages.

**Rule C.** With cross-validation the physical rotation spline keeps 16 knots and its held-out residual RMS is 3.66 deg against 2.84 in-sample; the glare model's is 3.64 to 3.65 deg. On held-out data the glare derotation is ahead on this criterion by 3.5 (0.35 deg) and 5.0 (0.7 deg) log units. The earlier 72-unit physical advantage does not survive. A side effect worth stating: cross-validation charges flexibility roughly like AIC, more gently than BIC, so a free smooth rotation can mimic GIMBAL's smooth derotation curve; on synthetic pure-glare data the glare model now wins its own data by about 1.3 log units, not by more than 10 (`tests/test_score_gimbal.py`).

**Rule G.** G-T25 now contributes 0 to every path that does not reverse; H-WIT (0.35 deg) and H-SLOW (0.7 deg) fits that do reverse score about -0.4 on it. The testimony-weighted GIMBAL leader moves from H-WIT to H-BAL at both fields of view.

**Rule X.** GIMBAL without exclusions: H-WIT leads both totals at both fields of view (0.35 deg: 35.3 physics-only, -22.6 testimony-weighted), H-ART and H-AC follow, H-BAL is fifth. With exclusions H-BAL leads. GOFAST without the size exclusion: H-ART leads (-904.6 physics-only against H-BAL -930.3). FLIR1: no exclusion applies, so both ways are identical.

**Rule K.** `data/derived/<case>/range_curves.csv` and `docs/results/<case>_range_curves.png` for all three videos (12 ranges, both totals, fewer random starts than the main fits).

**FLIR1 pitch bound (review nice-to-fix).** `tools/pitch_check.py`: the glare fits sit at pitch 0 deg (prior 3.8 +- 1.5, bounds 0 to 8); with the bound lifted the best pitch is at the scan's edge (-8 deg) and gains 99 to 109 log units on rotation plus prior, against a 268-unit rotation gap. The rest of the gap does not depend on the bound.

**Recovery and discriminators** were rerun for GIMBAL (both fields of view) and FLIR1 with the earlier generator parameter sets (`--reuse-sets`) and one noise draw; see `docs/results/recovery.md` and `discriminators.md`.
