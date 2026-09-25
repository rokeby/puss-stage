#!/usr/bin/env python3
"""Factory-clean validate the current Passage 2 V2 Wing FBX batch."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[2]
BLENDER = Path("/Applications/Blender v5-2.app/Contents/MacOS/Blender")
VALIDATOR = PROJECT / "Tools/WingCutoutPipeline/validate_fbx.py"
OUTPUT_ROOT = PROJECT / "DerivedAssets/Passage01V2Batch/GeneratedWings"
REPORT_PATH = PROJECT / "DerivedAssets/Passage01V2Batch/fbx_clean_reimport_validation.json"
EXPECTED_ROLES = ("L", "R", "T")


def main() -> int:
    fbxs = sorted(OUTPUT_ROOT.glob("P01_SET*/SM_P01_SET*.fbx"))
    expected_names = {
        f"SM_P01_SET{set_number:02d}_{role}.fbx"
        for set_number in range(1, 21)
        for role in EXPECTED_ROLES
    }
    actual_names = {path.name for path in fbxs}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise RuntimeError(f"FBX inventory mismatch missing={missing} unexpected={unexpected}")

    results = []
    failures = []
    for index, fbx in enumerate(fbxs, start=1):
        command = [
            str(BLENDER),
            "--background",
            "--factory-startup",
            "--python",
            str(VALIDATOR),
            "--",
            "--fbx",
            str(fbx),
            "--height-m",
            "2.0",
            "--panel-scale",
            "5.0",
            "--thickness-m",
            "0.10",
            "--thickness-axis",
            "x",
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        marker_lines = [
            line for line in completed.stdout.splitlines()
            if line.startswith("WING_FBX_VALIDATION ")
        ]
        if len(marker_lines) != 1:
            result = {
                "fbx": str(fbx),
                "status": "error",
                "errors": ["Missing or duplicate WING_FBX_VALIDATION marker"],
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        else:
            result = json.loads(marker_lines[0].split(" ", 1)[1])
            extra_errors = []
            uv_maps = result.get("uv_maps", [])
            if len(uv_maps) != 1 or uv_maps[0].get("name") != "UVMap":
                extra_errors.append(f"Expected exactly one UVMap, got {uv_maps}")
            materials = result.get("materials", [])
            asset_name = fbx.stem.removeprefix("SM_")
            expected_materials = [
                f"M_{asset_name}_Front",
                f"M_{asset_name}_Back",
                f"M_{asset_name}_Edge",
            ]
            if materials != expected_materials:
                extra_errors.append(
                    f"Expected material slots {expected_materials}, got {materials}"
                )
            if result.get("vertices", 0) <= 0 or result.get("polygons", 0) <= 0:
                extra_errors.append("Geometry is empty")
            if completed.returncode != 0:
                extra_errors.append(f"Validator return code {completed.returncode}")
            if extra_errors:
                result.setdefault("errors", []).extend(extra_errors)
                result["status"] = "error"
        result["sequence"] = index
        results.append(result)
        if result.get("status") != "ok":
            failures.append(fbx.name)
        print(
            "P02_V2_FBX_VALIDATED"
            f"|{index:02d}/60|{fbx.name}|status={result.get('status')}"
        )

    report = {
        "profile": "PussStage Wing V2",
        "validator": str(VALIDATOR),
        "factory_startup_per_fbx": True,
        "expected_count": 60,
        "validated_count": len(results),
        "failed_count": len(failures),
        "failures": failures,
        "status": "ok" if not failures else "error",
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "P02_V2_FBX_VALIDATION_BATCH_"
        f"{'SUCCESS' if not failures else 'FAILED'}"
        f"|count={len(results)}|failed={len(failures)}|report={REPORT_PATH}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
