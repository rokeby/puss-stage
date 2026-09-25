#!/usr/bin/env python3
"""Generate conservative height and tangent-space normal maps for painted wing PNGs.

The height map is derived from masked, multi-scale local luminance contrast rather
than raw brightness. This suppresses most of the source image's broad baked light
gradient while retaining salt ledges, cavities, granular crust, and painted relief.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Batch mode: process every PNG in --input directory into per-asset folders",
    )
    parser.add_argument("--height-out", type=Path)
    parser.add_argument("--normal-out", type=Path)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--normal-strength", type=float, default=10.0)
    return parser.parse_args()


def masked_blur(values: np.ndarray, mask: np.ndarray, radius: float) -> np.ndarray:
    weighted = Image.fromarray(np.uint8(np.clip(values * mask, 0.0, 1.0) * 255.0), "L")
    weights = Image.fromarray(np.uint8(np.clip(mask, 0.0, 1.0) * 255.0), "L")
    weighted = np.asarray(weighted.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0
    weights = np.asarray(weights.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0
    return weighted / np.maximum(weights, 1.0 / 255.0)


def robust_remap(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    sample = values[mask > 0.5]
    if sample.size == 0:
        raise ValueError("Input alpha contains no opaque pixels")
    low, high = np.percentile(sample, (1.0, 99.0))
    if high <= low:
        raise ValueError("Source image contains insufficient relief contrast")
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    # Keep headroom around the reference plane so Bump Offset remains stable.
    return 0.10 + normalized * 0.80


def make_preview(base: Image.Image, height: np.ndarray, normal: np.ndarray) -> Image.Image:
    rgba = np.asarray(base.convert("RGBA"), dtype=np.uint8)
    checker = np.empty_like(rgba[:, :, :3])
    yy, xx = np.indices(rgba.shape[:2])
    checker_value = np.where(((xx // 32 + yy // 32) % 2) == 0, 44, 70).astype(np.uint8)
    checker[:] = checker_value[:, :, None]
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    base_rgb = np.uint8(rgba[:, :, :3] * alpha + checker * (1.0 - alpha))
    height_rgb = np.repeat(np.uint8(np.clip(height, 0.0, 1.0)[:, :, None] * 255.0), 3, axis=2)
    normal_rgb = np.uint8(np.clip(normal, 0.0, 1.0) * 255.0)
    gutter = np.full((rgba.shape[0], 16, 3), 18, dtype=np.uint8)
    return Image.fromarray(np.concatenate((base_rgb, gutter, height_rgb, gutter, normal_rgb), axis=1), "RGB")


def process_one(
    input_path: Path,
    height_out: Path,
    normal_out: Path,
    preview_out: Path | None,
    normal_strength: float,
) -> str:
    source = Image.open(input_path).convert("RGBA")
    rgba = np.asarray(source, dtype=np.float32) / 255.0
    rgb = rgba[:, :, :3]
    mask = rgba[:, :, 3]

    # Work in approximately linear light so painted highlights do not dominate.
    linear_rgb = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    luminance = (
        linear_rgb[:, :, 0] * 0.2126
        + linear_rgb[:, :, 1] * 0.7152
        + linear_rgb[:, :, 2] * 0.0722
    )

    fine = masked_blur(luminance, mask, 1.25)
    medium = masked_blur(luminance, mask, 7.0)
    broad = masked_blur(luminance, mask, 28.0)
    relief_signal = (fine - medium) * 0.72 + (medium - broad) * 0.28
    height = robust_remap(relief_signal, mask)
    height[mask <= 0.01] = 0.5
    height_image = Image.fromarray(np.uint8(np.clip(height, 0.0, 1.0) * 255.0), "L")
    height_image = height_image.filter(ImageFilter.GaussianBlur(0.55))
    height = np.asarray(height_image, dtype=np.float32) / 255.0

    dy, dx = np.gradient(height)
    nx = -dx * normal_strength
    ny = -dy * normal_strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack((nx / length, ny / length, nz / length), axis=2) * 0.5 + 0.5
    normal[mask <= 0.01] = (0.5, 0.5, 1.0)

    height_out.parent.mkdir(parents=True, exist_ok=True)
    normal_out.parent.mkdir(parents=True, exist_ok=True)
    height_image.save(height_out)
    Image.fromarray(np.uint8(np.clip(normal, 0.0, 1.0) * 255.0), "RGB").save(normal_out)
    if preview_out:
        preview_out.parent.mkdir(parents=True, exist_ok=True)
        make_preview(source, height, normal).save(preview_out)

    opaque = mask > 0.5
    return " ".join(
        [
            f"asset={input_path.stem}",
            f"size={source.width}x{source.height}",
            f"opaque_pixels={int(np.count_nonzero(opaque))}",
            f"height_min={float(height[opaque].min()):.4f}",
            f"height_max={float(height[opaque].max()):.4f}",
            f"height_mean={float(height[opaque].mean()):.4f}",
            f"normal_strength={normal_strength:.2f}",
        ]
    )


def main() -> int:
    args = parse_args()
    if args.input.is_dir():
        if not args.output_dir:
            raise ValueError("Batch mode requires --output-dir")
        inputs = sorted(args.input.glob("*.png"))
        if not inputs:
            raise ValueError("Batch input directory contains no PNGs")
        for input_path in inputs:
            texture_dir = args.output_dir / input_path.stem / "Textures"
            status = process_one(
                input_path,
                texture_dir / f"{input_path.stem}_H.png",
                texture_dir / f"{input_path.stem}_N.png",
                args.output_dir / input_path.stem / f"{input_path.stem}_relief-preview.png",
                args.normal_strength,
            )
            print("RELIEF_MAPS_OK", status)
        print(f"RELIEF_MAPS_BATCH_OK count={len(inputs)}")
        return 0

    if not args.height_out or not args.normal_out:
        raise ValueError("Single-file mode requires --height-out and --normal-out")
    print(
        "RELIEF_MAPS_OK",
        process_one(
            args.input,
            args.height_out,
            args.normal_out,
            args.preview_out,
            args.normal_strength,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
