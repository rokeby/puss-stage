"""Read-only: every Scene's Entry Handoff Camera (the dock a hangar mouth sits on), with
its world transform, plus each Passage route's end frame for comparison and any actors
already tagged as a hangar. Writes Saved/CodexStructure/scene_docks.json. Mutates nothing."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "scene_docks.json")


def v(x):
    return [round(x.x, 2), round(x.y, 2), round(x.z, 2)]


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    out = {"entry_cameras": [], "route_ends": {}, "hangar_tagged": {}}
    for a in actors:
        label = a.get_actor_label()
        if "Entry Handoff Camera" in label:
            r = a.get_actor_rotation()
            out["entry_cameras"].append({"label": label, "loc": v(a.get_actor_location()), "rot": [round(r.roll, 3), round(r.pitch, 3), round(r.yaw, 3)],
                                         "tags": [str(t) for t in a.get_editor_property("tags")]})
        if isinstance(a, unreal.InfinityStagePassageActor):
            route = a.get_editor_property("route")
            n = route.get_spline_length()
            t = route.get_transform_at_distance_along_spline(n, unreal.SplineCoordinateSpace.WORLD, False)
            out["route_ends"][label] = {"length_cm": round(n, 2), "end": v(t.translation), "end_yaw": round(t.rotation.rotator().yaw, 3)}
        for t in a.get_editor_property("tags"):
            if str(t).startswith("RigAtmos.Scene") or str(t).startswith("RigAtmos.Hangar"):
                out["hangar_tagged"].setdefault(str(t), 0)
                out["hangar_tagged"][str(t)] += 1
    json.dump(out, open(OUT, "w"), indent=1)
    unreal.log(f"SCENE_DOCKS_OK|entry_cameras={len(out['entry_cameras'])}|routes={len(out['route_ends'])}")


main()
