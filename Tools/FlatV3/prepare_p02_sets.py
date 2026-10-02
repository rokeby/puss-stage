#!/usr/bin/env python3
"""Prepare the exact 24-item Flat V3 P02 batch from Gary's run list."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT = Path(__file__).resolve().parents[2]
RUN_LIST = PROJECT / "DerivedAssets/FlatV3/FuserQueue/25_P02_lurid_plants/adapt_inputs/RUN_LIST.md"
KEPT_PICKS = PROJECT / "DerivedAssets/FlatV3/Overnight/KEPT_PICKS.json"
OUTPUT = PROJECT / "DerivedAssets/FlatV3/Overnight/P02Sets/BUILD_PICKS.json"
PICKED_SETS = ("01", "04", "06", "07", "16", "18", "19", "20")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_run_list() -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^- (P02_SET(\d{2})_([LRC]))\.jpg\s+\(from (.+?), \[(\d+), (\d+)\]\)$"
    )
    records = []
    for line in RUN_LIST.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        label, set_number, side, source, width, height = match.groups()
        records.append({
            "label": label, "set_number": set_number, "side": side,
            "source": source, "declared_size": [int(width), int(height)],
        })
    expected_labels = {
        f"P02_SET{set_number}_{side}" for set_number in PICKED_SETS for side in ("L", "R", "C")
    }
    actual_labels = {record["label"] for record in records}
    if actual_labels != expected_labels:
        raise RuntimeError(
            f"RUN_LIST exact-label gate failed; missing={sorted(expected_labels - actual_labels)}, "
            f"extra={sorted(actual_labels - expected_labels)}"
        )
    return records


def main() -> int:
    kept_payload = json.loads(KEPT_PICKS.read_text(encoding="utf-8"))
    kept_by_set_side: dict[tuple[str, str], dict[str, Any]] = {}
    for pick in kept_payload["build_picks"]:
        if pick.get("passage") != "P02":
            continue
        match = re.search(r"P02_SET(\d{2})_[LRT]", str(pick["canonical_path"]))
        if match:
            kept_by_set_side[(match.group(1), str(pick["side"]).upper())] = pick

    build_picks = []
    for record in parse_run_list():
        set_number, side = record["set_number"], record["side"]
        authority = kept_by_set_side.get((set_number, side))
        if authority is None:
            raise RuntimeError(f"No KEPT_PICKS authority for P02 SET{set_number} {side}")
        source_rel = record["source"]
        source = PROJECT / source_rel
        if not source.is_file():
            raise FileNotFoundError(source)
        with Image.open(source) as image:
            actual_size = [image.width, image.height]
            bands = image.getbands()
        if actual_size != record["declared_size"]:
            raise RuntimeError(
                f"RUN_LIST size mismatch for {record['label']}: declared={record['declared_size']} actual={actual_size}"
            )

        special_opacity_export = set_number == "01" and side == "L"
        flags = dict(authority.get("flags", {}))
        flags.update({
            "alpha_missing": False,
            "alpha_recovered_by_chroma": not special_opacity_export,
            "alpha_recovered_from_old_opacity_mask": special_opacity_export,
            "sam_fallback_used": False,
        })
        if special_opacity_export:
            if "A" not in bands:
                raise RuntimeError("SET01_L texture export has no alpha channel; SAM fallback would be required")
            flags["manual_review_flag"] = (
                "SET01_L uses the matching old Unreal texture-export opacity alpha; SAM was not needed"
            )

        build_picks.append({
            "canonical_path": source_rel,
            "source_kind": "unreal_texture_export" if special_opacity_export else "approved_original_chroma",
            "source_pixel_size": actual_size,
            "source_has_alpha": "A" in bands,
            "source_sha256": sha256(source),
            "flat_type": authority["flat_type"],
            "target_height_cm": authority["target_height_cm"],
            "target_height_status": authority.get("target_height_status"),
            "side": side,
            "passage": "P02",
            "mesh_being_replaced": authority["mesh_being_replaced"],
            "mesh_bounds_height_cm": authority.get("mesh_bounds_height_cm"),
            "local_scale_z": authority.get("local_scale_z"),
            "current_rendered_height_cm": authority.get("current_rendered_height_cm"),
            "alpha_mode": "opacity_mask" if special_opacity_export else "chroma",
            "opacity_mask_source": source_rel if special_opacity_export else None,
            "opacity_mask_channel": "A" if special_opacity_export else None,
            "asset_suffix": record["label"],
            "build_authorized": True,
            "deterministic_triangulation": True,
            "peel_profile": "bottom-heavy" if side == "C" else None,
            "peel_percent": 2.0 if side == "C" else None,
            "flags": flags,
            "source_authority": {
                "run_list": str(RUN_LIST.relative_to(PROJECT)).replace("\\", "/"),
                "kept_picks": str(KEPT_PICKS.relative_to(PROJECT)).replace("\\", "/"),
                "kept_status": authority.get("status"),
                "kept_evidence": authority.get("evidence"),
            },
        })

    build_picks.sort(key=lambda pick: pick["asset_suffix"])
    expected_names = [f"SM_FlatV3_P02_SET{set_number}_{side}" for set_number in PICKED_SETS for side in ("L", "R", "C")]
    payload = {
        "schema_version": 1,
        "batch_label": "Flat V3 P02 - Gary's eight picked plant sets",
        "authority": [
            str(RUN_LIST.relative_to(PROJECT)).replace("\\", "/"),
            str(KEPT_PICKS.relative_to(PROJECT)).replace("\\", "/"),
        ],
        "selection_note": "Gary explicitly authorized P02 sets 01, 04, 06, 07, 16, 18, 19 and 20 as they are, upscaled 2x.",
        "expected_asset_count": 24,
        "expected_asset_names": expected_names,
        "mapping_filename": "MESH_SWAP_MAP.json",
        "build_picks": build_picks,
    }
    if len(build_picks) != 24:
        raise RuntimeError(f"Expected 24 build picks, got {len(build_picks)}")
    atomic_json(OUTPUT, payload)
    print(f"P02_SET_BATCH_PREPARED count={len(build_picks)} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
