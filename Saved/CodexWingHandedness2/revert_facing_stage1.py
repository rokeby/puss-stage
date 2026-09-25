"""REVERT (no save): restore each panel's recorded facing_before from apply_stage1_result.json
and rematerialize the affected Passages."""
import json
import os
import sys

import unreal  # noqa: E402

sys.path.insert(0, os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2"))
from _common import (  # noqa: E402
    OUT_DIR, dirty, editor_ready, load_show, passage_actors, require, write_json,
)

editor_ready()
rec = json.load(open(os.path.join(OUT_DIR, "apply_stage1_result.json"), encoding="utf-8"))
show = load_show()
cues = list(show.get_editor_property("cues"))
name_to_enum = {
    "AUTO_BY_ROLE": unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE,
    "PRESERVE_ASSET": unreal.InfinityPanelFacingPolicy.PRESERVE_ASSET,
    "ROTATE180_AROUND_UP": unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP,
}
restored = 0
passages = set()
for b in rec["before"]:
    cue = cues[b["index"]]
    require(str(cue.get_editor_property("label")) == b["label"], f"Row moved: {b['label']}")
    pair = cue.get_editor_property("wing_pair")
    panel = pair.get_editor_property(b["side"])
    key = next(k for k in name_to_enum if k in b["facing_before"])
    panel.set_editor_property("facing_policy", name_to_enum[key])
    pair.set_editor_property(b["side"], panel)
    cue.set_editor_property("wing_pair", pair)
    cues[b["index"]] = cue
    restored += 1
    passages.add(int(b["label"][1:3]))
show.modify()
show.set_editor_property("cues", cues)
actors = passage_actors(show)
for p in sorted(passages):
    require(bool(actors[p].materialize_passage()), f"Materialization failed for Passage {p}")
write_json("revert_result.json", {"status": "ok", "restored": restored, "passages": sorted(passages), "dirty": dirty()})
unreal.log(f"WING_FACING_REVERT_SUCCESS|restored={restored}|passages={sorted(passages)}|saved=0")
