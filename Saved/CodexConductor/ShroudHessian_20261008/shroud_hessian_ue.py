"""P22 create-only shroud hessian tool.  Written and tested OFFLINE; NOT RUN IN UNREAL.

Run order (one guarded project-Python call per line):

  DRY
  IMPORT_TEX <one texture key> -> PENDING (no save; same-call values are not trusted)
  MAT_CHECK                   -> later read-back, targeted save, read-back again, *_IMPORT_TEX_OK
  ...repeat for all 14 textures...
  BUILD_MAT                   -> PENDING (create-only master + six MIs; no save)
  MAT_CHECK                   -> later graph/MI read-back, targeted save, read-back again, *_BUILD_MAT_OK
  DRY                         -> review seeded assignments and exact package scope
  APPLY / REVERT              -> Gary's look approval and conductor editor slot only

IMPORT_TEX and BUILD_MAT deliberately do not emit OK.  Their PENDING markers mean
only that the later MAT_CHECK is now required.  The master is create-only: this
file never deletes or rewrites nodes on an existing material.

APPLY changes only ShoreHeadCloth material slot 0 on each figure's distinct BP
template and placed level instance.  It fingerprints the asset, transform,
attachment, simulation/teleport fields and parent Body relationship before and
after.  The existing Chaos cloth asset, live simulation, collision source setup,
component transforms and follower/figure components are outside the write set.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import shutil
import struct
import sys


HERE = os.path.dirname(os.path.abspath(__file__)) + os.sep
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", "..")) + os.sep
ARGS = os.environ.get("SHROUD_HESSIAN_ARGS", HERE + "shroud_hessian_args.json")
TEXTURE_PENDING = HERE + "shroud_hessian_texture_pending.json"
MATERIAL_PENDING = HERE + "shroud_hessian_material_pending.json"
APPLY_RECORD = HERE + "shroud_hessian_apply_record.json"
ASSET_ROOT = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian"
TEX_DIR = ASSET_ROOT + "/Textures"
MAT_DIR = ASSET_ROOT + "/Materials"
MASTER = MAT_DIR + "/M_Shroud_Hessian"
MATERIAL_INSTANCES = {n: MAT_DIR + "/MI_Shroud_Hessian_%02d" % n for n in range(3, 9)}
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
FIGURES = ("Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25")
FIGURE_LABELS = {f: f + " Clam" for f in FIGURES}
BP_ROOT = "/Game/Metahuman/ShoreCast_20260910/SceneCharacters"
BP_PATHS = {f: BP_ROOT + "/BP_%s_Draped" % f for f in FIGURES}
CLOTH_COMPONENT = "ShoreHeadCloth"
WRITE_MODES = ("IMPORT_TEX", "BUILD_MAT", "APPLY", "REVERT")
MODES = ("DRY", "IMPORT_TEX", "BUILD_MAT", "MAT_CHECK", "APPLY", "REVERT")
CONFIRM = {m: m + " SHROUDHESSIAN" for m in WRITE_MODES}
DEFAULT_SEED = 22081008


class ShroudError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise ShroudError(message)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as f:
        json.dump(value, f, indent=1, sort_keys=True, default=str)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    require(head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR", "PNG_HEADER|" + path)
    return list(struct.unpack(">II", head[16:24]))


def texture_catalog():
    rows = {
        "WeaveBC": ("T_Shroud_Weave_BC.png", "T_Shroud_Weave_BC", "TC_DEFAULT", True, "SAMPLERTYPE_COLOR"),
        "WeaveN": ("T_Shroud_Weave_N.png", "T_Shroud_Weave_N", "TC_NORMALMAP", False, "SAMPLERTYPE_NORMAL"),
    }
    for number in range(3, 9):
        rows["Stain%02dTint" % number] = ("T_Shroud_Stain_%02d_Tint.png" % number,
                                          "T_Shroud_Stain_%02d_Tint" % number,
                                          "TC_DEFAULT", True, "SAMPLERTYPE_COLOR")
        rows["Stain%02dMask" % number] = ("T_Shroud_Stain_%02d_Mask.png" % number,
                                          "T_Shroud_Stain_%02d_Mask" % number,
                                          "TC_MASKS", False, "SAMPLERTYPE_MASKS")
    return rows


def texture_asset(key):
    return TEX_DIR + "/" + texture_catalog()[key][1]


SCALAR_DEFAULTS = {
    "WeaveTiling": 8.0,
    "StainTintStrength": 1.0,
    "NormalStrength": 1.0,
    "RoughnessDry": 0.85,
    "RoughnessWet": 0.45,
    "RoughnessSoot": 0.93,
    "WetMaskStrength": 1.0,
    "SootMaskStrength": 1.0,
    "Specular": 0.35,
    "StainRotate": 0.0,
}
VECTOR_DEFAULTS = {"StainOffset": [0.0, 0.0, 0.0, 0.0], "WeaveTint": [1.0, 1.0, 1.0, 1.0]}
UV_CODE = ("float2 p=UV-0.5; float a=R*6.28318530718; float s=sin(a), c=cos(a); "
           "return float2(c*p.x-s*p.y,s*p.x+c*p.y)+0.5+O.xy;")
BASE_CODE = "return W.rgb * C.rgb * lerp(float3(1,1,1), T.rgb, saturate(S));"
NORMAL_CODE = ("float3 NN=normalize(float3(N.xy * max(S,0.0), max(N.z,0.001))); "
               "return NN * float3(1.0,1.0,TwoSided);")
ROUGH_CODE = ("float wet=saturate(M.r*W); float soot=saturate(M.g*S); "
              "return lerp(lerp(D, WR, wet), SR, soot);")


def material_spec():
    """Pure graph contract used by the offline harness and BUILD_MAT."""
    nodes = {
        "UV0": ("texcoord", 0),
        "WeaveTiling": ("scalar", SCALAR_DEFAULTS["WeaveTiling"]),
        "StainRotate": ("scalar", SCALAR_DEFAULTS["StainRotate"]),
        "StainOffset": ("vector", VECTOR_DEFAULTS["StainOffset"]),
        "WeaveBase": ("texture", "WeaveBC"),
        "WeaveNormal": ("texture", "WeaveN"),
        "StainTint": ("texture", "Stain03Tint"),
        "StainMask": ("texture", "Stain03Mask"),
        "WeaveTint": ("vector", VECTOR_DEFAULTS["WeaveTint"]),
        "TwoSidedSign": ("twosided", None),
    }
    nodes.update({k: ("scalar", v) for k, v in SCALAR_DEFAULTS.items()
                  if k not in ("WeaveTiling", "StainRotate")})
    nodes.update({
        "WeaveUV": ("custom", ("return UV*S;", ["UV", "S"], "F2")),
        "StainUV": ("custom", (UV_CODE, ["UV", "O", "R"], "F2")),
        "BaseOut": ("custom", (BASE_CODE, ["W", "T", "C", "S"], "F3")),
        "NormalOut": ("custom", (NORMAL_CODE, ["N", "S", "TwoSided"], "F3")),
        "RoughOut": ("custom", (ROUGH_CODE, ["M", "D", "WR", "SR", "W", "S"], "F1")),
    })
    edges = [
        ("UV0", "", "WeaveUV", "UV"), ("WeaveTiling", "", "WeaveUV", "S"),
        ("UV0", "", "StainUV", "UV"), ("StainOffset", "", "StainUV", "O"),
        ("StainRotate", "", "StainUV", "R"),
        ("WeaveUV", "", "WeaveBase", "UVs"), ("WeaveUV", "", "WeaveNormal", "UVs"),
        ("StainUV", "", "StainTint", "UVs"), ("StainUV", "", "StainMask", "UVs"),
        ("WeaveBase", "RGB", "BaseOut", "W"), ("StainTint", "RGB", "BaseOut", "T"),
        ("WeaveTint", "", "BaseOut", "C"), ("StainTintStrength", "", "BaseOut", "S"),
        ("WeaveNormal", "RGB", "NormalOut", "N"), ("NormalStrength", "", "NormalOut", "S"),
        ("TwoSidedSign", "", "NormalOut", "TwoSided"),
        ("StainMask", "RGBA", "RoughOut", "M"), ("RoughnessDry", "", "RoughOut", "D"),
        ("RoughnessWet", "", "RoughOut", "WR"), ("RoughnessSoot", "", "RoughOut", "SR"),
        ("WetMaskStrength", "", "RoughOut", "W"), ("SootMaskStrength", "", "RoughOut", "S"),
    ]
    return {"nodes": nodes, "edges": edges,
            "properties": [("BaseOut", "", "MP_BASE_COLOR"), ("NormalOut", "", "MP_NORMAL"),
                           ("RoughOut", "", "MP_ROUGHNESS"), ("Specular", "", "MP_SPECULAR")],
            "texture_parameters": ("WeaveBase", "WeaveNormal", "StainTint", "StainMask"),
            "scalar_parameters": tuple(SCALAR_DEFAULTS), "vector_parameters": tuple(VECTOR_DEFAULTS)}


def validate_material_values(material):
    scalars = dict(SCALAR_DEFAULTS)
    vectors = {k: list(v) for k, v in VECTOR_DEFAULTS.items()}
    for k, v in (material or {}).items():
        if k in scalars:
            scalars[k] = float(v)
        elif k in vectors:
            require(isinstance(v, list) and len(v) == 4, "VECTOR_VALUE|%s|%r" % (k, v))
            vectors[k] = [float(x) for x in v]
        else:
            raise ShroudError("MATERIAL_KEY|" + k)
    for key in ("WeaveTiling", "NormalStrength", "WetMaskStrength", "SootMaskStrength"):
        require(scalars[key] >= 0.0, "SCALAR_NONNEGATIVE|%s|%s" % (key, scalars[key]))
    for key in ("StainTintStrength", "RoughnessDry", "RoughnessWet", "RoughnessSoot", "Specular"):
        require(0.0 <= scalars[key] <= 1.0, "SCALAR_01|%s|%s" % (key, scalars[key]))
    require(scalars["RoughnessWet"] <= scalars["RoughnessDry"] <= scalars["RoughnessSoot"],
            "ROUGHNESS_ORDER|wet<=dry<=soot")
    return scalars, vectors


def parse_args(data, records=None):
    records = records or {"texture": False, "material": False, "apply": False}
    mode = str(data.get("mode", "")).upper()
    require(mode in MODES, "MODE|" + mode)
    run = str(data.get("run") or "").strip()
    require(run and run != "CONDUCTOR_SUPPLIES_RUN_ID", "RUN_ID_REQUIRED")
    if mode in WRITE_MODES:
        require(data.get("confirm") == CONFIRM[mode], "CONFIRM|expected %s" % CONFIRM[mode])
    texture = data.get("texture")
    if mode == "IMPORT_TEX":
        require(texture in texture_catalog(), "TEXTURE_KEY|%r" % texture)
        require(not records["texture"] and not records["material"], "PENDING_EXISTS")
    if mode == "BUILD_MAT":
        require(not records["texture"] and not records["material"], "PENDING_EXISTS")
    if mode == "MAT_CHECK":
        require(records["texture"] ^ records["material"], "MAT_CHECK_REQUIRES_ONE_PENDING")
    if mode == "APPLY":
        require(not records["apply"], "ALREADY_APPLIED")
    if mode == "REVERT":
        require(records["apply"], "NO_APPLY_RECORD")
    figures = list(data.get("figures") or FIGURES)
    require(figures and len(figures) == len(set(figures)) and not [f for f in figures if f not in FIGURES],
            "FIGURES|%r" % figures)
    scalars, vectors = validate_material_values(data.get("material") or {})
    return {"mode": mode, "run": run, "texture": texture, "figures": figures,
            "seed": int(data.get("seed", DEFAULT_SEED)), "scalars": scalars, "vectors": vectors}


def seeded_assignments(figures, seed):
    require(len(figures) <= len(MATERIAL_INSTANCES), "TOO_MANY_FIGURES")
    stains = sorted(MATERIAL_INSTANCES)
    random.Random(int(seed)).shuffle(stains)
    return {f: stains[i] for i, f in enumerate(figures)}


STATE_KEYS = ("class", "asset", "relative_location", "relative_rotation", "relative_scale", "absolute_rotation",
              "attach_socket", "attach_parent", "parent_is_this_body", "teleport_distance_threshold",
              "teleport_rotation_threshold", "use_attached_parent_as_pose_component", "visible", "hidden_in_game",
              "suspend_simulation", "enable_simulation")


def transition_problems(before, after, expected_material):
    """Pure gate: only override_materials may differ, and it must become [expected]."""
    problems = []
    for scope in ("template", "instance"):
        b, a = before[scope], after[scope]
        for key in STATE_KEYS:
            if b.get(key) != a.get(key):
                problems.append("UNTOUCHED_CHANGED|%s|%s|%r->%r" % (scope, key, b.get(key), a.get(key)))
        if a.get("override_materials") != [expected_material]:
            problems.append("MATERIAL|%s|%r" % (scope, a.get("override_materials")))
    return problems


def revert_problems(before, after):
    problems = []
    for scope in ("template", "instance"):
        keys = STATE_KEYS + ("override_materials",)
        for key in keys:
            if before[scope].get(key) != after[scope].get(key):
                problems.append("RESTORE|%s|%s" % (scope, key))
    return problems


def _u():
    import unreal
    return unreal


def _path(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def _full(obj):
    return None if obj is None else str(obj.get_path_name())


def _census():
    u = _u()
    lib = u.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _world_guard(write=False):
    u = _u()
    pie = list(u.EditorLevelLibrary.get_pie_worlds(False))
    require(not pie, "PIE_RUNNING_STOP_AND_REPORT")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and _path(world) == WORLD, "WORLD|%s" % _path(world))
    if write:
        require(_census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%s" % json.dumps(_census()))
    return world


def _backup(tag, run, files):
    folder = PROJECT + "Backups/Pre%s-%s" % (tag, run)
    require(not os.path.exists(folder), "BACKUP_EXISTS|" + folder)
    os.makedirs(folder)
    rows = []
    for src in files:
        require(os.path.isfile(src), "BACKUP_SOURCE|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        require(sha256_file(src) == sha256_file(dst), "BACKUP_HASH|" + src)
        rows.append({"source": src, "copy": dst, "sha256": sha256_file(src)})
    write_json(os.path.join(folder, "backup_manifest.json"), {"run": run, "files": rows})
    return folder, rows


def _package_file(package, ext=".uasset"):
    require(package.startswith("/Game/"), "PACKAGE_PATH|" + package)
    return PROJECT + "Content/" + package[len("/Game/"):] + ext


def _save_exact(content, maps):
    u = _u()
    before = _census()
    require(before == {"content": sorted(content), "maps": sorted(maps)},
            "DIRTY_SCOPE|%s|want=%s" % (json.dumps(before), json.dumps({"content": content, "maps": maps})))
    for package in sorted(content):
        require(u.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "SAVE_ASSET|" + package)
    if maps:
        require(maps == [WORLD], "MAP_SCOPE|%r" % maps)
        require(u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(_census()))
    return before


def _import_texture(opts):
    u = _u()
    key = opts["texture"]
    filename, asset_name, compression, srgb, sampler = texture_catalog()[key]
    src, asset = HERE + filename, TEX_DIR + "/" + asset_name
    require(os.path.isfile(src), "SOURCE_MISSING|" + src)
    require(not u.EditorAssetLibrary.does_asset_exist(asset), "ASSET_EXISTS|" + asset)
    backup, rows = _backup("ShroudHessianImport", opts["run"], [])
    pending = {"run": opts["run"], "key": key, "source": src, "source_sha256": sha256_file(src),
               "source_size": png_size(src), "asset": asset, "compression": compression, "srgb": srgb,
               "sampler": sampler, "backup": backup, "backup_files": rows}
    write_json(TEXTURE_PENDING, pending, exclusive=True)  # record before first Unreal mutation
    task = u.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", TEX_DIR)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = u.load_asset(asset)
    require(tex is not None, "IMPORT_FAILED|" + asset)
    tex.modify()
    tex.set_editor_property("compression_settings", getattr(u.TextureCompressionSettings, compression))
    tex.set_editor_property("srgb", bool(srgb))
    tex.set_editor_property("flip_green_channel", False)
    require(_census() == {"content": [asset], "maps": []}, "IMPORT_DIRTY_SCOPE|%s" % json.dumps(_census()))
    u.log("SHROUD_HESSIAN_IMPORT_TEX_PENDING|run=%s|key=%s|asset=%s|later=MAT_CHECK" %
          (opts["run"], key, asset))
    return pending


def _texture_readback(rec):
    u = _u()
    tex = u.load_asset(rec["asset"])
    require(tex is not None, "TEXTURE_MISSING|" + rec["asset"])
    return {"compression": str(tex.get_editor_property("compression_settings")),
            "srgb": bool(tex.get_editor_property("srgb")),
            "flip_green": bool(tex.get_editor_property("flip_green_channel")),
            "size": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]}


def _texture_problems(rec, got):
    return (["COMPRESSION|%s" % got["compression"]] if rec["compression"] not in got["compression"] else []) + \
           (["SRGB|%s" % got["srgb"]] if got["srgb"] != rec["srgb"] else []) + \
           (["FLIP_GREEN"] if got["flip_green"] else []) + \
           (["SIZE|%s!=%s" % (got["size"], rec["source_size"])] if got["size"] != rec["source_size"] else [])


def _custom_output_enum(u, name):
    return getattr(u.CustomMaterialOutputType, {"F1": "CMOT_FLOAT1", "F2": "CMOT_FLOAT2", "F3": "CMOT_FLOAT3"}[name])


def _build_master(textures):
    u = _u()
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    require(not eal.does_asset_exist(MASTER), "MASTER_EXISTS|" + MASTER)
    folder, name = MASTER.rsplit("/", 1)
    mat = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_clothing", True)
    mat.set_editor_property("used_with_skeletal_mesh", True)
    mat.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    spec, made = material_spec(), {}
    for index, (key, (kind, value)) in enumerate(spec["nodes"].items()):
        x, y = -1300 + (index % 3) * 400, -900 + (index // 3) * 150
        if kind == "texcoord":
            node = mel.create_material_expression(mat, u.MaterialExpressionTextureCoordinate, x, y)
            node.set_editor_property("coordinate_index", int(value))
        elif kind == "texture":
            node = mel.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, x, y)
            node.set_editor_property("parameter_name", key)
            node.set_editor_property("texture", textures[value])
            node.set_editor_property("sampler_type", getattr(u.MaterialSamplerType, texture_catalog()[value][4]))
        elif kind == "scalar":
            node = mel.create_material_expression(mat, u.MaterialExpressionScalarParameter, x, y)
            node.set_editor_property("parameter_name", key)
            node.set_editor_property("default_value", float(value))
        elif kind == "vector":
            node = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, x, y)
            node.set_editor_property("parameter_name", key)
            node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        elif kind == "twosided":
            node = mel.create_material_expression(mat, u.MaterialExpressionTwoSidedSign, x, y)
        else:
            code, inputs, output = value
            node = mel.create_material_expression(mat, u.MaterialExpressionCustom, x, y)
            node.set_editor_property("code", code)
            node.set_editor_property("output_type", _custom_output_enum(u, output))
            pins = []
            for input_name in inputs:
                pin = u.CustomInput()
                pin.set_editor_property("input_name", input_name)
                pins.append(pin)
            node.set_editor_property("inputs", pins)
        require(node is not None, "NODE|" + key)
        made[key] = node
    for src, output, dst, pin in spec["edges"]:
        require(mel.connect_material_expressions(made[src], output, made[dst], pin),
                "LINK|%s.%s->%s.%s" % (src, output, dst, pin))
    for src, output, prop in spec["properties"]:
        require(mel.connect_material_property(made[src], output, getattr(u.MaterialProperty, prop)), "PROP|" + prop)
    errors = [str(x) for x in (mel.recompile_material(mat) or [])]
    require(not errors, "COMPILE|%r" % errors)
    return mat


def _build_materials(opts):
    u = _u()
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    all_paths = [MASTER] + list(MATERIAL_INSTANCES.values())
    require(not [p for p in all_paths if eal.does_asset_exist(p)], "MATERIAL_ASSET_EXISTS")
    texture_keys = list(texture_catalog())
    missing = [texture_asset(k) for k in texture_keys if not eal.does_asset_exist(texture_asset(k))]
    require(not missing, "TEXTURES_MISSING|%r" % missing)
    textures = {k: u.load_asset(texture_asset(k)) for k in texture_keys}
    backup, rows = _backup("ShroudHessianMaterial", opts["run"], [])
    rec = {"run": opts["run"], "master": MASTER, "instances": MATERIAL_INSTANCES,
           "scalars": opts["scalars"], "vectors": opts["vectors"], "backup": backup, "backup_files": rows,
           "expected_packages": sorted(all_paths)}
    write_json(MATERIAL_PENDING, rec, exclusive=True)  # before first material creation
    master = _build_master(textures)
    factory = u.MaterialInstanceConstantFactoryNew()
    for number, path in MATERIAL_INSTANCES.items():
        folder, name = path.rsplit("/", 1)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant, factory)
        require(mi is not None, "MI_CREATE|" + path)
        mel.set_material_instance_parent(mi, master)
        mel.set_material_instance_texture_parameter_value(mi, "WeaveBase", textures["WeaveBC"])
        mel.set_material_instance_texture_parameter_value(mi, "WeaveNormal", textures["WeaveN"])
        mel.set_material_instance_texture_parameter_value(mi, "StainTint", textures["Stain%02dTint" % number])
        mel.set_material_instance_texture_parameter_value(mi, "StainMask", textures["Stain%02dMask" % number])
        for key, value in opts["scalars"].items():
            mel.set_material_instance_scalar_parameter_value(mi, key, float(value))
        for key, value in opts["vectors"].items():
            mel.set_material_instance_vector_parameter_value(mi, key, u.LinearColor(*value))
        mel.update_material_instance(mi)
    require(_census() == {"content": sorted(all_paths), "maps": []},
            "BUILD_DIRTY_SCOPE|%s" % json.dumps(_census()))
    u.log("SHROUD_HESSIAN_BUILD_MAT_PENDING|run=%s|assets=%d|later=MAT_CHECK" % (opts["run"], len(all_paths)))
    return rec


def _expression_inventory(mat):
    u = _u()
    out = {"classes": {}, "texture_parameters": {}, "scalar_parameters": [], "vector_parameters": [], "custom": {}}
    for node in u.MaterialEditingLibrary.get_material_expressions(mat):
        cls = str(node.get_class().get_name())
        out["classes"][cls] = out["classes"].get(cls, 0) + 1
        if cls == "MaterialExpressionTextureSampleParameter2D":
            out["texture_parameters"][str(node.get_editor_property("parameter_name"))] = _path(node.get_editor_property("texture"))
        elif cls == "MaterialExpressionScalarParameter":
            out["scalar_parameters"].append(str(node.get_editor_property("parameter_name")))
        elif cls == "MaterialExpressionVectorParameter":
            out["vector_parameters"].append(str(node.get_editor_property("parameter_name")))
        elif cls == "MaterialExpressionCustom":
            code = str(node.get_editor_property("code"))
            out["custom"][hashlib.sha256(code.encode("utf-8")).hexdigest()] = code
    out["scalar_parameters"].sort()
    out["vector_parameters"].sort()
    return out


def _serialized_mi(mi):
    """Read serialized arrays; avoids MaterialEditingLibrary getters that can dirty MIs in this project."""
    def name(row):
        info = row.get_editor_property("parameter_info")
        return str(info.get_editor_property("name"))
    textures = {name(row): _path(row.get_editor_property("parameter_value"))
                for row in (mi.get_editor_property("texture_parameter_values") or [])}
    scalars = {name(row): float(row.get_editor_property("parameter_value"))
               for row in (mi.get_editor_property("scalar_parameter_values") or [])}
    vectors = {}
    for row in (mi.get_editor_property("vector_parameter_values") or []):
        c = row.get_editor_property("parameter_value")
        vectors[name(row)] = [float(c.r), float(c.g), float(c.b), float(c.a)]
    return {"parent": _path(mi.get_editor_property("parent")), "textures": textures,
            "scalars": scalars, "vectors": vectors}


def _material_check_problems(rec):
    u = _u()
    mat = u.load_asset(rec["master"])
    require(mat is not None, "MASTER_MISSING")
    mel = u.MaterialEditingLibrary
    inv, spec, problems = _expression_inventory(mat), material_spec(), []
    for flag in ("two_sided", "used_with_clothing", "used_with_skeletal_mesh"):
        if not bool(mat.get_editor_property(flag)):
            problems.append("MASTER_FLAG|" + flag)
    terminal = mel.get_material_property_input_node(mat, u.MaterialProperty.MP_NORMAL)
    if terminal is None or str(terminal.get_class().get_name()) != "MaterialExpressionCustom" or \
            str(terminal.get_editor_property("code")) != NORMAL_CODE:
        problems.append("NORMAL_TERMINAL")
    else:
        names = [str(x) for x in mel.get_material_expression_input_names(terminal)]
        upstream = list(mel.get_inputs_for_material_expression(mat, terminal))
        links = dict(zip(names, upstream)) if len(names) == len(upstream) else {}
        want = {"N": ("MaterialExpressionTextureSampleParameter2D", "WeaveNormal"),
                "S": ("MaterialExpressionScalarParameter", "NormalStrength"),
                "TwoSided": ("MaterialExpressionTwoSidedSign", None)}
        for pin, (cls, parameter) in want.items():
            node = links.get(pin)
            if node is None or str(node.get_class().get_name()) != cls:
                problems.append("NORMAL_LINK|%s|%s" % (pin, None if node is None else node.get_class().get_name()))
            elif parameter is not None and str(node.get_editor_property("parameter_name")) != parameter:
                problems.append("NORMAL_LINK_PARAMETER|%s" % pin)
    if sorted(inv["texture_parameters"]) != sorted(spec["texture_parameters"]):
        problems.append("TEX_PARAMS|%r" % inv["texture_parameters"])
    if inv["scalar_parameters"] != sorted(spec["scalar_parameters"]):
        problems.append("SCALAR_PARAMS|%r" % inv["scalar_parameters"])
    if inv["vector_parameters"] != sorted(spec["vector_parameters"]):
        problems.append("VECTOR_PARAMS|%r" % inv["vector_parameters"])
    expected_custom = {hashlib.sha256(code.encode("utf-8")).hexdigest() for kind, value in spec["nodes"].values()
                       if kind == "custom" for code in [value[0]]}
    if not expected_custom <= set(inv["custom"]):
        problems.append("CUSTOM_CODE")
    for number, path in MATERIAL_INSTANCES.items():
        mi = u.load_asset(path)
        if mi is None:
            problems.append("MI_MISSING|" + path)
            continue
        got = _serialized_mi(mi)
        expected_tex = {"WeaveBase": texture_asset("WeaveBC"), "WeaveNormal": texture_asset("WeaveN"),
                        "StainTint": texture_asset("Stain%02dTint" % number),
                        "StainMask": texture_asset("Stain%02dMask" % number)}
        if got["parent"] != MASTER or got["textures"] != expected_tex:
            problems.append("MI_LINKS|%02d|%r" % (number, got))
        for key, value in rec["scalars"].items():
            if key not in got["scalars"] or abs(got["scalars"][key] - value) > 1e-4:
                problems.append("MI_SCALAR|%02d|%s" % (number, key))
        for key, value in rec["vectors"].items():
            if key not in got["vectors"] or max(abs(a - b) for a, b in zip(got["vectors"][key], value)) > 1e-4:
                problems.append("MI_VECTOR|%02d|%s" % (number, key))
    return problems, inv


def _mat_check(opts):
    u = _u()
    if os.path.isfile(TEXTURE_PENDING):
        rec = read_json(TEXTURE_PENDING)
        require(_census() == {"content": [rec["asset"]], "maps": []}, "CHECK_DIRTY_SCOPE|%s" % json.dumps(_census()))
        before = _texture_readback(rec)
        problems = _texture_problems(rec, before)
        require(not problems, "TEXTURE_READBACK|%r" % problems)
        saved = _save_exact([rec["asset"]], [])
        after = _texture_readback(rec)
        require(not _texture_problems(rec, after), "TEXTURE_AFTER_SAVE|%r" % after)
        rec.update({"checked_run": opts["run"], "readback_before_save": before, "readback_after_save": after,
                    "saved_packages": saved["content"]})
        final = HERE + "shroud_hessian_import_%s.json" % rec["key"]
        write_json(final, rec, exclusive=True)
        os.replace(TEXTURE_PENDING, TEXTURE_PENDING + ".completed-" + opts["run"])
        u.log("SHROUD_HESSIAN_IMPORT_TEX_OK|run=%s|key=%s|asset=%s" % (opts["run"], rec["key"], rec["asset"]))
        return rec
    rec = read_json(MATERIAL_PENDING)
    require(_census() == {"content": sorted(rec["expected_packages"]), "maps": []},
            "CHECK_DIRTY_SCOPE|%s" % json.dumps(_census()))
    problems, before = _material_check_problems(rec)
    require(not problems, "MATERIAL_READBACK|%r" % problems)
    saved = _save_exact(rec["expected_packages"], [])
    problems, after = _material_check_problems(rec)
    require(not problems, "MATERIAL_AFTER_SAVE|%r" % problems)
    rec.update({"checked_run": opts["run"], "inventory_before_save": before, "inventory_after_save": after,
                "saved_packages": saved["content"]})
    final = HERE + "shroud_hessian_material_record.json"
    write_json(final, rec, exclusive=True)
    os.replace(MATERIAL_PENDING, MATERIAL_PENDING + ".completed-" + opts["run"])
    u.log("SHROUD_HESSIAN_BUILD_MAT_OK|run=%s|master=%s|instances=%d" %
          (opts["run"], rec["master"], len(rec["instances"])))
    return rec


def _components(actor, name):
    u = _u()
    return [c for c in actor.get_components_by_class(u.ActorComponent) if str(c.get_name()) == name]


def _one_cloth(actor):
    hits = _components(actor, CLOTH_COMPONENT)
    require(len(hits) == 1 and str(hits[0].get_class().get_name()) == "ChaosClothComponent",
            "CLOTH_COMPONENT|%s|%d" % (actor.get_actor_label(), len(hits)))
    return hits[0]


def _figure_actors(figures):
    u = _u()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    by_label = {}
    for f in figures:
        hits = [a for a in actors if str(a.get_actor_label()) == FIGURE_LABELS[f]]
        require(len(hits) == 1, "FIGURE_ACTOR|%s|%d" % (f, len(hits)))
        by_label[f] = hits[0]
    return by_label


def _template(bp_path):
    u = _u()
    bp = u.load_asset(bp_path)
    require(bp is not None, "BP_MISSING|" + bp_path)
    sds = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    objects = []
    for handle in handles:
        obj = u.SubobjectDataBlueprintFunctionLibrary.get_object(
            u.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
        if obj is not None and str(obj.get_name()) in (CLOTH_COMPONENT, CLOTH_COMPONENT + "_GEN_VARIABLE"):  # [meas SHROUDBP 9 Oct] BP templates carry _GEN_VARIABLE
            objects.append(obj)
    unique = {_full(o): o for o in objects}
    require(len(unique) == 1, "TEMPLATE_COUNT|%s|%d" % (bp_path, len(unique)))
    cloth = next(iter(unique.values()))
    require(str(cloth.get_class().get_name()) == "ChaosClothComponent", "TEMPLATE_CLASS|" + bp_path)
    return bp, cloth


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rot(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def _state(cloth, body=None):
    try:
        parent = cloth.get_attach_parent()
        attach_socket = str(cloth.get_attach_socket_name())
        attach_parent = str(parent.get_name()) if parent else None
    except Exception as exc:
        parent, attach_socket, attach_parent = None, "UNREADABLE", "UNREADABLE|%s" % exc
    def prop(name):
        try:
            return cloth.get_editor_property(name)
        except Exception as exc:
            return "UNREADABLE|%s" % exc
    out = {"class": str(cloth.get_class().get_name()),
           "asset": _path(cloth.get_asset()),
           "override_materials": [_path(x) for x in (cloth.get_editor_property("override_materials") or [])],
           "relative_location": _vec(cloth.get_editor_property("relative_location")),
           "relative_rotation": _rot(cloth.get_editor_property("relative_rotation")),
           "relative_scale": _vec(cloth.get_editor_property("relative_scale3d")),
           "absolute_rotation": bool(cloth.get_editor_property("absolute_rotation")),
           "attach_socket": attach_socket, "attach_parent": attach_parent,
           "parent_is_this_body": (_full(parent) == _full(body)) if body is not None else None,
           "teleport_distance_threshold": prop("teleport_distance_threshold"),
           "teleport_rotation_threshold": prop("teleport_rotation_threshold"),
           "use_attached_parent_as_pose_component": prop("use_attached_parent_as_pose_component"),
           "visible": prop("visible"), "hidden_in_game": prop("hidden_in_game"),
           "suspend_simulation": prop("suspend_simulation"), "enable_simulation": prop("enable_simulation")}
    return out


def _body(actor):
    hits = _components(actor, "Body")
    require(len(hits) == 1, "BODY|%s|%d" % (actor.get_actor_label(), len(hits)))
    return hits[0]


def _figure_state(fig, actor=None):
    actor = actor or _figure_actors([fig])[fig]
    bp, template = _template(BP_PATHS[fig])
    return {"blueprint": BP_PATHS[fig], "actor": _full(actor),
            "template": _state(template), "instance": _state(_one_cloth(actor), _body(actor))}


def _set_template_material(fig, material):
    u = _u()
    bp, cloth = _template(BP_PATHS[fig])
    cloth.modify()
    cloth.set_editor_property("override_materials", [material])
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    return bp


def _set_instance_material(fig, material):
    cloth = _one_cloth(_figure_actors([fig])[fig])
    cloth.modify()
    cloth.set_editor_property("override_materials", [material])


def _apply(opts):
    u = _u()
    assignments = seeded_assignments(opts["figures"], opts["seed"])
    assets = {f: u.load_asset(MATERIAL_INSTANCES[n]) for f, n in assignments.items()}
    require(not [f for f, mi in assets.items() if mi is None], "MI_MISSING")
    actors = _figure_actors(opts["figures"])
    before = {f: _figure_state(f, actors[f]) for f in opts["figures"]}
    require(_census() == {"content": [], "maps": []}, "LOOKUP_DIRTIED|%s" % json.dumps(_census()))
    files = [_package_file(BP_PATHS[f]) for f in opts["figures"]] + [UMAP]
    rec = {"run": opts["run"], "seed": opts["seed"], "figures": opts["figures"],
           "assignments": {f: MATERIAL_INSTANCES[n] for f, n in assignments.items()}, "before": before, "saved": False}
    write_json(APPLY_RECORD, rec, exclusive=True)
    rec["backup"], rec["backup_files"] = _backup("ShroudHessian", opts["run"], files)
    write_json(APPLY_RECORD, rec)
    for f in opts["figures"]:
        _set_template_material(f, assets[f])
    for f in opts["figures"]:
        _set_instance_material(f, assets[f])
    after = {f: _figure_state(f) for f in opts["figures"]}
    problems = [p for f in opts["figures"] for p in transition_problems(before[f], after[f], rec["assignments"][f])]
    require(not problems, "APPLY_READBACK|%r" % problems[:12])
    content, maps = sorted(BP_PATHS[f] for f in opts["figures"]), [WORLD]
    # [meas SHAPPLY1 9 Oct] assigning the new MIs to the cloth components dirties those MIs (engine-side; this tool never
    # edits them).  Save exactly the ASSIGNED MIs that are dirty, alongside the BPs; anything else still refuses.
    assigned = set(rec["assignments"].values())
    content = sorted(set(content) | {pk for pk in _census()["content"] if pk in assigned})
    rec["dirty_before_save"] = _save_exact(content, maps)
    again = {f: _figure_state(f) for f in opts["figures"]}
    problems = [p for f in opts["figures"] for p in transition_problems(before[f], again[f], rec["assignments"][f])]
    require(not problems, "APPLY_AFTER_SAVE|%r" % problems[:12])
    rec.update({"after": again, "saved": True, "saved_packages": {"content": content, "maps": maps}})
    write_json(APPLY_RECORD, rec)
    u.log("SHROUD_HESSIAN_APPLY_OK|run=%s|seed=%s|figures=%d" % (opts["run"], opts["seed"], len(opts["figures"])))
    return rec


def _revert(opts):
    u = _u()
    rec = read_json(APPLY_RECORD)
    require(rec.get("saved"), "APPLY_RECORD_UNSAVED")
    figs = rec["figures"]
    now = {f: _figure_state(f) for f in figs}
    drift = [p for f in figs for p in transition_problems(rec["before"][f], now[f], rec["assignments"][f])]
    require(not drift, "DRIFT_SINCE_APPLY|%r" % drift[:12])
    require(_census() == {"content": [], "maps": []}, "LOOKUP_DIRTIED|%s" % json.dumps(_census()))
    files = [_package_file(BP_PATHS[f]) for f in figs] + [UMAP]
    backup, rows = _backup("ShroudHessianRevert", opts["run"], files)
    for f in figs:
        old = [u.load_asset(p) if p else None for p in rec["before"][f]["template"]["override_materials"]]
        bp, cloth = _template(BP_PATHS[f])
        cloth.modify(); cloth.set_editor_property("override_materials", old)
        u.BlueprintEditorLibrary.compile_blueprint(bp)
    for f in figs:
        old = [u.load_asset(p) if p else None for p in rec["before"][f]["instance"]["override_materials"]]
        cloth = _one_cloth(_figure_actors([f])[f]); cloth.modify(); cloth.set_editor_property("override_materials", old)
    restored = {f: _figure_state(f) for f in figs}
    problems = [p for f in figs for p in revert_problems(rec["before"][f], restored[f])]
    require(not problems, "REVERT_READBACK|%r" % problems[:12])
    content, maps = sorted(BP_PATHS[f] for f in figs), [WORLD]
    _save_exact(content, maps)
    restored = {f: _figure_state(f) for f in figs}
    problems = [p for f in figs for p in revert_problems(rec["before"][f], restored[f])]
    require(not problems, "REVERT_AFTER_SAVE|%r" % problems[:12])
    rec["reverted"] = {"run": opts["run"], "backup": backup, "backup_files": rows}
    write_json(APPLY_RECORD, rec)
    os.replace(APPLY_RECORD, APPLY_RECORD + ".reverted-" + opts["run"])
    u.log("SHROUD_HESSIAN_REVERT_OK|run=%s|figures=%d" % (opts["run"], len(figs)))
    return rec["reverted"]


def _dry(opts):
    assignments = seeded_assignments(opts["figures"], opts["seed"])
    out = {"run": opts["run"], "world": WORLD, "census": _census(),
           "texture_pending": os.path.isfile(TEXTURE_PENDING), "material_pending": os.path.isfile(MATERIAL_PENDING),
           "apply_record": os.path.isfile(APPLY_RECORD),
           "assignments": {f: MATERIAL_INSTANCES[n] for f, n in assignments.items()}, "figures": {}}
    for f in opts["figures"]:
        out["figures"][f] = _figure_state(f)
    require(_census() == out["census"], "DRY_DIRTIED|%s" % json.dumps(_census()))
    write_json(HERE + "shroud_hessian_dry_%s.json" % opts["run"], out)
    _u().log("SHROUD_HESSIAN_DRY_OK|run=%s|figures=%d|seed=%d" %
             (opts["run"], len(opts["figures"]), opts["seed"]))
    return out


def main():
    u = _u()
    run, mode = "NO_RUN", "NO_MODE"
    try:
        raw = read_json(ARGS)
        records = {"texture": os.path.isfile(TEXTURE_PENDING), "material": os.path.isfile(MATERIAL_PENDING),
                   "apply": os.path.isfile(APPLY_RECORD)}
        opts = parse_args(raw, records)
        run, mode = opts["run"], opts["mode"]
        u.log("SHROUD_HESSIAN_START|run=%s|mode=%s" % (run, mode))
        _world_guard(write=mode in WRITE_MODES)
        if mode == "DRY":
            return _dry(opts)
        if mode == "IMPORT_TEX":
            return _import_texture(opts)
        if mode == "BUILD_MAT":
            return _build_materials(opts)
        if mode == "MAT_CHECK":
            return _mat_check(opts)
        if mode == "APPLY":
            return _apply(opts)
        return _revert(opts)
    except Exception as exc:
        if mode == "APPLY" and os.path.isfile(APPLY_RECORD):
            try:
                failed = read_json(APPLY_RECORD)
                if not failed.get("saved"):
                    os.replace(APPLY_RECORD, APPLY_RECORD + ".failed-" + run)
            except Exception:
                pass
        census = {}
        try:
            census = _census()
        except Exception:
            pass
        u.log_error("SHROUD_HESSIAN_FAILED|run=%s|mode=%s|%s|census=%s|NOTHING SAVED unless an *_OK marker printed" %
                    (run, mode, str(exc).replace("\n", " "), json.dumps(census)))
        raise


if __name__ == "__main__":
    main()
