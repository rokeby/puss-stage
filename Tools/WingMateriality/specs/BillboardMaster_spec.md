# Spec for Codex: `build_billboard_master.py` (Flat V3 billboard skin)

Author: Wing materiality (Claude), 2026-10-01. Contract source:
`Docs/FlatV3Spec_2026-09-30.md` at 7f88cae ("Texture rules", "Built for movement").
Codex writes the code; Claude reviews it and runs it in Unreal. **Codex must not run
Unreal or any MCP call.**

## Deliverables (in a `--worktree`)

1. `Saved/CodexWingMateriality/build_billboard_master.py`: builds or rebuilds
   `/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master` plus two MIs,
   `MI_Billboard_Front` (Flutter off) and `MI_Billboard_Flap` (Flutter on, two-sided override).
2. `Tools/WingMateriality/generate_billboard_placeholders.py`: writes three tiny PNG
   placeholders to `DerivedAssets/WingMateriality/BillboardPlaceholders/`, so the master
   has sampler-compatible defaults before the real SkinTest maps arrive:
   `T_BB_Colour.png` (sRGB mid grey), `T_BB_Mask.png` (linear RGBA R=0 G=0.5 B=0.5 A=0),
   `T_BB_Normal.png` (flat 128,128,255). 64×64, power of two.
   The builder imports them with the right compression (Colour: TC_Default, sRGB;
   Mask: TC_Masks or TC_BC7 with sRGB OFF; Normal: TC_NormalMap), with mips ON
   (`TMGS_FromTextureGroup`), into `/Game/Scenes/Wings/PaintedSurface/Billboard/Textures`.

## Reference implementation: copy its patterns exactly

`Saved/CodexWingMateriality/build_kit_surface_master.py` (and the helpers it imports from
`build_painted_surface_master.py` with `WM_IMPORT_ONLY = True`): `Graph`, `get_or_create`,
`custom()`, `link()`, `prop()`, `scalar()`, `vector()`, F1/F2/F3, SHARED sampler source,
a `main()` guarded by `WM_IMPORT_ONLY`, the dirty-set invariant, and the explicit usage flags.

## Traps (each caused a real failure in this project; the draft must avoid all)

1. **Never delete material expressions** except through `get_or_create`, which refuses
   outside `/Game/Scenes/Wings/PaintedSurface`. Deleting on a rooted asset hard-crashes the
   editor (`!IsRooted()`).
2. **Sampler types must match the textures**: linear grayscale needs LINEAR_GRAYSCALE, the
   linear RGBA mask needs LINEAR_COLOR or MASKS (match the compression you import with),
   and normals need NORMAL. A mismatch fails compile silently and cascades. Copy `sampler_for()`
   from the kit builder.
3. Clear-coat pins aren't exposed. This master doesn't need clear coat, so use
   **DefaultLit through MakeMaterialAttributes** (`use_material_attributes=True`) as in the kit master.
4. Custom-node HLSL: **don't name variables `half`, `Texture`, `Tangent`**, or any HLSL
   keyword or type. CustomInput/CustomOutput structs reject kwargs, so use the `struct()` helper.
5. **`set_material_instance_texture_parameter_value` can return False on success**, so
   verify by reading the value back.
6. Single-input nodes (TransformPosition, Transform, ComponentMask) connect with pin `""`.
   TextureSample's texture-object pin is `"Tex"`.
7. The saves must add nothing to the dirty set beyond the script's own packages
   (`set(after) <= before_others`).

## The master

Material: Opaque, DefaultLit, `two_sided=False`, `use_material_attributes=True`,
`used_with_instanced_static_meshes=True`, `used_with_nanite=True`. Set
`max_world_position_offset_displacement` to `FlutterMaxCm` (default 6) if that property
exists in this build; try/except, and record whether it was set.

Coordinates:
- UV0 = photographic.
- **UV1 = metres** on the front, used for the sheet grid, halftone and fibre.
- Panel cm = UV1 × 100.

Texture parameters, all UV0, shared sampler source:
- `SkinColor`: sRGB colour.
- `SkinMask`: linear RGBA. **R** = peel amount (0 intact → 1 fully peeled), **G** = paper
  height, **B** = roughness, **A** = paste-soak gloss.
- `SkinNormal`: BC5.

Sheet grid, in a custom HLSL node using UV1 metres:
- Scalars: `SheetWidthM` 1.0, `SheetHeightM` 1.5, `SheetOverlapM` 0.025, `RowOffset` 0.5.
- `row = floor(uv1.y / SheetHeightM)`; `cell = floor((uv1.x + RowOffset*row*SheetWidthM) / SheetWidthM)`.
- Hash the (cell, row) pair to [0,1).
- Pick the under-layer per sheet: hash < `PBacking` (0.45) gives white backing
  `BackingColor` (0.80, 0.78, 0.72); < `PBacking + POlder` (0.35) gives "older poster",
  i.e. SkinColor sampled at UV0 + (hash*0.37, hash*0.61), desaturated 50% and faded 30%;
  otherwise primer `PrimerColor` (0.42, 0.42, 0.40).
- **Do NOT store layer IDs in a texture.** The under-layer comes only from the hash.

Peel composite:
- `t = smoothstep(PeelLo 0.35, PeelHi 0.65, R)`; colour = lerp(skin, under, t).
- Darken where the peel edge curls: `edge = saturate(abs(ddx(R)) + abs(ddy(R))) * PeelEdgeDark (2.0)`,
  multiply colour by `(1 - 0.35*edge)`.
- Sheet seams: a thin darker line at each sheet border in UV1 (width = `SheetOverlapM`),
  strength `SeamDark` 0.12.

Procedural halftone (no texture):
- Dot grid in panel cm, pitch `HalftonePitchMm` 4.5, rotated 15°.
- Dot radius from skin luminance (darker = bigger dot).
- `HalftoneStrength` 0.12 modulates colour.
- **Fade by pixel footprint so it can never shimmer**:
  `fw = length(fwidth(panelCm)) / (HalftonePitchMm*0.1)`, `fade = 1 - smoothstep(0.25, 0.5, fw)`.

Procedural paper fibre (no texture):
- Value-noise from hashes at about 2 mm in panel cm, anisotropic 3:1 along X.
- It affects roughness (±0.05) and albedo (±3%).
- Faded by the same footprint rule at its own scale.

Roughness: `lerp(RoughMin 0.40, RoughMax 0.55, B) - A*PasteGloss 0.15 + fibre`, saturated.

Normal: SkinNormal, scaled by `NormalStrength` 1.0 and blended (whiteout) with a faint
fibre normal from the same noise (gradient via ddx/ddy, strength `FibreNormal` 0.15, faded).
Tangent-space output (`tangent_space_normal=True`; the front is a planar UV0 card).

Variation:
- seed = PerInstanceCustomData[3] if ≥ 0, else PerInstanceRandom (copy from the painted master).
- Tint ±`TintVar` 0.04 between `TintWarm`/`TintCool`, and age fade ±`FadeVar` 0.06 toward a
  desaturated, lighter value.

Burn (port it from the painted master's CODE_PAINT burn block **verbatim**; it is a contract
with Effects sources):
- Static switch `UseBurn` (default False), `BurnPreview`, PerInstanceCustomData[0..2] with
  defaults 0 / 0.5 / 1.0, the (0,0) ignition sentinel → bottom centre, and `UVSpanUCm`/`UVSpanVCm`.
- Pad = Irregularity/2 + 1.25×Edge, with **Edge 40, Irregularity 160 coupled to Effects'
  FrontPadCm 130**.
- Output OpacityMask = 1 − hole. The master is opaque, so it's ignored there; an MI with a
  BlendMode Masked override uses it.

Flutter (Flap slot): static switch `Flutter` (default False). When True:
- WPO = local-space displacement along local −X (the front faces −X),
  `VC.R * FlutterAmpCm (3) * (sin(t*FlutterHz(0.7)*2π + phase) * 0.7 + gust*0.3)`.
- phase = seed*6.28 + dot(localPos, (0.013, 0.021, 0.017)).
- gust = a slow noise on time: sum two sines at 0.13 Hz and 0.31 Hz.
- Transform the local vector to world (TransformVector local→world).
- When False, the WPO pin is **left unconnected** (not a constant 0), so Front MIs never
  carry WPO.
Velocity: rely on `r.Velocity.EnableVertexDeformation` = 2 (the project value). Do NOT
change cvars.

## MIs

- `MI_Billboard_Front`: parent master, Flutter False.
- `MI_Billboard_Flap`: parent master, Flutter True, base-property override two_sided True.
  Set it through `base_property_overrides` and read it back.

## Falsifiable checks, before handing back (no Unreal)

- `python -c "import ast; ast.parse(open(...).read())"` on both files.
- `grep -n "delete_material_expression" build_billboard_master.py` must return
  NOTHING (deletion only via the imported get_or_create).
- grep shows the master path under `/Game/Scenes/Wings/PaintedSurface/Billboard`,
  `used_with_instanced_static_meshes`, `used_with_nanite`, `BLEND_OPAQUE`, and a
  `WM_IMPORT_ONLY` guard.
- grep the HLSL strings for the forbidden variable names in trap 4 and print
  the result (must be empty).
- Run the placeholder generator and print the three PNG sizes and modes.

Return a summary of what was built, the checks' output, and any property you couldn't
find or confirm (e.g. `max_world_position_offset_displacement`).
