"""Blender-native transparent PNG -> Unreal-ready stage wing generator.

Run through Blender, not the system Python:
    blender --background --factory-startup --python blender_png_to_wing.py -- ...

The implementation intentionally has no third-party Python dependencies. Blender
loads the PNG, the alpha channel is traced into polygon loops, and Blender's own
curve filling creates the solid panel.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
import math
from pathlib import Path
import re
import shutil
import sys
import traceback

import bmesh
import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="A transparent PNG")
    source.add_argument("--input-dir", type=Path, help="Folder of transparent PNGs")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--height-m", type=float, default=6.0)
    parser.add_argument("--thickness-cm", type=float, default=5.0)
    parser.add_argument(
        "--ue-panel-scale",
        type=float,
        default=5.0,
        help="Bake this scale into panel width and height, leaving thickness unchanged",
    )
    parser.add_argument(
        "--ue-yaw-deg",
        type=float,
        default=90.0,
        help="Bake this Z-axis rotation into the exported mesh",
    )
    parser.add_argument("--manifest", type=Path, help="Optional per-file JSON settings")
    parser.add_argument("--alpha-threshold", type=float, default=0.5)
    parser.add_argument("--trace-max-size", type=int, default=1024)
    parser.add_argument("--simplify-px", type=float, default=1.5)
    parser.add_argument("--min-island-px", type=int, default=64)
    parser.add_argument("--min-loop-area-px", type=float, default=24.0)
    parser.add_argument(
        "--islands",
        choices=("largest", "all"),
        default="largest",
        help="Keep only the largest connected opaque region, or all useful islands",
    )
    parser.add_argument("--save-blend", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--export-fbx", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if not 2.0 <= args.height_m <= 8.0:
        raise ValueError("--height-m must be between 2 and 8 metres")
    if not 0.1 <= args.thickness_cm <= 50.0:
        raise ValueError("--thickness-cm must be between 0.1 and 50 cm")
    if not 0.001 <= args.ue_panel_scale <= 100.0:
        raise ValueError("--ue-panel-scale must be between 0.001 and 100")
    if not -360.0 <= args.ue_yaw_deg <= 360.0:
        raise ValueError("--ue-yaw-deg must be between -360 and 360 degrees")
    if not 0.0 < args.alpha_threshold < 1.0:
        raise ValueError("--alpha-threshold must be between 0 and 1")
    if args.trace_max_size < 64:
        raise ValueError("--trace-max-size must be at least 64")
    if args.simplify_px < 0.0:
        raise ValueError("--simplify-px cannot be negative")


def load_manifest(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("images", data)
    if not isinstance(entries, dict):
        raise ValueError("Manifest must contain an 'images' object keyed by PNG filename")
    return entries


def collect_inputs(args: argparse.Namespace) -> list[Path]:
    if args.input:
        paths = [args.input]
    else:
        paths = sorted(args.input_dir.glob("*.png"))
    paths = [path.resolve() for path in paths]
    if not paths:
        raise FileNotFoundError("No PNG files found")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing input files: " + ", ".join(missing))
    return paths


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.curves, bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def safe_name(stem: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return name or "Wing"


def trace_alpha(image_path: Path, settings: dict) -> tuple[list[list[tuple[float, float]]], dict]:
    image = bpy.data.images.load(str(image_path), check_existing=False)
    original_width, original_height = map(int, image.size)
    if original_width <= 0 or original_height <= 0:
        raise ValueError(f"Could not read image dimensions: {image_path}")

    trace_image = image.copy()
    max_size = int(settings["trace_max_size"])
    factor = min(1.0, max_size / max(original_width, original_height))
    trace_width = max(1, round(original_width * factor))
    trace_height = max(1, round(original_height * factor))
    if (trace_width, trace_height) != (original_width, original_height):
        trace_image.scale(trace_width, trace_height)

    pixels = trace_image.pixels[:]
    threshold = float(settings["alpha_threshold"])
    mask = bytearray(trace_width * trace_height)
    opaque_count = 0
    for index in range(trace_width * trace_height):
        opaque = pixels[index * 4 + 3] >= threshold
        mask[index] = 1 if opaque else 0
        opaque_count += int(opaque)
    bpy.data.images.remove(trace_image)
    bpy.data.images.remove(image)

    if opaque_count == 0:
        raise ValueError(f"PNG has no pixels above alpha threshold {threshold}: {image_path}")

    components = connected_components(mask, trace_width, trace_height)
    components.sort(key=len, reverse=True)
    min_island = int(settings["min_island_px"])
    kept = components[:1] if settings["islands"] == "largest" else [c for c in components if len(c) >= min_island]
    clean_mask = bytearray(trace_width * trace_height)
    for component in kept:
        for index in component:
            clean_mask[index] = 1

    loops = boundary_loops(clean_mask, trace_width, trace_height)
    simplified: list[list[tuple[float, float]]] = []
    for loop in loops:
        loop = simplify_closed(loop, float(settings["simplify_px"]))
        if len(loop) >= 3 and abs(signed_area(loop)) >= float(settings["min_loop_area_px"]):
            simplified.append(loop)
    if not simplified:
        raise ValueError(f"No usable silhouette loops were produced: {image_path}")

    metadata = {
        "original_width": original_width,
        "original_height": original_height,
        "trace_width": trace_width,
        "trace_height": trace_height,
        "opaque_pixels": opaque_count,
        "connected_components": len(components),
        "kept_components": len(kept),
        "loops": len(simplified),
        "path_points": sum(len(loop) for loop in simplified),
    }
    return simplified, metadata


def connected_components(mask: bytearray, width: int, height: int) -> list[list[int]]:
    visited = bytearray(len(mask))
    components: list[list[int]] = []
    for start, value in enumerate(mask):
        if not value or visited[start]:
            continue
        visited[start] = 1
        queue = deque([start])
        component: list[int] = []
        while queue:
            index = queue.popleft()
            component.append(index)
            x = index % width
            y = index // width
            if x > 0:
                neighbor = index - 1
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
            if x + 1 < width:
                neighbor = index + 1
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
            if y > 0:
                neighbor = index - width
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
            if y + 1 < height:
                neighbor = index + width
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        components.append(component)
    return components


def boundary_loops(mask: bytearray, width: int, height: int) -> list[list[tuple[float, float]]]:
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for index, opaque in enumerate(mask):
        if not opaque:
            continue
        x = index % width
        y = index // width
        if y == 0 or not mask[index - width]:
            edges.add(((x, y), (x + 1, y)))
        if x + 1 == width or not mask[index + 1]:
            edges.add(((x + 1, y), (x + 1, y + 1)))
        if y + 1 == height or not mask[index + width]:
            edges.add(((x + 1, y + 1), (x, y + 1)))
        if x == 0 or not mask[index - 1]:
            edges.add(((x, y + 1), (x, y)))

    outgoing: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for start, end in edges:
        outgoing[start].append(end)
    unused = set(edges)
    loops: list[list[tuple[float, float]]] = []
    while unused:
        start_edge = next(iter(unused))
        unused.remove(start_edge)
        start, current = start_edge
        previous = start
        loop: list[tuple[float, float]] = [start, current]
        guard = 0
        while current != start and guard <= len(edges):
            guard += 1
            candidates = [end for end in outgoing[current] if (current, end) in unused]
            if not candidates:
                break
            next_point = choose_boundary_turn(previous, current, candidates)
            unused.remove((current, next_point))
            previous, current = current, next_point
            loop.append(current)
        if current == start and len(loop) >= 4:
            loops.append(loop[:-1])
    return loops


def choose_boundary_turn(previous, current, candidates):
    directions = {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}
    incoming = directions[(current[0] - previous[0], current[1] - previous[1])]
    turn_priority = {1: 0, 0: 1, 3: 2, 2: 3}  # left, straight, right, back

    def key(point):
        direction = directions[(point[0] - current[0], point[1] - current[1])]
        return turn_priority[(direction - incoming) % 4]

    return min(candidates, key=key)


def signed_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def point_segment_distance_sq(point, start, end) -> float:
    vx, vy = end[0] - start[0], end[1] - start[1]
    wx, wy = point[0] - start[0], point[1] - start[1]
    length_sq = vx * vx + vy * vy
    if length_sq == 0:
        return wx * wx + wy * wy
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / length_sq))
    dx, dy = point[0] - (start[0] + t * vx), point[1] - (start[1] + t * vy)
    return dx * dx + dy * dy


def simplify_open(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 2 or tolerance <= 0:
        return points
    threshold = tolerance * tolerance
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        farthest_index = -1
        farthest_distance = 0.0
        for index in range(first + 1, last):
            distance = point_segment_distance_sq(points[index], points[first], points[last])
            if distance > farthest_distance:
                farthest_distance = distance
                farthest_index = index
        if farthest_index >= 0 and farthest_distance > threshold:
            keep.add(farthest_index)
            stack.append((first, farthest_index))
            stack.append((farthest_index, last))
    return [points[index] for index in sorted(keep)]


def simplify_closed(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 4 or tolerance <= 0:
        return points
    start_index = min(range(len(points)), key=lambda i: (points[i][0], points[i][1]))
    rotated = points[start_index:] + points[:start_index]
    split_index = max(
        range(1, len(rotated)),
        key=lambda i: (rotated[i][0] - rotated[0][0]) ** 2 + (rotated[i][1] - rotated[0][1]) ** 2,
    )
    first = simplify_open(rotated[: split_index + 1], tolerance)
    second = simplify_open(rotated[split_index:] + [rotated[0]], tolerance)
    return first[:-1] + second[:-1]


def create_materials(image_path: Path, asset_name: str, lightweight: bool = False):
    if lightweight:
        front = bpy.data.materials.new(f"M_{asset_name}_Front")
        back = bpy.data.materials.new(f"M_{asset_name}_Back")
        edge = bpy.data.materials.new(f"M_{asset_name}_Edge")
        return front, back, edge

    image = bpy.data.images.load(str(image_path), check_existing=False)
    image.colorspace_settings.name = "sRGB"

    def photo_material(name: str):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        bsdf = nodes.get("Principled BSDF")
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = image
        texture.interpolation = "Linear"
        links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(texture.outputs["Alpha"], bsdf.inputs["Alpha"])
        bsdf.inputs["Roughness"].default_value = 0.72
        try:
            material.surface_render_method = "DITHERED"
        except (AttributeError, TypeError):
            pass
        return material

    front = photo_material(f"M_{asset_name}_Front")
    back = photo_material(f"M_{asset_name}_Back")
    edge = bpy.data.materials.new(f"M_{asset_name}_Edge")
    edge.use_nodes = True
    edge_bsdf = edge.node_tree.nodes.get("Principled BSDF")
    edge_bsdf.inputs["Base Color"].default_value = (0.035, 0.018, 0.01, 1.0)
    edge_bsdf.inputs["Roughness"].default_value = 0.82
    return front, back, edge


def create_panel(loops, image_path: Path, settings: dict, asset_name: str):
    min_x = min(point[0] for loop in loops for point in loop)
    max_x = max(point[0] for loop in loops for point in loop)
    min_y = min(point[1] for loop in loops for point in loop)
    max_y = max(point[1] for loop in loops for point in loop)
    trace_height = float(settings["trace_height"])
    trace_width = float(settings["trace_width"])
    silhouette_height = max_y - min_y
    if silhouette_height <= 0:
        raise ValueError("Silhouette has zero height")
    metres_per_pixel = float(settings["height_m"]) / silhouette_height
    centre_x = (min_x + max_x) * 0.5

    curve = bpy.data.curves.new(f"C_{asset_name}", "CURVE")
    curve.dimensions = "2D"
    curve.resolution_u = 1
    curve.render_resolution_u = 1
    curve.fill_mode = "BOTH"
    curve.extrude = float(settings["thickness_cm"]) / 200.0
    curve.bevel_depth = 0.0

    for loop in loops:
        spline = curve.splines.new("POLY")
        spline.points.add(len(loop) - 1)
        for spline_point, (x, y) in zip(spline.points, loop):
            spline_point.co = (
                (x - centre_x) * metres_per_pixel,
                (y - min_y) * metres_per_pixel,
                0.0,
                1.0,
            )
        spline.use_cyclic_u = True

    obj = bpy.data.objects.new(f"SM_{asset_name}", curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.rotation_euler[0] = math.radians(90.0)

    # Preserve a non-destructive, hidden path source in saved .blend files. The
    # visible duplicate is converted to the FBX mesh below.
    source_curve = obj.copy()
    source_curve.data = obj.data.copy()
    source_curve.name = f"SRC_{asset_name}_Curve"
    source_curve.data.name = f"SRC_{asset_name}_Curve"
    bpy.context.collection.objects.link(source_curve)
    source_curve.hide_render = True
    source_curve.hide_set(True)

    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    mesh = obj.data
    mesh.name = f"SM_{asset_name}"
    front, back, edge = create_materials(
        image_path, asset_name, lightweight=not bool(settings["save_blend"])
    )
    obj.data.materials.append(front)
    obj.data.materials.append(back)
    obj.data.materials.append(edge)

    # Curve-to-Mesh creates a generated UV layer. It does not align with the
    # source PNG, and Unreal samples UV channel 0 by default. Remove every
    # inherited layer so the projected photographic mapping is the sole UV0.
    for inherited_uv in list(mesh.uv_layers):
        mesh.uv_layers.remove(inherited_uv)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        if polygon.normal.y < -0.9:
            polygon.material_index = 0
        elif polygon.normal.y > 0.9:
            polygon.material_index = 1
        else:
            polygon.material_index = 2
        for loop_index in polygon.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            pixel_x = vertex.x / metres_per_pixel + centre_x
            pixel_y = vertex.z / metres_per_pixel + min_y
            uv_layer.data[loop_index].uv = (pixel_x / trace_width, pixel_y / trace_height)

    for polygon in mesh.polygons:
        polygon.use_smooth = False
    mesh.update()

    # Do not leave triangulation or mesh cleanup to an FBX importer. Concave
    # photographic silhouettes can otherwise be triangulated differently by
    # Blender and Unreal, producing stretched or crossed texture fragments.
    # Clean and triangulate once here, then export that exact topology.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1.0e-7)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1.0e-9)
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    # Triangulation can expose a perfectly collinear boundary point as a
    # zero-area triangle. Collapse those microscopic edges, then triangulate
    # the affected faces again so the final surface stays closed.
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1.0e-7)
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(verbose=False, clean_customdata=True)
    mesh.update(calc_edges=True)
    for polygon in mesh.polygons:
        polygon.use_smooth = False

    # MeshEdge does not expose link_faces after leaving BMesh, so perform the
    # final topology audit in a short read-only BMesh pass.
    audit = bmesh.new()
    audit.from_mesh(mesh)
    non_manifold_edges = sum(1 for edge in audit.edges if len(edge.link_faces) != 2)
    degenerate_triangles = sum(
        1
        for face in audit.faces
        if len(face.verts) != 3 or face.calc_area() <= 1.0e-12
    )
    cleanup_metadata = {
        "triangles_only": all(len(face.verts) == 3 for face in audit.faces),
        "non_manifold_edges": non_manifold_edges,
        "degenerate_triangles": degenerate_triangles,
        "vertices": len(audit.verts),
        "triangles": len(audit.faces),
    }
    audit.free()
    if not cleanup_metadata["triangles_only"]:
        raise RuntimeError(f"Clean export still contains non-triangle faces: {asset_name}")
    if non_manifold_edges:
        raise RuntimeError(f"Clean export contains {non_manifold_edges} non-manifold edges: {asset_name}")
    if degenerate_triangles:
        raise RuntimeError(f"Clean export contains {degenerate_triangles} degenerate triangles: {asset_name}")

    # Bake the placement correction previously applied to every actor in UE5.
    # At this point the panel uses X=width, Y=thickness, Z=height, so scaling
    # X/Z preserves the authored 5 cm depth. Applying the transforms keeps the
    # imported Static Mesh and its placed Actors at rotation 0 and scale 1.
    panel_scale = float(settings["ue_panel_scale"])
    obj.scale = (panel_scale, 1.0, panel_scale)
    obj.rotation_euler[2] = math.radians(float(settings["ue_yaw_deg"]))
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    obj["wing_height_m"] = float(settings["height_m"])
    obj["wing_final_height_m"] = float(settings["height_m"]) * panel_scale
    obj["wing_thickness_cm"] = float(settings["thickness_cm"])
    obj["ue_panel_scale_baked"] = panel_scale
    obj["ue_yaw_deg_baked"] = float(settings["ue_yaw_deg"])
    obj["source_png"] = str(image_path)
    return obj, cleanup_metadata


def export_asset(obj, source_path: Path, output_dir: Path, settings: dict) -> dict:
    asset_name = obj.name.removeprefix("SM_")
    asset_dir = output_dir / asset_name
    texture_dir = asset_dir / "Textures"
    asset_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)
    texture_path = texture_dir / source_path.name
    if source_path.resolve() != texture_path.resolve():
        shutil.copy2(source_path, texture_path)

    for material in obj.data.materials:
        if material and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    node.image.filepath = str(texture_path)

    blend_path = asset_dir / f"SM_{asset_name}.blend"
    fbx_path = asset_dir / f"SM_{asset_name}.fbx"
    if settings["save_blend"]:
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
    if settings["export_fbx"]:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=True,
            object_types={"MESH"},
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_UNITS",
            use_space_transform=True,
            bake_space_transform=False,
            axis_forward="-Y",
            axis_up="Z",
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            use_tspace=True,
            add_leaf_bones=False,
            bake_anim=False,
            # In high-throughput mode the copied PNG is the explicit handoff.
            # Do not duplicate megabytes of raster data inside every FBX.
            path_mode="COPY" if settings["save_blend"] else "AUTO",
            embed_textures=bool(settings["save_blend"]),
        )
    return {
        "asset_name": asset_name,
        "blend": str(blend_path) if settings["save_blend"] else None,
        "fbx": str(fbx_path) if settings["export_fbx"] else None,
        "texture": str(texture_path),
        "vertices": len(obj.data.vertices),
        "polygons": len(obj.data.polygons),
        "dimensions_m": [round(value, 6) for value in obj.dimensions],
    }


def settings_for(path: Path, args: argparse.Namespace, manifest: dict) -> dict:
    overrides = manifest.get(path.name, manifest.get(path.stem, {}))
    settings = {
        "height_m": args.height_m,
        "thickness_cm": args.thickness_cm,
        "ue_panel_scale": args.ue_panel_scale,
        "ue_yaw_deg": args.ue_yaw_deg,
        "alpha_threshold": args.alpha_threshold,
        "trace_max_size": args.trace_max_size,
        "simplify_px": args.simplify_px,
        "min_island_px": args.min_island_px,
        "min_loop_area_px": args.min_loop_area_px,
        "islands": args.islands,
        "save_blend": args.save_blend,
        "export_fbx": args.export_fbx,
    }
    settings.update(overrides)
    height = float(settings["height_m"])
    if not 2.0 <= height <= 8.0:
        raise ValueError(f"Height for {path.name} must be between 2 and 8 metres")
    panel_scale = float(settings["ue_panel_scale"])
    if not 0.001 <= panel_scale <= 100.0:
        raise ValueError(f"UE panel scale for {path.name} must be between 0.001 and 100")
    yaw = float(settings["ue_yaw_deg"])
    if not -360.0 <= yaw <= 360.0:
        raise ValueError(f"UE yaw for {path.name} must be between -360 and 360 degrees")
    return settings


def process_one(path: Path, output_dir: Path, settings: dict) -> dict:
    reset_scene()
    loops, trace_metadata = trace_alpha(path, settings)
    settings.update(trace_metadata)
    asset_name = safe_name(path.stem)
    obj, cleanup_metadata = create_panel(loops, path, settings, asset_name)
    exported = export_asset(obj, path, output_dir, settings)
    exported.update({
        "source": str(path),
        "height_m": settings["height_m"],
        "final_height_m": float(settings["height_m"]) * float(settings["ue_panel_scale"]),
        "thickness_cm": settings["thickness_cm"],
        "ue_panel_scale": settings["ue_panel_scale"],
        "ue_yaw_deg": settings["ue_yaw_deg"],
        "placement_transform_baked": True,
        "mesh_cleanup": cleanup_metadata,
        "trace": trace_metadata,
        "status": "ok",
    })
    return exported


def main() -> int:
    args = parse_args()
    validate_args(args)
    manifest = load_manifest(args.manifest)
    inputs = collect_inputs(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for path in inputs:
        try:
            result = process_one(path, output_dir, settings_for(path, args, manifest))
            print("WING_PIPELINE_OK", json.dumps(result, sort_keys=True))
            results.append(result)
        except Exception as exc:  # Continue the batch and report the failed file.
            traceback.print_exc()
            failure = {"source": str(path), "status": "error", "error": str(exc)}
            print("WING_PIPELINE_ERROR", json.dumps(failure, sort_keys=True))
            results.append(failure)

    has_errors = any(result["status"] == "error" for result in results)
    report = {
        "status": "error" if has_errors else "ok",
        "result_count": len(results),
        "results": results,
    }
    report_path = args.report.resolve() if args.report else output_dir / "wing_pipeline_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"WING_PIPELINE_REPORT {report_path}")
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
