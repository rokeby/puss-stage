# Session handover — 2026-09-25

## Current consolidated checkpoint — 25 September

Plugin **0.15.0-container-look**. Full suite **45/46** on a clean build with the
new code proven present in both DLLs. The single failure is the long-standing
`PussStage.InfinityStage.Functional.SavedFixturePIE` curtain-marker assertion,
unchanged since 14 September. **Do not describe the suite as green.**

### Facts from the night of 25/26 September that outlive their session

**There is no visible light shaft in Passage 1, and volumetric fog is currently
net-NEGATIVE.** A four-state console A/B at beam bay 005, captured offscreen with
the `VolumetricFog` show flag forced on, gave means of 4.367 baseline, **6.419
with fog off**, 4.563 with `r.VolumetricFog.UseLightFunctionAtlas 1`, and 4.422
with MegaLights additionally off. Fog off is the brightest state: the haze removes
roughly a third of the light and returns nothing. The brightest half-percent of
pixels (p99.5) is 54–59 in every state, so no faint shaft is being missed.
The light-function atlas is **not** the cause. The cause is direction: with
g=0.55 forward-scattering haze and every beam lamp throwing away from the camera,
only back-scatter is ever seen — about 16× dimmer — while extinction applies to
the whole corridor. **The fix is a rig change, not a fog change**: lamps ahead of
the audience throwing back toward it. Re-judge fog density 0.022 only after that
lands; it was tuned against a rig that could never show shafts.

**"The save only contains my change" is never quite true for a level.** Any level
save also serialises evaluated-but-not-dirty state — rig transforms, wing ISM
instance transforms at whatever frame the editor last evaluated. Observed on
2026-09-26: a net-nil save shrank the .umap by about 200 KB. It is harmless for
playback, which re-evaluates everything, but it means a level diff or a file-size
delta is **not** a reliable measure of what a script changed, and that one
stream's save can persist another's in-memory level state. Verify by probing the
level's contents, not by inspecting the package.

**A passing guard proves what it checks, and nothing else.** A dirty-package
guard sees which packages are dirty, not what changed inside them. On 2026-09-26
one stream's save legitimately persisted another's in-memory level state for
exactly this reason — caught because the stream asked what its own guard could
not see.

**A freely-released sheet cannot sprawl.** Proven on 2026-09-26 across four
benches: with a stiff solver, 2 cm/side self-collision, high bending, no
buckle-softening, a 4-degree lean, low friction and a real 2.5 m/s gust, a
curtain released all at once still piles inside its own footprint and deflates
to a flat strip. Symmetric sheet, symmetric result — no solver tuning fixes it.

**What works is guiding the heading.** Keep the top row PINNED and carry it down
(gravity-timed) and FORWARD over about 1.4 s, as a falling batten would. The top
folds over the body and the cloth lands crumpled and spread 2–3 m deep. Forward
distance is the dial: 0 m narrow, 3 m, 6 m progressively sprawled. It is a
transform track on the cloth component, so it is **directable in Sequencer** and
draggable in the editor with Simulate In Editor on — a staging decision rather
than a physics parameter. This is the Kabuki *furi-otoshi* made literal.

**The fall has three directable dials**, established 2026-09-26:
1. **Forward distance** — how far the heading travels. 0 m narrow, 3 m, 6 m
   progressively sprawled.
2. **Drop speed** — and this is the surprising one. A *faster* drop (0.9 s rather
   than 1.4 s) **billows on the way down** and lands as the most crumpled,
   overlapping heap. Speed buys crumple, not just urgency.
3. **Fabric weight and stiffness** — bending 0.8 with no buckle-softening and
   3 cm/side self-collision at stiffness 1.0 turns fine crinkle into **broad heavy
   folds**; it stops reading as silk. Grip (0.9 cloth-on-cloth, 0.8 floor) holds
   those folds; damping plus 3 self-collision substeps adds crumple.

So a curtain's fall is staged, not tuned: three values a director sets by eye.

**Chaos cloth gathers environment colliders from the component's BOUNDS, and
those bounds are the REFERENCE POSE, not the simulated state.** A cloth lifted
away from its rest position stops overlapping the floor it should collide with,
so the floor is never gathered and the cloth falls straight through. Found
2026-09-26: the placed curtains only land because their hem sits exactly at z=0,
touching the top of their catch box — that is luck, not design, and it breaks the
moment anything is raised, flown or retimed. A bounds scale of ~2 on the cloth
component was tried and **did not fix it** — a lifted cloth still fell straight
through its catch box. **The correct fix is not known.** Suspect this first
whenever cloth ignores a collider it clearly overlaps on screen, and do not
assume the bounds scale resolves it.

**Chaos cloth wind is in m/s, not cm/s** — unlike almost every other length in
this project, which is centimetres. The Aerodynamics node's own header says a
gust is above 8 m/s. Entering 250 or 400 (thinking cm/s) is a hurricane and
launches the cloth out of frame. Relevant to anything using wind, including
Effects' silk flames.

**Editor screenshots: use an offscreen SceneCapture2D, not HighResShot.**
`take_high_res_screenshot` and console `HighResShot` return a stale or black frame
whenever the level viewport is not the visible, focused window, and
`set_level_viewport_camera_info` addresses a different viewport client from the one
that is captured. `Saved/CodexConductor/capture_probe.py` spawns a transient
SceneCapture2D, captures through its own pipeline, exports a PNG and destroys the
actor; it works with the editor behind another window. Two caveats: it leaves the
**map flagged dirty** although the net change is nil, and there is no Python API to
clear that flag (checked on `Package`, `EditorLoadingAndSavingUtils`,
`SystemLibrary` and `EditorAssetLibrary`); and always force the `VolumetricFog`
show flag explicitly before drawing any fog conclusion from a capture.

**The Show compile is ~0.05 ms (274 cues, measured 2026-09-25) and runs ~5× per
playback frame** — ShowRoot's owner and curtain queries, the camera rig, and
Passage mechanisms. **Deliberately not cached**: the Show is mutated without
`Modify()` (`EnsureStableIds` and `ReconcilePassageSettings` inside
`InitializeTransport`; the suite edits fixtures then evaluates within one frame),
so a cache invalidated by editor delegates would serve stale segments — a wrong
camera owner or curtain state, with the dog driving. See
`InfinityStageCameraRig.cpp`, `EvaluateAtMasterFrame`.

**There are two authoring authorities, not one.** The Show asset owns cue content
and attachments. The **Master Level Sequence owns time and the Passage camera** —
a camera write-back keys its channels and must not touch the Show, and a camera
key therefore saves the Master package, so snapshot that before camera work.

**`FTransform::Equals(Other, 0.5f)` applies the tolerance to quaternion components
as well as translation**, so `InfinityStageSceneHandoffBuilder.cpp` currently
accepts a handoff camera re-aimed by roughly 60° as "matching". A pure re-aim of a
Passage end camera never registers as stale. Compare location to 0.5 cm and
`FQuat::AngularDistance` to ~0.05° instead.

**A channel with exactly one key is constant everywhere**, so a lone mid-Passage
camera key redefines `SegmentEndFrame` — which is where Scene handoffs snapshot,
so setting a value mid-Passage silently changes a handoff two segments away.
**Do not "fix" this.** Gary confirmed on 2026-09-26 that single-key holds are his
deliberate way of setting a Passage-wide constant. It is a working authoring
method with a side effect; the handoff watch exists to surface that side effect
for a match-or-keep decision, not to stop it happening.

**Wing image UVs are not mesh bounds.** The source images carry transparent
margins: the cloud ceiling's UV covers 4726 × 1889 cm on a 2129 × 1000 cm mesh.
Anything placing effects or damage by UV must use measured spans.

**Two Landscapes exist, not one** — "Passage 1 - ForestedLandscape" and
"Passage 3 - Wet Ground" — both near z=0, so mesh ground at z=0 will z-fight until
they are removed.

**P03's cue labels do not run in route order** (Wing 002 sits upstream of 001), and
Passage 5 reuses labels `P05 Wing 001..008` across different rows. Sort by route
position; never trust label order.

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
