"""REVIEW-M3: the four review items are wired the same way for every hypothesis.

- Rule B: the brightness audit's decision sets the criterion's weight on the case (not per hypothesis),
  and weight-0 criteria leave the BIC n.
- Rule R: every hypothesis except the one the design defines by range shares the 0.5 to 60 nmi support;
  physical limits act through constraints applied by one scorer function.
- Rule T: the scored GIMBAL turn rate is the ERA5 recomputation.
- Rule P: D-016 uses the measured point-spread width.
- M3.4: synthetic data keep the real display quantization.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from solve import score as S
from solve.case_data import load_case

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gimbal035():
    return load_case("gimbal", variant="fov035")


@pytest.fixture(scope="module")
def gimbal070():
    return load_case("gimbal", variant="fov070")


@pytest.fixture(scope="module")
def gofast():
    return load_case("gofast")


def test_brightness_audit_decides_the_weight_for_the_case(gimbal035, gofast):
    ga = json.loads((ROOT / "data/derived/gimbal/brightness_audit.json").read_text(encoding="utf-8"))
    fa = json.loads((ROOT / "data/derived/gofast/brightness_audit.json").read_text(encoding="utf-8"))
    assert ga["range_informative"] is False and "B1 saturation" in ga["fails"]
    assert ga["B1"]["saturated_fraction"] > 0.5
    assert gimbal035.weight_overrides.get("brightness_trend") == 0.0
    assert fa["range_informative"] is True
    assert "brightness_trend" not in gofast.weight_overrides


def test_weight_zero_criteria_leave_the_bic_n(gimbal035):
    c = copy.copy(gimbal035)
    full = dict(c.weight_overrides)
    c.weight_overrides = {}
    n_all = c.n_eff_total
    c.weight_overrides = full
    dropped = sum(gimbal035.series[k].n_eff for k, w in full.items() if w == 0.0)
    assert c.n_eff_total == pytest.approx(n_all - dropped)


def test_equal_range_support_except_the_range_defined_hypothesis():
    supports = {}
    for h in S.load_hypotheses():
        r = h.parameters.get("range_ref_nmi")
        assert r is not None, f"{h.id} has no range parameter"
        assert r["prior"] == "loguniform"
        supports[h.id] = tuple(r["bounds"])
    common = [b for b in supports.values() if b == (0.5, 60.0)]
    assert len(common) == len(supports) - 1   # one hypothesis is defined by its range in the binding design


def test_constraints_act_through_one_function(gofast):
    h = next(x for x in S.load_hypotheses() if x.constraints and x.constraints[0]["min"] > 0)
    specs = S.param_specs(gofast, h)
    p = {s.name: (s.mean if s.prior == "normal" else s.from_unit(0.5)) for s in specs}
    lo = dict(p, range_ref_nmi=1.0)    # high above the sea: inside an aircraft's altitude band on GOFAST's sight line
    hi = dict(p, range_ref_nmi=6.0)    # far down the sight line: low altitude, outside it
    a = S.constraint_log_prior(h, S.predict(gofast, h, lo))
    b = S.constraint_log_prior(h, S.predict(gofast, h, hi))
    assert a > -1e-3 and b < -100.0
    h2 = copy.deepcopy(h)
    h2.id, h2.label = "anon", "anon"
    assert S.constraint_log_prior(h2, S.predict(gofast, h2, hi)) == b


def test_gimbal_scores_the_era5_turn_rate(gimbal035, gimbal070):
    for c, fov in ((gimbal035, "035"), (gimbal070, "070")):
        assert c.cfg["jet"]["turn_rate"]["file"].endswith(f"turn_rate_era5_fov{fov}.csv")
    s = json.loads((ROOT / "data/derived/gimbal/turn_rate_era5_summary.json").read_text(encoding="utf-8"))
    for v in s.values():
        assert 90.0 < v["era5_nominal"]["jet_wind"][1] < 110.0
        assert v["nominal_outside_placeholder_band_fraction_core"] < 0.05


def test_d016_uses_the_measured_point_spread_width(gimbal035, gimbal070, gofast):
    assert gimbal035.weight_overrides.get("size_trend") == 0.0
    assert gofast.weight_overrides.get("size_trend") == 0.0
    # At 0.7 deg D-016 finds the blob resolved; the weight then comes from D-017 (saturation), not D-016.
    assert not any(f.startswith("D-016") for f in gimbal070.flags)
    from extract.psf import lo_metric
    assert lo_metric(2.0) < lo_metric(4.0) < lo_metric(8.0)


def test_d017_saturated_blob_size_carries_weight_0(gimbal035, gimbal070, gofast):
    """D-017: a resolved blob that is saturated (Rule B1's flag and limit, on the size criterion's own
    frames) gives the size criterion weight 0 for the case; unresolved cases are left to D-016."""
    from solve.brightness_audit import SAT_LIMIT, saturated_flags
    frac = float(saturated_flags("gimbal", gimbal070.series["size_trend"].frames).mean())
    assert frac > SAT_LIMIT
    assert gimbal070.weight_overrides.get("size_trend") == 0.0
    assert any(f.startswith("D-017: apparent-size criterion reported with weight 0") for f in gimbal070.flags)
    for c in (gimbal035, gofast):
        assert not any(f.startswith("D-017") for f in c.flags)
    # Weight-0 criteria leave the BIC n: only line of sight and rotation remain from the data series.
    c = gimbal070
    kept = c.readouts["azimuth"].n_eff + c.readouts["elevation"].n_eff + c.series["rotation"].n_eff
    assert abs(c.n_eff_total - kept) < 1e-9
    for h in S.load_hypotheses():
        specs = S.param_specs(gimbal070, h)
        p = {x.name: (x.mean if x.prior == "normal" else x.from_unit(0.5)) for x in specs}
        row = S.score(gimbal070, h, p).set_index("criterion").loc["size_trend"]
        assert row["weight"] == 0.0 and row["weighted"] == 0.0


def test_synthetic_data_keep_the_display_quantization(gofast):
    from solve import recovery as R
    h = next(x for x in S.load_hypotheses() if x.model == "wind_drifter")
    specs = S.param_specs(gofast, h)
    p = {s.name: (s.mean if s.prior == "normal" else s.from_unit(0.5)) for s in specs}
    p.update(range_ref_nmi=3.8, jet_heading_deg=280.0)
    syn = R.synthetic_case(gofast, h, p, np.random.default_rng(0))
    for key in ("azimuth", "elevation"):
        r = syn.readouts[key]
        assert np.array_equal(r.frames, gofast.readouts[key].frames)
        assert np.allclose(r.obs, np.round(r.obs))
    assert np.allclose(syn.readouts["range"].obs * 10, np.round(syn.readouts["range"].obs * 10))
    assert np.allclose(syn.readouts["closure"].obs % 10, 0)
    assert syn.series["background_motion"].sigma == gofast.series["background_motion"].sigma
