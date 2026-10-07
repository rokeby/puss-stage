"""Close renders of the two candidate front ends of ambiguous housings (3/4 perspective)."""
import bpy, sys, os, math
sys.path.insert(0, r"E:\PussStage\Tools\MeshyFixtures")
import meshy_common as mc
from mathutils import Vector
OUT = sys.argv[sys.argv.index("--")+1]
JOBS = {"SM_Lantern_Birdie": "Y", "SM_Lantern_1950s": "Y", "SM_Lantern_Profile": "X", "SM_Lantern_ParCan": "Y", "SM_Lantern_Fresnel": "Y"}
srcs = mc.list_sources()
for name, ax in JOBS.items():
    ob = mc.import_source(srcs[name])
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x = sc.render.resolution_y = 400
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    for s in (1, -1):
        d = Vector((s, 0, 0)) if ax == "X" else Vector((0, s, 0))
        side = Vector((0, 1, 0)) if ax == "X" else Vector((1, 0, 0))
        p = d * 4 + side * 2 + Vector((0, 0, 1.5))
        cam.location = p; cam.rotation_euler = (-p).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, f"end_{name}_{'p' if s>0 else 'n'}{ax}.png")
        bpy.ops.render.render(write_still=True)
