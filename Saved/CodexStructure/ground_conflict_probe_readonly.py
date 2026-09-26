"""Read-only: what already occupies floor level in each Passage's corridor.

The structure pass lays boards with their tops at the route line (z=0). Anything
floor-like already there - a Landscape, a ground mesh in a Level Instance -
would z-fight them. Lists, per Passage, the primitives whose top lies within
+-25 cm of the route line, whose height is under 60 cm, and whose footprint
overlaps the corridor. Mutates nothing.
"""
import collections
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"

passages = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
            if a.get_actor_label().startswith("Passage 0")]
footprints = {}
for p in passages:
    loc = p.get_actor_location()
    length = p.get_editor_property("route").get_spline_length()
    footprints[p.get_actor_label()[:10]] = (loc.x - 400, loc.x + length + 400, loc.y - 1200, loc.y + 1200, loc.z)

report = collections.defaultdict(list)
# get_all_actors_of_class sees Level Instance sub-levels too, which the editor
# actor subsystem skips.
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if isinstance(a, unreal.InfinityStagePassageActor):
        continue
    for comp in a.get_components_by_class(unreal.PrimitiveComponent):
        if not comp.is_visible():
            continue
        origin, extent, _ = unreal.SystemLibrary.get_component_bounds(comp)
        top = origin.z + extent.z
        for name, (x0, x1, y0, y1, z0) in footprints.items():
            overlaps = origin.x + extent.x > x0 and origin.x - extent.x < x1 and \
                origin.y + extent.y > y0 and origin.y - extent.y < y1
            if overlaps and abs(top - z0) <= 25.0 and extent.z * 2.0 < 60.0:
                report[name].append({
                    "actor": a.get_actor_label(), "class": a.get_class().get_name(),
                    "component": comp.get_class().get_name(), "top_cm": round(top, 1),
                    "size_cm": [round(extent.x * 2), round(extent.y * 2), round(extent.z * 2)]})
        if isinstance(a, unreal.Landscape) or "Landscape" in a.get_class().get_name():
            report["_landscape_bounds"].append({
                "actor": a.get_actor_label(), "min": [round(origin.x - extent.x), round(origin.y - extent.y), round(origin.z - extent.z)],
                "max": [round(origin.x + extent.x), round(origin.y + extent.y), round(origin.z + extent.z)]})

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "ground_conflict_probe.json")
json.dump({k: v for k, v in report.items()}, open(out, "w"), indent=1)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("GROUND_CONFLICT_PROBE_OK|" + "|".join(f"{k}={len(v)}" for k, v in sorted(report.items()))
           + f"|dirty={dirty}|mutated=0")
