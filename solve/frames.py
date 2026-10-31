"""Earth model and coordinate frames.

Conventions (binding for all of solve/):
- SI units internally: meters, seconds, radians. Display conversion happens only in
  units.py / the app.
- Spherical Earth, radius R_EARTH. Absolute positions of these events are not public,
  so the ellipsoid adds nothing; curvature itself matters (about 800 ft of drop at 30 nmi).
- Atmospheric refraction is modeled the standard way, as an effective Earth radius
  k * R (k = 4/3 for a standard atmosphere). It bends sight lines, so it is a
  property of the line of sight, not of positions: `effective_radius(refraction)`
  is used only when intersecting sight lines with altitude shells.
- Local frame: ENU (east, north, up) tangent at a reference point. Azimuths are
  measured clockwise from north; elevations positive up.
"""

from __future__ import annotations

import numpy as np

R_EARTH = 6_371_008.8  # mean Earth radius, m (IUGG)
K_STANDARD = 4.0 / 3.0

FT = 0.3048
NMI = 1852.0
KT = NMI / 3600.0
MPH = 1609.344 / 3600.0


def effective_radius(refraction: bool | float = False) -> float:
    """Earth radius to use for sight-line geometry. True means the standard k = 4/3."""
    if refraction is False or refraction is None:
        return R_EARTH
    k = K_STANDARD if refraction is True else float(refraction)
    return k * R_EARTH


def geodetic_to_ecef(lat: np.ndarray, lon: np.ndarray, h: np.ndarray, radius: float = R_EARTH) -> np.ndarray:
    lat, lon, h = np.broadcast_arrays(np.asarray(lat, float), np.asarray(lon, float), np.asarray(h, float))
    r = radius + h
    return np.stack([r * np.cos(lat) * np.cos(lon), r * np.cos(lat) * np.sin(lon), r * np.sin(lat)], axis=-1)


def ecef_to_geodetic(p: np.ndarray, radius: float = R_EARTH) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = np.asarray(p, float)
    r = np.linalg.norm(p, axis=-1)
    lat = np.arcsin(p[..., 2] / r)
    lon = np.arctan2(p[..., 1], p[..., 0])
    return lat, lon, r - radius


def enu_basis(lat: float, lon: float) -> np.ndarray:
    """Rows are the ECEF unit vectors of east, north, up at (lat, lon)."""
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    return np.array([[-so, co, 0.0],
                     [-sl * co, -sl * so, cl],
                     [cl * co, cl * so, sl]])


class LocalFrame:
    """ENU tangent frame at a reference point on the sphere (altitude 0)."""

    def __init__(self, lat0: float = 0.0, lon0: float = 0.0, radius: float = R_EARTH):
        self.lat0, self.lon0, self.radius = lat0, lon0, radius
        self.B = enu_basis(lat0, lon0)
        self.origin = geodetic_to_ecef(lat0, lon0, 0.0, radius)

    def to_ecef(self, enu: np.ndarray) -> np.ndarray:
        return self.origin + np.asarray(enu, float) @ self.B

    def from_ecef(self, p: np.ndarray) -> np.ndarray:
        return (np.asarray(p, float) - self.origin) @ self.B.T

    def altitude(self, enu: np.ndarray) -> np.ndarray:
        """Height above the sphere of local-frame points (true geometry, no refraction)."""
        p = self.to_ecef(enu)
        return np.linalg.norm(p, axis=-1) - self.radius

    def local_up(self, enu: np.ndarray) -> np.ndarray:
        """Unit 'up' (radial) vector, in this frame's ENU axes, at local-frame points."""
        p = self.to_ecef(enu)
        u = p / np.linalg.norm(p, axis=-1, keepdims=True)
        return u @ self.B.T


def az_el_to_vector(az: np.ndarray, el: np.ndarray) -> np.ndarray:
    """Unit vector in a local ENU frame. az clockwise from north, el up from horizontal."""
    az, el = np.broadcast_arrays(np.asarray(az, float), np.asarray(el, float))
    ce = np.cos(el)
    return np.stack([ce * np.sin(az), ce * np.cos(az), np.sin(el)], axis=-1)


def vector_to_az_el(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    v = np.asarray(v, float)
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.arctan2(v[..., 0], v[..., 1]), np.arcsin(np.clip(v[..., 2], -1.0, 1.0))


def local_level_basis(frame: LocalFrame, p_enu: np.ndarray) -> np.ndarray:
    """ENU axes of the tangent plane at points p (rows: east, north, up), in frame axes.

    Needed because 'level' at an object 30 nmi away is tilted relative to 'level'
    at the jet. Shape (..., 3, 3).
    """
    up = frame.local_up(p_enu)
    z = np.array([0.0, 0.0, 1.0])
    # Frame north pole direction in ENU axes = the ECEF z axis expressed in frame axes.
    pole = frame.B @ z
    east = np.cross(pole, up)
    east /= np.linalg.norm(east, axis=-1, keepdims=True)
    north = np.cross(up, east)
    return np.stack([east, north, up], axis=-2)


def sight_line_at_range(p0: np.ndarray, u: np.ndarray, rng: np.ndarray) -> np.ndarray:
    """Points along straight sight lines: p0 + rng * u. Straight in true geometry.

    Refraction is handled by the caller through `altitude_along_sight_line`, which uses
    the effective radius; positions themselves stay in true geometry.
    """
    return np.asarray(p0, float) + np.asarray(rng, float)[..., None] * np.asarray(u, float)


def altitude_along_sight_line(h0: float, el: float, rng: np.ndarray, refraction: bool | float = False) -> np.ndarray:
    """Height of a point at slant range `rng` along a ray leaving height h0 at elevation el.

    Uses the law of cosines on a sphere of effective radius; exact, not the flat or
    d^2 / 2R approximations.
    """
    re = effective_radius(refraction)
    r0 = re + h0
    rng = np.asarray(rng, float)
    r = np.sqrt(r0 ** 2 + rng ** 2 + 2.0 * r0 * rng * np.sin(el))
    return r - re


def range_to_altitude(h0: float, el: float, h_target: float, refraction: bool | float = False) -> float:
    """Slant range along a ray from height h0 at elevation el to height h_target.

    Returns the nearest positive solution, or nan if the ray never reaches h_target.
    """
    re = effective_radius(refraction)
    r0, rt = re + h0, re + h_target
    b = 2.0 * r0 * np.sin(el)
    c = r0 ** 2 - rt ** 2
    disc = b * b - 4.0 * c
    if disc < 0:
        return float("nan")
    roots = [(-b - np.sqrt(disc)) / 2.0, (-b + np.sqrt(disc)) / 2.0]
    pos = [x for x in roots if x > 0]
    return float(min(pos)) if pos else float("nan")


def horizon_dip(h: float, refraction: bool | float = False) -> float:
    """Angle of the geometric horizon below horizontal from height h (radians, positive)."""
    re = effective_radius(refraction)
    return float(np.arccos(re / (re + h)))
