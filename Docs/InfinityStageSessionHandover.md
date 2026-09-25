# Session handover — 2026-09-25

## Current consolidated checkpoint — 25 September

Plugin **0.15.0-container-look**. Full suite **45/46** on a clean build with the
new code proven present in both DLLs. The single failure is the long-standing
`PussStage.InfinityStage.Functional.SavedFixturePIE` curtain-marker assertion,
unchanged since 14 September. **Do not describe the suite as green.**

The project has moved from "wings passing on a travellator" to building the
**container**: a Baroque stage machine the audience travels inside. Direction,
stream ownership and per-stream briefs are in `Docs/Conductor/`, which is now
the first thing a new session should read after `AGENTS.md`.

### Infrastructure — 25 September

- **Version control is split.** Source, tooling, docs and config are now in
  **git** at the project root (541 files, 5 MB; Content excluded by
  `.gitignore`). `AGENTS.md` previously told every session the project had no
  git repository — corrected.
- **Full snapshot** at `D:\PussStageBackups\FullSnapshot-20260925-1853`:
  16,982 files, 62.8 GB, verified, Show and level byte-identical to live.
- **`README.md`** written for a person with no AI session open.
- **MCP ports separated.** Both projects were configured for 8000 and MHFat won
  the race, so Puss scripts were being addressed to the **MHFat** editor.
  PussStage now owns **8010**; MHFat keeps 8000, untouched.
  `Saved/CodexMocap/mcp_request.py` defaults to 8010 and takes `--url`.
  **Every Puss script must assert the expected world before mutating.**
- Note: any open Unreal editor blocks builds via Live Coding, **including
  MHFat's**. The build gate is global, not per-project.

### Built and verified — 25 September

- **Mouse stand-in for the dog.** Deliberately the same path the robot drives —
  same rotation write, pitch limits, recentre and Show camera ownership — so it
  only acts where the dog would. Set Live Camera Owner to **Force Dog** and the
  mouse looks around; under Timeline it stays hands-off. One fresh telemetry
  packet and the mouse stops contributing. Logs `GO1_MOUSE_LOOK_ACTIVE`.
- **Passage details-panel stall fixed.** Selecting a Passage took 10–20 seconds
  because the details view built rows for `MaterializedPanels` and
  `ManagedAttachmentActors` — 279 structs and **837 actor-reference pickers** on
  Passage 5. Now a one-line summary.

### Lighting and atmosphere — 25 September (saved)

Volumetric fog was **already enabled**; the problem was **fog density 0.5**,
effectively opaque past a few metres, which is why distance read as flat colour.
Now density 0.022, height falloff 0.12 (was 0.34, which starved the upper
corridor), extinction 0.9, scattering distribution 0.55.

**136 beam fixtures** — the two cross spots on every 4th bay — at volumetric
scattering 9.0 with volumetric shadows; the other **2,382 at 0.6**. Persisted
into the Show's light attachments, verified against live actors after
rematerialize, Show and level saved.

The finding worth keeping: raising scattering on all 2,257 fixtures produced
uniform fog soup. **Discrete beams need discrete sources.** And haze is only
visible where light is in or behind it — a far corridor reading as black is a
missing-practicals problem, not a fog problem.

### Gridiron preview — 25 September (saved, but Python)

`Saved/CodexLighting/gridiron_build.py` generates **771 beams** over all six
Passages: one cross beam per wing station plus continuous side rails, at 1150 cm
with 220 cm overhang, 26 × 34 cm section. Stations are derived from
`MaterializedPanels`, so it shares the wings' rhythm and re-fits automatically.
Regenerable by the tag `InfinityStage.Gridiron`; destroys only its own output.

It is **grey engine cubes and a Python preview** — components created this way
may not survive save/reload cleanly. Promoting it to a C++ `MaterializeStructure`
pass is the Rig & atmosphere stream's first job.

### Route

Passage 1 was banked to ~13° as a test of the "rolling music box" feeling and
then **reverted; the route is straight, auto-fit is back on**. The agreed target
is a **closed ring with rise and fall**, not yet applied. Banking is nearly free
architecturally — wings and camera both take their full transform from the route
spline — but **Passage 1's `Landscape` actor (192 references) cannot curve** and
must be replaced with mesh ground first.

### Not yet done

Ground grooves and wooden floor, Landscape removal, wall bays, light fixture
bodies, wing materiality, effects sources, the Scene transitions, the curtain's
material and its Sequencer swap.

## Earlier checkpoints

## Opening and PIE keyboard repair — 14 September

The opening now establishes Passage 1's starting view, uses a lens-sized
foreground curtain, and automatically holds at Passage 1 after its existing
15-second sequence. The PIE viewport has Space play/hold and Left/Right segment
navigation. Starting at the Cue Desk playhead respects Show autoplay, and
starting playback after a jump preserves the newly selected camera.
The Passage evaluation template also rejects swept times at its exclusive end,
preventing a delayed camera takeover on the first Scene tick. See
[Opening playback repair](OpeningPlaybackRepair-20260914.md) for operation,
scope, backup and final verification evidence. The full suite remains 43/44:
Interaction 1's authored 0.61 curtain value differs from the test's expected 1.0;
the other curtains' visual coverage is not signed off by this opening repair.

## Current transition checkpoint — 14 September

Passage-to-Scene repair is implemented and verified in normal PIE on UE 5.8.2.
The production Show Root now enables automatic Passage → Scene playback; all
six Scene cues use their containing sequence lengths. Scene 3's cut gaps are
closed, its authored timing is preserved, and the managed Master is rebuilt.
All six handoff cameras match their Passage endpoints. Normal PIE verified all
six transitions and Scene-end holds, plus the six Shore bodies under the one
Show player. An uninterrupted Passage 3 run reached `ClamCam1` and the Shore
animation, with inspected game-viewport captures.

The current full regression result is **43/44**. The remaining failure is the
same `SavedFixturePIE` fully-lowered curtain-marker assertion recorded below.
The level was saved/reloaded; automatic Scene playback and all thirteen
sequence-derived cue lengths survived. See
[Scene transition repair](SceneTransitionRepair-20260914.md) for operation,
backup paths, source/state/rendered evidence and remaining limits. In particular,
Scene 3 retains its authored 23.56-second lead-in before `LS_Clams` begins.

The 28 August record below is retained as history; the checkpoint above
supersedes its playback behavior, sequence-length debt and latest suite count.

## Previous handover — 28 August

Supersedes the 22 August state. The 17 August handover is kept at
`Backups/PrePCSwitchover-20260822-1450/InfinityStageSessionHandover-17Aug.md`.

The active Windows project is **`E:\PussStage`** with Unreal Engine 5.8 at
**`D:\Unreal Engine\UE_5.8`**. The plugin manifest is still
**`0.13.0-stage-light-authoring`**; the curtain, rehearsal and Cue Desk work
below was layered on top without another manifest version bump. Keep using
`Docs/WindowsBuildProcedure.md` for clean-build discipline; `Docs/PCMigration.md`
is now the completed migration record.

## 0. Historical PC baseline (28 August)

- The production Show remains the authority:
  `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`.
- The production level is
  `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`.
- Unreal MCP is proven on Windows at `http://127.0.0.1:8000/mcp`. The project
  config and Editor auto-start setting are present. Use the guarded
  `ExecuteProjectPythonFile` route in `Docs/CodexUnrealMCPRunbook.md`.
- The 28 August editor health check ended on the production level, outside PIE/SIE,
  with zero dirty content and map packages.
- The complete UE 5.8 run at that checkpoint was **42/43**, not green. The sole failure was
  `PussStage.InfinityStage.Functional.SavedFixturePIE`: the interaction sequence
  was not evaluated as fully lowered at its hidden-changeover marker. The same
  test passed in the focused curtain rerun immediately after the staging repair,
  so treat this as order/state-sensitive test debt until diagnosed. Evidence:
  `Saved/Logs/CueDeskTransformUI-FullInfinityStage-20260828.log` and
  `Saved/Logs/CodexCurtainStaging-SavedFixturePIE-20260828-Rerun.log`.

Do not claim a green suite or visually correct curtain composition from this
headless evidence. Source/state verification is strong; final rendered framing
still needs a human PIE/offscreen review.

## 1. Recent workstreams (27–28 August)

### Fire-safety curtain production asset

`WingCutoutPipeline` generated a V2 curtain source at
`DerivedAssets/FireSafetyCurtainV2/GeneratedWings/FireSafetyCurtain_01`: FBX,
editable Blender file, Base/alpha, height and DirectX normal maps, plus a relief
preview and generation report. The mesh is 17.770 × 10.000 × 0.100 metres with
applied transforms, one UV map, Front/Back/Edge slots, manifold triangulated
geometry and no degenerates.

It is imported under `/Game/Scenes/Wings/FireSafetyCurtain`. The relief material
uses the curtain's own Base, `OpacityMask`, Height and Normal textures; the
initial accidental Bamboo opacity fallback was corrected. The current Base
Color is the 3840 × 2160 TextileV5 weave. Clean read-back evidence:
`Saved/Logs/FireSafetyCurtain-TextileV5-Verify-20260827.log`.

This is a visual production asset, not evidence of real-world fire-rating
compliance. Independent weave tiling/normal-strength controls remain a possible
material refinement; they are not implemented.

### Curtain sequencing, staging and rehearsal transport

The production Show now compiles to the intended **19 segments**: seven SEQ
blocks (opening, five interactions, closing), six Passages and six Scenes. The
managed Master contains six Passage sections and thirteen Scene/SEQ sections.

The sequence-owned curtain uses
`/Game/InfinityStage/Interactions/BP_InfinityStageSequenceCurtain` and the
fire-safety curtain mesh at
`/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/SM_FireSafetyCurtain_01`.
There is an opening sequence, a reusable interaction template, five interaction
sequences and a closing sequence. Each carries the standard folders
`01_Curtain_Foreground`, `02_BoyCat_Behind_Curtain` and
`03_Light_Shadow_Audio_VFX`.

The five interactions and template are 500 frames at 25 fps: 0–75 curtain fall,
75–375 boy/cat performance window, frame 375 hidden Passage changeover,
375–400 fully covered safety beat, and 400–500 curtain rise. The Show retains
the preceding SceneExit camera and the sequence owns the curtain; do not add a
second runtime curtain.

Cue Desk rehearsal entry is no longer blocked by external-clock locks. The
visible **Rehearsal** toggle applies the bypass to live PIE; **Play Selected**
cues a selected Scene or SEQ at its exact first frame and plays it to the
boundary; Next Segment auto-plays SEQ/interstitial cues while Passage and Scene
cues hold at their exact start.

The sequence/state verifier passed with zero problems and zero dirty packages:
`Saved/CodexCurtainAuthoring/verify_curtain_staging.json`. Backup:
`Backups/PreCurtainStagingPass-20260828-002939`.

**Still creative/rehearsal work:** the actual boy/cat performance, audio,
lighting and effects are not authored. The curtain's full-screen coverage,
depth order and absence of a one-frame background flash need a rendered visual
check in all five interactions. Keep the latest full-suite failure above open.

### Passage 2 wing opacity repair

All **60** material instances used by Passage 2's Left, Right and Top wings now
use their own wing texture for `OpacityMask`. The initial audit found 54 Bamboo
Scaffolding assignments, one wrong right-wing texture and five already correct.
All 23 Passage 2 pairs were rematerialized and the level saved; the Show Asset
was unchanged. Independent read-back reports 60/60 matches, zero Bamboo masks
and zero dirty packages:
`Saved/CodexWingIntegration/verify_p02_opacity_masks.json`. Backup:
`Backups/PreP02OpacityFix-20260827-2201`.

### Duplicate stationary Passage 1 wings

The duplicate was not a second Stage Director or Passage actor. Passage 1 had
eight orphaned `InfinityStage.Managed` ISM components whose references had been
lost, leaving 144 stationary instances beside the tracked set. Materialization
cleanup now discovers and destroys all actor-owned tagged components, including
lost references, and has focused regression coverage.

Current read-back shows zero orphan components in every Passage. Passage 1 has
48 pairs, 144 references and eight tracked ISM components. No map mutation was
required because reopening cleared the transient duplicate state. Evidence:
`Saved/CodexWingIntegration/verify_p01_orphaned_wings.json`. Backup:
`Backups/PreWingOrphanCleanup-20260827-1752`.

### Cue Desk transform/UI continuation

The third column is now a fixed **Passage / Music** inspector. The redundant
Fit/Route/Stage tab strip and its persisted tab state were removed; selected cue
properties, including stage attachments, remain in the middle Cue Details view.

**Refit Selected Passage from Music** moved into Actions and reads the current
authoritative Passage/Music values when invoked. Actions also has a
**Relative Transform** submenu: from one selected Wing occurrence, copy the
Left, Right or Top panel's saved location, rotation and scale to every use of
the same mesh. The Show's per-occurrence `LocalTransform` values remain the
authority; affected Passages are rematerialized.

Clean UE 5.8 build succeeded. The new transform test and Cue Desk construction
test passed. The full run reached the 42/43 state recorded above. MCP reopened
the Cue Desk on the production level and left zero dirty packages. No Show or
level asset was changed by this workstream. Evidence:
`Saved/CodexCueDeskTransformUI/verify_cue_desk_transform_ui.json`. Backup:
`Backups/PreCueDeskTransformUI-20260828-0149`.

## 2. Typed stage-light authoring (27 August)

Wing-pair Light attachments now materialize native **Spot**, **Rect**, or
**Point** actors when no custom Actor Class is supplied. The Show stores common
and type-specific parameters including intensity/units, colour/temperature,
attenuation, contribution scales, shadows, reflection/GI, lighting channels,
culling, Point/Spot source shape and falloff, Spot cones, Rect size/barn doors
and source texture, IES, and light functions. A custom light actor class remains
an override and receives the same settings on its first Light Component.

Cue Desk **Actions** now contains:

- **Add Missing Stage Lights to Selection** — idempotently ensures one Left-panel
  and one Right-panel light per selected Wing Pair.
- **Replicate First Pair's Lighting Across Selection** — treats the earliest
  selected pair as the template, replaces only Light attachments on the rest,
  preserves props/sounds/triggers, and keeps destination identities stable on
  reapplication.

A lifecycle regression found by the new test was fixed: native light parameters
must be applied after the spawned actor is made Movable and parented, otherwise
Spot cone/radius defaults can reconstruct. Clean UE 5.8 build succeeded. The
focused `InfinityStage.StageContent` group passed **4/4**. Its contemporary full
run was 41/42 because the saved fixture still expected an older cue count; that
  count mismatch was superseded when the 19-segment spine was authored. The
  27 August full-suite state was the 42/43 curtain-marker result recorded in the
  historical baseline; the current result is 43/44 in the 14 September checkpoint.
Lighting evidence:
`Saved/Logs/InfinityStageStageLightingTargeted2-20260827.log` and
`Saved/Logs/InfinityStageStageLightingFull-20260827.log`. Backup:
`Backups/PreStageLightReplication-20260827-1826`.

**21 September — Whole-Passage scope now follows the template pair.** The
`Replicate First Pair's Lighting` submenu has three scopes (Selection, Whole
Passage, Entire Show). Whole Passage previously resolved the Passage through
`GetSelectedPassage()`, which prefers the desk's remembered passage-header
selection and could be stale after segment navigation or a rename, so the
targets could come from a different Passage than the template. It now derives
the Passage from the template cue itself via the new
`UInfinityStageShowAsset::FindPassageGuidForCue` /
`GetWingPairCueGuidsInPassage`, rematerializes only the Passages that received
lights, and names the Passage in the notification and in the
`INFINITY_STAGE_LIGHT_REPLICATION_OK ... passage='…'` log marker. Workflow: tune
`P0N Wing 001` in the level, select it in the Cue Desk, run
**Whole Passage — Exact / With Variation**; only `P0N` changes. The other
"Whole Passage" mechanism actions share the corrected helper. New test
`InfinityStage.StageContent.LightReplicationStaysInsideTemplatePassage`. Backup:
`Backups/PreLightReplicationPassageScope-20260921-1118`.

Audit of the 18 September lighting state (evidence
`Saved/CodexLighting/replication_scope_verify.json`): the ten UI runs that
evening were all `scope=1` on `P01 Wing 001` (47 targets) and touched only
Passage 01. Passages 02–06 carry P01 Wing 001's template *as it stood at 19:22*,
put there by the show-wide Python passes `replicate_p01_template.py`,
`repair_row1_and_replicate.py` and `replicate_from_row1_show.py`
(`rows=261/260`), before P01 Wing 001 was re-tuned. They are not independently
authored.

## 3. Earlier handover debt already cleared

The 17 August handover opened with two features "written and compiling but never
verified". **Both are resolved.** Verified 22 Aug against the freshly built base
dylib:

- `AnalyzeSelectionMusic` — **6 occurrences** in
  `libUnrealEditor-InfinityStageEditor.dylib`, and **zero numbered
  side-libraries** in `Binaries/Mac/`. The symbol is in the base library, which
  was the exact condition that handover set.
- The Python analyzer side was already verified, and was exercised end to end on
  22 Aug: all six passage rails plus four scene stems regenerated at provider
  **0.3.0**, seven feature curves and expressive sections each.

Do not re-do this work. The Mac pass count (34/34) and 28 August PC count
(42/43) are historical. The current PC result is 43/44 in the 14 September
checkpoint above.

## 4. What changed on 22 August

| | |
| --- | --- |
| **M.1** | Analyzer interpreter made portable. `InfinityStageMusicAnalysisImporter.cpp` tried `/usr/bin/env`, which does not exist on Windows. Now tries `py.exe` then `python.exe` there, keeps `/usr/bin/env python3` on Unix, honours `INFINITYSTAGE_PYTHON`. Compile-verified. |
| **M.2** | All hardcoded `/Users/zhexi-mbp-22/…` paths removed from `Scripts/`. Resolvers are per-script by design — Blender and Unreal embedded interpreters do not reliably put the script directory on `sys.path`. |
| **0.1** | Music analysis regenerated at 0.3.0 (see above). **Not yet reimported into the Show** — that still needs Cue Desk → Actions → Link / Reimport Music Analysis. |
| **0.6** | The dev fixture no longer declares `DeclaredUnpausable` on silent placeholders. Rehearsal now has an explicit bypass and exact Scene/SEQ entry; performance-mode locks may remain deliberate and must not be cleared merely to make rehearsal work. |
| Docs | Eight new documents; see the map below. |
| Backup | `Backups/PrePCSwitchover-20260822-1450` — plugin source, `Scripts/`, and the Show asset, taken before the C++ edits. |

## 5. The trap that bit three times — and its Windows form

Building while the editor is open produced numbered side-libraries
(`libUnrealEditor-InfinityStageEditor-0002.dylib`). The base library kept the old
code, `.modules` still pointed at the base, and a headless test run then passed
against **stale binaries** — a false green.

Windows has the same class of problem as hot-reload DLLs, and additionally *has*
Live Coding, which patches a running process and is **not** a substitute for a
clean build before testing.

**Two lessons, both learned the hard way on 22 Aug:**

1. Close the editor, build, then prove the new code is present before trusting
   any result. `Scripts/pc_bootstrap.bat` now enforces this.
2. **A symbol check alone is not sufficient.** A function in an anonymous
   namespace can be inlined and export nothing — this happened with
   `GatherPythonCandidates`, which showed zero in `nm` while being perfectly
   present. Search for a **UTF-16 string literal** instead; `TEXT()` literals are
   UTF-16, so a plain ASCII `strings` finds nothing and looks like failure.

## 6. Document map

**Current working lists — these are authoritative for what to do next:**

- `Docs/ShowBuildTodo.md` — engineering
- `Docs/ShowCreativeTodo.md` — creative production
- `Docs/ShowRehearsalTodo.md` — rehearsal and venue

**The move:**

- `Docs/PCMigration.md` — completed transfer record and remaining migration debt
- `Docs/WindowsBuildProcedure.md` — replaces the macOS build steps
- `Scripts/pc_bootstrap.bat`, `Scripts/pc_migration_exclude.txt`

**Briefs and contracts:**

- `Docs/SceneDeliveryContract.md` — send with every scene brief
- `Docs/Brief_S5_Mountains.md` — included in the 15 September Rob package; external send is not confirmed
- `Docs/SoundDeliveryList.md` — for Cameron, needs lengths specified

**Reference and procedures:**

- `Docs/InfinityStageAuthoringReference.md` — how the system actually works
- `Docs/CodexUnrealMCPRunbook.md` — automation transport
- `Docs/Go1TelemetryProgress.md` — the dog
- `Docs/WingGenerationConventions.md` — V2 production Wing rules

**History, with caveat:**

- `Docs/PussProjectTaskTracker.md` — carries a **reconciliation block at the top
  dated 22 Aug**. Four items in its body are listed as outstanding but were
  verified already built. Read the block before acting on any row.

## 7. Known outstanding

- Diagnose the latest full-suite `SavedFixturePIE` failure and return J.1 to a
  genuine green state.
- Perform the rendered curtain composition pass, then author the five boy/cat
  interactions. Headless state proof is not visual proof.
- **Reimport the music analysis** into the Show.
- Camera piloting with write-back, the route/clearance visualizer, the MIDI
  import layer and surtitles remain open.
- P3 has one triangle mismatch and six role mismatches. P5 now reads back 93
  rows using 22 serialized meshes under the canonical
  `/Game/Scenes/Wings/Passage5_BirdToMountainV2` root; the unused similarly
  named root remains part of the broader content-root cleanup.
- Send or otherwise confirm receipt of the Rob and Klara transfer archives;
  neither local package proves external delivery.
- Finish the Mountains rewrite, Scene 5 surtitles and Cameron villager intake.
- Migration-specific: re-verify the GO1 chain on Windows and reconcile
  `DerivedAssets/` plus the shared V2 Wing-source locations.

## 8. User's working preferences

Unchanged from 17 August and still accurate:

Wants the honest verification state, not optimistic summaries — flag stale
binaries and unverified work explicitly. Prefers one restart cycle over several,
so batch C++ changes. Values knowing *why* a design was chosen, and pushes back
usefully when a proposal duplicates existing data.

Added 22 August: **check the code before trusting a tracker row.** Two documents
in this project have now sent work toward features that already existed.

Added 28 August: distinguish a successful source build, a saved Unreal read-back
and rendered visual proof. None substitutes for the other two.
