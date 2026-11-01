"""FLIR1 scoring (M3): the on-screen field of view, sensor and zoom are case data shared by every
hypothesis; the 99.9 range line is never used as a range; the pre-stated M3 review rules (brightness
audit, point-spread test, D-017) decide the weights; and the outputs carry both totals."""

import copy
import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solve import likelihoods as L
from solve import score as S
from solve import testimony as T
from solve.case_data import derived_dir, fov_per_frame, load_case
from solve.sensor_atflir import glare_angle_base_v, human_horizon_v

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "derived" / "flir1_navy"
FLIR1_IDS = {"H-AC", "H-ART", "H-CLOSE", "H-WIT"}   # applies_to includes FLIR1 (design table)

PARAMS = {"jet_heading_deg": 227.0, "anchor_daz_deg": 0.0, "anchor_del_deg": 0.0, "wind_err_e_kt": 0.0,
          "wind_err_n_kt": 0.0, "jet_pitch_deg": 3.8, "range_ref_nmi": 10.0, "airspeed_kt": 300.0,
          "heading_deg": 100.0, "vz_fpm": 0.0}


@pytest.fixture(scope="module")
def case():
    return load_case("flir1")


def _params_for(case, h):
    names = {s.name for s in S.param_specs(case, h)}
    p = {k: v for k, v in PARAMS.items() if k in names}
    for n in names - set(p):
        p[n] = 0.0
    return p


def _hyp(model):
    return next(h for h in S.load_hypotheses() if h.model == model)


def _sym():
    s = pd.read_csv(D / "symbology_final.csv", dtype=str)
    s["frame"] = s["frame"].astype(int)
    return s


def test_outputs_live_next_to_the_m1_readings():
    assert derived_dir("flir1") == D
    assert derived_dir("gofast") == ROOT / "data" / "derived" / "gofast"


def test_field_of_view_per_frame_from_zoom_and_mode(case):
    fov = fov_per_frame(case.cfg, _sym(), len(case.t))
    assert fov[0] == pytest.approx(0.7)          # NAR 1.0x
    assert fov[1000] == pytest.approx(0.35)      # NAR 2.0x (TV stretch)
    assert np.all(np.isnan(fov[2169:2222]))      # MFOV or WFOV, unresolved: unknown
    assert case.ppd == pytest.approx(244.0 / 0.7)
    # Sizes are in px at the reference field: a 2.0x frame's native blob length is halved.
    cues = pd.read_csv(D / "image_track.csv")
    assert case.size_px_all[1000] == pytest.approx(cues.loc[1000, "obj_lo_major_px"] / 2.0)
    assert case.size_px_all[100] == pytest.approx(cues.loc[100, "obj_lo_major_px"])


def test_image_series_split_at_sensor_zoom_and_mode_and_skip_the_unresolved_field(case):
    sym = _sym()
    for key in ("size_trend", "brightness_trend"):
        s = case.series[key]
        assert not np.any((s.frames >= 2169) & (s.frames <= 2221))
        for g in np.unique(s.segment):
            fr = s.frames[s.segment == g]
            for fld in ("sensor", "zoom", "fov"):
                v = sym[(sym["field"] == fld) & sym["frame"].isin(fr)]["value"].unique()
                assert len(v) == 1, (key, g, fld, v)
    # Rotation: quality-gated frames, one offset per sensor (zoom does not change an angle).
    r = case.series["rotation"]
    cues = pd.read_csv(D / "image_track.csv").set_index("frame")
    sel = cues.loc[r.frames]
    assert np.all(sel["obj_hi_major_px"] / sel["obj_hi_minor_px"] >= 1.5)
    assert np.all(sel["obj_hi_area_px"] >= 6) and np.all(sel["obj_snr"] >= 8.0)
    sens = sym[sym["field"] == "sensor"].set_index("frame")["value"]
    for g in np.unique(r.segment):
        assert sens.loc[r.frames[r.segment == g]].nunique() == 1


def test_range_line_is_never_used_as_a_range(case):
    """The 99.9 RNG line (constant from f973) is a placeholder: no range readout or criterion."""
    assert "range" not in case.readouts and "closure" not in case.readouts
    assert "range" not in case.criteria and "background_motion" not in case.criteria
    assert "background_motion" not in case.series
    for h in S.load_hypotheses():
        df = S.score(case, h, _params_for(case, h))
        assert not ({"range", "closure", "background_motion"} & set(df["criterion"]))


def test_review_rules_decide_the_weights(case):
    ba = json.loads((D / "brightness_audit.json").read_text(encoding="utf-8"))
    assert ba["range_informative"] == ("brightness_trend" not in case.weight_overrides)
    assert ba["B3"]["fail"] is False          # zoom changes are segment boundaries, not inside a segment
    pj = json.loads((D / "psf.json").read_text(encoding="utf-8"))
    psf = pj["variants"]["default"]["psf_width_px_lo_metric"]
    major = float(np.nanmedian(case.size_px_all[case.window]))
    resolved = major >= 3.0 * psf
    from solve.brightness_audit import SAT_LIMIT, saturated_flags
    sat = float(saturated_flags("flir1", case.series["size_trend"].frames).mean())
    expect_zero = (not resolved) or sat > SAT_LIMIT
    assert (case.weight_overrides.get("size_trend") == 0.0) == expect_zero


def test_every_flir1_hypothesis_meets_the_same_18_testimony_terms(case):
    for h in S.load_hypotheses():
        pred = S.predict(case, h, S._full_params(S.param_specs(case, h), _params_for(case, h)))
        rows = T.testimony_loglik("flir1", S.testimony_predicted(case, pred), missing="raise")
        assert len(rows) == 18
        assert sorted(r["claim_id"] for r in rows) == sorted(
            r["claim_id"] for r in T.testimony_loglik("flir1", S.testimony_predicted(case, pred)))


def test_shared_settings_are_the_same_for_every_hypothesis(case):
    shared = None
    for h in S.load_hypotheses():
        sp = [(x.name, x.prior, x.lo, x.hi) for x in S.param_specs(case, h)][:len(case.shared_parameters)]
        shared = shared or sp
        assert sp == shared
        assert not any("fov" in x.name or "zoom" in x.name for x in S.param_specs(case, h))


def _with_rotation(case, obs):
    c = copy.copy(case)
    c.series = dict(case.series)
    c.series["rotation"] = dataclasses.replace(case.series["rotation"], obs=np.asarray(obs, float))
    return c


def _rotation_net(case, h, params):
    pred = S.predict(case, h, S._full_params(S.param_specs(case, h), params))
    ll, dof, det = S.rotation_terms(case, pred)
    s = case.series["rotation"]
    return L.scaled_sum(ll, s.n_eff) - L.bic_penalty(dof, case.n_eff_total), det


def test_rotation_criterion_separates_glare_and_physical_on_flir1_sampling(case):
    """On FLIR1's own gated frames and noise: a pure derotation series is won by the glare model, a smooth
    physical rotation by the physical model (the test the real data face, run on known inputs)."""
    glare, phys = _hyp("glare_target"), _hyp("close_object")
    s = case.series["rotation"]
    pg = _params_for(case, glare)
    pred = S.predict(case, glare, S._full_params(S.param_specs(case, glare), pg))
    truth = glare_angle_base_v(pred.el, pred.az, S._jet_pitch(case, pg), case.bank)[s.frames] + 30.0
    rng = np.random.default_rng(5)
    # The loader unwraps the measured axial angle (period 180); the synthetic series is treated the same way.
    syn = _with_rotation(case, np.unwrap(truth + rng.normal(scale=s.sigma, size=len(s.frames)), period=180.0))
    g_net, g_det = _rotation_net(syn, glare, pg)
    p_net, _ = _rotation_net(syn, phys, _params_for(syn, phys))
    assert g_det["coef"][0] == pytest.approx(30.0, abs=1.5)
    # Looking up (el +5 to +6) while the azimuth passes through zero, the derotation turns the glare through
    # about 180 deg: a step a smooth physical rotation cannot follow as well, net of its penalty.
    assert g_net > p_net + 10.0
    pp = _params_for(case, phys)
    pred2 = S.predict(case, phys, S._full_params(S.param_specs(case, phys), pp))
    t = case.t[s.frames]
    own = 40.0 * np.sin(2 * np.pi * (t - t[0]) / 30.0)
    truth2 = human_horizon_v(S._jet_pitch(case, pp), case.bank, pred2.az, pred2.el)[s.frames] + own
    syn2 = _with_rotation(case, np.unwrap(truth2 + rng.normal(scale=s.sigma, size=len(s.frames)), period=180.0))
    p_net2, _ = _rotation_net(syn2, phys, pp)
    g_net2, _ = _rotation_net(syn2, glare, _params_for(syn2, glare))
    assert p_net2 > g_net2 + 10.0


def test_results_carry_both_totals_for_every_flir1_hypothesis():
    res = json.loads((D / "results.json").read_text(encoding="utf-8"))
    assert res["label"] == "FLIR1" and res["case"] == "flir1"
    got = {h["hypothesis"]: h for h in res["hypotheses"]}
    assert FLIR1_IDS <= set(got)
    for hid in FLIR1_IDS:
        h = got[hid]
        assert h["in_design_set"] and h["valid"]
        assert np.isfinite(h["total_testimony_weighted"]) and np.isfinite(h["total_physics_only"])
        assert len(h["testimony_rows"]) == 18
        assert "rank_testimony_weighted_design_set" in h and "rank_physics_only_design_set" in h
    sc = pd.read_csv(D / "scores.csv")
    assert set(sc["fit"]) == {"testimony_weighted", "physics_only"}
    assert FLIR1_IDS <= set(sc["hypothesis"])
    assert not (set(sc["criterion"]) & {"range", "closure"})
