"""Read-only: which lights actually reach the Opening curtain, and at what angle?
The curtain hangs on P01's route at x 0, half-width 888.5, heading at 1020
(Soft goods, 29 Sep); its face looks down the route toward the house (-X).

For every light component in the level:
- Samples a 9 x 4 grid on that plane (converted to world by Passage 01's
  transform): in reach, and inside a spot's cone?
- An estimate of its illuminance there (cd / d^2 * cos, lumens converted by
  cone), and its incidence (0 = square on, i.e. flat; 90 = grazing, i.e. folds
  and sheen).
- Its owner: a Show attachment tag, or a level actor.

Also lists the directional and sky lights with their intensities (the celestial
rig's flood), and the stalls camera if one is found. Writes
curtain_light_inventory.json. Mutates nothing. Lean: all work in main().
"""
import json
import math
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "curtain_light_inventory.json")
HALF, TOP = 888.5, 1020.0


def to_cd(comp):
    i = comp.get_editor_property("intensity")
    units = str(comp.get_editor_property("intensity_units")) if hasattr(comp, "intensity_units") else ""
    if "LUMENS" in units.upper():
        if isinstance(comp, unreal.SpotLightComponent):
            half = math.radians(comp.get_editor_property("outer_cone_angle"))
            return i / (2.0 * math.pi * (1.0 - math.cos(half)))
        return i / (4.0 * math.pi)
    if "CANDELAS" in units.upper():
        return i
    return None   # unitless or EV: reported raw


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    p01 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
    ptf = p01.get_actor_transform()
    normal = unreal.MathLibrary.transform_direction(ptf, unreal.Vector(-1.0, 0.0, 0.0))
    samples = [unreal.MathLibrary.transform_location(ptf, unreal.Vector(0.0, y, z))
               for y in [(-HALF + k * HALF / 4.0) for k in range(9)] for z in (150.0, 450.0, 750.0, 1000.0)]
    centre = unreal.MathLibrary.transform_location(ptf, unreal.Vector(0.0, 0.0, 500.0))
    rows, env = [], []
    for a in actors:
        for comp in a.get_components_by_class(unreal.LightComponent):
            if isinstance(comp, (unreal.DirectionalLightComponent,)):
                env.append({"actor": a.get_actor_label(), "type": "Directional", "intensity": comp.get_editor_property("intensity"),
                            "visible": bool(comp.is_visible()), "hidden_in_game": bool(a.is_hidden_ed())})
                continue
            if not isinstance(comp, unreal.LocalLightComponent):
                continue
            if not comp.is_visible():
                continue
            pos = comp.get_world_location()
            reach = comp.get_editor_property("attenuation_radius")
            fwd = comp.get_forward_vector()
            spot = isinstance(comp, unreal.SpotLightComponent)
            outer = comp.get_editor_property("outer_cone_angle") if spot else 180.0
            hits = 0
            for s in samples:
                v = s - pos
                d = v.length()
                if d > reach or d < 1.0:
                    continue
                if spot and math.degrees(math.acos(max(-1.0, min(1.0, v.dot(fwd) / d)))) > outer:
                    continue
                if (pos - s).dot(normal) <= 0.0:
                    continue   # behind the curtain face
                hits += 1
            if hits == 0:
                continue
            v = centre - pos
            d = v.length()
            cosi = max(0.0, (pos - centre).dot(normal) / d)
            cd = to_cd(comp)
            tag = next((str(t) for t in a.tags if str(t).startswith("InfinityStage.Attachment.")), None)
            rows.append({"actor": a.get_actor_label(), "class": a.get_class().get_name(), "show_tag": tag,
                         "type": "Spot" if spot else comp.get_class().get_name().replace("Component", ""),
                         "samples_lit": hits, "of": len(samples),
                         "cd": round(cd, 2) if cd is not None else None, "raw_intensity": round(comp.get_editor_property("intensity"), 3),
                         "units": str(comp.get_editor_property("intensity_units")) if hasattr(comp, "intensity_units") else None,
                         "lux_at_centre_est": round(cd * cosi / (d / 100.0) ** 2, 3) if cd is not None else None,
                         "incidence_deg": round(math.degrees(math.acos(min(1.0, cosi))), 1), "distance_m": round(d / 100.0, 1),
                         "colour": [round(c, 3) for c in (comp.get_editor_property("light_color").r / 255.0,
                                                           comp.get_editor_property("light_color").g / 255.0,
                                                           comp.get_editor_property("light_color").b / 255.0)],
                         "kelvin": comp.get_editor_property("temperature") if comp.get_editor_property("use_temperature") else None,
                         "cone": [comp.get_editor_property("inner_cone_angle"), outer] if spot else None,
                         "cast_shadows": bool(comp.get_editor_property("cast_shadows")),
                         "local_pos": [round(c) for c in unreal.MathLibrary.inverse_transform_location(ptf, pos).to_tuple()]})
        if isinstance(a, unreal.SkyLight):
            c = a.get_component_by_class(unreal.SkyLightComponent)
            env.append({"actor": a.get_actor_label(), "type": "SkyLight", "intensity": c.get_editor_property("intensity"),
                        "visible": bool(c.is_visible())})
    rows.sort(key=lambda r: -(r["lux_at_centre_est"] or 0.0))
    json.dump({"curtain_normal_world": [round(c, 3) for c in normal.to_tuple()], "lights": rows, "environment": env},
              open(OUT, "w"), indent=1)
    unreal.log(f"CURTAIN_LIGHT_INVENTORY_OK|lights={len(rows)}|env={len(env)}|mutated=0")


main()
