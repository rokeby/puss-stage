"""Undo scene4_lattice_glow_key.py: remove the glow lights' bindings (component and actor)
from LS_S4_HangarRise and put each glow light's recorded rest intensity back. Saves the
sequence and the level. Guards: world, no PIE, 0+0 dirty, no Sequencer. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_lattice_glow_key_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    seq = unreal.load_asset(SEQ)
    removed = 0
    for b in list(seq.get_bindings()):
        parent = b.get_parent() if hasattr(b, "get_parent") else None
        pname = str(parent.get_display_name()) if parent and parent.is_valid() else ""
        if pname.startswith("S4 Lattice Glow "):
            b.remove()
            removed += 1
    for b in list(seq.get_bindings()):
        if str(b.get_display_name()).startswith("S4 Lattice Glow "):
            b.remove()
            removed += 1
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by_label = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    for label, cd in rec["rest_cd_before"].items():
        by_label[label].get_component_by_class(unreal.PointLightComponent).set_editor_property("intensity", float(cd))
    assert unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False), "sequence save failed"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(RECORD, RECORD + ".reverted")
    unreal.log(f"LATTICE_GLOW_KEY_REVERTED|bindings_removed={removed}|rest_restored={len(rec['rest_cd_before'])}|saved=sequence+level")


main()
