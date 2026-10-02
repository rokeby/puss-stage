"""READ-ONLY preflight for Gary's don't-save editor close.

No setters, saves, reloads, deletes, or quit calls are made here.
"""
import json

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
EXPECTED = {
    "content": [
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow1_A",
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow1_B",
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow2_A",
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow2_B",
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow3_A",
        "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow3_B",
    ],
    "maps": [EXPECTED_WORLD],
}


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_outermost().get_name() if world is not None else None
pie = editor.get_game_world() is not None
census = {
    "content": sorted(
        package.get_name()
        for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    ),
    "maps": sorted(
        package.get_name()
        for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    ),
}

package_members = sorted(
    name for name in dir(unreal.Package)
    if "dirty" in name.lower() or "clear" in name.lower()
)
set_dirty = getattr(unreal.Package, "set_dirty_flag", None)
is_dirty = getattr(unreal.Package, "is_dirty", None)
quit_editor = getattr(unreal.SystemLibrary, "quit_editor", None)
api_report = {
    "Package.has_set_dirty_flag": hasattr(unreal.Package, "set_dirty_flag"),
    "Package.has_is_dirty": hasattr(unreal.Package, "is_dirty"),
    "Package.dirty_or_clear_members": package_members,
    "Package.set_dirty_flag_doc": getattr(set_dirty, "__doc__", None),
    "Package.is_dirty_doc": getattr(is_dirty, "__doc__", None),
    "SystemLibrary.quit_editor_doc": getattr(quit_editor, "__doc__", None),
}

unreal.log(
    "GRACEFUL_CLOSE_PROBE|pie=%s|world=%s|census=%s|api=%s"
    % (
        "true" if pie else "false",
        world_path,
        compact(census),
        compact(api_report),
    )
)

if pie:
    raise RuntimeError("GRACEFUL_CLOSE_STOP|PIE_OR_SIE_ACTIVE")
if world_path != EXPECTED_WORLD:
    raise RuntimeError("GRACEFUL_CLOSE_STOP|WRONG_WORLD|%s" % world_path)
if census != EXPECTED:
    raise RuntimeError("GRACEFUL_CLOSE_STOP|UNEXPECTED_CENSUS|%s" % compact(census))

unreal.log("GRACEFUL_CLOSE_PROBE_OK|expected_7_packages=true")
