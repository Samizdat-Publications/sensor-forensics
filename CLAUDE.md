# CLAUDE.md: Sensor Forensics Lab

## Boot order (every session, and after every compaction)

1. AUTONOMY.md
2. NEXT-SESSION.md
3. _PLAN.md
4. DECISIONS.md
5. QUESTIONS.md
6. ENGINE.md
7. SPEC.md
8. DATA.md

## Mission

Reconstruct, as forensically as the public data allows, what the sensors saw in:

- **GIMBAL** (January 2015, F/A-18F, ATFLIR pod, infrared)
- **GOFAST** (January 2015, ATFLIR, infrared, with range on screen)
- **FLIR1 / "Tic Tac"** (November 2004, USS Nimitz group)
- **The PURSUE sensor videos** released by the Department of War in 2026 (134 videos across Releases 01 to 06 as of 10/30/2026; see D-005), where the on-screen data allows it.

For each video: rebuild the jet's path, the camera's line of sight and field of view per frame, and the family of possible object trajectories, then score each explanation against the footage and the witness testimony.

## People and authority

- **Owner:** Stewart Gregerson. He wants forensic testing of hypotheses, not confirmation of any belief. His rulings outrank everything.
- **References:** the released videos and their on-screen symbology; public ATFLIR and F/A-18 documentation; Sitrec (Mick West, open source on GitHub; check its license before reusing code); Peings and von Rennenkampff 2023, "Reconstruction of Potential Flight Paths for the January 2015 Gimbal UAP" (arXiv 2306.08773; Graves is a cited witness, not an author); Haqq-Misra and Kopparapu 2026, "Limits on Kinematic Inference from the PURSUE Airborne Sensor Videos" (arXiv 2608.12445); aircrew public testimony (Graves, Fravor, Dietrich, and others) as constraints with stated uncertainty.

## Standing rules

- **Same geometry, same scoring for every hypothesis.** No per-hypothesis fudge factors.
- **Read the frame, don't guess it.** Every on-screen number is extracted per frame with a confidence; inferred values are labeled inferred.
- **Show the range problem honestly.** Where range is unknown, results are curves over range, not a single answer.
- **Credit and compare prior work.** Reproduce Sitrec and the 2023 Peings and von Rennenkampff paper; document every point of agreement and disagreement and why.
- No emdashes anywhere Stewart reads.
