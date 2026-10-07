"""Re-import gate + contact (gap) harness for the v3 underpass meshes, with negative controls.

    blender -b --factory-startup --python-exit-code 1 --python harness_v3.py

Checks per FBX (re-imported in a fresh scene): one mesh object, no LOD, bounds == spec (0.1 cm), bounds centre
== pivot (0.1 cm), tris <= budget, all polys triangles, one slot MAT_Steel*, two UV layers, UV1 inside 0-1,
UV0 V runs DOWN on vertical faces (Unreal side), U == x/100 on faces not facing X, and CONTACT:
  islands = loose parts (after a 0.001 cm weld); an island is ATTACHED if its triangles intersect another
  island's (BVH overlap = interpenetration); gap(island) = 0 if attached, else min vertex distance to any other
  island; PASS needs max gap == 0, every island attached, and one connected component.
Negative controls (must FAIL): NEG_LacedColumn_lifted.fbx (lacing layer floated 5 cm, built by
build_girders_v3.py -- --negative-lifted), and the v3 girder exported 1 % long with V un-flipped.
v1 meshes (DerivedAssets/UnderpassKit/FBX) are measured with the same contact code for the report (informational).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CM = 0.01
EMBED_CM = 0.2   # a member counts as attached only if sunk >= 2 mm into what carries it
SPEC = {
    "SM_UP_LacedColumn_v3": {"bounds_cm": [1880.0, 60.0, 40.0], "max_tris": 5000},
    "SM_UP_PlateGirder_v3": {"bounds_cm": [100.0, 40.0, 90.0], "max_tris": 200},
    "SM_UP_KneeBracket_v3": {"bounds_cm": [120.0, 20.0, 120.0], "max_tris": 500},
}
V1 = {"SM_UP_LacedColumn": [500.0, 60.0, 40.0], "SM_UP_PlateGirder": [100.0, 40.0, 90.0],
      "SM_UP_KneeBracket": [120.0, 10.0, 120.0]}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_one(path):
    reset()
    bpy.ops.import_scene.fbx(filepath=str(path))
    return list(bpy.context.scene.objects)


def contact(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    for v in bm.verts:
        v.co /= CM                                   # work in cm
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-3)
    bm.verts.ensure_lookup_table()
    # winding consistency: two faces sharing an edge must traverse it in opposite directions
    inconsistent = 0
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        dirs = []
        for f in e.link_faces:
            for l in f.loops:
                if l.edge == e:
                    dirs.append(l.vert == e.verts[0])
        inconsistent += dirs[0] == dirs[1]
    # islands by face connectivity
    island_of = {}
    islands = []
    for f in bm.faces:
        if f in island_of:
            continue
        idx = len(islands)
        stack, faces = [f], []
        island_of[f] = idx
        while stack:
            g = stack.pop()
            faces.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in island_of:
                        island_of[h] = idx
                        stack.append(h)
        islands.append(faces)
    data = []
    for faces in islands:
        verts = sorted({v.index for f in faces for v in f.verts})
        remap = {vi: i for i, vi in enumerate(verts)}
        co = [bm.verts[vi].co.copy() for vi in verts]
        tris = [[remap[v.index] for v in f.verts] for f in faces]
        lo = Vector([min(c[i] for c in co) for i in range(3)])
        hi = Vector([max(c[i] for c in co) for i in range(3)])
        vol = 0.0
        for tri in tris:
            for k in range(1, len(tri) - 1):
                vol += co[tri[0]].dot(co[tri[k]].cross(co[tri[k + 1]])) / 6.0
        open_ = any(len(e.link_faces) != 2 for f in faces for e in f.edges)
        samples = co + [sum((co[t] for t in tri), Vector()) / len(tri) for tri in tris]
        data.append({"vol": vol, "open": open_, "samples": samples, "co": co, "bvh": BVHTree.FromPolygons(co, tris, epsilon=0.0), "lo": lo, "hi": hi})
    bm.free()
    n = len(data)

    def aabb_near(a, b, pad):
        return all(a["lo"][i] - pad <= b["hi"][i] and b["lo"][i] - pad <= a["hi"][i] for i in range(3))

    def depth_in(a, b):
        """Deepest sample of island a strictly inside closed island b (cm); samples = verts + tri centroids."""
        best = 0.0
        for c in a["samples"]:
            if not all(b["lo"][k] - 1e-6 <= c[k] <= b["hi"][k] + 1e-6 for k in range(3)):
                continue
            loc, nrm, _i, dist = b["bvh"].find_nearest(c)
            if loc is not None and (c - loc).dot(nrm) < 0:
                best = max(best, dist)
        return best

    adj = [set() for _ in range(n)]          # EMBEDDED contacts only (>= EMBED_CM interpenetration)
    touch = [set() for _ in range(n)]        # surfaces meet but nothing is sunk (coplanar / butt)
    embed_depths = []
    for i in range(n):
        for j in range(i + 1, n):
            if not (aabb_near(data[i], data[j], 0.01) and data[i]["bvh"].overlap(data[j]["bvh"])):
                continue
            d = max(depth_in(data[i], data[j]), depth_in(data[j], data[i]))
            if d >= EMBED_CM:
                adj[i].add(j)
                adj[j].add(i)
                embed_depths.append(d)
            else:
                touch[i].add(j)
                touch[j].add(i)
    gaps = []
    for i in range(n):
        if adj[i] or touch[i]:
            gaps.append(0.0)
            continue
        best = float("inf")
        for j in range(n):
            if j == i or not aabb_near(data[i], data[j], 60.0):
                continue
            for c in data[i]["co"]:
                hit = data[j]["bvh"].find_nearest(c)
                if hit[0] is not None:
                    best = min(best, hit[3])
        gaps.append(best)
    # every island must be a closed solid with OUTWARD normals (signed volume > 0)
    inverted = sum(1 for d in data if d["vol"] <= 0)
    open_islands = sum(1 for d in data if d["open"])
    seen, comps = set(), 0
    for s in range(n):
        if s in seen:
            continue
        comps += 1
        stack = [s]
        seen.add(s)
        while stack:
            k = stack.pop()
            for m in adj[k]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
    unattached = [i for i in range(n) if not adj[i]]
    touch_only = sum(1 for i in unattached if touch[i])
    return {"islands": n, "components": comps, "unattached": len(unattached), "touch_only": touch_only,
            "max_gap_cm": round(max(gaps) if gaps else 0.0, 4),
            "min_embed_cm": round(min(embed_depths), 3) if embed_depths else None,
            "inverted_islands": inverted, "open_islands": open_islands, "inconsistent_edges": inconsistent,
            "status": "PASS" if n and comps == 1 and (n == 1 or not unattached) and not inverted
                      and not open_islands and not inconsistent else "FAIL"}


def gate(path, bounds, max_tris, do_contact=True):
    objs = import_one(path)
    meshes = [o for o in objs if o.type == "MESH"]
    probs = []
    if len(objs) != 1 or len(meshes) != 1:
        probs.append(f"objects={[(o.name, o.type) for o in objs]}")
    if any("LOD" in o.name.upper() for o in objs):
        probs.append("lod_present")
    if not meshes:
        return {"status": "FAIL", "problems": probs + ["no_mesh"]}
    obj = meshes[0]
    cs = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(c[i] for c in cs) / CM for i in range(3)]
    hi = [max(c[i] for c in cs) / CM for i in range(3)]
    size = [round(hi[i] - lo[i], 3) for i in range(3)]
    centre = [round((hi[i] + lo[i]) / 2, 3) for i in range(3)]
    if any(abs(size[i] - bounds[i]) > 0.1 for i in range(3)):
        probs.append(f"bounds {size} != {bounds}")
    if any(abs(c) > 0.1 for c in centre):
        probs.append(f"pivot: bounds centre {centre}")
    me = obj.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris > max_tris:
        probs.append(f"tris {tris} > {max_tris}")
    if any(len(p.vertices) != 3 for p in me.polygons):
        probs.append("non_triangles")
    slots = [s.material.name if s.material else None for s in obj.material_slots]
    if len(slots) != 1 or not (slots[0] or "").startswith("MAT_Steel"):
        probs.append(f"slots {slots}")
    if len(me.uv_layers) != 2:
        probs.append(f"uv_layers {[u.name for u in me.uv_layers]}")
    else:
        if any(not (-1e-4 <= d.uv.x <= 1 + 1e-4 and -1e-4 <= d.uv.y <= 1 + 1e-4) for d in me.uv_layers[1].data):
            probs.append("uv1_outside_0_1")
    uv = me.uv_layers[0].data
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    up = down = 0
    u_err = 0.0
    for p in me.polygons:
        n = (nm @ p.normal).normalized()
        if abs(n.x) < 0.1:
            for li in p.loop_indices:
                x = (mw @ me.vertices[me.loops[li].vertex_index].co).x / CM
                u_err = max(u_err, abs(uv[li].uv.x - x / 100.0))
        if abs(n.z) >= 0.1:
            continue
        zs = [(mw @ me.vertices[me.loops[li].vertex_index].co).z / CM for li in p.loop_indices]
        if max(zs) - min(zs) < 0.5:
            continue
        vs = [1.0 - uv[li].uv.y for li in p.loop_indices]
        mz, mv = sum(zs) / len(zs), sum(vs) / len(vs)
        if sum((z - mz) * (v - mv) for z, v in zip(zs, vs)) < 0:
            down += 1
        else:
            up += 1
    if up or not down:
        probs.append(f"uv_v_sign down={down} up={up}")
    if u_err > 1e-3:
        probs.append(f"u_rule_err {u_err:.4f}")
    row = {"bounds_cm": size, "centre_cm": centre, "tris": tris, "slots": slots,
           "uv_layers": [u.name for u in me.uv_layers], "v_down_faces": down, "v_up_faces": up,
           "u_rule_max_err": round(u_err, 6), "scale": [round(s, 6) for s in mw.to_scale()]}
    if do_contact:
        row["contact"] = contact(obj)
        if row["contact"]["status"] != "PASS":
            probs.append(f"contact {row['contact']}")
    row["problems"] = probs
    row["status"] = "PASS" if not probs else "FAIL"
    return row


def neg_girder_long():
    objs = import_one(HERE / "FBX" / "SM_UP_PlateGirder_v3.fbx")
    obj = [o for o in objs if o.type == "MESH"][0]
    obj.scale = (obj.scale[0] * 1.01, obj.scale[1], obj.scale[2])
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for d in obj.data.uv_layers[0].data:
        d.uv.y = 1.0 - d.uv.y
    path = HERE / "reimport" / "NEG_girder_long.fbx"
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"MESH"},
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
                             bake_space_transform=False, add_leaf_bones=False)
    return gate(path, SPEC["SM_UP_PlateGirder_v3"]["bounds_cm"], 200)


def main():
    rows = {}
    for name, sp in SPEC.items():
        rows[name] = gate(HERE / "FBX" / f"{name}.fbx", sp["bounds_cm"], sp["max_tris"])
        print(f"GIRDERS_V3_GATE|{name}|{rows[name]['status']}|tris={rows[name].get('tris')}|"
              f"contact={rows[name].get('contact')}|{rows[name]['problems']}")
    neg = {"lifted_lacing": gate(HERE / "FBX" / "NEG_LacedColumn_lifted.fbx", [1880.0, 60.0, 50.0], 5000),
           "girder_long_vflip": neg_girder_long()}
    for k, r in neg.items():
        print(f"GIRDERS_V3_NEG|{k}|{r['status']}|{r['problems']}")
    v1 = {}
    for name, b in V1.items():
        v1[name] = gate(REPO / "DerivedAssets" / "UnderpassKit" / "FBX" / f"{name}.fbx", b, 10 ** 6)
        print(f"GIRDERS_V1_MEASURED|{name}|tris={v1[name]['tris']}|contact={v1[name].get('contact')}")
    neg_ok = (neg["lifted_lacing"]["status"] == "FAIL"
              and neg["lifted_lacing"].get("contact", {}).get("status") == "FAIL"
              and neg["girder_long_vflip"]["status"] == "FAIL")
    status = "PASS" if all(r["status"] == "PASS" for r in rows.values()) and neg_ok else "FAIL"
    out = HERE / "harness_result.json"
    out.write_text(json.dumps({"status": status, "v3": rows, "negative_controls": neg, "negatives_failed_as_expected": neg_ok,
                               "v1_measured": v1}, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"GIRDERS_V3_HARNESS_{status}|{out}")
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
