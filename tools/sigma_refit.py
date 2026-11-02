"""CP-04 second check: refit every hypothesis at larger rotation sigmas (case-level override, same for all).

The rotation sigma sweep in results.json is rescored at each fit's best parameters; this refits instead, through
the scorer's own fit path (solve.score.refit_at_rotation_sigma), so the totals at a larger sigma are proper
maxima. The override is applied to the case, never to a hypothesis.

Usage: .venv/Scripts/python tools/sigma_refit.py flir1 13.0 15.65 [--procs 6]
Writes data/derived/<case>/sigma_refit.json (FLIR1: data/derived/flir1_navy/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solve import score as S  # noqa: E402
from solve.case_data import derived_dir  # noqa: E402


def main(argv: list[str]) -> int:
    procs = 1
    if "--procs" in argv:
        i = argv.index("--procs")
        procs = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    case_name = argv[1]
    sigmas = [float(x) for x in argv[2:]]
    out = S.refit_at_rotation_sigma(case_name, sigmas, procs=procs)
    p = derived_dir(case_name) / "sigma_refit.json"
    p.write_text(json.dumps(S._jsonable(out), indent=1) + "\n", encoding="utf-8")
    for run in out["runs"]:
        print(f"--- sigma {run['sigma_deg']}")
        for e in sorted((e for e in run["hypotheses"] if e["valid"]), key=lambda e: -e["total_physics_only"]):
            print(f"{e['hypothesis']:8s} weighted {e['total_testimony_weighted']:12.2f}  physics {e['total_physics_only']:12.2f}")
    print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
