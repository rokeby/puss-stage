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
    validate_socket_payload,
)


PROJECT = Path(__file__).resolve().parents[2]
FAILURE_JSON = PROJECT / "Saved/CodexFlatV3/slot_a_import_FV3A-20261002-01_FAILURE.json"


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
    passed = (not metadata_failures and not semantic_failures and not triangle_failures and
              not pilot_failures and legacy_match)
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
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
