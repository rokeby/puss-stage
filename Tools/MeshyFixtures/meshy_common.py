"""Shared helpers for the Meshy fixture cleanup (Blender 4.4 headless)."""
import bpy, bmesh, glob, os, re
import numpy as np
from mathutils import Vector

ROOT = r"E:\PussStage\DerivedAssets\Lighting\Meshy"

def list_sources():
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
        if not os.path.isdir(d): continue
        tex = glob.glob(os.path.join(d, "*-texture.png"))
        m = re.match(r"Meshy_AI_(SM_.+?)_\d{10}_", os.path.basename(tex[0]))
        name = m.group(1).replace("FresnelDoo", "FresnelDoors")
        out[name] = {"uuid": os.path.basename(d), "dir": d, "basecolor": tex[0],
                     "metallic": os.path.join(d, "Meshy_AI_texture_0_metallic.png"),
                     "normal": os.path.join(d, "Meshy_AI_texture_0_normal.png"),
                     "roughness": os.path.join(d, "Meshy_AI_texture_0_roughness.png")}
    return out

def load_img(path):
    im = bpy.data.images.load(path, check_existing=True)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, im.channels)
    return a

def sample(arr, uv):
    h, w = arr.shape[:2]
    x = min(w - 1, max(0, int((uv[0] % 1.0) * w)))
    y = min(h - 1, max(0, int((uv[1] % 1.0) * h)))
    return arr[y, x]

def face_samples(bm, arr, uvl, n=4):
    """Per-face mean texel over centroid + a few corner-weighted points."""
    out = np.zeros((len(bm.faces), arr.shape[2]), dtype=np.float32)
    for f in bm.faces:
        uvs = [l[uvl].uv for l in f.loops]
        c = sum(uvs, Vector((0, 0))) / len(uvs)
        pts = [c] + [c.lerp(u, 0.5) for u in uvs]
        out[f.index] = np.mean([sample(arr, p) for p in pts], axis=0)
    return out

def lum(rgb):
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

def import_source(src):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(src["dir"], "Meshy_AI_model.fbx"))
    obs = [o for o in bpy.data.objects if o.type == "MESH"]
    assert len(obs) == 1, obs
    ob = obs[0]
    for o in list(bpy.data.objects):
        if o is not ob: bpy.data.objects.remove(o)
    ob.parent = None
    return ob
