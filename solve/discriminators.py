"""M3.6 discriminators: the single measurement that would separate two hypotheses.

For each pair of top hypotheses, this module asks: which quantity, measured at which time and
to what precision, would give a likelihood ratio of at least 10 between them?

Method (the same for every hypothesis; nothing here branches on a hypothesis):

1. **Prediction bands.** Each hypothesis is taken at its physics-only best fit (results.json).
   Its band for a quantity Q is the range of Q over every parameter set whose physics-only
   total is within BAND_DELTA (1.92, half the 95 percent chi-square quantile for one
   parameter of interest) of its best total. The set is explored by (a) a profile over the
   range parameter (the dominant degeneracy when range is not on screen) and (b) for each
   quantity, Lagrangian pushes: maximize total +/- lambda * Q from the best fit, lambda growing
   until the total falls out of the band, then bisected. Bands for quantities that were not
   pushed directly (other times) come from the same point set, so they can be slightly narrow.
2. **Separation.** A measurement x with Gaussian error sigma. Each hypothesis may sit anywhere
   inside its band (a profile likelihood, as the scorer itself uses maximum likelihood), so the
   log likelihood ratio of A over B is (d_B(x)^2 - d_A(x)^2) / (2 sigma^2), with d the distance
   from x to the band. If the bands are disjoint by a gap g, any measurement with
   sigma <= g / sqrt(2 ln 10) gives a ratio of at least 10 for whichever hypothesis is true,
   even at the band edges. If the bands overlap, only one direction can work: B is ruled out
   when A is true at its best fit only if A's best value lies outside B's band.
3. **Feasibility.** The required sigma is compared with a typical precision for an instrument
   that could plausibly have measured it (data/discriminators/notes.yaml, stated assumptions).

CLI:
    python -m solve.discriminators gimbal|gofast|flir1|all [--procs N] [--variant fov070]   # writes data/derived/<case>/discriminators.json
    python -m solve.discriminators --report                          # writes docs/results/discriminators.md
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize

from . import frames as F
from . import score as S
from .case_data import derived_dir, load_case

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "data" / "discriminators" / "notes.yaml"
REPORT = ROOT / "docs" / "results" / "discriminators.md"

LR_TARGET = 10.0
BAND_DELTA = 1.92
INVALID = 1e12
SECOND_SENSOR_OFFSET_NMI = 2.0     # assumed abeam spacing of a second aircraft (notes.yaml)


# ----------------------------------------------------------------------------- separation math


@dataclass
class Band:
    best: float
    lo: float
    hi: float
    lo_at_bound: list = field(default_factory=list)   # parameters at a prior bound where the extreme was reached
    hi_at_bound: list = field(default_factory=list)


def z_for_lr(lr: float = LR_TARGET) -> float:
    """Separation in sigmas between two point predictions that gives the likelihood ratio lr."""
    return math.sqrt(2.0 * math.log(lr))


def distance_to_band(x: float, b: Band) -> float:
    return max(b.lo - x, 0.0, x - b.hi)


def profile_log_lr(x: float, a: Band, b: Band, sigma: float) -> float:
    """ln of the likelihood ratio A over B for a measurement x with Gaussian error sigma, each
    hypothesis free to sit anywhere inside its band."""
    return (distance_to_band(x, b) ** 2 - distance_to_band(x, a) ** 2) / (2.0 * sigma ** 2)


def separation(a: Band, b: Band, lr: float = LR_TARGET) -> dict:
    """Precision needed for a likelihood ratio of at least lr between A and B.

    sigma_both: works whichever hypothesis is true, anywhere in its band (None if bands overlap).
    sigma_rules_out_b: works if A is true at its best fit (None if A's best is inside B's band).
    sigma_central: both at their best fits (optimistic).
    """
    z = z_for_lr(lr)
    gap = max(b.lo - a.hi, a.lo - b.hi)
    d_a = distance_to_band(a.best, b)
    d_b = distance_to_band(b.best, a)
    central = abs(a.best - b.best)
    return {"gap": gap, "central_difference": central,
            "sigma_both": gap / z if gap > 0 else None,
            "sigma_rules_out_b": d_a / z if d_a > 0 else None,
            "sigma_rules_out_a": d_b / z if d_b > 0 else None,
            "sigma_central": central / z if central > 0 else None}


def best_sigma(sep: dict) -> tuple[float | None, str]:
    """The usable required precision and its kind: both ways, else the better one-way figure."""
    if sep["sigma_both"]:
        return sep["sigma_both"], "both"
    one = [(v, k) for k, v in (("a_true", sep["sigma_rules_out_b"]), ("b_true", sep["sigma_rules_out_a"])) if v]
    if one:
        v, k = max(one)
        return v, k
    return None, "none"


# ----------------------------------------------------------------------------- generic band finder


def profile_bands(objective, z0, bounds, pushes, delta: float = BAND_DELTA, scan=None,
                  lambdas=(0.25, 1.0, 4.0, 16.0, 64.0), bisect: int = 5, maxiter: int = 40) -> dict:
    """Bands of quantities over the parameter sets within `delta` of the best objective.

    objective(z) -> (total, quantities dict, info) or None (invalid). z lives in a box `bounds`.
    pushes: [(quantity name, scale)]: each is pushed up and down by maximizing
    total +/- lambda * Q / scale. scan: (index, values) for a continuation profile over one
    coordinate. Returns {"best_total", "best_z", "points", "bands", "n_eval"}.
    """
    cache: dict = {}
    points: list = []
    n_eval = [0]

    def ev(z):
        key = np.asarray(z, float).round(12).tobytes()
        if key not in cache:
            n_eval[0] += 1
            cache[key] = objective(np.asarray(z, float))
        return cache[key]

    def record(z):
        r = ev(z)
        if r is not None and np.isfinite(r[0]):
            points.append((float(r[0]), dict(r[1]), np.array(z, float), r[2] if len(r) > 2 else {}))
        return r

    def local(z_start, fobj, bnds):
        def f(z):
            v = fobj(z)
            return INVALID if v is None or not np.isfinite(v) else -v
        r = minimize(f, np.asarray(z_start, float), method="L-BFGS-B", bounds=bnds,
                     options={"maxiter": maxiter, "eps": 1e-6})
        return r.x if r.fun < f(np.asarray(z_start, float)) else np.asarray(z_start, float)

    def tot(z):
        r = ev(z)
        return None if r is None else r[0]

    z_best = local(z0, tot, bounds)
    record(z0)
    record(z_best)
    t0 = max(p[0] for p in points)
    z_best = max(points, key=lambda p: p[0])[2]

    if scan is not None:
        idx, values = scan
        for direction in (1, -1):
            z = z_best.copy()
            vals = sorted((v for v in values if (v - z_best[idx]) * direction > 0), key=lambda v: abs(v - z_best[idx]))
            for v in vals:
                z = z.copy()
                z[idx] = v
                bnds = list(bounds)
                bnds[idx] = (v, v)
                z = local(z, tot, bnds)
                r = record(z)
                if r is None or r[0] < t0 - delta - 6.0:
                    break

    def push(name, scale, sign, z_start):
        def fobj(z, lam):
            r = ev(z)
            if r is None or r[1].get(name) is None:
                return None
            return r[0] + sign * lam * r[1][name] / scale
        z_ok, lam_ok, z = z_start.copy(), 0.0, z_start.copy()
        for lam in lambdas:
            z = local(z, lambda zz: fobj(zz, lam), bounds)
            r = record(z)
            if r is None or r[0] < t0 - delta:
                lo, hi = lam_ok, lam
                for _ in range(bisect):
                    mid = 0.5 * (lo + hi)
                    zm = local(z_ok, lambda zz: fobj(zz, mid), bounds)
                    rm = record(zm)
                    if rm is not None and rm[0] >= t0 - delta:
                        z_ok, lo = zm, mid
                    else:
                        hi = mid
                break
            z_ok, lam_ok = z, lam

    # First pass from the best fit; second pass from the most extreme accepted point found so far
    # (by any push or the scan), which gets past a local optimum the first pass stopped at.
    for name, scale in pushes:
        for sign in (1.0, -1.0):
            push(name, scale, sign, z_best)
    for name, scale in pushes:
        for sign in (1.0, -1.0):
            acc = [p for p in points if p[0] >= t0 - delta and p[1].get(name) is not None]
            if acc:
                ext = max(acc, key=lambda p: sign * p[1][name])
                if not np.allclose(ext[2], z_best):
                    push(name, scale, sign, ext[2])

    t_best = max(p[0] for p in points)
    best = max(points, key=lambda p: p[0])
    acc = [p for p in points if p[0] >= t_best - delta]
    bands = {}
    for q in best[1]:
        vals = [(p[1][q], p) for p in acc if p[1].get(q) is not None and np.isfinite(p[1][q])]
        if not vals or best[1].get(q) is None:
            continue
        lo = min(vals, key=lambda v: v[0])
        hi = max(vals, key=lambda v: v[0])
        bands[q] = Band(float(best[1][q]), float(lo[0]), float(hi[0]),
                        list(lo[1][3].get("at_bound", [])), list(hi[1][3].get("at_bound", [])))
    return {"best_total": t_best, "best_z": best[2], "points": points, "accepted": len(acc), "bands": bands,
            "n_eval": n_eval[0]}


# ----------------------------------------------------------------------------- the lab's hypotheses


def _frame_tags(case) -> dict:
    w = case.window
    return {"start": int(w[0]), "mid": int(case.ref_frame), "end": int(w[-1])}


def quantities(case, pred, params: dict) -> dict:
    """Measurable quantities predicted by one fitted model (the same list for every model)."""
    if not pred.valid:
        return {}
    tags = _frame_tags(case)
    q = {}
    for tag, i in tags.items():
        q[f"range_nmi@{tag}"] = float(pred.range_m[i] / F.NMI)
        q[f"closure_kt@{tag}"] = float(pred.closure_mps[i] / F.KT)
        q[f"altitude_ft@{tag}"] = float(pred.obj_alt[i] / F.FT)
    s = pred.scalars
    q["air_speed_kt"] = float(s["air_speed_kt"])
    q["ground_speed_kt"] = float(s["ground_speed_kt"])
    w = case.window
    q["intensity_ratio_end_over_start"] = float((pred.range_m[w[0]] / pred.range_m[w[-1]]) ** 2)
    # Bearing seen from a second aircraft abeam (to the right of the sight line) at the mid frame.
    i = tags["mid"]
    jet_wind = case.env.wind_enu(float(np.nanmedian(case.jet_alt)))
    jet = S._jet_model(case).state(params.get("jet_heading_deg", 0.0), jet_wind,
                                   turn_rate_z=params.get("turn_rate_z", 0.0), pitch_deg=S._jet_pitch(case, params))
    rel = pred.obj_pos[i, :2] - jet.pos[i, :2]
    uh = rel / np.linalg.norm(rel)
    perp = np.array([uh[1], -uh[0]])
    rel2 = rel - SECOND_SENSOR_OFFSET_NMI * F.NMI * perp
    q["second_bearing_deg@mid"] = float(-np.degrees(np.arctan2(rel2 @ perp, rel2 @ uh)))
    return q


PUSHES = [("range_nmi@mid", 1.0), ("closure_kt@mid", 10.0), ("altitude_ft@mid", 1000.0), ("air_speed_kt", 10.0),
          ("second_bearing_deg@mid", 0.5), ("intensity_ratio_end_over_start", 0.1), ("range_nmi@end", 1.0)]


class Problem:
    """One hypothesis on one case in the fit's unit-cube coordinates (as solve.score.fit)."""

    def __init__(self, case, hyp_id: str, testimony_weight: float = 0.0):
        self.case = case
        self.hyp = S._resolve_hypothesis(hyp_id)
        self.specs = S.param_specs(case, self.hyp)
        self.free = [s for s in self.specs if s.prior != "fixed"]
        self.const = {s.name: s.lo for s in self.specs if s.prior == "fixed"}
        self.w_t = float(testimony_weight)
        self.bounds = [(-1.0, 2.0) if s.periodic else (0.0, 1.0) for s in self.free]

    def params_of(self, z) -> dict:
        p = dict(self.const)
        for s, zi in zip(self.free, z):
            p[s.name] = s.from_unit(float(zi))
        return p

    def z_of(self, params: dict) -> np.ndarray:
        return np.array([s.to_unit(float(params[s.name])) for s in self.free])

    def evaluate(self, params: dict):
        ev = S._evaluate(self.case, self.hyp, params, self.specs, with_testimony=self.w_t != 0.0)
        if not ev["valid"]:
            return None
        df = S._rows(self.case, ev, self.specs, self.w_t)
        total = df.attrs["total_testimony_weighted"] if self.w_t else df.attrs["total_physics_only"]
        return float(total), ev["pred"]

    def objective(self, z):
        p = self.params_of(z)
        r = self.evaluate(p)
        if r is None:
            return None
        at_bound = [s.name for s in self.free if not s.periodic and s.prior != "normal"
                    and min(abs(s.to_unit(p[s.name])), abs(1 - s.to_unit(p[s.name]))) < 1e-3]
        return r[0], quantities(self.case, r[1], p), {"at_bound": at_bound}

    def range_index(self) -> int | None:
        for j, s in enumerate(self.free):
            if s.name == "range_ref_nmi":
                return j
        return None


_CASES: dict = {}


def _case(name: str, variant: str):
    key = (name, variant)
    if key not in _CASES:
        _CASES[key] = load_case(name, variant=variant or None)
    return _CASES[key]


def _below_normal():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass


def hypothesis_bands(task: dict) -> dict:
    """Bands for one hypothesis (worker entry point)."""
    case = _case(task["case"], task["variant"])
    prob = Problem(case, task["hypothesis"], 0.0)
    z0 = prob.z_of(task["params"])
    j = prob.range_index()
    scan = (j, list(np.linspace(0.0, 1.0, 13))) if j is not None else None
    out = profile_bands(prob.objective, z0, prob.bounds, PUSHES, scan=scan)
    # Testimony-weighted best fit: its predictions only (context, not a band).
    tw = Problem(case, task["hypothesis"], 0.0).objective(prob.z_of(task["params_tw"]))
    return {"hypothesis": task["hypothesis"], "best_total_physics_only": out["best_total"],
            "reported_total_physics_only": task["total_physics_only"], "accepted_points": out["accepted"],
            "n_points": len(out["points"]), "n_eval": out["n_eval"],
            "bands": {k: asdict(v) for k, v in out["bands"].items()},
            "testimony_weighted_fit": tw[1] if tw else {},
            "best_params": prob.params_of(out["best_z"])}


# ----------------------------------------------------------------------------- pairs


def _fitted(case_name: str, variant: str) -> list:
    r = json.loads((derived_dir(case_name) / "results.json").read_text(encoding="utf-8"))
    hs = r["variants"][variant]["hypotheses"] if variant else r["hypotheses"]
    return [h for h in hs if h.get("valid", True)]


def top_ids(fitted: list, n: int = 3) -> list:
    out = []
    for key in ("total_testimony_weighted", "total_physics_only"):
        for h in sorted(fitted, key=lambda h: -h[key])[:n]:
            if h["hypothesis"] not in out:
                out.append(h["hypothesis"])
    return out


def recovery_pairs(case_name: str, variant: str, margin: float = math.log(LR_TARGET)) -> list:
    """Pairs the model-recovery test could not separate (same rule as solve.recovery's report)."""
    p = derived_dir(case_name) / "recovery.csv"
    if not p.exists():
        return []
    df = pd.read_csv(p, keep_default_na=False, na_values=[""])
    df["variant"] = df["variant"].astype(object).fillna("").astype(str)
    df = df[(df["variant"] == variant) & (df["valid"].astype(str) == "True")]
    pairs = set()
    for _, grp in df.groupby(["generator", "set", "trial"]):
        grp = grp.sort_values("total_physics_only", ascending=False)
        g = grp["generator"].iloc[0]
        win = grp["fitted"].iloc[0]
        if win != g:
            pairs.add(tuple(sorted((g, win))))
        elif len(grp) > 1 and grp["total_physics_only"].iloc[0] - grp["total_physics_only"].iloc[1] < margin:
            pairs.add(tuple(sorted((g, grp["fitted"].iloc[1]))))
    return sorted(pairs)


def pair_list(case_name: str, variant: str, fitted: list) -> list:
    tops = top_ids(fitted)
    out = {}
    for i, a in enumerate(tops):
        for b in tops[i + 1:]:
            out.setdefault(tuple(sorted((a, b))), set()).add("top by a total")
    for pr in recovery_pairs(case_name, variant):
        out.setdefault(pr, set()).add("recovery: not separated")
    return [{"a": a, "b": b, "why": sorted(w)} for (a, b), w in sorted(out.items())]


# ----------------------------------------------------------------------------- per case


def notes() -> dict:
    return yaml.safe_load(NOTES.read_text(encoding="utf-8"))


def _measurement_key(q: str) -> str:
    return q.split("@")[0]


def evaluate_pairs(pairs: list, bands: dict, catalog: dict, t_of: dict) -> list:
    """For each pair, every candidate quantity's separation, ranked by feasibility."""
    out = []
    for pr in pairs:
        a, b = pr["a"], pr["b"]
        cands = []
        for q in sorted(set(bands.get(a, {})) & set(bands.get(b, {}))):
            m = catalog.get(_measurement_key(q))
            if m is None:
                continue
            A, B = Band(**bands[a][q]), Band(**bands[b][q])
            sep = separation(A, B)
            sig, kind = best_sigma(sep)
            typ = float(m["typical_sigma"])
            cands.append({"quantity": q, "time_s": t_of.get(q), "a_band": asdict(A), "b_band": asdict(B), **sep,
                          "required_sigma": sig, "kind": kind, "typical_sigma": typ,
                          "feasibility": (sig / typ) if sig else 0.0})
        cands.sort(key=lambda c: (c["kind"] == "both", c["feasibility"]), reverse=True)
        top = cands[0] if cands else None
        out.append({**pr, "candidates": cands, "top": top,
                    "realistic": bool(top and top["feasibility"] >= 1.0)})
    return out


def fov_conditioning(case_name: str, pairs: list) -> list:
    """GIMBAL: each pair's total difference at both fields of view (the FOV as a measurement)."""
    r = json.loads((derived_dir(case_name) / "results.json").read_text(encoding="utf-8"))
    if "variants" not in r:
        return []
    tab = {v: {h["hypothesis"]: h for h in d["hypotheses"]} for v, d in r["variants"].items()}
    out, seen = [], set()
    for pr in pairs:
        if (pr["a"], pr["b"]) in seen:
            continue
        seen.add((pr["a"], pr["b"]))
        row = {"a": pr["a"], "b": pr["b"]}
        for v, hs in tab.items():
            if pr["a"] in hs and pr["b"] in hs:
                row[v] = {k: hs[pr["a"]][k] - hs[pr["b"]][k] for k in ("total_physics_only", "total_testimony_weighted")}
        out.append(row)
    return out


def run_case(case_name: str, procs: int = 4, only_variant: str | None = None) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    _below_normal()
    r = json.loads((derived_dir(case_name) / "results.json").read_text(encoding="utf-8"))
    variants = list(r["variants"]) if "variants" in r else [""]
    cat = notes()["measurements"]
    result = {"case": case_name, "band_delta": BAND_DELTA, "lr_target": LR_TARGET,
              "second_sensor_offset_nmi": SECOND_SENSOR_OFFSET_NMI, "variants": {}}
    out = derived_dir(case_name) / "discriminators.json"
    if only_variant is not None:
        # Recompute one variant and keep the others from the existing file.
        old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        result["variants"] = {v: vv for v, vv in old.get("variants", {}).items() if v != only_variant}
        variants = [only_variant]
    for v in variants:
        fitted = _fitted(case_name, v)
        pairs = pair_list(case_name, v, fitted)
        need = sorted({p["a"] for p in pairs} | {p["b"] for p in pairs})
        tasks = [{"case": case_name, "variant": v, "hypothesis": h["hypothesis"], "params": h["params_physics_only_fit"],
                  "params_tw": h["params_testimony_weighted_fit"], "total_physics_only": h["total_physics_only"]}
                 for h in fitted if h["hypothesis"] in need]
        if procs > 1:
            with ProcessPoolExecutor(max_workers=procs, initializer=_below_normal) as ex:
                hb = list(ex.map(hypothesis_bands, tasks))
        else:
            hb = [hypothesis_bands(t) for t in tasks]
        bands = {h["hypothesis"]: h["bands"] for h in hb}
        case = _case(case_name, v)
        tags = _frame_tags(case)
        t_of = {}
        for q in next(iter(bands.values()), {}):
            tag = q.split("@")[1] if "@" in q else None
            t_of[q] = float(case.t[tags[tag]] - case.t[0]) if tag else None
        frames = {k: int(i) for k, i in tags.items()}
        result["variants"][v] = {
            "frames": frames, "times_s": {k: float(case.t[i] - case.t[0]) for k, i in tags.items()},
            "top": top_ids(fitted), "recovery_pairs": [list(p) for p in recovery_pairs(case_name, v)],
            "hypotheses": hb, "pairs": evaluate_pairs(pairs, bands, cat, t_of)}
    order = list(r["variants"]) if "variants" in r else [""]
    result["variants"] = {v: result["variants"][v] for v in order if v in result["variants"]}
    result["fov_conditioning"] = fov_conditioning(case_name, [p for vv in result["variants"].values() for p in vv["pairs"]])
    out.write_text(json.dumps(result, indent=1, default=S._jsonable), encoding="utf-8")
    return result


# ----------------------------------------------------------------------------- report


def _fmt(x, q: str = "") -> str:
    if x is None:
        return "n/a"
    k = _measurement_key(q)
    if k in ("altitude_ft",):
        return f"{x:,.0f}"
    if k in ("intensity_ratio_end_over_start",):
        return f"{x:.2f}"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 10:
        return f"{x:.1f}"
    return f"{x:.2f}"


def _band_txt(b: dict, q: str) -> str:
    s = f"{_fmt(b['best'], q)} ({_fmt(b['lo'], q)} to {_fmt(b['hi'], q)})"
    edge = [n for n in set(b.get("lo_at_bound", [])) | set(b.get("hi_at_bound", []))]
    return s + (" [band reaches a prior bound]" if edge else "")


def _when(q: str, vv: dict) -> str:
    if "@" not in q:
        return "whole clip"
    tag = q.split("@")[1]
    return f"frame {vv['frames'][tag]} ({vv['times_s'][tag]:.1f} s)"


def _variant_lines(case_name: str, v: str, vv: dict, cat: dict, labels: dict) -> list:
    L = []
    L.append(f"Top hypotheses (top three by either total): {', '.join(vv['top'])}. "
             + ("Pairs the recovery test could not separate: " + "; ".join(f"{a} and {b}" for a, b in vv["recovery_pairs"]) + "."
                if vv["recovery_pairs"] else "No model-recovery run for this setting, so only the top pairs are listed."))
    L.append("")
    L.append("| To tell | from | measure | when | to within | first predicts | second predicts | works if | does that data exist? |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for p in vv["pairs"]:
        t = p["top"]
        if t is None:
            L.append(f"| {p['a']} | {p['b']} | nothing computed | | | | | | |")
            continue
        m = cat[_measurement_key(t["quantity"])]
        works = {"both": "either is true", "a_true": f"{p['a']} is true", "b_true": f"{p['b']} is true",
                 "none": "no precision works"}[t["kind"]]
        prec = f"{_fmt(t['required_sigma'], t['quantity'])} {m['unit']}" if t["required_sigma"] else "none suffices"
        exists = m.get("exists", {}).get(case_name, m.get("exists", {}).get("default", ""))
        L.append(f"| {p['a']} | {p['b']} | {m['label']} | {_when(t['quantity'], vv)} | {prec} | "
                 f"{_band_txt(t['a_band'], t['quantity'])} {m['unit']} | {_band_txt(t['b_band'], t['quantity'])} {m['unit']} | "
                 f"{works} | {exists} |")
    L.append("")
    L.append("Feasibility is the required precision divided by a typical precision for that kind of data "
             "(at least 1 means an existing instrument class could do it). Every candidate per pair:")
    L.append("")
    L.append("| Pair | Measurement | When | First predicts | Second predicts | Gap between bands | Needed (both ways / one way) | Typical | Feasibility |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for p in vv["pairs"]:
        for c in p["candidates"]:
            m = cat[_measurement_key(c["quantity"])]
            need = ("both " + _fmt(c["sigma_both"], c["quantity"])) if c["sigma_both"] else (
                "one way " + _fmt(c["required_sigma"], c["quantity"]) if c["required_sigma"] else "none")
            L.append(f"| {p['a']} vs {p['b']} | {m['label']} | {_when(c['quantity'], vv)} | {_band_txt(c['a_band'], c['quantity'])} | "
                     f"{_band_txt(c['b_band'], c['quantity'])} | {_fmt(c['gap'], c['quantity']) if c['gap'] > 0 else 'overlap'} | {need} {m['unit']} | "
                     f"{_fmt(c['typical_sigma'], c['quantity'])} | {c['feasibility']:.2f} |")
    L.append("")
    return L


def write_report() -> Path:
    nt = notes()
    cat = nt["measurements"]
    L = ["# Discriminators (M3.6): what single measurement would settle each pair?", "",
         "Generated by `python -m solve.discriminators --report` from `data/derived/<case>/discriminators.json` "
         "(written by `python -m solve.discriminators <case>`); narrative and data-availability notes from "
         "`data/discriminators/notes.yaml`. Design: `docs/design/scoring.md`, Discriminators (binding).", ""]
    L += [ln.rstrip() for ln in nt["method"].strip().splitlines()]
    L.append("")
    for case_name in ("gimbal", "gofast", "flir1"):
        sec = nt["cases"].get(case_name, {})
        L.append(f"## {sec.get('title', case_name.upper())}")
        L.append("")
        p = derived_dir(case_name) / "discriminators.json"
        if not p.exists():
            L += [ln.rstrip() for ln in str(sec.get("stub", "Not computed yet.")).strip().splitlines()]
            L.append("")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for v, vv in d["variants"].items():
            if v:
                L.append(f"### {sec.get('variant_titles', {}).get(v, v)}")
                L.append("")
            L += _variant_lines(case_name, v, vv, cat, {})
        if d.get("fov_conditioning"):
            L.append("### The field of view as a measurement")
            L.append("")
            vs = [v for v in d["variants"]]
            L.append("Difference in totals (first minus second; positive favors the first; 2.3 is a likelihood ratio of 10) at each field of view:")
            L.append("")
            L.append("| Pair | " + " | ".join(f"{sec.get('variant_titles', {}).get(v, v)} physics-only / testimony-weighted" for v in vs) + " |")
            L.append("|---|" + "---|" * len(vs))
            seen = set()
            for row in d["fov_conditioning"]:
                key = (row["a"], row["b"])
                if key in seen:
                    continue
                seen.add(key)
                cells = []
                for v in vs:
                    x = row.get(v)
                    cells.append(f"{x['total_physics_only']:+.1f} / {x['total_testimony_weighted']:+.1f}" if x else "n/a")
                L.append(f"| {row['a']} vs {row['b']} | " + " | ".join(cells) + " |")
            L.append("")
        L += [ln.rstrip() for ln in str(sec.get("settle", "")).strip().splitlines()]
        L.append("")
    L += [ln.rstrip() for ln in nt.get("limits", "").strip().splitlines()]
    L.append("")
    REPORT.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    return REPORT


def main(argv: list[str]) -> int:
    procs = 4
    if "--procs" in argv:
        procs = int(argv[argv.index("--procs") + 1])
    only = argv[argv.index("--variant") + 1] if "--variant" in argv else None
    names = [a for a in argv if a in ("gimbal", "gofast", "flir1", "all")]
    for n in (["gimbal", "gofast", "flir1"] if "all" in names else names):
        d = run_case(n, procs=procs, only_variant=only)
        for v, vv in d["variants"].items():
            for p in vv["pairs"]:
                t = p["top"]
                print(n, v or "-", p["a"], p["b"], t and t["quantity"], t and t["kind"],
                      t and t["required_sigma"], t and round(t["feasibility"], 2))
    if "--report" in argv:
        print(write_report())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
