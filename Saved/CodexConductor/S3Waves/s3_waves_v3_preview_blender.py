"""Headless Blender perspective previews of the S3 waves v3 layers inside the S3 box (OFFLINE, read-only inputs).

  "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup \
      --python Saved/CodexConductor/S3Waves/s3_waves_v3_preview_blender.py -- --variants A,B --samples 48

Scene, in S3 Hangar Root LOCAL cm converted UE->Blender as (x, -y, z)/100 (same as s3_shore_blender_build.py:70):
  - shore ground: object SM_S3_ShoreGround appended read-only from DerivedAssets/S3Shore/SM_S3_ShoreGround.blend
  - side marble walls y +-999..1050, z 115..1300; deck under the shore
  - backdrop plane x 5997, y +-1000, z -35..2965 (lowered 150 cm on 7 Oct) with the built SkinColor
  - six wave cards per variant (alpha = cut mask) at their root-local x, base at the floor top (z 115)
  - lighting per variant: see LIGHTING below; haze = homogeneous volume box over the sea band only
Renders the brief's main pose (S3 Shot B04) and the axis view (S3 Shot B09), poses from s3_shore_footprint.json.
Writes only DerivedAssets/FlatV3/Scene3/waves_v3/previews/persp_<variant>_<shot>.png + persp_manifest.json.
"""
import json
import math
import os
import sys
import time

import bpy

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ROOT = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "waves_v3")
PREV = os.path.join(ROOT, "previews")
SHORE_BLEND = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround.blend")
BACKDROP = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "backdrop", "textures",
                        "T_S3_OpalBeach_Backdrop_SkinColor.png")
FLOOR = 115.0
SHOTS = {  # s3_shore_footprint.json cameras.rows (declaration, 1 Oct shot list)
    "B04_main": ((3000.0, -750.0, 240.0), (0.0, -5.4642, 75.4572), 35.0),
    "B09_axis": ((2100.0, 0.0, 290.0), (0.0, -6.3335, 0.0), 35.0),
    "B02_wide": ((2200.0, -250.0, 290.0), (0.0, -6.7966, 17.354), 35.0),
    "B05_tele": ((2700.0, 0.0, 260.0), (0.0, -7.098, -0.0467), 85.0),
}
LIGHTING = {
    # key = the existing "S3 Daylight Rake Key" placement (s3_daylight_apply.py:47-49), recoloured per variant
    "A": {"key_rgb": (0.70, 0.80, 1.00), "key_w": 3200.0, "fill_rgb": (0.60, 0.72, 0.90), "fill_w": 450.0,
          "ground_rgb": (0.55, 0.78, 0.95), "ground_w": 220.0, "warm": None,
          "haze_rgb": (0.62, 0.70, 0.78), "haze_density": 0.022, "world": (0.035, 0.042, 0.055)},
    "B": {"key_rgb": (0.78, 0.84, 0.88), "key_w": 2600.0, "fill_rgb": (0.62, 0.72, 0.78), "fill_w": 400.0,
          "ground_rgb": (0.62, 0.82, 0.80), "ground_w": 180.0,
          "warm": {"rgb": (1.00, 0.66, 0.38), "w": 1500.0, "loc": (2600.0, -980.0, 260.0), "target": (5000.0, 400.0, 230.0)},
          "haze_rgb": (0.70, 0.74, 0.74), "haze_density": 0.018, "world": (0.04, 0.045, 0.05)},
}


def argv_opts():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"variants": ["A", "B"], "samples": 48, "res": (1600, 900), "shots": list(SHOTS)}
    for i, a in enumerate(raw):
        if a == "--variants":
            opts["variants"] = raw[i + 1].split(",")
        if a == "--samples":
            opts["samples"] = int(raw[i + 1])
        if a == "--shots":
            opts["shots"] = raw[i + 1].split(",")
    return opts


def ue(x, y, z):
    return x / 100.0, -y / 100.0, z / 100.0


def mat_simple(name, rgb, rough=0.7):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Roughness"].default_value = rough
    return m


def mat_image(name, path, alpha=True, rough=0.55):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], bs.inputs["Base Color"])
    if alpha:
        nt.links.new(tex.outputs["Alpha"], bs.inputs["Alpha"])
        try:
            m.blend_method = "CLIP"
        except Exception:
            pass
    bs.inputs["Roughness"].default_value = rough
    return m


def quad(name, corners_ue, material, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    """corners in UE local cm, order: bottom-left, bottom-right, top-right, top-left AS SEEN FROM THE CAMERA."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([ue(*c) for c in corners_ue], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name="UV")
    for li, loop in enumerate(me.loops):
        me.uv_layers[0].data[li].uv = uv[loop.vertex_index]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


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


def area_light(name, loc, target, rgb, watts, size, shape="RECTANGLE"):
    from mathutils import Vector
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = watts
    ld.color = rgb
    ld.shape = shape
    ld.size, ld.size_y = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ue(*loc)
    d = Vector(ue(*target)) - Vector(ue(*loc))
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def add_camera(name, loc, rpy, lens):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 23.76
    cam.clip_start = 0.05
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ue(*loc)
    roll, pitch, yaw = rpy
    ob.rotation_euler = (math.radians(90.0 + pitch), 0.0, math.radians(-90.0 - yaw))   # s3_shore_blender_build.py:271
    return ob


def build_static():
    with bpy.data.libraries.load(SHORE_BLEND, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("SM_S3_ShoreGround")]
    sand = mat_simple("Sand", (0.34, 0.31, 0.27), 0.9)
    shore = []
    for ob in dst.objects:
        if ob is None or ob.type != "MESH":
            continue
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.clear()
        ob.data.materials.append(sand)
        shore.append(ob.name)
    marble = mat_simple("Marble", (0.45, 0.44, 0.42), 0.25)
    black = mat_simple("Black", (0.02, 0.02, 0.02), 0.8)
    box("Deck", (0, -1000, 95), (6000, 1000, 114.5), mat_simple("Oak", (0.18, 0.12, 0.08), 0.6))
    box("Marble L", (0, -1050, 115), (6000, -999, 1300), marble)
    box("Marble R", (0, 999, 115), (6000, 1050, 1300), marble)
    box("Far Wall", (6000, -1050, -100), (6050, 1050, 3200), black)
    bd = mat_image("Backdrop", BACKDROP, alpha=False, rough=0.8)
    # image left = UE -Y (screen left when looking +X); cottages sit on the image's right
    quad("Backdrop", [(5997, -1000, -35), (5997, 1000, -35), (5997, 1000, 2965), (5997, -1000, 2965)], bd)
    return shore


def build_variant(variant):
    design = json.load(open(os.path.join(ROOT, variant, "design_%s.json" % variant), encoding="utf-8"))
    names = []
    for L in design["layers"]:
        v0, v1 = L["canvas_cm"]["v"]
        u0, u1 = L["canvas_cm"]["u"]
        m = mat_image("M_" + variant + L["id"], os.path.join(PROJECT, L["files"]["rgba"]))
        ob = quad("W_%s_%s" % (variant, L["id"]),
                  [(L["x"], u0, FLOOR + v0), (L["x"], u1, FLOOR + v0), (L["x"], u1, FLOOR + v1), (L["x"], u0, FLOOR + v1)], m)
        names.append(ob.name)
    return design, names


def build_lights(variant, design):
    cfg = LIGHTING[variant]
    objs = [area_light("Key", (1500, -780, 2200), (4500, 820, 700), cfg["key_rgb"], cfg["key_w"], (9.0, 5.0)),
            area_light("Fill", (2400, 850, 1500), (4300, -700, 650), cfg["fill_rgb"], cfg["fill_w"], (12.0, 7.0))]
    # ground rows: a hidden strip on the floor behind each layer, washing the layer BEHIND it from below
    xs = sorted(L["x"] for L in design["layers"])
    for i, x in enumerate(xs[:-1]):
        nxt = xs[i + 1]
        objs.append(area_light("Ground%d" % i, (x + 20, 0, FLOOR + 8), (nxt, 0, FLOOR + 160),
                               cfg["ground_rgb"], cfg["ground_w"], (19.0, 0.12)))
    objs.append(area_light("GroundLast", (xs[-1] + 25, 0, FLOOR + 8), (5997, 0, FLOOR + 400),
                           cfg["ground_rgb"], cfg["ground_w"] * 1.4, (19.0, 0.12)))
    if cfg["warm"]:
        w = cfg["warm"]
        objs.append(area_light("WarmSide", w["loc"], w["target"], w["rgb"], w["w"], (2.0, 1.2)))
    # haze over the sea band only (x 3550..5990, full width, floor..6 m)
    hz = mat_haze(cfg)
    haze = box("Haze", (3550, -995, 115), (5990, 995, 715), hz)
    haze.visible_shadow = False
    return objs + [haze]


def mat_haze(cfg):
    m = bpy.data.materials.new("Haze")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*cfg["haze_rgb"], 1)
    vol.inputs["Density"].default_value = cfg["haze_density"]
    vol.inputs["Anisotropy"].default_value = 0.45
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return m


def setup_render(opts, cfg):
    sc = bpy.context.scene
    try:
        sc.render.engine = "CYCLES"
    except TypeError as exc:
        raise RuntimeError("no Cycles: %s" % exc)
    sc.cycles.device = "CPU"
    sc.cycles.samples = opts["samples"]
    sc.cycles.use_denoising = True
    sc.cycles.volume_step_rate = 4.0
    sc.cycles.max_bounces = 4
    sc.cycles.seed = 7
    sc.render.resolution_x, sc.render.resolution_y = opts["res"]
    world = sc.world or bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*cfg["world"], 1)
    bg.inputs[1].default_value = 1.0
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0


def clear_variant(objs):
    for ob in objs:
        o = bpy.data.objects.get(ob) if isinstance(ob, str) else ob
        if o is not None:
            bpy.data.objects.remove(o, do_unlink=True)


def main():
    opts = argv_opts()
    os.makedirs(PREV, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shore = build_static()
    cams = {k: add_camera("C_" + k, *SHOTS[k]) for k in opts["shots"]}
    manifest = {"schema": "s3_waves_v3_persp/1", "shore_objects": shore, "renders": []}
    for variant in opts["variants"]:
        design, names = build_variant(variant)
        lights = build_lights(variant, design)
        setup_render(opts, LIGHTING[variant])
        for shot, cam in cams.items():
            sc = bpy.context.scene
            sc.camera = cam
            path = os.path.join(PREV, "persp_%s_%s.png" % (variant, shot))
            sc.render.filepath = path
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            manifest["renders"].append({"variant": variant, "shot": shot, "file": path, "pose": SHOTS[shot],
                                        "seconds": round(time.time() - t0, 1), "samples": opts["samples"],
                                        "lighting": LIGHTING[variant]})
            print("S3WAVESV3_RENDER", variant, shot, round(time.time() - t0, 1), flush=True)
        clear_variant(names + [o.name for o in lights])
    with open(os.path.join(PREV, "persp_manifest.json"), "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=1)
    print("S3WAVESV3_PERSP_OK")


main()
