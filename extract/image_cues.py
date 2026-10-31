"""Per-frame image cues (M1.4): horizon-bar bank, object blob, background motion.

All angles are in degrees, measured counter-clockwise from the image +x axis with image y
pointing UP (the usual math convention applied to the picture as displayed). In pixel
coordinates (y down) a direction (dx, dy) has angle atan2(-dy, dx).

1. Bank (artificial horizon bars).
   The bars are thin bright strokes. In the layout `horizon` box we take the white top-hat
   (bright structures narrower than the kernel minus the local background), keep pixels above
   a noise-relative threshold, drop a disk around the reticle (circle plus its ticks), and fit
   one straight line by RANSAC (deterministic seed) restricted to |angle| <= 75 deg and to lines
   passing within 15 px of the reticle center. The fit is refined by top-hat-weighted total
   least squares on the inliers (|d| <= 1.5 px), trimming the outer 2 % of the bar length so
   the short end ticks do not pull it. Left and right bars are also fitted separately.
   Sign mapping: when the jet banks left (left wing down) the world, and the drawn horizon,
   rotate clockwise on screen, so the right end of the bars goes down and the line angle is
   negative. Hence bank_deg (positive = right wing down) = line angle. This is checked against
   Sitrec: GimbalData.csv `3 bank_angle` and GOFAST `Bank Angle` are positive for a left bank,
   so ours should equal minus their CSV value (see sitrec_bank_check).
   Columns: bank_deg, bank_sigma_deg (statistical, from the TLS residual), bank_resid_px
   (weighted RMS perpendicular residual), bank_npix (inlier pixels), bank_lr_diff_deg (left bar
   angle minus right bar angle), bank_offset_px (signed distance of the reticle center from the
   line, positive = center above the line).

2. Object blob.
   A window around the predicted position (previous centroid; for the pod-tracked GIMBAL and
   GOFAST targets kept within obj_anchor px of the screen-center start; back to the start after
   LOST_RESET frames without a detection) is cut out. Background b and noise
   s are the median and 1.4826 * MAD of a square ring around the search region, symbology
   excluded. Symbology mask: thin bright vertical and horizontal strokes (top-hat with a 7 px
   kernel across the stroke, then an opening along the stroke of a case-specific minimum length:
   the track brackets and boxes), plus a band around the fitted horizon line and the reticle
   disk. The object's contrast sign (brighter or darker than background) is decided from the data
   (sign of the largest |I - b| in the search region), then made constant by majority vote inside
   each polarity segment (WHT/BLK from symbology.csv) or a 31-frame running vote. The contrast
   image is c = sign * (I - b), i.e. |object - background| on the object's side, so a polarity
   flip of the video gives identical measurements. Two thresholds are applied: frac * peak with
   frac = 0.25 ("lo") and 0.5 ("hi", half maximum), each at least 3 s. The connected component
   (8-connectivity, symbology excluded) containing the peak is measured:
     cx, cy: contrast-weighted centroid (px, frame coordinates, pixel centers at integers);
     area_px: number of pixels;
     angle_deg: orientation of the major axis from contrast-weighted second central moments,
       convention above, range (-90, 90];
     major_px, minor_px: full axis lengths of the uniform ellipse with the same second moments
       (4 * sqrt(eigenvalue));
     integ: sum of c over the component (integrated |object - background|, gray levels * px);
     symadj_px: symbology-mask pixels touching the component (contact with brackets).
   Uncertainty: obj_snr = peak / s; obj_cxy_sigma_px = s * sqrt(sum of squared distances) /
   sum(c), the noise-propagated centroid error; the lo vs hi differences show threshold
   sensitivity, and obj_elong = 1 - minor/major tells when the angle is ill defined.

3. Background motion.
   Region: the active picture ("bg_*"; letterbox removed) and, for GIMBAL, the lower-left cloud
   tile ("cloud_*"). Masked out: the layout text boxes, the horizon box, the reticle, persistent
   strokes (median top-hat over the clip) and a box around the tracked object in both frames.
   Masked pixels are filled by normalized convolution, the image is high-passed (minus a
   sigma 12 px Gaussian, removing vignetting and the large sky gradient) and smoothed (sigma 1.5).
   Finding (documented in the M1.4 report): consecutive frames of these copies share content at
   zero shift (static fixed pattern plus what looks like temporal smoothing in the recording
   chain), so any whitened estimator, cv2.phaseCorrelate included, returns about 0 px even where
   the clouds visibly move several px/frame, and plain consecutive-frame correlation is biased
   toward 0. Displacement is therefore measured over a baseline of k frames (pair t - k//2 and
   t - k//2 + k; start k per case in CASES, chosen where D(k)/k stops growing with k; if the
   displacement over k is under 8 px, k is raised up to kmax so about 8 px are covered; the
   k used is in bg_k / cloud_k) and divided by k, so values are rates averaged over k frames:
     coarse: normalized cross-correlation (TM_CCOEFF_NORMED) of the region core within the other
       frame, parabolic sub-pixel peak; bg_ncc is the peak score, bg_ncc0 the score at zero
       shift (bg_ncc - bg_ncc0 near 0 means the motion is not distinguishable from none);
     fine: cv2.findTransformECC (Euclidean: rotation plus translation, masked) initialized from
       the coarse shift; bg_ecc is its correlation coefficient. If ECC fails or moves more than
       2 px from the coarse answer, the coarse shift is kept and bg_rot is empty.
   bg_dx, bg_dy: content motion in px/frame (+x right, +y down) at the region center.
   bg_rot_dpf: rotation in deg/frame, positive = counter-clockwise on screen.
   bg_pc_dx, bg_pc_dy, bg_pc_resp: cv2.phaseCorrelate (Hanning window) on the same pair,
   kept only as the documented diagnostic of the zero-shift lock; do not use as motion.

CLI:  python -m extract.image_cues <case> [--frames N]
      case: gimbal | gofast | flir1_navy
Outputs: data/derived/<case>/image_track.csv, data/derived/<case>/image_track_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------- case config

@dataclass
class CaseConfig:
    case: str
    layout: str
    n_frames: int
    reticle: tuple[float, float]       # reticle circle center (px), Hough on the median top-hat
    reticle_mask_r: float              # disk dropped from the bank fit (circle plus ticks)
    tophat_k: int                      # top-hat kernel for the bars (px)
    obj_init: tuple[float, float]      # first-frame object position guess
    obj_search: int                    # half size of the object search region (px)
    obj_ring: tuple[int, int]          # background ring (inner, outer) half sizes (px)
    bracket_len: int                   # minimum stroke length treated as symbology (px)
    obj_motion_mask: int               # half size of the object box masked in motion estimates
    k_whole: int                       # motion baseline (frames) for the whole-frame estimate
    shift_whole: int                   # max displacement searched over that baseline (px)
    cloud_tile: tuple[int, int, int, int] | None = None   # x0, y0, x1, y1
    k_cloud: int = 4
    shift_cloud: int = 32
    kmax: int = 20                     # longest baseline used when the motion is slow
    mask_horizontal: bool = True       # GOFAST: the target dash joins the bracket bars
    obj_anchor: float | None = None    # pod-tracked target: search center kept within this of obj_init


CASES: dict[str, CaseConfig] = {
    # GIMBAL clouds move 0.3 to 6.5 px/frame; GOFAST ocean 2 to 30 px/frame.
    "gimbal": CaseConfig("gimbal", "gimbal", 1031, (317.5, 182.5), 28.0, 7,
                         (318.0, 240.0), 18, (24, 34), 15, 48, 6, 48, (112, 245, 292, 398), 4, 32,
                         obj_anchor=10.0),
    "gofast": CaseConfig("gofast", "gofast", 1031, (317.5, 182.5), 28.0, 7,
                         (317.0, 241.0), 6, (10, 16), 7, 24, 2, 80, kmax=8,
                         mask_horizontal=False, obj_anchor=4.0),
    "flir1_navy": CaseConfig("flir1_navy", "flir1", 2288, (174.5, 101.5), 16.0, 5,
                             (175.0, 128.0), 16, (20, 27), 7, 34, 4, 32),
}


def frame_path(case: str, f: int) -> Path:
    return ROOT / "data" / "frames" / case / f"f{f:06d}.png"


def load_gray(case: str, f: int) -> np.ndarray:
    img = cv2.imread(str(frame_path(case, f)), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(frame_path(case, f))
    return img


def load_layout(name: str) -> dict:
    with open(ROOT / "extract" / "layouts" / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_polarity(case: str, n: int) -> list[str]:
    """Per-frame polarity (WHT/BLK) from symbology.csv, '' where unknown."""
    out = [""] * n
    p = ROOT / "data" / "derived" / case / "symbology.csv"
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["field"] == "polarity":
                f = int(row["frame"])
                if 0 <= f < n:
                    out[f] = row["value"]
    return out


def angle_ccw_deg(dx: float, dy: float) -> float:
    """Line direction angle (deg) CCW from +x with y up, folded into (-90, 90]."""
    a = math.degrees(math.atan2(-dy, dx))
    return fold180(a)


def fold180(a):
    """Fold an axial angle (period 180) into (-90, 90]."""
    a = np.asarray(a, dtype=float)
    r = (a + 90.0) % 180.0 - 90.0
    r = np.where(r == -90.0, 90.0, r)
    return float(r) if r.ndim == 0 else r


def white_tophat(img: np.ndarray, kx: int, ky: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))
    return cv2.morphologyEx(img.astype(np.float32), cv2.MORPH_TOPHAT, k)


def robust_sigma(v: np.ndarray) -> float:
    v = np.asarray(v, dtype=float).ravel()
    if v.size == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


# ----------------------------------------------------------------------------- 1. line fit

def _tls(x, y, w):
    sw = w.sum()
    mx, my = (w * x).sum() / sw, (w * y).sum() / sw
    dx, dy = x - mx, y - my
    cxx, cyy, cxy = (w * dx * dx).sum() / sw, (w * dy * dy).sum() / sw, (w * dx * dy).sum() / sw
    ev, evec = np.linalg.eigh(np.array([[cxx, cxy], [cxy, cyy]]))
    d = evec[:, 1]           # direction (largest eigenvalue)
    return mx, my, d[0], d[1]


def fit_line_robust(x, y, w=None, center=None, max_center_dist=None, max_abs_angle=75.0,
                    tol=1.5, iters=400, trim=0.02, seed=0) -> dict | None:
    """RANSAC + weighted total least squares line fit. Returns None when it cannot fit.

    Angle in the CCW-with-y-up convention, (-90, 90].
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    w = np.ones_like(x) if w is None else np.asarray(w, float)
    n = x.size
    if n < 8:
        return None
    rng = np.random.default_rng(seed)
    best_score, best = -1.0, None
    for _ in range(iters):
        i, j = rng.integers(0, n, 2)
        if i == j:
            continue
        dx, dy = x[j] - x[i], y[j] - y[i]
        L = math.hypot(dx, dy)
        if L < 10:
            continue
        ux, uy = dx / L, dy / L
        if abs(angle_ccw_deg(ux, uy)) > max_abs_angle:
            continue
        if center is not None and max_center_dist is not None:
            dc = abs((center[0] - x[i]) * uy - (center[1] - y[i]) * ux)
            if dc > max_center_dist:
                continue
        d = np.abs((x - x[i]) * uy - (y - y[i]) * ux)
        score = w[d <= tol].sum()
        if score > best_score:
            best_score, best = score, (x[i], y[i], ux, uy)
    if best is None:
        return None
    px, py, ux, uy = best
    inl = np.ones(n, bool)
    for _ in range(4):
        d = np.abs((x - px) * uy - (y - py) * ux)
        inl = d <= tol
        if inl.sum() < 8:
            return None
        s = (x - px) * ux + (y - py) * uy
        lo, hi = np.quantile(s[inl], [trim, 1 - trim])
        inl &= (s >= lo) & (s <= hi)
        px, py, ux, uy = _tls(x[inl], y[inl], w[inl])
    d = (x[inl] - px) * uy - (y[inl] - py) * ux
    s = (x[inl] - px) * ux + (y[inl] - py) * uy
    wi = w[inl]
    resid = float(math.sqrt((wi * d * d).sum() / wi.sum()))
    sxx = float(((s - s.mean()) ** 2).sum())
    sigma = math.degrees(resid / math.sqrt(sxx)) if sxx > 0 else float("nan")
    return {"angle_deg": angle_ccw_deg(ux, uy), "px": px, "py": py, "ux": ux, "uy": uy,
            "resid_px": resid, "n": int(inl.sum()), "sigma_deg": sigma, "inliers": inl}


def bar_pixels(gray: np.ndarray, box, center, mask_r: float, k: int):
    """Bright thin-stroke pixels (x, y, weight) in the horizon box, reticle disk removed."""
    x0, y0, x1, y1 = box
    roi = gray[y0:y1, x0:x1].astype(np.float32)
    th = white_tophat(roi, k, k)
    med = float(np.median(th))
    sig = robust_sigma(th)
    hi = float(np.quantile(th, 0.998))
    thr = max(18.0, med + 5.0 * sig, 0.3 * hi)
    ys, xs = np.nonzero(th > thr)
    X, Y = xs + x0, ys + y0
    keep = np.hypot(X - center[0], Y - center[1]) > mask_r
    return X[keep].astype(float), Y[keep].astype(float), th[ys[keep], xs[keep]].astype(float)


def measure_bank(gray: np.ndarray, box, center, mask_r: float = 28.0, k: int = 7) -> dict:
    nanres = {"bank_deg": np.nan, "bank_sigma_deg": np.nan, "bank_resid_px": np.nan,
              "bank_npix": 0, "bank_lr_diff_deg": np.nan, "bank_offset_px": np.nan}
    X, Y, W = bar_pixels(gray, box, center, mask_r, k)
    fit = fit_line_robust(X, Y, W, center=center, max_center_dist=15.0)
    if fit is None:
        return nanres
    out = {"bank_deg": fit["angle_deg"], "bank_sigma_deg": fit["sigma_deg"],
           "bank_resid_px": fit["resid_px"], "bank_npix": fit["n"]}
    inl = fit["inliers"]
    s = (X - fit["px"]) * fit["ux"] + (Y - fit["py"]) * fit["uy"]
    sc = (center[0] - fit["px"]) * fit["ux"] + (center[1] - fit["py"]) * fit["uy"]
    sides = []
    for side in (s < sc, s > sc):
        m = inl & side
        if m.sum() >= 8:
            px, py, ux, uy = _tls(X[m], Y[m], W[m])
            sides.append(angle_ccw_deg(ux, uy))
        else:
            sides.append(np.nan)
    out["bank_lr_diff_deg"] = fold180(sides[0] - sides[1]) if np.isfinite(sides).all() else np.nan
    # signed distance of the reticle center from the line, + = center above the line (y up)
    ux, uy = fit["ux"], fit["uy"]
    if ux < 0:
        ux, uy = -ux, -uy
    out["bank_offset_px"] = float((center[0] - fit["px"]) * uy - (center[1] - fit["py"]) * ux)
    out["_fit"] = fit
    return out


# ----------------------------------------------------------------------------- 2. object blob

def thin_stroke_mask(gray: np.ndarray, min_len: int, thr: float | None = None,
                     horizontal: bool = True) -> np.ndarray:
    """Thin bright vertical (and optionally horizontal) strokes: brackets, boxes.

    Top-hat across the stroke (7 px), a closing along it (7 px, bridges joints where a bar
    meets something wider) and an opening along it (min_len px, drops short blobs).
    """
    g = gray.astype(np.float32)
    thv = white_tophat(g, 7, 1)     # narrow in x -> vertical strokes
    if thr is None:
        thr = max(18.0, 4.0 * robust_sigma(thv))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
    mv = cv2.morphologyEx((thv > thr).astype(np.uint8), cv2.MORPH_CLOSE, vk)
    mv = cv2.morphologyEx(mv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_len)))
    m = mv
    if horizontal:
        thh = white_tophat(g, 1, 7)     # narrow in y -> horizontal strokes
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
        mh = cv2.morphologyEx((thh > thr).astype(np.uint8), cv2.MORPH_CLOSE, hk)
        mh = cv2.morphologyEx(mh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1)))
        m = m | mh
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    return m.astype(bool)


def blob_moments(c: np.ndarray, comp: np.ndarray, x0: int = 0, y0: int = 0) -> dict:
    """Moments of a component. c: contrast image (object side positive); comp: bool mask."""
    ys, xs = np.nonzero(comp)
    if xs.size == 0:
        return {"cx": np.nan, "cy": np.nan, "area_px": 0, "angle_deg": np.nan,
                "major_px": np.nan, "minor_px": np.nan, "integ": 0.0}
    w = np.clip(c[ys, xs].astype(float), 0, None)
    sw = w.sum()
    if sw <= 0:
        w = np.ones_like(w)
        sw = w.sum()
    cx = (w * xs).sum() / sw
    cy = (w * ys).sum() / sw
    mx, my = xs.mean(), ys.mean()
    dx, dy = xs - mx, ys - my
    # pixel = unit square: add 1/12 to the variances
    mu20 = (dx * dx).mean() + 1 / 12
    mu02 = (dy * dy).mean() + 1 / 12
    mu11 = (dx * dy).mean()
    th_img = 0.5 * math.atan2(2 * mu11, mu20 - mu02)   # y-down convention
    tr, det = mu20 + mu02, mu20 * mu02 - mu11 * mu11
    disc = math.sqrt(max(tr * tr / 4 - det, 0.0))
    l1, l2 = tr / 2 + disc, max(tr / 2 - disc, 0.0)
    # orientation from contrast-weighted moments (uses the sub-pixel edge information)
    wx, wy = xs - cx, ys - cy
    m20, m02, m11 = (w * wx * wx).sum() / sw, (w * wy * wy).sum() / sw, (w * wx * wy).sum() / sw
    th_img = 0.5 * math.atan2(2 * m11, m20 - m02)   # y-down convention
    return {"cx": float(cx + x0), "cy": float(cy + y0), "area_px": int(xs.size),
            "angle_deg": fold180(-math.degrees(th_img)),
            "major_px": 4 * math.sqrt(l1), "minor_px": 4 * math.sqrt(l2),
            "integ": float(np.clip(c[ys, xs], 0, None).sum())}


OBJ_FRACS = (("lo", 0.25), ("hi", 0.5))
OBJ_KEYS = ("cx", "cy", "area_px", "angle_deg", "major_px", "minor_px", "integ", "symadj_px")


def measure_object(gray: np.ndarray, center, search: int, ring: tuple[int, int],
                   sym_mask: np.ndarray | None = None, sign: int | None = None,
                   fracs=OBJ_FRACS, k_noise: float = 3.0) -> dict:
    """Measure the object blob near `center` (x, y). See module docstring."""
    H, W = gray.shape
    cx0, cy0 = int(round(center[0])), int(round(center[1]))
    R = ring[1]
    x0, x1 = max(cx0 - R, 0), min(cx0 + R + 1, W)
    y0, y1 = max(cy0 - R, 0), min(cy0 + R + 1, H)
    win = gray[y0:y1, x0:x1].astype(np.float32)
    sm = np.zeros_like(win, bool) if sym_mask is None else sym_mask[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    cheb = np.maximum(np.abs(xx - cx0), np.abs(yy - cy0))
    ring_m = (cheb > ring[0]) & (cheb <= ring[1]) & ~sm
    srch = (cheb <= search) & ~sm
    out = {"obj_found": 0, "obj_sign": 0, "obj_bg": np.nan, "obj_noise": np.nan,
           "obj_peak": np.nan, "obj_snr": np.nan, "obj_cxy_sigma_px": np.nan}
    for name, _ in fracs:
        for k in OBJ_KEYS:
            out[f"obj_{name}_{k}"] = np.nan
        out[f"obj_{name}_thr"] = np.nan
    if ring_m.sum() < 10 or srch.sum() < 4:
        return out
    bg = float(np.median(win[ring_m]))
    noise = max(robust_sigma(win[ring_m]), 0.5)
    dev = win - bg
    devs = cv2.GaussianBlur(dev, (0, 0), 0.7)
    if sign is None:
        idx = np.argmax(np.where(srch, np.abs(devs), -1))
        sign = 1 if devs.flat[idx] >= 0 else -1
    c = sign * dev
    cs = sign * devs
    cs_srch = np.where(srch, cs, -np.inf)
    pk = int(np.argmax(cs_srch))
    peak = float(cs_srch.flat[pk])
    py, px = np.unravel_index(pk, cs.shape)
    out.update({"obj_sign": int(sign), "obj_bg": bg, "obj_noise": noise, "obj_peak": peak,
                "obj_snr": peak / noise})
    if peak <= k_noise * noise:
        return out
    out["obj_found"] = 1
    sym_d = cv2.dilate(sm.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    for name, frac in fracs:
        thr = max(frac * peak, k_noise * noise)
        b = ((cs > thr) & srch).astype(np.uint8)
        _, lab = cv2.connectedComponents(b, connectivity=8)
        comp = lab == lab[py, px]
        m = blob_moments(c, comp, x0, y0)
        m["symadj_px"] = int((cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
                              & sym_d & ~comp).sum())
        for k in OBJ_KEYS:
            out[f"obj_{name}_{k}"] = m[k]
        out[f"obj_{name}_thr"] = thr
        if name == fracs[-1][0]:
            ys, xs = np.nonzero(comp)
            wsum = np.clip(c[ys, xs], 0, None).sum()
            if wsum > 0:
                r2 = ((xs + x0 - m["cx"]) ** 2 + (ys + y0 - m["cy"]) ** 2).sum()
                out["obj_cxy_sigma_px"] = float(noise * math.sqrt(r2) / wsum)
    return out


# ----------------------------------------------------------------------------- 3. motion

def feather_weight(valid: np.ndarray, erode_px: int = 4, sigma: float = 3.0) -> np.ndarray:
    v = cv2.erode(valid.astype(np.uint8), np.ones((2 * erode_px + 1, 2 * erode_px + 1), np.uint8))
    w = cv2.GaussianBlur(v.astype(np.float32), (0, 0), sigma)
    return (w * valid).astype(np.float32)


def phase_shift(a: np.ndarray, b: np.ndarray, weight: np.ndarray | None = None) -> tuple[float, float, float]:
    """cv2.phaseCorrelate with a Hanning window on weighted, mean-removed images.

    Returns the content shift from a to b (dx, dy px; +x right, +y down) and the response.
    """
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    if weight is None:
        weight = np.ones(a.shape, np.float32)
    sw = float(weight.sum())

    def prep(g):
        m = float((g * weight).sum() / sw) if sw > 0 else float(g.mean())
        return ((g - m) * weight).astype(np.float32)

    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(prep(a), prep(b), win)
    return float(dx), float(dy), float(resp)


def _norm_blur(g: np.ndarray, v: np.ndarray, sigma: float, fallback: float) -> np.ndarray:
    num = cv2.GaussianBlur(g * v, (0, 0), sigma)
    den = cv2.GaussianBlur(v, (0, 0), sigma)
    return np.where(den > 0.05, num / np.maximum(den, 1e-6), fallback).astype(np.float32)


def fill_masked(g: np.ndarray, valid: np.ndarray, sigma: float = 4.0) -> np.ndarray:
    """Replace invalid pixels by a normalized-convolution average of valid neighbors
    (the mean of all valid pixels where no valid neighbor is near)."""
    g = g.astype(np.float32)
    v = valid.astype(np.float32)
    mean = float(g[valid].mean()) if valid.any() else 0.0
    return np.where(valid, g, _norm_blur(g, v, sigma, mean)).astype(np.float32)


def prep_motion(g: np.ndarray, valid: np.ndarray, hp_sigma: float = 12.0, blur: float = 1.5) -> np.ndarray:
    """High-pass (minus a mask-aware Gaussian low-pass), masked pixels filled, then smoothed.

    The high-pass comes first so filled areas sit at the zero level and add no static edges.
    """
    g = g.astype(np.float32)
    v = valid.astype(np.float32)
    if hp_sigma > 0:
        mean = float(g[valid].mean()) if valid.any() else 0.0
        g = np.where(valid, g - _norm_blur(g, v, hp_sigma, mean), 0.0).astype(np.float32)
    f = fill_masked(g, valid)
    if blur > 0:
        f = cv2.GaussianBlur(f, (0, 0), blur)
    return f.astype(np.float32)


def _parabolic(m1: float, c0: float, p1: float) -> float:
    d = m1 - 2 * c0 + p1
    return 0.0 if d >= 0 else float(np.clip(0.5 * (m1 - p1) / d, -0.5, 0.5))


def register_pair(A: np.ndarray, B: np.ndarray, valid: np.ndarray, max_shift: int = 16,
                  ecc: bool = True) -> dict:
    """Displacement and rotation of content from A to B (prepared images, same shape).

    dx, dy at the image center (px); rot_deg CCW on screen; ncc, ncc0, ecc as confidences.
    """
    H, W = A.shape
    m = int(min(max_shift, H // 3, W // 3))
    R = cv2.matchTemplate(B, A[m:H - m, m:W - m], cv2.TM_CCOEFF_NORMED)
    iy, ix = np.unravel_index(int(np.argmax(R)), R.shape)
    sx = _parabolic(R[iy, ix - 1], R[iy, ix], R[iy, ix + 1]) if 0 < ix < R.shape[1] - 1 else 0.0
    sy = _parabolic(R[iy - 1, ix], R[iy, ix], R[iy + 1, ix]) if 0 < iy < R.shape[0] - 1 else 0.0
    cdx, cdy = ix - m + sx, iy - m + sy
    out = {"dx": float(cdx), "dy": float(cdy), "rot_deg": np.nan, "ncc": float(R[iy, ix]),
           "ncc0": float(R[m, m]), "ecc": np.nan,
           "edge": int(ix in (0, R.shape[1] - 1) or iy in (0, R.shape[0] - 1))}
    if not ecc:
        return out
    warp = np.array([[1, 0, cdx], [0, 1, cdy]], np.float32)
    try:
        cc, warp = cv2.findTransformECC(A, B, warp, cv2.MOTION_EUCLIDEAN,
                                        (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-5),
                                        valid.astype(np.uint8) * 255, 5)
    except cv2.error:
        return out
    c = np.array([W / 2.0, H / 2.0])
    d = warp[:, :2] @ c + warp[:, 2] - c
    if math.hypot(d[0] - cdx, d[1] - cdy) > 2.0:
        out["ecc"] = float(cc)
        return out
    out.update({"dx": float(d[0]), "dy": float(d[1]), "ecc": float(cc),
                "rot_deg": -math.degrees(math.atan2(float(warp[1, 0]), float(warp[0, 0])))})
    return out


def active_rect(case: str, n: int) -> tuple[int, int, int, int]:
    """Picture area (x0, y0, x1, y1) excluding the black letterbox, from 20 sampled frames."""
    m = np.mean([load_gray(case, f).astype(np.float32) for f in range(0, n, max(n // 20, 1))], 0)
    cols = np.nonzero(m.mean(0) > 8)[0]
    rows = np.nonzero(m.mean(1) > 8)[0]
    return int(cols.min()) + 2, int(rows.min()) + 2, int(cols.max()) - 1, int(rows.max()) - 1


def static_mask(case: str, n: int, layout: dict, cfg: CaseConfig, shape) -> np.ndarray:
    """Symbology that must not drive background motion: layout boxes, reticle, persistent strokes."""
    H, W = shape
    m = np.zeros((H, W), np.uint8)
    pad = 4
    for fld in layout["fields"].values():
        x0, y0, x1, y1 = fld["box"]
        m[max(y0 - pad, 0):y1 + pad, max(x0 - pad, 0):x1 + pad] = 1
    cv2.circle(m, (int(cfg.reticle[0]), int(cfg.reticle[1])), int(cfg.reticle_mask_r + 4), 1, -1)
    ths = [white_tophat(load_gray(case, f), 7, 7) for f in range(0, n, max(n // 40, 1))]
    med = np.median(np.array(ths), 0)
    m |= (med > 15).astype(np.uint8)
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    return m.astype(bool)


class MotionContext:
    """Per-case masks and regions for background motion."""

    def __init__(self, case: str, cfg: CaseConfig | None = None):
        self.case = case
        self.cfg = cfg or CASES[case]
        layout = load_layout(self.cfg.layout)
        g0 = load_gray(case, 0)
        self.shape = g0.shape
        self.smask = static_mask(case, self.cfg.n_frames, layout, self.cfg, g0.shape)
        ax0, ay0, ax1, ay1 = active_rect(case, self.cfg.n_frames)
        self.regions = {"bg": ((slice(ay0, ay1), slice(ax0, ax1)), self.cfg.k_whole, self.cfg.shift_whole)}
        if self.cfg.cloud_tile is not None:
            x0, y0, x1, y1 = self.cfg.cloud_tile
            self.regions["cloud"] = ((slice(y0, y1), slice(x0, x1)), self.cfg.k_cloud, self.cfg.shift_cloud)

    def valid(self, obj_centers) -> np.ndarray:
        v = ~self.smask
        h = self.cfg.obj_motion_mask
        for cx, cy in obj_centers:
            if cx is None or not np.isfinite(cx):
                cx, cy = self.cfg.obj_init
            v[max(int(cy) - h, 0):int(cy) + h, max(int(cx) - h, 0):int(cx) + h] = False
        return v

    def measure(self, region: str, f0: int, f1: int, obj_centers=(), pc: bool = True) -> dict:
        sl, k, shift = self.regions[region]
        v = self.valid(obj_centers)[sl]
        A = prep_motion(load_gray(self.case, f0)[sl], v)
        B = prep_motion(load_gray(self.case, f1)[sl], v)
        r = register_pair(A, B, v, max_shift=shift)
        if pc:
            r["pc_dx"], r["pc_dy"], r["pc_resp"] = phase_shift(A, B, feather_weight(v))
        return r


# ----------------------------------------------------------------------------- per case run

def _segments(labels: list[str]) -> list[tuple[int, int]]:
    segs, s = [], 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[s]:
            segs.append((s, i))
            s = i
    return segs


def vote_signs(signs: np.ndarray, polarity: list[str], window: int = 31) -> np.ndarray:
    """Majority sign per polarity segment, else a running majority."""
    out = signs.copy()
    if any(polarity):
        for s, e in _segments(polarity):
            v = signs[s:e]
            out[s:e] = 1 if v.sum() >= 0 else -1
    else:
        h = window // 2
        for i in range(len(signs)):
            v = signs[max(0, i - h):i + h + 1]
            out[i] = 1 if v.sum() >= 0 else -1
    return out


def object_sym_mask(g: np.ndarray, cfg: CaseConfig, fit: dict | None) -> np.ndarray:
    sym = thin_stroke_mask(g, cfg.bracket_len, horizontal=cfg.mask_horizontal)
    extra = np.zeros(g.shape, np.uint8)
    if fit is not None:
        L = 400
        p0 = (int(fit["px"] - L * fit["ux"]), int(fit["py"] - L * fit["uy"]))
        p1 = (int(fit["px"] + L * fit["ux"]), int(fit["py"] + L * fit["uy"]))
        cv2.line(extra, p0, p1, 1, 7)
    cv2.circle(extra, (int(cfg.reticle[0]), int(cfg.reticle[1])), int(cfg.reticle_mask_r), 1, -1)
    return sym | extra.astype(bool)


LOST_RESET = 15   # frames without a detection before the search returns to obj_init


def track_objects(case: str, cfg: CaseConfig, frames: list[int], fits: dict, signs=None) -> dict:
    rows = {}
    center = cfg.obj_init
    lost = 0
    for i, f in enumerate(frames):
        g = load_gray(case, f)
        sym = object_sym_mask(g, cfg, fits.get(f))
        sg = None if signs is None else int(signs[i])
        r = measure_object(g, center, cfg.obj_search, cfg.obj_ring, sym, sg)
        if r["obj_found"] and np.isfinite(r["obj_hi_cx"]):
            nc = (r["obj_hi_cx"], r["obj_hi_cy"])
            # follow the object; the step limit keeps the window from jumping to clutter
            if math.hypot(nc[0] - center[0], nc[1] - center[1]) <= cfg.obj_search:
                center = nc
            lost = 0
        else:
            lost += 1
            if lost >= LOST_RESET:
                center = cfg.obj_init
        if cfg.obj_anchor is not None:
            # the pod keeps a tracked target at the screen center: clamp the search center
            dx, dy = center[0] - cfg.obj_init[0], center[1] - cfg.obj_init[1]
            d = math.hypot(dx, dy)
            if d > cfg.obj_anchor:
                center = (cfg.obj_init[0] + dx * cfg.obj_anchor / d, cfg.obj_init[1] + dy * cfg.obj_anchor / d)
        rows[f] = r
    return rows


def measure_rate(mc: "MotionContext", region: str, f: int, n: int, centers: dict, target_px: float = 8.0):
    """Background displacement rate at frame f over a centered baseline of k frames.

    Starts at the region's k; if the displacement over k is below target_px (where the
    zero-shift bias matters), k is raised (up to kmax) so that about target_px is covered.
    Returns (result, k, f0, f1) with result displacements over the whole baseline.
    """
    _, k, _ = mc.regions[region]
    kmax = mc.cfg.kmax
    r = None
    f0 = f1 = 0
    for _ in range(3):
        if n <= k:
            return None, k, 0, 0
        f0 = min(max(f - k // 2, 0), n - 1 - k)
        f1 = f0 + k
        r = mc.measure(region, f0, f1, (centers[f0], centers[f1]), pc=(region == "bg"))
        disp = math.hypot(r["dx"], r["dy"])
        if disp >= target_px or k >= kmax:
            break
        speed = max(disp / k, target_px / kmax)
        k = int(min(kmax, max(k + 2, math.ceil(target_px / speed))))
    return r, k, f0, f1


def run_case(case: str, n_frames: int | None = None, progress: bool = True) -> list[dict]:
    cfg = CASES[case]
    layout = load_layout(cfg.layout)
    n = cfg.n_frames if n_frames is None else min(n_frames, cfg.n_frames)
    frames = list(range(n))
    polarity = load_polarity(case, n)
    hbox = layout["fields"]["horizon"]["box"]

    banks, fits = {}, {}
    for f in frames:
        b = measure_bank(load_gray(case, f), hbox, cfg.reticle, cfg.reticle_mask_r, cfg.tophat_k)
        fits[f] = b.pop("_fit", None)
        banks[f] = b
    if progress:
        print(f"  {case}: bank done", flush=True)

    pass1 = track_objects(case, cfg, frames, fits)
    s1 = np.array([pass1[f]["obj_sign"] for f in frames])
    signs = vote_signs(s1, polarity)
    objs = track_objects(case, cfg, frames, fits, signs)
    if progress:
        print(f"  {case}: object done", flush=True)

    mc = MotionContext(case, cfg)
    centers = {f: (objs[f]["obj_hi_cx"], objs[f]["obj_hi_cy"]) for f in frames}
    rows = []
    for i, f in enumerate(frames):
        row = {"frame": f, "polarity": polarity[f], "obj_sign_pass1": int(s1[i])}
        row.update(banks[f])
        row.update(objs[f])
        for region in mc.regions:
            r, k, f0, f1 = measure_rate(mc, region, f, n, centers)
            if r is None:
                continue
            row.update({f"{region}_dx": r["dx"] / k, f"{region}_dy": r["dy"] / k,
                        f"{region}_rot_dpf": r["rot_deg"] / k, f"{region}_ncc": r["ncc"],
                        f"{region}_ncc0": r["ncc0"], f"{region}_ecc": r["ecc"],
                        f"{region}_k": k, f"{region}_pair": f"{f0}-{f1}"})
            if region == "bg":
                row.update({"bg_pc_dx": r["pc_dx"] / k, "bg_pc_dy": r["pc_dy"] / k,
                            "bg_pc_resp": r["pc_resp"]})
        rows.append(row)
        if progress and f % 200 == 0:
            print(f"  {case} motion frame {f}/{n}", flush=True)
    return rows


COLUMNS_FIRST = ["frame", "polarity",
                 "bank_deg", "bank_sigma_deg", "bank_resid_px", "bank_npix", "bank_lr_diff_deg",
                 "bank_offset_px",
                 "obj_found", "obj_sign", "obj_sign_pass1", "obj_bg", "obj_noise", "obj_peak",
                 "obj_snr", "obj_cxy_sigma_px"]
MOTION_KEYS = ("dx", "dy", "rot_dpf", "ncc", "ncc0", "ecc", "k", "pair")


def write_csv(rows: list[dict], path: Path) -> list[str]:
    cols = list(COLUMNS_FIRST)
    for name, _ in OBJ_FRACS:
        cols += [f"obj_{name}_thr"] + [f"obj_{name}_{k}" for k in OBJ_KEYS]
    present = set().union(*[r.keys() for r in rows])
    for region in ("bg", "cloud"):
        cols += [f"{region}_{k}" for k in MOTION_KEYS if f"{region}_{k}" in present]
    cols += [c for c in ("bg_pc_dx", "bg_pc_dy", "bg_pc_resp") if c in present]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            out = []
            for c in cols:
                v = r.get(c, "")
                if isinstance(v, (float, np.floating)):
                    out.append("" if not np.isfinite(v) else f"{float(v):.4f}")
                elif isinstance(v, np.integer):
                    out.append(int(v))
                else:
                    out.append(v)
            w.writerow(out)
    return cols


# ----------------------------------------------------------------------------- cross-checks

def _col(rows, key):
    out = []
    for r in rows:
        v = r.get(key, np.nan)
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.array(out, float)


def _read_ref(path: Path, col: str) -> np.ndarray:
    with open(path, encoding="utf-8-sig") as fh:
        r = csv.reader(fh)
        hdr = next(r)
        j = hdr.index(col)
        vals = []
        for row in r:
            try:
                vals.append(float(row[j]))
            except (ValueError, IndexError):
                vals.append(np.nan)
    return np.array(vals)


def sitrec_bank(case: str) -> np.ndarray | None:
    """Sitrec CSV bank per frame, converted to our sign (positive = right wing down)."""
    if case == "gimbal":
        return -_read_ref(ROOT / "data/reference/sitrec/data/gimbal/GimbalData.csv", "3 bank_angle")
    if case == "gofast":
        return -_read_ref(ROOT / "data/reference/sitrec/data/gofast/Go Fast Tilt tracking.csv", "Bank Angle")
    return None


def sitrec_glare(case: str) -> np.ndarray | None:
    if case != "gimbal":
        return None
    return _read_ref(ROOT / "data/reference/sitrec/data/gimbal/GimbalData.csv", "1 glare_angle")


def axial_diff(a, b):
    return fold180(np.asarray(a, float) - np.asarray(b, float))


def unwrap_axial(a: np.ndarray) -> np.ndarray:
    ok = np.isfinite(a)
    u = np.full_like(a, np.nan)
    u[ok] = np.degrees(np.unwrap(np.radians(2 * a[ok]))) / 2
    return u


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    return o


def _num(v):
    """CSV strings back to numbers ('' -> None); other values unchanged."""
    if isinstance(v, str):
        if v == "":
            return None
        try:
            f = float(v)
            return int(f) if f.is_integer() and "." not in v else f
        except ValueError:
            return v
    return v


def summarize(case: str, rows: list[dict]) -> dict:
    out: dict = {"case": case, "n_frames": len(rows), "method": "extract/image_cues.py (see module docstring)"}
    bank = _col(rows, "bank_deg")
    out["bank"] = {"valid_frames": int(np.isfinite(bank).sum()),
                   "resid_px_median": float(np.nanmedian(_col(rows, "bank_resid_px"))),
                   "sigma_deg_median": float(np.nanmedian(_col(rows, "bank_sigma_deg"))),
                   "lr_diff_deg_median_abs": float(np.nanmedian(np.abs(_col(rows, "bank_lr_diff_deg")))),
                   "range_deg": [float(np.nanmin(bank)), float(np.nanmax(bank))]}
    sb = sitrec_bank(case)
    if sb is not None:
        m = min(len(sb), len(bank))
        a, b = bank[:m], sb[:m]
        ok = np.isfinite(a) & np.isfinite(b)
        d = a[ok] - b[ok]
        slope, icpt = np.polyfit(b[ok], a[ok], 1)
        out["sitrec_bank"] = {
            "mapping": "ours = -(Sitrec CSV bank); ours = horizon-bar line angle, CCW positive with y up",
            "n": int(ok.sum()), "mean_diff_deg": float(d.mean()),
            "mean_abs_diff_deg": float(np.abs(d).mean()), "max_abs_diff_deg": float(np.abs(d).max()),
            "rms_diff_deg": float(np.sqrt((d ** 2).mean())),
            "corr": float(np.corrcoef(a[ok], b[ok])[0, 1]),
            "fit_ours_eq_slope_x_sitrec_plus_icpt": [float(slope), float(icpt)],
            "rms_after_linear_fit_deg": float(np.sqrt(((a[ok] - (slope * b[ok] + icpt)) ** 2).mean())),
        }
        # a pixel-aspect difference between the two frame sources scales tan(angle)
        ta, tb = np.tan(np.radians(a[ok])), np.tan(np.radians(b[ok]))
        r = float((ta * tb).sum() / (tb * tb).sum())
        res = np.degrees(np.arctan(r * tb)) - a[ok]
        out["sitrec_bank"]["tan_ratio_ours_over_sitrec"] = r
        out["sitrec_bank"]["rms_after_tan_ratio_deg"] = float(np.sqrt((res ** 2).mean()))
        out["sitrec_bank"]["max_abs_after_tan_ratio_deg"] = float(np.abs(res).max())
    found = _col(rows, "obj_found") == 1
    ang = np.where(found, _col(rows, "obj_hi_angle_deg"), np.nan)
    out["obj"] = {"found_frames": int(found.sum()),
                  "snr_median": float(np.nanmedian(_col(rows, "obj_snr"))),
                  "sign_pass1_disagree_frames": int((_col(rows, "obj_sign") != _col(rows, "obj_sign_pass1")).sum())}
    if np.isfinite(ang).any():
        from scipy.ndimage import median_filter
        u = unwrap_axial(ang)
        okf = np.isfinite(u)
        us = median_filter(u[okf], 9, mode="nearest")
        out["obj"]["angle_raw_range_deg"] = [float(np.nanmin(ang)), float(np.nanmax(ang))]
        out["obj"]["angle_unwrapped_median9_range_deg"] = [float(us.min()), float(us.max())]
        out["obj"]["angle_frame_to_frame_median_abs_deg"] = float(np.nanmedian(np.abs(np.diff(u))))
        out["obj"]["angle_first_last_deg"] = [float(ang[np.isfinite(ang)][0]), float(ang[np.isfinite(ang)][-1])]
        out["obj"]["lo_hi_angle_diff_median_abs_deg"] = float(np.nanmedian(np.abs(axial_diff(
            _col(rows, "obj_lo_angle_deg"), _col(rows, "obj_hi_angle_deg")))))
    sg = sitrec_glare(case)
    if sg is not None:
        m = min(len(sg), len(ang))
        ok = np.isfinite(ang[:m])
        d = axial_diff(ang[:m][ok], sg[:m][ok])
        off = math.degrees(0.5 * math.atan2(np.sin(np.radians(2 * d)).mean(), np.cos(np.radians(2 * d)).mean()))
        r = axial_diff(d, off)
        out["sitrec_glare"] = {
            "offset_deg_ours_minus_sitrec": off, "n": int(ok.sum()),
            "mean_abs_after_offset_deg": float(np.abs(r).mean()),
            "rms_after_offset_deg": float(np.sqrt((r ** 2).mean())),
            "p95_abs_after_offset_deg": float(np.quantile(np.abs(r), 0.95)),
            "max_abs_after_offset_deg": float(np.abs(r).max()),
            "sitrec_range_deg": [float(np.nanmin(sg)), float(np.nanmax(sg))],
        }
    pol = [r["polarity"] for r in rows]
    out["polarity_segments"] = [[s, e - 1, pol[s]] for s, e in _segments(pol)]
    out["obj_at_frames"] = {}
    for f in (0, 300, 500, 700, 900, 1030):
        if f < len(rows):
            r = rows[f]
            out["obj_at_frames"][str(f)] = {k: _num(r.get(k)) for k in (
                "polarity", "obj_sign", "obj_snr", "obj_lo_area_px", "obj_hi_area_px", "obj_hi_angle_deg",
                "obj_hi_major_px", "obj_hi_minor_px", "obj_hi_integ", "obj_hi_symadj_px")}
    n = len(rows)
    for key in ("bg", "cloud"):
        dx, dy = _col(rows, f"{key}_dx"), _col(rows, f"{key}_dy")
        if not np.isfinite(dx).any():
            continue
        seg = {}
        for name, s, e in (("first100", 0, 100), ("last100", n - 100, n)):
            seg[name] = {"dx": float(np.nanmean(dx[s:e])), "dy": float(np.nanmean(dy[s:e])),
                         "speed": float(np.nanmean(np.hypot(dx[s:e], dy[s:e]))),
                         "ncc_median": float(np.nanmedian(_col(rows, f"{key}_ncc")[s:e])),
                         "ncc0_median": float(np.nanmedian(_col(rows, f"{key}_ncc0")[s:e])),
                         "ecc_median": float(np.nanmedian(_col(rows, f"{key}_ecc")[s:e]))}
        rot = _col(rows, f"{key}_rot_dpf")
        out[f"{key}_motion_px_per_frame"] = seg
        out[f"{key}_rot_dpf"] = {"median": float(np.nanmedian(rot)),
                                 "mad_sigma": robust_sigma(rot[np.isfinite(rot)]),
                                 "valid_frames": int(np.isfinite(rot).sum())}
    if "bg_pc_dx" in rows[0]:
        pcs = np.hypot(_col(rows, "bg_pc_dx"), _col(rows, "bg_pc_dy"))
        sp = np.hypot(_col(rows, "bg_dx"), _col(rows, "bg_dy"))
        out["cv2_phaseCorrelate_diagnostic"] = {
            "median_speed_pc": float(np.nanmedian(pcs)), "median_speed_ncc_ecc": float(np.nanmedian(sp)),
            "note": "phaseCorrelate locks onto a zero-shift peak on these copies; not used as motion"}
    return out


def find_orientation_steps(rows: list[dict], min_change: float = 8.0, half: int = 15) -> list[int]:
    """Frames where the object orientation changes fastest (>= min_change over 2*half frames)."""
    from scipy.ndimage import median_filter
    ang = np.where(_col(rows, "obj_found") == 1, _col(rows, "obj_hi_angle_deg"), np.nan)
    u = unwrap_axial(ang)
    ok = np.isfinite(u)
    us = u.copy()
    us[ok] = median_filter(u[ok], 9, mode="nearest")
    n = len(rows)
    rate = np.zeros(n)
    for i in range(half, n - half):
        if np.isfinite(us[i + half]) and np.isfinite(us[i - half]):
            rate[i] = abs(us[i + half] - us[i - half])
    picks, used = [], np.zeros(n, bool)
    for i in np.argsort(-rate):
        if rate[i] < min_change:
            break
        if used[i]:
            continue
        used[max(0, i - 2 * half):i + 2 * half] = True
        picks.append(int(i))
    return sorted(picks)


def step_rotation_check(case: str, rows: list[dict], centers: list[int], half: int = 15,
                        mc: MotionContext | None = None) -> list[dict]:
    """At each orientation step: object angle change vs background rotation over the same window.

    Background rotation is chained over consecutive pairs whose baseline k covers about 8 px
    of motion (from the per-frame rate), so the zero-shift bias does not pull it to 0.
    rot_sigma_deg = std of the pair rotations * sqrt(number of pairs), a scatter-based error.
    """
    mc = mc or MotionContext(case)
    ang = unwrap_axial(np.where(_col(rows, "obj_found") == 1, _col(rows, "obj_hi_angle_deg"), np.nan))
    bank = _col(rows, "bank_deg")
    cx, cy = _col(rows, "obj_hi_cx"), _col(rows, "obj_hi_cy")
    out = []
    for c in centers:
        s, e = max(c - half, 0), min(c + half, len(rows) - 1)
        rec = {"center_frame": c, "window": [s, e],
               "obj_angle_change_deg": float(np.nanmedian(ang[e - 2:e + 1]) - np.nanmedian(ang[s:s + 3])),
               "bank_change_deg": float(bank[e] - bank[s])}
        for region, (_, k0, _) in mc.regions.items():
            sp = np.hypot(_col(rows, f"{region}_dx"), _col(rows, f"{region}_dy"))
            rots, eccs, margins = [], [], []
            f = s
            while f < e:
                speed = sp[f] if np.isfinite(sp[f]) and sp[f] > 0 else 8.0 / mc.cfg.kmax
                k = int(min(max(k0, math.ceil(8.0 / speed)), mc.cfg.kmax, e - f))
                if k < 1:
                    break
                r = mc.measure(region, f, f + k, ((cx[f], cy[f]), (cx[f + k], cy[f + k])), pc=False)
                rots.append(r["rot_deg"])
                eccs.append(r["ecc"])
                margins.append(r["ncc"] - r["ncc0"])
                f += k
            rv = np.array(rots, float)
            ok = np.isfinite(rv)
            rec[f"{region}_rot_deg"] = float(rv[ok].sum()) if ok.any() else None
            rec[f"{region}_rot_pairs"] = [None if not np.isfinite(v) else round(float(v), 4) for v in rv]
            rec[f"{region}_rot_sigma_deg"] = (float(rv[ok].std(ddof=1) * math.sqrt(ok.sum()))
                                              if ok.sum() > 2 else None)
            rec[f"{region}_span"] = [s, f]
            rec[f"{region}_ecc_min"] = float(np.nanmin(eccs)) if np.isfinite(eccs).any() else None
            rec[f"{region}_ncc_margin_min"] = float(np.min(margins)) if margins else None
        out.append(rec)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Per-frame image cues (bank, object, background motion).")
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--frames", type=int, default=None, help="process only the first N frames")
    ap.add_argument("--summary-only", action="store_true",
                    help="recompute image_track_summary.json from an existing image_track.csv")
    a = ap.parse_args(argv)
    outdir = ROOT / "data" / "derived" / a.case
    if a.summary_only:
        with open(outdir / "image_track.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    else:
        rows = run_case(a.case, a.frames)
        write_csv(rows, outdir / "image_track.csv")
    summ = summarize(a.case, rows)
    steps = find_orientation_steps(rows)
    if a.case == "gimbal":
        for f in (700, 900):   # the steps named in the M1.4 work item, checked even if not picked
            if f < len(rows) and not any(abs(f - s) <= 15 for s in steps):
                steps.append(f)
    summ["orientation_steps"] = step_rotation_check(a.case, rows, sorted(steps))
    summ = _clean(summ)
    with open(outdir / "image_track_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summ, fh, indent=2)
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
