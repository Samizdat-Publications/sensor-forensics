from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solve import sensor_atflir as S

ROOT = Path(__file__).resolve().parents[1]
GIMBAL_CSV = ROOT / "data" / "reference" / "sitrec" / "data" / "gimbal" / "GimbalData.csv"


def sitrec_inputs(frame: int) -> tuple[float, float, float, float]:
    """Sitrec's default GIMBAL inputs at a frame (pitch, roll, az, el), rebuilt from its CSV."""
    df = pd.read_csv(GIMBAL_CSV, encoding="utf-8-sig")
    roll = -float(df.iloc[frame, 3])            # bank_angle, negated on load (left bank < 0)
    az = -float(df.iloc[frame, 5])              # gaussian_smoothed_azimuth, negated (left < 0)
    el = -2.01 + 0.025 * frame / 1031           # SitGimbal.js elStart + elRise * f / frames
    pitch = 3.6 / np.cos(np.radians(abs(roll)))  # par.jetPitch scaled by 1/cos(bank)
    return pitch, roll, az, el


def test_golden_sitrec_horizon_frame_435():
    """Sitrec's only locked GIMBAL output (test/console/gimbal.test.js:20), reproduced exactly."""
    pitch, roll, az, el = sitrec_inputs(435)
    assert S.human_horizon(pitch, roll, az, el) == pytest.approx(-28.43948837191162, abs=1e-9)


def test_ea_round_trip():
    for el, az in [(-2, -54), (0, 0), (-26, -44), (6, 3), (-36, -58)]:
        assert S.xyz_to_ea(S.ea_to_xyz(el, az)) == pytest.approx((el, az))


def test_horizon_equals_bank_straight_ahead():
    # Looking straight ahead with no pitch, the image horizon tilts by the bank angle,
    # with Sitrec's sign: a left bank (roll -30) gives a horizon angle of -30.
    assert S.human_horizon(0.0, -30.0, 0.0, 0.0) == pytest.approx(-30.0, abs=1e-9)
    assert S.human_horizon(0.0, 30.0, 0.0, 0.0) == pytest.approx(30.0, abs=1e-9)


def test_pod_pitch_roll_points_at_target():
    # Rebuild the line of sight from the pod angles (port of PRJ2XYZ logic) and compare.
    for el, az, jp in [(-2, -54, 4.0), (-2, 7, 4.0), (-26, -44, 3.0)]:
        pitch, groll = S.pod_pitch_roll(el, az, jp)
        r = np.radians(groll - 180)
        p = np.radians(pitch)
        x, y, z = np.sin(p) * np.sin(r), np.sin(p) * np.cos(r), np.cos(p)
        j = np.radians(-jp)
        za, ya = z * np.cos(j) + y * np.sin(j), y * np.cos(j) - z * np.sin(j)
        assert np.allclose([x, ya, -za], S.ea_to_xyz(el, az), atol=1e-12)


def test_pod_roll_swings_fast_near_boresight():
    # Near straight ahead the pod roll needed to follow a small az change is large:
    # the mechanism behind the GIMBAL rotation argument.
    jp = 4.0
    far = abs(S.pod_roll(-2, -30, jp, -30) - S.pod_roll(-2, -29, jp, -30))
    near = abs(S.pod_roll(-2, -1, jp, -30) - S.pod_roll(-2, 0, jp, -30))
    assert near > 5 * far


def test_conventions_agree_with_wings_level_and_no_pitch():
    for az, el in [(-54, -2), (30, -10)]:
        a = S.los_level_frame(az, el, "level")
        b = S.los_level_frame(az, el, "body", jet_roll=0.0, jet_pitch=0.0)
        assert np.allclose(a, b, atol=1e-12)


def test_conventions_differ_in_a_bank():
    a = S.los_level_frame(-30, -2, "level")
    b = S.los_level_frame(-30, -2, "body", jet_roll=-30.0, jet_pitch=4.0)
    el_b, _ = S.xyz_to_ea(b)
    assert abs(el_b - (-2)) > 5  # banking left lowers a body-frame look to the left


def test_level_to_enu_heading():
    v = S.ea_to_xyz(0, 0)  # straight along the track
    assert np.allclose(S.level_to_enu(v, 90.0), [1, 0, 0], atol=1e-12)
    assert np.allclose(S.level_to_enu(S.ea_to_xyz(0, -90), 0.0), [-1, 0, 0], atol=1e-12)
