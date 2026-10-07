"""No-wire twins of the short FenceBay bays, for the LOWER rows of a Stack fence (Gary 7 Oct:
"the wire only needs to appear at the top of the fence").

Headless Blender only:  blender -b --factory-startup --python barbed_nowire.py -- <stage>
  build     -> fbx/SM_FenceBay_short_open_nw.fbx, fbx/SM_FenceBay_short_door_gap_nw.fbx,
               fbx_negctl/*_nw*.fbx (deliberately broken), build_manifest_nw.json
  validate  -> validation_nw.json (factory-clean FBX re-import vs the CURRENT bay FBX; controls must FAIL)
  render    -> renders/stack_nw_compare.png

Source = the CURRENT bay FBX (DerivedAssets/FlatV3/FenceBay/short/<bay>.fbx, what Unreal imported), never
Tools/FlatV3/*. Every kept polygon is copied verbatim (positions, both UV layers UV0/UVMap, corner normals,
smooth flags, material index, order); the concertina (loops, razors, clips: every metal island that is not a
rail or a door jamb) is dropped.

Why two things are ADDED (the C++ fits by bounds, read from source):
  * Stack row height = the tallest built variant Mesh's bounds Z (InfinityStageStructureActor.cpp:596-602), and
    every panel is fitted bounds-centre-on-line with each axis scaled to the slot (FitMeshToTimber, :183-196).
    Without the coil the bay's top would fall from 3.026763 m to the rail top 2.701 m: the row pitch would change
    (2 whole rows of 302.68 cm become 2 of 270.1 + a bigger cut row), and the 302.68 cm wire bay drawn as the top
    row (TopRowMesh) would be Z-squashed to 89 %. So the top MUST stay at 3.026763 m.
  * A second rail - a verbatim copy of the bay's own rail - is lifted so its top is exactly 3.026763 m: it is
    real geometry that holds the bounds and hides the chain's phase seam at the row joint. It is shifted in Y
    (behind the chain, away from the walkway) by exactly what keeps the LOD0 Y bounds CENTRE where the current
    bay's is (the panel's placement depends on it); the Y extents themselves shrink (depth only feeds DepthCm,
    to which Scale.Y = 1 regardless).
  * The chain is continued 2.70 -> 3.026763 m with the same physical UV (UV0 = (x+1.68, z)/0.96, UVMap = 0 as
    on the current chain): without it every lower row joint would show a 33 cm see-through band where the
    coil used to sit (rows stack at 302.68 cm, the chain ends at 270 cm).
"""
import bpy, bmesh, json, sys, os, hashlib, math
from mathutils import Vector

OUT = r"E:\PussStage\Saved\CodexConductor\BarbedWire_20261007"
CUR = r"E:\PussStage\DerivedAssets\FlatV3\FenceBay\short"
BAYS = ("SM_FenceBay_short_open", "SM_FenceBay_short_door_gap")
SLOT_CHAIN, SLOT_METAL = "M_FenceChain_Masked", "M_FenceMetal"
HALF = 1.68
CHAIN_Y = -0.02
CHAIN_TOP = 2.70
MASK_TILE = 0.96
KEEP_Y = (-0.071, -0.019)   # rail + jambs live at y -0.045 +- 0.024 (build_fence_bay.py:72-78)
KEEP_ZMAX = 2.705           # rail top 2.701; the coil sits above it
EXPECT = {"SM_FenceBay_short_open": {"chain": 1, "metal": 1},
          "SM_FenceBay_short_door_gap": {"chain": 3, "metal": 4}}
TOL = 5e-4  # 0.5 mm


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def import_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    lods = {}
    for o in meshes:
        if "_LOD" in o.name:
            lods[int(o.name.rsplit("_LOD", 1)[1].split(".")[0])] = o
    groups = [o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.name.endswith("_LODGroup")]
    return lods, groups, meshes


def islands(me, polys):
    parent = {}
    def f(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for p in polys:
        vs = list(me.polygons[p].vertices)
        for v in vs[1:]:
            ra, rb = f(vs[0]), f(v)
            if ra != rb: parent[rb] = ra
    g = {}
    for p in polys:
        g.setdefault(f(me.polygons[p].vertices[0]), []).append(p)
    return list(g.values())


def bbox_polys(me, co, polys):
    vs = {v for p in polys for v in me.polygons[p].vertices}
    return [min(co[v][k] for v in vs) for k in range(3)], [max(co[v][k] for v in vs) for k in range(3)]


def classify(o):
    """(kept polys, dropped polys, chain islands, kept metal islands, rail island) of an imported LOD."""
    me = o.data; co = [o.matrix_world @ v.co for v in me.vertices]
    slots = [s.material.name.split(".")[0] if s.material else None for s in o.material_slots]
    chain = [p.index for p in me.polygons if slots[p.material_index] == SLOT_CHAIN]
    metal = [p.index for p in me.polygons if slots[p.material_index] == SLOT_METAL]
    chain_isl = islands(me, chain)
    kept_metal, dropped, rail = [], [], None
    for isl in islands(me, metal):
        mn, mx = bbox_polys(me, co, isl)
        if mx[2] <= KEEP_ZMAX and mn[1] >= KEEP_Y[0] and mx[1] <= KEEP_Y[1]:
            kept_metal.append(isl)
            if mx[0] - mn[0] > 2 * HALF - 1e-3 and mx[2] - mn[2] < 0.05 and mn[2] > 2.6:
                rail = isl
        else:
            dropped += isl
    kept = sorted([p for isl in chain_isl for p in isl] + [p for isl in kept_metal for p in isl])
    return kept, dropped, chain_isl, kept_metal, rail, co, slots


class Out:
    """Vertices are shared by key (source vertex index + shift), so the copied topology is the source's."""
    def __init__(s): s.v = []; s.idx = {}; s.f = []; s.uv0 = []; s.uv1 = []; s.n = []; s.m = []; s.sm = []

    def vert(s, key, p):
        if key not in s.idx:
            s.idx[key] = len(s.v); s.v.append(tuple(p))
        return s.idx[key]

    def add_poly(s, pts, uv0, uv1, nrm, mat, smooth, keys=None):
        keys = keys or [("pos",) + tuple(round(c, 7) for c in p) for p in pts]
        s.f.append(tuple(s.vert(k, p) for k, p in zip(keys, pts)))
        s.uv0.append([tuple(u) for u in uv0]); s.uv1.append([tuple(u) for u in uv1])
        s.n.append([tuple(x) for x in nrm]); s.m.append(mat); s.sm.append(smooth)

    def to_object(s, name, mats):
        me = bpy.data.meshes.new(name); me.from_pydata(s.v, [], s.f); me.update()
        l0 = me.uv_layers.new(name="UV0"); l1 = me.uv_layers.new(name="UVMap")
        for poly, a, b in zip(me.polygons, s.uv0, s.uv1):
            for li, ua, ub in zip(poly.loop_indices, a, b):
                l0.data[li].uv = ua; l1.data[li].uv = ub
        me.uv_layers.active = l0; l0.active_render = True
        for m in mats: me.materials.append(m)
        for poly, mi, sm in zip(me.polygons, s.m, s.sm):
            poly.material_index = mi; poly.use_smooth = sm
        me.normals_split_custom_set([n for poly_n in s.n for n in poly_n])
        ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
        return ob


def derive(bay, opts):
    """Read the current bay FBX and return ([Out per LOD], facts). opts: lift/centre/keep_coil_island (controls)."""
    lods, groups, _ = import_fbx(os.path.join(CUR, bay + ".fbx"))
    if sorted(lods) != [0, 1] or len(groups) != 1:
        raise RuntimeError("SOURCE_LODS|%s|%s" % (bay, sorted(lods)))
    # LOD0 bounds of the current bay = the targets
    o0 = lods[0]; co0 = [o0.matrix_world @ v.co for v in o0.data.vertices]
    tmn = [min(p[k] for p in co0) for k in range(3)]; tmx = [max(p[k] for p in co0) for k in range(3)]
    yc = (tmn[1] + tmx[1]) * 0.5
    outs, facts = [], {"source_fbx": os.path.join(CUR, bay + ".fbx"), "source_sha256": sha(os.path.join(CUR, bay + ".fbx")),
                       "source_bounds_lod0": [tmn, tmx], "lods": {}}
    shift = None
    for li in (0, 1):
        o = lods[li]; me = o.data
        kept, dropped, chain_isl, kept_metal, rail, co, slots = classify(o)
        if slots != [SLOT_CHAIN, SLOT_METAL]:
            raise RuntimeError("SOURCE_SLOTS|%s|%s" % (bay, slots))
        if len(chain_isl) != EXPECT[bay]["chain"] or len(kept_metal) != EXPECT[bay]["metal"] or rail is None:
            raise RuntimeError("SOURCE_ISLANDS|%s|LOD%d|chain=%d metal=%d rail=%s" % (bay, li, len(chain_isl), len(kept_metal), rail is not None))
        kmn, kmx = bbox_polys(me, co, kept)  # the real kept set (a control's extra coil must not move the rail)
        if opts.get("keep_coil_island"):
            extra = islands(me, dropped)[0]; kept = sorted(kept + extra)
        cn = me.corner_normals
        uv0 = me.uv_layers["UV0"].data; uv1 = me.uv_layers["UVMap"].data
        out = Out()

        def copy_poly(p, d=(0.0, 0.0, 0.0)):
            poly = me.polygons[p]
            out.add_poly([co[me.loops[l].vertex_index] + Vector(d) for l in poly.loop_indices],
                         [uv0[l].uv for l in poly.loop_indices], [uv1[l].uv for l in poly.loop_indices],
                         [cn[l].vector for l in poly.loop_indices], poly.material_index, poly.use_smooth,
                         [("src", me.loops[l].vertex_index, tuple(d)) for l in poly.loop_indices])
        for p in kept:
            copy_poly(p)
        rmn, rmx = bbox_polys(me, co, rail)
        if shift is None:  # computed on LOD0, applied identically to LOD1
            dz = (tmx[2] - rmx[2]) if opts.get("lift", True) else 0.0
            if opts.get("centre", True):
                dy = 2 * yc - kmn[1] - rmx[1]   # top rail becomes the Y max; kept geometry keeps the Y min
                if not (rmn[1] + dy > kmn[1] and rmx[1] + dy > kmx[1]):
                    raise RuntimeError("TOP_RAIL_Y_ASSUMPTION|%s|k=%s..%s r=%s..%s dy=%s yc=%s" % (bay, kmn, kmx, rmn, rmx, dy, yc))
            else:
                dy = 0.0
            shift = (0.0, dy, dz)
        for p in rail:
            copy_poly(p, shift)
        # chain continued to the top, same physical UV, normal copied from the chain itself
        chain_top = tmx[2] if opts.get("lift", True) else CHAIN_TOP
        ref = me.polygons[chain_isl[0][0]]
        nrm = cn[ref.loop_indices[0]].vector.copy()
        sm = ref.use_smooth
        quad = [(-HALF, CHAIN_Y, CHAIN_TOP), (-HALF, CHAIN_Y, chain_top), (HALF, CHAIN_Y, chain_top), (HALF, CHAIN_Y, CHAIN_TOP)]
        if chain_top > CHAIN_TOP + 1e-6:
            uvq = [((x + HALF) / MASK_TILE, z / MASK_TILE) for x, _, z in quad]
            for tri in ((0, 1, 2), (0, 2, 3)):
                out.add_poly([quad[i] for i in tri], [uvq[i] for i in tri], [(0.0, 0.0)] * 3, [nrm] * 3, 0, sm)
        outs.append(out)
        facts["lods"][li] = {"source_tris": len(me.polygons), "kept_tris": len(kept), "dropped_tris": len(dropped),
                             "added_tris": len(rail) + (2 if chain_top > CHAIN_TOP + 1e-6 else 0), "out_tris": len(out.f)}
    facts["top_rail_shift_m"] = list(shift); facts["target_y_centre"] = yc
    return outs, facts


def mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return m


def export_group(asset, objs, out_dir):
    # Same group convention and exporter settings as the current bays (build_fence_bay.py export_group).
    group = bpy.data.objects.new(asset + "_LODGroup", None); bpy.context.collection.objects.link(group)
    group["fbx_type"] = "LodGroup"; group["LODOrder"] = ",".join("LOD%d" % i for i in range(len(objs)))
    for o in objs: o.parent = group
    bpy.ops.object.select_all(action="DESELECT"); group.select_set(True)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    path = os.path.join(out_dir, asset + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", use_space_transform=True, bake_space_transform=False,
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, use_triangles=True, add_leaf_bones=False,
                             bake_anim=False, axis_forward="-Z", axis_up="Y")
    return path


def emit(bay, asset, opts, out_dir):
    outs, facts = derive(bay, opts)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = [mat(SLOT_CHAIN), mat(SLOT_METAL)]
    objs = [o.to_object("%s_LOD%d" % (asset, i), mats) for i, o in enumerate(outs)]
    path = export_group(asset, objs, out_dir)
    facts.update(asset=asset, fbx=path, sha256=sha(path), opts=opts)
    return facts


CONTROLS = {  # name: (bay, opts, checks that MUST fail)
    "negctl_keeps_coil": ("SM_FenceBay_short_open", {"keep_coil_island": True}, {"no_coil", "identical_minus_coil"}),
    "negctl_unlifted": ("SM_FenceBay_short_open", {"lift": False, "centre": False}, {"top_z", "y_centre"}),
}


def build():
    fdir = os.path.join(OUT, "fbx"); ndir = os.path.join(OUT, "fbx_negctl")
    os.makedirs(fdir, exist_ok=True); os.makedirs(ndir, exist_ok=True)
    man = {"assets": [], "controls": {}}
    for bay in BAYS:
        man["assets"].append(emit(bay, bay + "_nw", {}, fdir))
    for name, (bay, opts, _) in CONTROLS.items():
        d = os.path.join(ndir, name); os.makedirs(d, exist_ok=True)
        man["controls"][name] = emit(bay, bay + "_nw", opts, d)
    json.dump(man, open(os.path.join(OUT, "build_manifest_nw.json"), "w"), indent=1)
    print("NW_BUILD_OK")


# ------------------------------- validation ----------------------------------
def tri_keys(o, polys=None):
    me = o.data; co = [o.matrix_world @ v.co for v in me.vertices]
    uv0 = me.uv_layers["UV0"].data if "UV0" in me.uv_layers else me.uv_layers.active.data
    slots = [s.material.name.split(".")[0] if s.material else None for s in o.material_slots]
    keys = {}
    for p in (me.polygons if polys is None else [me.polygons[i] for i in polys]):
        k = tuple(sorted((tuple(round(c, 5) for c in co[me.loops[l].vertex_index]), tuple(round(c, 5) for c in uv0[l].uv))
                         for l in p.loop_indices)) + (slots[p.material_index],)
        keys[k] = keys.get(k, 0) + 1
    return keys


def check(path, bay):
    """Re-import `path` and compare it with the current bay `bay`. Returns a result row."""
    lods_s, _, _ = import_fbx(os.path.join(CUR, bay + ".fbx"))
    src = {}
    for li, o in lods_s.items():
        kept, dropped, *_r = classify(o)
        co = [o.matrix_world @ v.co for v in o.data.vertices]
        src[li] = {"kept": tri_keys(o, kept), "all": tri_keys(o),
                   "bounds": [[min(p[k] for p in co) for k in range(3)], [max(p[k] for p in co) for k in range(3)]],
                   "slots": [s.material.name.split(".")[0] for s in o.material_slots],
                   "uv_layers": [u.name for u in o.data.uv_layers]}
    lods, groups, meshes = import_fbx(path)
    C, M = {}, {}
    C["lod_count"] = sorted(lods) == sorted(src) and len(groups) == 1 and all(o.parent == groups[0] for o in lods.values())
    C["triangulated"] = all(len(p.vertices) == 3 for o in meshes for p in o.data.polygons)
    C["slots"] = all([s.material.name.split(".")[0] for s in o.material_slots] == src[i]["slots"] for i, o in lods.items())
    C["uv_layers"] = all([u.name for u in o.data.uv_layers] == src[i]["uv_layers"] for i, o in lods.items())
    o0 = lods.get(0)
    co = [o0.matrix_world @ v.co for v in o0.data.vertices]
    mn = [min(p[k] for p in co) for k in range(3)]; mx = [max(p[k] for p in co) for k in range(3)]
    smn, smx = src[0]["bounds"]
    M["bounds_lod0"] = [mn, mx]; M["source_bounds_lod0"] = [smn, smx]
    M["delta_mm"] = {"min": [round((mn[k] - smn[k]) * 1000, 3) for k in range(3)], "max": [round((mx[k] - smx[k]) * 1000, 3) for k in range(3)]}
    C["bounds_x"] = abs(mn[0] - smn[0]) < TOL and abs(mx[0] - smx[0]) < TOL
    C["bottom_z"] = abs(mn[2] - smn[2]) < TOL
    C["top_z"] = abs(mx[2] - smx[2]) < TOL
    C["y_centre"] = abs((mn[1] + mx[1]) * 0.5 - (smn[1] + smx[1]) * 0.5) < TOL
    M["new_top_z_m"] = mx[2]; M["y_centre_m"] = (mn[1] + mx[1]) * 0.5
    for i, o in lods.items():
        if i == 0: continue
        c2 = [o.matrix_world @ v.co for v in o.data.vertices]
        C["lod%d_inside_lod0" % i] = all(min(p[k] for p in c2) >= mn[k] - TOL and max(p[k] for p in c2) <= mx[k] + TOL for k in range(3))
    # verbatim: every kept source triangle is in the output; the rest of the output is the added rail + chain strip
    ident, extra_ok, coil = True, True, True
    M["lods"] = {}
    for i, o in lods.items():
        got = tri_keys(o)
        miss = sum(max(0, n - got.get(k, 0)) for k, n in src[i]["kept"].items())
        extra = {k: n - src[i]["kept"].get(k, 0) for k, n in got.items() if n > src[i]["kept"].get(k, 0)}
        rail_n = sum(n for k, n in extra.items() if k[-1] == SLOT_METAL)
        chain_n = sum(n for k, n in extra.items() if k[-1] == SLOT_CHAIN)
        coil_left = sum(n for k, n in extra.items() if k in src[i]["all"] and k not in src[i]["kept"])
        ident &= miss == 0
        extra_ok &= rail_n == 8 and chain_n == 2 and coil_left == 0
        # no coil: every metal island is a straight bar (rails, jambs, header) - nothing rises above the rail
        # except the one lifted rail, and the metal island count is the source's kept count + 1
        me = o.data; cc = [o.matrix_world @ v.co for v in me.vertices]
        slots = [s.material.name.split(".")[0] for s in o.material_slots]
        metal = islands(me, [p.index for p in me.polygons if slots[p.material_index] == SLOT_METAL])
        bars = 0
        for isl in metal:
            a, b = bbox_polys(me, cc, isl)
            d = sorted(b[k] - a[k] for k in range(3))
            bars += d[0] < 0.05 and d[1] < 0.05
        want_metal = EXPECT[bay]["metal"] + 1
        coil &= len(metal) == want_metal and bars == want_metal
        M["lods"][i] = {"tris": len(me.polygons), "missing_kept": miss, "added_metal": rail_n, "added_chain": chain_n,
                        "coil_tris_present": coil_left, "metal_islands": len(metal), "straight_bars": bars}
    C["identical_minus_coil"] = ident and extra_ok
    C["no_coil"] = coil
    # chain: physical UV on every chain triangle, the plane at y -0.02, top at the bounds top
    me = o0.data; uvl = me.uv_layers["UV0"].data; slots = [s.material.name.split(".")[0] for s in o0.material_slots]
    chain = [p for p in me.polygons if slots[p.material_index] == SLOT_CHAIN]
    C["chain_uv_physical"] = all(abs(uvl[l].uv[0] - (co[me.loops[l].vertex_index][0] + HALF) / MASK_TILE) < 1e-4 and
                                 abs(uvl[l].uv[1] - co[me.loops[l].vertex_index][2] / MASK_TILE) < 1e-4
                                 for p in chain for l in p.loop_indices)
    C["chain_plane"] = all(abs(co[v][1] - CHAIN_Y) < 1e-5 for p in chain for v in p.vertices)
    M["chain_top_z_m"] = max(co[v][2] for p in chain for v in p.vertices)
    C["chain_to_top"] = abs(M["chain_top_z_m"] - mx[2]) < TOL
    return {"path": path, "bay": bay, "checks": C, "metrics": M, "status": "PASS" if all(C.values()) else "FAIL",
            "failed": [k for k, v in C.items() if not v]}


def validate():
    man = json.load(open(os.path.join(OUT, "build_manifest_nw.json")))
    rows = []
    for a in man["assets"]:
        bay = a["asset"][:-len("_nw")]
        r = check(a["fbx"], bay); r["asset"] = a["asset"]; r["sha256_matches_build"] = sha(a["fbx"]) == a["sha256"]
        r["source_sha256_matches"] = sha(os.path.join(CUR, bay + ".fbx")) == a["source_sha256"]
        rows.append(r)
    ctl = {}
    for name, (bay, _opts, must) in CONTROLS.items():
        r = check(man["controls"][name]["fbx"], bay)
        ctl[name] = {"expected_failures": sorted(must), "observed_failures": r["failed"], "ok": r["status"] == "FAIL" and must <= set(r["failed"])}
    # the CURRENT bay itself is the coil-carrying control: it must fail no_coil
    r = check(os.path.join(CUR, "SM_FenceBay_short_open.fbx"), "SM_FenceBay_short_open")
    ctl["current_bay_with_coil"] = {"expected_failures": ["no_coil"], "observed_failures": r["failed"],
                                    "ok": r["status"] == "FAIL" and "no_coil" in r["failed"]}
    ok = all(r["status"] == "PASS" and r["sha256_matches_build"] and r["source_sha256_matches"] for r in rows) and all(c["ok"] for c in ctl.values())
    out = {"status": "PASS" if ok else "FAIL", "blender": bpy.app.version_string, "assets": rows, "controls": ctl}
    json.dump(out, open(os.path.join(OUT, "validation_nw.json"), "w"), indent=1, default=list)
    print("NW_VALIDATE status=%s controls=%s" % (out["status"], {k: v["ok"] for k, v in ctl.items()}))
    for r in rows:
        print("NW_ROW", r["asset"], r["status"], r["failed"], "top_z=%.6f" % r["metrics"]["new_top_z_m"], r["metrics"]["delta_mm"])
    if not ok: print("NW_VALIDATE_FAILED")


# --------------------------------- render ------------------------------------
def render():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bw", os.path.join(OUT, "barbed_wire.py"))
    bw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bw)  # module name "bw": barbed_wire.py's __main__ block does not run
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bw.scene_setup((1800, 1000), 40); m = bw.render_mats()
    f = lambda n: os.path.join(OUT, "fbx", n + ".fbx")
    cur = os.path.join(CUR, "SM_FenceBay_short_open.fbx")
    TOP = 3.026763439178467
    # left: today's stack (current bay x3 rows); right: _nw rows 0-1 + _bwc on the top row
    for side, stack in ((-1, [cur, cur, cur]), (1, [f("SM_FenceBay_short_open_nw"), f("SM_FenceBay_short_open_nw"), f("SM_FenceBay_short_open_bwc")])):
        for t in range(2):
            for row, path in enumerate(stack):
                x = side * 4.2 + (t - 0.5) * 3.36
                bw.import_lod0(path, m, (x, 0, row * TOP))
    bw.label("TODAY: coil on every row", (-4.2, -0.6, 0.2), 0.22)
    bw.label("_nw rows + _bwc top row", (4.2, -0.6, 0.2), 0.22)
    bw.cam(sc, (0, -17.5, 4.6), (0, 0, 4.4), 30)
    sc.render.filepath = os.path.join(OUT, "renders", "stack_nw_compare.png"); bpy.ops.render.render(write_still=True)
    print("NW_RENDER_OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["build"]
    {"build": build, "validate": validate, "render": render}[argv[0]]()
