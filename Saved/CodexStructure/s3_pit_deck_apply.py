"""Cut Scene 3's pit, line it, and add an oak deck attached to the hanging box.

Dry run is the default. S3_PIT_DECK_APPLY records and backs up the level,
trims Passage 03 - Floor at the hinge, fills the old floor around the swept
hole with three tagged strips, builds a black open-topped liner, and attaches
S3 Hangar Deck to S3 Hangar Root in root-relative coordinates. The level is
the only Unreal package saved. S3_PIT_DECK_REVERT requires the recorded applied
state, destroys every recorded actor, restores the floor transform, verifies
the result, and again saves only the level.

The planning functions above main() are deliberately Unreal-free for
test_s3_pit_deck_plan.py.
"""
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FLOOR_LABEL = "Passage 03 - Floor"
ROOT_LABEL = "S3 Hangar Root"
DECK_LABEL = "S3 Hangar Deck"
CUBE = "/Engine/BasicShapes/Cube.Cube"
STEEL = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
HOLE_MARGIN_CM = 25.0
SWEEP_CLEARANCE_CM = 100.0
LINER_THICKNESS_CM = 20.0
LINER_CLEARANCE_CM = 250.0

SHORE_LABELS = (
    "Shore01_M56 Clam",
    "Shore02_F52 Clam",
    "Shore03_M59 Clam",
    "Shore04_F55 Clam",
    "Shore05_M53 Clam",
    "Shore06_F25 Clam",
)
CAST_LABELS = SHORE_LABELS + (
    "Clam_with_Pearl_Clam_with_Pearl_0",
    "source_Anim",
    "tg0pfjxda_tier_0",
)
REMOVAL_LABELS = (
    "SM_P03_CeladonPalatialAntechamber_01_L",
    "SM_P03_CeladonPalatialAntechamber_01_L2",
    "SM_P03_CeladonPalatialAntechamber_01_L3",
    "PointLight",
)

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexStructure",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

RECORD = os.path.join(HERE, "s3_pit_deck_record.json")
CAST_RECORD = os.path.join(HERE, "s3_cast_reveal_record.json")
HANGAR_PLAN = os.path.join(HERE, "hangar_s3_plan.json")
HANGAR_RECORD = os.path.join(HERE, "hangar_s3_record.json")
P03_MOUTH_RECORD = os.path.join(HERE, "p03_mouth_floor_record.json")


def _pair(values):
    return [float(values[0]), float(values[1])]


def _rect_area(rect):
    return max(0.0, rect["x"][1] - rect["x"][0]) * max(
        0.0, rect["y"][1] - rect["y"][0]
    )


def measure_floor_top(readings, maximum_spread_cm=2.0):
    """Return the mean top after requiring six mutually consistent readings."""
    values = [float(value) for value in readings]
    if len(values) != 6:
        raise ValueError(f"expected six floor readings, found {len(values)}")
    spread = max(values) - min(values)
    if spread > float(maximum_spread_cm) + 1e-9:
        raise ValueError(
            f"floor readings spread {spread:.3f} cm; limit is {maximum_spread_cm:.3f} cm"
        )
    return sum(values) / len(values)


def plan_hole(floor_rect, hinge_x, reach_cm, half_w, wall_t):
    """Plan S3's swept hole in the dock frame and require it inside the old plane."""
    floor = {axis: _pair(floor_rect[axis]) for axis in ("x", "y", "z")}
    hinge_x = float(hinge_x)
    hole_half_y = float(half_w) + float(wall_t) + SWEEP_CLEARANCE_CM + HOLE_MARGIN_CM
    hole = {
        "x": [hinge_x, hinge_x + float(reach_cm) + HOLE_MARGIN_CM],
        "y": [-hole_half_y, hole_half_y],
        "z": [floor["z"][0], floor["z"][1]],
    }
    if not floor["x"][0] < hinge_x < floor["x"][1]:
        raise ValueError(f"hinge {hinge_x} is not inside floor x={floor['x']}")
    if hole["x"][1] >= floor["x"][1] - 1.0:
        raise ValueError(f"hole far edge {hole['x'][1]} is not inside floor x={floor['x']}")
    if hole["y"][0] <= floor["y"][0] + 1.0 or hole["y"][1] >= floor["y"][1] - 1.0:
        raise ValueError(f"hole y={hole['y']} is not inside floor y={floor['y']}")
    return hole


def plan_strips(floor_rect, hole):
    """Tile the old plane minus the hole with its trimmed near part and L/R/Far strips."""
    floor = {axis: _pair(floor_rect[axis]) for axis in ("x", "y", "z")}
    hx, hy = _pair(hole["x"]), _pair(hole["y"])
    near = {"x": [floor["x"][0], hx[0]], "y": list(floor["y"]), "z": list(floor["z"])}
    strips = [
        {
            "name": "Left",
            "label": f"{FLOOR_LABEL} - S3 Pit Strip Left",
            "x": [hx[0], floor["x"][1]],
            "y": [floor["y"][0], hy[0]],
            "z": list(floor["z"]),
        },
        {
            "name": "Right",
            "label": f"{FLOOR_LABEL} - S3 Pit Strip Right",
            "x": [hx[0], floor["x"][1]],
            "y": [hy[1], floor["y"][1]],
            "z": list(floor["z"]),
        },
        {
            "name": "Far",
            "label": f"{FLOOR_LABEL} - S3 Pit Strip Far",
            "x": [hx[1], floor["x"][1]],
            "y": list(hy),
            "z": list(floor["z"]),
        },
    ]
    if any(_rect_area(rect) <= 1.0 for rect in [near] + strips):
        raise ValueError("the trimmed floor or a required S3 strip has no area")
    hole_area = (hx[1] - hx[0]) * (hy[1] - hy[0])
    tiled_area = _rect_area(near) + sum(_rect_area(strip) for strip in strips)
    area_error = tiled_area - (_rect_area(floor) - hole_area)
    if abs(area_error) > 1.0:
        raise ValueError(f"strip tiling area error is {area_error:.3f} cm^2")
    return {"floor_after": near, "strips": strips, "area_error_cm2": area_error}


def plan_liner(
    hole,
    floor_bottom,
    hinge_z,
    depth,
    wall_t,
    supplied_floor_top=None,
):
    """Plan the reference open-topped liner, including the hinge-aware floor depth."""
    hanging_lowest = float(hinge_z) - (float(depth) + float(wall_t))
    expected_floor_top = hanging_lowest - LINER_CLEARANCE_CM
    floor_top = expected_floor_top if supplied_floor_top is None else float(supplied_floor_top)
    if abs(floor_top - expected_floor_top) > 0.01:
        raise ValueError(
            f"liner floor top {floor_top:.3f} ignores hinge-aware target {expected_floor_top:.3f}"
        )
    clearance = hanging_lowest - floor_top
    if clearance < 50.0 - 1e-9:
        raise ValueError(f"liner clearance is only {clearance:.3f} cm")

    (x0, x1), (y0, y1) = _pair(hole["x"]), _pair(hole["y"])
    z_top = float(floor_bottom) - 1.0
    near = x0 - HOLE_MARGIN_CM - 40.0
    T = LINER_THICKNESS_CM
    pieces = [
        ("Floor", [x0, x1], [y0, y1], [floor_top - T, floor_top]),
        ("Far Wall", [x1, x1 + T], [y0 - T, y1 + T], [floor_top - T, z_top]),
        ("Left Wall", [near, x1], [y0 - T, y0], [floor_top - T, z_top]),
        ("Right Wall", [near, x1], [y1, y1 + T], [floor_top - T, z_top]),
        ("Near Wall", [near - T, near], [y0 - T, y1 + T], [floor_top - T, z_top]),
    ]
    return {
        "hanging_lowest_z": hanging_lowest,
        "floor_top_z": floor_top,
        "clearance_cm": clearance,
        "z_top": z_top,
        "pieces": [
            {"label": f"S3 Pit Liner {name}", "x": xs, "y": ys, "z": zs}
            for name, xs, ys, zs in pieces
        ],
    }


def plan_deck(floor_top, hinge_z, depth, half_w, thickness=20.0):
    """Return the deck's root-relative slab plan for the LANDED root pose."""
    thickness = float(thickness)
    centre_z = float(floor_top) - float(hinge_z) - thickness / 2.0
    return {
        "label": DECK_LABEL,
        "x": [0.0, float(depth)],
        "y": [-float(half_w), float(half_w)],
        "z": [centre_z - thickness / 2.0, centre_z + thickness / 2.0],
        "relative_location": [float(depth) / 2.0, 0.0, centre_z],
        "relative_rotation": [0.0, 0.0, 0.0],
        "relative_scale": [float(depth) / 100.0, 2.0 * float(half_w) / 100.0, thickness / 100.0],
        "size": [float(depth), 2.0 * float(half_w), thickness],
        "landed_top": float(hinge_z) + centre_z + thickness / 2.0,
    }


def world_placed_relative_at_pitch(deck, pitch_deg=-90.0):
    """The wrong relative location produced by world-placing at rest while the root hangs."""
    dx, dy, dz = deck["relative_location"]
    phi = math.radians(float(pitch_deg))
    return [dx * math.cos(phi) + dz * math.sin(phi), dy, -dx * math.sin(phi) + dz * math.cos(phi)]


def validate_deck_relative(candidate_location, deck, floor_top, hinge_z, tolerance_cm=0.01):
    expected = deck["relative_location"]
    candidate = [float(value) for value in candidate_location]
    error = max(abs(got - want) for got, want in zip(candidate, expected))
    landed_top = float(hinge_z) + candidate[2] + deck["size"][2] / 2.0
    if error > float(tolerance_cm) or abs(landed_top - float(floor_top)) > float(tolerance_cm):
        raise ValueError(
            f"deck is not root-relative: transform_error={error:.3f}, landed_top={landed_top:.3f}"
        )
    return landed_top


def swing_check(deck, hinge_x, reach_cm):
    """Check every deck corner through pitch -90..0 against the apron and reach."""
    xs, zs = deck["x"], deck["z"]
    minimum_x = float("inf")
    for degrees in range(-90, 1):
        phi = math.radians(float(degrees))
        for x in xs:
            for z in zs:
                moved_x = float(hinge_x) + x * math.cos(phi) - z * math.sin(phi)
                minimum_x = min(minimum_x, moved_x)
    deck_reach = max(math.hypot(x, z) for x in xs for z in zs)
    if minimum_x < float(hinge_x) - HOLE_MARGIN_CM - 1e-6:
        raise ValueError(
            f"deck crosses behind hinge-25: min_x={minimum_x:.3f}, hinge={hinge_x:.3f}"
        )
    if deck_reach > float(reach_cm) + 1e-6:
        raise ValueError(f"deck reach {deck_reach:.3f} grows plan reach {reach_cm:.3f}")
    return {"minimum_x": minimum_x, "deck_reach_cm": deck_reach}


def bounds_intersect(bounds, prism):
    return all(
        float(bounds[axis][1]) >= float(prism[axis][0])
        and float(bounds[axis][0]) <= float(prism[axis][1])
        for axis in ("x", "y", "z")
    )


def reject_unknown_blockers(rows):
    unknown = [row for row in rows if not bool(row.get("allowed"))]
    if unknown:
        raise ValueError("unknown blockers: " + ", ".join(str(row.get("label")) for row in unknown))
    return rows


def fail(run, message):
    unreal.log_error(f"S3_PIT_DECK_STOPPED|run={run}|{message}")
    raise RuntimeError(message)


def _load_json(path, run):
    if not os.path.exists(path):
        fail(run, f"required record is absent: {os.path.basename(path)}")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        fail(run, f"could not read {os.path.basename(path)}: {exc}")


def _package_path(package):
    value = package.get_path_name() if hasattr(package, "get_path_name") else package.get_name()
    return str(value).split(".", 1)[0]


def package_census():
    return {
        "dirty_maps": sorted(
            _package_path(package)
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ),
        "dirty_content": sorted(
            _package_path(package)
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
    }


def all_level_actors(world):
    # GameplayStatics sees transient actors that EditorActorSubsystem omits.
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def actor_index(actors):
    out = {}
    for actor in actors:
        out.setdefault(str(actor.get_actor_label()), []).append(actor)
    return out


def one_actor(index, label, run):
    found = index.get(label, [])
    if len(found) != 1:
        fail(run, f"expected one actor {label!r}, found {len(found)}")
    return found[0]


def one_static_mesh_component(actor, label, run):
    components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    if len(components) != 1:
        fail(run, f"expected one StaticMeshComponent on {label}, found {len(components)}")
    component = components[0]
    if component.get_editor_property("static_mesh") is None:
        fail(run, f"{label} has no static mesh")
    return component


def plain_transform(actor):
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    return {
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def transform_error(actor, wanted):
    got = plain_transform(actor)
    return max(
        abs(float(got[group][i]) - float(wanted[group][i]))
        for group in ("location", "rotation", "scale")
        for i in range(3)
    )


def set_plain_transform(actor, value):
    actor.set_actor_scale3d(unreal.Vector(*value["scale"]))
    actor.set_actor_rotation(
        unreal.Rotator(
            roll=value["rotation"][0],
            pitch=value["rotation"][1],
            yaw=value["rotation"][2],
        ),
        False,
    )
    actor.set_actor_location(unreal.Vector(*value["location"]), False, True)


def mesh_frame_bounds(component, frame):
    mesh = component.get_editor_property("static_mesh")
    box = mesh.get_bounding_box()
    transform = component.get_world_transform()
    points = [
        unreal.MathLibrary.inverse_transform_location(
            frame,
            transform.transform_location(unreal.Vector(x, y, z)),
        )
        for x in (box.min.x, box.max.x)
        for y in (box.min.y, box.max.y)
        for z in (box.min.z, box.max.z)
    ]
    return {
        "x": [min(point.x for point in points), max(point.x for point in points)],
        "y": [min(point.y for point in points), max(point.y for point in points)],
        "z": [min(point.z for point in points), max(point.z for point in points)],
    }


def actor_bounds_in_frame(actor, frame):
    origin, extent = actor.get_actor_bounds(False)
    if extent.length() < 0.01:
        return None
    points = [
        unreal.MathLibrary.inverse_transform_location(
            frame,
            unreal.Vector(origin.x + sx * extent.x, origin.y + sy * extent.y, origin.z + sz * extent.z),
        )
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
        for sz in (-1.0, 1.0)
    ]
    return {
        "x": [min(point.x for point in points), max(point.x for point in points)],
        "y": [min(point.y for point in points), max(point.y for point in points)],
        "z": [min(point.z for point in points), max(point.z for point in points)],
    }


def _close_bounds(got, wanted, tolerance_cm):
    return max(
        abs(float(got[axis][i]) - float(wanted[axis][i]))
        for axis in ("x", "y", "z")
        for i in range(2)
    ) <= float(tolerance_cm)


def _mesh_size(mesh):
    box = mesh.get_bounding_box()
    return [
        float(box.max.x - box.min.x),
        float(box.max.y - box.min.y),
        float(box.max.z - box.min.z),
    ]


def _scale_for_box(mesh, rect):
    base = _mesh_size(mesh)
    size = [rect[axis][1] - rect[axis][0] for axis in ("x", "y", "z")]
    if min(base) <= 0.0 or min(size) <= 0.0:
        raise ValueError(f"invalid mesh or requested box size: base={base}, size={size}")
    return [size[i] / base[i] for i in range(3)]


def _assert_context(editor, world, actors, run, revert):
    world_path = world.get_path_name().split(".", 1)[0] if world else None
    if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
        fail(run, f"wrong world, or PIE: world={world_path!r}")
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"packages already dirty: {json.dumps(census, sort_keys=True)}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(run, "Sequencer is open")
    temps = sorted(
        str(actor.get_actor_label())
        for actor in actors
        if str(actor.get_actor_label()).startswith(("ZZ_", "TEMP_"))
        or str(actor.get_name()).startswith(("ZZ_", "TEMP_"))
    )
    if temps:
        fail(run, f"ZZ_/TEMP_ actors present: {temps}")
    if revert and not os.path.exists(RECORD):
        fail(run, "revert record is absent")
    if not revert and os.path.exists(RECORD):
        fail(run, "record already exists; revert first")


def _assert_hidden_prerequisite(index, run):
    record = _load_json(CAST_RECORD, run)
    hidden = {}
    for label in CAST_LABELS + REMOVAL_LABELS:
        actor = one_actor(index, label, run)
        try:
            value = bool(actor.get_editor_property("hidden"))
        except Exception as exc:
            fail(run, f"could not read saved Hidden-in-Game for {label}: {exc}")
        hidden[label] = value
    visible = sorted(label for label, value in hidden.items() if not value)
    if visible:
        fail(run, f"cast-reveal prerequisite is unsafe; these actors are not saved hidden: {visible}")
    return {"record_keys": sorted(record.keys()), "hidden": hidden}


def _floor_readings(floor_component, floor_bounds, frame, index, run):
    rows = []
    for label in SHORE_LABELS:
        actor = one_actor(index, label, run)
        world_location = actor.get_actor_location()
        local = unreal.MathLibrary.inverse_transform_location(frame, world_location)
        if not (
            floor_bounds["x"][0] - 1.0 <= local.x <= floor_bounds["x"][1] + 1.0
            and floor_bounds["y"][0] - 1.0 <= local.y <= floor_bounds["y"][1] + 1.0
        ):
            fail(run, f"{label} XY is outside {FLOOR_LABEL}: dock=({local.x:.2f},{local.y:.2f})")
        rows.append(
            {
                "label": label,
                "world_xy": [float(world_location.x), float(world_location.y)],
                "dock_xy": [float(local.x), float(local.y)],
                "top_z": float(floor_bounds["z"][1]),
                "mode": "static-mesh bounds at actor XY",
            }
        )
    try:
        top = measure_floor_top([row["top_z"] for row in rows])
    except ValueError as exc:
        fail(run, str(exc))
    return rows, top


def _instance_hits(actor, frame, prism):
    hits = 0
    for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if component.get_instance_count() <= 0:
            continue
        mesh = component.get_editor_property("static_mesh")
        if mesh is None:
            continue
        box = mesh.get_bounding_box()
        for index in range(component.get_instance_count()):
            transform = component.get_instance_transform(index, True)
            points = [
                unreal.MathLibrary.inverse_transform_location(
                    frame, transform.transform_location(unreal.Vector(x, y, z))
                )
                for x in (box.min.x, box.max.x)
                for y in (box.min.y, box.max.y)
                for z in (box.min.z, box.max.z)
            ]
            bounds = {
                "x": [min(point.x for point in points), max(point.x for point in points)],
                "y": [min(point.y for point in points), max(point.y for point in points)],
                "z": [min(point.z for point in points), max(point.z for point in points)],
            }
            if bounds_intersect(bounds, prism):
                hits += 1
    return hits


def _blocker_sweep(world, actors, frame, prism, allowed_labels, hangar_labels, run):
    rows = {}
    ignored_classes = (unreal.CameraActor, unreal.PostProcessVolume)

    def allowed(actor):
        label = str(actor.get_actor_label())
        tags = [str(tag) for tag in actor.get_editor_property("tags")]
        if label == "Passage 3 - Wet Ground":
            return label in allowed_labels and bool(actor.get_editor_property("hidden"))
        return label in allowed_labels or label in hangar_labels or "RigAtmos.Scene3Hangar" in tags

    for actor in actors:
        if isinstance(actor, ignored_classes) or actor.get_class().get_name() == "InfinityStageCelestialRig":
            continue
        label = str(actor.get_actor_label())
        isms = [
            component
            for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent)
            if component.get_instance_count() > 0
        ]
        if isms:
            pieces = _instance_hits(actor, frame, prism)
            if not pieces:
                continue
            source = f"instance_bounds:{pieces}"
            bounds = actor_bounds_in_frame(actor, frame)
        else:
            bounds = actor_bounds_in_frame(actor, frame)
            if bounds is None or not bounds_intersect(bounds, prism):
                continue
            source = "actor_bounds"
        rows[actor.get_path_name()] = {
            "label": label,
            "class": actor.get_class().get_name(),
            "allowed": allowed(actor),
            "sources": [source],
            "dock_bounds": bounds,
        }

    # One collision sweep over the planned hole, with known occupants ignored. This is
    # the builder's positive-control path for a landscape or oversized plane whose
    # aggregate actor bounds are otherwise uninformative.
    ignored = [
        actor
        for actor in actors
        if allowed(actor)
        or isinstance(actor, ignored_classes)
        or actor.get_class().get_name() == "InfinityStageCelestialRig"
    ]
    for fx in (0.1, 0.3, 0.5, 0.7, 0.9):
        for fy in (-0.9, -0.45, 0.0, 0.45, 0.9):
            x = prism["x"][0] + fx * (prism["x"][1] - prism["x"][0])
            y = prism["y"][0] + (fy + 1.0) * 0.5 * (prism["y"][1] - prism["y"][0])
            top = frame.transform_location(unreal.Vector(x, y, prism["z"][1] + 1.0))
            bottom = frame.transform_location(unreal.Vector(x, y, prism["z"][0] - 1.0))
            hit = unreal.SystemLibrary.line_trace_single(
                world,
                top,
                bottom,
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                True,
                ignored,
                unreal.DrawDebugTrace.NONE,
                True,
            )
            if hit is None:
                continue
            parts = hit.to_tuple()
            hit_actor = next((part for part in parts if isinstance(part, unreal.Actor)), None)
            if hit_actor is None:
                continue
            path = hit_actor.get_path_name()
            row = rows.setdefault(
                path,
                {
                    "label": str(hit_actor.get_actor_label()),
                    "class": hit_actor.get_class().get_name(),
                    "allowed": allowed(hit_actor),
                    "sources": [],
                    "dock_bounds": actor_bounds_in_frame(hit_actor, frame),
                },
            )
            if "collision_sweep" not in row["sources"]:
                row["sources"].append("collision_sweep")

    result = sorted(rows.values(), key=lambda row: (row["label"], row["class"]))
    unknown = [row for row in result if not row["allowed"]]
    unreal.log(
        f"S3_PIT_DECK_BLOCKERS|run={run}|all={json.dumps(result, sort_keys=True)}|"
        f"unknown={json.dumps(unknown, sort_keys=True)}"
    )
    try:
        reject_unknown_blockers(result)
    except ValueError as exc:
        fail(run, str(exc))
    return result


def _spawn_box(subsystem, frame, rect, label, mesh, material, folder, tags, mobility, source_component=None, cast_shadow=True):
    centre = unreal.Vector(
        (rect["x"][0] + rect["x"][1]) / 2.0,
        (rect["y"][0] + rect["y"][1]) / 2.0,
        (rect["z"][0] + rect["z"][1]) / 2.0,
    )
    world_centre = frame.transform_location(centre)
    yaw = frame.rotation.rotator().yaw
    actor = subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        world_centre,
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
    )
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    actor.set_editor_property("tags", [unreal.Name(tag) for tag in tags])
    component = actor.get_editor_property("static_mesh_component")
    component.set_mobility(mobility)
    component.set_static_mesh(mesh)
    component.set_material(0, material)
    component.set_cast_shadow(bool(cast_shadow))
    if source_component is not None:
        component.set_collision_enabled(source_component.get_collision_enabled())
        try:
            component.set_collision_profile_name(source_component.get_collision_profile_name())
        except Exception:
            pass
    actor.set_actor_scale3d(unreal.Vector(*_scale_for_box(mesh, rect)))
    return actor


def _spawn_deck(subsystem, root, deck_plan, mesh, material, folder, source_component):
    actor = subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        root.get_actor_location(),
        root.get_actor_rotation(),
    )
    actor.set_actor_label(DECK_LABEL)
    actor.set_folder_path(folder)
    actor.set_editor_property("tags", [unreal.Name("RigAtmos.S3Deck")])
    component = actor.get_editor_property("static_mesh_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_static_mesh(mesh)
    component.set_material(0, material)
    component.set_cast_shadow(True)
    component.set_collision_enabled(source_component.get_collision_enabled())
    try:
        component.set_collision_profile_name(source_component.get_collision_profile_name())
    except Exception:
        pass
    actor.attach_to_actor(
        root,
        unreal.Name(""),
        unreal.AttachmentRule.KEEP_RELATIVE,
        unreal.AttachmentRule.KEEP_RELATIVE,
        unreal.AttachmentRule.KEEP_RELATIVE,
        False,
    )
    relative_rect = {axis: deck_plan[axis] for axis in ("x", "y", "z")}
    actor.root_component.set_editor_property(
        "relative_location", unreal.Vector(*deck_plan["relative_location"])
    )
    actor.root_component.set_editor_property(
        "relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    )
    actor.root_component.set_editor_property(
        "relative_scale3d", unreal.Vector(*_scale_for_box(mesh, relative_rect))
    )
    return actor


def _readback_new(index, frame, root, record, run):
    errors = []
    strip_labels = {row["label"] for row in record["strips"]}
    for row in record["strips"] + record["liner"]["pieces"]:
        actor = one_actor(index, row["label"], run)
        component = one_static_mesh_component(actor, row["label"], run)
        got = mesh_frame_bounds(component, frame)
        wanted = {axis: row[axis] for axis in ("x", "y", "z")}
        if not _close_bounds(got, wanted, 1.0):
            errors.append(f"{row['label']} bounds got={got} wanted={wanted}")
        is_strip = row["label"] in strip_labels
        expected_mesh = record["floor_before"]["mesh"] if is_strip else CUBE
        expected_material = record["floor_before"]["material"] if is_strip else STEEL
        expected_tags = (
            {"RigAtmos.PitFloor", "RigAtmos.Scene3PitFloor"}
            if is_strip
            else {"RigAtmos.PitLiner", "RigAtmos.Scene3PitLiner"}
        )
        mesh = component.get_editor_property("static_mesh")
        material = component.get_material(0)
        tags = {str(tag) for tag in actor.get_editor_property("tags")}
        if mesh is None or mesh.get_path_name() != expected_mesh:
            errors.append(f"{row['label']} mesh is not {expected_mesh}")
        if material is None or material.get_path_name() != expected_material:
            errors.append(f"{row['label']} material is not {expected_material}")
        if not expected_tags.issubset(tags):
            errors.append(f"{row['label']} tags {sorted(tags)} do not contain {sorted(expected_tags)}")

    deck = one_actor(index, DECK_LABEL, run)
    if deck.get_attach_parent_actor() != root:
        errors.append("deck is not attached to S3 Hangar Root")
    component = one_static_mesh_component(deck, DECK_LABEL, run)
    root_frame = root.get_actor_transform()
    got_bounds = mesh_frame_bounds(component, root_frame)
    wanted_bounds = {axis: record["deck"][axis] for axis in ("x", "y", "z")}
    if not _close_bounds(got_bounds, wanted_bounds, 1.0):
        errors.append(f"deck root-relative bounds got={got_bounds} wanted={wanted_bounds}")

    relative_location = deck.root_component.get_editor_property("relative_location")
    relative_rotation = deck.root_component.get_editor_property("relative_rotation")
    relative_scale = deck.root_component.get_editor_property("relative_scale3d")
    got_location = [relative_location.x, relative_location.y, relative_location.z]
    got_rotation = [relative_rotation.roll, relative_rotation.pitch, relative_rotation.yaw]
    got_scale = [relative_scale.x, relative_scale.y, relative_scale.z]
    transform_delta = max(
        [
            abs(got_location[i] - record["deck"]["relative_location"][i])
            for i in range(3)
        ]
        + [abs(got_rotation[i] - record["deck"]["relative_rotation"][i]) for i in range(3)]
        + [abs(got_scale[i] - record["deck"]["relative_scale"][i]) for i in range(3)]
    )
    if transform_delta > 0.1:
        errors.append(f"deck relative transform error {transform_delta:.3f} cm/deg")
    landed_top = record["hinge_z"] + got_location[2] + record["deck"]["size"][2] / 2.0
    if abs(landed_top - record["measured_floor_top"]) > 1.0:
        errors.append(
            f"deck landed top {landed_top:.3f}, floor top {record['measured_floor_top']:.3f}"
        )
    if not bool(component.get_editor_property("cast_shadow")):
        errors.append("deck does not cast shadows")
    deck_mesh = component.get_editor_property("static_mesh")
    deck_material = component.get_material(0)
    if deck_mesh is None or deck_mesh.get_path_name() != CUBE:
        errors.append(f"deck mesh is not {CUBE}")
    if deck_material is None or deck_material.get_path_name() != record["floor_before"]["material"]:
        errors.append(f"deck material is not {record['floor_before']['material']}")
    if "RigAtmos.S3Deck" not in [str(tag) for tag in deck.get_editor_property("tags")]:
        errors.append("deck tag is absent")
    if transform_error(root, record["root_before"]) > 0.05:
        errors.append("S3 Hangar Root changed")
    if errors:
        fail(run, "read-back failed before save: " + " || ".join(errors))
    return {"deck_relative": got_location, "deck_landed_top": landed_top}


def _assert_only_level_dirty(run):
    census = package_census()
    if census["dirty_content"] or census["dirty_maps"] != [EXPECTED_WORLD]:
        fail(run, f"dirty set is not exactly the level: {json.dumps(census, sort_keys=True)}")


def _backup(stamp, project, record_path, run):
    backup = os.path.join(
        project, "Backups", "PreS3PitDeck-" + stamp.strftime("%Y%m%d-%H%M")
    )
    if os.path.exists(backup):
        fail(run, f"backup path already exists: {backup}")
    os.makedirs(backup)
    level_file = os.path.join(
        project, "Content", *EXPECTED_WORLD[len("/Game/") :].split("/")
    ) + ".umap"
    if not os.path.exists(level_file):
        fail(run, f"level file is absent: {level_file}")
    shutil.copy2(level_file, backup)
    shutil.copy2(record_path, backup)
    return backup


def _make_plan(world, actors, index, frame, hangar_plan, hangar_record, mouth_record, floor, floor_component, root, run):
    h = hangar_plan["hangar"]
    if bool(h.get("floor")):
        fail(run, "hangar_s3_plan.json no longer says floor=false")
    recorded_h = hangar_record.get("hangar", {})
    authority_fields = ("depth", "half_w", "wall_t", "apron", "hinge_z", "floor")
    authority_drift = {
        field: {"plan": h.get(field), "record": recorded_h.get(field)}
        for field in authority_fields
        if h.get(field) != recorded_h.get(field)
    }
    if authority_drift:
        fail(run, f"hangar plan/record geometry disagrees: {authority_drift}")
    floor_rotation = floor.get_actor_rotation()
    dock_yaw = float(hangar_plan["dock"]["yaw"])
    yaw_error = abs(((floor_rotation.yaw - dock_yaw + 180.0) % 360.0) - 180.0)
    if max(abs(floor_rotation.roll), abs(floor_rotation.pitch), yaw_error) > 0.05:
        fail(run, f"{FLOOR_LABEL} is not square to the S3 dock")

    floor_bounds = mesh_frame_bounds(floor_component, frame)
    floor_mesh = floor_component.get_editor_property("static_mesh")
    if floor_mesh.get_path_name() != CUBE:
        fail(run, f"{FLOOR_LABEL} is not the required engine Cube: {floor_mesh.get_path_name()}")
    floor_material = floor_component.get_material(0)
    if floor_material is None:
        fail(run, f"{FLOOR_LABEL} has no material in slot 0")
    if floor.get_attach_parent_actor() is not None:
        fail(run, f"{FLOOR_LABEL} is unexpectedly attached")
    mouth_x = mouth_record.get("plan", {}).get("floor_after_x")
    if not isinstance(mouth_x, list) or len(mouth_x) != 2:
        fail(run, "p03_mouth_floor_record.json has no plan.floor_after_x pair")
    if max(abs(floor_bounds["x"][i] - float(mouth_x[i])) for i in range(2)) > 1.0:
        fail(
            run,
            f"{FLOOR_LABEL} no longer matches the saved mouth trim: "
            f"bounds={floor_bounds['x']}, record={mouth_x}",
        )
    readings, floor_top = _floor_readings(floor_component, floor_bounds, frame, index, run)
    hinge_x = float(h["apron"])
    hinge_z = float(h.get("hinge_z") or 0.0)
    hole = plan_hole(
        floor_bounds,
        hinge_x,
        hangar_plan["reach_cm"],
        h["half_w"],
        h["wall_t"],
    )
    tiling = plan_strips(floor_bounds, hole)
    liner = plan_liner(
        hole,
        floor_bounds["z"][0],
        hinge_z,
        h["depth"],
        h["wall_t"],
    )
    deck = plan_deck(floor_top, hinge_z, h["depth"], h["half_w"], 20.0)
    swing = swing_check(deck, hinge_x, hangar_plan["reach_cm"])

    hinge_world = frame.transform_location(unreal.Vector(hinge_x, 0.0, hinge_z))
    root_location = root.get_actor_location()
    root_rotation = root.get_actor_rotation()
    root_scale = root.get_actor_scale3d()
    if (root_location - hinge_world).length() > 1.0:
        fail(run, f"S3 Hangar Root is not on the planned hinge: {plain_transform(root)}")
    root_yaw_error = abs(((root_rotation.yaw - dock_yaw + 180.0) % 360.0) - 180.0)
    if (
        abs(root_rotation.pitch + 90.0) > 0.1
        or abs(root_rotation.roll) > 0.1
        or root_yaw_error > 0.1
        or max(abs(root_scale.x - 1.0), abs(root_scale.y - 1.0), abs(root_scale.z - 1.0)) > 0.001
    ):
        fail(run, f"S3 Hangar Root is not in its saved hanging pose: {plain_transform(root)}")

    allowed_labels = set(CAST_LABELS + REMOVAL_LABELS) | {
        FLOOR_LABEL,
        "GroupActor0",
        "LS_OrtalanSheetSway",
        "Passage 3 - Wet Ground",
    }
    hangar_labels = set(hangar_record.get("labels", []))
    prism = {"x": list(hole["x"]), "y": list(hole["y"]), "z": [liner["floor_top_z"], floor_top]}
    blockers = _blocker_sweep(
        world,
        actors,
        frame,
        prism,
        allowed_labels,
        hangar_labels,
        run,
    )

    floor_before = plain_transform(floor)
    old_length = floor_bounds["x"][1] - floor_bounds["x"][0]
    new_length = tiling["floor_after"]["x"][1] - tiling["floor_after"]["x"][0]
    floor_local = unreal.MathLibrary.inverse_transform_location(frame, floor.get_actor_location())
    new_local = unreal.Vector(
        sum(tiling["floor_after"]["x"]) / 2.0,
        floor_local.y,
        floor_local.z,
    )
    new_world = frame.transform_location(new_local)
    floor_after = json.loads(json.dumps(floor_before))
    floor_after["location"] = [float(new_world.x), float(new_world.y), float(new_world.z)]
    floor_after["scale"][0] = floor_before["scale"][0] * new_length / old_length

    return {
        "dock": {"location": [hangar_plan["dock"]["loc"][0], hangar_plan["dock"]["loc"][1], 0.0], "yaw": dock_yaw},
        "hinge_x": hinge_x,
        "hinge_z": hinge_z,
        "reach_cm": float(hangar_plan["reach_cm"]),
        "floor_before": {
            "transform": floor_before,
            "dock_bounds": floor_bounds,
            "mesh": floor_component.get_editor_property("static_mesh").get_path_name(),
            "material": floor_component.get_material(0).get_path_name() if floor_component.get_material(0) else None,
            "folder": str(floor.get_folder_path()),
        },
        "floor_after": {"transform": floor_after, "dock_bounds": tiling["floor_after"]},
        "floor_readings": readings,
        "measured_floor_top": floor_top,
        "hole": hole,
        "strips": tiling["strips"],
        "area_error_cm2": tiling["area_error_cm2"],
        "liner": liner,
        "deck": deck,
        "swing": swing,
        "blocker_prism": prism,
        "blockers": blockers,
        "root_before": plain_transform(root),
    }


def _apply(world, frame, subsystem, index, floor, floor_component, root, plan, run):
    labels = [row["label"] for row in plan["strips"] + plan["liner"]["pieces"]] + [DECK_LABEL]
    occupied = sorted(label for label in labels if index.get(label))
    if occupied:
        fail(run, f"planned actor labels already exist: {occupied}")

    cube = unreal.load_asset(CUBE)
    steel = unreal.load_asset(STEEL)
    floor_mesh = floor_component.get_editor_property("static_mesh")
    floor_material = floor_component.get_material(0)
    if cube is None or steel is None or floor_mesh is None or floor_material is None:
        fail(
            run,
            "required geometry/material did not load: "
            f"cube={cube is not None}, steel={steel is not None}, "
            f"floor_mesh={floor_mesh is not None}, floor_material={floor_material is not None}",
        )

    stamp = datetime.datetime.now()
    record = dict(plan)
    record.update(
        {
            "written": stamp.isoformat(timespec="seconds"),
            "run": run,
            "spawned": labels,
            "cast_record": os.path.basename(CAST_RECORD),
            "hangar_plan": os.path.basename(HANGAR_PLAN),
        }
    )
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = _backup(stamp, project, RECORD, run)

    set_plain_transform(floor, plan["floor_after"]["transform"])
    floor_mobility = floor_component.get_editor_property("mobility")
    folder = floor.get_folder_path()
    for row in plan["strips"]:
        _spawn_box(
            subsystem,
            frame,
            row,
            row["label"],
            floor_mesh,
            floor_material,
            folder,
            ("RigAtmos.PitFloor", "RigAtmos.Scene3PitFloor"),
            floor_mobility,
            source_component=floor_component,
            cast_shadow=bool(floor_component.get_editor_property("cast_shadow")),
        )

    liner_folder = "Infinity Stage/Scene 03 Hangar"
    for row in plan["liner"]["pieces"]:
        _spawn_box(
            subsystem,
            frame,
            row,
            row["label"],
            cube,
            steel,
            liner_folder,
            ("RigAtmos.PitLiner", "RigAtmos.Scene3PitLiner"),
            unreal.ComponentMobility.STATIC,
            cast_shadow=True,
        )
    _spawn_deck(
        subsystem,
        root,
        plan["deck"],
        cube,
        floor_material,
        liner_folder,
        floor_component,
    )

    actors_after = all_level_actors(world)
    index_after = actor_index(actors_after)
    floor_after_bounds = mesh_frame_bounds(floor_component, frame)
    if not _close_bounds(floor_after_bounds, plan["floor_after"]["dock_bounds"], 1.0):
        fail(
            run,
            f"trimmed floor read-back failed: got={floor_after_bounds}, wanted={plan['floor_after']['dock_bounds']}",
        )
    readback = _readback_new(index_after, frame, root, record, run)
    _assert_only_level_dirty(run)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail(run, "level save failed")
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"post-save packages remain dirty: {json.dumps(census, sort_keys=True)}")
    unreal.log(
        f"S3_PIT_DECK_DONE|run={run}|applied|floor_top={plan['measured_floor_top']:.3f}|"
        f"deck_landed_top={readback['deck_landed_top']:.3f}|spawned={len(labels)}|backup={backup}|"
        f"census={json.dumps(census, sort_keys=True)}"
    )


def _revert(world, frame, subsystem, index, floor, floor_component, root, run):
    record = _load_json(RECORD, run)
    if transform_error(floor, record["floor_after"]["transform"]) > 0.1:
        fail(run, "revert refused: trimmed floor transform drifted")
    current_floor_bounds = mesh_frame_bounds(floor_component, frame)
    if not _close_bounds(current_floor_bounds, record["floor_after"]["dock_bounds"], 1.0):
        fail(run, "revert refused: trimmed floor bounds drifted")
    _readback_new(index, frame, root, record, run)

    deleted = 0
    for label in record["spawned"]:
        actor = one_actor(index, label, run)
        if not subsystem.destroy_actor(actor):
            fail(run, f"could not destroy recorded actor {label}")
        deleted += 1
    if deleted != len(record["spawned"]):
        fail(run, f"deleted {deleted} of {len(record['spawned'])} recorded actors")
    set_plain_transform(floor, record["floor_before"]["transform"])

    actors_after = all_level_actors(world)
    labels_after = {str(actor.get_actor_label()) for actor in actors_after}
    survivors = sorted(set(record["spawned"]) & labels_after)
    restored_bounds = mesh_frame_bounds(floor_component, frame)
    if survivors or transform_error(floor, record["floor_before"]["transform"]) > 0.1 or not _close_bounds(
        restored_bounds, record["floor_before"]["dock_bounds"], 1.0
    ):
        fail(
            run,
            f"revert read-back failed before save: survivors={survivors}, floor_bounds={restored_bounds}",
        )
    _assert_only_level_dirty(run)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail(run, "level save failed")
    reverted_record = RECORD + ".reverted"
    os.replace(RECORD, reverted_record)
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"post-save packages remain dirty: {json.dumps(census, sort_keys=True)}")
    unreal.log(
        f"S3_PIT_DECK_DONE|run={run}|reverted|deleted={deleted}|record={os.path.basename(reverted_record)}|"
        f"census={json.dumps(census, sort_keys=True)}"
    )


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_PIT_DECK_APPLY"))
    revert = bool(globals().get("S3_PIT_DECK_REVERT"))
    if apply and revert:
        fail(run, "apply and revert modes are mutually exclusive")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actors = all_level_actors(world) if world else []
    _assert_context(editor, world, actors, run, revert)
    index = actor_index(actors)
    floor = one_actor(index, FLOOR_LABEL, run)
    floor_component = one_static_mesh_component(floor, FLOOR_LABEL, run)
    root = one_actor(index, ROOT_LABEL, run)

    if revert:
        record = _load_json(RECORD, run)
        dock = record["dock"]
        frame = unreal.Transform(
            location=unreal.Vector(*dock["location"]),
            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=dock["yaw"]),
        )
        _revert(world, frame, unreal.get_editor_subsystem(unreal.EditorActorSubsystem), index, floor, floor_component, root, run)
        return

    prerequisite = _assert_hidden_prerequisite(index, run)
    hangar_plan = _load_json(HANGAR_PLAN, run)
    hangar_record = _load_json(HANGAR_RECORD, run)
    mouth_record = _load_json(P03_MOUTH_RECORD, run)
    dock = hangar_plan["dock"]
    frame = unreal.Transform(
        location=unreal.Vector(dock["loc"][0], dock["loc"][1], 0.0),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=dock["yaw"]),
    )
    plan = _make_plan(
        world,
        actors,
        index,
        frame,
        hangar_plan,
        hangar_record,
        mouth_record,
        floor,
        floor_component,
        root,
        run,
    )
    unreal.log(
        f"S3_PIT_DECK_PLAN|run={run}|prerequisite={json.dumps(prerequisite, sort_keys=True)}|"
        f"floor_readings={json.dumps(plan['floor_readings'], sort_keys=True)}|"
        f"measured_floor_top={plan['measured_floor_top']:.3f}|hole={json.dumps(plan['hole'], sort_keys=True)}|"
        f"strips={json.dumps(plan['strips'], sort_keys=True)}|liner={json.dumps(plan['liner'], sort_keys=True)}|"
        f"deck={json.dumps(plan['deck'], sort_keys=True)}|swing={json.dumps(plan['swing'], sort_keys=True)}"
    )
    if not apply:
        unreal.log(
            f"S3_PIT_DECK_DRY_RUN_OK|run={run}|mutated=0|"
            f"census={json.dumps(package_census(), sort_keys=True)}"
        )
        return
    _apply(
        world,
        frame,
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem),
        index,
        floor,
        floor_component,
        root,
        plan,
        run,
    )


if unreal is not None:
    main()
