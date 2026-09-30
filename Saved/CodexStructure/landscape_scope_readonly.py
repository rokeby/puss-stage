"""Read-only scope for Gary's "remove all landscapes and replace them with the floors" (30 Sep).
Per Landscape (and proxy): label, class, folder, bounds, component count, material; which Passage routes
cross it and the surface height under each route (traced); every actor that STANDS on it (bounds bottom
within 60 cm of the traced surface under the actor's centre) with its height above/below the Passage's
floor line; each Passage's Structure board count (where the landscape IS the floor); foliage near it.
Writes landscape_scope.json. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    lands = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    passages = [a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)]
    structures = {a.get_actor_label()[-2:]: a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)}

    def surface(x, y, only):
        hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(x, y, 50000.0), unreal.Vector(x, y, -50000.0),
                                                     unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True)
        if hit is None:
            return None
        parts = hit.to_tuple()
        act = next((p for p in parts if isinstance(p, unreal.Actor)), None)
        loc = next((p for p in parts if isinstance(p, unreal.Vector)), None)
        return loc.z if (act is only and loc) else None

    out = {"landscapes": [], "passages": {}}
    for p in passages:
        key = p.get_actor_label()[8:10]
        s = structures.get(key)
        boards = None
        if s:
            boards = sum(c.get_instance_count() for c in s.get_components_by_class(unreal.InstancedStaticMeshComponent)
                         if "Board" in c.get_name() or "Ground" in c.get_name())
        route = p.get_editor_property("route")
        out["passages"][key] = {"label": p.get_actor_label(), "structure_board_or_ground_instances": boards,
                                "route_len_m": round(route.get_spline_length() / 100.0, 1)}
    for L in lands:
        o, e = L.get_actor_bounds(False)
        comps = L.get_components_by_class(unreal.LandscapeComponent)
        mat = None
        try:
            m = L.get_editor_property("landscape_material")
            mat = m.get_path_name().split(".")[-1] if m else None
        except Exception:  # noqa: BLE001
            pass
        row = {"label": L.get_actor_label(), "class": L.get_class().get_name(), "folder": str(L.get_folder_path()),
               "centre": [round(v) for v in o.to_tuple()], "extent_m": [round(e.x / 100, 1), round(e.y / 100, 1), round(e.z / 100, 2)],
               "components": len(comps), "material": mat, "routes": [], "standing": []}
        for p in passages:
            route = p.get_editor_property("route")
            length = route.get_spline_length()
            zs = []
            for k in range(0, 21):
                q = route.get_location_at_distance_along_spline(length * k / 20.0, unreal.SplineCoordinateSpace.WORLD)
                if abs(q.x - o.x) <= e.x and abs(q.y - o.y) <= e.y:
                    z = surface(q.x, q.y, L)
                    if z is not None:
                        zs.append(round(z, 1))
            if zs:
                row["routes"].append({"passage": p.get_actor_label(), "samples_on_landscape": len(zs), "surface_z_range": [min(zs), max(zs)]})
        for a in actors:
            if a is L or isinstance(a, (unreal.LandscapeProxy, unreal.CameraActor, unreal.PostProcessVolume)) or a.get_class().get_name() == "InfinityStageCelestialRig":
                continue
            ao, ae = a.get_actor_bounds(False)
            if ae.length() < 1.0 or max(ae.x, ae.y) > 5.0e4 or abs(ao.x - o.x) > e.x or abs(ao.y - o.y) > e.y:
                continue
            z = surface(ao.x, ao.y, L)
            if z is not None and abs((ao.z - ae.z) - z) < 60.0:
                row["standing"].append({"label": a.get_actor_label(), "class": a.get_class().get_name(), "surface_z": round(z, 1),
                                        "bottom_z": round(ao.z - ae.z, 1)})
        foliage = [a for a in actors if a.get_class().get_name() == "InstancedFoliageActor"]
        row["foliage_instances_total_level"] = sum(c.get_instance_count() for f in foliage for c in f.get_components_by_class(unreal.InstancedStaticMeshComponent))
        out["landscapes"].append(row)
    json.dump(out, open(os.path.join(HERE, "landscape_scope.json"), "w"), indent=1)
    unreal.log("LANDSCAPE_SCOPE_OK|" + " ".join(f"{r['label']}:comps={r['components']}:standing={len(r['standing'])}" for r in out["landscapes"]))


main()
