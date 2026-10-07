"""Diagnostic: per housing, front-cap luminance/metallic score along +-X +-Y; per bulb, metallic vs height."""
import bpy, bmesh, sys, json
import numpy as np
sys.path.insert(0, r"E:\PussStage\Tools\MeshyFixtures")
import meshy_common as mc
from mathutils import Vector
res = {}
for name, src in mc.list_sources().items():
    ob = mc.import_source(src)
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    uvl = bm.loops.layers.uv.active
    bc = mc.load_img(src["basecolor"]); me = mc.load_img(src["metallic"])
    # subsample faces for speed
    faces = list(bm.faces)[::7] if len(bm.faces) > 100000 else list(bm.faces)
    C = np.array([f.calc_center_median()[:] for f in faces]); N = np.array([f.normal[:] for f in faces]); A = np.array([f.calc_area() for f in faces])
    L = np.array([mc.lum(mc.sample(bc, sum((l[uvl].uv for l in f.loops), Vector((0,0)))/len(f.loops))[:3]) for f in faces])
    M = np.array([mc.sample(me, sum((l[uvl].uv for l in f.loops), Vector((0,0)))/len(f.loops))[0] for f in faces])
    r = {"faces": len(bm.faces)}
    if "Lantern" in name:
        for lab, d in {"+X": (1,0,0), "-X": (-1,0,0), "+Y": (0,1,0), "-Y": (0,-1,0)}.items():
            d = np.array(d, float); p = C @ d; nd = N @ d
            sel = (nd > 0.7) & (p > p.max() - 0.25 * (p.max() - p.min()))
            r[lab] = {"n": int(sel.sum()), "lum": float((L[sel]*A[sel]).sum()/max(A[sel].sum(),1e-9)), "met": float((M[sel]*A[sel]).sum()/max(A[sel].sum(),1e-9))}
    else:
        z = C[:, 2]; bins = np.linspace(z.min(), z.max(), 21)
        r["metal_by_z"] = [round(float(M[(z>=bins[i])&(z<bins[i+1])].mean()),2) if ((z>=bins[i])&(z<bins[i+1])).any() else None for i in range(20)]
        r["lum_by_z"] = [round(float(L[(z>=bins[i])&(z<bins[i+1])].mean()),2) if ((z>=bins[i])&(z<bins[i+1])).any() else None for i in range(20)]
        rad = np.hypot(C[:,0], C[:,1])
        r["rad_by_z"] = [round(float(np.median(rad[(z>=bins[i])&(z<bins[i+1])])),3) if ((z>=bins[i])&(z<bins[i+1])).any() else None for i in range(20)]
    res[name] = r
print("DIAG" + json.dumps(res))
