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
    app/data/frames/<case>/f000000.jpg ...   gitignored, regenerated

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
DERIVED = ROOT / "data" / "derived"
FRAMES = ROOT / "data" / "frames"
OUT = ROOT / "app" / "data"

# App case id -> derived folder. FLIR1 uses the Navy 2020 copy (the reference copy).
CASES = {
    "gimbal": {"label": "GIMBAL", "folder": "gimbal", "date": "01/21/2015", "platform": "F/A-18F, ATFLIR"},
    "gofast": {"label": "GOFAST", "folder": "gofast", "date": "01/2015", "platform": "F/A-18F, ATFLIR"},
    "flir1": {"label": "FLIR1", "folder": "flir1_navy", "date": "11/14/2004", "platform": "F/A-18F, ATFLIR (Nimitz group)"},
}

CUE_COLUMNS = [
    "bank_deg", "bank_sigma_deg", "obj_found", "obj_snr", "obj_hi_cx", "obj_hi_cy",
    "obj_hi_major_px", "obj_hi_minor_px", "obj_hi_angle_deg", "obj_hi_area_px", "obj_peak",
    "bg_dx", "bg_dy",
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
        })
    return {
        "variant": vname,
        "sensor": v.get("sensor"),
        "window_frames": v.get("window_frames"),
        "reference_frame": v.get("reference_frame"),
        "weights": v["weights"],
        "flags": v.get("flags", []),
        "environment": v.get("environment"),
        "n_eff_total": v.get("n_eff_total"),
        "hypotheses": hyps,
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
    return {
        "case": cid, "source": f"docs/reproductions/{cid}.json", "sources": sources,
        "rows": [{"quantity": q, "unit": u, "values": {k: {"published": v[0], "reproduced": v[1]} for k, v in vals.items()}}
                 for q, u, vals in rows],
    }


def export_case(cid: str, spec: dict, frames: bool, force_frames: bool) -> dict:
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
        _write(out / "readings.json", {"case": cid, "source": f"data/derived/{spec['folder']}/symbology_final.csv",
                                       "n_frames": n, "fields": fields})
        files.append("readings.json")

    # image cues
    it = folder / "image_track.csv"
    if it.exists():
        cols = {c: [None] * n for c in CUE_COLUMNS}
        for r in _read_csv(it):
            i = int(r["frame"])
            if 0 <= i < n:
                for c in CUE_COLUMNS:
                    if c in r:
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
        "scored": bool(variants),
        "markers": {"rotation_steps": steps},
    }
    _write(out / "meta.json", meta)

    if frames:
        export_frames(spec["folder"], cid, n, force_frames)
    return meta


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
    ap.add_argument("--out", type=Path, default=None, help="output folder (default app/data)")
    a = ap.parse_args(argv)
    global OUT
    if a.out is not None:
        OUT = a.out
    index = []
    for cid, spec in CASES.items():
        meta = export_case(cid, spec, frames=not a.no_frames, force_frames=a.force_frames)
        index.append({k: meta[k] for k in ("case", "label", "date", "platform", "n_frames", "fps", "scored", "variants")})
        print(f"{cid}: {meta['n_frames']} frames, variants {meta['variants'] or 'none (not scored yet)'}")
    _write(OUT / "index.json", {"cases": index})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
