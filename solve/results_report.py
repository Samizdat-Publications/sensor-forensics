"""Plain-language results page for one case: docs/results/<case>.md, written from results.json.

Usage: python -m solve.results_report gofast
The page is generated, never hand-edited, so it always matches the numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def derived_dir(case: str) -> Path:
    from .case_data import derived_dir as _d

    return _d(case)


def _f(x, nd=1):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        return f"{x:,.{nd}f}"
    return str(x)


CRIT_NAMES = {
    "line_of_sight_az": "Azimuth readout",
    "line_of_sight_el": "Elevation readout",
    "range": "Range readout",
    "closure": "Closure (Vc) readout",
    "background_motion": "Ocean motion in the image",
    "size_trend": "Apparent size trend",
    "brightness_trend": "Brightness trend",
    "prior": "Nuisance priors",
    "complexity_penalty": "Complexity penalty",
    "testimony": "Testimony (before weight)",
}


WHY_ZERO = {
    "size_trend": "D-016: the blob is not resolved against the point-spread width measured on this video (REVIEW-M3 item 4)",
    "brightness_trend": "REVIEW-M3 Rule B: the blob is saturated, so its integrated contrast is not range-informative",
}
# A data-quality rule other than the default one, identified by the case loader's flag (solve/case_data.py).
WHY_ZERO_BY_FLAG = {
    "size_trend": [("D-017: apparent-size criterion reported with weight 0",
                    "D-017: the blob is resolved but saturated (Rule B1 saturation flag), so its size is clipped, not range-informative")],
}


def _why(c: str, o: dict | None = None) -> str:
    """Why criterion c has weight 0 on this result (the loader's flag decides which rule applied)."""
    for prefix, txt in WHY_ZERO_BY_FLAG.get(c, []):
        if o is not None and any(str(f).startswith(prefix) for f in o.get("flags", [])):
            return txt
    return WHY_ZERO.get(c, "weight 0 on this case")


def _zero(o: dict) -> list:
    """Physics criteria this case gives weight 0 (reported, not in any total)."""
    return [c for c in ("size_trend", "brightness_trend", "rotation", "background_motion", "range", "closure")
            if float(o["weights"].get(c, 1.0)) == 0.0]


def _lab(c: str, o: dict, names: dict) -> str:
    return names.get(c, c) + (" (weight 0)" if c in _zero(o) else "")


def _added_back(L: list, hyps_by_v: dict, labels: dict, names: dict) -> None:
    """Sensitivity: each weight-0 criterion added back at weight 1 (testimony-weighted fit values)."""
    if not any(_zero(o) for o, _ in hyps_by_v.values()):
        return
    L.append("### Sensitivity: weight-0 criteria added back")
    L.append("")
    L.append("Criteria that fail a data-quality test are reported but kept out of every total. For transparency, this table adds each one back at weight 1 to the testimony-weighted fit's totals (the fit itself is not redone, so a refit could only raise these numbers).")
    L.append("")
    for v, (o, hyps) in hyps_by_v.items():
        z = _zero(o)
        if not z:
            continue
        head = f"{labels[v]}: " if labels[v] else ""
        L.append(head + "; ".join(f"{names.get(c, c)}: {_why(c, o)}" for c in z) + ".")
        L.append("")
        L.append("| Hypothesis | " + " | ".join(f"+ {names.get(c, c)}: weighted / physics" for c in z) + " | + all: weighted / physics |")
        L.append("|---|" + "---|" * (len(z) + 1))
        for h in hyps:
            cells = []
            tot_w = h["total_testimony_weighted"]
            tot_p = tot_w - o["weights"]["testimony"] * h["criteria"].get("testimony", 0.0)
            aw, ap = tot_w, tot_p
            for c in z:
                x = h["criteria"].get(c, 0.0)
                cells.append(f"{_f(tot_w + x)} / {_f(tot_p + x)}")
                aw += x
                ap += x
            cells.append(f"{_f(aw)} / {_f(ap)}")
            L.append(f"| {h['hypothesis']} | " + " | ".join(cells) + " |")
        L.append("")


def _recovery_lines(case: str, variant: str = "") -> list:
    """Brief confusion matrix from data/derived/<case>/recovery.csv (M3.4), if it exists."""
    import pandas as pd

    p = derived_dir(case) / "recovery.csv"
    if not p.exists():
        return ["- Which hypotheses this data can separate in principle: the M3.4 recovery test has not been run for this case."]
    df = pd.read_csv(p, keep_default_na=False, na_values=[""])
    df["variant"] = df["variant"].astype(object).fillna("").astype(str)
    df = df[df["variant"] == variant]
    if df.empty or "winner" not in df:
        return ["- Which hypotheses this data can separate in principle: no M3.4 recovery run for this setting."]
    ok = df[df["valid"].astype(str).str.lower() == "true"]
    win = ok.loc[ok.groupby(["generator", "set", "trial"])["total_physics_only"].idxmax()]
    tab = pd.crosstab(win["generator"], win["fitted"])
    cols = sorted(set(df["fitted"]))
    out = ["- Model recovery (M3.4, `docs/results/recovery.md`): synthetic data from each hypothesis, scored by the same path (physics-only total). Rows: the hypothesis that made the data; columns: how often each hypothesis won.", ""]
    out.append("| Data made by | " + " | ".join(cols) + " | data sets |")
    out.append("|---|" + "---|" * (len(cols) + 1))
    for g in sorted(set(df["generator"])):
        row = tab.loc[g] if g in tab.index else None
        n = int(row.sum()) if row is not None else 0
        out.append(f"| {g} | " + " | ".join(str(int(row.get(c, 0))) if row is not None else "0" for c in cols) + f" | {n} |")
    out.append("")
    return out


def _bounds(h: dict, d: dict, bnd: list) -> str:
    """Parameters at a prior bound, plus any altitude constraint the fit sits on (within 50 ft)."""
    from . import score as S_

    out = list(bnd)
    hy = {x.id: x for x in S_.load_hypotheses()}.get(h["hypothesis"])
    for c in (hy.constraints if hy else []):
        if c["quantity"] == "object_altitude_ft":
            if d.get("altitude_ft_min", 1e9) <= float(c["min"]) + 50 or d.get("altitude_ft_max", -1e9) >= float(c["max"]) - 50:
                out.append(f"altitude constraint ({float(c['min']):,.0f} to {float(c['max']):,.0f} ft)")
    return ", ".join(out) or "none"


def build(case: str) -> str:
    res = json.loads((derived_dir(case) / "results.json").read_text(encoding="utf-8"))
    hyps = [h for h in res["hypotheses"] if h["valid"]]
    hyps.sort(key=lambda h: h["rank_testimony_weighted"])
    L = []
    L.append(f"# {res['label']}: hypothesis scores (M3)")
    L.append("")
    L.append("Generated by `python -m solve.score " + case + "` then `python -m solve.results_report " + case +
             "` from `data/derived/" + case + "/results.json` and `scores.csv`. Design: `docs/design/scoring.md` (binding).")
    L.append("")
    if res["flags"]:
        L.append("**Status flags (read first):**")
        L.append("")
        for f in res["flags"]:
            L.append(f"- {f}")
        ts = {h.get("testimony_status") for h in hyps}
        for s in ts:
            L.append(f"- Testimony: {s}.")
        L.append("- Review: the M3 review items (brightness audit, equal range priors, point-spread width) are resolved in `docs/results/REVIEW-M3.md`; which hypotheses this data can separate at all is in `docs/results/recovery.md`.")
        L.append("")
    L.append("## What was scored")
    L.append("")
    w = res["window_frames"]
    L.append(f"- Frames {w[0]} to {w[1]} (the frames with the range readout on screen); reference frame {res['reference_frame']}.")
    L.append("- Every hypothesis was fitted by the same code (maximum likelihood within its prior bounds, multi-start), against the same observables, with the same noise model and weights (`solve/scoring.yaml`). Hypotheses differ only in their physical model and priors (`solve/hypotheses/*.yaml`).")
    L.append("- Jet heading and the wind error at the object's altitude are fitted for every hypothesis (shared nuisance parameters); the jet's heading is not on screen.")
    ne = res["criteria_n_eff"]
    L.append("- Effective sample sizes (from the data's own autocorrelation, the same for every hypothesis): " +
             ", ".join(f"{_lab(k, res, CRIT_NAMES)} {v:.0f}" for k, v in ne.items()) + f"; total of the criteria in the totals (the BIC n) {res['n_eff_total']:.0f}.")
    L.append("- Log-likelihoods: higher is better. A difference of 2.3 is a likelihood ratio of 10. Totals include a complexity penalty of 0.5 k ln(n_eff) for k free parameters.")
    L.append("")
    L.append("## Results table")
    L.append("")
    L.append("Two totals, each at its own best fit: testimony-weighted (testimony weight "
             f"{res['weights']['testimony']}) and physics-only (testimony weight 0). \"Design set\" marks the hypotheses the design table lists for this video; the others were scored too, the same way, for completeness.")
    L.append("")
    L.append("| Rank (testimony-weighted) | Hypothesis | Design set | Testimony-weighted total | Physics-only total | Rank (physics-only) | k |")
    L.append("|---|---|---|---|---|---|---|")
    for h in hyps:
        L.append(f"| {h['rank_testimony_weighted']} | {h['hypothesis']}: {h['label']} | {_f(h['in_design_set'])} | "
                 f"{_f(h['total_testimony_weighted'])} | {_f(h['total_physics_only'])} | {h['rank_physics_only']} | {h['k']} |")
    L.append("")
    top = hyps[0]
    L.append("Gap to the leader (testimony-weighted, then physics-only): " + "; ".join(
        f"{h['hypothesis']} {_f(h['total_testimony_weighted'] - top['total_testimony_weighted'])} / "
        f"{_f(h['total_physics_only'] - max(x['total_physics_only'] for x in hyps))}" for h in hyps[1:]) + ".")
    L.append("")
    _added_back(L, {"": (res, hyps)}, {"": ""}, CRIT_NAMES)
    L.append("## Best-fit object (testimony-weighted fit)")
    L.append("")
    L.append("| Hypothesis | Range (nmi, mean) | Altitude (ft) | Air speed (kt) | Ground speed (kt) | Ground track (deg) | Vertical speed (ft/min) | Jet heading (deg) | Wind error E, N (kt) | Params at a prior bound |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for h in hyps:
        d, p = h["derived"], h["params_testimony_weighted_fit"]
        L.append(f"| {h['hypothesis']} | {_f(d['range_nmi_mean'], 2)} | {_f(d['altitude_ft_mean'], 0)} | {_f(d['air_speed_kt'])} | "
                 f"{_f(d['ground_speed_kt'])} | {_f(d['ground_track_deg'], 0)} | {_f(d['vertical_speed_fpm'], 0)} | "
                 f"{_f(p['jet_heading_deg'], 0)} | {_f(p['wind_err_e_kt'])}, {_f(p['wind_err_n_kt'])} | "
                 f"{_bounds(h, d, h['params_at_bound'])} |")
    L.append("")
    L.append("All fitted parameters (both fits) are in `results.json`.")
    L.append("")
    L.append("## Per-criterion log-likelihoods (testimony-weighted fit)")
    L.append("")
    crits = list(hyps[0]["criteria"].keys())
    L.append("| Criterion | Weight | " + " | ".join(h["hypothesis"] for h in hyps) + " |")
    L.append("|---|---|" + "---|" * len(hyps))
    for c in crits:
        key = "line_of_sight" if c.startswith("line_of_sight") else c
        wt = res["weights"].get(key, 1.0) if c not in ("prior", "complexity_penalty") else 1.0
        L.append(f"| {_lab(c, res, CRIT_NAMES)} | {_f(wt, 1)} | " + " | ".join(_f(h["criteria"].get(c)) for h in hyps) + " |")
    L.append("")
    for c in _zero(res):
        L.append(f"- {CRIT_NAMES.get(c, c)}: shown but weight 0 ({_why(c, res)}).")
    if _zero(res):
        L.append("")
    cc = res.get("closure_check") or {}
    if cc:
        L.append("## Closure-rate check")
        L.append("")
        L.append(f"The Vc readout falls from {_f(cc['closure_readout_kt_first_last'][0], 0)} to {_f(cc['closure_readout_kt_first_last'][1], 0)} kt over frames {cc['frames'][0]} to {cc['frames'][1]}. "
                 f"If the object hung still in the air at the jet's level, the closing speed would be the jet's own airspeed projected on the line of sight, TAS cos(el) cos(az), which needs no wind and no jet heading: "
                 f"{_f(cc['still_air_projection_kt_first_last'][0], 0)} kt at the start and {_f(cc['still_air_projection_kt_first_last'][1], 0)} kt at the end.")
        L.append("")
        L.append(f"- Readout minus that projection: mean {_f(cc['readout_minus_projection_kt_mean'])} kt, rms {_f(cc['readout_minus_projection_kt_rms'])} kt "
                 f"(start {_f(cc['readout_minus_projection_kt_first_last'][0])}, end {_f(cc['readout_minus_projection_kt_first_last'][1])} kt). "
                 "This is the object's own velocity along the line of sight, relative to the air at the jet's level, plus readout error. A balloon would show only the wind shear between its altitude and the jet's projected on the line of sight; a fast object would add its own speed.")
        L.append(f"- The range readout's own rate of change is {_f(cc['range_readout_rate_kt'])} kt against a mean Vc readout of {_f(cc['closure_readout_mean_kt'])} kt, so Vc and RNG agree on average.")
        if "best_fit_hypothesis" in cc:
            L.append(f"- The top hypothesis ({cc['best_fit_hypothesis']}) reproduces the Vc readout with an rms error of {_f(cc['best_fit_closure_rms_kt'])} kt.")
        L.append(f"- {cc['note']}")
        L.append("")
    L.append("## Testimony claims that bear on this video")
    L.append("")
    rows = {}
    for h in hyps:
        for r in h.get("testimony_rows", []):
            rows.setdefault((r["claim_id"], r["quantity"]), {})[h["hypothesis"]] = r
    if rows:
        L.append("Scored by `solve/testimony.py` (the same claims for every hypothesis; firsthand weight 1.0, relayed 0.5; recalled numbers never tighter than 25 percent). Each cell: predicted value, weighted log-likelihood.")
        L.append("")
        L.append("| Claim | Quantity | Claimed interval (sigma) | " + " | ".join(h["hypothesis"] for h in hyps) + " |")
        L.append("|---|---|---|" + "---|" * len(hyps))
        for (cid, q), per in rows.items():
            any_r = next(iter(per.values()))
            iv = any_r["interval"]
            ivs = f"{_f(iv.get('lo'), 1)} to {_f(iv.get('hi'), 1)} ({_f(iv.get('sigma'), 1)})" if "lo" in iv else str(iv.get("value"))
            cells = []
            for h in hyps:
                r = per.get(h["hypothesis"])
                pv = r["predicted_value"] if r else None
                pvs = _f(pv, 1) if isinstance(pv, (int, float)) else str(pv)
                cells.append(f"{pvs}, {_f(r['weighted_loglik'], 2)}" if r else "n/a")
            L.append(f"| {cid} | {q} | {ivs} | " + " | ".join(cells) + " |")
        L.append("")
    else:
        L.append("No testimony claims were scored for this case.")
        L.append("")
    L.append("Claims about on-screen numbers (jet altitude, the range and Vc fields, polarity) test memory against the record and never enter a hypothesis score (`solve.testimony.witness_consistency`).")
    L.append("")
    rc = res.get("range_curve_angles_only") or []
    if rc:
        L.append("## Range curve from the angles alone")
        L.append("")
        L.append("If the range readout and Vc are set aside, the azimuth, elevation and ocean motion fit a constant-velocity object at almost any range; the speed and altitude it would need change with range. This is the range problem the on-screen RNG removes.")
        L.append("")
        L.append("| Assumed range (nmi) | Air speed (kt) | Ground speed (kt) | Altitude (ft) | Line-of-sight log-likelihood |")
        L.append("|---|---|---|---|---|")
        for r in rc:
            if r.get("valid"):
                L.append(f"| {_f(r['range_nmi'])} | {_f(r['air_speed_kt'], 0)} | {_f(r['ground_speed_kt'], 0)} | {_f(r['altitude_ft_mean'], 0)} | {_f(r['line_of_sight_loglik'])} |")
        bad = [_f(r["range_nmi"]) for r in rc if not r.get("valid")]
        if bad:
            L.append("")
            L.append(f"No solution at {', '.join(bad)} nmi: the sight line reaches the sea before that range.")
        L.append("")
    L.append("## Checks reported, not scored")
    L.append("")
    L.append("Implied size is the blob's length times the range: an upper bound, because the blob includes the optics' blur.")
    L.append("")
    L.append("| Hypothesis | Implied size, upper bound (m) | Expected (m) | Inside? |")
    L.append("|---|---|---|---|")
    for h in hyps:
        for c in h["checks"]:
            L.append(f"| {h['hypothesis']} | {_f(c['value'], 2)} | {c['min']} to {c['max']} | {_f(c['pass'])} |")
    L.append("")
    L.append("## How to read this, and its limits")
    L.append("")
    L.append("- Likelihoods, not verdicts. No prior probability is put on any class of explanation; readers can add their own.")
    L.append("- The ocean-motion, closure and brightness criteria carry large negative values for every hypothesis: they measure how well the shared jet and pod model reproduces the data, and mostly cancel between hypotheses. Compare differences, not absolute values.")
    L.append("- Interpretations made where the design was silent: n_eff comes from the data's autocorrelation about a cubic fit (not from each hypothesis's residuals), so every hypothesis gets the same n_eff; the BIC n is the sum of the n_eff of the physics criteria that carry weight; parameters with a normal prior (wind error, vertical speed) enter through their log prior (relative to its peak) instead of k; azimuth and elevation are compared at the display's 6-frame update frames, range and Vc on every frame with the n_eff correction.")
    raw = sorted(((h["total_physics_only"] - h["criteria"].get("complexity_penalty", 0.0), h["hypothesis"]) for h in hyps), reverse=True)
    L.append("- Fit before the complexity penalty (physics-only): " + "; ".join(f"{n} {_f(v)}" for v, n in raw) +
             ". A model with more free parameters always fits at least as well; the penalty decides whether the extra freedom is earned.")
    common = set.intersection(*[set(h["params_at_bound"]) for h in hyps]) if hyps else set()
    if common:
        L.append(f"- Every hypothesis puts {', '.join(sorted(common))} at its prior bound. That is a property of the shared data and jet model, not of any hypothesis (for the elevation anchor: the readout seems to sit about half a degree or more below the true sight line, as if the display truncated rather than rounded, or the jet's pitch entered; open).")
    L += _recovery_lines(case)
    L.append("- Discriminators for the top pair (M3.6) are not written yet.")
    L.append("")
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- cases with sensor variants (GIMBAL)

CRIT_NAMES_V = dict(CRIT_NAMES, background_motion="Cloud motion (turn-rate band)", rotation="Image rotation")


def _fov(o) -> str:
    return f"{o['sensor'].get('fov_deg')} deg"


def _net_rotation(h: dict, n_eff_total: float) -> float:
    import math
    return h["loglik_scaled"] - 0.5 * h["free_terms"] * math.log(n_eff_total)


def _rotation_plot(res: dict, path: Path) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    names = res["variant_names"]
    fig, axes = plt.subplots(2, len(names), figsize=(7 * len(names), 7), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.3]}, squeeze=False)
    for j, v in enumerate(names):
        o = res["variants"][v]
        rc = o["rotation_check"]
        fr = rc["frames"]
        meas = rc["measured_deg"]
        ax, axr = axes[0][j], axes[1][j]
        ax.plot(fr, meas, color="0.55", lw=0.8, label="measured orientation")
        hy = {e["hypothesis"]: e for e in o["hypotheses"] if e["valid"]}
        best_g = max((k for k, h in rc["hypotheses"].items() if h["kind"] == "glare"),
                     key=lambda k: hy[k]["total_testimony_weighted"], default=None)
        best_p = max((k for k, h in rc["hypotheses"].items() if h["kind"] == "physical"),
                     key=lambda k: hy[k]["total_testimony_weighted"], default=None)
        if best_g:
            g = rc["hypotheses"][best_g]
            ax.plot(fr, g["fitted_deg"], color="C0", lw=1.4, label=f"{best_g}: glare, Sitrec derotation (1 offset)")
            axr.plot(fr, [a - b for a, b in zip(meas, g["fitted_deg"])], color="C0", lw=0.8)
            if "deadband" in g:
                db = g["deadband"]
                if db.get("best_coarse_fitted_deg"):
                    ax.plot(fr, db["best_coarse_fitted_deg"], color="C2", lw=1.0, ls="--",
                            label=f"{best_g}: + stepping (deadband) pod roll, diagnostic")
        if best_p:
            p = rc["hypotheses"][best_p]
            ax.plot(fr, p["fitted_deg"], color="C3", lw=1.2,
                    label=f"{best_p}: physical, free spline ({p['model_terms']} knots)")
            axr.plot(fr, [a - b for a, b in zip(meas, p["fitted_deg"])], color="C3", lw=0.8)
        for st in rc["measured_steps"]:
            ax.axvline(st["frame"], color="k", lw=0.5, alpha=0.4)
            axr.axvline(st["frame"], color="k", lw=0.5, alpha=0.4)
        ax.set_title(f"GIMBAL image rotation, field of view {_fov(o)}")
        ax.set_ylabel("orientation (deg, CCW)")
        ax.legend(fontsize=7, loc="upper left")
        axr.set_ylabel("residual (deg)")
        axr.set_xlabel("frame")
        axr.axhline(0, color="k", lw=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path.name


def build_variants(case: str) -> str:
    import math
    res = json.loads((derived_dir(case) / "results.json").read_text(encoding="utf-8"))
    names = res["variant_names"]
    V = res["variants"]
    first = V[names[0]]
    L = []
    L.append(f"# {res['label']}: hypothesis scores (M3.5)")
    L.append("")
    L.append(f"Generated by `python -m solve.score {case}` (one run per field of view) then `python -m solve.results_report {case}` "
             f"from `data/derived/{case}/results.json` and `scores.csv`. Design: `docs/design/scoring.md` (binding). "
             "Nothing on this page is a verdict about what the object was: these are likelihoods under stated conditions.")
    L.append("")
    flags = []
    for v in names:
        for f in V[v]["flags"]:
            if f not in flags:
                flags.append(f)
    L.append("**Status flags (read first):**")
    L.append("")
    for f in flags:
        where = [v for v in names if f in V[v]["flags"]]
        tag = "" if len(where) == len(names) else "At " + ", ".join(_fov(V[v]) for v in where) + ": "
        L.append(f"- {tag}{f}")
    ts = {h.get("testimony_status") for v in names for h in V[v]["hypotheses"] if h["valid"]}
    for s_ in ts:
        L.append(f"- Testimony: {s_}.")
    L.append("- Field of view is a sensor setting, not a hypothesis parameter: every hypothesis is scored at 0.35 deg and again at 0.7 deg, and the two runs are reported side by side, never mixed.")
    L.append("- Review: the four M3 review items (brightness audit, equal range priors, ERA5 turn rate, point-spread width) are resolved in `docs/results/REVIEW-M3.md`; which hypotheses this data can separate at all is in `docs/results/recovery.md`.")
    L.append("")

    # ---------------------------------------------------------------- what was scored
    L.append("## What was scored")
    L.append("")
    w = first["window_frames"]
    L.append(f"- Frames {w[0]} to {w[1]} (all of them: the object is found on every frame); reference frame {first['reference_frame']}.")
    L.append("- Every hypothesis was fitted by the same code (maximum likelihood within its prior bounds, multi-start), against the same observables, with the same noise model and weights (`solve/scoring.yaml`). Hypotheses differ only in their physical model and priors (`solve/hypotheses/*.yaml`).")
    L.append("- Shared nuisance parameters, fitted for every hypothesis: the jet's starting heading (not on screen), the wind error at the object's altitude, the sight-line offsets inside the whole-degree readouts, the jet's turn-rate offset inside its measured band, and the jet's pitch (which only moves the pod roll and image horizon).")
    tr = {v: V[v].get("turn_rate", {}) for v in names}
    L.append("- Jet turn rate: the lab's own cloud-derived history (`docs/reproductions/gimbal_turn_rate.md`), recomputed with ERA5 winds and temperature (REVIEW-M3 item 3) and re-derived from the same cloud measurement at each field of view: total heading change " +
             ", ".join(f"{_f(tr[v].get('heading_change_deg'))} deg at {_fov(V[v])}" for v in names) +
             "; median 1-sigma band " + ", ".join(f"{_f(tr[v].get('sigma_median_deg_s'), 3)} deg/s" for v in names) +
             ". The cloud motion enters once, as the band's Gaussian on the turn-rate offset (the \"cloud motion\" row).")
    L.append(f"- Display rounding (D-016, shared): the readout {first['display_rounding']}s (fitted once from the azimuth readout's hold times).")
    ne = first["criteria_n_eff"]
    L.append("- Effective sample sizes (from the data's own autocorrelation, the same for every hypothesis): " +
             ", ".join(f"{CRIT_NAMES_V.get(k, k)} {v:.0f}" for k, v in ne.items()) +
             "; total of the criteria in the totals (the BIC n): " + ", ".join(f"{V[v]['n_eff_total']:.0f} at {_fov(V[v])}" for v in names) + ".")
    rs = first["data_sigmas"].get("rotation")
    L.append(f"- Image rotation: the measured orientation of the blob's major axis on all 1,031 frames, noise {_f(rs, 2)} deg (scatter about a 9-frame running median). A glare model predicts it from the pod geometry with ONE free offset (Sitrec's glare start angle); a physical model gets a free smooth rotation (a spline whose knot count the data choose, each knot charged 0.5 ln(n_eff) like any parameter). Both get one shared offset for the black-hot segment.")
    L.append("- Log-likelihoods: higher is better. A difference of 2.3 is a likelihood ratio of 10. Totals include a complexity penalty of 0.5 k ln(n_eff) for k free parameters.")
    L.append("")

    # ---------------------------------------------------------------- results
    L.append("## Results: both totals at both fields of view")
    L.append("")
    L.append("Each total is at its own best fit: testimony-weighted (testimony weight "
             f"{first['weights']['testimony']}) and physics-only (testimony weight 0). Rank in brackets.")
    L.append("")
    hdr = "| Hypothesis | " + " | ".join(f"{_fov(V[v])} testimony-weighted | {_fov(V[v])} physics-only" for v in names) + " | k |"
    L.append(hdr)
    L.append("|---|" + "---|---|" * len(names) + "---|")
    ids = [h["hypothesis"] for h in sorted((h for h in first["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"])]
    ids += [h["hypothesis"] for h in first["hypotheses"] if not h["valid"]]
    for hid in ids:
        cells = []
        lab = ""
        kk = ""
        for v in names:
            h = next(x for x in V[v]["hypotheses"] if x["hypothesis"] == hid)
            lab = h["label"]
            if h["valid"]:
                cells.append(f"{_f(h['total_testimony_weighted'])} ({h['rank_testimony_weighted']})")
                cells.append(f"{_f(h['total_physics_only'])} ({h['rank_physics_only']})")
                kk = str(h["k"])
            else:
                cells += ["invalid", "invalid"]
        L.append(f"| {hid}: {lab} | " + " | ".join(cells) + f" | {kk} |")
    L.append("")
    L.append("k counts every free parameter, including the rotation criterion's own free terms (so a physical model's k includes its rotation spline). All six hypotheses are in the design set for GIMBAL.")
    L.append("")
    for v in names:
        o = V[v]
        hyps = sorted((h for h in o["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"])
        top = hyps[0]
        topp = max(hyps, key=lambda h: h["total_physics_only"])
        L.append(f"At {_fov(o)}: gap to the leader ({top['hypothesis']} testimony-weighted, {topp['hypothesis']} physics-only): " + "; ".join(
            f"{h['hypothesis']} {_f(h['total_testimony_weighted'] - top['total_testimony_weighted'])} / "
            f"{_f(h['total_physics_only'] - topp['total_physics_only'])}" for h in hyps if h is not top) + ".")
        L.append("")

    # ---------------------------------------------------------------- best fit
    L.append("## Best-fit object")
    L.append("")
    L.append("Range is free for every hypothesis (within its prior), so it is a fitted result here, not an input. Values are means over the clip; \"stop/reverse\" says whether the fitted ground velocity reverses direction.")
    L.append("")
    for v in names:
        o = V[v]
        hyps = sorted((h for h in o["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"])
        L.append(f"### {_fov(o)} field of view")
        L.append("")
        L.append("| Hypothesis | Fit | Range (nmi) | Altitude (ft) | Air speed (kt) | Ground speed (kt, min) | Ground track (deg) | Vertical speed (ft/min) | Stop/reverse | Jet heading (deg) | Turn-rate offset (sigma) | Jet pitch (deg) | Params at a prior bound |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for h in hyps:
            for tag, d, p, bnd in (("testimony-weighted", h["derived"], h["params_testimony_weighted_fit"], h["params_at_bound"]),
                                   ("physics-only", h.get("derived_physics_only_fit", h["derived"]), h["params_physics_only_fit"],
                                    h.get("params_at_bound_physics_only_fit", []))):
                L.append(f"| {h['hypothesis']} | {tag} | {_f(d['range_nmi_mean'], 1)} | {_f(d['altitude_ft_mean'], 0)} | {_f(d['air_speed_kt'], 0)} | "
                         f"{_f(d['ground_speed_kt'], 0)} ({_f(d['min_ground_speed_kt'], 0)}) | {_f(d['ground_track_deg'], 0)} | {_f(d['vertical_speed_fpm'], 0)} | "
                         f"{_f(d['stop_reverse'])} | {_f(p['jet_heading_deg'], 0)} | {_f(p.get('turn_rate_z'), 2)} | {_f(p.get('jet_pitch_deg'), 1)} | "
                         f"{_bounds(h, d, bnd)} |")
        L.append("")
    L.append("All fitted parameters (both fits, both fields of view) are in `results.json`.")
    L.append("")

    # ---------------------------------------------------------------- per criterion
    L.append("## Per-criterion log-likelihoods (testimony-weighted fit)")
    L.append("")
    for v in names:
        o = V[v]
        hyps = sorted((h for h in o["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"])
        L.append(f"### {_fov(o)}")
        L.append("")
        crits = list(hyps[0]["criteria"].keys())
        L.append("| Criterion | Weight | " + " | ".join(h["hypothesis"] for h in hyps) + " |")
        L.append("|---|---|" + "---|" * len(hyps))
        for c in crits:
            key = "line_of_sight" if c.startswith("line_of_sight") else c
            wt = o["weights"].get(key, 1.0) if c not in ("prior", "complexity_penalty") else 1.0
            L.append(f"| {_lab(c, o, CRIT_NAMES_V)} | {_f(wt, 1)} | " + " | ".join(_f(h["criteria"].get(c)) for h in hyps) + " |")
        L.append("")
        for c in _zero(o):
            L.append(f"- {CRIT_NAMES_V.get(c, c)} at {_fov(o)}: shown but weight 0 ({_why(c, o)}), so it enters no total.")
        L.append("")

    # ---------------------------------------------------------------- sensitivity
    _added_back(L, {v: (V[v], sorted((h for h in V[v]["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"]))
                    for v in names}, {v: _fov(V[v]) for v in names}, CRIT_NAMES_V)
    open_size = [v for v in names if "size_trend" not in _zero(V[v]) and "brightness_trend" in _zero(V[v])]
    if open_size:
        L.append("### Sensitivity: the apparent-size criterion removed where it is in the totals")
        L.append("")
        L.append("Open item (REVIEW-M3, section 4): where D-016 finds the blob resolved, the size criterion is in the totals, but in the black-hot segment the blob is the same clipped blob that failed the brightness audit, and the glare models' size prediction uses the measured brightness. D-016 does not cover saturation, so the totals without the size row are shown (testimony-weighted fit values; not refitted).")
        L.append("")
        L.append("| Hypothesis | " + " | ".join(f"{_fov(V[v])} weighted / physics, without size" for v in open_size) + " |")
        L.append("|---|" + "---|" * len(open_size))
        for hid in ids:
            cells = []
            for v in open_size:
                h = next(x for x in V[v]["hypotheses"] if x["hypothesis"] == hid)
                if not h["valid"]:
                    cells.append("invalid")
                    continue
                x = h["criteria"].get("size_trend", 0.0)
                tw = h["total_testimony_weighted"] - x
                cells.append(f"{_f(tw)} / {_f(tw - V[v]['weights']['testimony'] * h['criteria'].get('testimony', 0.0))}")
            L.append(f"| {hid} | " + " | ".join(cells) + " |")
        L.append("")

    # ---------------------------------------------------------------- rotation
    L.append("## The rotation test")
    L.append("")
    img = _rotation_plot(res, ROOT / "docs" / "results" / f"{case}_rotation.png")
    for v in names:
        o = V[v]
        rc = o["rotation_check"]
        hy = {e["hypothesis"]: e for e in o["hypotheses"] if e["valid"]}
        n_tot = o["n_eff_total"]
        rows = sorted(rc["hypotheses"].items(), key=lambda kv: -_net_rotation(kv[1], n_tot))
        L.append(f"### {_fov(o)}")
        L.append("")
        L.append("| Hypothesis | Kind | Free rotation terms | Rotation log-likelihood | After its own penalty | Residual RMS (deg) | Largest residual (deg) | Glare offset (deg) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for k, h in rows:
            L.append(f"| {k} | {h['kind']} | {h['free_terms']} ({h['model_terms']} model + shared) | {_f(h['loglik_scaled'])} | "
                     f"{_f(_net_rotation(h, n_tot))} | {_f(h['resid_rms_deg'], 2)} | {_f(h['resid_max_abs_deg'], 1)} | {_f(h['offset_deg'], 1)} |")
        L.append("")
        glare = [(k, h) for k, h in rc["hypotheses"].items() if h["kind"] == "glare"]
        phys = [(k, h) for k, h in rc["hypotheses"].items() if h["kind"] == "physical"]
        bg = max(glare, key=lambda kv: _net_rotation(kv[1], n_tot)) if glare else None
        bp = max(phys, key=lambda kv: _net_rotation(kv[1], n_tot)) if phys else None
        steps = rc["measured_steps"]
        L.append("Measured steps (found from the orientation series alone, no model): " +
                 ", ".join(f"f{s['frame']} ({_f(s['change_deg'], 0)} deg)" for s in steps) +
                 ". The findings log lists window centres 728, 824, 877, 908 and 974 from the extraction's own step finder; f866 to f920 is a fast continuous turn rather than a clean step, which this finder splits.")
        L.append("")
        if bg and bp:
            L.append("Residual jump left at each step (mean residual 5 to 20 frames after minus 5 to 20 before; 0 means the model reproduces the step):")
            L.append("")
            L.append("| Step frame | Measured change (deg) | " + f"{bg[0]} glare, smooth derotation | " + f"{bp[0]} physical spline |")
            L.append("|---|---|---|---|")
            for i, s_ in enumerate(steps):
                L.append(f"| {s_['frame']} | {_f(s_['change_deg'], 1)} | {_f(bg[1]['steps'][i]['jump_left_deg'], 1)} | {_f(bp[1]['steps'][i]['jump_left_deg'], 1)} |")
            L.append("")
        if bg and "deadband" in bg[1]:
            db = bg[1]["deadband"]
            b = db["best"]
            nb = len([x for x in b["steps_predicted"] if x >= db["coarse_window_start_frame"]])
            L.append(f"Step timing (diagnostic, not in any total). Sitrec's model as specified has a smooth pod roll, so it predicts no steps. To test whether steps follow from the geometry, the pod roll was held by a deadband controller (it stays put until the error exceeds a threshold, then jumps; one extra parameter, not in Sitrec), scanned over its threshold, two error measures (pointing error = sin(ball pitch) x roll error, or roll error itself) and with or without re-centring past the target, on {bg[0]}'s best-fit sight line. "
                     f"The best setting overall ({b['metric']}{', re-centring' if b['reflect'] else ''}, threshold {_f(b['threshold'], 1)}) makes {nb} small steps from f{db['coarse_window_start_frame']} on, i.e. it tracks almost continuously, and changes the rotation score by {_f(db['gain_vs_smooth_after_one_parameter_penalty'])} after its penalty.")
            L.append("")
            c = db.get("best_coarse")
            if c:
                cm = db["best_coarse_step_match"]
                cs = [x for x in c["steps_predicted"] if x >= db["coarse_window_start_frame"]]
                L.append(f"Restricted to settings that make about as many steps as were measured (between half and twice as many from f{db['coarse_window_start_frame']} on), the best is {c['metric']}{', re-centring' if c['reflect'] else ''}, threshold {_f(c['threshold'], 1)}: predicted pod-roll steps at f" + ", f".join(str(x) for x in cs) +
                         f". {cm['n_matched']} of the {cm['n_measured']} measured steps have a predicted step within {cm['tolerance_frames']} frames (nearest: " +
                         ", ".join(f"f{m} to f{q} ({int(q) - int(m):+d})" for m, q in cm["nearest_predicted"].items() if q is not None) +
                         f"); {cm['n_predicted_unmatched']} predicted steps have no measured counterpart. Rotation log-likelihood {_f(c['loglik_scaled'])} against {_f(bg[1]['loglik_scaled'])} for the smooth derotation (residual RMS {_f(c['resid_rms_deg'], 2)} deg); change after one parameter's penalty {_f(db['best_coarse_gain_vs_smooth_after_one_parameter_penalty'])}.")
                L.append("")
                try:
                    summ = json.loads((derived_dir(case) / "image_track_summary.json").read_text(encoding="utf-8"))
                    ref = [int(x["center_frame"]) for x in summ.get("orientation_steps", []) if abs(x["obj_angle_change_deg"]) > 5]
                except (OSError, KeyError, ValueError):
                    ref = []
                if ref and cs:
                    near = {m: min(cs, key=lambda q: abs(q - m)) for m in ref}
                    L.append("Against the findings-log step frames (" + ", ".join(str(m) for m in ref) + "): nearest predicted step " +
                             ", ".join(f"f{m}: f{q} ({q - m:+d})" for m, q in near.items()) + ".")
                    L.append("")
            else:
                L.append("No controller setting made a step count comparable to the measured one.")
                L.append("")
            L.append("Best of each controller variant (any step count): " + "; ".join(
                f"{k} threshold {_f(x['threshold'], 1)}: log-likelihood {_f(x['loglik_scaled'])}" for k, x in db["by_metric"].items()) + ".")
            L.append("")
        if bg and bp:
            gnet, pnet = _net_rotation(bg[1], n_tot), _net_rotation(bp[1], n_tot)
            better = "the free physical rotation" if pnet > gnet else "the glare derotation"
            jmax = max(abs(x["jump_left_deg"] or 0.0) for x in bg[1]["steps"]) if bg[1]["steps"] else 0.0
            txt = (f"**In plain words ({_fov(o)}):** Sitrec's glare model, the pod geometry with one fitted offset, reproduces the overall sweep of the image rotation "
                   f"(residual RMS {_f(bg[1]['resid_rms_deg'], 1)} deg; fitted offset {_f(bg[1]['offset_deg'], 1)} deg, against Sitrec's own starting value of 57.7 deg). "
                   f"With the pod roll following the geometry its rotation is smooth, so it leaves residual jumps of up to {_f(jmax, 0)} deg at the measured step frames. "
                   f"A physical object given a free smooth rotation fits with residual RMS {_f(bp[1]['resid_rms_deg'], 1)} deg using {bp[1]['model_terms']} knots. "
                   f"After each pays for its own free terms, {better} scores better on this criterion by {_f(abs(pnet - gnet))} log units.")
            db = bg[1].get("deadband")
            if db and db.get("best_coarse"):
                cm = db["best_coarse_step_match"]
                gain = db["best_coarse_gain_vs_smooth_after_one_parameter_penalty"]
                txt += (f" Making the pod roll step (a deadband controller, one extra parameter, tuned to make about the measured number of steps) puts a predicted step within {cm['tolerance_frames']} frames of "
                        f"{cm['n_matched']} of the {cm['n_measured']} measured steps, with {cm['n_predicted_unmatched']} predicted steps that have no measured counterpart, and changes the rotation score by "
                        f"{_f(gain)} after its penalty" + ((", which does " + ("" if gnet + max(gain, 0.0) >= pnet else "not ") +
                                                            "close the gap to the free physical rotation.") if pnet > gnet else "."))
            if pnet > gnet:
                txt += (" So on this criterion alone the rotation does not single out a glare fixed in the optics: what the glare model gets right is the size and"
                        " direction of the total turn and the fast turn near the azimuth crossing, and what it misses is the step timing.")
            else:
                txt += (" So on this criterion the pod geometry predicts the rotation better than a free rotation can, even after the free rotation fits its own"
                        " shape; the step timing is the part it does not capture.")
            L.append(txt)
            L.append("")
    if img:
        L.append(f"![GIMBAL rotation: measured orientation and the best glare and physical fits]({img})")
        L.append("")

    # ---------------------------------------------------------------- testimony
    L.append("## Testimony claims that bear on this video")
    L.append("")
    L.append("Scored by `solve/testimony.py` (the same claims for every hypothesis; firsthand weight 1.0, relayed 0.5; recalled numbers never tighter than 25 percent). Each cell: predicted value, weighted log-likelihood (testimony-weighted fit).")
    L.append("")
    for v in names:
        o = V[v]
        hyps = sorted((h for h in o["hypotheses"] if h["valid"]), key=lambda h: h["rank_testimony_weighted"])
        rows = {}
        for h in hyps:
            for r in h.get("testimony_rows", []):
                rows.setdefault((r["claim_id"], r["quantity"]), {})[h["hypothesis"]] = r
        L.append(f"### {_fov(o)}")
        L.append("")
        L.append("| Claim | Quantity | Claimed | " + " | ".join(h["hypothesis"] for h in hyps) + " |")
        L.append("|---|---|---|" + "---|" * len(hyps))
        for (cid, q), per in rows.items():
            iv = next(iter(per.values()))["interval"]
            ivs = f"{_f(iv.get('lo'), 0)} to {_f(iv.get('hi'), 0)} ({_f(iv.get('sigma'), 1)})" if "lo" in iv else str(iv.get("value", iv))
            cells = []
            for h in hyps:
                r = per.get(h["hypothesis"])
                pv = r["predicted_value"] if r else None
                if isinstance(pv, list):
                    pvs = " / ".join(_f(x, 0) for x in pv)
                elif isinstance(pv, (int, float)) and not isinstance(pv, bool):
                    pvs = _f(pv, 1)
                else:
                    pvs = _f(pv)
                cells.append(f"{pvs}, {_f(r['weighted_loglik'], 1)}" if r else "n/a")
            L.append(f"| {cid} | {q} | {ivs} | " + " | ".join(cells) + " |")
        L.append("| Total (before weight) | | | " + " | ".join(_f(h["criteria"].get("testimony")) for h in hyps) + " |")
        L.append("")

    # ---------------------------------------------------------------- range curve
    L.append("## Range curve from the angles alone")
    L.append("")
    L.append("With no range on screen, a constant-velocity object is fitted at each assumed range to the azimuth and elevation readouts (and the turn-rate band). Image cues and testimony are NOT used here. This shows what the sight lines alone allow.")
    L.append("")
    L.append("| Assumed range (nmi) | " + " | ".join(f"{_fov(V[v])}: air / ground speed (kt), altitude (ft), sight-line log-likelihood" for v in names) + " |")
    L.append("|---|" + "---|" * len(names))
    curves = {v: {r["range_nmi"]: r for r in V[v].get("range_curve_angles_only", [])} for v in names}
    for rng in sorted(curves[names[0]]):
        cells = []
        for v in names:
            r = curves[v].get(rng)
            cells.append(f"{_f(r['air_speed_kt'], 0)} / {_f(r['ground_speed_kt'], 0)}, {_f(r['altitude_ft_mean'], 0)}, {_f(r['line_of_sight_loglik'], 1)}"
                         if r and r.get("valid") else "no solution")
        L.append(f"| {_f(rng, 0)} | " + " | ".join(cells) + " |")
    L.append("")

    # ---------------------------------------------------------------- conditions
    L.append("## Conditions each result depends on")
    L.append("")
    L.append("- **Field of view** (0.35 or 0.7 deg): changes the cloud-derived turn rate and therefore the jet's path, so every sight line. Reported separately; the documentation-based consensus is 0.35 deg.")
    env = first["environment"]
    if str(env["source"]).startswith("placeholder"):
        L.append(f"- **Wind and temperature**: PLACEHOLDER {env['source']} (wind uncertainty {_f(env['wind_sigma_kt'], 0)} kt), ISA temperature at the jet. ERA5 replaces it when `data/weather/era5_gimbal_gofast_profiles.csv` exists; the balloon, slow-mover and wind-related testimony terms move with it.")
    else:
        L.append(f"- **Wind and temperature**: {env['source']}, wind uncertainty {_f(env['wind_sigma_kt'], 0)} kt, jet-level temperature ISA {env['dT_jet_K']:+.1f} K (TAS from Mach uses it). The ERA5 time is nominal: the date and hour of the recording are not certain (the file metadata points to 01/25/2015 near 02 to 03 UTC; the release lists 01/21/2015). The balloon, slow-mover and wind-related testimony terms move with the wind.")
    trs = derived_dir(case) / "turn_rate_era5_summary.json"
    if trs.exists():
        te = json.loads(trs.read_text(encoding="utf-8"))
        e0 = next(iter(te.values()))["era5_nominal"]
        L.append("- **Turn-rate derivation inputs** (REVIEW-M3 item 3): the cloud-derived turn rate now uses ERA5 at "
                 f"{e0['time_utc']}Z: jet-level wind {_f(e0['jet_wind'][1], 0)} kt from {_f(e0['jet_wind'][0], 0)}, cloud-deck wind "
                 f"{_f(e0['cloud_wind'][1], 0)} kt from {_f(e0['cloud_wind'][0], 0)} (deck 11,740 ft nominal), TAS from Mach at ISA {e0['dT_jet_K']:+.1f} K; "
                 "the band draws the time over 01/24 18Z to 01/25 06Z. Against the placeholder inputs the history moved by " +
                 ", ".join(f"{_f(x['nominal_change_vs_placeholder_deg_s']['rms_core'], 4)} deg/s rms at {x['fov_deg']} deg" for x in te.values()) +
                 " and the band's median half-width went from " +
                 ", ".join(f"{_f(x['band_halfwidth_core_median_deg_s']['placeholder'], 3)} to {_f(x['band_halfwidth_core_median_deg_s']['era5'], 3)} deg/s at {x['fov_deg']} deg" for x in te.values()) +
                 ". The jet's initial heading inside the inversion is still a draw in 295 to 335 deg (not on screen).")
    else:
        L.append("- **Turn-rate derivation inputs**: placeholder winds and ISA temperature (ERA5 recomputation not found).")
    L.append("- **Jet heading**: not on screen; fitted for every hypothesis. Testimony quantities that depend on direction (motion against the wind) inherit that freedom.")
    L.append("- **Turn rate**: the lab's cloud-derived history and its Monte Carlo band (cloud deck height, texture distance, image scale, ERA5 winds and temperature over a 12-hour window, and the jet's initial heading inside it). The horizon-bar bank is used only for the image horizon and pod roll, where the cloud motion's direction confirms it.")
    L.append("- **Jet pitch**: a shared nuisance (Sitrec's 3.6 deg, scaled by 1/cos(bank) as Sitrec does). Near the end of the clip the pod looks within a few degrees of its roll axis, so the predicted glare rotation there is sensitive to pitch and to the azimuth inside its whole-degree interval; both are fitted, the same way for every glare model.")
    L.append("- **Rotation measurement**: the blob's major-axis angle at the high threshold, noise about 0.9 deg; one shared offset allows a white-hot / black-hot bias. Pixel aspect (frames about 5 percent wide) slightly flattens measured angles and is not corrected (it changes the angles by under 2 deg at 45 deg).")
    for c, txt in (("brightness_trend", "Brightness trend"), ("size_trend", "Apparent size")):
        st = [f"weight 0 at {_fov(V[v])}" if c in _zero(V[v]) else f"in the totals at {_fov(V[v])}" for v in names]
        why = list(dict.fromkeys(_why(c, V[v]) for v in names if c in _zero(V[v]))) or [WHY_ZERO[c]]
        L.append(f"- **{txt}**: " + ", ".join(st) + f" (where weight 0: {'; '.join(why)}; see `docs/results/REVIEW-M3.md`).")
    L.append("- **Testimony**: the binding Gaussian edge grows quadratically outside a claim's interval, so a single distant memory can dominate a total; the physics-only column is the reading without it.")
    L.append("")
    L.append("## How to read this, and its limits")
    L.append("")
    L.append("- Likelihoods, not verdicts. No prior probability is put on any class of explanation; readers can add their own.")
    L.append("- Compare differences between hypotheses within one field of view, not absolute values, and not across fields of view (the jet's path differs).")
    L.append("- Interpretations made where the design was silent: as for GOFAST (n_eff from the data's autocorrelation; the BIC n is the sum of the physics criteria's n_eff; normal-prior nuisances enter through their log prior); plus, for GIMBAL, the cloud motion enters through the turn-rate band, the rotation noise is the scatter about a running median, and the physical rotation spline's knot count is chosen by the same penalized likelihood.")
    for v in names:
        rl = _recovery_lines(case, v)
        if len(rl) > 1:
            rl[0] = rl[0].replace("(M3.4,", f"(M3.4, {_fov(V[v])},")
        L += rl
    L.append("- Discriminators for the top pairs (M3.6) are not written yet.")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv):
    case = argv[1] if len(argv) > 1 else "gofast"
    out = ROOT / "docs" / "results" / f"{case}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    res = json.loads((derived_dir(case) / "results.json").read_text(encoding="utf-8"))
    text = build_variants(case) if "variants" in res else build(case)
    assert "—" not in text  # no em dashes in reader-facing output
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
