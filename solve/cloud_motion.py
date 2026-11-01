"""Background (cloud-deck) motion in the pod image: forward model and turn-rate inversion (M2.5).

Physical picture. The pod tracks the object, so the line of sight (LOS) is set by the
azimuth and elevation readouts. Behind the object, slightly below the line of sight,
lies the top of a cloud deck at height h_c. A cloud point P is fixed in the cloud air
mass. Between two frames P moves across the image because

1. the LOS turns in the world: its bearing is heading + az (az measured from the nose,
   in the levelled frame, Sitrec's "level" convention), so its bearing rate is
   omega + daz/dt, with omega the jet's heading rate (the turn rate);
2. the jet translates relative to the cloud air mass (velocity v_rel = TAS along the
   heading + wind at the jet - wind at the cloud deck), so the bearing of P changes by
   parallax: p = d(bearing of P)/dt = -(v_rel . e_right) / s_h, with e_right the
   horizontal unit vector to the right of the bearing to P and s_h its horizontal
   distance (bearing measured clockwise from north);
3. the LOS elevation changes and the depression of P changes (both tiny here).

To first order the content moves along the image horizon at

    h = -(omega + daz/dt) + p                                  (deg/s, + = content moves right)

and the image horizon makes the angle theta with the image x axis (counter-clockwise
positive, image y up), theta = sensor_atflir.human_horizon(pitch, roll, az, el) for an
ideally derotated pod. In pixels (our copies, x right, y down) the content motion is
(dx, dy) = (ppd_x * X, -ppd_y * Y) per frame, with (X, Y) = R(theta) (h cos(el), v) / fps.

Inversion: omega = -h - daz/dt + p. The cloud measurement fixes the LOS bearing rate
relative to the clouds; the azimuth readout and the parallax term turn it into a turn
rate. Note the sizes for GIMBAL: omega is about -2 deg/s and daz/dt about +1.8 deg/s,
while h is only 0.02 to 0.17 deg/s and p 0 to 0.05 deg/s.

Cloud distance. The deck top seen near the LOS lies near the deck horizon (the tangent
point of the sphere R_eff + h_c seen from R_eff + h_jet), at slant distance about
R_eff * dip, 150 to 300 km for GIMBAL. Points a little below the deck horizon in the image
are nearer (ray_deck_distance). Refraction is an option through an effective Earth
radius (solve.frames.effective_radius).

Geometry here: a local tangent-plane ENU frame (x east, y north, z up) at the jet's first
position, with the Earth's center at (0, 0, -R_eff); "up" at any point is the radial
direction. Angles are DEGREES at the interface, distances in m, velocities in m/s.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import frames as F


# ----------------------------------------------------------------------------- deck geometry

def deck_dip_deg(h_jet: float, h_cloud: float, refraction: bool | float = False) -> float:
    """Depression of the deck horizon (tangent to the sphere R + h_cloud) seen from R + h_jet."""
    R = F.effective_radius(refraction)
    return float(np.degrees(np.arccos((R + h_cloud) / (R + h_jet))))


def deck_horizon_distance(h_jet: float, h_cloud: float, refraction: bool | float = False) -> float:
    """Slant distance (m) from the jet to the deck horizon (tangent point)."""
    R = F.effective_radius(refraction)
    return float(np.sqrt((R + h_jet) ** 2 - (R + h_cloud) ** 2))


def cloud_height_for_dip(h_jet: float, dip_deg: float, refraction: bool | float = False) -> float:
    """Deck height (m) whose horizon is seen at depression dip_deg from h_jet."""
    R = F.effective_radius(refraction)
    return float((R + h_jet) * np.cos(np.radians(dip_deg)) - R)


def ray_deck_distance(h_jet: float, h_cloud: float, depression_deg: float,
                      refraction: bool | float = False) -> float:
    """Slant distance (m) along a ray at the given depression to its first deck crossing; nan if it misses."""
    R = F.effective_radius(refraction)
    a = R + h_jet
    sd = np.sin(np.radians(depression_deg))
    disc = (a * sd) ** 2 - (a ** 2 - (R + h_cloud) ** 2)
    if disc < 0 or sd <= 0:
        return float("nan")
    return float(a * sd - np.sqrt(disc))


# ----------------------------------------------------------------------------- vector helpers

def _up(p: np.ndarray, R: float) -> np.ndarray:
    c = np.asarray(p, float) + np.array([0.0, 0.0, R])
    return c / np.linalg.norm(c)


def _horizontal_basis(p: np.ndarray, R: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Local east, north, up at point p (north = projection of the frame's +y)."""
    u = _up(p, R)
    n = np.array([0.0, 1.0, 0.0]) - u[1] * u
    n /= np.linalg.norm(n)
    e = np.cross(n, u)
    return e, n, u


def direction(p: np.ndarray, bearing_deg: float, elevation_deg: float, R: float) -> np.ndarray:
    """Unit vector at p with the given bearing (clockwise from north) and elevation."""
    e, n, u = _horizontal_basis(p, R)
    b, el = np.radians(bearing_deg), np.radians(elevation_deg)
    return np.cos(el) * (np.sin(b) * e + np.cos(b) * n) + np.sin(el) * u


def bearing_elevation(p_from: np.ndarray, p_to: np.ndarray, R: float) -> tuple[float, float, float]:
    """Bearing (deg, clockwise from north), elevation (deg) and slant distance (m) from p_from to p_to."""
    e, n, u = _horizontal_basis(p_from, R)
    r = np.asarray(p_to, float) - np.asarray(p_from, float)
    d = float(np.linalg.norm(r))
    b = float(np.degrees(np.arctan2(np.dot(r, e), np.dot(r, n))))
    el = float(np.degrees(np.arcsin(np.clip(np.dot(r, u) / d, -1, 1))))
    return b, el, d


def ray_sphere(p: np.ndarray, d: np.ndarray, radius: float, R: float) -> float:
    """Distance along unit ray d from p to the first crossing of the sphere |x - center| = radius; nan if none."""
    c = np.array([0.0, 0.0, -R])
    oc = np.asarray(p, float) - c
    b = float(np.dot(d, oc))
    disc = b * b - (float(np.dot(oc, oc)) - radius * radius)
    if disc < 0:
        return float("nan")
    s = -b - np.sqrt(disc)
    return float(s) if s > 0 else float("nan")


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


# ----------------------------------------------------------------------------- scene and image projection

@dataclass
class CloudScene:
    """Fixed parameters of the background model."""
    h_jet: float                 # m, jet altitude
    h_cloud: float               # m, deck-top height
    ppd_x: float                 # image px per degree along our frames' x
    ppd_y: float                 # image px per degree along our frames' y
    below_los_deg: float = 0.0   # depression of the tracked cloud texture below the LOS
    right_of_los_deg: float = 0.0  # horizontal offset of the tracked texture from the LOS
    refraction: bool | float = False


def angular_to_pixels(h_deg: np.ndarray, v_deg: np.ndarray, theta_deg: np.ndarray, el_deg: np.ndarray,
                      ppd_x: float, ppd_y: float) -> tuple[np.ndarray, np.ndarray]:
    """Content motion (h horizontal, + right; v vertical, + up; degrees) to pixel motion (dx, dy; y down)."""
    th = np.radians(theta_deg)
    a = np.asarray(h_deg, float) * np.cos(np.radians(el_deg))
    v = np.asarray(v_deg, float)
    X = a * np.cos(th) - v * np.sin(th)
    Y = a * np.sin(th) + v * np.cos(th)
    return X * ppd_x, -Y * ppd_y


def pixels_to_angular(dx: np.ndarray, dy: np.ndarray, theta_deg: np.ndarray, el_deg: np.ndarray,
                      ppd_x: float, ppd_y: float) -> tuple[np.ndarray, np.ndarray]:
    """Inverse of angular_to_pixels: (h, v) in degrees (h along the horizon, + right; v + up)."""
    th = np.radians(theta_deg)
    X = np.asarray(dx, float) / ppd_x
    Y = -np.asarray(dy, float) / ppd_y
    a = X * np.cos(th) + Y * np.sin(th)
    v = -X * np.sin(th) + Y * np.cos(th)
    return a / np.cos(np.radians(el_deg)), v


# ----------------------------------------------------------------------------- forward model

def jet_states(t: np.ndarray, heading_deg: np.ndarray, v_rel_enu: np.ndarray, h_jet: float) -> np.ndarray:
    """Jet positions in the cloud air mass (trapezoidal integration of v_rel), starting over the origin."""
    t = np.asarray(t, float)
    v = np.asarray(v_rel_enu, float)
    p = np.zeros((len(t), 3))
    p[1:] = np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(t)[:, None], axis=0)
    p[:, 2] = h_jet
    return p


def predict_motion(t: np.ndarray, heading_deg: np.ndarray, v_rel_enu: np.ndarray, az_deg: np.ndarray,
                   el_deg: np.ndarray, theta_deg: np.ndarray, scene: CloudScene) -> dict:
    """Exact (vector) forward model: image motion of the cloud texture tracked near the LOS.

    For each frame i the tracked texture is the deck point P_i seen in the direction
    (bearing heading_i + az_i + right_of_los, elevation el_i - below_los). It is held fixed
    in the cloud air mass while the jet moves to frame i + 1 (positions from v_rel, which is
    the jet's velocity relative to the cloud air mass), and its angular offset from the new
    LOS is compared with the old one. Returned rates are centered between frames i and i+1
    and resampled to the frames by linear interpolation (end frames copy their neighbors).

    Returns h_rate, v_rate (deg/s; h + = content moves right along the horizon, v + = up),
    dx, dy (px/frame, our frames), dist_m (slant distance to P_i; nan where the ray misses
    the deck, in which case the rates are nan too).
    """
    t = np.asarray(t, float)
    n = len(t)
    R = F.effective_radius(scene.refraction)
    pos = jet_states(t, heading_deg, v_rel_enu, scene.h_jet)
    hd = np.asarray(heading_deg, float)
    az = np.asarray(az_deg, float)
    el = np.asarray(el_deg, float)
    h_mid = np.full(n - 1, np.nan)
    v_mid = np.full(n - 1, np.nan)
    dist = np.full(n, np.nan)
    for i in range(n):
        b = hd[i] + az[i] + scene.right_of_los_deg
        e = el[i] - scene.below_los_deg
        d = direction(pos[i], b, e, R)
        s = ray_sphere(pos[i], d, R + scene.h_cloud, R)
        dist[i] = s
        if i == n - 1 or not np.isfinite(s):
            continue
        P = pos[i] + s * d
        b0, e0, _ = bearing_elevation(pos[i], P, R)
        b1, e1, _ = bearing_elevation(pos[i + 1], P, R)
        los_b0, los_b1 = hd[i] + az[i], hd[i + 1] + az[i + 1]
        dt = t[i + 1] - t[i]
        h_mid[i] = (_wrap(b1 - los_b1) - _wrap(b0 - los_b0)) / dt
        v_mid[i] = ((e1 - el[i + 1]) - (e0 - el[i])) / dt
    tm = 0.5 * (t[1:] + t[:-1])
    h_rate = np.interp(t, tm, h_mid)
    v_rate = np.interp(t, tm, v_mid)
    fps = 1.0 / np.median(np.diff(t))
    dx, dy = angular_to_pixels(h_rate / fps, v_rate / fps, theta_deg, el, scene.ppd_x, scene.ppd_y)
    return {"h_rate": h_rate, "v_rate": v_rate, "dx": dx, "dy": dy, "dist_m": dist, "pos": pos}


def parallax_rate(t: np.ndarray, heading_deg: np.ndarray, v_rel_enu: np.ndarray, az_deg: np.ndarray,
                  dist_h_m: np.ndarray | float) -> np.ndarray:
    """First-order parallax p = -(v_rel . e_right) / s_h (deg/s) for a point on the LOS bearing."""
    b = np.radians(np.asarray(heading_deg, float) + np.asarray(az_deg, float))
    e_right = np.stack([np.cos(b), -np.sin(b)], axis=-1)
    v = np.asarray(v_rel_enu, float)[:, :2]
    return -np.degrees(np.sum(v * e_right, axis=1) / np.asarray(dist_h_m, float))


def predict_h_rate_linear(omega_deg_s: np.ndarray, daz_deg_s: np.ndarray, p_deg_s: np.ndarray) -> np.ndarray:
    """First-order horizontal content rate h = -(omega + daz/dt) + p (deg/s)."""
    return -(np.asarray(omega_deg_s) + np.asarray(daz_deg_s)) + np.asarray(p_deg_s)


# ----------------------------------------------------------------------------- inversion

def v_rel_from_heading(heading_deg: np.ndarray, tas_ms: np.ndarray, jet_wind_enu: np.ndarray,
                       cloud_wind_enu: np.ndarray) -> np.ndarray:
    """Jet velocity relative to the cloud air mass (ENU, m/s)."""
    h = np.radians(np.asarray(heading_deg, float))
    tas = np.broadcast_to(np.asarray(tas_ms, float), h.shape)
    v = np.stack([tas * np.sin(h), tas * np.cos(h), np.zeros_like(h)], axis=-1)
    return v + np.asarray(jet_wind_enu, float) - np.asarray(cloud_wind_enu, float)


def integrate_heading(t: np.ndarray, omega_deg_s: np.ndarray, heading0_deg: float) -> np.ndarray:
    om = np.asarray(omega_deg_s, float)
    h = np.empty(len(t))
    h[0] = heading0_deg
    h[1:] = heading0_deg + np.cumsum(0.5 * (om[1:] + om[:-1]) * np.diff(t))
    return h


def invert_turn_rate(t: np.ndarray, h_rate_deg_s: np.ndarray, az_deg: np.ndarray, tas_ms: np.ndarray,
                     heading0_deg: float, jet_wind_enu: np.ndarray, cloud_wind_enu: np.ndarray,
                     dist_h_m: np.ndarray | float, daz_deg_s: np.ndarray | None = None,
                     omega_init: np.ndarray | None = None, iters: int = 4) -> dict:
    """omega = -h - daz/dt + p, iterated because p depends on the heading history.

    dist_h_m: horizontal distance to the tracked cloud texture (scalar or per frame).
    Returns omega, p (deg/s), heading (deg) and the heading change over the record.
    """
    t = np.asarray(t, float)
    az = np.asarray(az_deg, float)
    daz = np.gradient(az, t) if daz_deg_s is None else np.asarray(daz_deg_s, float)
    om = np.zeros(len(t)) if omega_init is None else np.asarray(omega_init, float).copy()
    p = np.zeros(len(t))
    hd = integrate_heading(t, om, heading0_deg)
    for _ in range(iters):
        hd = integrate_heading(t, om, heading0_deg)
        v = v_rel_from_heading(hd, tas_ms, jet_wind_enu, cloud_wind_enu)
        p = parallax_rate(t, hd, v, az, dist_h_m)
        om = -np.asarray(h_rate_deg_s, float) - daz + p
    hd = integrate_heading(t, om, heading0_deg)
    return {"omega": om, "p": p, "heading": hd, "heading_change_deg": float(hd[-1] - hd[0])}
