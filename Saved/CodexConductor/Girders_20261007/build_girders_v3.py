"""Underpass rig v3 meshes: heavier, connected girder/lattice members (Gary 5 Oct #7, #25).

Headless only:
    "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python-exit-code 1 \
        --python Saved/CodexConductor/Girders_20261007/build_girders_v3.py

Writes FBX/<name>.fbx and build_manifest.json here. Never touches Tools/UnderpassKit (another stream's file):
the Builder / UV0 / UV1 / export conventions below are COPIED from Tools/UnderpassKit/build_underpass_kit.py
(sha256 b2ffb744..., lines 102-263 and 439-448) so the v3 meshes keep the kit's material/UV contract:
  * metres in Blender, FBX_SCALE_UNITS -> cm, axis_forward=-X, axis_up=Z, MESH only, one object, one slot,
    no LODs/LodGroup, transforms applied, triangulated;
  * length on +X, pivot = bounds centre (C++ FitMeshToTimber fits by bounds, so pivot/size are normalised);
  * UV0: U = x/100 on faces not facing X; V (Unreal side) runs DOWN on vertical faces; rivet band V 0-0.1
    (the M_UP_PaintedSteel procedural rivets) on chord backs / girder flanges; raw V stored as 1 - v_ue;
  * UV1: lightmap pack 0-1.

v3 differences: every member is its own WELDED closed solid (the kit welds nothing in the column: every face is
its own island), and every secondary member is SUNK into what carries it (no coplanar touching contacts), so
the harness can prove the max gap is 0 by mesh intersection.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
FBX_DIR = HERE / "FBX"
CM = 0.01
RIVET_BAND = (0.0, 0.1)
PLAIN_V0 = 0.2

# Column v3: authored at the placed height so the lacing is not stretched 3.76x (C++ ColumnHeightCm =
# DeckHeightCm 2000 - FloorHeightCm 0 - PierHeightCm 120 = 1880 at the header defaults).
COL = {
    "L": 1880.0, "half_y": 30.0, "half_z": 20.0, "end_plate": 4.0,
    "web_out": 28.0, "web_t": 2.4, "flange_in": 14.0, "flange_t": 3.0, "chord_z": 18.0,
    "bar_w": 12.0, "bar_t": 3.0, "bar_sink": 1.0, "bar_y": 21.0, "cell_target": 58.0,
    "batten_len": 50.0, "batten_z": (17.4, 19.0), "node_plate": (22.0, 12.0), "node_z": (17.6, 19.6),
    "rivet_r": 1.3, "rivet_z": (18.7, 20.0),
}


class PartBuilder:
    """One bmesh; each part is a welded closed solid with its own id (face int layer 'part')."""

    def __init__(self):
        self.bm = bmesh.new()
        self.rivet = self.bm.faces.layers.int.new("rivet")
        self.part_layer = self.bm.faces.layers.int.new("part")
        self.parts: list[dict] = []
        self._verts: list = []
        self._faces: list = []

    def begin(self, role):
        self.parts.append({"id": len(self.parts), "role": role})
        self._verts, self._faces = [], []

    def end(self):
        bmesh.ops.remove_doubles(self.bm, verts=self._verts, dist=1e-5)  # 0.001 cm
        live = [f for f in self._faces if f.is_valid]
        bmesh.ops.recalc_face_normals(self.bm, faces=live)
        # belt and braces: outward = positive signed volume (divergence theorem); flip the part if not
        vol = 0.0
        for f in live:
            co = [l.vert.co for l in f.loops]
            for k in range(1, len(co) - 1):
                vol += co[0].dot(co[k].cross(co[k + 1])) / 6.0
        if vol < 0:
            bmesh.ops.reverse_faces(self.bm, faces=live)
        open_edges = sum(1 for f in live for e in f.edges if len(e.link_faces) != 2)
        self.parts[-1]["closed"] = open_edges == 0

    def face(self, pts_cm, rivet=False):
        vs = [self.bm.verts.new(Vector(p) * CM) for p in pts_cm]
        self._verts += vs
        f = self.bm.faces.new(vs)
        f[self.rivet] = 1 if rivet else 0
        f[self.part_layer] = self.parts[-1]["id"]
        self._faces.append(f)
        return f

    def prism_x(self, role, outline_yz, x0, x1, rivet_edges=()):
        self.begin(role)
        n = len(outline_yz)
        a = [(x0, y, z) for y, z in outline_yz]
        b = [(x1, y, z) for y, z in outline_yz]
        self.face(list(reversed(a)))
        self.face(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], a[j], b[j], b[i]], rivet=i in rivet_edges)
        self.end()

    def prism_y(self, role, outline_xz, y0, y1, rivet_edges=()):
        self.begin(role)
        n = len(outline_xz)
        a = [(x, y0, z) for x, z in outline_xz]
        b = [(x, y1, z) for x, z in outline_xz]
        self.face(a)
        self.face(list(reversed(b)))
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], b[i], b[j], a[j]], rivet=i in rivet_edges)
        self.end()

    def box(self, role, mn, mx, rivet=False):
        (x0, y0, z0), (x1, y1, z1) = mn, mx
        self.prism_x(role, [(y0, z0), (y1, z0), (y1, z1), (y0, z1)], x0, x1,
                     rivet_edges=(0, 1, 2, 3) if rivet else ())

    def oriented_box(self, role, centre, axis_x, axis_y, half):
        self.begin(role)
        c, ax, ay = Vector(centre), Vector(axis_x).normalized(), Vector(axis_y).normalized()
        az = ax.cross(ay).normalized()
        hx, hy, hz = half
        k = {(sx, sy, sz): tuple(c + ax * sx * hx + ay * sy * hy + az * sz * hz)
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)}
        for q in ([(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)], [(1, -1, -1), (1, -1, 1), (1, 1, 1), (1, 1, -1)],
                  [(-1, -1, -1), (-1, -1, 1), (1, -1, 1), (1, -1, -1)], [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
                  [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)], [(-1, -1, 1), (-1, 1, 1), (1, 1, 1), (1, -1, 1)]):
            self.face([k[i] for i in q])
        self.end()

    def rivet_head(self, base_cm, axis, r, h0, h1, sides=6):
        """Hex-prism rivet head (closed), axis a unit vector; spans h0..h1 along it from base."""
        self.begin("rivet")
        a = Vector(axis).normalized()
        u = a.orthogonal().normalized()
        w = a.cross(u).normalized()
        base = Vector(base_cm)
        ring = [u * math.cos(2 * math.pi * i / sides) * r + w * math.sin(2 * math.pi * i / sides) * r
                for i in range(sides)]
        lo = [tuple(base + a * h0 + p) for p in ring]
        hi = [tuple(base + a * h1 + p) for p in ring]
        self.face(list(reversed(lo)))
        self.face(hi)
        for i in range(sides):
            j = (i + 1) % sides
            self.face([lo[i], lo[j], hi[j], hi[i]])
        self.end()


def assign_uv0(bm, rivet_layer):
    """COPY of build_underpass_kit.py:202-234 (trim unwrap)."""
    uv = bm.loops.layers.uv.new("UV0")
    bm.normal_update()
    zmax = max(v.co.z for v in bm.verts)
    ymin = min(v.co.y for v in bm.verts)
    for f in bm.faces:
        n = f.normal
        rivet = f[rivet_layer] == 1
        ys = [l.vert.co.y for l in f.loops]
        zs = [l.vert.co.z for l in f.loops]
        for l in f.loops:
            x, y, z = (c / CM for c in l.vert.co)
            vertical = abs(n.z) < 0.5
            if abs(n.x) > 0.9:
                u = 3.0 + (y - ymin / CM) / 100.0
                v = PLAIN_V0 + (zmax / CM - z) / 100.0
            elif vertical:
                u = x / 100.0
                if rivet:
                    top, bot = max(zs) / CM, min(zs) / CM
                    v = RIVET_BAND[0] + (top - z) / max(top - bot, 1e-6) * (RIVET_BAND[1] - RIVET_BAND[0])
                else:
                    v = PLAIN_V0 + (zmax / CM - z) / 100.0
            else:
                u = x / 100.0
                if rivet:
                    lo, hi = min(ys) / CM, max(ys) / CM
                    v = RIVET_BAND[0] + (y - lo) / max(hi - lo, 1e-6) * (RIVET_BAND[1] - RIVET_BAND[0])
                else:
                    v = PLAIN_V0 + (y - ymin / CM) / 100.0
            l[uv].uv = (u, 1.0 - v)


def add_uv1(obj):
    mesh = obj.data
    mesh.uv_layers.new(name="UV1")
    mesh.uv_layers.active_index = 1
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.view_layer.objects:
        o.select_set(o is obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.2)
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True


def finish(name, b: PartBuilder, slot="MAT_Steel"):
    bm = b.bm
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    centre = (lo + hi) * 0.5
    for v in bm.verts:
        v.co -= centre
    assign_uv0(bm, b.rivet)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.get(slot) or bpy.data.materials.new(slot)
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.set_sharp_from_angle(angle=math.radians(30.0))
    add_uv1(obj)
    obj["parts"] = json.dumps([p["role"] for p in b.parts])
    obj["open_parts"] = sum(1 for p in b.parts if not p.get("closed"))
    return obj


# --------------------------------------------------------------------------- modules
def build_laced_column(lift_lacing_cm=0.0):
    """Two heavy channel chords, X (double) lacing 12 x 3 sunk 1 cm into the chord flanges on both depth faces,
    gusset node plates at every lacing node, riveted batten plates at both ends and mid-height, 4 cm base and cap
    plates over the full section. lift_lacing_cm > 0 is the NEGATIVE CONTROL: the whole lacing layer floats."""
    c = COL
    b = PartBuilder()
    L, hy, hz = c["L"], c["half_y"], c["half_z"]
    x0, x1 = -L / 2, L / 2
    ep = c["end_plate"]
    for xa, xb in ((x0, x0 + ep), (x1 - ep, x1)):
        b.box("end_plate", (xa, -hy, -hz), (xb, hy, hz))
    cx0, cx1 = x0 + ep - 0.5, x1 - ep + 0.5            # chords sunk 0.5 into both end plates
    zc, tf, tw = c["chord_z"], c["flange_t"], c["web_t"]
    yo, yi = c["web_out"], c["flange_in"]
    for side in (-1, 1):
        pts = [(yi, -zc), (yo, -zc), (yo, zc), (yi, zc), (yi, zc - tf), (yo - tw, zc - tf), (yo - tw, -zc + tf),
               (yi, -zc + tf)]
        pts = [(y * side, z * side) for y, z in pts]
        b.prism_x("chord", pts, cx0, cx1, rivet_edges={1})
    lift = lift_lacing_cm
    bl = c["batten_len"]
    battens = [(cx0, cx0 + bl), (-bl / 2, bl / 2), (cx1 - bl, cx1)]   # ends sunk 0.5 into the end plates
    runs = [(battens[0][1], battens[1][0]), (battens[1][1], battens[2][0])]
    bz0, bz1 = c["batten_z"]
    rz0, rz1 = c["rivet_z"]
    for zf in (-1, 1):
        for xa, xb in battens:
            lo_z, hi_z = (bz0, bz1) if zf > 0 else (-bz1, -bz0)
            b.box("batten", (xa, -(yo - 0.5), lo_z + lift * zf), (xb, yo - 0.5, hi_z + lift * zf))
            xm = (xa + xb) / 2
            for dx in (-17.0, 0.0, 17.0):
                for yy in (-24.5, -17.5, 17.5, 24.5):
                    b.rivet_head((xm + dx, yy, lift * zf), (0, 0, zf), c["rivet_r"], rz0, rz1)
    bar_hw, bar_ht = c["bar_w"] / 2, c["bar_t"] / 2
    bar_zc = zc - c["bar_sink"] + bar_ht                 # 17 .. 20: 1 cm into the 18 cm flange face
    yb = c["bar_y"]
    npx, npy = c["node_plate"]
    nz0, nz1 = c["node_z"]
    cells = []
    for ra, rb in runs:
        n = max(1, round((rb - ra) / c["cell_target"]))
        pitch = (rb - ra) / n
        cells.append((ra, pitch, n))
        for zf in (-1, 1):
            zcen = zf * (bar_zc + lift)
            for k in range(n):
                xa, xb = ra + k * pitch, ra + (k + 1) * pitch
                for ya, yb_ in ((-yb, yb), (yb, -yb)):
                    pa, pb = Vector((xa, ya, zcen)), Vector((xb, yb_, zcen))
                    axis = pb - pa
                    hl = axis.length / 2
                    axis.normalize()
                    b.oriented_box("lace_bar", (pa + pb) / 2, axis, (-axis.y, axis.x, 0.0), (hl, bar_hw, bar_ht))
            for k in range(1, n):
                xk = ra + k * pitch
                lo_z, hi_z = (nz0, nz1) if zf > 0 else (-nz1, -nz0)
                for s in (-1, 1):
                    b.box("node_plate", (xk - npx / 2, s * yb - npy / 2, lo_z + lift * zf),
                          (xk + npx / 2, s * yb + npy / 2, hi_z + lift * zf))
    obj = finish("SM_UP_LacedColumn_v3", b)
    obj["cells"] = json.dumps([{"start": a, "pitch": round(p, 3), "n": n} for a, p, n in cells])
    return obj


def build_plate_girder():
    """Riveted built-up plate girder, 100 (stretched X) x 40 x 90: web 2.4, flange plates 40 x 6 (v1: 3),
    four 12 x 12 flange angles riveted to web and flange. X-constant section only (the gridiron stretches
    this mesh to every bay length, so any X-periodic detail would smear); rivets stay in the UV rivet band."""
    b = PartBuilder()
    x0, x1 = -50.0, 50.0
    b.box("web", (x0, -1.2, -39.5), (x1, 1.2, 39.5), rivet=False)
    for s in (-1, 1):
        lo, hi = (39.0, 45.0) if s > 0 else (-45.0, -39.0)
        b.prism_x("flange", [(-20, lo), (20, lo), (20, hi), (-20, hi)], x0, x1,
                  rivet_edges={2} if s > 0 else {0})
    for sy in (-1, 1):
        for sz in (-1, 1):
            # L angle (y,z) for +y,+z quadrant: vertical leg on the web (sunk 0.3), horizontal leg under the
            # flange (sunk 0.3)
            pts = [(0.9, 27.0), (4.2, 27.0), (4.2, 36.0), (13.0, 36.0), (13.0, 39.3), (0.9, 39.3)]
            pts = [(y * sy, z * sz) for y, z in pts]
            edges = (1, 2)                               # vertical-leg back, horizontal-leg underside
            if sy * sz < 0:                              # mirrored once: reverse to keep the winding
                pts = list(reversed(pts))
                edges = tuple((len(pts) - 2 - e) % len(pts) for e in edges)
            b.prism_x("flange_angle", pts, x0, x1, rivet_edges=edges)
    return finish("SM_UP_PlateGirder_v3", b)


def build_knee_bracket():
    """Knee 120 x 20 x 120 (v1: 120 x 10 x 120), corner at (-X,+Z) like v1 so bMirrorKnees is unchanged:
    4 cm bearing flange on the column face (-X), 4 cm top flange under the deck (+Z), 4 cm gusset plate and
    20 x 3 hypotenuse flange sunk into both, 16 rivet heads on the flanges' inner faces."""
    b = PartBuilder()
    # bearing flange (on the column face, -X) and top flange (under the deck, +Z) as ONE L solid: two boxes
    # sharing the corner would leave coplanar faces (z-fighting) and a non-manifold shared edge
    b.prism_y("flange_L", [(-60.0, -60.0), (-56.0, -60.0), (-56.0, 56.0), (60.0, 56.0), (60.0, 60.0), (-60.0, 60.0)],
              -10.0, 10.0)
    b.prism_y("gusset", [(-57.0, -59.0), (59.0, 57.0), (-57.0, 57.0)], -2.0, 2.0)
    t = 3.0 * math.sqrt(2.0)
    b.prism_y("hyp_flange", [(-58.0, -59.0), (-58.0 + t, -59.0), (59.0, 58.0 - t), (59.0, 58.0)], -10.0, 10.0,
              rivet_edges={1})
    for y in (-6.0, 6.0):
        for z in (-45.0, -15.0, 15.0, 42.0):
            b.rivet_head((-56.0, y, z), (1, 0, 0), 1.3, -0.3, 1.0)
        for x in (-42.0, -12.0, 18.0, 48.0):
            b.rivet_head((x, y, 56.0), (0, 0, -1), 1.3, -0.3, 1.0)
    return finish("SM_UP_KneeBracket_v3", b)


BUILDERS = {
    "SM_UP_LacedColumn_v3": build_laced_column,
    "SM_UP_PlateGirder_v3": build_plate_girder,
    "SM_UP_KneeBracket_v3": build_knee_bracket,
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def export_fbx(obj, path: Path):
    """COPY of build_underpass_kit.py:439-448 (the Flat V3 call)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
        bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv):
    FBX_DIR.mkdir(parents=True, exist_ok=True)
    log = {}
    targets = dict(BUILDERS)
    if "--negative-lifted" in argv:   # negative control: lacing layer floated 5 cm off the chords
        targets = {"NEG_LacedColumn_lifted": lambda: build_laced_column(lift_lacing_cm=5.0)}
    for name, fn in targets.items():
        reset_scene()
        obj = fn()
        path = FBX_DIR / f"{name}.fbx"
        export_fbx(obj, path)
        roles = json.loads(obj["parts"])
        log[name] = {"fbx": path.name, "sha256": sha256(path), "blender_tris": len(obj.data.polygons),
                     "parts": len(roles), "open_parts": int(obj["open_parts"]), "roles": {r: roles.count(r) for r in sorted(set(roles))},
                     "cells": json.loads(obj["cells"]) if "cells" in obj else None}
        print(f"GIRDERS_V3_EXPORTED|{name}|tris={len(obj.data.polygons)}|parts={len(roles)}|{path}")
    out = HERE / ("build_manifest_negative.json" if "--negative-lifted" in argv else "build_manifest.json")
    out.write_text(json.dumps({"blender": bpy.app.version_string, "script_sha256": sha256(Path(__file__)),
                               "column_spec": COL, "modules": log}, indent=1) + "\n", encoding="utf-8")
    print(f"GIRDERS_V3_BUILD_OK|{out}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
