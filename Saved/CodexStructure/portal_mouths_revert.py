"""Undo portal_mouths_apply.py: switch the portals on Structures 02-06 back off,
re-fit, check each structure against its recorded counts, and save the level
only. The pass is deterministic, so the re-fit restores the record; the
Backups/PrePortalMouths-* umap is the fallback. Lean: all work in main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "portal_mouths_revert_record.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "the map is already dirty"
    rec = json.load(open(RECORD, encoding="utf-8"))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    structures = {a.get_actor_label()[-2:]: a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)}
    for k in rec["targets"]:
        a = structures[k]
        a.modify()
        portal = a.get_editor_property("portal")
        portal.set_editor_property("enabled", False)
        a.set_editor_property("portal", portal)
        assert a.materialize_structure(), f"Structure {k} did not re-fit"
        want = rec["before"][k]
        got = {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in want if c != "current"}}
        assert got == want, f"Structure {k} not restored, NOT saved: {want} vs {got}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"PORTAL_MOUTHS_REVERTED|targets={rec['targets']}|level_saved=1")


main()
