"""Shared safety helpers for the offline-authored first-FX tools.

This module is importable by normal CPython so the planning harnesses can run
without Unreal.  Functions that need the editor import ``unreal`` lazily.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SAVED_MASTER_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"


class FxToolError(RuntimeError):
    """A deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise FxToolError(str(message))


def stamp_now():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def guid_text(value):
    for name in ("to_string", "ToString"):
        function = getattr(value, name, None)
        if callable(function):
            try:
                return str(function()).replace("-", "").upper()
            except Exception:  # noqa: BLE001 - Unreal wrapper variants differ.
                pass
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def enum_member(enum_type, *names):
    for name in names:
        if hasattr(enum_type, name):
            return getattr(enum_type, name)
    raise FxToolError("ENUM_MEMBER_MISSING|%s|%s" % (enum_type, ",".join(names)))


def dirty_census(unreal):
    def names(packages):
        return sorted(asset_id(package) for package in packages)

    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def editor_context(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None, "EDITOR_WORLD_MISSING")
    require(asset_id(world) == EXPECTED_WORLD,
            "WRONG_WORLD|expected=%s|actual=%s" % (EXPECTED_WORLD, asset_id(world)))
    return editor, world


def require_clean(unreal, label):
    census = dirty_census(unreal)
    require(census == {"content": [], "maps": []},
            "%s_DIRTY|census=%s" % (label, json.dumps(census, sort_keys=True)))
    return census


def package_file(unreal, package_path):
    require(package_path.startswith("/Game/"), "NON_GAME_PACKAGE|" + package_path)
    relative = package_path[len("/Game/"):].replace("/", os.sep) + ".uasset"
    return os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), relative))


def backup_packages(unreal, prefix, run, package_paths):
    """Copy exact packages to a new Backups folder and verify hashes."""
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup_root = os.path.join(project, "Backups", prefix + run)
    os.makedirs(backup_root, exist_ok=False)
    rows = []
    for package_path in package_paths:
        source = package_file(unreal, package_path)
        require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
        relative = package_path[len("/Game/"):].replace("/", os.sep) + ".uasset"
        destination = os.path.join(backup_root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        source_hash = sha256(source)
        destination_hash = sha256(destination)
        require(source_hash == destination_hash,
                "BACKUP_HASH_MISMATCH|package=" + package_path)
        rows.append({
            "package": package_path,
            "source": source,
            "backup": destination,
            "bytes": os.path.getsize(source),
            "sha256": source_hash,
        })
    return {"root": backup_root, "packages": rows}


def saved_dir(unreal):
    return os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor"))


def find_passage_actor(unreal, show, passage_number):
    prefix = "Passage %02d" % int(passage_number)
    actors = []
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if (actor.get_class().get_name() == "InfinityStagePassageActor"
                and actor.get_actor_label().startswith(prefix)
                and actor.get_editor_property("show_asset") == show):
            actors.append(actor)
    require(len(actors) == 1,
            "PASSAGE_ACTOR_COUNT|prefix=%s|count=%d" % (prefix, len(actors)))
    return actors[0]


def save_show_and_level(unreal):
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False),
            "SHOW_SAVE_FAILED")
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    require(level_subsystem.save_current_level(), "LEVEL_SAVE_FAILED")
    require_clean(unreal, "POST_SAVE")


def queue_saved_master_test(unreal, world, marker_prefix, run):
    require_clean(unreal, "PRE_SAVED_MASTER_TEST")
    command = "Automation RunTests " + SAVED_MASTER_TEST
    unreal.SystemLibrary.execute_console_command(world, command)
    unreal.log("%s_SAVED_MASTER_QUEUED|run=%s|test=%s|alone=true" %
               (marker_prefix, run, SAVED_MASTER_TEST))
    return command


def new_guid(unreal):
    for owner_name in ("GuidLibrary", "KismetGuidLibrary", "SystemLibrary"):
        owner = getattr(unreal, owner_name, None)
        function = getattr(owner, "new_guid", None) if owner else None
        if callable(function):
            value = function()
            validator = getattr(value, "is_valid", None)
            if callable(validator):
                require(bool(validator()), "NEW_GUID_INVALID")
            else:
                compact = "".join(character for character in guid_text(value)
                                  if character in "0123456789ABCDEF")
                require(any(character != "0" for character in compact), "NEW_GUID_INVALID")
            return value
    raise FxToolError("NEW_GUID_API_MISSING")


def transform_plain(transform):
    location = transform.translation
    rotation = transform.rotation.rotator()
    scale = transform.scale3d
    return {
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation_rpy": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def archive_record(path, run):
    archived = path + ".reverted-" + run
    os.rename(path, archived)
    return archived
