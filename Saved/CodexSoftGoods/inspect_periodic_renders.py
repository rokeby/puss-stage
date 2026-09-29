"""READ-ONLY, PIE (29 Sep): the ~1 s stutter survives a paused transport, flicker light functions off and dynamic
shadows off, so something ELSE sets the rhythm while the lights amplify it. A periodic extra scene render would do
exactly that: scene captures, sky-light recaptures, planar reflections, and GeometryCache or other streaming. List what
exists in the PIE world, with the flags that make it render. Writes nothing to the world."""
import json
import os

import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log("PUSS_SOFTGOODS_PERIODIC_RENDERS_STOPPED|no PIE")
        return
    rows = {"scene_captures": [], "sky_lights": [], "planar_reflections": [], "reflection_captures": 0, "other": []}
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for comp in actor.get_components_by_class(unreal.ActorComponent):
            cls = comp.get_class().get_name()
            if "SceneCapture" in cls:
                row = {"owner": actor.get_actor_label(), "class": cls, "active": comp.is_active()}
                for p in ("capture_every_frame", "capture_on_movement", "always_persist_rendering_state",
                          "texture_target"):
                    try:
                        v = comp.get_editor_property(p)
                        row[p] = v.get_path_name() if hasattr(v, "get_path_name") else v
                    except Exception:  # noqa: BLE001
                        pass
                rows["scene_captures"].append(row)
            elif cls == "SkyLightComponent":
                row = {"owner": actor.get_actor_label(), "visible": comp.is_visible()}
                for p in ("real_time_capture", "source_type", "intensity", "cast_shadows"):
                    try:
                        row[p] = str(comp.get_editor_property(p))
                    except Exception:  # noqa: BLE001
                        pass
                rows["sky_lights"].append(row)
            elif "PlanarReflection" in cls:
                rows["planar_reflections"].append({"owner": actor.get_actor_label(), "class": cls})
            elif "ReflectionCapture" in cls:
                rows["reflection_captures"] += 1
    del world
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_periodic_renders.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(rows, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_PERIODIC_RENDERS|" + json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in rows.items()}))


main()
