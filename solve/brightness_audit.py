"""Brightness criterion audit (REVIEW-M3 item 1, Rule B in docs/results/REVIEW-M3.md).

Decides, per video and by a rule written before the measurements, whether the measured
brightness (ln of the low-threshold integrated contrast, the series the scorer fits) can carry
range information, or is dominated by the sensor:

- B1 saturation: the blob is saturated on a frame when at least 3 of its pixels sit within 2
  codes of the clip code on the object's side (extract.frame_levels); fails if more than half of
  the scored frames are saturated.
- B2 gain and level: the series, centered per polarity segment, regressed on the natural logs
  of the whole-picture median level and robust contrast and of the background tile's median
  level and robust contrast (also centered per segment); fails if R squared, adjusted for 4
  regressors with the criterion's own n_eff, exceeds 0.5.
- B3 zoom: fails if the zoom readout changes inside a polarity segment of the scored window.

Supporting evidence (not part of the decision): steps found at the same frame in the object's
brightness and in the frame-level level or contrast.

The decision is written to data/derived/<case>/brightness_audit.json; solve/case_data.py reads it
(image.brightness_audit in the case YAML) and, when the criterion is not range-informative, gives
it weight 0 for every hypothesis (reported, not in any total).

CLI: python -m solve.brightness_audit gimbal|gofast|flir1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R2_LIMIT = 0.5
SAT_LIMIT = 0.5
N_REG = 4


def _center(y: np.ndarray, seg: np.ndarray) -> np.ndarray:
    out = np.array(y, float)
    for s in np.unique(seg):
        m = seg == s
        out[m] = y[m] - np.nanmean(y[m])
    return out


def _steps(y: np.ndarray, half: int = 5, k: float = 6.0) -> list[int]:
    """Indices where the median of the next `half` samples differs from the previous `half` by more
    than k robust sigmas of the frame-to-frame differences (local maxima only)."""
    y = np.asarray(y, float)
    d = np.diff(y)
    sig = 1.4826 * np.nanmedian(np.abs(d - np.nanmedian(d))) / np.sqrt(2.0)
    if not np.isfinite(sig) or sig <= 0:
        return []
    jump = np.zeros(len(y))
    for i in range(half, len(y) - half):
        jump[i] = np.nanmedian(y[i:i + half]) - np.nanmedian(y[i - half:i])
    big = np.abs(jump) > k * sig * np.sqrt(2.0 / half)
    out = []
    for i in np.flatnonzero(big):
        lo, hi = max(0, i - half), min(len(y), i + half + 1)
        if abs(jump[i]) == np.max(np.abs(jump[lo:hi])) and (not out or i - out[-1] > half):
            out.append(int(i))
    return out


def _dir(case_name: str) -> Path:
    from .case_data import derived_dir

    return derived_dir(case_name)   # data/derived/<case>, or the case YAML's derived_dir (FLIR1: flir1_navy)


def frame_levels_path(case_name: str) -> Path:
    return _dir(case_name) / "frame_levels.csv"


def saturated_flags(case_name: str, frames: np.ndarray) -> np.ndarray:
    """B1 per-frame saturation flag (extract.frame_levels: at least 3 blob pixels within 2 codes of the
    clip code on the object's side) on the given frames. Shared by the brightness audit (B1) and the
    D-017 saturated-blob size rule in solve/case_data.py, so both use one definition."""
    fl = pd.read_csv(frame_levels_path(case_name)).set_index("frame")
    return fl.loc[np.asarray(frames, int), "blob_saturated"].astype(bool).to_numpy()


def audit(case_name: str) -> dict:
    from .case_data import load_case

    case = load_case(case_name)
    s = case.series["brightness_trend"]
    fl = pd.read_csv(frame_levels_path(case_name)).set_index("frame")
    summ = json.loads((_dir(case_name) / "frame_levels_summary.json").read_text(encoding="utf-8"))
    fr, seg = s.frames, s.segment
    y = s.obs

    # B1 saturation, on the frames the criterion scores.
    sat = saturated_flags(case_name, fr)
    sat_frac = float(sat.mean())
    per_seg = {}
    for sg in np.unique(seg):
        m = seg == sg
        per_seg[int(sg)] = {"frames": [int(fr[m][0]), int(fr[m][-1])], "n": int(m.sum()),
                            "polarity": str(fl.loc[fr[m][0], "polarity"]),
                            "saturated_fraction": float(sat[m].mean()),
                            "median_blob_px_at_clip": float(np.nanmedian(fl.loc[fr[m], "blob_n_at_clip"])),
                            "median_blob_px": float(np.nanmedian(fl.loc[fr[m], "blob_n"])),
                            "median_object_peak_contrast": float(np.nanmedian(fl.loc[fr[m], "obj_peak"])),
                            "median_ring_background": float(np.nanmedian(fl.loc[fr[m], "obj_bg"]))}
    b1_fail = sat_frac > SAT_LIMIT

    # B2 gain and level.
    names = ["pic_level", "pic_contrast", "tile_level", "tile_contrast"]
    X = np.column_stack([np.log(np.clip(fl.loc[fr, c].to_numpy(float), 0.5, None)) for c in names])
    yc = _center(y, seg)
    Xc = np.column_stack([_center(X[:, j], seg) for j in range(X.shape[1])])
    coef, *_ = np.linalg.lstsq(Xc, yc, rcond=None)
    resid = yc - Xc @ coef
    r2 = float(1.0 - np.sum(resid ** 2) / np.sum(yc ** 2))
    ne = float(s.n_eff)
    r2_adj = float(1.0 - (1.0 - r2) * (ne - 1.0) / max(ne - N_REG - 1.0, 1.0))
    single = {}
    for j, c in enumerate(names):
        cc = np.corrcoef(Xc[:, j], yc)[0, 1]
        single[c] = {"r": float(cc), "r2": float(cc ** 2)}
    per_seg_r2 = {}
    for sg in np.unique(seg):
        m = seg == sg
        if m.sum() > 10:
            cf, *_ = np.linalg.lstsq(Xc[m], yc[m], rcond=None)
            rr = yc[m] - Xc[m] @ cf
            per_seg_r2[int(sg)] = float(1.0 - np.sum(rr ** 2) / np.sum(yc[m] ** 2))
    b2_fail = r2_adj > R2_LIMIT

    # B3 zoom.
    sym = pd.read_csv(ROOT / case.cfg["files"]["symbology"], dtype=str)
    z = sym[sym["field"] == "zoom"].set_index(sym[sym["field"] == "zoom"]["frame"].astype(int))["value"]
    zoom_changes = []
    for sg in np.unique(seg):
        vals = z.reindex(fr[seg == sg]).dropna().unique().tolist()
        if len(vals) > 1:
            zoom_changes.append({"segment": int(sg), "values": vals})
    b3_fail = bool(zoom_changes)

    # Supporting evidence: co-occurring steps.
    steps_obj = [int(fr[i]) for i in _steps(y)]
    steps_lvl = {c: [int(fr[i]) for i in _steps(np.log(np.clip(fl.loc[fr, c].to_numpy(float), 0.5, None)))]
                 for c in names}
    co = {c: [f for f in steps_obj if any(abs(f - g) <= 2 for g in v)] for c, v in steps_lvl.items()}

    fails = [k for k, v in (("B1 saturation", b1_fail), ("B2 gain and level", b2_fail), ("B3 zoom", b3_fail)) if v]
    out = {
        "case": case_name,
        "rule": "docs/results/REVIEW-M3.md, Rule B (stated before the measurements)",
        "scored_frames": [int(fr[0]), int(fr[-1])], "n_frames": int(len(fr)), "n_eff": ne,
        "clip_codes": {"bright": summ["clip_code_bright"], "dark": summ["clip_code_dark"],
                       "tolerance": summ["clip_tolerance_codes"]},
        "B1": {"saturated_fraction": sat_frac, "limit": SAT_LIMIT, "fail": bool(b1_fail), "segments": per_seg},
        "B2": {"regressors": [f"ln {c}" for c in names], "r2": r2, "r2_adjusted_n_eff": r2_adj, "limit": R2_LIMIT,
               "fail": bool(b2_fail), "coefficients": dict(zip(names, map(float, coef))), "single_regressor": single,
               "r2_by_segment": per_seg_r2},
        "B3": {"zoom_changes_inside_segments": zoom_changes, "fail": b3_fail},
        "steps": {"object_brightness": steps_obj, "frame_level": steps_lvl, "co_occurring_within_2_frames": co},
        "fails": fails,
        "range_informative": not fails,
        "decision": ("brightness criterion carries weight 0 for every hypothesis (reported, not in any total)" if fails
                     else "brightness criterion kept with its measured noise"),
    }
    return out


def main(argv: list[str]) -> int:
    case = argv[1] if len(argv) > 1 else "gimbal"
    out = audit(case)
    p = _dir(case) / "brightness_audit.json"
    p.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("case", "B1", "B2", "B3", "fails", "decision")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
