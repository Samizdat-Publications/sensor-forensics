# PURSUE triage schema

`triage.csv` holds one row per official clip ID (never duplicated, sorted by `clip_id`). `file_map.csv` maps downloaded files to clip IDs. Both are written per release batch; later batches append rows and re-sort.

## file_map.csv columns

clip_id, release, file (path under data/pursue/raw), file_sha256, ffprobe_duration_s, stated_duration_s (from index.csv, blank if none), method (duration | dvids | visual | combination), confidence (high | medium | low), notes.

The DVIDS page (https://www.dvidshub.net/video/<dvids_id>) lists the download file name (DOD_<number>); a match on it is the strongest evidence. Official durations on DVIDS and in the index can differ from the file by a few seconds (R05: PR136 and PR142), so duration alone is only a first pass.

## triage.csv columns

| Column | Meaning |
|---|---|
| clip_id | Official ID from index.csv |
| release | R01 to R06 |
| file | Path under data/pursue/raw |
| sensor_guess | IR, TV/EO, IR+TV, handheld thermal, film, other |
| platform_guess | Aircraft or device if stated by DVIDS or evident; say "unspecified" otherwise |
| resolution | WxH from ffprobe |
| duration_s | ffprobe duration |
| symbology_visible | Semicolon list of what is readable on screen. Tokens: az, el, range, altitude, airspeed, heading, fov_or_zoom, time, lat_lon, reticle_scale (tick-marked reticle), horizon_bars, north_arrow, reticle_brackets, crosshair_only, none |
| symbology_redacted | none, partial or full: whether on-screen data are blocked or blurred (black boxes over text fields count as full if every numeric field is covered) |
| scene_references | Semicolon list: horizon, sea surface, coastline, terrain, clouds, ship, aircraft, known-size object, none |
| n_objects | Count of objects of interest as best seen (0 if none discernible) |
| tier | Full, Bounded, Not viable, Pending |
| reason | One or two plain sentences |
| notes | Caveats, what would change the tier, official remarks |

## Tier rules

- **Full**: enough on-screen symbology for a per-frame line of sight. At minimum pod or turret azimuth and elevation plus own altitude, or a range.
- **Bounded**: no full line of sight, but a field-of-view scale (a reticle with marked angles, or a known FOV) or a scene reference of known size or distance, so range-size-speed curves can be drawn.
- **Not viable**: neither.
- **Pending**: only if the file is unreadable.

When unsure between two tiers, pick the lower one and say why in notes. A reticle with ticks but no stated angular spacing counts as a scale only if the object and ticks are both clearly visible, and the note must say the spacing needs calibration.
