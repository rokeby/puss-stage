"""READ-ONLY (5 Oct, Gary: 'did we take the curve off S02's path?'): per Passage actor, the route spline's shape.
Logs PROBE_ROUTE|passage|auto_fit_straight|points|length_cm|yaw_start|yaw_end|turn_deg|max_off_chord_cm. Changes nothing."""
import json
import math
import os

import unreal

out = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_class().get_name() != "InfinityStagePassageActor":
        continue
    sp = a.get_editor_property("route")
    n = sp.get_number_of_spline_points()
    length = sp.get_spline_length()
    W = unreal.SplineCoordinateSpace.WORLD
    p0, p1 = sp.get_location_at_distance_along_spline(0, W), sp.get_location_at_distance_along_spline(length, W)
    d0, d1 = sp.get_direction_at_distance_along_spline(0, W), sp.get_direction_at_distance_along_spline(length, W)
    y0, y1 = math.degrees(math.atan2(d0.y, d0.x)), math.degrees(math.atan2(d1.y, d1.x))
    cx, cy = p1.x - p0.x, p1.y - p0.y
    cl = math.hypot(cx, cy) or 1.0
    off = 0.0
    for i in range(41):
        q = sp.get_location_at_distance_along_spline(length * i / 40.0, W)
        off = max(off, abs(((q.x - p0.x) * cy - (q.y - p0.y) * cx) / cl))
    row = {"passage": str(a.get_actor_label()), "auto_fit_straight": bool(a.get_editor_property("auto_fit_straight_route")),
           "points": n, "length_cm": round(length, 1), "yaw_start": round(y0, 2), "yaw_end": round(y1, 2),
           "turn_deg": round(((y1 - y0 + 180) % 360) - 180, 2), "max_off_chord_cm": round(off, 1)}
    out.append(row)
    unreal.log("PROBE_ROUTE|" + json.dumps(row))
p = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor",
                 "probe_routes.json")
json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
unreal.log("PROBE_ROUTES_OK|n=%d|out=%s" % (len(out), p))
