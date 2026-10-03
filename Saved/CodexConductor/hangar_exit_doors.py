"""Plan, apply, or revert the six hangar exit doorway shells.

Default execution is DRY and read-only.  APPLY and REVERT are available only
through the HANGAR_EXIT_DOORS_APPLY / HANGAR_EXIT_DOORS_REVERT globals used by
the small runner files beside this module.  Importing this module in ordinary
Python never contacts Unreal.

Backdrop intersections stop APPLY unless they match the measured Scene 3 Opal
Beach contract.  That one case uses a generated, immutable crop plus a child MI
and the backdrop plane mesh, so the closed leaf reproduces the art it covers.
"""
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROBE_NAME = "hangar_exit_doorways_probe.json"
OVERRIDES_NAME = "hangar_exit_doors_overrides.json"
RECORD_NAME = "hangar_exit_doors_record.json"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
BLACK_PATH = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
S3_BACKDROP_MESH = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_Backdrop"
S3_EXIT_MESH = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_S3_OpalBeach_ExitDoor"
S3_BACKDROP_MI = "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_Backdrop"
S3_EXIT_MI = "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_ExitDoor"
S3_EXIT_TEXTURE_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/Textures"
S3_EXIT_TEXTURE_NAMES = {
    "SkinColor": "T_S3_OpalBeach_ExitDoor_SkinColor",
    "SkinMask": "T_S3_OpalBeach_ExitDoor_SkinMask",
    "SkinNormal": "T_S3_OpalBeach_ExitDoor_SkinNormal",
}
STATIC_MESH_LOCAL_BOUNDS_CM = {
    CUBE_PATH: {"min": [-50.0, -50.0, -50.0], "max": [50.0, 50.0, 50.0]},
}
DOOR_WIDTH_CM = 300.0
DOOR_HEIGHT_CM = 450.0
SEAM_CM = 1.0
READBACK_TOLERANCE_CM = 0.1
REQUIRED_TESTS = (
    "InfinityStage.Editor.SavedMasterMatchesShow",
    "InfinityStage.Editor.SceneCutBindingsResolve",
)


if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_PATH = os.path.join(HERE, PROBE_NAME)
OVERRIDES_PATH = os.path.join(HERE, OVERRIDES_NAME)
RECORD_PATH = os.path.join(HERE, RECORD_NAME)
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))
S3_CROP_DIR = os.path.join(PROJECT_DIR, "DerivedAssets", "FlatV3", "Scene3",
                           "backdrop", "exit_door_crop")
S3_CROP_MANIFEST_PATH = os.path.join(S3_CROP_DIR, "s3_exit_door_crop_manifest.json")


class PlanError(ValueError):
    pass


def _bounds_overlap_yz(bounds, y0, y1, z0, z1):
    return not (float(bounds["max"][1]) <= y0 or float(bounds["min"][1]) >= y1 or
                float(bounds["max"][2]) <= z0 or float(bounds["min"][2]) >= z1)


def _one_wall_material(scene):
    walls = scene.get("far_walls", [])
    if len(walls) != 1:
        raise PlanError("S%d far-wall count is %d, expected 1" %
                        (scene["scene"], len(walls)))
    components = [row for row in walls[0].get("components", [])
                  if row.get("static_mesh")]
    if len(components) != 1:
        raise PlanError("S%d far wall does not have exactly one mesh component" % scene["scene"])
    slots = components[0].get("materials", [])
    slot0 = [row.get("material") for row in slots if int(row.get("slot", -1)) == 0]
    if len(slot0) != 1 or not slot0[0]:
        raise PlanError("S%d far wall has no unique material slot 0" % scene["scene"])
    return slot0[0], components[0].get("static_mesh"), walls[0], components[0]


def _rotation_matrix(rotation_rpy):
    roll, pitch, yaw = [math.radians(float(value)) for value in rotation_rpy]
    sr, cr = math.sin(roll), math.cos(roll)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sy, cy = math.sin(yaw), math.cos(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def _matrix_vector(matrix, vector):
    return [sum(matrix[row][axis] * vector[axis] for axis in range(3))
            for row in range(3)]


def _inverse_rotate(matrix, vector):
    return [sum(matrix[axis][column] * vector[axis] for axis in range(3))
            for column in range(3)]


def _transform_point(transform_row, point, description):
    location, rotation, scale = _transform_row({"transform": transform_row}, description)
    matrix = _rotation_matrix(rotation)
    offset = _matrix_vector(matrix, [float(point[axis]) * scale[axis] for axis in range(3)])
    return [location[axis] + offset[axis] for axis in range(3)]


def _inverse_transform_point(transform_row, point, description):
    location, rotation, scale = _transform_row({"transform": transform_row}, description)
    if any(abs(value) <= 1.0e-9 for value in scale):
        raise PlanError(description + " has zero scale")
    matrix = _rotation_matrix(rotation)
    local = _inverse_rotate(matrix, [float(point[axis]) - location[axis] for axis in range(3)])
    return [local[axis] / scale[axis] for axis in range(3)]


def _canonical_asset_path(path):
    value = str(path or "")
    return value.split(".", 1)[0]


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_s3_crop_manifest():
    if not os.path.isfile(S3_CROP_MANIFEST_PATH):
        raise PlanError("S3 crop manifest is absent: " + S3_CROP_MANIFEST_PATH)
    with open(S3_CROP_MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if int(manifest.get("schema_version", 0)) != 1:
        raise PlanError("S3 crop manifest schema_version is not 1")
    backdrop = manifest.get("backdrop", {})
    material = manifest.get("output_material", {})
    output_mesh = manifest.get("output_mesh", {})
    if (_canonical_asset_path(backdrop.get("mesh")) != S3_BACKDROP_MESH or
            _canonical_asset_path(backdrop.get("material")) != S3_BACKDROP_MI or
            _canonical_asset_path(output_mesh.get("asset")) != S3_EXIT_MESH or
            _canonical_asset_path(material.get("asset")) != S3_EXIT_MI or
            _canonical_asset_path(material.get("parent")) != S3_BACKDROP_MI):
        raise PlanError("S3 crop manifest asset contract changed")
    for kind in sorted(S3_EXIT_TEXTURE_NAMES):
        row = manifest.get("textures", {}).get(kind, {})
        output = os.path.join(S3_CROP_DIR, os.path.basename(str(row.get("output", ""))))
        if not os.path.isfile(output):
            raise PlanError("S3 crop texture is absent: " + output)
        if _sha256(output) != row.get("output_sha256"):
            raise PlanError("S3 crop texture hash mismatch: " + output)
        row["resolved_output"] = output
    mesh_source = os.path.join(S3_CROP_DIR, os.path.basename(str(output_mesh.get("source", ""))))
    if not os.path.isfile(mesh_source) or _sha256(mesh_source) != output_mesh.get("source_sha256"):
        raise PlanError("S3 crop leaf mesh source/hash mismatch: " + mesh_source)
    build_report = os.path.join(
        S3_CROP_DIR, os.path.basename(str(output_mesh.get("build_report", ""))))
    if (not os.path.isfile(build_report) or
            _sha256(build_report) != output_mesh.get("build_report_sha256")):
        raise PlanError("S3 crop leaf mesh build report/hash mismatch: " + build_report)
    output_mesh["resolved_source"] = mesh_source
    return manifest


def _s3_leaf_uv_rect(root_transform, backdrop_transform, leaf_location_root_cm,
                     leaf_size_yz_cm):
    """Map the visible leaf footprint through the placed backdrop transform."""
    half_y = float(leaf_size_yz_cm[0]) * 0.5
    half_z = float(leaf_size_yz_cm[1]) * 0.5
    samples = []
    for y in (float(leaf_location_root_cm[1]) - half_y,
              float(leaf_location_root_cm[1]) + half_y):
        for z in (float(leaf_location_root_cm[2]) - half_z,
                  float(leaf_location_root_cm[2]) + half_z):
            world = _transform_point(root_transform,
                                     [float(leaf_location_root_cm[0]), y, z],
                                     "S3 hangar root")
            local = _inverse_transform_point(backdrop_transform, world,
                                             "S3 backdrop")
            u = (local[1] + 1000.0) / 2000.0
            v = 1.0 - local[2] / 3000.0
            samples.append((u, v))
    return [min(row[0] for row in samples), min(row[1] for row in samples),
            max(row[0] for row in samples), max(row[1] for row in samples)]


def _resolve_s3_surface(scene, leaf_location_root_cm, leaf_size_yz_cm):
    backdrops = scene.get("backdrops", [])
    if len(backdrops) != 1 or str(backdrops[0].get("label")) != "S3 Backdrop":
        raise PlanError("S3 crop requires exactly the S3 Backdrop actor")
    backdrop = backdrops[0]
    components = [row for row in backdrop.get("components", []) if row.get("static_mesh")]
    if len(components) != 1:
        raise PlanError("S3 Backdrop does not have exactly one mesh component")
    slots = components[0].get("materials", [])
    slot0 = [row.get("material") for row in slots if int(row.get("slot", -1)) == 0]
    if (_canonical_asset_path(components[0].get("static_mesh")) != S3_BACKDROP_MESH or
            len(slot0) != 1 or _canonical_asset_path(slot0[0]) != S3_BACKDROP_MI):
        raise PlanError("S3 Backdrop mesh/material no longer matches the crop source")
    manifest = _load_s3_crop_manifest()
    calculated = _s3_leaf_uv_rect(
        scene["root"]["transform"], backdrop["transform"],
        leaf_location_root_cm, leaf_size_yz_cm)
    expected = [float(value) for value in
                manifest["leaf"]["uv_rect_left_top_right_bottom"]]
    worst = max(abs(calculated[index] - expected[index]) for index in range(4))
    if worst > 1.0e-9:
        raise PlanError(
            "S3 leaf/crop registration mismatch: calculated=%r expected=%r worst_uv=%g" %
            (calculated, expected, worst))
    backdrop_origin_world = [float(value) for value in
                             backdrop["transform"]["world_location_cm"]]
    backdrop_origin_root = _inverse_transform_point(
        scene["root"]["transform"], backdrop_origin_world, "S3 backdrop in root")
    return {
        "strategy": "cropped_texture_child_mi",
        "source_backdrop": "S3 Backdrop",
        "source_mesh": S3_BACKDROP_MESH,
        "source_material": S3_BACKDROP_MI,
        "leaf_mesh": S3_EXIT_MESH,
        "leaf_material": S3_EXIT_MI,
        "leaf_plane_x_root_cm": float(backdrop_origin_root[0]) - 0.05,
        "uv_rect_left_top_right_bottom": calculated,
        "uv_scale": [calculated[2] - calculated[0], calculated[3] - calculated[1]],
        "uv_offset": calculated[:2],
        "manifest": os.path.relpath(S3_CROP_MANIFEST_PATH, PROJECT_DIR).replace("\\", "/"),
        "texture_sources": {
            kind: manifest["textures"][kind]["resolved_output"]
            for kind in sorted(S3_EXIT_TEXTURE_NAMES)
        },
        "texture_assets": {
            kind: S3_EXIT_TEXTURE_ROOT + "/" + S3_EXIT_TEXTURE_NAMES[kind]
            for kind in sorted(S3_EXIT_TEXTURE_NAMES)
        },
        "mesh_source": manifest["output_mesh"]["resolved_source"],
        "mesh_asset": S3_EXIT_MESH,
        "import_verify_run": str(manifest["backdrop"]["import_verify_run"]),
    }


def piece_bounds_in_landed_root(piece, current_root, landed_root):
    half = [float(value) * 0.5 for value in piece["size_cm"]]
    center = [float(value) for value in piece["location_cm"]]
    points = []
    for x in (center[0] - half[0], center[0] + half[0]):
        for y in (center[1] - half[1], center[1] + half[1]):
            for z in (center[2] - half[2], center[2] + half[2]):
                world = _transform_point(current_root, [x, y, z], "current hangar root")
                points.append(_inverse_transform_point(landed_root, world, "landed hangar root"))
    return {"min": [min(point[axis] for point in points) for axis in range(3)],
            "max": [max(point[axis] for point in points) for axis in range(3)]}


def validate_landed_piece_bounds(scene, current_root):
    """Require every planned door piece to remain in its live landed hangar."""
    hangar = scene["hangar_dimensions"]
    landed_root = scene["landed_root_transform"]
    wall_bounds = scene.get("wall_bounds_root_cm") or {}
    wall_z0 = float((wall_bounds.get("min") or [0.0, 0.0, 0.0])[2])
    wall_z1 = float((wall_bounds.get("max") or [0.0, 0.0, hangar["height"]])[2])
    door_floor_z = float(scene.get("door_floor_root_z_cm", -float(hangar["hinge_z"])))
    outer = ((500.0, float(hangar["depth"]) + 500.0),
             (-float(hangar["half_w"]) - float(hangar["wall_t"]),
              float(hangar["half_w"]) + float(hangar["wall_t"])),
             (wall_z0 - 5.0, wall_z1))
    failures = []
    for piece in scene["pieces"]:
        bounds = piece_bounds_in_landed_root(piece, current_root, landed_root)
        piece["planned_aabb_landed_root_cm"] = bounds
        limits = list(outer)
        if piece["role"] in ("leaf", "black"):
            limits[1] = (-float(hangar["half_w"]), float(hangar["half_w"]))
            limits[2] = (door_floor_z - 5.0, door_floor_z + 600.0)
        for axis, interval in enumerate(limits):
            if (bounds["min"][axis] < interval[0] - 0.01 or
                    bounds["max"][axis] > interval[1] + 0.01):
                failures.append("%s leaves landed S%d box on axis %d" %
                                (piece["label"], int(scene["scene"]), axis))
    if failures:
        raise PlanError("; ".join(failures))
    return scene


def _transform_row(row, description):
    transform = row.get("transform") or {}
    try:
        return (
            [float(value) for value in transform["world_location_cm"]],
            [float(value) for value in transform["world_rotation_rpy"]],
            [float(value) for value in transform["world_scale"]],
        )
    except (KeyError, TypeError, ValueError):
        raise PlanError("%s has no usable world transform" % description)


def _mesh_local_bounds(component, mesh, scene_number):
    bounds = (component.get("static_mesh_local_bounds_cm") or
              component.get("mesh_local_bounds_cm") or
              STATIC_MESH_LOCAL_BOUNDS_CM.get(mesh))
    try:
        minimum = [float(value) for value in bounds["min"]]
        maximum = [float(value) for value in bounds["max"]]
    except (KeyError, TypeError, ValueError):
        raise PlanError("S%d far wall has no usable static-mesh local bounds" % scene_number)
    if len(minimum) != 3 or len(maximum) != 3 or any(
            maximum[axis] <= minimum[axis] for axis in range(3)):
        raise PlanError("S%d far wall static-mesh local bounds are invalid" % scene_number)
    return minimum, maximum


def _wall_bounds_in_root(scene, wall, component, mesh):
    """Return the wall OBB expressed as an AABB in its hangar-root frame."""
    n = int(scene["scene"])
    root = scene.get("root") or {}
    root_location, root_rotation, root_scale = _transform_row(root, "S%d hangar root" % n)
    # The probed far wall is a StaticMeshActor, so its StaticMeshComponent is
    # the actor root.  Prefer a future component transform if the probe records
    # one, and otherwise use that root-component actor transform.
    component_frame = component if component.get("transform") else wall
    wall_location, wall_rotation, wall_scale = _transform_row(
        component_frame, "S%d far-wall mesh component" % n)
    if any(abs(value) <= 1.0e-9 for value in root_scale + wall_scale):
        raise PlanError("S%d far wall or hangar root has zero scale" % n)
    local_min, local_max = _mesh_local_bounds(component, mesh, n)
    wall_matrix = _rotation_matrix(wall_rotation)
    root_matrix = _rotation_matrix(root_rotation)
    points = []
    for x in (local_min[0], local_max[0]):
        for y in (local_min[1], local_max[1]):
            for z in (local_min[2], local_max[2]):
                scaled = [x * wall_scale[0], y * wall_scale[1], z * wall_scale[2]]
                world_offset = _matrix_vector(wall_matrix, scaled)
                world = [wall_location[axis] + world_offset[axis] for axis in range(3)]
                relative_world = [world[axis] - root_location[axis] for axis in range(3)]
                unrotated = _inverse_rotate(root_matrix, relative_world)
                points.append([unrotated[axis] / root_scale[axis] for axis in range(3)])
    return {
        "min": [min(point[axis] for point in points) for axis in range(3)],
        "max": [max(point[axis] for point in points) for axis in range(3)],
    }


def _override_offsets(overrides):
    rows = {} if overrides is None else overrides.get("scenes", {})
    result = {}
    for key, value in rows.items():
        try:
            scene = int(key)
            result[scene] = float(value["door_offset_y_cm"])
        except (KeyError, TypeError, ValueError):
            raise PlanError("invalid override for scene %r" % key)
    if any(scene not in range(1, 7) for scene in result):
        raise PlanError("override scene must be 1..6")
    return result


def plan_doors(probe, overrides=None, include_scenes=None):
    """Build the deterministic, Unreal-free doorway plan."""
    if int(probe.get("schema_version", 0)) != 1:
        raise PlanError("probe schema_version is not 1")
    if probe.get("world") != EXPECTED_WORLD:
        raise PlanError("probe world mismatch")
    if probe.get("census_before") != probe.get("census_after"):
        raise PlanError("probe package census changed")
    scenes = list(probe.get("scenes", []))
    if sorted(int(row.get("scene", -1)) for row in scenes) != list(range(1, 7)):
        raise PlanError("probe must contain exactly scenes 1..6")
    requested = (set(range(1, 7)) if include_scenes is None
                 else {int(value) for value in include_scenes})
    if not requested or any(value not in range(1, 7) for value in requested):
        raise PlanError("include_scenes must be a non-empty subset of 1..6")
    offsets = _override_offsets(overrides)
    plans = []
    questions = []
    for scene in sorted(scenes, key=lambda row: int(row["scene"])):
        n = int(scene["scene"])
        if n not in requested:
            continue
        if int(scene.get("root_count", 0)) != 1:
            raise PlanError("S%d root count is not 1" % n)
        if scene.get("landed_preview_root_up") is not True:
            raise PlanError("S%d landed preview root is not UP" % n)
        if int(scene.get("exit_camera_count", 0)) != 1:
            raise PlanError("S%d Exit camera count is not 1" % n)
        wall_material, wall_mesh, wall, wall_component = _one_wall_material(scene)
        hangar = scene.get("hangar", {})
        required = ("depth", "half_w", "height", "wall_t", "roof", "hinge_z")
        if any(key not in hangar for key in required):
            raise PlanError("S%d hangar dimensions are incomplete" % n)
        depth = float(hangar["depth"])
        half_w = float(hangar["half_w"])
        height = float(hangar["height"])
        wall_t = float(hangar["wall_t"])
        hinge_z = float(hangar["hinge_z"])
        # hinge_z places the hangar root in the landed dock frame.  Door
        # heights are root-relative, so the stage-floor plane is -hinge_z.
        # S3 is the non-zero proof case: hinge_z=-120 and floor local Z=120.
        floor_z = -hinge_z
        if min(depth, half_w, height, wall_t) <= 0.0 or height <= DOOR_HEIGHT_CM:
            raise PlanError("S%d hangar dimensions cannot contain the door" % n)
        wall_bounds = _wall_bounds_in_root(scene, wall, wall_component, wall_mesh)
        measured_size = [float(wall_bounds["max"][axis]) - float(wall_bounds["min"][axis])
                         for axis in range(3)]
        expected_size = [wall_t, 2.0 * (half_w + wall_t), height]
        if any(abs(left - right) > 2.0 for left, right in
               zip(measured_size, expected_size)):
            raise PlanError("S%d far-wall size disagrees with the builder: measured=%r expected=%r" %
                            (n, measured_size, expected_size))

        offset = offsets.get(n, 0.0)
        opening_y0 = offset - DOOR_WIDTH_CM / 2.0
        opening_y1 = offset + DOOR_WIDTH_CM / 2.0
        wall_y0, wall_y1 = float(wall_bounds["min"][1]), float(wall_bounds["max"][1])
        if opening_y0 <= wall_y0 + SEAM_CM or opening_y1 >= wall_y1 - SEAM_CM:
            raise PlanError("S%d door offset leaves no side-wall margin" % n)
        opening_z0, opening_z1 = floor_z, floor_z + DOOR_HEIGHT_CM
        crossing = []
        for backdrop in scene.get("backdrops", []):
            bounds = backdrop.get("bounds_dock_cm")
            if bounds and _bounds_overlap_yz(bounds, opening_y0, opening_y1,
                                             opening_z0, opening_z1):
                crossing.append(str(backdrop.get("label")))
        resolved_surface = None
        if n == 3 and crossing == ["S3 Backdrop"]:
            provisional_leaf = [
                (float(wall_bounds["min"][0]) + float(wall_bounds["max"][0])) / 2.0,
                offset,
                floor_z + DOOR_HEIGHT_CM / 2.0,
            ]
            resolved_surface = _resolve_s3_surface(
                scene, provisional_leaf,
                [DOOR_WIDTH_CM - SEAM_CM, DOOR_HEIGHT_CM - SEAM_CM])
        elif crossing:
            questions.append({
                "scene": n,
                "reason": "backdrop_uv_match_required",
                "backdrops": crossing,
                "draft_offset_y_cm": offset,
            })

        x = (float(wall_bounds["min"][0]) + float(wall_bounds["max"][0])) / 2.0
        left_width = opening_y0 - wall_y0
        right_width = wall_y1 - opening_y1
        wall_z0, wall_z1 = float(wall_bounds["min"][2]), float(wall_bounds["max"][2])
        header_height = wall_z1 - opening_z1
        side_height = opening_z1 - wall_z0
        if min(header_height, side_height) <= 0.0:
            raise PlanError("S%d door does not fit the measured far-wall Z bounds" % n)
        leaf_x = (resolved_surface["leaf_plane_x_root_cm"]
                  if resolved_surface is not None else x - 0.05)
        leaf_mesh = (resolved_surface["leaf_mesh"]
                     if resolved_surface is not None else CUBE_PATH)
        leaf_material = (resolved_surface["leaf_material"]
                         if resolved_surface is not None else wall_material)
        pieces = [
            {"role": "above", "label": "S%d Hangar Far Wall Above Exit" % n,
             "location_cm": [x, 0.0, opening_z1 + header_height / 2.0],
             "size_cm": [wall_t, wall_y1 - wall_y0, header_height], "material": wall_material},
            {"role": "left", "label": "S%d Hangar Far Wall Left of Exit" % n,
             "location_cm": [x, wall_y0 + left_width / 2.0, wall_z0 + side_height / 2.0],
             "size_cm": [wall_t, left_width, side_height], "material": wall_material},
            {"role": "right", "label": "S%d Hangar Far Wall Right of Exit" % n,
             "location_cm": [x, opening_y1 + right_width / 2.0, wall_z0 + side_height / 2.0],
             "size_cm": [wall_t, right_width, side_height], "material": wall_material},
            {"role": "leaf", "label": "S%d Hangar Exit Door Leaf" % n,
             "location_cm": [leaf_x, offset, floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": ([0.1, DOOR_WIDTH_CM - SEAM_CM, DOOR_HEIGHT_CM - SEAM_CM]
                         if resolved_surface is not None else
                         [wall_t, DOOR_WIDTH_CM - SEAM_CM, DOOR_HEIGHT_CM - SEAM_CM]),
             "material": leaf_material, "mesh": leaf_mesh,
             "mesh_size_cm": ([0.0, DOOR_WIDTH_CM - SEAM_CM,
                                DOOR_HEIGHT_CM - SEAM_CM]
                              if resolved_surface is not None else [100.0, 100.0, 100.0]),
             "state": "closed"},
            {"role": "black", "label": "S%d Hangar Exit Black" % n,
             "location_cm": [float(wall_bounds["max"][0]) + 2.0, offset,
                              floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": [2.0, DOOR_WIDTH_CM, DOOR_HEIGHT_CM], "material": BLACK_PATH},
        ]
        if opening_z0 > wall_z0 + 0.01:
            pieces.insert(3, {
                "role": "below", "label": "S%d Hangar Far Wall Below Exit" % n,
                "location_cm": [x, offset, wall_z0 + (opening_z0 - wall_z0) / 2.0],
                "size_cm": [wall_t, DOOR_WIDTH_CM, opening_z0 - wall_z0],
                "material": wall_material,
            })
        plans.append({
            "scene": n,
            "root_label": "S%d Hangar Root" % n,
            "source_wall_label": "S%d Hangar Far Wall" % n,
            "wall_material": wall_material,
            "wall_mesh": wall_mesh,
            "wall_bounds_root_cm": wall_bounds,
            "piece_coordinate_frame": "hangar_root",
            "door_offset_y_cm": offset,
            "door_floor_root_z_cm": floor_z,
            "door_center_dock_cm": [depth, offset,
                                    hinge_z + floor_z + DOOR_HEIGHT_CM / 2.0],
            "camera_to_door_distance_cm": scene.get("camera_to_door_distance_cm"),
            "straight_walk": scene.get("straight_walk"),
            "roof": bool(hangar["roof"]),
            "hangar_dimensions": {key: hangar[key] for key in required},
            "landed_root_transform": scene["root"]["transform"],
            "backdrop_crossings": crossing,
            "surface_strategy": (resolved_surface["strategy"] if resolved_surface is not None
                                 else "far_wall_material" if not crossing
                                 else "UNRESOLVED_BACKDROP_UV"),
            "surface": resolved_surface,
            "pieces": pieces,
        })
    return {
        "world": EXPECTED_WORLD,
        "probe_run": probe.get("run"),
        "door_cm": {"width": DOOR_WIDTH_CM, "height": DOOR_HEIGHT_CM, "seam": SEAM_CM},
        "scenes": plans,
        "open_questions": questions,
        "apply_ready": not questions,
        "required_tests": list(REQUIRED_TESTS),
    }


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("required file is absent: " + path)
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def package_census():
    def names(values):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in values)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def stop(run, reason):
    unreal.log_error("HANGAR_EXIT_DOORS_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def actor_index():
    result = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def one_actor(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        stop(run, "reason=ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _plain_actor(actor):
    parent = actor.get_attach_parent_actor()
    component = actor.get_editor_property("static_mesh_component")
    return {
        "label": str(actor.get_actor_label()),
        "parent_label": str(parent.get_actor_label()) if parent else None,
        "location": [float(value) for value in actor.get_actor_location().to_tuple()],
        "rotation": [float(actor.get_actor_rotation().roll), float(actor.get_actor_rotation().pitch),
                     float(actor.get_actor_rotation().yaw)],
        "scale": [float(value) for value in actor.get_actor_scale3d().to_tuple()],
        "mesh": str(component.get_editor_property("static_mesh").get_path_name()),
        "material": str(component.get_material(0).get_path_name()),
        "tags": [str(tag) for tag in actor.tags],
    }


def _plain_pose(actor):
    return {
        "location": [float(value) for value in actor.get_actor_location().to_tuple()],
        "rotation": [float(actor.get_actor_rotation().roll), float(actor.get_actor_rotation().pitch),
                     float(actor.get_actor_rotation().yaw)],
        "scale": [float(value) for value in actor.get_actor_scale3d().to_tuple()],
    }


def _same_vector(left, right, tolerance=READBACK_TOLERANCE_CM):
    return max(abs(float(left[index]) - float(right[index])) for index in range(3)) <= tolerance


def _set_root_local(actor, root, location, size, mesh_size=None):
    actor.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_relative_location(unreal.Vector(*location), False, True)
    actor.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    source = mesh_size or [100.0, 100.0, 100.0]
    scale = [1.0 if abs(float(source[index])) <= 1.0e-9
             else float(size[index]) / float(source[index]) for index in range(3)]
    actor.set_actor_relative_scale3d(unreal.Vector(*scale))


def _spawn_piece(subsystem, root, piece, cube, material):
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, root.get_actor_location(),
                                             root.get_actor_rotation(), False)
    actor.set_actor_label(piece["label"])
    component = actor.get_editor_property("static_mesh_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    mesh = cube
    if _canonical_asset_path(piece.get("mesh")) not in ("", _canonical_asset_path(CUBE_PATH)):
        mesh = unreal.load_asset(piece["mesh"])
        if mesh is None:
            raise PlanError("piece mesh failed to load: " + str(piece["mesh"]))
    component.set_static_mesh(mesh)
    component.set_material(0, material)
    component.set_cast_shadow(piece["role"] != "black")
    _set_root_local(actor, root, piece["location_cm"], piece["size_cm"],
                    piece.get("mesh_size_cm"))
    actor.tags = [unreal.Name("HangarExitDoor"), unreal.Name("HangarExit.%s" % piece["role"])]
    return actor


def _context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "reason=SEQUENCER_IS_OPEN")
    census = package_census()
    if census != {"content": [], "maps": []}:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    return world


def _level_disk_path():
    relative = EXPECTED_WORLD.removeprefix("/Game/").replace("/", os.sep) + ".umap"
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), relative)


def _backup(run, purpose):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s" % (purpose, run))
    os.makedirs(folder, exist_ok=False)
    source = _level_disk_path()
    if not os.path.isfile(source):
        stop(run, "reason=LEVEL_BACKUP_SOURCE_MISSING|path=" + source)
    target = os.path.join(folder, os.path.basename(source))
    shutil.copy2(source, target)
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump({"run": run, "world": EXPECTED_WORLD, "source": source,
                   "backup": target, "bytes": os.path.getsize(target)}, handle, indent=2)
    return folder


def _save_level_only(run):
    census = package_census()
    if census != {"content": [], "maps": [EXPECTED_WORLD]}:
        stop(run, "reason=TOUCHED_CENSUS|census=" + json.dumps(census, sort_keys=True))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    final = package_census()
    if final != {"content": [], "maps": []}:
        stop(run, "reason=DIRTY_AFTER_SAVE|census=" + json.dumps(final, sort_keys=True))
    return final


def _write_record(record, mode="w"):
    with open(RECORD_PATH, mode, encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)


def _configure_crop_texture(texture, kind):
    texture.modify()
    texture.set_editor_property("mip_gen_settings",
                                unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    if kind == "SkinColor":
        texture.set_editor_property("srgb", True)
        texture.set_editor_property("compression_settings",
                                    unreal.TextureCompressionSettings.TC_BC7)
    elif kind == "SkinMask":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("compression_settings",
                                    unreal.TextureCompressionSettings.TC_MASKS)
    elif kind == "SkinNormal":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("compression_settings",
                                    unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("flip_green_channel", False)
    else:
        raise PlanError("unknown S3 crop texture kind: " + str(kind))


def _s3_leaf_fbx_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    data = options.get_editor_property("static_mesh_import_data")
    data.set_editor_property("import_translation", unreal.Vector(0.0, 0.0, 0.0))
    data.set_editor_property("import_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    data.set_editor_property("import_uniform_scale", 1.0)
    data.set_editor_property("combine_meshes", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("convert_scene", True)
    data.set_editor_property("force_front_x_axis", False)
    data.set_editor_property("bake_pivot_in_vertex", False)
    data.set_editor_property("normal_import_method",
                             unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    return options


def _ensure_s3_surface_assets(plan, run):
    surfaces = [row.get("surface") for row in plan["scenes"]
                if int(row["scene"]) == 3 and row.get("surface")]
    if not surfaces:
        return []
    if len(surfaces) != 1:
        stop(run, "reason=S3_SURFACE_COUNT|count=%d" % len(surfaces))
    surface = surfaces[0]
    paths = (list(surface["texture_assets"].values()) +
             [surface["mesh_asset"], surface["leaf_material"]])
    exists = [bool(unreal.EditorAssetLibrary.does_asset_exist(path)) for path in paths]
    if any(exists) and not all(exists):
        stop(run, "reason=S3_SURFACE_PARTIAL_ASSETS|paths=" + json.dumps(paths))
    created = []
    textures = {}
    if not any(exists):
        mesh_task = unreal.AssetImportTask()
        mesh_task.set_editor_property("filename", surface["mesh_source"])
        mesh_task.set_editor_property("destination_path", surface["mesh_asset"].rsplit("/", 1)[0])
        mesh_task.set_editor_property("destination_name", surface["mesh_asset"].rsplit("/", 1)[1])
        mesh_task.set_editor_property("automated", True)
        mesh_task.set_editor_property("replace_existing", False)
        mesh_task.set_editor_property("save", False)
        mesh_task.set_editor_property("options", _s3_leaf_fbx_options())
        tasks = [mesh_task]
        for kind in sorted(S3_EXIT_TEXTURE_NAMES):
            source = surface["texture_sources"][kind]
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", source)
            task.set_editor_property("destination_path", S3_EXIT_TEXTURE_ROOT)
            task.set_editor_property("destination_name", S3_EXIT_TEXTURE_NAMES[kind])
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", False)
            tasks.append(task)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        mesh = unreal.EditorAssetLibrary.load_asset(surface["mesh_asset"])
        if not isinstance(mesh, unreal.StaticMesh):
            stop(run, "reason=S3_LEAF_MESH_IMPORT_FAILED")
        created.append(surface["mesh_asset"])
        for kind, path in surface["texture_assets"].items():
            texture = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(texture, unreal.Texture2D):
                stop(run, "reason=S3_TEXTURE_IMPORT_FAILED|kind=%s|path=%s" % (kind, path))
            _configure_crop_texture(texture, kind)
            textures[kind] = texture
            created.append(path)
        parent = unreal.EditorAssetLibrary.load_asset(surface["source_material"])
        if not isinstance(parent, unreal.MaterialInstanceConstant):
            stop(run, "reason=S3_PARENT_MI_MISSING")
        folder, name = surface["leaf_material"].rsplit("/", 1)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
        if not isinstance(instance, unreal.MaterialInstanceConstant):
            stop(run, "reason=S3_CHILD_MI_CREATE_FAILED")
        instance.modify()
        unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
        for kind, texture in textures.items():
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                instance, kind, texture)
        unreal.MaterialEditingLibrary.update_material_instance(instance)
        created.append(surface["leaf_material"])
        for path in created:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                stop(run, "reason=S3_SURFACE_SAVE_FAILED|path=" + path)
    instance = unreal.EditorAssetLibrary.load_asset(surface["leaf_material"])
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        stop(run, "reason=S3_CHILD_MI_READBACK_FAILED")
    parent = instance.get_editor_property("parent")
    if _canonical_asset_path(parent.get_path_name() if parent else None) != S3_BACKDROP_MI:
        stop(run, "reason=S3_CHILD_MI_PARENT_MISMATCH")
    mesh = unreal.EditorAssetLibrary.load_asset(surface["mesh_asset"])
    if not isinstance(mesh, unreal.StaticMesh):
        stop(run, "reason=S3_LEAF_MESH_READBACK_FAILED")
    box = mesh.get_bounding_box()
    dimensions = [float(box.max.x - box.min.x), float(box.max.y - box.min.y),
                  float(box.max.z - box.min.z)]
    slots = [str(row.get_editor_property("material_slot_name"))
             for row in mesh.get_editor_property("static_materials")]
    if (dimensions[0] > 0.1 or abs(dimensions[1] - 299.0) > 0.1 or
            abs(dimensions[2] - 449.0) > 0.1 or slots != ["Front"]):
        stop(run, "reason=S3_LEAF_MESH_CONTRACT|dimensions=%s|slots=%s" %
             (dimensions, slots))
    for kind, path in surface["texture_assets"].items():
        texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
            instance, kind)
        if _canonical_asset_path(texture.get_path_name() if texture else None) != path:
            stop(run, "reason=S3_CHILD_MI_TEXTURE_MISMATCH|kind=" + kind)
    if package_census() != {"content": [], "maps": []}:
        stop(run, "reason=S3_SURFACE_ASSETS_DIRTY_AFTER_SAVE|census=" +
             json.dumps(package_census(), sort_keys=True))
    return created


def select_job_a_plan(plan):
    """Apply S1/S2/S4/S5/S6, adding S3 only when its backdrop gate is clear."""
    unresolved = {int(row["scene"]) for row in plan.get("open_questions", [])}
    unexpected = sorted(unresolved - {3})
    if unexpected:
        raise PlanError("unresolved backdrop UV outside S3: %r" % unexpected)
    selected = {1, 2, 4, 5, 6}
    if 3 not in unresolved:
        selected.add(3)
    result = dict(plan)
    result["all_scenes_apply_ready"] = bool(plan["apply_ready"])
    result["scenes"] = [row for row in plan["scenes"] if int(row["scene"]) in selected]
    result["applied_scenes"] = sorted(selected)
    result["skipped_scenes"] = sorted(set(range(1, 7)) - selected)
    result["apply_ready"] = sorted(selected) in ([1, 2, 4, 5, 6], [1, 2, 3, 4, 5, 6])
    return result


def select_s3_completion_plan(plan):
    """Select only the crop-resolved S3 work for extending the applied Job A record."""
    questions = [row for row in plan.get("open_questions", [])
                 if int(row.get("scene", -1)) == 3]
    rows = [row for row in plan["scenes"] if int(row["scene"]) == 3]
    if questions or len(rows) != 1 or rows[0].get("surface_strategy") != "cropped_texture_child_mi":
        raise PlanError("S3 completion selected before the backdrop crop resolved")
    result = dict(plan)
    result["scenes"] = rows
    result["applied_scenes"] = [3]
    result["skipped_scenes"] = [1, 2, 4, 5, 6]
    result["apply_ready"] = True
    result["extension_mode"] = "s3_after_job_a"
    return result


def validate_live_plan_bounds(plan, run):
    index = actor_index()
    for scene in plan["scenes"]:
        root = one_actor(index, scene["root_label"], run)
        current_root = {
            "world_location_cm": list(root.get_actor_location().to_tuple()),
            "world_rotation_rpy": [float(root.get_actor_rotation().roll),
                                   float(root.get_actor_rotation().pitch),
                                   float(root.get_actor_rotation().yaw)],
            "world_scale": list(root.get_actor_scale3d().to_tuple()),
        }
        try:
            validate_landed_piece_bounds(scene, current_root)
        except PlanError as exc:
            stop(run, "reason=LANDED_BOUNDS_REFUSED|scene=%d|detail=%s" %
                 (scene["scene"], str(exc)))
    return plan


def apply_plan(plan, run):
    if not plan["apply_ready"]:
        stop(run, "reason=UNRESOLVED_BACKDROP_UV|questions=" +
             json.dumps(plan["open_questions"], separators=(",", ":"), sort_keys=True))
    extension = plan.get("extension_mode") == "s3_after_job_a"
    prior_record = None
    if os.path.exists(RECORD_PATH):
        if not extension:
            stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")
        prior_record = _load_json(RECORD_PATH)
        prior_scenes = sorted(int(value) for value in
                              prior_record.get("plan", {}).get("applied_scenes", []))
        if (prior_record.get("applied") is not True or prior_scenes != [1, 2, 4, 5, 6] or
                sorted(int(value) for value in
                       prior_record.get("plan", {}).get("skipped_scenes", [])) != [3]):
            stop(run, "reason=S3_EXTENSION_RECORD_CONTEXT")
    elif extension:
        stop(run, "reason=S3_EXTENSION_RECORD_MISSING")
    cube = unreal.load_asset(CUBE_PATH)
    black = unreal.load_asset(BLACK_PATH)
    if cube is None or black is None:
        stop(run, "reason=REQUIRED_ENGINE_ASSET_MISSING")
    index = actor_index()
    root_before = {}
    originals = []
    all_new_labels = []
    for scene in plan["scenes"]:
        root = one_actor(index, scene["root_label"], run)
        wall = one_actor(index, scene["source_wall_label"], run)
        current_root = {
            "world_location_cm": list(root.get_actor_location().to_tuple()),
            "world_rotation_rpy": [float(root.get_actor_rotation().roll),
                                   float(root.get_actor_rotation().pitch),
                                   float(root.get_actor_rotation().yaw)],
            "world_scale": list(root.get_actor_scale3d().to_tuple()),
        }
        try:
            validate_landed_piece_bounds(scene, current_root)
        except PlanError as exc:
            stop(run, "reason=LANDED_BOUNDS_REFUSED|scene=%d|detail=%s" %
                 (scene["scene"], str(exc)))
        root_before[str(scene["scene"])] = _plain_pose(root)
        wall_before = _plain_actor(wall)
        if (wall_before["mesh"] != scene["wall_mesh"] or
                wall_before["material"] != scene["wall_material"]):
            stop(run, "reason=LIVE_WALL_SURFACE_CHANGED|scene=%d" % scene["scene"])
        originals.append({"scene": scene["scene"], "actor": wall_before})
        all_new_labels.extend(piece["label"] for piece in scene["pieces"])
    conflicts = [label for label in all_new_labels if label in index]
    if conflicts:
        stop(run, "reason=TARGET_LABELS_ALREADY_EXIST|labels=" + json.dumps(conflicts))

    backup = _backup(run, "PreHangarExitDoorsS3" if extension else "PreHangarExitDoors")
    if extension:
        shutil.copy2(RECORD_PATH, os.path.join(backup, os.path.basename(RECORD_PATH)))
        record = prior_record
        record["applied"] = False
        record.setdefault("extensions", []).append({
            "mode": "s3_after_job_a", "run": run, "backup": backup,
            "probe_run": plan["probe_run"],
        })
        record["root_before"].update(root_before)
        record["originals"].extend(originals)
        record["plan"]["scenes"].extend(plan["scenes"])
        record["plan"]["applied_scenes"] = [1, 2, 3, 4, 5, 6]
        record["plan"]["skipped_scenes"] = []
        record["plan"]["open_questions"] = [
            row for row in record["plan"].get("open_questions", [])
            if int(row.get("scene", -1)) != 3]
        record["plan"]["apply_ready"] = True
        record["plan"]["all_scenes_apply_ready"] = True
        _write_record(record)
    else:
        record = {"schema_version": 1, "run": run, "world": EXPECTED_WORLD,
                  "backup": backup, "probe_run": plan["probe_run"], "plan": plan,
                  "root_before": root_before, "originals": originals, "created": [],
                  "applied": False, "required_tests": list(REQUIRED_TESTS)}
        _write_record(record, "x")
    record.setdefault("surface_assets_created", []).extend(
        _ensure_s3_surface_assets(plan, run))
    _write_record(record)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for scene in plan["scenes"]:
        index = actor_index()
        root = one_actor(index, scene["root_label"], run)
        wall = one_actor(index, scene["source_wall_label"], run)
        source_material = unreal.load_asset(scene["wall_material"])
        if source_material is None:
            stop(run, "reason=WALL_MATERIAL_LOAD_FAILED|scene=%d" % scene["scene"])
        above = next(piece for piece in scene["pieces"] if piece["role"] == "above")
        wall.set_actor_label(above["label"])
        component = wall.get_editor_property("static_mesh_component")
        component.set_static_mesh(cube)
        component.set_material(0, source_material)
        _set_root_local(wall, root, above["location_cm"], above["size_cm"])
        record["created"].append({"scene": scene["scene"], "label": above["label"],
                                  "reused_original": True})
        for piece in scene["pieces"]:
            if piece["role"] == "above":
                continue
            material = (black if piece["role"] == "black"
                        else unreal.load_asset(piece["material"]))
            if material is None:
                stop(run, "reason=PIECE_MATERIAL_LOAD_FAILED|label=" + piece["label"])
            _spawn_piece(subsystem, root, piece, cube, material)
            record["created"].append({"scene": scene["scene"], "label": piece["label"],
                                      "reused_original": False})
        _write_record(record)
    final = _save_level_only(run)
    index = actor_index()
    for scene in plan["scenes"]:
        root = one_actor(index, scene["root_label"], run)
        before = root_before[str(scene["scene"])]
        now = _plain_pose(root)
        if (not _same_vector(before["location"], now["location"]) or
                not _same_vector(before["rotation"], now["rotation"], 0.001) or
                not _same_vector(before["scale"], now["scale"], 0.000001)):
            stop(run, "reason=ROOT_MOVED|scene=%d" % scene["scene"])
        for piece in scene["pieces"]:
            actor = one_actor(index, piece["label"], run)
            location = list(actor.root_component.get_editor_property("relative_location").to_tuple())
            if not _same_vector(location, piece["location_cm"]):
                stop(run, "reason=PIECE_READBACK|label=" + piece["label"])
            if piece.get("mesh") or piece["role"] == "leaf":
                actual = _plain_actor(actor)
                expected_mesh = _canonical_asset_path(piece.get("mesh") or CUBE_PATH)
                if (_canonical_asset_path(actual["mesh"]) != expected_mesh or
                        _canonical_asset_path(actual["material"]) !=
                        _canonical_asset_path(piece["material"])):
                    stop(run, "reason=PIECE_SURFACE_READBACK|label=" + piece["label"])
    record["applied"] = True
    record["last_apply_run"] = run
    record["post_save_census"] = final
    record["landed_preview_roots_unchanged"] = True
    _write_record(record)
    applied = ",".join(str(value) for value in plan.get(
        "applied_scenes", [int(row["scene"]) for row in plan["scenes"]]))
    skipped = ",".join(str(value) for value in plan.get("skipped_scenes", [])) or "none"
    unreal.log("HANGAR_EXIT_DOORS_APPLY_OK|run=%s|scenes=%s|skipped=%s|state=closed|backup=%s|census=%s|tests_required_singly=%s" %
               (run, applied, skipped, backup, json.dumps(final, separators=(",", ":")),
                ",".join(REQUIRED_TESTS)))


def _restore_actor(actor, row, index, run):
    parent = one_actor(index, row["parent_label"], run) if row.get("parent_label") else None
    actor.detach_from_actor(unreal.DetachmentRule.KEEP_WORLD,
                            unreal.DetachmentRule.KEEP_WORLD,
                            unreal.DetachmentRule.KEEP_WORLD)
    actor.set_actor_location(unreal.Vector(*row["location"]), False, True)
    actor.set_actor_rotation(unreal.Rotator(roll=row["rotation"][0], pitch=row["rotation"][1],
                                            yaw=row["rotation"][2]), False)
    actor.set_actor_scale3d(unreal.Vector(*row["scale"]))
    if parent:
        actor.attach_to_actor(parent, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_label(row["label"])
    actor.tags = [unreal.Name(value) for value in row.get("tags", [])]
    component = actor.get_editor_property("static_mesh_component")
    component.set_static_mesh(unreal.load_asset(row["mesh"]))
    component.set_material(0, unreal.load_asset(row["material"]))


def revert_plan(run):
    record = _load_json(RECORD_PATH)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        stop(run, "reason=REVERT_RECORD_CONTEXT")
    backup = _backup(run, "PreHangarExitDoorsRevert")
    index = actor_index()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    originals = {int(row["scene"]): row["actor"] for row in record["originals"]}
    for scene in record["plan"]["scenes"]:
        n = int(scene["scene"])
        for piece in scene["pieces"]:
            found = index.get(piece["label"], [])
            if len(found) != 1:
                stop(run, "reason=REVERT_PIECE_COUNT|label=%s|count=%d" %
                     (piece["label"], len(found)))
            if piece["role"] == "above":
                _restore_actor(found[0], originals[n], index, run)
            else:
                subsystem.destroy_actor(found[0])
        index = actor_index()
    final = _save_level_only(run)
    index = actor_index()
    for n in sorted(originals):
        one_actor(index, "S%d Hangar Far Wall" % n, run)
        for suffix in ("Above Exit", "Below Exit", "Left of Exit", "Right of Exit"):
            if "S%d Hangar Far Wall %s" % (n, suffix) in index:
                stop(run, "reason=REVERT_LABEL_REMAINS|scene=%d" % n)
    archived = RECORD_PATH + ".reverted-" + run
    os.rename(RECORD_PATH, archived)
    reverted = ",".join(str(value) for value in sorted(originals))
    unreal.log("HANGAR_EXIT_DOORS_REVERT_OK|run=%s|scenes=%s|backup=%s|record=%s|census=%s|tests_required_singly=%s" %
               (run, reverted, backup, os.path.basename(archived),
                json.dumps(final, separators=(",", ":")), ",".join(REQUIRED_TESTS)))


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    apply = bool(globals().get("HANGAR_EXIT_DOORS_APPLY"))
    revert = bool(globals().get("HANGAR_EXIT_DOORS_REVERT"))
    if apply and revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    _context(run)
    if revert:
        revert_plan(run)
        return
    try:
        probe = _load_json(PROBE_PATH)
        overrides = _load_json(OVERRIDES_PATH, required=False)
        job_a = bool(globals().get("HANGAR_EXIT_DOORS_JOB_A"))
        job_s3 = bool(globals().get("HANGAR_EXIT_DOORS_S3_ONLY"))
        if job_a and job_s3:
            raise PlanError("JOB_A and S3_ONLY are mutually exclusive")
        plan = plan_doors(probe, overrides, include_scenes={3} if job_s3 else None)
        if job_a:
            plan = select_job_a_plan(plan)
        elif job_s3:
            plan = select_s3_completion_plan(plan)
        validate_live_plan_bounds(plan, run)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    if not apply:
        final = package_census()
        if final != {"content": [], "maps": []}:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(final, sort_keys=True))
        unreal.log("HANGAR_EXIT_DOORS_DRY_OK|run=%s|mutated=0|apply_ready=%d|plan=%s" %
                   (run, int(plan["apply_ready"]),
                    json.dumps(plan, separators=(",", ":"), sort_keys=True)))
        return
    apply_plan(plan, run)


if unreal is not None:
    main()
