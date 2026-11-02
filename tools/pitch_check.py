"""Diagnostic: how much of a rotation gap a jet-pitch prior bound accounts for (CP-04 review, nice-to-fix).

For each hypothesis at its stored best fits (results.json), the jet pitch alone is scanned past its prior
bound (other parameters held) and the rotation criterion plus the pitch's normal log prior are recorded.
Reported, never added to any total; the same scan for every hypothesis.

Usage: .venv/Scripts/python tools/pitch_check.py flir1
Lives in tools/ (not solve/): it only reads the scorer's outputs and calls its public entry point solve.score.score.
Writes data/derived/<case>/pitch_bound_check.json.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solve import score as S  # noqa: E402
from solve.case_data import derived_dir, load_case  # noqa: E402


def run(case_name: str, grid=np.arange(-8.0, 10.01, 0.25)) -> dict:
    case = load_case(case_name)
    res = json.loads((derived_dir(case_name) / "results.json").read_text(encoding="utf-8"))
    hyps = {h.id: h for h in S.load_hypotheses()}
    spec = case.shared_parameters["jet_pitch_deg"]
    mean, sd = float(spec["mean"]), float(spec["sd"])
    out = {"case": case_name, "prior": {"mean": mean, "sd": sd, "bounds": spec.get("bounds")}, "hypotheses": {}}
    for e in res["hypotheses"]:
        if not e["valid"]:
            continue
        rows = {}
        for tag, pk in (("testimony_weighted", "params_testimony_weighted_fit"), ("physics_only", "params_physics_only_fit")):
            p0 = dict(e[pk])
            scan = []
            for pitch in grid:
                p = dict(p0, jet_pitch_deg=float(pitch))
                try:
                    df = S.score(case, hyps[e["hypothesis"]], p, testimony_weight=0.0)
                except ValueError:
                    continue
                rot = float(df.set_index("criterion").loc["rotation", "loglik"])
                scan.append({"pitch_deg": float(pitch), "rotation": rot,
                             "rotation_plus_prior": rot - 0.5 * ((pitch - mean) / sd) ** 2})
            at = min(scan, key=lambda r: abs(r["pitch_deg"] - p0["jet_pitch_deg"]))
            best = max(scan, key=lambda r: r["rotation_plus_prior"])
            rows[tag] = {"fitted_pitch_deg": p0["jet_pitch_deg"], "at_fit": at, "best_unbounded": best,
                         "gain_unbounded": best["rotation_plus_prior"] - at["rotation_plus_prior"]}
        out["hypotheses"][e["hypothesis"]] = rows
    (derived_dir(case_name) / "pitch_bound_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv) -> int:
    out = run(argv[1] if len(argv) > 1 else "flir1")
    for k, v in out["hypotheses"].items():
        r = v["physics_only"]
        print(k, r["fitted_pitch_deg"], r["best_unbounded"]["pitch_deg"], round(r["gain_unbounded"], 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
