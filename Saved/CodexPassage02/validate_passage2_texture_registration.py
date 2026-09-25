#!/usr/bin/env python3
"""Validate V2 Base/alpha, height, normal, and relief-preview registration."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image


PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT / "DerivedAssets/Passage01V2Batch/Input"
OUTPUT_ROOT = PROJECT / "DerivedAssets/Passage01V2Batch/GeneratedWings"
REPORT_PATH = PROJECT / "DerivedAssets/Passage01V2Batch/texture_registration_validation.json"


def main() -> int:
    sources = sorted(SOURCE_ROOT.glob("P01_SET*.png"))
    if len(sources) != 60:
        raise RuntimeError(f"Expected 60 Base RGBA sources, found {len(sources)}")
    results = []
    failures = []
    for source in sources:
        asset = source.stem
        texture_dir = OUTPUT_ROOT / asset / "Textures"
        copied_base = texture_dir / source.name
        height = texture_dir / f"{asset}_H.png"
        normal = texture_dir / f"{asset}_N.png"
        preview = OUTPUT_ROOT / asset / f"{asset}_relief-preview.png"
        errors = []
        paths = [source, copied_base, height, normal, preview]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            errors.append(f"Missing files: {missing}")
            dimensions = {}
            modes = {}
        else:
            opened = {path.name: Image.open(path) for path in paths}
            dimensions = {name: list(image.size) for name, image in opened.items()}
            modes = {name: image.mode for name, image in opened.items()}
            base_size = opened[source.name].size
            for map_path in (copied_base, height, normal):
                if opened[map_path.name].size != base_size:
                    errors.append(
                        f"{map_path.name} size {opened[map_path.name].size} != Base {base_size}"
                    )
            expected_preview_size = (base_size[0] * 3 + 32, base_size[1])
            if opened[preview.name].size != expected_preview_size:
                errors.append(
                    f"Preview size {opened[preview.name].size} != {expected_preview_size}"
                )
            if opened[source.name].mode != "RGBA" or opened[copied_base.name].mode != "RGBA":
                errors.append("Base source/copy must be RGBA")
            if opened[height.name].mode != "L":
                errors.append("Height map must be single-channel linear grayscale")
            if opened[normal.name].mode != "RGB":
                errors.append("Normal map must be RGB")
            if source.read_bytes() != copied_base.read_bytes():
                errors.append("Copied Base texture differs byte-for-byte from approved source")
            for image in opened.values():
                image.close()
        result = {
            "asset": asset,
            "status": "ok" if not errors else "error",
            "dimensions": dimensions,
            "modes": modes,
            "normal_strength": 4.5,
            "derived_after_orientation_approval": True,
            "errors": errors,
        }
        results.append(result)
        if errors:
            failures.append(asset)
    report = {
        "profile": "PussStage Wing V2",
        "generator": str(PROJECT / "Tools/StageOpening/generate_relief_maps.py"),
        "normal_strength": 4.5,
        "validated_count": len(results),
        "failed_count": len(failures),
        "failures": failures,
        "status": "ok" if not failures else "error",
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "P02_V2_TEXTURE_REGISTRATION_"
        f"{'SUCCESS' if not failures else 'FAILED'}"
        f"|count={len(results)}|failed={len(failures)}|report={REPORT_PATH}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
