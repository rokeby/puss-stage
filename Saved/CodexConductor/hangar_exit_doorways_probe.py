"""Read-only PASS 1 survey for the six proposed hangar exit doorways.

This script never evaluates Sequencer, ends PIE, saves a package, or changes an
actor.  It records far-wall/root geometry, surface slots, possible backdrops,
the tagged Exit handoff camera, and a conservative straight-walk obstruction
survey in each hangar's landed dock frame.  The package census must be byte-for-
byte equivalent before and after the survey.

Output: Saved/CodexConductor/hangar_exit_doorways_probe.json
Marker: HANGAR_EXIT_DOORWAYS_PROBE_OK
"""
import datetime
import json
import math
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OUTPUT_NAME = "hangar_exit_doorways_probe.json"
PLAN_PATTERN = "hangar_s%d_plan.json"
WALK_HALF_WIDTH_CM = 60.0
WALK_HEIGHT_CM = 220.0
DOOR_WIDTH_CM = 300.0
DOOR_HEIGHT_CM = 450.0


def package_census():
    def names(values):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in values)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def rot(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def transform_row(actor):
    return {
        "world_location_cm": vec(actor.get_actor_location()),
        "world_rotation_rpy": rot(actor.get_actor_rotation()),
        "world_scale": vec(actor.get_actor_scale3d()),
        "relative_location_cm": vec(actor.root_component.get_editor_property("relative_location")),
        "relative_rotation_rpy": rot(actor.root_component.get_editor_property("relative_rotation")),
        "relative_scale": vec(actor.root_component.get_editor_property("relative_scale3d")),
    }


def object_path(value):
    return None if value is None else str(value.get_path_name())


def box_corners(lo, hi):
    return [unreal.Vector(x, y, z)
            for x in (lo[0], hi[0])
            for y in (lo[1], hi[1])
            for z in (lo[2], hi[2])]


def union_bounds(rows):
    if not rows:
        return None
    return {
        "min": [min(row["min"][axis] for row in rows) for axis in range(3)],
        "max": [max(row["max"][axis] for row in rows) for axis in range(3)],
    }


def component_bounds_in_frame(component, frame):
    """Prefer mesh-local corners; component AABB is a marked fallback."""
    points = []
    source = "component_aabb_fallback"
    if isinstance(component, unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        if mesh is not None:
            try:
                bounds = mesh.get_bounding_box()
                local_min = bounds.min
                local_max = bounds.max
                component_transform = component.get_component_transform()
                points = [unreal.MathLibrary.transform_location(component_transform, point)
                          for point in box_corners(vec(local_min), vec(local_max))]
                source = "static_mesh_local_box"
            except Exception:
                points = []
    if not points:
        origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
        lo = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
        hi = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
        points = box_corners(lo, hi)
    local = [unreal.MathLibrary.inverse_transform_location(frame, point) for point in points]
    return {
        "min": [min(getattr(point, axis) for point in local) for axis in ("x", "y", "z")],
        "max": [max(getattr(point, axis) for point in local) for axis in ("x", "y", "z")],
        "source": source,
    }


def materials(component):
    result = []
    count = int(component.get_num_materials()) if hasattr(component, "get_num_materials") else 0
    for slot in range(count):
        material = component.get_material(slot)
        result.append({"slot": slot, "material": object_path(material)})
    return result


def actor_row(actor, root_frame):
    components = list(actor.get_components_by_class(unreal.PrimitiveComponent))
    bounds = []
    component_rows = []
    for component in components:
        if not component.is_visible():
            continue
        row = component_bounds_in_frame(component, root_frame)
        bounds.append(row)
        component_rows.append({
            "name": str(component.get_name()),
            "class": str(component.get_class().get_name()),
            "bounds_dock_cm": row,
            "static_mesh": object_path(component.get_editor_property("static_mesh"))
                           if isinstance(component, unreal.StaticMeshComponent) else None,
            "materials": materials(component),
        })
    parent = actor.get_attach_parent_actor()
    return {
        "label": str(actor.get_actor_label()),
        "class": str(actor.get_class().get_name()),
        "path": object_path(actor),
        "parent_label": str(parent.get_actor_label()) if parent is not None else None,
        "tags": sorted(str(tag) for tag in actor.tags),
        "transform": transform_row(actor),
        "bounds_dock_cm": union_bounds(bounds),
        "components": component_rows,
    }


def cine_camera_row(actor, dock):
    component = actor.get_cine_camera_component()
    location = actor.get_actor_location()
    dock_location = unreal.MathLibrary.inverse_transform_location(dock, location)
    focus = component.get_editor_property("focus_settings")
    return {
        "label": str(actor.get_actor_label()),
        "path": object_path(actor),
        "tags": sorted(str(tag) for tag in actor.tags),
        "world_location_cm": vec(location),
        "dock_location_cm": vec(dock_location),
        "world_rotation_rpy": rot(actor.get_actor_rotation()),
        "focal_length_mm": float(component.get_editor_property("current_focal_length")),
        "manual_focus_distance_cm": float(focus.get_editor_property("manual_focus_distance")),
    }


def segment_intersects_expanded_aabb(start, end, bounds, expand):
    """2-D slab test against an XY AABB expanded by the walk half-width."""
    lo = [float(bounds["min"][0]) - expand, float(bounds["min"][1]) - expand]
    hi = [float(bounds["max"][0]) + expand, float(bounds["max"][1]) + expand]
    t0, t1 = 0.0, 1.0
    for axis in (0, 1):
        delta = float(end[axis]) - float(start[axis])
        if abs(delta) < 1.0e-9:
            if float(start[axis]) < lo[axis] or float(start[axis]) > hi[axis]:
                return False
            continue
        enter = (lo[axis] - float(start[axis])) / delta
        leave = (hi[axis] - float(start[axis])) / delta
        if enter > leave:
            enter, leave = leave, enter
        t0, t1 = max(t0, enter), min(t1, leave)
        if t0 > t1:
            return False
    return True


def ignored_for_walk(actor, scene):
    label = str(actor.get_actor_label())
    cls = str(actor.get_class().get_name())
    if label.startswith("S%d Hangar" % scene) or label.startswith("S%d Uplight" % scene):
        return True
    if label.startswith("S%d Practical" % scene) or label.startswith("S%d Lattice" % scene):
        return True
    if label.startswith("Scene %d" % scene) and "Camera" in label:
        return True
    if any(word in cls for word in ("Camera", "Light", "PostProcess", "Sky", "Fog", "Volume")):
        return True
    if any(word in label for word in ("Floor", "Landscape", "Ground", "Apron", "Backdrop")):
        return True
    return False


def straight_walk(actors, scene, dock, start, end, floor_z):
    blockers = []
    for actor in actors:
        if ignored_for_walk(actor, scene):
            continue
        component_bounds = []
        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            if component.is_visible():
                component_bounds.append(component_bounds_in_frame(component, dock))
        bounds = union_bounds(component_bounds)
        if bounds is None:
            continue
        if bounds["max"][2] < floor_z or bounds["min"][2] > floor_z + WALK_HEIGHT_CM:
            continue
        if segment_intersects_expanded_aabb(start, end, bounds, WALK_HALF_WIDTH_CM):
            blockers.append({
                "label": str(actor.get_actor_label()),
                "class": str(actor.get_class().get_name()),
                "bounds_dock_cm": bounds,
            })
    blockers.sort(key=lambda row: row["label"])
    return {
        "method": "conservative visible-component dock AABB corridor; not navmesh/collision proof",
        "corridor_width_cm": 2.0 * WALK_HALF_WIDTH_CM,
        "walk_height_cm": WALK_HEIGHT_CM,
        "clear": not blockers,
        "blockers": blockers,
    }


def load_plan(saved_dir, scene):
    path = os.path.join(saved_dir, "CodexStructure", PLAN_PATTERN % scene)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle), path


def one_exit_camera(actors, scene):
    tagged = [actor for actor in actors
              if isinstance(actor, unreal.CineCameraActor)
              and actor.actor_has_tag("InfinityStage.SceneExit")
              and str(actor.get_actor_label()).startswith("Scene %d " % scene)]
    if len(tagged) == 1:
        return tagged
    return [actor for actor in actors
            if isinstance(actor, unreal.CineCameraActor)
            and str(actor.get_actor_label()).startswith("Scene %d " % scene)
            and "Exit Handoff Camera" in str(actor.get_actor_label())]


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("HANGAR_EXIT_DOORWAYS_PROBE_STOPPED|run=%s|reason=PIE_OR_SIE_ACTIVE" % run)
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        raise RuntimeError("HANGAR_EXIT_DOORWAYS_PROBE_STOPPED|run=%s|reason=WRONG_WORLD" % run)

    before = package_census()
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by_label = {}
    for actor in actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
    saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    scenes = []
    for scene in range(1, 7):
        plan, plan_path = load_plan(saved_dir, scene)
        root_label = "S%d Hangar Root" % scene
        roots = by_label.get(root_label, [])
        if len(roots) != 1:
            raise RuntimeError("S%d root count is %d, expected 1" % (scene, len(roots)))
        root = roots[0]
        root_frame = root.get_actor_transform()
        dock_data = plan["dock"]
        dock = unreal.Transform(
            location=unreal.Vector(*dock_data["loc"]),
            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(dock_data["yaw"])),
        )
        far_walls = [actor for actor in actors
                     if str(actor.get_actor_label()).startswith("S%d Hangar Far Wall" % scene)
                     and "Hinge" not in str(actor.get_actor_label())]
        backdrops = [actor for actor in actors
                     if str(actor.get_actor_label()).startswith("S%d " % scene)
                     and "Backdrop" in str(actor.get_actor_label())]
        cameras = one_exit_camera(actors, scene)
        wall_rows = [actor_row(actor, root_frame) for actor in far_walls]
        backdrop_rows = [actor_row(actor, dock) for actor in backdrops]
        camera_rows = [cine_camera_row(actor, dock) for actor in cameras]
        wall_bounds = union_bounds([row["bounds_dock_cm"] for row in wall_rows
                                    if row["bounds_dock_cm"] is not None])
        hangar = plan["hangar"]
        door_center = [float(hangar["depth"]), 0.0, float(hangar.get("hinge_z", 0.0)) + DOOR_HEIGHT_CM / 2.0]
        distance = None
        walk = None
        if len(camera_rows) == 1:
            camera_location = camera_rows[0]["dock_location_cm"]
            distance = math.sqrt(sum((camera_location[index] - door_center[index]) ** 2
                                     for index in range(3)))
            walk = straight_walk(actors, scene, dock, camera_location, door_center,
                                 float(hangar.get("hinge_z", 0.0)))
        scenes.append({
            "scene": scene,
            "plan_source": os.path.relpath(plan_path, unreal.Paths.convert_relative_path_to_full(
                unreal.Paths.project_dir())).replace("\\", "/"),
            "dock": dock_data,
            "hangar": {key: hangar[key] for key in
                       ("depth", "half_w", "height", "wall_t", "roof", "hinge_z")},
            "root_count": len(roots),
            "root": actor_row(root, root_frame),
            "landed_preview_root_up": abs(float(
                root.root_component.get_editor_property("relative_rotation").pitch)) <= 0.05,
            "far_wall_count": len(far_walls),
            "far_walls": wall_rows,
            "far_wall_union_bounds_dock_cm": wall_bounds,
            "backdrop_count": len(backdrops),
            "backdrops": backdrop_rows,
            "exit_camera_count": len(cameras),
            "exit_cameras": camera_rows,
            "draft_door_center_dock_cm": door_center,
            "camera_to_door_distance_cm": distance,
            "straight_walk": walk,
        })

    after = package_census()
    if after != before:
        raise RuntimeError("HANGAR_EXIT_DOORWAYS_PROBE_STOPPED|run=%s|reason=CENSUS_CHANGED|before=%s|after=%s" %
                           (run, json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True)))
    report = {
        "schema_version": 1,
        "run": run,
        "world": EXPECTED_WORLD,
        "door_draft_cm": {"width": DOOR_WIDTH_CM, "height": DOOR_HEIGHT_CM},
        "census_before": before,
        "census_after": after,
        "scenes": scenes,
    }
    output = os.path.join(saved_dir, "CodexConductor", OUTPUT_NAME)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    unreal.log("HANGAR_EXIT_DOORWAYS_PROBE_OK|run=%s|scenes=6|census_unchanged=1|mutated=0|output=%s" %
               (run, output))


main()
