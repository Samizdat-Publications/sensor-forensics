"""Tests for solve/testimony.py (work item M3.3c)."""

from __future__ import annotations

import copy
import inspect
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.integrate import quad
from scipy.stats import norm

from solve import testimony as T

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------- likelihood shape

def test_interval_flat_inside_and_symmetric():
    lo, hi, s = 6.0, 8.0, 0.05
    inside = [T.interval_logpdf(x, lo, hi, s) for x in (6.3, 7.0, 7.7)]
    assert max(inside) - min(inside) < 1e-9
    assert inside[0] == pytest.approx(-math.log(hi - lo), abs=1e-9)
    # symmetric about the middle, and falls off outside
    for d in (0.1, 0.5, 2.0):
        assert T.interval_logpdf(7 - 1 - d, lo, hi, s) == pytest.approx(T.interval_logpdf(7 + 1 + d, lo, hi, s))
    assert T.interval_logpdf(8.5, lo, hi, s) < T.interval_logpdf(8.1, lo, hi, s) < inside[0]


def test_interval_is_a_density():
    for lo, hi, s in [(6, 8, 2), (0, 10, 1.5), (100, 100, 20), (25, 30, 7.5)]:
        val, _ = quad(lambda x: math.exp(T.interval_logpdf(x, lo, hi, s)), lo - 12 * s, hi + 12 * s, limit=200)
        assert val == pytest.approx(1.0, abs=1e-6)


def test_point_interval_is_gaussian_and_tails_are_stable():
    assert T.interval_logpdf(130, 100, 100, 20) == pytest.approx(norm.logpdf(130, 100, 20))
    # far outside an interval: finite and close to the Gaussian edge from the nearer end
    far = T.interval_logpdf(30.0, 6.0, 8.0, 2.0)
    assert math.isfinite(far)
    z = (30 - 8) / 2
    assert far == pytest.approx(norm.logcdf(-z) - math.log(2.0), rel=1e-6)
    below = T.interval_logpdf(-40.0, 6.0, 8.0, 2.0)
    assert below == pytest.approx(norm.logcdf(-(46 / 2)) - math.log(2.0), rel=1e-6)
    assert T.interval_logpdf(math.inf, 0, 1, 1) == -math.inf


def test_categorical_and_bool_terms():
    eps = T.load_mapping()["categorical_error_rate"]
    base = {"range_nmi": 7.0}
    hit = {r["claim_id"]: r for r in T.testimony_loglik("gimbal", {**base, "stops_and_reverses": True})}
    miss = {r["claim_id"]: r for r in T.testimony_loglik("gimbal", {**base, "stops_and_reverses": False})}
    half = {r["claim_id"]: r for r in T.testimony_loglik("gimbal", {**base, "stops_and_reverses": 0.5})}
    assert hit["G-T11"]["loglik"] == pytest.approx(math.log(1 - eps))
    assert miss["G-T11"]["loglik"] == pytest.approx(math.log(eps))
    assert half["G-T11"]["loglik"] == pytest.approx(math.log(0.5))
    rows = {r["claim_id"]: r for r in T.testimony_loglik("gimbal", {"motion_vs_wind": "with"})}
    assert rows["G-T21"]["loglik"] == pytest.approx(math.log(eps))


def test_arrays_are_reduced_per_term():
    track = np.linspace(14.0, 10.0, 50)           # range over the clip, ends at 10 nmi
    rows = T.testimony_loglik("flir1", {"range_nmi": track})
    (r,) = [x for x in rows if x["claim_id"] == "T-T60"]
    assert r["predicted_value"] == pytest.approx(10.0)  # reduce: last
    rows = T.testimony_loglik("gimbal", {"range_nmi": track})
    assert rows and all(x["predicted_value"] == pytest.approx(12.0) for x in rows)  # reduce: median


def test_mixture_term_uses_both_readings():
    rows = T.testimony_loglik("gimbal", {"ground_speed_kt": 100.0, "air_speed_kt": 220.0})
    (r,) = [x for x in rows if x["claim_id"] == "G-T28"]
    sg = max(20, T.MEMORY_SIGMA_FLOOR * 110)  # D-015 floor on recalled numbers
    a = T.interval_logpdf(100, 90, 110, sg)
    b = T.interval_logpdf(220, 90, 110, sg)
    assert r["loglik"] == pytest.approx(math.log(0.5 * math.exp(a) + 0.5 * math.exp(b)))
    # a mixture term is left out unless every reading it allows is predicted
    rows = T.testimony_loglik("gimbal", {"ground_speed_kt": 100.0})
    assert "G-T28" not in {x["claim_id"] for x in rows}


# ----------------------------------------------------------------------------- weighting

def test_firsthand_and_relayed_weights():
    rows = T.testimony_loglik("gimbal", {"range_nmi": 7.0, "reversal_radius_ft": 300.0})
    by = {r["claim_id"]: r for r in rows}
    assert by["G-T13"]["firsthand"] is False and by["G-T13"]["weight"] == 0.5
    assert by["G-T25"]["firsthand"] is True and by["G-T25"]["weight"] == 1.0
    for r in rows:
        assert r["weighted_loglik"] == pytest.approx(r["weight"] * r["loglik"])
    assert T.total(rows) == pytest.approx(sum(r["weight"] * r["loglik"] for r in rows))
    # the weight follows the claim file's firsthand flag for every row
    claims = {c["id"]: c for c in T.load_claims("flir1")}
    pred = {q: 1.0 for q in T.required_quantities("flir1")}
    for r in T.testimony_loglik("flir1", pred):
        assert r["firsthand"] is claims[r["claim_id"]]["firsthand"]
        assert r["weight"] == (1.0 if r["firsthand"] else 0.5)


def test_conflicting_claims_each_contribute():
    rows = T.testimony_loglik("flir1", {"object_altitude_ft": 24000.0})
    ids = [r["claim_id"] for r in rows]
    # Day's 28,000 ft (T-T44) and the controller's 20,000 ft via Fravor (T-T01) both enter
    assert "T-T44" in ids and "T-T01" in ids
    by = {r["claim_id"]: r for r in rows}
    assert by["T-T44"]["interval"]["lo"] == 28000 and by["T-T01"]["interval"]["lo"] == 20000


# ----------------------------------------------------------------------------- names cannot matter

HYP_ID = re.compile(r"\bH-[A-Z]{2,}\b")


def test_module_has_no_hypothesis_names():
    src = (ROOT / "solve" / "testimony.py").read_text(encoding="utf-8")
    assert not HYP_ID.search(src)
    design = (ROOT / "docs" / "design" / "scoring.md").read_text(encoding="utf-8")
    ids = set(HYP_ID.findall(design))
    assert ids, "the design table lists hypothesis ids"
    for hid in ids:
        assert hid not in src
    # no explanation is named either ("hypothesis" appears only as the name of a use category)
    for word in ("balloon", "glare", "bird", "drone", "parallax", "artifact", "distant"):
        assert word not in src.lower(), word


def test_signature_takes_quantities_only():
    params = list(inspect.signature(T.testimony_loglik).parameters)
    assert params == ["case", "predicted", "missing"]


def test_labels_are_rejected_and_order_does_not_matter():
    pred = {"range_nmi": 7.0, "object_altitude_ft": 23000.0, "stops_and_reverses": True,
            "motion_vs_wind": "against", "range_trend": "decreasing", "ground_speed_kt": 20.0,
            "air_speed_kt": 120.0, "reversal_radius_ft": 400.0}
    with pytest.raises(T.TestimonyError):
        T.testimony_loglik("gimbal", {**pred, "hypothesis": "any label"})
    with pytest.raises(T.TestimonyError):
        T.testimony_loglik("gimbal", {**pred, "name": "x"})
    a = T.testimony_loglik("gimbal", pred)
    b = T.testimony_loglik("gimbal", dict(reversed(list(pred.items()))))
    assert a == b
    # two "models" that predict the same numbers get the same rows, whatever they are called
    models = {"first label": dict(pred), "second label": dict(pred)}
    out = {k: T.testimony_loglik("gimbal", v) for k, v in models.items()}
    assert out["first label"] == out["second label"]


def test_missing_raise_guards_equal_treatment():
    with pytest.raises(T.TestimonyError):
        T.testimony_loglik("gimbal", {"range_nmi": 7.0}, missing="raise")
    full = {q: (True if q == "stops_and_reverses" else
                "against" if q == "motion_vs_wind" else
                "decreasing" if q == "range_trend" else 100.0) for q in T.required_quantities("gimbal")}
    rows = T.testimony_loglik("gimbal", full, missing="raise")
    assert len(rows) == sum(len(e.get("terms", [])) for e in
                            T.load_mapping()["cases"]["gimbal"]["claims"].values())


# ----------------------------------------------------------------------------- YAML validation

def test_real_files_validate_and_every_claim_is_mapped():
    m = T.load_mapping()
    for case in T.CASES:
        claims = T.load_claims(case)
        entries = m["cases"][case]["claims"]
        assert set(entries) == {c["id"] for c in claims}
    counts = {case: sum(e["scorable"] for e in m["cases"][case]["claims"].values()) for case in T.CASES}
    assert counts == {"gimbal": 8, "gofast": 2, "flir1": 14}


@pytest.fixture()
def claims():
    return copy.deepcopy(T.load_claims("gofast"))


@pytest.mark.parametrize("mutate", [
    lambda c: c[0].pop("witness"),
    lambda c: c[0].update(id="G-T01"),
    lambda c: c[0].update(firsthand="yes"),
    lambda c: c[0].update(applies_to=["ROSWELL"]),
    lambda c: c[0].update(quote=" ".join(["word"] * 15)),
    lambda c: c[0].update(extra_field=1),
    lambda c: c[1].update(id=c[0]["id"]),
    lambda c: c[0].update(conflicts_with=["F-T02"]),           # not symmetric
    lambda c: c[0]["source"].pop("url"),
])
def test_claim_validation_rejects(claims, mutate):
    mutate(claims)
    with pytest.raises(T.TestimonyError):
        T.validate_claims(claims, "gofast")


def test_claim_validation_accepts_symmetric_conflict(claims):
    claims[0]["conflicts_with"] = ["F-T02"]
    claims[1]["conflicts_with"] = ["F-T01"]
    T.validate_claims(claims, "gofast")


def _all_claims():
    return {k: T.load_claims(k) for k in T.CASES}


@pytest.mark.parametrize("mutate", [
    lambda m: m["cases"]["gofast"]["claims"].pop("F-T02"),
    lambda m: m["cases"]["gofast"]["claims"]["F-T01"].update(firsthand=True),
    lambda m: m["cases"]["gofast"]["claims"]["F-T01"]["terms"][0].update(quantity="vibes"),
    lambda m: m["cases"]["gofast"]["claims"]["F-T01"]["terms"][0].update(lo=5000, hi=1000),
    lambda m: m["cases"]["gofast"]["claims"]["F-T01"]["terms"][0].update(sigma=0),
    lambda m: m["cases"]["gofast"]["claims"]["F-T01"].pop("terms"),
    lambda m: m["cases"]["gofast"]["claims"]["F-T02"].update(scorable=True),
    lambda m: m["cases"]["gofast"]["claims"]["F-T02"].pop("kind"),
    lambda m: m["cases"]["gimbal"]["claims"]["G-T21"]["terms"][0].update(value="sideways"),
])
def test_mapping_validation_rejects(mutate):
    m = copy.deepcopy(T.load_mapping())
    mutate(m)
    with pytest.raises(T.TestimonyError):
        T.validate_mapping(m, _all_claims())


# ----------------------------------------------------------------------------- witness consistency fixture

def _fixture(tmp_path: Path):
    d = tmp_path / "toy"
    d.mkdir()
    rows = []
    for f in range(10):
        rows += [(f, "altitude", "25000"), (f, "airspeed", str(240 + f // 5)),
                 (f, "polarity", "BLK" if f < 7 else "WHT"), (f, "range", "blank" if f < 2 else "3.5")]
    pd.DataFrame(rows, columns=["frame", "field", "value"]).to_csv(d / "symbology_final.csv", index=False)
    (d / "frames_meta.json").write_text(json.dumps({"n_frames": 300, "fps_nominal": 30.0}), encoding="utf-8")
    pd.DataFrame({"obj_found": [1] * 10, "polarity": ["BLK"] * 7 + ["WHT"] * 3,
                  "obj_sign": [1] * 7 + [-1] * 3}).to_csv(d / "image_track.csv", index=False)

    base = copy.deepcopy(T.load_claims("gofast")[0])
    claims = []
    for i in range(1, 7):
        c = copy.deepcopy(base)
        c["id"] = f"F-T0{i}"
        c["firsthand"] = i % 2 == 0
        claims.append(c)
    m = copy.deepcopy(T.load_mapping())
    m["cases"] = {"gofast": {"derived_dir": "toy", "claims": {
        "F-T01": {"firsthand": False, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "jet_altitude_ft", "lo": 10000, "hi": 10000, "tol": 2500}]},
        "F-T02": {"firsthand": True, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "jet_speed_kt", "lo": 242, "hi": 242, "tol": 1}]},
        "F-T03": {"firsthand": False, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "polarity", "value": "BLK"}, {"quantity": "object_contrast", "value": "colder"}]},
        "F-T04": {"firsthand": True, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "display_range_nmi", "lo": 3.4, "hi": 3.5, "tol": 0.05}]},
        "F-T05": {"firsthand": False, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "clip_duration_s", "lo": 90, "hi": 90, "tol": 15},
                              {"quantity": "clip_duration_s", "lo": 10, "hi": 10, "tol": 5}]},
        "F-T06": {"firsthand": True, "scorable": False, "use": ["witness_consistency"], "kind": "image_content", "why": "t",
                  "witness": [{"quantity": "closure_kt", "lo": 170, "hi": 170, "tol": 5}]},
    }}}
    return tmp_path, m, claims


def test_witness_consistency_on_fixture(tmp_path):
    root, m, claims = _fixture(tmp_path)
    df = T.witness_consistency("gofast", derived_root=root, mapping=m, claims=claims)
    rows = list(df.itertuples())
    alt, spd, pol, con, rng, dur90, dur10, clo = rows
    assert alt.status == "disagree" and alt.difference == pytest.approx(-15000)
    assert spd.status == "agree" and spd.lab == "240 to 241" and spd.difference == pytest.approx(1.0)
    assert pol.status == "partial" and pol.difference == pytest.approx(0.3)
    assert con.status == "agree"            # BLK and brighter, WHT and darker: colder in every frame
    assert rng.status == "agree" and rng.lab == "3.5"   # blanks ignored
    assert dur90.status == "disagree" and dur90.difference == pytest.approx(80.0)
    assert dur10.status == "agree" and dur10.difference == pytest.approx(0.0)
    assert clo.status == "no_lab_reading"   # no closure field in the fixture
    assert len(rows) == 8


def test_witness_consistency_real_cases_run():
    for case in T.CASES:
        df = T.witness_consistency(case)
        assert set(df["status"]) <= {"agree", "disagree", "partial", "no_lab_reading"}
    gofast = T.witness_consistency("gofast").set_index(["claim_id", "quantity"])
    assert gofast.loc[("F-T05", "jet_altitude_ft"), "status"] == "disagree"
    assert gofast.loc[("F-T04", "display_range_nmi"), "status"] == "agree"


def test_memory_floor_widens_tight_claims():
    """D-015: a recalled number is never treated as tighter than 25 percent of its value."""
    rows = T.testimony_loglik("gimbal", {"range_nmi": 30.0})
    for r in rows:
        iv = r["interval"]
        if iv["scale"] == "linear":
            assert iv["sigma"] >= T.MEMORY_SIGMA_FLOOR * max(abs(iv["lo"]), abs(iv["hi"])) - 1e-12
            assert iv["sigma"] >= iv["sigma_claimed"]
