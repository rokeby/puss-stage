"""Before/after renders of one underpass bay, assembled the way C++ places it (headless Blender, Cycles).

    blender -b --factory-startup --python render_compare.py -- <variant>
variant: v1 (current kit meshes, current settings), v3 (v3 meshes, current settings),
         v3x2 (v3 meshes + a SETTINGS PROPOSAL: ColumnWidthCm 120, ColumnDepthCm 80, BeamWidthCm 80, BeamDepthCm 180).

Placement mirrors InfinityStageStructureActor.cpp FitMeshToTimber (:183-196), BuildUnderpass (:1874-2045) and
BuildGridiron (:1093-1170) with header defaults (DeckHeightCm 2000, PierHeightCm 120, ColumnOutsetCm 60,
KneeSizeCm 120, DeckDepthCm 30, Gridiron HeightCm 1150) and GridHalfWidthCm 745 (P05, rig plan :188).
It is an illustration of the formulas, not a read of the level.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V1 = REPO / "DerivedAssets" / "UnderpassKit" / "FBX"
V3 = HERE / "FBX"
OUT = HERE / "renders"
CM = 0.01

variant = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "v1"
S = {"col_w": 60.0, "col_d": 40.0, "beam_w": 40.0, "beam_d": 90.0}
if variant == "v3x2":
    S = {"col_w": 120.0, "col_d": 80.0, "beam_w": 80.0, "beam_d": 180.0}
H = 745.0
OUTSET = 60.0
LINE = H + OUTSET
DECK = 2000.0
PIER_H = 120.0
GRID_Z = 1150.0
KNEE = 120.0


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load(path):
    """Import an FBX, bake its transform into the mesh, return (mesh datablock, bounds lo/hi in cm)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    obj = [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]
    me = obj.data.copy()
    me.transform(obj.matrix_world)
    me.transform(Matrix.Scale(1.0 / CM, 4))  # mesh in cm
    for o in [o for o in bpy.data.objects if o not in before]:
        bpy.data.objects.remove(o, do_unlink=True)
    xs = [v.co for v in me.vertices]
    lo = Vector([min(c[i] for c in xs) for i in range(3)])
    hi = Vector([max(c[i] for c in xs) for i in range(3)])
    return me, lo, hi


def make_from(x_axis, second, second_is_z):
    x = Vector(x_axis).normalized()
    if second_is_z:
        y = Vector(second).cross(x).normalized()
        z = x.cross(y)
    else:
        y = (Vector(second) - x * x.dot(Vector(second))).normalized()
        z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def place(part, centre, rot3, size, mat):
    me, lo, hi = part
    ms = hi - lo
    scale = Vector([size[i] / ms[i] if ms[i] > 1e-6 else 1.0 for i in range(3)])
    pivot = rot3 @ Vector([(lo[i] + hi[i]) * 0.5 * scale[i] for i in range(3)])
    loc = Vector(centre) - pivot
    m = Matrix.Translation(loc * CM) @ rot3.to_4x4() @ Matrix.Diagonal((scale.x * CM, scale.y * CM, scale.z * CM, 1))
    o = bpy.data.objects.new(me.name, me)
    o.matrix_world = m
    if not me.materials:
        me.materials.append(mat)
    else:
        me.materials[0] = mat
    bpy.context.scene.collection.objects.link(o)
    return o


def steel(name, paint, rust_amt):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UV0"
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.62 - rust_amt
    ramp.color_ramp.elements[1].position = 0.70 - rust_amt
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*paint, 1.0)
    mix.inputs[7].default_value = (0.22, 0.08, 0.03, 1.0)
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs[3].default_value = 0.5
    rough.inputs[4].default_value = 0.9
    met = nt.nodes.new("ShaderNodeMapRange")
    met.inputs[3].default_value = 0.35
    met.inputs[4].default_value = 0.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(uv.outputs[0], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[0])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], rough.inputs[0])
    nt.links.new(ramp.outputs["Color"], met.inputs[0])
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    nt.links.new(met.outputs[0], bsdf.inputs["Metallic"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return m


def plain(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def build():
    reset()
    sc = bpy.context.scene
    green = steel("Steel_Green", (0.05, 0.11, 0.07), 0.0)
    black = steel("Steel_Black", (0.02, 0.022, 0.02), 0.05)
    conc = plain("Concrete", (0.32, 0.31, 0.29), 0.9)
    floor = plain("Floor", (0.08, 0.07, 0.06), 0.8)
    src = V1 if variant == "v1" else V3
    sfx = "" if variant == "v1" else "_v3"
    col = load(src / f"SM_UP_LacedColumn{sfx}.fbx")
    knee = load(src / f"SM_UP_KneeBracket{sfx}.fbx")
    gird = load(src / f"SM_UP_PlateGirder{sfx}.fbx")
    pier = load(V1 / "SM_UP_PierBase.fbx")
    deck = load(V1 / "SM_UP_DeckBay.fbx")
    up, fwd, across = Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))
    col_h = DECK - PIER_H
    knee_y = knee[2].y - knee[1].y
    for xs in (0.0, 1000.0):
        for side in (-1, 1):
            line = Vector((xs, side * LINE, 0))
            place(pier, line + up * (PIER_H / 2), Matrix.Identity(3), (140, 140, PIER_H), conc)
            place(col, line + up * (PIER_H + col_h / 2), make_from(up, across, False), (col_h, S["col_w"], S["col_d"]), green)
            for d in (-1, 1):
                kx = fwd * d
                c = line + fwd * (d * (S["col_d"] + KNEE) / 2) + up * (DECK - KNEE / 2)
                place(knee, c, make_from(kx, up, True), (KNEE, knee_y, KNEE), green)
    half_deck = LINE + S["col_w"] / 2
    for xs in (250.0, 750.0):
        place(deck, (xs, 0, DECK + 15), Matrix.Identity(3), (500, half_deck * 2, 30), black)
    for xs in (0.0, 500.0, 1000.0):
        place(gird, (xs, 0, GRID_Z), make_from(across, up, True), (2 * H, S["beam_w"], S["beam_d"]), green)
    for xs in (250.0, 750.0):
        for side in (-1, 1):
            place(gird, (xs, side * H, GRID_Z + S["beam_d"]), make_from(fwd, up, True), (500, S["beam_w"], S["beam_d"]), green)
    bpy.ops.mesh.primitive_plane_add(size=80, location=(5, 0, 0))
    bpy.context.active_object.data.materials.append(floor)
    # light: a warm key sun, a cool fill, dim world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.color = (1.0, 0.86, 0.7)
    sun.rotation_euler = (math.radians(55), 0, math.radians(-35))
    sc.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA"))
    fill.data.energy = 40000
    fill.data.size = 6
    fill.data.color = (0.7, 0.8, 1.0)
    fill.location = (-6, -4, 6)
    fill.rotation_euler = (math.radians(60), 0, math.radians(-60))
    sc.collection.objects.link(fill)
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.03, 0.035, 0.045, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = world
    r = sc.render
    try:
        r.engine = "CYCLES"
    except TypeError:
        pass
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            sc.cycles.device = "GPU"
            break
        except Exception:  # noqa: BLE001
            continue
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    r.resolution_x, r.resolution_y = 760, 900
    r.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"


CAMS = {  # name: (location cm, target cm, lens mm)
    "A_route_low": ((-650, 250, 60), (500, 805, 1000), 20),
    "B_elevation": ((500, -2600, 900), (500, 0, 1050), 24),
    "C_knee_up": ((330, 420, 1500), (0, 805, 1930), 24),
    "D_lacing_close": ((-150, 690, 1000), (-20, 805, 1060), 35),
}


def shoot():
    sc = bpy.context.scene
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    OUT.mkdir(exist_ok=True)
    for name, (loc, tgt, lens) in CAMS.items():
        cam.location = Vector(loc) * CM
        d = (Vector(tgt) - Vector(loc)) * CM
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.05
        sc.render.filepath = str(OUT / f"{variant}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"GIRDERS_RENDER|{variant}|{name}|{sc.render.filepath}")


build()
shoot()
