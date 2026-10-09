# P34 — I2 sleight move-in

Offline-authored bundle. It adds a sampled cubic push-in to the **existing** I2
hangar-camera binding, matches the mouth camera at frame 1250, and (by default)
eases the mouth camera back to its recorded hold pose over 6 seconds. It does
not move the cut and does not touch either gobo spot or the MPC track.

## P60 binding/cut repair (9 October)

- **declaration-proven** - the shrink tool enumerates the sequence's existing
  bindings, then changes only section end/active state; it contains no camera
  rebind path (`E:/PussStage/Saved/CodexSoftGoods/shrink_scene_playback.py:274-278,467-475`).
- **measured** - the live shrink record retains child binding
  `A4162B8C4B7F601B6D73BF97DB42FD91` and trims its two float sections to 1950;
  the camera cut remains 1250 while playback ends at 1950
  (`E:/PussStage/Saved/CodexSoftGoods/shrink_scene_playback_apply_51C-I2SHRINK-APPLY-20261009-0530.json:1-27,2082-2145`).
- **measured** - the first live move-in attempt failed because `LevelSequence`
  has no `find_binding_from_object`; the replacement world-context scan then
  refused the component GUID (`E:/PussStage/Saved/Logs/PussStage.log:3028-3041,3089-3100`).
- **inferred** - the world was the wrong resolution context for the child
  component binding. The repair selects the unique child of mouth actor binding
  `E6CF...` whose tracks contain `CurrentFocalLength` and
  `ManualFocusDistance`, then resolves that child against the parent camera
  actor and asserts the resulting object path is the actual
  `CineCameraComponent`. `PROBE` records both parent-actor and world-context
  results so the conductor can verify that inference live without mutation.

The component GUID is therefore live-derived rather than fixed. The cut is also
an argument defaulting to `"LIVE"`: DRY reads the unique hangar/mouth boundary
from the active camera-cut track, verifies that the two cuts cover the current
playback range exactly once, and plans against the shortened live endpoint.

## Proof boundary

The P34 references to a fixed component GUID and fixed live playback baseline
are superseded by the P60 live-derived component/cut contract above.

- **declaration-proven** — save scope, fixed GUIDs, frame 1250, defaults,
  confirmation strings, backup name and preview frames are specified by
  `Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:1-50`.
- **measured-upstream** — DRY re-reads and hashes the three absolute-path JSONs
  under `E:/PussStage/Saved/CodexConductor/` named in the brief. Those records
  provide the saved camera baseline and drape bounds; this offline bundle does
  not re-measure Unreal.
- **measured-offline** — `harness_result.json` records the fake-Unreal positive
  round trip and negative controls. This is tool behavior, not a saved-asset or
  rendered result.
- **inferred** — `preview_plan` and `preview_coverage` (SVG plus offline PNG
  convenience copies) analytically predict camera paths and edge coverage.
  They are not scene renders. Gary's rendered acceptance remains open.

## Files

`i2_sleight_move_in.py` now also exposes read-only `PROBE`; DRY/APPLY/REVERT
retain their original confirmation, backup, census, save and read-back contract.

- `i2_sleight_move_in.py` — DRY/APPLY/REVERT tool.
- `i2_sleight_move_in_args.json` — Gary's tunable values and read-only evidence
  paths.
- `i2_sleight_move_in_run.py` / `i2_sleight_move_in_request.json` — guarded
  project-Python transport.
- `make_previews.py` — offline SVG regeneration.
- `test_i2_sleight_move_in.py` — fake-Unreal harness.

## Conductor run order

1. With Unreal clean and untouched, set a unique run id and run `PROBE` with
   `confirm: "PROBE I2MOVEIN"`. Require `I2_MOVE_IN_PROBE_OK`; inspect every
   child row and require the track-selected child to resolve to the expected
   mouth `CineCameraComponent` under parent-actor context. PROBE writes only a
   JSON diagnostic under this folder and dirties no package.
2. Review the args and the two SVG previews. Regenerate them offline with
   `python make_previews.py` after any value change.
3. Ensure PIE/SIE is stopped, Sequencer is closed, the vertical-slice world is
   current, and the full dirty census is empty. Set a unique run id and run
   `DRY` with `confirm: "DRY I2MOVEIN"`. Require
   `I2_MOVE_IN_DRY_OK|run=<id>` and inspect the DRY JSON. Confirm `cut_source`
   is `LIVE`, `cut_frame` is the measured boundary, and `playback` is current.
4. With no intervening I2 edit, change only mode, confirm and run id to `APPLY`,
   `APPLY I2MOVEIN`, and a fresh id. Send the same request. Require
   `I2_MOVE_IN_APPLY_OK|run=<id>`. APPLY creates
   `Backups/PreI2MoveIn-<run>`, saves only
   `/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips`, and records a
   clean post-save read-back of every key.
5. Run focused editor checks singly:
   `InfinityStage.Editor.SceneCutBindingsResolve`, then
   `InfinityStage.Editor.SavedMasterMatchesShow`.
6. In the conductor-owned visual slot, capture frames
   1150/1200/1249/1250/1300/1400 and have Gary judge the movement and the cut.
   No offline result is visual acceptance.

## Revert

With a clean editor and no intervening I2 change, use a fresh run id plus
`mode: "REVERT"` and `confirm: "REVERT I2MOVEIN"`. Require
`I2_MOVE_IN_REVERT_OK|run=<id>`. REVERT makes its own
`Backups/PreI2MoveIn-<run>`, restores the exact pre-APPLY snapshot, saves only
the named sequence, and archives the apply record.
