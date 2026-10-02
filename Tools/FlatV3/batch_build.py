#!/usr/bin/env python3
"""Offline, resumable Flat V3 overnight batch builder.

This is the only supervising process for the batch.  It performs local colour-
key cutouts, physical-scale jigsaw cleanup, colour bleed, one-load Real-ESRGAN
2x upscaling, skin/back processing, Blender 4.4 builds, clean re-import
validation, two-view contact rendering, and final reports.  It never calls the
network, image generation, or Unreal.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gc
import hashlib
import html
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Lock all model consumers to the already-installed local caches.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("PYTHONNOUSERSITE", "1")

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from spandrel import ModelLoader


PROJECT = Path(__file__).resolve().parents[2]
TOOLS = PROJECT / "Tools" / "FlatV3"
DERIVED = PROJECT / "DerivedAssets" / "FlatV3"
QUEUE = DERIVED / "FuserQueue"
PICKS_PATH = QUEUE / "BUILD_PICKS.json"
OUT = DERIVED / "Overnight"
SHARED = OUT / "shared"
FLATS = OUT / "flats"
LOGS = OUT / "logs"
GPU_MARKER = DERIVED / "Overnight" / "RUNNING.json"
TEXTURE_ROOT = PROJECT / "DerivedAssets" / "TextureLibrary"
PAPER_DISP = TEXTURE_ROOT / "Paper" / "Paper003" / "Paper003_4K-JPG_Displacement.jpg"
PAPER_ROUGH = TEXTURE_ROOT / "Paper" / "Paper003" / "Paper003_4K-JPG_Roughness.jpg"
MODEL = Path(r"D:\PussStageTools\FlatV3\models\RealESRGAN_x4plus.pth")
SAM_MODEL = Path(r"D:\PussStageTools\FlatV3\models\sam2.1_hiera_large.pt")
SAM_CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
VENV_PYTHON = Path(r"D:\PussStageTools\FlatV3\venv\Scripts\python.exe")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe")
BUILD_SKIN = TOOLS / "build_skin.py"
BUILD_FLAT = TOOLS / "build_v3_flat.py"
UV_AUDIT_AFTER = DERIVED / "uv_axis_audit_after.json"
BG_RGB = np.asarray((0xD6, 0xC8, 0xAA), dtype=np.uint8)
SCHEMA = 1
WAVE_WIDTH_CM = 1250.0
BAKE_POLES_BY_DEFAULT = True
SEGMENT_MAX = 1280


def configure_batch_paths(picks_path: Path, output_path: Path) -> None:
    global PICKS_PATH, OUT, SHARED, FLATS, LOGS
    PICKS_PATH = picks_path.resolve()
    OUT = output_path.resolve()
    SHARED = OUT / "shared"
    FLATS = OUT / "flats"
    LOGS = OUT / "logs"


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def save_png(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), array, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
        raise RuntimeError(f"Could not write {path}")


def read_rgb(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def read_rgb_and_alpha(path: Path) -> tuple[np.ndarray, np.ndarray]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    if image.ndim != 3 or image.shape[2] != 4:
        raise RuntimeError(f"Embedded-alpha cut requested but source is not RGBA: {path}")
    rgb = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB)
    alpha = image[:, :, 3]
    if int(alpha.min()) == 255 or int(alpha.max()) == 0:
        raise RuntimeError(f"Embedded alpha is not a usable cut mask: {path}")
    return rgb, alpha


def embedded_alpha_cut(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    rgb, alpha = read_rgb_and_alpha(path)
    mask = alpha >= 128
    if not mask.any():
        raise RuntimeError(f"Embedded alpha threshold produced an empty cut: {path}")
    return rgb, mask, {
        "method": "existing embedded alpha thresholded at 128; no segmentation, colour key, or SAM",
        "alpha_threshold": 128,
        "alpha_min": int(alpha.min()),
        "alpha_max": int(alpha.max()),
        "foreground_percent_before_jigsaw": round(float(mask.mean() * 100.0), 6),
    }


def contract_alpha_one_pixel(alpha: np.ndarray) -> np.ndarray:
    """Move a matte edge inward by one source pixel without binarising it."""
    return cv2.erode(
        np.asarray(alpha, np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )


def border_samples(rgb: np.ndarray) -> tuple[np.ndarray, int]:
    height, width = rgb.shape[:2]
    border = max(8, min(height, width) // 90)
    samples = np.concatenate(
        (
            rgb[:border].reshape(-1, 3), rgb[-border:].reshape(-1, 3),
            rgb[:, :border].reshape(-1, 3), rgb[:, -border:].reshape(-1, 3),
        ), axis=0,
    )
    return samples, border


def spatial_basis(height: int, width: int) -> np.ndarray:
    """Quadratic field used to model generated studio-background falloff."""
    yy, xx = np.mgrid[-1.0:1.0:complex(0, height), -1.0:1.0:complex(0, width)]
    return np.stack(
        (np.ones_like(xx), xx, yy, xx * xx, xx * yy, yy * yy), axis=2
    ).astype(np.float32)


def adaptive_background_lab(rgb: np.ndarray, border: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Fit a robust quadratic LAB field from the clear four-sided border."""
    height, width = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    basis = spatial_basis(height, width)
    border_mask = np.zeros((height, width), dtype=bool)
    border_mask[:border] = True; border_mask[-border:] = True
    border_mask[:, :border] = True; border_mask[:, -border:] = True
    design = basis[border_mask]
    observed = lab[border_mask]
    keep = np.ones(len(observed), dtype=bool)
    coefficients = np.zeros((basis.shape[2], 3), dtype=np.float32)
    for _ in range(4):
        coefficients = np.linalg.lstsq(design[keep], observed[keep], rcond=None)[0].astype(np.float32)
        residual = np.linalg.norm(observed - design @ coefficients, axis=1)
        median = float(np.median(residual[keep]))
        mad = float(np.median(np.abs(residual[keep] - median)))
        cutoff = max(2.5, median + 4.5 * max(mad, 0.25))
        revised = residual <= cutoff
        if int(revised.sum()) < max(200, int(0.70 * len(observed))):
            break
        keep = revised
    model = np.clip(basis @ coefficients, 0, 255).astype(np.float32)
    residual = np.linalg.norm(lab - model, axis=2)
    border_residual = residual[border_mask]
    model_rgb = cv2.cvtColor(np.clip(model, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    centre = model[height // 2, width // 2]
    corners = model[[0, 0, height - 1, height - 1], [0, width - 1, 0, width - 1]]
    return model, {
        "lab": lab,
        "rgb": model_rgb,
        "residual": residual,
        "border_mask": border_mask,
        "border_residual": border_residual,
        "fit_inlier_percent": round(float(keep.mean() * 100.0), 6),
        "model_centre_lab": [round(float(value), 3) for value in centre],
        "model_corner_lab": [[round(float(value), 3) for value in row] for row in corners],
        "model_span_lab": round(float(np.max(np.linalg.norm(model - centre, axis=2))), 6),
    }


def matte_gate(alpha: np.ndarray, border: int, path: Path, label: str) -> dict[str, Any]:
    foreground = alpha >= 128
    coverage = float(foreground.mean())
    if not 0.01 < coverage < 0.95:
        raise RuntimeError(f"{label} matte has implausible foreground coverage {coverage:.6f}: {path}")
    border_alpha = np.concatenate(
        (alpha[:border].ravel(), alpha[-border:].ravel(), alpha[:, :border].ravel(), alpha[:, -border:].ravel())
    )
    border_opaque_fraction = float((border_alpha >= 8).mean())
    if border_opaque_fraction > 0.01:
        raise RuntimeError(
            f"{label} matte left {border_opaque_fraction:.4%} non-transparent border pixels: {path}"
        )
    return {
        "foreground_percent": round(coverage * 100.0, 6),
        "border_nontransparent_percent": round(border_opaque_fraction * 100.0, 6),
        "pass": True,
    }


class SAMChromaRefiner:
    """One-load, offline SAM 2.1 box/point refiner for ambiguous chroma cuts."""

    def __init__(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the declared SAM chroma refinement")
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        started = time.perf_counter()
        model = build_sam2(SAM_CONFIG, str(SAM_MODEL), device="cuda")
        self.predictor = SAM2ImagePredictor(model)
        self.model = model
        self.setup_seconds = round(time.perf_counter() - started, 4)
        self.calls = 0

    def refine(self, rgb: np.ndarray, adaptive_alpha: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        height, width = rgb.shape[:2]
        scale = min(1.0, SEGMENT_MAX / max(height, width))
        seg_w = max(1, int(round(width * scale))); seg_h = max(1, int(round(height * scale)))
        seg_rgb = cv2.resize(rgb, (seg_w, seg_h), interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb
        seg_alpha = cv2.resize(adaptive_alpha, (seg_w, seg_h), interpolation=cv2.INTER_AREA)
        coarse = seg_alpha >= 128
        count, labels, component_stats, _ = cv2.connectedComponentsWithStats(coarse.astype(np.uint8), 8)
        components = [index for index in range(1, count) if component_stats[index, cv2.CC_STAT_AREA] >= max(12, int(coarse.size * 0.0003))]
        if not components:
            raise RuntimeError("Adaptive chroma matte provided no SAM prompt components")
        prompt_mask = np.isin(labels, components)
        ys, xs = np.where(prompt_mask)
        pad = max(3, int(round(0.015 * max(seg_h, seg_w))))
        box = np.asarray(
            [max(0, xs.min() - pad), max(0, ys.min() - pad), min(seg_w - 1, xs.max() + pad), min(seg_h - 1, ys.max() + pad)],
            dtype=np.float32,
        )
        positives: list[tuple[float, float]] = []
        for component in sorted(components, key=lambda index: int(component_stats[index, cv2.CC_STAT_AREA]), reverse=True)[:8]:
            component_mask = labels == component
            distance = cv2.distanceTransform(component_mask.astype(np.uint8), cv2.DIST_L2, 5)
            py, px = np.unravel_index(int(np.argmax(distance)), distance.shape)
            positives.append((float(px), float(py)))
        negatives = [
            (1.0, 1.0), (float(seg_w - 2), 1.0),
            (1.0, float(seg_h - 2)), (float(seg_w - 2), float(seg_h - 2)),
        ]
        # Preserve substantial see-through holes by explicitly prompting them as background.
        enclosed = (~coarse).astype(np.uint8)
        flood = enclosed.copy()
        mask = np.zeros((seg_h + 2, seg_w + 2), np.uint8)
        cv2.floodFill(flood, mask, (0, 0), 2)
        holes = flood == 1
        hole_count, hole_labels, hole_stats, _ = cv2.connectedComponentsWithStats(holes.astype(np.uint8), 8)
        for component in range(1, hole_count):
            if hole_stats[component, cv2.CC_STAT_AREA] < max(20, int(coarse.size * 0.0005)):
                continue
            distance = cv2.distanceTransform((hole_labels == component).astype(np.uint8), cv2.DIST_L2, 5)
            py, px = np.unravel_index(int(np.argmax(distance)), distance.shape)
            negatives.append((float(px), float(py)))
        points = np.asarray(positives + negatives, dtype=np.float32)
        labels_prompt = np.asarray([1] * len(positives) + [0] * len(negatives), dtype=np.int32)
        self.predictor.set_image(seg_rgb)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            candidates, scores, _ = self.predictor.predict(
                point_coords=points, point_labels=labels_prompt, box=box, multimask_output=True
            )
        core = seg_alpha >= 224
        ranked: list[tuple[float, int, dict[str, Any]]] = []
        for index, candidate in enumerate(candidates.astype(bool)):
            intersection = float(np.logical_and(candidate, coarse).sum())
            union = float(np.logical_or(candidate, coarse).sum())
            iou = intersection / max(1.0, union)
            core_recall = float(np.logical_and(candidate, core).sum()) / max(1.0, float(core.sum()))
            border_fraction = float(np.concatenate((candidate[0], candidate[-1], candidate[:, 0], candidate[:, -1])).mean())
            area_ratio = float(candidate.mean() / max(1e-6, coarse.mean()))
            rank = 2.0 * iou + core_recall + float(scores[index]) - 3.0 * border_fraction - 0.35 * abs(math.log(max(area_ratio, 1e-6)))
            ranked.append((rank, index, {
                "sam_score": round(float(scores[index]), 6), "coarse_iou": round(iou, 6),
                "adaptive_core_recall": round(core_recall, 6), "border_fraction": round(border_fraction, 6),
                "area_ratio_to_adaptive": round(area_ratio, 6), "rank": round(rank, 6),
            }))
        _, chosen_index, chosen_stats = max(ranked, key=lambda value: value[0])
        chosen = candidates[chosen_index].astype(bool)
        if chosen_stats["coarse_iou"] < 0.45 or chosen_stats["border_fraction"] > 0.01:
            raise RuntimeError(f"SAM chroma refinement failed overlap/border gate: {chosen_stats}")
        # Fire, smoke and pale timber can be several semantic objects even
        # though the flat needs one matte. SAM owns the ambiguous boundary, but
        # must not discard high-confidence adaptive-key pixels such as painted
        # flames. Union only that >=224 core when SAM recall is incomplete.
        core_union_used = chosen_stats["adaptive_core_recall"] < 0.90
        if core_union_used:
            chosen = np.logical_or(chosen, core)
        final_core_recall = float(np.logical_and(chosen, core).sum()) / max(1.0, float(core.sum()))
        full = cv2.resize(chosen.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)
        soft = cv2.GaussianBlur((full * 255).astype(np.uint8), (0, 0), sigmaX=0.65, sigmaY=0.65)
        alpha = contract_alpha_one_pixel(soft)
        self.calls += 1
        return alpha, {
            "used": True,
            "checkpoint": str(SAM_MODEL),
            "config": SAM_CONFIG,
            "setup_seconds": self.setup_seconds,
            "segmentation_size_px": [seg_w, seg_h],
            "prompt_box_xyxy": [round(float(value), 3) for value in box],
            "positive_point_count": len(positives),
            "negative_point_count": len(negatives),
            "candidate_count": int(len(candidates)),
            "chosen_candidate": int(chosen_index),
            "chosen": chosen_stats,
            "adaptive_core_union_used": core_union_used,
            "final_adaptive_core_recall": round(final_core_recall, 6),
        }

    def close(self) -> None:
        del self.predictor, self.model
        gc.collect()
        torch.cuda.empty_cache()


def chroma_alpha_cut(
    path: Path, sam_refiner: SAMChromaRefiner | None = None
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Recover a matte from an adaptive falloff model, optionally refined by SAM."""
    rgb = read_rgb(path)
    samples, border = border_samples(rgb)
    key_rgb = np.median(samples, axis=0)
    _, background = adaptive_background_lab(rgb, border)
    distance = background["residual"]
    border_distance = background["border_residual"]
    transparent_distance = float(np.clip(np.quantile(border_distance, 0.995) + 1.0, 3.5, 18.0))
    opaque_distance = transparent_distance + 12.0
    alpha_f = np.clip((distance - transparent_distance) / (opaque_distance - transparent_distance), 0.0, 1.0)
    alpha_f = cv2.GaussianBlur(alpha_f.astype(np.float32), (0, 0), sigmaX=0.55, sigmaY=0.55)
    adaptive_alpha = contract_alpha_one_pixel(np.clip(np.rint(alpha_f * 255.0), 0, 255).astype(np.uint8))
    adaptive_gate = matte_gate(adaptive_alpha, border, path, "Adaptive chroma")

    transition = (adaptive_alpha > 0) & (adaptive_alpha < 255)
    foreground = adaptive_alpha >= 128
    contact_band = cv2.dilate(foreground.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    ambiguous_contact_percent = float(np.logical_and(transition, contact_band).mean() * 100.0)
    declared_key_distance_rgb = float(np.linalg.norm(key_rgb.astype(np.float32) - BG_RGB.astype(np.float32)))
    falloff_touches_subject = bool(
        declared_key_distance_rgb < 45.0 and ambiguous_contact_percent > 0.002
    )
    sam_stats: dict[str, Any] = {
        "used": False,
        "triggered": falloff_touches_subject,
        "reason": "preflight has no GPU model" if falloff_touches_subject and sam_refiner is None else "not required",
    }
    alpha = adaptive_alpha
    if falloff_touches_subject and sam_refiner is not None:
        alpha, sam_stats = sam_refiner.refine(rgb, adaptive_alpha)
        sam_stats["triggered"] = True
    final_gate = matte_gate(alpha, border, path, "Final chroma")

    # Generic colour despill: push only soft-edge pixels a short distance away
    # from the locally predicted background colour. This works for the P03 beige
    # field and the older magenta plates without hard-coding either hue.
    rgb_f = rgb.astype(np.float32)
    bg_rgb = background["rgb"].astype(np.float32)
    edge = (alpha > 0) & (alpha < 255)
    edge_weight = np.zeros(alpha.shape, dtype=np.float32)
    edge_weight[edge] = np.sqrt(1.0 - alpha[edge].astype(np.float32) / 255.0) * 0.32
    despilled = np.clip(rgb_f + (rgb_f - bg_rgb) * edge_weight[:, :, None], 0, 255).astype(np.uint8)
    before_edge_distance = float(np.linalg.norm(rgb_f - bg_rgb, axis=2)[edge].mean()) if edge.any() else 0.0
    after_edge_distance = float(np.linalg.norm(despilled.astype(np.float32) - bg_rgb, axis=2)[edge].mean()) if edge.any() else 0.0
    despill_pass = after_edge_distance + 1e-4 >= before_edge_distance
    if not despill_pass:
        raise RuntimeError(f"Adaptive chroma despill moved edge pixels toward the key: {path}")

    return despilled, alpha, {
        "method": "robust quadratic LAB background field; adaptive soft matte; conditional SAM 2.1 refinement; generic local despill; one-source-pixel contract",
        "key_detection": "median RGB plus robust quadratic LAB field fitted from the clear four-sided border",
        "border_width_px": border,
        "detected_key_rgb": [round(float(value), 3) for value in key_rgb],
        "declared_key_rgb": BG_RGB.tolist(),
        "transparent_lab_distance": round(transparent_distance, 4),
        "opaque_lab_distance": round(opaque_distance, 4),
        "background_fit_inlier_percent": background["fit_inlier_percent"],
        "background_model_span_lab": background["model_span_lab"],
        "background_model_centre_lab": background["model_centre_lab"],
        "background_model_corner_lab": background["model_corner_lab"],
        "declared_key_distance_rgb": round(declared_key_distance_rgb, 6),
        "falloff_touches_subject": falloff_touches_subject,
        "ambiguous_contact_percent": round(ambiguous_contact_percent, 6),
        "adaptive_gate": adaptive_gate,
        "sam_refinement": sam_stats,
        "final_coverage_gate": final_gate,
        "contract_px_at_source_resolution": 1,
        "alpha_levels": int(len(np.unique(alpha))),
        "soft_alpha_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
        "foreground_percent_before_jigsaw": final_gate["foreground_percent"],
        "border_nontransparent_percent": final_gate["border_nontransparent_percent"],
        "edge_background_distance_before": round(before_edge_distance, 6),
        "edge_background_distance_after": round(after_edge_distance, 6),
        "despill_pass": despill_pass,
    }


def opacity_mask_cut(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Recover the old Unreal opacity mask from an RGBA texture export."""
    rgb, source_alpha = read_rgb_and_alpha(path)
    alpha = contract_alpha_one_pixel(source_alpha)
    coverage = float((alpha >= 128).mean())
    soft_pixels = int(((source_alpha > 0) & (source_alpha < 255)).sum())
    if soft_pixels == 0 or not 0.01 < coverage < 0.95:
        raise RuntimeError(f"Exported opacity mask is not a usable soft matte: {path}")
    samples, border = border_samples(rgb)
    del samples
    border_alpha = np.concatenate(
        (alpha[:border].ravel(), alpha[-border:].ravel(), alpha[:, :border].ravel(), alpha[:, -border:].ravel())
    )
    border_opaque_fraction = float((border_alpha >= 8).mean())
    if border_opaque_fraction > 0.01:
        raise RuntimeError(
            f"Exported opacity mask left {border_opaque_fraction:.4%} non-transparent border pixels: {path}"
        )
    return rgb, alpha, {
        "method": "old Unreal texture-export alpha channel recovered as the opacity mask; one-source-pixel contract",
        "opacity_mask_source": str(path),
        "opacity_mask_channel": "A",
        "source_alpha_min": int(source_alpha.min()),
        "source_alpha_max": int(source_alpha.max()),
        "source_alpha_levels": int(len(np.unique(source_alpha))),
        "source_soft_alpha_pixels": soft_pixels,
        "contract_px_at_source_resolution": 1,
        "foreground_percent_before_jigsaw": round(coverage * 100.0, 6),
        "border_nontransparent_percent": round(border_opaque_fraction * 100.0, 6),
        "old_unreal_opacity_mask_validation_pass": True,
        "sam_fallback_used": False,
        "manual_review_flag": "SET01_L matte recovered from the old Unreal texture-export alpha, not chroma-keyed",
    }


def write_rgb(path: Path, rgb: np.ndarray) -> None:
    save_png(path, cv2.cvtColor(np.asarray(rgb, np.uint8), cv2.COLOR_RGB2BGR))


def write_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    rgba = np.dstack((np.asarray(rgb, np.uint8), np.asarray(alpha, np.uint8)))
    save_png(path, cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count <= 1:
        raise RuntimeError("Colour key produced no foreground component")
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == index


def colour_key(rgb: np.ndarray, target_height_cm: float) -> tuple[np.ndarray, dict[str, Any]]:
    """Extract the generated flat from its nominal #D6C8AA field."""
    h, w = rgb.shape[:2]
    border = max(8, min(h, w) // 90)
    samples = np.concatenate(
        (
            rgb[:border].reshape(-1, 3), rgb[-border:].reshape(-1, 3),
            rgb[:, :border].reshape(-1, 3), rgb[:, -border:].reshape(-1, 3),
        ), axis=0,
    )
    declared = BG_RGB.astype(np.float32)
    sample_distance = np.linalg.norm(samples.astype(np.float32) - declared, axis=1)
    close_samples = samples[sample_distance < 38.0]
    estimated = np.median(close_samples if len(close_samples) > 200 else samples, axis=0)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    bg_lab = cv2.cvtColor(np.uint8([[estimated]]), cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0]
    distance = np.linalg.norm(lab - bg_lab, axis=2)
    border_distance = np.concatenate(
        (distance[:border].ravel(), distance[-border:].ravel(), distance[:, :border].ravel(), distance[:, -border:].ravel())
    )
    # Generated brushwork can touch the frame and contaminate the border sample.
    # Cap the key before pale cloud/wave paint fragments into separate islands.
    threshold = float(np.clip(np.quantile(border_distance, 0.975) + 3.0, 8.0, 18.0))
    mask = distance > threshold
    # Retain one physical mass.  The following jigsaw pass, not the colour key,
    # owns the 3 cm feature cleanup; doing it here can sever pale wave joins.
    mask = largest_component(mask)
    return mask, {
        "method": "local LAB colour key against the generated flat field; largest connected subject retained",
        "declared_background_rgb": BG_RGB.tolist(),
        "estimated_background_rgb": [round(float(value), 3) for value in estimated],
        "lab_threshold": round(threshold, 4),
        "foreground_percent_before_jigsaw": round(float(mask.mean() * 100.0), 6),
    }


def jigsaw(mask: np.ndarray, target_height_cm: float) -> tuple[np.ndarray, dict[str, Any]]:
    rows = np.flatnonzero(mask.any(axis=1))
    if not len(rows):
        raise RuntimeError("Empty cutout")
    subject_h = int(rows[-1] - rows[0] + 1)
    px_per_cm = subject_h / target_height_cm
    min_feature_px = max(1, int(round(3.0 * px_per_cm)))
    radius = max(1, min_feature_px // 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    cleaned = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
    sigma = max(0.65, 0.75 * px_per_cm)
    smoothed = cv2.GaussianBlur(cleaned.astype(np.float32), (0, 0), sigmaX=sigma, sigmaY=sigma) >= 0.5
    smoothed = largest_component(smoothed)
    return smoothed, {
        "minimum_feature_cm": 3.0,
        "minimum_feature_px": min_feature_px,
        "smoothing_sigma_px": round(float(sigma), 4),
        "foreground_percent_after_jigsaw": round(float(smoothed.mean() * 100.0), 6),
    }


def crop_with_bleed_margin(rgb: np.ndarray, mask: np.ndarray, height_cm: float) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    ys, xs = np.where(mask)
    subject_h = int(ys.max() - ys.min() + 1)
    px_per_cm = subject_h / height_cm
    margin = max(8, int(math.ceil(7.0 * px_per_cm)))
    x0, x1 = max(0, int(xs.min()) - margin), min(mask.shape[1], int(xs.max()) + margin + 1)
    y0, y1 = max(0, int(ys.min()) - margin), min(mask.shape[0], int(ys.max()) + margin + 1)
    return rgb[y0:y1, x0:x1].copy(), mask[y0:y1, x0:x1].copy(), {
        "crop_xyxy": [x0, y0, x1, y1], "margin_px": margin, "px_per_cm": round(px_per_cm, 6)
    }


def colour_bleed(rgb: np.ndarray, mask: np.ndarray, height_cm: float) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    ys = np.flatnonzero(mask.any(axis=1))
    px_per_cm = len(ys) / height_cm
    bleed_px = max(2, int(round(5.0 * px_per_cm)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bleed_px * 2 + 1, bleed_px * 2 + 1))
    bleed_mask = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)
    _, indices = ndimage.distance_transform_edt(~mask, return_indices=True)
    nearest = rgb[indices[0], indices[1]]
    output = np.broadcast_to(BG_RGB, rgb.shape).copy()
    output[bleed_mask] = nearest[bleed_mask]
    output[mask] = rgb[mask]
    return output, bleed_mask, {"bleed_cm": 5.0, "bleed_px": bleed_px}


def repeat_wave(rgb: np.ndarray, mask: np.ndarray, height_cm: float, phase: float) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Make one >=12 m row half from a phase-shifted stretch of the source."""
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    tile_rgb, tile_mask = rgb[y0:y1, x0:x1].copy(), mask[y0:y1, x0:x1].copy()
    tile_h, tile_w = tile_mask.shape
    wanted = int(math.ceil(tile_h * WAVE_WIDTH_CM / height_cm))
    overlap = max(8, int(tile_w * 0.08))
    step = max(1, tile_w - overlap)
    repeats = int(math.ceil((wanted + tile_w) / step)) + 1
    long_w = tile_w + (repeats - 1) * step
    accum = np.zeros((tile_h, long_w, 3), np.float32)
    weight = np.zeros((tile_h, long_w), np.float32)
    alpha_accum = np.zeros((tile_h, long_w), np.float32)
    for index in range(repeats):
        segment_rgb = tile_rgb if index % 2 == 0 else tile_rgb[:, ::-1]
        segment_mask = tile_mask if index % 2 == 0 else tile_mask[:, ::-1]
        local_weight = segment_mask.astype(np.float32)
        if overlap and index:
            local_weight[:, :overlap] *= np.linspace(0.0, 1.0, overlap, dtype=np.float32)[None, :]
        if overlap and index < repeats - 1:
            local_weight[:, -overlap:] *= np.linspace(1.0, 0.0, overlap, dtype=np.float32)[None, :]
        start = index * step
        accum[:, start:start + tile_w] += segment_rgb.astype(np.float32) * local_weight[:, :, None]
        weight[:, start:start + tile_w] += local_weight
        alpha_accum[:, start:start + tile_w] = np.maximum(alpha_accum[:, start:start + tile_w], segment_mask)
    safe = np.maximum(weight, 1.0)
    long_rgb = np.clip(accum / safe[:, :, None], 0, 255).astype(np.uint8)
    long_mask = alpha_accum >= 0.5
    # The painted bottom rail must remain one connected card through cross-fades.
    rail = max(2, int(round(tile_h * 0.018)))
    long_mask[-rail:, :] = True
    for row in range(tile_h - rail, tile_h):
        missing = weight[row] <= 0
        long_rgb[row, missing] = np.median(tile_rgb[-rail:].reshape(-1, 3), axis=0)
    offset = int(round(phase * step))
    if offset + wanted > long_w:
        offset = max(0, long_w - wanted)
    return long_rgb[:, offset:offset + wanted], long_mask[:, offset:offset + wanted], {
        "minimum_width_cm": 1200.0,
        "authored_width_cm": WAVE_WIDTH_CM,
        "source_stretch_offset_px": offset,
        "source_phase": phase,
        "crossfade_overlap_px": overlap,
        "repeat_count": repeats,
    }


class Upscaler:
    def __init__(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the Real-ESRGAN overnight batch")
        self.model = ModelLoader().load_from_file(MODEL).eval().to("cuda")
        self.loads = 1
        if int(self.model.scale) != 4:
            raise RuntimeError(f"Expected x4 Real-ESRGAN descriptor, got x{self.model.scale}")

    def _tile(self, rgb: np.ndarray, tile: int = 320, overlap: int = 24) -> np.ndarray:
        h, w = rgb.shape[:2]
        scale = int(self.model.scale)
        output = np.zeros((h * scale, w * scale, 3), dtype=np.uint8)
        step = tile - overlap * 2
        ys, xs = list(range(0, h, step)), list(range(0, w, step))
        for core_y0 in ys:
            core_y1 = min(h, core_y0 + step)
            in_y0, in_y1 = max(0, core_y0 - overlap), min(h, core_y1 + overlap)
            for core_x0 in xs:
                core_x1 = min(w, core_x0 + step)
                in_x0, in_x1 = max(0, core_x0 - overlap), min(w, core_x1 + overlap)
                patch = rgb[in_y0:in_y1, in_x0:in_x1]
                tensor = torch.from_numpy(patch.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to("cuda")
                with torch.inference_mode():
                    result = self.model(tensor).clamp(0, 1)
                data = (result[0].permute(1, 2, 0).detach().cpu().numpy() * 255.0).round().astype(np.uint8)
                sx0, sy0 = (core_x0 - in_x0) * scale, (core_y0 - in_y0) * scale
                sx1, sy1 = sx0 + (core_x1 - core_x0) * scale, sy0 + (core_y1 - core_y0) * scale
                output[core_y0 * scale:core_y1 * scale, core_x0 * scale:core_x1 * scale] = data[sy0:sy1, sx0:sx1]
                del tensor, result, data
        return output

    def two_x(self, rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        started = time.perf_counter()
        torch.cuda.reset_peak_memory_stats()
        up4 = self._tile(rgb)
        up2 = cv2.resize(up4, (rgb.shape[1] * 2, rgb.shape[0] * 2), interpolation=cv2.INTER_AREA)
        del up4
        torch.cuda.empty_cache()
        return up2, {
            "model": str(MODEL), "model_sha256": sha256(MODEL), "model_load_ordinal": 1,
            "native_size_px": [rgb.shape[1], rgb.shape[0]], "output_size_px": [up2.shape[1], up2.shape[0]],
            "method": "RealESRGAN_x4plus inference, Lanczos/area-resampled to the requested exact 2x output",
            "seconds": round(time.perf_counter() - started, 3),
            "peak_vram_mib": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 3),
        }


@dataclass
class WorkItem:
    source: Path
    passage: str
    height_cm: float
    source_side: str
    build_side: str
    asset_suffix: str
    mount: str
    kind: str
    minimum_width_m: float = 0.0
    phase: float | None = None
    pick: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    cut_method: str = "colour_key"

    @property
    def asset_name(self) -> str:
        return "SM_FlatV3_" + self.asset_suffix

    @property
    def folder(self) -> Path:
        return FLATS / self.asset_suffix

    @property
    def log(self) -> Path:
        return LOGS / f"{self.asset_suffix}.log"

    @property
    def bake_poles(self) -> bool:
        return bool(
            BAKE_POLES_BY_DEFAULT
            and self.kind == "flat"
            and self.mount == "wing"
            and self.source_side in {"L", "R"}
        )


def preliminary_backbone(path: Path, height_cm: float) -> tuple[str | None, dict[str, Any]]:
    rgb = read_rgb(path)
    mask, key = colour_key(rgb, height_cm)
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    bbox = mask[y0:y1 + 1, x0:x1 + 1]
    rectangularity = float(bbox.mean())
    left, right = [], []
    for row in bbox:
        cols = np.flatnonzero(row)
        if len(cols):
            left.append(float(cols.min()))
            right.append(float(cols.max()))
    width = max(1.0, float(bbox.shape[1]))
    scores = {
        "L": float(np.median(np.abs(np.asarray(left) - np.median(left))) / width),
        "R": float(np.median(np.abs(np.asarray(right) - np.median(right))) / width),
    }
    chosen = min(scores, key=scores.get)
    has_backbone = rectangularity < 0.88 and scores[chosen] < 0.035 and len(left) / bbox.shape[0] > 0.62
    return (chosen if has_backbone else None), {
        **key, "rectangularity": round(rectangularity, 6),
        "edge_median_absolute_deviation_over_width": {side: round(value, 6) for side, value in scores.items()},
        "classified_backbone_side": chosen if has_backbone else None,
    }


def parse_stem(path: Path) -> tuple[str, str, int]:
    match = re.fullmatch(r"out_(.+)_([LRC])_v(\d+)", path.stem)
    if not match:
        raise RuntimeError(f"Input name does not match Flat V3 convention: {path.name}")
    return match.group(1), match.group(2), int(match.group(3))


def is_kept_payload(payload: dict[str, Any]) -> bool:
    picks = payload.get("build_picks", [])
    return bool(picks and "mesh_being_replaced" in picks[0])


def pick_uncertainties(pick: dict[str, Any]) -> list[str]:
    status = pick.get("status", {})
    return sorted({
        f"{key}={value}"
        for key, value in status.items()
        if re.search(r"(?i)inferred|unclear", str(value))
    })


def select_picks(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    picks = payload["build_picks"]
    if not is_kept_payload(payload):
        return picks, []
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for pick in picks:
        reasons: list[str] = []
        alpha_mode = pick.get("alpha_mode")
        build_authorized = bool(pick.get("build_authorized"))
        if alpha_mode == "chroma":
            pass
        elif alpha_mode == "opacity_mask":
            if not pick.get("source_has_alpha"):
                reasons.append("opacity_mask_mode_requires_rgba_source")
        elif pick.get("flags", {}).get("alpha_missing") or not pick.get("source_has_alpha"):
            reasons.append("blocked_alpha_missing")
        if not reasons and not build_authorized:
            reasons.extend(pick_uncertainties(pick))
        if reasons:
            skipped.append({
                "passage": pick["passage"], "side": pick["side"],
                "source_name": Path(pick["canonical_path"]).stem,
                "source": pick["canonical_path"],
                "mesh_being_replaced": pick["mesh_being_replaced"],
                "reasons": reasons,
            })
        else:
            selected.append(pick)
    return selected, skipped


def safe_asset_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not token:
        raise RuntimeError(f"Source name has no usable asset characters: {value!r}")
    return token


def normalise_alpha_mode(value: Any) -> str:
    mode = str(value or "colour_key").lower()
    return "chroma" if mode == "colour_key" else mode


def build_kept_work_items(picks: list[dict[str, Any]]) -> list[WorkItem]:
    items: list[WorkItem] = []
    used: set[str] = set()
    for pick in picks:
        source = (PROJECT / pick["canonical_path"]).resolve()
        passage = safe_asset_token(str(pick["passage"]))
        source_side = str(pick["side"]).upper()
        if source_side not in {"L", "R", "C"}:
            raise RuntimeError(f"Unsupported kept-pick side {source_side!r}: {source}")
        source_name = safe_asset_token(source.stem)
        suffix = safe_asset_token(str(pick.get("asset_suffix") or f"{passage}_{source_name}_{source_side}"))
        if suffix in used:
            raise RuntimeError(f"Duplicate kept output asset name: SM_FlatV3_{suffix}")
        used.add(suffix)
        is_border = source_side == "C" or "top/border" in str(pick.get("flat_type", "")).lower()
        mount = "top-border" if is_border else "wing"
        kind = "wave" if is_border else "flat"
        build_side = "L" if is_border else source_side
        cut_method = normalise_alpha_mode(pick.get("alpha_mode") or "embedded_alpha")
        if cut_method not in {"embedded_alpha", "chroma", "opacity_mask"}:
            raise RuntimeError(f"Unsupported alpha mode {cut_method!r}: {source}")
        classification = {
            "source_contract": (
                "per-image border-detected chroma matte" if cut_method == "chroma"
                else "old Unreal texture-export opacity-mask alpha" if cut_method == "opacity_mask"
                else "KEPT_PICKS existing embedded alpha"
            ),
            "alpha_mode": cut_method,
            "flat_type": pick.get("flat_type"),
            "border_or_top": is_border,
            "pole_contract": "none for tops/borders" if is_border else "baked for floor-standing wing",
            "flags": pick.get("flags", {}),
        }
        items.append(WorkItem(
            source=source, passage=passage, height_cm=float(pick["target_height_cm"]),
            source_side=source_side, build_side=build_side, asset_suffix=suffix,
            mount=mount, kind=kind, pick=pick, classification=classification,
            cut_method=cut_method,
        ))
    return items


def build_work_items(picks: list[dict[str, Any]]) -> list[WorkItem]:
    if picks and "mesh_being_replaced" in picks[0]:
        return build_kept_work_items(picks)
    items: list[WorkItem] = []
    used: set[str] = set()
    side_versions: dict[tuple[str, str], int] = {}
    for pick in picks:
        source = PROJECT / pick["canonical_path"]
        if pick["passage"] != "S03":
            what, side, version = parse_stem(source)
            side_versions[(what.rsplit("_", 1)[0] if side == "C" else what, side)] = max(
                version, side_versions.get((what, side), 0)
            )
    for pick in picks:
        source = (PROJECT / pick["canonical_path"]).resolve()
        passage = pick["passage"]
        height = 800.0 if passage == "P05" else float(pick["target_height_cm"])
        if passage == "S03":
            stage_match = re.search(r"stage([123])", source.stem)
            if not stage_match:
                raise RuntimeError(f"Cannot map wave stage from {source.name}")
            row = int(stage_match.group(1))
            for label, phase in (("A", 0.08), ("B", 0.53)):
                suffix = f"S3_WaveRow{row}_{label}"
                items.append(WorkItem(
                    source, passage, height, "C", "L", suffix, "wave-row", "wave",
                    12.0, phase, pick, cut_method=normalise_alpha_mode(pick.get("alpha_mode")),
                ))
                used.add(suffix)
            continue
        what, source_side, version = parse_stem(source)
        build_side, mount, kind, suffix = source_side, "wing", "flat", f"{what}_{source_side}_v{version}"
        classification: dict[str, Any] = {}
        if passage == "P05" and source_side == "C":
            backbone, classification = preliminary_backbone(source, height)
            if backbone:
                build_side = backbone
                base = what
                existing = [
                    parse_stem((PROJECT / other["canonical_path"]).resolve())[2]
                    for other in picks
                    if other["passage"] == "P05" and re.search(fr"_{backbone}_v\d+$", Path(other["canonical_path"]).stem)
                ]
                new_version = max(existing or [0]) + 1
                while f"{base}_{backbone}_v{new_version}" in used:
                    new_version += 1
                suffix = f"{base}_{backbone}_v{new_version}"
                classification["mount_decision"] = "wing: a continuous straight backbone side was measured"
            else:
                mount, kind, build_side = "wave-row", "wave", "L"
                suffix = f"{what}_C_v{version}"
                classification["mount_decision"] = "C/border-type bottom-edge mount: no single backbone side was measured"
        if suffix in used:
            raise RuntimeError(f"Duplicate output asset name: {suffix}")
        used.add(suffix)
        items.append(WorkItem(
            source, passage, height, source_side, build_side, suffix, mount, kind,
            0.0, None, pick, classification,
            cut_method=normalise_alpha_mode(pick.get("alpha_mode")),
        ))
    return items


def alpha_from_sheet(rgb: np.ndarray, strength: float = 1.0) -> np.ndarray:
    smooth = cv2.GaussianBlur(rgb, (0, 0), sigmaX=38.0, sigmaY=38.0)
    delta = np.max(np.abs(rgb.astype(np.float32) - smooth.astype(np.float32)), axis=2)
    alpha = np.clip((delta - 4.0) / 34.0, 0.0, 1.0) * 255.0 * strength
    border = max(3, min(rgb.shape[:2]) // 80)
    alpha[:border] = alpha[-border:] = 0
    alpha[:, :border] = alpha[:, -border:] = 0
    return alpha.astype(np.uint8)


def prepare_shared_overlays() -> dict[str, Any]:
    SHARED.mkdir(parents=True, exist_ok=True)
    poster_source = QUEUE / "16_ALL_older_poster_fragments" / "results" / "out_ALL_older_posters_sheet_v1.png"
    stencil_source = QUEUE / "17_ALL_timber_stencil_chalk" / "results" / "out_ALL_stencil_chalk_sheet_v1.png"
    stain_sources = [
        QUEUE / "18_ALL_grime_paste_water" / "results" / "out_ALL_grime_paste_sheet_v1.png",
        QUEUE / "18_ALL_grime_paste_water" / "results" / "out_ALL_grime_paste_sheet_v3.png",
    ]
    poster = read_rgb(poster_source)
    stencil = read_rgb(stencil_source)
    stains = [read_rgb(path) for path in stain_sources]
    poster_alpha = alpha_from_sheet(poster, 0.82)
    stencil_alpha = alpha_from_sheet(stencil, 1.0)
    poster_atlas = SHARED / "T_FlatV3_OlderPosterAtlas_RGBA.png"
    stencil_atlas = SHARED / "T_FlatV3_StencilChalkAtlas_RGBA.png"
    older_flat = SHARED / "T_FlatV3_OlderPosterFragments_Color.png"
    write_rgba(poster_atlas, poster, poster_alpha)
    write_rgba(stencil_atlas, stencil, stencil_alpha)
    write_rgb(older_flat, poster)

    normalized = []
    for source in stains:
        resized = cv2.resize(source, (1024, 1024), interpolation=cv2.INTER_AREA)
        normalized.append(resized)
    base = ((normalized[0].astype(np.uint16) + normalized[1].astype(np.uint16)) // 2).astype(np.uint8)
    # A reflected 2x2 construction has identical opposite edges and therefore tiles.
    tile_top = np.concatenate((base, base[:, ::-1]), axis=1)
    tile_bottom = np.concatenate((base[::-1], base[::-1, ::-1]), axis=1)
    tile_rgb = np.concatenate((tile_top, tile_bottom), axis=0)
    tile_alpha = alpha_from_sheet(tile_rgb, 1.0)
    stain_tile = SHARED / "T_FlatV3_StainTile_RGBA.png"
    write_rgba(stain_tile, tile_rgb, tile_alpha)
    result = {
        "schema_version": 1,
        "created": now(),
        "older_poster": {"source": str(poster_source), "source_sha256": sha256(poster_source), "atlas": str(poster_atlas), "flattened_colour": str(older_flat)},
        "stencil_alpha_atlas": {"source": str(stencil_source), "source_sha256": sha256(stencil_source), "file": str(stencil_atlas), "alpha_method": "local-background high-pass"},
        "tileable_stains": {"sources": [str(path) for path in stain_sources], "source_sha256": [sha256(path) for path in stain_sources], "file": str(stain_tile), "tiling_method": "reflected 2x2; opposite edges identical"},
        "look_contract": "faint and sparse; per-flat bake caps stain at 0.09, stencil at 0.12, poster ghost at 0.04 opacity",
    }
    atomic_json(SHARED / "overlay_manifest.json", result)
    return result


def component_boxes(alpha: np.ndarray) -> list[tuple[int, int, int, int]]:
    grouped = cv2.dilate((alpha > 22).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(grouped, 8)
    boxes = []
    area_total = alpha.size
    for index in range(1, count):
        x, y, w, h, area = map(int, stats[index])
        if 0.0003 * area_total <= area <= 0.18 * area_total:
            boxes.append((x, y, x + w, y + h))
    return boxes


def paste_decal(base: np.ndarray, rgba: np.ndarray, box: tuple[int, int, int, int], center: tuple[int, int], max_width: int, opacity: float) -> None:
    x0, y0, x1, y1 = box
    crop = rgba[y0:y1, x0:x1]
    scale = min(1.0, max_width / max(1, crop.shape[1]))
    size = (max(2, int(crop.shape[1] * scale)), max(2, int(crop.shape[0] * scale)))
    crop = cv2.resize(crop, size, interpolation=cv2.INTER_AREA)
    px0 = int(np.clip(center[0] - size[0] // 2, 0, base.shape[1] - size[0]))
    py0 = int(np.clip(center[1] - size[1] // 2, 0, base.shape[0] - size[1]))
    alpha = crop[:, :, 3].astype(np.float32) / 255.0 * opacity
    target = base[py0:py0 + size[1], px0:px0 + size[0]].astype(np.float32)
    target[:] = target * (1.0 - alpha[:, :, None]) + crop[:, :, :3].astype(np.float32) * alpha[:, :, None]
    base[py0:py0 + size[1], px0:px0 + size[0]] = np.clip(target, 0, 255).astype(np.uint8)


def bake_back_overlays(aged_dir: Path, asset_suffix: str) -> dict[str, Any]:
    target_path = aged_dir / "T_FlatV3_AgedPlywood_Stencil_Color.png"
    base_bgr = cv2.imread(str(target_path), cv2.IMREAD_COLOR)
    if base_bgr is None:
        raise FileNotFoundError(target_path)
    base = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2RGB)
    rng = np.random.default_rng(int(hashlib.sha256(asset_suffix.encode()).hexdigest()[:8], 16))
    stain = cv2.cvtColor(cv2.imread(str(SHARED / "T_FlatV3_StainTile_RGBA.png"), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    stencil = cv2.cvtColor(cv2.imread(str(SHARED / "T_FlatV3_StencilChalkAtlas_RGBA.png"), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    poster = cv2.cvtColor(cv2.imread(str(SHARED / "T_FlatV3_OlderPosterAtlas_RGBA.png"), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    tiled = np.tile(stain, (math.ceil(base.shape[0] / stain.shape[0]) + 1, math.ceil(base.shape[1] / stain.shape[1]) + 1, 1))
    oy, ox = int(rng.integers(0, stain.shape[0])), int(rng.integers(0, stain.shape[1]))
    tiled = tiled[oy:oy + base.shape[0], ox:ox + base.shape[1]]
    stain_alpha = tiled[:, :, 3].astype(np.float32) / 255.0 * 0.09
    base = np.clip(base.astype(np.float32) * (1.0 - stain_alpha[:, :, None]) + tiled[:, :, :3].astype(np.float32) * stain_alpha[:, :, None], 0, 255).astype(np.uint8)
    selections = []
    for label, atlas, opacity, width_fraction in (
        ("stencil", stencil, 0.12, 0.30), ("poster_ghost", poster, 0.04, 0.22)
    ):
        boxes = component_boxes(atlas[:, :, 3])
        if not boxes:
            continue
        box = boxes[int(rng.integers(0, len(boxes)))]
        center = (int(rng.uniform(0.22, 0.78) * base.shape[1]), int(rng.uniform(0.25, 0.82) * base.shape[0]))
        paste_decal(base, atlas, box, center, int(base.shape[1] * width_fraction), opacity)
        selections.append({"kind": label, "source_box": list(box), "center_px": list(center), "opacity_cap": opacity})
    write_rgb(target_path, base)
    manifest_path = aged_dir / "aged_texture_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["baked_overlays"] = {
        "tileable_stains": str(SHARED / "T_FlatV3_StainTile_RGBA.png"), "stain_opacity_cap": 0.09,
        "decal_atlases": [str(SHARED / "T_FlatV3_StencilChalkAtlas_RGBA.png"), str(SHARED / "T_FlatV3_OlderPosterAtlas_RGBA.png")],
        "placements": selections, "contract": "faint and sparse, baked into Timber plywood colour",
    }
    atomic_json(manifest_path, manifest)
    return manifest["baked_overlays"]


CONTACT_RENDER_EXPR = r'''
import bpy, os
from mathutils import Vector
bpy.ops.import_scene.fbx(filepath=os.environ["FLATV3_CONTACT_FBX"], use_custom_normals=True)
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
lod0=[o for o in meshes if "_LOD0" in o.name]
flat=lod0[0] if lod0 else max(meshes,key=lambda o:len(o.data.polygons))
for o in bpy.context.scene.objects:
    if o.type in {"MESH","CURVE","SURFACE","META","FONT"}: o.hide_render=(o!=flat)
coords=[flat.matrix_world@v.co for v in flat.data.vertices]
lo=Vector((min(v.x for v in coords),min(v.y for v in coords),min(v.z for v in coords)))
hi=Vector((max(v.x for v in coords),max(v.y for v in coords),max(v.z for v in coords)))
c=(lo+hi)*0.5; width=hi.y-lo.y; height=hi.z-lo.z; depth=hi.x-lo.x
scene=bpy.context.scene
contact_device=os.environ.get("FLATV3_CONTACT_DEVICE","GPU").upper()
if contact_device=="CPU":
    scene.render.engine="CYCLES"; scene.cycles.device="CPU"; scene.cycles.samples=32; scene.cycles.use_denoising=True
else:
    scene.render.engine="BLENDER_EEVEE_NEXT"
scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGB"; scene.render.film_transparent=False
scene.world.color=(0.012,0.014,0.018); scene.view_settings.look="AgX - Medium High Contrast"; scene.view_settings.exposure=0.55
cam_data=bpy.data.cameras.new("ContactCamera"); cam=bpy.data.objects.new("ContactCamera",cam_data); bpy.context.collection.objects.link(cam); scene.camera=cam
cam.data.type="ORTHO"; cam.data.ortho_scale=max(width,height)*1.18
def look(obj,target): obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()
def lamp(name,loc,energy,size,color):
    data=bpy.data.lights.new(name,"AREA"); data.energy=energy; data.shape="DISK"; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj); obj.location=loc; look(obj,c); return obj
distance=max(width,height)*1.6+3.0
front_key=lamp("FrontKey",(lo.x-distance,c.y-width*.30,c.z+height*.25),900,max(3.0,height*.7),(1.0,.90,.78))
back_key=lamp("BackKey",(hi.x+distance,c.y+width*.28,c.z+height*.30),1050,max(3.0,height*.75),(.88,.92,1.0))
front_fill=lamp("FrontFill",(lo.x-distance*.7,c.y+width*.35,c.z-height*.10),350,max(2.0,height*.5),(.55,.66,1.0))
out=os.environ["FLATV3_CONTACT_DIR"]; stem=os.environ["FLATV3_CONTACT_STEM"]
back_key.hide_render=True
cam.location=(lo.x-distance,c.y,c.z); look(cam,c); scene.render.filepath=os.path.join(out,stem+"_front_head_on.png"); bpy.ops.render.render(write_still=True)
front_key.hide_render=True; front_fill.hide_render=True; back_key.hide_render=False
cam.location=(hi.x+distance,c.y+width*.55,c.z+height*.14); look(cam,c); cam.data.ortho_scale=max(width,height)*1.30
scene.render.filepath=os.path.join(out,stem+"_back_three_quarter.png"); bpy.ops.render.render(write_still=True)
'''


def run_command(command: list[str], log_stream, env: dict[str, str] | None = None) -> None:
    log_stream.write("\nCOMMAND " + subprocess.list2cmdline(command) + "\n")
    log_stream.flush()
    completed = subprocess.run(command, cwd=PROJECT, stdout=log_stream, stderr=subprocess.STDOUT, env=env, text=True)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command[0]}")


def validate_shared_pole(manifest: dict[str, Any]) -> None:
    pole = OUT / "SM_FlatV3_Pole.fbx"
    built_wings = [
        item for item in manifest.get("items", [])
        if item.get("status") == "built" and item.get("kind") == "flat" and not item.get("baked_poles")
    ]
    if not built_wings:
        manifest["shared_pole_validation"] = {
            "pass": True,
            "reason": "all successful wing builds use baked poles; no shared pole FBX is required",
        }
        return
    if not pole.is_file():
        raise RuntimeError("Successful wing builds exist but the canonical shared pole FBX is missing")
    report = OUT / "SM_FlatV3_Pole_validation.json"
    log_path = LOGS / "shared_pole_validation.log"
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        run_command([
            str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(BUILD_FLAT), "--",
            "--validate-fbx", str(pole), "--kind", "pole", "--validation-out", str(report),
        ], log)
    data = json.loads(report.read_text(encoding="utf-8"))
    manifest["shared_pole_validation"] = {"pass": bool(data.get("pass")), "fbx": str(pole), "report": str(report), "log": str(log_path)}
    if not data.get("pass"):
        raise RuntimeError(f"Shared pole validation failed: {report}")


def contact_image_check(path: Path) -> dict[str, Any]:
    image = np.asarray(Image.open(path).convert("RGB"))
    corners = np.concatenate((image[:20, :20].reshape(-1, 3), image[-20:, -20:].reshape(-1, 3)), axis=0)
    bg = np.median(corners, axis=0)
    delta = np.max(np.abs(image.astype(np.float32) - bg), axis=2)
    coverage = float((delta > 9.0).mean())
    return {"pass": coverage > 0.005, "non_background_percent": round(coverage * 100.0, 6), "size_px": [image.shape[1], image.shape[0]]}


def item_fingerprint(item: WorkItem) -> str:
    data = {
        "driver": sha256(Path(__file__)), "builder": sha256(BUILD_FLAT), "skin": sha256(BUILD_SKIN),
        "source": sha256(item.source), "asset": item.asset_suffix, "height": item.height_cm,
        "mount": item.mount, "kind": item.kind, "phase": item.phase,
        "cut_method": item.cut_method, "bake_poles": item.bake_poles,
        "peel_profile": item.pick.get("peel_profile"),
        "peel_percent": item.pick.get("peel_percent"),
        "deterministic_triangulation": item.pick.get("deterministic_triangulation", False),
        "overlays": sha256(SHARED / "overlay_manifest.json"),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def complete_status(item: WorkItem, fingerprint: str) -> dict[str, Any] | None:
    status_path = item.folder / "status.json"
    if not status_path.is_file():
        return None
    with contextlib.suppress(Exception):
        status = json.loads(status_path.read_text(encoding="utf-8"))
        required = [Path(value) for value in status.get("required_outputs", [])]
        expected_baked_poles = item.bake_poles
        if (status.get("status") == "built"
                and status.get("fingerprint") == fingerprint
                and status.get("validation_pass") is True
                and bool(status.get("baked_poles")) == expected_baked_poles
                and all(path.is_file() for path in required)):
            status["resume_action"] = "skipped_existing_verified_output"
            return status
    return None


def build_one(
    item: WorkItem, upscaler: Upscaler, sam_refiner: SAMChromaRefiner | None = None
) -> dict[str, Any]:
    item.folder.mkdir(parents=True, exist_ok=True)
    item.log.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = item_fingerprint(item)
    resumed = complete_status(item, fingerprint)
    if resumed:
        return resumed
    started = time.perf_counter()
    status: dict[str, Any] = {
        "schema_version": SCHEMA, "asset_name": item.asset_name, "asset_suffix": item.asset_suffix,
        "passage": item.passage, "source": str(item.source), "height_cm": item.height_cm,
        "source_side": item.source_side, "build_side": item.build_side, "mount": item.mount,
        "kind": item.kind, "classification": item.classification, "fingerprint": fingerprint,
        "started": now(), "status": "running", "log": str(item.log),
    }
    atomic_json(item.folder / "status.json", status)
    with item.log.open("a", encoding="utf-8", buffering=1) as log:
        log.write(f"\n===== {now()} START {item.asset_name} =====\n")
        try:
            soft_alpha: np.ndarray | None = None
            if item.cut_method == "embedded_alpha":
                rgb, mask, key_stats = embedded_alpha_cut(item.source)
            elif item.cut_method == "chroma":
                rgb, soft_alpha, key_stats = chroma_alpha_cut(item.source, sam_refiner)
                mask = soft_alpha >= 128
            elif item.cut_method == "opacity_mask":
                rgb, soft_alpha, key_stats = opacity_mask_cut(item.source)
                mask = soft_alpha >= 128
            else:
                rgb = read_rgb(item.source)
                mask, key_stats = colour_key(rgb, item.height_cm)
            mask, jigsaw_stats = jigsaw(mask, item.height_cm)
            rgb, mask, crop_stats = crop_with_bleed_margin(rgb, mask, item.height_cm)
            if soft_alpha is not None:
                x0, y0, x1, y1 = crop_stats["crop_xyxy"]
                soft_alpha = soft_alpha[y0:y1, x0:x1].copy()
                soft_support = cv2.dilate(
                    mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                ).astype(bool)
                soft_alpha[~soft_support] = 0
            if item.kind == "wave" and item.phase is not None:
                if soft_alpha is not None:
                    raise RuntimeError("Soft-alpha cut modes do not support phase-repeated wave rows")
                rgb, mask, wave_stats = repeat_wave(rgb, mask, item.height_cm, item.phase)
                mask, post_wave_jigsaw = jigsaw(mask, item.height_cm)
            else:
                wave_stats, post_wave_jigsaw = None, None
            native_art = item.folder / "stage1_colour_key_art.png"
            native_mask = item.folder / "stage2_jigsaw_mask.png"
            write_rgb(native_art, rgb)
            final_native_alpha = soft_alpha if soft_alpha is not None else mask.astype(np.uint8) * 255
            save_png(native_mask, final_native_alpha)
            bleed_rgb, bleed_mask, bleed_stats = colour_bleed(rgb, mask, item.height_cm)
            bleed_path = item.folder / "stage3_colour_bleed.png"
            write_rgba(bleed_path, bleed_rgb, bleed_mask.astype(np.uint8) * 255)
            up2, upscale_stats = upscaler.two_x(bleed_rgb)
            soft_alpha_path: Path | None = None
            if soft_alpha is not None:
                up_soft_alpha = cv2.resize(
                    final_native_alpha, (mask.shape[1] * 2, mask.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4
                )
                up_support = cv2.resize(
                    soft_support.astype(np.uint8), (mask.shape[1] * 2, mask.shape[0] * 2), interpolation=cv2.INTER_NEAREST
                ).astype(bool)
                up_soft_alpha[~up_support] = 0
                soft_alpha_path = item.folder / "stage4_RealESRGAN_2x_soft_alpha.png"
                save_png(soft_alpha_path, up_soft_alpha)
            up_mask = cv2.resize(
                mask.astype(np.uint8), (mask.shape[1] * 2, mask.shape[0] * 2), interpolation=cv2.INTER_NEAREST
            ).astype(bool)
            art_path = item.folder / "stage4_RealESRGAN_2x_art.png"
            mask_path = item.folder / "stage4_RealESRGAN_2x_jigsaw_mask.png"
            write_rgb(art_path, up2)
            save_png(mask_path, up_mask.astype(np.uint8) * 255)
            del up2

            skin_dir, aged_dir = item.folder / "skin", item.folder / "aged"
            skin_dir.mkdir(exist_ok=True); aged_dir.mkdir(exist_ok=True)
            skin_cmd = [
                str(VENV_PYTHON), str(BUILD_SKIN), "--mask", str(mask_path), "--art", str(art_path),
                "--older-poster", str(SHARED / "T_FlatV3_OlderPosterFragments_Color.png"),
                "--paper-displacement", str(PAPER_DISP), "--paper-roughness", str(PAPER_ROUGH),
                "--texture-root", str(TEXTURE_ROOT), "--aged-output", str(aged_dir),
                # A blank disables build_skin's legacy single generated stencil;
                # the processed jobs 16/17/18 atlases are baked immediately after.
                "--stencil-text", " ",
                "--height-cm", str(item.height_cm), "--asset-name", item.asset_suffix,
                "--output", str(skin_dir), "--diagnostics-output", str(item.folder / "diagnostics"),
                "--seed", str(20261001 + int(hashlib.sha256(item.asset_suffix.encode()).hexdigest()[:5], 16) % 100000),
            ]
            if item.minimum_width_m:
                skin_cmd += ["--width-cm", str(WAVE_WIDTH_CM)]
            if item.pick.get("peel_profile"):
                skin_cmd += ["--peel-profile", str(item.pick["peel_profile"])]
            if item.pick.get("peel_percent") is not None:
                skin_cmd += ["--peel-percent", str(item.pick["peel_percent"])]
            run_command(skin_cmd, log)
            overlay_bake = bake_back_overlays(aged_dir, item.asset_suffix)

            skin_color = skin_dir / f"T_{item.asset_suffix}_SkinColor.png"
            skin_mask = skin_dir / f"T_{item.asset_suffix}_SkinMask.png"
            skin_normal = skin_dir / f"T_{item.asset_suffix}_SkinNormal.png"
            flaps = skin_dir / f"{item.asset_suffix}_flaps.json"
            build_cmd = [
                str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(BUILD_FLAT), "--",
                "--mask", str(mask_path), "--art", str(skin_color), "--skin-mask", str(skin_mask),
                "--skin-normal", str(skin_normal), "--flaps", str(flaps), "--aged-texture-dir", str(aged_dir),
                "--height-cm", str(item.height_cm), "--side", item.build_side, "--name", item.asset_suffix,
                "--asset-name", item.asset_suffix, "--mount", item.mount, "--output-dir", str(item.folder),
                "--texture-root", str(TEXTURE_ROOT),
            ]
            bake_poles = item.bake_poles
            if bake_poles:
                build_cmd.append("--bake-poles")
            if item.pick.get("deterministic_triangulation"):
                build_cmd.append("--deterministic-triangulation")
            if item.pick.get("triangulate_export"):
                build_cmd.append("--triangulate-export")
            run_command(build_cmd, log)

            fbx = item.folder / f"{item.asset_name}.fbx"
            validation = item.folder / "validation.json"
            validate_cmd = [
                str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(BUILD_FLAT), "--",
                "--validate-fbx", str(fbx), "--skin-color", str(skin_color), "--kind", item.kind,
                "--validation-out", str(validation), "--expected-height-cm", str(item.height_cm),
                "--minimum-width-m", str(item.minimum_width_m),
            ]
            run_command(validate_cmd, log)
            validation_data = json.loads(validation.read_text(encoding="utf-8"))
            if not validation_data.get("pass"):
                failed_checks = [name for name, check in validation_data.get("checks", {}).items() if not check.get("pass")]
                raise RuntimeError(f"FBX validation gates failed: {failed_checks}; report: {validation}")
            build_manifest_path = item.folder / f"{item.asset_suffix}_{item.build_side}_build.json"
            build_manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
            containment = build_manifest["head_on_frame_visibility"]
            if not containment.get("pass"):
                raise RuntimeError(f"Frame containment failed: {containment}")

            contact_env = os.environ.copy()
            contact_env.update({
                "FLATV3_CONTACT_FBX": str(fbx), "FLATV3_CONTACT_DIR": str(item.folder),
                "FLATV3_CONTACT_STEM": item.asset_suffix,
            })
            run_command([str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", CONTACT_RENDER_EXPR], log, contact_env)
            front = item.folder / f"{item.asset_suffix}_front_head_on.png"
            back = item.folder / f"{item.asset_suffix}_back_three_quarter.png"
            contact_checks = {"front": contact_image_check(front), "back": contact_image_check(back)}
            if not all(check["pass"] for check in contact_checks.values()):
                raise RuntimeError(f"Contact render occupancy failed: {contact_checks}")

            socket_sidecar = item.folder / f"sockets_{item.asset_name}.json"
            required = [fbx, validation, build_manifest_path, socket_sidecar, skin_color, skin_mask, skin_normal, front, back]
            if soft_alpha_path is not None:
                required.append(soft_alpha_path)
            status.update({
                "status": "built", "finished": now(), "seconds": round(time.perf_counter() - started, 3),
                "cutout": {**key_stats, **jigsaw_stats, **crop_stats, "wave": wave_stats, "post_wave_jigsaw": post_wave_jigsaw},
                "bleed": bleed_stats, "upscale": upscale_stats, "back_overlays": overlay_bake,
                "fbx": str(fbx), "build_manifest": str(build_manifest_path), "validation": str(validation),
                "validation_pass": True, "frame_containment": containment,
                "baked_poles": bake_poles, "socket_sidecar": str(socket_sidecar),
                "contact_renders": {"front": str(front), "back": str(back), "checks": contact_checks},
                "soft_alpha": str(soft_alpha_path) if soft_alpha_path is not None else None,
                "required_outputs": [str(path) for path in required],
            })
            log.write(f"===== {now()} BUILT {item.asset_name} =====\n")
        except Exception as exc:
            status.update({
                "status": "failed", "finished": now(), "seconds": round(time.perf_counter() - started, 3),
                "failure_type": type(exc).__name__, "reason": str(exc), "traceback": traceback.format_exc(),
            })
            log.write(status["traceback"] + "\n")
            log.write(f"===== {now()} FAILED {item.asset_name}: {exc} =====\n")
        atomic_json(item.folder / "status.json", status)
    return status


def repair_one_from_stage4(item: WorkItem, contact_device: str = "GPU") -> dict[str, Any]:
    """Resume a failed item after its costly cutout/upscale products exist."""
    item.folder.mkdir(parents=True, exist_ok=True)
    item.log.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    fingerprint = item_fingerprint(item)
    status: dict[str, Any] = {
        "schema_version": SCHEMA, "asset_name": item.asset_name, "asset_suffix": item.asset_suffix,
        "passage": item.passage, "source": str(item.source), "height_cm": item.height_cm,
        "source_side": item.source_side, "build_side": item.build_side, "mount": item.mount,
        "kind": item.kind, "classification": item.classification, "fingerprint": fingerprint,
        "started": now(), "status": "running", "log": str(item.log),
        "resume_action": "reused_existing_stage4_no_upscaler",
    }
    atomic_json(item.folder / "status.json", status)
    with item.log.open("a", encoding="utf-8", buffering=1) as log:
        log.write(f"\n===== {now()} REPAIR_FROM_STAGE4 {item.asset_name} =====\n")
        try:
            art_path = item.folder / "stage4_RealESRGAN_2x_art.png"
            mask_path = item.folder / "stage4_RealESRGAN_2x_jigsaw_mask.png"
            if not art_path.is_file() or not mask_path.is_file():
                raise FileNotFoundError(f"Stage 4 resume inputs missing: {art_path}, {mask_path}")
            soft_alpha_path: Path | None = None
            if item.cut_method in {"chroma", "opacity_mask"}:
                native_alpha_path = item.folder / "stage2_jigsaw_mask.png"
                native_alpha = cv2.imread(str(native_alpha_path), cv2.IMREAD_GRAYSCALE)
                existing_stage4_alpha = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if native_alpha is None or existing_stage4_alpha is None:
                    raise FileNotFoundError("Soft-alpha repair inputs are missing")
                soft_alpha_path = item.folder / "stage4_RealESRGAN_2x_soft_alpha.png"
                if not soft_alpha_path.is_file():
                    save_png(soft_alpha_path, existing_stage4_alpha)
                binary_native = native_alpha >= 128
                binary_up2 = cv2.resize(
                    binary_native.astype(np.uint8),
                    (existing_stage4_alpha.shape[1], existing_stage4_alpha.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ).astype(bool)
                save_png(mask_path, binary_up2.astype(np.uint8) * 255)
                log.write(
                    f"REPAIR_MASK split_soft_alpha={soft_alpha_path} binary_geometry_mask={mask_path}\n"
                )

            skin_dir, aged_dir = item.folder / "skin", item.folder / "aged"
            skin_dir.mkdir(exist_ok=True); aged_dir.mkdir(exist_ok=True)
            skin_cmd = [
                str(VENV_PYTHON), str(BUILD_SKIN), "--mask", str(mask_path), "--art", str(art_path),
                "--older-poster", str(SHARED / "T_FlatV3_OlderPosterFragments_Color.png"),
                "--paper-displacement", str(PAPER_DISP), "--paper-roughness", str(PAPER_ROUGH),
                "--texture-root", str(TEXTURE_ROOT), "--aged-output", str(aged_dir),
                "--stencil-text", " ", "--height-cm", str(item.height_cm), "--asset-name", item.asset_suffix,
                "--output", str(skin_dir), "--diagnostics-output", str(item.folder / "diagnostics"),
                "--seed", str(20261001 + int(hashlib.sha256(item.asset_suffix.encode()).hexdigest()[:5], 16) % 100000),
            ]
            if item.minimum_width_m:
                skin_cmd += ["--width-cm", str(WAVE_WIDTH_CM)]
            if item.pick.get("peel_profile"):
                skin_cmd += ["--peel-profile", str(item.pick["peel_profile"])]
            if item.pick.get("peel_percent") is not None:
                skin_cmd += ["--peel-percent", str(item.pick["peel_percent"])]
            run_command(skin_cmd, log)
            overlay_bake = bake_back_overlays(aged_dir, item.asset_suffix)

            skin_color = skin_dir / f"T_{item.asset_suffix}_SkinColor.png"
            skin_mask = skin_dir / f"T_{item.asset_suffix}_SkinMask.png"
            skin_normal = skin_dir / f"T_{item.asset_suffix}_SkinNormal.png"
            flaps = skin_dir / f"{item.asset_suffix}_flaps.json"
            build_cmd = [
                str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(BUILD_FLAT), "--",
                "--mask", str(mask_path), "--art", str(skin_color), "--skin-mask", str(skin_mask),
                "--skin-normal", str(skin_normal), "--flaps", str(flaps), "--aged-texture-dir", str(aged_dir),
                "--height-cm", str(item.height_cm), "--side", item.build_side, "--name", item.asset_suffix,
                "--asset-name", item.asset_suffix, "--mount", item.mount, "--output-dir", str(item.folder),
                "--texture-root", str(TEXTURE_ROOT),
            ]
            bake_poles = item.bake_poles
            if bake_poles:
                build_cmd.append("--bake-poles")
            if item.pick.get("deterministic_triangulation"):
                build_cmd.append("--deterministic-triangulation")
            if item.pick.get("triangulate_export"):
                build_cmd.append("--triangulate-export")
            run_command(build_cmd, log)

            fbx = item.folder / f"{item.asset_name}.fbx"
            validation = item.folder / "validation.json"
            run_command([
                str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(BUILD_FLAT), "--",
                "--validate-fbx", str(fbx), "--skin-color", str(skin_color), "--kind", item.kind,
                "--validation-out", str(validation), "--expected-height-cm", str(item.height_cm),
                "--minimum-width-m", str(item.minimum_width_m),
            ], log)
            validation_data = json.loads(validation.read_text(encoding="utf-8"))
            if not validation_data.get("pass"):
                failed_checks = [name for name, check in validation_data.get("checks", {}).items() if not check.get("pass")]
                raise RuntimeError(f"FBX validation gates failed: {failed_checks}; report: {validation}")
            build_manifest_path = item.folder / f"{item.asset_suffix}_{item.build_side}_build.json"
            build_manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
            containment = build_manifest["head_on_frame_visibility"]
            if not containment.get("pass"):
                raise RuntimeError(f"Frame containment failed: {containment}")

            contact_env = os.environ.copy()
            contact_env.update({
                "FLATV3_CONTACT_FBX": str(fbx), "FLATV3_CONTACT_DIR": str(item.folder),
                "FLATV3_CONTACT_STEM": item.asset_suffix,
                "FLATV3_CONTACT_DEVICE": contact_device,
            })
            run_command([str(BLENDER), "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", CONTACT_RENDER_EXPR], log, contact_env)
            front = item.folder / f"{item.asset_suffix}_front_head_on.png"
            back = item.folder / f"{item.asset_suffix}_back_three_quarter.png"
            contact_checks = {"front": contact_image_check(front), "back": contact_image_check(back)}
            if not all(check["pass"] for check in contact_checks.values()):
                raise RuntimeError(f"Contact render occupancy failed: {contact_checks}")

            socket_sidecar = item.folder / f"sockets_{item.asset_name}.json"
            required = [fbx, validation, build_manifest_path, socket_sidecar, skin_color, skin_mask, skin_normal, front, back]
            if soft_alpha_path is not None:
                required.append(soft_alpha_path)
            if not all(path.is_file() for path in required):
                raise FileNotFoundError("Required repaired output missing: " + ", ".join(str(path) for path in required if not path.is_file()))
            status.update({
                "status": "built", "finished": now(), "seconds": round(time.perf_counter() - started, 3),
                "cutout": {"resume_action": "reused_existing_stage4"},
                "upscale": {"resume_action": "reused_existing_stage4", "model_loaded": False},
                "back_overlays": overlay_bake, "fbx": str(fbx), "build_manifest": str(build_manifest_path),
                "validation": str(validation), "validation_pass": True, "frame_containment": containment,
                "baked_poles": bake_poles, "socket_sidecar": str(socket_sidecar),
                "contact_renders": {"front": str(front), "back": str(back), "checks": contact_checks},
                "contact_render_device": contact_device,
                "soft_alpha": str(soft_alpha_path) if soft_alpha_path is not None else None,
                "required_outputs": [str(path) for path in required],
            })
            log.write(f"===== {now()} REPAIRED {item.asset_name} =====\n")
        except Exception as exc:
            status.update({
                "status": "failed", "finished": now(), "seconds": round(time.perf_counter() - started, 3),
                "failure_type": type(exc).__name__, "reason": str(exc), "traceback": traceback.format_exc(),
            })
            log.write(status["traceback"] + "\n")
            log.write(f"===== {now()} REPAIR_FAILED {item.asset_name}: {exc} =====\n")
        atomic_json(item.folder / "status.json", status)
    return status


def make_contact_sheet(statuses: list[dict[str, Any]]) -> None:
    built = [status for status in statuses if status.get("status") == "built"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for status in built:
        groups.setdefault(status["passage"], []).append(status)
    cards = []
    for passage in sorted(groups):
        cards.append(f"<h2>{html.escape(passage)}</h2><div class='grid'>")
        for status in sorted(groups[passage], key=lambda value: value["asset_name"]):
            front = Path(status["contact_renders"]["front"])
            back = Path(status["contact_renders"]["back"])
            rel_front = os.path.relpath(front, OUT).replace("\\", "/")
            rel_back = os.path.relpath(back, OUT).replace("\\", "/")
            cards.append(
                "<article><h3>" + html.escape(status["asset_name"]) + "</h3>"
                f"<div class='pair'><figure><img src='{html.escape(rel_front)}'><figcaption>front head-on</figcaption></figure>"
                f"<figure><img src='{html.escape(rel_back)}'><figcaption>back 3/4</figcaption></figure></div>"
                f"<p class='pass'>VALIDATION PASS · {html.escape(status['mount'])} · {status['height_cm']:.0f} cm</p></article>"
            )
        cards.append("</div>")
    document = """<!doctype html><meta charset='utf-8'><title>Flat V3 batch contacts</title>
<style>body{font:16px system-ui;background:#17191d;color:#eee;margin:24px}h1,h2{margin:20px 0 10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(540px,1fr));gap:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}article{background:#24272d;padding:12px;border-radius:8px}img{width:100%;height:auto;background:#111}figure{margin:0}figcaption{color:#bbb}.pass{color:#8ee29a;font-weight:700}</style>
<h1>Flat V3 batch build</h1><p>Every card below passed clean FBX re-import validation and contact-render occupancy.</p>""" + "\n".join(cards)
    (OUT / "CONTACT_SHEET.html").write_text(document, encoding="utf-8")

    font = ImageFont.load_default()
    cell_w, image_h, gap = 420, 300, 22
    row_h = image_h + 74
    rows = sum(len(values) for values in groups.values()) + len(groups)
    sheet = Image.new("RGB", (cell_w * 2 + gap * 3, max(180, rows * row_h)), (23, 25, 29))
    draw = ImageDraw.Draw(sheet)
    y = 18
    for passage in sorted(groups):
        draw.text((gap, y), passage, fill=(240, 232, 210), font=font)
        y += 28
        for status in sorted(groups[passage], key=lambda value: value["asset_name"]):
            for column, key in enumerate(("front", "back")):
                image = Image.open(status["contact_renders"][key]).convert("RGB")
                image.thumbnail((cell_w, image_h), Image.Resampling.LANCZOS)
                x = gap + column * (cell_w + gap)
                sheet.paste(image, (x + (cell_w - image.width) // 2, y))
            draw.text((gap, y + image_h + 6), status["asset_name"], fill=(235, 235, 235), font=font)
            draw.text((gap + cell_w + gap, y + image_h + 6), "VALIDATION PASS", fill=(130, 230, 150), font=font)
            y += row_h
    sheet = sheet.crop((0, 0, sheet.width, max(180, y + 10)))
    sheet.save(OUT / "CONTACT_SHEET.jpg", quality=92, subsampling=0)


def write_failures(
    statuses: list[dict[str, Any]], fatal: str | None = None,
    skipped: list[dict[str, Any]] | None = None,
) -> None:
    failures = [status for status in statuses if status.get("status") == "failed"]
    skipped = skipped or []
    lines = ["# Flat V3 batch failures and skips", "", f"Updated: {now()}", ""]
    if fatal:
        lines += ["## Batch-level failure", "", "```text", fatal.strip(), "```", ""]
    if not failures and not fatal:
        lines += ["No build failures. Every scheduled flat was built and validated.", ""]
    for status in failures:
        lines += [f"## {status['asset_name']}", "", f"- Reason: `{status.get('reason', 'unknown')}`", f"- Log: `{status.get('log')}`", ""]
    if skipped:
        lines += ["## Skipped before build", "", f"Count: {len(skipped)}", ""]
        for item in skipped:
            lines.append(
                f"- `{item['passage']} {item['side']} {item['source_name']}`: "
                + ", ".join(item["reasons"])
            )
        lines.append("")
    (OUT / "FAILURES.md").write_text("\n".join(lines), encoding="utf-8")


def write_kept_map(items: list[WorkItem], filename: str = "KEPT_MAP.json") -> None:
    mappings = {
        item.asset_name: item.pick["mesh_being_replaced"]
        for item in sorted(items, key=lambda value: value.asset_name)
        if item.pick.get("mesh_being_replaced")
    }
    atomic_json(OUT / filename, {
        "schema_version": 1,
        "created": now(),
        "source_picks": str(PICKS_PATH),
        "entry_count": len(mappings),
        "mesh_map": mappings,
        "entries": [
            {
                "new_mesh": item.asset_name,
                "replaces": item.pick.get("mesh_being_replaced"),
                "passage": item.passage,
                "side": item.source_side,
                "height_cm": item.height_cm,
                "source": str(item.source),
            }
            for item in sorted(items, key=lambda value: value.asset_name)
        ],
    })


def write_batch_summary(
    statuses: list[dict[str, Any]], payload: dict[str, Any], skipped: list[dict[str, Any]], fatal: str | None,
) -> None:
    if not payload.get("batch_label"):
        return
    built = [status for status in statuses if status.get("status") == "built"]
    failed = [status for status in statuses if status.get("status") == "failed"]
    alpha_counts: dict[str, int] = {}
    for pick in payload.get("build_picks", []):
        mode = str(pick.get("alpha_mode") or "embedded_alpha")
        alpha_counts[mode] = alpha_counts.get(mode, 0) + 1
    special_flags = [
        str(pick.get("flags", {}).get("manual_review_flag"))
        for pick in payload.get("build_picks", [])
        if pick.get("flags", {}).get("manual_review_flag")
    ]
    lines = [
        f"# {payload['batch_label']}", "", f"Updated: {now()}", "",
        f"- Scheduled: {len(statuses)}", f"- Built and all gates passed: {len(built)}",
        f"- Failed: {len(failed)}", f"- Skipped: {len(skipped)}",
        f"- Alpha modes: {json.dumps(alpha_counts, sort_keys=True)}",
        f"- Upscale: 2x Real-ESRGAN (`RealESRGAN_x4plus` inferred once per batch)",
        f"- Poles: baked on L/R wings; none on C top borders",
        f"- Mesh swap map: `{payload.get('mapping_filename', 'KEPT_MAP.json')}`", "",
        "## Special flags", "",
    ]
    lines.extend([f"- {flag}" for flag in special_flags] or ["- None."])
    lines += ["", "## Verification", ""]
    if fatal:
        lines.append("- **measured:** batch-level fatal error; see `FAILURES.md`.")
    elif failed:
        lines.append(f"- **measured:** {len(failed)} asset build(s) failed; see `FAILURES.md`.")
    else:
        lines.append("- **measured:** every scheduled asset passed FBX re-import, frame-containment and two-view contact-render occupancy gates.")
    lines.append("- **inferred / not claimed:** no Unreal import, Show swap, or rendered in-show acceptance was performed.")
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_soft_alpha_artifacts(items: list[WorkItem]) -> dict[str, Any]:
    """Preserve the original soft matte when upgrading an older staged run.

    Early chroma-mode outputs used the stage-4 geometry-mask filename for the
    soft matte.  Repairs split that into a soft alpha artifact and a binary
    contour mask.  Materialize the companion file before any repair can replace
    the older staged matte; never manufacture a soft matte from a binary mask.
    """
    created: list[str] = []
    existing: list[str] = []
    missing: list[dict[str, str]] = []
    for item in items:
        if item.cut_method not in {"chroma", "opacity_mask"}:
            continue
        soft_path = item.folder / "stage4_RealESRGAN_2x_soft_alpha.png"
        if soft_path.is_file():
            existing.append(item.asset_suffix)
            continue
        staged_path = item.folder / "stage4_RealESRGAN_2x_jigsaw_mask.png"
        alpha = cv2.imread(str(staged_path), cv2.IMREAD_GRAYSCALE)
        if alpha is None:
            missing.append({"asset_suffix": item.asset_suffix, "reason": "stage4 mask missing"})
            continue
        if len(np.unique(alpha)) <= 2:
            missing.append({
                "asset_suffix": item.asset_suffix,
                "reason": "stage4 mask is binary and no preserved soft matte exists",
            })
            continue
        save_png(soft_path, alpha)
        created.append(item.asset_suffix)
    return {
        "expected": sum(item.cut_method in {"chroma", "opacity_mask"} for item in items),
        "created": created, "existing": existing, "missing": missing,
        "pass": not missing,
    }


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        # Access denied still proves that a process owns this PID.
        return ctypes.get_last_error() == 5
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (OSError, ProcessLookupError):
        return False


def wait_for_gpu_slot(marker: Path) -> dict[str, Any]:
    waited_from: str | None = None
    while marker.is_file():
        with contextlib.suppress(Exception):
            state = json.loads(marker.read_text(encoding="utf-8"))
            owner_pid = int(state.get("pid", 0))
            if state.get("status") == "running" and owner_pid != os.getpid() and process_exists(owner_pid):
                if waited_from is None:
                    waited_from = now()
                    print(f"FLAT_V3_GPU_WAIT owner_pid={owner_pid} marker={marker}", flush=True)
                time.sleep(2)
                continue
        break
    return {"marker": str(marker), "waited_from": waited_from, "acquired": now()}


def write_running_state(payload: dict[str, Any]) -> None:
    atomic_json(GPU_MARKER, payload)
    local_marker = OUT / "RUNNING.json"
    if local_marker != GPU_MARKER:
        atomic_json(local_marker, payload)


def preflight() -> dict[str, Any]:
    required = [PICKS_PATH, VENV_PYTHON, BLENDER, MODEL, SAM_MODEL, BUILD_SKIN, BUILD_FLAT, PAPER_DISP, PAPER_ROUGH, UV_AUDIT_AFTER]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing preflight files: " + ", ".join(missing))
    source = BUILD_FLAT.read_text(encoding="utf-8")
    markers = {
        "mask_row_origin_fix": "mask = np.flipud" in source,
        "raw_v_direction_fix": '"raw_fbx_contract": "du/dY < 0" if coordinate_component == 1 else "dv/dZ > 0"' in source,
        "uv1_interchange_precompensation": "metric_uv = (-co.y, 1.0 - co.z)" in source,
        "lod_group_builder": 'group["fbx_type"] = "LodGroup"' in source,
        "lod_group_validator": '"fbx_lod_group": raw_lod_group' in source,
        "coverage_under_point_one_percent": "fraction < 0.001" in source,
        "frame_containment_gate": 'raise RuntimeError(f"Head-on frame containment failed' in source,
    }
    audit = json.loads(UV_AUDIT_AFTER.read_text(encoding="utf-8"))
    slopes = []
    for file_record in audit.get("files", []):
        for obj in file_record.get("objects", []):
            front = obj.get("sections", {}).get("Front")
            if front:
                slopes.append(float(front["dv_dZ"]["slope_per_m"]))
    markers["saved_after_audit_raw_dv_dz_positive"] = bool(slopes) and all(value > 0 for value in slopes)
    if not all(markers.values()):
        raise RuntimeError("STOP: required LOD/V-flip/validation fix absent: " + json.dumps(markers))
    blender_version = subprocess.run([str(BLENDER), "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    if not blender_version.startswith("Blender 4.4"):
        raise RuntimeError(f"STOP: Blender 4.4 required, got {blender_version}")
    payload = json.loads(PICKS_PATH.read_text(encoding="utf-8"))
    picks, skipped = select_picks(payload)
    all_picks = payload["build_picks"]
    missing_sources = [pick["canonical_path"] for pick in picks if not (PROJECT / pick["canonical_path"]).is_file()]
    if missing_sources:
        raise FileNotFoundError("Missing picks: " + ", ".join(missing_sources))
    source_hash_mismatches = []
    alpha_checks = []
    for pick in picks:
        source = PROJECT / pick["canonical_path"]
        actual_hash = sha256(source)
        declared_hash = pick.get("source_sha256")
        if declared_hash and actual_hash != declared_hash:
            source_hash_mismatches.append({
                "source": pick["canonical_path"], "declared": declared_hash,
                "actual": actual_hash,
            })
        alpha_mode = normalise_alpha_mode(pick.get("alpha_mode") or "embedded_alpha")
        if alpha_mode == "chroma":
            _, alpha, stats = chroma_alpha_cut(source)
            alpha_checks.append({
                "source": pick["canonical_path"], "mode": alpha_mode,
                "min": int(alpha.min()), "max": int(alpha.max()),
                "soft_alpha_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
                "pass": bool(stats["despill_pass"] and stats["border_nontransparent_percent"] <= 1.0),
                "stats": stats,
            })
        elif alpha_mode == "opacity_mask":
            _, alpha, stats = opacity_mask_cut(source)
            alpha_checks.append({
                "source": pick["canonical_path"], "mode": alpha_mode,
                "min": int(alpha.min()), "max": int(alpha.max()),
                "soft_alpha_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
                "pass": bool(stats["old_unreal_opacity_mask_validation_pass"]),
                "stats": stats,
            })
        elif alpha_mode == "lab_colour_key":
            rgb = read_rgb(source)
            mask, stats = colour_key(rgb, float(pick["target_height_cm"]))
            mask, jigsaw_stats = jigsaw(mask, float(pick["target_height_cm"]))
            alpha = mask.astype(np.uint8) * 255
            border = max(1, min(alpha.shape) // 90)
            border_pixels = np.concatenate((
                alpha[:border].ravel(), alpha[-border:].ravel(),
                alpha[:, :border].ravel(), alpha[:, -border:].ravel(),
            ))
            border_nontransparent_percent = float((border_pixels > 0).mean() * 100.0)
            stats["jigsaw"] = jigsaw_stats
            stats["border_nontransparent_percent"] = round(border_nontransparent_percent, 6)
            alpha_checks.append({
                "source": pick["canonical_path"], "mode": alpha_mode,
                "min": int(alpha.min()), "max": int(alpha.max()),
                "pass": bool(int(alpha.min()) == 0 and int(alpha.max()) == 255
                             and border_nontransparent_percent <= 1.0),
                "stats": stats,
            })
        else:
            _, alpha = read_rgb_and_alpha(source)
            alpha_checks.append({
                "source": pick["canonical_path"], "mode": alpha_mode,
                "min": int(alpha.min()), "max": int(alpha.max()),
                "pass": int(alpha.min()) < 255 and int(alpha.max()) > 0,
            })
    failed_alpha_checks = [check["source"] for check in alpha_checks if not check["pass"]]
    if failed_alpha_checks:
        raise RuntimeError("STOP: alpha coverage/despill gate failed: " + ", ".join(failed_alpha_checks))
    if source_hash_mismatches:
        raise RuntimeError("STOP: kept source SHA-256 mismatch: " + json.dumps(source_hash_mismatches))
    skip_counts: dict[str, int] = {}
    for item in skipped:
        item_categories: set[str] = set()
        for reason in item["reasons"]:
            key = "uncertain" if re.search(r"(?i)inferred|unclear", reason) else reason
            item_categories.add(key)
        for key in item_categories:
            skip_counts[key] = skip_counts.get(key, 0) + 1
    declared_ready = payload.get("selection_summary", {}).get("build_ready_with_embedded_alpha")
    expected_count = payload.get("expected_asset_count")
    if expected_count is not None and len(picks) != int(expected_count):
        raise RuntimeError(f"STOP: expected {expected_count} scheduled assets, got {len(picks)}")
    work_items = build_work_items(picks)
    expected_names = payload.get("expected_asset_names")
    actual_names = [item.asset_name for item in work_items]
    if expected_names is not None and sorted(actual_names) != sorted(expected_names):
        raise RuntimeError("STOP: scheduled asset names differ from the declared exact-name gate")
    return {
        "schema_version": 1, "time": now(), "pass": True, "blender": blender_version,
        "markers": markers, "raw_front_dv_dz_slopes": slopes,
        "input_pick_count": len(all_picks), "declared_alpha_ready_count": declared_ready,
        "scheduled_count": len(picks), "skipped_count": len(skipped), "skip_reason_counts": skip_counts,
        "selection_note": payload.get("selection_note") or (
            "KEPT_PICKS declares alpha-ready only; strict user gate also excludes every inferred/UNCLEAR entry"
            if is_kept_payload(payload) else "all input picks scheduled"
        ),
        "source_hashes_match": not source_hash_mismatches,
        "alpha_checks": alpha_checks,
        "exact_asset_names": actual_names,
        "exact_asset_name_gate_pass": expected_names is None or sorted(actual_names) == sorted(expected_names),
        "network_used": False, "unreal_used": False, "generation_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="Check all stop conditions without building")
    parser.add_argument(
        "--picks", type=Path, default=PICKS_PATH,
        help="BUILD_PICKS.json or KEPT_PICKS.json input (default: Fuser queue BUILD_PICKS.json)",
    )
    parser.add_argument(
        "--output", type=Path,
        help="Batch output root (default: Overnight, or Overnight/Kept for KEPT_PICKS.json)",
    )
    parser.add_argument(
        "--repair-from-stage4", action="append", default=[], metavar="ASSET_SUFFIX",
        help="Repair one failed item from its existing Stage 4 art/mask without loading the upscaler",
    )
    parser.add_argument(
        "--repair", action="append", default=[], metavar="ASSET_SUFFIX",
        help="Rerun the full pipeline for one failed item and merge it into the existing manifest",
    )
    parser.add_argument(
        "--cpu-contact-render", action="store_true",
        help=("With --repair-from-stage4 only, keep the repair off the shared GPU by using "
              "Cycles CPU for the two contact renders; SAM/upscaling must already be staged"),
    )
    args = parser.parse_args()
    if args.cpu_contact_render and not args.repair_from_stage4:
        parser.error("--cpu-contact-render is valid only with --repair-from-stage4")
    picks_path = args.picks if args.picks.is_absolute() else PROJECT / args.picks
    default_output = DERIVED / "Overnight" / "Kept" if picks_path.name.upper() == "KEPT_PICKS.JSON" else DERIVED / "Overnight"
    output_path = args.output or default_output
    if not output_path.is_absolute():
        output_path = PROJECT / output_path
    configure_batch_paths(picks_path, output_path)
    OUT.mkdir(parents=True, exist_ok=True); FLATS.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True); SHARED.mkdir(exist_ok=True)
    proof = preflight()
    atomic_json(OUT / "PREFLIGHT.json", proof)
    if args.preflight:
        print("FLAT_V3_BATCH_PREFLIGHT_PASS " + json.dumps({
            "markers": proof["markers"], "scheduled": proof["scheduled_count"],
            "skipped": proof["skipped_count"], "skip_reasons": proof["skip_reason_counts"],
        }), flush=True)
        return 0

    payload = json.loads(PICKS_PATH.read_text(encoding="utf-8"))
    picks, skipped = select_picks(payload)
    overlays = prepare_shared_overlays()
    items = build_work_items(picks)
    soft_alpha_artifacts = ensure_soft_alpha_artifacts(items)
    atomic_json(OUT / "SKIPPED.json", {
        "schema_version": 1, "created": now(), "count": len(skipped), "items": skipped,
    })
    if is_kept_payload(payload) or payload.get("mapping_filename"):
        write_kept_map(items, str(payload.get("mapping_filename") or "KEPT_MAP.json"))
    if args.repair:
        targets = set(args.repair)
        by_suffix = {item.asset_suffix: item for item in items}
        unknown = sorted(targets - set(by_suffix))
        if unknown:
            raise RuntimeError("Unknown repair asset suffixes: " + ", ".join(unknown))
        manifest_path = OUT / "MANIFEST.json"
        if not manifest_path.is_file():
            raise FileNotFoundError("Cannot repair without the existing batch MANIFEST.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        repair_started = now()
        manifest.update({
            "status": "running", "finished": None, "fatal": None,
            "driver": str(Path(__file__).resolve()), "driver_sha256": sha256(Path(__file__)),
            "preflight": proof, "overlays": overlays, "repair_started": repair_started,
            "repair_mode": "full_pipeline", "repair_targets": sorted(targets),
            "soft_alpha_artifacts": soft_alpha_artifacts,
        })
        statuses = []
        for item in items:
            status_path = item.folder / "status.json"
            if not status_path.is_file():
                raise FileNotFoundError(f"Missing status for repair census: {status_path}")
            statuses.append(json.loads(status_path.read_text(encoding="utf-8")))
        gate = wait_for_gpu_slot(GPU_MARKER)
        manifest["gpu_gate"] = gate
        write_running_state({
            "started": repair_started, "pid": os.getpid(), "status": "running",
            "repair_mode": "full_pipeline", "repair_targets": sorted(targets),
            "batch_output": str(OUT),
        })
        atomic_json(manifest_path, manifest)
        fatal = None
        sam_refiner: SAMChromaRefiner | None = None
        upscaler: Upscaler | None = None
        try:
            target_items = [by_suffix[target] for target in sorted(targets)]
            if any(item.cut_method == "chroma" for item in target_items):
                sam_refiner = SAMChromaRefiner()
                manifest["sam_refiner"] = {
                    "checkpoint": str(SAM_MODEL), "config": SAM_CONFIG,
                    "setup_seconds": sam_refiner.setup_seconds,
                }
            upscaler = Upscaler()
            manifest["upscaler_load_count"] = upscaler.loads
            for target in sorted(targets):
                assert upscaler is not None
                repaired = build_one(by_suffix[target], upscaler, sam_refiner)
                statuses = [repaired if value.get("asset_suffix") == target else value for value in statuses]
                manifest["items"] = statuses
                manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
                manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
                atomic_json(manifest_path, manifest)
            validate_shared_pole(manifest)
        except Exception:
            fatal = traceback.format_exc()
        finally:
            if sam_refiner is not None:
                manifest.setdefault("sam_refiner", {})["calls"] = sam_refiner.calls
                sam_refiner.close()
            manifest["items"] = statuses
            manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
            manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
            manifest["finished"] = now()
            manifest["status"] = "fatal" if fatal else ("complete_with_failures" if manifest["failure_count"] else "complete")
            manifest["fatal"] = fatal
            atomic_json(manifest_path, manifest)
            make_contact_sheet(statuses)
            write_failures(statuses, fatal, skipped)
            write_batch_summary(statuses, payload, skipped, fatal)
            atomic_json(OUT / "DONE.json", {
                "finished": manifest["finished"], "status": manifest["status"],
                "built": manifest["built_count"], "failed": manifest["failure_count"],
            })
            terminal_status = "done" if not fatal and not manifest["failure_count"] else "fatal"
            write_running_state({
                "started": repair_started, "pid": os.getpid(), "status": terminal_status,
                "batch_status": manifest["status"], "finished": manifest["finished"],
                "repair_mode": "full_pipeline", "repair_targets": sorted(targets),
                "batch_output": str(OUT),
            })
        print(json.dumps({
            "status": manifest["status"], "built": manifest["built_count"],
            "failed": manifest["failure_count"], "repair_targets": sorted(targets),
        }), flush=True)
        return 2 if fatal or manifest["failure_count"] else 0
    if args.repair_from_stage4:
        targets = set(args.repair_from_stage4)
        by_suffix = {item.asset_suffix: item for item in items}
        unknown = sorted(targets - set(by_suffix))
        if unknown:
            raise RuntimeError("Unknown repair asset suffixes: " + ", ".join(unknown))
        manifest_path = OUT / "MANIFEST.json"
        if not manifest_path.is_file():
            raise FileNotFoundError("Cannot repair without the existing batch MANIFEST.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        repair_started = now()
        manifest.update({
            "status": "running", "finished": None, "fatal": None,
            "driver": str(Path(__file__).resolve()), "driver_sha256": sha256(Path(__file__)),
            "preflight": proof, "overlays": overlays, "repair_started": repair_started,
            "repair_targets": sorted(targets),
            "soft_alpha_artifacts": soft_alpha_artifacts,
        })
        statuses = []
        for item in items:
            status_path = item.folder / "status.json"
            if not status_path.is_file():
                raise FileNotFoundError(f"Missing status for repair census: {status_path}")
            statuses.append(json.loads(status_path.read_text(encoding="utf-8")))
        if args.cpu_contact_render:
            gate = {
                "marker": str(GPU_MARKER),
                "mode": "cpu_only_stage4_repair",
                "gpu_owner_untouched": True,
                "acquired": now(),
            }
        else:
            gate = wait_for_gpu_slot(GPU_MARKER)
        manifest["gpu_gate"] = gate
        running_state = {
            "started": repair_started, "pid": os.getpid(), "status": "running",
            "repair_targets": sorted(targets), "batch_output": str(OUT),
            "resource_mode": gate.get("mode", "gpu_serialized"),
        }
        if args.cpu_contact_render:
            atomic_json(OUT / "RUNNING.json", running_state)
        else:
            write_running_state(running_state)
        atomic_json(manifest_path, manifest)
        fatal = None
        try:
            for target in sorted(targets):
                repaired = repair_one_from_stage4(
                    by_suffix[target],
                    contact_device="CPU" if args.cpu_contact_render else "GPU",
                )
                statuses = [repaired if value.get("asset_suffix") == target else value for value in statuses]
                manifest["items"] = statuses
                manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
                manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
                atomic_json(manifest_path, manifest)
            validate_shared_pole(manifest)
        except Exception:
            fatal = traceback.format_exc()
        finally:
            manifest["items"] = statuses
            manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
            manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
            manifest["finished"] = now()
            manifest["status"] = "fatal" if fatal else ("complete_with_failures" if manifest["failure_count"] else "complete")
            manifest["fatal"] = fatal
            atomic_json(manifest_path, manifest)
            make_contact_sheet(statuses)
            write_failures(statuses, fatal, skipped)
            write_batch_summary(statuses, payload, skipped, fatal)
            atomic_json(OUT / "DONE.json", {
                "finished": manifest["finished"], "status": manifest["status"],
                "built": manifest["built_count"], "failed": manifest["failure_count"],
            })
            terminal_status = "done" if not fatal and not manifest["failure_count"] else "fatal"
            terminal_state = {
                "started": repair_started, "pid": os.getpid(), "status": terminal_status,
                "batch_status": manifest["status"], "finished": manifest["finished"],
                "repair_targets": sorted(targets), "batch_output": str(OUT),
                "resource_mode": gate.get("mode", "gpu_serialized"),
            }
            if args.cpu_contact_render:
                atomic_json(OUT / "RUNNING.json", terminal_state)
            else:
                write_running_state(terminal_state)
        print(json.dumps({
            "status": manifest["status"], "built": manifest["built_count"],
            "failed": manifest["failure_count"], "repair_targets": sorted(targets),
        }), flush=True)
        return 2 if fatal or manifest["failure_count"] else 0

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA, "started": now(), "status": "running", "driver": str(Path(__file__).resolve()),
        "driver_sha256": sha256(Path(__file__)), "preflight": proof, "source_picks": str(PICKS_PATH),
        "poles_baked_by_default": BAKE_POLES_BY_DEFAULT,
        "overlays": overlays, "scheduled_asset_count": len(items), "upscaler_load_count": 0,
        "input_pick_count": len(payload["build_picks"]), "skipped_count": len(skipped), "skipped": skipped,
        "items": [], "network_used": False, "generation_used": False, "unreal_used": False,
    }
    gate = wait_for_gpu_slot(GPU_MARKER)
    manifest["gpu_gate"] = gate
    write_running_state({
        "started": manifest["started"], "pid": os.getpid(), "status": "running",
        "batch_output": str(OUT), "source_picks": str(PICKS_PATH),
    })
    atomic_json(OUT / "MANIFEST.json", manifest)
    statuses: list[dict[str, Any]] = []
    fatal = None
    upscaler: Upscaler | None = None
    sam_refiner: SAMChromaRefiner | None = None
    try:
        pending = []
        for item in items:
            fingerprint = item_fingerprint(item)
            existing = complete_status(item, fingerprint)
            if existing:
                statuses.append(existing)
            else:
                pending.append(item)
        if pending:
            if any(item.cut_method == "chroma" for item in pending):
                sam_refiner = SAMChromaRefiner()
                manifest["sam_refiner"] = {
                    "checkpoint": str(SAM_MODEL), "config": SAM_CONFIG,
                    "setup_seconds": sam_refiner.setup_seconds,
                }
            upscaler = Upscaler()
            manifest["upscaler_load_count"] = upscaler.loads
        for item in items:
            if any(status.get("asset_suffix") == item.asset_suffix for status in statuses):
                continue
            assert upscaler is not None
            status = build_one(item, upscaler, sam_refiner)
            statuses.append(status)
            manifest["items"] = statuses
            manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
            manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
            atomic_json(OUT / "MANIFEST.json", manifest)
        manifest["items"] = statuses
        validate_shared_pole(manifest)
    except Exception:
        fatal = traceback.format_exc()
    finally:
        if sam_refiner is not None:
            manifest.setdefault("sam_refiner", {})["calls"] = sam_refiner.calls
            sam_refiner.close()
        manifest["items"] = statuses
        manifest["built_count"] = sum(value.get("status") == "built" for value in statuses)
        manifest["failure_count"] = sum(value.get("status") == "failed" for value in statuses)
        manifest["finished"] = now()
        manifest["status"] = "fatal" if fatal else ("complete_with_failures" if manifest["failure_count"] else "complete")
        manifest["fatal"] = fatal
        atomic_json(OUT / "MANIFEST.json", manifest)
        make_contact_sheet(statuses)
        write_failures(statuses, fatal, skipped)
        write_batch_summary(statuses, payload, skipped, fatal)
        atomic_json(OUT / "DONE.json", {"finished": manifest["finished"], "status": manifest["status"], "built": manifest["built_count"], "failed": manifest["failure_count"]})
        terminal_status = "done" if not fatal and not manifest["failure_count"] else "fatal"
        write_running_state({
            "started": manifest["started"], "pid": os.getpid(), "status": terminal_status,
            "batch_status": manifest["status"], "finished": manifest["finished"],
            "batch_output": str(OUT), "source_picks": str(PICKS_PATH),
        })
    print(json.dumps({"status": manifest["status"], "built": manifest["built_count"], "failed": manifest["failure_count"]}), flush=True)
    return 2 if fatal or manifest["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
