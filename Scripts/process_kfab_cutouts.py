#!/usr/bin/env python3
"""Extract K_Fab viewer objects onto transparent, object-centred PNG canvases."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ASSETS = {
    "12.55.33": "stone-column-wall-fragment",
    "12.57.27": "weathered-stone-pilaster",
    "13.00.18": "ornate-stone-archway-facade",
    "13.07.21": "ruined-multi-storey-facade",
    "13.09.20": "broken-concrete-rubble-pile",
    "13.09.55": "reinforced-concrete-rebar-block",
    "13.11.48": "weathered-townhouse-facade",
    "13.12.42": "paired-stone-birds-planter",
    "13.14.30": "ruined-stone-tower",
    "13.17.44": "overgrown-ruined-stone-wall",
    "13.18.52": "small-stone-outbuilding",
    "13.19.24": "ruined-stone-doorway",
    "13.19.42": "ruined-stone-wall-fragment",
    "13.20.17": "worn-sofa-front-view",
    "13.20.38": "worn-sofa-side-view",
    "13.21.38": "wheeled-excavator",
    "13.22.09": "excavator-boom-arm-detail",
    "13.22.29": "vertical-metal-downpipe",
    "13.23.13": "ornate-stone-canopy-shrine",
    "13.29.59": "tree-trunk-exposed-roots",
}


# Viewer controls are separate from the scanned object and are explicitly removed.
# Coordinates are fractional so they remain tied to each source screenshot's canvas.
UI_MASKS = {
    "12.55.33": [(0.33, 0.89, 0.86, 1.00)],
    "13.18.52": [(0.72, 0.95, 0.90, 1.00)],
    "13.19.42": [(0.00, 0.92, 0.18, 1.00), (0.92, 0.00, 1.00, 0.09)],
    "13.20.17": [(0.53, 0.95, 0.70, 1.00)],
    "13.20.38": [(0.54, 0.94, 0.73, 1.00)],
    "13.21.38": [(0.42, 0.96, 0.55, 1.00)],
    "13.22.09": [(0.33, 0.93, 0.48, 1.00), (0.92, 0.00, 1.00, 0.09)],
    "13.22.29": [(0.25, 0.97, 0.75, 1.00)],
}


def keep_largest_component(alpha: Image.Image) -> Image.Image:
    """Keep the largest 4-connected opaque region using a scanline flood fill."""
    array = np.asarray(alpha, dtype=np.uint8)
    height, width = array.shape
    work = bytearray((array > 0).astype(np.uint8).tobytes())
    largest_area = 0
    largest_runs: list[tuple[int, int, int]] = []

    for start in range(width * height):
        if work[start] == 0:
            continue
        stack = [start]
        runs: list[tuple[int, int, int]] = []
        area = 0
        while stack:
            index = stack.pop()
            if work[index] == 0:
                continue
            y, x = divmod(index, width)
            row_start = y * width
            left = x
            while left > 0 and work[row_start + left - 1]:
                left -= 1
            right = x
            while right + 1 < width and work[row_start + right + 1]:
                right += 1
            for sx in range(left, right + 1):
                work[row_start + sx] = 0
            runs.append((y, left, right))
            area += right - left + 1

            for neighbour_y in (y - 1, y + 1):
                if neighbour_y < 0 or neighbour_y >= height:
                    continue
                neighbour_row = neighbour_y * width
                sx = left
                while sx <= right:
                    if work[neighbour_row + sx]:
                        stack.append(neighbour_row + sx)
                        while sx <= right and work[neighbour_row + sx]:
                            sx += 1
                    sx += 1

        if area > largest_area:
            largest_area = area
            largest_runs = runs

    result = np.zeros((height, width), dtype=np.uint8)
    for y, left, right in largest_runs:
        result[y, left : right + 1] = 255
    return Image.fromarray(result, mode="L")


def timestamp_for(path: Path) -> str:
    stem = path.stem
    marker = " at "
    if marker not in stem:
        raise ValueError(f"Unexpected filename: {path.name}")
    return stem.split(marker, 1)[1]


def background_alpha(
    image: Image.Image, timestamp: str
) -> tuple[Image.Image, np.ndarray]:
    """Build a refined matte and a local grayscale backdrop estimate."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    chroma = maximum - minimum
    luminance = np.rint(rgb.mean(axis=2)).astype(np.uint8)

    lum_image = Image.fromarray(luminance, mode="L")
    local_max = np.asarray(lum_image.filter(ImageFilter.MaxFilter(5)), dtype=np.int16)
    local_min = np.asarray(lum_image.filter(ImageFilter.MinFilter(5)), dtype=np.int16)
    local_range = local_max - local_min

    # The viewer backdrops are neutral grayscale. Find their dominant brightness
    # from smooth neutral pixels without assuming a fixed light or dark theme.
    smooth_neutral = (chroma <= 3) & (local_range <= 7)
    values = luminance[smooth_neutral]
    if values.size < 100:
        raise RuntimeError("Could not identify enough neutral background pixels")
    histogram = np.bincount(values, minlength=256)
    peak = int(histogram.argmax())

    potential = (
        (chroma <= 4)
        & (local_range <= 11)
        & (np.abs(luminance.astype(np.int16) - peak) <= 58)
    )
    potential_image = Image.fromarray((potential.astype(np.uint8) * 255), mode="L")

    # Mark every background-like region connected to the outside edge. This
    # protects similarly coloured object surfaces behind a clear silhouette edge.
    draw = ImageDraw.Draw(potential_image)
    width, height = potential_image.size
    for x in range(width):
        if potential_image.getpixel((x, 0)) == 255:
            ImageDraw.floodfill(potential_image, (x, 0), 128, thresh=0)
        if potential_image.getpixel((x, height - 1)) == 255:
            ImageDraw.floodfill(potential_image, (x, height - 1), 128, thresh=0)
    for y in range(height):
        if potential_image.getpixel((0, y)) == 255:
            ImageDraw.floodfill(potential_image, (0, y), 128, thresh=0)
        if potential_image.getpixel((width - 1, y)) == 255:
            ImageDraw.floodfill(potential_image, (width - 1, y), 128, thresh=0)

    marked = np.asarray(potential_image, dtype=np.uint8)
    external_background = marked == 128

    # Estimate the viewer backdrop locally by row. This is used to remove the
    # gray/black color contamination baked into antialiased source-edge pixels.
    row_background = np.full(height, np.nan, dtype=np.float32)
    for y in range(height):
        row_values = luminance[y][external_background[y]]
        if row_values.size >= max(8, round(width * 0.02)):
            row_background[y] = float(np.median(row_values))
    known_rows = np.flatnonzero(np.isfinite(row_background))
    if known_rows.size:
        row_background = np.interp(
            np.arange(height), known_rows, row_background[known_rows]
        ).astype(np.float32)
    else:
        row_background.fill(float(peak))
    background_map = np.broadcast_to(row_background[:, None], (height, width)).copy()

    # Also clear very smooth enclosed backdrop holes, such as spaces between
    # columns or machinery. The tighter thresholds protect neutral object faces.
    enclosed_background = (
        (marked == 255)
        & (chroma <= 1)
        & (local_range <= 3)
        & (np.abs(luminance.astype(np.int16) - peak) <= 58)
    )
    background = external_background | enclosed_background
    alpha = Image.fromarray((~background).astype(np.uint8) * 255, mode="L")

    # Remove known floating viewer controls before edge cleanup.
    alpha_draw = ImageDraw.Draw(alpha)
    alpha_draw.rectangle((0, 0, width, max(3, round(height * 0.003))), fill=0)
    for x0, y0, x1, y1 in UI_MASKS.get(timestamp, []):
        alpha_draw.rectangle(
            (
                round(x0 * width),
                round(y0 * height),
                round(x1 * width),
                round(y1 * height),
            ),
            fill=0,
        )

    alpha = keep_largest_component(alpha)

    # Contract by two source pixels to remove the viewer's baked-in dark/light
    # antialias rim. Genuine narrow elements remain recoverable in the soft edge.
    silhouette = alpha.filter(ImageFilter.MinFilter(5))
    silhouette_array = np.asarray(silhouette, dtype=np.uint8) > 0
    core = silhouette.filter(ImageFilter.MinFilter(3))
    core_array = np.asarray(core, dtype=np.uint8) > 0
    edge = silhouette_array & ~core_array

    # Compute a soft edge only inside the narrow silhouette band, based on the
    # pixel's distance from the locally estimated neutral viewer backdrop.
    rgb_float = rgb.astype(np.float32)
    backdrop_rgb = background_map[:, :, None]
    color_distance = np.sqrt(np.sum((rgb_float - backdrop_rgb) ** 2, axis=2))
    # A broad ramp is essential for screenshots rendered over black or pale gray:
    # their antialiased boundary pixels can be far from the backdrop while still
    # representing only a small fraction of the foreground object.
    ramp = np.clip((color_distance - 2.0) / 148.0, 0.0, 1.0)
    ramp = ramp * ramp * (3.0 - 2.0 * ramp)
    refined = np.zeros((height, width), dtype=np.float32)
    refined[core_array] = 1.0
    refined[edge] = ramp[edge]
    alpha = Image.fromarray(np.rint(refined * 255.0).astype(np.uint8), mode="L")
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.95))
    alpha_array = np.asarray(alpha, dtype=np.float32) / 255.0
    alpha_array = np.power(alpha_array, 1.22)
    alpha = Image.fromarray(np.rint(alpha_array * 255.0).astype(np.uint8), mode="L")
    return alpha, background_map


def decontaminate_edges(
    image: Image.Image, alpha: Image.Image, background_map: np.ndarray
) -> Image.Image:
    """Unmix the neutral viewer backdrop from partially transparent edge pixels."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    alpha_array = np.asarray(alpha, dtype=np.float32) / 255.0
    backdrop = background_map[:, :, None]
    safe_alpha = np.maximum(alpha_array[:, :, None], 0.06)
    recovered = (rgb - (1.0 - alpha_array[:, :, None]) * backdrop) / safe_alpha
    recovered = np.clip(recovered, 0.0, 255.0)

    # Reconstruction can amplify colored subpixel scan noise. Suppress chroma in
    # proportion to edge transparency while retaining the original opaque colors.
    recovered_luma = np.sum(
        recovered * np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), axis=2
    )
    chroma_factor = np.clip(alpha_array * 1.55, 0.0, 1.0)[:, :, None]
    recovered = recovered_luma[:, :, None] + (
        recovered - recovered_luma[:, :, None]
    ) * chroma_factor

    # Preserve fully opaque source pixels exactly; decontaminate only the matte edge.
    partial = (alpha_array > 0.0) & (alpha_array < 0.999)
    cleaned = rgb.copy()
    cleaned[partial] = recovered[partial]
    cleaned[alpha_array <= 0.0] = 0.0
    rgba = np.dstack(
        (np.rint(cleaned).astype(np.uint8), np.rint(alpha_array * 255.0).astype(np.uint8))
    )
    return Image.fromarray(rgba, mode="RGBA")


def resize_premultiplied(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize RGBA without allowing hidden background RGB to bleed into edges."""
    if image.size == size:
        return image
    array = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = array[:, :, 3] / 255.0
    premultiplied = np.rint(array[:, :, :3] * alpha[:, :, None]).astype(np.uint8)
    resized_channels = [
        np.asarray(
            Image.fromarray(premultiplied[:, :, channel], mode="L").resize(
                size, Image.Resampling.LANCZOS
            ),
            dtype=np.float32,
        )
        for channel in range(3)
    ]
    resized_premultiplied = np.stack(resized_channels, axis=2)
    resized_alpha = np.asarray(
        Image.fromarray(np.rint(alpha * 255.0).astype(np.uint8), mode="L").resize(
            size, Image.Resampling.LANCZOS
        ),
        dtype=np.float32,
    )
    alpha_float = resized_alpha / 255.0
    output_rgb = np.zeros_like(resized_premultiplied)
    visible = alpha_float > 0.01
    output_rgb[visible] = np.clip(
        resized_premultiplied[visible] / alpha_float[visible, None], 0.0, 255.0
    )
    output = np.dstack((np.rint(output_rgb).astype(np.uint8), resized_alpha.astype(np.uint8)))
    return Image.fromarray(output, mode="RGBA")


def crop_upscale_and_pad(
    image: Image.Image, alpha: Image.Image, background_map: np.ndarray
) -> Image.Image:
    rgba = decontaminate_edges(image, alpha, background_map)
    box = alpha.getbbox()
    if box is None:
        raise RuntimeError("Extraction produced an empty alpha matte")

    crop = rgba.crop(box)
    width, height = crop.size
    longest = max(width, height)
    scale = max(1.0, 2000.0 / longest)
    scaled_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if scaled_size != crop.size:
        crop = resize_premultiplied(crop, scaled_size)

    pad = max(32, round(max(crop.size) * 0.035))
    canvas_width = max(2000, crop.width + 2 * pad)
    canvas_height = max(2000, crop.height + 2 * pad)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    offset = ((canvas_width - crop.width) // 2, (canvas_height - crop.height) // 2)
    canvas.alpha_composite(crop, offset)
    return canvas


def normalize_existing_rgba(image: Image.Image) -> Image.Image:
    """Crop, premultiplied-upscale, and pad an already transparent asset."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        raise RuntimeError("Transparent asset has an empty alpha channel")

    crop = rgba.crop(box)
    longest = max(crop.size)
    scale = max(1.0, 2000.0 / longest)
    scaled_size = (
        max(1, round(crop.width * scale)),
        max(1, round(crop.height * scale)),
    )
    if scaled_size != crop.size:
        crop = resize_premultiplied(crop, scaled_size)

    pad = max(32, round(max(crop.size) * 0.035))
    canvas_width = max(2000, crop.width + 2 * pad)
    canvas_height = max(2000, crop.height + 2 * pad)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    offset = ((canvas_width - crop.width) // 2, (canvas_height - crop.height) // 2)
    canvas.alpha_composite(crop, offset)
    return canvas


def process(source_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(source_dir.glob("Screenshot 2026-07-19 at *.png"))
    if len(sources) != len(ASSETS):
        raise RuntimeError(f"Expected {len(ASSETS)} screenshots, found {len(sources)}")

    for source in sources:
        timestamp = timestamp_for(source)
        description = ASSETS[timestamp]
        image = Image.open(source)
        alpha, background_map = background_alpha(image, timestamp)
        result = crop_upscale_and_pad(image, alpha, background_map)
        output = output_dir / f"{source.stem}-{description}.png"
        result.save(output, format="PNG", optimize=True)
        extrema = result.getchannel("A").getextrema()
        bbox = result.getchannel("A").getbbox()
        print(f"{output.name}\t{result.width}x{result.height}\talpha={extrema}\tbbox={bbox}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    process(args.source_dir, args.output_dir)


if __name__ == "__main__":
    main()
