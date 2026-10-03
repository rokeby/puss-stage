"""Begin only the Flat V3 ST PIE session whose owner/current files were armed."""
import json
import pathlib

import unreal


CONDUCTOR = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = CONDUCTOR / "pie_recording_current_run.json"
OWNER = CONDUCTOR / "pie_recording_owner.json"

current = json.loads(CURRENT.read_text(encoding="utf-8"))
owner = json.loads(OWNER.read_text(encoding="utf-8"))
if current.get("kind") != "flatv3_st_pie_stills":
    raise RuntimeError("ST_PIE_CURRENT_RUN_KIND_FAIL")
if (not owner.get("active") or owner.get("kind") != "flatv3_st_pie_stills" or
        owner.get("run_dir") != current.get("run_dir") or
        owner.get("run_id") != current.get("run_id")):
    raise RuntimeError("ST_PIE_OWNERSHIP_NOT_ARMED")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    unreal.log_error("ST_PIE_BEGIN_ABORT_PREEXISTING_PIE run=" + current["run_id"])
    raise RuntimeError("ST_PIE_ALREADY_RUNNING")
dirty_maps = [value.get_name() for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
dirty_content = [value.get_name() for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
if dirty_maps or dirty_content:
    raise RuntimeError("ST_PIE_BEGIN_DIRTY_CENSUS")
result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log(
    "FLATV3_ST_PIE_BEGIN_OWNED run=%s mode=PlayMode_InEditorFloating "
    "api=LevelEditorSubsystem.editor_request_begin_play result=%s"
    % (current["run_id"], str(result))
)
