"""Synthetic tests for solve.families (M2.6).

The observer is GIMBAL-like: 25,000 ft, 355 kt TAS, 34.4 s at 29.97 fps. A
turning observer banks 30 deg left (about 50 deg of heading change); a straight
observer holds its heading. Sight lines are built from the true object path and
passed through the same readout pipeline the real data uses (level-convention
Az/El relative to the jet's heading, then solve.los.sight_lines).
"""

import numpy as np
import pytest

from solve import families as FM
from solve import frames as F
from solve.jet import integrate, wind_from
from solve.los import points_at_range, sight_lines

FPS = 30000 / 1001
N = 1031
T = np.arange(N) / FPS
H_JET = 25_000 * F.FT


def _track(bank: float):
    return integrate(T, 355 * F.KT, bank, 315.0, wind_enu=wind_from(270, 60 * F.KT), altitude=H_JET)


def _readouts(track, p_true: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    d = p_true - track.ground_pos
    az, el = F.vector_to_az_el(d)
    az_read = FM._wrap180(np.degrees(az) - track.heading)
    return az_read, np.degrees(el)


def _sl(track, az, el):
    return sight_lines(track, az, el, "level")


R0 = 10 * F.NMI
V_TRUE = np.array([-120.0, 90.0, -2.0])  # m/s, about 292 kt, slowly descending


def _cv_case(bank: float, quantize: bool = False):
    tr = _track(bank)
    u0 = F.az_el_to_vector(np.radians(315.0 - 40.0), np.radians(-2.0))
    p0 = tr.ground_pos[0] + R0 * u0
    p = p0 + np.outer(T, V_TRUE)
    az, el = _readouts(tr, p)
    if quantize:
        az, el = np.round(az), np.round(el)
    return _sl(tr, az, el), tr


def _range_curve(sl, noise, values_nmi):
    return FM.range_grid(sl, "constant_velocity", values_nmi, unit="nmi", noise=noise)


def test_a_constant_velocity_recovered_from_a_turning_jet():
    sl, _ = _cv_case(-30.0)
    grid = np.arange(4.0, 25.01, 0.5)
    df = _range_curve(sl, FM.EXACT, grid)
    i = int(np.argmin(df["misfit_deg_rms"]))
    assert abs(df["value"][i] - 10.0) <= 0.5
    # The curve is not flat: wrong ranges are rejected by a wide margin.
    assert df["misfit_deg_rms"].iloc[[0, -1]].min() > 50 * df["misfit_deg_rms"][i]
    r_best, res = FM.best_value(sl, "constant_velocity", 8 * F.NMI, 12 * F.NMI, metric="misfit_deg_rms",
                                noise=FM.EXACT)
    assert r_best == pytest.approx(R0, rel=0.02)
    v = res.params["velocity"]
    assert np.linalg.norm(v - V_TRUE) <= 0.02 * np.linalg.norm(V_TRUE)
    assert res.misfit_deg_rms < 1e-3


def test_b_whole_degree_quantization_broadens_the_minimum_but_keeps_the_truth():
    """Criterion: the one-sigma region is {r0 : (D(r0) - D_min) * n_eff / n <= 1}, where D is the
    interval-aware deviance (half width 0.5 deg, sigma 0.05 deg) and n_eff = n / 6 (one independent
    sample per display update). The true r0 must lie inside it, and the region must be wider than the
    same criterion gives for the noise-free sight lines."""
    grid = np.arange(4.0, 25.01, 0.25)
    sl_q, _ = _cv_case(-30.0, quantize=True)
    df_q = _range_curve(sl_q, FM.WHOLE_DEGREE, grid)
    sl_x, _ = _cv_case(-30.0)
    df_x = _range_curve(sl_x, FM.EXACT, grid)
    in_q = df_q[df_q["within_1sigma"]]["value"]
    in_x = df_x[df_x["within_1sigma"]]["value"]
    assert in_q.min() <= 10.0 <= in_q.max()
    assert (in_q.max() - in_q.min()) > (in_x.max() - in_x.min())
    # Plain RMS misfit treating rounded readouts as exact is also broader and shallower.
    assert df_q["misfit_deg_rms"].min() > df_x["misfit_deg_rms"].min()


def test_c_straight_observer_cannot_see_constant_velocity_range():
    sl, tr = _cv_case(0.0)
    df = _range_curve(sl, FM.EXACT, np.arange(2.0, 40.01, 2.0))
    # Every range fits (scaling symmetry): the misfit curve is flat at round-off level.
    assert df["misfit_deg_rms"].max() < 1e-3
    # ...while the implied motion relative to the jet scales with the assumed range:
    # p(t) = o(t) + k (p_true(t) - o(t)) with k = r0 / r_true.
    v_rel = df[["vx", "vy", "vz"]].to_numpy() - tr.ground_vel[0]
    ratio = np.linalg.norm(v_rel, axis=1) / np.linalg.norm(V_TRUE - tr.ground_vel[0])
    assert np.allclose(ratio, df["value"] / 10.0, rtol=1e-3)


def _shear_wind(h: float, t: float) -> np.ndarray:
    """Wind that turns and strengthens with height, so drift depends on altitude."""
    km = h / 1000.0
    spd = 8.0 + 4.0 * km                     # m/s
    to = np.radians(60.0 + 15.0 * km)        # direction the air moves toward
    return np.array([spd * np.sin(to), spd * np.cos(to), 0.0])


def test_d_wind_drifting_balloon_recovered_at_true_range_and_rejected_elsewhere():
    from scipy.integrate import solve_ivp

    tr = _track(-30.0)
    u0 = F.az_el_to_vector(np.radians(315.0 - 30.0), np.radians(-3.0))
    r_true = 12 * F.NMI
    p0 = tr.ground_pos[0] + r_true * u0

    def rhs(tt, p):
        return _shear_wind(float(FM._height(p)), tt)

    sol = solve_ivp(rhs, (T[0], T[-1]), p0, t_eval=T, rtol=1e-10, atol=1e-6)
    p = sol.y.T
    az, el = _readouts(tr, p)
    sl = _sl(tr, az, el)
    at_truth = FM.wind_drift(sl, r_true, _shear_wind)
    assert at_truth.misfit_deg_rms < 1e-3
    for k in (0.7, 1.4):
        wrong = FM.wind_drift(sl, k * r_true, _shear_wind)
        assert wrong.misfit_deg_rms > 0.1
        assert wrong.misfit_deg_rms > 100 * at_truth.misfit_deg_rms
    r_best, _ = FM.best_value(sl, "wind_drift", 6 * F.NMI, 20 * F.NMI, metric="misfit_deg_rms",
                              wind_fn=_shear_wind)
    assert r_best == pytest.approx(r_true, rel=0.01)
    # stationary_air with zero allowed air speed is exactly wind_drift.
    same = FM.stationary_air(sl, r_true, _shear_wind, max_air_speed=0.0)
    assert same.misfit_deg_rms == pytest.approx(at_truth.misfit_deg_rms, abs=1e-12)


@pytest.mark.parametrize("refraction", [False, True])
def test_e_constant_altitude_round_trips_with_points_at_range(refraction):
    sl, _ = _cv_case(-30.0)
    h = 18_000 * F.FT
    res = FM.constant_altitude(sl, h, refraction=refraction)
    assert np.all(np.isfinite(res.rng))
    pos, alt = points_at_range(sl, res.rng, refraction)
    assert np.allclose(alt, h, atol=1e-3)
    assert np.allclose(pos, res.pos, atol=1e-6)
    assert np.allclose(res.alt, h, atol=1e-3)
    assert res.misfit_deg_rms == 0.0
    # Above the jet, a ray 2 deg down only gets there beyond its tangent point (far away)...
    high = FM.constant_altitude(sl, 30_000 * F.FT, refraction=refraction)
    assert np.nanmin(high.rng) > 100 * F.NMI
    # ...and a ray steep enough to hit the ground first never gets there at all.
    steep = sight_lines(_track(-30.0), np.zeros(N), np.full(N, -5.0), "level")
    blocked = FM.constant_altitude(steep, 30_000 * F.FT, refraction=refraction)
    assert blocked.n == 0 and np.isnan(blocked.misfit_deg_rms)


def test_interval_residual_is_free_inside_and_gaussian_outside():
    w, s = 0.5, 0.05
    r = FM.interval_residual(np.array([0.0, 0.2, -0.3, 0.8, -1.5]), w, s)
    assert np.allclose(r[:2], 0.0, atol=1e-4) and abs(r[2]) < 0.01
    # Outside the interval it grows like (|d| - w) / sigma, up to a slowly varying log term.
    assert r[3] == pytest.approx((0.8 - w) / s, rel=0.1) and r[4] < 0
    assert np.allclose(FM.interval_residual(np.array([0.1, -0.2]), 0.0, s), [2.0, -4.0])
