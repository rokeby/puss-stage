"""Read-only (30 Sep): what does each Scene's hangar box rise THROUGH? For Scenes 1-6, in the
builder's own dock frame (the Entry Handoff Camera at z 0, its yaw; hinge at x = apron,
z = hinge_z), two independent looks at the box's footprint (x apron..apron+depth, |y| <= half-width):
1. vertical visibility traces on a 5 x 5 grid, ignoring the hangar's own actors: the first
   surface under each point and its height relative to the hinge;
2. every other actor whose world bounds cover the footprint's centre and reach within the
   swept depth, with NO size cutoff (hangar_build.py's blocker test skips anything wider than
   10 km, which is how a ground plane can pass it), plus its owner facts (class, folder,
   tags, mesh, materials, collision).
Writes hangar_ground_survey.json. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
S4 = {"depth": 6000.0, "half_w": 1000.0, "height": 3000.0, "apron": 500.0, "hinge_z": 0.0}


def facts(a):
    row = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "folder": str(a.get_folder_path()),
           "tags": [str(t) for t in a.tags][:6]}
    smc = a.get_component_by_class(unreal.StaticMeshComponent)
    if smc:
        mesh = smc.get_editor_property("static_mesh")
        row["mesh"] = mesh.get_path_name() if mesh else None
        row["materials"] = [m.get_path_name().split(".")[-1] if m else None for m in smc.get_materials()][:3]
        row["collision"] = str(smc.get_collision_enabled())
        row["hidden_in_game"] = bool(smc.get_editor_property("hidden_in_game"))
    return row


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    out = {}
    for n in range(1, 7):
        path = os.path.join(HERE, f"hangar_s{n}_record.json")
        h = json.load(open(path, encoding="utf-8"))["hangar"] if os.path.exists(path) else dict(S4)
        hz = float(h.get("hinge_z") or 0.0)
        cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
        cl, cr = cam.get_actor_location(), cam.get_actor_rotation()
        dock = unreal.Transform(location=unreal.Vector(cl.x, cl.y, 0.0), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
        d, w, ap = h["depth"], h["half_w"], h["apron"]
        tag = unreal.Name(f"RigAtmos.Scene{n}Hangar")
        mine = [a for a in actors if tag in a.tags or a.get_actor_label().startswith(f"S{n} ")]
        grid = []
        for fx in (0.1, 0.3, 0.5, 0.7, 0.9):
            for fy in (-0.9, -0.45, 0.0, 0.45, 0.9):
                top = dock.transform_location(unreal.Vector(ap + fx * d, fy * w, hz + 3000.0))
                bot = dock.transform_location(unreal.Vector(ap + fx * d, fy * w, hz - d - 500.0))
                hit = unreal.SystemLibrary.line_trace_single(world, top, bot, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, mine,
                                                             unreal.DrawDebugTrace.NONE, True)
                if hit is None:
                    grid.append({"fx": fx, "fy": fy, "hit": None})
                    continue
                parts = hit.to_tuple()
                actor = next((p for p in parts if isinstance(p, unreal.Actor)), None)
                loc = next((p for p in parts if isinstance(p, unreal.Vector)), None)
                z_rel = unreal.MathLibrary.inverse_transform_location(dock, loc).z - hz if loc else None
                grid.append({"fx": fx, "fy": fy, "hit": actor.get_actor_label() if actor else "?", "z_rel_hinge": round(z_rel, 1) if z_rel is not None else None})
        centre = dock.transform_location(unreal.Vector(ap + 0.5 * d, 0.0, hz))
        cover = []
        for a in actors:
            if a in mine or a == cam or isinstance(a, (unreal.PostProcessVolume, unreal.CameraActor)):
                continue
            o, e = a.get_actor_bounds(False)
            if e.length() < 1.0:
                continue
            if abs(centre.x - o.x) <= e.x and abs(centre.y - o.y) <= e.y and (o.z + e.z) >= hz - d and (o.z - e.z) <= hz + 100.0:
                row = facts(a)
                row.update({"extent_m": [round(e.x / 100, 1), round(e.y / 100, 1), round(e.z / 100, 2)],
                            "top_rel_hinge_cm": round(o.z + e.z - hz, 1), "bottom_rel_hinge_cm": round(o.z - e.z - hz, 1)})
                cover.append(row)
        hits = {}
        for g in grid:
            hits.setdefault(g["hit"], []).append(g.get("z_rel_hinge"))
        out[f"S{n}"] = {"hangar": {k: h.get(k) for k in ("depth", "half_w", "height", "apron", "hinge_z", "floor")},
                        "trace_summary": {str(k): {"points": len(v), "z_rel_hinge": sorted(set(v))[:5] if v and v[0] is not None else None} for k, v in hits.items()},
                        "covering_actors": cover[:25], "grid": grid}
    json.dump(out, open(os.path.join(HERE, "hangar_ground_survey.json"), "w"), indent=1)
    unreal.log("HANGAR_GROUND_SURVEY_OK|" + " ".join(f"{k}:{len(v['covering_actors'])}" for k, v in out.items()))


main()
