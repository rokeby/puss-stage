"""Undo p01_opening_apply.py exactly: remove every lamp whose label its revert
record lists (the opening light and the floats), re-materialize Passage 01 and
re-fit its structure, then save the Show and the level only. The apply adds and
never edits, so removing its labels restores the Show."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p01_opening_revert_record.json")


def fail(message):
    raise RuntimeError(f"P01_OPENING_REVERT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
record = json.load(open(RECORD, encoding="utf-8"))
remove = set(record["added_labels"])
if SHOW_PATH in dirty()[0]:
    fail("Show already dirty")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
show.modify()
cues = list(show.get_editor_property("cues"))
removed = 0
for i, cue in enumerate(cues):
    if str(cue.get_editor_property("label")) not in record["pairs"]:
        continue
    pair = cue.get_editor_property("wing_pair")
    atts = list(pair.get_editor_property("attachments"))
    kept = [a for a in atts if str(a.get_editor_property("label")) not in remove]
    removed += len(atts) - len(kept)
    pair.set_editor_property("attachments", kept)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
show.set_editor_property("cues", cues)
if removed != len(remove):
    fail(f"removed {removed} lamps, record lists {len(remove)}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 01 did not re-fit")
content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P01_OPENING_REVERT_OK|removed={removed}|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
