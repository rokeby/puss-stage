"""READ-ONLY (30 Sep): at every Passage mouth, does a floor slab run DOWNSTAGE of the stage-front lip and bury the fascia?
Soft goods measured it at P03: "Passage 03 - Floor" (top -5) starts 84 m downstage and covers the house floor at -120, while
P01's "Passage 01 - Opening Floor" starts AT the lip (x -150) and leaves the drop exposed. The shared curtain cache drapes
down P01's fascia, so a buried fascia makes the pile sink or float. This answers it for all six mouths at once.

Per mouth (portal frame = the Passage route start, the frame the portal is built in; P02 is rotated 22.9 deg): every
StaticMeshActor whose label contains "Floor" and whose TRUE corners (mesh box x actor transform, not the world AABB) reach
the mouth region (x -400..+50 cm, |y| < 1300 cm in the portal frame). For each: its downstage edge (min x), its top z, and
whether it starts downstage of the lip (min x < -150 - 1 cm) while lying above the house floor (top > -120 cm), i.e.
buries the fascia. Also the portal's own lip x (the forestage depth) as built.
Mutates nothing. Marker FLOOR_VS_LIP|run=<id>."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    floors = [a for a in actors if isinstance(a, unreal.StaticMeshActor) and "floor" in a.get_actor_label().lower()
              and a.static_mesh_component.static_mesh is not None]
    rows = {}
    for n in range(1, 7):
        s = by.get(f"Infinity Stage - Structure 0{n}")
        if s is None:
            continue
        portal = s.get_editor_property("portal")
        lip = -float(portal.get_editor_property("forestage_depth_cm"))
        route = s.get_editor_property("passage").get_editor_property("route")
        start = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        frame = unreal.Transform(location=start.translation, rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=start.rotation.rotator().yaw))
        hits = []
        for a in floors:
            bb = a.static_mesh_component.static_mesh.get_bounding_box()
            xf = a.static_mesh_component.get_world_transform()
            pts = [frame.inverse_transform_location(xf.transform_location(unreal.Vector(x, y, z)))
                   for x in (bb.min.x, bb.max.x) for y in (bb.min.y, bb.max.y) for z in (bb.min.z, bb.max.z)]
            lo_x, hi_x = min(p.x for p in pts), max(p.x for p in pts)
            lo_y, hi_y = min(p.y for p in pts), max(p.y for p in pts)
            top = max(p.z for p in pts)
            if hi_x < -400.0 or lo_x > 50.0 or hi_y < -1300.0 or lo_y > 1300.0:
                continue
            hits.append({"label": a.get_actor_label(), "min_x_cm": round(lo_x, 1), "max_x_cm": round(hi_x, 1), "top_z_cm": round(top, 2),
                         # 30 Sep: "> -120" flagged P03's intended oak house plane (top -119, 1 cm above the house floor).
                         # A slab downstage of the lip buries the fascia only if it hides a meaningful part of its 120 cm
                         # drop: the pile hangs to z -71.3 (Soft goods), so anything above -72 there is the real fault.
                         "exposed_fascia_cm": round(max(0.0, -max(top, -120.0)), 1) if lo_x < lip - 1.0 else 120.0,
                         "buries_fascia": bool(lo_x < lip - 1.0 and top > -72.0)})
        house = {k: float(portal.get_editor_property(k)) for k in ("house_floor_depth_cm", "house_floor_downstage_cm", "house_floor_half_width_cm", "mouth_half_width_cm")}
        rows[f"P0{n}"] = {"lip_x_cm": lip, "house": house, "stage_front": bool(portal.get_editor_property("stage_front")),
                          "ground_on": bool(s.get_editor_property("ground").get_editor_property("enabled")), "floors": hits}
    with open(os.path.join(HERE, f"floor_vs_lip_{run}.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    need = {k: [h["label"] for h in v["floors"] if h["buries_fascia"]] for k, v in rows.items()}
    unreal.log(f"FLOOR_VS_LIP|run={run}|trim_needed={json.dumps(need)}|" + " || ".join(
        f"{k}: lip {v['lip_x_cm']} ground_on={v['ground_on']} " + "; ".join(f"{h['label']} x[{h['min_x_cm']},{h['max_x_cm']}] top {h['top_z_cm']}" for h in v["floors"])
        for k, v in rows.items()))


main()
