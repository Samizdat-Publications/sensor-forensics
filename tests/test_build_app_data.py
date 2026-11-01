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


@pytest.mark.parametrize("cid", ["gimbal", "gofast"])
def test_predictions_cover_every_fit_and_frame(out, cid):
    """predictions.json re-evaluates every stored fit on every frame (tools/app_predictions.py)."""
    meta = json.loads((out / cid / "meta.json").read_text())
    pred = json.loads((out / cid / "predictions.json").read_text())
    res = json.loads((out / cid / "results.json").read_text())
    n = meta["n_frames"]
    for v in res["variants"]:
        pv = pred["variants"][v["variant"]]
        for h in v["hypotheses"]:
            if not h["valid"]:
                continue
            for fit in ("testimony_weighted", "physics_only"):
                f = pv["hypotheses"][h["id"]][fit]
                assert f["valid"]
                for k in ("obj_e", "jet_e", "horizon_deg", "img_x", "range_m"):
                    assert len(f[k]) == n
                lock = f["frame_lock"]
                assert lock["object_n"] > 0.5 * n
                # the pod tracks the object: every model predicts it on the boresight
                assert lock["object_px_median"] < 6.0


def test_gimbal_horizon_reference_and_lock(out):
    pred = json.loads((out / "gimbal" / "predictions.json").read_text())
    assert pred["measured"]["horizon_source"].startswith("cloud-deck motion direction")
    lock = pred["variants"]["fov035"]["hypotheses"]["H-BAL"]["testimony_weighted"]["frame_lock"]
    assert lock["horizon_n"] > 900
    assert lock["horizon_px_median"] < 10.0


def test_extras_and_exclusions_pass_through(out):
    app = json.loads((out / "gimbal" / "results.json").read_text())
    v = next(x for x in app["variants"] if x["variant"] == "fov035")
    assert set(v["excluded_criteria"]) == {"size_trend", "brightness_trend"}
    assert "closure_check" in v["extras"] or "turn_rate" in v["extras"]
    assert "extras" in v["hypotheses"][0]


def test_testimony_claims_exported(out):
    t = json.loads((out / "gimbal" / "testimony.json").read_text())
    assert len(t["claims"]) >= 40
    scored = [c for c in t["claims"] if c["scorable"]]
    assert scored and all("hypothesis" in c["use"] for c in scored)


def test_range_curves_csv_passthrough(tmp_path, monkeypatch):
    import app_predictions as AP
    d = tmp_path / "data" / "derived" / "gimbal"
    d.mkdir(parents=True)
    (d / "range_curves.csv").write_text("variant,hypothesis,range_nmi,air_speed_kt,max_accel_g,new_column\n"
                                        "fov035,H-BAL,10,5.0,0.01,x\nfov035,H-BAL,4,3.0,0.02,y\n", encoding="utf-8")
    monkeypatch.setattr(AP, "ROOT", tmp_path)
    rc = AP.range_curves_csv("gimbal")
    rows = rc["variants"]["fov035"]["H-BAL"]
    assert [r["range_nmi"] for r in rows] == [4.0, 10.0]
    assert rows[0]["new_column"] == "y" and rows[1]["max_accel_g"] == 0.01
