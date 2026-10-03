"""Shared fail-closed helpers for Flat V3 slot SK (not executed offline)."""

from __future__ import annotations

import glob
import importlib.util
import json
import os
import re

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.dirname(os.path.abspath(__file__))
SAVED_FLAT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "run_sk.json")
CLEAN = {"content": [], "maps": []}
KINDS = ("SkinColor", "SkinMask", "SkinNormal")
PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")
TEXTURE_MATCH_PROPERTIES = (
    "size",
    "lod_group",
    "never_stream",
    "compression_settings",
    "srgb",
    "mip_gen_settings",
    "virtual_texture_streaming",
)


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
    if value.get("apply_run_id") != "FV3SK-20261003-02":
        raise RuntimeError("SK_APPLY_RUN_ID_FAIL")
    if value.get("revert_run_id") != "FV3SKR-20261003-02":
        raise RuntimeError("SK_REVERT_RUN_ID_FAIL")
    if value.get("import_status") != "DONE":
        raise RuntimeError("SK_IMPORT_STATUS_FAIL")
    if value.get("import_success_marker") != (
            "FLATV3_SK_IMPORT_OK run=" + value["import_run_id"]):
        raise RuntimeError("SK_IMPORT_MARKER_CONFIG_FAIL")
    if value.get("workflow") != ["apply_batches", "verify"]:
        raise RuntimeError("SK_WORKFLOW_FAIL")
    if value.get("texture_match_properties") != list(TEXTURE_MATCH_PROPERTIES):
        raise RuntimeError("SK_TEXTURE_MATCH_PROPERTIES_FAIL")
    if value.get("settings_fix_required") is not False:
        raise RuntimeError("SK_SETTINGS_FIX_STATE_FAIL")
    batches = value.get("apply_batches", [])
    if [batch.get("passage") for batch in batches] != list(PASSAGES):
        raise RuntimeError("SK_BATCH_ORDER_FAIL")
    rows = value.get("rows", [])
    textures = {path for row in rows for path in row["new_textures"].values()}
    names = [row["mi"].rsplit("/", 1)[-1] for row in rows]
    if len(set(names)) != len(names):
        raise RuntimeError("SK_CONFIG_DUPLICATE_MI_NAME|" + ",".join(sorted({n for n in names if names.count(n) > 1})))
    for row in rows:
        # MI_FlatV3_P04_... must live under .../Passage04/... (3 Oct: P04 MIs reused by
        # P02 were mis-attributed to Passage02).
        name = row["mi"].rsplit("/", 1)[-1]
        passage = name.split("_")[2] if name.startswith("MI_FlatV3_P") else None
        if passage and ("/Passage" + passage[1:3] + "/") not in row["mi"]:
            raise RuntimeError("SK_CONFIG_MI_PASSAGE_MISMATCH|" + row["mi"])
    if len(rows) != int(value.get("mi_count", -1)) or len(textures) != int(value.get("new_texture_count", -1)):
        raise RuntimeError(
            "SK_CONFIG_COUNT_FAIL|mis=%d|textures=%d" % (len(rows), len(textures))
        )
    for batch in batches:
        passage_rows = [row for row in rows if row.get("passage") == batch["passage"]]
        passage_textures = {
            row["new_textures"][kind] for row in passage_rows for kind in KINDS
        }
        if (len(passage_rows) != int(batch.get("mi_count", -1)) or
                len(passage_textures) != int(batch.get("texture_count", -1))):
            raise RuntimeError(
                "SK_BATCH_COUNT_FAIL|passage=%s|mis=%d|textures=%d"
                % (batch["passage"], len(passage_rows), len(passage_textures))
            )
    return value


def batch(cfg, passage):
    for ordinal, value in enumerate(cfg["apply_batches"], 1):
        if value["passage"] == passage:
            return ordinal, value
    raise RuntimeError("SK_UNKNOWN_PASSAGE|passage=" + str(passage))


def rows_for_passage(cfg, passage):
    batch(cfg, passage)
    rows = [row for row in cfg["rows"] if row.get("passage") == passage]
    if not rows:
        raise RuntimeError("SK_EMPTY_BATCH|passage=" + passage)
    return rows


def completed_passages_before(cfg, passage):
    ordinal, _value = batch(cfg, passage)
    return [value["passage"] for value in cfg["apply_batches"][:ordinal - 1]]


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


def planned_texture_pairs(rows):
    result = {}
    for row in rows:
        for kind in KINDS:
            destination = row["new_textures"][kind]
            value = (row["old_textures"][kind], kind)
            previous = result.get(destination)
            if previous is not None and previous != value:
                raise RuntimeError(
                    "SK_TEXTURE_PAIR_CONFLICT|path=%s|first=%s|second=%s"
                    % (destination, previous, value)
                )
            result[destination] = value
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


def require_run_open(run):
    token = "FLATV3_SLOT_RELEASED run=%s" % run
    result = scan_logs(token)
    if result["hits"]:
        raise RuntimeError("SK_RUN_ALREADY_RELEASED|" + json.dumps(result, sort_keys=True))
    return result


def require_token_unused(token):
    result = scan_logs(token)
    if result["hits"]:
        raise RuntimeError("SK_TOKEN_ALREADY_IN_LOGS|" + json.dumps(result, sort_keys=True))
    return result


def batch_success_token(run, passage):
    return "FLATV3_SK_APPLY_BATCH_OK passage=%s run=%s" % (passage, run)


def require_batch_marker(run, passage):
    token = batch_success_token(run, passage)
    result = scan_logs(token)
    if not result["hits"]:
        raise RuntimeError("SK_REQUIRED_BATCH_MARKER_MISSING|token=" + token)
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


def saved_texture_profile(asset_path):
    if not asset_path.startswith("/Game/"):
        raise RuntimeError("SK_TEXTURE_NOT_GAME_ASSET|path=" + asset_path)
    package_file = os.path.join(
        unreal.Paths.project_content_dir(),
        asset_path[len("/Game/"):].replace("/", os.sep) + ".uasset",
    )
    if not os.path.isfile(package_file):
        raise RuntimeError("SK_TEXTURE_PACKAGE_MISSING|path=" + package_file)
    with open(package_file, "rb") as stream:
        text = stream.read().decode("latin-1")
    specs = {
        "size": ("Dimensions", r"[0-9]+x[0-9]+"),
        "lod_group": ("LODGroup", r"TEXTUREGROUP_[A-Za-z0-9_]+"),
        "never_stream": ("NeverStream", r"True|False"),
        "compression_settings": ("CompressionSettings", r"TC_[A-Za-z0-9_]+"),
        "srgb": ("SRGB", r"True|False"),
        "mip_gen_settings": ("MipGenSettings", r"TMGS_[A-Za-z0-9_]+"),
        "virtual_texture_streaming": (
            "VirtualTextureStreaming", r"True|False"
        ),
    }
    result = {}
    for key, (label, pattern) in specs.items():
        parsed = []
        for match in re.finditer(re.escape(label), text):
            segment = re.sub(
                r"[^\x20-\x7e]", ".", text[match.start():match.start() + 240]
            )
            value = re.search(
                re.escape(label) + r"\.+(" + pattern + r")", segment
            )
            if value:
                parsed.append(value.group(1))
        if not parsed:
            raise RuntimeError(
                "SK_TEXTURE_PACKAGE_TAG_FAIL|asset=%s|tag=%s" % (asset_path, label)
            )
        result[key] = parsed[-1]
    return result


def verify_texture_pair(original_path, replacement_path, kind):
    original = load_asset(original_path, unreal.Texture2D)
    replacement = load_asset(replacement_path, unreal.Texture2D)
    verify_texture(original, kind)
    verify_texture(replacement, kind)
    # Saved package metadata is stable while runtime size getters can report a
    # temporary 32x32 placeholder during async texture compilation/streaming.
    original_profile = saved_texture_profile(original_path)
    replacement_profile = saved_texture_profile(replacement_path)
    if original_profile != replacement_profile:
        raise RuntimeError(
            "SK_TEXTURE_PROFILE_MISMATCH|old=%s|new=%s|old_profile=%s|new_profile=%s"
            % (original_path, replacement_path,
               json.dumps(original_profile, sort_keys=True),
               json.dumps(replacement_profile, sort_keys=True))
        )
    return {"old": original_path, "new": replacement_path,
            "kind": kind, "profile": replacement_profile}


def gpu_memory_guard():
    # UE 5.8 exposes texture-memory data to native RHI code, but no supported
    # unreal.SystemLibrary/Python getter returns current D3D12 budget or usage.
    # Do not substitute a console command: its text is not a synchronous,
    # machine-readable guard.  Passage batching plus GC is the available guard.
    return {
        "available": False,
        "action": "PASSAGE_BATCH_PLUS_COLLECT_GARBAGE",
        "reason": "NO_SUPPORTED_PYTHON_GPU_MEMORY_BUDGET_GETTER",
    }


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

