# CP-03 independent review

Reviewer: independent checkpoint reviewer, 10/31/2026. Scope: CP-03 acceptance from _PLAN.md M2 ("reproductions within a stated tolerance, or a documented explanation of the difference"), against the tolerances stated in _PLAN.md lines 215 to 218.

**Overall: Partial, not yet a pass.** The numbers are reproducible and the reporting is mostly candid. But the headline explanation ("the miss explained and resolved by the measured turn rate") is overstated, the distant-path result depends on an untested FOV assumption, and the gate fails.

## Verdicts

| # | Item | Verdict | Reason |
|---|---|---|---|
| 1 | Reruns match the quoted numbers | Pass | `solve.repro_gofast`, `solve.repro_gimbal` and `solve.turn_rate_gimbal` (3 min 50 s) all regenerate; `git diff --ignore-cr-at-eol` on docs/ and data/ is empty, and every figure quoted in SUMMARY.md and CP-03.md (13,192 / 13,243 ft, 63 kt, 6.64 nmi, f830, f880, 145 and 1 bad frames, f660 / f650, 6.24 nmi, 0 of 40) matches the JSON. |
| 2a | GOFAST: published values and verdict | Pass | 13,151 / 13,208 ft and 64 kt toward 93 deg match sitrec.md:171-173, and 41 ft and 1 kt sit well inside 300 ft and 5 kt. Caveats: the "published" values come from a third-party 2024 notebook run on an unpinned Sitrec HEAD, and the repro uses `Go Fast AZ.csv` while Sitrec's actual default is the `Az Editor` curve (sitrec.md:102). |
| 2b | P&vR close path: values and verdict | Partial | The published values match the paper summary. But the 15 percent speed and 60-frame tolerances are not in _PLAN.md and first appear in the same commit as the results (25cf1ab), so "stated in advance" is not demonstrated. "8 of 9" counts the start range, which is fixed by construction. The 259 vs 300 kt ground speed passes only under that self-chosen 15 percent band. |
| 2c | P&vR Fig. A7 | Partial | It is labelled Partial honestly. But "passes with the cloud turn rate (461 kt)" depends on the f881 to f981 end window: in gimbal_speed.png the cloud-rate curve climbs to about 700 kt over the last 50 frames. |
| 2d | Sitrec distant path | Pass | It fails as specified (145 frames), and that is reported. The criterion is self-constructed, because Sitrec prints no GIMBAL number, and gimbal.md says so. |
| 3 | "Turn-rate source decides GIMBAL" | Partial | **Independence holds.** The lab rate uses the lab's own bg_dx and lab azimuth. Sitrec's keyed curve is used only for comparison, and Sitrec's cloud height, cloud wind and pitch are small placeholders. **Three problems.** (i) omega is roughly -daz/dt minus h, and h is only 0.03 to 0.16 deg/s against 1.8 deg/s, so the 0.029 deg/s match to Sitrec's curve is partly structural. (ii) The image scale is assumed (0.35 deg over 426 px). Its "data check" fits Sitrec's bank lagged 24 frames, which is the competing source. I reran with a 0.7 deg FOV (scale 0.5): the total turn becomes -68.4 deg, the RMS against Sitrec's cloud curve rises from 0.029 to 0.132 deg/s, and the all-lab 340 kt distant path has no solution on 433 frames. The Monte Carlo band only spans scale +/-5 percent. (iii) With the cloud rate the close-path end range is 6.24 nmi against 6.8, a 0.56 nmi miss (tolerance 0.204); Sitrec's cloud port gives 6.33, also out. f650 (all lab, and the MC median) is 70 frames from f720, outside the 60-frame tolerance. So SUMMARY's "inside the 60-frame tolerance" holds only for f660 at the boundary. |
| 4 | Plain-words conclusions | Partial | "Geometry allows both readings, M3 decides" is fair and does not overreach either way. "Steady, straight, level ... 260 to 295 kt" overstates it: with the lab cloud rate the air heading wanders 26 to 42 deg (35 nominal), and with Sitrec inputs it has 27 no-solution frames, a 45 deg span and 208 to 292 kt. The distant reading's dependence on the 0.35 deg FOV is not stated. "Explained and resolved" (CP-03 evidence table) is not supported; see item 3 (iii). |
| 5 | Gate | Fail | `tools/gate.py`: 119 tests, 0 failures, 0 errors, 2 skipped, GATE FAIL. Both skips are tests/test_weather.py:177 and :189 ("saved ERA5 profiles not present"), from the in-progress M2.2 weather work (untracked solve/weather.py, tests/test_weather.py, data/weather/). The 35 CP-03 tests named in the brief all pass. CP-03.md points to an "independent check" at its bottom that does not exist. |
| 6 | No em dashes | Pass | There are 0 U+2014 characters in CP-03.md, SUMMARY.md, gimbal.md, gimbal_turn_rate.md, sitrec.md and peings-vonrennenkampff-2023.md. |

## Must-fix

1. Correct SUMMARY.md explanation 1 and the CP-03 evidence row. The cloud rate moves the minimum from 110 frames late to 60 to 70 frames early: f650 and the MC median are outside tolerance. It also pushes the end range out of tolerance (6.24 vs 6.8 nmi). Say "attributed", not "explained and resolved".
2. Test and disclose the 0.7 deg FOV case (reviewer run: 433 no-solution frames, RMS 0.132 deg/s vs Sitrec's cloud curve). Then either justify 0.35 deg without using the bank rate, or state the distant-path result as conditional on it.
3. Get the gate green before sign-off. Either land the ERA5 profiles, or keep in-progress weather tests out of the gated suite until they can run.
4. Label the GIMBAL A, A7 and B tolerances (15 percent speeds, 60 frames, 1.5 nmi, under 5 percent bad frames) as set at M2, not in _PLAN.md, or show where they were recorded before the run.
5. In the CP-03 plain words, qualify or drop "steady" (35 deg air-heading wander, a ground-speed range) and add the FOV condition.

## Nice-to-fix

- GOFAST: name the 0x1beef notebook and the unpinned Sitrec HEAD as the source of the "published" values, and run Sitrec's default `Az Editor` azimuth as a sensitivity.
- Say "7 of 8 non-trivial checks" instead of "8 of 9".
- State the A7 end window and what happens in the last 50 frames.
- Report the _PLAN.md line-of-sight RMS (0.1 deg) tolerance where it applies, or mark it not applicable. It is never mentioned in SUMMARY.md.
- Note the shape mismatch: the reproduced close-path air speed rises to about 410 kt at f250 and plateaus near 210 kt, not P&vR's "nearly linear" fall. The point checks hide this.
- In gimbal_turn_rate.md, say that the cloud rate is dominated by the azimuth derivative. The evidence against the bank rate is the measured cloud motion (6.4 to 1.1 px/frame), not the closeness to Sitrec's curve.
- Add the independent-check section that CP-03.md refers to.
