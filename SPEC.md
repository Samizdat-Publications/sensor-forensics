# SPEC.md: Sensor Forensics Lab

## Pipeline per video

1. **Ingest:** official copy, frame extraction, hash.
2. **Symbology extraction:** OCR and template matching of every on-screen field per frame; manual correction tool; confidence per value.
3. **Jet reconstruction:** jet path from altitude, airspeed, bank and heading cues (horizon line, turn rate), with uncertainty.
4. **Line of sight:** per-frame vectors from pod angles, corrected for jet attitude; field of view from zoom.
5. **Object track in image:** position, size, orientation, brightness of the object per frame; background motion (clouds, ocean) for independent checks of camera motion.
6. **Trajectory families:** for each candidate range (or range profile), solve the object's 3D path; compute speed, acceleration, altitude.
7. **Hypotheses:** each is a physical model with parameters:
   - distant aircraft (jet exhaust glare), balloon drifting with measured winds, bird, a close small object, a fast object at the aircrew-reported range, sensor artifacts (glare that rotates with the pod's derotation, focus and zoom effects)
   - plus any hypothesis Stewart adds (Q-001)
8. **Scoring:** how well each hypothesis reproduces the observed line of sight, angular rate, apparent size, rotation, brightness, and background motion, plus consistency with testimony (weighted, adjustable).
9. **Discriminators:** for each pair of top hypotheses, the measurement that would separate them (for example, radar range at one timestamp).

## The experience (three.js web app)

- **Cockpit view:** the original video beside a synthetic re-render from the reconstructed geometry, frame-locked, with a difference overlay.
- **God's-eye view:** the jet, the line-of-sight fan, and each hypothesis's object path in 3D, with a range slider.
- **Range explorer:** speed, altitude, and acceleration of the object as functions of assumed range, with physically notable thresholds marked (balloon drift speed, bird speeds, airliner speeds, sonic speed).
- **Compare analyses:** Sitrec's solution, the 2023 paper's solution, and the lab's, side by side.
- **Evidence ledger:** every number, its source frame, and its confidence.
- Design pass with Claude Design if available, else the frontend-design skill.

## Exports

Each case exports in the UFO Case Files format (shared with Stewart's case files project) so it appears there too.
