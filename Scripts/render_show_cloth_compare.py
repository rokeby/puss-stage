"""Show-cloth comparison for Gary (29 Sep): which cloth carries a shadow play at a passage mouth? Headless Blender 4.4,
Cycles CPU. Reads and writes nothing in Unreal.

    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup -t 16 --python Scripts/render_show_cloth_compare.py

Gary: "It should have lights in front of it.. it's a stage curtain..". So FRONT-LIT is the headline: a small lantern
downstage, a flat cat cut-out between the lantern and the cloth (casting only a shadow, hidden from camera), in a
near-dark box. Panels (Blender metres; the cloth hangs in the x-z plane at y = 0, the audience is at -y):
  front_<cloth>_flat      velvet | calico | scrim, flat-hanging
  front_calico_<pleats>   calico with shallow / deep sine pleats at the pattern's 0.85 m fold wavelength
  reveal_scrim_on         the scrim with the passage behind it lit (front lantern still on): the scrim's reveal
  back_<cloth>_flat       secondary: lantern and cut-out BEHIND the cloth (wayang), velvet | calico | scrim
The passage behind (floor, three pairs of pale flats, back wall) is present in every panel and unlit except
"reveal". Writes Saved/CodexSoftGoods/ShowCloth/<panel>.png and panels.json; the card is Scripts/show_cloth_card.py.
"""
import json
import math
import os
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Saved" / "CodexSoftGoods" / "ShowCloth"
RES = (int(os.environ.get("RES_X", "960")), int(os.environ.get("RES_Y", "540")))
SAMPLES = int(os.environ.get("SAMPLES", "64"))
ONLY = [p for p in os.environ.get("ONLY", "").split(",") if p]
WAVE = 0.85
PLEATS = {"flat": 0.0, "shallow": 0.08, "deep": 0.25}
CLOTH_W, CLOTH_H = 12.0, 8.0
FRONT_LANTERN = (0.6, -7.0, 2.5)
BACK_LANTERN = (0.6, 7.0, 2.5)
AIM = (0.0, 0.0, 3.5)


def fullness(amplitude):
    """Cloth width per metre of track for a sine pleat of this amplitude (numeric arc length)."""
    n, k = 2000, 2 * math.pi / WAVE
    return sum(math.sqrt(1 + (amplitude * k * math.cos(k * WAVE * i / n)) ** 2) for i in range(n)) / n


def mesh_object(name, verts, faces, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cloth(name, amplitude):
    cols, rows = 401, 5
    verts = []
    for r in range(rows):
        z = CLOTH_H * r / (rows - 1)
        for c in range(cols):
            x = -CLOTH_W / 2 + CLOTH_W * c / (cols - 1)
            verts.append((x, amplitude * math.sin(2 * math.pi * x / WAVE), z))
    faces = [(r * cols + c, r * cols + c + 1, (r + 1) * cols + c + 1, (r + 1) * cols + c)
             for r in range(rows - 1) for c in range(cols - 1)]
    return mesh_object(name, verts, faces)


def box(name, centre, size, mat):
    cx, cy, cz = centre
    sx, sy, sz = (s / 2 for s in size)
    verts = [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = mesh_object(name, verts, faces, smooth=False)
    ob.data.materials.append(mat)
    return ob


def cat(name, y, anchor):
    """A sitting cat in profile, flat in the x-z plane at depth y; anchor = where its middle (0, 0.4) goes."""
    ax, az = anchor
    parts = []

    def ellipse(cx, cz, rx, rz, n=48):
        return [(cx + rx * math.cos(2 * math.pi * i / n), cz + rz * math.sin(2 * math.pi * i / n)) for i in range(n)]

    parts.append(ellipse(0.0, 0.26, 0.21, 0.27))                       # body
    parts.append(ellipse(0.03, 0.60, 0.13, 0.12))                      # head
    parts.append([(-0.08, 0.66), (-0.02, 0.70), (-0.09, 0.82)])        # ears
    parts.append([(0.07, 0.70), (0.14, 0.66), (0.14, 0.82)])
    parts.append(ellipse(-0.12, 0.03, 0.12, 0.05))                     # front paws
    tail = [(0.10 + 0.34 * math.sin(t * math.pi / 2), 0.06 + 0.30 * (1 - math.cos(t * math.pi / 2)) ** 1.2)
            for t in [i / 12 for i in range(13)]]
    for i in range(len(tail) - 1):                                      # tail: a curling band of quads
        (x0, z0), (x1, z1) = tail[i], tail[i + 1]
        w = 0.035
        parts.append([(x0 - w, z0), (x1 - w, z1), (x1 + w, z1), (x0 + w, z0)])
    verts, faces = [], []
    for part in parts:
        base = len(verts)
        verts += [(ax + x, y, az + (z - 0.4)) for x, z in part]
        faces.append(tuple(range(base, base + len(part))))
    ob = mesh_object(name, verts, faces, smooth=False)
    ob.visible_camera = False
    ob.visible_glossy = False
    ob.visible_transmission = False
    return ob


def material(name, build):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(build(nt), out.inputs["Surface"])
    return m


def principled(nt, colour, roughness=1.0, sheen=0.0, sheen_rough=0.3, sheen_tint=(1, 1, 1, 1)):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = colour
    p.inputs["Roughness"].default_value = roughness
    for key, value in (("Sheen Weight", sheen), ("Sheen Roughness", sheen_rough), ("Sheen Tint", sheen_tint),
                       ("Specular IOR Level", 0.2)):
        if key in p.inputs:
            p.inputs[key].default_value = value
    return p.outputs["BSDF"]


def mix(nt, a, b, fac):
    m = nt.nodes.new("ShaderNodeMixShader")
    m.inputs["Fac"].default_value = fac
    nt.links.new(a, m.inputs[1])
    nt.links.new(b, m.inputs[2])
    return m.outputs["Shader"]


def make_materials():
    velvet = material("Velvet", lambda nt: principled(nt, (0.16, 0.008, 0.015, 1), 1.0, sheen=1.0, sheen_rough=0.35,
                                                      sheen_tint=(0.9, 0.45, 0.45, 1)))

    def calico_build(nt):
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
        tr.inputs["Color"].default_value = (0.75, 0.66, 0.52, 1)
        return mix(nt, principled(nt, (0.78, 0.72, 0.60, 1), 1.0), tr.outputs["BSDF"], 0.3)

    def scrim_build(nt):
        tp = nt.nodes.new("ShaderNodeBsdfTransparent")
        return mix(nt, tp.outputs["BSDF"], principled(nt, (0.72, 0.72, 0.70, 1), 1.0), 0.55)   # 55% thread cover

    calico = material("Calico", calico_build)
    scrim = material("Scrim", scrim_build)
    floor = material("Floor", lambda nt: principled(nt, (0.05, 0.04, 0.035, 1), 0.6))
    flats = material("Flats", lambda nt: principled(nt, (0.5, 0.45, 0.38, 1), 1.0))
    wall = material("Wall", lambda nt: principled(nt, (0.03, 0.03, 0.035, 1), 1.0))
    black = material("CutOut", lambda nt: principled(nt, (0.0, 0.0, 0.0, 1), 1.0))
    return {"velvet": velvet, "calico": calico, "scrim": scrim, "floor": floor, "flats": flats, "wall": wall, "black": black}


def light(name, kind, loc, energy, target=None, size=None, spot_deg=None, radius=0.03, colour=(1.0, 0.86, 0.68)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = colour
    if kind == "SPOT":
        ld.spot_size = math.radians(spot_deg or 60)
        ld.spot_blend = 0.3
        ld.shadow_soft_size = radius
    if kind == "AREA":
        ld.size = size or 4
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    if target:
        tgt = bpy.data.objects.new(name + "_target", None)
        tgt.location = target
        bpy.context.scene.collection.objects.link(tgt)
        con = ob.constraints.new("TRACK_TO")
        con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    return ob


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.transparent_max_bounces = 12
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("NearDark")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.022, 0.03, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.05
    scene.world = world
    mats = make_materials()

    cloths = {k: cloth(f"Cloth_{k}", a) for k, a in PLEATS.items()}
    floor = mesh_object("Floor", [(-20, -20, 0), (20, -20, 0), (20, 14, 0), (-20, 14, 0)], [(0, 1, 2, 3)], smooth=False)
    floor.data.materials.append(mats["floor"])
    for y in (2.5, 5.0, 7.5):                                           # the passage: three pairs of flats
        for side in (-1, 1):
            box(f"Flat_{side}_{y}", (side * 3.6, y, 3.0), (2.0, 0.08, 6.0), mats["flats"])
    box("BackWall", (0, 11, 4), (20, 0.2, 8), mats["wall"])
    lantern_front = light("LanternFront", "SPOT", FRONT_LANTERN, 2500, AIM, spot_deg=70)
    lantern_back = light("LanternBack", "SPOT", BACK_LANTERN, 2500, AIM, spot_deg=70)
    t = 1.5 / 7.0                                                       # cut-out 1.5 m in front of its lantern
    anchor_front = (FRONT_LANTERN[0] + (AIM[0] - FRONT_LANTERN[0]) * t, FRONT_LANTERN[2] + (AIM[2] - FRONT_LANTERN[2]) * t)
    cat_front = cat("CatFront", FRONT_LANTERN[1] + 1.5, anchor_front)
    cat_back = cat("CatBack", BACK_LANTERN[1] - 1.5, anchor_front)
    for c in (cat_front, cat_back):
        c.data.materials.append(mats["black"])
    passage = [light("PassageWash", "AREA", (0, 5.5, 7.5), 2500, (0, 5.5, 0), size=6, colour=(1.0, 0.8, 0.55)),
               light("PassageSideL", "SPOT", (-2.5, 1.5, 6), 2500, (0, 7, 1), spot_deg=60, radius=0.2),
               light("PassageSideR", "SPOT", (2.5, 1.5, 6), 2500, (0, 7, 1), spot_deg=60, radius=0.2)]
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam)
    cam.location = (0, -13, 2.2)
    cam.data.lens = 35
    tgt = bpy.data.objects.new("CamTarget", None)
    tgt.location = (0, 0, 3.4)
    scene.collection.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam

    panels = []
    for c in ("velvet", "calico", "scrim"):
        panels.append((f"front_{c}_flat", c, "flat", "front", False))
    panels += [("front_calico_shallow", "calico", "shallow", "front", False),
               ("front_calico_deep", "calico", "deep", "front", False),
               ("front_velvet_deep", "velvet", "deep", "front", False),
               ("reveal_scrim_on", "scrim", "flat", "front", True)]
    for c in ("velvet", "calico", "scrim"):
        panels.append((f"back_{c}_flat", c, "flat", "back", False))
    OUT.mkdir(parents=True, exist_ok=True)
    done = []
    for name, cloth_mat, pleat, side, passage_on in panels:
        if ONLY and name not in ONLY:
            continue
        for k, ob in cloths.items():
            ob.hide_render = k != pleat
            ob.data.materials.clear()
            ob.data.materials.append(mats[cloth_mat])
        lantern_front.data.energy = 2500 if side == "front" else 0
        lantern_back.data.energy = 2500 if side == "back" else 0
        cat_front.hide_render = side != "front"
        cat_back.hide_render = side != "back"
        for p in passage:
            p.data.energy = 2500 if passage_on else 0
        scene.render.filepath = str(OUT / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        done.append(name)
        print(f"SHOW_CLOTH_PANEL|{name}")
    meta = {"panels": done, "fullness": {k: round(fullness(a), 2) for k, a in PLEATS.items()}, "wave_m": WAVE,
            "cloth_m": [CLOTH_W, CLOTH_H], "front_lantern": FRONT_LANTERN, "samples": SAMPLES, "res": RES}
    (OUT / "panels.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("SHOW_CLOTH_DONE|" + json.dumps(meta))


if __name__ == "__main__":
    main()
