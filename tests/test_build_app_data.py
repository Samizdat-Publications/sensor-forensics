"""tools/build_app_data.py: the app exports carry both fits' criteria and reproduce Python's totals."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_app_data as B  # noqa: E402


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("appdata")
    assert B.main(["--no-frames", "--out", str(d)]) == 0
    return d


def test_index_lists_three_cases(out):
    idx = json.loads((out / "index.json").read_text())
    assert [c["case"] for c in idx["cases"]] == ["gimbal", "gofast", "flir1"]


@pytest.mark.parametrize("cid", ["gimbal", "gofast"])
def test_stored_fit_totals_match_python(out, cid):
    app = json.loads((out / cid / "results.json").read_text())
    for v in app["variants"]:
        for h in v["hypotheses"]:
            w = h["python_totals"]["testimony_weight"]
            tw = next(f for f in h["fits"] if f["fit"] == "testimony_weighted")
            po = next(f for f in h["fits"] if f["fit"] == "physics_only")
            phys = lambda f: sum(c["loglik"] * c["weight"] for c in f["criteria"] if c["kind"] != "testimony")
            testi = sum(c["loglik"] for c in tw["criteria"] if c["kind"] == "testimony")
            assert phys(tw) + w * testi == pytest.approx(h["python_totals"]["testimony_weighted"], rel=1e-9, abs=1e-6)
            assert phys(po) == pytest.approx(h["python_totals"]["physics_only"], rel=1e-9, abs=1e-6)


@pytest.mark.parametrize("cid", ["gimbal", "gofast", "flir1"])
def test_readings_cover_every_frame(out, cid):
    meta = json.loads((out / cid / "meta.json").read_text())
    rd = json.loads((out / cid / "readings.json").read_text())
    assert len(meta["t_s"]) == meta["n_frames"]
    for f in ("azimuth", "elevation"):
        assert len(rd["fields"][f]["value"]) == meta["n_frames"]
