"""Read-only: is each materialized gobo inside its materialized beam? From the
tagged SpotLight actor (world position, forward, outer cone) and the tagged gobo
actor (bounds centre, cast-shadow, mobility): the gobo centre's distance along the
axis, its offset off-axis, and the cone radius there. P01's source and its test
object (the mushroom) are reported alongside. Mutates nothing."""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    rec = json.load(open(os.path.join(HERE, "blink_spots_revert_record.json"), encoding="utf-8"))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    tagged = {}
    for a in actors:
        for t in a.tags:
            s = str(t)
            if s.startswith("InfinityStage.Attachment."):
                tagged[s.split("|")[-1]] = a
    out = []
    for cg, (lg, pg) in rec["added"].items():
        lamp, gobo = tagged[lg], tagged[pg]
        lc = lamp.get_component_by_class(unreal.SpotLightComponent)
        p = lamp.get_actor_location()
        f = lamp.get_actor_forward_vector()
        o, e = gobo.get_actor_bounds(False)
        v = o - p
        along = v.dot(f)
        off = (v - f * along).length()
        smc = gobo.get_component_by_class(unreal.StaticMeshComponent)
        out.append({"lamp": lamp.get_actor_label(), "gobo": gobo.get_actor_label(),
                    "along_cm": round(along, 1), "off_axis_cm": round(off, 1),
                    "cone_radius_cm": round(along * math.tan(math.radians(lc.get_editor_property("outer_cone_angle"))), 1),
                    "gobo_extent": [round(x, 1) for x in e.to_tuple()],
                    "gobo_cast_shadow": bool(smc.get_editor_property("cast_shadow")),
                    "gobo_mobility": str(smc.get_editor_property("mobility")),
                    "gobo_visible": bool(smc.is_visible()), "gobo_hidden_in_game": bool(gobo.is_hidden_ed()),
                    "lamp_cast_shadows": bool(lc.get_editor_property("cast_shadows")),
                    "lamp_visible": bool(lc.is_visible()), "lamp_intensity": round(lc.get_editor_property("intensity"), 1),
                    "source_radius": lc.get_editor_property("source_radius")})
    json.dump(out, open(os.path.join(HERE, "blink_gobo_in_beam.json"), "w"), indent=1)
    unreal.log(f"BLINK_GOBO_IN_BEAM_OK|pairs={len(out)}|mutated=0")


main()
