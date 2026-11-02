# Testimony as likelihood terms (M3.3c)

Written 10/31/2026. Code: `solve/testimony.py`. Mapping: `data/testimony/scorable.yaml` (hand-written, one entry per claim, each with a one-line reason). Tests: `tests/test_testimony.py`. Design: `docs/design/scoring.md`, Testimony row (binding).

Nothing here is a finding about what any object was. It records which statements the scorer can test, how, and where the witnesses' memory of on-screen numbers matches the record.

## How claims become terms

- A claim is **scored** only if it constrains a quantity the trajectory models predict for this object during this clip: range, object altitude, ground or air speed, length, the stop-and-reverse, motion against or with the wind, the range trend, the reversal radius.
- Each scored term is an interval [lo, hi] with a Gaussian edge whose width is the claim's uncertainty band: flat inside, Gaussian tails outside. Categories (stop-and-reverse, motion vs wind, range trend) use a 10 percent chance that the recollection is wrong, the same for every claim.
- A term can be conditional (11/01/2026, REVIEW-M3 Rule G): G-T25, the reversal radius, scores only a path that stops and reverses and contributes 0 otherwise; whether the object reversed is scored once, by G-T11. (Before CP-04 a path that never reversed was scored at a 1,000,000 ft sentinel radius, which cost every such path about 24.6 log units from one claim.)
- Firsthand claims weigh 1.0, relayed claims 0.5. Conflicting claims each enter with their own interval. The same witness repeating the same value is scored once.
- Class statements (all East Coast contacts over 2014 to 2015), counts of other objects, locations, other events and, for FLIR1, the state of the object during Fravor's merge an hour before the clip, are context and are not scored.
- Claims about on-screen numbers (jet altitude and speed, range and closure fields, polarity, the clip's length) test memory against the record. They are reported in the witness-consistency tables below and **never change a hypothesis score**. Wind, time of day and visibility are environment, checked against ERA5 or ephemeris, not used to tell hypotheses apart.

**Interface for the scorer.** `testimony_loglik(case, predicted)` with `predicted` a dict of the quantities in `required_quantities(case)` (scalars or per-frame arrays; the same keys for every hypothesis; pass `missing="raise"` to enforce that). It returns rows `{claim_id, quantity, predicted_value, interval, loglik, weight, firsthand, weighted_loglik}`; the criterion value is `total(rows)`, multiplied by the testimony weight (1.0 default, 0 for the physics-only total). The module rejects any key that is not a quantity, so no hypothesis name can reach it, and identical numbers always give identical rows.

## GIMBAL: 41 claims, 8 scored (9 terms)

| Claim | Witness | Firsthand | Quantity | Interval (edge) |
|---|---|---|---|---|
| G-T09 | Graves | yes | ground_speed_kt | 0 to 30 (20) |
| G-T09 | Graves | yes | object_altitude_ft | 15,000 to 25,000 (2,500) |
| G-T11 | Graves (via P&vR) | yes | stops_and_reverses | true |
| G-T12 | recording WSO (via P&vR) | no | range_nmi | 0 to 10 (1.5) |
| G-T13 | Graves (via P&vR) | no | range_nmi | 6 to 8 (2) |
| G-T14 | Graves (via P&vR) | no | range_trend | decreasing |
| G-T21 | cockpit crew on the tape | yes | motion_vs_wind | against |
| G-T25 | Graves | yes | reversal_radius_ft, only for a path that reverses (REVIEW-M3 Rule G) | 50 to 500, log scale (0.5 dex) |
| G-T28 | Graves | no | ground or air speed (either) | 90 to 110 (20) |

Not scored (33): 11 class statements, 6 counts of other objects, 5 locations or times, 3 duplicates of G-T11's reversal, 2 other events, 2 image content, 2 sensor or data, 2 roles. Environment: G-T20 (wind 120 kt from the west at about 25,000 ft) and G-T15 (after sunset).

**Witness consistency**

| Claim | Recalled | On screen (lab) | Difference | Status |
|---|---|---|---|---|
| G-T28 | jet at 242 kt | 238 to 242 kt | 0 | agree |
| G-T29 | black hot | BLK on 659 frames, WHT on the first 372 (12.4 s) | 36% of frames differ | partial |
| G-T29 | dark object putting out heat | object hotter than background on all 1,031 frames | 0 | agree |

**Conflicts.** 12 conflicting pairs, 5 of them between different witnesses (all context: wind speeds, class speeds, the near-miss distance). Two pairs are both scored and enter side by side, both from Graves: basically stationary (G-T09) vs about 100 kt (G-T28), and a reversal with no radius (G-T11) vs a U-turn within about 500 ft (G-T25). The wind is 120 kt on the tape (G-T20) against Fravor's relayed 70 or 90 kt (G-T36).

## GOFAST: 11 claims, 2 scored (2 terms)

| Claim | Witness | Firsthand | Quantity | Interval (edge) |
|---|---|---|---|---|
| F-T01 | AARO case card | no | object_altitude_ft | 0 to 2,000 (2,000) |
| F-T04 | Graves | no | range_nmi | 4.3 to 5.0 (1.0) |

Not scored (9): 4 on-screen facts (tested below), 2 counts, 2 sensor or data, 1 role. No GOFAST claim is firsthand: no one from the recording crew has been interviewed at length in the sources found. The on-screen range already fixes the object's altitude near 13,000 ft for every model, so F-T01 costs every hypothesis about the same.

**Witness consistency**

| Claim | Recalled | On screen (lab) | Difference | Status |
|---|---|---|---|---|
| F-T04 | range field 3.4 to 3.5, ticking down | 4.4 down to 3.3 nmi (3.4 to 3.5 in the last 4.7 s) | 0 | agree |
| F-T05 | recording jet about 10,000 ft | 25,000 to 25,010 ft | -15,000 ft | disagree |
| F-T06 | 170 under the range | closure 220 down to 150 kt (170 on screen f751 to f857) | 0 | agree |
| F-T09, F-T10 | black hot | BLK on 885 frames, WHT f638 to f783 | 14% of frames differ | partial |
| F-T09, F-T10 | object colder than the background | object colder on all 771 frames where it is found | 0 | agree |

Graves's 10,000 ft does not match the jet's readout. His sentence may refer to the object's height instead; the lab's reproductions put the object near 13,200 ft, closer but still outside his rounding. His estimate of the true range (about 5 miles) is scored as a hypothesis term; his reading of the display (3.4 to 3.5) matches the record.

## FLIR1: 108 claims, 14 scored (18 terms)

| Quantity | Claims (relayed marked *) | Values |
|---|---|---|
| size_ft (7) | T-T14, T-T20, T-T33 (Fravor); T-T28* (Dietrich via report); T-T57 (Underwood via Gizmodo); T-T67 (CVW-11 log); T-T71* (2009 report) | 40, 56, 47; 30 to 40; 40; 25 to 30; 45 ft |
| object_altitude_ft (6) | T-T44, T-T95 (Day); T-T101 (Voorhis); T-T64* (log); T-T13*, T-T01* (Fravor relaying) | 28,000; 20,000 to 28,000; 25,000 to 28,000; 25,000; 20,000; 20,000 ft |
| ground_speed_kt (4) | T-T44 (Day); T-T101 (Voorhis); T-T64* (log); T-T57 (Underwood) | 100, 100, 100, 120 kt |
| range_nmi (1) | T-T60 (Underwood, at the last frame) | 8.7 to 13 nmi (10 to 15 miles) |

Not scored (94): 33 about Fravor's merge an hour before the clip, 10 radar events outside the clip (the 80,000 ft descents, the CAP-point jumps), 13 locations or times, 12 sensor or data, 12 image content, 5 counts, 5 duplicates, 4 other days or occasions. Environment: surface wind 5 to 10 kt (T-T87), sea state (T-T03), visibility (T-T36), time of day (T-T70, T-T91).

Altitude, speed and range are scored as the radar contacts' cruise state, which the second sortie was vectored to (Day, T-T51). Length is scored under the witnesses' identification of the filmed object with the one they saw; a hypothesis that the clip shows something else is penalized by those claims, which is the point of testing testimony.

**Witness consistency** (FLIR1 has no per-frame OCR yet; altitude, speed and range-field readings are the M0 hand reading in `docs/audit/flir1.md`)

| Claim | Recalled | Record (lab) | Difference | Status |
|---|---|---|---|---|
| T-T17 (Fravor) | video about 90 s | 76.3 s (2,288 frames at 30 fps) | +13.7 s | agree (within "a minute and a half") |
| T-T53 (Day) | about 10 s | 76.3 s | -66 s | disagree (he may have received an excerpt) |
| T-T63 (Weigelt) | 8 to 10 min | 76.3 s | +404 s | disagree with the released clip (a longer tape is not ruled out) |
| T-T75 (Fravor) | jet about 20,000 ft (19,990) | 19,990 to 20,000 ft | 0 | agree |
| T-T75, T-T76 (Fravor) | jet 250 kt | 240 to 253 kt | 0 | agree |
| T-T77 (Fravor), T-T78 (Underwood) | range field reads 99.9 | no range field found in the M0 audit | | disagree, to confirm when FLIR1 is read per frame |

**Conflicts.** 71 conflicting pairs, 55 between different witnesses. Ten pairs are both scored and enter side by side: length (25 to 30 ft in the log, 30 to 40, 40, 45, 47 and 56 ft) and cruise altitude (20,000 ft from Fravor relaying the controller, 25,000 ft in the log, 28,000 ft from Day, and Day's own later band of 20,000 to 28,000 ft). The duration claims (10 s, 90 s, 8 to 10 min) are tested against the clip's 76.3 s above.

## Notes for the scorer and the owner

- **Magnitude.** The binding Gaussian edge grows quadratically outside an interval. A path at 30 nmi in GIMBAL gets -95 from G-T12 and -65 from G-T13 (before the 0.5 relayed weight), against about -2 inside them. A floor or an outlier mixture would bound one memory's influence; that is a design choice for Stewart, not made here.
- **Double counting.** The H-WIT model takes its range prior from the same testimony (GIMBAL 6 to 8 nmi). Scoring G-T12 and G-T13 against it as well counts those claims twice; the scorer should decide how to handle that.
- **Equal treatment.** Pass every quantity in `required_quantities(case)` for every hypothesis (or `missing="raise"`); a hypothesis that omits a quantity silently skips those claims. GIMBAL needs 8 quantities, GOFAST 2, FLIR1 4. Definitions (for example, what counts as a stop and reverse) are in `scorable.yaml`.
- **Flagged for the testimony files.** T-T57 (Underwood's 40 ft and 120 kt) is marked firsthand in `flir1.yaml`, but Underwood says he never saw the object by eye (T-T56); the weight follows the file as recorded.
- **Environment checks are pending.** `data/weather/` holds ERA5 profiles for FLIR1 only, so the GIMBAL and GOFAST wind claims (120 kt on the tape, 70 or 90 kt relayed) await the GIMBAL ERA5 pull.
