"""Undo scene4_lattice_glow_apply.py from its plain record: delete only the glow lights it
created and put each beam/rail's recorded materials back. Save the level. Guards: world,
no PIE, 0+0 dirty, no Sequencer. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_lattice_glow_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    rec = json.load(open(RECORD, encoding="utf-8"))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by_label = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    deleted = 0
    for label in rec["created_lights"]:
        if label in by_label:
            assert sub.destroy_actor(by_label[label]), f"{label} not deleted"
            deleted += 1
    for label, paths in rec["materials_before"].items():
        a = by_label[label]
        a.modify()
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        for i, p in enumerate(paths):
            smc.set_material(i, unreal.load_asset(p) if p else None)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    os.replace(RECORD, RECORD + ".reverted")
    unreal.log(f"LATTICE_GLOW_REVERTED|deleted={deleted}|materials_restored={len(rec['materials_before'])}|level_saved=1")


main()
