"""ATFLIR pod geometry: pointing angles, pod roll and pitch, and the image horizon.

Two conventions for the on-screen azimuth and elevation are supported (D-005 plan,
gap "angle reference frame"):

- "level" (Sitrec's convention, ported): Az/El are world-levelled angles. El is
  measured from the local horizontal plane; Az is measured in that plane from the
  jet's direction of travel, positive to the right. Jet roll and pitch only enter
  the pod roll/pitch and the image horizon.
- "body": Az/El are measured in the jet's body frame (wing plane and fuselage axis),
  so jet bank and pitch rotate the line of sight in the world.

The functions marked "port" follow Sitrec v1 (MIT, Copyright (c) 2023-2024 Mick
West; see data/reference/sitrec/NOTICE.md), src/SphericalMath.js and
src/JetUtils.js at commit 83891bf. Sitrec's local frame is kept inside this module:
x right, y up, -z forward (three.js). All angles in this module are DEGREES at the
interface, to match the readouts and Sitrec, and radians internally.

Sign conventions at the interface:
- az: positive = right of the nose ("7° R" = +7, "54° L" = -54)
- el: positive = above the horizon
- jet_roll: positive = right wing down. GIMBAL's left bank is negative.
- jet_pitch: positive = nose up (boresight above the horizon)
"""

from __future__ import annotations

import numpy as np


def _rot(v: np.ndarray, axis: np.ndarray, deg: float) -> np.ndarray:
    """Rotate v about a unit axis by deg, right-handed (three.js applyAxisAngle)."""
    a = np.radians(deg)
    k = np.asarray(axis, float) / np.linalg.norm(axis)
    v = np.asarray(v, float)
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def _angle(u: np.ndarray, v: np.ndarray) -> float:
    c = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


X, Y, Z = np.eye(3)


def ea_to_xyz(el: float, az: float) -> np.ndarray:
    """Port of EA2XYZ: unit vector for (el, az) in the level, heading-aligned frame."""
    e, a = np.radians(el), np.radians(az)
    return np.array([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)])


def xyz_to_ea(v: np.ndarray) -> tuple[float, float]:
    """Port of XYZ2EA: returns (el, az) in degrees."""
    el = np.degrees(np.arctan2(v[1], np.hypot(v[2], v[0])))
    az = np.degrees(np.arctan2(v[0], -v[2]))
    return float(el), float(az)


def jet_axes(jet_roll: float, jet_pitch: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Jet up, right and forward unit vectors in the level heading-aligned frame (Sitrec order)."""
    up = _rot(_rot(Y, Z, -jet_roll), X, jet_pitch)
    right = _rot(_rot(X, Z, -jet_roll), X, jet_pitch)
    fwd = _rot(_rot(-Z, Z, -jet_roll), X, jet_pitch)
    return up, right, fwd


def human_horizon(jet_pitch: float, jet_roll: float, az: float, el: float) -> float:
    """Port of getHumanHorizonFromPitchRollAzEl: angle of the real horizon in the image (deg).

    This is the horizon angle a pod with ideal derotation (camera level with the
    wings) would show: the image horizon tilts by this much relative to the frame.
    """
    heading = ea_to_xyz(el, az)
    rel = _rot(_rot(heading, X, -jet_pitch), Z, jet_roll)
    _, rel_az = xyz_to_ea(rel)
    up, right, _ = jet_axes(jet_roll, jet_pitch)
    camera_horizon = _rot(right, up, -rel_az)
    real_horizon = _rot(X, Y, -az)
    ang = -_angle(camera_horizon, real_horizon)
    if np.dot(np.cross(camera_horizon, real_horizon), heading) < 0:
        return -ang
    return ang


def pod_pitch_roll(el: float, az: float, jet_pitch: float) -> tuple[float, float]:
    """Port of EAJP2PR: pod ball pitch and GLOBAL roll (pod roll + jet roll), degrees.

    Pitch is always returned positive; the mirror solution (-pitch, roll +/- 180)
    also points at the target.
    """
    v = ea_to_xyz(el, az)
    jp = np.radians(-jet_pitch)
    x = v[0]
    y = v[1] * np.cos(jp) - v[2] * np.sin(jp)
    z = v[2] * np.cos(jp) + v[1] * np.sin(jp)
    pitch = np.degrees(np.arctan2(np.hypot(x, y), -z))
    roll = np.degrees(np.arctan2(x, y)) + 180.0
    if roll > 180:
        roll -= 360
    return float(pitch), float(roll)


def pod_roll(el: float, az: float, jet_pitch: float, jet_roll: float) -> float:
    """Port of podRollFromFrame: pod roll relative to the jet, wrapped to [-180, 180)."""
    _, global_roll = pod_pitch_roll(el, az, jet_pitch)
    r = global_roll - jet_roll
    if r < -180:
        r += 360
    if r >= 180:
        r -= 360
    return r


def cue_az(el: float, az: float, jet_roll: float, jet_pitch: float) -> float:
    """Port of CueAz: the target direction projected onto the wing plane, angle from the nose."""
    heading = ea_to_xyz(el, az)
    up, _, fwd = jet_axes(jet_roll, jet_pitch)
    cue = heading - np.dot(heading, up) * up
    ang = _angle(fwd, cue)
    if np.dot(np.cross(cue, fwd), up) < 0:
        ang = -ang
    return ang


def los_level_frame(az: float, el: float, convention: str = "level",
                    jet_roll: float = 0.0, jet_pitch: float = 0.0) -> np.ndarray:
    """Line of sight in the level frame (x right, y up, -z along the jet's track).

    "level": the readout angles are already level angles.
    "body": the readout angles are in the body frame; rotate by pitch then roll.
    """
    if convention == "level":
        return ea_to_xyz(el, az)
    if convention == "body":
        up, right, fwd = jet_axes(jet_roll, jet_pitch)
        e, a = np.radians(el), np.radians(az)
        return np.cos(e) * np.cos(a) * fwd + np.cos(e) * np.sin(a) * right + np.sin(e) * up
    raise ValueError(f"unknown convention {convention!r}")


def level_to_enu(v_level: np.ndarray, heading_deg: float) -> np.ndarray:
    """Level frame (x right, y up, -z forward) to local ENU, given the track heading (deg true)."""
    h = np.radians(heading_deg)
    fwd = np.array([np.sin(h), np.cos(h), 0.0])
    right = np.array([np.cos(h), -np.sin(h), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    return v_level[0] * right + v_level[1] * up - v_level[2] * fwd


# ----------------------------------------------------------------------------- vectorized forms (M3.5)
# The scorer evaluates these on every frame of every fit, so they work on arrays. Each matches its
# scalar port above to floating-point precision (tests/test_sensor_atflir.py).


def _rot_v(v: np.ndarray, axis: np.ndarray, deg: np.ndarray) -> np.ndarray:
    """Rodrigues rotation of rows v (N, 3) about unit axes (N, 3) or (3,) by deg (N,)."""
    v = np.asarray(v, float)
    k = np.broadcast_to(np.asarray(axis, float), v.shape)
    k = k / np.linalg.norm(k, axis=-1, keepdims=True)
    a = np.radians(np.asarray(deg, float))[:, None]
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.sum(k * v, axis=-1, keepdims=True) * (1 - np.cos(a))


def ea_to_xyz_v(el, az) -> np.ndarray:
    e, a = np.radians(np.asarray(el, float)), np.radians(np.asarray(az, float))
    e, a = np.broadcast_arrays(e, a)
    return np.stack([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)], axis=-1)


def pod_pitch_roll_v(el, az, jet_pitch) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized pod_pitch_roll: ball pitch and global roll (deg) per frame."""
    v = ea_to_xyz_v(el, az)
    jp = np.radians(-np.broadcast_to(np.asarray(jet_pitch, float), v.shape[:-1]))
    x = v[..., 0]
    y = v[..., 1] * np.cos(jp) - v[..., 2] * np.sin(jp)
    z = v[..., 2] * np.cos(jp) + v[..., 1] * np.sin(jp)
    pitch = np.degrees(np.arctan2(np.hypot(x, y), -z))
    roll = np.degrees(np.arctan2(x, y)) + 180.0
    roll = np.where(roll > 180, roll - 360, roll)
    return pitch, roll


def human_horizon_v(jet_pitch, jet_roll, az, el) -> np.ndarray:
    """Vectorized human_horizon (Sitrec getHumanHorizonFromPitchRollAzEl), degrees per frame."""
    az = np.atleast_1d(np.asarray(az, float))
    n = len(az)
    el = np.broadcast_to(np.asarray(el, float), (n,))
    jp = np.broadcast_to(np.asarray(jet_pitch, float), (n,))
    jr = np.broadcast_to(np.asarray(jet_roll, float), (n,))
    heading = ea_to_xyz_v(el, az)
    rel = _rot_v(_rot_v(heading, X, -jp), Z, jr)
    rel_az = np.degrees(np.arctan2(rel[:, 0], -rel[:, 2]))
    Yn, Xn = np.tile(Y, (n, 1)), np.tile(X, (n, 1))
    up = _rot_v(_rot_v(Yn, Z, -jr), X, jp)
    right = _rot_v(_rot_v(Xn, Z, -jr), X, jp)
    cam = _rot_v(right, up, -rel_az)
    real = _rot_v(Xn, Y, -az)
    c = np.sum(cam * real, axis=-1) / (np.linalg.norm(cam, axis=-1) * np.linalg.norm(real, axis=-1))
    ang = -np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))
    flip = np.sum(np.cross(cam, real) * heading, axis=-1) < 0
    return np.where(flip, -ang, ang)


def pod_horizon_v(el, az, jet_pitch) -> np.ndarray:
    """Horizon angle (deg, CCW, image y up) in the RAW pod image, before derotation.

    The pod head rolls about the jet's forward axis until the target lies in its pitch plane
    (pod_pitch_roll: roll 0 = looking straight down), then the ball pitches toward it. The camera
    behind the ball therefore has its image x axis along the ball's pitch axis, right = d x F, with
    F the jet's forward axis (pitched up by jet_pitch, wings level: jet roll only splits the global
    roll into pod roll + jet roll and does not change the camera's attitude) and d the unit
    direction of the target projected on the plane normal to F. The world horizon direction in the
    image is h = LOS x up(world); its angle from the image x axis is the raw horizon angle.
    """
    v = ea_to_xyz_v(el, az)
    n = v.shape[0]
    F = np.tile(np.array([0.0, 0.0, -1.0]), (n, 1))
    F = _rot_v(F, X, np.broadcast_to(np.asarray(jet_pitch, float), (n,)))
    d = v - np.sum(v * F, axis=-1, keepdims=True) * F
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    r = np.cross(d, F)
    r = r / np.linalg.norm(r, axis=-1, keepdims=True)
    u = np.cross(r, v)
    h = np.cross(v, np.tile(Y, (n, 1)))
    h = h / np.linalg.norm(h, axis=-1, keepdims=True)
    return np.degrees(np.arctan2(np.sum(h * u, axis=-1), np.sum(h * r, axis=-1)))


def glare_angle_base_v(el, az, jet_pitch, jet_roll) -> np.ndarray:
    """Displayed orientation (deg, CCW, image y up) of a glare fixed in the pod optics, up to one offset.

    Sitrec's derotation model (docs/prior-work/sitrec.md, "ATFLIR pod, derotation and glare"):
    the display rotates the raw pod image so the real horizon appears at the human horizon
    (human_horizon: the horizon a camera level with the wings would show; the lab confirmed the
    cloud motion runs along it, docs/reproductions/gimbal_turn_rate.md). The derotation is
    therefore D = human_horizon - pod_horizon, and a glare fixed at angle g0 in the raw image is
    displayed at g0 + D. g0 is Sitrec's glare start angle (par.glareStartAngle): the ONE free
    offset, fitted by the scorer. The pod roll here is the ideal (geometric) roll, so the
    predicted rotation is smooth: Sitrec obtains its steps only by driving the pod roll from the
    measured glare angle (deroFromGlare), which cannot be used to test the glare reading.
    """
    return human_horizon_v(jet_pitch, jet_roll, az, el) - pod_horizon_v(el, az, jet_pitch)


def pod_roll_deadband(global_roll: np.ndarray, pod_pitch: np.ndarray, threshold_deg: float,
                      metric: str = "pointing", reflect: bool = False) -> tuple[np.ndarray, list]:
    """Pod roll that holds still until the inner steering would exceed a threshold, then jumps.

    NOT in Sitrec: the simplest controller that turns the smooth geometric roll into steps,
    used only by the M3.5 step-timing diagnostic. metric "pointing": the inner optics must absorb
    a pointing error of about sin(ball pitch) x roll error; "roll": the roll error itself. On a
    jump the roll goes to the geometric roll (reflect=False) or past it by the threshold
    (reflect=True, a bang-bang re-centring). Returns (roll per frame, frames where it jumped).
    """
    gr = np.asarray(global_roll, float)
    s = np.sin(np.radians(np.asarray(pod_pitch, float))) if metric == "pointing" else np.ones(len(gr))
    out = np.empty(len(gr))
    out[0] = gr[0]
    steps = []
    thr = float(threshold_deg)
    for i in range(1, len(gr)):
        e = (gr[i] - out[i - 1] + 180.0) % 360.0 - 180.0
        if thr > 0 and abs(s[i] * e) <= thr:
            out[i] = out[i - 1]
            continue
        out[i] = gr[i] + (np.sign(e) * thr / max(s[i], 1e-6) if reflect and thr > 0 else 0.0)
        if thr > 0:
            steps.append(i)
    return out, steps
