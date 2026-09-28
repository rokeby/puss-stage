"""Undo p01_station1_symmetry_apply.py: put P01 Wing 001's Right panel back to its
recorded y, re-materialize Passage 01, and save only the Show and the level."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p01_station1_symmetry_record.json")


def fail(message):
    raise RuntimeError(f"P01_STATION1_REVERT_FAILED|{message}")


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
record = json.load(open(RECORD, encoding="utf-8"))
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
show.modify()
cues = list(show.get_editor_property("cues"))
index = next(i for i, c in enumerate(cues) if str(c.get_editor_property("label")) == record["cue"])
pair = cues[index].get_editor_property("wing_pair")
right = pair.get_editor_property("right")
t = right.get_editor_property("local_transform")
right.set_editor_property("local_transform", unreal.Transform(
    location=unreal.Vector(t.translation.x, float(record["right_local_y_before"]), t.translation.z),
    rotation=t.rotation.rotator(), scale=t.scale3d))
pair.set_editor_property("right", right)
cue = cues[index]
cue.set_editor_property("wing_pair", pair)
cues[index] = cue
show.set_editor_property("cues", cues)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.is_structure_current() and not a.materialize_structure():
            fail("Structure 01 did not re-fit")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
unreal.log(f"P01_STATION1_REVERT_OK|cue={record['cue']}|right_y={record['right_local_y_before']}")
