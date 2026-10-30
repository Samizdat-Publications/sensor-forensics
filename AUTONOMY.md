# Autonomy Protocol

You (Claude Code) run this project on your own. Stewart checks in when he can. Work continuously, report at every checkpoint, and stop only for a true blocker as defined below.

## Execution model

- **Orchestrator (main session, high effort):** plans work items, delegates, reviews, integrates, and commits. Keep the main context lean.
- **Workers (subagents, medium effort, Sonnet or Opus):** well-scoped implementation tasks. Each brief is self-contained: goal, files to touch, the ENGINE.md contract to honor, and the test that proves it's done.
- **Background jobs:** long CPU work (downloads, data processing, model runs, renders, long test suites) runs in the background while you work on something else.
- **Independent check:** at every checkpoint, a fresh subagent that has not seen the implementation reviews the evidence against the acceptance criteria in _PLAN.md. Give it the criteria and the evidence, not your narrative. Fix what it finds before posting the checkpoint.

## Work loop

1. Read NEXT-SESSION.md and take the next open work item in _PLAN.md.
2. Check for answers from Stewart in three places: the conversation, QUESTIONS.md, and the "Answers from the control tower" section at the bottom of QUESTIONS.md. Fold each answer into DECISIONS.md.
3. Implement, test, and verify. Look at screenshots and renders yourself whenever the result is visual. Commit in small steps with clear messages.
4. Update _PLAN.md status, NEXT-SESSION.md, and `.tower/status.json` (see below).
5. When a checkpoint's work items are all done, run the checkpoint procedure, then keep going.

## Checkpoint procedure

1. **Gate:** all tests pass, and every acceptance criterion has evidence (screenshots, numbers, test output, a short video where motion matters).
2. **Independent check** by a fresh subagent, as above.
3. **Write** `checkpoints/CP-xx.md` from `checkpoints/CP-TEMPLATE.md`.
4. **Commit,** tag `cp-xx`, and push to the private GitHub repo.
5. **Post** the checkpoint message below in the session, and fire the notification hook if one is configured.
6. **Update** NEXT-SESSION.md so a brand-new session could resume from it alone, and update `.tower/status.json`.
7. **Continue** straight to the next work item. Do not end your turn or wait for a reply.

Checkpoint message format (plain text, no emdashes):

```
=== CHECKPOINT CP-xx: <title> (<MM/DD/YYYY HH:MM>) ===
DONE:
- <what now works, in plain words>
EVIDENCE: checkpoints/CP-xx.md (screenshots and numbers listed there)
NEXT:
- <next 2 to 4 work items>
QUESTIONS FOR STEWART (none of these block me; I'm using the defaults shown):
- Q-xxx: <question> | Default in use: <what I'm doing> | If you choose otherwise: <rework cost>
BLOCKERS: none
=== continuing ===
```

## Control tower status file

Stewart runs a local "control tower" dashboard that watches all his project folders. Keep `.tower/status.json` current (commit it). Update it at every checkpoint, every new question, every blocker, and at least once per milestone. Schema:

```json
{
  "project": "<repo name>",
  "title": "<human title>",
  "updated": "<ISO-8601 local time>",
  "milestone": "M2",
  "milestone_title": "<title>",
  "progress": {"done": 7, "total": 12},
  "last_checkpoint": {"id": "CP-02", "title": "<title>", "file": "checkpoints/CP-02.md"},
  "headline": "<one plain sentence: what is happening right now>",
  "needs_stewart": [{"id": "Q-003", "text": "<short question>", "default": "<default in use>", "needed_by": "CP-04"}],
  "blocked": false,
  "blocker": null,
  "highlights": ["artifacts/<best screenshot>.png"]
}
```

## Questions

- **Never wait for an answer.** Pick the most reasonable default (prefer reversible choices; prefer SPEC.md and the named references), log it in QUESTIONS.md, and proceed.
- **Each entry records:** ID, question, why it matters, the default in use, rework cost if the answer differs, and the checkpoint it's needed by.
- **Keep the list short.** Ask few, high-value questions, batch them at checkpoints, and never repeat one that's still open.
- **How answers arrive:** Stewart types `Q-xxx: <answer>` in the session, edits QUESTIONS.md, or answers from the control tower, which appends lines like `- Q-003: <answer> (MM/DD/YYYY HH:MM, via tower)` under `## Answers from the control tower` at the bottom of QUESTIONS.md. When an answer lands, record it in DECISIONS.md as `D-xxx (owner ruling)`, mark the question answered, and add any rework to _PLAN.md as a work item.
- **Authority order:** Stewart's rulings (DECISIONS.md), then SPEC.md and ENGINE.md, then the named references, then your own judgment.

## True blockers (the only reasons to stop)

1. You need something only Stewart can provide (a credential, purchase, account, or physical action) **and** no stub, placeholder, sample data, or fallback lets progress continue.
2. An action would be destructive or irreversible outside this repo: deleting or moving files elsewhere, force-pushing, spending money, or making anything public.
3. The toolchain cannot run after reasonable fixes and there is no alternative.
4. The same critical-path failure survives three materially different fix attempts with no alternate route.

On a true blocker:

1. Write BLOCKED.md: what's blocked, why, what you tried, and the exact action Stewart needs to take.
2. Set `"blocked": true` and fill `"blocker"` in `.tower/status.json`.
3. Post a message in the checkpoint format with `BLOCKERS:` filled in.
4. Keep working on anything that isn't blocked, and end the turn only when nothing productive remains.

**Not blockers:**

- Missing art or hardware: use a stand-in, sample data, or a simulator.
- Unanswered design questions: use the default.
- Missing optional data: use the fallback.
- Bugs off the critical path: log them in _PLAN.md.

## Guardrails

- Work only inside this repo folder unless ENGINE.md names a read-only input folder. API keys come from this repo's `.env`, which Stewart fills in himself and which is gitignored.
- Never commit secrets. Never make the repo public or deploy publicly unless DECISIONS.md says so.
- House style for anything Stewart reads (docs, UI text, checkpoint messages): no emdashes, dates as MM/DD/YYYY, display units in feet, mph or knots, and pounds.
- Prefer free, open data and tools. Never buy anything; queue purchases as questions.
- Don't load huge files or logs into context. Summarize them, and use subagents for broad searches.

## Context and continuity

- Long runs compact automatically, so the repo docs are your memory. After any compaction or new session, re-read the boot list in CLAUDE.md, starting with NEXT-SESSION.md.
- Keep NEXT-SESSION.md current enough that a session with zero memory can resume correctly.
