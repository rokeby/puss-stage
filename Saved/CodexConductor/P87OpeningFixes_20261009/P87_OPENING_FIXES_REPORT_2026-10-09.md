# P87 Opening fixes — offline delivery report

Date: 9 October 2026  
Scope: tools, harness, previews and report only; no Unreal, MCP, PIE or Blender.

## Outcome

- **measured:** The offline harness passes 45/45 checks (17 negative, 28
  positive). It exercises clock refusal, confirm strings, dirty-state refusal,
  foreign-record refusal, one-fall planning, exact camera end pose, zero new
  shadow casters, deterministic single-draw bulb scatter, backup-before-write,
  active-record refusal, drift refusal, APPLY/read-back and REVERT/read-back.
  Evidence: `test_p87_opening.py:121-199`; terminal result recorded below.
- **measured:** All six Python files compile under the system Python, and the
  PIL preview generator wrote both PNGs. Evidence: `p87_preview.py:1-87` and
  `DerivedAssets/P87OpeningFixes/p87_timeline.png` / `p87_stage_front.png`.
- **inferred:** The Unreal adapter is ready for conductor DRY, but none of its
  UE calls or mutations is live-proven because this brief explicitly forbids
  Unreal. Evidence: `p87_unreal_adapter.py:296-425`.
- **inferred:** Rendered composition, light levels, camera framing and floor
  contact remain Gary's acceptance; offline plans and PNG diagrams do not prove
  the look. Evidence: `p87_opening_args.json:1-26`.
- **measured:** The requested worktree commit could not be created: Git was
  unable to create `E:/PussStage/.git/worktrees/PussStage23/index.lock` because
  this managed worktree has read-only access to the shared git metadata. The
  delivered files therefore remain uncommitted in this worktree; no main-tree
  file was written and no existing change was staged.

## De-duplication

- **measured:** P31 has a brief and commit `5ab1b93a`, but no
  `prelude_camera_move.py` was found in this worktree, so P87 supplies the
  camera implementation. Evidence: `dedupe_inventory.json:3-8`.
- **measured:** Q17 already owns the ragged curtain asset/material swap. P87
  changes Geometry Cache section timing only and does not replace that asset.
  Evidence: `dedupe_inventory.json:9-14`.
- **declaration-proven:** P13 already declares the first flurry at 37.44 s,
  curtain flurry index 1, six facade PAR slots and the ParCan mesh. P87 reuses
  P13 `_gc`, `_set_gc`, `_mint` and Show-attachment helpers instead of creating
  a second transport. Evidence: `opening_lighting_p13.py:54-55,111-112,799,899-919`.
- **measured:** Job 35's ADD_UPLIGHTS path is P02-P06 wing-foot infrastructure,
  while P87's six lights are a distinct Opening stage-front subset; P87 moves
  existing P01 bulb rows rather than adding duplicate bulbs. Evidence:
  `dedupe_inventory.json:20-30`; `P01FloorPracticals_20261008/p01_floor.py:2-40`.

## The four fixes

1. **declaration-proven:** Gary asks for one curtain fall at the first flurry and
   a hold thereafter. Evidence: `Docs/Conductor/codex_briefs/p87_opening_fixes.md:11-14`.
   **measured:** The pure plan emits exactly HOLD/FALL/PILE_HOLD, reports one
   fall, and records displaced live falls for reversible recovery. Evidence:
   `p87_opening_common.py:200-221` and harness checks 12-14.

2. **declaration-proven:** Gary asks for a wide full-stage hold followed by a
   very slow move ending on the existing Passage pose. Evidence:
   `Docs/Conductor/codex_briefs/p87_opening_fixes.md:15-18`.
   **measured:** The planner holds to the pinned fall, uses a per-frame
   smootherstep, and copies the live final pose exactly at frame 2409. Evidence:
   `p87_opening_common.py:173-197` and harness checks 15-17.
   **inferred:** `x=-2400 cm, z=150 cm, pitch=9 degrees, 15 mm` should fit the
   proscenium; it is the P31 proposal and still requires a live bounds report
   and rendered still. Evidence: `p87_opening_args.json:7-13`.

3. **declaration-proven:** Gary asks for stage-front uplights after the flashes.
   Evidence: `Docs/Conductor/codex_briefs/p87_opening_fixes.md:19-21`.
   **measured:** The plan makes six 3200 K / 350 lm args-driven ParCan rows,
   keys them from zero after the pinned flurry, and adds zero shadow casters.
   Evidence: `p87_opening_common.py:224-243`; harness checks 18-21.
   **inferred:** The count, temperature and intensity are look proposals, not
   approved values. Evidence: `p87_opening_args.json:15-18`.

4. **declaration-proven:** Gary asks for less orderly bulbs, on the ground in
   front of wings and not intersecting them. Evidence:
   `Docs/Conductor/codex_briefs/p87_opening_fixes.md:22-24`.
   **measured:** Each bulb uses one stable hash draw per front distance,
   lateral offset, yaw, pitch and roll; changing yaw range does not move bulbs.
   The plan enforces wing clearance and requests an `ECC_CAT_FLOOR` live trace.
   Evidence: `p87_opening_common.py:246-274`; harness checks 22-26.
   **inferred:** Actual floor hits and non-intersection are pending live DRY/APPLY
   read-back. Evidence: `p87_unreal_adapter.py:335-358`.

## Clock verdict and safety

- **declaration-proven:** The saved Opening table declares 25 fps and a 2,409
  frame end. Evidence: `Saved/CodexConductor/opening_timing.json:5,48-51` and
  `Saved/CodexConductor/opening_sequence_record.json:12129-12131`.
- **UNCLEAR:** Gary's `00:37:50` cannot be accepted as whole-frame
  `HH:MM:SS:FF` at 25 fps because frame 50 is invalid; it may be a Master clock,
  a decimal/subframe display, or shorthand for 37.50 seconds. P13's earlier
  first-flurry proposal is 37.44 seconds, but that does not prove Gary's clock.
  Evidence searched: `p87_opening_fixes.md:11-13`,
  `opening_lighting_p13.py:54-55`, `opening_timing.json:5`.
- **measured:** APPLY is mechanically refused while `first_flurry_frame` is
  null. Evidence: `p87_opening_common.py:124-130`; harness negative control 5.
- **declaration-proven:** Show attachments have minted `AttachmentGuid` identity
  and `RelativeTransform`; custom sequence binding resolves attachment tags.
  Evidence: `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:440,467`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageAttachmentBinding.h:26-41`.
- **measured:** The transaction writes a verified backup and exclusive record
  before mutation, saves only Show/Opening sequence/level, reads back, requires
  zero dirty packages, and REVERT refuses drift. Evidence:
  `p87_opening_fixes.py:89-117,127-151`; harness checks 33-45.

## Commands

```powershell
python Saved/CodexConductor/P87OpeningFixes_20261009/test_p87_opening.py
python Saved/CodexConductor/P87OpeningFixes_20261009/p87_preview.py
```

Live order is in `README.md:19-42`. Do not skip the first unresolved-clock DRY.

## Open questions for Gary / conductor

1. Which displayed clock produced `00:37:50`, and what exact Opening-local frame
   does it resolve to?
2. Are the proposed 6 x 3200 K / 350 lm shadowless uplights the right starting
   grandeur, or should count/temperature/level change before APPLY?
3. After the live bounds report, does the P31 wide pose frame the full stage
   without revealing house walls, Wash C or the floor edge?

Harness result: `P87_HARNESS_RESULT|pass=45|fail=0|total=45|negative=17|positive=28`
