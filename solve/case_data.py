"""Case loader for M3 scoring: observations, jet inputs and environment for one video.

Everything a hypothesis is scored against lives in a CaseData built from
solve/cases/<case>.yaml. Nothing here depends on which hypothesis is scored. The
data-only effective sample sizes and measurement sigmas are computed once here, so
every hypothesis gets exactly the same n_eff and noise on a case.

Weather: ERA5 through solve.weather (wind_at / temperature_at) when the case's
profile file exists; otherwise the configured placeholder (a radiosonde profile),
FLAGGED in `env.flags` and in every output.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import atmosphere as A
from . import frames as F
from . import likelihoods as L
from .repro_gofast import _lab_series

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = Path(__file__).resolve().parent / "cases"
SCORING_YAML = Path(__file__).resolve().parent / "scoring.yaml"


@lru_cache(maxsize=None)
def scoring_config() -> dict:
    return yaml.safe_load(SCORING_YAML.read_text(encoding="utf-8"))


@dataclass
class Environment:
    wind_heights_m: np.ndarray
    wind_u: np.ndarray            # m/s eastward, on wind_heights_m
    wind_v: np.ndarray            # m/s northward
    wind_sigma_kt: float
    dT_jet: float                 # K, temperature offset from ISA at the jet's altitude
    source: str
    flags: list = field(default_factory=list)

    def wind_enu(self, h_m) -> np.ndarray:
        """Horizontal wind (m/s, the direction the air moves TOWARD) at heights h_m: shape (..., 2)."""
        h = np.asarray(h_m, float)
        u = np.interp(h, self.wind_heights_m, self.wind_u)
        v = np.interp(h, self.wind_heights_m, self.wind_v)
        return np.stack([u, v], axis=-1)


@dataclass
class Readout:
    name: str
    frames: np.ndarray        # frame indices scored
    obs: np.ndarray           # readout values at those frames
    step: float
    n_eff: float


@dataclass
class Series:
    name: str
    frames: np.ndarray
    obs: np.ndarray           # for size / brightness: log values; for background: px/frame
    segment: np.ndarray       # segment id per sample (polarity run); -1 if not segmented
    sigma: float              # data-derived measurement sigma
    n_eff: float


@dataclass
class CaseData:
    name: str
    cfg: dict
    fps: float
    t: np.ndarray                 # s, all frames
    window: np.ndarray            # frame indices scored
    ref_frame: int
    az_read: np.ndarray           # deg, all frames (nan where blank)
    el_read: np.ndarray
    tas: np.ndarray               # m/s, all frames
    bank: np.ndarray              # deg, smoothed
    jet_alt: np.ndarray           # m
    ppd: float                    # px per deg (horizontal)
    readouts: dict                # name -> Readout
    series: dict                  # name -> Series
    brightness_log_all: np.ndarray  # log observed brightness, all frames (nan where not found)
    size_px_all: np.ndarray
    env: Environment
    criteria: list
    shared_parameters: dict
    flags: list
    variant: str = ""                         # sensor setting run (e.g. a field of view), shared by all hypotheses
    turn_rate: np.ndarray | None = None       # deg/s per frame, when the case supplies a measured turn-rate history
    turn_rate_sigma: np.ndarray | None = None # deg/s per frame, 1 sigma of that history (from its 95 percent band)
    weight_overrides: dict = field(default_factory=dict)  # case-level, e.g. D-016 (size not resolved: weight 0)
    rotation_knots: tuple = ()                # candidate knot counts of a physical object's free rotation spline

    @property
    def n_eff_total(self) -> float:
        """Sum of the physics criteria's data-only n_eff (the BIC n).

        A criterion this case gives weight 0 (D-016, REVIEW-M3 Rule B) is reported but not in any
        total, so its observations do not count in the BIC n either (REVIEW-M3).
        """
        tot = 0.0
        for c in self.criteria:
            if float(self.weight_overrides.get(c, 1.0)) == 0.0:
                continue
            if c == "line_of_sight":
                tot += self.readouts["azimuth"].n_eff + self.readouts["elevation"].n_eff
            elif c in self.readouts:
                tot += self.readouts[c].n_eff
            elif c in self.series:
                tot += self.series[c].n_eff
        return tot


# ----------------------------------------------------------------------------- environment


def _igra_profile(path: Path, time: str):
    d = pd.read_csv(path)
    d = d[d["time"] == time].dropna(subset=["height_m", "wind_speed_ms", "wind_dir_deg"])
    d = d.sort_values("height_m").drop_duplicates("height_m")
    if d.empty:
        raise ValueError(f"no sounding at {time} in {path}")
    sp = d["wind_speed_ms"].to_numpy(float)
    dr = np.radians(d["wind_dir_deg"].to_numpy(float))
    return d["height_m"].to_numpy(float), -sp * np.sin(dr), -sp * np.cos(dr)


def load_environment(cfg: dict, jet_alt_m: float) -> Environment:
    w = cfg["weather"]
    heights = np.arange(0.0, 15_001.0, 250.0)
    try:
        from . import weather as W

        W.load_profiles(w["event"])  # raises FileNotFoundError when ERA5 is not fetched yet
        uv = np.array([W.wind_at(w["event"], w["time_utc"], h) for h in heights])
        t_k = W.temperature_at(w["event"], w["time_utc"], jet_alt_m, ref="pressure_altitude")
        dT = float(t_k - A.isa(np.array(jet_alt_m))[0])
        return Environment(heights, uv[:, 0], uv[:, 1], float(w["wind_sigma_kt_era5"]), dT,
                           source=f"ERA5 {w['event']} at {w['time_utc']} UTC (box centre)", flags=[])
    except (FileNotFoundError, KeyError, ValueError, ImportError) as e:
        p = w["placeholder"]
        hh, u, v = _igra_profile(ROOT / p["file"], p["time"])
        flags = [f"PLACEHOLDER WIND: ERA5 for '{w['event']}' not available ({type(e).__name__}); "
                 f"using radiosonde {Path(p['file']).name} at {p['time']} with wind sigma {p['wind_sigma_kt']} kt. "
                 f"Temperature: ISA (no ERA5)."]
        return Environment(hh, u, v, float(p["wind_sigma_kt"]), 0.0,
                           source=f"placeholder: {Path(p['file']).name} {p['time']}", flags=flags)


# ----------------------------------------------------------------------------- loading


def _data_n_eff(t: np.ndarray, y: np.ndarray, degree: int) -> float:
    return L.n_eff_autocorr(L.smooth_residual(t, y, degree))


def derived_dir(name: str) -> Path:
    """Where a case's derived tables live: the case YAML's `derived_dir` (FLIR1: data/derived/flir1_navy, next
    to its M1 readings), else data/derived/<case>."""
    p = CASE_DIR / f"{name}.yaml"
    if p.exists():
        d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("derived_dir")
        if d:
            return ROOT / d
    return ROOT / "data" / "derived" / name


def _sym_strings(sym: pd.DataFrame, field: str, n: int) -> np.ndarray:
    """A symbology field as strings on every frame (blank where absent)."""
    s = sym[sym["field"] == field].set_index("frame")["value"].reindex(range(n))
    return np.array(["" if pd.isna(v) else str(v) for v in s.to_numpy()], dtype=object)


def _segment_ids(keys: list, cues: pd.DataFrame, sym: pd.DataFrame, n: int, polarity_column: str) -> np.ndarray:
    """Segment id per frame: a new segment at every change of any listed key. "polarity" is the image track's
    polarity column; any other key is a symbology field (e.g. sensor, zoom, FOV mode)."""
    cols = []
    for k in keys:
        if k == "polarity":
            cols.append(np.array(["" if pd.isna(v) else str(v) for v in cues[polarity_column].to_numpy()[:n]],
                                 dtype=object))
        else:
            cols.append(_sym_strings(sym, k, n))
    tup = np.array(["|".join(v) for v in zip(*cols)]) if cols else np.full(n, "")
    return _segments(tup)


def fov_per_frame(cfg: dict, sym: pd.DataFrame, n: int) -> np.ndarray | None:
    """Field of view (deg) on every frame from the on-screen FOV mode and zoom (sensor.fov_by_frame), or None
    when the case has one fixed field. Unknown modes (e.g. an unresolved MFOV / WFOV word) give nan."""
    fb = cfg["sensor"].get("fov_by_frame")
    if not fb:
        return None
    mode = _sym_strings(sym, fb["mode_field"], n)
    table = {str(k): float(v) for k, v in fb["mode_fov_deg"].items()}
    fov = np.array([table.get(m, np.nan) for m in mode])
    if fb.get("divide_by_zoom", False):
        z = pd.to_numeric(pd.Series(_sym_strings(sym, fb["zoom_field"], n)), errors="coerce").to_numpy(float)
        fov = fov / z
    return fov


def _segments(pol: np.ndarray) -> np.ndarray:
    seg = np.zeros(len(pol), int)
    for i in range(1, len(pol)):
        seg[i] = seg[i - 1] + (pol[i] != pol[i - 1])
    return seg


def case_variants(name: str) -> list[str]:
    """Names of the case's sensor-setting runs (sensor_variants in its YAML); [""] if it has none."""
    cfg = yaml.safe_load((CASE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return [str(v["name"]) for v in cfg.get("sensor_variants", [])] or [""]


def _apply_variant(cfg: dict, variant: str | None) -> tuple[dict, str]:
    vs = cfg.get("sensor_variants") or []
    if not vs:
        return cfg, ""
    v = vs[0] if not variant else next(x for x in vs if str(x["name"]) == str(variant))
    cfg = copy.deepcopy(cfg)
    for k, val in (v.get("sensor") or {}).items():
        cfg["sensor"][k] = val
    for block in ("jet", "image"):
        for k, val in (v.get(block) or {}).items():
            if isinstance(val, dict):
                cfg[block].setdefault(k, {}).update(val)
            else:
                cfg[block][k] = val
    return cfg, str(v["name"])


def _running_median_sigma(y: np.ndarray, seg: np.ndarray, w: int) -> float:
    """Measurement scatter: pooled standard deviation about a w-frame running median, per segment."""
    parts = []
    for s in np.unique(seg):
        m = seg == s
        yy = pd.Series(y[m])
        r = (yy - yy.rolling(w, center=True, min_periods=1).median()).to_numpy()
        parts.append((m.sum(), float(np.nanstd(r))))
    tot = sum(k for k, _ in parts)
    return float(np.sqrt(sum(k * v ** 2 for k, v in parts) / tot))


def load_case(name: str, env: Environment | None = None, variant: str | None = None) -> CaseData:
    cfg = yaml.safe_load((CASE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    cfg, variant_name = _apply_variant(cfg, variant)
    sc = scoring_config()
    deg = int(sc["autocorrelation"]["smooth_degree"])
    n = int(cfg["n_frames"])
    fps = float(cfg["fps"])
    t = np.arange(n) / fps
    sym = pd.read_csv(ROOT / cfg["files"]["symbology"], dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    summ = json.loads((ROOT / cfg["files"]["symbology_summary"]).read_text(encoding="utf-8"))
    cues = pd.read_csv(ROOT / cfg["files"]["image_track"])
    flags: list = []

    # Window.
    tw = cfg["track_window"]
    present = ~np.isnan(_lab_series(cfg["readouts"][tw["field"]]["field"], sym))
    window = np.flatnonzero(present)

    # Jet inputs.
    j = cfg["jet"]
    alt_m = _lab_series(j["altitude_field"], sym) * F.FT
    mach = _lab_series(j["mach_field"], sym)
    bank_raw = cues[j["bank_column"]].to_numpy(float)
    bank = pd.Series(bank_raw).rolling(int(j["bank_smooth_frames"]), center=True, min_periods=1).mean().to_numpy()
    if env is None:
        env = load_environment(cfg, float(np.nanmedian(alt_m)))
    tas = A.mach_to_tas(mach, alt_m, env.dT_jet)
    turn_rate = turn_sigma = None
    tr = j.get("turn_rate")
    if tr:
        d = pd.read_csv(ROOT / tr["file"]).sort_values("frame")
        turn_rate = d[tr["column"]].to_numpy(float)[:n]
        z95 = float(tr.get("band_z", 1.959964))
        turn_sigma = (d[tr["hi_column"]].to_numpy(float) - d[tr["lo_column"]].to_numpy(float))[:n] / (2.0 * z95)

    # Readouts.
    mod = int(cfg["update_modulus"])
    readouts: dict = {}
    # Display rounding convention (D-016): a sensor setting shared by every hypothesis. "round": a
    # whole-degree readout v means [v - 0.5, v + 0.5]; "floor" (truncation toward minus infinity):
    # [v, v + 1), i.e. the interval centre is v + 0.5.
    rounding = str(cfg.get("display_rounding", "round"))
    if rounding not in ("round", "floor"):
        raise ValueError(f"display_rounding must be round or floor, not {rounding!r}")
    shift = {k: (0.5 * float(r["step"]) if rounding == "floor" and k in ("azimuth", "elevation") else 0.0)
             for k, r in cfg["readouts"].items()}
    az_all = _lab_series(cfg["readouts"]["azimuth"]["field"], sym) + shift["azimuth"]
    el_all = _lab_series(cfg["readouts"]["elevation"]["field"], sym) + shift["elevation"]
    for key, r in cfg["readouts"].items():
        vals = _lab_series(r["field"], sym) + shift.get(key, 0.0)
        fr = window
        if r["update"] in ("summary_phase", "phase_of"):
            # phase_of: a readout that never changes on screen shares another field's display update.
            src = r["field"] if r["update"] == "summary_phase" else r["phase_field"]
            ph = summ["fields"][src]["change_frame_phase"]["dominant_residue"]
            fr = window[(window % mod) == ph]
        fr = fr[np.isfinite(vals[fr])]
        readouts[key] = Readout(key, fr, vals[fr], float(r["step"]), _data_n_eff(t[fr], vals[fr], deg))

    # Reference frame: the azimuth update frame nearest the middle of the window.
    upd = readouts["azimuth"].frames
    ref = int(upd[np.argmin(np.abs(upd - 0.5 * (window[0] + window[-1])))])

    # Image cues.
    im = cfg["image"]
    # Segments ("within one polarity", design table). A case may also split at other on-screen settings that
    # change the blob's scale or gain for any source (FLIR1: sensor, zoom, FOV mode); default: polarity only.
    seg_all = _segment_ids(list(im.get("segment_by", ["polarity"])), cues, sym, n, im["polarity_column"])
    found = cues[im["found_column"]].to_numpy(int) == 1
    # Frames excluded from every image series (FLIR1: the unresolved MFOV / WFOV stretch); readouts are kept.
    for a, b in im.get("exclude_frames", []) or []:
        found[int(a):int(b) + 1] = False
    size_px = np.where(found, cues[im["size_column"]].to_numpy(float), np.nan)
    # A field of view that changes on screen (FLIR1 zoom and FOV mode): image sizes are expressed in px at the
    # case's reference field (sensor.fov_deg), so one px-per-degree scale holds on every frame.
    fov_f = fov_per_frame(cfg, sym, n)
    if fov_f is not None:
        size_px = size_px * fov_f / float(cfg["sensor"]["fov_deg"])
    bright = np.where(found, cues[im["brightness_column"]].to_numpy(float), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        size_log = np.log(np.where(size_px > 0, size_px, np.nan))
        bright_log = np.log(np.where(bright > 0, bright, np.nan))
    series: dict = {}
    minseg = int(im["min_segment_frames"])
    for key, y_all in (("size_trend", size_log), ("brightness_trend", bright_log)):
        fr = window[np.isfinite(y_all[window])]
        segs = seg_all[fr]
        keep = np.zeros(len(fr), bool)
        for s in np.unique(segs):
            if (segs == s).sum() >= minseg:
                keep |= segs == s
        fr, segs = fr[keep], segs[keep]
        y = y_all[fr]
        resid = np.full(len(fr), np.nan)
        diffs_sig = []
        for s in np.unique(segs):
            m = segs == s
            resid[m] = L.smooth_residual(t[fr[m]], y[m], deg)
            diffs_sig.append((m.sum(), float(np.nanstd(resid[m]))))
        wsum = sum(k for k, _ in diffs_sig)
        sigma = float(np.sqrt(sum(k * s ** 2 for k, s in diffs_sig) / wsum))
        series[key] = Series(key, fr, y, segs, sigma, L.n_eff_autocorr(resid))

    # Image rotation of the object (rotation criterion): measured orientation of the blob's major axis
    # (deg, CCW, image y up). Noise: scatter about a running median (the series has real steps, so a
    # low-order fit is not a noise estimate); n_eff: the standard rule (autocorrelation about a cubic
    # per polarity segment), the same for every hypothesis.
    rotation_knots: tuple = ()
    if "rotation" in cfg["criteria"]:
        rc = cfg["rotation"]
        ok = found.copy()
        # Optional quality rule (FLIR1): orientation only where the blob is elongated, large and bright enough.
        if "min_elongation" in rc:
            ma, mi = (cues[c].to_numpy(float) for c in rc["elongation_columns"])
            with np.errstate(divide="ignore", invalid="ignore"):
                ok &= (ma / mi) >= float(rc["min_elongation"])
        if "min_area_px" in rc:
            ok &= cues[rc["area_column"]].to_numpy(float) >= float(rc["min_area_px"])
        if "min_snr" in rc:
            ok &= cues[rc["snr_column"]].to_numpy(float) >= float(rc["min_snr"])
        ang = np.where(ok, cues[rc["orientation_column"]].to_numpy(float), np.nan)
        fr = window[np.isfinite(ang[window])]
        rseg = (_segment_ids(list(rc["segment_by"]), cues, sym, n, im["polarity_column"])
                if "segment_by" in rc else seg_all)
        segs = rseg[fr]
        y = np.unwrap(ang[fr], period=180.0)   # axial angle: continuous series
        resid = np.full(len(fr), np.nan)
        for sg in np.unique(segs):
            m = segs == sg
            resid[m] = L.smooth_residual(t[fr[m]], y[m], deg)
        sigma = _running_median_sigma(y, segs, int(rc["noise_window_frames"]))
        series["rotation"] = Series("rotation", fr, y, segs, sigma, L.n_eff_autocorr(resid))
        k = rc["physical_spline_knots"]
        rotation_knots = tuple(int(x) for x in (k if isinstance(k, list) else [k]))

    sens = cfg["sensor"]
    ppd = float(sens["picture_width_px"]) / float(sens["fov_deg"])
    if im.get("background_mode", "image_motion") == "image_motion":
        bx, by = im["background_columns"]
        bgx = cues[bx].to_numpy(float) / float(sens.get("pixel_aspect_x", 1.0))
        bgy = cues[by].to_numpy(float)
        bg = np.hypot(bgx, bgy)
        fr = window[np.isfinite(bg[window])]
        series["background_motion"] = Series("background_motion", fr, bg[fr], np.full(len(fr), -1),
                                             float(np.nanstd(L.smooth_residual(t[fr], bg[fr], deg))),
                                             _data_n_eff(t[fr], bg[fr], deg))
    elif im["background_mode"] not in ("turn_rate_band", "none"):
        # turn_rate_band: background motion enters through the jet's measured turn-rate nuisance (GIMBAL);
        # none: not measurable on this clip, no background criterion (FLIR1).
        raise ValueError(f"unknown background_mode {im['background_mode']!r}")

    # D-016: the size criterion carries weight only for a resolved object (blob major axis at least
    # 3 times the point-spread width measured on the same video). Applied when the case states it.
    weight_overrides: dict = {}
    if "psf_file" in im:
        # REVIEW-M3 item 4: the point-spread width measured on this video (extract/psf.py), in the size
        # criterion's own metric, for this sensor variant (the upper bound: Rule P).
        pj = json.loads((ROOT / im["psf_file"]).read_text(encoding="utf-8"))
        im = dict(im, psf_width_px=float(pj["variants"][variant_name or "default"]["psf_width_px_lo_metric"]))
    if "psf_width_px" in im:
        psf = im["psf_width_px"]
        major = float(np.nanmedian(size_px[window]))
        if psf is None or major < 3.0 * float(psf):
            weight_overrides["size_trend"] = 0.0
            why = ("point-spread width not measured on this video" if psf is None else
                   f"blob major axis {major:.1f} px is under 3 x the point-spread width {float(psf):.1f} px")
            flags.append(f"D-016: apparent-size criterion reported with weight 0 ({why}); resolution not established.")
        else:
            # D-017 (owner ruling): a resolved blob whose size comes from a saturated (clipped) blob is not
            # range-informative either. Same saturation flag and limit as the brightness audit's B1, on the
            # size criterion's own scored frames; the same for every hypothesis.
            from .brightness_audit import SAT_LIMIT, frame_levels_path, saturated_flags
            if frame_levels_path(name).exists():
                sat_frac = float(saturated_flags(name, series["size_trend"].frames).mean())
                if sat_frac > SAT_LIMIT:
                    weight_overrides["size_trend"] = 0.0
                    flags.append(f"D-017: apparent-size criterion reported with weight 0 (resolved, but the blob is "
                                 f"saturated on {100 * sat_frac:.0f} percent of its scored frames, over the "
                                 f"{100 * SAT_LIMIT:.0f} percent limit of Rule B1); size is clipped, not range-informative.")
            else:
                flags.append("D-017: blob saturation not measured on this video (no frame_levels.csv); "
                             "apparent-size criterion kept.")

    # REVIEW-M3 item 1 (Rule B): the brightness criterion carries weight only when the audit found the
    # measured brightness range-informative (not saturated, not dominated by frame-level gain or level,
    # no zoom change). The decision is the audit's (solve/brightness_audit.py), the same for every hypothesis.
    if im.get("brightness_audit") and not (ROOT / im["brightness_audit"]).exists():
        # Only while the audit itself is being run (it loads the case to read the scored series).
        flags.append("REVIEW-M3 Rule B: brightness audit not yet run on this case; brightness criterion kept.")
    elif im.get("brightness_audit"):
        ba = json.loads((ROOT / im["brightness_audit"]).read_text(encoding="utf-8"))
        if not ba.get("range_informative", True):
            weight_overrides["brightness_trend"] = 0.0
            flags.append("REVIEW-M3 Rule B: brightness criterion reported with weight 0 (" + "; ".join(ba["fails"]) +
                         f": blob saturated on {100 * ba['B1']['saturated_fraction']:.0f} percent of scored frames, "
                         f"gain and level explain {100 * ba['B2']['r2_adjusted_n_eff']:.0f} percent of its variance); "
                         "not range-informative.")

    flags += env.flags
    return CaseData(name=name, cfg=cfg, fps=fps, t=t, window=window, ref_frame=ref, az_read=az_all, el_read=el_all,
                    tas=tas, bank=bank, jet_alt=alt_m, ppd=ppd, readouts=readouts, series=series,
                    brightness_log_all=bright_log, size_px_all=size_px, env=env,
                    criteria=list(cfg["criteria"]), shared_parameters=dict(cfg["shared_parameters"]), flags=flags,
                    variant=variant_name, turn_rate=turn_rate, turn_rate_sigma=turn_sigma,
                    weight_overrides=weight_overrides, rotation_knots=rotation_knots)
