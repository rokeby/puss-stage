"""Undo mouth_lanterns_apply.py from its plain-number record: delete only the lanterns
the apply CREATED (tag RigAtmos.MouthLantern), restore any it updated to the recorded
values, save the level. Guards: world, no PIE, 0+0 dirty, no Sequencer. Lean: all work
in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "mouth_lanterns_record.json")
TAG = "RigAtmos.MouthLantern"


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    deleted = 0
    for label in rec["created"]:
        if label in mine:
            assert sub.destroy_actor(mine[label]), f"{label} not deleted"
            deleted += 1
    for label, b in rec.get("updated_before", {}).items():
        a = mine[label]
        a.modify()
        a.set_actor_location(unreal.Vector(*b["loc"]), False, True)
        a.set_actor_rotation(unreal.Rotator(roll=b["rot"][0], pitch=b["rot"][1], yaw=b["rot"][2]), True)
        c = a.get_component_by_class(unreal.SpotLightComponent)
        for k, p in (("cd", "intensity"), ("outer", "outer_cone_angle"), ("inner", "inner_cone_angle"), ("k", "temperature"),
                     ("radius", "attenuation_radius"), ("shadows", "cast_shadows")):
            c.set_editor_property(p, b[k])
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(RECORD, RECORD + ".reverted")
    unreal.log(f"MOUTH_LANTERNS_REVERTED|deleted={deleted}|restored={len(rec.get('updated_before', {}))}|level_saved=1")


main()
