"""M3 scoring: the single scoring path for every hypothesis (docs/design/scoring.md, binding).

Public entry points (the only ones; tests/test_equal_treatment.py checks this):

- score(case, hypothesis, params) -> DataFrame of criterion log-likelihoods
- fit(case, hypothesis, ...)      -> maximum likelihood within the prior bounds (multi-start)
- run_case(case)                  -> fits every hypothesis, writes scores.csv, results.json
                                     and docs/results/<case>.md

Hypotheses are data (solve/hypotheses/*.yaml): a model key into solve.models plus
parameter priors with sources. This module never looks at a hypothesis's id or label
except to copy it into the outputs; ranking, fitting and scoring depend only on the
model, the priors and the data.

Totals (D-011): every result carries BOTH the testimony-weighted total (testimony weight
from solve/scoring.yaml, 1.0 by default) and the physics-only total (testimony weight 0),
each at its own best fit:

    physics_total   = sum_c w_c * LL_c + LL_prior - 0.5 k ln(n_eff_total)
    weighted_total  = physics_total + w_T * LL_testimony

with LL_c each criterion's summed log-likelihood scaled by n_eff / n (data-only n_eff),
LL_prior the log density of the normal-prior nuisance parameters relative to their peak,
and k the number of uniform / log-uniform parameters (shared nuisances included, the
same for every hypothesis on a case).

Usage: python -m solve.score gofast
       python -m solve.score gimbal [fov035,fov070]   (one run per sensor variant, reported separately)
       python -m solve.score gimbal --part fov035; ... --part fov070; python -m solve.score gimbal --merge
"""

from __future__ import annotations

import copy
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize

from . import frames as F
from . import likelihoods as L
from . import models as M
from .case_data import CaseData, case_variants, derived_dir, load_case, scoring_config
from .models.base import Prediction
from .models.geometry import JetModel

__all__ = ["score", "fit", "run_case", "load_hypotheses", "Hypothesis"]

ROOT = Path(__file__).resolve().parents[1]
HYP_DIR = Path(__file__).resolve().parent / "hypotheses"
PHYSICS = ["line_of_sight", "range", "closure", "background_motion", "size_trend", "rotation", "brightness_trend"]
INVALID_OBJECTIVE = 1e12


# ----------------------------------------------------------------------------- hypotheses as data


@dataclass
class ParamSpec:
    name: str
    prior: str               # uniform | loguniform | normal | fixed
    lo: float
    hi: float
    mean: float = 0.0
    sd: float = 1.0
    periodic: bool = False
    source: str = ""
    report_as: str = ""      # a criterion name: the log prior is reported as that criterion, not as "prior"

    @property
    def counted(self) -> bool:
        """Counts toward k in the complexity penalty."""
        return self.prior in ("uniform", "loguniform")

    def from_unit(self, z: float) -> float:
        if self.periodic:
            z = z % 1.0
        if self.prior == "loguniform":
            return float(math.exp(math.log(self.lo) + (math.log(self.hi) - math.log(self.lo)) * z))
        return float(self.lo + (self.hi - self.lo) * z)

    def to_unit(self, x: float) -> float:
        if self.prior == "loguniform":
            return (math.log(x) - math.log(self.lo)) / (math.log(self.hi) - math.log(self.lo))
        return (x - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0.0

    def log_prior(self, x: float) -> float:
        if self.prior == "normal":
            return -0.5 * ((x - self.mean) / self.sd) ** 2
        return 0.0


@dataclass
class Hypothesis:
    id: str
    label: str
    description: str
    model: str
    applies_to: list
    parameters: dict
    parameter_groups: list = field(default_factory=list)
    model_options: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    sources: dict = field(default_factory=dict)
    path: str = ""
    constraints: list = field(default_factory=list)   # physical limits on predicted quantities (uniform priors)


def _hyp_from_dict(d: dict, path: str = "") -> Hypothesis:
    return Hypothesis(id=str(d["id"]), label=str(d["label"]), description=str(d.get("description", "")).strip(),
                      model=str(d["model"]), applies_to=[str(a).upper() for a in d.get("applies_to", [])],
                      parameters=dict(d.get("parameters", {})), parameter_groups=list(d.get("parameter_groups", [])),
                      model_options=dict(d.get("model_options") or {}), checks=list(d.get("checks", [])),
                      sources=dict(d.get("sources", {})), path=path, constraints=list(d.get("constraints", [])))


def load_hypotheses(directory: Path | str | None = None) -> list[Hypothesis]:
    """All hypotheses in the directory, in file-name order."""
    p = Path(directory) if directory else HYP_DIR
    return [_hyp_from_dict(yaml.safe_load(f.read_text(encoding="utf-8")), str(f)) for f in sorted(p.glob("*.yaml"))]


def _resolve_hypothesis(h) -> Hypothesis:
    if isinstance(h, Hypothesis):
        return h
    if isinstance(h, dict):
        return _hyp_from_dict(h)
    p = Path(str(h))
    if p.suffix in (".yaml", ".yml") and p.exists():
        return _hyp_from_dict(yaml.safe_load(p.read_text(encoding="utf-8")), str(p))
    by_id = {x.id: x for x in load_hypotheses()}
    return by_id[str(h)]


def _resolve_case(c) -> CaseData:
    return c if isinstance(c, CaseData) else load_case(str(c))


def _spec(name: str, d: dict, case: CaseData) -> ParamSpec:
    prior = str(d.get("prior", "uniform"))
    sd = d.get("sd", 1.0)
    if isinstance(sd, str) and sd.startswith("environment."):
        sd = getattr(case.env, sd.split(".", 1)[1])
    sd = float(sd)
    mean = float(d.get("mean", 0.0))
    bounds = d.get("bounds")
    byc = d.get("bounds_by_case") or {}
    label = str(case.cfg.get("label", case.name)).upper()
    if label in {str(k).upper() for k in byc}:
        bounds = {str(k).upper(): v for k, v in byc.items()}[label]
    if bounds is None:
        bounds = [mean - 4 * sd, mean + 4 * sd]
    lo, hi = float(bounds[0]), float(bounds[1])
    if hi == lo:
        prior = "fixed"
    return ParamSpec(name, prior, lo, hi, mean, sd, bool(d.get("periodic", False)), str(d.get("source", "")),
                     str(d.get("report_as", "")))


def param_specs(case: CaseData, hyp: Hypothesis) -> list[ParamSpec]:
    """Shared case nuisances first, then the hypothesis's own parameters (YAML order), then groups."""
    specs = [_spec(n, d, case) for n, d in case.shared_parameters.items()]
    specs += [_spec(n, d, case) for n, d in hyp.parameters.items()]
    for g in hyp.parameter_groups:
        for j in range(int(g["count"])):
            for base in g["names"]:
                specs.append(_spec(f"{base}_{j}", g, case))
    return specs


# ----------------------------------------------------------------------------- one evaluation


def _jet_model(case: CaseData) -> JetModel:
    jm = case.__dict__.get("_jet_model")
    if jm is None:
        jm = JetModel(case.t, case.tas, case.bank, case.jet_alt, case.turn_rate, case.turn_rate_sigma)
        case.__dict__["_jet_model"] = jm
    return jm


def _jet_pitch(case: CaseData, params: dict):
    j = case.cfg["jet"]
    p = float(params.get("jet_pitch_deg", j.get("pitch_deg", 0.0)))
    if j.get("pitch_scale_with_bank", False):
        return p / np.cos(np.radians(np.abs(case.bank)))
    return p


def predict(case: CaseData, hyp: Hypothesis, params: dict) -> Prediction:
    jet_wind = case.env.wind_enu(float(np.nanmedian(case.jet_alt)))
    jet = _jet_model(case).state(params.get("jet_heading_deg", 0.0), jet_wind,
                                 turn_rate_z=params.get("turn_rate_z", 0.0), pitch_deg=_jet_pitch(case, params))
    return M.get(hyp.model)(case, jet, params, hyp.model_options)


def _segment_norm(y: np.ndarray, seg: np.ndarray) -> np.ndarray:
    out = np.array(y, float)
    for s in np.unique(seg):
        m = seg == s
        out[m] = y[m] - np.nanmean(y[m])
    return out


def criterion_logliks(case: CaseData, pred: Prediction, criteria: list | None = None) -> dict:
    """{criterion: (scaled loglik, n, n_eff, free terms)} for the physics criteria.

    "free terms" counts parameters a criterion fits internally (the rotation criterion's glare
    offset or smooth-rotation spline, and its polarity offset); they enter k like any other.
    """
    sc = scoring_config()["noise"]
    out: dict = {}
    crit = case.criteria if criteria is None else criteria
    for c in crit:
        if c == "line_of_sight":
            for key, arr in (("azimuth", pred.az), ("elevation", pred.el)):
                r = case.readouts[key]
                ll = L.interval_loglik(r.obs, arr[r.frames], r.step, sc["angle_sigma_deg"])
                out[f"line_of_sight_{key[:2]}"] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff, 0)
        elif c == "range":
            r = case.readouts["range"]
            ll = L.interval_loglik(r.obs, pred.range_m[r.frames] / F.NMI, r.step, sc["range_sigma_nmi"])
            out[c] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff, 0)
        elif c == "closure":
            r = case.readouts["closure"]
            sig = sc["closure_step_kt"] / math.sqrt(12.0)
            ll = L.gaussian_loglik(r.obs - pred.closure_mps[r.frames] / F.KT, sig)
            out[c] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff, 0)
        elif c == "background_motion":
            if c not in case.series:
                continue   # measured through the jet's turn rate: scored from its nuisance (see _evaluate)
            s = case.series[c]
            p = np.nan_to_num(pred.background_px[s.frames], nan=0.0)
            sig = np.sqrt(s.sigma ** 2 + (sc["background_model_frac"] * p) ** 2)
            ll = L.gaussian_loglik(s.obs - p, sig)
            out[c] = (L.scaled_sum(ll, s.n_eff), len(s.frames), s.n_eff, 0)
        elif c in ("size_trend", "brightness_trend"):
            s = case.series[c]
            src = pred.size_log if c == "size_trend" else pred.brightness_log
            p = src[s.frames]
            ok = np.isfinite(p)
            resid = _segment_norm(s.obs[ok], s.segment[ok]) - _segment_norm(p[ok], s.segment[ok])
            ll = L.gaussian_loglik(resid, s.sigma)
            out[c] = (L.scaled_sum(ll, s.n_eff), int(ok.sum()), s.n_eff, 0)
        elif c == "rotation":
            ll, dof, _ = rotation_terms(case, pred)
            s = case.series[c]
            out[c] = (L.scaled_sum(ll, s.n_eff), len(s.frames), s.n_eff, dof)
    return out


def rotation_terms(case: CaseData, pred: Prediction) -> tuple[np.ndarray, int, dict]:
    """The rotation criterion for any model: one call to likelihoods.rotation_loglik.

    The model only supplies its predicted orientation (without free terms) and its kind (glare
    fixed in the optics, or physical); the measured series, its noise and the spline size are
    the case's, identical for every hypothesis.
    """
    s = case.series["rotation"]
    return L.rotation_loglik(s.obs, pred.rotation_base[s.frames], pred.rotation_kind, s.segment,
                             case.t[s.frames], s.sigma, case.rotation_knots,
                             penalty_per_term=L.bic_penalty(1, case.n_eff_total), scale=s.n_eff / len(s.frames),
                             folds=case.rotation_folds)


def testimony_predicted(case: CaseData, pred: Prediction) -> dict:
    """The quantities testimony claims can test (the testimony vocabulary, the same keys for every model)."""
    return dict(pred.testimony_quantities)


def _testimony(case: CaseData, pred: Prediction) -> tuple[float, list, str]:
    """(testimony criterion value before the testimony weight, claim rows, status).

    Calls solve.testimony (never reimplemented here) with missing="raise", so every
    hypothesis is scored on exactly the same claims.
    """
    try:
        from . import testimony as T
    except ImportError:
        return 0.0, [], "solve/testimony.py not available: no claims scored"
    tcase = str(case.cfg.get("testimony_case", case.name))
    rows = T.testimony_loglik(tcase, testimony_predicted(case, pred), missing="raise")
    return T.total(rows), rows, f"solve/testimony.py: {len(rows)} claim terms scored"


def constraint_log_prior(hyp: Hypothesis, pred: Prediction) -> float:
    """Uniform prior on a predicted quantity (e.g. the object's altitude over the scored window).

    Each constraint in the hypothesis YAML names a quantity of the testimony vocabulary (the same
    keys for every model), a [min, max] support and a soft edge (sd, same units) for the optimizer.
    The smallest and largest predicted values must lie inside the support; the log density is the
    interval likelihood of each, ~0 inside and falling as a Gaussian edge outside. Applied by this
    one function to every hypothesis that lists constraints; reported in the "prior" row.
    """
    out = 0.0
    for c in hyp.constraints:
        q = np.asarray(pred.testimony_quantities[c["quantity"]], float)
        lo, hi, sd = float(c["min"]), float(c["max"]), float(c.get("edge_sd", 0.0))
        ext = np.array([np.nanmin(q), np.nanmax(q)])
        out += float(np.sum(L.interval_loglik(np.full(2, 0.5 * (lo + hi)), ext, hi - lo, max(sd, 1e-9))))
    return out


def _evaluate(case: CaseData, hyp: Hypothesis, params: dict, specs: list[ParamSpec], criteria=None,
              with_testimony: bool = True) -> dict:
    pred = predict(case, hyp, params)
    if not pred.valid:
        return {"valid": False, "reason": pred.reason}
    ll = criterion_logliks(case, pred, criteria)
    lp = sum(s.log_prior(params[s.name]) for s in specs if not s.report_as) + constraint_log_prior(hyp, pred)
    crit = case.criteria if criteria is None else criteria
    for c in sorted({s.report_as for s in specs if s.report_as}):
        if c in crit:
            ll[c] = (sum(s.log_prior(params[s.name]) for s in specs if s.report_as == c), 1, 1.0, 0)
    if with_testimony:
        lt, trows, tstatus = _testimony(case, pred)
    else:
        lt, trows, tstatus = 0.0, [], "not evaluated"
    return {"valid": True, "pred": pred, "ll": ll, "log_prior": lp, "testimony": lt, "testimony_rows": trows,
            "testimony_status": tstatus}


def _weights(case: CaseData | None = None) -> dict:
    """scoring.yaml weights, with the case's own overrides (D-016), the same for every hypothesis."""
    w = dict(scoring_config()["weights"])
    if case is not None:
        w.update(getattr(case, "weight_overrides", {}) or {})
    return w


def _complexity(case: CaseData, specs: list[ParamSpec], ll: dict | None = None) -> tuple[int, float, float]:
    k = sum(1 for s in specs if s.counted) + sum(int(v[3]) for v in (ll or {}).values())
    n = case.n_eff_total
    return k, n, L.bic_penalty(k, n)


def _rows(case: CaseData, ev: dict, specs: list[ParamSpec], w_t: float) -> pd.DataFrame:
    w = _weights(case)
    rows = []
    for name, (ll, n, ne, _) in ev["ll"].items():
        key = "line_of_sight" if name.startswith("line_of_sight") else name
        rows.append({"criterion": name, "loglik": ll, "n": n, "n_eff": ne, "weight": float(w.get(key, 1.0)),
                     "kind": "physics"})
    rows.append({"criterion": "prior", "loglik": ev["log_prior"], "n": np.nan, "n_eff": np.nan, "weight": 1.0,
                 "kind": "prior"})
    k, n, pen = _complexity(case, specs, ev["ll"])
    rows.append({"criterion": "complexity_penalty", "loglik": -pen, "n": k, "n_eff": n, "weight": 1.0,
                 "kind": "penalty"})
    rows.append({"criterion": "testimony", "loglik": ev["testimony"], "n": len(ev["testimony_rows"]),
                 "n_eff": np.nan, "weight": w_t, "kind": "testimony"})
    df = pd.DataFrame(rows)
    df["weighted"] = df["loglik"] * df["weight"]
    phys = float(df.loc[df["kind"] != "testimony", "weighted"].sum())
    df.attrs.update({"total_physics_only": phys, "total_testimony_weighted": phys + w_t * ev["testimony"],
                     "testimony_weight": w_t, "k": k, "n_eff_total": n, "testimony_status": ev["testimony_status"]})
    return df


def _full_params(specs: list[ParamSpec], params: dict) -> dict:
    out = {}
    for s in specs:
        if s.name in params:
            out[s.name] = float(params[s.name])
        elif s.prior == "fixed":
            out[s.name] = s.lo
        elif s.prior == "normal":
            out[s.name] = s.mean
        else:
            raise KeyError(f"parameter {s.name!r} missing")
    return out


def score(case, hypothesis, params: dict, testimony_weight: float | None = None) -> pd.DataFrame:
    """Criterion log-likelihoods of one hypothesis at given parameters.

    Rows: each physics criterion, 'prior', 'complexity_penalty' and 'testimony'; columns
    loglik (scaled by n_eff / n), n, n_eff, weight, weighted. df.attrs holds both totals.
    """
    case = _resolve_case(case)
    hyp = _resolve_hypothesis(hypothesis)
    specs = param_specs(case, hyp)
    p = _full_params(specs, params)
    w_t = _weights(case)["testimony"] if testimony_weight is None else float(testimony_weight)
    ev = _evaluate(case, hyp, p, specs)
    if not ev["valid"]:
        raise ValueError(f"invalid parameters: {ev['reason']}")
    return _rows(case, ev, specs, w_t)


# ----------------------------------------------------------------------------- fitting


def fit(case, hypothesis, testimony_weight: float | None = None, n_starts: int | None = None,
        n_random: int | None = None, seed: int | None = None, criteria: list | None = None,
        fixed: dict | None = None) -> dict:
    """Maximum likelihood (plus the normal-prior nuisances) within the prior bounds, multi-start.

    The objective is the weighted physics log-likelihood + log prior + w_T * testimony.
    Random points in the prior box are scored first; the best n_starts seed L-BFGS-B runs
    in unit-cube coordinates (periodic parameters wrap). `fixed` pins parameters (used for
    range curves). The seed never depends on the hypothesis.
    """
    case = _resolve_case(case)
    hyp = _resolve_hypothesis(hypothesis)
    cfg = scoring_config()
    fc = cfg["fit"]
    n_starts = int(fc["n_starts"] if n_starts is None else n_starts)
    n_random = int(fc["n_random"] if n_random is None else n_random)
    seed = int(fc["seed"] if seed is None else seed)
    w = _weights(case)
    w_t = w["testimony"] if testimony_weight is None else float(testimony_weight)
    specs = param_specs(case, hyp)
    fixed = dict(fixed or {})
    free = [s for s in specs if s.prior != "fixed" and s.name not in fixed]
    const = {s.name: (fixed[s.name] if s.name in fixed else s.lo) for s in specs if s not in free}
    use_t = w_t != 0.0

    def params_of(z):
        p = dict(const)
        for s, zi in zip(free, z):
            p[s.name] = s.from_unit(float(zi))
        return p

    def objective_parts(p):
        ev = _evaluate(case, hyp, p, specs, criteria, with_testimony=use_t)
        if not ev["valid"]:
            return None
        phys = 0.0
        for name, (ll, _, _, _) in ev["ll"].items():
            key = "line_of_sight" if name.startswith("line_of_sight") else name
            phys += float(w.get(key, 1.0)) * ll
        # Terms fitted inside a criterion (rotation) can change in number with the parameters; their
        # penalty is part of the objective so the fit and the reported total agree.
        inner = sum(int(v[3]) for v in ev["ll"].values())
        return phys + ev["log_prior"] + w_t * ev["testimony"] - L.bic_penalty(inner, case.n_eff_total)

    n_eval = [0]

    def f(z):
        n_eval[0] += 1
        v = objective_parts(params_of(z))
        return INVALID_OBJECTIVE if v is None or not np.isfinite(v) else -v

    d = len(free)
    rng = np.random.default_rng(seed)
    if d == 0:
        best_z = np.zeros(0)
    else:
        Z = rng.random((n_random, d))
        Z[0] = 0.5
        vals = np.array([f(z) for z in Z])
        order = np.argsort(vals)[:n_starts]
        bounds = [(-1.0, 2.0) if s.periodic else (0.0, 1.0) for s in free]
        best_z, best_v = Z[order[0]], vals[order[0]]
        for i in order:
            if vals[i] >= INVALID_OBJECTIVE:
                continue
            r = minimize(f, Z[i], method="L-BFGS-B", bounds=bounds,
                         options={"maxiter": int(fc["maxiter"]), "eps": 1e-6})
            if r.fun < best_v:
                best_z, best_v = r.x, r.fun
    p = params_of(best_z)
    if not np.isfinite(f(best_z)) or f(best_z) >= INVALID_OBJECTIVE:
        return {"hypothesis": hyp.id, "valid": False, "params": p, "n_eval": n_eval[0]}
    ev = _evaluate(case, hyp, p, specs, criteria, with_testimony=True)
    df = _rows(case, ev, specs, w_t)
    return {"hypothesis": hyp.id, "label": hyp.label, "valid": True, "params": p, "scores": df,
            "prediction": ev["pred"], "testimony_rows": ev["testimony_rows"],
            "total_physics_only": df.attrs["total_physics_only"],
            "total_testimony_weighted": df.attrs["total_testimony_weighted"],
            "k": df.attrs["k"], "n_eff_total": df.attrs["n_eff_total"], "n_eval": n_eval[0],
            "at_bound": [s.name for s in free if not s.periodic and min(abs(s.to_unit(p[s.name])),
                                                                        abs(1 - s.to_unit(p[s.name]))) < 1e-3],
            "testimony_status": df.attrs["testimony_status"], "specs": specs}


# ----------------------------------------------------------------------------- case-level analyses


def closure_check(case: CaseData, best: dict | None = None) -> dict:
    """What the closure readout says, independent of any hypothesis.

    For an object at rest in the air at the jet's altitude, the closing speed would be the
    jet's own airspeed projected on the line of sight, TAS cos(el) cos(az) (wind cancels).
    The readout minus that projection is the object's own velocity along the line of sight,
    relative to the air at the jet's level. Also compares the readout with the range readout's
    own rate of change.
    """
    if "closure" not in case.readouts or "range" not in case.readouts:
        return {}
    r = case.readouts["closure"]
    fr = r.frames
    az = np.radians(case.az_read[fr])
    el = np.radians(case.el_read[fr])
    proj = case.tas[fr] * np.cos(el) * np.cos(az) / F.KT
    diff = r.obs - proj
    rr = case.readouts["range"]
    slope = np.polyfit(case.t[rr.frames], rr.obs, 1)[0] * 3600.0  # nmi/h = kt
    out = {
        "frames": [int(fr[0]), int(fr[-1])],
        "closure_readout_kt_first_last": [float(r.obs[0]), float(r.obs[-1])],
        "still_air_projection_kt_first_last": [float(np.mean(proj[:30])), float(np.mean(proj[-30:]))],
        "readout_minus_projection_kt_mean": float(np.mean(diff)),
        "readout_minus_projection_kt_rms": float(np.sqrt(np.mean(diff ** 2))),
        "readout_minus_projection_kt_first_last": [float(np.mean(diff[:30])), float(np.mean(diff[-30:]))],
        "range_readout_rate_kt": float(-slope),
        "closure_readout_mean_kt": float(np.mean(r.obs)),
        "note": "Projection uses the readout az/el (whole degrees) and TAS from Mach; az from the nose, so "
                "crab angle is ignored.",
    }
    if best is not None and best.get("valid"):
        pc = best["prediction"].closure_mps[fr] / F.KT
        out["best_fit_hypothesis"] = best["hypothesis"]
        out["best_fit_closure_rms_kt"] = float(np.sqrt(np.mean((r.obs - pc) ** 2)))
    return out


def range_curve(case: CaseData, ranges_nmi=(1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 8.0, 12.0, 20.0)) -> list:
    """Angles-only range curve: at each assumed range, the constant-velocity object that best fits the
    line of sight and the ocean motion, and the speed and altitude it then needs (range and closure
    readouts NOT used, to show what the angles alone allow)."""
    probe = Hypothesis(id="range-curve probe", label="constant-velocity probe", description="", model="point_target",
                       applies_to=[], parameters={
                           "range_ref_nmi": {"prior": "uniform", "bounds": [0.05, 60.0]},
                           "airspeed_kt": {"prior": "uniform", "bounds": [0.0, 2000.0]},
                           "heading_deg": {"prior": "uniform", "bounds": [0.0, 360.0], "periodic": True},
                           "vz_fpm": {"prior": "uniform", "bounds": [-20000.0, 20000.0]}})
    crit = [c for c in case.criteria if c in ("line_of_sight", "background_motion")]
    out = []
    for r in ranges_nmi:
        res = fit(case, probe, testimony_weight=0.0, criteria=crit, fixed={"range_ref_nmi": float(r)},
                  n_starts=4, n_random=150)
        if not res["valid"]:
            out.append({"range_nmi": r, "valid": False})
            continue
        s = res["prediction"].scalars
        df = res["scores"]
        los = float(df.loc[df["criterion"].str.startswith("line_of_sight"), "loglik"].sum())
        out.append({"range_nmi": r, "valid": True, "air_speed_kt": s["air_speed_kt"],
                    "ground_speed_kt": s["ground_speed_kt"], "altitude_ft_mean": s["altitude_ft_mean"],
                    "vertical_speed_fpm": s["vertical_speed_fpm"], "line_of_sight_loglik": los})
    return out


def _checks(hyp: Hypothesis, scalars: dict) -> list:
    out = []
    for c in hyp.checks:
        v = scalars.get(c["quantity"])
        ok = None if v is None else bool(float(c["min"]) <= v <= float(c["max"]))
        out.append({"quantity": c["quantity"], "value": v, "min": c["min"], "max": c["max"], "pass": ok,
                    "source": c.get("source", "")})
    return out


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_jsonable(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def measured_rotation_steps(case: CaseData, min_change_deg: float = 6.0, half: int = 4, sep: int = 15) -> list:
    """Steps in the measured orientation, found from the data alone (no model).

    A step is a local maximum of |y(f + half) - y(f - half)| above min_change_deg on the 9-frame
    running median of the series; its size is the change from 10 frames before to 10 after.
    """
    s = case.series["rotation"]
    y = pd.Series(s.obs).rolling(9, center=True, min_periods=1).median().to_numpy()
    f = s.frames
    d = np.full(len(y), 0.0)
    d[half:-half] = y[2 * half:] - y[:-2 * half]
    cand = [i for i in range(half, len(y) - half) if abs(d[i]) >= min_change_deg
            and abs(d[i]) == np.max(np.abs(d[max(0, i - sep):i + sep + 1]))]
    out = []
    for i in cand:
        if out and f[i] - out[-1]["frame"] < sep:
            continue
        a, b = max(0, i - 10), min(len(y) - 1, i + 10)
        out.append({"frame": int(f[i]), "change_deg": float(y[b] - y[a])})
    return out


def _match_steps(measured: list, predicted: list, tol: int = 10) -> dict:
    mf = [m["frame"] for m in measured]
    hits = {m: min(predicted, key=lambda q: abs(q - m)) if predicted else None for m in mf}
    matched = {m: q for m, q in hits.items() if q is not None and abs(q - m) <= tol}
    return {"tolerance_frames": tol, "nearest_predicted": hits, "matched": matched, "n_matched": len(matched),
            "n_measured": len(mf), "n_predicted": len(predicted),
            "n_predicted_unmatched": len([q for q in predicted if all(abs(q - m) > tol for m in mf)])}


def rotation_check(case: CaseData, results: list) -> dict:
    """The rotation test in detail, for every hypothesis at its testimony-weighted best fit.

    For every model: residual RMS overall and around each measured step, and the mean residual
    just before and just after each step (a model that predicts the step leaves no jump).
    For glare models, also the step-timing test: Sitrec's derotation model with the ideal
    (geometric) pod roll has no steps, so the simplest pod-roll controller that makes steps (a
    deadband, solve.sensor_atflir.pod_roll_deadband; NOT in Sitrec) is scanned over its threshold
    and two error measures, with the glare offset refitted by the same rotation likelihood. Its
    best threshold is one extra fitted parameter; the result is reported, not added to any total.
    """
    from .sensor_atflir import pod_pitch_roll_v, pod_roll_deadband

    if "rotation" not in case.series:
        return {}
    s = case.series["rotation"]
    steps = measured_rotation_steps(case)
    n_scale = s.n_eff / len(s.frames)
    pen1 = L.bic_penalty(1, case.n_eff_total)
    out = {"sigma_deg": s.sigma, "n_eff": s.n_eff, "noise": dict(case.rotation_noise),
           "cross_validated": case.rotation_folds is not None,
           "cv_block_frames": None if case.rotation_folds is None else int(np.ceil(len(s.frames) / max(s.n_eff, 1.0))),
           "measured_steps": steps, "hypotheses": {}}
    fr = s.frames
    for entry, res in results:
        if not entry.get("valid"):
            continue
        pred = res["prediction"]
        ll, dof, det = rotation_terms(case, pred)
        resid = det["resid"]
        per_step = []
        for st in steps:
            k = int(np.searchsorted(fr, st["frame"]))
            pre = resid[max(0, k - 20):max(0, k - 5)]
            post = resid[k + 5:k + 20]
            win = resid[max(0, k - 15):k + 16]
            per_step.append({"frame": st["frame"], "resid_before_deg": float(np.mean(pre)) if len(pre) else None,
                             "resid_after_deg": float(np.mean(post)) if len(post) else None,
                             "jump_left_deg": float(np.mean(post) - np.mean(pre)) if len(pre) and len(post) else None,
                             "rms_window_deg": float(np.sqrt(np.mean(win ** 2)))})
        cvr = det.get("cv_resid")
        h = {"kind": pred.rotation_kind, "free_terms": dof, "model_terms": det["n_model_terms"],
             "fitted_terms": det.get("n_terms"), "cross_validated": bool(det.get("cross_validated")),
             "cv_resid_rms_deg": None if cvr is None else float(np.sqrt(np.mean(cvr ** 2))),
             "loglik_scaled": float(L.scaled_sum(ll, s.n_eff)), "resid_rms_deg": float(np.sqrt(np.mean(resid ** 2))),
             "resid_max_abs_deg": float(np.max(np.abs(resid))), "steps": per_step,
             "fitted_deg": det["fitted"], "offset_deg": float(det["coef"][0]) if pred.rotation_kind == "glare" else None}
        if pred.rotation_kind == "glare":
            pitch = _jet_pitch(case, res["params"])
            pitch = np.broadcast_to(np.asarray(pitch, float), pred.az.shape)
            ball_pitch, groll = pod_pitch_roll_v(pred.el, pred.az, pitch)
            base_s = pred.rotation_base[fr]
            scan = []
            for metric, grid in (("pointing", np.arange(0.1, 3.01, 0.1)), ("roll", np.arange(1.0, 30.01, 1.0))):
                for reflect in (False, True):
                    for thr in grid:
                        ra, jumps = pod_roll_deadband(groll, ball_pitch, float(thr), metric, reflect)
                        dr = ((ra - groll + 180.0) % 360.0) - 180.0
                        llb, _, detb = L.rotation_loglik(s.obs, base_s - dr[fr], "glare", s.segment, case.t[fr], s.sigma,
                                                         case.rotation_knots, folds=case.rotation_folds)
                        scan.append({"metric": metric, "reflect": reflect, "threshold": float(thr),
                                     "loglik_scaled": float(L.scaled_sum(llb, s.n_eff)),
                                     "resid_rms_deg": float(np.sqrt(np.mean(detb["resid"] ** 2))),
                                     "steps_predicted": [int(j) for j in jumps if j >= fr[0] + 30],
                                     "_fitted": detb["fitted"]})
            best = max(scan, key=lambda r: r["loglik_scaled"])
            sm = _match_steps(steps, [q for q in best["steps_predicted"]])
            # A fine threshold makes many tiny steps (near-continuous tracking), which says nothing about
            # step timing. "Coarse" settings make about as many steps as were measured over the stepping
            # stretch (from 150 frames before the first measured step): between half and twice as many.
            first = steps[0]["frame"] - 150 if steps else fr[0]
            nm = max(1, len(steps))
            coarse = [r for r in scan if 0.5 * nm <= len([q for q in r["steps_predicted"] if q >= first]) <= 2 * nm]
            best_c = max(coarse, key=lambda r: r["loglik_scaled"]) if coarse else None
            # Predicted steps only count where the pod actually rolls fast enough to step (after the
            # first measured step minus 100 frames); earlier jumps are listed too.
            h["deadband"] = {
                "best": {k: v for k, v in best.items() if not k.startswith("_")},
                "step_match": sm,
                "gain_vs_smooth_loglik": best["loglik_scaled"] - h["loglik_scaled"],
                "gain_vs_smooth_after_one_parameter_penalty": best["loglik_scaled"] - h["loglik_scaled"] - pen1,
                "by_metric": {f"{m}{'_reflect' if r else ''}": {k: v for k, v in max(
                    (x for x in scan if x["metric"] == m and x["reflect"] == r), key=lambda x: x["loglik_scaled"]).items()
                    if not k.startswith("_")} for m in ("pointing", "roll") for r in (False, True)},
                "fitted_deg": best["_fitted"],
                "coarse_window_start_frame": int(first),
                "best_coarse": None if best_c is None else {k: v for k, v in best_c.items() if not k.startswith("_")},
                "best_coarse_step_match": None if best_c is None else _match_steps(
                    steps, [q for q in best_c["steps_predicted"] if q >= first]),
                "best_coarse_gain_vs_smooth_after_one_parameter_penalty": None if best_c is None else
                    best_c["loglik_scaled"] - h["loglik_scaled"] - pen1,
                "best_coarse_fitted_deg": None if best_c is None else best_c["_fitted"],
                "note": "Not in Sitrec and not in any total: a diagnostic of whether a pod-roll controller reproduces "
                        "the step frames from the on-screen angles alone.",
            }
        out["hypotheses"][entry["hypothesis"]] = h
    out["frames"] = fr
    out["measured_deg"] = s.obs
    return out


def _fit_pair(task: tuple) -> tuple:
    """Both fits of one hypothesis (testimony-weighted, then physics-only). Loads the case itself, so it can
    run in a worker process; the same code path as a serial run."""
    case_name, variant, exclusions, h = task
    case = load_case(case_name, variant=variant or None, exclusions=exclusions)
    w_t = _weights(case)["testimony"]
    res_w = fit(case, h, testimony_weight=w_t)
    testimony_active = res_w.get("valid") and len(res_w.get("testimony_rows", [])) > 0
    res_p = fit(case, h, testimony_weight=0.0) if testimony_active else res_w
    return res_w, res_p


PROCS = 1   # worker processes for the per-hypothesis fits (CLI --procs); results do not depend on it


def _fit_all(case: CaseData, case_name: str, hyps: list) -> list:
    tasks = [(case_name, case.variant, case.exclusions_applied, h) for h in hyps]
    if PROCS > 1 and len(tasks) > 1:
        from multiprocessing import Pool
        with Pool(min(PROCS, len(tasks))) as pool:
            return pool.map(_fit_pair, tasks)
    return [_fit_pair(t) for t in tasks]


SIGMA_SWEEP_DEG = (0.88, 1.3, 2.0, 3.0)


def _replace_series(series, **kw):
    import dataclasses
    return dataclasses.replace(series, **kw)


def rotation_sigma_sweep(case: CaseData, hyps: list, results: list, sigmas=SIGMA_SWEEP_DEG) -> dict:
    """The rotation criterion and both totals rescored at other rotation sigmas (REVIEW-M3 Rule N sweep).

    At each run's own best-fit parameters (NOT refitted): only the rotation row changes, so
    total(sigma) = total - rotation(main sigma) + rotation(sigma). The same for every hypothesis.
    """
    s = case.series["rotation"]
    by_id = {h.id: h for h in hyps}
    out = {"main_sigma_deg": s.sigma, "sigmas_deg": [float(x) for x in sigmas],
           "note": "Rescored at each fit's best parameters, not refitted.", "hypotheses": {}}
    for entry, _ in results:
        if not entry.get("valid"):
            continue
        h = by_id[entry["hypothesis"]]
        row = {}
        for tag, pkey, tkey, ckey in (("testimony_weighted", "params_testimony_weighted_fit", "total_testimony_weighted", "criteria"),
                                      ("physics_only", "params_physics_only_fit", "total_physics_only", "criteria_physics_only_fit")):
            pred = predict(case, h, entry[pkey])
            base_rot = float(entry[ckey]["rotation"])
            cells = []
            for sg in sigmas:
                c2 = copy.copy(case)
                c2.series = dict(case.series)
                c2.series["rotation"] = _replace_series(s, sigma=float(sg))
                ll, _, _ = rotation_terms(c2, pred)
                r = float(L.scaled_sum(ll, s.n_eff))
                cells.append({"sigma_deg": float(sg), "rotation": r, "total": float(entry[tkey]) - base_rot + r})
            row[tag] = cells
        out["hypotheses"][entry["hypothesis"]] = row
    return out


def _run_one(case: CaseData, case_name: str, hyps: list, with_range_curve: bool) -> tuple[dict, list]:
    label = str(case.cfg.get("label", case_name)).upper()
    w_t = _weights(case)["testimony"]
    results = []
    score_rows = []
    pairs = _fit_all(case, case_name, hyps)
    for h, (res_w, res_p) in zip(hyps, pairs):
        entry = {"hypothesis": h.id, "label": h.label, "model": h.model, "in_design_set": label in h.applies_to,
                 "valid": bool(res_w.get("valid"))}
        if res_w.get("valid"):
            for tag, res in (("testimony_weighted", res_w), ("physics_only", res_p)):
                df = res["scores"].copy()
                df.insert(0, "fit", tag)
                df.insert(0, "hypothesis", h.id)
                if case.variant:
                    df.insert(0, "variant", case.variant)
                score_rows.append(df)
            pred = res_w["prediction"]
            entry.update({
                "params_testimony_weighted_fit": res_w["params"],
                "params_physics_only_fit": res_p["params"],
                "total_testimony_weighted": res_w["total_testimony_weighted"],
                "total_physics_only": res_p["total_physics_only"],
                "k": res_w["k"], "k_physics_only_fit": res_p["k"], "n_eff_total": res_w["n_eff_total"],
                "criteria": {r.criterion: r.loglik for r in res_w["scores"].itertuples()},
                "criteria_physics_only_fit": {r.criterion: r.loglik for r in res_p["scores"].itertuples()},
                "derived": pred.scalars,
                "derived_physics_only_fit": res_p["prediction"].scalars,
                "checks": _checks(h, pred.scalars),
                "params_at_bound": res_w["at_bound"],
                "params_at_bound_physics_only_fit": res_p["at_bound"],
                "testimony_rows": res_w["testimony_rows"],
                "testimony_rows_physics_only_fit": res_p["testimony_rows"],
                "testimony_status": res_w["testimony_status"],
                "n_eval": res_w["n_eval"] + (res_p["n_eval"] if res_p is not res_w else 0),
            })
        results.append((entry, res_w))
    valid = [e for e, _ in results if e["valid"]]
    for key, rk in (("total_testimony_weighted", "rank_testimony_weighted"), ("total_physics_only", "rank_physics_only")):
        order = sorted(valid, key=lambda e: -e[key])
        for i, e in enumerate(order):
            e[rk] = i + 1
        design = [e for e in order if e["in_design_set"]]
        for i, e in enumerate(design):
            e[rk + "_design_set"] = i + 1
    best = max(((e, r) for e, r in results if e["valid"]), key=lambda x: x[0]["total_testimony_weighted"], default=(None, None))
    out = {
        "case": case_name,
        "label": label,
        "variant": case.variant,
        "sensor": dict(case.cfg.get("sensor", {})),
        "display_rounding": str(case.cfg.get("display_rounding", "round")),
        "window_frames": [int(case.window[0]), int(case.window[-1])],
        "reference_frame": case.ref_frame,
        "flags": case.flags,
        "environment": {"source": case.env.source, "wind_sigma_kt": case.env.wind_sigma_kt, "dT_jet_K": case.env.dT_jet},
        "criteria_n_eff": {**{f"line_of_sight_{k[:2]}": case.readouts[k].n_eff for k in ("azimuth", "elevation")},
                           **{k: case.readouts[k].n_eff for k in ("range", "closure") if k in case.readouts},
                           **{k: v.n_eff for k, v in case.series.items()}},
        "n_eff_total": case.n_eff_total,
        "data_sigmas": {k: v.sigma for k, v in case.series.items()},
        "weights": _weights(case),
        "hypotheses": [e for e, _ in results],
        "closure_check": closure_check(case, best[1]),
    }
    out["exclusions"] = dict(case.exclusions)
    out["exclusions_applied"] = bool(case.exclusions_applied)
    if "rotation" in case.series:
        out["rotation_noise"] = dict(case.rotation_noise)
        out["rotation_check"] = rotation_check(case, results)
        out["rotation_sigma_sweep"] = rotation_sigma_sweep(case, hyps, results)
    if case.turn_rate is not None:
        out["turn_rate"] = {"heading_change_deg": float(np.trapezoid(case.turn_rate, case.t)),
                            "sigma_median_deg_s": float(np.median(case.turn_rate_sigma))}
    if with_range_curve:
        rc = case.cfg.get("range_curve_nmi")
        out["range_curve_angles_only"] = range_curve(case, tuple(rc)) if rc else range_curve(case)
    return out, score_rows


def run_case(case_name: str, hypotheses: list | None = None, write: bool = True, with_range_curve: bool = True,
             variants: list | None = None) -> dict:
    """Fit every hypothesis on a case (both totals), rank, and write the outputs.

    A case with sensor_variants (GIMBAL: the field of view) is run once per variant; every
    hypothesis sees the same variant, and results are reported per variant, never mixed.
    """
    hyps = load_hypotheses() if hypotheses is None else [_resolve_hypothesis(h) for h in hypotheses]
    names = case_variants(case_name) if variants is None else list(variants)
    d = derived_dir(case_name)
    if names == [""]:
        out, score_rows, nx_rows = _run_both(case_name, None, hyps, with_range_curve)
        if write:
            d.mkdir(parents=True, exist_ok=True)
            if score_rows:
                pd.concat(score_rows, ignore_index=True).to_csv(d / "scores.csv", index=False, float_format="%.6g")
            _write_nx_rows(d, nx_rows)
            (d / "results.json").write_text(json.dumps(_jsonable(out), indent=1) + "\n", encoding="utf-8")
        return out
    outs, rows, nxr = {}, [], []
    for v in names:
        o, r, nx = _run_both(case_name, v, hyps, with_range_curve)
        outs[v] = o
        rows += r
        nxr += nx
    out = {"case": case_name, "label": next(iter(outs.values()))["label"], "variant_names": names, "variants": outs}
    if write:
        d.mkdir(parents=True, exist_ok=True)
        if rows:
            pd.concat(rows, ignore_index=True).to_csv(d / "scores.csv", index=False, float_format="%.6g")
        _write_nx_rows(d, nxr)
        (d / "results.json").write_text(json.dumps(_jsonable(out), indent=1) + "\n", encoding="utf-8")
    return out


NX_KEYS = ("hypothesis", "label", "valid", "in_design_set", "total_testimony_weighted", "total_physics_only",
           "rank_testimony_weighted", "rank_physics_only", "rank_testimony_weighted_design_set",
           "rank_physics_only_design_set", "k", "k_physics_only_fit", "criteria", "criteria_physics_only_fit",
           "params_testimony_weighted_fit", "params_physics_only_fit", "derived", "derived_physics_only_fit",
           "params_at_bound", "params_at_bound_physics_only_fit")


def _run_both(case_name: str, variant: str | None, hyps: list, with_range_curve: bool) -> tuple[dict, list, list]:
    """REVIEW-M3 Rule X: the run with the data-quality exclusions (the default outputs) and, when any exclusion
    applies, a full refit with every criterion at its design weight, summarized in out["no_exclusions"]."""
    case = load_case(case_name, variant=variant)
    out, rows = _run_one(case, case_name, hyps, with_range_curve)
    if not case.weight_overrides:
        out["no_exclusions"] = {"identical": True, "note": "No data-quality exclusion applies on this run: the totals "
                                "without exclusions are the totals above."}
        return out, rows, []
    case_nx = load_case(case_name, variant=variant, exclusions=False)
    o2, rows2 = _run_one(case_nx, case_name, hyps, False)
    out["no_exclusions"] = {"identical": False, "flags": o2["flags"], "weights": o2["weights"],
                            "n_eff_total": o2["n_eff_total"],
                            "hypotheses": [{k: e[k] for k in NX_KEYS if k in e} for e in o2["hypotheses"]]}
    if "rotation_sigma_sweep" in o2:
        out["no_exclusions"]["rotation_sigma_sweep"] = o2["rotation_sigma_sweep"]
    for r in rows2:
        r.insert(0, "exclusions", "none")
    return out, rows, rows2


def _write_nx_rows(d: Path, rows: list) -> None:
    p = d / "scores_no_exclusions.csv"
    if rows:
        pd.concat(rows, ignore_index=True).to_csv(p, index=False, float_format="%.6g")
    elif p.exists():
        p.unlink()


def _write_variants(case_name: str, names: list) -> dict:
    """Merge per-variant part files (written by `--part`) into scores.csv and results.json."""
    d = derived_dir(case_name)
    outs = {v: json.loads((d / f"results_part_{v}.json").read_text(encoding="utf-8")) for v in names}
    rows = [pd.read_csv(d / f"scores_part_{v}.csv") for v in names]
    out = {"case": case_name, "label": outs[names[0]]["label"], "variant_names": names, "variants": outs}
    pd.concat(rows, ignore_index=True).to_csv(d / "scores.csv", index=False, float_format="%.6g")
    (d / "results.json").write_text(json.dumps(_jsonable(out), indent=1) + "\n", encoding="utf-8")
    for v in names:
        (d / f"results_part_{v}.json").unlink()
        (d / f"scores_part_{v}.csv").unlink()
    return out


def recheck_rotation(case_name: str) -> dict:
    """Recompute only the rotation diagnostic from the stored best fits (no refitting), and rewrite results.json."""
    d = derived_dir(case_name)
    out = json.loads((d / "results.json").read_text(encoding="utf-8"))
    by_id = {h.id: h for h in load_hypotheses()}
    for v, o in (out["variants"].items() if "variants" in out else [("", out)]):
        case = load_case(case_name, variant=v or None)
        res = []
        for e in o["hypotheses"]:
            if e["valid"]:
                p = e["params_testimony_weighted_fit"]
                res.append((e, {"prediction": predict(case, by_id[e["hypothesis"]], p), "params": p}))
        o["rotation_check"] = rotation_check(case, res)
    (d / "results.json").write_text(json.dumps(_jsonable(out), indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    global PROCS
    if "--procs" in argv:
        i = argv.index("--procs")
        PROCS = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    case = argv[1] if len(argv) > 1 else "gofast"
    if len(argv) > 2 and argv[2] == "--recheck-rotation":
        recheck_rotation(case)
        print("rotation diagnostic recomputed")
        return 0
    if len(argv) > 2 and argv[2] == "--merge":
        out = _write_variants(case, case_variants(case))
        print(f"merged {out['variant_names']}")
        return 0
    if len(argv) > 3 and argv[2] == "--part":
        # One sensor variant per process (run them in parallel), then `--merge`.
        v = argv[3]
        o, rows, _nx = _run_both(case, v, load_hypotheses(), True)
        d = derived_dir(case)
        d.mkdir(parents=True, exist_ok=True)
        pd.concat(rows, ignore_index=True).to_csv(d / f"scores_part_{v}.csv", index=False, float_format="%.6g")
        (d / f"results_part_{v}.json").write_text(json.dumps(_jsonable(o), indent=1) + "\n", encoding="utf-8")
        out = {"variants": {v: o}}
    else:
        variants = argv[2].split(",") if len(argv) > 2 else None
        out = run_case(case, variants=variants)
    for vname, o in (out["variants"].items() if "variants" in out else [("", out)]):
        if vname:
            print(f"--- {vname}")
        for e in sorted(o["hypotheses"], key=lambda e: -(e.get("total_testimony_weighted") or -1e18)):
            if e["valid"]:
                print(f"{e['hypothesis']:8s} weighted {e['total_testimony_weighted']:10.2f}  physics {e['total_physics_only']:10.2f}  k={e['k']}")
            else:
                print(f"{e['hypothesis']:8s} invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
