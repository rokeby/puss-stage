"""Read-only (30 Sep): is each mouth's portal CENTRED and SQUARE on where a transition drape is placed
(the Passage's route start, yawed to the route tangent there)? Measured from the portal's own
ISM INSTANCE TRANSFORMS (centre = instance transform of the mesh-bounds centre; yaw from the
instance rotation), not from world bounding boxes (P02's yawed posts inflate those: 18.71 m
instead of 19.0 m). Per mouth, in the route-start frame (x along, y across, z up):
- each post's centre, its yaw relative to the route, and its local size;
- the post pair's midpoint offset across and along; the post LINE's yaw deviation from square;
- inner width = across distance between centres minus the posts' across size;
- the header's centre across offset.
Writes portal_drape_alignment.json. Mutates nothing."""
import json
import math
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "portal_drape_alignment.json")


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    structures = {a.get_actor_label()[-2:]: a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)}
    out = {}
    for key in sorted(structures):
        s = structures[key]
        route = s.get_editor_property("passage").get_editor_property("route")
        T = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        route_yaw = T.rotation.rotator().yaw
        pieces = []
        for comp in s.get_components_by_class(unreal.InstancedStaticMeshComponent):
            if not comp.get_name().startswith("StructurePortal_"):
                continue
            bb = comp.get_editor_property("static_mesh").get_bounding_box()
            centre_local = unreal.Vector((bb.min.x + bb.max.x) / 2, (bb.min.y + bb.max.y) / 2, (bb.min.z + bb.max.z) / 2)
            for i in range(comp.get_instance_count()):
                t = comp.get_instance_transform(i, True)
                c = unreal.MathLibrary.inverse_transform_location(T, t.transform_location(centre_local))
                # Extent in the ROUTE frame (tight for pieces yawed with the route): the posts are
                # Cubes pitched 90, so their height lies along LOCAL x, not z.
                corners = [unreal.MathLibrary.inverse_transform_location(T, t.transform_location(unreal.Vector(x, y, z)))
                           for x in (bb.min.x, bb.max.x) for y in (bb.min.y, bb.max.y) for z in (bb.min.z, bb.max.z)]
                size = [max(q.x for q in corners) - min(q.x for q in corners), max(q.y for q in corners) - min(q.y for q in corners),
                        max(q.z for q in corners) - min(q.z for q in corners)]
                pieces.append({"i": i, "along": round(c.x, 2), "across": round(c.y, 2), "up": round(c.z, 2),
                               "yaw_rel_route": round(wrap(t.rotation.rotator().yaw - route_yaw), 3), "size": [round(v, 1) for v in size]})
        posts = sorted([p for p in pieces if p["size"][2] > 1000.0 and max(p["size"][0], p["size"][1]) < 200.0], key=lambda p: p["across"])
        header = next((p for p in pieces if p["size"][1] > 1500.0 and p["up"] > 1000.0), None)
        row = {"route_start": [round(v, 1) for v in T.translation.to_tuple()], "route_yaw": round(route_yaw, 3), "posts": posts, "header": header}
        if len(posts) == 2:
            a, b = posts
            d_along, d_across = b["along"] - a["along"], b["across"] - a["across"]
            row.update({"mid_across_cm": round((a["across"] + b["across"]) / 2, 2), "mid_along_cm": round((a["along"] + b["along"]) / 2, 2),
                        "post_line_yaw_dev_deg": round(math.degrees(math.atan2(d_along, d_across)), 3),
                        "inner_width_m": round((math.hypot(d_along, d_across) - (a["size"][1] + b["size"][1]) / 2) / 100.0, 3)})
        out[key] = row
    json.dump(out, open(OUT, "w"), indent=1)
    unreal.log("PORTAL_ALIGN_OK|" + " ".join(f"P{k}:mid_across={r.get('mid_across_cm')} mid_along={r.get('mid_along_cm')} "
                                             f"line_dev={r.get('post_line_yaw_dev_deg')} width={r.get('inner_width_m')}" for k, r in out.items()))


main()
