"""Begin only the currently armed P04 lighting-look recording PIE."""
import json
import pathlib

import unreal


base = pathlib.Path("E:/PussStage/Saved/CodexConductor")
current = json.loads((base / "lighting_looks_current_run.json").read_text(encoding="utf-8"))
owner = json.loads((base / "pie_recording_owner.json").read_text(encoding="utf-8"))
if not owner.get("active") or owner.get("run_dir") != current.get("run_dir"):
    raise RuntimeError("lighting-look recording ownership is not armed for the current run")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is already active; refusing to begin another")
dirty_maps = [package.get_name() for package in
              unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
dirty_content = [package.get_name() for package in
                 unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
if dirty_maps or dirty_content:
    raise RuntimeError("editor census is not clean; refusing to begin PIE")
result = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("LIGHTING_LOOKS_BEGIN_OWNED_PLAY|run=%s|result=%s" %
           (current["run_id"], str(result)))
