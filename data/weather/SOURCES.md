# Weather data sources and hashes

Accessed 2026-10-31. No account, no credentials, default headers.

## ERA5 (Copernicus reanalysis, hosted by Google ARCO-ERA5)

- Hourly files: `gs://gcp-public-data-arco-era5/ar/1959-2022-1h-360x181_equiangular_with_poles_conservative.zarr` (1 degree conservative regrid of ERA5, 37 levels; opened with xarray + gcsfs, token="anon", zarr_format=2). Subset by time, level (150 to 1000 hPa), latitude and longitude before loading. Variables: u_component_of_wind, v_component_of_wind, temperature, geopotential; height_m = geopotential / 9.80665.
- Why not the 0.25 degree store `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3` (its metadata is zarr v2 despite the name; open with zarr_format=2): one chunk is one global hour, 37 levels, about 118 MB per variable, and the connection here sustained 0.5 to 1.5 MB/s.
- Hours stored: GIMBAL/GOFAST 2015-01-20T00Z to 2015-01-21T23Z, 2015-01-24T16Z to 2015-01-25T23Z, 2015-01-26T00Z to 06Z (87 hours; 01/22, 01/23 and early 01/24 not fetched). FLIR1 2004-11-14T12Z to 2004-11-15T06Z (19 hours).
- Licence: Copernicus Climate Change Service; contains modified Copernicus Climate Change Service information (CC-BY 4.0 terms).
- Fetch code: `tools/fetch_weather.py`.

## NOAA IGRA v2 radiosondes

- Base URL: https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/ , files `USM00072206-data.txt.zip` (Jacksonville), `USM00072402-data.txt.zip` (Wallops Island), `USM00072293-data.txt.zip` (San Diego). Each is the full period of record; downloaded once, only the event windows were extracted (00Z and 12Z soundings, 2015-01-20 to 2015-01-26 and 2004-11-14 to 2004-11-15). The zips are not stored in the repo.
- Zip SHA-256 (as downloaded 2026-10-31):
  - USM00072206-data.txt.zip (85,993,365 bytes) 770ea95cda5ff643e5c390c3b4d2ca7b4bad12f7e5118f2695d3baa26241a1c2
  - USM00072402-data.txt.zip (80,413,862 bytes) 9a172d898b2e242ce8b7222f377f518c8ea8925fb35c1cd2cff97b0819b6bf8a
  - USM00072293-data.txt.zip (93,067,491 bytes) aff0348b2a59b1f2beba19d4344e4dc27044ec4f9cf9fd3ccf9938512e897088
- Parsed fixed-width columns (IGRA v2 data format): pressure idx 9-14 (Pa), height 16-20 (m), temperature 22-26 (tenths C), wind direction 40-44 (deg), wind speed 46-50 (tenths m/s). Missing -9999 and -8888 become blank.

## Saved files (SHA-256)

- `data/weather/era5_flir1.nc` (343936 bytes) f65e1ff448e7f526a586802dcac10fe696c43c99d9fb5694a43c65604eb7ea3e
- `data/weather/era5_gimbal_gofast.nc` (4787288 bytes) 9b4ce8755df7c51bd7a91b93797972412f82b4d8a7147f8d5f9457c37a20ba8a
- `data/weather/era5_flir1_profiles.csv` (24818 bytes) 18bf9a7404d61947e27e0e0e71a2b9bbe7cfa4db59c25cce2798a2d592f70015
- `data/weather/era5_gimbal_gofast_profiles.csv` (110802 bytes) 9cb4d34ad9271dd7fadcd833d3c68c9d5438e61b332f76c2a0550c5642d6f7da
- `data/weather/igra_USM00072206_gimbal_gofast.csv` (69931 bytes) 2cf0d684977b39cee53961eb2c9130c0bbdc145dd910680e8e54372399347a30
- `data/weather/igra_USM00072293_flir1.csv` (13537 bytes) 6d539bd9b9758cdac0cba0af08936adb0462edce34dc36fe6d93ea2249c4e3ca
- `data/weather/igra_USM00072402_gimbal_gofast.csv` (113766 bytes) 2bd9d3a86ec5ac445260278b2b7422b9913083a2204594c942cc3bf4ac7f011b
- `data/weather/igra_vs_era5.csv` (20103 bytes) 5a4b7725f0e8d514427e11cc9022c939f0383f0db125dfeb4a517210dfa14142
- `data/weather/summary_gimbal_gofast.csv` (6297 bytes) 1e3c6f60671d8f522814a8c21a14ce07f2fdcac8a83f6eb165e43b04f806c851
- `data/weather/igra_vs_era5.csv` (20103 bytes) 5a4b7725f0e8d514427e11cc9022c939f0383f0db125dfeb4a517210dfa14142

All files are under 20 MB and are committed as is; `.gitignore` excludes partial downloads (`data/weather/_part_*.nc`, `data/weather/_cache/`) and any `*_0p25_full*.nc` file.
