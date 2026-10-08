# S1 animals snap at the reveal cut: investigation (8 Oct 2026, read-only, offline)

Gary, 8 Oct: the S1 animals sit in an "idle" while the lights blink on, then snap into a more animated animation.
Nothing was run in Unreal, no MCP call was made, and nothing was edited apart from this file. Tiers are used per claim:
**[decl]** a header, config or JSON we can read · **[bin]** recovered from a .uasset or .umap with the in-repo offline
reader · **[meas]** an existing record or log from a live run · **[inf]** inferred, with the reason it is unverified.

The offline reader is `Saved/CodexConductor/S3Diag/s3_seq_sem.py`, the same one that produced `S1Snap/*_sem.json`.
`*_sem.json` does not decode `MovieSceneSkeletalAnimationTrack.AnimationSections`: it lists them as paths only, with
`sections: []` (`S1Snap/LS_Animals_1_S1Hangar_sem.json`, tracks 9/24/28). The skeletal sections below came from a
scratch extension of that reader that decodes each `AnimationSections` export through `Model.props`. It opened the
files read-only. To reproduce: `Model(path)`, then for each `track_props["AnimationSections"]` path call
`m.props(m.by_path[path])`.

## Verdict in one screen

- **Cause.** Before Scene frame 594 nothing evaluates the animals, so they hold their **level pose**. At 594 the copy's
  sub-sequence starts. It lands **3.07 s into eating loops** that have no ease (Pig `Eat_loop_1`, Deer `Eat_loop`,
  Raccoon `Eating`). The section on LS_DevScene_01 has empty `Easing`, so the pose goes from the level pose to
  mid-eat in one frame. [bin + meas]
- **The "idle" is probably not an animation.** No idle asset is assigned in the level. Pig and Deer are saved in
  `AnimationCustomMode`, and the Raccoon is saved with the class-default mode and no AnimClass. [bin] So they probably
  stand **static** in a stored or reference pose until 594. [inf, see §1]
- **Recommendation.** (b) Ease In on the CinematicShotSection in **LS_DevScene_01 only**. That is one field pair and
  one asset, and it reverses cleanly. Before it is applied, a live bench must prove that sub-section easing blends
  skeletal animation (§4). If Gary wants the animals already moving while the lights strike, use (c): the stripped
  pre-roll duplicate, after the `klara_preroll_s4.py` precedent. That writes LS_DevScene_01 plus a new asset of ours.

## 1. Which actors are "the S1 animals"

| Label | Class | Level | Mesh | AnimationMode | Anim asset in level |
|---|---|---|---|---|---|
| `Pig_anim_RM` (`SkeletalMeshActor_13`) | SkeletalMeshActor | `/Game/KK_S1_Animals/L_Animals` | `Pig/pig_fbx/Pig_anim_RM` | `AnimationCustomMode` | none |
| `RedDeer_Calf_anim_IP` (`SkeletalMeshActor_15`) | SkeletalMeshActor | same | `Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP` | `AnimationCustomMode` | none |
| `medhue_raccoon` (`SkeletalMeshActor_7`) | SkeletalMeshActor | same | `Raccoon/medhue_raccoon` | not serialized (class default) | none |

- **The table** comes from the export props of `Content/KK_S1_Animals/L_Animals.umap` [bin]. Pig and Deer also carry
  `VisibilityBasedAnimTickOption = AlwaysTickPoseAndRefreshBones` [bin]. For the Raccoon, no `AnimationMode`,
  `AnimClass` or `AnimationData` tag is serialized [bin].
- **Not our doing.** `CustomMode` is already present in the pre-reveal backups dated 5 Oct 18:07, for example
  `Backups/PreKlaraReveal-S1-KLARAREVEAL-20261006-234321/L_Animals.umap` (1 hit) [bin]. It is Klara's saved state.
- **What the mode means.** The header says custom mode is "engine leaves AnimInstance as it is"
  (`D:\Unreal Engine\UE_5.8\Engine\Source\Runtime\Engine\Classes\Components\SkeletalMeshComponent.h:193`) [decl].
  `AnimationMode` is declared at `:694`, `AnimClass` at `:395` and `AnimationData` (FSingleAnimationPlayData) at
  `:450` [decl].
- **No idle asset exists in the level.** `grep -a` of L_Animals.umap for `Anim_Arm_`, `Anim_Avatar_`, `AnimToPlay`,
  `AnimationSingleNode`, `AnimBlueprint`, `ABP_` and `AnimSequence` found **nothing** [bin]. The meshes have no
  post-process ABP: the same grep of `Pig_anim_RM.uasset`, `RedDeer_Calf_anim_IP.uasset` and `medhue_raccoon.uasset`
  found nothing [bin].
- **The level's LevelSequenceActor does not auto-play.** `LevelSequenceActor_1` (label `LS_Animals_1`) points at
  Klara's original `/Game/KK_S1_Animals/LS_Animals_1`, and it serializes no `PlaybackSettings` [bin]. The default is
  `bAutoPlay(false)` (`MovieSceneSequencePlaybackSettings.h:52,70`) [decl].
- **Nothing else drives the animals.** Nothing in our sequences binds them: `LS_DevScene_01_sem.json`,
  `LS_Master_sem.json` and `LS_S1_HangarRise_sem.json` have no Pig, raccoon or RedDeer binding [bin, 7 Oct 19:08
  snapshot]. Nothing in our code drives them either: a grep of `Plugins/` for `PlayAnimation`, `SetAnimationMode` and
  `AnimationSingleNode` found nothing [decl].
- **So the pre-594 pose is probably static.** Custom mode with no instance created, and the Raccoon with no AnimClass,
  means a static pose: the ref pose or the last pose written. **[inf]** The .cpp files that would confirm this are not
  installed. Gary may be calling a still pose "idle". **UNCLEAR whether they move before 594.** A live read must
  settle it (§4).

## 2. What the copy does at the cut

**The copy is ours.** `LS_Animals_1_S1Hangar` lives at `/Game/InfinityStage/KlaraHookin/`. It is our duplicate of her
`LS_Animals_1`, re-keyed by APPLY_SEQ (`KlaraIngest/HOOKIN_PLAN.md:144-146`) [decl]. Her original stays at
`Content/KK_S1_Animals/LS_Animals_1.uasset`.

**Rates** [bin `S1Snap/LS_Animals_1_S1Hangar_sem.json:5-12`; `LS_DevScene_01_sem.json:12`]:
- The copy runs at a tick of 24000 and displays at 30 fps. Its PlaybackRange is [−248000, 4806400) ticks, which is
  her frames [−310, 6008).
- LS_DevScene_01 runs at a tick of 24000 and displays at 25 fps.

**The slot.**
- *As measured.* `Shots` holds `LS_Animals_1_S1Hangar` over Scene frames [594, 5769) with `start_offset` 86400
  [meas `Saved/Logs/PussStage.log:7458`, `PROBE_S1_FOLD_OK`, 8 Oct 02:56]. In ticks that is [570240, 5538240), and
  the section's `Easing` is `{}` [bin `LS_DevScene_01_sem.json:9194-9211`, 7 Oct snapshot].
- *What the offset is.* 86400 ticks is 3.6 s, which is 90 Scene frames or 108 of her frames. Her time at the cut is
  therefore **−6.733 s, her frame −202** [meas `KlaraIngest/klara_reveal_record_S1.json:10272` `her_time_s`, `:10806`
  `her_frame_at_cut`, `:10822` `skip_frames 90`].
- *A header mismatch.* The header comment says the offset is "in display rate"
  (`MovieSceneSectionParameters.h:74-76`). The record proves ticks.

**What plays at her −6.733 s.** These are the skeletal sections [bin], with clip lengths read from each
AnimSequence's `SequenceLength` tag [bin]:

| Animal | Section (export) | Range, her s | Anim | Clip len | Clip time at cut | Ease |
|---|---|---|---|---|---|---|
| Pig | `…Track_0.Section_8` | [−9.800, −5.633) | `Pig_Eat_loop_1` | 4.167 s | 3.067 s | no ease-in; AutoEaseOut 9601 t (0.40 s) |
| Pig, next | `Section_9` | [−6.033, −1.533) | `Pig_Eat_loop_2` (FirstLoopStartFrameOffset 92000) | 4.167 | — | AutoEaseIn 0.40 s |
| Deer | `…Track_1.Section_14` | [−9.800, −5.633) | `Deer_Eat_loop` | 4.167 | 3.067 s | AutoEaseOut 12001 t (0.50 s) |
| Deer, next | `Section_15` | [−6.133, 0.333) | `Deer_EatDig_loop` | 4.167 | — | AutoEaseIn 0.50 s |
| Raccoon | `…Track_2.Section_16` | [−9.767, 14.467) | `Raccoon_Eating` | 2.700 | 0.333 s, in its second loop | none |

**So her animation is mid-motion at the cut.** All three animals are inside eating loops, 3 s in, and their first
sections start 3 s before the cut. Two consequences:
- An Ease In on these sections could not take effect: its window lies before the slot. [bin + arithmetic]
- 0.6–0.7 s after the cut, the Pig and Deer cross-fade into a second eating loop [bin].

The clip time assumes the default `StartFrameOffset` of 0. It is not serialized, so it is the default [bin]. That loops
wrap at the clip length is [inf], because `MapTimeToAnimation` is .cpp only.

**Other tracks at the cut.**
- *Transform.* `Section_0` on each animal has no keys near the cut. The Raccoon's first yaw key is at 64.3 s, and the
  additive `Section_1` begins at 113.3 s [bin, sem dump].
- *Control Rig.* `CR_Pig_LookAtCamera` is infinite-range, keys from 70.7 s. The additive head layers run from 65 s
  (Pig, Deer) and 81.7 s (Raccoon). `CR_DeerCalf_EarsHead` is infinite-range, keys from 65.4 s [bin]. The
  infinite-range CR sections begin evaluating at the cut too, which may add to the snap [inf].
- *Weight.* Weight channels are present with 1.0 and no keys, for example Pig `Section_0` and Raccoon `Section_0/8/9`
  (tail `0000803f`) [bin].
- *Camera.* Her first camera cut, `CineCameraActor` (2b4e…), covers her [−10.367, 13.467) s, so it is live at the cut
  [bin].

## 3. Why it snaps

1. **The blend source is a static pose.** Before 594, Pig and Deer have no AnimInstance (custom mode leaves it as it
   is, `SkeletalMeshComponent.h:193` [decl]). At 594 Sequencer installs its sequencer instance and drives the
   animation at weight 1, from a clip 3 s in. [inf: `UAnimSequencerInstance` and `ISequencerAnimationSupport` are
   declared at `AnimGraphRuntime/Public/AnimSequencerInstance.h:20-45` and `SequencerAnimationSupport.h:30-50`, but
   the code that installs the instance is .cpp only.]
2. **Nothing sets a weight below 1 at the cut.**
   - The shot section's `Easing` is empty [bin].
   - Her sections active at the cut have no ease-in, and their ease-in windows would lie before the slot anyway [bin].
   - Weight is not keyed [bin].
   - `GetTotalWeightValue` combines easing and the Weight curve: it is the default in `MovieSceneSection.h:690-694`
     and the skeletal override in `MovieSceneSkeletalAnimationSection.h:153` [decl].
3. **What a weight below 1 would blend toward is not proven.** The sequencer proxy owns a `FAnimNode_PoseSnapshot
   SnapshotNode` and a `FullBodyBlendNode` (`AnimSequencerInstanceProxy.h:174-177`), plus `SavePose()`
   (`SequencerAnimationSupport.h:49`, "Saved the named pose to restore after") [decl]. So the remaining weight most
   likely goes to a saved snapshot or the ref pose. That is the static level pose here [inf, .cpp not installed].
   `SlotName` (`MovieSceneSkeletalAnimationSection.h:75`) only matters with an AnimBP that has a Sequencer slot. These
   actors have no AnimBP [bin].

## 4. Options, ranked

All writes take a `Backups/Pre<Thing>-YYYYMMDD-HHMM` snapshot first. They save only the named assets, never Save All,
and never L_Animals (memory `klara-streamed-levels-traps`).

### 1. (b) Ease In on the shot section in LS_DevScene_01 (recommended)

- **Fields.** On `LS_DevScene_01.MovieScene_0.MovieSceneCinematicShotTrack_0.MovieSceneCinematicShotSection_0`, set
  `Easing.bManualEaseIn = true` and `Easing.ManualEaseInDuration = 24000–36000` ticks (1.0–1.5 s; the Scene tick is
  24000). These are the `FMovieSceneEasingSettings` fields at `MovieSceneSection.h:112-156, 793-794` [decl].
- **Writes.** LS_DevScene_01 only. Her copy and her level are untouched.
- **Why it might work.** The ECS has per-sub-sequence easing: `HierarchicalEasingProvider`, "The sub-sequence ID that
  should receive ease in/out as a whole", and `WeightAndEasingResult` (`BuiltInComponentTypes.h:704, 721-733`)
  [decl]. The skeletal system holds `FActiveSkeletalAnimation::BlendWeight` (`MovieSceneSkeletalAnimationSystem.h:29`)
  [decl]. **That the blend weight is fed by the hierarchical ease is [inf].**
- **Risks** [inf]:
  - It eases **every** track in the copy, not only the animals:
    - *Her light Intensity.* Our strike keys already settle at her lit values, so the change should be close to
      invisible (`klara_reveal_record_S1.json` per_light plateaus).
    - *Her camera cut.* It may turn into a camera blend from the glide camera, which lands on her pose (`poses.her_lit`
      = `her_first`).
    - *Her audio.* It enters mid-sound at the cut (`:474-480`), and the ease could scale its volume.
  - The blend target is the static level or ref pose, so the animals "come alive" over 1–1.5 s. They do not blend
    from an idle.
  - It sits **after** the strikes: the last strike is at 575, then the cut is at 594.
- **Verify** with a bench in PIE that restores and has no save path (memory `puss-bench-originals-to-file`). It sets
  the ease transiently, then captures stills at 593, 594, 600, 612, 625 and 631. It must show that the pose
  interpolates and that the camera and lights do not jump.

### 2. (c) Pre-roll: a stripped duplicate so they are already eating during the strikes

- **Fields.** Add a new sub track in LS_DevScene_01 with one section over [282, 594). It plays a **duplicate** of the
  copy, stripped to SkeletalAnimation, Control Rig and transform tracks. This is the same strip list as
  `KlaraIngest/klara_preroll_s4.py:6-16` [decl precedent].
- **Seamless option.** Make the duplicate's time at 594 equal her −6.733 s, so the hand-over is the *same* animation at
  the *same* phase and there is no restart.
  - That needs her time back to −19.213 s. Her first sections start at −9.8 s, so in the duplicate:
    - extend `Section_8` / `Section_14` 12.5 s earlier (3 × 4.167 s, which keeps the phase);
    - extend `Section_16` 13.5 s earlier (5 × 2.7 s);
    - extend its PlaybackRange.
  - Phase preservation by whole loops is [inf], because `MapTimeToAnimation` is .cpp only.
- **Writes.** LS_DevScene_01 plus a new asset of ours, for example `/Game/InfinityStage/KlaraHookin/
  LS_Animals_1_S1Preroll`. The copy and her original are never touched.
- **Risks.** These are the four traps of `S4_ENTRY_INVESTIGATION_2026-10-07.md` §D:
  - the duplicate's CameraCut, lights and audio must be **removed**;
  - bindings must resolve;
  - the C−1, C and C+1 boundary must not restore to the level pose;
  - keys are absolute.
  It is a creative call for Gary: animals moving during the strikes. For S4, Gary chose pre-roll on 7 Oct
  (`klara_preroll_s4_args.json` decided_by_note), but it is now "off" by default with `strike_lights none`
  (`klara_preroll_s4.py:31-34`).
- **Verify** with the same stills, at every strike and at 593/594/595.

### 3. (e) Weight curve 0→1 on her sections

- **Fields.** Key `Params.Weight` (`FMovieSceneFloatChannel`, `MovieSceneSkeletalAnimationSection.h:81-82` [decl],
  present with 1.0 [bin]) 0→1 over her [−6.733, −5.4] s on Pig `Section_8`, `Section_9`; Deer `Section_14`,
  `Section_15`; and Raccoon `Section_16`.
- **Weight must cover two sections each.** Pig and Deer cross-fade into the next section 0.6–0.7 s after the cut, so
  weighting only the first section leaves the second at full weight. Multi-section normalisation is [inf].
- **Writes.** The copy `LS_Animals_1_S1Hangar`, which is ours, behind a backup. Her original is not touched.
- **Advantage.** It touches only the animals: no light, camera or audio side effects.
- **Risks.**
  - The Weight channel is `UPROPERTY()` only, not BlueprintReadWrite (`:81`). Python access to keys goes through the
    channel proxy (`get_all_channels`), which is [inf] until a DRY lists it.
  - A future reveal re-APPLY or REVERT re-copies or re-shifts the copy and would drop the keys.

### 4. (a) Ease In on her sections

This does not work as asked: the sections active at the cut start 3 s before the slot, so their ease-in window is never
evaluated [bin]. It would only work combined with a shorter slot skip, which is (d).

### 5. (d) Move the slot offset to a calmer frame of hers

- **What it would take.** A smaller `start_offset`, for example 0 to enter at her −10.33 s, before any section (static),
  then her own sections start at −9.8 s.
- **Why it ranks last.** It moves her lights, camera and audio entry as well. The 86400 was chosen so that all 14 of
  her lights are lit at the cut (`klara_reveal_record_S1.json` plan.lit, `n_needed` 12, `frame` −202). It also
  changes the reveal's SLOT_DRIFT bookkeeping. And there is no level idle to match: the level pose is static (§1).

### What a later DRY probe must read live (read-only, run-id stamped)

- `AnimationMode` and `get_anim_instance()` class for the three actors, in PIE, at Scene frames 300 and 593. Is there an
  instance before 594? Is it `AnimSequencerInstance`?
- Two bone transforms, for example head and pelvis, on two consecutive ticks before 594. Does the "idle" move?
- The shot section's `get_editor_property("easing")` fields and `get_pre_roll_frames()`. These confirm the empty
  easing live.
- On the copy: each animal's skeletal sections, with range, `params.animation`, `params.start_frame_offset` and
  `first_loop_start_frame_offset`. Confirm `Section_8`, `Section_14` and `Section_16` are active at her −202.
- Whether the Weight channel is reachable through `get_all_channels()` on a skeletal section. This gates (e).
- `get_parent_sequence_frame` mapping of Scene 594 → her −202 frames (30 fps).

## 5. When the lights blink on in S1

All frames are Scene frames at 25 fps [meas `klara_reveal_record_S1.json` timeline `:10863-10910`, strike_schedule
`:10825`]:

| Event | Frames | Seconds |
|---|---|---|
| Land | 104 | |
| Hers Dark | [104, 282) | |
| Glide in | [119, 269] | 6.0 s |
| Glow fade | [244, 282] | |
| Strikes | 282, 306, 326, 342, 364, 391, 411, 437, 464, 481, 502, 529, 551, 575 | 11.28–23.00 s, 0.6–1.1 s gaps |
| Cut, where the slot starts | 594 | 23.76 s |
| Crossfade window | [282, 584] | |

- Each strike is a 2–4 pulse flicker over about 0.32 s [decl `S4_ENTRY_INVESTIGATION` §A, `strike_keys`]. The intro
  keys run, for example, 282→290 on SpotLight7 [meas `:per her_lights`].
- **The snap lands 0.76 s after the last strike, with every light already lit.** So (b) or (e) places the blend just
  after the reveal, not under it. Only (c) puts the motion under the strikes.

## Searched and found nothing in

- **L_Animals.umap**: any AnimSequence, AnimToPlay, SingleNode, AnimBlueprint or ABP string.
- **The three skeletal-mesh .uassets**: a PostProcess ABP.
- **Plugins/ source**: PlayAnimation, SetAnimationMode or AnimationSingleNode.
- **LS_DevScene_01, LS_Master and LS_S1_HangarRise sem dumps**: any animal binding or skeletal track.
- **KlaraIngest/**: any S1 pre-roll tool. Only `klara_preroll_s4*` exists.
- **The UE 5.8 Engine/Source tree**: no private .cpp for MovieSceneSkeletalAnimationSystem, AnimSequencerInstanceProxy
  or SkeletalMeshComponent. All runtime behaviour above is [inf].
