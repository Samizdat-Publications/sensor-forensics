"""Shared geometry for the M3 physical models.

Frame: the local tangent plane ENU at the jet's first position (x east, y north),
with the Earth's center at (0, 0, -R). Heights are measured along the radius
(exact sphere, no refraction), so a constant-altitude path stays on its altitude
shell. Angles at the jet use the jet's own local vertical and north, a refinement
of solve.los.sight_lines (which uses the frame's fixed z-up; the difference is the
tilt of the vertical over the jet's few km of travel, about 0.04 deg).

Pod angles follow solve.sensor_atflir's "level" convention (Sitrec): az from the
nose (air heading), positive right, in the local horizontal plane; el from the
local horizontal, positive up.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import frames as F
from ..atmosphere import G0
from ..sensor_atflir import los_level_frame

R = F.R_EARTH
CENTER = np.array([0.0, 0.0, -R])


def z_on_shell(xy: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Tangent-frame z of points with horizontal coordinates xy (..., 2) at height h above the sphere."""
    r2 = (R + np.asarray(h, float)) ** 2 - np.sum(np.asarray(xy, float) ** 2, axis=-1)
    return np.sqrt(r2) - R


def height_of(p: np.ndarray) -> np.ndarray:
    return np.linalg.norm(np.asarray(p, float) - CENTER, axis=-1) - R


def local_basis(p: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """East, north, up unit vectors at points p (..., 3): up radial, north = projection of +y."""
    up = np.asarray(p, float) - CENTER
    up = up / np.linalg.norm(up, axis=-1, keepdims=True)
    y = np.array([0.0, 1.0, 0.0])
    north = y - (up @ y)[..., None] * up
    north = north / np.linalg.norm(north, axis=-1, keepdims=True)
    east = np.cross(north, up)
    return east, north, up


def wrap180(a: np.ndarray) -> np.ndarray:
    return (np.asarray(a, float) + 180.0) % 360.0 - 180.0


@dataclass
class JetState:
    t: np.ndarray
    pos: np.ndarray        # (N, 3) tangent frame, on the altitude shell
    vel: np.ndarray        # (N, 3)
    heading: np.ndarray    # deg true (air heading = nose)
    east: np.ndarray
    north: np.ndarray
    up: np.ndarray
    wind: np.ndarray       # (2,) wind at the jet, m/s


class JetModel:
    """Coordinated-turn jet track with the starting heading as a free (nuisance) parameter.

    The air track is integrated once for heading 0 (solve.jet's trapezoidal rule) and
    rotated for each heading, so the fit can vary the heading cheaply.
    """

    def __init__(self, t: np.ndarray, tas: np.ndarray, bank_deg: np.ndarray, alt_m: np.ndarray):
        self.t = np.asarray(t, float)
        tas = np.asarray(tas, float)
        rate = np.degrees(G0 * np.tan(np.radians(bank_deg)) / tas)
        dt = np.diff(self.t)
        hr = np.zeros(len(self.t))
        hr[1:] = np.cumsum(0.5 * (rate[1:] + rate[:-1]) * dt)
        self.heading_rel = hr
        h = np.radians(hr)
        v0 = np.stack([tas * np.sin(h), tas * np.cos(h)], axis=-1)
        p0 = np.zeros((len(self.t), 2))
        p0[1:] = np.cumsum(0.5 * (v0[1:] + v0[:-1]) * dt[:, None], axis=0)
        self.air_pos0 = p0
        self.air_vel0 = v0
        self.alt = np.asarray(alt_m, float)

    def state(self, heading0_deg: float, wind_xy: np.ndarray) -> JetState:
        H = np.radians(heading0_deg)
        c, s = np.cos(H), np.sin(H)
        rot = np.array([[c, s], [-s, c]])  # rotates bearings clockwise by H
        xy = self.air_pos0 @ rot.T + np.outer(self.t - self.t[0], wind_xy)
        vxy = self.air_vel0 @ rot.T + wind_xy
        z = z_on_shell(xy, self.alt)
        pos = np.column_stack([xy, z])
        vz = np.gradient(z, self.t)
        vel = np.column_stack([vxy, vz])
        e, n, u = local_basis(pos)
        return JetState(self.t, pos, vel, (heading0_deg + self.heading_rel) % 360.0, e, n, u, np.asarray(wind_xy, float))


def los_enu(jet: JetState, i: int, az_deg: float, el_deg: float, bank_deg: float = 0.0,
            pitch_deg: float = 0.0, convention: str = "level") -> np.ndarray:
    """Unit line of sight (tangent frame) at frame i from pod angles."""
    v = los_level_frame(az_deg, el_deg, convention, jet_roll=bank_deg, jet_pitch=pitch_deg)
    h = np.radians(jet.heading[i])
    fwd = np.sin(h) * jet.east[i] + np.cos(h) * jet.north[i]
    right = np.cos(h) * jet.east[i] - np.sin(h) * jet.north[i]
    u = v[0] * right + v[1] * jet.up[i] - v[2] * fwd
    return u / np.linalg.norm(u)


def range_to_height(p0: np.ndarray, u: np.ndarray, h: float) -> float:
    """Nearest positive distance along unit ray u from p0 to height h; nan if never reached."""
    d = np.asarray(p0, float) - CENTER
    b = float(np.dot(u, d))
    c = float(np.dot(d, d) - (R + h) ** 2)
    disc = b * b - c
    if disc < 0:
        return float("nan")
    sq = np.sqrt(disc)
    for r in sorted((-b - sq, -b + sq)):
        if r > 0:
            return float(r)
    return float("nan")


def angles_from(jet: JetState, rel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pod az (deg, from the nose), el (deg) and slant range (m) of relative vectors rel (N, 3)."""
    rng = np.linalg.norm(rel, axis=-1)
    el = np.degrees(np.arcsin(np.clip(np.sum(rel * jet.up, axis=-1) / rng, -1, 1)))
    brg = np.degrees(np.arctan2(np.sum(rel * jet.east, axis=-1), np.sum(rel * jet.north, axis=-1)))
    return wrap180(brg - jet.heading), el, rng


def sea_range(p: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Slant distance from points p (N, 3) along unit rays u (N, 3) to sea level; nan if the ray misses."""
    d = p - CENTER
    b = np.sum(u * d, axis=-1)
    c = np.sum(d * d, axis=-1) - R ** 2
    disc = b * b - c
    with np.errstate(invalid="ignore"):
        r = -b - np.sqrt(disc)
    return np.where((disc >= 0) & (r > 0), r, np.nan)
