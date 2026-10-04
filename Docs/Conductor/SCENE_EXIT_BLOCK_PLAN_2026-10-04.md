# Scene exits: curtain, puppet minute, door (BLOCKING plan, 4 Oct, offline)

**Status: planned and tooled offline. NOTHING has run in Unreal.** The tool, the DRY runner and the
harness are in `Saved/CodexConductor/`. The harness passes **86/0** (`test_scene_exit_block_output.txt`).
The option B harness it reuses still passes 57/0. Both were measured by running them on 4 Oct.

Tiers (AGENTS.md), per claim: **[decl]** declaration-proven (source, header or file read here);
**[bin]** binary-proven; **[meas]** measured (an intervention and its read-back; here, either an
earlier editor probe, dated, or the offline harness); **[inf]** inferred, with the reason.

## 1. The ask

Gary, 4 Oct: *"It's a door but the curtain hangs over it and we have a 1min cat boy shadowpuppet scene
on it first, just block for now."* (`Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:81`) **[decl]**.
Read as: a curtain hangs over each hangar's hidden exit door; a ~60 s puppet scene plays on it; then
we go through the door. Placeholder level only. This **supersedes options A and C**
(`SCENE_EXIT_OPTIONS_2026-10-04.md`). Option B's door camera and leaf swing are reused for the
"through".

## 2. The block, per Scene

```
 ...Scene content...| PUPPET MINUTE (60 s)        | fly-out 3 s | B: 1.5 s door, leaf swings, walk | hold 1 s |
                    W0 = old end                                                                 W1        new end
 camera:  (Scene's) | CUT -> "S<N> Exit Block Camera" at B's seat, 9 m from the door, locked ...walks through | black
 curtain: hung over the door, the whole Scene    | rises 498 cm | stays up ........................................
 card:    "puppet screen" on the curtain front   | rises with it
```

- **Curtain.** This is a `Cube` box, 2 × 700 × 600 cm. Its centre plane sits 60 cm in front of the door
  face and its hem is 2 cm above the door floor. It uses the existing curtain MI
  `/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop` **[decl: the asset exists on disk]**.
  Its static-mesh usage is **not verified [inf]**: it is a GeometryCache drop's MI, and APPLY loads it
  live.
- **Puppet screen (the media slot).** This is a 480 × 270 (16:9) card, 1 cm in front of the curtain and
  centred on the eye line. It is tagged `ShadowPuppetScreen.S<N>`.
  - **No MediaTexture or flipbook material exists** in `Content/InfinityStage`, `Content/Scenes` or
    `Content/Materials` (a byte search of the .uasset files for "MediaTexture" and "Flipbook" found
    0 hits) **[meas: search]**.
  - The puppet spec rules out video playback, because it is not scrub-safe. The spec wants a flipbook
    with a Sequencer-keyed frame parameter, as a **light function** on the front lantern
    (`Docs/ShadowPuppetCaptureSpec.md` §7) **[decl]**.
  - So the card carries a plain lit `/Engine/BasicShapes/BasicShapeMaterial` **[decl: the engine file
    exists]**. It is not emissive, and nothing lights it (the `CARD_IS_PLAIN_LIT` warning).
  - The puppet beats are Sequencer **marked frames**: `EXB puppet start`, `EXB curtain out`,
    `EXB curtain gone`, `EXB door opens` and `EXB through (exit hold)`. The API is precedented in
    `opening_sequence_apply.py:291-318` **[decl]**.
- **Fly-out.** The curtain and the card rise together, smoothstep, over 3 s. They clear both
  thresholds below with a 50 cm margin. Raise = **498 cm** in every Scene **[meas: offline planner]**.
  - The door top, so the 449 cm leaf can swing under the hem.
  - The top edge of every later frame at the curtain plane. At 35 mm and 840 cm that edge is about
    310 cm.
- **Through.** This is option B unchanged: 1.5 s on the closed door, a 3 s swing to 100° on the left
  jamb, and a walk at 250 cm/s into the Exit Black, ending 25 cm short of it. It lasts 7.64 s
  **[meas: offline planner]**.
  - The B planner is **reused, not copied**. Its pure section (above `def _here`) is parsed and
    executed with `FPS` set to the Scene's rate, and checked for API drift.
  - The harness proves that the B keys are byte-identical to `scene_exit_move.plan_exit_move` at the
    same end **[meas]**.
- **The camera is locked** through the puppet minute. That fits Gary's 4 Oct "keep all camera locked"
  (`MORNING_SUMMARY_2026-10-04.md:82`) **[decl]**.

## 3. Where the 60 s lives (measured from source): lengthen each Scene

**How the Show times a Scene.** With `bUseSequenceLength`, a Scene's length *is* its Level Sequence's
playback range, converted to Show ticks. Otherwise it is `DurationFrames` (`InfinityStageCompiler.cpp:17-40`,
used at `:217-226`; default `false`, `InfinityStageTypes.h:804-807`) **[decl]**. Adding the minute
inside the Scene's sequence therefore lengthens the Scene's Show segment, and every later segment
moves by the same amount.

**Room inside the current lengths?** None that works. The current lengths are below; they are the last
**[meas]** values (the DRY re-reads them live).

| Scene | End (frames @ fps) | Seconds | Source |
| --- | --- | --- | --- |
| S1 | 5270 @ 25 | 210.8 | `probe_interaction_cut_binding.json`, 30 Sep |
| S2 | 775 @ 25 | 31.0 | `nest_s2_record.json`, 3 Oct |
| S3 | 1573 @ **24** | 65.5 | `extend_scene_playback_scene3_refused.json` |
| S4 | 775 @ 25 | 31.0 | `probe_interaction_cut_binding.json`, 30 Sep |
| S5 | 1225 @ 25 | 49.0 | `extend_scene_playback.json`, 3 Oct |
| S6 | 775 @ 25 | 31.0 | `nest_s6_record.json`, 3 Oct |

- The block needs about 71.6 s. Only S1 is long enough, but S1's `LS_Animals_1` shot covers all of S1,
  `[-1, 5270]`, with 4 nested cuts, and nested shot cuts outrank root cuts (memory, measured 30 Sep).
  So the minute would have to replace S1's own content.

**Recommendation: append the block after each Scene's content, and lengthen the Scene by exactly the
block.** Use Soft goods' existing `extend_scene_playback.py`, which does the end, the rematch, the
coverage gate, the Master rebuild and the exact saves (`:8-33`) **[decl]**.
- **Growth** **[meas: offline planner]**:
  - S1, S2, S4, S5, S6: **+1791 frames = +71.64 s** each (60 + 3 + 7.64 + 1).
  - S3 at 24 fps, starting at ClamCam1's end (§5): **+68.62 s**.
  - In total the Show grows by about **427 s (7.1 min)** **[arith]**. The Opening plan adds another 81 s
    (`OPENING_SEQUENCE_PLAN_2026-10-04.md` §3) **[decl]**.
- **Patch K.** It makes the Master rebuild carry later Passage keys with their moved sections:
  - `MoveSection` comes before `SetRange` (`InfinityStageSequenceBuilderLibrary.cpp:299-308`) **[decl]**.
  - The test name `PassageKeysFollowSection` is present in `UnrealEditor-InfinityStageEditor.dll`
    (2 Oct 19:38) **[bin]**. Controls: `SavedMasterMatchesShow` is present; a made-up name is absent.
  - The test passed on 2 Oct (`Saved/Logs/SS-FullInfinityStage-20261002.log:2776`) **[meas]**.
  - So lengthening no longer strands later Passage scores.
- **The key gate.** `extend_scene_playback.py`'s KEY GATE still refuses whenever a later Passage has a
  varying channel (`:193-218, 306-312`) **[decl]**.
  - Whether any Passage after S1–S6 varies today is **UNCLEAR**. On 30 Sep only P01 varied, and P01
    comes before S1. Walk-in keying since then may have added others. The extension's own DRY reports
    it.
  - If it refuses, relaxing the gate now that K is built is a Soft goods change and needs its OK.
- **The builder's rematch.** After the block's cut `[W0, W1)` is added, the builder sets Entry to
  `[start, first interior start)` and the retained Exit to `[last interior end, end)`
  (`InfinityStageSceneHandoffBuilder.cpp:396-461`, `:440`, `:447`, `:461`) **[decl]**.
  - So Entry becomes `[0, W0)` and Exit becomes `[W1, new end)`. The Exit copies the block camera's
    saved final pose, which is black.
  - The Interaction keeps retaining it, as before.
- **Music.** A Scene whose music mode is Start or ExplicitCrossfade gets a rail spanning its whole
  segment (`InfinityStageSequenceBuilderLibrary.cpp:440-476`) **[decl]**. So the minute inherits that
  music. Which Scenes have a music mode set was not read **[inf]**. What the puppet minute
  should sound like is undecided.
- **Rejected for now:** a separate "Exit N" Show cue (a Sequence cue with `bRetainPreviousCamera`)
  between each Scene and its Interaction.
  - The builder allows it, because a Scene's next segment may be a retain-camera cue (`:189-206`)
    **[decl]**.
  - It is cleaner on paper (its own segment and music, and the Scene sequences are untouched), but it
    means Show writes and six new sequences. The hangar actors are also bound in the Scene sequences.
  - Worth revisiting when the puppets are real.

## 4. Order of operations (per Scene, each step its own approval)

1. **DRY** with `scene_exit_block_dry_run.py`. It is read-only. It writes `scene_exit_block_plan_S<N>.json`
   (content_end, new_end) and `scene_exit_block_S<N>_dry.json`, and prints the
   `extend_scene_playback_mode.json` to use.
2. **Extend** with Soft goods' `extend_scene_playback.py`, mode
   `{"scene_label": "Scene N — External Sound", "new_end_frame": <new_end>, "dry_run": true}`. Run DRY,
   then APPLY. Then run `SavedMasterMatchesShow`.
3. **DRY again**. The state must now be `extended`.
4. **APPLY.** It needs `scene_exit_block_overrides.json` (shape below). It backs up to
   `Backups/PreSceneExitBlock-S<N>-<run>/` (the Scene sequence, the level and the Show), then:
   - spawns the curtain, the card and the camera on the **live** hangar root;
   - keys the camera, leaf, curtain and card, the focus track, one cut `[W0, W1)` and the markers;
   - runs `match_named_scene_handoffs`;
   - gates coverage and the dirty census;
   - saves **only** the sequence and the level;
   - reads back the bindings, the key counts, the cut ranges, the Exit range, the markers and the actor
     poses.
   It logs `SCENE_EXIT_BLOCK_APPLY_OK`. Then run `SceneCutBindingsResolve` and `SavedMasterMatchesShow`,
   one at a time.
5. **Look.** Take PIE stills of the puppet hold, the fly-out and the door. Nothing here has been seen.
6. **REVERT**, if needed. It removes exactly what the record lists, rematches and checks that the cuts
   and markers equal the pre-apply state. **The Scene stays long**: shorten it with
   `extend_scene_playback.py` `new_end_frame = content_end`, which the REVERT_OK line prints.

```json
{"decided_by": "Gary", "decision": "4 Oct: curtain over the door, 1 min shadow puppet, block",
 "scenes": [2], "params": {}, "scene_params": {"3": {"s3_backdrop_cut": false}}}
```
The tool never writes this file. A peer's "approved on Gary's word" is not Gary's yes (memory).

**Guards.** The tool refuses with PIE running (it never ends PIE), with the Sequencer open, in the wrong
world, with anything dirty before it starts, or with `ZZ_` actors present. It never reloads the level
and never saves anything it did not intend to (no Save All).
- **Composition is against the live hangar root.** The root must equal the landed root the doors tool
  recorded on 3 Oct (`hangar_exit_doors_record.json` `root_before`), within 0.5 cm and 0.05°, or
  `ROOT_NOT_LANDED`.
- **Inside-box guard.** Every spawned box, hung and raised, must lie inside the hangar interior in the
  root frame: x in [0, door face], |y| ≤ half_w, z in [floor, height]. This is checked offline on the
  plan and again on the spawned actors' world bounds.

## 5. Per-Scene findings

| | S1 | S2 | S3 | S4 | S5 | S6 |
| --- | --- | --- | --- | --- | --- | --- |
| Offline DRY | **pass** | **pass** | **refuses** | **pass** | **pass** | **pass** |
| Door from dock | 65 m | 65 m | 65 m | 65 m | **155 m** | 65 m |

- **S3 refuses twice** **[meas: harness, on the real door record]**:
  - `S3_BACKDROP_BEHIND_LEAF`. The leaf is the cropped backdrop image, 0.05 cm in front of the
    uncut `S3 Backdrop` (`hangar_exit_doors.py:204-240`, record `surface_strategy:
    cropped_texture_child_mi`) **[decl]**. An open leaf would reveal the same art behind it.
  - `TAIL_GAP`. ClamCam1 `[81, 1501)` is the last interior root cut, so after the rematch nothing would
    cover `[1501, 1573)`. The source is the 30 Sep probe, so this is **[meas, stale]**.
  - It passes with `s3_backdrop_cut` and `start_at_last_interior_end` (the block then starts at 1501).
  - The backdrop hole is still needed for a real door. Without it, S3 could do the curtain and puppet
    minute and then cut without the door (a decision, not built).
- **S3 is 24 fps** **[meas, stale]**. `scene_exit_move.py` refuses any non-25 fps Scene
  (`scene_exit_move.py:597-599`) **[decl]**. The block runs B's planner at 24 fps instead, and the
  harness checks that the override changes the frame counts **[meas]**.
- **S5 is 155 m deep.** That is irrelevant to the block, which is a cut, so S5 gets the same 71.64 s.
  The 150 × 200 m room and the 5000 cm height leave room for the fly-out **[meas: inside-box check]**.
- **All six: the hangar-rise section ends at or before W0.** S1 and S4 end at 775; S2, S5 and S6 end
  at the Scene end (`nest_s*_record.json`); S3 ends at 744.
  - So for the whole block the rise is no longer evaluated (`RISE_SECTION_ENDS_BEFORE_BLOCK_END`
    warning).
  - What the hangar shows then is **UNMEASURED**. That covers its pose and the lights keyed in the
    rise, where the glow "rests at 0 cd" (`RigAndAtmosphere_Handover_2026-09-28.md:502`) **[decl]**.
  - The pose should be fine, because the level is saved LANDED (memory, 2 Oct) **[inf]**. The lights
    may drop **[inf]**.
  - S1 has had about 179 s past its rise since 30 Sep, and nobody has reported a drop. That is not a
    measurement.
  - Fix, if needed: Rig & atmosphere extends each rise section to the new end.
- **The Exit Black is metal black** (all six). It reads tan under warm light (memory, measured 30 Sep).
  The warning is carried over from B.

## 6. Decisions needed (recommendation first)

1. **Lengthen each Scene by about 71.6 s** (recommended), against a separate Exit cue per Scene. The
   Show grows by about 7.1 min.
2. **Should the curtain hang all through the Scene?** Recommended: **yes**, as the literal reading of
   "hangs over it". It is a red 7 × 6 m rectangle about 16% of frame width at 65 m **[arith, 35 mm]**.
   In **S3** it covers 7 × 6 m of the Opal Beach backdrop all Scene. Alternative: fly it in at W0.
3. **S3:** cut the backdrop for a real door, or block S3 as curtain plus puppets and then cut, with no
   door?
4. **Sound for the puppet minute:** the Scene's music carries on (the default), or silence, or a cue?
5. **Light on the screen:** the block adds none, and the card may read dark. Add a placeholder work
   light (a look write) or wait for the lantern and light-function route?
6. **Key gate:** if the extension DRY refuses on a later Passage's varying channel, may Soft goods relax
   the gate now that K is built?

## 7. Unproven (everything below runs only in the editor)

- None of `scene_exit_block.py`'s Unreal side has ever executed. Every call has an in-repo precedent:
  `scene_exit_move.py` (also never run), `hangar_exit_doors.py` (applied 3 Oct) and
  `opening_sequence_apply.py`.
- The transform channel names, and that `Scale.*` defaults stop an unkeyed scale from evaluating to 0
  **[inf]**.
- That a transform track on an attached actor keys relative transforms **[inf]**. The same assumption
  is in B.
- The marked-frame Python method names: `get_marked_frames_from_sequence`,
  `add_marked_frame_to_sequence`, `sort_marked_frames`, `delete_marked_frame` **[decl: header
  `MovieSceneSequenceExtensions.h:532-599`; the Python spelling is inferred]**.
- The Python name of `bUseSequenceLength`. The tool tries `use_sequence_length`, then
  `b_use_sequence_length`, and refuses if neither reads **[inf]**.
- That the curtain MI renders on a static mesh **[inf]**.
- The loader runs scene_exit_move's top-level code, which is only assignments, imports, functions and
  the docstring. Its side-effect screen rejects bare calls and `if` blocks, but **not** calls inside
  assignments. Today those are only `os.path.join` **[decl]**.
- The visual result: puppet framing, the fly-out and the door read. Nobody has seen any of it.
