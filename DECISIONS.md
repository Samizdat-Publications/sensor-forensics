# DECISIONS.md: owner rulings and binding choices

Newest at the bottom. Stewart's rulings are marked (owner ruling) and outrank everything.

- D-001 (owner ruling, 10/30/2026): Build as forensic a recreation of GIMBAL and GOFAST as the public data allows; test hypotheses, don't confirm a belief.
- D-002 (10/30/2026): Include FLIR1 and the 2026 PURSUE sensor videos where the on-screen data allows reconstruction.
- D-003 (10/30/2026): Reproduce prior public analyses first and document disagreements.
- D-004 (10/30/2026): Repo `Samizdat-Publications/sensor-forensics`, private.
- D-005 (10/30/2026, fact correction found while planning): The 2023 GIMBAL paper (arXiv 2306.08773) is by Yannick Peings and Marik von Rennenkampff; Ryan Graves is a cited witness, not an author. The 2026 PURSUE paper (arXiv 2608.12445) is by Jacob Haqq-Misra and Ravi Kopparapu. As of 10/30/2026 PURSUE has 134 videos across Releases 01 to 06 (Release 07 is documents only), not 112 across five tranches. Docs corrected.
- D-006 (10/30/2026): ENGINE pins Python 3.12 via a uv-managed `.venv` (meets the 3.11+ rule). The machine default is 3.14, and rapidocr needs Python below 3.13. No system-wide installs; Tesseract is skipped and rapidocr is the second OCR vote behind template matching.
- D-007 (10/30/2026): Repo layout adds `schemas/` (case file schema), `docs/` (audit, prior work, reproductions, results, design) and `handoff/` (the original package, for reference).
- D-008 (10/30/2026): The project lives in `C:\Users\stewa\Documents\Claude\Sensor forensics\` (the folder this session was opened in), not the kickoff's `C:\Users\stewa\Documents\Claude\sensor-forensics`, because Claude Code keys session history to the exact path and the global rule forbids moving or renaming project folders. The repo name stays `sensor-forensics`. See Q-004.
- D-009 (owner ruling, 10/30/2026): Stewart approved the M0 to M6 execution plan now in _PLAN.md.
