import numpy as np
import pytest

from solve import frames as F


def test_ecef_round_trip():
    lat, lon, h = np.radians(30.3), np.radians(-81.4), 7620.0
    p = F.geodetic_to_ecef(lat, lon, h)
    lat2, lon2, h2 = F.ecef_to_geodetic(p)
    assert np.allclose([lat2, lon2, h2], [lat, lon, h], atol=1e-9)


def test_local_frame_round_trip_and_altitude():
    fr = F.LocalFrame(np.radians(30), np.radians(-80))
    enu = np.array([[1000.0, -2000.0, 7620.0], [55_560.0, 0.0, 0.0]])
    assert np.allclose(fr.from_ecef(fr.to_ecef(enu)), enu, atol=1e-6)
    alt = fr.altitude(enu)
    assert alt[0] == pytest.approx(7620.0 + (1000**2 + 2000**2) / (2 * F.R_EARTH), abs=0.01)
    # A point 30 nmi out on the tangent plane is about 795 ft above the sphere.
    assert alt[1] / F.FT == pytest.approx(795, abs=3)


def test_az_el_vector_round_trip():
    az = np.radians([0, 45, 170, -90])
    el = np.radians([0, -2, 10, -26])
    a2, e2 = F.vector_to_az_el(F.az_el_to_vector(az, el))
    assert np.allclose(a2, az) and np.allclose(e2, el)


def test_altitude_along_sight_line_matches_frame_geometry():
    fr = F.LocalFrame()
    h0, el = 7620.0, np.radians(-2.0)
    u = F.az_el_to_vector(np.radians(30), el)
    for rng in (5 * F.NMI, 30 * F.NMI):
        p = np.array([0, 0, h0]) + rng * u
        assert F.altitude_along_sight_line(h0, el, rng) == pytest.approx(fr.altitude(p), abs=1e-3)


def test_range_to_altitude_inverts():
    h0, el = 7620.0, np.radians(-26.0)
    for refr in (False, True):
        r = F.range_to_altitude(h0, el, 4000.0, refr)
        assert F.altitude_along_sight_line(h0, el, r, refr) == pytest.approx(4000.0, abs=1e-6)
    assert np.isnan(F.range_to_altitude(1000.0, np.radians(10), 0.0))


def test_refraction_bends_sight_lines_down():
    # A refracted ray curves toward the Earth, so at a fixed apparent elevation the
    # point at 30 nmi sits lower, by a quarter of the curvature drop (k = 4/3).
    h0, el, rng = 7620.0, np.radians(-2.0), 30 * F.NMI
    drop = F.altitude_along_sight_line(h0, el, rng, False) - F.altitude_along_sight_line(h0, el, rng, True)
    assert drop / F.FT == pytest.approx(795 / 4, rel=0.03)


def test_horizon_dip_25000ft():
    # Geometric dip from 25,000 ft is about 2.8 degrees.
    assert np.degrees(F.horizon_dip(25000 * F.FT)) == pytest.approx(2.80, abs=0.03)


def test_local_level_basis_is_orthonormal_and_tilts():
    fr = F.LocalFrame(np.radians(30), 0.0)
    pts = np.array([[0.0, 0.0, 0.0], [0.0, 55_560.0, 0.0]])
    B = F.local_level_basis(fr, pts)
    for b in B:
        assert np.allclose(b @ b.T, np.eye(3), atol=1e-12)
    assert np.allclose(B[0], np.eye(3), atol=1e-12)
    tilt = np.degrees(np.arccos(B[1][2] @ np.array([0, 0, 1.0])))
    assert tilt == pytest.approx(np.degrees(55_560.0 / F.R_EARTH), abs=1e-3)
