# Infinity Stage Director

## Ground-up plugin specification for PussStage

**Status:** Draft for architectural review  
**Target:** Unreal Engine 5.8  
**Provisional plugin name:** Infinity Stage Director  
**Specification date:** 10 August 2026  
**Relationship to Stage Wing Director 0.15.0:** New, side-by-side plugin; reuse selected assets and ideas, but do not migrate the old authored show model

---

## 1. Executive decision

Infinity Stage Director should be built as a new plugin and a new data model, not as an in-place refactor of Stage Wing Director.

The central conceptual change is:

> The old system generated an effectively endless carousel of reusable wing designs moving toward a fixed camera. The new system authors a finite, ordered score of wing-pair occurrences placed along finite paths, while a camera rig advances through them in absolute show time.

The new plugin will therefore be:

- finite in authored order and route extent, while allowing each wing mechanism to loop deterministically;
- explicitly authored rather than randomly or cyclically generated;
- driven by one absolute show timeline shared by Sequencer and segment-level live operator control;
- music-led by default: each Passage's confirmed soundtrack In/Out range establishes its initial duration, while camera speed and Wing Pair spacing remain deliberate artist choices;
- presented through one unified chronological cue list containing Passage structure, Wing Pair rows, and Scene rows, rather than a separate Set/Pair design library;
- presented through a QLab-inspired, resizable **Cue Desk** in which the Cue Score is the only mandatory panel and menus/contextual inspectors replace most single-function buttons;
- spline-based rather than locked to a straight local axis;
- non-destructively adjustable across ranges through automation lanes;
- persistently materialized in the editor world before PIE, while remaining scalable through compiled data, chunk Actors, batching, and contribution-aware update tiers rather than one ticking Actor per wing pair; and
- integrated into one master sequence containing passage and scene subsequences with explicit camera handover and handback.

“Finite” applies to the score and route: the camera never wraps to recycle logical cues. It does **not** require distant wing pairs to stop moving. Their local in/out mechanisms may loop for as long as their Passage is active, with phase derived from absolute time so seeks, update-tier changes, and optional serialized streaming remain exact.

The canonical authoring data should be Unreal Primary Data Assets. A spreadsheet-like editor should sit on top of those assets. CSV and lossless JSON should be import/export formats, not the primary store.

The recommended physical organization is hybrid:

1. Give each inter-scene passage its own finite spline and spatial zone.
2. Use the intervening main scenes as natural cut points between zones.
3. Allow a passage spline to be straight, serpentine, helical, or custom when it needs to fit a long route into a smaller footprint.
4. Materialize every fixed Wing Pair into serialized editor-visible chunk content before PIE; use contribution-aware motion, shadow, audio, and optional serialized-streaming tiers at runtime without creating the stage on demand.
5. Place one persistent Show Root that owns the single Master player, camera authority, transport, and exclusive music router.
6. Treat ground as section-owned artist content: separate wood, concrete, forest, Landscape, spline-strip, or Level Instance Ground Zones may coexist in the same Show World.

This produces the visual impression of one immense tunnel without requiring one literal multi-kilometre straight level containing several thousand persistent wing Actors.

---

## 2. Source material and working assumptions

### 2.1 Existing project

The current PussStage project and Stage Wing Director plugin target Unreal Engine 5.8. The existing plugin already demonstrates several useful ideas:

- a Runtime/Editor module split;
- Primary Data Asset ownership;
- Left/Right/optional Top panel definitions with asset correction transforms;
- local in/out wing motion;
- spatial mechanism sound driven by scenic movement;
- an authoring window with lists, details panels, preview, validation, transactions, and automation tests; and
- optional contained-scene and transition-curtain integrations.

It also embodies the architecture that must now be retired:

- Sets, deprecated Bucket migration data, Look Cues, cyclic/random pair selection, and repeat-count semantics;
- a bounded carousel that wraps visible rigs;
- cue changes fed into the carousel at wrap points;
- per-pair generated lights and companion arrangements;
- a large tick-driven Director state machine;
- operator GO as the primary time source; and
- one ticking Pair Actor plus one ticking mechanism-audio component per visible pair, with generated fixture Actors potentially adding further cost.

The new plugin may adapt small, well-isolated concepts from the old code, but it must not serialize the old structs or subclass the old Director as its foundation.

### 2.2 Script sheet

The linked draft sheet, [“PUSS_draft 3”](https://docs.google.com/spreadsheets/d/1K00WJO1QO9P7SLUS2S_ppORToxhhsQLdpBvqlSvMBDA/edit?gid=0#gid=0), uses descending rows as chronological order. The read-only inspection for this specification used `Sheet1!A1:O101`. Its current macro structure includes:

| Approximate sheet rows | Macro Section |
| ---: | --- |
| 2–16 | Opening |
| 17–18 | Infinity Stage / Walking music 1 |
| 19–27 | Story 1 |
| 28 | Walking music 2 |
| 29–40 | Story 2 |
| 41–42 | Infinity Stage / Walking music 3 |
| 43–55 | Story 3 |
| 56 | Infinity Stage / Walking music 4 |
| 57–63 | Story 4 |
| 64–66 | Sunrise interlude |
| 67–70 | Infinity Stage / Walking music 5 |
| 71–83 | Story 5, including a moon interlude |
| 84–100 | Walking music 6 / late Infinity Stage events |
| 101 | End |

This validates one heterogeneous chronological **Cue Score**, rather than separate competing Passage and Scene timelines. The serialized cue kinds are **Wing Pair**, **Scene**, and **Sequence**; semantic roles include Opening, Passage, Scene, Interlude, Transition, and End. Contiguous Wing Pair cues are grouped into derived Passage Spans. A Hold is Transport/Section timing behavior, not another scenic asset type.

The brief refers to six scenes, while the current STRUCTURE labels explicitly name Story 1 through Story 5 alongside the Opening, interludes, and End. The plugin must not hard-code a scene count; final Section boundaries can be resolved editorially without changing the architecture.

The sheet's IMAGE, STAGE, LIGHTING, SOUND, and narration columns remain artistic/script references. The plugin should not try to generate those contents. It should provide timing, route anchors, sequence organization, and handoff points so that those elements can be authored manually in Unreal.

### 2.3 Confirmed production decisions and remaining defaults

The following decisions are now part of the specification:

- The principal editor is one chronological **Show Cue List**. A Wing Pair row represents exactly one Left/Right/optional Top occurrence. Scene rows and derived structural Passage headers also appear there, so not every visible row is a wing pair.
- A Scene row defines both an artist-authored sequence and the world-space Scene Volume/content in which it plays. Its most important plugin behavior is the incoming camera handover and outgoing camera handback.
- Final playback supports both Sequencer and live operator control. The operator moves forward and backward between named timeline segments; both modes evaluate the same absolute show time.
- Movie Render Queue (MRQ) is Unreal's offline/high-quality render pipeline. It is supported for deterministic output and testing, but is not a prerequisite for the live performance.
- Puss is a physical robot dog on the theatre stage and is outside this Unreal plugin's control. The virtual camera carries or resolves behind-camera shadow-casting figures representing Puss the cat and the Boy.
- A wing pair may keep looping while it can contribute to the image, including when seen in depth. Its phase is an absolute-time function, not accumulated Tick state.
- Pairs behind the camera may be reduced or unloaded only when they cannot contribute visible shadows, reflections, or other camera-visible effects.
- “Approximately one pair every two seconds” is treated as pass cadence. The mechanism loop duration remains an independent value.
- Every main Scene may conceal a spatial cut between separate Passage zones. The incoming Passage usually resolves into the Scene's establishing shot; the Scene owns its internal cuts; its closing shot resolves into the next Passage camera.
- Lighting, scenic props, and animated meshes are ordinary artist-authored Unreal Actors, optionally attached to stable passage anchors.
- Old show/Set/Pair authoring will not be migrated. Existing meshes and isolated implementation ideas may be reused as ordinary inputs to the fresh plugin.
- Music is the default Passage setup rail now. The selected Sound Wave's confirmed source In/Out range supplies Passage duration unless the artist explicitly changes duration authority. Frames remain the deterministic evaluation coordinate; this is not a second clock.
- Camera speed is normally a manually locked artistic value. Wing Pair count is normally derived from music duration, camera speed, spacing, and entry/exit clearances, with an inline **Reset to Music-Derived Count** action.
- Audio analysis is assistive, reviewable, and editor-only. It may propose loudness, onset, tempo, beat, and major-change markers, but it never silently rewrites timing, Wing Pair count, routes, or automation.
- All ordinary Wing Pair geometry is serialized, visible, and selectable in the Level Editor before PIE. Beginning play registers and animates existing content; it does not construct the stage.
- The default project layout uses separate spatial bays/routes so all Passages, Scenes, grounds, lights, and props can be visible together for art direction. Shared-coordinate Runtime Data Layer reuse remains an optional production optimization.
- Core show logic lives in a placed Show Root Blueprint/C++ Actor, not in the Level Blueprint. The Level Blueprint may only adapt venue-specific external input through the public transport API.
- The editor follows the QLab cueing pattern: a dominant chronological list, contextual inspector, compact status/transport rail, protected Operator mode, and user-resizable/dockable secondary panes.

---

## 3. Product goals

### 3.1 Primary goals

1. Author a finite show in one chronological Cue List that mixes Passage structure, Wing Pair rows, and Scene rows.
2. Keep that Cue Score as the sole chronological authority; Passage Spans store route/default/automation settings but never a second copy of their Wing Pair rows.
3. Make a four-minute, 120-pair passage comfortable to create and revise.
4. Keep a roughly 45-minute show responsive and deterministic at the eventual several-thousand-wing scale, with pair-versus-panel counting confirmed before budgets are frozen.
5. Place every wing pair, camera pose, and attached anchor along the same editable spline coordinate system.
6. Let insertion, deletion, spacing changes, and passage-length changes reflow the route without hand-adjusting every pair.
7. Allow selected patterns to be duplicated, repeated, reversed, redistributed, and retimed in bulk.
8. Allow motion, spacing, aperture, camera, and audio parameters to change gradually across a time or cue range.
9. Make the trimmed music recording the default Passage-duration authority, with a waveform, fades, manual markers, optional reviewed analysis suggestions, and an explicit speed/spacing/count solver.
10. Generate and maintain a master Level Sequence made from passage and artist-authored scene subsequences.
11. Provide section-level mechanism sound controls whose playback follows the exact authored motion.
12. Preserve manually authored lights, props, animation, and scene sequences when plugin data is rebuilt.
13. Treat Scene entry and exit as explicit camera contracts: Passage to establishing shot, internal Scene cuts, then closing shot to the next Passage.
14. Support deterministic local wing loops without turning the finite cue score back into a wrapping carousel.
15. Support operator Next, Previous, Go-to-Segment, Play, Pause, and Hold against the same master timeline used by Sequencer.
16. Provide a camera-associated Puss-and-Boy shadow-figure rig without attempting to control the physical robot dog.
17. Keep all fixed scenic geometry available in Editor mode and PIE, with a transactional materialization/synchronization step and no stage-content creation at BeginPlay.
18. Support distinct artist-owned ground systems per Passage and Scene without assuming one world-spanning floor.
19. Provide a flexible, QLab-inspired Cue Desk whose inspector, Music/Automation/Validation deck, columns, and workspace tabs are resizable, dockable, and recoverable.

### 3.2 Secondary goals

- Make passage data inspectable and exchangeable outside Unreal.
- Provide useful passage statistics: pair count, duration, path length, average/peak camera speed, minimum spacing, and active render/audio estimates.
- Permit special “hero” Wing Pair cues to use bespoke Actor classes while keeping the normal path highly batched.
- Reuse existing wing meshes, materials, audio assets, and isolated transform conventions through normal asset references and presets.
- Support both an artist-friendly editor workflow and a deterministic cooked runtime.

### 3.3 Non-goals

The core plugin will not:

- randomly generate pair order;
- cycle through asset pools;
- loop or wrap the finite cue order, camera route, or a bounded carousel;
- reproduce lighting-child arrangements from one wing set to another;
- own ordinary scene lighting;
- place incidental animated meshes automatically;
- replace Sequencer as the animation and shot editor;
- create one subsequence per wing pair;
- use a flat Unreal DataTable as the authoritative representation;
- treat inferred tempo, beats, downbeats, formal sections, or narrative meaning as unquestionable truth;
- time-stretch or pitch-shift the defining music merely to make an over-constrained Passage fit;
- synthesize, spawn, or silently repair fixed stage geometry at BeginPlay;
- use the Level Blueprint as a competing show clock, camera switcher, or section-music player;
- silently rescale an artist's absolute hand-drawn route;
- edit or destroy old Stage Wing Director assets in place; or
- simulate or control the physical robot dog on the theatre stage.

---

## 4. Terminology

| Term | Meaning |
| --- | --- |
| **Show** | The complete work, including passages, scenes, interludes, transitions, and holds. |
| **Section** | A derived macro timeline unit used by Sequencer, streaming, and sound: either one Passage Span or one Scene/Sequence cue. It is not a second chronological list. |
| **Show Cue List / Cue Score** | The authoritative ordered heterogeneous cue array and its principal editor view. Wing Pair, Scene, and other Sequence cues appear together in show order. |
| **Cue Row** | One serialized row in the Cue Score. Its kind determines whether it is a Wing Pair, Scene, or other Sequence. Passage headers and Event/Transport lanes are derived UI, not duplicate cue rows. |
| **Passage / Passage Span** | A finite camera journey derived from one contiguous run of Wing Pair cues, with its own route, defaults, automation, music, and mechanism settings. |
| **Scene** | A first-class cue row combining an artist-authored set-piece Level Sequence, defined world content/volume, and camera entry/exit contract. |
| **Scene Volume** | The registered world-space bounds/content adapter in which a Scene plays, normally backed by a Runtime Data Layer, Level Instance, spatial bay, or always-loaded content. |
| **Wing Pair cue** | One timed and positioned Left/Right/optional Top wing pair in a Passage. It is the atomic wing row, but not the only Cue Row kind. |
| **Panel** | One Left, Right, or Top mesh and its correction, material, and rendering settings. |
| **Pass frame** | The frame at which the passage camera crosses a Wing Pair cue's nominal transverse plane. |
| **Gap** | Arc-length distance from one Wing Pair cue to the next. |
| **Interval** | Time from one Wing Pair cue's pass frame to the next. |
| **Route** | The spline path and frame system shared by the camera, Wing Pair cues, Shadow Figure Rig, and manual attachment anchors. |
| **Passage default** | A value inherited by Wing Pair cues unless changed by automation or an explicitly masked row override. |
| **Automation lane** | A non-destructive parameter curve applied across a cue or time range. |
| **Wing Pair override** | A value explicitly pinned on one Wing Pair cue; it wins over Passage defaults and ordinary automation. |
| **Attachment Anchor** | A lightweight path-relative Actor/component that keeps manual lights, props, or animation aligned when the route changes. |
| **Shadow Figure Rig** | The virtual Puss-and-Boy figures carried behind or near the camera to cast their shadows into the photographed world. It is unrelated to control of the physical robot dog. |
| **Transport Segment** | A stable named span of the Master timeline used by live Next/Previous/Go controls and rehearsal navigation. |
| **Compiled Passage** | Dense derived arrays used for fast validation, preview, Sequencer evaluation, rendering, and audio. |
| **Music Rail** | A Show-owned concrete Sound Wave/source-range definition with gain, fades, output, and optional reviewed Music Map. A Section Music Binding selects the exact local coverage used by a Passage/Scene; that coverage is the default Passage setup-duration authority. |
| **Music Map** | Cached, editable waveform/feature, suggested-tempo/beat/change, and confirmed-marker data. Suggestions remain distinct from accepted artist data. |
| **Cue Desk** | The QLab-inspired editor workspace: dominant Cue Score, contextual inspector, optional bottom deck, and persistent status/transport rail. |
| **Show Root** | The one placed coordinator that owns or binds the Master Sequence Player, transport, camera arbiter, music router, readiness state, and persistent stage registry. |
| **Materialized Stage** | Serialized editor-world Passage/chunk/hero content built transactionally from the Cue Score. It exists before PIE and is animated, not created, at runtime. |
| **Ground Zone** | An artist-owned floor/terrain registration associated with a Passage or Scene and optionally a route range, folder, Data Layer, or Level Instance. |

The UI should call the atomic wing row **Wing Pair** unless production later standardizes another label. The code uses `FInfinityWingPairCuePayload` so it cannot be confused with a reusable mesh asset or the old Set/Look Cue concepts.

---

## 5. Core authoring model

~~~mermaid
flowchart TD
    A["Show Asset"] --> B["Authoritative ordered Cue Score"]
    B --> C["Wing Pair cues"]
    B --> D["Scene cues"]
    B --> E["Other Sequence cues"]
    C --> F["Derived contiguous Passage Spans"]
    F --> G["Route + defaults + automation + sound"]
    F --> R["Music Rail + reviewed Music Map"]
    F --> H["Compiled Passage data"]
    D --> I["Scene Volume / world content"]
    D --> J["Artist-authored Level Sequence"]
    D --> K["Entry + Exit camera contracts"]
    A --> L["Transport Segments"]
    A --> M["Persistent managed Master Sequence"]
    F --> N["Passage spline + camera rig"]
    H --> S["Persistent editor-materialized Wing Chunks"]
    N --> O["Puss/Boy Shadow Figure Rig"]
    N --> P["Manual Attachment Anchors"]
    A --> T["Placed Show Root: transport + camera + music authority"]
    A --> U["Artist-owned Scene/Ground Zones"]
    M --> Q["One subsection per Passage Span or Scene/Sequence cue"]
    R --> M
    T --> M
~~~

### 5.1 Source-of-truth rule

- **Show Asset / Cue Score** is the only authority for chronological order. It owns one ordered `TArray<FInfinityCue>` containing every Wing Pair, Scene, and other Sequence cue.
- **Passage Span records** are authoritative for route definition, defaults, automation, sound, and generated-sequence reference for a contiguous Wing Pair range. They are keyed to stable boundary Cue GUIDs and contain no duplicate cue array.
- **The Show Music Program** is authoritative for defining recordings, allowed source ranges, fades, gain, cross-Section continuation, and accepted Music Maps. Passage/Scene records own explicit Section Music Bindings that select local source coverage and duration/fit authority; managed audio tracks are adapters, not a second edit surface.
- **Scene cue payloads** are authoritative for the referenced Level Sequence, Scene Volume/world content, trims, and entry/exit camera contract.
- **Artist Level Sequences** are authoritative for the internals of Scenes, Interludes, and manually authored tracks.
- **The materialized Passage/Chunk world representation** is a serialized derived adapter with a manifest. Cue GUID/side identity and authored placement remain in the Show; manual Hero/viewport changes enter the Show only through explicit Adopt/Promote commands.
- **Artist-owned Ground Zones, lights, props, vegetation, and Scene sets** remain world authority for their content. The plugin registers, validates, and optionally anchors them but does not derive their artistry from the Cue Score.
- **The placed Show Root** is runtime ownership/coordination state, not an alternate Show data model.
- **Passage and Master Level Sequences** are persistent mixed-ownership containers. Plugin-owned tracks/sections are rebuildable adapters; user-owned tracks remain authoritative and are never regenerated.
- **Derived Sections, global timing, Passage membership, and compiled data** are replaceable results of the Cue Score and Passage Span records.
- **CSV/DataTable views** are exchange or reporting products, not truth.

No datum should have two silent authorities. A Scene row inserted between two Wing Pair cues partitions them into two Passage Spans; there is no separate Section list to reconcile. Where a managed Master subsection has been moved by hand, the plugin must flag drift and offer an explicit choice:

1. restore it from the Show Asset; or
2. adopt the Sequencer timing back into the Show Asset.

### 5.2 Passage partition rule

A Passage Span is one maximal contiguous run of included Wing Pair cues unless the artist adds an explicit Passage Break. Scene and other camera-bearing Sequence cues always break a Passage. The partitioner gives every span a stable `PassageSpanGuid` and preserves it when edits leave its identity unambiguous.

Structural edits are explicit:

- inserting a Scene inside a Passage previews a split and creates a new span record for one side;
- deleting the Scene previews a merge and asks which route/default/audio settings to keep or combine;
- moving a Wing Pair across a Scene moves it between spans and recompiles both;
- disabling a cue follows the Show's configured “omit and close gap” or “retain timed disabled placeholder” policy; and
- undo restores cue order, span IDs, routes, and settings in one transaction.

No span owns a copy of its member cues. Membership is resolved by GUID boundaries against the authoritative array and validated after every structural edit.

### 5.3 Scale and storage

The roughly 45-minute Cue Score may contain several thousand rows in one Primary Data Asset. This is acceptable only with:

- virtualized editor rows;
- compiled per-span data and incremental dirty-span rebuilds;
- compact serialized structs rather than one UObject per cue;
- transaction commands that touch only changed ranges where Unreal permits;
- per-span generated sequences, route actors, streaming manifests, and caches; and
- optional source-control locking/ownership guidance for a single show asset.

If production source-control contention later requires physical sharding, introduce a one-to-one cue-score storage asset or deterministic cue pages behind the same logical ordered array. Do not reintroduce separate chronologies or copy cues into Passage assets. The 3,000- and 10,000-cue fixtures remain engineering stress cases, not asserted production counts.

---

## 6. Main user workflows

### 6.1 Work in the unified Show Cue List

The default editor opens the complete work as one chronological, virtualized list. From top to bottom it displays:

- a derived collapsible Passage header followed by its contiguous Wing Pair cues;
- a Scene row wherever a set piece interrupts the walk;
- other Sequence rows for Opening, Interlude, Transition, or End; and
- optional editorial Event/Transport markers in dedicated lanes rather than pretending they are wing pairs.

The row type is always visible through its icon, color, indentation, and Details layout. Expanding a four-minute Passage exposes its roughly 120 Wing Pair rows in place; collapsing it returns to macro show structure. Expanding thousands of rows must remain virtualized.

The list is the authoritative Cue Score. A Passage header is a derived range, not a serialized duplicate. Dropping a Scene between Wing Pair cues previews the resulting Passage split, route/configuration inheritance, duration change, handoffs, and undo scope before committing.

### 6.2 Create the show

1. Run **Show > Initialize in Current Map**. In one undoable, idempotent transaction the plugin creates the Show Asset, managed Master Level Sequence, one `AInfinityStageShowRoot`, one placed Master `ALevelSequenceActor`, folders/Data Layers, camera infrastructure, and shared audio routing.
2. Choose display frame rate/tick resolution and confirm the output/clock profile.
3. Import or assign the first Passage music recording. Its full source range initially becomes the used In/Out range and default Passage duration.
4. Choose manual camera speed and Wing Pair spacing. Review the derived travel distance, count, cadence, clearances, and residual, then create the Passage rows.
5. Choose a finite route and spatial bay, create an optional temporary Ground Zone, and materialize the fixed Passage into serialized world content.
6. Add Scene and other Sequence cues in performance order; assign each Scene's Level Sequence, Scene Volume/content, ground/set context, and camera contracts.
7. Set trims, entry/exit camera markers, source handles, evaluation preparation, Master-time load/retention leads, section audio policy, and operator Transport Segments.
8. Build or refresh only plugin-managed sequence tracks, synchronize changed stage chunks, then validate the show.

Running initialization again repairs or reports missing managed pieces; it must not create duplicates. The Cue Desk opens immediately and exposes setup as a resumable dock tab rather than a blocking multi-page wizard.

### 6.3 Create a Scene cue

Selecting a Scene row exposes its complete definition in the same Details area:

- **Identity and timing:** label, role, stable GUID, enabled state, duration/trim, handles, notes, and script source.
- **Scene sequence:** artist-authored Level Sequence and internal-camera ownership.
- **Scene Volume/content:** registered Scene Volume GUID plus Runtime Data Layer, Level Instance, spatial bay, or always-loaded policy.
- **Entry:** establishing camera binding/marker, entry frame, optics/focus, and incoming Passage match policy.
- **Internal shots:** the interval in which the Scene sequence's Camera Cut Track is authoritative.
- **Exit:** closing camera binding/marker, exit frame, optics/focus, and outgoing Passage match policy.
- **Loading:** preload deadline, activation/deactivation, visibility isolation, and failure policy.
- **Sound:** guide/final track references, mix, fades, and boundary crossfades.
- **Live transport:** segment name, stop/hold behavior, and Next/Previous targets.

The optional world `AInfinityStageSceneVolume` is an editor and registration aid, not a box that clips rendering. It identifies the intended content bounds, streaming adapter, and camera markers. Its content remains artist-authored.

### 6.4 Create a passage

**Passage > Create Passage** opens a nonmodal, music-led setup tab beside the Cue Score. Passage is a derived range, not a Cue kind, so it must not appear in **+ Cue** or Cue insertion menus. The setup uses three internal tabs—**Music**, **Passage Fit**, and **Route & Stage**—with only one detailed section expanded at a time. A compact summary on each tab plus the persistent bottom rail keeps every linked result visible without making the window vertically enormous:

- Sound Wave and source In/Out range;
- music-used duration and Passage duration authority;
- fade-in/fade-out, gain, output, and analysis/marker state;
- camera speed or speed profile;
- Wing Pair spacing;
- entry and exit clearances;
- derived camera travel distance;
- Wing Pair count;
- average pass cadence and, for a speed curve, its minimum/maximum;
- route mode, required versus available length, spatial bay, and starter Ground Zone; and
- which single quantity the constraint solver is allowed to derive.

Recommended initial authority is:

| Quantity | Initial state |
| --- | --- |
| Music In/Out duration | **Music locked** |
| Camera speed | **Manual** |
| Wing Pair spacing | **Manual** |
| Entry/exit clearance | Derived as half a spacing each, then editable |
| Travel distance | Derived from the speed integral over music duration |
| Wing Pair count | **Derived** |

For a four-minute source, 2.5 m/s camera speed, 5 m spacing, and 2.5 m entry/exit clearances, the preview is 600 m, 120 Wing Pairs, and one pass every two seconds. The count field includes the requested inline **Reset to Music-Derived Count** control; it is not a global toolbar button.

Confirming creates the explicit placeholder Wing Pair rows, Passage Span record, persistent Passage Actor, serialized chunk content, camera rig, Shadow Figure Rig plan, section audio binding, and optional temporary flat Ground Zone. The rows may then be designed individually or in repeated selections; no Pair/Set library is created.

If the artist manually types a count, the editor asks which formerly fixed quantity may become derived. The recommended default is **Fit Spacing** while preserving music and camera speed. Resetting count restores the last artist-authored spacing and recalculates count from music, speed, and clearances. Replacing/reimporting music marks the fit stale and offers a preview; it never silently adds or deletes designed rows.

### 6.5 Author one Wing Pair row

Selecting one row opens its complete design in the Details area. No separate Pair or Wing Set library is required.

The row details are grouped as:

- **Identity:** label, stable ID, enabled state, color/tags, Cue Range membership, notes.
- **Timing and spacing:** interval to next, gap to next, pass-frame display, derived distance display.
- **Left panel:** asset, enabled, correction rotation, 2D scale, full transform, material overrides, shadow/collision.
- **Right panel:** same fields.
- **Top panel:** optional, same fields.
- **Pair placement:** half-width/aperture, center offset, height, yaw/roll relative to route.
- **Mechanism motion:** Static/One Shot/Continuous Loop/Bounded Loop, cycle rate/duration, phase origin/offset, travel, Left/Right relationship, Top behavior, and curves.
- **Audio override:** normally empty; only exceptional Wing Pair cues override the Passage profile.
- **Special rendering:** ordinary batched instance or optional hero Actor class.

Duplicate creates an independent deep copy with a new stable GUID. Mesh assets remain shared references; authored values do not remain secretly linked.

### 6.6 Build and repeat a pattern

The user can select any contiguous or non-contiguous Wing Pair rows and:

- duplicate once;
- repeat N times;
- insert before or after the selection;
- copy/paste as an independent range;
- reverse order;
- move by drag/drop or keyboard;
- replace Left/Right/Top assets;
- swap Left and Right;
- enable or disable Top;
- fill a property with one value;
- offset a property by a value;
- distribute intervals or gaps;
- stretch selected timing to a target duration;
- fit selected spacing to a target length;
- interpolate endpoint values;
- clear selected overrides; or
- create an Automation Lane from the selection.

Repeat Selection is a finite **authoring** command: it creates explicit rows that can be changed independently. This is distinct from a wing mechanism's local repeating motion, which may loop at runtime without creating or recycling cue rows.

If a mixed selection includes Scene/Sequence cues, wing-only commands clearly report that those rows will be skipped, or reject the operation when order/timing would become ambiguous. No bulk command silently converts a cue kind or crosses a Scene boundary. Copying a mixed score range is allowed as a structural command with a full split/merge preview.

### 6.7 Make a gradual change

For “wing movement slows over 30 seconds”:

1. Select the affected rows or drag a range over the passage ruler.
2. Choose **Add Automation Lane**.
3. Choose **Mechanism > Loop Rate** or **Duration Scale**.
4. Set the start and end values, for example 1.0 to 2.0.
5. Choose an ease shape or edit the curve.
6. Preview the resolved values and motion.

For “wings widen over 30 seconds,” target **Mechanism > Inward Travel** or **Layout > Resting Half Width**, depending on the intended visual effect. Time-varying loop rate is integrated into phase, so the slowdown does not pop or restart a cycle.

For “the whole passage slows,” use a transactional timing operation that previews and writes intervals. The UI must never label all three operations merely “speed”:

- **Pass cadence / camera pace** changes when the camera reaches pairs.
- **Mechanism duration** changes how quickly an individual pair moves in/out.
- **Animation/audio playback rate** changes a referenced asset's rate.

### 6.8 Place manual props and lights

The artist places ordinary Actors in the level. If they must remain associated with a route position:

1. Add an Infinity Stage Attachment Anchor.
2. Bind it to a Show, Passage Span GUID, and Wing Pair Cue GUID, or to an explicit local frame/distance.
3. Choose Center, Left, Right, Top, Before, or After as its reference socket.
4. Attach the manual light, prop, Niagara system, or animated Actor beneath it.

Recompiling the route repositions the Anchor but never replaces or rewrites its artist-authored children.

### 6.9 Hand a camera into and back out of a Scene

1. In the incoming Passage, capture the arrival/settled camera as its Exit Pose.
2. On the Scene row, choose the establishing camera and run **Match Incoming Passage to Scene Entry**.
3. Adjust transform, lens, focus, screen-space target, and any final approach blend until validation is within tolerance.
4. Set the exact handover frame. Before it, the Passage camera is authoritative; from it, the Scene sequence owns Camera Cuts.
5. Choose the Scene's closing shot and capture its Exit Pose.
6. Select the next Passage Entry Pose and run **Match Scene Exit to Outgoing Passage**.
7. Set the exact handback frame. The closing shot may move continuously into the outgoing Passage pose, or the Scene may conceal a matched/hard cut to a separate Passage zone.
8. Preview entry, internal cuts, and exit together in Master context, including first-frame world loading.

Each Scene is therefore a deliberate camera bridge as well as a set piece. It may hide the spatial reset between two unrelated Passage splines, but the boundary frames and camera ownership are never inferred from whichever child happens to evaluate last.

### 6.10 Set up the Puss-and-Boy Shadow Figure Rig

1. Select a Passage header and enable its Shadow Figure Rig plan.
2. Assign the Puss-the-cat and Boy figure assets or an artist-authored rig class.
3. Position them behind/lateral to the camera in route-relative upright or camera-relative mode.
4. Choose shadow, main-pass, reflection, and lighting-channel behavior supported by the production renderer.
5. Bind any relative walk/gesture animation in the managed Passage sequence or an artist-owned track.
6. Preview from the Cine Camera with shadow/debug bounds visible and validate that the figures themselves do not enter the intended shot.

This rig exists only in Unreal. It does not drive, sense, or synchronize the physical robot dog on stage.

### 6.11 Rehearse with operator transport

1. Create or accept default Transport Segments at Passage, Scene, and chosen Event boundaries.
2. Preflight the previous, current, and next segment's world/asset readiness.
3. Use Play Forward/Reverse to a boundary, Pause/Resume, Jump to Start/End, or Previous/Next Segment.
4. Confirm current absolute frame, selected segment, direction, camera owner, music-clock state, and readiness in the operator monitor.
5. When music is owned by the Master sequence, picture and music move together. When an external music/timecode source cannot pause or reverse, unsafe transport commands are disabled rather than allowed to drift.

These controls wrap the same root Level Sequence Player used by ordinary playback. They never create an independent cue clock or resurrect per-wing GO state.

### 6.12 Synchronize the fixed editor stage

The Cue Score is authoritative, but its world representation is persistent and visible. **Passage > Synchronize Stage** performs a previewed, transactional diff:

1. Compare the Show revision with the materialization manifest.
2. Report Cue additions/removals, route relocations, render-key migrations, hero conflicts, Anchor dependants, and Ground Zones made stale.
3. Apply changes only to affected persistent chunks.
4. Preserve artist-owned grounds, lights, props, vegetation, Scene sets, and Anchor children.
5. Update the manifest and validation state.

Timing-only edits do not rebuild geometry. Spacing, route, panel asset, count, or placement changes do. Small local edits may auto-synchronize after a debounce if enabled; structural changes require explicit synchronization. Repeating an unchanged synchronization must not dirty a package.

Selection is bidirectional: selecting a Wing Pair row highlights its Left/Right/Top instances; selecting a managed instance reveals its Cue row. A generic viewport move is detected as world drift and offers **Adopt World Transform** or **Revert to Cue**. A special pair may be promoted to a persistent Hero Actor while retaining its Cue GUID.

### 6.13 Author section-specific ground

Unreal does not require one world-spanning ground. For each Passage or Scene, the artist may register one or more Ground Zones using modular Static Meshes, a spline strip, an independent Landscape, a Level Instance, or fully manual content.

The setup tab can create a neutral temporary deck following the Passage bounds. The artist may later promote it to manual/world-locked ownership and replace it with wood, concrete, forest soil, vegetation, decals, terrain, or a set-specific floor. Once promoted, the plugin validates but never reshapes or replaces it.

Ground transitions may be:

- physically continuous and art-directed;
- blended/overlapped in a transition zone;
- separated and hidden by the intervening Scene's cut language; or
- mutually exclusive in Runtime Data Layers when shared coordinates are deliberately used.

Separate bays are the default because they let the whole show—including distinct grounds—remain visible and editable at once.

---

## 7. Detailed data model

The names below are proposed C++ names, not commitments to final UI labels.

### 7.1 UInfinityStageShowAsset

A `UPrimaryDataAsset` containing:

- `SchemaVersion` and custom serialization version;
- `ShowGuid`;
- display name and notes;
- `DisplayRate` and `TickResolution`;
- global defaults;
- authoritative ordered `TArray<FInfinityCue>`;
- `TArray<FInfinityPassageSpan>` containing no duplicate cues;
- `TArray<FInfinityCameraHandoff>`;
- ordered `TArray<FInfinityTransportSegment>` for live/rehearsal navigation;
- authoritative `FInfinityMusicProgram` containing stable Rail source definitions and the compiled interval map derived from Section Music Bindings;
- soft reference to the managed Master Level Sequence;
- expected placed Show Root GUID and world/materialization profile;
- global audio bus/submix, camera-authority, and setup defaults;
- managed-content build hash;
- persistent stage-materialization hash/manifest reference;
- packaging/preload policy; and
- validation suppression records with reasons.

### 7.2 FInfinityCue

Common fields:

- immutable `CueGuid`;
- display name and cue kind: Wing Pair, Scene, or Sequence;
- semantic role: Passage content, Opening, Scene, Interlude, Transition, End, or project-defined role;
- included/enabled;
- editorial color and tags;
- source sheet/script reference;
- notes;
- optional persistent editor warning suppressions; and
- exactly one payload matching `CueKind`.

Payloads:

- **Wing Pair:** `FInfinityWingPairCuePayload`
- **Scene:** `FInfinitySequenceCuePayload` with required Scene fields
- **Sequence:** `FInfinitySequenceCuePayload` for Opening/Interlude/Transition/End

Do not use a fragile inheritance hierarchy of polymorphic `USTRUCT` values. Use an enum plus well-separated payload structs and enforce kind/payload consistency. `FInstancedStruct` is acceptable only if its editor, diff, transaction, and cook behavior pass the risk spike.

### 7.3 FInfinitySequenceCuePayload and Scene definition

All Scene/Sequence cues carry:

- `TSoftObjectPtr<ULevelSequence>`;
- playback-range or explicit-trim policy;
- explicit or derived duration;
- `SourceHandles` describing unused source frames available before/after the chosen trim;
- optional MovieScene evaluation pre-roll/post-roll used only to prepare hidden state;
- `LoadLeadFrames` and `RetentionTailFrames` in Master time for world/audio readiness and reverse operation;
- world-content adapter: Runtime Data Layer, Level Instance, spatial bay, or always loaded;
- optional registered `SceneVolumeGuid` and expected world bounds;
- activation, visibility-isolation, and release policy;
- one explicit `FInfinitySectionMusicBinding` containing defining-music policy, Rail references, local coverage, transition identity, and outer-mix settings; and
- source/script notes.

V1 never delegates the defining score to a child sequence. Scene/Sequence children may retain artist-authored dialogue, ambience, effects, and a muted/reference guide, but the Show Music Program and its managed Master Audio Track remain the only defining-music authority. A future child-owned score mode is deferred until it can meet the same seek, preload, exclusive-owner, and operator-readiness contract.

When the semantic role is Scene, the payload additionally requires:

- Entry Camera binding or named marker and exact establishing frame;
- Exit Camera binding or named marker and exact closing frame;
- entry and exit transform, lens, aperture, sensor, focus, and aim snapshots used for comparison;
- the internal frame range in which the Scene's Camera Cut Track owns the view;
- incoming-handover and outgoing-handback policy;
- optional safe-cut/occlusion notes; and
- optional `SceneVolumeGuid` resolved through a self-registering `AInfinityStageSceneVolume`.

The Scene Volume stores or exposes editor bounds, content membership/adapter, camera-marker components, and validation aids. It does not generate set dressing, lighting, animation, or shots. Runtime identity is GUID-based; Actor labels are display-only.

### 7.4 FInfinityCameraHandoff

This is the single authority for camera ownership across one adjacent derived Section boundary. It is keyed by previous Passage Span/Sequence Cue GUID and next Passage Span/Sequence Cue GUID and contains:

- transition policy: direct cut, match cut, opaque transition, or authored Transition Sequence;
- authored exact local boundary frames on each side, with global Master frame derived by the compiler;
- previous Exit Pose and next Entry Pose references;
- exact camera-authority switch and ownership on each side of the boundary;
- available source handles for trimming/match work; V1 macro Sections remain serial and non-overlapping;
- transform/lens/focus tolerances;
- next-content preload deadline and failure policy;
- audio crossfade/mix boundary; and
- notes.

A Scene normally has two records: incoming Passage-to-Scene handover and Scene-to-outgoing-Passage handback. A creatively authored Transition is an ordinary Sequence cue with one record on each side. Transition fields must not also be duplicated inside neighboring records or inferred from evaluation order.

### 7.5 FInfinityTransportSegment

A persistent live/rehearsal navigation record containing:

- immutable `TransportSegmentGuid`;
- label, color, enabled state, and notes;
- start and end anchors expressed as stable Cue/Passage Span/Event/Cue Range GUID plus local frame;
- resolved absolute Master start/end frames;
- forward action at end: continue, pause/hold, or wait for operator;
- Previous/Next target policy;
- restart-versus-resume policy when revisiting;
- whether audio follows the Master transport or an external unpausable source;
- optional keyboard/OSC/MIDI control label; and
- validation state.

The default builder creates one segment per derived Section. Artists may subdivide a long Passage at Events or Cue Ranges without splitting its span. Live controls always seek/play the Master Level Sequence; a Transport Segment never carries its own mutable animation state or alternate clock.

### 7.6 FInfinityPassageSpan

Contains:

- immutable `PassageSpanGuid`;
- display name, description, tags;
- stable first/last member Wing Pair Cue GUIDs;
- lead-in time and distance;
- tail time and distance;
- Passage defaults;
- route definition;
- camera plan;
- Shadow Figure plan for the virtual Puss-and-Boy figures;
- `TArray<FInfinityAutomationLane>`;
- `TArray<FInfinityCueRange>`;
- `TArray<FInfinityPassageEvent>`;
- one `FInfinitySectionMusicBinding` referencing the Show Music Program and defining this Passage's local music coverage;
- last applied `FInfinityPassageFitRecipe`/source fingerprint and stale-fit state;
- mechanism-audio profile;
- rendering/materialization/optional serialized-streaming policy;
- associated persistent Passage Actor and Ground Zone GUID references;
- optional persistent managed Passage Level Sequence reference;
- content hash and compiled-cache version; and
- editor-only selection, column, and view preferences kept in user settings rather than production data where possible.

It never stores member Wing Pair cues. The compiler resolves its contiguous membership from the authoritative Cue Score, errors if its boundaries are missing/non-Wing/non-contiguous, and updates boundary GUIDs transactionally during a confirmed split or merge.

### 7.7 FInfinityWingPairCuePayload

Contains:

- `IntervalToNext` in frames;
- `GapToNextCm`;
- Left, Right, and Top `FInfinityPanelDefinition`;
- pair-level relative transform;
- local half-width/aperture override;
- mechanism-motion override mask and values, including loop enable/cycle/phase where locally pinned;
- audio override mask and values;
- optional route-roll/height/lateral overrides;
- render mode;
- optional hero Actor class;
- editor warning suppressions local to this row.

Identity, enabled state, label, notes, and tags live once in the owning `FInfinityCue`. Derived local/global pass frame, cumulative distance, spline transform, effective parameters, chunk, and batch indexes do not belong in the authored payload.

The last Wing Pair cue in a Passage Span has Interval/Gap-to-next disabled in the normal UI. Span tail values provide the final travel to its Scene/Sequence boundary.

### 7.8 FInfinityPanelDefinition

Adapt the useful semantics of the old panel definition:

- enabled;
- soft Static Mesh reference;
- optional material overrides;
- rotation in 90-degree correction steps;
- 2D X/Z scale for flat photographic panels;
- advanced local transform;
- cast shadow;
- collision policy, default No Collision;
- mobility/rendering flags;
- optional per-instance custom-data defaults; and
- asset bounds override only when imported bounds are unusable.

Useful old transform conventions may be copied into a manually created project preset, but new project defaults live in Project Settings and are editable.

### 7.9 FInfinityPassageDefaults

Contains the values normally shared by all Wing Pair cues in a Passage Span:

- panel placement conventions;
- resting half-width;
- inward travel;
- top-panel behavior;
- mechanism style and curve;
- default motion mode: Static, One Shot, Continuous Loop, or Bounded Loop;
- loop rate/duration, phase origin/offset, Left/Right/Top normalized curves, and optional activation span;
- pass-relative pre-pass/post-pass gesture preset when a non-looping row is deliberately chosen;
- stage-up/orientation policy;
- render/collision/shadow policy;
- camera height, lateral offset, look-ahead, roll, and lens;
- gap and interval defaults;
- audio profile; and
- editor preview and runtime contribution-tier distances/times.

### 7.10 FInfinityShadowFigurePlan

Defines the virtual figures that travel with the camera and cast Puss-and-Boy shadows:

- enabled state and rig class/prefab;
- extensible figure array with role (initially Puss the cat and Boy), soft mesh/Actor asset reference, and optional Sequencer binding;
- root mode: camera-relative or route-relative, with camera-relative as the production default;
- longitudinal distance behind camera plus lateral, height, rotation, and scale offsets;
- independent relative transforms for both figures;
- shadow-casting, direct-visibility, reflection, and lighting-channel policy;
- optional walk-phase/velocity outputs for artist animation, without choosing or owning that animation;
- activation and conservative bounds used by shadow/collision validation; and
- Passage-level overrides of Show defaults.

“Attached behind the camera” is evaluated as a stable world transform from the current camera/route frame, not as an uncontrolled late-ticking child. That keeps shadows deterministic under scrub, reverse, segment jumps, and offline rendering. The physical robot dog has no data or control interface in this plan.

### 7.11 FInfinityAutomationLane

Contains:

- immutable Lane GUID;
- name, color, enabled/muted;
- parameter ID from a typed enum/registry;
- domain: Wing Pair index within the span, Cue GUID range, Passage-local frame range, or normalized Passage range;
- start/end anchors;
- blend mode: Override, Add, or Multiply;
- priority;
- `FRichCurve` or equivalent channel;
- boundary behavior;
- optional lane group; and
- notes.

Explicit Wing Pair payload override masks always win; lanes cannot opt out of that rule.

Discrete values such as mesh assets or booleans are not tweenable. They may use a range fill operation, not an interpolation lane.

In V1, Automation Lanes cannot target `IntervalToNext`, `GapToNextCm`, total duration/length, or the distance-time rail. Those are changed by explicit transactional retiming/respacing tools. This prevents a lane from altering the time or distance domain in which it is itself evaluated. A time-domain loop-rate lane is permitted because its integrated phase is a dependent motion result, not the camera/time rail.

### 7.12 FInfinityCueRange and FInfinityPassageEvent

`FInfinityCueRange` is a named contiguous range anchored by start/end Wing Pair Cue GUIDs inside one Passage Span. It supports collapse, selection, duplication, repetition, color, and notes. Ordinary Tags remain non-contiguous filters and never imply range topology.

`FInfinityPassageEvent` is a first-class editorial marker containing:

- immutable Event GUID;
- name, role, color, and notes;
- anchor mode: frame, Wing Pair Cue GUID, station distance, or normalized progress;
- optional Attachment Anchor/Actor soft reference;
- optional script-sheet/source reference;
- optional generated Sequencer marked-frame label;
- optional `Transport Stop` flag used to derive/subdivide live Transport Segments; and
- event category such as Puss glance, narration, music, animation, scenic encounter, or technical.

Events organize manually authored encounters without placing or animating their content.

### 7.13 FInfinityRouteDefinition

Contains:

- route mode;
- serialized route points or generator settings;
- spline point type and tangents;
- up-vector and roll policy;
- footprint/turn/height constraints;
- target-length policy;
- lead-in/out continuation;
- endpoint camera framing data;
- closed-loop flag forced false for production passages;
- preview drawing settings; and
- revision GUID used by compiled data and Anchors.

### 7.14 FInfinityCompiledPassage and FInfinityCompiledShow

Derived dense arrays:

- Wing Pair Cue GUIDs and GUID-to-index map;
- pass frames;
- cumulative distances;
- effective intervals/gaps;
- effective motion/layout/camera/audio values;
- spline frames/transforms;
- absolute-time loop parameters/phases, motion active intervals, and conservative motion envelopes;
- audio event schedules;
- render keys, persistent Chunk GUIDs, component lookup, and current instance indexes;
- asset preload lists;
- Music Rail/sample mapping, fit snapshot, and accepted marker references;
- materialization-manifest revision and Ground Zone coverage requirements;
- route-clearance and shadow-relevance metadata;
- statistics and validation facts; and
- source content hash.

`FInfinityCompiledShow` additionally contains:

- cue-kind indexes and Cue GUID-to-global-order map;
- derived Section/Passage Span ranges and global start/end frames;
- exact conversion between global Master time and each Passage/Scene local time;
- Scene ranges and world-content manifests;
- camera-authority intervals and Handoff records;
- Transport Segment bounds and previous/current/next preload relationships; and
- the Show content hash.

The compiled representations must be reproducible from the Show Asset's Cue Score and Passage Span settings. Editor builds may cache them in Derived Data Cache. Cooked builds serialize/version compiled blobs, or generate them deterministically during cook; runtime playback must never require DDC. Compiled data is never the only copy of authored information.

### 7.15 FInfinityMusicProgram, FInfinitySectionMusicBinding, FInfinityMusicRail, and UInfinityMusicMap

The Show owns one `FInfinityMusicProgram`: an ordered array of stable Rail source definitions plus a compiled interval map assembled from every derived Section's binding. Each `FInfinityMusicRail` contains:

- immutable Rail GUID;
- soft `USoundWave` reference;
- allowed source In and Out as integer sample indices;
- base gain and output bus/submix;
- default non-destructive fade shape/settings, overridable at an authored binding boundary;
- source fingerprint, seek/compression readiness, and stale-analysis state;
- optional `UInfinityMusicMap` reference; and
- notes.

The Rail describes one recording/source range; it does not own a Section policy or Passage duration. Each Passage Span and Scene/Sequence payload instead owns one `FInfinitySectionMusicBinding` containing:

- immutable Binding GUID and owning derived Section GUID;
- policy: **Start Own Rail**, **Continue Previous Rail**, **Silence**, or **Explicit Crossfade**;
- `PrimaryRailGuid` for Start/Continue;
- separate `OutgoingRailGuid` and `IncomingRailGuid` plus required `TransitionGuid` for Explicit Crossfade;
- for every participating Rail, exact Section coverage In/Out sample indices or confirmed Rail-marker anchors within that Rail's allowed source range;
- local Section coverage offset, compiled Master/source-sample mapping, and continuation expectation;
- binding fade/crossfade, gain/mix override, and reference-only child-guide declaration; and
- Passage-only duration/fit-window authority plus validation state.

**Start Own Rail** begins the Primary Rail at the binding's coverage In. **Continue Previous Rail** uses the same Rail GUID and requires its coverage In to equal the previous binding's coverage Out, within an explicit sample tolerance; it creates no stop/restart or duplicate player. **Silence** references no output Rail. **Explicit Crossfade** is the only binding with two Rail GUIDs and describes the outgoing/incoming source ranges and shared Transition identity structurally rather than overloading one field.

This makes a recording that spans a Passage and Scene serializable: each Section owns only its local coverage while the Music Program compiles one continuous output interval. A child may contain ordinary scene sound design, but it may not own the defining score in V1. Policy, transition, and coverage are never duplicated on the Rail itself.

The defining source is a concrete Sound Wave rather than an arbitrary procedural Sound Cue/MetaSound because duration, source sample, waveform, repeatable seeking, and analysis need one unambiguous recording. A later playback wrapper may be used only when it declares exact sample alignment to that Sound Wave.

`UInfinityMusicMap` separates machine proposals from artist decisions:

- source fingerprint plus analyzer/settings version;
- cached multiresolution waveform, loudness, onset, spectral/Constant-Q, and novelty curves;
- competing global/local tempo candidates, including half/double-time ambiguity and confidence;
- suggested beat/downbeat and major-change candidates with stable GUIDs/provenance;
- confirmed tempo segments, beats, bars, markers, and named structural ranges;
- rejected suggestion GUIDs; and
- manual tap-tempo/downbeat/grid-correction history.

Dense waveforms, feature curves, suggestions, rejection/provenance history, and analysis scratch data are `WITH_EDITORONLY_DATA` or DDC-backed. Cook only compact confirmed tempo/marker data actually required for runtime labels/scheduling; if confirmed information has already been baked into Master frames/Events, strip the Music Map runtime payload entirely.

Reanalysis of the same source fingerprint preserves confirmed and rejected decisions unless explicitly cleared. A replacement source fingerprint never inherits them silently: offer an explicit remap by source time, normalized progress, or imported composer identity, show a diff, and require review. Suggestions never become Cue Score rows automatically. Confirmed items may be converted, through a previewed command, into Passage Events, Cue Ranges, automation boundaries, or pass anchors.

### 7.16 FInfinityStageMaterializationManifest

The materialization manifest is stored with the map/Show setup and contains:

- Show/source hash and schema/build versions;
- persistent Passage, Chunk, Hero, camera, Shadow Figure, Show Root, and Ground Zone GUIDs;
- Cue GUID + panel side to Chunk/component/instance lookup;
- render-key and expected object/instance counts;
- artist-ownership exclusions and promoted-hero records;
- stale/dirty chunk ranges; and
- last successful transactional synchronization result.

An ISM index is never durable identity because batching changes it. Cue GUID plus Left/Right/Top side remains identity. Missing or stale fixed content is a PIE/cook validation error; runtime may not regenerate it as a recovery mechanism.

### 7.17 FInfinityGroundZoneRegistration

A Ground Zone registration contains:

- immutable Zone GUID and owner Passage Span/Scene Cue GUID;
- optional start/end route distance;
- world bounds and strategy: Static Mesh, Spline Strip, Landscape, Level Instance, or Manual;
- folder, Editor Data Layer, and optional Runtime Data Layer;
- scaffold state: Follow Route or artist-promoted World Locked;
- transition type: hard cut/concealed seam, blend, or continuous;
- soft references/registered actors without taking ownership of their artistic content;
- expected surface/height and wing/camera/shadow clearance tolerances; and
- notes and validation state.

The plugin may create or update a temporary scaffold deck while it remains Follow Route. It never modifies a World Locked Ground Zone automatically.

---

## 8. Timing and distance model

### 8.1 Frame-domain authority

All authored show timing uses `FFrameNumber`/`FFrameTime`, not accumulated floating-point seconds. The Show defines:

- a human-facing display rate; and
- a high-resolution tick rate suitable for Sequencer evaluation.

The UI may display seconds, timecode, or future bar/beat labels, but converts to frames at the boundary.

This does not conflict with music-led setup. A confirmed Sound Wave In/Out range is converted from integer samples into the Show's rational frame domain and normally determines a Passage's initial frame duration. Once compiled, Sequencer's absolute Master frame is the single evaluation coordinate for music, camera, wings, Scenes, and operator transport. Music is the **authoring rail**, not a free-running second clock.

Managed Passage and Master sequences use the Show tick resolution. Child-sequence ranges, trims, and marked frames are converted with `FFrameRate::TransformTime` or its exact UE 5.8 equivalent and retain subframes. Any unavoidable display-frame rounding is visible and uses one documented policy; it must not accumulate across Sections.

### 8.2 Global Cue Score rail

The compiler partitions the Cue Score into derived Sections in order:

- each Passage Span duration is `LeadIn + WingPairIntervals + Tail`;
- each Scene/Sequence cue duration is its explicit trim/duration or referenced sequence playback range; and
- authored Transition cues and holds occupy their own serial duration according to their Handoff/Transport policy.

For Section `j`:

    GlobalStart[j + 1] = GlobalStart[j] + EffectiveDuration[j]

Each Section stores an exact transform between global Master frame and local child frame, including trim, subframe offset, and any allowed play rate. Wing pass frames and Passage Events are compiled in Passage-local time, then mapped into the global score. Scene rows therefore occupy real chronological duration in the same array as the surrounding Wing Pair cues even though their animation is owned by another Level Sequence.

V1 macro Sections are half-open, serial, and non-overlapping. An authored Transition is its own Sequence cue between neighboring Sections and owns the Camera Cut for its serial interval. Source handles can be used to create the transition asset, but they do not make the neighboring Master subsections co-evaluate. Defining-music Audio Sections may overlap only for an explicitly declared crossfade on the one managed Master Audio Track.

### 8.3 Passage-local time and distance rails

Each Wing Pair cue inside one Passage Span defines:

- interval to the next pass; and
- arc-length gap to the next occurrence.

For Wing Pair cue `i`:

    PassFrame[i + 1] = PassFrame[i] + IntervalToNext[i]
    Distance[i + 1]  = Distance[i]  + GapToNextCm[i]

The complete anchor set is:

1. Passage start: `(0, 0)`
2. Lead-in end / first occurrence: `(LeadInFrames, LeadInDistance)`
3. Every later Wing Pair pass anchor
4. Passage end: `(LastPassFrame + TailFrames, LastDistance + TailDistance)`

A Passage Span cannot have zero rows because membership is derived from at least one contiguous Wing Pair cue. A one-row Passage uses start, its single pass anchor, and end. Two anchors may not have the same frame with different distances.

This representation answers four important questions directly:

- How many pairs are there? The row count.
- How long is the passage? Lead-in + intervals + tail.
- How long is the physical route? Lead-in distance + gaps + tail distance.
- When does the camera pass each pair? The cumulative pass frames.

For the default music-fit layout, entry and exit distance each begin at half the requested centre-to-centre spacing. This centres one Wing Pair in each notional spatial cell, so a 600 m route at 5 m spacing contains exactly 120 pairs: first pass at 2.5 m and last pass at 597.5 m. Artists may override the clearances, but the solver must always report them.

### 8.4 Camera distance curve

The compiler creates a monotone distance-over-time curve through the complete start/lead/occurrence/tail anchor set. It should use monotone cubic interpolation or another tangent-clamped method that:

- crosses every authored anchor exactly;
- avoids unintended reversal;
- avoids negative speed;
- exposes speed/acceleration diagnostics; and
- remains deterministic under scrub, jump, reverse, and render.

The user can select a linear, smooth, or hold-like tangent policy at anchors, but the validator blocks or repairs a non-monotone curve unless explicit reverse travel is introduced as a future feature.

### 8.5 Editing absolute values

The grid may show both:

- derived Passage-local and global Master Pass Time plus local Distance; and
- authored Interval and Gap.

Editing an absolute pass time updates the preceding interval. Editing an absolute distance updates the preceding gap. Bulk ripple rules must be shown before the edit is committed.

### 8.6 Lock and solve rules

The passage may persist editor-authoring constraints for:

- total duration;
- total route length;
- selected music markers;
- selected Wing Pair Cue pass frames/distances; or
- a combination that remains mathematically solvable.

The Guided Setup exposes exactly one solver output at a time:

- **Fit Wing Count** — default;
- **Fit Spacing**;
- **Fit Camera Speed**;
- **Fit Duration**; or
- **Fit Exit Clearance**.

Music In/Out duration and manual camera speed are locked by default; Wing Pair count is derived. Editing a derived value changes authority explicitly and asks which former input may become derived. No field silently moves merely because another was typed.

Bulk retiming presents explicit policies:

- **Ripple following:** later Wing Pair pass times move.
- **Keep passage end:** compensate across a chosen unpinned range.
- **Change spacing, not timing:** preserve pass frames and adjust gaps.
- **Change timing, not spacing:** preserve physical placement and alter camera speed.

In V1 these constraints govern editor commands; they are not hidden runtime modifiers. A retiming/respacing command solves a named elastic range and writes the resulting base intervals/gaps in one transaction. If it cannot satisfy the pins, positivity rules, and total lock, it applies nothing and lists the constraints that must be released.

Guided Setup stores the last applied fit recipe—Music Rail fingerprint/allowed range, Section coverage, duration and fit-window authority, camera-speed profile, requested/last-manual/solved spacing, entry and exit clearance modes/values, solver target, residual policy, and result hash—for understandable reopening and reset. Each clearance mode is **Half Spacing**, **Manual**, or **Solved**. Half Spacing follows solved spacing; Manual remains numerically pinned; Solved is written only by an explicit clearance solve. Editing a Solved clearance changes it to Manual. Selecting another solver target while a Solved clearance remains involved requires an explicit choice to preserve it as Manual or release it back to Half Spacing/Solved; authority never changes silently. Editing the recipe creates a **Proposed/Stale Fit** until **Apply Fit** writes the resulting lead/tail, intervals, gaps, count, and materialization changes transactionally. Runtime compilation reads the written anchors, never an unapplied proposal; this prevents a hidden second timing authority.

### 8.7 Deterministic compile order

The compiler resolves data in this order:

1. Read the authored lead/tail, intervals, and gaps already produced by editor commands.
2. Validate positivity and construct absolute frame/distance anchors.
3. Construct the monotone distance-time rail.
4. Sample non-rail Automation Lanes at stable frame/distance/index domains.
5. Apply explicitly masked Wing Pair Cue overrides.
6. Compile motion, camera-offset, render, Event, Anchor, and audio schedules.
7. Validate final bounds, monotonicity, and budgets.

A stored interval/gap is authoritative rail data, not an automatic local override. Every lane-targetable scalar has an explicit local-override bit.

### 8.8 Operator transport and time conversion

`UInfinityStageTransportController` controls the same root `ULevelSequencePlayer` as the Master sequence. A forward/reverse play, pause, seek, or segment jump changes only the authoritative global Master position. The compiled global-to-local map then evaluates the correct Passage, Scene, camera owner, loops, shadows, and Anchors for that frame.

Transport Segment ranges are inclusive at start and exclusive at end. Play-to-boundary clamps exactly without a one-frame overshoot. A target that is not preloaded leaves both time and camera ownership unchanged and reports **Not Ready**; it never performs a partial seek.

### 8.9 Music readiness

V1 includes the reliable Music Rail: Sound Wave, exact In/Out, waveform, fades, gain, duration authority, manual markers, Tap Tempo, optional Audio Synesthesia loudness/onset/Constant-Q overlays, and the Passage-fit solver. A Passage without final music may use a visibly **Unrailed** placeholder duration.

V2 may add reviewed tempo sections, non-uniform bar/beat grids, downbeats, major-change candidates, imported composer MIDI/tempo/cue maps, snap-to-beat, and previewed range fitting. The tempo layer maps onto existing Master frames. It must not replace Cue GUIDs, create an independent clock, or mutate the Cue Score just because analysis completed.

### 8.10 Music-led fit mathematics

First distinguish the durations:

- `T_rail = (RailSourceOutSample - RailSourceInSample) / SampleRate`, the full allowed Rail range;
- `T_coverage = (BindingCoverageOutSample - BindingCoverageInSample) / SampleRate`, the part assigned to this Section;
- `O_coverage` = local Passage start offset of that binding coverage;
- `T_passage` = compiled Passage duration; and
- `T_fit` = camera-travel window used by the solver.

For **Section Music Coverage** authority in V1, the binding requires `O_coverage >= 0` and `T_passage = O_coverage + T_coverage`. In the ordinary one-Rail-per-Passage case, coverage defaults to the Rail's full In/Out range, so the artist-facing label remains **Music In/Out**. When a five-minute Rail crosses a two-minute Passage and continues through a Scene, the Passage binding ends at an explicit two-minute source sample/confirmed marker and derives a two-minute Passage; the following Continue binding begins at exactly that sample. The entire five-minute recording never forces the first Passage to five minutes. **Manual Passage**, **Timeline Boundary**, and **Placeholder/No Music** set `T_passage` from their explicit manual, boundary, or placeholder value and merely report any local-coverage mismatch.

Fit-window policy is explicit:

- **Whole Passage** (default): `T_fit = T_passage`; a positive Rail offset is inside the camera-fit interval.
- **Music Coverage Only:** travel is solved over `[O_coverage, O_coverage + T_coverage)` so `T_fit = T_coverage`; any time outside it must be an explicit camera hold/lead/tail and still lies inside `T_passage`.

**Fit Duration** is available in V1 only for a constant positive manual camera speed, **Whole Passage** fit window, and an explicitly unlocked Manual/Derived Passage duration. It is disabled for a variable speed profile, Music Coverage Only, Music-locked duration, or Timeline-locked duration. Selecting it changes Passage duration to the derived output; it never time-stretches/pitch-shifts the Sound Wave, and the binding reports the resulting numerical coverage mismatch.

Now let:

- `T = T_fit` in seconds;
- `v(t)` = non-negative authored camera-speed profile in metres/second;
- `L = integral[0..T] v(t) dt` = camera travel distance;
- `s` = centre-to-centre Wing Pair spacing;
- `e` and `x` = entry and exit clearances; and
- `N` = Wing Pair count.

The required layout length is:

    RequiredLength = e + (N - 1) * s + x

For constant speed, `L = v * T`. The default clearances are `e = s / 2` and `x = s / 2`. The default derived count is:

    N = 1 + floor((L - e - x + tolerance) / s)

If `L < e + x`, no Wing Pair fits and setup reports an unsatisfied constraint. The remaining distance is explicit:

    Residual = L - [e + (N - 1) * s + x]

Residual policy is selectable: add to exit (default), split between entry/exit, centre stations, or distribute into spacing within a declared tolerance. The status rail always reports residual or mismatch numerically.

Inverse solve rules are explicit:

- **Fit Spacing, `N > 1`, Manual clearances:** `s = (L - e - x) / (N - 1)`.
- **Fit Spacing with both clearances Half Spacing:** `s = L / N`.
- **Fit Spacing with one Half Spacing clearance:** solve the corresponding linear equation and validate positive `s`.
- **`N = 1`:** spacing has no geometric effect; preserve last manual spacing, place the pair after entry clearance, and require `L >= e + x`.
- **Fit constant Camera Speed:** `v = RequiredLength / T_fit`.
- **Fit a variable speed profile:** scale the whole non-negative profile amplitude by `RequiredLength / CurrentIntegral`, preserving its shape and zero-speed holds.
- **Fit Duration at constant speed:** `T_fit = RequiredLength / v`; because V1 requires Whole Passage here, `T_passage = T_fit`.
- **Fit Exit Clearance:** `x = L - e - (N - 1)s`; on Apply, the exit authority becomes **Solved** and the recipe records the generating target/result.

Every inverse solve rejects non-positive/undefined results and makes no partial edit.

For variable speed, compile cumulative distance `S(t) = integral[0..t] v(u) du` as a monotone table/curve. Wing Pair `i` passes when `S(t_i) = e + i*s`; solve `t_i` by deterministic inverse lookup. A zero-speed hold is permitted, negative speed is not in V1, and holds may not create duplicate conflicting anchors.

The example requested in this brief closes exactly:

| Input/result | Value |
| --- | ---: |
| Used music | 240 s |
| Camera speed | 2.5 m/s |
| Travel | 600 m |
| Spacing | 5 m |
| Entry / exit | 2.5 m / 2.5 m |
| Wing Pair count | 120 |
| Average pass cadence | 2 s |

**Reset to Music-Derived Count** restores Fit Wing Count, uses the confirmed Music Rail, current speed profile, persisted last-manual spacing, clearance modes/values, and rounding policy, then previews the row/materialization change. Increasing appends from a chosen placeholder/template. Decreasing may remove untouched generated placeholders only after confirmation. If any affected row has artist edits, Anchors, or dependant world content, Reset is blocked and lists the rows; the artist must explicitly relocate or delete them through ordinary Cue commands before applying the lower count. There is no hidden second “Unplaced Cues” collection. Camera speed is never changed by this reset command.

---

## 9. Wing mechanism motion

### 9.1 Finite score, locally looping mechanisms

Wing motion is a pure function of absolute Passage/Master time and compiled parameters. It must not depend on Tick accumulation or on the frame that happened previously.

Finite describes the Cue Score and route; it does not prohibit local mechanisms from looping. `MotionPlaybackMode` supports:

- **Static** — hold one authored pose;
- **One Shot** — evaluate one pass-relative in/hold/out gesture;
- **Continuous Loop** — repeat throughout the Passage's active span; and
- **Bounded Loop** — repeat between authored activation anchors and hold the configured boundary pose outside them.

Passage defaults normally select Continuous Loop. One Wing Pair cue may pin another mode without affecting its neighbors. The camera never causes logical rows to wrap or restart.

### 9.2 Absolute loop phase and tweened rate

Each looping Wing Pair cue defines:

- phase origin: Passage Start, its Pass Frame, or an explicit frame;
- phase offset;
- cycle rate/duration;
- optional activation interval; and
- closed normalized Left, Right, and Top curves.

For an effective automated rate `r(t)` in cycles per second, compile an unwrapped phase:

    p(t) = PhaseOffset + integral(PhaseOrigin .. t, r(u) du)
    LoopPhase(t) = Frac(p(t))

The curves evaluate at `LoopPhase(t)`. Rate zero holds the current phase. Do **not** use `t / CurrentDuration(t)`: changing the duration would jump phase and visibly pop during a slowdown. The compiler stores or deterministically evaluates the integrated phase curve, including Automation Lane changes.

For a constant rate this reduces to a simple absolute-time phase calculation. Reaching the same frame by normal play, direct seek, reverse, operator segment navigation, stream-out/in, or Movie Render Queue must return the same transform.

One Shot uses a clamped normalized pass-relative window with approach, optional hold, retreat, and rest. Bounded Loop uses the same absolute phase inside its activation range and an explicitly chosen start/end hold pose outside it.

### 9.3 Curve-authored choreography

Left, Right, and Top each have independently editable normalized curves. Loop curves must meet endpoint position tolerance and should meet endpoint tangent tolerance; the validator reports a visible seam.

“Together,” “opposed,” “Left then Right,” “open to closed,” phase waves, and similar choreography are editor presets that fill those curves and phase fields. They are not separate runtime algorithms. Phase-distribution presets may derive offsets by Wing Pair index, route distance, or explicit values, but bake visible editable data.

### 9.4 Motion parameters

Tweenable parameters include:

- resting half-width;
- Left and Right inward travel;
- Top travel;
- loop rate/duration scale;
- phase and phase-distribution amount;
- one-shot pre-pass start offset and hold time;
- local vertical/lateral offset;
- pair yaw/roll;
- curve amplitude;
- optional material parameter; and
- mechanism audio gain/pitch response.

Mesh choice, Actor class, collision policy, and other discrete fields are bulk-fillable but not tweenable. A time-varying loop-rate lane uses the integrated-phase rule in Section 9.2. A Wing-Pair-index lane can instead give successive pairs different constant rates, which is often the desired “the tunnel gradually slows” look.

### 9.5 Resolution order

Effective values resolve in this order:

1. Project defaults
2. Passage defaults
3. Automation lanes in stable priority order
4. Explicitly masked Wing Pair Cue overrides

For rail values, Sections 8.6–8.7 apply instead; Automation Lanes do not modify timing or spacing in V1.

The Details panel displays the source of each effective value. A value inherited from an Automation Lane should show the lane name and a “make local override” action. Multi-edit commands can clear overrides so a range returns to its lanes.

### 9.6 Contribution-aware motion tiers

“Behind the camera” is not by itself permission to stop a pair. Maintain distinct camera-visible, shadow-relevant, reflection/GI-conservative, audio, preload, and reverse-retention relevance tiers.

A pair may enter a lower update or shadow-only tier only when its swept bounds and relevant lights prove that doing so preserves the current image. It may freeze or unload only when it cannot contribute:

- directly visible geometry;
- an in-frame shadow;
- a relevant reflection or global-illumination result;
- audible mechanism sound; or
- a current/previous Transport Segment needed for an allowed reverse move.

When relevance cannot be proved, retain conservatively. Distant visible pairs may use LOD or reduced update frequency, but each actual update samples the exact absolute phase; changing tier or streaming back in never restarts the loop.

### 9.7 Avoiding interpenetration

The compiler estimates panel bounds across the complete swept motion envelope. Validation warns when:

- Left and Right overlap at maximum travel;
- neighboring Wing Pair cues intersect at the route's turn;
- Top intersects side panels;
- the camera, Shadow Figure Rig, or figure envelope intersects a panel;
- a very short gap and long movement create unwanted simultaneous blockage; or
- a route bend makes transverse planes cross.

---

## 10. Bulk editing and automation

### 10.1 Virtualized list

The heterogeneous Show Cue List must use virtualized row widgets. Creating 3,000 data rows must not create 3,000 live Slate widgets.

Shared columns:

- global order/index;
- cue kind;
- enabled;
- label;
- derived Section/Passage;
- global start/time;
- duration/interval summary;
- tags;
- warning status; and
- notes indicator.

Wing Pair columns add local pass time, distance, gap, Left/Right/Top assets, motion/loop summary, and automation/override indicator. Scene columns add Level Sequence, Scene Volume, entry/exit camera, trim, camera owner, and readiness. Irrelevant cells display blank rather than misleading defaults.

Columns are reorderable, hideable, and saved per user.

### 10.2 Selection behavior

- Click selects one row.
- Shift selects a contiguous range.
- Command/Ctrl adds individual rows.
- Range ruler selection and list selection stay synchronized.
- Viewport selection of a previewed wing selects its source row.
- Multi-selection Details shows common values, mixed values, and explicit bulk-apply checkboxes.
- Mixed-kind selections show shared editorial fields only; kind-specific edits require an explicit compatible subset.
- Filtering never changes underlying order.

### 10.3 Tags and Cue Ranges

Tags may include any non-contiguous set of cues and are used for filtering, search, and bulk selection.

An explicit wing Cue Range is contiguous inside one Passage Span and anchored by start/end Wing Pair Cue GUIDs. Cue Ranges support:

- collapse/expand;
- select range;
- duplicate or repeat range;
- color;
- notes; and
- timing/spacing summary.

Cue Ranges are organizational spans, not reusable design definitions and not runtime loops. Filtering never silently changes their endpoints.

### 10.4 Automation editor

Automation appears in a lane area aligned with the selected Passage Span ruler. It provides:

- range handles snapped to Wing Pair Cue GUIDs or frames;
- curve editor;
- parameter/unit labels;
- resolved-value ghost curves;
- mute/solo;
- priority ordering;
- overlap warnings;
- bake to Wing Pair Cue overrides;
- restore/unbake;
- copy/paste lanes; and
- a preview readout at the playhead.

Lane ranges anchored to Wing Pair Cue GUIDs remain attached when other rows are inserted before them. Frame-anchored lanes remain fixed to passage/music time. An Automation Lane may not silently cross a Scene cue; a structural split truncates, duplicates, or cancels the lane according to an explicit preview choice. The UI always shows anchor mode.

An adjacent Event lane displays Passage Events for narration beats, Puss glances, music markers, and manually authored scenic encounters. Events may snap to Wing Pair cues or time without becoming Cue Score rows.

### 10.5 Common recipes

Provide one-click recipes that create ordinary visible data:

- mechanism slowdown/speedup creates a Loop Rate/Duration Scale Automation Lane with integrated phase;
- passage/camera slowdown uses a transactional retiming preview and writes intervals;
- widen/narrow aperture;
- increase/decrease wing travel;
- fade mechanism gain;
- lift/lower a range;
- stagger phases;
- distribute pass times evenly;
- distribute gaps evenly;
- fit selection to duration;
- fit selection to distance; and
- interpolate between first and last selected values.

Recipes must not hide generated rules. They produce visible lane data or visible per-row edits; timing and spacing recipes never create a self-referential runtime lane.

### 10.6 Scene insertion, split, deletion, and merge

Structural Cue Score edits have a dedicated preview:

- **Insert Scene in Passage:** split the span; choose which side retains the original `PassageSpanGuid`, duplicate or reset defaults/audio/automation, create/fit a route for the new side, and create two Camera Handoffs.
- **Delete/move Scene between Passages:** merge spans; choose one route/settings source or create a new combined route, resolve overlapping lanes/ranges, and remove/retarget Handoffs.
- **Move Wing Pair across Scene:** update both span boundaries, local pass rails, Anchors, Transport ranges, and compiled subsections.
- **Change Cue kind:** only through an explicit conversion wizard showing discarded/incompatible payload fields; never by editing the enum cell casually.

Every operation is atomic and fully undoable.

### 10.7 Undo and data safety

Every authoring command uses Unreal transactions and supports one-step undo/redo. A bulk command should be one transaction, not thousands of undo entries.

Before destructive import, delete, bake, or “replace all” operations, show:

- affected cues and Passage Spans;
- row count;
- range;
- fields;
- whether manual overrides will be lost; and
- a preview/diff where appropriate.

---

## 11. Route and spline system

### 11.1 Coordinate frame

At distance `s` along the route:

- tangent = forward;
- transported right = stage lateral;
- stage up = vertical reference;
- the wing-pair plane is transverse to the tangent.

Use a stable-up or parallel-transport frame so helices and long curves do not develop sudden roll flips. Following authored spline roll is opt-in; keeping wings vertically staged is the default.

### 11.2 Route modes

#### Straight

A generated straight route of exactly the compiled required length.

#### Serpentine

Generated from:

- target footprint;
- lateral amplitude;
- minimum turn radius;
- segment/turn count;
- entry/exit straight lengths; and
- optional vertical separation.

The generator solves or extends the route to the required arc length.

#### Helix

Generated from:

- radius;
- pitch/vertical rise per turn;
- turn count or maximum height;
- handedness;
- entry/exit straight lengths; and
- clearance envelope.

A flat spiral is not the default because adjacent coils can enter the camera frustum. A helix or well-separated serpentine provides better visual isolation.

#### Normalized Custom

The artist edits a custom spline shape whose longitudinal control positions are normalized to passage progress. When the required length changes, the solver preserves the authored lateral/vertical character while adjusting longitudinal span and reparameterizing by arc length.

The editor must show before/after footprint and warn if the requested length cannot be achieved under pinned points or minimum-radius constraints.

#### Manual Absolute

The artist draws an ordinary absolute spline. Its geometry is never silently rescaled. If content becomes longer than the route, validation offers:

- extend along the end tangent;
- add a straight tail;
- fit Wing Pair gaps into the existing length;
- convert to Normalized Custom; or
- leave unresolved.

### 11.3 Length policy

Generated and Normalized routes use **Passage Span Determines Length** by default. Manual Absolute routes use **Spline Determines Capacity**.

Required route length equals:

    lead-in distance + Wing Pair gaps + tail distance

The route may contain extra reserve length. The UI displays Used / Available / Reserve.

### 11.4 Editing

An `AInfinityStagePassageActor` contains the editable `USplineComponent`, but serialized route points live in the owning `FInfinityPassageSpan` in the Show Asset. The Actor registers by Show GUID + Passage Span GUID. A custom component visualizer:

- writes route edits transactionally;
- shows Wing Pair stations;
- shows camera direction and current visible/shadow/audio contribution ranges;
- shows panel bounds and motion envelopes;
- shows entry/exit cameras;
- shows anchor references;
- colors invalid turns/clearance; and
- can isolate one cue range.

### 11.5 Validation

Route validation covers:

- insufficient length;
- degenerate or zero-length segments;
- excessive curvature;
- orientation/up-vector flips;
- non-adjacent segment proximity;
- wing-envelope overlap;
- camera, Shadow Figure Rig, and figure clearance;
- unintended views into another coil or spatial zone;
- floor/ceiling bounds;
- angular velocity and camera comfort;
- World Partition/Data Layer bounds; and
- entry/exit straight length needed for framing.

### 11.6 Recommendation for PussStage

Do not begin with one spline for the entire 45-minute work. Begin with one route per derived Passage Span visible in the script. Every Scene cue terminates the incoming route and permits the following span to begin elsewhere. Place those routes:

- in separate spatial bays; or
- at shared coordinates under mutually exclusive Runtime Data Layers.

Use the main scenes and interludes as editorial/world-loading boundaries. Only introduce a helix or stronger serpentine within a passage whose required length genuinely exceeds its available footprint.

---

## 12. Camera, traveling Shadow Figure Rig, and manual anchors

### 12.1 Camera rig

Each Passage Actor, keyed to one Passage Span, owns or resolves:

- a Cine Camera;
- passage spline reference;
- camera distance evaluator;
- lateral and height offsets;
- look-ahead distance;
- yaw/pitch/roll offsets;
- optional look-at target;
- lens, aperture, focus, and sensor settings;
- camera shake/noise layers outside the core distance calculation; and
- entry/exit pose markers.

Camera transform is evaluated from absolute Passage frame. The camera may follow the tangent, aim at a look-ahead point, or blend to a named transition target.

### 12.2 Traveling Puss-and-Boy Shadow Figure Rig

Puss on the physical stage is a real robot dog and is outside this plugin's control. The plugin does not simulate, drive, track, or synchronize that robot.

In Unreal, each Passage camera may own `AInfinityStageShadowFigureRig` or an equivalent component. It is evaluated from the same absolute Master/Passage time as the camera and contains an ordered array of figure definitions, initially Puss the cat and the Boy:

- soft mesh/rig/animation reference and semantic role;
- offset behind, lateral to, and above/below the camera;
- scale and local rotation;
- orientation mode: camera-relative, route-relative upright, or world-upright;
- cast-shadow policy;
- main-pass, reflection, ray-tracing, and lighting-channel policy;
- optional artist Sequencer binding; and
- deterministic route velocity and walk-phase outputs.

Position follows the camera/path, but orientation need not inherit camera pitch or roll. Figure animation remains artist-authored; the rig exposes inputs and bindings but does not select a walk cycle.

By default the incoming Passage's figure rig deactivates at the Scene camera handover, and the outgoing Passage's rig activates at handback. A Scene may explicitly bind and animate a rig of its own, but camera ownership must never leave two unintended Puss/Boy shadow rigs active at once.

Do not assume that hiding a figure from the main pass preserves its shadow on every renderer/material path. Phase 0 must prove the selected shadow-only policy with production masked materials, Virtual Shadow Maps/ray tracing settings, reflections, and Movie Render Queue. If that content path cannot cast an invisible shadow reliably, keep the geometry physically behind/outside the view and surface the fallback in validation.

### 12.3 Attachment anchors

`AInfinityStageAttachmentAnchor` supports:

- Show + Passage Span + registered Passage Actor reference;
- reference mode: Wing Pair Cue GUID, passage frame, absolute distance, or normalized progress;
- socket: Center, Left, Right, Top, Before, After;
- local transform;
- follow route roll yes/no;
- editor-only label/color;
- orphan handling; and
- optional child-activation callbacks.

Anchor lookup is GUID-based and indexed. It must never depend on cue array index or Actor label.

Deleting a Wing Pair cue with Anchors produces a warning and offers:

- rebind to previous;
- rebind to next;
- convert to absolute distance;
- leave orphaned; or
- delete Anchor only with explicit confirmation.

### 12.4 Manual content ownership

The plugin may reposition the Anchor transform. It must not:

- duplicate attached artists' Actors;
- change their light settings;
- change their animation;
- replace their materials;
- rename them for identity; or
- remove them during a passage rebuild.

---

## 13. Sequencer architecture

### 13.1 Hierarchy

Use three scales:

    Master Show Level Sequence
      -> one subsection per Passage Span or Scene/Sequence cue
          -> ordinary camera, animation, audio, FX, and plugin passage track

The Master Sequence contains only macro sections, typically the opening, six passages, story scenes/interludes, transitions, and ending. It never contains thousands of wing subsections.

### 13.2 Native Passage track

Implement native C++:

- `UMovieSceneInfinityPassageTrack`
- `UMovieSceneInfinityPassageSection`
- track editor integration; and
- evaluation system/entity components appropriate to UE 5.8.

The section references a Show Asset + Passage Span GUID and a resolved Passage Actor/rig. At any local `FFrameTime`, it submits an absolute evaluation request keyed by root sequence/player instance, sequence instance, managed section GUID, Span GUID, and operand—not by one global “active Passage.”

Do not base production playback on the Blueprint Customizable Sequencer Track beta. A native track is justified because seekability, Movie Render Queue, pre-animated state, hierarchy bias, and deterministic evaluation are core requirements.

### 13.3 Persistent managed Passage sequence

The builder creates or maintains a persistent mixed-ownership Passage Level Sequence containing:

- one managed Passage track/section;
- a binding to the Passage Actor/rig;
- a camera binding and Camera Cut Track;
- optional local guide/audition metadata, but no independently auto-playing copy of defining music by default;
- named markers for important passage/cue events;
- managed folders/tracks tagged with plugin metadata; and
- untouched space for artist-authored tracks.

Rebuild updates only plugin-owned objects identified by a serialized `UInfinityStageManagedDecoration` on each managed Track/Section. The decoration carries Owner GUID, Show GUID, derived Section GUID, Passage Span GUID, managed role, and build-schema version. Display names, object signatures, and array positions are not ownership identity.

The builder never deletes an unknown/user track because its display name resembles a generated name. If a child Passage is explicitly configured to own a local guide track, manual edits to that managed track are drift and offer **Restore from Music Rail** or **Adopt into Music Rail**. The normal live path uses the Master music rail so physically separate Passage zones cannot acquire competing playback authority.

### 13.4 Master builder

The persistent mixed-ownership Master builder:

- partitions the ordered Cue Score into Passage Spans and Scene/Sequence Sections;
- reads Camera Handoff records;
- creates/updates one subsection per included derived Section, never per Wing Pair;
- creates/updates one plugin-managed standard Master Audio Track from all authoritative Music Rails and declared continuations/crossfades;
- sets exact frame ranges and trims;
- sets MovieScene evaluation pre-roll/post-roll separately from source handles and streaming readiness leads;
- sets Section colors/names/markers;
- retains stable subsection identity across rebuilds;
- reports gaps/overlaps;
- hashes the result;
- preserves all non-managed tracks; and
- can adopt manual section timing only through an explicit command.

Passage duration comes from its compiled timeline. Sequence-section duration comes from its source sequence playback range or an explicit trim policy. The same managed Decoration contract protects plugin-owned Master objects; global user tracks remain artist-owned.

MovieScene evaluation pre-roll may resolve assets, evaluate a hidden preparatory pose, or warm a managed system. While `IsPreRoll`/its UE 5.8 equivalent is true, a Section may not acquire Camera Cut authority, start or seek defining music, or emit mechanism transients. World/audio loading deadlines are instead expressed by `LoadLeadFrames` in Master time, and reverse retention by `RetentionTailFrames`; source edit flexibility remains `SourceHandles`. These three concepts must not share one field or UI label.

### 13.5 Shots versus subsequences

Use ordinary nested Level Sequences as the structural primitive. A child sequence may own its Camera Cut Track and internal Shots. The Master should not flatten scene shots.

If production benefits from a Shots Track at the top level, the builder may represent camera-bearing Sections as Shots, but this must not create one asset per wing or duplicate artist-authored scene internals.

### 13.6 Camera handoff

Every adjacent pair of camera-bearing Sections resolves through the one `FInfinityCameraHandoff` record defined in Section 7.4:

- previous exit frame/camera;
- next entry frame/camera;
- cut frame;
- transition type;
- available source handles;
- transform tolerance;
- lens/sensor tolerance;
- focus tolerance;
- aim/target tolerance; and
- preload deadline.

The normal Passage → Scene → Passage cycle is explicit:

1. The incoming Passage camera owns the approach and settles into the establishing framing.
2. At the exact entry Handoff frame, the Scene's establishing camera/Camera Cut Track takes ownership.
3. The Scene owns its internal cuts and shot sequence.
4. Its closing shot arrives at the captured outgoing pose.
5. At the exact exit Handoff frame, the next Passage camera takes ownership and begins its route.

The Scene interval may conceal a complete spatial discontinuity between the two Passage splines. Camera ownership is compiled as an absolute-time interval, so reverse playback and direct seek choose the same owner without replaying a mutable handoff action.

For V1, macro subsections may not overlap. A deliberate visual transition is an explicit artist-authored Transition Sequence cue placed serially between its neighbors; it alone owns the Camera Cut during its interval. Its source may use handles captured from either side, but the neighboring child Camera Cut Tracks are not evaluated concurrently. Validation rejects any overlapping macro subsection or simultaneous child Camera Cut authority. Hierarchy-bias/blend arbitration for genuinely overlapping subsections is deferred.

Tools:

- capture current frame as Entry/Exit Pose;
- copy optics;
- match world transform;
- match screen-space target;
- A/B preview;
- onion-skin or split-view comparison where practical; and
- validation report.

### 13.7 Playback modes

Required:

- editor scrub;
- Sequencer play;
- PIE Level Sequence playback;
- reverse visual evaluation;
- arbitrary jump;
- live/rehearsal operator transport;
- Movie Render Queue (Unreal's offline/high-quality image/movie renderer); and
- cooked playback.

Required live controls:

- play forward to the current/next segment boundary and hold exactly there;
- play reverse to the current/previous segment boundary;
- pause/resume;
- seek or shuttle at an allowed rate;
- jump to current segment start/end;
- select/jump Previous and Next Segment; and
- surface readiness/fail-safe state before changing time.

### 13.8 Transport controller and input adapters

`UInfinityStageTransportController` wraps the same root `ULevelSequencePlayer`; it never advances a private wing/cue clock. Forward/reverse play and Previous/Next jumps are separate commands so the final button semantics can be chosen artistically without changing runtime architecture.

Status APIs expose:

- selected/current Transport Segment GUID and label;
- exact Master frame and local Section frame;
- direction, rate, playing/paused/held state;
- current camera owner;
- previous/current/next readiness; and
- clock-safety or load error.

Blueprint/C++ command and status APIs are required first. Keyboard, OSC, MIDI, Stream Deck, or a custom operator panel are adapters and must not contain show state.

In rehearsal mode, arbitrary seek and reverse are allowed under the audio scrub/reverse policy. In performance mode, hold, rewind, or rate change is allowed only when music/timecode is controlled by the same Master player. If an external source cannot pause or reverse, those commands are disabled rather than allowing picture/music drift.

---

## 14. World and section organization

### 14.1 World-content adapters

V1 uses one **Unified Infinity Show World** so the complete production behaves like one real theatrical installation. Passages and Scenes normally occupy separate physical bays; all fixed Passage wings, grounds, cameras, Scene sets, manual lights, props, and registered content can be inspected together in the Level Editor.

Per-Section worlds remain an import, development, or offline-render fallback, not the primary live architecture. A single real-time Master Sequence cannot assume possessable bindings across unrelated unloaded maps without a separately engineered world bridge.

### 14.2 Data Layers and Level Instances

Each derived Section, through its Passage Span settings or Scene/Sequence cue payload, may reference:

- a Runtime Data Layer;
- a Level Instance;
- a spatial zone; or
- none, if its content is always available.

The default V1 authoring and PIE profile keeps the whole fixed stage resident. Runtime Data Layers and World Partition are optional optimizations for a profiled production build, never prerequisites for seeing or editing the stage.

Passage Actors, persistent Wing Chunk Actors, camera rigs, Show Root, Ground Zone registrations, and Scene Volumes self-register by Show/Passage Span/Scene/Cue/Chunk GUID. The Show Root and camera/transport infrastructure remain always loaded and non-spatial. A replaceable/custom binding may resolve registered Actors after an optional Data Layer activation. Actor-label rebinding and hard cross-cell Actor references are not acceptable production identity because they are ambiguous and may accidentally bundle streamed content.

Use Outliner folders for permanent human organization, Editor Data Layers to isolate a bay while dressing, and Actor Editor Context so newly placed lights/props/ground enter the selected Passage or Scene context. All Sections Visible remains the default authoring preset.

### 14.3 Streaming

Provide:

- a **Fixed Resident** default in which serialized stage content already exists before playback;
- an optional camera-lookahead streaming source for serialized chunks/Data Layers;
- configurable `LoadLeadFrames` before a Section boundary and `RetentionTailFrames` after it, both measured on the Master timeline;
- asynchronous per-chunk asset/audio preload manifests where optional streaming is enabled;
- bidirectional previous/current/next retention for operator transport;
- “ready to cut” state;
- editor warning when the next Section cannot be made ready in time; and
- deterministic readiness policy.

Absolute show time never slips silently to accommodate loading:

| Mode | Readiness policy |
| --- | --- |
| Editor seek/preview | Load, then evaluate the requested fixed frame. |
| Movie Render Queue | Warm/load before rendering the frame range; waiting does not advance rendered show time. |
| Fixed real-time/music playback | Preflight and preload by the boundary deadline. A miss is an explicit failure/fail-safe; the scheduled cut is not delayed. |
| Live/rehearsal transport | Prepare the target before the command. A Hold may pause the whole authoritative clock only if music/timecode is paused by the same authority; a not-ready jump/reverse leaves time unchanged. |

The real-time failure policy—abort, safe black/curtain fallback, or scheduled cut with a surfaced error—is chosen per Show/boundary. External unpausable music forbids a local late hold.

Optional streaming loads fixed serialized packages; it never constructs Wing Pair rows, chooses assets, creates instances, or repairs a stale stage at runtime. Fixed Resident and streamed profiles must render equivalent frames. A missing materialized chunk is an explicit error.

`LoadLeadFrames` is a readiness deadline, not hidden extra show duration: loading may begin while the prior serial Section is active, but the target Section cannot take camera/music authority early. `RetentionTailFrames` keeps the prior serialized content available for reverse/jump policy without extending its Camera Cut or music interval. MovieScene evaluation pre-roll and source handles are separate concepts defined in Sections 7.3 and 13.4.

### 14.4 Spatial reuse

Two Passage routes may occupy the same world coordinates if:

- they live in mutually exclusive Data Layers;
- their Actors/bindings are distinct and stable;
- the next route is loaded without revealing it;
- readiness passes before the fixed cut frame; and
- world audio/lighting does not leak between layers.

This can substantially reduce the physical footprint while retaining finite authored data, but it conflicts with viewing all overlapping Sections simultaneously. It is therefore opt-in only after a first-frame activation, reverse-readiness, shadow/reflection, ground, audio, and lighting-isolation test. Separate bays remain the production default.

A Scene cue is the preferred place to conceal activation of another bay or reuse of the same coordinates. Its establishing and closing shots create the camera-language bridge, while the Camera Handoffs keep the world switch and view owner exact in forward, reverse, and direct-seek evaluation.

### 14.5 Persistent editor materialization

“Not generated” means **not procedurally created during playback**. The Cue Score still needs an editor-time materialization step so several thousand logical rows can become efficient serialized map content.

The normal representation is:

1. one persistent `AInfinityStagePassageActor` per Passage, owning route, camera rail, metadata, and chunk registry;
2. persistent `AInfinityStageWingChunkActor` objects for stable distance/GUID ranges, normally around 64–128 pairs after profiling; and
3. optional persistent `AInfinityStageWingPairActor` Hero promotions for exceptional pairs.

Within each chunk, repeated instance-compatible render keys use moving ISM components. Unique or instance-incompatible panels use child Static Mesh Components within that chunk; they do not force one Actor per pair. Manual lights/props use stable Anchors because an ISM index is not durable identity.

The materialization service performs an incremental transactional diff and never runs in Construction Script, on every property keystroke, on map open, or at BeginPlay. Preview motion is transient and restores the canonical editor pose before save. PIE's normal duplication of the Editor World into a Play World is an Unreal mechanism, not plugin generation. In **Fixed Resident** mode, plugin Actor/component/instance counts must otherwise match immediately before and after BeginPlay. In optional serialized-stream mode, unloaded content is validated through cooked Actor descriptors/packages, Runtime Data Layer membership, and the materialization manifest; each chunk is checked against that manifest when loaded, without plugin-side construction.

### 14.6 Show Root, sound player, and Level Blueprint boundary

Initialization places exactly one `BP_InfinityStageShowRoot`, derived from `AInfinityStageShowRoot`. It is visible in the Outliner and contains or references:

- the Show Asset and placed Master Level Sequence Actor;
- the single root Level Sequence Player/transport controller;
- camera-authority coordinator;
- `UInfinityStageMusicDirectorComponent`, which owns Rail readiness/status, output-token arbitration, and editor audition while the one root Sequence Player's managed Master Audio Track produces show playback;
- mechanism-audio pool and show bus/submix routing;
- registry/readiness state for persistent Passage, Scene, Chunk, Ground, camera, and Shadow Figure objects; and
- optional World Partition streaming-source component.

Any audition/fallback audio component defaults `Auto Activate = false`; child sequence Actors default `Auto Play = false`. Duplicating a Show Root leaves the copy disabled until assigned a different Show, and two active roots for one Show are an error. The placed Show Root plus Master Level Sequence Actor constitute the requested map-visible sound player; setup must not also place one autonomous Ambient Sound per Section.

Core playback must not be implemented in the Level Blueprint. A venue-specific Level Blueprint may resolve the Show Root and call public Prepare/Transport APIs for external hardware or emergencies. It may not play section music directly, advance another sequence clock, or call `SetViewTarget` while Camera Cuts own the view.

### 14.7 Ground Zones

There is no requirement for one giant ground Actor. A Show may combine modular Static Mesh floors, spline-deformed strips, independent Landscapes, terrain meshes, Level Instances, decals, foliage, and manual dressing.

Each artist-owned `AInfinityStageGroundZone` registers identity, Section ownership, optional route range, bounds, strategy, folder/Data Layer, Follow Route versus World Locked state, and transition policy. Recommended uses are:

- wood/concrete/theatrical deck: modular meshes or a spline strip;
- forest/soil: independent Landscape or terrain mesh plus foliage/dressing;
- reusable Scene set/floor: Level Instance;
- locked dense static dressing: optional Packed Level Actor; and
- a cut-concealed change: completely independent Ground Zones in separate bays.

Ground is never rewritten after promotion to World Locked. Route/spacing edits instead mark affected Ground Zones stale and preview coverage/seam problems. Validation checks route coverage, camera/Shadow Figure surface intersection, wing penetration, visible edges/seams, wrong Data Layer/folder, unintended simultaneous grounds, and whether an establishing/closing shot exposes a disconnected bay edge.

---

## 15. Runtime evaluation and rendering

### 15.1 Runtime subsystem

A `UInfinityStageWorldSubsystem` is the single runtime service, but it owns an evaluation-context map keyed by root sequence/player instance, sequence instance/operand, managed Section GUID, and Passage Span GUID where relevant. This allows editor preview, PIE, MRQ, live transport, and nested evaluation to coexist without sharing one mutable “active Passage.” For each context it:

1. resolves compiled Show, Section, Passage, and camera-authority data;
2. receives absolute Master/sequence frame;
3. maps to local time and evaluates camera distance/pose;
4. binary-searches the contribution-relevant cue/spatial range;
5. evaluates exact loop/gesture transforms for relevant Wing Pair cues;
6. updates existing persistent render batches/components and visibility/update tiers;
7. updates manual Anchor transforms;
8. schedules/prioritizes mechanism audio;
9. evaluates the traveling Shadow Figure Rig; and
10. restores pre-animated state when the Passage section stops.

No per-cue Tick is allowed.

The subsystem never creates the fixed stage. In Fixed Resident mode, PIE start verifies and registers every serialized Show Root, Passage/Chunk/Hero/Camera/Shadow/Ground object against the materialization manifest. In optional serialized-stream mode, startup verifies always-loaded coordinators plus cooked Actor descriptors/packages, Runtime Data Layer membership, and per-chunk manifests; a chunk's live objects are registered and checked when its serialized package loads. Missing/stale descriptors, packages, or loaded-chunk members fail visibly instead of triggering reconstruction.

### 15.2 Renderer

Normal panels are grouped by a render key including:

- Static Mesh;
- material overrides;
- shadow/collision/mobility policy;
- Nanite/instance compatibility;
- required custom-data layout; and
- render layer.

Use `UInstancedStaticMeshComponent` for repeated moving or Nanite-compatible render keys unless profiling proves another representation better. Use HISM only for genuinely static, suitable groups. Unique or non-instance-compatible panels use persistent child `UStaticMeshComponent`s inside their Chunk Actor, or a persistent Hero Actor when independent authoring is required; contribution tiers bound their update cost rather than their authored existence.

In the required Fixed Resident profile, these ISM/Static Mesh Components and Hero Actors are persistent serialized children of Chunk/Passage Actors and exist before PIE. Runtime contribution tiers may freeze, hide, lower update frequency, or optionally stream fixed chunks, but they do not allocate the stage on demand. Enforce configurable hard budgets for persistent Chunk Actors, ISM components, fallback Static Mesh Components, Hero Actors, and unique render keys.

Component and draw-call cost cannot be made independent of content uniqueness. If nearly every photographic panel has a different mesh/material render key, the component count will approach that uniqueness. The editor reports this honestly and Phase 0 profiles the real library. Possible later optimizations include greater asset reuse, shared cutout planes with texture-array selection, or a specialized multi-mesh renderer; the specification must not promise ISM batching for incompatible assets.

Phase 0 must test the real photographic wing materials, especially masked versus translucent rendering, per-instance custom data, shadowing, and translucency sorting. If a material cannot render correctly in an instance batch, the compiler must choose an explicit fallback render path and report its cost. Prefer production cutout materials that are instance-compatible where their required visual quality permits it.

### 15.3 Persistent chunks and contribution windows

The compiled route is divided into stable persistent chunks by distance/GUID range. Chunk size is profile-driven, not hard-coded into authored assets, and boundaries avoid “every Nth row” cascading churn after an insertion. Each chunk owns its render-key table, Cue/side lookup, persistent component set, and optional preload manifest.

Maintain:

- preload window ahead;
- camera-visible geometry window;
- shadow-relevant light/frustum window, including a conservative tail behind the camera;
- reflection/GI-conservative window;
- audio window;
- previous/current/next Transport Segment retention window; and
- editor preview contribution window.

Compile swept motion bounds per Wing Pair cue and aggregate them per chunk. Evaluate light/frustum contribution primarily at chunk/batch level, not through thousands of Actors. An artist **Force Shadow Active** override is available for exceptional rows/ranges where automatic relevance cannot capture the intended lighting.

A visually culled pair may still use a shadow-only/lower-update tier. It may freeze or an optional serialized chunk may unload only after geometry, shadow, reflection/GI, audio, and reverse-retention relevance all end. Visual loops may continue while their mechanism audio is voice-limited. Any tier or serialized-streaming change samples exact absolute phase and cannot restart motion.

The renderer can reuse component/instance capacity, but it must never wrap logical cue identity. A streamed Wing Pair always resolves to its one finite Cue GUID, time, distance, design, and absolute loop phase.

This is deterministic contribution management over a fixed stage, not a return to the old carousel.

### 15.4 Assets and loading

- Use soft asset references in authored data.
- Compile per-chunk preload sets plus a small Section-level manifest.
- In Fixed Resident mode, ensure references are cooked and ready before performance; in the optional streamed profile, begin async loads by the Section's Master-time `LoadLeadFrames` deadline.
- Define Primary Asset cook rules.
- Avoid synchronous loads in the per-frame evaluator.
- Warn when unique mesh/material combinations eliminate useful batching.
- Never require editor DDC in a cooked build; compiled blobs and the materialized map content are serialized/versioned for cook.

### 15.5 Collision

Default photographic wing panels to No Collision. Permit explicit opt-in collision only for special rows/hero Actors.

The camera/Shadow Figure Rig clearance validator uses swept bounds, not runtime physics, as the normal safety check.

### 15.6 Determinism

For a given:

- Show Asset/Passage Span revision;
- sequence frame;
- world transform;
- random seed used only for audio clip choice; and
- asset set,

the visual evaluation result must be identical regardless of playback history.

---

## 16. Audio and music

### 16.1 Section Sound panel

Every derived Show Section exposes a Sound panel through its Passage Span header or Scene/Sequence cue.

For a Passage, the panel edits its Section Music Binding and referenced Show Music Program Rail inline and owns the full mechanism system described below. The Rail itself remains Show-owned so it may continue across a Scene without duplication; local coverage/boundary policy remains on the binding.

For a Scene, Interlude, or Transition, the referenced Level Sequence remains authoritative for its internal sound design. The Section panel controls only its outer guide-track reference, gain, mute/solo, submix/bus, fade-in/out, boundary crossfade, and notes unless the artist explicitly opts into deeper managed control. The Master builder must not rewrite an artist's internal audio tracks.

#### Music rail

- concrete Sound Wave asset slot with drag/drop and Unreal Import Audio command;
- source duration/sample rate/channels plus exact source In/Out sample handles;
- reference-only versus final-output flag;
- Passage/show offset and exact sample-to-frame mapping;
- gain, mute/solo, and optional submix/send;
- fade-in/fade-out durations and linear/log/equal-power/custom curves, editable numerically and on the waveform;
- duration authority and numerical music-versus-Passage/camera mismatch;
- waveform, manual markers, analysis suggestions, accepted Music Map, and stale-analysis/fit state;
- 2D/non-spatialized playback by default;
- seek/compression/readiness diagnostics; and
- notes.

Unreal's normal importer accepts WAV and MP3 among other formats. Recommend 48 kHz, 16-bit WAV for final performance files and allow MP3 for drafts/rehearsal. Imported assets become `USoundWave`s; replacing a draft MP3 with final WAV invalidates the fingerprint and requires duration/marker/sync review rather than an automatic refit.

Show-critical trimmed/seeked rails must use a seek-capable codec/settings profile. Prefer streamed Bink Audio for long performance tracks and allow PCM for short diagnostics where memory permits. Reject Platform Specific compression for a Rail whose Sequencer section must seek/trim if the selected platform path does not support seeking. Validation offers an actionable asset-settings fix and Phase 0 measures seek/resume error on every shipping platform/codec profile.

#### Mechanism profile

- sound pool or MetaSound;
- separate optional open/close/reversal categories;
- base gain;
- pitch/rate mapping;
- movement-speed response curve;
- attenuation;
- concurrency;
- maximum pooled voices;
- priority by distance/loudness;
- deterministic seed;
- trigger and release thresholds;
- direction-change behavior;
- per-side/Top routing; and
- preview mute/solo.

Separate Left/Right/Top routing is new behavior. The old plugin used one Pair-level source driven by the greatest measured displacement among its mechanisms.

#### Ambience/mix

- optional ambience references;
- section bus/submix;
- control-bus or mix state;
- fade in/out;
- output notes; and
- links to artist-owned Sequencer tracks.

### 16.2 Deterministic mechanism audio

Do not give every Wing Pair cue a permanently ticking audio component.

The compiler derives one-shot schedules and repeating loop event patterns from authored motion curves. For loops, each event is identified by unwrapped phase, cycle index, side, and curve marker rather than by expanding thousands of events into authored data. At runtime a pooled spatial audio manager:

- evaluates scheduled start/reversal/stop events as well as the motion curve and derivative;
- identifies audible active mechanisms;
- prioritizes nearest/loudest events;
- allocates a bounded Audio Component pool;
- positions sources at Left/Right/Top anchors;
- selects clips deterministically;
- applies gain/pitch response; and
- releases voices cleanly.

Visual evaluation is stateless, but audio playback state is keyed by the same sequence-player/root-instance and Passage-section context used by visual evaluation. The scheduler:

- fires events crossed in `(PreviousFrame, CurrentFrame]` only during forward, contiguous Playing;
- treats MovieScene evaluation pre-roll as preparation only: it may establish a hidden pose or preload data but cannot emit a start, reversal, stop, or loop transient;
- suppresses historical transients and resets sustained state on seek, scrub, jump, or discontinuity;
- cannot miss start/reversal events merely because a frame was dropped;
- derives crossed loop events from unwrapped phase/cycle index, without duplicating them after a reverse/forward change;
- sorts equal-priority candidates deterministically by configured priority, distance, then Cue GUID;
- applies voice-steal hysteresis and short release fades; and
- derives listener/priority position from the evaluated CineCamera/active Camera Cut, not an assumed PlayerController listener.

Initial mechanism sync is frame-accurate. Sample-accurate claims require a later Quartz/MetaSound scheduling path.

The old plugin's user-facing idea—squeaks and creaks that follow eased physical movement—is worth retaining. Its per-component measured-displacement implementation should be rewritten around authored absolute-time curves for scale and determinism.

### 16.3 Scrub and reverse policy

- Visual motion evaluates during all scrubs and reverse playback.
- Scrubbing does not spray transient sound by default.
- An explicit **Scrub Audio Preview** mode may audition bounded snippets.
- Reverse visual playback does not automatically reverse audio assets.
- Operator backward shuttle uses the same policy: by default it suppresses mechanism transients and does not play music backwards; on landing, sequence-owned music is sought to the authoritative frame.
- A final performance reverse policy remains configurable when the music/sound design is known, but it may never allow an independent audio clock to drift silently.
- Movie Render Queue and forward Sequencer playback use the deterministic scheduled behavior.

### 16.4 Music integration phases

#### V1 — reliable Music Rail

- WAV/MP3 import through Unreal and a concrete Sound Wave source;
- waveform, exact In/Out, fades, gain, audition, and manual markers;
- Section Music Coverage as the default Passage-duration authority (shown as Music In/Out when coverage equals the Rail's full used range);
- speed/spacing/clearance/count constraint solver and inline count reset;
- generated plugin-managed standard Sequencer Audio Track;
- one Show Root music router with exclusive ownership;
- deterministic play/pause/seek/jump reconstruction from Master time;
- ordinary single-owner boundaries plus explicitly declared two-section crossfades;
- source-hash/stale-fit validation;
- optional Audio Synesthesia loudness, onset, and Constant-Q suggestion overlays;
- manual BPM, Tap Tempo, and Set Downbeat; and
- a modular music-analysis provider interface.

#### V2 — reviewed musical intelligence

- evaluated tempo/beat/downbeat and major-change provider;
- time-varying/non-uniform tempo maps;
- composer MIDI/tempo/cue-map import;
- bars/beats ruler, snap, and manual grid correction;
- previewable creation of Events, Cue Ranges, and automation boundaries;
- previewed fitting of selected pass anchors within camera-speed/gap limits;
- advanced transition authoring and output-latency calibration; and
- optional Quartz/MetaSound/Harmonix-backed precision adapter only after stability testing.

### 16.5 Assisted music analysis

A useful and genuinely sophisticated assistant is feasible, but a universally correct automatic interpretation is not. Percussive fixed-tempo music is tractable; rubato, ambient sections, mixed metre, long fades, silence, dense mixes, and half/double-tempo ambiguity require artist judgment. The product language is therefore **Analyze and Review**, never “auto-choreograph.”

Native UE 5.8 Audio Synesthesia NRT can provide saved editor-time loudness, onset timestamps/strengths, and Constant-Q spectral bands. These are suitable for energy, attack, density, and some change evidence, but they are not by themselves a reliable BPM/downbeat/formal-section detector. Quartz schedules musical events; it does not analyze arbitrary recordings.

Define an editor-only modular `IInfinityMusicAnalysisProvider` that receives decoded PCM, settings, and cancellation and returns versioned results. A full provider should compute:

1. normalized analysis PCM and multiresolution waveform;
2. loudness and multiband/spectral/chroma features;
3. onset/spectral-flux novelty;
4. multiple global tempo hypotheses and half/double alternatives;
5. tempo-continuity beat tracking and optional local tempo segments;
6. probable downbeats/bars with confidence;
7. feature self-similarity/novelty and major-change candidates; and
8. evidence labels such as energy rise/fall, timbre change, density change, or silence.

V2 implementation options are a native permissively licensed DSP provider or a pinned editor-only helper based on a reviewed library such as librosa. A helper runs only during editor analysis, stores all results in `UInfinityMusicMap`, and introduces no Python or network dependency in cooked playback. Third-party licensing, binary packaging, deterministic versioning, and a representative annotated-music evaluation must be approved before it ships. Composer-provided tempo/MIDI/cue data should always outrank inference from the mixed recording.

The Music deck shows Waveform, Beats, Downbeats/Bars, Major Changes, Onsets, Loudness/Energy, confirmed markers, and camera-speed/pass overlays. Suggested markers are visually distinct from confirmed markers. Artists can audition, accept, reject, drag, rename, lock, tap tempo, set first downbeat, choose a tempo hypothesis, correct a grid anchor, or reanalyze a selected range. Reanalysis preserves accepted/rejected decisions.

Analysis completion changes no Cue Score data. Applying confirmed data is an explicit diff command that states whether it may move pass timing/camera speed, gaps, count, or markers only, and reports maximum speed/gap changes plus every affected Cue GUID.

Before the product calls this analysis “production ready,” evaluate it against manually annotated examples covering fixed-tempo percussion, half/double ambiguity, tempo change, rubato/orchestral writing, ambient/non-beat material, long silence/fades, speech over music, and dense compressed mixes. Record beat timing error, tempo-hypothesis accuracy, structural-boundary precision/recall, false positives, and confidence calibration. If confidence is not demonstrably calibrated, show qualitative uncertainty or omit the percentage rather than presenting false precision.

### 16.6 Music ownership and section isolation

There is one music-output authority per Show: the one root Level Sequence Player evaluating the plugin-managed Master Audio Track, coordinated and monitored by the placed Show Root's Music Director. Passage Actors may expose an editor-visible audio binding/audition proxy, but never an autonomous, auto-activating music player.

Rules:

- music is 2D/non-spatial by default, so physical Passage bays cannot trigger or attenuate one another;
- world position, overlap volumes, Data Layer visibility, BeginPlay, and player proximity never start defining music;
- ordinary Section ranges are half-open `[Start, End)` and have the owner count declared by policy: zero for Silence/reference-only and one for Start/Continue output;
- `Explicit Crossfade` is the only normal state with two overlapping Audio Sections/voices and requires a shared Transition GUID;
- a continuous score spanning Passage and Scene is one continuing rail, not two coincident players;
- Scene children may own dialogue, ambience, effects, and reference guides, but not defining music in V1;
- the Master builder rejects any audible child guide/score that duplicates the managed Master Rail;
- editor audition acquires the same exclusive token and stops before PIE; and
- mechanism sounds remain spatial and use their separate bounded pool/bus.

The plugin-managed Master Audio Track is generated from authoritative Music Rail data. Artist edits to its trim, offset, gain, or fades are drift and offer **Restore from Music Rail** or **Adopt into Music Rail**; two silent authorities are forbidden.

For real-time show playback, prefer and validate Sequencer's Audio clock source at the Show profile level so the one Master player advances picture and defining music together. Clock choice is never per Section. Editor scrub and Movie Render Queue still evaluate exact Master frames; Quartz, if later used for scheduled starts, remains subordinate to that timeline rather than becoming another show clock.

On play/resume/seek, the root player derives the active managed Audio Section/source sample from absolute Master time, preloads it, stops stale playback, establishes the exact fade gain, seeks, then begins forward playback. The Music Director exposes readiness and enforces exclusivity; it does not launch a parallel copy. Backward shuttle stops/mutes defining music; on landing or forward resume the root player reconstructs the correct source position. If a target rail is not ready, an operator jump remains at the prior stable frame and reports **Audio Not Ready**.

V1 must prove the standard Audio Track's required seek, pause, fade, crossfade, and operator-jump behavior with the chosen codec in Phase 0. If later precision requirements force a custom Music Rail playback track/deck, it replaces the standard output path for that profile; the two paths may never sound simultaneously.

---

## 17. Editor experience

### 17.1 UI design principle: the Cue Desk

The editor takes its cue from QLab's most durable ideas without copying its screen literally:

- one linear cue list is the centre of the application;
- selection and playback standby/current state are distinct;
- the inspector is contextual to cue type;
- secondary information collapses into dockable/resizable panes;
- long inspectors use tabs containing remembered collapsible groups rather than one uninterrupted vertical form;
- a protected Operator mode removes editing risk; and
- the bottom rail gives constant timing/readiness feedback.

The **Cue Score is the only mandatory, non-closable panel**. There is no permanent tool palette and no separate Set/Pair design browser. A user should be able to understand the show by reading down the list.

### 17.2 Layout iteration and recommendation

The first QLab-faithful sketch stacked the list over a full-width inspector:

```text
┌ Show  Cue  Passage  Music  Transport  View ───────── AUTHOR ┐
│ CURRENT / STANDBY: P03 · Wing 042       01:18 / 04:00 │
├────────────────────────────────────────────────────────┤
│ ▶ │ Cue │ Type / Name │ Start │ Beat │ Distance │ Notes │
│   │ P03 │ PASSAGE     │       │      │ 600 m    │       │
│   │ .01 │ WING PAIR   │ 00:01 │ 1.1  │ 2.5 m    │       │
│   │ S04 │ SCENE       │ 04:00 │ —    │ —        │       │
│                 DOMINANT CUE SCORE                       │
├════════════ draggable horizontal splitter ══════════════┤
│ Inspector: Basics | Timing | Wing | Motion | Audio       │
├──────────────────────────────────────────────────────────┤
│ MUSIC 04:00 🔒 │ CAMERA 04:00 │ 600 m │ 120 │ READY     │
└──────────────────────────────────────────────────────────┘
```

This is legible and becomes the **Compact Cue Desk** preset, but a waveform, curves, inspector, and Level viewport compete for scarce vertical space. The recommended wide-screen iteration keeps the list dominant while moving the inspector to the side:

```text
┌ Show  Cue  Passage  Music  Transport  View ───────── AUTHOR ┐
├─────────────────────────────────────────┬───────────────────┤
│ ▶ Cue  Type / Name       Start  Music   │ INSPECTOR         │
│ ▾ P03  FOREST PASSAGE    00:00  04:00   │ Passage | Music   │
│   .001 WING · Birch      00:01  beat 1  │                   │
│   .002 WING · Pine       00:03  beat 2  │ contextual fields │
│   ...                                    │                   │
│   S04  SCENE · Kitchen   04:00  —       │                   │
│             DOMINANT CUE SCORE           │                   │
├════════════════ draggable splitter ═════╧═══════════════════┤
│ Music | Automation | Events | Validation | Stage Preview    │
│ waveform · confirmed/suggested markers · speed/pass overlay │
├──────────────────────────────────────────────────────────────┤
│ 01:18.320 │ MUSIC 04:00 🔒 │ 600 m │ 2.5 m/s │ 120 │ READY │
└──────────────────────────────────────────────────────────────┘
```

Default layout contract:

- Cue Score approximately 74% and Inspector approximately 26% above the bottom deck;
- bottom deck collapsed by default or 20–24% high when open;
- on a standard desktop layout, target at least 16 medium cue rows; a deliberately short/720p window may reduce to 12 before secondary panes must collapse or tab away;
- every divider is draggable and double-click collapses/restores its secondary pane;
- Inspector and bottom-deck tabs can be reordered, moved between stacks, detached, closed, and reopened;
- every major Inspector/Guided Setup category is either a tab or a collapsible group; no normal workflow requires all categories to be expanded simultaneously;
- collapse state and last active subtab are remembered per workspace and cue kind, with **Expand All/Collapse All** available only in a context menu or View command;
- on a short display, secondary content scrolls inside its own pane while the Cue Score heading, active setup-tab summaries, and bottom status rail remain available;
- the Cue Score cannot be closed;
- personal layout/column geometry is stored per-user, not in source-controlled Show data;
- named shared presets are published deliberately;
- detached panes are recovered onto the primary display after a monitor change; and
- the application selects an initial wide or compact preset from available width but never rearranges a saved user layout automatically.

### 17.3 Saved workspaces

Ship these resettable presets:

- **Cue Desk** — dominant list, right Inspector, bottom deck collapsed;
- **Music & Timing** — list plus a tall waveform/analysis/speed deck;
- **Stage Layout** — Cue Score beside Unreal's Level viewport and Outliner;
- **Automation** — list plus large curve/Event deck;
- **Compact Cue Desk** — QLab-like vertical list/inspector stack;
- **Diagnostics** — list plus Validation and performance/materialization counters; and
- **Operator** — read-only list, current/next segment, large transport/status and preflight.

### 17.4 Main Cue Score

Default columns are:

| Column | Purpose |
| --- | --- |
| State | Playhead/current/standby, warning, included/disabled, held state |
| Cue | Stable human-editable cue number; GUID remains hidden identity |
| Type / Name | Explicit WING PAIR, SCENE, SEQUENCE, or derived PASSAGE label |
| Start | Master timecode |
| Music | bar/beat or named confirmed marker when available |
| Duration / Interval | type-specific duration or time to next pass |
| Distance | route chainage for Wing Pair cues |
| Summary | mesh/motion/route/sequence/audio summary |
| Notes | operator-facing note indicator |

Columns are resizable, reorderable, hideable, and stored in named **Editorial**, **Music**, **Geometry**, and **Operator** presets. Row height supports Small/Medium/Large.

Behavior:

- derived Passage headers are sticky while their Wing Pair rows scroll and show duration, distance, count, music-fit state, and sync;
- Scene rows receive a subtle full-row tint and explicit text/icon; color never carries meaning alone;
- current playback, operator standby, selection, hover, disabled, and warning states are visually distinct;
- row warnings open the corresponding Validation entry and Inspector field;
- thousands of rows are virtualized with no hidden button widget per cell;
- drag reorder previews Passage split/merge and timing/materialization consequences before crossing a Scene;
- row selection frames managed world content; world selection reveals the row; and
- right-click exposes only commands valid for the selected cue kind/range.

### 17.5 Contextual Inspector and multi-selection

Inspector tabs appear only when relevant:

- Basics;
- Timing / Rails;
- Wing Pair;
- Motion;
- Route / Placement;
- Music;
- Camera / Handoff;
- Audio;
- Automation;
- Ground / World;
- Validation; and
- Advanced / Build.

Selecting a Passage header exposes the complete music-led fit, route, defaults, Sound, camera, Shadow Figure, Ground, materialization, and validation panels. Selecting a Wing Pair exposes its full inline Left/Right/Top design. A Scene exposes Level Sequence, Scene Volume/content, audio ownership, and camera entry/internal/exit contract.

Multiple selection shows mixed values and supports **Set All**, relative offset, distribute, interpolate, restore inheritance, and create Automation Lane. Reset/inheritance actions live beside the affected field. Every displayed value labels itself as **Manual**, **Music**, **Derived**, **Inherited**, **Automated**, **Pinned**, **Overridden**, or **Stale**; users never infer authority from color alone.

### 17.6 Command and button policy

Persistent authoring controls are limited to:

- **+ Cue ▾**;
- Authoring/Operator mode;
- Search/command palette;
- one grouped transport control; and
- warning/readiness state.

Everything else belongs in menus, context menus, the command palette, Inspector field actions, or keyboard shortcuts. Do not recreate the old strip of separate Insert Passage, Insert Scene, Build Master, Validate, Preview Handoff, Export, and Settings buttons.

Menus:

- **Show:** create/open/save, initialize/repair map, build managed sequences, import/export, show settings, Show Ready.
- **Cue:** insert Wing Pair/Scene/Sequence, duplicate, repeat range, copy/paste, include/disable, tags, ranges, renumber.
- **Passage:** guided setup, split/merge, fit/retime, Reset Music-Derived Count, synchronize stage, promote/demote Hero, route and ground tools.
- **Music:** assign/replace/import, Analyze/Review, Tap Tempo, Set Downbeat, marker operations, authority, fades, audition.
- **Transport:** play/preview/GO, reverse, previous/next segment, hold/resume, seek, loop selection.
- **View:** workspaces, panes/tabs, columns, row size, Level viewport focus/isolation/overlays.
- **Tools:** validation, diagnostics, repair managed content, source drift, performance profile.

The requested Reset Count control also appears as a compact inline affordance beside the **Wing Pair count field**. A single-purpose button is justified only when immediate, frequent, safety-critical, or inseparable from one field; live GO/HOLD/STOP controls are the principal exception.

### 17.7 Nonmodal Guided Setup

Creating a Show or Passage never traps the artist in a modal wizard. It opens a resumable **Guided Setup** tab while the Cue Score remains visible.

One-time Show setup reports Ready/Missing/Needs Repair for:

- Show Asset;
- Show Root;
- Master Level Sequence and placed Sequence Actor;
- camera/transport/music authority;
- folders, Editor Data Layers, and output routing; and
- materialization manifest.

Passage setup presents three sibling tabs. Only the active tab expands; the other two remain as one-line status summaries that can be selected without losing edits:

1. **Music Rail:** Sound Wave, exact In/Out/used duration, fades, gain, waveform, analysis/marker state, duration authority.
2. **Passage Fit:** music duration, manual camera speed/profile, manual spacing, entry/exit, derived distance/count/cadence/residual, and explicit solver target.
3. **Route and Fixed Stage:** route shape/bay, required/available length, starter ground, persistent chunk preview, and one **Create Passage & Materialize Stage** confirmation.

```text
┌ GUIDED SETUP · PROPOSED PASSAGE ─────────────────────────────────────┐
│ [1 MUSIC · 04:00 LOCKED] [2 PASSAGE FIT · 120 / 600 m] [3 STAGE · A]│
├ ACTIVE: PASSAGE FIT ─────────────────────────────────────────────────┤
│ Solve: [Wing Count ▾]                                                │
│ Camera speed  2.50 m/s [MANUAL]   Travel 600.0 m [REPORTED]         │
│ Spacing       5.00 m   [MANUAL]   Cadence 2.000 s [REPORTED]        │
│ Entry / exit  2.5 / 2.5 m [½ SPACING]                               │
│ Wing Pairs    120 [DERIVED] [↺ Reset to music-derived]              │
│ FIT PROPOSED · Music delta ±0 frames · Residual 0.00 m               │
└──────────────────────────────────────────────────────────────────────┘
MUSIC 04:00 🔒 │ CAMERA 2.50 m/s │ 600 m │ 120 @ 5 m │ PROPOSED
```

Music, waveform, analysis, Route, Ground, and materialization controls appear when their tab is selected; they are not stacked below the active Fit form. Within **Advanced**, subsections such as duration authority, clearance solving, tempo map, and output routing are collapsible and remember their state.

The first Guided Setup surface intentionally exposes the three common solver targets—Count, Spacing, and Camera Speed. The adjacent **Advanced** tab exposes Fit Duration, Fit Exit Clearance, Whole Passage versus Music Coverage Only, clearance authorities, and residual policy. The active target is always chosen before its derived field becomes read-only; typing never silently transfers authority.

The preview describes exactly what will be created and the transaction/undo boundary. A count decrease never silently destroys designed rows. Reopening setup resumes from current data rather than presenting the Passage as uninitialized.

### 17.8 Music and timing deck

The Music deck contains horizontally zoomable, cached lanes for:

- waveform;
- source In/Out and fade handles;
- accepted/manual markers;
- suggested beats/downbeats/major changes, visually distinct and confidence/provenance annotated;
- loudness/energy/onset features;
- camera speed/distance;
- Wing Pair pass anchors;
- Events/Cue Ranges; and
- current Master/Passage playhead.

Time-ruler display switches between seconds/timecode, frames, or confirmed bars/beats. Long tracks use multiresolution envelope caches and background, cancellable analysis. Clicking a suggested event auditions a bounded context; it does not insert a cue. Context commands accept/reject/lock it or convert it into a marker/range after preview.

### 17.9 Persistent status and transport rail

The bottom rail remains visible even when every secondary pane is closed. Authoring example:

```text
AUTHOR │ P03 Forest │ MUSIC USED 04:00.000 🔒 │ PASSAGE 04:00.000
SYNCED ±0 frames │ 600.0 m / 600.0 m │ 120 pairs @ 5.00 m │ RESIDUAL 0.00 m
CAMERA 2.50 avg / 2.50 peak m/s │ 2.000 s/pair │ STAGE SYNCED │ READY
```

For variable speed it shows average/peak speed and minimum/maximum pass interval. It distinguishes source-file duration, used In/Out duration, Passage duration, camera traversal duration, required/available route, count, residual, music-fit authority, materialization state, audio owner, camera owner, and readiness.

A disagreement is numerical and textual:

```text
MUSIC 04:00.000 │ CAMERA RUN 03:54.000 │ CAMERA SHORT −00:06.000
```

Clicking a metric focuses its Inspector field or bottom-deck lane; metrics are navigational text, not a row of buttons. Show-level focus replaces Passage statistics with total duration, summed route length, counts, errors, and current Section.

### 17.10 Operator mode

Entering Operator mode performs preflight and locks structural/property editing. Blocking validation prevents Show Ready. The protected display keeps the Cue Score but prioritizes current/standby/next segments, exact time, music and camera ownership, direction/rate, loaded previous/current/next readiness, and large transport controls:

```text
RUN — EDITING LOCKED │ [PREVIOUS] [PLAY ◀] [HOLD/RESUME] [GO ▶] [NEXT]
TC 00:14:28:12 │ P03 → S04 │ CAMERA: PASSAGE │ MUSIC MASTER ✓ │ READY
```

Space maps to **Preview** in Authoring and the clearly labelled primary **GO** action in Operator mode; text-entry focus never triggers transport. Keyboard, OSC, MIDI, and Stream Deck remain adapters over the same commands/status.

### 17.11 Viewport and fixed-stage authoring

The default Cue Desk does not permanently embed a large Level viewport. The **Stage Layout** workspace docks the Cue Score beside Unreal's normal viewport and Outliner. Context/View commands include Focus in Viewport, Reveal Cue, Isolate Passage, Show Entire Stage, Show Route/Chainage, Show Ground Coverage, Show Camera Ownership, Show Shadow Contribution, Show Materialization Drift, and Edit Placement.

Viewport overlays show spline, stations, Passage/Scene/Ground bounds, camera/Shadow Figure pose, selected lights, swept motion/shadow envelopes, music markers projected to pass positions, chunk/render-key ownership, and stale world differences. The footer reports `120/120 visible in Editor · 0 runtime-created` or the exact discrepancy.

Preview changes transforms of existing content and is never serialized accidentally. It must not spawn `WPR_...` Actors or instances, rebuild the map as the playhead moves, or dirty the level merely because time changed.

### 17.12 Keyboard, accessibility, and resilience

- Arrow keys navigate; Shift extends; Ctrl/Cmd toggles selection; left/right collapse/expand Passage groups.
- Enter/F2 edits; Ctrl/Cmd+D duplicates; platform copy/paste/delete/undo/redo conventions apply.
- Ctrl/Cmd+F searches; a searchable, rebindable command palette exposes every menu command.
- Focus is visible; icons have accessible names; color is paired with text/shape.
- UI/font scale, high contrast, reduced motion, and Small/Medium/Large rows are supported.
- Pane movement preserves selection, scroll position, column focus, and last Inspector tab per cue kind.
- Floating panes return on-screen after monitor changes.
- Operator mode has a distance-legibility preset with larger current/next cue text.

### 17.13 Unreal editor implementation

Use `FAssetEditorToolkit`/dock-tab layouts and `SSplitter` for resizable workspaces; `SListView`/`STreeView` virtualization and `SHeaderRow` for the Cue Score; Property Editor/Details customizations for contextual forms; Sequencer Curve Editor channels for automation; and cached Slate waveform geometry for music.

Do not construct interactive widgets for every off-screen cell. Run compile, waveform extraction, analysis, and materialization diffs as cancellable background/editor tasks with clear stale results. Store user layouts in per-user Editor settings. Named shared presets, column schemas, and Operator profiles may be project data only when deliberately published.

---

## 18. CSV, JSON, and script interchange

### 18.1 Why not a canonical DataTable

The authored model contains:

- stable ordered GUID rows;
- heterogeneous cue payloads;
- three nested panel definitions;
- override masks;
- inline curves;
- route points;
- automation ranges;
- soft asset references;
- Cue Ranges/tags; and
- transactional reorder semantics.

Flattening this into a UE DataTable would make editing and round-trip behavior brittle. It would also encourage two sources of truth between the DataTable and editor asset.

### 18.2 CSV cue-sheet export

Provide a human-readable flat export with columns such as:

- Show/Cue/derived Section/Passage Span IDs;
- `CueKind` and semantic role;
- order;
- enabled;
- Cue Range/tags;
- label;
- pass frame/time;
- interval;
- distance;
- gap;
- Left/Right/Top asset paths;
- aperture;
- travel;
- mechanism style/duration;
- route offsets;
- Section Music Binding policy, Rail GUIDs, and local coverage summary;
- Scene Level Sequence, Scene Volume/world adapter, trim, and entry/exit camera markers;
- Transport Segment and Handoff summary;
- notes; and
- warning summary.

Nested material/transform details may use clearly versioned additional columns or remain JSON-only.

### 18.3 Lossless JSON

JSON export includes:

- the complete ordered heterogeneous Cue Score;
- all Passage Span settings without duplicated member cues;
- Scene/Sequence payloads and volume references;
- Camera Handoffs and Transport Segments;
- schema version;
- automation curves;
- route data;
- complete Music Program/Rails/Section bindings, mechanism audio, and Shadow Figure plans;
- stable GUIDs; and
- content hash.

It supports:

- backup;
- external tooling;
- deterministic diff;
- schema-version upgrade/archival; and
- lossless reimport.

### 18.4 Import

Import flow:

1. Parse without changing assets.
2. Validate schema and asset paths.
3. Match cues, spans, Handoffs, and Transport Segments by GUID.
4. Show added, removed, updated, reordered, and conflicted rows.
5. Require an explicit deletion policy.
6. Apply as one transaction.
7. Recompile and show post-import validation.

Blank GUIDs create new cues. Changing an existing row's `CueKind` requires an explicit conversion/diff confirmation because its payload is structurally different. Import never infers deletion merely because a CSV omits a row unless **Replace entire Cue Score** was explicitly selected. A CSV containing only Wing Pair rows may target one Passage Span; it cannot reorder Scene cues outside that declared scope.

### 18.5 Script sheet relationship

The current Google Sheet should remain a script/dramaturgy source. A future one-way **Seed Show from CSV** tool may map STRUCTURE/MUSIC markers into Sections, Events, and notes, but the plugin should not make live Google Sheets connectivity a production dependency.

---

## 19. Validation and diagnostics

### 19.1 Severity

- **Error:** cannot compile, play, or render correctly.
- **Warning:** can proceed, but likely visual/audio/performance problem.
- **Info:** noteworthy derived fact or recommendation.

### 19.2 Show/Cue Score validators

- duplicate/missing Cue, Passage Span, Handoff, Transport Segment, or derived Section GUID;
- Cue kind/payload mismatch;
- broken/non-contiguous Passage Span partition or duplicated cue membership;
- Scene/Sequence cue missing Level Sequence;
- Scene cue missing/unresolved Scene Volume or world-content adapter;
- invalid duration or trim;
- inconsistent display/tick rates;
- unintended gap/overlap;
- child duration drift;
- stale managed Master hash;
- missing/duplicate active Show Root or root Master Sequence Player;
- auto-playing managed child Sequence or auto-activating managed defining-music component;
- defining-music owner count inconsistent with policy: zero is required for Silence/reference-only, one for Start/Continue output, and exactly two only inside a declared crossfade;
- audible child guide/score duplicates the managed Master Rail, or a child claims V1 defining-music authority;
- missing or simultaneous/double camera authority;
- invalid entry Handoff, internal Scene camera window, or exit Handback;
- Scene entry/exit transform, lens, focus, or aim outside tolerance;
- Transport Segment with missing/reversed/out-of-show bounds;
- unresolved world content;
- insufficient forward or backward preload/retention;
- incompatible map/binding; and
- included Cue with no playable payload.

### 19.3 Passage validators

- missing member Wing Pair Cue or duplicate member resolution;
- zero/negative interval or gap;
- invalid lead/tail;
- non-monotone distance/time;
- contradictory locks;
- invalid/missing Music Rail or Section Music Binding, source/coverage In/Out samples, continuation discontinuity, crossfade GUID pair, fades, duration authority, or seek readiness;
- non-seek-capable/platform-specific compression on a show-critical trimmed or operator-seeked Rail;
- music/source fingerprint differs from count-fit snapshot, waveform, analysis, or managed Audio Track;
- duration/speed/spacing/count/clearance equation or residual does not close within tolerance;
- non-finite/negative camera-speed profile or non-invertible cumulative distance;
- analysis suggestion incorrectly treated as confirmed authoring data;
- confirmed beat/marker outside used In/Out range;
- undeclared rail overlap/crossfade or spatialized defining music;
- missing panel asset;
- disabled Left and Right without intentional marker;
- invalid override value;
- invalid/zero loop period or negative rate;
- discontinuous loop-curve endpoints/tangents;
- non-finite or discontinuous integrated phase;
- orphaned Automation Lane range;
- overlapping lanes with ambiguous equal priority;
- stale compiled hash;
- unsupported hero class;
- excessive unique render keys;
- unsafe shadow-relevance cull or unsupported shadow-only material path;
- Shadow Figure Rig visible/intersecting the camera unexpectedly or two unintended rigs active across a Handoff;
- unresolved audio asset; and
- audio pool pressure above configured target.

### 19.4 Route validators

As listed in Section 11.5, plus:

- Passage content longer than route;
- excessive unused reserve;
- spline-point edit not written back;
- invalid generated-route solution;
- endpoint transition frame outside safe straight;
- anchor outside route range; and
- self-intersection inside the camera visibility/shadow envelope.

### 19.5 Materialization, world, and ground validators

- materialization hash/schema does not match Show revision;
- in Fixed Resident mode, expected persistent Passage/Chunk/Hero/panel missing or duplicate Cue/side mapping;
- in Fixed Resident mode, fixed stage Actor/component/instance appeared or disappeared after BeginPlay;
- in optional serialized-stream mode, missing/stale cooked Actor descriptor or package, wrong Runtime Data Layer membership, or a loaded chunk that does not conform to its manifest;
- world transform drift not adopted/reverted;
- component/render-key/persistent-memory or active-update budget exceeded;
- duplicate active Show Root or chunk referenced by another Show;
- Ground Zone missing, stale after route edit, or not covering its declared route/camera/shadow envelope;
- wing/camera/Shadow Figure penetration outside tolerance;
- visible seam/bay edge, unintended ground overlap/gap, or mutually exclusive grounds simultaneously active;
- wrong folder/Data Layer/Actor Editor Context; and
- missing or unresolved Ground/Scene Level Instance/Landscape/material reference.

### 19.6 Actionable reporting

Every issue should have:

- asset and stable GUID;
- human label/index;
- frame and distance if relevant;
- reason;
- severity;
- one or more safe fixes;
- **Select/Open** action; and
- suppression only with an authored reason.

Validation must be available:

- for current selection;
- for current Passage Span or Scene cue;
- for complete Show;
- during Master build;
- before cook; and
- in automation tests.

---

## 20. Reuse and clean break from Stage Wing Director

### 20.1 Reuse by concept or isolated code

Strong candidates:

- Left/Right/Top panel definition semantics;
- 90-degree import correction and 2D flat-panel scaling;
- local pair anchor arrangement;
- the basic in/out alpha-to-transform operation;
- mechanism sound settings and motion-response intent;
- Primary Data Asset as a basic container pattern;
- the design lesson of separating display labels from internal identity and validating uniqueness;
- transaction-safe duplicate/reorder UX;
- camera viewfinder and preview interaction patterns;
- optional transition-curtain mesh/audio behavior; and
- automation-test discipline.

Reuse here means field meaning, transform/math ideas, and UX lessons. It does not mean transplanting old classes or their loading/ticking behavior: the old panel, fixture, and audio paths load synchronously; Pair/audio objects tick; the viewfinder is embedded in a monolithic window; and the curtain is coupled to the old transition state. Any adapted code must be reviewed and moved into small new classes. The 5,000-line old Director and 3,000-line old editor module must not be copied as units.

### 20.2 Retire

- Wing Sets and Buckets;
- Look Cue selection modes;
- random/cyclic pair choice;
- runtime Repeat Count;
- visible-layer carousel;
- conveyor wrap;
- cue feed on wrap;
- rear-entry/exit wrap fades;
- moving-ground compensation as a core feature;
- generated light fixtures and inheritance;
- companion-tag generation;
- saved generated-rig art-direction state;
- GO-driven Scene/Look state machine;
- inline-show fallback;
- actor-label sequence rebinding;
- old legacy field migration inside runtime; and
- persistent preview Actor naming as identity.

### 20.3 Side-by-side plugin

Proposed:

    Plugins/InfinityStageDirector/
    Plugins/StageWingDirector/      # remains separate while still useful to the old production setup

New C++ classes, asset classes, config keys, commands, and generated metadata use an `InfinityStage` namespace/prefix.

### 20.4 Clean-break asset policy

There is no old-show importer, compatibility bridge, Set/Look flattening mode, or legacy provenance in scope. Production creates the new Cue Score deliberately.

Existing meshes, materials, sounds, and other neutral content may be assigned normally. If a required asset currently lives under the old plugin's content root, move or duplicate it into neutral project/shared content before the old plugin is retired. The new runtime and cooked Show must not depend on Stage Wing Director modules, classes, config, or runtime state.

Any isolated transform math, UI pattern, or preset adapted from the old implementation is rewritten behind new types and verified independently. The old plugin remains untouched and can coexist for visual comparison while Infinity Stage Director is developed.

---

## 21. Plugin architecture

### 21.1 Modules

#### InfinityStageRuntime

- asset schemas and serialization;
- custom versioning;
- Music Rail/Music Map schemas and deterministic sample/frame conversion;
- Cue Score partition/compiler and compiled structures;
- route/spline math;
- Show Root, persistent Passage/Chunk/Hero Actors, Scene/Ground Volumes, and registration components;
- camera/Shadow Figure Rig/Anchor evaluation;
- Transport Controller and readiness/status API;
- World Subsystem;
- persistent chunk renderer/contribution tiers;
- exclusive Master music director and mechanism-audio pool;
- native MovieScene track/section/evaluation;
- runtime validation;
- async preload; and
- Blueprint-facing read-only events/APIs.

#### InfinityStageEditor

- asset type actions;
- unified Cue Score editor and Passage-focused mode;
- heterogeneous virtualized grid;
- dockable Cue Desk workspace/layout/column presets;
- Details proxies/customizations;
- Guided Setup and duration/speed/spacing/count solver;
- Music Rail waveform, fade/marker review, analysis-provider UI, and automation/curve UI;
- spline component visualizer;
- persistent stage materialization/synchronization service and viewport selection bridge;
- Ground Zone/Scene Volume setup and preview overlays;
- Master and Passage sequence builders;
- Sequencer track-editor registration;
- CSV/JSON import/export;
- editor validation/fixes;
- commands/menus/settings; and
- documentation links.

#### InfinityStageTests, optional developer module

- unit;
- editor automation;
- functional;
- scale/performance fixtures; and
- packaged/live/MRQ test fixtures.

### 21.2 Key classes/services

| Responsibility | Proposed type |
| --- | --- |
| Show/Cue Score data | `UInfinityStageShowAsset`, `FInfinityCue` |
| Passage settings | `FInfinityPassageSpan` inside the Show Asset |
| Show/world/audio coordinator | `AInfinityStageShowRoot`, `UInfinityStageMusicDirectorComponent` |
| Music data and review | `FInfinityMusicProgram`, `FInfinitySectionMusicBinding`, `FInfinityMusicRail`, `UInfinityMusicMap`, `IInfinityMusicAnalysisProvider` |
| Music-led constraint solving | `FInfinityStagePassageFitSolver` |
| World representation | `AInfinityStagePassageActor`, `AInfinityStageWingChunkActor`, optional `AInfinityStageWingPairActor` |
| Editor materialization | `FInfinityStageMaterializationService`, `FInfinityStageMaterializationManifest` |
| Scene content registration | `AInfinityStageSceneVolume` |
| Ground registration | `AInfinityStageGroundZone` |
| Traveling silhouettes | `AInfinityStageShadowFigureRig` / component |
| Manual path-relative content | `AInfinityStageAttachmentAnchor` / component |
| Absolute-time evaluation | `UInfinityStageWorldSubsystem` |
| Compile score/spans to dense data | `FInfinityStageCueScoreCompiler`, `FInfinityStagePassageCompiler` |
| Render batching/contribution | `UInfinityStageWingChunkComponent` / renderer service |
| Music and pooled mechanism sound | Show Root Music Director plus `UInfinityStageAudioSubsystem` |
| Live/rehearsal transport | `UInfinityStageTransportController` |
| Sequencer adapter | `UMovieSceneInfinityPassageTrack/Section` |
| Master build | `FInfinityStageMasterSequenceBuilder` |
| Passage sequence build | `FInfinityStagePassageSequenceBuilder` |
| Validation | asset validators plus shared rule library |

### 21.3 Separation rules

- Asset classes contain authored data, not world scanning.
- Compiler is a pure or nearly pure transformation.
- Evaluator consumes absolute time and compiled data.
- Materializer runs only as an explicit editor transaction and owns only manifest-declared stage objects.
- Renderer knows instance batches, not authoring UI.
- Music transport knows Rail ownership/Master time; mechanism audio knows schedules/active cues; neither knows Cue Score widgets.
- Sequence builder changes only objects carrying a valid `UInfinityStageManagedDecoration`.
- Editor commands mutate assets transactionally through a command/service layer.
- No monolithic Director owns editing, playback, lighting, input, camera, audio, and transitions.

### 21.4 Dependencies

Likely Runtime dependencies:

- Core, CoreUObject, Engine;
- CinematicCamera;
- LevelSequence;
- MovieScene and MovieSceneTracks;
- AudioMixer as required;
- Projects/DeveloperSettings; and
- optional Quartz only when live musical scheduling is implemented.

Optional Editor dependencies:

- Audio Synesthesia for native NRT suggestion overlays; and
- a separately packaged/licence-reviewed analysis provider, never a cooked Runtime dependency.

Likely Editor dependencies:

- UnrealEd;
- Slate/SlateCore;
- PropertyEditor;
- AssetTools;
- ContentBrowser;
- LevelEditor;
- Sequencer;
- MovieSceneTools;
- CurveEditor;
- ToolMenus; and
- DataValidation.

Exact APIs and module boundaries must be proven against the installed UE 5.8 source in Phase 0.

### 21.5 Serialization

- Register an Infinity Stage custom version GUID.
- Store immutable object GUIDs separate from display names.
- Give every future Infinity Stage schema upgrade a deterministic test.
- Never reuse old serialized C++ type names.
- Cache compiled data by content hash and compiler version.
- Rebuild stale caches automatically, but never rewrite authored data without a transaction.
- Store materialization and Music Map fingerprints separately from display names/paths.
- Never require Derived Data Cache at runtime; cooked compiled blobs and persistent map content are versioned/serialized.

---

## 22. Master-build ownership contract

The sequence builder is a high-risk area and needs a strict contract.

### Builder may

- create a named managed folder/track;
- partition the Cue Score and create one managed subsection per Passage Span or Scene/Sequence cue;
- create/update objects carrying `UInfinityStageManagedDecoration` with Owner/Show/derived Section/Passage Span/Cue GUIDs, role, and build version;
- set range, trim, color, display name, and referenced child sequence;
- create/update the Passage custom track and its required binding;
- compile exact non-overlapping camera-authority intervals from Camera Handoffs;
- create/update generated markers;
- report drift; and
- remove obsolete managed objects after a diff/confirmation policy.

### Builder may not

- delete unknown tracks;
- identify ownership only by display name;
- modify artist camera/animation/FX tracks inside a Scene;
- replace a child sequence;
- rewrite an artist's Camera Cut Track;
- move manual sections silently;
- rebind Actors by label;
- change level content; or
- save unrelated dirty packages.

### Idempotence

Building twice from unchanged source assets must produce no semantic changes, no duplicate tracks/sections, and no dirty package on the second build.

---

## 23. Performance and scalability requirements

### 23.1 Structural requirements

- No one Actor, Tick, or Audio Component per authored Wing Pair cue.
- Persistent Actor count scales with Shows, Passages, stable chunks, Scenes, Ground Zones, and Hero promotions—not ordinary pair count.
- Component/render-key count is measured and budgeted honestly; incompatible unique meshes/materials cannot be batched by declaration.
- No per-cue Tick.
- All authored Wing Pair/chunk/hero content exists as serialized editor-visible map content before PIE. Fixed Resident loads all of it; optional serialized-stream mode may keep packages unloaded but never un-authored.
- No `SpawnActor`, `AddInstance`, or component construction for fixed stage content at BeginPlay; optional streaming only loads serialized packages.
- No whole-world Actor scan during normal evaluation.
- No synchronous asset load on a render/evaluation frame.
- GUID lookups use indexes/maps, not repeated linear scans.
- List UI is virtualized.
- Compiled time/distance lookup uses binary search or better.
- Per-frame transform/render/audio work scales with contribution-relevant Wing Pairs, including conservative shadow contributors, not total show rows, even though fixed geometry remains authored and visible.
- Persistent chunk/component/hero/render-key budgets and active update/audio budgets are separate and both expose counters.

### 23.2 Test scales

Maintain generated fixtures for:

- 120 Wing Pair cues plus two Scene cues / representative short assembly;
- 600 Wing Pair cues / long Passage Span;
- 3,000 mixed cues / unresolved upper-production or representative full-work stress scale;
- 10,000 mixed cues / stress scale; and
- Master Sequence of approximately 45 minutes with all macro Sections.

### 23.3 Initial target budgets

Budgets must be finalized on the production workstation and render target. Suggested starting gates:

- mixed Cue Score selection/edit response below 100 ms at 3,000 rows;
- Passage compile below 2 seconds at 3,000 simple rows after a cold data edit;
- incremental local edit/preview refresh below 100 ms where no asset load is required;
- passage evaluator below 2 ms game-thread time for the configured contribution range;
- in Fixed Resident mode, zero fixed-stage Actor/component/instance additions or removals at BeginPlay;
- in optional serialized-stream mode, valid cooked descriptors/Data Layer membership and exact per-loaded-chunk manifest conformity, with no plugin-side construction;
- direct seek to a loaded frame visibly resolves below 100 ms;
- chunk/Hero Actor growth within the declared materialization formula and no ordinary Pair Actor growth;
- exact Transport boundary response with no one-frame overshoot;
- bounded looping, shadow-only, previous-segment, and Shadow Figure Rig costs;
- no missing first frame after a Section cut in Movie Render Queue; and
- stable memory after repeated scrub/transition cycles.

These are engineering gates, not a promise that arbitrary source meshes/materials meet the same render cost.

### 23.4 Instrumentation

Add Unreal Insights/stat counters for:

- compile time;
- active looping/moving Wing Pairs;
- shadow-only Wing Pairs and conservative shadow-tail distance;
- Shadow Figure Rig evaluation/render cost;
- loaded chunks;
- total serialized/materialized Wing Pairs, Chunk Actors, Hero Actors, components, instances, and stale chunks;
- render batches and updated instances;
- unique render keys;
- asset wait time;
- route lookup time;
- audio candidates/voices/steals;
- Anchor updates;
- sequence evaluation; and
- previous/current/next Transport Segment readiness and command latency.

The performance fixture must include the actual cutout material family, not only opaque placeholder cubes.

---

## 24. Test plan

### 24.1 Unit tests

- heterogeneous Cue serialization, kind/payload matching, and stable order;
- deterministic derivation of Passage Spans and Sections;
- insert-Scene split, delete-Scene merge, and stable Span GUID rules;
- global/local time conversion through Passage and Scene cues;
- cumulative pass frames/distances;
- explicit start/lead/Wing Pair/tail anchors, including a one-row span;
- rejection of equal-frame/different-distance anchors;
- four-minute/2.5 m/s/5 m/half-spacing-clearance fit yields exactly 600 m, 120 pairs, and 2 s cadence;
- count-fit boundary tolerance never produces 119 or 121 for that example;
- all solver targets close the same duration/speed/spacing/count/clearance equation;
- Music Coverage, Manual, Timeline Boundary, and Placeholder duration authorities plus Whole Passage/Music Coverage Only fit windows resolve the documented `T_passage`/`T_fit` and binding offset;
- a five-minute Rail split into a two-minute Start binding plus continuing Scene binding does not lengthen the first Passage and preserves exact source-sample continuity;
- Fit Spacing covers two Manual, two Half Spacing, mixed-clearance, and preserved Solved-clearance modes plus the `N = 1` case;
- Fit Duration is accepted only for constant-speed/Whole-Passage/unlocked-duration input and rejects Music Coverage Only, variable-profile, or locked-duration combinations;
- Fit Exit Clearance writes explicit Solved authority and an edited solved value becomes Manual;
- variable-speed integration and station-time inversion are deterministic;
- Reset Count restores count authority and last manual spacing without changing camera speed;
- integer source-sample to rational-frame conversion has no cumulative drift over a 60-minute fixture;
- Show Music Program owner intervals resolve Silence, Start, Continue across a Scene, and declared crossfade without duplicate Rail GUIDs; V1 child defining-music ownership is rejected;
- Music Rail fades meet exact endpoint gains and In/Out validation;
- suggested, confirmed, and rejected Music Map data survive reanalysis correctly;
- absolute-to-delta editing;
- monotone interpolation;
- inversion/query of distance-time curve;
- lane range anchoring after insert/delete/reorder;
- Add/Multiply/Override resolution and priorities;
- Wing Pair override precedence;
- rail exclusion from Automation Lanes and atomic constraint-solver failure;
- duplicate assigns new GUID;
- copied asset references remain valid;
- route generation exact-length tolerance;
- stable spline frame/no roll flip;
- turn/clearance checks;
- camera-authority interval uniqueness and Handoff boundaries;
- Transport Segment bounds and exact clamp frames;
- constant and integrated-rate loop phase at play/seek/reverse/optional serialized-stream boundaries;
- a 30-second loop-rate slowdown preserving phase continuity and expected cycle count;
- rejection of discontinuous loop curve endpoints;
- shadow-relevance decision from swept bounds/light/frustum inputs;
- contribution-range binary search;
- render-key grouping;
- deterministic audio schedule/seed;
- forward interval-crossing audio event queries and discontinuity reset;
- JSON round-trip;
- CSV merge by GUID; and
- custom version upgrades.

### 24.2 Editor automation tests

- initialize a blank map in one undoable transaction; exactly one Show Root, Master Sequence Actor, audio authority, folders/layers, and manifest exist;
- initialize again and verify no duplicates or package churn;
- Cue Desk splitters, tabs, workspaces, column presets, and compact/wide layouts restore safely;
- Guided Setup exposes only one expanded Music/Fit/Route stage at a time, preserves all draft values while switching, and restores its last tab/collapse state;
- short-window and 720p layout tests keep the Cue Score, setup-tab summaries, and bottom status rail usable without opening an excessively tall top-level window;
- Cue Score remains visible while Guided Setup opens/closes/resumes;
- dropping representative WAV/MP3 assets creates a Music Rail and previews duration/count/distance before commit;
- waveform In/Out/fade/marker geometry aligns at multiple zoom levels;
- analysis is cancellable/cached and never modifies Cue rows on completion;
- replacing/reimporting music presents a stale-fit diff rather than silently refitting;
- count reset is one transaction; a decrease removes confirmed untouched placeholders but blocks on designed/anchored rows until the artist explicitly relocates or deletes them;
- create one mixed Cue Score: Passage → Scene → Passage;
- create a 120-Wing-Pair Passage Span;
- materialize 120- and 3,000-pair fixtures with Actor count proportional to passages/chunks, not ordinary pairs;
- in Fixed Resident mode, all expected Wing instances/components exist before PIE;
- in serialized-stream mode, every authored chunk has a valid cooked descriptor/package and loaded chunks exactly match their manifests;
- Cue-row and viewport instance selection round-trip;
- generic world drift is detected; Adopt/Revert and Hero promote/demote preserve Cue identity;
- incremental synchronization changes only affected chunks and an unchanged second synchronization dirties no package;
- route/spacing changes mark Ground Zones stale without altering artist-owned ground;
- row-kind-specific Details and safe mixed-selection editing;
- assign Scene Volume/sequence and capture entry/exit cameras;
- insert/move/delete Scene with Passage split/merge undo/redo;
- duplicate/repeat/reverse pattern;
- multi-edit and mixed values;
- undo/redo bulk operation in one step;
- automation-lane creation/edit/bake;
- Cue Range/Event anchoring after insert/reorder;
- route editing writes to the Passage Span in the Show Asset and undoes;
- Anchor survives insert/reorder;
- save/reload retains order and GUIDs;
- validation issue selects exact source;
- Passage sequence build is idempotent;
- Master build is idempotent;
- user tracks survive rebuild;
- managed Decorations retain durable ownership through save/reload;
- manual managed-section drift is detected;
- adopt/restore timing works;
- managed Master Music Rail ownership/fades match authored Rail data and reject undeclared overlaps;
- editor audition stops before PIE;
- operator controls and readiness monitor update correctly; and
- shadow/debug preview selects the correct rig, pair, and light-relevance source.

### 24.3 Runtime/Sequencer tests

- in Fixed Resident mode, compare fixed-stage Actor/component/instance counts immediately before and after BeginPlay; no plugin stage content is added or removed;
- a missing/stale materialized chunk fails explicitly and is never reconstructed at runtime;
- Fixed Resident and optional serialized-stream profiles produce equivalent frames;
- play from start;
- direct seek;
- operator play/pause/seek/shuttle and exact forward/backward Transport boundary clamp;
- Previous/Next Segment jump with no one-frame overshoot;
- reverse visual playback;
- nested subsequence time transform;
- cross-frame-rate trim conversion with subframe/rounding policy;
- trim and play-rate behavior;
- camera crosses exact Wing Pair plane at exact pass frame;
- identical frame result after different playback histories;
- identical visual state after Sequencer play, operator forward, operator reverse, Previous/Next jump, and MRQ sample;
- pre-animated state restore;
- MovieScene evaluation pre-roll may prepare hidden pose/assets but never acquires camera/music authority or emits a mechanism transient;
- two evaluation-player contexts coexist without state leakage;
- overlapping macro subsections are rejected and a serial Transition Sequence owns its own Camera Cut interval;
- Passage arrival → Scene establishing camera → internal cuts → closing camera → next Passage ownership;
- the same boundary sequence evaluated in reverse and by direct seek;
- previous/current/next Section streaming, Scene Volume registration, and bidirectional readiness;
- a not-ready operator target leaves time and camera unchanged and reports Not Ready;
- fixed real-time playback reports/fails safely if readiness misses the preflight deadline without slipping show time;
- external unpausable music disables unsafe hold/reverse while sequence-owned music seeks with the Master;
- no first-frame pop;
- Movie Render Queue repeated frame comparison;
- loop transforms remain identical after optional serialized chunk unload/reload and update-tier changes;
- production Puss/Boy figures cast expected in-frame shadows without unintended direct view/reflection;
- camera pitch/roll exercises all Shadow Figure Rig orientation modes;
- a behind-camera pair whose shadow enters frame matches an all-resident golden render and unloads only after relevance ends;
- no physical-robot runtime dependency/control path is required;
- exactly one defining music voice exists, or exactly two during a declared crossfade;
- zero defining-music voices exist through a Silence/reference-only Section;
- one Rail continues across Passage → Scene without stop/restart or duplicate output;
- seeking directly into Passage B leaves no Passage A music playing, irrespective of physical bay overlap;
- pause/resume/Previous/Next reconstruct the correct Music Rail source offset from Master time;
- backward shuttle is silent for defining music and forward resume lands at the correct source offset;
- a 45–60-minute PIE/packaged marker fixture remains within one display frame of visual/music sync after fixed output-latency compensation;
- repeated seek/pause/resume/segment-jump tests across every approved codec/platform land within the configured audible-sync tolerance and report measured error;
- ordinary Passage/Scene boundaries have no double playback and Scene-child versus Master ownership conflicts are rejected;
- editor and PIE never output defining music simultaneously;
- audio forward playback;
- scrub transient suppression;
- no historical loop-audio burst after seek and no duplicate cycle event after reverse/forward;
- voice prioritization/stealing with bounded distant loops;
- persistent chunk/component/render-key budgets under repeated and mostly unique production assets; and
- cook/package asset discovery.

### 24.4 Ground and world-authoring tests

- flat mesh, spline strip, independent Landscape, Level Instance, and Manual Ground Zones register to the correct Section;
- a temporary Follow Route deck updates transactionally, while a promoted World Locked zone is never modified;
- continuous transition golden sweep shows no unintended seam;
- a Scene cut conceals disconnected Ground Zones in separate bays;
- route/spacing changes create actionable coverage diagnostics;
- Data Layer isolation never enables mutually exclusive grounds, lights, or rail music together;
- establishing/closing shots do not reveal bay edges; and
- all-section Editor visibility plus Fixed Resident PIE stays within profiled memory or blocks Show Ready with an explicit budget error.

### 24.5 Production acceptance scenes

#### Passage–Scene–Passage vertical slice

- one unified list containing at least 120 Wing Pair cues, one Scene cue, and an outgoing Passage;
- approximately two-second pass cadence;
- looping near/distant/rear pairs with a 30-second rate slowdown;
- repeated 10–20-row motifs;
- at least two gradual motion changes;
- one gradual camera slowdown;
- manual lights and one animated prop attached to Anchors;
- mechanism audio;
- a four-minute Music Rail whose duration/speed/spacing setup yields exactly 120 pairs, with editable In/Out/fades and reviewed analysis suggestions;
- persistent Show Root, Master music/camera ownership, and zero fixed stage creation at BeginPlay;
- one wood/concrete temporary deck promoted to manual ground and one disconnected forest Ground Zone concealed by the Scene;
- Puss/Boy Shadow Figure Rig producing an intended in-frame shadow;
- matched handover into the Scene, internal cuts, closing-shot handback; and
- a concealed spatial cut between separate Passage zones plus operator forward/reverse rehearsal.

#### Full-show assembly

- all current script macro Sections;
- roughly 45-minute Master;
- QLab-inspired Cue Desk and Operator workspace used for the complete run;
- all fixed stage content materialized/visible in the Editor, with Fixed Resident and any optional streamed profile validated;
- six passage routes;
- all current Scene/Interlude subsequences;
- previous/current/next loading;
- entry and exit Handoff validation;
- scrub from start to end;
- save/reopen;
- packaged playback or MRQ test; and
- no reliance on Stage Wing Director runtime state.

---

## 25. Delivery phases

### Phase 0 — risk spike

Prove before building the full editor:

- one Show Asset with a mixed Cue Score and derived Passage Spans;
- one 120-Wing-Pair synthetic Passage → Scene → short outgoing Passage;
- one 3,000-cue synthetic mixed score;
- music-fit proof that 240 s × 2.5 m/s at 5 m spacing/half-spacing clearances yields exactly 120 pairs;
- Sound Wave In/Out/fade/sample-to-frame mapping and one exclusive Master Audio Track/Show Root music authority;
- Bink/PCM seek, pause/resume, fade/crossfade, and representative output-latency proof with Platform Specific compression rejection;
- deterministic Cue partition and global/local time conversion;
- spline placement and stable orientation;
- camera distance through exact pass anchors;
- Static plus Continuous Loop with independent closed Left/Right/Top curves;
- one 30-second integrated loop-rate Automation Lane and one travel lane;
- one compiled mechanism start/reversal schedule with scrub suppression;
- native Sequencer section at absolute time;
- direct seek/reverse/MRQ consistency;
- persistent editor materialization of 120- and 3,000-pair fixtures using real render-key distributions;
- Fixed Resident pre-PIE/post-BeginPlay object-count parity, serialized-stream descriptor/loaded-chunk-manifest validity, and no runtime stage construction;
- ISM batch updates over existing serialized components;
- route length change;
- one Attachment Anchor;
- one camera-relative Puss/Boy Shadow Figure Rig with production light/shadow/main-pass proof;
- contribution-aware behind-camera wing shadow retention;
- exact operator forward/back segment transport with not-ready protection;
- one complete Passage → Scene → Passage camera-ownership test;
- one Ground Zone/temporary deck plus a route edit that marks artist-owned ground stale without modifying it;
- one actual cutout material family, repeated-versus-unique component-budget test, and world/binding/readiness spike; and
- profiling on the target workstation.

Exit criterion: the music-fit/time/spline/Sequencer/persistent-world/render/audio-authority architecture is demonstrably viable.

### Phase 1 — Cue Desk, Show setup, and Music Rail foundation

- schemas/custom version;
- Primary Data Assets;
- QLab-inspired heterogeneous virtualized Cue Score and derived Passage headers;
- wide/compact saved workspaces, resizable dock tabs/splitters, columns, command menus, status rail, and protected Operator shell;
- row-kind and Passage-Span Details;
- idempotent Show initialization placing Show Root, Master Actor, folders/layers, audio/camera authority, and manifest;
- nonmodal Guided Setup;
- `FInfinityMusicRail`, waveform/In/Out/fades/gain/manual markers, exact duration authority, and source hashing;
- duration/speed/spacing/count/clearance solver plus inline Reset Count;
- multi-select;
- duplicate/repeat/reorder;
- timing/spacing totals;
- Straight route;
- transient preview;
- base validation; and
- transactions/undo.

### Phase 2 — persistent stage, routes, ground, and evaluator

- compiled Show and Passage Spans;
- monotone distance-time curve;
- absolute-time evaluator;
- Serpentine/Helix/Normalized/Manual routes;
- persistent Passage/Chunk/Hero format and transactional incremental materialization;
- Cue ↔ viewport selection, world-drift Adopt/Revert, Hero promote/demote;
- repeated-key ISM and unique-panel fallback renderer over serialized components;
- camera follower;
- traveling Shadow Figure Rig;
- shadow-aware contribution tiers;
- Anchors;
- Ground Zone registration, temporary deck, coverage/stale diagnostics;
- Fixed Resident profile plus optional serialized async preload; and
- scale instrumentation.

### Phase 3 — Sequencer, camera handoff, music transport, and live control

- native Passage track;
- Passage sequence builder;
- Cue Score/Scene Volume/Handoff editor;
- Master builder;
- plugin-managed Master Music Rail Audio Track, exclusive Show Root routing, source-seek reconstruction, fades, and ownership validation;
- scene trims/handles;
- full camera handover/handback tools and authority validation;
- required `UInfinityStageTransportController` with forward/reverse/segment controls;
- Data Layer/Level Instance activation;
- bidirectional Master-time load lead/retention readiness, with evaluation pre-roll kept authority-silent; and
- MRQ hardening.

### Phase 4 — bulk/range authoring and interchange

- automation lanes;
- curve UI;
- recipes;
- advanced range fit/retime/respacing and variable camera-speed rail;
- bake/unbake;
- Cue Ranges and tags;
- CSV cue sheet;
- lossless JSON;
- diff import; and
- large-show ergonomics.

### Phase 5 — mechanism sound and reviewed musical intelligence

- Passage Sound panel;
- deterministic motion-derived audio schedule;
- pooled spatial voices;
- mix/submix controls;
- scrub policy;
- optional Audio Synesthesia feature overlays;
- analysis-provider implementation/evaluation corpus;
- reviewed tempo/beat/downbeat/major-change Music Map;
- composer tempo/MIDI/cue import;
- marker/range/automation-boundary conversion and previewed beat fitting; and
- optional precision clock adapter after profiling.

### Phase 6 — production hardening

- neutral/shared asset audit and strict independence from Stage Wing Director runtime;
- World Partition tuning;
- fixed-resident memory, source-control/OFPA, editor open/save, and optional streamed-equivalence hardening;
- performance budgets;
- packaged/MRQ soak tests;
- documentation;
- example show/passages;
- release packaging; and
- sign-off against Section 24.

---

## 26. Acceptance criteria

The plugin is ready for first production use when:

1. An artist can author Wing Pair, Scene, and other Sequence cues in one authoritative, QLab-inspired chronological Cue Desk without opening a Set/Pair library; the list remains dominant while Inspector/bottom tabs resize, dock, detach, collapse, and restore safely. Guided Setup expands only one Music/Fit/Route tab at a time, and long Inspector categories are remembered collapsible groups rather than a single tall form.
2. Assigning a 240-second Music Rail with 2.5 m/s speed, 5 m spacing, and half-spacing clearances previews exactly 600 m, 120 Wing Pairs, and 2-second cadence; Reset to Music-Derived Count restores that closure without changing camera speed.
3. Inserting or deleting a Scene cue transactionally splits/merges Passage Spans, routes, lanes, Handoffs, and timing with a preview and one-step undo.
4. A 30-second loop-rate slowdown and widening can be made with Automation Lanes, edited later, and previewed at any frame without phase discontinuity.
5. Camera pass frames and wing loop phases remain exact after scrub, operator jump, reverse, optional serialized stream-out/in, and MRQ.
6. A Manual Absolute route is never silently changed when content length changes.
7. Manual lights/props attached to Anchors survive compile, route edit, row insertion, and Master rebuild.
8. The Master Sequence references Passage Spans and Scene/Sequence cues at macro scale only.
9. A Scene cue defines its volume/content and completes Passage arrival → establishing shot → internal cuts → closing shot → next Passage handback with validated camera ownership and transform/optics continuity.
10. A Scene can conceal a switch between unrelated Passage zones without a missing/incorrect first frame in forward, reverse, direct seek, or render.
11. Music supports exact In/Out, fades, gain, waveform, manual markers, duration authority, deterministic seeking, one exclusive playback owner, and reviewable analysis suggestions that never mutate cues automatically.
12. Mechanism sound follows one-shot and looping authored motion and respects a bounded voice budget without historical bursts after seek.
13. Distant and rear Wing Pairs remain active when their geometry or shadows contribute, then change update/visibility/optional-streaming tier without restarting phase or causing shadow pops.
14. The Puss/Boy Shadow Figure Rig casts the intended shadows while remaining out of the intended shot, with no dependency on or control path to the physical robot dog.
15. Operator Play Forward/Reverse, Pause, Seek, Previous/Next, and Hold land on exact Master frames, preserve correct camera ownership, and refuse an unready/clock-unsafe move cleanly.
16. A several-thousand-row show does not create a corresponding number of Actors, ticking objects, Audio Components, or Slate widgets.
17. Rebuilding managed sequence content preserves user-authored tracks.
18. Old assets remain untouched; the new runtime has no dependency on old classes, plugin content, or carousel state.
19. Validation can locate every blocking issue by stable asset/GUID identity.
20. Initializing an empty Show World creates exactly one visible Show Root, Master Actor, camera/music authority, folders/layers, and manifest; repeating setup creates no duplicates.
21. Every ordinary fixed Wing Pair is visible/selectable in the Editor before PIE. In the default Fixed Resident profile, BeginPlay adds/removes no plugin stage Actors, components, or instances; optional serialized streaming only loads pre-authored packages and validates every loaded chunk against its manifest.
22. Cue and viewport selection round-trip; transactional synchronization preserves artist lights/props/ground, supports drift Adopt/Revert and Hero promotion, and does not dirty unchanged content.
23. Separate wood/concrete/forest/Scene Ground Zones can coexist, and route edits warn about coverage/seams without rewriting World Locked ground.
24. Operator mode locks editing, shows numerical music/camera/distance/count/readiness state, and has no competing Level Blueprint, child Auto Play, or Auto Activate authority.

---

## 27. Clarification questions and decision register

### Resolved decisions

1. One **Wing Pair** cue is one Left/Right/optional Top occurrence, while Scene and other Sequence cues coexist in the same authoritative list.
2. Puss is a physical robot dog outside the plugin. Unreal carries virtual Puss-the-cat and Boy figures behind/near the camera to create shadows.
3. Sequencer and live operator transport are both required and share one absolute Master timeline. MRQ is the offline/high-quality render path, not the operator interface.
4. Approximately two seconds is the initial pass interval; mechanism cycle duration is independent.
5. Wing mechanisms normally loop continuously while relevant, with deterministic absolute phase. Static, One Shot, and Bounded Loop remain available.
6. Main Scenes may and should conceal cuts between separate Passage zones.
7. The normal camera grammar is incoming Passage arrival/establishing frame, Scene-owned internal cuts, then closing shot and handback to the next Passage.
8. There is no old-show migration. Only neutral assets and isolated implementation ideas are reused.
9. The Cue Desk is QLab-inspired: the main chronological list is dominant, secondary tabs/panes are resizable/dockable, long category groups are collapsible, Guided Setup uses one expanded internal stage tab at a time, and single-function authoring buttons are minimized.
10. Music is the default Passage-duration authority; camera speed and spacing are normally manual, while Wing Pair count and distance are derived.
11. Music analysis is an editor-only review aid, not an automatic choreographer. V1 provides the reliable Rail and native feature overlays; a corpus-tested provider is a later capability.
12. Fixed Passage geometry is materialized transactionally and visible before PIE. Runtime playback animates existing serialized content and may optionally stream it, but never generates the stage.
13. One visible Show Root owns the Master clock, camera authority, transport, and exclusive non-spatial music routing; core behavior does not live in the Level Blueprint.
14. The production baseline is one Unified Show World with separate Passage/Scene bays and independent Ground Zones; Scenes conceal spatial cuts.
15. The final visual output is a live performance running narrative visuals through PIE/UE5 Sequencer. Movie Render Queue remains a deterministic test/offline-review path, not the delivery format; nDisplay is not assumed.
16. Performance planning assumes at least 30 unique wing source assets per Passage and six Passages, therefore at least 180 unique wings overall. The conservative fixture treats each as a distinct mesh/material render key until the real materials prove that more batching is possible.
17. Passage defining music is wholly controlled by the Master Sequence. Scene sound may also be external to Unreal; those Scene Transport Segments declare external audio authority/readiness and disable unsafe reverse/hold/rate changes unless the external system is synchronised and controllable.
18. The world footprint, vertical range, and minimum route radius remain deliberately content-dependent. V1 uses normalized/editable spline routes and separate provisional bays so the final footprint can be solved after Scene and Passage extents are known rather than embedded in the data model.

### Build-readiness assessment

The specification is sufficiently complete to begin Phase 0 and build an end-to-end **first full V1** without another architecture workshop. Core ownership, schemas, editor/runtime boundaries, timing mathematics, rendering model, music authority, camera handoffs, live transport, materialization, validation, testing, and delivery order are resolved. No unanswered item below requires inventing a competing timeline, second cue model, or different runtime architecture.

If production answers are not yet available, V1 proceeds with these explicit provisional defaults:

- one Unified Show World with separate Passage/Scene bays and Fixed Resident live PIE as the final visual runtime;
- Master Sequence-controlled Passage music, hybrid externally declared Scene sound, keyboard/Blueprint operator controls, and optional OSC/MIDI/timecode adapters later;
- reverse visuals with defining Passage music muted during shuttle and seek/resume performed only through the verified Sequencer/codec path; Scene segments with uncontrolled external sound reject unsafe transport;
- possessable Passage cameras and registered Scene cameras, with serial cuts/Transition cues rather than overlapping macro subsections;
- camera-relative Puss/Boy Shadow Figure Rig kept physically behind/outside the shot until a production shadow-only path is proven;
- Continuous Loop as the Passage mechanism default, with rate/phase exposed rather than a hard-coded artistic cycle;
- separate spatial bays, temporary modular/spline Ground Zones, and artist promotion to World Locked;
- 48 kHz production WAV, non-spatial defining music, and platform-verified Bink/PCM seek settings; and
- V1 reviewed waveform/loudness/onset/Constant-Q assistance only; inferred beat/downbeat/form analysis remains the separately evaluated V2 provider.

Three answers are still needed before performance and live-show hardening can be signed off, although they do not block initial implementation: target workstation/GPU for live PIE; usable world footprint/vertical range/turn radius; and the exact protocol/clock relationship for external Scene sound. Output mode, minimum unique-wing scale, and Passage music authority are now resolved. The other open items are content, artistic-default, or venue-integration choices that the implemented UI is designed to hold.

### Remaining production choices before final implementation

1. **Existing Story ingestion:** which Scene content should become Level Instances, ordinary Actors, or Data Layers inside the resolved Unified Show World, and what conversion work is needed.
2. **Operator semantics:** exact named segment boundaries, button mapping, shuttle rates, hold behavior, control hardware/protocol, and how externally sounded Scene segments signal start/readiness/synchronisation to the Master transport.
3. **Scene Volume representation:** preferred combination of Runtime Data Layer, Level Instance, registered volume Actor, and spatial bay.
4. **Shadow figures:** final Puss/Boy assets, relative animation, camera/route orientation, offsets, lights, shadow renderer, reflection policy, and whether a true shadow-only path is reliable.
5. **Loop defaults:** typical cycle period, phase origin/distribution, Left/Right/Top relationship, and which exceptional pairs use One Shot or Bounded Loop.
6. **Handoff style per Scene:** hard/matched cut, shared camera binding, short blend, or explicit Transition Sequence. Every Scene still requires an Entry and Exit camera contract.
7. **Ground implementation per Section:** modular mesh/spline strip, Landscape, Level Instance, or fully manual; plus which transitions are continuous versus concealed by Scene cuts.

### Decisions needed for performance tuning

8. Target workstation/GPU for the final live PIE performance; no nDisplay or offline-render delivery is currently assumed.
9. The baseline is 30 unique wing source assets per Passage / 180 overall; confirm how many distinct mesh/material render keys this produces once the actual asset library is assigned.
10. Whether “several thousand wings” means panels or Wing Pair cues, plus maximum visible and shadow-relevant depth.
11. Nanite/material/collision/shadow constraints of the photographic wing assets.
12. Available world footprint, vertical range, minimum acceptable turn radius, and whether adjacent coils may ever be visible.
13. Whether Fixed Resident PIE fits memory comfortably or optional serialized World Partition/Data Layer streaming must be enabled.

### Decisions needed when music and sound are available

14. Final music source format and whether it is final-mixed in Unreal or only a reference rail.
15. Need for bars/beats/tempo changes versus manual time markers, and whether composer MIDI/tempo/cue maps are available.
16. Whether V2 should ship a native analysis provider, a pinned editor-only helper, or import-only musical intelligence after the evaluation corpus.
17. Required audio output format: stereo, binaural, multichannel, venue routing, or separate stems.
18. Final operator reverse-audio behavior: mute/shuttle then seek, audible reverse treatment, or another designed behavior.
19. Desired mechanism sound: one-shot squeaks at starts/reversals, continuous friction, layered MetaSound, or a mixture.

These choices tune content and controls but do not reopen the core Cue Score, absolute-time, Scene-Handoff, looping-motion, or clean-break architecture.

---

## 28. Recommended artist-facing vertical slice

After the Phase 0 risk spike and the minimum features from Phases 1–5, build one artist-facing vertical slice as a single Cue Score:

    Passage Span A (120 Wing Pair cues)
      → Scene Cue (entry, internal cuts, exit)
      → Passage Span B (short representative continuation)

Include:

- 120 placeholder/real Wing Pair cues in Span A and at least 20 in Span B;
- a 240-second Music Rail, 2.5 m/s manual camera speed, 500 cm manual spacing, 2.5 m clearances, 600 m travel, exactly 120 derived pairs, and 2-second cadence;
- waveform In/Out/fades/manual markers plus native feature suggestions that remain unaccepted until reviewed;
- the QLab-inspired Cue Desk, Music & Timing workspace, persistent numerical status rail, and protected Operator workspace;
- two physically separated routes, one converted from Straight to Serpentine;
- one Show Root with exclusive Music Rail, Master camera/transport authority, and no Level Blueprint competition;
- every Wing Pair materialized into persistent editor-visible Chunk content before PIE, with Fixed Resident pre/post-BeginPlay count parity and optional streamed-manifest validation;
- one temporary spline/mesh deck promoted to World Locked and one independent forest Ground Zone concealed across the Scene;
- one camera rig per Passage Span;
- one Puss/Boy Shadow Figure Rig behind the active Passage camera;
- continuously looping near, distant, and rear/shadow-relevant pairs;
- two repeated 12-row motifs;
- one 30-second integrated Loop Rate slowdown lane;
- one 30-second Inward Travel lane;
- one camera slowdown created by varying intervals while gaps stay fixed;
- one manually placed animated Actor on a Wing Pair Anchor;
- one mechanism sound profile;
- one plugin-managed Master Music Rail Audio Track with no undeclared overlap;
- persistent managed Passage sequences;
- one artist-authored Scene sequence and registered Scene Volume;
- validated arrival to establishing shot, internal Camera Cuts, closing-shot handback, and concealed spatial zone switch;
- a persistent managed three-Section Master; and
- operator forward, reverse, pause, Previous/Next Segment, and not-ready rehearsal tests.

Reuse the Phase 0 synthetic 3,000-cue fixture for regression profiling. The vertical slice proves the artistic workflow; Phase 0 separately proves the architectural risks before the full UX is built.

---

## 29. Technical basis

The architecture uses established UE 5.8 facilities:

- QLab's documented [Workspace](https://qlab.app/docs/v5/fundamentals/workspace/) and [Inspector](https://qlab.app/docs/v5/fundamentals/inspector/) patterns support the Cue Desk precedent: a central cue list, cue-specific Inspector, resizable/collapsible panes, and protected Show Mode. Infinity Stage adapts the interaction principles rather than copying the product.
- Epic documents [Sub-Sequences and Shots](https://dev.epicgames.com/documentation/unreal-engine/sequences-shots-and-takes-in-unreal-engine) as the way to organize larger cinematic sequences into manageable child sequences.
- Unreal [Spline Components](https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-spline-components-overview-in-unreal-engine) are editable paths intended for moving and placing Actors/components.
- Sequencer [Property/Transform tracks](https://dev.epicgames.com/documentation/en-us/unreal-engine/cinematic-transform-and-property-tracks-in-unreal-engine) support keyframed float/transform curves, while a native custom track is appropriate for the plugin's absolute-time passage evaluation.
- Sequencer [Audio Tracks](https://dev.epicgames.com/documentation/en-us/unreal-engine/cinematic-audio-track-in-unreal-engine) support trims, fades, pitch/volume, crossfades, and spatial attachment.
- Unreal's [Level Sequence project settings](https://dev.epicgames.com/documentation/unreal-engine/level-sequence-settings-in-the-unreal-engine-project-settings?lang=en-US) expose an Audio clock source for real-time sequence playback; it must be verified with the chosen codec and operator seeks.
- UE 5.8's [audio import documentation](https://dev.epicgames.com/documentation/unreal-engine/importing-audio-files?lang=en-US) lists WAV, MP3, OGG, FLAC, AIFF/AIF, Opus, 16-bit, and 24-bit source support; final-show policy still prefers seek-verified 48 kHz/16-bit WAV.
- [Audio Synesthesia](https://dev.epicgames.com/documentation/en-us/unreal-engine/audio-synesthesia-in-unreal-engine) provides editor/offline NRT loudness, onset, and Constant-Q analysis assets, useful as optional feature/suggestion inputs rather than a complete music-form oracle.
- [Quartz](https://dev.epicgames.com/documentation/unreal-engine/overview-of-quartz-in-unreal-engine) provides sample-accurate musical scheduling when later required; it is not a recording-analysis engine or alternate show clock here.
- librosa's official [beat/tempo documentation](https://librosa.org/doc/latest/beat.html) and [temporal segmentation documentation](https://librosa.org/doc/0.11.0/segment.html) demonstrate a credible editor-only V2 analysis route, subject to packaging, licence, versioning, and evaluation approval.
- Epic's [UE 5.8 instancing guidance](https://dev.epicgames.com/documentation/unreal-engine/instanced-static-mesh-component-in-unreal-engine) distinguishes ISM/HISM tradeoffs and notes that HISM is especially suited to genuinely static thousands, while ISM is generally appropriate for dynamic/Nanite use after profiling.
- [World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine) and [Runtime Data Layers](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---data-layers-in-unreal-engine) provide organization and loading controls for large, separated world content.
- [Actor Editor Context](https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-editor-context-in-unreal-engine) can place newly authored lights/props/ground into the selected Passage/Scene context.
- Epic's [Blueprint best-practices guidance](https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-best-practices-in-unreal-engine) distinguishes reusable Blueprint Classes from level-specific Level Blueprint logic, supporting the placed Show Root boundary.
- [Level Instancing](https://dev.epicgames.com/documentation/en-us/unreal-engine/level-instancing-in-unreal-engine) and [Landscape Materials/Edit Layers](https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-edit-layers-in-unreal-engine?lang=en-US) support section-specific set/ground organization; no engine rule requires one ground object for the map.
- UE 5.8 [dynamic bindings](https://dev.epicgames.com/documentation/en-us/unreal-engine/dynamic-binding-in-sequencer) provide a later route for resolving registered passage rigs without actor-label matching.
- Epic's [Movie Render Pipeline](https://dev.epicgames.com/documentation/unreal-engine/movie-render-pipeline-in-unreal-engine?lang=en-US) defines Movie Render Queue (MRQ) as the high-quality offline image/movie output path; it is a validation/render target here, not the live operator transport.
- The [UE 5.8 release notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes) describe Sequencer Audio Modulation Control Bus and Control Bus Mix tracks, useful for a later Section-mix layer.

These are implementation foundations, not reasons to expose engine complexity in the artist-facing workflow.

---

## 30. Final recommendation

Build Infinity Stage Director around three stable artifacts:

1. one **Show Cue Score Asset** containing the authoritative heterogeneous order of Wing Pair, Scene, and other Sequence cues;
2. **Passage Span configurations and compiled routes** keyed to contiguous Wing Pair ranges, containing automation, route, camera, shadow-figure, rendering, music, and mechanism sound settings but no duplicate cue lists; and
3. a **persistent managed sequence hierarchy** whose plugin-owned tracks evaluate the score deterministically while preserving artist-owned Scene and global tracks.

Add two world-facing artifacts that make those data usable as a real stage:

4. one placed **Show Root** owning the single Master transport, camera authority, music router, and readiness registry; and
5. a **persistently materialized editor stage** made from Passage/Chunk/Hero Actors plus artist-owned Scene/Ground Zones, visible before PIE and never synthesized at BeginPlay.

Use a hybrid spatial layout—separate Passage zones plus editable finite splines—rather than one enormous line or one universal spiral. Let Scene cues conceal spatial and Ground Zone resets while explicitly owning the establishing/internal/closing camera interval. Use automation lanes for gradual mechanism/layout change, deterministic local loops for ongoing depth motion, and CSV/JSON only as interchange. Preserve manual scene content through GUID-based Scene Volumes, Ground Zones, Anchors, and strict managed-content ownership.

Make the Music Rail the default Passage setup authority: exact recording In/Out plus manual camera speed and spacing derive travel and count, with an always-visible numerical status rail and explicit reset. Offer sophisticated analysis as a reviewed proposal layer, not an algorithm that decides the performance. Present all of this in the QLab-inspired Cue Desk, where the chronological list dominates and secondary controls remain contextual, resizable, and dockable.

Most importantly, make visuals a pure evaluation of absolute Show frame, make defining music and live controls follow the same Master player, and make playback animate a stage that already exists. Those decisions keep music sync, operator forward/back navigation, scrubbing, looping wing phase, Scene camera ownership, shadow figures, nested Sequencer playback, Movie Render Queue, route/ground changes, and several thousand finite Wing Pair cues coherent.
