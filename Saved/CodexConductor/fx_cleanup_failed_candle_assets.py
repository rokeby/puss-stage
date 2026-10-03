"""Discard only the three unsaved packages left by the failed candle build.

Fail closed before the first deletion unless PIE is off, the expected world is
open, every target is absent on disk, the dirty census is exact, and no package
outside this cleanup set refers to a target.  Nothing is saved.
"""
from __future__ import annotations

import datetime
import importlib
import json
import os
import sys

import unreal


# The embedded interpreter caches project-Saved modules between MCP calls.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SAVED = os.path.normcase(os.path.abspath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())))
for _name, _module in list(sys.modules.items()):
    _source = getattr(_module, "__file__", None) or ""
    if (_name != "__main__" and _source and
            os.path.normcase(os.path.abspath(_source)).startswith(_SAVED + os.sep)):
        sys.modules.pop(_name, None)
importlib.invalidate_caches()


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGETS = (
    "/Game/Scenes/Effects/MI_FX_CandleWax",
    "/Game/Scenes/Effects/M_FX_CandleFlame",
    "/Game/Scenes/Effects/M_FX_CandleWax",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_id(value):
    return str(value.get_path_name()).split(".", 1)[0]


def census():
    return {
        "content": sorted(asset_id(value) for value in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(asset_id(value) for value in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def disk_filename(package_path):
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    relative = package_path[len("/Game/"):].replace("/", os.sep)
    return os.path.normpath(os.path.join(content, relative + ".uasset"))


def loaded_asset(package_path):
    name = package_path.rsplit("/", 1)[-1]
    return unreal.find_object(None, package_path + "." + name)


def normalise_ref(value):
    return str(value).split(".", 1)[0]


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(world is not None and asset_id(world) == EXPECTED_WORLD,
        "WRONG_WORLD|actual=%s" % (asset_id(world) if world else None))

before = census()
expected = {"content": sorted(TARGETS), "maps": []}
require(before == expected,
        "CLEANUP_CENSUS_NOT_EXACT|expected=%s|actual=%s" %
        (json.dumps(expected, sort_keys=True), json.dumps(before, sort_keys=True)))

loaded = {}
external = {}
for path in TARGETS:
    require(not os.path.isfile(disk_filename(path)), "CLEANUP_ON_DISK|path=" + path)
    asset = loaded_asset(path)
    require(asset is not None, "CLEANUP_TARGET_NOT_LOADED|path=" + path)
    loaded[path] = asset
    refs = sorted({normalise_ref(value) for value in
                   unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)}
                  - set(TARGETS))
    if refs:
        external[path] = refs
require(not external, "CLEANUP_EXTERNAL_REFERENCER|refs=" +
        json.dumps(external, sort_keys=True))

# An absent-namespace manifest is the only possible backup for never-saved assets.
run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
backup_root = os.path.join(project, "Backups", "PreFxCandleCleanup-" + run)
os.makedirs(backup_root, exist_ok=False)
manifest = {
    "run": run,
    "world": EXPECTED_WORLD,
    "targets_absent_on_disk": list(TARGETS),
    "dirty_before": before,
    "outside_referencers": external,
    "save_policy": "no save path",
}
with open(os.path.join(backup_root, "manifest.json"), "x", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)

deleted = []
for path in TARGETS:  # MI first, then the two materials.
    require(not os.path.isfile(disk_filename(path)), "CLEANUP_ON_DISK|path=" + path)
    refs = sorted({normalise_ref(value) for value in
                   unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)}
                  - set(TARGETS))
    require(not refs, "CLEANUP_EXTERNAL_REFERENCER|path=%s|refs=%s" %
            (path, json.dumps(refs)))
    asset = loaded_asset(path)
    require(asset is not None, "CLEANUP_TARGET_NOT_LOADED|path=" + path)
    require(unreal.EditorAssetLibrary.delete_loaded_asset(asset),
            "CLEANUP_DELETE_FAIL|path=" + path)
    require(loaded_asset(path) is None and
            not unreal.EditorAssetLibrary.does_asset_exist(path),
            "CLEANUP_DELETE_READBACK_FAIL|path=" + path)
    deleted.append(path)

after = census()
require(after == {"content": [], "maps": []},
        "CLEANUP_CENSUS_NOT_EMPTY|actual=" + json.dumps(after, sort_keys=True))

report = {
    "ok": True,
    "run": run,
    "deleted": deleted,
    "backup": backup_root,
    "census": after,
}
report_path = os.path.join(_HERE, "fx_cleanup_failed_candle_assets_report.json")
with open(report_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
unreal.log("FX_CANDLE_FAILED_ASSETS_CLEANED|deleted=%d|order=%s|backup=%s|census=%s" %
           (len(deleted), ",".join(deleted), backup_root,
            json.dumps(after, separators=(",", ":"))))
