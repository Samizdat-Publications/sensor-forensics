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
        """Sum of the physics criteria's data-only n_eff (the BIC n)."""
        tot = 0.0
        for c in self.criteria:
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
    for k, val in (v.get("jet") or {}).items():
        if isinstance(val, dict):
            cfg["jet"].setdefault(k, {}).update(val)
        else:
            cfg["jet"][k] = val
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
    pol = cues[im["polarity_column"]].astype(str).to_numpy()
    seg_all = _segments(pol)
    found = cues[im["found_column"]].to_numpy(int) == 1
    size_px = np.where(found, cues[im["size_column"]].to_numpy(float), np.nan)
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
        ang = np.where(found, cues[rc["orientation_column"]].to_numpy(float), np.nan)
        fr = window[np.isfinite(ang[window])]
        segs = seg_all[fr]
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
    elif im["background_mode"] != "turn_rate_band":
        raise ValueError(f"unknown background_mode {im['background_mode']!r}")

    # D-016: the size criterion carries weight only for a resolved object (blob major axis at least
    # 3 times the point-spread width measured on the same video). Applied when the case states it.
    weight_overrides: dict = {}
    if "psf_width_px" in im:
        psf = im["psf_width_px"]
        major = float(np.nanmedian(size_px[window]))
        if psf is None or major < 3.0 * float(psf):
            weight_overrides["size_trend"] = 0.0
            why = ("point-spread width not measured on this video" if psf is None else
                   f"blob major axis {major:.1f} px is under 3 x the point-spread width {float(psf):.1f} px")
            flags.append(f"D-016: apparent-size criterion reported with weight 0 ({why}); resolution not established.")

    flags += env.flags
    return CaseData(name=name, cfg=cfg, fps=fps, t=t, window=window, ref_frame=ref, az_read=az_all, el_read=el_all,
                    tas=tas, bank=bank, jet_alt=alt_m, ppd=ppd, readouts=readouts, series=series,
                    brightness_log_all=bright_log, size_px_all=size_px, env=env,
                    criteria=list(cfg["criteria"]), shared_parameters=dict(cfg["shared_parameters"]), flags=flags,
                    variant=variant_name, turn_rate=turn_rate, turn_rate_sigma=turn_sigma,
                    weight_overrides=weight_overrides, rotation_knots=rotation_knots)
