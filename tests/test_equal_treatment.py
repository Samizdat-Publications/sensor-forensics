"""Equal-treatment tests (docs/design/scoring.md): no hypothesis-specific code, rename / reorder
invariance, and a single scoring entry point."""

import ast
import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solve import score as S
from solve.case_data import load_case

SOLVE = Path(__file__).resolve().parents[1] / "solve"


def _names():
    hyps = S.load_hypotheses()
    assert len(hyps) >= 6
    return {h.id for h in hyps}, {h.label for h in hyps}


def _docstring_nodes(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def test_no_code_under_solve_names_a_hypothesis():
    """AST scan: no string literal (docstrings aside) equals or contains a hypothesis id or label,
    so no comparison, branch, dict key or match case can single one out."""
    ids, labels = _names()
    bad = []
    for f in sorted(SOLVE.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docs = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                v = node.value
                if any(i.lower() in v.lower() for i in ids) or v in labels:
                    bad.append(f"{f.name}:{node.lineno}: {v!r}")
            if isinstance(node, ast.Compare):
                for part in [node.left, *node.comparators]:
                    if isinstance(part, ast.Attribute) and part.attr in ("id", "label"):
                        bad.append(f"{f.name}:{node.lineno}: compares .{part.attr}")
            if isinstance(node, ast.Match):
                bad.append(f"{f.name}:{node.lineno}: match statement (review by hand)")
    assert not bad, "hypothesis-specific code found:\n" + "\n".join(bad)


def test_hypothesis_files_hold_no_code_paths():
    """Hypotheses differ only by a model key, priors and data; every model key is in the registry."""
    from solve import models as M
    for h in S.load_hypotheses():
        assert h.model in M.MODELS
        for name, d in h.parameters.items():
            assert d.get("source"), f"{h.id}.{name} has no source"
            assert d.get("prior") in ("uniform", "loguniform", "normal")
        assert h.sources, f"{h.id} lists no sources"


@pytest.fixture(scope="module", params=["gofast", "gimbal"])
def case(request):
    return load_case(request.param)


PARAMS = {"jet_heading_deg": 270.0, "anchor_daz_deg": 0.1, "anchor_del_deg": -0.2, "wind_err_e_kt": 3.0,
          "wind_err_n_kt": -2.0, "range_ref_nmi": 3.8, "airspeed_kt": 30.0, "heading_deg": 120.0, "vz_fpm": 50.0,
          "altitude_ref_ft": 15500.0, "turn_rate_z": 0.2, "jet_pitch_deg": 3.6}


def _params_for(case, h):
    names = {s.name for s in S.param_specs(case, h)}
    p = {k: v for k, v in PARAMS.items() if k in names}
    for n in names - set(p):
        p[n] = 100.0  # spline knots
    return p


def test_rename_and_reorder_leave_scores_unchanged(case):
    hyps = S.load_hypotheses()
    base = {h.id: S.score(case, h, _params_for(case, h)) for h in hyps}
    renamed = []
    for k, h in enumerate(hyps):
        h2 = copy.deepcopy(h)
        h2.id, h2.label = f"X{k:02d}", f"renamed {k}"
        renamed.append((h.id, h2))
    rng = np.random.default_rng(0)
    for i in rng.permutation(len(renamed)):
        orig, h2 = renamed[i]
        df = S.score(case, h2, _params_for(case, h2))
        pd.testing.assert_frame_equal(df, base[orig])
        assert df.attrs["total_testimony_weighted"] == base[orig].attrs["total_testimony_weighted"]
        assert df.attrs["total_physics_only"] == base[orig].attrs["total_physics_only"]


def test_fit_does_not_depend_on_the_name(case):
    h = next(x for x in S.load_hypotheses() if x.model == "wind_drifter")
    h2 = copy.deepcopy(h)
    h2.id, h2.label = "anonymous", "anonymous"
    a = S.fit(case, h, n_random=40, n_starts=2, testimony_weight=1.0)
    b = S.fit(case, h2, n_random=40, n_starts=2, testimony_weight=1.0)
    assert a["params"] == b["params"]
    assert a["total_testimony_weighted"] == b["total_testimony_weighted"]


def test_single_public_scoring_entry_point():
    assert {"score", "fit", "run_case"} <= set(S.__all__)
    # Only solve/score.py may compute criterion likelihoods or totals; models never import the scorer.
    private = ("interval_loglik", "gaussian_loglik", "bic_penalty", "scaled_sum", "criterion_logliks")
    for f in sorted(SOLVE.rglob("*.py")):
        if f.name in ("score.py", "likelihoods.py"):
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in private:
                pytest.fail(f"{f.name}:{node.lineno} uses {node.attr} outside solve/score.py")
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("score"):
                pytest.fail(f"{f.name} imports the scorer's internals")
    # Both totals are always reported.
    df = S.score(load_case("gofast"), S.load_hypotheses()[0], _params_for(load_case("gofast"), S.load_hypotheses()[0]))
    assert {"total_testimony_weighted", "total_physics_only"} <= set(df.attrs)


def test_every_hypothesis_meets_the_same_testimony_claims(case):
    """missing='raise' in the scorer: every model supplies every testimony quantity."""
    rows = {}
    for h in S.load_hypotheses():
        ev = S._evaluate(case, h, S._full_params(S.param_specs(case, h), _params_for(case, h)), S.param_specs(case, h))
        if ev["valid"]:
            rows[h.id] = sorted((r["claim_id"], r["quantity"]) for r in ev["testimony_rows"])
    assert len({tuple(v) for v in rows.values()}) == 1
