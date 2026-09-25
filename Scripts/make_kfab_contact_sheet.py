#!/usr/bin/env python3
"""Build a black/white edge stress sheet for the K_Fab cutout batch."""

from pathlib import Path
import argparse

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sources = sorted(args.input_dir.glob("*.png"))
    if not sources:
        raise RuntimeError(f"No PNG files found in {args.input_dir}")

    columns = 4
    rows = (len(sources) + columns - 1) // columns
    tile_width, tile_height = 600, 460
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)

    for index, source in enumerate(sources):
        column, row = index % columns, index // columns
        left, top = column * tile_width, row * tile_height
        preview_height = tile_height - 54
        draw.rectangle((left, top, left + tile_width // 2, top + preview_height), fill="black")
        draw.rectangle(
            (left + tile_width // 2, top, left + tile_width, top + preview_height),
            fill="white",
        )

        asset = Image.open(source).convert("RGBA")
        alpha_box = asset.getchannel("A").getbbox()
        if alpha_box is None:
            continue
        asset = asset.crop(alpha_box)
        maximum = (tile_width // 2 - 30, preview_height - 30)
        asset.thumbnail(maximum, Image.Resampling.LANCZOS)
        for half in range(2):
            center_x = left + tile_width // 4 + half * tile_width // 2
            position = (center_x - asset.width // 2, top + (preview_height - asset.height) // 2)
            sheet.paste(asset, position, asset)

        label = source.stem.replace("Screenshot 2026-07-19 at ", "")
        draw.rectangle(
            (left, top + preview_height, left + tile_width, top + tile_height),
            fill=(232, 232, 232),
        )
        draw.text((left + 8, top + preview_height + 8), label, fill="black", font=font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=94, subsampling=0)
    print(f"Wrote {args.output} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
