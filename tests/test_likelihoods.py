"""Unit tests for each M3 criterion likelihood on synthetic inputs (solve/likelihoods.py, solve/score.py)."""

from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import norm

from solve import likelihoods as L
from solve import score as S
from solve.case_data import Readout, Series
from solve.models.base import Prediction
from solve import frames as F


# ------------------------------------------------------------------ primitives

def test_interval_uniform_limit_inside_and_outside():
    obs = np.array([10.0, 10.0, 10.0])
    pred = np.array([10.0, 10.4, 10.7])
    ll = L.interval_loglik(obs, pred, step=1.0, sigma=1e-4)
    assert ll[0] == pytest.approx(0.0, abs=1e-9)
    assert ll[1] == pytest.approx(0.0, abs=1e-9)
    assert ll[2] < -1000  # outside the interval with almost no smoothing


def test_interval_matches_normal_cdf_difference():
    obs, pred, step, s = 3.4, 3.47, 0.1, 0.05
    ref = np.log(norm.cdf((obs + 0.05 - pred) / s) - norm.cdf((obs - 0.05 - pred) / s))
    assert L.interval_loglik(obs, pred, step, s) == pytest.approx(ref, rel=1e-9)


def test_interval_far_tails_finite_ordered_and_symmetric():
    far = L.interval_loglik(np.zeros(4), np.array([3.0, 6.0, -3.0, -6.0]), step=1.0, sigma=0.1)
    assert np.all(np.isfinite(far))
    assert far[1] < far[0] < 0
    assert far[0] == pytest.approx(far[2], rel=1e-9)
    assert far[1] == pytest.approx(far[3], rel=1e-9)


def test_gaussian_matches_scipy():
    r = np.array([-2.0, 0.0, 1.5])
    assert np.allclose(L.gaussian_loglik(r, 0.7), norm.logpdf(r, scale=0.7))


def test_n_eff_white_and_ar1():
    rng = np.random.default_rng(1)
    white = rng.normal(size=4000)
    assert L.n_eff_autocorr(white) > 0.8 * 4000
    rho = 0.8
    x = np.zeros(20000)
    e = rng.normal(size=20000)
    for i in range(1, len(x)):
        x[i] = rho * x[i - 1] + e[i]
    expected = len(x) * (1 - rho) / (1 + rho)
    assert L.n_eff_autocorr(x) == pytest.approx(expected, rel=0.3)


def test_scaled_sum_and_bic():
    assert L.scaled_sum(np.full(100, -1.0), 25.0) == pytest.approx(-25.0)
    assert L.bic_penalty(4, np.e ** 2) == pytest.approx(4.0)


# ------------------------------------------------------------------ criteria through the scorer

def _fake_case(n=300):
    t = np.arange(n) / 30.0
    fr = np.arange(0, n)
    upd = fr[fr % 6 == 5]
    rng_true = np.linspace(4.4, 3.3, n) * F.NMI
    az_true = np.linspace(-43.0, -58.0, n)
    el_true = np.linspace(-26.0, -36.0, n)
    vc_true = np.linspace(210.0, 150.0, n)
    size_log = -np.log(rng_true)
    seg = (fr >= 150).astype(int)
    noise = np.random.default_rng(3).normal(scale=0.02, size=n)
    readouts = {
        "azimuth": Readout("azimuth", upd, np.round(az_true[upd]), 1.0, 10.0),
        "elevation": Readout("elevation", upd, np.round(el_true[upd]), 1.0, 10.0),
        "range": Readout("range", fr, np.round(rng_true / F.NMI, 1), 0.1, 30.0),
        "closure": Readout("closure", fr, np.round(vc_true, -1), 10.0, 30.0),
    }
    series = {
        "size_trend": Series("size_trend", fr, size_log + 3.0 * seg + noise, seg, 0.02, 100.0),
        "brightness_trend": Series("brightness_trend", fr, 2 * size_log + noise, seg, 0.02, 100.0),
        "background_motion": Series("background_motion", fr, np.linspace(12, 18, n) + noise, np.full(n, -1), 0.5, 100.0),
    }
    case = SimpleNamespace(readouts=readouts, series=series,
                           criteria=["line_of_sight", "range", "closure", "background_motion", "size_trend",
                                     "brightness_trend"])
    truth = Prediction(valid=True, az=az_true, el=el_true, range_m=rng_true, closure_mps=vc_true * F.KT,
                       size_log=size_log, brightness_log=2 * size_log, background_px=np.linspace(12, 18, n))
    return case, truth


def _shift(p: Prediction, **kw) -> Prediction:
    d = dict(p.__dict__)
    d.update(kw)
    return Prediction(**d)


@pytest.mark.parametrize("crit,bad", [
    ("line_of_sight_az", lambda p: _shift(p, az=p.az + 1.0)),
    ("line_of_sight_el", lambda p: _shift(p, el=p.el - 1.0)),
    ("range", lambda p: _shift(p, range_m=p.range_m * 1.1)),
    ("closure", lambda p: _shift(p, closure_mps=p.closure_mps + 20 * F.KT)),
    ("background_motion", lambda p: _shift(p, background_px=p.background_px * 1.5)),
    ("size_trend", lambda p: _shift(p, size_log=np.zeros_like(p.size_log))),        # flat: no 1/range growth
    ("brightness_trend", lambda p: _shift(p, brightness_log=-p.brightness_log)),    # wrong-way trend
])
def test_each_criterion_prefers_the_truth(crit, bad):
    case, truth = _fake_case()
    good_ll = S.criterion_logliks(case, truth)[crit][0]
    bad_ll = S.criterion_logliks(case, bad(truth))[crit][0]
    assert good_ll > bad_ll + 5


def test_trends_are_relative_only():
    """Size and brightness use the trend within each polarity segment: a constant offset changes nothing."""
    case, truth = _fake_case()
    a = S.criterion_logliks(case, truth)
    b = S.criterion_logliks(case, _shift(truth, size_log=truth.size_log + 7.0, brightness_log=truth.brightness_log - 2.0))
    assert a["size_trend"][0] == pytest.approx(b["size_trend"][0])
    assert a["brightness_trend"][0] == pytest.approx(b["brightness_trend"][0])


def test_autocorrelation_scaling_applies():
    case, truth = _fake_case()
    ll1 = S.criterion_logliks(case, _shift(truth, closure_mps=truth.closure_mps + 5 * F.KT))["closure"][0]
    case.readouts["closure"].n_eff = 60.0
    ll2 = S.criterion_logliks(case, _shift(truth, closure_mps=truth.closure_mps + 5 * F.KT))["closure"][0]
    assert ll2 == pytest.approx(2 * ll1)
