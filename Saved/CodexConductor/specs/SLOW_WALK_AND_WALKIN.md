# Slow walk P02-P04 to 3:00 + key the Opening->P01 walk-in (Gary, 2 Oct night, his own answers in the Conductor 4 session:
# "Slow the walk"; walk-in "Yes, key it"). Rules: PIE off + census clean first (never end PIE), never quit, never Save All,
# purge cached Saved/ modules, MCP envelope from Saved/CodexConductor/quit_request.json, markers by run id. Stop on failure.
## PART 1: tool Saved/CodexConductor/passage_slow_walk.py (DRY/APPLY/REVERT, one passage per run) + offline harness
For the WingPair cues of one passage (by passage label, identity by cue index+GUID read fresh): k = 180.000 / current duration
(duration = LeadInFrames + sum(IntervalToNext of all but the last pair) + TailFrames; InfinityStageCompiler.cpp:240-312).
Scale LeadInFrames, every IntervalToNext and TailFrames by k in ticks (round each), then put the total rounding residual into
TailFrames so the compiled duration is EXACTLY 180.000 s. Distances (LeadInDistanceCm, GapToNextCm, TailDistanceCm), count,
GUIDs, meshes and override bits stay UNCHANGED (assert). Report speed old -> new (cm/s) and k.
DRY: the plan + the Master range delta + every downstream section's shift. APPLY: backup Show + Master + level to
Backups/PreSlowWalk-<P>-<stamp>; Modify; set the fields; materialize ONLY that passage; rebuild the managed Master (the same
call the Cue Desk uses; patch K carries downstream keys); rematch the following Scene's handoff
(Saved/CodexSoftGoods/extend_scene_playback.py rematch_only for that Scene); targeted saves (Show, Master, level only);
read back duration == 180.000 and distances unchanged; then SavedMasterMatchesShow and SceneCutBindingsResolve singly.
Harness offline: + 47.431 s -> 180.000 exact with distances unchanged; - a distance change fails; - a count change fails.
Order: P02, then P03, then P04, each DRY then APPLY. Landed-preview STATUS at the end (all six UP).
## PART 2: Opening -> P01 walk-in
Saved/CodexCameraPilot: fill the OPENING entry of walkin_transitions.json from Saved/CodexConductor/opening_walkin_probe.json
(measured: sequence LS_Opening_Curtain_Baked [0,375] @25 fps; stalls camera 'Opening — Stalls Camera' (-1400,0,150), pitch 14,
15 mm; curtain landed_s 6.3267; pile route extent [-203,467] cm; P01 start 15.0 s at (0,0,150), 25 mm, focus 600, 2.5 m/s).
Run the generalised key script for OPENING: DRY (report the planned keys), then APPLY with its own backup/record/revert;
read back; then SavedMasterMatchesShow and SceneCutBindingsResolve singly. If the key script needs a field the probe didn't
measure, STOP and report it (never guess).
FINAL MESSAGE: per passage k, old/new speed, markers, backups; the walk-in key table; censuses; tags per AGENTS.md.
Commit the new tool + harness only if every step passed (conductor-owned files under Saved/CodexConductor), else nothing.
