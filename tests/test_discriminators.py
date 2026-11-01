"""M3.6 discriminators: the separation calculator and the band finder on synthetic models with
known predictions, so the required precision can be checked by hand."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from solve import discriminators as D
from solve.discriminators import Band

ROOT = Path(__file__).resolve().parents[1]
Z10 = math.sqrt(2 * math.log(10))


def test_point_predictions_give_the_textbook_precision():
    a, b = Band(0.0, 0.0, 0.0), Band(10.0, 10.0, 10.0)
    sep = D.separation(a, b)
    assert sep["sigma_both"] == pytest.approx(10.0 / Z10)
    assert sep["sigma_central"] == pytest.approx(10.0 / Z10)
    s = sep["sigma_both"]
    # A measurement at A's prediction with that precision gives exactly a ratio of 10, and the reverse.
    assert math.exp(D.profile_log_lr(0.0, a, b, s)) == pytest.approx(10.0)
    assert math.exp(D.profile_log_lr(10.0, a, b, s)) == pytest.approx(0.1)
    # Coarser than that is not enough; finer is more than enough.
    assert math.exp(D.profile_log_lr(0.0, a, b, 1.1 * s)) < 10.0
    assert math.exp(D.profile_log_lr(0.0, a, b, 0.9 * s)) > 10.0


def test_bands_use_the_gap_between_their_edges():
    a, b = Band(0.0, -2.0, 3.0), Band(10.0, 7.0, 12.0)
    sep = D.separation(a, b)
    assert sep["gap"] == pytest.approx(4.0)
    assert sep["sigma_both"] == pytest.approx(4.0 / Z10)
    # Worst case: the measurement lands on A's edge nearest B, and B sits on its nearest edge.
    assert math.exp(D.profile_log_lr(3.0, a, b, sep["sigma_both"])) == pytest.approx(10.0)
    assert D.best_sigma(sep) == (pytest.approx(4.0 / Z10), "both")


def test_nested_bands_separate_in_one_direction_only():
    wide, narrow = Band(5.0, 0.0, 60.0), Band(0.5, 0.0, 2.0)   # a slow flier's air speed contains a balloon's
    sep = D.separation(wide, narrow)
    assert sep["sigma_both"] is None
    assert sep["sigma_rules_out_b"] == pytest.approx(3.0 / Z10)   # wide true at 5: narrow's edge 2 is 3 away
    assert sep["sigma_rules_out_a"] is None                         # narrow true: always inside wide's band
    assert D.best_sigma(sep) == (pytest.approx(3.0 / Z10), "a_true")
    same = D.separation(Band(1.0, 0.0, 2.0), Band(1.0, 0.0, 2.0))
    assert D.best_sigma(same) == (None, "none")


def _quadratic_model(center, sd, scale):
    """Toy fitted model: total = -0.5 ((x - center) / sd)^2 - 0.5 (y / 0.1)^2, quantity Q = scale * x."""
    def objective(z):
        x, y = float(z[0]), float(z[1])
        return -0.5 * ((x - center) / sd) ** 2 - 0.5 * (y / 0.1) ** 2, {"Q": scale * x, "Y": y}, {}
    return objective


def test_band_finder_recovers_a_known_band():
    sd, center, scale = 0.05, 0.4, 100.0
    out = D.profile_bands(_quadratic_model(center, sd, scale), np.array([0.5, 0.2]), [(0.0, 1.0), (-1.0, 1.0)],
                          [("Q", 1.0)], delta=D.BAND_DELTA, scan=(0, list(np.linspace(0, 1, 21))))
    b = out["bands"]["Q"]
    half = scale * sd * math.sqrt(2 * D.BAND_DELTA)        # 1.96 sd
    assert b.best == pytest.approx(scale * center, abs=0.05)
    assert b.lo == pytest.approx(scale * center - half, rel=0.02)
    assert b.hi == pytest.approx(scale * center + half, rel=0.02)


def test_two_synthetic_models_give_the_right_required_precision():
    """Model A predicts Q = 40 +/- 1.96 x 2, model B Q = 60 +/- 1.96 x 3 (band half-widths):
    the gap is 20 - 3.92 - 5.88 = 10.2, so the precision needed is 10.2 / sqrt(2 ln 10)."""
    bands = {}
    for hid, c, sd in (("A", 0.4, 0.02), ("B", 0.6, 0.03)):
        out = D.profile_bands(_quadratic_model(c, sd, 100.0), np.array([0.5, 0.0]), [(0.0, 1.0), (-1.0, 1.0)],
                              [("Q", 1.0)])
        bands[hid] = {"Q": vars(out["bands"]["Q"])}
    cat = {"Q": {"typical_sigma": 1.0}}
    res = D.evaluate_pairs([{"a": "A", "b": "B", "why": []}], bands, cat, {})
    top = res[0]["top"]
    gap = 20.0 - 1.96 * 2.0 - 1.96 * 3.0
    assert top["kind"] == "both"
    assert top["gap"] == pytest.approx(gap, rel=0.03)
    assert top["required_sigma"] == pytest.approx(gap / Z10, rel=0.03)
    assert top["feasibility"] == pytest.approx(gap / Z10, rel=0.03)
    assert res[0]["realistic"]


def test_candidates_are_ranked_by_feasibility():
    bands = {"A": {"x": vars(Band(0, 0, 0)), "y": vars(Band(0, 0, 0))},
             "B": {"x": vars(Band(1, 1, 1)), "y": vars(Band(100, 100, 100))}}
    cat = {"x": {"typical_sigma": 0.01}, "y": {"typical_sigma": 100.0}}
    top = D.evaluate_pairs([{"a": "A", "b": "B", "why": []}], bands, cat, {})[0]["top"]
    assert top["quantity"] == "x"       # 1 / 2.15 over 0.01 beats 100 / 2.15 over 100


@pytest.mark.parametrize("case", ["gimbal", "gofast"])
def test_written_discriminators_cover_every_pair(case):
    """The committed output lists, for every pair, a top candidate and bands that contain the best fit."""
    d = json.loads((ROOT / "data" / "derived" / case / "discriminators.json").read_text(encoding="utf-8"))
    assert d["variants"]
    for vv in d["variants"].values():
        assert vv["pairs"]
        ids = {h["hypothesis"] for h in vv["hypotheses"]}
        for h in vv["hypotheses"]:
            # The band search starts at the reported best fit, so it can only match or improve it.
            assert h["best_total_physics_only"] >= h["reported_total_physics_only"] - 1e-6
            for b in h["bands"].values():
                assert b["lo"] - 1e-9 <= b["best"] <= b["hi"] + 1e-9
        for p in vv["pairs"]:
            assert p["a"] in ids and p["b"] in ids
            assert p["top"] is not None
