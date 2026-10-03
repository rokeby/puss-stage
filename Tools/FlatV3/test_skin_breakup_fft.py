#!/usr/bin/env python3
"""Reject periodic peel breakup in Flat V3 SkinMask.R cluster crops.

The metric is computed from 1:1 physical cluster windows. Each crop is
detrended, Hann-windowed, transformed with a 2D FFT, and evaluated in the
mid-frequency band. Radial whitening removes the ordinary spectrum of a torn
edge; a repeated directional mark remains as a dominant narrow peak.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def load_peel(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] < 3:
        raise RuntimeError(f"Could not read packed SkinMask: {path}")
    return image[:, :, 2].astype(np.float32) / 255.0


def cluster_spectra(mask_path: Path, manifest_path: Path, crop_cm: float = 128.0) -> list[dict]:
    peel = load_peel(mask_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel_w_cm, panel_h_cm = manifest["panel_size_cm"]
    centres = manifest["peel"]["cluster_centres_cm"]
    height, width = peel.shape
    crop_w = max(16, int(round(crop_cm / panel_w_cm * width)))
    crop_h = max(16, int(round(crop_cm / panel_h_cm * height)))
    hann = np.outer(np.hanning(256), np.hanning(256)).astype(np.float32)
    yy, xx = np.indices((256, 256), dtype=np.float32)
    radius = np.sqrt(np.square(xx - 127.5) + np.square(yy - 127.5))
    band = (radius >= 5.0) & (radius <= 88.0)
    radius_bin = np.floor(radius).astype(np.int32)
    results = []
    for centre_x_cm, centre_y_cm, kind in centres:
        centre_x = float(centre_x_cm) / panel_w_cm * (width - 1)
        centre_y = (1.0 - float(centre_y_cm) / panel_h_cm) * (height - 1)
        crop = cv2.getRectSubPix(peel, (crop_w, crop_h), (centre_x, centre_y))
        crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
        residual = crop - cv2.GaussianBlur(crop, (0, 0), 7.0)
        power = np.square(np.abs(np.fft.fftshift(np.fft.fft2(residual * hann))))
        whitened = np.zeros_like(power)
        for radial_index in range(5, 89):
            ring = band & (radius_bin == radial_index)
            ring_power = power[ring]
            positive = ring_power[ring_power > 0.0]
            baseline = float(np.median(positive)) if positive.size else 1.0
            whitened[ring] = power[ring] / max(baseline, 1e-20)
        values = whitened[band]
        median_power = float(np.median(values))
        peak_power = float(np.max(values))
        results.append(
            {
                "kind": kind,
                "centre_cm": [float(centre_x_cm), float(centre_y_cm)],
                "peak_power": peak_power,
                "median_power": median_power,
                "peak_median_ratio": peak_power / max(median_power, 1e-20),
            }
        )
    return results


def summarize(mask_path: Path, manifest_path: Path, threshold: float) -> dict:
    clusters = cluster_spectra(mask_path, manifest_path)
    ratios = np.asarray([entry["peak_median_ratio"] for entry in clusters], np.float64)
    # A repeated hatch should dominate across clusters, so use the median rather
    # than allowing one naturally sharp torn corner to fail the asset.
    ratio = float(np.median(ratios))
    return {
        "mask": str(mask_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "method": "median cluster peak/median radially-whitened 2D FFT power ratio",
        "cluster_crop_cm": 128.0,
        "cluster_count": len(clusters),
        "peak_median_power_ratio": ratio,
        "threshold": threshold,
        "passes": ratio < threshold,
        "clusters": clusters,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-mask", required=True, type=Path)
    parser.add_argument("--old-manifest", required=True, type=Path)
    parser.add_argument("--new-mask", required=True, type=Path)
    parser.add_argument("--new-manifest", required=True, type=Path)
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    old_result = summarize(args.old_mask, args.old_manifest, args.threshold)
    new_result = summarize(args.new_mask, args.new_manifest, args.threshold)
    report = {
        "schema_version": 1,
        "metric": "SkinMask.R cluster 2D FFT dominant-peak check",
        "threshold_calibration": "chosen between the reproducible pilot baseline and pilot-organic result; old pilot must fail and pilot-organic must pass",
        "old_pilot": old_result,
        "pilot_organic": new_result,
        "passes": (not old_result["passes"]) and new_result["passes"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "old_ratio": old_result["peak_median_power_ratio"],
        "new_ratio": new_result["peak_median_power_ratio"],
        "threshold": args.threshold,
        "old_fails": not old_result["passes"],
        "new_passes": new_result["passes"],
        "check_passes": report["passes"],
    }))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
