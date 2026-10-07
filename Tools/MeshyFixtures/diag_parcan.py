import bpy, sys, numpy as np
sys.path.insert(0, r"E:\PussStage\Tools\MeshyFixtures")
import meshy_common as mc, build_meshy_fixtures as B
name = "SM_Lantern_ParCan"; cfg = B.HOUSINGS[name]; src = mc.list_sources()[name]
ob = mc.import_source(src); ob.rotation_euler = (0, 0, B.BEAM_ROT[cfg["beam"]]); B.apply_all(ob)
B.decimate_to(ob, 11700); B.triangulate(ob)
C, N, A = B.face_arrays(ob); V = B.vert_array(ob); Lum = B.face_texel_lum(ob, mc.load_img(src["basecolor"]))
xmax, xmin = V[:, 0].max(), V[:, 0].min(); L = xmax - xmin
front = (N[:, 0] > 0.5) & (C[:, 0] > xmax - 0.45 * L); cand = front & (Lum >= 0.15)
comp, k = B.edge_components(ob, cand)
w = A * cand; cy, cz = (C[:, 1]*w).sum()/w.sum(), (C[:, 2]*w).sum()/w.sum()
print("DBG body", cy, cz, "halfY", (V[:,1].max()-V[:,1].min())/2, "ncomp", k)
rows = []
for i in range(k):
    s = comp == i; a = A[s].sum()
    c = np.array([(C[s,1]*A[s]).sum()/a, (C[s,2]*A[s]).sum()/a]); rr = np.hypot(C[s,1]-c[0], C[s,2]-c[1])
    rows.append((a, s.sum(), c.round(3).tolist(), round(float(rr.min()),3), round(float(np.percentile(rr,95)),3), round(float(C[s,0].mean()),3)))
for r in sorted(rows, reverse=True)[:8]: print("DBG", r)
