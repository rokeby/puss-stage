"""Read-only, for Gary's "they are never visible in the same frame": every local
light in the level (spot, point, rect), by passage, with its shadow setting, and,
for sample camera poses, how many fall inside the camera's view frustum. The
renderer only sets up shadows for lights whose bounds meet the view, so this
shows whether lights in OTHER passages cost anything today. Camera: the rig's
eye height, looking down the route, 25 mm on Super 35, pitch 0. Mutates nothing.
"""
import collections
import json
import math
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "light_visibility_by_passage.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and ed.get_game_world() is None, "PIE is running or no editor world"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
passages = sorted((a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)), key=lambda p: p.get_actor_label())
bands = [(p.get_actor_label()[:10], p.get_actor_location().y) for p in passages]


def passage_of(y):
    label, py = min(bands, key=lambda b: abs(b[1] - y))
    return label if abs(py - y) < 30000 else "other"


lights = []
for a in actors:
    for c in a.get_components_by_class(unreal.LocalLightComponent):
        if not c.get_editor_property("visible") or a.get_editor_property("hidden"):
            continue
        loc = c.get_world_location()
        lights.append({"passage": passage_of(loc.y), "x": loc.x, "y": loc.y, "z": loc.z,
                       "radius": float(c.get_editor_property("attenuation_radius")),
                       "shadows": bool(c.get_editor_property("cast_shadows")),
                       "affects_world": bool(c.get_editor_property("affects_world")),
                       "max_draw": float(c.get_editor_property("max_draw_distance")),
                       "kind": c.get_class().get_name()})
live = [l for l in lights if l["affects_world"]]
totals = collections.defaultdict(lambda: {"lights": 0, "casters": 0})
for l in live:
    totals[l["passage"]]["lights"] += 1
    totals[l["passage"]]["casters"] += int(l["shadows"])

# Frustum test: 25 mm on Super 35 (23.76 x 13.365 mm), looking +X, pitch 0.
half_h = math.atan(11.88 / 25.0)
half_v = math.atan(6.6825 / 25.0)
poses = []
for p in passages:
    label = p.get_actor_label()[:10]
    route = p.get_editor_property("route")
    length = route.get_spline_length()
    for frac in (0.1, 0.5, 0.9):
        t = route.get_transform_at_distance_along_spline(length * frac, unreal.SplineCoordinateSpace.WORLD)
        eye = t.translation + unreal.Vector(0, 0, 150)
        fwd = unreal.MathLibrary.get_forward_vector(t.rotation.rotator())
        poses.append((label, round(frac, 1), eye, unreal.Vector(fwd.x, fwd.y, 0.0).normal()))


def in_view(l, eye, fwd):
    d = unreal.Vector(l["x"] - eye.x, l["y"] - eye.y, l["z"] - eye.z)
    along = d.dot(fwd)
    if along < -l["radius"]:
        return False
    if l["max_draw"] > 0 and d.length() - l["radius"] > l["max_draw"]:
        return False
    right = unreal.Vector(-fwd.y, fwd.x, 0.0)
    side = abs(d.dot(right))
    up = abs(d.z)
    # Sphere against the side and top/bottom planes of a symmetric frustum.
    if side * math.cos(half_h) - max(along, 0.0) * math.sin(half_h) > l["radius"]:
        return False
    if up * math.cos(half_v) - max(along, 0.0) * math.sin(half_v) > l["radius"]:
        return False
    return True


views = []
for label, frac, eye, fwd in poses:
    seen = collections.Counter()
    seen_casters = collections.Counter()
    for l in live:
        if in_view(l, eye, fwd):
            seen[l["passage"]] += 1
            seen_casters[l["passage"]] += int(l["shadows"])
    bins = collections.Counter()
    for l in live:
        if l["shadows"] and in_view(l, eye, fwd):
            dist = math.dist((l["x"], l["y"], l["z"]), (eye.x, eye.y, eye.z)) / 100.0
            for cap in (20, 30, 50, 80):
                bins[f"within_{cap}m"] += int(dist <= cap)
    views.append({"camera_in": label, "at": frac, "in_view_by_passage": dict(seen),
                  "casters_in_view_by_passage": dict(seen_casters), "casters_in_view_by_distance": dict(bins)})
draws = sorted(l["max_draw"] for l in live if l["max_draw"] > 0)
json.dump({"max_draw_quartiles": [draws[int(len(draws) * q)] for q in (0.0, 0.25, 0.5, 0.75)] + [draws[-1]] if draws else [],
           "totals": totals, "views": views, "light_count": len(lights), "live": len(live),
           "max_draw_set": sum(1 for l in live if l["max_draw"] > 0)}, open(OUT, "w"), indent=1)
unreal.log(f"LIGHT_VISIBILITY_OK|lights={len(lights)}|live={len(live)}|poses={len(views)}|mutated=0")
