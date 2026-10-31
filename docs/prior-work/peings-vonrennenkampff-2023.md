# Reconstruction of Potential Flight Paths for the January 2015 "Gimbal" UAP

- **Title:** Reconstruction of Potential Flight Paths for the January 2015 "Gimbal" UAP (PDF header title: "AIAA: Reconstruction of potential flight paths for the January 2015 'Gimbal' UAP")
- **Authors:** Yannick Peings and Marik von Rennenkampff, independent researchers (p. 1). LT Ryan Graves is a cited witness and is thanked in the acknowledgments, not an author (p. 30).
- **Date:** v1 submitted 06/14/2023; v2 last revised 11/15/2023 (arXiv abstract page, https://arxiv.org/abs/2306.08773)
- **URL:** https://arxiv.org/abs/2306.08773 ; PDF https://arxiv.org/pdf/2306.08773 (v2 read, 30 pages, 8.2 MB)
- **Version read:** v2
- **License:** not stated in the PDF. Code and data: https://github.com/ypeings/Gimbal-UAP.git (p. 30, data availability statement). The repo and its license were not inspected in this task.
- **Prepared:** 10/30/2026. Page numbers are the PDF page and the printed page number (they are identical). "Fig." numbers are the paper's.

## Event identification stated by the paper

| Item | Paper statement | Page |
|---|---|---|
| Date | Not known with certainty. "One evening in January 2015." Department of Defense statements point to 01/21/2015; the metadata of the DoD-released video says it was encoded 01/25/2015 02:29 UTC, which is 01/24/2015 9:29 pm EST; an unclassified DoD email dates the event to 01/25/2015. Using hourly ERA5 winds the authors find the evening of 01/24/2015 a better match for a 120-kt westerly than 01/20 or 01/21. | pp. 2, 6 |
| Location | "approximately 300 miles off the coast of Jacksonville, Florida" (approximate location in Fig. A1; wind map for 01/25/2015 00:00 UTC, 7 pm EST) | pp. 2, 21 |
| Platform and unit | F/A-18F Super Hornet, VFA-11, returning to USS Theodore Roosevelt (CVN-71) after a COMPTUEX air-to-air mission; AN/ASQ-228 ATFLIR; clip is 34 s | pp. 1-3 |
| Light | LT Graves has stated Gimbal was filmed after sunset | p. 6 |

So the paper's own best estimate of the GIMBAL date is 01/24/2015, about 9:29 pm EST (video encode time 01/25/2015 02:29 UTC); the date is explicitly unresolved (01/21, 01/24, 01/25 all appear in the cited material).

## Inputs

| Quantity | Value | Source location (page, section) |
|---|---|---|
| Aircraft IAS | 238 to 242 kt through the clip, read from the ATFLIR display | p. 6, Sec. III.A |
| Altitude | 25,000 ft, "almost constant", read from the display; path reconstructed in 2-D | pp. 6-7, Sec. III.A |
| Air temperature | about -25 C, "estimated from meteorological data around that altitude on January 24th, 2015" | p. 6 |
| IAS to TAS conversion | e6bx TAS calculator (https://e6bx.com/tas/); result TAS 363 to 369 kt; "for each selected frame, the corresponding TAS value from that interval is used" | p. 6 |
| TAS used in plots | "~365 kts" | Fig. 3 caption, p. 7 |
| Bank angle | extracted every 10 frames; the clip is stated as "30 fps" and "1034 frames", giving "103 values of banking angle, from frame 1 to 1031"; elsewhere "104 reconstruction points" | p. 6; p. 8 |
| Rate of turn | ROT (deg/s) = 1091 x tan(bank) / TAS, with TAS in kt and the aviation rule "commonly used" (their ref. [2]); Eq. (1) | p. 6 |
| Equations of motion (every 10 frames) | x(t) = x(t-1) + TAS dt sin(beta) - Ws dt sin(Wd); y(t) = y(t-1) + TAS dt cos(beta) - Ws dt cos(Wd); Eqs. (2),(3). beta = heading, starts at 0 deg; TAS and Ws in Nm/s; dt = time between 10 frames, "~0.3 s"; Wd = wind direction, "0 deg for headwind, 180 deg for tailwind" | pp. 6-7 |
| Wind speed and source | 120 kt from the west. Source 1: the WSO says on the video audio that the wind is "120 knots to the west" (read by the authors as westerly, from the west). Source 2: ERA5 reanalysis shows a jet stream with 110 to 120 kt westerly at about 25,000 ft off Jacksonville (Fig. A1, 400 hPa about 24,000 ft) | p. 6; p. 21 |
| Wind direction relative to the jet | Chosen -35 deg (35 deg to the left of the initial F/A-18F heading); tested range -70 to +70 deg; "sweet spot" -50 to -15 deg | pp. 7, 10-11 |
| Wind applied to the object? | The F/A-18F path is drawn with wind in Fig. 3 and Fig. 6a; for the LOS construction (Fig. 4) wind is omitted for the jet, "assuming the wind is similar for both" (object within 10 Nm stays above 23,000 ft) | pp. 7-8 |
| Azimuth | Displayed integer values, "rounded and updated every other frame"; smoothed by a moving average of 50 frames of the raw extracted Az; plus a cloud-motion refinement (below). Az goes from 54 deg left to 7 deg right | p. 8 |
| Azimuth refinement from clouds | "about 9 fields of view are scanned"; at 0.35 deg per FOV, 9 x 0.35 = 3.15 deg; a term is added to the LOS "that gradually adjusts" Az to match the observed change in the number of scanned FOV | p. 8 |
| Elevation | Displayed El constant at -2 deg ("likely corresponds to a [-1.5 / -2.5] range"). Flat cloud cover assumed. Constrained by the cloud line lowering about 0.05 deg in the FOV: El starts at -2 deg and increases linearly to -1.95 deg across the 104 reconstruction points | p. 8 |
| FOV | NAR2 = 0.35 deg (0.35 x 0.35 horizontal and vertical), a 2x digital zoom of the NAR 0.7 deg optical FOV. "Current consensus" 0.35. Debated 0.35 vs 0.7; Fig. A4 repeats with 0.7 | p. 8; p. 15 |
| Range, aircrew account | Object "within 10 nautical miles"; WSO estimate relayed by LT Graves refined to 6 to 8 Nm; range value in the incident report is redacted | pp. 2-3 (Fig. 1 page 4) |
| Range used for the "best-guess" path | Starts at 8 Nm, straight line, ends 6.8 Nm (13 percent closer) | p. 10-11 |
| Size change | Apparent size grows about 15 percent (11 images, every 100 frames; pixel count above a constant grayscale threshold in ImageJ; white-hot to black-hot step compensated), so distance falls about 13 percent (1/1.15 = 0.87). The -10 to -20 percent band is shown for uncertainty | p. 10; Fig. A2 p. 22 |
| Object size | 15 to 20 ft along the longest axis at 8 Nm, from the object spanning 1/15 to 1/20 of the 0.35 deg horizontal FOV; formula size = 2 tan(FOV/2) x distance x 6076.12 ft/Nm x fraction (Appendix) | pp. 10, 21 |
| Object direction | Straight line, "generally against" the wind, offset 15 deg from the wind direction (so 20 deg left of the initial jet heading for wind at -35 deg); tested offsets -40 to +40 deg | pp. 10-13 |
| Pixel scale at 30 Nm | One NAR1 pixel about 4 to 5 ft at 30 Nm: size(ft) = 2 tan(FOV/2) x dist(Nm) x 6076.12 / 480 (pixels on width) | Fig. A8 caption, p. 28 |

## Conventions and assumptions

- Az is measured from the jet's forward axis (boresight "is not aligned with direction of travel in the presence of crosswind", p. 8). Left of the nose is called "L" and right "R"; Az 0 means the object is directly ahead.
- Wind angle convention: "0 deg for headwind, 180 deg for tailwind" (p. 7), and the wind direction is given relative to the initial F/A-18F heading, negative to the left, positive to the right (Fig. 5 caption, p. 11).
- Wind source "120 kt to the west" is taken as a westerly (wind from the west) (p. 6). The initial absolute heading of the jet is not stated, so "-35 deg relative to heading" cannot be converted to a compass wind direction without it. (Sitrec uses a 315 deg initial heading with wind from 270, i.e. -45 deg.)
- Frame indexing: frames are described as 30 fps and 1034 frames with samples at frames 1, 11, ... 1031 (p. 6). The Sitrec data use 29.97 fps and 1031 frames, 0 to 1030. How frame 1 maps to frame 0 is not stated.
- Same-wind frame of reference: for LOS plots the jet and object are in the same moving air mass (Fig. 4 caption, p. 9); the object's ground track is obtained by adding wind (Sec. IV.A, p. 9).
- Elevation treated as constant plus a linear drift; the ATFLIR pod is assumed to point along the displayed Az/El in a gravity-levelled frame (no roll or pitch treatment is described for the jet attitude beyond bank for ROT). Jet pitch is not mentioned.
- The paper models the lines of sight only; pod roll, derotation and glare are discussed qualitatively (Sec. IV.B), not modelled.

## Method

1. Jet air track (every 10 frames): from IAS to TAS, bank angle to rate of turn by ROT = 1091 tan(bank) / TAS, integrate heading, advance by TAS sin(beta) and TAS cos(beta) (pp. 5-6). Ground track: subtract the wind term using Eqs. (2) and (3) (p. 6). Result (Fig. 3, p. 7): with a 120 kt wind from 35 deg left of the initial heading the jet ends "around coordinates (-1. ; 1.9), in Nm" (text truncated as printed; the plotted solid curve ends near X = -1.0 Nm, Y = 1.9 Nm, read from the figure by this lab; the no-wind dashed curve ends near X = -1.65, Y = 2.87 Nm). The text cites "equations (1) and (2)" for this figure, a mislabel for Eqs. (2) and (3).
2. Lines of sight (every 10 frames): Az (50-frame moving average, plus cloud-motion correction term) and El (-2 to -1.95 deg linear) applied to the jet air track (p. 8). The convergence of the LOS in the top view (Fig. 4, p. 9) is cited as consistent with the decreasing angular cloud speed.
3. Candidate object paths: with the aircrew range constraint (within 10 Nm; 6 to 8 Nm) and the size-change constraint (about -13 percent distance), intersect LOS with a straight-line path against the wind. Scan wind direction (-70 to +70 deg) and object offset from the wind (-40 to +40 deg); record percent change of distance from start to end (Fig. 5, p. 11). Pick wind -35 deg and offset +15 deg (pp. 10-11).
4. Present the path in two frames: ground frame, to compare with the SA (radar) display (Fig. 6a, p. 13), and air frame (Fig. 8, p. 14).
5. Sensitivity: FOV 0.7 deg (Fig. A4, p. 24), no cloud-motion LOS adjustment (Fig. A5, p. 25), wind +35 deg to the right with offset 10 deg (Fig. A6, p. 26).
6. Distant-plane check: reproduce a 30 Nm solution (Fig. A7, p. 27) and compare IR size with an F/A-18F at 30 Nm (Fig. A8, p. 28).

## Results

### Best-guess close path (Sec. IV.A, Figs. 6 to 8, pp. 11-14)

| Quantity | Value | Page |
|---|---|---|
| Start range | 8 Nm | pp. 10, 13 |
| End range | 6.8 Nm (13 percent closer) | p. 11, 13 |
| Wind | 120 kt, 35 deg left of initial heading | p. 11 |
| Object heading offset | 15 deg from wind (20 deg left of the jet's initial heading) | Fig. 6 caption, p. 13 |
| Object air speed at start | about 400 kt, falling nearly linearly to under 50 kt around frame 900 | p. 11 |
| Object ground speed | about 300 kt at start, minimum near 0 at about frame 720, exceeds 120 kt by the end | p. 11 |
| Ground-speed reversal | about frame 720 (object passes under 120 kt relative to ground, reverses on the SA display); coincides with the first step rotation in the video (about frame 720) | p. 11 |
| Long continuous rotation | around frame 900 (yellow band in Fig. 7); "vertical U-turn" in the air frame | pp. 11-12, 14 |
| Altitude change | climbs about 250 ft over the clip (Fig. A3, p. 23); about 300 ft in the Sitrec comparison (Fig. 10, p. 18) | pp. 12, 23, 18 |
| Plausible initial air speed range | 200 to 450 kt | p. 12 |
| Sensitivity of initial speed | a similar path with initial ground speed about 180 kt at wind -25 deg, offset 20 deg, 9 Nm | Fig. 7 caption, p. 14 |
| Object IR size | 15 to 20 ft long | pp. 10, 20-21 |

### Other cases

| Case | Result | Page |
|---|---|---|
| FOV 0.7 deg, 8 Nm | start speed 250 kt, climbs about 350 ft; still a vertical U-turn | p. 15 (Fig. A4 p. 24) |
| No cloud-motion LOS adjustment | "noisier, although qualitatively similar" | p. 15 (Fig. A5) |
| Wind 35 deg to the right, offset 10 deg | vertical U-turn; closes 37 percent (about 50 percent apparent growth, not observed); climbs about 600 ft; rejected | pp. 15, 26 |
| Sitrec straight-line example, 9 Nm | wind 120 kt from 35 deg left of heading; object slows below wind speed, ground speed 0 around frame 780; climbs about 300 ft; "vertical U-turn"; "remarkably consistent" with the authors' own result for close paths (also with two other independent researchers) | pp. 16, 18 (Fig. 10) |
| About 30 Nm level path (Fig. A7) | altitude fixed at 18,700 ft; object air speed must rise from 300 to 450 kt; "not a particularly straight nor steady flight path" | pp. 16, 27 |

### Conclusions stated (Sec. V, p. 20)

- At witness range (within 10 Nm) the geometry requires the object to stop and reverse along the vertical ("vertical U-turn"), matching the aircrew's SA description and coinciding with the video rotation.
- Wind is critical; it explains why the SA stop precedes the IR rotation.
- The IR signature is about 15 to 20 ft long at 8 Nm, "markedly smaller than any conventional aircraft".
- The paper's opinion: the "distant plane" hypothesis "does not fit the data" and the close scenario "requires fewer low-probability assumptions".

## Caveats stated by the authors

- Range is the critical missing quantity; the "solution we highlight here depends on the accuracy of the provided radar range (< 10 Nm), which is not available to us" (p. 20).
- Only one potential trajectory is shown, "our best-guess estimate", not extremely sensitive to exact parameters "as long as they obey the general configuration" (p. 12).
- Initial air speed "is quite uncertain" (200 to 450 kt) (p. 12; Fig. 7 caption p. 14).
- Altitude change is "one of the most uncertain parameters" because the pod elevation variation is unknown and a linear increase is imposed, "likely smoothing" real changes (p. 12).
- The 0.35 vs 0.7 deg FOV was debated; 0.35 is the "current consensus" (p. 15).
- "What is seen in the Gimbal video is an infrared signature, and how it reflects the true shape and size of the object is uncertain" (p. 10).
- The wind direction/offset analysis is "more speculative given the potential influence of other factors like error in the ATFLIR derotation mechanism" (p. 10, about the horizon misalignment between frames 500 and 800).
- "Identifying the object is beyond our expertise" and the authors invite aeronautics and defense experts to comment (pp. 1, 18, 20).

### How the paper treats West's distant-plane hypothesis (Sec. IV.B, pp. 16-18)

- Acknowledges Sitrec and that for close trajectories "Sitrec and our own recreation are remarkably consistent" (p. 16).
- States West does "not believe this scenario is plausible": in Sitrec the LOS flatten near 30 Nm so a level path can be drawn there, read as a jet seen tail-on whose exhaust glare is rotated by the pod; the rotation is then an ATFLIR artifact (p. 16).
- Confirms the 30 Nm solution exists ("We also find this solution") but not a steady one (Fig. A7: speed 300 to 450 kt at fixed 18,700 ft) (p. 16, 27).
- Lists six objections (pp. 16-18): (1) requires the aircrew to have locked the wrong target and the witnessed range to be wrong; low probability of a tail-on plane at 30 Nm in a 0.35 deg FOV; (2) Navy could not identify a plane in a controlled range; (3) the "fleet" would have to be unrelated; (4) the LOS from a distant plane mimic the close path described by the aircrew, which implies radar error or spoofing; (5) IR size and shape mismatch with an F/A-18F exhaust at 30 Nm (Figs. A8 to A10, pp. 28-29); (6) the stepwise pod roll required by the glare theory is not described in the ATFLIR patent (US 9,121,758 B2) or by two private ATFLIR experts; "we recognize this is well beyond our expertise" (p. 17-18).
- Explicitly does not "thoroughly discuss the plausibility" (p. 16). Concludes that "it is our opinion that this hypothesis does not fit the data" (p. 20).

## Open points (ambiguous or unstated)

1. Absolute initial heading of the F/A-18F and the true wind direction are not given, only wind relative to heading.
2. Which IAS-to-TAS inputs gave 363 to 369 kt (calibrated vs indicated airspeed, e6bx assumptions beyond temperature) is not stated. Sitrec uses 351 kt.
3. The cloud-motion correction term to Az is described but not given numerically ("gradually adjusts them to match the change in number of scanned FOV", p. 8).
4. Frame numbering (30 fps, 1034 frames) vs the video's 1031 frames at 29.97 fps.
5. The printed jet end point for the wind case in Fig. 3 reads "(-1. ; 1.9)" (truncated in the PDF); the plot shows about (-1.0, 1.9) Nm. The paper does not state the initial compass heading (the plot is drawn with initial heading along +Y).
6. Altitude of the Fig. A7 level path (18,700 ft) is "set constant"; whether 30 Nm is the unique level solution is not shown.
7. The elevation drift (-2 to -1.95 deg across 104 points) is a hand-fit to the cloud line, not a measurement; Sitrec instead uses -2.01 rising 0.025 deg.
8. Date ambiguity (01/21, 01/24, 01/25/2015) persists; ERA5 favours 01/24/2015 evening.
9. The jet pitch, crab angle and the pod boresight offset are not modelled; the paper says Az is relative to boresight but then uses it with the heading-derived air track.
10. The GitHub repo (ypeings/Gimbal-UAP) was not read; numeric tables may exist there.
