"""Headless close-up of one S3 wave piece edge: LIVE (1.8 cm, v1 wood edge, one-sided -> culled inward walls) vs
T5O (5 cm, outward walls, MI_WaveEdge_SeaPaint stand-in).  Read-only on the FBXs; writes one PNG.
Usage: blender -b --factory-startup --python render_t5o_closeup_blender.py -- <fbx> <skincolor.png> <out.png> <mode live|t5o> <frame_from_fbx>
Stand-in materials (NOT the UE graph): Front/Flap = SkinColor on UV0; Timber = v3 dark wood; Edge (live) = v1-ish wood
(0.16, 0.10, 0.055), backface-culled like the one-sided v1 master; Edge (t5o) = the master's formula approximated:
lerp(TimberDark, TimberLight, noise grain) with a CanvasColor lip within 0.25 cm of the front/back planes
(x = -15 / -10 cm), values = s3waves_t5o_core.MI_VECTORS (linear).  Framing from <frame_from_fbx> so both match."""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
fbx, skin, out, mode, frame_fbx = argv[0], argv[1], argv[2], argv[3], argv[4]
SEA = {"TimberLight": (0.0908, 0.117, 0.1144), "TimberDark": (0.0726, 0.0936, 0.0915),
       "CanvasColor": (0.1845, 0.2122, 0.1946)}


def import_lod0(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    lod0 = [o for o in new if o.name.endswith("LOD0")] or new
    for o in new:
        if o not in lod0:
            o.hide_render = True
    return lod0, [o for o in bpy.data.objects if o not in before]


bpy.ops.wm.read_factory_settings(use_empty=True)
# framing source: the LIVE mesh, imported then removed, so both renders share a camera
ref, ref_all = import_lod0(frame_fbx)
pts = [ref[0].matrix_world @ v.co for v in ref[0].data.vertices]
ymin, ymax = min(p.y for p in pts), max(p.y for p in pts)
mid = 0.5 * (ymin + ymax)
band = [p for p in pts if abs(p.y - mid) <= 0.25 * (ymax - ymin)] or pts
top = max(band, key=lambda p: p.z)
target = Vector((-0.13, top.y, top.z - 0.08))
for o in ref_all:
    bpy.data.objects.remove(o, do_unlink=True)
lod0, _ = import_lod0(fbx)
img = bpy.data.images.load(skin)


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def mat_color(name, color, cull=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    principled(m).inputs["Base Color"].default_value = (*color, 1.0)
    principled(m).inputs["Roughness"].default_value = 0.75
    m.use_backface_culling = cull
    return m


def mat_image(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = img
    m.node_tree.links.new(t.outputs[0], principled(m).inputs["Base Color"])
    principled(m).inputs["Roughness"].default_value = 0.8
    return m


def mat_sea():
    m = bpy.data.materials.new("Edge_sea")
    m.use_nodes = True
    nt, b = m.node_tree, principled(m)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    grain = nt.nodes.new("ShaderNodeMix")
    grain.data_type = "RGBA"
    grain.inputs["A"].default_value = (*SEA["TimberDark"], 1.0)
    grain.inputs["B"].default_value = (*SEA["TimberLight"], 1.0)
    nt.links.new(noise.outputs["Fac"], grain.inputs["Factor"])
    lo = nt.nodes.new("ShaderNodeMath")
    lo.operation = "LESS_THAN"
    lo.inputs[1].default_value = -0.1475
    hi = nt.nodes.new("ShaderNodeMath")
    hi.operation = "GREATER_THAN"
    hi.inputs[1].default_value = -0.1025
    nt.links.new(sep.outputs["X"], lo.inputs[0])
    nt.links.new(sep.outputs["X"], hi.inputs[0])
    lip = nt.nodes.new("ShaderNodeMath")
    lip.operation = "MAXIMUM"
    nt.links.new(lo.outputs[0], lip.inputs[0])
    nt.links.new(hi.outputs[0], lip.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(grain.outputs["Result"], mix.inputs["A"])
    mix.inputs["B"].default_value = (*SEA["CanvasColor"], 1.0)
    nt.links.new(lip.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.72
    return m


mats = {"Front": mat_image("Front_s"), "Flap": mat_image("Flap_s"),
        "Timber": mat_color("Timber_s", (0.10, 0.06, 0.03)),
        "Edge": mat_sea() if mode == "t5o" else mat_color("Edge_live", (0.16, 0.10, 0.055), cull=True)}
for o in lod0:
    for s in o.material_slots:
        key = s.material.name.split(".")[0] if s.material else s.name
        for k in mats:
            if key.startswith(k):
                s.material = mats[k]

scene = bpy.context.scene
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 45.0
scene.collection.objects.link(cam)
cam.location = target + Vector((-0.42, -0.95, 0.22))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
for nm, e, rot in (("key", 3.0, (50, 0, -120)), ("fill", 0.8, (70, 0, 60))):
    L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, "SUN"))
    L.data.energy = e
    L.rotation_euler = tuple(math.radians(a) for a in rot)
    scene.collection.objects.link(L)
w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.025, 0.03, 1.0)
scene.world = w
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    if eng in engines:
        scene.render.engine = eng
        break
scene.render.resolution_x, scene.render.resolution_y = 900, 640
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("S3T5O_CLOSEUP_DONE|%s|mode=%s|engine=%s" % (out, mode, scene.render.engine))
