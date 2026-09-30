# Chaos Cloth curtain — pipeline and traps

> **26 Sep: the curtain FALLS, it does not fly** (Gary; `Docs/Conductor/BRIEF_TRANSITIONS_AND_SCALE_2026-09-26.md`).
> It is already down and lit; at the cue it drops to the floor and stays as a pile. It is the
> Kabuki *furi-otoshi*. **Chaos cannot un-pin at runtime**: the kinematic set
> (`KinematicVertices3D`) is baked when the simulation initialises, and changing MaxDistance later
> does not free those particles. So the falling asset `CA_<STEM>_Fall` pins **nothing**, and
> `BP_CurtainChaos` starts its ChaosClothComponent **suspended** (`bSuspendSimulation`,
> Sequencer-keyable), holding the hanging start pose. Un-suspending is the drop: it falls as a whole,
> the hem lands first, and it crumples up from the floor. The BP carries a hidden `FloorCatch` box (top
> at z = 0, WorldStatic, ignores Pawn/Camera/Visibility) because **the stage boards have no
> collision** (Rig & atmosphere: every structure ISM is NoCollision; the chariot slots are open).
> Unproven: whether Chaos environment collision counts a box in the cloth's *own* actor. If the
> pile drops through, FloorCatch must become a separate actor, which is a level write.
> Asymmetric release (one side first) would be pins as a stiff anim-drive spring whose stiffness
> goes to 0 at the cue. Not built.
> Scrub: tick **Simulate In Editor** (the cloth appears, hanging), then untick **Suspend
> Simulation** to drop it; `Hard Reset Simulation` and re-tick Suspend to hang it again.

Soft goods stream, 25 September 2026. The show curtain is now **Chaos Cloth simulated live
in the editor**, not a Blender bake. The bake route (`Scripts/build_curtain_cloth_bake.py`,
`DerivedAssets/CurtainCloth/CurtainCloth_Fly_V1.abc`) is kept for the one case it still wins:
a cue that needs the same silhouette every night.

**Why the route changed:** four bake cycles were rejected ("gelatinous", "waxy", "drawn-on
creases", "pretty poor"). Each was a blind guess plus a 10–15 min bake, because nobody could
touch a parameter while watching the cloth. Chaos puts the solver in the editor.

## 28 Sep (night): the goal is WEIGHT and a WIDE pile, and the Blender drop bake

Gary reset the goal: "heavy, rough cloth... a wider pile than on top of itself... not a pile of virtual
silk falling into a thin slice of space". The mechanism is free, and he approved baking the fall in Blender.
The tool is `Scripts/bake_curtain_drop.py` (headless Blender 4.4, the SAME pattern code, all settings as env
vars). It measures the settled pile in metres: depth, width, height, footprint, LAYERS and FOLD SIZE.
Renders go on phone cards via `Scripts/drop_bake_card.py`, clips via `Scripts/drop_bake_clip.sh`, and
tables via `Scripts/drop_bake_summary.py`. Outputs are in `Saved/CodexSoftGoods/DropBake/`.

What the scouts found (27 cm quads; pictures checked before any number was trusted):
- **Compression.** Cloth that out-stiffs gravity is cardboard. The pleated sheet STOOD 10 m TALL ON ITS
  HEM with no pins. Blender stiffness is not normalised by mass, so it needs a heavy per-vertex mass
  (`VERTEX_MASS_SCOUT`, area-scaled) and low compression. Too stiff and it tips over whole as a "PLANK";
  too soft and it crinkles into a low silky "MAT". Both were shown to Gary.
- **Rest shape (Gary's catch).** A curtain MODELLED pleated has pleats as its rest shape, and they survive the
  fall. Blender's `rest_shape_key` has NO effect in 4.4. The working route is `REST=gather`: model it
  FLAT and gather the pinned heading onto the track with an animated shape key. It then hangs in soft swags,
  and after the fall the fold size rises from 0.42 m to 0.72 m (the pleat pitch is gone). The pile is FLATTER,
  because flat fabric wants to lie flat.
- **Thickness.** Self-collision 1 → 3 cm doubles the pile height (0.14 → 0.30 m) and rounds the folds
  (0.69 → 0.94 m). With a flat rest shape, thickness is what holds a pile up.
- **Creasing (Gary's catch).** 27 cm quads with zero thickness fold to knife edges. At 0.7–0.9 m folds,
  9 cm quads give ~8 quads per fold. Measured cost at 2.0×: 15 cm 15.7k verts ~1 s/frame; 9.1 cm 42.9k
  ~2–5 s/frame (~30 min a run); 7.6 cm 61.8k ~5–9 s/frame (~1 h).
- **Arithmetic ceiling.** ~12 m² of fabric per metre of track heaps to ~0.5 m, not more.
- **Chaos side, not yet tested.** PBD stretch is symmetric, with no compression knob, and BucklingRatio = 0
  (set 27 Sep) disables buckle-softening. The Chaos rest shape is already flat (2D rest lengths, FlatnessRatio 1).

Blender traps, each of which produced a plausible-looking wrong result:
- An animated Vertex Weight Mix does not release pins. Use weight 0.99 with pin stiffness keyed to 0.
- ANY data change to the cloth after the sim (adding a modifier, or creating its material at render time)
  frees the in-memory cache, so the "final" render shows the unsimulated or hanging pose. Build everything
  first, and render the final frame BEFORE stepping the timeline back.
- A/B results identical to every digit mean a disconnected knob, not a result.

## 29 Sep (night): held patch E, light-replication draw order (not a curtain item; recorded here as its author's log)

`ReplicateLightAttachmentsWithVariation` passed six random draws as FVector/FRotator ARGUMENTS, so the compiler chose
their order. `Scripts/check_light_variation_order.py` reproduces UE 5.8 offline: the seed is
uint32(CityHash64(FGuid)) ^ Seed, then the FRandomStream LCG, with FRandRange in double. Run on a read-only dump of all
261 Wing Pairs / 2676 lights:
- **Result:** P02's corridor (21 Wing Pairs, 126 lights, jittered copies of P02 Wing 001, Cue Desk "with variation",
  seed 0) reproduces exactly under RIGHT-TO-LEFT order (MSVC): translation 7e-12 cm, rotation 7e-16, intensity at float
  rounding. Left-to-right reproduces none, and the other rotator order fails at 4e-2. Patch E pins that order, keeping
  FVector::FReal.
- **SCOPE OF THE PROOF:** it proves P02's corridor. A passage varied under a DIFFERENT binary would show as "no match",
  not as a contradiction. No other passage matched in either order, so nothing else in the saved Show depends on the
  draw order. If a future dump shows a new variation match, re-run the checker before trusting the pinned order for it.
- **Same bug class, flagged to Rig (their file, InfinityStageStructureActor.cpp):** lines 747 and 1047
  (`FRandRange * FRandRange`) and line 1216 (`(FRand() < 0.5 ? 180 : 0) + FRandRange(...)`).

## 29 Sep (night): transition curtain, RE-SIZED after Gary's reframe (plan only, nothing built)

Gary: "since the interaction is a shadow interaction my idea was for it to happen on the curtain and to drop it and
enter the next passage"; "The interaction will be more like 60s and maybe longer, so the fall should happen after it".
So the curtain is not a device inside the Interaction; THE INTERACTION HAPPENS ON IT. It hangs for the whole segment,
the boy-and-cat shadow play runs on it, and only at the end does it fall and reveal the Passage.
- **Length is his and will keep changing.** Interactions go from 20 s to about 60 s or more; he lengthens the sequences
  himself. Every cue has bUseSequenceLength, so the segment follows each sequence's PLAYBACK RANGE. Hardcode nothing:
  - the drape's sections derive from that range: HOLD [0, end − lead), FALL [end − lead, end);
  - lead = about 1 s of hang, plus the fall and landing (about 4–5 s). It is a parameter, not a baked number.
- **A long hang costs nothing.** HOLD loops the cache's FIRST FRAME (the end-offset trick used in the Opening). A 60 s or
  5-minute hang needs no longer bake and no extra disk. The existing 11 s GC_CurtainDrop_Opening covers the release and
  fall.
- **Standing step after he changes an Interaction's length:**
  1. `fit_transition_drapes.py`: idempotent; re-places each drape's HOLD/FALL from the current playback range.
  2. The guarded Master rebuild, which moves everything after it (5 × 40 s = +200 s if all go to 60 s). Growing the
     Interactions is his content; the mechanism is offered, not the decision.
  - A test should assert "each transition drape's FALL ends at its sequence's end", so a stale fit fails loudly.
- **Placement:** the drape at Passage N+1's route start (its mouth). Portals are approved at ALL mouths (Gary), so ONE
  bake serves all five once Rig enables them. The camera cut runs from the Interaction's START to its end, to Look &
  camera's stalls camera for that mouth. The pile goes under the cut to the Passage rig.
- **The fire-safety rig** is made inactive (or removed), and the SavedFixturePIE Interaction block (retained Scene camera,
  active fire-safety mesh, the 0.61 keying) is rewritten in the same build.
- **Reopened by the reframe (not now):** a minute or more of shadow play makes the curtain's FRONT-LIT READ matter more than
  its fall. The heavy velvet was tuned for the fall. Whether a pale, matte show cloth should carry the scene is now a real
  question, and it goes to Gary with pictures.

## 29 Sep (evening): restart protocol, the stutter after a clean editor

- **Instrument fix first.** The Slate post-tick delta is CLAMPED at 125 ms (1/8 s), so every max_ms before 19:10Z read
  125.0 and spike magnitude was censored. `editor_frames.py` now times frames with a wall clock (perf_counter) and reports
  the clamped Slate delta beside it. The recorder unregisters cleanly: each of 12 recordings logged exactly one summary.
- **Results** (editor pid 45468, new binaries, PIE off, 450 frames each; wall clock):

  | Step | Mean | p95 | Frames over 40 ms | Max |
  | --- | --- | --- | --- | --- |
  | (1) Virgin | 21.5 ms | 34.2 ms | 13 | 217 ms |
  | (3) After Look & camera's read-only probe | 20.3 ms | 32.6 ms | 8 | 101 ms |
  | (5) After Rig's writes (6 refits, a save, captures) | 22.2 ms | 36.1 ms | 16 | 195 ms |
  | Afternoon's dirty editor, for comparison | 23.7 ms | 49.6 ms | 33 | (censored) |

  In the afternoon the spikes came on a steady beat about 1 s apart.
- **Reading:**
  - A milder periodic stutter (clusters every ~1–2.5 s) is INHERENT to a fresh editor.
  - One round of read-only or writing scripts did not rebuild the afternoon's heavier state.
  - That extra weight was either cumulative (hours of use) or removed by today's code. One restart cannot separate the
    two, so neither is claimed.
- **Traces:** `Saved/Profiling/Stutter_DirtyEditor_20260929.utrace` and `Stutter_CleanEditor_20260929.utrace`.
- **Still missing:** `stat unit` (Game, Draw, GPU) during a spike.

## 29 Sep (late): Opening fall fixed; Scene 1 full length; the stutter measured

- **Opening fall fixed.** The drape template's GeometryCacheComponent had `running = False`, which I set to stop
  auto-play, and that froze the GeometryCache track on frame 0. The bench (`opening_fall_bench.py`) showed identical
  frames. With running on, frame 150 is fallen and frame 350 is the bake's pile. Saved on Gary's "yes fix" (backup
  `PreOpeningRunningFix-20260929-142225`) and re-proven from disk. Gary in PIE: "curtain fell ... and it looks ok".
  Traps: memory `ue58-geometrycache-sequencer-traps`.
- **Scene 1 plays its full 210.8 s.** Every cue already had bUseSequenceLength = true. The cut came from LS_DevScene_01's
  PLAYBACK RANGE (0–15 s) against its LS_Animals_1 shot section (to 210.8 s). `scene1_extend_rebuild.py` sets the playback end
  from the shot SECTION end, rebuilds, and verifies 13/13 at 0.000 s. Show total 993.4 s (16:33). Scene 3 is untouched: its
  LS_Clams section is placed for 60.58 s of a 119.93 s shot, which looks like Gary's trim, so it is his call. The lasting fix
  is in the compiler: ResolveSceneDuration = max(playback end, latest nested shot SECTION end). Section, not child: a
  trimmed section is a decision. Queued for a build.
- **Cloth gate, measured** (`cloth_gate_measure.py`, PIE copies only). Suspending the six Shore drapes removes their
  end-tick (4–10 ms ×6 down to <1 ms). A/B mean frame: 30.2 → 24.3 ms; frames over 40 ms: 45 → 13. SUSPEND is the
  switch. `cloth_gate_apply.py` (level default suspended, plus an infinite RESTORE STATE track in LS_DevScene_03) is ready
  and needs Gary's yes. Python trap: `suspend_simulation` is the bool property and shadows the UFUNCTION.
- **The ~1 s stutter is periodic, and the show does not set its rhythm.**
  - Measured in all three states: PIE with the transport paused, PIE with toggles, and the editor with PIE off.
  - Things that change the SIZE of the spikes but never the RHYTHM: flicker light functions off (−1.5 ms mean, Gary's flicker
    decision priced), dynamic shadows off (−4.5 ms), VSM cache off (worse), MaxLightsPerPixel 32 (no effect), and
    instanced meshes hidden (−4.7 ms).
  - The hitch owner is the scene render on the game thread. In the editor it shows `UpdatePrimitive` and
    `FScene_EndFrame`, which look like render-state churn.
  - Ruled out: other editors, scene captures, BP lights (all 2450 lights are native), and effect sources (0 instances).
  - Gary says it is a regression. The leading bet is accumulated editor state, a leaked callback or similar. The test is
    a clean-editor recording at the next build.
  - Trace of the dirty state: `Saved/Profiling/Stutter_DirtyEditor_20260929.utrace`.

## 29 Sep (14:00): THE OPENING IS PLACED (Gary: "yes opening", typed in this session)

- `curtain_place_opening_and_transitions.py` with `DO_TRANSITIONS = False` (backup
  `Backups/PreCurtainPlacement-20260929-135157`):
  - level CineCamera "Opening — Stalls Camera": (−1400, 0, 150), +14°, 15 mm, HFOV 76.8°, focus off;
  - `LS_Opening_Curtain_Baked`: the Fire Safety rig is removed; "Opening Drape (baked)" GeometryCacheActor spawnable
    with HOLD 0–25 / FALL 25–300 / PILE 300–375 (tick 24000, 960 per frame, loop offsets 263040); Camera Cut 0–375.
  - It saved only that sequence and the level; dirty after [].
- `repoint_opening_rebuild.py` (backup `Backups/PreOpeningRepoint-20260929-135221`): cue 0 now points at the baked
  sequence, RebuildManagedMaster ran, and it saved only the Show and the Master. 13/13 sections matched before
  (0.000 s: the 12:56 rebuild held) and after, and the Master's first section plays LS_Opening_Curtain_Baked.
- **Tier: read-back, NOT rendered.** Nobody has seen the fall in Unreal yet. Watch:
  - frames 0–25 should show the hang;
  - the PIE view should cut to the stalls camera, then to P01 at 15 s;
  - the pile goes at 15 s, under the cut.
- **Known red until patch A is built:** SavedFixturePIE "Opening reveal establishes Passage 1 camera before lifting".
- **Revert:** point cue 0 back to `LS_Opening_Curtain` and rebuild the Master. The camera actor and the new sequence
  can stay, since nothing else references them.
- **Transitions: not touched.** Gary's redesign (via the conductor, 29 Sep afternoon): there is no curtain on scene entry. On exit the box
  rotates back, and a show cloth at the passage mouth carries the shadow play, then drops. The scrim/calico/velvet
  panels are in `Saved/CodexSoftGoods/ShowCloth/` (`Scripts/render_show_cloth_compare.py`), parked on Gary's
  "don't get distracted from end to end".

## 29 Sep (afternoon): the curtain at the front and at the transitions — IMPORTED; placement written, NOT RUN

Gary (via the conductor): "place the opening curtain where it's supposed to be (at the front and also in between
transitions)... functioning end to end".

**Why it wasn't "at the front":** every sequence curtain is `BP_InfinityStageSequenceCurtain`, a CAMERA-FOLLOWING rig
with the flat fire-safety mesh. In the Opening it sits 100 cm from the lens at 0.1 scale ("too close, focus off").
The Opening has no camera cut, so the transport shows Passage 1's camera, which starts at X = 0, ON the curtain line
(`InfinityStageTransportController.cpp`: "Establish the next Passage's frozen opening view behind the closed
curtain", with an authored Camera Cut taking priority).

**DONE (content only, `Saved/CodexSoftGoods/curtain_baked_import.py`):** under `/Game/Scenes/Curtain/Baked/`:
`GC_CurtainDrop_Opening` (final2_stage_v2, Blender frames 120–450, 11.0 s, motion vectors computed),
`SM_CurtainDrape_Hanging` (frame 121) and `SM_CurtainDrape_Pile` (frame 450), and `MI_CurtainVelvet_DeepRed_Drop`
(PatternWidthM 35.529, DropM 10, SeamWidthM 1.37). `M_CurtainVelvet` now has Used with Geometry Cache (backup
`Backups/PreCurtainBakedImport-*`). Source: `DerivedAssets/CurtainCloth/Baked/CurtainDrop_Opening_final2.abc`.
- **Axis check passed exactly.** Conversion is Custom, scale (100, −100, 100), rotation (90, 0, 90). The cache is
  world-true (curtain line at X = 0), so the actor transform is identity. Hanging frame: X −103.7…+69.0,
  Y ±888.5. Pile: X −468.6…+508.4, Y −1084.6…+1167.6. Both are the bake's own numbers to 0.1 cm.
- **Trap: UE numbers Alembic frames ABSOLUTELY.** The file holds Blender frames 120–450, so sampling "330" gave
  Blender frame 330, not the 330th frame. The first run's check caught it; nothing was saved from that run.
- **Trap: `mcp_request.py` times out after 30 s by default,** while the import keeps running in the editor. Pass
  `--timeout 900`, and do not re-send (a re-sent call queues and re-runs the script).

**WRITTEN, NOT RUN (the classifier blocks level/sequence writes without Gary's direct yes in this session):**
1. `Saved/CodexSoftGoods/curtain_place_opening_and_transitions.py`. It backs up the level and seven sequences first.
   - It creates a level CineCamera "Opening — Stalls Camera": (−1400, 0, 150), pitch +14, 15 mm on 23.76 × 13.365,
     focus off. This is Gary's 28 Sep stalls view, and it's a level actor because the transport locates a
     sub-sequence cut in the world.
   - It duplicates the Opening to `LS_Opening_Curtain_Baked`, which:
     - drops the fire-safety rig;
     - adds a spawnable "Opening Drape (baked)" GeometryCacheActor with three sections: HOLD 0–25 (first frame looped),
       FALL 25–300 (release lands on frame 50, as the old lift did) and PILE 300–375 (last frame looped);
     - adds a Camera Cut 0–375 to the stalls camera.
   - It swaps the mesh of the six transition rigs (Interactions 1–5 and Closing) from SM_FireSafetyCurtain_01 to
     SM_CurtainDrape_Hanging. The frame is the same 17.8 × 10 m, so the rig keys, distances and tests hold.
2. `Saved/CodexSoftGoods/repoint_opening_rebuild.py`: it repoints cue 0 to the new sequence, runs the guarded
   RebuildManagedMaster and requires the Master's first section to play LS_Opening_Curtain_Baked. The revert is to
   point cue 0 back and rebuild.
- **REAL vs STAND-IN:** the Opening gets the real baked fall. The six transitions get the velvet drape flying in and
  out on the old camera-following rig: a stand-in, with no fall.
- **Known consequences:**
  - The pile vanishes at 15 s. That's the cut to Passage 1's camera, so the pop is hidden.
  - `SavedFixturePIE`'s "Opening reveal establishes Passage 1 camera before lifting" will FAIL by design once the
    Opening authors a camera cut. The test needs updating to accept an authored cut.
- **Not covered:** the passage-end curtains (run-through note: the dusky end of the tunnel). They need a drape at
  each passage end that falls at the Scene's start, which means edits inside the Scene sequences.

## 29 Sep: Master rebuilt; two durable lessons

- **Master rebuilt** (`Scripts/rebuild_managed_master_guarded.py`, Gary's go after saving Scene 3). Before, every
  section from Scene 3 on was 520.098 s off (Scene 3: Show 272.455–337.997 vs Master 272.455–858.095). After, all
  13 sequence sections match their Show segments to 0.000 s. Only the Master was dirtied and saved. Backup:
  `Backups/PreMasterRebuild-20260929-125656`. Proven by read-back; `SavedFixturePIE`'s Closing assertion is
  predicted to pass but has NOT been run (it starts PIE while Gary works). Scene 3 now reads 65.5 s, not the "2 min"
  mentioned, so Gary should check it.
- **STANDING STEP: after changing any Scene's playback range, rebuild the Master.** The 14 Sep repair doc already
  said so and it was not followed, which cost the back half of the show. A note alone has failed once, so the fix is a
  TEST asserting every managed Master section equals its sub-sequence's own playback range, naming the cue
  (to write next; source-only; needs a build window).
- **Scene-scoped cost is a class of problem.** Two things measured today cost the WHOLE show for one place: the
  Chaos curtain preview (removed, `Backups/PreRemovePreview-20260929-123440`) and the six Shore drapes on the
  Scene 3 MetaHumans (13.4 ms of a 23.6 ms PIE frame, a stall in `FChaosClothComponentEndTickFunction`, every
  frame). The plan is to switch them off outside Scene 3 (keyable `bSuspendSimulation`/`bEnableSimulation`, the switch
  to be picked by `stat dumpframe` in PIE), driven by Scene 3's sequence with Restore State. The entry settle is Gary's
  look call.

## 29 Sep (night): plan for curtains at the transitions (Gary's morning brief), nothing built

Gary: "implementing the curtain in many of those transition areas ready for later different more tattered and
otherwise dramatic curtains to replace them in their fall to transition between scenes".
- **The slot exists.** `Saved/CodexCurtainAuthoring/author_sequence_curtains.py` gave all 7 sequence blocks
  (Opening, Interactions 1–5, Closing) a spawned `BP_InfinityStageSequenceCurtain` (an AInfinityStageCurtainRig) and
  a CurtainProgress track, and the Show holds each block's cover/handoff timing. A baked curtain belongs INSIDE
  that slot: a rig subclass with a GeometryCacheComponent plus a GeometryCache track. That keeps the transport's
  covered handoff and the tests' "exactly one curtain rig". Traps: the rig force-shows SM_FireSafetyCurtain_01
  when active, and it disables actor collision.
- **A fall only REVEALS.** The Opening covers from frame 0 and reveals 50–150 (the bake). Interactions COVER 0–50 then
  REVEAL 325–375. The Closing only COVERS 0–100. So Interactions need a fly-in before the drop (a small addition to
  the bake: keyed heading motion), and the Closing a fly-in without a drop. Fly-in vs appear vs cut is Gary's call.
- **One bake per distinct site geometry.** The bake is only as right as its colliders, and the stage front is defined
  for Passage 01 only. Identical sites can share one asset (instanced); different ones need their own bake
  (~2.5–3.5 h unattended each).
- **Cost:** imported caches are STREAMABLE (UGeometryCacheTrackStreamable: per-sample info resident, chunks
  streamed), so RAM follows what plays; disk is one asset each.
- **Swapping:** a Sequencer GeometryCache section stores its own asset reference, so swap by RE-IMPORTING OVER THE
  SAME ASSET PATH (no sequence edits) or with a one-field section edit. Start with one shared placeholder per
  block type; give a transition its own named asset when its tattered curtain arrives.
- **CONFIRMED 29 Sep (read-only, `Saved/CodexSoftGoods/segments_vs_master.py`): the Master is STALE from Scene 3
  on.** BuildSegments on a transient transport matches the Master exactly up to Scene 3's start (272.455 s). Scene 3
  is 160.375 s in the Show and 585.640 s in the Master, so every later segment is 425.265 s off (Closing: Show
  877.429 vs Master 1302.694). SavedFixturePIE scrubs to the Show's Closing + 4 s = 881.4 s, which falls between
  Interaction 3 and Scene 4 in the Master, so it finds 0 rigs. In PIE the transport lands 425 s off for every segment
  after Scene 3. Fix: RebuildManagedMaster (the library call, never the PussStageBootstrap.RebuildCurrentMaster
  test), with the Show and Master backed up and Gary's yes. The original hypothesis follows:
  SavedFixturePIE's failing "Closing sequence evaluates exactly one curtain rig" (1 expected, 0 found): segments are built from the SHOW; the Master (saved 21 Sep) lays Scene 3 at 585.64 s
  against a 160.375 s sequence, so every segment after Scene 3 may sit ~425 s earlier in the Show than in the
  Master, and the Closing scrub (+4 s) then lands outside the Master's Closing section. That fits it being the only
  curtain assertion that fails (Interaction 1, before Scene 3, passes). Check read-only: Segments[18].StartFrame
  vs the Master's Closing section start (frame 32567 = 1302.69 s).

## 29 Sep: Opening repoint preflight (read-only), and an anomaly in the Master (NOT curtain work)

`Saved/CodexSoftGoods/preflight_opening_repoint.py` (read-only; dirty set empty before and after; run after Wing
materiality's saves) compared every Show cue that has a sequence against the Master
(`LS_InfinityStage_V1Master`: 25 fps, 24000 tick, 0–32942 = 1317.7 s, 13 subsequence sections).
- **The Opening is consistent.** Cue 0 "Opening — Curtain" → `LS_Opening_Curtain`, sequence_owns_curtain true,
  15.0 s at 25 fps; Master section frames 0–375 = 15.0 s. The curtain holds closed 0–50 and flies out 50–150
  (CurtainProgress 1 → 0), so a replacement curtain must release at frame 50.
- **ANOMALY, cue 97 "Scene 3 — External Sound" → `LS_DevScene_03`:** its Master section is **585.64 s**
  (frames 6811–21452), against a sequence of **160.375 s**, 3.65 times as long. It is also the **only 24 fps**
  sequence in the show; every other one is 25. The other 11 sequence cues match their sections exactly. It is
  NOT known whether this is a deliberate hold/loop laid by the builder or a stale Master. It sits in the
  passage→scene→passage path Gary calls "clunky and buggy", but it has NOT been shown to cause that. It is carried
  into the transitions work (conductor). Consequence here: a full `RebuildManagedMaster` would re-lay it, so the
  Opening repoint is a NARROW edit: cue 0 in the Show plus only the Master's Opening section (0–375), retargeted to
  a 15.0 s / 25 fps sequence, which is what a rebuild would produce for cue 0. Do NOT use the
  `PussStageBootstrap.RebuildCurrentMaster` automation test: it rebuilds AND SAVES the Show and the Master.

## 28–29 Sep: the landing bounce (fixed) and the final bake

Gary on the true-speed take: "it does read as heavy... the bounce is off". Measured before theorising:
per-frame silhouette, then per-frame centre of mass (`Scripts/drop_bake_bounce.py`). The hem touches at
+0.2 s with no effect. The pile collapses at ~+1.7 s and THEN swells: COM +0.106 m, top +0.72 m. It happens at
9.1 cm only; the 27 cm scout rose 1.6 cm.
- **Cause: solver under-stepping.** QUALITY 10 → 20 with COLLISION_QUALITY 4 → 8 removes it (COM rise +0.001 m).
  COM crossings match the old fall to the frame down to 2 m, and the final pile is unchanged. Finer edges need
  more steps. Cost: ~2x solve.
- **Refuted:** self-collision/edge ratio (the swell is the same at 3 and 1.5 cm); impulse clamps (1.0 never engages,
  0.1 barely moves it).
- **Trades, not fixes:** bending damping 5 or 2 from release kills the swell but slows the whole fall into a sink.
- **Dead end, do not retry:** keying bending damping up at the collapse. The descent stayed bit-identical, then the
  cloth BLEW UP (top 6.2 m).
- The self-collision ratio check is a WARNING only. The approved take uses 3 cm on 9.1 cm edges.

**Final bake** `final1_q15_quality20`: the approved settings with only the solver fixed, and a real-time clip plus
Alembic (frames 120–330, simulated mesh only, 110 MB; take 1 was 5.5 GB because the export evaluated the
render-only subdivision + solidify). There is no bounce. After the heap forms (+1.6 s) it SLUMPS outward for ~4 s
to ~0.5 m high. Staging (full extents over every frame, UE cm, UE X = 100 × Blender y upstage, UE Y = 100 ×
Blender x): downstage −379 (lip at −150), upstage +435 (Wing 001 at 250), portal |Y| 1354 settled and ±1188
mid-fall (limit ±920), header 1000 (passes). All were still growing at +6 s. The drop has NO upstage bias:
Gary accepted a forward fall; the Chaos asset's upstage air was not carried over. An upstage throw
(THROW_M) moves the pile upstage, but the hem kicks downstage as the top goes over.

## 27 Sep: why the free fall was a "viennetta", and the guided fall

Gary rejected the first fall: "It should be a big crumpled heavy fabric sprawled on the floor, not a very
narrowly squished viennetta." Four off-stage benches (`Scripts/curtain_fall_bench.py`: transient
curtains at y >= 60000, runtime overrides through the ChaosClothAssetInteractor, one capture per few
ticks, full cleanup) found:

- **A free-released sheet cannot sprawl.** Released uniformly, a symmetric vertical sheet falls straight
  down and piles in its own footprint. Stiffer solver (8 iterations, 4 substeps), 2 cm/side
  self-collision, bending 0.3–0.5, no buckle-softening, a 4° lean, low friction and a real 2.5 m/s gust
  all still end as a strip. With the stiffer settings the pile first has volume, then **deflates** to a
  strip over ~200 ticks.
- **Guiding the heading works.** Keep the heading pinned (`CA_<STEM>`, fly mode) and carry the cloth
  component down (gravity-timed, s²) and forward over ~1.4 s, like a batten falling forward. The top edge
  folds over the body and the cloth lands crumpled and spread 2–3 m deep. **Forward distance is the dial**
  (0 m: narrow; 3 m, 6 m: progressively sprawled). Bench config: `Scripts/curtain_fall_bench_guided.json`;
  clip: `Saved/CodexSoftGoods/curtain_guided_fall_plain_vs_ragged.gif`. In the show this is a transform
  track on the cloth component; in the editor, drag the component down with Simulate In Editor on.
- **Heavy-fabric loft** (bench5, guided 4.5 m, plain): bending 0.8, no buckle-softening (BucklingRatio 0),
  3 cm/side self-collision at stiffness 1.0 turns the fine crinkle into broad heavy folds. Grip (0.9 cloth,
  0.8 floor) holds them, and damping plus 3 self-collision substeps adds crumple. A **faster drop (0.9 s)**
  billows on the way down and lands as the most crumpled, overlapping heap: the best match so far for
  "big crumpled heavy fabric sprawled". Clip: `Saved/CodexSoftGoods/curtain_guided_fall_loft.gif`.
- **WindVelocity is in m/s**, not cm/s ("a gust is above 8 m/s"). 250 means a hurricane.
- **Environment collision is gathered from the cloth's bounds, which are the reference pose.** A cloth lifted
  off the floor (even with bounds scale 2) fell straight through FloorCatch. The placed curtains land only
  because the hem touches z = 0. Unresolved.
- **The editor currently ticks at ~2.5 s idle** (background throttling plus intermittent 3 s HTTP stalls to
  generate_204), so cloth cost can't be measured until the editor runs in the foreground. The physics is
  still valid (Chaos clamps dt), just slow-motion.
- Setting a cloth component's transform through `set_editor_property` re-registers it, and its interactor
  never comes up. Use `set_relative_location/rotation(..., teleport)`.

## 28 Sep: THE PIN WAS WRONG ALL ALONG. Chaos re-sorts sim vertices

**Every guided fall before 28 Sep was from a mis-pinned curtain.** The heading selection used static-mesh
vertex indices (verified on the imported mesh), but **Chaos does not use the static mesh's vertex order
for its sim vertices**. Observed on running sims (in-situ settle tests plus an off-stage pin-order test):
Chaos orders sim vertices **column by column across the 2D pattern (low u first), bottom-to-top within
each column**. So the mesh's "top row" indices 0–146 pinned the bottom-up runs of the first two columns:
the curtain hung from its LEFT EDGE. Renumbering the source mesh (first-appearance order) changed nothing,
because Chaos re-sorts regardless. For the plain 147×67 grid the true heading is `c·67 + 66`; that holds
the whole top edge level (pin-order test, silhouettes). The indices always read back correctly on the
imported mesh, so this is invisible until a sim runs. Treat ANY index-based cloth selection or weight map
as suspect.

The sprawl, loft, breeze and gust bench findings were all measured on this mis-pinned cloth. They point
the right way but are not trustworthy numbers until re-run on a correctly pinned curtain.

**Fixed (28 Sep), and the fix cannot ship wrong silently.** The pattern cutter reproduces Chaos's sort
(2D pattern UV: u asc, then v asc) and writes `heading_sim_indices`, which the build pins; the mesh-order
`heading_vertex_indices` are still verified on import. Every pinned build must PASS the automated check:
`Scripts/curtain_pin_check.py` hangs each pinned curtain off-stage under its own lamp (the bench site is
unlit) for 120 ticks, and `Scripts/curtain_pin_check_score.py` requires ≥95% of the top edge within 8 px
and ≥95% of the width retained. Result: plain PASS and ragged PASS (100% held); a negative control (the
old left-edge hang) scores 26.6% and fails. Next: a position-based pin (UV-mask TextureToAttribute, then
vertex colour) as the durable replacement, validated by the same check. No position-based cloth selection
node has been found in 5.8.

## 28 Sep: the Chaos Opening (in a duplicate sequence)

Gary: the curtain doesn't follow the camera. It stands fully in front of every wing (x ≈ 0, just
upstream of station 1) and falls UPSTAGE. `Scripts/build_opening_chaos_sequence.py` made
`/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos`, a duplicate; **the original
`LS_Opening_Curtain` is untouched** and Show cue 0 still plays it. The copy spawns:

- "Chaos Curtain" = `BP_CurtainChaosCloth` (a plain Actor with the pinned PLAIN cloth). Its actor
  transform track parks it at (0, 0, 0), yaw 90, then from frame 50 to 72 (≈0.9 s) carries it 1.8 m
  upstage and 995 cm down (s^1.5 / s² keys): the guided fall.
- "Curtain Floor" = `BP_CurtainFloorCatch` (a hidden WorldStatic box, top at z = 0, ignoring
  Pawn/Camera/Visibility/CatFloor).

Why not a subclass of `AInfinityStageCurtainRig` (the old Fire Safety rig): its constructor calls
`SetActorEnableCollision(false)` (a bare UPROPERTY Blueprint cannot flip, so a floor box inside it
is dead), it force-shows `SM_FireSafetyCurtain_01` whenever active, and the Interaction-1 automation
test counts exactly one rig. With `bSequenceOwnsCurtain` nothing outside the sequence reads
`CurtainProgress`.

The 1.8 m throw (not 4.5 m) keeps the ±888 cm pile in front of station 1's wings (x = 250, ±750).
Still open: persistence (a default spawnable pops the pile at 15 s), the camera pose and lens,
removing the x = 5400 preview (a level write), and repointing cue 0 (a Show write). All are Gary's.

**Breeze** (bench6): under 1 m/s, a breeze makes no measurable difference to the hanging 0.8 kg/m²
velvet. Mean frame-to-frame change: still 1.50, 0.3 m/s 1.48, 0.6 m/s 1.47, 0.6 m/s with drag 0.15
1.17. Not baked. Options: none, a 1–2 m/s gust timed at release, or a lighter-feeling fabric.

**Air at the release** (28 Sep, Gary's choice): the plain pinned asset carries a constant 1.5 m/s
wind UPSTAGE, in the cloth's COMPONENT space (upstage = local −Y for a yaw-90 curtain), drag 0.08
(`AIR_BY_STEM` in `build_curtain_chaos_asset.py`). Benched (bench8): inert while hanging (motion
1.41 vs 1.46 still), and it adds a subtle upstage billow once the cloth falls, so it is functionally
"air at the release" with no timing machinery. A scene Wind Directional Source (strength 1, speed 5)
did NOT measurably reach the cloth, so a Sequencer-keyed wind actor cannot deliver a gust. A literally
timed gust would need a small C++ component (a keyable float feeding the interactor's WindVelocity).
Not built.

## 28 Sep (late): the Opening fall goes THROUGH the floor, and Gary was right

The conductor captured `LS_Opening_Curtain_Chaos` by stepping the playhead one frame per tick. The
curtain slid down and vanished, and Gary said "it seems to fall through the ground". I predicted a
Sequencer teleport-with-reset. **That prediction was falsified.** `Scripts/curtain_teleport_drop_test.py`
reproduces the Opening arrangement off-stage: `BP_CurtainChaosCloth` with the correctly pinned plain cloth
stands over a SEPARATE `BP_CurtainFloorCatch`, and the cloth ACTOR is carried 995 cm down and 180 cm
upstage (s² / s^1.5) over 32 ticks. Variant A used `teleport=False` and variant B `teleport=True`. **They
are indistinguishable.** Both descend taut and rigid, with the hanging folds unchanged. The lower curtain
goes BELOW the floor instead of bunching on it, and only a small crumple near the heading stays above
z = 0. Frames are in `Saved/CodexSoftGoods/Frames/teleport_drop/`.

- **`UChaosClothComponent` ignores the actor/component `ETeleportType`.** It teleports only on its own
  `bTeleport`/`bReset` (Interp, so Sequencer-keyable), on `ForceNextUpdateTeleport[AndReset]`, or when
  one frame's move exceeds `TeleportDistanceThreshold`. That threshold is 300 cm on both BPs, and the
  rotation threshold is 0, which is off. The drop moves at most ~62 cm per tick, so it never auto-teleports.
- **A separate floor-catch actor did NOT catch the correctly pinned cloth.** It is unknown whether the
  in-actor `FloorCatch` (`BP_CurtainChaos`) does, because that has only been seen on the mis-pinned
  cloth. So **the guided fall has never been seen working on a correctly pinned curtain.**
- The conductor's per-tick scrub capture is not shown to be the cause. Whether scrubbing resets the
  cloth is a separate, unmeasured question.
- The rigid descent is not explained. Two suspects, neither measured: the default `LinearVelocityScale`
  0.75 (a quarter of the reference-frame motion is carried rigidly), and a drop that is slow in sim
  time (the idle editor ticks at ~2.5 s and Chaos clamps dt). If the drop is slow, the heading's
  acceleration stays under g and the cloth simply hangs taut from it all the way down.

(The "next steps" first written here are superseded by the section below.)

## 28 Sep (evening): moving the component CARRIES the cloth, so a guided fall cannot work

Five benches, all off-stage and transient, measured with SIDE ORTHOGRAPHIC show-only captures
of the cloth alone in base colour, so the z-range below ground and the upstage spread are read in
pixels, not by eye. Measure scripts: `Scripts/curtain_floor_bench_measure.py`,
`Scripts/curtain_carriage_measure.py`. Bench scripts: `Scripts/curtain_{floor_control,floor_timing,vscale,carriage}_bench.py`.

- **Floor control (six variants).** Every floor variant ends 75–80% below z = 0, against 98% with no
  floor. That includes a 400 cm-thick box and CCD on (read back as present), so it is **not
  tunnelling**. (The in-actor variant with `BP_CurtainChaos` never simulated, so it is void.)
- **Floor timing.** A floor RISING into a static curtain leaves a bulge at the slab's current
  height (z≈420), and so does a floor SPAWNED after the sim starts. **Environment colliders are live and
  late ones are gathered.** The thin 50 cm slab still passes through: my reading is that cloth caught
  inside is pushed out through the nearer face.
- **Velocity scale.** A transient in-memory copy of the plain cloth, WITHOUT the node, matches the
  saved asset exactly through the drop, so the technique is faithful. With `LinearVelocityScale` 1.0
  (read back as (1,1,1) from the running interactor), the result is **unchanged**: 0.42 s into the
  drop, the heading has come down 217 cm, free fall would be 86 cm, and the hem has come down 215 cm.
- **Carriage probe (the decisive one).** Heading jerked 300 cm UP in 0.25 s: the hem rose −1 → 299 in the
  same 0.25 s. Cloth cannot be pushed up. Sideways jerk: the hem arrives 300 cm across on the same
  tick, with no lag or swing, and identically at velocity scale 0.75 and 1.0. The free particles still
  drift ~11 cm in the baked 1.5 m/s air afterwards, so they ARE simulating.

**Conclusion.** Under Simulate In Editor, moving a ChaosClothComponent (by actor or by component)
moves the whole simulation frame, and the free cloth rides along with none of that motion felt as
inertia. That explains the taut descent, the hem welded to the heading, and the floor failure (the
floor slides up through a carried sheet). **A guided fall by moving the component cannot work.**
Untested: whether PIE or a packaged game differ. Rehearsal in the editor would not, either way.

**Candidate fix, which is Gary's decision:** move a BONE, not the component. Build a Root + Heading
skeleton (Blender, skeletal import through `FChaosClothAssetSkeletalMeshImportNode_v2`), with the
heading skinned to Heading, and parent the cloth under a SkeletalMeshComponent playing a short drop
animation. `bUseAttachedParentAsPoseComponent` is a plain component property, so no runtime hook is
needed. The component and reference frame stay put, as with any character's cape. **Unverified:** that
bone motion is felt as inertia. The current assets have ONE bone (Root), which is also the reference
bone, so no no-content test exists. The pin must be re-derived for the skeletal import (the pin check
covers that).

**Other facts from these benches:**
- The editor's tick delta is CLAMPED at 0.125 s. Any frame slower than that runs the sim in slow
  motion, so bench "seconds" are delta seconds, not wall seconds.
- Cloth cost, wall-clock with no captures: frame 333 ms with 3 curtains spawned, 340 ms with 3
  simulating, i.e. ~+7 ms for three (median of 19 each; p90 546 ms). The cloth is cheap; the frame
  was not.
- The environment collision config's `UseCCD` is present in the asset; `LinearVelocityScale` is not
  (there is no VelocityScale node).

**TRAP, which crashed the editor (28 Sep 17:09):** `SetSkinnedAssetAndUpdate` on a REGISTERED
Poseable or SkeletalMesh component with a Chaos cloth asset asserts
(`AssetSkeletalMeshObj || AssetSkeletonObj`, BoneContainer.cpp:163). The cloth asset has no Skeleton.
The same call on an unregistered `new_object` component passes, which is misleading. Never give a
cloth asset to a pose component; a pose parent needs a real SkeletalMesh with a Skeleton.

## Read this first: the rest-shape trap

**Chaos takes the cloth's rest shape from the 3D mesh by default.** Two settings:

| Node | Setting | Default | Must be |
| --- | --- | --- | --- |
| `SimulationStretchConfig` | `bStretchUse3dRestLengths` | `True` | **`False`**: rest lengths from the flat 2D pattern (UV0 × UVScale) |
| `SimulationBendingConfig` | `RestAngleType` | `Use3DRestAngles` | **`FlatnessRatio`**, `FlatnessRatio` = 1: flat at rest |

The mesh's 3D positions are the pleated *start pose*. With the defaults, those pleats become
the rest state and the solver holds them forever. That is the "creases drawn on in repeated
patterns" defect Gary rejected twice in the Blender route, in a different engine. **Shape the
start pose; let the solver make every crease.** The same rule applies to the pattern cutter:
raggedness is boundary topology made from non-repeating noise. Sine sums repeated about 11× across
the 35 m pattern and were thrown out.

## Files

| What | Where |
| --- | --- |
| Pattern cutter (Blender 4.4, headless) | `Scripts/build_curtain_chaos_pattern.py` → `DerivedAssets/CurtainCloth/Chaos/SM_<STEM>.fbx` + `<STEM>.json` + `<STEM>_pattern.png` |
| Weave maps | `Scripts/build_curtain_weave_maps.py` → `DerivedAssets/CurtainCloth/Chaos/Textures/` |
| Unreal build (textures, velvet material, mesh, Dataflow, cloth asset) | `Scripts/build_curtain_chaos_asset.py` |
| Place a scrubbable instance in the level (**needs the conductor's level slot**) | `Scripts/place_curtain_chaos_preview.py` |
| Unreal content | `/Game/Scenes/Curtain/Chaos/` |

`<STEM>` is `CurtainChaos_Ragged_Q15` (15 cm quads, ~15k vertices: interactive) or
`CurtainChaos_Ragged_Q09` (9 cm, ~41k: the bake resolution, for once the values are settled).

Unreal scripts run through the guarded MCP route: copy into `Saved/CodexSoftGoods/`, then
`python Saved/CodexMocap/mcp_request.py tools/call --params-file <request>.json`
(`ExecuteProjectPythonFile`, relativeSavedPath `CodexSoftGoods/<script>.py`). Each script
checks it is in the expected world, refuses to start if any package is dirty, saves only what
it made, and ends on an explicit `PUSS_SOFTGOODS_*_SUCCESS` marker.

## Rebuild

```bash
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python Scripts/build_curtain_chaos_pattern.py
python Scripts/build_curtain_weave_maps.py
```

Then run `build_curtain_chaos_asset.py` in the editor. It re-imports the mesh and textures,
rebuilds the material in place, and deletes and recreates `DF_`/`CA_` (they are derived data).
Pattern knobs are environment variables: `CURTAIN_QUADS_PER_BOLT` (9 → 15 cm, 15 → 9 cm),
`CURTAIN_SEED`, `CURTAIN_FULLNESS`, `CURTAIN_RAGGED=0`. For the Unreal side, set `CURTAIN_STEM`.

## Pattern

- Flat pattern **fullness 2.0**: 35.5 m of fabric for a 17.77 m track, 10 m drop. UV0 is that
  pattern normalised 0–1. Chaos `StaticMeshImport` uses UVChannel 0 with UVScale =
  (pattern width, drop) in cm, so the 2D rest lengths are the real fabric's.
- Start pose: the fabric gathered onto the track in pleats. The gather is by arc length, so it
  starts unstretched, and pleat depth varies per pleat, never per vertex.
- Columns are sized so a **seam** falls on a grid line every **1.37 m** of flat fabric (one bolt).
  The material draws the seams from UV0.
- Rags: an aperiodic torn hem, 3–5 tongues torn well up, frayed sides, 4–7 tears ripped up from
  the hem (split edges, opened 4 mm so they cannot re-weld) and 5–8 holes. Cut edges are
  relaxed off the grid. Anything not connected to the heading is removed.
- **Heading** = the top row, tied to the batten. Its vertex indices go into the sidecar JSON;
  the build checks after import that every one of them is on the top edge.

## Physics: what carried over from the bakes

Relationships, not numbers. Blender's per-vertex mass and stiffness units do not translate.

| Relationship | Chaos |
| --- | --- |
| Will not stretch | `Stretch` PBD, stiffness 1.0, **area constraint off** (it resists compression → plate); tethers stiffness 1, scale 1 |
| Folds for free (Blender tension 200 / compression 3) | `Bending` PBD stiffness 0.05, **buckling stiffness 0.005** after buckling ratio 0.5 |
| Heavy, not jelly | Density **0.8 kg/m²** (heavy velour, about 25 oz/yd²). The Blender "7 kg/m²" was a solver artefact, not a fabric weight |
| No flutter | Damping 0.05, drag/lift 0.03 |
| Folds keep their structure | Self-collision on, friction 0.8 |
| Heading on the batten | `Selection` "Heading" (SimVertices3D indices) → `MaxDistance.InKinematic`; MaxDistance 10000 cm for everything else |

Tune in the graph (`DF_CurtainChaos_Ragged_Q15`) with the cloth running. Numbers that settle
go back into `PHYSICS` in `build_curtain_chaos_asset.py` so a rebuild keeps them.

## Velvet

`M_CurtainVelvet` / `MI_CurtainVelvet_DeepRed`: **Cloth** shading model, two-sided, with sheen
from Fuzz Color. The base is darkened face-on and lifts toward grazing (Fresnel), which is the
nap turning away, the cue that reads as weight under raking beams. Flat deep-red base
(Gary, 25 Sep), weave from `FireSafetyCurtain_01_WeaveDetail_v1` at 12 cm tiles and ~20%,
seams darkened along a 2.4 cm line. **Nothing is painted into the colour**: TextileV5 is a picture of a
whole curtain with crumples painted in and must not be used on simulated cloth.

## Engine traps (UE 5.8), each hit once

1. **MaxDistance defaults to 0 when no weight map is painted**, which freezes the whole cloth.
   Set Low/High high and pin with `InKinematic` instead.
2. **`DataflowBlueprintLibrary.EvaluateDataflow` returns False for cloth assets even on
   success.** Epic's `DF_StaticMeshClothTemplate` and `DF_EmptyClothAssetTemplate` return False
   too. Don't gate on it. The evidence of a build is `LogSkeletalMesh: Built Skeletal Mesh
   CA_…` plus the cloth asset's material slots, which the evaluation fills.
3. **`MaterialEditingLibrary.DeleteAllMaterialExpressions` deletes only about half per call**
   (15 → 7 → 3). Loop until `GetNumMaterialExpressions` is 0, or orphans pile up on every rebuild.
4. **The Cloth model's "Cloth" input (CustomData0) is not reachable from Python.** Go through
   `MakeMaterialAttributes`: its `ClearCoat` pin *is* CustomData0.
5. **Saving a cloth asset sets the Clothing usage flag** and re-dirties the material instance
   unless the base material already has `used_with_clothing`.
6. **Dataflow authoring is fully scriptable**: `DataflowEditorBlueprintLibrary.add_dataflow_node`
   / `set_dataflow_node_property` (ImportText strings, e.g. `(bIsAnimatable=True,Low=1,High=1)`)
   / `connect_dataflow_nodes` (pins `Collection`; terminal input `CollectionLods[0]`). Node type
   names are the struct names, e.g. `FChaosClothAssetStaticMeshImportNode_v2`. The cloth asset
   links to its graph through `dataflow_instance.dataflow_asset` / `dataflow_terminal`, a
   deprecated-warning property path that still works.
8. **A configured game trace channel is named by its display name in Python.** `ECC_GameTraceChannel1`
   = "CatFloor" is `unreal.CollisionChannel.ECC_CAT_FLOOR`; there is no `ECC_GAME_TRACE_CHANNEL1`.
   Also, `set_collision_response_to_all_channels(BLOCK)` writes all 32 slots, including channels
   not yet defined, and an explicit per-component response beats the channel's default. So FloorCatch
   ignores CatFloor explicitly (the cat must not stand on the cloth's hidden safety net).
9. **`suspend_simulation` is a bool PROPERTY in Python**: it shadows the SuspendSimulation function, so
   calling it raises "'bool' object is not callable". Set it with `set_editor_property`.
   `resume_simulation()` is a real method.
10. **To put a curtain back to rest, switch Simulate In Editor off FIRST, then suspend.** The other order
    undoes the suspend and leaves the curtain live-simulating in the editor (hit twice on 27 Sep, once by
    the conductor and once by this stream; both caught on read-back). `simulate_in_editor` refuses
    `set_editor_property` on templates: use `set_simulate_in_editor()`.
7. `ChaosClothComponent.bSimulateInEditor` is transient and per instance ("Simulate In Editor" in
   Details): switching it on never dirties the level. `bEnableSimulation` and `bSuspendSimulation`
   are Sequencer-keyable.

## State and proof (25 Sep)

- Built: the CA/DF/mesh/material/textures under `/Game/Scenes/Curtain/Chaos`. **Tier: saved
  read-back.** 7/7 assets load, the cloth is linked to its graph and carries the velvet MI, 0 dirty
  (`Saved/CodexSoftGoods/verify_chaos_curtain.json`).
- Placed (26 Sep, 01:57, approved by Gary): `BP_CurtainChaos` and one instance, "CurtainChaos
  Preview", in `L_InfinityStage_V1VerticalSlice` at (5400, 0, 0), yaw 90 (P01's world, currently
  dark: judge the velvet after Rig's back-thrown lamps). Simulate In Editor is off; switching it
  on is Gary's call. Read-back: one actor, the right asset, dirty 0/0. Backup
  `Backups/PreCurtainChaosPreview-20260926-0156`. This save also absorbed the conductor's
  capture-tool map flag (`absorbed_capture_map_flag`). The conductor's HOLD reached this stream
  only after the save.
- The actor's bounds extend about 128 cm deeper and lower than the geometry. Probably cloth bounds
  padding; not confirmed.
- **Disproven (28 Sep):** Chaos does NOT keep the static-mesh vertex order; see "THE PIN WAS WRONG ALL ALONG".
- **Not yet seen:** any rendered frame. The look, the weight and the frame rate are unverified.
- Not started: the sequencer swap (conductor's call), velvet/sack/hanging-cloth variants,
  peeling wing-edge strips, dust sheets.
- **Festoon retired** (26 Sep, 20:01, Gary's go): the "CurtainCloth Preview" actor at x = 4400 and
  `GC_CurtainCloth_Festoon_V1` are gone. Before deleting, the asset registry, a byte search of all 30
  LevelSequences and the in-memory bindings all confirmed the level was the only referencer.
  Backup `Backups/PreFestoonRemoval-20260926-2001` (the .umap + the cache, hash-verified). The fly
  bake `.abc` on disk stays as a record.
- **Plain variant**: `CA_CurtainChaos_Plain_Q15_Fall` (fullness 1.25, no rags) and
  `BP_CurtainChaos_Plain_Q15`, unplaced, for Gary to compare with the ragged one. This is the one that
  matches "heavy, thick… nothing too fancy, a core fabric rather than drapery".
