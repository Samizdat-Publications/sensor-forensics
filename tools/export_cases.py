"""Export UFO Case Files (schema v0.1, D-014) from the lab's current outputs.

Usage (from the repo root):
    .venv/Scripts/python tools/export_cases.py [--out exports/cases]

One file per scored video (gimbal, gofast, flir1), one for the PURSUE triage summary, and
one per frozen PURSUE clip if data/derived/pursue/<clip>/results.json exists. The exporter
reads whatever is current and tolerates missing or new optional fields: a missing input
becomes an absent or empty field, never a crash. It does not edit solve/ or data/derived/.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NMI_M = 1852.0
KT_MPS = 1852.0 / 3600.0
FT_M = 0.3048
FPM_MPS = FT_M / 60.0
LR10 = math.log(10.0)  # 2.3026: a likelihood ratio of 10

DERIVED = ROOT / "data" / "derived"
REPO_URL = "https://github.com/Samizdat-Publications/sensor-forensics"

# Static facts per video. Event facts come from the public record (docs/prior-work, testimony
# README); anything the lab has not pinned down is null with a note, not guessed.
CASES: dict[str, dict] = {
    "gimbal": {
        "title": "GIMBAL (F/A-18F, ATFLIR, January 2015)",
        "derived": "gimbal",
        "key": "gimbal",
        "manifest": ["gimbal_navy2020"],
        "date": "2015-01",
        "date_uncertainty": "Month is public; the exact day and time of day are not pinned down by the lab. "
                            "Weather was taken at 2015-01-25T02:30 UTC as the analysis time.",
        "place": "Atlantic Ocean off the US East Coast",
        "place_note": "No position is shown on screen; the lab holds no coordinates for this clip.",
        "platform": "F/A-18F Super Hornet",
        "variant_primary": "fov035",  # documented consensus field of view (NAR 2x); fov070 is reported as a sensitivity
    },
    "gofast": {
        "title": "GOFAST (F/A-18F, ATFLIR, January 2015)",
        "derived": "gofast",
        "key": "gofast",
        "manifest": ["gofast_navy2020"],
        "date": "2015-01",
        "date_uncertainty": "Month is public; the exact day and time of day are not pinned down by the lab. "
                            "Weather was taken at 2015-01-25T02:30 UTC as the analysis time.",
        "place": "Atlantic Ocean off the US East Coast",
        "place_note": "No position is shown on screen; the lab holds no coordinates for this clip.",
        "platform": "F/A-18F Super Hornet",
        "variant_primary": "",
    },
    "flir1": {
        "title": "FLIR1 \"Tic Tac\" (F/A-18F, ATFLIR, USS Nimitz group, November 2004)",
        "derived": "flir1_navy",
        "key": "flir1",
        "manifest": ["flir1_navy2020", "flir1_2007_f4"],
        "date": "2004-11-14",
        "date_uncertainty": "Day is public; weather was taken at 2004-11-14T20:30 UTC as the analysis time.",
        "place": "Pacific Ocean off Southern California (USS Nimitz carrier group)",
        "place_note": "No position is shown on screen; the lab holds no coordinates for this clip.",
        "platform": "F/A-18F Super Hornet",
        "variant_primary": "",
    },
}

MODELS_NOTE = (
    "Every hypothesis is fitted by the same code against the same observables with the same noise "
    "model and weights; hypotheses differ only in their physical model and priors."
)


# ---------------------------------------------------------------- helpers

def clean(x):
    """Recursively replace NaN/inf with None so the output is strict JSON."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):  # numpy scalar
        try:
            return clean(x.item())
        except Exception:
            return str(x)
    return x


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def provenance(inputs: list[str]) -> dict:
    version = "0.0.0"
    try:
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except Exception:
        pass
    commit = git("rev-parse", "HEAD") or "0000000"
    dirty = git("status", "--porcelain", "--untracked-files=no")
    return {
        "repo": REPO_URL,
        "commit": commit,
        "working_tree_clean": (dirty == "") if commit != "0000000" else None,
        "lab_version": version,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "tools/export_cases.py",
        "inputs": inputs,
    }


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------- pieces

def manifest_sources(ids: list[str]) -> list[dict]:
    man = (load_json(ROOT / "data" / "videos" / "MANIFEST.json") or {}).get("videos", {})
    out = []
    for i in ids:
        m = man.get(i)
        if not m:
            continue
        stream = next((s for s in (m.get("ffprobe") or {}).get("streams", []) if s.get("codec_type") == "video"),
                      (m.get("ffprobe") or {}).get("streams", [{}])[0] if (m.get("ffprobe") or {}).get("streams") else {})
        media = {k: stream.get(k) for k in ("codec_name", "width", "height", "r_frame_rate", "duration")
                 if stream.get(k) is not None}
        out.append({
            "id": i, "role": "video", "title": f"{m.get('video', i)} ({m.get('file', '')})",
            "file": m.get("file"), "url": m.get("source_url"), "sha256": m.get("sha256"),
            "bytes": m.get("bytes"), "official_copy": m.get("official_copy"),
            "provenance": m.get("provenance", ""), "retrieved": m.get("retrieved"), "media": media,
        })
    return out


def testimony_source(key: str) -> list[dict]:
    p = ROOT / "data" / "testimony" / f"{key}.yaml"
    if not p.exists():
        return []
    return [{"id": f"testimony_{key}", "role": "testimony", "title": f"Public testimony claims for {key}",
             "file": rel(p), "url": None, "sha256": sha256_of(p), "bytes": p.stat().st_size,
             "official_copy": False,
             "provenance": "Hand-extracted paraphrases with per-claim source URLs; see data/testimony/SOURCES.md."}]


def observables(d: Path) -> list[dict]:
    out = []
    s = load_json(d / "symbology_summary.json") or {}
    for name, f in (s.get("fields") or {}).items():
        gap = (f.get("update_gap_frames") or {}).get("median")
        out.append({
            "name": name, "kind": "read_from_screen", "frames": f.get("frames"),
            "resolution": (f"Field updates about every {gap:g} frames (median)" if gap else None),
            "first_value": f.get("first_value"), "last_value": f.get("last_value"),
            "confidence_summary": (f"{f.get('low_confidence', 0)} of {f.get('frames', 0)} frames below the "
                                   f"{s.get('low_conf_threshold', 0.3)} template-match confidence threshold; "
                                   f"{f.get('blank', 0)} blank"),
            "low_confidence_fraction": f.get("low_confidence_frac"),
        })
    t = load_json(d / "image_track_summary.json")
    if t:
        out.append({"name": "image_track", "kind": "measured_from_image",
                    "confidence_summary": "Per-frame blob position, size and brightness; see image_track_summary.json.",
                    "summary": t})
    return out


def sensor_block(res_view: dict, d: Path) -> dict:
    sen = res_view.get("sensor") or {}
    meta = load_json(d / "frames_meta.json") or {}
    fps = meta.get("fps_nominal")
    n = meta.get("n_frames")
    note = ""
    fbf = sen.get("fov_by_frame")
    if fbf:
        note = ("Field of view is read per frame from the display mode: "
                + ", ".join(f"{k} {v} deg" for k, v in (fbf.get("mode_fov_deg") or {}).items())
                + (", divided by the zoom factor" if fbf.get("divide_by_zoom") else "") + ".")
    return {"name": "AN/ASQ-228 ATFLIR", "band": "infrared",
            "field_of_view_deg": sen.get("fov_deg"), "field_of_view_note": note or
            "Fixed value assumed for the whole clip (see analysis.variants).",
            "picture_width_px": sen.get("picture_width_px"), "pixel_aspect": sen.get("pixel_aspect_x"),
            "frame_rate_hz": fps, "duration_s": (n / fps) if (fps and n) else None}


def hypothesis_priors(hid: str) -> str:
    p = ROOT / "solve" / "hypotheses" / f"{hid.lower()}.yaml"
    try:
        y = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    desc = " ".join(str(y.get("description", "")).split())
    params = []
    for k, v in (y.get("parameters") or {}).items():
        if isinstance(v, dict) and "bounds" in v:
            params.append(f"{k} {v.get('prior', '')} {v['bounds']}".replace("  ", " "))
    return (desc + (" Priors: " + "; ".join(params) + "." if params else "")).strip()


_NOEXCL = re.compile(r"(total_physics_only|total_testimony_weighted).*(no_exclusion|without|all_criteria|unexcluded)")


def hypothesis_block(h: dict, variant: str) -> dict:
    hid = h.get("hypothesis") or h.get("id") or "?"
    derived = h.get("derived") or {}
    si = {}
    for k, v in derived.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if k.endswith("_nmi_mean") or k.endswith("_nmi"):
            si[re.sub(r"_nmi(_mean)?$", r"_m\1", k)] = v * NMI_M
        elif k.endswith("_kt") or "_kt_" in k:
            si[k.replace("_kt", "_mps")] = v * KT_MPS
        elif "_ft_" in k or k.endswith("_ft"):
            si[k.replace("_ft", "_m")] = v * FT_M
        elif k.endswith("_fpm"):
            si[k.replace("_fpm", "_mps")] = v * FPM_MPS
    out = {
        "id": hid, "label": h.get("label", hid), "variant": variant, "model": h.get("model"),
        "in_design_set": h.get("in_design_set"), "valid": h.get("valid"),
        "priors_summary": hypothesis_priors(hid), "free_parameters": h.get("k"),
        "best_fit_parameters": h.get("params_testimony_weighted_fit") or {},
        "best_fit_parameters_physics_only": h.get("params_physics_only_fit") or {},
        "parameters_at_bound": h.get("params_at_bound") or [],
        "criteria_log_likelihood": h.get("criteria") or {},
        "criteria_log_likelihood_physics_only": h.get("criteria_physics_only_fit") or {},
        "total_testimony_weighted": h.get("total_testimony_weighted"),
        "total_physics_only": h.get("total_physics_only"),
        "rank_testimony_weighted": h.get("rank_testimony_weighted"),
        "rank_physics_only": h.get("rank_physics_only"),
        "derived": derived, "derived_si": si, "checks": h.get("checks") or [],
    }
    for k, v in h.items():  # robust to new optional fields: pick up totals without post-hoc exclusions
        m = _NOEXCL.search(k)
        if m and isinstance(v, (int, float)):
            out[f"{m.group(1)}_without_post_hoc_exclusions"] = v
    for k in ("rank_physics_only_design_set", "rank_testimony_weighted_design_set", "testimony_status", "n_eval"):
        if k in h:
            out[k] = h[k]
    return out


def range_points(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows or []:
        if r.get("range_nmi") is None:
            continue
        out.append({
            "range_m": r["range_nmi"] * NMI_M, "range_display_nmi": r["range_nmi"], "valid": r.get("valid"),
            "air_speed_mps": _mul(r.get("air_speed_kt"), KT_MPS), "ground_speed_mps": _mul(r.get("ground_speed_kt"), KT_MPS),
            "altitude_m": _mul(r.get("altitude_ft_mean"), FT_M), "vertical_speed_mps": _mul(r.get("vertical_speed_fpm"), FPM_MPS),
            "line_of_sight_log_likelihood": r.get("line_of_sight_loglik"),
        })
    return out


def _mul(x, f):
    return None if x is None else x * f


def range_curves(views: dict[str, dict], primary: str, case_dir: str) -> dict:
    v = views.get(primary) or next(iter(views.values()), {})
    angles = range_points(v.get("range_curve_angles_only") or [])
    per_h = {}
    for k, val in v.items():  # any per-hypothesis curve the scorer adds later
        if k.startswith("range_curve") and k != "range_curve_angles_only" and isinstance(val, dict):
            per_h = {hid: range_points(rows) for hid, rows in val.items() if isinstance(rows, list)}
    note = ("Angles-only curves: for each assumed constant range, the speed, altitude and fit that the "
            "line-of-sight angles imply. Range is not measured in this clip's angles; read the curve, not one number.")
    if not per_h:
        note += " Per-hypothesis curves over range are not in the current outputs."
    return {"available": bool(angles), "note": note, "link": f"data/derived/{case_dir}/results.json",
            "angles_only": angles, "per_hypothesis": per_h}


def discriminators(case_dir: str, key: str) -> list[dict]:
    d = load_json(DERIVED / case_dir / "discriminators.json")
    if not d:
        return []
    try:
        cat = yaml.safe_load((ROOT / "data" / "discriminators" / "notes.yaml").read_text(encoding="utf-8"))["measurements"]
    except Exception:
        cat = {}
    out = []
    for vname, vv in (d.get("variants") or {}).items():
        for pr in vv.get("pairs") or []:
            top = pr.get("top") or {}
            q = top.get("quantity") or ""
            m = cat.get(q.split("@")[0], {})
            why = pr.get("why") or []
            out.append({
                "variant": vname, "pair": [pr.get("a"), pr.get("b")],
                "separable_from_current_data": not any("not separated" in w for w in why) if why else None,
                "measurement": m.get("label") or q or None, "unit": m.get("unit"),
                "quantity_key": q or None, "time_s": top.get("time_s"),
                "required_precision": top.get("required_sigma"), "typical_precision": top.get("typical_sigma"),
                "feasibility": top.get("feasibility"), "works_both_ways": (top.get("kind") == "both") if top else None,
                "data_exists": (m.get("exists") or {}).get(key), "why": why,
            })
    return out


def testimony_block(key: str) -> dict:
    try:
        from solve import testimony as T
        claims = T.load_claims(key)
        mapping = T.load_mapping()["cases"][key]["claims"]
        scorable = [c for c, e in mapping.items() if e.get("scorable")]
        terms = sum(len(e.get("terms") or []) for e in mapping.values() if e.get("scorable"))
        wits = sorted({c["witness"] for c in claims})
        out = {"claims_total": len(claims), "claims_scorable": len(scorable), "scored_terms": terms,
               "witnesses": wits, "link": f"data/testimony/{key}.yaml",
               "claims_summary": (f"{len(claims)} claims from {len(wits)} witnesses or records; "
                                  f"{len(scorable)} constrain a quantity the models predict ({terms} scored terms). "
                                  "Each is a paraphrase with a source; testimony is applied identically to every hypothesis.")}
        try:
            w = T.witness_consistency(key)
            c = Counter(w["status"])
            out["witness_consistency"] = {"agree": c.get("agree", 0), "partial": c.get("partial", 0),
                                          "disagree": c.get("disagree", 0), "total": int(len(w)),
                                          "note": "Memory of on-screen numbers against the record; reported separately and never changes a score."}
        except Exception:
            pass
        return out
    except Exception as e:  # tolerate a changed testimony module
        return {"claims_total": 0, "claims_scorable": 0, "scored_terms": 0, "claims_summary": f"unavailable: {e}"}


def post_hoc(flags: list[str]) -> list[dict]:
    out = []
    for f in flags:
        if re.match(r"(D-016|D-017|REVIEW-M3 Rule B)", f):
            out.append({"id": f.split(":")[0], "description": f, "decided_blind": False})
    return out


def build_verdict(hyps: list[dict], primary: str, flags: list[str], case_label: str, has_excl_totals: bool) -> dict:
    pool = [h for h in hyps if h["variant"] == primary and h.get("valid") is not False
            and isinstance(h.get("total_physics_only"), (int, float))]
    pool.sort(key=lambda h: h["total_physics_only"], reverse=True)
    conditions = [
        "Range is not measured in this clip; conclusions hold over the stated range support (0.5 to 60 nmi), not at one range.",
        "Scores are log-likelihoods under the lab's noise model; a gap of 2.3 is a likelihood ratio of 10.",
        MODELS_NOTE,
    ]
    conditions += flags
    if not has_excl_totals:
        conditions.append("Some data-quality rules (zero weight for saturated or unresolved size and brightness) were "
                          "not decided blind; totals without them are not yet in these outputs.")
    if len(pool) < 2:
        return {"text": f"{case_label}: fewer than two scored hypotheses; no ranking is stated.",
                "conditions": conditions, "decisive": False, "leader_physics_only": None, "margin_log_likelihood": None}
    lead, nxt = pool[0], pool[1]
    margin = lead["total_physics_only"] - nxt["total_physics_only"]
    tied = [h["id"] for h in pool[1:] if lead["total_physics_only"] - h["total_physics_only"] < LR10]
    # Not decisive while post-hoc exclusions exist and totals without them are not reported (CP-04 review).
    pending = bool(post_hoc(flags)) and not has_excl_totals
    decisive = margin >= LR10 and not pending
    if margin >= LR10 and pending:
        text = (f"On the video alone (physics-only), {lead['label']} scores highest, ahead of the next explanation "
                f"by {margin:.1f} log units, but this is not called decisive: the lead depends on data-quality rules "
                "applied after results were seen, and totals without them are not yet reported.")
    elif decisive:
        text = (f"On the video alone (physics-only), {lead['label']} scores highest, ahead of the next "
                f"explanation by {margin:.1f} log units (a likelihood ratio above 10). That is the conditional "
                "result under the models and conditions listed; it is not an identification.")
    else:
        text = (f"The data do not separate the explanations. {lead['label']} scores highest on the video alone "
                f"(physics-only) but only by {margin:.1f} log units over {nxt['label']}, under the 2.3 needed for a "
                f"likelihood ratio of 10; within that margin: {', '.join(tied) if tied else 'none besides the runner-up'}. "
                "See the discriminators for the measurement that would separate them.")
    return {"text": text, "conditions": conditions, "decisive": decisive,
            "leader_physics_only": lead["id"], "margin_log_likelihood": margin}


# ---------------------------------------------------------------- video case

def results_views(res: dict) -> dict[str, dict]:
    """Normalize results.json to {variant: case-like dict}. GIMBAL nests variants; the others are flat."""
    if "variants" in res and isinstance(res["variants"], dict):
        return res["variants"]
    return {"": res}


def build_video_case(case_id: str, cfg: dict) -> dict | None:
    d = DERIVED / cfg["derived"]
    res = load_json(d / "results.json")
    if not res:
        return None
    views = results_views(res)
    primary = cfg.get("variant_primary", "")
    if primary not in views:
        primary = next(iter(views))
    pv = views[primary]
    hyps = [hypothesis_block(h, vname) for vname, v in views.items() for h in v.get("hypotheses", [])]
    weights = pv.get("weights") or {}
    for h in hyps:
        h["criteria_weights"] = weights
    flags = list(pv.get("flags") or [])
    excl = post_hoc(flags)
    has_excl = any(k.endswith("_without_post_hoc_exclusions") for h in hyps for k in h)
    sources = manifest_sources(cfg["manifest"]) + testimony_source(cfg["key"])
    sources.append({"id": "weather_era5", "role": "weather", "title": "ERA5 reanalysis wind and temperature",
                    "file": None, "url": "https://cloud.google.com/storage/docs/public-datasets/era5", "sha256": None,
                    "provenance": (pv.get("environment") or {}).get("source", "ERA5")})
    sig_kt = (pv.get("environment") or {}).get("wind_sigma_kt")
    verdict = build_verdict(hyps, primary, flags, cfg["title"], has_excl)
    return {
        "schema_version": "0.1", "case_id": case_id, "kind": "video_case", "title": cfg["title"],
        "summary": (f"Forensic reconstruction of {cfg['title']}: the jet path, line of sight and field of view per "
                    "frame, scored against each candidate explanation with identical geometry and weights."),
        "event": {"date": cfg["date"], "date_uncertainty": cfg["date_uncertainty"], "place": cfg["place"],
                  "latitude_deg": None, "longitude_deg": None, "position_uncertainty_m": None,
                  "position_note": cfg["place_note"]},
        "platform": {"name": cfg["platform"], "aircraft_or_ship": cfg["platform"],
                     "note": "Jet heading is not on screen and is fitted; altitude comes from the display where legible."},
        "sensor": sensor_block(pv, d),
        "sources": sources,
        "observables": observables(d),
        "environment": {"weather_source": (pv.get("environment") or {}).get("source"),
                        "wind_uncertainty_mps": _mul(sig_kt, KT_MPS),
                        "note": "Wind at the object's altitude carries this uncertainty for every hypothesis."},
        "analysis": {
            "method": "Maximum-likelihood multi-start fit per hypothesis; BIC-style complexity penalty; same code and weights for all.",
            "frame_window": pv.get("window_frames"), "reference_frame": pv.get("reference_frame"),
            "primary_variant": primary,
            "variants": [{"id": k, "description": (f"Sensor field of view {v.get('sensor', {}).get('fov_deg')} deg" if k else "Single analysis")}
                         for k, v in views.items()],
            "effective_sample_size": pv.get("n_eff_total"),
            "log_likelihood_note": "Natural log; higher is better; a difference of 2.3 is a likelihood ratio of 10.",
            "flags": flags, "post_hoc_exclusions": excl,
            "totals_without_post_hoc_exclusions_available": has_excl,
        },
        "hypotheses": hyps,
        "range_curves": range_curves(views, primary, cfg["derived"]),
        "discriminators": discriminators(cfg["derived"], cfg["key"]),
        "testimony": testimony_block(cfg["key"]),
        "verdict": verdict,
        "provenance": provenance([rel(d / "results.json"), rel(d / "scores.csv"), rel(d / "discriminators.json"),
                                  "data/videos/MANIFEST.json", f"data/testimony/{cfg['key']}.yaml"]),
        "notes": f"See docs/results/{cfg['key']}.md for the full write-up. Environment source: "
                 f"{(pv.get('environment') or {}).get('source', 'n/a')}.",
    }


# ---------------------------------------------------------------- PURSUE

def build_triage() -> dict | None:
    p = ROOT / "data" / "pursue" / "triage.csv"
    if not p.exists():
        return None
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    tiers = Counter(r["tier"] for r in rows)
    rels = Counter(r["release"] for r in rows)
    n = len(rows)
    bounded = tiers.get("Bounded", 0)
    text = (f"Of {n} PURSUE sensor videos triaged, {bounded} support at most a bounded reconstruction and "
            f"{n - bounded} are not viable (most on-screen data is redacted and there is no known scale). "
            "No clip in this triage is claimed to identify its object.")
    return {
        "schema_version": "0.1", "case_id": "pursue-triage", "kind": "triage_summary",
        "title": f"PURSUE sensor videos: viability triage ({n} clips)",
        "summary": "Which of the 2026 PURSUE releases carry enough on-screen data to reconstruct anything, and how much.",
        "event": {"date": None, "date_uncertainty": "Many events across Releases 01 to 06; dates are per clip.",
                  "place": None, "position_note": "Per clip, mostly not stated."},
        "sources": [{"id": "pursue_triage_csv", "role": "data", "title": "Hand-built clip-by-clip triage table",
                     "file": rel(p), "url": None, "sha256": sha256_of(p), "bytes": p.stat().st_size,
                     "official_copy": False,
                     "provenance": "Built by the lab from the released videos; see data/pursue/ for the index checks."}],
        "triage": {"clips_total": n, "by_tier": dict(tiers), "by_release": dict(rels),
                   "clips": [{"clip_id": r["clip_id"], "release": r.get("release"), "tier": r["tier"],
                              "reason": r.get("reason", ""), "sensor_guess": r.get("sensor_guess"),
                              "resolution": r.get("resolution"), "duration_s": _num(r.get("duration_s")),
                              "symbology_redacted": r.get("symbology_redacted")} for r in rows]},
        "verdict": {"text": text, "decisive": False,
                    "conditions": ["Tiers are about what the data could support, not about what the objects are.",
                                   "Triage is by sampled frames and the released symbology; a re-check at frame level can change a tier."],
                    "leader_physics_only": None, "margin_log_likelihood": None},
        "provenance": provenance(["data/pursue/triage.csv"]),
        "notes": "Frozen clips that are fully scored export as their own clip_case files.",
    }


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pursue_clip_cases() -> list[dict]:
    root = DERIVED / "pursue"
    if not root.is_dir():
        return []
    tri = {}
    p = ROOT / "data" / "pursue" / "triage.csv"
    if p.exists():
        with p.open(encoding="utf-8", newline="") as f:
            tri = {r["clip_id"]: r for r in csv.DictReader(f)}
    out = []
    for d in sorted(x for x in root.iterdir() if x.is_dir() and (x / "results.json").exists()):
        row = next((r for cid, r in tri.items() if cid.lower() == d.name.lower()), {})
        cfg = {"title": f"PURSUE clip {row.get('clip_id', d.name)}", "derived": f"pursue/{d.name}", "key": d.name,
               "manifest": [], "date": None, "date_uncertainty": "Not stated on screen.", "place": None,
               "place_note": "Not stated.", "platform": row.get("platform_guess") or "unspecified",
               "variant_primary": ""}
        c = build_video_case(re.sub(r"[^a-z0-9_.-]", "-", d.name.lower()), cfg)
        if c is None:
            continue
        c["kind"] = "clip_case"
        meta = load_json(d / "frames_meta.json") or {}
        if meta.get("source_sha256"):
            c["sources"].insert(0, {"id": "clip", "role": "video", "title": row.get("file") or d.name,
                                    "file": meta.get("source_video"), "url": None, "sha256": meta["source_sha256"],
                                    "provenance": "PURSUE release file as frozen by the lab."})
        if row:
            c["notes"] += f" Triage tier: {row.get('tier')}. {row.get('reason', '')}"
        out.append(c)
    return out


# ---------------------------------------------------------------- main

def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for cid, cfg in CASES.items():
        c = build_video_case(cid, cfg)
        if c:
            cases.append(c)
    t = build_triage()
    if t:
        cases.append(t)
    cases += pursue_clip_cases()
    paths = []
    for c in cases:
        p = out_dir / f"{c['case_id']}.json"
        p.write_text(json.dumps(clean(c), indent=1, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(p)
    return paths


def main(argv: list[str]) -> int:
    out = ROOT / "exports" / "cases"
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
    for p in export_all(out):
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
