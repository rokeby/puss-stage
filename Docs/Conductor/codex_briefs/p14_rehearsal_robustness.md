# P14: Rehearsal robustness: cue desk, transport, show-run tools (Gary 8 Oct: "deep priority")
First rehearsal Tue 13 Oct, show Sat 17 Oct. Gary's priorities: the content of the show, the CUE DESK, the robustness of the rehearsal tools, and the robustness of transitions.
Known failures to start from:
- **Vamp end → S3 end jump**: Docs/Conductor/codex_briefs/p2_vamp_bug.md and Scripts/patches/2026-10-08_vamp_end_jump.patch (held).
- **Performance mode refuses scrubs** inside DeclaredUnpausable external-sound segments (UNSAFE_EXTERNAL_CLOCK). Gary "can't fast-forward" in S3.
- **result=4 = performance interlock refusal** (memory notes in Docs).
- **Play-only vanishing** from sub-section completion modes (fixed in S3 with KEEP_STATE; other Scenes NOT checked).
Job (offline, source + data reads only):
1. Read the cue desk (find it: grep Plugins/InfinityStage for CueDesk / transport controller / operator UI) and the transport controller. List every operator action, its preconditions, and every way it can refuse or misbehave mid-show: jumps, GO, hold, vamp, release, external sound, PIE restart, a crash mid-scene. For each, give the recovery path an operator would use.
2. Scan all six LS_DevScene_0N and the Master offline (.uasset bytes or existing census/probe JSONs under Saved/) for the S3 class of bug: sub-sections and visibility/spawn sections with PROJECT_DEFAULT/RESTORE_STATE completion that end mid-scene. Produce a list per Scene.
3. Write C++ fixes for anything clear-cut as HELD patches in Scripts/patches/2026-10-08_<name>.patch, each with an automation test. Write Python DRY/APPLY tools for data fixes (e.g. a KEEP_STATE pass for other Scenes).
4. A rehearsal runbook for the operator: Docs/Conductor/REHEARSAL_OPERATOR_RUNBOOK_2026-10-08.md, one page, with a failure table.
Deliver Docs/Conductor/P14_REHEARSAL_ROBUSTNESS_2026-10-08.md.
