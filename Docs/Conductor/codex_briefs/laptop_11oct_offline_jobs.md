# Laptop Codex jobs, 11–12 Oct: OFFLINE ONLY (the PC is travelling)

**Read first:**
- `Docs/Conductor/codex_briefs/_house_rules.md`;
- `Docs/Conductor/HANDOVER_2026-10-10_CONDUCTOR5_EVENING.md` (the "11 Oct, PC pack-down" section);
- the Job 196 to 198 sections of `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md`.

**Hard limits:**
- No Unreal, no MCP, no build, and no Content (it is not in git).
- Deliver live-ready tools: DRY by default, an exact-confirm APPLY, REVERT, backups, read-back, run-id markers, an offline harness with +/- controls, and `Scripts/ue58_api_preflight.py` clean.
- Each job writes `Docs/Conductor/JOB<N>_REPORT_2026-10-12.md` with per-claim tiers (declaration-proven / measured / inferred) and `file:line`.
- Never plan a save under `/Game/InfinityStage/KlaraHookin/`.
- Commit on a branch named `laptop/<job>`. The conductor merges it when the PC is back.

## L1: seam fixes from the job 196 audit
**Inputs:** `Saved/CodexConductor/Job191TransitionAudit_20261011/`, where the seam-audit results (`seam_audit_result.json`) and the runner are. Gary's priority is transitions and rehearsal.

Build one tool per fault, each a narrow change at its seam:
- **06 I2->P3:** a 2,195 cm camera jump with picture on screen. Either hide it inside a cut through black (a Fade track spanning the seam, at about 0.5 s) or match the P3 entry camera to the I2 exit pose. DRY reports both options. The default is the black cut.
- **12 I4 -> Nap Interlude -> P5:** a 3.2 km / 41.5° jump. First find out whether the Interlude legitimately teleports (the camera handover facts are in the memory docs: nested shot cuts outrank the root, and bindings must resolve). Then cover it with a black cut or fix the binding.
- **14 S5->I5:** a 727 cm / 86° jump, with black at +1 frame and +1 s. Probably a cut that is already covered; verify from the samples, and only extend the black if it is visible.
- **15 I5->P6:** a luminance pop (mean delta 108; I5 is over-bright). Propose an I5 exposure correction, or a short exposure ramp across the seam. Look values are PROPOSALS for Gary.

## L2: S6 move-in (no cut)
From job 198b's DRY: plan a P06 push that ENDS exactly at the nested `CineCameraActor5`'s first-frame pose, read from the job 198 record. Never edit that camera. Deliver the plan, a preview SVG of the path and the tool ready for APPLY.

## L3: interaction relength
Gary: lengths follow the script pace, about 60 s or less (beat table in `Docs/Conductor/SHADOW_SHOTLIST_INTERACTIONS_2026-10-11.md`). Prepare a DRY/APPLY tool that relengthens `LS_Interaction_01..05` and ripples the Master after them (Passage keys are absolute; see `Docs` memories on ripple). Target lengths come from an args JSON.
