"""Jet kinematics: the observing aircraft's track from airspeed, bank and wind.

The jet flies a coordinated turn: turn rate = g tan(bank) / TAS. Heading is
integrated from an unknown starting heading (a parameter), and the ground track is
the air track plus wind drift. Positions are in a local ENU frame (m) whose origin
is the jet's position at the first frame, at the jet's altitude; over a 34 to 76 s
clip the jet moves a few km, so a tangent plane is exact enough for the jet itself
(lines of sight to distant objects use solve.frames for curvature).

Sign conventions: bank positive = right wing down (turning right); heading in
degrees true, clockwise from north; wind given as the vector the air moves TOWARD
(ENU, m/s), with a helper for meteorological "from" direction and speed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .atmosphere import G0


def wind_from(direction_from_deg: float, speed: float) -> np.ndarray:
    """ENU wind vector (m/s) for a wind blowing FROM direction_from_deg at speed."""
    to = np.radians(direction_from_deg + 180.0)
    return np.array([speed * np.sin(to), speed * np.cos(to), 0.0])


@dataclass
class JetTrack:
    t: np.ndarray            # s, per frame
    heading: np.ndarray      # deg true, nose / air-track heading per frame
    turn_rate: np.ndarray    # deg/s
    air_pos: np.ndarray      # ENU m, position relative to the air mass (no wind)
    ground_pos: np.ndarray   # ENU m, position over the ground (air track + wind drift)
    ground_vel: np.ndarray   # ENU m/s
    track_heading: np.ndarray  # deg true, direction of the ground velocity


def integrate(t: np.ndarray, tas: np.ndarray, bank_deg: np.ndarray, heading0_deg: float,
              wind_enu: np.ndarray | None = None, altitude: np.ndarray | float = 0.0,
              turn_rate_deg_s: np.ndarray | None = None) -> JetTrack:
    """Integrate the jet's track over the frame times t (trapezoidal in heading).

    turn_rate_deg_s, if given, overrides the bank-derived rate (for example a rate
    matched to cloud motion, as Sitrec's GIMBAL default does).
    """
    t = np.asarray(t, float)
    n = len(t)
    tas = np.broadcast_to(np.asarray(tas, float), (n,)).astype(float)
    bank = np.broadcast_to(np.asarray(bank_deg, float), (n,)).astype(float)
    if turn_rate_deg_s is None:
        rate = np.degrees(G0 * np.tan(np.radians(bank)) / tas)
    else:
        rate = np.broadcast_to(np.asarray(turn_rate_deg_s, float), (n,)).astype(float)
    dt = np.diff(t)
    heading = np.empty(n)
    heading[0] = heading0_deg
    heading[1:] = heading0_deg + np.cumsum(0.5 * (rate[1:] + rate[:-1]) * dt)
    h = np.radians(heading)
    air_vel = np.stack([tas * np.sin(h), tas * np.cos(h), np.zeros(n)], axis=-1)
    wind = np.zeros(3) if wind_enu is None else np.asarray(wind_enu, float)
    ground_vel = air_vel + wind
    air_pos = np.zeros((n, 3))
    air_pos[1:] = np.cumsum(0.5 * (air_vel[1:] + air_vel[:-1]) * dt[:, None], axis=0)
    ground_pos = air_pos + np.outer(t - t[0], wind)
    alt = np.broadcast_to(np.asarray(altitude, float), (n,))
    air_pos[:, 2] = alt
    ground_pos[:, 2] = alt
    track = np.degrees(np.arctan2(ground_vel[:, 0], ground_vel[:, 1])) % 360.0
    return JetTrack(t=t, heading=heading % 360.0, turn_rate=rate, air_pos=air_pos,
                    ground_pos=ground_pos, ground_vel=ground_vel, track_heading=track)
