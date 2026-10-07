"""Headless Blender preview (OFFLINE, writes only Saved/CodexFlatV3/flutter/preview/).
Left card: live P04_real_13 R as built today (5 flaps, curl 0.63-0.95 cm, flutter peak = 3 cm * VC.R).
Right card: proposal (12 flaps from the bit-identical rebuild, curl 2.5-6 cm, flutter peak 6 cm).
Flap geometry follows build_v3_flat.create_flaps (build_v3_flat.py:1543-1580): outline n-gon, weight
clip((axis-0.18)/0.52), x = front - 0.001 - sin(w*pi/2)*curl; flutter adds -w*amp along X (the master's
CODE_FLUTTER at its positive peak). Not the Unreal material: a plain image texture on UV0."""
import bpy, json, math, sys
from pathlib import Path
ST = Path(r"E:\PussStage\DerivedAssets\FlatV3\Realism_20261007\P04_gothic_blasted_trees\13_gothic_arch_ruin\stage1\P04_real_13_gothic_arch_ruin_R\skin_v3")
OWNER = "P04_real_13_gothic_arch_ruin_R"
FL = Path(r"E:\PussStage\Saved\CodexFlatV3\flutter")
OUT = FL / "preview"; OUT.mkdir(exist_ok=True)
man = json.loads((ST / f"{OWNER}_skin_manifest.json").read_text())
PW, PH = [v / 100.0 for v in man["panel_size_cm"]]
live = json.loads((ST / f"{OWNER}_flaps.json").read_text())["flaps"]
more = json.loads((FL / "skin_gate" / "B_maxflaps" / f"{OWNER}_flaps.json").read_text())["flaps"]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
img = bpy.data.images.load(str(ST / f"T_{OWNER}_SkinColor_o2.png"))

def mat(name, back_dark=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UV0"
    nt.links.new(uvn.outputs[0], tex.inputs[0])
    if back_dark:
        geo = nt.nodes.new("ShaderNodeNewGeometry"); mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.inputs[2].default_value = (0.2, 0.06, 0.04, 1)  # BackingColor (WingMateriality.md:55-57)
        nt.links.new(geo.outputs["Backfacing"], mix.inputs[0]); nt.links.new(tex.outputs[0], mix.inputs[1])
        nt.links.new(mix.outputs[0], bsdf.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs[1], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.7
    return m
MB, MF = mat("Board"), mat("Flap", True)

def uv_to_yz(u, v, oy):   # card in the Y/Z plane, front faces -X; U runs along +Y here (preview only)
    return (oy + (u - 0.5) * PW, v * PH)

def card(flaps, oy, curl_scale, curl_min, amp_m, tag):
    me = bpy.data.meshes.new("board" + tag)
    vs = [(0, *uv_to_yz(u, v, oy)) for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
    me.from_pydata(vs, [], [(0, 1, 2, 3)]); uv = me.uv_layers.new(name="UV0")
    for i, l in enumerate(me.loops): uv.data[i].uv = ((0, 0), (1, 0), (1, 1), (0, 1))[l.vertex_index]
    ob = bpy.data.objects.new("board" + tag, me); sc.collection.objects.link(ob); me.materials.append(MB)
    for k, f in enumerate(flaps):
        pts = [(float(a), float(b)) for a, b in f["outline_uv_bottom_left"]]
        hor = f["orientation"] == "horizontal"
        ax = [p[1] if hor else p[0] for p in pts]; lo, hi = min(ax), max(ax)
        curl = max(curl_min, f["curl_cm"] * curl_scale) / 100.0
        verts = []
        for (u, v), a in zip(pts, ax):
            w = min(1, max(0, ((a - lo) / max(hi - lo, 1e-6) - 0.18) / 0.52))
            y, z = uv_to_yz(u, v, oy)
            verts.append((-0.001 - math.sin(w * math.pi / 2) * curl - w * amp_m, y, z))
        m2 = bpy.data.meshes.new(f"flap{tag}{k}"); m2.from_pydata(verts, [], [tuple(reversed(range(len(verts))))])
        u2 = m2.uv_layers.new(name="UV0")
        for i, l in enumerate(m2.loops): u2.data[i].uv = pts[l.vertex_index]
        o2 = bpy.data.objects.new(f"flap{tag}{k}", m2); sc.collection.objects.link(o2); m2.materials.append(MF)

GAP = PW + 1.0
card(live, -GAP / 2, 1.0, 0.0, 0.03, "A")
card(more, GAP / 2, 6.0, 2.5, 0.06, "B")
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.0; sun.rotation_euler = (math.radians(70), 0, math.radians(-60))   # raking, from the side
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
try: sc.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError: sc.render.engine = "CYCLES"
sc.render.resolution_x, sc.render.resolution_y = 1800, 1400
def shoot(name, loc, look, lens):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); sc.collection.objects.link(cam)
    cam.data.lens = lens; cam.location = loc
    d = [look[i] - loc[i] for i in range(3)]
    import mathutils
    cam.rotation_euler = mathutils.Vector(d).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam; sc.render.filepath = str(OUT / f"{name}.png"); bpy.ops.render.render(write_still=True)
shoot("overview_3q", (-11.0, -6.0, 4.0), (0, 0, PH * 0.42), 30)
for idx in (0, 1):
    pts = more[idx]["outline_uv_bottom_left"]; cu = sum(p[0] for p in pts) / len(pts); cv = sum(p[1] for p in pts) / len(pts)
    ty, tz = uv_to_yz(cu, cv, GAP / 2)
    shoot(f"closeup_B_flap{idx+1}", (-1.6, ty - 1.4, tz + 0.3), (0, ty, tz), 40)
    lu = live[idx]["outline_uv_bottom_left"]; cu = sum(p[0] for p in lu) / len(lu); cv = sum(p[1] for p in lu) / len(lu)
    ty, tz = uv_to_yz(cu, cv, -GAP / 2)
    shoot(f"closeup_A_flap{idx+1}", (-1.6, ty - 1.4, tz + 0.3), (0, ty, tz), 40)
print("PREVIEW_OK", OUT)
