"""Render a baked curtain cache from the Opening's STALLS camera framing (headless Blender 4.4). Offline and read-only.

    set ABC=...\\final3_settled.abc & set RENDER_FRAMES=541,870 & set OUT_ID=stalls_final3 & blender -b --factory-startup --python Scripts/render_stalls_view.py

30 Sep, for Gary's look decision: is a coarser crumple in the pile still the fall he approved? He approved an image, so
the comparison is an image, at the audience's framing and pixel scale:
  - the camera sits 14 m downstage, 1.5 m up, pitched +14 deg;
  - the lens is 15 mm on the 23.76 mm-wide filmback (79 deg across), at 1920 x 1080.
The stage colliders are drawn for context (COLLIDERS; COLLIDER_ORIGIN_CM for a passage site, where the wing cards are
hidden).

THIS IS NOT A SHOW FRAME. It is Blender Workbench, a flat matte velvet-red, with no Unreal lighting, material,
exposure or post. Every PNG it writes is named `<OUT_ID>_f<frame>_NOT_SHOW_FRAME.png`, so the file cannot be
mistaken for a capture.
"""
import importlib.util
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
os.environ.setdefault("CURTAIN_QUADS_PER_BOLT", "15")
os.environ.setdefault("RENDER_STYLE", "matte")
_spec = importlib.util.spec_from_file_location("curtain_drop", ROOT / "Scripts" / "bake_curtain_drop.py")
drop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drop)

ABC = os.environ["ABC"]
# "541,870" renders those frames; "450-780" renders every frame in the range, into <OUT_ID>_clip/ for a video.
_rf = os.environ["RENDER_FRAMES"]
CLIP = "-" in _rf
RENDER_FRAMES = list(range(int(_rf.split("-")[0]), int(_rf.split("-")[1]) + 1)) if CLIP else [int(f) for f in _rf.split(",")]
OUT_ID = os.environ.get("OUT_ID", Path(ABC).stem + "_stalls")
OUT = Path(os.environ.get("OUT_DIR", str(ROOT / "Saved" / "CodexSoftGoods" / "DropBake")))
FILMBACK_W_MM, LENS_MM = 23.76, 15.0


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    bpy.ops.wm.alembic_import(filepath=ABC)
    obj = next(o for o in scene.objects if o.type == "MESH")
    drop.add_render_modifiers(obj)                       # the bake's own render-only subdivision and 6 mm thickness
    mat = bpy.data.materials.new("M_curtain")
    mat.diffuse_color = (0.45, 0.02, 0.04, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    if drop.COLLIDERS:
        drop.add_stage_colliders()
        drop.set_side_hide(False)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_specular_highlight, sh.show_cavity, sh.cavity_type = False, True, "BOTH"
    sh.cavity_ridge_factor = sh.cavity_valley_factor = 1.0
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    cam_data = bpy.data.cameras.new("stalls")
    cam_data.sensor_fit, cam_data.sensor_width, cam_data.lens = "HORIZONTAL", FILMBACK_W_MM, LENS_MM
    cam = bpy.data.objects.new("stalls", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -14.0, 1.5))
    cam.rotation_euler = (math.radians(90 + 14), 0.0, 0.0)
    scene.camera = cam
    if CLIP:
        (OUT / f"{OUT_ID}_clip").mkdir(parents=True, exist_ok=True)
    for n, f in enumerate(RENDER_FRAMES):
        scene.frame_set(f)
        scene.render.filepath = str(OUT / f"{OUT_ID}_clip" / f"f{n:04d}.png") if CLIP else             str(OUT / f"{OUT_ID}_f{f}_NOT_SHOW_FRAME.png")
        bpy.ops.render.render(write_still=True)
        print(f"STALLS_RENDER|{scene.render.filepath}", flush=True)


main()
