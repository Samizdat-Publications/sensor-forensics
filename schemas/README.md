# UFO Case File format, version 0.1

The schema is `C:\Users\stewa\Documents\Claude\Sensor forensics\schemas\ufo-case-file.schema.json` (JSON Schema 2020-12). It was defined here by the Sensor Forensics Lab (decision D-014) so that a separate UFO Case Files project can adopt it. Extra fields are allowed everywhere, so other projects can add their own without breaking validation.

One file describes one case: a recording, one frozen clip, or a summary of many clips. Numbers are SI (meters, seconds, meters per second) unless the field name says otherwise (for example `range_display_nmi`, or `deg`). Where the lab keeps a number in the unit a person sees on screen (knots, nautical miles, feet), the key name ends in that unit, and SI copies sit beside it (`derived_si`, `range_m`).

## Fields in plain words

Required: `schema_version`, `case_id`, `kind`, `title`, `event`, `sources`, `verdict`, `provenance`. Everything else is optional, so a thin case can still validate.

- **schema_version**: always `"0.1"` for now.
- **case_id**: short lowercase name, for example `gimbal`. Used as the file name.
- **kind**: `video_case` (a scored recording), `clip_case` (one frozen clip), or `triage_summary` (a roll-up of many clips).
- **title**, **summary**: a name, and two or three plain sentences.
- **event**: `date` (ISO date or month, or null), `date_uncertainty` in words, `place`, optional `latitude_deg` and `longitude_deg` with `position_uncertainty_m`, and `position_note` saying why a position is missing.
- **platform**: the aircraft or ship that recorded it, with an optional altitude as a number plus unit plus uncertainty.
- **sensor**: the instrument. Field of view in degrees (full angle), picture width in pixels, frame rate, duration. Field of view can change per frame, which `field_of_view_note` explains.
- **sources**: every input, with a link, a SHA-256 hash of the exact file, size, whether it is an official copy, and where this copy came from. The hash lets anyone confirm they hold the same bytes.
- **observables**: what is on screen, one entry per field (azimuth, range, and so on). Each says whether it was read from the screen or measured from the image, how often it updates, its first and last values, and what fraction of frames the reader was unsure of.
- **environment**: where the weather came from and how uncertain the wind is.
- **analysis**: how scoring was done: the frames used, the effective sample size, any variants (for example two field-of-view assumptions), warnings, and the list of data-quality rules applied after seeing results (`post_hoc_exclusions`, each marked as decided blind or not).
- **hypotheses**: one entry per candidate explanation and variant. It holds the model, a summary of its priors, best-fit parameters, per-criterion log-likelihoods, and two totals: `total_testimony_weighted` and `total_physics_only` (the video alone). When available, the same two totals without the post-hoc exclusions are in `*_without_post_hoc_exclusions`. Higher totals are better; a gap of 2.3 is a likelihood ratio of 10.
- **range_curves**: what the data allow if the unknown range were each of a series of values. Read it as a curve, not one answer: it shows what speed and altitude each assumed range would imply.
- **discriminators**: for pairs the data cannot separate, the single extra measurement that could, the precision needed (`required_precision`), the precision real instruments typically reach, the ratio of the two (`feasibility`, 1 or more means achievable), and whether such data exists.
- **testimony**: how many claims were collected, how many the scorer could use, the witnesses, and how well memory of on-screen numbers matches the record (`witness_consistency`). It never changes a hypothesis score on its own.
- **triage**: only for `triage_summary`: counts by tier and release, and one line per clip.
- **verdict**: the result in plain words (`text`), what must hold for it to stand (`conditions`), whether the data are decisive (`decisive`, true only when the leader beats every other by a likelihood ratio of 10 or more), and the leader and margin.
- **provenance**: the repository, the exact commit, the lab version, and when the file was generated. This is how you can reproduce the file.
- **notes**: free text.

## Commands (Windows PowerShell 5.1)

Build the case files:

```powershell
cd "C:\Users\stewa\Documents\Claude\Sensor forensics"; .\.venv\Scripts\python.exe "C:\Users\stewa\Documents\Claude\Sensor forensics\tools\export_cases.py"
```

Check them against the schema:

```powershell
cd "C:\Users\stewa\Documents\Claude\Sensor forensics"; .\.venv\Scripts\python.exe "C:\Users\stewa\Documents\Claude\Sensor forensics\tools\validate_cases.py"
```

Output goes to `C:\Users\stewa\Documents\Claude\Sensor forensics\exports\cases\`.
