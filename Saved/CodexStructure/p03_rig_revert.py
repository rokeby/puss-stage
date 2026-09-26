"""Undo p03_rig_apply.py exactly, from the revert record it wrote BEFORE mutating.

Removes every light whose label is "<P03 cue label> Rig ...", restores each
pre-existing P03 light's changed fields by attachment GUID, re-materializes
Passage 03 and its structure (so housings follow), then saves the Show and the
level only. Run inside a conductor-granted Show+level slot.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p03_rig_revert_record.json")


def fail(message):
    raise RuntimeError(f"P03_RIG_REVERT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def guid_str(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
record = json.load(open(RECORD, encoding="utf-8"))
content0, _ = dirty()
if SHOW_PATH in content0:
    fail("Show already dirty")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
show.modify()
cues = list(show.get_editor_property("cues"))
by_label = {str(c.get_editor_property("label")): i for i, c in enumerate(cues)}
removed = restored = 0
for cue_rec in record["cues"]:
    label = cue_rec["label"]
    if label not in by_label:
        fail(f"{label} is no longer in the Show")
    i = by_label[label]
    cue = cues[i]
    pair = cue.get_editor_property("wing_pair")
    fields_by_guid = {row["guid"]: row["fields"] for row in cue_rec["lights"]}
    kept = []
    for att in pair.get_editor_property("attachments"):
        if str(att.get_editor_property("label")).startswith(f"{label} Rig "):
            removed += 1
            continue
        fields = fields_by_guid.get(guid_str(att.get_editor_property("attachment_guid")))
        if fields is not None:
            L = att.get_editor_property("lighting")
            L.set_editor_property("intensity", float(fields["intensity"]))
            L.set_editor_property("cast_shadows", bool(fields["cast_shadows"]))
            L.set_editor_property("cast_volumetric_shadow", bool(fields["cast_volumetric_shadow"]))
            L.set_editor_property("volumetric_scattering_intensity", float(fields["volumetric_scattering_intensity"]))
            att.set_editor_property("lighting", L)
            restored += 1
        kept.append(att)
    pair.set_editor_property("attachments", kept)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
show.set_editor_property("cues", cues)
if restored != record["existing_lights"]:
    fail(f"restored {restored} lights, record holds {record['existing_lights']}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 03"))
if not passage.materialize_passage():
    fail("Passage 03 did not materialize")
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 03 did not re-fit")

content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P03_RIG_REVERT_OK|rig_removed={removed}|lights_restored={restored}"
           f"|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
