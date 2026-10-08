# Codex team brief — Conductor 5, 8 Oct 2026

Gary (8 Oct ~02:55 UTC): "soon it will be time to run all this work through codex again, get ready to efficiently
manage a team of agents there". This is the dispatch sheet: house rules every agent gets verbatim, then the work
packages, each with what goes in the brief.

Launcher: `Scripts/codex.sh` (read-only default; `--worktree` for code; `--unreal` only with an editor slot from the
conductor; `--build` only in a build window). Final messages land in a file whose path is printed. Never pipe it
through `head`/`tail` (it buffers and looks hung).

## House rules (paste into every brief)

1. **Worktrees only for code** (`--worktree`). Never write the main tree `E:\PussStage`; the conductor reviews,
   copies and commits. Never `git stash`, never `git commit -a`.
2. **No editor unless the brief grants a slot.** With `--unreal`: if PIE is running, STOP and report. Never end PIE,
   never run stop/quit/relaunch scripts, never close or restart the editor; a "PIE check" only READS the log
   (memory codex-unreal-must-not-end-pie). One editor writer at a time; the conductor hands out slots.
3. **Tool shape.** DRY → APPLY (confirm string) → REVERT. Record + `Backups/Pre<Thing>-<run>` BEFORE any change.
   Exact dirty-package census before and after; save only the named packages, never Save All. Read back, then save,
   then read back again. The success marker comes only after the asserted read-back, and carries a run id.
4. **UE 5.8 traps** (each has bitten us): never delete nodes on existing materials (editor crash); values read in the
   same call as an import or build lie, so verify in a later call; `get_marked_frames` returns a sorted copy, so
   delete by `find_marked_frame_by_label`; float channel read-back needs ~1e-4 tolerance; set_collision_enabled
   alone doesn't persist; in PIE use `unreal.load_asset`, not EditorAssetLibrary; no deferred spawn in PIE Python.
5. **Harness first.** Every tool ships with an offline harness that has negative AND positive controls, and seeded
   mutations it must catch. Report pass counts.
6. **Mark uncertainty per claim:** declaration-proven / binary-proven / measured / inferred, with `file:line`.
   Unmarked reports are rejected.
7. **Look/creative values are Gary's.** Defaults go in args; nothing look-changing is applied without his yes.
9. **Editor sky stays hidden** (Gary, standing rule): after any editor restart run
   `Saved/CodexConductor/editor_sky_toggle.py` (hide=true, transient, saves nothing). Leave the editor that way.
8. **Kill your process tree on stop** (codex.exe outlives its wrapper; memory codex-orphan-processes).

## Work packages (ready to brief)

| # | Package | Mode | Inputs / reference | Done when |
|---|---|---|---|---|
| 1 | **S3 dunes ×2** (peaks ~4.8 m, reach 6–8 m, centre lane and millstone clear) | worktree, then conductor imports | `Saved/CodexConductor/S3Shore/s3_shore_field.py` height_sets (add set D), `s3_shore_blender_build.py` (headless `blender -b`, one at a time — memory blender-bake-memory-headless), test_s3_shore_offline (79/79) | set D field + gate pass + overview stills; **harvest Gary's hand-painted wet patches** (vertex G on SM_S3_ShoreGround_B) into real pool dips first; new print line for the grease prints |
| 2 | **S3 wave flats thicker + spaced** (~5 cm like V3) | worktree | `S3Waves/s3_waves_v3_core.py` (135/135), FlatV3Spec | new FBXs + MIs pass re-import validation; motion keys still clear |
| 3 | **Fixtures: parcans 3×, bulbs 2×, glowing filament + dim light, per-passage placement proposals** | worktree + stills slot | `FixturesFollow/` (46/46), Docs/Conductor/FIXTURES_FOLLOW_SCALE_BULBS_2026-10-07.md | overhead stills per passage for Gary to approve |
| 4 | **Glimmer lamps → bare bulb on a cord off a wing, gentle deterministic sway** | worktree | scores_glimmer_config.py; wing mechanisms freeze outside their Passage (memory) | which wings move, per passage; cords clear of the camera path |
| 5 | **Standing stones ×3, half-buried** | worktree | `S3Shore/standing_stones_proposal.json`, `S3Millstone/s3_props_ue.py` (needs lean support + a relaxed buried-stone guard) | props tool mode + harness |
| 6 | **Cloth: "wearing a carpet" + collision show-through + hessians must be pinned to the back (they flip onto the head)** (Gary) | read-only investigation | Docs/ChaosClothCurtain.md, the figures' cloth assets | ranked causes with tiers; no edits |
| 7 | **Figure animation intensity per shot without breaking cloth** (Gary wants to tune it himself) | read-only research | LS_Clams skeletal sections (play rate, offsets, weights) | a 1-page how-to for Gary, tested on one figure in a duplicate sequence |
| 8 | **S4 entry v5 / scene-exit shadow curtain** | worktree | S4_ENTRY_*_2026-10-07.md, SCENE_EXIT_SHADOW_CURTAIN_PLAN | preview stills before apply (Gary) |
| 9 | **Klara wings → V3** (not now) | read-only | KLARA_WINGS_V3_FEASIBILITY_2026-10-07.md | — |

**Stays with Claude sessions** (editor, timing-critical or mid-flight):
- MRQ video fallbacks: S5 test tonight, then the six scenes; due Sun 11 Oct.
- S3 shot and keyframe work with Gary.
- The pearl fade twin (finishing touches).
- Grease tint (built, held by Gary).
- Tests and commits.

## Dispatch plan

- Run 3–4 agents at a time: packages 1, 2, 3, 6 first (offline, independent files). Two of them need Blender, and
  only one may run Blender at a time (memory pressure).
- The conductor reviews every draft: run its harness, read the design, copy it into the main tree, commit by path.
- Editor slots for `--unreal` steps are granted one at a time, logged in the conductor log with a run-id window.
