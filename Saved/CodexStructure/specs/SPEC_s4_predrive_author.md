# Spec: `Saved/CodexStructure/s4_predrive_author_apply.py`: the S4 dim starts WITH the curtain (patch P is built)

Gary (30 Sep, confirmed in the Rig & atmosphere session): "dim from the curtain too". Patch P (commit cc1331e build)
gave `AInfinityStageArrival` the property `PreSceneFloatDrives` (struct `FInfinityArrivalFloatDrive`: `Target`
soft-object, `BindingGuid`, `PropertyName`). It evaluates those float channels BEFORE the Scene's first frame, in game
worlds only.

This script does the two authoring steps P left to Rig & atmosphere:

## 1. Re-key the ramps to start at W0 (asset `/Game/InfinityStage/RigAtmos/LS_S4_HangarRise`)
- Read `W0 = plan.cloth_release_s` and `W1 = plan.section_end_s` from
  `Saved/CodexStructure/p04_backcloth_section_record.json`. REFUSE unless `plan.lead_s == 5.0`, W0 < 0 < W1.
- The 38 "Intensity" float channels on component bindings whose PARENT binding name starts with "S4 Practical" (14) or
  "S4 Lattice Glow" (24) are today `[(0,0),(W1,full)]`. They become `[(W0,0),(W1,full)]`, LINEAR, where full = the
  channel's current max.
- The "BlendWeight" channel on binding "S4 Hangar Pinned Exposure" is today `[(0,0),(W1,1)]`. It becomes
  `[(W0,0),(W1,1)]`, AUTO.
- Nothing else in the sequence changes (the root, uplights, roof, lattice fly and backcloth are already right).
- REFERENCE implementation for finding the channels, guards, record, backup, revert, read-back and runners:
  `Saved/CodexStructure/s4_rekey_window_apply.py` (reviewed and applied today). Mirror its structure.
- Keep planning pure and Unreal-free (`plan_keys(before, W0, W1)`).

## 2. Author the drives on the level actor "S4 Arrival"
Set `pre_scene_float_drives` to exactly 39 entries:
- 38 lights: `Target` = the `LightComponent` of the LEVEL actor whose label equals the parent binding's display name
  (for example actor "S4 Practical L1", via `get_component_by_class(unreal.LightComponent)`), `BindingGuid` = that
  component binding's GUID (`binding.get_id()`), `PropertyName` = "Intensity".
- 1 volume: `Target` = the level actor "S4 Hangar Pinned Exposure", `BindingGuid` = its binding's GUID,
  `PropertyName` = "BlendWeight".
- REFUSE if any parent actor, component or binding can't be matched one-to-one. Never guess by index.
- Build the structs through the Python API (`unreal.InfinityArrivalFloatDrive()` + `set_editor_property`). If the exact
  Python names differ (for example `binding_guid`, `property_name`, `target`), discover them at runtime with
  `dir()`/`get_editor_property` and print them in the plan.

## Traps
1. Never open Sequencer (asset API only). Opening or scrubbing a Master-bound sequence dirties the map.
2. Guards before any write:
   - expected world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
   - no PIE (`get_game_world() is None`, and `get_editor_world()` not None);
   - BOTH dirty lists empty;
   - no Sequencer open;
   - no ZZ_/TEMP_ actors;
   - record absent.
3. The record `s4_predrive_author_record.json` holds the keys AS FOUND and the Arrival's previous drives (count and
   entries as plain strings). The revert restores exactly those, gated on a read-back of the applied state.
4. Save ONLY the sequence asset and the level (the Arrival is a level actor). Back up both first to
   `Backups/PreS4Predrive-<stamp>/`.
5. READ-BACK before saving:
   - every changed key (within 1 frame and 1e-3);
   - the drives array (count 39, each target path, GUID and property).
   - The SEAM: the Arrival's `resolve_float_drive_at_master_frame(show, t, i)` one Master tick before Scene 4's start
     must equal the channel's value at scene time 0 within 1e-2, for a practical, a glow and the volume. It must also
     be clearly LESS than full at W0 + 1 s. Map the Master time exactly as `Saved/CodexStructure/seam_check_readonly.py`
     does (the transport's `build_segments` + the Scene segment start).
   - Any mismatch: stop, no save.
6. The done line carries `run=<HHMMSS>` and a post-run census of BOTH packages.

## Harness `Saved/CodexStructure/test_s4_predrive_plan.py`, plain Python
Use `Saved/CodexStructure/specs/fixture_s4_keys_1739.json`, with W0 = −5.874 and W1 = 4.126. Its practical/glow
entries are the pre-window values; build the "before" from them, as they were re-keyed to `[(0,0),(4.126,full)]`.
- **POSITIVE:** "S4 Practical L1" → `[(-5.874,0),(4.126,400)]`; "S4 Lattice Glow 1-1" → `[(-5.874,0),(4.126,20)]`;
  volume → `[(-5.874,0),(4.126,1)]`.
- **NEGATIVE, each must FAIL:**
  - a) W0 >= 0 raises;
  - b) the unchanged before-state doesn't match the expected;
  - c) a plan that leaves the ramps at 0 (a wrong W0) is detected.

Deliver all new files: the script, two runners (apply/revert), three request JSONs and the harness. Run the harness and
report its lines verbatim. Don't run Unreal.
