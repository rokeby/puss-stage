# MeshyClean: bulbs and stage-light housings (6 Oct 2026)

Offline cleanup of the 13 Meshy exports in `../Meshy/<uuid>/`. The spec is
`Docs/Conductor/MESHY_PROMPTS_BULB_HOUSING_2026-10-06.md` ("After Meshy"). The cleanup was built headless in Blender 4.4 by
`Tools/MeshyFixtures/build_meshy_fixtures.py`, and the sheet and report come from `compose_contact_sheet.py`. Nothing here
has been imported into Unreal yet.

- `<Asset>/<Asset>.fbx`: the mesh. `<Asset>/T_<Asset>_{BaseColor,Normal,Roughness,Metallic}.png` are Meshy's maps,
  copied and renamed. `<Asset>/<Asset>_record.json` is the per-asset record.
- `cleanup_report.json` holds every record, including heuristics, evidence, warnings and the FBX re-import read-back.
- `contact_sheet.png` gives two views per asset: textured, and a slot map with pivot axes. The red bar is 10 cm.

## What the FBXs contain

| | Bulbs (7) | Housings (6) |
| --- | --- | --- |
| Units / axes | cm in UE (`UnitScaleFactor` 100), Z up | same |
| Pivot | tip of the screw cap; glass hangs in -Z | tilt axis of the yoke (heuristic); beam +X, clamp +Z |
| Slot 0 | `M_<A>_Glow`: synthetic filament (clear) or the whole glass (Frost, Opal) | `M_<A>_Lens` |
| Slot 1 | `M_<A>_Metal`: cap, plus support wires | `M_<A>_Metal`: body, yoke, clamp |
| Slot 2 | `M_<A>_Glass`: clear shell (clear bulbs only) | none |
| Tris | 2,735–2,890 (budget 3k) | LOD0 11,348 (budget 12k), LOD1 2,860 (budget 3k) |
| LODs | 1, no LodGroup | FBX `LodGroup` empty with `<A>_LOD0` and `<A>_LOD1` (the Flat V3 pattern) |
| UV0 | Meshy's own atlas UVs, kept (no V flip) | same |

## Import settings for the conductor (the same pattern as `Saved/CodexFlatV3/fence/fb_workflow.py:233-275`)

- `AssetImportTask`: `automated=True`, `replace_existing=False` (create-only), `save=False` until the gates pass.
- `FbxImportUI`: `import_mesh=True`, `import_as_skeletal=False`, `import_materials=False`, `import_textures=False`,
  `import_animations=False`. In `static_mesh_import_data`, set `combine_meshes=False`, plus `import_mesh_lods=True`
  for housings.
  Interchange **ignores** these options (memory `ue58-fbx-import-traps`). Set them anyway, then **diff the destination
  folder before and after**, and delete any stray material or texture assets that were never saved.
- Import the textures as separate tasks. Use `T_*_Normal` as a normal map, and `T_*_Roughness` / `T_*_Metallic` as
  linear (`LINEAR_GRAYSCALE`, sRGB off).
- Destinations: bulbs go to `/Game/InfinityStage/Lighting/Bulbs`, housings to `/Game/InfinityStage/RigAtmos/Lanterns`.
- Nanite off. Call `modify()` before every setter, then read each value back.

## Gates to run after import (read back, never assume)

1. **LODs:** bulbs `get_num_lods()==1`. Housings `==2`, with no stray `*_LOD0` / `*_LOD1` / `*_LODGroup` assets.
2. **Bounds:** `get_bounding_box()` size must match `final_size_cm` in the record within 0.2 cm, with X/Y/Z in the same
   order. If not, fix the export. Never rotate in UE.
3. **Slots:** `static_materials` order is Glow/Lens first. Expect 3 slots on clear bulbs and 2 on the rest.
4. **Beam sign (housings): UNCLEAR until measured.** The Underpass gate only proved that the extents keep their axes,
   not the sign of X. Read the section bounds of slot 0 (the lens), or take one capture. The lens centroid must be at
   +X, near `classification.lens_centroid_cm` (for example, Fresnel +14.7 cm). If it comes out at -X, re-export. Do not
   rotate in UE.
5. **UV V:** the textured look must match `contact_sheet.png`. The maps were baked for Meshy's UVs, and the exporter
   keeps them. The wing rule that "V runs down" is about planar-projected wings, not baked atlases.

## Needs a human (see `warnings` in the report)

- **Clear bulbs (A60_Clear, A60_Worn, C35, G95, ST64):** the slot-0 filament is **synthetic**. Meshy only painted the
  filament, or, for A60_Clear and ST64, built the stem and filament **outside** the glass; that geometry was deleted.
  Meshy's painted filament stays in the glass base colour. A translucent glass MI will show both.
- **G95_Clear:** the spec says the globe glass belongs in slot 0, but the bulb is clear. It was built as a clear bulb
  (filament in slot 0, glass in slot 2). Gary or the conductor should choose.
- **Birdie and 1950s:** both ends carry a lens-like disc. The front was chosen by texel luminance and needs a look.
- **Profile:** the lens is painted dark, so it was picked on geometry alone (a 9.6 cm disc in the barrel mouth).
- **ParCan:** the lens/face is 19.3 cm, against the prompt's 22 cm can (-12 %). The length matches at 40 cm.
- **Pivots** are heuristic: the most lateral vertices on each side. The axes on the contact sheet show where they
  landed.
