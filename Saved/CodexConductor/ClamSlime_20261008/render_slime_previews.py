"""PREVIEWS - NOT RUN (Gary 8 Oct: GPU work paused "for GPU's sake").  Run it only when the GPU is free again:

    "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python render_slime_previews.py

Headless Blender, Workbench engine (rasterised on the GPU through Blender's GPU backend even with -b [inf: Workbench
has no CPU path]).  Opens build/slime_build.blend (the rig + the A_PearlClam_SlimeOpen action, written by
build_slime.py), imports the clam Bottom + Lid FBX exactly as hinge_render.py does (lid at its hinge pivot), and for
the opening angles 0 / 10 / 20 / 30 / 55 deg sets the anim frame whose angle matches (the lid gets the same angle)
and renders three cameras: side (+X), front three-quarter, back three-quarter (the hinge).  Writes
previews/slime_<deg>deg_<cam>.png and the contact sheet previews/slime_sheet.png (5 rows x 3 cameras, numpy only).
Nothing is saved back to the .blend.  Marker SLIME_PREVIEWS_OK|<sheet path>.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = "E:/PussStage/Saved/CodexConductor/ClamSlime_20261008/"
sys.path.insert(0, HERE)
import slime_design as d         # noqa: E402

EXPORT = "E:/PussStage/DerivedAssets/PearlClam/Export/"
OUT = HERE + "previews/"
ANGLES = (0, 10, 20, 30, 55)
RES = (900, 700)
CAMS = {   # location (m), look-at target (m)
    "side": ((1.9, -0.05, 0.55), (0.0, -0.05, 0.5)),
    "front34": ((1.25, -1.55, 0.95), (0.0, -0.1, 0.5)),
    "back34": ((0.9, 1.4, 0.75), (0.0, 0.45, 0.32)),
}


def imp(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=EXPORT + name)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]


def frame_for(angles, deg):
    if deg <= 0:
        return 0
    return int(np.nonzero(angles >= deg - 1e-9)[0][0])


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=HERE + "build/slime_build.blend")
    sc = bpy.context.scene
    A = d.load_design()
    angles = A["angles"]
    bot, lid = imp("SM_PearlClam_Bottom.fbx"), imp("SM_PearlClam_Lid.fbx")
    for o in (bot, lid):
        o.rotation_euler, o.scale = (0, 0, 0), (1, 1, 1)
    lid.location = tuple(d.PIVOT * 0.01)
    for o, col in ((bot, (0.75, 0.55, 0.45, 1)), (lid, (0.45, 0.6, 0.8, 1))):
        for s in o.material_slots:
            if s.material:
                s.material.diffuse_color = col
    for m in bpy.data.materials:
        if m.name.startswith(d.SLOT_LIGAMENT):
            m.diffuse_color = (0.12, 0.06, 0.02, 1)
        elif m.name.startswith(d.SLOT_SLIME):
            m.diffuse_color = (0.55, 0.85, 0.55, 1)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.image_settings.file_format = "PNG"
    cam_data = bpy.data.cameras.new("prev_cam")
    cam = bpy.data.objects.new("prev_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.lens = 45
    paths = []
    for deg in ANGLES:
        f = frame_for(angles, deg)
        sc.frame_set(f)
        lid.rotation_euler = (math.radians(-float(angles[f])), 0, 0)
        row = []
        for name, (loc, tgt) in CAMS.items():
            cam.location = loc
            cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
            p = OUT + "slime_%02ddeg_%s.png" % (deg, name)
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            row.append(p)
        paths.append(row)
    # contact sheet: rows = angles, columns = cameras
    W, H = RES
    sheet = np.ones((H * len(paths), W * len(CAMS), 4), np.float32)
    for r, row in enumerate(paths):
        for c, p in enumerate(row):
            img = bpy.data.images.load(p)
            px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
            y0 = (len(paths) - 1 - r) * H                      # Blender image rows run bottom-up
            sheet[y0:y0 + H, c * W:(c + 1) * W] = px
            bpy.data.images.remove(img)
    out = bpy.data.images.new("slime_sheet", W * len(CAMS), H * len(paths), alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = OUT + "slime_sheet.png"
    out.file_format = "PNG"
    out.save()
    print("SLIME_PREVIEWS_OK|%s|rows=%s deg|cols=%s" % (OUT + "slime_sheet.png", list(ANGLES), list(CAMS)))


main()
