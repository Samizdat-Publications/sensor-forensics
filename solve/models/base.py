"""Predicted observables shared by every physical model.

A model only decides WHERE the object is (a path in the tangent frame) and what kind
of emitter it is (a real object whose size scales as 1/range, or a glare whose size
is set by its brightness and whose orientation follows the pod's derotation). From
that, this module computes every observable the scorer tests, the same way for all
models: line of sight (pod az / el), slant range, closure rate, apparent size factor,
brightness factor, glare rotation, ocean image motion, and the scalar quantities that
testimony can test (range, altitude, speed, minimum ground speed, stop / reverse,
motion relative to the wind, implied size).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import frames as F
from ..sensor_atflir import glare_angle_base_v, human_horizon_v
from .geometry import JetState, angles_from, height_of, los_enu, range_to_height, sea_range


@dataclass
class Prediction:
    valid: bool
    az: np.ndarray | None = None              # deg, all frames
    el: np.ndarray | None = None
    range_m: np.ndarray | None = None
    closure_mps: np.ndarray | None = None
    size_log: np.ndarray | None = None        # log apparent size factor (un-normalized)
    brightness_log: np.ndarray | None = None  # log brightness factor (un-normalized)
    rotation_base: np.ndarray | None = None   # deg, predicted image orientation up to the fitted terms (see below)
    rotation_kind: str = ""                   # "glare" (fixed in the optics) or "physical" (free smooth rotation)
    background_px: np.ndarray | None = None   # px/frame, ocean image motion at the boresight
    obj_pos: np.ndarray | None = None
    obj_alt: np.ndarray | None = None
    obj_vel: np.ndarray | None = None
    air_vel: np.ndarray | None = None
    scalars: dict = field(default_factory=dict)
    testimony_quantities: dict = field(default_factory=dict)  # keys from the testimony vocabulary only
    reason: str = ""


INVALID = Prediction(valid=False, reason="infeasible geometry")


def anchor(case, jet: JetState, params: dict) -> tuple[np.ndarray, float] | None:
    """Object position (tangent frame) and height at the case's reference frame.

    The object sits on the reference frame's line of sight (readout + the shared anchor
    offsets) at `range_ref_nmi`, or where that sight line reaches `altitude_ref_ft`.
    """
    i = case.ref_frame
    az = case.az_read[i] + params.get("anchor_daz_deg", 0.0)
    el = case.el_read[i] + params.get("anchor_del_deg", 0.0)
    j = case.cfg["jet"]
    u = los_enu(jet, i, az, el, case.bank[i], float(j.get("pitch_deg", 0.0)), j.get("convention", "level"))
    if "range_ref_nmi" in params:
        r = params["range_ref_nmi"] * F.NMI
    elif "altitude_ref_ft" in params:
        r = range_to_height(jet.pos[i], u, params["altitude_ref_ft"] * F.FT)
    else:
        raise KeyError("a model needs range_ref_nmi or altitude_ref_ft")
    if not np.isfinite(r) or r <= 0:
        return None
    p = jet.pos[i] + r * u
    return p, float(height_of(p))


def object_wind(case, h_m: float, params: dict) -> np.ndarray:
    """Wind (m/s, toward) at the object's altitude, including the shared wind-error parameters."""
    w = case.env.wind_enu(h_m)
    return w + np.array([params.get("wind_err_e_kt", 0.0), params.get("wind_err_n_kt", 0.0)]) * F.KT


def observables(case, jet: JetState, pos: np.ndarray, vel: np.ndarray, air_vel: np.ndarray,
                wind_xy: np.ndarray, size_model: str, glare: bool) -> Prediction:
    rel = pos - jet.pos
    az, el, rng = angles_from(jet, rel)
    if not np.all(np.isfinite(rng)) or np.any(rng <= 1.0):
        return Prediction(valid=False, reason="object at the jet")
    closure = -np.sum(rel * (vel - jet.vel), axis=-1) / rng
    if size_model == "inverse_range":
        size_log = -np.log(rng)
    elif size_model == "brightness_sqrt":
        size_log = 0.5 * case.brightness_log_all
    else:
        raise ValueError(f"unknown size model {size_model!r}")
    brightness_log = -2.0 * np.log(rng)

    # Image rotation of the object (the rotation criterion). The model registry decides the kind:
    # a glare fixed in the pod optics is displayed at g0 + derotation (sensor_atflir.glare_angle_base_v,
    # Sitrec's model; g0 is fitted by the scorer); a physical object keeps its own attitude, so its
    # image orientation is the displayed horizon plus a free smooth rotation (fitted by the scorer and
    # charged by the complexity penalty). Both are evaluated on the model's own predicted sight line.
    rot_base, rot_kind = None, ""
    if "rotation" in case.criteria:
        pitch = jet.pitch_deg
        if glare:
            rot_base, rot_kind = glare_angle_base_v(el, az, pitch, case.bank), "glare"
        else:
            rot_base, rot_kind = human_horizon_v(pitch, case.bank, az, el), "physical"

    u = rel / rng[:, None]
    if "background_motion" in case.series:
        s = sea_range(jet.pos, u)
        vj = jet.vel
        d_dot = -(vj - np.sum(vj * u, axis=-1)[:, None] * u) / s[:, None]
        u_dot = np.gradient(u, case.t, axis=0)
        flow = np.linalg.norm(d_dot - u_dot, axis=-1)
        bg_px = np.degrees(flow) * case.ppd / case.fps
    else:
        bg_px = None   # background motion enters through the jet's measured turn rate (GIMBAL)

    alt = height_of(pos)
    pred = Prediction(valid=True, az=az, el=el, range_m=rng, closure_mps=closure, size_log=size_log,
                      brightness_log=brightness_log, rotation_base=rot_base, rotation_kind=rot_kind, background_px=bg_px,
                      obj_pos=pos, obj_alt=alt, obj_vel=vel, air_vel=air_vel)
    pred.scalars = scalar_quantities(case, pred, wind_xy)
    for k in ("reversal_radius_ft", "stops_and_reverses", "motion_vs_wind", "range_trend"):
        pred.scalars[k] = pred.testimony_quantities[k]
    return pred


def scalar_quantities(case, pred: Prediction, wind_xy: np.ndarray) -> dict:
    w = case.window
    gv = pred.obj_vel[w, :2]
    gs = np.linalg.norm(gv, axis=-1)
    mean_dir = gv.mean(axis=0)
    nd = np.linalg.norm(mean_dir)
    reverse = bool(nd > 0 and np.any(gv @ (mean_dir / nd) < 0))
    av = pred.air_vel[w]
    air_h = av[:, :2].mean(axis=0)
    wmag = float(np.linalg.norm(wind_xy))
    vs_wind = None
    if np.linalg.norm(air_h) > 1.0 * F.KT and wmag > 1.0 * F.KT:
        c = np.dot(air_h, wind_xy) / (np.linalg.norm(air_h) * wmag)
        vs_wind = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
    size_px = np.nanmedian(case.size_px_all[w]) if np.any(np.isfinite(case.size_px_all[w])) else np.nan
    rng_med = float(np.median(pred.range_m[w]))
    implied = float(np.radians(size_px / case.ppd) * rng_med) if np.isfinite(size_px) else None

    # Testimony vocabulary (data/testimony/scorable.yaml, definitions followed literally).
    env_wind = case.env.wind_enu(pred.obj_alt[w])                 # modeled wind, no fitted error term
    air_h = np.linalg.norm(gv - env_wind, axis=-1)
    t = case.t[w]
    acc = np.gradient(pred.obj_vel[w], t, axis=0)
    vv = pred.obj_vel[w]
    sp = np.linalg.norm(vv, axis=-1)
    kappa = np.linalg.norm(np.cross(vv, acc), axis=-1) / np.maximum(sp, 1e-6) ** 3
    radius_ft = float(min(1e6, 1.0 / max(float(np.max(kappa)), 1e-30) / F.FT))
    lag = int(round(3.0 * case.fps))
    stops = False
    for i in np.flatnonzero(gs < 20 * F.KT):
        if i - lag < 0 or i + lag >= len(gs):
            continue
        a, b = gv[i - lag], gv[i + lag]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na > 0 and nb > 0 and np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1))) >= 120:
            stops = True
            break
    wm = env_wind.mean(axis=0)
    if np.linalg.norm(wm) > 0:
        down = float(np.median(gv @ (wm / np.linalg.norm(wm)))) / F.KT
        mvw = "against" if down < -10 else ("with" if down > 10 else "neither")
    else:
        mvw = "neither"
    r0, r1 = pred.range_m[w[0]], pred.range_m[w[-1]]
    trend = "decreasing" if r1 < 0.99 * r0 else ("increasing" if r1 > 1.01 * r0 else "constant")
    size_ft_series = np.radians(case.size_px_all[w] / case.ppd) * pred.range_m[w] / F.FT
    pred.testimony_quantities = {
        "range_nmi": pred.range_m[w] / F.NMI,
        "object_altitude_ft": pred.obj_alt[w] / F.FT,
        "ground_speed_kt": gs / F.KT,
        "air_speed_kt": air_h / F.KT,
        "min_ground_speed_kt": float(np.min(gs) / F.KT),
        "size_ft": size_ft_series,
        "reversal_radius_ft": radius_ft,
        "stops_and_reverses": bool(stops),
        "motion_vs_wind": mvw,
        "range_trend": trend,
    }
    return {
        "range_nmi_mean": float(np.mean(pred.range_m[w]) / F.NMI),
        "altitude_ft_mean": float(np.mean(pred.obj_alt[w]) / F.FT),
        "altitude_ft_min": float(np.min(pred.obj_alt[w]) / F.FT),
        "altitude_ft_max": float(np.max(pred.obj_alt[w]) / F.FT),
        "air_speed_kt": float(np.mean(np.linalg.norm(av, axis=-1)) / F.KT),
        "ground_speed_kt": float(np.mean(gs) / F.KT),
        "min_ground_speed_kt": float(np.min(gs) / F.KT),
        "ground_track_deg": float(np.degrees(np.arctan2(mean_dir[0], mean_dir[1])) % 360) if nd > 0 else None,
        "vertical_speed_fpm": float(np.mean(pred.obj_vel[w, 2]) / F.FT * 60.0),
        "stop_reverse": reverse,
        "motion_vs_wind_deg": vs_wind,
        "against_wind": None if vs_wind is None else bool(vs_wind > 90.0),
        "wind_at_object_kt": wmag / F.KT,
        "implied_size_upper_m": implied,
    }
