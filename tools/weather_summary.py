"""Derive the numbers quoted in docs/weather.md from the saved ERA5 and IGRA files.

Run from the repo root: .venv/Scripts/python tools/weather_summary.py
Writes data/weather/summary_gimbal_gofast.csv (every UTC hour of the four candidate dates) and prints the
tables and comparisons used in the write-up.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from solve import weather as W  # noqa: E402

FT, KT = W.FT, W.KT
CASES = ("2015-01-20", "2015-01-21", "2015-01-24", "2015-01-25")
STATIONS = {  # IGRA id: (event, lat, lon)
    "USM00072206": ("gimbal_gofast", 30.4839, -81.7011),
    "USM00072402": ("gimbal_gofast", 37.9333, -75.4667),
    "USM00072293": ("flir1", 32.85, -117.12),
}


def gimbal_tables():
    times = W.gimbal_candidate_times(CASES)
    a = W.summary_table("gimbal", times, (25000, 13000), ref="height")
    b = W.summary_table("gimbal", times, (25000, 13000), ref="pressure_altitude")
    b = b.add_suffix("_pa").rename(columns={"time_utc_pa": "time_utc"})
    out = a.merge(b, on="time_utc")
    out.to_csv(ROOT / "data" / "weather" / "summary_gimbal_gofast.csv", index=False)
    return out


def igra_vs_era5():
    rows = []
    for st, (ev, lat, lon) in STATIONS.items():
        df = pd.read_csv(ROOT / "data" / "weather" / f"igra_{st}_{ev}.csv")
        df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
        grid = W.load_grid(ev)
        if grid is None:
            continue
        glat, glon = grid.latitude.values, grid.longitude.values
        if not (glat.min() <= lat <= glat.max() and glon.min() <= lon <= glon.max()):
            print("station outside grid:", st)
            continue
        for t, d in df.groupby("time"):
            if np.datetime64(t, "ns") not in grid.time.values:
                continue
            d = d.dropna(subset=["wind_dir_deg", "wind_speed_ms", "temp_c"]).sort_values("pressure_hpa")
            if len(d) < 10:
                continue
            u_r, v_r = W.speed_dir_to_uv(d.wind_speed_ms.values, d.wind_dir_deg.values)
            g = grid.sel(time=np.datetime64(t, "ns")).interp(latitude=lat, longitude=lon, method="linear")
            lev = g.level.values.astype(float)
            for p in (850, 700, 500, 400, 300, 250, 200, 150):
                if not (d.pressure_hpa.min() <= p <= d.pressure_hpa.max()):
                    continue
                lp = np.log(d.pressure_hpa.values)
                ur = np.interp(np.log(p), lp, u_r)
                vr = np.interp(np.log(p), lp, v_r)
                tr = np.interp(np.log(p), lp, d.temp_c.values) + 273.15
                zr = np.interp(np.log(p), lp, d.height_m.values) if d.height_m.notna().all() else np.nan
                ue = np.interp(np.log(p), np.log(lev), g.u_component_of_wind.values)
                ve = np.interp(np.log(p), np.log(lev), g.v_component_of_wind.values)
                te = np.interp(np.log(p), np.log(lev), g.temperature.values)
                ze = np.interp(np.log(p), np.log(lev), g.height.values)
                sr, dr = W.uv_to_speed_dir(ur, vr)
                se, de = W.uv_to_speed_dir(ue, ve)
                rows.append(dict(station=st, time=t, p=p, spd_sonde_kt=sr / KT, spd_era5_kt=se / KT,
                                 dir_sonde=dr, dir_era5=de, vec_diff_ms=float(np.hypot(ur - ue, vr - ve)),
                                 dt_k=tr - te, dz_m=zr - ze))
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    g = gimbal_tables()
    print(g[["time_utc", "speed_kt_25000", "dir_from_deg_25000", "temp_c_25000", "speed_kt_13000", "dir_from_deg_13000",
             "temp_c_13000", "speed_kt_25000_pa", "dir_from_deg_25000_pa", "temp_c_25000_pa", "speed_kt_13000_pa",
             "dir_from_deg_13000_pa"]].to_string(index=False))
    i = (g["speed_kt_25000"] - 120).abs().idxmin()
    print("\nclosest to 120 kt at 25,000 ft (height ref):", g.loc[i, ["time_utc", "speed_kt_25000", "dir_from_deg_25000", "temp_c_25000"]].to_dict())
    j = (g["speed_kt_25000_pa"] - 120).abs().idxmin()
    print("closest to 120 kt at 25,000 ft (pressure altitude):", g.loc[j, ["time_utc", "speed_kt_25000_pa", "dir_from_deg_25000_pa", "temp_c_25000_pa"]].to_dict())
    for d in CASES:
        s = g[g.time_utc.str.startswith(d)]
        print(d, "25k speed range", s.speed_kt_25000.min(), s.speed_kt_25000.max(), "dir range", s.dir_from_deg_25000.min(), s.dir_from_deg_25000.max(),
              "| 13k speed range", s.speed_kt_13000.min(), s.speed_kt_13000.max(), "dir", s.dir_from_deg_13000.min(), s.dir_from_deg_13000.max(),
              "| T25k range", s.temp_c_25000.min(), s.temp_c_25000.max())
    print("\nFLIR1")
    ft = W.summary_table("flir1", pd.date_range("2004-11-14T18:00", "2004-11-14T23:00", freq="1h"), (20000, 25000, 13000))
    print(ft.to_string(index=False))
    # fractional times
    for t in ("2004-11-14T20:00", "2004-11-14T20:30", "2004-11-14T21:00"):
        print(t, W.wind_speed_dir_at("flir1", t, 20000 * FT, 31.205, -117.870), "T(K)", W.temperature_at("flir1", t, 20000 * FT, 31.205, -117.870))
    for t in ("2015-01-25T02:30", "2015-01-25T02:00", "2015-01-25T03:00"):
        print(t, "25k", W.wind_speed_dir_at("gimbal", t, 25000 * FT, 30.5, -76.5), "13k", W.wind_speed_dir_at("gimbal", t, 13000 * FT, 30.5, -76.5))
    cmp_ = igra_vs_era5()
    cmp_.to_csv(ROOT / "data" / "weather" / "igra_vs_era5.csv", index=False)
    print("\nradiosonde vs ERA5")
    print(cmp_.groupby(["station"]).agg(n=("p", "size"), vec_rms=("vec_diff_ms", lambda x: float(np.sqrt(np.mean(np.square(x))))),
                                        vec_mean=("vec_diff_ms", "mean"), dT_mean=("dt_k", "mean"), dT_std=("dt_k", "std")).round(2))
    print(cmp_[cmp_.p.isin([500, 250, 200])].groupby(["station", "p"]).agg(
        n=("p", "size"), vec_mean=("vec_diff_ms", "mean"), dT=("dt_k", "mean"), dspd=("spd_sonde_kt", "mean"), espd=("spd_era5_kt", "mean")).round(2))
    return g, cmp_


if __name__ == "__main__":
    main()
