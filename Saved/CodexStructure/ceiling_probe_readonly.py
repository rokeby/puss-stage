"""Read-only: what hangs over Passage 01 above the gridiron.

The conductor's offscreen captures show large, very saturated red cloud panels
dominating the view upward. This lists every primitive whose bounds reach above
the grid inside P01's footprint: Top wing panels first, then anything else.
Mutates nothing.
"""
import collections
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GRID_Z = 1150.0

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p01 = next(a for a in sub.get_all_level_actors()
           if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
origin = p01.get_actor_location()
length = p01.get_editor_property("route").get_spline_length()


def side_of(ref):
    return str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")


tops = collections.Counter()
top_z = []
for ref in p01.get_editor_property("materialized_panels"):
    if side_of(ref) == "TOP":
        comp = ref.get_editor_property("component")
        mesh = comp.get_editor_property("static_mesh")
        mats = [m.get_path_name() if m else None for m in comp.get_materials()]
        tops[(mesh.get_path_name() if mesh else None, tuple(mats))] += 1
        top_z.append(ref.get_editor_property("base_world_transform").translation.z)

others = collections.Counter()
for a in sub.get_all_level_actors():
    if a == p01:
        continue
    for comp in a.get_components_by_class(unreal.PrimitiveComponent):
        try:
            b = comp.get_editor_property("bounds") if False else comp.bounds
        except Exception:
            continue
        lo = b.origin - b.box_extent
        hi = b.origin + b.box_extent
        inside = (hi.x > origin.x and lo.x < origin.x + length
                  and hi.y > origin.y - 2500 and lo.y < origin.y + 2500)
        if inside and hi.z > GRID_Z and comp.is_visible():
            mesh = comp.get_editor_property("static_mesh").get_path_name() if isinstance(comp, unreal.StaticMeshComponent) and comp.get_editor_property("static_mesh") else None
            mats = tuple(m.get_path_name() if m else None for m in comp.get_materials()) if hasattr(comp, "get_materials") else ()
            others[(a.get_actor_label(), a.get_class().get_name(), comp.get_class().get_name(), mesh, mats,
                    round(lo.z), round(hi.z))] += 1

report = {
    "p01_top_panels": [{"mesh": k[0], "materials": list(k[1]), "count": n} for k, n in tops.most_common()],
    "p01_top_z_cm": [round(min(top_z)), round(max(top_z))] if top_z else None,
    "other_primitives_above_grid": [
        {"actor": k[0], "class": k[1], "component": k[2], "mesh": k[3], "materials": list(k[4]),
         "z_cm": [k[5], k[6]], "count": n} for k, n in others.most_common(40)],
}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "ceiling_probe.json")
json.dump(report, open(out, "w"), indent=1)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"CEILING_PROBE_OK|top_panels={sum(tops.values())}|other_kinds={len(others)}|dirty={dirty}|mutated=0")
