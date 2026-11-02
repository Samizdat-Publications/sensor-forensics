"""Per-hypothesis curves over range (REVIEW-M3 Rule K, CP-04 must-fix d).

For every hypothesis with a range parameter (range_ref_nmi, the slant range at the case's reference
frame), at each fixed range of a grid inside its own prior, the remaining parameters are refitted by
the single scoring path (solve.score.fit with `fixed`), once testimony-weighted and once physics-only,
with the data-quality exclusions and the case's final winds (ERA5). Recorded per point: both totals,
the no-exclusion physics-only total rescored at the physics-only fit's parameters (not refitted), and
the implied mean slant range, mean air and ground speed, mean altitude and the largest acceleration
over the scored window, for both fits.

Fewer random starts than the main fits (RC_FIT below, the same for every hypothesis and range), so a
point can sit slightly below what a full fit would reach; the main fits in results.json are the
reference values.

The grid is GRID_NMI plus the case's own `range_curves_extra_nmi` (case YAML; GOFAST adds points around its
on-screen range), the same points for every hypothesis on the case.

Usage: python -m solve.range_curves gimbal [--procs 6]
       python -m solve.range_curves gofast | flir1
       python -m solve.range_curves gofast --missing [--procs 6]   (only grid points not yet in the CSV, merged)
Writes data/derived/<case>/range_curves.csv and docs/results/<case>_range_curves.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import score as S
from .case_data import case_variants, derived_dir, load_case

ROOT = Path(__file__).resolve().parents[1]
GRID_NMI = (0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0)
RC_FIT = {"n_random": 120, "n_starts": 3}
G = 9.80665


def _max_accel_g(case, pred) -> float:
    w = case.window
    acc = np.gradient(pred.obj_vel[w], case.t[w], axis=0)
    return float(np.max(np.linalg.norm(acc, axis=-1)) / G)


def _point(task: tuple) -> dict:
    case_name, variant, hid, r = task
    case = load_case(case_name, variant=variant or None)
    case_nx = load_case(case_name, variant=variant or None, exclusions=False) if case.weight_overrides else case
    h = {x.id: x for x in S.load_hypotheses()}[hid]
    w_t = S._weights(case)["testimony"]
    row = {"variant": variant or "", "hypothesis": hid, "range_nmi": r, "range_ref_nmi": r,
           "n_random": RC_FIT["n_random"], "n_starts": RC_FIT["n_starts"]}
    for tag, wt in (("testimony_weighted", w_t), ("physics_only", 0.0)):
        res = S.fit(case, h, testimony_weight=wt, fixed={"range_ref_nmi": float(r)}, **RC_FIT)
        row[f"valid_{tag}"] = bool(res.get("valid"))
        if not res.get("valid"):
            continue
        pred = res["prediction"]
        sc = pred.scalars
        row[f"total_{tag}"] = res[f"total_{tag}"]
        row[f"range_nmi_mean_{tag}"] = sc["range_nmi_mean"]
        row[f"air_speed_kt_{tag}"] = sc["air_speed_kt"]
        row[f"ground_speed_kt_{tag}"] = sc["ground_speed_kt"]
        row[f"altitude_ft_mean_{tag}"] = sc["altitude_ft_mean"]
        row[f"max_accel_g_{tag}"] = _max_accel_g(case, pred)
        if tag == "physics_only":
            # Unsuffixed columns (the app's range explorer names): the physics-only fit.
            for k in ("air_speed_kt", "ground_speed_kt", "altitude_ft_mean", "max_accel_g"):
                row[k] = row[f"{k}_{tag}"]
            if case_nx is case:
                row["total_physics_only_no_exclusions_rescored"] = res["total_physics_only"]
            else:
                df = S.score(case_nx, h, res["params"], testimony_weight=0.0)
                row["total_physics_only_no_exclusions_rescored"] = df.attrs["total_physics_only"]
    return row


def grid_for(case) -> list:
    """GRID_NMI plus the case's own extra points (identical for every hypothesis on the case)."""
    extra = [float(x) for x in (case.cfg.get("range_curves_extra_nmi") or [])]
    return sorted(set(float(x) for x in GRID_NMI) | set(extra))


def tasks_for(case_name: str) -> list:
    out = []
    for v in case_variants(case_name):
        case = load_case(case_name, variant=v or None)
        grid = grid_for(case)
        for h in S.load_hypotheses():
            specs = {s.name: s for s in S.param_specs(case, h)}
            sp = specs.get("range_ref_nmi")
            if sp is None:
                continue
            for r in grid:
                if sp.lo - 1e-9 <= r <= sp.hi + 1e-9:
                    out.append((case_name, v, h.id, r))
    return out


def _read(case_name: str) -> pd.DataFrame:
    df = pd.read_csv(derived_dir(case_name) / "range_curves.csv", keep_default_na=False, na_values=[""])
    df["variant"] = df["variant"].astype(object).where(df["variant"].notna(), "").astype(str)
    return df


def run(case_name: str, procs: int = 1, missing_only: bool = False) -> pd.DataFrame:
    tasks = tasks_for(case_name)
    old = None
    if missing_only and (derived_dir(case_name) / "range_curves.csv").exists():
        old = _read(case_name)
        have = {(str(v), str(h), round(float(r), 6)) for v, h, r in zip(old["variant"], old["hypothesis"], old["range_ref_nmi"])}
        tasks = [t for t in tasks if (str(t[1] or ""), t[2], round(float(t[3]), 6)) not in have]
    if procs > 1:
        from multiprocessing import Pool
        with Pool(procs) as pool:
            rows = []
            for r in pool.imap_unordered(_point, tasks):
                rows.append(r)
                print(f"{len(rows)}/{len(tasks)} {r['variant']} {r['hypothesis']} {r['range_ref_nmi']}", flush=True)
    else:
        rows = [_point(t) for t in tasks]
    df = pd.DataFrame(rows)
    if old is not None:
        df = pd.concat([old, df], ignore_index=True) if len(df) else old
    df = df.sort_values(["variant", "hypothesis", "range_ref_nmi"]).reset_index(drop=True)
    p = derived_dir(case_name) / "range_curves.csv"
    df.to_csv(p, index=False, float_format="%.6g")
    plot(case_name, df)
    return df


def plot(case_name: str, df: pd.DataFrame | None = None) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator

    if df is None:
        df = _read(case_name)
    df["variant"] = df["variant"].astype(object).where(df["variant"].notna(), "").astype(str)
    variants = list(dict.fromkeys(df["variant"]))
    panels = [("total_physics_only", "physics-only total"), ("total_testimony_weighted", "testimony-weighted total"),
              ("air_speed_kt_physics_only", "air speed, physics-only fit (kt)"),
              ("altitude_ft_mean_physics_only", "altitude, physics-only fit (ft)")]
    fig, axes = plt.subplots(len(variants), len(panels), figsize=(4.6 * len(panels), 3.8 * len(variants)), squeeze=False)
    hyps = sorted(set(df["hypothesis"]))
    colors = {h: f"C{i}" for i, h in enumerate(hyps)}
    for i, v in enumerate(variants):
        dv = df[df["variant"] == v]
        for j, (col, title) in enumerate(panels):
            ax = axes[i][j]
            for h in hyps:
                d = dv[dv["hypothesis"] == h].sort_values("range_ref_nmi")
                if col in d and d[col].notna().any():
                    ax.plot(d["range_ref_nmi"], d[col], marker="o", ms=3, lw=1.2, color=colors[h], label=h)
            ax.set_xscale("log")
            # Labelled ticks at a fixed sparse set inside the plotted span (no minor labels), so labels never overlap.
            xs = dv["range_ref_nmi"].astype(float)
            lo_x, hi_x = float(xs.min()), float(xs.max())
            ticks = [t for t in (0.5, 1, 2, 3, 5, 10, 20, 30, 60) if lo_x * 0.99 <= t <= hi_x * 1.01]
            ax.xaxis.set_major_locator(FixedLocator(ticks))
            ax.xaxis.set_minor_locator(NullLocator())
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.set_xticklabels([f"{t:g}" for t in ticks], fontsize=8)
            if col.startswith("total"):
                vals = dv[col].dropna()
                if len(vals):
                    top = vals.max()
                    # Show at least 150 below the best point, and enough to include the best hypothesis's next grid
                    # point (a narrow peak, as where the range is read on screen, otherwise shows as one spike).
                    lead = dv.loc[vals.idxmax(), "hypothesis"]
                    lv = dv[(dv["hypothesis"] == lead)][col].dropna().sort_values(ascending=False)
                    span = 150.0 if len(lv) < 2 else min(max(150.0, 1.15 * (top - lv.iloc[1])), 20000.0)
                    ax.set_ylim(top - span, top + 0.05 * span)
            ax.set_xlabel("range at the reference frame (nmi)")
            ax.set_title(f"{case_name.upper()}{' ' + v if v else ''}: {title}", fontsize=9)
            ax.grid(alpha=0.3)
            if i == 0 and j == 0:
                ax.legend(fontsize=7)
    fig.tight_layout()
    out = ROOT / "docs" / "results" / f"{case_name}_range_curves.png"
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out


def main(argv: list[str]) -> int:
    case_name = argv[1]
    procs = int(argv[argv.index("--procs") + 1]) if "--procs" in argv else 1
    if "--plot" in argv:
        print(plot(case_name))
        return 0
    df = run(case_name, procs, missing_only="--missing" in argv)
    print(df.to_string(max_cols=12))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
