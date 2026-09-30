"""Read-only: Passage 04's END, for Soft goods' backcloth bake and the Arrival timing
(30 Sep). Writes JSON to Saved/CodexStructure/p04_end_colliders.json:
- timing: P04's tail (the last pass -> route end) and last wing intervals, from the
  Show exactly as FInfinityStageCompiler builds them (distance is piecewise linear in
  time, so the end speed is constant and the camera stops dead at the route end);
- the static floor: where Structure 04's boards end, the hangar apron, the hinge line
  and the camera's stop;
- colliders: the last three wing pairs (oriented boxes from the panel instances, at
  their rest BaseWorldTransform and as evaluated now) and every structure instance
  (gridiron, fixtures, lines, portal) within 12 m of the route end.
Mutates nothing. Lean: all work in main()."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p04_end_colliders.json")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def v(x):
    return [round(x.x, 1), round(x.y, 1), round(x.z, 1)]


def obox(transform, bounds_box):
    lo, hi = bounds_box.min, bounds_box.max
    corners = [unreal.Vector(a, b, c) for a in (lo.x, hi.x) for b in (lo.y, hi.y) for c in (lo.z, hi.z)]
    w = [transform.transform_location(p) for p in corners]
    centre = transform.transform_location(unreal.Vector((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2))
    s = transform.scale3d
    r = transform.rotation.rotator()
    return {"min_cm": [round(min(p.x for p in w), 1), round(min(p.y for p in w), 1), round(min(p.z for p in w), 1)],
            "max_cm": [round(max(p.x for p in w), 1), round(max(p.y for p in w), 1), round(max(p.z for p in w), 1)],
            "oriented": {"centre_cm": v(centre),
                         "size_cm": [round(abs((hi.x - lo.x) * s.x), 1), round(abs((hi.y - lo.y) * s.y), 1),
                                     round(abs((hi.z - lo.z) * s.z), 1)],
                         "roll_deg": round(r.roll, 2), "pitch_deg": round(r.pitch, 2), "yaw_deg": round(r.yaw, 2)}}


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    p04 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 04"))
    s04 = next(a for a in actors if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label().endswith("04"))
    pguid = p04.get_editor_property("passage_guid")
    settings = next(s for s in show.get_editor_property("passage_settings") if s.get_editor_property("passage_guid").to_string() == pguid.to_string())
    cues = list(show.get_editor_property("cues"))
    guids = [c.get_editor_property("cue_guid").to_string() for c in cues]
    first = guids.index(settings.get_editor_property("first_cue_guid").to_string())
    last = guids.index(settings.get_editor_property("last_cue_guid").to_string())
    lead_f = settings.get_editor_property("lead_in_frames").value
    tail_f = settings.get_editor_property("tail_frames").value
    lead_d = settings.get_editor_property("lead_in_distance_cm")
    tail_d = settings.get_editor_property("tail_distance_cm")
    wings, d, frame = [], lead_d, lead_f
    for i in range(first, last + 1):
        wp = cues[i].get_editor_property("wing_pair")
        wings.append({"cue": str(cues[i].get_editor_property("label")), "guid": guids[i], "distance_cm": round(d, 2),
                      "pass_s_from_segment_start": round(frame / rate, 3)})
        if i < last:
            d += wp.get_editor_property("gap_to_next_cm")
            frame += wp.get_editor_property("interval_to_next").value
    route = p04.get_editor_property("route")
    route_len = route.get_spline_length()
    speeds = [round((b["distance_cm"] - a["distance_cm"]) / (b["pass_s_from_segment_start"] - a["pass_s_from_segment_start"]), 2)
              for a, b in zip(wings[-4:], wings[-3:])]
    timing = {"tick_rate": rate, "lead_in_s": lead_f / rate, "lead_in_cm": lead_d, "tail_s": tail_f / rate, "tail_cm": tail_d,
              "tail_speed_cm_s": (tail_d / (tail_f / rate)) if tail_f else None, "last_interval_speeds_cm_s": speeds,
              "segment_s": (frame + tail_f) / rate, "total_distance_cm": d + tail_d, "route_length_cm": route_len,
              "stations": len(wings), "last_station_cm": wings[-1]["distance_cm"], "last_wings": wings[-3:],
              "route_end_world": v(route.get_location_at_distance_along_spline(route_len, unreal.SplineCoordinateSpace.WORLD)),
              "route_start_world": v(route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD))}
    g = s04.get_editor_property("ground")
    floor_end_cm = min(wings[-1]["distance_cm"] + g.get_editor_property("apron_cm"), route_len)
    width, gap = g.get_editor_property("board_width_cm"), g.get_editor_property("board_gap_cm")
    lanes = int((s04.get_editor_property("grid_half_width_cm") * 2 + gap) // (width + gap))
    labels = {a.get_actor_label(): a for a in actors}
    apron = labels.get("S4 Hangar Apron")
    root = labels.get("S4 Hangar Root")
    cam = next(a for a in actors if a.get_actor_label().startswith("Scene 4") and "Entry Handoff Camera" in a.get_actor_label())
    apron_box = None
    if apron:
        alo, aext = apron.get_actor_bounds(False)
        apron_box = {"min_cm": v(alo - aext), "max_cm": v(alo + aext), "static": True}
    statics = {"floor_boards_end_route_cm": floor_end_cm,
               "floor_boards_end_world": v(route.get_location_at_distance_along_spline(floor_end_cm, unreal.SplineCoordinateSpace.WORLD)),
               "floor_top_z_cm": g.get_editor_property("floor_height_cm"),
               "floor_half_width_cm": round((lanes * (width + gap) - gap) / 2, 2),
               "slot_width_cm": g.get_editor_property("slot_width_cm"), "slot_inboard_cm": g.get_editor_property("slot_inboard_cm"),
               "apron": apron_box, "hinge_world": v(root.get_actor_location()) if root else None,
               "camera_stop_world": v(cam.get_actor_location()), "camera_label": cam.get_actor_label()}
    panels = []
    last_guids = {w["guid"]: w for w in wings[-3:]}
    for ref in p04.get_editor_property("materialized_panels"):
        cg = ref.get_editor_property("cue_guid").to_string()
        if cg not in last_guids:
            continue
        comp = ref.get_editor_property("component")
        idx = ref.get_editor_property("instance_index")
        mesh = comp.get_editor_property("static_mesh")
        bb = mesh.get_bounding_box()
        now = comp.get_instance_transform(idx, True)
        mats = [m.get_path_name() for m in comp.get_materials() if m]
        panels.append({"cue": last_guids[cg]["cue"], "station_cm": last_guids[cg]["distance_cm"], "side": str(ref.get_editor_property("side")),
                       "mesh": mesh.get_path_name(), "materials": mats,
                       "rest": obox(ref.get_editor_property("base_world_transform"), bb), "evaluated_now": obox(now, bb),
                       "inward_world": v(ref.get_editor_property("inward_world_direction"))})
    near_x = timing["route_end_world"][0] - 1200.0
    pieces = []
    for comp in s04.get_components_by_class(unreal.InstancedStaticMeshComponent):
        name = comp.get_name()
        if name.startswith(("StructureGround", "StructureGrooves", "StructureUnderstage")):
            continue
        bb = comp.get_editor_property("static_mesh").get_bounding_box()
        for i in range(comp.get_instance_count()):
            t = comp.get_instance_transform(i, True)
            if t.translation.x >= near_x:
                b = obox(t, bb)
                b["layer"] = name
                pieces.append(b)
    out = {"units": "UE world cm; P04 runs along +X at y 240000, so route distance ~ world x", "timing": timing,
           "static_floor": statics, "last_wing_panels": panels, "structure_pieces_within_12m_of_route_end": pieces}
    json.dump(out, open(OUT, "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"P04_END_OK|tail_speed={timing['tail_speed_cm_s']}|tail_s={timing['tail_s']}|last_station={timing['last_station_cm']}"
               f"|floor_end={floor_end_cm}|panels={len(panels)}|pieces={len(pieces)}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
