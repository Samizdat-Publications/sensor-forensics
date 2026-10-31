"""Lines of sight in the local ENU frame, and points along them.

Combines the jet track (solve.jet) with the pod readouts (solve.sensor_atflir)
to give, per frame, the jet position and the unit line-of-sight vector in ENU.
Objects are placed along the sight line at a range; their altitude above the
sphere uses the exact law-of-cosines form (solve.frames), with refraction as an
option.

Az is measured from the jet's nose (air heading, JetTrack.heading), as Sitrec
does; crab angle and boresight offset are not modeled (a documented assumption).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import frames as F
from .jet import JetTrack
from .sensor_atflir import level_to_enu, los_level_frame


@dataclass
class SightLines:
    t: np.ndarray        # s
    origin: np.ndarray   # ENU m, jet positions (ground frame)
    u: np.ndarray        # ENU unit vectors
    el: np.ndarray       # deg, elevation of the sight line relative to local horizontal at the jet
    h0: np.ndarray       # m, jet altitude


def sight_lines(track: JetTrack, az_deg: np.ndarray, el_deg: np.ndarray, convention: str = "level",
                bank_deg: np.ndarray | float = 0.0, pitch_deg: np.ndarray | float = 0.0) -> SightLines:
    n = len(track.t)
    az = np.broadcast_to(np.asarray(az_deg, float), (n,))
    el = np.broadcast_to(np.asarray(el_deg, float), (n,))
    bank = np.broadcast_to(np.asarray(bank_deg, float), (n,))
    pitch = np.broadcast_to(np.asarray(pitch_deg, float), (n,))
    u = np.empty((n, 3))
    el_world = np.empty(n)
    for i in range(n):
        v = los_level_frame(az[i], el[i], convention, jet_roll=bank[i], jet_pitch=pitch[i])
        e = level_to_enu(v, track.heading[i])
        u[i] = e / np.linalg.norm(e)
        el_world[i] = np.degrees(np.arcsin(np.clip(u[i, 2], -1, 1)))
    return SightLines(t=track.t, origin=track.ground_pos.copy(), u=u, el=el_world, h0=track.ground_pos[:, 2].copy())


def points_at_range(sl: SightLines, rng_m: np.ndarray, refraction: bool | float = False) -> tuple[np.ndarray, np.ndarray]:
    """Object positions (ENU, horizontal components) and altitudes (m) at the given slant ranges."""
    r = np.broadcast_to(np.asarray(rng_m, float), sl.t.shape)
    pos = sl.origin + r[:, None] * sl.u
    alt = np.array([F.altitude_along_sight_line(sl.h0[i], np.radians(sl.el[i]), r[i], refraction)
                    for i in range(len(r))])
    pos[:, 2] = alt
    return pos, alt
