# P4 fixtures offline delivery — 8 Oct 2026

Nothing in Unreal was opened, mutated, saved, or rendered in this stream. The six JSONs and PNGs are proposals only.

## Delivered

- **[declaration-proven]** `FInfinityBulbBodySettings` now declares opt-in bulb-owned point-light and cord-sway values;
  both default off (`InfinityStageBulbBody.h:89-144`). This avoids a Light attachment, so a relocated bare bulb does
  not acquire a generated lantern.
- **[declaration-proven]** bulb point lights are transient game-world components; cord and bulb transforms pivot around
  the saved cord mesh top using a GUID/seed-phased sine (`InfinityStagePassageActor.cpp:2027-2107`,
  `InfinityStageBulbBody.cpp:66-84`). Editor authoring transforms are not driven.
- **[declaration-proven]** RELOCATE exposes `glow_mode` and `cord_sway_mode` plus every creative value as an argument;
  it writes the body→cord GUID and remains under the existing DRY/APPLY/REVERT, confirm, record, backup, narrow-save,
  read-back and marker gates (`fixtures_common.py:460-495`, `fixtures_follow.py:32-38`).
- **[measured]** the expanded offline harness passes `53/53`, including negative controls for glow OFF, static cords,
  a wrong cord GUID and a setter/read-back lie (`harness_result.json:2`). Python bytecode compilation also passed.
- **[measured]** six per-passage proposal JSONs contain 244 proposed bulbs total: P01 54, P02 13, P03 25, P04 19,
  P05 107, P06 26 (`FixturesFollow/previews/summary.json:8`, `:37`, `:66`, `:95`, `:124`, `:153`, `:181`). Six
  overhead PNGs were generated (`FixturesFollow/previews/`).
- **[measured]** P01/P02/P03/P05 overhead routes use tracked rig-lamp level read-backs; P06 uses the tracked station
  sample in `lighting_events_report.json`. **[inferred]** missing stations are linearly interpolated or extrapolated.
  **[inferred]** P04 uses a 500 cm straight route because no saved P04 station-coordinate record was found; its JSON
  and PNG say so.

## Conductor run order (later, not performed here)

1. Build with all editors closed; prove a new UTF-16 literal from the patch is in the DLL; run the focused bulb-body
   automation then the narrow `InfinityStage` suite.
2. Run `python Saved/CodexConductor/FixturesFollow/test_fixtures_follow.py` and require `53/53`.
3. Review `previews/P0N_overhead.png` and the matching proposal JSON. Gary approves or changes x3, hang split, filament
   intensity, 24 lm point light, 2.5°/1.5° sway and 7 s period.
4. In the editor, one passage at a time: SCALE DRY/APPLY, then RELOCATE DRY. Compare the live SHA/count/floor report to
   the offline proposal. APPLY only after the exact confirmation and Gary's approval; start with P01.
5. Require saved read-back, zero dirty packages beyond the named Show/level during the guarded write, success marker,
   focused tests, and a rendered still/PIE look check. Automation is not visual acceptance.

## Open gates

- **[inferred]** the C++ compiles: engine 5.8 header lookup confirms every point-light setter used, but this stream did
  not take the exclusive build gate.
- **[inferred]** point-light intensity, filament intensity and sway amplitudes look right: these are exposed defaults,
  not accepted creative values.
- **[inferred]** saved snapshots still match the live Show: the first live DRY must settle this and resolve real floor
  bounds before any APPLY.
