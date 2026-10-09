# P60 — fix job 34 (I2 sleight move-in) live refusal MOUTH_COMPONENT_OBJECT_GUID (Codex, offline)

Read `_house_rules.md`; all rules apply (worktree, offline only, harness -/+, proof tiers, <700 words).

Live DRY refused 9 Oct ~09:29 UTC (run 51C-I2MOVEIN-DRY2-20261009-0533, `E:/PussStage/Saved/Logs/PussStage.log`,
grep MOUTH_COMPONENT): `Saved/CodexConductor/I2SleightMoveIn_20261009/i2_sleight_move_in.py:866-868` resolves the
mouth camera component's binding GUID via `_binding_object_guid` and it no longer equals MOUTH_COMPONENT_GUID
`A4162B8C4B7F601B6D73BF97DB42FD91`. Just before, job 24 (I2 shrink, −276 frames) was applied to
`/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips` (find its tool/record under
E:/PussStage/Saved/CodexConductor or Saved/CodexSoftGoods — grep "I2" + "shrink"/"extend_scene_playback").

Do:
1. Determine (cite file:line) why the guard fails: did job 24 rebind/re-create the CameraComponent child binding, or is
   `_binding_object_guid` the wrong lookup (e.g. a find-binding-by-object API that needs a world/context, returns a
   proxy whose id differs, or matches the parent actor)? Mark proven vs inferred; if UNCLEAR, add a read-only
   diagnostic phase (PROBE) that logs every binding under the mouth camera actor binding E6CF6346... (name, guid,
   parent, bound object path) so the next live run settles it.
2. Fix robustly: resolve the mouth component binding by the parent binding (E6CF6346…) + child whose tracks include
   CurrentFocalLength/ManualFocusDistance, then assert it binds the mouth camera's CineCameraComponent. Keep every
   other guard. The cut at 1250 must ALSO be re-derived: after a −276 shrink, check whether the cut frame moved
   (read it, don't assume 1250); make the cut frame an arg defaulting to "LIVE" (read from the cut track) with a
   guard that the hangar/mouth cut boundary exists exactly once.
3. Update the harness: positive (shifted child GUID, shrunk sequence) + negatives; rerun all existing controls.
Deliver changes in the same folder; README note on what changed.
