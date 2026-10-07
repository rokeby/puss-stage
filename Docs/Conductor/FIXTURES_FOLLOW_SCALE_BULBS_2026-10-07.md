# Fixtures: follow the aim, scale x3, bulbs out of the cans (7 Oct 2026)

Tooling is in `Saved/CodexConductor/FixturesFollow/`. Nothing has been run in the editor. No Show, level or config write
has been made, and nothing is committed. The offline harness passes (46 checks, every one with a negative control).

Tiers, per claim: **[decl]** a header, signature or source line we can read; **[meas]** read back from a file or log, or
an offline run; **[inf]** inferred, with the reason. The live DRY settles each [inf] item, or stops on it.

## Summary

1. **You can aim the lights yourself, and the cans follow [decl+meas].** Rotating a rig light in the editor writes
   its full transform back to the Show. Each housing (can) is computed from its light's Show transform when the
   Structure is re-fitted, so a re-fit re-aims every can.
2. **There is no housing data to author [decl].** FOLLOW therefore re-fits the Structure and then proves that every
   can matches its light. It refuses with a NOOP when nothing is stale.
3. **x3 is a single structure field plus the bulb rows [decl].** Housings take `Fixtures.BodySizeCm` (1x to 3x). The
   lens offset scales with it automatically. Bulbs are scaled 3.2 to 9.6 about the glass centre.
4. **At 3x the bulbs are about 1 m tall [meas].** The A60 becomes 106 cm and the G95 130 cm. The Fresnel becomes
   91x71x148 cm and the ParCan 120x93x134 cm.
5. **Today's bulbs are 3.2x real size, not real size [meas].** Every swap record carries `bulb_scale: 3.2`.
6. **RELOCATE takes 212 dim or dead bulbs out of the cans [meas offline count].** About half hang on cords under
   their bay's crossbeam. The rest lie or stand on the floor, clear of the camera lane. 13 working practicals stay in
   their lanterns.
7. **Glimmers: all 32 PRACTICAL_GLIMMER lights go, and each spot gets a bare bulb [meas offline].** The glimmer body
   row becomes the bulb and the glimmer light row becomes its cord. No GLIMMER_CAP rows exist.
   `scores_glimmer_config.py` removes the glimmer from the GAP look, so a scores re-apply cannot bring the lights back.
8. **Each relocated bulb's paired dim light is retired by default, so its can disappears with it [decl].** A
   reflection then comes from the emissive glass alone. Keeping a small light on each bulb with no can needs a
   one-flag C++ change (section D3).
9. **Every write follows the same pattern** as the tools before it: record first, a `Backups/` snapshot, rollback in
   memory, narrow saves, read-back and markers. REVERT is available for SCALE and RELOCATE.
10. **Your decisions are listed at the end.** The bulb size and the light-on-bulb question come first.

---

## A. Mechanism

### A1. How lamps, housings and bulbs are represented

| Thing | Where it lives | Proof |
|---|---|---|
| Rig light (TOP, LOW_SIDE, BEAM, PRACTICAL...) | A Show `FInfinityCueAttachment` of kind LIGHT on a WingPair cue, with `RelativeTransform` (InfinityStageTypes.h:439-498). Materialized as a spot, point or rect light actor attached to the Passage actor. | [decl] |
| **Housing (Fresnel / ParCan "can")** | **Not a Show row.** One ISM instance per **enabled, Station-anchored LIGHT** on every WingPair cue at a station, in placement order. Practical point lights are included (InfinityStageStructureActor.cpp:142-180, 1920-1955). One `BodyMesh` / `BodySizeCm` / `BodyMaterial` per Structure (InfinityStageStructureActor.h:396-416). | [decl] |
| Hanging line above a housing | Generated with the housing. It exists only when lateral <= GridHalfWidth and 1 <= drop <= MaxDropCm (cpp:1957-1975). | [decl] |
| Bare bulb (Meshy SM_Bulb_* / SM_FX_Bulb_*) | Its own PROP row `<label>_BODY`, paired with its light by label only. The swap placed the glass centre on the light origin (meshy_swap.py:1-40, records). **It does not follow its light.** | [decl] + [meas] |
| `_CAP` cylinder | PROP row. It was disabled by the swap in P03 (21) and P05 (93) only. | [meas] |

The C++ housing formula, mirrored in `fixtures_common.housing_pose`, works like this [decl, cpp:1941-1953]:

- `Throw` is the light's own **X axis**.
- The rotation is `MakeFromXZ(Throw, Up)`, or `MakeFromXY(Throw, StationAcross)` when `|Throw.Z| > 0.98`.
- The body centre is `light - Throw * BodySize.X / 2`, and the mesh is fitted by bounds.

So **roll is ignored**, and a point light's housing faces the point light's own X axis.

### A2. When you rotate a light in the editor

- **Gizmo rotate or move (on release):** `HandleActorsMoved` writes the whole relative transform, rotation included,
  into the Show attachment (InfinityStageEditorModule.cpp:227-300, the write at :286). Log line:
  `INFINITY_STAGE_ATTACHMENT_MOVED`. [decl]
- **Typing in Details:** `HandleObjectPropertyChanged` writes the light settings plus the transform (:307-405, the
  transform at :395). Log line: `INFINITY_STAGE_ATTACHMENT_LIGHT_UPDATED`. [decl]
- **Proof it happens with a rotation [meas]:** the editor log `Saved/Logs/PussStage-backup-2026.10.07-23.22.07.log`
  has, at 23:08:12 UTC today, `ATTACHMENT_LIGHT_UPDATED ... 'P03 SCORE B10 GAP PRACTICAL_GLIMMER'
  property=RelativeRotation` followed by `ATTACHMENT_MOVED updated=1`.
- **Field:** `FInfinityCueAttachment::RelativeTransform`, relative to the attachment's anchor (the pair at its
  station). [decl]
- **Not written** [decl]:
  - in PIE (game world, :230, :321);
  - when an open Sequencer keys that actor's transform (`INFINITY_CAPTURE_SKIPPED_SEQUENCER`, :263).
- **The Show is left dirty.** "save it intentionally" (:295). [decl]

### A3. Does a re-materialize re-orient the housing?

**Yes, but only on a Structure re-fit** (`MaterializeStructure`, cpp:488; the Details button "Materialize Structure",
cpp:762). [decl]

- The Passage materialize does not touch the Structure. The text "Structure" does not appear anywhere in
  `InfinityStagePassageActor.cpp` [decl, searched].
- The tools call both (`lighting_scores_apply._materialize_passage`, :2879-2896).
- The Structure **knows it is stale**: its signature hashes every placement's location, X axis and Z axis (cpp:218-252),
  and `IsStructureCurrent` compares it (cpp:358-370). A test proves that a moved light reads stale
  (InfinityStageStructureTests.cpp:371-373). [decl]

What does **not** follow a re-aimed light:

- **The bulb PROP row** (A1).
- **Light Drama pan and tilt.** These run in the game only, at about 6/3 deg in the rows we read [meas, row
  `drama.pan_amplitude_degrees`], while the can stays static.
- **Roll.**

### A4. How P01 worked on 6 Oct [meas]

1. You hand-moved and rotated the score lights of **P01 Wing 003 (B03)** and **Wing 004 (B04)** in the editor.
2. The drift report `Saved/CodexConductor/LIGHTING_DRIFT_2026-10-06.md` (run DRIFT-20261006-184442) classifies those
   rows' `relative_transform.location` and `rotation_xyzw` changes as hand edits. Example: TOP_L rotation
   `[0.3586,0.3586,-0.6094,0.6094] -> [0.1123,-0.1825,-0.5118,-0.8319]`.
3. `p01_rig_pattern.py` (run 20261006-184409) then copied each role's relative location and rotation from the template
   bay of the same side-parity to every other P01 bay. P02 and P03 got the same treatment from P01 on 7 Oct
   (`p0N_rig_pattern_record.json`).
4. The cans did not follow until the Structures were re-fitted. The morning summary records bodies "up to 14.3 m from
   their lights in P06".

The 6 Oct editor log has rotated away (only 7 Oct logs remain in `Saved/Logs`), so the write-back events of that day
cannot be shown directly [searched].

### A5. What to do to aim a light so the tool can follow

1. Close any Sequencer that keys the lamp, and stop PIE.
2. In the viewport, select the **light actor** under `Passage 0N`. This is the spot or point light itself, not its
   can; the can has NoCollision and is not selectable as a row (cpp:798).
3. Rotate it, and move it too if you like. Only the aim (X axis) matters to the can.
4. **To repeat one bay's aim across the passage:** hand-aim one bay per side, then ask for the rig-pattern copy, as
   with P01. Do not use Cue Desk "Replicate First Pair's Lighting" on score bays: `ReplicateLightAttachments` **deletes
   and re-creates every LIGHT row** of the targets (InfinityStageShowAsset.cpp:619-630).
5. **Save the Show** when you are happy (Ctrl+S on the Show asset), or tell us to save it with FOLLOW.
6. Then either click **Materialize Structure** on `Infinity Stage - Structure 0N` and save the level, or let us run
   **FOLLOW** for that passage. FOLLOW does the same re-fit, but checks every can and saves narrowly.

---

## B. FOLLOW (op `FOLLOW`)

Housings are derived purely from the lights [decl, A1/A3], so **a re-materialize is enough**. FOLLOW is that
re-materialize, with proof added:

- **DRY**
  - Reads the stations (`gather_stations`) and pair frames (`OccurrenceOffset * StationWorld`, cpp:159).
  - Rebuilds the placement list exactly as `GatherFixturePlacements` does.
  - Predicts every can.
  - Compares each prediction with the live ISM instance at the same index. The test is the 8-corner gap, which is
    mirror-safe (memory ue58-ism-readback-and-test-traps).
  - Lists stale cans, with their aim error in degrees, and prints `plan_sha256`.
- **APPLY**
  - Writes a backup (`Backups/PreFixFollowFollowP0N-*`) and a record.
  - Runs `materialize_structure()`.
  - Asserts:
    - the ISM count equals the placement count;
    - every can is within 0.5 cm of its prediction;
    - `IsStructureCurrent` is true;
    - the Show rows are byte-identical (FOLLOW never writes a row).
  - Runs a narrow save, then reads back again.
  - The record is archived `.done-<run>`: there is nothing to revert.
- **REVERT** is refused by design, with the reason. Re-aim the light, or restore the backup.
- **Nothing stale** gives `FIXFOLLOW_FOLLOW_NOOP`, never the OK marker.

Offline evidence: the Python port of `GatherFixturePlacements` reproduces the live housing counts recorded by the swap
read-back exactly. That is 284, 132, 103 and 598 for P01, P02, P03 and P05 (harness B8) [meas]. P04 and P06 snapshots
are incomplete (P04 prototype bays; P06 relayout today), so they are not compared offline [inf].

The bulb rows do not follow. If you re-aim a practical, its bulb stays put; RELOCATE moves the bulbs away from the cans
anyway.

## C. SCALE (op `SCALE`)

- **Housings**
  - `Fixtures.BodySizeCm` = lantern bounds x (live scale x `housing_factor`). Mesh and material are untouched.
  - Where the scale lives: the Structure, not the Show (h:396-416) [decl].
  - Refuses unless the live scale is the expected 1.0. This stops a double apply (harness C4).
- **Lens offset at 3x [decl + meas]**
  - The C++ puts the light on the bounds front face, so the lens lands at `lens_offset_local x scale`. It scales
    linearly by itself (harness C3).
  - Fresnel: (-2.4, 0, -6.4) cm becomes (-7.1, 0, -19.2) cm.
  - ParCan: (-2.9, 0, -7.5) cm becomes (-8.6, 0, -22.4) cm.
  - At 3x the lens radius is 21.9 cm (Fresnel) and 29.0 cm (ParCan), so the beam origin still falls on the lens disc,
    above its centre.
  - Exact lens-on-light needs C++ (D3, patch 2).
- **Bulbs**
  - Every Meshy bulb PROP row is scaled 3.2 to 9.6 **about its glass centre**, so the glass stays where it is (C1, with
    a control showing that a pivot scale moves it by more than 10 cm).
  - A bulb not at 3.2 is refused, not rescaled (C5).
  - Where the scale lives: each bulb row's own `RelativeTransform.Scale3D` [decl].
- **Order**
  - SCALE refuses while a RELOCATE record is active, because scaling a resting bulb lifts it off the floor and breaks
    its cord. **Run SCALE first.**
  - SCALE re-fits the Structure, so it also does a FOLLOW.
- **Girders**
  - The DRY builds the crossbeam and rail OBBs per station from the live gridiron settings and stations (cpp:1258-1300).
    It reports cans that interpenetrate them at 1x and at 3x.
  - Offline estimate [inf]: grid half width assumed 1350, rails as long bars, own station only. P01 71 at 1x vs 77 at
    3x; P02 27/31; P03 42/46; P04 19/20; P05 156/156; P06 32/35 (stale snapshot).
  - Most hits **already exist at 1x**: TOP lamps sit at z 1180-1420, inside the v3 girder band, which is handover open
    item 6. 3x adds only a handful. The live DRY gives the exact list.
- **Hanging lines** get shorter at 3x, and some TOP cans' tops rise past the grid top, which drops their line. APPLY
  records `hanging_line_count` before and after, and prints `lines=a->b`.

## D. RELOCATE (op `RELOCATE`), glimmers included

### D1. Proposed placement (deterministic; one sha256 per GUID and key, never a random stream)

**Counts** [meas offline, after SCALE; the live DRY recounts]:

| | relocated | hang | ground (lying/standing) | glimmer to bulb | working (stay in can) | lights retired = cans removed |
|---|---|---|---|---|---|---|
| P01 | 47 | 27 | 20 (8/12) | 7 | 1 (300 lm) | 54 |
| P02 | 11 | 5 | 6 (4/2) | 2 | 12 (PRACTICAL_R, 800 lm) | 13 |
| P03 | 21 | 10 | 11 (8/3) | 4 | 0 | 25 |
| P04 | 15 | 3 | 12 (7/5) | 4 | 0 | 19 |
| P05 | 93 | 51 | 42 (25/17) | 14 | 0 | 107 |
| P06 | 25 | 11 | 14 (9/5) | 1 | 0 | 26 |

P06 counts come from a snapshot taken before today's relayout [inf].

**Rules**, all arguments in `fixtures_common.RELOCATE_DEFAULTS`. Coordinates are in the route-relative pair frame, so
P02's bend does not distort them (memory puss-structure-invariants).

- Lateral |y| is between 150 cm (the camera and cat lane stays clear) and 520 cm (inside the wings at about +-600 to
  700).
- **HANG**
  - x within +-25 cm of the bay's station, which is under its crossbeam (cpp:1265-1272).
  - Glass centre at 2.2 to 6.5 m.
  - A vertical cord from the bulb cap to the crossbeam underside (HeightCm - Depth/2 = 1060 cm with v3).
- **GROUND**
  - x from -260 to +220.
  - 60% lying on its side, 40% standing on its cap with the glass up, at a random yaw.
  - The lowest bound corner rests on the floor (harness D3). The floor height comes from the bounds of the floor
    actors under each spot, read live. Spots with no floor under them are listed, not guessed.
- **P04 (rain, wet slab)** is set to 35% hang, so more bulbs sit on the floor near the wet slab (your call).

**Previews** in `FixturesFollow/previews/`:

- `P0N_topdown.png`: bays unrolled at a nominal 600 cm pitch, positions inside each bay exact.
- `P0N_routecam.png`: a pinhole view from the lane at 60 cm, with mirror reflections, to give the idea.

Both are **schematic** [inf]. `fixtures_preview.py --from-dry` is meant to redraw from a live DRY.

### D2. Light linkage (proposal)

- **Working practicals** (paired light above 50 lm) **stay as they are**: lamp, can and bulb. These are 12 P02
  PRACTICAL_R at 800 lm and one P01 PRACTICAL_DEAD at 300 lm (13 of the 225 swapped bulbs). They light the scene, so moving them changes the look [meas, swap records].
- **Dead and dim bulbs (0 to 40 lm):**
  - **the bulb mesh moves;**
  - the paired light is **retired**: disabled for ground bulbs, or re-kinded into the bulb's cord for hang bulbs that
    have no spare `_CAP` row;
  - its can disappears, because only enabled LIGHT rows get one (cpp:162-166) [decl].
  - The glass keeps glowing at its authored level. All 225 bodies have `follow_light` False [meas], and a
    follow-light body whose light is gone falls back to authored x flicker (InfinityStagePassageActor.cpp:1976-2000)
    [decl].
- **Why not move the light with the bulb today:** a Station light anywhere gets a can, so a ground bulb would get a
  ParCan on the floor [decl]. The PairCentre anchor avoids the can, but it rides the panels, and a bulb on the floor
  would slide as wings move [inf: the panel travel is not measured]. Rejected.
- **Performance [inf]:**
  - The retired lights are unshadowed 0 to 40 lm points (plus the 32 glimmers at 160 lm); removing 244 of them only saves cost.
  - Emissive glass on a glossy floor shows in Lumen and screen-space reflections, but a small emissive is fainter than
    a real point light's specular highlight. That is the look question in D3 and decision 3.
- **Glimmer (Gary's request)**, for each `*PRACTICAL_GLIMMER_BODY`:
  - The SM_Lamp_Ceiling body becomes a bare Meshy bulb with its glass **on the glimmer light's spot**. The variant
    comes from a per-light sha256. The tint is one of the passage's own derived SM_FX bulbs.
  - The glimmer LIGHT row becomes its cord (`HANG_AT_SPOT`, the default), or is disabled (`GROUND_UNDER_SPOT`).
  - Any `*GLIMMER*_CAP` row is disabled. None exists in any snapshot [meas: searched every swap and scores record].
- **Scores re-apply:**
  - `scores_glimmer_config.py` (DRY run: `SCORES_VALIDATE_OK` on all six passages [meas]) removes the
    PRACTICAL_GLIMMER instrument from `local_looks.GAP`. GAP keeps its PRACTICAL_DEAD, as `PRACTICALS_EVERYWHERE`
    requires (lighting_scores_apply.py:385).
  - Note [decl]: a scores re-APPLY is refused while score rows exist (`SCORE_ALREADY_PRESENT`, :1799-1802). It
    therefore always follows a REVERT, which discards the Meshy swap and all of this. These tools must be re-run after
    any scores re-apply.

**Glimmer attachments to change** [meas, from snapshots at 7 Oct 08:2x; the live DRY lists the live GUIDs; full JSON
in `FixturesFollow/glimmer_attachments_snapshot.json`]. Every glimmer is at (-20, -700, 140) cm in its bay; P03 B10
was rotated by you at 23:08 UTC, which is not in the files. Each pair below is light GUID / body GUID:

- **P01**
  - B02 `07C6C4424357A9334CDFE89FE9705D69` / `5840444948F3C807A6FD6CB7516B2DA9`
  - B08 `A1D1D15D4FE4ADEE49A71191DAA38186` / `A58CCA914DBF34233156BBAA90E5E65D`
  - B17 `004FA2164F0E970C46A12FB3F3D4B71D` / `5CF2373946B9F1585CA8A7801664B103`
  - B24 `018DFE69422093E054846DAAA6F21FD2` / `B584D98349AC5E222577678134845257`
  - B31 `EA1ABA8046A3C41FB5806490FC35B9B8` / `84EFD359454695A0B54E36A3ACA13F15`
  - B38 `BB51E8BF4924A92DB6281B81CDB3868D` / `9A56F2AE46B0A51F957402A20AE5E4A7`
  - B44 `AF0A1D63449177E73B7A9982AA5B9E9C` / `72CDB22C4ECFCDE3B8FC258A27DB5456`
- **P02**
  - B06 (Wing 007) `733128CB425DBDE3F27E3BB05C86B3AA` / `134ED8724ADE571F5807B68F9BEFEDD4`
  - B22 `9E27B8A94E4D99DFD0D43CB56971C553` / `5344CE3A43C6DD6EE59C638FA7B8105E`
- **P03**
  - B03 (Wing 002) `6E9F9B4F4A4E7FFAFB109BA97C642534` / `BE9C86C34E06D294197D2087F1021FF8`
  - B10 `75CDEE9646C003F7E3EE1E810EAE107E` / `497F65BC4DFCA5D955CE3C8DBB12DABA`
  - B15 `F1D12EBE44A87821573C8AB64602A72D` / `F44C609E4B924E847E719199CDBC3B4B`
  - B19 `1424A2424A6168BAE40E529DFB1EF86D` / `54DE6B074A0D56B3D8859C9E4B6BFA36`
- **P04**
  - B07 `2A2D37C8452FE04B33C98A9463EAA62E` / `20A02DED4D6619568658659162C52AF6`
  - B10 `B6F15DD14A830F034CFA35B20072A7C3` / `129B0E8B451A5A1AA2852AA4B96FE926`
  - B13 `82E3236E4E77343370CFED9AD0A23EC1` / `EC9C1FF74446AF84EFE68E833F9E16F9`
  - B19 `E1BFC20D416E03A4C4659F89AF54CEB0` / `F38662E546C748C7546410BFADA250EA`
- **P05** (cue labels repeat, so these are keyed by GUID)
  - B19 `6CD4FBBC42E89020AC98A68956DC8F6F` / `20FB63AC478530A139168480E91307AE`
  - B26 `09A69EA84BC1E44366E177A3C57308C2` / `8D9046394B9BE25FE5B63C8A1CB157DA`
  - B33 `7735964C48134C19ADDD128FF5829D22` / `C90F13674DDF29E4DD1F0CA048B60985`
  - B40 `EA6324104B4C98047137E991ACF4AB90` / `94D14BAA42D4F72FBA545296FA1F89FF`
  - B47 `1793A1FA4125683F350DD29E3EAB24CA` / `2CA13D7240DC3581D6C492B6DE66899C`
  - B54 `67E16AEB4CCAEA680B075291B3DA1CE7` / `E5CCBE904F68CA94ADFC8C95D2E2D290`
  - B61 `46E57B8D4246269FA6ABA7A404708DBA` / `E2C59932443DF196D7331688B49A57E7`
  - B68 `6F9B68E14DA533A66658F5BBF74CE564` / `46E4145C48AF45C764BAA99C98AF5B4F`
  - B75 `6F00279846CACAEBB698869B8F602587` / `DCB100364ECA7BCFD0CE61B3F018AC15`
  - B82 `7ED51F264E03C26C014F8B9E5A3D6C1B` / `E5F1603B46E9C217708D449D57F496F5`
  - B86 `4D53106B47EB380AD9FD6BAB8C2138D4` / `FEA39CB94E88E216A9DC7598E1445896`
  - B88 `FAA008CB416419B940428C867B9AE5F9` / `8E3236924C00BD5ADAA832B52DBA6A2E`
  - B90 `3C77346E40F0C34D16023DBBCF597490` / `5681B89E4B6ECF8F1E9794A09A1F1AF0`
  - B92 `13B5B20341A5B936F40C3C9CADCCD22A` / `AFEBDADA4E62CD98035298BF1D266B7C`
- **P06**
  - B12 `0EFAA1244643A5F21EBDB19F6F34E2C7` / `6BB5E0744000700A4CEB399F9FAF822C`. This is from the scores snapshot on cue
    "P06 OLD 06 - gauze_lattice"; it may be gone after today's relayout [inf].

### D3. C++ that would make it better (held proposals; not written, not built)

1. **`bHousePointLights` (default true) on `FInfinityStageFixtureSettings`.**
   - When false, `GatherFixturePlacements` skips lights whose `Lighting.Type == Point`
     (InfinityStageTypes.h:199). That function also feeds the signature, so `IsStructureCurrent` stays consistent.
   - Then a bulb's 18 to 40 lm light can travel **with** its bulb (true specular reflections on the wet floor) and no
     can appears.
   - RELOCATE would gain `paired_light: MOVE_WITH_BULB`.
   - About 6 lines, plus a test mirroring StructureTests :355-373.
2. **`LensOffsetCm` (FVector, housing frame).**
   - `BodyCentre -= Rotation.RotateVector(LensOffsetCm)` at cpp:1952.
   - SCALE would set it from `lens_offset_local`, so each beam leaves the lens centre exactly.
3. **Per-role lantern** (Fresnel for TOP, ParCan for LOW_SIDE...). This needs a `TMap<role, mesh>`. It is a known open
   item from the swap.

## E. Harness

`python test_fixtures_follow.py` gives `FIXFOLLOW_HARNESS_OK|passed=46|failed=0` [meas]. Each check has a control
that must fail.

- **B: housing maths**
  - B1-B3: housing formula, including the vertical-throw `MakeFromXY` branch.
  - B4: placement filter.
  - B5: stale detection, with a not-stale control.
  - B6: count mismatch.
  - B7: mirror-safe compare.
  - B8: offline counts equal the live housing counts.
  - B9: the meshy_swap loader, with a side-effect refusal.
  - B10: args gates.
- **C: SCALE**
  - C1: glass-centre pivot (control: the pivot moves the glass).
  - C2-C3: 3.2 to 9.6, size x3, lens x3.
  - C4-C5: no double apply; an unexpected scale is refused.
  - C6-C7: girder OBB hit and miss.
- **D: RELOCATE**
  - D1: determinism and seed sensitivity.
  - D2: lane, lateral and cord invariants, with a lane-intrusion control.
  - D3: floor rest, with a wrong-rotation control.
  - D4: working practicals (control: threshold lifted).
  - D5: no glimmer light left in any passage (control: OFF).
  - D6: bulb on the glimmer spot.
  - D7: scope, with an extra-change control.
  - D8: revert, with a drift control.
  - D9: retired lights equal removed cans.
- **E: scores config**
  - E1: glimmer removed (control: the live file still has it).
  - E2: idempotent.

**Not covered offline [inf]:** the UE Python names marked inferred in `fixtures_follow.py`'s header, which are
`gather_stations` shape, `occurrence_offset`, `grid_half_width_cm`, `gridiron` fields, writing `kind` on an existing
row, `get_actor_bounds`. The first DRY exercises every read. The first APPLY's read-back exercises the `kind` write.
Every stop happens before a save.

## Run order (editor, one passage at a time; P01 first)

- **Before anything:** take the census, and make sure no other stream holds the Show. Tool calls go through
  `FixturesFollow/fixtures_follow_request.json` with `fixtures_follow_args.json`. APPLY needs `confirm` and the DRY's
  `plan_sha256` in `ack_records`, and foreign active records must be acknowledged (the Meshy swap records will be).

0. **Gary aims lights (A5) and saves the Show.** You can stop after step 1 if aiming is all you want today.
1. **FOLLOW DRY, then APPLY** for each passage Gary aimed: `{"op":"FOLLOW","mode":"DRY","passage":"P0N"}`. Expect
   `FIXFOLLOW_FOLLOW_DRY_OK|...stale=N`, then `..._APPLY_OK` (or `_NOOP`).
2. **SCALE DRY, then APPLY**, once Gary has confirmed x3 (decision 1). Read `girder_hits_before/after`. After APPLY,
   read `lines=a->b`.
3. **Gary looks at a still or PIE of one passage at 3x** before any RELOCATE.
4. **Config:** `python scores_glimmer_config.py`, then `... APPLY`. This is offline, a file edit with a backup.
5. **RELOCATE DRY.** Run `fixtures_preview.py` and Gary approves or adjusts (`hang_fraction`, lane, z range, seed).
   Then RELOCATE APPLY.
6. After each APPLY, run both tests: SavedMasterMatchesShow and the scene-cut test.
7. **Undo:** REVERT RELOCATE first, then SCALE (the tools enforce this order).

## Gary's decisions

1. **Size.** "x3" from now makes the bulbs 9.6x real (A60 about 1.06 m, G95 1.3 m) and the cans 1.5 m tall.
   Recommendation: confirm on one passage first (run order step 3). The factor is an argument.
2. **Hang vs ground split:** 50% everywhere, 35% hang in P04. Also confirm that ground bulbs stay out of the 1.5 m
   camera lane.
3. **Light on relocated bulbs:** emissive-only now (recommended for today), or a small point light that travels with
   the bulb (needs C++ patch 1 and a build).
4. **Glimmer spots:** hang the bare bulb at the spot from a cord (default), or lay it on the floor under the spot.
5. **The 13 working practicals** (P02 PRACTICAL_R x12, one P01) stay in their cans: OK?
6. **Lens-exact cans** (C++ patch 2) and per-role lanterns (patch 3): worth a build?

## Searched and found nothing

- No per-light housing opt-out or lens offset in `FInfinityStageFixtureSettings` (h:396-416).
- No attachment-GUID minting in `EnsureStableIds` (ShowAsset.cpp:91-124). That is why RELOCATE re-uses rows (body,
  cap, retired light) instead of adding cords.
- No `GLIMMER_CAP` row in any snapshot.
- No 6 Oct editor log in `Saved/Logs`.
- No station distances in any Saved record, which is why the previews use a nominal pitch.
- No Structure reference in `InfinityStagePassageActor.cpp`.
