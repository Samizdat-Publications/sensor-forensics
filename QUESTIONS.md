# QUESTIONS.md: open questions for Stewart

None of these block work. Answer by typing `Q-xxx: <answer>` in the session, or by writing under the question.

| ID | Question | Why it matters | Default in use | Rework if different | Needed by | Status |
|---|---|---|---|---|---|---|
| Q-001 | Any specific hypothesis or analyst's claim you want tested? Name the source. | Scope | The SPEC.md list | Low | CP-04 | Answered D-010 |
| Q-002 | How much weight should aircrew testimony get by default (you can change it live)? | Scoring | Low, adjustable in the app | None | CP-04 | Answered D-011 |
| Q-003 | Publish results on the hub later? | Sharing | Private | None | CP-07 | Open |
| Q-004 | OK to keep the project in `Sensor forensics` (with a space) rather than the kickoff's `sensor-forensics` folder? | Session history is keyed to the folder path | Stay in `C:\Users\stewa\Documents\Claude\Sensor forensics\` | Low (a folder move plus re-opening the session) | Any time | Answered D-012 |
| Q-005 | Freeze the PURSUE scope at the start of M5 (including any release after 10/30/2026)? | Scope of M5 | Freeze at M5 start; later releases go on a follow-up list | Low | CP-06 | Answered D-013 |
| Q-006 | OK to define the UFO Case Files format here as schema v0.1, for the future Case Files project to adopt? | M6 exports | `schemas/ufo-case-file.schema.json` v0.1; align if the Case Files spec appears first | Low | CP-07 | Answered D-014 |
| Q-007 | GIMBAL at the 0.7 deg field of view: the object counts as resolved, but its size series comes from a saturated (clipped) blob. Should size count there? | Size is a scoring criterion; clipped blobs measure glare, not shape | Treat a saturated blob's size like brightness: reported, weight 0 for every hypothesis | Low | CP-04 | Answered D-017 |

## Answers from the control tower
