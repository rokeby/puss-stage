#!/usr/bin/env python3
"""Build Gary's Scene 3 backdrop v3 without changing the painting.

The production path centre-crops the source to an exact 2:3 image, calls the
existing tiled Real-ESRGAN function for a 2x intermediate, then resamples to
the 4096x8192 power-of-two texture used by the 20x30 m backdrop.  It also
rebuilds the exit-door leaf crop for the mural's measured 150 cm lower offset.

``--dry`` decodes and validates the input and prints the complete plan without
creating a directory or running Real-ESRGAN.  The offline harness injects a
tiny CPU upscaler; the CLI never exposes that test seam and always uses the
existing production Real-ESRGAN function.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw


EXPECTED_SOURCE_SIZE = (1696, 2528)
POT_SIZE = (4096, 8192)
INTERMEDIATE_SCALE = 2
LEAF_OUTPUT_SIZE = (1024, 2048)
BACKDROP_SIZE_CM = (2000.0, 3000.0)
ORIGINAL_BACKDROP_BOTTOM_Z_CM = -5.0
MURAL_DROP_CM = 150.0
LOWERED_BACKDROP_BOTTOM_Z_CM = ORIGINAL_BACKDROP_BOTTOM_Z_CM - MURAL_DROP_CM
LEAF_CENTER_YZ_CM = (0.0, 225.0)
LEAF_SIZE_YZ_CM = (299.0, 449.0)
EXPECTED_LEAF_RECT = [0.42525, 0.7985, 0.57475, 0.9481666666666667]

FINAL_NAME = "T_S3_BackdropV3_SkinColor.png"
LEAF_NAME = "T_S3_BackdropV3_ExitDoor_SkinColor.png"
INTERMEDIATE_NAME = "S3_BackdropV3_RealESRGAN_2x.png"
QA_NAME = "S3_BackdropV3_QA.png"
REPORT_NAME = "build_report.json"


class BuildError(ValueError):
    """The declared backdrop build contract was not met."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_two_by_three_crop(size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Return the largest centred integer crop whose width:height is 2:3."""
    width, height = (int(size[0]), int(size[1]))
    unit = min(width // 2, height // 3)
    if unit < 1:
        raise BuildError("image is too small for an exact 2:3 integer crop")
    crop_w, crop_h = unit * 2, unit * 3
    left = (width - crop_w) // 2
    top = (height - crop_h) // 2
    box = (left, top, left + crop_w, top + crop_h)
    validate_crop_box(box)
    return box


def validate_crop_box(box: tuple[int, int, int, int]) -> None:
    width, height = int(box[2] - box[0]), int(box[3] - box[1])
    if width <= 0 or height <= 0 or width * 3 != height * 2:
        raise BuildError("crop is not exactly 2:3: %dx%d" % (width, height))


def validate_pot_size(size: tuple[int, int]) -> None:
    width, height = (int(size[0]), int(size[1]))
    if (width, height) != POT_SIZE:
        raise BuildError("production POT output must be 4096x8192, got %dx%d" % (width, height))
    if any(value <= 0 or value & (value - 1) for value in (width, height)):
        raise BuildError("output dimensions are not powers of two")


def leaf_uv_rect(backdrop_bottom_z_cm: float) -> list[float]:
    """Map the visible 299x449 cm leaf footprint into the lowered backdrop."""
    half_y = LEAF_SIZE_YZ_CM[0] * 0.5
    half_z = LEAF_SIZE_YZ_CM[1] * 0.5
    y0, y1 = LEAF_CENTER_YZ_CM[0] - half_y, LEAF_CENTER_YZ_CM[0] + half_y
    z0, z1 = LEAF_CENTER_YZ_CM[1] - half_z, LEAF_CENTER_YZ_CM[1] + half_z
    u0 = (y0 + BACKDROP_SIZE_CM[0] * 0.5) / BACKDROP_SIZE_CM[0]
    u1 = (y1 + BACKDROP_SIZE_CM[0] * 0.5) / BACKDROP_SIZE_CM[0]
    v_top = 1.0 - (z1 - backdrop_bottom_z_cm) / BACKDROP_SIZE_CM[1]
    v_bottom = 1.0 - (z0 - backdrop_bottom_z_cm) / BACKDROP_SIZE_CM[1]
    return [u0, v_top, u1, v_bottom]


def validate_lowered_leaf_rect(rect: list[float]) -> None:
    if len(rect) != 4 or max(abs(float(a) - b) for a, b in zip(rect, EXPECTED_LEAF_RECT)) > 1.0e-12:
        raise BuildError("leaf crop does not include the measured 150 cm mural drop: %r" % rect)


def build_plan(input_path: Path, output_dir: Path, source_size: tuple[int, int]) -> dict:
    crop = exact_two_by_three_crop(source_size)
    rect = leaf_uv_rect(LOWERED_BACKDROP_BOTTOM_Z_CM)
    validate_pot_size(POT_SIZE)
    validate_lowered_leaf_rect(rect)
    crop_size = [crop[2] - crop[0], crop[3] - crop[1]]
    return {
        "input": str(input_path),
        "output": str(output_dir),
        "source_size_px": list(source_size),
        "crop_box_px_left_top_right_bottom": list(crop),
        "crop_size_px": crop_size,
        "crop_aspect": "2:3 exact",
        "local_stroke_edits": 0,
        "upscale": {
            "function": "Tools/FlatV3/build_scene3_backdrop.py:realesrgan_2x",
            "scale": INTERMEDIATE_SCALE,
            "intermediate_size_px": [crop_size[0] * 2, crop_size[1] * 2],
        },
        "pot_output_size_px": list(POT_SIZE),
        "leaf": {
            "backdrop_bottom_z_cm_before": ORIGINAL_BACKDROP_BOTTOM_Z_CM,
            "mural_drop_cm": MURAL_DROP_CM,
            "backdrop_bottom_z_cm_after": LOWERED_BACKDROP_BOTTOM_Z_CM,
            "center_yz_cm": list(LEAF_CENTER_YZ_CM),
            "size_yz_cm": list(LEAF_SIZE_YZ_CM),
            "uv_rect_left_top_right_bottom": rect,
            "output_size_px": list(LEAF_OUTPUT_SIZE),
        },
        "files": {
            "intermediate": str(output_dir / INTERMEDIATE_NAME),
            "backdrop_texture": str(output_dir / FINAL_NAME),
            "leaf_texture": str(output_dir / LEAF_NAME),
            "qa": str(output_dir / QA_NAME),
            "report": str(output_dir / REPORT_NAME),
        },
    }


def _production_upscale(source: np.ndarray) -> tuple[np.ndarray, dict]:
    # Import lazily: DRY and the offline harness must never initialise CUDA.
    from build_scene3_backdrop import realesrgan_2x

    return realesrgan_2x(source)


def _fit_preview(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(box, Image.Resampling.LANCZOS)
    return copy


def _qa_sheet(source: Image.Image, crop: Image.Image, up2: Image.Image, pot: Image.Image,
              crop_box: tuple[int, int, int, int], leaf_rect: list[float]) -> Image.Image:
    sheet = Image.new("RGB", (1600, 1200), (38, 41, 45))
    draw = ImageDraw.Draw(sheet)
    draw.text((30, 22), "S3 BACKDROP V3 - PAINT AS-IS / NO LOCAL STROKE EDITS", fill=(245, 245, 240))
    panels = (("SOURCE + 2:3 CROP", source), ("CROPPED", crop),
              ("REAL-ESRGAN 2x", up2), ("POT 4096x8192", pot))
    for index, (label, image) in enumerate(panels):
        col, row = index % 4, index // 4
        x0, y0 = 30 + col * 390, 70 + row * 510
        preview = _fit_preview(image, (350, 470))
        sheet.paste(preview, (x0 + (350 - preview.width) // 2, y0 + 25))
        draw.text((x0, y0), label, fill=(230, 232, 235))
    draw.text((30, 590), "crop box: %s" % (crop_box,), fill=(230, 232, 235))
    draw.text((30, 625), "leaf UV after -150 cm: " + ", ".join("%.9f" % v for v in leaf_rect),
              fill=(230, 232, 235))
    draw.text((30, 660), "final texture is deliberately non-uniform; the 20x30 m plane restores 2:3",
              fill=(230, 232, 235))
    return sheet


def _resample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, Image.Resampling.LANCZOS)


def build(input_path: Path, output_dir: Path, *,
          upscale_fn: Callable[[np.ndarray], tuple[np.ndarray, dict]] | None = None,
          test_pot_size: tuple[int, int] | None = None,
          test_leaf_size: tuple[int, int] | None = None) -> dict:
    """Run a build; non-default sizes are private seams for the tiny CPU harness."""
    source = Image.open(input_path).convert("RGB")
    if source.size != EXPECTED_SOURCE_SIZE and test_pot_size is None:
        raise BuildError("expected source 1696x2528, got %dx%d" % source.size)
    plan = build_plan(input_path.resolve(), output_dir.resolve(), source.size)
    crop_box = tuple(plan["crop_box_px_left_top_right_bottom"])
    cropped = source.crop(crop_box)
    source_array = np.asarray(cropped)
    up2_array, upscale_stats = (upscale_fn or _production_upscale)(source_array)
    expected_2x = (cropped.width * 2, cropped.height * 2)
    if (up2_array.shape[1], up2_array.shape[0]) != expected_2x:
        raise BuildError("2x upscaler returned %dx%d, expected %dx%d" %
                         (up2_array.shape[1], up2_array.shape[0], *expected_2x))
    up2 = Image.fromarray(up2_array.astype(np.uint8), "RGB")
    pot_size = test_pot_size or POT_SIZE
    leaf_size = test_leaf_size or LEAF_OUTPUT_SIZE
    pot = _resample(up2, pot_size)
    rect = plan["leaf"]["uv_rect_left_top_right_bottom"]
    leaf_box = tuple(rect[i] * pot.size[i % 2] for i in range(4))
    leaf = pot.transform(leaf_size, Image.Transform.EXTENT, leaf_box,
                         resample=Image.Resampling.BICUBIC)
    qa = _qa_sheet(source, cropped, up2, pot, crop_box, rect)

    output_dir.mkdir(parents=True, exist_ok=True)
    files = plan["files"]
    up2.save(files["intermediate"], compress_level=6)
    pot.save(files["backdrop_texture"], compress_level=6)
    leaf.save(files["leaf_texture"], compress_level=6)
    qa.save(files["qa"], compress_level=6)
    report = {
        "schema_version": 1,
        "plan": plan,
        "input_sha256": sha256(input_path),
        "upscale": upscale_stats,
        "outputs": {
            name: {"path": files[name], "sha256": sha256(Path(files[name])),
                   "size_px": list(Image.open(files[name]).size)}
            for name in ("intermediate", "backdrop_texture", "leaf_texture", "qa")
        },
        "proof": {
            "declaration_proven": [
                "The brief requires the painting to be used as-is with no local stroke edits.",
                "S3_MURAL_LOWER_2026-10-07.md declares a 150 cm mural drop from the former -5 cm bottom.",
            ],
            "measured": [
                "Input decoded at %dx%d and SHA-256 was recorded." % source.size,
                "Centred crop decoded at %dx%d, exactly 2:3." % cropped.size,
                "The existing Real-ESRGAN function returned the recorded 2x intermediate.",
                "Backdrop and lowered-mural leaf outputs decoded at the recorded sizes.",
            ],
            "inferred": [
                "The QA sheet is an offline colour/layout preview, not rendered Unreal acceptance.",
            ],
        },
    }
    Path(files["report"]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        raise BuildError("input does not exist: %s" % args.input)
    with Image.open(args.input) as source:
        if source.size != EXPECTED_SOURCE_SIZE:
            raise BuildError("expected source 1696x2528, got %dx%d" % source.size)
        plan = build_plan(args.input.resolve(), args.output.resolve(), source.size)
    if args.dry:
        print(json.dumps(plan, indent=2))
        print("S3_BACKDROP_V3_DRY_OK|mutated=0|crop=%s|pot=4096x8192" %
              ",".join(str(value) for value in plan["crop_box_px_left_top_right_bottom"]))
        return 0
    report = build(args.input, args.output)
    crop = report["plan"]["crop_box_px_left_top_right_bottom"]
    rect = report["plan"]["leaf"]["uv_rect_left_top_right_bottom"]
    print("S3_BACKDROP_V3_BUILD_OK|crop=%s|pot=4096x8192|leaf_uv=%s|local_edits=0" %
          (",".join(str(value) for value in crop), ",".join("%.9f" % value for value in rect)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
