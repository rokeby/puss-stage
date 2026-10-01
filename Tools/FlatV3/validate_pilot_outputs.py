"""Validate the complete rendered/texture Flat V3 pilot delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2


VIEWS = ("head_on_6m", "front_head_on_poles", "front_three_quarter_poles", "peel_closeup_1m",
         "grazing_30deg", "back_three_quarter_2m", "back_head_on")


def image_record(path: Path, expected_size: tuple[int, int] | None, channels: tuple[int, ...]) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    actual_channels = 1 if image is not None and image.ndim == 2 else (image.shape[2] if image is not None else None)
    actual_size = [int(image.shape[1]), int(image.shape[0])] if image is not None else None
    size_valid = False
    if actual_size is not None:
        size_valid = (tuple(actual_size) == expected_size if expected_size is not None else
                      all(value >= 1024 and value <= 4096 and value & (value - 1) == 0 for value in actual_size))
    valid = image is not None and size_valid and actual_channels in channels
    return {
        "file": str(path.resolve()), "size_px": actual_size, "channels": actual_channels,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        "pass": bool(valid),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.pilot_dir.resolve()
    textures: dict[str, dict] = {}
    renders: dict[str, dict] = {}
    object_lists: dict[str, dict] = {}
    for side in ("L", "R"):
        base = f"P02_RuisdaelA_{side}"
        textures[f"{side}_SkinColor"] = image_record(root / f"T_{base}_SkinColor.png", (2048, 4096), (4,))
        textures[f"{side}_SkinMask"] = image_record(root / f"T_{base}_SkinMask.png", (1024, 2048), (4,))
        textures[f"{side}_SkinNormal"] = image_record(root / f"T_{base}_SkinNormal.png", (1024, 2048), (3, 4))
        manifest = json.loads((root / f"{base}_build.json").read_text(encoding="utf-8"))
        expected = ["Dummy_8cm_Groove", "Floor_Back", "Floor_Front", f"SM_FlatV3_{base}_LOD0"]
        if not manifest.get("baked_poles", {}).get("enabled", False):
            expected.extend((f"Pole_{side}_1", f"Pole_{side}_2"))
        expected = sorted(expected)
        for view in VIEWS:
            key = f"{side}_{view}"
            renders[key] = image_record(root / f"{base}_{view}.png", (1400, 1000), (4,))
            actual = sorted(manifest["render"]["asserted_object_lists"].get(view, []))
            object_lists[key] = {"actual": actual, "expected": expected, "pass": actual == expected}
    aged: dict[str, dict] = {}
    for side in ("L", "R"):
        aged_dir = root / "Aged" / side
        for path in sorted(aged_dir.glob("*.png")):
            aged[f"{side}/{path.name}"] = image_record(path, None, (1, 3, 4))
    texture_report = {
        "schema_version": 1, "textures": textures, "aged_textures": aged,
        "pass": all(record["pass"] for record in (*textures.values(), *aged.values())),
    }
    render_report = {
        "schema_version": 1, "renders": renders, "asserted_object_lists": object_lists,
        "pass": all(record["pass"] for record in renders.values()) and all(record["pass"] for record in object_lists.values()),
    }
    (root / "texture_validation.json").write_text(json.dumps(texture_report, indent=2) + "\n", encoding="utf-8")
    (root / "render_validation.json").write_text(json.dumps(render_report, indent=2) + "\n", encoding="utf-8")
    if not texture_report["pass"] or not render_report["pass"]:
        raise RuntimeError("Flat V3 pilot output validation failed")
    print("FLAT_V3_PILOT_OUTPUTS_PASS")
    print(json.dumps({"texture_count": len(textures) + len(aged), "render_count": len(renders), "object_list_assertions": len(object_lists)}))


if __name__ == "__main__":
    main()
