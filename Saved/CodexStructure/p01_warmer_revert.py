"""Undo p01_warmer_apply.py exactly: remove the lamps its revert record lists,
re-enable the lamps it disabled, re-materialize Passage 01, re-fit its structure,
and save only the Show and the level."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p01_warmer_revert_record.json")


def fail(message):
    raise RuntimeError(f"P01_WARMER_REVERT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
record = json.load(open(RECORD, encoding="utf-8"))
remove = set(record["added_labels"])
enable = set(record["disabled_labels"])
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
show.modify()
cues = list(show.get_editor_property("cues"))
removed = enabled = 0
for i, cue in enumerate(cues):
    if str(cue.get_editor_property("label")) not in record["pairs"]:
        continue
    pair = cue.get_editor_property("wing_pair")
    kept = []
    for att in pair.get_editor_property("attachments"):
        name = str(att.get_editor_property("label"))
        if name in remove:
            removed += 1
            continue
        if name in enable:
            att.set_editor_property("enabled", True)
            enabled += 1
        kept.append(att)
    pair.set_editor_property("attachments", kept)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
show.set_editor_property("cues", cues)
if removed != len(remove) or enabled != len(enable):
    fail(f"removed {removed}/{len(remove)}, re-enabled {enabled}/{len(enable)}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 01 did not re-fit")
c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if set(c1) - {SHOW_PATH} or set(m1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {c1} {m1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
unreal.log(f"P01_WARMER_REVERT_OK|removed={removed}|re_enabled={enabled}")
