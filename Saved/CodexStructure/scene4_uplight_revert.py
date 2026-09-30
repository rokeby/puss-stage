"""Undo scene4_uplight_apply.py:
- remove the uplights' bindings from LS_S4_HangarFold;
- delete every actor tagged RigAtmos.Scene4Uplight;
- delete M_RigAtmos_WorkBulb;
- save the fold and the level.

The hangar's own 64 actors are untouched. Refuses on PIE, dirty state or an
open Sequencer. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Uplight"
FOLD = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_uplight_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    fold = unreal.EditorAssetLibrary.load_asset(FOLD)
    removed = 0
    for b in list(fold.get_bindings()):
        if str(b.get_display_name()).startswith("S4 Uplight"):
            for child in list(b.get_child_possessables()):
                child.remove()
            b.remove()
            removed += 1
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = [a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]]
    deleted = sum(1 for a in mine if sub.destroy_actor(a))
    assert unreal.EditorAssetLibrary.save_asset(FOLD, only_if_is_dirty=False), "fold save failed"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    mat_deleted = unreal.EditorAssetLibrary.delete_asset(rec["material"]) if unreal.EditorAssetLibrary.does_asset_exist(rec["material"]) else False
    unreal.log(f"S4_UPLIGHT_REVERTED|bindings={removed}|actors={deleted}|material_deleted={mat_deleted}|saved=fold+level")


main()
