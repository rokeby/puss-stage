"""Build and gate the sixteen P05 measured-pole Flat V3 variants offline.

This orchestrator never imports into Unreal.  Each production ``_poles2`` FBX
is paired with a current-code, 100 cm baseline control so the measured pole
change can be proved topology-only outside the baked poles.  The geometry
harness also proves the superseded 460 cm length fails at the measured maximum
P05 body bottom and the replacement length passes all 186 formula heights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from socket_contract import make_socket_payload, validate_socket_payload


PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT / "DerivedAssets/FlatV3/Overnight/Kept/flats"
OUTPUT_ROOT = PROJECT / "DerivedAssets/FlatV3/P05Poles2"
BUILDER = PROJECT / "Tools/FlatV3/build_v3_flat.py"
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe")
EXPECTED_ASSET_COUNT = 16
EXPECTED_PANEL_COUNT = 186
TARGET_SUFFIX = "_poles2"
BASELINE_EXTENSION_CM = 100.0
SUPERSEDED_EXTENSION_CM = 460.0
ORIGINAL_POLE_TIP_CM = 100.0
FLOOR_Z_CM = 0.0
POLE_FLOOR_TOLERANCE_CM = 1.0
POLE_CLEARANCE_CM = 10.0
POLE_EXTENSION_CM = 556.0
FLOAT_DRY_ARTIFACT = (
    PROJECT / "Saved/CodexFlatV3/swapkit/p05float_dry_run_FV3F-20261002-01.json"
)
SKIPPED_IDENTITY = (124, "1ED83B530F4AEEB89EB6DE8F21BD20F9", "right")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_inventory(folder: Path) -> dict[str, str]:
    return {
        str(path.relative_to(folder)).replace("\\", "/"): sha256(path)
        for path in sorted(folder.rglob("*.png"))
    }


def p05_height_harness() -> dict:
    """Prove the chosen length against the immutable Slot F height evidence."""
    artifact = load_json(FLOAT_DRY_ARTIFACT)
    if (artifact.get("status") != "PASS" or artifact.get("row_count") != 93 or
            artifact.get("panel_count") != EXPECTED_PANEL_COUNT or
            artifact.get("formula") != "H = 150 + 300 * u cm"):
        raise RuntimeError(f"P05_HEIGHT_ARTIFACT_FAIL|path={FLOAT_DRY_ARTIFACT}")

    panels = []
    for row in artifact.get("rows", []):
        for side in ("left", "right"):
            value = row["sides"][side]
            hash_input = str(row["cue_guid"]) + side
            digest = hashlib.sha256(hash_input.encode("utf-8")).digest()
            u = int.from_bytes(digest[:8], byteorder="big", signed=False) / float(2 ** 64)
            height = 150.0 + 300.0 * u
            if (abs(float(value["u"]) - u) > 1e-15 or
                    abs(float(value["target_world_bottom_cm"]) - height) > 1e-9):
                raise RuntimeError(
                    "P05_HEIGHT_FORMULA_DRIFT|identity=%s:%s:%s" %
                    (row["cue_index"], row["cue_guid"], side))
            panels.append({
                "cue_index": int(row["cue_index"]),
                "cue_guid": str(row["cue_guid"]),
                "cue_label": str(row["cue_label"]),
                "side": side,
                "u": u,
                "slot_f_world_min_cm": height,
                "panel_body_world_bottom_cm": height + ORIGINAL_POLE_TIP_CM,
                "source_mesh": str(value["mesh"]),
            })
    if len(panels) != EXPECTED_PANEL_COUNT:
        raise RuntimeError(
            f"P05_HEIGHT_PANEL_COUNT_FAIL|expected={EXPECTED_PANEL_COUNT}|actual={len(panels)}")

    active = [
        row for row in panels
        if (row["cue_index"], row["cue_guid"], row["side"]) != SKIPPED_IDENTITY
    ]
    if len(active) != EXPECTED_PANEL_COUNT - 1:
        raise RuntimeError(f"P05_HEIGHT_ACTIVE_COUNT_FAIL|actual={len(active)}")
    maximum = max(active, key=lambda row: row["panel_body_world_bottom_cm"])
    required_extension = math.ceil(maximum["panel_body_world_bottom_cm"] + POLE_CLEARANCE_CM)
    if required_extension != int(POLE_EXTENSION_CM):
        raise RuntimeError(
            f"P05_POLE_LENGTH_RULE_FAIL|required={required_extension}|configured={POLE_EXTENSION_CM:g}")

    superseded_bottom = maximum["panel_body_world_bottom_cm"] - SUPERSEDED_EXTENSION_CM
    superseded_fails = superseded_bottom > FLOOR_Z_CM + POLE_FLOOR_TOLERANCE_CM
    replacement_failures = [
        "%s:%s:%s" % (row["cue_index"], row["cue_guid"], row["side"])
        for row in panels
        if row["panel_body_world_bottom_cm"] - POLE_EXTENSION_CM >
        FLOOR_Z_CM + POLE_FLOOR_TOLERANCE_CM
    ]
    if not superseded_fails or replacement_failures:
        raise RuntimeError(
            "P05_POLE_GEOMETRY_HARNESS_FAIL|superseded_fails=%s|replacement_failures=%s" %
            (superseded_fails, json.dumps(replacement_failures)))

    superseded_failure_count = sum(
        row["panel_body_world_bottom_cm"] - SUPERSEDED_EXTENSION_CM >
        FLOOR_Z_CM + POLE_FLOOR_TOLERANCE_CM for row in panels)
    return {
        "status": "PASS",
        "evidence": str(FLOAT_DRY_ARTIFACT),
        "formula": artifact["formula"] + " + 100 cm original baked pole tip",
        "panel_count": len(panels),
        "active_panel_count": len(active),
        "skipped_identity": {
            "cue_index": SKIPPED_IDENTITY[0],
            "cue_guid": SKIPPED_IDENTITY[1],
            "side": SKIPPED_IDENTITY[2],
        },
        "maximum_active_panel_body_world_bottom": maximum,
        "clearance_rule_cm": POLE_CLEARANCE_CM,
        "required_extension_cm": required_extension,
        "negative_control": {
            "extension_cm": SUPERSEDED_EXTENSION_CM,
            "status": "EXPECTED_FAIL",
            "maximum_pole_world_bottom_cm": superseded_bottom,
            "failure_count": superseded_failure_count,
            "gate": "pole_world_bottom_cm <= floor_z_cm + 1 cm",
        },
        "positive_control": {
            "extension_cm": POLE_EXTENSION_CM,
            "status": "PASS",
            "panel_count": len(panels),
            "failure_count": len(replacement_failures),
            "maximum_pole_world_bottom_cm": max(
                row["panel_body_world_bottom_cm"] - POLE_EXTENSION_CM for row in panels),
            "gate": "pole_world_bottom_cm <= floor_z_cm + 1 cm",
        },
    }


def source_rows() -> list[dict]:
    rows = []
    for folder in sorted(SOURCE_ROOT.glob("P05_*")):
        status_path = folder / "status.json"
        if not status_path.is_file():
            continue
        status = load_json(status_path)
        if status.get("passage") != "P05" or status.get("status") != "built":
            continue
        manifests = sorted(folder.glob("*_build.json"))
        if len(manifests) != 1:
            raise RuntimeError(f"SOURCE_MANIFEST_COUNT_FAIL|folder={folder}|actual={len(manifests)}")
        manifest = load_json(manifests[0])
        asset = str(status["asset_name"])
        owner = str(status["asset_suffix"])
        if not asset.startswith("SM_FlatV3_P05_CloudRef") or asset.endswith("_poles"):
            raise RuntimeError(f"SOURCE_ASSET_NAME_FAIL|asset={asset}")
        rows.append({
            "folder": folder,
            "status": status,
            "manifest": manifest,
            "asset": asset,
            "owner": owner,
            "side": str(status["build_side"]),
            "height_cm": float(status["height_cm"]),
            "png_before": png_inventory(folder),
        })
    if len(rows) != EXPECTED_ASSET_COUNT:
        raise RuntimeError(f"SOURCE_COUNT_FAIL|expected={EXPECTED_ASSET_COUNT}|actual={len(rows)}")
    return rows


def run(command: list[str], log_path: Path) -> None:
    completed = subprocess.run(command, cwd=PROJECT, text=True, capture_output=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" +
        completed.stdout + "\nSTDERR\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"BLENDER_FAIL|code={completed.returncode}|log={log_path}")


def build_variant(blender: Path, row: dict, *, suffix: str, extension_cm: float,
                  output_dir: Path, log_dir: Path) -> tuple[Path, Path, Path]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"NEW_OUTPUT_REQUIRED|refusing_overwrite={output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = row["manifest"]["inputs"]
    owner = row["owner"] + suffix
    asset = row["asset"] + suffix
    build_command = [
        str(blender), "--background", "--factory-startup", "--python", str(BUILDER), "--",
        "--mask", str(inputs["mask"]), "--art", str(inputs["art"]),
        "--skin-mask", str(inputs["skin_mask"]), "--skin-normal", str(inputs["skin_normal"]),
        "--flaps", str(inputs["flaps"]), "--aged-texture-dir", str(row["folder"] / "aged"),
        "--height-cm", str(row["height_cm"]), "--side", row["side"],
        "--name", owner, "--asset-name", asset.removeprefix("SM_FlatV3_"),
        "--mount", "wing", "--output-dir", str(output_dir),
        "--texture-root", str(row["folder"] / "skin"), "--bake-poles",
        "--pole-extension-cm", str(extension_cm), "--triangulate-export",
    ]
    run(build_command, log_dir / f"{owner}_build.log")
    fbx = output_dir / f"{asset}.fbx"
    manifests = sorted(output_dir.glob("*_build.json"))
    if len(manifests) != 1 or not fbx.is_file():
        raise RuntimeError(f"BUILD_OUTPUT_FAIL|owner={owner}|manifests={len(manifests)}|fbx={fbx.is_file()}")
    validation = output_dir / "validation.json"
    validation_command = [
        str(blender), "--background", "--factory-startup", "--python", str(BUILDER), "--",
        "--validate-fbx", str(fbx), "--kind", "flat", "--skin-color", str(inputs["art"]),
        "--expected-height-cm", str(row["height_cm"]), "--validation-out", str(validation),
    ]
    run(validation_command, log_dir / f"{owner}_validate.log")
    return fbx, manifests[0], validation


def gate_pair(row: dict, baseline: tuple[Path, Path, Path], poles: tuple[Path, Path, Path]) -> dict:
    baseline_fbx, baseline_manifest_path, baseline_validation_path = baseline
    poles_fbx, poles_manifest_path, poles_validation_path = poles
    base_manifest = load_json(baseline_manifest_path)
    new_manifest = load_json(poles_manifest_path)
    base_validation = load_json(baseline_validation_path)
    new_validation = load_json(poles_validation_path)
    failures = []
    control_failures = []

    for label, validation in (("baseline", base_validation), ("poles", new_validation)):
        if not validation.get("pass"):
            failures.append(f"{label}:VALIDATION_FAIL")
            if label == "baseline":
                control_failures.append("VALIDATION_FAIL")
        triangulated = validation.get("checks", {}).get("triangulated_export", {})
        if not triangulated.get("pass") or not triangulated.get("enabled"):
            failures.append(f"{label}:TRIANGULATED_EXPORT_FAIL")
            if label == "baseline":
                control_failures.append("TRIANGULATED_EXPORT_FAIL")
        lod = validation.get("checks", {}).get("fbx_lod_group", {})
        if not lod.get("pass") or lod.get("mechanism") != "FBX LodGroup NodeAttribute":
            failures.append(f"{label}:LOD_GROUP_FAIL")
            if label == "baseline":
                control_failures.append("LOD_GROUP_FAIL")

    if base_manifest.get("art_panel_geometry_contract") != new_manifest.get("art_panel_geometry_contract"):
        failures.append("ART_PANEL_GEOMETRY_OR_UV_CHANGED")
    if base_validation.get("triangle_counts") != new_validation.get("triangle_counts"):
        failures.append("DETERMINISTIC_TRIANGLE_COUNTS_CHANGED")

    baked = new_manifest.get("baked_poles", {})
    if (abs(float(baked.get("extension_below_panel_cm", -1)) - POLE_EXTENSION_CM) > 1e-6 or
            abs(float(baked.get("bottom_z_m", 1)) + POLE_EXTENSION_CM / 100.0) > 1e-6):
        failures.append("POLE_EXTENSION_MANIFEST_FAIL")
    for record in baked.get("records", []):
        if abs(float(record.get("bottom_z_m", 1)) + POLE_EXTENSION_CM / 100.0) > 0.002:
            failures.append("POLE_RECORD_BOTTOM_FAIL")

    asset = row["asset"] + TARGET_SUFFIX
    sidecar_path = poles_fbx.parent / f"sockets_{asset}.json"
    if not sidecar_path.is_file():
        failures.append("SOCKET_SIDECAR_MISSING")
        socket_failures = ["SOCKET_SIDECAR_MISSING"]
        sidecar = {}
    else:
        sidecar = load_json(sidecar_path)
        expected_socket = make_socket_payload(
            asset=asset, side=row["side"], mount="wing", height_cm=row["height_cm"],
            width_m=float(new_manifest["dimensions_m"]["width"]),
            pole_positions_y_m=new_manifest["pole_positions_y_m"],
            pole_extension_cm=POLE_EXTENSION_CM,
        )
        socket_failures = validate_socket_payload(sidecar, expected_socket)
        if socket_failures:
            failures.extend("SOCKET:" + value for value in socket_failures)
        if sidecar.get("baked_pole_geometry") != expected_socket.get("baked_pole_geometry"):
            failures.append("SOCKET_POLE_GEOMETRY_METADATA_FAIL")

    if row["png_before"] != png_inventory(row["folder"]):
        failures.append("SOURCE_PNG_CHANGED_DURING_BUILD")
    for key in ("mask", "art", "skin_mask", "skin_normal", "flaps"):
        if base_manifest["inputs"][key] != new_manifest["inputs"][key]:
            failures.append(f"INPUT_PATH_CHANGED:{key}")

    return {
        "asset": asset,
        "source_asset": row["asset"],
        "pass": not failures,
        "failures": failures,
        "control_validation_pass": not control_failures,
        "control_failures": control_failures,
        "pole_extension_cm": POLE_EXTENSION_CM,
        "fbx": str(poles_fbx),
        "fbx_sha256": sha256(poles_fbx),
        "baseline_fbx": str(baseline_fbx),
        "baseline_fbx_sha256": sha256(baseline_fbx),
        "validation": str(poles_validation_path),
        "triangle_counts": new_validation.get("triangle_counts"),
        "art_panel_geometry_contract": new_manifest.get("art_panel_geometry_contract"),
        "source_png_sha256": row["png_before"],
        "socket_sidecar": str(sidecar_path),
        "socket_failures": socket_failures,
    }


def write_status(row: dict, result: dict, poles_manifest: Path, poles_validation: Path) -> Path:
    folder = Path(result["fbx"]).parent
    status = {
        "schema_version": 1,
        "status": "built" if result["pass"] else "failed",
        "passage": "P05",
        "asset_name": result["asset"],
        "asset_suffix": row["owner"] + TARGET_SUFFIX,
        "source_asset_name": row["asset"],
        "source_folder": str(row["folder"]),
        "height_cm": row["height_cm"],
        "source_side": row["side"],
        "build_side": row["side"],
        "mount": "wing",
        "kind": "flat",
        "baked_poles": True,
        "pole_extension_cm": POLE_EXTENSION_CM,
        "triangulate_export": True,
        "fbx": result["fbx"],
        "build_manifest": str(poles_manifest),
        "validation": str(poles_validation),
        "validation_pass": bool(result["pass"]),
        "socket_sidecar": result["socket_sidecar"],
        "panel_geometry_proof": result["art_panel_geometry_contract"],
    }
    path = folder / "status.json"
    write_json(path, status)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    args = parser.parse_args()
    blender = args.blender.resolve()
    if not blender.is_file():
        raise RuntimeError(f"BLENDER_4_4_MISSING|path={blender}")
    if OUTPUT_ROOT.exists() and any(OUTPUT_ROOT.iterdir()):
        raise RuntimeError(f"NEW_OUTPUT_ROOT_REQUIRED|refusing_overwrite={OUTPUT_ROOT}")

    rows = source_rows()
    height_harness = p05_height_harness()
    results = []
    for row in rows:
        owner = row["owner"]
        baseline_dir = OUTPUT_ROOT / "controls" / (owner + "_baseline_control")
        poles_dir = OUTPUT_ROOT / "flats" / (owner + TARGET_SUFFIX)
        logs = OUTPUT_ROOT / "logs"
        baseline = build_variant(
            blender, row, suffix="_baseline_control", extension_cm=BASELINE_EXTENSION_CM,
            output_dir=baseline_dir, log_dir=logs,
        )
        poles = build_variant(
            blender, row, suffix=TARGET_SUFFIX, extension_cm=POLE_EXTENSION_CM,
            output_dir=poles_dir, log_dir=logs,
        )
        result = gate_pair(row, baseline, poles)
        write_status(row, result, poles[1], poles[2])
        results.append(result)
        print(f"P05_POLES_ASSET {'PASS' if result['pass'] else 'FAIL'} {result['asset']}", flush=True)
        if not result["pass"]:
            raise RuntimeError("P05_POLES_GATE_FAIL|" + json.dumps(result["failures"]))

    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "baked long poles",
        "target_suffix": TARGET_SUFFIX,
        "pole_extension_cm": POLE_EXTENSION_CM,
        "height_harness": height_harness,
        "asset_count": len(results),
        "control_count": len(results),
        "all_controls_pass": (
            len(results) == EXPECTED_ASSET_COUNT and
            all(row["control_validation_pass"] for row in results)
        ),
        "socket_contract_validation": {
            "asset_count": len(results),
            "all_pass": all(not row["socket_failures"] for row in results),
        },
        "all_pass": len(results) == EXPECTED_ASSET_COUNT and all(row["pass"] for row in results),
        "assets": results,
    }
    write_json(OUTPUT_ROOT / "P05_POLES_BUILD_REPORT.json", report)
    print(f"P05_POLES2_BUILD_OK assets={len(results)} controls={len(results)} "
          f"extension_cm={POLE_EXTENSION_CM:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
