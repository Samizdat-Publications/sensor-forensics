# How far each video can be reconstructed (CP-01 verdicts)

10/31/2026. Details and evidence: `docs/audit/gimbal.md`, `gofast.md`, `flir1.md`, `pursue.md`.

| Video | Verdict | Why |
|---|---|---|
| **GOFAST** | Reconstructable to tight bounds | Range, pod azimuth and elevation, jet altitude, airspeed, Mach and a clock are on screen frame by frame, plus a closure rate (Vc) that is not among the stated inputs of Sitrec's GOFAST sitch or AARO's analysis. Object altitude and speed follow, limited mainly by the 0.1 nmi and 1 deg display steps and the unknown jet heading. |
| **GIMBAL** | Line of sight reconstructable; range not determined | Pod angles, airspeed, Mach, altitude, bank (horizon bars) and a clock are readable. No range, and elevation reads -2 in whole degrees throughout. Results are curves over assumed range; cloud motion and the jet's left turn give partial leverage. The glare rotation can be tested directly against a pod model because bank and pod angles are on screen. |
| **FLIR1** | Line of sight reconstructable with lower confidence; range not determined | Same pod angles, altitude and airspeed, but in a 352 x 264 copy with 5 to 6 px glyphs and little background texture for a parallax check. A range line appears from frame 973 on but reads a constant "99.9 RNG 99" (a placeholder, not a measurement; correction 10/31/2026 after M1 reading, the M0 audit missed it). The weakest of the three Navy videos. |
| **PURSUE (134 clips)** | None fully reconstructable; 16 bounded, 118 not viable (17 and 117 at CP-01; PR107 re-tiered at CP-06, D-019) | Redaction removes the pod angles, altitude and range from essentially every military clip. Seventeen carry a scale (tracker-gate size labels, tick-marked reticles, an angle ladder, partial pod angles, or known-size objects) that supports range-size-speed curves. |
