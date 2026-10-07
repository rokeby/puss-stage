"""Meshy bulb / housing cleanup (offline, Blender 4.4 headless). Spec: Docs/Conductor/MESHY_PROMPTS_BULB_HOUSING_2026-10-06.md
("After Meshy").

Run:
  blender.exe -b --factory-startup -P Tools/MeshyFixtures/build_meshy_fixtures.py -- [AssetName ...]

Per asset: import the Meshy FBX, orient, remove radial artifacts (bulbs), decimate to budget, scale to real size,
set the pivot, classify faces into material slots, (bulbs, clear) add a SYNTHETIC filament, (housings) build LOD1 and an
FBX LodGroup, export with the Flat V3 / Underpass FBX call, re-import the FBX to read back bounds / tris / slots / UVs,
copy textures, render a 3/4 contact view (textured + slot map) and write a per-asset JSON record.

Units: Blender metres; the FBX call (FBX_SCALE_UNITS, axis_forward=-X, axis_up=Z) is the one the Underpass kit and Flat
V3 imported with (UE cm = Blender m x 100).

Slot layout (spec): 0 = glow (bulb filament; + glass for frosted/opal; housing lens), 1 = metal, 2 = clear glass shell
(clear bulbs only).

Heuristics (all documented in cleanup_report.json per asset):
  BULB cap/glass split: radial profile r(z) in 60 bins; r_cap = median radius over 82-94 % height; scanning down from 90 %
    height, the cap ends at the first bin whose median radius > 1.12 x r_cap. Faces whose centroid is above that z are
    metal (slot 1), below are glass. The Meshy metallic map is sampled on both sides as a cross-check only.
  BULB artifact removal: faces whose centroid radius > 1.12 x the median radius of its z bin (bins with >= 30 faces)
    are deleted (thin planes / wings that image-to-3D glued to the shell).
  HOUSING lens: on the oriented LOD0 (beam +X): forward faces = n.x > 0.5 in the front 45 % of the length; candidates =
    forward faces whose base-colour texel luminance >= 0.15 (painted body fronts read darker, diag_lens.py); components
    by shared edges between candidates; the seed is the largest-area component near the body centre that covers its
    own centre (a -X ray through its area centroid first hits it; rejects annular rims); the lens is then every
    forward face within the seed's 95th-percentile radius and x range +/- 5 % of length (merges fresnel steps).
    LOD1 faces take the slot of the nearest LOD0 face (BVH).
  HOUSING length (for scale): x extent of the vertices within 1.35 x the lens radius of the beam axis.
  HOUSING pivot (tilt axis): for each side (+Y, -Y), vertices with |y| >= 0.93 x that side's max |y|, restricted to the
    middle 70 % of the length and below the top 15 % of the height (to exclude clamp and barn doors); pivot x,z = mean
    of both sides' medians, y = 0 after centring y on the lens axis.
"""
import bpy, bmesh, sys, os, re, json, math, shutil, hashlib
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshy_common as mc

OUT_ROOT = r"E:\PussStage\DerivedAssets\Lighting\MeshyClean"
RENDER_DIR = os.path.join(OUT_ROOT, "_renders")

BULBS = {
    "SM_Bulb_A60_Clear": dict(h=11.0, w=6.0, clear=True, fil="coil"),
    "SM_Bulb_A60_Frost": dict(h=11.0, w=6.0, clear=False),
    "SM_Bulb_A60_Opal": dict(h=11.0, w=6.0, clear=False),
    "SM_Bulb_A60_Worn": dict(h=11.0, w=6.0, clear=True, fil="coil"),
    "SM_Bulb_G95_Clear": dict(h=13.5, w=9.5, clear=True, fil="loop"),
    "SM_Bulb_C35_Clear": dict(h=10.0, w=3.5, clear=True, fil="coil_small"),
    "SM_Bulb_ST64_Cage": dict(h=14.0, w=6.4, clear=True, fil="cage"),
}
# beam = the source axis the lens faces (from the raw 6-view renders and the front-cap luminance score, diag_axes.py)
HOUSINGS = {
    "SM_Lantern_Fresnel": dict(beam="-Y", L=30.0, lens_d=15.0),
    "SM_Lantern_FresnelDoors": dict(beam="-Y", L=30.0),
    "SM_Lantern_Profile": dict(beam="-X", L=60.0),
    "SM_Lantern_ParCan": dict(beam="-Y", L=40.0, body_d=22.0),
    "SM_Lantern_Birdie": dict(beam="+Y", L=12.0, ambiguous_front=True),
    "SM_Lantern_1950s": dict(beam="-Y", L=35.0, ambiguous_front=True),
}
BEAM_ROT = {"+X": 0.0, "-X": math.pi, "+Y": -math.pi / 2, "-Y": math.pi / 2}  # rotation about Z taking beam to +X

BULB_TRIS = 3000
LOD0_TRIS = 12000
LOD1_TRIS = 3000
LENS_LUM_MIN = 0.15   # diag_lens.py: painted body fronts read < 0.15, lenses (glass or Meshy's metallic-painted glass) above

SLOT_COLOURS = [(1.0, 0.85, 0.1, 1), (0.35, 0.4, 0.5, 1), (0.3, 0.9, 1.0, 1)]


# ----------------------------------------------------------------------------------------------------------- helpers
def tris_of(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def apply_all(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def decimate_to(ob, target):
    """Collapse-decimate (triangulating) until tris <= target. Returns the ratio used."""
    start = tris_of(ob)
    if start <= target:
        return 1.0
    ratio = target / start * 0.97
    for _ in range(8):
        tmp = ob.data.copy()
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        n = sum(len(p.vertices) - 2 for p in ev.data.polygons)
        ob.modifiers.remove(mod)
        if n <= target:
            bpy.context.view_layer.objects.active = ob
            mod = ob.modifiers.new("dec", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = ratio
            mod.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.meshes.remove(tmp)
            return ratio
        bpy.data.meshes.remove(tmp)
        ratio *= target / n * 0.98
    raise RuntimeError(f"decimate failed to reach {target}")


def triangulate(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(ob.data); bm.free()


def make_material(name, colour):
    m = bpy.data.materials.new(name)
    m.diffuse_color = colour
    return m


def set_slots(ob, names):
    ob.data.materials.clear()
    for i, n in enumerate(names):
        ob.data.materials.append(make_material(n, SLOT_COLOURS[i]))


def face_arrays(ob):
    me = ob.data
    n = len(me.polygons)
    C = np.zeros(n * 3); N = np.zeros(n * 3); A = np.zeros(n)
    me.polygons.foreach_get("center", C); me.polygons.foreach_get("normal", N); me.polygons.foreach_get("area", A)
    return C.reshape(n, 3), N.reshape(n, 3), A


def vert_array(ob):
    me = ob.data
    V = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def tube(bm, pts, radius, mat, sides=4):
    """Sweep a `sides`-gon of `radius` along pts (list of Vector); returns tri count added."""
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized(); b = t.cross(a)
        ring = [bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * radius)
                for k in range(sides)]
        rings.append(ring)
    n = 0
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            f = bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k])); f.material_index = mat; n += 2
    for ring in (rings[0], rings[-1][::-1]):
        f = bm.faces.new(ring); f.material_index = mat; n += sides - 2
    return n


def face_texel_metal(ob, metal_arr):
    uvl = ob.data.uv_layers.active.data
    out = np.zeros(len(ob.data.polygons))
    for p in ob.data.polygons:
        uv = sum((uvl[i].uv for i in p.loop_indices), Vector((0, 0))) / p.loop_total
        out[p.index] = mc.sample(metal_arr, uv)[0]
    return out


# ------------------------------------------------------------------------------------------------------------ bulbs
def bulb_radial_cleanup(ob, rec):
    """Delete geometry outside the glass shell. Shell radius per z bin = median over 16 angular sectors of each
    sector's max radius (robust to a protrusion occupying a few sectors). Faces with centroid radius > 1.10 x shell
    + 0.5 % H, below 85 % of the height (the cap is never touched), are deleted, then islands < 0.5 % of faces."""
    C, N, A = face_arrays(ob)
    z = C[:, 2]; H = z.max() - z.min()
    top = C[z > z.min() + 0.82 * H]
    cx, cy = np.median(top[:, 0]), np.median(top[:, 1])
    r = np.hypot(C[:, 0] - cx, C[:, 1] - cy); th = np.arctan2(C[:, 1] - cy, C[:, 0] - cx)
    zb = np.clip(((z - z.min()) / (H + 1e-9) * 60).astype(int), 0, 59)
    sb = np.clip(((th + math.pi) / (2 * math.pi) * 16).astype(int), 0, 15)
    shell = np.full(60, np.nan)
    for b_ in range(60):
        m = [r[(zb == b_) & (sb == k)].max() for k in range(16) if ((zb == b_) & (sb == k)).any()]
        if m: shell[b_] = np.median(m)
    kill = (r > 1.10 * shell[zb] + 0.005 * H) & (z < z.min() + 0.85 * H)
    n_out = int(kill.sum())
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    if kill.any():
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(kill)[0]], context="FACES")
    # islands
    bm.faces.ensure_lookup_table()
    seen = set(); islands = []
    for f in bm.faces:
        if f.index in seen: continue
        st = [f]; seen.add(f.index); isl = []
        while st:
            g = st.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st.append(h)
        islands.append(isl)
    small = [f for isl in islands if len(isl) < 0.005 * len(bm.faces) for f in isl]
    if small:
        bmesh.ops.delete(bm, geom=small, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data); bm.free()
    rec["artifact_faces_removed_source"] = {"outside_shell": n_out, "small_islands": len(small),
                                            "of_source_faces": len(C)}
    rec["artifact_rule"] = ("delete faces with centroid radius > 1.10 x shell radius + 0.5 % H below 85 % height "
                            "(shell = per-z-bin median of 16 sector maxima), then islands < 0.5 % of faces")
    if n_out > 0.05 * len(C):
        rec["warnings"].append(f"{n_out} source faces lay OUTSIDE the glass (diag renders show a stem/filament assembly "
                               "displaced beside the bulb); deleted, not relocated")


def bulb_profile(ob):
    V = vert_array(ob)
    z = V[:, 2]
    zmin, zmax = z.min(), z.max(); H = zmax - zmin
    top = V[z > zmin + 0.82 * H]
    cx, cy = np.median(top[:, 0]), np.median(top[:, 1])
    r = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    bins = np.linspace(zmin, zmax, 61)
    med = []
    for i in range(60):
        s = (z >= bins[i]) & (z < bins[i + 1])
        med.append(float(np.median(r[s])) if s.sum() else float("nan"))
    hz = [(bins[i] + bins[i + 1]) / 2 for i in range(60)]
    capbins = [m for i, m in enumerate(med) if 0.82 <= (hz[i] - zmin) / H <= 0.94 and not math.isnan(m)]
    r_cap = float(np.median(capbins))
    z_cut = None
    for i in range(int(0.90 * 60), -1, -1):
        if not math.isnan(med[i]) and med[i] > 1.12 * r_cap:
            z_cut = bins[i + 1]; break
    imax = int(np.nanargmax(med))
    return dict(cx=cx, cy=cy, zmin=zmin, zmax=zmax, H=H, r_cap=r_cap, z_cut=z_cut, z_maxr=hz[imax], r_max=med[imax],
                profile=med)


def add_filament(ob, kind, prof, rec):
    """Synthetic filament (slot 0) + support wires (slot 1) inside the glass. Coordinates in final metres, pivot frame.
    Every sweep point is then checked against the glass profile and the whole assembly is shrunk in XY (about the bulb
    axis) until each point sits within 0.75 x the shell radius at its height."""
    H = prof["H"]; rmax = prof["r_max"]; zc = prof["z_maxr"]; zneck = prof["z_cut"]
    glass = H + zneck                                   # glass length below the cap (zneck < 0)
    items = []                                          # (points, radius, slot, sides)
    ends = []
    if kind in ("coil", "coil_small"):
        L = (0.36 if kind == "coil" else 0.5) * rmax
        rc = 0.0011 if kind == "coil" else 0.0008
        turns = 7 if kind == "coil" else 5
        zf = zc + (0.12 * H if kind == "coil" else 0.05 * H)
        n = turns * 8
        pts = [Vector((-L / 2 + L * i / n, rc * math.cos(2 * math.pi * turns * i / n), zf + rc * math.sin(2 * math.pi * turns * i / n)))
               for i in range(n + 1)]
        items.append((pts, 0.00035, 0, 4)); ends = [pts[0], pts[-1]]
    elif kind == "loop":
        R = 0.32 * rmax
        pts = [Vector((-R * math.cos(math.pi * i / 24), 0.0, zc - 0.05 * H + 1.1 * R * math.sin(math.pi * i / 24)))
               for i in range(25)]
        items.append((pts, 0.0005, 0, 4)); ends = [pts[0], pts[-1]]
    elif kind == "cage":
        Rc = 0.42 * rmax; ztop = zneck - 0.30 * glass; zbot = -H + 0.22 * glass
        for k in range(8):
            a0 = 2 * math.pi * k / 8; a1 = a0 + 2 * math.pi / 16
            p_top0 = Vector((0.35 * Rc * math.cos(a0), 0.35 * Rc * math.sin(a0), ztop))
            p_bot = [Vector((Rc * math.cos(a), Rc * math.sin(a), zbot)) for a in (a0, a1)]
            p_top1 = Vector((0.35 * Rc * math.cos(a1), 0.35 * Rc * math.sin(a1), ztop))
            seg = [p_top0.lerp(p_bot[0], t / 5) for t in range(6)] + [p_bot[1].lerp(p_top1, t / 5) for t in range(1, 6)]
            items.append((seg, 0.00025, 0, 3))
        ends = [Vector((0, 0, ztop)), Vector((0, 0, zbot))]
    for e in ends:                                       # lead-in / support wires from the neck (metal, slot 1)
        top = Vector((e.x * 0.3, e.y * 0.3, zneck - 0.004))
        items.append(([top, top.lerp(e, 0.5), e], 0.0003, 1, 3))
    # fit inside the glass
    zb = np.linspace(prof["zmin"], prof["zmax"], 61); zcen = (zb[:-1] + zb[1:]) / 2
    prof_r = np.array(prof["profile"]); ok = ~np.isnan(prof_r)
    def shell(z): return float(np.interp(z, zcen[ok], prof_r[ok]))
    f = 1.0; zlow_ok = True
    for pts, rad, _, _ in items:
        for p in pts:
            r = math.hypot(p.x, p.y)
            lim = 0.75 * shell(p.z) - rad
            if r > 1e-6: f = min(f, max(lim, 0.0) / r)
            if p.z < -H + 0.003: zlow_ok = False
    if f < 1.0:
        for pts, _, _, _ in items:
            for p in pts: p.x *= f; p.y *= f
    bm = bmesh.new(); bm.from_mesh(ob.data)
    tris0 = tris1 = 0
    for pts, rad, slot, sides in items:
        t = tube(bm, pts, rad, slot, sides)
        if slot == 0: tris0 += t
        else: tris1 += t
    bm.to_mesh(ob.data); bm.free()
    rec["synthetic_filament"] = {"kind": kind, "slot0_tris": tris0, "support_wire_tris_slot1": tris1,
                                 "xy_fit_factor": round(f, 3), "inside_glass_check": "all sweep points r <= 0.75 x shell(z)",
                                 "z_above_glass_bottom": zlow_ok,
                                 "note": "NOT from Meshy. Meshy's own filament is either only painted into the base colour "
                                         "(no interior geometry; diag_interior.py) or was generated OUTSIDE the glass "
                                         "(see warnings) and deleted. A procedural filament is the slot-0 part."}
    if not zlow_ok:
        rec["warnings"].append("synthetic filament reaches the glass bottom")
    return tris0 + tris1


def build_bulb(name, cfg, src, rec, metal_arr):
    ob = mc.import_source(src)
    rec["source_tris"] = tris_of(ob)
    apply_all(ob)
    bulb_radial_cleanup(ob, rec)
    # filament budget estimate so the total stays <= 3000
    fil_budget = {"coil": 520, "coil_small": 400, "loop": 260, "cage": 700}.get(cfg.get("fil"), 0) if cfg["clear"] else 0
    rec["decimate_ratio"] = decimate_to(ob, BULB_TRIS - fil_budget - 20)
    triangulate(ob)
    # scale by height, pivot at the cap tip
    prof = bulb_profile(ob)
    s = (cfg["h"] / 100.0) / prof["H"]
    ob.data.transform(Matrix.Translation((-prof["cx"], -prof["cy"], -prof["zmax"])))
    ob.data.transform(Matrix.Scale(s, 4))
    prof = bulb_profile(ob)
    # classify: metal above z_cut
    set_slots(ob, [f"M_{name}_Glow", f"M_{name}_Metal"] + ([f"M_{name}_Glass"] if cfg["clear"] else []))
    glass_slot = 2 if cfg["clear"] else 0
    C, N, A = face_arrays(ob)
    met = face_texel_metal(ob, metal_arr)
    mi = np.where(C[:, 2] > prof["z_cut"], 1, glass_slot)
    ob.data.polygons.foreach_set("material_index", mi.astype(np.int32))
    rec["classification"] = {
        "rule": "metal = face centroid above z_cut (first bin, scanning down from 90 % height, with median radius > 1.12 x r_cap)",
        "z_cut_cm": round(prof["z_cut"] * 100, 2), "r_cap_cm": round(prof["r_cap"] * 100, 2),
        "cap_height_cm": round(-prof["z_cut"] * 100, 2),
        "metallic_map_mean_above_cut": round(float(met[mi == 1].mean()), 3),
        "metallic_map_mean_below_cut": round(float(met[mi != 1].mean()), 3)}
    ob.data.update()
    if cfg["clear"]:
        add_filament(ob, cfg["fil"], prof, rec)
    ob.name = name; ob.data.name = name
    return ob, s


# --------------------------------------------------------------------------------------------------------- housings
def edge_components(ob, cand):
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    comp = -np.ones(len(bm.faces), int); k = 0
    for f in bm.faces:
        if not cand[f.index] or comp[f.index] >= 0: continue
        stack = [f]; comp[f.index] = k
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if cand[h.index] and comp[h.index] < 0:
                        comp[h.index] = k; stack.append(h)
        k += 1
    bm.free()
    return comp, k


def face_texel_lum(ob, arr):
    uvl = ob.data.uv_layers.active.data
    out = np.zeros(len(ob.data.polygons))
    for p in ob.data.polygons:
        uv = sum((uvl[i].uv for i in p.loop_indices), Vector((0, 0))) / p.loop_total
        out[p.index] = mc.lum(mc.sample(arr, uv)[:3])
    return out


def classify_lens(ob, rec_key, rec, bc_arr):
    C, N, A = face_arrays(ob)
    V = vert_array(ob)
    Lum = face_texel_lum(ob, bc_arr)
    xmin, xmax = V[:, 0].min(), V[:, 0].max(); L = xmax - xmin
    front = (N[:, 0] > 0.5) & (C[:, 0] > xmax - 0.45 * L)
    bvh = BVHTree.FromPolygons([v.co[:] for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])
    for lum_min in (LENS_LUM_MIN, 0.0):
        cand = front & (Lum >= lum_min)
        comp, k = edge_components(ob, cand)
        best = _lens_seed(C, A, V, cand, comp, k, bvh, xmax)
        if best is not None:
            break
    if best is None:
        rec["warnings"].append(f"{rec_key}: no lens seed found")
        return None
    if lum_min == 0.0:
        rec["warnings"].append("UNCLEAR lens: no bright (texel lum >= 0.15) forward region covers its own centre; the "
                               "lens was picked on geometry alone (luminance filter off) - check the slot map")
    _, i, cyz, R = best
    s = comp == i
    x0, x1 = C[s, 0].min() - 0.05 * L, C[s, 0].max() + 0.05 * L
    rr = np.hypot(C[:, 1] - cyz[0], C[:, 2] - cyz[1])
    lens = (front | s) & (rr < 1.0 * R) & (C[:, 0] >= x0) & (C[:, 0] <= x1)
    # whole-lens radius: from the grown set
    R2 = float(np.percentile(rr[lens], 98))
    return dict(mask=lens, cy=float(cyz[0]), cz=float(cyz[1]), R=R2, seed_faces=int(s.sum()), seed_lum_min=lum_min,
                lens_lum=float((Lum[lens] * A[lens]).sum() / A[lens].sum()),
                rest_front_lum=float((Lum[front & ~lens] * A[front & ~lens]).sum() / max(A[front & ~lens].sum(), 1e-12)),
                faces=int(lens.sum()), x_range=(float(C[lens, 0].min()), float(C[lens, 0].max())), L=float(L))


def _lens_seed(C, A, V, cand, comp, k, bvh, xmax):
    # body centre (y,z): area-weighted centroid of the candidates
    w = A * cand
    if w.sum() <= 0:
        return None
    cy, cz = (C[:, 1] * w).sum() / w.sum(), (C[:, 2] * w).sum() / w.sum()
    best = None
    for i in range(k):
        s = comp == i
        area = A[s].sum()
        cyz = np.array([(C[s, 1] * A[s]).sum() / area, (C[s, 2] * A[s]).sum() / area])
        rr = np.hypot(C[s, 1] - cyz[0], C[s, 2] - cyz[1])
        R = np.percentile(rr, 95) if s.sum() > 3 else 0
        if R <= 0: continue
        hit = bvh.ray_cast(Vector((xmax + 1.0, cyz[0], cyz[1])), Vector((-1, 0, 0)))
        if hit[2] is None or comp[hit[2]] != i: continue   # annulus/rim: a ray down its own centre hits something else
        if np.hypot(cyz[0] - cy, cyz[1] - cz) > 0.35 * (V[:, 1].max() - V[:, 1].min()) / 2: continue
        if best is None or area > best[0]:
            best = (area, i, cyz, R)
    return best


def housing_pivot(ob):
    V = vert_array(ob)
    xmin, xmax = V[:, 0].min(), V[:, 0].max(); L = xmax - xmin
    zmin, zmax = V[:, 2].min(), V[:, 2].max()
    mid = (V[:, 0] > xmin + 0.15 * L) & (V[:, 0] < xmax - 0.15 * L) & (V[:, 2] < zmax - 0.15 * (zmax - zmin))
    res = []
    for sgn in (1, -1):
        sel = mid & (sgn * V[:, 1] > 0)
        ymax = (sgn * V[sel, 1]).max()
        knob = sel & (sgn * V[:, 1] >= 0.93 * ymax)
        res.append((np.median(V[knob, 0]), np.median(V[knob, 2]), int(knob.sum()), float(ymax)))
    px = (res[0][0] + res[1][0]) / 2; pz = (res[0][1] + res[1][1]) / 2
    return px, pz, res


def build_housing(name, cfg, src, rec):
    ob = mc.import_source(src)
    rec["source_tris"] = tris_of(ob)
    ob.rotation_euler = (0, 0, BEAM_ROT[cfg["beam"]])
    apply_all(ob)
    rec["decimate_ratio_lod0"] = decimate_to(ob, LOD0_TRIS - 300)
    triangulate(ob)
    lens = classify_lens(ob, "LOD0", rec, mc.load_img(src["basecolor"]))
    if lens is None:
        raise RuntimeError("lens not found")
    # centre lens axis on y=0 (z handled by the pivot), measure length near the axis
    V = vert_array(ob)
    near = np.hypot(V[:, 1] - lens["cy"], V[:, 2] - lens["cz"]) < 1.35 * lens["R"]
    body_len = V[near, 0].max() - V[near, 0].min()
    s = (cfg["L"] / 100.0) / body_len
    ob.data.transform(Matrix.Translation((0, -lens["cy"], 0)))
    ob.data.transform(Matrix.Scale(s, 4))
    px, pz, knobs = housing_pivot(ob)
    ob.data.transform(Matrix.Translation((-px, 0, -pz)))
    set_slots(ob, [f"M_{name}_Lens", f"M_{name}_Metal"])
    ob.data.polygons.foreach_set("material_index", np.where(lens["mask"], 0, 1).astype(np.int32))
    ob.data.update()
    C, N, A = face_arrays(ob)
    lc = C[lens["mask"]]
    rec["classification"] = {
        "rule": "lens seed = largest edge-connected region of forward-facing (n.x>0.5) faces in the front 45 % whose "
                "base-colour texel luminance >= 0.15 and that covers its own centre (a -X ray through its area centroid first hits it); lens = all forward faces "
                "within the seed's 95th-pct radius and x-range +/-5 % L",
        "seed_lum_filter": lens["seed_lum_min"], "lens_mean_lum": round(lens["lens_lum"], 3), "other_front_faces_mean_lum": round(lens["rest_front_lum"], 3),
        "lens_faces_lod0": lens["faces"], "lens_seed_faces": lens["seed_faces"],
        "lens_diameter_cm": round(2 * lens["R"] * s * 100, 1),
        "lens_centroid_cm": [round(float(x) * 100, 1) for x in (A[lens["mask"]] @ lc / A[lens["mask"]].sum())],
        "lens_area_fraction": round(float(A[lens["mask"]].sum() / A.sum()), 4)}
    rec["scale_rule"] = f"x extent of vertices within 1.35 x lens radius of the beam axis = {body_len * s * 100:.1f} cm (target {cfg['L']})"
    rec["pivot_rule"] = ("tilt axis: median (x,z) of the most lateral 7 % of vertices on each side, middle 70 % of length, "
                         "below top 15 %")
    rec["pivot_evidence"] = [{"side": "+Y" if i == 0 else "-Y", "x_cm": round((k[0] - px) * 100, 2), "z_cm": round((k[1] - pz) * 100, 2),
                              "verts": k[2], "half_width_cm": round(k[3] * 100, 1)} for i, k in enumerate(knobs)]
    ob.name = name + "_LOD0"; ob.data.name = name + "_LOD0"
    # LOD1
    lod1 = ob.copy(); lod1.data = ob.data.copy(); bpy.context.collection.objects.link(lod1)
    lod1.name = name + "_LOD1"; lod1.data.name = name + "_LOD1"
    rec["decimate_ratio_lod1"] = decimate_to(lod1, LOD1_TRIS - 50)
    triangulate(lod1)
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    mi0 = np.zeros(len(ob.data.polygons), np.int32); ob.data.polygons.foreach_get("material_index", mi0)
    C1, _, _ = face_arrays(lod1)
    mi1 = np.array([mi0[bvh.find_nearest(Vector(c))[2]] for c in C1], np.int32)
    lod1.data.polygons.foreach_set("material_index", mi1); lod1.data.update()
    return ob, lod1, s


# ----------------------------------------------------------------------------------------------------------- export
def export_fbx(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # verbatim Flat V3 / Underpass call (build_v3_flat.py:1838-1843) + face smoothing groups, triangles
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
        bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO",
        use_custom_props=True, mesh_smooth_type="FACE", use_triangles=True, embed_textures=False,
    )


def readback(path):
    """Re-import the exported FBX into an empty scene: bounds, tris, slots, UV V-sign, hierarchy."""
    keep = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in keep]
    out = {"objects": []}
    for o in new:
        r = {"name": re.sub(r"\.\d{3}$", "", o.name), "type": o.type, "parent": re.sub(r"\.\d{3}$", "", o.parent.name) if o.parent else None,
             "fbx_type": o.get("fbx_type")}
        if o.type == "MESH":
            V = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
            mi = np.zeros(len(o.data.polygons), np.int32); o.data.polygons.foreach_get("material_index", mi)
            r.update(tris=tris_of(o), bounds_cm=[[round(float(x) * 100, 2) for x in V.min(0)], [round(float(x) * 100, 2) for x in V.max(0)]],
                     size_cm=[round(float(x) * 100, 2) for x in (V.max(0) - V.min(0))],
                     slots=[{"index": i, "name": re.sub(r"\.\d{3}$", "", s.material.name) if s.material else None, "faces": int((mi == i).sum())}
                            for i, s in enumerate(o.material_slots)],
                     uv_layers=[u.name for u in o.data.uv_layers])
        out["objects"].append(r)
    for o in new:
        bpy.data.objects.remove(o)
    return out


def uv_hash(ob):
    a = np.zeros(len(ob.data.loops) * 2); ob.data.uv_layers.active.data.foreach_get("uv", a)
    return a


# ----------------------------------------------------------------------------------------------------------- render
def render_views(name, objs, size_cm, out_tex, out_slot, tex_paths):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.render.resolution_x = sc.render.resolution_y = 512
    sc.render.film_transparent = False
    if not sc.world:
        sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.42, 0.42, 0.42)
    sc.display.shading.background_type = "WORLD" if hasattr(sc.display.shading, "background_type") else None
    V = np.vstack([np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for o in objs])
    c = Vector(((V.min(0) + V.max(0)) / 2).tolist()); ext = float((V.max(0) - V.min(0)).max())
    d = Vector((1.0, -0.9, 0.55)).normalized()            # 3/4 view from front-right (+X beam faces the camera)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"
    span = max(ext * 1.35, 0.14)
    cam.data.ortho_scale = span
    cam.location = c + d * 3; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = 10
    bpy.context.view_layer.update()
    # 10 cm scale bar along the camera's screen-right, below the object
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0)); up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    p0 = c - up * (span * 0.43) - right * (span * 0.42)
    bm = bmesh.new()
    seg = [p0 + right * (0.10 * t / 10) for t in range(11)]
    tube(bm, seg, span * 0.006, 0, sides=4)
    for t in (0, 10):
        q = p0 + right * (0.01 * t)
        tube(bm, [q - up * span * 0.015, q + up * span * 0.015], span * 0.004, 0, sides=4)
    me = bpy.data.meshes.new("bar"); bm.to_mesh(me); bm.free()
    bar = bpy.data.objects.new("ScaleBar10cm", me); sc.collection.objects.link(bar)
    barmat = make_material("bar", (0.95, 0.15, 0.1, 1)); me.materials.append(barmat)
    # textured
    bc = bpy.data.images.load(tex_paths["BaseColor"], check_existing=True)
    saved = {}
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m.name in saved: continue
            saved[m.name] = m
            m.use_nodes = True
            nt = m.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = bc
            nt.links.new(t.outputs[0], bsdf.inputs[0])
    barmat.use_nodes = True
    bnt = barmat.node_tree; next(n for n in bnt.nodes if n.type == "BSDF_PRINCIPLED").inputs[0].default_value = (0.95, 0.15, 0.1, 1)
    sc.display.shading.color_type = "TEXTURE"
    sc.render.filepath = out_tex
    bpy.ops.render.render(write_still=True)
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_xray = True          # see-through, so a filament inside the glass shows in the slot map
    sc.display.shading.xray_alpha = 0.45
    # pivot marker positions (drawn by compose_contact_sheet.py): origin, +X and +Z tips in normalised image coords
    from bpy_extras.object_utils import world_to_camera_view
    mk = {k: list(world_to_camera_view(sc, cam, Vector(v))[:2]) for k, v in
          (("origin", (0, 0, 0)), ("x_tip", (span * 0.15, 0, 0)), ("z_tip", (0, 0, span * 0.1)))}
    sc.render.filepath = out_slot
    bpy.ops.render.render(write_still=True)
    sc.display.shading.show_xray = False
    # strip texture nodes again so the FBX carries no texture references
    for m in saved.values():
        for n in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]:
            m.node_tree.nodes.remove(n)
    bpy.data.objects.remove(bar); bpy.data.objects.remove(cam)
    return {"view_dir": list(d), "ortho_span_m": span, "pivot_marker_uv": mk}


# ------------------------------------------------------------------------------------------------------------- main
def process(name, src):
    rec = {"asset": name, "source_uuid": src["uuid"], "source_dir": src["dir"], "warnings": []}
    out_dir = os.path.join(OUT_ROOT, name); os.makedirs(out_dir, exist_ok=True)
    tex = {}
    for key, s in (("BaseColor", src["basecolor"]), ("Normal", src["normal"]), ("Roughness", src["roughness"]),
                   ("Metallic", src["metallic"])):
        dst = os.path.join(out_dir, f"T_{name}_{key}.png"); shutil.copyfile(s, dst); tex[key] = dst
    rec["textures"] = [os.path.basename(p) for p in tex.values()]
    metal_arr = mc.load_img(src["metallic"])
    if name in BULBS:
        cfg = BULBS[name]
        ob, s = build_bulb(name, cfg, src, rec, metal_arr)
        uv_before = uv_hash(ob)
        objs = [ob]; export_objs = [ob]
        rec["class"] = "bulb"
        rec["pivot"] = "screw-cap tip at origin; cap +Z; glass hangs in -Z"
        rec["orientation_evidence"] = ("source already cap-up: raw 6-view renders show the screw base at +Z; metallic map "
                                       f"mean above z_cut {rec['classification']['metallic_map_mean_above_cut']} vs below "
                                       f"{rec['classification']['metallic_map_mean_below_cut']}")
        rec["target_cm"] = {"height": cfg["h"], "width": cfg["w"]}
    else:
        cfg = HOUSINGS[name]
        ob, lod1, s = build_housing(name, cfg, src, rec)
        uv_before = uv_hash(ob)
        grp = bpy.data.objects.new(name + "_LODGroup", None); bpy.context.collection.objects.link(grp)
        grp["fbx_type"] = "LodGroup"; grp["LODOrder"] = "LOD0,LOD1"
        ob.parent = grp; lod1.parent = grp
        objs = [ob]; export_objs = [grp, ob, lod1]
        rec["class"] = "housing"
        rec["pivot"] = "yoke tilt axis at origin (heuristic, see pivot_evidence); beam +X; yoke/clamp +Z"
        rec["orientation_evidence"] = (f"source beam axis {cfg['beam']} (raw 6-view renders + front-cap luminance score, "
                                       f"diag_axes.py); rotated {math.degrees(BEAM_ROT[cfg['beam']]):.0f} deg about Z")
        rec["target_cm"] = {"length": cfg["L"], **({"lens_d": cfg["lens_d"]} if "lens_d" in cfg else {}),
                            **({"body_d": cfg["body_d"]} if "body_d" in cfg else {})}
        if cfg.get("ambiguous_front"):
            rec["warnings"].append("UNCLEAR front: both ends of this Meshy model carry a lens-like disc; front chosen by "
                                   "the higher front-cap luminance score (diag_axes.py). The rear disc stays in slot 1.")
    rec["uniform_scale_from_source"] = s
    for o in objs:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
        o.select_set(False)
    rec["renders"] = render_views(name, objs, None, os.path.join(RENDER_DIR, f"{name}_tex.png"),
                                  os.path.join(RENDER_DIR, f"{name}_slots.png"), tex)
    fbx = os.path.join(out_dir, name + ".fbx")
    export_fbx(fbx, export_objs)
    rec["fbx"] = fbx
    rec["fbx_sha256"] = hashlib.sha256(open(fbx, "rb").read()).hexdigest()
    rb = readback(fbx)
    rec["readback"] = rb
    meshes = [o for o in rb["objects"] if o["type"] == "MESH"]
    lod0 = next(o for o in meshes if not o["name"].endswith("_LOD1"))
    rec["final_bounds_cm"] = lod0["bounds_cm"]; rec["final_size_cm"] = lod0["size_cm"]
    rec["tris"] = lod0["tris"]
    rec["slots"] = lod0["slots"]
    if rec["class"] == "housing":
        l1 = next(o for o in meshes if o["name"].endswith("_LOD1"))
        rec["lod1_tris"] = l1["tris"]; rec["lod1_slots"] = l1["slots"]
        grp = [o for o in rb["objects"] if o["type"] == "EMPTY"]
        rec["lodgroup_readback"] = [{"name": g["name"], "fbx_type": g["fbx_type"]} for g in grp]
    # checks
    if rec["class"] == "bulb":
        if rec["tris"] > BULB_TRIS: rec["warnings"].append(f"tris {rec['tris']} > {BULB_TRIS}")
        h = rec["final_size_cm"][2]; w = max(rec["final_size_cm"][:2])
        if abs(h - cfg["h"]) > 0.1 * cfg["h"]: rec["warnings"].append(f"height {h} cm outside +-10 % of {cfg['h']}")
        if abs(w - cfg["w"]) > 0.1 * cfg["w"]: rec["warnings"].append(f"width {w:.2f} cm outside +-10 % of {cfg['w']} (Meshy proportions; height was matched)")
        if rec["final_bounds_cm"][1][2] > 0.05: rec["warnings"].append("geometry above the pivot")
    else:
        if rec["tris"] > LOD0_TRIS: rec["warnings"].append(f"LOD0 tris {rec['tris']} > {LOD0_TRIS}")
        if rec["lod1_tris"] > LOD1_TRIS: rec["warnings"].append(f"LOD1 tris {rec['lod1_tris']} > {LOD1_TRIS}")
        if "lens_d" in cfg:
            d = rec["classification"]["lens_diameter_cm"]
            if abs(d - cfg["lens_d"]) > 0.1 * cfg["lens_d"]: rec["warnings"].append(f"lens diameter {d} cm vs prompt {cfg['lens_d']}")
        if "body_d" in cfg:
            d = min(rec["final_size_cm"][1], rec["final_size_cm"][2])
            rec["warnings"].append(f"check: can cross-section min(Y,Z) extent {d} cm incl. yoke vs prompt dia {cfg['body_d']}") if abs(d - cfg["body_d"]) > 0.1 * cfg["body_d"] else None
        if rec["classification"]["lens_centroid_cm"][0] <= 0: rec["warnings"].append("lens centroid not at +X")
    for sl in rec["slots"]:
        if sl["faces"] == 0: rec["warnings"].append(f"slot {sl['index']} empty")
    rec["uv_layers"] = lod0["uv_layers"]
    rec["uv_note"] = ("Meshy UV0 kept as authored (decimation interpolates it); the textures were made for these UVs, so "
                      "no V flip was applied. The wing 'V runs down' rule concerns planar-projected wings, not baked atlases.")
    with open(os.path.join(out_dir, name + "_record.json"), "w") as f:
        json.dump(rec, f, indent=1, default=float)
    print(f"MESHYCLEAN_ASSET_OK|{name}|tris={rec['tris']}|warnings={len(rec['warnings'])}")
    return rec


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    os.makedirs(RENDER_DIR, exist_ok=True)
    srcs = mc.list_sources()
    names = argv or list(srcs)
    for n in names:
        try:
            process(n, srcs[n])
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"MESHYCLEAN_ASSET_FAIL|{n}|{e}")


if __name__ == "__main__":
    main()
