"""Undo scene4_floor_rise_apply.py, from its plain-number record:
- restore slab 3's old keys (+90 -> 0 over 1-4 s);
- remove slab 2's binding from the fold;
- detach the ghost light;
- return the hinges to the old rest (slab 2 flat, slab 3 +90) and their tags;
- put the fold record's rest pose and attachments back.
Saves the fold and the level. Refuses on PIE, dirty state or an open Sequencer.
Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
FOLD = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
FOLD_RECORD = os.path.join(HERE, "scene4_fold_revert_record.json")
RECORD = os.path.join(HERE, "scene4_floor_rise_record.json")
FPS = 30
SLAB2, SLAB3 = "S4 Hangar Floor 2 Hinge", "S4 Hangar Floor 3 Hinge"
GHOST = ("S4 Ghost Light Stand", "S4 Ghost Light Bulb", "S4 Ghost Light")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    fold = unreal.EditorAssetLibrary.load_asset(FOLD)
    for b in list(fold.get_bindings()):
        name = str(b.get_display_name())
        if name == SLAB2:
            b.remove()
        elif name == SLAB3:
            for track in b.get_tracks():
                if isinstance(track, unreal.MovieScene3DTransformTrack):
                    ch = track.get_sections()[0].get_all_channels()[4]
                    for k in list(ch.get_keys()):
                        ch.remove_key(k)
                    for t_s, v in rec["before"]["slab3_keys"]:
                        ch.add_key(unreal.FrameNumber(int(round(t_s * FPS))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                   interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    # Flatten slab 2 first, so the ghost light detaches at its original world position.
    mine[SLAB2].modify()
    mine[SLAB2].set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    for g in GHOST:
        mine[g].detach_from_actor(unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD, unreal.DetachmentRule.KEEP_WORLD)
    mine[SLAB3].modify()
    mine[SLAB3].set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=float(rec["before"]["rest"][SLAB3]), yaw=0.0), False, True)
    for label, tags in rec["before"]["tags"].items():
        mine[label].set_editor_property("tags", tags)
    fold_rec = json.load(open(FOLD_RECORD, encoding="utf-8"))
    fold_rec["rest_pose"]["packed"].pop(SLAB2, None)
    fold_rec["rest_pose"]["packed"][SLAB3] = ["Y", float(rec["before"]["rest"][SLAB3])]
    for g in GHOST:
        fold_rec["attached"].pop(g, None)
    json.dump(fold_rec, open(FOLD_RECORD, "w", encoding="utf-8"), indent=1)
    assert unreal.EditorAssetLibrary.save_asset(FOLD, only_if_is_dirty=False), "fold save failed"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(RECORD, RECORD + ".reverted")
    unreal.log("FLOOR_RISE_REVERTED|saved=fold+level")


main()
