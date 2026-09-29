"""Lip close-ups and buried-lamp list from a baked curtain Alembic (headless Blender 4.4). Reads, never simulates.

    set ABC=Saved\\CodexSoftGoods\\DropBake\\final2_stage_v2.abc & set COLLIDERS=Docs/StageFrontColliders_2026-09-28.json|v2 &
    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup --python Scripts/render_drop_closeups.py

Imports the bake's Alembic into a scene with the SAME stage colliders (built by Scripts/bake_curtain_drop.py's own
code, from Rig's file), then renders, per frame in SHOT_FRAMES:
  lip34   a low three-quarter along the fascia, from downstage-left
  lipcut  an orthographic section at the lip, looking along the track (the drape profile over the nosing)
and writes <OUT>_buried.json: for each LIP housing, the cloth above its footprint at the last frame (vertices, the
top of the cloth over it, the depth of cloth above the housing). Glow-through is NOT judged here (Workbench has no
scene lights); this says WHERE the Unreal capture should look.
"""
import importlib.util
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
ABC = ROOT / os.environ["ABC"]
OUT = ROOT / "Saved" / "CodexSoftGoods" / "DropBake" / os.environ.get("OUT", ABC.stem + "_closeup")
SHOT_FRAMES = [int(f) for f in os.environ.get("SHOT_FRAMES", "150,180,195,210,240,300,450").split(",")]
os.environ.setdefault("CURTAIN_RAGGED", "0")

spec = importlib.util.spec_from_file_location("bake", ROOT / "Scripts" / "bake_curtain_drop.py")
bake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bake)                      # the __main__ guard stops it baking; we reuse its collider code


def camera(name, loc, target, lens=35.0, ortho=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    if ortho:
        cam.data.type, cam.data.ortho_scale = "ORTHO", ortho
    else:
        cam.data.lens = lens
    tgt = bpy.data.objects.new(f"{name}_target", None)
    bpy.context.scene.collection.objects.link(tgt)
    tgt.location = target
    con = cam.constraints.new("TRACK_TO")
    con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    return cam


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    bake.add_stage_colliders()                     # posts in place: POSTS_FROM is 0 here, the show window only
    bpy.ops.wm.alembic_import(filepath=str(ABC))
    cloth = next(o for o in scene.objects if o.type == "MESH" and not o.name.startswith("Collider_"))
    m = bpy.data.materials.new("M_cloth")
    m.diffuse_color = (0.45, 0.02, 0.04, 1.0)
    cloth.data.materials.clear()
    cloth.data.materials.append(m)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type, sh.show_specular_highlight, sh.show_cavity, sh.cavity_type = "STUDIO", "MATERIAL", False, True, "BOTH"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    shots = {
        "lip34": camera("lip34", (-7.0, -6.5, 0.9), (-1.0, -1.5, -0.35), lens=30.0),
        "lipcut": camera("lipcut", (-30.0, -1.5, -0.2), (0.0, -1.5, -0.2), ortho=4.5),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for f in SHOT_FRAMES:
        scene.frame_set(f)
        for name, cam in shots.items():
            bake.set_side_hide(name == "lipcut")    # the near post would stand in the section view
            scene.camera = cam
            scene.render.filepath = str(OUT.parent / f"{OUT.name}_{name}_f{f:04d}.png")
            bpy.ops.render.render(write_still=True)
    # Buried lip lamps at the last shot frame: cloth over each LIP housing's footprint (Blender metres).
    scene.frame_set(SHOT_FRAMES[-1])
    ev = cloth.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = [ev.matrix_world @ v.co for v in ev.data.vertices]
    data = json.loads((ROOT / bake.COLLIDERS.split("|")[0]).read_text(encoding="utf-8"))
    buried = []
    for h in data.get("lamp_housings", []):
        lo = (h["min_cm"][1] / 100, h["min_cm"][0] / 100, h["min_cm"][2] / 100)
        hi = (h["max_cm"][1] / 100, h["max_cm"][0] / 100, h["max_cm"][2] / 100)
        over = [p for p in co if lo[0] <= p.x <= hi[0] and lo[1] <= p.y <= hi[1] and p.z >= hi[2] - 0.02]
        buried.append({"name": h["name"], "cloth_vertices_over": len(over),
                       "cloth_top_over_m": round(max((p.z for p in over), default=0.0), 3),
                       "cloth_above_housing_m": round(max((p.z for p in over), default=hi[2]) - hi[2], 3),
                       "ue_x_cm": [h["min_cm"][0], h["max_cm"][0]], "ue_y_cm": [h["min_cm"][1], h["max_cm"][1]]})
    (OUT.parent / f"{OUT.name}_buried.json").write_text(json.dumps({"frame": SHOT_FRAMES[-1], "housings": buried}, indent=1),
                                                         encoding="utf-8")
    print(f"CURTAIN_CLOSEUPS_DONE|shots={len(SHOT_FRAMES) * len(shots)}|buried={sum(1 for b in buried if b['cloth_vertices_over'])}")


main()
