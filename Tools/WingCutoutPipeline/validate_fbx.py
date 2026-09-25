"""Import a generated FBX into a clean Blender scene and validate its handoff data."""

from __future__ import annotations

import argparse
import bmesh
import json
import math
from pathlib import Path
import sys

import bpy


def args_from_blender():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", type=Path, required=True)
    parser.add_argument("--height-m", type=float)
    parser.add_argument("--panel-scale", type=float, default=1.0)
    parser.add_argument("--thickness-m", type=float, default=0.05)
    parser.add_argument("--thickness-axis", choices=("x", "y", "z"))
    parser.add_argument("--tolerance-m", type=float, default=0.002)
    return parser.parse_args(argv)


def main():
    args = args_from_blender()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one mesh, imported {len(meshes)}")
    obj = meshes[0]
    dimensions_xyz = [float(value) for value in obj.dimensions]
    dimensions = sorted(dimensions_xyz)
    errors = []
    if abs(dimensions[0] - args.thickness_m) > args.tolerance_m:
        errors.append(f"Thickness {dimensions[0]:.6f} m does not match {args.thickness_m:.6f} m")
    expected_height = args.height_m * args.panel_scale if args.height_m is not None else None
    if expected_height is not None and min(abs(value - expected_height) for value in dimensions) > args.tolerance_m:
        errors.append(f"No dimension matches expected final height {expected_height:.6f} m")
    if args.thickness_axis:
        axis_index = {"x": 0, "y": 1, "z": 2}[args.thickness_axis]
        if abs(dimensions_xyz[axis_index] - args.thickness_m) > args.tolerance_m:
            errors.append(
                f"Thickness is not on expected {args.thickness_axis.upper()} axis: "
                f"{dimensions_xyz[axis_index]:.6f} m"
            )
    if any(abs(float(value) - 1.0) > 1e-4 for value in obj.scale):
        errors.append(f"FBX object scale is not applied: {tuple(round(float(value), 6) for value in obj.scale)}")
    if any(abs(math.degrees(float(value))) > 1e-3 for value in obj.rotation_euler):
        errors.append(
            "FBX object rotation is not applied: "
            f"{tuple(round(math.degrees(float(value)), 6) for value in obj.rotation_euler)} degrees"
        )
    if not obj.data.uv_layers:
        errors.append("FBX contains no UV map")
    elif len(obj.data.uv_layers) != 1:
        errors.append(f"Expected exactly one photographic UV channel, found {len(obj.data.uv_layers)}")
    elif obj.data.uv_layers[0].name != "UVMap":
        errors.append(f"Expected photographic UV channel named UVMap, found {obj.data.uv_layers[0].name}")
    if len(obj.material_slots) != 3:
        errors.append(f"Expected exactly three material slots, found {len(obj.material_slots)}")
    material_names = [slot.material.name if slot.material else None for slot in obj.material_slots]
    expected_suffixes = ("_Front", "_Back", "_Edge")
    if len(material_names) == 3 and any(
        name is None or not name.endswith(suffix)
        for name, suffix in zip(material_names, expected_suffixes)
    ):
        errors.append(f"Material slot order is not Front/Back/Edge: {material_names}")

    audit = bmesh.new()
    audit.from_mesh(obj.data)
    non_triangle_faces = sum(1 for face in audit.faces if len(face.verts) != 3)
    non_manifold_edges = sum(1 for edge in audit.edges if len(edge.link_faces) != 2)
    degenerate_triangles = sum(
        1
        for face in audit.faces
        if len(face.verts) != 3 or face.calc_area() <= 1.0e-12
    )
    audit.free()
    if non_triangle_faces:
        errors.append(f"FBX contains {non_triangle_faces} non-triangle faces")
    if non_manifold_edges:
        errors.append(f"FBX contains {non_manifold_edges} non-manifold edges")
    if degenerate_triangles:
        errors.append(f"FBX contains {degenerate_triangles} degenerate triangles")
    uv_maps = []
    for layer in obj.data.uv_layers:
        coordinates = [tuple(item.uv) for item in layer.data]
        uv_maps.append({
            "name": layer.name,
            "count": len(coordinates),
            "min": [round(min(value[index] for value in coordinates), 6) for index in (0, 1)] if coordinates else None,
            "max": [round(max(value[index] for value in coordinates), 6) for index in (0, 1)] if coordinates else None,
            "unique_rounded": len({(round(value[0], 4), round(value[1], 4)) for value in coordinates}),
        })
    report = {
        "fbx": str(args.fbx.resolve()),
        "object": obj.name,
        "dimensions_m_sorted": [round(value, 6) for value in dimensions],
        "dimensions_m_xyz": [round(value, 6) for value in dimensions_xyz],
        "object_scale_xyz": [round(float(value), 6) for value in obj.scale],
        "object_rotation_deg_xyz": [round(math.degrees(float(value)), 6) for value in obj.rotation_euler],
        "vertices": len(obj.data.vertices),
        "polygons": len(obj.data.polygons),
        "uv_maps": uv_maps,
        "materials": material_names,
        "non_triangle_faces": non_triangle_faces,
        "non_manifold_edges": non_manifold_edges,
        "degenerate_triangles": degenerate_triangles,
        "errors": errors,
        "status": "ok" if not errors else "error",
    }
    print("WING_FBX_VALIDATION", json.dumps(report, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
