#!/usr/bin/env python3
"""CPU-only targeted rebuild of the seven cross-importer Flat V3 outliers."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[2]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe")
BUILDER = PROJECT / "Tools" / "FlatV3" / "build_v3_flat.py"
INSPECTOR = PROJECT / "Tools" / "FlatV3" / "inspect_fbx_topology.py"
TEXTURE_ROOT = PROJECT / "DerivedAssets" / "TextureLibrary"
P06 = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "P06"
BASELINE = P06 / "triangulation_baseline"
LOGS = P06 / "triangulation_logs"
REPORT = P06 / "TRIANGULATION_REBUILD.json"
GPU_MARKER = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "RUNNING.json"
TARGETS = [
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_bronze_tree_L_v2",
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_bronze_tree_R_v1",
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_chinoiserie_garden_L_v1",
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_chinoiserie_garden_R_v1",
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_grand_pavilion_L_v1",
    PROJECT / "DerivedAssets/FlatV3/Overnight/P06/flats/P06_grand_pavilion_R_v1",
    PROJECT / "DerivedAssets/FlatV3/Overnight/Kept/flats/P05_CloudRef02_L_L",
]


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hashes(folder: Path, pattern: str) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): sha256(path)
        for path in sorted(folder.rglob(pattern))
    }


def run(command: list[str], log: Path) -> None:
    completed = subprocess.run(
        command, cwd=PROJECT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + completed.stdout
        + "\nSTDERR\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}); inspect {log}")


def maximum_numeric_delta(left: Any, right: Any) -> float:
    if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
        return max((maximum_numeric_delta(left[key], right[key]) for key in left), default=0.0)
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return max((maximum_numeric_delta(a, b) for a, b in zip(left, right)), default=0.0)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right))
    return 0.0 if left == right else float("inf")


def main() -> None:
    if not BLENDER.is_file():
        raise FileNotFoundError(BLENDER)
    BASELINE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    gpu_marker = read_json(GPU_MARKER) if GPU_MARKER.is_file() else {"status": "absent"}
    rows = []
    for folder in TARGETS:
        build_path = next(folder.glob("*_build.json"))
        build_before = read_json(build_path)
        validation_path = folder / "validation.json"
        validation_before = read_json(validation_path)
        fbx = Path(build_before["outputs"]["flat_fbx"])
        socket = Path(build_before["outputs"]["socket_json"])
        blend = Path(build_before["outputs"]["blend"])
        asset = fbx.stem
        recovery = BASELINE / asset
        recovery.mkdir(exist_ok=True)
        for source in (fbx, socket, blend, build_path, validation_path):
            destination = recovery / source.name
            if not destination.exists():
                shutil.copy2(source, destination)
        pixel_hashes_before = hashes(folder, "*.png")
        socket_before = read_json(socket)
        before_topology = recovery / "topology_before.json"
        run([
            str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(INSPECTOR), "--", "--fbx", str(recovery / fbx.name),
            "--out", str(before_topology),
        ], LOGS / f"{asset}_inspect_before.log")

        inputs = build_before["inputs"]
        command = [
            str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(BUILDER), "--",
            "--mask", str(inputs["mask"]), "--art", str(inputs["art"]),
            "--skin-mask", str(inputs["skin_mask"]), "--skin-normal", str(inputs["skin_normal"]),
            "--flaps", str(inputs["flaps"]), "--aged-texture-dir", str(folder / "aged"),
            "--height-cm", str(inputs["height_cm"]), "--side", str(build_before["side"]),
            "--name", str(build_before["name"]), "--asset-name", asset.removeprefix("SM_FlatV3_"),
            "--mount", str(build_before.get("mount", "wing")), "--output-dir", str(folder),
            "--texture-root", str(TEXTURE_ROOT), "--skip-pole-export", "--triangulate-export",
        ]
        if bool(build_before.get("baked_poles", {}).get("enabled")):
            command.append("--bake-poles")
        run(command, LOGS / f"{asset}_build.log")

        build_after = read_json(build_path)
        skin_color = Path(build_after["inputs"]["art"])
        run([
            str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(BUILDER), "--", "--validate-fbx", str(fbx),
            "--skin-color", str(skin_color), "--kind", "flat",
            "--validation-out", str(validation_path),
            "--expected-height-cm", str(inputs["height_cm"]),
        ], LOGS / f"{asset}_validate.log")
        validation_after = read_json(validation_path)
        after_topology = folder / "topology_after.json"
        run([
            str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(INSPECTOR), "--", "--fbx", str(fbx), "--out", str(after_topology),
        ], LOGS / f"{asset}_inspect_after.log")

        pixels_after = hashes(folder, "*.png")
        sockets_after = read_json(socket)
        old_uv = validation_before["checks"]
        new_uv = validation_after["checks"]
        uv_contract_pass = all(new_uv[key]["pass"] for key in (
            "uv0_uv1", "uv1_metres_all_slots", "front_flap_uv0_registration",
            "front_flap_uv0_axis_contract", "lod1_uv0_uv1", "lod1_uv1_metres_all_slots",
        ))
        rows.append({
            "asset": asset,
            "folder": str(folder),
            "baseline": str(recovery),
            "before": {
                "triangle_counts": validation_before["triangle_counts"],
                "bounds_m": validation_before["bounds_m"],
                "dimensions_m": validation_before["dimensions_m"],
                "topology": read_json(before_topology),
            },
            "after": {
                "triangle_counts": validation_after["triangle_counts"],
                "bounds_m": validation_after["bounds_m"],
                "dimensions_m": validation_after["dimensions_m"],
                "topology": read_json(after_topology),
                "validation_pass": validation_after["pass"],
                "triangulated_export": validation_after["checks"]["triangulated_export"],
            },
            "unchanged": {
                "pixel_file_count": len(pixel_hashes_before),
                "pixel_sha256_exact": pixel_hashes_before == pixels_after,
                "socket_payload_exact": socket_before == sockets_after,
                "material_slots_exact": validation_before["checks"]["material_slots_exact"]["value"]
                    == validation_after["checks"]["material_slots_exact"]["value"],
                "bounds_max_abs_delta_m": maximum_numeric_delta(
                    validation_before["bounds_m"], validation_after["bounds_m"]),
                "dimensions_max_abs_delta_m": maximum_numeric_delta(
                    validation_before["dimensions_m"], validation_after["dimensions_m"]),
                "front_raster_texel_delta": int(
                    new_uv["front_skincolor_background_coverage"]["front_texels"]
                    - old_uv["front_skincolor_background_coverage"]["front_texels"]),
                "uv_contract_pass": uv_contract_pass,
                "uv0_registration_max_error": new_uv["front_flap_uv0_registration"]["maximum_error"],
                "uv1_lod0_max_error_m": new_uv["uv1_metres_all_slots"]["maximum_error_m"],
                "uv1_lod1_max_error_m": new_uv["lod1_uv1_metres_all_slots"]["maximum_error_m"],
            },
        })
        write_json(REPORT, {
            "schema_version": 1, "started": started, "updated": now(),
            "offline_only": True, "unreal_used": False, "mcp_used": False, "port_8010_used": False,
            "gpu": {"workload": "CPU-only geometry build/import validation; no render/upscale/segmentation", "marker": gpu_marker},
            "assets": rows,
        })
    payload = read_json(REPORT)
    payload["finished"] = now()
    payload["all_pass"] = all(
        row["after"]["validation_pass"]
        and row["unchanged"]["pixel_sha256_exact"]
        and row["unchanged"]["socket_payload_exact"]
        and row["unchanged"]["material_slots_exact"]
        and row["unchanged"]["bounds_max_abs_delta_m"] <= 1.0e-5
        and row["unchanged"]["uv_contract_pass"]
        for row in rows
    )
    write_json(REPORT, payload)
    print(f"FLAT_V3_TRIANGULATION_REBUILD_{'PASS' if payload['all_pass'] else 'FAIL'} assets={len(rows)}")
    if not payload["all_pass"]:
        raise RuntimeError(f"Targeted rebuild comparison failed; inspect {REPORT}")


if __name__ == "__main__":
    started = now()
    main()
