"""Tests for the FLIR1 symbology reading (M1, FLIR1): extract/symbology.py with the FLIR1 layout
and templates, plus extract/flir1_read.py (2007-copy cross-check)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from extract import symbology as sym

ROOT = Path(__file__).resolve().parents[1]
CASE = "flir1_navy"
DERIVED = ROOT / "data" / "derived" / CASE
FRAMES_8 = [0, 327, 653, 980, 1307, 1634, 1960, 2287]   # the M0 strip frames

# Hand-read by eye from 7x bicubic crops of each field in the official copy (and the M0 strip
# artifacts/cp01/flir1_fields.png), 10/31/2026. Notes: f653 mach last digit and f1307 airspeed
# last digit are the hardest (4 vs 5, 8 vs 3); the reading given is the one that also fits the
# neighboring frames. The clock values match a 30 frame/s clock started at 41:35 within the frame.
GT = {
    "azimuth":   "4R 3R 3R 1R 0L 3L 6L 8L",
    "elevation": "6 6 6 5 5 5 5 5",
    "zoom":      "1.0 1.0 2.0 2.0 1.0 1.0 1.0 2.0",
    "altitude":  "19990 19990 19990 19990 20000 20000 19990 20000",
    "airspeed":  "251 252 249 248 248 245 249 253",
    "mach":      "0.55 0.55 0.54 0.54 0.54 0.54 0.54 0.55",
    "clock":     "4135 4146 4157 4207 4218 4229 4240 4251",
    "range":     "blank blank blank 99.9 99.9 99.9 99.9 99.9",
    "sensor":    "IR IR TV TV IR IR IR IR",
    "fov":       "NAR NAR NAR NAR NAR NAR NAR NAR",
    "polarity":  "WHT WHT WHT WHT WHT WHT WHT WHT",
}


def _final():
    p = DERIVED / "symbology_final.csv"
    if not p.exists():
        pytest.skip("run python -m extract.flir1_read and python -m extract.merge flir1_navy first")
    with p.open(encoding="utf-8") as fh:
        return {(int(r["frame"]), r["field"]): r for r in csv.DictReader(fh)}


def test_default_reader_params_unchanged():
    """GIMBAL/GOFAST geometry must stay exactly as before the FLIR1 generalization."""
    c = sym.Cell(100.0, 10, 22, "d")
    assert c.hw == (15, 10) and c.rp.upsample == 1 and c.rp.shift == 1
    assert sym.case_params("gimbal") == sym.DEFAULT_PARAMS
    assert sym.case_params("gofast") == sym.DEFAULT_PARAMS


def test_flir1_layout_alias_and_params():
    assert sym.layout_path(CASE).name == "flir1.yaml"
    rp = sym.case_params(CASE)
    assert rp.upsample == 4
    lay = sym.load_layout(CASE)
    assert {"azimuth", "elevation", "zoom", "altitude", "airspeed", "mach", "clock", "range",
            "sensor", "fov", "polarity"} <= set(lay)
    # every cell window lies inside the upsampled frame
    H, W = 264 * rp.upsample, 352 * rp.upsample
    for spec in lay.values():
        for c in spec.cells:
            h, w = c.hw
            x0 = int(round(rp.upsample * c.x - w / 2)) - rp.shift
            y0 = rp.upsample * c.y0 - rp.pad - rp.shift
            assert 0 <= x0 and x0 + w + 2 * rp.shift <= W and 0 <= y0 and y0 + h + 2 * rp.shift <= H


@pytest.mark.parametrize("field", list(GT))
def test_strip_frames_match_hand_reading(field):
    d = _final()
    truth = GT[field].split()
    got = [d[(f, field)]["value"] for f in FRAMES_8]
    assert got == truth, f"{field}: read {got}, hand {truth}"


def test_range_line_appears_at_973():
    """The '99.9 RNG' line: absent before frame 973, present (and constant) from then on."""
    d = _final()
    before = [d[(f, "range")]["value"] for f in range(0, 973)]
    after = [d[(f, "range")]["value"] for f in range(973, 2288)]
    assert before.count("blank") / len(before) > 0.99
    assert after.count("99.9") / len(after) > 0.98


def test_copy_alignment_monotone():
    p = DERIVED / "copy_alignment.csv"
    if not p.exists():
        pytest.skip("no copy alignment yet")
    with p.open(encoding="utf-8") as fh:
        j = [int(r["f4_frame"]) for r in csv.DictReader(fh)]
    assert all(b >= a for a, b in zip(j, j[1:]))
    assert all(-8 <= jj - i <= 4 for i, jj in enumerate(j))
