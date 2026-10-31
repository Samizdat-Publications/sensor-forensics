"""M2 reproduction: GOFAST object altitude and speed, Sitrec's way and the lab's way.

1. "sitrec": Sitrec v1's default GOFAST pipeline from Sitrec's own inputs
   (data/reference/sitrec/data/gofast/*.csv; SitGoFast.js defaults as documented in
   docs/prior-work/sitrec.md): keyframes expanded linearly, 50-frame rolling
   averages on El, RNG and bank, jet TAS 369 kt but turn rate from a fixed 351 kt
   (g = 9.77468), heading 262, jet wind 120 kt from 270, two-point straight track
   between frames 375 and 1030, 25,000 ft, no refraction.
2. "lab": the same geometry from this lab's per-frame readings
   (data/derived/gofast/symbology_final.csv and image_track.csv), TAS from the
   on-screen Mach (ISA, ERA5 temperature when available), bank from the horizon
   bars, each readout taken as the center of its display interval.

Published comparison values: Sitrec (observed 2024 run) 13,151 / 13,208 ft at
frames 375 / 1030, about 64 kt ground speed toward about 93 deg; AARO 13,219 /
13,150 ft at its two sample instants. Tolerances (stated in _PLAN.md before the
run): altitude within 300 ft, speed within 5 kt.

Usage: python -m solve.repro_gofast  (writes docs/reproductions/gofast.json)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import atmosphere as A
from . import frames as F
from .jet import integrate, wind_from
from .los import points_at_range, sight_lines

ROOT = Path(__file__).resolve().parents[1]
SITREC = ROOT / "data" / "reference" / "sitrec" / "data" / "gofast"
FPS = 30000 / 1001
N = 1031
A_FRAME, B_FRAME = 375, 1030


def _expand(path: Path, col: str) -> np.ndarray:
    k = pd.read_csv(path, encoding="utf-8-sig")
    return np.interp(np.arange(N), k["Frame"].to_numpy(float), k[col].to_numpy(float))


def _roll(x: np.ndarray, w: int = 50) -> np.ndarray:
    return pd.Series(x).rolling(w, min_periods=1).mean().to_numpy()


def _two_point(sl, rng_m: np.ndarray, refraction: bool = False) -> dict:
    pos, alt = points_at_range(sl, rng_m, refraction)
    a, b = pos[A_FRAME], pos[B_FRAME]
    dt = (B_FRAME - A_FRAME) / FPS
    v = (b[:2] - a[:2]) / dt
    return {
        "alt_ft_at_375": float(alt[A_FRAME] / F.FT),
        "alt_ft_at_1030": float(alt[B_FRAME] / F.FT),
        "ground_speed_kt": float(np.hypot(*v) / F.KT),
        "ground_track_deg": float(np.degrees(np.arctan2(v[0], v[1])) % 360),
        "range_nmi_375_1030": [float(rng_m[A_FRAME] / F.NMI), float(rng_m[B_FRAME] / F.NMI)],
        "alt_ft_per_frame_min_max": [float(np.nanmin(alt[A_FRAME:]) / F.FT), float(np.nanmax(alt[A_FRAME:]) / F.FT)],
    }


def sitrec_way() -> dict:
    t = np.arange(N) / FPS
    az = _expand(SITREC / "Go Fast AZ.csv", "Az")
    el = _roll(_expand(SITREC / "Go Fast El.csv", "El"))
    rng = _roll(_expand(SITREC / "Go Fast RNG.csv", "RNG")) * F.NMI
    tilt = pd.read_csv(SITREC / "Go Fast Tilt tracking.csv", encoding="utf-8-sig")
    bank_csv = tilt.iloc[:, 12].to_numpy(float)
    bank = _roll(-np.append(bank_csv, bank_csv[-1])[:N])
    rate = np.degrees(9.77468 * np.tan(np.radians(bank)) / (351 * F.KT))
    track = integrate(t, 369 * F.KT, bank, 262.0, wind_enu=wind_from(270, 120 * F.KT),
                      altitude=25_000 * F.FT, turn_rate_deg_s=rate)
    sl = sight_lines(track, az, el, "level")
    out = _two_point(sl, rng)
    target_wind = wind_from(274, 65 * F.KT)
    gv = np.array([np.sin(np.radians(out["ground_track_deg"])), np.cos(np.radians(out["ground_track_deg"]))]) \
        * out["ground_speed_kt"] * F.KT
    out["air_speed_kt_vs_65kt_from_274"] = float(np.hypot(*(gv - target_wind[:2])) / F.KT)
    return out


def _lab_series(field: str, sym: pd.DataFrame) -> np.ndarray:
    s = sym[sym["field"] == field].sort_values("frame")["value"].tolist()
    out = []
    for v in s:
        if v in ("blank", "", None) or (isinstance(v, float) and np.isnan(v)):
            out.append(np.nan)
        elif field == "azimuth":
            out.append(float(v[:-1]) * (-1 if v.endswith("L") else 1))
        else:
            out.append(float(v))
    return np.array(out)


def lab_way(heading0: float = 262.0, wind=(270, 120), refraction: bool = False) -> dict:
    sym = pd.read_csv(ROOT / "data" / "derived" / "gofast" / "symbology_final.csv", dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    cues = pd.read_csv(ROOT / "data" / "derived" / "gofast" / "image_track.csv")
    t = np.arange(N) / FPS
    az, el = _lab_series("azimuth", sym), _lab_series("elevation", sym)
    rng = _lab_series("range", sym) * F.NMI
    mach, alt_ft = _lab_series("mach", sym), _lab_series("altitude", sym)
    bank_col = next(c for c in cues.columns if c.startswith("bank"))
    bank = _roll(cues[bank_col].to_numpy(float))
    tas = A.mach_to_tas(mach, alt_ft * F.FT)
    track = integrate(t, tas, bank, heading0, wind_enu=wind_from(wind[0], wind[1] * F.KT), altitude=alt_ft * F.FT)
    sl = sight_lines(track, az, el, "level")
    pos, alt = points_at_range(sl, rng, refraction)
    out = _two_point(sl, np.nan_to_num(rng, nan=0.0), refraction)
    # Straight-line fit over every frame with a range (not just two frames).
    ok = ~np.isnan(rng)
    tt = t[ok]
    vx = np.polyfit(tt, pos[ok, 0], 1)[0]
    vy = np.polyfit(tt, pos[ok, 1], 1)[0]
    out["fit_ground_speed_kt"] = float(np.hypot(vx, vy) / F.KT)
    out["fit_ground_track_deg"] = float(np.degrees(np.arctan2(vx, vy)) % 360)
    out["alt_ft_mean_with_range"] = float(np.mean(alt[ok]) / F.FT)
    out["tas_kt_mean"] = float(np.mean(tas) / F.KT)
    out["first_range_frame"] = int(np.argmax(ok))
    return out


def main() -> int:
    res = {"sitrec_way": sitrec_way(), "lab_way": lab_way(),
           "lab_way_refraction": lab_way(refraction=True),
           "published": {"sitrec_observed_alt_ft": [13151, 13208], "sitrec_observed_ground_speed_kt": 64,
                         "sitrec_observed_track_deg": 93, "aaro_alt_ft": [13219, 13150]},
           "tolerance": {"alt_ft": 300, "speed_kt": 5}}
    out = ROOT / "docs" / "reproductions" / "gofast.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
