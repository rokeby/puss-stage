import os
import sys

import unreal


PROJECT_ROOT = unreal.Paths.project_dir()
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Scripts", "Unreal"))

import p166_scripted_safe_startup


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("JOB196_FINAL_REFUSED|pie=true")

world = editor.get_editor_world()
world_path = world.get_path_name() if world else "<none>"
expected = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
if not world_path.startswith(expected + "."):
    raise RuntimeError("JOB196_FINAL_REFUSED|world=%s" % world_path)

p166_scripted_safe_startup.apply_safe_settings("job196-final")

loading = unreal.EditorLoadingAndSavingUtils
dirty_maps = sorted(package.get_name() for package in loading.get_dirty_map_packages())
dirty_content = sorted(package.get_name() for package in loading.get_dirty_content_packages())
if dirty_maps or dirty_content:
    raise RuntimeError(
        "JOB196_FINAL_REFUSED|dirty_maps=%s|dirty_content=%s"
        % (dirty_maps, dirty_content)
    )

unreal.log(
    "JOB196_FINAL_STATE_OK|world=%s|pie=false|realtime=false|dirty_maps=0|dirty_content=0"
    % world_path
)
