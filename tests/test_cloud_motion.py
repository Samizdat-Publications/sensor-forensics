"""Synthetic checks of the cloud-motion forward model and turn-rate inversion (solve/cloud_motion.py)."""

import numpy as np
import pytest

from solve import cloud_motion as CM
from solve import frames as F

FPS = 30000 / 1001
H_JET = 25_000 * F.FT


def _scene(h_c_ft=11_740.0, below=0.05, refraction=False):
    return CM.CloudScene(h_jet=H_JET, h_cloud=h_c_ft * F.FT, ppd_x=1217.0, ppd_y=1223.0,
                         below_los_deg=below, refraction=refraction)


def _el_for_scene(scene, line_below=0.0):
    """LOS elevation that puts the deck horizon line_below deg below the LOS."""
    return -(CM.deck_dip_deg(scene.h_jet, scene.h_cloud, scene.refraction) - line_below)


def test_deck_geometry_consistent():
    dip = CM.deck_dip_deg(H_JET, 11_740 * F.FT)
    assert 1.9 < dip < 2.2                       # Sitrec's deck sits at the -2 deg readout
    assert CM.cloud_height_for_dip(H_JET, dip) == pytest.approx(11_740 * F.FT, abs=1e-3)
    s_t = CM.deck_horizon_distance(H_JET, 11_740 * F.FT)
    s_near = CM.ray_deck_distance(H_JET, 11_740 * F.FT, dip + 0.05)
    assert np.isnan(CM.ray_deck_distance(H_JET, 11_740 * F.FT, dip - 0.05))
    assert 150e3 < s_near < s_t < 260e3
    # refraction lowers the deck that sits on the same dip
    assert CM.cloud_height_for_dip(H_JET, dip, refraction=True) < CM.cloud_height_for_dip(H_JET, dip)


def test_pixel_projection_round_trip():
    h = np.array([0.1, -0.05, 0.0]) / FPS
    v = np.array([0.0, 0.01, -0.02]) / FPS
    th = np.array([-16.0, -30.0, 10.0])
    el = np.full(3, -2.0)
    dx, dy = CM.angular_to_pixels(h, v, th, el, 1217.0, 1223.0)
    h2, v2 = CM.pixels_to_angular(dx, dy, th, el, 1217.0, 1223.0)
    assert np.allclose(h2, h) and np.allclose(v2, v)
    # pure horizontal motion along a horizon tilted -16 deg: right and down on screen (y down)
    assert dx[0] > 0 and dy[0] > 0
    assert np.degrees(np.arctan2(-dy[0], dx[0])) == pytest.approx(-16.0, abs=0.1)


def test_straight_flight_looking_ahead_has_no_sideways_motion():
    n = 120
    t = np.arange(n) / FPS
    sc = _scene()
    hd = np.full(n, 315.0)
    v = CM.v_rel_from_heading(hd, 180.0, np.zeros(3), np.zeros(3))
    el = np.full(n, _el_for_scene(sc))
    r = CM.predict_motion(t, hd, v, np.zeros(n), el, np.zeros(n), sc)
    assert np.all(np.abs(r["h_rate"]) < 1e-6)
    assert np.all(np.abs(r["v_rate"]) < 5e-3)     # depression change of a deck point near the horizon is tiny


def test_pure_turn_without_translation_moves_clouds_at_minus_omega():
    n = 90
    t = np.arange(n) / FPS
    sc = _scene()
    omega = -2.0
    hd = CM.integrate_heading(t, np.full(n, omega), 315.0)
    v = np.zeros((n, 3))
    az = np.full(n, -30.0)
    el = np.full(n, _el_for_scene(sc))
    r = CM.predict_motion(t, hd, v, az, el, np.zeros(n), sc)
    assert np.allclose(r["h_rate"], -omega, atol=1e-6)
    # with the azimuth sweeping back at the same rate the LOS is fixed and the clouds stand still
    az2 = -30.0 - omega * t
    r2 = CM.predict_motion(t, hd, v, az2, el, np.zeros(n), sc)
    assert np.allclose(r2["h_rate"], 0.0, atol=1e-6)


@pytest.mark.parametrize("h_c_ft,refraction", [(8_000.0, False), (11_740.0, False), (18_000.0, False),
                                               (11_740.0, True)])
def test_parallax_matches_first_order_formula(h_c_ft, refraction):
    n = 60
    t = np.arange(n) / FPS
    sc = _scene(h_c_ft, below=0.04, refraction=refraction)
    hd = np.full(n, 0.0)
    v = CM.v_rel_from_heading(hd, 180.0, np.array([30.0, 0.0, 0.0]), np.array([-5.0, 3.0, 0.0]))
    az = np.full(n, -54.0)
    el = np.full(n, _el_for_scene(sc))
    r = CM.predict_motion(t, hd, v, az, el, np.zeros(n), sc)
    s = r["dist_m"]
    p = CM.parallax_rate(t, hd, v, az, s * np.cos(np.radians(el - sc.below_los_deg)))
    assert np.all(np.isfinite(s))
    assert np.allclose(r["h_rate"][1:-1], p[1:-1], rtol=2e-3)
    # sign: looking left while flying north, a fixed point drifts further left (bearing decreases),
    # so it moves left on screen
    assert np.all(r["h_rate"] < 0)
    # known cloud height: the deck distance follows from the geometry
    assert s[0] == pytest.approx(CM.ray_deck_distance(sc.h_jet, sc.h_cloud, -(el[0] - sc.below_los_deg),
                                                      refraction), rel=1e-6)


def test_inversion_recovers_turn_rate_from_forward_model():
    n = 300
    t = np.arange(n) / FPS
    sc = _scene(below=0.04)
    omega = -1.5 - 0.8 * np.sin(t / 3.0)
    hd = CM.integrate_heading(t, omega, 315.0)
    jw = np.array([61.7, 0.0, 0.0])
    cw = np.array([7.5, 4.4, 0.0])
    v = CM.v_rel_from_heading(hd, 180.0, jw, cw)
    az = -54.0 + 1.6 * t + 0.1 * t ** 2
    el = np.full(n, _el_for_scene(sc, 0.0))
    theta = -16.0 - 0.5 * t
    r = CM.predict_motion(t, hd, v, az, el, theta, sc)
    # measure it as the lab does: pixels -> horizon rate
    h_meas, _ = CM.pixels_to_angular(r["dx"], r["dy"], theta, el, sc.ppd_x, sc.ppd_y)
    h_meas = h_meas * FPS
    s_h = np.nanmean(r["dist_m"]) * np.cos(np.radians(2.0))
    inv = CM.invert_turn_rate(t, h_meas, az, 180.0, 315.0, jw, cw, s_h, daz_deg_s=1.6 + 0.2 * t)
    assert np.max(np.abs(inv["omega"][2:-2] - omega[2:-2])) < 0.01
    assert inv["heading_change_deg"] == pytest.approx(hd[-1] - hd[0], abs=0.1)
