"""Read-only Blender probe of her 3 wing FBXs (copies in DerivedAssets/FlatV3/KlaraS2/_src): Front face normal, the
direction image U runs along FBX Y, and V along Z.  blender -b --factory-startup --python <this> -- <out.json>"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

SRC = Path("E:/PussStage/DerivedAssets/FlatV3/KlaraS2/_src")
out = Path(sys.argv[sys.argv.index("--") + 1])
res = {}
for name in ("SM_S2_L_Wing_Shrine.fbx", "SM_S2_R_Wing_Shrine.fbx", "SM_S2_ceiling_wing.fbx"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(SRC / name))
    obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    me = obj.data
    mw = obj.matrix_world
    uv = me.uv_layers.active.data
    rows = []
    for p in me.polygons:
        if "Front" not in me.materials[p.material_index].name:
            continue
        for li in p.loop_indices:
            co = mw @ me.vertices[me.loops[li].vertex_index].co
            rows.append((co.x, co.y, co.z, uv[li].uv[0], uv[li].uv[1]))
    a = np.array(rows)
    n = np.array([0.0, 0.0, 0.0])
    for p in me.polygons:
        if "Front" in me.materials[p.material_index].name:
            n += np.array((mw.to_3x3() @ p.normal)[:]) * p.area
    n /= np.linalg.norm(n)
    du_dy = float(np.polyfit(a[:, 1], a[:, 3], 1)[0])
    dv_dz = float(np.polyfit(a[:, 2], a[:, 4], 1)[0])
    allv = np.array([(mw @ v.co)[:] for v in me.vertices])
    res[name] = {"front_normal_fbx_blender": [round(float(x), 4) for x in n], "du_dY_per_m": round(du_dy, 5),
                 "dv_dZ_per_m": round(dv_dz, 5), "front_x_m": [round(float(a[:, 0].min()), 4), round(float(a[:, 0].max()), 4)],
                 "bounds_min_m": [round(float(x), 4) for x in allv.min(0)], "bounds_max_m": [round(float(x), 4) for x in allv.max(0)],
                 "object_matrix_world": [list(r) for r in mw]}
out.write_text(json.dumps(res, indent=1))
print("HER_FBX_HANDEDNESS_DONE")
