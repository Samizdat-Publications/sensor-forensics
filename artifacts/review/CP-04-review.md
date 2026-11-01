# CP-04 independent review

Reviewer: independent check, 11/01/2026. Commit reviewed: eb2ef56 ("CP-04 draft").
Gate rerun: `.venv/Scripts/python tools/gate.py` gives 239 tests, 0 failures, 0 errors, 0 skipped, node exit 0, GATE PASS.

**Overall: SEND BACK (Partial).** The scoring machinery treats every hypothesis alike in code, and the results pages are thorough and honest in their detail. But the checkpoint's own summary claims a pre-registration that the git history contradicts for D-017. Two hidden drivers set the GIMBAL headline rankings: the testimony sentinel radius and the rotation noise scale. The plain-words conclusions also leave out what recovery.md says the data cannot separate.

## Verdicts

| Criterion | Verdict | Reason |
|---|---|---|
| A results table per video with per-criterion scores | Pass | gofast.md, gimbal.md (both FOVs) and flir1.md each show both totals, ranks, k, best-fit parameters and a per-criterion table; scores.csv has every criterion for both fits of all 6 hypotheses (120, 216 and 96 rows); the results.json totals match the pages (spot-checked GIMBAL, all 12). |
| ... and the range curves | Partial | Each page has an angles-only constant-velocity range table (also in results.json `range_curve_angles_only`), but there is no per-hypothesis score-versus-range curve. CP-04 also cites `docs/reproductions/gimbal_range_curves.png` and `data/derived/gimbal/families/` as evidence, and both are M2 files whose own title and summary.json say "PROVISIONAL: jet heading 315 deg ... wind 120 kt ... placeholders". |
| Verifier checks equal treatment: same observables, likelihoods, testimony terms and weights | Pass | tests/test_equal_treatment.py passes (AST scan for ids and labels, `.id`/`.label` compares, rename and reorder invariance, name-blind fit, identical testimony claim sets). My own grep of solve/ found no hypothesis-name branching; the only model-key branch (recovery.py:309) is in reporting. Glare versus physical rotation is the design's stated split (scoring.md, Rotation row). |
| Same range support | Pass (one disclosed exception) | All YAMLs use 0.5 to 60 nmi log-uniform except H-CLOSE (0.05 to 2 nmi), which the binding design defines by its range; this is disclosed in Rule R and CP-04. |
| Priors cited and comparably generous | Partial | Every parameter has a source, and the bird, drone, airliner and balloon limits cite real references. But the BIC counts parameters, not prior width, so wide priors cost nothing: H-ART (0 to 600 kt) wins every GOFAST data set made by H-AC and H-CLOSE (recovery.md), and the H-WIT knots (plus or minus 20 km) are free. The H-SLOW 20,000 ft ceiling binds in every GIMBAL fit (19,997 ft). |
| Data-quality rules decided before seeing their effect on rankings | **Fail** (as CP-04 states it) | D-017 was committed 11/01 11:40 (07db8f5), nine hours after REVIEW-M3 (7d20dfb, 01:54) printed the 0.7 deg ranking with size weighted (H-WIT -62.5 first, H-ART and H-AC second and third, H-BAL fifth) and handed the choice to Stewart "with and without it". The brightness review item was raised because brightness "drives the ranking" (PROVISIONAL banner, 1e9c403). Rules B, R, T and P are stated inside REVIEW-M3 as written before measuring, but rules and results were committed together, so git cannot confirm that. All three exclusions move the physics-only leader to H-BAL: GOFAST size (H-ART led at 2c99399), GIMBAL 0.35 brightness (H-SLOW -51.4 against H-BAL -199.2 when added back) and GIMBAL 0.7 size (H-ART -106.1 against H-BAL -218.1 when added back). Each rule is physically defensible and applies the same to every hypothesis. What fails is CP-04's line "decided before looking at their effect". |
| Testimony terms equal for every hypothesis | Pass, with a hidden driver | Same claims and weights for all (firsthand 1.0, relayed 0.5, D-015 floor). But G-T25 (Graves, U-turn within about 500 ft) scores any non-reversing path at the code's 1,000,000 ft cap (models/base.py:152), which costs -24.6 per hypothesis against -0.5 for H-WIT. The same maneuver is also scored by G-T11 (-2.2), from the same witness. Without G-T25, H-BAL would lead the testimony-weighted total at both FOVs (by about 7 at 0.35 deg and 15 at 0.7 deg). The size of this term is set by the cap, not by any data. |
| Plain-words conclusions do not overstate (vs recovery.md) | **Fail** | GIMBAL: "a balloon-like drifter fits best" leaves out that recovery shows H-BAL winning every data set made by H-SLOW and by H-WIT, at both FOVs, so the lead cannot separate them. The 0.7 deg lead also exists only under D-017. "A radar range of 10 nmi or less would rule all four out" holds at 0.35 deg only: at 0.7 deg the balloon band is 9.0 to 13.5 nmi (gimbal.md). GOFAST: "a wind good to about 4 kt would separate a balloon from an object moving under its own power", but gofast.md says that works one way only against the slow flier. FLIR1: the summary is design-set only, and does not mention that H-BAL (-2,804 physics-only) beats both glare models (-2,947 and -2,949). |
| Both totals in each results table | Pass | Present in all three tables and in results.json. |
| No em dashes in reader-facing docs | Pass | A scan of checkpoints/, docs/, data/testimony/ and the root .md files found no U+2014, no entity form and no en dashes. |

## Must-fix

1. **Correct CP-04's pre-registration claim.** State that D-017 was an owner ruling made with both 0.7 deg rankings visible, and that the brightness and size reviews were prompted by provisional rankings. Put a line in the GIMBAL conclusion: at 0.7 deg the physics-only leader is H-BAL with D-017 and a glare model or H-WIT without it.
2. **Rotation noise scale (GIMBAL).** The rotation criterion uses sigma 0.88 deg, the scatter about a 9-frame running median. The best physical spline's residual RMS is 1.96 deg (largest 14.9 deg), so no model fits to that noise. By my estimate, scaling the reported numbers (n_eff 23, penalty 1.90 per term, 31 extra terms), the glare model overtakes the free physical rotation on this criterion if sigma is above about 1.3 deg. This criterion is nearly the whole glare-versus-physical gap in the GIMBAL totals (72.6 of 79). Rerun with sigma set from the residuals, or with a heavy-tailed likelihood, before saying "the rotation separates a glare from a physical object". Also disclose that H-WIT's k = 49 exceeds the BIC n = 45, and that physical models carry 33 rotation terms against a rotation n_eff of 23, where BIC is not valid.
3. **G-T25 sentinel.** Report the testimony-weighted GIMBAL totals with G-T25 treated without the 1,000,000 ft cap (for example, conditioned on a reversal, or capped at the largest radius the clip's path length can show), and say in CP-04 that the testimony-weighted H-WIT lead rests on this one term.
4. **Rewrite the plain-words bullets against recovery.md:** GIMBAL balloon versus slow flier versus free path are not separated; scope the radar-range claim to 0.35 deg; GOFAST wind separation is one-way against the slow flier; mention H-BAL's FLIR1 standing.
5. **Range-curve evidence.** Replace the M2 PROVISIONAL PNG and families/ citation with the M3 curves, or regenerate them with ERA5. Either add per-hypothesis physics-only total-versus-fixed-range curves for GIMBAL and FLIR1, or state in CP-04 that the range curves are angles-only constant-velocity curves.

## Nice-to-fix

- GOFAST and GIMBAL show per-criterion scores for the testimony-weighted fit only. Add the physics-only fit's breakdown: at GIMBAL the physics-only fits differ greatly (H-WIT at 59.8 nmi against 9.7 nmi).
- FLIR1 glare fits sit at the jet-pitch lower bound (0 deg; prior 3.8 plus or minus 1.5). Report how much of the +606 rotation gap the bound accounts for.
- discriminators.md still says "FLIR1 is being scored by another worker"; FLIR1 results now exist. Remove the internal process text.
- CP-04 says "28 scorable terms"; the results tables show 9 + 2 + 18 = 29. Reconcile the count.
- CP-04 calls F-T01 "the witness memory", but it is a relayed case-card report (firsthand: false).
- Q-008 is marked "Needed by CP-04" and is still open. Answer it, or move the date.
- Disclose in CP-04 that BIC ignores prior width (recovery.md already says so for GOFAST).

## Files

- C:\Users\stewa\Documents\Claude\Sensor forensics\checkpoints\CP-04.md
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\results\gimbal.md, gofast.md, flir1.md, recovery.md, REVIEW-M3.md, discriminators.md
- C:\Users\stewa\Documents\Claude\Sensor forensics\solve\models\base.py (line 152, radius cap)
- C:\Users\stewa\Documents\Claude\Sensor forensics\data\testimony\scorable.yaml (G-T11, G-T25)
- C:\Users\stewa\Documents\Claude\Sensor forensics\docs\reproductions\gimbal_range_curves.png (M2, provisional)
