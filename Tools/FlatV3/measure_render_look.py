"""Measure robust contrast and saturation for Flat V3 review images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def subject_pixels(path: Path, infer_dark_background: bool) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    if image.shape[2] == 4 and not infer_dark_background:
        mask = image[:, :, 3] >= 128
        bgr = image[:, :, :3]
    else:
        bgr = image[:, :, :3]
        corners = np.vstack((bgr[:32, :32].reshape(-1, 3), bgr[:32, -32:].reshape(-1, 3),
                             bgr[-32:, :32].reshape(-1, 3), bgr[-32:, -32:].reshape(-1, 3)))
        background = np.median(corners.astype(np.float32), axis=0)
        distance = np.linalg.norm(bgr.astype(np.float32) - background[None, None, :], axis=2)
        mask = distance > 12.0
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        if count > 1:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            mask = labels == largest
    if np.count_nonzero(mask) < 1000:
        raise RuntimeError(f"Subject mask too small for {path}: {np.count_nonzero(mask)} pixels")
    return bgr[mask][:, ::-1].astype(np.float32) / 255.0


def srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def metrics(path: Path, infer_dark_background: bool) -> dict:
    rgb = subject_pixels(path, infer_dark_background)
    linear = srgb_to_linear(rgb)
    luma = linear @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    maximum = rgb.max(axis=1)
    minimum = rgb.min(axis=1)
    saturation = np.where(maximum > 1e-6, (maximum - minimum) / maximum, 0.0)
    p05, p95 = np.quantile(luma, (0.05, 0.95))
    return {
        "file": str(path.resolve()),
        "subject_pixels": int(len(rgb)),
        "linear_luma_p05": round(float(p05), 6),
        "linear_luma_p95": round(float(p95), 6),
        "linear_luma_p95_minus_p05": round(float(p95 - p05), 6),
        "linear_luma_stddev": round(float(np.std(luma)), 6),
        "hsv_saturation_mean": round(float(np.mean(saturation)), 6),
        "hsv_saturation_median": round(float(np.median(saturation)), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", nargs=2, metavar=("LABEL", "PATH"), required=True)
    parser.add_argument("--infer-dark-background", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inferred = set(args.infer_dark_background)
    results = {label: metrics(Path(path), label in inferred) for label, path in args.image}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "metrics": results}, indent=2), encoding="utf-8")
    print("FLAT_V3_LOOK_MEASURED")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
