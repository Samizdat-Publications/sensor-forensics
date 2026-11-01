"""Fetch ERA5 (ARCO anonymous Zarr) subsets and IGRA v2 soundings for the three Navy events.

Writes data/weather/era5_<event>.nc, era5_<event>_profiles.csv and
igra_<station>_<event>.csv. Run from the repo root: .venv/Scripts/python tools/fetch_weather.py
Network only; no account. Sources and hashes are recorded by hand in data/weather/SOURCES.md.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "weather"
STORE = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
VARS = ["u_component_of_wind", "v_component_of_wind", "temperature", "geopotential"]
LEVELS = [150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000]

# lat range, lon range (degrees east, negative west), time range, centre
EVENTS = {
    # Requested box 28 to 33 N, 79 to 74 W. The stored grid is extended west and north (28 to 38 N, 83 to 74 W)
    # at no extra download cost (chunks are global) so it also covers the radiosonde stations
    # Jacksonville (30.5 N, 81.7 W) and Wallops Island (37.9 N, 75.5 W) for the radiosonde vs ERA5 check.
    "gimbal_gofast": dict(lat=(28, 38), lon=(-83, -74), t=("2015-01-20T00", "2015-01-26T06"), centre=(30.5, -76.5),
                          box=((28, 33), (-79, -74))),
    "flir1": dict(lat=(29, 34), lon=(-120, -115), t=("2004-11-14T12", "2004-11-15T06"), centre=(31.205, -117.870)),
}

# IGRA: station -> (event, start, end)
IGRA = {
    "USM00072206": ("gimbal_gofast", "2015-01-20T00", "2015-01-26T12"),
    "USM00072402": ("gimbal_gofast", "2015-01-20T00", "2015-01-26T12"),
    "USM00072293": ("flir1", "2004-11-14T00", "2004-11-15T12"),
}


STORE_1DEG = "gs://gcp-public-data-arco-era5/ar/1959-2022-1h-360x181_equiangular_with_poles_conservative.zarr"
# one full-resolution (0.25 deg) chunk is a whole global field at 37 levels, about 118 MB compressed,
# so the 0.25 deg store is fetched only for the key hours below; the hourly window uses the 1 deg store.
KEY_HOURS = {
    "gimbal_gofast": ["2015-01-25T02", "2015-01-25T03"],
    "flir1": ["2004-11-14T20", "2004-11-14T21"],
}


def _open(store: str) -> xr.Dataset:
    ds = xr.open_zarr(store, chunks=None, storage_options={"token": "anon"}, consolidated=True, zarr_format=2)
    ds.attrs["_id"] = "1deg" if "360x181" in store else "0p25"
    return ds


def _tag(sub: xr.Dataset, event: str, store: str) -> xr.Dataset:
    sub = sub.assign_coords(longitude=((sub.longitude + 180) % 360) - 180).sortby("longitude").sortby("latitude")
    sub["height"] = sub["geopotential"] / 9.80665
    sub["height"].attrs = dict(units="m", long_name="geopotential height (geopotential / 9.80665)")
    sub.attrs.update(source=store, event=event)
    return sub


def _load_blocks(ds: xr.Dataset, cfg: dict, times, block: int) -> xr.Dataset:
    """Load VARS for the box, one (variable, time-block) task per thread, so each stored chunk is read once."""
    from concurrent.futures import ThreadPoolExecutor

    lat0, lat1 = cfg["lat"]
    lon0, lon1 = cfg["lon"]
    ti = np.searchsorted(ds.time.values, np.array(times, dtype="datetime64[ns]"))
    tasks = []
    for v in VARS:
        if block == 1:
            groups = [[int(i)] for i in ti]
        else:
            groups = {}
            for i in ti:
                groups.setdefault(int(i) // block, []).append(int(i))
            groups = list(groups.values())
        for g in groups:
            tasks.append((v, g))

    cache = OUT / "_cache"
    cache.mkdir(parents=True, exist_ok=True)

    def run(task):
        v, g = task
        cf = cache / f"{ds.attrs.get('_id', 'x')}_{v}_{g[0]}_{g[-1]}_{lat0}_{lat1}_{lon0}_{lon1}.nc"
        if cf.exists():
            return v, xr.load_dataarray(cf)
        pad = 0.01  # the stored float32 coordinates are not exact integers
        asc = bool(ds.latitude[0] < ds.latitude[-1])
        da = ds[v].isel(time=g).sel(
            level=slice(LEVELS[0], LEVELS[-1]),
            latitude=slice(lat0 - pad, lat1 + pad) if asc else slice(lat1 + pad, lat0 - pad),
            longitude=slice(lon0 % 360 - pad, lon1 % 360 + pad))
        da = da.assign_coords(latitude=np.round(da.latitude.values.astype("float64"), 3),
                              longitude=np.round(da.longitude.values.astype("float64"), 3))
        da = da.sel(level=[l for l in LEVELS if l in da.level.values]).load()
        da.to_netcdf(cf)
        return v, da

    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(run, tasks))
    out = {}
    for v in VARS:
        out[v] = xr.concat([d for vv, d in res if vv == v], dim="time").sortby("time")
    return xr.Dataset(out)


def _profiles(sub: xr.Dataset, centre, path: Path) -> None:
    clat, clon = centre
    pr = sub.interp(latitude=clat, longitude=clon, method="linear")
    df = pr.to_dataframe().reset_index()
    df = df.rename(columns={"level": "level_hpa", "height": "height_m", "u_component_of_wind": "u_ms",
                            "v_component_of_wind": "v_ms", "temperature": "t_k"})
    df["time"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%dT%H:%MZ")
    df = df[["time", "level_hpa", "height_m", "u_ms", "v_ms", "t_k"]].round(
        {"height_m": 1, "u_ms": 3, "v_ms": 3, "t_k": 3})
    df.to_csv(path, index=False)
    print("wrote", path.name, len(df), flush=True)


def era5(event: str, t0: str | None = None, t1: str | None = None, part: str | None = None) -> None:
    """Hourly window at 1 deg from the ARCO 1 deg store -> era5_<event>.nc and the centre profiles CSV.

    With t0/t1/part given, writes only that slice to a part file (split to run several processes at once;
    stored chunks hold 8 hours, so split on 00 UTC days); merge_parts() joins them.
    """
    cfg = dict(EVENTS[event])
    if t0:
        cfg["t"] = (t0, t1)
    ds = _open(STORE_1DEG)
    times = pd.date_range(cfg["t"][0], cfg["t"][1], freq="1h").values
    sub = _load_blocks(ds, cfg, times, block=8)
    sub = sub.sel(time=slice(cfg["t"][0], cfg["t"][1]))
    sub = _tag(sub, event, STORE_1DEG)
    print(event, dict(sub.sizes), flush=True)
    if part:
        sub.to_netcdf(OUT / f"_part_{event}_{part}.nc")
        return
    sub.to_netcdf(OUT / f"era5_{event}.nc")
    _profiles(sub, cfg["centre"], OUT / f"era5_{event}_profiles.csv")


def merge_parts(event: str) -> None:
    parts = sorted(OUT.glob(f"_part_{event}_*.nc"))
    sub = xr.concat([xr.load_dataset(p) for p in parts], dim="time").sortby("time")
    sub.attrs.update(source=STORE_1DEG, event=event)
    sub.to_netcdf(OUT / f"era5_{event}.nc")
    _profiles(sub, EVENTS[event]["centre"], OUT / f"era5_{event}_profiles.csv")
    print("merged", event, dict(sub.sizes), flush=True)


def era5_025(event: str) -> None:
    """Full-resolution (0.25 deg) store, key hours only -> era5_<event>_0p25_keyhours.nc (+ centre profiles)."""
    cfg = EVENTS[event]
    ds = _open(STORE)
    sub = _load_blocks(ds, cfg, pd.to_datetime(KEY_HOURS[event]).values, block=1)
    sub = _tag(sub, event, STORE)
    print(event, "0.25", dict(sub.sizes), flush=True)
    sub.to_netcdf(OUT / f"era5_{event}_0p25_keyhours.nc")
    _profiles(sub, cfg["centre"], OUT / f"era5_{event}_0p25_keyhours_profiles.csv")


def parse_igra(fileobj, start: str, end: str) -> pd.DataFrame:
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    rows = []
    keep = False
    cur = None
    for raw in io.TextIOWrapper(fileobj, encoding="ascii"):
        if raw.startswith("#"):
            y, mo, d, h = int(raw[13:17]), int(raw[18:20]), int(raw[21:23]), int(raw[24:26])
            if h == 99:  # missing nominal hour: fall back to release time
                h = int(raw[27:29]) if raw[27:29].strip() and int(raw[27:29]) < 99 else 0
            if y < t0.year - 0 or y > t1.year:
                keep = False
                continue
            cur = pd.Timestamp(year=y, month=mo, day=d, hour=h)
            keep = t0 <= cur <= t1
            continue
        if not keep:
            continue
        # fixed width data record
        p = int(raw[9:15])
        z = int(raw[16:21])
        t = int(raw[22:27])
        dd = int(raw[40:45])
        ff = int(raw[46:51])
        if p == -9999:
            continue
        rows.append(dict(
            time=cur.strftime("%Y-%m-%dT%H:%MZ"),
            pressure_hpa=p / 100.0,
            height_m=np.nan if z in (-9999, -8888) else float(z),
            temp_c=np.nan if t in (-9999, -8888) else t / 10.0,
            wind_dir_deg=np.nan if dd in (-9999, -8888) else float(dd),
            wind_speed_ms=np.nan if ff in (-9999, -8888) else ff / 10.0,
        ))
    return pd.DataFrame(rows)


def igra(station: str, zpath: Path) -> None:
    event, start, end = IGRA[station]
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            df = parse_igra(f, start, end)
    df.to_csv(OUT / f"igra_{station}_{event}.csv", index=False)
    print("igra", station, len(df), df["time"].nunique(), "soundings", flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    what = sys.argv[1]
    if what == "era5":
        for ev in (sys.argv[2:] or EVENTS):
            era5(ev)
    elif what == "era5_part":
        era5(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif what == "merge":
        merge_parts(sys.argv[2])
    elif what == "era5_025":
        for ev in (sys.argv[2:] or EVENTS):
            era5_025(ev)
    elif what == "igra":
        for st, zp in zip(sys.argv[2::2], sys.argv[3::2]):
            igra(st, Path(zp))
