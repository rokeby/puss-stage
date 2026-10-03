#!/usr/bin/env python3
"""Rebuild the 63 placed pilot skins into skin_v3 with isotropic peel islands.

Offline and sequential.  ``skin`` and ``skin_v2`` are read-only; FBXs are
fingerprinted before the batch and never opened for writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from argparse import Namespace
from pathlib import Path

import build_skin
import rebuild_pilot_organic_skins as round1
from test_skin_breakup_anisotropy import cluster_edge_anisotropy, field_audit
from test_skin_breakup_fft import summarize as fft_summarize


ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "DerivedAssets" / "FlatV3" / "Review_2026-10-03" / "peel"
SAVED_SWAPKIT = ROOT / "Saved" / "CodexFlatV3" / "swapkit"
PROFILE = "pilot-isotropic"
OUTPUT_DIR = "skin_v3"
TEXTURE_SUFFIX = "_o2"
ANISOTROPY_THRESHOLD = 0.20
FFT_THRESHOLD = 80.0


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def validate_pair(old_manifest_path: Path, new_manifest_path: Path) -> dict:
    checks = round1.validate_pair(old_manifest_path, new_manifest_path)
    new = json.loads(new_manifest_path.read_text(encoding="utf-8"))
    if new["peel"]["profile"] != PROFILE:
        raise RuntimeError(
            f"ROUND2_PROFILE_FAIL|asset={new['asset']}|profile={new['peel']['profile']}"
        )
    mask_path = new_manifest_path.parent / new["textures"]["SkinMask"]["file"]
    anisotropy = cluster_edge_anisotropy(mask_path, new_manifest_path)
    value = anisotropy["orientation_histogram_anisotropy"]
    checks.update({
        "edge_orientation_anisotropy": value,
        "edge_orientation_anisotropy_threshold": ANISOTROPY_THRESHOLD,
        "edge_orientation_anisotropy_pass": value < ANISOTROPY_THRESHOLD,
        "edge_orientation_anisotropy_method": anisotropy["method"],
    })
    if not checks["edge_orientation_anisotropy_pass"]:
        raise RuntimeError(
            "ROUND2_EDGE_ORIENTATION_FAIL|asset=%s|anisotropy=%.9f|threshold=%.9f"
            % (new["asset"], value, ANISOTROPY_THRESHOLD)
        )
    return checks


def write_run_config(inventory: dict) -> Path:
    destinations = {
        "P01": "/Game/Scenes/Wings/FlatV3/Passage01",
        "P02": "/Game/Scenes/Wings/FlatV3/Passage02",
        "P03": "/Game/Scenes/Wings/FlatV3/Passage03",
        "P04": "/Game/Scenes/Wings/FlatV3/Passage04",
        "P05": "/Game/Scenes/Wings/FlatV3/Passage05",
        "P06": "/Game/Scenes/Wings/FlatV3/Passage06",
    }
    rows = []
    for inventory_row in inventory["placed_rows"]:
        if inventory_row["action"] != "rebuild_pilot_organic":
            continue
        owner = inventory_row["owner"]
        old_manifest_path = ROOT / inventory_row["source_manifest"]
        new_manifest_path = old_manifest_path.parent.parent / OUTPUT_DIR / (
            owner + "_skin_manifest.json"
        )
        manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
        sources = {
            kind: str((new_manifest_path.parent / manifest["textures"][kind]["file"]).resolve())
            for kind in ("SkinColor", "SkinMask", "SkinNormal")
        }
        destination = destinations[inventory_row["passage"]]
        old_textures = {
            kind: f"{destination}/Textures/{owner}/T_{owner}_{kind}"
            for kind in ("SkinColor", "SkinMask", "SkinNormal")
        }
        new_textures = {kind: path + TEXTURE_SUFFIX for kind, path in old_textures.items()}
        for slot in ("Front", "Flap"):
            rows.append({
                "passage": inventory_row["passage"],
                "owner": owner,
                "slot": slot,
                "mi": f"{destination}/Materials/Instances/MI_FlatV3_{owner}_{slot}",
                "sources": sources,
                "old_textures": old_textures,
                "new_textures": new_textures,
            })
    rows.sort(key=lambda row: (row["passage"], row["owner"], row["slot"]))
    unique_textures = sorted({path for row in rows for path in row["new_textures"].values()})
    if len(rows) != 136 or len(unique_textures) != 204:
        raise RuntimeError(
            f"SK_CONFIG_COUNT_FAIL|mis={len(rows)}|textures={len(unique_textures)}"
        )
    payload = {
        "schema_version": 1,
        "slot": "SK",
        "status": "AS_IS_OFFLINE_ONLY_NOT_RUN",
        "source_skin_directory": OUTPUT_DIR,
        "texture_name_suffix": TEXTURE_SUFFIX,
        "import_run_id": "FV3SKI-20261003-01",
        "apply_run_id": "FV3SK-20261003-01",
        "revert_run_id": "FV3SKR-20261003-01",
        "workflow": ["import", "apply", "verify"],
        "terminal_stage": "verify",
        "mi_count": len(rows),
        "new_texture_count": len(unique_textures),
        "rows": rows,
    }
    path = SAVED_SWAPKIT / "run_sk.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def canonical_calibration(inventory: dict) -> dict:
    row = next(
        value for value in inventory["placed_rows"]
        if value["owner"] == "P04_coventry_ruin_L_v1"
    )
    old_manifest_path = ROOT / row["source_manifest"]
    round1_manifest_path = old_manifest_path.parent.parent / "skin_v2" / old_manifest_path.name
    round2_manifest_path = old_manifest_path.parent.parent / OUTPUT_DIR / old_manifest_path.name
    manifests = {
        "old_pilot": old_manifest_path,
        "round1_organic": round1_manifest_path,
        "round2_isotropic": round2_manifest_path,
    }
    masks = {}
    for name, manifest_path in manifests.items():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        masks[name] = manifest_path.parent / manifest["textures"]["SkinMask"]["file"]
    tensor = {
        name: cluster_edge_anisotropy(masks[name], manifests[name])
        for name in manifests
    }
    for result in tensor.values():
        result["threshold"] = ANISOTROPY_THRESHOLD
        result["passes"] = bool(
            result["orientation_histogram_anisotropy"] < ANISOTROPY_THRESHOLD
        )
    tensor_passes = bool(
        not tensor["old_pilot"]["passes"]
        and not tensor["round1_organic"]["passes"]
        and tensor["round2_isotropic"]["passes"]
    )
    fft = {
        name: fft_summarize(masks[name], manifests[name], FFT_THRESHOLD)
        for name in manifests
    }
    fft_passes = bool(
        not fft["old_pilot"]["passes"]
        and fft["round1_organic"]["passes"]
        and fft["round2_isotropic"]["passes"]
    )
    report = {
        "schema_version": 1,
        "asset": row["owner"],
        "edge_orientation_anisotropy": tensor,
        "edge_orientation_calibration_passes": tensor_passes,
        "fft": fft,
        "fft_calibration_passes": fft_passes,
        "field_anisotropy": {
            "old_pilot": field_audit(old_manifest_path, "pilot"),
            "round1_organic": field_audit(old_manifest_path, "pilot-organic"),
            "round2_isotropic": field_audit(old_manifest_path, "pilot-isotropic"),
        },
        "passes": bool(tensor_passes and fft_passes),
    }
    path = REVIEW / "anisotropy_calibration.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passes"]:
        raise RuntimeError("ROUND2_CANONICAL_CALIBRATION_FAIL")
    return report


def rebuild(inventory: dict) -> dict:
    selected = [ROOT / value for value in inventory["unique_pilot_manifests"]]
    protected_texture_hashes = {}
    fbx_stats = {}
    for manifest_path in selected:
        for protected_dir in (manifest_path.parent, manifest_path.parent.parent / "skin_v2"):
            for path in protected_dir.glob("*.png"):
                protected_texture_hashes[relative(path)] = digest(path)
        for fbx in manifest_path.parent.parent.glob("*.fbx"):
            stat = fbx.stat()
            fbx_stats[relative(fbx)] = [stat.st_size, stat.st_mtime_ns]

    results = []
    for index, manifest_path in enumerate(selected, 1):
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = manifest_path.parent.parent / OUTPUT_DIR
        new_manifest_path = output / (old["asset"] + "_skin_manifest.json")
        if output.exists():
            if not new_manifest_path.is_file():
                raise RuntimeError(f"REFUSE_PARTIAL_EXISTING_OUTPUT|{output}")
            existing = json.loads(new_manifest_path.read_text(encoding="utf-8"))
            if existing["peel"]["profile"] != PROFILE:
                raise RuntimeError(f"REFUSE_WRONG_PROFILE_EXISTING_OUTPUT|{output}")
        else:
            args = Namespace(
                mask=Path(old["inputs"]["mask"]),
                art=Path(old["inputs"]["art"]),
                older_poster=Path(old["inputs"]["older_poster"]),
                paper_displacement=Path(old["inputs"]["paper_displacement"]),
                paper_roughness=Path(old["inputs"]["paper_roughness"]),
                texture_root=ROOT,
                aged_output=output / "aged_unused",
                stencil_text=old["asset"],
                height_cm=float(old["panel_size_cm"][1]),
                width_cm=float(old["panel_size_cm"][0]),
                color_width=int(old["textures"]["SkinColor"]["size_px"][0]),
                color_height=int(old["textures"]["SkinColor"]["size_px"][1]),
                asset_name=old["asset"],
                output=output,
                diagnostics_output=None,
                seed=int(old["deterministic_seed"]),
                peel_percent=float(old["peel"]["target_percent"]),
                peel_profile=PROFILE,
                substrate_profile=old["front_colour"]["substrate_profile"],
                texture_suffix=TEXTURE_SUFFIX,
                skip_aged_textures=True,
            )
            build_skin.build(args)
        checks = validate_pair(manifest_path, new_manifest_path)
        results.append({
            "asset": old["asset"],
            "old_manifest": relative(manifest_path),
            "round1_manifest": relative(manifest_path.parent.parent / "skin_v2" / manifest_path.name),
            "round2_manifest": relative(new_manifest_path),
            "checks": checks,
        })
        print(f"[{index:02d}/{len(selected):02d}] {old['asset']} PASS")

    protected_unchanged = all(
        digest(ROOT / path) == value for path, value in protected_texture_hashes.items()
    )
    fbx_unchanged = all(
        [(ROOT / path).stat().st_size, (ROOT / path).stat().st_mtime_ns] == signature
        for path, signature in fbx_stats.items()
    )
    required = (
        "same_resolution",
        "same_input_art_and_silhouette_hashes",
        "skincolor_alpha_byte_identical",
        "skincolor_outside_130cm_cluster_unions_byte_identical",
        "cluster_centres_identical",
        "peel_within_half_percent",
        "fft_pass",
        "edge_orientation_anisotropy_pass",
    )
    report = {
        "schema_version": 1,
        "status": "PASS" if protected_unchanged and fbx_unchanged else "FAIL",
        "execution": {
            "offline": True,
            "unreal": False,
            "mcp": False,
            "port_8010": False,
            "gpu_work_performed": False,
            "job_concurrency": 1,
        },
        "source_skin_count": len(selected),
        "output_directory": OUTPUT_DIR,
        "skin_and_skin_v2_textures_unchanged_sha256": protected_unchanged,
        "fbx_size_and_mtime_unchanged": fbx_unchanged,
        "verification_summary": {
            "all_required_checks_pass": all(
                result["checks"][key] for result in results for key in required
            ),
            "checked_skin_count": len(results),
            "max_peel_percent_error": max(
                result["checks"]["peel_percent_error"] for result in results
            ),
            "max_edge_orientation_anisotropy": max(
                result["checks"]["edge_orientation_anisotropy"] for result in results
            ),
            "edge_orientation_anisotropy_threshold": ANISOTROPY_THRESHOLD,
            "checks": list(required),
        },
        "results": results,
    }
    if report["status"] != "PASS" or not report["verification_summary"]["all_required_checks_pass"]:
        raise RuntimeError("ROUND2_BATCH_FINAL_INTEGRITY_FAIL")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = round1.build_inventory()
    if args.inventory_only:
        print(json.dumps({
            "placed_rows": inventory["placed_row_count"],
            "pilot_manifests": inventory["unique_pilot_manifest_count"],
        }))
        return 0
    report = rebuild(inventory)
    calibration = canonical_calibration(inventory)
    config_path = write_run_config(inventory)
    report["canonical_calibration"] = {
        "path": relative(REVIEW / "anisotropy_calibration.json"),
        "passes": calibration["passes"],
    }
    report["run_config"] = relative(config_path)
    report_path = REVIEW / "isotropic_skin_batch_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "rebuilt": report["source_skin_count"],
        "max_edge_orientation_anisotropy": report["verification_summary"]["max_edge_orientation_anisotropy"],
        "gpu_work_performed": False,
        "run_config": relative(config_path),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
