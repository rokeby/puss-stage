"""Undo groove_material_apply.py: restore each structure's RECORDED groove material and
bSteelGrooves (both exactly as the record holds them), re-fit, and require each
structure's groove_piece_count to equal its recorded count before saving the level only.
Until 30 Sep this wrote bSteelGrooves = False whatever the record said (the record holds
True everywhere): the same look (0 grooves) but not the recorded state, under a
"reverted" marker (revert audit, 30 Sep). If the recorded flags no longer rebuild the
recorded count (e.g. a later build draws grooves with no material), it REFUSES before
saving rather than choose between the flags and the look. Refuses on PIE or dirty state.
Lean: all work in main()."""
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
        g.set_editor_property("steel_grooves", bool(before["steel_grooves"]))
        a.set_editor_property("ground", g)
        assert a.materialize_structure(), f"{a.get_actor_label()} did not re-fit"
        got = a.get_editor_property("ground")
        mat = got.get_editor_property("groove_material")
        done[a.get_actor_label()] = [bool(a.is_structure_current()), int(a.get_editor_property("groove_piece_count")),
                                     bool(got.get_editor_property("steel_grooves")), mat.get_path_name().split(".")[0] if mat else None]
    want = {l: [True, rec["before"][l]["groove_piece_count"], bool(b["steel_grooves"]),
                b["groove_material"].split(".")[0] if b["groove_material"] else None] for l, b in rec["ground_before"].items()}
    assert len(done) == 6 and done == want, f"NOT saved: after revert {done}, recorded {want}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"GROOVE_MATERIAL_REVERTED|{done}|level_saved=1")


main()
