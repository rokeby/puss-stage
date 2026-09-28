"""Read-only: where each P01 wing pair's Left and Right panels stand across the
route, in route order, from both the Show (LocalTransform) and the materialized
panels. Checks the premise "P01's first station is -750 / +500 where every other
station is +-750" before editing station 1. Mutates nothing.
"""
import collections
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL = re.compile(r"^P01 Wing (\d{3})$")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
show = passage.get_editor_property("show_asset")

base_x = {}
for ref in passage.get_editor_property("materialized_panels"):
    g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
    base_x.setdefault(g, ref.get_editor_property("base_world_transform").translation.x)

rows = []
for i, cue in enumerate(show.get_editor_property("cues")):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    pair = cue.get_editor_property("wing_pair")
    left = pair.get_editor_property("left").get_editor_property("local_transform").translation
    right = pair.get_editor_property("right").get_editor_property("local_transform").translation
    g = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
    rows.append({"index": i, "label": m.group(0), "x": round(base_x.get(g, 0)),
                 "left_y": round(left.y), "right_y": round(right.y),
                 "occ_offset_y": round(pair.get_editor_property("occurrence_offset").translation.y)})
rows.sort(key=lambda r: r["x"])
pattern = collections.Counter((r["left_y"], r["right_y"]) for r in rows)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p01_wing_laterals.json")
json.dump({"rows": rows, "pattern": {f"{k[0]}/{k[1]}": n for k, n in pattern.items()}}, open(out, "w"), indent=1)
unreal.log(f"P01_WING_LATERALS_OK|pairs={len(rows)}|patterns={len(pattern)}|mutated=0")
