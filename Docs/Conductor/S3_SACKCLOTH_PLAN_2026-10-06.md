# S3 sackcloth: heavy hessian over the shore figures, a rag pile, sand piles

**Written:** 6 Oct 2026. Investigation and offline prep only. Unreal was not run, MCP was not called, nothing was
committed, and no Content was touched.
**For:** Gary (6 Oct), Scene 3:
- "a larger piece of sackcloth that is heavy and covers their whole body";
- "we just see mostly their legs and arms underneath";
- "heft, similar to the entry curtain";
- "about 1.2 by 1.2 m";
- "rough sacks you might transport coffee beans in";
- a "pile of dry rags ... on top of some sandy ground".

**Tiers, used on every claim (AGENTS.md):**
- **[decl]**: read in a file, script or record (cited `file:line` or by key);
- **[meas]**: run and read back today (dated);
- **[rec]**: measured by an earlier session, as its record states (not re-run);
- **[inf]**: inferred, with the reason.

---

## 0. Short version

- **The current cloth** [decl/rec]:
  - It is a **Chaos Cloth Asset** (the UE 5.3+ Panel Cloth / Dataflow kind), `CA_ShoreHeadDrape`.
  - It is played by a **`ChaosClothComponent`** that is attached to the MetaHuman Body's `head` socket inside
    six scoped Blueprint copies, `BP_Shore0N_*_Draped`.
  - It simulates live, every frame.
  - It is a 100 cm source plane scaled by 1.641315, so **it is already ~1.64 m square: larger than Gary's 1.2 m**.
  - Its material is a flat constant linen colour.
- **The figures animate** [rec]: six MetaHumans sway through selected sections of their own mocap at 0.6×. They are
  not a held cower. An agitation layer is still planned.
- **1.2 × 1.2 m will not cover the underpants of a standing figure** [inf, arithmetic + meas on a crude proxy]:
  - Centred on the crown, its hem lands at chest height.
  - Hip coverage on the four upright figures needs **≈1.8 m**, or a front-back-long rectangle.
  - This is Gary's first call (§6).
- **Recommended route: D, "drape then skin"** (§3), not a live free sheet and not a per-figure Alembic:
  1. Blender drapes a thick, frayed, heavy hessian sheet over each figure in its own pose.
  2. The result is skinned to the MetaHuman skeleton and rides the body as a leader-posed skeletal mesh.
  - It is deterministic, scrub-safe and nearly free at runtime.
  - Retiring the six live drapes **removes a measured 4–10 ms × 6 of cloth end-tick** [rec].
  - Optional upgrade: Chaos secondary motion on the hem only.
- **Material:** Poly Haven **`hessian_230`** (CC0, coarse burlap, 0.269 m tile, with a Mask map) [meas: API metadata,
  6 Oct]. Nothing hessian-like exists in Content [meas: name search]. It goes on the Fab `M_MS_Fabric` master, or
  on a new Cloth-model master per the curtain plan.
- **Rag pile and sand:**
  - one Blender pile, a single static mesh, on the existing Megascans sand;
  - the beach-v2 sand floor already exists and is applied [rec].
- **Written today:**
  - this plan;
  - `Tools/S3Sackcloth/build_sackcloth.py`, with a `--dry-run` and drape/pile modes, smoke-tested in Blender 4.4 (§7).

---

## 1. The current set-up

### 1.1 Assets

| What | Path | Tier |
|---|---|---|
| Six MetaHumans | `/Game/Metahuman/ShoreCast_20260910/Characters/MHC_Shore0{1..6}_*`; assembled `Assembled/Shore0N_*/MHC_Shore0N_*/BP_MHC_Shore0N_*` (Body, Face, Outfits, PHYS) | decl (folder listing) |
| Scene copies with the cloth | `/Game/Metahuman/ShoreCast_20260910/SceneCharacters/BP_Shore0{1..6}_*_Draped` | decl (`Saved/CodexMocap/shore_draped_cast_components.json`) |
| Cloth component | `ShoreHeadCloth`, a `ChaosClothComponent`, child of `Body`, socket `head`, `use_attached_parent_as_pose_component=False`, relative scale 1.641315 | decl (`Saved/CodexMocap/create_shore_drape_pilot.py:23-36`; `shore_drape_pilot.json`) |
| Cloth asset | `Cloth/CA_ShoreHeadDrape` (five figures) and `Cloth/CA_ShoreHeadDrape_Bowed` (Shore02, gravity-aligned and anchored at the head-capsule centre). Both are duplicates of the mannequin prototype `/Game/Scenes/CA__OrtolanSheets` | decl (`create_pinned_shore_drape.py:22`; `shore_bowed_drape.json`; `shore_clam_integration.json`) |
| Source mesh | `/Game/Scenes/SM_OrtalanSheet`: 441 vertices (21 × 21, 5 cm grid), box extent 50 × 50 × 0 cm | decl (`create_pinned_shore_drape.py:10`; `drape_source_mesh_api.json:2`; `shore_pinned_drape.json` `source_vertices`) |
| Size in the scene | 100 cm × 1.641315 ≈ **1.64 m square**, simulated at 5 cm × 1.64 ≈ **8.2 cm edges**, with zero thickness | inf (component scale applies to the cloth: the bowed record's `rest_crown_above_skull_center_cm` 16.41315 = 10 × 1.641315) |
| Attachment | A spatial crown disc: Max Distance 0 inside 3 cm, falling off to 14 cm, free beyond (max distance 140 cm). Numbered pins are SUPERSEDED ("canopy") | decl (`shore_spatial_crown_attachment.json`; `shore_pinned_drape.json` `status`) |
| Collision | A per-figure `Cloth/PHYS_Shore0N_*_Drape`: the body PHYS with head +3 cm and clavicle/upper-arm +2.5 cm | decl (`Docs/ShoreCast-20260910.md:5,90`) |
| Material | `Cloth/M_ShoreLinen`: Default Lit, two-sided, **constant** base 0.58/0.55/0.48, roughness 0.94, no maps. This is the "basic plain sheet" | decl (`create_pinned_shore_drape.py:37-46`) |
| Grooms | Hidden in the draped copies (the cloth covers the hair) | decl (`shore_pinned_drape.json` `grooms_hidden_in_draped_copies`) |

### 1.2 What the figures do

**Six figures** [decl: `shore_cast_brief.json`]:

| Figure | Height |
|---|---|
| Shore01_M56 | 179 cm |
| Shore02_F52 | 166 cm |
| Shore03_M59 | 173 cm |
| Shore04_F55 | 160 cm |
| Shore05_M53 | 184 cm |
| Shore06_F25 | 169 cm |

**They animate** [decl: `Docs/ShoreCast-20260910.md:3`; `shore_gentle_motion_selection.json`]:
- Each plays an 18 s source section of its own fitted take at **0.60×**.
- The sections sit in `LS_Clams`, which runs at 30 fps.
- Routing: `DA_InfinityStage_V1Show` → `LS_DevScene_03` → `LS_Clams` (`ShoreCast-20260910.md:9`).
- `s3_beats_record.json` shows a nested `Body` SkeletalAnimation section of range 0–14852 [decl]. Whether it loops
  over the whole scene is **not checked** [inf: units/rate unread].

**Posture** [decl: `shore_gentle_motion_selection.json`, `head_height_range_cm` over the selected sections]:

| Figure | Head-bone height | Posture |
|---|---|---|
| Shore01 | 159–162 cm | standing |
| Shore02 | **90–102 cm** | deeply bowed / crouched, already a cower |
| Shore03 | 146–155 cm | |
| Shore04 | 141–144 cm | |
| Shore05 | 144–163 cm | |
| Shore06 | 151–154 cm | |

- **Head sway:** over the full takes the head bone moves −32…+37 cm in x for Shore01 [decl, same file]. The selected
  sections were chosen for low motion energy, so they move less [inf].
- **Still planned:** an agitation ramp and a return to the start pose ("animation work, owner TBD") [decl:
  `Docs/Scene3BeatSheet_2026-10-01.md:38`].

### 1.3 Where they stand now

- **Diorama move:** applied 1 Oct [rec: `Saved/CodexConductor/s3_diorama_move_record.json`; spec
  `specs/S3_DIORAMA_MOVE.md`].
- **Beach v2:** applied 4 Oct [rec: `s3_beach_place_record.json` `applied: true`, backup `PreS3BeachV2-20261004-1242`]:
  - the sand floor `SM_S3_BeachV2_SandFloor`;
  - five Megascans rocks and three seaweeds;
  - the six figures raised 35–44 cm onto the sand.
- **Figure dock positions** (S3 dock frame, cm) [decl: same record `figures[].dock_xy`]:

  | Figure | x | y |
  |---|---|---|
  | Shore01 | 3649 | −213 |
  | Shore02 | 3199 | 109 |
  | Shore03 | 3391 | 301 |
  | Shore04 | 3684 | 262 |
  | Shore05 | 3411 | −244 |
  | Shore06 | 3760 | 0 |

- **Draft shot cameras** [decl: `s3_shotlist_record.json` `plan.shots`, tag `S3.ShotDraft`]:
  - Several cameras sit close to the figures: B04 at 35 mm focused 5.5 m on Shore01, and B08 at 50 mm focused 1.4 m
    from inside the ring.
  - **The cloth will be seen close.** It must hold up at about 1.5 m, not only at the 14 m stalls distance.

### 1.4 What the live drapes cost

- **Overall:** "the six Shore drapes ... 13.4 ms of a 23.6 ms PIE frame, a stall in
  `FChaosClothComponentEndTickFunction`, every frame" [rec: `Docs/ChaosClothCurtain.md:705-707`].
- **Suspending all six** cut the end-tick from 4–10 ms × 6 to under 1 ms. The mean frame went from 30.2 to 24.3 ms
  [rec: `ChaosClothCurtain.md:605-608`].
- **The gate was never applied:**
  - `Saved/CodexSoftGoods/cloth_gate_apply.py` exists, but no `Backups/PreClothGate-*` exists [meas: ls, 6 Oct].
  - The last status (29 Sep) shows all six enabled and not suspended [decl: `cloth_gate_status.json`].
- **Consequence:** the drapes cost frame time everywhere in the show, not only in S3 [inf: they tick whenever the
  level is loaded].

### 1.5 Searched, with nothing found

Content folder and file names were searched for: Burlap, Jute, Sack, Hessian, Fabric, Cloth, Rag, Linen, Canvas, Sand
[meas, 6 Oct]. Results:
- **No sack or hessian textures anywhere.**
- `Content/Fab/Materials/Standard/M_MS_Fabric(_Masked)`: a Fab/Megascans fabric master with the `QMF_FabricFuzz`
  function, but **no fabric surfaces downloaded**.
- MetaHuman default-garment textures (e.g. `macro_linen_rbess3s_4K`).
- Sand:
  - Megascans `01_Soil_Sand_pjuuz0` (2K) and `02_` (4K);
  - OceanFloor `T_SandDunes_*` and `T_SandDetail_*`;
  - Forest pack `MI_ground_Sand_*`.
- `DerivedAssets/TextureLibrary` holds one fabric, `Fabric081B` (ambientCG, a dirty plastisol tarp). It is not
  hessian.

No body FBX/Alembic export of the shore cast exists on disk [meas: find for `shoreguy*`/`Shore0*` outside Content; only
autosaves, backups and JSON]. Every Blender route therefore starts with an export from UE (§5 step 2).

---

## 2. Material

### 2.1 Source

**Primary: Poly Haven `hessian_230`** [meas: `api.polyhaven.com/info/hessian_230`, 6 Oct, metadata only, nothing
downloaded]:
- CC0, tags burlap/sack/hessian/jute/coarse/sackcloth;
- 268.75 × 267.2 mm real-world tile;
- maps include Diffuse, nor_dx, Rough, AO, Displacement, **Mask** and anisotropy (`/files/hessian_230`).

**Alternatives:**
- **`hessian_380`** is the "fine" grade: more of a coffee-sack inner layer.
- **ambientCG** has no hessian [meas]: searches for burlap/jute/hessian/sack/sackcloth returned 0. Its "rough"
  fabrics (Fabric061–066) are unvetted.
- **The Blender MCP's Poly Haven tools** could not be checked: "Could not connect to Blender" [meas]. The public API
  carries the same catalogue.

**Download route:** add `hessian_230` and `hessian_380` to `DerivedAssets/TextureLibrary/download_cc0_library.py`
(the Flat V3 library tool), as a new family `Sackcloth` [inf: same pattern; it keeps publisher files byte-for-byte and
records the sha256]. Use 2K for the sheet (the tile is 27 cm) and 4K only if B08-distance stills show softness.

### 2.2 Recipe (UE 5.8): a new master `M_Sackcloth`, create-only

Build it with the guard scaffolding of `velvet_v2_build.py` (`Docs/CurtainFabricPlan_2026-10-06.md` §1).

- **Shading model:** **Default Lit**, not Cloth.
  - Hessian is matte and hairy-dull; it is not a pile fabric. Cloth's fuzz lobe gives the velvet "bright rim, dark
    core" [decl: `CurtainFabricPlan` §2.1], which reads as plush [inf].
  - Add a weak **sheen-like rim** instead: Fresnel (exp 4) × 0.08 lifting the base toward a pale straw colour. That
    gives loose-fibre glint at grazing light.
  - Two-sided is **not** needed: the mesh has real back faces and a rim from solidify.
- **UV0 is in metres** (written by the tool), so the weave tiles at `TileM` 0.269 and stays continuous through the folds.
- **Maps:** the scan's Diffuse, NormalDX (strength 1.0, coarse weave at 1.5 m), Roughness (~0.9 overall) and AO
  into AO.
- **Height / parallax:** skip parallax (cost; it breaks on folded cloth) [inf]. The displacement map feeds only a
  slight normal boost.
  - Real relief comes from the geometry: folds plus the 6–8 mm solidify.
  - Optionally, Nanite tessellation displacement of 1–2 mm on the front slot only if a close still demands it (needs
    the Nanite displacement project setting; **not checked** in `DefaultEngine.ini`).
- **Weave gaps (opacity):** no on the main field.
  - At 1.4 m, light through the weave would show the body as a dotted silhouette. That could be lovely but costs
    masked overdraw [inf]. Leave it as a bench variant using the scan's Mask.
- **Colour variation:**
  - a 0.4–0.8 m low-frequency mottle on value and hue (±8%; procedural, as `VV2_Crush`);
  - a per-figure tint from UV1.y (random per piece, 0..1): a lerp between "new jute" (linear ~0.42/0.30/0.17) and
    "old grey sack" (~0.30/0.27/0.22).
- **Dirt and stains:**
  - a world-Z gradient darkening near the ground (wet sand and grime on the hem) using **UV1.x** (distance to the
    torn edge) and a world-position mask (below 0.4 m);
  - one or two blotchy "coffee/oil" stains from a tiling grunge texture;
  - a stencil print (e.g. a faded "CAFÉ" bale stamp) is a possible flourish; it is a look call.
- **Frayed edges:**
  - a **masked** variant `M_Sackcloth_Masked` uses `UV1.x < FrayWidth (~2 cm)` × a stretched noise to cut a hairy
    fringe;
  - the geometry already carries an aperiodic torn border and a few worn holes (tool).
  - Masked costs a little; it applies only to the `Sack_Edge` and outer-band pixels if implemented as a separate
    slot [inf].
- **Slots** (from the tool):
  - `Sack_Front`: the outer face;
  - `Sack_Back`: the inner face, darker × 0.7 and less normal;
  - `Sack_Edge`: the solidify rim, fibrous and lighter.
- **Usage flags:** Skeletal Mesh (route D), Clothing (route D+), Geometry Cache (route B), Nanite (the pile).
- **Thickness:** the solidify at 6–8 mm, applied in Blender on the settled copy, so the rim strip reads in the close
  shots (curtain lesson: zero thickness folds to knife edges, `ChaosClothCurtain.md:510-512`).

**Rag-pile instances:** `MI_Sackcloth_Dry`, `MI_Sackcloth_Dirty` (darker, grime ×2) and `MI_Sackcloth_Bleached`
(pale grey), assigned per piece. Per-piece variation also comes for free from UV1.y.

---

## 3. Simulation approach

### 3.1 The facts that decide it

1. **The figures animate**: they sway now, and an agitation layer is planned [rec/decl §1.2]. Anything that does not
   follow the skeleton fails.
2. **Six figures now**, with "duplicate some figures for a bigger huddle" requested [decl:
   `Scene3BeatSheet_2026-10-01.md:107`].
3. **Live cloth already costs 4–10 ms per figure** [rec §1.4]. A larger, heavier, thicker sheet with real
   self-collision costs more, not less [inf].
4. **Close cameras** (B08 ~1.4 m) [decl §1.3]: the cloth must carry rich folds, thickness and a ragged edge.
5. **Live Chaos is not deterministic under Sequencer scrubbing or transport jumps** [inf: it integrates from whatever
   state it holds; the curtain moved to GeometryCache for this reason, `ChaosClothCurtain.md:90`].

### 3.2 The options

| | What | For | Against | Cost to build |
|---|---|---|---|---|
| **A**: live Chaos per figure (today's route, made heavy) | Replace `CA_ShoreHeadDrape` with a 1.2–1.8 m, heavier, stiffer-bending asset; a bigger crown/shoulder Max-Distance region; the body PHYS colliders | Real motion and response to agitation; the pipeline exists | **Frame cost** ×6+ (already 13.4 ms of 23.6); slips and canopies (two corrections already, §1.1); a free sheet over a pot-belly and arms penetrates [inf]; no thickness (Chaos simulates a surface, so thickness would be render-only); non-deterministic on scrub/jump; the cloth gate is still unapplied | ~1 day of tuning per pose class; editor-only, every iteration a live run |
| **B**: a Blender-baked Alembic per figure | Export each body's animated section (FBX: skeleton + `AS_*_Full` at its start and 0.6 rate), drape and simulate the sheet hooked to the head bone, GeometryCache on the actor | The best-looking motion; deterministic; scrub-safe (the curtain pipeline) | Coupled to the animation timing: **any agitation edit or section move = re-bake** ×6; ~4.8k frames per figure for a 160 s scene [inf: 160.375 s, `ChaosClothCurtain.md` cue 97 note]; ~0.1–0.5 s/frame → 1–7 h each [inf]; ~0.3–0.6 GB Alembic each [inf: 4–8k verts × frames]; GeometryCache traps (stale frame after a jump, `running=false` freezes frame 0: memory *ue58-geometrycache-sequencer-traps*) | ~1 day setup + 6–40 h unattended |
| **C**: a static draped mesh | Blender drape in one pose → a static mesh attached to `head` | Cheapest | **Fails on animated bodies:** a rigid shell on the head swings through the shoulders and arms as the torso sways (±20–40 cm head travel) [inf] | ~½ day |
| **D**: drape then skin (**recommended**) | Blender drape per figure in a representative frame of its own section, then skin weights transferred from the MetaHuman body (head, neck, spine_03–05, clavicles, upper arms) → a **SkeletalMesh** on the MetaHuman skeleton → a component on `BP_Shore0N_Draped` with **Leader Pose = Body** | Follows any animation, including future agitation, with no re-bake; deterministic and scrub-safe; ~0 ms (one skinned mesh per figure); full authored richness (thickness, torn edge, folds); retiring the live drapes buys back ~6 ms of the mean frame [rec §1.4] | Folds are frozen in shape and only bend with the body. Under hard sway, slight "rubber shell" stretching is possible [inf], mitigated by heavy stiff hessian, which barely moves anyway. Needs a per-figure pose export. Leader-pose with a mesh bound in a different reference pose is standard practice but **untested here** [inf] | ~1.5–2 days for six |
| **D+**: D plus Chaos on the hem only | Build a Chaos Cloth Asset from D's skeletal mesh (skeletal import node, `ChaosClothCurtain.md:941`): Max Distance 0 on the crown/shoulders, 5–15 cm toward the hem, backstop; **3D rest lengths ON** (here the draped folds ARE the wanted rest shape, the opposite of the curtain rule) | The hem swings and settles during agitation; still far cheaper than A (small deviations, short solve) | Cost returns (smaller) and must be measured; cloth-component pose-from-parent is "unverified" in memory (*puss-chaos-cloth-teleport-floor*); scrub jumps need a teleport-reset | +1 day, after D is approved |

### 3.3 Recommendation

**D for all six now. D+ only if Gary, after seeing D in the agitation beats, wants the hem to move.**

**Why not A:**
- It is the expensive, fragile path Gary's complaint came from.
- It still cannot carry the 6–8 mm thickness or the torn edge into the sim.

**Why not B:**
- It is best only for a fixed animation, and S3's animation is explicitly not final (agitation layer).
- Six re-bakes per animation change is the trap the curtain team already lives with.

**What D keeps:** the realism that matters at 1.4 m (folds, weight, thickness, edges, material).

**Shore02 (bowed, crown at ~1.1 m):**
- Her drape is the easiest: 1.2 m already reaches the ground around a crouched body [inf].
- Do her first as the pilot, because her current asset is the special case (`CA_ShoreHeadDrape_Bowed`).

### 3.4 Size (the arithmetic Gary needs) [inf, with a measured cross-check]

- **The hem needs to sit below the crotch:** ≈0.45 × stature, i.e. ~0.72–0.83 m for these six. The crown of an
  upright figure is ~1.60–1.84 m.
- **A centred square** reaches about 0.8 × half-side below the crown at the edge mid-points and 0.8 × half-diagonal at
  the corners (the 0.8 accounts for wrapping over the head and shoulders).

  | Sheet | Edge drop | Corner drop | Hem lands at |
  |---|---|---|---|
  | **1.2 m** | ~0.48 m | ~0.68 m | **chest / waist** |
  | 1.64 m (today) | ~0.66 m | ~0.93 m | |
  | **1.8 m** | ~0.72 m | ~1.0 m | crotch / upper thigh |

- **Measured on a crude 1.76 m cylinder proxy** (smoke test, §7):
  - 1.2 m: hem median 1.36 m above the feet, 0 % of the hem below the 0.79 m target;
  - 1.8 m: hem median 1.0 m, 15 % below.
  - This proves only the direction. The proxy has no shoulders or arms, and the run is coarse and not fully settled.
- **Ways to keep Gary's "1.2 m" feel** and still hide the underpants:
  - (a) 1.2 × 1.8 m with the long axis front-to-back and the pin offset 15 cm forward. The face is covered, and the
    back drops to the buttocks [inf]. The tool supports `--size-y 1.8 --pin-offset 0,0.15`.
  - (b) Lower the figures into a real cower (crouch). That is animation, Gary's call.
  - (c) Darken or recolour the default-garment underpants so whatever shows reads as shadow (a cheap MI override on
    the outfit; it complements any choice).

---

## 4. Rag pile and sand

**Pile** (tool `--mode pile`):
- 8–12 torn hessian pieces, 0.45–1.3 m, pre-crumpled.
- They are dropped in a stack onto a generated sand mound, all in one mesh so self-collision stacks them.
- Settled for ~4 s.
- Exported as ONE static mesh with the mound.
- **Measured smoke:** 5 coarse pieces gave a 1.2 × 1.3 m footprint, 0.34 m P95 height, a 0.5 m peak.
- A production pile is ~1.8–2.5 m across and 0.4–0.6 m high [inf, to be set by Gary].
- **Pile assets:**
  - `/Game/Scenes/S3/Sackcloth/SM_S3_RagPile_A` (Nanite on; the material slots take `MI_Sackcloth_Dry` / `_Dirty` /
    `_Bleached`);
  - `SM_S3_SandPile_A..C`.
- Add a few loose single rags (2–3 pieces) as separate small meshes to scatter between the figures [inf: breaks the
  "one heap" read].

**Sand:**
- Beach v2 already lays a sand floor over an ellipse at dock centre x 3550, rx 500, ry 700, up to 20 cm high, with
  the Megascans `01_Soil_Sand_pjuuz0_2K_inst` [decl: `Saved/CodexConductor/s3_beach_v2.py:41-49`].
- **"Small beachy sand piles":** 3–5 extra mounds, 0.3–1.0 m across and 5–20 cm high.
  - Either the tool's mound generator or the Forest pack's `SM_sandy_slope_0N` pieces [decl: listing].
  - Give them **the same MI**, so they match the floor.
  - Optionally add Poly Haven `dry`/`dense_sand` for a drier, lighter top, as a later look call.

**Placement** (draft for Gary, in S3 dock frame cm):
- **Rag pile candidate R1: (3450, 560).**
  - Beside Shore03 at the +y side, inside the sand ellipse (normalised radius ≈ 0.81) [inf].
  - Clear of the camera-side gap (θ = 180°, −x) and of B04's camera at (3500, −750).
- **Candidate R2: (3300, −520).**
  - A foreground element in B04's view.
  - ~3 m from that camera [inf], which clears the 150 cm camera rule used by beach v2 [decl: `CAMERA_CLEARANCE_CM`].
- **The house pattern** [decl: `s3_beach_v2.py`; memory *puss-level-saved-landed-frame-trap*]:
  - attach to `S3 Hangar Root`;
  - tag **`S3.Rags`** (sand piles `S3.SandPiles`);
  - folder `S3/Sackcloth`;
  - compose against the LIVE root with an inside-box guard;
  - DRY/APPLY/REVERT, backup, record and level-only save.
- **Seat on the sand:** sample `sand_height()` from `s3_beach_v2.py` for the pile's base z, as beach v2 did for the
  figures' feet [inf: reuse].

---

## 5. Step list (route D), with estimates

Agent-hours are inferred. Editor steps need a free editor and, for writes, Gary's yes
(memory *puss-mutation-scripts-need-gary*, *puss-gary-word-means-gary*).

| # | Step | Where | Est. | Gate |
|---|---|---|---|---|
| 1 | **Gary's calls** (§6): size, cower vs sway, pile size/position, underpants tint | chat | — | blocks 3+ |
| 2 | **Export six posed bodies** (read-only to Content): per figure, `SKM_MHC_Shore0N_BodyMesh` + its `AS_Shore0N_*_Full` as FBX (`AssetExportTask`, FBX exporter, anim range = the selected section), into `DerivedAssets/S3Sackcloth/Bodies/`. Pick each figure's representative frame (the median-head-height sample in `shore_gentle_motion_selection.json`). Also export the skeleton and a reference-pose FBX for skin transfer. | editor, MCP | 1 h + run | read-only run; Gary's permission per memory |
| 3 | **Download** `hessian_230` / `hessian_380` via the library tool | offline | 0.5 h | — |
| 4 | **Size test:** run `build_sackcloth.py --mode drape` on Shore01 (upright) and Shore02 (bowed) at 1.2², 1.2 × 1.8 and 1.8², 2 cm quads, ~6 s settle, `--render`. Phone-card stills to Gary. | Blender | 1 h + ~10 min unattended | Gary picks the size |
| 5 | **Six drapes** at the chosen size, 1.5 cm quads, solidify 7 mm, per-figure yaw/pin offset. Check: hem metric, no penetration (add a body-distance check), stills. | Blender | 2 h + ~1 h unattended | Gary eyeballs stills |
| 6 | **Skin transfer** (to add to the tool as `--mode skin`): import the reference-pose skeleton FBX; Data Transfer of vertex groups from the body (nearest face interpolated); limit to 4 influences; zero the hand/finger groups (the cloth must not grab hands); smooth weights; export a skeletal FBX bound to the same bone names | Blender | 3 h (first), then scripted | — |
| 7 | **Material:** create-only `M_Sackcloth` (+ `_Masked`), three MIs, import the textures (`/Game/Scenes/S3/Sackcloth/Textures`) | editor | 2–3 h | Gary's yes (new assets only) |
| 8 | **Import** `SK_S3_Sack_Shore0N` (skeleton = the MetaHuman body skeleton; Interchange: watch the FBX traps, memory *ue58-fbx-import-traps*) | editor | 1 h | backup `Backups/PreS3Sackcloth-…` |
| 9 | **Wire:** in each `BP_Shore0N_Draped`, add `SackCloth` (SkeletalMeshComponent, leader pose = Body via construction script, as `ConfigureShoreDrape` does for the cloth) and **hide + disable simulation** on `ShoreHeadCloth` (do not delete: reversible). Never give a cloth asset to a pose component (crash memory). | editor | 2 h | Gary's yes; backup the six BPs |
| 10 | **Verify:** saved read-back; PIE through the S3 beats (sway + agitation), stills at B02/B04/B08; `stat` frame A/B against the 1.4 numbers; scrub jumps | editor | 2 h | report tiered |
| 11 | **Rag pile + sand piles:** pile bake (~10 min), import, `s3_rags_place.py` DRY/APPLY/REVERT (beach-v2 pattern, tag `S3.Rags`) | Blender + editor | 4 h | Gary's position |
| 12 | (optional) **D+** hem Chaos on 1–2 hero figures | editor | 1 day | after Gary sees D |

**Total for D plus the pile:** ~2.5 working days with Gary's answers in hand, mostly agent time [inf].

**Assets** (proposed):

| Kind | Name / path |
|---|---|
| Master materials | `/Game/Scenes/S3/Sackcloth/M_Sackcloth`, `M_Sackcloth_Masked` |
| Material instances | `MI_Sackcloth_Dry`, `_Dirty`, `_Bleached` |
| Textures | `T_Sackcloth_Hessian230_{BC,N,R,AO,Mask}` |
| Drapes | `SK_S3_Sack_Shore0{1..6}` |
| Rag pile | `SM_S3_RagPile_A` |
| Sand piles | `SM_S3_SandPile_{A..C}` |
| Blender outputs | `DerivedAssets/S3Sackcloth/` (the tool's default `--out-dir`) |

---

## 6. Gary's decisions

1. **Size:** 1.2 × 1.2 m covers to the chest on the upright figures (§3.4).
   - Choose 1.2 × 1.8 (front-back long, recommended), or 1.8 × 1.8.
   - Or keep 1.2 and make them crouch.
   - (Today's sheet is already 1.64 m.)
2. **Cower or sway:**
   - Should the figures stay in their current standing sway (Shore02 already crouches)?
   - Or get a lower, cowering posture? That is animation work, and it changes how much cloth is needed.
3. **Motion of the cloth:**
   - Is a cloth that rides the body with authored folds (D) enough?
   - Or must the hem visibly swing in the agitation beats (D+, costs frame time)?
4. **The underpants fallback:** OK to darken the default-garment underpants as insurance?
5. **Look:**
   - new golden jute versus old grey sack (per figure or uniform);
   - stains;
   - a faded stencil print or not;
   - weave see-through (masked) or solid.
6. **Rag pile:**
   - size (1.5 m vs 2.5 m across);
   - one heap or a heap plus scattered rags;
   - position R1 (3450, 560), R2 (3300, −520), or elsewhere;
   - sand piles where.
7. **More figures:** if the huddle grows, D scales cheaply. Each duplicate is one more skinned mesh and no sim.
8. **The live drapes:** may they be switched off (hidden + simulation disabled, reversible) once D is in?
   - That also settles the never-applied cloth gate (§1.4).

---

## 7. What was run today, and what was not

**`Tools/S3Sackcloth/build_sackcloth.py`** (new):
- **`--dry-run`** (plain Python) [meas, 6 Oct]:
  - drape 1.2² gives `SACK_DRY_RUN_OK` with 3721 verts;
  - 1.4 × 1.9 with a pin offset passes;
  - pile passes;
  - the negative cases fail as designed: `--quad 0.09` ("fewer than 20 quads") and a missing `--collider`, both rc 2.
- **Blender 4.4.0 smoke tests** [meas, 6 Oct, scratchpad outputs, a few seconds each]:
  - drape on a crude OBJ cylinder proxy, 4 cm quads, 180 frames, quality 8: runs end to end (import, auto-scale,
    crown, pin disc, cloth, settled copy, solidify, FBX, JSON, renders). Hem metrics as in §3.4.
  - pile with 5 pieces, 5 cm quads, 90 frames: `SACK_OK`, footprint 1.16 × 1.33 m, P95 height 0.34 m.
- **Found and fixed by the smoke test:**
  - a physical sacking mass (0.55 kg/m²) did not fall at all: the hem stayed at the crown after 40 frames.
  - Blender stiffness is not mass-normalised (memory *puss-blender-cloth-drop-traps*). The tool now takes
    `--solver-mass` (default 13.4 kg/m² = the approved curtain's 0.1111 kg per 9.1 cm vertex
    [decl: `Saved/CodexSoftGoods/DropBake/final10_opening_dense_a06.json` `mass_per_vertex`]), with air damping
    scaled by vertex area.
- **Not exercised:**
  - FBX armature import;
  - `--head-bone` hook (route B);
  - `--export-abc`;
  - a real MetaHuman body;
  - the cm→m auto-scale on a real UE FBX.
- **Stiffness:** at production settings the stiffness is untuned. The 1.8 m smoke drape stood as a stiff tent on the
  proxy. Tune `--bend`/`--compression` on a real body in step 4 and judge from the pictures, not the numbers (curtain
  lesson).
- **Not written:** `--mode skin` (step 6), the UE material builder (step 7) and the placement tool (step 11).

---

## 8. 6 Oct follow-up: Gary's answers and what was built

### 8.1 Gary's answers (relayed by the conductor)

- **Size:** 1.8 × 1.8 m.
- **Route:** D, drape-then-skin: fixed folds that ride the body, no live hem. In his words: "Let's try option 1 and
  see if it looks ok".
- **Look:** "Old grey worn sack" for all figures. No golden jute, no stencil.
- **Export of the six posed bodies:** "Yes, export now".
- **Texture:** `hessian_230` 2K was downloaded with his OK, to `DerivedAssets/S3Sackcloth/textures/hessian_230/`
  (diff, nor_dx, rough, ao, disp, mask, plus `manifest.json` with sha256 and the Poly Haven md5) [decl: manifest].
  Step 3 is done.

### 8.2 Export tool: `Saved/CodexConductor/s3_shore_export_bodies.py` (+ `_run.py`, `_request.json`)

**Status:** written and **not run** (no MCP from this session). Its offline part has run (8.2.3).

#### 8.2.1 What it does

- Read-only on the level and the Show.
- **Inputs:** for each figure it uses the level actor `<id> Clam`, asserting the class is `BP_<id>_Draped_C`, and
  that actor's `Body` and `Face` components.
- **Exports**, with `AssetExportTask` + `FbxExportOption`, to `DerivedAssets/S3Sackcloth/bodies/<id>/`:
  - `<id>_Body.fbx` (the body skeletal mesh, reference pose);
  - `<id>_Face.fbx` (the face skeletal mesh; it carries the head the drape rests on: the MetaHuman body mesh stops at
    the neck [inf, MetaHuman layout]);
  - `<id>_Anim.fbx` (the figure's full `AS_<id>_*_Full` take; skeleton plus curves).
- **Writes** `bodies/export_manifest.json`: paths, bytes, sha256, the anim frame count / length / fps, the pose time
  and frame, and the actor and Body world transforms.
- **Never** loads a LevelSequence. The scene section comes from the records (`shore_gentle_motion_selection.json`,
  cross-checked against `shore_clam_integration.json`); it fails on a mismatch.
- **Never** saves.
- **Census:** the dirty-package census must be identical before and after.
- **Refuses** if PIE is running. It never ends PIE.
- **Marker:** `S3_SHORE_EXPORT_OK|run=…|figures=6|files=18|census=…|manifest=…`. Any failure is
  `S3_SHORE_EXPORT_FAILED|run=…|reason=…`.

#### 8.2.2 API basis

**Declaration-proven:**
- `UAssetExportTask` fields: `Runtime/Engine/Public/AssetExportTask.h:20-65`.
- `UExporter::RunAssetExportTask`, a static `BlueprintCallable`: `Runtime/Engine/Classes/Exporters/Exporter.h:254-255`.
- `UFbxExportOption` flags: `Editor/UnrealEd/Classes/Exporters/FbxExportOption.h:69-115`.
- `USkeletalMeshExporterFBX` and `UAnimSequenceExporterFBX`: `Editor/UnrealEd/Classes/Exporters/`.
- `GetNumFrames` / `GetSequenceLength` take out-params, so Python gets return values:
  `Editor/AnimationBlueprintLibrary/Public/AnimationBlueprintLibrary.h:73,598`.

**Inferred** (no exporter .cpp in the install, memory *ue58-engine-source-limits*):
- the exact bind pose, units and axes written;
- whether Python exposes the exporter classes. The tool falls back to "by extension".
- These are checked on the Blender side.

**Why not a posed mesh directly** [decl]: no exporter in the headers writes a skeletal mesh in an animated pose. So
Blender poses it from mesh + anim (8.3).

#### 8.2.3 Pose frames

Picked offline [meas: `python s3_shore_export_bodies.py`, 6 Oct]. Each is the 0.5 s sample inside the figure's scene
window whose head height is nearest the window median.

| Figure | Section start | Pose source time | Head z |
|---|---|---|---|
| Shore01 | 12.5 | 27.0 s | 161.2 cm |
| Shore02 | 49.0 | 57.5 s | 94.0 cm |
| Shore03 | 33.0 | 40.5 s | 152.7 cm |
| Shore04 | 72.5 | 80.0 s | 142.5 cm |
| Shore05 | 14.0 | 19.5 s | 154.3 cm |
| Shore06 | 28.5 | 32.0 s | 152.5 cm |

### 8.3 `build_sackcloth.py --mode skin` (route D)

#### 8.3.1 Steps

1. **Pose.**
   - Import the three FBX files from the manifest. The scene fps is set to the anim's first, so seconds map to frames.
   - Measure the rest body + face height and rescale cm→m if needed.
   - Go to the pose frame and copy the anim rig's pose onto the body and face rigs (`copy_pose`).
   - **Two copy modes:**
     - `matrix`: full bone transforms;
     - `rotation`: anim rotations on the body's own bone offsets, i.e. UE's "Skeleton" translation retargeting.
   - `auto` (the default) keeps whichever puts the head bone nearest the UE record. The check
     `pose_head_z_matches_record` (3 cm) fails the run otherwise.
   - This matters because the anim FBX's rig carries `metahuman_base_skel`'s proportions, not each body's.
2. **Colliders.** Make static posed copies of body + face as colliders.
3. **Crown.** The crown is the highest collider point within 25 cm of the head bone (`--crown head`), so bowed
   Shore02 gets its crown, not its back.
4. **Drape** the 1.8 × 1.8 m sheet with the 7 mm solidify and the frayed border.
5. **Weights.**
   - Data Transfer (nearest face, interpolated) from the posed body + face.
   - Every weight is remapped to its nearest ancestor in the chain: head, neck_01/02, spine_01-05, clavicle_l/r,
     upperarm_l/r. Hands → upper arm; facial bones → head; pelvis and legs → `spine_01`.
   - Non-bone groups such as the cloth's `Pin` are dropped.
   - Then 3 Laplacian smoothing passes, top-4 influences, and normalise.
6. **Bind.**
   - A copy of the body rig with the **pose applied as rest**, named `Armature`. The sack's bind pose is therefore
     the drape pose.
   - In UE, leader pose drives it from the Body's live bones [inf: standard; a follower skins with its own
     inverse-bind matrices].
7. **Export and verify.** Export `<out-id>_SK.fbx`, re-import it and compare. The checks:
   - `skin_bind_is_identity` (< 0.1 mm);
   - `skin_roundtrip_within_5mm` (head bone and bounding box);
   - `skin_unweighted_under_1pct`.

#### 8.3.2 Harness

`Tools/S3Sackcloth/make_synthetic_rig.py` writes a synthetic body/face/anim FBX set at cm scale with a manifest of the
same shape:
- the MetaHuman bone names;
- an anim rig whose spine is 5% longer than the body's.

#### 8.3.3 Measured on the synthetic rig (6 Oct, Blender 4.4.0, 4 cm quads, scratchpad outputs)

**The whole skin path runs:**
- head z matches the record to 0.0 mm in `matrix` mode. `rotation` mode is 2.25 cm off, so `auto` discriminates;
- 0 unweighted vertices;
- bind error 3e-7 m;
- re-import head and bounding-box error under 4e-7 m;
- 22 bones exported.

**Coverage at 1.8 m does NOT reach the crotch on a 1.77 m stand-in:**
- At default settings the outer-hem P10 was **1.0-1.1 m above the feet** and the median 1.3-1.5 m, against a 0.80 m
  target. `hem_median_below_target` correctly FAILS.
- The stand-in is a 34 cm-wide cylinder with no shoulders, so the fabric gathers and bells out around a narrow
  column [inf]. The real bodies decide (step 4).
- **If it is still short** on a real body, the levers:
  - `--pin-offset 0,0.2` (more cloth to the front);
  - `--yaw 45` (corners front and back; the one try on the stand-in slid sideways, so look at the stills);
  - 2.0 m.
  - Gary's eye decides.

**Settle defaults** for drape and skin, chosen from stills on the stand-in:
- compression 20, bend 1, friction 2, quality 20 / collision 8, **air damping 6**, 240 frames.
- At air damping 1 the far edges flipped back over the head. With compression 4 the sheet crumpled into a cap.
- These are a starting point, not a tune.
- Pile mode keeps its own defaults (compression 4, bend 2, friction 8, air 1, 120 frames); its regression run passed
  (`SACK_OK`).

**Other measurements:**
- **Two bugs fixed by measuring:**
  - worn holes counted as "hem" and read 0.3 m high, so the hem is now the outer boundary in the flat pattern;
  - the `vertex_group_smooth` operator's poll fails headless, so the smoothing is now done in the tool.
- **Cost:** 0.25 s/frame at 4 cm on the stand-in. Real bodies at 2 cm should be ~1-2 s/frame, ~4-8 min per figure [inf].

**Not exercised:** a real UE FBX (units, axes, the bone count of about 1000, the face rig's root). The re-import and
head checks are the gates.

#### 8.3.4 Commands per figure (after the export)

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" -b --factory-startup --python Tools/S3Sackcloth/build_sackcloth.py -- --mode skin --figure Shore01_M56 --out-id Shore01_M56_Sack --quad 0.02 --render
```

Outputs, in `DerivedAssets/S3Sackcloth/`:
- `<id>_Sack.json`: checks and metrics;
- `_34.png` / `_side.png`: stills for Gary;
- `<id>_Sack_SK.fbx`: the skeletal mesh;
- `<id>_Sack.fbx`: a static preview.

### 8.4 UE import and material builder plan (not written; create-only; conductor runs; Gary's yes for the writes)

**Builder:** `Saved/CodexConductor/s3_sackcloth_build.py`, DRY / APPLY / VERIFY. It copies `velvet_v2_build.py`'s
scaffolding:
- refuse if a target exists;
- never delete a node (memory *ue58-python-material-authoring*);
- assert every connection and re-read every edge;
- gate on material-instance read-back, not on setter bools;
- refuse if content is dirty before; save only its own packages;
- pixel-shader instruction count above 0 at VERIFY.

**1. Textures** → `/Game/Scenes/S3/Sackcloth/Textures/`, from `DerivedAssets/S3Sackcloth/textures/hessian_230/`:

| Texture | Source map | Settings |
|---|---|---|
| `T_Sack_Hessian230_BC` | diff | sRGB |
| `T_Sack_Hessian230_N` | nor_dx | `TC_Normalmap`; DirectX is UE's convention |
| `T_Sack_Hessian230_R` | rough | linear grayscale; memory: use `LINEAR_GRAYSCALE` |
| `T_Sack_Hessian230_AO` | ao | linear grayscale |
| `T_Sack_Hessian230_H` | disp | linear grayscale |
| `T_Sack_Hessian230_Mask` | mask | linear grayscale; for the later see-through variant |

- Use AssetImportTask with options set, and **diff the folder before and after** (memory *ue58-fbx-import-traps*:
  stray assets).
- The rough, AO and disp PNGs are 16-bit (`I;16`) [meas: PIL]. **Check** that UE imports them as G16, not 8-bit.

**2. `M_Sackcloth`** (master):
- **Model and flags:** Default Lit, opaque, NOT two-sided (solidify gives real back faces). Usage: Skeletal Mesh, Static
  Mesh (the rag pile), Nanite.
- **Coordinates:** UV0 is in metres, so `TexCoord0 / TileM` (TileM 0.269).
- **Base colour:**
  - `BC × lerp(1, Mottle, MottleAmount)`. The mottle is low-frequency noise on world position, 0.5 m, ±8%.
  - Then desaturate by `Desaturate` and multiply by `Tint`.
  - Then `lerp(…, GrimeColor, GrimeMask)`. GrimeMask = saturate((`HemGrimeHeightM` − world Z above the ground plane
    param) / falloff), maxed with `(1 − UV1.x / EdgeGrimeWidthM)` × EdgeGrimeAmount.
  - UV1.x is the torn-edge distance written by the tool.
- **Normal:** `T_N` with `NormalStrength` (FlattenNormal), plus a 1 m crumple normal from noise at 0.15.
- **Roughness:** `T_R × RoughnessScale` (start 1.0, clamp 0.75-1.0).
- **Specular:** 0.3.
- **AO:** `T_AO`.
- **Rim:** `Fresnel(exp RimExponent 4) × RimAmount 0.06 × RimColor` added to the base colour: loose-fibre glint at
  grazing light.
- **No parallax, no displacement in pass 1.**
- **Slots (from the tool):** `Sack_Front` → `MI_Sackcloth_OldGrey`; `Sack_Back` → `MI_Sackcloth_OldGrey_Inner`;
  `Sack_Edge` → `MI_Sackcloth_OldGrey`.

**3. `MI_Sackcloth_OldGrey`** (Gary: "old grey worn sack"):
- Desaturate 0.75, Tint linear 0.62/0.60/0.56;
- MottleAmount 0.10, GrimeColor 0.10/0.09/0.08, HemGrimeHeightM 0.35, EdgeGrimeWidthM 0.03, EdgeGrimeAmount 0.6;
- RoughnessScale 1.0, NormalStrength 1.0, RimAmount 0.05.

`MI_Sackcloth_OldGrey_Inner`: the same with InnerDarken 0.7 and NormalStrength 0.6.

All values are starting points [inf]. Gary judges them from stills.

**4. Skeletal meshes** → `/Game/Scenes/S3/Sackcloth/SK_S3_Sack_<id>` from `DerivedAssets/S3Sackcloth/<id>_Sack_SK.fbx`:
- Skeleton = the figure's body skeleton, read from the export manifest's `skeleton` (record:
  `/Game/Metahuman/ShoreCast_20260910/Assembled/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel`).
- Import as a skeletal mesh only: no animations, no materials or textures, no morph targets, no physics asset; keep the
  mesh's own reference pose (do **not** use T0 as the reference pose).
- Through Interchange, read every option back.
- **Gates:**
  - one LOD;
  - three material slots;
  - bone count equals the Blender export's;
  - the skeleton is the body's;
  - a probe actor with leader pose set at the pose time puts the sack within 1 cm of the Blender bounding box (bench,
    no save).

**5. Wire, per figure** (backup `Backups/PreS3Sackcloth-YYYYMMDD-HHMM`: the six BPs and the level):
- In `BP_<id>_Draped`, add a `SackCloth` SkeletalMeshComponent (the asset above, the OldGrey MIs per slot), parented
  to Body.
- In the construction script, call `SetLeaderPoseComponent(Body)`. That is the pattern `ConfigureShoreDrape` uses for
  the head cloth.
- Hide `ShoreHeadCloth` and set Enable Simulation false. Do not delete it (reversible).
- **Never** give a cloth asset to a pose or skeletal component (crash memory).
- Save only those packages. Read back.
- Verify in PIE (stills at B02/B04/B08, `stat` frame A/B, scrub jumps); the conductor must not end PIE.

### 8.5 Order of runs for the conductor

1. `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/s3_shore_export_bodies_request.json`
   - Expect `S3_SHORE_EXPORT_OK|run=…|figures=6|files=18`.
   - Then check `DerivedAssets/S3Sackcloth/bodies/export_manifest.json` and that the census is empty before and after.
2. **Size and look test** on Shore01 (upright) and Shore02 (bowed), about 5-10 min each. Show the stills to Gary:
   ```
   "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" -b --factory-startup --python Tools/S3Sackcloth/build_sackcloth.py -- --mode skin --figure Shore01_M56 --out-id Shore01_M56_Sack --render
   ```
   - Then the same with `Shore02_F52`.
   - **Gate:** all checks pass except possibly `hem_median_below_target`, which is a coverage question for Gary,
     with the levers in 8.3.3.
3. **The other four** with the same command, then the 2 cm-quad finals for all six (`--quad 0.02`).
4. **The UE builder and import** (8.4): to be written, then DRY → APPLY (Gary's yes) → VERIFY.
5. **Wiring** (8.4 item 5): Gary's yes.

---

## 9. 6 Oct afternoon: first real bodies. The balloon fixed, and the missing torso

All runs below used Blender 4.4.0 on the exported Shore01/Shore02 FBX. Stills and JSON are in
`DerivedAssets/S3Sackcloth/iter_20261006/`. Every number is [meas] unless marked.

### 9.1 Why the first run ballooned (the conductor's Shore01 run: a 0.9 m "boulder")

**Cause: the vertex mass was ~100× too light for Blender's stiffness units.**
- The tool's `--solver-mass 13.4 kg/m²` × vertex area gave 0.005–0.012 kg per vertex.
- Blender's cloth presets assume 0.3–1 kg per vertex at the same spring values, so the springs out-muscled gravity
  and the sheet crumpled stiffly.
- With the old recipe re-run at 3 cm, the footprint was **1.10 × 1.10 m**.
- With a 0.6 kg vertex mass (everything else at preset-like values), the same sheet **hangs**, with a footprint of
  0.53–0.73 m.
- Of four recipes tried (cotton-like, denim-like, heavy-soft, mass-only), all four hung once the mass was right.
  Heavy-soft hung closest to the body.

**The recipe is now the drape/skin default:**

| Setting | Value |
|---|---|
| vertex mass | 0.6 kg |
| tension | 40 |
| compression | 5 |
| shear | 10 |
| bend | 1 |
| air damping | 1 |
| quality / collision | 12 / 4 |
| friction | 5 |
| self-collision distance | 5 mm |
| quad | 3 cm |
| frames | 300 (10 s) |

- Solidify stays at 7 mm.
- Cost: about 1.0–1.4 s/frame, so ~6 min per figure. Four figures run in parallel in about the same time.

### 9.2 The missing hips are not a dropped slot: the exported Body has no torso at all

- **Measured in Blender:** the rest-pose `Shore01_M56_Body.fbx` has 380–512 open boundary edges at 0.8–1.0 m.
- **More decisive, also measured:** **no vertex dominated by a pelvis, spine or thigh bone lies above 0.79 m.** Arms,
  legs, feet and neck are present; the whole torso from the thigh tops to the neck is cut away.
- **Interpretation [inf]:** MetaHuman removes the body faces hidden under the outfit. The assembled
  `MHC_<id>_Outfits` holds DefaultGarment Shirt and Short materials [decl: `assembly_assets_Shore01_M56.json`]. In UE
  the shirt/short garment (Gary's "white underpants") fills the gap.
- **In Blender (until a full body exists):** skin mode adds a **collider-only torso proxy**. It is four ellipsoids
  along the posed spine: hip width from the thigh bones, shoulder width from the upper arms, depths 0.10–0.135 m.
  It is never exported and never used for weights.
- **The proper fix (UE, read-only):**
  - The export tool now also exports `SKM_MHC_<id>_BodyMesh_DNA` when it exists and shares the skeleton. It is
    expected to be the uncut body [inf, by name only].
  - Skin mode prefers it automatically (`body_source` in the JSON) and drops the proxy.
  - **Re-run the export** to get it.
- **Also added:** a ground collider at the feet. Shore02's cloth reached the floor and went 13 cm through it without
  one.

### 9.3 New gates (numbers per figure)

The conductor's spec gave three gates:
- hem median ≤ 0.85 m above the feet;
- max horizontal extent ≤ 0.65 m from the body axis;
- no balloon.

**How each is measured now:**
- **Hem:** the outer hem only. Holes are excluded, which earlier made the hem read high.
- **Extent:** the horizontal offset from the nearest point of the posed pelvis-to-head bone chain. A pelvis-only axis
  read 0.75 m on bowed Shore02 because the head is far in front of the pelvis.
- **Balloon:** the gate is now the **footprint** (bbox side ≤ 0.85 m: the balloon measured 1.10 m, hanging runs
  0.50–0.73 m).
  - The cloth-to-body gap p75 is reported but is **not** a gate. A crouched figure's sheet tents to the ground
    (Shore02 gap p75 0.26 m) without ballooning.
  - Calibration, old recipe: gap p75 0.27 m and bbox 1.10 m. New recipe on Shore01: gap p75 0.10 m and bbox 0.66 m.

**Shore01 (upright, 1.79 m, crown 1.86 m):**

| Size / pin | Hem p50 | Hem p10 | Extent max | bbox (m) | Gates |
|---|---|---|---|---|---|
| **1.8 × 1.8** (Gary's) | **1.015** | 0.79 | 0.33 | 0.66 × 0.53 | hem FAILS |
| 1.8 + pin 20 cm forward | 0.97 | 0.71 | 0.32 | 0.65 × 0.51 | hem FAILS |
| 1.8 + 45° turn | 1.02 | 0.82 | 0.39 | | hem FAILS (old proxy-less run) |
| **2.0 + pin 20 cm forward** | **0.848** | 0.56 | 0.32 | 0.71 × 0.50 | all pass |
| 2.2 × 2.2 | 0.815 | 0.57 | 0.38 | 0.71 × 0.61 | all pass |

**Shore02 (bowed, head bone 0.94 m):**

| Size | Hem p50 | Hem p10 | Extent | bbox (m) | Gates |
|---|---|---|---|---|---|
| **1.8 × 1.8** | **0.32** | 0.10 | 0.32 | 0.59 × 0.54 | all pass |

- For Shore02 the cloth falls forward over the bowed head and shoulders down to the ground.
- **But her rear and the back of the thighs stay uncovered** in the side still (the open tubes are the cut body; in UE
  that is where the white shorts show).
- A **backward** pin offset is the lever for her (`--pin-forward -0.2`). Not run yet.

### 9.4 What this means for Gary

1. **1.8 m cannot cover the crotch on the upright figures.** The pin offset and the 45° turn each moved the median
   hem ≤ 5 cm. **2.0 m with the pin 20 cm forward** is the smallest tried that passes (median 0.85 m; the corners
   reach the knees at 0.56 m).
   - Choose per figure: 2.0 m for the four upright figures, 1.8 m for bowed Shore02.
   - Or keep 1.8 m everywhere and darken the shorts. His call.
2. **Look:** stills are rendered with the hessian_230 material, desaturated to "old grey worn", in EEVEE:
   - `iter_20261006/Shore01_M56_Sack_1p8_{34,side}.png`
   - `iter_20261006/Shore01_M56_Sack_2p0_fwd20_{34,side}.png`
   - `iter_20261006/Shore01_M56_Sack_2p2_{34,side}.png`
   - `iter_20261006/Shore02_F52_Sack_1p8_{34,side}.png`
   - The body renders black in these stills (the review skin material did not take). This is cosmetic, review only.
3. **The earlier `DerivedAssets/S3Sackcloth/Shore01_M56_Sack*` files are the balloon run.** They are superseded; do
   not import them.

### 9.5 Commands

All four candidates above came from (`--textured` renders the material):
```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" -b --factory-startup --python Tools/S3Sackcloth/build_sackcloth.py -- --mode skin --figure Shore01_M56 --out-dir DerivedAssets/S3Sackcloth/iter_20261006 --out-id Shore01_M56_Sack_2p0_fwd20 --size-x 2.0 --size-y 2.0 --pin-forward 0.2 --render --textured
```

**Size flags:**
- `--size-x 1.8 --size-y 1.8` is the default (Gary's size);
- add `--pin-forward 0.2` for more cloth at the front, or `-0.2` for Shore02's back;
- `--quad 0.02` for a finer final (≈2–3× the time) [inf].
