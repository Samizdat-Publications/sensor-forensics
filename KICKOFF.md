# KICKOFF: Sensor Forensics Lab (for Stewart)

A forensic reconstruction of the Navy targeting-pod videos (GIMBAL, GOFAST, FLIR1 "Tic Tac") and the 2026 PURSUE releases. It reads the telemetry burned into each video frame, rebuilds the jet's flight path and the camera's line of sight in 3D, then tests every competing explanation (distant aircraft, balloon, bird, close fast object, sensor artifacts like glare and gimbal rotation) against the same footage. The radar data stays classified, so the lab shows what each possible range implies instead of pretending to know the range.

## 1. One-time setup (PowerShell)

Extract the zip into `C:\Users\stewa\Documents\Claude\Claude Code Ideas\handoffs\`, then:

```powershell
cd "C:\Users\stewa\Documents\Claude"
Copy-Item -Recurse "C:\Users\stewa\Documents\Claude\Claude Code Ideas\handoffs\sensor-forensics" "C:\Users\stewa\Documents\Claude\sensor-forensics"
cd "C:\Users\stewa\Documents\Claude\sensor-forensics"
git init -b main
Move-Item "claude-setup" ".claude"
```

## 2. Start Claude Code in the folder

1. Open a new Claude Code session on `C:\Users\stewa\Documents\Claude\sensor-forensics`.
2. Accept the folder trust prompt.
3. For planning: `/model opus`, then `/effort max`.
4. Switch to plan mode (Shift+Tab).

## 3. Paste this prompt

```
You are taking over a new project from a handoff package: the Sensor Forensics Lab, a forensic reconstruction of the Navy GIMBAL, GOFAST, and FLIR1 videos and the 2026 PURSUE sensor videos. Read CLAUDE.md and follow its boot order, starting with AUTONOMY.md.

The rule that governs everything: this is a hypothesis-testing lab. Every explanation, mundane or anomalous, is run through the same geometry and physics and scored against the same frame-by-frame evidence. Where the public data can't decide between explanations, the lab must say so and show exactly which missing measurement would decide it. Reproduce the existing published analyses first (Mick West's open-source Sitrec models, and the 2023 GIMBAL flight path paper by Graves and colleagues), so we know where and why they disagree.

Start with a data audit at M0: for each video, list exactly which quantities are readable on screen frame by frame, which are inferred, and which are unknown. Then produce the execution plan for M0 through M6 in _PLAN.md. For each milestone give the work items in order, which ones you will delegate to the worker subagent, what runs in the background, how you will prove each acceptance criterion, and the top risks with a fallback for each. List any gaps you see in SPEC.md or ENGINE.md and the default you will use for each.

When I approve the plan, execute autonomously per AUTONOMY.md: post a checkpoint message at every CP, keep going without waiting for my replies, log questions with defaults in QUESTIONS.md, and stop only for a true blocker. Start with M0.
```

## 4. Approve and let it run

1. Approve with the auto mode (or auto-accept edits) option, then `/effort high`.
2. Optional `/goal`:
   ```
   /goal Every milestone M0 through M6 in _PLAN.md is marked [x] with its checkpoint file written, or BLOCKED.md describes a true blocker and no unblocked work remains
   ```
