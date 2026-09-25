# Wing generation conventions

## Current production FBX profile

All newly generated PussStage production Wings use this V2 profile. The
deterministic cutout pipeline still has a **legacy 5 cm default**, so every new
production manifest or command must state the V2 values explicitly instead of
relying on defaults:

- Source height `2.0 m`, `ue_panel_scale: 5.0`, final height `10.0 m`.
- Finished thickness `10.0 cm` (`--thickness-cm 10`); clean re-import depth is
  `0.10 m` on X.
- Baked physical yaw `90 degrees`; Unreal FBX import uses identity rotation and
  scale. A right-side actor may still need a 180-degree stage-up rotation to
  face the passage, which is not an image flip.
- Exactly one photographic UV channel named `UVMap` and exactly three material
  slots named Front, Back and Edge for that asset.
- One registered texture set produced only after orientation approval:
  sRGB Base Color with alpha, `<asset>_H.png` linear grayscale height,
  `<asset>_N.png` tangent-space DirectX normal, and
  `<asset>_relief-preview.png` for inspection. A separate authored roughness
  map is optional; otherwise start the shared relief material at Roughness
  `0.72` and Specular `0.25`.
- Generate height/normal/preview textures with
  `Tools/StageOpening/generate_relief_maps.py`. The current restrained
  production starting point is normal strength `4.5`; tune only with an
  explicit art-direction reason and record the value.
- In Unreal, keep the opacity mask on unshifted source UVs. Use the height map
  for Bump Offset (starting Height Ratio `0.004`, Reference Plane `0.50`) and
  sample Base Color and Normal with the offset UVs. This prevents the silhouette
  from swimming.

Required validation for every delivered FBX:

1. `wing_pipeline_report.json` records `status: ok`, `thickness_cm: 10.0`,
   `ue_yaw_deg: 90.0`, the intended scale/height and nonzero geometry.
2. A factory-clean FBX re-import passes `validate_fbx.py` with applied
   transforms, `0.10 m` depth, one `UVMap`, and Front/Back/Edge slots.
3. Base, alpha, height and normal maps have identical dimensions and final
   handedness, and the relief preview has been inspected.
4. The L/R pair passes the acceptance check below. `_C` assets are restricted
   to Top palettes and receive an explicit overhead placement review.

Do not retroactively rebuild or reinterpret legacy 5 cm FBXs merely because the
current profile changed. Flag them as legacy and migrate only with explicit
scope and artist acceptance.

## Left/right image handedness

New paired wing art must be delivered in its final implemented image handedness before texture, normal-map or FBX generation:

- `*_L`: the exterior/backbone edge is on the image's left; the inward-facing or projecting edge points right, toward the passage.
- `*_R`: the exterior/backbone edge is on the image's right; the inward-facing or projecting edge points left, toward the passage.

Left and Right should remain independently designed rather than becoming mirrors, but each member must obey its final side orientation. Review the two images together with the passage centre between them. Do not rely on the Infinity Stage **Flip Image Horizontally** control to repair newly generated sources.

For a generated Left source that arrives backwards, flip it horizontally exactly once **before** creating its derived textures, normal map or mesh. Keep the corrected asset under the canonical `*_L` name and retain any rejected draft separately. Never flip a corrected source again during Unreal placement.

Legacy assets may retain an explicit per-occurrence image-flip setting. Do not bulk rewrite or unmirror existing Show data without a paired preview and artist approval.

## Handedness versus mesh facing

Image handedness and mesh facing are separate:

- A horizontal image flip changes photographic/architectural handedness.
- `ue_yaw_deg` or a 180-degree stage-up actor rotation changes which physical face points into the passage.
- Left/Right route assignment changes placement only.

Do not use FBX yaw to correct image handedness, and do not use image mirroring to correct front/back facing.

## Texture and normal-map order

Resolve and approve handedness first, then generate Base Color, alpha, Roughness and tangent-space normal textures from the oriented source. This keeps all maps registered and avoids a late normal-map correction.

If an already-generated tangent-space normal map must be horizontally flipped, flip the map and invert its red/X channel. Prefer regenerating the normal map from the corrected source instead.

## Pair acceptance check

Before FBX generation or Unreal assignment, verify:

1. The `*_L` exterior edge is left and its inward edge is right.
2. The `*_R` exterior edge is right and its inward edge is left.
3. The pair is intentionally varied, not accidentally mirrored.
4. Base Color, alpha and all PBR maps share identical dimensions and orientation.
5. No new asset depends on an Unreal image-flip flag for correct presentation.
6. The intended Front material can face the passage without changing image handedness.
