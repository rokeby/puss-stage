# PG4 — Gobo flipbooks with signed-distance-field edges (offline)

Read `_house_rules.md`. Offline only. Do not edit `Saved/CodexConductor/animated_gobo.py` (no material change is
needed: its Edge node already does `smoothstep(0.5 - Softness, 0.5 + Softness, mix(R, G, def))`).

## Why (Gary 9 Oct, "they all seem to have a low resolution, quite rough edge")
Measured offline by the gobo session (`Tools/ShadowGobo/sdf_edge_prototype.py`, images in
`Tools/ShadowGobo/Puppets/sdf_proto/`, by eye at real curtain magnification):
- hard-edge cells at 409 px (the current real-time clip at 4096) = wobbly, bumpy edges;
- hard edge at 819 px = crisp, faint stepping at fine tips;
- SDF at 819 px with Softness 0.02 = crisp AND smooth; Defocus then blurs coherently (both channels cross 0.5 at
  the same edge);
- SDF at 409 px = still too soft; thin slit tips break into dashes -> 409 is too small even with SDF.
The prototype's `cell_sdf()` is the reference: R = 0.5 + sd/(2*spread), G = same with spread x4, sd = signed
distance (positive in LIGHT) computed at HIGH resolution and bilinearly downsampled, in cell px.

## Build
1. `pack_rig_flipbook.py --sdf` (keep the hard mode as default for old clips): frames must be rendered at >= 2x the
   cell's inner size; compute the SDF at that resolution (scipy.ndimage.distance_transform_edt), downsample, encode
   R/G as above (args `--spread`, `--wide`); gutters edge-replicated as now; manifest `atlas.channels` records the
   encoding, and `light_function_params` carries `Softness: 0.02` for SDF atlases (plan_from_args takes supplied
   params from the manifest).
2. `clip_render.py` / `build_realtime_puppet_clips.py`: a `--render-scale` (default 2) so frames are rendered at
   2x cell size when `--sdf` is used.
3. Repack the boy real-time rub clip (`clip_rub_rt` beats) at **8192, --sdf** into `Tools/ShadowGobo/Puppets/clip_rub_rt_sdf/`
   (commit atlas, manifest, contact, twin GIF, and a zoom comparison like `sdf_proto/edge_zoom_tuned.png` against
   the current `clip_rub_rt` atlas).
4. Thin features: rods and fine slits must survive. Report the minimum feature width in cell px for the boy (rod,
   narrowest slit) and check it stays >= 2 px at 8192 for ~200 cells per atlas (I1-I5 estimate in
   `Docs/Conductor/SHADOW_PUPPET_PLAN_I1_I5.md`).

## Harness (+/-)
SDF crosses 0.5 exactly on the silhouette edge of a synthetic disc (within 0.5 px) (+); R and G share the edge (+);
a frame rendered at 1x (below the 2x rule) is refused in --sdf mode (-); hard mode output unchanged byte-for-byte
for the existing test frames (+, regression); thin-line synthetic frame keeps a continuous 0.5 contour at 2 px (+) and
a 0.5 px line fails a min-width warning (-).

## Deliver (rule 8)
Paths, commit (or file list if your sandbox cannot commit), run order, harness counts, the zoom comparison path,
minimum feature widths, questions.
