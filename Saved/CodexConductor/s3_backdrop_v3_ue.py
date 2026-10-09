"""DRY/APPLY/REVERT the create-only Scene 3 backdrop-v3 material swap.

APPLY reads the live ``S3 Backdrop`` and ``S3 Hangar Exit Door Leaf`` material
instances, imports two new colour textures without replacement, copies texture
settings from each live SkinColor texture, creates one child MI per live MI with
only SkinColor overridden, and assigns those children to the two actors.

REVERT restores the recorded actor materials.  It intentionally retains the
four create-only assets: deleting Content is outside this tool's authority.
No Unreal object is captured at module import, so the offline harness can test
all planning gates in ordinary Python.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import struct

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BACKDROP_LABEL = "S3 Backdrop"
LEAF_LABEL = "S3 Hangar Exit Door Leaf"
PARAMETER = "SkinColor"

TEXTURE_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/Textures"
MATERIAL_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/Materials"
BACKDROP_TEXTURE = TEXTURE_ROOT + "/T_S3_BackdropV3_SkinColor"
LEAF_TEXTURE = TEXTURE_ROOT + "/T_S3_BackdropV3_ExitDoor_SkinColor"
BACKDROP_MI = MATERIAL_ROOT + "/MI_S3_BackdropV3"
LEAF_MI = MATERIAL_ROOT + "/MI_S3_BackdropV3_ExitDoor"
NEW_ASSETS = (BACKDROP_TEXTURE, LEAF_TEXTURE, BACKDROP_MI, LEAF_MI)

BACKDROP_PNG_NAME = "T_S3_BackdropV3_SkinColor.png"
LEAF_PNG_NAME = "T_S3_BackdropV3_ExitDoor_SkinColor.png"
BUILD_REPORT_NAME = "build_report.json"
EXPECTED_BACKDROP_SIZE = (4096, 8192)
EXPECTED_LEAF_SIZE = (1024, 2048)
EXPECTED_LEAF_RECT = [0.42525, 0.7985, 0.57475, 0.9481666666666667]

# These are the writable sampling/compression decisions that must follow the
# live texture, rather than assumptions baked into this deferred script.
TEXTURE_SETTING_FIELDS = (
    "srgb",
    "compression_settings",
    "mip_gen_settings",
    "lod_group",
    "address_x",
    "address_y",
    "filter",
    "never_stream",
    "virtual_texture_streaming",
    "preserve_border",
)

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
    PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    PROJECT = os.path.dirname(os.path.dirname(HERE))

ARGS_PATH = os.path.join(HERE, "s3_backdrop_v3_args.json")
DRY_PATH = os.path.join(HERE, "s3_backdrop_v3_dry.json")
RECORD_PATH = os.path.join(HERE, "s3_backdrop_v3_record.json")
DEFAULT_BUILD_DIR = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "backdrop_v3", "output")


class PlanError(ValueError):
    pass


def _canonical(path):
    return str(path or "").split(".", 1)[0]


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_size(path):
    with open(path, "rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise PlanError("NOT_PNG|" + path)
    return struct.unpack(">II", header[16:24])


def _json_value(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def leaf_uv_rect(backdrop_bottom_z_cm=-155.0):
    half_y, half_z = 299.0 * 0.5, 449.0 * 0.5
    y0, y1 = -half_y, half_y
    z0, z1 = 225.0 - half_z, 225.0 + half_z
    return [
        (y0 + 1000.0) / 2000.0,
        1.0 - (z1 - backdrop_bottom_z_cm) / 3000.0,
        (y1 + 1000.0) / 2000.0,
        1.0 - (z0 - backdrop_bottom_z_cm) / 3000.0,
    ]


def _near_list(actual, expected, tolerance=1.0e-12):
    return len(actual) == len(expected) and all(
        abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected)
    )


def _resolve_build_inputs(args):
    build_dir = os.path.abspath(str(args.get("build_dir") or DEFAULT_BUILD_DIR))
    return {
        "build_dir": build_dir,
        "backdrop_png": os.path.join(build_dir, BACKDROP_PNG_NAME),
        "leaf_png": os.path.join(build_dir, LEAF_PNG_NAME),
        "report": os.path.join(build_dir, BUILD_REPORT_NAME),
    }


def _load_build_contract(args):
    paths = _resolve_build_inputs(args)
    for path in (paths["backdrop_png"], paths["leaf_png"], paths["report"]):
        if not os.path.isfile(path):
            raise PlanError("BUILD_INPUT_MISSING|" + path)
    if png_size(paths["backdrop_png"]) != EXPECTED_BACKDROP_SIZE:
        raise PlanError("BACKDROP_PNG_SIZE|%r" % (png_size(paths["backdrop_png"]),))
    if png_size(paths["leaf_png"]) != EXPECTED_LEAF_SIZE:
        raise PlanError("LEAF_PNG_SIZE|%r" % (png_size(paths["leaf_png"]),))
    with open(paths["report"], encoding="utf-8") as handle:
        report = json.load(handle)
    plan = report.get("plan", {})
    if plan.get("local_stroke_edits") != 0:
        raise PlanError("BUILD_REPORT_LOCAL_EDITS")
    rect = ((plan.get("leaf") or {}).get("uv_rect_left_top_right_bottom") or [])
    if not _near_list(rect, EXPECTED_LEAF_RECT):
        raise PlanError("BUILD_REPORT_LEAF_RECT|%r" % rect)
    outputs = report.get("outputs", {})
    expected = {
        "backdrop_texture": paths["backdrop_png"],
        "leaf_texture": paths["leaf_png"],
    }
    for key, path in expected.items():
        row = outputs.get(key, {})
        if os.path.basename(str(row.get("path", ""))) != os.path.basename(path):
            raise PlanError("BUILD_REPORT_PATH|" + key)
        if row.get("sha256") != _sha256(path):
            raise PlanError("BUILD_REPORT_HASH|" + key)
    return {
        "paths": paths,
        "sha256": {key: _sha256(path) for key, path in expected.items()},
        "leaf_uv_rect": rect,
        "local_stroke_edits": 0,
    }


def build_plan(state, build_contract):
    """Pure plan/gate used by both live DRY and the offline harness."""
    if state.get("world") != WORLD:
        raise PlanError("WRONG_WORLD")
    if set(state.get("actors", {})) != {"backdrop", "leaf"}:
        raise PlanError("ACTOR_SET")
    if not _near_list(build_contract.get("leaf_uv_rect", []), leaf_uv_rect(-155.0)):
        raise PlanError("LOWERED_LEAF_RECT")
    if int(build_contract.get("local_stroke_edits", -1)) != 0:
        raise PlanError("LOCAL_STROKE_EDITS")
    exists = state.get("new_asset_exists", {})
    if set(exists) != set(NEW_ASSETS) or any(bool(exists[path]) for path in NEW_ASSETS):
        raise PlanError("CREATE_ONLY_ASSET_EXISTS|%r" % exists)
    rows = {}
    definitions = {
        "backdrop": (BACKDROP_TEXTURE, BACKDROP_MI, "backdrop_png"),
        "leaf": (LEAF_TEXTURE, LEAF_MI, "leaf_png"),
    }
    for role, (texture_path, mi_path, source_key) in definitions.items():
        actor = state["actors"][role]
        current_material = _canonical(actor.get("material"))
        current_texture = _canonical(actor.get("skin_color"))
        settings = actor.get("texture_settings") or {}
        if not current_material or not current_texture:
            raise PlanError("LIVE_SOURCE_MISSING|" + role)
        if set(settings) != set(TEXTURE_SETTING_FIELDS):
            raise PlanError("LIVE_TEXTURE_SETTINGS|%s|%r" % (role, sorted(settings)))
        override = {PARAMETER: texture_path}
        if set(override) != {PARAMETER}:
            raise PlanError("PARAM_SWAP_ONLY|" + role)
        rows[role] = {
            "actor_label": actor["label"],
            "actor_object_path": actor["object_path"],
            "component_name": actor["component_name"],
            "old_material": current_material,
            "old_skin_color": current_texture,
            "source_texture_settings": settings,
            "source_png": build_contract["paths"][source_key],
            "source_sha256": build_contract["sha256"]["%s_texture" % role],
            "new_texture": texture_path,
            "new_material": mi_path,
            "new_material_parent": current_material,
            "texture_overrides": override,
            "hidden": bool(actor.get("hidden", False)),
        }
    return {
        "world": WORLD,
        "actors": rows,
        "new_assets": list(NEW_ASSETS),
        "allowed_apply_census": {"content": sorted(NEW_ASSETS), "maps": [WORLD]},
        "leaf_uv_rect": list(build_contract["leaf_uv_rect"]),
        "mural_bottom_z_cm": -155.0,
        "mural_drop_cm": 150.0,
        "param_swap_only": True,
        "revert_policy": "restore actor materials; retain four create-only assets",
    }


def validate_param_swap_only(plan):
    for role, row in plan.get("actors", {}).items():
        if row.get("texture_overrides") != {PARAMETER: row.get("new_texture")}:
            raise PlanError("PARAM_SWAP_ONLY|" + role)
        if row.get("new_material_parent") != row.get("old_material"):
            raise PlanError("CHILD_PARENT|" + role)
    return True


def check_mode(args, record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE|" + mode)
    if mode == "APPLY":
        if args.get("confirm") != "APPLY S3BACKDROPV3":
            raise PlanError("CONFIRM_APPLY")
        if record_exists:
            raise PlanError("RECORD_EXISTS")
    if mode == "REVERT":
        if args.get("confirm") != "REVERT S3BACKDROPV3":
            raise PlanError("CONFIRM_REVERT")
        if not record_exists:
            raise PlanError("RECORD_MISSING")
    return mode


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _census():
    def names(packages):
        return sorted(str(package.get_name()).split(".", 1)[0] for package in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _index():
    result = {}
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def _one(index, label):
    rows = index.get(label, [])
    if len(rows) != 1:
        raise PlanError("ACTOR_COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _one_mesh_component(actor):
    rows = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    if len(rows) != 1:
        raise PlanError("MESH_COMPONENT_COUNT|%s|%d" % (actor.get_actor_label(), len(rows)))
    return rows[0]


def _texture_settings(texture):
    values = {}
    for field in TEXTURE_SETTING_FIELDS:
        values[field] = _json_value(texture.get_editor_property(field))
    return values


def _actor_state(actor):
    component = _one_mesh_component(actor)
    material = component.get_material(0)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise PlanError("CURRENT_MATERIAL_NOT_MI|" + str(actor.get_actor_label()))
    texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, PARAMETER)
    if not isinstance(texture, unreal.Texture2D):
        raise PlanError("CURRENT_SKINCOLOR_NOT_TEXTURE|" + str(actor.get_actor_label()))
    return {
        "label": str(actor.get_actor_label()),
        "object_path": str(actor.get_path_name()),
        "component_name": str(component.get_name()),
        "material": _canonical(material.get_path_name()),
        "skin_color": _canonical(texture.get_path_name()),
        "texture_settings": _texture_settings(texture),
        # Use the 5.8 editor properties; the older runtime visibility helper is absent.
        "hidden": bool(actor.is_hidden_ed()) or bool(actor.get_editor_property("hidden")),
    }


def _live_state():
    index = _index()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    return {
        "world": str(world.get_outermost().get_name()) if world else None,
        "actors": {
            "backdrop": _actor_state(_one(index, BACKDROP_LABEL)),
            "leaf": _actor_state(_one(index, LEAF_LABEL)),
        },
        "new_asset_exists": {
            path: bool(unreal.EditorAssetLibrary.does_asset_exist(path)) for path in NEW_ASSETS
        },
    }


def _context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise PlanError("PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != WORLD:
        raise PlanError("WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise PlanError("SEQUENCER_OPEN")
    return editor, world


def _level_path():
    relative = WORLD.removeprefix("/Game/").replace("/", os.sep) + ".umap"
    return os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), relative
    )


def _backup(run, purpose, record, build_contract):
    folder = os.path.join(PROJECT, "Backups", "%s-%s" % (purpose, run))
    os.makedirs(folder, exist_ok=False)
    sources = [_level_path(), build_contract["paths"]["report"],
               build_contract["paths"]["backdrop_png"], build_contract["paths"]["leaf_png"]]
    copied = []
    for source in sources:
        if not os.path.isfile(source):
            raise PlanError("BACKUP_SOURCE_MISSING|" + source)
        target = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, target)
        copied.append({"source": source, "backup": target, "sha256": _sha256(target),
                       "bytes": os.path.getsize(target)})
    _write(os.path.join(folder, "manifest.json"), {
        "run": run, "world": WORLD, "record_before_unreal_change": record, "files": copied,
    })
    return folder


def _import_texture(source, destination):
    folder, name = destination.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        raise PlanError("CREATE_ONLY_EXISTS|" + destination)
    task = unreal.AssetImportTask()
    for key, value in (("filename", source), ("destination_path", folder),
                       ("destination_name", name), ("automated", True),
                       ("replace_existing", False), ("save", False)):
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.EditorAssetLibrary.load_asset(destination)
    if not isinstance(texture, unreal.Texture2D):
        raise PlanError("TEXTURE_IMPORT_FAILED|" + destination)
    return texture


def _copy_texture_settings(source, target):
    target.modify()
    for field in TEXTURE_SETTING_FIELDS:
        target.set_editor_property(field, source.get_editor_property(field))
    expected, actual = _texture_settings(source), _texture_settings(target)
    if actual != expected:
        raise PlanError("TEXTURE_SETTINGS_READBACK|expected=%r|actual=%r" % (expected, actual))


def _serialized_texture_overrides(instance):
    result = {}
    for value in instance.get_editor_property("texture_parameter_values"):
        info = value.get_editor_property("parameter_info")
        name = str(info.get_editor_property("name"))
        result[name] = _canonical(value.get_editor_property("parameter_value").get_path_name())
    return result


def _create_child(parent_path, destination, texture):
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        raise PlanError("CREATE_ONLY_EXISTS|" + destination)
    parent = unreal.EditorAssetLibrary.load_asset(parent_path)
    if not isinstance(parent, unreal.MaterialInstanceConstant):
        raise PlanError("PARENT_MI_MISSING|" + parent_path)
    folder, name = destination.rsplit("/", 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise PlanError("CREATE_MI_FAILED|" + destination)
    unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        instance, PARAMETER, texture
    )
    unreal.MaterialEditingLibrary.update_material_instance(instance)
    if _canonical(instance.get_editor_property("parent").get_path_name()) != parent_path:
        raise PlanError("MI_PARENT_READBACK|" + destination)
    if _serialized_texture_overrides(instance) != {PARAMETER: _canonical(texture.get_path_name())}:
        raise PlanError("MI_OVERRIDE_READBACK|" + destination)
    return instance


def _save_assets_exact(paths):
    census = _census()
    expected = {"content": sorted(paths), "maps": []}
    if census != expected:
        raise PlanError("ASSET_DIRTY_SCOPE|expected=%s|actual=%s" %
                        (json.dumps(expected), json.dumps(census)))
    saved = {path: bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False))
             for path in paths}
    if not all(saved.values()) or _census() != {"content": [], "maps": []}:
        raise PlanError("ASSET_SAVE|%r|%s" % (saved, json.dumps(_census())))


def _assign(index, label, material_path):
    actor = _one(index, label)
    component = _one_mesh_component(actor)
    material = unreal.EditorAssetLibrary.load_asset(material_path)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise PlanError("ASSIGN_MI_MISSING|" + material_path)
    actor.modify()
    component.modify()
    component.set_material(0, material)
    got = _canonical(component.get_material(0).get_path_name())
    if got != material_path:
        raise PlanError("ASSIGN_READBACK|%s|%s" % (label, got))


def _save_map_exact(world):
    census = _census()
    if census != {"content": [], "maps": [WORLD]}:
        raise PlanError("MAP_DIRTY_SCOPE|" + json.dumps(census))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        raise PlanError("MAP_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        raise PlanError("POST_SAVE_DIRTY|" + json.dumps(_census()))


def _verify_assignments(plan, expected_key):
    state = _live_state()
    for role, row in plan["actors"].items():
        expected = row[expected_key]
        if state["actors"][role]["material"] != expected:
            raise PlanError("POST_SAVE_ASSIGNMENT|%s|%s" %
                            (role, state["actors"][role]["material"]))
    return state


def run_apply(run, args, world):
    build_contract = _load_build_contract(args)
    state = _live_state()
    plan = build_plan(state, build_contract)
    validate_param_swap_only(plan)
    record = {
        "run": run, "world": WORLD, "mode": "APPLY", "applied": False, "saved": False,
        "plan": plan, "census_before": _census(), "proof": {
            "declaration_proven": [
                "New texture assets and child MIs are create-only.",
                "Each new MI overrides only SkinColor and inherits every other parameter.",
            ],
            "measured": [],
            "inferred": ["Rendered visual acceptance remains Gary's."],
        },
    }
    _write(RECORD_PATH, record, exclusive=True)
    record["backup"] = _backup(run, "PreS3BackdropV3", record, build_contract)
    _write(RECORD_PATH, record)

    assets = {}
    for role in ("backdrop", "leaf"):
        row = plan["actors"][role]
        live_source = unreal.EditorAssetLibrary.load_asset(row["old_skin_color"])
        if not isinstance(live_source, unreal.Texture2D):
            raise PlanError("LIVE_TEXTURE_RELOAD|" + role)
        if _texture_settings(live_source) != row["source_texture_settings"]:
            raise PlanError("LIVE_TEXTURE_SETTINGS_DRIFT|" + role)
        texture = _import_texture(row["source_png"], row["new_texture"])
        _copy_texture_settings(live_source, texture)
        material = _create_child(row["new_material_parent"], row["new_material"], texture)
        assets[role] = {"texture": texture, "material": material}
    _save_assets_exact(list(NEW_ASSETS))
    record["assets_saved"] = list(NEW_ASSETS)
    record["asset_post_save_census"] = _census()
    _write(RECORD_PATH, record)

    index = _index()
    _assign(index, BACKDROP_LABEL, BACKDROP_MI)
    _assign(index, LEAF_LABEL, LEAF_MI)
    _save_map_exact(world)
    record["saved"] = True
    _write(RECORD_PATH, record)
    after = _verify_assignments(plan, "new_material")
    if _census() != {"content": [], "maps": []}:
        raise PlanError("POST_READBACK_DIRTY|" + json.dumps(_census()))
    record["post_save"] = after
    record["post_save_census"] = _census()
    record["proof"]["measured"] = [
        "Four new assets were saved and read back with exact parents/overrides/settings.",
        "The two actor assignments were saved, freshly indexed, and read back.",
        "The final dirty-package census was empty.",
    ]
    record["applied"] = True
    _write(RECORD_PATH, record)
    return {"assets_created": 4, "map_saved": 1, "dirty_after": record["post_save_census"]}


def run_revert(run, args, world):
    with open(RECORD_PATH, encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != WORLD or not record.get("applied"):
        raise PlanError("RECORD_INVALID")
    plan = record["plan"]
    _verify_assignments(plan, "new_material")
    build_contract = _load_build_contract(args)
    backup = _backup(run, "PreS3BackdropV3Revert", record, build_contract)
    index = _index()
    _assign(index, BACKDROP_LABEL, plan["actors"]["backdrop"]["old_material"])
    _assign(index, LEAF_LABEL, plan["actors"]["leaf"]["old_material"])
    _save_map_exact(world)
    after = _verify_assignments(plan, "old_material")
    if _census() != {"content": [], "maps": []}:
        raise PlanError("POST_REVERT_DIRTY|" + json.dumps(_census()))
    record.setdefault("reverts", []).append({
        "run": run, "backup": backup, "post_save": after,
        "post_save_census": _census(), "retained_assets": list(NEW_ASSETS),
    })
    record["reverted"] = True
    _write(RECORD_PATH, record)
    return {"map_saved": 1, "materials_restored": 2, "retained_assets": 4,
            "dirty_after": _census()}


def main():
    run = datetime.datetime.now().strftime("S3BDV3-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        if unreal is None:
            raise PlanError("UNREAL_MODULE_UNAVAILABLE")
        with open(ARGS_PATH, encoding="utf-8") as handle:
            args = json.load(handle)
        mode = check_mode(args, os.path.exists(RECORD_PATH))
        _, world = _context()
        census = _census()
        if mode == "DRY":
            build_contract = _load_build_contract(args)
            state = _live_state()
            plan = build_plan(state, build_contract)
            validate_param_swap_only(plan)
            result = {
                "run": run, "mode": mode, "census": census,
                "apply_would_refuse_dirty": census != {"content": [], "maps": []},
                "state": state, "build": build_contract, "plan": plan,
            }
            _write(DRY_PATH, result)
            unreal.log("S3_BACKDROP_V3_DRY_OK|run=%s|mutated=0|new_assets=4|leaf_uv=%s|out=%s" %
                       (run, ",".join("%.9f" % value for value in plan["leaf_uv_rect"]), DRY_PATH))
            return
        if census != {"content": [], "maps": []}:
            raise PlanError("DIRTY_BEFORE|" + json.dumps(census))
        result = run_apply(run, args, world) if mode == "APPLY" else run_revert(run, args, world)
        unreal.log("S3_BACKDROP_V3_%s_OK|run=%s|map_saved=1|dirty_after=0+0|%s" %
                   (mode, run, json.dumps(result, sort_keys=True)))
    except Exception as exc:
        census = _census() if unreal is not None else {"content": [], "maps": []}
        unreal.log_error("S3_BACKDROP_V3_FAILED|run=%s|mode=%s|%s|census=%s|%s" %
                         (run, mode, str(exc).replace("\n", " "), json.dumps(census),
                          "NOTHING SAVED unless an _OK marker printed; if dirty, Don't-Save restart"
                          if mode != "DRY" else "DRY changed no Unreal package"))
        raise
