# Spec: `Saved/CodexStructure/s4_rekey_window_apply.py` (Scene 4 "all at once, gradually")

Gary, 30 Sep, confirmed in the Rig & atmosphere session: the P04 curtain falls 2 s earlier (lead 3.0 → 5.0, done
separately by `p04_backcloth_lead5_apply.py`). The rig rises WITH the curtain. Lights and exposure ramp over the same
window. Later beats keep their spacing.

## What to write
One Unreal-Python script, modelled closely on the REFERENCE `Saved/CodexStructure/s4_arrival_light_apply.py`: same
guards, record/backup/revert shape, runners, and marker style.
- Modes: dry run (default), `S4REKEY_APPLY`, `S4REKEY_REVERT`.
- Runners: `s4_rekey_window_apply_run.py` and `s4_rekey_window_revert_run.py`, plus the three `*_request.json` files
  (the same format as the reference's).
- Pure planning lives in a function `plan_keys(before, W0, W1)` that takes and returns plain floats. It must be
  importable WITHOUT Unreal, for the harness below.

## The window: READ it, never type it
- Read `Saved/CodexStructure/p04_backcloth_section_record.json`:
  - `W0 = plan.cloth_release_s` (expected ≈ −5.874);
  - `W1 = plan.section_end_s` (expected ≈ +4.126).
- REFUSE if `plan.lead_s != 5.0`, if either value is missing, or if `W0 >= 0` or `W1 <= 0`.
- TRAP: typing −5.874 / 4.126 silently breaks the day the cloth moves again.

## Keys in `/Game/InfinityStage/RigAtmos/LS_S4_HangarRise` (Scene 4 time, seconds; display rate from the asset)
- **Root** (binding "S4 Hangar Root", 3D transform track, pitch = channel INDEX 4, as `hangar_build.py` keys it):
  - becomes `[(W0, -90), (W1, 0)]`, AUTO interpolation;
  - its other channels are untouched.
- **Practicals and lattice glow.** These are the float tracks with property "Intensity" on component bindings whose
  PARENT binding's display name starts with "S4 Practical" (14) or "S4 Lattice Glow" (24):
  - each becomes `[(0, 0), (W1, full)]`, LINEAR, where full = that channel's current maximum (400 / 20);
  - TRAP: keys before 0 on these would never play until held patch P exists. Only the root is driven before the cut
    (InfinityStageArrival.cpp:246-275).
- **Exposure.** The float track "BlendWeight" on binding "S4 Hangar Pinned Exposure":
  - becomes `[(0, 0), (W1, 1)]`, AUTO;
  - do not touch the actor's saved weight (it is already 0).
- **Later beats keep their spacing after the new landing.** delta = W1 − 16.0 (the current landing), applied to every
  key with t > 0 on:
  - "S4 Uplight" intensity channels (parents starting "S4 Uplight");
  - "S4 Hangar Roof Hinge" pitch (channel index 4);
  - "S4 Hangar Lattice Fly" Z (channel index 2).
  - The key at t = 0 stays.
- **Untouched:** the "P04 Backcloth (baked)" GeometryCache track, and the playback range (0..31).

## Traps (each has cost this project time)
1. NEVER open Sequencer. Asset API only: `unreal.load_asset`, `get_bindings`, `get_tracks`, `get_all_channels`,
   `add_key`, `remove_key`. Opening a Master-bound sequence dirties the map.
2. Channel NAMES are suffixed (`Location.Z_183`, `Rotation.Y_2`). Select channels by INDEX, and record the names in the
   plan log so a reader can check them.
3. This is a SECOND layer on top of the 17:39 change (`s4_arrival_light_record.json`). The new record
   `s4_rekey_window_record.json` must store the keys AS FOUND NOW, and the revert restores exactly those (not the
   pre-17:39 keys). The revert is gated on a read-back matching the record.
4. Guards before any write:
   - expected world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
   - no PIE (`get_game_world() is None`; during PIE `get_editor_world()` can be None, so check that too);
   - BOTH dirty lists empty (maps AND content);
   - no Sequencer open;
   - record absent.
5. Save ONLY the sequence asset (`EditorAssetLibrary.save_asset`). NEVER the level.
6. Read back every changed channel after the edit and BEFORE the save (keys within 1 frame, values within 1e-3). On any
   mismatch, stop without saving.
7. The done line reports a post-run census of BOTH packages, and the marker carries `run=<HHMMSS>`.

## Harness: `Saved/CodexStructure/test_s4_rekey_plan.py`, plain Python, no Unreal
Feed `plan_keys` the "before" keys in `Saved/CodexStructure/specs/fixture_s4_keys_1739.json` (committed), with
W0 = −5.874 and W1 = 4.126.

**POSITIVE control:** these exact outputs must be asserted:
- root `[(-5.874,-90),(4.126,0)]`;
- "S4 Practical L1" `[(0,0),(4.126,400)]`;
- "S4 Lattice Glow 1-1" `[(0,0),(4.126,20)]`;
- the first uplight `[(0,0),(6.126,0),(6.326,10000)]`;
- roof `[(0,-90),(6.626,-90),(12.626,0)]`;
- lattice fly Z `[(0,2800),(12.626,2800),(16.626,1200)]`;
- weight `[(0,0),(4.126,1)]`.

**NEGATIVE controls,** each must FAIL (the harness checks that it does):
- a) `plan_keys` with W0 >= 0 raises;
- b) the unchanged "before" keys, compared to the expected outputs, do not match;
- c) a planted wrong delta (W1 − 15.0) gives a roof start ≠ 6.626.

**Print** PASS or FAIL per case, and exit non-zero on any unexpected result.

## Constraints
- Don't modify any existing file except by adding the new files listed above.
- No Unreal run. The Rig & atmosphere session reviews the diff, runs the dry run and applies.
