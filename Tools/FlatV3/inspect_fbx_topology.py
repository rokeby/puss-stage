"""Inspect Flat V3 FBX topology in Blender 4.4 without Unreal.

Run with Blender 4.4 in background/factory-startup mode.  The report is aimed
at cross-importer triangle-count diagnosis: it records source polygon arity,
loop-triangle areas, repeated-index/zero-area triangles, and positional vertex
duplicates per LOD.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy


def args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(raw)


def quantized_position(vertex, digits: int = 9) -> tuple[float, float, float]:
    return tuple(round(float(value), digits) for value in vertex.co)


def inspect_mesh(obj: bpy.types.Object) -> dict:
    mesh = obj.data
    mesh.calc_loop_triangles()
    arity = Counter(len(polygon.vertices) for polygon in mesh.polygons)
    position_groups: dict[tuple[float, float, float], list[int]] = defaultdict(list)
    for vertex in mesh.vertices:
        position_groups[quantized_position(vertex)].append(vertex.index)
    duplicate_groups = [
        {"position_m": list(position), "indices": indices}
        for position, indices in position_groups.items()
        if len(indices) > 1
    ]
    degenerate = []
    minimum_area = math.inf
    for index, triangle in enumerate(mesh.loop_triangles):
        vertices = [mesh.loops[loop_index].vertex_index for loop_index in triangle.loops]
        coords = [mesh.vertices[vertex_index].co for vertex_index in vertices]
        area = 0.5 * float((coords[1] - coords[0]).cross(coords[2] - coords[0]).length)
        minimum_area = min(minimum_area, area)
        repeated_indices = len(set(vertices)) != 3
        repeated_positions = len({quantized_position(mesh.vertices[vertex_index]) for vertex_index in vertices}) != 3
        if repeated_indices or repeated_positions or area <= 1.0e-12:
            polygon = mesh.polygons[triangle.polygon_index]
            slot = None
            if 0 <= polygon.material_index < len(obj.material_slots):
                material = obj.material_slots[polygon.material_index].material
                slot = material.name if material else None
            degenerate.append({
                "loop_triangle_index": index,
                "polygon_index": triangle.polygon_index,
                "material": slot,
                "vertex_indices": vertices,
                "positions_m": [list(map(float, co)) for co in coords],
                "area_m2": area,
                "repeated_indices": repeated_indices,
                "repeated_positions_1e9m": repeated_positions,
            })
    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "loop_triangles": len(mesh.loop_triangles),
        "polygon_arity": {str(key): value for key, value in sorted(arity.items())},
        "triangles": arity.get(3, 0),
        "quads": arity.get(4, 0),
        "ngons": sum(count for sides, count in arity.items() if sides > 4),
        "minimum_loop_triangle_area_m2": None if minimum_area is math.inf else minimum_area,
        "degenerate_loop_triangles": degenerate,
        "duplicate_position_groups_1e9m": len(duplicate_groups),
        "duplicate_position_vertices_excess_1e9m": sum(len(row["indices"]) - 1 for row in duplicate_groups),
        "duplicate_position_examples_1e9m": duplicate_groups[:20],
    }


def main() -> None:
    if bpy.app.version[:2] != (4, 4) or not bpy.app.background:
        raise RuntimeError(f"Blender 4.4 background required; got {bpy.app.version_string}")
    parsed = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(Path(parsed.fbx).resolve()), use_custom_normals=True)
    meshes = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "MESH"),
        key=lambda obj: obj.name,
    )
    payload = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "headless": bpy.app.background,
        "fbx": str(Path(parsed.fbx).resolve()),
        "meshes": [inspect_mesh(obj) for obj in meshes],
    }
    Path(parsed.out).resolve().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("FLAT_V3_TOPOLOGY_INSPECT_OK " + json.dumps({
        "fbx": payload["fbx"],
        "meshes": [
            {
                "name": row["name"],
                "loop_triangles": row["loop_triangles"],
                "quads": row["quads"],
                "ngons": row["ngons"],
                "degenerate": len(row["degenerate_loop_triangles"]),
                "duplicate_position_excess": row["duplicate_position_vertices_excess_1e9m"],
            }
            for row in payload["meshes"]
        ],
    }), flush=True)


if __name__ == "__main__":
    main()
