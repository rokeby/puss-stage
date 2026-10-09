"""Create-only industrial tiling master for the P02 Flat V3 industrial pieces.

Offline-authored; the conductor runs this later through ExecuteProjectPythonFile.

Modes:
  DRY     read-only preflight; the target must not exist.
  APPLY   create exactly one new Material package, read it back, and save only it.
  REVERT  produce an exact delete list. It never deletes the created asset.

The graph samples UV channel 1, whose Flat V3 contract is metres on every slot,
and converts it to centimetres before dividing by TileSizeCmU/V. The master is
two-sided because the same contract requires the Flap slot to be two-sided; the
P02 retexture tool uses this master for Front, Flap, and Timber child MIs.
"""
from __future__ import annotations

import datetime
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline import and harness.
    unreal = None


MARK = "INDUSTRIAL_MASTER"
TOKEN = "INDUSTRIALMASTER"
MASTER = "/Game/Scenes/Wings/PaintedSurface/Industrial/M_Wing_IndustrialTiling_Master"
ARGS_NAME = "industrial_master_args.json"
RECORD_NAME = "industrial_master_record.json"
REPORT_NAME = "industrial_master_report.json"
REVERT_REPORT_NAME = "industrial_master_revert_delete_list.json"

DEFAULT_TEXTURES = {
    "BaseColorTexture": "/Engine/EngineResources/WhiteSquareTexture",
    "NormalTexture": "/Engine/EngineMaterials/FlatNormal",
    # This project texture is already sampled as LINEAR_GRAYSCALE by the painted-surface master.
    "RoughnessTexture": "/Game/Scenes/Wings/PaintedSurface/Textures/T_WingDetail_Grime",
    "AOTexture": "/Game/Scenes/Wings/PaintedSurface/Textures/T_WingDetail_Grime",
}
TEXTURE_SAMPLERS = {
    "BaseColorTexture": "SAMPLERTYPE_COLOR",
    "NormalTexture": "SAMPLERTYPE_NORMAL",
    "RoughnessTexture": "SAMPLERTYPE_LINEAR_GRAYSCALE",
    "AOTexture": "SAMPLERTYPE_LINEAR_GRAYSCALE",
}
SCALAR_DEFAULTS = {"TileSizeCmU": 100.0, "TileSizeCmV": 100.0}
CUSTOM_DESC = "UV1 metres to industrial texture tiles"
CUSTOM_INPUTS = ("UV1Metres", "TileSizeCmU", "TileSizeCmV")
CUSTOM_CODE = (
    "float u = UV1Metres.x * 100.0 / max(abs(TileSizeCmU), 1.0);\n"
    "float v = UV1Metres.y * 100.0 / max(abs(TileSizeCmV), 1.0);\n"
    "return float2(u, v);"
)
# UV1 + two scalar parameters + one Custom coordinate node + four texture parameters.
EXPECTED_EXPRESSIONS = 8


class PlanError(ValueError):
    pass


def require(value, message):
    if not value:
        raise PlanError(str(message))


def utc_run(prefix):
    return "%s-%s" % (prefix, datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S"))


def here():
    if unreal is not None:
        saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        return os.path.join(saved, "CodexFlatV3", "industrial")
    return os.path.dirname(os.path.abspath(__file__))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def validate_args(raw):
    args = {
        "mode": "DRY",
        "confirm": "",
        "master": MASTER,
        "tile_size_cm_u": SCALAR_DEFAULTS["TileSizeCmU"],
        "tile_size_cm_v": SCALAR_DEFAULTS["TileSizeCmV"],
        "two_sided": True,
        "allow_permanent_asset_delete": False,
    }
    args.update(raw or {})
    args["mode"] = str(args.get("mode", "DRY")).upper()
    require(args["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|" + args["mode"])
    if args["mode"] != "DRY":
        want = "%s %s" % (args["mode"], TOKEN)
        require(args.get("confirm") == want, "CONFIRM|want=" + want)
    require(args.get("master") == MASTER, "MASTER_PATH_DRIFT")
    require(args.get("allow_permanent_asset_delete") is False, "PERMANENT_DELETE_FORBIDDEN")
    require(args.get("two_sided") is True, "FLAT_V3_FLAP_REQUIRES_TWO_SIDED")
    for key in ("tile_size_cm_u", "tile_size_cm_v"):
        value = float(args[key])
        require(25.0 <= value <= 1000.0, "TILE_SIZE|%s|%s" % (key, value))
        args[key] = value
    return args


def asset_id(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def package_names(packages):
    out = []
    for package in packages:
        getter = getattr(package, "get_name", None) or getattr(package, "get_path_name")
        out.append(str(getter()).split(".", 1)[0])
    return sorted(out)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": package_names(lib.get_dirty_content_packages()),
        "maps": package_names(lib.get_dirty_map_packages()),
    }


def asset_file(path):
    require(path.startswith("/Game/"), "NOT_GAME_PATH|" + path)
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.normpath(os.path.join(root, path[len("/Game/"):].replace("/", os.sep)) + ".uasset")


def backup_prechange(run, args, dirty_before, backup_root=None):
    root = backup_root
    if root is None:
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        root = os.path.join(project, "Backups")
    target = os.path.join(root, "PreIndustrialMaster-" + run)
    os.makedirs(target, exist_ok=False)
    target_file = asset_file(MASTER)
    require(not os.path.exists(target_file), "CREATE_ONLY_FILE_EXISTS|" + target_file)
    manifest = {
        "run": run,
        "purpose": "before create-only industrial master build",
        "target_asset": MASTER,
        "target_file": target_file,
        "target_existed": False,
        "dirty_before": dirty_before,
        "args": args,
    }
    write_json(os.path.join(target, "prechange.json"), manifest, exclusive=True)
    return target


def editor_guard():
    require(unreal is not None, "UNREAL_REQUIRED")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")


def preflight(args, state_dir=None):
    editor_guard()
    before = census()
    require(before == {"content": [], "maps": []}, "DIRTY_CENSUS|" + json.dumps(before, sort_keys=True))
    require(not unreal.EditorAssetLibrary.does_asset_exist(MASTER), "CREATE_ONLY_EXISTS|" + MASTER)
    for parameter, path in DEFAULT_TEXTURES.items():
        require(unreal.load_asset(path) is not None, "DEFAULT_TEXTURE_MISSING|%s|%s" % (parameter, path))
    record = os.path.join(state_dir or here(), RECORD_NAME)
    require(not os.path.exists(record), "ACTIVE_RECORD_EXISTS|" + record)
    return before


def _property_set_and_read(mat, name, value):
    mat.set_editor_property(name, value)
    require(mat.get_editor_property(name) == value, "MATERIAL_PROPERTY_READBACK|%s|%r" % (name, value))


def _node(mat, cls, x, y, **props):
    mel = unreal.MaterialEditingLibrary
    node = mel.create_material_expression(mat, cls, x, y)
    require(node is not None, "CREATE_EXPRESSION|%s" % cls)
    for name, value in props.items():
        node.set_editor_property(name, value)
    return node


def _connect(source, output_name, target, input_name):
    mel = unreal.MaterialEditingLibrary
    ok = mel.connect_material_expressions(source, output_name, target, input_name)
    if not ok and len(mel.get_material_expression_input_names(target)) == 1:
        ok = mel.connect_material_expressions(source, output_name, target, "")
    require(ok, "CONNECT|%s.%s->%s.%s" % (source.get_name(), output_name, target.get_name(), input_name))


def build_graph(mat, args):
    """Build the graph on a NEW, empty Material. No expression deletion exists here."""
    mel = unreal.MaterialEditingLibrary
    require(int(mel.get_num_material_expressions(mat)) == 0, "NEW_ASSET_NOT_EMPTY")
    properties = (
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT),
        ("two_sided", True),
        ("tangent_space_normal", True),
        ("used_with_instanced_static_meshes", True),
        ("used_with_nanite", True),
    )
    for name, value in properties:
        _property_set_and_read(mat, name, value)

    uv1 = _node(mat, unreal.MaterialExpressionTextureCoordinate, -1000, 0, coordinate_index=1)
    scalars = {}
    for index, (name, value) in enumerate((
            ("TileSizeCmU", args["tile_size_cm_u"]),
            ("TileSizeCmV", args["tile_size_cm_v"]))):
        scalars[name] = _node(
            mat, unreal.MaterialExpressionScalarParameter, -1000, 180 + 110 * index,
            parameter_name=name, default_value=float(value), group="01 Tiling", sort_priority=index)

    uv = _node(
        mat, unreal.MaterialExpressionCustom, -650, 0, description=CUSTOM_DESC,
        code=CUSTOM_CODE, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    custom_inputs = []
    for name in CUSTOM_INPUTS:
        custom_input = unreal.CustomInput()
        custom_input.set_editor_property("input_name", name)
        custom_inputs.append(custom_input)
    uv.set_editor_property("inputs", custom_inputs)
    _connect(uv1, "", uv, "UV1Metres")
    _connect(scalars["TileSizeCmU"], "", uv, "TileSizeCmU")
    _connect(scalars["TileSizeCmV"], "", uv, "TileSizeCmV")

    shared = unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS
    textures = {}
    for index, name in enumerate(DEFAULT_TEXTURES):
        texture = unreal.load_asset(DEFAULT_TEXTURES[name])
        textures[name] = _node(
            mat, unreal.MaterialExpressionTextureSampleParameter2D, -300, -300 + 220 * index,
            parameter_name=name, texture=texture,
            sampler_type=getattr(unreal.MaterialSamplerType, TEXTURE_SAMPLERS[name]),
            sampler_source=shared, group="00 Textures", sort_priority=index)
        _connect(uv, "", textures[name], "UVs")

    props = (
        ("BaseColorTexture", "RGB", unreal.MaterialProperty.MP_BASE_COLOR),
        ("NormalTexture", "RGB", unreal.MaterialProperty.MP_NORMAL),
        ("RoughnessTexture", "R", unreal.MaterialProperty.MP_ROUGHNESS),
        ("AOTexture", "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
    )
    for name, output_name, prop in props:
        require(mel.connect_material_property(textures[name], output_name, prop), "CONNECT_PROPERTY|" + name)
    return {"uv": uv, "textures": textures, "scalars": scalars, "properties": properties}


def _parameter_name(node):
    try:
        return str(node.get_editor_property("parameter_name"))
    except Exception:  # Non-parameter expressions.
        return None


def readback(mat, graph=None):
    """Read every contract field back; never trust a setter return value."""
    mel = unreal.MaterialEditingLibrary
    scalar_names = sorted(str(name) for name in mel.get_scalar_parameter_names(mat))
    texture_names = sorted(str(name) for name in mel.get_texture_parameter_names(mat))
    require(scalar_names == sorted(SCALAR_DEFAULTS), "SCALAR_PARAMETER_NAMES|" + json.dumps(scalar_names))
    require(texture_names == sorted(DEFAULT_TEXTURES), "TEXTURE_PARAMETER_NAMES|" + json.dumps(texture_names))
    scalars = {}
    for name in SCALAR_DEFAULTS:
        got = float(mel.get_material_default_scalar_parameter_value(mat, name))
        want = float(graph["scalars"][name].get_editor_property("default_value")) if graph else got
        require(abs(got - want) <= 1e-4, "SCALAR_DEFAULT|%s|%r|%r" % (name, got, want))
        scalars[name] = got
    textures = {}
    for name, want in DEFAULT_TEXTURES.items():
        got = asset_id(mel.get_material_default_texture_parameter_value(mat, name))
        require(got == want, "TEXTURE_DEFAULT|%s|%s|%s" % (name, got, want))
        textures[name] = got
    expression_count = int(mel.get_num_material_expressions(mat))
    require(expression_count == EXPECTED_EXPRESSIONS,
            "EXPRESSION_COUNT|%d|want=%d" % (expression_count, EXPECTED_EXPRESSIONS))
    flags = {}
    for name, want in (("two_sided", True), ("tangent_space_normal", True),
                       ("used_with_instanced_static_meshes", True), ("used_with_nanite", True)):
        got = bool(mat.get_editor_property(name))
        require(got is want, "MATERIAL_FLAG|%s|%r|want=%r" % (name, got, want))
        flags[name] = got
    inputs = {}
    for key, prop in (("base_color", unreal.MaterialProperty.MP_BASE_COLOR),
                      ("normal", unreal.MaterialProperty.MP_NORMAL),
                      ("roughness", unreal.MaterialProperty.MP_ROUGHNESS),
                      ("ambient_occlusion", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)):
        node = mel.get_material_property_input_node(mat, prop)
        require(node is not None, "PROPERTY_UNWIRED|" + key)
        inputs[key] = _parameter_name(node)
    require(inputs == {"base_color": "BaseColorTexture", "normal": "NormalTexture",
                       "roughness": "RoughnessTexture", "ambient_occlusion": "AOTexture"},
            "PROPERTY_SOURCES|" + json.dumps(inputs, sort_keys=True))
    return {
        "asset": asset_id(mat),
        "scalar_parameters": scalars,
        "texture_parameters": textures,
        "expression_count": expression_count,
        "flags": flags,
        "property_sources": inputs,
        "uv_contract": "UV1 metres * 100 / TileSizeCmU,V",
        "mask_sampler": "LINEAR_GRAYSCALE",
    }


def dry(args, run=None, state_dir=None):
    run = run or utc_run("INDMASTER-DRY")
    before = preflight(args, state_dir=state_dir)
    return {
        "mode": "DRY",
        "run": run,
        "marker": MARK + "_DRY_OK",
        "asset": MASTER,
        "create_only": True,
        "dirty_before": before,
        "dirty_after": census(),
        "parameters": {"textures": DEFAULT_TEXTURES, "scalars": {
            "TileSizeCmU": args["tile_size_cm_u"], "TileSizeCmV": args["tile_size_cm_v"]}},
        "two_sided_reason": "Flat V3 Flap slot contract requires two-sided; one master serves Front/Flap/Timber",
        "save_only": [MASTER],
        "revert_policy": "delete-list only; no deletion call",
    }


def apply(args, run=None, state_dir=None, backup_root=None):
    run = run or utc_run("INDMASTER")
    state_dir = state_dir or here()
    before = preflight(args, state_dir=state_dir)
    backup = backup_prechange(run, args, before, backup_root=backup_root)
    record_path = os.path.join(state_dir, RECORD_NAME)
    record = {"status": "STARTED", "run": run, "asset": MASTER, "backup": backup, "args": args}
    write_json(record_path, record, exclusive=True)

    folder, name = MASTER.rsplit("/", 1)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.Material, unreal.MaterialFactoryNew())
    require(mat is not None and asset_id(mat) == MASTER, "CREATE_FAILED|" + MASTER)
    graph = build_graph(mat, args)
    pre_save = readback(mat, graph)
    dirty = census()
    require(dirty == {"content": [MASTER], "maps": []}, "DIRTY_SCOPE_PRE_SAVE|" + json.dumps(dirty))
    unreal.MaterialEditingLibrary.layout_material_expressions(mat)
    errors = [str(error) for error in (unreal.MaterialEditingLibrary.recompile_material(mat) or [])]
    require(not errors, "RECOMPILE_ERRORS|" + json.dumps(errors[:8]))
    require(unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=False), "SAVE_FAILED|" + MASTER)
    require(census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|" + json.dumps(census()))
    require(os.path.isfile(asset_file(MASTER)), "SAVED_FILE_MISSING|" + asset_file(MASTER))
    loaded = unreal.EditorAssetLibrary.load_asset(MASTER)
    require(isinstance(loaded, unreal.Material), "READBACK_TYPE|" + str(type(loaded)))
    post_save = readback(loaded)
    require(post_save == pre_save, "READBACK_CHANGED_ACROSS_SAVE")

    record.update({"status": "APPLIED", "readback": post_save, "saved_file": asset_file(MASTER)})
    write_json(record_path, record)
    report = {
        "mode": "APPLY",
        "run": run,
        "marker": MARK + "_APPLY_OK",
        "asset": MASTER,
        "backup": backup,
        "record": record_path,
        "readback": post_save,
        "dirty_before": before,
        "dirty_after": census(),
        "saved_only": [MASTER],
        "recompile_errors": errors,
        "compile_log_check": "PENDING: after async compile, grep PussStage.log for this asset and 'Failed to compile'",
    }
    write_json(os.path.join(state_dir, REPORT_NAME), report)
    unreal.log("%s_APPLY_OK|run=%s|asset=%s|expressions=%d|dirty=0|compile_log_check=PENDING" %
               (MARK, run, MASTER, post_save["expression_count"]))
    return report


def revert_delete_list(args, run=None, state_dir=None):
    """No mutation: verify ownership and emit the one exact asset/file a human may delete later."""
    run = run or utc_run("INDMASTER-REVERT")
    state_dir = state_dir or here()
    editor_guard()
    require(census() == {"content": [], "maps": []}, "DIRTY_CENSUS|" + json.dumps(census()))
    record_path = os.path.join(state_dir, RECORD_NAME)
    require(os.path.isfile(record_path), "NO_ACTIVE_RECORD|" + record_path)
    record = read_json(record_path)
    require(record.get("status") == "APPLIED" and record.get("asset") == MASTER, "RECORD_NOT_APPLIED")
    require(unreal.EditorAssetLibrary.does_asset_exist(MASTER), "CREATED_ASSET_MISSING|" + MASTER)
    owned = readback(unreal.EditorAssetLibrary.load_asset(MASTER))
    require(owned == record.get("readback"), "OWNED_GRAPH_DRIFT")
    report = {
        "mode": "REVERT",
        "run": run,
        "marker": MARK + "_REVERT_DELETE_LIST_OK",
        "changed_assets": [],
        "deleted_assets": [],
        "delete_list": [{"asset": MASTER, "package_file": asset_file(MASTER)}],
        "record_retained": record_path,
        "instruction": "No deletion was performed. Obtain explicit approval, then delete only this listed asset.",
        "dirty_after": census(),
    }
    write_json(os.path.join(state_dir, REVERT_REPORT_NAME), report)
    unreal.log("%s_REVERT_DELETE_LIST_OK|run=%s|asset=%s|deleted=0" % (MARK, run, MASTER))
    return report


def execute(args, run=None, state_dir=None, backup_root=None):
    args = validate_args(args)
    if args["mode"] == "DRY":
        return dry(args, run=run, state_dir=state_dir)
    if args["mode"] == "APPLY":
        return apply(args, run=run, state_dir=state_dir, backup_root=backup_root)
    return revert_delete_list(args, run=run, state_dir=state_dir)


def main():
    args = validate_args(read_json(os.path.join(here(), ARGS_NAME)))
    run = utc_run("INDMASTER-" + args["mode"])
    try:
        result = execute(args, run=run)
    except Exception as exc:
        if unreal is not None:
            unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, exc))
        raise
    if unreal is not None:
        unreal.log("%s|run=%s" % (result["marker"], result["run"]))
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
