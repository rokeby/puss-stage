"""Headless Blender renders of the BUILT variant-B set (the 12 Flat V3 FBXs + their SkinColor) from S3 Shot B09 and
B02, in the same box / shore / backdrop / B lighting as the design board (s3_waves_v3_preview_blender.py).  OFFLINE.

  "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup \
      --python Saved/CodexConductor/S3Waves/s3_waves_v3_B_preview_blender.py -- --samples 48

Each FBX is a FRESH import of the shipped file (LOD0 shown, LOD1 hidden), placed at its planned root-local mount
(UE (x, y, z) cm -> Blender (x, -y, z) / 100, s3_shore_blender_build.py:70 convention).  Flap polygons (peel + foam)
are visible at rest; their flutter is Unreal WPO and is NOT simulated here.  Lighting = the design board's B setup
with the ground rows / warm side placed as the LIGHT plan places them (s3_waves_v3_core.light_specs).
Writes DerivedAssets/FlatV3/Scene3/waves_v3/B_build/previews/built_B_<shot>.png + manifest.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B_BUILD = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "waves_v3", "B_build")
OUT = os.path.join(B_BUILD, "previews")
SHORE_BLEND = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround.blend")
BACKDROP = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "backdrop", "textures",
                        "T_S3_OpalBeach_Backdrop_SkinColor.png")
FLOOR = 115.0
SHOTS = {"B09_axis": ((2100.0, 0.0, 290.0), (0.0, -6.3335, 0.0), 35.0),
         "B02_wide": ((2200.0, -250.0, 290.0), (0.0, -6.7966, 17.354), 35.0)}
CFG = {"key_rgb": (0.74, 0.82, 0.92), "key_w": 2600.0, "fill_rgb": (0.62, 0.72, 0.78), "fill_w": 400.0,
       "ground_rgb": (0.62, 0.78, 0.92), "ground_w": 180.0,
       "warm_rgb": (1.00, 0.66, 0.38), "warm_w": 1500.0,
       "haze_rgb": (0.70, 0.74, 0.74), "haze_density": 0.018, "world": (0.04, 0.045, 0.05)}


def load_core():
    import importlib.util
    spec = importlib.util.spec_from_file_location("s3wv3_core_prev", os.path.join(HERE, "s3_waves_v3_core.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ue(x, y, z):
    return x / 100.0, -y / 100.0, z / 100.0


def mat_simple(name, rgb, rough=0.7):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Roughness"].default_value = rough
    return m


def mat_skin(name, path, uv="UV0"):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.interpolation = "Cubic"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = uv
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.55
    return m


def box(name, lo, hi, material):
    x0, y0, z0 = ue(*lo)
    x1, y1, z1 = ue(*hi)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.active_object
    ob.name = name
    ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    ob.scale = (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
    ob.data.materials.append(material)
    return ob


def quad(name, corners, material):
    me = bpy.data.meshes.new(name)
    me.from_pydata([ue(*c) for c in corners], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name="UV")
    for li, loop in enumerate(me.loops):
        me.uv_layers[0].data[li].uv = ((0, 0), (1, 0), (1, 1), (0, 1))[loop.vertex_index]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def area_light(name, loc, target, rgb, watts, size):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.color, ld.shape = watts, rgb, "RECTANGLE"
    ld.size, ld.size_y = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ue(*loc)
    ob.rotation_euler = (Vector(ue(*target)) - Vector(ue(*loc))).to_track_quat("-Z", "Y").to_euler()
    return ob


def camera(name, loc, rpy, lens):
    cam = bpy.data.cameras.new(name)
    cam.lens, cam.sensor_width, cam.clip_start = lens, 23.76, 0.05
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ue(*loc)
    ob.rotation_euler = (math.radians(90.0 + rpy[1]), 0.0, math.radians(-90.0 - rpy[2]))
    return ob


def static_scene():
    with bpy.data.libraries.load(SHORE_BLEND, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("SM_S3_ShoreGround")]
    sand = mat_simple("Sand", (0.34, 0.31, 0.27), 0.9)
    for ob in dst.objects:
        if ob is not None and ob.type == "MESH":
            bpy.context.scene.collection.objects.link(ob)
            ob.data.materials.clear()
            ob.data.materials.append(sand)
    marble = mat_simple("Marble", (0.45, 0.44, 0.42), 0.25)
    box("Deck", (0, -1000, 95), (6000, 1000, 114.5), mat_simple("Oak", (0.18, 0.12, 0.08), 0.6))
    box("Marble L", (0, -1050, 115), (6000, -999, 1300), marble)
    box("Marble R", (0, 999, 115), (6000, 1050, 1300), marble)
    box("Far Wall", (6000, -1050, -100), (6050, 1050, 3200), mat_simple("Black", (0.02, 0.02, 0.02), 0.8))
    bd = bpy.data.materials.new("Backdrop")
    bd.use_nodes = True
    t = bd.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(BACKDROP)
    bs = next(n for n in bd.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bd.node_tree.links.new(t.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.8
    quad("Backdrop", [(5997, -1000, -35), (5997, 1000, -35), (5997, 1000, 2965), (5997, -1000, 2965)], bd)


def import_pieces(report):
    timber = mat_simple("TimberPrev", (0.20, 0.15, 0.10), 0.7)
    placed = []
    for suffix, row in sorted(report["pieces"].items()):
        folder = os.path.join(B_BUILD, "pieces", suffix)
        fbx = os.path.join(folder, "SM_FlatV3_%s.fbx" % suffix)
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=fbx, use_custom_normals=True)
        new = [o for o in bpy.context.scene.objects if o not in before]
        skin = mat_skin("Skin_" + suffix, os.path.join(folder, "T_%s_SkinColor.png" % suffix))
        lod0 = [o for o in new if o.type == "MESH" and "_LOD0" in o.name]
        if len(lod0) != 1:
            raise RuntimeError("LOD0 %s %s" % (suffix, [o.name for o in new]))
        for o in new:
            if o.type == "MESH" and "_LOD1" in o.name:
                o.hide_render = True
        ob = lod0[0]
        ob.parent = None
        mx = row["mount_local"]
        ob.location = ue(*mx)
        ob.rotation_euler = (0, 0, 0)
        ob.scale = (1, 1, 1)
        for i, slot in enumerate(ob.material_slots):
            ob.material_slots[i].material = skin if i in (0, 1) else timber
        placed.append(ob.name)
    return placed


def lights(core):
    area_light("Key", (1500, -780, 2200), (4500, 820, 700), CFG["key_rgb"], CFG["key_w"], (9.0, 5.0))
    area_light("Fill", (2400, 850, 1500), (4300, -700, 650), CFG["fill_rgb"], CFG["fill_w"], (12.0, 7.0))
    for s in core.light_specs():
        if s["kind"] == "ground_row":
            area_light(s["label"], s["location"], s["target"], CFG["ground_rgb"], CFG["ground_w"], (19.0, 0.12))
        else:
            area_light(s["label"], s["location"], s["target"], CFG["warm_rgb"], CFG["warm_w"], (2.0, 1.2))
    hz = bpy.data.materials.new("Haze")
    hz.use_nodes = True
    nt = hz.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*CFG["haze_rgb"], 1)
    vol.inputs["Density"].default_value = CFG["haze_density"]
    vol.inputs["Anisotropy"].default_value = 0.45
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    b = core.HAZE["box_local"]
    h = box("Haze", tuple(b["min"]), tuple(b["max"]), hz)
    h.visible_shadow = False


def main():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(raw[raw.index("--samples") + 1]) if "--samples" in raw else 48
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    core = load_core()
    report = json.load(open(os.path.join(B_BUILD, "build_report_B.json"), encoding="utf-8"))
    static_scene()
    placed = import_pieces(report)
    lights(core)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.volume_step_rate = 4.0
    sc.cycles.max_bounces = 4
    sc.cycles.seed = 7
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    world = sc.world or bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*CFG["world"], 1)
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    manifest = {"placed": placed, "renders": [], "lighting": CFG, "samples": samples}
    for shot, pose in SHOTS.items():
        sc.camera = camera("C_" + shot, *pose)
        path = os.path.join(OUT, "built_B_%s.png" % shot)
        sc.render.filepath = path
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        manifest["renders"].append({"shot": shot, "file": path, "pose": pose, "seconds": round(time.time() - t0, 1)})
        print("S3WAVESV3B_RENDER", shot, round(time.time() - t0, 1), flush=True)
    json.dump(manifest, open(os.path.join(OUT, "built_B_manifest.json"), "w", encoding="utf-8"), indent=1)
    print("S3WAVESV3B_PREVIEW_OK")


main()
