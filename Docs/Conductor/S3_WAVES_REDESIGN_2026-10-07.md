# S3 waves redesign: layered theatrical sea (7 Oct 2026, offline)

**Gary's brief, 7 Oct.** The sawtooth reads as crude. He wants three things, front to back:
- "wave-pattern shaped" waves in front;
- a staggered rolling ocean surface behind them;
- foam waves at the back.

The look should be moody and cool, after the Whistler backdrop, but keep its contrast. He also wants better art, motion, and lighting with depth.

**Scope.** Everything here was done offline: no Unreal, no commits, no downloads, no Blender MCP. One headless Blender 4.4 run at a time, started only after another agent's shore build had exited. Gary's windowed Blender was not touched.

**Tiers, per claim:**
- **[decl]** declaration-proven: read from a record, script, header or config.
- **[meas]** measured: run here and read back.
- **[meas-old]** an earlier live probe, not re-read today.
- **[inf]** inferred, with the reason given.
- **UNCLEAR** means the item was searched and not settled.

---

## 0. Look first: previews

All previews are in `DerivedAssets/FlatV3/Scene3/waves_v3/previews/`.

| File | What |
|---|---|
| `BOARD_persp_A_vs_B.png` | **Start here.** Both variants from four S3 shot poses, inside the box, over the built backdrop skin and today's shore mesh |
| `persp_{A,B}_{B09_axis,B02_wide,B05_tele,B04_main}.png` | 1600x900 Cycles renders (64 spp) behind the board |
| `contact_{A,B}_silhouettes.png` | Each layer front-on and true-scale, painted card plus a pure black cut line, with 1 m ticks |
| `contact_{A,B}_frontal_stack.png` | All six layers overlaid in an orthographic front view over the bottom 6 m of the backdrop skin |

**The two variants:**
- **A, "woodblock / low sea".** Front breakers have Hokusai-style claw crests. Slate-indigo troughs, paper-white foam, Hollar-hatch grain. The back crest line stays at the sightline to the mural figures' feet.
  - Lit with a cool key, ground rows and haze.
- **B, "scroll / raked sea".** Front breakers have rolled Baroque-scroll crests, in Whistler grey-green with Bakhuysen brush grain. The rake is steeper, up to about 2.5 m at the back, so the surf masks the mural's foreground.
  - Lit with a nocturne key plus the **warm side-light option**.

**Not judged** [inf]:
- Gary has not seen either variant.
- These previews are not Unreal renders: there is no billboard skin, halftone, peel, TSR or Lumen.
- The cast and props are not in the scene.

---

## 1. Design: six layers in three bands

### Placement: inside the existing floor notches

The shore re-sculpt notches the floor flat under each wave row.
- **[decl]** It takes the row positions from `s3_shore_footprint.json` `wave_rows`: Row1 3649..3735, Row2 4449..4535, Row3 5249..5332 (local cm).
- **[decl]** The flat half-width is `max(45, half+10)` (`s3_shore_field.py:281-283`, notches `:271-278`, repose walls `:316-320`).
- **[inf]** So the flat bands are about x 3639..3745, 4439..4545 and 5239..5342.

**Every layer below fits inside a band**, so the shore needs **no** re-sculpt:
- **[inf]** each layer is two pieces 15 cm apart in x, and each piece's frame is at most 12 cm deep;
- **[inf]** the deepest point is therefore layer x + 27, at most 3722, 4522 and 5322.

A fourth band near x 5750 would need a new `wave_rows` entry from the shore stream, so it was not proposed.

### Layers

Each layer is 22 m long: the 20 m hangar plus 1 m of overhang at each side. All heights are above the floor top, which is local z 115.

| Layer | x | Kind | A: max height / trough (cm) | B: max height / trough (cm) |
|---|---:|---|---:|---:|
| L1 Breakers | 3650 | "wave-pattern" crest: long back slope, steep face, lip curling forward over an open mouth (claws in A, rolled scroll in B) | 112 / 40 | 114 / 40 |
| L2 SwellNear | 3695 | rolling swell (two trochoids + envelope), small forward-curling whitecaps | 119 / 76 | 132 / 80 |
| L3 SwellMid | 4450 | swell, phase-shifted | 136 / 94 | 156 / 105 |
| L4 SwellFar | 4495 | swell, longer period | 144 / 106 | 167 / 122 |
| L5 Rollers | 5250 | small breakers curling the other way | 180 / 126 | 226 / 152 |
| L6 Foam | 5295 | swell base + froth band, spray fingers, lace holes (attached; no loose droplets) | 200 / 142 | 248 / 180 |

**[meas]** Max heights are from `design_{A,B}.json` `layers[].max_height_cm`.

### Why the front is low (the key finding)

**[meas]** I computed elevation angles from the shot eyes in `s3_shore_footprint.json`.
- **[decl]** Those eyes sit only 110–175 cm above the floor top and 6–15 m from band 1.
- **[meas]** In my first draft the front breaker crest was 1.78 m. From B04 it stood at +4.7° while every row behind it stood at about +2.2°, so it hid the whole sea behind it.

**The rule this gives:** the front crests stay at about eye height, 1.1–1.25 m. Each layer behind must then clear the sightline over the layer in front, from **every** shot.

**[meas]** `design_*.json` `sightlines` records the clearance for B04, B05, B06, B07, B09 and B11.
- All clearances are positive.
- Smallest: 0.20° (A, L4 from B09) and 0.11° (B, L3 from B11).

**[inf]** This also explains the old plan. The old 1.2 / 1.8 / 2.6 m steps had the right instinct; what failed was the art.

### Trade-off for Gary: the mural figures

**[meas]** The feet of the huddled figures sit about 2.2 m up the backdrop. That reading is from `contact_*_frontal_stack.png`; **[inf]** treat it as ±20 cm.

From B04, those feet are at +1.82°.
- **A** keeps the back foam at that line, so the figures stand clear and the sea is compressed into thin stacked bands.
- **B** gives a deeper, readable rake, but its foam covers the figures' feet and the beach foreground from low cameras.

### Shot B04

**[meas]** The brief's "main" pose (S3 Shot B04, yaw 75.5°) looks mostly at the **right wall**. In `persp_*_B04_main.png` the waves fill only about the left third of the frame, and a dune fills the rest.

The layered reading is judged better from B09, B02 and B05.

---

## 2. Art

### Palette

**[meas]** Anchors were sampled from the built backdrop SkinColor (`design_*.json` `palette_anchors_measured`):

| Anchor | RGB |
|---|---|
| paper | (224, 216, 205) |
| horizon sea | (187, 182, 165) |
| sand | (198, 186, 162) |
| figure shadow | (132, 123, 111) |
| coolest sky pixel | (198, 197, 194) |

**[meas]** The coolest 0.1% of the sky is still B−R ≈ −4, so **the skin contains no blue**.

**[decl] Design choice.** The sea's lightness ladder comes from these anchors, but its hue is chosen:
- A: slate, 208°;
- B: grey-green, 176°.

**Foam is the measured paper white**, so the sea's lights belong to the mural. The formulas are in `derive_palette()`.

### Contrast

The painting provides contrast in four ways:
- dark troughs against light crest glow;
- a thin painted light rim on every up-facing edge, so each crest reads against the dark row behind it;
- white foam with a cool shadow line beneath it;
- aerial perspective, which lightens layers by up to 18% toward the back.

### Painting method

**[decl]** The painting is painterly and fully seeded. `s3_waves_v3_design.py` `paint()` uses a distance field with brush strokes that follow it:
- broken iso-lines: woodblock flow lines in A, faint scumble in B;
- high-pass grain from on-disk public-domain / CC0 sources:
  - Hollar, *Warship in the Trough of a Wave*, Met 361510;
  - Bakhuysen, *Rough Sea*, Rijks 200108177;
  - both use fixed sea-only crop boxes (no ships or figures), and a median filter removes 1 px scan seams in the Rijks file.

Hokusai's *Under the Wave off Kanagawa* (Rijks 200134564, PDM) is on D: and is the silhouette reference for A. **[decl]** Its pixels are **not** used.

### Determinism

**[meas]** Two full runs gave byte-identical mask, art and RGBA hashes for 12 of 12 layers, at production resolution (4096 px per 12.5 m). Every random draw is one draw per statement (memory note *puss-random-draw-order*).

### Cuttable line

**[meas]** `cut_gates` checks every layer:
- one connected board per layer;
- open and close at 3 cm;
- sub-3 cm holes filled (none found);
- a solid 20 cm skirt below the floor top.

### Art risk

**[meas]** In the B05 85 mm view, the claws and curls read soft. **[inf]** The production skin adds halftone and paper grain, but the foam mass may still need more stroke detail before it is a hero close-up.

---

## 3. Motion plan (spec only)

Machine-readable: `Saved/CodexConductor/S3Waves/s3_waves_v3_motion_plan.json`.

### Mechanism

**[decl]** Use the existing pattern: baked Transform keys on actor bindings in `LS_DevScene_03`.
- Linear keys every 3 frames, gated to the +10 s uplight strike: `s3_wave_split_apply.py:26-36` (constants), `:84-89` (phase function), `:432-449` (`_add_track`).
- **[meas-old]** The split pieces carry 2,002 keys each on frames 239–6240 (`s3_wave_split_record.json` `created[].track_readback`).

**[decl]** Wing mechanisms cannot be used: they freeze outside their Passage (`InfinityStagePassageActor.cpp:1313-1318`), and the kinds are only Slide, Topple, Turn and Trap (`InfinityStageTypes.h:579-588`).

### Per layer

- **Sway in Y.** Periods are 7.5 / 10 / 15 / 10 / 15 / 6 s and amplitudes 45 / 70 / 85 / 95 / 110 / 35 cm, alternating direction, with staggered phases.
  - **Every period divides the 30 s vamp** (VAMP_RANGE 3480..4200, `:36`), so the loop seam is identical at both ends.
- **Bob, downward only.** 4–10 cm, two dips per sway, so a layer "rolls" at each turnaround. The 20 cm skirt never opens a gap.
- **Rock.** Roll ±0.25–0.35°, lagging the sway by a quarter period, about the **layer** centre. Each piece gets `dZ = u_centre·sin(roll)`, so P1 and P2 never split.
- P1 and P2 of a layer always get identical offsets.

### Foam flicker

Foam crest flicker uses the **Flap slot**:
- **[decl]** `MI_Billboard_Flap` has flutter WPO from VC.R, with MaxWPODisplacement 6 cm (`Docs/WingMateriality.md:80-82`);
- **[decl]** `build_v3_flat.py` ingests any `--flaps` JSON with `outline_uv_bottom_left` and weights by axis (`create_flaps`, `:1543-1580`).

**Proposal:** author a foam-flaps JSON (claw and froth outlines) for L1 and L6 instead of the skin's peel flaps.
- **[inf]** `build_skin` enforces 3–6 flaps only on its own output (`build_skin.py:684-685`); no count limit was seen in `create_flaps`. Untested.

### Limits

- **[decl]** The split tool caps side overhang at 200 cm (`:44`).
- L5's 100 cm strip overhang plus 110 cm sway gives 210 cm. Either clamp L5's sway to 100 cm or re-agree the cap.
- **[inf]** "The camera is the cat" does **not** constrain any of this: Scenes are exempt (memory note, Gary 2 Oct).

---

## 4. Lighting and depth plan

### What already exists

- **[decl]** `S3 Daylight Rake Key`: local (1500,−780,2200) → (4500,820,700), 1800 cd, 5800 K, shadows on.
- **[decl]** `S3 Daylight Cool Fill`: 450 cd, 6800 K (`s3_daylight_apply.py:47-54`); the record says `applied: true`.
- **[meas-old]** Strike Key/Fill/Cyc, Uplights 1–3 and Practicals L/R 1–7 (`hangar_light_keys_probe.json`).

### Proposals

These are tested only in the Blender previews **[meas, preview only]**; in Unreal they are **[inf]**.

1. **Cool key.** Retint the rake key toward about 7000–8000 K and drop it about 30%, keeping the rake from front-left so the curl tops and claws catch the light.
2. **Ground rows.** These are the classic separation. Put a hidden linear Rect light on the floor in each notch, about 8 cm up, just behind layers L1–L5, aimed up and back at the next layer.
   - Cool, low intensity, **shadows off**.
   - **[inf]** These lights are hidden: a layer's troughs are high enough to block the floor strip from every shot.
   - **[meas]** The previews show a lit lower body on each layer against the dark top of the layer in front. That is the "rim" a flat card can actually get; a true back-light hits only the backs.
3. **Haze between rows.** Use a low-density volume over the sea band. In Unreal this would be Local Fog Volumes or volumetric height fog.
   - **UNCLEAR:** whether S3 has a height fog actor. None was found in the light probes searched.
   - Combined with the painted aerial step, it pushes the back rows away.
4. **Warm-contrast option (variant B previews).** A low warm side light, about 3200 K, from the left wall at about 2.5 m, grazing the crests: warm crest tops over cool troughs.
   - **[meas]** It warms L1's face strongly. If Gary likes it, keep it subtle, or gobo it to the crests.

---

## 5. Build plan: Flat V3, new names

### Driver

`Saved/CodexConductor/S3Waves/s3_waves_v3_build.py --variant <A|B>`.
- **[meas]** Plan mode wrote `build_plan_{A,B}.json`: 12 pieces each, with cut points, sizes, mount positions and the exact commands.
- `--run` crops the pieces and runs:
  1. `build_skin.py` (4096x1024 SkinColor; 1% bottom-heavy peel);
  2. `build_v3_flat.py --mount wave-row --side L --deterministic-triangulation --triangulate-export` (four slots Front/Flap/Timber/Edge; LOD1 = board only via the FBX `LodGroup`, `build_v3_flat.py:1863-1869`, `:2175-2176`);
  3. `--validate-fbx --kind wave --minimum-width-m 12`.
- **[decl]** This is the same chain as the old waves (`waves/build_wave_assets.py`).
- **Not run:** waiting for Gary's pick.

### Pieces

- Each layer becomes P1, from u −1100 to cut+150, and P2, from cut−150 to +1100.
- The cut sits in a trough near the centre, so the overlap is about 3 m with identical art.
- P2 mounts 15 cm behind P1.
- Mount at local z **95** (the skirt bottom is the origin), rotation 0, scale 1, front facing −X.
- **[meas]** Widths are 12.1–13.7 m, so texel density is 3.0–3.4 px/cm.

### Names

All names are new and searched; none exist yet.
- **[meas]** `Content/Scenes/Wings/FlatV3/Scene3` has no `WaveV3` asset.
- Meshes: `SM_FlatV3_S3_WaveV3_<L1Breakers…L6Foam>_<P1|P2>`.
- Destination: `/Game/Scenes/Wings/FlatV3/Scene3/WavesV3/`, with textures and MIs (`_Front`, `_Flap`, `_Timber`, `_Edge`) under it.
- **No in-place reimport.**
- Timber and Edge use the CanvasEdge placeholder until the V3 Timber master exists (`waves/IMPORT_PLAN.md`).

### Unreal steps (for a later editor slot; plan only)

1. Fresh import with options set: no materials, no textures, LodGroup. Then gate:
   - `get_num_lods()==2`;
   - no stray assets;
   - the UV sign gates (memory note *ue58-fbx-import-traps*).
2. **Spawn new tool-owned actors.**
   - Tag them `S3.WavesV3.ToolOwned`.
   - Attach them to `S3 Hangar Root` with RELATIVE transforms, Movable.
   - Call `modify()` before any setter.
   - Do **not** reuse the split pieces' mesh slots.
3. Hide the nine `S3 Wave Split` pieces; do not delete them. The six originals stay hidden.
4. Key the new bindings per `s3_waves_v3_motion_plan.json`.
5. Save only the level and `LS_DevScene_03`, and read back.
6. Revert: delete the new actors and bindings, then unhide the split pieces.

### Current live state

- **[meas-old, probe 6 Oct]** The nine split pieces are back on the beach (`hp_probe_walls_result.json`; world x 15071–15083 ≈ local 3649–3661).
- **[decl]** Backup `Backups/PreS3WaveReattach-S3WR-20261005-102840` exists.
- **UNCLEAR:** whether the reattach APPLY marker is in the logs. It was not found in the current `Saved/Logs`, which are rotated.

---

## 6. Why the 2 Oct `_v2` swap "never dirtied the level"

**Verdict: all three runs executed the same, original mesh-set code. The two fixes were never run.**

**Run −01 was a genuine failure.**
- **[decl]** At commit 3dd7474, `set_component_mesh` called `set_static_mesh` with no `modify()` (`offline_harness/originals/w2_common_preModify.py:194`).
- **[decl]** The memory note *ue58-fbx-import-traps* already records that setters without `modify()` never dirty the level.
- **[meas]** Run −01's report shows the clean census `{"content":[],"maps":[]}`.

**Runs −02 and −03 ran a stale cached module.**
- **[meas]** Both failure tracebacks report `w2_common.py` **line 261** in `assert_level_only_dirty` and **line 269** in `save_current_level` (`swapkit/w2_apply_FV3W2-20261002-0{2,3}_FAILURE.json`).
- **[meas]** Those line numbers are the 3dd7474 layout exactly: `def assert_level_only_dirty` at 257 with its raise at 261, and `def save_current_level` at 268 with its call at 269 (`git show 3dd7474:…/w2_common.py`).
- **[meas]** The fixed files on disk at those times had different layouts:
  - 263367e: the defs at 263 and 274;
  - d1b03f5: the defs at 267 and 278.
- **[meas]** The traceback *text* shows those newer files' lines (`json.dumps(...)`, `package = ls_package(config)`). Python prints the current disk line for a stale code object's line number.
- **So:** the editor ran 3dd7474's `set_static_mesh` code from a cached `w2_common` module all three times. The "3 methods" in `FlatV3Status.md:229` were one method three times.

**Why the fixes were not loaded.**
- **[decl]** The purge-the-cached-modules fix was committed *after* run −03: 22dd2d7 at 18:17, against run −03 at 17:50.
- **[decl]** The memory note *ue58-python-stale-module-cache* describes the same mechanism.

**This was not the split-actor path.**
- **[decl]** The split tool ran on 4 Oct, after these runs.
- **[decl]** W2 targeted the six `S3 Wave Row` actors (`w2_preflight_FV3W2-20261002-03.json`).
- **[inf]** Those six are now hidden sources, so a fresh `_v2` swap on them would be invisible anyway.

**Consequences:**
- Neither `modify()+set_static_mesh` nor `set_editor_property("static_mesh")` has ever been tested live.
- The `_v2` meshes remain imported and unreferenced.
- Any future apply should log the sha256 of each helper module it actually imported (`module.__file__`) and assert it matches the file on disk.

---

## Files

All under `E:\PussStage\`.

**Saved/CodexConductor/S3Waves/**
- `s3_waves_v3_design.py` (the generator)
- `s3_waves_v3_contact.py`
- `s3_waves_v3_preview_blender.py`
- `s3_waves_v3_board.py`
- `s3_waves_v3_build.py`
- `build_plan_{A,B}.json`
- `s3_waves_v3_motion_plan.json`

**DerivedAssets/FlatV3/Scene3/waves_v3/**
- `{A,B}/` holds `L*_{mask,art,rgba}.png` (7209 px wide, production resolution) and `design_{A,B}.json`
- `previews/`

**Open questions for Gary:**
1. A or B, or A's crests with B's rake?
2. Should the back surf mask the mural figures' feet?
3. Keep the warm side light?
4. Approve the foam-flap flicker?
