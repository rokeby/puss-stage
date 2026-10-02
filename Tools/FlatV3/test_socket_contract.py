"""Offline Slot A regression: JSON -> Unreal Rotator simulation -> spec gate."""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from socket_contract import (
    as_pole_list,
    discover_slot_a_rows,
    load_json,
    make_socket_payload,
    make_wing_payload_from_fbx_records,
    validate_socket_payload,
    validate_wing_geometry,
)


PROJECT = Path(__file__).resolve().parents[2]
FAILURE_JSON = PROJECT / "Saved/CodexFlatV3/slot_a_import_FV3A-20261002-01_FAILURE.json"
P02_EMISSION_REPORT = PROJECT / "Saved/CodexFlatV3/offline_harness/p02_socket_emission_report.json"
OLD_SET01 = PROJECT / "Saved/CodexFlatV3/offline_harness/old_sockets_SM_FlatV3_P02_SET01_C.json"


def legacy_pilot_gate(payload: dict) -> str | None:
    """The two pilot-only assumptions that rejected the batch."""
    by_name = {row["name"]: row for row in payload.get("sockets", [])}
    if not by_name:
        return None
    required = {"SOCKET_Hinge", "SOCKET_Pivot", "SOCKET_Pole_1", "SOCKET_Pole_2"}
    if set(by_name) != required:
        return "SOCKET_JSON_NAMES_FAIL"
    if abs(float(by_name["SOCKET_Pivot"]["relative_location_cm"][2]) - 500.0) > 1.0:
        return "PIVOT_SOCKET_FAIL"
    return None


def observed_failure_counts() -> dict[str, int]:
    payload = load_json(FAILURE_JSON)
    counter = collections.Counter(
        str(item["error"]).split("|", 1)[0] for item in payload.get("failures", [])
    )
    return dict(sorted(counter.items()))


def observed_primary_reasons() -> dict[str, str]:
    payload = load_json(FAILURE_JSON)
    return {
        str(item["owner"]): str(item["error"]).split("|", 1)[0]
        for item in payload.get("failures", [])
    }


def triangle_tolerance_rows() -> list[dict]:
    payload = load_json(FAILURE_JSON)
    rows = []
    pattern = re.compile(r"actual=(\d+)\|expected=(\d+)")
    for failure in payload.get("failures", []):
        if not str(failure.get("error", "")).startswith("TRIANGLE_COUNT_FAIL|"):
            continue
        match = pattern.search(failure["error"])
        if not match:
            raise RuntimeError(f"Cannot parse triangle failure: {failure['error']}")
        actual, expected = map(int, match.groups())
        rows.append({
            "asset": failure["owner"], "actual": actual, "expected": expected,
            "delta": actual - expected, "pass_with_interchange_tolerance": abs(actual - expected) <= 1,
        })
    return rows


def pilot_reference_results() -> list[dict]:
    pilot = PROJECT / "DerivedAssets/FlatV3/Pilot"
    results = []
    for manifest_path in sorted(pilot.glob("P02_RuisdaelA_*_build.json")):
        manifest = load_json(manifest_path)
        asset = "SM_FlatV3_" + manifest_path.stem.removesuffix("_build")
        sidecar_path = pilot / f"sockets_{asset}.json"
        expected = make_socket_payload(
            asset=asset,
            side=str(manifest["side"]),
            mount=str(manifest.get("mount", "wing")),
            height_cm=float(manifest["inputs"]["height_cm"]),
            width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=as_pole_list(manifest.get("pole_positions_y_m")),
        )
        failures = validate_socket_payload(
            load_json(sidecar_path), expected, require_metadata=False
        )
        results.append({
            "asset": asset, "path": str(sidecar_path),
            "semantic_failures": failures,
        })
    return results


def _manifest(folder: Path, status: dict) -> dict:
    path = Path(str(status.get("build_manifest", "")))
    if not path.is_file():
        matches = sorted(folder.glob("*_build.json"))
        if len(matches) != 1:
            raise RuntimeError(f"Cannot resolve build manifest for {folder}")
        path = matches[0]
    return load_json(path)


def p02_import_results() -> tuple[list[dict], dict]:
    """Validate every sidecar admitted by the current P02 import inventory."""
    root = PROJECT / "DerivedAssets/FlatV3/Overnight"
    results = []
    flats = root / "P02Sets/flats"
    for folder in sorted(path for path in flats.iterdir() if path.is_dir()):
        status_path = folder / "status.json"
        validation_path = folder / "validation.json"
        if not status_path.is_file() or not validation_path.is_file():
            continue
        status = load_json(status_path)
        validation = load_json(validation_path)
        if status.get("passage") != "P02" or not validation.get("pass"):
            continue
        manifest = _manifest(folder, status)
        expected = make_socket_payload(
            asset=str(status["asset_name"]),
            side=str(status["build_side"]),
            mount=str(status["mount"]),
            height_cm=float(status["height_cm"]),
            width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=as_pole_list(manifest.get("pole_positions_y_m")),
        )
        sidecar = folder / ("sockets_" + str(status["asset_name"]) + ".json")
        failures = validate_socket_payload(
            load_json(sidecar), expected, require_metadata=True)
        results.append({
            "kind": "plant", "asset": status["asset_name"],
            "sidecar": str(sidecar), "failures": failures,
        })

    emission = load_json(P02_EMISSION_REPORT)
    for item in emission["industrial"]:
        expected = make_wing_payload_from_fbx_records(
            asset=str(item["asset"]), side=str(item["side"]),
            height_cm=1200.0, records=item["source_records"])
        sidecar = Path(item["sidecar"])
        actual = load_json(sidecar)
        failures = validate_socket_payload(actual, expected, require_metadata=True)
        failures.extend(validate_wing_geometry(
            actual, side=str(item["side"]), height_cm=1200.0,
            bounds_cm=item["geometry_bounds_cm"],
        ))
        results.append({
            "kind": "industrial", "asset": item["asset"],
            "sidecar": str(sidecar), "failures": failures,
            "source_findings": item["source_findings"],
        })

    set01_status = load_json(flats / "P02_SET01_C/status.json")
    set01_manifest = _manifest(flats / "P02_SET01_C", set01_status)
    set01_expected = make_socket_payload(
        asset=str(set01_status["asset_name"]),
        side=str(set01_status["build_side"]),
        mount=str(set01_status["mount"]),
        height_cm=float(set01_status["height_cm"]),
        width_m=float(set01_manifest["dimensions_m"]["width"]),
        pole_positions_y_m=as_pole_list(set01_manifest.get("pole_positions_y_m")),
    )
    negative_failures = validate_socket_payload(
        load_json(OLD_SET01), set01_expected, require_metadata=True)
    negative = {
        "fixture": str(OLD_SET01),
        "expected_status": "FAIL",
        "failures": negative_failures,
        "passed_negative_control": negative_failures == [
            "ROTATION_ORDER_FAIL", "SOCKET_CONTRACT_METADATA_FAIL"],
    }
    return results, negative


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    rows = discover_slot_a_rows(PROJECT)
    if len(rows) != 35:
        raise RuntimeError(f"Slot A inventory changed: expected 35 built flats, found {len(rows)}")

    results = []
    legacy_counts: collections.Counter[str] = collections.Counter()
    reproduced_primary_counts: collections.Counter[str] = collections.Counter()
    primary_reasons = observed_primary_reasons()
    semantic_failures = 0
    metadata_failures = 0
    for row in rows:
        actual = load_json(row["sidecar_path"])
        failures = validate_socket_payload(actual, row["expected"], require_metadata=True)
        semantic = validate_socket_payload(actual, row["expected"], require_metadata=False)
        legacy = legacy_pilot_gate(actual)
        if legacy:
            legacy_counts[legacy] += 1
        reproduced_primary = (
            "TRIANGLE_COUNT_FAIL"
            if primary_reasons.get(row["asset"]) == "TRIANGLE_COUNT_FAIL"
            else legacy
        )
        if reproduced_primary:
            reproduced_primary_counts[reproduced_primary] += 1
        semantic_failures += bool(semantic)
        metadata_failures += bool(failures)
        results.append({
            "asset": row["asset"], "passage": row["passage"],
            "socket_names": [item["name"] for item in actual.get("sockets", [])],
            "legacy_pilot_gate": legacy or "PASS",
            "reproduced_original_primary_gate": reproduced_primary or "PASS",
            "spec_semantic_failures": semantic,
            "full_contract_failures": failures,
        })

    triangles = triangle_tolerance_rows()
    pilot_results = pilot_reference_results()
    pilot_failures = sum(bool(row["semantic_failures"]) for row in pilot_results)
    observed = observed_failure_counts()
    legacy_match = dict(sorted(reproduced_primary_counts.items())) == observed
    triangle_failures = sum(not row["pass_with_interchange_tolerance"] for row in triangles)
    p02_results, p02_negative = p02_import_results()
    p02_failures = sum(bool(row["failures"]) for row in p02_results)
    passed = (not metadata_failures and not semantic_failures and not triangle_failures and
              not pilot_failures and legacy_match and not p02_failures and
              p02_negative["passed_negative_control"])
    report = {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "scope": "all 35 Slot A flats; no Unreal and no mesh rebuild",
        "simulated_unreal_rotation_order": "roll-pitch-yaw",
        "asset_count": len(rows),
        "full_contract_failure_count": metadata_failures,
        "semantic_failure_count": semantic_failures,
        "legacy_pilot_gate_failure_counts": dict(sorted(legacy_counts.items())),
        "reproduced_original_primary_failure_counts": dict(sorted(reproduced_primary_counts.items())),
        "reproduced_original_failure_counts_match": legacy_match,
        "observed_failure_counts": observed,
        "triangle_tolerance": {
            "rule": "abs(UE source-model triangles - Blender FBX validation triangles) <= 1",
            "failure_count": triangle_failures,
            "items": triangles,
        },
        "pilot_hand_derived_reference": {
            "asset_count": len(pilot_results),
            "semantic_failure_count": pilot_failures,
            "items": pilot_results,
        },
        "p02_import_sidecars": {
            "scope": "every plant and industrial sidecar admitted by run_p02.json",
            "require_metadata": True,
            "asset_count": len(p02_results),
            "failure_count": p02_failures,
            "negative_control": p02_negative,
            "items": p02_results,
        },
        "items": results,
    }
    if args.report:
        report_path = args.report if args.report.is_absolute() else PROJECT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "assets": len(rows),
        "full_contract_failures": metadata_failures,
        "semantic_failures": semantic_failures,
        "legacy_pilot_gate_failures": dict(sorted(legacy_counts.items())),
        "triangle_tolerance_failures": triangle_failures,
        "pilot_reference_failures": pilot_failures,
        "p02_import_sidecars": len(p02_results),
        "p02_import_failures": p02_failures,
        "p02_old_set01_negative_control": p02_negative["passed_negative_control"],
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
