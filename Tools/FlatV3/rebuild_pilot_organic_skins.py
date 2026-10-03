#!/usr/bin/env python3
"""Inventory placed Flat V3 assets and rebuild only pilot skins as pilot-organic.

This is an offline, sequential CPU job. It never imports Unreal, touches Content,
opens a network connection, or writes an FBX. Existing skins are read-only; every
new texture is written beneath that flat's new ``skin_v2`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from argparse import Namespace
from pathlib import Path

import cv2
import numpy as np

import build_skin
from test_skin_breakup_fft import summarize as fft_summarize


ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "DerivedAssets" / "FlatV3"
OVERNIGHT = DERIVED / "Overnight"
SAVED = ROOT / "Saved" / "CodexFlatV3"
REVIEW = DERIVED / "Review_2026-10-03" / "peel"
FFT_OLD_PILOT_FRACTION = 0.95


def read_json(relative: str | Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def owner_from_mesh(mesh: str) -> str:
    name = str(mesh).rsplit("/", 1)[-1]
    if name.startswith("SM_FlatV3_"):
        return name[len("SM_FlatV3_"):]
    raise RuntimeError(f"NOT_FLAT_V3_MESH|{mesh}")


def placed_assets() -> tuple[dict[str, set[str]], list[dict], list[str]]:
    evidence = [
        "Saved/CodexFlatV3/swapkit/swapkit_apply_FV3D-20261002-03.json",
        "Saved/CodexFlatV3/swapkit/swapkit_apply_FV3P02-20261002-02.json",
        "Saved/CodexFlatV3/swapkit/swapkit_apply_FV3P03-20261002-01.json",
        "Saved/CodexFlatV3/slot_b_apply_FV3B-20261002-03.json",
        "Saved/CodexFlatV3/swapkit/swapkit_apply_FV3C-20261002-03.json",
        "Saved/CodexFlatV3/swapkit/c3_apply_FV3C3-20261002-01.json",
        "Saved/CodexFlatV3/swapkit/swapkit_apply_FV3P06-20261002-01.json",
    ]
    for item in evidence:
        payload = read_json(item)
        if payload.get("status") != "PASS":
            raise RuntimeError(f"PLACEMENT_ARTIFACT_NOT_PASS|{item}")

    kept = read_json("DerivedAssets/FlatV3/Overnight/Kept/KEPT_MAP.json")
    p01_run = read_json("Saved/CodexFlatV3/swapkit/run_d_p01.json")
    p01_excluded = set(p01_run["excluded_new_meshes"])
    passages: dict[str, set[str]] = {
        "P01": {entry["new_mesh"] for entry in kept["entries"]
                if entry["passage"] == "P01" and entry["new_mesh"] not in p01_excluded},
    }

    p02 = read_json("DerivedAssets/FlatV3/Overnight/P02_LAYOUT_DRAFT_v2.json")
    p02_meshes = set()
    for occurrence in p02["occurrences"]:
        for side in ("left", "right", "top"):
            mesh = occurrence["proposal"].get(side, {}).get("asset")
            if mesh:
                p02_meshes.add(mesh)
    passages["P02"] = p02_meshes

    p03 = read_json("DerivedAssets/FlatV3/Overnight/P03_LAYOUT_DRAFT.json")
    passages["P03"] = {row["asset"] for row in p03["family_catalog"].values()}

    p04 = read_json("Saved/CodexFlatV3/swapkit/mapping_b_p04.json")
    passages["P04"] = {path.rsplit("/", 1)[-1]
                         for path in p04["left_pool"] + p04["right_pool"]}

    p05_meshes = {entry["new_mesh"] for entry in kept["entries"] if entry["passage"] == "P05"}
    c3 = read_json("Saved/CodexFlatV3/swapkit/run_c3.json")
    p05_meshes.add(c3["asset_name"])
    passages["P05"] = p05_meshes

    p06 = read_json("Saved/CodexFlatV3/swapkit/p06_layout.json")
    p06_meshes = set()
    for occurrence in p06["occurrences"]:
        if occurrence["action"] != "swap":
            continue
        left = p06["family_catalog"][occurrence["left_family"]]["left_asset"]
        right = p06["family_catalog"][occurrence["right_family"]]["right_asset"]
        p06_meshes.update((left, right))
    passages["P06"] = p06_meshes

    expected_counts = {"P01": 6, "P02": 35, "P03": 11, "P04": 8, "P05": 16, "P06": 12}
    actual_counts = {key: len(value) for key, value in passages.items()}
    if actual_counts != expected_counts:
        raise RuntimeError(f"PLACED_UNIQUE_COUNT_MISMATCH|expected={expected_counts}|actual={actual_counts}")

    wave_import = read_json("Saved/CodexFlatV3/swapkit/w2_import_FV3W2I-20261002-02.json")
    wave_actors = read_json("Saved/CodexFlatV3/probe_w2_actors_out.json")
    imported_v2 = sorted(path for path in wave_import["saved_roots"]
                         if "/StaticMeshes/" in path and path.endswith("_v2"))
    active_meshes = sorted(component["mesh"].split(".", 1)[0]
                           for actor in wave_actors["actors"]
                           for component in actor["components"])
    if any(path in active_meshes for path in imported_v2):
        raise RuntimeError("S3_V2_WAVE_UNEXPECTEDLY_ACTIVE")
    waves = [{
        "mesh": path,
        "owner": path.rsplit("/", 1)[-1].removeprefix("SM_FlatV3_").removesuffix("_v2"),
        "status": "imported_unused",
        "active_actor_meshes": active_meshes,
        "import_artifact": "Saved/CodexFlatV3/swapkit/w2_import_FV3W2I-20261002-02.json",
        "actor_probe": "Saved/CodexFlatV3/probe_w2_actors_out.json",
    } for path in imported_v2]
    return passages, waves, evidence


def manifest_index() -> dict[str, Path]:
    roots = [
        OVERNIGHT / "Kept" / "flats",
        OVERNIGHT / "P02Sets" / "flats",
        OVERNIGHT / "P03" / "flats",
        OVERNIGHT / "flats",
        OVERNIGHT / "P06" / "flats",
    ]
    result = {}
    for root in roots:
        for path in root.rglob("*_skin_manifest.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            result.setdefault(payload["asset"], path)
    return result


def build_inventory() -> dict:
    passages, waves, evidence = placed_assets()
    manifests = manifest_index()
    rows = []
    for passage, meshes in passages.items():
        for mesh in sorted(meshes):
            owner = owner_from_mesh(mesh)
            manifest_path = manifests.get(owner)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else None
            generated = bool(manifest and manifest.get("generator") == "Tools/FlatV3/build_skin.py")
            profile = manifest["peel"]["profile"] if generated else None
            rows.append({
                "passage": passage,
                "mesh": mesh,
                "owner": owner,
                "skin_from_build_skin": generated,
                "peel_profile": profile,
                "target_peel_percent": manifest["peel"]["target_percent"] if generated else None,
                "source_manifest": relative(manifest_path) if manifest_path else None,
                "action": "rebuild_pilot_organic" if profile == "pilot" else "unchanged",
            })
    rebuild_manifests = sorted({row["source_manifest"] for row in rows
                                if row["action"] == "rebuild_pilot_organic"})
    return {
        "schema_version": 1,
        "proof_tier": "measured from PASS placement/import artifacts and build_skin manifests",
        "placement_evidence": evidence,
        "placed_unique_by_passage": {key: len(value) for key, value in passages.items()},
        "placed_rows": rows,
        "placed_row_count": len(rows),
        "unique_pilot_manifest_count": len(rebuild_manifests),
        "unique_pilot_manifests": rebuild_manifests,
        "scene3_v2_waves": waves,
    }


def write_inventory(inventory: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    lines = [
        "# Flat V3 placed-skin inventory (offline, 3 Oct 2026)", "",
        "**Measured:** placement comes from PASS apply/import JSONs; skin provenance and peel profile come from each source skin manifest.", "",
        "| Passage | Mesh | build_skin | Peel profile | Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in inventory["placed_rows"]:
        lines.append("| {passage} | `{mesh}` | {built} | {profile} | {action} |".format(
            passage=row["passage"], mesh=row["mesh"],
            built="yes" if row["skin_from_build_skin"] else "no",
            profile=row["peel_profile"] or "n/a", action=row["action"]))
    lines += ["", "## Scene 3 `_v2` waves: imported but unused", "",
              "**Measured:** the import artifact contains the `_v2` packages, while the actor probe points all six actors at the unsuffixed meshes.", "",
              "| Imported mesh | Status |", "| --- | --- |"]
    for row in inventory["scene3_v2_waves"]:
        lines.append(f"| `{row['mesh']}` | {row['status']} |")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_slot_config(inventory: dict) -> Path:
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
        new_manifest_path = old_manifest_path.parent.parent / "skin_v2" / f"{owner}_skin_manifest.json"
        manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
        source_files = {kind: str((new_manifest_path.parent / manifest["textures"][kind]["file"]).resolve())
                        for kind in ("SkinColor", "SkinMask", "SkinNormal")}
        root = destinations[inventory_row["passage"]]
        old_textures = {kind: f"{root}/Textures/{owner}/T_{owner}_{kind}"
                        for kind in ("SkinColor", "SkinMask", "SkinNormal")}
        new_textures = {kind: path + "_o2" for kind, path in old_textures.items()}
        for slot in ("Front", "Flap"):
            rows.append({
                "passage": inventory_row["passage"], "owner": owner, "slot": slot,
                "mi": f"{root}/Materials/Instances/MI_FlatV3_{owner}_{slot}",
                "sources": source_files, "old_textures": old_textures,
                "new_textures": new_textures,
            })
    rows.sort(key=lambda row: (row["passage"], row["owner"], row["slot"]))
    unique_textures = {path for row in rows for path in row["new_textures"].values()}
    if len(rows) != 136 or len(unique_textures) != 204:
        raise RuntimeError(f"SLOT_CONFIG_COUNT_FAIL|mis={len(rows)}|textures={len(unique_textures)}")
    payload = {
        "schema_version": 1,
        "status": "AS_IS_NOT_RUN",
        "import_run_id": "FV3SKI-20261003-01",
        "apply_run_id": "FV3SK-20261003-01",
        "mi_count": len(rows), "new_texture_count": len(unique_textures),
        "rows": rows,
    }
    path = SAVED / "skins" / "skin_swap_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def cluster_exclusion(manifest: dict, shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    panel_w_cm, panel_h_cm = manifest["panel_size_cm"]
    yy, xx = np.indices((height, width), dtype=np.float32)
    x_cm = xx / max(width - 1, 1) * panel_w_cm
    y_cm = (height - 1 - yy) / max(height - 1, 1) * panel_h_cm
    excluded = np.zeros((height, width), dtype=bool)
    for centre_x, centre_y, _kind in manifest["peel"]["cluster_centres_cm"]:
        excluded |= np.square(x_cm - centre_x) + np.square(y_cm - centre_y) <= 130.0 ** 2
    return excluded


def validate_pair(old_manifest_path: Path, new_manifest_path: Path) -> dict:
    old = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    new = json.loads(new_manifest_path.read_text(encoding="utf-8"))
    old_dir, new_dir = old_manifest_path.parent, new_manifest_path.parent
    old_files = {key: old_dir / value["file"] for key, value in old["textures"].items()}
    new_files = {key: new_dir / value["file"] for key, value in new["textures"].items()}
    old_color = cv2.imread(str(old_files["SkinColor"]), cv2.IMREAD_UNCHANGED)
    new_color = cv2.imread(str(new_files["SkinColor"]), cv2.IMREAD_UNCHANGED)
    if old_color is None or new_color is None or old_color.shape != new_color.shape:
        raise RuntimeError(f"COLOR_RESOLUTION_MISMATCH|asset={old['asset']}")
    excluded = cluster_exclusion(old, old_color.shape[:2])
    outside_equal = bool(np.array_equal(old_color[~excluded], new_color[~excluded]))
    alpha_equal = bool(np.array_equal(old_color[:, :, 3], new_color[:, :, 3]))
    same_sizes = all(old["textures"][key]["size_px"] == new["textures"][key]["size_px"]
                     for key in ("SkinColor", "SkinMask", "SkinNormal"))
    same_inputs = all(old["inputs"][key] == new["inputs"][key]
                      for key in ("mask_sha256", "art_sha256", "older_poster_sha256",
                                  "paper_displacement_sha256", "paper_roughness_sha256"))
    same_centres = old["peel"]["cluster_centres_cm"] == new["peel"]["cluster_centres_cm"]
    peel_error = abs(float(new["peel"]["measured_percent"]) - float(old["peel"]["target_percent"]))
    old_fft = fft_summarize(old_files["SkinMask"], old_manifest_path, float("inf"))
    fft_threshold = old_fft["peak_median_power_ratio"] * FFT_OLD_PILOT_FRACTION
    fft = fft_summarize(new_files["SkinMask"], new_manifest_path, fft_threshold)
    checks = {
        "same_resolution": same_sizes,
        "same_input_art_and_silhouette_hashes": same_inputs,
        "skincolor_alpha_byte_identical": alpha_equal,
        "skincolor_outside_130cm_cluster_unions_byte_identical": outside_equal,
        "cluster_centres_identical": same_centres,
        "peel_percent_error": peel_error,
        "peel_within_half_percent": peel_error <= 0.5,
        "old_pilot_fft_peak_median_power_ratio": old_fft["peak_median_power_ratio"],
        "pilot_organic_fft_peak_median_power_ratio": fft["peak_median_power_ratio"],
        "fft_threshold": fft_threshold,
        "old_pilot_fft_fails": old_fft["peak_median_power_ratio"] >= fft_threshold,
        "fft_pass": fft["passes"],
        "fft_gate_scope": "diagnostic only per asset; canonical same-flat calibration is the acceptance gate",
    }
    if not all(value for key, value in checks.items()
               if key not in ("peel_percent_error", "old_pilot_fft_peak_median_power_ratio",
                              "pilot_organic_fft_peak_median_power_ratio", "fft_threshold",
                              "old_pilot_fft_fails", "fft_pass", "fft_gate_scope")):
        raise RuntimeError(f"ORGANIC_SKIN_VALIDATION_FAIL|asset={old['asset']}|checks={checks}")
    return checks


def rebuild(inventory: dict) -> dict:
    selected = [ROOT / value for value in inventory["unique_pilot_manifests"]]
    old_texture_hashes = {}
    fbx_stats = {}
    for manifest_path in selected:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for texture in manifest["textures"].values():
            path = manifest_path.parent / texture["file"]
            old_texture_hashes[relative(path)] = digest(path)
        flat_root = manifest_path.parent.parent
        for fbx in flat_root.glob("*.fbx"):
            stat = fbx.stat()
            fbx_stats[relative(fbx)] = [stat.st_size, stat.st_mtime_ns]

    results = []
    for index, manifest_path in enumerate(selected, 1):
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = manifest_path.parent.parent / "skin_v2"
        new_manifest_path = output / f"{old['asset']}_skin_manifest.json"
        if output.exists():
            if not new_manifest_path.is_file():
                raise RuntimeError(f"REFUSE_PARTIAL_EXISTING_OUTPUT|{output}")
            existing = json.loads(new_manifest_path.read_text(encoding="utf-8"))
            if existing["peel"]["profile"] != "pilot-organic":
                raise RuntimeError(f"REFUSE_NON_ORGANIC_EXISTING_OUTPUT|{output}")
        else:
            args = Namespace(
                mask=Path(old["inputs"]["mask"]), art=Path(old["inputs"]["art"]),
                older_poster=Path(old["inputs"]["older_poster"]),
                paper_displacement=Path(old["inputs"]["paper_displacement"]),
                paper_roughness=Path(old["inputs"]["paper_roughness"]),
                texture_root=ROOT, aged_output=output / "aged_unused",
                stencil_text=old["asset"], height_cm=float(old["panel_size_cm"][1]),
                width_cm=float(old["panel_size_cm"][0]),
                color_width=int(old["textures"]["SkinColor"]["size_px"][0]),
                color_height=int(old["textures"]["SkinColor"]["size_px"][1]),
                asset_name=old["asset"], output=output, diagnostics_output=None,
                seed=int(old["deterministic_seed"]),
                peel_percent=float(old["peel"]["target_percent"]),
                peel_profile="pilot-organic",
                substrate_profile=old["front_colour"]["substrate_profile"],
                texture_suffix="_o2", skip_aged_textures=True,
            )
            build_skin.build(args)
        checks = validate_pair(manifest_path, new_manifest_path)
        results.append({
            "asset": old["asset"], "old_manifest": relative(manifest_path),
            "new_manifest": relative(new_manifest_path), "checks": checks,
        })
        print(f"[{index:02d}/{len(selected):02d}] {old['asset']} PASS")

    old_unchanged = all(digest(ROOT / path) == value for path, value in old_texture_hashes.items())
    fbx_unchanged = True
    for path, signature in fbx_stats.items():
        stat = (ROOT / path).stat()
        fbx_unchanged &= [stat.st_size, stat.st_mtime_ns] == signature
    required_checks = (
        "same_resolution",
        "same_input_art_and_silhouette_hashes",
        "skincolor_alpha_byte_identical",
        "skincolor_outside_130cm_cluster_unions_byte_identical",
        "cluster_centres_identical",
        "peel_within_half_percent",
    )
    verification_summary = {
        "all_required_checks_pass": all(
            result["checks"][key]
            for result in results
            for key in required_checks
        ),
        "checked_skin_count": len(results),
        "max_peel_percent_error": max(
            result["checks"]["peel_percent_error"] for result in results
        ),
        "checks": list(required_checks),
    }
    report = {
        "schema_version": 1,
        "status": "PASS" if old_unchanged and fbx_unchanged else "FAIL",
        "execution": {"offline": True, "unreal": False, "mcp": False,
                      "port_8010": False, "gpu_work_performed": False,
                      "job_concurrency": 1},
        "source_skin_count": len(selected),
        "old_textures_unchanged_sha256": old_unchanged,
        "fbx_size_and_mtime_unchanged": fbx_unchanged,
        "verification_summary": verification_summary,
        "fft_threshold_rule": "per-flat threshold = 0.95 * reproducible old-pilot peak/median power ratio",
        "results": results,
    }
    if report["status"] != "PASS":
        raise RuntimeError("BATCH_FINAL_INTEGRITY_FAIL")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = build_inventory()
    write_inventory(inventory, REVIEW / "placed_flat_inventory.json")
    if args.inventory_only:
        print(json.dumps({"placed_rows": inventory["placed_row_count"],
                          "pilot_manifests": inventory["unique_pilot_manifest_count"],
                          "s3_v2_unused": len(inventory["scene3_v2_waves"])}))
        return 0
    report = rebuild(inventory)
    slot_config = write_slot_config(inventory)
    report["slot_config"] = relative(slot_config)
    (REVIEW / "organic_skin_batch_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "rebuilt": report["source_skin_count"],
                      "gpu_work_performed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
