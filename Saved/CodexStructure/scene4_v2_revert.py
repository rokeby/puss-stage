"""Undo scene4_v2_apply.py, level side, from its plain-number record:
- level the root and move it back to the camera (the box returns to its v1
  place);
- detach the top-level hinges and delete the root and the apron;
- restore every hinge's prior relative rotation, the lattice height and the lamp
  intensities.
Saves the level. Scene 4 must be re-pointed first, with scene4_fold_nest_v1.py
(back to LS_S4_HangarFold, and a Master rebuild), so the Scene never plays a
sequence whose bindings no longer match. LS_S4_HangarRise is kept (unreferenced).
Refuses on PIE, dirty state, an open Sequencer, or Scene 4 still pointing at v2.
Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_v2_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    scene = unreal.load_asset(SCENE4)
    for t in scene.find_tracks_by_type(unreal.MovieSceneSubTrack):
        if str(t.get_display_name()) == "Hangar Fold":
            seq = t.get_sections()[0].get_sequence()
            assert seq is None or seq.get_path_name().split(".")[0] != rec["sequence"], \
                "Scene 4 still plays v2: run scene4_fold_nest_v1.py first"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    root = mine["S4 Hangar Root"]
    root.modify()
    root.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    root.set_actor_location(unreal.Vector(rec["mouth"][0], rec["mouth"][1], 0.0), False, True)
    for label in rec["top"]:
        mine[label].detach_from_actor(unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD)
    assert sub.destroy_actor(root), "root not deleted"
    if "S4 Hangar Apron" in mine:
        assert sub.destroy_actor(mine["S4 Hangar Apron"]), "apron not deleted"
    before = rec["before"]
    for label, (ro, pi, ya) in before["rel_rot"].items():
        mine[label].modify()
        mine[label].set_actor_relative_rotation(unreal.Rotator(roll=ro, pitch=pi, yaw=ya), False, True)
    fly = mine["S4 Hangar Lattice Fly"]
    loc = fly.get_actor_location()
    fly.set_actor_location(unreal.Vector(loc.x, loc.y, before["lattice_z"]), False, True)
    for label, cd in before["cd"].items():
        mine[label].get_component_by_class(unreal.LightComponent).set_editor_property("intensity", float(cd))
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(RECORD, RECORD + ".reverted")
    unreal.log("S4_V2_REVERTED|root=deleted|apron=deleted|rest=v1|level_saved=1")


main()
