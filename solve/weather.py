"""Upper-air weather for the Navy events: ERA5 profiles and a small interpolation layer.

Data lives in data/weather/ (see data/weather/SOURCES.md):

- ``era5_<event>_profiles.csv``: hourly vertical profiles at the box centre
  (time, level_hpa, height_m, u_ms, v_ms, t_k). Always present, commit-sized.
- ``era5_<event>.nc``: the gridded hourly box. Optional; when present and a lat/lon is
  given, profiles are interpolated bilinearly in space first.
- ``igra_<station>_<event>.csv``: radiosonde soundings (used for cross-checks only).

Conventions
-----------
- u is the eastward wind component, v the northward one, both in m/s. Wind *from the
  west* has u > 0. Meteorological direction is "degrees the wind blows from", so
  ``from_deg = atan2(-u, -v)`` (a westerly is 270, a northerly 360).
- Vertical interpolation is linear in geopotential height (geopotential / g0) between the
  pressure levels at each of the two bracketing hours, then linear in time. At a grid point
  (level, hour, grid node) the stored value is returned exactly.
- Heights are MSL geopotential metres. Aircraft readouts are *pressure* altitude; set
  ``ref="pressure_altitude"`` to convert an ISA altitude to its pressure and interpolate
  linearly in log-pressure instead. Over the Atlantic in January the two differ by a few
  hundred metres at 25,000 ft; both are reported in docs/weather.md.
- Times are UTC. Naive values are taken as UTC.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "weather"

FT = 0.3048
KT = 1852.0 / 3600.0  # m/s per knot

# event key -> (file stem, default box centre lat, lon)
EVENTS: dict[str, tuple[str, float, float]] = {
    "gimbal_gofast": ("gimbal_gofast", 30.5, -76.5),
    "flir1": ("flir1", 31.205, -117.870),
}
ALIASES = {"gimbal": "gimbal_gofast", "gofast": "gimbal_gofast", "gimbal_gofast": "gimbal_gofast", "flir1": "flir1"}


def _key(event: str) -> str:
    try:
        return ALIASES[event.lower()]
    except KeyError as e:
        raise KeyError(f"unknown event {event!r}; known: {sorted(ALIASES)}") from e


def centre(event: str) -> tuple[float, float]:
    _, lat, lon = EVENTS[_key(event)]
    return lat, lon


# ---------------------------------------------------------------- unit helpers


def uv_to_speed_dir(u, v):
    """(u, v) m/s -> (speed m/s, direction the wind blows FROM in degrees, 0..360)."""
    u = np.asarray(u, float)
    v = np.asarray(v, float)
    return np.hypot(u, v), np.degrees(np.arctan2(-u, -v)) % 360.0


def speed_dir_to_uv(speed, from_deg):
    """Speed (m/s) and meteorological from-direction (deg) -> (u, v) m/s."""
    s = np.asarray(speed, float)
    d = np.radians(np.asarray(from_deg, float))
    return -s * np.sin(d), -s * np.cos(d)


def _to_ts(t) -> pd.Timestamp:
    ts = pd.Timestamp(t)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


# ---------------------------------------------------------------- loading


@lru_cache(maxsize=None)
def _profiles_cached(key: str, path_str: str) -> pd.DataFrame:
    df = pd.read_csv(path_str)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    return df.sort_values(["time", "height_m"]).reset_index(drop=True)


def load_profiles(event: str, path: Path | None = None) -> pd.DataFrame:
    """Hourly ERA5 profiles at the box centre: time, level_hpa, height_m, u_ms, v_ms, t_k."""
    key = _key(event)
    p = Path(path) if path else DATA_DIR / f"era5_{EVENTS[key][0]}_profiles.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing; run tools/fetch_weather.py era5 {key}")
    return _profiles_cached(key, str(p)).copy()


@lru_cache(maxsize=None)
def _grid_cached(path_str: str):
    import xarray as xr

    ds = xr.load_dataset(path_str)
    return ds.sortby("latitude").sortby("longitude").sortby("time")


def load_grid(event: str, path: Path | None = None):
    """Gridded hourly ERA5 box (xarray Dataset) or None if the file is not present."""
    key = _key(event)
    p = Path(path) if path else DATA_DIR / f"era5_{EVENTS[key][0]}.nc"
    if not p.exists():
        return None
    return _grid_cached(str(p))


# ---------------------------------------------------------------- interpolation core


def _vertical(h_prof, vals, z, ref, p_prof=None, p_target=None):
    """Interpolate one profile to a single target. h_prof ascending (m)."""
    if ref == "pressure_altitude":
        # log-pressure is monotonic: p_prof descending with height
        order = np.argsort(np.log(p_prof))
        return float(np.interp(np.log(p_target), np.log(p_prof)[order], vals[order]))
    return float(np.interp(z, h_prof, vals))


def _profile_at_time(event: str, ts: pd.Timestamp, lat, lon):
    """Return arrays (level_hpa, height_m, u, v, t) at the exact hour ts, spatially interpolated."""
    key = _key(event)
    grid = load_grid(key) if (lat is not None and lon is not None) else None
    if grid is not None:
        g = grid.sel(time=np.datetime64(ts, "ns"))
        pt = g.interp(latitude=float(lat), longitude=float(lon), method="linear")
        lev = pt["level"].values.astype(float)
        h = pt["height"].values.astype(float)
        u = pt["u_component_of_wind"].values.astype(float)
        v = pt["v_component_of_wind"].values.astype(float)
        t = pt["temperature"].values.astype(float)
    else:
        df = load_profiles(key)
        d = df[df["time"] == ts]
        if d.empty:
            raise KeyError(ts)
        lev = d["level_hpa"].values.astype(float)
        h = d["height_m"].values.astype(float)
        u = d["u_ms"].values.astype(float)
        v = d["v_ms"].values.astype(float)
        t = d["t_k"].values.astype(float)
    o = np.argsort(h)
    return lev[o], h[o], u[o], v[o], t[o]


def _available_times(event: str, lat, lon) -> np.ndarray:
    key = _key(event)
    grid = load_grid(key) if (lat is not None and lon is not None) else None
    if grid is not None:
        return pd.DatetimeIndex(grid["time"].values).values
    return np.sort(load_profiles(key)["time"].unique())


def _interp(event, time_utc, height_m, lat, lon, ref):
    from .atmosphere import isa

    ts = _to_ts(time_utc)
    times = pd.DatetimeIndex(_available_times(event, lat, lon))
    if ts < times[0] or ts > times[-1]:
        raise ValueError(f"{ts} outside the stored window {times[0]} to {times[-1]}")
    i1 = int(np.searchsorted(times.values, np.datetime64(ts, "ns"), side="left"))
    if times[i1] == ts:
        i0, w = i1, 0.0
    else:
        i0 = i1 - 1
        if times[i1] - times[i0] > pd.Timedelta(hours=1, minutes=1):
            raise ValueError(f"{ts} falls in a gap of the stored data ({times[i0]} to {times[i1]}); no interpolation across it")
        w = (ts - times[i0]) / (times[i1] - times[i0])
    p_target = None
    if ref == "pressure_altitude":
        p_target = float(isa(np.array(height_m))[1]) / 100.0
    out = []
    for idx in {i0, i1}:
        lev, h, u, v, t = _profile_at_time(event, times[idx], lat, lon)
        res = tuple(_vertical(h, x, height_m, ref, lev, p_target) for x in (u, v, t))
        out.append((idx, res))
    r = dict(out)
    a, b = r[i0], r[i1]
    return tuple((1 - w) * a[k] + w * b[k] for k in range(3))


def wind_at(event: str, time_utc, height_m: float, lat=None, lon=None, ref: str = "height"):
    """(u, v) in m/s at a UTC time and height (m MSL, or ISA pressure altitude if ref='pressure_altitude').

    lat/lon: bilinear in space when the gridded file is present; otherwise (or when omitted)
    the box-centre profile is used. Linear in height (or log-pressure) and in time.
    """
    u, v, _ = _interp(event, time_utc, height_m, lat, lon, ref)
    return u, v


def temperature_at(event: str, time_utc, height_m: float, lat=None, lon=None, ref: str = "height") -> float:
    """Air temperature in K, same interpolation as wind_at."""
    return _interp(event, time_utc, height_m, lat, lon, ref)[2]


def wind_speed_dir_at(event: str, time_utc, height_m: float, lat=None, lon=None, ref: str = "height"):
    """Convenience: (speed_kt, from_deg)."""
    u, v = wind_at(event, time_utc, height_m, lat, lon, ref)
    s, d = uv_to_speed_dir(u, v)
    return float(s) / KT, float(d)


# ---------------------------------------------------------------- summary table


def summary_table(event: str, times, heights_ft=(25000, 13000), lat=None, lon=None, ref: str = "height") -> pd.DataFrame:
    """Wind speed (kt), direction (deg from) and temperature (C) at each time and height at the box centre."""
    la, lo = centre(event)
    lat = la if lat is None else lat
    lon = lo if lon is None else lon
    rows = []
    for t in times:
        row = {"time_utc": _to_ts(t).strftime("%Y-%m-%d %H:%M")}
        for hft in heights_ft:
            u, v, tk = _interp(event, t, hft * FT, lat, lon, ref)
            s, d = uv_to_speed_dir(u, v)
            row[f"speed_kt_{hft}"] = round(float(s) / KT, 1)
            row[f"dir_from_deg_{hft}"] = round(float(d)) % 360
            row[f"temp_c_{hft}"] = round(tk - 273.15, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def available_hours(event: str, dates) -> list[pd.Timestamp]:
    """Stored UTC hours that fall on the given dates (the fetch covers only some hours of some dates)."""
    ts = pd.DatetimeIndex(_available_times(event, None, None))
    keep = [t for t in ts if t.strftime("%Y-%m-%d") in set(dates)]
    return list(keep)


def gimbal_candidate_times(dates=("2015-01-20", "2015-01-21", "2015-01-24", "2015-01-25")) -> list[pd.Timestamp]:
    """Every stored UTC hour of each candidate date."""
    return available_hours("gimbal", dates)
