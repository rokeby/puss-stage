"""Undo hangar_build.py for one scene (scene from hangar_revert_mode.json): delete every actor
tagged RigAtmos.Scene{N}Hangar that the build CREATED (the labels in its record, and only
those), and the sequence LS_S{N}_HangarRise it created. Refuses for Scene 4 (built by the
five-pass scripts, with its own revert chain), if the sequence is played by any Scene's
sequence (un-nest first), and on PIE, dirty state, an open Sequencer or ZZ_ actors.
Saves the level only after reading back that NO recorded actor is left and the sequence is
gone. The deleted count may be lower than the recorded count, because a child can go with its
parent (S2 rebuild, 30 Sep: 113 of 114), so the gate is absence, not the count. Lean: all
work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    n = json.load(open(os.path.join(HERE, "hangar_revert_mode.json"), encoding="utf-8"))["scene"]
    assert n != 4, "Scene 4 was built by the five-pass scripts: use scene4_v2_revert.py and its chain"
    record_path = os.path.join(HERE, f"hangar_s{n}_record.json")
    rec = json.load(open(record_path, encoding="utf-8"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith("ZZ_") for a in actors), "bench actors (ZZ_) in the level"
    referencers = [r for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(rec["sequence"], False)
                   if str(r) != rec["sequence"]]
    assert not referencers, f"{rec['sequence']} is referenced by {referencers}: un-nest it first, and if the level is a referencer, remove its Arrival (arrivals_revert_run.py)"
    tag = rec["tag"]
    created = set(rec["labels"])
    mine = [a for a in actors if tag in [str(t) for t in a.get_editor_property("tags")] and a.get_actor_label() in created]
    def depth(a):
        k, p = 0, a.get_attach_parent_actor()
        while p is not None:
            k, p = k + 1, p.get_attach_parent_actor()
        return k

    deleted = 0
    for a in sorted(mine, key=depth, reverse=True):      # children first, so nothing dangles mid-delete
        if sub.destroy_actor(a):
            deleted += 1
    left = [a.get_actor_label() for a in sub.get_all_level_actors()
            if tag in [str(t) for t in a.get_editor_property("tags")] and a.get_actor_label() in created]
    assert not left, f"NOT saved, level holds unsaved deletions: {len(left)} recorded actors survived, e.g. {left[:5]}"
    seq_deleted = unreal.EditorAssetLibrary.delete_asset(rec["sequence"])
    assert not unreal.EditorAssetLibrary.does_asset_exist(rec["sequence"]), f"NOT saved: {rec['sequence']} still exists"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(record_path, record_path + ".reverted")
    unreal.log(f"HANGAR_REVERTED|S{n}|deleted={deleted}/{len(created)}|sequence_deleted={seq_deleted}|level_saved=1")


main()
