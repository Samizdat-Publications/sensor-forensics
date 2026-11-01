"""M2.7 reproduction: the two published GIMBAL reconstructions, then rerun with lab inputs.

A. Peings and von Rennenkampff 2023 (P&vR), "best-guess" close path, from their
   stated inputs (docs/prior-work/peings-vonrennenkampff-2023.md): TAS about 365 kt,
   bank every 10 frames (Sitrec's GimbalData.csv `bank_angle` column stands in for
   their own extraction), ROT = 1091 tan(bank) / TAS (deg/s, kt), heading starts at
   0, forward-Euler steps of 10 frames at 30 fps (their Eqs. 1 to 3), azimuth = a
   50-frame centered moving average of the integer readout (Sitrec's raw `azimuth`
   column), elevation -2.00 rising linearly to -1.95 deg, wind 120 kt from 35 deg
   left of the initial heading. Their cloud-motion azimuth correction is not
   quantified in the paper and is omitted (they report the uncorrected version as
   "noisier, although qualitatively similar", p. 15). The object is a straight line
   in the top view of the air frame, starting 8 nmi along the first sight line,
   heading 20 deg left of the jet's initial heading (15 deg off the wind), and is
   intersected with every sight line. Both aircraft are in the same air mass for the
   sight-line construction; ground speed adds the wind.

B. A Sitrec-style distant path. Sitrec's default jet turn rate is a cloud-speed
   solve (not ported); its documented alternative "From Bank and Speed" is used:
   bank = minus CSV `bank_angle`, TAS 351 kt, g = 9.77468, heading 315, jet wind
   120 kt from 270, azimuth = minus `gaussian_smoothed_azimuth`, elevation
   -2.01 + 0.025 f / 1031, level convention. The object starts 32 nmi along the
   first sight line and moves at a constant AIR speed of 340 kt through a target wind
   of 65 kt from 274 (Sitrec's CNodeLOSTraverseConstantSpeed: far intersection of
   each sight line with a sphere of radius 340 kt / fps around the previous position
   advected by the wind; no intersection -> closest point, flagged). Also P&vR's
   Fig. A7 check: a LEVEL path at 18,700 ft placed on every sight line and the air
   speed it implies.

C. Both rerun with the lab's measured inputs (data/derived/gimbal/): TAS from the
   on-screen Mach, bank from the horizon bars (image_track.csv), azimuth readout as
   the center of its +/-0.5 deg interval with the measured 6-frame display cadence
   (a smoothing spline constrained to stay inside every interval at every display
   update), elevation -2 (sensitivity -2.5 and -1.5), the lab's 1031-frame indexing
   at 29.97 fps. One-at-a-time swaps attribute each difference to an input.

Frame numbering: A and B use Sitrec's 0-based frames. Lab inputs use the lab's own
frames; our_frame = sitrec_frame + 1 for the azimuth readout (FINDINGS-LOG), so lab
series are shifted by one frame when they are mixed into a Sitrec-numbered run.

Usage: python -m solve.repro_gimbal  (writes docs/reproductions/gimbal.json and
docs/reproductions/gimbal_*.png)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import make_smoothing_spline

from . import atmosphere as A
from . import frames as F
from .jet import JetTrack, integrate, wind_from
from .los import SightLines, sight_lines

ROOT = Path(__file__).resolve().parents[1]
SITREC_CSV = ROOT / "data" / "reference" / "sitrec" / "data" / "gimbal" / "GimbalData.csv"
LAB_DIR = ROOT / "data" / "derived" / "gimbal"
OUT_DIR = ROOT / "docs" / "reproductions"

FPS = 30000 / 1001
N = 1031
JET_ALT_FT = 25_000.0
SITREC_G = 9.77468

# Published values and the tolerances stated before the run (work item M2.7).
PUBLISHED_A = {
    "start_range_nmi": 8.0, "end_range_nmi": 6.8,
    "air_speed_start_kt": 400.0, "air_speed_min_kt_below": 50.0, "air_speed_min_frame": 900,
    "ground_speed_start_kt": 300.0, "ground_speed_min_frame": 720, "ground_speed_end_kt_above": 120.0,
    "alt_change_ft": 250.0,
    "jet_end_no_wind_nmi": [-1.65, 2.87], "jet_end_wind_nmi": [-1.0, 1.9],
}
TOL_A = {"position_nmi": 0.2, "min_frame": 60, "speed_frac": 0.15}
PUBLISHED_A7 = {"alt_ft": 18_700.0, "range_nmi": 30.0, "air_speed_start_kt": 300.0, "air_speed_end_kt": 450.0}
TOL_A7 = {"speed_frac": 0.15, "range_nmi": 1.5}


# ----------------------------------------------------------------------------- inputs

@dataclass
class Inputs:
    """Per-frame inputs (length N) and run settings for one reconstruction."""
    name: str
    tas_kt: np.ndarray
    bank_deg: np.ndarray          # positive = right wing down (GIMBAL is negative)
    az_deg: np.ndarray            # positive = right of the nose
    el_deg: np.ndarray
    fps: float = FPS
    turn: str = "g"               # "pvr1091" or "g"
    g: float = A.G0
    turn_tas_kt: np.ndarray | None = None   # TAS used in the turn-rate formula (Sitrec reads a fixed 351)
    turn_override: np.ndarray | None = None  # deg/s per frame, replaces the bank formula (e.g. cloud-matched)
    notes: dict = field(default_factory=dict)


def _const(x: float) -> np.ndarray:
    return np.full(N, float(x))


def load_sitrec() -> pd.DataFrame:
    return pd.read_csv(SITREC_CSV, encoding="utf-8-sig")


def _moving_average(x: np.ndarray, w: int = 50, centered: bool = True) -> np.ndarray:
    return pd.Series(x).rolling(w, min_periods=1, center=centered).mean().to_numpy()


def _shift_to_lab(x: np.ndarray, k: int = 1) -> np.ndarray:
    """Sitrec-numbered series -> lab numbering (lab frame f holds Sitrec frame f - k)."""
    return np.concatenate([np.full(k, x[0]), x[:-k]])


def _shift_to_sitrec(x: np.ndarray, k: int = 1) -> np.ndarray:
    """Lab-numbered series -> Sitrec numbering (Sitrec frame s = lab frame s + 1)."""
    return np.concatenate([x[k:], np.full(k, x[-1])])


def pvr_tas_kt(const: float | None = None) -> np.ndarray:
    """P&vR TAS: "for each selected frame, the corresponding TAS value from that interval is used" (p. 6).

    Their IAS interval 238 to 242 kt maps onto TAS 363 to 369 kt; the displayed IAS per frame
    (the lab's readout, Sitrec numbering) is mapped linearly onto that interval. `const`
    replaces it with a constant (e.g. the 365 kt of their Fig. 3 caption).
    """
    if const is not None:
        return _const(const)
    ias = _shift_to_sitrec(_lab_field("airspeed").astype(float).to_numpy())
    return 363.0 + 1.5 * (ias - 238.0)


def pvr_inputs(az_centered: bool = True, tas_const: float | None = None) -> Inputs:
    d = load_sitrec()
    az_raw = -d["4 azimuth"].to_numpy(float)              # CSV positive = left
    az = _moving_average(az_raw, 50, centered=az_centered)
    el = np.linspace(-2.00, -1.95, N)
    return Inputs("A_pvr_repro", tas_kt=pvr_tas_kt(tas_const), bank_deg=-d["3 bank_angle"].to_numpy(float),
                  az_deg=az, el_deg=el, fps=30.0, turn="pvr1091",
                  notes={"az": "Sitrec raw integer azimuth, 50-frame " + ("centered" if az_centered else "trailing")
                         + " moving average, no cloud-motion correction",
                         "tas": "displayed IAS 238-242 mapped linearly onto 363-369 kt" if tas_const is None
                         else f"constant {tas_const} kt",
                         "bank": "Sitrec GimbalData.csv bank_angle (stand-in for P&vR's own every-10-frame extraction)"})


def sitrec_inputs() -> Inputs:
    d = load_sitrec()
    f = np.arange(N)
    return Inputs("B_sitrec_style", tas_kt=_const(351.0), bank_deg=-d["3 bank_angle"].to_numpy(float),
                  az_deg=-d["5 gaussian_smoothed_azimuth"].to_numpy(float),
                  el_deg=-2.01 + 0.025 * f / N, fps=FPS, turn="g", g=SITREC_G,
                  notes={"turn": "From Bank and Speed (Sitrec's default Match Clouds is not ported)"})


# ----------------------------------------------------------------------------- lab readings

def _lab_field(field_name: str) -> pd.Series:
    sym = pd.read_csv(LAB_DIR / "symbology_final.csv", dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    return sym[sym["field"] == field_name].sort_values("frame").set_index("frame")["value"]


def lab_azimuth_readings() -> np.ndarray:
    s = _lab_field("azimuth")
    return np.array([float(v[:-1]) * (-1.0 if v.endswith("L") else 1.0) for v in s.tolist()])


def lab_tas_kt(dT: float = 0.0, smooth: int = 100) -> np.ndarray:
    """TAS from the on-screen Mach (two decimals) and altitude, ISA + dT, centered moving average."""
    mach = _lab_field("mach").astype(float).to_numpy()
    alt = _lab_field("altitude").astype(float).to_numpy()
    tas = A.mach_to_tas(mach, alt * F.FT, dT) / F.KT
    return _moving_average(tas, smooth) if smooth > 1 else tas


def lab_bank_deg() -> np.ndarray:
    cues = pd.read_csv(LAB_DIR / "image_track.csv")
    return cues["bank_deg"].to_numpy(float)


def interval_azimuth(readings: np.ndarray, cadence: int = 6, phase: int = 3, half_width: float = 0.5,
                     latency: float | None = None) -> tuple[np.ndarray, dict]:
    """Smooth azimuth from integer readouts treated as intervals.

    A reading v held on frames [a, b) means the true azimuth was inside [v - 0.5, v + 0.5]
    at every display update from a to b - cadence (the display refreshes every `cadence`
    frames; a change shown at frame b happened during (b - cadence, b]). Data points are
    the interval centers ((a + b) / 2 - latency, v) of every complete interval, with
    latency = cadence / 2 by default. A smoothing spline is fitted and its smoothing is
    relaxed (bisection on log lambda) to the smoothest curve that stays inside every
    interval at every update frame.
    """
    lat = cadence / 2.0 if latency is None else latency
    r = np.asarray(readings, float)
    change = np.flatnonzero(np.diff(r) != 0) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(r)]])
    xs, ys = [], []
    cons_f, cons_v = [], []
    for a, b in zip(starts, ends):
        v = r[a]
        complete = a > 0 and b < len(r)
        if complete:
            xs.append((a + b) / 2.0 - lat)
            ys.append(v)
        last = b - cadence if b < len(r) else len(r) - 1
        if a == 0:
            grid = np.arange(phase, last + 1, cadence)
        else:
            grid = np.arange(a, last + 1, cadence)
        cons_f.extend(grid.tolist())
        cons_v.extend([v] * len(grid))
    xs, ys = np.array(xs), np.array(ys)
    cons_f, cons_v = np.array(cons_f, float), np.array(cons_v)
    frames = np.arange(len(r), dtype=float)

    def fit(lam: float):
        spl = make_smoothing_spline(xs, ys, lam=lam)
        return spl, float(np.max(np.abs(spl(cons_f) - cons_v)))

    lo, hi = -2.0, 8.0          # log10 lambda bracket
    spl_lo, viol_lo = fit(10 ** lo)
    if viol_lo > half_width:
        spl, viol, lam = spl_lo, viol_lo, 10 ** lo
    else:
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            _, v = fit(10 ** mid)
            if v <= half_width:
                lo = mid
            else:
                hi = mid
        lam = 10 ** lo
        spl, viol = fit(lam)
    az = spl(frames)
    info = {"n_intervals": int(len(starts)), "n_centers": int(len(xs)), "n_constraints": int(len(cons_f)),
            "lambda": float(lam), "max_constraint_violation_deg": float(viol),
            "rms_vs_centers_deg": float(np.sqrt(np.mean((spl(xs) - ys) ** 2))),
            "cadence_frames": cadence, "phase": phase, "latency_frames": lat}
    return az, info


def lab_inputs(el: float = -2.0, dT: float = 0.0) -> tuple[Inputs, dict]:
    az, info = interval_azimuth(lab_azimuth_readings())
    tas = lab_tas_kt(dT)
    return Inputs("C_lab", tas_kt=tas, bank_deg=lab_bank_deg(), az_deg=az, el_deg=_const(el), fps=FPS, turn="g",
                  notes={"az_fit": info, "tas": "Mach x ISA speed of sound" + (f" (dT {dT:+.1f} K)" if dT else ""),
                         "bank": "image_track.csv horizon bars", "frames": "lab numbering"}), info


# ----------------------------------------------------------------------------- jet and sight lines

def turn_rate_deg_s(inp: Inputs) -> np.ndarray:
    if inp.turn_override is not None:
        return np.asarray(inp.turn_override, float)
    tas = inp.tas_kt if inp.turn_tas_kt is None else inp.turn_tas_kt
    if inp.turn == "pvr1091":
        return 1091.0 * np.tan(np.radians(inp.bank_deg)) / tas
    return np.degrees(inp.g * np.tan(np.radians(inp.bank_deg)) / (tas * F.KT))


def pvr_jet(inp: Inputs, step: int = 10, wind_rel_deg: float | None = None, wind_kt: float = 120.0,
            heading0: float = 0.0) -> tuple[np.ndarray, JetTrack]:
    """P&vR Eqs. 1 to 3: forward Euler every `step` frames, heading from 0.

    beta_k = beta_{k-1} + ROT_{k-1} dt;  x_k = x_{k-1} + TAS dt sin(beta_k) - Ws dt sin(Wd), etc.
    Wind direction Wd is where the wind comes FROM, relative to the initial heading
    (0 = headwind). Returns the sampled frames and a JetTrack in the air frame
    (ground_pos = air position, since sight lines are built in the air mass); the
    wind-drifted ground track is attached as the extra attribute `wind_ground_pos`.
    """
    fr = np.arange(0, N, step)
    dt = step / inp.fps
    rot = turn_rate_deg_s(inp)[fr]
    tas = inp.tas_kt[fr] * F.KT
    n = len(fr)
    beta = np.empty(n)
    beta[0] = heading0
    for k in range(1, n):
        beta[k] = beta[k - 1] + rot[k - 1] * dt
    air = np.zeros((n, 3))
    gnd = np.zeros((n, 3))
    wd = None if wind_rel_deg is None else np.radians(wind_rel_deg + heading0)
    for k in range(1, n):
        b = np.radians(beta[k])
        step_xy = tas[k] * dt * np.array([np.sin(b), np.cos(b), 0.0])
        air[k] = air[k - 1] + step_xy
        gnd[k] = gnd[k - 1] + step_xy
        if wd is not None:
            gnd[k] -= wind_kt * F.KT * dt * np.array([np.sin(wd), np.cos(wd), 0.0])
    alt = JET_ALT_FT * F.FT
    air[:, 2] = alt
    gnd[:, 2] = alt
    t = fr / inp.fps
    track = JetTrack(t=t, heading=beta % 360.0, turn_rate=rot, air_pos=air, ground_pos=air.copy(),
                     ground_vel=np.zeros((n, 3)), track_heading=beta % 360.0)
    track.wind_ground_pos = gnd  # type: ignore[attr-defined]
    return fr, track


def sitrec_jet(inp: Inputs, heading0: float = 315.0, wind=(270.0, 120.0)) -> JetTrack:
    t = np.arange(N) / inp.fps
    w = None if wind is None else wind_from(wind[0], wind[1] * F.KT)
    return integrate(t, inp.tas_kt * F.KT, inp.bank_deg, heading0, wind_enu=w, altitude=JET_ALT_FT * F.FT,
                     turn_rate_deg_s=turn_rate_deg_s(inp))


# ----------------------------------------------------------------------------- object constructions

def straight_line_object(sl: SightLines, frames: np.ndarray, start_range_m: float, heading_deg: float,
                         wind_enu: np.ndarray) -> dict:
    """P&vR construction: a straight line in the top view (air frame) intersected with every sight line."""
    uh = sl.u[:, :2]
    uh_norm = np.linalg.norm(uh, axis=1)
    o = sl.origin[:, :2]
    p0 = o[0] + start_range_m * uh[0]
    d = np.array([np.sin(np.radians(heading_deg)), np.cos(np.radians(heading_deg))])
    n = len(frames)
    s = np.full(n, np.nan)
    tau = np.full(n, np.nan)
    for i in range(n):
        m = np.column_stack([uh[i], -d])
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        s[i], tau[i] = np.linalg.solve(m, p0 - o[i])
    rng = s                                         # u is a unit 3-D vector, so s is the slant range
    valid = rng > 0
    alt = np.array([F.altitude_along_sight_line(sl.h0[i], np.radians(sl.el[i]), rng[i]) if valid[i] else np.nan
                    for i in range(n)])
    alt_flat = sl.h0 + rng * np.sin(np.radians(sl.el))
    t = sl.t
    v_along = np.gradient(tau, t)
    vz = np.gradient(alt, t)
    air_speed = np.hypot(v_along, vz)
    gv = v_along[:, None] * d[None, :] + np.asarray(wind_enu, float)[None, :2]
    ground_speed = np.hypot(gv[:, 0], gv[:, 1])
    pos = p0[None, :] + tau[:, None] * d[None, :]
    return {"frames": frames, "t": t, "range_m": rng, "alt_m": alt, "alt_flat_m": alt_flat, "tau_m": tau,
            "v_along_ms": v_along, "vz_ms": vz, "air_speed_ms": air_speed, "ground_speed_ms": ground_speed,
            "pos_air": pos, "uh_norm": uh_norm, "valid": valid}


def smoothed_speeds(obj: dict, d_heading_deg: float, wind_enu: np.ndarray, window: int = 21) -> dict:
    """Savitzky-Golay (order 2) derivative of the along-line position, `window` samples wide.

    Raw sample-to-sample differences of a 50-frame average of an integer readout are
    dominated by the readout's 1-degree steps; P&vR's plotted speeds are smooth.
    window = 21 samples of 10 frames is about 7 s.
    """
    from scipy.signal import savgol_filter
    t = obj["t"]
    dt = float(t[1] - t[0])
    tau = obj["tau_m"]
    w = min(window, len(tau) - (1 - len(tau) % 2))
    v = savgol_filter(tau, w, 2, deriv=1, delta=dt)
    vz = savgol_filter(obj["alt_m"], w, 2, deriv=1, delta=dt)
    d = np.array([np.sin(np.radians(d_heading_deg)), np.cos(np.radians(d_heading_deg))])
    gv = v[:, None] * d[None, :] + np.asarray(wind_enu, float)[None, :2]
    return {"v_along_ms": v, "air_speed_ms": np.hypot(v, vz), "ground_speed_ms": np.hypot(gv[:, 0], gv[:, 1])}


def const_air_speed_object(sl: SightLines, start_range_m: float, speed_kt: float, target_wind_enu: np.ndarray,
                           fps: float = FPS) -> dict:
    """Port of Sitrec's CNodeLOSTraverseConstantSpeed (airSpeed = true, moving away).

    Each frame: the point on the sight line, on the far branch, whose displacement from
    the previous position minus the per-frame target wind has length speed / fps. If no
    such point exists the closest point on the sight line to the previous position is
    used and the frame is flagged bad (Sitrec does the same; its binary search can flag a
    few more frames, see docs/reproductions/gimbal.md).
    """
    n = len(sl.t)
    step = speed_kt * F.KT / fps
    wstep = np.asarray(target_wind_enu, float) / fps
    r = np.empty(n)
    bad = np.zeros(n, bool)
    p = np.empty((n, 3))
    r[0] = start_range_m
    p[0] = sl.origin[0] + r[0] * sl.u[0]
    for i in range(1, n):
        c = p[i - 1] + wstep
        oc = sl.origin[i] - c
        b = float(np.dot(sl.u[i], oc))
        disc = b * b - (float(np.dot(oc, oc)) - step * step)
        if disc < 0:
            r[i] = float(np.dot(sl.u[i], p[i - 1] - sl.origin[i]))
            bad[i] = True
        else:
            r[i] = -b + np.sqrt(disc)
        p[i] = sl.origin[i] + r[i] * sl.u[i]
    alt = np.array([F.altitude_along_sight_line(sl.h0[i], np.radians(sl.el[i]), r[i]) for i in range(n)])
    return {"t": sl.t, "range_m": r, "pos": p, "alt_m": alt, "bad": bad}


def fixed_altitude_object(sl: SightLines, alt_m: float, wind_enu: np.ndarray | None = None,
                          smooth_frames: int = 1, earth: str = "flat") -> dict:
    """Object on every sight line at a fixed altitude (P&vR Fig. A7) and the air speed it implies.

    earth="flat": altitude = h0 + r sin(el), the 2-D construction P&vR use (18,700 ft is
    then at about 30 nmi). earth="sphere": exact altitude above a spherical Earth (the
    same altitude is then about 35 nmi out).
    """
    n = len(sl.t)
    if earth == "flat":
        r = (sl.h0 - alt_m) / np.sin(-np.radians(sl.el))
    else:
        r = np.array([F.range_to_altitude(sl.h0[i], np.radians(sl.el[i]), alt_m) for i in range(n)])
    pos = sl.origin + r[:, None] * sl.u
    v = np.gradient(pos[:, :2], sl.t, axis=0)
    if wind_enu is not None:
        v = v - np.asarray(wind_enu, float)[None, :2]
    if smooth_frames > 1:
        v = np.column_stack([_moving_average(v[:, k], smooth_frames) for k in range(2)])
    return {"t": sl.t, "range_m": r, "pos": pos, "air_speed_ms": np.hypot(v[:, 0], v[:, 1]),
            "air_heading_deg": np.degrees(np.arctan2(v[:, 0], v[:, 1])) % 360}


# ----------------------------------------------------------------------------- Sitrec "Match Clouds" (approximate port)

CLOUD_SPEED_POINTS = [0, -0.155, 181.334, -0.132, 433.866, -0.091, 354.555, -0.102, 718.438, -0.055,
                      632.133, -0.069, 1030, -0.013, 897.667, -0.023]   # SitGimbal.js cloudSpeedEditor


def cloud_speed_curve() -> np.ndarray:
    """Sitrec's hand-keyed cloud angular speed (deg/s) per frame.

    APPROXIMATION: Sitrec evaluates these points with its CNodeCurveEditor (not ported);
    here they are sorted by frame and joined by a monotone cubic (PCHIP).
    """
    from scipy.interpolate import PchipInterpolator
    pts = np.array(CLOUD_SPEED_POINTS, float).reshape(-1, 2)
    pts = pts[np.argsort(pts[:, 0])]
    return PchipInterpolator(pts[:, 0], pts[:, 1])(np.arange(N))


def cloud_turn_rate(az_deg: np.ndarray, tas_kt: float = 351.0, jet_alt_ft: float = JET_ALT_FT,
                    cloud_alt_ft: float = 11_740.0, fps: float = FPS) -> np.ndarray:
    """Port of Sitrec's CNodeTurnRateFromClouds.recalculate (EUS frame, WGS84 radius, no refraction).

    MIT, Copyright (c) 2023-2024 Mick West; see data/reference/sitrec/NOTICE.md.
    """
    R = 6_378_137.0
    cs = cloud_speed_curve()

    def up(p):
        c = p - np.array([0.0, -R, 0.0])
        return c / np.linalg.norm(c)

    def rot(v, k, a):
        return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))

    def horizon_point(a, fwd, alt):
        pos = a + np.array([0.0, R, 0.0])
        hr = R + alt
        dist = np.sqrt(max(float(np.dot(pos, pos)) - hr * hr, 0.0))
        return a + fwd / np.linalg.norm(fwd) * dist

    jet = np.array([0.0, jet_alt_ft * F.FT, 0.0])
    fwd = np.array([0.0, 0.0, -1.0])
    speed = tas_kt * F.KT
    rate = 0.0
    out = []
    for f in range(N - 1):
        last, last_fwd = jet.copy(), fwd.copy()
        jet = jet + fwd * speed / fps
        u = up(jet)
        fwd = rot(fwd, u, -np.radians(rate / fps))
        right = np.cross(u, fwd)
        fwd = np.cross(right, u)
        los = rot(last_fwd, up(last), np.radians(-az_deg[f]))
        h = horizon_point(last, los, cloud_alt_ft * F.FT)
        f1 = (h - last) / np.linalg.norm(h - last)
        f2 = (h - jet) / np.linalg.norm(h - jet)
        change = np.degrees(np.arctan2(f2[2], f2[0]) - np.arctan2(f1[2], f1[0]))
        change = (change + 180.0) % 360.0 - 180.0
        change -= az_deg[f + 1] - az_deg[f]
        rate = change * fps + cs[f]
        out.append(rate)
    out.append(rate)
    return np.array(out)


# ----------------------------------------------------------------------------- runs

def _window_mean(x: np.ndarray, a: int, b: int) -> float:
    return float(np.nanmean(np.asarray(x, float)[a:b]))


def _sign_change_frame(fr: np.ndarray, v: np.ndarray) -> int | None:
    s = np.sign(v)
    idx = np.flatnonzero((s[1:] != s[:-1]) & (s[1:] != 0))
    return int(fr[idx[0] + 1]) if len(idx) else None


def _unwrap_deg(h: np.ndarray) -> np.ndarray:
    return np.degrees(np.unwrap(np.radians(h)))


def _straightness(pos_xy: np.ndarray) -> dict:
    """Max and RMS perpendicular deviation from the best straight line (total least squares)."""
    c = pos_xy.mean(axis=0)
    _, _, vt = np.linalg.svd(pos_xy - c)
    d = vt[0]
    perp = (pos_xy - c) @ np.array([-d[1], d[0]])
    return {"max_dev_nmi": float(np.max(np.abs(perp)) / F.NMI), "rms_dev_nmi": float(np.sqrt(np.mean(perp ** 2)) / F.NMI),
            "length_nmi": float(np.ptp((pos_xy - c) @ d) / F.NMI),
            "line_heading_deg": float(np.degrees(np.arctan2(d[0], d[1])) % 180.0)}


def run_a(inp: Inputs, wind_rel_deg: float = -35.0, wind_kt: float = 120.0, offset_deg: float = 15.0,
          start_nmi: float = 8.0, step: int = 10, sg_window: int = 21) -> dict:
    """P&vR close straight-line path. Heading frame: the jet's initial heading is 0 deg.

    wind_rel_deg: where the wind comes FROM, relative to the initial heading (P&vR: -35).
    The object heads offset_deg to the right of the upwind direction (P&vR: 15, giving -20).
    """
    fr, track = pvr_jet(inp, step=step, wind_rel_deg=wind_rel_deg, wind_kt=wind_kt)
    sl = sight_lines(track, inp.az_deg[fr], inp.el_deg[fr], "level")
    obj_heading = wind_rel_deg + offset_deg
    wind = wind_from(wind_rel_deg, wind_kt * F.KT)
    o = straight_line_object(sl, fr, start_nmi * F.NMI, obj_heading, wind)
    ok = o["valid"]
    sm = smoothed_speeds(o, obj_heading, wind, sg_window)
    gs = sm["ground_speed_ms"] / F.KT
    asp = sm["air_speed_ms"] / F.KT
    v = sm["v_along_ms"] / F.KT
    i_gmin = int(np.nanargmin(np.where(ok, gs, np.nan)))
    i_amin = int(np.nanargmin(np.where(ok, asp, np.nan)))
    gnd = track.wind_ground_pos  # type: ignore[attr-defined]
    res = {
        "inputs": inp.name,
        "wind_rel_deg": wind_rel_deg, "wind_kt": wind_kt, "object_heading_rel_deg": obj_heading,
        "start_range_nmi": float(o["range_m"][0] / F.NMI),
        "end_range_nmi": float(o["range_m"][-1] / F.NMI),
        "min_range_nmi": float(np.nanmin(o["range_m"]) / F.NMI),
        "all_intersections_in_front": bool(np.all(ok)),
        "air_speed_start_kt": float(asp[0]), "air_speed_end_kt": float(asp[-1]),
        "air_speed_min_kt": float(asp[i_amin]), "air_speed_min_frame": int(fr[i_amin]),
        "ground_speed_start_kt": float(gs[0]), "ground_speed_end_kt": float(gs[-1]),
        "ground_speed_min_kt": float(gs[i_gmin]), "ground_speed_min_frame": int(fr[i_gmin]),
        "air_velocity_reversal_frame": _sign_change_frame(fr, v),
        "raw_ground_speed_min_frame": int(fr[int(np.nanargmin(np.where(ok, o["ground_speed_ms"], np.nan)))]),
        "alt_start_ft": float(o["alt_m"][0] / F.FT), "alt_end_ft": float(o["alt_m"][-1] / F.FT),
        "alt_change_ft": float((o["alt_m"][-1] - o["alt_m"][0]) / F.FT),
        "alt_change_flat_earth_ft": float((o["alt_flat_m"][-1] - o["alt_flat_m"][0]) / F.FT),
        "jet_end_air_nmi": [float(track.air_pos[-1, 0] / F.NMI), float(track.air_pos[-1, 1] / F.NMI)],
        "jet_end_ground_nmi": [float(gnd[-1, 0] / F.NMI), float(gnd[-1, 1] / F.NMI)],
        "jet_heading_change_deg": float(_unwrap_deg(track.heading)[-1] - track.heading[0]),
        "tas_kt_mean": float(np.mean(inp.tas_kt)),
        "speed_smoothing": f"Savitzky-Golay order 2, {sg_window} samples of {step} frames",
    }
    res["_series"] = {"frames": fr, "track": track, "sl": sl, "obj": o, "gs_kt": gs, "as_kt": asp, "v_kt": v}
    return res


def run_b(inp: Inputs, heading0: float = 315.0, jet_wind=(270.0, 120.0), target_wind=(274.0, 65.0),
          start_nmi: float = 32.0, speed_kt: float = 340.0, turn_rate: np.ndarray | None = None,
          smooth: int = 100) -> dict:
    """Sitrec-style constant-air-speed far path. turn_rate overrides the bank formula (deg/s)."""
    t = np.arange(N) / inp.fps
    w = None if jet_wind is None else wind_from(jet_wind[0], jet_wind[1] * F.KT)
    rate = turn_rate_deg_s(inp) if turn_rate is None else turn_rate
    track = integrate(t, inp.tas_kt * F.KT, inp.bank_deg, heading0, wind_enu=w, altitude=JET_ALT_FT * F.FT,
                      turn_rate_deg_s=rate)
    sl = sight_lines(track, inp.az_deg, inp.el_deg, "level")
    tw = wind_from(target_wind[0], target_wind[1] * F.KT)
    o = const_air_speed_object(sl, start_nmi * F.NMI, speed_kt, tw, inp.fps)
    p = o["pos"]
    v = np.gradient(p[:, :2], o["t"], axis=0)
    vs = np.column_stack([_moving_average(v[:, k], smooth) for k in range(2)])
    gnd_hdg = np.degrees(np.arctan2(vs[:, 0], vs[:, 1])) % 360
    air = vs - tw[None, :2]
    air_hdg = np.degrees(np.arctan2(air[:, 0], air[:, 1])) % 360
    gs = np.hypot(vs[:, 0], vs[:, 1]) / F.KT
    vz = _moving_average(np.gradient(o["alt_m"], o["t"]), smooth) / F.FT * 60.0
    e = smooth // 2
    inner = slice(e, N - e)
    good = ~o["bad"]
    first_bad_run = None
    run = 0
    for i in range(1, N):
        run = run + 1 if o["bad"][i] else 0
        if run >= 10:
            first_bad_run = i - 9
            break
    res = {
        "inputs": inp.name, "heading0": heading0, "jet_wind": None if jet_wind is None else list(jet_wind),
        "target_wind": list(target_wind), "turn_rate_source": "bank" if turn_rate is None else "override",
        "start_range_nmi": float(o["range_m"][0] / F.NMI), "end_range_nmi": float(o["range_m"][-1] / F.NMI),
        "range_min_max_nmi": [float(o["range_m"].min() / F.NMI), float(o["range_m"].max() / F.NMI)],
        "alt_start_ft": float(o["alt_m"][0] / F.FT), "alt_end_ft": float(o["alt_m"][-1] / F.FT),
        "alt_min_max_ft": [float(o["alt_m"].min() / F.FT), float(o["alt_m"].max() / F.FT)],
        "vertical_speed_fpm_min_max": [float(np.min(vz[inner])), float(np.max(vz[inner]))],
        "n_no_intersection_frames": int(o["bad"].sum()),
        "first_no_intersection_run_frame": first_bad_run,
        "ground_heading_start_end_deg": [float(gnd_hdg[e]), float(gnd_hdg[N - e - 1])],
        "ground_heading_span_deg": float(np.ptp(_unwrap_deg(gnd_hdg[inner]))),
        "air_heading_start_end_deg": [float(air_hdg[e]), float(air_hdg[N - e - 1])],
        "air_heading_span_deg": float(np.ptp(_unwrap_deg(air_hdg[inner]))),
        "ground_speed_kt_min_max": [float(np.min(gs[inner])), float(np.max(gs[inner]))],
        "straightness_top_view": _straightness(p[:, :2]),
        "straightness_top_view_good_frames": _straightness(p[good, :2]),
        "jet_heading_change_deg": float(_unwrap_deg(track.heading)[-1] - track.heading[0]),
        "jet_end_ground_nmi": [float(track.ground_pos[-1, 0] / F.NMI), float(track.ground_pos[-1, 1] / F.NMI)],
        "tas_kt_mean": float(np.mean(inp.tas_kt)),
        "smoothing_frames_for_heading_speed": smooth,
    }
    res["_series"] = {"track": track, "sl": sl, "obj": o, "gs_kt": gs, "air_hdg": air_hdg, "gnd_hdg": gnd_hdg, "vz_fpm": vz}
    return res


def run_a7(inp: Inputs, alt_ft: float = 18_700.0, geometry: str = "air", earth: str = "flat",
           heading0: float = 315.0, jet_wind=(270.0, 120.0), target_wind=(274.0, 65.0), smooth: int = 100) -> dict:
    """Level path at a fixed altitude on every sight line; implied air speed (P&vR Fig. A7).

    geometry="air": P&vR's (jet air track every frame, same air mass, no wind).
    geometry="ground": Sitrec's (jet ground track with jet wind; speed relative to target wind).
    start = mean over frames 50 to 150, end = mean over frames N-150 to N-50 (clear of the
    moving-average edges).
    """
    if geometry == "air":
        fr, track = pvr_jet(inp, step=1)
        sl = sight_lines(track, inp.az_deg[fr], inp.el_deg[fr], "level")
        o = fixed_altitude_object(sl, alt_ft * F.FT, None, smooth, earth)
    else:
        track = sitrec_jet(inp, heading0, jet_wind)
        sl = sight_lines(track, inp.az_deg, inp.el_deg, "level")
        o = fixed_altitude_object(sl, alt_ft * F.FT, wind_from(target_wind[0], target_wind[1] * F.KT), smooth, earth)
    asp = o["air_speed_ms"] / F.KT
    e = smooth // 2
    return {"inputs": inp.name, "geometry": geometry, "earth": earth, "alt_ft": alt_ft,
            "range_start_end_nmi": [float(o["range_m"][0] / F.NMI), float(o["range_m"][-1] / F.NMI)],
            "air_speed_start_kt": _window_mean(asp, 50, 150), "air_speed_end_kt": _window_mean(asp, N - 150, N - 50),
            "air_speed_at_frame_700_kt": _window_mean(asp, 650, 750),
            "air_speed_min_max_kt": [float(np.min(asp[e:N - e])), float(np.max(asp[e:N - e]))],
            "air_heading_span_deg": float(np.ptp(_unwrap_deg(o["air_heading_deg"][e:N - e]))),
            "straightness_top_view": _straightness(o["pos"][:, :2]),
            "_series": {"obj": o, "as_kt": asp, "sl": sl}}


def strip(d):
    """Drop the private series for JSON output."""
    if isinstance(d, dict):
        return {k: strip(v) for k, v in d.items() if not str(k).startswith("_")}
    if isinstance(d, (list, tuple)):
        return [strip(v) for v in d]
    if isinstance(d, (np.floating,)):
        return float(d)
    if isinstance(d, (np.integer,)):
        return int(d)
    if isinstance(d, np.bool_):
        return bool(d)
    if isinstance(d, np.ndarray):
        return d.tolist()
    return d




# ----------------------------------------------------------------------------- pass / fail against stated tolerances

def check_a(r: dict) -> dict:
    P, T = PUBLISHED_A, TOL_A
    f = T["speed_frac"]
    jet_err = float(np.hypot(*(np.array(r["jet_end_ground_nmi"]) - P["jet_end_wind_nmi"])))
    jet_err_nw = float(np.hypot(*(np.array(r["jet_end_air_nmi"]) - P["jet_end_no_wind_nmi"])))
    rows = {
        "start_range_nmi": (r["start_range_nmi"], P["start_range_nmi"], abs(r["start_range_nmi"] - 8.0) <= T["position_nmi"]),
        "end_range_nmi": (r["end_range_nmi"], P["end_range_nmi"], abs(r["end_range_nmi"] - 6.8) <= T["position_nmi"]),
        "jet_end_no_wind_err_nmi": (jet_err_nw, 0.0, jet_err_nw <= T["position_nmi"]),
        "jet_end_wind_err_nmi": (jet_err, 0.0, jet_err <= T["position_nmi"]),
        "air_speed_start_kt": (r["air_speed_start_kt"], P["air_speed_start_kt"],
                               abs(r["air_speed_start_kt"] / P["air_speed_start_kt"] - 1) <= f),
        "ground_speed_start_kt": (r["ground_speed_start_kt"], P["ground_speed_start_kt"],
                                  abs(r["ground_speed_start_kt"] / P["ground_speed_start_kt"] - 1) <= f),
        "ground_speed_end_kt_over_120": (r["ground_speed_end_kt"], P["ground_speed_end_kt_above"],
                                         r["ground_speed_end_kt"] >= P["ground_speed_end_kt_above"] * (1 - f)),
        "ground_speed_min_frame": (r["ground_speed_min_frame"], P["ground_speed_min_frame"],
                                   abs(r["ground_speed_min_frame"] - P["ground_speed_min_frame"]) <= T["min_frame"]),
        "air_speed_under_50_frame": (r["air_velocity_reversal_frame"], P["air_speed_min_frame"],
                                     r["air_velocity_reversal_frame"] is not None
                                     and abs(r["air_velocity_reversal_frame"] - P["air_speed_min_frame"]) <= T["min_frame"]),
    }
    out = {k: {"lab": v[0], "published": v[1], "pass": bool(v[2])} for k, v in rows.items()}
    out["alt_change_ft_info_only"] = {"lab": r["alt_change_ft"], "published": P["alt_change_ft"], "pass": None}
    out["all_pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict) and v["pass"] is not None)
    return out


def check_a7(r: dict) -> dict:
    P, f = PUBLISHED_A7, TOL_A7["speed_frac"]
    rng = r["range_start_end_nmi"]
    rows = {
        "range_near_30_nmi": (rng, P["range_nmi"], all(abs(x - P["range_nmi"]) <= TOL_A7["range_nmi"] for x in rng)),
        "air_speed_start_kt": (r["air_speed_start_kt"], P["air_speed_start_kt"],
                               abs(r["air_speed_start_kt"] / P["air_speed_start_kt"] - 1) <= f),
        "air_speed_end_kt": (r["air_speed_end_kt"], P["air_speed_end_kt"],
                             abs(r["air_speed_end_kt"] / P["air_speed_end_kt"] - 1) <= f),
    }
    out = {k: {"lab": v[0], "published": v[1], "pass": bool(v[2])} for k, v in rows.items()}
    out["all_pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict))
    return out


def check_b(r: dict) -> dict:
    """Sitrec's premise (stated before the run): a constant-air-speed 340 kt path from 32 nmi exists
    (no-intersection frames under 5 percent), stays within 30 to 34 nmi, and is level within 500 ft
    (P&vR p. 16: in Sitrec the sight lines "flatten" near 30 nmi so a level path can be drawn)."""
    lo, hi = r["range_min_max_nmi"]
    a0, a1 = r["alt_min_max_ft"]
    rows = {
        "path_exists_bad_frames_under_5pct": (r["n_no_intersection_frames"], 0.05 * N, r["n_no_intersection_frames"] < 0.05 * N),
        "range_within_30_34_nmi": ([lo, hi], [30, 34], lo >= 30 and hi <= 34),
        "level_within_500_ft": (a1 - a0, 500, (a1 - a0) <= 500),
    }
    out = {k: {"lab": v[0], "criterion": v[1], "pass": bool(v[2])} for k, v in rows.items()}
    out["all_pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict))
    return out


# ----------------------------------------------------------------------------- attribution

A_KEYS = ["end_range_nmi", "ground_speed_min_frame", "air_velocity_reversal_frame", "air_speed_start_kt",
          "ground_speed_start_kt", "ground_speed_end_kt", "alt_change_ft", "all_intersections_in_front"]
B_KEYS = ["end_range_nmi", "alt_start_ft", "alt_end_ft", "n_no_intersection_frames", "air_heading_span_deg",
          "ground_speed_kt_min_max", "jet_heading_change_deg"]
A7_KEYS = ["range_start_end_nmi", "air_speed_start_kt", "air_speed_at_frame_700_kt", "air_speed_end_kt"]


def _pick(r: dict, keys: list[str]) -> dict:
    out = {k: r.get(k) for k in keys}
    if "straightness_top_view_good_frames" in r:
        out["max_dev_from_line_nmi"] = r["straightness_top_view_good_frames"]["max_dev_nmi"]
    return strip(out)


def lab_series_sitrec_numbering(el: float = -2.0, dT: float = 0.0) -> dict:
    """Lab inputs moved onto Sitrec's frame numbering (for one-at-a-time swaps)."""
    az, info = interval_azimuth(lab_azimuth_readings())
    return {"az": _shift_to_sitrec(az), "bank": _shift_to_sitrec(lab_bank_deg()),
            "tas": _shift_to_sitrec(lab_tas_kt(dT)), "tas_dT": _shift_to_sitrec(lab_tas_kt(9.5)), "az_info": info}


def attribution_a(base: Inputs, lab: dict, lab_inp: Inputs) -> dict:
    d = load_sitrec()
    g_az = -d["5 gaussian_smoothed_azimuth"].to_numpy(float)
    cloud = cloud_turn_rate(g_az)
    V: dict[str, dict] = {}

    def add(name, inp=None, **kw):
        V[name] = _pick(run_a(inp or base, **kw), A_KEYS)

    add("repro")
    add("tas_const_365", replace(base, tas_kt=_const(365.0)))
    add("tas_351_sitrec", replace(base, tas_kt=_const(351.0)))
    add("tas_lab_mach_isa", replace(base, tas_kt=lab["tas"]))
    add("tas_lab_mach_minus25C", replace(base, tas_kt=lab["tas_dT"]))
    add("turn_formula_exact_g", replace(base, turn="g"))
    add("turn_sitrec_g_351", replace(base, turn="g", g=SITREC_G, turn_tas_kt=_const(351.0)))
    add("turn_from_clouds_sitrec", replace(base, turn_override=cloud))
    add("bank_lab", replace(base, bank_deg=lab["bank"]))
    add("az_trailing_ma50", pvr_inputs(az_centered=False))
    add("az_sitrec_gaussian", replace(base, az_deg=g_az))
    add("az_lab_interval_spline", replace(base, az_deg=lab["az"]))
    add("az_plus_1deg_ramp", replace(base, az_deg=base.az_deg + np.linspace(0, 1, N)))
    add("el_const_-2.0", replace(base, el_deg=_const(-2.0)))
    add("el_const_-2.5", replace(base, el_deg=_const(-2.5)))
    add("el_const_-1.5", replace(base, el_deg=_const(-1.5)))
    add("fps_29.97", replace(base, fps=FPS))
    add("wind_sitrec_heading315_from270", wind_rel_deg=-45.0)
    add("wind_literal_to_west_heading315", wind_rel_deg=135.0)
    add("speed_smoothing_11", sg_window=11)
    add("speed_smoothing_31", sg_window=31)
    add("ALL_LAB", lab_inp)
    for el in (-2.5, -1.5):
        add(f"ALL_LAB_el_{el}", replace(lab_inp, el_deg=_const(el)))
    add("ALL_LAB_tas_minus25C", replace(lab_inp, tas_kt=lab_tas_kt(9.5)))
    add("ALL_LAB_literal_wind", lab_inp, wind_rel_deg=135.0)
    return V


def attribution_b(base: Inputs, lab: dict, lab_inp: Inputs) -> dict:
    cloud = cloud_turn_rate(base.az_deg)
    V: dict[str, dict] = {}

    def add(name, inp=None, **kw):
        V[name] = _pick(run_b(inp or base, **kw), B_KEYS)

    add("repro_bank")
    add("turn_from_clouds_sitrec_default", turn_rate=cloud)
    add("tas_365", replace(base, tas_kt=_const(365.0)))
    add("tas_lab_mach_isa", replace(base, tas_kt=lab["tas"]))
    add("bank_lab", replace(base, bank_deg=lab["bank"]))
    add("az_lab_interval_spline", replace(base, az_deg=lab["az"]))
    add("az_lab_with_clouds_turn", replace(base, az_deg=lab["az"]), turn_rate=cloud_turn_rate(lab["az"]))
    add("el_const_-2.0", replace(base, el_deg=_const(-2.0)))
    add("el_const_-2.5", replace(base, el_deg=_const(-2.5)))
    add("el_const_-1.5", replace(base, el_deg=_const(-1.5)))
    add("wind_literal_to_west", jet_wind=(90.0, 120.0), target_wind=(94.0, 65.0))
    add("clouds_wind_literal_to_west", turn_rate=cloud, jet_wind=(90.0, 120.0), target_wind=(94.0, 65.0))
    add("ALL_LAB_bank_turn", lab_inp)
    lab_cloud = cloud_turn_rate(lab_inp.az_deg, tas_kt=float(np.mean(lab_inp.tas_kt)))
    add("ALL_LAB_clouds_turn", lab_inp, turn_rate=lab_cloud)
    for el in (-2.5, -1.5):
        add(f"ALL_LAB_clouds_turn_el_{el}", replace(lab_inp, el_deg=_const(el)), turn_rate=lab_cloud)
    add("ALL_LAB_clouds_turn_literal_wind", lab_inp, turn_rate=lab_cloud, jet_wind=(90.0, 120.0), target_wind=(94.0, 65.0))
    return V


def attribution_a7(base_air: Inputs, base_ground: Inputs, lab: dict, lab_inp: Inputs) -> dict:
    d = load_sitrec()
    cloud = cloud_turn_rate(-d["5 gaussian_smoothed_azimuth"].to_numpy(float))
    V: dict[str, dict] = {}

    def add(name, inp, **kw):
        V[name] = _pick(run_a7(inp, **kw), A7_KEYS)

    add("repro_pvr_air_flat", base_air)
    add("sphere_earth", base_air, earth="sphere")
    add("sitrec_geometry_ground_flat", base_ground, geometry="ground")
    add("turn_from_clouds", replace(base_air, turn_override=cloud))
    add("tas_lab_mach_isa", replace(base_air, tas_kt=lab["tas"]))
    add("bank_lab", replace(base_air, bank_deg=lab["bank"]))
    add("az_lab_interval_spline", replace(base_air, az_deg=lab["az"]))
    add("ALL_LAB_air_flat", lab_inp)
    add("ALL_LAB_air_sphere", lab_inp, earth="sphere")
    return V


# ----------------------------------------------------------------------------- plots

def _plots(runs: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = []
    nm = F.NMI
    a_runs = [("A reproduction (P&vR inputs)", runs["A"], "C0", "-"), ("A with all lab inputs", runs["A_lab"], "C3", "--")]
    b_runs = [("B, bank turn rate (as specified)", runs["B"], "C0", "-"),
              ("B, Sitrec Match Clouds turn rate (port)", runs["B_clouds"], "C2", "-"),
              ("B, all lab inputs, clouds turn rate", runs["B_lab"], "C3", "--")]

    # top view
    fig, ax = plt.subplots(1, 3, figsize=(18, 6))
    for lab, r, c, ls in a_runs:
        s = r["_series"]
        jet = s["track"].air_pos / nm
        obj = s["obj"]["pos_air"] / nm
        ax[0].plot(jet[:, 0], jet[:, 1], color=c, ls=ls, lw=1.2, label=lab + ": jet (air frame)")
        ax[0].plot(obj[:, 0], obj[:, 1], color=c, ls=ls, lw=2.5, label=lab + ": object")
        for i in range(0, len(jet), 20):
            ax[0].plot([jet[i, 0], obj[i, 0]], [jet[i, 1], obj[i, 1]], color=c, lw=0.4, alpha=0.4)
    ax[0].set_title("A: P&vR close path, air frame (initial jet heading = up)")
    ax[0].set_xlabel("x (nmi)"); ax[0].set_ylabel("y (nmi)"); ax[0].set_aspect("equal"); ax[0].legend(fontsize=7)
    for lab, r, c, ls in b_runs:
        s = r["_series"]
        jet = s["track"].ground_pos / nm
        obj = s["obj"]["pos"] / nm
        ax[1].plot(jet[:, 0], jet[:, 1], color=c, ls=ls, lw=1.2)
        ax[1].plot(obj[:, 0], obj[:, 1], color=c, ls=ls, lw=2.5, label=lab)
        bad = s["obj"]["bad"]
        if bad.any():
            ax[1].plot(obj[bad, 0], obj[bad, 1], "x", color=c, ms=3)
        for i in range(0, N, 200):
            ax[1].plot([jet[i, 0], obj[i, 0]], [jet[i, 1], obj[i, 1]], color=c, lw=0.4, alpha=0.4)
        ax[2].plot(obj[:, 0], obj[:, 1], color=c, ls=ls, lw=2, label=lab)
        ax[2].plot(obj[0, 0], obj[0, 1], "o", color=c, ms=4)
        if bad.any():
            ax[2].plot(obj[bad, 0], obj[bad, 1], "x", color=c, ms=3)
    ax[1].set_title("B: Sitrec-style far path, ground frame (north up)")
    ax[1].set_xlabel("east (nmi)"); ax[1].set_ylabel("north (nmi)"); ax[1].set_aspect("equal"); ax[1].legend(fontsize=7)
    ax[2].set_title("B: object paths, zoomed (dot = frame 0, x = no-intersection frames)")
    ax[2].set_xlabel("east (nmi)"); ax[2].set_ylabel("north (nmi)"); ax[2].set_aspect("equal"); ax[2].legend(fontsize=7)
    fig.tight_layout(); p = OUT_DIR / "gimbal_topview.png"; fig.savefig(p, dpi=110); plt.close(fig); files.append(p.name)

    # range
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    for lab, r, c, ls in a_runs:
        s = r["_series"]
        ax[0].plot(s["frames"], s["obj"]["range_m"] / nm, color=c, ls=ls, label=lab)
    ax[0].axhline(8.0, color="k", lw=0.5); ax[0].axhline(6.8, color="k", lw=0.5, ls=":")
    ax[0].set_title("A: range (published 8.0 to 6.8 nmi)"); ax[0].set_xlabel("frame"); ax[0].set_ylabel("nmi"); ax[0].legend(fontsize=8)
    for lab, r, c, ls in b_runs:
        ax[1].plot(np.arange(N), r["_series"]["obj"]["range_m"] / nm, color=c, ls=ls, label=lab)
    ax[1].set_title("B: range"); ax[1].set_xlabel("frame"); ax[1].set_ylabel("nmi"); ax[1].legend(fontsize=8)
    fig.tight_layout(); p = OUT_DIR / "gimbal_range.png"; fig.savefig(p, dpi=110); plt.close(fig); files.append(p.name)

    # speed
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    for lab, r, c, ls in a_runs:
        s = r["_series"]
        ax[0].plot(s["frames"], s["as_kt"], color=c, ls=ls, label=lab + ": air speed")
        ax[0].plot(s["frames"], s["gs_kt"], color=c, ls=ls, lw=0.8, alpha=0.6, label=lab + ": ground speed")
    ax[0].axvline(720, color="k", lw=0.5, ls=":"); ax[0].axvline(900, color="k", lw=0.5, ls=":")
    ax[0].set_title("A: object speed (P&vR: air 400 kt falling below 50 near f900; ground min near f720)")
    ax[0].set_xlabel("frame"); ax[0].set_ylabel("kt"); ax[0].legend(fontsize=7)
    for lab, r, c, ls in [("A7 reproduction (P&vR inputs, flat Earth)", runs["A7"], "C0", "-"),
                          ("A7 all lab inputs", runs["A7_lab"], "C3", "--"),
                          ("A7 with Sitrec clouds turn rate", runs["A7_clouds"], "C2", "-")]:
        ax[1].plot(np.arange(N), r["_series"]["as_kt"], color=c, ls=ls, label=lab)
    ax[1].axhline(300, color="k", lw=0.5, ls=":"); ax[1].axhline(450, color="k", lw=0.5, ls=":")
    ax[1].set_ylim(0, 900)
    ax[1].set_title("A7: level path at 18,700 ft, implied air speed (P&vR: 300 to 450 kt)")
    ax[1].set_xlabel("frame"); ax[1].set_ylabel("kt"); ax[1].legend(fontsize=7)
    fig.tight_layout(); p = OUT_DIR / "gimbal_speed.png"; fig.savefig(p, dpi=110); plt.close(fig); files.append(p.name)

    # altitude
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    for lab, r, c, ls in a_runs:
        s = r["_series"]
        ax[0].plot(s["frames"], s["obj"]["alt_m"] / F.FT, color=c, ls=ls, label=lab)
    ax[0].set_title("A: object altitude (P&vR: climbs about 250 ft)"); ax[0].set_xlabel("frame"); ax[0].set_ylabel("ft"); ax[0].legend(fontsize=8)
    for lab, r, c, ls in b_runs:
        ax[1].plot(np.arange(N), r["_series"]["obj"]["alt_m"] / F.FT, color=c, ls=ls, label=lab)
    ax[1].set_title("B: object altitude (spherical Earth)"); ax[1].set_xlabel("frame"); ax[1].set_ylabel("ft"); ax[1].legend(fontsize=8)
    fig.tight_layout(); p = OUT_DIR / "gimbal_altitude.png"; fig.savefig(p, dpi=110); plt.close(fig); files.append(p.name)
    return files


# ----------------------------------------------------------------------------- main

def compute_all() -> dict:
    d = load_sitrec()
    a_in = pvr_inputs()
    b_in = sitrec_inputs()
    lab_inp, az_info = lab_inputs()
    lab = lab_series_sitrec_numbering()
    cloud = cloud_turn_rate(b_in.az_deg)
    lab_cloud = cloud_turn_rate(lab_inp.az_deg, tas_kt=float(np.mean(lab_inp.tas_kt)))
    runs = {
        "A": run_a(a_in),
        "A_lab": run_a(lab_inp),
        "B": run_b(b_in),
        "B_clouds": run_b(b_in, turn_rate=cloud),
        "B_lab": run_b(lab_inp, turn_rate=lab_cloud),
        "B_lab_bank": run_b(lab_inp),
        "A7": run_a7(a_in),
        "A7_lab": run_a7(lab_inp),
        "A7_clouds": run_a7(replace(a_in, turn_override=cloud_turn_rate(-d["5 gaussian_smoothed_azimuth"].to_numpy(float)))),
    }
    bank_rate = turn_rate_deg_s(b_in)
    res = {
        "work_item": "M2.7 GIMBAL",
        "frame_numbering": "A and B: Sitrec 0-based frames; runs named *lab* use the lab's frames (lab = Sitrec + 1)",
        "tolerances": {"A": TOL_A, "A7": TOL_A7,
                       "B": "constant-air-speed path exists (<5% no-intersection frames), range within 30-34 nmi, level within 500 ft"},
        "published": {"A": PUBLISHED_A, "A7": PUBLISHED_A7},
        "inputs": {"A": a_in.notes, "B": b_in.notes, "lab": strip(lab_inp.notes)},
        "A_repro": strip(runs["A"]), "A_check": check_a(runs["A"]),
        "A_lab": strip(runs["A_lab"]),
        "A7_repro": strip(runs["A7"]), "A7_check": check_a7(runs["A7"]),
        "A7_lab": strip(runs["A7_lab"]), "A7_clouds": strip(runs["A7_clouds"]),
        "B_repro_bank": strip(runs["B"]), "B_check_bank": check_b(runs["B"]),
        "B_clouds_port": strip(runs["B_clouds"]), "B_check_clouds": check_b(runs["B_clouds"]),
        "B_lab_clouds": strip(runs["B_lab"]), "B_lab_bank": strip(runs["B_lab_bank"]),
        "turn_rate_bank_vs_clouds_deg_s_every_100_frames": {
            "frames": list(range(0, N, 100)), "bank_sitrec_351": np.round(bank_rate[::100], 3).tolist(),
            "clouds_port": np.round(cloud[::100], 3).tolist(),
            "heading_change_bank_deg": float(np.sum(bank_rate[:-1]) / FPS),
            "heading_change_clouds_deg": float(np.sum(cloud[:-1]) / FPS)},
        "lab_azimuth_fit": az_info,
        "attribution_A": attribution_a(a_in, lab, lab_inp),
        "attribution_B": attribution_b(b_in, lab, lab_inp),
        "attribution_A7": attribution_a7(a_in, b_in, lab, lab_inp),
    }
    res["_runs"] = runs
    return res


def main() -> int:
    res = compute_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res["plots"] = _plots(res.pop("_runs"))
    out = OUT_DIR / "gimbal.json"
    out.write_text(json.dumps(strip(res), indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("A_check", "A7_check", "B_check_bank", "B_check_clouds")}, indent=1, default=str))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
