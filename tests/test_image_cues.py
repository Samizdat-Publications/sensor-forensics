"""Synthetic fixtures for extract/image_cues.py (M1.4)."""

import math

import cv2
import numpy as np
import pytest
from scipy.ndimage import fourier_shift

from extract.image_cues import (
    measure_bank,
    measure_object,
    phase_shift,
    prep_motion,
    register_pair,
    thin_stroke_mask,
)

H, W = 480, 640
CENTER = (317.5, 182.5)
BOX = (226, 120, 412, 250)


def _noisy_bg(level=90.0, sigma=4.0, seed=1):
    rng = np.random.default_rng(seed)
    return np.full((H, W), level, np.float32) + rng.normal(0, sigma, (H, W)).astype(np.float32)


def _render_bars(angle_deg, seed=1):
    """Two bright bars symmetric about the reticle, with end ticks and the reticle itself.

    Returns the image and the exact angle of the drawn line (CCW, y up).
    """
    img = _noisy_bg(seed=seed)
    S = 16  # fixed-point shift 4 bits
    ux, uy = math.cos(math.radians(angle_deg)), -math.sin(math.radians(angle_deg))
    cx, cy = CENTER
    layer = np.zeros((H, W), np.uint8)

    def P(x, y):
        return (int(round(x * S)), int(round(y * S)))

    for sgn in (-1, 1):
        a = P(cx + sgn * 32 * ux, cy + sgn * 32 * uy)
        b = P(cx + sgn * 80 * ux, cy + sgn * 80 * uy)
        cv2.line(layer, a, b, 255, 2, cv2.LINE_AA, 4)
        # short end tick, perpendicular, pointing down
        tx, ty = -uy, ux
        if ty < 0:
            tx, ty = -tx, -ty
        e = (cx + sgn * 80 * ux, cy + sgn * 80 * uy)
        cv2.line(layer, P(*e), P(e[0] + 8 * tx, e[1] + 8 * ty), 255, 2, cv2.LINE_AA, 4)
    cv2.circle(layer, (int(cx), int(cy)), 8, 255, 2, cv2.LINE_AA)
    cv2.line(layer, (int(cx) - 24, int(cy)), (int(cx) - 9, int(cy)), 255, 2)
    cv2.line(layer, (int(cx) + 9, int(cy)), (int(cx) + 24, int(cy)), 255, 2)
    img = img + 0.4 * layer.astype(np.float32)
    # exact angle of the fixed-point segment that was drawn (right bar)
    a = P(cx + 32 * ux, cy + 32 * uy)
    b = P(cx + 80 * ux, cy + 80 * uy)
    true = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0]))
    return np.clip(img, 0, 255).astype(np.uint8), true


@pytest.mark.parametrize("angle", [-36.0, -22.6, -4.1, 0.0, 1.5, 13.4, 31.0])
def test_bank_line_angle_recovered(angle):
    img, true = _render_bars(angle)
    r = measure_bank(img, BOX, CENTER, mask_r=28.0, k=7)
    assert abs(r["bank_deg"] - true) < 0.2, (r, true)
    assert r["bank_npix"] > 100
    assert r["bank_resid_px"] < 1.0
    assert abs(r["bank_offset_px"]) < 1.0


def _render_ellipse(theta_deg, cx, cy, a=9.0, b=4.0, bg=60.0, fg=200.0, noise=2.0, ss=8, seed=3,
                    size=(120, 120)):
    """Anti-aliased filled ellipse; theta CCW from +x with y up; centroid (cx, cy) in pixel coords."""
    h, w = size
    ys, xs = np.mgrid[0:h * ss, 0:w * ss]
    X = (xs + 0.5) / ss - 0.5
    Y = (ys + 0.5) / ss - 0.5
    ux, uy = math.cos(math.radians(theta_deg)), -math.sin(math.radians(theta_deg))
    dx, dy = X - cx, Y - cy
    p = dx * ux + dy * uy
    q = -dx * uy + dy * ux
    m = ((p / a) ** 2 + (q / b) ** 2 <= 1).astype(np.float32)
    cov = m.reshape(h, ss, w, ss).mean(axis=(1, 3))
    rng = np.random.default_rng(seed)
    img = bg + (fg - bg) * cov + rng.normal(0, noise, (h, w))
    return np.clip(img, 0, 255).astype(np.uint8)


@pytest.mark.parametrize("theta,cx,cy", [(30.0, 60.3, 58.7), (-50.0, 59.6, 61.2), (75.0, 61.1, 60.4),
                                         (-5.0, 60.0, 60.0)])
def test_rotated_ellipse_recovered(theta, cx, cy):
    img = _render_ellipse(theta, cx, cy)
    r = measure_object(img, (62, 58), search=18, ring=(24, 34))
    assert r["obj_found"] == 1 and r["obj_sign"] == 1
    assert abs(r["obj_hi_cx"] - cx) < 0.3 and abs(r["obj_hi_cy"] - cy) < 0.3, r
    d = (r["obj_hi_angle_deg"] - theta + 90) % 180 - 90
    assert abs(d) < 1.0, (r["obj_hi_angle_deg"], theta)
    # equivalent-ellipse axes close to the true full axes (2a, 2b)
    assert abs(r["obj_hi_major_px"] - 18) < 1.0 and abs(r["obj_hi_minor_px"] - 8) < 1.0
    # lower threshold gives a blob at least as large
    assert r["obj_lo_area_px"] >= r["obj_hi_area_px"]


def test_polarity_inversion_same_blob():
    rng = np.random.default_rng(7)
    tex = cv2.GaussianBlur(rng.normal(0, 12, (120, 120)).astype(np.float32), (0, 0), 3)
    img = _render_ellipse(-40.0, 60.4, 59.2, bg=110.0, fg=20.0, noise=3.0).astype(np.float32) + tex
    img = np.clip(img, 0, 255).astype(np.uint8)
    inv = (255 - img).astype(np.uint8)
    r1 = measure_object(img, (60, 60), search=18, ring=(24, 34))
    r2 = measure_object(inv, (60, 60), search=18, ring=(24, 34))
    assert r1["obj_sign"] == -1 and r2["obj_sign"] == 1
    for k, v in r1.items():
        if k in ("obj_sign", "obj_bg"):
            continue
        assert v == pytest.approx(r2[k], rel=1e-6, abs=1e-6), k
    assert r1["obj_bg"] == pytest.approx(255 - r2["obj_bg"], abs=1e-4)


def test_brackets_excluded_from_blob():
    base = _render_ellipse(80.0, 60.0, 60.0, a=10.0, b=5.0)
    br = base.copy()
    br[44:78, 50:52] = 170   # bright vertical bracket lines just outside the blob
    br[44:78, 69:71] = 170
    sym = thin_stroke_mask(br, 15)
    r0 = measure_object(base, (60, 60), search=18, ring=(24, 34))
    r1 = measure_object(br, (60, 60), search=18, ring=(24, 34), sym_mask=sym)
    assert sym[50:70, 50].all() and sym[50:70, 70].all()
    assert abs(r1["obj_hi_area_px"] - r0["obj_hi_area_px"]) <= 4
    assert abs(r1["obj_hi_cx"] - r0["obj_hi_cx"]) < 0.3


def _texture(seed=5, size=(220, 240)):
    rng = np.random.default_rng(seed)
    t = cv2.GaussianBlur(rng.normal(0, 1, size).astype(np.float32), (0, 0), 3)
    return (t / t.std() * 25 + 100).astype(np.float64)


@pytest.mark.parametrize("dx,dy", [(2.3, -1.6), (0.4, 0.25), (-6.7, 3.1)])
def test_translated_texture_recovered(dx, dy):
    a = _texture()
    b = np.real(np.fft.ifft2(fourier_shift(np.fft.fft2(a), (dy, dx))))
    valid = np.ones(a.shape, bool)
    A, B = prep_motion(a, valid), prep_motion(b, valid)
    r = register_pair(A, B, valid, max_shift=16)
    assert abs(r["dx"] - dx) < 0.1 and abs(r["dy"] - dy) < 0.1, r
    assert abs(r["rot_deg"]) < 0.05


def test_phase_correlate_diagnostic_sign_convention():
    # cv2.phaseCorrelate (diagnostic column only) uses the same sign convention as register_pair
    rng = np.random.default_rng(11)
    a = cv2.GaussianBlur(rng.normal(100, 20, (200, 200)).astype(np.float32), (0, 0), 1.0)
    b = np.roll(a, (-2, 3), axis=(0, 1))   # content moves +3 px in x, -2 px in y
    pdx, pdy, resp = phase_shift(a, b)
    assert abs(pdx - 3) < 0.1 and abs(pdy + 2) < 0.1 and resp > 0.3


def test_rotation_sign_ccw_positive():
    a = _texture(seed=9, size=(260, 260))
    M = cv2.getRotationMatrix2D((130, 130), 0.8, 1.0)  # +angle = counter-clockwise on screen
    b = cv2.warpAffine(a.astype(np.float32), M, (260, 260), flags=cv2.INTER_CUBIC,
                       borderMode=cv2.BORDER_REFLECT)
    valid = np.ones(a.shape, bool)
    r = register_pair(prep_motion(a, valid), prep_motion(b, valid), valid, max_shift=12)
    assert abs(r["rot_deg"] - 0.8) < 0.05, r
    assert abs(r["dx"]) < 0.1 and abs(r["dy"]) < 0.1
