"""Shared helpers for the S6 bee-swarm editor scripts (Saved/CodexBeeSwarm).

Importable by plain CPython (offline harness/py_compile); `unreal` is passed in.
Rules these scripts follow (see Docs/BeeSwarmBuildRunbook_2026-10-04.md):
  * every success marker comes after ASSERTED returns, save and read-back;
  * no UE object is kept at module level (MCP Python re-runs crash on stale wrappers);
  * only NEW assets under /Game/Scenes/Effects/Swarm/ are created or saved;
  * never delete material expressions outside that folder;
  * never reload the open world; never end PIE.
"""
from __future__ import annotations

import datetime
import json
import os

SWARM_FOLDER = "/Game/Scenes/Effects/Swarm"
SHOW_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SANDBOX_MAP = SWARM_FOLDER + "/L_SwarmSandbox"
SWARM_ACTOR_CLASS = "/Script/InfinityStage.InfinityStageBeeSwarmActor"

MESH = SWARM_FOLDER + "/SM_Bee"
M_BODY = SWARM_FOLDER + "/M_Bee_Body"
M_WING = SWARM_FOLDER + "/M_Bee_Wing"
MI_BODY = SWARM_FOLDER + "/MI_Bee_Body"
MI_GLINT = SWARM_FOLDER + "/MI_Bee_Glint"
MI_WING = SWARM_FOLDER + "/MI_Bee_Wing"
NIAGARA_SYSTEM = SWARM_FOLDER + "/NS_BeeSwarm"

# User parameters the C++ component / actor write (names as in the v3 patch).
USER_POSITIONS = "User.BeePositions"      # Niagara "Position Array"
USER_VELOCITIES = "User.BeeVelocities"    # Niagara "Vector Array"
USER_BRIGHTNESS = "User.SwarmBrightness"  # float


class BeeSwarmError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise BeeSwarmError(str(message))


def stamp_now():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)


def asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def saved_dir(unreal):
    return os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexBeeSwarm"))


def dirty_census(unreal):
    def names(packages):
        return sorted(asset_id(p) for p in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def editor_world(unreal, allow_pie=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not allow_pie:
        require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE|stop PIE yourself; scripts never end PIE")
    world = editor.get_editor_world()
    require(world is not None, "EDITOR_WORLD_MISSING")
    return world


def exists(unreal, path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def save_exact(unreal, path):
    require(path.startswith(SWARM_FOLDER + "/"), "SAVE_OUTSIDE_SWARM_FOLDER|" + path)
    ok = unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    require(ok, "SAVE_FAILED|" + path)
    return path


def unwrap_out(value, count=1):
    """UE Python returns (ret, out...) for out-params; accept both shapes."""
    if isinstance(value, tuple):
        return value
    return (value,) + (None,) * count


def set_prop_any(obj, names, value):
    """Set the first property name that exists (UE strips/renames bool b-prefixes)."""
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return name
        except Exception as error:  # noqa: BLE001
            errors.append("%s:%s" % (name, error))
    raise BeeSwarmError("PROPERTY_MISSING|%s|%s" % (",".join(names), " ; ".join(errors)[:400]))


def get_prop_any(obj, names):
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:  # noqa: BLE001
            continue
    raise BeeSwarmError("PROPERTY_MISSING|" + ",".join(names))
