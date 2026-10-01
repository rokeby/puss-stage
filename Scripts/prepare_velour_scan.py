"""Prepare the Poly Haven velour scan for the curtain material bench."""

from pathlib import Path

import numpy as np
from PIL import Image


TARGET_SIZE = (4096, 4096)
TARGET_MEAN = 128.0
MAX_STD = 20.0
REC709 = np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)
PREVIEW_TINT_LINEAR = np.array((0.07, 0.004, 0.012), dtype=np.float32)


def srgb_to_linear(values):
    values = values.astype(np.float32) / 255.0
    return np.where(
        values <= 0.04045,
        values / 12.92,
        ((values + 0.055) / 1.055) ** 2.4,
    )


def linear_to_srgb(values):
    values = np.clip(values, 0.0, 1.0)
    return np.where(
        values <= 0.0031308,
        values * 12.92,
        1.055 * np.power(values, 1.0 / 2.4) - 0.055,
    )


def quantize_with_exact_mean(values, target_mean):
    quantized = np.clip(np.rint(values), 0, 255).astype(np.uint8)
    target_sum = int(target_mean * quantized.size)
    residual = target_sum - int(quantized.sum(dtype=np.int64))
    if residual == 0:
        return quantized

    flat = quantized.reshape(-1)
    direction = 1 if residual > 0 else -1
    remaining = abs(residual)
    eligible_limit = 255 if direction > 0 else 0

    # Rounding leaves only a small residual. Spread corrections across the image
    # so the exact integer mean does not create a visible strip or seam.
    while remaining:
        count = min(remaining, flat.size)
        positions = ((np.arange(count, dtype=np.int64) + 0.5) * flat.size / count).astype(
            np.int64
        )
        valid = flat[positions] < eligible_limit if direction > 0 else flat[positions] > eligible_limit
        positions = positions[valid]
        if positions.size == 0:
            raise RuntimeError("cannot reach the requested exact mask mean")
        positions = positions[:remaining]
        flat[positions] = (flat[positions].astype(np.int16) + direction).astype(np.uint8)
        remaining -= positions.size

    if int(quantized.sum(dtype=np.int64)) != target_sum:
        raise RuntimeError("mask mean correction did not reach its exact target")
    return quantized


def edge_difference_metrics(values):
    values = values.astype(np.float32, copy=False)
    horizontal_wrap = np.mean(np.abs(values[:, -1] - values[:, 0]))
    vertical_wrap = np.mean(np.abs(values[-1] - values[0]))
    wrap = float((horizontal_wrap + vertical_wrap) * 0.5)

    horizontal_interior = 0.5 * (
        np.mean(np.abs(values[:, -1] - values[:, -2]))
        + np.mean(np.abs(values[:, 1] - values[:, 0]))
    )
    vertical_interior = 0.5 * (
        np.mean(np.abs(values[-1] - values[-2]))
        + np.mean(np.abs(values[1] - values[0]))
    )
    interior = float((horizontal_interior + vertical_interior) * 0.5)
    ratio = wrap / interior if interior > 1.0e-8 else (0.0 if wrap <= 1.0e-8 else float("inf"))
    return wrap, interior, ratio


def print_tile_check(label, values):
    wrap, interior, ratio = edge_difference_metrics(values)
    comparable = ratio <= 2.0
    print(
        f"{label} tile check: wrap={wrap:.6f}, interior={interior:.6f}, "
        f"ratio={ratio:.3f}, comparable={str(comparable).lower()}"
    )
    if not comparable:
        print(f"{label}: source appears non-tileable; no seam repair was applied")


def build_mask(colour_image):
    colour = np.asarray(colour_image, dtype=np.uint8)
    linear_rgb = srgb_to_linear(colour)
    luma = np.sum(linear_rgb * REC709, axis=2, dtype=np.float32) * 255.0
    del colour, linear_rgb

    before_mean = float(np.mean(luma, dtype=np.float64))
    before_std = float(np.std(luma, dtype=np.float64))
    contrast_scale = min(1.0, MAX_STD / before_std) if before_std > 0.0 else 1.0
    adjusted = (luma - before_mean) * contrast_scale + TARGET_MEAN
    if float(adjusted.min()) < 0.0 or float(adjusted.max()) > 255.0:
        low = -255.0
        high = 255.0
        centered = (luma - before_mean) * contrast_scale
        for _ in range(32):
            midpoint = (low + high) * 0.5
            candidate_mean = float(np.mean(np.clip(centered + midpoint, 0.0, 255.0)))
            if candidate_mean < TARGET_MEAN:
                low = midpoint
            else:
                high = midpoint
        adjusted = np.clip(centered + (low + high) * 0.5, 0.0, 255.0)

    mask = quantize_with_exact_mean(adjusted, TARGET_MEAN)
    after_std = float(np.std(mask, dtype=np.float64))
    if before_std > MAX_STD and after_std > MAX_STD:
        # Integer quantisation can add a few thousandths of a level. Nudge the
        # scaled contrast down until the delivered 8-bit image respects the cap.
        for _ in range(8):
            contrast_scale *= (MAX_STD / after_std) * 0.9999
            adjusted = (luma - before_mean) * contrast_scale + TARGET_MEAN
            mask = quantize_with_exact_mean(adjusted, TARGET_MEAN)
            after_std = float(np.std(mask, dtype=np.float64))
            if after_std <= MAX_STD:
                break

    after_mean = float(np.mean(mask, dtype=np.float64))
    print(f"mask before: mean={before_mean:.6f}, std={before_std:.6f}")
    print(f"mask after:  mean={after_mean:.6f}, std={after_std:.6f}")
    return mask


def build_normal(normal_image):
    encoded = np.asarray(normal_image, dtype=np.uint8)
    normal = encoded.astype(np.float32) / 127.5 - 1.0
    lengths = np.linalg.norm(normal, axis=2)
    zero_length = lengths < 1.0e-8
    lengths[zero_length] = 1.0
    normal /= lengths[:, :, None]
    normal[zero_length] = (0.0, 0.0, 1.0)

    tilt = np.degrees(np.arccos(np.clip(normal[:, :, 2], -1.0, 1.0)))
    print(
        f"normal tilt: mean={float(np.mean(tilt, dtype=np.float64)):.6f} deg, "
        f"p99={float(np.percentile(tilt, 99)):.6f} deg"
    )
    output = np.clip(np.rint((normal * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    return output, normal


def build_preview(mask, normal_encoded, output_path):
    height, width = mask.shape
    preview_tile = np.empty((height, width, 3), dtype=np.uint8)
    main_light = np.array((-0.84, 0.36, 0.40), dtype=np.float32)
    main_light /= np.linalg.norm(main_light)
    fill_light = np.array((0.24, -0.31, 0.92), dtype=np.float32)
    fill_light /= np.linalg.norm(fill_light)

    for start in range(0, height, 256):
        stop = min(start + 256, height)
        normal = normal_encoded[start:stop].astype(np.float32) / 127.5 - 1.0
        normal[:, :, :2] *= 0.7
        normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1.0e-8)
        main = np.maximum(np.sum(normal * main_light, axis=2), 0.0)
        fill = np.maximum(np.sum(normal * fill_light, axis=2), 0.0)
        light = 0.38 + 1.05 * main + 0.22 * fill
        weave = mask[start:stop].astype(np.float32) / TARGET_MEAN
        linear = PREVIEW_TINT_LINEAR[None, None, :] * weave[:, :, None] * light[:, :, None]
        preview_tile[start:stop] = np.clip(np.rint(linear_to_srgb(linear) * 255.0), 0, 255).astype(
            np.uint8
        )

    tile_image = Image.fromarray(preview_tile, mode="RGB")
    preview = Image.new("RGB", (width * 2, height * 2))
    preview.paste(tile_image, (0, 0))
    preview.paste(tile_image, (width, 0))
    preview.paste(tile_image, (0, height))
    preview.paste(tile_image, (width, height))
    preview.save(output_path)


def main():
    project_root = Path(__file__).resolve().parents[1]
    source_dir = project_root / "Saved" / "CodexSoftGoods" / "VelvetScan"
    output_dir = project_root / "DerivedAssets" / "CurtainCloth" / "Textures"
    colour_path = source_dir / "velour_velvet_diff_4k.jpg"
    normal_path = source_dir / "velour_velvet_nor_dx_4k.jpg"
    mask_path = output_dir / "T_CurtainVelourScan.png"
    normal_output_path = output_dir / "T_CurtainVelourScan_N.png"
    preview_path = output_dir / "T_CurtainVelourScan_preview.png"
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(colour_path) as source_colour, Image.open(normal_path) as source_normal:
        print(f"colour source size: {source_colour.size[0]}x{source_colour.size[1]}")
        print(f"normal source size: {source_normal.size[0]}x{source_normal.size[1]}")
        colour_resized = source_colour.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        normal_resized = source_normal.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)

    mask = build_mask(colour_resized)
    normal_output, normalized_normal = build_normal(normal_resized)
    Image.fromarray(mask, mode="L").save(mask_path)
    Image.fromarray(normal_output, mode="RGB").save(normal_output_path)

    print_tile_check("mask", mask)
    print_tile_check("normal", normalized_normal)
    build_preview(mask, normal_output, preview_path)
    print(f"wrote: {mask_path}")
    print(f"wrote: {normal_output_path}")
    print(f"wrote: {preview_path}")


if __name__ == "__main__":
    main()
