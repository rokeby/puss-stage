#!/usr/bin/env python3
"""Build the offline Scene 3 Opal Beach backdrop source and QA package.

The source edit is deterministic and deliberately local: only manually bounded
added elements are eligible, and within those bounds only dark line strokes are
softened/broken.  Sky, sea, and unbounded beach pixels remain byte-identical.
Real-ESRGAN is loaded once and tiled, then its x4 result is resampled per tile to
the requested 2x intermediate before the non-uniform 4096x8192 POT resample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from spandrel import ModelLoader


CROP_BOX = (28, 34, 1668, 2494)  # 1640x2460, exactly 2:3 after border removal.
ASSET_NAME = "S3_OpalBeach_Backdrop"
MODEL_PATH = Path(r"D:\PussStageTools\FlatV3\models\RealESRGAN_x4plus.pth")

# Boxes are in the original Fuser image. They bound only Gary's added subjects.
ELEMENT_BOXES_SOURCE = {
    "huddle_left": (250, 1910, 735, 2305),
    "huddle_middle": (845, 1855, 1210, 2165),
    "huddle_right": (1300, 1745, 1585, 2030),
    "bones": (120, 2075, 1160, 2485),
    "cottages": (1010, 1665, 1660, 1935),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_png(path: Path, rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, "RGB").save(path, compress_level=6)


def crop_box_to_trimmed(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, _, _ = CROP_BOX
    return box[0] - left, box[1] - top, box[2] - left, box[3] - top


def clipped_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return max(0, x0), max(0, y0), min(width, x1), min(height, y1)


def soften_added_lines(source: np.ndarray, seed: int = 20261001) -> tuple[np.ndarray, np.ndarray, dict]:
    """Lighten/break dark linear marks only inside the declared element boxes."""
    height, width = source.shape[:2]
    eligible = np.zeros((height, width), np.uint8)
    for box in ELEMENT_BOXES_SOURCE.values():
        x0, y0, x1, y1 = clipped_box(crop_box_to_trimmed(box), width, height)
        cv2.rectangle(eligible, (x0, y0), (x1 - 1, y1 - 1), 255, -1)

    gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
    local_luma = cv2.GaussianBlur(gray, (0, 0), 6.0)
    relative_darkness = local_luma.astype(np.int16) - gray.astype(np.int16)
    edges = cv2.Canny(gray, 24, 68, L2gradient=True)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    dark_lines = (
        (eligible > 0)
        & (edges > 0)
        & (gray < 188)
        & (relative_darkness > 5)
    )
    dark_lines = cv2.morphologyEx(dark_lines.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) > 0

    rng = np.random.default_rng(seed)
    coarse = rng.random((max(2, height // 46), max(2, width // 46)), dtype=np.float32)
    breakup = cv2.resize(coarse, (width, height), interpolation=cv2.INTER_CUBIC)
    breakup = cv2.GaussianBlur(breakup, (0, 0), 1.1)

    wash = cv2.GaussianBlur(source, (0, 0), 4.2).astype(np.float32)
    original = source.astype(np.float32)
    line_alpha = np.zeros((height, width), np.float32)
    line_alpha[dark_lines] = 0.38
    line_alpha[dark_lines & (breakup > 0.57)] = 0.68
    line_alpha[dark_lines & (breakup < 0.31)] = 0.24
    softened = original * (1.0 - line_alpha[:, :, None]) + wash * line_alpha[:, :, None]

    # A faint pigment halo around the remaining stroke reads as a wet edge at
    # 100%, without changing any pixel outside the declared element bounds.
    line_float = dark_lines.astype(np.float32)
    halo = cv2.GaussianBlur(line_float, (0, 0), 2.1)
    halo = np.clip(halo - line_float * 0.34, 0.0, 1.0)
    halo *= (eligible > 0).astype(np.float32)
    bleed = cv2.GaussianBlur(source, (0, 0), 1.65).astype(np.float32)
    bleed_alpha = halo * 0.24
    softened = softened * (1.0 - bleed_alpha[:, :, None]) + bleed * bleed_alpha[:, :, None]
    result = np.clip(np.round(softened), 0, 255).astype(np.uint8)

    changed = np.any(result != source, axis=2)
    outside_changed = int(np.count_nonzero(changed & (eligible == 0)))
    if outside_changed != 0:
        raise RuntimeError(f"Local edit changed {outside_changed} pixels outside the declared regions")

    stats: dict[str, object] = {
        "seed": seed,
        "eligible_pixels": int(np.count_nonzero(eligible)),
        "stroke_pixels": int(np.count_nonzero(dark_lines)),
        "changed_pixels": int(np.count_nonzero(changed)),
        "outside_declared_regions_changed_pixels": outside_changed,
        "stroke_mean_luma_before": round(float(np.mean(gray[dark_lines])), 6),
        "stroke_mean_luma_after": round(float(np.mean(cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)[dark_lines])), 6),
        "method": "Canny-bounded relative-dark stroke selection; locally blurred wash replacement with deterministic broken alpha and 2.1 px wet-edge halo",
    }
    return result, dark_lines.astype(np.uint8) * 255, stats


def save_element_qa(before: np.ndarray, after: np.ndarray, stroke_mask: np.ndarray, qa_dir: Path) -> dict:
    metrics: dict[str, object] = {}
    for name, source_box in ELEMENT_BOXES_SOURCE.items():
        box = clipped_box(crop_box_to_trimmed(source_box), before.shape[1], before.shape[0])
        x0, y0, x1, y1 = box
        before_crop = before[y0:y1, x0:x1]
        after_crop = after[y0:y1, x0:x1]
        save_png(qa_dir / "elements_100pct" / f"{name}_before.png", before_crop)
        save_png(qa_dir / "elements_100pct" / f"{name}_after.png", after_crop)
        Image.fromarray(stroke_mask[y0:y1, x0:x1], "L").save(
            qa_dir / "elements_100pct" / f"{name}_stroke_mask.png", compress_level=6
        )
        changed = np.any(before_crop != after_crop, axis=2)
        metrics[name] = {
            "crop_box_trimmed_px": list(box),
            "crop_size_px": [x1 - x0, y1 - y0],
            "changed_pixels": int(np.count_nonzero(changed)),
            "changed_percent_of_crop": round(100.0 * float(np.mean(changed)), 6),
        }
    return metrics


def angular_size(size_m: float, distance_m: float) -> float:
    return math.degrees(2.0 * math.atan(size_m / (2.0 * distance_m)))


def viewing_distance_comparison(before: np.ndarray, after: np.ndarray, distance_m: float, path: Path) -> dict:
    canvas_w, canvas_h = 1600, 900
    half_w = canvas_w // 2
    hfov = 50.0
    vfov = math.degrees(2.0 * math.atan(math.tan(math.radians(hfov / 2.0)) * (canvas_h / half_w)))
    angular_w = angular_size(20.0, distance_m)
    angular_h = angular_size(30.0, distance_m)
    panel_w = max(1, round(half_w * angular_w / hfov))
    panel_h = max(1, round(canvas_h * angular_h / vfov))
    panel_w = min(panel_w, half_w)
    panel_h = min(panel_h, canvas_h)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (111, 117, 122))
    draw = ImageDraw.Draw(canvas)
    for index, (label, array) in enumerate((("BEFORE", before), ("AFTER", after))):
        panel = Image.fromarray(array, "RGB").resize((panel_w, panel_h), Image.Resampling.LANCZOS)
        x = index * half_w + (half_w - panel_w) // 2
        y = (canvas_h - panel_h) // 2
        canvas.paste(panel, (x, y))
        draw.text((index * half_w + 18, 16), f"{label}  {distance_m:.0f} m  HFOV {hfov:.0f} deg", fill=(235, 238, 240))
    canvas.save(path, compress_level=6)
    return {
        "distance_m": distance_m,
        "horizontal_fov_degrees": hfov,
        "panel_angular_width_degrees": round(angular_w, 6),
        "panel_angular_height_degrees": round(angular_h, 6),
        "panel_raster_in_half_view_px": [panel_w, panel_h],
    }


def realesrgan_2x(source: np.ndarray, tile: int = 256, pad: int = 18) -> tuple[np.ndarray, dict]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the configured Real-ESRGAN batch")
    started = time.perf_counter()
    descriptor = ModelLoader().load_from_file(MODEL_PATH).eval().to("cuda")
    load_seconds = time.perf_counter() - started
    scale = int(descriptor.scale)
    if scale != 4:
        raise RuntimeError(f"Expected x4 Real-ESRGAN descriptor, got x{scale}")

    height, width = source.shape[:2]
    output = np.empty((height * 2, width * 2, 3), np.uint8)
    tile_count = 0
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    inference_started = time.perf_counter()
    for y0 in range(0, height, tile):
        y1 = min(height, y0 + tile)
        py0, py1 = max(0, y0 - pad), min(height, y1 + pad)
        for x0 in range(0, width, tile):
            x1 = min(width, x0 + tile)
            px0, px1 = max(0, x0 - pad), min(width, x1 + pad)
            patch = source[py0:py1, px0:px1]
            tensor = torch.from_numpy(patch.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to("cuda")
            with torch.inference_mode():
                up4 = descriptor(tensor).clamp(0.0, 1.0)
            up4_array = (
                up4[0].permute(1, 2, 0).detach().cpu().numpy() * 255.0
            ).round().astype(np.uint8)
            crop_x0, crop_y0 = (x0 - px0) * scale, (y0 - py0) * scale
            crop_x1, crop_y1 = crop_x0 + (x1 - x0) * scale, crop_y0 + (y1 - y0) * scale
            interior4 = up4_array[crop_y0:crop_y1, crop_x0:crop_x1]
            interior2 = cv2.resize(interior4, ((x1 - x0) * 2, (y1 - y0) * 2), interpolation=cv2.INTER_AREA)
            output[y0 * 2:y1 * 2, x0 * 2:x1 * 2] = interior2
            tile_count += 1
            del tensor, up4, up4_array, interior4
    torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - inference_started
    peak_mib = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)
    return output, {
        "loader": "spandrel.ModelLoader",
        "architecture": str(descriptor.architecture.id),
        "model": str(MODEL_PATH),
        "model_sha256": sha256(MODEL_PATH),
        "model_load_count": 1,
        "native_model_scale": scale,
        "delivered_scale": 2,
        "tile_input_px": tile,
        "tile_pad_px": pad,
        "tile_count": tile_count,
        "device": str(next(descriptor.model.parameters()).device),
        "model_load_seconds": round(load_seconds, 6),
        "inference_seconds": round(inference_seconds, 6),
        "peak_allocated_vram_mib": round(peak_mib, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--seed", type=int, default=20261001)
    args = parser.parse_args()

    source_path = args.input.resolve()
    output = args.output.resolve()
    working = output / "working"
    qa = output / "qa"
    alternates = output / "alternates"
    for directory in (working, qa, alternates):
        directory.mkdir(parents=True, exist_ok=True)

    source_image = np.asarray(Image.open(source_path).convert("RGB"))
    x0, y0, x1, y1 = CROP_BOX
    before = source_image[y0:y1, x0:x1].copy()
    if before.shape[1] * 3 != before.shape[0] * 2:
        raise RuntimeError(f"Trimmed crop is not exactly 2:3: {before.shape[1]}x{before.shape[0]}")
    after, stroke_mask, local_stats = soften_added_lines(before, args.seed)

    save_png(working / "S3_OpalBeach_trimmed_2x3_before.png", before)
    save_png(working / "S3_OpalBeach_trimmed_2x3_watercolourized.png", after)
    Image.fromarray(stroke_mask, "L").save(qa / "localized_dark_strokes.png", compress_level=6)
    element_stats = save_element_qa(before, after, stroke_mask, qa)
    distance_stats = [
        viewing_distance_comparison(before, after, distance, qa / f"viewing_distance_{int(distance)}m_before_after.png")
        for distance in (65.0, 81.0)
    ]

    source_dir = source_path.parent
    alternate_records = []
    for name in ("shore_out1.jpg", "shore_out2.jpg"):
        alternate_source = source_dir / name
        if alternate_source.is_file():
            alternate_target = alternates / name
            shutil.copy2(alternate_source, alternate_target)
            alternate_records.append({"file": str(alternate_target), "sha256": sha256(alternate_target)})

    report: dict[str, object] = {
        "schema_version": 1,
        "asset": ASSET_NAME,
        "proof": {
            "declaration_proven": [
                "Gary accepted shore_out3 portrait.jpg as the Scene 3 backdrop input (task declaration).",
                "The task and FUSER_EDIT.md identify Whistler's Opal Beach source as Smithsonian CC0; this offline run did not re-query the institution.",
            ],
            "measured": [],
            "inferred": [
                "The localized line treatment reads more like loose watercolour; final artistic acceptance remains Gary's.",
                "The offline previews approximate distance and neutral cool daylight; they are not Unreal rendered acceptance.",
            ],
        },
        "input": {
            "file": str(source_path),
            "sha256": sha256(source_path),
            "size_px": [int(source_image.shape[1]), int(source_image.shape[0])],
        },
        "crop": {
            "source_box_px_left_top_right_bottom": list(CROP_BOX),
            "trim_px_left_top_right_bottom": [x0, y0, source_image.shape[1] - x1, source_image.shape[0] - y1],
            "output_size_px": [int(before.shape[1]), int(before.shape[0])],
            "aspect": "2:3 exact",
        },
        "localized_treatment": local_stats,
        "element_qa": element_stats,
        "distance_qa": distance_stats,
        "alternates": alternate_records,
    }

    if not args.local_only:
        up2, upscale_stats = realesrgan_2x(after)
        up2_path = working / "S3_OpalBeach_watercolourized_RealESRGAN_2x.png"
        save_png(up2_path, up2)
        pot = cv2.resize(up2, (4096, 8192), interpolation=cv2.INTER_LANCZOS4)
        pot_path = working / "S3_OpalBeach_Backdrop_POT_4096x8192.png"
        save_png(pot_path, pot)
        mask = Image.new("L", (2048, 4096), 255)
        mask_path = working / "S3_OpalBeach_Backdrop_full_mask_2048x4096.png"
        mask.save(mask_path, compress_level=6)
        report["upscale"] = upscale_stats
        report["upscale"]["input_size_px"] = [int(after.shape[1]), int(after.shape[0])]
        report["upscale"]["output_2x_size_px"] = [int(up2.shape[1]), int(up2.shape[0])]
        report["pot_resample"] = {
            "input_file": str(up2_path),
            "output_file": str(pot_path),
            "output_size_px": [4096, 8192],
            "method": "OpenCV Lanczos4 non-uniform resample; the 20x30 m plane UV 0-1 restores 2:3 display aspect",
            "wall_size_mm": [20000.0, 30000.0],
            "effective_mm_per_pixel": [round(20000.0 / 4096.0, 6), round(30000.0 / 8192.0, 6)],
        }
        report["skin_input_mask"] = {"file": str(mask_path), "size_px": [2048, 4096], "coverage_percent": 100.0}
        report["proof"]["measured"] = [
            f"Input decoded at {source_image.shape[1]}x{source_image.shape[0]} and SHA-256 was recorded.",
            f"Border trim produced {before.shape[1]}x{before.shape[0]}, exactly 2:3.",
            f"Localized treatment changed zero pixels outside the declared added-element regions.",
            f"Real-ESRGAN model loaded once, emitted a 2x intermediate, and POT output decoded at 4096x8192.",
            "At 20x30 m the POT colour density is 4.882812 mm/px horizontally and 3.662109 mm/px vertically.",
        ]
    else:
        report["proof"]["measured"] = [
            f"Input decoded at {source_image.shape[1]}x{source_image.shape[0]} and SHA-256 was recorded.",
            f"Border trim produced {before.shape[1]}x{before.shape[0]}, exactly 2:3.",
            f"Localized treatment changed zero pixels outside the declared added-element regions.",
        ]

    (output / "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"LOCAL_EDIT_OK|changed={local_stats['changed_pixels']}|outside=0")
    print(f"CROP_OK|size={before.shape[1]}x{before.shape[0]}|aspect=2:3")
    if not args.local_only:
        print(f"REAL_ESRGAN_OK|loads=1|size={up2.shape[1]}x{up2.shape[0]}")
        print("POT_OK|size=4096x8192|mm_per_px=4.882812,3.662109")


if __name__ == "__main__":
    main()
