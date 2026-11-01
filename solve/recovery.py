"""M3.4 model-recovery test: which hypotheses can this data separate, even in principle?

For a case (and one sensor variant), synthetic observations are generated from each hypothesis
at three parameter sets, then the full scorer fits EVERY hypothesis to each synthetic data set
(physics-only total, testimony weight 0, the same single scoring path as the real data), and the
winner is recorded. The result is a confusion matrix: rows = the hypothesis that generated the
data, columns = the hypothesis that wins.

Parameter sets per generating hypothesis (all within its own priors):
  best   its physics-only best fit to the real data (results.json);
  near   its best fit with the range held at 0.6 x the best-fit mean range (clipped into its prior);
  far    the same at 1.6 x.
If a held range breaks the hypothesis's own constraints (constraint log prior below -2), the factor is pulled
toward 1 (0.8 / 1.25, then 0.9 / 1.1). The remaining parameters are refitted to the real data at
that range, so each set is the hypothesis's best showing at another distance.

Synthetic data use the real case's sampling and sensor behavior, identically for every generator:
  - az / el readouts: the predicted angle plus N(0, angle_sigma_deg) noise, rounded by the case's
    display rounding (D-016) to whole degrees, on the case's 6-frame display update frames only
    (between updates the display holds); the anchor reads the synthetic readout;
  - range and Vc readouts (GOFAST): predicted value plus noise, quantized to the 0.1 nmi and 10 kt
    display steps on every frame;
  - image series (size, brightness, ocean motion, rotation): the model's prediction plus the REAL
    measurement noise, i.e. the real series' residual about its own smooth fit (cubic per polarity
    segment; rotation: about a 9-frame running median), circularly shifted by a random offset per
    trial, which keeps the measured scatter, heavy tails and autocorrelation;
  - rotation: the generating model's own best representation of the measured rotation (glare: the
    pod derotation plus its fitted offset; physical: the horizon plus its fitted smooth spline);
  - the measured turn-rate history and its band stay as measured (the generator's turn_rate_z sets
    the jet path); n_eff and sigmas are the real case's (same noise model by construction).
Criteria with weight 0 on the case (D-016, REVIEW-M3 Rule B) are generated but carry no weight, as
on the real data.

Fitting uses the real-data runs' settings (solve/scoring.yaml), the same for every hypothesis; the seed
never depends on the hypothesis. Each row also carries the generating model's total at its true
parameters on that synthetic data set (a check on the optimizer: its own fit should reach it).

CLI: python -m solve.recovery gimbal fov035 [--procs 12] [--trials 2]
     python -m solve.recovery gofast "" [--procs 12] [--trials 2]
     python -m solve.recovery --report   (docs/results/recovery.md)
Writes data/derived/<case>/recovery_sets[_<variant>].json and data/derived/<case>/recovery.csv (all variants).
"""

from __future__ import annotations

import copy
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import frames as F
from . import likelihoods as L
from . import score as S
from .case_data import load_case, scoring_config

ROOT = Path(__file__).resolve().parents[1]
FIT_KW: dict = {}   # the real-data runs' fit settings (solve/scoring.yaml), the same for every hypothesis
SET_FACTORS = [(0.6, 1.6), (0.8, 1.25), (0.9, 1.1)]
SEED = 20261101


# ----------------------------------------------------------------------------- helpers

def _hyps() -> dict:
    return {h.id: h for h in S.load_hypotheses()}


def _results(case_name: str, variant: str) -> dict:
    out = json.loads((ROOT / "data" / "derived" / case_name / "results.json").read_text(encoding="utf-8"))
    return out["variants"][variant] if variant else out


def _range_param(specs) -> str | None:
    names = [s.name for s in specs]
    return "range_ref_nmi" if "range_ref_nmi" in names else None


def _noise_pool(case) -> dict:
    """Real measurement noise per series: residual about its own smooth fit, scaled to the case's sigma."""
    deg = int(scoring_config()["autocorrelation"]["smooth_degree"])
    pool = {}
    for key, s in case.series.items():
        r = np.full(len(s.frames), np.nan)
        for sg in np.unique(s.segment):
            m = s.segment == sg
            if key == "rotation":
                y = pd.Series(s.obs[m])
                r[m] = (y - y.rolling(9, center=True, min_periods=1).median()).to_numpy()
            else:
                r[m] = L.smooth_residual(case.t[s.frames[m]], s.obs[m], deg)
        r = np.nan_to_num(r - np.nanmean(r))
        sd = float(np.std(r))
        pool[key] = r * (s.sigma / sd) if sd > 0 else r
    return pool


def _quantize(x: np.ndarray, step: float, rounding: str) -> np.ndarray:
    if rounding == "floor":
        return np.floor(x / step) * step + 0.5 * step   # the loader stores a floored readout as its interval centre
    return np.round(x / step) * step


def synthetic_case(case, hyp, params: dict, rng: np.random.Generator):
    """A copy of the case whose observations are drawn from `hyp` at `params` (see module docstring)."""
    sc = scoring_config()["noise"]
    rounding = str(case.cfg.get("display_rounding", "round"))
    syn = copy.deepcopy(case)
    pred = S.predict(case, hyp, params)
    if not pred.valid:
        raise ValueError(f"generator invalid: {pred.reason}")
    pool = _noise_pool(case)

    # Readouts.
    for key in ("azimuth", "elevation"):
        r = syn.readouts[key]
        arr = pred.az if key == "azimuth" else pred.el
        r.obs = _quantize(arr[r.frames] + rng.normal(0.0, sc["angle_sigma_deg"], len(r.frames)), r.step,
                          rounding if key in ("azimuth", "elevation") else "round")
        full = np.full(len(case.t), np.nan)
        full[r.frames] = r.obs
        full = pd.Series(full).ffill().bfill().to_numpy()
        if key == "azimuth":
            syn.az_read = full
        else:
            syn.el_read = full
    if "range" in syn.readouts:
        r = syn.readouts["range"]
        r.obs = _quantize(pred.range_m[r.frames] / F.NMI + rng.normal(0.0, sc["range_sigma_nmi"], len(r.frames)),
                          r.step, "round")
    if "closure" in syn.readouts:
        r = syn.readouts["closure"]
        r.obs = _quantize(pred.closure_mps[r.frames] / F.KT
                          + rng.normal(0.0, sc["closure_step_kt"] / np.sqrt(12.0), len(r.frames)), r.step, "round")

    # Image series: prediction plus the real noise, circularly shifted.
    def noisy(key, model):
        s = syn.series[key]
        e = np.roll(pool[key], int(rng.integers(0, len(s.frames))))
        return np.asarray(model, float) + e

    if "brightness_trend" in syn.series:
        s = syn.series["brightness_trend"]
        s.obs = noisy("brightness_trend", pred.brightness_log[s.frames])
        bl = np.array(syn.brightness_log_all, float)
        bl[s.frames] = s.obs
        syn.brightness_log_all = bl
    pred2 = S.predict(syn, hyp, params)       # the glare size model reads the (synthetic) brightness
    if "size_trend" in syn.series:
        s = syn.series["size_trend"]
        s.obs = noisy("size_trend", pred2.size_log[s.frames])
    if "background_motion" in syn.series:
        s = syn.series["background_motion"]
        s.obs = noisy("background_motion", np.nan_to_num(pred2.background_px[s.frames]))
    if "rotation" in syn.series:
        _, _, det = S.rotation_terms(case, pred)      # the generator's own fit to the measured rotation
        s = syn.series["rotation"]
        s.obs = noisy("rotation", det["fitted"])
    syn.__dict__.pop("_jet_model", None)
    syn.flags = list(case.flags) + ["synthetic data (M3.4 recovery)"]
    # The generating parameters re-expressed against the synthetic readout at the reference frame (the anchor
    # offsets are relative to the displayed whole degree): a diagnostic of what the true model scores.
    i = case.ref_frame
    truth = dict(params)
    if "anchor_daz_deg" in truth:
        truth["anchor_daz_deg"] = float(pred.az[i] - syn.az_read[i])
    if "anchor_del_deg" in truth:
        truth["anchor_del_deg"] = float(pred.el[i] - syn.el_read[i])
    syn.__dict__["_truth_params"] = truth
    return syn


def run_dataset(task: dict) -> list:
    """One synthetic data set: generate, then fit every hypothesis (physics-only)."""
    case = load_case(task["case"], variant=task["variant"] or None)
    hyps = _hyps()
    gen = hyps[task["generator"]]
    rng = np.random.default_rng(task["seed"])
    syn = synthetic_case(case, gen, task["params"], rng)
    try:
        truth_total = float(S.score(syn, gen, syn.__dict__["_truth_params"], testimony_weight=0.0).attrs["total_physics_only"])
    except ValueError:
        truth_total = float("nan")
    rows = []
    for hid, h in hyps.items():
        fr = S.fit(syn, h, testimony_weight=0.0, seed=SEED, **FIT_KW)
        rows.append({"case": task["case"], "variant": task["variant"], "generator": task["generator"],
                     "set": task["tag"], "generator_range_nmi": task["range_nmi_mean"], "trial": task["trial"],
                     "fitted": hid, "valid": bool(fr.get("valid")),
                     "total_physics_only": fr.get("total_physics_only") if fr.get("valid") else np.nan,
                     "k": fr.get("k") if fr.get("valid") else np.nan,
                     "fitted_range_nmi": fr["prediction"].scalars["range_nmi_mean"] if fr.get("valid") else np.nan,
                     "generator_total_at_true_params": truth_total})
    return rows


def confusion(df: pd.DataFrame) -> pd.DataFrame:
    """Rows: generator; columns: winning hypothesis (count of synthetic data sets)."""
    win = (df[df["valid"]].sort_values("total_physics_only", ascending=False)
           .groupby(["generator", "set", "trial"]).head(1))
    return pd.crosstab(win["generator"], win["fitted"]).reindex(sorted(df["generator"].unique()), fill_value=0)


def main(argv: list[str]) -> int:
    case_name = argv[1]
    variant = argv[2] if len(argv) > 2 else ""
    procs = int(argv[argv.index("--procs") + 1]) if "--procs" in argv else 12
    trials = int(argv[argv.index("--trials") + 1]) if "--trials" in argv else 1
    d = ROOT / "data" / "derived" / case_name
    sets_path = d / f"recovery_sets{'_' + variant if variant else ''}.json"
    if "--reuse-sets" in argv and sets_path.exists():
        sets = json.loads(sets_path.read_text(encoding="utf-8"))["sets"]
    else:
        hyp_ids = sorted(_hyps())
        with Pool(min(procs, len(hyp_ids))) as pool:
            parts = pool.starmap(_sets_one, [(case_name, variant, hid) for hid in hyp_ids])
        sets = {k: v for p in parts for k, v in p.items()}
        sets_path.write_text(json.dumps({"case": case_name, "variant": variant, "sets": sets}, indent=1, default=float) + "\n",
                             encoding="utf-8")
        print(f"wrote {sets_path}", flush=True)
    tasks = []
    k = 0
    for gid, ss in sorted(sets.items()):
        for st in ss:
            for t in range(trials):
                tasks.append({"case": case_name, "variant": variant, "generator": gid, "tag": st["tag"],
                              "params": st["params"], "range_nmi_mean": st["range_nmi_mean"], "trial": t,
                              "seed": SEED + 1000 * k + t})
            k += 1
    rows = []
    part = d / f"recovery_part_{variant or 'default'}.csv"
    with Pool(procs) as pool:
        for r in pool.imap_unordered(run_dataset, tasks):
            rows += r
            pd.DataFrame(rows).to_csv(part, index=False, float_format="%.6g")
            print(f"{len(rows) // len(_hyps())}/{len(tasks)} data sets done", flush=True)
    df = pd.DataFrame(rows)
    best = df[df["valid"]].groupby(["generator", "set", "trial"])["total_physics_only"].transform("max")
    df["winner"] = df["valid"] & (df["total_physics_only"] == best.reindex(df.index))
    out = d / "recovery.csv"
    if out.exists():   # keep other sensor variants' rows
        old = pd.read_csv(out, keep_default_na=False, na_values=[""])
        old["variant"] = old["variant"].astype(object).fillna("").astype(str)
        df = pd.concat([old[old["variant"] != variant], df], ignore_index=True)
    df.to_csv(out, index=False, float_format="%.6g")
    part.unlink(missing_ok=True)
    print(confusion(df[df["variant"].astype(object).fillna("").astype(str) == variant]).to_string())
    return 0


def _sets_one(case_name: str, variant: str, hid: str) -> dict:
    allsets = param_sets_for(case_name, variant, hid)
    return {hid: allsets}


def param_sets_for(case_name: str, variant: str, hid: str) -> list:
    """The three parameter sets of one generating hypothesis (see the module docstring)."""
    case = load_case(case_name, variant=variant or None)
    res = _results(case_name, variant)
    e = next(x for x in res["hypotheses"] if x["hypothesis"] == hid)
    if not e.get("valid"):
        return []
    h = _hyps()[hid]
    best = dict(e["params_physics_only_fit"])
    sets = [{"tag": "best", "params": best, "range_nmi_mean": e["derived_physics_only_fit"]["range_nmi_mean"]}]
    specs = S.param_specs(case, h)
    rp = _range_param(specs)
    spec = {s.name: s for s in specs}.get(rp)
    if rp is None:
        return sets
    for tag, j in (("near", 0), ("far", 1)):
        for fac in SET_FACTORS:
            r = float(np.clip(best[rp] * fac[j], spec.lo * 1.001, spec.hi * 0.999))
            fr = S.fit(case, h, testimony_weight=0.0, fixed={rp: r}, seed=SEED, **FIT_KW)
            if not fr.get("valid"):
                continue
            if S.constraint_log_prior(h, fr["prediction"]) > -2.0:
                sets.append({"tag": tag, "params": dict(fr["params"]),
                             "range_nmi_mean": fr["prediction"].scalars["range_nmi_mean"], "factor": fac[j]})
                break
    return sets


# ----------------------------------------------------------------------------- report

def _physics_key(h, case=None) -> tuple:
    """What a model computes on this case (emitter physics and velocity use), from the model registry, not the
    name. Emitter physics only counts where a criterion that sees it carries weight: the size model through the
    size criterion, the glare flag through the rotation criterion."""
    from . import models as M
    m = M.MODELS[h.model]
    size_on = case is None or float(case.weight_overrides.get("size_trend", 1.0)) != 0.0
    rot_on = case is None or ("rotation" in case.criteria and float(case.weight_overrides.get("rotation", 1.0)) != 0.0)
    return (getattr(m, "size_model", "") if size_on else "", bool(getattr(m, "glare", False)) and rot_on,
            bool(getattr(m, "use_air_velocity", False)), h.model == "spline_path")


def _fmt_ids(ids) -> str:
    ids = sorted(ids)
    return ids[0] if len(ids) == 1 else ", ".join(ids[:-1]) + " and " + ids[-1]


def report_lines(case_name: str, variant: str, label: str) -> list:
    p = ROOT / "data" / "derived" / case_name / "recovery.csv"
    df = pd.read_csv(p, keep_default_na=False, na_values=[""])
    df["variant"] = df["variant"].astype(object).fillna("").astype(str)
    df = df[df["variant"] == variant]
    hyps = _hyps()
    case = load_case(case_name, variant=variant or None)
    ids = sorted(set(df["fitted"]))
    key = ["generator", "set", "trial"]
    L = [f"## {label}", ""]
    sp = ROOT / "data" / "derived" / case_name / f"recovery_sets{'_' + variant if variant else ''}.json"
    sets = json.loads(sp.read_text(encoding="utf-8"))["sets"] if sp.exists() else {}
    if sets:
        L.append("Generating parameter sets (mean range of each set, nmi): " + "; ".join(
            f"{g} " + ", ".join(f"{st['tag']} {st['range_nmi_mean']:.1f}" for st in ss) for g, ss in sorted(sets.items())) + ".")
        L.append("")
    # Margins: how decisively the truth wins or loses (log-likelihood units; 2.3 = factor 10).
    rows = []
    for (g, st, tr), grp in df[df["valid"]].groupby(key):
        grp = grp.sort_values("total_physics_only", ascending=False)
        top = grp.iloc[0]
        second = grp.iloc[1] if len(grp) > 1 else None
        own = grp[grp["fitted"] == g]["total_physics_only"]
        own = float(own.iloc[0]) if len(own) else float("nan")
        rows.append({"generator": g, "set": st, "trial": tr, "winner": top["fitted"],
                     "margin_vs_runner_up": float(top["total_physics_only"] - second["total_physics_only"]) if second is not None else float("nan"),
                     "truth_behind_winner": float(top["total_physics_only"] - own),
                     "runner_up": second["fitted"] if second is not None else "",
                     "fit_vs_truth": own - float(grp["generator_total_at_true_params"].iloc[0])
                     if "generator_total_at_true_params" in grp else float("nan")})
    R = pd.DataFrame(rows)
    tab = pd.crosstab(R["generator"], R["winner"]).reindex(index=ids, columns=ids, fill_value=0)
    L.append("Confusion matrix (counts of synthetic data sets; rows: the hypothesis that made the data; columns: the winner on the physics-only total; an exact or near tie goes to whichever fit came out ahead, so read ties from the margins below):")
    L.append("")
    L.append("| Data made by | " + " | ".join(ids) + " | correct |")
    L.append("|---|" + "---|" * (len(ids) + 1))
    for g in ids:
        n = int(tab.loc[g].sum())
        L.append(f"| {g} | " + " | ".join(str(int(tab.loc[g, c])) for c in ids) + f" | {int(tab.loc[g, g])} of {n} |")
    L.append("")
    L.append("| Data made by | Set | Trial | Winner | Runner-up | Winner's lead over the runner-up | The truth's deficit to the winner | Truth's own fit minus its total at the true parameters |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in R.sort_values(["generator", "set", "trial"]).itertuples():
        L.append(f"| {r.generator} | {r.set} | {r.trial} | {r.winner} | {r.runner_up} | {r.margin_vs_runner_up:.1f} | {r.truth_behind_winner:.1f} | {r.fit_vs_truth:.1f} |")
    L.append("")
    bad = R[R["fit_vs_truth"] < -1.0]
    L.append(f"Optimizer check: in {len(bad)} of {len(R)} data sets the generating model's own fit ended more than 1 log unit below its total at the true parameters" +
             (" (those cells understate the truth; read them as a lower bound on its score)." if len(bad) else "."))
    L.append("")
    # Plain words.
    L.append("In plain words:")
    L.append("")
    for g in ids:
        sub = R[R["generator"] == g]
        if sub.empty:
            continue
        ok = sub[sub["winner"] == g]
        wrong = sub[sub["winner"] != g]
        txt = f"- Data made by {g}: it wins {len(ok)} of {len(sub)}"
        if len(ok):
            txt += f" (lead over the runner-up {ok['margin_vs_runner_up'].min():.1f} to {ok['margin_vs_runner_up'].max():.1f})"
        if len(wrong):
            txt += (f"; otherwise the winner is {_fmt_ids(set(wrong['winner'])).replace(' and ', ' or ')}, with {g} behind by "
                    f"{wrong['truth_behind_winner'].min():.1f} to {wrong['truth_behind_winner'].max():.1f}")
        L.append(txt + ".")
    bst = R[R["set"] == "best"]
    if len(bst):
        wins = {}
        for r in bst.itertuples():
            wins.setdefault(r.winner, set()).add(r.generator)
        L.append("- At the best-fit parameter sets (the synthetic data that look most like the real video), the winner was: " +
                 "; ".join(f"{w} for data made by {_fmt_ids(gs)}" for w, gs in sorted(wins.items())) +
                 ". A hypothesis that wins on data made by several others cannot, by winning on the real data, tell them apart.")
    # Pairs confused (in these trials) vs always separated, and same-physics groups.
    conf = set()
    for r in R.itertuples():
        if r.winner != r.generator:
            conf.add(tuple(sorted((r.winner, r.generator))))
        elif r.runner_up and r.margin_vs_runner_up < 2.3:
            conf.add(tuple(sorted((r.winner, r.runner_up))))
    groups: dict = {}
    for i in ids:
        groups.setdefault(_physics_key(hyps[i], case), []).append(i)
    same = [v for v in groups.values() if len(v) > 1]
    L.append("")
    if conf:
        L.append("- Not separated by this data (a wrong winner, or the true model winning by less than 2.3, a likelihood ratio of 10, at least once): " +
                 "; ".join(f"{a} and {b}" for a, b in sorted(conf)) + ".")
    good = [g for g in ids if len(R[R["generator"] == g]) and
            all((r.winner == g and r.margin_vs_runner_up >= 2.3) for r in R[R["generator"] == g].itertuples())]
    if good:
        L.append("- Recovered every time, by a likelihood ratio of 10 or more over every other hypothesis: " + _fmt_ids(good) +
                 ". Data made by these are told apart from all the others here.")
    else:
        L.append("- No hypothesis was recovered every time by a likelihood ratio of 10 or more.")
    never = [g for g in ids if len(R[R["generator"] == g]) and not (R[R["generator"] == g]["winner"] == g).any()]
    if never:
        L.append("- Never recovered (another hypothesis always won on its data): " + _fmt_ids(never) + ".")
    if same:
        L.append("- Same physics on this case, different priors only (emitter physics counted only where a weighted criterion sees it; such models can differ only where a prior bound or constraint binds, or through the penalty for extra free parameters): " +
                 "; ".join(_fmt_ids(v) for v in same) + ".")
    L.append("")
    return L


def write_report() -> Path:
    L = ["# Model recovery (M3.4): which hypotheses can this data separate?", ""]
    L.append("Generated by `python -m solve.recovery --report` from `data/derived/<case>/recovery.csv` (written by `python -m solve.recovery <case> <variant>`). Design: `docs/design/scoring.md` (binding): a model-recovery test, synthetic data from each hypothesis through the full scorer, shows which hypotheses the data can separate even in principle.")
    L.append("")
    L.append("**Method.** For each hypothesis, synthetic observations were generated at three parameter sets: its physics-only best fit to the real data, and its best fit with the range held at about 0.6 and 1.6 times that (pulled toward 1 where a constraint would break). Each synthetic data set has the real sampling and sensor behavior: whole-degree az / el readouts with the case's display rounding on the 6-frame display updates, the 0.1 nmi and 10 kt range and Vc steps (GOFAST), the real measurement noise of every image series (its own residual, circularly shifted, so its scatter, tails and autocorrelation are kept), and the same weight-0 criteria as the real case. Every hypothesis was then fitted to every data set by the single scoring path (physics-only total, the real runs' fit settings, the same for all; the generating model's total at its true parameters is kept as a check on the optimizer). A modest number of noise draws per set: enough to show the pattern, not to estimate rates.")
    L.append("")
    L.append("Margins are differences of physics-only totals (log-likelihood after the complexity penalty); 2.3 is a likelihood ratio of 10.")
    L.append("")
    for case_name, variant, label in (("gimbal", "fov035", "GIMBAL, 0.35 deg field of view"),
                                      ("gimbal", "fov070", "GIMBAL, 0.7 deg field of view"),
                                      ("gofast", "", "GOFAST")):
        p = ROOT / "data" / "derived" / case_name / "recovery.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p, keep_default_na=False, na_values=[""])
        if (d["variant"].astype(object).fillna("").astype(str) == variant).any():
            L += report_lines(case_name, variant, label)
    L.append("## Limits")
    L.append("")
    L.append("- Few trials per cell: a 1 in a cell is an existence proof that the pair can be confused, not a rate.")
    L.append("- The synthetic data are drawn from each hypothesis's own model, so this tests separability under the lab's sensor model; errors in that model (shared by every hypothesis) are not tested here.")
    L.append("- Testimony is not part of this test (physics-only total).")
    L.append("- GIMBAL at 0.7 deg was not run (next step: python -m solve.recovery gimbal fov070 --trials 2, about 80 minutes on 14 processes; on a shared machine, run it with fewer processes at low priority). At 0.7 deg the resolved size criterion is also in the totals, so the glare and physical groups may separate differently.")
    L.append("")
    text = "\n".join(L) + "\n"
    assert "—" not in text
    out = ROOT / "docs" / "results" / "recovery.md"
    out.write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        print(write_report())
        raise SystemExit(0)
    raise SystemExit(main(sys.argv))
