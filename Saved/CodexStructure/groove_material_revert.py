"""Undo groove_material_apply.py: restore each structure's recorded groove material
and turn bSteelGrooves OFF, so the floor looks as it did before the build (no
grooves), rather than leaving grooves in the default material. Then re-fit and
save the level only. Refuses on PIE or dirty state. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "groove_material_revert_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    rec = json.load(open(RECORD, encoding="utf-8"))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    done = {}
    for a in sub.get_all_level_actors():
        if not isinstance(a, unreal.InfinityStageStructureActor) or a.get_actor_label() not in rec["ground_before"]:
            continue
        before = rec["ground_before"][a.get_actor_label()]
        a.modify()
        g = a.get_editor_property("ground")
        g.set_editor_property("groove_material",
                              unreal.EditorAssetLibrary.load_asset(before["groove_material"]) if before["groove_material"] else None)
        g.set_editor_property("steel_grooves", False)
        a.set_editor_property("ground", g)
        assert a.materialize_structure(), f"{a.get_actor_label()} did not re-fit"
        done[a.get_actor_label()] = [bool(a.is_structure_current()), int(a.get_editor_property("groove_piece_count"))]
    assert len(done) == 6 and all(v[0] and v[1] == 0 for v in done.values()), f"after revert: {done}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"GROOVE_MATERIAL_REVERTED|{done}|level_saved=1")


main()
