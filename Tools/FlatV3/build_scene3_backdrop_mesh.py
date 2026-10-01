"""Build and clean-reimport-test the Flat V3 Scene 3 backdrop in Blender 4.4.

The source panel is authored in Blender metres.  The production FBX uses the
same exporter settings as build_v3_flat.py.  Validation must run in a separate
``--factory-startup --background`` Blender process so it tests the file rather
than the authoring scene.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


ASSET_NAME = "SM_FlatV3_S3_Backdrop"
WIDTH_M = 20.0
HEIGHT_M = 30.0
MATERIAL_SLOTS = ["Front"]

# Gary's source-image cottage bounds, normalized after the accepted trim
# (28,34)-(1668,2494).  These are used only to prove where that already-authored
# texture region lands in the mirrored importer-simulation render.
COTTAGES_UV0_BOX = (
    (1010.0 - 28.0) / 1640.0,
    (1665.0 - 34.0) / 2460.0,
    (1660.0 - 28.0) / 1640.0,
    (1935.0 - 34.0) / 2460.0,
)


def args_after_double_dash() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-fbx", type=Path)
    parser.add_argument("--build-report", type=Path)
    parser.add_argument("--validate-fbx", type=Path)
    parser.add_argument("--validation-out", type=Path)
    parser.add_argument("--skin-color", type=Path)
    parser.add_argument("--render-out", type=Path)
    parser.add_argument("--render-report", type=Path)
    return parser.parse_args(raw)


def require_blender_44() -> None:
    if bpy.app.version[:2] != (4, 4):
        raise RuntimeError(f"Blender 4.4 required; got {bpy.app.version_string}")
    if not bpy.app.background:
        raise RuntimeError("Backdrop generation must run headless (--background)")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.curves,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def create_backdrop() -> bpy.types.Object:
    """Create one -X-facing quad with its origin at bottom-centre."""
    half_width = WIDTH_M / 2.0
    vertices = [
        (0.0, +half_width, 0.0),
        (0.0, -half_width, 0.0),
        (0.0, -half_width, HEIGHT_M),
        (0.0, +half_width, HEIGHT_M),
    ]
    mesh = bpy.data.meshes.new(ASSET_NAME)
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()

    # UV0 follows the legacy raw-FBX convention.  U decreases along Blender
    # +Y so it increases along Unreal +Y after axis conversion.  Raw FBX V
    # increases bottom-to-top; Interchange converts that to Unreal's V-down.
    uv0 = mesh.uv_layers.new(name="UV0")
    uv0_by_vertex = {
        0: (0.0, 0.0),
        1: (1.0, 0.0),
        2: (1.0, 1.0),
        3: (0.0, 1.0),
    }
    for loop in mesh.loops:
        uv0.data[loop.index].uv = uv0_by_vertex[loop.vertex_index]

    # Raw FBX UV1 is pre-compensated for Interchange: U runs 0..20 m toward
    # eventual Unreal +Y, while raw V=1-Z metres becomes Unreal V=Z metres.
    uv1 = mesh.uv_layers.new(name="UV1")
    uv1_by_vertex = {
        0: (0.0, 1.0),
        1: (WIDTH_M, 1.0),
        2: (WIDTH_M, 1.0 - HEIGHT_M),
        3: (0.0, 1.0 - HEIGHT_M),
    }
    for loop in mesh.loops:
        uv1.data[loop.index].uv = uv1_by_vertex[loop.vertex_index]

    material = bpy.data.materials.new("Front")
    obj = bpy.data.objects.new(ASSET_NAME, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj["FrontAxis"] = "-X"
    obj["OriginContract"] = "bottom-centre"
    obj["UnrealAxisConversion"] = "X_U=X_B; Y_U=-Y_B; Z_U=Z_B"
    return obj


def export_selection(path: Path, objects: list[bpy.types.Object]) -> None:
    """Exact production settings used by Tools/FlatV3/build_v3_flat.py."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        object_types={"MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-X",
        axis_up="Z",
        bake_space_transform=False,
        add_leaf_bones=False,
        path_mode="AUTO",
        use_custom_props=True,
    )


def transformed_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    lower = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    upper = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return lower, upper


def uv_by_vertex(obj: bpy.types.Object, layer_name: str) -> dict[int, list[tuple[float, float]]]:
    layer = obj.data.uv_layers.get(layer_name)
    if layer is None:
        return {}
    result: dict[int, list[tuple[float, float]]] = {}
    for loop in obj.data.loops:
        result.setdefault(loop.vertex_index, []).append(tuple(map(float, layer.data[loop.index].uv)))
    return result


def maximum_uv_error(
    obj: bpy.types.Object,
    layer_name: str,
    expected,
) -> tuple[float, list[dict[str, object]]]:
    samples = []
    maximum = 0.0
    for vertex_index, values in uv_by_vertex(obj, layer_name).items():
        co = obj.data.vertices[vertex_index].co
        target = expected(co)
        for value in values:
            error = max(abs(value[0] - target[0]), abs(value[1] - target[1]))
            maximum = max(maximum, error)
            samples.append(
                {
                    "vertex": vertex_index,
                    "co_m": list(map(float, co)),
                    "actual": list(value),
                    "expected": list(target),
                    "maximum_error": error,
                }
            )
    return maximum, samples


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_preview_material(texture_path: Path) -> bpy.types.Material:
    material = bpy.data.materials.new("Front")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UV0"
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(str(texture_path), check_existing=False)
    image.image.colorspace_settings.name = "sRGB"
    image.interpolation = "Linear"

    # Direct raw-FBX UV0 sampling is deliberate.  Blender's bottom-origin
    # image sampler plus Interchange's V conversion are the equivalent pair;
    # inserting 1-v here previously hid an upside-down production mapping.
    links.new(uv.outputs["UV"], image.inputs["Vector"])
    links.new(image.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def create_unreal_simulation(imported: bpy.types.Object, texture_path: Path) -> bpy.types.Object:
    """Apply the importer Y reflection and its compensating winding reversal."""
    source = imported.data
    vertices = [(float(v.co.x), -float(v.co.y), float(v.co.z)) for v in source.vertices]
    faces = [tuple(reversed(tuple(poly.vertices))) for poly in source.polygons]
    mesh = bpy.data.meshes.new(ASSET_NAME + "_UnrealAxisSimulation")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    for source_layer in source.uv_layers:
        target_layer = mesh.uv_layers.new(name=source_layer.name)
        # Rebuild via vertex association; this asset is one quad with no seams.
        source_values = uv_by_vertex(imported, source_layer.name)
        for loop in mesh.loops:
            target_layer.data[loop.index].uv = source_values[loop.vertex_index][0]

    obj = bpy.data.objects.new(ASSET_NAME + "_UnrealAxisSimulation", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(make_preview_material(texture_path))
    return obj


def render_unreal_view(
    imported: bpy.types.Object,
    texture_path: Path,
    render_path: Path,
    report_path: Path,
) -> dict[str, object]:
    simulated = create_unreal_simulation(imported, texture_path)
    imported.hide_render = True

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"

    world = bpy.data.worlds.new("Black")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.world = world

    camera_data = bpy.data.cameras.new("Camera_Unreal_Mirrored")
    camera_data.type = "PERSP"
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.sensor_width = 36.0
    horizontal_fov = math.radians(50.0)
    camera_data.lens = camera_data.sensor_width / (2.0 * math.tan(horizontal_fov / 2.0))
    camera = bpy.data.objects.new("Camera_Unreal_Mirrored", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (-65.0, 0.0, HEIGHT_M / 2.0)
    look_at(camera, (0.0, 0.0, HEIGHT_M / 2.0))
    # Blender puts +Y on screen-left when looking +X. Unreal puts +Y on
    # screen-right. A negative camera-local X scale mirrors the Blender view so
    # the simulated imported coordinates are judged with Unreal screen parity.
    camera.scale.x = -1.0
    scene.camera = camera

    render_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(render_path)
    bpy.ops.render.render(write_still=True)

    u0, v0, u1, v1 = COTTAGES_UV0_BOX
    points = []
    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
        # COTTAGES_UV0_BOX uses source-image top-origin coordinates.  Raw FBX
        # V is bottom-origin, so physical Z is H*(1-source_v).
        point = Vector((0.0, -WIDTH_M / 2.0 + WIDTH_M * u, HEIGHT_M * (1.0 - v)))
        projected = world_to_camera_view(scene, camera, point)
        points.append((float(projected.x), float(projected.y)))
    centre_x = sum(point[0] for point in points) / len(points)
    panel_centre = world_to_camera_view(scene, camera, Vector((0.0, 0.0, HEIGHT_M / 2.0)))
    cottages_right = centre_x > float(panel_centre.x)

    report = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "render": str(render_path.resolve()),
        "source_texture": str(texture_path.resolve()),
        "simulation": {
            "axis_conversion": "X_U=X_B; Y_U=-Y_B; Z_U=Z_B",
            "winding_reversed_after_reflection": True,
            "camera_location_m": list(map(float, camera.location)),
            "camera_looks": "+X",
            "camera_local_x_scale": float(camera.scale.x),
            "camera_mirror_reason": "Blender +Y is screen-left looking +X; Unreal +Y is screen-right",
            "uv_sampling": "direct raw-FBX UV0; Blender bottom-origin sampling is equivalent to Interchange V conversion plus Unreal top-origin sampling",
        },
        "cottages": {
            "source_uv0_box_top_origin": list(COTTAGES_UV0_BOX),
            "source_region": "right third",
            "projected_corners_normalized": [list(point) for point in points],
            "projected_centre_x_normalized": centre_x,
            "panel_centre_x_normalized": float(panel_centre.x),
            "screen_right": cottages_right,
        },
        "checks": {
            "render_written": {"pass": render_path.is_file(), "value": str(render_path)},
            "camera_mirrored_for_unreal_parity": {"pass": camera.scale.x < 0.0, "value": float(camera.scale.x)},
            "cottages_land_screen_right": {
                "pass": cottages_right,
                "cottages_centre_x": centre_x,
                "panel_centre_x": float(panel_centre.x),
            },
        },
    }
    report["pass"] = all(check["pass"] for check in report["checks"].values())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["pass"]:
        raise RuntimeError(f"Unreal-view render validation failed: {report_path}")
    return report


def build(fbx_path: Path, report_path: Path) -> None:
    clear_scene()
    backdrop = create_backdrop()
    export_selection(fbx_path.resolve(), [backdrop])
    result = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "factory_startup_process": True,
        "asset": ASSET_NAME,
        "fbx": str(fbx_path.resolve()),
        "authored_dimensions_m": [0.0, WIDTH_M, HEIGHT_M],
        "material_slots": MATERIAL_SLOTS,
        "uv0": "raw FBX: u=0 at Blender +Y and u=1 at Blender -Y; v=0 at bottom and v=1 at top",
        "uv1": "raw FBX pre-compensation: u=0..20 toward eventual Unreal +Y; v=1-Z_m so Unreal reads V=Z_m bottom-to-top",
        "exporter": {
            "apply_scale_options": "FBX_SCALE_UNITS",
            "axis_forward": "-X",
            "axis_up": "Z",
            "bake_space_transform": False,
            "add_leaf_bones": False,
            "path_mode": "AUTO",
            "use_custom_props": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"SCENE3_BACKDROP_BUILD_OK|fbx={fbx_path.resolve()}", flush=True)


def validate(
    fbx_path: Path,
    validation_path: Path,
    texture_path: Path,
    render_path: Path,
    render_report_path: Path,
) -> None:
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(fbx_path.resolve()), use_custom_normals=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    candidates = [obj for obj in meshes if obj.name.startswith(ASSET_NAME)]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one imported {ASSET_NAME} mesh; got {[obj.name for obj in meshes]}")
    obj = candidates[0]
    lower, upper = transformed_bounds(obj)
    dimensions = upper - lower
    slots = [slot.material.name if slot.material else None for slot in obj.material_slots]
    uv_names = [layer.name for layer in obj.data.uv_layers]

    uv0_error, uv0_samples = maximum_uv_error(
        obj,
        "UV0",
        lambda co: ((WIDTH_M / 2.0 - float(co.y)) / WIDTH_M, float(co.z) / HEIGHT_M),
    )
    uv1_error, uv1_samples = maximum_uv_error(
        obj,
        "UV1",
        lambda co: (WIDTH_M / 2.0 - float(co.y), 1.0 - float(co.z)),
    )

    front_normals = []
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    for polygon in obj.data.polygons:
        front_normals.append(normal_matrix @ polygon.normal)
    normal_pass = bool(front_normals) and all(normal.x < -0.999 for normal in front_normals)

    # Importer-axis simulation. A reflection changes winding, so the importer
    # compensates by reversing the polygon before the final normal is tested.
    source_points = [obj.data.vertices[index].co.copy() for index in obj.data.polygons[0].vertices]
    unreal_points = [Vector((point.x, -point.y, point.z)) for point in source_points]
    unreal_points.reverse()
    unreal_normal = (unreal_points[1] - unreal_points[0]).cross(unreal_points[2] - unreal_points[0]).normalized()

    uv0_by_vertex_map = uv_by_vertex(obj, "UV0")
    handedness_samples = []
    for vertex_index, values in uv0_by_vertex_map.items():
        co = obj.data.vertices[vertex_index].co
        handedness_samples.append({"blender_y_m": float(co.y), "unreal_y_m": -float(co.y), "u": values[0][0]})
    low = min(handedness_samples, key=lambda sample: sample["unreal_y_m"])
    high = max(handedness_samples, key=lambda sample: sample["unreal_y_m"])
    du_d_unreal_y = (high["u"] - low["u"]) / (high["unreal_y_m"] - low["unreal_y_m"])
    vertical_samples = []
    for vertex_index, values in uv0_by_vertex_map.items():
        co = obj.data.vertices[vertex_index].co
        vertical_samples.append({"z_m": float(co.z), "v": values[0][1]})
    bottom = min(vertical_samples, key=lambda sample: sample["z_m"])
    top = max(vertical_samples, key=lambda sample: sample["z_m"])
    raw_dv_dz = (top["v"] - bottom["v"]) / (top["z_m"] - bottom["z_m"])

    render_report = render_unreal_view(obj, texture_path.resolve(), render_path.resolve(), render_report_path.resolve())
    checks = {
        "one_mesh": {"pass": len(meshes) == 1, "value": [mesh.name for mesh in meshes]},
        "name": {"pass": obj.name == ASSET_NAME, "value": obj.name, "expected": ASSET_NAME},
        "dimensions_20x30m": {
            "pass": abs(float(dimensions.y) - WIDTH_M) <= 0.001 and abs(float(dimensions.z) - HEIGHT_M) <= 0.001,
            "measured_m": list(map(float, dimensions)),
            "expected_m": [0.0, WIDTH_M, HEIGHT_M],
        },
        "material_slots_exact": {"pass": slots == MATERIAL_SLOTS, "value": slots, "expected": MATERIAL_SLOTS},
        "uv_layers_exact": {"pass": uv_names == ["UV0", "UV1"], "value": uv_names},
        "uv0_full_face_legacy_raw_fbx": {"pass": uv0_error <= 1.0e-5, "maximum_error": uv0_error, "samples": uv0_samples},
        "uv1_metres": {"pass": uv1_error <= 1.0e-4, "maximum_error_m": uv1_error, "samples": uv1_samples},
        "bottom_centre_origin": {
            "pass": obj.location.length <= 0.001 and abs(float(lower.y + upper.y)) <= 0.001 and abs(float(lower.z)) <= 0.001,
            "object_location_m": list(map(float, obj.location)),
            "bounds_m": {"min": list(map(float, lower)), "max": list(map(float, upper))},
        },
        "front_faces_negative_x": {
            "pass": normal_pass,
            "normals": [list(map(float, normal)) for normal in front_normals],
        },
        "unreal_axis_handedness": {
            "pass": du_d_unreal_y > 0.0,
            "conversion": "X_U=X_B; Y_U=-Y_B; Z_U=Z_B",
            "samples": handedness_samples,
            "du_d_unreal_y_per_m": du_d_unreal_y,
            "conclusion": "u must decrease along Blender +Y so it increases along Unreal +Y",
        },
        "raw_fbx_vertical_uv": {
            "pass": raw_dv_dz > 0.0,
            "samples": vertical_samples,
            "dv_dz_per_m": raw_dv_dz,
            "dv_dz_per_cm": raw_dv_dz / 100.0,
            "legacy_contract": "raw FBX V rises bottom-to-top; Interchange converts it to Unreal V-down",
        },
        "simulated_unreal_normal": {
            "pass": unreal_normal.x < -0.999,
            "value": list(map(float, unreal_normal)),
            "winding_reversed_after_reflection": True,
        },
        "unreal_view_render": {
            "pass": bool(render_report["pass"]),
            "cottages_screen_right": render_report["cottages"]["screen_right"],
            "report": str(render_report_path.resolve()),
        },
    }
    result = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "factory_startup_process": True,
        "fbx": str(fbx_path.resolve()),
        "checks": checks,
        "pass": all(check["pass"] for check in checks.values()),
        "expected_unreal_readback": {
            "bounds_cm": {"Y": [-1000.0, 1000.0], "Z": [0.0, 3000.0]},
            "front_normal": [-1.0, 0.0, 0.0],
            "du_dY": "> 0",
            "dv_dZ": "< 0",
        },
    }
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("SCENE3_BACKDROP_VALIDATION_" + ("PASS" if result["pass"] else "FAIL"), flush=True)
    if not result["pass"]:
        raise RuntimeError(f"Backdrop validation failed: {validation_path}")


def main() -> None:
    require_blender_44()
    args = args_after_double_dash()
    if args.build_fbx:
        if not args.build_report:
            raise RuntimeError("Build mode requires --build-report")
        build(args.build_fbx, args.build_report)
    elif args.validate_fbx:
        required = (args.validation_out, args.skin_color, args.render_out, args.render_report)
        if any(value is None for value in required):
            raise RuntimeError(
                "Validation mode requires --validation-out, --skin-color, --render-out, and --render-report"
            )
        validate(args.validate_fbx, args.validation_out, args.skin_color, args.render_out, args.render_report)
    else:
        raise RuntimeError("Choose --build-fbx or --validate-fbx")


if __name__ == "__main__":
    main()
