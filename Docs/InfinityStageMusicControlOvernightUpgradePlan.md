# Infinity Stage — Music and Live-Control Overnight Upgrade Plan

## Implementation checkpoint — 12 August 2026

Completed and applied to the production development fixture:

- Resizable wide three-pane Cue Desk: nested/flat Cue Score, permanent Cue inspector, and Passage/Music/Fit/Route inspector, with the Music timeline in the resizable lower pane.
- Derived Passage header nodes over the authoritative chronological Cue array, collapse/expand behavior, and mutation-safe selection for duplicate/delete/move operations.
- Music waveform scrubbing mapped through Passage-local time to the one Master frame; in PIE it seeks the root Sequence Player, and outside PIE it evaluates the existing camera rig and fixed Wing mechanisms without spawning a second stage.
- Compact Previous / Reverse / Hold / GO / Next controls backed by the existing transport controller, plus an exact-frame public scrub command.
- Selected-Passage proxy exposing the real Passage and Music Rail instead of the complete Show arrays; music-led fit now persists preferred spacing, speed, clearances, lead/tail and named fit mode when resetting the count.
- One-click safe relink/reimport of analysis maps from `Saved/InfinityStage/MusicAnalysis`; all six maps were imported and linked without changing Cue identity, order, count or timing.
- Role-aware front-axis placement. Right architectural wings turn physically by 180 degrees and no longer gain a new negative-scale photographic mirror. Ten previously flagged right assets had the old automatic mirror removed, while left and neutral assets were deliberately untouched.
- Explicit per-panel **Flip Image Horizontally** authoring is now independent of front/back facing. The Cue Desk's contextual **Image Orientation** menu can toggle one Left/Right/Top occurrence or copy its checked/unchecked state to every occurrence using the same mesh, with undo/redo and immediate fixed-Passage rematerialization. Source photographs, FBXs and normalized mesh assets remain unchanged.
- The Cue Desk now provides **Actions > Wing Movement** presets for selected Wing Pair rows or their whole current Passage: a gentle wave along the route, the reversed wave toward camera, synchronized breathing, and a reversible static hold. The closed smooth curves, rate, travel and Passage-relative phase offsets remain ordinary editable Cue data. Music Timeline scrubbing and Master playback evaluate the same absolute phase; no per-wing Tick or playback history is introduced.
- Six fixed Passage bays rematerialized; zero Curtain assignments remain; the production Master was rebuilt and saved with 6 Passage, 5 Scene and 6 managed music sections.
- UE 5.8 editor build succeeded. The complete 13-test Infinity Stage suite passed after content repair, including Master Sequence open, Cue Desk construction, role-aware facing, 3,000-wing scale, transport safety and saved-fixture PIE. Final startup contained no real HTTP 403, fatal, crash, assertion or failed-ensure signature.

Deferred to the next iteration rather than represented as complete:

- draggable Source In/Out and fade handles, zoom/pan/ruler lanes and bounded audio audition;
- marker selection plus Confirm/Reject/Suggested editing and explicit analysis-to-cue fit diffs;
- artist-authored Group nodes, drag/drop range moves between Passages and move previews;
- persistent per-user pane ratios, responsive narrow/medium breakpoints, dock/detach and dedicated Operator workspace;
- formal managed-build content hashes and UI status beyond successful idempotent rebuild;
- saving the automatically enabled Instanced Static Mesh usage flag on the small set of Shrine materials before a packaged build.

**Plan date:** 12 August 2026  
**Target:** a materially more usable Infinity Stage Cue Desk for authoring and live PIE performance  
**Working window:** 14 focused hours, with a two-hour stretch reserve only after the core gate is green  
**Current baseline:** the compiling `InfinityStage` plugin, six imported Passage rails and Music Maps, fixed editor-visible wings, managed Master Sequence, camera rigs, and the saved six-Passage development show

## 1. Morning outcome

By morning, an artist should be able to select a Passage in the main Cue list and do the following without opening several unrelated Unreal windows:

1. see the defining music as a usable horizontal timeline rather than a static summary;
2. trim the used music range and edit fade-in/fade-out from that timeline;
3. see music length, Passage length, camera speed, spacing, route distance, Wing Pair count, and closure error together;
4. restore a Passage to a music-derived Wing Pair count without changing the preferred camera speed;
5. inspect proposed beats, onsets, and major changes, confirm or reject them, and choose a tempo hypothesis without silently retiming any cue;
6. preview an optional beat/pass fit as a numerical diff, then explicitly apply or cancel it;
7. rebuild or restore the one managed Master music track and see whether it is synchronized or stale;
8. enter a compact Operator view and run forward, hold/resume, move to neighboring Sections, or rehearse backwards through the existing root Sequence Player; and
9. see an immediate explanation when a command is unavailable because the current Scene declares external unpausable sound;
10. drag the music playhead and see the Passage camera and fixed Wing Pairs evaluate at that exact moment in the Level viewport; and
11. switch the Cue list between Flat and Nested modes, collapse Passage/Section groups, and reorder Wing Pair blocks within or between them.

The upgrade is successful only if all defining Passage music still comes from the one Master Sequence Player. Passage Actors, their physical map positions, and editor audition controls must never create competing playback clocks.

## 2. What already exists and what the overnight changes

| Area | Existing foundation | Overnight upgrade |
| --- | --- | --- |
| Cue Desk | Dominant virtualized flat Cue list, Cue/Music/Fit/Route tabs, draggable side and bottom splitters | Persist layouts; add a virtualized Nested view over the same Cue Score; give the Music workspace its own lanes, toolbar and interaction; add Author/Operator workspace modes |
| Music data | Six `FInfinityMusicRail` records with Sound, source In/Out, fades, fingerprint and Music Map | Add explicit duration/fit authority, rail gain/readiness, chosen tempo/grid state, stale state, and exact fit snapshot |
| Analysis | Deterministic offline provider; waveform, tempo, beat, onset and major-change proposals; importer preserves decisions | Background Analyze/Reanalyze action, review controls, marker hit-testing, filters, state editing, accepted-grid workflow and stale-source handling |
| Fit | Correct solver and “Reset wing count from music,” but the tab currently uses temporary numbers | Bind Fit directly to the selected Passage and used Music Rail; preview every consequence; make music-locked fit the default |
| Timeline | Resizable waveform with fades and major-change lines, currently paint-only | Zoom/pan, ruler, playhead, source handles, fade handles, cue/pass overlay, camera-speed overlay, beat/change lanes and context actions |
| Sequencer | Stable managed Passage, Scene and Audio tracks; idempotent rebuild | Add managed-build status/hash, Restore/Adopt policy, exact source-out handling and preflight diagnostics |
| Transport | Existing forward/reverse-to-boundary, jump, pause/resume, shuttle, exact segment frames and external-clock safety | Surface it in the Cue Desk with clear status, keyboard commands, readiness feedback and a live Operator layout |
| Fixed stage | Six materialized Passage bays, fixed before PIE | Add non-dirtying absolute-frame visual scrub and repair Right-wing facing/handedness; no runtime stage generation changes |

## 3. Non-negotiable authority rules

### 3.1 Music is the authoring rail

For a Passage with a valid Start music binding, the default duration is:

```text
UsedMusicDuration = SourceOut - SourceIn
PassageDuration = UsedMusicDuration
```

If Source Out is unset, use the Sound Wave duration. Fades are inside the used range and do not silently extend it.

The default fit lock order is:

1. **Music duration locked**;
2. **preferred camera speed retained**;
3. **preferred spacing retained**;
4. entry and exit clearances retained; and
5. **Wing Pair count derived**, with the residual distance reported.

The artist may deliberately change the fit mode, but the UI must identify the changed authority and never solve a circular set of hidden constraints.

### 3.2 Sequencer remains the playback clock

Music analysis does not create a second clock. Confirmed beats and markers are labels and authoring anchors in the music source domain. Compilation converts accepted source samples/times into exact Master frames. Playback, camera motion, wing motion, fades, and operator transport still evaluate the root Sequence Player's frame.

### 3.3 Analysis is assistive

Analyze/Reanalyze may update a `UInfinityStageMusicMapAsset`; it may not add, delete, reorder, or retime Cue rows. Suggested, confirmed and rejected states remain separate. Any operation that would change the Cue Score must first show:

- affected Passage and cue range;
- old/new duration, pass frames and Wing Pair count;
- old/new average and peak camera speed;
- old/new minimum/maximum interval and gap;
- maximum cue displacement in frames/seconds;
- affected Cue GUID count; and
- validation warnings.

Only an explicit **Apply** transaction changes authored cues. Cancel leaves the Show Asset byte-for-byte unchanged.

### 3.4 External Scene sound is declared, not guessed

Passage defining music is Master-controlled. A Scene may also rely on external sound. When the active Scene is `DeclaredUnpausable`, Performance mode disables unsafe hold, reverse, jump and non-1.0 shuttle commands. Rehearsal mode may move visuals, but the UI must state that external sound is not synchronized. No overnight task invents an OSC/timecode protocol.

### 3.5 Side, facing and image handedness are separate

`Left`/`Right` first identify which side of the route a panel occupies. They do not, by themselves, authorize mirroring the photographed image. The Wing Library and placement compiler keep three independent facts:

1. **canonical asset frame** — scale, pivot, vertical axis and panel thickness/front axis;
2. **semantic handedness** — Left architectural, Right architectural or neutral, including which silhouette edge should be outside; and
3. **placement facing** — which material/front normal faces the photographed corridor at a particular route station.

Negative-scale mirroring is never applied automatically merely to make an architectural edge fall on the other side. It can reverse winding, tangents, text and photographic content. An explicit artist-approved mirrored variant is allowed, but it is recorded as such. A Right panel should normally use a correctly handed Right asset or a reversible placement correction that preserves the intended image.

## 4. UI layout

The main Cue list remains the most prominent object. Music gains horizontal space below it because time is more legible horizontally; analysis does not return to a tall box above the Details panel.

The wide-screen default uses three vertical panes so Cue and Music remain visible together:

```text
┌ Show ▾ ─ Author/Operator ─ Sync: CURRENT ─────────────────────────────── Actions ▾ ┐
├─────────────────────────────┬──────────────────────────┬───────────────────────────┤
│ CUE SCORE · Flat / Nested   │ CUE INSPECTOR            │ PASSAGE / MUSIC           │
│ ▾ P01 Intro       48 pairs │ P01 Wing 024             │ P01 Intro Walking         │
│   ▾ Opening Architecture   │ Left / Right / Top       │ Rail · In/Out · fades     │
│      23 P01 Wing 023  2.0s │ spacing · timing         │ tempo/grid review         │
│   ▶ Lake Objects           │ mechanism · overrides    │ music-led Fit summary     │
│ 49 Scene 1 · External      │                          │ Master CURRENT            │
│ ▶ P02 Walking     24 pairs │                          │                           │
├─────────────────────────────┴──────────────────────────┴───────────────────────────┤
│ P01 · 00:00.000 / 01:36.300    ◀  HOLD/RESUME  GO ▶       Music Actions ▾          │
│ RULER / WAVEFORM / WING PASSES / CAMERA SPEED / ANALYSIS                           │
│ [In]────────────── waveform and markers ───────────────────────────────[Out]        │
├───────────────────────────────────────────────────────────────────────────────────┤
│ MUSIC 01:36.300 · PASSAGE 01:36.300 · Δ 0 fr · CAMERA 2.50 m/s · 48 @ 5.00 m       │
│ ROUTE 240.0 m · MASTER CURRENT · MUSIC READY · CAMERA READY                         │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Pane behavior

- The cue/inspector and editor/music splitters remain draggable.
- In a sufficiently wide window, the upper workspace has three independent resizable columns: Cue Score, Cue Inspector and Passage/Music Inspector.
- The lower Music workspace can collapse to a 28–36 px summary strip, restore to the previous height, or detach into a dock tab.
- Cue and Music are no longer mutually exclusive in the wide layout. Each inspector column can collapse independently.
- Fit is integrated into the Passage/Music column as a compact card; Route remains a selectable view in that column or a dedicated Stage Layout workspace.
- Split ratios, collapsed state, timeline zoom, visible lanes, last tab and Author/Operator mode are stored in per-user Editor settings, not in the Show Asset.
- Minimum sizes prevent the Cue list, transport status or timeline from being trapped below usable dimensions.
- A **Reset Workspace Layout** command exists in the Actions menu; it is not a permanent button.

### 4.2 Button discipline

The default Author layout has only two compact menu buttons at the top, one selected-passage Music Actions menu, and a conventional transport cluster in the bottom header. Functions such as analyze, confirm all visible, reject, rebuild, restore, adopt, fit, export and reset layout live in contextual menus or right-click menus.

Operator mode is the deliberate exception: one prominent **GO / Resume Forward** control is appropriate cueing-software language. It is surrounded only by Previous, reverse-to-boundary, Hold/Resume and Next. Structural editing is locked in Operator mode.

### 4.3 Flat and Nested Cue modes

The canonical Show Asset remains one ordered Cue Score. Nested mode is a structural view over that order, not a second array that can drift.

```text
SHOW
├─ PASSAGE 01 · Intro Walking          48 pairs · 01:36.3
│  ├─ GROUP · Opening architecture     12 pairs
│  │  ├─ P01 Wing 001
│  │  └─ …
│  ├─ GROUP · Lake objects             20 pairs
│  └─ GROUP · Approach Scene 1         16 pairs
├─ SCENE 01 · External Sound
├─ PASSAGE 02 · Walking                24 pairs · 00:47.4
│  └─ …
└─ …
```

- Passage nodes are derived from contiguous Wing Pair runs separated by Scene/Sequence cues and therefore cannot become detached from chronology.
- Artist Groups are stable-GUID organizational ranges inside a Passage. They carry a name, color, notes and collapsed state, but no independent playback clock or duplicated Wing rows.
- Flat mode shows the same rows in exact chronological order with optional Group/Passage header rows.
- Dragging one Wing or a selected contiguous block within a Passage reorders the canonical Cue array transactionally.
- Dragging a Group moves its full contiguous range and preserves internal order and Cue GUIDs.
- Dropping into another Passage previews the resulting source/destination duration, music mismatch, count, route and materialization changes before Apply.
- Scene/Sequence rows stay top-level. An ordinary artist Group cannot cross a Scene boundary.
- A Passage may be collapsed without removing its camera/music status from the footer.
- Collapse state is per-user UI state; Group identity/name/notes are Show data.
- Duplicate/Repeat Group uses the existing deep-copy semantics but assigns new Cue and Group GUIDs.

The first overnight implementation may use derived Passage nodes plus one level of artist Groups. Arbitrary folder-within-folder depth is not required for the core gate and must not replace the flat Cue Score as authority.

### 4.4 Responsive three-pane behavior

- **Wide (recommended, approximately 1500 px or more):** Cue Score | Cue Inspector | Passage/Music Inspector, with the Music timeline across the full width below.
- **Medium:** Cue Score | one Inspector column, with Cue and Passage/Music selectable or pinnable; the Music timeline remains below.
- **Narrow:** Cue Score above or beside a tabbed Inspector; the lower Music workspace may collapse to its summary strip.
- The breakpoints are based on each pane's measured minimum usable size rather than one hard-coded desktop resolution.
- Default wide ratios begin near `28% / 30% / 42%`, but saved user ratios win.
- The Cue Score keeps enough width for indentation, label and the compact Timing/Spacing/Status columns. Optional low-value columns hide before the label truncates excessively.
- The Passage/Music column is a dedicated selected-Passage editor. It must not display the raw entire Show `MusicRails` array or force the artist to hunt through `Index [0]`, `Index [1]`, and unrelated rails.
- A small pane header allows **Pin Cue**, **Pin Music**, swap columns, collapse, or open in a dock tab. These commands live in the header menu rather than freestanding buttons.
- When no Passage is selected, the third pane shows Show-level music readiness and the six Rail summaries. When one Passage is selected, it shows only that Passage's binding and Rail.

## 5. Music workspace behavior

### 5.1 Selection and navigation

- Selecting any Wing Pair selects its containing Passage in the Music workspace.
- Selecting a Scene shows that Scene's music/external-sound policy and neighboring Passage boundaries.
- Selecting multiple Wing Pairs in one Passage highlights their time range and pass markers.
- Selecting rows across Passages shows a summary and disables ambiguous single-Passage edits.
- Clicking the waveform seeks editor preview; during PIE it requests a safe rehearsal/performance transport seek through the existing controller rather than moving an unrelated preview player.
- The playhead follows the Master frame. A source-time readout shows the mapped sample/time under the pointer.

### 5.2 Lanes

The overnight lane set is intentionally small but complete:

1. **Ruler:** seconds/timecode, with bars/beats when one tempo hypothesis is confirmed.
2. **Waveform:** cached waveform, source In/Out, fades and gain envelope.
3. **Wing Passes:** one tick per occurrence, selected-range shading and scene boundaries.
4. **Camera:** preferred speed and compiled effective average/segment values; warnings where a proposed fit exceeds limits.
5. **Analysis:** filterable beats, onsets and major changes, visually separating Suggested, Confirmed and Rejected.

Lane headers carry visibility/solo-style controls and context menus; they do not introduce rows of standalone buttons.

### 5.3 Direct manipulation

- Dragging Source In/Out or fade handles previews exact time and frame values and commits one `FScopedTransaction` on release.
- Shift constrains to confirmed beat/grid positions; Command/Ctrl temporarily disables snapping.
- Handle crossing is prohibited. Fade lengths clamp inside the used range.
- Clicking a marker selects it. Double-click auditions from a short pre-roll. Right-click offers Confirm, Reject, Return to Suggested, Rename and Set as Grid Origin where applicable.
- Dragging a confirmed manual marker creates a manual edit record; reanalysis does not silently move it.
- Wheel/trackpad zooms around the cursor; horizontal drag pans; Home frames the whole used range; F frames selection.

### 5.4 Audition isolation

Editor audition uses one non-spatial preview owner. Starting audition stops any previous rail preview. Starting PIE stops editor audition. Passage world location never affects gain or starts playback. The header visibly states `AUDITION`, `PIE MASTER`, `EXTERNAL`, or `SILENT` as the current audio authority.

### 5.5 Music scrub drives the visual stage

Horizontal timeline position maps through one exact chain:

```text
Timeline X
→ Rail source sample/time
→ Passage-local frame
→ Master frame
→ camera distance/pose + Wing mechanism phase + shadow-figure pose
```

There is no second preview-time variable. The same absolute frame used by Sequencer is submitted to the existing camera and Passage evaluators.

In the Editor outside PIE:

- mouse-down acquires a transient Preview context and records the current preview/camera state;
- dragging evaluates the existing serialized Passage camera, Wing Pair instances and shadow-figure rig at a throttled display rate while preserving exact final-frame evaluation;
- the Level viewport may **Follow Preview Camera** or remain free while showing the active camera frustum;
- the nearest passed Wing row receives a non-selection playhead highlight, so list selection is not destroyed;
- preview evaluation does not materialize components, save transforms, dirty the map, fire mechanism transients or start a world-position sound player; and
- mouse-up either holds the preview frame or restores the pre-preview pose according to a visible Preview Hold toggle.

In PIE, the timeline requests a safe scrub/jump on the root Sequence Player. Music is muted/stopped while continuously dragging unless explicit bounded Scrub Audio Preview is enabled; release reconstructs the managed Rail at the landed Master frame. Performance-mode external-sound restrictions remain authoritative. Scrubbing within an unsafe external Scene is refused rather than moving visuals alone.

Selecting or scrubbing a different Passage also focuses its bay only when **Follow Passage in Viewport** is enabled. This avoids the Level camera flying hundreds of metres while an artist is making list edits.

### 5.6 Scrub performance and restoration

- Coalesce pointer events to at most the active viewport/display cadence; never rematerialize on every mouse move.
- Update existing batched instance transforms using absolute mechanism phase.
- Cache base transforms and compiled cue/pass lookup for the active Passage.
- Evaluate the exact pointer-release frame even if intermediate samples were skipped.
- Cancel on Escape, map close, asset switch, PIE transition or Cue Desk destruction and restore safely.
- Preview state is transient and excluded from undo/redo and package dirtiness.
- Direct seek, sequential playback and editor scrub must produce tolerance-identical camera and Wing transforms at the same Master frame.

## 6. Music-led Fit workflow

### 6.1 Selected-Passage Fit card

Replace the current temporary Fit values with the selected Passage's real values:

```text
Authority        Music used range (Locked)
Music            01:36.300
Preferred camera 2.50 m/s
Spacing          5.00 m
Entry / Exit     2.50 m / 2.50 m
Derived count    48 Wing Pairs
Compiled route   240.00 m
Residual         +0.75 m
```

Editable fields use explicit lock/pin states. Changing camera speed previews a new count; changing count previews the required speed; changing spacing previews count and route. Nothing is committed until **Apply Fit**. The existing reset action becomes **Reset Count to Music-Derived Default** and remains available in the Fit menu and selected-Passage context menu.

### 6.2 Fit modes

Overnight implementation supports three named policies:

- **Music Locked — derive count** (default): retain music, camera speed and spacing; derive count.
- **Music + Count Locked — solve camera speed:** useful after the artist has chosen the exact number of pairs.
- **Manual Passage:** retain explicit cue timing; show the music mismatch but do not repair it.

There is no generic auto-solver that changes whichever value happens to be unlocked. Named policies make the consequence predictable.

### 6.3 Applying count changes safely

When increasing count, duplicate from a selected/template block only if one was explicitly chosen; otherwise append neutral Wing Pair rows and mark them `DESIGN NEEDED`. Never repeat a random ceiling/top mesh into a side slot. When reducing count, show the exact rows to be removed and require confirmation if any has unique design, tags, overrides, or manual anchors.

Every apply operation:

1. records one transaction;
2. preserves surviving Cue GUIDs;
3. creates fresh GUIDs only for added rows;
4. recompiles and validates;
5. refreshes only the affected persistent Passage; and
6. leaves the existing visible Passage intact if materialization preflight fails.

## 7. Right-wing handedness and facing repair

The current implementation proves why this needs an explicit pass:

- fixture creation assigns Left `Y=-600` and Right `Y=+600`, but supplies no independent right-side facing correction; and
- the Wing Asset Auditor can bake a negative-Y mirror into architectural mesh source geometry to force the tall edge outside.

That conflates corridor placement, front/back presentation and image handedness. The overnight repair is:

1. Extend the Wing Library record with explicit canonical front axis, expected outside edge and optional reversible Left/Right placement adjustment.
2. Stop proposing or applying automatic geometry mirrors. Axis, pivot, thickness and uniform scale corrections remain valid; photographic handedness requires preview/approval.
3. Audit material-slot/front presentation so the intended Front material is what the passage camera sees without mirroring the source photograph.
4. Add a paired preview in the Wing Audit: the same station viewed from the Passage camera with Left and Right corridor labels and the outside edges marked.
5. Detect previously baked mirror corrections from `AppliedCanonicalTransform` and offer **Preview Unmirror**, never an unannounced bulk rewrite.
6. Create a one-time Show repair diff for current Right assignments/local transforms, then rematerialize all affected Passages transactionally while preserving the previous visible stage on failure.
7. Keep neutral objects/buildings neutral unless explicitly assigned handedness.

The acceptance image is not merely “both assets are located on the correct side.” It must show the intended photographic content unmirrored, the correct material/front face toward the passage view, and the architectural tall edge outside where that rule applies.

## 8. Analysis and musical-control upgrade

### 8.1 Provider integration

The existing local NumPy provider remains the first provider. Add an editor-only cancellable analysis service that:

- resolves a stable local WAV source for the selected Sound Wave;
- fingerprints it and detects stale results;
- runs `Tools/InfinityStage/music_analysis.py` without network access;
- streams progress and supports cancellation;
- imports the resulting JSON through the existing safe importer;
- preserves prior Confirmed/Rejected decisions for the same source fingerprint; and
- reports unsupported codecs, missing source files or provider failures without changing the Cue Score.

If a draft MP3 has no reliable decoded-source path, prompt for import/conversion to a project WAV rather than pretending sample-exact analysis. Final performance recommendation remains 48 kHz WAV; playback continues through Unreal's imported Sound Wave.

### 8.2 Tempo review

- Show all ranked tempo hypotheses, including half/double-time alternatives.
- Permit exactly one active confirmed global tempo for the V1 grid.
- Display confidence as evidence, not truth; suppress percentages when the provider reports no calibrated support.
- Provide Tap Tempo and Set First Beat/Grid Origin from the timeline context menu.
- Passage 6 and any other non-metric track may remain `No stable tempo`; duration-led fitting still works.

### 8.3 Beat/pass assistance

The first useful assistance is not “auto-choreograph.” It is a bounded proposal:

- choose a subdivision or every N confirmed beats;
- select a Wing Pair range;
- keep the Passage start/end fixed;
- move pass anchors only inside configured timing and camera-speed limits;
- preserve cue order and monotone time/distance; and
- show every moved cue and maximum displacement before applying.

Three actions are planned:

1. **Show Beat Fit Preview** — overlay only, no asset edit;
2. **Apply Pass Anchors to Confirmed Grid** — explicit transactional retime within limits; and
3. **Create Guide Range at Major Change** — creates named, non-playback guide metadata, not a Scene or camera cut.

The fit can be artistically rejected without losing confirmed music markers.

### 8.4 Scope of “sophisticated” overnight analysis

The existing provider already offers credible waveform, onset, tempo hypotheses and spectral/loudness structural-change evidence. Overnight work productizes review and control around those outputs. It does **not** claim robust downbeat, bar, metre, rubato or formal-section understanding. Time-varying tempo maps, composer MIDI import and evaluated downbeat inference remain subsequent V2 work unless the core gate finishes early.

## 9. Managed Master and audio ownership

### 9.1 Rebuild contract

The Music Rail/Section binding remains authoritative. The plugin-owned Audio section is generated and should appear locked/managed in Sequencer.

Add a build manifest/hash so the Cue Desk can report:

- `CURRENT` — managed objects match the Show;
- `STALE` — Show/Rail changed since rebuild;
- `DRIFTED` — a managed Audio section was edited manually;
- `MISSING` — required track/section absent; or
- `INVALID` — source, range or ownership failure.

**Restore Managed Master** rebuilds plugin-owned objects only. **Adopt Managed Audio Edit** previews trim/offset/fade/gain changes and, when valid, writes them back to the Music Rail/Section binding. It never adopts unrelated artist tracks.

### 9.2 Exact range and fades

- Convert Sound Wave source range into the Show tick resolution without accumulating display-frame rounding.
- Honor Source Out instead of always extending the Audio section to Passage end.
- Validate that the used source range covers the Passage after offsets.
- Implement linear fades overnight and retain a schema slot for equal-power/custom curves.
- Standard generated Passage music is 2D/non-spatial and non-repeating.
- Explicit crossfade remains the only valid two-owner interval and must be structurally declared.

### 9.3 Readiness

The Show Root exposes current music owner, expected source position, rail readiness and last reconstruction result. A not-ready jump does not partially seek the camera and does not advance Master time. Playback preflight checks the current, next and previous transport Sections because reverse rehearsal is required.

## 10. Author and Operator modes

### 10.1 Author mode

- Structural and property editing available.
- Timeline click/drag acts as editor preview or safe rehearsal seek.
- Analysis and fit previews available.
- Main Cue list retains current proportions.

### 10.2 Operator mode

Entering Operator mode runs preflight and then locks structural editing. The bottom header becomes:

```text
RUN — EDITING LOCKED   PREV   PLAY ◀   HOLD/RESUME   GO ▶   NEXT
TC 00:14:28:12   CURRENT P03   NEXT Scene 3   CAMERA Passage
MUSIC Master P03 ✓   PREV/CURRENT/NEXT READY   PERFORMANCE SAFE
```

The existing controller provides the command implementation. Overnight work adds:

- command/status delegates so the UI updates without polling thousands of rows;
- explicit `Playing`, `Held`, `Direction`, `Rate`, selected Section and last-error status;
- one-frame-exact boundary feedback;
- visible `Unsafe external sound` and `Audio not ready` reasons;
- configurable keyboard mappings with text-entry guards; and
- a command API surface ready for later OSC/MIDI/Stream Deck adapters.

Suggested defaults: Space = GO/Hold according to current state, Left/Right = previous/next Section selection, Shift+Left/Right = reverse/forward to boundary. These are stored in Editor settings and remain rebindable.

## 11. Overnight implementation order

### Core run — 14 hours

| Elapsed | Work | Concrete output | Gate |
| --- | --- | --- | --- |
| 00:00–00:30 | Safety baseline | Record current build/tests, snapshot changed-file ledger, inspect newest crash/403 evidence, close Editor for reflected-code changes | Existing suite green |
| 00:30–01:30 | Right-wing facing/handedness | Separate side/facing/handedness metadata, stop automatic mesh mirrors, paired preview and current-Show repair diff | Intended image/front/outside edge pass without destructive guessing |
| 01:30–02:45 | Music/fit model | Fit authority enum, fit snapshot/result, selected Passage resolution, rail duration/source-range helpers, validation and serialization version | Unit tests for six real rails and exact 240 s example |
| 02:45–04:00 | Music-led Fit UI | Real selected-Passage values, named fit modes, diff preview, reset-to-music count, safe apply/undo | No temporary Fit state; zero silent edits |
| 04:00–06:15 | Interactive Music workspace + visual scrub | Extract timeline widget, zoom/pan/ruler/playhead, handles/overlays, Master-frame preview context, camera/Wing evaluation and restoration | Same frame gives same visual state; no map dirtiness or transient audio burst |
| 06:15–07:45 | Three-pane and Nested Cue UI | Responsive Cue/Cue Inspector/Music layout, derived Passage tree, one-level Groups, collapse and transactional drag/reorder | Flat and Nested compile to identical chronology; cross-Passage drop previews consequences |
| 07:45–08:45 | Analysis Review | Suggested/confirmed/rejected filters, tempo choice, marker context actions, stale state, async selected-rail analyze/reimport if provider launch is stable | Analysis never changes cue count/order/timing |
| 08:45–09:45 | Managed Master sync | Build hash/status, exact Source Out and fade validation, Restore/Adopt preview, one-owner diagnostic | Rebuild twice is idempotent and preserves artist tracks |
| 09:45–11:00 | Operator/control surface | Author/Operator modes, transport/status delegates, compact controls, error reasons, keyboard commands, current/next/readiness display | Exact boundary and external-sound safety tests |
| 11:00–11:45 | Beat/pass proposal | Accepted beat grid, pass overlay and bounded diff-only fit; transactional apply only if its tests are green | Direct seek and monotonic timing preserved |
| 11:45–12:45 | Project integration | Exercise all six rails, Right-wing repair preview, rebuild Master, reopen Cue Desk/Sequencer, Editor scrub and PIE Passage→Scene→Passage | One camera/music owner; fixed stage remains visible |
| 12:45–14:00 | Hardening/handoff | Full automation twice, clean Editor reopen, responsive-layout and scrub smoke tests, audio-device smoke where possible, logs/report/screenshots | No new feature after final gate begins |

### Stretch reserve — up to two additional hours

Stretch work begins only if the full Core gate is green:

1. time-varying tempo-segment data and manual grid-correction anchors;
2. improved energy/novelty lane and labelled change evidence;
3. a first camera-speed automation lane generated from a reviewed musical range;
4. equal-power crossfade UI for an explicitly declared Passage/Scene transition; or
5. a basic Passage mechanism-sound profile schema/UI, without claiming the full pooled scheduler.

The order above is the preference order. No stretch feature may destabilize the Cue Desk, Master ownership or operator transport.

## 12. Implementation boundary

Expected files/modules:

- Runtime: music-fit/authority structs and solver helpers; Cue Group/range metadata; transport/music status; Show Root readiness; serialization/custom version changes; managed Audio metadata; side/facing placement metadata.
- Editor: extracted Music Timeline/Workspace widgets; absolute-frame preview context; three-pane/Nested Cue view; commands; per-user layout settings; fit diff model; analysis task wrapper; Master drift inspector; handedness preview/repair diff.
- Tests: music range/fit, scrub equivalence/restoration, tree/flat reorder, marker review/reimport, widget construction and interaction, managed rebuild/adopt, orientation, transport/error state and saved-show integration.
- Documentation: updated overnight report, operator quick-start and music-authoring quick-start.

Do not add the full mechanism-audio pool, general automation-lane framework, route generator, hardware adapter, World Partition streaming scheme, or source-mesh correction work to the core overnight path. Those remain valid roadmap items but are independent of the music/control upgrade.

## 13. Test plan

### 13.1 Music and fit

- full source duration and explicit In/Out duration;
- invalid/crossed handles and fades longer than the used range;
- zero/one/many Wing Pair Passages;
- exact music-locked count for 240 s, 2.5 m/s, 5 m spacing and half-spacing clearances;
- residual-distance reporting and deterministic count rounding;
- Music + Count Locked camera-speed solve;
- Manual mode mismatch reporting;
- count increase/decrease diff, stable GUID preservation and undo/redo;
- no role-invalid ceiling/top asset copied into a side slot; and
- failed materialization preserves the previously visible Passage.

### 13.2 Analysis

- deterministic provider golden tests;
- all six supplied WAVs analyze without user input;
- same-fingerprint reanalysis preserves decisions;
- changed fingerprint reports stale and does not inherit decisions silently;
- silence/no-tempo and half/double ambiguity remain honest;
- Confirm/Reject/Reset state survives save/reload;
- Cancelled analysis leaves the current Music Map intact; and
- no analysis action changes Cue GUIDs, count, order, interval, gap or camera settings.

### 13.3 Timeline/UI

- construct with no Show, no rail, no map, one cue and the full fixture;
- resize/collapse/detach/restore at 1280×720 and a wide desktop size;
- persistent split ratios do not trap a pane off-screen;
- zoom/pan and frame-selection remain finite at zero/very long durations;
- marker/handle hit tests choose the visually nearest item deterministically;
- a drag creates one undo transaction, not one per mouse move;
- multi-selection and Passage switching preserve correct context; and
- text-entry focus cannot trigger transport shortcuts.

Additional synchronized-scrub and hierarchy checks:

- dragging to a Master frame produces the same camera, mechanism and shadow-figure transforms as sequential playback and direct Sequencer seek;
- skipped intermediate mouse events do not change the final pose;
- editor scrub does not dirty the map/Show, rematerialize, fire mechanism transients or start Passage world audio;
- cancel, asset switch, Cue Desk close and PIE transition restore preview state safely;
- Follow Preview Camera and Follow Passage can be disabled independently;
- Flat and Nested modes expose the same enabled cues in the same canonical order;
- Group move preserves internal order/GUIDs and one-step undo restores the exact prior order;
- cross-Passage drop shows a fit/music/route diff and Cancel changes nothing;
- three-pane, two-pane and narrow layouts retain selection and stay above minimum usable sizes; and
- Cue and Music inspectors remain simultaneously visible in the wide default.

### 13.4 Master and live control

- two rebuilds create identical managed identity/count/ranges;
- ordinary artist tracks survive rebuild;
- Source In/Out/fades map to exact managed Audio section values;
- manual managed drift is detected; Restore and valid Adopt work transactionally;
- current defining-music owner count is 0/1 except declared crossfade;
- every operator command lands/holds on the exact declared frame without overshoot;
- Passage→Scene→Passage reports the correct camera and music owner;
- external-unpausable Performance command is refused without moving time/camera;
- Rehearsal movement clearly reports external audio unsynchronized;
- not-ready target leaves current time/camera/music unchanged; and
- play, direct seek, reverse landing and clean reopen yield the same visual state.

### 13.5 Regression and scale

- existing Wing Audit, viewport selection/edit, materialization and 3,000-row compile tests remain green;
- no per-Wing Actor or Tick is introduced;
- timeline drawing uses cached/decimated geometry and remains responsive with thousands of pass markers; and
- full saved fixture opens in Cue Desk, Sequencer and PIE from a clean Editor session.

### 13.6 Wing orientation

- Left/Right route position, material-facing direction and photographic handedness are tested independently;
- automatic audit never applies a negative-scale photograph mirror;
- explicit artist-approved mirrored variants remain possible and visibly labelled;
- previously mirrored correction can preview/revert using recorded correction metadata;
- Right architectural examples show the declared outside edge on the corridor exterior;
- neutral objects do not receive arbitrary Left/Right flips; and
- one failed repair/rematerialization leaves every prior visible component intact.

## 14. Crash and 403 recovery loop

Run the recovery audit at the baseline, every 60–90 minutes, after each Editor reopen, and before morning handoff.

1. Record the exact action/test, local timestamp, process result and last green checkpoint.
2. Inspect `Saved/Logs`, `Saved/Crashes`, the macOS Unreal crash report and any tool request/status record.
3. Classify separately: compile error, Unreal assertion/crash, process termination, HTTP 403, port conflict, cloud-sync placeholder, or unknown.
4. Reproduce once with the smallest exact action. Do not begin with the full suite.
5. Repair the smallest cause, rerun the exact test twice, then rerun the preceding green gate.
6. For an HTTP 403, do not retry in a loop. Preserve local work, identify the actual service/request, continue through the offline provider where possible, and retry only at the next scheduled checkpoint.
7. For the known Master Sequence risk, explicitly open/close the managed Master after every track-editor or managed-track change.
8. For Cue Desk risk, open with null asset, development asset, multi-selection and collapsed Music workspace.
9. Quarantine a path after three identical unresolved failures, preserve a minimal reproduction, and continue independent core work.

Recovery is credited only after two exact passes and a clean Editor reopen where Editor state was involved. The morning report lists all crashes/403s, including zero occurrences, rather than relying on memory.

## 15. Morning acceptance gate

The upgrade is **Core Complete** only when:

- the selected Passage's music source range actually drives the Fit card;
- reset-to-music derives the count while keeping preferred camera speed;
- the lower Music workspace is interactive, collapsible and restores its layout;
- timeline scrub visibly evaluates the fixed wings/camera at the exact Master frame without dirtying or regenerating the stage;
- the wide default shows Cue Score, Cue Inspector and Passage/Music Inspector simultaneously;
- Flat/Nested views preserve one authoritative order and support safe block reordering;
- Right-wing content is correctly faced/handed without automatic photographic mirroring;
- fades and source handles edit transactionally from the waveform;
- beats/onsets/changes can be reviewed without mutating cues;
- one accepted tempo can display a grid, including an honest no-tempo state;
- a beat/pass change is previewed before any explicit apply;
- the managed Master reports current/stale/drifted status and rebuilds idempotently;
- Operator mode drives the existing root Sequence Player and shows current/next/camera/music/readiness;
- Performance mode refuses unsafe external-sound movement visibly;
- all six supplied Passage rails reopen and bind correctly;
- fixed wings remain editor-visible and are not regenerated in PIE;
- the full Infinity Stage automation suite passes twice; and
- Cue Desk, Master Sequence and saved vertical-slice map survive a clean UE 5.8 reopen.

## 16. Morning handoff

Deliver:

1. an updated build report with Core/Stretch status;
2. a short Music authoring workflow: assign rail → trim/fade → analyze/review → fit → rebuild;
3. a short Operator workflow: preflight → GO/Hold/Previous/Next → external-sound warning behavior;
4. screenshots of Author mode, expanded Music workspace, collapsed Music strip and Operator mode;
5. exact automated test results and the six-rail integration result;
6. managed Master ownership/drift result;
7. crash/403 ledger and evidence paths; and
8. the next three roadmap tasks, reordered from real overnight findings.

## 17. Roadmap immediately after the overnight

1. **Musical automation:** general range lanes for camera-speed/timing and mechanism-rate with phase-continuous loop integration.
2. **Music intelligence V2:** time-varying tempo, bar/downbeat correction, MIDI/composer map import and evaluated provider quality.
3. **Performance audio:** exact codec/seek validation on the live machine, output bus/submix controls, latency calibration and explicitly declared crossfades.
4. **Mechanism sound:** motion-derived pooled spatial creaks/squeaks with deterministic seek/reverse policy.
5. **Camera/Scene handoffs:** authored entry/exit pose and lens matching, transition Sequence tools and external control adapter once its protocol is known.
6. **Stage authoring:** range automation, route editing/clearance, anchors, Ground Zones and shadow-figure lighting proof.

This sequence keeps music and live control as the organizing rails while preserving the fixed-stage, manually lit authoring model.
