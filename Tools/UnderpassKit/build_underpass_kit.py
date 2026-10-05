"""Underpass rig kit: headless Blender build + offline FBX re-import gate.

Blueprint: Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md section 2/3.

Run (build of record):
    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" --background --factory-startup \
        --python-exit-code 1 --python Tools/UnderpassKit/build_underpass_kit.py
    add `-- --gate-only` to re-run only the re-import gate on existing FBXs.

Conventions (plan section 2):
  * modelled in METRES, exported with the Flat V3 FBX call (FBX_SCALE_UNITS -> cm);
  * length on +X, section in Y (width) and Z (depth); pivot = bounds centre;
  * one mesh object, one material slot, no LODs / LodGroup, transforms applied;
  * triangulated in Blender (concave n-gon caps are not left to the importer);
  * UV0 = trim unwrap: U = 1.0 per 100 cm along X; V = 1.0 per 100 cm, running
    DOWN on vertical faces IN UNREAL (dv/dZ < 0, the UE rule); rivet faces are packed
    into the rivet band V 0.0-0.1 (Unreal V), every other face lives at V >= 0.2.
    Interchange flips V on import (v_ue = 1 - v_blender; Docs/FlatV3Status.md:87,
    "raw dv/dZ > 0 (Interchange flips V)"), so the RAW Blender/FBX V written here is
    1 - v_ue and runs UP; the gate converts back and checks the Unreal-side values;
  * UV1 = the same faces packed 0-1 (lightmap pack), for a later AO bake only.

Deviations from the plan table (each forced by the plan's own bounds):
  * K1 is 120 x 10 x 120: the 10 cm hypotenuse flange the plan asks for makes Y 10, not 2.
  * D1 stringers are 30 wide x 18 deep so that stringer + 12 cm tie = the planned 30 cm Z.
  * C1 channels are 37 deep (Z) so the 1.5 cm lacing on both faces lands on the planned 40 cm;
    the channels span |Y| 16.5-28.5 and the splice plates take |Y| to 30 (= planned 60 cm).
  * Rivets are not geometry anywhere: the material draws them in the V 0-0.1 band.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "DerivedAssets" / "UnderpassKit"
FBX_DIR = OUT_DIR / "FBX"
MANIFEST = OUT_DIR / "kit_manifest.json"
CM = 0.01  # metres per centimetre
RIVET_BAND = (0.0, 0.1)
PLAIN_V0 = 0.2

# name: expected bounds (cm, X Y Z), triangle budget, material slot, optional flag
SPEC = {
    "SM_UP_PlateGirder": {"bounds_cm": [100.0, 40.0, 90.0], "max_tris": 60, "slot": "MAT_Steel", "optional": False,
                          "role": "Phase A gridiron BeamMesh (profile, stretches in X only)"},
    "SM_UP_LacedColumn": {"bounds_cm": [500.0, 60.0, 40.0], "max_tris": 600, "slot": "MAT_Steel", "optional": False,
                          "role": "Phase B column, X = height"},
    "SM_UP_PierBase": {"bounds_cm": [140.0, 140.0, 120.0], "max_tris": 300, "slot": "MAT_Concrete", "optional": False,
                       "role": "Phase B pier, never stretched"},
    "SM_UP_KneeBracket": {"bounds_cm": [120.0, 10.0, 120.0], "max_tris": 60, "slot": "MAT_Steel", "optional": False,
                          "role": "Phase B knee, never stretched"},
    "SM_UP_DeckBay": {"bounds_cm": [500.0, 1000.0, 30.0], "max_tris": 500, "slot": "MAT_Steel", "optional": False,
                      "role": "Phase B open-tie deck bay, X = station gap, Y = span"},
    "SM_UP_Channel": {"bounds_cm": [100.0, 10.0, 30.0], "max_tris": 40, "slot": "MAT_Steel", "optional": True,
                      "role": "spare rail profile"},
    "SM_UP_CatwalkRail": {"bounds_cm": [500.0, 6.0, 110.0], "max_tris": 120, "slot": "MAT_Steel", "optional": True,
                          "role": "catwalk post + cable rail"},
}
DEVIATIONS = {
    "SM_UP_KneeBracket": "Y 10 not 2: the plan's 10 cm hypotenuse flange sets Y",
    "SM_UP_DeckBay": "stringers 30 wide x 18 deep (not 30x30) so stringer + 12 cm tie = planned Z 30",
    "SM_UP_LacedColumn": "channels 37 deep, |Y| 16.5-28.5 (inner gap 33, not 36), plates to |Y| 30, so bounds = 500x60x40",
    "SM_UP_PierBase": "XY rescaled 0.6 % after bevel so the battered/bevelled footprint is exactly 140",
}
DECK_TIES = {"count": 11, "pitch_cm": 45.0, "width_cm": 20.0, "gap_cm": 25.0}


# --------------------------------------------------------------------------- geometry helpers
class Builder:
    """Collects faces into one bmesh; each face carries a 'rivet' int tag."""

    def __init__(self):
        self.bm = bmesh.new()
        self.rivet = self.bm.faces.layers.int.new("rivet")

    def face(self, points_cm, rivet=False):
        verts = [self.bm.verts.new(Vector(p) * CM) for p in points_cm]
        f = self.bm.faces.new(verts)
        f[self.rivet] = 1 if rivet else 0
        return f

    def prism_x(self, outline_yz, x0, x1, rivet_edges=()):
        """Extrude a CCW (Y,Z) outline along X from x0 to x1. rivet_edges = indices i of
        side faces (edge i -> i+1) that belong to the rivet band."""
        n = len(outline_yz)
        a = [(x0, y, z) for y, z in outline_yz]
        b = [(x1, y, z) for y, z in outline_yz]
        self.face(list(reversed(a)))           # -X cap
        self.face(b)                           # +X cap
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], a[j], b[j], b[i]], rivet=i in rivet_edges)

    def prism_y(self, outline_xz, y0, y1, rivet_edges=()):
        """Extrude a CCW (X,Z) outline (seen from -Y) along Y."""
        n = len(outline_xz)
        a = [(x, y0, z) for x, z in outline_xz]
        b = [(x, y1, z) for x, z in outline_xz]
        self.face(a)
        self.face(list(reversed(b)))
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], b[i], b[j], a[j]], rivet=i in rivet_edges)

    def box(self, mn, mx, rivet=False):
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        self.prism_x([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], x0, x1,
                     rivet_edges=(0, 1, 2, 3) if rivet else ())

    def oriented_box(self, centre, axis_x, axis_y, half):
        """Box with local X along axis_x (unit, in the XY plane here), local Y along axis_y."""
        c = Vector(centre)
        ax = Vector(axis_x).normalized()
        ay = Vector(axis_y).normalized()
        az = ax.cross(ay).normalized()
        hx, hy, hz = half
        corners = {}
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    corners[(sx, sy, sz)] = tuple(c + ax * (sx * hx) + ay * (sy * hy) + az * (sz * hz))
        quads = [
            [(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)],
            [(1, -1, -1), (1, -1, 1), (1, 1, 1), (1, 1, -1)],
            [(-1, -1, -1), (-1, -1, 1), (1, -1, 1), (1, -1, -1)],
            [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
            [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)],
            [(-1, -1, 1), (-1, 1, 1), (1, 1, 1), (1, -1, 1)],
        ]
        for q in quads:
            self.face([corners[k] for k in q])


def _normals_outward(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def finish_object(name, builder: Builder, slot_name, *, merge=True):
    bm = builder.bm
    if merge:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    _normals_outward(bm)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    # centre on bounds (pivot = bounds centre)
    lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    centre = (lo + hi) * 0.5
    for v in bm.verts:
        v.co -= centre
    for layer in list(bm.loops.layers.uv.values()):  # e.g. create_cube's 'UVMap'
        bm.loops.layers.uv.remove(layer)
    assign_uv0(bm, builder.rivet)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.get(slot_name) or bpy.data.materials.new(slot_name)
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.set_sharp_from_angle(angle=math.radians(30.0))  # auto-smooth 30 deg, applied as sharp edges
    add_uv1(obj)
    return obj


def assign_uv0(bm, rivet_layer):
    """Trim unwrap, in cm -> UV units of 1 per 100 cm. Vertical faces: V grows DOWNWARD."""
    uv = bm.loops.layers.uv.new("UV0")
    bm.normal_update()
    zmax = max(v.co.z for v in bm.verts)
    ymin = min(v.co.y for v in bm.verts)
    for f in bm.faces:
        n = f.normal
        rivet = f[rivet_layer] == 1
        xs = [l.vert.co.x for l in f.loops]
        ys = [l.vert.co.y for l in f.loops]
        zs = [l.vert.co.z for l in f.loops]
        for l in f.loops:
            x, y, z = (c / CM for c in l.vert.co)
            vertical = abs(n.z) < 0.5
            if abs(n.x) > 0.9:                      # end caps / faces facing along X
                u = 3.0 + (y - ymin / CM) / 100.0
                v = PLAIN_V0 + (zmax / CM - z) / 100.0
            elif vertical:
                u = x / 100.0
                if rivet:
                    top, bot = max(zs) / CM, min(zs) / CM
                    v = RIVET_BAND[0] + (top - z) / max(top - bot, 1e-6) * (RIVET_BAND[1] - RIVET_BAND[0])
                else:
                    v = PLAIN_V0 + (zmax / CM - z) / 100.0
            else:                                   # horizontal faces: V runs across Y
                u = x / 100.0
                if rivet:
                    lo, hi = min(ys) / CM, max(ys) / CM
                    v = RIVET_BAND[0] + (y - lo) / max(hi - lo, 1e-6) * (RIVET_BAND[1] - RIVET_BAND[0])
                else:
                    v = PLAIN_V0 + (y - ymin / CM) / 100.0
            l[uv].uv = (u, 1.0 - v)  # stored raw; Unreal reads v_ue = 1 - raw


def add_uv1(obj):
    mesh = obj.data
    mesh.uv_layers.new(name="UV1")
    mesh.uv_layers.active_index = 1
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.view_layer.objects:
        o.select_set(o is obj)
    method = "lightmap_pack"
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.2)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as exc:  # noqa: BLE001  fall back, recorded in the manifest
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        method = f"bbox_normalised_uv0 ({exc})"
        u0, u1 = mesh.uv_layers[0].data, mesh.uv_layers[1].data
        us = [d.uv.x for d in u0]
        vs = [d.uv.y for d in u0]
        su, sv = max(us) - min(us) or 1.0, max(vs) - min(vs) or 1.0
        for a, b in zip(u0, u1):
            b.uv = ((a.uv.x - min(us)) / su, (a.uv.y - min(vs)) / sv)
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True
    obj["uv1_method"] = method


# --------------------------------------------------------------------------- modules
def build_plate_girder():
    """I-section: depth 90, flanges 40 x 3, web 2; web split 10 cm from each flange so the
    flange-side strips can carry the rivet band (16-point outline -> 60 tris)."""
    b = Builder()
    o = [(-20, -45), (20, -45), (20, -42), (1, -42), (1, -32), (1, 32), (1, 42), (20, 42),
         (20, 45), (-20, 45), (-20, 42), (-1, 42), (-1, 32), (-1, -32), (-1, -42), (-20, -42)]
    # side face i spans o[i] -> o[i+1]; rivet band: both flange outer faces + the 4 web strips
    rivet = {0, 3, 5, 8, 11, 13}
    b.prism_x(o, -50, 50, rivet_edges=rivet)
    return finish_object("SM_UP_PlateGirder", b, "MAT_Steel")


def build_channel():
    """C-section 30 deep (Z) x 10 flange (Y) x 1.5 thick; web on -Y."""
    b = Builder()
    t = 1.5
    o = [(-5, -15), (5, -15), (5, -15 + t), (-5 + t, -15 + t), (-5 + t, 15 - t), (5, 15 - t), (5, 15), (-5, 15)]
    b.prism_x(o, -50, 50, rivet_edges={7})
    return finish_object("SM_UP_Channel", b, "MAT_Steel")


def build_laced_column():
    """Two C-channels (37 deep, 12 flange, back to the outside), X-lacing 6 x 1.5 every 50 cm on
    both Z faces (10 pairs per face), splice plates 40 x 30 x 1.5 at x=0 and x=250 of the run."""
    b = Builder()
    L = 500.0
    x0, x1 = -L / 2, L / 2
    zc, t_web, t_fl = 18.5, 1.2, 1.5
    for side in (-1, 1):
        yo, yi = 28.5 * side, 16.5 * side
        # outline in (Y,Z), CCW seen from +X; build for +Y then mirror
        pts = [(yi, -zc), (yo, -zc), (yo, zc), (yi, zc), (yi, zc - t_fl),
               (yo - t_web * side, zc - t_fl), (yo - t_web * side, -zc + t_fl), (yi, -zc + t_fl)]
        if side < 0:
            pts = [(y, -z) for y, z in pts]  # keeps CCW after the Y mirror
        b.prism_x(pts, x0, x1, rivet_edges={1})
    # lacing bars on the flange faces (z = +-18.5 .. +-20)
    yb = 22.5  # bar ends land on the flange centre line
    for zface in (-1, 1):
        zc_bar = zface * (zc + 0.75)
        for k in range(10):
            xa = x0 + k * 50.0
            xb = xa + 50.0
            for ya, yb_ in ((-yb, yb), (yb, -yb)):
                pa, pb = Vector((xa, ya, zc_bar)), Vector((xb, yb_, zc_bar))
                axis = (pb - pa)
                half_len = axis.length / 2.0
                axis.normalize()
                across = Vector((-axis.y, axis.x, 0.0))
                # trim the bar so its rotated corners stay inside its 50 cm cell (bounds stay 500)
                half = min(half_len, (25.0 - 3.0 * abs(axis.y)) / abs(axis.x) - 0.05)
                b.oriented_box((pa + pb) / 2, axis, across, (half, 3.0, 0.75))
    # splice plates on the channel backs
    for xs in (x0, x0 + 250.0):
        xa = max(xs - 20.0, x0) if xs > x0 else x0
        for side in (-1, 1):
            y_in, y_out = (28.5, 30.0) if side > 0 else (-30.0, -28.5)
            b.box((xa, y_in, -15.0), (xa + 40.0, y_out, 15.0), rivet=True)
    return finish_object("SM_UP_LacedColumn", b, "MAT_Steel", merge=False)


def build_pier_base():
    """140 x 140 x 120 concrete pier: battered top (-8 cm each side), 6 cm one-segment bevel,
    three spall notches (boolean difference, applied)."""
    bm = bmesh.new()
    s, h = 70.0 * CM, 60.0 * CM
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 2 * s
        v.co.y *= 2 * s
        v.co.z *= 2 * h
        if v.co.z > 0:
            v.co.x -= math.copysign(8.0 * CM, v.co.x)
            v.co.y -= math.copysign(8.0 * CM, v.co.y)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=6.0 * CM, segments=1, affect="EDGES",
                    profile=0.5, clamp_overlap=True)
    mesh = bpy.data.meshes.new("SM_UP_PierBase")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("SM_UP_PierBase", mesh)
    bpy.context.scene.collection.objects.link(obj)
    cutters = []
    # centres on edges: a battered vertical edge, a bottom corner edge, a bottom edge
    for i, (loc, rot) in enumerate((((64, 64, 25), (0.3, 0.2, 0.7)),
                                    ((-69, -69, -40), (0.5, 0.1, 0.2)),
                                    ((70, -25, -60), (0.2, 0.6, 0.4)))):
        bpy.ops.mesh.primitive_cube_add(size=0.16, location=Vector(loc) * CM, rotation=rot)
        cutter = bpy.context.active_object
        cutter.name = f"cutter_{i}"
        cutters.append(cutter)
        mod = obj.modifiers.new(f"spall_{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    # back into the common finish path (re-centre, triangulate, UVs)
    b = Builder()
    b.bm.free()
    b.bm = bmesh.new()
    b.bm.from_mesh(obj.data)
    b.rivet = b.bm.faces.layers.int.new("rivet")
    # the batter puts the side faces' lowest bevelled ring at |x| 69.6, not 70: rescale XY so
    # the planned 140 x 140 footprint holds exactly (changes the 6 cm bevel by 0.6 %)
    for axis in (0, 1):
        lo = min(v.co[axis] for v in b.bm.verts)
        hi = max(v.co[axis] for v in b.bm.verts)
        k = (140.0 * CM) / (hi - lo)
        for v in b.bm.verts:
            v.co[axis] = (v.co[axis] - (lo + hi) / 2) * k
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return finish_object("SM_UP_PierBase", b, "MAT_Concrete", merge=False)


def build_knee_bracket():
    """Right-angle gusset in the XZ plane (corner at -X,+Z), plate 2 thick, 10 cm flange
    (1.5 thick) on the hypotenuse, trimmed to the 120 x 120 bounds."""
    b = Builder()
    tri = [(-60, -60), (60, 60), (-60, 60)]  # CCW in (X,Z) seen from -Y
    b.prism_y(tri, -1.0, 1.0)
    t = 1.5 * math.sqrt(2.0)
    flange = [(-60, -60), (-60 + t, -60), (60, 60 - t), (60, 60)]
    b.prism_y(flange, -5.0, 5.0, rivet_edges={1})
    return finish_object("SM_UP_KneeBracket", b, "MAT_Steel", merge=False)


def build_deck_bay():
    """Open-tie deck bay 500 (X) x 1000 (Y) x 30 (Z): two stringers along X at Y +-250
    (30 wide x 18 deep), 11 ties along Y (20 wide x 12 deep) every 45 cm = 25 cm REAL gaps."""
    b = Builder()
    for yc in (-250.0, 250.0):
        b.box((-250.0, yc - 15.0, -15.0), (250.0, yc + 15.0, 3.0), rivet=False)
    n, pitch, w = DECK_TIES["count"], DECK_TIES["pitch_cm"], DECK_TIES["width_cm"]
    first = -pitch * (n - 1) / 2.0
    for i in range(n):
        xc = first + i * pitch
        b.box((xc - w / 2, -500.0, 3.0), (xc + w / 2, 500.0, 15.0))
    return finish_object("SM_UP_DeckBay", b, "MAT_Steel", merge=False)


def build_catwalk_rail():
    """Posts 6 x 6 x 110 every 125 cm (5 posts), two 2 x 2 cable runs."""
    b = Builder()
    for i in range(5):
        xc = -247.0 + i * (494.0 / 4.0)
        b.box((xc - 3.0, -3.0, -55.0), (xc + 3.0, 3.0, 55.0))
    for zc in (50.0, 10.0):
        b.box((-250.0, -1.0, zc - 1.0), (250.0, 1.0, zc + 1.0))
    return finish_object("SM_UP_CatwalkRail", b, "MAT_Steel", merge=False)


BUILDERS = {
    "SM_UP_PlateGirder": build_plate_girder,
    "SM_UP_LacedColumn": build_laced_column,
    "SM_UP_PierBase": build_pier_base,
    "SM_UP_KneeBracket": build_knee_bracket,
    "SM_UP_DeckBay": build_deck_bay,
    "SM_UP_Channel": build_channel,
    "SM_UP_CatwalkRail": build_catwalk_rail,
}


# --------------------------------------------------------------------------- export / gate
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def export_fbx(obj, path: Path):
    """Flat V3's call (Tools/FlatV3/build_v3_flat.py:1838-1843), MESH only per the plan."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
        bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO",
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _vertical_v_signs(obj):
    """Per vertical face (|nz| < 0.1, z-extent > 0.5 cm): least-squares dv/dz in world space."""
    mesh = obj.data
    mw = obj.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    uv = mesh.uv_layers[0].data
    pos, neg, checked = 0, 0, 0
    for poly in mesh.polygons:
        n = (nmat @ poly.normal).normalized()
        if abs(n.z) >= 0.1:
            continue
        zs = [(mw @ mesh.vertices[mesh.loops[li].vertex_index].co).z / CM for li in poly.loop_indices]
        vs = [1.0 - uv[li].uv.y for li in poly.loop_indices]  # Unreal-side V
        if max(zs) - min(zs) < 0.5:
            continue
        mz, mv = sum(zs) / len(zs), sum(vs) / len(vs)
        num = sum((z - mz) * (v - mv) for z, v in zip(zs, vs))
        checked += 1
        if num < 0:
            neg += 1
        else:
            pos += 1
    return checked, neg, pos


def _deck_tie_gaps(obj):
    """Tie tops are the only vertices above Z 3.5 cm: each tie contributes x = xc +- 10."""
    mw = obj.matrix_world
    xs = sorted({round((mw @ v.co).x / CM, 2) for v in obj.data.vertices if (mw @ v.co).z / CM > 3.5})
    if len(xs) % 2:
        return -1, [], []
    spans = [(xs[2 * i], xs[2 * i + 1]) for i in range(len(xs) // 2)]
    gaps = [round(spans[i + 1][0] - spans[i][1], 3) for i in range(len(spans) - 1)]
    widths = [round(b - a, 3) for a, b in spans]
    return len(spans), gaps, widths


def gate_one(name: str, path: Path) -> dict:
    reset_scene()
    bpy.ops.import_scene.fbx(filepath=str(path))
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == "MESH"]
    problems = []
    if len(objs) != 1 or len(meshes) != 1:
        problems.append(f"objects={[(o.name, o.type) for o in objs]}")
    if any("LOD" in o.name.upper() for o in objs) or any(o.get("fbx_type") == "LodGroup" for o in objs):
        problems.append("lod_present")
    row = {"name": name, "fbx": str(path.relative_to(REPO)).replace("\\", "/"), "sha256": sha256(path),
           "bytes": path.stat().st_size}
    if not meshes:
        row.update(status="FAIL", problems=problems + ["no_mesh"])
        return row
    obj = meshes[0]
    spec = SPEC[name]
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(c[i] for c in corners) / CM for i in range(3)]
    hi = [max(c[i] for c in corners) / CM for i in range(3)]
    size = [round(hi[i] - lo[i], 4) for i in range(3)]
    centre = [round((hi[i] + lo[i]) / 2, 4) for i in range(3)]
    if any(abs(size[i] - spec["bounds_cm"][i]) > 0.1 for i in range(3)):
        problems.append(f"bounds {size} != {spec['bounds_cm']}")
    if any(abs(c) > 0.1 for c in centre):
        problems.append(f"bounds_centre {centre} not at pivot")
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    non_tri = sum(1 for p in obj.data.polygons if len(p.vertices) != 3)
    if tris > spec["max_tris"]:
        problems.append(f"tris {tris} > {spec['max_tris']}")
    slots = [s.material.name if s.material else None for s in obj.material_slots]
    if len(slots) != 1 or not slots[0] or not slots[0].startswith(spec["slot"]):
        problems.append(f"slots {slots}")
    uv_names = [u.name for u in obj.data.uv_layers]
    if len(uv_names) != 2:
        problems.append(f"uv_layers {uv_names}")
    else:
        u1 = obj.data.uv_layers[1].data
        if any(not (-1e-4 <= d.uv.x <= 1 + 1e-4 and -1e-4 <= d.uv.y <= 1 + 1e-4) for d in u1):
            problems.append("uv1_outside_0_1")
    checked, neg, pos = _vertical_v_signs(obj)
    if checked == 0 or pos:
        problems.append(f"uv_v_sign vertical_faces={checked} down={neg} up={pos}")
    # U along X at 1 per 100 cm: on the longest +X run, u span == length/100
    uv0 = obj.data.uv_layers[0].data
    along = [li for p in obj.data.polygons if abs(p.normal.x) < 0.1 for li in p.loop_indices]
    u_span = (max(uv0[li].uv.x for li in along) - min(uv0[li].uv.x for li in along)) if along else 0.0
    # the rule itself: on every face not facing X, U == x_cm / 100 (pivot-centred x)
    mesh = obj.data
    u_err = max((abs(uv0[li].uv.x - (obj.matrix_world @ mesh.vertices[mesh.loops[li].vertex_index].co).x / CM / 100.0)
                 for li in along), default=0.0)
    if u_err > 1e-3:
        problems.append(f"uv0 U != x/100 on along-X faces (max err {u_err:.4f})")
    rivet_loops = sum(1 for d in uv0 if RIVET_BAND[0] - 1e-4 <= 1.0 - d.uv.y <= RIVET_BAND[1] + 1e-4)
    plain_min_v = min((1.0 - d.uv.y for d in uv0 if 1.0 - d.uv.y > RIVET_BAND[1] + 1e-4), default=None)
    row.update({
        "role": spec["role"], "optional": spec["optional"],
        "bounds_cm": size, "bounds_centre_cm": centre, "expected_bounds_cm": spec["bounds_cm"],
        "long_axis": "XYZ"[size.index(max(size))],
        "tris": tris, "non_triangle_polys": non_tri, "max_tris": spec["max_tris"],
        "objects": len(objs), "material_slots": slots, "uv_layers": uv_names,
        "uv0_vertical_faces_checked": checked, "uv0_vertical_faces_v_down": neg, "uv0_vertical_faces_v_up": pos,
        "uv0_u_span_along_x_faces": round(u_span, 4), "uv0_u_rule_max_err": round(u_err, 6), "uv0_rivet_band_loops": rivet_loops,
        "uv0_plain_min_v_unreal": None if plain_min_v is None else round(plain_min_v, 4),
        "object_scale_after_reimport": [round(s, 6) for s in obj.matrix_world.to_scale()],
    })
    if name == "SM_UP_DeckBay":
        count, gaps, widths = _deck_tie_gaps(obj)
        row["deck_ties"] = {"count": count, "gaps_cm": gaps, "widths_cm": widths}
        if count != DECK_TIES["count"] or any(abs(g - DECK_TIES["gap_cm"]) > 0.1 for g in gaps):
            problems.append(f"deck_ties count={count} gaps={gaps}")
    row["status"] = "PASS" if not problems else "FAIL"
    row["problems"] = problems
    return row


def negative_control():
    """The gate must FAIL a girder exported 1 % long with a stray second object and V not flipped."""
    reset_scene()
    obj = build_plate_girder()
    obj.scale = (1.01, 1.0, 1.0)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for d in obj.data.uv_layers[0].data:
        d.uv.y = 1.0 - d.uv.y
    stray = bpy.data.objects.new("SM_UP_PlateGirder_LOD1", obj.data.copy())
    bpy.context.scene.collection.objects.link(stray)
    stray.select_set(True)
    path = OUT_DIR / "negative_control_girder.fbx"
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
        bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO",
    )
    row = gate_one("SM_UP_PlateGirder", path)
    path.unlink()
    return row


def main(argv):
    gate_only = "--gate-only" in argv
    FBX_DIR.mkdir(parents=True, exist_ok=True)
    build_log = {}
    if not gate_only:
        for name, fn in BUILDERS.items():
            reset_scene()
            obj = fn()
            for o in list(bpy.context.scene.objects):
                if o is not obj:
                    bpy.data.objects.remove(o, do_unlink=True)
            path = FBX_DIR / f"{name}.fbx"
            export_fbx(obj, path)
            build_log[name] = {"uv1_method": obj.get("uv1_method"), "blender_tris": len(obj.data.polygons)}
            print(f"UNDERPASS_KIT_EXPORTED|{name}|{path}")
    rows = []
    for name in SPEC:
        path = FBX_DIR / f"{name}.fbx"
        if not path.exists():
            rows.append({"name": name, "status": "FAIL", "problems": ["fbx_missing"]})
            continue
        rows.append(gate_one(name, path))
        print(f"UNDERPASS_KIT_GATE|{name}|{rows[-1]['status']}|{rows[-1].get('problems')}")
    neg = negative_control()
    print(f"UNDERPASS_KIT_NEGATIVE_CONTROL|{neg['status']}|{neg.get('problems')}")
    status = "PASS" if all(r["status"] == "PASS" for r in rows) and neg["status"] == "FAIL" else "FAIL"
    manifest = {
        "status": status,
        "blender": bpy.app.version_string,
        "script": "Tools/UnderpassKit/build_underpass_kit.py",
        "script_sha256": sha256(Path(__file__)),
        "plan": "Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md",
        "units": "cm (Blender metres x 100); FBX_SCALE_UNITS, axis_forward=-X, axis_up=Z",
        "uv_convention": {"uv0_u_per_100cm_along_x": 1.0, "rivet_band_v": list(RIVET_BAND), "plain_v_min": PLAIN_V0,
                          "vertical_faces": "dv/dZ < 0"},
        "phase_a_section": {"BeamWidthCm": 40.0, "BeamDepthCm": 90.0, "SectionVariation": 0.0, "TwistDegrees": 0.0},
        "deck_ties": DECK_TIES,
        "deviations_from_plan_table": DEVIATIONS,
        "not_built": ["T_UP_SteelTrim_N/M and T_UP_Graffiti_Atlas bakes (plan section 2 'Bakes'): rivets are "
                      "procedural in M_UP_PaintedSteel instead (rivet band V 0-0.1)"],
        "build": build_log,
        "modules": rows,
        "negative_control": {"expected": "FAIL", "status": neg["status"], "problems": neg.get("problems")},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"UNDERPASS_KIT_GATE_{status}|modules={len(rows)}|manifest={MANIFEST}")
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
