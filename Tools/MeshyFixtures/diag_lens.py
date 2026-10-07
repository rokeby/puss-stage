"""Diagnostic: texel luminance / metallic of forward-facing front faces of each decimated housing, by radius from the
front-face area centroid. Also renders a front ortho view with luminance-threshold candidates painted."""
import bpy, sys, os, json, math
import numpy as np
sys.path.insert(0, r"E:\PussStage\Tools\MeshyFixtures")
import meshy_common as mc
import build_meshy_fixtures as B
from mathutils import Vector
OUT = sys.argv[sys.argv.index("--")+1]
res = {}
for name, cfg in B.HOUSINGS.items():
    src = mc.list_sources()[name]
    ob = mc.import_source(src)
    ob.rotation_euler = (0, 0, B.BEAM_ROT[cfg["beam"]]); B.apply_all(ob)
    B.decimate_to(ob, 11700); B.triangulate(ob)
    C, N, A = B.face_arrays(ob)
    bc = mc.load_img(src["basecolor"]); me = mc.load_img(src["metallic"])
    uvl = ob.data.uv_layers.active.data
    L = np.zeros(len(C)); M = np.zeros(len(C))
    for p in ob.data.polygons:
        uv = sum((uvl[i].uv for i in p.loop_indices), Vector((0, 0))) / p.loop_total
        L[p.index] = mc.lum(mc.sample(bc, uv)[:3]); M[p.index] = mc.sample(me, uv)[0]
    xmax, xmin = C[:, 0].max(), C[:, 0].min()
    cand = (N[:, 0] > 0.5) & (C[:, 0] > xmax - 0.45 * (xmax - xmin))
    hist = {}
    for lo, hi in ((0, .1), (.1, .2), (.2, .3), (.3, .45), (.45, .6), (.6, 1.01)):
        s = cand & (L >= lo) & (L < hi)
        hist[f"{lo}-{hi}"] = {"n": int(s.sum()), "area": round(float(A[s].sum()/A[cand].sum()), 3), "met": round(float(M[s].mean()), 2) if s.any() else None}
    res[name] = hist
    # render front view coloured by lum class
    mats = [B.make_material(f"c{i}", c) for i, c in enumerate([(0.1,0.1,0.1,1),(1,0.2,0.2,1),(1,0.9,0.1,1),(0.2,1,0.2,1)])]
    ob.data.materials.clear(); [ob.data.materials.append(m) for m in mats]
    cls = np.where(~cand, 0, np.where(L < 0.15, 1, np.where(M > 0.4, 2, 3))).astype(np.int32)
    ob.data.polygons.foreach_set("material_index", cls); ob.data.update()
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x = sc.render.resolution_y = 300
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.2
    d = Vector((1, -0.25, 0.15)).normalized(); cam.location = d*5; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"lens_{name}.png"); bpy.ops.render.render(write_still=True)
print("DIAG" + json.dumps(res))
