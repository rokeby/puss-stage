"""Pure-Python Flat V3 socket sidecar contract.

This module deliberately has no Blender or Unreal dependency.  It is used by
the offline re-emitter and regression test so the JSON-to-Unreal conversion can
be checked while the editor is unavailable.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable


ROTATION_ORDER = "roll-pitch-yaw"
SOCKET_SCHEMA_VERSION = 1
SOCKET_CONTRACT = {
    "ue_rotator_order": ROTATION_ORDER,
    "hinge_local_x_axis": "base-edge Y; either sign is the same hinge line",
    "pivot_local_x_axis": "+Z",
    "fbx_interchange_y_reflected": True,
}


def as_float_list(values: Iterable[float]) -> list[float]:
    return [float(value) for value in values]


def as_pole_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        return as_float_list(value)
    return [float(value)]


def make_socket_payload(
    *,
    asset: str,
    side: str,
    mount: str,
    height_cm: float,
    width_m: float,
    pole_positions_y_m: Iterable[float],
) -> dict[str, Any]:
    """Build the Unreal-local sidecar from builder-manifest declarations.

    Blender/FBX Y is reflected by UE Interchange.  Rotations are named fields,
    and Unreal Python constructs Rotator with roll, pitch, yaw keywords.
    """
    if side not in {"L", "R"}:
        raise ValueError(f"Unsupported side: {side!r}")
    if mount not in {"wing", "wave-row", "top-border"}:
        raise ValueError(f"Unsupported mount: {mount!r}")

    records: list[dict[str, Any]] = []
    if mount == "wing":
        records = [
            {
                "name": "SOCKET_Hinge",
                "relative_location_cm": [0.0, 0.0, 0.0],
                "relative_rotation_deg": {"roll": 0.0, "pitch": 0.0, "yaw": -90.0},
            },
            {
                "name": "SOCKET_Pivot",
                "relative_location_cm": [
                    0.0,
                    float(width_m) * 50.0 * (1.0 if side == "L" else -1.0),
                    float(height_cm) * 0.5,
                ],
                "relative_rotation_deg": {"roll": 0.0, "pitch": 90.0, "yaw": 0.0},
            },
        ]
        records.extend(
            {
                "name": f"SOCKET_Pole_{index}",
                "relative_location_cm": [0.0, -float(y_m) * 100.0, 0.0],
                "relative_rotation_deg": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            }
            for index, y_m in enumerate(pole_positions_y_m, start=1)
        )

    return {
        "schema_version": SOCKET_SCHEMA_VERSION,
        "asset": asset,
        "coordinate_space": "Unreal static-mesh local",
        "location_units": "cm",
        "rotation_units": "degrees",
        "rotation_order": ROTATION_ORDER,
        "fbx_interchange_conversion": "X=X, Y=-Y, Z=Z",
        "contract": dict(SOCKET_CONTRACT),
        "sockets": records,
    }


def ue_forward_vector(rotation: dict[str, float]) -> list[float]:
    """Simulate Unreal MathLibrary.get_forward_vector(FRotator).

    Roll does not change local +X.  Unreal's forward-vector convention is
    X=cos(pitch)cos(yaw), Y=cos(pitch)sin(yaw), Z=sin(pitch).
    """
    pitch = math.radians(float(rotation["pitch"]))
    yaw = math.radians(float(rotation["yaw"]))
    cos_pitch = math.cos(pitch)
    return [cos_pitch * math.cos(yaw), cos_pitch * math.sin(yaw), math.sin(pitch)]


def _close(actual: Iterable[float], expected: Iterable[float], tolerance: float = 1e-3) -> bool:
    return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected))


def validate_socket_payload(
    payload: dict[str, Any], expected: dict[str, Any], *, require_metadata: bool = True
) -> list[str]:
    """Return every sidecar contract failure; an empty list is PASS."""
    failures: list[str] = []
    for key in (
        "schema_version", "asset", "coordinate_space", "location_units",
        "rotation_units", "fbx_interchange_conversion",
    ):
        if payload.get(key) != expected.get(key):
            failures.append(f"HEADER_{key.upper()}_FAIL")
    if require_metadata:
        if payload.get("rotation_order") != ROTATION_ORDER:
            failures.append("ROTATION_ORDER_FAIL")
        if payload.get("contract") != SOCKET_CONTRACT:
            failures.append("SOCKET_CONTRACT_METADATA_FAIL")

    actual_rows = payload.get("sockets")
    expected_rows = expected.get("sockets")
    if not isinstance(actual_rows, list):
        return failures + ["SOCKET_ROWS_FAIL"]
    actual_by_name = {str(row.get("name")): row for row in actual_rows}
    expected_by_name = {str(row.get("name")): row for row in expected_rows}
    if sorted(actual_by_name) != sorted(expected_by_name):
        failures.append("SOCKET_JSON_NAMES_FAIL")
        return failures

    for name, expected_row in expected_by_name.items():
        row = actual_by_name[name]
        location = row.get("relative_location_cm")
        rotation = row.get("relative_rotation_deg")
        if not isinstance(location, list) or len(location) != 3:
            failures.append(f"{name}:LOCATION_RECORD_FAIL")
            continue
        if not isinstance(rotation, dict) or sorted(rotation) != ["pitch", "roll", "yaw"]:
            failures.append(f"{name}:ROTATION_RECORD_FAIL")
            continue
        if not _close(location, expected_row["relative_location_cm"]):
            failures.append(f"{name}:LOCATION_FAIL")
        if not _close(
            [rotation[axis] for axis in ("roll", "pitch", "yaw")],
            [expected_row["relative_rotation_deg"][axis] for axis in ("roll", "pitch", "yaw")],
        ):
            failures.append(f"{name}:ROTATION_FAIL")

        axis = ue_forward_vector(rotation)
        if name == "SOCKET_Hinge" and (
            max(abs(float(value)) for value in location) > 1e-6 or abs(axis[1]) < 0.999999
        ):
            failures.append("HINGE_SOCKET_FAIL")
        if name == "SOCKET_Pivot" and axis[2] < 0.999999:
            failures.append("PIVOT_SOCKET_AXIS_FAIL")

    return failures


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_slot_a_rows(project: Path) -> list[dict[str, Any]]:
    """Recreate the 35-row Slot A source inventory without Unreal."""
    roots = [
        (project / "DerivedAssets/FlatV3/Overnight/flats", {"P04", "P05"}),
        (project / "DerivedAssets/FlatV3/Overnight/Kept/flats", {"P01", "P05"}),
    ]
    rows: list[dict[str, Any]] = []
    for root, passages in roots:
        if not root.is_dir():
            continue
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            status_path = folder / "status.json"
            if not status_path.is_file():
                continue
            status = load_json(status_path)
            passage = str(status.get("passage"))
            if (status.get("status") != "built" or passage not in passages or
                    folder.name.startswith("S3_")):
                continue
            manifest_path = Path(status["build_manifest"])
            if not manifest_path.is_file():
                matches = sorted(folder.glob("*_build.json"))
                if len(matches) != 1:
                    raise RuntimeError(f"Cannot resolve build manifest for {folder}")
                manifest_path = matches[0]
            manifest = load_json(manifest_path)
            asset = str(status["asset_name"])
            sidecar_path = folder / f"sockets_{asset}.json"
            expected = make_socket_payload(
                asset=asset,
                side=str(status["build_side"]),
                mount=str(status["mount"]),
                height_cm=float(status["height_cm"]),
                width_m=float(manifest["dimensions_m"]["width"]),
                pole_positions_y_m=as_pole_list(manifest.get("pole_positions_y_m")),
            )
            rows.append({
                "asset": str(status["asset_suffix"]),
                "mesh_name": asset,
                "passage": passage,
                "folder": folder,
                "status": status,
                "manifest": manifest,
                "manifest_path": manifest_path,
                "sidecar_path": sidecar_path,
                "expected": expected,
            })
    return rows
