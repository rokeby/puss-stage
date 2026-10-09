# Headless Blender, read-only: import Klara's S2 wing FBX sources (archive) and report bounds, tris, materials.
import bpy, json, sys, os
A = "D:/PussStageArchive/Keep-20261003/Klara Scenes WIP/2. Old Man and Shrine/Assets/"
out = {}
for f in ["SM_S2_L_Wing_Shrine.fbx", "SM_S2_R_Wing_Shrine.fbx", "SM_S2_ceiling_wing.fbx", "MudTower_SeeThrough/SM_MudTower_SeeThrough.fbx"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=A + f)
    rows = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        me = o.data
        vs = [o.matrix_world @ v.co for v in me.vertices]
        mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
        me.calc_loop_triangles()
        per = {}
        for t in me.loop_triangles:
            nm = me.materials[t.material_index].name if me.materials else None
            per[nm] = per.get(nm, 0) + 1
        rows.append({"obj": o.name, "min_m": [round(x, 4) for x in mn], "max_m": [round(x, 4) for x in mx],
                     "tris": len(me.loop_triangles), "tris_per_slot": per, "slots": [m.name if m else None for m in me.materials],
                     "uv_layers": [u.name for u in me.uv_layers]})
    out[f] = rows
json.dump(out, open("E:/PussStage/Saved/CodexFlatV3/s2klara/fbx_probe.json", "w"), indent=1)
print("FBXPROBE_OK")
