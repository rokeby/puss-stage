"""Read-only: the five transition mouths (Passages 02-06), for the mouth lanterns (30 Sep).
Per passage: the route's start frame, the first station, the portal pieces (posts,
header) as built, any actor whose label says stalls / curtain / drape / mouth within
40 m of the mouth, and the P01 warmer spots as the reference instrument.
Writes Saved/CodexStructure/mouth_survey.json. Mutates nothing. Lean: all work in main()."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "mouth_survey.json")
WORDS = ("stalls", "curtain", "drape", "mouth", "warmer", "portal", "interaction")


def v(x):
    return [round(x.x, 1), round(x.y, 1), round(x.z, 1)]


def r(x):
    return [round(x.roll, 2), round(x.pitch, 2), round(x.yaw, 2)]


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    structures = {a.get_actor_label()[-2:]: a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)}
    out = {"mouths": {}, "warmer": []}
    named = [a for a in actors if any(w in a.get_actor_label().lower() for w in WORDS)]
    for a in actors:
        if isinstance(a, unreal.SpotLight) and "warmer" in a.get_actor_label().lower():
            c = a.get_component_by_class(unreal.SpotLightComponent)
            out["warmer"].append({"label": a.get_actor_label(), "loc": v(a.get_actor_location()), "rot": r(a.get_actor_rotation()),
                                  "cd": c.get_editor_property("intensity"), "outer": c.get_editor_property("outer_cone_angle"),
                                  "inner": c.get_editor_property("inner_cone_angle"), "k": c.get_editor_property("temperature"),
                                  "use_k": c.get_editor_property("use_temperature"), "shadows": c.get_editor_property("cast_shadows"),
                                  "radius": c.get_editor_property("attenuation_radius")})
    for key in ("01", "02", "03", "04", "05", "06"):
        s = structures.get(key)
        if not s:
            continue
        p = s.get_editor_property("passage")
        route = p.get_editor_property("route")
        start = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        portal = s.get_editor_property("portal")
        pieces = []
        for comp in s.get_components_by_class(unreal.InstancedStaticMeshComponent):
            if not comp.get_name().startswith(("StructurePortal_", "StructureForestage", "StructureStageFront")):
                continue
            bb = comp.get_editor_property("static_mesh").get_bounding_box()
            n = comp.get_instance_count()
            if comp.get_name().startswith("StructurePortal_"):
                for i in range(n):
                    t = comp.get_instance_transform(i, True)
                    lo, hi = bb.min, bb.max
                    pts = [t.transform_location(unreal.Vector(x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
                    pieces.append({"i": i, "min": [round(min(q.x for q in pts)), round(min(q.y for q in pts)), round(min(q.z for q in pts))],
                                   "max": [round(max(q.x for q in pts)), round(max(q.y for q in pts)), round(max(q.z for q in pts))]})
            else:
                pieces.append({"component": comp.get_name(), "instances": n})
        mouth = start.translation
        near = [{"label": a.get_actor_label(), "class": a.get_class().get_name(), "loc": v(a.get_actor_location()), "rot": r(a.get_actor_rotation())}
                for a in named if (a.get_actor_location() - mouth).length() < 4000.0]
        out["mouths"][key] = {"passage": p.get_actor_label(), "route_start": v(mouth), "route_start_rot": r(start.rotation.rotator()),
                              "portal_enabled": bool(portal.get_editor_property("enabled")),
                              "stage_front": bool(portal.get_editor_property("stage_front")),
                              "offset_from_first_station_cm": portal.get_editor_property("offset_from_first_station_cm"),
                              "opening_half_width_cm": portal.get_editor_property("opening_half_width_cm"),
                              "opening_height_cm": portal.get_editor_property("opening_height_cm"),
                              "grid_half_width_cm": s.get_editor_property("grid_half_width_cm"),
                              "portal_pieces": pieces, "named_actors_within_40m": near}
    json.dump(out, open(OUT, "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"MOUTH_SURVEY_OK|mouths={len(out['mouths'])}|warmer={len(out['warmer'])}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
