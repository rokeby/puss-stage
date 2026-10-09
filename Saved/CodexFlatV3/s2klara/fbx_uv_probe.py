# Headless Blender, read-only: UV bounds per material slot of Klara's S2 wing FBX sources.
import bpy, json
A = "D:/PussStageArchive/Keep-20261003/Klara Scenes WIP/2. Old Man and Shrine/Assets/"
out = {}
for f in ["SM_S2_L_Wing_Shrine.fbx", "SM_S2_R_Wing_Shrine.fbx", "SM_S2_ceiling_wing.fbx"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=A + f)
    o = [x for x in bpy.context.scene.objects if x.type == "MESH"][0]
    me = o.data; uv = me.uv_layers[0].data
    per = {}
    for p in me.polygons:
        nm = me.materials[p.material_index].name
        n = (p.normal.x, p.normal.y, p.normal.z)
        for li in p.loop_indices:
            u, v = uv[li].uv
            r = per.setdefault(nm, {"u": [9, -9], "v": [9, -9], "nx": set()})
            r["u"] = [min(r["u"][0], u), max(r["u"][1], u)]; r["v"] = [min(r["v"][0], v), max(r["v"][1], v)]
        per[nm]["nx"].add(round(n[0], 2))
    out[f] = {k: {"u": [round(x, 4) for x in r["u"]], "v": [round(x, 4) for x in r["v"]], "normal_x": sorted(r["nx"])[:6]} for k, r in per.items()}
json.dump(out, open("E:/PussStage/Saved/CodexFlatV3/s2klara/fbx_uv_probe.json", "w"), indent=1)
