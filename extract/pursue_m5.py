"""M5 bounded PURSUE analysis: small, tested measurement helpers (D-013).

The eight bounded clips have no per-frame line of sight, only a scale: a tracker gate
with a metre label, an elevation readout with an "NNM" label, a burned-in ladder, or a
ship of known class. These helpers measure what the scale needs:

- `colour_mask`        symbology pixels of one hue band (the gates are drawn in colour)
- `gate_extent`        the tracker gate's size in pixels near a point (box or corner brackets)
- `mover_peak`         a small object moving against a slowly drifting background
                       (frame minus the brighter of its two temporal neighbours)
- `blob_centroid`      sub-pixel centroid and extent of a bright blob near a guess
- `image_shift`        background shift between two frames (phase correlation)
- `gate_label_test`    the two readings of a gate label, tested on (label, gate px, scene scale)
- `range_like_test`    whether a label behaves like slant range to a level plane (R sin|el| constant)
- `ladder_fit`         rung spacing (px per unit), roll and numbering direction from rung points
- curve builders       object size and speed as functions of assumed range or range ratio

Readings of the on-screen numbers themselves are made by eye on sampled frames and stored
as data (data/derived/pursue/<clip>/readings_manual.csv), never inferred by code.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# image measurements
# ---------------------------------------------------------------------------

def colour_mask(img_bgr: np.ndarray, hue_lo: int, hue_hi: int, s_min: int = 90,
                v_min: int = 70) -> np.ndarray:
    """Boolean mask of pixels whose OpenCV hue (0..179) lies in [hue_lo, hue_hi]."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if hue_lo <= hue_hi:
        hm = (h >= hue_lo) & (h <= hue_hi)
    else:  # wraps through 0 (reds, magentas)
        hm = (h >= hue_lo) | (h <= hue_hi)
    return hm & (s >= s_min) & (v >= v_min)


@dataclass
class Gate:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def w(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def h(self) -> int:
        return self.y1 - self.y0 + 1

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def gate_extent(mask: np.ndarray, near_xy: tuple[float, float], search: int = 220,
                link_px: int = 14, min_size: int = 10,
                exclude: np.ndarray | None = None) -> Gate | None:
    """Gate box around `near_xy` from a symbology mask.

    Pixels within `search` of the point are linked by a dilation of `link_px` (so the four
    corner brackets of a bracket gate join into one group, and a box's sides stay one group);
    the group nearest the point is taken. The gate SIZE is its vertical extent: the metre
    label sits beside the gate at mid height, so it can widen the group but never heighten
    it. `exclude` masks fixed symbology (crosshair, frame ticks) before linking.
    """
    H, W = mask.shape
    x, y = int(round(near_xy[0])), int(round(near_xy[1]))
    xa, xb = max(0, x - search), min(W, x + search + 1)
    ya, yb = max(0, y - search), min(H, y + search + 1)
    m = mask[ya:yb, xa:xb].copy()
    if exclude is not None:
        m &= ~exclude[ya:yb, xa:xb]
    if not m.any():
        return None
    k = np.ones((link_px, link_px), np.uint8)
    lab_n, lab = cv2.connectedComponents(cv2.dilate(m.astype(np.uint8), k))
    best, best_d = None, np.inf
    for i in range(1, lab_n):
        ys, xs = np.nonzero((lab == i) & m)
        if len(ys) == 0:
            continue
        h = ys.max() - ys.min() + 1
        if h < min_size:
            continue
        # distance from the point to the group's bounding box (0 if inside)
        dx = max(xs.min() - (x - xa), 0, (x - xa) - xs.max())
        dy = max(ys.min() - (y - ya), 0, (y - ya) - ys.max())
        d = float(np.hypot(dx, dy))
        if d < best_d:
            best_d, best = d, (xs.min() + xa, ys.min() + ya, xs.max() + xa, ys.max() + ya)
    return None if best is None else Gate(*[int(v) for v in best])


def mover_peak(prev: np.ndarray, cur: np.ndarray, nxt: np.ndarray,
               valid: np.ndarray | None = None) -> tuple[int, int, float]:
    """Brightest point that is brighter in `cur` than in BOTH temporal neighbours.

    A small bright object moving several pixels per frame leaves this residual; a static or
    slowly drifting background (and a large bright ship) does not. Gray uint8 inputs.
    """
    d = cur.astype(np.float32) - np.maximum(prev, nxt).astype(np.float32)
    d = cv2.GaussianBlur(d, (3, 3), 0)
    if valid is not None:
        d[~valid] = -1e9
    y, x = np.unravel_index(int(np.argmax(d)), d.shape)
    return int(x), int(y), float(d[y, x])


def blob_centroid(gray: np.ndarray, xy: tuple[float, float], r: int = 8,
                  tophat: int = 11, k_sigma: float = 4.0, rel_peak: float = 0.0) -> tuple[float, float, float, float, int] | None:
    """Sub-pixel centroid (x, y), extent along x and along y (px) and pixel count of
    the bright blob nearest `xy`, from a white top-hat thresholded at median + k_sigma * MAD, or
    at rel_peak times the window's peak if that is higher (rel_peak = 0.5 gives a half-maximum
    extent, less sensitive to the halo of a bright point)."""
    H, W = gray.shape
    x, y = int(round(xy[0])), int(round(xy[1]))
    xa, xb, ya, yb = max(0, x - r), min(W, x + r + 1), max(0, y - r), min(H, y + r + 1)
    pad = tophat
    pa, pb, qa, qb = max(0, xa - pad), min(W, xb + pad), max(0, ya - pad), min(H, yb + pad)
    th = cv2.morphologyEx(gray[qa:qb, pa:pb], cv2.MORPH_TOPHAT,
                          np.ones((tophat, tophat), np.uint8)).astype(np.float32)
    med = float(np.median(th))
    mad = float(np.median(np.abs(th - med))) * 1.4826 + 1e-6
    win = th[ya - qa:yb - qa, xa - pa:xb - pa]
    thr = max(med + k_sigma * mad, med + rel_peak * (float(win.max()) - med))
    m = (win > thr).astype(np.uint8)
    if not m.any():
        return None
    n, lab = cv2.connectedComponents(m)
    best, best_d = None, np.inf
    for i in range(1, n):
        ys, xs = np.nonzero(lab == i)
        cx, cy = xs.mean() + xa, ys.mean() + ya
        d = np.hypot(cx - x, cy - y)
        if d < best_d:
            best_d, best = d, (ys, xs)
    ys, xs = best
    w = win[ys, xs] - med
    cx = float((xs * w).sum() / w.sum()) + xa
    cy = float((ys * w).sum() / w.sum()) + ya
    return cx, cy, float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1), int(len(xs))


def image_shift(a: np.ndarray, b: np.ndarray, window: bool = True) -> tuple[float, float, float]:
    """Translation (dx, dy) that maps frame `a` onto frame `b` (phase correlation), plus the
    peak response. Gray inputs of equal shape."""
    fa, fb = a.astype(np.float32), b.astype(np.float32)
    win = cv2.createHanningWindow(fa.shape[::-1], cv2.CV_32F) if window else None
    (dx, dy), resp = cv2.phaseCorrelate(fa, fb, win)
    return float(dx), float(dy), float(resp)


def ladder_profile_fit(img_bgr: np.ndarray, lag_px: tuple[int, int] = (140, 350),
                       exclude_small_roll: float = 0.0, scale: float = 0.5,
                       tophat_thresh: float = 40.0) -> dict:
    """Rung direction and rung spacing of a burned-in ladder, without reading any digit.

    Bright thin strokes (white top-hat, with horizontal tape streaks longer than 300 px removed) are rotated through
    candidate angles; the angle that makes the rungs horizontal maximises the sharpness of the
    row-sum profile (sum of squares). The spacing is the first autocorrelation peak of that
    profile inside `lag_px` (full-resolution px), refined parabolically. `quality` is the
    normalised autocorrelation at that lag (about 0.45 or more means a clean ladder).
    The angle is the image angle of the rungs (deg, positive = rungs falling to the right).
    """
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, np.ones((9, 9), np.uint8))
    th = th - cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((1, 301), np.uint8))
    m = (th > tophat_thresh).astype(np.float32)
    m = cv2.resize(m, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = m.shape

    def prof(a: float) -> np.ndarray:
        R = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1)
        return cv2.warpAffine(m, R, (w, h)).sum(1)

    angs = np.arange(-89.0, 90.0, 1.0)
    if exclude_small_roll > 0:
        angs = angs[np.abs(angs) > exclude_small_roll]
    sc = np.array([(prof(a) ** 2).sum() for a in angs])
    a0 = angs[int(np.argmax(sc))]
    fine = np.arange(a0 - 1, a0 + 1.0001, 0.1)
    a = float(fine[int(np.argmax([(prof(x) ** 2).sum() for x in fine]))])
    p = prof(a)
    p = p - p.mean()
    ac = np.correlate(p, p, "full")[len(p) - 1:]
    lo, hi = int(lag_px[0] * scale), int(lag_px[1] * scale)
    L = lo + int(np.argmax(ac[lo:hi + 1]))
    y0, y1, y2 = ac[L - 1], ac[L], ac[L + 1]
    den = y0 - 2 * y1 + y2
    d = 0.5 * (y0 - y2) / den if den != 0 else 0.0
    q = float(ac[L] / ac[0]) if ac[0] > 0 else 0.0
    return {"angle_deg": a, "spacing_px": float((L + d) / scale), "quality": q}


def anisotropic_spacing(psi_deg: np.ndarray, s0: float, aspect: float) -> np.ndarray:
    """Perpendicular rung spacing seen in an image whose x axis is stretched by `aspect`
    relative to y, for rungs at image angle psi (s0 = spacing at zero roll, in y pixels).
    True roll phi satisfies tan(psi) = tan(phi) / aspect; spacing = aspect s0 /
    sqrt(aspect^2 cos^2 phi + sin^2 phi). With aspect = 1 the spacing is s0 at any roll."""
    psi = np.radians(np.asarray(psi_deg, float))
    phi = np.arctan(aspect * np.tan(psi))
    return aspect * s0 / np.sqrt(aspect ** 2 * np.cos(phi) ** 2 + np.sin(phi) ** 2)


# ---------------------------------------------------------------------------
# tests of what a label means
# ---------------------------------------------------------------------------

def gate_label_test(label_m: np.ndarray, gate_px: np.ndarray,
                    scene_scale: np.ndarray | None = None) -> dict:
    """Test the two readings of a tracker-gate metre label.

    Width reading: label = gate width in metres = gate_px * (metres per pixel at the gate's
    range), and metres per pixel depends only on range and zoom. So label / gate_px is
    constant while range and zoom hold (the gate can resize freely), and it scales as
    1 / scene_scale when the sensor zooms (scene_scale = magnification relative to the first
    sample, 1 when unknown). Range reading: the label is independent of the gate size.

    Returns the spread of label/gate_px (zoom-corrected) and the correlation of log(label)
    with log(gate_px). Width reading consistent: small spread and slope near 1.
    """
    label_m = np.asarray(label_m, float)
    gate_px = np.asarray(gate_px, float)
    s = np.ones_like(gate_px) if scene_scale is None else np.asarray(scene_scale, float)
    mpp = label_m / gate_px * s  # metres per pixel referred to the first sample's zoom
    ok = np.isfinite(mpp)
    lx, ly = np.log(gate_px[ok] / s[ok]), np.log(label_m[ok])
    slope = float(np.polyfit(lx, ly, 1)[0]) if ok.sum() >= 2 and np.ptp(lx) > 0 else float("nan")
    r = (float(np.corrcoef(lx, ly)[0, 1]) if ok.sum() >= 3 and np.ptp(lx) > 0 and np.ptp(ly) > 0
         else float("nan"))
    return {
        "n": int(ok.sum()),
        "m_per_px_median": float(np.median(mpp[ok])),
        "m_per_px_rel_spread": float(np.std(mpp[ok]) / np.mean(mpp[ok])),
        "gate_px_ratio": float(np.ptp(gate_px[ok]) / np.min(gate_px[ok]) + 1) if ok.any() else float("nan"),
        "loglog_slope": slope,
        "loglog_r": r,
    }


def range_like_test(label: np.ndarray, el_deg: np.ndarray, el_halfwidth_deg: float = 0.5) -> dict:
    """If the label is slant range R to a point on a level plane a height h below the sensor,
    R sin|el| = h is constant while the platform altitude holds. Returns h per sample, its
    median and spread, plus the spread expected from whole-degree rounding of el alone."""
    label = np.asarray(label, float)
    el = np.radians(np.abs(np.asarray(el_deg, float)))
    h = label * np.sin(el)
    rel_round = np.radians(el_halfwidth_deg) / np.tan(el)  # d(sin)/sin for a half-degree error
    return {
        "h": h,
        "h_median": float(np.median(h)),
        "h_rel_spread": float(np.std(h) / np.mean(h)),
        "rounding_rel_halfwidth_median": float(np.median(rel_round)),
        "horizontal": label * np.cos(el),
    }


def ladder_fit(values: np.ndarray, pts_xy: np.ndarray) -> dict:
    """Fit rung positions (pts_xy, one point per labelled rung, e.g. the left end of each
    rung) against their labels (values). Returns px per unit along the ladder axis, the axis
    roll (deg, image x to the right, y down; 0 when rungs stack vertically with the numbers
    increasing downward), the numbering direction and the rms of the fit."""
    v = np.asarray(values, float)
    p = np.asarray(pts_xy, float)
    A = np.c_[v - v.mean(), np.ones_like(v)]
    cx, *_ = np.linalg.lstsq(A, p[:, 0], rcond=None)
    cy, *_ = np.linalg.lstsq(A, p[:, 1], rcond=None)
    step = np.array([cx[0], cy[0]])  # px per unit, in image coordinates
    spacing = float(np.hypot(*step))
    pred = np.c_[A @ cx, A @ cy]
    rms = float(np.sqrt(np.mean(np.sum((pred - p) ** 2, axis=1))))
    # roll: angle of the "increasing value" direction from image-down
    roll = float(np.degrees(np.arctan2(-step[0], step[1])))
    return {
        "px_per_unit": spacing,
        "roll_deg": roll,
        "numbers_increase": "down" if abs(roll) < 90 else "up",
        "rms_px": rms,
    }


# ---------------------------------------------------------------------------
# curves
# ---------------------------------------------------------------------------

def size_speed_vs_range(range_m: np.ndarray, extent_px: float, rate_px_s: float,
                        ifov_rad: float) -> tuple[np.ndarray, np.ndarray]:
    """Small-angle size (m) and transverse speed (m/s) of an object at slant range R, from its
    image extent and image rate with a known angular pixel scale (ifov_rad per px). The
    speed is the transverse component relative to the sensor platform (a lower bound on the
    total relative speed; Haqq-Misra and Kopparapu Eq. 2 with theta = 90 deg)."""
    r = np.asarray(range_m, float)
    return r * extent_px * ifov_rad, r * rate_px_s * ifov_rad


def size_speed_vs_ratio(ratio: np.ndarray, extent_px: float, rate_px_s: float,
                        m_per_px_ref: float) -> tuple[np.ndarray, np.ndarray]:
    """Size and transverse speed of an object at range ratio R_obj / R_ref, where m_per_px_ref
    is the scale fixed at the reference range (a ship of known length, or a gate whose label
    gives metres at the range the tracker used). Haqq-Misra and Kopparapu Eq. 10."""
    q = np.asarray(ratio, float)
    return q * extent_px * m_per_px_ref, q * rate_px_s * m_per_px_ref


def range_from_scale(m_per_px: float, hfov_deg: np.ndarray, width_px: int) -> np.ndarray:
    """Range at which a pixel spans m_per_px for an assumed horizontal field of view
    (rectilinear, centre of frame, small pixel): R = m_per_px / IFOV."""
    hf = np.radians(np.asarray(hfov_deg, float))
    ifov = 2 * np.tan(hf / 2) / width_px
    return m_per_px / ifov
