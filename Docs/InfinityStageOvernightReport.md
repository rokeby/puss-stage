# Infinity Stage Director — Overnight Build Report

**Build date:** 11 August 2026  
**Target:** live UE 5.8 PIE/Sequencer narrative visuals  
**Plugin:** `Plugins/InfinityStage` (foundation report originally built at `0.1.0`; current authoring integration is `0.5.0`)  
**Status:** V1 vertical slice and V2 music-analysis foundation complete; production authoring expansion remains

## Outcome

A new side-by-side Infinity Stage plugin now compiles and runs without changing the old Stage Wing Director. It provides a finite, music-led Cue Score, fixed editor-visible stage materialization, one Master Sequence authority, live operator transport, Scene camera/audio handoff rules, and a saved six-Passage development show made from the supplied music.

V2 now also has a deterministic offline music-analysis provider and six versioned Unreal Music Map assets. Analysis output is explicitly review-only: reimport tests prove it does not add, delete, reorder, or retime Cue Score rows.

This is a coherent production foundation, not the whole specification. It does not yet include the full automation-lane/tween editor, author-ready spline visualizer, complete attachment-anchor workflow, production mechanism-audio pool, venue control adapters, or full 45-minute/3,000-wing authored show.

> **15 August authoring-integration addendum:** the practical day-to-day controls have advanced beyond this original overnight snapshot. The Cue Desk now has persistent nested/flat and three-column layouts, a collapsible horizontal Music Timeline, exact cue-to-Master playhead following, camera/overview scrub modes, native Passage camera channels and music-overlaid speed editing, camera-led Fan Reveal, live ordinal Passage waves, Scene subsequence navigation, previous/next PIE segment rehearsal, lossless Wing-sequence interchange and a managed Movie Render Queue wrapper. See `Docs/InfinityStageAuthoringReference.md` for the current workflow.

## Gate status

| Gate | Status | Evidence |
| --- | --- | --- |
| A — baseline | PASS | UE 5.8 Editor target builds; old plugin remains present and was not refactored. |
| B — V1 core | PASS | Runtime, Editor and Tests modules compile; assets save/reload; fixed materialization and managed Sequencer tracks pass. |
| C — live PIE slice | PASS (automated) | Saved Passage → external-sound Scene → Passage fixture reopens and passes exact transport/camera ownership checks in PIE. A human visual/audio stage audition is still required. |
| D1 — synthetic analysis | PASS | Five deterministic golden tests cover known tempo, structure, silence, fingerprints and repeatability. |
| D2 — supplied music | PASS | All six stable WAVs fingerprint, analyze, visualize and import into versioned review assets; repeat output matches. |

## V1 delivered

### Data and compilation

- `UInfinityStageShowAsset` is a Primary Data Asset containing one ordered mixed list of Wing Pair, Scene and Sequence cues.
- Cue, Wing Occurrence, Passage, Music Rail and transport segment identities use stable GUIDs.
- Time is compiled in the Show tick domain (24,000 ticks/s; 25 fps display in the fixture), not accumulated floating-point seconds.
- Explicit lead-in, pass, and tail anchors close each Passage camera-distance curve.
- The fit solver treats music duration, camera speed, wing spacing and entry/exit clearances as a coupled system and can reset a contiguous Passage's wing count from those values.
- Passage music remains Master-owned. World placement never starts a competing sound player.

### QLab-influenced Cue Desk

- The main virtualized Cue Score occupies 72% of the initial width and remains the dominant surface.
- The cue/inspector split is draggable; the whole Cue Desk is a dockable Unreal tab.
- Cue, Music, Fit and Route are mutually exclusive internal tabs, avoiding one extremely tall form.
- Add Cue and Actions are compact menus. Duplicate, move, rebuild and delete do not occupy a row of freestanding single-purpose buttons.
- Cue selection now resolves the selected Cue GUID back to its fixed world instances. By default the active Level viewport frames and outlines the selected Left/Right/Top panels; the Actions menu can disable Follow Selection or explicitly frame the current selection.
- Cue-detail edits are debounced, rematerialize only the selected Passage bay, and restore the instance highlight. The Cue asset therefore remains authoritative instead of allowing an edited raw ISM instance to drift from saved data.
- The persistent lower status rail reports compiled duration, average camera speed, route distance, wing count, Passage count and readiness.
- Music Setup exposes Source In/Out and fades, plus a compact six-track Analysis Review summary. Tempo and structural markers are visibly described as proposals.
- A console hook, `InfinityStage.OpenCueDesk`, supports repeatable QA launches and can preselect a Show through `-InfinityStageCueDeskShow=...`.

### Fixed world authoring

- `AInfinityStagePassageActor` owns an editable spline and persistent managed render components.
- Materialization is an explicit editor action. BeginPlay does not generate the fixed stage.
- Wings are visible in the saved map before PIE and remain visible in PIE.
- The development map uses six independent spatial bays, 800 m apart, so each main Scene can conceal the cut to another Passage. This avoids committing to an unsafe giant spiral before footprint and turn-radius measurements exist.
- Ground is deliberately ordinary authored level content, not plugin-generated geometry. Each bay/Scene can receive independent forest, concrete, wood or other ground meshes/materials and lighting.
- Manual lights and unique scenic objects remain ordinary level actors, preserving the real-stage authoring model.

### Sequencer, camera and operator transport

- One `AInfinityStageShowRoot` owns one root `ULevelSequencePlayer` and transport controller.
- Native managed Passage, Scene and Music tracks rebuild idempotently while preserving user tracks.
- The saved Master contains 6 Passage sections, 5 Scene subsections and 6 managed music sections; it does not create one subsection per wing.
- The camera and looping mechanisms evaluate absolute Sequence time. Seek/reverse does not depend on prior Tick history.
- Required transport supports forward/reverse segment navigation, exact jumps, pause/resume and rehearsal/performance policies through Blueprint/C++ APIs.
- Scene sections may declare external unpausable sound. Performance mode refuses unsafe hold/reverse/jump rather than drifting external sound; rehearsal mode can seek the visuals.
- The physical robot dog is outside the plugin. The camera rig includes a separate shadow-figure root for artist-authored Puss-the-cat/Boy figures behind the camera; production shadow-only rendering and animation remain an art/lighting acceptance task.

## Saved development content

- `Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset`
- `Content/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.uasset`
- five `LS_DevScene_XX` sequences
- `Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap`
- six imported Passage Sound Waves under `Content/InfinityStage/Audio/Passages/`
- six review assets under `Content/InfinityStage/MusicMaps/`

The fixture contains:

- 6 music-led Passages and 5 externally sounded Scene handoffs;
- 261 fixed Wing Pairs;
- 30 distinct source meshes in each Passage's repeating palette;
- 129 distinct wing mesh assets currently discoverable across the source content (there are not yet 180 different source meshes available to populate the assumed 30 × 6 without cross-Passage reuse);
- 180 managed render components (30 per Passage); and
- approximately 527.054 seconds of supplied Passage music plus five 15-second Scene placeholders.

This fixture proves the architecture. It is not presented as the final 45-minute Cue Score or final spatial layout.

## V2 music-analysis foundation

The local `InfinityStage Numpy Feature Provider 0.2.1` reads the verified Float32 WAVs without an online service. It produces:

- SHA-256 and MD5 source provenance;
- multiresolution waveform review bins;
- loudness, onset and spectral evidence;
- ranked tempo candidates with ambiguity retained;
- beat proposals;
- major-change proposals; and
- JSON plus SVG review artifacts.

Passage 6 correctly reports **no stable tempo** despite having many events; a zero-confidence BPM is no longer manufactured. Passages 2 and 5 explicitly retain high half/double-time ambiguity. Every proposal requires artist approval.

Outputs live under `Saved/InfinityStage/MusicAnalysis/`. A second analysis run produced semantically identical JSON for all six tracks (excluding the run timestamp) and byte-identical SVGs. The Unreal importer created `MM_P01_Analysis` through `MM_P06_Analysis`, preserved cue identity/count, and passed a second idempotent reimport.

## Verification results

### Final automated gates

- UE 5.8 `PussStageEditor Mac Development`: **Succeeded**.
- Exact repaired test `InfinityStage.Editor.CueDeskConstructs`: **Passed**.
- Full `InfinityStage` Automation suite: **9/9 passed twice in two clean command-line Editor sessions**.
- Both final runs ended with `TEST COMPLETE. EXIT CODE: 0`.
- Saved-map PIE exact transport evidence:
  - Passage 1 → Scene boundary: tick `2,312,065` exactly;
  - unsafe next jump in the external-unpausable Scene: rejected with time/selection unchanged;
  - rehearsal Scene → Passage 2: tick `2,672,065` exactly;
  - reverse returned to Scene boundary tick `2,312,065` exactly.
- 3,000-row compile test: `0.385 ms` and `0.386 ms` on the development M1 Max, with no Actor, component or per-row Tick created by compilation. This is a compiler result, not a production rendering benchmark.
- Music provider: **5/5 golden tests passed**.
- Six supplied-track outputs: deterministic semantic JSON and byte-identical SVG repeat.
- Final stale-process audit: no Unreal Editor, commandlet, Trace Server or Crash Report Client remained.

### Known nonfatal environment warnings

- The command-line Editor reports that its optional HTTP listener cannot bind port 8000 because another local service owns it. Infinity Stage does not depend on this listener and all tests pass.
- Null-RHI PIE logs a CoreAudio sample-rate query warning. This does not validate audible production output; the supplied Sound Waves and managed Audio sections still require a normal-device listening check.
- BlueprintAIExporter declares UE 5.6 compatibility in its descriptor while the project is UE 5.8. That pre-existing plugin is outside Infinity Stage.

## Crash, stall and “403” recovery ledger

### Master Sequence editor crash — fixed after first user open

- At 22:00:46 on 11 August 2026, opening `LS_InfinityStage_V1Master` asserted in
  `UE::Sequencer::FTrackModel::ForceUpdate` and then crashed on an invalid shared
  pointer.
- The preceding ensure identified the exact cause: no Sequencer track editor was
  registered for `UMovieSceneInfinityPassageTrack` (the managed Scene and Audio
  track types had the same missing editor contract).
- `InfinityStageEditor` now registers and unregisters a minimal managed-track
  editor covering all three generated track classes. The new exact automation
  test `InfinityStage.Editor.MasterSequenceOpens` opens and closes the saved
  Master successfully with exit code 0.
- This crash was triggered by opening the asset and was unrelated to concurrent
  source-file edits; no build or Unreal process was being run externally at the
  time.

### PIE Passage camera did not claim the viewport — fixed

- Music and Master time advanced, but the Passage camera did not become the PIE
  view target because the custom track called the deprecated UE camera-cut
  compatibility entry point, which is a no-op for the UE 5.8 Level Sequence
  player.
- Passage evaluation now claims the live Player Controller view target directly,
  and transport jumps deterministically claim/evaluate the destination Passage
  camera after sequence evaluation.
- The saved-map PIE test now verifies Passage 1 and Passage 2 camera ownership as
  well as the existing Passage → Scene → Passage frame boundaries; the exact test
  passes with exit code 0.

### Repeated materialization test-fixture crash — fixed

- Two early full-suite runs (`pid 94595` and `pid 94932`) asserted that a second `WorldSettings` could not be created.
- Both stacks ended in `FInfinityStagePersistentMaterializationTest`, which initialized an already initialized preview world.
- The duplicate initialization call was removed. Production materialization code was not the cause.
- The exact test and every later full suite passed.
- Crash evidence remains in the Unreal 5.8 Saved/Crashes folder under the two matching report directories.

### Startup-console fixture path — quarantined, bypassed

- The direct startup command that combined fixture creation and immediate Quit stalled three times before useful Automation control, leaving one stale commandlet.
- The exact stale process was closed and the build was rerun through a post-startup Automation bootstrap instead.
- The bootstrap created and saved all fixture assets successfully. Ordinary `InfinityStage` test discovery was then separated from mutation bootstrap names.

### Final GUI-only visual-capture launch — quarantined

- A clean full-RHI Editor launched directly for screenshot capture remained in early project/plugin startup without creating a visible window or advancing its log.
- It did not crash. Graceful termination was ignored, so only its exact Editor/Trace PIDs were force-closed.
- This does not invalidate the clean command-line Editor asset reopen/Slate construction/PIE results, but a human dock/resize visual inspection remains on the first daytime checklist.

### Cue Desk optional-pointer crash — fixed before handoff

- The first regression after adding the QA auto-open hook produced a `SIGSEGV` in `SInfinityStageCueDesk::Construct` because the optional raw Show pointer in Slate arguments had no default initializer.
- The pointer now initializes to `nullptr`.
- Recovery followed the required order: rebuild → exact failed test pass → full suite pass → clean reopen/full suite pass.
- Evidence is preserved in `PussStage-backup-2026.08.11-01.22.17.log`.

### 403 classification

No HTTP 403 occurred. Matches such as `01.12.55:403`, process ID `403`, or GUID fragments are timestamps/identifiers, not HTTP responses or Unreal exit codes. The port-8000 bind warning is also not a 403. No retry storm or authentication failure occurred.

### Development fixture assigned ceiling meshes to side slots — fixed in builder

- The original development fixture cycled through one alphabetically collected mesh array. It did not classify assets by role, so a mesh such as `SM_Ceiling_turquoise` could be assigned to a Left panel. This was fixture construction error, not primarily an artist-import error.
- The fixture builder now creates Left, Right, generic-side and Top palettes from asset naming evidence. Ceiling/overhead assets cannot enter side slots; obvious ground/prop assets are excluded from the automatic side palette.
- Right-side fixture panels receive the opposite inward-facing orientation. Optional Top panels are placed horizontally and conservatively downscaled to the 12 m development corridor rather than retaining an extreme source size.
- This changes future fixture generation only. The saved development Show/map must be regenerated deliberately after closing the interactive Editor; it was not overwritten while the artist had it open.

## Production limitations and next priorities

1. Restart Unreal so the newly compiled Cue-to-viewport selection bridge is loaded, then visually confirm single- and multi-cue framing/highlighting from the Cue Desk.
2. Listen to all six managed music handoffs with a normal audio device; approve Source In/Out and fade values.
3. Add the Wing Asset Audit/Correction Library: persistent per-mesh role, front axis, scale and pivot corrections plus a viewport edit proxy for direct gizmo editing of a cue without mutating raw instances.
4. Regenerate the development fixture with the role-aware palettes once any current map edits have been saved or intentionally discarded.
5. Replace the five 15-second placeholder Scene sequences with the authored Scene sequences and decide each external sound/control protocol.
6. Build the range-automation layer for timing/camera-speed and continuous mechanism-rate tweening, including integral phase continuity.
7. Add the normalized custom/serpentine/helix route modes, spline visualizer and physical clearance validator.
8. Add attachment anchors for manual lights/animated props and complete the shadow-figure actor/material proof under the production lighting path.
9. Replace the development component strategy with active/preload chunk budgets where production render diversity requires it; profile on the final live-performance workstation.
10. Expand from the 10-minute architecture fixture to the complete Cue Score only after Scene durations/music locks and venue footprint are known.

UE 5.8 does **not** need to be left running. Structural builds and Automation are more reliable with it closed; launch a fresh normal Editor for the visual/audio acceptance checklist.

## Changed-file boundary

All new implementation is confined to:

- `Plugins/InfinityStage/`;
- `Content/InfinityStage/`;
- `Tools/InfinityStage/`;
- `Saved/InfinityStage/MusicAnalysis/`; and
- the named `Docs/InfinityStage*` planning/report/manifest files.

The original Google Drive music and old Stage Wing Director plugin/assets were not edited in place.

## Post-build legacy plugin archive

At the user's request, the original plugin was moved intact from
`Plugins/StageWingDirector` to `ArchivedPlugins/StageWingDirector`. Its explicit
entry was removed from `PussStage.uproject`, so Unreal no longer discovers,
compiles, or loads its Runtime/Editor modules. Recovery instructions are in
`ArchivedPlugins/README.md`.

Because the old `/Game/Levels/StageTest` World Partition actors contain serialized
Stage Wing Director classes, the project startup and game-default maps now point
to `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`. The old map and
external actors were preserved unchanged.

The post-archive UE 5.8 build succeeded, the startup log mounted Infinity Stage
without mounting Stage Wing Director, and all 9 Infinity Stage tests—including
saved-map PIE—passed with exit code 0.
