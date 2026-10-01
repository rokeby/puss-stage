# Flat V3 P02 pilot import plan

Target root: `/Game/Scenes/Wings/FlatV3/Pilot/`

This is a plan only. No Unreal operation has been run. Every destination name below is new; do not overwrite or rename an existing asset. Import into these new subfolders:

- `StaticMeshes/`
- `Textures/L/`, `Textures/R/`
- `Textures/Aged/Common/`, `Textures/Aged/L/`, `Textures/Aged/R/`
- `Materials/Instances/`

## Static meshes

Import `SM_FlatV3_P02_RuisdaelA_L.fbx` and `SM_FlatV3_P02_RuisdaelA_R.fbx` with:

- asset names unchanged;
- Static Mesh on; Skeletal Mesh off;
- Import Mesh LODs on; Combine Meshes off;
- Import Materials off; Import Textures off;
- Import Uniform Scale `1.0`; Translation `(0,0,0)`; Rotation `(0,0,0)`;
- Convert Scene on; Force Front XAxis off; Bake Pivot in Vertex off;
- Normal Import Method `Import Normals and Tangents`;
- Vertex Color Import Option `Replace`;
- Generate Lightmap UVs off (UV channel 1 is the required metre-space UV1 and must not be replaced);
- Generate Missing Collision off; Nanite off for this pilot;
- preserve FBX material order: `Front`, `Flap`, `Timber`, `Edge`.

The expected result is one Static Mesh per FBX with LOD0 and LOD1. LOD1 must contain the board only. If the importer offers `_LOD0` and `_LOD1` as separate assets instead, stop: this Blender package proves the FBX contents but not the Unreal importer's LOD assembly.

Import `SM_FlatV3_Pole.fbx` with the same settings except Import Mesh LODs off. The pole is a one-metre modular shared mesh and has no LOD1 or sockets by design.

After import, verify before saving:

- L/R height `1000 cm`, scale `(1,1,1)`, origin at floor/backbone/pole-line contract, Front normals toward `-X`;
- four slots in the exact order above;
- UV channels 0 and 1; UV1 is not regenerated;
- LOD1 switches beyond approximately 15 m and has no frame, hardware or flaps;
- `SOCKET_Hinge`, `SOCKET_Pivot`, `SOCKET_Pole_1`, `SOCKET_Pole_2` exist on each flat;
- vertex colour import survived: Flap R `0..1`; Timber R `0/0.5/1`; Timber G varying by member.

## Textures

Import each side's three `T_P02_RuisdaelA_[L|R]_Skin*.png` files into its side folder with these exact settings:

| Suffix | sRGB | Compression Settings | Flip Green Channel |
| --- | --- | --- | --- |
| `_SkinColor` | on | Default | off |
| `_SkinMask` | off | Masks (`TC_Masks`) | off |
| `_SkinNormal` | off | Normalmap | off |

The SkinMask file channels are R continuous peel amount, G paper height, B roughness, A paste-soak gloss/AO. Do not split or reinterpret them. There is no halftone texture; halftone and paper fibre remain procedural in the parent material.

The aged sets under `Aged/L/` and `Aged/R/` retain source-family filenames. Route the identical shared softwood, steel, roughness and normal files from `Aged/L/` to `Textures/Aged/Common/` only once. Route each side's non-identical `T_FlatV3_AgedPlywood_Stencil_Color.png` to `Textures/Aged/L/` or `Textures/Aged/R/`. Settings:

| Aged map | sRGB | Compression Settings | Flip Green Channel |
| --- | --- | --- | --- |
| `*_Color` | on | Default | off |
| `*_Roughness` | off | Masks (`TC_Masks`) | off |
| `*_NormalDX` | off | Normalmap | off |

## New material instances

Create these new instances:

- `MI_FlatV3_P02_RuisdaelA_L_Front`, parent `/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front`;
- `MI_FlatV3_P02_RuisdaelA_L_Flap`, parent `/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap`;
- `MI_FlatV3_P02_RuisdaelA_R_Front`, same Front parent;
- `MI_FlatV3_P02_RuisdaelA_R_Flap`, same Flap parent.

For each side, assign its `SkinColor`, `SkinMask`, and `SkinNormal`; set `SheetWidthM=1.0`, `SheetHeightM=1.5`, `SheetOverlapM=0.025`, `RowOffset=0.5`. The same values are recorded in each `P02_RuisdaelA_[L|R]_mi_params.json`.

Assign those instances only to Front and Flap. The specification says Timber and Edge masters follow after `library.json`; their parent paths are not yet declared. Do not invent or overwrite a parent. Keep Timber/Edge assignment as an explicit Unreal-integration hold until that stream supplies the two masters.

## Evidence boundary

- **Declared:** parent paths, parameter names, `TC_Masks`, and the procedural halftone rule come from `Docs/FlatV3Spec_2026-09-30.md:264-280`.
- **Measured:** the packaged FBXs passed Blender 4.4 factory-startup re-import; the JSON results are beside the meshes.
- **Inferred / not yet accepted:** the Unreal importer settings above are the intended zero-adjustment route. Unreal import, material compilation, distance switching, venue lighting and rendered stage acceptance remain open because this run explicitly excluded Unreal.

## MANDATORY post-import handedness check (reviewer, 1 Oct)

Blender's renders show the L flat MIRRORED relative to the A2 art (the big
lobe and the dead snag are swapped left/right). This may be only the viewing
convention: Blender is right-handed, so looking along +X, +Y is on screen LEFT,
while in Unreal +Y is on the RIGHT. The FBX importer's Y negation may restore it,
or it may send L outward. The exporter uses `axis_forward="-X"`, unlike the old
pipeline's `-Y`. This is NOT verified. Before ANY placement, read back in Unreal:
1. the bounds of `SM_FlatV3_P02_RuisdaelA_L`: its Y extent must be >= 0 (it
   extends +Y, inward); R must be <= 0;
2. Front face normals point -X;
3. art handedness: a capture of L from -X looking +X (Unreal) must match the A2
   art unmirrored: the big lobe upper RIGHT, the dead snag upper left of centre.
Any failure: STOP, don't place, fix the exporter. Never use the image-flip flag
or a 180-degree rotation (spec: zero adjustment).
