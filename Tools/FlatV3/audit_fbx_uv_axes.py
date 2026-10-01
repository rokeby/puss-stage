"""Measure FBX UV-axis slopes after a clean Blender 4.4 read-back.

The audit works on distinct (mesh vertex, UV) samples so triangle tessellation
does not weight the least-squares fit.  It is intentionally import-only and is
safe to run offline against production and legacy FBXs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np


def args_after_double_dash() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fbx", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(raw)


def require_blender_44() -> None:
    if bpy.app.version[:2] != (4, 4):
        raise RuntimeError(f"Blender 4.4 required; got {bpy.app.version_string}")
    if not bpy.app.background:
        raise RuntimeError("UV audit must run headless (--background)")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def fit(samples: list[tuple[float, float]]) -> dict[str, float | int | None]:
    values = np.asarray(samples, dtype=np.float64)
    if len(values) < 2 or float(np.ptp(values[:, 0])) <= 1.0e-12:
        return {"samples": len(values), "slope_per_m": None, "slope_per_cm": None, "intercept": None, "r_squared": None}
    design = np.column_stack((values[:, 0], np.ones(len(values))))
    slope, intercept = np.linalg.lstsq(design, values[:, 1], rcond=None)[0]
    predicted = design @ np.asarray((slope, intercept))
    residual = float(np.sum((values[:, 1] - predicted) ** 2))
    total = float(np.sum((values[:, 1] - values[:, 1].mean()) ** 2))
    r_squared = 1.0 if total <= 1.0e-24 and residual <= 1.0e-24 else (1.0 - residual / total if total > 0.0 else 0.0)
    return {
        "samples": len(values),
        "slope_per_m": float(slope),
        "slope_per_cm": float(slope) / 100.0,
        "intercept": float(intercept),
        "r_squared": float(r_squared),
    }


def object_record(obj: bpy.types.Object) -> dict[str, object]:
    mesh = obj.data
    uv = mesh.uv_layers.get("UV0") or (mesh.uv_layers[0] if mesh.uv_layers else None)
    slots = [slot.material.name if slot.material else None for slot in obj.material_slots]
    record: dict[str, object] = {
        "object": obj.name,
        "slots": slots,
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "sections": {},
    }
    if uv is None:
        return record

    by_section: dict[str, set[tuple[int, float, float, float, float]]] = {}
    for polygon in mesh.polygons:
        section = slots[polygon.material_index] if 0 <= polygon.material_index < len(slots) else f"slot_{polygon.material_index}"
        for loop_index in polygon.loop_indices:
            loop = mesh.loops[loop_index]
            co = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
            u, v = uv.data[loop_index].uv
            by_section.setdefault(str(section), set()).add(
                (loop.vertex_index, round(float(co.y), 9), round(float(co.z), 9), round(float(u), 9), round(float(v), 9))
            )

    for section, unique in sorted(by_section.items()):
        samples = sorted(unique)
        u_y = [(sample[1], sample[3]) for sample in samples]
        v_z = [(sample[2], sample[4]) for sample in samples]
        record["sections"][section] = {
            "distinct_vertex_uv_samples": len(samples),
            "du_dY": fit(u_y),
            "dv_dZ": fit(v_z),
            "ranges": {
                "Y_m": [min(sample[1] for sample in samples), max(sample[1] for sample in samples)],
                "Z_m": [min(sample[2] for sample in samples), max(sample[2] for sample in samples)],
                "U": [min(sample[3] for sample in samples), max(sample[3] for sample in samples)],
                "V": [min(sample[4] for sample in samples), max(sample[4] for sample in samples)],
            },
        }
    return record


def audit(path: Path) -> dict[str, object]:
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(path.resolve()), use_custom_normals=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    return {
        "fbx": str(path.resolve()),
        "objects": [object_record(obj) for obj in sorted(meshes, key=lambda item: item.name)],
    }


def main() -> None:
    require_blender_44()
    args = args_after_double_dash()
    result = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "factory_startup_process": True,
        "method": "least squares over distinct (mesh vertex, UV0) samples after Blender FBX import",
        "files": [audit(path) for path in args.fbx],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"FLAT_V3_UV_AXIS_AUDIT_OK|files={len(result['files'])}|output={args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
