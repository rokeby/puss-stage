"""Pixel-check the Blender Unreal-parity backdrop render with the Flat V3 venv."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


COTTAGES_UV0_BOX = (
    (1010.0 - 28.0) / 1640.0,
    (1665.0 - 34.0) / 2460.0,
    (1660.0 - 28.0) / 1640.0,
    (1935.0 - 34.0) / 2460.0,
)


def standardized_grey(image: np.ndarray) -> np.ndarray:
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return (grey - float(grey.mean())) / (float(grey.std()) + 1.0e-6)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--texture", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = cv2.imread(str(args.texture.resolve()), cv2.IMREAD_COLOR)
    render = cv2.imread(str(args.render.resolve()), cv2.IMREAD_COLOR)
    if source is None or render is None:
        raise RuntimeError("Texture or render did not decode")

    non_black = cv2.cvtColor(render, cv2.COLOR_BGR2GRAY) > 12
    ys, xs = np.where(non_black)
    if not len(xs):
        raise RuntimeError("No rendered panel pixels found")
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    panel = render[top:bottom, left:right]
    reference = cv2.resize(source, (panel.shape[1], panel.shape[0]), interpolation=cv2.INTER_AREA)
    panel_grey = standardized_grey(panel)
    reference_grey = standardized_grey(reference)
    correct_correlation = float(np.mean(panel_grey * reference_grey))
    flipped_correlation = float(np.mean(panel_grey * np.fliplr(reference_grey)))

    u0, v0, u1, v1 = COTTAGES_UV0_BOX
    x0, x1 = round(u0 * panel.shape[1]), round(u1 * panel.shape[1])
    y0, y1 = round(v0 * panel.shape[0]), round(v1 * panel.shape[0])
    mirrored_x0, mirrored_x1 = panel.shape[1] - x1, panel.shape[1] - x0
    cottage_reference = standardized_grey(reference[y0:y1, x0:x1])
    cottage_right = standardized_grey(panel[y0:y1, x0:x1])
    cottage_left = standardized_grey(panel[y0:y1, mirrored_x0:mirrored_x1])
    cottage_left = cv2.resize(cottage_left, (cottage_reference.shape[1], cottage_reference.shape[0]))
    right_correlation = float(np.mean(cottage_reference * cottage_right))
    left_correlation = float(np.mean(cottage_reference * cottage_left))

    checks = {
        "render_matches_unflipped_texture": {
            "pass": correct_correlation > flipped_correlation + 0.10,
            "correct_correlation": correct_correlation,
            "horizontally_flipped_correlation": flipped_correlation,
            "required_margin": 0.10,
        },
        "cottages_pixels_are_on_screen_right": {
            "pass": right_correlation > left_correlation + 0.25 and (x0 + x1) / 2.0 > panel.shape[1] / 2.0,
            "right_region_correlation": right_correlation,
            "mirrored_left_region_correlation": left_correlation,
            "required_margin": 0.25,
            "cottages_box_in_panel_px": [x0, y0, x1, y1],
        },
    }
    result = {
        "schema_version": 1,
        "runtime": "FlatV3 venv (OpenCV and NumPy)",
        "texture": str(args.texture.resolve()),
        "render": str(args.render.resolve()),
        "render_size_px": [int(render.shape[1]), int(render.shape[0])],
        "panel_bbox_px_left_top_right_bottom": [left, top, right, bottom],
        "checks": checks,
        "pass": all(check["pass"] for check in checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["pass"]:
        raise RuntimeError(f"Backdrop render pixel validation failed: {args.output}")
    print(
        "SCENE3_BACKDROP_PIXEL_VALIDATION_PASS"
        f"|whole={correct_correlation:.6f}>{flipped_correlation:.6f}"
        f"|cottages_right={right_correlation:.6f}>{left_correlation:.6f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
