"""Read-only: the below-lip sweep found a "Passage 01 - Opening Floor" actor whose
bounds (x -35150..69150, y +-10000, z -50..50) cover the whole stage and the house
in front of the lip. What is it: mesh, surface height, visibility, collision,
who made it? Mutates nothing.
"""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "opening_floor_inspect.json")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == "Passage 01 - Opening Floor")
rec = {"label": actor.get_actor_label(), "name": actor.get_name(), "class": actor.get_class().get_name(),
       "hidden_in_game": bool(actor.get_editor_property("hidden")),
       "is_editor_only": bool(actor.get_editor_property("is_editor_only_actor")),
       "tags": [str(t) for t in actor.get_editor_property("tags")],
       "folder": str(actor.get_folder_path()),
       "attach_parent": actor.get_attach_parent_actor().get_actor_label() if actor.get_attach_parent_actor() else None}
tf = actor.get_actor_transform()
rec["transform"] = {"loc": [tf.translation.x, tf.translation.y, tf.translation.z],
                    "rot": [tf.rotation.rotator().roll, tf.rotation.rotator().pitch, tf.rotation.rotator().yaw],
                    "scale": [tf.scale3d.x, tf.scale3d.y, tf.scale3d.z]}
comps = []
for c in actor.get_components_by_class(unreal.StaticMeshComponent):
    mesh = c.get_editor_property("static_mesh")
    box = mesh.get_bounding_box() if mesh else None
    origin, extent = c.get_local_bounds() if hasattr(c, "get_local_bounds") else (None, None)
    wtf = c.get_world_transform()
    top = None
    if box:
        pts = [unreal.MathLibrary.transform_location(wtf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        top = [round(min(p.z for p in pts), 2), round(max(p.z for p in pts), 2)]
    comps.append({"name": c.get_name(), "mesh": mesh.get_path_name() if mesh else None,
                  "mesh_bounds_local": [[box.min.x, box.min.y, box.min.z], [box.max.x, box.max.y, box.max.z]] if box else None,
                  "world_z_span": top,
                  "materials": [m.get_path_name() if m else None for m in c.get_materials()],
                  "visible": bool(c.get_editor_property("visible")),
                  "hidden_in_game": bool(c.get_editor_property("hidden_in_game")),
                  "collision": str(c.get_collision_enabled()),
                  "cast_shadow": bool(c.get_editor_property("cast_shadow"))})
rec["components"] = comps
json.dump(rec, open(OUT, "w"), indent=1)
unreal.log(f"OPENING_FLOOR_INSPECT_OK|components={len(comps)}|z={[c['world_z_span'] for c in comps]}"
           f"|visible={[c['visible'] and not c['hidden_in_game'] for c in comps]}|mutated=0")
