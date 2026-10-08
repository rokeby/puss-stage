"""Headless Blender: Front/Flap UV0 registration of a rebuilt FBX vs the LIVE (imported) FBX.

For LOD0 and LOD1 of each FBX, every loop of every polygon in the Front and Flap slots gives a tuple
(x, y, z, u, v) (cm, rounded 1e-3 cm / 1e-6 UV).  Front and Flap sit at the same x in legacy_1p8 and thick5
(the front plane is placement authority: build_v3_flat.configure_geometry), so the sorted tuple lists must be
IDENTICAL.  Also counts triangles per slot.  Writes JSON; prints S3T5O_UVCMP_OK|... or S3T5O_UVCMP_FAIL|...
Usage: blender -b --factory-startup --python compare_front_flap_uv0_blender.py -- <live.fbx> <new.fbx> <out.json>
"""
import hashlib
import json
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
live_fbx, new_fbx, out_path = argv[0], argv[1], argv[2]
SLOTS = ("Front", "Flap")


def load(fbx):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    out = {}
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        lod = "LOD0" if ob.name.endswith("_LOD0") else ("LOD1" if ob.name.endswith("_LOD1") else ob.name)
        me, mw = ob.data, ob.matrix_world
        uv = me.uv_layers.get("UV0") or me.uv_layers[0]
        names = [s.name.split(".")[0] for s in ob.material_slots]
        me.calc_loop_triangles()
        tris = {}
        for t in me.loop_triangles:
            n = names[me.polygons[t.polygon_index].material_index]
            tris[n] = tris.get(n, 0) + 1
        rows = {s: [] for s in SLOTS}
        for p in me.polygons:
            n = names[p.material_index]
            if n not in rows:
                continue
            for li in p.loop_indices:
                co = mw @ me.vertices[me.loops[li].vertex_index].co * 100.0
                u, v = uv.data[li].uv
                rows[n].append((round(co.x, 3), round(co.y, 3), round(co.z, 3), round(u, 6), round(v, 6)))
        out[lod] = {"rows": {s: sorted(r) for s, r in rows.items()}, "triangles_by_slot": tris,
                    "triangles": sum(tris.values()), "slots": names}
    return out


live, new = load(live_fbx), load(new_fbx)
res = {"live": live_fbx, "new": new_fbx, "lods": {}, "pass": True}
for lod in ("LOD0", "LOD1"):
    a, b = live.get(lod), new.get(lod)
    if a is None or b is None:
        res["lods"][lod] = {"pass": False, "error": "missing lod"}
        res["pass"] = False
        continue
    row = {"live_triangles": a["triangles"], "new_triangles": b["triangles"],
           "live_by_slot": a["triangles_by_slot"], "new_by_slot": b["triangles_by_slot"], "slots_new": b["slots"]}
    for s in SLOTS:
        ra, rb = a["rows"][s], b["rows"][s]
        same = ra == rb
        worst = 0.0
        if not same and len(ra) == len(rb):
            worst = max(max(abs(x - y) for x, y in zip(p, q)) for p, q in zip(ra, rb))
        row[s] = {"loops_live": len(ra), "loops_new": len(rb), "identical": same, "worst_abs_diff": worst,
                  "sha_live": hashlib.sha256(json.dumps(ra).encode()).hexdigest()[:16],
                  "sha_new": hashlib.sha256(json.dumps(rb).encode()).hexdigest()[:16]}
        # LOD1 has no Flap (board only): both must be empty, which compares identical
        if not same:
            res["pass"] = False
    res["lods"][lod] = row
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(res, fh, indent=1)
print("S3T5O_UVCMP_%s|%s" % ("OK" if res["pass"] else "FAIL", out_path), flush=True)
