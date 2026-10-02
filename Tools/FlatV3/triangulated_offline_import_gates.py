"""Independent Blender 4.4 import gates for targeted triangulated Flat V3 FBXs.

This is adapted from p02_offline_import_gates.py but intentionally scoped to
the seven image flats rebuilt for cross-importer triangle determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy


PROJECT = Path(__file__).resolve().parents[2]
P06 = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "P06"
REBUILD = P06 / "TRIANGULATION_REBUILD.json"
RESULT = P06 / "TRIANGULATION_OFFLINE_GATES.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def factory_import(path: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    empties = [obj for obj in bpy.context.scene.objects if obj.type == "EMPTY"]
    lod0 = next((obj for obj in meshes if "_LOD0" in obj.name), None)
    lod1 = next((obj for obj in meshes if "_LOD1" in obj.name), None)
    groups = [obj for obj in empties if obj.name.endswith("_LODGroup")]
    return {"lod0": lod0, "lod1": lod1, "groups": groups, "meshes": meshes}


def topology(obj) -> dict:
    obj.data.calc_loop_triangles()
    arity: dict[str, int] = {}
    zero_area = []
    for polygon in obj.data.polygons:
        key = str(len(polygon.vertices))
        arity[key] = arity.get(key, 0) + 1
        if polygon.area <= 1.0e-12:
            zero_area.append(polygon.index)
    return {
        "polygons": len(obj.data.polygons),
        "loop_triangles": len(obj.data.loop_triangles),
        "polygon_arity": arity,
        "zero_area_polygon_indices": zero_area,
        "triangle_only": bool(obj.data.polygons)
            and all(len(polygon.vertices) == 3 for polygon in obj.data.polygons)
            and not zero_area
            and len(obj.data.polygons) == len(obj.data.loop_triangles),
    }


def slots(obj) -> list[str | None]:
    return [slot.material.name if slot.material else None for slot in obj.material_slots]


def validate_row(row: dict) -> dict:
    folder = Path(row["folder"])
    asset = row["asset"]
    imported = factory_import(folder / f"{asset}.fbx")
    lod0, lod1 = imported["lod0"], imported["lod1"]
    checks = {}
    checks["LOD"] = {
        "pass": bool(lod0 and lod1 and len(imported["groups"]) == 1
                     and lod0.parent == imported["groups"][0] and lod1.parent == imported["groups"][0]),
        "groups": [obj.name for obj in imported["groups"]],
        "meshes": [obj.name for obj in imported["meshes"]],
    }
    if not lod0 or not lod1:
        return {"asset": asset, "checks": checks, "pass": False}
    top0, top1 = topology(lod0), topology(lod1)
    expected = row["after"]["triangle_counts"]
    build_path = next(folder.glob("*_build.json"))
    build = read_json(build_path)
    checks["TRI"] = {
        "pass": top0["triangle_only"] and top1["triangle_only"],
        "lod0": top0, "lod1": top1,
    }
    checks["COUNT"] = {
        "pass": (
            top0["loop_triangles"] == int(expected["lod0"]) == int(build["triangle_counts"]["flat_total"])
            and top1["loop_triangles"] == int(expected["lod1"]) == int(build["triangle_counts"]["lod1_total"])
        ),
        "imported": [top0["loop_triangles"], top1["loop_triangles"]],
        "validation": [expected["lod0"], expected["lod1"]],
        "builder": [build["triangle_counts"]["flat_total"], build["triangle_counts"]["lod1_total"]],
    }
    expected_slots = ["Front", "Flap", "Timber", "Edge"]
    checks["SLOTS"] = {
        "pass": slots(lod0) == expected_slots and slots(lod1) == expected_slots,
        "lod0": slots(lod0), "lod1": slots(lod1),
    }
    checks["UVSET"] = {
        "pass": ([layer.name for layer in lod0.data.uv_layers] == ["UV0", "UV1"]
                 and [layer.name for layer in lod1.data.uv_layers] == ["UV0", "UV1"]),
        "lod0": [layer.name for layer in lod0.data.uv_layers],
        "lod1": [layer.name for layer in lod1.data.uv_layers],
    }
    checks["UVCONTRACT"] = {
        "pass": bool(row["unchanged"]["uv_contract_pass"]),
        "uv0_registration_max_error": row["unchanged"]["uv0_registration_max_error"],
        "uv1_lod0_max_error_m": row["unchanged"]["uv1_lod0_max_error_m"],
        "uv1_lod1_max_error_m": row["unchanged"]["uv1_lod1_max_error_m"],
    }
    checks["ART"] = {
        "pass": bool(row["unchanged"]["pixel_sha256_exact"]),
        "pixel_file_count": row["unchanged"]["pixel_file_count"],
        "front_raster_texel_delta": row["unchanged"]["front_raster_texel_delta"],
    }
    checks["SOCKETS"] = {"pass": bool(row["unchanged"]["socket_payload_exact"])}
    checks["BOUNDS"] = {
        "pass": (float(row["unchanged"]["bounds_max_abs_delta_m"]) <= 1.0e-5
                 and float(row["unchanged"]["dimensions_max_abs_delta_m"]) <= 1.0e-5),
        "bounds_max_abs_delta_m": row["unchanged"]["bounds_max_abs_delta_m"],
        "dimensions_max_abs_delta_m": row["unchanged"]["dimensions_max_abs_delta_m"],
    }
    checks["VALIDATION"] = {"pass": bool(row["after"]["validation_pass"])}
    return {"asset": asset, "checks": checks, "pass": all(value["pass"] for value in checks.values())}


def main() -> None:
    if bpy.app.version[:2] != (4, 4) or not bpy.app.background:
        raise RuntimeError(f"Blender 4.4 background required; got {bpy.app.version_string}")
    rebuild = read_json(REBUILD)
    production = [validate_row(row) for row in rebuild["assets"]]
    bronze = next(row for row in rebuild["assets"] if row["asset"] == "SM_FlatV3_P06_bronze_tree_R_v1")
    old_fbx = Path(bronze["baseline"]) / f"{bronze['asset']}.fbx"
    old = factory_import(old_fbx)
    old_topology = {key: topology(old[key]) for key in ("lod0", "lod1")}
    negative_rejected = not all(value["triangle_only"] for value in old_topology.values())
    payload = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "headless": bpy.app.background,
        "offline_only": True,
        "production": production,
        "production_passed": sum(row["pass"] for row in production),
        "production_count": len(production),
        "negative_control": {
            "asset": bronze["asset"],
            "fbx": str(old_fbx),
            "expected": "reject legacy quads/n-gons/zero-area topology",
            "rejected": negative_rejected,
            "topology": old_topology,
        },
        "acceptance_boundary": (
            "Proves factory-clean Blender FBX import, fixed triangle topology, count equality, and recorded "
            "offline contracts. Actual UE 5.8 Interchange output remains untested offline."
        ),
    }
    payload["all_pass"] = payload["production_passed"] == payload["production_count"] and negative_rejected
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        "FLAT_V3_TRIANGULATED_OFFLINE_GATES|production=%d/%d|negative_rejected=%s"
        % (payload["production_passed"], payload["production_count"], negative_rejected),
        flush=True,
    )
    if not payload["all_pass"]:
        raise RuntimeError(f"Offline import gate failure; inspect {RESULT}")


if __name__ == "__main__":
    main()
