"""Read-only: what stands between the opening camera (x 0) and the curtain (x 5400)
near the centre of frame. The conductor's capture shows a boxy silhouette with a
panel on top in front of the curtain. Lists every visible primitive whose bounds
sit in x 300..5300, |y| < 500, z < 600, with whether it would render in game.
Mutates nothing.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"

hits = []
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    for comp in a.get_components_by_class(unreal.PrimitiveComponent):
        if not comp.is_visible():
            continue
        o, e, _ = unreal.SystemLibrary.get_component_bounds(comp)
        if o.x + e.x < 300 or o.x - e.x > 5300 or abs(o.y) - e.y > 500 or o.z - e.z > 600:
            continue
        if max(e.x, e.y, e.z) > 3000:     # corridor-scale things (boards, wings' ISMs) are not the object
            continue
        mesh = None
        if isinstance(comp, unreal.StaticMeshComponent) and comp.get_editor_property("static_mesh"):
            mesh = comp.get_editor_property("static_mesh").get_path_name()
        hits.append({"actor": a.get_actor_label(), "actor_class": a.get_class().get_name(),
                     "component": comp.get_name(), "component_class": comp.get_class().get_name(),
                     "mesh": mesh, "centre": [round(o.x), round(o.y), round(o.z)],
                     "size": [round(e.x * 2), round(e.y * 2), round(e.z * 2)],
                     "hidden_in_game": bool(comp.get_editor_property("hidden_in_game")),
                     "editor_only": bool(comp.get_editor_property("is_editor_only")) if hasattr(comp, "get_editor_property") else None})

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "opening_occluder_probe.json")
json.dump(sorted(hits, key=lambda h: h["centre"][0]), open(out, "w"), indent=1)
unreal.log(f"OPENING_OCCLUDER_PROBE_OK|hits={len(hits)}|mutated=0")
