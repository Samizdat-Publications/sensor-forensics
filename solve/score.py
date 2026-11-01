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
from .case_data import CaseData, load_case, scoring_config
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


def _hyp_from_dict(d: dict, path: str = "") -> Hypothesis:
    return Hypothesis(id=str(d["id"]), label=str(d["label"]), description=str(d.get("description", "")).strip(),
                      model=str(d["model"]), applies_to=[str(a).upper() for a in d.get("applies_to", [])],
                      parameters=dict(d.get("parameters", {})), parameter_groups=list(d.get("parameter_groups", [])),
                      model_options=dict(d.get("model_options") or {}), checks=list(d.get("checks", [])),
                      sources=dict(d.get("sources", {})), path=path)


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
    return ParamSpec(name, prior, lo, hi, mean, sd, bool(d.get("periodic", False)), str(d.get("source", "")))


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
        jm = JetModel(case.t, case.tas, case.bank, case.jet_alt)
        case.__dict__["_jet_model"] = jm
    return jm


def predict(case: CaseData, hyp: Hypothesis, params: dict) -> Prediction:
    jet_wind = case.env.wind_enu(float(np.nanmedian(case.jet_alt)))
    jet = _jet_model(case).state(params.get("jet_heading_deg", 0.0), jet_wind)
    return M.get(hyp.model)(case, jet, params, hyp.model_options)


def _segment_norm(y: np.ndarray, seg: np.ndarray) -> np.ndarray:
    out = np.array(y, float)
    for s in np.unique(seg):
        m = seg == s
        out[m] = y[m] - np.nanmean(y[m])
    return out


def criterion_logliks(case: CaseData, pred: Prediction, criteria: list | None = None) -> dict:
    """{criterion: (scaled loglik, n, n_eff)} for the physics criteria."""
    sc = scoring_config()["noise"]
    out: dict = {}
    crit = case.criteria if criteria is None else criteria
    for c in crit:
        if c == "line_of_sight":
            for key, arr in (("azimuth", pred.az), ("elevation", pred.el)):
                r = case.readouts[key]
                ll = L.interval_loglik(r.obs, arr[r.frames], r.step, sc["angle_sigma_deg"])
                out[f"line_of_sight_{key[:2]}"] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff)
        elif c == "range":
            r = case.readouts["range"]
            ll = L.interval_loglik(r.obs, pred.range_m[r.frames] / F.NMI, r.step, sc["range_sigma_nmi"])
            out[c] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff)
        elif c == "closure":
            r = case.readouts["closure"]
            sig = sc["closure_step_kt"] / math.sqrt(12.0)
            ll = L.gaussian_loglik(r.obs - pred.closure_mps[r.frames] / F.KT, sig)
            out[c] = (L.scaled_sum(ll, r.n_eff), len(r.frames), r.n_eff)
        elif c == "background_motion":
            s = case.series[c]
            p = np.nan_to_num(pred.background_px[s.frames], nan=0.0)
            sig = np.sqrt(s.sigma ** 2 + (sc["background_model_frac"] * p) ** 2)
            ll = L.gaussian_loglik(s.obs - p, sig)
            out[c] = (L.scaled_sum(ll, s.n_eff), len(s.frames), s.n_eff)
        elif c in ("size_trend", "brightness_trend"):
            s = case.series[c]
            src = pred.size_log if c == "size_trend" else pred.brightness_log
            p = src[s.frames]
            ok = np.isfinite(p)
            resid = _segment_norm(s.obs[ok], s.segment[ok]) - _segment_norm(p[ok], s.segment[ok])
            ll = L.gaussian_loglik(resid, s.sigma)
            out[c] = (L.scaled_sum(ll, s.n_eff), int(ok.sum()), s.n_eff)
        elif c == "rotation":
            raise NotImplementedError("rotation criterion: built with the GIMBAL run (M3.5); GOFAST does not score it")
    return out


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


def _evaluate(case: CaseData, hyp: Hypothesis, params: dict, specs: list[ParamSpec], criteria=None,
              with_testimony: bool = True) -> dict:
    pred = predict(case, hyp, params)
    if not pred.valid:
        return {"valid": False, "reason": pred.reason}
    ll = criterion_logliks(case, pred, criteria)
    lp = sum(s.log_prior(params[s.name]) for s in specs)
    if with_testimony:
        lt, trows, tstatus = _testimony(case, pred)
    else:
        lt, trows, tstatus = 0.0, [], "not evaluated"
    return {"valid": True, "pred": pred, "ll": ll, "log_prior": lp, "testimony": lt, "testimony_rows": trows,
            "testimony_status": tstatus}


def _weights() -> dict:
    return dict(scoring_config()["weights"])


def _complexity(case: CaseData, specs: list[ParamSpec]) -> tuple[int, float, float]:
    k = sum(1 for s in specs if s.counted)
    n = case.n_eff_total
    return k, n, L.bic_penalty(k, n)


def _rows(case: CaseData, ev: dict, specs: list[ParamSpec], w_t: float) -> pd.DataFrame:
    w = _weights()
    rows = []
    for name, (ll, n, ne) in ev["ll"].items():
        key = "line_of_sight" if name.startswith("line_of_sight") else name
        rows.append({"criterion": name, "loglik": ll, "n": n, "n_eff": ne, "weight": float(w.get(key, 1.0)),
                     "kind": "physics"})
    rows.append({"criterion": "prior", "loglik": ev["log_prior"], "n": np.nan, "n_eff": np.nan, "weight": 1.0,
                 "kind": "prior"})
    k, n, pen = _complexity(case, specs)
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
    w_t = _weights()["testimony"] if testimony_weight is None else float(testimony_weight)
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
    w = _weights()
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
        for name, (ll, _, _) in ev["ll"].items():
            key = "line_of_sight" if name.startswith("line_of_sight") else name
            phys += float(w.get(key, 1.0)) * ll
        return phys + ev["log_prior"] + w_t * ev["testimony"]

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


def run_case(case_name: str, hypotheses: list | None = None, write: bool = True, with_range_curve: bool = True) -> dict:
    """Fit every hypothesis on a case (both totals), rank, and write the outputs."""
    case = load_case(case_name)
    hyps = load_hypotheses() if hypotheses is None else [_resolve_hypothesis(h) for h in hypotheses]
    label = str(case.cfg.get("label", case_name)).upper()
    w_t = _weights()["testimony"]
    results = []
    score_rows = []
    for h in hyps:
        res_w = fit(case, h, testimony_weight=w_t)
        testimony_active = res_w.get("valid") and len(res_w.get("testimony_rows", [])) > 0
        res_p = fit(case, h, testimony_weight=0.0) if testimony_active else res_w
        entry = {"hypothesis": h.id, "label": h.label, "model": h.model, "in_design_set": label in h.applies_to,
                 "valid": bool(res_w.get("valid"))}
        if res_w.get("valid"):
            for tag, res in (("testimony_weighted", res_w), ("physics_only", res_p)):
                df = res["scores"].copy()
                df.insert(0, "fit", tag)
                df.insert(0, "hypothesis", h.id)
                score_rows.append(df)
            pred = res_w["prediction"]
            entry.update({
                "params_testimony_weighted_fit": res_w["params"],
                "params_physics_only_fit": res_p["params"],
                "total_testimony_weighted": res_w["total_testimony_weighted"],
                "total_physics_only": res_p["total_physics_only"],
                "k": res_w["k"], "n_eff_total": res_w["n_eff_total"],
                "criteria": {r.criterion: r.loglik for r in res_w["scores"].itertuples()},
                "derived": pred.scalars,
                "checks": _checks(h, pred.scalars),
                "params_at_bound": res_w["at_bound"],
                "testimony_rows": res_w["testimony_rows"],
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
        "window_frames": [int(case.window[0]), int(case.window[-1])],
        "reference_frame": case.ref_frame,
        "flags": case.flags,
        "environment": {"source": case.env.source, "wind_sigma_kt": case.env.wind_sigma_kt, "dT_jet_K": case.env.dT_jet},
        "criteria_n_eff": {**{f"line_of_sight_{k[:2]}": case.readouts[k].n_eff for k in ("azimuth", "elevation")},
                           **{k: case.readouts[k].n_eff for k in ("range", "closure") if k in case.readouts},
                           **{k: v.n_eff for k, v in case.series.items()}},
        "n_eff_total": case.n_eff_total,
        "data_sigmas": {k: v.sigma for k, v in case.series.items()},
        "weights": _weights(),
        "hypotheses": [e for e, _ in results],
        "closure_check": closure_check(case, best[1]),
    }
    if with_range_curve:
        out["range_curve_angles_only"] = range_curve(case)
    if write:
        d = ROOT / "data" / "derived" / case_name
        d.mkdir(parents=True, exist_ok=True)
        if score_rows:
            pd.concat(score_rows, ignore_index=True).to_csv(d / "scores.csv", index=False, float_format="%.6g")
        (d / "results.json").write_text(json.dumps(_jsonable(out), indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    case = argv[1] if len(argv) > 1 else "gofast"
    out = run_case(case)
    for e in sorted(out["hypotheses"], key=lambda e: -(e.get("total_testimony_weighted") or -1e18)):
        if e["valid"]:
            print(f"{e['hypothesis']:8s} weighted {e['total_testimony_weighted']:10.2f}  physics {e['total_physics_only']:10.2f}  k={e['k']}")
        else:
            print(f"{e['hypothesis']:8s} invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
