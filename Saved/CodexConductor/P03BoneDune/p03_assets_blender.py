"""Generate six Rodin bones, process them, and build the P03 dune in headless Blender.

Run only after confirming no other blender.exe process exists:
  blender -b --python p03_assets_blender.py -- --mode DRY
  blender -b --python p03_assets_blender.py -- --mode APPLY --confirm "APPLY P03 ASSETS"
  blender -b --python p03_assets_blender.py -- --mode REVERT --confirm "REVERT P03 ASSETS"

APPLY reads the Hyper3D key only from blender_mcp_addon preferences. The key is never
printed, logged, serialized, or placed in an environment variable. Generation POSTs are
single-attempt. Status POSTs are deliberate polling calls, not automatic request retries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import mimetypes
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p03_bone_dune_contract as C  # noqa: E402

PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BONES_ROOT = os.path.join(PROJECT, "DerivedAssets", "P03Bones")
DUNE_ROOT = os.path.join(PROJECT, "DerivedAssets", "P03Dune")
RECORD = os.path.join(HERE, "p03_assets_record.json")
BASE_URL = "https://api.hyper3d.com/api/v2"
MAX_TRIS = 150000
CONFIRMS = {"APPLY": "APPLY P03 ASSETS", "REVERT": "REVERT P03 ASSETS"}


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as dst:
        json.dump(value, dst, indent=1)
        dst.flush()
        os.fsync(dst.fileno())
    os.replace(tmp, path)


def safe_rel(path):
    return os.path.relpath(path, PROJECT).replace("\\", "/")


def backup_outputs(run, suffix):
    root = os.path.join(PROJECT, "Backups", "PreP03BoneDuneAssets-%s-%s" % (run, suffix))
    if os.path.exists(root):
        raise RuntimeError("BACKUP_EXISTS|" + root)
    os.makedirs(root)
    rows = []
    for source in (BONES_ROOT, DUNE_ROOT):
        rel = safe_rel(source)
        row = {"path": rel, "existed": os.path.isdir(source)}
        if row["existed"]:
            target = os.path.join(root, rel)
            shutil.copytree(source, target)
            row["files"] = sum(len(files) for _r, _d, files in os.walk(target))
        rows.append(row)
    write_json(os.path.join(root, "backup_manifest.json"), rows)
    return root, rows


def multipart(fields):
    boundary = "----PussStageP03" + uuid.uuid4().hex
    chunks = []
    for key, value in fields:
        chunks.extend([
            ("--" + boundary + "\r\n").encode(),
            ('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode(),
            str(value).encode("utf-8"), b"\r\n",
        ])
    chunks.append(("--" + boundary + "--\r\n").encode())
    return b"".join(chunks), "multipart/form-data; boundary=" + boundary


def api_json(key, endpoint, body, content_type="application/json", timeout=90):
    req = urllib.request.Request(BASE_URL + endpoint, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": content_type,
                                          "User-Agent": "PussStage-P03BoneDune/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"error": "HTTP_%d" % error.code, "message": raw[:500]}
        return error.code, payload


def get_key():
    addon = bpy.context.preferences.addons.get("blender_mcp_addon")
    if addon is None:
        # A headless process may load saved preferences with the add-on disabled.
        # Enable only in this process; never save or mutate user preferences.
        user_addons = os.path.join(bpy.utils.user_resource("SCRIPTS"), "addons")
        if user_addons not in sys.path:
            sys.path.insert(0, user_addons)
        try:
            bpy.ops.preferences.addon_enable(module="blender_mcp_addon")
        except Exception as error:
            raise RuntimeError("RODIN_PREFS_ADDON_UNAVAILABLE|%s" % type(error).__name__) from error
        addon = bpy.context.preferences.addons.get("blender_mcp_addon")
    if addon is None:
        raise RuntimeError("RODIN_PREFS_ADDON_NOT_ENABLED")
    key = str(getattr(addon.preferences, "hyper3d_api_key", "") or "").strip()
    if not key:
        raise RuntimeError("RODIN_PREFS_KEY_EMPTY")
    return key


def generation_form(spec):
    return [
        ("prompt", spec["prompt"]),
        ("tier", "Gen-2.5-High"),
        ("texture_mode", "high"),
        ("material", "PBR"),
        ("mesh_mode", "Raw"),
        ("geometry_file_format", "glb"),
        ("geometry_instruct_mode", "faithful"),
        ("texture_delight", "true"),
        ("preview_render", "true"),
        ("quality_override", "180000"),
        ("seed", str(spec["seed"])),
        ("bbox_condition", json.dumps(spec["bbox_cm"], separators=(",", ":"))),
        ("is_symmetric", spec["symmetry"]),
        ("addons", "HighPack"),
    ]


def sanitize_generation(payload, status):
    jobs = payload.get("jobs") or {}
    return {
        "http": status,
        "uuid": payload.get("uuid"),
        "job_uuids": jobs.get("uuids", []),
        "consumed": payload.get("consumed"),
        "prompt": payload.get("prompt"),
        "submit_time": payload.get("submit_time"),
        "error": payload.get("error"),
        "message": payload.get("message"),
        "subscription_key_serialized": False,
    }


def download_url(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "PussStage-P03BoneDune/1"})
    with urllib.request.urlopen(req, timeout=180) as response, open(path, "wb") as dst:
        shutil.copyfileobj(response, dst, length=1024 * 1024)


def generate_one(key, spec, record):
    name = spec["name"]
    root = os.path.join(BONES_ROOT, name)
    rodin = os.path.join(root, "Rodin")
    req_dir = os.path.join(root, "RodinInput")
    os.makedirs(rodin, exist_ok=True)
    os.makedirs(req_dir, exist_ok=True)
    form = generation_form(spec)
    request_record = {"asset": name, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "endpoint": BASE_URL + "/rodin", "form_as_sent": form,
                      "expected_cost_credits": 0.5,
                      "credential_source": 'bpy.context.preferences.addons["blender_mcp_addon"].preferences.hyper3d_api_key',
                      "credential_serialized": False}
    write_json(os.path.join(req_dir, "rodin_request.json"), request_record)
    body, content_type = multipart(form)
    status, payload = api_json(key, "/rodin", body, content_type, timeout=120)  # one attempt; never retry
    clean = sanitize_generation(payload, status)
    write_json(os.path.join(rodin, "submit_response.json"), clean)
    record["bones"][name] = {"submission": clean, "status": "submitted" if clean.get("uuid") else "rejected"}
    write_json(RECORD, record)
    if status != 201 or payload.get("error") or not payload.get("uuid"):
        raise RuntimeError("RODIN_SUBMIT_REJECTED|%s|http=%s|error=%s" % (name, status, payload.get("error")))
    subscription = (payload.get("jobs") or {}).get("subscription_key")
    if not subscription:
        raise RuntimeError("RODIN_SUBSCRIPTION_MISSING|" + name)
    started = time.monotonic()
    delay = 8
    while True:
        if time.monotonic() - started > 30 * 60:
            raise RuntimeError("RODIN_TIMEOUT|" + name)
        time.sleep(delay)
        sb, st = json.dumps({"subscription_key": subscription}).encode(), "application/json"
        scode, state = api_json(key, "/status", sb, st, timeout=60)
        if scode != 200:
            raise RuntimeError("RODIN_STATUS_HTTP|%s|%s" % (name, scode))
        states = [row.get("status") for row in state.get("jobs", [])]
        if "Failed" in states:
            raise RuntimeError("RODIN_JOB_FAILED|%s|%s" % (name, states))
        if states and all(value == "Done" for value in states):
            break
        delay = min(delay + 4, 30)
    dcode, downloads = api_json(key, "/download", json.dumps({"task_uuid": payload["uuid"]}).encode(),
                                "application/json", timeout=60)
    if dcode != 201 or downloads.get("error"):
        raise RuntimeError("RODIN_DOWNLOAD_LIST|%s|http=%s|error=%s" % (name, dcode, downloads.get("error")))
    kept = []
    for item in downloads.get("list", []):
        remote_name = os.path.basename(item.get("name") or "")
        if remote_name not in ("base_high_pbr.glb", "preview.webp", "render.jpg"):
            continue
        target = os.path.join(rodin, remote_name)
        download_url(item["url"], target)
        kept.append({"name": remote_name, "bytes": os.path.getsize(target), "sha256": sha256(target)})
    glb = os.path.join(rodin, "base_high_pbr.glb")
    if not os.path.isfile(glb):
        raise RuntimeError("RODIN_GLB_MISSING|" + name)
    record["bones"][name].update({"status": "downloaded", "files": kept})
    write_json(RECORD, record)
    print("P03_RODIN_DOWNLOADED|asset=%s|task=%s|credits=%s" % (name, payload["uuid"], payload.get("consumed")))
    return glb


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def upstream_image(socket):
    seen = set()
    stack = [socket]
    while stack:
        item = stack.pop()
        for link in getattr(item, "links", []):
            node = link.from_node
            if id(node) in seen:
                continue
            seen.add(id(node))
            if node.type == "TEX_IMAGE" and node.image:
                return node.image, getattr(link.from_socket, "name", "")
            stack.extend(inp for inp in node.inputs if inp.is_linked)
    return None, ""


def save_pixels(path, source, role, channel=None):
    width, height = source.size
    if max(width, height) > 4096:
        scale = 4096.0 / max(width, height)
        source = source.copy()
        source.scale(max(1, round(width * scale)), max(1, round(height * scale)))
        width, height = source.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    if role == "N":
        pixels[:, :, 1] = 1.0 - pixels[:, :, 1]  # OpenGL -> DirectX
    elif role == "Roughness":
        index = {"Red": 0, "Green": 1, "Blue": 2, "Alpha": 3}.get(channel, 1)
        grey = pixels[:, :, index].copy()
        pixels[:, :, 0] = grey
        pixels[:, :, 1] = grey
        pixels[:, :, 2] = grey
        pixels[:, :, 3] = 1.0
    out = bpy.data.images.new("P03_%s_OUT" % role, width=width, height=height, alpha=True, float_buffer=False)
    out.colorspace_settings.name = "sRGB" if role == "BaseColor" else "Non-Color"
    out.pixels.foreach_set(pixels.ravel())
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    return [width, height]


def mesh_tris(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = obj.evaluated_get(deps).to_mesh()
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    obj.evaluated_get(deps).to_mesh_clear()
    return count


def validate_fbx_clean(path, expected_name):
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=path, use_anim=False, automatic_bone_orientation=False)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError("FBX_REIMPORT_OBJECTS|%s|%d" % (expected_name, len(meshes)))
    obj = meshes[0]
    tris = mesh_tris(obj)
    if tris > MAX_TRIS:
        raise RuntimeError("FBX_REIMPORT_TRIS|%s|%d" % (expected_name, tris))
    if len(obj.data.uv_layers) != 1 or obj.data.uv_layers[0].name != "UVMap":
        raise RuntimeError("FBX_REIMPORT_UV|%s|%s" % (expected_name, [x.name for x in obj.data.uv_layers]))
    if len(obj.data.materials) != 1:
        raise RuntimeError("FBX_REIMPORT_SLOTS|%s|%d" % (expected_name, len(obj.data.materials)))
    corners = [obj.matrix_world @ obj.bound_box[i] for i in range(8)]
    lo = np.min([[v.x, v.y, v.z] for v in corners], axis=0)
    hi = np.max([[v.x, v.y, v.z] for v in corners], axis=0)
    return {"objects": 1, "tris": tris, "size_cm": [round(float(v) * 100.0, 2) for v in (hi - lo)],
            "min_z_cm": round(float(lo[2]) * 100.0, 4), "uv": [x.name for x in obj.data.uv_layers],
            "slots": 1, "identity": all(abs(v) < 1e-5 for v in tuple(obj.location) + tuple(obj.rotation_euler))}


def process_bone(spec, glb):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=glb)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("GLB_NO_MESH|" + spec["name"])
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = "SM_" + spec["name"]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    dims = np.array(obj.dimensions[:], dtype=float)
    scale = (spec["target_longest_cm"] / 100.0) / float(dims.max())
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    before = mesh_tris(obj)
    if before > MAX_TRIS:
        mod = obj.modifiers.new("P03 <=150k", "DECIMATE")
        mod.ratio = min(1.0, 145000.0 / before)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    after = mesh_tris(obj)
    if after > MAX_TRIS:
        raise RuntimeError("DECIMATE_LIMIT|%s|%d" % (spec["name"], after))
    # Base-centre pivot, min Z = 0, identity transform.
    corners = [obj.matrix_world @ obj.bound_box[i] for i in range(8)]
    lo = np.min([[v.x, v.y, v.z] for v in corners], axis=0)
    hi = np.max([[v.x, v.y, v.z] for v in corners], axis=0)
    obj.location -= ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, lo[2])
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    materials = [m for m in obj.data.materials if m]
    if len(materials) != 1:
        raise RuntimeError("MATERIAL_SLOT_COUNT|%s|%d" % (spec["name"], len(materials)))
    mat = materials[0]
    mat.name = "MI_" + spec["name"]
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        raise RuntimeError("PBR_BSDF_MISSING|" + spec["name"])
    base_img, _ = upstream_image(bsdf.inputs["Base Color"])
    norm_img, _ = upstream_image(bsdf.inputs["Normal"])
    rough_img, rough_channel = upstream_image(bsdf.inputs["Roughness"])
    if not all((base_img, norm_img, rough_img)):
        raise RuntimeError("PBR_TEXTURE_LINKS|" + spec["name"])
    out = os.path.join(BONES_ROOT, spec["name"], "Export")
    os.makedirs(out, exist_ok=True)
    tex = {}
    tex["T_%s_BaseColor.png" % spec["name"]] = save_pixels(os.path.join(out, "T_%s_BaseColor.png" % spec["name"]), base_img, "BaseColor")
    tex["T_%s_N.png" % spec["name"]] = save_pixels(os.path.join(out, "T_%s_N.png" % spec["name"]), norm_img, "N")
    tex["T_%s_Roughness.png" % spec["name"]] = save_pixels(os.path.join(out, "T_%s_Roughness.png" % spec["name"]), rough_img, "Roughness", rough_channel)
    for item in bpy.context.scene.objects:
        item.select_set(item == obj)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(out, "SM_%s.fbx" % spec["name"])
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             use_tspace=True, embed_textures=False, path_mode="AUTO")
    size_cm = [round(float(v) * 100.0, 2) for v in obj.dimensions]
    clean = validate_fbx_clean(fbx, spec["name"])
    manifest = {
        "asset": "SM_" + spec["name"], "date": "2026-10-08",
        "source": {"generator": "Hyper3D Rodin Gen-2.5-High + HighPack (4K)",
                   "task_uuid": None, "request": "../RodinInput/rodin_request.json", "credits": None},
        "processing": {"input_tris": before, "output_tris": after, "max_tris": MAX_TRIS,
                       "uniform_scale": scale, "pivot": "base centre (min z 0)",
                       "normal": "OpenGL -> DirectX (green inverted)"},
        "export": {"fbx": os.path.basename(fbx), "fbx_sha256": sha256(fbx), "textures": tex,
                   "fbx_options": "FBX_SCALE_UNITS, -Z fwd / Y up, triangles, no embedded textures"},
        "ue_destination": {
            "root": "/Game/InfinityStage/Dev/Generated/P03Bones/%s" % spec["name"],
            "mesh": "/Game/InfinityStage/Dev/Generated/P03Bones/%s/SM_%s" % (spec["name"], spec["name"]),
            "texture_roles": ["BaseColor", "N", "Roughness"],
            "import_pattern": "S3 props IMPORT_MESH, then one IMPORT_TEX + VERIFY_TEX per role, then BUILD_MAT",
        },
        "validation_blender_export": {"objects": 1, "tris": after, "size_cm": size_cm,
                                      "uv": ["UVMap"], "slots": 1, "identity": True},
        "validation_blender_clean_reimport": clean,
        "not_verified": ["Unreal import", "rendered in P03"],
    }
    write_json(os.path.join(out, "SM_%s_manifest.json" % spec["name"]), manifest)
    return manifest


def build_dune_mesh(args):
    d = args["dune"]
    xs = np.linspace(-d["length_cm"] * 0.5, d["length_cm"] * 0.5, int(d["grid_x"]))
    ys = np.linspace(-d["width_cm"] * 0.5, d["width_cm"] * 0.5, int(d["grid_y"]))
    h = np.array([[C.dune_height_cm(x, y, d, args["seed"]) for y in ys] for x in xs])
    verts = [(x / 100.0, -y / 100.0, h[ix, iy] / 100.0)
             for ix, x in enumerate(xs) for iy, y in enumerate(ys)]
    ny = len(ys)
    faces = []
    for ix in range(len(xs) - 1):
        for iy in range(ny - 1):
            a = ix * ny + iy
            faces.append((a, a + ny, a + ny + 1, a + 1))
    mesh = bpy.data.meshes.new("SM_P03_BoneDune")
    mesh.from_pydata(verts, [], faces)
    mesh.update(calc_edges=True)
    uv = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, -co.y)
        poly.use_smooth = True
    obj = bpy.data.objects.new("SM_P03_BoneDune", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("MI_S3_ShoreGround_v2")
    mat.diffuse_color = (0.48, 0.30, 0.12, 1)
    mat.roughness = 0.92
    mesh.materials.append(mat)
    return obj, xs, ys, h


def setup_preview():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world = bpy.data.worlds.new("P03World")
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.035, 0.025, 0.018, 1)
    bg.inputs[1].default_value = 0.22
    sun = bpy.data.lights.new("RakingSun", "SUN")
    sun.energy = 4.0
    sun.angle = math.radians(2.0)
    so = bpy.data.objects.new("RakingSun", sun)
    scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), 0, math.radians(-38))


def add_camera(name, location, target, ortho=None):
    from mathutils import Vector
    cam = bpy.data.cameras.new(name)
    if ortho:
        cam.type, cam.ortho_scale = "ORTHO", ortho
    else:
        cam.lens = 48
    obj = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def render_dune_previews(args, obj):
    setup_preview()
    preview = os.path.join(DUNE_ROOT, "previews")
    os.makedirs(preview, exist_ok=True)
    scene = bpy.context.scene
    cameras = [
        ("P03_BoneDune_top.png", add_camera("Top", (0, 0, 12), (0, 0, 0), ortho=10.5)),
        ("P03_BoneDune_three_quarter.png", add_camera("ThreeQuarter", (-7.8, -8.2, 5.4), (0.4, 0, 1.15))),
    ]
    for filename, camera in cameras:
        scene.camera = camera
        scene.render.filepath = os.path.join(preview, filename)
        bpy.ops.render.render(write_still=True)
    return [safe_rel(os.path.join(preview, name)) for name, _cam in cameras]


def build_dune(args):
    clear_scene()
    os.makedirs(DUNE_ROOT, exist_ok=True)
    obj, xs, ys, h = build_dune_mesh(args)
    placements = C.bone_placements(args)
    # The exported dune remains one clean mesh, while previews use the actual processed
    # bone FBXs. The six bones remain separate Show attachments in the placement plan.
    bone_preview_mat = bpy.data.materials.new("P03PreviewBone")
    bone_preview_mat.diffuse_color = (0.62, 0.52, 0.36, 1)
    bone_preview_mat.roughness = 0.88
    for row, spec in zip(placements, C.BONE_SPECS):
        loc = row["dune_local_transform"]["location_cm"]
        source = os.path.join(BONES_ROOT, spec["name"], "Export", "SM_%s.fbx" % spec["name"])
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=source, use_anim=False, automatic_bone_orientation=False)
        imported = [item for item in bpy.context.scene.objects if item not in before and item.type == "MESH"]
        if len(imported) != 1:
            raise RuntimeError("PREVIEW_BONE_IMPORT|%s|%d" % (spec["name"], len(imported)))
        proxy = imported[0]
        proxy.name = "Preview_" + row["bone"]
        proxy.location = (loc[0] / 100.0, -loc[1] / 100.0, loc[2] / 100.0)
        r, p, y = row["dune_local_transform"]["rotation_rpy_deg"]
        proxy.rotation_euler = tuple(math.radians(v) for v in (r, p, -y))
        proxy.data.materials.clear()
        proxy.data.materials.append(bone_preview_mat)
    for other in bpy.context.scene.objects:
        other.select_set(other == obj)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(DUNE_ROOT, "SM_P03_BoneDune.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             embed_textures=False, path_mode="AUTO")
    previews = render_dune_previews(args, obj)
    placement_path = os.path.join(DUNE_ROOT, "P03_BoneDune_placements.json")
    placement = {"schema": "p03_bone_dune_placements/1", "seed": args["seed"],
                 "target": C.TARGET_CUE, "dune": args["dune"], "bones": placements,
                 "proposal": C.placement_plan(args)}
    write_json(placement_path, placement)
    vertex_count = len(obj.data.vertices)
    polygon_count = len(obj.data.polygons)
    uv_names = [uv.name for uv in obj.data.uv_layers]
    clean = validate_fbx_clean(fbx, "P03_BoneDune")
    manifest = {"schema": "p03_bone_dune_manifest/1", "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "seed": args["seed"], "fbx": os.path.basename(fbx), "fbx_sha256": sha256(fbx),
                "vertex_count": vertex_count, "polygon_count": polygon_count,
                "triangles_expected": polygon_count * 2,
                "bounds_cm": {"x": [round(float(xs.min()), 3), round(float(xs.max()), 3)],
                              "y": [round(float(ys.min()), 3), round(float(ys.max()), 3)],
                              "z": [round(float(h.min()), 3), round(float(h.max()), 3)]},
                 "uv": uv_names, "material_slot": "MI_S3_ShoreGround_v2",
                 "validation_blender_clean_reimport": clean,
                 "ue_destination": {"mesh": "/Game/InfinityStage/Dev/Generated/P03Dune/SM_P03_BoneDune",
                                    "material": "/Game/InfinityStage/Dev/Generated/S3Shore/MI_S3_ShoreGround_v2"},
                 "placements": safe_rel(placement_path), "previews": previews,
                 "look_status": "offline Blender preview with processed bone meshes; Gary approval required; nothing applied to Unreal"}
    write_json(os.path.join(DUNE_ROOT, "SM_P03_BoneDune_manifest.json"), manifest)
    return manifest


def apply(run):
    args = C.check_args({"mode": "DRY"})
    if os.path.isfile(RECORD):
        prior = json.load(open(RECORD, encoding="utf-8"))
        if prior.get("status") != "reverted":
            raise RuntimeError("RECORD_EXISTS|status=%s|run=%s" % (prior.get("status"), prior.get("run")))
    backup, pre = backup_outputs(run, "APPLY")
    record = {"schema": "p03_assets_record/1", "run": run, "status": "prepared", "backup": backup,
              "pre": pre, "bones": {}, "credits_used": 0.0, "credential_serialized": False}
    write_json(RECORD, record)
    key = get_key()
    try:
        for spec in C.BONE_SPECS:
            glb = generate_one(key, spec, record)
            manifest = process_bone(spec, glb)
            submission = record["bones"][spec["name"]]["submission"]
            manifest["source"]["task_uuid"] = submission["uuid"]
            manifest["source"]["credits"] = submission["consumed"]
            write_json(os.path.join(BONES_ROOT, spec["name"], "Export", "SM_%s_manifest.json" % spec["name"]), manifest)
            record["bones"][spec["name"]].update({"status": "processed", "manifest": manifest})
            record["credits_used"] += float(submission.get("consumed") or 0.0)
            write_json(RECORD, record)
        record["dune"] = build_dune(args)
        record["status"] = "applied"
        write_json(RECORD, record)
        print("P03_ASSETS_APPLY_OK|run=%s|bones=%d|credits=%.3f" % (run, len(C.BONE_SPECS), record["credits_used"]))
    except Exception as error:
        record.update({"status": "failed", "error": str(error)})
        write_json(RECORD, record)
        print("P03_ASSETS_APPLY_FAILED|run=%s|credits=%.3f|error=%s" %
              (run, record["credits_used"], str(error)))
        raise
    finally:
        key = None


def revert(run):
    if not os.path.isfile(RECORD):
        raise RuntimeError("RECORD_MISSING")
    rec = json.load(open(RECORD, encoding="utf-8"))
    if rec.get("status") not in ("prepared", "failed", "applied"):
        raise RuntimeError("RECORD_STATUS|%s" % rec.get("status"))
    current, _rows = backup_outputs(run, "REVERT")
    for target in (BONES_ROOT, DUNE_ROOT):
        if os.path.isdir(target):
            moved = os.path.join(current, "replaced", safe_rel(target))
            os.makedirs(os.path.dirname(moved), exist_ok=True)
            shutil.move(target, moved)
    for row in rec["pre"]:
        if row["existed"]:
            source = os.path.join(rec["backup"], row["path"])
            target = os.path.join(PROJECT, row["path"])
            shutil.copytree(source, target)
    rec["reverted_from_status"] = rec["status"]
    rec["status"] = "reverted"
    rec["revert_backup"] = current
    write_json(RECORD, rec)
    print("P03_ASSETS_REVERT_OK|run=%s|backup=%s|credits_not_reversible=%.3f" %
          (run, current.replace("\\", "/"), rec.get("credits_used", 0.0)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), default="DRY")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--run", default="P03ASSETS-" + stamp())
    ns = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if ns.mode in CONFIRMS and ns.confirm != CONFIRMS[ns.mode]:
        raise RuntimeError("CONFIRM_MISSING|%s needs %r" % (ns.mode, CONFIRMS[ns.mode]))
    if ns.mode == "DRY":
        args = C.check_args({"mode": "DRY"})
        dry = {"run": ns.run, "mode": "DRY", "ok": True,
               "bones": [{"name": s["name"], "bbox_cm": s["bbox_cm"], "seed": s["seed"]}
                         for s in C.BONE_SPECS], "expected_max_credits": 3.0,
               "dune": args["dune"], "proposal": C.placement_plan(args),
               "blender": bpy.app.version_string}
        write_json(os.path.join(HERE, "p03_assets_dry_%s.json" % ns.run), dry)
        print(json.dumps(dry, indent=1))
        print("P03_ASSETS_DRY_OK|run=%s|bones=6|max_credits=3.0" % ns.run)
    elif ns.mode == "APPLY":
        apply(ns.run)
    else:
        revert(ns.run)


main()
