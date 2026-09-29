"""Undo top_down_enable_apply.py: restore each targeted attachment's enabled,
cast_shadows and cast_volumetric_shadow flags from the revert record (by GUID),
re-materialize every passage, re-fit every structure, and save the Show and the
level only."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "top_down_enable_revert_record.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "foreign dirty content"
record = json.load(open(RECORD, encoding="utf-8"))
old = {t["guid"]: t for t in record["targets"]}
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
show.modify()
cues = list(show.get_editor_property("cues"))
restored = 0
for ci, cue in enumerate(cues):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
        continue
    pair = cue.get_editor_property("wing_pair")
    atts = list(pair.get_editor_property("attachments"))
    changed = False
    for ai, att in enumerate(atts):
        t = old.get(unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid")))
        if not t:
            continue
        L = att.get_editor_property("lighting")
        L.set_editor_property("cast_shadows", t["cast_shadows"])
        L.set_editor_property("cast_volumetric_shadow", t["cast_volumetric_shadow"])
        att.set_editor_property("lighting", L)
        att.set_editor_property("enabled", t["enabled"])
        atts[ai] = att
        restored += 1
        changed = True
    if changed:
        pair.set_editor_property("attachments", atts)
        cue.set_editor_property("wing_pair", pair)
        cues[ci] = cue
show.set_editor_property("cues", cues)
assert restored == len(old), f"restored {restored} of {len(old)}"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for p in (a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStagePassageActor)):
    assert p.materialize_passage(), f"{p.get_actor_label()} did not materialize"
for s in (a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)):
    assert s.materialize_structure(), f"{s.get_actor_label()} did not re-fit"
assert unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "Show save failed"
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
unreal.log(f"TOP_DOWN_REVERT_OK|restored={restored}|show_saved=1|level_saved=1")
