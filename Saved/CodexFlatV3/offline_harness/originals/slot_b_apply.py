"""Apply all deterministic P04 Flat V3 assignments, materialize P04, save narrowly."""
import importlib
import json
import importlib
import os
import sys
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)
import slot_b_revert

report = {"run": c.RUN, "mode": "apply"}
show_touched = False
saved_roots = []
try:
    c.assert_context(clean=True)
    originals = c.read_json("slot_b_originals_%s.json" % c.RUN)
    plan = c.read_json("slot_b_dry_run_%s.json" % c.RUN)
    for name in ("DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"):
        if not os.path.isfile(os.path.join(c.BACKUP, name)):
            raise RuntimeError("BACKUP_FILE_MISSING|" + name)
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues = list(show.get_editor_property("cues"))
    originals_by_index = {row["cue_index"]: row for row in originals["rows"]}
    for row in plan["rows"]:
        original = originals_by_index[row["cue_index"]]
        cue = cues[row["cue_index"]]
        if str(cue.get_editor_property("label")) != row["cue_label"]:
            raise RuntimeError("CUE_IDENTITY_FAIL|" + row["cue_label"])
        pair = cue.get_editor_property("wing_pair")
        for side in ("left", "right", "top"):
            if c.panel_plain(pair.get_editor_property(side)) != original[side]:
                raise RuntimeError("ORIGINALS_DRIFT|label=%s|side=%s" % (row["cue_label"], side))
        if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
            raise RuntimeError("MECHANISM_DRIFT_BEFORE|" + row["cue_label"])
        for side in ("left", "right"):
            pair.set_editor_property(side, c.set_panel(pair.get_editor_property(side), row[side]))
        pair.set_editor_property("occurrence_offset", c.transform_from_plain(original["occurrence_offset"]))
        cue.set_editor_property("wing_pair", pair)
        cues[row["cue_index"]] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    show_touched = True
    unreal.log("FLATV3_B_MATERIALIZE_CALL run=%s passage=P04 ordinal=1" % c.RUN)
    if not c.p04_actor(show).materialize_passage():
        raise RuntimeError("P04_MATERIALIZE_FAIL")
    expected_dirty = {"content": [c.SHOW], "maps": [c.WORLD]}
    before_save = c.census()
    if before_save != expected_dirty:
        raise RuntimeError("DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected_dirty, sort_keys=True), json.dumps(before_save, sort_keys=True)))
    if not unreal.EditorAssetLibrary.save_asset(c.SHOW, only_if_is_dirty=False):
        raise RuntimeError("SHOW_SAVE_FAIL")
    saved_roots.append(c.SHOW)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("LEVEL_SAVE_FAIL")
    saved_roots.append(c.WORLD)
    if c.census() != {"content": [], "maps": []}:
        raise RuntimeError("POST_SAVE_DIRTY|" + json.dumps(c.census(), sort_keys=True))

    show2 = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues2 = list(show2.get_editor_property("cues"))
    readback = []
    for row in plan["rows"]:
        original = originals_by_index[row["cue_index"]]
        pair = cues2[row["cue_index"]].get_editor_property("wing_pair")
        actual = {side: c.panel_plain(pair.get_editor_property(side)) for side in ("left", "right", "top")}
        for side in ("left", "right"):
            expected = row[side]
            if (actual[side]["mesh"] != expected["mesh"] or actual[side]["material_overrides"] != [] or
                    not c.close_transform(actual[side]["local_transform"], expected["local_transform"]) or
                    "PRESERVE_ASSET" not in actual[side]["facing_policy"] or
                    actual[side]["flip_image_horizontally"]):
                raise RuntimeError("PANEL_READBACK_FAIL|label=%s|side=%s|actual=%s" %
                                   (row["cue_label"], side, json.dumps(actual[side], sort_keys=True)))
        if actual["top"] != original["top"]:
            raise RuntimeError("TOP_CHANGED|" + row["cue_label"])
        if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
            raise RuntimeError("MECHANISM_CHANGED|" + row["cue_label"])
        if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
                                 original["occurrence_offset"]):
            raise RuntimeError("OCCURRENCE_OFFSET_CHANGED|" + row["cue_label"])
        readback.append({"cue_label": row["cue_label"], "left": actual["left"], "right": actual["right"]})
    report.update({"status": "PASS", "backup": c.BACKUP, "rows": len(readback),
                   "materialize_calls": ["P04"], "dirty_before_save": before_save,
                   "dirty_after_save": c.census(), "readback": readback,
                   "saved_roots": sorted(set(saved_roots))})
    path = c.write_json("slot_b_apply_%s.json" % c.RUN, report)
    unreal.log("FLATV3_B_APPLY_SAVED run=%s rows=%d saved_roots=%s census=%s report=%s" %
               (c.RUN, len(readback), json.dumps(sorted(set(saved_roots))),
                json.dumps(c.census(), separators=(",", ":"), sort_keys=True), path))
except Exception as exc:
    reason = "apply:" + str(exc)
    report.update({"status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
                   "census": c.census()})
    c.write_json("slot_b_apply_%s_FAILURE.json" % c.RUN, report)
    if show_touched:
        try:
            saved_roots = slot_b_revert.revert(reason)
        except Exception as revert_exc:
            reason += "|REVERT_FAIL:" + str(revert_exc)
    c.log_release("FAIL", saved_roots, reason)
