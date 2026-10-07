# S4 entry v5 (`strike_preroll`): build report (7 Oct 2026, offline)

Nothing ran in Unreal or over MCP. Nothing was committed. Every file I wrote is under
`Saved/CodexConductor/KlaraIngest/`, apart from this report. The predecessor's analysis is
`Docs/Conductor/S4_ENTRY_INVESTIGATION_2026-10-07.md`. I build on it and do not redo it.

**Tiers.** Every claim carries one:
- **[decl]** stated in a header, source, args or doc we can read (file:line);
- **[bytes]** read today from a `.uasset`/`.umap` by the harness reader;
- **[meas]** a value from a live record or DRY JSON;
- **[harness]** a result of the offline tests below. It is a property of the pure code on those inputs, not of
  Unreal;
- **[inf]** inferred, with the reason.

Nothing here is binary-proven: no DLL was read.

## 1. What was built

| File | Status |
|---|---|
| `klara_reveal.py` | edited: new style `strike_preroll` (v5), live v5 gather, DRY logs, APPLY record version 5, REVERT guard |
| `klara_reveal_s4v5_args.json`, `_run.py`, `_request.json` | new: the S4 v5 args (mode DRY, `decided_by` empty), runner, MCP request |
| `klara_preroll_s4.py` + `_args.json`, `_run.py`, `_request.json` | new: the pre-roll sub-section (DRY / APPLY / REVERT, its own record) |
| `klara_pendulum_s4.py` + `_args.json`, `_run.py`, `_request.json` | new: the read-only PIE PROBE, then DRY / APPLY / REVERT of the tick-off event |
| `test_klara_reveal_v5_offline.py` | new: the v5 harness |
| `test_klara_reveal_offline.py` | edited: two stale fixtures fixed (§6) |

**Git note.** `.gitignore:43` (`Saved/Codex*/**`) ignores the three new `*_args.json` files. The existing
`klara_reveal_args.json` is tracked, so it was force-added. The conductor needs `git add -f` for the new three. [meas
`git check-ignore -v`]

### 1.1 `klara_reveal.py` v5

- **Dispatch.** `build_plan` hands off to `build_plan_v5` only when `facts.reveal.style == "strike_preroll"`. The
  check is the first statement of `build_plan`.
  - S1 facts carry no `reveal`, and v4 her_dark_pan carries a different style, so neither reaches v5. [decl, see
    `build_plan`]
  - `_gather_v5` runs only for that style. [decl, see `gather`]
- **Glide-end pose** (`glide_end_pose`). The default mode is `her_cut_pullback`: her cut-frame camera after the level
  move, pulled back 600 cm along the dock axis, raised 120 cm, tilted −10°, at 24 mm. A mode `explicit` takes
  loc/rot/focal from args. All of these numbers are PROPOSED; Gary judges from stills.
- **Strikes.** These are S1's `schedule` and `strike_keys`, unchanged, with seed `KLARA-REVEAL-7OCT|S4`. They run
  over her **character lights**.
  - A character light is any of her lights whose cone and radius cover a subject point (`character_lights` →
    `light_covers`, which ignores occlusion [inf]).
  - Subjects are her level actors whose labels start with `BP_MHC_Child`, `SK_Pigeon`, `Pendulum`, `GC_Old_Book` or
    `Paper_Fall`.
  - Strikes are ordered near→far from the glide-end pose, where the camera rests.
  - Each light strikes to its **plateau**, the sustained lit level from `find_lit_frame`. Set
    `strike_target: "at_cut"` to strike to her value at the cut instead.
  - Lights that are not character lights stay at 0 until the hard cut.
- **Timeline** (`plan_timeline_v5`):
  - glows on during the rise [0, L);
  - dark hold;
  - glide [d0, g1] to the dark pose, with **first strike S0 = d0** (`strike_start_s` 0);
  - strikes inside the glide; they spill into the hold only if they do not fit, which warns
    `STRIKES_SPILL_PAST_GLIDE`;
  - camera at rest, then the **hard cut at C**. The slot starts at her frame 6 (first bound frame, snapped) with
    offset 4800 ticks, as in v4;
  - `timeline.preroll = [S0 − preroll_lead_frames, C)`.
  - The outro is v4's, unchanged.
  - `C = max(hookin cut, need)`, the same rule as v3/v4.
- **The new DRY gate** (`sample_cut_path` + `gate_camera_path`). It samples **every frame and every key time of every
  cut** of her copy inside the slot, plus our glide keys, after the planned move.
  - `CAMERA_PATH_BEHIND_X_MIN` refuses when the camera's dock-local x is below `camera_x_min_local`. The default is
    −600 cm, a PROPOSED value.
  - `CAMERA_PATH_BEHIND_STANDING_BACKCLOTH` refuses when the camera is behind the cloth's front face plus 20 cm,
    inside its y/z span, at a Scene frame where the cloth is **not down**.
  - The cloth state is an explicit **live input**. `_backcloth_state` reads it at DRY time:
    - the actor `P04 Backcloth (baked)`, its location and its bounds now;
    - every GeometryCache section that drives it: directly in `LS_DevScene_04` (the hold the s4_hangar_hold extension
      will write, binding `<prefix><label>`), or inside a sub-sequence (the rise via the Hangar Fold). Sub-sequence
      sections are mapped with `get_parent_sequence_frame` and clipped to the sub-section.
  - `backcloth_down_ranges` counts a frame as down when the cache time is in [`down_cache_s` 9.0, duration 11.0].
    KeepState extends a section **that ends down** to its clip end [inf: KeepState semantics; PIE must confirm].
  - Missing or unreadable state refuses `BACKCLOTH_STATE_UNREAD`. It is **never assumed** up or down.
  - Two further checks: (ii) `GLIDE_END_BEHIND_BACKCLOTH` / `GLIDE_END_OUTSIDE_HANGAR`; (iii) `glide_end_sees`
    (`surfaces_seen` from the new pose).
- **REVERT guard.** `run_revert` now refuses `PREROLL_APPLIED` while `klara_preroll_record_S4.json` is applied. The S1
  path never has that file. [decl]

### 1.2 `klara_preroll_s4.py`

- **Duplicate and strip.** It duplicates the hookin copy to the **new** path
  `/Game/InfinityStage/KlaraHookin/LS_Children_S4Preroll`, then strips it (`classify_bindings`):
  - **every root track** (camera cut, audio). If `remove_track` leaves the cut track, every cut section is removed and
    zero is read back;
  - camera bindings: cut-referenced bindings, `CameraComponent` children and lens tracks;
  - light bindings: Intensity/LightColor tracks, `LightComponent0` children and her light labels;
  - orphans and the children of removed bindings;
  - kept tracks must belong to `KEEP_TRACK_CLASSES`, or the plan refuses.
- **The section.** One new sub track `Klara Preroll - S4` holds one section [P0, C) from her frame **192**, with
  offset 153600 ticks. That is past the pendulum's first key, her frame 191. [bytes]
- **Read-back.** It checks offset, `get_parent_sequence_frame(H0) == P0`, range and sequence. It checks the main slot
  still starts at C. The census must hold exactly `LS_DevScene_04` + the duplicate. It saves those two and reads them
  back after the save.
- **Absolute-keys trap.** The record stores SHA-256 fingerprints of the copy's and the duplicate's transform keys. A
  later DRY refuses `PREROLL_KEYS_STALE` if either changed.
- **REVERT.** It removes the track, saves, deletes the duplicate only if nothing references it, and renames the
  record.

### 1.3 `klara_pendulum_s4.py`

**PROBE** (PIE, read only)
- It arms a Slate post-tick callback. The callback holds only plain Python data and looks every actor up afresh on
  each tick.
- When the Master's Scene-4 time crosses 10 s and 24 s, it logs `BP_Pendulum_C_0`'s location, rotation and
  `is_actor_tick_enabled()` on **3 consecutive ticks**. It stamps each with `run=`.
- It also logs two predictions: LS-only, from the copy's pendulum keys at the mapped her frame (pre-roll or slot);
  and the level placement.
- It writes `klara_pendulum_probe_S4_<run>.json` and classifies the samples (`classify_pendulum`).
- It never saves, never sends a transport command and never ends PIE. It stops itself when PIE ends or after 600 s.
- Where Scene time comes from: a `LevelSequenceActor` playing the Master [inf]. If the transport plays the Master
  some other way, the probe logs `MASTER_PLAYER_NOT_FOUND` and stops, harmlessly.

**APPLY**
- **The gate.** It needs a complete probe whose verdict recommends it, `binding_resolves` must be True, and it needs
  `decided_by` and `confirm`.
- **The writes**, all in `LS_DevScene_04`:
  - a binding `Klara Pendulum - Tick Off: Pendulum_Anchor`;
  - an Event track with one **Repeater** section over [0, Scene end);
  - in that section, `SequencerTools.create_quick_binding(seq, actor, "Set Actor Tick Enabled", False)` and
    `create_event(..., ["False"])`.
- **Then.** It reads back, checks the census, saves only `LS_DevScene_04`, and needs a **re-PROBE** to prove it
  worked.

**REVERT** removes the binding and saves. The director-BP endpoint function stays inside `LS_DevScene_04` until a
backup restore. [inf]

## 2. Why the event route for the pendulum (deliverable 3)

| Route | Verdict |
|---|---|
| (a) Edit her `BP_Pendulum` | Excluded by Gary ("her asset untouched"). |
| (b) Actor-instance tick flag in `L_KK_children` | **Rejected.** `PrimaryActorTick` is `UPROPERTY(EditDefaultsOnly)` [decl `UE_5.8 Engine/Classes/GameFramework/Actor.h:317-318`]. `bStartWithTickEnabled` is EditDefaultsOnly and `bCanEverTick` is "only settable in defaults" [decl `Engine/EngineBaseTypes.h:211-217`]. Property access flags instance edits of such properties `CannotEditInstance` [decl `CoreUObject/Public/UObject/PropertyAccessUtil.h:40-41`]; that Python's `set_editor_property` is refused by it is [inf]. It would also write Klara's level, which a `klara_copy.ps1` re-run erases [decl memory klara-streamed-levels-traps]. |
| (c) **Chosen:** a Show-side Sequencer event in our `LS_DevScene_04` | The API exists: `SequencerTools.CreateQuickBinding` / `CreateEvent` / `IsEventEndpointValid` [decl `SequencerScriptingEditor/Public/SequencerTools.h:248-277`]; `MovieSceneEventTrackExtensions.AddEventRepeaterSection` [decl `SequencerScripting/Public/ExtensionLibraries/MovieSceneEventTrackExtensions.h:33`]; the Repeater's `Event` UPROPERTY is EditAnywhere [decl `MovieSceneTracks/Public/Sections/MovieSceneEventRepeaterSection.h:30-31`]. Not proven: that it fires inside a nested Scene under the Master, that it survives transport jumps, and that the Python names match. These are [inf]; the DRY's `api_table` probes them, and the re-PROBE proves the effect. |
| (d) C++ | **Fallback spec only**, if (c) fails its re-PROBE. Add a Scene-cue property `TArray<TSoftObjectPtr<AActor>> TickSuppressedActors`. On Scene activation the transport calls `SetActorTickEnabled(false)` and records the prior state, and restores it on Scene exit. It needs a build and Gary's yes. No code is written. |

## 3. Harness results [harness]

Both harnesses were run on 7 Oct with `python <file>` (Python 3.14.7):

| Harness | Result |
|---|---|
| `test_klara_reveal_v5_offline.py` | **27/27 pass** (40 s), including **14/14 seeded mutations caught** of v5, pre-roll and pendulum code |
| `test_klara_reveal_offline.py` | **75/75 pass**, including its 15/15 v4 mutations. At the start of this session it was **71/75**: see §6 |

**The checks Gary's brief asked for.** Every positive check has a control that fails.

- **S1 unchanged.**
  - (a) Replaying the live S1 DRY (`klara_reveal_dry_S1.json`) reproduces its recorded plan. Control: L+1 differs.
  - (b) **HEAD `klara_reveal.py` (via `git show`) and the new code give byte-identical plan JSON** on three inputs:
    the S1 DRY facts, the synthetic v3 facts, and the S4 v4 her_dark_pan facts.
  - `detect_lit` is also identical on those inputs.
  - Control: on v5 facts the two codes give different plans.
- **Whole-path gate.**
  - With the backcloth STANDING it FAILS `CAMERA_PATH_BEHIND_STANDING_BACKCLOTH`: her CineCameraActor, 2312 samples,
    Scene frames 946..2871, min dock-local x −428, cloth front x 10489. "Down" is only [26, 775).
  - With the backcloth HELD it PASSES: down [26, 4890), and it warns `CAMERA_BEHIND_BACKCLOTH_PLANE_WHILE_DOWN`, which
    is a stills check.
  - Control: a first-frame-only gate passes the standing state. That is the v4 blind spot.
  - Control: `camera_x_min_local` 0 fails, and −1000 passes.
  - An unread or missing cloth state refuses.
- **Strike schedule.** It is deterministic within a process and across `PYTHONHASHSEED` 0, 1 and 12345. A different
  seed gives different frames. A source scan finds no line with two `rng.` draws, and the v5 block has no draws of
  its own.
- **Pre-roll range.**
  - It equals [first strike, cut) = [119, 376).
  - Control: lead 3 gives [116, 376).
  - Control: `strike_start_s` 1.0 moves the start by exactly 25 frames.
- **Pre-roll strip on the copy's bytes.**
  - It keeps the 7 children (actor, Body, Face), Floor, GC_Old_Book (+ its component), Paper_Fall, Pendulum_Anchor
    and SK_Pigeon_01.
  - Everything kept resolves into `/Game/L_KK_children`.
  - It removes 3 cameras and 3 CameraComponents, 7 SpotLights and 12 `LightComponent0`, which includes the 5 orphans.

## 4. The v5 projection on the live S4 DRY facts

These are not live numbers. The facts are [meas] `klara_reveal_dry_S4.json`, run KLARAREVEAL-20261007-095026 (the
pre-apply state a REVERT restores). The subject points and cut curves are [bytes]. The backcloth state is HELD
(SYNTHETIC). The live DRY decides the real numbers. [harness]

| Quantity | Value |
|---|---|
| Placement | lead 1459 cm, delta (−2204.3, −301.5, 0): unchanged from v4 |
| Her cut camera | (12127.7, 240000, 91), her frame 6 |
| **Glide-end pose** | (11527.7, 240000, 211), pitch −4, yaw 5, 24 mm. It sits behind the children (world x 11680–11880 [bytes]), looking +x over them toward the pendulum. It sees the set only (45/45 rays). |
| Glide | [119, 269], 6.0 s, 860 cm, peak 215 cm/s |
| Strikes (6, all inside the glide) | SpotLight3 119, SpotLight5 134, Spot_MainLight_window 153, SpotLight4 174, SpotLight 200, SpotLight2 216 |
| Not struck (cover no subject) | SpotLight6 (a 60 cm-radius practical) and SpotLight7 |
| Hard cut | 376 (the hookin cut; no shift). Camera at rest [269, 376) = 4.3 s |
| Slot | [376, 4471), from her frame 6 |
| Pre-roll | [119, 376), her frames 192 → 500.4 |
| Planned end | 4861 = **194.44 s** (live is 4890 = 195.6 s): `RELENGTH_FIRST` |

## 5. Backcloth (deliverable 4: read-only, no tool written)

**The cause** comes from the conductor's own finding, which this report references and does not re-derive [meas]:
- The `P04 Backcloth (baked)` GeometryCache track lives in `LS_S4_HangarRise`.
- `LS_DevScene_04` plays that only over the Hangar Fold [0, 775), and past that it is not held
  (`s4_hangar_hold_dry_S4HOLD-20261007-102800.json` plan.not_held_rise_tracks).
- The same mechanism was measured for S3's pinned-exposure weight: 1.0 at +30 s, 0.0 from +33 s.
- Another agent is extending `s4_hangar_hold.py` to hold float and GeometryCache rise tracks.
- **The v5 gate reads exactly that hold.** Any active GC section on a binding named `…P04 Backcloth (baked)` in
  `LS_DevScene_04` counts. The gate passes only if "down" covers her pull-back frames.

**How it is authored now.** Read-only by a subagent, re-checked against the files cited:
- **The actor.** `P04 Backcloth (baked)` stands at (10450, 240000, 0). Its cache is
  `/Game/Scenes/Curtain/Baked/GC_CurtainBackcloth_P04`, bake `final11_backcloth_p04_a06`: 11.0 s, release 1.0 s in.
  [meas `Saved/CodexStructure/p04_backcloth_section_record.json`]
- **The section.** It is one GC section in `LS_S4_HangarRise` on binding `3775D9A8…` [decl
  `Saved/CodexStructure/p04_backcloth_section_apply.py:203-219`]:
  - range [−7.0326, +3.0008] s motion time;
  - offset 23200 ticks;
  - KeepState;
  - run BLF-20261006-015230 [meas `backcloth_lead_fit_record.json` section_live_after].
- **Who drives it.**
  - Before the cut, the Arrival C++ drives it [decl `InfinityStageArrival.cpp:1161-1182`].
  - From the Scene's first frame, Sequencer drives it [decl `:1110-1114`].
- **Why "we walk straight through it"** [decl `GARY_PIE_NOTES_2026-10-05.md:94-99`]. That was the 5 Oct timing on the
  180 s P04. The 6 Oct lead fit restored a 5 s lead [meas `backcloth_lead_fit_record.json`]. So the **drop** is
  authored. The **hold** past frame 775 is missing.

**Do P01/02/03/05 drop and hold?** The end-frame/REST trap applies.

| Scene | Drape section (motion s) | Hangar Fold | Scene length | Covers the Scene? |
|---|---|---|---|---|
| S1 | [−5.90, 4.13] | [0, 775) | 6176 | no |
| S2 | [−5.90, 4.13] | [0, 775) | 2025 | no |
| S3 | [−5.90, 4.13] | [0, 744) | 6240 | no |
| S5 | [−3.60, 6.43] | [0, 1225) | 1225 | **yes** |

- Values are [meas `passage_end_drape_record_S{1,2,3,5}.json`; fold and Scene lengths from the S4HOLD dry survey].
- Every section ends inside its fold with KeepState. Past the fold, S1–S3 are in the same unheld state as S4 [inf,
  same mechanism].
- The planner itself marks "KeepState holds the end" as [inf] [decl `passage_end_drape.py:222-227`].

**Steps to make S4 drop and hold through the whole Scene.** No tool from me, per the conductor.
1. **The drop: no change.** It releases at Scene −7.0 s and lands by +3.0 s [meas].
2. **The hold.** The s4_hangar_hold extension (the other agent) writes a GC section in `LS_DevScene_04` over
   [775, Scene end):
   - it binds the same actor;
   - the cache sits at its last sample (≥ 9.0 s, ≤ 11.0 s) with a tiny play rate or an EndFrameOffset, so it never
     loops [inf: a section longer than the cache loops, decl `passage_end_drape.py:469-471`];
   - KeepState;
   - it must not overlap the rise's section.
   - **The Scene end is 4861 after the v5 relength**, so re-run the hold DRY after `extend_scene_playback` [decl memory
     hangar-rise-bounded-by-scene-length].
3. **Check.**
   - v5 DRY: `KLARAREVEAL_V5_BACKCLOTH` lists the hold and `down_ranges` ⊇ [26, 4861). The gate has no
     `…STANDING_BACKCLOTH` refusal.
   - PIE stills at about 600, 776, 1050 (42 s), 2871 and 4860, plus one after a transport jump into mid-S4. Re-pose
     before each capture (async GC decode).

**Owner of `passage_end_drape.py`.** It is the **conductor's tool** [inf]:
- It lives in `Saved/CodexConductor/`.
- The 5 Oct notes say "tool being written offline (passage_end_drape.py)" [decl
  `GARY_PIE_NOTES_2026-10-05.md:37-38`].
- Its commits are 9ee6297 and 70c8ebf on 5 Oct. Git shows only the shared identity "Zhexi Zhang" [meas `git log`].
- **Applied by both streams:**
  - S1/S2/S5 on 7 Oct 02:44, `decided_by` "…W&T session";
  - S3 at 08:02, "…conductor session" [meas records].
- No ownership doc names it.

## 6. The existing harness was red at the start (fixture faults, named)

At the start of this session `test_klara_reveal_offline.py` gave **71/75**. These were fixture faults, not code
faults [meas: the first run]:

| Assertion | Cause | Fix |
|---|---|---|
| `Plan.test_full_plan`: `hide.labels [] != ['S1 Hangar Roof']` | The live args now carry Gary's S1 `roof: keep`. | The harness pins the global `hide_roof` for S1. |
| `S4Bytes.test_copy_shift_equals_level_transform` (2204.30 off) | The copy is now shifted for the **live** v4 LT (11435.67, 239706.98), not the hookin's. | `S4_LT` is now measured from the bytes. It must equal the hookin LT or the applied record's `level_transform_after`. Control: not zero. |
| `S4Reveal.test_darkness_at_her_first_frame`, `test_dark_pan_plan` | The same stale LT put her camera 22 m from her lights (lit fraction 0.32). | Fixed by the same change. |

**A new [bytes] finding.** In the **copy**, the 5 orphan `LightComponent0` bindings have **no** parent binding
reference. In her original, those references point at L_Animals SpotLight_1/17/20/22/23.
- So through the copy, S4 does not drive S1's lights. That settles the investigation's open [inf] on this point.
- The pre-roll strip removes them anyway.

## 7. Run order for the conductor (DRY → APPLY)

Gary is in PIE. Every editor step waits until PIE has ended, except step 1, which needs PIE.

**Request files.** Each tool has one MCP request: `klara_reveal_s4v5_request.json`, `klara_preroll_s4_request.json`,
`klara_pendulum_s4_request.json`. Each runs its `*_run.py`, which reads the matching args file. Edit `mode`,
`confirm` and `decided_by` in that args file between steps.

0. **Snapshot.** Take `Backups/PreS4EntryV5-<ts>` of `LS_DevScene_04`, `LS_Children_S4Hangar`,
   `L_InfinityStage_V1VerticalSlice.umap` and `L_KK_children.umap`.
   - **Precondition:** the s4_hangar_hold GC hold must be applied first. Otherwise step 4 refuses by design.
1. **Pendulum PROBE** (now possible, in Gary's or a conductor PIE run of S4):
   - `klara_pendulum_s4_args.json` mode `PROBE`. Send `klara_pendulum_s4_request.json` **before** S4 reaches 10 s.
   - Wait for `KLARAPENDULUM_PROBE_OK|run=<id>` (parse by marker and run id).
   - Read `klara_pendulum_probe_S4_<run>.json`.
   - 24 s maps to her frame 240 under the live v4 cut 405 [harness `Pendulum.test_her_frame_mapping`].
2. **klara_reveal REVERT** of the live v4 S4:
   - `klara_reveal_s4v5_args.json`: mode `REVERT`, confirm `REVERT KLARAREVEAL`.
   - Send `klara_reveal_s4v5_request.json`, then expect `KLARAREVEAL_REVERT_OK|run=`.
3. **klara_reveal v5 DRY:** mode `DRY`. Expect `KLARAREVEAL_DRY_OK|…|apply_ready=1`.
   - Read the `KLARAREVEAL_V5_*` lines: GATE, BACKCLOTH, GLIDE_END, STRIKES, PREROLL.
   - It prints the `extend_scene_playback` mode (projection 194.44 s).
4. **Relength.**
   - `extend_scene_playback.py` with the printed mode.
   - Then re-run the s4_hangar_hold DRY/APPLY to the new end. The hangar and the backcloth hold must reach it.
   - Re-run the v5 DRY to confirm `relength_first` is gone.
5. **klara_reveal v5 APPLY:** fill `decided_by`, confirm `APPLY KLARAREVEAL`. Expect `KLARAREVEAL_APPLY_OK|run=`.
6. **klara_preroll_s4 DRY**, then **APPLY:**
   - `klara_preroll_s4_args.json` mode `DRY`. Read every `KLARAPREROLL_KEEP` and `KLARAPREROLL_REMOVE` line.
   - Then mode `APPLY`, confirm `APPLY KLARAPREROLL`, `decided_by` filled. Expect `KLARAPREROLL_APPLY_OK|run=`.
7. **Pendulum DRY**, then **APPLY**, only if the probe verdict recommends it:
   - mode `DRY`, then `APPLY` with confirm `APPLY KLARAPENDULUM`.
   - Then **re-PROBE in PIE**. Re-derive the times from the v5 cut 376: her frame 191 is at Scene ≈ 530 (21.2 s), so
     24 s is still valid. `tick_enabled` must read False in S4, and the rotation must equal her keys.
8. **Tests and builds:**
   - `rebuild_managed_master`;
   - SavedMasterMatchesShow (the real test, not swapkit);
   - SceneCutBindingsResolve and the live `check_scene_cut_bindings`;
   - the suite.
9. **PIE stills:**
   - at L, mid-glide, each strike (119…216), C−1, C, C+1 (375/376/377), and her rest pose (≈42 s, frame ~1050);
   - check the curtain pile, the pre-roll boundary (no T-pose or level pose at C) and the pendulum angle;
   - re-pose the GeometryCache before capturing.

**REVERT order:** pendulum REVERT (independent) → preroll REVERT → klara_reveal REVERT. The reveal REVERT refuses
`PREROLL_APPLIED` otherwise.

## 8. Open look calls for Gary

None of these numbers is his yet.

1. **The dark glide-end framing.** The default is the pull-back wide described in §4. The alternative is an
   `explicit` pose in the args.
2. **The light drop at the hard cut.** SpotLight, SpotLight2 and SpotLight4 strike to their plateau (160 / 160 /
   108), but her own shot opens with them at **0**: her dark opening. So her shot begins darker than the struck
   view. The DRY warns `V5_LIGHT_DROP_AT_HARD_CUT`. The other option is `strike_target: "at_cut"`, which leaves those
   three dark, so the children are never struck.
3. **A 4.3 s rest before the cut.** The cut cannot come earlier than the hookin's cut of 376 under the current rule.
   An earlier cut would need the slot moved earlier, which no tool does today.
4. **Which lights strike.** The six "character lights" were chosen by geometric cover. Gary may want a subject order
   instead: children, then pigeon, then pendulum.
5. **Her environment.** Her sun, sky and fog ramp up over the strikes [119, 366] toward her values at frame 6. That
   lightens "near-total darkness" during the glide.
6. **The rig.** `lattice: cancel` keeps the rig up, as in S1. "Rising into place" may mean letting it move instead.
7. **The pre-roll start**, her frame 192 (PROPOSED). The pendulum is static before frame 191.
8. **The Scene length**: 194.44 s against 195.6 s live. That is −1.16 s, from the her_dark_pan cut shift that v5 does
   not need. Cues past the end are listed in the DRY's `plan.audio`.

## 9. Searched, found nothing in

- **A show-side tick suppressor.** The plugin source has no mechanism to disable a foreign actor's tick. Grep for
  `SetActorTickEnabled`, `bStartWithTickEnabled` and similar finds only our cat, effect and bee components
  (`InfinityStageCameraRig.cpp:563`, `ShadowCatComponent.cpp:57-58`).
- **A GeometryCache hold writer** in `Saved/`, `Tools/` or `Scripts/` (subagent grep). That is the reason for the
  s4_hangar_hold extension.
- **The engine `.cpp` for GC sections and for events in sub-sequences.** It is not installed on D:, so KeepState,
  looping and nested-event firing are [inf] here.
