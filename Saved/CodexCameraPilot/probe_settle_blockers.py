"""Read-only: what stands in front of the P04 settle camera in the FROZEN editor world, and what the
downward traces hit (raw HitResult fields, since GameplayStatics.break_hit_result is not in 5.8 Python).
No spawns, no writes. Success marker: PUSS_SETTLE_BLOCKERS"""
import json
import os

import unreal

POSES = {"f000": unreal.Vector(10043.5, 240000.0, 180.0), "f040": unreal.Vector(10543.5, 240000.0, 180.0),
         "entry": unreal.Vector(10668.5, 240000.0, 180.0)}


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report = {"ahead": {}, "trace": {}}
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    for key, eye in POSES.items():
        found = []
        for actor in actors:
            origin, extent = actor.get_actor_bounds(False)
            for ahead in (50.0, 150.0, 300.0, 600.0):
                p = eye + unreal.Vector(ahead, 0.0, 0.0)
                if all(abs(getattr(p, a) - getattr(origin, a)) <= getattr(extent, a) for a in ("x", "y", "z")):
                    if max(extent.x, extent.y, extent.z) < 20000.0:      # skip level-scale volumes
                        found.append("%s (%s) at +%dcm, hidden_in_game=%s" % (
                            actor.get_actor_label(), actor.get_class().get_name(), ahead,
                            actor.get_editor_property("hidden")))
                    break
        report["ahead"][key] = found[:15]
        result = unreal.SystemLibrary.line_trace_single(
            world, eye, eye - unreal.Vector(0.0, 0.0, 600.0), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            unreal.DrawDebugTrace.NONE, True)
        hit = result[1] if isinstance(result, tuple) else result
        report["trace"][key] = None if hit is None else [str(f)[:80] for f in hit.to_tuple()]
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "Captures", "Settle", "blockers.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    unreal.log("PUSS_SETTLE_BLOCKERS|written %s" % out)


main()
