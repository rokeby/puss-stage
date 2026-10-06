# Curtain fabric: velvet v2, three alternative textiles, and a bench plan

**Written:** 6 Oct 2026, offline. Nothing here has run in Unreal.
**For:** Gary (6 Oct ~02:00): "the curtain looks really basic right now. Either an effective velvet that responds well to
all these lighting changes, or a different textile."

Every claim carries a tier, per AGENTS.md:
- **[decl]** read in a file, header or shader (cited);
- **[meas]** run and read back (dated);
- **[inf]** inferred, with the reason.

---

## 0. Recommendation (the short version)

| Curtain | Fabric | Why |
| --- | --- | --- |
| Opening drop + I1–I5 drapes (one cache, `GC_CurtainDrop_Opening`) | **Velvet v2**, variant **V2B** first ("theatre velvet": darker faces, stronger pile sheen) | It is the house curtain. Velvet's signature under hard light is a dark core with bright grazing rims on the fold crests, which is exactly what the Cloth model's fuzz lobe and v2's Fresnel terms add |
| Back-passage curtains with pictures (`MI_CurtainImage_P01..P05`) and the P04 backcloth | **Painted cotton (scenic muslin / duck)**, pale, matte | A deep red dye absorbs blue and green light, so velvet goes black under the coloured washes (section 2.4). A pale cotton takes the colour of every light, and a print sits on it crisply, with no pile to mute it |
| P05 blue-sky fence curtains (the new unfurl cache) | **Cotton, dyed sky blue**; **silk satin** as the bench alternative | Fill-lit blue sky: matte cotton reads as a painted sky; satin reads as a rippling, glossy sky. Gary's call from stills |
| Masking (border, legs) | Stay velvet black | Black steel read LIT TAN under warm light; velvet MID black held at 77 (memory *puss-masking-needs-velvet*, measured 30 Sep) |

**The one design decision inside this:** the curtain that must "respond well to all these lighting changes" should be
**pale**, not red. On a red velvet, the coloured light is lost by physics, not by the shader.

---

## 1. What `velvet_v2_build.py` and `velvet_v2_bench.py` do (written 5 Oct, never run)

### The builder (`Saved/CodexConductor/velvet_v2_build.py`, commit 0c67597)

**What it creates** [decl: :6-11, :50-58]:
- `M_CurtainVelvet_v2`, a NEW master. It uses the **Cloth** shading model, is two-sided, uses material attributes, and is
  flagged for Geometry Cache, Skeletal Mesh and Clothing [decl: :326-333].
- One instance, `MI_CurtainVelvet_v2_DeepRed`, in `/Game/Scenes/Curtain/Chaos/Materials`.
- Nothing existing is edited [decl: :10].

**The graph** [decl: :13-24, :147-187]:
- UV0 is scaled by `PatternWidthM`/`DropM` into flat-fabric metres. These are copied at run time from
  `MI_CurtainVelvet_DeepRed_Drop` [decl: :270-280].
- Two normal maps:
  - `T_CurtainVelourScan_N` (pile, 0.5 m tile, strength 0.6);
  - `T_CurtainVelvetCrush_N` (crush, 0.6 m tile, strength 0.25).
  - They are whiteout-blended [decl: :131-135].
- A procedural 4-octave crush mottle [decl: :85-105].
- A Fresnel drives `FoldDarken` (faces darker) and `RimLift` (grazing toward the sheen colour) in the albedo
  [decl: :107-114].
- **How the Cloth inputs are fed:**
  - Fuzz colour goes to SubsurfaceColor.
  - Cloth amount goes to ClearCoat on MakeMaterialAttributes, which lands in CustomData0. That is the route
    `M_CurtainVelvet` was built with [decl: :28-30].
- Colour = plain oxblood B [decl: :76-80].

**Safety, all honoured in the code:**
- **Create-only.** It refuses if a target exists [decl: :367-369].
- **It never deletes an expression.** There is no delete call in the file (searched).
- Every connect is asserted, then every edge is re-read [decl: :443-484].
- It gates on the MI read-back, including the override flags, never on setter bools [decl: :303-324].
- It refuses when content is already dirty, and saves only its two packages [decl: :255-256, :510-518].
- DRY is the default mode [decl: :39-43, :198].
- VERIFY requires a pixel-shader instruction count above 0 [decl: :355-359].
- All UE work happens inside `main()` [decl: :190-191].
- This matches the memory rules *ue58-python-material-authoring* (never delete nodes on pre-existing assets) and
  *puss-mcp-python-crashes-the-editor*.

### The bench wrapper (`Saved/CodexConductor/velvet_v2_bench.py`)

**What it does** [decl: :1-22]:
- It runs NEXT TO `Saved/CodexSoftGoods/material_bench.py`, which owns the `ZZ_MaterialBench_Drape` GeometryCache
  stand-in, placing it, capturing it and cleaning it up.
- Its actions:
  - `params` (read-only);
  - `variant` (a transient MID parented to `MI_CurtainVelvet_v2_DeepRed`, on every slot);
  - `lights` (read-only: the mouth lanterns);
  - `spot_on`/`spot_off` (one transient `ZZ_VelvetBench_Spot`).
- It never saves, and refuses in PIE or in the wrong world.

**Its plan** [decl: `velvet_v2_bench_variants.json` "capture_plan"]:
- 6 variants (control B, then V2A–V2E) under 3 lightings (Opening stalls, I1 lantern, I1 narrow shadow-play spot at
  900 cd, 12°/6°): 18 stills.

**Gaps found by reading it (none are bugs in what it claims):**
1. **The parent is hard-coded** to `MI_CurtainVelvet_v2_DeepRed` [decl: :29, :190]. The alternative textiles need a
   parent per variant.
2. **The lights schema has no colour.** `validate_variants` demands exactly local_cm, aim_local_cm, candela,
   outer/inner_deg, kelvin, radius_cm and shadows [decl: :85-87]. Coloured spots need an optional `rgb` key.
3. **Holds only.** `tick_at_this_time` does not pose the stand-in mid-fall [decl: `Docs/ChaosClothCurtain.md`
   "Velvet", last bullet], so there are no mid-fall stills.
4. **The Fresnel has no explicit Normal input** [decl: EDGES :160 wires only ExponentIn]. It therefore uses the pixel
   normal, including both detail normals [inf: the Fresnel node's default], so the rim may sparkle with the pile tile.
   Watch for it in the close stills; the fix is a `PileNormalStrength` value, not a graph edit.

---

## 2. What makes velvet read under hard theatre light (UE 5.8, this project)

### 2.1 The Cloth model [decl: `UE_5.8/Engine/Shaders/Private/ShadingModels.ush:674-710`]

- `ClothBxDF` adds an "asperity scattering" lobe: inverse GGX, `D_InvGGX(Pow4(Roughness))`, with `Vis_Cloth`.
- Its F0 is the **Fuzz colour** (`F_Schlick(FuzzColor, VoH)`).
- It is blended with the standard specular by `Cloth` = CustomData0: `lerp(Spec1, Spec2, Cloth)`.
- **One roughness drives both lobes.** At the 0.85–0.95 velvet roughness, the fuzz lobe is broad and grazing: bright
  where the fold turns away from the viewer under a light. That is the "bright rim, dark core".
- **Cloth transmits nothing:** `Lighting.Transmission = 0` (:708). The "Subsurface Color" pin is a sheen colour
  (also `Docs/ScrimFeasibility_2026-09-29.md`).

### 2.2 Anisotropy is NOT available on Cloth in legacy shading

- `DefaultLitBxDF` has an anisotropic GGX path [decl: ShadingModels.ush:212, 224-267].
- `ClothBxDF` has none [decl: no Anisotropy reference in :674-710].
- So the scan's patchy, directional velour highlights cannot be had on the Cloth model. That is already recorded:
  "its anisotropy maps, which Cloth shading cannot use" (`Docs/ChaosClothCurtain.md`, "Velvet").
- Substrate (a Slab with Fuzz plus anisotropy) would allow both, but **Substrate is not enabled** in this project
  [decl: no `r.Substrate` in `Config/DefaultEngine.ini`; the switch is `RendererSettings.h:1257-1261`, restart
  required].
- Enabling it is a project-wide material recompile and a risk to every existing material. **Not recommended now.**

### 2.3 Distance decides which detail matters [meas, 30 Sep]

- At the 14 m stalls, "only colour, sheen and falloff read; weave and seams (12 cm) are invisible".
- The CC0 velour scan was indistinguishable from flat B (0.08–0.14/255).
- [decl: `Docs/ChaosClothCurtain.md` "Velvet" bullets "Bench" and "CC0 scan"]

**So the two detail scales that pay are:**
- the **fold scale**, which is real geometry in the cache;
- the **crush scale (0.35–0.6 m)**, where v2's mottle sits.

**The levers that matter are the response ones:**
- the face/rim contrast (FoldDarken, RimLift, NapExponent);
- sheen versus body colour;
- roughness.

### 2.4 Coloured light on a red dye [inf: reflectance arithmetic]

- The oxblood body is linear RGB 0.07/0.004/0.012 [decl: velvet_v2_build.py:76-80].
- Under a saturated blue light, the reflected blue is 0.012 of the light: about 6× darker than under white, and with no
  red to show. A red velvet therefore goes **black** under the P05 blues and the P06 sleepy blue.
- That is true of real theatre velvet too. It is the reason cycloramas and backcloths are pale.
- **The fabric that "responds" to coloured light is a pale, matte cotton.** Velvet responds to the light's *angle*
  (rims), not to its colour.

### 2.5 Test conditions must match the show

- **Exposure.** Capture with no exposure override: "Manual+bias captures ≠ EV100" (memory
  *puss-capture-exposure-convention*).
- **The rig.** The show's own rig at the site, plus coloured spots, a raking key and a strobe peak (section 4).

---

## 3. Recipes

All are create-only: a NEW master or a NEW MI, never an edit to an existing material.

### 3.1 Velvet v2 (house curtain): run the existing builder as written

- **Parent / master:** `M_CurtainVelvet_v2` → `MI_CurtainVelvet_v2_DeepRed`. Pick a variant from the bench.
- **First candidate V2B** [decl: `velvet_v2_bench_variants.json`]:
  - RimLift 0.5, FoldDarken 0.4, NapExponent 2.5, Roughness 0.9;
  - Base 0.045/0.003/0.008, Sheen 0.45/0.06/0.09.
- **To try if V2B reads flat at 14 m** (a new variant row, no graph change):
  - Sheen 0.55/0.10/0.12, a lighter, less saturated sheen than the dye, as on real velvet;
  - CrushAmount 0.5;
  - PileNormalStrength 0.3, which reduces any rim sparkle.

### 3.2 Painted cotton: scenic muslin / cotton duck (backcloths, image curtains, P05 sky)

- **New master `M_CurtainCanvas`.**
  - Default Lit, two-sided, used with Geometry Cache.
  - Default Lit, not Two Sided Foliage: foliage transmission brings VSM subsurface wash-out and a per-light
    transmission flag, and gives glow, not image [decl: `Docs/ScrimFeasibility_2026-09-29.md` "Do not reach for a
    transmission shading model"].
- **BaseColor** = `CanvasColor × lerp(1, ImageRGB × ImageTint, ImageAmount × mask)`.
  - That is dye on cloth: a print multiplies the base. The print is `M_CurtainImage`'s UV mode, i.e. the picture rides
    the folds, which is Gary's "printed, squashed by the pleats" choice.
  - Plus a 0.6–1.2 m low-frequency "paint mottle" on value, ±6%, procedural as in v2's `VV2_Crush`.
- **Roughness** 0.88, **Specular** 0.35.
- **Normal:** one canvas-weave normal at 2–3 cm, strength 0.15. Invisible at 14 m but right in the close shots; it
  costs nothing.
- **Colours** (linear albedo):
  - unbleached muslin 0.60/0.56/0.48;
  - white-primed canvas 0.75/0.74/0.70;
  - P05 sky cotton 0.20/0.38/0.62.
- **Instances:**
  - `MI_CurtainCanvas_Muslin`;
  - `MI_CurtainCanvas_SkyBlue`;
  - per picture curtain, `MI_CurtainCanvas_Image_P01..P05`. These would replace the planned `MI_CurtainImage_P0n`;
    see 3.5.

### 3.3 Wool serge (a heavy, matte, coloured drape; the stage-black standard)

- **Parent:** `M_CurtainVelvet_v2` (no new master), as an MI with the sheen turned almost off:
  - SheenAmount 0.25, RimLift 0.1, FoldDarken 0.85, Roughness 0.95, Specular 0.25, CrushAmount 0.1,
    PileNormalStrength 0.1;
  - Base, for a mid-tone dyed serge, e.g. bottle green 0.04/0.09/0.05;
  - Sheen = base × 2.
- **Why:** it reads heavy and soft, with almost no rim. It is the fabric choice if V2B reads "too plush".
- **Weakness:** at 14 m it is close to the old flat material. It needs the light to model the folds.

### 3.4 Silk satin (P05 sky alternative)

- **New master `M_CurtainSatin`:** Default Lit, two-sided, used with Geometry Cache, **anisotropy** on.
  - The anisotropic path exists in DefaultLitBxDF [decl: :224-267].
  - Anisotropy 0.7 along the warp, UV V = down the drop [decl: `build_curtain_chaos_pattern.py` `build_grid`: v = z/DROP].
  - Roughness 0.32, Specular 0.5, Base 0.03/0.08/0.30.
- **Risks** [inf]:
  - Anisotropy needs good tangents. The Alembic export writes normals and UVs [decl: `bake_curtain_drop.py:765-766`],
    so UE must derive the tangents.
  - Low roughness on dense GeometryCache folds can shimmer (specular aliasing).
  - Bench it at the Opening's stalls distance before anything else.

### 3.5 About `curtain_image.py` (Conductor's file, NEVER RUN)

- Its `M_CurtainImage` is Default Lit with a flat velvet-red base, roughness 0.85 and specular 0.3 [decl:
  `Saved/CodexConductor/curtain_image.py` header, SCALARS/VECTORS :86-97]. That is the "basic" look Gary objected to.
- **Recommendation: before its BUILD is ever run**, give its master the canvas recipe of 3.2:
  - a `CanvasColor` instead of `VelvetColor`;
  - the image multiplied into the base;
  - mottle and weave normal;
  - **default `PlanarMapping` 0 (UV)**, since Gary chose printed (it defaults to 1, planar, today: :88).
- This is cheaper than adding a second master later. The edit is to an unrun script, so no asset is touched.

---

## 4. Bench plan (base: `velvet_v2_bench.py` + `material_bench.py`)

**Prerequisites, each its own MCP call with a run id and a success marker:**
1. `velvet_v2_build.py`: DRY → APPLY → VERIFY. The markers are `VV2_DRY_OK` / `VV2_OK` / `VV2_VERIFY_OK`. Then grep the
   log for "Failed to compile".
2. **A new create-only builder for `M_CurtainCanvas` + `M_CurtainSatin` and their MIs** (3.2, 3.4).
   - Clone `velvet_v2_build.py`'s scaffolding: guards, create-only, edge read-back, save-only-targets.
   - **Not written yet.** About 2 h of agent time [inf].
3. **A wrapper change, as a NEW file `textile_bench.py`** (the velvet one stays as written).
   - An optional `parent` per variant, from an allow-list of the new MIs.
   - An optional `rgb` per light (`light_color`, `use_temperature` false when set).
   - Everything else is `velvet_v2_bench.py`'s code.

**Sites and cameras** (as the existing capture plan):
- **P01:** "Opening — Stalls Camera".
- **P02 / I1:** "Interaction 1 — Stalls Camera" (the mouth lantern at its site).

**Lights.** Each light is one transient `ZZ_` spot, `spot_off` before the next and before cleanup.

| Key | What | Setting (bench actor frame) | Why |
| --- | --- | --- | --- |
| `site` | the show's own lights only | none added | the real look |
| `shadowplay_narrow` | existing | 900 cd, 12°/6°, 3200 K | the I1–I5 shadow play |
| `rake_side` | raking key | 600 cd, 25°/15°, from x -300, y -900, z 450: about 80° off the cloth normal | velvet's rim test |
| `blue_fill` | P05 sky fill | rgb 0.15/0.35/1.0, 400 cd, 40°/30° | the colour-response test |
| `amber` | P01 orange fog flood | rgb 1.0/0.45/0.12, 400 cd, 40°/30° | the warm look |
| `pink` | dim-bulb pink | rgb 1.0/0.6/0.74, 300 cd | the P01 fairy-tale tints |
| `strobe_peak` | P04 strobe at flash peak | 6000 cd white, 50°/40°, frontal | clipping at the flash (a static still = the peak sample) |

- **Exposure:** no override (EV100 as the show).
- **The strobe** is judged as two stills: the peak, and the `site` still (the decay floor). The real strobe's waveform
  is pure Master-time maths [decl: `InfinityStageStrobeLight.h:108-110` `LevelAt`], so the bench needs only its extremes.

**Variants:**
- Velvet: B (control, via `material_bench.py`), V2A, V2B, V2D, plus a "V2F lighter sheen" row (3.1).
- Serge-green (3.3).
- Canvas: Muslin, SkyBlue (3.2).
- Satin: SkyBlue (3.4).

That is 9 variants. At the 2 sites × 7 lights, a full cross is 126 stills, which is too many.

**The cut:**
- **House-curtain set**, at P01: B, V2A, V2B, V2D, V2F, Serge × `site`, `rake_side`, `blue_fill`, `strobe_peak`: 24 stills.
- **Picture/sky set**, at I1: Muslin, SkyBlue cotton, Satin, V2B (for comparison) × `site`, `shadowplay_narrow`,
  `blue_fill`, `amber`, `pink`: 20 stills.
- **Total 44 stills.** About 90 MCP calls: a variant call plus a capture call per still (async decode: capture in its
  own call), plus spot on/off.

**Measured per still** (curtain-mask pixels; offline, from the PNGs):
- p5, p50 and p99 luma;
- **rim ratio** p99/p50, highest for velvet;
- **colour response** = the mean RGB under `blue_fill` / under `site`, which says whether the fabric takes the light's
  colour;
- **clip %** at `strobe_peak`.

The numbers are recorded beside the stills. **Gary picks by eye.**

**After Gary picks:** the assets the new MIs would go on. Nothing is assigned before his answer.

| Curtain | Asset that carries the material today | How to swap without touching shared things |
| --- | --- | --- |
| Opening drop + I1–I5 drapes | `GC_CurtainDrop_Opening` slots → `MI_CurtainVelvet_DeepRed_Drop` (`/Game/Scenes/Curtain/Baked`) [decl: ChaosClothCurtain.md:5-16] | Set the **GeometryCache asset's** `Materials` slots to the chosen MI. `UGeometryCache::Materials` is the asset's own list [decl: `GeometryCache.h:64-65`], so one write reaches all six sites. Do **not** edit or reparent the Drop MI: Rig's `MI_PortalBorder_BlackVelvet` is its child [decl: `Saved/CodexStructure/portal_border_apply.py:8`] |
| P04 backcloth | `GC_CurtainBackcloth_P04` + `MI_CurtainVelvet_DeepRed_Backcloth` [decl: `Saved/CodexSoftGoods/import_passing_bake.py:8-10`] | The GC asset's slot → `MI_CurtainCanvas_Image_P04` (or Muslin) |
| Back-passage curtains P01–P05 | actors "P0n End Drape (stand-in)", plus "P04 Backcloth (baked)" [decl: `curtain_image.py:75-79`] | Per-actor component override, as `curtain_image.py` ASSIGN does (its own backup + record + level-only save) |
| Picture MIs | `MI_CurtainImage_P01..P05` in `/Game/InfinityStage/Curtains/Image` (not built) [decl: `curtain_image.py:65-70`] | Built from the canvas master instead (3.5) |
| P05 blue-sky curtains | the new unfurl cache (`Scripts/patches/2026-10-06_unfurl_bake_mode.patch`) | Its GC asset slot → `MI_CurtainCanvas_SkyBlue` or `MI_CurtainSatin_SkyBlue` on import |

- **Each write:** a `Backups/Pre<Thing>-YYYYMMDD-HHMM` snapshot, exclusive save of the affected packages only, a
  read-back, and the log marker (AGENTS.md).
- **Who approves.** These are look decisions, so they need **Gary's own yes** (memory *puss-gary-word-means-gary*).
