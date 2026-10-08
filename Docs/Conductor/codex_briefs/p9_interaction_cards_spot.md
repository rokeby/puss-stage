# P9: Interaction transitions: remove the white shadow cards, slow shadow-play spot (final jobs 1.9a/1.9b, 2.4, 2.10, 3.5, 3.9)
Read:
- Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md (rows 1.9, 1.9a, 1.9b);
- Docs/Conductor/SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md;
- the tools that made the cards and the spot: grep Saved/ for curtain_sleight.py and shadow_play_spot.py.
Gary's pattern: we go into darkness, a spotlight SLOWLY discovers a curtain that is already there, the shadow-puppet gobo plays ON that curtain, then the light dims and the curtain switch is made.
Build ONE tool (DRY/APPLY/REVERT, args per Interaction I1..I5) that:
- (a) removes each Interaction's "Sleight Mouth/Hangar Shadow Card" (two 480x270 cards per Interaction; Gary already removed the I4 hangar card on 7 Oct). It must handle a card that is already missing.
- (b) brings a "Shadow Play Spot" onto each Interaction's curtain, replicating I4's spot (7483 cd, cast shadows; read its transform relative to its curtain from the tool or record that made it). Reference Interaction is an arg with default I4.
- (c) replaces the 0.5 s snap-up (plan: frames 175-187) with a slow fade. Fade seconds is an arg, default 4.0, Gary's to set.
- (d) leaves a light-function slot ready for the animated gobo (Saved/CodexConductor/animated_gobo.py from P6, which is in another worktree; read Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md if present, else just expose the property).
The Show asset is the authority for cues and attachments (AGENTS.md). Determine whether cards and spot live in the Show, the level or a sequence, and write through the right owner. Census exact; record + backup. Harness with negative and positive controls.
