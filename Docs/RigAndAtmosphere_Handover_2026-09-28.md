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
