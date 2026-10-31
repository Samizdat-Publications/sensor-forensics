"""Tests for extract/symbology.py (M1.3, per-frame ATFLIR symbology reading)."""

from __future__ import annotations

import csv

import cv2
import numpy as np
import pytest

from extract import symbology as sym

FRAMES_8 = [0, 147, 294, 441, 589, 736, 883, 1030]

# Ground truth read by eye from artifacts/cp01/<case>_fields.png and re-checked at 7x zoom
# with neighbor frames (docs/audit/<case>.md tables give the first-to-last ranges).
# "*" = not readable by eye: GOFAST f736 altitude is an interlaced frame whose two fields show
# 25000 and 25010 (the display flickers between them from f635 to f839); either is accepted.
GT = {
    "gimbal": {
        "azimuth": "54L 48L 41L 32L 23L 13L 2L 7R",
        "elevation": "-2 -2 -2 -2 -2 -2 -2 -2",
        "altitude": "25010 25010 25010 25000 25010 25010 25010 25010",
        "airspeed": "238 239 240 241 242 242 241 241",
        "mach": "0.58 0.58 0.58 0.58 0.59 0.59 0.58 0.58",
        "clock": "5245 5250A 5255A 5300A 5304A 5309A 5314A 5319A",
        "zoom": "2.0 2.0 2.0 2.0 2.0 2.0 2.0 2.0",
        "sensor": "IR IR IR IR IR IR IR IR",
        "polarity": "WHT WHT WHT BLK BLK BLK BLK BLK",
    },
    "gofast": {
        "azimuth": "35L 38L 41L 46L 49L 51L 55L 58L",
        "elevation": "-22 -24 -25 -27 -29 -31 -33 -36",
        "range": "blank blank blank 4.3 4.0 3.8 3.5 3.3",
        "closure": "blank blank blank 210 190 180 160 150",
        "altitude": "25000 25000 25000 25000 25000 * 25010 25010",
        "airspeed": "252 252 253 254 254 255 256 259",
        "mach": "0.61 0.61 0.61 0.61 0.61 0.61 0.62 0.62",
        "clock": "4220A 4225A 4230A 4234A 4239A 4244A 4249A 4254A",
        "zoom": "1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0",
        "sensor": "IR IR IR IR IR IR IR IR",
        "polarity": "BLK BLK BLK BLK BLK WHT BLK BLK",
    },
}
AMBIGUOUS = {("gofast", 736, "altitude"): {"25000", "25010"}}


def _have_frames(case: str) -> bool:
    return all(sym.frame_path(case, i).exists() for i in FRAMES_8)


# --------------------------------------------------------------------------- (a) synthetic digits

def _render_frame(rng: np.random.Generator, digits: str, xs: list[int], y: int) -> np.ndarray:
    """Dark moving-scene background, white digits (Hershey simplex), blur and JPEG noise."""
    h, w = 40, 20 + 11 * len(digits) + 20
    yy, xx = np.mgrid[0:h, 0:w]
    bg = 60 + 40 * np.sin(xx / rng.uniform(5, 15) + rng.uniform(0, 6)) * np.cos(yy / rng.uniform(5, 15))
    img = np.clip(bg + rng.normal(0, 8, (h, w)), 0, 255).astype(np.uint8)
    level = int(rng.uniform(170, 240))
    for d, x in zip(digits, xs):
        cv2.putText(img, d, (x - 4, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, level, 1, cv2.LINE_AA)
    img = cv2.GaussianBlur(img, (3, 3), rng.uniform(0.3, 0.8))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.uniform(25, 60))])
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def _synthetic_cells(rng, n_frames: int):
    xs = [20 + 11 * k for k in range(6)]
    y_base = 26
    cells = [sym.Cell(float(x), y_base - 10, y_base - 1, "d") for x in xs]
    patches, windows, truth, refs = [], [], [], []
    for _ in range(n_frames):
        digits = "".join(rng.choice(list("0123456789"), size=len(xs)))
        th = sym.tophat(_render_frame(rng, digits, xs, y_base))
        ref = float(np.median([sym.ink(sym.cell_patch(th, c)) for c in cells]))
        for c, d in zip(cells, digits):
            patches.append(sym.cell_patch(th, c))
            windows.append(sym.cell_window(th, c))
            truth.append(d)
            refs.append(ref)
    return cells[0], np.array(patches, np.float32), windows, truth, refs


def test_synthetic_digits_cluster_templates_and_ncc():
    rng = np.random.default_rng(42)
    cell, P, _, truth, _ = _synthetic_cells(rng, 120)
    # Library by clustering, as for the videos; the generator's truth stands in for the
    # by-eye cluster labeling (majority label per cluster).
    lab = sym.kmeans_clusters(P, 40)
    lib = sym.Library()
    for c in range(lab.max() + 1):
        idx = np.where(lab == c)[0]
        if len(idx) < 3:
            continue
        vals, counts = np.unique(np.array(truth)[idx], return_counts=True)
        lib.add("s", str(vals[counts.argmax()]), P[idx].mean(0))
    assert set(lib.labels("s")) == set("0123456789")

    # fresh, independently rendered test set
    _, _, windows, truth2, refs2 = _synthetic_cells(np.random.default_rng(7), 60)
    reads = [sym.classify_cell(w, cell, lib, r) for w, r in zip(windows, refs2)]
    acc = np.mean([r.label == t for r, t in zip(reads, truth2)])
    assert acc == 1.0, f"synthetic accuracy {acc:.3f}"
    assert np.median([r.margin for r in reads]) > sym.LOW_CONF


def test_relative_margin_scale():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(15, 10)).astype(np.float32)
    b = (a + rng.normal(scale=0.5, size=a.shape)).astype(np.float32)
    rho = float(sym.norm_vec(a) @ sym.norm_vec(b))
    # a patch identical to a scores 1 - rho more on a than on b: relative margin 1
    assert sym.relative_margin(1.0 - rho, a, b) == pytest.approx(1.0, abs=0.05)
    assert sym.relative_margin(0.0, a, b) == 0.0


# --------------------------------------------------------------------------- (b) by-eye frames

@pytest.mark.parametrize("case", ["gimbal", "gofast"])
def test_by_eye_frames_read_correctly(case):
    if not _have_frames(case) or not (sym.template_dir(case) / "labels.json").exists():
        pytest.skip("frames or templates not present")
    layout = sym.load_layout(case)
    lib = sym.Library.load(sym.template_dir(case))
    bad = []
    for k, i in enumerate(FRAMES_8):
        reads = sym.read_frame(sym.read_tophat(case, i), layout, lib)
        for field, exp in GT[case].items():
            want = exp.split()[k]
            ok = {want} if want != "*" else AMBIGUOUS[(case, i, field)]
            if reads[field].value not in ok:
                bad.append((i, field, want, reads[field].value, reads[field].confidence))
    assert not bad, bad


@pytest.mark.parametrize("case", ["gimbal", "gofast"])
def test_output_csv_complete_and_matches_by_eye(case):
    p = sym.ROOT / "data" / "derived" / case / "symbology.csv"
    if not p.exists():
        pytest.skip("run python -m extract.symbology <case> first")
    with p.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    fields = list(sym.load_layout(case))
    n = sym.n_frames(case)
    got = {(int(r["frame"]), r["field"]): r for r in rows}
    assert len(got) == n * len(fields)
    for i in range(n):
        for f in fields:
            r = got[(i, f)]
            assert r["value"] != "" and "?" not in r["value"]
            assert r["method"] in ("template", "template+temporal", "ocr", "blank")
            assert (r["value"] == "blank") == (r["method"] == "blank")
    for k, i in enumerate(FRAMES_8):
        for field, exp in GT[case].items():
            want = exp.split()[k]
            ok = {want} if want != "*" else AMBIGUOUS[(case, i, field)]
            assert got[(i, field)]["value"] in ok, (i, field, want, got[(i, field)]["value"])


# --------------------------------------------------------------------------- (c) temporal filter

def test_temporal_filter_repairs_injected_outlier():
    vals = ["41L"] * 10 + ["40L"] * 10
    conf = [0.9] * 20
    vals[4] = "47L"                      # impossible single-frame jump inside a constant run
    out = sym.temporal_filter("azimuth", vals, conf)
    assert out.values[4] == "41L"
    assert out.method[4] == "template+temporal"
    assert out.values[10] == "40L" and out.method[10] == "template"   # the real change is kept
    assert sum(m == "template+temporal" for m in out.method) == 1


def test_temporal_filter_keeps_confident_plausible_flicker_and_repairs_low_conf():
    vals = ["25000", "25000", "25010", "25000", "25000"]
    kept = sym.temporal_filter("altitude", vals, [0.9] * 5)
    assert kept.values == vals                       # real display dither: kept
    low = sym.temporal_filter("altitude", vals, [0.9, 0.9, 0.05, 0.9, 0.9])
    assert low.values[2] == "25000" and low.method[2] == "template+temporal"


def test_temporal_filter_transition_glitch_and_blank_runs():
    # interlaced mix of old and new digits at a change (50L -> 49L read as 59L)
    out = sym.temporal_filter("azimuth", ["50L", "50L", "59L", "49L", "49L"], [0.9] * 5)
    assert out.values == ["50L", "50L", "49L", "49L", "49L"]
    assert out.method[2] == "template+temporal"
    # a value flashing inside a blank stretch, and a one-frame dropout inside values
    r = sym.temporal_filter("range", ["blank", "blank", "4.3", "blank", "blank"], [0.5] * 5)
    assert r.values == ["blank"] * 5
    r2 = sym.temporal_filter("range", ["4.3", "4.3", "blank", "4.3"], [0.9] * 4)
    assert r2.values == ["4.3"] * 4 and r2.method[2] == "template+temporal"
    # clock: one-second steps are normal; a 10 s jump for one frame is not
    c = sym.temporal_filter("clock", ["4229A", "4239A", "4229A", "4230A"], [0.9] * 4)
    assert c.values[1] == "4229A"


def test_numeric_parsing():
    assert sym.numeric("azimuth", "54L") == -54 and sym.numeric("azimuth", "7R") == 7
    assert sym.numeric("clock", "5319A") == 53 * 60 + 19
    assert sym.numeric("clock", "5245") == 52 * 60 + 45
    assert sym.numeric("range", "blank") is None
