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
"""

from __future__ import annotations

import numpy as np
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
