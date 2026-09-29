"""Undo floors_to_stage_apply.py: put each slab's location and scale back from
the revert record, and save the level only. Like the apply, it tolerates Gary's
LS_DevScene_03 as the one foreign dirty package, never saving it."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOREIGN_OK = {"/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"}
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "floors_to_stage_revert_record.json")


def fail(message):
    raise RuntimeError(f"FLOORS_TO_STAGE_REVERT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
    fail("wrong world or PIE active")
content0 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
maps0 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
if content0 - FOREIGN_OK or maps0 - {EXPECTED_WORLD}:
    fail(f"unexpected dirty state: {content0} {maps0}")
record = json.load(open(RECORD, encoding="utf-8"))
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
found = {a.get_name(): a for a in sub.get_all_level_actors() if a.get_name() in record["slabs"]}
if sorted(found) != sorted(record["slabs"]):
    fail(f"slabs found {sorted(found)}")
for name, old in record["slabs"].items():
    a = found[name]
    a.modify()
    a.set_actor_location(unreal.Vector(*old["loc"]), False, False)
    a.set_actor_scale3d(unreal.Vector(*old["scale"]))
    tf = a.get_actor_transform()
    if abs(tf.translation.z - old["loc"][2]) > 0.01 or abs(tf.scale3d.z - old["scale"][2]) > 0.0001:
        fail(f"{name} did not restore")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
unreal.log(f"FLOORS_TO_STAGE_REVERT_OK|slabs={len(found)}|level_saved=1")
