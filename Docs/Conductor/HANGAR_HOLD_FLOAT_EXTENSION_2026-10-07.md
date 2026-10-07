# Hangar hold: non-transform extension ("hold": "FLOAT"), 7 Oct 2026

Offline only. No MCP call, no Unreal, no commit, no stash. Files touched:
`Saved/CodexConductor/s4_hangar_hold.py`, `Saved/CodexConductor/s4_hangar_hold_args.json`,
`Saved/CodexConductor/test_s4_hangar_hold_offline.py`, and this note. The runner `s4_hangar_hold_run.py` and the
request file `s4_hangar_hold_request.json` are unchanged and still drive both paths.

Tiers, as AGENTS.md requires: **[decl]** a header, signature or config I read; **[bin]** strings from an installed DLL;
**[meas]** an intervention was run and read back (here: the harness, or earlier live records, which are cited);
**[prec]** an in-repo call that ran before (cited); **[inf]** inferred, with the reason.

## 1. What was built

- **Dispatch.** `main()` (`s4_hangar_hold.py:1371`) checks `args["hold"]`. If it is absent or `"TRANSFORM"`, it runs
  `main_transform` (`:1333`), which is the 4e1e703 `main` body verbatim. If it is `"FLOAT"`, it runs `main_float`
  (`:1289`). **[meas: harness]**
- **Transform path is bit-identical.** Harness class `TransformBitIdentical` (`test_s4_hangar_hold_offline.py:392`) checks three things. **[meas]**
  1. A sha256 fingerprint over every transform-path pure output on fixed fixtures equals the value frozen from the
     unedited module. The value is `e40026d8…`, computed before any edit.
  2. A control monkeypatches one value by 1e-9 and confirms the hash changes.
  3. A source check covers all 33 top-level functions and every module constant and class of the
     4e1e703 file, read with `git show`. Each is verbatim in the new file, and `main_transform`'s body equals the old
     `main`'s body. The control: mutating one literal in `plan_holds` is caught.
- **Pure planner** `plan_nontransform` (`:722`) covers every NON-transform rise track. It sorts each track into
  held targets, refused tracks and listed tracks (with what holding them would mean).
  - **Held value:** `held_value` (`:654`) uses the value after the LAST key by time. A channel with no keys uses its default. **[meas: harness]**
  - **Refusals** (`_nt_target` `:676`, `held_value`):
    - a last key after the fold end (`LAST_KEY_AFTER_FOLD_END`);
    - a keyed float channel whose post-infinity extrapolation is not constant, or could not be read
      (`POST_EXTRAP_NOT_CONSTANT` / `POST_EXTRAP_UNREAD`; getter declared at
      `UE_5.8/.../SequencerScripting/Private/KeysAndChannels/MovieSceneScriptingFloat.h:552`
      `GetPostInfinityExtrapolation` **[decl]**);
    - a section that ends before, or starts after, the fold end;
    - more than one section or channel;
    - a non-absolute float blend;
    - an inactive section;
    - an unkeyed channel with no default;
    - a float track with no property path;
    - a duplicate target.
  - **Allowed:** a last key at the fold-end tick exactly. A last key before frame 0 is held and flagged
    `last_key_before_fold`. I read "outside the fold" as after its end, because a value fixed before frame 0 is still
    the value at the fold end **[inf]**.
- **Gates.**
  - `float_apply_gate` (`:785`) blocks APPLY on any refused track, scene conflict, identity mismatch or empty plan.
    DRY reports all of them and never stops on them.
  - `float_scene_conflicts` (`:755`) treats each of these as a conflict:
    - a same-class, same-property track that overlaps the hold on the matching Scene binding. Two absolute float
      sections would blend **[inf]**;
    - our own track already present (a leftover).
- **Binding identity** (`_float_plan` `:979`, `run_apply_float` `:1033`). The target object is the level actor by
  label, plus the component by name for `LightComponent0`-style child bindings.
  - DRY checks that `rise.locate_bound_objects(rise_binding, editor_world)` equals exactly that object's path
    **[prec opening_sequence_apply.py:330]**.
  - APPLY makes the Scene binding with `add_possessable(object)` **[prec hangar_build.py:489, s3_daylight_apply.py:402]**.
    It then checks that the Scene binding resolves to the same path, both before the save and again after the reload.
  - Component bindings must come back parented. A created parent actor binding is recorded and renamed
    `S<n> Hangar Float Hold: <label>`. Reused bindings keep their names (`klara_reveal.py:2996-3013` lesson).
- **APPLY discipline** follows the transform `run_apply`:
  - exclusive fsynced record first, then a backup of `LS_DevScene_0N` with a hash check;
  - census clean before, Scene-only census before the save, save of the Scene only;
  - read-back of range, completion, value (float32 tolerance), no keys, ABSOLUTE blend, property path and display name;
  - reload and second read-back, which includes binding resolution;
  - census clean after, then the record is marked applied and `S<n>FLOATHOLD_APPLY_OK` is logged.
- **REVERT** (`run_revert_float` `:1156`) removes exactly the recorded tracks, found by binding guid + class +
  property path + our display name. It then removes the bindings it created, children before parents
  (`revert_order` `:847`), and only if they are empty. It reads back that nothing is left before saving.
- **Kept separate from the transform hold** (`fnames` `:630`):
  - confirm `<MODE> S<n>FLOATHOLD`;
  - record `s<n>_hangar_float_hold_record.json`;
  - track name `S<n> Hangar Float Hold`;
  - prefix `S<n> Hangar Float Hold: `;
  - backup `PreS<n>HangarFloatHold-<run>`.

  No float name matches or prefixes a transform name, so the transform REVERT's leftover and track tests cannot see
  float work, and the reverse holds too. Each confirm string is rejected by the other path's validator.
  **[meas: harness `FloatSeparateFromTransform`]**

  The existing transform records `s1..s4_hangar_hold_record.json` are untouched and need no revert. The float targets
  are lights, the PPV, and opt-in props. None of them is a hangar mover, so no binding is shared **[inf from the
  inventories below]**. If one ever were shared, the transform REVERT would refuse with `CREATED_BINDING_NOT_EMPTY`
  rather than break it (`:581-582`, verified at :582) **[decl]**.
- **`hold_kinds`** defaults to `["float"]`. `"visibility"` and `"bool"` are opt-in and use the same last-value rule,
  because they are trivially analogous: one bool channel, copied with the same track class. A visibility channel is
  `bHiddenInGame`, so True means HIDDEN **[prec klara_reveal.py:3131-3139]**. Scripting does not expose the bool
  channel's extrapolation. The header default is `RCCE_Constant` (`MovieSceneBoolChannel.h:38`) **[decl]**. That a
  given channel still has the default is **[inf]**.

## 2. Per-scene inventory (what DRY will plan)

Counts come from the 7 Oct transform DRY outputs, `plan.not_held_rise_tracks` **[meas, harness `LiveInventory`]**:

| Scene | float (held) | GeometryCache (listed) | visibility (listed unless opted in) |
|---|---|---|---|
| S1 | 42 = 41 lights + `S1 Hangar Pinned Exposure` | `P01 End Drape (stand-in)` | 0 |
| S2 | 42 = 41 lights + `S2 Hangar Pinned Exposure` | `P02 End Drape (stand-in)` | 0 |
| S3 | 50 = 47 lights (`hangar_light_keys_probe.json`) + Pinned Exposure + **2 unidentified** | `P03 End Drape (stand-in)` | 9 (`Shore01-06 … Clam`, `Clam_with_Pearl…`, `tg0pfjxda_tier_0`, `source_Anim`) |
| S4 | 42 = 41 lights + `S4 Hangar Pinned Exposure` | `P04 Backcloth (baked)` | 0 |

These are the expected held values, taken from the last keys measured on 7 Oct in `hangar_light_keys_probe.json` and
`scene_exposure_weight_read.json`. The live DRY recomputes every one, so treat them as **[inf]** until it does:

| Track | Value after the last key |
|---|---|
| Pinned Exposure BlendWeight | 1.0 (last key frame 124, inside the fold) |
| Lattice Glow Intensity | 20 |
| Practical Intensity | 400 |
| Uplight Intensity | 10000 |
| S3 Strike Intensity | 1500 / 1000 / 4000 |

- All of those last keys are at or before 10.5 s, inside the 31 s fold. Their sections run [0, 930) or [0, 775) frames,
  which covers the fold end. So no refusal is expected **[inf]**.
- S3's 2 extra float tracks: the inventory counts 50 against 48 known. They are on `LightComponent0` bindings and may
  be a second property on a light. The DRY lists them by property path.
- The 9 S3 visibility tracks:
  - **What holding means:** the clams/props would keep whatever their last rise key sets (hidden or shown) for the rest
    of S3, instead of reverting to level state.
  - **Not held by default.** They take `"hold_kinds": ["float", "visibility"]` and need a creative yes from Gary.
  - Some of these binding names (`Clam_with_Pearl_Clam_with_Pearl_0`, `source_Anim`) look like object names, not
    labels. If one does not resolve by label, the DRY reports `ACTOR_COUNT` under `identity_mismatch` **[inf]**.

## 3. GeometryCache: researched, NOT implemented

- **What the section exposes [decl].** `FMovieSceneGeometryCacheParams` (`UE_5.8/Engine/Plugins/Runtime/GeometryCache/Source/GeometryCacheTracks/Classes/MovieSceneGeometryCacheSection.h:13-54`) has:
  - `GeometryCacheAsset`, `FirstLoopStartFrameOffset`, `StartFrameOffset`, `EndFrameOffset`, `PlayRate`, `bReverse`;
  - no hold, clamp or loop flag.

  `MapTimeToAnimation` is declared at `:71` and in `Private/MovieSceneGeometryCacheTemplate.h:21`. Its body is in a
  `.cpp` that is not installed. I searched `Plugins/Runtime/GeometryCache/**/*.cpp` and found none.
- **[bin]** `UnrealEditor-GeometryCacheTracks.dll` strings (ASCII and UTF-16) contain only those property names and
  their tooltips. There is nothing about clamping or holding. The tooltip "offset for the first loop" implies that a
  section longer than the clip LOOPS **[inf]**.
- **[decl + meas, project test]** `InfinityStageArrivalTests.cpp:186-190` asserts that `MapTimeToAnimation` returns
  sample 0 before the section and the last sample after it ("does not loop"). That is the mapping function only. It
  says nothing about what Sequencer draws when no section is being evaluated.
- **[meas, record]** The P04 backcloth section in `LS_S4_HangarRise` already ENDS at Scene time +3.0 s, with
  KEEP_STATE (`backcloth_lead_fit_record.json` section_after). That is 28 s before the fold ends. So "the backcloth
  returns to hanging after the fold" is unmeasured. The cloth may already hold its pile from 3 s onward, or it may not.
  Nobody has looked at 3–31 s against 31 s and later.

**Options, if the probe shows the cloth is NOT held:**

| | Mechanism | Tier | Risk |
|---|---|---|---|
| O1 | Scene GC section on the backcloth binding over [fold_end, scene_end), same cache, `StartFrameOffset` = duration − 1 cache frame (in ticks), `EndFrameOffset` 0, `PlayRate` 1, `bReverse` false | [inf] | The mapping body is unseen. The first-loop tooltip says a section longer than the clip loops, so it would loop a one-frame window at the pile, which should look frozen. Must be checked in PIE. |
| O2 | One-frame Scene GC section at fold_end, offset to the last frame, KEEP_STATE | [inf] | Relies on KEEP_STATE plus manual tick persisting past a section's end. The probe's 3–31 s reading tests exactly this, using the rise's own section. |
| O3 | `bReverse` with section start at fold_end | rejected | Plays the drop backwards (lifts the pile). |
| O4 | Near-zero `PlayRate` | rejected | Unprovable. A zero rate may be replaced by 1.0 [inf]. |
| O5 | Set the level component (`running` false, offsets) | rejected | `running=false` freezes frame 0, the hanging pose (memory ue58-geometrycache-sequencer-traps). |

**PIE probe to decide.** The probe is built in as a read-only mode, `run_pieprobe` (`:1209`), in the conductor's own PIE:
- It never ends PIE and never writes anything.
- It runs in two calls, because GC frames decode asynchronously. First call: `"probe_phase": "scrub", "master_frame": F`
  (precedent `s3_white_probe.py:27-38`). Second, later call: `"probe_phase": "read"`.
- It reads `anim_time`, `elapsed`, `duration`, `playing`, `looping`, `running`, `manual_tick` and bounds for each rise
  GC actor. It also reads the live float values of the targets.

S4 segment start is 28482625, at 960 ticks per frame. Both are **[meas]** in `probe_s4_sky_pie.py:33-34`; re-read them
if a Passage has been retimed since. Probe these S4 frames:

| S4 frame | Master frame |
|---|---|
| 50 | 28530625 |
| 200 | 28674625 |
| 770 | 29221825 |
| 800 | 29250625 |
| 1500 | 29922625 |
| 3912 | 32238145 |

How to read the result:

| Result | Meaning | Action |
|---|---|---|
| `at_last_sample` true at 200 and at 800+ | Already held | Nothing to build |
| True at 200, false at 800+ | The fold end releases the cloth | Test O2 first (cheaper, reversible), then O1 |
| False already at 200 | The section end releases the cloth | O1 |

For every Scene GC write, compare the bounds against the render, re-posing once (stale-frame trap).

## 4. Harness

`python Saved/CodexConductor/test_s4_hangar_hold_offline.py` → **Ran 37, OK** **[meas, 7 Oct]**. That is 18 tests that
were already there plus 19 new ones.

- **Pre-existing failure, now fixed.** Before any edit, `Args.test_args` FAILED (17/18), because the shipped args file
  had been left at `APPLY S3` after this morning's run. The args file now ships as `DRY / scene 3 / hold FLOAT`, and
  the test passes unchanged.
- **New −/+ controls:**
  - a last key at the fold end is held, but one tick later it is refused and APPLY is gated;
  - the first key ≠ the held value (0.0 vs 1.0 for the S3 exposure);
  - unkeyed → default (7.5), and unkeyed with no default → refused;
  - linear or unread extrapolation → refused;
  - each section/channel/blend/active refusal;
  - a one-frame overlap becomes a conflict, while a section ending at the fold end does not;
  - a different parent does not match;
  - leftover own track → conflict;
  - float/transform names and confirms are disjoint;
  - dispatch routes correctly;
  - float32 read-back tolerance accepts 1e-4 at 10000 and rejects 0.5;
  - revert order is children before parents;
  - the transform fingerprint and source are frozen.

## 5. Order and request files (conductor)

Each step uses the same request: `Saved/CodexConductor/s4_hangar_hold_request.json`, which runs `ExecuteProjectPythonFile`
on `CodexConductor/s4_hangar_hold_run.py`, which reads `s4_hangar_hold_args.json`.

- Edit the args, then send the request.
- Give each step an explicit `run_id` and parse the marker by that id (memory puss-log-markers-run-id).
- Common to every step: `"hold": "FLOAT"`, `"hold_kinds": ["float"]`, `"completion": "KEEP_STATE"`.
- APPLY needs PIE stopped, Sequencer closed and a 0+0 census. `decided_by` must name who decided. That is a lighting
  hold, so the conductor may approve it per the delegation rule, or ask Gary.

**S3 first:**
1. DRY: `{"mode":"DRY","scene":3,...,"run_id":"S3FLOATHOLD-<stamp>-dry"}`.
   - Expect `S3FLOATHOLD_DRY_OK|…|gate=[]`.
   - Read `s3_hangar_float_hold_dry_<run>.json`: about 50 targets, refused 0, conflicts 0, identity_mismatch 0, and
     Pinned Exposure value 1.0.
   - Identify the 2 extra float tracks.
2. APPLY: `{"mode":"APPLY","scene":3,"confirm":"APPLY S3FLOATHOLD","decided_by":"…","run_id":"S3FLOATHOLD-<stamp>-apply"}`. Expect `S3FLOATHOLD_APPLY_OK|…|held=N`.
3. PIE check, read-only. Use `s3_white_probe.py` at r33/r40/r55/r182 (BlendWeight should now be 1.0) and luma. You can
   also run `PIEPROBE` with `segment_start_master` 18884545 (**[inf]**: r1 = 18908545 − 24000, and it fits r10/r182)
   and `ticks_per_frame` 1000.

**Then S4, S1, S2:** run the same DRY → APPLY → PIE check with `scene` 4, 1, 2 and confirms
`APPLY S4FLOATHOLD`, `APPLY S1FLOATHOLD`, `APPLY S2FLOATHOLD`. Run the S4 backcloth `PIEPROBE` (section 3) before
deciding on any cache work. If a step needs undoing: `{"mode":"REVERT","scene":N,"confirm":"REVERT S<N>FLOATHOLD"}`. This
leaves the transform hold in place.

## 6. Not verified

- **[inf]** Whether a component `add_possessable` reuses or duplicates an existing Scene component binding. The APPLY
  records whichever happens and checks it by resolution.
- **[inf]** Whether `set_display_name` sticks on float/visibility property tracks. klara_reveal relies on it
  (`:2978, :3136`). If it does not, APPLY stops before saving.
- **[inf]** Whether held exposure or lights at KEEP_STATE past the Scene end matter in the next Passage. RESTORE_STATE
  is available through `completion`.
- Nothing here has run in Unreal.
