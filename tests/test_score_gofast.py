"""Synthetic recovery for GOFAST: observations generated from H-BAL and from H-SLOW (known parameters,
the real display quantization and the measured noise), then scored through the full scorer. The
generating hypothesis must win or tie (physics-only total, within 1 log unit).

The wind uncertainty is set to an ERA5-like 5 kt for this test. With the 20 kt placeholder wind a
slow flier's air speed is partly absorbed by the wind-error nuisance, which is the honest reason the
M3.4 confusion matrix must be run once ERA5 is in.
"""

import copy
import dataclasses

import numpy as np
import pytest

from solve import frames as F
from solve import score as S
from solve.case_data import load_case, load_environment


@pytest.fixture(scope="module")
def case5():
    base = load_case("gofast")
    env = load_environment(base.cfg, float(np.nanmedian(base.jet_alt)))
    env = dataclasses.replace(env, wind_sigma_kt=5.0, flags=["synthetic test: wind sigma 5 kt"])
    return load_case("gofast", env=env)


def _hyp(model):
    return next(h for h in S.load_hypotheses() if h.model == model)


def _synthetic(case, hyp, params, seed):
    """A copy of the case whose observations are the model's predictions, quantized and noised."""
    rng = np.random.default_rng(seed)
    p = S._full_params(S.param_specs(case, hyp), params)
    pred = S.predict(case, hyp, p)
    assert pred.valid
    c = copy.copy(case)
    c.__dict__.pop("_jet_model", None)
    c.az_read = np.round(pred.az)
    c.el_read = np.round(pred.el)
    ro = {}
    for k, r in case.readouts.items():
        if k == "azimuth":
            obs = c.az_read[r.frames]
        elif k == "elevation":
            obs = c.el_read[r.frames]
        elif k == "range":
            obs = np.round(pred.range_m[r.frames] / F.NMI, 1)
        else:
            obs = np.round(pred.closure_mps[r.frames] / F.KT, -1)
        ro[k] = dataclasses.replace(r, obs=obs)
    se = {}
    for k, s in case.series.items():
        src = {"size_trend": pred.size_log, "brightness_trend": pred.brightness_log,
               "background_motion": pred.background_px}[k]
        se[k] = dataclasses.replace(s, obs=src[s.frames] + rng.normal(scale=s.sigma, size=len(s.frames)))
    c.readouts, c.series = ro, se
    return c


def _totals(case):
    out = {}
    for model in ("wind_drifter", "slow_mover"):
        r = S.fit(case, _hyp(model), testimony_weight=0.0, n_random=200, n_starts=4)
        assert r["valid"]
        out[model] = r
    return out


def test_balloon_data_recovers_balloon(case5):
    truth = {"jet_heading_deg": 280.0, "anchor_daz_deg": 0.0, "anchor_del_deg": 0.0, "range_ref_nmi": 3.8,
             "vz_fpm": 100.0, "wind_err_e_kt": 2.0, "wind_err_n_kt": -1.0}
    syn = _synthetic(case5, _hyp("wind_drifter"), truth, seed=11)
    r = _totals(syn)
    bal, slow = r["wind_drifter"]["total_physics_only"], r["slow_mover"]["total_physics_only"]
    assert bal >= slow - 1.0
    assert r["wind_drifter"]["params"]["range_ref_nmi"] == pytest.approx(3.8, abs=0.1)


def test_slow_flier_data_recovers_slow_flier(case5):
    truth = {"jet_heading_deg": 280.0, "anchor_daz_deg": 0.0, "anchor_del_deg": 0.0, "range_ref_nmi": 3.8,
             "airspeed_kt": 45.0, "heading_deg": 200.0, "vz_fpm": 0.0, "wind_err_e_kt": 0.0, "wind_err_n_kt": 0.0}
    syn = _synthetic(case5, _hyp("slow_mover"), truth, seed=12)
    r = _totals(syn)
    bal, slow = r["wind_drifter"]["total_physics_only"], r["slow_mover"]["total_physics_only"]
    assert slow >= bal - 1.0
    assert r["slow_mover"]["params"]["airspeed_kt"] == pytest.approx(45.0, abs=12.0)
