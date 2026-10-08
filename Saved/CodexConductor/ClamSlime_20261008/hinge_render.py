"""Headless Blender: import the clam Bottom + Lid FBX, place the lid at its hinge pivot (Blender (0, 47.86, 30.02) cm),
render side + back views of the hinge at several opening angles (workbench, no scene saved)."""
import bpy, math, os, sys
E = "E:/PussStage/DerivedAssets/PearlClam/Export/"
OUT = "E:/PussStage/Saved/CodexConductor/ClamSlime_20261008/hinge/"
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def imp(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=E + name)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]
bot, lid = imp("SM_PearlClam_Bottom.fbx"), imp("SM_PearlClam_Lid.fbx")
for o in (bot, lid):
    o.rotation_euler = (0, 0, 0); o.scale = (1, 1, 1)
bpy.context.view_layer.update()
# measure the imported scale: bottom height should be ~0.443 m
h = (max((bot.matrix_world @ v.co).z for v in bot.data.vertices) - min((bot.matrix_world @ v.co).z for v in bot.data.vertices))
print("HINGE_RENDER|bottom height m", round(h, 4))
lid.location = (0.0, 0.4786, 0.3002)
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "OBJECT"
bot.color = (0.75, 0.55, 0.45, 1); lid.color = (0.45, 0.6, 0.8, 1)
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
cam_data = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cam_data); sc.collection.objects.link(cam); sc.camera = cam
cam_data.lens = 50
views = {"side": ((1.6, 0.47, 0.35), (math.radians(90), 0, math.radians(90))),
         "back34": ((0.9, 1.4, 0.75), None)}
from mathutils import Vector
for deg in (0, 30, 55):
    lid.rotation_euler = (math.radians(-deg), 0, 0)
    for vname, (loc, rot) in views.items():
        cam.location = loc
        if rot is None:
            d = Vector((0, 0.45, 0.32)) - Vector(loc); cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        else:
            cam.rotation_euler = rot
        sc.render.filepath = OUT + "hinge_%02ddeg_%s.png" % (deg, vname)
        bpy.ops.render.render(write_still=True)
print("HINGE_RENDER_OK|", OUT)
