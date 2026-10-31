import numpy as np
import pytest

from solve import jet as J
from solve.frames import KT


def test_wind_from_direction():
    w = J.wind_from(270.0, 10.0)  # westerly blows toward the east
    assert np.allclose(w, [10.0, 0.0, 0.0], atol=1e-12)


def test_straight_flight_no_wind():
    t = np.arange(0, 10.01, 0.1)
    tr = J.integrate(t, 200.0, 0.0, 90.0)
    assert np.allclose(tr.ground_pos[-1, :2], [2000.0, 0.0], atol=1e-9)
    assert np.allclose(tr.heading, 90.0)


def test_constant_bank_traces_a_circle_of_the_right_radius():
    tas, bank = 180.0, 30.0
    rate = np.degrees(9.80665 * np.tan(np.radians(bank)) / tas)
    period = 360.0 / rate
    t = np.linspace(0, period, 20001)
    tr = J.integrate(t, tas, bank, 0.0)
    radius = tas ** 2 / (9.80665 * np.tan(np.radians(bank)))
    # Full circle returns to the start; the farthest point is one diameter away.
    assert np.linalg.norm(tr.air_pos[-1, :2]) == pytest.approx(0.0, abs=0.5)
    assert np.max(np.linalg.norm(tr.air_pos[:, :2], axis=1)) == pytest.approx(2 * radius, rel=1e-4)
    # Positive bank turns right (clockwise): heading increases, first move is east of north-going start.
    assert tr.heading[100] > 0 and tr.air_pos[2000, 0] > 0


def test_left_bank_turns_left_and_wind_adds_drift():
    t = np.linspace(0, 34.4, 1031)
    wind = J.wind_from(270.0, 120 * KT)
    tr = J.integrate(t, 355 * KT, -30.0, 315.0, wind_enu=wind)
    assert tr.heading[-1] < 315.0  # heading decreased: a left turn
    drift = tr.ground_pos[-1] - tr.air_pos[-1]
    assert drift[0] == pytest.approx(120 * KT * 34.4, rel=1e-9) and drift[1] == pytest.approx(0.0, abs=1e-6)


def test_turn_rate_override():
    t = np.linspace(0, 10, 101)
    tr = J.integrate(t, 180.0, 30.0, 0.0, turn_rate_deg_s=-1.0)
    assert tr.heading[-1] == pytest.approx(350.0)
