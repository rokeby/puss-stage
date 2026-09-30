"""Undo floors_above_boards_apply.py: put the three slabs back at the recorded
location (under the boards), and save the level only."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "floors_above_boards_revert_record.json")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "foreign dirty content"
# No record means nothing to revert: the apply writes its record before any mutation (even on a dry run),
# so it never ran. Held, not applied (handover, 28 Sep; revert audit, 30 Sep).
assert os.path.exists(RECORD), "NOTHING TO REVERT: no record, so floors_above_boards_apply.py never ran"
record = json.load(open(RECORD, encoding="utf-8"))
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
found = {a.get_name(): a for a in sub.get_all_level_actors() if a.get_name() in record["slabs"]}
assert sorted(found) == sorted(record["slabs"]), f"slabs found {sorted(found)}"
for name, old in record["slabs"].items():
    found[name].modify()
    found[name].set_actor_location(unreal.Vector(*old["loc"]), False, False)
    found[name].set_actor_scale3d(unreal.Vector(*old["scale"]))
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
unreal.log(f"FLOORS_ABOVE_REVERT_OK|slabs={len(found)}|level_saved=1")
