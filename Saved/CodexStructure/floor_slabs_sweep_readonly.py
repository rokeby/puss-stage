"""Read-only, for Gary's "drop all floors to zero" (29 Sep): find every floor slab
(a large engine Cube or Plane, or any actor labelled Floor), with its surface
height against the stage level of the structure it sits under, plus the dirty
set and any ZZ_/TEMP bench actors. Mutates nothing.
"""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "floor_slabs_sweep.json")
SHAPES = ("/Engine/BasicShapes/Cube.Cube", "/Engine/BasicShapes/Plane.Plane")
MIN_SPAN_CM = 2000.0

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()

# Stage level under each structure: its first station's height plus the floor setting.
stages = []
for a in actors:
    if isinstance(a, unreal.InfinityStageStructureActor):
        res = a.gather_stations()
        stations = res[0] if isinstance(res, tuple) else res
        if not stations:
            continue
        ground = a.get_editor_property("ground")
        z = stations[0].get_editor_property("station_world").translation.z + ground.get_editor_property("floor_height_cm")
        ys = [s.get_editor_property("station_world").translation.y for s in stations]
        xs = [s.get_editor_property("station_world").translation.x for s in stations]
        stages.append({"structure": a.get_actor_label(), "stage_z": round(z, 2), "ground_on": bool(ground.get_editor_property("enabled")),
                       "x": [round(min(xs)), round(max(xs))], "y": [round(min(ys)), round(max(ys))]})

slabs = []
for a in actors:
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        if isinstance(c, unreal.InstancedStaticMeshComponent):
            continue
        mesh = c.get_editor_property("static_mesh")
        path = mesh.get_path_name() if mesh else ""
        labelled = "floor" in a.get_actor_label().lower()
        if path not in SHAPES and not labelled:
            continue
        box = mesh.get_bounding_box() if mesh else None
        if not box:
            continue
        tf = c.get_world_transform()
        pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        lo = [min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)]
        hi = [max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)]
        if not labelled and (hi[0] - lo[0] < MIN_SPAN_CM or hi[1] - lo[1] < MIN_SPAN_CM):
            continue
        under = [s for s in stages if lo[1] - 2000 <= s["y"][0] <= hi[1] + 2000 and lo[0] <= s["x"][1] and hi[0] >= s["x"][0]]
        at = a.get_actor_transform()
        slabs.append({"label": a.get_actor_label(), "name": a.get_name(), "class": a.get_class().get_name(),
                      "component": c.get_name(), "mesh": path,
                      "actor_loc": [round(at.translation.x, 2), round(at.translation.y, 2), round(at.translation.z, 2)],
                      "actor_scale": [round(at.scale3d.x, 4), round(at.scale3d.y, 4), round(at.scale3d.z, 4)],
                      "component_is_root": c == a.get_editor_property("root_component"),
                      "world_min": [round(v, 1) for v in lo], "world_max": [round(v, 1) for v in hi],
                      "top_z": round(hi[2], 2), "thickness_cm": round(hi[2] - lo[2], 2),
                      "materials": [m.get_path_name() if m else None for m in c.get_materials()],
                      "visible": bool(c.get_editor_property("visible")) and not bool(a.get_editor_property("hidden")),
                      "stages_under": under})
dirty = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
         "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
bench = [a.get_actor_label() for a in actors if a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp"))]
json.dump({"slabs": slabs, "stages": stages, "dirty": dirty, "bench_actors": bench}, open(OUT, "w"), indent=1)
unreal.log(f"FLOOR_SLABS_SWEEP_OK|slabs={len(slabs)}|tops={[s['top_z'] for s in slabs]}|bench={len(bench)}"
           f"|dirty={len(dirty['content'])}+{len(dirty['maps'])}|mutated=0")
