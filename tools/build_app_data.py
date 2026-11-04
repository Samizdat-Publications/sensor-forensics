"""Export per-case JSON (and JPEG frame sequences) for the static web app in app/.

Usage (from the repo root):
    .venv/Scripts/python tools/build_app_data.py            # JSON + frames
    .venv/Scripts/python tools/build_app_data.py --no-frames
    .venv/Scripts/python tools/build_app_data.py --force-frames   # re-encode every JPEG

Reads only data/derived/ and data/frames/ (never writes there). Writes:
    app/data/index.json                      case list
    app/data/<case>/meta.json                frame count, fps, sources, variants
    app/data/<case>/results.json             per variant: weights, flags, hypotheses with
                                             both fits' per-criterion log-likelihoods
                                             (full precision from results.json) and the
                                             weight and kind of every criterion (scores.csv)
    app/data/<case>/readings.json            per-frame on-screen readouts with confidence
    app/data/<case>/cues.json                per-frame image cues (bank, object blob)
    app/data/<case>/range_curve.json         angles-only fit as a function of assumed range
    app/data/<case>/turn_rate.json           jet turn rate per frame (where it exists)
    app/data/<case>/compare.json             prior work (published) beside the lab's reproduction
    app/data/<case>/predictions.json         per frame, every stored fit re-evaluated by the scorer's own
                                             forward model (tools/app_predictions.py): sight line, image
                                             horizon, rotation, size, image position, object and jet paths,
                                             frame-lock errors; plus the measured references
    app/data/<case>/predictions_<variant>.json   the same per field of view, without the test-only image positions:
                                             what the app loads (only the field of view on screen)
    app/data/<case>/testimony.json           every testimony claim with its source and how it is used
    app/data/<case>/range_curves.json        per-hypothesis curves over range (range_curves.csv), when present
    app/data/frames/<case>/f000000.jpg ...   gitignored, regenerated
    app/data/video/<case>.mp4                the same frames as an H.264 video for playback, gitignored

All values stay in SI or the units the derived files use; the app converts for display.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_predictions as AP  # noqa: E402
DERIVED = ROOT / "data" / "derived"
FRAMES = ROOT / "data" / "frames"
OUT = ROOT / "app" / "data"

# App case id -> derived folder. FLIR1 uses the Navy 2020 copy (the reference copy).
CASES = {
    "gimbal": {"label": "GIMBAL", "folder": "gimbal", "date": "01/21/2015", "platform": "F/A-18F, ATFLIR"},
    "gofast": {"label": "GOFAST", "folder": "gofast", "date": "01/2015", "platform": "F/A-18F, ATFLIR"},
    "flir1": {"label": "FLIR1", "folder": "flir1_navy", "date": "11/14/2004", "platform": "F/A-18F, ATFLIR (Nimitz group)",
              # docs/audit/flir1.md: the "99.9 RNG" line never changes, so it is a placeholder, not a range
              "placeholders": {"range": {"value": "99.9", "note": "placeholder, no range on screen"}}},
}
EXPORTS = ROOT / "exports" / "cases"
NOTES = ROOT / "data" / "discriminators" / "notes.yaml"

CUE_COLUMNS = [
    "bank_deg", "bank_sigma_deg", "obj_found", "obj_snr", "obj_hi_cx", "obj_hi_cy",
    "obj_hi_major_px", "obj_hi_minor_px", "obj_hi_angle_deg", "obj_hi_area_px", "obj_peak",
    "obj_lo_major_px", "obj_lo_minor_px", "bg_dx", "bg_dy", "cloud_dx", "cloud_dy",
]


def _num(s: str):
    if s is None or s == "":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _round(v, nd=4):
    return None if v is None else round(v, nd)


def _clean(o):
    """JSON-safe: NaN and inf become null."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), separators=(",", ":"), allow_nan=False), encoding="utf-8")


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score_rows(folder: Path) -> dict:
    """(variant, hypothesis, fit) -> {criterion: (weight, kind)} from scores.csv."""
    out: dict = {}
    p = folder / "scores.csv"
    if not p.exists():
        return out
    for r in _read_csv(p):
        key = (r.get("variant", "") or "", r["hypothesis"], r["fit"])
        out.setdefault(key, {})[r["criterion"]] = (float(r["weight"]), r["kind"])
    return out


DERIVED_KEYS = [
    "range_nmi_mean", "altitude_ft_mean", "altitude_ft_min", "altitude_ft_max", "air_speed_kt",
    "ground_speed_kt", "ground_track_deg", "vertical_speed_fpm", "motion_vs_wind", "wind_at_object_kt",
    "stops_and_reverses", "range_trend",
]


# Keys export_variant consumes itself; anything else the scorer adds is passed through under "extras"
# (both-ways totals, sensitivity runs and the like), so a rerun with new fields shows up without a code change.
HYP_KEYS = {"hypothesis", "label", "model", "valid", "in_design_set", "k", "testimony_status", "total_testimony_weighted",
            "total_physics_only", "criteria", "criteria_physics_only_fit", "derived", "derived_physics_only_fit",
            "params_testimony_weighted_fit", "params_physics_only_fit", "checks", "testimony_rows",
            "testimony_rows_physics_only_fit"}
VARIANT_KEYS = {"case", "label", "variant", "sensor", "window_frames", "reference_frame", "weights", "flags", "environment",
                "n_eff_total", "hypotheses", "range_curve_angles_only"}
EXTRA_MAX_BYTES = 60_000


def _extras(d: dict, known: set) -> dict:
    out = {}
    for k, x in d.items():
        if k in known:
            continue
        try:
            js = json.dumps(_clean(x))
        except (TypeError, ValueError):
            continue
        if len(js) <= EXTRA_MAX_BYTES:
            out[k] = _clean(x)
    return out


def export_variant(v: dict, vname: str, rows: dict) -> dict:
    hyps = []
    for h in v["hypotheses"]:
        fits = []
        for fit, ckey, dkey, pkey in (
            ("testimony_weighted", "criteria", "derived", "params_testimony_weighted_fit"),
            ("physics_only", "criteria_physics_only_fit", "derived_physics_only_fit", "params_physics_only_fit"),
        ):
            crit = h.get(ckey) or {}
            wk = rows.get((vname, h["hypothesis"], fit), {})
            if crit and not wk:
                raise SystemExit(f"scores.csv has no rows for {vname or '-'} {h['hypothesis']} {fit}")
            fits.append({
                "fit": fit,
                "criteria": [
                    {"name": name, "loglik": ll, "weight": wk[name][0], "kind": wk[name][1]}
                    for name, ll in crit.items()
                ],
                "derived": {k: (h.get(dkey) or {}).get(k) for k in DERIVED_KEYS},
                "params": h.get(pkey) or {},
            })
        hyps.append({
            "id": h["hypothesis"],
            "label": h["label"],
            "model": h.get("model"),
            "valid": bool(h.get("valid")),
            "in_design_set": bool(h.get("in_design_set", True)),
            "k": h.get("k"),
            "testimony_status": h.get("testimony_status"),
            "python_totals": {
                "testimony_weighted": h.get("total_testimony_weighted"),
                "physics_only": h.get("total_physics_only"),
                "testimony_weight": v["weights"].get("testimony"),
            },
            "fits": fits,
            "checks": h.get("checks", []),
            "testimony_rows": [{k: r.get(k) for k in ("claim_id", "quantity", "predicted_value", "interval", "loglik", "weight",
                                                      "firsthand", "weighted_loglik")} for r in h.get("testimony_rows") or []],
            "extras": _extras(h, HYP_KEYS),
        })
    # Criteria a data-quality rule holds at weight 0 for every hypothesis (D-016, D-017, REVIEW-M3 Rule B).
    excluded = sorted({c["name"] for hh in hyps for f in hh["fits"] for c in f["criteria"]
                       if c["kind"] == "physics" and c["weight"] == 0})
    return {
        "variant": vname,
        "sensor": v.get("sensor"),
        "window_frames": v.get("window_frames"),
        "reference_frame": v.get("reference_frame"),
        "weights": v["weights"],
        "flags": v.get("flags", []),
        "environment": v.get("environment"),
        "n_eff_total": v.get("n_eff_total"),
        "excluded_criteria": excluded,
        "hypotheses": hyps,
        "extras": _extras(v, VARIANT_KEYS),
    }


REPRO = ROOT / "docs" / "reproductions"


def _g(d: dict, *path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def compare_rows(cid: str) -> dict | None:
    """Published prior-work numbers beside the lab's reproduction of each (docs/reproductions/<case>.json).

    Each row: quantity, unit, and per source {published, reproduced}. Units as in the source (kt, ft, nmi).
    """
    p = REPRO / f"{cid}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    if cid == "gimbal":
        pub, A, A7, B = d["published"], d["A_repro"], d["A7_repro"], d["B_clouds_port"]
        sources = [
            {"id": "pvr_close", "label": "Peings and von Rennenkampff 2023, close path", "note": "Their Figure A path; lab reproduction with their inputs.",
             "check": _g(d, "A_check", "all_pass")},
            {"id": "pvr_far", "label": "Peings and von Rennenkampff 2023, distant path", "note": "Their 30 nmi constant-altitude path.",
             "check": _g(d, "A7_check", "all_pass")},
            {"id": "sitrec", "label": "Sitrec (Mick West), distant plane", "note": "Sitrec's 'match clouds' path, ported; published criterion: a path exists at 30 to 34 nmi, level within 500 ft.",
             "check": _g(d, "B_check_clouds", "all_pass")},
        ]
        rows = [
            ("Start range", "nmi", {"pvr_close": (pub["A"]["start_range_nmi"], A["start_range_nmi"]),
                                     "pvr_far": (pub["A7"]["range_nmi"], A7["range_start_end_nmi"][0]),
                                     "sitrec": (None, B["start_range_nmi"])}),
            ("End range", "nmi", {"pvr_close": (pub["A"]["end_range_nmi"], A["end_range_nmi"]),
                                   "pvr_far": (pub["A7"]["range_nmi"], A7["range_start_end_nmi"][1]),
                                   "sitrec": (None, B["end_range_nmi"])}),
            ("Air speed at start", "kt", {"pvr_close": (pub["A"]["air_speed_start_kt"], A["air_speed_start_kt"]),
                                           "pvr_far": (pub["A7"]["air_speed_start_kt"], A7["air_speed_start_kt"]),
                                           "sitrec": (None, None)}),
            ("Air speed at end", "kt", {"pvr_close": (None, A["air_speed_end_kt"]),
                                         "pvr_far": (pub["A7"]["air_speed_end_kt"], A7["air_speed_end_kt"]),
                                         "sitrec": (None, None)}),
            ("Altitude at start", "ft", {"pvr_close": (None, A["alt_start_ft"]), "pvr_far": (pub["A7"]["alt_ft"], A7["alt_ft"]),
                                          "sitrec": (None, B["alt_start_ft"])}),
            ("Altitude change", "ft", {"pvr_close": (pub["A"]["alt_change_ft"], A["alt_change_ft"]), "pvr_far": (0.0, 0.0),
                                        "sitrec": (None, B["alt_end_ft"] - B["alt_start_ft"])}),
        ]
        # Points to draw over the clip (lab frame numbers; Sitrec frames are lab - 1, under one frame).
        n_last = 1030
        points = {
            "pvr_close": [("range_nmi", 0, pub["A"]["start_range_nmi"], A["start_range_nmi"]),
                          ("range_nmi", n_last, pub["A"]["end_range_nmi"], A["end_range_nmi"]),
                          ("altitude_ft", 0, None, A["alt_start_ft"]), ("altitude_ft", n_last, None, A["alt_start_ft"] + A["alt_change_ft"])],
            "pvr_far": [("range_nmi", 0, pub["A7"]["range_nmi"], A7["range_start_end_nmi"][0]),
                        ("range_nmi", n_last, pub["A7"]["range_nmi"], A7["range_start_end_nmi"][1]),
                        ("altitude_ft", 0, pub["A7"]["alt_ft"], A7["alt_ft"]), ("altitude_ft", n_last, pub["A7"]["alt_ft"], A7["alt_ft"])],
            "sitrec": [("range_nmi", 0, None, B["start_range_nmi"]), ("range_nmi", n_last, None, B["end_range_nmi"]),
                       ("altitude_ft", 0, None, B["alt_start_ft"]), ("altitude_ft", n_last, None, B["alt_end_ft"])],
        }
    elif cid == "gofast":
        pub, sw = d["published"], d["sitrec_way"]
        sources = [
            {"id": "sitrec", "label": "Sitrec (Mick West)", "note": "Published observed values; lab reproduction the Sitrec way.", "check": None},
            {"id": "aaro", "label": "AARO (2023 statement)", "note": "Published altitude only.", "check": None},
        ]
        rows = [
            ("Altitude at frame 375", "ft", {"sitrec": (pub["sitrec_observed_alt_ft"][0], sw["alt_ft_at_375"]), "aaro": (pub["aaro_alt_ft"][0], None)}),
            ("Altitude at frame 1030", "ft", {"sitrec": (pub["sitrec_observed_alt_ft"][1], sw["alt_ft_at_1030"]), "aaro": (pub["aaro_alt_ft"][1], None)}),
            ("Ground speed", "kt", {"sitrec": (pub["sitrec_observed_ground_speed_kt"], sw["ground_speed_kt"]), "aaro": (None, None)}),
            ("Ground track", "deg", {"sitrec": (pub["sitrec_observed_track_deg"], sw["ground_track_deg"]), "aaro": (None, None)}),
        ]
    else:
        return None
    if cid == "gofast":
        points = {
            "sitrec": [("altitude_ft", 375, pub["sitrec_observed_alt_ft"][0], sw["alt_ft_at_375"]),
                       ("altitude_ft", 1030, pub["sitrec_observed_alt_ft"][1], sw["alt_ft_at_1030"])],
            "aaro": [("altitude_ft", 375, pub["aaro_alt_ft"][0], None), ("altitude_ft", 1030, pub["aaro_alt_ft"][1], None)],
        }
    if cid not in ("gimbal", "gofast"):
        return None
    for src in sources:
        src["points"] = [{"quantity": q, "frame": f, "published": a, "reproduced": b} for q, f, a, b in points.get(src["id"], [])]
    return {
        "case": cid, "source": f"docs/reproductions/{cid}.json", "sources": sources,
        "rows": [{"quantity": q, "unit": u, "values": {k: {"published": v[0], "reproduced": v[1]} for k, v in vals.items()}}
                 for q, u, vals in rows],
    }


def export_case(cid: str, spec: dict, frames: bool, force_frames: bool, predictions: bool = True) -> dict:
    folder = DERIVED / spec["folder"]
    out = OUT / cid
    meta_src = json.loads((folder / "frames_meta.json").read_text(encoding="utf-8"))
    frame_rows = _read_csv(folder / "frames.csv")
    n = len(frame_rows)
    files: list[str] = []

    # results
    res_path = folder / "results.json"
    variants = []
    steps: list = []
    if res_path.exists():
        res = json.loads(res_path.read_text(encoding="utf-8"))
        rows = score_rows(folder)
        vmap = res["variants"] if "variants" in res else {res.get("variant", "") or "": res}
        variants = [export_variant(v, vn, rows) for vn, v in vmap.items()]
        _write(out / "results.json", {"case": cid, "label": spec["label"], "variants": variants})
        files.append("results.json")
        curves = {vn: v.get("range_curve_angles_only", []) for vn, v in vmap.items()}
        _write(out / "range_curve.json", {"case": cid, "note": "Angles-only fit at fixed assumed range (testimony weight 0).", "variants": curves})
        files.append("range_curve.json")
        rc = next(iter(vmap.values())).get("rotation_check") or {}
        steps = [s["frame"] for s in rc.get("measured_steps", []) if "frame" in s]

    res_obj = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else None
    pred_files: dict = {}
    if predictions:
        pred = {"case": cid, **AP.case_predictions(spec["folder"], res_obj)}
        _write(out / "predictions.json", pred)
        files.append("predictions.json")
    elif (out / "predictions.json").exists():
        pred = json.loads((out / "predictions.json").read_text(encoding="utf-8"))
    else:
        pred = None
    if pred is not None:
        # The app loads only the field of view on screen, without the test-only image positions (img_x, img_y:
        # tests/js/geom.test.mjs checks them against predictions.json).
        for vn, v in pred["variants"].items():
            name = f"predictions_{vn or 'default'}.json"
            slim = {**v, "hypotheses": {h: {fn: {k: x for k, x in f.items() if k not in ("img_x", "img_y")}
                                            for fn, f in fits.items()} for h, fits in v["hypotheses"].items()}}
            _write(out / name, {"case": cid, "variant": vn, "picture": pred["picture"], "measured": pred["measured"],
                                "method": pred["method"], "data": slim})
            pred_files[vn] = name
            files.append(name)
    claims = AP.testimony_claims(cid)
    if claims:
        _write(out / "testimony.json", {"case": cid, "source": f"data/testimony/{cid}.yaml, data/testimony/scorable.yaml",
                                        "claims": claims})
        files.append("testimony.json")
    rcc = AP.range_curves_csv(spec["folder"])
    if rcc is not None:
        _write(out / "range_curves.json", {"case": cid, **rcc})
        files.append("range_curves.json")

    cmp = compare_rows(cid)
    if cmp:
        _write(out / "compare.json", cmp)
        files.append("compare.json")

    # readings (on-screen symbology), columnar per field
    sym = folder / "symbology_final.csv"
    if sym.exists():
        fields: dict = {}
        for r in _read_csv(sym):
            f = r["field"]
            d = fields.setdefault(f, {"value": [None] * n, "confidence": [None] * n, "method": [None] * n})
            i = int(r["frame"])
            if 0 <= i < n:
                d["value"][i] = r["value"] if r["value"] != "" else None
                d["confidence"][i] = _round(_num(r["confidence"]), 3)
                d["method"][i] = r["method"]
        for f, ph in spec.get("placeholders", {}).items():
            read = {x for x in fields.get(f, {}).get("value", []) if x not in (None, "blank")}
            if read != {ph["value"]}:
                raise SystemExit(f"{cid}: {f} was declared a placeholder ({ph['value']}) but reads {sorted(read)[:5]}")
            fields[f]["placeholder"] = ph
        _write(out / "readings.json", {"case": cid, "source": f"data/derived/{spec['folder']}/symbology_final.csv",
                                       "n_frames": n, "fields": fields})
        files.append("readings.json")

    # image cues
    it = folder / "image_track.csv"
    if it.exists():
        itr = _read_csv(it)
        cols = {c: [None] * n for c in CUE_COLUMNS if c in itr[0]}
        for r in itr:
            i = int(r["frame"])
            if 0 <= i < n:
                for c in cols:
                    cols[c][i] = _round(_num(r[c]), 4)
        _write(out / "cues.json", {"case": cid, "source": f"data/derived/{spec['folder']}/image_track.csv",
                                   "n_frames": n, "columns": cols})
        files.append("cues.json")

    # turn rate
    tr = folder / "turn_rate.csv"
    if tr.exists():
        trr = _read_csv(tr)
        keys = [k for k in trr[0].keys() if k != "frame"]
        cols = {k: [None] * n for k in keys}
        for r in trr:
            i = int(r["frame"])
            if 0 <= i < n:
                for k in keys:
                    cols[k][i] = _round(_num(r[k]), 5)
        _write(out / "turn_rate.json", {"case": cid, "units": "deg/s, negative = left turn",
                                        "source": f"data/derived/{spec['folder']}/turn_rate.csv", "columns": cols})
        files.append("turn_rate.json")

    meta = {
        "case": cid, "label": spec["label"], "date": spec["date"], "platform": spec["platform"],
        "derived_folder": spec["folder"], "n_frames": n, "fps": meta_src.get("fps_nominal"),
        "t_s": [_round(_num(r["t_nominal_s"]), 4) for r in frame_rows],
        "source_video": meta_src.get("source_video", "").replace("\\", "/"),
        "source_sha256": meta_src.get("source_sha256"),
        "variants": [v["variant"] for v in variants], "files": files,
        "frames_path": f"data/frames/{cid}/", "frame_pattern": "f{index:06d}.jpg",
        "video": f"data/video/{cid}.mp4",
        "predictions_files": pred_files,
        "scored": bool(variants),
        "markers": {"rotation_steps": steps},
        "summary": case_summary(cid),
    }
    _write(out / "meta.json", meta)

    if frames:
        export_frames(spec["folder"], cid, n, force_frames)
        export_video(spec["folder"], cid, n, meta["fps"], force_frames)
    return meta


def case_summary(cid: str) -> dict | None:
    """The plain verdict for the app's rail and welcome card: the case file's verdict (tools/export_cases.py) and
    the first measurement under "What would settle it" (data/discriminators/notes.yaml, the results pages' text)."""
    import re

    import yaml

    p = EXPORTS / f"{cid}.json"
    if not p.exists():
        return None
    v = json.loads(p.read_text(encoding="utf-8"))["verdict"]
    out = {"verdict_text": v["text"], "decisive": v["decisive"], "leader_physics_only": v["leader_physics_only"],
           "source": f"exports/cases/{cid}.json verdict; data/discriminators/notes.yaml results_page_settle.{cid}"}
    settle = (yaml.safe_load(NOTES.read_text(encoding="utf-8")).get("results_page_settle") or {}).get(cid, "")
    m = re.search(r"- \*\*(.+?)\*\*\s*(.+?)(?:\n\s*\n|\Z)", settle, re.S)
    if m:
        clean = lambda s: re.sub(r"\s+", " ", re.sub(r"`|\*\*|\[([^\]]+)\]\([^)]+\)", r"\1", s)).strip()
        out["settle_title"] = clean(m.group(1)).rstrip(".")
        out["settle_text"] = clean(m.group(2))
    return out


def export_video(folder: str, cid: str, n: int, fps: float, force: bool) -> None:
    """One H.264 video per case from the same extracted frames as the JPEGs, at the exact frame rate, so frame i is
    shown at i / fps: the app plays it and reads the frame on screen from the video's own clock. CRF 26 keeps the picture (PSNR about 38 dB against the frames; it smooths only the sensor grain) at a fifth of the size. A keyframe every 30
    frames keeps seeking quick; +faststart lets it start before it has fully downloaded."""
    import shutil
    import subprocess
    from fractions import Fraction

    dst = OUT / "video" / f"{cid}.mp4"
    if dst.exists() and not force:
        print(f"  video {cid}: up to date")
        return
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found: it is needed for the app's playback videos")
    rate = "30000/1001" if abs(fps - 30000 / 1001) < 1e-6 else str(Fraction(fps).limit_denominator(1001))
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", rate, "-i", str(FRAMES / folder / "f%06d.png"),
                    "-frames:v", str(n), "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-g", "30",
                    "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(dst)], check=True)
    print(f"  video {cid}: {dst.stat().st_size / 1e6:.1f} MB")


def export_frames(folder: str, cid: str, n: int, force: bool) -> None:
    from PIL import Image

    src = FRAMES / folder
    dst = OUT / "frames" / cid
    dst.mkdir(parents=True, exist_ok=True)
    made = 0
    for i in range(n):
        target = dst / f"f{i:06d}.jpg"
        if target.exists() and not force:
            continue
        p = src / f"f{i:06d}.png"
        if not p.exists():
            raise SystemExit(f"missing source frame {p}; run extract first")
        with Image.open(p) as im:
            im.convert("RGB").save(target, "JPEG", quality=85, optimize=True)
        made += 1
    print(f"  frames {cid}: {made} written, {n - made} up to date")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-frames", action="store_true")
    ap.add_argument("--force-frames", action="store_true")
    ap.add_argument("--no-predictions", action="store_true", help="skip predictions.json (loads every case through solve/)")
    ap.add_argument("--out", type=Path, default=None, help="output folder (default app/data)")
    a = ap.parse_args(argv)
    global OUT
    if a.out is not None:
        OUT = a.out
    index = []
    for cid, spec in CASES.items():
        meta = export_case(cid, spec, frames=not a.no_frames, force_frames=a.force_frames,
                           predictions=not a.no_predictions)
        index.append({k: meta[k] for k in ("case", "label", "date", "platform", "n_frames", "fps", "scored", "variants", "summary")})
        print(f"{cid}: {meta['n_frames']} frames, variants {meta['variants'] or 'none (not scored yet)'}")
    _write(OUT / "index.json", {"cases": index})
    if not a.no_predictions and a.out is None:
        write_framelock(ROOT / "artifacts" / "cp05" / "framelock.json")
    return 0


def write_framelock(path: Path) -> None:
    """CP-05 frame-lock metric: median pixel error of horizon and object position, every fit of every case."""
    rows = []
    for cid in CASES:
        p = OUT / cid / "predictions.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for vn, v in d["variants"].items():
            for h, fits in v["hypotheses"].items():
                for fn, f in fits.items():
                    if f.get("valid"):
                        rows.append({"case": cid, "variant": vn, "hypothesis": h, "fit": fn, **f["frame_lock"]})
        src = d.get("measured", {}).get("horizon_source")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "definition": AP.__doc__.split("Frame-lock metric (CP-05):")[1].strip(),
        "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
