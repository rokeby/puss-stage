"""Undo board_material_apply.py: put each structure's old Ground.BoardMaterial back
(None = the mesh's own), re-fit, and save the level only. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "board_material_revert_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "foreign dirty content"
    record = json.load(open(RECORD, encoding="utf-8"))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    done = 0
    for s in sub.get_all_level_actors():
        if not isinstance(s, unreal.InfinityStageStructureActor) or s.get_actor_label() not in record["structures"]:
            continue
        old = record["structures"][s.get_actor_label()]["old_board_material"]
        s.modify()
        ground = s.get_editor_property("ground")
        ground.set_editor_property("board_material", unreal.EditorAssetLibrary.load_asset(old.split(".")[0]) if old else None)
        s.set_editor_property("ground", ground)
        assert s.materialize_structure(), f"{s.get_actor_label()} did not re-fit"
        done += 1
    assert done == len(record["structures"]), f"restored {done} of {len(record['structures'])}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"BOARD_MATERIAL_REVERT_OK|structures={done}|level_saved=1")


main()
