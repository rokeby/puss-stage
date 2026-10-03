"""Scene 3 beach-v2 DRY/APPLY/REVERT implementation.

The public entry point remains s3_beach_place.py.  That file delegates its
Unreal execution to this module so the already-landed v1 tool remains readable
for provenance and exact legacy restoration.

APPLY verifies and replaces only the nine v1 tool-owned actors, imports one
deterministic subdivided OBJ sand layer, places embedded Megascans rocks and
seaweed, and raises the six ring figures so their bounds feet meet the sampled
sand surface.  REVERT removes only v2 actors, restores the six figure
transforms, and reconstructs the nine v1 actors.  The imported mesh is retained
on REVERT; no asset is permanently deleted.
"""
import datetime
import json
import math
import os
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
ROOT_LABEL = "S3 Hangar Root"
LEGACY_TAG = "RigAtmos.S3Beach"
TAG = "RigAtmos.S3BeachV2"
FOLDER = "RigAtmos/S3BeachV2"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
BOX_X = (500.0, 6500.0)
BOX_Y = (-1000.0, 1000.0)
BOX_Z = (-5.0, 600.0)
CAMERA_CLEARANCE_CM = 150.0
WAVE_BANDS_X = ((4100.0, 4300.0), (4900.0, 5100.0), (5700.0, 5900.0))
SAND_LABEL = "S3 Beach V2 Sand Floor"
SAND_ASSET = "/Game/InfinityStage/Dev/Generated/S3Beach/SM_S3_BeachV2_SandFloor"
SAND_MATERIAL = "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/01_Soil_Sand_pjuuz0_2K_inst"
SAND_CENTER_X = 3550.0
SAND_RX = 500.0
SAND_RY = 700.0
SAND_BASE_Z = -5.0
SAND_GRID_X = 31
SAND_GRID_Y = 35
SAND_MAX_Z = 20.0
FIGURE_LABELS = (
    "Shore01_M56 Clam", "Shore02_F52 Clam", "Shore03_M59 Clam",
    "Shore04_F55 Clam", "Shore05_M53 Clam", "Shore06_F25 Clam",
)
LEGACY_LABELS = (
    "S3 Beach Mound Rear", "S3 Beach Mound Left", "S3 Beach Mound Right",
    "S3 Beach Rock Back L", "S3 Beach Rock Back R", "S3 Beach Shingle L",
    "S3 Beach Shingle R", "S3 Beach Seaweed L", "S3 Beach Seaweed R",
)
REQUIRED_TESTS = ("InfinityStage.Editor.SavedMasterMatchesShow",
                  "InfinityStage.Editor.SceneCutBindingsResolve")

PROP_SPECS = (
    {"kind": "rock", "label": "S3 Beach V2 Rock 01", "mesh_path": "/Game/EnvironmentPacks/Megascans_2K/3D_Asset/03_Flat_Rock_ohCwN/Aset_rock_granite_M_ohCwN_LOD0", "xy": (3820.0, -380.0), "yaw": 27.0, "scale": 0.75, "embed": 0.30},
    {"kind": "rock", "label": "S3 Beach V2 Rock 02", "mesh_path": "/Game/EnvironmentPacks/Megascans_2K/3D_Asset/05_Rock_Granite_pkjsG/Aset_rock_granite_M_pkjsG_LOD0", "xy": (3820.0, 330.0), "yaw": -38.0, "scale": 0.65, "embed": 0.34},
    {"kind": "rock", "label": "S3 Beach V2 Rock 03", "mesh_path": "/Game/EnvironmentPacks/Megascans_2K/3D_Asset/13_Granite_Rock_ohFsZ/Aset_rock_granite_M_ohFsZ_LOD0", "xy": (3740.0, -310.0), "yaw": 73.0, "scale": 0.90, "embed": 0.25},
    {"kind": "rock", "label": "S3 Beach V2 Rock 04", "mesh_path": "/Game/EnvironmentPacks/Megascans_2K/3D_Asset/20_Mossy_Flat_Stone_oidxM/Aset_rock_granite_L_oidxM_LOD0", "xy": (3860.0, 235.0), "yaw": -44.0, "scale": 0.75, "embed": 0.30},
    {"kind": "rock", "label": "S3 Beach V2 Rock 05", "mesh_path": "/Game/EnvironmentPacks/Megascans_2K/3D_Asset/09_Rock_Granite_okowW/Aset_rock_granite_M_okowW_LOD0", "xy": (3990.0, -90.0), "yaw": 11.0, "scale": 1.10, "embed": 0.40},
    {"kind": "seaweed", "label": "S3 Beach V2 Seaweed 01", "mesh_path": "/Game/EnvironmentPacks/OceanFloor/Meshes/SM_SeaweedA", "xy": (3850.0, -400.0), "yaw": 18.0, "scale": 0.42, "embed": 0.12},
    {"kind": "seaweed", "label": "S3 Beach V2 Seaweed 02", "mesh_path": "/Game/EnvironmentPacks/OceanFloor/Meshes/SM_SeaweedB", "xy": (3800.0, 450.0), "yaw": -21.0, "scale": 0.34, "embed": 0.12},
    {"kind": "seaweed", "label": "S3 Beach V2 Seaweed 03", "mesh_path": "/Game/EnvironmentPacks/OceanFloor/Meshes/SM_SeaweedA", "xy": (3700.0, 470.0), "yaw": 62.0, "scale": 0.38, "embed": 0.12},
)


class PlanError(ValueError):
    pass


def project_file(*parts):
    if unreal is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def record_path():
    return project_file("Saved", "CodexConductor", "s3_beach_place_record.json")


def pending_path():
    return record_path() + ".v2-pending"


def obj_path():
    return project_file("Saved", "CodexConductor", "SM_S3_BeachV2_SandFloor.obj")


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _mul(a, value):
    return tuple(float(item) * float(value) for item in a)


def _length2(value):
    return _dot(value, value)


def point_triangle_distance(point, a, b, c):
    """Exact Euclidean point/triangle distance (Ericson region tests)."""
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(point, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return math.sqrt(_length2(ap))
    bp = _sub(point, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return math.sqrt(_length2(bp))
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return math.sqrt(_length2(_sub(point, _add(a, _mul(ab, v)))))
    cp = _sub(point, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return math.sqrt(_length2(cp))
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return math.sqrt(_length2(_sub(point, _add(a, _mul(ac, w)))))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return math.sqrt(_length2(_sub(point, _add(b, _mul(_sub(c, b), w)))))
    denom = 1.0 / (va + vb + vc)
    v, w = vb * denom, vc * denom
    projection = _add(a, _add(_mul(ab, v), _mul(ac, w)))
    return math.sqrt(_length2(_sub(point, projection)))


def _shape_metric(x, y):
    nx = (float(x) - SAND_CENTER_X) / SAND_RX
    ny = float(y) / SAND_RY
    wobble = 0.055 * math.sin(float(y) / 115.0) + 0.035 * math.sin((float(x) + float(y)) / 170.0)
    return math.sqrt(nx * nx + ny * ny) + wobble


def sand_height(x, y):
    metric = _shape_metric(x, y)
    if metric >= 1.0:
        return SAND_BASE_Z
    feather = max(0.0, min(1.0, (1.0 - metric) / 0.20))
    noise = (3.2 * math.sin(float(x) / 93.0) * math.cos(float(y) / 127.0) +
             1.7 * math.sin((float(x) + 2.0 * float(y)) / 61.0))
    return min(SAND_MAX_Z, SAND_BASE_Z + feather * (14.0 + noise))


def build_sand_mesh(cameras):
    if not cameras:
        raise PlanError("no S3 Shot cameras")
    xs = [SAND_CENTER_X - SAND_RX + 2.0 * SAND_RX * i / (SAND_GRID_X - 1)
          for i in range(SAND_GRID_X)]
    ys = [-SAND_RY + 2.0 * SAND_RY * i / (SAND_GRID_Y - 1)
          for i in range(SAND_GRID_Y)]
    grid = [[(x - SAND_CENTER_X, y, sand_height(x, y)) for y in ys] for x in xs]
    faces = []
    for ix in range(SAND_GRID_X - 1):
        for iy in range(SAND_GRID_Y - 1):
            candidates = (((ix, iy), (ix + 1, iy), (ix + 1, iy + 1)),
                          ((ix, iy), (ix + 1, iy + 1), (ix, iy + 1)))
            for indices in candidates:
                dock_triangle = [(grid[a][b][0] + SAND_CENTER_X, grid[a][b][1], grid[a][b][2])
                                 for a, b in indices]
                if any(_shape_metric(point[0], point[1]) > 1.001 for point in dock_triangle):
                    continue
                clearance = min(point_triangle_distance(tuple(camera["location"]), *dock_triangle)
                                for camera in cameras)
                if clearance >= CAMERA_CLEARANCE_CM - 1.0e-6:
                    faces.append(indices)
    if not faces:
        raise PlanError("sand mesh has no camera-safe faces")
    used = sorted(set(item for face in faces for item in face))
    remap = {item: index for index, item in enumerate(used)}
    vertices = [grid[ix][iy] for ix, iy in used]
    remapped_faces = [tuple(remap[item] for item in face) for face in faces]
    min_clearance = min(point_triangle_distance(tuple(camera["location"]),
                         *[(vertices[index][0] + SAND_CENTER_X, vertices[index][1], vertices[index][2])
                           for index in face])
                         for face in remapped_faces for camera in cameras)
    return {"vertices": vertices, "faces": remapped_faces,
            "min_camera_clearance_cm": min_clearance}


def point_covered(mesh, x, y):
    px, py = float(x) - SAND_CENTER_X, float(y)
    for face in mesh["faces"]:
        a, b, c = [mesh["vertices"][index] for index in face]
        area = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(area) < 1.0e-9:
            continue
        u = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / area
        v = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / area
        if u >= -1.0e-6 and v >= -1.0e-6 and u + v <= 1.0 + 1.0e-6:
            return True
    return False


def aabb_distance_to_point(bounds, point):
    gaps = [max(0.0, float(bounds["min"][axis]) - float(point[axis]),
                float(point[axis]) - float(bounds["max"][axis])) for axis in range(3)]
    return math.sqrt(sum(value * value for value in gaps))


def rotated_bounds(local_bounds, spec, location_z):
    scale = float(spec["scale"])
    radians = math.radians(float(spec["yaw"]))
    cosine, sine = math.cos(radians), math.sin(radians)
    points = []
    for x in (local_bounds["min"][0], local_bounds["max"][0]):
        for y in (local_bounds["min"][1], local_bounds["max"][1]):
            for z in (local_bounds["min"][2], local_bounds["max"][2]):
                sx, sy = scale * float(x), scale * float(y)
                points.append((spec["xy"][0] + sx * cosine - sy * sine,
                               spec["xy"][1] + sx * sine + sy * cosine,
                               location_z + scale * float(z)))
    return {"min": [min(point[axis] for point in points) for axis in range(3)],
            "max": [max(point[axis] for point in points) for axis in range(3)]}


def plan_prop(spec, local_bounds, cameras):
    row = dict(spec)
    scaled_min = float(local_bounds["min"][2]) * float(spec["scale"])
    scaled_height = ((float(local_bounds["max"][2]) - float(local_bounds["min"][2])) *
                     float(spec["scale"]))
    surface = sand_height(*spec["xy"])
    location_z = surface - scaled_min - scaled_height * float(spec["embed"])
    bounds = rotated_bounds(local_bounds, spec, location_z)
    row.update({"surface_z_cm": surface, "location_z_cm": location_z,
                "embedded_fraction": float(spec["embed"]), "aabb": bounds,
                "nearest_camera_clearance_cm": min(aabb_distance_to_point(bounds, camera["location"])
                                                   for camera in cameras)})
    return row


def validate_v2_plan(mesh, props, figures, cameras, existing_labels):
    failures = []
    labels = [SAND_LABEL] + [row["label"] for row in props]
    if len(labels) != 9 or len(labels) != len(set(labels)):
        failures.append("v2 requires one sand layer plus eight unique dressing actors")
    collisions = [label for label in labels if int(existing_labels.get(label, 0))]
    if collisions:
        failures.append("v2 labels already exist: " + ", ".join(collisions))
    if mesh["min_camera_clearance_cm"] < CAMERA_CLEARANCE_CM - 1.0e-6:
        failures.append("sand enters a 1.5 m shot-camera exclusion")
    for row in props:
        bounds = row["aabb"]
        if row["nearest_camera_clearance_cm"] < CAMERA_CLEARANCE_CM - 1.0e-6:
            failures.append(row["label"] + " enters a 1.5 m shot-camera exclusion")
        if not 0.20 <= row["embedded_fraction"] <= 0.40 and row["kind"] == "rock":
            failures.append(row["label"] + " rock embed is outside 20-40 percent")
        for axis, interval in enumerate((BOX_X, BOX_Y, BOX_Z)):
            if bounds["min"][axis] < interval[0] - 0.001 or bounds["max"][axis] > interval[1] + 0.001:
                failures.append(row["label"] + " leaves landed S3 box")
        if any(bounds["max"][0] >= band[0] and bounds["min"][0] <= band[1]
               for band in WAVE_BANDS_X):
            failures.append(row["label"] + " enters wave travel")
    if len(figures) != len(FIGURE_LABELS):
        failures.append("expected six ring figures")
    for row in figures:
        if not point_covered(mesh, row["dock_xy"][0], row["dock_xy"][1]):
            failures.append(row["label"] + " feet are outside the sand mesh")
        if not 0.0 <= row["raise_cm"] <= 80.0:
            failures.append(row["label"] + " requires an unsafe vertical correction")
        if abs(row["planned_foot_z_cm"] - row["surface_z_cm"]) > 0.01:
            failures.append(row["label"] + " planned feet do not meet sand")
    if not cameras:
        failures.append("no S3 Shot cameras")
    if failures:
        raise PlanError("; ".join(failures))
    return True


def _vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def _plain_transform(value):
    rotation = value.rotation.rotator()
    return {"location": _vector(value.translation),
            "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": _vector(value.scale3d)}


def _transform(row):
    return unreal.Transform(location=unreal.Vector(*row["location"]),
                            rotation=unreal.Rotator(roll=row["rotation"][0], pitch=row["rotation"][1], yaw=row["rotation"][2]),
                            scale=unreal.Vector(*row["scale"]))


def _actor_index():
    result = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def _one(index, label):
    rows = index.get(label, [])
    if len(rows) != 1:
        raise PlanError("expected exactly one actor labelled %s, found %d" % (label, len(rows)))
    return rows[0]


def _package_census():
    names = lambda rows: sorted(str(value.get_path_name()).split(".", 1)[0] for value in rows)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def _shot_cameras(sequence, dock):
    rows = []
    for binding in sequence.get_spawnables():
        label = str(binding.get_display_name())
        if not label.startswith("S3 Shot B"):
            continue
        template = binding.get_object_template()
        if template is None or not isinstance(template, unreal.CineCameraActor):
            raise PlanError("S3 Shot template is not a CineCameraActor: " + label)
        location = template.get_editor_property("root_component").get_editor_property("relative_location")
        rows.append({"label": label, "location": _vector(unreal.MathLibrary.inverse_transform_location(dock, location))})
    if sorted(row["label"] for row in rows) != ["S3 Shot B%02d" % number for number in range(2, 13)]:
        raise PlanError("unexpected S3 Shot camera census")
    return rows


def _local_bounds(mesh):
    box = mesh.get_bounding_box()
    return {"min": _vector(box.min), "max": _vector(box.max)}


def _world_bounds_dock(actor, dock):
    origin, extent = actor.get_actor_bounds(False, True)
    points = []
    for x in (origin.x - extent.x, origin.x + extent.x):
        for y in (origin.y - extent.y, origin.y + extent.y):
            for z in (origin.z - extent.z, origin.z + extent.z):
                points.append(_vector(unreal.MathLibrary.inverse_transform_location(dock, unreal.Vector(x, y, z))))
    return {"min": [min(point[axis] for point in points) for axis in range(3)],
            "max": [max(point[axis] for point in points) for axis in range(3)]}


def _load_legacy(index):
    try:
        with open(record_path(), encoding="utf-8") as handle:
            record = json.load(handle)
    except Exception as exc:
        raise PlanError("legacy record unreadable: " + str(exc))
    if (record.get("world") != EXPECTED_WORLD or record.get("tag") != LEGACY_TAG or
            not record.get("applied") or len(record.get("spawned", [])) != 9):
        raise PlanError("expected the applied nine-actor v1 beach record")
    actors = []
    by_label = {row.get("label"): row for row in record["spawned"]}
    if set(by_label) != set(LEGACY_LABELS):
        raise PlanError("legacy record labels changed")
    for label in LEGACY_LABELS:
        actor = _one(index, label)
        if (str(actor.get_path_name()) != by_label[label].get("object_path") or
                LEGACY_TAG not in [str(value) for value in actor.get_editor_property("tags")]):
            raise PlanError("legacy ownership mismatch: " + label)
        actors.append(actor)
    return record, actors


def _live_plan():
    index = _actor_index()
    root = _one(index, ROOT_LABEL)
    sequence = unreal.load_asset(ROOT_SEQUENCE)
    if not isinstance(sequence, unreal.LevelSequence):
        raise PlanError("S3 root sequence missing")
    dock = unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))
    cameras = _shot_cameras(sequence, dock)
    legacy, legacy_actors = _load_legacy(index)
    mesh_plan = build_sand_mesh(cameras)
    props, runtime_props = [], []
    for spec in PROP_SPECS:
        mesh = unreal.load_asset(spec["mesh_path"])
        if not isinstance(mesh, unreal.StaticMesh):
            raise PlanError("missing beach-v2 mesh: " + spec["mesh_path"])
        row = plan_prop(spec, _local_bounds(mesh), cameras)
        props.append(row)
        runtime_props.append({"row": row, "mesh": mesh})
    figures = []
    for label in FIGURE_LABELS:
        actor = _one(index, label)
        location = unreal.MathLibrary.inverse_transform_location(dock, actor.get_actor_location())
        bounds = _world_bounds_dock(actor, dock)
        surface = sand_height(float(location.x), float(location.y))
        delta = surface - bounds["min"][2]
        figures.append({"label": label, "actor_path": str(actor.get_path_name()),
                        "dock_xy": [float(location.x), float(location.y)],
                        "before_foot_z_cm": bounds["min"][2], "surface_z_cm": surface,
                        "raise_cm": delta, "planned_foot_z_cm": bounds["min"][2] + delta,
                        "before_transform": _plain_transform(actor.get_actor_transform())})
    existing = {label: len(index.get(label, [])) for label in [SAND_LABEL] + [row["label"] for row in props]}
    validate_v2_plan(mesh_plan, props, figures, cameras, existing)
    report = {"version": 2, "strategy": "subdivided_noise_plane_with_camera_cutouts",
              "sand": {"label": SAND_LABEL, "asset": SAND_ASSET,
                       "material": SAND_MATERIAL, "vertex_count": len(mesh_plan["vertices"]),
                       "triangle_count": len(mesh_plan["faces"]),
                       "min_camera_clearance_cm": mesh_plan["min_camera_clearance_cm"],
                       "z_range_cm": [min(row[2] for row in mesh_plan["vertices"]),
                                      max(row[2] for row in mesh_plan["vertices"])]},
              "props": props, "figures": figures, "cameras": cameras,
              "legacy_actor_count": len(legacy_actors), "inside_box_guard": True,
              "required_tests": list(REQUIRED_TESTS)}
    return report, {"mesh_plan": mesh_plan, "props": runtime_props, "figures": figures,
                    "legacy": legacy, "legacy_actors": legacy_actors,
                    "root": root, "dock": dock}


def _assert_context(apply, revert):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if (world.get_outermost().get_name() if world else None) != EXPECTED_WORLD:
        raise PlanError("WRONG_WORLD")
    if editor.get_game_world() is not None:
        raise PlanError("PIE_OR_SIE_ACTIVE")
    census = _package_census()
    if census["maps"] or census["content"]:
        raise PlanError("DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if os.path.exists(pending_path()):
        raise PlanError("V2_PENDING_RECORD_EXISTS")
    if revert:
        with open(record_path(), encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("version") != 2 or record.get("tag") != TAG or not record.get("applied"):
            raise PlanError("REVERT_REQUIRES_APPLIED_V2_RECORD")
    elif apply:
        # _live_plan performs the full legacy ownership check.
        if not os.path.isfile(record_path()):
            raise PlanError("APPLY_REQUIRES_V1_RECORD")


def _backup(prefix):
    source = project_file("Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"
    if not os.path.isfile(source):
        raise PlanError("LEVEL_BACKUP_SOURCE_MISSING")
    folder = project_file("Backups", prefix + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    if os.path.exists(folder):
        raise PlanError("BACKUP_EXISTS|path=" + folder)
    relative = os.path.relpath(source, project_file("Content"))
    destination = os.path.join(folder, "Content", relative)
    os.makedirs(os.path.dirname(destination))
    shutil.copy2(source, destination)
    return folder


def _write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _write_obj(mesh):
    lines = ["# deterministic Scene 3 beach-v2 sand layer", "o SM_S3_BeachV2_SandFloor"]
    for x, y, z in mesh["vertices"]:
        lines.append("v %.6f %.6f %.6f" % (x, y, z))
    for x, y, _ in mesh["vertices"]:
        lines.append("vt %.6f %.6f" % ((x + SAND_RX) / 250.0, (y + SAND_RY) / 250.0))
    lines.append("usemtl Sand")
    for face in mesh["faces"]:
        values = [index + 1 for index in face]
        lines.append("f %d/%d %d/%d %d/%d" % (values[0], values[0], values[1], values[1], values[2], values[2]))
    with open(obj_path(), "w", encoding="ascii", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _import_sand(mesh_plan):
    if unreal.EditorAssetLibrary.does_asset_exist(SAND_ASSET):
        raise PlanError("SAND_ASSET_ALREADY_EXISTS")
    _write_obj(mesh_plan)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", obj_path())
    task.set_editor_property("destination_path", SAND_ASSET.rsplit("/", 1)[0])
    task.set_editor_property("destination_name", SAND_ASSET.rsplit("/", 1)[1])
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(SAND_ASSET)
    if not isinstance(mesh, unreal.StaticMesh):
        raise PlanError("SAND_IMPORT_FAILED|objects=" + json.dumps([str(value) for value in task.imported_object_paths]))
    if not unreal.EditorAssetLibrary.save_asset(SAND_ASSET, only_if_is_dirty=False):
        raise PlanError("SAND_ASSET_SAVE_FAILED")
    return mesh


def _spawn_actor(subsystem, root, dock, row, mesh, material, tag):
    dock_transform = unreal.Transform(location=unreal.Vector(row["dock_location"][0], row["dock_location"][1], row["dock_location"][2]),
                                      rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=row.get("yaw", 0.0)),
                                      scale=unreal.Vector(row.get("scale", 1.0), row.get("scale", 1.0), row.get("scale", 1.0)))
    world = unreal.MathLibrary.compose_transforms(dock_transform, dock)
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, world.translation, world.rotation.rotator())
    if actor is None:
        raise PlanError("SPAWN_FAILED|label=" + row["label"])
    actor.modify(); actor.set_actor_label(row["label"])
    actor.modify(); actor.set_folder_path(FOLDER)
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(tag), unreal.Name("S3BeachV2." + row["kind"])])
    component = actor.get_editor_property("static_mesh_component")
    component.modify(); component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.modify(); component.set_editor_property("static_mesh", mesh)
    if material is not None:
        component.modify(); component.set_material(0, material)
    actor.modify(); actor.set_actor_scale3d(world.scale3d)
    actor.modify(); actor.attach_to_actor(root, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                                          unreal.AttachmentRule.KEEP_WORLD,
                                          unreal.AttachmentRule.KEEP_WORLD, False)
    if actor.get_attach_parent_actor() is not root:
        raise PlanError("PARENT_READBACK_MISMATCH|label=" + row["label"])
    return actor


def _save_level():
    census = _package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        raise PlanError("DIRTY_SCOPE|census=" + json.dumps(census, sort_keys=True))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise PlanError("LEVEL_SAVE_FAILED")
    after = _package_census()
    if after["maps"] or after["content"]:
        raise PlanError("POST_SAVE_DIRTY|census=" + json.dumps(after, sort_keys=True))
    return after


def _apply(run, report, runtime):
    backup = _backup("PreS3BeachV2-")
    record = {"version": 2, "tag": TAG, "world": EXPECTED_WORLD, "run": run,
              "backup": backup, "plan": report, "legacy": runtime["legacy"],
              "spawned": [], "figures": runtime["figures"], "sand_asset": SAND_ASSET,
              "applied": False}
    _write_json(pending_path(), record, exclusive=True)
    sand_mesh = _import_sand(runtime["mesh_plan"])
    sand_material = unreal.load_asset(SAND_MATERIAL)
    if sand_material is None:
        raise PlanError("SAND_MATERIAL_MISSING")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in runtime["legacy_actors"]:
        actor.modify()
        if not subsystem.destroy_actor(actor):
            raise PlanError("LEGACY_DESTROY_FAILED|label=" + actor.get_actor_label())
    sand_row = {"label": SAND_LABEL, "kind": "sand_floor",
                "dock_location": [SAND_CENTER_X, 0.0, 0.0], "yaw": 0.0, "scale": 1.0}
    created = [_spawn_actor(subsystem, runtime["root"], runtime["dock"], sand_row,
                            sand_mesh, sand_material, TAG)]
    for item in runtime["props"]:
        row = item["row"]
        spawn_row = dict(row)
        spawn_row["dock_location"] = [row["xy"][0], row["xy"][1], row["location_z_cm"]]
        created.append(_spawn_actor(subsystem, runtime["root"], runtime["dock"], spawn_row,
                                    item["mesh"], None, TAG))
    if len(created) != 9:
        raise PlanError("V2_SPAWN_COUNT")
    index = _actor_index()
    for row in runtime["figures"]:
        actor = _one(index, row["label"])
        if str(actor.get_path_name()) != row["actor_path"]:
            raise PlanError("FIGURE_PATH_CHANGED|label=" + row["label"])
        actor.modify()
        location = actor.get_actor_location()
        actor.set_actor_location(unreal.Vector(location.x, location.y, location.z + row["raise_cm"]), False, True)
        dock_bounds = _world_bounds_dock(actor, runtime["dock"])
        if abs(dock_bounds["min"][2] - row["surface_z_cm"]) > 0.5:
            raise PlanError("FIGURE_FOOT_READBACK|label=" + row["label"])
        row["after_transform"] = _plain_transform(actor.get_actor_transform())
        row["after_foot_z_cm"] = dock_bounds["min"][2]
    for actor in created:
        record["spawned"].append({"label": str(actor.get_actor_label()),
                                  "object_path": str(actor.get_path_name())})
    record["figures"] = runtime["figures"]
    record["post_save_census"] = _save_level()
    record["applied"] = True
    _write_json(pending_path(), record)
    os.replace(pending_path(), record_path())
    unreal.log("S3_BEACH_V2_DONE|run=%s|applied|actors=9|figures_on_sand=6|backup=%s|tests_required_singly=%s" %
               (run, backup, ",".join(REQUIRED_TESTS)))


def _restore_legacy(subsystem, root, dock, legacy):
    by_spawned = {row["label"]: row for row in legacy["spawned"]}
    new_paths = {}
    for row in legacy["plan"]["rows"]:
        mesh = unreal.load_asset(row["mesh_path"])
        material = unreal.load_asset(row["material_path"]) if row.get("material_path") else None
        if not isinstance(mesh, unreal.StaticMesh):
            raise PlanError("LEGACY_MESH_MISSING|label=" + row["label"])
        dock_location = row["transform"]["location"]
        spawn = {"label": row["label"], "kind": row["kind"], "dock_location": dock_location,
                 "yaw": row["transform"]["rotation"][2], "scale": 1.0}
        actor = _spawn_actor(subsystem, root, dock, spawn, mesh, material, LEGACY_TAG)
        actor.modify(); actor.set_actor_scale3d(unreal.Vector(*row["transform"]["scale"]))
        new_paths[row["label"]] = str(actor.get_path_name())
    for label, row in by_spawned.items():
        row["object_path"] = new_paths[label]
    return legacy


def _revert(run):
    with open(record_path(), encoding="utf-8") as handle:
        record = json.load(handle)
    index = _actor_index()
    targets = []
    for row in record["spawned"]:
        actor = _one(index, row["label"])
        if (str(actor.get_path_name()) != row["object_path"] or
                TAG not in [str(value) for value in actor.get_editor_property("tags")]):
            raise PlanError("REVERT_OWNERSHIP_MISMATCH|label=" + row["label"])
        targets.append(actor)
    dock = unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))
    root = _one(index, ROOT_LABEL)
    backup = _backup("PreS3BeachV2Revert-")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in targets:
        actor.modify()
        if not subsystem.destroy_actor(actor):
            raise PlanError("REVERT_DESTROY_FAILED|label=" + actor.get_actor_label())
    index = _actor_index()
    for row in record["figures"]:
        actor = _one(index, row["label"])
        actor.modify(); actor.set_actor_transform(_transform(row["before_transform"]), False, True)
    legacy = _restore_legacy(subsystem, root, dock, record["legacy"])
    census = _save_level()
    archived = record_path() + ".v2-reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(record_path(), archived)
    _write_json(record_path(), legacy, exclusive=True)
    unreal.log("S3_BEACH_V2_DONE|run=%s|reverted|v1_restored=9|figures_restored=6|retained_asset=%s|backup=%s|census=%s" %
               (run, SAND_ASSET, backup, json.dumps(census, sort_keys=True)))


def main(apply_override=None, revert_override=None):
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_BEACH_APPLY")) if apply_override is None else bool(apply_override)
    revert = bool(globals().get("S3_BEACH_REVERT")) if revert_override is None else bool(revert_override)
    try:
        if apply and revert:
            raise PlanError("APPLY_AND_REVERT_BOTH_SET")
        _assert_context(apply, revert)
        if revert:
            _revert(run)
            return
        report, runtime = _live_plan()
        unreal.log("S3_BEACH_V2_PLAN|run=%s|%s" %
                   (run, json.dumps(report, separators=(",", ":"), sort_keys=True)))
        if not apply:
            if _package_census() != {"maps": [], "content": []}:
                raise PlanError("DRY_RUN_DIRTIED_PACKAGES")
            unreal.log("S3_BEACH_V2_DRY_RUN_OK|run=%s|mutated=0|replace_v1=9|actors=9|figures_on_sand=6|camera_clearance_cm=150" % run)
            return
        _apply(run, report, runtime)
    except PlanError as exc:
        unreal.log_error("S3_BEACH_V2_%s_STOPPED|run=%s|reason=%s|census=%s" %
                         ("REVERT" if revert else ("APPLY" if apply else "DRY_RUN"), run, str(exc),
                          json.dumps(_package_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("S3_BEACH_V2_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(_package_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None and __name__ == "__main__":
    main()
