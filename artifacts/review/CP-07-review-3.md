# CP-07 independent review, third check (M6: exports and wrap)

Reviewer: independent checkpoint reviewer, 11/02/2026, at commit d4dc0bc. Nothing in the repo was edited except this file.

| Item | Verdict | Evidence |
|---|---|---|
| 1. README no longer claims P&vR reproduced | **PASS** | Item 4 now reads "each rerun from its own inputs ... Sitrec reproduces; the paper's paths reproduce only in part, and `docs/prior-work/DISAGREEMENTS.md` says why." Matches `docs\reproductions\SUMMARY.md` (P&vR close path 7 of 8 checks, Fig. A7 Partial). The file table now says "Prior results rerun from their own inputs". Credits line claims only Sitrec's locked test value, which SUMMARY grades Pass (exact). |
| 2. CP-07.md review history | **PASS** | "Sent back twice (`CP-07-review.md`, `CP-07-review-2.md`); both criteria passed on the second check" is accurate: _PLAN.md lists two acceptance criteria (cases validate, recording), both PASS in review 2; the README item was PARTIAL there and its one must-fix is now fixed. Evidence table matches what I reran. |
| 3. README overclaims vs docs/results | **PASS** | Findings bullets unchanged since review 2, which checked them against the results pages; quick reread found nothing new. |
| 4. No em dashes | **PASS** | 0 U+2014 in `README.md` and `checkpoints\CP-07.md`. |
| 5. validate_cases | **PASS** | `.venv\Scripts\python.exe tools\validate_cases.py`: PASS flir1, gimbal, gofast, pursue-triage; 4 passed, 0 failed. |

## Notes (not blocking)

- The `cp-07` tag does not exist yet (CP-07.md says "fixed before tagging" and points to `git show cp-07`). Create it after this check.
- CP-07.md and _PLAN.md describe the pass as coming from the second check; add this third check to the independent-check line when tagging.
- Carried from review 2: "Sitrec reproduces" leaves out that Sitrec's "From Bank and Speed" distant path fails as specified (SUMMARY row 13); it passes with Sitrec's default cloud-matched turn rate at 0.35 deg.

## Overall: PASS
