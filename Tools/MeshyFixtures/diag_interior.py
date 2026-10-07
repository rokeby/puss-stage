"""Diagnostic: per bulb, shell radius by sector-max, count interior faces (r < 0.8 shell), render interior-only view."""
import bpy, bmesh, sys, os, json, math
import numpy as np
sys.path.insert(0, r"E:\PussStage\Tools\MeshyFixtures")
import meshy_common as mc
from mathutils import Vector
OUT = sys.argv[sys.argv.index("--")+1]
res = {}
for name, src in mc.list_sources().items():
    if "Bulb" not in name: continue
    ob = mc.import_source(src)
    me = ob.data; n = len(me.polygons)
    C = np.zeros(n*3); me.polygons.foreach_get("center", C); C = C.reshape(n, 3)
    top = C[C[:, 2] > C[:, 2].min() + 0.82 * (C[:, 2].max() - C[:, 2].min())]
    cx, cy = np.median(top[:, 0]), np.median(top[:, 1])
    r = np.hypot(C[:, 0]-cx, C[:, 1]-cy); th = np.arctan2(C[:, 1]-cy, C[:, 0]-cx)
    z = C[:, 2]; zb = np.clip(((z - z.min())/(z.max()-z.min()+1e-9)*60).astype(int), 0, 59)
    sb = np.clip(((th + math.pi)/(2*math.pi)*16).astype(int), 0, 15)
    shell = np.zeros(60)
    for b in range(60):
        m = [r[(zb == b) & (sb == s)].max() for s in range(16) if ((zb == b) & (sb == s)).any()]
        shell[b] = np.median(m) if m else np.nan
    rs = shell[zb]
    inner = r < 0.8 * rs; outer = r > 1.10 * rs + 0.01
    res[name] = {"faces": n, "inner": int(inner.sum()), "outer": int(outer.sum())}
    # render inner only
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~inner)[0]], context="FACES"); bm.to_mesh(me); bm.free()
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x = sc.render.resolution_y = 300
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.2
    d = Vector((1, -1, 0.4)).normalized(); cam.location = d*5; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"inner_{name}.png"); bpy.ops.render.render(write_still=True)
print("DIAG" + json.dumps(res))
