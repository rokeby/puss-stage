# P17: P03 bone dune + new Rodin bones (Gary 8 Oct, own words)
Gary: "something that would be nice for passage three. Once the curtain bake is done, is simply a mound of sand, a kind of believably tall dune of sand with some of our rendered bones in it and you could ask Rodin to make a few more different kinds of bones."
Existing:
- Hyper3D bones HominidJaw, HominidLegBone and HominidRibcage, imported to UE 8 Oct via Saved/CodexConductor/S3Millstone/s3_props_ue.py (see Saved/CodexConductor/conductor_helpers/bones_import.sh; sources under DerivedAssets/).
- The S3 shore sand field tools in Saved/CodexConductor/S3Shore/ (dune shaping, ripple realism, set D from P3 tonight) and the sand material used on SM_S3_ShoreGround.
- Rodin API facts: read the memory text copied below. The key is in Blender's add-on prefs (bpy.context.preferences.addons["blender_mcp_addon"].preferences.hyper3d_api_key); read it from a HEADLESS `blender -b --python` script only. NEVER print, log or write the key anywhere.
Rodin facts (7 Oct, measured):
- POST https://api.hyper3d.com/api/v2/rodin directly, multipart form.
- bbox_condition is JSON text "[w,HEIGHT,l]".
- addons and image_label are REPEATED form fields.
- A 400 is not charged; never auto-retry a POST.
- Extreme-High texture goes "visceral" (Gary). Use tier Gen-2.5-High (or the non-extreme texture) for calmer surfaces.
- Cost ~0.5-3 credits per job.
- Results: base_high_pbr.glb.
EXCEPTION to house rule 2: you MAY run headless Blender (`blender -b`, ONE process at a time, never the GUI). A production curtain bake (unfurl_sleight_b1hop10_p02) is running headless; check `tasklist` for blender.exe count and memory, and keep your Blender work small. You may make up to 6 Rodin generations.
Job:
1. **Bones:** 4-6 new bone kinds that sit with the existing three: skull/cranium, pelvis, scapula, vertebra chain, long femur, finger/hand bones. Text prompts, aged and sand-stained, believable scale bbox. Download, decimate to <=150k tris with a baked texture set (BaseColor/N/Roughness, 4K max), and export FBX + textures under DerivedAssets/P03Bones/<Name>/ in the same layout as the existing bone imports, so s3_props_ue.py-style IMPORT_MESH/IMPORT_TEX works. Note the poly and texture sizes.
2. **Dune:** a believably tall sand mound (default 3.5 m high, ~8x6 m footprint; args), wind-shaped with a steep lee face, ripples, and slump at the toe. Bones half-buried in it (placement JSON: bone, transform, burial depth), deterministic seed. Export FBX with UVs for the S3 sand material (or a baked height/normal) under DerivedAssets/P03Dune/. Add relief preview PNGs (top + 3/4).
3. **Placement proposal for P03:** which bay or gap. Read P03's wing layout from Saved/ records or the Show census JSONs; P03 is the pyre/fire passage. Make it a DRY/APPLY/REVERT tool that adds the dune + bones as Show attachments (kind PROP or a static-mesh attachment; copy fx_smoke_place.py's pattern) at a station anchor. The conductor applies it after Gary sees the previews.
Deliver Docs/Conductor/P17_P03_BONE_DUNE_2026-10-08.md, with Rodin task ids and credits used.
