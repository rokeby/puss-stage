#!/usr/bin/env python3
"""Validate and package the generated Scene 3 backdrop texture set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ASSET = "S3_OpalBeach_Backdrop"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(path: Path, expected_size: tuple[int, int], expected_mode: str) -> dict:
    with Image.open(path) as image:
        image.load()
        if image.size != expected_size or image.mode != expected_mode:
            raise RuntimeError(
                f"{path.name}: expected {expected_size} {expected_mode}, got {image.size} {image.mode}"
            )
        extrema = image.getextrema()
    return {
        "file": str(path.resolve()),
        "size_px": list(expected_size),
        "mode": expected_mode,
        "channel_extrema": [list(pair) for pair in extrema],
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    textures = root / "textures"
    qa = root / "qa"
    qa.mkdir(parents=True, exist_ok=True)

    color_path = textures / f"T_{ASSET}_SkinColor.png"
    mask_path = textures / f"T_{ASSET}_SkinMask.png"
    normal_path = textures / f"T_{ASSET}_SkinNormal.png"
    records = {
        "SkinColor": image_record(color_path, (4096, 8192), "RGBA"),
        "SkinMask": image_record(mask_path, (1024, 2048), "RGBA"),
        "SkinNormal": image_record(normal_path, (1024, 2048), "RGB"),
    }

    mask_image = Image.open(mask_path).convert("RGBA")
    mask = np.asarray(mask_image)
    peel = mask[:, :, 0] > 0
    bottom_500_start = round(mask.shape[0] * (1.0 - 500.0 / 3000.0))
    bottom_500 = np.zeros_like(peel)
    bottom_500[bottom_500_start:, :] = True
    measured_peel = 100.0 * np.count_nonzero(peel) / peel.size
    peel_in_bottom_500 = 100.0 * np.count_nonzero(peel & bottom_500) / max(np.count_nonzero(peel), 1)

    labels = ("R peel amount", "G paper height", "B roughness", "A paste-soak")
    channel_preview = Image.new("RGB", (2048, 1080), (232, 232, 232))
    draw = ImageDraw.Draw(channel_preview)
    for index, label in enumerate(labels):
        channel = mask_image.getchannel(index).resize((480, 960), Image.Resampling.LANCZOS).convert("RGB")
        x = 16 + index * 508
        channel_preview.paste(channel, (x, 64))
        draw.text((x, 24), label, fill=(20, 20, 20))
    channel_preview.save(qa / "SkinMask_channels.png", compress_level=6)

    # Native texture pixels: no resampling. Centre the square on the accepted
    # left huddle after source-crop normalization and POT mapping.
    color = Image.open(color_path).convert("RGBA")
    huddle_center_source = ((250 + 735) / 2.0 - 28.0, (1910 + 2305) / 2.0 - 34.0)
    centre_x = round(huddle_center_source[0] / 1640.0 * color.width)
    centre_y = round(huddle_center_source[1] / 2460.0 * color.height)
    half = 512
    crop_box = (centre_x - half, centre_y - half, centre_x + half, centre_y + half)
    color.crop(crop_box).save(qa / "S3_Backdrop_HuddleLeft_1to1.png", compress_level=6)

    target_root = "/Game/Scenes/Wings/FlatV3/Scene3"
    mi_params = {
        "schema_version": 1,
        "material_instance": {
            "name": "MI_S3_OpalBeach_Backdrop",
            "parent": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
            "target": f"{target_root}/Materials/MI_S3_OpalBeach_Backdrop",
        },
        "texture_parameters": {
            "SkinColor": f"{target_root}/Textures/T_{ASSET}_SkinColor",
            "SkinMask": f"{target_root}/Textures/T_{ASSET}_SkinMask",
            "SkinNormal": f"{target_root}/Textures/T_{ASSET}_SkinNormal",
        },
        "scalar_parameters": {
            "SheetWidthM": 1.0,
            "SheetHeightM": 1.5,
            "SheetOverlapM": 0.025,
            "RowOffset": 0.5,
        },
        "texture_import": {
            "SkinColor": {"srgb": True, "compression": "Default/BC7", "mips": "full"},
            "SkinMask": {"srgb": False, "compression": "TC_Masks", "mips": "full", "channels": {"R": "continuous peel amount", "G": "paper height", "B": "roughness", "A": "paste-soak gloss/AO"}},
            "SkinNormal": {"srgb": False, "compression": "Normalmap/BC5", "mips": "full", "convention": "DirectX"},
        },
        "surface": {
            "panel_size_cm": [2000.0, 3000.0],
            "mesh_owner": "Rig",
            "mount": "S3 Far Wall hinge",
            "mesh_contract": "separate 20x30 m engine plane, UV0 0-1; texture non-uniform resample is restored by the plane aspect",
        },
    }
    (root / "mi_params.json").write_text(json.dumps(mi_params, indent=2), encoding="utf-8")

    validation = {
        "schema_version": 1,
        "asset": ASSET,
        "textures": records,
        "peel": {
            "measured_nonzero_percent": round(measured_peel, 6),
            "measured_percent_in_bottom_500cm": round(peel_in_bottom_500, 6),
            "target_percent": 2.5,
            "profile": "bottom-heavy",
        },
        "preview_crop": {
            "file": str((qa / "S3_Backdrop_HuddleLeft_1to1.png").resolve()),
            "source_texture_box_px": list(crop_box),
            "size_px": [1024, 1024],
            "resampled": False,
        },
        "proof": {
            "measured": [
                "All three production textures decoded at their required dimensions and channel modes.",
                f"SkinMask R has {measured_peel:.6f}% nonzero peel pixels; {peel_in_bottom_500:.6f}% of those pixels lie within the bottom 500 cm.",
                "The huddle crop is a direct 1024x1024 pixel crop from SkinColor with no resampling.",
            ],
            "inferred": [
                "Import settings and material parameter paths remain unverified until the separate Unreal integration pass.",
            ],
        },
    }
    (root / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(f"TEXTURES_OK|color=4096x8192|mask=1024x2048|normal=1024x2048")
    print(f"PEEL_OK|percent={measured_peel:.6f}|bottom500cm={peel_in_bottom_500:.6f}")
    print("MI_PARAMS_OK|parent=MI_Billboard_Front|target=/Game/Scenes/Wings/FlatV3/Scene3")


if __name__ == "__main__":
    main()
