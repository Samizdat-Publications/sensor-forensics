"""International Standard Atmosphere and airspeed conversions (SI units).

Used to turn the cockpit readouts (indicated airspeed, Mach, pressure altitude)
into true airspeed. An optional temperature offset from ISA lets the weather data
(ERA5 or soundings) replace the standard day.
"""

from __future__ import annotations

import numpy as np

G0 = 9.80665
R_AIR = 287.05287
GAMMA = 1.4
T0 = 288.15
P0 = 101_325.0
RHO0 = 1.225
LAPSE = -0.0065
H_TROPOPAUSE = 11_000.0
A0 = float(np.sqrt(GAMMA * R_AIR * T0))  # sea-level speed of sound, about 340.29 m/s


def isa(h: np.ndarray, dT: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Temperature (K), pressure (Pa) and density (kg/m^3) at pressure altitude h (m).

    dT shifts temperature only (pressure stays on the ISA profile, which is how a
    pressure altimeter defines altitude).
    """
    h = np.asarray(h, float)
    t_std = np.where(h <= H_TROPOPAUSE, T0 + LAPSE * h, T0 + LAPSE * H_TROPOPAUSE)
    p_trop = P0 * (1 + LAPSE * H_TROPOPAUSE / T0) ** (-G0 / (LAPSE * R_AIR))
    p = np.where(
        h <= H_TROPOPAUSE,
        P0 * (1 + LAPSE * h / T0) ** (-G0 / (LAPSE * R_AIR)),
        p_trop * np.exp(-G0 * (h - H_TROPOPAUSE) / (R_AIR * (T0 + LAPSE * H_TROPOPAUSE))),
    )
    t = t_std + dT
    return t, p, p / (R_AIR * t)


def speed_of_sound(t: np.ndarray) -> np.ndarray:
    return np.sqrt(GAMMA * R_AIR * np.asarray(t, float))


def mach_to_tas(mach: np.ndarray, h: np.ndarray, dT: float = 0.0) -> np.ndarray:
    t, _, _ = isa(h, dT)
    return np.asarray(mach, float) * speed_of_sound(t)


def cas_to_mach(cas: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Calibrated airspeed (m/s) to Mach at pressure altitude h, subsonic compressible flow.

    Indicated airspeed is treated as calibrated (position error unknown, folded into
    the uncertainty budget).
    """
    cas = np.asarray(cas, float)
    _, p, _ = isa(h)
    qc = P0 * ((1 + 0.2 * (cas / A0) ** 2) ** 3.5 - 1)
    return np.sqrt(5 * ((qc / p + 1) ** (2 / 7) - 1))


def cas_to_tas(cas: np.ndarray, h: np.ndarray, dT: float = 0.0) -> np.ndarray:
    return mach_to_tas(cas_to_mach(cas, h), h, dT)


def turn_rate(tas: np.ndarray, bank: np.ndarray) -> np.ndarray:
    """Coordinated level turn rate (rad/s). Positive bank (right wing down) turns right."""
    return G0 * np.tan(np.asarray(bank, float)) / np.asarray(tas, float)
