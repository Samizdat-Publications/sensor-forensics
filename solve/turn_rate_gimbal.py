"""M2.5: GIMBAL jet turn rate from the lab's own cloud-motion measurement.

Four turn-rate histories (deg/s, negative = left turn), lab frame numbering, 29.97 fps:

(a) omega_bank_lab     coordinated turn g0 tan(bank) / TAS from the lab's horizon-bar bank
                       (image_track.csv) and the lab TAS (on-screen Mach x ISA speed of sound).
(b) omega_bank_sitrec  the same formula and TAS with Sitrec's GimbalData.csv bank column
                       (shifted one frame to lab numbering), so only the bank differs.
(c) omega_cloud_sitrec Sitrec's default "Match Clouds" rate, solve.repro_gimbal.cloud_turn_rate
                       (port; hand-keyed cloud-speed curve, Sitrec's Gaussian azimuth, 351 kt,
                       cloud tops 11,740 ft, no wind), shifted to lab numbering.
(d) omega_cloud_lab    this work: omega = -h - daz/dt + p (solve.cloud_motion), with
                       h  = background motion along the image horizon, from image_track.csv
                            bg_dx, bg_dy (whole active picture; the lower-left cloud tile is
                            the cross-check), projected on the horizon angle theta from
                            sensor_atflir.human_horizon, converted with px per degree;
                       daz/dt from the lab's interval-constrained azimuth spline;
                       p  = parallax of the deck texture (relative velocity to the cloud air
                            mass over its distance, from the deck geometry).
                       Smoothed with a 91-frame (3 s) centered mean, like its band.

Uncertainty (omega_cloud_lab_lo / _hi, 2.5 and 97.5 percentiles of a Monte Carlo):
azimuth rebuilt from the half-degree crossing times (display cadence 6 frames: each crossing
uniform within the 6 frames before it was displayed; common latency 0 to 6 frames), cloud
deck 8,000 to 18,000 ft (with or without standard refraction), texture 0.01 to 0.12 deg below
the deck horizon, image scale +/-5 percent and pixel aspect 1.00 to 1.05, cloud-level wind
0 to 40 kt from any direction, jet wind 120 kt from 240 to 300, initial heading 295 to 335,
jet pitch 2 to 6 deg (horizon angle), whole-frame or cloud-tile measurement.

Also: total heading change, RMS differences, a scale / lag fit of the bank-derived rate to the
cloud rate, the body-frame azimuth convention, a joint image-scale fit, and reruns of the
key GIMBAL results with the cloud rate (P&vR close path, the 340 kt distant path, the
constant-velocity range curve).

PLACEHOLDERS: jet heading 315 deg at frame 0 and wind 120 kt from 270 (as M2.6); cloud-level
wind 17 kt from 240 (Sitrec). solve/weather.py (ERA5) replaces them when it lands.

CLI: python -m solve.turn_rate_gimbal            (the 0.35 deg run below)
     python -m solve.turn_rate_gimbal --fov 0.7  (turn_rate_fov070.csv: same method at another field of view, M3.5)
Writes data/derived/gimbal/turn_rate.csv, data/derived/gimbal/turn_rate_summary.json,
docs/reproductions/gimbal_turn_rate.png
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import make_smoothing_spline

from . import atmosphere as A
from . import cloud_motion as CM
from . import families as FM
from . import families_gimbal as FG
from . import frames as F
from . import repro_gimbal as RG
from .jet import integrate, wind_from
from .los import sight_lines
from .sensor_atflir import human_horizon, los_level_frame, xyz_to_ea

ROOT = Path(__file__).resolve().parents[1]
GIMBAL = ROOT / "data" / "derived" / "gimbal"
OUT_CSV = GIMBAL / "turn_rate.csv"
OUT_JSON = GIMBAL / "turn_rate_summary.json"
PLOT = ROOT / "docs" / "reproductions" / "gimbal_turn_rate.png"

N = RG.N
FPS = RG.FPS
T = np.arange(N) / FPS
H_JET = RG.JET_ALT_FT * F.FT
FOV_DEG = 0.35
# Active picture of our 640 x 480 copies (median frame): columns 104.5 to 530.5, rows 26.5 to 454.5.
PICTURE_W_PX, PICTURE_H_PX = 426.0, 428.0
PPD_X = PICTURE_W_PX / FOV_DEG     # 1217 px/deg: 0.35 deg spans the picture width
PPD_Y = PICTURE_H_PX / FOV_DEG     # 1223 px/deg: and its height (square field, P&vR)
PITCH_DEG = 3.6                    # Sitrec par.jetPitch
EL_READ = -2.0
HEADING0 = FG.HEADING0_PLACEHOLDER
JET_WIND = FG.WIND_PLACEHOLDER      # (from deg, kt)
CLOUD_WIND = (240.0, 17.0)          # Sitrec SitGimbal.js
H_CLOUD_FT = 11_740.0               # Sitrec; nominal
TEXTURE_BELOW_DEG = 0.04            # tracked texture below the deck horizon (nominal)
SMOOTH = 91                         # frames (3 s) for comparisons
EDGE = SMOOTH // 2
CORE = slice(EDGE, N - EDGE)        # frames 45 to 985: clear of the smoothing edges
N_MC = 300
SEED = 20261031


# ----------------------------------------------------------------------------- helpers

def smooth(x: np.ndarray, w: int = SMOOTH) -> np.ndarray:
    return pd.Series(np.asarray(x, float)).rolling(w, center=True, min_periods=1).mean().to_numpy()


def rms(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    return float(np.sqrt(np.nanmean(x ** 2)))


def heading_change(om: np.ndarray) -> float:
    return float(np.trapezoid(om, T))


def bank_rate(bank_deg: np.ndarray, tas_kt: np.ndarray) -> np.ndarray:
    return np.degrees(A.G0 * np.tan(np.radians(bank_deg)) / (tas_kt * F.KT))


def cues() -> pd.DataFrame:
    return pd.read_csv(GIMBAL / "image_track.csv").sort_values("frame").reset_index(drop=True)


def horizon_angle(bank: np.ndarray, az: np.ndarray, pitch: float = PITCH_DEG, el: float = EL_READ) -> np.ndarray:
    return np.array([human_horizon(pitch, bank[i], az[i], el) for i in range(N)])


def robust_rate(h: np.ndarray, w: int = 31, k: float = 5.0) -> tuple[np.ndarray, np.ndarray]:
    """Reject outliers (more than k robust sigmas from a w-frame running median), fill, w-frame mean."""
    s = pd.Series(h)
    med = s.rolling(w, center=True, min_periods=1).median()
    resid = s - med
    mad = 1.4826 * resid.abs().rolling(4 * w, center=True, min_periods=1).median()
    bad = (resid.abs() > k * mad.clip(lower=1e-4)) | s.isna()
    clean = s.mask(bad).interpolate(limit_direction="both")
    return clean.rolling(w, center=True, min_periods=1).mean().to_numpy(), bad.to_numpy()


def measured_h(c: pd.DataFrame, theta: np.ndarray, source: str = "bg", ppd_x: float = PPD_X,
               ppd_y: float = PPD_Y, rot_correct: bool = True) -> dict:
    """Background motion along the image horizon, deg/s (+ = content moves right).

    The cloud tile's center (202, 321.5) lies off the picture center (317.5, 240.5), so the
    image rotation (rate taken from the horizon angle theta) adds a translation there; it is
    removed. The whole-picture region is centered, so no correction is needed.
    """
    dx = c[f"{source}_dx"].to_numpy(float).copy()
    dy = c[f"{source}_dy"].to_numpy(float).copy()
    if source == "cloud" and rot_correct:
        rho = np.radians(np.gradient(smooth(theta, 31)))      # rad/frame, CCW (y up)
        rx, ry = 202.0 - 317.5, -(321.5 - 240.5)               # y-up lever arm
        dx -= -rho * ry                                        # CCW rotation: d = rho x r = rho (-ry, rx)
        dy -= -(rho * rx)
    h, v = CM.pixels_to_angular(dx, dy, theta, np.full(N, EL_READ), ppd_x, ppd_y)
    h_s, bad = robust_rate(h * FPS)
    v_s, _ = robust_rate(v * FPS)
    return {"h": h_s, "h_raw": h * FPS, "v": v_s, "n_rejected": int(bad.sum())}


def texture_distance_h(h_cloud_m: float, below_deg: float, refraction: bool) -> tuple[float, float, float]:
    """Horizontal distance (m) to the tracked deck texture, the deck-horizon dip and its distance."""
    dip = CM.deck_dip_deg(H_JET, h_cloud_m, refraction)
    s = CM.ray_deck_distance(H_JET, h_cloud_m, dip + below_deg, refraction)
    return s * np.cos(np.radians(dip + below_deg)), dip, CM.deck_horizon_distance(H_JET, h_cloud_m, refraction)


def crossing_azimuth(readings: np.ndarray, lam: float, rng: np.random.Generator | None = None,
                     cadence: int = 6, latency: float = 3.0) -> np.ndarray:
    """Azimuth through the half-degree crossings implied by the integer readout changes.

    A change from v to v' displayed at frame b means the azimuth crossed (v + v') / 2 at
    some display update in (b - cadence, b], minus the display latency. Nominal: the middle
    of that window; with rng, uniform inside it.
    """
    r = np.asarray(readings, float)
    ch = np.flatnonzero(np.diff(r) != 0) + 1
    jit = rng.uniform(-cadence / 2, cadence / 2, len(ch)) if rng is not None else np.zeros(len(ch))
    x = ch - cadence / 2.0 + jit - latency
    y = 0.5 * (r[ch - 1] + r[ch])
    order = np.argsort(x)
    x, y = x[order], y[order]
    keep = np.concatenate([[True], np.diff(x) > 1e-6])
    spl = make_smoothing_spline(x[keep], y[keep], lam=lam)
    return spl(np.arange(N, dtype=float))


# ----------------------------------------------------------------------------- the four histories

def inputs() -> dict:
    lab_inp, az_info = RG.lab_inputs()
    az = lab_inp.az_deg
    tas = lab_inp.tas_kt
    bank = lab_inp.bank_deg
    d = RG.load_sitrec()
    bank_s = RG._shift_to_lab(-d["3 bank_angle"].to_numpy(float))
    g_az = -d["5 gaussian_smoothed_azimuth"].to_numpy(float)
    om_cs = RG._shift_to_lab(RG.cloud_turn_rate(g_az))
    cs_curve = RG._shift_to_lab(RG.cloud_speed_curve())
    return {"lab_inp": lab_inp, "az_info": az_info, "az": az, "tas": tas, "bank": bank, "bank_s": bank_s,
            "om_a": bank_rate(bank, tas), "om_b": bank_rate(bank_s, tas), "om_c": om_cs,
            "om_c_lab_az": RG.cloud_turn_rate(az, tas_kt=float(np.mean(tas))),
            "cs_curve": cs_curve, "readings": RG.lab_azimuth_readings(), "cues": cues()}


def cloud_rate(inp: dict, az: np.ndarray | None = None, source: str = "bg", h_cloud_ft: float = H_CLOUD_FT,
               below: float = TEXTURE_BELOW_DEG, refraction: bool = False, scale: float = 1.0,
               aspect: float = PPD_X / PPD_Y, cloud_wind=CLOUD_WIND, jet_wind=JET_WIND, heading0: float = HEADING0,
               pitch: float = PITCH_DEG, bank_for_theta: np.ndarray | None = None, smooth_w: int = SMOOTH,
               daz: np.ndarray | None = None) -> dict:
    az = inp["az"] if az is None else az
    bank = inp["bank"] if bank_for_theta is None else bank_for_theta
    theta = horizon_angle(bank, az, pitch)
    ppd_x = PPD_X * scale
    ppd_y = ppd_x / aspect
    m = measured_h(inp["cues"], theta, source, ppd_x, ppd_y)
    s_h, dip, s_t = texture_distance_h(h_cloud_ft * F.FT, below, refraction)
    jw = wind_from(jet_wind[0], jet_wind[1] * F.KT)
    cw = wind_from(cloud_wind[0], cloud_wind[1] * F.KT)
    inv = CM.invert_turn_rate(T, m["h"], az, inp["tas"] * F.KT, heading0, jw, cw, s_h,
                              daz_deg_s=np.gradient(az, T) if daz is None else daz, omega_init=inp["om_a"])
    om = inv["omega"]
    return {"omega": smooth(om, smooth_w) if smooth_w > 1 else om, "omega_raw": om, "p": inv["p"],
            "h": m["h"], "h_raw": m["h_raw"], "v": m["v"], "theta": theta, "n_rejected": m["n_rejected"],
            "dist_h_km": s_h / 1000.0, "dip_deg": dip, "deck_horizon_km": s_t / 1000.0,
            "heading_change_deg": heading_change(om)}


def monte_carlo(inp: dict, n: int = N_MC, seed: int = SEED, base_scale: float = 1.0) -> dict:
    """Monte Carlo band. base_scale multiplies the image scale (px/deg): 0.5 is a 0.7 deg field."""
    rng = np.random.default_rng(seed)
    lam = inp["az_info"]["lambda"]
    draws, totals, params, azs = [], [], [], []
    for _ in range(n):
        az = crossing_azimuth(inp["readings"], lam, rng, latency=rng.uniform(0.0, 6.0))
        p = {"h_cloud_ft": rng.uniform(8_000.0, 18_000.0), "refraction": bool(rng.random() < 0.5),
             "below": rng.uniform(0.01, 0.12), "scale": base_scale * rng.uniform(0.95, 1.05),
             "aspect": rng.uniform(1.0, 1.05), "cloud_wind": (rng.uniform(0, 360), rng.uniform(0, 40)),
             "jet_wind": (rng.uniform(240, 300), 120.0), "heading0": rng.uniform(295, 335),
             "pitch": rng.uniform(2.0, 6.0), "source": "bg" if rng.random() < 0.5 else "cloud"}
        r = cloud_rate(inp, az=az, **p)
        draws.append(r["omega"])
        azs.append(az)
        totals.append(r["heading_change_deg"])
        params.append({k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()})
    D = np.array(draws)
    return {"draws": D, "lo": np.percentile(D, 2.5, axis=0), "hi": np.percentile(D, 97.5, axis=0),
            "sd": D.std(axis=0), "totals": np.array(totals), "params": params, "az": np.array(azs)}


# ----------------------------------------------------------------------------- interpretation tests

def fit_bank_scale_lag(inp: dict, target: np.ndarray, bank: np.ndarray, lags=range(-30, 61, 3)) -> dict:
    """Best constant bank-angle scale s and lag L (frames, + = bars lag the true bank) for
    g0 tan(s * bank(t + L)) / TAS to match the target rate (both 91-frame smoothed, core frames)."""
    best = None
    grid = []
    for L in lags:
        b = np.interp(np.arange(N) + L, np.arange(N), bank)
        for s in np.arange(0.80, 1.201, 0.005):
            r = rms(smooth(bank_rate(s * b, inp["tas"]))[CORE] - target[CORE])
            grid.append((L, s, r))
            if best is None or r < best[2]:
                best = (L, s, r)
    s_only = min((g for g in grid if g[0] == 0), key=lambda g: g[2])
    l_only = min((g for g in grid if abs(g[1] - 1.0) < 1e-9), key=lambda g: g[2])
    return {"best_lag_frames": int(best[0]), "best_scale": round(float(best[1]), 3), "rms_deg_s": best[2],
            "scale_only_lag0": round(float(s_only[1]), 3), "rms_scale_only_deg_s": s_only[2],
            "lag_only_scale1_frames": int(l_only[0]), "rms_lag_only_deg_s": l_only[2]}


def body_frame_azimuth(az: np.ndarray, bank: np.ndarray, pitch: float = PITCH_DEG, el: float = EL_READ) -> np.ndarray:
    """Level azimuth if the readout were measured in the jet's body frame (wing plane, nose)."""
    out = np.empty(N)
    for i in range(N):
        _, a = xyz_to_ea(los_level_frame(az[i], el, "body", jet_roll=bank[i], jet_pitch=pitch))
        out[i] = a
    return out


def scale_fit(inp: dict, r_nom: dict, lag_a: int = 0, lag_b: int = 0) -> dict:
    """Joint least squares for the image scale and a turn-rate scale k, assuming omega = k omega_bank_lab:
    (h_px rate) / ppd = -(k omega_bank + daz) + p. Linear in (1/ppd, k)."""
    theta = r_nom["theta"]
    c = inp["cues"]
    h_unit, _ = CM.pixels_to_angular(c["bg_dx"].to_numpy(float), c["bg_dy"].to_numpy(float), theta,
                                     np.full(N, EL_READ), 1.0, 1.0 * PPD_X / PPD_Y)
    hpx = smooth(robust_rate(h_unit * FPS)[0])                   # px/s along the horizon (x px)
    daz = smooth(np.gradient(inp["az"], T))
    om_b = smooth(np.interp(np.arange(N) + lag_a, np.arange(N), inp["om_a"]))
    p = smooth(r_nom["p"])
    M = np.column_stack([hpx[CORE], om_b[CORE]])
    y = (p - daz)[CORE]
    (a, k), *_ = np.linalg.lstsq(M, y, rcond=None)
    om_b2 = smooth(np.interp(np.arange(N) + lag_b, np.arange(N), inp["om_b"]))
    M2 = np.column_stack([hpx[CORE], om_b2[CORE]])
    (a2, k2), *_ = np.linalg.lstsq(M2, y, rcond=None)
    return {"bank_lab": {"lag_frames": lag_a, "ppd_x": float(1 / a), "fov_deg_over_picture_width": float(PICTURE_W_PX * a),
                         "k": float(k)},
            "bank_sitrec": {"lag_frames": lag_b, "ppd_x": float(1 / a2),
                            "fov_deg_over_picture_width": float(PICTURE_W_PX * a2), "k": float(k2)}}


# ----------------------------------------------------------------------------- reruns

A_KEYS = ["end_range_nmi", "ground_speed_min_frame", "ground_speed_min_kt", "air_velocity_reversal_frame",
          "air_speed_start_kt", "ground_speed_start_kt", "alt_change_ft", "jet_heading_change_deg"]
B_KEYS = ["end_range_nmi", "range_min_max_nmi", "alt_start_ft", "alt_end_ft", "n_no_intersection_frames",
          "air_heading_span_deg", "ground_speed_kt_min_max", "straightness_top_view_good_frames",
          "air_heading_start_end_deg", "jet_heading_change_deg"]


def rate_for_az(inp: dict, az_lab_numbering: np.ndarray) -> np.ndarray:
    """Lab cloud turn rate re-derived for a given azimuth series (lab numbering).

    The clouds fix the LOS bearing (heading + az) relative to the cloud deck, so a run that
    uses a different azimuth series must use the turn rate derived with that series."""
    return cloud_rate(inp, az=az_lab_numbering)["omega"]


def rerun_a(inp: dict) -> dict:
    a_in = RG.pvr_inputs()
    om_pvr = RG._shift_to_sitrec(rate_for_az(inp, RG._shift_to_lab(a_in.az_deg)))
    om_lab = rate_for_az(inp, inp["az"])
    return {"pvr_inputs_with_lab_cloud_rate": RG._pick(RG.run_a(replace(a_in, turn_override=om_pvr)), A_KEYS),
            "all_lab_with_lab_cloud_rate": RG._pick(RG.run_a(replace(inp["lab_inp"], turn_override=om_lab)), A_KEYS),
            "note": "turn rate re-derived from the lab cloud motion with each run's own azimuth series"}


def rerun_b(inp: dict) -> dict:
    b_in = RG.sitrec_inputs()
    om_s = RG._shift_to_sitrec(rate_for_az(inp, RG._shift_to_lab(b_in.az_deg)))
    om_lab = rate_for_az(inp, inp["az"])
    return {"sitrec_inputs_with_lab_cloud_rate": RG._pick(RG.run_b(b_in, turn_rate=om_s), B_KEYS),
            "all_lab_with_lab_cloud_rate": RG._pick(RG.run_b(inp["lab_inp"], turn_rate=om_lab), B_KEYS),
            "note": "turn rate re-derived from the lab cloud motion with each run's own azimuth series"}


def rerun_bank_lag(inp: dict, lag: int) -> dict:
    """The lab bank rate advanced by `lag` frames (horizon bars lagging the turn), all lab inputs."""
    om = np.interp(np.arange(N) + lag, np.arange(N), inp["om_a"])
    return {"lag_frames": lag,
            "A_all_lab": RG._pick(RG.run_a(replace(inp["lab_inp"], turn_override=om)), A_KEYS),
            "B_all_lab": RG._pick(RG.run_b(inp["lab_inp"], turn_rate=om), B_KEYS)}


def range_curve(om: np.ndarray | None, noise=FM.EXACT, ranges=FG.RANGES_NMI, az: np.ndarray | None = None) -> pd.DataFrame:
    """M2.6's constant-velocity range grid (raw integer azimuth, heading 315, wind 120 kt from 270) with a
    turn-rate override; az replaces the raw readout (e.g. the lab's interval spline)."""
    fin = FG.load_inputs()
    track = integrate(fin["t"], fin["tas"], fin["bank"], FG.HEADING0_PLACEHOLDER,
                      wind_enu=wind_from(FG.WIND_PLACEHOLDER[0], FG.WIND_PLACEHOLDER[1] * F.KT),
                      altitude=fin["alt"], turn_rate_deg_s=om)
    sl = sight_lines(track, fin["az"] if az is None else az, fin["el"], "level")
    df = FM.range_grid(sl, "constant_velocity", ranges, unit="nmi", noise=noise)
    return FG._add_air_speed(df, wind_from(FG.WIND_PLACEHOLDER[0], FG.WIND_PLACEHOLDER[1] * F.KT))


def range_summary(df: pd.DataFrame) -> dict:
    i = int(df["misfit_deg_rms"].idxmin())
    out = {"best_range_nmi": float(df["value"][i]), "best_misfit_deg_rms": float(df["misfit_deg_rms"][i]),
           "best_ground_speed_kt": float(df["fit_speed_kt"][i])}
    for r in (8.0, 30.0):
        row = df[df["value"] == r].iloc[0]
        out[f"at_{r:g}nmi"] = {"misfit_deg_rms": float(row["misfit_deg_rms"]),
                               "ground_speed_kt": float(row["fit_speed_kt"]),
                               "ground_speed_1sigma_kt": [float(row["speed_lo_1sigma_kt"]),
                                                          float(row["speed_hi_1sigma_kt"])],
                               "air_speed_kt_placeholder_wind": float(row["air_speed_kt_placeholder_wind"]),
                               "mean_alt_ft": float(row["mean_alt_ft"])}
    band = df[(df["value"] >= 5) & (df["value"] <= 40)]
    out["misfit_5_to_40nmi_min_max"] = [float(band["misfit_deg_rms"].min()), float(band["misfit_deg_rms"].max())]
    if df["misfit_excess_deg_rms"].notna().any() and "within_1sigma" in df and df["within_1sigma"].any():
        w = df[df["within_1sigma"]]["value"]
        out["interval_one_sigma_range_nmi"] = [float(w.min()), float(w.max())]
    return out


# ----------------------------------------------------------------------------- main computation

def compute() -> dict:
    inp = inputs()
    nom = cloud_rate(inp)
    om_d = nom["omega"]
    tile = cloud_rate(inp, source="cloud")
    mc = monte_carlo(inp)
    lo, hi = mc["lo"], mc["hi"]

    S = {k: smooth(inp[k]) for k in ("om_a", "om_b", "om_c")}
    S["om_d"] = om_d
    names = {"om_a": "bank_lab", "om_b": "bank_sitrec", "om_c": "cloud_sitrec", "om_d": "cloud_lab"}
    segs = {"f45-300": slice(45, 300), "f300-600": slice(300, 600), "f600-870": slice(600, 870),
            "f870-985": slice(870, 986)}
    comp = {}
    for k in ("om_a", "om_b", "om_c"):
        diff = S[k] - om_d
        inside = (S[k] >= lo) & (S[k] <= hi)
        comp[names[k]] = {
            "rms_vs_cloud_lab_deg_s": rms(diff[CORE]),
            "mean_vs_cloud_lab_deg_s": float(np.mean(diff[CORE])),
            "max_abs_vs_cloud_lab_deg_s": float(np.max(np.abs(diff[CORE]))),
            "segments_mean_diff_deg_s": {s: float(np.mean(diff[sl])) for s, sl in segs.items()},
            "fraction_core_frames_inside_band": float(np.mean(inside[CORE])),
            "heading_change_deg": heading_change(inp[k]),
        }
    # cross-pairs among the three published-style histories
    comp["bank_lab_vs_cloud_sitrec_rms_deg_s"] = rms((S["om_a"] - S["om_c"])[CORE])
    comp["bank_sitrec_vs_cloud_sitrec_rms_deg_s"] = rms((S["om_b"] - S["om_c"])[CORE])
    comp["bank_lab_vs_bank_sitrec_rms_deg_s"] = rms((S["om_a"] - S["om_b"])[CORE])
    tot = mc["totals"]
    comp["cloud_lab"] = {"heading_change_deg": nom["heading_change_deg"],
                         "heading_change_mc_2p5_50_97p5_deg": np.percentile(tot, [2.5, 50, 97.5]).tolist(),
                         "heading_change_tile_deg": tile["heading_change_deg"],
                         "band_halfwidth_core_median_deg_s": float(np.median((hi - lo)[CORE]) / 2)}

    # data space: what the bank rates predict for the clouds
    daz = np.gradient(inp["az"], T)
    pred = {k: smooth(CM.predict_h_rate_linear(inp[k], daz, nom["p"])) for k in ("om_a", "om_b", "om_c")}
    h_meas = smooth(nom["h"])
    data_space = {names[k]: {"rms_deg_s": rms((pred[k] - h_meas)[CORE]),
                             "rms_px_per_frame": rms((pred[k] - h_meas)[CORE]) * PPD_X / FPS}
                  for k in pred}
    data_space["tile_vs_whole_picture_rms_deg_s"] = rms((smooth(tile["h"]) - h_meas)[CORE])
    data_space["measured_h_deg_s_at_frames"] = {str(f): float(h_meas[f]) for f in (45, 300, 600, 900, 985)}
    data_space["sitrec_keyed_cloud_speed_deg_s_at_frames"] = {str(f): float(-inp["cs_curve"][f])
                                                             for f in (45, 300, 600, 900, 985)}
    data_space["ratio_measured_over_sitrec_keyed_core_median"] = float(np.median(h_meas[CORE] / -inp["cs_curve"][CORE]))
    data_space["integral_h_deg"] = float(np.trapezoid(nom["h"], T))
    data_space["integral_h_in_fovs_0p35"] = float(np.trapezoid(nom["h"], T) / FOV_DEG)
    data_space["integral_p_deg"] = float(np.trapezoid(nom["p"], T))
    data_space["azimuth_change_deg"] = float(inp["az"][-1] - inp["az"][0])
    data_space["perp_motion_rms_deg_s"] = rms(smooth(nom["v"])[CORE])
    data_space["rejected_frames_bg"] = nom["n_rejected"]

    # interpretation tests
    tests = {
        "bank_lab_scale_lag": fit_bank_scale_lag(inp, om_d, inp["bank"]),
        "bank_sitrec_scale_lag": fit_bank_scale_lag(inp, om_d, inp["bank_s"]),
    }
    for dT in (9.5,):
        tas_w = RG.lab_tas_kt(dT)
        om_w = bank_rate(inp["bank"], tas_w)
        tests[f"bank_lab_tas_isa_plus_{dT}"] = {"heading_change_deg": heading_change(om_w),
                                                "rms_vs_cloud_lab_deg_s": rms((smooth(om_w) - om_d)[CORE])}
        om_w2 = bank_rate(inp["bank_s"], tas_w)
        tests[f"bank_sitrec_tas_isa_plus_{dT}"] = {"heading_change_deg": heading_change(om_w2),
                                                   "rms_vs_cloud_lab_deg_s": rms((smooth(om_w2) - om_d)[CORE])}
    az_body = body_frame_azimuth(inp["az"], inp["bank"])
    body = cloud_rate(inp, az=az_body)
    tests["body_frame_azimuth"] = {
        "heading_change_deg": body["heading_change_deg"],
        "rms_vs_bank_lab_deg_s": rms((smooth(inp["om_a"]) - body["omega"])[CORE]),
        "rms_vs_bank_sitrec_deg_s": rms((smooth(inp["om_b"]) - body["omega"])[CORE]),
        "rms_vs_level_cloud_lab_deg_s": rms((body["omega"] - om_d)[CORE]),
        "level_minus_body_az_deg_start_end": [float(inp["az"][0] - az_body[0]), float(inp["az"][-1] - az_body[-1])]}
    tests["scale_fit_no_lag"] = scale_fit(inp, nom)
    tests["scale_fit_with_best_lag"] = scale_fit(inp, nom, tests["bank_lab_scale_lag"]["lag_only_scale1_frames"],
                                                 tests["bank_sitrec_scale_lag"]["lag_only_scale1_frames"])
    tests["readout_rounding"] = ("'0' is held 19 frames between '-1' (17) and '1' (17): a 1-deg-wide zero "
                                 "interval, so the readout rounds (truncation toward zero would hold '0' about "
                                 "twice as long)")
    for name, kw in {"h_cloud_8000ft": {"h_cloud_ft": 8000.0}, "h_cloud_18000ft": {"h_cloud_ft": 18000.0},
                     "refraction": {"refraction": True}, "no_cloud_wind": {"cloud_wind": (0.0, 0.0)},
                     "no_jet_wind": {"jet_wind": (270.0, 0.0)},
                     "literal_wind_from_090": {"jet_wind": (90.0, 120.0)},
                     "scale_640px": {"scale": 640.0 / PICTURE_W_PX, "aspect": 1.0},
                     "aspect_1.05": {"aspect": 1.05},
                     "theta_from_sitrec_bank": {"bank_for_theta": inp["bank_s"]},
                     "cloud_tile": {"source": "cloud"}}.items():
        r = cloud_rate(inp, **kw)
        tests.setdefault("sensitivity", {})[name] = {
            "heading_change_deg": r["heading_change_deg"], "rms_vs_nominal_deg_s": rms((r["omega"] - om_d)[CORE]),
            "rms_bank_lab_minus_this_deg_s": rms((S["om_a"] - r["omega"])[CORE]),
            "rms_cloud_sitrec_minus_this_deg_s": rms((S["om_c"] - r["omega"])[CORE]),
            "dist_h_km": r["dist_h_km"], "dip_deg": r["dip_deg"]}
    geo = {}
    for hc in (8000.0, 11740.0, 18000.0):
        for refr in (False, True):
            s_h, dip, s_t = texture_distance_h(hc * F.FT, TEXTURE_BELOW_DEG, refr)
            geo[f"{hc:.0f}ft_{'refr' if refr else 'norefr'}"] = {
                "deck_horizon_dip_deg": dip, "deck_horizon_km": s_t / 1000, "texture_dist_km": s_h / 1000}

    # reruns with the lab cloud rate (nominal) and the spread over MC histories
    reruns = {"A": rerun_a(inp), "B": rerun_b(inp),
              "bank_lab_advanced_by_best_lag": rerun_bank_lag(inp, tests["bank_lab_scale_lag"]["lag_only_scale1_frames"])}
    rng = np.random.default_rng(SEED + 1)
    pick = rng.choice(N_MC, 40, replace=False)
    a_min, b_bad, b_dev, b_span = [], [], [], []
    for j in pick:
        az_j, om_j = mc["az"][j], mc["draws"][j]
        lab_j = replace(inp["lab_inp"], az_deg=az_j)
        ra = RG.run_a(replace(lab_j, turn_override=om_j))
        a_min.append(ra["ground_speed_min_frame"])
        rb = RG.run_b(lab_j, turn_rate=om_j)
        b_bad.append(rb["n_no_intersection_frames"])
        b_dev.append(rb["straightness_top_view_good_frames"]["max_dev_nmi"])
        b_span.append(rb["air_heading_span_deg"])
    pct = lambda x: np.percentile(x, [0, 10, 50, 90, 100]).round(3).tolist()  # noqa: E731
    reruns["mc_40_histories_all_lab"] = {
        "percentiles": [0, 10, 50, 90, 100],
        "A_ground_speed_min_frame": pct(a_min), "B_no_intersection_frames": pct(b_bad),
        "B_max_dev_nmi_good_frames": pct(b_dev), "B_air_heading_span_deg": pct(b_span)}
    reruns["reference"] = {
        "A_pvr_bank_sitrec": RG._pick(RG.run_a(RG.pvr_inputs()), ["ground_speed_min_frame", "end_range_nmi"]),
        "A_pvr_cloud_sitrec_port": RG._pick(RG.run_a(replace(RG.pvr_inputs(), turn_override=RG.cloud_turn_rate(
            -RG.load_sitrec()["5 gaussian_smoothed_azimuth"].to_numpy(float)))), ["ground_speed_min_frame",
                                                                                   "end_range_nmi"]),
        "A_all_lab_bank_lab": RG._pick(RG.run_a(inp["lab_inp"]), ["ground_speed_min_frame", "end_range_nmi"]),
        "B_all_lab_bank_lab": RG._pick(RG.run_b(inp["lab_inp"]), ["n_no_intersection_frames", "end_range_nmi"])}
    om_raw_s = om_d
    curves = {"bank_lab": range_curve(None), "cloud_lab": range_curve(om_raw_s),
              "cloud_sitrec": range_curve(inp["om_c"]), "bank_sitrec": range_curve(inp["om_b"])}
    for k, om in (("bank_lab", None), ("cloud_lab", om_raw_s), ("cloud_sitrec", inp["om_c"])):
        curves[f"{k}_interval"] = range_curve(om, noise=FG.NOISE_GIMBAL)
    for k, om in (("bank_lab", None), ("cloud_lab", om_raw_s), ("bank_sitrec", inp["om_b"])):
        curves[f"{k}_spline_az"] = range_curve(om, az=inp["az"])
    reruns["range_curves"] = {k: range_summary(v) for k, v in curves.items()}

    out = pd.DataFrame({"frame": np.arange(N), "omega_bank_lab": inp["om_a"], "omega_bank_sitrec": inp["om_b"],
                        "omega_cloud_sitrec": inp["om_c"], "omega_cloud_lab": om_d,
                        "omega_cloud_lab_lo": lo, "omega_cloud_lab_hi": hi})
    summary = {
        "work_item": "M2.5 GIMBAL turn rate from cloud motion",
        "units": "deg/s, negative = left turn; lab frame numbering; 29.97 fps",
        "placeholders": "jet heading 315 at f0, jet wind 120 kt from 270, cloud wind 17 kt from 240 (Sitrec)",
        "scale": {"picture_px": [PICTURE_W_PX, PICTURE_H_PX], "fov_deg": FOV_DEG, "ppd_x": PPD_X, "ppd_y": PPD_Y,
                  "assumption": "0.35 deg spans the active picture (426 x 428 px), square field"},
        "cloud_geometry_nominal": {"h_cloud_ft": H_CLOUD_FT, "texture_below_deck_horizon_deg": TEXTURE_BELOW_DEG,
                                   "dip_deg": nom["dip_deg"], "texture_dist_h_km": nom["dist_h_km"],
                                   "deck_horizon_km": nom["deck_horizon_km"], "table": geo},
        "smoothing_frames": SMOOTH, "core_frames": [EDGE, N - EDGE - 1], "n_mc": N_MC,
        "comparison": comp, "data_space": data_space, "tests": tests, "reruns": reruns,
    }
    series = {"S": S, "lo": lo, "hi": hi, "nom": nom, "tile": tile, "pred": pred, "h_meas": h_meas,
              "inp": inp, "curves": curves, "body": body}
    return {"csv": out, "summary": summary, "series": series}


# ----------------------------------------------------------------------------- plot

def plot(series: dict, path: Path = PLOT) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    blue, orange, aqua, yellow, ink, muted, red = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#0b0b0b", "#52514e", "#c8324b"
    S, lo, hi, inp = series["S"], series["lo"], series["hi"], series["inp"]
    f = np.arange(N)
    fig, axs = plt.subplots(2, 2, figsize=(14, 9.5), constrained_layout=True)

    ax = axs[0, 0]
    ax.fill_between(f, lo, hi, color=ink, alpha=0.15, lw=0, label="(d) 95% band")
    ax.plot(f, S["om_d"], color=ink, lw=2.2, label="(d) cloud motion, this lab")
    ax.plot(f, S["om_a"], color=orange, lw=1.6, label="(a) bank, lab horizon bars")
    ax.plot(f, S["om_b"], color=yellow, lw=1.6, ls="--", label="(b) bank, Sitrec column")
    ax.plot(f, S["om_c"], color=blue, lw=1.6, label="(c) Sitrec Match Clouds (hand-keyed)")
    ax.set_title("Jet turn rate, 3 s smoothing", loc="left", fontsize=11)
    ax.set_xlabel("frame")
    ax.set_ylabel("turn rate (deg/s, negative = left)")
    ax.legend(frameon=False, fontsize=8, loc="lower left")

    ax = axs[0, 1]
    ax.fill_between(f, lo - S["om_d"], hi - S["om_d"], color=ink, alpha=0.15, lw=0)
    ax.axhline(0, color=ink, lw=1)
    ax.plot(f, S["om_a"] - S["om_d"], color=orange, lw=1.6, label="(a) - (d)")
    ax.plot(f, S["om_b"] - S["om_d"], color=yellow, lw=1.6, ls="--", label="(b) - (d)")
    ax.plot(f, S["om_c"] - S["om_d"], color=blue, lw=1.6, label="(c) - (d)")
    ax.set_xlim(EDGE, N - EDGE)
    ax.set_title("Difference from the lab cloud rate (grey: 95% band of (d))", loc="left", fontsize=11)
    ax.set_xlabel("frame")
    ax.set_ylabel("deg/s")
    ax.legend(frameon=False, fontsize=8)

    ax = axs[1, 0]
    h = series["h_meas"]
    ax.plot(f, series["nom"]["h_raw"], color=muted, lw=0.5, alpha=0.5, label="measured, per frame (whole picture)")
    ax.plot(f, h, color=ink, lw=2.2, label="measured, 3 s mean")
    ax.plot(f, smooth(series["tile"]["h"]), color=aqua, lw=1.4, label="measured, cloud tile")
    ax.plot(f, -inp["cs_curve"], color=blue, lw=1.4, ls="--", label="Sitrec hand-keyed cloud speed")
    ax.plot(f, series["pred"]["om_a"], color=orange, lw=1.4, label="predicted from (a) bank, lab")
    ax.plot(f, series["pred"]["om_b"], color=yellow, lw=1.4, ls="--", label="predicted from (b) bank, Sitrec")
    ax.set_ylim(-0.4, 0.45)
    ax.set_xlim(0, N - 1)
    ax.axhline(0, color=ink, lw=0.8)
    ax.set_title("Cloud motion along the image horizon (+ = content moves right)", loc="left", fontsize=11)
    ax.set_xlabel("frame")
    ax.set_ylabel(f"deg/s  (1 deg/s = {PPD_X / FPS:.1f} px/frame)")
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)

    ax = axs[1, 1]
    cv = series["curves"]
    for k, col, ls, lab in (("bank_lab", orange, "-", "(a) bank, lab"), ("bank_sitrec", yellow, "--", "(b) bank, Sitrec"),
                            ("cloud_sitrec", blue, "-", "(c) Sitrec clouds"), ("cloud_lab", ink, "-", "(d) lab clouds")):
        ax.plot(cv[k]["value"], cv[k]["misfit_deg_rms"], color=col, ls=ls, lw=2 if k == "cloud_lab" else 1.5, label=lab)
    ax.plot(cv["cloud_lab_spline_az"]["value"], cv["cloud_lab_spline_az"]["misfit_deg_rms"], color=ink, lw=1.5,
            ls=":", label="(d) lab clouds, azimuth spline")
    ax.plot(cv["bank_lab_spline_az"]["value"], cv["bank_lab_spline_az"]["misfit_deg_rms"], color=orange, lw=1.5,
            ls=":", label="(a) bank, lab, azimuth spline")
    ax.set_ylim(0, 1.9)
    ax.set_title("Constant-velocity misfit vs start range (solid: integer readout; dotted: spline)\n"
                 "(heading 315, wind 120 kt from 270: placeholders)", loc="left", fontsize=11)
    ax.set_xlabel("start range r0 (nmi)")
    ax.set_ylabel("RMS angular misfit (deg)")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def fov_variant(fov_deg: float, n: int = N_MC) -> pd.DataFrame:
    """The lab cloud-derived turn rate and its band for another field of view (M3.5).

    The field of view sets the image scale (0.35 deg spans the 426 px picture by default); a wider
    field means each pixel of measured cloud motion is a larger angle, so the inverted turn rate
    changes. Same inversion, smoothing and Monte Carlo as compute(), with the scale multiplied by
    FOV_DEG / fov_deg. Written to data/derived/gimbal/turn_rate_fov<NNN>.csv.
    """
    inp = inputs()
    scale = FOV_DEG / float(fov_deg)
    nom = cloud_rate(inp, scale=scale)
    mc = monte_carlo(inp, n=n, base_scale=scale)
    return pd.DataFrame({"frame": np.arange(N), "omega_cloud_lab": nom["omega"], "omega_cloud_lab_lo": mc["lo"],
                         "omega_cloud_lab_hi": mc["hi"], "fov_deg": float(fov_deg),
                         "heading_change_deg": nom["heading_change_deg"]})


def fov_csv(fov_deg: float) -> Path:
    return GIMBAL / f"turn_rate_fov{int(round(fov_deg * 100)):03d}.csv"


def main() -> int:
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--fov":
        fov = float(sys.argv[2])
        df = fov_variant(fov)
        df.to_csv(fov_csv(fov), index=False, float_format="%.5f")
        print(f"wrote {fov_csv(fov)}; heading change {df['heading_change_deg'].iloc[0]:.2f} deg")
        return 0
    res = compute()
    res["csv"].to_csv(OUT_CSV, index=False, float_format="%.5f")
    OUT_JSON.write_text(json.dumps(RG.strip(res["summary"]), indent=1) + "\n", encoding="utf-8")
    plot(res["series"])
    s = res["summary"]
    print(json.dumps(RG.strip({"comparison": s["comparison"], "data_space": s["data_space"]}), indent=1))
    print(f"wrote {OUT_CSV}, {OUT_JSON}, {PLOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
