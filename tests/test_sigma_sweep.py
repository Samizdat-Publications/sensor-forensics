"""CP-04 second check: the rotation sigma sweep brackets each case's own sigma (same rule for every case),
locates where the leader changes, the FLIR1 results carry it, and the case-level sigma override reaches every
hypothesis the same way."""

import json
import math
from pathlib import Path

import pytest

from solve import range_curves as RC
from solve import score as S
from solve.case_data import derived_dir, load_case

ROOT = Path(__file__).resolve().parents[1]


def test_grid_brackets_the_case_sigma_by_one_rule():
    for main in (0.675, 11.86):
        g = S.sweep_sigmas(main, heldout_rms=(3.6, 8.4))
        assert min(g) < main < max(g)
        for f in S.SIGMA_SWEEP_FACTORS:
            assert any(abs(x - f * main) < 0.01 for x in g)
        for x in S.SIGMA_SWEEP_DEG:
            if abs(x - main) >= 0.01:
                assert any(abs(y - x) < 0.01 for y in g)
        assert any(abs(x - 8.4) < 0.01 for x in g) and any(abs(x - 3.6) < 0.01 for x in g)
        assert g == sorted(g) and all(abs(x - main) >= 0.01 for x in g)


def test_crossover_bisection_finds_a_known_change():
    # Two straight lines in sigma that cross at 7.3: A leads below, B above.
    tot = {"A": lambda s: 10.0 - s, "B": lambda s: 2.7}
    out = S.leader_crossovers(lambda h, s: tot[h](s), ["A", "B"], 1.0, 20.0, [1.0, 5.0, 10.0, 20.0])
    assert len(out) == 1
    c = out[0]
    assert c["leader_below"] == "A" and c["leader_above"] == "B"
    assert abs(c["sigma_deg"] - 7.3) < 0.02
    assert S.leader_crossovers(lambda h, s: tot["A"](s) if h == "A" else -100.0, ["A", "B"], 1.0, 20.0, [5.0]) == []


def test_crossover_ignores_the_name():
    tot = {"A": lambda s: 10.0 - s, "B": lambda s: 2.7}
    out = S.leader_crossovers(lambda h, s: tot[{"X": "B", "Y": "A"}[h]](s), ["X", "Y"], 1.0, 20.0, [5.0, 10.0])
    assert out[0]["leader_below"] == "Y" and out[0]["leader_above"] == "X"
    assert abs(out[0]["sigma_deg"] - 7.3) < 0.02


def test_flir1_results_bracket_the_sigma_and_report_crossovers():
    r = json.loads((derived_dir("flir1") / "results.json").read_text(encoding="utf-8"))
    sw = r["rotation_sigma_sweep"]
    assert min(sw["sigmas_deg"]) < sw["main_sigma_deg"] < max(sw["sigmas_deg"])
    assert set(sw["crossovers"]) == {"physics_only", "testimony_weighted"}
    for cs in sw["crossovers"].values():
        for c in cs:
            assert c["leader_below"] != c["leader_above"]
            lo, hi = c["between_grid_deg"]
            assert lo <= c["sigma_deg"] <= hi


def test_rotation_sigma_override_is_case_level():
    base = load_case("flir1")
    c = load_case("flir1", rotation_sigma_deg=13.0)
    assert c.series["rotation"].sigma == 13.0
    assert math.isclose(c.rotation_noise["sigma_from_data_deg"], base.series["rotation"].sigma)
    # Nothing else in the case changes.
    assert c.n_eff_total == base.n_eff_total and c.rotation_knots == base.rotation_knots


def test_range_curve_grid_includes_the_case_extra_points():
    g = RC.grid_for(load_case("gofast"))
    for x in (3.5, 3.85, 4.0, 4.5):
        assert x in g
    assert set(RC.GRID_NMI) <= set(g)
    assert RC.grid_for(load_case("gimbal", variant="fov035")) == sorted(RC.GRID_NMI)
