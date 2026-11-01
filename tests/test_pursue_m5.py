"""Tests for the M5 bounded PURSUE helpers (extract/pursue_m5.py), on synthetic images."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from extract.pursue_m5 import (
    anisotropic_spacing, blob_centroid, colour_mask, gate_extent, gate_label_test,
    image_shift, ladder_fit, ladder_profile_fit, mover_peak, range_from_scale, range_like_test,
    size_speed_vs_range, size_speed_vs_ratio,
)


def _canvas(h=400, w=600, v=60):
    rng = np.random.default_rng(0)
    return np.clip(rng.normal(v, 4, (h, w, 3)), 0, 255).astype(np.uint8)


def test_colour_mask_picks_hue_band():
    im = _canvas()
    cv2.rectangle(im, (100, 100), (160, 160), (255, 255, 0), 1)  # cyan (BGR)
    cv2.rectangle(im, (300, 100), (360, 160), (0, 0, 255), 1)  # red
    m = colour_mask(im, 80, 100)
    assert m[100, 100:161].all() and not m[100, 300:361].any()


@pytest.mark.parametrize("side", [24, 60, 150])
def test_gate_extent_box_with_label(side):
    im = _canvas()
    x0, y0 = 200, 120
    cv2.rectangle(im, (x0, y0), (x0 + side - 1, y0 + side - 1), (255, 255, 0), 1)
    cv2.putText(im, "36M", (x0 + side + 3, y0 + side // 2 + 4), 0, 0.4, (255, 255, 0), 1)
    g = gate_extent(colour_mask(im, 80, 100), (x0 + side / 2, y0 + side / 2), link_px=9)
    assert g is not None and g.h == side


def test_gate_extent_corner_brackets_linked():
    im = _canvas()
    x0, y0, s, arm = 200, 100, 80, 12
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x0 + s, y0, -1, 1), (x0, y0 + s, 1, -1), (x0 + s, y0 + s, -1, -1)]:
        cv2.line(im, (cx, cy), (cx + dx * arm, cy), (255, 255, 0), 1)
        cv2.line(im, (cx, cy), (cx, cy + dy * arm), (255, 255, 0), 1)
    m = colour_mask(im, 80, 100)
    g = gate_extent(m, (x0 + s / 2, y0 + s / 2), link_px=s - 2 * arm + 4)
    assert g.h == s + 1


def test_mover_peak_and_centroid_find_small_moving_blob():
    rng = np.random.default_rng(1)
    bg = np.clip(rng.normal(80, 3, (300, 400)), 0, 255).astype(np.uint8)
    frames = []
    for k in range(3):
        f = bg.copy()
        cv2.rectangle(f, (300, 50), (360, 120), 200, -1)  # a static bright "ship"
        cv2.circle(f, (100 + 20 * k, 200 - 3 * k), 3, 220, -1)
        frames.append(f)
    x, y, s = mover_peak(*frames)
    assert abs(x - 120) <= 2 and abs(y - 197) <= 2 and s > 50
    cx, cy, ex, ey, n = blob_centroid(frames[1], (x, y), r=8)
    assert abs(cx - 120) < 0.5 and abs(cy - 197) < 0.5 and 5 <= ex <= 9 and n > 10


def test_image_shift_recovers_translation():
    rng = np.random.default_rng(2)
    a = cv2.GaussianBlur(rng.normal(100, 30, (256, 256)).astype(np.float32), (7, 7), 0)
    M = np.float32([[1, 0, 5.0], [0, 1, -3.0]])
    b = cv2.warpAffine(a, M, (256, 256), borderMode=cv2.BORDER_REFLECT)
    dx, dy, _ = image_shift(a, b)
    assert abs(dx - 5) < 0.3 and abs(dy + 3) < 0.3


def test_gate_label_test_separates_the_two_readings():
    px = np.array([150, 126, 66, 54, 42, 30, 21])
    width = 0.25 * px  # labels that are gate widths at 0.25 m/px
    t = gate_label_test(width, px)
    assert t["m_per_px_rel_spread"] < 1e-9 and abs(t["loglog_slope"] - 1) < 1e-9
    rng_label = np.full(px.shape, 3000.0)  # a range: independent of gate size
    t2 = gate_label_test(rng_label, px)
    assert t2["m_per_px_rel_spread"] > 0.5 and abs(t2["loglog_slope"]) < 1e-9
    # zoom: label constant while the gate grows in px with magnification -> still width
    zoom = np.array([1.0, 1.5, 2.0])
    t3 = gate_label_test(np.full(3, 29.0), 100 * zoom, scene_scale=zoom)
    assert t3["m_per_px_rel_spread"] < 1e-9


def test_range_like_test_constant_height():
    el = np.array([-7, -8, -9, -10.0])
    h = 8.5
    R = h / np.sin(np.radians(-el))
    t = range_like_test(R, el)
    assert abs(t["h_median"] - h) < 1e-9 and t["h_rel_spread"] < 1e-9


def test_ladder_fit_roll_and_direction():
    v = np.array([15, 20, 25, 30.0])
    for roll in (0.0, 30.0, -45.0, 180.0):
        r = np.radians(roll)
        d = np.array([-np.sin(r), np.cos(r)])  # "increasing value" direction, image coords
        pts = np.array([500, 400]) + np.outer((v - 20) * 36.0, d)
        out = ladder_fit(v, pts)
        assert abs(out["px_per_unit"] - 36.0) < 1e-6 and out["rms_px"] < 1e-6
        assert abs(((out["roll_deg"] - roll + 180) % 360) - 180) < 1e-6
    assert ladder_fit(v, np.c_[np.zeros(4), -36 * v])["numbers_increase"] == "up"


def _ladder_image(spacing=180.0, psi=0.0, n=5):
    im = np.full((1080, 1920, 3), 70, np.uint8)
    c = np.array([960.0, 540.0])
    u = np.array([np.cos(np.radians(psi)), np.sin(np.radians(psi))])
    nrm = np.array([-u[1], u[0]])
    for k in range(n):
        o = c + (k - n // 2) * spacing * nrm
        for s in (-1, 1):
            a = o + s * 40 * u
            b = o + s * 160 * u
            cv2.line(im, tuple(int(v) for v in a), tuple(int(v) for v in b), (230, 230, 230), 3)
    return im


@pytest.mark.parametrize("psi", [0.0, 20.0, -35.0])
def test_ladder_profile_fit_spacing_and_angle(psi):
    r = ladder_profile_fit(_ladder_image(180.0, psi))
    assert abs(r["spacing_px"] - 180.0) < 3.0
    assert abs(abs(r["angle_deg"]) - abs(psi)) < 1.5 and r["quality"] > 0.3


def test_anisotropic_spacing():
    assert np.allclose(anisotropic_spacing([0, 30, 80], 180, 1.0), 180)
    assert abs(anisotropic_spacing(0.0, 180, 1.8) - 180) < 1e-9
    assert anisotropic_spacing(60.0, 180, 1.8) > 180 * 1.5


def test_curves_scale_linearly():
    s, v = size_speed_vs_range(np.array([1000.0, 2000.0]), 10, 100, 1e-4)
    assert np.allclose(s, [1.0, 2.0]) and np.allclose(v, [10.0, 20.0])
    s, v = size_speed_vs_ratio(np.array([0.5, 1.0]), 8, 600, 0.2)
    assert np.allclose(s, [0.8, 1.6]) and np.allclose(v, [60, 120])
    R = range_from_scale(0.25, np.array([1.0]), 1280)
    assert abs(R[0] - 0.25 / (2 * np.tan(np.radians(0.5)) / 1280)) < 1e-6
