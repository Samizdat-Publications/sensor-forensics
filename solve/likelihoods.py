"""Criterion likelihoods for M3 scoring (docs/design/scoring.md, binding).

Pure functions; no knowledge of hypotheses. solve/score.py is the only caller in
solve/ (enforced by tests/test_equal_treatment.py).

- interval_loglik: a readout v shown in steps of `step` means the true value lay in
  [v - step/2, v + step/2] when the display last updated. The likelihood of a
  prediction x is the probability that x plus Gaussian measurement noise (sigma)
  lands in that interval: Phi((v + h - x)/s) - Phi((v - h - x)/s). As sigma -> 0
  this is the uniform interval (1 inside, 0 outside); computed in log space so
  far-outside predictions keep a finite, ordered log-likelihood.
- gaussian_loglik: ordinary normal log density of residuals.
- n_eff_autocorr: effective sample size n / (1 + 2 sum rho_k), with rho_k the
  sample autocorrelation summed until it first drops to zero or below (initial
  positive sequence). Frames are not independent; each criterion's summed
  log-likelihood is scaled by n_eff / n.
- bic_penalty: 0.5 k ln(n_eff).
- rotation_loglik: the image-rotation criterion for every model (M3.5). The model supplies a
  predicted orientation up to fitted terms and its kind; the free terms (a glare's one offset,
  or a physical object's smooth rotation spline, plus a shared per-polarity-segment offset of
  the measurement) are fitted here by linear least squares. Since CP-04 (REVIEW-M3 Rule C) they
  are scored by blocked cross-validation (held-out log-likelihood, not counted in k), so the
  same code and the same rule serve every hypothesis.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.special import log_ndtr

LOG_FLOOR = -1e6


def _log_diff_ndtr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """log(Phi(a) - Phi(b)) for a >= b, stable in both tails."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    out = np.empty(np.broadcast(a, b).shape)
    a, b = np.broadcast_arrays(a, b)
    # Upper tail: use the mirror Phi(a) - Phi(b) = Phi(-b) - Phi(-a).
    upper = b > 0
    hi = np.where(upper, -b, a)
    lo = np.where(upper, -a, b)
    lhi = log_ndtr(hi)
    llo = log_ndtr(lo)
    d = np.clip(llo - lhi, None, -1e-300)
    out[...] = lhi + np.log(-np.expm1(d))
    return np.maximum(out, LOG_FLOOR)


def interval_loglik(obs: np.ndarray, pred: np.ndarray, step: float, sigma: float) -> np.ndarray:
    """Per-sample log-likelihood of quantized readouts `obs` (display step `step`) given predictions."""
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    h = 0.5 * step
    s = max(float(sigma), 1e-9)
    return _log_diff_ndtr((obs + h - pred) / s, (obs - h - pred) / s)


def gaussian_loglik(resid: np.ndarray, sigma: np.ndarray | float) -> np.ndarray:
    resid = np.asarray(resid, float)
    s = np.asarray(sigma, float)
    return -0.5 * (resid / s) ** 2 - np.log(s) - 0.5 * np.log(2 * np.pi)


def autocorr(x: np.ndarray, max_lag: int | None = None) -> np.ndarray:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.array([1.0])
    x = x - x.mean()
    v = np.dot(x, x)
    if v <= 0:
        return np.array([1.0])
    m = n - 1 if max_lag is None else min(max_lag, n - 1)
    return np.array([np.dot(x[: n - k], x[k:]) / v for k in range(m + 1)])


def n_eff_autocorr(resid: np.ndarray) -> float:
    """Effective sample size from the integrated autocorrelation (initial positive sequence)."""
    r = np.asarray(resid, float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 3:
        return float(n)
    rho = autocorr(r, max_lag=n // 2)
    s = 0.0
    for k in range(1, len(rho)):
        if rho[k] <= 0:
            break
        s += rho[k]
    return float(max(1.0, min(n, n / (1.0 + 2.0 * s))))


def scaled_sum(ll: np.ndarray, n_eff: float) -> float:
    """Sum of per-sample log-likelihoods scaled by n_eff / n (the design's autocorrelation rule)."""
    ll = np.asarray(ll, float)
    ll = ll[np.isfinite(ll)]
    n = len(ll)
    if n == 0:
        return 0.0
    return float(ll.sum() * (n_eff / n))


def robust_sigma_from_diffs(y: np.ndarray) -> float:
    """Frame-to-frame measurement scatter: 1.4826 * MAD(diff(y)) / sqrt(2)."""
    y = np.asarray(y, float)
    d = np.diff(y[np.isfinite(y)])
    if len(d) < 3:
        return float("nan")
    mad = np.median(np.abs(d - np.median(d)))
    return float(1.4826 * mad / np.sqrt(2.0))


def smooth_residual(t: np.ndarray, y: np.ndarray, degree: int = 3) -> np.ndarray:
    """Data-only residual about a low-order polynomial (used to measure autocorrelation)."""
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    ok = np.isfinite(y) & np.isfinite(t)
    out = np.full_like(y, np.nan)
    if ok.sum() <= degree + 1:
        return out
    p = np.polynomial.Polynomial.fit(t[ok], y[ok], degree)
    out[ok] = y[ok] - p(t[ok])
    return out


def bic_penalty(k: int | float, n_eff: float) -> float:
    return 0.5 * float(k) * float(np.log(max(n_eff, 1.0)))


_BASIS_CACHE: dict = {}


def natural_spline_basis(t: np.ndarray, n_knots: int) -> np.ndarray:
    """Columns: natural cubic splines through n_knots evenly spaced knots over t (one unit value each).

    Any natural cubic spline on those knots is a linear combination of the columns, so fitting it
    is linear least squares; its degrees of freedom are n_knots.
    """
    t = np.asarray(t, float)
    k = int(n_knots)
    key = (t.tobytes(), k)
    if key not in _BASIS_CACHE:
        tk = np.linspace(t.min(), t.max(), k)
        _BASIS_CACHE[key] = CubicSpline(tk, np.eye(k), bc_type="natural", axis=0)(t)
    return _BASIS_CACHE[key]


def cv_folds(n: int, n_eff: float, n_folds: int = 5) -> np.ndarray:
    """Fold id per sample for blocked cross-validation (REVIEW-M3 Rule C).

    Contiguous blocks of ceil(n / n_eff) samples (the decorrelation length implied by the data's own
    n_eff), assigned to the folds in turn. Depends only on n and n_eff, never on a model.
    """
    b = max(1, int(np.ceil(n / max(float(n_eff), 1.0))))
    return (np.arange(n) // b) % int(n_folds)


def rotation_fit(obs: np.ndarray, base: np.ndarray, kind: str, segment: np.ndarray, t: np.ndarray,
                 n_knots, penalty_per_term: float = 0.0, scale: float = 1.0, sigma: float = 1.0,
                 folds: np.ndarray | None = None) -> dict:
    """Best fit of the free rotation terms for one model (shared by every hypothesis).

    obs: measured orientation (deg, unwrapped with period 180); base: the model's predicted
    orientation without its free terms, at the same samples; kind: "glare" (free terms: one
    constant offset, Sitrec's glare start angle) or "physical" (a natural cubic spline: the
    object's own rotation, free and smooth). Every kind also gets one offset per polarity
    segment after the first (a measurement bias between white-hot and black-hot thresholds,
    the same for all). Orientations are axial, so base is unwrapped with period 180 and any
    whole multiple of 180 is absorbed by the offset or the spline's constant.

    folds: fold id per sample (cv_folds). When given (REVIEW-M3 Rule C), the free terms are scored
    by blocked cross-validation: each fold's samples are predicted from a fit to the others, the
    criterion is the held-out log-likelihood, the knot count is the one with the largest held-out
    log-likelihood, and the free terms are NOT charged in k (dof 0). Without folds: the earlier
    in-sample fit, the knot count chosen by scale * sum(loglik) - penalty_per_term * terms, dof = terms.
    Returns residuals and fitted values of the full-data fit at the chosen knot count, the per-sample
    log-likelihood (held-out when cross-validated) and the number of terms charged in k.
    """
    obs = np.asarray(obs, float)
    base = np.unwrap(np.asarray(base, float), period=180.0)
    r = obs - base
    segment = np.asarray(segment)
    n_seg = len(np.unique(segment)) - 1
    if kind == "glare":
        ks = [1]
    elif kind == "physical":
        ks = [int(n_knots)] if np.isscalar(n_knots) else [int(k) for k in n_knots]
    else:
        raise ValueError(f"unknown rotation kind {kind!r}")
    t = np.asarray(t, float)
    best = None
    for k in ks:
        A, A_pinv = _rotation_design(kind, k, t, segment)
        coef = A_pinv @ r
        fitted = A @ coef
        res = r - fitted
        if folds is None:
            ll = gaussian_loglik(res, sigma)
            score = scale * float(np.sum(ll)) - penalty_per_term * A.shape[1]
            dof = int(A.shape[1])
            cv_res = None
        else:
            cv_res = np.empty_like(r)
            for fold, (m, P) in _cv_design(kind, k, t, segment, np.asarray(folds)).items():
                cv_res[m] = r[m] - A[m] @ (P @ r[~m])
            ll = gaussian_loglik(cv_res, sigma)
            score = scale * float(np.sum(ll))
            dof = 0
        if best is None or score > best["score"]:
            best = {"resid": res, "fitted": base + fitted, "dof": dof, "coef": coef, "score": score,
                    "n_model_terms": int(k), "n_segment_terms": n_seg, "n_terms": int(A.shape[1]),
                    "loglik": ll, "cv_resid": cv_res, "cross_validated": folds is not None}
    return best


_CV_CACHE: dict = {}


def _cv_design(kind: str, k: int, t: np.ndarray, segment: np.ndarray, folds: np.ndarray) -> dict:
    """{fold: (held-out mask, pseudo-inverse of the training rows)} (cached: fixed per case)."""
    key = (kind, k, t.tobytes(), segment.tobytes(), folds.tobytes())
    if key not in _CV_CACHE:
        A, _ = _rotation_design(kind, k, t, segment)
        out = {}
        for f in np.unique(folds):
            m = folds == f
            out[int(f)] = (m, np.linalg.pinv(A[~m]))
        _CV_CACHE[key] = out
    return _CV_CACHE[key]


_DESIGN_CACHE: dict = {}


def _rotation_design(kind: str, k: int, t: np.ndarray, segment: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Design matrix of the free rotation terms and its pseudo-inverse (cached: fixed per case)."""
    key = (kind, k, t.tobytes(), segment.tobytes())
    if key not in _DESIGN_CACHE:
        cols = [np.ones(len(t))] if kind == "glare" else list(natural_spline_basis(t, k).T)
        cols += [(segment == sg).astype(float) for sg in np.unique(segment)[1:]]
        A = np.column_stack(cols)
        _DESIGN_CACHE[key] = (A, np.linalg.pinv(A))
    return _DESIGN_CACHE[key]


def rotation_loglik(obs: np.ndarray, base: np.ndarray, kind: str, segment: np.ndarray, t: np.ndarray,
                    sigma: float, n_knots, penalty_per_term: float = 0.0, scale: float = 1.0,
                    folds: np.ndarray | None = None) -> tuple[np.ndarray, int, dict]:
    """Per-sample Gaussian log-likelihood of the measured orientation under the best-fit free terms
    (held-out when `folds` is given, REVIEW-M3 Rule C).

    Returns (per-sample loglik, free-term count for the complexity penalty, fit details).
    """
    fit = rotation_fit(obs, base, kind, segment, t, n_knots, penalty_per_term, scale, sigma, folds)
    return fit["loglik"], fit["dof"], fit
