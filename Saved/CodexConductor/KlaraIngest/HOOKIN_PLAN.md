# Klara hook-in plan: S1 / S2 / S4 (6 Oct, offline)

Offline only: no Unreal, no MCP, nothing copied into Content, no commit. The tool is
`klara_hookin.py` (with `_run.py`, `_args.json` (DRY), `_request.json`). The harness is
`test_klara_hookin_offline.py`: 21 tests pass, and 6 of 6 seeded mutations are caught.

Tiers per claim:
- **[decl]**: a header or source we can read.
- **[bin]**: none used here.
- **[meas]**: bytes read or a record read back today.
- **[inf]**: inferred, with the reason stated.

## 1. How a Scene plays today

- A Scene cue plays one sequence, `LS_DevScene_0N`. The Master nests that per cue
  (`extend_scene_playback.py:300-320, 390` [decl]).
- `LS_DevScene_0N` nests three things:
  - `LS_S<n>_HangarRise`;
  - a "shot" sub-section (S1 `/Game/Scenes/LS_Animals_1`, S2 `LS_Shrine`, S4 `LS_Children`);
  - the root track "Narration (stand-in)".

  Source: byte scan of the `.uasset` files [meas]. The `_1` suffix is an FName number, so the
  exact name is [inf]; DRY checks it.
- S1's narration is at frames 5216-6091 at 25 fps (208.64-243.64 s), and S1 ends at 245.0 s
  (`s1_narration_after_voices_record.json` [meas]). S2's narration is 104-1973 (4.16-78.92 s,
  74.752 s long) (`scene_narration_standin_record.json` [meas]).
- **No Scene streams a level today.**
  - The show `.umap` (single-file, not OFPA) contains no `LevelStreaming`, `LevelInstance`,
    `WorldPartition` or `bIsPartitioned` strings, ASCII or UTF-16 [meas].
  - `scene_scale_audit.json:95` lists `level_instances: []` [meas, 26 Sep].
  - The orphan folder `Content/__ExternalActors__/KK_S1_Animals/LI_KKS1Animals` holds 0 files [meas].
- Today's shot cameras never resolve: "LS_Animals_1 … no actor in the show level carries those
  labels" (`Docs/SceneImportCameras_2026-09-30.md` §1 [meas, 30 Sep]).

## 2. The key question: how do her bindings resolve?

**Her bindings are full paths into her maps** [meas]. I decoded each LS's soft-object-path table
(package FName, asset FName, sub-path):
- S1 has 25 bindings, e.g. `/Game/KK_S1_Animals/L_Animals.L_Animals:PersistentLevel.CineCameraActor_7`.
- S2 has 1 binding, `/Game/Japanese_Alley/Maps/Japanese_Alley…:PersistentLevel.CineCameraActor_1`.
- S4 has 21 bindings in `/Game/L_KK_children` and **5 SpotLights in `/Game/KK_S1_Animals/L_Animals`**.

Her `L_KK_children.umap` holds no LevelStreaming names [meas]. So in her own project those 5
lights probably never resolved [inf].

### Options

**(a) RECOMMENDED: plain streaming sublevels at IDENTITY, plus retargeting the existing shot sections.**
- The locator stores a `FSoftObjectPath` (`ActorLocatorFragment.h:39-40` [decl]).
- A non-instanced streaming level loads under its real package name. So the full path should find
  the actor in the editor world, which is what `CheckSceneCutBindings` resolves against
  (`InfinityStageCameraPilotLibrary.cpp:691, 777` [decl]). That this resolves is [inf]: the engine
  has headers only, no `.cpp`.
- PIE needs a PIE-prefix fixup. That is [inf] and must be **measured** in PIE.
- The show world is not World Partition [meas: the strings are absent], so classic sublevels are
  allowed [inf].

**Why not a LevelInstance.** Instances load under an instanced package name: our own code matches
`"_LevelInstance_"` (`suppress_foreign_sky_stage1.py:10` [meas]). Resolution then needs a per-player
`SetSourceActorContext(StreamingWorld, ContainerID, SourceAssetPath)`
(`LevelSequencePlayer.h:93, 180-186` [decl]). Our single Master player in the persistent level
does not supply that for nested Scenes [inf].

**Why IDENTITY placement.**
- Her keyed cameras (3DTransform tracks in S1/S2/S4 [meas]) are absolute. A level transform would
  move the actors but not the keys [inf: standard Sequencer behaviour].
- Gary's architecture is "the lights strike, then we **cut** into the scene's sequence"
  (`SCENE_ARCHITECTURE_2026-09-30.md` [decl]). So her set never has to sit inside the hangar.

**(b) Re-binding to our actors** means copying her level contents into the show map (S4: 7
MetaHuman BPs, 3.6 GB closure [meas census]). It is heavy and it mutates the map. Rejected.

**(c) Spawnables** means editing her LS, and the transforms stay absolute anyway. MetaHumans would
spawn at the cut. Rejected [inf].

### Overlap: one set visible at a time

Her three sets all sit roughly within ±60 m of the origin [meas]. Method: an offline parse of
`RelativeLocation`, 5-95th percentile:
- L_Animals: x -129..535, y -381..270;
- Japanese_Alley: x -2449..600;
- L_KK_children: x -430..1630.

So they **overlap each other**, which means each Scene needs a Level Visibility track:
- Levels are added as `LevelStreamingDynamic`, initially loaded and initially **hidden**.
- Each Scene shows only its own levels during its shot:
  `MovieSceneLevelVisibilitySection.SetLevelNames / SetVisibility`
  (`MovieSceneLevelVisibilitySection.h:43, 49` [decl]).
- Level names are short names [inf].

Overlap with our own content near the origin (the dev grid) is UNMEASURED.

## 3. Per-scene steps (in order)

0. **Prerequisites.**
   - Klara's copy has landed.
   - Take a `Backups/` snapshot. The tool also takes per-file sha-checked backups.
   - Run DRY and read its `api_table`: every row marked [inf] must be `ok=1`.
1. **APPLY_STREAM** (map write, Gary). Adds the 3 levels at identity and saves **only** the show map.
   - It records the `check_scene_cut_bindings` lines for each cue. This is the real binding gate.
   - The automation test `SceneCutBindingsResolve` builds its **own** preview world
     (`InfinityStageCutBindingTests.cpp:31` [decl]). It proves the function works, not our data.
2. **APPLY_SEQ** (writes the Scene sequences only). For each Scene, on the existing shot
   sub-section in `LS_DevScene_01/02/04`:
   - `set_sequence(her LS)`;
   - range `[start, start + ceil(len × 25))`;
   - `StartFrameOffset = 0`.
   - Read-back: `get_parent_sequence_frame` must map her playback start and end onto exactly that
     range (`MovieSceneSectionExtensions.h:255` [decl]). This proves the time scale is 1 and the
     offset is 0.
   - **Her negative start needs nothing extra.** The section start plays her lower bound
     (`inner_to_scene_s`, harnessed; port of `scene_audio_import.py:235-241` [prec]).
   - Lengths: S1 210.6 s = **5265 f**, S2 5 s = **125 f**, S4 164 s = **4100 f**, all on the
     25 fps grid [meas census + harness]. At 24 fps, 5054.4 would be ceiled to 5055 and flagged.
   - Narration is handled per §4. The tool adds the visibility track and saves only the sequences.
3. **Relength** each Scene with `Saved/CodexSoftGoods/extend_scene_playback.py`, using the
   `extend_mode` body DRY prints (`new_end_s`). That tool sets the end (`:371`), runs
   **MatchNamedSceneHandoffs** (`:373`), gates root cut coverage (`:383`), rebuilds the Master
   (`:390`), checks that Passage keys are carried, and saves exactly.
4. **Verify.**
   - Run `InfinityStage.Editor.SavedMasterMatchesShow` (`run_saved_master_test.py`).
   - Run DRY again: `cut_bindings.ok=1` per cue.
   - Run `SceneCutBindingsResolve`.
   - Do a **PIE** play-through into each Scene (`scene1_tail_view_pie.py`): her camera must take
     the view.
5. **REVERT.** `REVERT_SEQ`, then extend back to `playback_before`, then `REVERT_STREAM`.

## 4. Decisions needed before APPLY (the tool refuses until they are made)

- **Start option.** The default is `keep` (the current shot start). DRY prints `keep`, `land` and
  `land_plus_strike`. Nested cuts outrank root cuts (memory, measured 30 Sep), so with `keep` at
  frame 0 **her cameras hide the hangar rise**. Gary's "rise, strike, then cut" points to
  `land_plus_strike`.
- **S1 narration (D57).** Her LS_Animals_1 holds only `Animals_Project_CLICK` (149.2 s). Its name
  table has no `Animal_Voices` [meas], so the rule says **REPORT**.
  - The narration (208.64-243.64 s) would then run past her shot end (210.6 s from start), and the
    tool refuses with `NARRATION_PAST_HER_END`.
  - Directing must give `narration_override_start_s` or a `tail_s`.
  - Also check whether "CLICK" is a click track rather than audience audio [inf from the name].
- **S2 narration cannot fit.** 74.75 s of narration does not fit a 5 s shot (`NARRATION_NOT_INSIDE_SHOT`).
  The S2 hangar-rise section (31 s on 30 Sep [meas, stale]) would also pass a 5 s end
  (`SECTION_PAST_PLANNED_END`).
- **S4** binds the 5 L_Animals SpotLights. With L_Animals visible in S4 they will animate, which
  Klara may never have seen [inf]. Visibility is set per args (`["L_KK_children","L_Animals"]`).

## 5. Risks

- Her levels carry DirectionalLight, SkyLight, Fog, PostProcessVolume and Atmosphere actors, and a
  LevelSequenceActor [meas: name tables]. There is no `bAutoPlay`/`PlaybackSettings` override in
  them, so they will not autoplay [inf].
- While a level is visible, her sky doubles ours (see the `suppress_foreign_sky` precedent). This
  is the lighting stream's call.
- Memory: the S1 + S4 closures are 1.45 GB and 3.59 GB, kept resident while "initially loaded".
- Adding a level may dirty her packages. The census gate then stops with nothing saved.
- Saving the map persists evaluated state. The tool refuses while Sequencer is open.
