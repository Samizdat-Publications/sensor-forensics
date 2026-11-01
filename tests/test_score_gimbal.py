"""GIMBAL scoring (M3.5): the rotation criterion is one shared function for every hypothesis, it
recovers a pure pod-roll glare series and prefers a smooth physical rotation when the data are one,
and the field of view is a sensor setting shared by every hypothesis."""

import ast
import copy
import dataclasses
from pathlib import Path

import numpy as np
import pytest

from solve import likelihoods as L
from solve import models as M
from solve import score as S
from solve.case_data import case_variants, load_case
from solve.sensor_atflir import glare_angle_base_v, human_horizon_v

SOLVE = Path(__file__).resolve().parents[1] / "solve"

PARAMS = {"jet_heading_deg": 315.0, "anchor_daz_deg": 0.0, "anchor_del_deg": 0.0, "wind_err_e_kt": 0.0,
          "wind_err_n_kt": 0.0, "turn_rate_z": 0.0, "jet_pitch_deg": 3.6, "range_ref_nmi": 20.0,
          "airspeed_kt": 40.0, "heading_deg": 240.0, "vz_fpm": 0.0, "altitude_ref_ft": 19000.0}


@pytest.fixture(scope="module")
def case():
    return load_case("gimbal")


def _params_for(case, h):
    names = {s.name for s in S.param_specs(case, h)}
    p = {k: v for k, v in PARAMS.items() if k in names}
    for n in names - set(p):
        p[n] = 0.0  # spline knots: a path through the anchor
    return p


def _hyp(model):
    return next(h for h in S.load_hypotheses() if h.model == model)


def test_rotation_likelihood_is_the_shared_function_for_every_hypothesis(case, monkeypatch):
    """Every hypothesis's rotation row comes from one call to likelihoods.rotation_loglik, and the
    kind (glare or physical) is the model registry's, never the hypothesis's name."""
    calls = []
    real = L.rotation_loglik

    def spy(obs, base, kind, *a, **kw):
        calls.append(kind)
        return real(obs, base, kind, *a, **kw)

    monkeypatch.setattr(L, "rotation_loglik", spy)
    for h in S.load_hypotheses():
        calls.clear()
        df = S.score(case, h, _params_for(case, h))
        assert calls == ["glare" if M.MODELS[h.model].glare else "physical"], h.model
        assert "rotation" in set(df["criterion"])
    # No other module computes the rotation likelihood or fits its free terms.
    for f in sorted(SOLVE.rglob("*.py")):
        if f.name in ("score.py", "likelihoods.py"):
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("rotation_loglik", "rotation_fit"):
                pytest.fail(f"{f.name}:{node.lineno} uses {node.attr} outside solve/score.py")


def _with_rotation(case, obs):
    c = copy.copy(case)
    c.series = dict(case.series)
    c.series["rotation"] = dataclasses.replace(case.series["rotation"], obs=np.asarray(obs, float))
    return c


def _rotation_net(case, h, params):
    """Rotation log-likelihood minus the penalty for its own free terms (what the total sees)."""
    pred = S.predict(case, h, S._full_params(S.param_specs(case, h), params))
    ll, dof, det = S.rotation_terms(case, pred)
    s = case.series["rotation"]
    return L.scaled_sum(ll, s.n_eff) - L.bic_penalty(dof, case.n_eff_total), det


def test_pure_pod_roll_glare_series_is_recovered_by_the_glare_model(case):
    glare, phys = _hyp("glare_target"), _hyp("slow_mover")
    p = _params_for(case, glare)
    pred = S.predict(case, glare, S._full_params(S.param_specs(case, glare), p))
    s = case.series["rotation"]
    pitch = S._jet_pitch(case, p)
    truth = glare_angle_base_v(pred.el, pred.az, pitch, case.bank)[s.frames] + 57.6
    rng = np.random.default_rng(3)
    syn = _with_rotation(case, truth + rng.normal(scale=s.sigma, size=len(s.frames)))
    g_net, g_det = _rotation_net(syn, glare, p)
    p_net, _ = _rotation_net(syn, phys, _params_for(syn, phys))
    assert g_net > p_net + 10.0
    assert g_det["coef"][0] == pytest.approx(57.6, abs=0.3)            # Sitrec's glare start angle, recovered
    assert np.sqrt(np.mean(g_det["resid"] ** 2)) == pytest.approx(s.sigma, rel=0.1)


def test_smooth_physical_rotation_is_preferred_when_the_data_are_one(case):
    glare, phys = _hyp("glare_target"), _hyp("slow_mover")
    p = _params_for(case, phys)
    pred = S.predict(case, phys, S._full_params(S.param_specs(case, phys), p))
    s = case.series["rotation"]
    t = case.t[s.frames]
    own = 60.0 * np.sin(2 * np.pi * (t - t[0]) / 40.0) + 20.0 * (t - t[0]) / t[-1]   # slow, smooth turning
    truth = human_horizon_v(S._jet_pitch(case, p), case.bank, pred.az, pred.el)[s.frames] + own
    rng = np.random.default_rng(4)
    syn = _with_rotation(case, truth + rng.normal(scale=s.sigma, size=len(s.frames)))
    p_net, p_det = _rotation_net(syn, phys, p)
    g_net, _ = _rotation_net(syn, glare, _params_for(syn, glare))
    assert p_net > g_net + 10.0
    assert p_det["n_model_terms"] <= 16       # the penalty keeps the spline small for a smooth series


def test_field_of_view_is_a_sensor_setting_shared_by_every_hypothesis():
    names = case_variants("gimbal")
    assert names == ["fov035", "fov070"]
    a, b = (load_case("gimbal", variant=v) for v in names)
    assert a.cfg["sensor"]["fov_deg"] == 0.35 and b.cfg["sensor"]["fov_deg"] == 0.7
    assert not np.allclose(a.turn_rate, b.turn_rate)       # the cloud inversion depends on the image scale
    for h in S.load_hypotheses():
        sa = [(x.name, x.prior, x.lo, x.hi) for x in S.param_specs(a, h)]
        sb = [(x.name, x.prior, x.lo, x.hi) for x in S.param_specs(b, h)]
        assert sa == sb
        assert not any("fov" in x[0] for x in sa)
    for crit in ("rotation", "size_trend", "brightness_trend"):
        assert a.series[crit].sigma == b.series[crit].sigma


def test_size_criterion_carries_no_weight_when_resolution_is_not_established(case):
    """D-016: GIMBAL's point-spread width is not measured, so size is reported with weight 0 for all."""
    for h in S.load_hypotheses():
        df = S.score(case, h, _params_for(case, h))
        row = df[df["criterion"] == "size_trend"].iloc[0]
        assert row["weight"] == 0.0 and row["weighted"] == 0.0


def test_background_motion_enters_once_through_the_turn_rate_band(case):
    h = _hyp("wind_drifter")
    p = _params_for(case, h)
    base = S.score(case, h, p)
    p2 = dict(p, turn_rate_z=2.0)
    df = S.score(case, h, p2)
    bg = df[df["criterion"] == "background_motion"].iloc[0]
    assert bg["loglik"] == pytest.approx(-2.0)                   # -z^2 / 2, the band's Gaussian
    assert df[df["criterion"] == "prior"].iloc[0]["loglik"] == base[base["criterion"] == "prior"].iloc[0]["loglik"]
