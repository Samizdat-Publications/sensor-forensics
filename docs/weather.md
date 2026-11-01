# Upper-air weather for the Navy events (M2.2)

Code: `solve/weather.py` (interpolation), `tools/fetch_weather.py` (download), `tools/weather_summary.py` (numbers below). Data and provenance: `data/weather/` and `data/weather/SOURCES.md`. Tests: `tests/test_weather.py`.

## What was fetched, and what was not

- ERA5 came from Google's ARCO anonymous Zarr. The 0.25 degree store (`full_37-1h-0p25deg-chunk-1.zarr-v3`) keeps one hour of the whole globe, all 37 levels, in one chunk of about 118 MB per variable. Four variables for one hour is about 470 MB, and the link here ran at 0.5 to 1.5 MB/s, so that store was not used. The hourly fields come from the same ARCO bucket's 1 degree regridded store (`1959-2022-1h-360x181_equiangular_with_poles_conservative.zarr`, 8 hours per chunk, about 65 MB). Spatial resolution is therefore 1 degree, not 0.25 degree. The jet and temperature fields are smooth at that scale, but the box spread quoted below is coarse (6 by 6 nodes).
- GIMBAL/GOFAST hours stored: 01/20 00Z to 01/21 23Z, 01/24 16Z to 01/25 23Z, and 01/26 00Z to 06Z (87 hours). Not fetched: 01/22, 01/23, and 01/24 before 16Z. The module raises an error for a time inside a gap instead of interpolating across it. The stored grid is 28 to 38 N, 83 to 74 W, a superset of the requested 28 to 33 N, 79 to 74 W box, so that the Jacksonville and Wallops radiosonde sites are inside it; "box" below means the requested part. All 25 levels from 1000 to 150 hPa were kept (no extra download cost).
- FLIR1: 11/14/2004 12Z to 11/15 06Z (19 hours), box 29 to 34 N, 120 to 115 W, as requested.
- Radiosondes: IGRA v2 soundings at 00Z and 12Z for Jacksonville (72206), Wallops Island (72402) and San Diego (72293).

Conventions: u is eastward, v northward; "deg from" is the meteorological direction (a westerly is 270, a northerly is 0). Altitudes are 25,000 ft and 13,000 ft of ISA pressure altitude (what the altimeter reads), converted to pressure and interpolated in log-pressure. Using geometric height instead changes the speeds by 1 to 3 kt and the 25,000 ft temperature by +1.3 C (`data/weather/summary_gimbal_gofast.csv` carries both). Values are at the box centre, 30.5 N 76.5 W.

## (a) GIMBAL/GOFAST candidate dates: wind and temperature at the box centre

Every third hour plus the event hours; the full hourly table is `data/weather/summary_gimbal_gofast.csv`.

| UTC | 25,000 ft kt | 25,000 ft deg from | 25,000 ft C | 13,000 ft kt | 13,000 ft deg from | 13,000 ft C |
|---|---|---|---|---|---|---|
| 2015-01-20 00:00 | 66 | 278 | -31.5 | 39 | 290 | -4.3 |
| 2015-01-20 03:00 | 59 | 275 | -31.7 | 35 | 286 | -4.6 |
| 2015-01-20 06:00 | 54 | 267 | -31.5 | 34 | 277 | -4.6 |
| 2015-01-20 09:00 | 51 | 262 | -31.1 | 34 | 274 | -4.7 |
| 2015-01-20 12:00 | 48 | 265 | -30.6 | 31 | 273 | -5.0 |
| 2015-01-20 15:00 | 42 | 253 | -30.6 | 27 | 263 | -5.5 |
| 2015-01-20 18:00 | 48 | 242 | -30.0 | 28 | 250 | -6.0 |
| 2015-01-20 21:00 | 48 | 250 | -30.7 | 24 | 249 | -6.8 |
| 2015-01-21 00:00 | 42 | 259 | -32.5 | 24 | 243 | -7.3 |
| 2015-01-21 03:00 | 51 | 266 | -32.8 | 26 | 239 | -8.0 |
| 2015-01-21 06:00 | 60 | 267 | -32.8 | 24 | 232 | -7.9 |
| 2015-01-21 09:00 | 67 | 270 | -33.4 | 24 | 239 | -7.3 |
| 2015-01-21 12:00 | 59 | 277 | -33.1 | 32 | 259 | -6.2 |
| 2015-01-21 15:00 | 74 | 297 | -32.3 | 32 | 278 | -5.6 |
| 2015-01-21 18:00 | 72 | 293 | -30.9 | 29 | 281 | -4.6 |
| 2015-01-21 21:00 | 70 | 288 | -29.8 | 27 | 286 | -4.0 |
| 2015-01-24 16:00 | 83 | 247 | -25.1 | 66 | 233 | -0.4 |
| 2015-01-24 18:00 | 87 | 248 | -24.8 | 71 | 232 | -1.1 |
| 2015-01-24 20:00 | 91 | 251 | -25.1 | 78 | 234 | -1.1 |
| 2015-01-24 22:00 | 95 | 253 | -25.6 | 73 | 243 | -0.5 |
| 2015-01-24 23:00 | 96 | 255 | -25.7 | 69 | 246 | -1.2 |
| 2015-01-25 00:00 | 99 | 258 | -25.6 | 64 | 251 | -1.9 |
| 2015-01-25 01:00 | 101 | 260 | -25.6 | 60 | 257 | -2.5 |
| 2015-01-25 02:00 | 100 | 261 | -25.6 | 57 | 262 | -2.8 |
| 2015-01-25 03:00 | 98 | 262 | -25.9 | 53 | 264 | -2.9 |
| 2015-01-25 06:00 | 93 | 263 | -26.5 | 48 | 265 | -2.6 |
| 2015-01-25 09:00 | 89 | 265 | -26.4 | 50 | 273 | -2.4 |
| 2015-01-25 12:00 | 82 | 262 | -26.7 | 43 | 272 | -2.2 |
| 2015-01-25 15:00 | 79 | 256 | -26.9 | 39 | 263 | -2.4 |
| 2015-01-25 18:00 | 85 | 255 | -26.6 | 41 | 258 | -2.5 |
| 2015-01-25 21:00 | 82 | 256 | -26.3 | 42 | 252 | -2.3 |

## (b) Which date and hour match "120 knots" at 25,000 ft, and from which side?

No stored hour reaches 120 kt at the box centre. The strongest centre value is 101 kt from 260 deg at 01:00Z on 01/25 (99 kt from 261 deg at 02:30Z, the 9:30 pm EST candidate). On 01/20 and 01/21 the centre never exceeds 76 kt, and on 01/24 it peaks at 96 kt (23Z). Over the requested box at 02:30Z on 01/25 the 25,000 ft wind runs from 66 to 117 kt (117 kt at the 32 N, 75 W node, from 255 deg) and from 247 to 270 deg, so 120 kt sits at the top of what the box holds. The nearest observation: the Jacksonville radiosonde at 00Z on 01/25 measured 111 kt from 267 deg at 25,000 ft pressure altitude, and ERA5 at Jacksonville at that hour gives 103 kt from 270 deg. Best match: the evening of 01/24 EST (late 01/24 UTC to early 01/25 UTC), at 100 to 117 kt, not exactly 120. 01/20 and 01/21 fit much worse (40 to 76 kt).

Direction: westerly in every stored hour, from 242 to 301 deg; the eastward component u at the centre is at least +38 m/s at 25,000 ft from 01/24 16Z to 01/25 23Z, so never easterly. "The wind's 120 knots to the west" read literally as blowing toward the west (an easterly) is not physical on any candidate date. Read as 120 knots from the west it is a westerly, as Peings and von Rennenkampff and Sitrec use.

## (c) Wind near 13,000 ft (GOFAST object altitude)

At 02:30Z on 01/25 at the centre: 55 kt from 263 deg (pressure altitude; 54 kt from 263 deg at geometric height). Over the box: 40 to 69 kt, from 239 to 282 deg. Sitrec's 65 kt from 274 deg is 10 kt and 11 deg from the centre value and inside the box range; AARO's 60 kt from 265 deg is 5 kt and 2 deg from it. On the evening of 01/24 the 13,000 ft wind is stronger and more southwesterly (69 to 78 kt from 232 to 246 deg between 18Z and 23Z), and on 01/20 and 01/21 it is 23 to 39 kt. Sondes at 13,000 ft, 00Z 01/25: Jacksonville 41 kt from 287 deg, Wallops 37 kt from 282 deg. The shear near 13,000 ft is large and varies in space, so 1 degree ERA5 is a coarse guide here.

## (d) Temperature at 25,000 ft

ERA5 at the centre, 02:30Z on 01/25: -25.7 C at 25,000 ft pressure altitude (-24.4 C at 25,000 ft geometric height). That is 8.8 C warmer than ISA (-34.5 C) and 0.7 C from the -25 C assumed by Peings and von Rennenkampff. Across 01/24 16Z to 01/25 23Z the centre value is -24.8 to -26.9 C (pressure altitude); the Jacksonville sonde at 00Z on 01/25 gave -25.7 C. On 01/20 and 01/21 it is colder, -30 to -33 C. The -25 C figure is supported for the 01/24 to 01/25 candidate; ISA is not.

## (e) FLIR1, 11/14/2004 at 31.205 N, 117.870 W

At 20,000 ft pressure altitude: 67 kt from 8 deg at 20:00Z, 66 kt from 9 deg at 20:30Z, 65 kt from 10 deg at 21:00Z (geometric height: 64 kt from 9 to 11 deg). The wind is northerly, as in Sitrec. Sitrec's 70 kt (local) from north is 3 to 5 kt above ERA5 at 20,000 ft, a close match. Sitrec's 100 kt (target) from north is reached higher up: ERA5 gives 101 kt from 3 deg at 25,000 ft and 108 kt at 27,500 ft, so 100 kt corresponds to a target near 25,000 ft, not 20,000 ft. That is a testable altitude constraint for the FLIR1 solution. San Diego soundings: 12Z 11/14 gave 50 kt from 17 deg at 20,000 ft and 84 kt from 5 deg at 25,000 ft; 00Z 11/15 gave 53 kt from 25 deg at 20,000 ft and 102 kt from 14 deg at 25,000 ft (the event lies between them). Temperature at 20,000 ft pressure altitude: -19.7 C.

## (f) Radiosonde versus ERA5

For the hours stored (7 soundings each for Jacksonville and Wallops, 2 for San Diego), sonde versus ERA5 interpolated to the site at 850, 700, 500, 400, 300, 250, 200 and 150 hPa:

| Site | levels compared | vector wind difference RMS | mean | temperature, sonde minus ERA5 (mean, sd) |
|---|---|---|---|---|
| Jacksonville | 56 | 2.7 m/s (5.3 kt) | 2.2 m/s | +0.4 K, 0.6 |
| Wallops Island | 56 | 3.4 m/s (6.5 kt) | 2.9 m/s | +0.0 K, 0.9 |
| San Diego | 16 | 3.1 m/s (6.1 kt) | 2.9 m/s | +0.4 K, 0.8 |

Jet level (250 hPa), mean speeds: Jacksonville sonde 100 kt versus ERA5 100 kt; Wallops 90 versus 87 kt; San Diego 123 versus 115 kt (ERA5 about 8 kt low at the jet core in the two soundings available). At 500 hPa ERA5 is within 1 to 3 kt. A balloon drifts downwind and ERA5 averages over 1 degree, so differences of a few m/s are expected. Rows: `data/weather/igra_vs_era5.csv`.

## Limits

- 1 degree resolution, hourly; the 0.25 degree store was not used (cost above). The 01/22, 01/23 and early 01/24 hours are missing, so those UTC dates are not covered.
- ERA5 jet-core speeds can run several knots low (see (f)). The solver should carry the 25,000 ft wind as roughly 100 to 117 kt with a few kt of uncertainty, not as a single number.
