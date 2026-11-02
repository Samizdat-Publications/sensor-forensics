# PURSUE: data audit and triage (M0)

Completed 10/31/2026. Index: `data/pursue/index.csv` (134 videos in the official database, Releases 01 to 06). Files: all six official zips downloaded, hashed and extracted (`data/pursue/downloads.json`, 149 files). Mapping of files to clip IDs: `data/pursue/file_map.csv`. Triage: `data/pursue/triage.csv`, rules in `data/pursue/TRIAGE-SCHEMA.md`.

## Mapping

- Every one of the 134 index clips maps to a file. 138 of 150 mapping rows are high confidence; each was matched on the download file name that the clip's DVIDS page lists (DOD_<number>), cross-checked by duration and content.
- 16 files map to no video clip: all are NASA-logo audio waveform videos (32 to 96 minutes in some cases), almost certainly the 16 audio records (type AUD) in the official database.
- PR057a and PR057b share one DVIDS ID and one file.
- Official stated durations are loose for several clips (for example PR108 is 94.8 s on disk against 136 s stated; PR043 loops a 2 s clip to 11.7 s).

## Tiers

| Tier | Count | Meaning |
|---|---|---|
| Full | 0 | Enough on-screen symbology for a per-frame line of sight |
| Bounded | 16 | No full line of sight, but an angular scale or a reference of known size, so range-size-speed curves can be drawn |
| Not viable | 118 | Neither |

Counts revised 11/02/2026 at the CP-06 check (D-019): PR107 moved from Bounded to Not viable, because an elevation readout alone gives no scale. At CP-01 they were 17 and 117.

Why nothing is Full: in almost every military clip the numeric display fields are blacked out, leaving a crosshair, corner ticks and sometimes a north arrow. This matches Haqq-Misra and Kopparapu's observation, now checked clip by clip.

Bounded clips, grouped by what gives the scale:

| Scale source | Clips | Confidence | What must be confirmed in M5 |
|---|---|---|---|
| Tracker gate labeled in metres ("23M", "36M" to "2M", "92M") | PR044, PR052, PR059, PR078, PR089 (PR034 likely hides the same label) | Medium to low | That the label is the gate width (a size scale) and not a range |
| Tick-marked reticle | PR030, PR120, PR121, PR122 | Medium | The angular spacing of the ticks |
| Marked-angle ladder | PR113 | Medium | What the ladder measures: it rolls with the picture and reverses direction, so it may be a pitch ladder, not the depression scale assumed by Haqq-Misra and Kopparapu |
| Partial pod angles on screen | PR111 (elevation and an "NNM" label); PR107 (elevation only) was re-tiered to Not viable (D-019) | Low | Whether PR111's label is a range (M5: it behaves like slant range, but with no azimuth the clip stays Bounded) |
| Known-size scene objects | PR037 (small boat), PR048 and PR058 (offshore wind turbines), PR134 (town, roads, buildings), PR149 (cargo ship) | Medium to low | Object class and size |

Not viable includes, by definition, FBI-UAP-PR005 and PR006 (officially described as artistic digital recreations), handheld phone clips with no scale (FBI-UAP-PR001 to PR004), and DOW-UAP-PR159 (a 1952 16 mm film; out of scope for sensor reconstruction).

## Verdict

**No PURSUE clip can be reconstructed like GIMBAL or GOFAST.** Redaction removes the pod angles, altitude and range from essentially all of them. Sixteen clips (12 percent) carry enough of a scale for bounded analysis: curves of object size and speed against assumed range, with the reference object or reticle fixing one point. D-013 froze M5 to the 8 strongest of them (the five tracker-gate clips, PR111, PR113 and PR149); results in `docs/results/pursue.md`.
