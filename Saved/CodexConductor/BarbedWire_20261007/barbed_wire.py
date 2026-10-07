"""Barbed-wire fence kit for the underpass FenceBay short family (Gary, 7 Oct 2026).

Headless Blender only:  blender -b --factory-startup --python barbed_wire.py -- <stage>
  build     -> fbx/*.fbx (+ fbx_negctl/ deliberately broken copy) + build_manifest.json + Source.blend
  validate  -> validation.json  (factory-clean FBX re-import; negative control must FAIL)
  render    -> renders/*.png

Frame = the short family's (Tools/FlatV3/build_fence_bay.py:57-80, measured re-import of
SM_FenceBay_short_open.fbx -> current_probe.json): metres, X along the fence, Z up,
walkway = Blender -Y (Unreal +Y).  The C++ placer fits instances by mesh BOUNDS
(InfinityStageStructureActor.cpp:183-196 FitMeshToTimber), so a drop-in bay must keep
LOD0 bounds X = +-1.68, Z = 0..3.026763 and the Y bounds centre (-0.0032468).
"""
import bpy, math, json, sys, os, hashlib, random
from mathutils import Vector

OUT = r"E:\PussStage\Saved\CodexConductor\BarbedWire_20261007"
CUR = r"E:\PussStage\DerivedAssets\FlatV3\FenceBay\short"
TEX = r"E:\PussStage\DerivedAssets\FlatV3\FenceBay\Textures"

# ---- drop-in targets (measured from the current FBX, current_probe.json) ----
HALF = 1.68
TOP = 3.026763439178467
YC = (-0.0928683876991272 + 0.08637472242116928) * 0.5
# ---- unchanged short-family members (build_fence_bay.py:68-80) --------------
CHAIN_Y = -0.02; MASK_TILE = 0.96; CHAIN_H = 2.70
RAIL_Y = -0.045; RAIL_Z = 2.68; RAIL_R = 0.021
DOOR_X = (0.20, 1.10); DOOR_H = 2.10; JAMB_R = 0.024
UVU = 0.96  # 1 UV unit = 0.96 m, the master's PhysicalTileSizeCm (M_FenceBay_Masked_Master_spec.json:22)

P = dict(
    post_r=0.0508,        # 101.6 mm OD round steel (was 76 mm SM_FencePost_short, unplaced)
    arm_r=0.016,          # 32 mm outrigger tube
    arm_spread=0.26, arm_rise=0.26,   # 45 deg Y-outrigger
    wire_r=0.005,         # each of the two twisted wires: 10 mm dia -> 20 mm strand envelope
    twist_p=0.084,        # 40 twists per 3.36 m tile (tiles seamlessly)
    barb_sp=0.112,        # 30 barbs per tile
    barb_l=0.032, barb_r=0.0035,      # 4-point barb, 64 mm tip to tip, 7 mm wire
    coil_r=0.15, coil_loops=28,       # concertina: 300 mm dia, 120 mm pitch
    top_offset=0.0, lods=3,
)
MUTANT = dict(barb_sp=0.15, top_offset=0.04, post_r=0.03, lods=2)

SLOT_CHAIN, SLOT_METAL, SLOT_WIRE = "M_FenceChain_Masked", "M_FenceMetal", "M_BarbedWire"


class Acc:
    def __init__(s): s.v = []; s.f = []; s.uv = []; s.m = []

    def tube(s, pts, radii, sides, mat, cap1=False, uv_upright=False):
        n = len(pts); pts = [Vector(p) for p in pts]
        if isinstance(radii, (int, float)): radii = [radii] * n
        T = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
        t0 = T[0]; ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
        N = (ref - t0 * ref.dot(t0)).normalized()
        L = [0.0]
        for i in range(1, n): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
        base = len(s.v)
        for i in range(n):
            if i:
                N = N - T[i] * N.dot(T[i])
                if N.length < 1e-9:
                    N = (ref - T[i] * ref.dot(T[i]))
                N.normalize()
            B = T[i].cross(N)
            for k in range(sides):
                th = 2 * math.pi * k / sides
                s.v.append(tuple(pts[i] + radii[i] * (math.cos(th) * N + math.sin(th) * B)))
        for i in range(n - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                a = base + i * sides + k; b = base + i * sides + k2
                c = base + (i + 1) * sides + k2; d = base + (i + 1) * sides + k
                def uv(li, kk, r):
                    around = 2 * math.pi * r * kk / sides / UVU; along = L[li] / UVU
                    return (around, along) if uv_upright else (along, around)
                ua, ub = uv(i, k, radii[i]), uv(i, k + 1, radii[i])
                uc, ud = uv(i + 1, k + 1, radii[i + 1]), uv(i + 1, k, radii[i + 1])
                s.f.append((a, b, c)); s.uv.append((ua, ub, uc)); s.m.append(mat)
                s.f.append((a, c, d)); s.uv.append((ua, uc, ud)); s.m.append(mat)
        if cap1:
            ring = [base + (n - 1) * sides + k for k in range(sides)]
            ci = len(s.v); s.v.append(tuple(pts[-1]))
            for k in range(sides):
                a, b = ring[k], ring[(k + 1) % sides]
                s.f.append((ci, a, b)); s.m.append(mat)
                s.uv.append(tuple((s.v[x][0] / UVU, s.v[x][1] / UVU) for x in (ci, a, b)))

    def quad_plane(s, quads, y, mat):
        for qa, qb, za, zb in quads:
            base = len(s.v)
            for x, z in ((qa, za), (qa, zb), (qb, zb), (qb, za)):
                s.v.append((x, y, z))
            uvs = [((x + HALF) / MASK_TILE, z / MASK_TILE) for x, z in ((qa, za), (qa, zb), (qb, zb), (qb, za))]
            s.f.extend([(base, base + 1, base + 2), (base, base + 2, base + 3)])
            s.uv.extend([(uvs[0], uvs[1], uvs[2]), (uvs[0], uvs[2], uvs[3])]); s.m.extend([mat, mat])

    def translate(s, start, d):
        for i in range(start, len(s.v)):
            x, y, z = s.v[i]; s.v[i] = (x + d[0], y + d[1], z + d[2])

    def clamp_x(s, h=HALF):
        s.v = [(min(h, max(-h, x)), y, z) for x, y, z in s.v]

    def bounds(s):
        return [min(v[i] for v in s.v) for i in range(3)], [max(v[i] for v in s.v) for i in range(3)]

    def to_object(s, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(s.v, [], s.f)
        me.update()
        uvl = me.uv_layers.new(name="UVMap")
        for poly, uvs in zip(me.polygons, s.uv):
            for li, uv in zip(poly.loop_indices, uvs): uvl.data[li].uv = uv
        for m in mats: me.materials.append(m)
        for poly, mi in zip(me.polygons, s.m): poly.material_index = mi
        ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
        return ob


# ------------------------------- wire pieces ---------------------------------
def frame(T):
    ref = Vector((0, 0, 1)) if abs(T.z) < 0.9 else Vector((1, 0, 0))
    N = (ref - T * ref.dot(T)).normalized(); return N, T.cross(N)


def barb(acc, c, T, phi, lod, mat, env, p, wrap=True):
    """Four-point barb: two short wires crossed at 90 deg, tips leaning along the
    strand, wrapped once around it (LOD0)."""
    c = Vector(c); N, B = frame(T)
    L = p["barb_l"]; r = p["barb_r"]; tip = 0.0007
    sides = 4 if lod == 0 else 3
    for w in (0, 1):
        ang = phi + w * math.pi / 2
        d = math.cos(ang) * N + math.sin(ang) * B
        lean = T * (0.011 if w == 0 else -0.011)
        pts = [c - L * d + lean, c + T * (0.003 if w == 0 else -0.003), c + L * d + lean]
        acc.tube(pts, [tip, r, tip], sides, mat)
    if lod == 0 and wrap:
        wr = env + r * 0.6
        pts = []
        for j in range(9):
            a = phi + 2 * math.pi * 1.25 * j / 8
            pts.append(c + T * (-0.008 + 0.016 * j / 8) + wr * (math.cos(a) * N + math.sin(a) * B))
        acc.tube(pts, r * 0.85, 3, mat)


def barb_phi(i, side):
    base = math.radians((17 + i * 53) % 90)
    return -base if side < 0 else base


def strand(acc, y0, z0, lod, mat, p, side=1):
    """Two wires twisted round each other along X, barbs every barb_sp; periodic in 2*HALF."""
    wr = p["wire_r"]; e = wr
    n = max(1, int(round(2 * HALF / p["barb_sp"]))); sp = 2 * HALF / n
    if p is not P and p.get("barb_sp") != P["barb_sp"]:
        sp = p["barb_sp"]; n = int(2 * HALF / sp)
    if lod == 0:
        twists = int(round(2 * HALF / p["twist_p"])); segs = twists * 6
        for w in (0, 1):
            pts = []
            for j in range(segs + 1):
                x = -HALF + 2 * HALF * j / segs
                th = 2 * math.pi * twists * j / segs + w * math.pi
                pts.append((x, y0 + e * math.cos(th), z0 + e * math.sin(th)))
            acc.tube(pts, wr, 5, mat)
    else:
        acc.tube([(-HALF, y0, z0), (HALF, y0, z0)], (1.8 * wr if lod == 1 else 2.4 * wr), 5 if lod == 1 else 3, mat)
    if lod <= 1:
        for i in range(n):
            x = -HALF + (i + 0.5) * sp
            barb(acc, (x, y0, z0), Vector((1, 0, 0)), barb_phi(i, side), lod, mat, 2 * wr, p)


def concertina(acc, yc, zc, lod, mat, p):
    """Helical concertina of single barbed wire; integer loops per tile, radius and lean
    jitter periodic in the tile, so a run reads as clipped, uneven coils, not a sine."""
    R = p["coil_r"]; loops = p["coil_loops"]; pitch = 2 * HALF / loops
    per_loop = {0: 24, 1: 12, 2: 8}[lod]
    N = loops * per_loop; pts = []
    for j in range(N + 1):
        t = 2 * math.pi * loops * j / N
        r = R * (1 + 0.05 * math.sin(t * 3 / loops) + 0.03 * math.sin(t * 7 / loops + 1.0))
        x = -HALF + pitch * t / (2 * math.pi) + 0.035 * math.sin(t)  # loops lean: clipped look
        pts.append((x, yc + r * math.cos(t), zc + r * math.sin(t)))
    wr = p["wire_r"] * (1.2 if lod == 0 else 1.6)
    acc.tube(pts, wr, {0: 5, 1: 4, 2: 3}[lod], mat)
    if lod <= 1:
        P3 = [Vector(q) for q in pts]
        Ls = [0.0]
        for a, b in zip(P3, P3[1:]): Ls.append(Ls[-1] + (b - a).length)
        nb = int(round(Ls[-1] / p["barb_sp"])) // (1 if lod == 0 else 2)
        step = Ls[-1] / nb; j = 0
        for i in range(nb):
            s = (i + 0.5) * step
            while Ls[j + 1] < s: j += 1
            f = (s - Ls[j]) / max(1e-9, Ls[j + 1] - Ls[j])
            c = P3[j].lerp(P3[j + 1], f); T = (P3[j + 1] - P3[j]).normalized()
            barb(acc, c, T, math.radians((i * 61) % 90), lod, mat, wr, p, wrap=False)
    # clips tying neighbouring loops (the concertina signature)
    if lod == 0:
        for k in range(loops):
            x = -HALF + (k + 0.5) * pitch
            for a in (math.radians(100), math.radians(260)):
                yy = yc + R * math.cos(a); zz = zc + R * math.sin(a)
                acc.tube([(x - 0.03, yy, zz), (x + 0.03, yy, zz)], 0.006, 4, mat)


# ------------------------------- assemblies ----------------------------------
def post_and_arms(acc, x, y, apex, lod, mat, p, both=True):
    sides = {0: 16, 1: 8, 2: 6}[lod]; asides = {0: 6, 1: 4, 2: 3}[lod]
    acc.tube([(x, y, 0.0), (x, y, apex + 0.04)], p["post_r"], sides, mat, cap1=True, uv_upright=True)
    for sgn in ((-1, 1) if both else (1,)):
        acc.tube([(x, y, apex), (x, y + sgn * p["arm_spread"], apex + p["arm_rise"])], p["arm_r"], asides, mat, cap1=True)


def bay(kind, lod, p, apex, dy):
    """kind: open_bw | door_gap_bw | open_bwc"""
    acc = Acc()
    if kind.startswith("door"):
        x0, x1 = DOOR_X
        acc.quad_plane(((-HALF, x0, 0.0, CHAIN_H), (x1, HALF, 0.0, CHAIN_H), (x0, x1, DOOR_H, CHAIN_H)), CHAIN_Y, 0)
    else:
        acc.quad_plane(((-HALF, HALF, 0.0, CHAIN_H),), CHAIN_Y, 0)
    rs = {0: 8, 1: 4, 2: 4}[lod]
    acc.tube([(-HALF, RAIL_Y, RAIL_Z), (HALF, RAIL_Y, RAIL_Z)], RAIL_R, rs, 1)
    if kind.startswith("door"):
        x0, x1 = DOOR_X
        for x in (x0 - JAMB_R, x1 + JAMB_R):
            acc.tube([(x, RAIL_Y, 0.0), (x, RAIL_Y, RAIL_Z)], JAMB_R, rs, 1, uv_upright=True)
        acc.tube([(x0 - JAMB_R, RAIL_Y, DOOR_H + RAIL_R), (x1 + JAMB_R, RAIL_Y, DOOR_H + RAIL_R)], RAIL_R, rs, 1)
    top_start = len(acc.v)
    y = YC + dy; px = -HALF + p["post_r"]
    post_and_arms(acc, px, y, apex, lod, 1, p)
    sp, rise = p["arm_spread"], p["arm_rise"]
    lift = p["arm_r"] + 2 * p["wire_r"]
    if kind.endswith("bwc"):
        for sgn in (-1, 1):
            strand(acc, y + sgn * sp, apex + rise + lift, lod, 2, p, side=sgn)
        concertina(acc, y, apex + 0.13, lod, 2, p)
    else:
        for t in (0.5, 1.0):
            for sgn in (-1, 1):
                strand(acc, y + sgn * sp * t, apex + rise * t + lift, lod, 2, p, side=sgn)
    acc.clamp_x()
    return acc, top_start


def fit_bay(kind, p):
    """Two-pass fit: LOD0 bounds top == TOP (+top_offset) and Y centre == YC."""
    apex, dy = 2.70, 0.0
    for _ in range(3):
        acc, _s = bay(kind, 0, p, apex, dy)
        mn, mx = acc.bounds()
        apex += (TOP + p["top_offset"]) - mx[2]
        dy += YC - (mn[1] + mx[1]) * 0.5
    return apex, dy


# ------------------------------- materials -----------------------------------
def mat_simple(name, col, metal, rough):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*col, 1); bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return m


def export_group(asset, lods, out_dir, extras=()):
    group = bpy.data.objects.new(asset + "_LODGroup", None); bpy.context.collection.objects.link(group)
    group["fbx_type"] = "LodGroup"; group["LODOrder"] = ",".join("LOD%d" % i for i in range(len(lods)))
    for o in list(lods) + list(extras): o.parent = group
    bpy.ops.object.select_all(action="DESELECT"); group.select_set(True)
    for o in list(lods) + list(extras): o.select_set(True)
    bpy.context.view_layer.objects.active = lods[0]
    # Same exporter settings as the imported kit (build_fence_bay.py:1034), which
    # measured lods=2 in Unreal (fbs_import_FV3FBS-20261005-01.json).
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, asset + ".fbx"), use_selection=True,
                             object_types={"MESH", "EMPTY"}, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             use_space_transform=True, bake_space_transform=False, mesh_smooth_type="FACE",
                             use_mesh_modifiers=True, use_triangles=True, add_leaf_bones=False, bake_anim=False,
                             axis_forward="-Z", axis_up="Y")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = [mat_simple(SLOT_CHAIN, (0.3, 0.33, 0.3), 0.7, 0.6), mat_simple(SLOT_METAL, (0.24, 0.27, 0.25), 0.8, 0.45),
            mat_simple(SLOT_WIRE, (0.35, 0.33, 0.30), 0.85, 0.5)]
    fdir = os.path.join(OUT, "fbx"); ndir = os.path.join(OUT, "fbx_negctl")
    os.makedirs(fdir, exist_ok=True); os.makedirs(ndir, exist_ok=True)
    manifest = {"frame": "short family; X +-1.68 m, Z up, walkway = Blender -Y", "params": P, "assets": []}

    def emit(asset, accs, slotmats, out, extra=None):
        objs = [a.to_object("%s_LOD%d" % (asset, i), slotmats) for i, a in enumerate(accs)]
        export_group(asset, objs, out)
        row = {"asset": asset, "fbx": os.path.join(out, asset + ".fbx"), "tris": [len(a.f) for a in accs]}
        row["sha256"] = sha(row["fbx"]); row.update(extra or {})
        for o in objs + [bpy.data.objects[asset + "_LODGroup"]]: bpy.data.objects.remove(o, do_unlink=True)
        return row

    for kind in ("open_bw", "door_gap_bw", "open_bwc"):
        apex, dy = fit_bay(kind, P)
        accs = [bay(kind, l, P, apex, dy)[0] for l in range(P["lods"])]
        manifest["assets"].append(emit("SM_FenceBay_short_" + kind, accs, mats, fdir,
                                       {"apex_z": apex, "dy": dy, "bounds_lod0": accs[0].bounds()}))
    apex_bw = fit_bay("open_bw", P)[0]
    # stand-alone post: pivot as SM_FencePost_short (origin at base, axis at y=-0.065)
    accs = []
    for l in range(P["lods"]):
        a = Acc(); post_and_arms(a, 0.0, -0.065, apex_bw, l, 0, P); accs.append(a)
    manifest["assets"].append(emit("SM_FencePost_short_bw", accs, [mats[1]], fdir, {"apex_z": apex_bw}))
    accs = []
    for l in range(P["lods"]):
        a = Acc(); strand(a, 0.0, 0.0, l, 0, P); a.clamp_x(); accs.append(a)
    manifest["assets"].append(emit("SM_BarbedWire_Strand_336", accs, [mats[2]], fdir))
    accs = []
    for l in range(P["lods"]):
        a = Acc(); concertina(a, 0.0, 0.0, l, 0, P); a.clamp_x(); accs.append(a)
    manifest["assets"].append(emit("SM_BarbedWire_Concertina_336", accs, [mats[2]], fdir))
    # ---- negative control: same builder, deliberately wrong numbers ----
    pm = dict(P); pm.update(MUTANT)
    apex, dy = fit_bay("open_bw", pm)
    accs = [bay("open_bw", l, pm, apex, dy)[0] for l in range(pm["lods"])]
    manifest["negative_control"] = emit("SM_FenceBay_short_open_bw", accs, mats, ndir, {"mutations": MUTANT})
    json.dump(manifest, open(os.path.join(OUT, "build_manifest.json"), "w"), indent=1)
    print("BW_BUILD_OK")


# ------------------------------- validation ----------------------------------
def islands(me, face_filter):
    parent = list(range(len(me.vertices)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    used = set()
    for poly in me.polygons:
        if not face_filter(poly): continue
        vs = list(poly.vertices); used.update(vs)
        for v in vs[1:]:
            ra, rb = find(vs[0]), find(v)
            if ra != rb: parent[rb] = ra
    groups = {}
    for v in used: groups.setdefault(find(v), []).append(v)
    return [sorted(g) for g in groups.values()]


def bbox(co, idx):
    pts = [co[i] for i in idx]
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def check_asset(path, kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    meshes = sorted([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: o.name)
    groups = [o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.name.endswith("_LODGroup")]
    lods = {int(o.name.split("_LOD")[-1].split(".")[0]): o for o in meshes if "_LOD" in o.name}
    C = {}; M = {}
    C["lod_count"] = len(lods) == 3 and len(groups) == 1 and all(o.parent == groups[0] for o in lods.values())
    C["triangulated"] = all(len(p.vertices) == 3 for o in meshes for p in o.data.polygons)
    tris = [len(lods[i].data.polygons) for i in sorted(lods)]; M["tris"] = tris
    C["lod_reduces"] = all(tris[i + 1] < 0.45 * tris[i] or tris[i] < 500 for i in range(len(tris) - 1))
    l0 = lods[0]; co = [l0.matrix_world @ v.co for v in l0.data.vertices]
    mn = [min(p[k] for p in co) for k in range(3)]; mx = [max(p[k] for p in co) for k in range(3)]
    M["bounds_lod0"] = [mn, mx]
    slots = [s.material.name.split(".")[0] if s.material else None for s in l0.material_slots]; M["slots"] = slots
    for i, o in lods.items():
        if i == 0: continue
        c2 = [o.matrix_world @ v.co for v in o.data.vertices]
        ok = all(min(p[k] for p in c2) >= mn[k] - 0.012 and max(p[k] for p in c2) <= mx[k] + 0.012 for k in range(3))
        C["lod%d_inside_lod0" % i] = ok
    if kind.startswith("bay"):
        C["slots"] = slots == [SLOT_CHAIN, SLOT_METAL, SLOT_WIRE]
        C["bounds_x"] = abs(mn[0] + HALF) < 5e-4 and abs(mx[0] - HALF) < 5e-4
        C["bottom_z"] = abs(mn[2]) < 5e-4
        C["top_z"] = abs(mx[2] - TOP) < 5e-4
        C["y_centre"] = abs((mn[1] + mx[1]) * 0.5 - YC) < 1e-3
        me = l0.data
        chain = [p for p in me.polygons if slots[p.material_index] == SLOT_CHAIN]
        C["chain_unchanged"] = (len(chain) == (6 if "door" in kind else 2)) and all(abs(co[v][1] - CHAIN_Y) < 1e-5 for p in chain for v in p.vertices)
        uvl = me.uv_layers.active.data
        C["chain_uv_physical"] = all(abs(uvl[li].uv[0] - (co[me.loops[li].vertex_index][0] + HALF) / MASK_TILE) < 1e-4 and
                                     abs(uvl[li].uv[1] - co[me.loops[li].vertex_index][2] / MASK_TILE) < 1e-4
                                     for p in chain for li in p.loop_indices)
        # post: tall metal island
        metal = islands(me, lambda p: slots[p.material_index] == SLOT_METAL)
        posts = []
        for g in metal:
            a, b = bbox(co, g)
            if b[2] - a[2] > 2.0 and a[0] < -HALF + 1e-3 and b[0] - a[0] < 0.3: posts.append((a, b, g))
        C["one_post"] = len(posts) == 1
        if posts:
            a, b, g = posts[0]; r = (b[0] - a[0]) * 0.5; M["post_radius_m"] = r
            C["post_radius"] = abs(r - P["post_r"]) < 1e-3
            C["post_on_joint"] = abs(a[0] + HALF) < 5e-4 and abs(a[2]) < 5e-4
            # V down in Unreal == Blender v rising with z (as the chain plane, imported fine)
            zs, vs = [], []
            gs = set(g)
            for poly in me.polygons:
                if all(v in gs for v in poly.vertices) and abs(poly.normal.z) < 0.5:
                    for li in poly.loop_indices:
                        zs.append(co[me.loops[li].vertex_index][2]); vs.append(uvl[li].uv[1])
            n = len(zs); mz = sum(zs) / n; mv = sum(vs) / n
            cov = sum((z - mz) * (v - mv) for z, v in zip(zs, vs))
            C["post_uv_v_runs_with_z"] = cov > 0
        # wires and barbs
        wire = islands(me, lambda p: slots[p.material_index] == SLOT_WIRE)
        long_w, small = [], []
        for g in wire:
            a, b = bbox(co, g)
            if b[0] - a[0] > 3.3 and b[1] - a[1] < 0.03 and b[2] - a[2] < 0.03: long_w.append((a, b, g))
            elif max(b[k] - a[k] for k in range(3)) < 0.1: small.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
        axes = []
        for a, b, g in long_w:
            ax = ((a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
            if not any(abs(ax[0] - q[0]) < 0.01 and abs(ax[1] - q[1]) < 0.01 for q in axes): axes.append(ax)
        M["straight_strands"] = len(axes); M["straight_wires"] = len(long_w)
        want = 2 if kind.endswith("bwc") else 4
        C["strand_count"] = len(axes) == want and len(long_w) == 2 * want
        # gauge: vertex rings (5 per ring) of the twisted wires
        radii = []
        for a, b, g in long_w:
            for r0 in range(5, len(g) - 10, 5 * 37):
                ring = [co[g[r0 + k]] for k in range(5)]
                c = sum(ring, Vector()) / 5; radii.append(sum((q - c).length for q in ring) / 5)
        if radii:
            M["wire_radius_m"] = sum(radii) / len(radii)
            C["wire_gauge"] = all(abs(r - P["wire_r"]) < 2.5e-4 for r in radii)
        # periodic ends: first and last ring centroid of each twisted wire match
        ends = []
        for a, b, g in long_w:
            r0 = [co[g[k]] for k in range(5)]; r1 = [co[g[-5 + k]] for k in range(5)]
            c0 = sum(r0, Vector()) / 5; c1 = sum(r1, Vector()) / 5
            ends.append(math.hypot(c0[1] - c1[1], c0[2] - c1[2]))
        C["strand_tiles_seamlessly"] = bool(ends) and max(ends) < 1e-3
        # barb spacing per strand (cluster small islands by x)
        spacing_ok = bool(axes); sp_all = []
        for ax in axes:
            xs = sorted(x for x, y, z in small if math.hypot(y - ax[0], z - ax[1]) < 0.02)
            cl = []
            for x in xs:
                if cl and x - cl[-1][-1] < 0.03: cl[-1].append(x)
                else: cl.append([x])
            cx = [sum(c) / len(c) for c in cl]
            d = [b - a for a, b in zip(cx, cx[1:])]
            if cx: d.append((cx[0] + HALF) + (HALF - cx[-1]))  # across the tile joint
            sp_all.extend(d)
            spacing_ok &= len(cx) == 30 and all(abs(x - 0.112) < 0.003 for x in d)
        M["barb_spacing_m"] = [min(sp_all), max(sp_all)] if sp_all else None
        C["barb_spacing"] = spacing_ok
    elif kind == "post":
        C["slots"] = slots == [SLOT_METAL]
        C["pivot_base"] = abs(mn[2]) < 5e-4
        me = l0.data
        g = max(islands(me, lambda p: True), key=lambda g: bbox(co, g)[1][2] - bbox(co, g)[0][2])
        a, b = bbox(co, g); M["post_axis"] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; M["post_radius_m"] = (b[0] - a[0]) / 2
        C["pivot_axis_matches_SM_FencePost_short"] = abs((a[0] + b[0]) / 2) < 5e-4 and abs((a[1] + b[1]) / 2 + 0.065) < 5e-4
        C["post_radius"] = abs((b[0] - a[0]) / 2 - P["post_r"]) < 1e-3
    else:
        C["slots"] = slots == [SLOT_WIRE]
        C["bounds_x"] = abs(mn[0] + HALF) < 5e-4 and abs(mx[0] - HALF) < 5e-4
        C["axis_at_origin"] = abs((mn[1] + mx[1]) / 2) < 0.02 and abs((mn[2] + mx[2]) / 2) < 0.02
    return {"path": path, "checks": C, "metrics": M, "status": "PASS" if all(C.values()) else "FAIL",
            "failed": [k for k, v in C.items() if not v]}


def validate():
    man = json.load(open(os.path.join(OUT, "build_manifest.json")))
    kinds = {"SM_FenceBay_short_open_bw": "bay_open_bw", "SM_FenceBay_short_door_gap_bw": "bay_door_bw",
             "SM_FenceBay_short_open_bwc": "bay_open_bwc", "SM_FencePost_short_bw": "post",
             "SM_BarbedWire_Strand_336": "module", "SM_BarbedWire_Concertina_336": "module"}
    rows = []
    for a in man["assets"]:
        r = check_asset(a["fbx"], kinds[a["asset"]]); r["asset"] = a["asset"]
        r["sha256_matches_build"] = sha(a["fbx"]) == a["sha256"]; rows.append(r)
    neg = check_asset(man["negative_control"]["fbx"], "bay_open_bw")
    expected = {"top_z", "barb_spacing", "post_radius", "lod_count"}
    neg_ok = neg["status"] == "FAIL" and expected.issubset(set(neg["failed"]))
    # current asset through the same harness (reference row, expected to fail the new checks)
    cur = check_asset(os.path.join(CUR, "SM_FenceBay_short_open.fbx"), "bay_open_bw")
    status = "PASS" if all(r["status"] == "PASS" and r["sha256_matches_build"] for r in rows) and neg_ok else "FAIL"
    out = {"status": status, "blender": bpy.app.version_string, "assets": rows,
           "negative_control": {"expected_failures": sorted(expected), "observed_failures": neg["failed"], "ok": neg_ok},
           "current_short_open_reference": {"failed": cur["failed"], "metrics": cur["metrics"]}}
    json.dump(out, open(os.path.join(OUT, "validation.json"), "w"), indent=1, default=list)
    print("BW_VALIDATE status=%s neg_ok=%s" % (status, neg_ok))
    if status != "PASS": print("BW_VALIDATE_FAILED")


# --------------------------------- renders -----------------------------------
def render_mats():
    tex = bpy.data.images.load(os.path.join(TEX, "T_FenceBay_ChainMaskPreview.png"))
    chain = bpy.data.materials.new("R_Chain"); chain.use_nodes = True
    nt = chain.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = tex
    b.inputs["Base Color"].default_value = (0.42, 0.44, 0.42, 1); b.inputs["Metallic"].default_value = 0.8
    b.inputs["Roughness"].default_value = 0.5
    tex.colorspace_settings.name = "Non-Color"
    nt.links.new(t.outputs["Color"], b.inputs["Alpha"])
    def steel(name, rust):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
        b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 9.0; nz.inputs["Detail"].default_value = 8.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.5 - rust * 0.25
        ramp.color_ramp.elements[1].position = 0.62
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs[6].default_value = (0.24, 0.085, 0.03, 1); mix.inputs[7].default_value = (0.62, 0.63, 0.62, 1)
        nt.links.new(ramp.outputs["Color"], mix.inputs[0]); nt.links.new(mix.outputs[2], b.inputs["Base Color"])
        rmix = nt.nodes.new("ShaderNodeMapRange"); rmix.inputs[3].default_value = 0.85; rmix.inputs[4].default_value = 0.32
        nt.links.new(ramp.outputs["Color"], rmix.inputs[0]); nt.links.new(rmix.outputs[0], b.inputs["Roughness"])
        b.inputs["Metallic"].default_value = 0.9
        return m
    return {SLOT_CHAIN: chain, SLOT_METAL: steel("R_Metal", 0.6), SLOT_WIRE: steel("R_Wire", 1.0)}


def import_lod0(path, mats, loc=(0, 0, 0), name=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    keep = None
    for o in new:
        if o.type == "MESH" and o.name.split(".")[0].endswith("_LOD0"): keep = o
    for o in new:
        if o is not keep: bpy.data.objects.remove(o, do_unlink=True)
    keep.parent = None; keep.location = loc
    for s in keep.material_slots:
        nm = s.material.name.split(".")[0] if s.material else SLOT_METAL
        s.material = mats.get(nm, mats[SLOT_METAL])
    return keep


def scene_setup(res, samples=48):
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples
    sc.cycles.use_denoising = True; sc.render.resolution_x, sc.render.resolution_y = res
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs["Color"].default_value = (0.05, 0.055, 0.065, 1)
    bg.inputs["Strength"].default_value = 1.0
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(55), 0, math.radians(-35)))
    sun = bpy.context.object; sun.data.energy = 3.5; sun.data.color = (1.0, 0.82, 0.62)
    bpy.ops.object.light_add(type="AREA", location=(0, -5, 4)); f = bpy.context.object; f.data.energy = 900; f.data.size = 6
    f.rotation_euler = (math.radians(60), 0, 0); f.data.color = (0.6, 0.72, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=200); fl = bpy.context.object
    fl.data.materials.append(mat_simple("R_Floor", (0.06, 0.06, 0.065), 0.0, 0.9))
    return sc


def cam(sc, loc, target, lens):
    bpy.ops.object.camera_add(location=loc); c = bpy.context.object; sc.camera = c; c.data.lens = lens
    c.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def label(text, loc, size=0.16):
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(90), 0, 0)); t = bpy.context.object
    t.data.body = text; t.data.size = size; t.data.align_x = "CENTER"
    t.data.materials.append(mat_simple("R_Label", (0.9, 0.9, 0.85), 0.0, 0.6))


def render():
    rd = os.path.join(OUT, "renders"); os.makedirs(rd, exist_ok=True)
    f = lambda n: os.path.join(OUT, "fbx", n + ".fbx")
    # 1. current vs new, side by side
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = scene_setup((1800, 820)); m = render_mats()
    for i, (path, txt) in enumerate(((os.path.join(CUR, "SM_FenceBay_short_open.fbx"), "CURRENT  SM_FenceBay_short_open"),
                                     (f("SM_FenceBay_short_open_bw"), "NEW  _bw  (4 barbed strands, Y-outrigger)"),
                                     (f("SM_FenceBay_short_open_bwc"), "NEW  _bwc  (concertina + 2 strands)"))):
        x = (i - 1) * 3.9
        import_lod0(path, m, (x, 0, 0)); label(txt, (x, -0.6, 0.15))
    cam(sc, (0, -7.2, 2.35), (0, 0, 2.05), 30)
    sc.render.filepath = os.path.join(rd, "compare_current_vs_new.png"); bpy.ops.render.render(write_still=True)
    # 2. close-up of barbs at the outrigger
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = scene_setup((1600, 1000), 64); m = render_mats()
    o = import_lod0(f("SM_FenceBay_short_open_bw"), m); import_lod0(f("SM_FenceBay_short_open_bw"), m, (3.36, 0, 0))
    man = json.load(open(os.path.join(OUT, "build_manifest.json")))
    apex = man["assets"][0]["apex_z"]
    tgt = (1.95, YC - 0.24, apex + 0.27)
    cam(sc, (2.42, YC - 0.98, apex + 0.47), tgt, 50)
    sc.render.filepath = os.path.join(rd, "closeup_barbs.png"); bpy.ops.render.render(write_still=True)
    # 3. fence run as the Structure actor stacks it: 2 rows x 9 tiles, 60x40 cm columns
    #    every 3 tiles on the column line 75 cm outboard (InfinityStageStructureActor.h:874).
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = scene_setup((1800, 900)); m = render_mats()
    base = import_lod0(f("SM_FenceBay_short_open_bw"), m)
    for t in range(9):
        for row in range(2):
            ob = base if (t == 0 and row == 0) else bpy.data.objects.new("Run_%d_%d" % (t, row), base.data)
            if ob is not base: bpy.context.collection.objects.link(ob)
            ob.location = (t * 3.36, 0, row * TOP)
    for c in range(4):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.68 + c * 10.08, 0.75, 4.0)); col = bpy.context.object
        col.scale = (0.6, 0.4, 8.0); col.data.materials.append(mat_simple("R_Col", (0.07, 0.06, 0.055), 0.6, 0.6))
    cam(sc, (-4.2, -4.0, 1.7), (12.0, 0.0, 3.6), 24)
    sc.render.filepath = os.path.join(rd, "fence_run.png"); bpy.ops.render.render(write_still=True)
    print("BW_RENDER_OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["build"]
    {"build": build, "validate": validate, "render": render}[argv[0]]()
