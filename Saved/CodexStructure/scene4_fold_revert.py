"""Undo scene4_fold_apply.py:
- stand the hangar back up if the pass left it resting packed (hinges to 0,
  lattice down, lamps back on);
- detach the practicals from the wall hinges (world positions unchanged);
- restore the hinge tags from the record;
- save the level;
- delete the fold sequence (an asset this pass created, nothing else).

Refuses on PIE or foreign dirty state. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_fold_revert_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    rec = json.load(open(RECORD, encoding="utf-8"))
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    # Look & camera may host their pitch camera as a subsequence INSIDE the fold, so the
    # fold's Time Scale retimes both. Deleting the fold would silently destroy their
    # section: refuse, and let the two streams agree first.
    fold = unreal.EditorAssetLibrary.load_asset(rec["sequence"]) if unreal.EditorAssetLibrary.does_asset_exist(rec["sequence"]) else None
    if fold and fold.find_tracks_by_type(unreal.MovieSceneSubTrack):
        raise RuntimeError("S4_FOLD_REVERT_REFUSED|the fold hosts another stream's subsequence (Look & camera's pitch); agree before deleting it")
    del fold
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    rest = rec.get("rest_pose")
    if rest:   # the level rests packed; stand it back up before undoing the rest
        for label, (axis, _packed) in rest["packed"].items():
            mine[label].modify()
            mine[label].set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
        fly = mine["S4 Hangar Lattice Fly"]
        fly.modify()
        loc = fly.get_actor_location()
        fly.set_actor_location(unreal.Vector(loc.x, loc.y, rest["lattice_standing_z"]), False, True)
        for label in rest["lamps"]:
            mine[label].modify()
            mine[label].get_component_by_class(unreal.SpotLightComponent).set_editor_property("intensity", float(rest["practical_cd"]))
    for label in rec["attached"]:
        mine[label].detach_from_actor(unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD,
                                      unreal.DetachmentRule.KEEP_WORLD)
    for label, tags in rec["tags_before"].items():
        mine[label].set_editor_property("tags", tags)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    deleted = False
    if unreal.EditorAssetLibrary.does_asset_exist(rec["sequence"]):
        deleted = unreal.EditorAssetLibrary.delete_asset(rec["sequence"])
    unreal.log(f"S4_FOLD_REVERTED|detached={len(rec['attached'])}|tags={len(rec['tags_before'])}"
               f"|sequence_deleted={deleted}|level_saved=1")


main()
