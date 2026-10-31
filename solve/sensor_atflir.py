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
