"""Inspect every Meshy export: bounds, tris, materials, UV layers, objects. Prints JSON."""
import bpy, json, glob, os, sys
from mathutils import Vector
ROOT = r"E:\PussStage\DerivedAssets\Lighting\Meshy"
out = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if not os.path.isdir(d): continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(d, "Meshy_AI_model.fbx"))
    tex = [os.path.basename(p) for p in glob.glob(os.path.join(d, "*-texture.png"))]
    rec = {"uuid": os.path.basename(d), "tex": tex, "objects": []}
    for o in bpy.data.objects:
        r = {"name": o.name, "type": o.type, "loc": list(o.location), "rot": list(o.rotation_euler), "scale": list(o.scale),
             "parent": o.parent.name if o.parent else None}
        if o.type == "MESH":
            m = o.data
            ws = [o.matrix_world @ v.co for v in m.vertices]
            mn = [min(v[i] for v in ws) for i in range(3)]; mx = [max(v[i] for v in ws) for i in range(3)]
            r.update(tris=sum(len(p.vertices) - 2 for p in m.polygons), verts=len(m.vertices),
                     bmin=mn, bmax=mx, dims=[mx[i]-mn[i] for i in range(3)],
                     mats=[s.material.name if s.material else None for s in o.material_slots],
                     uvs=[u.name for u in m.uv_layers])
        rec["objects"].append(r)
    rec["unit_scale"] = bpy.context.scene.unit_settings.scale_length
    out.append(rec)
print("JSONSTART" + json.dumps(out) + "JSONEND")
