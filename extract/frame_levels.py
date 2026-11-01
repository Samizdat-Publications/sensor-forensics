"""Frame-level gain and level proxies and blob saturation (REVIEW-M3, item 1: brightness audit).

For every frame of a case, from the extracted PNG frames:

- whole active picture (letterbox removed; persistent symbology, layout boxes, the reticle and a
  box around the tracked object masked): median gray level and robust contrast (1.4826 x MAD);
- a fixed background region (GIMBAL: the lower-left cloud tile of extract.image_cues; GOFAST:
  the same tile position, ocean): median level and robust contrast;
- the blob's extreme raw code on the object's side (white-hot object: its brightest pixel;
  black-hot: its darkest) and the number of blob pixels within 2 codes of the clip code;
- the clip codes themselves: the brightest and darkest codes reached anywhere in the masked
  active picture over the whole clip.

The blob is the low-threshold component of extract.image_cues (pixels within the object's search
box whose contrast sign * (I - obj_bg) exceeds obj_lo_thr, 8-connected to the peak), rebuilt
from image_track.csv so the measurement uses the same pixels as the brightness criterion.

CLI: python -m extract.frame_levels gimbal|gofast
Writes data/derived/<case>/frame_levels.csv and frame_levels_summary.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .image_cues import CASES, active_rect, load_gray, load_layout, robust_sigma, static_mask

ROOT = Path(__file__).resolve().parents[1]
CLIP_TOL = 2          # codes: "at the clip" means within this many gray levels of the clip code
OBJ_BOX = 30          # px half size of the object box masked from the frame statistics


# Fixed background tile for cases without a cloud tile of their own. FLIR1 (352 x 264 copy, active picture
# x 54 to 294, y 17 to 251): a lower-left sky tile clear of the elevation box (y <= 137 with its pad), the
# airspeed / Mach boxes (y >= 221) and the reticle; chosen from the layout before any level was measured.
LEVEL_TILES: dict[str, tuple[int, int, int, int]] = {"flir1_navy": (58, 140, 150, 215)}


def _tile(case: str) -> tuple[int, int, int, int]:
    if case in LEVEL_TILES:
        return LEVEL_TILES[case]
    t = CASES[case].cloud_tile
    return t if t is not None else CASES["gimbal"].cloud_tile


def measure(case: str) -> tuple[pd.DataFrame, dict]:
    cfg = CASES[case]
    n = cfg.n_frames
    track = pd.read_csv(ROOT / "data" / "derived" / case / "image_track.csv").sort_values("frame").reset_index(drop=True)
    g0 = load_gray(case, 0)
    smask = static_mask(case, n, load_layout(cfg.layout), cfg, g0.shape)
    ax0, ay0, ax1, ay1 = active_rect(case, n)
    tx0, ty0, tx1, ty1 = _tile(case)
    rows = []
    hi_code, lo_code = 0, 255
    blobs = []
    for f in range(n):
        g = load_gray(case, f)
        r = track.iloc[f]
        valid = ~smask.copy()
        cx, cy = r["obj_hi_cx"], r["obj_hi_cy"]
        if np.isfinite(cx):
            valid[max(int(cy) - OBJ_BOX, 0):int(cy) + OBJ_BOX, max(int(cx) - OBJ_BOX, 0):int(cx) + OBJ_BOX] = False
        pic = g[ay0:ay1, ax0:ax1][valid[ay0:ay1, ax0:ax1]].astype(float)
        til = g[ty0:ty1, tx0:tx1][valid[ty0:ty1, tx0:tx1]].astype(float)
        hi_code = max(hi_code, int(pic.max()))
        lo_code = min(lo_code, int(pic.min()))
        row = {"frame": f, "pic_level": float(np.median(pic)), "pic_contrast": float(robust_sigma(pic)),
               "tile_level": float(np.median(til)), "tile_contrast": float(robust_sigma(til)),
               "pic_mean": float(pic.mean()), "pic_std": float(pic.std())}
        # The blob (low-threshold component around the peak), rebuilt from the track's own numbers.
        blob_vals = None
        if int(r["obj_found"]) == 1 and np.isfinite(r["obj_lo_thr"]):
            s = int(r["obj_sign"])
            x, y = int(round(r["obj_lo_cx"])), int(round(r["obj_lo_cy"]))
            R = cfg.obj_search + 4
            y0, x0 = max(y - R, 0), max(x - R, 0)
            win = g[y0:y + R + 1, x0:x + R + 1].astype(float)
            c = s * (win - float(r["obj_bg"]))
            b = (cv2.GaussianBlur(c.astype(np.float32), (0, 0), 0.7) > float(r["obj_lo_thr"])).astype(np.uint8)
            _, lab = cv2.connectedComponents(b, connectivity=8)
            yy, xx = np.unravel_index(int(np.argmax(np.where(b > 0, c, -np.inf))), c.shape)
            comp = lab == lab[yy, xx]
            blob_vals = win[comp]
            row.update({"obj_sign": s, "blob_n": int(comp.sum()),
                        "blob_extreme_code": float(blob_vals.max() if s > 0 else blob_vals.min())})
        blobs.append(blob_vals)
        rows.append(row)
    df = pd.DataFrame(rows)
    # The clip codes include the object's own pixels (the object may be the brightest thing on screen).
    for bv in blobs:
        if bv is not None and bv.size:
            hi_code = max(hi_code, int(bv.max()))
            lo_code = min(lo_code, int(bv.min()))
    n_at_clip = []
    for row, bv in zip(rows, blobs):
        if bv is None:
            n_at_clip.append(np.nan)
            continue
        if row["obj_sign"] > 0:
            n_at_clip.append(int((bv >= hi_code - CLIP_TOL).sum()))
        else:
            n_at_clip.append(int((bv <= lo_code + CLIP_TOL).sum()))
    df["blob_n_at_clip"] = n_at_clip
    df["blob_saturated"] = df["blob_n_at_clip"] >= 3
    df["polarity"] = track["polarity"].astype(str).to_numpy()
    df["obj_lo_integ"] = track["obj_lo_integ"].to_numpy(float)
    df["obj_bg"] = track["obj_bg"].to_numpy(float)
    df["obj_peak"] = track["obj_peak"].to_numpy(float)
    summ = {"case": case, "active_rect": [ax0, ay0, ax1, ay1], "tile": [tx0, ty0, tx1, ty1],
            "clip_code_bright": hi_code, "clip_code_dark": lo_code, "clip_tolerance_codes": CLIP_TOL,
            "object_box_masked_px": OBJ_BOX,
            "saturated_frames": int(df["blob_saturated"].sum()), "frames": int(n)}
    return df, summ


def main(argv: list[str]) -> int:
    case = argv[1] if len(argv) > 1 else "gimbal"
    df, summ = measure(case)
    d = ROOT / "data" / "derived" / case
    df.to_csv(d / "frame_levels.csv", index=False, float_format="%.4f")
    (d / "frame_levels_summary.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
