"""Shared fail-closed helpers for Flat V3 slot SK (not executed offline)."""

from __future__ import annotations

import glob
import importlib.util
import json
import os

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.dirname(os.path.abspath(__file__))
SAVED_FLAT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "run_sk.json")
CLEAN = {"content": [], "maps": []}
KINDS = ("SkinColor", "SkinMask", "SkinNormal")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot = load_module("fv3_sk_phase1_library", os.path.join(SAVED_FLAT, "phase1_import.py"))
cleanup_mod = load_module(
    "fv3_sk_import_failure_cleanup", os.path.join(HERE, "import_failure_cleanup.py")
)


def config(path=None):
    with open(path or CONFIG_PATH, encoding="utf-8") as stream:
        value = json.load(stream)
    if value.get("slot") != "SK":
        raise RuntimeError("SK_CONFIG_SLOT_FAIL")
    if value.get("import_run_id") != "FV3SKI-20261003-01":
        raise RuntimeError("SK_IMPORT_RUN_ID_FAIL")
    if value.get("apply_run_id") != "FV3SK-20261003-01":
        raise RuntimeError("SK_APPLY_RUN_ID_FAIL")
    if value.get("workflow") != ["import", "apply", "verify"]:
        raise RuntimeError("SK_WORKFLOW_FAIL")
    rows = value.get("rows", [])
    textures = {path for row in rows for path in row["new_textures"].values()}
    if len(rows) != 136 or len(textures) != 204:
        raise RuntimeError(
            "SK_CONFIG_COUNT_FAIL|mis=%d|textures=%d" % (len(rows), len(textures))
        )
    return value


def planned_textures(cfg):
    result = {}
    for row in cfg["rows"]:
        for kind in KINDS:
            destination = row["new_textures"][kind]
            value = (row["sources"][kind], kind)
            previous = result.get(destination)
            if previous is not None and previous != value:
                raise RuntimeError(
                    "SK_TEXTURE_MAPPING_CONFLICT|path=%s|first=%s|second=%s"
                    % (destination, previous, value)
                )
            result[destination] = value
    if len(result) != int(cfg["new_texture_count"]):
        raise RuntimeError("SK_PLANNED_TEXTURE_COUNT_FAIL")
    return result


def census():
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def assert_context(clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actual = world.get_outermost().get_name() if world else None
    if actual != WORLD:
        raise RuntimeError("WRONG_WORLD|expected=%s|actual=%s" % (WORLD, actual))
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    current = census()
    if clean and current != CLEAN:
        raise RuntimeError("DIRTY_AT_START|" + json.dumps(current, sort_keys=True))
    return editor, world


def log_paths():
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return sorted(glob.glob(os.path.join(saved, "Logs", "PussStage*.log")))


def scan_logs(token):
    hits = []
    paths = log_paths()
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as stream:
                for number, line in enumerate(stream, 1):
                    if token in line:
                        hits.append({
                            "file": os.path.basename(path),
                            "line": number,
                            "text": line.strip(),
                        })
        except OSError as exc:
            raise RuntimeError("SK_LOG_READ_FAIL|path=%s|reason=%s" % (path, exc))
    return {"token": token, "logs_scanned": [os.path.basename(path) for path in paths],
            "hits": hits}


def require_run_unused(run):
    result = scan_logs(run)
    if result["hits"]:
        raise RuntimeError("SK_RUN_ID_ALREADY_IN_LOGS|" + json.dumps(result, sort_keys=True))
    return result


def require_marker(marker, run):
    token = "%s run=%s" % (marker, run)
    result = scan_logs(token)
    if not result["hits"]:
        raise RuntimeError("SK_REQUIRED_MARKER_MISSING|token=" + token)
    return result


def load_asset(path, expected_type=None):
    value = unreal.EditorAssetLibrary.load_asset(path)
    if value is None or (expected_type is not None and not isinstance(value, expected_type)):
        raise RuntimeError("ASSET_LOAD_FAIL|path=" + path)
    return value


def texture_settings(texture, kind):
    pilot.configure_texture(texture, kind)
    return pilot.verify_texture(texture, kind)


def verify_texture(texture, kind):
    return pilot.verify_texture(texture, kind)


def mi_textures(instance):
    return pilot.serialized_texture_parameters(instance)


def assert_texture_map(actual, expected, label):
    if actual != expected:
        raise RuntimeError(
            "MI_TEXTURE_READBACK_FAIL|label=%s|expected=%s|actual=%s"
            % (label, json.dumps(expected, sort_keys=True), json.dumps(actual, sort_keys=True))
        )
    return actual


def assert_mi(instance, expected, label):
    actual = mi_textures(instance)
    relevant = {name: actual.get(name) for name in KINDS}
    return assert_texture_map(relevant, expected, label)


def set_mi_textures(instance, texture_paths):
    instance.modify()
    for parameter in KINDS:
        texture = load_asset(texture_paths[parameter], unreal.Texture2D)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, parameter, texture
        )
    unreal.MaterialEditingLibrary.update_material_instance(instance)


def save_exact(paths):
    saved = []
    for path in sorted(set(paths)):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True):
            raise RuntimeError("SAVE_FAIL|path=" + path)
        saved.append(path)
    return saved


def reload_exact(paths):
    packages = []
    for path in sorted(set(paths)):
        packages.append(load_asset(path).get_outermost())
    success, error = unreal.EditorLoadingAndSavingUtils.reload_packages(
        packages, unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE
    )
    if not success:
        raise RuntimeError("TARGET_RELOAD_FAIL|error=" + str(error))


def write_report(name, value):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def release(run, status, saved, phase, reason=None):
    current = census()
    if reason is not None:
        unreal.log_error(
            "FLATV3_SK_%s_FAIL run=%s reason=%s census=%s"
            % (phase.upper(), run, str(reason).replace("\n", "\\n"),
               json.dumps(current, separators=(",", ":"), sort_keys=True))
        )
    unreal.log(
        "FLATV3_SLOT_RELEASED run=%s slot=SK phase=%s status=%s saved_count=%d "
        "saved_roots=%s census=%s"
        % (run, phase, status, len(set(saved)),
           json.dumps(sorted(set(saved)), separators=(",", ":")),
           json.dumps(current, separators=(",", ":"), sort_keys=True))
    )

