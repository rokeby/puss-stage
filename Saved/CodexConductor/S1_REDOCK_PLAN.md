# S1 re-dock after the P01 shorten (plan, 7 Oct)

This is offline only: nothing here has run in Unreal. Every claim is tagged per AGENTS.md:
- **[decl]**: read in source, a header or a script.
- **[meas]**: read back from an earlier run's record.
- **[prec]**: an in-repo tool already makes this call.
- **[inf]**: inferred, with the reason given.

Files:
- `s1_redock.py`, the tool
- `s1_redock_run.py`, `s1_redock_request.json` and `s1_redock_args.json` (set to DRY, not approved)
- `test_s1_redock_offline.py`: 15 tests, 132 checks, 0 failed. Three injected mutations made it fail 10, 1 and 3 checks.

## 1. Why the hangar moves, and why a translation is enough

- After `p01_shorten` APPLY, P01's auto-fit straight route ends 3600 cm earlier.
  - 6 × 600 cm **[inf]**. The tool reads the live end view.
  - `p01_shorten.py:27-37` **[decl]**.
- The S1 hangar is docked at the old end: root at (29284.0135, 0, 0) and dock at (28784.0135, 0, 150).
  **[meas]** `s1_landed_preview_record.json`, `scene_docks.json`
- On a straight route the heading and height stay the same. So the dock moves by a pure translation, Δ = (−3600, 0, 0).
  - This is **[inf]**, but it is asserted live: any yaw change over 0.01° refuses, and any end-view height change over
    1 cm refuses.
- The root's rotation is never written.
  - The sunk-REST-pose trap cannot reach a translation, because the root's rest and landed LOCATION are identical.
    **[meas]** `s1_landed_preview_record.json`
  - The guard still checks every hangar-tagged piece against the LIVE **landed** box, before and after. A root that is
    not landed refuses. The harness negative control shows that composing through the rest root puts a piece about
    34 m underground, and the guard refuses it.
- Rejected: `hangar_revert` followed by `hangar_build`. That route re-runs 117 spawns, the Arrival, the nest, the
  hangar retime and the exit doors, and it loses every applied tune.

## 2. What moves (the DRY lists every row with before/after)

| What | How | Evidence |
|---|---|---|
| **Top-level actors.** Tag `RigAtmos.Scene1Hangar`: the Root, the Apron, the Pinned Exposure PPV and S1 Arrival. | Location += Δ | Tagging: `hangar_build.py:365,379` **[decl]**. Apron and PPV are world-fixed: `:433-458` **[decl]**. The Arrival spawns at the root: `arrivals_apply.py:212` **[decl]** |
| **Everything attached under them** (closure, any depth). That is about 113 hangar pieces, the 5 exit-door shells, I1's `S1 Sleight Hangar Camera` and `S1 Sleight Twin Lantern`. | Carried. Read back: world position = before + Δ, and position relative to the root unchanged (±0.05 cm) | `hangar_build.py:424-427`, `hangar_exit_doors.py:606`, `curtain_sleight.py:1843,2024` **[decl]**. The camera's keys are root-relative **[meas]** `curtain_sleight_record_I1.json` |
| `S1 Pit Liner ×5` and `Opening Floor - Pit Strip L/R/Far` | Location += Δ (`extra_move_labels`) | Laid in world space against the hinge **[meas]** `plane_pitliner_record.json`, `plane_pithole_record.json` |
| `Passage 01 - Opening Floor` | **TRIM**. The far edge moves 29284.01 → 25684.01 and the near edge stays at −150. scale.x goes 294.340135 → 258.340135; loc.x goes 14567.00675 → 12767.00675 | Far edge = the hinge **[meas]** `floor_dark_wet_record.json`, `plane_trim_record.json`. If it were left, the floor would cover the new pit **[inf]** |
| `LS_S1_HangarRise` root binding (`EE1E481E…`) | Location X/Y/Z channel **defaults** += Δ, and keys too if any exist | At BeginPlay the Arrival sets the root from the first key, or else the default (`InfinityStageArrival.cpp:80-121, 971-1021` **[decl]**). Without this shift, a game world snaps the hangar back to the old end. S1 has defaults only, no keys **[meas]** |
| I1 spawnables `Sleight Hangar Drape` and `Sleight Hangar Shadow Card` | World Location keys += Δ, and the template's relative location too. The template must equal key 0 or the tool refuses | Keys at x 34883.96 / 34841.16 **[meas]** `curtain_sleight_record_I1.json`. Template = key 0: `curtain_sleight.py:1906-1907, 2062-2064` **[decl]** |
| Scene 1 Entry/Exit Handoff Cameras | **Regenerated**: `MatchNamedSceneHandoffs`(Scene 1) inside APPLY, then gate: Entry camera = new seat ±1 cm | `match_scene1_handoff.py:96` **[prec]**. Exit also sits on the dock **[meas]** `extend_scene_playback_scene1_apply.json` |
| Master | `RebuildManagedMaster` with a **no-change** gate: segments, managed sections, keys, artist content and markers must be identical, and the Master must be in sync. The Show is untouched (`protected_view` equal) | `passage_retime_to_music.py:1271` **[prec]** |

Things that ride along with no action:
- Roof hinge and lattice keys: they are relative.
- Light intensity keys, the rise pitch keys, and `hangar_heave`, which keys pitch only.
- The I1 hangar camera keys.
- The PPV blend weight.

## 3. What is NOT moved (the DRY lists it for review)

The DRY looks at every actor in a window in the old dock frame:
- from 1000 cm before the new end to 150 m past the old end, and ±50 m sideways;
- the same window as `p01_shorten._region_inventory`.

Each actor is classified:
- **PASSAGE_OWNED**: P01 Passage, Structure 01, the rig, managed attachments. `p01_shorten` materialises them.
- **REGENERATED**: the Scene 1 handoff cameras.
- **ACKED**: actors listed in `leave_in_place`.
- **UNKNOWN**: APPLY refuses until each one is either moved (`extra_move_labels`) or acked.

**The P01 lane has never been inventoried** (`lane_inventory_130421.json` covers lanes 2–6). This list is the first
measurement of it.

A sequence scan covers every Show cue's sequence, one nesting level down, the Master, the rise and I1. It never calls
GetBoundObjects. It refuses in two cases unless the binding is handled or acked:
- a 3D-transform binding on a moved top-level actor, other than the rise root;
- a spawnable whose keys sit in the old hangar box.

Known gap: the pit strips' far ends move back 69149.96 → 65549.96. That leaves a 36 m band about 34 m beyond the new
far wall without floor. **[inf]** It has not been rendered.

## 4. Records left holding the OLD frame (this tool never edits them; the record lists them)

- **`hangar_exit_doors_record.json`**
  - Its `landed_root_transform` is read as "the landed root" by `curtain_sleight.py:1533-1545` and
    `passage_end_drape.py:44`.
  - Its REVERT restores the S1 far wall at its OLD world pose (`hangar_exit_doors.py:1024-1031`) **[decl]**. Do not revert the doors while
    the re-dock is applied.
- **`KlaraIngest/klara_hookin_args.json`**: `hangars.1.dock` is still 28784.0135.
  - Its DRY checks the live S1 Apron and will refuse.
  - Set the dock to the record's `klara_dock_for_args`, which is (25184.0135, 0, 150) **[inf until measured]**.
- **`floor_dark_wet_apply.py:74-75`**: the P01 extent is hard-coded.
  - Its REVERT would put the floor back over the new pit. Do not revert it while the re-dock is applied.
- APPLY and REVERT refuse while any of these records is applied, because each one composes against the S1 frame:
  - Klara stream/seq records
  - `passage_end_drape_record_S1`
  - `scene_exit_block/move_record_S1`
  - `hangar_heave_record_S1`

  None of them is applied today.

## 5. Run order

1. Snapshot: D: and `Backups/PreS1Redock-<ts>`. The tool also takes its own backup of the level, the rise, I1,
   LS_DevScene_01, the Master and the Show.
2. Run the offline tests: `python test_s1_redock_offline.py` must show `failed=0`.
3. **Optional preview, before `p01_shorten` APPLY.** Run s1_redock DRY. It reports `predicted=1`, `apply_ready=0`.
   Review the move list and the UNKNOWN list, and fill in `leave_in_place` / `extra_move_labels`.
4. `p01_shorten` APPLY, then the two tests.
5. Retime APPLY (`passages ["1"]`), then the tests. The retime does not move the end **[decl]** (retime header).
6. Walk-in re-ease. This belongs to the Opening stream and is independent of S1.
7. **s1_redock DRY** (live delta, which must equal −removed_cm ±5 cm).
   - Copy `expected_for_apply_args` into `expected`.
   - Set `approved_by`. It is non-creative and reversible, so the conductor may approve it.
   - **APPLY** (`"APPLY S1REDOCK"`), then wait for `S1_REDOCK_APPLY_OK|run=…`.
   - Then run, one at a time: `SavedMasterMatchesShow`, then `SceneCutBindingsResolve`.
   - This step replaces P01_SHORTEN_PLAN steps 8 and 9. Running `match_scene1_handoff.py` first does no harm.
8. Update the Klara hook-in args dock, then the hook-in. It reads the NEW landed root.
9. Look at the P01→S1 crossing, the S1 rise and the I1 sleight wide. These are for Gary's verdict.

**REVERT is LIFO:**
1. Revert the Klara hook-in.
2. Then `s1_redock` REVERT (`"REVERT S1REDOCK"`). This does not re-match.
3. Then the retime.
4. Then the shorten.
5. Then run `match_scene1_handoff.py`.

On any `S1_REDOCK_STOPPED` before a save, nothing has been saved: quit the editor with Don't Save and restart.

## 6. Risks and what is inferred

- **The live API surface has not been exercised by this tool.** The calls are precedent calls from tools that have
  run (cited inline), but this particular combination has not run:
  - `set_default` / `set_value` on a nested rise
  - template writes on I1
  - `locate_bound_objects` on the rise
- **The slab material may compress about 12 % in x** if its tiling is UV-mapped rather than world-mapped. **[inf]**
- **The rebuild step is defensive.** The Show is unchanged, so the gate expects identical state. If the rebuild changes
  anything, the run stops.
