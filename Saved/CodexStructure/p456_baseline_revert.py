"""Undo p456_baseline_apply.py: restore every rewritten attachment's enabled flag,
relative transform and light fields from the revert record (by GUID), then
materialize P04, P05 and P06, re-fit their structures, and save the Show and the
level only. Lean, like the apply: all work inside main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p456_baseline_revert_record.json")


def enum_value(enum_cls, text):
    name = text.split(".")[-1].split(":")[0].strip("<> ")
    return getattr(enum_cls, name)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "foreign dirty content"
    record = json.load(open(RECORD, encoding="utf-8"))
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    show.modify()
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for guid, rec in record["rows"].items():
        by_cue.setdefault(rec["cue_index"], []).append((guid, rec))   # labels repeat in P05; use the index
    restored = 0
    for ci, items in by_cue.items():
        cue = cues[ci]
        label = str(cue.get_editor_property("label"))
        pair = cue.get_editor_property("wing_pair")
        atts = list(pair.get_editor_property("attachments"))
        for guid, rec in items:
            att = atts[rec["index"]]
            assert unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid")) == guid, f"{label} index moved"
            b = rec["before"]
            att.set_editor_property("relative_transform", unreal.Transform(
                location=unreal.Vector(*b["loc"]), rotation=unreal.Rotator(roll=b["rot"][0], pitch=b["rot"][1], yaw=b["rot"][2]),
                scale=unreal.Vector(*b["scale"])))
            L = att.get_editor_property("lighting")
            L.set_editor_property("type", enum_value(unreal.InfinityStageLightType, b["type"]))
            L.set_editor_property("intensity_units", enum_value(unreal.InfinityStageLightIntensityUnits, b["intensity_units"]))
            for f in ("intensity", "temperature_kelvin", "attenuation_radius_cm", "inner_cone_angle_degrees",
                      "outer_cone_angle_degrees", "volumetric_scattering_intensity"):
                L.set_editor_property(f, float(b[f]))
            for f in ("use_temperature", "cast_shadows", "cast_volumetric_shadow"):
                L.set_editor_property(f, bool(b[f]))
            cur = L.get_editor_property("color")
            if isinstance(b["color"], list):
                L.set_editor_property("color", type(cur)(*b["color"]))
            att.set_editor_property("lighting", L)
            att.set_editor_property("enabled", bool(b["enabled"]))
            atts[rec["index"]] = att
            restored += 1
        pair.set_editor_property("attachments", atts)
        cue.set_editor_property("wing_pair", pair)
        cues[ci] = cue
    show.set_editor_property("cues", cues)
    assert restored == len(record["rows"]), f"restored {restored} of {len(record['rows'])}"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    for p in actors:
        if isinstance(p, unreal.InfinityStagePassageActor) and p.get_actor_label()[8:10] in ("04", "05", "06"):
            assert p.materialize_passage(), f"{p.get_actor_label()} did not materialize"
    for s in actors:
        if isinstance(s, unreal.InfinityStageStructureActor) and s.get_actor_label()[-2:] in ("04", "05", "06"):
            assert s.materialize_structure(), f"{s.get_actor_label()} did not re-fit"
    assert unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "Show save failed"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"P456_REVERT_OK|restored={restored}|show_saved=1|level_saved=1")


main()
