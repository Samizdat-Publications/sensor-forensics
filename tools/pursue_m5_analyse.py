"""M5 analysis stage: label tests, range-size-speed curves and plots for the eight clips.

Run through tools/pursue_m5.py analyse. Every input is a file under
data/derived/pursue/<clip>/ (by-eye readings, gate scans, tracks, ladder sweep); every
number below that is not computed from those files is a stated assumption, listed in the
clip's summary.json under "assumptions".
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / "data" / "derived" / "pursue"
FIG = ROOT / "docs" / "results" / "pursue"

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
from extract.pursue_m5 import (  # noqa: E402
    anisotropic_spacing, gate_label_test, range_from_scale, range_like_test,
    size_speed_vs_range, size_speed_vs_ratio,
)

RANGES = np.geomspace(10, 30000, 60)    # m, assumed object range
RATIOS = np.linspace(0.02, 1.0, 50)     # R_obj / R_ref
HFOV = np.geomspace(0.3, 30, 40)        # deg, assumed horizontal field of view


def rd(clip: str, name: str) -> list[dict]:
    with (DER / clip.lower() / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Curves:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, curve, x_name, x, y_name, y, y_lo=None, y_hi=None):
        x = np.atleast_1d(x)
        y = np.broadcast_to(y, x.shape)
        lo = np.broadcast_to(np.nan if y_lo is None else y_lo, x.shape)
        hi = np.broadcast_to(np.nan if y_hi is None else y_hi, x.shape)
        for a, b, c, d in zip(x, y, lo, hi):
            self.rows.append({"curve": curve, "x_name": x_name, "x": f"{a:.6g}", "y_name": y_name,
                              "y": f"{b:.6g}", "y_lo": "" if np.isnan(c) else f"{c:.6g}",
                              "y_hi": "" if np.isnan(d) else f"{d:.6g}"})

    def write(self, clip: str) -> None:
        p = DER / clip.lower() / "curves.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["curve", "x_name", "x", "y_name", "y", "y_lo", "y_hi"])
            w.writeheader()
            w.writerows(self.rows)


def save_summary(clip: str, s: dict) -> None:
    (DER / clip.lower() / "summary.json").write_text(json.dumps(s, indent=2, default=float) + "\n",
                                                     encoding="utf-8")


# ---------------------------------------------------------------------------
# gate-label clips
# ---------------------------------------------------------------------------

def object_speed_px_s(track: list[dict], fps: float, window_s: float = 1.0) -> dict:
    f = np.array([int(r["frame"]) for r in track])
    x = np.array([float(r["x"]) for r in track])
    y = np.array([float(r["y"]) for r in track])
    w = int(round(window_s * fps))
    sp = []
    for i in range(len(f)):
        j = np.searchsorted(f, f[i] + w)
        if j < len(f) and f[j] - f[i] <= w * 1.2:
            sp.append(np.hypot(x[j] - x[i], y[j] - y[i]) / ((f[j] - f[i]) / fps))
    sp = np.array(sp)
    return {"median": float(np.median(sp)), "p10": float(np.percentile(sp, 10)),
            "p90": float(np.percentile(sp, 90)), "n": int(len(sp))}


def gate_clip(clip: str, width_px: int, obj_ext_px: float | None, obj_speed: dict | None,
              notes: dict) -> dict:
    r = rd(clip, "readings_manual.csv")
    lab = np.array([float(x["label_m"]) for x in r])
    gpx = np.array([float(x["gate_px"]) for x in r])
    zoom = np.array([float(x.get("scene_scale") or 1.0) for x in r])
    t = gate_label_test(lab, gpx, zoom)
    mpp = lab / gpx * zoom
    mpp_lo, mpp_hi = float(np.min(mpp)), float(np.max(mpp))
    c = Curves()
    c.add("system_range_vs_fov", "assumed_hfov_deg", HFOV, "range_at_gate_m",
          range_from_scale(t["m_per_px_median"], HFOV, width_px),
          range_from_scale(mpp_lo, HFOV, width_px), range_from_scale(mpp_hi, HFOV, width_px))
    s = {"clip": clip, "label_test": t, "m_per_px_range": [mpp_lo, mpp_hi], **notes}
    if obj_ext_px:
        sz, _ = size_speed_vs_ratio(RATIOS, obj_ext_px, 0, t["m_per_px_median"])
        c.add("object_size_vs_ratio", "range_ratio_obj_to_gate", RATIOS, "size_m", sz,
              RATIOS * obj_ext_px * mpp_lo, RATIOS * obj_ext_px * mpp_hi)
        s["object_extent_px"] = obj_ext_px
        s["object_size_at_ratio1_m"] = [obj_ext_px * mpp_lo, obj_ext_px * mpp_hi]
    if obj_speed:
        v = obj_speed["median"]
        c.add("object_speed_vs_ratio", "range_ratio_obj_to_gate", RATIOS, "transverse_speed_mps",
              RATIOS * v * t["m_per_px_median"], RATIOS * obj_speed["p10"] * mpp_lo,
              RATIOS * obj_speed["p90"] * mpp_hi)
        s["object_image_speed_px_s"] = obj_speed
        s["object_speed_at_ratio1_mps"] = [obj_speed["p10"] * mpp_lo, v * t["m_per_px_median"],
                                           obj_speed["p90"] * mpp_hi]
    c.write(clip)
    save_summary(clip, s)
    plot_curves(clip, c.rows, f"{clip}: gate label read as gate width "
                f"({t['m_per_px_median']:.3g} m/px at the gate)")
    return s


# ---------------------------------------------------------------------------
# PR111
# ---------------------------------------------------------------------------

def pr111() -> dict:
    clip = "DOW-UAP-PR111"
    r = [x for x in rd(clip, "readings_manual.csv") if x["label_m"]]
    g = rd(clip, "gate_manual.csv")
    gt = gate_label_test([float(x["label_m"]) for x in g], [float(x["gate_px"]) for x in g])
    segs = {}
    c = Curves()
    for sname in "ABCD":
        q = [x for x in r if x["segment"] == sname]
        L = np.array([float(x["label_m"]) for x in q])
        e = np.array([float(x["el_deg"]) for x in q])
        f = np.array([int(x["frame"]) for x in q]) / 29.97003
        t = range_like_test(L, e)
        hz = t["horizontal"]
        segs[sname] = {"frames": [int(q[0]["frame"]), int(q[-1]["frame"])], "n": len(q),
                       "label_range": [float(L.min()), float(L.max())],
                       "el_range_deg": [float(e.min()), float(e.max())],
                       "h_below_sensor": t["h_median"], "h_rel_spread": t["h_rel_spread"],
                       "rounding_rel_halfwidth": t["rounding_rel_halfwidth_median"],
                       "horizontal_closing_per_s": float(-np.polyfit(f, hz, 1)[0]),
                       "slant_closing_per_s": float(-np.polyfit(f, L, 1)[0])}
    sea = float(np.mean([segs["B"]["h_below_sensor"], segs["D"]["h_below_sensor"]]))
    H = np.linspace(20, 400, 77)
    for sname in "AC":
        h = segs[sname]["h_below_sensor"]
        hh = h * (1 + segs[sname]["rounding_rel_halfwidth"])
        hl = h * (1 - segs[sname]["rounding_rel_halfwidth"])
        c.add(f"object_altitude_seg{sname}", "platform_altitude_label_units", H,
              "object_altitude_label_units", H - h, H - hh, H - hl)
    for sname in "ABCD":
        q = [x for x in r if x["segment"] == sname]
        c.add(f"height_below_sensor_seg{sname}", "frame", [int(x["frame"]) for x in q],
              "label_x_sin_el", [float(x["label_m"]) * np.sin(np.radians(abs(float(x["el_deg"]))))
                                 for x in q])
    c.write(clip)
    s = {"clip": clip, "gate_label_test": gt, "segments": segs,
         "sea_plane_h_if_B_D_are_surface": sea,
         "object_altitude_if_metres_and_B_D_surface": {
             "A": sea - segs["A"]["h_below_sensor"], "C": sea - segs["C"]["h_below_sensor"]},
         "assumptions": ["label read as slant range in label units (M taken as metres only where stated)",
                         "elevation readout is the line-of-sight depression from the horizontal",
                         "whole-degree display rounding, half width 0.5 deg"]}
    save_summary(clip, s)
    plot_pr111(clip, r, segs, c.rows)
    return s


# ---------------------------------------------------------------------------
# PR113
# ---------------------------------------------------------------------------

def pr113() -> dict:
    clip = "DOW-UAP-PR113"
    lad = rd(clip, "ladder_auto.csv")
    A, S = [], []
    for x in lad:
        a0, s0, q0 = float(x["angle_deg"]), float(x["spacing_px"]), float(x["quality"])
        a1, s1, q1 = (float(x["angle_deg_rolled"]), float(x["spacing_px_rolled"]),
                      float(x["quality_rolled"]))
        if abs(a0) < 1 and q0 >= 0.45:
            A.append(0.0)
            S.append(s0)
        elif abs(a1) >= 4.5 and q1 >= 0.45:
            A.append(a1)
            S.append(s1)
    A, S = np.array(A), np.array(S)
    from scipy.optimize import least_squares
    res = least_squares(lambda p: anisotropic_spacing(A, p[0], p[1]) - S, [180, 1.5],
                        loss="soft_l1", f_scale=2.0)
    J = res.jac
    cov = np.linalg.inv(J.T @ J) * np.median(res.fun ** 2) / 0.45
    s0, aspect = (float(v) for v in res.x)
    s0_sd, a_sd = (float(v) for v in np.sqrt(np.diag(cov)))
    zero = S[A == 0]
    kv = float(np.median(zero)) / 5.0  # px per ladder degree, vertical
    tr = rd(clip, "object_track.csv")
    fx = np.array([float(r["x"]) for r in tr])
    fy = np.array([float(r["y"]) for r in tr])
    dx = float(np.polyfit(np.arange(len(fx)), fx, 1)[0])
    dy = float(np.polyfit(np.arange(len(fy)), fy, 1)[0])
    ex = float(np.median([float(r["ext_x"]) for r in tr]))
    ey = float(np.median([float(r["ext_y"]) for r in tr]))
    fps = 30.0
    cases = {"square pixels (H&K assumption)": 1.0, f"fitted aspect {aspect:.2f}": aspect,
             "reticle ring by eye 1.8": 1.8}
    c = Curves()
    out = {}
    for name, a in cases.items():
        w_deg = np.hypot(dx / a, dy) / kv * fps  # deg/s
        size_deg = max(ex / (a * kv), ey / kv)
        ifov = np.radians(1.0 / kv)
        tag = f"aspect_{a:.2f}"
        c.add(f"transverse_speed_{tag}", "range_m", RANGES, "speed_mps",
              RANGES * np.radians(w_deg))
        c.add(f"size_{tag}", "range_m", RANGES, "size_m", RANGES * np.radians(size_deg))
        out[name] = {"aspect": a, "omega_deg_s": float(w_deg), "omega_rad_s": float(np.radians(w_deg)),
                     "size_deg": float(size_deg), "hfov_deg_over_1850px": 1850 / (a * kv),
                     "range_for_mach1_m": 340.0 / np.radians(w_deg),
                     "size_at_100m_m": 100 * np.radians(size_deg),
                     "speed_at_100m_mps": 100 * np.radians(w_deg)}
        _ = ifov
    # Haqq-Misra and Kopparapu's numbers, for comparison: 35.4 px/deg, 142 px/frame, 25 px
    hk_w = 142 / 35.4 * fps
    c.add("transverse_speed_HK2026", "range_m", RANGES, "speed_mps", RANGES * np.radians(hk_w))
    c.add("size_HK2026", "range_m", RANGES, "size_m", RANGES * np.radians(25 / 35.4))
    c.add("ladder_spacing_vs_roll", "rung_image_angle_deg", A, "spacing_px", S)
    c.write(clip)
    s = {"clip": clip, "ladder": {
            "type": "HUD pitch ladder (dive lines numbered downward 0 to 16 s, horizon line near 10 s, "
                    "climb lines numbered upward after)",
            "n_samples_used": int(len(A)), "n_zero_roll": int(len(zero)),
            "spacing_zero_roll_px_per_5": [float(np.percentile(zero, 10)), float(np.median(zero)),
                                           float(np.percentile(zero, 90))],
            "px_per_deg_vertical": kv, "fit_s0_px": s0, "fit_s0_sd": s0_sd,
            "fit_aspect_x_over_y": aspect, "fit_aspect_sd": a_sd,
            "max_rung_angle_used_deg": float(np.max(np.abs(A))),
            "reticle_ring_by_eye_px": [172, 94]},
         "object": {"frames": [int(tr[0]["frame"]), int(tr[-1]["frame"])],
                    "rate_px_per_frame": [dx, dy, float(np.hypot(dx, dy))],
                    "extent_px": [ex, ey]},
         "cases": out,
         "HK2026": {"px_per_deg": 35.4, "fov_deg": 54, "omega_rad_s": 2.10,
                    "omega_rad_s_recomputed": float(np.radians(hk_w))},
         "assumptions": ["the HUD pitch ladder is conformal (1 ladder degree = 1 degree of view)",
                         "the background did not move across frames 406 to 411 (measured shift under 0.1 px/frame)",
                         "frame rate 30 fps, as the container states"]}
    save_summary(clip, s)
    plot_curves(clip, c.rows, "DOW-UAP-PR113: transit object, pitch-ladder scale", logx=True)
    return s


# ---------------------------------------------------------------------------
# PR149
# ---------------------------------------------------------------------------

def pr149() -> dict:
    clip = "DOW-UAP-PR149"
    tr = rd(clip, "object_track.csv")
    sh = rd(clip, "ship_track.csv")
    f = np.array([int(r["frame"]) for r in tr])
    x = np.array([float(r["x"]) for r in tr])
    y = np.array([float(r["y"]) for r in tr])
    vx, vy = np.polyfit(f, x, 1)[0], np.polyfit(f, y, 1)[0]
    sf = np.array([int(r["frame"]) for r in sh])
    scx = np.array([float(r["cx"]) for r in sh])
    scy = np.array([float(r["cy"]) for r in sh])
    sel = sf <= 100
    svx, svy = np.polyfit(sf[sel], scx[sel], 1)[0], np.polyfit(sf[sel], scy[sel], 1)[0]
    Lpx = float(np.median([float(r["axis_len_px"]) for r in sh]))
    fps = 30.0
    v_frame = float(np.hypot(vx, vy) * fps)
    v_rel = float(np.hypot(vx - svx, vy - svy) * fps)
    ext_cross = float(np.median([float(r["ext_y"]) for r in tr]))
    ext_along = float(np.median([float(r["ext_x"]) for r in tr]))
    c = Curves()
    bands = {"HK2026_150_200m": (150.0, 200.0), "lab_120_200m": (120.0, 200.0)}
    out = {}
    for name, (lo, hi) in bands.items():
        mlo, mhi = lo / Lpx, hi / Lpx
        c.add(f"speed_bound_frame_{name}", "range_ratio_obj_to_ship", RATIOS, "transverse_speed_mps",
              RATIOS * v_frame * (mlo + mhi) / 2, RATIOS * v_frame * mlo, RATIOS * v_frame * mhi)
        c.add(f"speed_rel_ship_{name}", "range_ratio_obj_to_ship", RATIOS, "transverse_speed_mps",
              RATIOS * v_rel * (mlo + mhi) / 2, RATIOS * v_rel * mlo, RATIOS * v_rel * mhi)
        c.add(f"size_cross_track_{name}", "range_ratio_obj_to_ship", RATIOS, "size_m",
              RATIOS * ext_cross * (mlo + mhi) / 2, RATIOS * ext_cross * mlo, RATIOS * ext_cross * mhi)
        c.add(f"ship_range_vs_fov_{name}", "assumed_hfov_deg", HFOV, "ship_range_m",
              range_from_scale((mlo + mhi) / 2, HFOV, 1920), range_from_scale(mlo, HFOV, 1920),
              range_from_scale(mhi, HFOV, 1920))
        out[name] = {"m_per_px": [mlo, mhi], "bound_frame_mps": [v_frame * mlo, v_frame * mhi],
                     "bound_rel_ship_mps": [v_rel * mlo, v_rel * mhi],
                     "size_cross_at_ratio1_m": [ext_cross * mlo, ext_cross * mhi]}
    c.write(clip)
    s = {"clip": clip, "ship_length_px": Lpx, "object_rate_px_per_frame": [float(vx), float(vy)],
         "ship_drift_px_per_frame": [float(svx), float(svy)], "v_frame_px_s": v_frame,
         "v_rel_ship_px_s": v_rel, "object_extent_px": {"along_track": ext_along, "cross_track": ext_cross},
         "frames": [int(f[0]), int(f[-1])], "bands": out,
         "HK2026": {"v_px_per_frame": 20.2, "hull_px": 920, "bound_mps": [99, 132]},
         "geometry_note": "the object stays below the ship's waterline in the image, so for an object above "
                          "the sea its line of sight meets the sea nearer than the ship: R_obj/R_ship < 1",
         "assumptions": ["ship seen near broadside (foreshortening only lowers the true m/px, so the bound holds)",
                         "ship length 150 to 200 m (H&K, Handymax) or 120 to 200 m (lab: geared four-crane "
                         "general cargo or bulk carrier, class not identified)", "30 fps"]}
    save_summary(clip, s)
    plot_curves(clip, c.rows, "DOW-UAP-PR149: speed and size bound from the ship scale")
    return s


# ---------------------------------------------------------------------------
# plots
# ---------------------------------------------------------------------------

def plot_curves(clip: str, rows: list[dict], title: str, logx: bool = False) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups: dict[tuple, dict] = {}
    for r in rows:
        groups.setdefault((r["x_name"], r["y_name"]), {}).setdefault(r["curve"], []).append(r)
    keys = [k for k in groups if k[0] != "frame" and k[0] != "rung_image_angle_deg"]
    fig, axes = plt.subplots(1, len(keys), figsize=(5.2 * len(keys), 4.2), squeeze=False)
    for ax, k in zip(axes[0], keys):
        for name, rr in groups[k].items():
            xs = np.array([float(r["x"]) for r in rr])
            ys = np.array([float(r["y"]) for r in rr])
            ax.plot(xs, ys, label=name)
            if rr[0]["y_lo"]:
                lo = np.array([float(r["y_lo"]) for r in rr])
                hi = np.array([float(r["y_hi"]) for r in rr])
                ax.fill_between(xs, lo, hi, alpha=0.2)
        if k[0] in ("range_m", "assumed_hfov_deg") or logx:
            ax.set_xscale("log")
            ax.set_yscale("log")
        if k[1] in ("speed_mps", "transverse_speed_mps"):
            ax.axhline(340, color="gray", ls="--", lw=0.8)
            ax.text(ax.get_xlim()[0], 340, " Mach 1", va="bottom", fontsize=7, color="gray")
        ax.set_xlabel(k[0].replace("_", " "))
        ax.set_ylabel(k[1].replace("_", " "))
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=6)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{clip}.png", dpi=110)
    plt.close(fig)


def plot_pr111(clip, r, segs, rows) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    allr = rd(clip, "readings_manual.csv")
    ax[0].plot([int(x["frame"]) for x in allr], [float(x["el_deg"]) for x in allr], "k.-", ms=3)
    ax[0].set_ylabel("elevation readout (deg)")
    a2 = ax[0].twinx()
    for sname in "ABCD":
        q = [x for x in r if x["segment"] == sname]
        a2.plot([int(x["frame"]) for x in q], [float(x["label_m"]) for x in q], "o", ms=3, label=f"label seg {sname}")
    a2.set_yscale("log")
    a2.set_ylabel("NNM label")
    a2.legend(fontsize=6)
    ax[0].set_xlabel("frame")
    for rr in [x for x in rows if x["x_name"] == "frame"]:
        pass
    for sname in "ABCD":
        q = [x for x in rows if x["curve"] == f"height_below_sensor_seg{sname}"]
        ax[1].plot([float(x["x"]) for x in q], [float(x["y"]) for x in q], "o-", ms=3,
                   label=f"seg {sname}: {segs[sname]['h_below_sensor']:.1f}")
    ax[1].set_yscale("log")
    ax[1].set_xlabel("frame")
    ax[1].set_ylabel("label x sin|el| (height below sensor, label units)")
    ax[1].legend(fontsize=7)
    for sname in "AC":
        q = [x for x in rows if x["curve"] == f"object_altitude_seg{sname}"]
        xs = [float(x["x"]) for x in q]
        ax[2].plot(xs, [float(x["y"]) for x in q], label=f"object seg {sname}")
        ax[2].fill_between(xs, [float(x["y_lo"]) for x in q], [float(x["y_hi"]) for x in q], alpha=0.2)
    ax[2].axvline(71.5, color="gray", ls="--", lw=0.8)
    ax[2].text(73, 5, "sea plane if B, D are the surface", fontsize=7, color="gray", rotation=90)
    ax[2].set_xlabel("platform altitude above the sea (label units)")
    ax[2].set_ylabel("object altitude above the sea (label units)")
    ax[2].legend(fontsize=7)
    for a in ax:
        a.grid(alpha=0.3, which="both")
    fig.suptitle("DOW-UAP-PR111: NNM label behaves like slant range to a level plane", fontsize=10)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{clip}.png", dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------

GATE_NOTES_FILE = DER / "gate_clip_inputs.json"


def analyse_all() -> dict:
    out = {"DOW-UAP-PR113": pr113(), "DOW-UAP-PR149": pr149(), "DOW-UAP-PR111": pr111()}
    inputs = json.loads(GATE_NOTES_FILE.read_text(encoding="utf-8"))
    for clip, cfg in inputs.items():
        sp = None
        if cfg.get("track"):
            sp = object_speed_px_s(rd(clip, "object_track.csv"), cfg["fps"])
        out[clip] = gate_clip(clip, cfg["width_px"], cfg.get("object_extent_px"), sp,
                              {"notes": cfg.get("notes", ""), "assumptions": cfg.get("assumptions", [])})
    (DER / "m5_summary.json").write_text(json.dumps(out, indent=2, default=float) + "\n", encoding="utf-8")
    print("analysed:", ", ".join(out))
    return out
