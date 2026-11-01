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


def load_case(name: str, env: Environment | None = None) -> CaseData:
    cfg = yaml.safe_load((CASE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
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

    # Readouts.
    mod = int(cfg["update_modulus"])
    readouts: dict = {}
    az_all = _lab_series(cfg["readouts"]["azimuth"]["field"], sym)
    el_all = _lab_series(cfg["readouts"]["elevation"]["field"], sym)
    for key, r in cfg["readouts"].items():
        vals = _lab_series(r["field"], sym)
        fr = window
        if r["update"] == "summary_phase":
            ph = summ["fields"][r["field"]]["change_frame_phase"]["dominant_residue"]
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

    sens = cfg["sensor"]
    ppd = float(sens["picture_width_px"]) / float(sens["fov_deg"])
    bx, by = im["background_columns"]
    bgx = cues[bx].to_numpy(float) / float(sens.get("pixel_aspect_x", 1.0))
    bgy = cues[by].to_numpy(float)
    bg = np.hypot(bgx, bgy)
    fr = window[np.isfinite(bg[window])]
    series["background_motion"] = Series("background_motion", fr, bg[fr], np.full(len(fr), -1),
                                         float(np.nanstd(L.smooth_residual(t[fr], bg[fr], deg))),
                                         _data_n_eff(t[fr], bg[fr], deg))

    flags += env.flags
    return CaseData(name=name, cfg=cfg, fps=fps, t=t, window=window, ref_frame=ref, az_read=az_all, el_read=el_all,
                    tas=tas, bank=bank, jet_alt=alt_m, ppd=ppd, readouts=readouts, series=series,
                    brightness_log_all=bright_log, size_px_all=size_px, env=env,
                    criteria=list(cfg["criteria"]), shared_parameters=dict(cfg["shared_parameters"]), flags=flags)
