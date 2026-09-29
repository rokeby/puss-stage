"""Read-only: which P05 station lost its slot in the per-side re-fit (186 -> 185),
and why. Lists stations where one side has no wing (the fix gives that side no
slot) with the cue label and its panels' laterals. Mutates nothing."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p05_slot_probe.json")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
structure = next(a for a in sub.get_all_level_actors()
                 if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label() == "Infinity Stage - Structure 05")
passage = structure.get_editor_property("passage")
result = structure.gather_stations()
stations = result[0] if isinstance(result, tuple) else result
show = passage.get_editor_property("show_asset")
labels = {unreal.GuidLibrary.conv_guid_to_string(c.get_editor_property("cue_guid")): str(c.get_editor_property("label"))
          for c in show.get_editor_property("cues")}
rows = []
for i, st in enumerate(stations):
    neg, pos = st.get_editor_property("negative_side_cm"), st.get_editor_property("positive_side_cm")
    if neg <= 0.0 or pos <= 0.0:
        g = unreal.GuidLibrary.conv_guid_to_string(st.get_editor_property("cue_guid"))
        panels = []
        for ref in passage.get_editor_property("materialized_panels"):
            if unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")) == g:
                t = ref.get_editor_property("base_world_transform").translation
                panels.append({"side": str(ref.get_editor_property("side")), "world": [round(t.x), round(t.y), round(t.z)]})
        rows.append({"index": i, "cue": labels.get(g, g), "negative_side_cm": neg, "positive_side_cm": pos,
                     "distance_cm": st.get_editor_property("distance_cm"), "panels": panels})
report = {"stations": len(stations), "one_sided": rows,
          "slot_count_in_memory": int(structure.get_editor_property("slot_count"))}
json.dump(report, open(OUT, "w"), indent=1)
unreal.log(f"P05_SLOT_PROBE_OK|stations={len(stations)}|one_sided={len(rows)}|mutated=0")
