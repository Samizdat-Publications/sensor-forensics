# M3 scoring design (binding for solve/score.py and solve/models/)

Written 10/31/2026 before any hypothesis is scored, so the rules cannot be tuned to a result.

## Principles

1. **One scoring path.** Every hypothesis is scored by the same function, against the same observables, with the same uncertainty model. Hypotheses differ only in their physical model and parameter priors, which live in data files (`solve/hypotheses/*.yaml`). Code never branches on a hypothesis name (enforced by an AST test).
2. **Likelihoods, not verdicts.** Each criterion yields a log-likelihood. Totals are sums of weighted log-likelihoods minus a complexity penalty. No prior probability is put on hypothesis classes ("aircraft" vs "unknown"); readers can apply their own.
3. **Two totals, always shown together** (D-011): a testimony-weighted total (testimony weight 1.0 by default, adjustable) and a physics-only total (testimony weight 0). Neither is hidden.
4. **Say when the data cannot decide.** A model-recovery test (synthetic data from each hypothesis through the full scorer) shows which hypotheses this data can separate even in principle; results are reported against that confusion matrix.

## Hypotheses (initial set; Stewart may add more)

| Id | Model | Free parameters (priors with sources in the YAML) | Applies to |
|---|---|---|---|
| H-AC | Distant aircraft, engine exhaust seen as glare | range, airspeed 250 to 520 kt, altitude 15,000 to 45,000 ft, heading; glare size independent of range; glare rotation follows the pod's derotation | GIMBAL, FLIR1 |
| H-BAL | Balloon drifting with the wind | start range only (velocity = ERA5 wind at its altitude, with wind uncertainty) | GOFAST, GIMBAL |
| H-SLOW | Slow object (bird, small drone) at the measured or implied range, apparent speed from parallax | range, air speed 0 to 60 kt, heading | GOFAST, GIMBAL |
| H-CLOSE | Close small object | range 0.05 to 2 nmi, size 0.1 to 2 m, air speed | GIMBAL, FLIR1 |
| H-WIT | Object at the aircrew-reported range, motion free (what the geometry then requires) | range from testimony (GIMBAL 6 to 8 nmi; FLIR1 per claims), path as a smooth spline | GIMBAL, FLIR1 |
| H-ART | Sensor artifact: glare in the pod optics, rotation set by derotation; target of any type behind it | as H-AC plus the glare model | GIMBAL, FLIR1 |

H-WIT is scored with the same likelihoods as the others; its flexibility (a spline path) is charged by the complexity penalty like any other free parameter.

## Criteria (observables) and their likelihoods

| Criterion | Measurement | Likelihood | Videos |
|---|---|---|---|
| Line of sight | Az/El readouts as intervals (whole degrees, 6-frame updates) | Uniform interval smoothed by measurement noise; effective sample size n/6 for azimuth | all |
| Angular motion vs background | Cloud / ocean motion and the lab turn-rate history | Gaussian on the residual with the measured confidence | GIMBAL, GOFAST |
| Range readout | GOFAST RNG (0.1 nmi steps) | Interval likelihood | GOFAST |
| Closure rate | GOFAST Vc | Gaussian with step-size noise | GOFAST |
| Apparent size trend | Blob size within one polarity, normalized | Real object: size proportional to 1/range; glare: size set by brightness, not range | GIMBAL, FLIR1, GOFAST |
| Rotation | Glare orientation per frame | Glare hypotheses: predicted by the pod-roll / derotation model; physical object: rotation is a free spline (penalized) | GIMBAL, FLIR1 |
| Brightness trend | Integrated contrast within one polarity | Relative trend only (no radiometric calibration) | all |
| Testimony | Claims in `data/testimony/*.yaml` with a quantity the model predicts (range, altitude, speed, stop/reverse, behavior vs wind, size) | Interval likelihood using the claim's uncertainty band; firsthand claims at full weight, relayed at half; conflicting claims each enter with their own band (they widen, not cancel) | all |

Claims the geometry cannot predict (number of objects, sounds, radar screens not released) are listed as context and not scored.

Autocorrelation: each criterion's log-likelihood is scaled by n_eff / n, with n_eff from the measured autocorrelation (frames are not independent).

Complexity: BIC-style penalty 0.5 k ln(n_eff) per hypothesis, same rule for all; splines count their effective degrees of freedom.

## Outputs per video

`data/derived/<case>/scores.csv` (hypothesis, criterion, loglik, n_eff, weight) and `results.json` (best-fit parameters, both totals, rank, range curves); `docs/results/<case>.md` with a plain-language table.

## Discriminators

For each pair of top hypotheses, the single measurement and precision that would separate them with a likelihood ratio of 10 or more (for example: radar range at a timestamp, to a given precision; a closure rate; a calibrated size). Written to `docs/results/<case>.md`.

## Equal-treatment tests

- AST scan: no code under `solve/` compares a hypothesis id or label.
- Renaming or reordering hypotheses leaves every score unchanged.
- A single public scoring entry point is used by every caller.
