"""Re-emit only the P02 import socket sidecars from build data and FBX empties.

Run with Blender 4.4 in background mode.  This never opens Unreal and never
rewrites an FBX, blend, manifest, validation file, Show asset or level.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from socket_contract import (
    as_pole_list,
    load_json,
    make_socket_payload,
    make_wing_payload_from_fbx_records,
    validate_socket_payload,
    validate_wing_geometry,
)


PROJECT = Path(__file__).resolve().parents[2]
PLANT_ROOT = PROJECT / "DerivedAssets/FlatV3/Overnight/P02Sets/flats"
INDUSTRIAL_ROOT = PROJECT / "DerivedAssets/FlatV3/Overnight/P02Industrial"
SET01 = PLANT_ROOT / "P02_SET01_C"
SET04 = PLANT_ROOT / "P02_SET04_C"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def source_scan(fbx: Path) -> tuple[list[dict], dict[str, float]]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(fbx), use_custom_props=True, automatic_bone_orientation=False)
    records = []
    for obj in sorted(bpy.context.scene.objects, key=lambda value: value.name):
        if obj.type == "EMPTY" and obj.name.startswith("SOCKET_"):
            records.append({
                "name": obj.name,
                "location_m": [round(float(value), 6) for value in obj.matrix_world.translation],
            })
    mesh_points = [
        obj.matrix_world @ vertex.co
        for obj in bpy.context.scene.objects if obj.type == "MESH"
        for vertex in obj.data.vertices
    ]
    if not mesh_points:
        raise RuntimeError(f"No mesh geometry in {fbx}")
    blender_bounds = {
        "y_min": min(float(point.y) for point in mesh_points),
        "y_max": max(float(point.y) for point in mesh_points),
        "z_min": min(float(point.z) for point in mesh_points),
        "z_max": max(float(point.z) for point in mesh_points),
    }
    ue_bounds_cm = {
        "y_min": -blender_bounds["y_max"] * 100.0,
        "y_max": -blender_bounds["y_min"] * 100.0,
        "z_min": blender_bounds["z_min"] * 100.0,
        "z_max": blender_bounds["z_max"] * 100.0,
    }
    return records, ue_bounds_cm


def source_contract_findings(records: list[dict], *, height_cm: float) -> dict:
    by_name = {record["name"]: record for record in records}
    poles = sorted(
        (record for record in records if record["name"].startswith("SOCKET_Pole_")),
        key=lambda record: int(record["name"].rsplit("_", 1)[1]),
    )
    allowed = {"SOCKET_Hinge", "SOCKET_Pivot"} | {record["name"] for record in poles}
    extras = sorted(set(by_name) - allowed)
    failures = []
    if "SOCKET_Hinge" not in by_name or "SOCKET_Pivot" not in by_name or not poles:
        failures.append("SOURCE_REQUIRED_WING_NAMES_FAIL")
        return {"failures": failures, "excluded_non_wing_sockets": extras}
    hinge = by_name["SOCKET_Hinge"]["location_m"]
    if max(abs(float(value)) for value in hinge) > 0.002:
        failures.append("SOURCE_HINGE_BASE_EDGE_FAIL")
    for pole in poles:
        x, _, z = pole["location_m"]
        if abs(float(x)) > 0.002 or abs(float(z)) > 0.002:
            failures.append(pole["name"] + ":SOURCE_POLE_LINE_FAIL")
    pole_y = [float(record["location_m"][1]) for record in poles]
    pivot = by_name["SOCKET_Pivot"]["location_m"]
    expected_pivot = [0.0, (min(pole_y) + max(pole_y)) * 0.5, height_cm / 200.0]
    if any(abs(float(a) - float(b)) > 0.002 for a, b in zip(pivot, expected_pivot)):
        failures.append("SOURCE_PIVOT_GEOMETRY_MIDPOINT_FAIL")
    return {
        "failures": failures,
        "excluded_non_wing_sockets": extras,
        "source_pivot_m": pivot,
        "contract_pivot_m": expected_pivot,
    }


def emit_set01(dry_run: bool) -> dict:
    status = load_json(SET01 / "status.json")
    manifest_path = Path(status["build_manifest"])
    if not manifest_path.is_file():
        matches = sorted(SET01.glob("*_build.json"))
        if len(matches) != 1:
            raise RuntimeError("Cannot resolve SET01_C build manifest")
        manifest_path = matches[0]
    manifest = load_json(manifest_path)
    payload = make_socket_payload(
        asset=str(status["asset_name"]),
        side=str(status["build_side"]),
        mount=str(status["mount"]),
        height_cm=float(status["height_cm"]),
        width_m=float(manifest["dimensions_m"]["width"]),
        pole_positions_y_m=as_pole_list(manifest.get("pole_positions_y_m")),
    )
    path = SET01 / ("sockets_" + str(status["asset_name"]) + ".json")
    before = path.read_bytes()
    after = encoded(payload)
    if not dry_run:
        write_atomic(path, after)

    set04 = load_json(SET04 / "sockets_SM_FlatV3_P02_SET04_C.json")
    comparable = dict(payload)
    comparable["asset"] = set04["asset"]
    return {
        "asset": status["asset_name"],
        "path": str(path),
        "changed": before != after,
        "before_sha256": digest(before),
        "after_sha256": digest(after),
        "socket_count": len(payload["sockets"]),
        "contract_failures": validate_socket_payload(payload, payload, require_metadata=True),
        "matches_set04_structure": comparable == set04,
    }


def emit_industrial(dry_run: bool) -> list[dict]:
    manifest = load_json(INDUSTRIAL_ROOT / "manifest.json")
    height_cm = float(manifest["target_height_cm"])
    items = []
    for item in sorted(manifest["assets"], key=lambda value: value["asset"]):
        asset = str(item["asset"])
        side = str(item["side"])
        fbx = INDUSTRIAL_ROOT / str(item["fbx"])
        records, bounds_cm = source_scan(fbx)
        payload = make_wing_payload_from_fbx_records(
            asset=asset, side=side, height_cm=height_cm, records=records)
        expected_width_m = float(item["dimensions_m"]["width"])
        pole_y = [
            float(record["location_m"][1]) for record in records
            if record["name"].startswith("SOCKET_Pole_")
        ]
        source_width_m = max(pole_y) - min(pole_y)
        geometry_failures = validate_wing_geometry(
            payload, side=side, height_cm=height_cm, bounds_cm=bounds_cm)
        if abs(source_width_m - expected_width_m) > 0.002:
            geometry_failures.append("SOURCE_POLE_SPAN_VS_MANIFEST_FAIL")
        contract_failures = validate_socket_payload(payload, payload, require_metadata=True)
        if contract_failures or geometry_failures:
            raise RuntimeError(json.dumps({
                "asset": asset,
                "contract_failures": contract_failures,
                "geometry_failures": geometry_failures,
            }, sort_keys=True))
        path = INDUSTRIAL_ROOT / ("sockets_" + asset + ".json")
        before = path.read_bytes()
        after = encoded(payload)
        if not dry_run:
            write_atomic(path, after)
        items.append({
            "asset": asset,
            "side": side,
            "fbx": str(fbx),
            "sidecar": str(path),
            "changed": before != after,
            "before_sha256": digest(before),
            "after_sha256": digest(after),
            "source_records": records,
            "geometry_bounds_cm": bounds_cm,
            "source_findings": source_contract_findings(records, height_cm=height_cm),
            "emitted_socket_names": [record["name"] for record in payload["sockets"]],
            "contract_failures": contract_failures,
            "geometry_failures": geometry_failures,
        })
    if len(items) != 8:
        raise RuntimeError(f"P02 industrial inventory changed: expected 8, found {len(items)}")
    return items


def main() -> int:
    args = parse_args()
    set01 = emit_set01(args.dry_run)
    industrial = emit_industrial(args.dry_run)
    report = {
        "schema_version": 1,
        "mode": "dry-run" if args.dry_run else "write",
        "unreal_used": False,
        "mesh_files_touched": 0,
        "set01": set01,
        "industrial_count": len(industrial),
        "industrial_changed": sum(bool(item["changed"]) for item in industrial),
        "source_contract_failure_assets": [
            item["asset"] for item in industrial if item["source_findings"]["failures"]
        ],
        "source_extra_socket_assets": [
            item["asset"] for item in industrial
            if item["source_findings"]["excluded_non_wing_sockets"]
        ],
        "industrial": industrial,
    }
    report_path = args.report if args.report.is_absolute() else PROJECT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mode": report["mode"],
        "set01_changed": set01["changed"],
        "set01_matches_set04_structure": set01["matches_set04_structure"],
        "industrial_count": report["industrial_count"],
        "industrial_changed": report["industrial_changed"],
        "source_contract_failure_assets": report["source_contract_failure_assets"],
        "source_extra_socket_assets": report["source_extra_socket_assets"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
