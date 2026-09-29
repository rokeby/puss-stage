"""Read-only, for Gary's "maybe delete the landscape floors": every Landscape in
the level, its bounds, and what stands ON it. That means actors whose downward
trace from just above their base hits a landscape first, so they would fall into
void if it went. Also listed: what stands NEAR one (inside its footprint, base
within 3 m of its height range). Skeletal-mesh actors (the Scene 3 cast) are
called out. Refuses in PIE. Mutates nothing, spawns nothing.
"""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "landscape_sweep.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and ed.get_game_world() is None, "PIE is running or no editor world; try again when it ends"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()


def bounds(a):
    o, e = a.get_actor_bounds(False)
    return [o.x - e.x, o.y - e.y, o.z - e.z], [o.x + e.x, o.y + e.y, o.z + e.z]


landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
rec = []
for ls in landscapes:
    lo, hi = bounds(ls)
    rec.append({"label": ls.get_actor_label(), "class": ls.get_class().get_name(), "name": ls.get_name(),
                "min": [round(v) for v in lo], "max": [round(v) for v in hi],
                "hidden_in_game": bool(ls.get_editor_property("hidden")), "folder": str(ls.get_folder_path())})
ls_names = {ls.get_name() for ls in landscapes}

standing, near = [], []
for a in actors:
    if a.get_name() in ls_names or isinstance(a, unreal.LandscapeProxy):
        continue
    lo, hi = bounds(a)
    if hi[0] - lo[0] > 50000 or hi[1] - lo[1] > 50000:
        continue                                    # volumes, sky, floors
    over = [r for r in rec if r["min"][0] <= (lo[0] + hi[0]) / 2 <= r["max"][0]
            and r["min"][1] <= (lo[1] + hi[1]) / 2 <= r["max"][1]
            and r["min"][2] - 300 <= lo[2] <= r["max"][2] + 300]
    if not over:
        continue
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    start = unreal.Vector(cx, cy, lo[2] + 50.0)
    end = unreal.Vector(cx, cy, lo[2] - 2000.0)
    hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                 False, [a], unreal.DrawDebugTrace.NONE, True)
    hit_actor = None
    if hit:
        h = hit.to_tuple() if hasattr(hit, "to_tuple") else None
        try:
            hit_actor = hit.get_editor_property("actor") if not h else next((x for x in h if isinstance(x, unreal.Actor)), None)
        except Exception:
            hit_actor = None
    skeletal = bool(a.get_components_by_class(unreal.SkeletalMeshComponent))
    row = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "base_z": round(lo[2], 1),
           "xy": [round(cx), round(cy)], "skeletal": skeletal, "landscape": [r["label"] for r in over],
           "trace_hit": hit_actor.get_actor_label() if hit_actor else None}
    (standing if hit_actor is not None and hit_actor.get_name() in ls_names else near).append(row)

report = {"landscapes": rec, "standing_on_landscape": standing, "near_landscape": near,
          "standing_skeletal": [r["label"] for r in standing if r["skeletal"]]}
json.dump(report, open(OUT, "w"), indent=1)
unreal.log(f"LANDSCAPE_SWEEP_OK|landscapes={len(rec)}|standing={len(standing)}|standing_skeletal={len(report['standing_skeletal'])}"
           f"|near={len(near)}|mutated=0")
