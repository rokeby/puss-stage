"""Read-only: the S4 ghost light as it stands: attachment chain, light type and settings, and
its place in the hangar root's frame; plus the root's rest transform and the Scene 4 Entry
Handoff Camera. Writes ghost_light_facts.json. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def chain(a):
    out, p = [], a.get_attach_parent_actor()
    while p:
        out.append(p.get_actor_label())
        p = p.get_attach_parent_actor()
    return out


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    root = next(a for a in actors if a.get_actor_label() == "S4 Hangar Root")
    rt = root.get_actor_transform()
    cam = next(a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label())
    out = {"root": {"loc": root.get_actor_location().to_tuple(), "rot": [root.get_actor_rotation().roll, root.get_actor_rotation().pitch, root.get_actor_rotation().yaw]},
           "camera": {"label": cam.get_actor_label(), "loc": cam.get_actor_location().to_tuple(), "rot": [cam.get_actor_rotation().roll, cam.get_actor_rotation().pitch, cam.get_actor_rotation().yaw]},
           "ghost": []}
    for a in actors:
        if "Ghost" in a.get_actor_label() and "S4" in a.get_actor_label():
            rel = rt.inverse_transform_location(a.get_actor_location())
            row = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "chain": chain(a),
                   "world": a.get_actor_location().to_tuple(), "in_root_frame": rel.to_tuple(), "tags": [str(t) for t in a.tags]}
            lc = a.get_component_by_class(unreal.LightComponent)
            if lc:
                row["light"] = {"type": lc.get_class().get_name(), "intensity": lc.get_editor_property("intensity"),
                                "units": str(lc.get_editor_property("intensity_units")) if hasattr(lc, "get_editor_property") else None,
                                "attenuation_radius": lc.get_editor_property("attenuation_radius"),
                                "cast_shadows": lc.get_editor_property("cast_shadows"), "mobility": str(lc.get_editor_property("mobility")),
                                "source_radius": lc.get_editor_property("source_radius"), "color": lc.get_editor_property("light_color").to_tuple(),
                                "forward_world": lc.get_forward_vector().to_tuple(), "visible": lc.get_editor_property("visible"),
                                "indirect": lc.get_editor_property("indirect_lighting_intensity")}
                if isinstance(lc, unreal.SpotLightComponent):
                    row["light"].update({"inner": lc.get_editor_property("inner_cone_angle"), "outer": lc.get_editor_property("outer_cone_angle")})
            out["ghost"].append(row)
    json.dump(out, open(os.path.join(HERE, "ghost_light_facts.json"), "w"), indent=1)
    unreal.log(f"GHOST_FACTS_OK|{len(out['ghost'])}")


main()
