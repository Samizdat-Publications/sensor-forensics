"""GIMBAL first look at the trajectory families (M2.6). Not the final scoring.

Inputs (this lab's per-frame readings):
- data/derived/gimbal/symbology_final.csv: azimuth ("54L" = -54), elevation (-2
  on every frame), Mach and pressure altitude (TAS by solve.atmosphere.mach_to_tas,
  ISA temperature; Mach smoothed over 31 frames because it is read to 0.01).
- data/derived/gimbal/image_track.csv: bank_deg from the horizon bars (positive =
  right wing down, so GIMBAL's left bank is negative), smoothed over 9 frames. Note
  the open finding that these bank angles run about 8.5 percent larger than
  Sitrec's (possible pixel aspect ratio).

PROVISIONAL PLACEHOLDERS (flagged in every output): jet heading 315 deg at frame 0,
and wind 120 kt from 270 at every altitude, both for the jet and for the air-speed
and wind-drift columns. solve/weather.py (ERA5) replaces the wind when it lands.
Angle convention: "level" (Sitrec's).

Outputs:
- data/derived/gimbal/families/constant_velocity_el{-2.0,-2.5,-1.5}.csv (readouts as
  exact points), constant_velocity_interval.csv (interval-aware loss, half width
  0.5 deg, sigma 0.1 deg), constant_velocity_bank_scaled.csv (bank x 1/1.085, Sitrec's
  horizon-bar scale), constant_altitude.csv and constant_altitude_refraction.csv
  (azimuth smoothed over 91 frames for this family only; ranges past 150 nmi dropped),
  wind_drift_placeholder_wind.csv, summary.json
- docs/reproductions/gimbal_range_curves.png

Usage: python -m solve.families_gimbal
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from . import atmosphere as A
from . import families as FM
from . import frames as F
from .jet import integrate, wind_from
from .los import sight_lines

ROOT = Path(__file__).resolve().parents[1]
GIMBAL = ROOT / "data" / "derived" / "gimbal"
OUT = GIMBAL / "families"
PLOT = ROOT / "docs" / "reproductions" / "gimbal_range_curves.png"
FPS = 30000 / 1001

HEADING0_PLACEHOLDER = 315.0
WIND_PLACEHOLDER = (270.0, 120.0)  # from deg, kt
PLACEHOLDER_NOTE = ("PROVISIONAL: jet heading 315 deg at frame 0 and wind 120 kt from 270 at all altitudes "
                    "are placeholders until solve/weather.py and the heading study land.")
NOISE_GIMBAL = FM.Noise((0.5, 0.5), 0.1)
BANK_SCALE_SITREC = 1 / 1.085
CA_MAX_RANGE = 150 * F.NMI  # drops far-branch crossings beyond the ray's tangent point (about 120 nmi)
RANGES_NMI = np.round(np.arange(1.0, 60.01, 0.5), 3)
ALTS_FT = np.arange(0.0, 40_000.1, 1000.0)


def _series(sym: pd.DataFrame, field: str) -> np.ndarray:
    s = sym[sym["field"] == field].sort_values("frame")["value"].tolist()
    if field == "azimuth":
        return np.array([float(v[:-1]) * (-1 if v.endswith("L") else 1) for v in s])
    return np.array([float(v) for v in s])


def load_inputs() -> dict:
    sym = pd.read_csv(GIMBAL / "symbology_final.csv", dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    cues = pd.read_csv(GIMBAL / "image_track.csv")
    az = _series(sym, "azimuth")
    el = _series(sym, "elevation")
    mach = pd.Series(_series(sym, "mach")).rolling(31, center=True, min_periods=1).mean().to_numpy()
    # Pressure altitude reads 25,010 or 25,000 ft; smooth so 10 ft display steps do not
    # become jumps in the jet's height.
    alt = pd.Series(_series(sym, "altitude") * F.FT).rolling(61, center=True, min_periods=1).mean().to_numpy()
    bank = cues.sort_values("frame")["bank_deg"].rolling(9, center=True, min_periods=1).mean().to_numpy()
    n = len(az)
    t = np.arange(n) / FPS
    tas = A.mach_to_tas(mach, alt)
    # Smoothed azimuth (Savitzky-Golay, 91 frames, quadratic) for constant_altitude
    # only: placing points on whole-degree steps 20 to 90 nmi away turns each 1 deg
    # step into a jump of km, which swamps speed and acceleration. A first-look
    # stand-in for the M2.5 line-of-sight fit, flagged in the outputs.
    az_smooth = savgol_filter(az, 91, 2, mode="interp")
    return {"t": t, "az": az, "az_smooth": az_smooth, "el": el, "alt": alt, "tas": tas, "bank": bank}


def build_sight_lines(inp: dict, el_override: float | None = None, heading0: float = HEADING0_PLACEHOLDER,
                      wind=WIND_PLACEHOLDER, smooth_az: bool = False):
    track = integrate(inp["t"], inp["tas"], inp["bank"], heading0,
                      wind_enu=wind_from(wind[0], wind[1] * F.KT), altitude=inp["alt"])
    el = inp["el"] if el_override is None else np.full_like(inp["el"], el_override)
    az = inp["az_smooth"] if smooth_az else inp["az"]
    return sight_lines(track, az, el, "level"), track


def _add_air_speed(df: pd.DataFrame, wind_enu: np.ndarray) -> pd.DataFrame:
    v = df[["vx", "vy", "vz"]].to_numpy()
    df["air_speed_kt_placeholder_wind"] = np.linalg.norm(v - wind_enu, axis=1) / F.KT
    h = np.clip(df["mean_alt_ft"].to_numpy() * F.FT, -500.0, 20_000.0)
    df["mach1_kt_at_mean_alt"] = A.speed_of_sound(A.isa(h)[0]) / F.KT
    return df


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    inp = load_inputs()
    wind_enu = wind_from(WIND_PLACEHOLDER[0], WIND_PLACEHOLDER[1] * F.KT)
    tables: dict[str, pd.DataFrame] = {}
    for el in (-2.0, -2.5, -1.5):
        sl, _ = build_sight_lines(inp, el_override=el)
        df = FM.range_grid(sl, "constant_velocity", RANGES_NMI, unit="nmi", noise=FM.EXACT)
        tables[f"constant_velocity_el{el}"] = _add_air_speed(df, wind_enu)
    # Sensitivity: bank scaled down to Sitrec's horizon-bar angles (ours read about 8.5
    # percent larger, an open pixel-aspect finding), which lowers the turn rate.
    inp_s = dict(inp, bank=inp["bank"] * BANK_SCALE_SITREC)
    sl_s, _ = build_sight_lines(inp_s)
    df = FM.range_grid(sl_s, "constant_velocity", RANGES_NMI, unit="nmi", noise=FM.EXACT)
    tables["constant_velocity_bank_scaled"] = _add_air_speed(df, wind_enu)
    sl, track = build_sight_lines(inp)
    df = FM.range_grid(sl, "constant_velocity", RANGES_NMI, unit="nmi", noise=NOISE_GIMBAL)
    tables["constant_velocity_interval"] = _add_air_speed(df, wind_enu)
    sl_smooth, _ = build_sight_lines(inp, smooth_az=True)
    tables["constant_altitude"] = FM.range_grid(sl_smooth, "constant_altitude", ALTS_FT, unit="ft",
                                                smooth_s=2.0, max_range=CA_MAX_RANGE)
    tables["constant_altitude_refraction"] = FM.range_grid(sl_smooth, "constant_altitude", ALTS_FT, unit="ft",
                                                           refraction=True, smooth_s=2.0, max_range=CA_MAX_RANGE)
    tables["wind_drift_placeholder_wind"] = FM.range_grid(sl, "wind_drift", RANGES_NMI, unit="nmi",
                                                          wind_fn=lambda h, t: wind_enu)
    for name, df in tables.items():
        df.insert(0, "note", PLACEHOLDER_NOTE)
        df.to_csv(OUT / f"{name}.csv", index=False, float_format="%.6g")

    summary = {"note": PLACEHOLDER_NOTE, "convention": "level", "frames": int(len(inp["t"])),
               "jet": {"tas_kt_mean": float(np.mean(inp["tas"]) / F.KT),
                       "heading_change_deg": float(track.heading[-1] - track.heading[0]
                                                   + (360 if track.heading[-1] > track.heading[0] + 180 else 0)),
                       "bank_deg_mean": float(np.mean(inp["bank"]))},
               "noise_interval": {"half_width_deg": list(NOISE_GIMBAL.half_width_deg),
                                  "sigma_deg": NOISE_GIMBAL.sigma_deg, "n_eff": "n/6"}}
    cv = {}
    for name in ("constant_velocity_el-2.0", "constant_velocity_el-2.5", "constant_velocity_el-1.5",
                 "constant_velocity_bank_scaled", "constant_velocity_interval"):
        df = tables[name]
        key = "deviance" if name.endswith("interval") else "misfit_deg_rms"
        i = int(df[key].idxmin())
        band = df[(df["value"] >= 5) & (df["value"] <= 40)]
        at = {f"{r:g}nmi": {"ground_speed_kt": float(df.loc[df["value"] == r, "fit_speed_kt"].iloc[0]),
                            "ground_speed_1sigma_kt": [float(df.loc[df["value"] == r, "speed_lo_1sigma_kt"].iloc[0]),
                                                       float(df.loc[df["value"] == r, "speed_hi_1sigma_kt"].iloc[0])],
                            "air_speed_kt_placeholder_wind":
                                float(df.loc[df["value"] == r, "air_speed_kt_placeholder_wind"].iloc[0]),
                            "mean_alt_ft": float(df.loc[df["value"] == r, "mean_alt_ft"].iloc[0]),
                            "misfit_deg_rms": float(df.loc[df["value"] == r, "misfit_deg_rms"].iloc[0])}
              for r in (8.0, 30.0)}
        entry = {"best_range_nmi": float(df["value"][i]),
                 "best_misfit_deg_rms": float(df["misfit_deg_rms"][i]),
                 "best_ground_speed_kt": float(df["fit_speed_kt"][i]),
                 "misfit_deg_rms_5_to_40nmi_min_max": [float(band["misfit_deg_rms"].min()),
                                                        float(band["misfit_deg_rms"].max())],
                 "at": at}
        if name.endswith("interval"):
            w = df[df["within_1sigma"]]["value"]
            entry["one_sigma_range_nmi"] = [float(w.min()), float(w.max())]
            entry["misfit_excess_deg_rms_5_to_40nmi_min_max"] = [float(band["misfit_excess_deg_rms"].min()),
                                                                  float(band["misfit_excess_deg_rms"].max())]
            entry["delta_chi2_eff_5_to_40nmi_max"] = float(band["delta_chi2_eff"].max())
        cv[name] = entry
    summary["constant_velocity"] = cv
    ca = tables["constant_altitude"].dropna(subset=["mean_speed_kt"])
    summary["constant_altitude"] = ca[["value", "mean_range_nmi", "mean_speed_kt", "max_speed_kt",
                                       "max_accel_g"]].round(2).to_dict(orient="records")
    wd = tables["wind_drift_placeholder_wind"]
    j = int(wd["misfit_deg_rms"].idxmin())
    summary["wind_drift_placeholder_wind"] = {"best_range_nmi": float(wd["value"][j]),
                                              "best_misfit_deg_rms": float(wd["misfit_deg_rms"][j])}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    plot(tables)
    return summary


def plot(tables: dict[str, pd.DataFrame]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    blue, orange, aqua, yellow, ink, muted = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#0b0b0b", "#52514e"
    fig, axs = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    base = tables["constant_velocity_el-2.0"]
    lo, hi = tables["constant_velocity_el-2.5"], tables["constant_velocity_el-1.5"]
    iv = tables["constant_velocity_interval"]

    ax = axs[0, 0]
    ax.plot(base["value"], base["misfit_deg_rms"], color=blue, lw=2, label="El -2.0 (readout center)")
    ax.plot(lo["value"], lo["misfit_deg_rms"], color=orange, lw=2, label="El -2.5")
    ax.plot(hi["value"], hi["misfit_deg_rms"], color=aqua, lw=2, ls=(0, (2, 2)),
            label="El -1.5 (the three El curves overlap)")
    bs = tables["constant_velocity_bank_scaled"]
    ax.plot(bs["value"], bs["misfit_deg_rms"], color=yellow, lw=2, ls="--",
            label="El -2.0, bank scaled x0.92 to Sitrec (lower turn rate)")
    ax.set_title("Constant velocity: RMS angular misfit (readouts as exact points)", loc="left", fontsize=11)
    ax.set_xlabel("start range r0 (nmi)")
    ax.set_ylabel("RMS misfit (deg)")
    ax.legend(frameon=False)

    ax = axs[0, 1]
    ax.semilogy(iv["value"], np.maximum(iv["delta_chi2_eff"], 1e-3), color=blue, lw=2)
    ax.axhline(1.0, color=muted, lw=1, ls="--")
    ax.text(2, 1.3, "1 sigma", ha="left", color=muted, fontsize=9)
    ax.set_title("Constant velocity: interval-aware loss\n"
                 "(readout intervals +/- 0.5 deg, sigma 0.1 deg, n_eff = n/6)",
                 loc="left", fontsize=11)
    ax.set_xlabel("start range r0 (nmi)")
    ax.set_ylabel("delta chi-square (effective)")

    ax = axs[1, 0]
    ax.axhspan(0, 50, color="#d9d8d3", alpha=0.6, lw=0)
    ax.axhspan(50, 170, color="#ecebe7", alpha=0.6, lw=0)
    ax.axhspan(15, 60, xmin=0.0, xmax=0.04, color="#a3a29d", lw=0)
    ax.axhspan(400, 500, color="#d9d8d3", alpha=0.6, lw=0)
    ax.text(59, 25, "balloon drift, light wind (under 50 kt)", ha="right", va="center", fontsize=8, color=muted)
    ax.text(59, 140, "balloon in 50 kt plus the 120 kt placeholder wind", ha="right", va="center", fontsize=8,
            color=muted)
    ax.text(3.0, 37, "birds 15 to 60 kt (air speed)", fontsize=8, color=muted, va="center")
    ax.text(59, 450, "airliners 400 to 500 kt", ha="right", va="center", fontsize=8, color=muted)
    ax.plot(base["value"], base["mach1_kt_at_mean_alt"], color=muted, lw=1, ls=":")
    ax.text(59, base["mach1_kt_at_mean_alt"].iloc[-1] + 12, "Mach 1 at the implied altitude (ISA)",
            ha="right", fontsize=8, color=muted)
    ax.fill_between(base["value"], base["speed_lo_1sigma_kt"], base["speed_hi_1sigma_kt"], color=blue,
                    alpha=0.10, lw=0, hatch="///", edgecolor=blue, label="one-sigma speed range, El -2.0")
    ax.plot(base["value"], base["fit_speed_kt"], color=blue, lw=2, label="ground speed, El -2.0")
    ax.fill_between(base["value"], np.minimum(lo["fit_speed_kt"], hi["fit_speed_kt"]),
                    np.maximum(lo["fit_speed_kt"], hi["fit_speed_kt"]), color=blue, alpha=0.18, lw=0,
                    label="ground speed, El -2.5 to -1.5")
    ax.plot(base["value"], base["air_speed_kt_placeholder_wind"], color=orange, lw=2,
            label="air speed (placeholder wind)")
    ax.plot(bs["value"], bs["fit_speed_kt"], color=yellow, lw=2, ls="--", label="ground speed, bank scaled x0.92")
    ca = tables["constant_altitude"].dropna(subset=["mean_speed_kt"])
    ax.plot(ca["mean_range_nmi"], ca["mean_speed_kt"], color=aqua, lw=0, marker="o", ms=4,
            label="constant altitude: mean speed vs mean range")
    ax.set_ylim(0, 1600)
    ax.set_xlim(0, 60)
    ax.set_title("Implied speed vs range (constant velocity; constant altitude as dots)", loc="left", fontsize=11)
    ax.set_xlabel("start range r0 (nmi)")
    ax.set_ylabel("speed (kt)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8)

    ax = axs[1, 1]
    ax.plot(base["value"], base["mean_alt_ft"] / 1000, color=blue, lw=2, label="mean altitude, El -2.0")
    ax.fill_between(base["value"], np.minimum(lo["mean_alt_ft"], hi["mean_alt_ft"]) / 1000,
                    np.maximum(lo["mean_alt_ft"], hi["mean_alt_ft"]) / 1000, color=blue, alpha=0.18, lw=0,
                    label="El -2.5 to -1.5")
    ax.plot(base["value"], base["alt_change_ft"] / 1000, color=orange, lw=2, label="altitude change over the clip")
    ax.axhline(0, color=muted, lw=0.8)
    ax.set_title("Implied altitude vs range (constant velocity)", loc="left", fontsize=11)
    ax.set_xlabel("start range r0 (nmi)")
    ax.set_ylabel("thousand ft")
    ax.set_ylim(-5, 30)
    ax.text(1, 28, "below 2 nmi the best-fit paths leave the plot (no constant velocity fits there)",
            fontsize=8, color=muted)
    ax.legend(frameon=False, fontsize=8, loc="center right")

    for a in axs.flat:
        a.grid(True, color="#e4e3df", lw=0.6)
        a.tick_params(colors=muted)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.suptitle("GIMBAL range curves, first look. " + PLACEHOLDER_NOTE, fontsize=9, color=ink, x=0.01,
                 ha="left")
    PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT, dpi=130, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    print(json.dumps(run()["constant_velocity"], indent=1))
