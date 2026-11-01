"""Per-frame predictions for the app's cockpit and god's-eye views (M4.3, M4.4).

Read-only use of solve/: loads each case through solve.case_data.load_case, rebuilds every stored fit's
prediction with solve.score.predict (the scorer's own forward model, at the parameters stored in
data/derived/<case>/results.json) and fits the rotation terms with solve.score.rotation_terms. Nothing
here re-fits a hypothesis or changes a number the scorer reports; it only evaluates the stored fits on
every frame so the browser can draw them.

Camera model used by the re-render (shared with app/js/geom.js; tests/js/geom.test.mjs checks parity):
- the camera sits at the jet and looks along the hypothesis's predicted line of sight (the pod tracks
  the object, so every model puts the object on the boresight);
- it is rolled so the world horizon appears at the image horizon angle theta
  (sensor_atflir.human_horizon_v with the fit's jet pitch and the measured bank, on the predicted sight
  line): with f the forward unit vector, r0 = unit(f x up) and u0 = r0 x f, the image axes are
  r = r0 cos(theta) - u0 sin(theta) and u = r0 sin(theta) + u0 cos(theta);
- pinhole projection onto the frame: x = cx + f_x (d.r)/(d.f), y = cy - f_y (d.u)/(d.f), with
  f_x = (picture width / 2) / tan(fov / 2) and f_y = f_x / pixel_aspect_x.

Frame-lock metric (CP-05): median over frames of
- object: distance (px) between the measured blob centroid and the predicted image position;
- horizon: (picture width / 2) x |sin(theta_pred - theta_meas)| (px), the offset between the predicted
  and the measured horizon lines at the picture's left and right edges. theta_meas is measured only
  where the image shows a horizon reference: GIMBAL's cloud deck, whose texture moves along the image
  horizon (solve/cloud_motion.py), so its motion direction measures the horizon angle (frames where the
  cloud tile moves at least 1 px/frame). GOFAST looks down at the sea and FLIR1 at a featureless sky:
  no measured horizon, metric n/a.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Active picture centre (frame px, pixel centres at integers) and size, per derived folder.
# GIMBAL / GOFAST: 640 x 480 copies, picture columns 104.5 to 530.5 (solve/cases/*.yaml picture_width_px 426);
# FLIR1: 352 x 264 copy, picture columns 52 to 295 (solve/cases/flir1.yaml).
PICTURE = {
    "gimbal": {"frame_w": 640, "frame_h": 480, "cx": 317.5, "cy": 239.5, "width_px": 426.0},
    "gofast": {"frame_w": 640, "frame_h": 480, "cx": 317.5, "cy": 239.5, "width_px": 426.0},
    "flir1_navy": {"frame_w": 352, "frame_h": 264, "cx": 173.5, "cy": 131.5, "width_px": 244.0},
}
SOLVE_CASE = {"gimbal": "gimbal", "gofast": "gofast", "flir1_navy": "flir1"}
MIN_CLOUD_PX = 1.0   # px/frame: below this the cloud motion direction is not a usable horizon reference
HORIZON_MEDIAN_FRAMES = 15   # running median of the per-frame direction (single-frame motion estimates are noisy)


def _r(a, nd):
    a = np.asarray(a, float)
    return [None if not np.isfinite(x) else round(float(x), nd) for x in a]


def wrap90(a):
    return (np.asarray(a, float) + 90.0) % 180.0 - 90.0


def camera_basis(f: np.ndarray, theta_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Image right / up unit vectors (N, 3) for forward vectors f (N, 3, ENU) rolled to horizon angle theta."""
    f = f / np.linalg.norm(f, axis=-1, keepdims=True)
    up = np.array([0.0, 0.0, 1.0])
    r0 = np.cross(f, up)
    r0 /= np.linalg.norm(r0, axis=-1, keepdims=True)
    u0 = np.cross(r0, f)
    th = np.radians(np.asarray(theta_deg, float))[:, None]
    return r0 * np.cos(th) - u0 * np.sin(th), r0 * np.sin(th) + u0 * np.cos(th)


def project(cam: np.ndarray, f: np.ndarray, r: np.ndarray, u: np.ndarray, p: np.ndarray, pic: dict,
            fov_deg, pixel_aspect: float) -> tuple[np.ndarray, np.ndarray]:
    """Frame px of points p seen from cam (all (N, 3)); see the module docstring."""
    fx = (pic["width_px"] / 2.0) / np.tan(np.radians(np.asarray(fov_deg, float)) / 2.0)
    fy = fx / pixel_aspect
    f = f / np.linalg.norm(f, axis=-1, keepdims=True)
    d = p - cam
    z = np.sum(d * f, axis=-1)
    return pic["cx"] + fx * np.sum(d * r, axis=-1) / z, pic["cy"] - fy * np.sum(d * u, axis=-1) / z


def frame_lock(pred_x, pred_y, pred_theta, meas_x, meas_y, meas_theta, width_px: float) -> dict:
    """Median pixel errors (object position, horizon) between a re-render and the original."""
    ex = np.hypot(np.asarray(pred_x, float) - np.asarray(meas_x, float), np.asarray(pred_y, float) - np.asarray(meas_y, float))
    eh = (width_px / 2.0) * np.abs(np.sin(np.radians(wrap90(np.asarray(pred_theta, float) - np.asarray(meas_theta, float)))))
    ok_o, ok_h = np.isfinite(ex), np.isfinite(eh)
    return {"object_px_median": float(np.median(ex[ok_o])) if ok_o.any() else None, "object_n": int(ok_o.sum()),
            "horizon_px_median": float(np.median(eh[ok_h])) if ok_h.any() else None, "horizon_n": int(ok_h.sum())}


def measured(folder: str, n: int, pixel_aspect: float) -> dict:
    """Measured references per frame: object centroid and (GIMBAL) the cloud-motion horizon angle."""
    d = pd.read_csv(ROOT / "data" / "derived" / folder / "image_track.csv").set_index("frame").reindex(range(n))
    found = d["obj_found"].fillna(0).to_numpy() == 1
    cx = np.where(found, d["obj_hi_cx"].to_numpy(float), np.nan)
    cy = np.where(found, d["obj_hi_cy"].to_numpy(float), np.nan)
    theta = np.full(n, np.nan)
    src = None
    if "cloud_dx" in d:
        dx = d["cloud_dx"].to_numpy(float) / pixel_aspect
        dy = d["cloud_dy"].to_numpy(float)
        ok = np.hypot(dx, dy) >= MIN_CLOUD_PX
        raw = np.where(ok, wrap90(np.degrees(np.arctan2(-dy, dx))), np.nan)
        k = HORIZON_MEDIAN_FRAMES
        med = pd.Series(raw).rolling(k, center=True, min_periods=k // 2 + 1).median().to_numpy()
        theta = np.where(ok, med, np.nan)
        src = (f"cloud-deck motion direction (image_track.csv cloud_dx, cloud_dy, x corrected for pixel aspect "
               f"{pixel_aspect}), {k}-frame running median; frames moving at least {MIN_CLOUD_PX:g} px/frame")
    return {"obj_cx": cx, "obj_cy": cy, "horizon_deg": theta, "horizon_source": src}


def _accel_g(t: np.ndarray, vel: np.ndarray, window: np.ndarray) -> float:
    a = np.gradient(vel[window], t[window], axis=0)
    return float(np.max(np.linalg.norm(a, axis=-1)) / 9.80665)


def case_predictions(folder: str, results: dict | None) -> dict:
    """Everything the cockpit and god's-eye views draw for one case (see build_app_data.py)."""
    from solve import score as S
    from solve.case_data import fov_per_frame, load_case
    from solve.models.base import Prediction  # noqa: F401  (documents the source of the fields)
    from solve.sensor_atflir import human_horizon_v, los_level_frame  # noqa: F401

    pic = PICTURE[folder]
    cname = SOLVE_CASE[folder]
    out: dict = {"picture": pic, "variants": {}, "method": __doc__.split("\n\n")[1].replace("\n", " ")}
    vmap = {}
    if results is not None:
        vmap = results["variants"] if "variants" in results else {results.get("variant", "") or "": results}
    names = list(vmap) or [""]
    hyps = {h.id: h for h in S.load_hypotheses()}
    base_meas = None
    for vn in names:
        case = load_case(cname, variant=vn or None)
        n = len(case.t)
        sens = case.cfg["sensor"]
        aspect = float(sens.get("pixel_aspect_x", 1.0))
        if base_meas is None:
            base_meas = measured(folder, n, aspect)
            out["measured"] = {"obj_cx": _r(base_meas["obj_cx"], 2), "obj_cy": _r(base_meas["obj_cy"], 2),
                               "horizon_deg": _r(base_meas["horizon_deg"], 3), "horizon_source": base_meas["horizon_source"],
                               "object_source": f"data/derived/{folder}/image_track.csv obj_hi_cx, obj_hi_cy (obj_found)"}
        sym = pd.read_csv(ROOT / case.cfg["files"]["symbology"], dtype=str)
        sym["frame"] = sym["frame"].astype(int)
        fovf = fov_per_frame(case.cfg, sym, n)
        fov = np.asarray(fovf, float) if fovf is not None else np.full(n, float(sens["fov_deg"]))
        pitch0 = S._jet_pitch(case, {})
        readout_h = human_horizon_v(pitch0, case.bank, case.az_read, case.el_read)
        vout = {"fov_deg": float(sens["fov_deg"]), "fov_by_frame": _r(fov, 4) if fovf is not None else None,
                "pixel_aspect_x": aspect, "ppd": case.ppd, "window_frames": [int(case.window[0]), int(case.window[-1])],
                "readout_horizon_deg": _r(readout_h, 3),
                "readout_horizon_note": ("Image horizon from the readout angles (whole degrees) and the measured bank, "
                                         f"jet pitch {np.nanmedian(np.atleast_1d(pitch0)):.1f} deg (case default); no hypothesis."),
                "hypotheses": {}}
        v = vmap.get(vn)
        for h in (v or {}).get("hypotheses", []):
            if not h.get("valid") or h["hypothesis"] not in hyps:
                continue
            hyp = hyps[h["hypothesis"]]
            fits = {}
            for tag, pkey in (("testimony_weighted", "params_testimony_weighted_fit"), ("physics_only", "params_physics_only_fit")):
                params = h.get(pkey)
                if not params:
                    continue
                fits[tag] = one_fit(S, case, hyp, params, pic, fov, aspect, base_meas)
            vout["hypotheses"][h["hypothesis"]] = fits
        out["variants"][vn] = vout
    return out


def one_fit(S, case, hyp, params: dict, pic: dict, fov: np.ndarray, aspect: float, meas: dict) -> dict:
    from solve.sensor_atflir import human_horizon_v

    pred = S.predict(case, hyp, params)
    if not pred.valid:
        return {"valid": False, "reason": pred.reason}
    jet_wind = case.env.wind_enu(float(np.nanmedian(case.jet_alt)))
    jet = S._jet_model(case).state(params.get("jet_heading_deg", 0.0), jet_wind,
                                   turn_rate_z=params.get("turn_rate_z", 0.0), pitch_deg=S._jet_pitch(case, params))
    n = len(case.t)
    theta = human_horizon_v(jet.pitch_deg, case.bank, pred.az, pred.el)
    f = pred.obj_pos - jet.pos
    r, u = camera_basis(f, theta)
    px, py = project(jet.pos, f, r, u, pred.obj_pos, pic, fov, aspect)

    rot = np.full(n, np.nan)
    if pred.rotation_base is not None and "rotation" in case.series:
        _, _, rf = S.rotation_terms(case, pred)
        s = case.series["rotation"]
        rot[s.frames] = wrap90(rf["fitted"])
    size = np.full(n, np.nan)
    if "size_trend" in case.series:
        s = case.series["size_trend"]
        p = pred.size_log[s.frames]
        for sg in np.unique(s.segment):
            m = (s.segment == sg) & np.isfinite(p)
            size[s.frames[m]] = np.exp(p[m] - np.mean(p[m]) + np.mean(s.obs[m]))
    lock = frame_lock(px, py, theta, meas["obj_cx"], meas["obj_cy"], meas["horizon_deg"], pic["width_px"])
    w = case.window
    return {
        "valid": True,
        "az_deg": _r(pred.az, 4), "el_deg": _r(pred.el, 4), "range_m": _r(pred.range_m, 1),
        "horizon_deg": _r(theta, 3), "rotation_deg": _r(rot, 2), "rotation_kind": pred.rotation_kind,
        "size_px": _r(size, 2), "img_x": _r(px, 3), "img_y": _r(py, 3),
        "obj_e": _r(pred.obj_pos[:, 0], 1), "obj_n": _r(pred.obj_pos[:, 1], 1), "obj_u": _r(pred.obj_pos[:, 2], 1),
        "jet_e": _r(jet.pos[:, 0], 1), "jet_n": _r(jet.pos[:, 1], 1), "jet_u": _r(jet.pos[:, 2], 1),
        "jet_pitch_deg": float(np.nanmedian(np.atleast_1d(jet.pitch_deg))),
        "max_accel_g": _accel_g(case.t, pred.obj_vel, w),
        "frame_lock": lock,
    }


def range_curves_csv(folder: str) -> dict | None:
    """Per-hypothesis curves over assumed range (data/derived/<case>/range_curves.csv), when the scorer wrote them.

    Columns are passed through as they are (numbers as numbers); rows are grouped by variant (if the column
    exists) and hypothesis. Known columns the range explorer draws when present: range_nmi, air_speed_kt,
    ground_speed_kt, altitude_ft_mean, max_accel_g, line_of_sight_loglik, total_physics_only, total_testimony_weighted.
    """
    p = ROOT / "data" / "derived" / folder / "range_curves.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    hcol = next((c for c in ("hypothesis", "hyp", "id") if c in d.columns), None)
    if hcol is None or "range_nmi" not in d.columns:
        return {"source": str(p.relative_to(ROOT)).replace("\\", "/"), "error": "no hypothesis or range_nmi column", "variants": {}}
    vcol = "variant" if "variant" in d.columns else None
    out: dict = {}
    for _, row in d.iterrows():
        vn = "" if vcol is None or pd.isna(row[vcol]) else str(row[vcol])
        rec = {}
        for k, x in row.items():
            if k in (hcol, vcol):
                continue
            if isinstance(x, (int, float, np.integer, np.floating)):
                rec[k] = None if not math.isfinite(float(x)) else float(x)
            elif isinstance(x, (bool, np.bool_)):
                rec[k] = bool(x)
            else:
                rec[k] = None if pd.isna(x) else str(x)
        out.setdefault(vn, {}).setdefault(str(row[hcol]), []).append(rec)
    for vd in out.values():
        for rows in vd.values():
            rows.sort(key=lambda r: (r.get("range_nmi") is None, r.get("range_nmi") or 0))
    return {"source": str(p.relative_to(ROOT)).replace("\\", "/"), "columns": list(d.columns), "variants": out}


def testimony_claims(cid: str) -> list:
    """Every testimony claim for a case with its source, and how the scorer uses it (data/testimony)."""
    import yaml

    tdir = ROOT / "data" / "testimony"
    f = tdir / f"{cid}.yaml"
    if not f.exists():
        return []
    claims = yaml.safe_load(f.read_text(encoding="utf-8")) or []
    sc = yaml.safe_load((tdir / "scorable.yaml").read_text(encoding="utf-8")) or {}
    entries = ((sc.get("cases") or {}).get(cid) or {}).get("claims") or {}
    out = []
    for c in claims:
        src = c.get("source") or {}
        e = entries.get(c.get("id"), {}) if isinstance(entries, dict) else {}
        out.append({
            "id": c.get("id"), "witness": c.get("witness"), "firsthand": c.get("firsthand"),
            "claim": c.get("claim"), "quote": c.get("quote"), "quantity": c.get("quantity"), "value": c.get("value"),
            "uncertainty": c.get("uncertainty"), "source_title": src.get("title"), "source_outlet": src.get("outlet"),
            "source_date": src.get("date"), "source_url": src.get("url"), "location": c.get("location_in_source"),
            "verification": c.get("verification"),
            "scorable": e.get("scorable"), "use": e.get("use"), "kind": e.get("kind"), "why": e.get("why"),
        })
    return out
