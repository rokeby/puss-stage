"""Read-only audit before the C++ structure pass replaces the Python gridiron.

Predicts what AInfinityStageStructureActor will derive (width measured from the
route line, not from the panel midpoint), checks whether the Python preview's
components survived save/reload, and records the rig facts the next jobs need:
landscape, fog, shadow-casting local lights. Mutates nothing and saves nothing.
"""
import collections
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LEGACY_TAG = "InfinityStage.Gridiron"
OVERHANG = 220.0

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
assert ed.get_game_world() is None, "PIE active - stop PIE first"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = list(sub.get_all_level_actors())


def prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception as exc:  # property names drift between engine versions
        return f"unreadable: {exc.__class__.__name__}"


def side_of(ref):
    return str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")


report = {"passages": {}, "legacy_gridiron": [], "landscape": [], "fog": [], "lights": {}}

for passage in actors:
    if passage.get_class().get_name() != "InfinityStagePassageActor":
        continue
    label = passage.get_actor_label()
    route = passage.get_editor_property("route")
    points = route.get_number_of_spline_points()
    by_cue = collections.defaultdict(dict)
    for ref in passage.get_editor_property("materialized_panels"):
        side = side_of(ref)
        if side in ("LEFT", "RIGHT"):
            g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
            by_cue[g][side] = ref.get_editor_property("base_world_transform").translation
    route_half = 0.0
    mid_half = 0.0
    asym = 0.0
    for sides in by_cue.values():
        locs = list(sides.values())
        centre = unreal.Vector(sum(v.x for v in locs) / len(locs), sum(v.y for v in locs) / len(locs),
                               sum(v.z for v in locs) / len(locs))
        key = route.find_input_key_closest_to_world_location(centre)
        frame = route.get_transform_at_spline_input_key(key, unreal.SplineCoordinateSpace.WORLD, False)
        origin = frame.translation
        across = unreal.MathLibrary.transform_direction(frame, unreal.Vector(0.0, 1.0, 0.0))
        lateral = [(v - origin).dot(across) for v in locs]
        route_half = max(route_half, max(abs(x) for x in lateral))
        if len(lateral) == 2:
            mid_half = max(mid_half, abs(lateral[0] - lateral[1]) / 2.0)
            asym = max(asym, abs(lateral[0] + lateral[1]) / 2.0)
    report["passages"][label] = {
        "materialized_pairs": int(passage.get_editor_property("materialized_wing_pair_count")),
        "stations_with_side_panels": len(by_cue),
        "route_points": points,
        "route_length_cm": round(route.get_spline_length()),
        "auto_fit": bool(passage.get_editor_property("auto_fit_straight_route")),
        "actor_location": [round(c) for c in (passage.get_actor_location().x, passage.get_actor_location().y,
                                              passage.get_actor_location().z)],
        "actor_yaw": round(passage.get_actor_rotation().yaw, 2),
        "half_width_from_route_line_cm": round(route_half, 1),
        "half_width_python_style_cm": round(mid_half, 1),
        "max_corridor_offset_from_route_cm": round(asym, 1),
        "predicted_grid_half_span_cm": round(route_half + OVERHANG, 1),
    }

for a in actors:
    tags = [str(t) for t in a.get_editor_property("tags")]
    if LEGACY_TAG in tags:
        isms = a.get_components_by_class(unreal.InstancedStaticMeshComponent)
        report["legacy_gridiron"].append({
            "label": a.get_actor_label(),
            "components": len(isms),
            "instances": sum(c.get_instance_count() for c in isms),
        })
    cls = a.get_class().get_name()
    if "Landscape" in cls:
        report["landscape"].append({"label": a.get_actor_label(), "class": cls})
    if cls == "ExponentialHeightFog":
        fc = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
        report["fog"].append({
            "label": a.get_actor_label(),
            "density": prop(fc, "fog_density"),
            "height_falloff": prop(fc, "fog_height_falloff"),
            "volumetric": prop(fc, "enable_volumetric_fog"),
            "extinction_scale": prop(fc, "volumetric_fog_extinction_scale"),
            "scattering_distribution": prop(fc, "volumetric_fog_scattering_distribution"),
            "view_distance": prop(fc, "volumetric_fog_distance"),
        })

counts = collections.Counter()
for a in actors:
    for lc in a.get_components_by_class(unreal.LocalLightComponent):
        kind = lc.get_class().get_name()
        counts[kind + ".total"] += 1
        if lc.get_editor_property("cast_shadows"):
            counts[kind + ".shadow"] += 1
        if lc.get_editor_property("cast_volumetric_shadow"):
            counts[kind + ".volumetric_shadow"] += 1
report["lights"] = dict(sorted(counts.items()))

d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
     "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
report["dirty"] = d
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "structure_audit.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(report, open(out, "w"), indent=1, default=str)
legacy = sum(g["instances"] for g in report["legacy_gridiron"])
unreal.log(f"STRUCTURE_AUDIT_OK|passages={len(report['passages'])}|legacy_actors={len(report['legacy_gridiron'])}"
           f"|legacy_instances={legacy}|landscape={len(report['landscape'])}"
           f"|dirty={len(d['content'])}+{len(d['maps'])}|mutated=0")
