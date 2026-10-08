"""Headless close-up of one S3 wave FBX edge, CURRENT vs FIXED (read-only on the FBXs; writes PNGs here only).
Usage: blender -b --factory-startup --python render_edge_closeup_blender.py -- <fbx> <skincolor.png> <out.png> <edge_one_sided 0|1>
Materials are stand-ins (NOT the UE materials): Front/Flap = SkinColor on UV0, Timber = dark wood, Edge = flat
wood colour (v3 TimberLight 0.16/0.10/0.055). edge_one_sided=1 turns on backface culling for the Edge material,
which models a one-sided UE material (M_Wing_CanvasEdge_Master v1). Camera framing is identical for both inputs
(chosen from the CURRENT mesh's crest so both renders look at the same spot)."""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
fbx, skin, out, one_sided = argv[0], argv[1], argv[2], argv[3] == "1"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == "MESH"]
lod0 = [o for o in meshes if o.name.endswith("LOD0")] or meshes
for o in meshes:
    if o not in lod0:
        o.hide_render = True

img = bpy.data.images.load(skin)


def mat(name, color=None, image=None, cull=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if image is not None:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = image
        m.node_tree.links.new(t.outputs[0], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    m.use_backface_culling = cull
    return m


mats = {"Front": mat("Front_s", image=img), "Flap": mat("Flap_s", image=img),
        "Timber": mat("Timber_s", color=(0.045, 0.028, 0.016)),
        "Edge": mat("Edge_s", color=(0.16, 0.10, 0.055), cull=one_sided)}
for o in lod0:
    for s in o.material_slots:
        key = s.material.name.split(".")[0] if s.material else s.name
        for k in mats:
            if key.startswith(k):
                s.material = mats[k]

# Fixed framing (metres, Blender = UE local / 100): a crest near y=+2.6 m on L1 P1, seen from front-left-above.
o0 = lod0[0]
pts = [o0.matrix_world @ v.co for v in o0.data.vertices]
band = [p for p in pts if 2.0 <= p.y <= 3.0] or pts
top = max(band, key=lambda p: p.z)
target = Vector((-0.14, top.y, top.z - 0.10))
print("S3WAVES_TARGET", tuple(round(c, 3) for c in target))
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50.0
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = target + Vector((-0.35, -1.00, 0.25))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0.0, math.radians(-120))
scene.collection.objects.link(sun)
fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))
fill.data.energy = 0.8
fill.rotation_euler = (math.radians(70), 0.0, math.radians(60))
scene.collection.objects.link(fill)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.025, 0.03, 1.0)
scene.world = world

for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        continue
scene.render.resolution_x, scene.render.resolution_y = 960, 720
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("S3WAVES_EDGE_CLOSEUP_DONE|%s|engine=%s|one_sided=%s" % (out, scene.render.engine, one_sided))
