# Stage Wing Cutout Pipeline

Turns transparent PNG photographs into Unreal-ready FBX stage wings. The tool's
5 cm thickness default is retained for legacy compatibility. New PussStage
production Wings must explicitly use the 10 cm V2 profile documented in
[`Docs/WingGenerationConventions.md`](../../Docs/WingGenerationConventions.md).

The pipeline runs entirely through Blender Python. It does not require Illustrator,
Potrace, ImageMagick, or third-party Python packages.

## What it creates

For `Tree.png`, the output is:

```text
GeneratedWings/
  Tree/
    SM_Tree.fbx
    SM_Tree.blend
    Textures/
      Tree.png
  wing_pipeline_report.json
```

The mesh is vertical, Z-up, centred at the bottom of its silhouette, and centred
through its 5 cm depth. By default, the pipeline also bakes the project placement
correction into the mesh: Z rotation +90 degrees and 5x scale across panel width
and height, with thickness left at 5 cm. Imported UE5 actors can therefore remain
at rotation `(0, 0, 0)` and scale `(1, 1, 1)`. The FBX has three material slots:

- `M_<name>_Front`
- `M_<name>_Back`
- `M_<name>_Edge`

Each saved `.blend` also retains a hidden `SRC_<name>_Curve` object. Unhide it to
edit the traced path or extrusion non-destructively; the FBX contains only the mesh.

Front and back UVs map directly to the original PNG. Fine transparent gaps remain
available through the PNG alpha; the traced silhouette supplies the physical outer
shape and larger holes.

The FBX intentionally contains exactly one UV channel. It is the photographic
projection Unreal materials read as UV channel 0.

## One image

From the Unreal project root:

```bash
python3 Tools/WingCutoutPipeline/run_wing_pipeline.py \
  --input DerivedAssets/IMG_6250-stage-wing-transparent-v3.png \
  --output-dir DerivedAssets/GeneratedWings \
  --height-m 6.5
```

Height must be between 2 and 8 metres. Thickness defaults to 5 cm.

For a current production Wing, do not use that legacy thickness default. Use a
manifest or command that explicitly includes:

```bash
--height-m 2 --thickness-cm 10 --ue-panel-scale 5 --ue-yaw-deg 90
```

This produces the verified V2 handoff scale: 10 m final height and 10 cm final
depth. After orientation is final, also generate the registered `_H.png` height
map, `_N.png` normal map and relief preview with
`Tools/StageOpening/generate_relief_maps.py`, then clean-reimport and validate
each FBX before delivery.

## A folder of images

```bash
python3 Tools/WingCutoutPipeline/run_wing_pipeline.py \
  --input-dir DerivedAssets/WingPNGs \
  --output-dir DerivedAssets/GeneratedWings \
  --height-m 6
```

All PNGs receive the default height unless a manifest overrides them:

```bash
python3 Tools/WingCutoutPipeline/run_wing_pipeline.py \
  --input-dir DerivedAssets/WingPNGs \
  --output-dir DerivedAssets/GeneratedWings \
  --manifest Tools/WingCutoutPipeline/wing_manifest.example.json
```

## Useful controls

- `--alpha-threshold 0.5`: opaque/transparent cutoff used for geometry.
- `--trace-max-size 1024`: contour working resolution. Higher preserves more detail.
- `--simplify-px 1.5`: contour simplification tolerance at tracing resolution.
- `--islands largest`: keeps the largest connected shape, appropriate for a physical panel.
- `--islands all`: keeps all islands larger than `--min-island-px`.
- `--thickness-cm 5`: finished total thickness.
- `--ue-panel-scale 5`: bake 5x into width and height without scaling thickness.
- `--ue-yaw-deg 90`: bake the UE-facing Z-axis orientation into the mesh.
- `--no-save-blend`: export FBX without retaining the Blender source.

For noisy photographic masks, raise `--simplify-px` to 2–4. For architectural
edges, lower it toward 0.5–1.0. Increasing `--trace-max-size` raises both fidelity
and polygon count.

## Left/right orientation

Resolve image handedness before running this pipeline. Follow
[`Docs/WingGenerationConventions.md`](../../Docs/WingGenerationConventions.md):
`*_L` sources arrive with their exterior/backbone edge on the image left and
their inward edge pointing right; `*_R` sources use the opposite arrangement.
Review the pair together before generating derived textures or FBXs.

`--ue-yaw-deg` bakes physical mesh facing only. It does not repair photographic
handedness. Newly generated assets must not depend on Unreal's horizontal image
flip. If a source needs correction, flip it once before producing Base Color,
alpha, Roughness and normal textures. Never silently mirror legacy or neutral
assets.

## Unreal import

The PNG is embedded in the FBX and also copied into the asset's `Textures`
folder. Unreal can import the embedded image when **Import Textures** is enabled;
the copied PNG remains available for reliable manual material setup:

```text
PNG RGB   -> Base Color
PNG Alpha -> Opacity Mask
Blend Mode = Masked
```

Assign the masked material to the Front and Back slots. Assign an opaque dark or
painted material to Edge. Unreal's FBX importer does not reliably reproduce a
Blender node material, so the Blender materials are intended primarily as named
slots and previews.

## Validate an exported FBX

For a clean re-import test through Blender 5.1.2:

```bash
"/Applications/Blender v5-2.app/Contents/MacOS/Blender" \
  --background --factory-startup \
  --python Tools/WingCutoutPipeline/validate_fbx.py -- \
  --fbx DerivedAssets/GeneratedWings/Tree/SM_Tree.fbx \
  --height-m 6.5 --panel-scale 5 --thickness-axis x
```

The validator checks dimensions, UVs, material slots, vertices, and polygons after
fresh FBX import.

## Current limitation

`--islands largest` intentionally discards disconnected alpha specks because they
cannot form one physical scenic panel. Use `--islands all` only when separate
floating pieces are intentional. Every filled polygon is triangulated by Blender
and FBX, but tracing resolution and simplification keep that triangulation bounded.
