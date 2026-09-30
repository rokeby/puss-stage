"""Undo blink_spots_apply.py: from each planned pair, remove the attachments that
were not in its "before" list and are labelled Blink Spot / Blink Gobo. Require
that what remains is exactly the recorded list, in order. Then materialize
P02-P06, re-fit their structures, and save the Show and the level only. Lean:
all work inside main()."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "blink_spots_revert_record.json")
PASSAGES = ("P02", "P03", "P04", "P05", "P06")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "foreign dirty content"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors), "bench actors in the level"
    record = json.load(open(RECORD, encoding="utf-8"))
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    cues = list(show.get_editor_property("cues"))
    index = {gs(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
    show.modify()
    removed = 0
    for cg, rec in record["pairs"].items():
        ci = index[cg]
        cue = cues[ci]
        pair = cue.get_editor_property("wing_pair")
        atts = list(pair.get_editor_property("attachments"))
        keep, drop = [], []
        for a in atts:
            new = gs(a.get_editor_property("attachment_guid")) not in rec["before"]
            if new and str(a.get_editor_property("label")).endswith(("Blink Spot", "Blink Gobo")):
                drop.append(a)
            else:
                keep.append(a)
        assert [gs(a.get_editor_property("attachment_guid")) for a in keep] == rec["before"], f"{rec['cue']}: pair differs from the record"
        removed += len(drop)
        pair.set_editor_property("attachments", keep)
        cue.set_editor_property("wing_pair", pair)
        cues[ci] = cue
    show.set_editor_property("cues", cues)
    passages = {("P" + p.get_actor_label()[8:10]): p for p in actors if isinstance(p, unreal.InfinityStagePassageActor)}
    for pn in PASSAGES:
        assert passages[pn].materialize_passage(), f"{pn} did not materialize"
    refit = {}
    for s in sub.get_all_level_actors():
        if isinstance(s, unreal.InfinityStageStructureActor) and ("P" + s.get_actor_label()[-2:]) in PASSAGES:
            assert s.materialize_structure(), f"{s.get_actor_label()} did not re-fit"
            refit[s.get_actor_label()] = bool(s.is_structure_current())
    assert len(refit) == len(PASSAGES) and all(refit.values()), f"structures: {refit}"
    c1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    m1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    assert not (c1 - {SHOW_PATH}) and not (m1 - {EXPECTED_WORLD}), f"out-of-scope dirty: {c1} {m1}"
    assert unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "Show save failed"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    unreal.log(f"BLINK_SPOTS_REVERTED|removed={removed}|refit={refit}")


main()
