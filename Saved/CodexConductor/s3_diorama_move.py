"""Plan, apply, or revert the Scene 3 clam diorama move.

Dry run is the default.  S3_DIORAMA_APPLY and S3_DIORAMA_REVERT are accepted
only from the dedicated wrappers beside this file.  The pure planning helpers
remain importable by test_s3_diorama_move_plan.py without Unreal.
"""
import datetime
import itertools
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
LANDED_ROOT_DOCK = (500.0, 0.0, -120.0)
PEDESTAL_TARGET = (3500.0, 0.0)
BOX_X = (900.0, 6100.0)
BOX_Y = (-900.0, 900.0)

PEDESTAL_LABEL = "Clam_Pedastal"
GROUP_LABELS = (
    PEDESTAL_LABEL,
    "Clam_with_Pearl_Clam_with_Pearl_0",
    "source_Anim",
    "PointLight",
)
FIGURE_LABELS = (
    "Shore01_M56 Clam",
    "Shore02_F52 Clam",
    "Shore03_M59 Clam",
    "Shore04_F55 Clam",
    "Shore05_M53 Clam",
    "Shore06_F25 Clam",
)
TARGET_LABELS = GROUP_LABELS + FIGURE_LABELS
STRIKE_LABELS = (
    "S3 Strike Cyc 1",
    "S3 Strike Cyc 2",
    "S3 Strike Cyc 3",
    "S3 Strike Fill L",
    "S3 Strike Fill R",
    "S3 Strike Key",
)
SLOT_ANGLES = (0.0, 55.0, -55.0, 110.0, -110.0, 160.0)
SLOT_RADII = (260.0, 320.0, 260.0, 320.0, 260.0, 320.0)

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "s3_diorama_move_record.json")


class PlanError(ValueError):
    pass


def normalize_degrees(value):
    return (float(value) + 180.0) % 360.0 - 180.0


def bearing_degrees(origin, target):
    dx = float(target[0]) - float(origin[0])
    dy = float(target[1]) - float(origin[1])
    if math.hypot(dx, dy) < 0.001:
        return None
    return math.degrees(math.atan2(dy, dx))


def bounds_from_points(points):
    if not points:
        raise PlanError("cannot form bounds from no points")
    return {
        "min": [min(float(p[i]) for p in points) for i in range(3)],
        "max": [max(float(p[i]) for p in points) for i in range(3)],
    }


def box_corners(bounds):
    return [
        [x, y, z]
        for x in (float(bounds["min"][0]), float(bounds["max"][0]))
        for y in (float(bounds["min"][1]), float(bounds["max"][1]))
        for z in (float(bounds["min"][2]), float(bounds["max"][2]))
    ]


def transformed_local_bounds(local_bounds, location, yaw_degrees, scale=(1.0, 1.0, 1.0)):
    angle = math.radians(float(yaw_degrees))
    c, s = math.cos(angle), math.sin(angle)
    points = []
    for x, y, z in box_corners(local_bounds):
        x *= float(scale[0])
        y *= float(scale[1])
        z *= float(scale[2])
        points.append([
            float(location[0]) + c * x - s * y,
            float(location[1]) + s * x + c * y,
            float(location[2]) + z,
        ])
    return bounds_from_points(points)


def aabbs_overlap(a, b, tolerance_cm=0.01):
    return all(
        min(float(a["max"][axis]), float(b["max"][axis]))
        - max(float(a["min"][axis]), float(b["min"][axis]))
        > float(tolerance_cm)
        for axis in range(3)
    )


def validate_ring_boxes(rows):
    outside = []
    for row in rows:
        bounds = row["planned_bounds"]
        if (
            bounds["min"][0] < BOX_X[0] - 0.01
            or bounds["max"][0] > BOX_X[1] + 0.01
            or bounds["min"][1] < BOX_Y[0] - 0.01
            or bounds["max"][1] > BOX_Y[1] + 0.01
        ):
            outside.append({"label": row["label"], "bounds": bounds})
    if outside:
        raise PlanError("figure AABB outside landed box: " + json.dumps(outside, sort_keys=True))
    overlaps = []
    for left, right in itertools.combinations(rows, 2):
        if aabbs_overlap(left["planned_bounds"], right["planned_bounds"]):
            overlaps.append([left["label"], right["label"]])
    if overlaps:
        raise PlanError("figure AABBs overlap: " + json.dumps(overlaps))
    return True


def validate_target_guards(rows):
    failures = []
    by_label = {str(row["label"]): row for row in rows}
    for label in TARGET_LABELS:
        row = by_label.get(label)
        count = 0 if row is None else int(row.get("count", 1))
        if count != 1:
            failures.append("%s count=%d" % (label, count))
            continue
        if row.get("parent"):
            failures.append("%s attached_to=%s" % (label, row["parent"]))
        references = list(row.get("show_references") or [])
        if references:
            failures.append("%s show_references=%s" % (label, json.dumps(references, sort_keys=True)))
    if failures:
        raise PlanError(" || ".join(failures))
    return True


def _slot_rows():
    rows = []
    for index, (angle, radius) in enumerate(zip(SLOT_ANGLES, SLOT_RADII)):
        radians = math.radians(angle)
        rows.append({
            "index": index,
            "angle_deg": angle,
            "radius_cm": radius,
            "position_xy": [
                PEDESTAL_TARGET[0] + radius * math.cos(radians),
                PEDESTAL_TARGET[1] + radius * math.sin(radians),
            ],
        })
    return rows


def assign_nearest(figures, slots):
    """Minimum total XY travel; labels and slot indexes make ties deterministic."""
    ordered = sorted(figures, key=lambda row: row["label"])
    best = None
    best_assignment = None
    for permutation in itertools.permutations(range(len(slots))):
        cost = 0.0
        for row, slot_index in zip(ordered, permutation):
            x, y = row["location"][:2]
            sx, sy = slots[slot_index]["position_xy"]
            cost += (float(x) - sx) ** 2 + (float(y) - sy) ** 2
        key = (round(cost, 6), permutation)
        if best is None or key < best:
            best = key
            best_assignment = permutation
    return {row["label"]: slots[index] for row, index in zip(ordered, best_assignment)}


def plan_diorama(targets):
    missing = [label for label in TARGET_LABELS if label not in targets]
    if missing:
        raise PlanError("missing planning targets: " + ", ".join(missing))
    pedestal = targets[PEDESTAL_LABEL]
    pedestal_before = pedestal["location"]
    delta = [
        PEDESTAL_TARGET[0] - float(pedestal_before[0]),
        PEDESTAL_TARGET[1] - float(pedestal_before[1]),
        0.0,
    ]
    planned = []
    for label in GROUP_LABELS:
        row = targets[label]
        before_location = [float(v) for v in row["location"]]
        before_rotation = [float(v) for v in row["rotation"]]
        planned.append({
            "label": label,
            "kind": "translated_group",
            "before_location": before_location,
            "planned_location": [
                before_location[0] + delta[0],
                before_location[1] + delta[1],
                before_location[2],
            ],
            "before_rotation": before_rotation,
            "planned_rotation": list(before_rotation),
        })

    figures = [targets[label] for label in FIGURE_LABELS]
    slots = _slot_rows()
    assignments = assign_nearest(figures, slots)
    figure_rows = []
    for label in FIGURE_LABELS:
        row = targets[label]
        slot = assignments[label]
        before_location = [float(v) for v in row["location"]]
        before_rotation = [float(v) for v in row["rotation"]]
        planned_location = [
            float(slot["position_xy"][0]),
            float(slot["position_xy"][1]),
            before_location[2],
        ]
        old_bearing = bearing_degrees(before_location, pedestal_before)
        new_bearing = bearing_degrees(planned_location, [PEDESTAL_TARGET[0], PEDESTAL_TARGET[1], 0.0])
        ambiguous = old_bearing is None
        yaw_offset = 0.0 if ambiguous else normalize_degrees(before_rotation[2] - old_bearing)
        planned_yaw = normalize_degrees(new_bearing + yaw_offset)
        planned_rotation = [before_rotation[0], before_rotation[1], planned_yaw]
        planned_bounds = transformed_local_bounds(
            row["local_bounds"], planned_location, planned_yaw, row.get("scale", (1.0, 1.0, 1.0))
        )
        figure = {
            "label": label,
            "kind": "ring_figure",
            "slot_index": int(slot["index"]),
            "slot_angle_deg": float(slot["angle_deg"]),
            "slot_radius_cm": float(slot["radius_cm"]),
            "before_location": before_location,
            "planned_location": planned_location,
            "before_rotation": before_rotation,
            "planned_rotation": planned_rotation,
            "current_bearing_to_clam_deg": old_bearing,
            "preserved_yaw_offset_deg": yaw_offset,
            "yaw_offset_ambiguous": ambiguous,
            "planned_bounds": planned_bounds,
        }
        planned.append(figure)
        figure_rows.append(figure)
    validate_ring_boxes(figure_rows)
    centroid = [
        sum(row["planned_location"][axis] for row in figure_rows) / len(figure_rows)
        for axis in range(3)
    ]
    return {
        "dock_origin_world": list(DOCK_ORIGIN),
        "dock_yaw_deg": DOCK_YAW,
        "group_delta_xy_cm": delta,
        "pedestal_target_dock_xy_cm": list(PEDESTAL_TARGET),
        "ring_centroid_dock_cm": centroid,
        "targets": planned,
    }


def _package_path(package):
    value = package.get_path_name() if hasattr(package, "get_path_name") else package.get_name()
    return str(value).split(".", 1)[0]


def package_census():
    return {
        "maps": sorted(_package_path(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_package_path(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_DIORAMA_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def actor_index(actors):
    result = {}
    for actor in actors:
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def one_actor(index, label, run):
    found = index.get(label, [])
    if len(found) != 1:
        stop(run, "target_label=%s|count=%d" % (label, len(found)))
    return found[0]


def plain_transform(actor):
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    return {
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def _unreal_box_corners(minimum, maximum):
    return [
        unreal.Vector(x, y, z)
        for x in (minimum.x, maximum.x)
        for y in (minimum.y, maximum.y)
        for z in (minimum.z, maximum.z)
    ]


def actor_local_bounds(actor):
    actor_world = actor.get_actor_transform()
    points = []
    sources = []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        if mesh is None:
            continue
        box = mesh.get_bounding_box()
        component_world = unreal.Transform(
            location=component.get_world_location(),
            rotation=component.get_world_rotation(),
            scale=component.get_world_scale(),
        )
        for mesh_point in _unreal_box_corners(box.min, box.max):
            world_point = unreal.MathLibrary.transform_location(component_world, mesh_point)
            local = unreal.MathLibrary.inverse_transform_location(actor_world, world_point)
            points.append([float(local.x), float(local.y), float(local.z)])
        sources.append(mesh.get_path_name())
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh = component.get_skeletal_mesh_asset()
        if mesh is None:
            continue
        mesh_bounds = mesh.get_bounds()
        origin = mesh_bounds.origin
        extent = mesh_bounds.box_extent
        minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        component_world = unreal.Transform(
            location=component.get_world_location(),
            rotation=component.get_world_rotation(),
            scale=component.get_world_scale(),
        )
        for mesh_point in _unreal_box_corners(minimum, maximum):
            world_point = unreal.MathLibrary.transform_location(component_world, mesh_point)
            local = unreal.MathLibrary.inverse_transform_location(actor_world, world_point)
            points.append([float(local.x), float(local.y), float(local.z)])
        sources.append(mesh.get_path_name())
    if not points:
        origin, extent = actor.get_actor_bounds(False, True)
        minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        for world_point in _unreal_box_corners(minimum, maximum):
            local = unreal.MathLibrary.inverse_transform_location(actor_world, world_point)
            points.append([float(local.x), float(local.y), float(local.z)])
        sources.append("actor_bounds_fallback")
    return bounds_from_points(points), sorted(sources)


def _actor_asset_tokens(actor):
    tokens = {
        str(actor.get_path_name()),
        str(actor.get_outermost().get_name()),
        str(actor.get_class().get_path_name()),
    }
    for component_class, property_name in (
        (unreal.StaticMeshComponent, "static_mesh"),
        (unreal.SkeletalMeshComponent, "skeletal_mesh_asset"),
    ):
        for component in actor.get_components_by_class(component_class):
            try:
                asset = component.get_editor_property(property_name)
            except Exception:
                asset = None
            if asset is not None:
                tokens.add(str(asset.get_path_name()))
                tokens.add(str(asset.get_class().get_path_name()))
    return sorted(token for token in tokens if token.startswith("/") and len(token) > 2)


def show_references(show, targets, all_actors):
    sections = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        label = str(cue.get_editor_property("label"))
        sections.append(("cues[%d]:%s" % (index, label), str(cue)))
    for index, row in enumerate(show.get_editor_property("passage_settings")):
        sections.append(("passage_settings[%d]" % index, str(row)))
    for index, row in enumerate(show.get_editor_property("music_rails")):
        sections.append(("music_rails[%d]" % index, str(row)))
    sections.append(("managed_master_sequence", str(show.get_editor_property("managed_master_sequence"))))
    sections.append(("wing_library", str(show.get_editor_property("wing_library"))))

    managed = {}
    for owner in all_actors:
        try:
            values = list(owner.get_editor_property("managed_attachment_actors"))
        except Exception:
            continue
        for value in values:
            if value is not None:
                managed.setdefault(value.get_path_name(), []).append(owner.get_actor_label())

    result = {}
    for label, actor in targets.items():
        references = []
        for tag in [str(value) for value in actor.get_editor_property("tags")]:
            if tag.startswith("InfinityStage.Attachment."):
                references.append("attachment_tag:" + tag)
        for owner in managed.get(actor.get_path_name(), []):
            references.append("managed_attachment_actors:" + str(owner))
        for token in _actor_asset_tokens(actor):
            for source, text in sections:
                if token in text:
                    references.append("%s soft_path=%s" % (source, token))
        result[label] = sorted(set(references))
    return result


def _dock_transform():
    return unreal.Transform(
        location=unreal.Vector(*DOCK_ORIGIN),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW),
    )


def _dock_location(actor, dock):
    value = unreal.MathLibrary.inverse_transform_location(dock, actor.get_actor_location())
    return [float(value.x), float(value.y), float(value.z)]


def _relative_to_root(actor, root, run):
    if actor is root:
        return unreal.Transform()
    parent = actor.get_attach_parent_actor()
    if parent is None:
        stop(run, "strike=%s|reason=no_parent" % actor.get_actor_label())
    relative = actor.root_component.get_relative_transform()
    while parent is not root:
        grandparent = parent.get_attach_parent_actor()
        if grandparent is None:
            stop(run, "strike=%s|reason=not_under_S3_Hangar_Root" % actor.get_actor_label())
        relative = unreal.MathLibrary.compose_transforms(
            relative, parent.root_component.get_relative_transform()
        )
        parent = grandparent
    return relative


def strike_aim_report(index, centroid_dock, dock, run):
    root = one_actor(index, "S3 Hangar Root", run)
    landed_root = unreal.Transform(
        location=dock.transform_location(unreal.Vector(*LANDED_ROOT_DOCK)),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )
    target_world = dock.transform_location(unreal.Vector(*centroid_dock))
    rows = []
    for label in STRIKE_LABELS:
        actor = one_actor(index, label, run)
        relative = _relative_to_root(actor, root, run)
        landed = unreal.MathLibrary.compose_transforms(relative, landed_root)
        location = landed.translation
        rotation = landed.rotation.rotator()
        pitch = math.radians(float(rotation.pitch))
        yaw = math.radians(float(rotation.yaw))
        forward = [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)]
        to_target = [
            float(target_world.x - location.x),
            float(target_world.y - location.y),
            float(target_world.z - location.z),
        ]
        length = math.sqrt(sum(value * value for value in to_target))
        if length < 0.001:
            stop(run, "strike=%s|reason=target_at_light" % label)
        direction = [value / length for value in to_target]
        dot = max(-1.0, min(1.0, sum(forward[i] * direction[i] for i in range(3))))
        dock_location = unreal.MathLibrary.inverse_transform_location(dock, location)
        rows.append({
            "label": label,
            "landed_location_dock_cm": [float(dock_location.x), float(dock_location.y), float(dock_location.z)],
            "landed_rotation_deg": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "aim_error_deg": math.degrees(math.acos(dot)),
        })
    return rows


def _assert_context(editor, world, run, revert):
    world_path = world.get_outermost().get_name() if world is not None else None
    if world_path != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD|world=%s" % world_path)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if revert and not os.path.exists(RECORD):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    if not revert and os.path.exists(RECORD):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")


def _live_plan(actors, index, run):
    target_actors = {label: one_actor(index, label, run) for label in TARGET_LABELS}
    show = unreal.load_asset(SHOW_PATH)
    if show is None:
        stop(run, "reason=SHOW_ASSET_DID_NOT_LOAD")
    references = show_references(show, target_actors, actors)
    guard_rows = []
    for label in TARGET_LABELS:
        actor = target_actors[label]
        parent = actor.get_attach_parent_actor()
        guard_rows.append({
            "label": label,
            "count": len(index.get(label, [])),
            "parent": parent.get_actor_label() if parent else None,
            "show_references": references[label],
        })
    try:
        validate_target_guards(guard_rows)
    except PlanError as exc:
        stop(run, "reason=TARGET_GUARD|detail=" + str(exc))

    dock = _dock_transform()
    target_rows = {}
    for label, actor in target_actors.items():
        transform = plain_transform(actor)
        local_bounds, bounds_sources = actor_local_bounds(actor)
        target_rows[label] = {
            "label": label,
            "location": _dock_location(actor, dock),
            "rotation": transform["rotation"],
            "scale": transform["scale"],
            "world_before": transform,
            "local_bounds": local_bounds,
            "bounds_sources": bounds_sources,
        }
    try:
        plan = plan_diorama(target_rows)
    except PlanError as exc:
        stop(run, "reason=PLAN_INVALID|detail=" + str(exc))
    plan["guards"] = guard_rows
    plan["strike_aim"] = strike_aim_report(index, plan["ring_centroid_dock_cm"], dock, run)
    return plan, target_actors, dock


def _world_transform_for_row(row, target_actor, dock):
    location = dock.transform_location(unreal.Vector(*row["planned_location"]))
    rotation = row["planned_rotation"]
    scale = target_actor.get_actor_scale3d()
    return {
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation": [float(rotation[0]), float(rotation[1]), float(rotation[2] + DOCK_YAW)],
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def set_plain_transform(actor, transform):
    # Without modify() the setters move the actor but never dirty the level (run 132809:
    # read-back passed, census empty, nothing to save). s3_cast_reveal_apply.py does the same.
    actor.modify()
    root = actor.get_editor_property("root_component")
    if root is not None:
        root.modify()
    actor.set_actor_scale3d(unreal.Vector(*transform["scale"]))
    actor.set_actor_rotation(
        unreal.Rotator(
            roll=transform["rotation"][0],
            pitch=transform["rotation"][1],
            yaw=transform["rotation"][2],
        ),
        False,
    )
    actor.set_actor_location(unreal.Vector(*transform["location"]), False, True)


def transform_errors(actor, wanted):
    got = plain_transform(actor)
    location = max(abs(got["location"][i] - wanted["location"][i]) for i in range(3))
    rotation = max(
        abs(normalize_degrees(got["rotation"][i] - wanted["rotation"][i]))
        for i in range(3)
    )
    scale = max(abs(got["scale"][i] - wanted["scale"][i]) for i in range(3))
    return location, rotation, scale


def _package_filename(project, package_name, extension):
    if not package_name.startswith("/Game/"):
        raise RuntimeError("non-project package cannot be backed up: " + package_name)
    return os.path.join(project, "Content", *package_name[len("/Game/"):].split("/")) + extension


def _backup_files(project, targets, prefix, stamp, run):
    backup = os.path.join(project, "Backups", prefix + stamp.strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(backup):
        stop(run, "reason=BACKUP_EXISTS|path=" + backup)
    level_file = _package_filename(project, EXPECTED_WORLD, ".umap")
    files = [level_file]
    for actor in targets.values():
        package = str(actor.get_outermost().get_name()).split(".", 1)[0]
        if package != EXPECTED_WORLD:
            files.append(_package_filename(project, package, ".uasset"))
    files = sorted(set(files))
    missing = [path for path in files if not os.path.isfile(path)]
    if missing:
        stop(run, "reason=BACKUP_SOURCE_MISSING|files=" + json.dumps(missing))
    os.makedirs(backup)
    copied = []
    content = os.path.join(project, "Content")
    for source in files:
        relative = os.path.relpath(source, content)
        destination = os.path.join(backup, "Content", relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative.replace("\\", "/"))
    return backup, copied


def _assert_only_level_dirty(run):
    census = package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        stop(run, "reason=DIRTY_CENSUS_NOT_EXACT_LEVEL|census=" + json.dumps(census, sort_keys=True))
    return census


def _readback(targets, wanted, run):
    report = []
    for label in TARGET_LABELS:
        location, rotation, scale = transform_errors(targets[label], wanted[label])
        if location > 0.1 or rotation > 0.01 or scale > 0.001:
            stop(
                run,
                "reason=TRANSFORM_READBACK|label=%s|location_cm=%.6f|rotation_deg=%.6f|scale=%.6f"
                % (label, location, rotation, scale),
            )
        report.append({"label": label, "location_error_cm": location, "rotation_error_deg": rotation})
    return report


def _write_record(record):
    with open(RECORD, "x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _load_record(run):
    try:
        with open(RECORD, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        stop(run, "reason=RECORD_READ_FAILED|detail=" + str(exc))


def _apply(plan, targets, dock, run):
    stamp = datetime.datetime.now()
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup, copied = _backup_files(project, targets, "PreS3DioramaMove-", stamp, run)
    rows = {row["label"]: row for row in plan["targets"]}
    before = {label: plain_transform(actor) for label, actor in targets.items()}
    after = {label: _world_transform_for_row(rows[label], targets[label], dock) for label in TARGET_LABELS}
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "world": EXPECTED_WORLD,
        "backup": backup,
        "backup_files": copied,
        "before": before,
        "after": after,
        "plan": plan,
    }
    _write_record(record)
    for label in TARGET_LABELS:
        set_plain_transform(targets[label], after[label])
    record["readback"] = _readback(targets, after, run)
    _assert_only_level_dirty(run)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    unreal.log(
        "S3_DIORAMA_DONE|run=%s|applied|backup=%s|census=%s"
        % (run, backup, json.dumps(census, separators=(",", ":"), sort_keys=True))
    )


def _revert(index, run):
    record = _load_record(run)
    if record.get("world") != EXPECTED_WORLD:
        stop(run, "reason=RECORD_WORLD_MISMATCH")
    targets = {label: one_actor(index, label, run) for label in TARGET_LABELS}
    _readback(targets, record["after"], run)
    stamp = datetime.datetime.now()
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup, copied = _backup_files(project, targets, "PreS3DioramaRevert-", stamp, run)
    for label in TARGET_LABELS:
        set_plain_transform(targets[label], record["before"][label])
    _readback(targets, record["before"], run)
    _assert_only_level_dirty(run)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    archived = RECORD + ".reverted-" + stamp.strftime("%Y%m%d-%H%M%S")
    os.rename(RECORD, archived)
    unreal.log(
        "S3_DIORAMA_DONE|run=%s|reverted|backup=%s|files=%d|record=%s|census=%s"
        % (run, backup, len(copied), os.path.basename(archived),
           json.dumps(census, separators=(",", ":"), sort_keys=True))
    )


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_DIORAMA_APPLY"))
    revert = bool(globals().get("S3_DIORAMA_REVERT"))
    if apply and revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    _assert_context(editor, world, run, revert)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = actor_index(actors)
    if revert:
        _revert(index, run)
        return
    plan, targets, dock = _live_plan(actors, index, run)
    compact = json.dumps(plan, separators=(",", ":"), sort_keys=True)
    unreal.log("S3_DIORAMA_PLAN|run=%s|%s" % (run, compact))
    unreal.log(
        "S3_DIORAMA_STRIKE_AIM|run=%s|centroid=%s|lights=%s"
        % (
            run,
            json.dumps(plan["ring_centroid_dock_cm"], separators=(",", ":")),
            json.dumps(plan["strike_aim"], separators=(",", ":"), sort_keys=True),
        )
    )
    if not apply:
        census = package_census()
        if census["maps"] or census["content"]:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(census, sort_keys=True))
        unreal.log("S3_DIORAMA_DRY_RUN_OK|run=%s|mutated=0|plan=%s" % (run, compact))
        return
    _apply(plan, targets, dock, run)


if unreal is not None:
    main()
