# Rig & atmosphere — handover, 28 September 2026

For whoever picks this stream up cold. Brief:
`Docs/Conductor/BRIEF_RIG_AND_ATMOSPHERE_2026-09-25.md`. Design records:
`Docs/OpeningLight_2026-09-27.md`, `Docs/SceneScaleAudit_2026-09-26.md`,
`Docs/GroundPlaneDesign.md`. Scripts: `Saved/CodexStructure/` (every mutating
script has a dry run, a revert record written before it mutates, and a revert).

## 1. Built vs unbuilt C++ — read this before the next build

**In the DLL (built 26 Sep, suite 70/71, lone failure `SavedFixturePIE`):**
the structure pass (`AInfinityStageStructureActor`: gridiron, ground, cloth
(off), fixtures) and Light Drama (`InfinityStageLightDrama.*`). 10 of my tests.

**Committed but NOT compiled:**

- `c8aee3b`: per-side chariot slots (`NegativeSideCm` / `PositiveSideCm`), so each
  side's slots start under its own wing.
- `68057a2`: the portal layer, off by default.
- 12 tests of mine in total after the build: 9 `InfinityStage.Structure.*`,
  3 `InfinityStage.LightDrama.*`.

> **After that build, `IsStructureCurrent` reads FALSE for all six structure
> actors.** That is expected, not a regression: the station signature now
> includes both sides' extents. They need a re-materialize (a level write, in
> its own slot), which will also move the slots in P01, P04 and P05, whose
> corridors are asymmetric.

## 2. Authored and live (saved read-back; none of it accepted by eye)

| What | When | Backup | Undo |
| --- | --- | --- | --- |
| Six structure actors replace the Python gridiron (771 timbers, 26,090 boards, 480 slots). Reload-from-disk proof passed. P03 ground is off (its Wet Ground Landscape sits at about +10 cm). | 26 Sep 01:59 | `Backups/PreStructureSwap-20260926-0159` | restore the umap |
| P03 upper rig: 53 lamps (33 pools, 14 slashes, 6 back-lights) with Light Drama; 189 existing lights reworked into shadowless fill on a composed path envelope. P03 casters 147 → 53; the "patchy" rectangles are gone (capture-confirmed). | 26 Sep 02:00 | `Backups/PreP03Rig-20260926-0200` | `p03_rig_revert.py` |
| Opening lamp + 78 floats past x 5400. **The lamp is now disabled** (superseded by the warmer); the floats stay. | 28 Sep 08:26 | `Backups/PreOpeningLight-20260928-0826` | `p01_opening_revert.py` |
| P01 Wing 001's Right panel +500 → +750 (the mouth becomes a uniform three-pair ±750 frame). | 28 Sep 09:00 | `Backups/PreP01Station1Symmetry-20260928-0900` | `p01_station1_symmetry_revert.py` |
| Curtain warmer: two house spots at (−2100, ±650, 1265) for Gary's stalls camera (−1400, 0, 150, +14°, 15 mm), plus 18 floats behind the curtain's new line (x 250–5050). | 28 Sep 09:28 | `Backups/PreWarmer-20260928-0928` | `p01_warmer_revert.py` |

The opening curtain at x 0 exists only as a **spawnable in
`LS_Opening_Curtain_Chaos`**. Without the sequence playing, the warmer lights
an empty mouth.

## 3. Designed, not built

- **The portal** (approved by Gary): posts framing ±950, header at 1050, the
  gridiron carried forward, a forestage, a float trough, and 5 hemp lines. It
  needs the build, then `Portal.bEnabled` on Structure 01, then a re-fit. At 15 mm
  with a 14° tilt its posts will keystone (lean together); capture it early.
- **The lip floats**, held for the portal: without its trough they would float
  in void at the bottom of frame. Until then the hem, which is the feature from
  the stalls, gets no uplight.
- **The Scene Volume / hangar** ("one generator, two station sources") and the
  portal as a hangar mouth: `Docs/SceneScaleAudit_2026-09-26.md`.
- **CatFloor collision:** one invisible, query-only slab per bay that blocks only
  `ECC_GameTraceChannel1`; the boards stay NoCollision. Not started.
- **Cloth layer:** off until Soft goods' `SM_FloorCloth_A–D` are imported.

## 4. Measured facts, so nobody re-derives them

- **Fog is net-negative by 2–3 mean** even with the P03 back-lights scattering
  (up to +156 per pixel where they throw toward the lens). The balance (more or
  brighter back-lights, or density below 0.022) is Gary's call. My unexecuted
  suggestion is about 0.012.
- **Haze shows a shaft only to a viewer the light travels toward** (g = 0.55).
  The old forward-thrown beams showed nothing (four-state A/B, 25 Sep).
- **"Patchy" hard colour rectangles are VSM one-pass overflow**, and the log says
  so (`[VSM] One Pass Projection max lights overflow`). About 1,700 shadow-casting
  local lights remain show-wide, and the editor idles at 92–93% GPU SM (MHFat's
  measurement). MegaLights tested with no loss, but the console trial resets on
  restart and it is currently off.
- **P01's floor** was built and unlit on 26 Sep. The warmer and floats now
  light parts of it; unverified by capture.
- **P01's other seven asymmetric pairs (−400/+750)** are untouched by deliberate
  decision. Regularising them is a separate question for Gary.
- **The six shadow cats' heights follow the camera, not the floor** (P01 −5.5,
  P04–P06 +4.1). That belongs to Look & camera.

## 5. Gotchas

- `unreal.Guid` never compares equal with `==` in Python. Compare
  `GuidLibrary.conv_guid_to_string(...)`. It produced a false negative, not an
  error.
- **The gridiron's cross beams pass through P01's border flats**: the borders
  hang 800–1800 cm at the stations, and the grid sits at 1150. Unresolved: raise
  P01's `Gridiron.HeightCm` above 1800, or set the beams between stations.
- **Before any level save, refuse if `ZZ_`/TEMP actors exist.** Other streams
  bench in the level, and the map-dirty flag cannot tell you whose work it is.
- **Resting-editor positions are "fossils"** of the last evaluation (the P01
  camera rig sits at x 3850, not at the opening pose). Measure poses through
  the evaluation path.
- **Offscreen captures render editor-only proxies** (the rig's 5× SM_CineCam).
- **Attachment GUIDs are read-only from Python.** Mint them via
  `replicate_light_attachments`; when pair light counts differ, use a padded
  scratch pair.

## Open decisions (Gary)

Fog balance · P03 pool tint (gold left / violet right) · MegaLights · shadowless
fill show-wide · timber materials and board/beam meshes · wall bays · removing
P03's Landscape · the grid-through-borders clash · P01's other asymmetric pairs
· return from the hangar (visible mouth / second mouth and the ring / cut / hybrid).

## Evening, 28 September: where things stand

- **The 28 Sep build carried the slot fix and the portal.** All 12 of my tests
  passed (`Saved/Logs/SuiteAfterBuild-1358.log`, suite 76/77). All six
  structures still need `structure_refit_all.py`, which has not run.
- **Editor runs from this session are classifier-blocked**, including
  read-only ones, and so is adding an allow rule. Gary chose the allow rule
  `Bash(python Saved/CodexMocap/mcp_request.py tools/call:*)` in
  `.claude/settings.local.json`, and must add it himself. Nothing below has
  run in the editor. The conductor will not run any of it on this stream's
  behalf.
- **Gary's decisions:** portal yes. The curtain falls forward, and overspill
  is OK. Stage front option A, with the curtain hitting the posts. The house
  floor wraps the sides. Station 1's floats: the cloth drapes over them.
  Footlights: shadowless and buried, judged in the capture
  (`BURIAL_ACCEPTED`).
- **Stage front C++: `c467046`, unbuilt.** It needs a build window (the
  conductor is negotiating with MHFat), then the suite, with the new test
  `StageFrontCatchesTheOverspill`. The nosing is built but off.
- **Colliders:** `Docs/StageFrontColliders_2026-09-28.json` (v3, the built
  numbers), generated by `Saved/CodexStructure/make_stage_front_colliders.py`.
  The running bake uses v2 (`070ffe4`), which is within 3.2 cm and errs clear.
  Wing 001 is excluded until `wing001_footprint_probe` plus the analyser give
  its opaque silhouette.
- **The chain, once the rule is in, on the conductor's call:**
  `below_lip_sweep_readonly` (report it first), `wing001_footprint_probe`,
  `structure_refit_all` (dry run, then apply). After the build:
  `portal_enable_apply`, then `verify_stage_front_readonly` (built edges vs
  the collider file, to 1 cm). Then the conductor's capture. Then 3b (the
  lip floats plan, apply and verify).
- **Framing:** use the Super 35 filmback (see the camera memory). A
  full-frame assumption produced a wrong 17% / z −305 figure, since
  corrected in `Docs/OpeningLight_2026-09-27.md`.
- **Queued after the stage-front chain** (Gary, via the conductor): P04 and P05
  lighting passes, both "barely there" and never lit; fog density to 0.012.
  Also a read-only spine check for the conductor, `master_vs_show_readonly.py`
  (Master saved 21 Sep vs the Show saved 28 Sep). Never run
  `PussStageBootstrap.RebuildCurrentMaster`: it is a test that rebuilds and
  SAVES both assets.

## 29 September, morning

- **Floors dropped under the boards** (Gary: "drop all floors to zero", "show
  me the boards"; the conductor approved it under the delegation). Three textured
  slabs, `StaticMeshActor_0` (P01 walnut), `_1` (P06 Versailles) and `_7` (P05
  oak), were 100 cm engine Cubes with their tops at +49.5, burying every
  structure floor, the wing feet, the floats and the cats. They are now 1 cm
  thick with tops at −5, under the boards. P01's slab is trimmed to end at the
  lip (x −150), so the stage front shows. Backup
  `Backups/PreFloorsToStage-20260929-1233`; undo `floors_to_stage_revert.py`.
  Consequence: the slots show the slab 5 cm down, not the dark understage.
- **Structure re-fit still unsaved:** the first run refused on P05 Wing 004
  (its Right panel stands on the route line, so it's one-sided). The guard now
  follows the mechanism (`be716f3`). My Python reload of the open level crashed
  the editor; never do that. The re-run waits for its slot.
- **Board material:** every structure piece is an engine Cube with no material
  (grey). Per-layer material settings already exist. A convincing material must
  tile using per-instance custom data or world-aligned UVs. The look is Gary's.

## 29 September, afternoon

- **Structure re-fit saved** (the per-side slot fix): 6/6 current; P05 has 185
  slots, because P05 Wing 004's Right panel stands on the route line.
- **Floors:** the slabs are still under the boards (top −5). Gary chose walnut
  planks on the boards (`Ground.BoardMaterial`, from Wing materiality's
  `MI_Kit_WalnutPlank`, still to come) and procedural steel grooves. The floor
  raise and Top Down are both held.
- **P04/P05/P06 baseline lighting applied:** P01's tuned rig, rewritten in place
  and found by GUID, because P05 reuses cue labels. Shadow casters 1643 → 612
  (P04 42, P05 0, P06 110). Backup `Backups/PreP456Baseline-20260929-1323`; undo
  `p456_baseline_revert.py`. Not yet seen in a frame.
- **Unbuilt C++ for the next window:** the celestial fix (`0af1130`: stops the
  per-frame world walk) and the steel grooves (`1ef583b`).
- **Specs with Gary:** `Docs/LegibleMachineSpec_2026-09-29.md` (grooves, wing
  poles, border pipes, side frame, floating lamps). Lamp culling: other
  passages already cost nothing (they're frustum-culled). The lever is the
  shadow distance within the current passage, or MegaLights.
- **Editor crashes today, each with a lesson:** don't reload the open level from
  Python, and don't re-run heavy MCP scripts that keep UE wrappers at module
  level. Both are in memory.
- **At the next build window, before building:** apply Soft goods' patch A from
  git (`git show HEAD:Scripts/patches/2026-09-29_A_opening_cut_and_master_test.patch
  | git apply`, approved by the conductor under Gary's delegation). It adds the
  test `InfinityStage.Editor.SavedMasterMatchesShow` and tightens
  `SavedFixturePIE`. Commit it separately, crediting Soft goods. **Don't apply
  patch B** (held for Gary). Then build with `0af1130` and `1ef583b`.
  **Patch A has never been compiled.** If the build fails in it, don't fix it
  in place: `git checkout -- Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageEditorAutomationTests.cpp`,
  build without it, and send Soft goods the error. Expected with everything
  in: 81 pass, 1 fail (`SavedFixturePIE`). That's today's 77 plus 3 celestial
  tests plus 1 master test; the grooves add assertions only.
- **Hangar light event:** designed in `Docs/HangarLightEvent_2026-09-29.md`.
  Lumen gives sky occlusion for free. Pin exposure before any A/B/C test.

## 29 September, evening

- **Celestial: the running DLL walks the world every frame.** The DLL was built
  29 Sep 01:39, from the initial-commit code. `ApplyCyclePhase` walks every
  actor and logs `CELESTIAL_FOREIGN_LIGHTING_SUPPRESSED` on every phase apply.
  That's a constant cost, not a rhythm, so it can't be Gary's periodic hitch.
  `0af1130` makes it event-driven. `62d8f2a` removes the 2 s full-world
  safety-net walk, which never reached a binary, and re-hides only the actors
  already silenced. Build order: patch A, then `0af1130` + `62d8f2a`, then
  `1ef583b`.
- **Blink spots (Gary liked P01's).** P01 Wing 041 "Entry High -Y":
  - 2000 cd, cone 9.8/11.7, 9280 K, shadowed;
  - light function `MI_LF_Flicker_Buzz`;
  - a **22 cm source radius**.

  That radius is the "shadow focus" knob; UE's default is 0. A bar of width w at
  distance d from the lens throws a shadow w·D/d wide, blurred by 44·(D−d)/d,
  with peak darkness about w/44. So: near the lens is vast and soft; far out
  with a wider bar is smaller, with a core.
  - **Plan** (`blink_spots_plan_readonly.py` → `blink_spots_plan.json`): one per
    passage, two in P05.
    - Gobos are timber from the rig: the Forest pack's `SM_wood_beam_01/02`.
      Props take their mesh's own material; the Show has no override.
    - Distances run from 0.9 m (P05, vast and soft) through 1.25 m (P02, P01's
      twin) to 5.5 m (P06, the only hard core).
    - 9280 K at P05's second spot and P06, 4000 K elsewhere.
  - **Dry run passed:** census 612 → 618 casters; `blink_spots_apply.py`,
    `blink_spots_revert.py`. Apply approved by the conductor.
  - **Pools:** every pool, P01's included, now lands on walnut boards, except
    P03's (Wet Ground). Captures: `blink_capture.py`.
- **Structure 01 portal: defaults are load-bearing.** Soft goods baked the
  Opening drape against the portal's default colliders. The cloth wraps the
  OUTSIDE of the posts (inner face ±950, x ±20) at frames 170–180, and the
  heading is at 1020 under a header whose underside is at 1050.
  - Don't move the posts; that means a 3 h re-bake.
  - Raising the header is harmless; lowering it below about 1030 cuts the
    heading.
  - `portal_enable_apply.py` now works inside `main()`.
- **Build window: NEVER run the unfiltered suite** (conductor, 29 Sep evening).
  `PussStageBootstrap.RebuildCurrentMaster` rebuilds the Master from the Show and
  SAVES both (`InfinityStageEditorAutomationTests.cpp:718–748`). Scene 3's length
  is disputed: 585.64 s authored on 14 Sep, 65.542 s walked today. So an
  unfiltered run could bake a wrong answer over the evidence. Filter with
  `Automation RunTests InfinityStage.`: it matches `InfinityStage.*` and
  `PussStage.InfinityStage.*`, never `PussStageBootstrap.*`. Counts will differ
  from the 81/82 full-suite figure; report what the filter ran.
- **Stutter (Soft goods measured it, 29 Sep):**
  - Spikes every 1–1.5 s, owned by "Render Lights and Shadows", called 338 times
    per frame. **338 is P01's shadow-caster count exactly** (525 enabled), and
    336 of those also carry a flicker light function.
  - I left P01 out of the P04–P06 caster cut. Cutting P01 is a look change: Gary's
    call, not prepared.
  - The toggle A/B belongs to Soft goods. Pausing the transport freezes the wings;
    `ShowFlag.LightFunctions 0` kills the flicker.
- **Scene 4 hangar built** (`scene4_hangar_build.py`): 64 actors, tag
  `RigAtmos.Scene4Hangar`.
  - Size: 60 × 20 × 30 m around Scene 4's camera at (0, 280000, 180).
  - Surfaces: walnut floor, black-metal walls and roof, a 12 m lattice.
  - Light: a ghost light, 14 practicals, and a volume pinning exposure at EV100
    0.5 with Local Exposure neutral.
  - Backup `PreScene4Hangar-20260929-1441`; revert `scene4_hangar_revert.py`.
  - The lattice is out of the establishing frame (FOV 37.5°).
- **The fold is keyed** in `/Game/InfinityStage/RigAtmos/LS_S4_HangarFold`: 25 s,
  practicals attached to their walls, hinge tags rewritten to verified angles.
  - The build-time far-wall tag had the wrong sign.
  - Backup `PreScene4Fold-20260929-1452`; revert `scene4_fold_revert.py`.
  - Captures: in near-dark the motion reads only as silhouettes. The lights-up
    reads; the roof and lattice move out of frame. Whether to light the flats
    while they move is Gary's call. Motion blur isn't judged yet.

## 29 September, late evening: after the build

- **Build:** patch A (`e88a12d`), 0af1130 + 62d8f2a, 1ef583b, Look & camera's
  ae92198 + 01d3152.
  - The celestial test caught a redundant pre-BeginPlay walk, fixed in
    `37e711e`. That fix is NOT the stutter fix.
  - Suite `InfinityStage`: 84/1/85; the only red is `SavedFixturePIE`.
  - Next queue: Look & camera's 7e2c544 (+1 test) and Soft goods' held patch C.
- **Grooves on** (Gary: "Save it"). `Ground.GrooveMaterial` = MI_Kit_SteelGroove
  on all six structures, 3 plates per slot.
  - The re-fit also moved board counts: S01 +1, S02 −1, S04 +4, S05 −1, S06 −6.
    It's deterministic, and the cause is UNEXPLAINED: no board-laying code
    changed and the Show was untouched. Suspect station extents following
    evaluated wing positions at the current transport time. Investigate.
  - Backup `PreGrooveMaterial-20260929-2044`; revert `groove_material_revert.py`.
- **The grooves don't read** from eye height or 4.5 m (8 cm wide, recessed
  2.2–5 cm).
  - The close-up is blocked: the wing's upright stands in the slot. Next time,
    shoot straight down.
  - Levers for Gary: `SlotWidthCm` (8), `SlotInboardCm` (150; safe up to about
    380–630 per passage). `CatClearanceCm` 120 always keeps a 2.4 m lane.
- **Fold lit** (Gary): practicals strike 2–4 s, before the walls rise.
  - From outside, the lit wall and its rank of lamps visibly lift. From Scene 4's
    camera, the hall brightens as the walls rise.
  - Beams don't read as sweeping shafts: 400 cd, shadowless, wide cones.
  - Motion blur is unjudged; it needs playback.
  - Backup `PreFoldRelight-20260929-2103`; revert `scene4_fold_relight_revert.py`.
- **Lighting audit:** `Docs/LightingEfficiencyPlan_2026-09-29.md`.
  - Light Drama is authored on 20 of about 2500 lamps.
  - Stop proposing `MaxLightsPerPixel`.
  - Read `sg.ShadowQuality` with the fixed `vsm_cvars_readonly.py`, which now
    records whether each cvar exists.
  - `MaxDrawDistanceCm` does reach the lamps (`PassageActor.cpp:383`), so
    "distance culling not biting" is about the values, not plumbing.
- **Look & camera's request:** a `FloorHeightCm` getter on the structure actor,
  for the next source slot.
- **Scene 4 re-docked (29 Sep late).** The hangar's mouth now sits on "Scene 4 —
  External Sound — Entry Handoff Camera" (10668.5, 240000): P04's route end, and
  the camera the show cuts to.
  - The build and fold scripts READ the site from that actor; nothing is typed.
  - The level rests PACKED (frame 0), so nothing snaps on arrival.
  - The fold is nested in LS_DevScene_04 on a "Hangar Fold" subsequence track.
    Its section Time Scale is Gary's speed dial.
  - `scene4_fold_nest.py` derives the section end, the scene end (floor 15 s),
    the camera cuts, and a Master rebuild with a 13/13 check. Rerun it after any
    Time Scale change.
  - Scene 4 is now 25 s; show total 1003.396 s.
  - Backups `PreScene4Redock-*`, `PreScene4Nest-20260929-171111`.
  - `scene4_fold_revert.py` refuses while the fold hosts Look & camera's pitch
    subsequence.
- **Portals at every mouth** (Gary: yes, full stage front): Structures 02–06 on
  at defaults, via `portal_mouths_apply.py`; revert `portal_mouths_revert.py`.
  - The house floor now reaches P04's stalls seat (14 m back, top −120).
  - S03 has the frame only: no ground on S03, so no stage front.
- **Upper hangar lit** (Gary: options 1 + 2): 3 far-wall uplights (strike 4.0 s
  in the fold) and 24 emissive lattice bulbs (`M_RigAtmos_WorkBulb`), via
  `scene4_uplight_apply.py`; revert `scene4_uplight_revert.py`.
  - At a 30° tilt the lid closing reads (roof underside lit through the lattice
    at 15.5 s).
  - At 48° it's still black: grazing light on black metal. The levers are a
    lighter surface, steeper and brighter uplights, or haze.
- **Map-dirty after benches:** `level_verified_save.py` saves only if the hangar
  is exactly at rest (and the uplights at 0 cd) and the handoff cameras are
  untouched. The conductor approved it for clearing no-net-change flags.
- **Floor rise (Gary; no rim):** floor slabs 2 and 3 rest HANGING (−90°) and rise
  (1–4 s and 3–6 s); the ghost light rides slab 2. In capture, a glow breaks on
  the horizon at about 2.5 s, then the lamp arrives standing.
  - Built by `scene4_floor_rise_apply.py`; revert `scene4_floor_rise_revert.py`;
    backup `PreFloorRise-*`.
  - The fold record's rest pose was updated; `level_verified_save.py` reads it.
- **Preview-restore lesson (also in memory):** snapshot originals as floats; a
  UE struct wrapper tracked the live rotation and left Floor 3 flat. The
  verified save caught it.
- **Look & camera's score is hosted inside the fold** (`LS_S4_CameraScore`, a
  subsequence of `LS_S4_HangarFold`), so the fold's Time Scale retimes both.
  - Their keys follow the side walls (4–8.5 s), the far wall (8–12 s), the roof
    swing (12.5–18.5 s), the lattice (18.5–22.5 s) and Scene 4's exit cut (24 s).
  - Before ANY fold rework, ask them to unhost it (`revert_scene4_score.py`), then
    send them the new timings. `scene4_fold_revert.py` refuses while it's hosted.
  - The floor slabs 1–3 and the ghost light sit in their level window (0–4.3 s).
- **Approach measured** (`scene4_approach_capture.py`, rendered with and without
  the hangar): the hangar is 0.25–1% of the frame from 43–85 m out and nothing
  of it is lit. Floor slab 1 (never moves) reads as floor past the tunnel end.
  Gary's objection is the inward wall swing ("boxing-in" vs pop-up); the design
  is his to choose.

## 29 September, night: Scene 4 v2, the whole box rises

This SUPERSEDES the fold above for playback. v1 (`LS_S4_HangarFold`) is kept
but no longer referenced.

- **Gary's sketch, Order A.** The whole box hangs below the passage floor,
  hinged at the mouth. It rises ASSEMBLED and dark except the ghost light; then
  the lights strike, the roof swings over and the lattice flies in. The walls'
  inward swing is dropped. The camera is stopped at the end of the path.
- **Rig.** "S4 Hangar Root" (tags `RigAtmos.Scene4Root`,
  `Hinge|edge=mouth|axis=Y|closed=-90|open=0`) carries the floor slabs, walls,
  far wall and lattice fly.
  - The hinge is world Y through (11168.5, 240000, 0): the handoff camera +5 m.
  - A world-fixed 5 m walnut apron ("S4 Hangar Apron") bridges camera to hinge.
    With the hinge under the lens the lip sat 84° down, out of frame (Look &
    camera's catch).
  - The PPV stays world-fixed. The level rests at frame 0: root −90, box hanging
    60 m down.
- **Sequence** `/Game/InfinityStage/RigAtmos/LS_S4_HangarRise`, 30 fps, 31 s:
  - rise 1→16 s, which is exactly smoothstep:
    θ = −90 + 90·(3u² − 2u³), u = (t − 1)/15;
  - practicals in L/R pairs from 16.5 s, 0.3 s apart, all on by 18.5;
  - uplights strike 18.0/18.15/18.3;
  - roof 18.5–24.5;
  - lattice z 28 → 12 m over 24.5–28.5;
  - hold to 31.
- **Nested.** Scene 4's "Hangar Fold" section now plays LS_S4_HangarRise
  (`scene4_fold_nest_v2.py`, a wrapper round `scene4_fold_nest.py` with
  `FOLD_PATH`).
  - Scene 4 runs 596.471–627.471 (31 s); cuts [0,30] and [30,31]; show total
    1009.396 s; Master 13/13, worst 0.000 s.
  - Time Scale is still Gary's dial. `scene4_fold_check_readonly.py` knows both
    sequences' motion ends (22.5 s and 28.5 s).
- **Verified.**
  - Save gate: dirty 0+0, no ZZ_.
  - `level_verified_save.py` is v2-aware: when `scene4_v2_record.json` exists it
    checks root −90, roof upright, inner hinges 0, lattice root-relative z, and
    lamps at 0 cd.
  - Arc: 512 points recomposed through the attachment chain never enter the
    passage. Analytically, x′ ≥ 0 for every box point with x, z ≥ 0 between −90
    and 0.
  - Captures in `Saved/CodexStructure/Captures/RiseV2/`:
    - p0: dark with lattice dots, the glow breaking over the lip at about 12 s,
      hall lit by 18 s, uplight shafts reading as cones;
    - p-15: lip and lamp by 14 s;
    - side, EV −3: the mechanism reads plainly.
  - NOT yet played in PIE.
- **Numbers for Look & camera.** `scene4_v2_numbers_readonly.py` (read-only)
  prints every actor's LANDED extents relative to the camera, plus Scene 4's
  cuts.
  - Ghost bulb at +30 m, y −4 m, z 1.88 m.
  - Box interior x +5..+65, y ±10, z 0..30; roof upright to z 90.
  - They re-host `LS_S4_CameraScore` in LS_S4_HangarRise.
- **Revert** (Scene 4 first, then the level):
  - `scene4_fold_nest_v1.py`, then `scene4_v2_revert.py`, which works from
    `scene4_v2_record.json`.
  - Backups `PreScene4V2-20260929-2015`, `PreScene4Nest-20260929-201525`.
- **Capture script.** `scene4_fold_capture.py` takes per-view exposure
  (`FOLD_VIEW_EV`); `scene4_v2_side.py` uses it.
- **Still to do:**
  - patch R's fix message names LS_S4_HangarFold; update it to HangarRise
    before it's applied;
  - the "mechanical rig" lighting steer (Gary, on hold until the mechanism
    settles);
  - PIE playback of the rise.

## 29 September, night: the board drift is explained and closed

- **What moved.** The groove re-fit (16:33) was the first fit after the 14:52
  build. It changed board counts on S01 +1, S02 −1, S04 +4, S05 −1, S06 −6
  (S03 has no floor).
  - Behind those counts, the joint pattern changed in 288 of the 337 lanes. The
    other 49 lanes' first boards are cut by a slot either way.
  - Stations, slots, lanes, widths, extents and grooves did not move. Nothing
    anyone authored moved.
- **Why.** `BuildGround` seeds each lane's first board with
  `Stream.FRandRange(Min, Max) * Stream.FRandRange(0.2, 1.0)`. C++ leaves the
  evaluation order of a product's operands unspecified.
  - The grooves commit `1ef583b` edited that function. The rebuild then
    evaluated the length draw first where the old binary drew the fraction
    first.
  - The same expression in `BuildPortal`'s stage front is evaluated fraction
    first by today's binary: the compiler chose differently at two sites.
- **Proof.** `board_dump_readonly.py` dumps every board (read-only).
  `board_drift_analysis.py` is offline Python. It re-lays each lane from the
  Passage GUID using CityHash64, HashCombineFast and the FRandomStream LCG, all
  per the UE 5.8 headers.
  - Length first reproduces every board of all 337 lanes: position within
    0.05 cm and tone bit-exact.
  - Fraction first reproduces the OLD counts exactly: 7170 / 2615 / 2915 /
    6381 / 7068.
  - For the stage front, `portal_data_dump_readonly.py` shows 690 decisive lane
    starts on S02 and S06, all fraction first.
- **The conductor's three questions:**
  - Deterministic? Yes. The layout is a pure function of the inputs and the
    binary.
  - Compounding? No. It toggles between two layouts, and only when a rebuild
    flips the compiler's choice.
  - Visible? Only as a different random joint stagger.
- **Fix, held, not built:** `Scripts/patches/2026-09-29_S_board_draw_order_pin.patch`.
  - It splits the draws into sequenced statements, each in today's saved
    order: the floor draws length first, the stage front fraction first. The
    unused cloth yaw is split too.
  - New test `InfinityStage.Structure.SavedFloorsSurviveARebuild` reads both
    orders back from the boards.
  - Applying it re-rolls nothing. Backup `Backups/PreDrawOrderPin-*`.
- **Also a hazard, not mine, stored data safe:**
  `UInfinityStageShowAsset::ReplicateLightAttachmentsWithVariation`
  (`ShowAsset.cpp:551/553`) draws three jitters as function arguments, whose
  order is unspecified. Its output is written into the Show, so saved lights
  are safe. The "same seed, same corridor" promise, though, holds only within
  one binary.
- **Future comparison:** re-run the dump and the analysis after any re-fit.
  Every lane must reproduce exactly.
- **Patch R updated.** Its fix messages now name both `LS_S4_HangarFold` and
  `LS_S4_HangarRise`.
  - Bare, `scene4_fold_nest.py` now KEEPS whichever sequence Scene 4 plays.
    Before this it defaulted to v1 and would have re-pointed Scene 4 back to
    the fold.
  - Only the `_v1`/`_v2` wrappers re-point. Dry run confirmed:
    LS_S4_HangarRise, 31 s, nothing mutated.

## 30 September, overnight (Gary away): what landed

- **Build (conductor-driven):** C, F, D, E, R and S are in; suite 88 / 1 / 89.
  - The one red is a new assertion in Soft goods' file.
  - The applied tree is committed as `9da3c82`.
- **Held for the next build:** patch G, `Scripts/patches/2026-09-30_G_scene_arrival.patch`.
  - What it adds: `AInfinityStageArrival` ("one curve, two evaluators"). A Scene's opening
    motion is keyed at negative time; the Arrival plays it before the Scene starts, from
    the Passage track, and Sequencer plays it after.
  - The hook: 8 lines in `MovieSceneInfinityPassageTrack.cpp`, which is Director's file.
    It carries a comment, was approved by the conductor, and **Director should review
    it**.
  - The test: `InfinityStage.Arrival.OneCurveAcrossTheSceneBoundary`.
  - Codex failed on capacity; the patch was written by hand.
- **Capture convention (in memory):** Manual + Exposure Compensation is NOT EV100.
  - Those captures render several stops darker than the show.
  - Capture with no exposure override instead: it is byte-identical to the show.
  - A scene capture cannot hide a light.
  - The convention hid the P04 pit's bulb dots on 29 Sep.
- **Mouth lanterns P02–P06:**
  - One spot per mouth, low and raking from house left, 210 cd, 2800 K.
  - The intensity is calibrated to the show's real exposure: the unbound PPV pins EV100 −3.
  - P04's drape reads: median R 95, lit faces 171–194, no clipping.
  - Revert: `mouth_lanterns_revert.py`.
- **Lattice glow (Gary's note):**
  - The bulbs were emissive cubes, and no light rode the lattice.
  - Added: 24 shadowless 20 cd point lights, plus burnished-steel beams.
  - The glow **rests at 0 cd** and fades in over 4–8 s in the rise. It had leaked into P04's
    approach; I found the leak by projecting every light into that camera.
  - Legible pixels at 10 s: 0.06% → 9.8%. Frames from 14 s on are unchanged.
  - The verified save now checks the glow is at 0 cd at rest.
- **P04 end:** colliders and timing for Soft goods' bake are in
  `Docs/P04EndColliders_2026-09-30.json`.
  - Static floor runs to the hinge. There is an 18.5 cm hole at x 10650–10668.5 to close
    with Structure 04 ApronCm 420.
  - The camera moves at a constant 2.5 m/s and stops dead at x 10668.5.
  - Recommended cloth line: x 10450.
- **Exposure at P04's end:**
  - Today the hangar volume starts 1 m before the stop, so a 3.5-stop drop lands on the
    cloth crossing.
  - Three strips (A instant / B over 26 m / C over 10 m) were simulated without touching
    the volume.
  - This is Gary's pick.
- **Parametric hangars:** `hangar_build.py` builds any Scene's hangar from numbers in its
  dock frame.
  - Scene 4 is reproduced to 0.000 cm.
  - Built: S1, S2 (on its terrain), S3 (around its cast), S5 (200 × 150 × 50 m) and S6
    (no roof).
  - Revert (`hangar_revert.py`) was tested on S6; S6 was then rebuilt.
  - **None is nested yet.**
  - Scene 3 has four to-dos before nesting: the far Celadon panel clip (−30° to −20°),
    light calibration for EV −3, the ghost light among the cast, and the enclosure's
    effect on its open-sky light.
  - Scene 5's lighting does not scale with its size.
- **Gary's four answers (29 Sep night):**
  - the rise is settled;
  - "the passage rig again" for the hangar's lighting;
  - grooves to 16 cm;
  - P03's recipe on P01's casters.
  The last two are approved but queued behind the transition focus.
- **Still Gary's:** exposure option A/B/C, lattice glow brightness (20 cd), haze, and
  S5's scale.
- **Later that night:**
  - **Grooves are now 16 cm on all six floors** (revert: `groove_width_apply.py` with
    `GROOVE_WIDTH_REVERT`).
    - From eye height and in the rhythm view, 0.05% of pixels changed: the slots sit
      150 cm inboard, under the wings. The legibility lever is **SlotInboardCm**, not
      the width.
  - **P01 shadow pass: casters 338 → 99** (P04/P06 rule: keys Entry Top and Entry Fwd +Y
    keep their shadows). Revert: `p01_shadow_revert.py`.
    - Exempt: the Wing 041 blink spot and the house spots.
    - The look is held at the show's exposure. Frame rate is not yet measured.
  - **Lighting now scales with hangar size** (rails, bulbs, glow within a budget,
    uplights). S5 was rebuilt and reads.
  - **Structure 04 ApronCm is now 420**: the P04 boards meet the hangar apron, for the
    backcloth bake.
  - **`p04_arrival_apply.py` is ready** (dry run: release −3.574 s, rise 19.57 s, landing
    at 16 s). It needs patch G built.

## 30 September, morning: the other five arrivals, placed inert

The conductor approved steps 1 and 2 of 3 for Scenes 1, 2, 3, 5 and 6 under Gary's 29 Sep
delegation. **Step 3, nesting each hangar into its Scene, is Gary's and has not been done.**

- **What was written** (`arrivals_apply.py`):
  - Each `LS_SN_HangarRise` root pitch is re-keyed the way Scene 4's was: −90 at −3.567 s,
    then 0 at the builder's landing (16 s × K), AUTO. Every later beat is unchanged.
  - An inert `SN Arrival` is placed on each root. Its cue GUID is read from the Show (the
    Show is never written) and its binding GUID from the rise.
  - Backup: `Backups/PreArrivalSequences-20260930-0652` (the level, the five rises, and the
    Show). Record: `arrivals_record.json`.
  - Revert: `arrivals_revert_run.py`. Read-back: `arrivals_check_readonly.py`.
- **Verified from saved state:**
  - The Show is byte-identical to the backup, and no Scene sequence was written.
  - Each rise is referenced by the level only.
  - Each new Arrival declines two seconds before its Scene. S4, the control, resolves
    −88.361° there.
- **The one live side effect:** each unnested Arrival logs
  `INFINITY_STAGE_ARRIVAL_SKIPPED reason=NoSubSection` once per play session. That is a
  test warning, not a failure: this project does not elevate log warnings. It also costs
  one Show compile per Passage frame each, about 0.05 ms, so about 0.25 ms for all five.
- **Order of operations:** `hangar_revert.py` now refuses while an Arrival references the
  rise. Run `arrivals_revert_run.py` first.

| Scene | Box d × w × h (m) | K | Builder rise | Keyed rise (start → land) | Pitch at the cut |
|---|---|---|---|---|---|
| 1 | 60 × 20 × 30, placeholder | 1 | 15.0 s | 19.567 s (−3.567 → 16.0) | −82.119° |
| 2 | 60 × 20 × 30, placeholder, on terrain | 1 | 15.0 s | 19.567 s (−3.567 → 16.0) | −82.119° |
| 3 | 60 × 20 × 30, hinge −120 cm | 1 | 15.0 s | 19.567 s (−3.567 → 16.0) | −82.119° |
| 5 | 150 × 200 × 50 | 1.581 | 23.733 s | 28.867 s (−3.567 → 25.3) | −86.218° |
| 6 | 60 × 20 × 30, no roof | 1 | 15.0 s | 19.567 s (−3.567 → 16.0) | −82.119° |

- **Derived vs guessed:**
  - **The start is transplanted, not measured (all five).** It is S4's applied start,
    which is P04's cloth release. Every Passage ends at 2.5 m/s, so the same time before
    the cut is the same distance before the stop. No backcloth exists in those Passages,
    so the first 3.6 s of rise would be visible from the Passage, uncovered. That look is
    decided at nesting.
    - Once a bake passes for Passage N, revert, then rerun with
      `ARRIVAL_RISE_START_S = {N: cross_N − lead_N}`, where
      `cross_N = −(distance from cloth line to stop) / 250`.
    - Passage tails before each stop, from `arrivals_probe.json`: P01 334 cm (last
      interval at 3.0 m/s), P02 608 cm, P03 672 cm, P05 341 cm, P06 390 cm.
  - **S1, S2, S3, S6 carry S4's curve exactly** (K = 1). S1's and S2's boxes are
    placeholder sizes, so resizing them changes K and moves the landing.
  - **S5 is a judgement, not a measurement.** Its curve combines two rules: the start from
    P04's cloth and the landing from the K law. The K law (time ∝ √length) is my builder's
    assumption and Gary has never seen it. The peak tip speed is about 12 m/s, against
    Scene 4's 7 m/s. At the cut the box has barely begun (−86.2°).
  - **S6 is a judgement:** the curve is S4's, but a roofless box rising, and the empty
    roof beat (18.5–24.5 s) after landing, have never been looked at.
  - **S3:** the far Celadon clip (−30° to −20°) now falls at Scene time 8.43–10.03 s,
    inside the Scene. Its four to-dos stand.

## 30 September, morning: why the authored hold is dark (diagnosis; nothing changed)

- **The ghost light is occluded, not mis-aimed.** "S4 Ghost Light" is an omni point light:
  60 cd, 15 m attenuation, shadowed. It rides Floor 2 Hinge, 25 m into the box and 1.88 m
  off the floor.
  - From the stop, the camera sits **under the floor plane** of the hanging box: 471 cm
    at the cut, 386 cm at +3 s, 31 cm at +9.5 s.
  - The lamp, and everything within its reach, is behind the floor slab. The bulb clears
    the lip at +9.5 s: the same threshold Look & camera measured photometrically.
  - Counterfactuals (`ghost_geom.py [reach] [lamp_x]`):
    - With the reach removed, at most 0.08 lux lands on anything visible at +3 s.
    - With the lamp at the mouth, the bulb shows from +6 s instead of +9.5 s.
  - **No lamp inside the box fixes the hold.**
- **The lattice is in view from the cut** (`lattice_vis.py`). It is flown on the trough's
  open side, outside the floor's shadow, and 6 → 9 → 12 of its 24 bulbs are in a −15°
  look-down at the cut, +3 s and +6 s. It is dark only because its glow is keyed at 0 cd
  until +4 s.
- **Do not move the 4–8 s glow fade before the cut.** The leak it fixed was a REST-state
  problem: before the cut, nothing evaluates the rise's light keys, so the P04 approach
  sees the level's saved rest value, which must stay 0 cd.
  - A fade starting AT the cut lights the hold without reopening the leak.
  - A key before the cut does nothing in the show but changes nothing either. What must
    never change is the rest value.
  - Whether to light the hold at the cut is Gary's look decision. Whether 20 cd reads at
    the show's exposure is Look & camera's bench.

## 30 September: G3 held (arrival quiet while unnested)

- `Scripts/patches/2026-09-30_G3_arrival_unnested_quiet.patch` (conductor-approved; not yet
  built).
  - An Arrival whose motion is not nested now checks that BEFORE compiling the Show.
  - It logs `INFINITY_STAGE_ARRIVAL_WAITING … reason=NotNested` once at Display, instead
    of a per-session warning.
  - The Arrival test gains the unnested case, still one test, with an exact-once expected
    message.
- Apply at build time only: `git apply Scripts/patches/2026-09-30_G3_arrival_unnested_quiet.patch`.
- DLL marker: `INFINITY_STAGE_ARRIVAL_WAITING` (UTF-16).
- Backup of the two files: `Backups/PreG3ArrivalQuiet-*`.

## 30 September, morning: S5 speed and S6 roof beat, as pictures for Gary

- Sheets: `Saved/CodexStructure/Captures/RiseSpeed_S5_vs_S4_Sheet.png` and
  `RoofBeat_S6_vs_S4_Sheet.png`.
  - Frames come from `rise_compare_bench.py`: the owner's keys are scrubbed in Sequencer,
    with no exposure override.
  - The sheets are composed offline by `rise_sheets.py`, which also measures the caption
    numbers.
- Bench runs: S4 speed, S5 speed, S4 roof, S6 roof, S4 arc and S6 arc.
  - Every run wrote its originals to `BenchOriginals/` before posing anything.
  - Nothing needed restoring, and every run ended with 0+0 dirty.
- **S5 speed:**
  - From the stop the cat stands almost on the hinge, so the eye reads the SWEEP: 4.7°/s
    against Scene 4's 6.9°/s. S5 therefore reads about 1.5× slower, not faster; its far
    wall's 12 m/s is 150 m away.
  - From the stop S5 is black until about 12 s. After landing, 1.2% of its frame is lit,
    against Scene 4's 20.8%.
- **S6 roof beat:**
  - Outside, S6's frame changes 0.00% from 18.5 to 24.5 s.
  - From the stop looking up, S4's roof shows only as a glint (22.5 s) and a lit ceiling
    (24.5 s). Once shut, S4 and S6 are the same frame (0.4% of pixels differ).
  - **Scene 4's own roof beat barely reads from the cat's position.**
- Caveat: Sequencer does not evaluate before the playback start (0). The −3 s side frame
  shows rest (−90.00°), not −89.78°.

### Correction and the ground-plane fault (30 Sep, late morning)

- **Correction:** the speed sheet's "1.2% vs 20.8% lit" compared S5 just landed with S4
  after its uplights. At MATCHED phases (Scene 4's beats × K), measured from the stop:

  | Phase | S4 lit | S5 lit |
  |---|---|---|
  | landed | 1.0% | 1.2% |
  | uplights on | 20.7% | 2.8% |
  | end | 24.0% | 4.9% |

  - On the floor half of the frame: S4 20.6%, S5 2.0%.
  - Sheet: `Captures/WhyS5Dark_Sheet.png`. The speed sheet's caption now points to it.
- **Ground-plane fault: five sites, not three, and two mechanisms**
  (`hangar_ground_survey_readonly.py`, `ground_beyond_hinge_readonly.py`).
  - **Planes (S1, S5, S6).** The Passage's own hand-placed floor plane (a scaled Cube,
    1 cm thick, top 5 cm below the hinge) runs past the Passage end:
    - S1: 399 m ("Opening Floor");
    - S6: 139 m ("Opening Floor2");
    - S5: 16 m ("Dark Wood Floor2"), so only the first 16 m of its box.
    - Nothing stands on any of them beyond the hinge. One fix: end each plane at its hinge
      line, as P04's Structure Ground does, with the near end unchanged.
  - **Landscapes (S2, S3).** The Passage's landscape covers the whole footprint: S2 at
    hinge level, S3 1.2 m above its lowered hinge. The box hangs underground and rises
    through the terrain. A landscape can't be shortened; it needs a hole, which is a
    different fix and touches the Passage environments.
  - **S4 is the only clean site** (a void beyond the hinge).
  - The builder allowed all five by name, so they are deferrals, not misses. Its blocker
    test also skips anything wider than 10 km; that isn't the cause here, but it is a gap.
