# PURSUE video index: how it was built

Retrieved 10/30/2026.

## Source

The official PURSUE page (https://www.war.gov/UFO/?type=.vid) renders its database from a single CSV that the page itself loads: `https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv?release=7v3` (478 records: 134 VID, 298 PDF, 30 IMG, 16 AUD).

war.gov returns HTTP 403 to every scripted request (curl, requests, WebFetch), so no workaround was attempted. The CSV was read inside an ordinary browser session on the official page, filtered to `Type = VID`, and transcribed to `index.csv` with these columns:

clip_id, release, release_date, agency, incident_date, incident_location, dvids_id, redaction_flag, pdf_pairing, title

- `release` is derived from the official release date: 05/08 = R01, 05/22 = R02, 06/12 = R03, 07/10 = R04, 08/07 = R05, 09/18 = R06. Release 07 (10/23/2026) has no videos.
- `redaction_flag` is the official "Redaction" column (TRUE means the release marks the clip as redacted).
- The official "Description Blurb" is not copied into the index; it is used during triage.

## Counts

134 videos: R01 27, R02 51, R03 6, R04 19, R05 16, R06 15 (computed by `tools/check_pursue_index.py`). No duplicate clip IDs.

Agencies: Department of War 123, FBI 7, Local Law Enforcement 4.

## Oddities in the official data

- DOW-UAP-PR057a and PR057b share DVIDS ID 1007720.
- DOW-UAP-PR093 and PR095 have identical titles ("May 05 2020 Gulf of Arabia ... Dual UAP") but different DVIDS IDs.
- DOW-UAP-PR045 is titled "Middle East, 2020" but its incident location is "Southern United States".
- DOW-UAP-PR099 is titled "25SEP19" but its incident date is 2023.
- DOW-UAP-PR117 to PR122 list their PDF pairing as "DOW-UAP-PR-101", which is not a valid document ID.
- FBI-UAP-PR005 and PR006 are described officially as artistic digital recreations, not sensor footage: not reconstructable by definition.
- DOW-UAP-PR159 is a 1952 16mm film (Tremonton, Utah), not a sensor video.
- The Haqq-Misra and Kopparapu paper's per-release counts (27/50/0/19/16, total 112) differ from this official list; R03 holds FBI clips in this index.
