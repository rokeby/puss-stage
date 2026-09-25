# PussStage Project Task Tracker and Handover

**Last reconciled:** 2026-08-17 14:52 BST  
**Project root:** `/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage`  
**Purpose:** durable handover for Codex task threads, delivered work, incomplete work, and the next production actions.

## Status at a glance

> ### ⚠ Reconciliation, 22 August 2026 — read before acting on anything below
>
> This document was last reconciled **17 August** and the plugin has moved from
> `0.6.0-wing-modulation` to **`0.12.3-show-owns-look`** since. Several items
> below are listed as outstanding but were **verified present in the source on
> 22 Aug**. One of them nearly caused a working feature to be rebuilt.
>
> **Listed as outstanding, but already implemented:**
>
> | Item | Evidence |
> | --- | --- |
> | P2 item 7 — rehearsal transport unreachable | `bRehearsalTransport` in `SInfinityStageCueDesk` — menu item, persisted preference, applied to live PIE |
> | P1 item 6 — attachment anchors for lights and props | `FInfinityCueAttachment` across 4 source files |
> | P1 item 4 — mechanism rate automation | `CycleRateScale` channels across 3 source files |
> | P0 item 6 — restart to load `0.6.0-wing-modulation` | Six minor versions out of date |
>
> **Confirmed still genuinely open** (absent from source on 22 Aug):
> camera piloting with write-back (P2 item 8d), the route/clearance visualizer
> (P1 item 5), the MIDI import layer (P1 item 2), and surtitles — which are new
> scope, not a regression.
>
> **What remained of P2 item 7** was not the toggle but the data: the dev fixture
> declared `DeclaredUnpausable` on silent placeholder Scenes. Fixed in the fixture
> on 22 Aug; **the live Show asset still carries the flag** and should be cleared
> when the cue spine is authored.
>
> Current working lists are `Docs/ShowBuildTodo.md`, `ShowCreativeTodo.md` and
> `ShowRehearsalTodo.md`. Treat those as authoritative for what to do next, and
> this document as history plus the playbooks in its second half.


Codex app status and project handover status are different. `idle` or `notLoaded`
only means a task is not currently executing; it does not prove that its project
work is complete. The 14:52 BST live inventory confirms this task manager as the
only active visible PussStage thread; the recently updated producer threads are
`notLoaded`. Project outcomes remain reconciled from task summaries and primary
files, never inferred from those execution states.

| Handover status | Count | Meaning |
| --- | ---: | --- |
| Live | 1 | This task manager is the only currently active visible PussStage thread. `idle` and `notLoaded` producer tasks remain tracked by outcome, not inferred as complete. |
| Implemented/tested; restart, re-verification or acceptance pending | 8 | Native, authoring or support-asset work exists. P02 remains verified; P03 has partial P03 clean-rebuild re-validation (reimport + actor/materialization read-back mostly complete but geometry checks and role assignments still failing). P05's clean 11:09 checkpoint was followed by an unverified saved content-root switch that now needs read-back. |
| Asset production pending selection/import | 0 | The P02/P03/P05 V2 families have production assets; P03 and P05 have follow-up integration checks, and P05's later duplicate-root routing needs read-back rather than more asset generation. |
| Ready / awaiting user scope | 0 | The supplied P02/P03/P05 placement scope was executed; current P03/P05 follow-up is reconciling post-change integration, not missing scope. |
| Partial / interrupted | 2 | Shore Mourning remains interrupted. Shadow Cat has a substantial live implementation, but current vendor-script/physics warnings and final behavior acceptance keep it partial. |
| Research/guidance complete; user or implementation action pending | 3 | Investigation is complete; a documented artist step, prototype or later implementation remains. |
| Completed project/support threads | 10 | The thread delivered its requested output or guidance. Walking-cat work is not counted here because its implementation remains incomplete. |
| Excluded as unrelated | 2 | The tasks used the PussStage working directory but concerned private mortgage-document translation or unrelated cloud-drive cleanup. |

## How to use this document

This file has three jobs:

1. **System primer:** what PussStage/Infinity Stage is, how its major parts fit
   together and where authority lives.
2. **Progress tracker:** what is live, done, partial, blocked, unverified and next.
3. **Handover memory:** the authoritative data model, proven tool workflows,
   decisions, operational lessons and failure-prevention rules needed by someone
   joining the project without the original task history.

Do not turn it into a transcript. Preserve only information that changes a
future decision or prevents repeated investigation. Link canonical runbooks and
technical documentation instead of copying them in full.

## System overview and architecture

### What this system is

**PussStage** is an Unreal Engine 5.8 project for authoring and presenting a
finite, music-led virtual stage journey. Its active production system is the
`InfinityStage` plugin: a camera travels through spatial **Passages** lined with
animated scenic **Wing** panels, while authored **Scenes** bridge one Passage
to the next. Music, camera movement, Wing mechanisms, lighting time, Scene
handoffs and operator transport all resolve against one deterministic Master
timeline.

The artistic model is closer to a programmable physical theatre than a normal
game level. Wings, floors, lights and unique props remain visible authored stage
content. The plugin supplies the score, timing, routes, camera evaluation,
repeatable Wing movement and handoff machinery. The current six-Passage
vertical slice proves that architecture and provides a production authoring
fixture; it is not yet the final 45-minute / roughly 3,000-Wing show.

`Plugins/InfinityStage` is the active architecture. `StageWingDirector` is
legacy/reference work and must not be treated as a parallel production system.

### The core mental model

| Concept | Role in the system |
| --- | --- |
| **Show Asset** | The ordered Cue Score and primary authoring authority. It owns cue order, stable identities, Wing occurrences, Passage grouping/settings, timing and soft asset references. Production asset: `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`. |
| **Wing Pair cue** | One stage station containing Left, Right and optionally Top panel occurrences, plus spacing, transforms, facing, visibility and deterministic movement settings. |
| **Passage** | A contiguous music-led run of Wing Pair cues with one Music Rail, one route/camera envelope and shared Passage settings. Passage headings are an authoring view over this structure. |
| **Scene / Sequence cue** | Artist-authored Level Sequence content between or among Passages. A Scene's own Camera Cut Track owns the view during its interval and may declare externally controlled sound constraints. |
| **Managed Master Sequence** | The single playback schedule and clock. Plugin-owned Passage, Scene and Music sections are rebuilt from the Show while artist keys and user-owned tracks must be preserved. Native camera/reveal curves live on its managed Passage sections. |
| **Passage Actor** | The spatial adapter in the level. `AInfinityStagePassageActor` owns the route spline, camera rig and persistent instanced render components, and materializes the Show's Wing rows into visible world geometry. |
| **Cue Desk** | The production editor UI for the Show, Music Rail, fit, route/camera controls, Wing movement, interchange, rehearsal and render-range preparation. It is an editing surface, not a separate database. |
| **Show Root / transport** | Owns the root Level Sequence Player used by Sequencer, PIE rehearsal and operator transport, so seek, reverse and jumps evaluate the same absolute Master frame. |

### Authority and data flow

```text
approved visual source
  -> transparent final-handed PNG
  -> V2 Wing package (Base/H/N/preview + 10 cm FBX + validation)
  -> Unreal Static Mesh / texture / material assets under /Game/Wings
  -> Wing occurrences referenced by the authoritative Show Asset
       -> compile/rebuild managed Master sections for time and playback
       -> materialize affected Passage Actors for saved world geometry
  -> one Master-frame evaluation drives camera, Wings, music, sky and Scenes
  -> editor scrub / PIE / operator rehearsal / Movie Render Queue output
```

The Show is authoritative for the ordered score, but not every kind of project
data belongs inside it:

- The managed Master owns native Sequencer camera/reveal keys and the compiled
  timeline presentation; rebuilding must preserve valid keys and user tracks.
- The level owns Passage Actor placement and routes, ordinary ground, lights,
  set dressing and other artist-authored world content.
- Child Scene sequences own their internal animation and Camera Cut tracks.
- Wing meshes, materials and textures are reusable Unreal assets referenced by
  the Show; replacing or moving an asset does not by itself update or verify the
  Show and materialized actors.
- `.infinitywings.json` files are portable arrangement metadata with soft asset
  paths. They are neither an asset bundle nor a second Show authority.
- Music-analysis maps and markers are review proposals until explicitly
  confirmed; they never become another playback clock.
- Generated selected-range render wrappers are disposable adapters around the
  persistent Master and must not contain artist-authored tracks.

### Authoring and runtime shape

- The development map was designed as six independent spatial Passage bays,
  separated so five Scene handoffs can conceal the jump between them. The final
  venue footprint and route geometry remain production decisions.
- Fixed Wings are editor-visible Instanced Static Mesh content. They are not
  spawned by BeginPlay and do not create one Actor, timer or Tick per Wing.
- Camera routes, Wing mechanisms, lighting and transport evaluate absolute
  Master time. The same frame must produce the same state after scrub, seek,
  reverse, reload, PIE or render.
- Passage music is Master-owned. World placement never starts a competing audio
  player. External unpausable Scene sound is handled through explicit rehearsal
  versus performance transport policy.
- Ground, local lights and singular scenic objects deliberately remain ordinary
  level content. The plugin does not own scenic floor design.
- The physical robot dog is outside the plugin. The camera rig provides a
  separate shadow-figure root for artist-authored figures behind the camera;
  their final animation and shadow-only composition remain production work.

### Code, content and generated-data boundaries

| Boundary | Canonical location | Ownership rule |
| --- | --- | --- |
| Active plugin code | `Plugins/InfinityStage/` | Runtime, Editor and Tests modules; change through normal code/build/test workflow. |
| Authoritative Show | `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` | Inspect first; mutate narrowly; back up before whole-set trials. |
| Managed Master | `/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master` | Rebuild after order/timing/duration changes, not for a mesh-only reassignment; preserve artist keys/tracks. |
| Current vertical slice | `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` | Holds Passage Actors, routes and ordinary stage content; target-save only after intended materialization/level edits. |
| Child Scenes | `/Game/InfinityStage/Dev/Sequences/LS_DevScene_01` through `LS_DevScene_05` | Artist-authored animation and camera authority during Scene intervals. |
| Production Wing content | Family-specific roots under `/Game/Wings/` | Reusable assets; current canonical family/root must be verified before integration or cleanup. |
| Source/generated Wing packages | `DerivedAssets/` | Keep PNGs, maps, FBX, reports and quarantine evidence together as a handover unit. |
| Music and review maps | `/Game/InfinityStage/Audio/Passages`, `/Game/InfinityStage/MusicMaps`, `Saved/InfinityStage/MusicAnalysis/` | Audio playback is Master-owned; analysis output remains review-only. |
| Portable Wing sequences | `Saved/InfinityStage/WingSequences/` | Versioned metadata for arrangement transfer; referenced Unreal assets must exist separately. |
| Generated render wrappers | `/Game/InfinityStage/Generated/Renders/` | Replaceable plugin-owned wrappers; never the home of persistent artist tracks. |

### How a change becomes complete

A source file, an imported asset, a Show edit and a visible level result are
different checkpoints. A production authoring change is complete only when its
intended layer has been verified:

1. Validate source assets or code against the relevant convention/tests.
2. Inspect the authoritative Show, current map, PIE state and existing dirty
   packages before mutation.
3. Make one deterministic, narrowly scoped edit through the Cue Desk or guarded
   loopback project-Python transport.
4. Rebuild the managed Master only when cue order, timing, duration or managed
   timeline data requires it.
5. Materialize exactly the affected Passage Actor(s).
6. Save only the intended Show, level and explicitly affected sequence/assets.
7. Run a separate read-only Unreal verification and require an explicit success
   marker; file timestamps, asset names and `idle` task state are not proof.
8. Obtain human visual/audio acceptance where automation cannot judge the
   artistic result.

### Where a new contributor should read next

- Current controls and artist workflow:
  `Docs/InfinityStageAuthoringReference.md`.
- Original architecture, fixture scope and automated gates:
  `Docs/InfinityStageOvernightReport.md`.
- Safe Unreal automation, exact transports and markers:
  `Docs/CodexUnrealMCPRunbook.md`.
- Wing handedness, V2 geometry, maps and export validation:
  `Docs/WingGenerationConventions.md`.
- Live performer control from the Unitree GO1 (network, bridge, UE plugin,
  Windows port): `Docs/Go1TelemetryProgress.md`, then
  `Docs/Go1TelemetrySetup.md` to run it.
- Current state, blockers and next work: the live/outstanding sections and P0
  list in this document.

## Live and outstanding threads

### 1. Track Puss project tasks

- **Handover state:** Live task manager.
- **Codex app state:** `active`.
- **Done:** live thread inventory reconciled against project files; this tracker created.
- **Next:** use this task for status checks and update this document after material project changes.
- **Thread ID:** `019ffc1f-4b52-7921-b539-8e53a15f1161`.

### 2. Building Infinity Stage

- **Handover state:** Native `0.6.0-wing-modulation` implementation is built and its prior 31-test gate passed. A newer Space-bar transport toggle is linked into numbered `-0002` modules but has no post-change suite or loaded-Editor proof. Later saved-package and live-authoring evidence still needs targeted read-back and human acceptance.
- **Codex app state:** `notLoaded`; no new outcome is inferred. The resumed implementation turn's completed build/test evidence remains the handover basis.
- **Latest delivered:**
  - Plugin `0.5.0-authoring-integration` with a persistent, resizable three-column Cue Desk and collapsible Music Timeline; layout proportions, active Inspector tab, nested mode and timeline visibility persist per project.
  - Nested/flat Passage views and multi-row drag/drop reordering. Whole-Passage undulation phase now follows each row's live cue ordinal, so reordering updates the travelling phase without regenerating a preset.
  - Exact cue-to-Master playhead/camera synchronization; confirmed music markers can be pinned as camera anchors, marker snapping can be enabled, and Option temporarily bypasses snapping while dragging.
  - Previous/next Master-segment controls for later-Passage PIE rehearsal and corrected camera ownership at autoplay/frame zero.
  - Bare **Space** handling is now implemented in `SInfinityStageCueDesk::OnKeyDown`: with the Cue Desk focused it stops a running preview/PIE transport or plays forward when stopped, ignores modified/repeated Space and defers to text-entry children. It routes through the normal transport command so an externally unpausable Scene still rejects the stop. `UInfinityStageTransportController::IsTransportPlaying` supplies the PIE state.
  - Nine native managed-Passage camera channels: integrated speed/time warp, three position offsets, three rotations, focal length and focus distance. Cue Desk and Sequencer edit the same Master-owned keys.
  - Constraint-safe speed envelopes, Wing/music anchors, live speed readout and Scene endpoint lens/focus handoff.
  - Native navigation into child Scene subsequences from managed Master blocks and the Cue Desk.
  - **Camera Gust / Fan Reveal** simplified to a normal camera-led spatial frontier: camera speed from the music rail determines how quickly the road opens; `Reveal Ahead` and `Opening Ramp` are the primary controls. The seconds-based cascade survives only as Advanced compatibility mode.
  - **Render Selected Range** under Cue Desk **Actions**: a selected `PASS` or cue-row span generates `/Game/InfinityStage/Generated/Renders/LS_<Show>_RenderSelection`, exposes Passage Camera Rigs through a standard Camera Cut Track, preserves nested Scene cameras, and creates or updates one stable Movie Render Queue job without clearing other jobs or resetting its existing render configuration. The generated wrapper is replaceable and must not hold artist-authored tracks.
  - **Editor Lighting** under Cue Desk **View**: Manual Editing Light defaults to noon and prevents editor scrubbing from leaving the shared celestial actors at night; exact preview time and lighting parameters remain editable through the Celestial Rig. PIE, live transport, MRQ and packaged playback always ignore the manual preview and remain Master-driven.
  - **Wing Sequence Files** under Cue Desk **Actions**: lossless schema-v1 `.infinitywings.json` export of selected rows or a whole Passage, plus insert and replace imports. The format preserves complete L/R/T occurrence metadata, frame-rate-aware timing, movement/Camera Gust data and legacy image-flip state; imported cues receive fresh identities. Replace preserves target Passage identity, music rail, temporality, camera curves and adjacent Scene ownership.
  - A new void **Materialize Passage** Call-in-Editor wrapper now appears beside **Clear Materialized Passage** after restart. It retains the existing Boolean API for code/tests and logs `INFINITY_STAGE_MATERIALIZE_OK actor='<name>' passage=<guid> wing_pairs=<count>` on success.
  - Verification history: the `0.5.0` authoring-integration baseline passed **28/28 Infinity Stage tests**, including saved vertical-slice PIE, Master opening, Scene handover, Camera Gust, live reordered phase, interchange/render-wrapper coverage and the 3,000-Wing compile test. The later `0.6.0-wing-modulation` gate passed **31/31** before the Space change. `Saved/Logs/InfinityStageAuthoringIntegrationTests.log` and `Saved/Logs/InfinityStageWingModulationTests.log` end with successful test exits; the newer Space change still needs a post-build suite and loaded-Editor proof.
  - **Later unverified saved-content evidence:** autosaves at 17:04 BST and the production Master saved at 17:16 BST contain serialized `LookAheadDistanceCm`, which is absent from the 14 August Master baseline; the Show and Master were saved at 17:16 and the vertical-slice level at 17:34. This is file-level evidence that the newer Camera Gust/reveal field reached managed content. It does not establish that all nine camera channels, bindings, keys, Scene handoffs or other generated content are correct, and no matching task outcome, log marker or independent Unreal read-back was found.
  - **Live 16 August authoring evidence:** `INFINITY_STAGE_ROUTE_EDIT_OK` reports Passage 2 at `route_cm=13582.6`, followed by `INFINITY_STAGE_ROUTE_HANDOFF_MATCH ok=1` for all five Scene boundaries. The user then applied smooth undulation to 23 Wing Pair cues. The vertical-slice level was explicitly saved and validated at 16:13 BST, but the production Show and five child Scene packages retain their older modification times; only autosaves contain the new undulation/handoff work. Treat the route as saved-but-unread-back and the Scene/Show edits as in-memory/autosave work, not completed persistence.
- **Outstanding:**
  1. Restart and confirm plugin `0.6.0-wing-modulation` plus the newest Cue Desk/transport code are loaded. The current Editor started with the older unnumbered Infinity Stage modules; the manifest now points to `libUnrealEditor-InfinityStage*-0002.dylib`, so the new Space toggle is not proven live. Run the focused/full suite after restart before calling it accepted.
  2. Read back the production Master in Unreal. If it exposes all expected camera/reveal channels, bindings and preserved keys, record a unique verification marker and do not rebuild again; otherwise run **Actions → Rebuild Managed Master Sequence** once, then independently read it back.
  3. Read back Passage 2's saved spline and camera-rig values. Inspect the autosaved Scene handoffs and Show undulation, then intentionally save or discard those packages; do not infer persistence from their autosaves.
  4. If Passage endpoint framing changes again, run **Scene Camera Handoff → Match All Scenes**.
  5. Reapply **Camera-led Reveal** to any rows still stamped with the obsolete preset; existing content is not silently rewritten.
  6. Set **View → Editor Lighting → Bright Work Light — 12:00** or another manual preview and verify that editor scrubbing no longer strands the viewport at night; save the level only if the chosen working time should persist.
  7. Save the level and edited Scene sequences, then use **Actions → Render Selected Range…** on one `PASS` and one multi-cue selection; visually verify wrapper range, Passage cameras, nested Scene cameras and a local MRQ output.
  8. Visually test curve editing, anchors, Camera/Overview scrub modes, reveal frontier, reverse/seek and Scene entry/exit cameras.
  9. Test Wing Sequence insert and replace on a disposable Show copy, require `INFINITY_STAGE_WING_SEQUENCE_IMPORT_OK`, inspect the affected Passage, then intentionally save only after acceptance. A file export alone does not save or rebind the level.
- **Evidence:** `Docs/InfinityStageAuthoringReference.md`, `Plugins/InfinityStage/Docs/AuthoringReference.md`, `Plugins/InfinityStage/Docs/CelestialCycle.md`, `Plugins/InfinityStage/InfinityStage.uplugin`, `Saved/Logs/InfinityStageAuthoringIntegrationTests.log`, `Saved/Logs/InfinityStageWingModulationTests.log`, the current `PussStage.log`, and task `019fecd3-01be-78f1-991b-2849c074bf82`.
- **Thread ID:** `019fecd3-01be-78f1-991b-2849c074bf82`.

### 3. Locate Passage wing assignment

- **Handover state:** The original Passage 1 reassignment completed and verified; it has since been superseded by the separately verified all-V2 trial in section 6. New movement presets remain implemented/tested but unapplied.
- **Codex app state:** `idle`.
- **Delivered:**
  - At this task's completion, Passage 1 repeated Rococo → Pillar1 BW → Pillar2 BW across 48 rows with `SM_Ceiling_bw`; that configuration is historical evidence and is preserved inside the pre-V2 Show snapshot documented in `Docs/Passage1SetVersions.md`, not the current live side-mesh state.
  - The affected Passage was materialized, the Show Asset and vertical-slice level were saved, and independent Unreal read-back succeeded. Exact markers are in `Docs/CodexUnrealMCPRunbook.md`.
  - **Phased Breathe** presets were added for 2-phase alternating, 3-phase and 4-phase patterns. UE 5.8 built successfully and **24 tests passed**.
- **Outstanding:** restart Unreal to load the Phased Breathe menu. Select the intended Wing rows/Passage and apply a phase preset if desired; the implementation task deliberately did not change the current movement selection.
- **Evidence:** `Docs/CodexUnrealMCPRunbook.md` and `Plugins/InfinityStage/Docs/AuthoringReference.md`.
- **Thread ID:** `019ffd2c-e68d-7d40-9bf1-6debdc659c35`.

### 4. Add sun and moon cycle

- **Handover state:** Implementation complete; saved-map integration and artist acceptance pending.
- **Codex app state:** `idle`.
- **Delivered:** deterministic show-wide celestial rig; sun, moon, stars, Skylight and fog driven from the absolute Master Sequence frame; default 20-second day/night cycle; per-Passage Temporality controls; timeline-scrub preview. The later Editor Lighting upgrade separates a persistent manual working-light preview from performance lighting and exposes exact Celestial Rig settings in Details; the latest clean build and 26/26 suite passed.
- **Outstanding:**
  1. Save and close the interactive Unreal Editor.
  2. Apply `Scripts/add_infinity_stage_dusk_sky.py` to the saved vertical-slice map.
  3. Reopen/restart Unreal so the new native editor UI is loaded.
  4. Verify PASS-row selection, Temporality controls, manual Editor Lighting, Follow Master, sun/moon/stars motion, scrubbing, reverse and PIE playback. The later implementation did not force-save the level's selected working time.
- **Evidence:** `Plugins/InfinityStage/Docs/CelestialCycle.md` and `Scripts/add_infinity_stage_dusk_sky.py`.
- **Important:** the map has since been saved during other authoring work, so timestamps no longer establish whether the prepared celestial environment upgrade was applied. Keep this pending until the rig/actor bindings are read back from Unreal and a unique success marker is confirmed.
- **Thread ID:** `019ffc09-811b-7682-bf63-889c563d8a3f`.

### 5. Wing Gen and Next Steps

- **Handover state:** Three Chinoiserie LiDAR pairs remain validated external packages. The complete six-set sanatorium-to-Chinoiserie L/R/C family was imported, assigned, materialized, target-saved and independently verified in Passage 3 with the earlier batch; the 17 August `GeneratedWingsV2_Passage03_Clean` batch now supersedes that FBX geometry source for a required re-import pass. Human stage-light acceptance remains.
- **Codex app state:** `notLoaded`; do not infer completion from this state. The current Passage 3 completion claim comes from Unreal evidence below.
- **Delivered:** new Stage Opening PNG families including bamboo and steel scaffolds, ceramic totems, Paper Screen and the accepted softer Biomechanical Pillar pair. The previously omitted Paper Screen and Biomechanical pairs were copied into the shared `V2/Wings/0. Stage opening/IMG` folder and checksum-verified.
- **Completed Chinoiserie package:** the approved pair plus two non-mirrored variants produced six 10 m-tall, 10 cm-thick FBX/Blender panels with corrected source handedness, Base/alpha, restrained Height and DirectX Normal maps, relief previews and Front/Back/Edge slots. All six clean-reimport checks passed; the package was copied byte-for-byte to shared `V2/Other/3D Assets/ChinoiserieLidarPanels` with six canonical source PNGs under `V2/Other/IMG`. Nothing was imported into Unreal by this task.
- **Completed sanatorium sequence package:** six independent L/R/C sets move from sun-washed administration and glass-block classroom architecture through the yellow-curtain threshold and smooth sanatorium arches into pale plaster salon and cracked celadon palatial panels. All final silhouettes use intact architectural edges; LiDAR character is confined to surface treatment. The 18 assets include Base/alpha, Height, Normal, relief previews, FBX and Blender sources at 10 m working height and 10 cm depth. All 18 clean FBX reimports passed, and the shared Passage 3 copy matches the local package.
- **New generation convention:** earlier Left sources were sometimes repaired in the Show with **Flip Image Horizontally**. New paired art must instead arrive in final image handedness before any PBR-map or FBX work: `*_L` has its exterior/backbone edge on image-left and inward/projection edge on image-right; `*_R` is the converse. This is separate from the 180-degree mesh-facing yaw used to point a panel into the passage. Legacy Show data and the verified `left_preserve+right_rotate180` V2 trial remain historical states and must not be bulk-rewritten.
- **Verified Passage 3 integration (legacy batch):** 18 V2 panels became 90 scoped Unreal assets under `/Game/Wings/Passage03_ShrineToForgetting`; 21 contiguous `P03 Wing` rows use the six L/R/C families in order, `_C` is Top-only, all image flips are false, the exact Passage actor materializes 21 pairs, the pre-change Show backup exists, and Unreal finished with no dirty packages.
- **Current Passage 3 revalidation status:** The clean source (`DerivedAssets/GeneratedWingsV2_Passage03_Clean`) remains canonical and its production checks still pass for non-triangle faces, non-manifold edges and degenerate triangles. The clean reimport/read-back stage is now completed: `reimport_passage03_clean_meshes.json` reports `status=ok`, `replaced=18`, and `mesh_count=18`; `inspect_p03_actor_state.json` shows `materialized_wing_pair_count=21`, `static_mesh_components=18`, `actor_hidden=false`, `non_p03_meshes_in_use={}`; and 21 rows were read back with flips disabled.
- **Outstanding:** fix remaining Passage 3 verification failures: `verify_p03_clean_geometry.json` reports `status=error` with `triangle_mismatches=1` (`P03_RepeatingSanatoriumArches_01_L` expected 988 vs Unreal 1024 triangles), and `inspect_p03_rows.json` reports `role_mismatches=6`. Then rerun read-back + verify, target-save only the affected level assets, and visually judge silhouette/relief/placement under production lighting.
- **Evidence:** `Docs/WingGenerationConventions.md`; `DerivedAssets/GeneratedWingsV2_Chinoiserie/README.md`; `DerivedAssets/GeneratedWingsV2_Passage03/README.md` and `GeneratedWingsV2_Passage03/wing_pipeline_report.json` (legacy); `DerivedAssets/GeneratedWingsV2_Passage03_Clean/README.md`, `DerivedAssets/GeneratedWingsV2_Passage03_Clean/clean_fbx_validation_report.json` (current); `Saved/CodexWingIntegration/preflight_all_passages.json`; `Saved/CodexWingIntegration/reimport_passage03_clean_meshes.json`; `Saved/CodexWingIntegration/inspect_p03_actor_state.json`; `Saved/CodexWingIntegration/inspect_p03_rows.json`; `Saved/CodexWingIntegration/verify_p03_clean_geometry.json`; markers `P03_V2_IMPORT_SUCCESS`, `P03_SHRINE_FORGETTING_ASSIGN_SUCCESS` and `P03_SHRINE_FORGETTING_VERIFY_SUCCESS`.
- **Thread ID:** `019ffd01-11c0-7f00-87ed-09b74c3ab8c9`.

### 6. Blend floral furry architecture

- **Handover state:** Optimized 14-panel conversion/import batch and recoverable Passage 1 V2 assignment are complete and independently verified; human stage-light acceptance remains.
- **Codex app state:** `idle`; latest turn completed.
- **Delivered:**
  - Stage-opening transformation grammar clarified as **Painted / Exposed / Covered**.
  - Rococo-painterly covered/exposed studies and a lighter floral/furry mutation produced.
  - `SaltFormation_01_L_v2` packaged as a portable 10 m × 7.04 m × 10 cm FBX with base/alpha, height and DirectX normal textures, three material slots and documented conservative Bump Offset settings.
  - Clean FBX re-import validation passed. The 10 cm rule now applies to every newly generated production Wing; accepted legacy pipeline outputs remain 5 cm unless explicitly migrated.
  - 22 rejected original floral/furry/biomechanical images were moved—not deleted—to `DerivedAssets/GeneratedConcepts/StageOpening/Discarded`; Ceramic Totem and amalgam studies remain active.
- **Verified Unreal proof:** `/Game/Wings/StageOpeningV2/` contains the SaltFormation mesh, three textures, masked two-sided relief surface and opaque edge material. Independent read-back confirmed texture settings, exactly four texture samples plus one Bump Offset node, ratio `0.008`, reference plane `0.5`, and Surface/Surface/Edge mesh-slot assignment. FBX-created placeholder material instances remain on disk but are not assigned.
- **Completed optimized batch:** 14 selected panels were converted locally in one batch at 10 m height and 10 cm depth, with 152–4,651 polygons depending on silhouette. Each retains explicit base/height/normal textures. The batch excludes superseded studies and `Discarded` content and uses normalized underscore asset paths for painterly names.
- **Batch economy:** one Blender startup, 768 px tracing, stronger silhouette simplification for scaffolds/gauze, no `.blend` saves and no duplicate embedded raster payload in FBXs. Unreal is intended to use one shared relief master, one shared Edge material and 14 lightweight instances instead of 28 separately compiled surface materials.
- **Verified batch import:** two bulk Unreal import calls plus one shader path produced exactly 72 scoped batch assets—14 meshes, 42 textures, 14 material instances and two shared materials. Unreal independently verified texture settings, instance parents/parameters, Surface/Surface/Edge slot assignments and 10 m × 10 cm dimensions. The single SaltFormation proof assets coexist, bringing the folder's total file count above 72.
- **Verified Passage 1 trial at its recorded checkpoint:** the Show repeated nine V2 pairings over all 48 rows and used every one of the 15 V2 meshes. Six authored L/R pairs remained together; three L-only designs used documented compatible structural right panels. Left panels preserved their baked face, right panels rotated 180° around stage-up, photographic images were not mirrored, and all 48 Top assignments remained unchanged. Materialization produced 48 pairs / 144 panels; the Show Asset and affected level were target-saved and independently read back.
- **Restoration point:** the complete pre-trial Show state—not only its mesh list—is saved at `/Game/InfinityStage/Dev/SavedVersions/DA_InfinityStage_V1Show_P01_PreV2_20260814`. It preserves the preceding Rococo/Pillar cycle, the existing row-1 Salt test, timing, motion, transforms and overrides.
- **Verification marker:** `P01_V2_SEQUENCE_VERIFY_SUCCESS|rows=48|sequence_pairs=9|unique_v2_meshes=15|tops=48|materialized_pairs=48|materialized_panels=144|orientation=left_preserve+right_rotate180|backup_readback=1`.
- **New sequence snapshots and current-state caveat:** `Saved/InfinityStage/WingSequences/Passage 1 Motley structures.infinitywings.json` and `Passage 1 PillarRococo.infinitywings.json` are parseable schema-v1, 48-row whole-Passage exports with matching envelopes. The former names the live Show as its source and records all 48 Left occurrences with `bFlipImageHorizontally=true`; the latter names the pre-V2 backup and records 38 of 48 Left flips true. This later external snapshot means the earlier no-mirroring marker is historical evidence, not proof of today's live orientation. The Show Asset remains authoritative and must be read back in Unreal before acceptance or further mutation.
- **Outstanding:** read back the current live Show's 48 L/R image-flip and facing policies in Unreal, then visually review orientations, silhouettes, seams and relief under production lighting. Restore or import the documented pre-V2/PillarRococo version only through an explicit, previewed action.
- **Evidence:** `Docs/Passage1SetVersions.md`, the two external files under `Saved/InfinityStage/WingSequences/`, `DerivedAssets/StageOpeningV2Batch/unreal_batch.json`, `DerivedAssets/GeneratedWingsV2/README.md` and `DerivedAssets/GeneratedWingsV2/SaltFormation_01_L_v2/UE5_Material_Setup.md`.
- **Thread ID:** `019ffd63-7ae2-70e0-8c8e-713d373ffce8`.

### 7. Find UE5.8 ground assets

- **Handover state:** Specific Landscape material/layer workflow identified; artist setup is in progress and saved state has not been read back.
- **Codex app state:** `notLoaded`; no completion is inferred.
- **Delivered:** recommended `/Game/MWMeadowWetlands/Materials/Ground/MTL_MWL_Landscape`; identified actual main paint targets `Dirt`, `Forest`, `Moss`, `Rock` and `Stones`, plus supplied Layer Info assets under `/Game/MWMeadowWetlands/Maps/MeadowWetlandsLandscape_sharedassets/`.
- **Next artist step:** in Landscape Paint, click the lightning-bolt **Populate Target Layers from Materials**, assign `Dirt_LayerInfo`, **Fill Layer**, wait for shader compilation, then assign the remaining Layer Info assets.
- **Important correction:** `DirtRough` and `ForestMoss` are internal texture/material-function variants, not the main supplied paint targets. A black Landscape before target population/fill is consistent with uninitialized layers, not proof that the material is broken.
- **Verification boundary:** the level package timestamp changed during this work, but there is no Unreal success marker/read-back proving which Landscape settings were saved. Treat the setup as unverified until inspected in Unreal.
- **Thread ID:** `019ffd24-48e2-7201-8e90-0453573371e6`.

### 8. Design detailed ground plane

- **Handover state:** two verified 4K wood-floor material packs are imported as production support assets; applying and accepting a project-owned ground preset remains, while the broader Landscape-versus-mesh architecture is still open.
- **Codex app state:** `notLoaded`; existing import/read-back evidence remains authoritative.
- **Delivered:** documented the distinction between Landscape Paint, Mesh Paint, Foliage Paint and PCG. Imported only Materials and Textures from the UE 5.0 Vol.01/Vol.02 packs into `/Game/4K_WoodFlooring_Vol_01` and `/Game/4K_WoodFlooring_Vol_02`; demo maps, architectural meshes and TrueSky content were excluded. Unreal read-back found 305 assets, exactly 50 real floor material instances, valid in-pack parents and no audit failures; useful materials were saved in UE 5.8 format. Both UE 5.0 source ZIPs and the duplicate UE 4.13 ZIP were permanently deleted as requested; the extracted Vol.01 source folder remains. The imported packs use approximately 3.8 GB and the task reported only about 28 GB free afterward.
- **Recommended first use:** duplicate `/Game/4K_WoodFlooring_Vol_01/Materials/M_Oak_Strp_01_Mat_Inst` to `/Game/Stage/Ground/Materials/MI_Ground_OakStrip_01`, then apply the project-owned instance to a thin box rather than editing vendor content or the shared `M_Flooring_Mat` master. A 20 × 12 × 0.05 scaled default Cube gives roughly a 20 × 12 m, 5 cm-thick collision floor for a bounded test.
- **Outstanding:** test physical board scale, orientation, roughness, normal, grunge and scratches under the production camera without replacing `M_StageMovingGround`; compare that finite mesh proof with the MW Wetlands Landscape experiment before committing the full-show architecture. Monitor disk space before adding another large texture pack.
- **Evidence:** `Saved/WoodFloorImportAudit.json` and the two imported `/Game/4K_WoodFlooring_Vol_0*` roots.
- **Thread ID:** `019ffca2-7d43-72c3-b295-93321d7eb841`.

### 9. Create swaying sheet figures

- **Handover state:** UE5.8 Chaos Cloth workflow research complete; no cloth asset or prototype has been built.
- **Codex app state:** `notLoaded`; no prototype or completion is inferred.
- **Recommended first proof:** use a simple animated skeletal mannequin with a separate Chaos Cloth Asset, an evenly subdivided single-surface sheet, a small kinematic crown/back-of-neck region, and a cloth-specific Physics Asset containing smooth head/neck/chest/shoulder/arm collision shapes.
- **MetaHuman path:** Sequencer/mocap drives MetaHuman bones; the animated Body component moves Physics Asset shapes; Chaos Cloth collides against those shapes. Detailed rendered skin is not normally the collision surface. A duplicated, simplified cloth Physics Asset is preferable to a dense anatomical one.
- **Latest bounded tutorial:** create a scratch `/Game/Experiments/ChaosClothSphere` proof with a 100 × 100 cm, approximately 20 × 20 subdivided `SM_CC_TestSheet`, a `CA_CC_TestSheet` **Static Mesh Cloth** asset, the same mesh as SIM/RENDER input, `SKM_Manny_Simple` as temporary skeleton/weights, and `WeightMap_MaxDistance` filled white so the whole test sheet can fall. Use a normal collision sphere beneath it and animate that sphere gently in Sequencer. This is documented guidance only; no asset was created.
- **Outstanding:** build the sphere proof, then the mannequin proof; validate collision/pinning/damping without wind, transfer to one mocapped MetaHuman and only afterward add self-collision, hands or wind. Treat settings as guidance until the project prototype is tested.
- **Thread ID:** `019ffd8e-899a-7c02-b0e9-e9bb88146708`.

### 10. Generate mourning shore set pieces

- **Handover state:** Partial / interrupted.
- **Codex app state:** `notLoaded`; latest turn status was `interrupted`.
- **Delivered before interruption:** four concept families exist under `DerivedAssets/GeneratedConcepts/ShoreMourning/`, with normal and chroma variants:
  - `SM_VillagerDanceCircle`
  - `SM_BoneShoreBank`
  - `SM_TidalBoneFrieze`
  - `SM_WaystoneClamAltar`
- **Outstanding:** review the four concepts, select/iterate the useful designs, create clean transparent production PNGs, then send approved pieces through the wing-cutout FBX pipeline if required.
- **Thread ID:** `019f99b2-6251-7ba0-9294-06497cec1cd1`.

### 11. Understand wing music setup

- **Handover state:** Research complete; MIDI-driven movement implementation has not started.
- **Codex app state:** `notLoaded`.
- **Delivered:** audit of the active Infinity Stage music/wing timing model and a proposed three-layer musical mapping: phrase-level breathing, pulse/strum accordion movement, and accent/cascade gestures. MIDI was identified as the semantic movement map while Master audio/Sequencer remains the playback clock.
- **Outstanding:** decide the supported MIDI source format and authoring workflow; define grouping rules for chords, strums, cascades, sustain and phrases; implement reviewed MIDI-to-movement proposals without introducing a second clock.
- **Thread ID:** `019ff304-2874-7862-a1ee-9c4d5e64a7f0`.

### 12. Passage 2 forest-to-industrial Wing development

- **Handover state:** the 20-set L/R/T sequence has been rebuilt to the 10 cm V2 contract, imported as 300 scoped Unreal assets, assigned across all 23 Passage 2 cues, materialized, target-saved and independently verified. Human visual acceptance remains.
- **Codex app state:** `notLoaded`; the authoritative completion evidence is the Unreal read-back, not the app state.
- **Narrative progression:** approximately 120 Wings moving from a whimsical but dark, wet magical-realist forest through a denser waxy/root-rich forest to an overgrown industrial-estate edge with restrained brick/crumbling traces. Snails, badgers and snakes are tonal presences rather than frequent literal subjects.
- **Movement/design distinction:** retain thick, wide scenic Wing presence, but make the set feel like an unfolding stop-motion sequence of changing details rather than Passage 1's cycling/undulating architectural mechanism.
- **Delivered source packs:** the initial lighter three-matrix extraction remains intact under `DerivedAssets/GeneratedConcepts/Passage02Forest/RousseauFinal/`; the denser, darker revision remains intact under `RousseauDenseWetFinal/`. The latest successor is `RousseauLayeredLightFinal/`: it preserves the dense wet structure, colour progression and no-blue-sky rule while keeping the nearest foliage/roots/top bough dark, lifting middle vegetation and placing the lightest values on the deepest foliage and receding trail so separate scenic layers remain readable.
- **Dense-wet validation:** its three matrices produced 36 gutter-free scenes plus 108 extracted L/R/T panel PNGs—147 PNGs total. On-disk checks found all 147 non-empty and recognized as PNGs. `S01`–`S12` remain row-major within each matrix. Three 1440×480 audit montages under `RousseauDenseWetFinal/audit/` visually confirmed usable vegetation structure, top-branch continuity and intentional side overlap; no additional image-generation repair was needed at the source-crop stage.
- **Layered-light validation:** its three source matrices produced 36 gutter-free scenes, 108 panel crops (36 Left, 36 Right and 36 Top) and three 1440×480 audit montages—150 PNGs in the pack. Local read-back found zero empty panels and `file` recognized all 108 as PNGs. The completed task reported all panel integrity checks passed; the darker `RousseauDenseWetFinal` source was not overwritten.
- **Transparent portal pack—technically valid, artistically superseded:** `RousseauTransparentCutoutsFinal/` contains 36 U-shaped portals, 108 RGBA L/R/T files and three alpha audits; local file inspection confirmed 36 of each side and 108/108 RGBA PNGs. The magenta-matte workflow used soft chroma removal, despill and a one-pixel contraction. The user then rejected the physical grammar: hard portal cuts do not suit independently layered moving pieces, side Wings must not carry ceiling branches and Tops must be multi-member clusters rather than single branches.
- **Independent-cutout draft—do not treat as approved:** `RousseauIndependentCutoutsFinal/` contains six chroma sheets, six alpha sheets, 108 raw panels, 108 cleaned RGBA panels and three audits. It corrects the component split but has no canonical README and was visually rejected after small-object batch generation drifted toward outlined foliage, gold-vein ornament, conical symmetry, crushed blacks and a generic game-asset finish.
- **Approved component grammar:** L/R are independent freestanding vegetation or architectural masses with soft botanical inner edges and no overhead ceiling member. T is a substantial connected cluster of overlapping branches, vines, pipes or crumbling masonry. Side silhouettes should vary—upright/columnar, forked or scalloped with substantial upper foliage—not repeat a declining mound.
- **Approved style lock:** matte Rousseau-like pigment and simplified painted forms combined with believable wet directional light: dark foreground occlusion, readable green middle and selective cooler recessed light. Dark lush wetness is an accent, not the uniform value of every piece. The user explicitly approved the final side/top pair and two upper-foliage variants; these anchors currently live in `.codex/generated_images` rather than a project-owned pack.
- **Current individual sequence:** `RousseauApprovedIndividualSequenceV5/chroma/` now contains Sets 01–20 as 60 L/R/T source files. The task reported 60/60 cleaned RGBA PNGs with matching source dimensions, zero-alpha corners, soft edges, no bright-magenta fringe and all 20 L/R handedness checks passing; checksum-matching copies are staged in the shared `V2/Wings/1. Opening to Animals/IMG` folder.
- **First conversion—superseded before import:** the shared `V2/Wings/1. Opening to Animals/3D Asset/wing_pipeline_report.json` contains 60 `status: ok` entries at 10 m final height and yaw 90, but all have `thickness_cm: 5.0` and the handoff lacks the required registered height/normal/preview set. Representative clean re-imports proved UVs/slots for that requested build, not compliance with the newer production contract. Nothing from this batch was imported into Unreal.
- **Completed V2 correction and Unreal integration:** `DerivedAssets/Passage01V2Batch/GeneratedWings/wing_pipeline_report.json` records 60 successful panels at 2 m source / 10 m final height, 10 cm thickness, scale 5 and yaw 90; the factory-clean validation reports 60/60. Unreal contains 60 meshes, 180 Base/height/normal textures and 60 lightweight relief instances under `/Game/Wings/Passage02_AnimalsToShrineV2`. The 23 rows use `01–12, 01, 02 / 13–16, 13 / 17–20`, matching the 14/5/4 narrative allocation, with L/R/T assigned and all image flips false. The exact actor materializes 23 pairs and the Editor verified clean after targeted saves.
- **Passage 2 allocation rule:** for its 23 cues, keep the three narrative buckets contiguous and allocate them 14 / 5 / 4. Cycle only within Sets 01–12 for the first bucket, 13–16 for the second and 17–20 for the third; do not wrap Set 20 back to Set 01 at the ending.
- **Proven crop geometry:** each Left and Right crop retains 60% of scene width, giving 20% shared center overlap; each Top crop uses the full width and upper 48% of the scene. The crops faithfully preserve approved pixels and seam imagery without another generation pass.
- **Verification boundary:** numerical RGBA validation does not establish artist acceptance or buildable movement grammar. Do not send either rejected 108-panel batch to `Tools/WingCutoutPipeline/run_wing_pipeline.py`; final selected Wings also need a production-resolution check.
- **Outstanding:** visually review the 23-cue forest-to-industrial sequence, silhouette depth and relief under production lighting. If rejected, restore `/Game/InfinityStage/Dev/SavedVersions/DA_InfinityStage_V1Show_P02_PreAnimalsToShrineV2_20260815`; keep the 5 cm batch quarantined as historical output.
- **Evidence:** source packs above; `DerivedAssets/Passage01V2Batch/GeneratedWings/wing_pipeline_report.json`; `DerivedAssets/Passage01V2Batch/fbx_clean_reimport_validation.json`; `DerivedAssets/Passage01V2Batch/texture_registration_validation.json`; `Saved/CodexWingIntegration/preflight_all_passages.json`; markers `P02_V2_IMPORT_SUCCESS`, `P02_ANIMALS_SHRINE_ASSIGN_SUCCESS` and `P02_ANIMALS_SHRINE_VERIFY_SUCCESS`.
- **Thread ID:** `019ffdcf-550f-7c20-8347-ff33118ed418`.

### 13. Place ready FBX wings into Infinity Stage Passages

- **Handover state:** The supplied P02/P03/P05 scope reached a verified sequential checkpoint through the standard loopback Python route. P02 remains verified; P03 requires re-import/validation after the clean rebuild; a later, externally authored or otherwise unattributed P05 duplicate-root save now needs fresh read-back. This task remains a reusable intake point for future explicitly named Passage/FBX scopes after that reconciliation.
- **Codex app state:** last recorded `idle`; no task-state inference is used for the completed integration claim.
- **Next:** for a future scope, provide exact Passage(s) and V2 FBX family. Repeat preflight → scoped import → Show backup/edit → one-actor materialization → targeted save → independent read-back; never run competing screen-driven writers.
- **Thread ID:** `01a00122-ce51-7a50-9f43-9a0d77e1dc15`.

### 14. Generating Cloud Wings

- **Handover state:** the 22 current-scope Cloud Wings—8 L/R pairs and 6 C Tops—are cleanly rebuilt. The original in-place repair and one-fifth ceiling scale were independently verified at 11:09 BST, but a later saved reroute to a duplicate Unreal content root has no post-change read-back. Current Passage 5 routing therefore needs integration verification plus human visual acceptance.
- **Codex app state:** `notLoaded`; the completed clean-build checkpoint and later unverified root change are distinguished by evidence below, not by this state.
- **Latest task outcome:** completed at 05:24 BST. The user identified the earlier Task Manager-staged V2 FBXs as visually glitchy despite their initial import checks. The Cloud task regenerated all 22 from the accepted transparencies with applied transforms, 10 cm X depth, 10 m final height, baked 90° yaw, one `UVMap`, Front/Back/Edge slots and deterministic pre-export triangulation/cleanup. Factory-clean re-import found zero non-triangle faces, non-manifold edges or degenerate triangles across all 22.
- **Verified in-place repair checkpoint:** the clean meshes from `GeneratedWingsV2_Clean/` replaced `/Game/Wings/Passage05_BirdToMountain/StaticMeshes` in place. A pre-repair Show backup was saved at `/Game/InfinityStage/Dev/SavedVersions/DA_InfinityStage_V1Show_P05_PreCleanFBXRepair_20260815`; 23 obsolete Left image flips were removed, the actor materialized 93 pairs, the Show and level were targeted-saved, and independent read-back reported zero dirty packages.
- **Verified ceiling checkpoint:** at 11:09 BST, all 93 Top occurrences referenced the six clean `SM_CloudCeiling*_*_C` assets under the in-place repair root and used absolute local scale `(X=1.0, Y=0.2, Z=0.2)`. With the baked V2 orientation, X preserved the 10 cm thickness while width and height became one-fifth, giving 2 m-high ceilings approximately 3.53–7.41 m wide. The requested reassert/materialize pass was deliberately idempotent—`mesh_changes=0` and `scale_changes=0`—then target-saved the Show and level. Independent read-back found 93 rows, 93 materialized pairs, six Top meshes distributed 16/16/16/15/15/15, zero source flips and zero dirty packages.
- **Post-verification saved change:** at 12:09 BST a separate `/Game/Wings/Passage5_BirdToMountainV2` root appeared with 110 assets: 22 Static Meshes, 22 textures and 66 per-slot materials. All 22 mesh import records point to the same `GeneratedWingsV2_Clean` FBXs and matching source MD5s. At 12:31 BST the Show Asset and vertical-slice level were saved; later Show/Master saves at 17:16 and a level save at 17:34 preserve file-level evidence of all 22 unique Passage 5 mesh paths under this new root and none under `/Game/Wings/Passage05_BirdToMountain`. **Verified fact:** the current saved files contain the new-root references. **Inference pending Unreal read-back:** current P05 rows and materialized components were rerouted to them. The file evidence does not prove 93-row transforms, material correctness, live actor state or a clean dirty-package boundary. No task outcome or post-change Unreal verifier was found, so authorship and acceptance are unconfirmed.
- **Remaining live-view ambiguity:** an exhaustive comparison of all 279 live actor component references had already failed to finish because the local execution approval timed out twice; no `audit_live_show_and_actor_v2_result.json` or success marker was produced. The later root switch makes a fresh authoritative Show/actor/material read-back mandatory. Do not claim that either the earlier component audit or the new-root integration completed verification.
- **Scoped art-direction exception:** the user explicitly said not to worry about Passage 5 height/bump maps during this clean rebuild. No derived maps were regenerated; at the verified in-place checkpoint all 22 material instances had `HeightRatio = 0.0`. The later duplicate root uses a different 66-material/22-texture layout and its parameters are not yet verified. This exception does not relax the general V2 Base/height/normal rule for other new production Wings.
- **Quarantine:** the bad Task Manager FBXs are preserved beside the clean batch under `GeneratedWingsV2_Broken_TaskManager_NonProduction/` with `DO_NOT_IMPORT.md`. The earlier 5 cm package remains separately non-production.
- **Evidence:** `DerivedAssets/Passage05BirdToMountainBatch/README.md`; `GeneratedWingsV2_Clean/wing_pipeline_report.json`; `GeneratedWingsV2_Clean/clean_fbx_validation_report.json`; `Saved/CodexPassage05/reimport_clean_passage05_v2_result.json`; `Saved/CodexPassage05/verify_clean_passage05_v2_result.json`; `Saved/CodexPassage05/preflight_ceiling_scale_v2_result.json`; `Saved/CodexPassage05/apply_clean_assignment_ceiling_scale_v2_result.json`; `Saved/CodexPassage05/verify_clean_assignment_ceiling_scale_v2_result.json`; `Content/Wings/Passage5_BirdToMountainV2/`; current Show/level package strings and timestamps; markers `P05_CLEAN_FBX_BATCH_VALIDATE_SUCCESS`, `P05_CLEAN_REIMPORT_SUCCESS`, `P05_CLEAN_VERIFY_SUCCESS`, `P05_CLEAN_ASSIGN_CEILING_SCALE_SUCCESS` and `P05_CLEAN_ASSIGN_CEILING_SCALE_VERIFY_SUCCESS`.
- **Next:** through the guarded loopback route, read back the current Show's 93 P05 L/R/T paths, flips and transforms; inspect all 22 new-root meshes' bounds/source plus material slots and parameters; compare all 279 live actor components; require a new explicit success marker; then decide which root is canonical before another save or visual acceptance. Do not delete either root. If the sequence is rejected, the pre-clean-repair backup above remains the restoration point.
- **Thread ID:** `01a001d2-43cf-7090-ab2f-98ab9a9ca49c`.

### 15. Review and import usable assets

- **Handover state:** `notLoaded`. Its broad mountains/birds/bees review has no new outcome summary. P02/P03 import and cue integration remain independently verified; P05 reached the same checkpoint but a later unattributed duplicate-root save requires a new authority read-back.
- **Codex app state:** `notLoaded`; do not infer the broader review is complete.
- **Next:** continue enforcing the same V2 gate for future assets. Quarantine rather than silently import a non-compliant new asset; label genuine vendor/legacy content instead of rebuilding it without scope.
- **Thread ID:** `01a001be-098a-7910-b69c-b8e883f10338`.

### 16. Add walking cat behind camera

- **Handover state:** Substantial implementation and duplicate-cleanup are live; runtime-warning cleanup and final behavioral/visual acceptance remain. The replacement AnimX Advanced Cats content is present under `Content/AnimX`, and the Infinity Stage adapter now exists at `/Game/InfinityStage/Internal/BP_InfinityStageShadowCat`.
- **Codex app state:** `notLoaded`; the implementation claim comes from the completed task outcome, native source and current Unreal log, not this execution state.
- **Delivered design:** every `AInfinityStageCameraRig` owns one `UInfinityStageShadowCatComponent` child adapter. Moving bypasses the vendor locomotion blend and loops `/Game/AnimX/_Common/CatMannequin/Anim/Move/Walk/A_Cat_Move_Walk_F`; stopped uses `A_Cat_Idle_Base`. Play rate derives from the evaluated camera speed and is bounded by parent-rig controls for position, rotation, scale, walk blend speed and maximum rate. Cast-shadow, main-pass and reflection visibility are independently configurable.
- **Duplicate guardrail:** editor hooks on map-open and End PIE remove only unclaimed `BP_InfinityStageShadowCat` camera children while retaining the six adapters owned by the six camera rigs. The original reproduction found 44 attached cats, of which 38 were stale; the task's module-0015 verification removed the 38 without saving. Current log markers repeatedly report `claimed=6|attached_adapters=6|level_dirty=0`, and later PIE restarts report `removed=6|claimed=6` rather than unbounded accumulation.
- **Current live proof:** repeated PIE runs emit `SHADOW_CAT_READY` for all six camera rigs with the expected mesh, direct-walk mode, camera-relative offset, visibility and registration. The vertical-slice level was explicitly saved at 16:13 BST after route/cat authoring and passed Unreal's one-asset validation. This proves the level write, not the exact intended rig values; scale/height differ among rigs in the log and need authoritative read-back.
- **Known blocker:** PIE currently emits repeated `S_Styles_R.SpeedMultiplier` empty-array warnings from `CompBP_Material_R_ANX_C` and collision/simulation warnings for each adapter's `HeightFixer Sphere`. The direct animation bypass does not stop those vendor components from running. Do not call the integration runtime-clean or MRQ-ready until both warning families are resolved and a fresh log is clean.
- **Next:** read back all six saved rig settings and adapter ownership; remove the vendor array/collision warnings; then verify idle/walk switching and play-rate continuity under stop, accelerate, reverse and seek, plus shadow-only composition, reflection policy and MRQ determinism. Human acceptance of gait, scale and floor contact remains required.
- **Evidence:** task outcome `01a000f5-06c0-7f60-93fd-846b818c9f57`; `InfinityStageCameraRig.h/.cpp`, `InfinityStageShadowCatComponent.h/.cpp`, `InfinityStageEditorModule.cpp`; current `PussStage.log` markers `SHADOW_CAT_READY`, `SHADOW_CAT_ORPHAN_CLEANUP` and `SHADOW_CAT_EDITOR_CLEANUP`.
- **Thread ID:** `01a000f5-06c0-7f60-93fd-846b818c9f57`.

### 17. GO1 remote telemetry to UE camera control

- **Handover state:** Working end to end and in use on the Passage 1 camera.
  Calibration and performance remain; the transport layer is settled.
- **What it is:** the Unitree GO1's handheld remote drives UE camera rotation
  live, so a performer moving the dog looks around the virtual stage. Dog ->
  internal head Pi -> UDP -> `Go1Input` plugin -> Passage camera.
- **Where authority lives:** `Docs/Go1TelemetryProgress.md` is the subsystem
  handover (status, measurements, findings, limitations, all commands, Windows
  port). `Docs/Go1TelemetrySetup.md` is the operating procedure.
  `go1_pi_bridge/README.md` is the offline command card for use on the dog's
  hotspot, where the Mac has no internet.
- **Delivered:** `go1_pi_bridge/go1_remote_bridge.cpp` (runs on the dog, built
  in place with a direct `g++` call); `go1_pi_bridge/listen.py`;
  `Plugins/Go1Input/` providing the `Go1 Remote Receiver` component with
  absolute/velocity rotation modes, dog-mode mirroring, smoothing and response
  curve, receiver-clock fail-safe, editor-mode operation and on-screen
  diagnostics.
- **Verified:** 1489 packets / 30 s with zero gaps; packet age 3-10 ms over
  Ethernet; axes to +/-1.00; buttons decoded (X = `0x0400`, Y = `0x0800`).
- **Physical calibration:** 3.5 m screen at 3 m viewing distance gives
  `Yaw Range Deg` 30.3, `Pitch Range Deg` 18.2 and camera FOV 60.5 degrees.
  Both derive from the same measurement; changing the screen or the performer's
  distance means recomputing both.
- **Camera ownership integration (delivered 2026-08-20):**
  `UGo1RemoteReceiverComponent` now consults
  `AInfinityStageShowRoot::GetCurrentCameraOwner()` each tick:
  `Timeline` releases input entirely, `DogGazeOnly` selects Absolute and
  `DogFreeLook` selects Velocity. While ownership governs, the component's own
  dog-mode mirroring and remote toggle are ignored; both remain as fallbacks
  when no Show Root exists. `Go1Input` now depends on `InfinityStage`; the
  dependency is deliberately one-way. With `Target Camera Actor` empty the
  component rotates the player's current view target, so it follows camera cuts
  and one receiver can serve every camera — which is why it should live on the
  Show Root. Transitions (timeline handback, camera cut) re-centre so nothing
  snaps. Verified: clean build, `nm` on the base dylib with the editor closed,
  **37/37 automation tests** (`Saved/Logs/Go1OwnershipIntegration.log`, exit 0),
  and live resolution logged in the `SavedFixturePIE` fixture. No Show, level or
  Master content was opened or saved.
- **Immediate operational consequence:** authored ownership defaults to
  `Timeline`, so the dog now controls nothing until a Passage/Scene Camera Owner
  is authored or the Show Root's transient override is used. Unticking
  `Use Show Camera Ownership` restores the previous behaviour.
- **Receiver relocated (2026-08-20):** the component now lives on
  `InfinityStageShowRoot_0` rather than `InfinityStageCameraRig_0`, with
  `Target Camera Actor` empty so it drives the live view target — one receiver
  for every camera. Performed headlessly with the editor closed via
  `SubobjectDataSubsystem` (`add_component_by_class` is not exposed in this
  build), after backing the level up to `Saved/Go1Move/Backup/`. Fresh-process
  read-back confirms exactly one component on the Show Root with all 26 settings
  preserved; exactly one content file was written; 37/37 tests still pass.
  Scripts retained in `Saved/Go1Move/`.
- **Next:** confirm `Dog Mode For Gaze` / `Dog Mode For Turn` integers with the
  dog **standing** (it reports mode 0 while prone, so they are unverified);
  investigate ~22 fps in PIE; test the wireless path and watch `gaps`; tune
  smoothing and response curve by feel.
- **Not done, deliberately:** no auto-start service on the dog; no changes to
  the dog's system configuration; the Windows appendix is written but untested.
- **Interaction with Infinity Stage:** in Absolute mode the component overrides
  sequence-driven camera **rotation** (intended - Passage 1's rotation keyframes
  are suspended in favour of live control) while sequence-driven **location**
  still applies. Making the two compose instead would need a parent "gaze pivot"
  actor with the camera attached beneath it: a deliberate change to authoring
  hierarchy, not taken.

## Completed project and support threads

| Thread | Outcome | Thread ID |
| --- | --- | --- |
| Create Blueprints 5.8 repo | Private `rokeby/MCPBlueprintsGenerator-UE5.8` repository created and published; local plugin became its own clean source repository. | `019ff195-4947-7071-b39a-7b682ab72224` |
| Test MCP plugin redesign | Stage Wing Director 0.15.0 exit-fade feature delivered; package built; 11 tests passed. This is historical/legacy work now that Infinity Stage is the active architecture. | `019f7642-d008-74c2-9dd6-2a531837108d` |
| Import Sequencer sequences | Curtain sequence completion-state workflow explained; actor-level Force Keep State and section-level completion controls identified. | `019f98bf-6bcb-7a21-b537-a207298dd516` |
| Build wing cutout pipeline | PNG-to-Blender/FBX pipeline delivered and used for the Shore of Bones assets, including open/closed clam assets. | `019f758b-2e89-7802-b9da-94e2edf283c6` |
| Place curtain reveal scene | Contained-scene hierarchy and discovery workflow completed; real Empty Actor roots recommended instead of Outliner folders. | `019f9501-d1f8-71c2-bb15-a5a5caace75c` |
| Create animated theatre curtain | Two-layer physics curtain delivered as FBX and `.blend`, with three meshes, 323 bones and a 240-frame animation. | `019f98d0-7378-77e1-8fc3-b9d50245fd43` |
| Extracting PNGs | 20 K_Fab source images cleaned, renamed, validated as transparent RGBA PNGs and copied to the shared stage-materials folder. | `019f75aa-734e-7321-9357-5e5dcfff601d` |
| MCP Build of Plugin | UE 5.8 `MCPBlueprintsGenerator` sibling fork built with live inspect/validate/apply/compile/help tools, state fingerprints and project MCP configuration. | `019f75fe-0004-76a1-ac71-afd32320195a` |
| Stage Blueprints | Camera-framed alternating-aperture Blueprint patch compiled and imported; the patch is archived under `Saved/BlueprintAIImports/Imported/`. | `019f75a6-6503-75a2-91d9-cb418dabb92a` |
| Plan sequence import workflow | Defined a self-contained UE 5.8 shot-kit handoff: dedicated shot folder, Level Instance/sublevel, Level Sequence, known `StageOrigin`, explicit global-light bindings and dependency-safe source-control or Unreal migration delivery. No shot was imported. | `01a000ab-565a-7453-bcdd-01f85a1d0891` |

## Prioritized project TODOs

### P0 — finish and accept the newest work

1. Read back the current Passage 1 L/R facing and image-flip state in Unreal before visual acceptance: the latest live-Show JSON export records all 48 Left flips enabled, while the earlier `P01_V2_SEQUENCE_VERIFY_SUCCESS` marker recorded no photographic mirroring. Do not assume either snapshot is current without authoritative read-back.
2. Reconcile Passage 5 before visual acceptance. The 11:09 checkpoint verified 93 clean assignments and ceiling scale `(1.0, 0.2, 0.2)`, but the 12:31 Show/level files now contain all 22 paths from the later `/Game/Wings/Passage5_BirdToMountainV2` duplicate root and have no post-change Unreal read-back. Treat row/component rerouting as an inference until verified. Read the current 93 Show rows, 22 mesh sources/bounds/materials, 279 live actor components, transforms/flips and dirty state; choose a canonical root only after that evidence. Do not delete either root.
3. Reconcile the current Passage 2 authoring layers before more edits: read back the saved `13582.6 cm` route and camera-rig/cat values from the level, then inspect the autosaved five-Scene handoff match and 23-row smooth undulation. Intentionally save or discard the Show/Scene work; the production Show and Scene files themselves have not changed.
4. Resolve Shadow Cat's `S_Styles_R.SpeedMultiplier` empty-array and `HeightFixer Sphere` simulation/collision warnings, then verify deterministic idle/walk/play-rate behavior under stop, accelerate, reverse and seek plus shadow-only composition and MRQ.
5. Review Passage 3's six sanatorium-to-Chinoiserie L/R/C sets in motion; `_C` is Top-only and all image flips are false. Restore the pre-P03 Show backup if the sequence is rejected.
6. Restart and confirm that the Editor has loaded plugin `0.6.0-wing-modulation` and the newest `-0002` modules, including the Space transport toggle, Materialize Passage, render/interchange actions, Manual Editor Lighting, camera and Wing channels, camera-led reveal, Phased Breathe, Scrub View and nested/flat Cue views. The current process loaded the pre-build unnumbered modules.
7. Read back the managed Master before rebuilding. If all expected camera/reveal/Wing channels, bindings and keys are present, record an explicit success marker and continue to visual verification; otherwise rebuild it once. Verify curves/anchors, reveal frontier, PASS Temporality, Camera/Overview scrub modes and Scene handoffs.
8. Test **View → Editor Lighting**, **Actions → Render Selected Range…** and Wing Sequence insert/replace on disposable content, including one Passage, a multi-cue span, nested Scene cameras and the interchange success marker.
9. Apply and inspect a project-owned copy of the imported oak-strip floor instance on a bounded thin-box proof; verify scale and lighting without replacing the moving ground.
10. Integrate the celestial environment into `L_InfinityStage_V1VerticalSlice.umap` using the prepared one-shot script while the interactive Editor is closed, then verify it through Unreal read-back.
11. Inspect the current MW Wetlands Landscape state in Unreal; populate/assign/fill target layers as needed and verify the saved state rather than relying on the level timestamp.
12. Judge the verified Stage Opening shared-master relief and silhouette quality under grazing stage lighting.
13. Listen to all six managed music handoffs on a normal audio device and approve Source In/Out and fades.
14. Curate the remaining Stage Opening and interrupted Shore Mourning concepts before further generation/conversion.

### P1 — authoring and control

1. Freeze the approved Stage Opening L/R/Top family manifest only after current Unreal read-back and visual review; the complete pre-V2 restoration snapshot and two external 48-row Wing Sequence files are already available.
2. Define and implement the MIDI review/import layer for strum, phrase, sustain, accent and cascade movement proposals.
3. Replace five 15-second placeholder Scene sequences with authored Scenes and decide their external sound/control protocols.
4. Complete remaining mechanism-rate/range automation with deterministic phase continuity; Passage camera speed curves are now implemented.
5. Add the spline/route visualizer and clearance validation for normalized, custom, serpentine and helix paths.
6. Add attachment anchors for manual lights and animated props; complete the shadow-figure art/lighting proof.
7. Build the simple skeletal-mannequin Chaos Cloth sheet proof, then validate the same collision-source pattern on one mocapped MetaHuman.

### P2 — deferred Cue Desk and production hardening

1. Add draggable Source In/Out and fade handles, timeline zoom/pan/rulers and bounded audio audition.
2. Complete explicit analysis-to-cue fit diffs and marker editing beyond the delivered confirm/snap/pin-anchor workflow.
3. Add artist-authored groups and a dedicated Operator workspace; multi-row drag/drop and persistent pane ratios are delivered.
4. Add formal managed-build hashes/status and save the remaining Instanced Static Mesh material flags before a packaged build.
5. Profile active/preload chunk budgets on the final live-performance workstation.
6. Expand the fixture into the full Cue Score only after Scene durations, music locks and venue footprint are known.
8. **Scene authoring pass — camera, preview and sync.** Four related gaps, all confirmed against code on 2026-08-17 and best done together because they share the Scene/camera path. (a) The Cue Desk editor preview and Music Timeline are **Passage-scoped**: `GetSelectedPassage()` (`SInfinityStageCueDesk.cpp:3610`) falls back to the nearest preceding Passage, so selecting a Scene and pressing play replays the previous Passage and shows its music rail. PIE is correct because the transport enumerates all compiled segments. This blocks Scene music later. (b) `ClaimSegmentCamera` reads only the Scene sequence's **top-level** Camera Cut track, so a Scene whose **Camera Cut** lives inside a Shots subsequence is never claimed. Note the supported split that does work today: keep the Camera Cut on the Scene sequence and let a subsequence animate the bound camera — the claim only needs the cut at top level and does not care where the animation lives. (c) ~~Binding resolution could not find spawnables.~~ **Fixed 2026-08-17:** the claim now resolves through `Player->GetBoundObjects()`, with the direct sequence lookup kept as a pre-Begin-Play fallback. (d) Camera piloting: the Master has no possessable Passage camera, so the rig cannot be piloted from Sequencer; the proposed fix is a temporary pilot that bakes the delta into the Passage section's offset/rotation channels on exit, mirroring `AInfinityStageWingEditProxy`. **Partly done 2026-08-17:** Cue Desk → Sequencer push implemented (`FInfinityStageSequencerBridge`, View → Sync Sequencer Playhead, default off). Still open: the Sequencer → Cue Desk direction, and (a) itself — selecting a Scene still resolves to the preceding Passage for preview and the Music Timeline. **Note:** driving the Cue Desk playhead from Sequencer's playhead would resolve (a) largely for free, since Sequencer already evaluates the whole Master hierarchy including nested shots.
7. **Deferred by the user on 2026-08-16, not urgent.** Make rehearsal transport reachable. Once PIE playback enters a Scene, every seek is rejected with `Unsafe External Clock`, because `UInfinityStageTransportController::bPerformanceMode` defaults to `true` (`InfinityStageTransportController.h:60`), the dev fixture marks all five placeholder Scenes `DeclaredUnpausable` (`InfinityStageDevFixtureBuilder.cpp:411`) even though their music mode is `Silence`, and `IsUnsafeExternalMove` then blocks any move while the playhead sits inside one. The documented rehearsal escape is unreachable: no production code path sets `bPerformanceMode = false`; the only assignment in the plugin is in `InfinityStageEditorAutomationTests.cpp:639`. **Stopgap:** during PIE, untick **Transport → Performance Mode** on the Show Root actor. **Fix:** add a Rehearsal/Performance toggle to the Cue Desk transport and make the rejection notification name the blocking Scene and the toggle. **Separately, and only through the full Show-mutation protocol:** the silent placeholder Scenes should probably not declare unpausable external sound at all; consider deferring that until authored Scenes replace them.

## Operational invariants

The system overview defines the components and boundaries. These are the short
rules that must remain true during implementation and authoring:

- There is one ordered Show authority, one Master playback clock and no hidden
  side database maintained by the Cue Desk, Python or MCP.
- A Show mutation is not a completed world edit until the affected Passage is
  materialized, the intended packages are target-saved and Unreal read-back
  confirms the result.
- Music analysis and MIDI may propose semantics; confirmed Show/Master data owns
  playback.
- A mesh/material-only reassignment does not require a Master rebuild. Cue
  order, timing or duration changes do.
- Passage Actor routes and ordinary scenic level content remain separate from
  plugin-generated score/timeline data.
- `Plugins/InfinityStage` is active production architecture;
  `StageWingDirector` remains legacy/reference work.
- `Docs/CodexUnrealMCPRunbook.md` is the canonical automation procedure.
- Nothing on the GO1 is modified beyond `~/go1_bridge/` and one
  `authorized_keys` line: no `sudo`, no package installs, no edits inside
  `~/Unitree`, no service or network configuration changes. The bridge sends an
  idle `HighCmd` with every motion field zeroed each tick and never commands
  the robot to move.

## Tool playbooks worth preserving

### Infinity Stage Show edits

1. Read `AGENTS.md` and `Docs/CodexUnrealMCPRunbook.md`.
2. Stop PIE and inspect the authoritative Show Asset first.
3. Use exact Unreal object paths and stable cue/Passage identities.
4. Before replacing an existing art set, serialize the exact affected cue rows
   (Left, Right and Top paths plus stable identities) as a restoration snapshot.
5. Make a narrow, deterministic, idempotent edit with explicit assertions.
6. For nested Unreal structs, assign every changed child back to its parent and
   assign the complete `cues` array back to the Show Asset.
7. Materialize exactly the affected Passage Actor(s).
8. Save only the affected Show Asset and level; never use **Save All** when
   unrelated packages may be dirty.
9. Require a unique success marker in the live Unreal log.
10. Run a separate read-only verifier and compare the exact saved Unreal values.

For a whole-set trial, prefer duplicating the complete Show Asset into
`/Game/InfinityStage/Dev/SavedVersions/` before mutation; a mesh-only list does
not preserve movement, timing, transforms or overrides. Record both versions in
`Docs/Passage1SetVersions.md` and require a verifier marker that includes
`backup_readback=1`. That checkpoint's StageOpeningV2 orientation rule was
verified as `left_preserve+right_rotate180` with no photographic mirroring; do
not assume it is still the live state, because the later exported live-Show
snapshot records all Left image-flip flags enabled. Read back the authority.

A mesh-only reassignment does not require a managed Master rebuild. Timing,
ordering or duration changes do.

### Reusable Wing Sequence files

After restarting into the current plugin, use **Actions → Wing Sequence Files**
in the Cue Desk. **Export Selected Wing Pair(s)…** writes the ordered selection;
**Export Whole Current Passage…** also preserves its spacing/camera envelope.
The default library is `Saved/InfinityStage/WingSequences`. The schema-v1 JSON
is readable metadata that references soft asset paths—it does not copy meshes,
materials or textures and never becomes a second Show authority.

Use **Apply Saved Arrangement to Current Passage…** for the normal tuned-set
restore: it repeats/trims the saved design order across the target's existing
music-fitted rows while preserving Passage/row labels, count, timing, spacing
and IDs. Use **Import and Insert After Selection…** for fresh rows or
**Advanced: Replace Complete Passage Rows…** only when the file's count, labels,
timing, spacing and envelope should be adopted. Complete Replace preserves the
target Passage GUID/label, Music Rail, celestial temporality, camera curves and
adjacent Scene ownership. Imported fresh cues get fresh Cue/Occurrence GUIDs;
in-file Camera Gust anchors are remapped and orphaned partial anchors become
safe one-pair groups.

The Fit panel's **Reset wing count from music** targets the selected Passage and
uses its complete existing Wing order as the expansion pattern. The recommended
restore order is reset count from the target music first, then Apply Saved
Arrangement. PASS headings are directly renameable by double-click; Passage
renaming is independent of Wing row labels and imports.
After import, the plugin reconciles the Show, rematerializes affected Passage
Actors and rebuilds plugin-owned Master tracks, but deliberately leaves changed
packages dirty for an intentional targeted save. Require
`INFINITY_STAGE_WING_SEQUENCE_IMPORT_OK`, then read back the Show and affected
Passage before saving. Unsupported newer schemas are rejected rather than
partially applied.

Opening a different Show in the Cue Desk does not rebind the level. Exporting it
needs no viewport refresh. To preview it, stop PIE, set each affected Passage
Actor's **Show Asset**, click the void **Materialize Passage** Details button and
require `INFINITY_STAGE_MATERIALIZE_OK`; do not save the level unless the preview
assignment is meant to persist. There is not yet a transactional **Apply Current
Show to Level Preview / Restore** Cue Desk action.

### Wing source handedness before conversion

Use `Docs/WingGenerationConventions.md` as the canonical pair check. Before
generating Base Color derivatives, normals or FBX files, review `*_L` and `*_R`
together with the passage centre between them: Left exterior edge on image-left,
Right exterior edge on image-right, both inward edges pointing toward centre.
Correct a backwards generated source once at source-art stage, then regenerate
all derived maps. Do not use FBX yaw to repair image handedness, do not use image
mirroring to repair physical face direction, and do not make a new asset depend
on Unreal's per-occurrence **Flip Image Horizontally** flag. Preserve legacy
flags unless a paired preview and artist-approved migration explicitly covers
them.

### External Sequence and set-dressing handoff

Use `Docs/KlaraDioramaLevelSetup.md` as the literal external-contributor
checklist. It specifies the **Basic → Empty Actor** `DioramaOrigin`, identity
transform, centimetre units, axis/front agreement, file paths and migration
scope.

For a contributor-authored cinematic, use the same Unreal 5.8 PussStage project
or a source-control branch and keep the main level as locked visual context.
Deliver one self-contained kit such as
`/Game/InfinityStage/Shots/P03_Shot010/` containing a dedicated Level
Instance/sublevel, Level Sequence and all local assets/materials, placed against
an agreed `StageOrigin` pivot. Use spawnables for cameras, temporary effects and
sequence-only actors; use possessables for actors owned by the supplied Level
Instance. Main-level actors require deliberate rebindable bindings. Keep local
lights with the set, but document or explicitly bind any global sun, Skylight,
fog, exposure or post-process change so duplicate systems do not compete.

Hand over the complete folder through source control. If a separate project is
unavoidable, use Unreal **Asset Actions → Migrate** on both the shot level and
sequence so dependencies travel together; do not manually copy selected
`.uasset` files. Integration then places the Level Instance once, binds main
actors deliberately and adds the Level Sequence as a child shot/subsequence.
Only timing, ordering or duration changes belong in the authoritative Show
Asset and require a managed Master rebuild, affected-Passage materialization,
targeted saves, success marker and read-back.

### Unreal MCP and Python fallback

- The current standard no-UI route is the local MCP toolset
  `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`, tool
  `ExecuteProjectPythonFile`. Pass a `.py` path relative to the project
  `Saved/` directory; the executor rejects absolute/traversal/non-Python paths.
- The project endpoint is configured in `.codex/config.toml` at the loopback-only
  address `http://127.0.0.1:8000/mcp`. Require both
  `PROJECT_PYTHON_EXEC_SUCCESS|<path>` and a script-specific success marker.
- Start with `Saved/CodexWingIntegration/remote_healthcheck.py`, then use a
  separate deterministic preflight, mutation and read-only verifier. A
  successful transport call is not proof of saved state.
- Epic Remote Python is enabled and the Editor listens on `127.0.0.1:6766`, but
  official UE 5.8 multicast discovery returned zero nodes on this macOS host.
  `Tools/UnrealRemote/unreal_remote_exec.py` remains diagnostic only until its
  own health check passes.
- Coordinate-driven use of the Editor's one-line Python field is now a
  last-resort fallback. Screenshot and confirm focus first; a stale focus can
  paste unrelated text and produce a misleading `SyntaxError`.
- Never run a second Unreal process against a map already open for editing.

### Headless Infinity Stage plugin build and tests

Use the exact macOS commands in
`Docs/CodexUnrealMCPRunbook.md#headless-plugin-build-and-test-no-editor-ui` for
code-only verification. The interactive Editor must be closed before invoking
either UE 5.8 `Build.sh` for target `PussStageEditor Mac Development` or
`UnrealEditor-Cmd` with `-NullRHI` and `Automation RunTests InfinityStage`.
This route rebuilds `Plugins/InfinityStage` and runs automation tests; it opens
no map and saves no content, so authoring read/write work still uses the guarded
loopback MCP route above.

Require process exit code `0`, `**** TEST COMPLETE. EXIT CODE: 0 ****` in the
dedicated `-abslog`, and zero `Result={Fail}` lines. Unreal treats an unexpected
Error-level log as a test failure even when assertions pass; a test that
deliberately exercises a refusal path must register its expected error with
`AddExpectedErrorPlain` rather than weakening the gate.

### MCP Blueprints Generator

The UE 5.8 tool loop is:

1. `InspectBlueprint` with an explicit object path.
2. Create one complete JSON specification using
   `Plugins/MCPBlueprintsGenerator/Examples/GeneratorSchema.md`.
3. `ValidateSpecification` with the inspection fingerprint.
4. `ApplySpecification` with that same fingerprint.
5. `CompileBlueprint`, then inspect again and resolve compiler/pin diagnostics.

Specifications are deliberately coarse-grained and atomic; do not fall back to
fragile node-at-a-time mutation. The manual fallback folder is
`Saved/MCPBlueprintImports`, and successful specifications move to its
`Imported` subfolder. Project-history examples referencing `BP_Stage`,
`BP_Wing` or `Stage` must not be run unchanged in other projects.

### Cue Desk and stage-content authoring

- Click the body of a **PASS** row to select Passage-wide controls; its arrow
  only expands/collapses Wing rows.
- Passage **Temporality** is the intended home for apparent-time controls.
- **Scrub View: Overview** keeps Master-frame wing/camera-rig evaluation while
  leaving the editor viewport free; **Camera View** follows the Passage camera.
- Use nested view to work with contiguous Wing rows beneath a renameable Passage
  header and flat view for the complete cue order. Multi-select rows before
  dragging a range. Passage undulation phase follows each row's current cue
  ordinal, so a reorder intentionally changes the travelling wave immediately.
- Music-analysis markers remain proposals until confirmed. Confirm the intended
  markers, use **Curve Actions → Pin Confirmed Music Markers as Anchors**, and
  enable marker snapping when aligning camera keys; hold Option while dragging
  to bypass snapping temporarily.
- Use the previous/next Master-segment controls to rehearse later Passages in
  PIE without changing the authoritative cue order. Verify autoplay/frame-zero
  camera ownership after any camera-routing change.
- After the `-0002` build is loaded, give the Cue Desk focus and press bare
  **Space** to stop a running editor/PIE transport or play forward when stopped.
  The binding intentionally ignores modified/repeated Space, lets text fields
  consume it while typing and uses the normal transport constraint path rather
  than creating another playback clock.
- For a reliable working light, use **View → Editor Lighting → Manual Editing
  Light** and choose a preset or select the Celestial Rig for exact 0–24-hour
  preview controls. Use **Follow Master While Editing** only when inspecting the
  show progression. Save the level only if the chosen preview should persist;
  PIE, transport, MRQ and packaged playback remain Master-driven regardless.
- For MRQ, save the level and edited Scene sequences, select a `PASS` or cue-row
  range, then use **Actions → Render Selected Range…**. The idempotent action
  creates `/Game/InfinityStage/Generated/Renders/LS_<Show>_RenderSelection`,
  saves only the Show, managed Master and wrapper, and updates one stable queue
  job without clearing other jobs or resetting that job's configuration. Scene
  ranges keep their nested Camera Cut authority. Do not author tracks in the
  replaceable wrapper. `Render (Remote)` sees only saved packages; on Mac,
  PNG/EXR plus WAV is the recoverable long-render fallback.
- Outliner folders are visual organization, not attachment parents. Use real
  Empty Actor roots beneath a contained-scene rig, or explicitly list actors
  whose hierarchy must remain unchanged.

### Imported wood-floor materials

1. Preserve the vendor roots `/Game/4K_WoodFlooring_Vol_01` and
   `/Game/4K_WoodFlooring_Vol_02`; the verified import retained only Materials
   and Textures and excluded demo maps, architectural meshes and TrueSky.
2. When auditing migrated content, count `MaterialInstanceConstant` registry
   classes directly. Vol.01 also contains redirectors from renamed Versailles
   assets; following redirects double-counted the first audit.
3. If Unreal MCP is offline, use the open-Editor Python fallback in
   `Docs/CodexUnrealMCPRunbook.md`; target-save only useful material assets,
   then use a separate read-only pass to verify every instance's parent.
   `Saved/WoodFloorImportAudit.json` is the durable result: 305 assets, 50 real
   instances and an empty `failures` list.
4. Do not call an explicit editor quit after an intentional audit failure; the
   first verifier's unnecessary quit caused a macOS shutdown crash. Let the
   executor return normally, fix the class-count assertion and rerun safely.
5. Duplicate a chosen instance into project-owned content before tuning. The
   first recommended proof is
   `/Game/4K_WoodFlooring_Vol_01/Materials/M_Oak_Strp_01_Mat_Inst` →
   `/Game/Stage/Ground/Materials/MI_Ground_OakStrip_01`; use the instance, not
   the shared `M_Flooring_Mat` master. Apply it to a bounded thin box, inspect
   board scale/rotation and lighting, and leave `M_StageMovingGround` untouched.

### Scenic cutout and curtain assets

- The reusable PNG-to-Blender/FBX procedure is documented in
  `StageWingCutoutPipeline/README.md` and `Tools/WingCutoutPipeline/README.md`.
- Every newly generated production Wing uses the V2 profile in
  `Docs/WingGenerationConventions.md`: final handedness first; explicit source
  height `2.0 m`, panel scale `5.0`, `--thickness-cm 10` and baked yaw `90`;
  Base/alpha plus `_H` height, `_N` DirectX normal and relief preview; one
  `UVMap`; Front/Back/Edge slots; pipeline-report success and a clean FBX
  re-import. The tool's 5 cm default is legacy compatibility only and must not
  be inherited by a new production batch.
- For complex alpha silhouettes, `Tools/WingCutoutPipeline/blender_png_to_wing.py`
  must clean and triangulate the exact mesh before export. Then run
  `Tools/WingCutoutPipeline/validate_fbx.py` from factory-startup Blender with
  `--height-m 2 --panel-scale 5 --thickness-m 0.10 --thickness-axis x` and
  require `WING_FBX_VALIDATION` to report `status=ok`, one `UVMap`, three slots,
  `non_triangle_faces=0`, `non_manifold_edges=0` and
  `degenerate_triangles=0`. Passage 5's aggregate example is
  `DerivedAssets/Passage05BirdToMountainBatch/GeneratedWingsV2_Clean/clean_fbx_validation_report.json`
  and its batch marker is `P05_CLEAN_FBX_BATCH_VALIDATE_SUCCESS|count=22`.
- The current clean Passage 5 rebuild is a documented user exception to the
  derived-map portion of V2: do not regenerate height/bump maps and keep
  `HeightRatio=0.0`. Do not copy that exception to other Passage families.
- To resize a ceiling occurrence without changing its production FBX, edit the
  Top panel's `local_transform.scale3d` in the authoritative Show data using an
  **absolute** target, not a multiplicative delta. Passage 5's baked V2 axes use
  `(X=1.0, Y=0.2, Z=0.2)`: X preserves 10 cm thickness and Y/Z reduce width and
  height to one-fifth. Inspect all scoped rows first, reassign the nested pair and
  complete cue array, materialize only that Passage, target-save Show and level,
  then independently read back exact scale, mesh distribution and dirty state.
  Require `P05_CLEAN_ASSIGN_CEILING_SCALE_SUCCESS` followed by
  `P05_CLEAN_ASSIGN_CEILING_SCALE_VERIFY_SUCCESS`; the proven rerun reported
  `mesh_changes=0|scale_changes=0`, preventing an accidental second reduction to
  4%.
- For the six ready Chinoiserie LiDAR panels classified under `Other`, follow
  `DerivedAssets/V2_MANUAL_IMPORT_README.md`: import 18 textures manually, import
  the six FBXs at rotation zero/scale one with materials/textures/collision off,
  reuse `/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master`
  and `M_StageOpeningV2_Edge`, and never add another L/R image flip. The local
  `GeneratedWingsV2_Chinoiserie/wing_pipeline_report.json` is the validation
  source; these files have not yet been imported into Unreal.
- Treat transparent PNGs, Blender sources, FBXs, copied textures and pipeline
  reports as one handover unit. Record their output folder and validation result.
- For a selected V2 batch, use one Blender startup, a bounded trace resolution,
  stronger simplification for open scaffold/gauze silhouettes, no `.blend` saves
  unless source handoff requires them, and no duplicate embedded raster payload
  in each FBX. Preserve explicit base/height/normal texture files and the batch
  `wing_pipeline_report.json`.
- Drive the Stage Opening V2 Unreal import from
  `DerivedAssets/StageOpeningV2Batch/unreal_batch.json`. The proven 14-panel run
  used two bulk import calls and produced 72 scoped assets: 14 meshes, 42
  textures, 14 material instances, one relief master and one Edge material.
- In UE 5.8 Python, do not call `Texture2D.post_edit_change()` after setting
  texture properties: it is not exposed and raises `AttributeError`. Property
  assignment plus targeted asset save was sufficient. Keep the importer
  idempotent so a rerun after interruption reuses the imported assets rather
  than duplicating them.
- In Unreal, prefer one compiled relief master plus one shared Edge material and
  per-panel material instances. Verify parent/parameters and mesh slots by
  read-back after import; file count alone is insufficient.
- For an approved 4×3 scenic matrix, the proven low-cost extraction workflow is:
  freeze the final matrix; number its cells row-major `S01`–`S12`; remove gutters;
  crop Left and Right to 60% width each for a 20% shared seam; crop Top to full
  width × upper 48%; then validate every output as readable and non-empty. Keep
  these as opaque source art and isolate alpha only after curation. The canonical
  example and naming map are
  `DerivedAssets/GeneratedConcepts/Passage02Forest/RousseauLayeredLightFinal/README.md`;
  its dense-dark and lighter predecessors remain versioned beside it under
  `RousseauDenseWetFinal/` and `RousseauFinal/`.
- For a dense scenic pack that reads too dark, revise light by depth rather than
  applying one global exposure change: preserve the nearest side foliage, roots
  and principal top bough as the darkest plane; selectively lift the middle
  vegetation; reserve the lightest values for deep foliage and the receding
  route. Preserve composition, biomass, seam geometry and palette progression,
  recrop from the versioned successor, then rerun the per-matrix audits.
- For Passage 2 transparent art, separate physical component design from alpha
  validity. L/R must be freestanding masses without ceiling branches; T must be
  a substantial connected multi-member ceiling cluster. Use soft botanical
  inner edges and ensure each file represents one buildable moving object.
- Magenta semantic mattes can be converted to RGBA with a soft matte, despill
  and one-pixel contraction, as documented by the superseded
  `RousseauTransparentCutoutsFinal/README.md`. This removes fringe but does not
  prove art direction or component grammar. Preserve every experiment as a
  versioned pack and never promote it solely because alpha statistics pass.
- To prevent small-object image-generation drift, lock one approved side and
  one approved top reference, generate fewer/larger objects per image, and audit
  painterly texture, wet directional lighting and silhouette variation before
  scaling. The current approved grammar is Rousseau-like matte pigment plus
  dark foreground/readable middle/cool recessed light; selective wet darkness,
  upright/forked/scalloped side shapes and substantial upper foliage.
- For the actual Passage 2 production sequence, never feed a contact sheet,
  matrix or composite back into ImageGen. Generate exactly one set at a time as
  three separate full-resolution files—L, R, then T—using only the approved
  individual anchors and the immediately accepted set where continuity is
  needed. Stop for artist approval before the next set. The canonical current
  output is `RousseauApprovedIndividualSequenceV5/chroma/`; Sets 01–20 now
  exist, and their 60 cleaned RGBA handoff files passed reported alpha and
  handedness QA. Their first 5 cm FBX conversion is superseded and must not be
  imported; follow the V2 correction gate recorded in section 12.
- Before spending on repair or regeneration, use `ffmpeg` to build one L/R/T
  audit montage per matrix and inspect vegetation structure, shared side seams
  and top-branch continuity. Normalize and pad each mixed-aspect input PNG to a
  common tile canvas before applying the tile layout. Store the proof beside the
  pack under `audit/`. Both the dense-wet and layered-light packs' three
  montages passed this check, so their exact-pixel crops remain valid comparison
  sources.
- Curtain FBX import/animation specifics live with each artifact under
  `DerivedAssets/CurtainAnim/README*.md`.

### MW Wetlands Landscape setup

1. Assign `/Game/MWMeadowWetlands/Materials/Ground/MTL_MWL_Landscape` to the
   Landscape actor's **Landscape Material** property.
2. In Landscape Paint, use the lightning-bolt **Populate Target Layers from
   Materials** control when the panel reports zero targets.
3. Assign the supplied `Dirt_LayerInfo` from
   `/Game/MWMeadowWetlands/Maps/MeadowWetlandsLandscape_sharedassets/`, then
   right-click `Dirt` and **Fill Layer**.
4. Wait for shaders, then assign `Forest`, `Moss`, `Rock`, `Stones` and utility
   Layer Info assets as needed.
5. Inspect the rendered Landscape and saved Unreal properties; black output
   before layer initialization is not by itself a material compilation failure.

## Key learnings and mistakes not to repeat

| Learning / guardrail | Why it matters |
| --- | --- |
| `idle` and `notLoaded` do not mean completed. | Codex app state is execution state; completion must come from the final outcome and saved evidence. |
| Inspect → mutate → materialize → targeted save → read back. | A tool call, log line or timestamp alone does not prove the authoritative Unreal data is correct. |
| Do not use **Save All** for scoped automation. | It can persist unrelated dirty packages and make the mutation boundary unknowable. |
| Saving the current level can include pre-existing unsaved level edits. | Confirm dirty state and user-authorized scope before saving. |
| Do not assume nested Unreal Python struct edits serialize in place. | Reassign nested structs and the complete cue array explicitly. |
| Do not compare `str(FGuid)` in UE 5.8. | This build can return an address-like struct description rather than stable identity. Match exact stable cue labels/indexes/counts, or serialize numeric GUID fields explicitly. |
| Use `local_transform` for `FInfinityPanelDesign::LocalTransform`. | The first Passage 2 assignment stopped before Show mutation because the Python field was incorrectly called `transform`. Preserve each row's existing transform/facing when changing only its mesh/material/image settings. |
| Do not use `MaterialEditingLibrary.get_material_instance_*_parameter_value()` in a read-only verifier on this build. | The getter dirtied every inspected instance. Read serialized texture/scalar parameter arrays; if async compilation later dirties only the new content root, perform one asserted targeted settle-save and never broaden to **Save All**. |
| One owner writes the Show/level at a time. | Forest, Wing Gen and Cloud tasks fought for desktop focus. Freeze producers, preflight all target rows once, then integrate one Passage at a time through loopback Python with a clean-state gate between Passages. |
| Do not call `mark_package_dirty()` on `InfinityStageShowAsset` in this UE build. | It is not exposed to Python and produced `AttributeError`; explicit property edits plus targeted save are sufficient. |
| Live input written in `TG_PostUpdateWork` never reaches the camera. | The POV is snapshotted before that group, so the actor rotates but nothing renders - indistinguishable from dead input. Write camera rotation in `TG_DuringPhysics`. |
| Map a performer's stick to an angle, not a turn rate, when the view maps to a physical screen. | Velocity mapping runs into the pitch clamp and judders against the limit; absolute mapping has no limit to hit and returns to centre naturally. |
| Trust the dog's shipped SDK headers, not its shipped examples. | On firmware 1.3.8 `example_wifi_joy.cpp` uses fields `comm.h` does not define, and its `CMakeLists.txt` lists absent sources so `cmake` cannot configure. Build with a direct `g++` call. |
| Only one process can hold the telemetry UDP port. | Editor mode, PIE and a stray `listen.py` all compete for 9876; the loser reports no data with no other symptom. Check with `lsof -nP -iUDP:9876` before deeper debugging. |
| Never overwrite a map from a second Unreal process. | The interactive editor may hold a different in-memory package; close it or use the proven live-editor route. |
| Do not run headless plugin build/tests while the interactive Editor is open, and do not ignore Error-level test logs. | A second Unreal process can conflict with an open package, while Automation treats unexpected Error logs as failures even when assertions pass. On 16 August the live Editor had loaded the unnumbered Infinity Stage modules while a later build changed the manifest to `-0002`, leaving source/binaries ahead of the running process. Close the Editor before the canonical build/test commands, require exit-code/test markers, declare intentional errors with `AddExpectedErrorPlain`, then restart and confirm the actual loaded module. |
| Bypassing a vendor AnimBP does not disable the vendor actor's other Blueprint components. | Shadow Cat's direct `A_Cat_Move_Walk_F` path prevents trot/run selection, but live PIE still executes `CompBP_Material_R_ANX_C` and its `S_Styles_R.SpeedMultiplier` empty-array access, plus an incompatible `HeightFixer Sphere` simulation setup. Treat warning-free PIE as a separate gate: repair or disable the offending component paths and scan the fresh log before claiming runtime/MRQ readiness. |
| Preserve one Master clock. | Independent MIDI, audio or Tick clocks will drift from camera, wing and Sequencer state. |
| A green automated suite is not visual/audio acceptance. | Normal-device listening, viewport behavior, composition and lighting still require human checks. |
| Use Blueprint inspection fingerprints through validation and apply. | They prevent patches being applied to a Blueprint that changed after inspection. |
| Outliner folders are not actor hierarchy. | Contained-scene discovery needs real attachments or explicit actor lists. |
| Distinguish active Infinity Stage work from legacy Stage Wing Director work. | Fixes or packages for the legacy carousel do not automatically advance the finite-path production system. |
| A new preset in compiled code is not the same as applying it to the Show Asset. | Phased Breathe was implemented/tested without altering current movement selections; restart, select and apply deliberately. |
| Do not expand MCP tooling merely to create a portable FBX package. | Local PNG/Blender/FBX generation and validation can finish independently; add import tools only for a real repeated in-editor workflow. |
| A relief-ready FBX is not the complete visual asset. | The mesh carries geometry, UVs and material slots; base/alpha, height and normal textures must be imported separately with the documented colour space/compression. There is no extra fourth bump map—the height map drives Bump Offset. |
| Never let a new production Wing inherit the cutout pipeline's defaults. | The first current Passage 5 Cloud batch silently used the legacy 5 cm thickness and produced only its RGBA base texture. Require explicit V2 manifest values, derived-map presence and clean-reimport evidence before calling a batch ready or importing it. |
| A green pipeline report and clean FBX re-import prove the requested build, not current production-policy compliance. | The 60 Passage 2 and 22 Passage 5 batches both reported `status: ok`, valid UVs/slots and clean imports at 5 cm, yet remained non-production because the V2 contract requires 10 cm plus registered height/normal/preview files. Compare report values and the complete artifact inventory with `Docs/WingGenerationConventions.md` before import. |
| UVs, dimensions and material slots do not prove a complex cutout FBX is visually or topologically clean. | The first 10 cm Passage 5 Task Manager export passed the earlier checks but rendered as glitchy geometry. Clean the exact exported mesh, triangulate concave silhouettes before FBX export, then require both the generation report and a factory-clean re-import to report triangle-only topology, zero non-manifold edges and zero degenerate triangles. |
| Do not judge an in-place FBX replacement by its Unreal asset name, do not compound an already serialized scale factor, and do not treat a duplicate import root as integrated merely because it contains the right FBX source paths. | Passage 5's in-place clean geometry retained the old object names and all 93 ceilings already stored `(1.0, 0.2, 0.2)`. A later 110-asset duplicate root points to the same clean FBXs, and the subsequently saved Show/level files contain its paths, but no authoritative post-change read-back exists. Verify Static Mesh provenance/bounds/materials, absolute Show transforms and live components after every root switch. |
| Reusing a shared material architecture is preferable to compiling one full material per panel. | The 14-panel V2 batch uses one relief master, one Edge material and lightweight instances, reducing shader compilation and keeping tuning coherent. |
| Do not call `Texture2D.post_edit_change()` from UE 5.8 Python. | The method is not exposed and stopped the first Stage Opening batch run after import. Set the properties, target-save the assets and make the script safe to rerun over existing imports. |
| Separate bulk asset import from Show Asset assignment. | The verified Stage Opening batch added assets without changing the Show or level. A later Passage trial remains a distinct authoring mutation requiring a restoration snapshot, materialization, targeted saves and read-back. |
| Vary one visual-development dimension at a time. | Passage 2 style matrices keep begin/middle/end composition and route geometry fixed across rows so photographic language can be judged without confusing it with layout changes. |
| A mesh-path list is not a complete set-version backup. | Duplicate the authoritative Show Asset before a whole-set trial so timing, movement, transforms, overrides and unaffected Passages remain restorable; verify that duplicate by read-back before editing live rows. |
| Do not feed opaque contact-sheet crops directly to the Wing pipeline. | The Passage 2 extraction pack preserves approved pixels and seam overlap, but selected panels still need alpha isolation and production-resolution checks before `run_wing_pipeline.py`. |
| Do not overwrite an approved source-art pack during a major art-direction revision. | Passage 2 keeps a version chain—`RousseauFinal`, `RousseauDenseWetFinal` and `RousseauLayeredLightFinal`—so visual comparison and deterministic fallback remain possible. |
| Do not solve crushed-dark scenic art with one global exposure lift. | Passage 2 became more layered by retaining a dark wet foreground, selectively lifting the middle plane and placing the brightest values on the receding route; this preserved density and mood while improving depth separation. |
| Valid RGBA is not the same as a buildable, approved moving Wing. | The first 108-panel Passage 2 portal pack passed alpha checks but imposed hard U-shaped cuts, put ceiling branches in L/R pieces and reduced T to an unsuitable single-member role. Validate physical L/R/T grammar and artist acceptance before pipeline conversion. |
| Do not batch-generate many small scenic objects before style-locking large references. | Passage 2 drifted into outlined leaves, gold veins, conical symmetry, crushed blacks and a generic game-asset finish. Stop at a side/top proof, use the accepted render as a direct high-resolution anchor, generate fewer objects per image and scale only after approval. |
| Do not use contact sheets as references for Passage 2 sequence generation. | Even after the user requested individual Wings, the contact-sheet workflow remained visible and homogenized the style twice. Exclude every matrix/composite from the reference stack; generate one L, one R and one T at full resolution, stop for approval, then begin the next set. |
| Keep LiDAR/digital corruption off architectural silhouettes when the art direction calls for intact construction. | Repeated sanatorium revisions retained bites, clipped bands and fringe because “LiDAR/glitch” language kept affecting the boundary. Reset on one test with an intact rectangle or smooth arch and confine scan character to surface texture; approve that boundary before regenerating the family. |
| Audit extracted L/R/T panels before regenerating them. | Matrix-level montage review can expose broken seams or missing structure cheaply. All three dense-wet and all three layered-light montages passed, avoiding an unnecessary generation/repair pass while leaving alpha and resolution acceptance explicit. |
| Do not pass mixed-aspect L/R/T crops directly into an `ffmpeg` tile filter. | The first audit montage captured only one panel. Normalize/pad every input to the same tile canvas first, then assemble the montage; this leaves the source PNGs untouched and produces a reliable visual audit. |
| Resolve Wing image handedness before textures, normals or FBX conversion. | Earlier Left sources could require an Unreal **Flip Image Horizontally** repair, while a 180-degree stage-up yaw only changes mesh facing. Review the pair together, fix a backwards source exactly once and regenerate registered PBR maps; never flip a newly corrected asset again during placement. |
| Do not make a contributor's cinematic by editing the production level or Master directly. | A self-contained Level Instance plus child Level Sequence preserves set placement, lighting ownership, bindings and dependencies. Integrate it as a shot kit, and route only authoritative timing/order changes through the Show Asset and managed Master workflow. |
| Opening a Show Asset in the Cue Desk does not rebind materialized Passage Actors. | Export can operate directly on the opened Show, but level preview still requires each affected actor's **Show Asset** to be assigned and **Materialize Passage** invoked. Do not save the level unless that preview binding is intended to persist. |
| A non-void `CallInEditor` function may not appear as a Details button. | `MaterializePassage()` returned `bool`, so Unreal exposed only its void clear companion. Keep the Boolean API for code, but add a parameterless void wrapper with `DisplayName="Materialize Passage"`, a reflection test and an explicit log marker. |
| Use UE 5.8's exact value types in editor utility code. | The first Wing Sequence build failed because `FFrameNumber` was constructed from `int64` and a filename replacement character used invalid indexing. Round and cast to `int32` for `FFrameNumber`; pass `static_cast<TCHAR>('_')` to `MakeValidFileName`. |
| An exported Wing Sequence is a snapshot, not proof of current Show state. | The later live-Show JSON records all 48 Left image flips enabled while the earlier Unreal verifier recorded no photographic mirroring. Keep both as version history, but resolve current truth through Show read-back before acceptance or mutation. |
| Do not treat material-function variants as paintable Landscape targets. | In MW Wetlands, `DirtRough` and `ForestMoss` were initially described as layers but the actual main targets are `Dirt`, `Forest`, `Moss`, `Rock` and `Stones`. |
| A changed `.umap` timestamp is not proof of the intended edit. | Landscape work changed the level package, but without a success marker and Unreal read-back the exact saved state remains unverified. |
| Count migrated Unreal assets by registry class, not resolved redirect targets. | The first wood-floor verifier followed five renamed Versailles redirectors and double-counted real instances. Count `MaterialInstanceConstant` entries directly, assert parents in a separate read-back, and let the open-Editor executor return normally rather than explicitly quitting after a failed audit. |
| Do not link the public MRQ tab-name symbol on this Mac build. | The first selected-range build hit a platform linkage failure. Invoke the stable registered tab identifier `MoviePipelineQueue`; the clean UE 5.8 build then linked and the full suite passed. |

## Decision and learning log

Add an entry only when it materially changes future work. Keep the evidence
specific and do not restate ordinary task status.

| Date | Decision or learning | Evidence | Consequence |
| --- | --- | --- | --- |
| 2026-08-11 | Infinity Stage became the active finite, music-led architecture while Stage Wing Director remained separate legacy/reference code. | `Docs/InfinityStageOvernightReport.md` | New production work targets `Plugins/InfinityStage`; legacy fixes are labelled clearly. |
| 2026-08-13 | The Show Asset is the authoring authority and Passage Actors must be rematerialized after row changes. | `Docs/CodexUnrealMCPRunbook.md` and verified Passage 1 reassignment markers | All future authoring automation follows inspect/edit/materialize/targeted-save/read-back. |
| 2026-08-13 | Passage apparent time uses Master-frame evaluation with a 20-second default day/night cycle and Passage-level rate controls. | `Plugins/InfinityStage/Docs/CelestialCycle.md` | Celestial motion remains scrub/reverse safe and must not use an independent clock. |
| 2026-08-13 | Music/MIDI should describe movement semantics, while audio/Sequencer remains the playback clock. | Task `019ff304-2874-7862-a1ee-9c4d5e64a7f0` | Future MIDI work is a reviewed proposal/import layer, not live clock ownership. |
| 2026-08-14 | Passage camera curves live as native channels on managed Master Passage sections; the Cue Desk edits those same keys. | `Plugins/InfinityStage/Docs/AuthoringReference.md` | Rebuilding the managed Master preserves keys/valid anchors; do not introduce proxy camera-curve data. |
| 2026-08-14 | Normal Wing reveal is a spatial frontier driven by evaluated camera distance, not an independent seconds-based cascade. | `Plugins/InfinityStage/Docs/AuthoringReference.md` | Music/camera acceleration, hold, scrub and reverse deterministically control the same reveal; timed cascade is advanced compatibility only. |
| 2026-08-14 | V2 Stage Opening panels established 10 cm finished thickness while legacy cutouts remained 5 cm. | `DerivedAssets/GeneratedWingsV2/README.md` | This became the project-wide new-production contract on 2026-08-15: explicitly pass `--thickness-cm 10` and preserve accepted legacy outputs unless migration is in scope. |
| 2026-08-14 | Stage Opening visual grammar is Painted / Exposed / Covered. | Task `019ffd63-7ae2-70e0-8c8e-713d373ffce8` and generated concepts | Painterly/covered panels favour shallow relief; real rods/ties/negative spaces justify selective geometry. |
| 2026-08-14 | Stage Opening V2 uses one relief master, one shared Edge material and per-panel instances. | `DerivedAssets/StageOpeningV2Batch/unreal_batch.json` and independent Unreal read-back | Future tuning stays centralized; do not compile a separate full material for every panel. |
| 2026-08-14 | Passage 1's all-V2 trial was a nine-pair sequence backed by a complete pre-V2 Show snapshot at its verified checkpoint. | `Docs/Passage1SetVersions.md` and `P01_V2_SEQUENCE_VERIFY_SUCCESS`; later external exports show orientation metadata has since diverged | Preserve the checkpoint and JSON files as versions, but read the current Show before judging or restoring; never infer current image-flip state from the historical marker. |
| 2026-08-14 | Passage 2 uses a forest-to-industrial three-act progression and a versioned source-art chain: lighter original, dense-dark revision and layered-light successor. | Three versioned READMEs; three dense-wet and three layered-light panel-audit montages | Compare versions without overwriting approved source art. Use selective depth lighting—dark foreground, lifted middle, lightest receding route—while preserving the verified 20% seam overlap; then curate and alpha-isolate unless production checks reveal a specific defect. Final pieces retain heavily loaded interlocking tops without a blue-sky slit. |
| 2026-08-14 | Movie Render Queue receives a generated per-Show selection wrapper rather than fixed cameras or render-only tracks in the authoritative Master. | `Plugins/InfinityStage/Docs/AuthoringReference.md`; clean build, 25/25 suite, saved PIE and idempotence test reported green | Use **Render Selected Range…**; keep artist tracks in the persistent Master or child Scenes, preserve nested Scene camera authority and treat the wrapper as replaceable. |
| 2026-08-14 | Editor working light is a separate preview policy while all performance contexts remain Master-driven. | `Plugins/InfinityStage/Docs/CelestialCycle.md`; clean build and 26/26 suite reported green | Manual Editing Light may persist with the level and protect authoring from night scrubs; PIE, transport, MRQ and packaged playback ignore it, so there is still one performance clock. |
| 2026-08-14 | Reusable Wing sequences use versioned JSON metadata with fresh imported row identities; replacing a Passage preserves target music, sky and handoff ownership. | `Plugins/InfinityStage/Docs/AuthoringReference.md`; UE 5.8 editor build and 27/27 suite reported green; two 48-row files exported under `Saved/InfinityStage/WingSequences` | Use **Actions > Wing Sequence Files** for portable arrangements. Treat `.infinitywings.json` as metadata with soft asset paths, not an Unreal asset bundle or current-state authority. |
| 2026-08-14 | Applying a saved Wing arrangement is distinct from replacing complete authored rows. | `Plugins/InfinityStage/Docs/AuthoringReference.md`; `InfinityStage.Editor.WingSequenceInterchange` | The normal restore path preserves the target's Passage/row names, count, timing, spacing and IDs and repeats/trims only the saved design pattern. Use advanced Complete Replace only to adopt the file's structural data. |
| 2026-08-14 | Imported wood-floor vendor roots remain immutable support content; production tuning starts from a project-owned material-instance duplicate. | `Saved/WoodFloorImportAudit.json`: 305 assets, 50 instances, no failures | Keep Vol.01/Vol.02 references intact, duplicate only selected instances under `/Game/Stage/Ground/Materials`, and compare a bounded thin-box proof before changing the show ground. |
| 2026-08-14 | Passage 2 physical grammar is independent L/R side masses plus a separate multi-member T ceiling; the approved style is matte Rousseau-like pigment with believable layered wet light and varied upper-foliage silhouettes. | User-approved side/top and upright/forked anchors in task `019ffdcf-550f-7c20-8347-ff33118ed418`; rejected portal and independent-cutout audits | Do not use the two bulk transparent drafts as production input. Consolidate the approved large anchors, test fewer high-resolution objects and validate component independence before scaling. |
| 2026-08-14 | Passage 2 production art is generated as individual full-resolution L/R/T sets, one set per approval gate; contact sheets are excluded from the reference stack. | User correction after the V3/V4 matrix attempts; `RousseauApprovedIndividualSequenceV5/chroma/set_01` through `set_20` now exist. | Preserve per-component variation and prevent homogenization. Use only the frozen 20-set sequence for the current correction/import; any future extensions return to per-set approval before conversion. |
| 2026-08-14 | Sanatorium-to-Chinoiserie LiDAR character belongs in surface treatment, not broken silhouette edges. | Rejected jagged/clipped L-wing attempts and the replacement intact yellow-curtain rectangle in task `019ffd01-11c0-7f00-87ed-09b74c3ab8c9` | Approve one mathematically intact architectural boundary, then regenerate the remaining L family before creating R/C or 3D derivatives. |
| 2026-08-14 | New Wing sources are authored in final image handedness before PBR/FBX conversion; image mirroring, mesh-facing yaw and route-side placement remain separate operations. | `Docs/WingGenerationConventions.md`; legacy Show inspection found Left-side image flipping while the current V2 trial separately verifies mesh-facing rotation | Check L/R as a pair at source-art stage, regenerate all maps after any correction and never rely on Unreal image-flip flags for newly generated pairs. Preserve legacy states until an artist-approved migration. |
| 2026-08-14 | Contributor-authored sequences travel as self-contained shot kits rather than direct edits to the production level or managed Master. | Completed guidance task `01a000ab-565a-7453-bcdd-01f85a1d0891`; current Show/Master authority in this tracker and the Unreal runbook | Standardize a shot folder, Level Instance/sublevel, child Level Sequence, `StageOrigin`, explicit bindings and complete dependency migration; integrate timing/order through the authoritative workflow only. |
| 2026-08-15 | All newly generated production Wing FBXs use one explicit V2 contract; the pipeline's 5 cm default is legacy only. | Updated `AGENTS.md`, `Docs/WingGenerationConventions.md` and `Tools/WingCutoutPipeline/README.md`; active Forest and Cloud tasks confirmed 60- and 22-asset 5 cm batches respectively. | Every producer must resolve handedness before maps, export at 10 cm with the Base/height/normal/preview set and clean-reimport every FBX. The import task rejects or quarantines non-compliant new outputs. |
| 2026-08-15 | Passage 2's 20-set design is distributed into its 23-cue target as contiguous 14 / 5 / 4 narrative buckets. | User instruction and active Forest task: Sets 01–12, 13–16 and 17–20. | Cycle only inside each bucket; never wrap the final urban section back to Set 01 merely to fill the Passage. |
| 2026-08-15 | Cue Desk workspace layout is a per-project editor preference, while row order remains Show data and whole-Passage phase derives from the live cue ordinal. | `Docs/InfinityStageAuthoringReference.md`; `InfinityStage.Mechanism.LivePassagePhaseFollowsCueOrder` passed in `Saved/Logs/InfinityStageAuthoringIntegrationTests.log`. | Resizing/collapsing the UI does not mutate the Show. Drag/drop reordering does change authored order and intentionally updates the travelling undulation without regenerating a preset. |
| 2026-08-15 | Guarded project-Python over the loopback Unreal MCP endpoint is the standard automation route for now. | `ExecuteProjectPythonFile`; `PUSS_REMOTE_HEALTHCHECK_SUCCESS`; P02/P03/P05 import/assign/verify markers. Epic Remote Python listened on `127.0.0.1:6766` but official discovery found zero nodes. | Use no-screen Saved-script execution with transport and domain markers; keep desktop input and multicast Remote Python as fallbacks until separately healthy. |
| 2026-08-15 | Multi-Passage Wing integration uses a single writer and Passage-by-Passage clean-state gates. | Aggregate fingerprint `16c12e4fddf4585b7bf5f51aa0414da5e8f07abe0a0a2e6a325f6fd97520a853`; 23/21/93 actor materialization read-back; zero dirty packages. | Producers may generate assets concurrently, but Show/level mutation runs sequentially: P02 → P03 → P05, with scoped import, backup, materialization, targeted saves and independent verification at each boundary. |
| 2026-08-15 | Passage 5's clean FBX repair supersedes the first Task Manager-staged V2 export. | User visual rejection; 22/22 `GeneratedWingsV2_Clean` factory re-imports have triangle-only topology, zero non-manifold/degenerate geometry; `P05_CLEAN_VERIFY_SUCCESS`. | Use only the clean folder for P05. Keep the bad export diagnostic-only, require topology audits for future cutouts, and treat `HeightRatio=0.0` as this user's scoped no-bump override rather than a project-wide V2 change. |
| 2026-08-15 | Passage 5 ceiling display size is an occurrence-level Show transform, not a destructive FBX rescale. | At the 11:09 verified checkpoint, all 93 saved Top occurrences read back at `(X=1.0, Y=0.2, Z=0.2)` with the six clean ceiling meshes; the idempotent reassert pass reported zero mesh/scale changes and zero dirty packages. | Preserve the 10 cm × variable-width × 10 m clean source FBXs. Set the absolute local scale once, keep X thickness at 1.0 and never multiply an already reduced occurrence by another 0.2. Reverify after the later content-root switch. |
| 2026-08-16 | Native plugin build/test and live authoring use separate transports. | Validated headless commands and pass/fail markers in `Docs/CodexUnrealMCPRunbook.md`; the route opens no map and saves no content. | Close the interactive Editor before `Build.sh` or `UnrealEditor-Cmd -NullRHI`; use the guarded loopback MCP project-Python route for Show, level or content reads/writes. |
| 2026-08-16 | Shadow Cat is camera-owned stage machinery, not a free-running world character. | `AInfinityStageCameraRig` / `UInfinityStageShadowCatComponent`; direct walk/idle clips; task module-0015 cleanup; live `SHADOW_CAT_READY`, `SHADOW_CAT_ORPHAN_CLEANUP` and `SHADOW_CAT_EDITOR_CLEANUP` markers. | Each Passage camera owns one adapter whose placement and play rate follow evaluated camera state. Map-open/End-PIE cleanup removes only unclaimed camera children. Do not add a second follower/controller clock, and do not accept the feature until vendor component warnings and shadow-only composition are clean. |
| 2026-08-16 | Time-varying Wing movement lives on the managed Master as channels that modulate authored per-cue mechanism values; it never becomes a second source of movement truth. | `MovieSceneInfinityPassageTrack.h`; 31/31 suite including a history-independence test for the integrated rate channel. | Key Wing Travel Scale, Cycle Rate Scale and Phase Bias per Passage. Per-cue mechanism data stays authoritative for shape and variation, so presets and the live ordinal phase pattern keep working. Do not add per-cue keyed movement without revisiting this boundary. A rate channel must be integrated, never sampled, or scrub and reverse will disagree with playback. |
| 2026-08-16 | The per-cue Left/Right/Top mechanism curves are phase-indexed shape curves, not timeline curves. | `InfinityStagePassageActor.cpp` phase evaluation; `Docs/InfinityStageAuthoringReference.md`. | Use them to shape one breath. Use the Master Wing channels for anything that must change across the music. Confusing the two was the reason time-varying movement looked like it already existed. |

## Progress and verification ledger

Use this compact ledger for material milestones. Do not append a row merely
because a scheduled reconciliation found no change.

| Date | Area | Material change | Verification/evidence | Remaining acceptance or next action |
| --- | --- | --- | --- | --- |
| 2026-08-20 | GO1 receiver moved to the Show Root | The `Go1 Remote Receiver` component was moved from `InfinityStageCameraRig_0` to `InfinityStageShowRoot_0`, `Target Camera Actor` left empty so it drives the live view target. One receiver now serves every camera, retiring the one-socket limit on multi-camera use. | Editor closed; level backed up to `Saved/Go1Move/Backup/` first; fresh-process read-back shows exactly one component hosted on `InfinityStageShowRoot` with all 26 settings preserved (`Saved/Logs/Go1Move_Verify.log`); **only** `L_InfinityStage_V1VerticalSlice.umap` was written; **37/37** tests pass (`Saved/Logs/Go1Move_Tests.log`, exit 0) with `Show Root found` logged at runtime. | Author a Passage/Scene Camera Owner so the dog has control (default `Timeline` releases it), then human acceptance with the dog. |
| 2026-08-20 | GO1 receiver honours Show camera ownership | `UGo1RemoteReceiverComponent` consults `AInfinityStageShowRoot::GetCurrentCameraOwner()` and maps Timeline/DogGazeOnly/DogFreeLook to released/Absolute/Velocity; drives the player's current view target so one receiver follows camera cuts; re-centres on handback and cuts. `Go1Input` now depends one-way on `InfinityStage`. | Clean UE 5.8 build; `nm` confirms new symbols in the **base** dylib with the editor closed and no numbered side-libraries; **37/37** automation tests, exit code 0, zero `Result={Fail}` (`Saved/Logs/Go1OwnershipIntegration.log`); `SavedFixturePIE` logged `Show Root found` and `Camera owner -> Timeline (input released)`. No content opened or saved. | Author Camera Owner on a Passage/Scene (default `Timeline` releases the dog); move the receiver onto the Show Root; then human acceptance with the dog. |
| 2026-08-18 | GO1 remote telemetry to UE camera | Live performer control of the Passage 1 camera from the dog's handheld remote: bridge on the dog's internal Pi, `Go1Input` UE plugin, absolute/velocity modes, dog-mode mirroring, fail-safe and editor-mode operation. | 1489 packets / 30 s with zero gaps, packet age 3-10 ms, axes to +/-1.00, buttons decoded; robot publish rate measured at exactly 50 Hz; camera control confirmed live in PIE. `Docs/Go1TelemetryProgress.md`. | Confirm dog-mode integers with the dog standing; investigate ~22 fps; test the wireless path; tune feel. |
| 2026-08-11 | Infinity Stage V1/V2 foundation | Six-Passage vertical slice, managed Master, transport and deterministic music-analysis foundation delivered. | `Docs/InfinityStageOvernightReport.md`; final reported 9/9 suite twice. | Human visual/audio acceptance and production authoring expansion. |
| 2026-08-13 | Scene camera handoff | Ten boundary cameras added across five Scenes, idempotent on rerun. | Building Infinity Stage task; 18-test suite and saved-map rerun reported green. | Visual acceptance in normal editor/PIE. |
| 2026-08-13 | Celestial temporality | Master-driven sun, moon, stars and Passage Temporality UI implemented. | Celestial and Cue Desk tests reported green; `CelestialCycle.md`. | Apply the prepared environment upgrade to the saved map, restart and visually verify. |
| 2026-08-14 | Project memory | Task tracker expanded into progress, operations and handover memory. | This document and the recurring heartbeat automation, now reduced from 30 minutes to three hours. | Keep entries evidence-based and promote only durable learnings. |
| 2026-08-14 | Connectivity recovery | Five PussStage tasks in `systemError` were sent scope-preserving resume prompts and all accepted new in-progress turns. | Immediate Codex task snapshots showed `active` / `inProgress` for Building Infinity Stage, Wing Gen, Forest Wing Gen, Generating Cloud Wings, and Review and import usable assets. | Reconcile each task's next outcome; do not infer completion from the successful restart alone. |
| 2026-08-15 | Production Wing FBX standardization | The V2 contract was promoted project-wide. P02's 60 panels retain full Base/height/normal evidence; P05's 22 panels were later clean-rebuilt at 10 cm under an explicit user exception that disabled bump and set `HeightRatio=0.0`. | Canonical docs; P02 60/60 factory-clean validation; P05 clean pipeline/re-import reports and Unreal read-back. | Keep the general V2 derived-map gate for future Wings; do not generalize P05's scoped no-bump override. |
| 2026-08-15 | Infinity Stage authoring integration 0.5.0 | Persistent Cue Desk splitters/timeline, nested/flat cue views, multi-row reorder, marker snapping/anchors, live ordinal phase, segment rehearsal and initial PIE camera ownership were integrated. Later saved content now includes `LookAheadDistanceCm` in the production Master. | `Plugins/InfinityStage/InfinityStage.uplugin`; `Docs/InfinityStageAuthoringReference.md`; UE 5.8 build and 28/28 suite passed; `Saved/Logs/InfinityStageAuthoringIntegrationTests.log` ends with exit code 0. Current Master/autosave strings prove the new field is serialized, but no later Unreal verifier exists. | Confirm the loaded plugin and read back all expected Master channels/bindings/keys before deciding whether another rebuild is needed; then complete viewport/PIE/MRQ human acceptance. |
| 2026-08-15 | AnimX walking-cat integration | The imported AnimX cat is now wrapped by one camera-owned `BP_InfinityStageShadowCat` adapter per Passage rig. It uses direct walk/idle clips, camera-speed-derived play rate, parent-rig placement/render controls and scoped orphan cleanup on map-open/End PIE. | Completed cat-task outcomes through module 0015; live 16 August PIE repeatedly reports six registered `SHADOW_CAT_READY` adapters and cleanup markers with six claimed cats. The vertical-slice level was saved at 16:13 BST. | Read back all six saved rig values. Fix current `SpeedMultiplier` empty-array and `HeightFixer Sphere` warnings, then verify stop/accelerate/reverse/seek, floor contact, shadow-only framing and MRQ. |
| 2026-08-14 | Passage 1 wings and phased movement | The Rococo/Pillar reassignment was materialized/saved and later preserved in the pre-V2 snapshot; 2/3/4-phase Breathe presets were implemented. | `P01_REASSIGN_SUCCESS` and `P01_VERIFY_SUCCESS` in `Docs/CodexUnrealMCPRunbook.md`; UE build and 24-test result reported. | Current side meshes are the later all-V2 trial. Restart for the phase menu and apply a Phased Breathe preset only if desired. |
| 2026-08-14 | Passage camera and reveal | Nine Master-owned camera channels plus camera-led Wing reveal delivered. | `Plugins/InfinityStage/Docs/AuthoringReference.md`; build, 24/24 suite and saved-PIE result reported. | Restart, rebuild managed Master once and perform visual acceptance. |
| 2026-08-14 | Stage Opening V2 relief test | SaltFormation delivered as a portable 10 cm FBX with height/normal workflow. | Clean FBX re-import validation; `DerivedAssets/GeneratedWingsV2/SaltFormation_01_L_v2/UE5_Material_Setup.md`. | Unreal proof is complete; use production lighting to accept/reject family-wide relief treatment. |
| 2026-08-14 | SaltFormation Unreal proof | Relief surface/edge materials, three textures and mesh assignments were built, saved and independently read back. | Assets under `Content/Wings/StageOpeningV2/`; verifier confirmed texture settings, four samples, one Bump Offset and Surface/Surface/Edge slots. | Complete stage-light visual acceptance; unused FBX placeholder instances may be cleaned later. |
| 2026-08-14 | Stage Opening V2 production batch | Fourteen 10 m × 10 cm scenic panels were batch-built and imported as 72 scoped Unreal assets without changing the Show Asset or level. | `DerivedAssets/StageOpeningV2Batch/unreal_batch.json`; independent Unreal read-back verified texture settings, instance parents/parameters, slot assignments and mesh dimensions. | The reversible Passage 1 trial is verified; obtain visual acceptance under production lighting. |
| 2026-08-14 | Passage 1 all-V2 set trial | Nine V2 L/R pairings now repeat over 48 rows, using all 15 meshes; all Tops and non-mesh settings were preserved, and a complete pre-V2 Show snapshot was created. | `Docs/Passage1SetVersions.md`; `P01_V2_SEQUENCE_VERIFY_SUCCESS` confirms rows, orientations, 144 materialized panels, targeted saves and backup read-back. | Human visual acceptance under production lighting; restore the saved pre-V2 Show version if rejected. |
| 2026-08-14 | Passage 2 Rousseau source packs | The original lighter and dense-dark packs were preserved; the layered-light successor was completed with three matrices, 36 scenes, 108 overlapping L/R/T panels and three audits. | Three versioned READMEs; local read-back found 36 Left, 36 Right and 36 Top panels, zero empty files and 108/108 recognized PNGs; three 1440×480 audits were produced and the task reported all integrity checks passed. | Opaque source art remains valid. Consolidate the later approved component/style anchors before producing the replacement transparent pack. |
| 2026-08-14 | Passage 2 transparent trials | A 108-panel U-portal RGBA pack and a 108-panel independent-component RGBA draft were created and audited, then superseded: the first failed movement grammar and the second drifted stylistically. | `RousseauTransparentCutoutsFinal/README.md`; `RousseauIndependentCutoutsFinal/audit/`; local checks found 108/108 RGBA panels in each draft. | Do not use either batch. The replacement production path is now the approved individual V5 sequence; alpha-isolate only after that sequence is frozen. |
| 2026-08-14 | Selected-range rendering | Cue Desk now builds a replaceable render wrapper and one stable MRQ job for a selected Passage or continuous cue span without modifying fixed camera structure in the Master. | `AuthoringReference.md`; clean UE 5.8 build, 25/25 suite, new idempotence/range test and saved PIE reported green. | Restart; verify one Passage and multi-cue local render, including nested Scene cameras and output settings. |
| 2026-08-14 | Editor working light | Manual Editor Lighting with presets, exact Celestial Rig controls and explicit Follow Master mode was added without changing performance-time ownership. | `CelestialCycle.md`; clean UE 5.8 build and 26/26 suite reported green. | Restart, visually compare manual editing light with Follow Master and save the level only if the preview choice should persist. |
| 2026-08-14 | Wing Sequence interchange | Selected rows or complete Passages can be exported to versioned `.infinitywings.json`, reinserted, or used to replace a target Passage while preserving target identity, music, temporality and handoffs. | `AuthoringReference.md`; successful UE 5.8 editor build; 27/27 suite; two 48-row schema-v1 files exported and parsed successfully. | Export is artist-proven. Test import/replace/Undo on disposable content, require `INFINITY_STAGE_WING_SEQUENCE_IMPORT_OK`, then read back before targeted save. |
| 2026-08-14 | Passage materialization button | A void Call-in-Editor wrapper exposes **Materialize Passage** in Details while retaining the Boolean implementation for code and tests. | Clean editor build; 27/27 suite including reflection and saved PIE; source marker `INFINITY_STAGE_MATERIALIZE_OK`. | Restart the open Editor, confirm the button beside Clear Materialized Passage and use it for any temporary Show preview without saving unintended bindings. |
| 2026-08-14 | Music-fit-safe Wing arrangement restore | Added non-destructive **Apply Saved Arrangement**, corrected music-derived resizing to target the selected Passage and repeat its complete current design order, and made PASS headings directly renameable without renaming Wing rows. | UE 5.8 editor build; 27/27 suite including expanded interchange and saved vertical-slice PIE; `Saved/Logs/InfinityStageArrangementImportTests.log` has zero HTTP-403/assert/fatal/crash/test-failure signatures. | Restart the Editor. For a restore, select PASS, reset count from music in Fit, then apply the saved arrangement and visually inspect before targeted save. |
| 2026-08-14 | Wood-floor material library | Two 4K UE 5.0 material/texture packs were selectively imported and upgraded; demo/TrueSky content was excluded and three source ZIPs were deleted as requested. | `Saved/WoodFloorImportAudit.json`: 155 + 150 assets, 25 + 25 real material instances, valid parents and no failures. | Duplicate one chosen instance to project-owned content, test scale/lighting on a thin box, compare with the Landscape experiment and monitor the remaining disk space. |
| 2026-08-14 | Wing source handedness and Chinoiserie package | The canonical L/R rule was applied before conversion to three non-mirrored Chinoiserie pairs—six 10 m × 10 cm FBX/Blender/PBR assets. | `Docs/WingGenerationConventions.md`; `GeneratedWingsV2_Chinoiserie/wing_pipeline_report.json`; all six clean FBX reimports passed and the shared copy matched. | Import manually from `V2/Other` only when needed, using `DerivedAssets/V2_MANUAL_IMPORT_README.md`; no Unreal import or Show integration is yet claimed. |
| 2026-08-15 | Passage 3 sanatorium-to-Chinoiserie integration | Six asymmetric L/R/C sets became 90 scoped Unreal assets and 21 verified cue rows; `_C` is Top-only, flips are zero, and the actor materializes 21 pairs. | P03 import/assign/verify markers; `Saved/CodexWingIntegration/preflight_all_passages.json`; pre-change Show backup. | Human visual acceptance under production lighting; restore the P03 backup if rejected. |
| 2026-08-15 | Passage 2 individual V2 integration | Twenty L/R/T sets became 300 scoped Unreal assets and 23 verified rows using the approved 14/5/4 narrative allocation; the actor materializes 23 pairs. | 60/60 pipeline/FBX/texture validation; P02 import/assign/verify markers; pre-change Show backup. | Human visual acceptance under production lighting; restore the P02 backup if rejected. |
| 2026-08-15 | Passage 5 Cloud clean repair, ceiling sizing and later unverified root change | The glitchy first V2 FBXs were replaced in place by 22 clean, triangulated/manifold 10 cm FBXs; 23 legacy Left flips were removed and 93 rows were verified with Tops at `(1.0, 0.2, 0.2)`. Later, a 110-asset `/Game/Wings/Passage5_BirdToMountainV2` duplicate was imported from those same clean FBXs; current Show/level files, including later 17:16–17:34 saves, contain its 22 mesh paths. | Clean reports and `P05_CLEAN_ASSIGN_CEILING_SCALE_VERIFY_SUCCESS` prove the 11:09 checkpoint. Filesystem inventory/import metadata and current package strings prove the new assets and references exist, but only imply the current row/component routing; no post-change Unreal verifier or completed 279-component audit exists. | Read back the new saved state before acceptance: rows, absolute transforms, flips, bounds/source, materials, live components and dirty packages. Choose the canonical root afterward; do not delete either root meanwhile. |
| 2026-08-17 | Passage 3 clean rebuild re-validation (`P03`) | Clean source was already switched in and reimported into `/Game/Wings/Passage03_ShrineToForgetting/StaticMeshes` (18/18 mesh replacements), and actor/materialized read-back is correct for pair count and flip policy. Current read-back still reports one triangle-count mismatch and six role-mismatch rows. | `Saved/CodexWingIntegration/reimport_passage03_clean_meshes.json` (`status=ok`, `replaced=18`); `inspect_p03_actor_state.json` (`materialized_wing_pair_count=21`, `static_mesh_components=18`); `inspect_p03_rows.json` (`role_mismatches=6`); `verify_p03_clean_geometry.json` (`triangle_mismatches=1`, `image_flips_enabled=0`). | Resolve `P03_RepeatingSanatoriumArches_01_L` triangle mismatch, align role assignments, rerun read-back/verify and visual acceptance under production lighting. Do not mark complete until that final marker is present and rollback remains valid. |
| 2026-08-16 | Wing movement keyframing and guided route editing (`0.6.0-wing-modulation`) | Three native Wing channels—Travel Scale, Cycle Rate Scale and Phase Bias—were added to the managed Passage section beside the ten camera channels, multiplying each cue's authored mechanism values over Master time. Cycle Rate is integrated on a fixed grid anchored at Passage start. Passage Actor Details added **Edit Route / Extend to Compiled Length / Finish Route Edit** and an overwrite warning. A later source/docs build also adds bare-Space transport toggling through the ordinary constraint path. | The original `0.6.0` gate passed **31/31 tests** in `Saved/Logs/InfinityStageWingModulationTests.log`. Passage 2 later exercised route editing successfully. The Space change linked into `-0002` modules after that suite; the open Editor still had the unnumbered modules loaded, so no live or post-change test claim is made for it. | Restart into `-0002`, rerun the suite and verify Space in editor preview/PIE/text fields/external-unpausable Scenes. Read back Master Wing channels and the saved Passage 2 route before acceptance. Interchange export of Wing channels is not implemented. |
| 2026-08-16 | Passage 2 route and handoff authoring checkpoint | Passage 2's route edit reported `route_cm=13582.6`; all five Scene entry/exit cameras were matched to Passage endpoints; a smooth undulation was applied to all 23 Passage 2 Wing rows. | Live log markers `INFINITY_STAGE_ROUTE_EDIT_OK` and `INFINITY_STAGE_ROUTE_HANDOFF_MATCH ok=1`; the level save completed and validated at 16:13 BST. Production Show/Scene package mtimes are unchanged while current autosaves contain the later work. | Read back the saved spline/camera rigs. Inspect the autosaved Show and five Scenes, then intentionally save or discard them; do not treat autosaves as final persistence. |
| 2026-08-17 | Scene handover, transport and Cue Desk repairs (`0.6.1-scene-transport`) | **Root cause found and fixed:** `ClaimSegmentCamera` was only called from PIE init, `ScrubToMasterFrame` and `JumpToSegment`, and the transport component had `bCanEverTick=false`, so playing across a Passage→Scene boundary never handed the view over. The component now ticks in `TG_PostUpdateWork` and claims the new segment's camera on crossing; Wings remain tick-free. Scene camera bindings now resolve through `Player->GetBoundObjects()` so **Spawnable** cameras work, with the previous direct lookup kept as a pre-Begin-Play fallback. Added **View → Play Through Boundaries** (`PlayForwardThroughBoundaries()`), **Actions → Scene Camera Handoff → Check All Scenes (read-only)** staleness reporting, **View → Rehearsal Transport**, a **Top Follows Wing Movement** per-cue checkbox, `AInfinityStageShowGameMode` (no default pawn/HUD), a now-playing readout on the Cue Desk status rail, and a Cue Desk splitter min-size fix. | Clean UE 5.8 build; **32/32 tests passed**; `Saved/Logs/InfinityStage_Batch3b.log` ends `TEST COMPLETE. EXIT CODE: 0` with zero fatal/assert signatures. **No Show, level, Master or Scene content was opened or saved by any of this work.** | Restart and confirm `0.6.1-scene-transport`. Verify: continuous play across Passage 3 → Scene 3 hands the camera over; Check All Scenes reports the known stale focal length; Top checkbox on a multi-row selection; splitter drags. Set World Settings → GameMode Override to `InfinityStageShowGameMode` and save the level to stop the default pawn. |
| 2026-08-17 | Scene sound, expressive music analysis and Sequencer sync (`0.7.0-expressive-music`) | **Scene sound:** the Master builder now creates an audio section for Scene segments; `FInfinitySceneCueData::Music` already existed but the build loop only walked `Compiled.Passages`, so Scenes were silently skipped. **Scene length:** new per-Scene `bUseSequenceLength` takes the segment length from the Scene sequence's own playback range, converting tick resolutions; defaults off, falls back to `DurationFrames` on a missing/empty sequence. **Music analysis 0.3.0:** added continuous `featureCurves` (intensity, rhythmicDensity, brightness, low/mid/highBand, novelty) exported at 10 Hz, plus `expressiveSections` labelled quiet/building/intense/releasing/sustained from intensity level and trend. Schema bumped to 2; additive only, and the Unreal importer never checked the version. **Sequencer sync:** `FInfinityStageSequencerBridge` tracks open Sequencers weakly and **View → Sync Sequencer Playhead** (default off) pushes the Cue Desk playhead to any Sequencer whose *root* is this Show's Master, with a reentrancy guard. | Clean UE 5.8 build; **33/33 C++ tests** (`Saved/Logs/InfinityStage_SequencerSync.log`, exit 0, zero fatal/assert); **9/9 Python tests** including a synthetic quiet→building→intense→releasing arc that the analyzer labelled correctly. **No Show, level, Master or Scene content was opened or saved by this work.** | Restart and confirm `0.7.0-expressive-music`. **Scene audio and any Use Sequence Length change need Actions → Rebuild Managed Master Sequence to take effect** (timing/managed-track change). Re-run the analyzer on real Passage audio — no source WAVs remain in the tree, so validation used a synthetic arc. Sequencer sync and Scene-scoped Cue Desk preview are still unverified in a live editor. |
| 2026-08-17 | Music-to-movement bridge and rail picker (`0.8.0-music-to-movement`) | Closed the gap between analysis and mechanism. `UInfinityStageMusicMapAsset` gained `FeatureCurves` and `ExpressiveSections`; the analysis importer reads schema-2 `featureCurves`/`expressiveSections` (optional, so older maps still import). **Curve Actions → Apply Music Analysis Curve** samples an envelope at the Passage's music position — honouring rail source-in and Passage offset — maps unit values onto a channel-appropriate range (0.5–1.5 for Travel/Rate/Speed, ±0.25 cycles for Phase Bias), and writes Ramer–Douglas–Peucker-decimated keys capped at 96 so the result stays hand-editable; tolerance is relaxed rather than keys truncated. Channels with no meaningful unit mapping are refused. A **rail picker** property customization replaces the raw `PrimaryRailGuid`/`SecondaryRailGuid` fields for both Passage and Scene bindings, lists rails by label, flags a dangling GUID as *Missing rail*, and can create a rail from a Content Browser Sound selection. | Clean UE 5.8 build; **34/34 tests** (`Saved/Logs/InfinityStage_CurveBridge.log`, exit 0, zero fatal/assert), including a new curve sampling/clamping test. **No Show, level, Master or Scene content was opened or saved.** | Restart and confirm `0.8.0-music-to-movement`. Re-run the analyzer (0.3.0) on real Passage audio and re-import so `FeatureCurves` exist — existing maps predate them. Then: select a Passage, pick **Wing Travel Scale** in the timeline channel selector, and apply the `intensity` curve. Verify key count, shape and that wings visibly respond. Camera piloting remains the last outstanding queue item. |
| 2026-08-18 | Camera ownership and PIE start position (`0.9.0-camera-ownership`) | **Go1 assessment:** `Docs/Go1TelemetryProgress.md` records one hard constraint — one socket, one owner on UDP 9876 — so the receiver cannot be duplicated onto every Passage and Scene camera; its own open item 5 already prescribed a single receiver on a persistent actor. Implemented the Show-side half: `EInfinityCameraOwner {Timeline, Dog, DogGazeOnly}` authored per Passage and per Scene, resolved by `AInfinityStageShowRoot::GetCameraOwnerAtFrame()` with a **transient** live override (`bOverrideCameraOwner`) so a performance decision never rewrites the score, and **View → Live Camera Owner** in the Cue Desk. InfinityStage deliberately does **not** depend on Go1Input: external input plugins read the ownership query instead of carrying per-actor enable flags. Also **View → PIE Starts At Playhead** (default on), implemented entirely editor-side via `FEditorDelegates::PostPIEStarted` + `ScrubToMasterFrame`, guarded to fire only when the Cue Desk Show matches the PIE Show Root. | Clean UE 5.8 build; **35/35 tests** (`Saved/Logs/InfinityStage_Phase1.log`, exit 0, zero fatal/assert), including a new ownership test covering per-segment resolution, override precedence, Show immutability under override, and out-of-range fallback. Symbol presence in the base dylib verified with `nm` before trusting the run. **No Show, level, Master or Scene content was opened or saved.** | Restart and confirm `0.9.0-camera-ownership`. Set Camera Owner on a Passage and a Scene, enter PIE from a selected row, and check the handover. **Go1 side still to do:** move the receiver onto the Show Root and make `UGo1RemoteReceiverComponent` consult `GetCameraOwnerAtFrame` instead of its own enable flag. Remaining plan phases 3–6 in `Docs/InfinityStageStagecraftPlan.md`. |
| 2026-08-18 | Cue-anchored stage content foundation (`0.10.0-stage-content`) | Phase 3 of `Docs/InfinityStageStagecraftPlan.md`. `FInfinityCueAttachment` (stable `AttachmentGuid`, kind, soft actor class/mesh, anchor, relative transform, trigger distance) on the Wing Pair cue, plus `AInfinityStagePassageActor::GetAttachmentWorldTransform()` resolving station or panel anchors — reading the **live** instance transform so panel-anchored content follows inward travel, and falling back to the station when a panel is absent. New **Stage** Inspector tab beside Music/Fit/Route. Soft references throughout so a missing asset warns and skips rather than blocking a materialize. | Clean UE 5.8 build; **36/36 tests** (`Saved/Logs/InfinityStage_Phase3.log`, exit 0, zero fatal/assert). The new test re-spaces a Passage — exactly what a music change does — and asserts the attachment moves with its wing while preserving its relative offset, plus clean failure on an unknown attachment. Symbol verified in the base dylib before the run. **No Show, level, Master or Scene content was opened or saved.** | Restart, confirm `0.10.0-stage-content`, add an attachment on a Wing Pair via the Stage tab. **Not yet built:** actual spawning/placement of attachment actors, the viewport drag-to-edit write-back, the stage-spot generator (Phase 4), trigger firing (Phase 5) and mechanism SFX (Phase 6) — this delivers the anchoring model those three consume. |
| 2026-08-18 | Stage lighting and attachment placement (`0.11.0-stage-lighting`) | Phase 4. Added `EInfinityAttachmentAnchor::PairCentre` tracking the live midpoint between panels. `AInfinityStagePassageActor::MaterializeAttachments()` spawns attachment actors into `ManagedAttachmentActors`, attached to the Passage and destroyed on clear or re-materialize, so materialization has one ownership story and a re-fit cannot orphan lights or props; a mesh-only attachment spawns an `AStaticMeshActor` with no Blueprint required, and a broken reference logs `INFINITY_STAGE_ATTACHMENT_SKIPPED` and is skipped rather than failing the materialize. **Cue Desk Actions gained a Materialize section** (Selected Passage / All Passages) — previously reachable only from the Actor Details panel — plus **Add Stage Spots to Selection**, generating panel-anchored top-left/right spots. Camera Rig gained an optional **Follow Light** behind the shadow figure, off by default. | Clean UE 5.8 build; **36/36 tests** (`Saved/Logs/InfinityStage_Phase4.log`, exit 0, zero fatal/assert), extended to assert pair-centre midpoint tracking, actor spawning, re-materialize idempotence, disabled-attachment removal and clear-up. **No Show, level, Master or Scene content was opened or saved.** | Restart, confirm `0.11.0-stage-lighting`. Select Wing Pairs → Actions → Add Stage Spots → Materialize Selected Passage. **Not yet built:** viewport drag-to-edit write-back for attachments (currently offsets are typed in the Stage tab), trigger firing (Phase 5), mechanism SFX (Phase 6), and Wing Sequence interchange does not yet carry attachments — that needs a schema bump, and the importer rejects unknown schemas outright. |
| 2026-08-18 | Direct manipulation of attachments (`0.11.1-stage-lighting`) | Moving a spawned attachment actor in the viewport now writes its transform back to the cue as a **relative** offset, via `GEditor->OnActorsMoved()` in the editor module. Chose direct manipulation over a temporary edit-proxy mode (the `AInfinityStageWingEditProxy` pattern) because the attachment actor is already present, selectable and attached to its Passage — so moving it is the natural gesture and needs no mode. Split the resolver into `GetAttachmentAnchorWorldTransform()` (anchor without offset) plus `GetAttachmentWorldTransform()`, and added `FindAttachmentByActor()` so a moved actor can be traced back to its cue. | Clean UE 5.8 build; **36/36 tests** (`Saved/Logs/InfinityStage_DragEdit.log`, exit 0, zero fatal/assert). **No Show, level, Master or Scene content was opened or saved.** | Restart, confirm `0.11.1-stage-lighting`, generate spots, materialize, then drag one and re-materialize to confirm it returns to the dragged position rather than the default. **Note:** `FindAttachmentByActor` recovers identity from spawn order; if attachment identity ever needs to survive an out-of-band level edit, store the GUID on the spawned actor as a tag instead. Phases 5 (triggers) and 6 (mechanism SFX) remain. |
| 2026-08-18 | Mechanism sound model and attachment identity (`0.12.0-mechanism-sound`) | Replaced attachment identity-by-spawn-order with a GUID **actor tag** (`InfinityStage.Attachment.<cue>|<attachment>`), closing the risk that a duplicated or reordered actor could write another attachment's offset. Phase 6 data model: `FInfinityMechanismSoundSet` per Passage (sound bucket, policy, gain, audible radius, movement threshold) plus per-cue `bMuteMechanismSound`, and `GetMechanismSoundIndexForCue()` with RoundRobin / StableRandom / ByCycleRate policies. StableRandom seeds from the cue GUID — never a call counter or world time — so selection survives scrub, reverse, reload and re-materialize. | Clean UE 5.8 build; **37/37 tests** (`Saved/Logs/InfinityStage_Phase6.log`, exit 0, zero fatal/assert). New test covers disabled/empty sets, round-robin ordering, stable-random repeatability across queries, and per-cue muting leaving neighbours voiced. **No Show, level, Master or Scene content was opened or saved.** | Restart, confirm `0.12.0-mechanism-sound`. **Playback is not wired yet:** selection and timing derivation exist, but nothing voices them. The intended route is the transport tick querying wings inside `AudibleRadiusCm` and voicing movement onsets through a small pooled set of audio components — deliberately not per-wing components, which would break the tick-free Wing invariant. Phase 5 (animation triggers) remains, as does attachment support in Wing Sequence interchange. |
| 2026-08-18 | Scene look modes and segment stepping (`0.12.1-scene-look`) | Renamed `EInfinityCameraOwner::Dog` to `DogFreeLook` before anything consumed it, and documented the mapping onto the receiver's existing rotation modes: **DogFreeLook → Velocity** (stick is a turn rate, view can circle) and **DogGazeOnly → Absolute** (stick is an angle within range, centring returns to centre). Both already exist in `EGo1RotationMode`; no new rotation code was needed. Added an **advisory** to `CheckSceneHandoffs`: a Scene with dog look enabled whose cut camera also has keyed rotation is reported as a likely conflict, deliberately not blocked, since authored rotation may be intended as a base to look around from. **Left/Right arrow keys** now step whole segments (Passage↔Scene) with the Cue Desk focused, routed through the same transport as the segment buttons. | Clean UE 5.8 build; **37/37 tests** (`Saved/Logs/InfinityStage_SceneLook.log`, exit 0, zero fatal/assert). **No Show, level, Master or Scene content was opened or saved.** | Restart, confirm `0.12.1-scene-look`. **Still to wire:** the receiver reading `GetCameraOwnerAtFrame` and setting its rotation mode from it, so look policy comes from the score rather than a component setting. Note arrow keys and Space require Cue Desk focus, not the PIE viewport. |
| 2026-08-20 | Attachment mobility fix; Go1 ownership connected end to end (`0.12.2-attachment-mobility`) | The other session wired `UGo1RemoteReceiverComponent` to `AInfinityStageShowRoot::GetCurrentCameraOwner()`, mapping `DogGazeOnly`→Absolute and `DogFreeLook`→Velocity, so look policy now comes from the Show rather than a per-actor flag. Building both plugins together surfaced a **real bug in the attachment spawner**: spawned actors default to `EComponentMobility::Static`, which cannot attach to the Passage Actor's movable root, so `AttachToActor` silently aborted and attachments were left loose in the world — unparented, therefore not following the Passage and invisible to the drag-to-edit write-back, which finds its owner via `GetAttachParentActor()`. Spawned roots are now set Movable before attaching. | Clean combined UE 5.8 build; **37/37 tests** (`Saved/Logs/InfinityStage_Mobility.log`, exit 0, zero fatal/assert). The fix is evidenced by the log itself: `cannot attach` warnings went **4 → 0** between `InfinityStage_Combined.log` and `InfinityStage_Mobility.log`. **No Show, level, Master or Scene content was opened or saved.** | **Testing gap worth closing:** the attachment tests exercise `GetAttachmentWorldTransform` (pure maths) and passed green throughout while the actual spawning was broken. A test that materializes and asserts each spawned attachment's `GetAttachParentActor()` is the Passage Actor would have caught this. Add it before relying on attachments in anger. |
| 2026-08-20 | Dog-mode mirroring removed; Show owns look policy (`0.12.3-show-owns-look`) | Hardware measurement over the wired link settled telemetry open item 1, but not as framed. Standing/Select: `mode = 0` on 501/501 packets. Move mode (START): `mode = 0` on 401/401. The expected turn value `2` **never appeared in any state**; an earlier noisy 0/1 mix was a transitional settling condition, not a property of standing. `HighState.mode` therefore cannot distinguish the two states, so `bFollowDogMode`, `DogModeForGaze` and `DogModeForTurn` were **deleted** rather than left as dead knobs, along with their selection branch. `DogMode` parsing and the debug readout were kept — the field arrives and is diagnostically useful. Gaze versus free look is now decided solely by `EInfinityCameraOwner` on the Passage or Scene. | Clean combined UE 5.8 build; **37/37 tests** (`Saved/Logs/InfinityStage_DogModeCleanup.log`, exit 0, zero fatal/assert). Zero residual references to the removed fields. **No Show, level, Master or Scene content was opened or saved.** | Nothing outstanding for look policy. **If dog physical state is ever wanted as a signal**, it needs a different `HighState` member forwarded by the bridge — `mode` is flat across these states. Note the measurement was wired only; wireless remains untested (telemetry open item 3), with the wired baseline at 501/501 packets, 0 gaps. |
| 2026-08-14 | External shot handoff | A contributor workflow now packages set dressing, local lights and animation as a Level Instance/sublevel plus child Level Sequence with an agreed pivot and explicit ownership. | `Docs/KlaraDioramaLevelSetup.md` and completed task `01a000ab-565a-7453-bcdd-01f85a1d0891`; no Unreal authoring mutation was claimed. | Give Klara the scale/front reference, then verify migrated map/sequence dependencies, bindings, identity placement, global-light ownership and authoritative timing during integration. |

## New-contributor quick start

1. Read `AGENTS.md`, this tracker, then `Docs/CodexUnrealMCPRunbook.md` before
   any open-Editor automation or Infinity Stage authoring change.
2. Open the live/outstanding section and choose the highest-priority item whose
   dependency is actually available.
3. Confirm whether Unreal is open, whether PIE is stopped, which map is loaded,
   and what packages were already dirty.
4. Inspect the authoritative asset or source before proposing a mutation.
5. Follow the relevant tool playbook above and preserve exact paths, logs,
   markers, test results and read-back evidence.
6. Update both the task status and any genuinely reusable learning discovered.
   If a lesson is Unreal-automation-specific and newly proven, also update the
   canonical runbook.

## Handover rules

When a task changes the project materially:

1. Update its handover state here: `Live`, `Needs integration/acceptance`, `Asset production`, `Research/guidance`, `Partial`, `Blocked`, or `Completed`.
2. Record the concrete deliverable and the exact remaining action; do not use app `idle`/`notLoaded` as a completion signal.
3. Link the primary file, map, package or report that proves the handoff.
4. Record verification: build target, focused test count, visual/audio check, or known unverified area.
5. Move only genuinely finished work into the completed table.
6. Capture the proven workflow when a task establishes a new way to use a
   project tool. Record exact paths, preconditions, success markers and fallback.
7. Add a learning/guardrail when a failure reveals a repeatable hazard. State
   both the mistake and the prevention; do not merely archive the error text.
8. Keep decisions separate from task status and record their consequences for
   future implementation.

## Scope note

The tasks **Translate text to English** (`019f93a0-e343-7fb1-864c-f7412d66881c`)
and **Scan cloud drive for deletions** (`01a0004f-c753-78d1-bfde-626b1d59d003`)
were launched from the PussStage working directory but concern private mortgage
documents or unrelated archive/Drive cleanup. Both are deliberately excluded
from project status.

This workspace root is not itself a Git repository. The tracker therefore uses
live Codex task metadata, task outcome summaries, file presence/timestamps and
the existing Infinity Stage reports as its evidence base. The nested
`Plugins/MCPBlueprintsGenerator` directory is a separate Git repository.
