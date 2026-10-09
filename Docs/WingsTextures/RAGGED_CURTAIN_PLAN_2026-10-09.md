# Ragged held curtain: Opening plan and P02/P03 image feasibility

**[measured]** Job 76 / W&T Q17 was offline analysis and tooling only; nothing in Unreal or Blender was run.

## Evidence boundary

- **[measured]** Job 74 imported `/Game/Scenes/Curtain/Baked/GC_CurtainDrop_RaggedProscenium_P02Held` as one 631-sample, 30 fps Geometry Cache covering source frames 450..1080; its hang and last-frame bounds passed the import axis check, it uses `MI_CurtainVelvet_DeepRed_Drop`, and it was not placed or hooked (`Saved/CodexSoftGoods/q16/job74_record.json:4-23`, `:25-34`; git commit `114af306`).
- **[measured]** The held artifact releases at 480, lands at 665, blends by smootherstep over 665..695, and then presents the chosen held pose; its exported Alembic read-back error is 0 at 450, 665, 695 and 1080 (`Saved/CodexSoftGoods/DropBake/ragged_proscenium_p02_held.json:13-21`, `:57-65`, `:2446-2458`).
- **[measured]** The source and output mesh signatures each contain one corner-domain `UVMap`; this proves the UV layer survived the Q13 Alembic export/read-back (`Saved/CodexSoftGoods/DropBake/ragged_prep/Q13_BLENDER_EXPORT.json:7-14`, `:42-45`, `:51-58`, `:85-89`, `:95-107`).
- **[UNCLEAR]** Job 74's Unreal import record reads back frame range, sample count, bounds, material and axis failures, but does not count Unreal UV channels (`Saved/CodexSoftGoods/q16/job74_record.json:14-23`). Therefore Unreal-side UV survival was not independently measured in Q16. The P02/P03 verdict below does not depend on UV0 because their current image material defaults to local planar mapping.

## A. Opening

### What plays now

- **[declaration-proven]** The Opening sequence is `/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked`; it owns a spawnable `GeometryCacheActor` named `Opening Drape (baked)` at identity, with one spawn track and one Geometry Cache track split into HOLD, FALL and PILE (`Saved/CodexSoftGoods/curtain_place_opening_and_transitions.py:32-38`, `:98-148`).
- **[measured]** A saved probe found that exact actor template and the two track classes, with its component referencing `GC_CurtainDrop_Opening` (`Saved/CodexSoftGoods/inspect_opening_template.json:3-20`).
- **[measured]** The current final13 schedule is HOLD `[0,49)` at offset 23200, FALL `[49,299)` at offset 23200, and PILE `[299,375)` at offset 263999; the release is display frame 50 (`Saved/CodexSoftGoods/opening_hold_at_release_final13.json:27-47`, `:50-70`).
- **[measured]** A referencer probe recorded the Show cue `Opening — Curtain` pointing to that sequence and recorded five separate Interaction sequences with old-cache Geometry Cache sections (`Saved/CodexSoftGoods/probe_opening_cache_provenance.json:11-50`, `:52-79`, `:81-108`, `:110-137`, `:139-166`, `:168-196`).
- **[declaration-proven]** `import_passing_bake.py` describes `plan.release_in_cache_s` as a seconds-from-first-sample cross-stream contract (`Saved/CodexSoftGoods/import_passing_bake.py:23-25`) and derives it from `(release_frame - first) / 30` (`:189-196`).
- **[measured]** Both old final13 and the new held cache have `release_in_cache_s = 1.0`; old final13 covers 450..780 (`Saved/CodexSoftGoods/import_passing_bake_final13.json:185-199`) and the new cache covers 450..1080 (`Saved/CodexSoftGoods/import_passing_bake.json:86-89`, `:205-227`).

### Timing conclusion

- **[inferred]** Keep every current section range and offset. The FALL is 250 display frames at 25 fps = 10 s. Its 23200/24000 s start offset samples source frame 479; the shared 1.0 s release therefore still lands on display frame 50. At the FALL end the longer cache is around source frame 779/780, already frozen after the 665..695 blend. The existing PILE offset 263999 ticks also samples that frozen region. Changing timing would add risk without changing the held image.
- **[inferred]** The new cache is 21 s long, versus the 15 s Opening sequence, but that does not truncate visible motion: release-to-land is about 6.17 s and release-to-held is about 7.17 s, both inside the 10 s FALL window.
- **[declaration-proven]** The target cache already carries `MI_CurtainVelvet_DeepRed_Drop`, the same material name used by final13 (`Saved/CodexSoftGoods/q16/job74_record.json:9-12`; `Saved/CodexSoftGoods/import_passing_bake_final13.json:189-195`). No material edit belongs in this swap.

### Recommendation and prepared tool

- **[inferred]** Recommend option **(a)**: change only four asset fields in `LS_Opening_Curtain_Baked`—the spawnable template component's `geometry_cache` plus the three Geometry Cache section `geometry_cache_asset` fields. Do not edit offsets, ranges, actor transform, camera, Show timing, Master, level, or any Interaction sequence.
- **[declaration-proven]** `Saved/CodexSoftGoods/q17/ragged_opening_swap.py` provides confirm-gated DRY/APPLY/REVERT; APPLY and REVERT require a clean initial census, validate both cache frame ranges/materials plus the Q16 timing sidecar, create a run-id backup and record before mutation, accept exactly one dirty content package, save only `LS_Opening_Curtain_Baked`, read all four fields back after save, require zero final dirt, and fingerprint the five Interaction sequences unchanged (`Saved/CodexSoftGoods/q17/ragged_opening_swap.py:35-66`, `:247-405`).
- **[measured]** The offline harness passes **19/19** controls: 8 positive and 11 negative (`Saved/CodexSoftGoods/q17/test_ragged_opening_swap.py:1-108`; marker `Q17_OFFLINE_HARNESS|passed=19|failed=0|positive=8|negative=11`).

### Later ordered run (not run by job 76)

1. **[declaration-proven]** Leave `ragged_opening_swap_args.json` in DRY with confirm `DRY_RAGGED_OPENING_ONLY`; execute `CodexSoftGoods/q17/ragged_opening_swap.py` through `ExecuteProjectPythonFile` and require `Q17_RAGGED_OPENING_DRY_OK`.
2. **[declaration-proven]** Review the dry JSON: four Opening fields planned, five transition sequences fingerprinted, no mutation, save scope exactly the Opening sequence.
3. **[declaration-proven]** With the correct editor/world, PIE stopped and zero dirty packages, set a unique run id, `mode=APPLY`, confirm `APPLY_RAGGED_OPENING_ONLY`, and retain `decided_by`; require `Q17_RAGGED_OPENING_APPLY_OK`, the named backup/record, saved read-back and `dirty_final=0`.
4. **[inferred]** Render-check hang, release, landing/hold, bottom-edge raggedness and camera coverage. Automation is not visual acceptance.
5. **[declaration-proven]** To undo, use `mode=REVERT`, confirm `REVERT_RAGGED_OPENING_ONLY`, a new run id and decision text; require `Q17_RAGGED_OPENING_REVERT_OK`.

## B. P02/P03 end-curtain picture feasibility

### Current path and mapping

- **[measured]** P02 and P03 are level `GeometryCacheActor`s labelled `P02 End Drape (stand-in)` and `P03 End Drape (stand-in)`, bound into `LS_S2_HangarRise` and `LS_S3_HangarRise`; both records use old final13, 11 s duration and 1.0 s release (`Saved/CodexConductor/passage_end_drape_record_S2.json:16-24`, `:52-57`, `:81-110`; `Saved/CodexConductor/passage_end_drape_record_S3.json:16-24`, `:52-57`, `:81-110`).
- **[declaration-proven]** The placement tool sets the level actor component cache and a single Geometry Cache section asset, while preserving a level actor after the Passage tail (`Saved/CodexConductor/passage_end_drape.py:19-30`, `:1086-1102`, `:1120-1146`).
- **[measured]** `curtain_image_assign_record_P02.json` and `_P03.json` record one assigned material slot on those exact actors (`Saved/CodexConductor/curtain_image_assign_record_P02.json:1-8`; `Saved/CodexConductor/curtain_image_assign_record_P03.json:1-8`).
- **[declaration-proven]** Their image master supports two mappings. Default `PlanarMapping=1` projects in actor-local Y/Z; UV0 mapping is optional. Assignment is a component material override, leaving the shared cache material untouched (`Saved/CodexConductor/curtain_image.py:15-34`, `:86-103`, `:460-509`).
- **[declaration-proven]** The current P02/P03 MI planar rectangle is Y `-940..940` cm and Z `20..1020` cm (`Saved/CodexConductor/curtain_image.py:80-93`, `:150-156`).
- **[measured]** The ragged cache's hang bounds are Y `-940..940` cm and Z `21.3..1020` cm, matching that existing rectangle to within 1.3 cm (`Saved/CodexSoftGoods/q16/job74_record.json:19-22`).
- **[declaration-proven]** In the source pattern, UV0 is normalized flat-pattern space, cuts remove topology from that same pattern, smoothed/opened rag edges rebuild UVs from flat coordinates, and pleating moves only 3D positions while retaining the flat UVs (`Scripts/build_curtain_chaos_pattern.py:8-20`, `:186-210`, `:283-311`, `:367-390`, `:432-436`). Thus rags are holes/cut boundaries in the image domain, not a separate UV island layout; pleats do not exist in UV0.

### Verdict

- **[inferred]** **CHEAP (about 30 minutes of editor execution/verification, no re-bake and no new MI):** preserve each actor's existing `MI_CurtainImage_P02/P03` component override and its existing image texture, and swap only the actor component plus its one `LS_S2/S3_HangarRise` Geometry Cache section to the ragged cache. The active planar mapping ignores the unresolved Unreal UV-channel question and its rectangle already matches the ragged hanging bounds.
- **[inferred]** Reuse `curtain_image.py`'s existing MIs and assignment; do **not** rerun BUILD, SET or ASSIGN unless read-back says an override is absent. A future targeted P02/P03 swap should use `passage_end_drape.py`'s backup/census/read-back discipline, preserve P03's recorded 120 cm floor offset, and re-run its pose/pile guards because the ragged pile bounds differ from final13 (`Saved/CodexConductor/passage_end_drape_record_S3.json:91-118`; `Saved/CodexSoftGoods/q16/job74_record.json:20-22`).
- **[inferred]** Keep the existing 1.0 s release offset and section length: the ragged motion reaches its held pose before the old approximately 10 s cache-play window ends. If the pile guard asks for a small along-route shift, move the actor and its recorded placement together; that is placement correction, not image/UV work.
- **[inferred]** After each future swap, read back (1) actor cache, (2) section cache, (3) component material override, (4) image texture/planar scalars, (5) exact dirty census, then render-check picture orientation, crop across the torn hem, release and pile. The image assignment is mechanically feasible; rendered look remains Gary's acceptance.
