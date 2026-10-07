"""Build SM_S3_ShoreGround in Blender from s3_shore_field.py, export FBX, render previews.

Run headless (does NOT touch any open Blender session):
  "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup \
      --python Saved/CodexConductor/S3Shore/s3_shore_blender_build.py -- [--no-render] [--grid 7.5]

Outputs (DerivedAssets/S3Shore/):
  SM_S3_ShoreGround.fbx          the mesh (single LOD, no LodGroup, one material slot)
  SM_S3_ShoreGround.blend        the working file (proxies in collection 'S3Context', not exported)
  SM_S3_ShoreGround_manifest.json  expected UE bounds, calibration vertices, checks, sha256
  previews/*.png                 look renders

Axis convention (INFERRED, gated on import): Blender default FBX export
(forward -Z, up Y) lands Blender (x, y, z) at UE (x, -y, z) with 1 BU = 1 m =
100 UE cm.  So UE-local (x, y, z) cm is authored at Blender (x/100, -y/100, z/100).
The mesh Y range is deliberately asymmetric (UE -1012 .. +1008) so the import
gate can detect a mirror from the bounding box alone.
"""
import hashlib
import json
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_shore_field as F  # noqa: E402

PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(PROJECT, "DerivedAssets", "S3Shore")
PREV = os.path.join(OUT, "previews")
NAME = "SM_S3_ShoreGround"
SLOT = "MI_S3_ShoreGround"
FLOOR_TOP = 115.0
SAMPLES = [32]
CALIBRATION = [(0.5, 0.25, 0.75, 1.0), (1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0), (0.0, 0.0, 1.0, 0.5)]


def argv_opts():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"render": "--no-render" not in argv, "sets": None, "samples": 32, "overview": "--overview" in argv}
    if "--grid" in argv:
        F.PARAMS["grid_cm"] = float(argv[argv.index("--grid") + 1])
    if "--set" in argv:
        F.PARAMS["height_set"] = argv[argv.index("--set") + 1]
    if "--sets" in argv:
        opts["sets"] = argv[argv.index("--sets") + 1].split(",")
    if "--samples" in argv:
        opts["samples"] = int(argv[argv.index("--samples") + 1])
    return opts


def pin_fbx_clock():
    """The FBX header carries datetime.now(); pin it so two builds of the same field are byte-identical."""
    import datetime as _dt
    import io_scene_fbx.export_fbx_bin as efb

    class _Clock:
        class datetime:
            @staticmethod
            def now():
                return _dt.datetime(2026, 10, 7, 0, 0, 0)
    efb.datetime = _Clock


def ue_to_blender(x, y, z):
    return x / 100.0, -y / 100.0, z / 100.0


def build_mesh(grid):
    X, Y, H = grid["X"], grid["Y"], grid["h"]
    nx, ny = H.shape
    Z = FLOOR_TOP + H
    # surface verts
    vx, vy, vz = ue_to_blender(X.ravel(), Y.ravel(), Z.ravel())
    verts = np.stack([vx, vy, vz], axis=1)
    cols = np.stack([grid["r"].ravel(), grid["g"].ravel(), grid["b"].ravel(), grid["a"].ravel()], axis=1)
    idx = np.arange(nx * ny).reshape(nx, ny)
    a = idx[:-1, :-1].ravel()
    b = idx[1:, :-1].ravel()
    c = idx[1:, 1:].ravel()
    d = idx[:-1, 1:].ravel()
    # winding: UE-space CCW seen from +Z becomes CW after the Y mirror -> order chosen so
    # Blender normals point +Z (checked below, before export).
    quads = np.stack([a, b, c, d], axis=1)
    # skirts: the 4 boundary loops dropped to the deck underside
    bottom = FLOOR_TOP - (FLOOR_TOP - F.PARAMS["skirt_bottom_local_z"])
    ring = np.concatenate([idx[:, 0], idx[-1, 1:], idx[::-1, -1][1:], idx[0, ::-1][1:-1]])
    base = verts.shape[0]
    rv = verts[ring].copy()
    rv[:, 2] = bottom / 100.0
    verts = np.concatenate([verts, rv])
    rc = np.tile(np.array([[0.0, 0.0, 0.0, 1.0]]), (len(ring), 1))
    cols = np.concatenate([cols, rc])
    n = len(ring)
    skirt = np.stack([ring, np.roll(ring, -1), base + (np.arange(n) + 1) % n, base + np.arange(n)], axis=1)
    faces = np.concatenate([quads, skirt])
    # calibration colours on 4 hidden skirt-bottom corner verts
    corners = []
    for k, (ix, iy) in enumerate([(0, 0), (nx - 1, 0), (nx - 1, ny - 1), (0, ny - 1)]):
        pos = int(np.where(ring == idx[ix, iy])[0][0])
        cols[base + pos] = CALIBRATION[k]
        corners.append({"ue_local": [float(X[ix, iy]), float(Y[ix, iy]), bottom], "rgba_linear": CALIBRATION[k]})

    me = bpy.data.meshes.new(NAME)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    nf = len(faces)
    me.loops.add(nf * 4)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", (np.arange(nf) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    # make the top surface face +Z
    up = np.zeros(len(me.polygons) * 3, dtype=np.float32)
    me.polygons.foreach_get("normal", up)
    top_nz = up.reshape(-1, 3)[: len(quads), 2]
    if np.median(top_nz) < 0:
        for poly in me.polygons:
            poly.flip()
        me.update()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))

    # colour attribute (per point, linear float)
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", cols.astype(np.float32).ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = 0

    # UV0: metres in UE space (u = x/100, v = y_ue/100); UV1: normalised 0..1
    lv = np.zeros(nf * 4, dtype=np.int32)
    me.loops.foreach_get("vertex_index", lv)
    co = verts[lv]
    ue_x, ue_y = co[:, 0] * 100.0, -co[:, 1] * 100.0
    uv0 = me.uv_layers.new(name="UVMap")
    uv0.data.foreach_set("uv", np.stack([ue_x / 100.0, ue_y / 100.0], 1).astype(np.float32).ravel())
    xr, yr = F.PARAMS["x_range"], F.PARAMS["y_range"]
    uv1 = me.uv_layers.new(name="UVNorm")
    uv1.data.foreach_set("uv", np.stack([(ue_x - xr[0]) / (xr[1] - xr[0]),
                                         (ue_y - yr[0]) / (yr[1] - yr[0])], 1).astype(np.float32).ravel())
    me.uv_layers.active_index = 0

    ob = bpy.data.objects.new(NAME, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(SLOT)
    build_preview_material(mat)
    me.materials.append(mat)
    return ob, corners, len(quads)


def build_preview_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs["Color"])
    # sand -> mud (R)
    mix1 = nt.nodes.new("ShaderNodeMix"); mix1.data_type = "RGBA"
    mix1.inputs[6].default_value = (0.66, 0.57, 0.43, 1)   # dry sand
    mix1.inputs[7].default_value = (0.13, 0.10, 0.075, 1)  # mud
    nt.links.new(sep.outputs[0], mix1.inputs[0])
    # moss (B)
    mix2 = nt.nodes.new("ShaderNodeMix"); mix2.data_type = "RGBA"
    mix2.inputs[7].default_value = (0.11, 0.16, 0.05, 1)
    nt.links.new(mix1.outputs[2], mix2.inputs[6])
    nt.links.new(sep.outputs[2], mix2.inputs[0])
    # wet darkening (G)
    wet = nt.nodes.new("ShaderNodeMix"); wet.data_type = "RGBA"; wet.blend_type = "MULTIPLY"
    wet.inputs[7].default_value = (0.45, 0.45, 0.47, 1)
    nt.links.new(sep.outputs[1], wet.inputs[0])
    nt.links.new(mix2.outputs[2], wet.inputs[6])
    # preview-only sand: fine grain in albedo and bump (real UE material is Megascans sand/mud)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 900.0
    noise.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeMix"); grain.data_type = "RGBA"; grain.blend_type = "OVERLAY"
    grain.inputs[0].default_value = 0.18
    nt.links.new(wet.outputs[2], grain.inputs[6])
    nt.links.new(noise.outputs["Color"], grain.inputs[7])
    nt.links.new(grain.outputs[2], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs[3].default_value = 0.9
    rough.inputs[4].default_value = 0.18
    nt.links.new(sep.outputs[1], rough.inputs[0])
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])


def context_proxies(fp):
    coll = bpy.data.collections.new("S3Context")
    bpy.context.scene.collection.children.link(coll)

    def box(name, lo, hi, color):
        x0, y0, z0 = ue_to_blender(*lo)
        x1, y1, z1 = ue_to_blender(*hi)
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        ob = bpy.context.active_object
        ob.name = name
        ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        ob.scale = (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
        m = bpy.data.materials.new("P_" + name)
        m.diffuse_color = color
        m.use_nodes = True
        bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bs.inputs["Base Color"].default_value = color
        bs.inputs["Roughness"].default_value = 0.15 if "Marble" in name else 0.6
        ob.data.materials.append(m)
        ob.visible_shadow = False      # preview: the 12 m walls would put a 12 deg raking sun in total shadow
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
        return ob

    marble = (0.82, 0.80, 0.76, 1)
    box("Marble L", (0, -1050, 115), (6000, -999, 1300), marble)
    box("Marble R", (0, 999, 115), (6000, 1050, 1300), marble)
    box("Backdrop", (5997, -1000, 115), (6050, 1000, 1300), (0.55, 0.62, 0.68, 1))
    box("Door", (5990, -150, 115), (5998, 150, 570), (0.02, 0.02, 0.02, 1))
    for row in fp["wave_rows"]["rows"]:
        top = {"Row1": 235, "Row2": 295, "Row3": 375}[row["name"]]
        box("Wave " + row["name"], (row["x"][0] + 30, -1000, 115), (row["x"][0] + 42, 1000, top), (0.20, 0.38, 0.52, 1))
    live = json.load(open(os.path.join(HERE, "s3_shore_live_reads.json"), encoding="utf-8"))
    for label, f in live["figures"].items():   # LIVE positions (DRY S3SHORE-20261007-181646); not re-seated
        px, py = f["local"]
        box("Fig " + label[:7], (px - 22, py - 22, f["foot_local_z"]), (px + 22, py + 22, f["local_aabb"]["max"][2]),
            (0.85, 0.83, 0.80, 1))
    for label, a in live["actors"].items():
        if label == "Clam_Pedastal":
            box("Pedestal", tuple(a["local_aabb"]["min"]), tuple(a["local_aabb"]["max"]), marble)
        elif label.startswith("S3 Beach V2 Rock"):
            box(label, tuple(a["local_aabb"]["min"]), tuple(a["local_aabb"]["max"]), (0.25, 0.24, 0.22, 1))
        elif label.startswith("S3 Beach V2 Seaweed"):
            box(label, tuple(a["local_aabb"]["min"]), tuple(a["local_aabb"]["max"]), (0.15, 0.25, 0.10, 1))
    # print band (where the hand prints start) as a thin dark line on each side wall
    # current print line (160, dark red) and the active set's proposed new minimum (dark blue)
    cur = fp["handprint_lowest_extent_above_floor_cm"]["value"]
    new = F.active_set()["print_line_cm"]
    for nm, z, col in (("PrintBand", cur, (0.3, 0.05, 0.05, 1)), ("NewPrintLine", new, (0.05, 0.08, 0.35, 1))):
        box(nm + " L", (0, -998.5, 115 + z), (6000, -998, 115 + z + 3), col)
        box(nm + " R", (0, 998, 115 + z), (6000, 998.5, 115 + z + 3), col)
        box(nm + " B", (5996, -1000, 115 + z), (5996.5, 1000, 115 + z + 3), col)
    return coll


def add_camera(name, loc_ue, rpy, lens, sensor=23.76):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = sensor
    cam.clip_start = 0.05
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ue_to_blender(*loc_ue)
    roll, pitch, yaw = rpy
    ob.rotation_euler = (math.radians(90.0 + pitch), 0.0, math.radians(-90.0 - yaw))
    ob["ue_yaw"] = float(yaw)
    return ob


def aim_sun(view_yaw_deg, elevation_deg=14.0, side_deg=70.0):
    """Raking sun per still: light travels at (view yaw + side_deg) in UE, i.e. from the back-left of the
    frame across it, 14 deg above the horizon, so heaps, crests and ripples throw shadows toward frame right."""
    from mathutils import Vector
    so = bpy.data.objects.get("Sun")
    if so is None:
        return
    a = math.radians(view_yaw_deg + side_deg)
    el = math.radians(elevation_deg)
    d_ue = Vector((math.cos(el) * math.cos(a), math.cos(el) * math.sin(a), -math.sin(el)))
    so.rotation_euler = Vector((d_ue.x, -d_ue.y, d_ue.z)).to_track_quat("-Z", "Y").to_euler()


def setup_render(engine_pref):
    sc = bpy.context.scene
    engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for e in engine_pref:
        if e in engines:
            try:
                sc.render.engine = e
                break
            except TypeError:
                continue
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("W") if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.6, 0.66, 1)
    bg.inputs[1].default_value = 0.35
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        sun = bpy.data.lights.new("Sun", "SUN")
        sun.energy = 7.0
        sun.angle = math.radians(1.0)
        so = bpy.data.objects.new("Sun", sun)
        sc.collection.objects.link(so)
        # LOW RAKING light (12 deg) from the mouth / left-wall side, travelling +x and toward the right wall:
        # it crosses the wind-ripple crests and grazes the heaps so relief reads
        from mathutils import Vector
        el = math.radians(12.0)
        d_ue = Vector((math.cos(el) * 0.8, math.cos(el) * 0.6, -math.sin(el)))
        d_bl = Vector((d_ue.x, -d_ue.y, d_ue.z))
        so.rotation_euler = d_bl.to_track_quat("-Z", "Y").to_euler()
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = SAMPLES[0]
        sc.cycles.use_denoising = True
    return sc.render.engine


HIDE_FOR = {  # preview readability only: proxies hidden per shot (walls/waves would block or shadow the floor)
    "overview_from_mouth": ("Marble", "Backdrop"),
    "drift_left_wall": ("Marble R", "Backdrop", "Wave", "Door"),
    "back_wall_drifts_door": ("Wave", "Marble"),
    "mud_front_low": ("Marble", "Backdrop"),
    # close dune stills: the cast/rock proxies are 44 cm AABB boxes that block the walls; hidden (the cast floats
    # anyway and Gary re-arranges it).  Wave flats stay (they are full-width proxies of real flats).
    "wall_main_B04": ("Fig", "Pedestal", "S3 Beach V2"),
    "corner_back_right": ("Fig", "Pedestal", "S3 Beach V2"),
    "wall_left_close": ("Fig", "Pedestal", "S3 Beach V2"),
}


def render(cam, path):
    sc = bpy.context.scene
    key = os.path.splitext(os.path.basename(path))[0]
    for o in bpy.data.objects:
        if o.users_collection and o.users_collection[0].name == "S3Context":
            hide = next((v for k, v in HIDE_FOR.items() if key == k or key.endswith("_" + k)), ())
            o.hide_render = any(o.name.startswith(p) for p in hide)
    if "ue_yaw" in cam.keys():
        aim_sun(cam["ue_yaw"], side_deg=SUN_SIDE.get(next((k for k in SUN_SIDE if key.endswith(k)), ""), 70.0))
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# Close previews (Gary judges on these).  MAIN = the main S3 camera pose from the brief: world (14422,159250,120)
# minus root (11421.97,160000,-120) = local (3000.03,-750,240), yaw 75.5, pitch -5.5, hFOV 37.5 deg
# (= 35 mm on the assumed 23.76 mm filmback; this is S3 Shot B04's pose in the 1 Oct record).
CLOSE_SHOTS = [
    ("wall_main_B04", (3000.03, -750.0, 240.0), (0, -5.5, 75.5), 35.0),
    ("corner_back_right", (5450.0, 150.0, 290.0), (0, -8.0, 57.0), 24.0),
    ("wall_left_close", (2400.0, 300.0, 260.0), (0, -9.0, -100.0), 24.0),
]


SUN_SIDE = {"corner_back_right": -60.0}   # light from behind-right of the corner camera so the back drifts face it


STONES_JSON = os.path.join(HERE, "standing_stones_proposal.json")
STONE_FBX = os.path.join(PROJECT, "DerivedAssets", "HoledStandingStone", "Export", "SM_HoledStandingStone.fbx")


def add_stones(coll):
    """Preview only: the real SM_HoledStandingStone FBX, linked-duplicated at every proposed placement (pivot =
    proposal pivot; yaw and lean applied; UE->Blender: y mirrored, yaw negated -- lean signs are [inf])."""
    if not (os.path.isfile(STONES_JSON) and os.path.isfile(STONE_FBX)):
        return []
    prop = json.load(open(STONES_JSON, encoding="utf-8"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=STONE_FBX)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if len(new) != 1:
        return []
    src = new[0]
    from mathutils import Vector
    bpy.context.view_layer.update()
    pts = [src.matrix_world @ Vector(c) for c in src.bound_box]
    h = max(p.z for p in pts) - min(p.z for p in pts)
    k = 3.30 / h                                         # normalise to the manifest height (330 cm)
    mat = bpy.data.materials.new("P_Stone")
    mat.use_nodes = True
    bs = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (0.33, 0.31, 0.28, 1)
    bs.inputs["Roughness"].default_value = 0.85
    src.data.materials.clear()
    src.data.materials.append(mat)
    placed = []
    for row, rep in zip(prop["placements"], prop["report"]):
        ob = src.copy()
        ob.name = "Stone " + row["label"][-1]
        coll.objects.link(ob)
        x, y = row["xy_root_local"]
        ob.matrix_world = src.matrix_world.copy()
        ob.scale = (src.scale[0] * k, src.scale[1] * k, src.scale[2] * k)
        ob.rotation_euler = (math.radians(row.get("lean_roll_deg", 0.0)) + src.rotation_euler[0],
                             math.radians(-row.get("lean_pitch_deg", 0.0)) + src.rotation_euler[1],
                             math.radians(-row["yaw_deg"]) + src.rotation_euler[2])
        bpy.context.view_layer.update()
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        zmin = min(p.z for p in pts)
        cx = sum(p.x for p in pts) / 8.0
        cy = sum(p.y for p in pts) / 8.0
        want_bottom = (rep["pivot_root_local_z"] - 30.0) / 100.0
        ob.location = ob.location + Vector((x / 100.0 - cx, -y / 100.0 - cy, want_bottom - zmin))
        placed.append(ob.name)
    for c_ in list(src.users_collection):
        c_.objects.unlink(src)
    return placed


def remove_ground():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith(NAME):
            bpy.data.objects.remove(o, do_unlink=True)


def preview_sets(opts):
    fp = F.load_footprint()
    out_dir = os.path.join(PREV, "sets")
    os.makedirs(out_dir, exist_ok=True)
    rows = {}
    coll = None
    for name in opts["sets"]:
        F.PARAMS["height_set"] = name
        grid = F.build_grid(fp)
        failures, report = F.checks(fp, F.PARAMS, grid)
        remove_ground()
        if coll is not None:      # proxies carry the per-set print line: rebuild them
            for o in list(coll.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(coll)
        build_mesh(grid)
        coll = context_proxies(fp)
        setup_render(["CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"])
        bpy.context.scene.cycles.device = "CPU"
        paths = []
        for shot, loc, rpy, lens in CLOSE_SHOTS:
            cam = add_camera("C_%s_%s" % (name, shot), loc, rpy, lens)
            pth = os.path.join(out_dir, "%s_%s.png" % (name, shot))
            render(cam, pth)
            paths.append(pth)
        rows[name] = {"renders": paths, "failures": failures, "walls": report["walls"], "realism": report["realism"]}
        print("S3SHORE_SET_PREVIEW", name, json.dumps(failures), flush=True)
    with open(os.path.join(out_dir, "sets_preview_index.json"), "w", encoding="utf-8") as h:
        json.dump(rows, h, indent=1)
    print("S3SHORE_SETS_PREVIEW_OK", json.dumps(sorted(rows)))


def render_all(fp, coll):
    renders = []
    engine = setup_render(["CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"])
    if engine == "CYCLES":
        bpy.context.scene.cycles.device = "CPU"
    cams = {c["label"]: c for c in fp["cameras"]["rows"]}
    shots = [(n, add_camera("C_" + n, loc, rpy, lens)) for n, loc, rpy, lens in CLOSE_SHOTS]
    shots += [
        ("overview_from_mouth", add_camera("OV_Mouth", (-900, 0, 900), (0, -22, 0), 18)),
        ("overview_high_three_quarter", add_camera("OV_TQ", (-600, -1700, 2200), (0, -38, 38), 16)),
        ("back_wall_drifts_door", add_camera("OV_Back", (3900, 0, 330), (0, -9, 0), 20)),
        ("mud_front_low", add_camera("OV_Mud", (200, 600, 190), (0, -10, -25), 24)),
    ]
    shots.append(("cam_EntryHandoff", add_camera("Entry Handoff", (-500.0, 0.0, 300.0), (0, 0, 0), 50.0)))
    for lab in ("S3 Shot B02", "S3 Shot B09"):
        c = cams[lab]
        shots.append(("cam_" + lab.split()[-1], add_camera(lab, c["local"], c["rpy"], c["lens_mm"])))
    for name, cam in shots:
        p = os.path.join(PREV, name + ".png")
        render(cam, p)
        renders.append(p)
    # top-down vertex-colour plan (Workbench, colour attribute)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "VERTEX"
    coll.hide_render = True
    top = bpy.data.cameras.new("Top")
    top.type = "ORTHO"
    top.ortho_scale = 62.0
    tob = bpy.data.objects.new("Top", top)
    sc.collection.objects.link(tob)
    tob.location = (30.06, 0.0, 30.0)
    tob.rotation_euler = (0.0, 0.0, 0.0)
    sc.render.resolution_x, sc.render.resolution_y = 2400, 820
    p = os.path.join(PREV, "plan_vertex_colour_RGB.png")
    render(tob, p)
    renders.append(p)
    coll.hide_render = False
    return renders, engine


def main():
    opts = argv_opts()
    SAMPLES[0] = opts["samples"]
    os.makedirs(PREV, exist_ok=True)
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if opts["sets"]:
        preview_sets(opts)
        return
    if opts["overview"]:
        # Stills are a separate run from the (hash-seeded) export build, so a render problem can never touch the
        # FBX.  Same field, same mesh code; nothing is exported.  Engine: Cycles is not offered under
        # --factory-startup here, so setup_render falls back to EEVEE Next [measured 7 Oct].
        fp = F.load_footprint()
        grid = F.build_grid(fp)
        failures, _rep = F.checks(fp, F.PARAMS, grid)
        build_mesh(grid)
        coll = context_proxies(fp)
        stones = add_stones(coll)
        renders, engine = render_all(fp, coll)
        with open(os.path.join(PREV, "overview_index.json"), "w", encoding="utf-8") as h:
            json.dump({"height_set": F.PARAMS["height_set"], "grid_sha256": F.grid_sha256(grid), "engine": engine,
                       "failures": failures, "renders": renders, "stones_placed": stones}, h, indent=1)
        print("S3SHORE_OVERVIEW_OK", F.PARAMS["height_set"], engine, F.grid_sha256(grid))
        return
    if sys.flags.hash_randomization:
        raise SystemExit("S3SHORE_REFUSED hash randomisation is on: run with PYTHONHASHSEED=0 and "
                         "--python-use-system-env so the FBX is byte-identical between builds")
    pin_fbx_clock()
    fp = F.load_footprint()
    grid = F.build_grid(fp)
    failures, report = F.checks(fp, F.PARAMS, grid)
    if failures:
        raise SystemExit("S3SHORE_FIELD_CHECKS_FAILED " + json.dumps(failures))
    height_sets = F.write_height_sets(fp)
    np.save(os.path.join(OUT, NAME + "_grid_h.npy"), np.ascontiguousarray(grid["h"], dtype=np.float64))
    ob, corners, nquads = build_mesh(grid)
    import s3_shore_seat_report as SR
    seat = SR.build(grid=grid)
    seat_summary = {"path": SR.OUT, "counts": seat["counts"], "live_reads_run": seat["live_reads_run"]}
    me = ob.data
    co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    ue = np.stack([co[:, 0] * 100, -co[:, 1] * 100, co[:, 2] * 100], 1)
    bounds = {"min": [round(float(v), 2) for v in ue.min(0)], "max": [round(float(v), 2) for v in ue.max(0)]}

    # export
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    fbx = os.path.join(OUT, NAME + ".fbx")
    kwargs = dict(filepath=fbx, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
                  mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                  apply_scale_options="FBX_SCALE_NONE", axis_forward="-Z", axis_up="Y",
                  use_tspace=False, embed_textures=False, path_mode="AUTO")
    props = bpy.ops.export_scene.fbx.get_rna_type().properties
    if "colors_type" in props.keys():
        kwargs["colors_type"] = "LINEAR"
    bpy.ops.export_scene.fbx(**kwargs)
    sha = hashlib.sha256(open(fbx, "rb").read()).hexdigest()
    # determinism log: every build appends (field sha, fbx sha); the harness compares the last two
    det_path = os.path.join(OUT, NAME + "_determinism_log.json")
    try:
        det = json.load(open(det_path, encoding="utf-8"))
    except (OSError, ValueError):
        det = []
    det.append({"built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "height_set": F.PARAMS["height_set"],
                "params_sha256": hashlib.sha256(json.dumps(F.PARAMS, sort_keys=True).encode()).hexdigest(),
                "grid_sha256": F.grid_sha256(grid), "fbx_sha256": sha, "render": opts["render"]})
    with open(det_path, "w", encoding="utf-8") as h:
        json.dump(det[-10:], h, indent=1)

    # context + previews (not exported)
    coll = context_proxies(fp)
    blend = os.path.join(OUT, NAME + ".blend")
    renders = []
    engine = None
    if opts["render"]:
        renders, engine = render_all(fp, coll)
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)

    manifest = {
        "schema": "s3_shore_ground_manifest/2",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "blender": bpy.app.version_string, "blender_numpy": np.__version__,
        "python_hash_randomization": sys.flags.hash_randomization,
        "fbx": fbx, "fbx_sha256": sha, "fbx_bytes": os.path.getsize(fbx),
        "fbx_determinism": "PYTHONHASHSEED=0 (FBX UUIDs come from str hash) + FBX header clock pinned to 2026-10-07",
        "frame": "S3 Hangar Root LOCAL cm; attach at RELATIVE IDENTITY",
        "height_set": F.PARAMS["height_set"], "height_set_summary": height_sets["sets"][F.PARAMS["height_set"]],
        "height_sets_json": F.HEIGHT_SETS_JSON,
        "params": F.PARAMS, "grid_sha256": F.grid_sha256(grid), "slope_clamp": grid["slope_clamp"],
        "footprint_sha256": hashlib.sha256(open(F.FOOTPRINT, "rb").read()).hexdigest(),
        "vertex_count": len(me.vertices), "face_count_quads": len(me.polygons),
        "triangles_expected": 2 * len(me.polygons), "surface_quads": nquads,
        "expected_ue_local_bounds_cm": bounds,
        "mirror_gate": "UE bounds.min.y must be -1012 and max.y +1008 (+-0.5); swapped => Y mirrored on import",
        "calibration_vertices": corners,
        "vertex_colour_export": "LINEAR float -> FBX; UE byte value for 0.5 tells whether Interchange sRGB-encodes (expect 128 linear, 188 if sRGB)",
        "uv": {"UV0": "u = x_ue/100, v = y_ue/100 (metres)", "UV1": "normalised over the mesh extent"},
        "material_slot": SLOT,
        "checks_failures": failures, "checks": report,
        "renders": renders, "render_engine": engine,
        "seat_report": seat_summary,
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, NAME + "_manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    print("S3SHORE_BUILD_OK", json.dumps({"verts": len(me.vertices), "polys": len(me.polygons),
                                         "bounds": bounds, "fbx_bytes": manifest["fbx_bytes"],
                                         "sha256": sha, "grid_sha256": manifest["grid_sha256"], "engine": engine}))


main()
