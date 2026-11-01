"""Tests for solve.weather: interpolation, sign convention, offline operation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from solve import weather as W
from solve.atmosphere import isa


def _write_profiles(dirpath, event="gimbal_gofast"):
    """Synthetic two-hour, three-level profile: u = 0.004*z, v = -0.002*z + hour offset, t = 290 - 0.0065 z."""
    rows = []
    for k, t in enumerate(["2015-01-25T02:00Z", "2015-01-25T03:00Z"]):
        for lev, z in [(1000, 100.0), (500, 5500.0), (250, 10500.0)]:
            rows.append(dict(time=t, level_hpa=lev, height_m=z + 50 * k, u_ms=0.004 * z + 10 * k,
                             v_ms=-0.002 * z, t_k=290 - 0.0065 * z))
    pd.DataFrame(rows).to_csv(dirpath / f"era5_{event}_profiles.csv", index=False)


@pytest.fixture()
def synth(tmp_path, monkeypatch):
    _write_profiles(tmp_path)
    monkeypatch.setattr(W, "DATA_DIR", tmp_path)
    W._profiles_cached.cache_clear()
    W._grid_cached.cache_clear()
    yield tmp_path
    W._profiles_cached.cache_clear()
    W._grid_cached.cache_clear()


def test_reproduces_grid_values_at_grid_points(synth):
    t = "2015-01-25T02:00Z"
    for z, u, v, tk in [(100.0, 0.4, -0.2, 290 - 0.65), (5500.0, 22.0, -11.0, 290 - 35.75), (10500.0, 42.0, -21.0, 290 - 68.25)]:
        uu, vv = W.wind_at("gimbal", t, z)
        assert uu == pytest.approx(u, abs=1e-9)
        assert vv == pytest.approx(v, abs=1e-9)
        assert W.temperature_at("gimbal", t, z) == pytest.approx(tk, abs=1e-9)


def test_linear_between_levels(synth):
    t = "2015-01-25T02:00Z"
    u0, v0 = W.wind_at("gimbal", t, 5500.0)
    u1, v1 = W.wind_at("gimbal", t, 10500.0)
    for frac in (0.25, 0.5, 0.9):
        z = 5500.0 + frac * 5000.0
        u, v = W.wind_at("gimbal", t, z)
        assert u == pytest.approx(u0 + frac * (u1 - u0), abs=1e-9)
        assert v == pytest.approx(v0 + frac * (v1 - v0), abs=1e-9)
        t_mid = W.temperature_at("gimbal", t, z)
        assert t_mid == pytest.approx(W.temperature_at("gimbal", t, 5500.0) * (1 - frac) + W.temperature_at("gimbal", t, 10500.0) * frac)


def test_linear_in_time(synth):
    z = 10500.0
    ua, _ = W.wind_at("gimbal", "2015-01-25T02:00Z", z)
    ub, _ = W.wind_at("gimbal", "2015-01-25T03:00Z", z)
    um, _ = W.wind_at("gimbal", "2015-01-25T02:30Z", z)
    assert um == pytest.approx(0.5 * (ua + ub))
    assert ub > ua  # the synthetic file adds 10 m/s at the later hour
    u25, _ = W.wind_at("gimbal", "2015-01-25T02:15Z", z)
    assert u25 == pytest.approx(0.75 * ua + 0.25 * ub)


def test_gap_in_data_raises(synth):
    df = pd.read_csv(synth / "era5_gimbal_gofast_profiles.csv")
    late = df.copy()
    late["time"] = "2015-01-25T09:00Z"
    pd.concat([df, late]).to_csv(synth / "era5_gimbal_gofast_profiles.csv", index=False)
    W._profiles_cached.cache_clear()
    with pytest.raises(ValueError, match="gap"):
        W.wind_at("gimbal", "2015-01-25T05:00Z", 5000.0)
    assert W.wind_at("gimbal", "2015-01-25T09:00Z", 5500.0)  # stored hour still works


def test_outside_window_raises(synth):
    with pytest.raises(ValueError):
        W.wind_at("gimbal", "2015-01-25T05:00Z", 5000.0)


def test_uv_sign_convention():
    # wind from the west blows toward the east: u > 0, direction-from 270
    s, d = W.uv_to_speed_dir(10.0, 0.0)
    assert s == pytest.approx(10.0) and d == pytest.approx(270.0)
    # from the north: v < 0, 360 (0)
    s, d = W.uv_to_speed_dir(0.0, -10.0)
    assert d == pytest.approx(0.0) or d == pytest.approx(360.0)
    # from the east: u < 0, 90 ; from the south: v > 0, 180
    assert W.uv_to_speed_dir(-5.0, 0.0)[1] == pytest.approx(90.0)
    assert W.uv_to_speed_dir(0.0, 5.0)[1] == pytest.approx(180.0)
    # round trip
    for dd in (0, 45, 123, 274, 265, 359):
        u, v = W.speed_dir_to_uv(30.0, dd)
        s, d2 = W.uv_to_speed_dir(u, v)
        assert s == pytest.approx(30.0) and (d2 - dd + 180) % 360 - 180 == pytest.approx(0.0, abs=1e-9)
    # a westerly stored as u > 0 comes back as 270
    assert W.speed_dir_to_uv(20.0, 270.0)[0] == pytest.approx(20.0)


def test_pressure_altitude_mode_hits_levels(synth):
    t = "2015-01-25T02:00Z"
    # ISA altitude whose pressure is exactly 500 hPa
    p = 50000.0
    h = 5574.4  # about; solve exactly below
    lo, hi = 5000.0, 6000.0
    for _ in range(60):
        h = 0.5 * (lo + hi)
        if float(isa(np.array(h))[1]) > p:
            lo = h
        else:
            hi = h
    u, v = W.wind_at("gimbal", t, h, ref="pressure_altitude")
    assert u == pytest.approx(22.0, abs=1e-6)
    assert v == pytest.approx(-11.0, abs=1e-6)


def test_works_offline_from_saved_csv(synth, monkeypatch):
    """No gridded file and no network: only the CSV is needed."""
    import socket

    def no_net(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "socket", no_net)
    assert W.load_grid("gimbal") is None
    df = W.load_profiles("gimbal")
    assert set(df.columns) == {"time", "level_hpa", "height_m", "u_ms", "v_ms", "t_k"}
    u, v = W.wind_at("gimbal", "2015-01-25T02:00Z", 8000.0, lat=30.0, lon=-76.0)  # lat/lon ignored without a grid
    assert np.isfinite(u) and np.isfinite(v)


def test_bilinear_in_space_with_grid(synth):
    xr = pytest.importorskip("xarray")
    times = pd.to_datetime(["2015-01-25T02:00", "2015-01-25T03:00"])
    lev = np.array([1000.0, 500.0, 250.0])
    lat = np.array([29.0, 30.0, 31.0])
    lon = np.array([-78.0, -77.0, -76.0])
    shape = (2, 3, 3, 3)
    tt, ll, la, lo = np.meshgrid(np.arange(2), lev, lat, lon, indexing="ij")
    u = (la - 30.0) * 2.0 + (lo + 77.0) * 3.0 + 10.0 + ll / 100.0
    v = -(la - 30.0) + 1.0 + 0 * ll
    t = 250.0 + 0 * ll
    h = {1000.0: 100.0, 500.0: 5500.0, 250.0: 10500.0}
    z = np.vectorize(h.get)(ll)
    dims = ("time", "level", "latitude", "longitude")
    ds = xr.Dataset(
        {"u_component_of_wind": (dims, u), "v_component_of_wind": (dims, v), "temperature": (dims, t),
         "height": (dims, z), "geopotential": (dims, z * 9.80665)},
        coords={"time": times, "level": lev, "latitude": lat, "longitude": lon},
    )
    ds.to_netcdf(synth / "era5_gimbal_gofast.nc")
    W._grid_cached.cache_clear()
    t0 = "2015-01-25T02:00Z"
    # exact at a node
    uu, vv = W.wind_at("gimbal", t0, 5500.0, lat=30.0, lon=-77.0)
    assert uu == pytest.approx(10.0 + 5.0, abs=1e-4)
    assert vv == pytest.approx(1.0, abs=1e-4)
    # bilinear between nodes: the test field is linear in lat and lon, so interpolation is exact
    uu, vv = W.wind_at("gimbal", t0, 5500.0, lat=30.4, lon=-76.25)
    assert uu == pytest.approx(0.4 * 2.0 + 0.75 * 3.0 + 10.0 + 5.0, abs=1e-4)
    assert vv == pytest.approx(-0.4 + 1.0, abs=1e-4)


def test_summary_table_columns(synth):
    tab = W.summary_table("gimbal", ["2015-01-25T02:00Z", "2015-01-25T03:00Z"], heights_ft=(25000, 13000))
    assert list(tab.columns[:1]) == ["time_utc"]
    for c in ("speed_kt_25000", "dir_from_deg_25000", "temp_c_25000", "speed_kt_13000", "dir_from_deg_13000"):
        assert c in tab.columns
    # synthetic wind: u>0, v<0 -> from the north-west quadrant (270..360)
    assert (tab["dir_from_deg_25000"] > 270).all() and (tab["dir_from_deg_25000"] < 360).all()


# ----- real data (committed CSVs), skipped if absent


@pytest.fixture()
def real():
    W._profiles_cached.cache_clear()
    W._grid_cached.cache_clear()
    for ev in ("gimbal_gofast", "flir1"):
        if not (W.DATA_DIR / f"era5_{ev}_profiles.csv").exists():
            pytest.skip("saved ERA5 profiles not present")
    yield


def test_real_profiles_reproduced_at_grid_points(real):
    for ev, t in [("gimbal_gofast", "2015-01-25T02:00Z"), ("flir1", "2004-11-14T20:00Z")]:
        df = W.load_profiles(ev)
        d = df[df["time"] == W._to_ts(t)]
        assert len(d) >= 20
        for _, r in d.iloc[::4].iterrows():
            u, v = W.wind_at(ev, t, r["height_m"])
            assert u == pytest.approx(r["u_ms"], abs=1e-6)
            assert v == pytest.approx(r["v_ms"], abs=1e-6)
            assert W.temperature_at(ev, t, r["height_m"]) == pytest.approx(r["t_k"], abs=1e-6)


def test_real_gimbal_jet_is_westerly(real):
    """January 2015 at 25,000 ft off Florida: a strong westerly (u > 0, from about 270)."""
    u, v = W.wind_at("gimbal", "2015-01-25T02:30Z", 25000 * W.FT)
    assert u > 10
    s, d = W.uv_to_speed_dir(u, v)
    assert 240 < d < 300
