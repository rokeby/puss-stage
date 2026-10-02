"""Restore only the P04 fields changed by Slot B apply, then save narrowly."""
import json
import importlib
import os
import sys
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)


def revert(reason):
    c.assert_context(clean=False)
    doc = c.read_json("slot_b_originals_%s.json" % c.RUN)
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues = list(show.get_editor_property("cues"))
    untouched = {}
    for record in doc["rows"]:
        cue = cues[record["cue_index"]]
        if str(cue.get_editor_property("label")) != record["cue_label"]:
            raise RuntimeError("REVERT_CUE_IDENTITY_FAIL|" + record["cue_label"])
        pair = cue.get_editor_property("wing_pair")
        untouched[record["cue_index"]] = {
            "top": c.panel_plain(pair.get_editor_property("top")),
            "mechanism": c.mechanism_plain(pair.get_editor_property("mechanism")),
        }
        for side in ("left", "right"):
            pair.set_editor_property(
                side, c.set_panel(pair.get_editor_property(side), record[side]))
        pair.set_editor_property(
            "occurrence_offset", c.transform_from_plain(record["occurrence_offset"]))
        cue.set_editor_property("wing_pair", pair)
        cues[record["cue_index"]] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    if not c.p04_actor(show).materialize_passage():
        raise RuntimeError("REVERT_P04_MATERIALIZE_FAIL")
    expected = {"content": [c.SHOW], "maps": [c.WORLD]}
    if c.census() != expected:
        raise RuntimeError("REVERT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected, sort_keys=True), json.dumps(c.census(), sort_keys=True)))
    saved_roots = []
    if not unreal.EditorAssetLibrary.save_asset(c.SHOW, only_if_is_dirty=False):
        raise RuntimeError("REVERT_SHOW_SAVE_FAIL")
    saved_roots.append(c.SHOW)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("REVERT_LEVEL_SAVE_FAIL")
    saved_roots.append(c.WORLD)
    if c.census() != {"content": [], "maps": []}:
        raise RuntimeError("REVERT_POST_SAVE_DIRTY|" + json.dumps(c.census(), sort_keys=True))
    show2 = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues2 = list(show2.get_editor_property("cues"))
    for record in doc["rows"]:
        pair = cues2[record["cue_index"]].get_editor_property("wing_pair")
        for side in ("left", "right"):
            actual = c.panel_plain(pair.get_editor_property(side))
            if actual != record[side]:
                raise RuntimeError("REVERT_READBACK_FAIL|label=%s|side=%s" %
                                   (record["cue_label"], side))
        actual_offset = c.transform_plain(pair.get_editor_property("occurrence_offset"))
        if not c.close_transform(actual_offset, record["occurrence_offset"]):
            raise RuntimeError("REVERT_OFFSET_READBACK_FAIL|label=" + record["cue_label"])
        if (c.panel_plain(pair.get_editor_property("top")) != untouched[record["cue_index"]]["top"] or
                c.mechanism_plain(pair.get_editor_property("mechanism")) !=
                untouched[record["cue_index"]]["mechanism"]):
            raise RuntimeError("REVERT_UNTOUCHED_FIELD_CHANGED|label=" + record["cue_label"])

    saved_roots = sorted(set(saved_roots))
    report = {"run": c.RUN, "mode": "revert", "status": "PASS",
              "reason": str(reason), "rows": len(doc["rows"]),
              "restored_fields": ["left", "right", "occurrence_offset"],
              "saved_roots": saved_roots, "census": c.census()}
    c.write_json("slot_b_revert_%s.json" % c.RUN, report)
    unreal.log("FLATV3_B_REVERTED run=%s reason=%s rows=%d saved_roots=%s census=%s" %
               (c.RUN, str(reason).replace(" ", "_"), len(doc["rows"]),
                json.dumps(saved_roots, separators=(",", ":")),
                 json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
    return saved_roots


if __name__ == "__main__":
    revert(str(globals().get("FLATV3_REVERT_REASON", "manual")))
