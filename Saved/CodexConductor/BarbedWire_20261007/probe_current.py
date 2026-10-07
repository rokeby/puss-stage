import bpy, json, sys
from mathutils import Vector
res={}
for name in ("SM_FenceBay_short_open","SM_FenceBay_short_door_gap","SM_FencePost_short"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=r"E:\PussStage\DerivedAssets\FlatV3\FenceBay\short\%s.fbx"%name)
    out={}
    for o in bpy.context.scene.objects:
        if o.type!="MESH": out[o.name]={"type":o.type,"props":{k:str(o[k]) for k in o.keys()}}; continue
        c=[o.matrix_world@v.co for v in o.data.vertices]
        mn=[min(p[i] for p in c) for i in range(3)]; mx=[max(p[i] for p in c) for i in range(3)]
        out[o.name]={"tris":len(o.data.polygons),"min":mn,"max":mx,"slots":[s.material.name for s in o.material_slots],"parent":o.parent.name if o.parent else None}
    res[name]=out
json.dump(res,open(r"E:\PussStage\Saved\CodexConductor\BarbedWire_20261007\current_probe.json","w"),indent=1)
print("PROBE_OK")
