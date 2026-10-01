"""Generate seamless, stage-scale crushed-velvet colour and normal textures."""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image


SIZE = 2048
DEFAULT_SEED = 20260930


def periodic_noise(
    size,
    rng,
    min_frequency,
    max_frequency,
    components,
    gaussian_sigma_tiles=0.0,
):
    """Return standardized, isotropic periodic Fourier noise.

    Directions, radii and phases are randomized independently. Integer wave
    vectors keep the result exactly tile-periodic; weighting each component by
    a Gaussian transfer function is equivalent to a wrap-aware Gaussian blur.
    """
    if components < 64:
        raise ValueError("periodic fields need at least 64 randomized components")

    spectrum = np.zeros((size, size), dtype=np.complex64)
    for _ in range(components):
        while True:
            direction = rng.uniform(0.0, math.tau)
            radius = math.sqrt(
                rng.uniform(min_frequency * min_frequency, max_frequency * max_frequency)
            )
            frequency_x = int(round(radius * math.cos(direction)))
            frequency_y = int(round(radius * math.sin(direction)))
            frequency_length = math.hypot(frequency_x, frequency_y)
            if min_frequency <= frequency_length <= max_frequency:
                break

        phase = rng.uniform(0.0, math.tau)
        amplitude = rng.uniform(0.75, 1.25) / math.sqrt(components)
        if gaussian_sigma_tiles > 0.0:
            amplitude *= math.exp(
                -0.5
                * (math.tau * gaussian_sigma_tiles * frequency_length) ** 2
            )
        coefficient = np.complex64(amplitude * complex(math.cos(phase), math.sin(phase)))
        spectrum[frequency_y % size, frequency_x % size] += coefficient
        spectrum[-frequency_y % size, -frequency_x % size] += np.conj(coefficient)

    result = np.fft.ifft2(spectrum).real.astype(np.float32)
    result -= np.mean(result, dtype=np.float64)
    deviation = float(np.std(result, dtype=np.float64))
    if deviation <= 1.0e-8:
        raise RuntimeError("periodic noise unexpectedly has zero variance")
    return result / np.float32(deviation)


def patch_frequency_band(patches):
    """Keep the default patch field in the soft 1.5--4 cycles-per-tile range."""
    upper = max(1.5, float(patches))
    lower = max(1.0, upper * 0.375)
    return lower, upper


def encode_normal_map(rng, patches, tilt_deg):
    low_min, low_max = patch_frequency_band(patches)
    angle_field = periodic_noise(
        SIZE, rng, low_min, low_max, 128, gaussian_sigma_tiles=0.055
    )
    strength_broad = periodic_noise(
        SIZE, rng, low_min, low_max, 128, gaussian_sigma_tiles=0.065
    )
    strength_detail = periodic_noise(
        SIZE,
        rng,
        low_max + 1.0,
        low_max * 3.0,
        192,
        gaussian_sigma_tiles=0.018,
    )
    strength_field = (
        np.float32(0.42) * strength_broad
        + np.float32(0.58) * strength_detail
    )
    strength_field /= np.float32(np.std(strength_field, dtype=np.float64))

    # Work in a continuous angle field so pile direction bends instead of
    # snapping at vector-field zeroes. The tilt envelope forms soft patches:
    # its extremes approach flat and the requested maximum respectively.
    angle = np.float32(math.pi) * np.tanh(np.float32(0.42) * angle_field)
    strength = np.float32(0.5) + np.float32(0.5) * np.tanh(
        np.float32(0.9) * strength_field
    )
    strength = strength * strength * (np.float32(3.0) - np.float32(2.0) * strength)
    maximum_slope = np.float32(math.tan(math.radians(tilt_deg)))
    low_slope = maximum_slope * strength
    slope_x = low_slope * np.cos(angle)
    slope_y = low_slope * np.sin(angle)

    slope_length = np.sqrt(slope_x * slope_x + slope_y * slope_y)
    scale = np.minimum(np.float32(1.0), maximum_slope / np.maximum(slope_length, 1.0e-8))
    slope_x *= scale
    slope_y *= scale
    inverse_length = np.float32(1.0) / np.sqrt(
        slope_x * slope_x + slope_y * slope_y + np.float32(1.0)
    )

    # Unreal uses DirectX tangent normals: red is +X/right and green is +Y/down.
    normal = np.stack(
        (slope_x * inverse_length, slope_y * inverse_length, inverse_length), axis=2
    )
    encoded = np.rint((normal * np.float32(0.5) + np.float32(0.5)) * np.float32(255.0))
    return np.clip(encoded, 0.0, 255.0).astype(np.uint8)


def make_colour_map(rng, patches, requested_std):
    low_min, low_max = patch_frequency_band(patches)
    broad = periodic_noise(
        SIZE, rng, low_min, low_max, 192, gaussian_sigma_tiles=0.045
    )
    detail_min = max(low_max + 1.0, float(patches) * 2.0)
    detail_max = max(detail_min + 1.0, float(patches) * 5.0)
    detail = periodic_noise(
        SIZE, rng, detail_min, detail_max, 192, gaussian_sigma_tiles=0.012
    )
    # The broad field establishes the crushed patches; a substantial but still
    # soft isotropic layer removes memorable low-frequency landmarks when tiled.
    field = np.float32(0.58) * broad + np.float32(0.42) * detail
    field -= np.mean(field, dtype=np.float64)
    field /= np.float32(np.std(field, dtype=np.float64))
    colour = np.rint(np.float32(128.0) + np.float32(requested_std) * field)
    return np.clip(colour, 0.0, 255.0).astype(np.uint8)


def seam_numbers(pixels):
    values = pixels.astype(np.int16)
    horizontal_interior = np.abs(values[:, 1:] - values[:, :-1])
    vertical_interior = np.abs(values[1:, :] - values[:-1, :])
    horizontal_wrap = np.abs(values[:, 0] - values[:, -1])
    vertical_wrap = np.abs(values[0, :] - values[-1, :])
    numbers = {
        "x_wrap_max": int(horizontal_wrap.max()),
        "x_interior_max": int(horizontal_interior.max()),
        "x_wrap_mean": float(horizontal_wrap.mean()),
        "x_interior_mean": float(horizontal_interior.mean()),
        "y_wrap_max": int(vertical_wrap.max()),
        "y_interior_max": int(vertical_interior.max()),
        "y_wrap_mean": float(vertical_wrap.mean()),
        "y_interior_mean": float(vertical_interior.mean()),
    }
    assert numbers["x_wrap_max"] <= numbers["x_interior_max"], numbers
    assert numbers["y_wrap_max"] <= numbers["y_interior_max"], numbers
    return numbers


def make_preview(colour, encoded_normal):
    normal = encoded_normal.astype(np.float32) / np.float32(127.5) - np.float32(1.0)
    normal[:, :, :2] *= np.float32(0.5)
    normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), np.float32(1.0e-8))
    light = np.asarray([0.70, -0.32, 0.64], dtype=np.float32)
    light /= np.linalg.norm(light)
    illumination = np.clip(np.sum(normal * light[None, None, :], axis=2), 0.0, 1.0)
    illumination = np.float32(0.50) + np.float32(0.50) * illumination
    colour_modulation = colour.astype(np.float32) / np.float32(128.0)
    base = np.asarray([118.0, 12.0, 25.0], dtype=np.float32)
    rgb = base[None, None, :] * colour_modulation[:, :, None] * illumination[:, :, None]
    sheen = np.power(np.clip(illumination, 0.0, 1.0), np.float32(4.0))[:, :, None]
    rgb += sheen * np.asarray([22.0, 6.0, 8.0], dtype=np.float32)[None, None, :]
    tile = np.clip(np.rint(rgb), 0.0, 255.0).astype(np.uint8)

    close_panel = np.tile(tile, (2, 2, 1))
    # Sixteen tiles in the same-size panel: each occupies one quarter of the
    # close-panel tile area, making the repeated read visible at a distance.
    reduced = Image.fromarray(tile).resize(
        (SIZE // 2, SIZE // 2), resample=Image.Resampling.LANCZOS
    )
    distance_panel = np.tile(np.asarray(reduced), (4, 4, 1))
    return np.concatenate((close_panel, distance_panel), axis=1)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--patches", type=int, default=4, help="low-frequency cycles per tile")
    parser.add_argument("--tilt-deg", type=float, default=30.0)
    parser.add_argument("--color-std", type=float, default=12.0)
    args = parser.parse_args()
    if args.patches < 1:
        parser.error("--patches must be at least 1")
    if not 0.0 < args.tilt_deg < 80.0:
        parser.error("--tilt-deg must be between 0 and 80")
    if not 0.0 < args.color_std < 64.0:
        parser.error("--color-std must be between 0 and 64")
    return args


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    colour = make_colour_map(rng, args.patches, args.color_std)
    normal = encode_normal_map(rng, args.patches, args.tilt_deg)
    preview = make_preview(colour, normal)

    colour_seams = seam_numbers(colour)
    normal_seams = seam_numbers(normal)
    output_dir = Path(__file__).resolve().parents[1] / "DerivedAssets" / "CurtainCloth" / "Textures"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "colour": output_dir / "T_CurtainVelvetCrush.png",
        "normal": output_dir / "T_CurtainVelvetCrush_N.png",
        "preview": output_dir / "T_CurtainVelvetCrush_preview.png",
    }
    Image.fromarray(colour).save(outputs["colour"])
    Image.fromarray(normal).save(outputs["normal"])
    Image.fromarray(preview).save(outputs["preview"])

    for label, path in outputs.items():
        print(f"{label}={path}")
    print(
        f"colour_stats=mean:{float(colour.mean()):.3f},std:{float(colour.std()):.3f}"
    )
    print(f"colour_seams={colour_seams}")
    print(f"normal_seams={normal_seams}")
    print("normal_convention=DirectX tangent space, +X right, +Y down, +Z outward")


if __name__ == "__main__":
    main()
