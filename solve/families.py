"""Trajectory families: sight lines turned into curves over range.

Where the range to the object is not measured, a set of sight lines does not pick
one trajectory; it picks a family. Each function here takes one value of the
family's free parameter (a start range, or an altitude), builds the object's path
under a stated physical assumption, and reports the kinematics that assumption
implies plus how well it fits the observed sight lines. Sweeping the parameter
with `range_grid` gives the "range curve": misfit, speed, altitude and
acceleration as functions of range. That curve, not a single point, is the result
(CLAUDE.md: "show the range problem honestly").

Families
--------
1. `constant_velocity(sl, r0)`: bearings-only target motion analysis (TMA). The
   object starts on the reference sight line at slant range r0 and moves in a
   straight line at constant velocity; the velocity (3 numbers) is fitted to all
   sight lines. Seen from an observer flying straight at constant velocity, every
   r0 fits equally well (scaling a constant-velocity solution about the observer
   gives another one), so range is unobservable; a turning observer breaks that
   symmetry, and the depth of the misfit curve shows by how much.
2. `constant_altitude(sl, h)`: the object is where each sight line crosses the
   altitude shell h (spherical Earth, standard refraction optional). Zero misfit
   by construction wherever the ray reaches h; the result is the implied speed and
   acceleration.
3. `wind_drift(sl, r0, wind_fn)`: the object starts on the reference sight line at
   r0 and is carried by the wind at its own altitude, wind_fn(height_m, t) -> ENU
   m/s (optionally plus a constant vertical rate, for a rising or sinking
   balloon). No free parameter after r0, so its misfit curve is the test.
4. `stationary_air(sl, r0, wind_fn, max_air_speed)`: "at rest in the moving air
   mass" with zero air speed is exactly `wind_drift`, so this is the variant that
   allows a small constant velocity relative to the air (fitted, each component
   bounded by max_air_speed): a bird, a slowly powered drifter, or a balloon whose
   assumed wind is slightly off. With max_air_speed = 0 it returns wind_drift.

Geometry
--------
Positions are computed in true geometry in the sight lines' local ENU frame
(straight sight lines, origin on the sphere under the jet's first position, as in
solve.jet / solve.los). Reported positions use the same convention as
`solve.los.points_at_range`: east and north from the tangent plane, and the third
component replaced by the height above the sphere. That "map" frame is locally
level, so a level-flying object shows zero vertical speed even 50 km away, where
the tangent plane has dropped by hundreds of feet. Constant velocity is a straight
line in true 3D geometry; over a 30 s clip that differs from a level great-circle
path by a few meters. Refraction is an option of constant_altitude only (it moves
where a ray meets an altitude shell); the other families use straight rays. The
jet's own altitude is taken as its tangent-plane z (error at most a few meters
over the few km the jet travels).

Misfit, and the quantization-aware loss
---------------------------------------
For each frame the model direction (object minus jet) is compared with the
observed sight line. Two angular residuals are formed in the readout's own axes:
d_az = model azimuth minus observed azimuth (degrees of azimuth, wrapped) and
d_el = model elevation minus observed elevation. Under the "level" convention
(solve.sensor_atflir) these are exactly the differences in the on-screen Az and El
readouts, because the jet's heading cancels.

- `misfit_deg_rms`: RMS great-circle angle between model and observed directions,
  treating each readout as an exact point. Easy to read, but it charges a model
  for disagreeing with a rounded number.
- The interval-aware loss. A readout is an integer and is refreshed on a 6-frame
  display cycle, so the true angle lies anywhere in [c - w, c + w] with w = 0.5
  deg (the "half width"), blurred by measurement noise sigma (display latency,
  boresight jitter, jet-attitude error). The likelihood of a residual d is the
  uniform interval convolved with a Gaussian:

      L(d) = [Phi((w - d) / sigma) - Phi((-w - d) / sigma)] / (2 w)

  so any d well inside +/- w costs nothing, and outside the interval the cost
  rises like ((|d| - w) / sigma)^2 / 2. Each residual is mapped to
  r = sign(d) sqrt(2 [log L(0) - log L(d)]), which is what the fits minimize
  (sum of r^2, the "deviance"). With w = 0 this is the ordinary Gaussian d / sigma.
  `misfit_excess_deg_rms` is the plain-angle summary of the same idea: the RMS of
  the part of each residual that falls outside its interval.
- Frames are not independent (one readout holds for many frames), so the deviance
  is rescaled by n_eff / n before it is read as a chi-square; `range_grid` uses
  n_eff = n / 6 by default (one independent sample per display update). A one-sigma
  range interval is then the set of grid values with
  (deviance - min deviance) * n_eff / n <= 1.

The 6-frame refresh also means a readout can lag the true angle by up to 6 frames;
that lag is not modeled as a time shift here, it is part of what sigma absorbs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar
from scipy.signal import savgol_filter
from scipy.special import log_ndtr

from . import frames as F
from .atmosphere import G0
from .los import SightLines, points_at_range

WindFn = Callable[[float, float], np.ndarray]

DEFAULT_SIGMA_DEG = 0.05


@dataclass
class Noise:
    """Readout model for the interval-aware loss.

    half_width_deg: (az, el) half widths of the readout interval, deg. 0.5 for
        whole-degree readouts; 0 treats readouts as exact points.
    sigma_deg: Gaussian measurement noise that smooths the interval edges, deg.
    """
    half_width_deg: tuple[float, float] = (0.0, 0.0)
    sigma_deg: float = DEFAULT_SIGMA_DEG


EXACT = Noise((0.0, 0.0), DEFAULT_SIGMA_DEG)
WHOLE_DEGREE = Noise((0.5, 0.5), DEFAULT_SIGMA_DEG)


@dataclass
class FamilyResult:
    family: str
    value: float                 # the family parameter (m): start range or altitude
    t: np.ndarray                # s
    pos: np.ndarray              # (n, 3) map frame: east, north (m), height above sphere (m)
    alt: np.ndarray              # m, height above sphere (= pos[:, 2])
    rng: np.ndarray              # m, slant range from the jet
    vel: np.ndarray              # (n, 3) m/s in the map frame
    speed: np.ndarray            # m/s, 3D speed in the map frame
    accel: np.ndarray            # (n, 3) m/s^2
    accel_g: np.ndarray          # |accel| / g0
    d_az: np.ndarray             # deg, model minus observed azimuth
    d_el: np.ndarray             # deg, model minus observed elevation
    misfit_deg_rms: float        # RMS great-circle angle, readouts as exact points
    misfit_excess_deg_rms: float  # RMS of residual outside the readout interval
    deviance: float              # sum of squared interval-aware residuals
    n: int                       # frames used (finite)
    params: dict = field(default_factory=dict)
    pos_on_lines: np.ndarray | None = None  # (n, 3) map frame, closest points on the sight lines


# ----------------------------------------------------------------------------
# geometry helpers


def _true_to_map(p: np.ndarray) -> np.ndarray:
    """True tangent-plane ENU points -> (east, north, height above sphere)."""
    p = np.asarray(p, float)
    h = np.sqrt(p[..., 0] ** 2 + p[..., 1] ** 2 + (F.R_EARTH + p[..., 2]) ** 2) - F.R_EARTH
    out = p.copy()
    out[..., 2] = h
    return out


def _height(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    return np.sqrt(p[..., 0] ** 2 + p[..., 1] ** 2 + (F.R_EARTH + p[..., 2]) ** 2) - F.R_EARTH


def _obs_az_el(sl: SightLines) -> tuple[np.ndarray, np.ndarray]:
    az, el = F.vector_to_az_el(sl.u)
    return np.degrees(az), np.degrees(el)


def _wrap180(x: np.ndarray) -> np.ndarray:
    return (np.asarray(x, float) + 180.0) % 360.0 - 180.0


def angular_residuals(sl: SightLines, p_true: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(d_az, d_el, great-circle angle), degrees, of model points p_true against the sight lines."""
    d = np.asarray(p_true, float) - sl.origin
    az_m, el_m = F.vector_to_az_el(d)
    az_o, el_o = _obs_az_el(sl)
    d_az = _wrap180(np.degrees(az_m) - az_o)
    d_el = np.degrees(el_m) - el_o
    w = d / np.linalg.norm(d, axis=-1, keepdims=True)
    ang = np.degrees(np.arccos(np.clip(np.sum(w * sl.u, axis=-1), -1.0, 1.0)))
    return d_az, d_el, ang


def interval_residual(d: np.ndarray, half_width: float, sigma: float) -> np.ndarray:
    """Quantization-aware residual r with r^2 = 2 [log L(0) - log L(d)] (see module docstring)."""
    d = np.asarray(d, float)
    if half_width <= 0:
        return d / sigma
    w, s = float(half_width), float(sigma)

    def log_l(a: np.ndarray) -> np.ndarray:
        hi = log_ndtr((w - a) / s)
        lo = log_ndtr((-w - a) / s)
        return hi + np.log1p(-np.exp(lo - hi))

    a = np.abs(d)
    dl = np.maximum(log_l(np.zeros(1))[0] - log_l(a), 0.0)
    return np.sign(d) * np.sqrt(2.0 * dl)


def _resid_vector(d_az: np.ndarray, d_el: np.ndarray, noise: Noise) -> np.ndarray:
    return np.concatenate([interval_residual(d_az, noise.half_width_deg[0], noise.sigma_deg),
                           interval_residual(d_el, noise.half_width_deg[1], noise.sigma_deg)])


def _excess(d: np.ndarray, w: float) -> np.ndarray:
    return np.maximum(np.abs(d) - w, 0.0)


def _kinematics(t: np.ndarray, pos_map: np.ndarray, smooth_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Velocity and acceleration by Savitzky-Golay differentiation (quadratic, window smooth_s)."""
    n = len(t)
    dt = float(np.median(np.diff(t)))
    win = int(round(smooth_s / dt)) | 1
    win = max(5, min(win, n - (1 - n % 2)))
    if n < 5:
        vel = np.gradient(pos_map, t, axis=0)
        return vel, np.gradient(vel, t, axis=0)
    vel = savgol_filter(pos_map, win, 2, deriv=1, delta=dt, axis=0, mode="interp")
    acc = savgol_filter(pos_map, win, 2, deriv=2, delta=dt, axis=0, mode="interp")
    return vel, acc


def _result(family: str, value: float, sl: SightLines, p_true: np.ndarray, noise: Noise,
            smooth_s: float, params: dict | None = None, pos_map: np.ndarray | None = None) -> FamilyResult:
    if pos_map is None:
        pos_map = _true_to_map(p_true)
    ok = np.all(np.isfinite(p_true), axis=1)
    n_all = len(sl.t)
    d_az = np.full(n_all, np.nan)
    d_el = np.full(n_all, np.nan)
    ang = np.full(n_all, np.nan)
    if ok.any():
        sub = SightLines(t=sl.t[ok], origin=sl.origin[ok], u=sl.u[ok], el=sl.el[ok], h0=sl.h0[ok])
        d_az[ok], d_el[ok], ang[ok] = angular_residuals(sub, p_true[ok])
    vel = np.full((n_all, 3), np.nan)
    acc = np.full((n_all, 3), np.nan)
    if ok.sum() >= 5 and np.all(ok):
        vel, acc = _kinematics(sl.t, pos_map, smooth_s)
    elif ok.sum() >= 5:
        vel[ok], acc[ok] = _kinematics(sl.t[ok], pos_map[ok], smooth_s)
    rng = np.linalg.norm(p_true - sl.origin, axis=1)
    hw = noise.half_width_deg
    if ok.any():
        misfit = float(np.sqrt(np.mean(ang[ok] ** 2)))
        exc = float(np.sqrt(np.mean(_excess(d_az[ok], hw[0]) ** 2 + _excess(d_el[ok], hw[1]) ** 2)))
        dev = float(np.sum(_resid_vector(d_az[ok], d_el[ok], noise) ** 2))
    else:
        misfit = exc = dev = float("nan")
    return FamilyResult(family=family, value=float(value), t=sl.t, pos=pos_map, alt=pos_map[:, 2], rng=rng,
                        vel=vel, speed=np.linalg.norm(vel, axis=1), accel=acc,
                        accel_g=np.linalg.norm(acc, axis=1) / G0, d_az=d_az, d_el=d_el,
                        misfit_deg_rms=misfit, misfit_excess_deg_rms=exc, deviance=dev, n=int(ok.sum()),
                        params=params or {})


# ----------------------------------------------------------------------------
# family 1: constant velocity (bearings-only TMA)


def _perp_basis(u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    z = np.array([0.0, 0.0, 1.0])
    e1 = np.cross(u, z)
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    e2 = np.cross(u, e1)
    return e1, e2


def _cv_linear(sl: SightLines, p0: np.ndarray, tau: np.ndarray, iters: int = 4) -> np.ndarray:
    """Pseudo-linear TMA: (p0 + v tau - o) parallel to u, weighted by 1/range, iterated."""
    e1, e2 = _perp_basis(sl.u)
    rhs_vec = sl.origin - p0
    rho = np.maximum(np.linalg.norm(rhs_vec, axis=1), 1.0)
    v = np.zeros(3)
    for _ in range(iters):
        wgt = 1.0 / rho
        A = np.concatenate([e1 * tau[:, None], e2 * tau[:, None]]) * np.concatenate([wgt, wgt])[:, None]
        b = np.concatenate([np.sum(e1 * rhs_vec, 1), np.sum(e2 * rhs_vec, 1)]) * np.concatenate([wgt, wgt])
        v = np.linalg.lstsq(A, b, rcond=None)[0]
        rho = np.maximum(np.linalg.norm(p0 + np.outer(tau, v) - sl.origin, axis=1), 1.0)
    return v


def _fib_sphere(k: int = 2000) -> np.ndarray:
    i = np.arange(k) + 0.5
    z = 1 - 2 * i / k
    phi = np.pi * (1 + 5 ** 0.5) * i
    rr = np.sqrt(1 - z * z)
    return np.stack([rr * np.cos(phi), rr * np.sin(phi), z], axis=1)


_SPHERE = _fib_sphere()


def _velocity_uncertainty(sol, v: np.ndarray, n: int, n_eff: float | None) -> dict:
    """One-sigma velocity covariance and the speed range on its ellipsoid.

    Linearized least squares: cov = s2 (J^T J)^-1 * n / n_eff, with s2 the reduced
    chi-square of the fit (so the scatter the data actually show sets the scale,
    whatever sigma was assumed) and n / n_eff inflating for frames that are not
    independent (default n_eff = n / 6). Speed bounds are the min and max of |v| over
    the one-sigma ellipsoid (min 0 if the ellipsoid contains v = 0); sigma_max is the
    largest one-sigma semi-axis (usually close to the line of sight). Only meaningful for the Gaussian loss (half width 0);
    with the interval loss the Jacobian vanishes inside the intervals and the fields
    are NaN.
    """
    nan = {"cov": np.full((3, 3), np.nan), "speed_lo": np.nan, "speed_hi": np.nan, "sigma_max": np.nan}
    J = sol.jac
    m = J.shape[0]
    if m <= 3:
        return nan
    jtj = J.T @ J
    if not np.all(np.isfinite(jtj)) or np.linalg.cond(jtj) > 1e14:
        return nan
    s2 = 2.0 * sol.cost / (m - 3)
    ne = n / 6.0 if n_eff is None else float(n_eff)
    cov = np.linalg.inv(jtj) * s2 * (n / ne)
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        return nan
    surf = v + _SPHERE @ L.T
    sp = np.linalg.norm(surf, axis=1)
    inside = float(v @ np.linalg.solve(cov, v)) <= 1.0
    return {"cov": cov, "speed_lo": 0.0 if inside else float(sp.min()), "speed_hi": float(sp.max()),
            "sigma_max": float(np.sqrt(np.linalg.eigvalsh(cov)[-1]))}


def constant_velocity(sl: SightLines, r0: float, ref: int = 0, noise: Noise = EXACT,
                      smooth_s: float = 1.0, n_eff: float | None = None) -> FamilyResult:
    """Best constant-velocity straight path starting on sight line `ref` at slant range r0 (m).

    Fits the 3D velocity by least squares on the interval-aware angular residuals
    (with Noise((0, 0), sigma) this is plain least squares on the angles). Returns the
    fitted path as `pos`, the closest points on each sight line to it as
    `pos_on_lines`, the fitted velocity (true-geometry ENU, m/s) in
    params["velocity"], and its one-sigma uncertainty (params "cov", "speed_lo",
    "speed_hi", "sigma_max"; see _velocity_uncertainty). When the observer flies
    nearly along the line of sight, the velocity component along it is barely
    constrained, so the best-fit speed can swing widely between neighboring ranges;
    read speed_lo and speed_hi, not the point value alone.
    """
    t = sl.t
    tau = t - t[ref]
    p0 = sl.origin[ref] + r0 * sl.u[ref]
    v_init = _cv_linear(sl, p0, tau)

    def fun(v: np.ndarray) -> np.ndarray:
        p = p0 + np.outer(tau, v)
        d_az, d_el, _ = angular_residuals(sl, p)
        return _resid_vector(d_az, d_el, noise)

    scale = max(np.linalg.norm(v_init), 10.0)
    sol = least_squares(fun, v_init, x_scale=scale, method="trf", xtol=1e-12, ftol=1e-12, gtol=1e-12,
                        max_nfev=200)
    v = sol.x
    p = p0 + np.outer(tau, v)
    params = {"velocity": v, "speed": float(np.linalg.norm(v)), "ref": ref, "optimizer_status": int(sol.status)}
    if max(noise.half_width_deg) > 0:
        params.update(cov=np.full((3, 3), np.nan), speed_lo=np.nan, speed_hi=np.nan, sigma_max=np.nan)
    else:
        params.update(_velocity_uncertainty(sol, v, len(t), n_eff))
    res = _result("constant_velocity", r0, sl, p, noise, smooth_s, params=params)
    along = np.sum((p - sl.origin) * sl.u, axis=1)
    res.pos_on_lines = _true_to_map(sl.origin + along[:, None] * sl.u)
    return res


# ----------------------------------------------------------------------------
# family 2: constant altitude


def constant_altitude(sl: SightLines, h: float, refraction: bool | float = False, noise: Noise = EXACT,
                      smooth_s: float = 1.0, max_range: float | None = None,
                      min_range: float = 100.0) -> FamilyResult:
    """Object where each sight line meets the altitude shell h (m).

    NaN where the ray never reaches h, or reaches it only after passing below the
    surface (blocked by the Earth), or (if max_range is given, m) beyond max_range,
    or closer than min_range (m; a shell at the jet's own altitude meets the ray at
    the jet). A downward ray can still meet a shell above the jet beyond its tangent
    point; that solution is kept unless max_range excludes it (real geometry, just far).
    """
    re = F.effective_radius(refraction)
    rng = np.empty(len(sl.t))
    for i in range(len(sl.t)):
        el = np.radians(sl.el[i])
        r = F.range_to_altitude(sl.h0[i], el, h, refraction)
        if np.isfinite(r) and el < 0:
            r_tan = -(re + sl.h0[i]) * np.sin(el)
            if r_tan < r and (re + sl.h0[i]) * np.cos(el) - re < 0:
                r = np.nan
        if np.isfinite(r) and (r < min_range or (max_range is not None and r > max_range)):
            r = np.nan
        rng[i] = r
    pos_map, _ = points_at_range(sl, np.nan_to_num(rng, nan=0.0), refraction)
    p_true = sl.origin + rng[:, None] * sl.u
    pos_map[~np.isfinite(rng)] = np.nan
    res = _result("constant_altitude", h, sl, p_true, noise, smooth_s,
                  params={"refraction": refraction, "reachable_fraction": float(np.mean(np.isfinite(rng))),
                          "max_range": max_range},
                  pos_map=pos_map)
    res.rng = rng
    # By construction the object lies on the sight lines, so the angular misfit is
    # zero; report exactly that rather than round-off.
    if res.n:
        fin = np.isfinite(rng)
        res.d_az[fin] = 0.0
        res.d_el[fin] = 0.0
        res.misfit_deg_rms = res.misfit_excess_deg_rms = res.deviance = 0.0
    return res


# ----------------------------------------------------------------------------
# families 3 and 4: carried by the wind


def _integrate_drift(t: np.ndarray, ref: int, p0: np.ndarray, wind_fn: WindFn,
                     extra_vel: np.ndarray) -> np.ndarray:
    """RK4 integration of dp/dt = wind(height(p), t) + extra_vel, forward and back from ref."""

    def f(p: np.ndarray, tt: float) -> np.ndarray:
        return np.asarray(wind_fn(float(_height(p)), float(tt)), float) + extra_vel

    n = len(t)
    p = np.empty((n, 3))
    p[ref] = p0
    for i in range(ref, n - 1):
        h = t[i + 1] - t[i]
        x, tt = p[i], t[i]
        k1 = f(x, tt)
        k2 = f(x + 0.5 * h * k1, tt + 0.5 * h)
        k3 = f(x + 0.5 * h * k2, tt + 0.5 * h)
        k4 = f(x + h * k3, tt + h)
        p[i + 1] = x + h / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
    for i in range(ref, 0, -1):
        h = t[i - 1] - t[i]
        x, tt = p[i], t[i]
        k1 = f(x, tt)
        k2 = f(x + 0.5 * h * k1, tt + 0.5 * h)
        k3 = f(x + 0.5 * h * k2, tt + 0.5 * h)
        k4 = f(x + h * k3, tt + h)
        p[i - 1] = x + h / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
    return p


def wind_drift(sl: SightLines, r0: float, wind_fn: WindFn, ref: int = 0, vertical_rate: float = 0.0,
               noise: Noise = EXACT, smooth_s: float = 1.0) -> FamilyResult:
    """Object starting on sight line `ref` at slant range r0 (m), carried by wind_fn(height_m, t).

    vertical_rate (m/s, positive up) adds a constant climb or sink, for example a
    balloon's ascent rate. Wind vectors are taken in the sight lines' ENU axes (the
    0.5 deg rotation of local east 50 km away is ignored).
    """
    p0 = sl.origin[ref] + r0 * sl.u[ref]
    p = _integrate_drift(sl.t, ref, p0, wind_fn, np.array([0.0, 0.0, vertical_rate]))
    return _result("wind_drift", r0, sl, p, noise, smooth_s,
                   params={"ref": ref, "vertical_rate": vertical_rate})


def stationary_air(sl: SightLines, r0: float, wind_fn: WindFn, ref: int = 0, max_air_speed: float = 10.0,
                   fit_vertical: bool = False, noise: Noise = EXACT, smooth_s: float = 1.0) -> FamilyResult:
    """Wind drift plus a small constant velocity relative to the air mass, fitted.

    Each horizontal component of the air velocity is bounded by max_air_speed (m/s);
    the vertical component is fitted too when fit_vertical, with the same bound.
    max_air_speed = 0 is identical to wind_drift (zero air speed: at rest in the
    moving air mass). The fitted air velocity is params["air_velocity"].
    """
    if max_air_speed <= 0:
        res = wind_drift(sl, r0, wind_fn, ref=ref, noise=noise, smooth_s=smooth_s)
        res.family = "stationary_air"
        res.params["air_velocity"] = np.zeros(3)
        return res
    p0 = sl.origin[ref] + r0 * sl.u[ref]
    k = 3 if fit_vertical else 2

    def path(x: np.ndarray) -> np.ndarray:
        ev = np.zeros(3)
        ev[:k] = x
        return _integrate_drift(sl.t, ref, p0, wind_fn, ev)

    def fun(x: np.ndarray) -> np.ndarray:
        d_az, d_el, _ = angular_residuals(sl, path(x))
        return _resid_vector(d_az, d_el, noise)

    sol = least_squares(fun, np.zeros(k), bounds=(-max_air_speed, max_air_speed), x_scale=max_air_speed,
                        diff_step=1e-3, max_nfev=60)
    ev = np.zeros(3)
    ev[:k] = sol.x
    return _result("stationary_air", r0, sl, path(sol.x), noise, smooth_s,
                   params={"ref": ref, "air_velocity": ev, "air_speed": float(np.linalg.norm(ev)),
                           "max_air_speed": max_air_speed})


# ----------------------------------------------------------------------------
# sweeps


FAMILIES = {
    "constant_velocity": constant_velocity,
    "constant_altitude": constant_altitude,
    "wind_drift": wind_drift,
    "stationary_air": stationary_air,
}

_UNIT = {"m": 1.0, "nmi": F.NMI, "ft": F.FT, "km": 1000.0}


def summarize(res: FamilyResult) -> dict:
    ok = np.isfinite(res.alt) & np.isfinite(res.speed)
    if not ok.any():
        return {"misfit_deg_rms": np.nan, "misfit_excess_deg_rms": np.nan, "deviance": np.nan,
                "mean_speed_kt": np.nan, "max_speed_kt": np.nan, "mean_alt_ft": np.nan,
                "alt_change_ft": np.nan, "max_accel_g": np.nan, "mean_range_nmi": np.nan, "n": 0}
    idx = np.flatnonzero(ok)
    return {
        "misfit_deg_rms": res.misfit_deg_rms,
        "misfit_excess_deg_rms": res.misfit_excess_deg_rms,
        "deviance": res.deviance,
        "mean_speed_kt": float(np.mean(res.speed[ok]) / F.KT),
        "max_speed_kt": float(np.max(res.speed[ok]) / F.KT),
        "mean_alt_ft": float(np.mean(res.alt[ok]) / F.FT),
        "alt_change_ft": float((res.alt[idx[-1]] - res.alt[idx[0]]) / F.FT),
        "max_accel_g": float(np.max(res.accel_g[ok])),
        "mean_range_nmi": float(np.nanmean(res.rng[ok]) / F.NMI),
        "n": int(ok.sum()),
    }


def range_grid(sl: SightLines, family: str | Callable[..., FamilyResult], values, unit: str = "m",
               n_eff: float | None = None, **kwargs) -> pd.DataFrame:
    """Run a family over a grid of parameter values; one tidy row per value.

    values are in `unit` ("m", "nmi", "ft", "km"); the `value` column keeps that
    unit and `value_m` holds SI. Columns: value, value_m, misfit_deg_rms,
    misfit_excess_deg_rms, deviance, delta_chi2_eff, within_1sigma, mean_speed_kt,
    max_speed_kt, mean_alt_ft, alt_change_ft, max_accel_g, mean_range_nmi, n, plus
    vx/vy/vz (m/s), fit_speed_kt and its one-sigma speed range speed_lo_1sigma_kt /
    speed_hi_1sigma_kt for constant_velocity, and the fitted air speed for stationary_air.

    delta_chi2_eff = (deviance - min deviance) * n_eff / n with n_eff defaulting to
    n / 6 (one independent sample per 6-frame display update); within_1sigma marks
    delta_chi2_eff <= 1. Pass n_eff explicitly to change the assumption.
    """
    fn = FAMILIES[family] if isinstance(family, str) else family
    rows = []
    if fn is constant_velocity:
        kwargs = {**kwargs, "n_eff": n_eff}
    for val in np.atleast_1d(values):
        res = fn(sl, float(val) * _UNIT[unit], **kwargs)
        row = {"value": float(val), "value_m": float(val) * _UNIT[unit]}
        row.update(summarize(res))
        if "velocity" in res.params:
            row.update(vx=res.params["velocity"][0], vy=res.params["velocity"][1], vz=res.params["velocity"][2],
                       fit_speed_kt=res.params["speed"] / F.KT,
                       speed_lo_1sigma_kt=res.params["speed_lo"] / F.KT,
                       speed_hi_1sigma_kt=res.params["speed_hi"] / F.KT,
                       vel_sigma_max_kt=res.params["sigma_max"] / F.KT)
        if "air_speed" in res.params:
            row["air_speed_kt"] = res.params["air_speed"] / F.KT
        rows.append(row)
    df = pd.DataFrame(rows)
    n = len(sl.t)
    ne = n / 6.0 if n_eff is None else float(n_eff)
    dmin = np.nanmin(df["deviance"]) if df["deviance"].notna().any() else np.nan
    df["delta_chi2_eff"] = (df["deviance"] - dmin) * ne / n
    df["within_1sigma"] = df["delta_chi2_eff"] <= 1.0
    return df


def best_value(sl: SightLines, family: str | Callable[..., FamilyResult], lo: float, hi: float,
               metric: str = "deviance", xatol: float = 1.0, **kwargs) -> tuple[float, FamilyResult]:
    """Bounded scalar minimization of a family's misfit metric over its parameter (SI units)."""
    fn = FAMILIES[family] if isinstance(family, str) else family

    def obj(x: float) -> float:
        return float(getattr(fn(sl, x, **kwargs), metric))

    r = minimize_scalar(obj, bounds=(lo, hi), method="bounded", options={"xatol": xatol})
    return float(r.x), fn(sl, float(r.x), **kwargs)
