"""Raw preview: 6 ortho views (+X,-X,+Y,-Y,+Z,-Z camera positions) of each Meshy export, textured, Workbench.
Also prints connected-component stats. Output: <scratch>/raw_<uuid>_<view>.png"""
import bpy, bmesh, glob, os, sys, json, math
from mathutils import Vector
ROOT = r"E:\PussStage\DerivedAssets\Lighting\Meshy"
OUT = sys.argv[sys.argv.index("--")+1]
VIEWS = {"px": (1,0,0), "nx": (-1,0,0), "py": (0,1,0), "ny": (0,-1,0), "pz": (0,0,1), "nz": (0,0,-1)}
stats = {}
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if not os.path.isdir(d): continue
    u = os.path.basename(d)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(d, "Meshy_AI_model.fbx"))
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    # components
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    seen = set(); comps = []
    for v in bm.verts:
        if v.index in seen: continue
        stack = [v]; seen.add(v.index); n = 0
        while stack:
            x = stack.pop(); n += 1
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen: seen.add(o.index); stack.append(o)
        comps.append(n)
    comps.sort(reverse=True)
    # image node present?
    mat = ob.material_slots[0].material
    imgs = [n.image.filepath for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image] if mat and mat.use_nodes else []
    stats[u] = {"components": len(comps), "top": comps[:8], "imgs": imgs}
    tex = glob.glob(os.path.join(d, "*-texture.png"))[0]
    if not imgs:
        mat.use_nodes = True
        nt = mat.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(tex)
        nt.links.new(t.outputs[0], bsdf.inputs[0])
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x = sc.render.resolution_y = 384
    w = bpy.data.worlds.new("w"); sc.world = w
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.2
    for k, dv in VIEWS.items():
        cam.location = Vector(dv) * 5
        up = "Y"
        cam.rotation_euler = (-Vector(dv) + Vector((0, 1e-3, 0)) * (k in ("pz","nz"))).to_track_quat("-Z", up).to_euler()
        sc.render.filepath = os.path.join(OUT, f"raw_{u[:8]}_{k}.png")
        bpy.ops.render.render(write_still=True)
print("STATS" + json.dumps(stats))
