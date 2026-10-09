# Job 90b - I2 reference reconciliation and I3 darkness

This bundle is offline-authored. It has not run in Unreal and is not rendered
acceptance.

`preview_timeline.svg` is the analytical intent preview; it is not a scene
still and does not establish the look.

## Conductor order

1. Stop PIE/SIE, close Sequencer, load the vertical-slice world, and require an
   empty full dirty-package census.
2. Set a unique run id and run `DRY` with confirmation
   `DRY INTERACTION90B`. Require `INTERACTION_90B_DRY_OK`, `mutated=0`, and
   `dirty=0`.
3. Inspect the DRY report. It must show I2's cut pose held until `CST drop`,
   opposite signed curtain-plane distances, and the last transform key exactly
   equal to the live P03 start pose returned by `get_passage_camera_pose`.
4. Inspect S3/I3: S3 reaches full black on its final displayed frame; I3 holds
   blackout at 1.0 from frame 0 through camera settle, the camera has non-zero
   travel, then blackout clears while both shadow spots fade to I2's live
   reference intensities. Curtain sections, cuts, playback end, and the
   mouth-camera end are not mutation targets.
5. Inspect all five lighting audit rows. Each contains the authored twin-shadow
   comparison plus job-39 F17's live world/spawned-light, PP exposure and fog
   census, ranked differences, and proposals. For every reported pop, copy the
   smallest explicit `PPV_WEIGHT`, `LIGHT_HIDE`, `LIGHT_DIM`, or `ACTOR_HIDE`
   fix into `lighting_fix_steps`; re-run DRY. Visibility values are visible
   booleans and bind `bHidden`, never `bHiddenInGame`.
6. Change only mode, confirmation, and run id to APPLY. Require
   `INTERACTION_90B_APPLY_OK`, the exact named save list, record path, backup,
   and `dirty=0`.
7. Run `InfinityStage.Editor.SceneCutBindingsResolve` and
   `InfinityStage.Editor.SavedMasterMatchesShow` separately.
8. Capture still pairs for every audited cut at `cut-1`, `cut`, `cut+1`; I2 at
   drop-1/drop/drop+1, mid-travel, end-1/end; S3 at end-26/end-1; I3 at frame 0,
   mid-move, settle, spot-start, spot-end. Then run a foreground PIE take. Gary judges
   total darkness, framing, the through-curtain move, and lighting continuity.

REVERT uses `REVERT INTERACTION90B`, takes a new
`Backups/PreInteraction90bRevert-<run>`, drift-checks owned channels/tracks,
restores them, saves only the recorded packages, and archives the record.

## Proof tiers

- **declaration-proven:** the tool targets only S3/I2/I3 owned fade/channels plus
  explicit F17-style steps; saves are the computed package set; GUIDs use
  `GuidLibrary.conv_guid_to_string`; enum and channel suffixes are normalised
  (`interaction_90b.py`).
- **measured-offline:** `test_interaction_90b.py` exercises positive planning,
  negative controls, confirmation, state drift, and DRY/APPLY/REVERT dispatch.
- **inferred:** a black fade guarantees black output and the analytical
  curtain-plane sign change represents a visible plane crossing.
- **UNCLEAR until live DRY/render:** current engine-minted bindings, exact cut
  frames, which interactions have non-shadow-light/exposure/fog pops, saved
  read-back, and the visual result.
