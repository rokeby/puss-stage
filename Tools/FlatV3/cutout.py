# Conductor-approved Flat V3 cutout tool; promoted from the A/A2 pilot test.
from __future__ import annotations

import gc
import hashlib
import html
import inspect
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from shapely.geometry import Polygon
from skimage.segmentation import slic


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(r"D:\PussStageSources\FlatV3")
TOOL_ROOT = Path(os.environ.get("FLATV3_ROOT", r"D:\PussStageTools\FlatV3"))
STAGE_GREY = (31, 34, 38)
SEGMENT_MAX = 1280
LAMA_MAX = 1536
FONT = ImageFont.load_default()


@dataclass(frozen=True)
class ElementSpec:
    key: str
    example: str
    label: str
    side: str
    target_height_cm: float
    roi: tuple[float, float, float, float]
    preferred_candidate: str


@dataclass(frozen=True)
class SourceSpec:
    example: str
    source_id: str
    source_path: Path
    metadata_path: Path
    prompt: str
    selection_reason: str
    elements: tuple[ElementSpec, ...]


SOURCES = (
    SourceSpec(
        example="A",
        source_id="SMK-KMS3366",
        source_path=SOURCE_ROOT / "P02" / "smk_KMS3366" / "original.jpg",
        metadata_path=SOURCE_ROOT / "P02" / "smk_KMS3366" / "source.json",
        prompt="oak tree.",
        selection_reason="The painting has distinct left and right oak masses already framing a road; using both avoids mirroring.",
        elements=(
            ElementSpec("A_L", "A", "left oak mass", "L", 1000.0, (0.005, 0.015, 0.505, 0.965), "roi_sam_A_L_1"),
            ElementSpec("A_R", "A", "right oak mass", "R", 1000.0, (0.485, 0.105, 0.995, 0.965), "roi_sam_A_R_1"),
        ),
    ),
    SourceSpec(
        example="B",
        source_id="MET-361510",
        source_path=SOURCE_ROOT / "SEA_ROWS" / "met_361510" / "original.jpg",
        metadata_path=SOURCE_ROOT / "SEA_ROWS" / "met_361510" / "source.json",
        prompt="ocean wave crest.",
        selection_reason="361510 has the longest legible foreground crest/trough run before the large right-hand ship interrupts it.",
        elements=(
            ElementSpec("B_ROW", "B", "foreground wave crest band", "ROW", 120.0, (0.015, 0.39, 0.805, 0.93), "roi_sam_B_ROW_2"),
        ),
    ),
    SourceSpec(
        example="C",
        source_id="MET-700415",
        source_path=SOURCE_ROOT / "REFERENCE" / "met_700415" / "original.jpg",
        metadata_path=SOURCE_ROOT / "REFERENCE" / "met_700415" / "source.json",
        prompt="theatrical cloud column.",
        selection_reason="The left cloud-and-column bank is a single wing-like mass with a straight architectural outside edge and a lively cloud edge.",
        elements=(
            ElementSpec("C_WING", "C", "left cloud and column wing", "L", 1000.0, (0.012, 0.035, 0.455, 0.965), "roi_sam_C_WING_2"),
        ),
    ),
)


def ensure_dirs() -> None:
    for name in ("A", "B", "C"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    (ROOT / "C" / "nano_banana_pack").mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def save_rgb(path: Path, rgb: np.ndarray, quality: int = 94) -> None:
    image = Image.fromarray(np.asarray(rgb, dtype=np.uint8), "RGB")
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image.save(path, quality=quality, subsampling=0, optimize=True)
    else:
        image.save(path)


def save_mask(path: Path, mask: np.ndarray) -> None:
    Image.fromarray((mask.astype(np.uint8) * 255), "L").save(path)


def save_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    rgba = np.dstack([np.asarray(rgb, dtype=np.uint8), np.asarray(alpha, dtype=np.uint8)])
    Image.fromarray(rgba, "RGBA").save(path, compress_level=6)


def resize_fit(rgb: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale == 1.0:
        return rgb.copy(), 1.0
    out = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return out, scale


def roi_pixels(roi: tuple[float, float, float, float], w: int, h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = roi
    return (
        max(0, min(w - 1, round(x0 * w))),
        max(0, min(h - 1, round(y0 * h))),
        max(1, min(w, round(x1 * w))),
        max(1, min(h, round(y1 * h))),
    )


def cuda_begin() -> None:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()


def cuda_end(started: float) -> dict[str, float]:
    torch.cuda.synchronize()
    return {
        "seconds": round(time.perf_counter() - started, 4),
        "peak_vram_mib": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 3),
        "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / (1024 * 1024), 3),
    }


def overlay(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], alpha: float = 0.48) -> np.ndarray:
    out = rgb.astype(np.float32).copy()
    out[mask] = out[mask] * (1 - alpha) + np.array(color, dtype=np.float32) * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def label_image(rgb: np.ndarray, text: str) -> Image.Image:
    im = Image.fromarray(rgb)
    bar = Image.new("RGB", (im.width, 30), (245, 242, 232))
    draw = ImageDraw.Draw(bar)
    draw.text((7, 8), text, fill=(20, 20, 20), font=FONT)
    result = Image.new("RGB", (im.width, im.height + bar.height), (255, 255, 255))
    result.paste(bar, (0, 0))
    result.paste(im, (0, bar.height))
    return result


def contact_sheet(entries: list[tuple[str, np.ndarray]], path: Path, cell_w: int = 430, cols: int = 3) -> None:
    cards: list[Image.Image] = []
    for label, rgb in entries:
        image = Image.fromarray(rgb)
        image.thumbnail((cell_w, 310), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (cell_w, 350), (230, 230, 230))
        canvas.paste(image, ((cell_w - image.width) // 2, 32))
        ImageDraw.Draw(canvas).text((7, 8), label, fill=(15, 15, 15), font=FONT)
        cards.append(canvas)
    rows = math.ceil(len(cards) / cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * 350), (48, 48, 48))
    for index, card in enumerate(cards):
        sheet.paste(card, ((index % cols) * cell_w, (index // cols) * 350))
    sheet.save(path, quality=92, subsampling=0)


def post_process_grounding(processor: Any, outputs: Any, input_ids: torch.Tensor, size: tuple[int, int]) -> Any:
    function = processor.post_process_grounded_object_detection
    params = inspect.signature(function).parameters
    kwargs: dict[str, Any] = {
        "outputs": outputs,
        "input_ids": input_ids,
        "target_sizes": [size],
        "text_threshold": 0.16,
    }
    if "box_threshold" in params:
        kwargs["box_threshold"] = 0.16
    else:
        kwargs["threshold"] = 0.16
    return function(**kwargs)[0]


def mask_score(mask: np.ndarray, roi_box: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = roi_box
    roi = np.zeros_like(mask, dtype=bool)
    roi[y0:y1, x0:x1] = True
    inter = float(np.logical_and(mask, roi).sum())
    mask_area = max(1.0, float(mask.sum()))
    roi_area = max(1.0, float(roi.sum()))
    coverage = inter / roi_area
    precision = inter / mask_area
    oversize = max(0.0, mask_area / roi_area - 1.2)
    return 1.2 * coverage + 0.55 * precision - 0.25 * oversize


def candidate_sheet_for_element(
    seg_rgb: np.ndarray,
    candidates: list[dict[str, Any]],
    element: ElementSpec,
    out_dir: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    h, w = seg_rgb.shape[:2]
    roi = roi_pixels(element.roi, w, h)
    ranked = sorted(candidates, key=lambda c: mask_score(c["mask"], roi), reverse=True)
    preferred = [c for c in ranked if c["id"] == element.preferred_candidate]
    if not preferred:
        preferred = [c for c in ranked if c["kind"] == element.preferred_candidate]
    chosen = preferred[0] if preferred else ranked[0]
    entries: list[tuple[str, np.ndarray]] = []
    colors = [(229, 57, 53), (0, 150, 136), (63, 81, 181), (255, 152, 0), (156, 39, 176), (0, 188, 212)]
    for i, candidate in enumerate(ranked[:11]):
        score = mask_score(candidate["mask"], roi)
        label = f"{candidate['id']} | {candidate['kind']} | ROI score {score:.3f}"
        entries.append((label, overlay(seg_rgb, candidate["mask"], colors[i % len(colors)])))
    roi_view = seg_rgb.copy()
    cv2.rectangle(roi_view, (roi[0], roi[1]), (roi[2] - 1, roi[3] - 1), (255, 40, 40), 4)
    entries.insert(0, ("human selection ROI (input to ROI-SAM candidate)", roi_view))
    contact_sheet(entries, out_dir / f"stage1_{element.key}_candidate_masks.jpg")
    save_mask(out_dir / f"stage1_{element.key}_chosen_mask.png", chosen["mask"])
    save_rgb(out_dir / f"stage1_{element.key}_chosen_overlay.jpg", overlay(seg_rgb, chosen["mask"], (255, 54, 79)))
    decision = {
        "chosen_candidate_id": chosen["id"],
        "chosen_kind": chosen["kind"],
        "selection_method": "human review of the candidate sheet; exact preferred candidate id, with ROI score only as fallback",
        "selection_reason": "The reviewed candidate best isolates the requested physical mass; model score alone was not treated as an artistic verdict.",
        "roi_normalized": list(element.roi),
        "candidate_count": len(candidates),
        "top_candidates": [
            {
                "id": c["id"],
                "kind": c["kind"],
                "roi_score": round(mask_score(c["mask"], roi), 6),
                "model_score": c.get("model_score"),
                "area_px": int(c["mask"].sum()),
            }
            for c in ranked[:12]
        ],
    }
    return chosen["mask"], decision


def run_segmentation(metrics: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by the declared local toolchain")
    setup_started = time.perf_counter()
    sam = build_sam2(
        "configs/sam2.1/sam2.1_hiera_l.yaml",
        str(TOOL_ROOT / "models" / "sam2.1_hiera_large.pt"),
        device="cuda",
    )
    auto = SAM2AutomaticMaskGenerator(
        sam,
        points_per_side=24,
        points_per_batch=64,
        pred_iou_thresh=0.72,
        stability_score_thresh=0.84,
        crop_n_layers=0,
        min_mask_region_area=180,
    )
    predictor = SAM2ImagePredictor(sam)
    revision = "12bdfa3120f3e7ec7b434d90674b3396eccf88eb"
    processor = AutoProcessor.from_pretrained(
        "IDEA-Research/grounding-dino-base", revision=revision, local_files_only=True
    )
    dino = AutoModelForZeroShotObjectDetection.from_pretrained(
        "IDEA-Research/grounding-dino-base", revision=revision, local_files_only=True
    ).to("cuda").eval()
    metrics["shared_model_setup"] = {
        "seconds": round(time.perf_counter() - setup_started, 4),
        "sam_checkpoint": str(TOOL_ROOT / "models" / "sam2.1_hiera_large.pt"),
        "grounding_dino_revision": revision,
        "offline_flags": {key: os.environ.get(key) for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")},
    }

    for source in SOURCES:
        out_dir = ROOT / source.example
        full_rgb = read_rgb(source.source_path)
        seg_rgb, seg_scale = resize_fit(full_rgb, SEGMENT_MAX)
        save_rgb(out_dir / "00_source_preview.jpg", seg_rgb)
        cuda_begin()
        started = time.perf_counter()
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            auto_records = auto.generate(seg_rgb)
        auto_candidates: list[dict[str, Any]] = []
        for index, record in enumerate(sorted(auto_records, key=lambda r: float(r["predicted_iou"]), reverse=True)[:80]):
            area_fraction = float(record["area"]) / (seg_rgb.shape[0] * seg_rgb.shape[1])
            if 0.003 <= area_fraction <= 0.88:
                auto_candidates.append(
                    {
                        "id": f"auto_{index:02d}",
                        "kind": "sam_auto",
                        "mask": record["segmentation"].astype(bool),
                        "model_score": round(float(record["predicted_iou"]), 6),
                    }
                )

        batch = processor(images=Image.fromarray(seg_rgb), text=source.prompt, return_tensors="pt")
        cuda_batch = {key: value.to("cuda") for key, value in batch.items()}
        with torch.inference_mode():
            outputs = dino(**cuda_batch)
        dino_result = post_process_grounding(
            processor, outputs, cuda_batch["input_ids"], (seg_rgb.shape[0], seg_rgb.shape[1])
        )
        dino_boxes = dino_result["boxes"].detach().cpu().numpy()
        dino_scores = dino_result["scores"].detach().cpu().numpy()
        dino_labels = [str(x) for x in dino_result.get("labels", [])]
        predictor.set_image(seg_rgb)
        dino_candidates: list[dict[str, Any]] = []
        dino_overlay = seg_rgb.copy()
        for index, (box, score) in enumerate(zip(dino_boxes[:12], dino_scores[:12])):
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                masks, sam_scores, _ = predictor.predict(
                    point_coords=None,
                    point_labels=None,
                    box=box.astype(np.float32),
                    multimask_output=True,
                )
            best = int(np.argmax(sam_scores))
            dino_candidates.append(
                {
                    "id": f"dino_sam_{index:02d}",
                    "kind": "dino_sam",
                    "mask": masks[best].astype(bool),
                    "model_score": round(float(score), 6),
                    "sam_score": round(float(sam_scores[best]), 6),
                }
            )
            x0, y0, x1, y1 = box.round().astype(int)
            cv2.rectangle(dino_overlay, (x0, y0), (x1, y1), (255, 45, 45), 3)
            cv2.putText(dino_overlay, f"{index}:{score:.2f}", (x0, max(16, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 45, 45), 2, cv2.LINE_AA)
        save_rgb(out_dir / "stage1_grounding_dino_boxes.jpg", dino_overlay)

        timing = cuda_end(started)
        timing.update(
            {
                "segmentation_size_px": [int(seg_rgb.shape[1]), int(seg_rgb.shape[0])],
                "source_size_px": [int(full_rgb.shape[1]), int(full_rgb.shape[0])],
                "sam_auto_proposals_raw": len(auto_records),
                "sam_auto_candidates_retained": len(auto_candidates),
                "grounding_dino_box_count": len(dino_boxes),
                "grounding_dino_prompt": source.prompt,
                "grounding_dino_scores": [round(float(v), 6) for v in dino_scores.tolist()],
                "grounding_dino_labels": dino_labels,
            }
        )
        metrics["examples"][source.example]["stage1_segmentation"] = timing
        metrics["examples"][source.example]["source_selection_reason"] = source.selection_reason
        metrics["examples"][source.example]["source_sha256_before"] = sha256(source.source_path)

        candidates = auto_candidates + dino_candidates
        for element in source.elements:
            x0, y0, x1, y1 = roi_pixels(element.roi, seg_rgb.shape[1], seg_rgb.shape[0])
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                roi_masks, roi_scores, _ = predictor.predict(
                    point_coords=None,
                    point_labels=None,
                    box=np.array([x0, y0, x1, y1], dtype=np.float32),
                    multimask_output=True,
                )
            for idx in range(roi_masks.shape[0]):
                candidates.append(
                    {
                        "id": f"roi_sam_{element.key}_{idx}",
                        "kind": "roi_sam",
                        "mask": roi_masks[idx].astype(bool),
                        "model_score": round(float(roi_scores[idx]), 6),
                    }
                )
            chosen_seg, decision = candidate_sheet_for_element(seg_rgb, candidates, element, out_dir)
            full_mask = cv2.resize(
                chosen_seg.astype(np.uint8),
                (full_rgb.shape[1], full_rgb.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
            states[element.key] = {
                "source": source,
                "element": element,
                "source_rgb": full_rgb,
                "model_mask": full_mask,
                "stage1_decision": decision,
            }
            metrics["examples"][source.example]["elements"][element.key] = {"stage1_decision": decision}
        del full_rgb, seg_rgb, cuda_batch, outputs
        gc.collect()

    del auto, predictor, sam, dino, processor
    gc.collect()
    torch.cuda.empty_cache()


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask.astype(bool)
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == index


def envelope_geometry(mask: np.ndarray, element: ElementSpec) -> np.ndarray:
    h, w = mask.shape
    x0, y0, x1, y1 = roi_pixels(element.roi, w, h)
    clipped = np.zeros_like(mask, dtype=bool)
    clipped[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
    clipped = largest_component(clipped)
    geometry = np.zeros_like(clipped)
    if element.side == "ROW":
        xs: list[int] = []
        tops: list[float] = []
        for x in range(x0, x1):
            ys = np.flatnonzero(clipped[y0:y1, x]) + y0
            if ys.size:
                usable = ys[ys >= y0 + int((y1 - y0) * 0.1)]
                if usable.size:
                    xs.append(x)
                    tops.append(float(np.percentile(usable, 8)))
        if len(xs) < 20:
            # Explicit fallback: a contrast-derived crest line within the declared ROI.
            gray = cv2.cvtColor(np.asarray(Image.fromarray(np.dstack([mask] * 3).astype(np.uint8) * 255)), cv2.COLOR_RGB2GRAY)
            for x in range(x0, x1):
                col = gray[y0:y1, x]
                xs.append(x)
                tops.append(float(y0 + np.argmax(col)))
        top_curve = np.interp(np.arange(x0, x1), np.asarray(xs), np.asarray(tops))
        top_curve = ndimage.median_filter(top_curve, size=max(5, int((x1 - x0) * 0.009)))
        for offset, x in enumerate(range(x0, x1)):
            top = int(np.clip(round(top_curve[offset]), y0, y1 - 2))
            geometry[top:y1, x] = True
    else:
        rows: list[int] = []
        edges: list[float] = []
        for y in range(y0, y1):
            xs = np.flatnonzero(clipped[y, x0:x1]) + x0
            if xs.size:
                rows.append(y)
                edges.append(float(xs.max() if element.side == "L" else xs.min()))
        if len(rows) < 20:
            raise RuntimeError(f"{element.key}: chosen mask has no usable mass inside ROI")
        row_axis = np.arange(min(rows), max(rows) + 1)
        edge_curve = np.interp(row_axis, np.asarray(rows), np.asarray(edges))
        edge_curve = ndimage.median_filter(edge_curve, size=max(5, int((y1 - y0) * 0.007)))
        for offset, y in enumerate(row_axis):
            edge = int(np.clip(round(edge_curve[offset]), x0 + 1, x1 - 1))
            if element.side == "L":
                geometry[y, x0 : edge + 1] = True
            else:
                geometry[y, edge:x1] = True
        geometry[max(rows) : y1, x0:x1] = True
    return largest_component(geometry)


def contour_vertex_count(mask: np.ndarray) -> int:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return int(sum(len(c) for c in contours))


def smooth_at_physical_scale(mask: np.ndarray, target_height_cm: float) -> tuple[np.ndarray, dict[str, Any]]:
    ys, xs = np.where(mask)
    height_px = int(ys.max() - ys.min() + 1)
    cm_per_px = target_height_cm / height_px
    feature_px = max(3, round(3.0 / cm_per_px))
    if feature_px % 2 == 0:
        feature_px += 1
    radius_px = max(2, round(2.0 / cm_per_px))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (feature_px, feature_px))
    work = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    work = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
    sigma = max(0.8, radius_px / 2.0)
    blur = cv2.GaussianBlur(work.astype(np.float32), (0, 0), sigmaX=sigma, sigmaY=sigma)
    smooth_raster = largest_component(blur >= 0.50)
    contours, _ = cv2.findContours(smooth_raster.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    vector_epsilon_cm = 0.75
    vector_epsilon_px = max(1.0, vector_epsilon_cm / cm_per_px)
    simplified = cv2.approxPolyDP(contour, vector_epsilon_px, True)
    smooth = np.zeros_like(smooth_raster, dtype=np.uint8)
    cv2.fillPoly(smooth, [simplified], 1)
    smooth = smooth.astype(bool)
    before_area = int(mask.sum())
    after_area = int(smooth.sum())
    metrics = {
        "target_height_cm": target_height_cm,
        "geometry_height_px": height_px,
        "cm_per_source_pixel": round(cm_per_px, 6),
        "jigsaw_min_feature_cm": 3.0,
        "jigsaw_kernel_px": feature_px,
        "target_curve_radius_cm": 2.0,
        "gaussian_sigma_px": round(sigma, 4),
        "before_vertex_count": contour_vertex_count(mask),
        "after_vertex_count": int(len(simplified)),
        "after_raster_contour_sample_count": contour_vertex_count(smooth_raster),
        "vector_simplification_epsilon_cm": vector_epsilon_cm,
        "vector_simplification_epsilon_px": round(vector_epsilon_px, 4),
        "before_area_px": before_area,
        "after_area_px": after_area,
        "area_change_percent": round((after_area - before_area) * 100.0 / before_area, 4),
    }
    return smooth, metrics


def crop_bounds(mask: np.ndarray, pad: int) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return (
        max(0, int(xs.min()) - pad),
        max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + pad + 1),
        min(mask.shape[0], int(ys.max()) + pad + 1),
    )


def draw_outline(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int] = (255, 43, 43), width: int = 6) -> np.ndarray:
    out = rgb.copy()
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, contours, -1, color, width, lineType=cv2.LINE_AA)
    return out


def run_jigsaw(metrics: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    for key, state in states.items():
        started = time.perf_counter()
        element: ElementSpec = state["element"]
        source_rgb = state["source_rgb"]
        raw_geometry = envelope_geometry(state["model_mask"], element)
        smooth, geom_metrics = smooth_at_physical_scale(raw_geometry, element.target_height_cm)
        ys, _ = np.where(smooth)
        cm_per_px = element.target_height_cm / (ys.max() - ys.min() + 1)
        bleed_px = max(1, round(5.0 / cm_per_px))
        pad_px = max(12, bleed_px + 8)
        bounds = crop_bounds(smooth, pad_px)
        x0, y0, x1, y1 = bounds
        crop_rgb = source_rgb[y0:y1, x0:x1]
        crop_raw = raw_geometry[y0:y1, x0:x1]
        crop_smooth = smooth[y0:y1, x0:x1]
        out_dir = ROOT / element.example
        save_mask(out_dir / f"stage2_{key}_before_jigsaw.png", crop_raw)
        save_mask(out_dir / f"stage2_{key}_jigsaw_mask.png", crop_smooth)
        save_rgb(out_dir / f"stage2_{key}_outline_over_original.jpg", draw_outline(crop_rgb, crop_smooth, width=max(2, round(0.6 / cm_per_px))))
        geom_metrics.update(
            {
                "seconds": round(time.perf_counter() - started, 4),
                "peak_vram_mib": 0.0,
                "crop_bounds_source_xyxy": list(bounds),
                "crop_size_px": [int(crop_rgb.shape[1]), int(crop_rgb.shape[0])],
                "bleed_cm": 5.0,
                "bleed_px_at_native_scale": bleed_px,
                "constraint_status": "physical-kernel-enforced; minimum radius is an approximate smoothing target, not a CAD curvature proof",
            }
        )
        state.update(
            {
                "geometry_full": smooth,
                "crop_rgb": crop_rgb,
                "crop_raw": crop_raw,
                "crop_geometry": crop_smooth,
                "crop_bounds": bounds,
                "cm_per_px": cm_per_px,
                "bleed_px": bleed_px,
            }
        )
        metrics["examples"][element.example]["elements"][key]["stage2_jigsaw"] = geom_metrics


def lama_process(model: Any, rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, list[int]]:
    small, scale = resize_fit(rgb, LAMA_MAX)
    small_mask = cv2.resize(mask.astype(np.uint8), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    result = np.asarray(model(Image.fromarray(small), Image.fromarray(small_mask * 255)).convert("RGB"))
    if scale != 1.0:
        result = cv2.resize(result, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
    return result, [int(small.shape[1]), int(small.shape[0])]


def run_lama(metrics: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    from simple_lama_inpainting import SimpleLama

    model = SimpleLama(device=torch.device("cuda"))
    for key, state in states.items():
        element: ElementSpec = state["element"]
        rgb = state["crop_rgb"]
        geometry = state["crop_geometry"]
        bleed_px = state["bleed_px"]
        cuda_begin()
        started = time.perf_counter()
        background, background_work = lama_process(model, rgb, geometry)
        kernel_size = bleed_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        bleed_mask = cv2.dilate(geometry.astype(np.uint8), kernel).astype(bool)
        ring = np.logical_and(bleed_mask, ~geometry)
        base = rgb.copy()
        # LaMa sees a neutral continuation canvas, not the original background, in the bleed ring.
        border_color = np.median(rgb[geometry], axis=0).astype(np.uint8)
        base[~geometry] = border_color
        bleed_rgb, bleed_work = lama_process(model, base, ring)
        bleed_rgb[geometry] = rgb[geometry]
        stage_timing = cuda_end(started)
        stage_timing.update(
            {
                "background_fill_working_size_px": background_work,
                "bleed_working_size_px": bleed_work,
                "background_fill_mask_pixels_native": int(geometry.sum()),
                "bleed_ring_pixels_native": int(ring.sum()),
                "bleed_cm": 5.0,
            }
        )
        out_dir = ROOT / element.example
        save_rgb(out_dir / f"stage3_{key}_lama_background_fill.jpg", background)
        save_rgba(out_dir / f"stage3_{key}_lama_bleed_art.png", bleed_rgb, bleed_mask.astype(np.uint8) * 255)
        save_mask(out_dir / f"stage3_{key}_geometry_inside_bleed.png", geometry)
        state["bleed_rgb"] = bleed_rgb
        state["bleed_mask"] = bleed_mask
        state["background_fill"] = background
        metrics["examples"][element.example]["elements"][key]["stage3_lama"] = stage_timing
    del model
    gc.collect()
    torch.cuda.empty_cache()


def tensor_from_tile(tile: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(tile.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to("cuda")


def upscale_tiled(descriptor: Any, rgb: np.ndarray, tile: int = 320, overlap: int = 24) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = int(descriptor.scale)
    output = np.zeros((h * scale, w * scale, 3), dtype=np.uint8)
    step = tile - overlap * 2
    ys = list(range(0, h, step))
    xs = list(range(0, w, step))
    for yi, core_y0 in enumerate(ys):
        core_y1 = min(h, core_y0 + step)
        in_y0 = max(0, core_y0 - overlap)
        in_y1 = min(h, core_y1 + overlap)
        for xi, core_x0 in enumerate(xs):
            core_x1 = min(w, core_x0 + step)
            in_x0 = max(0, core_x0 - overlap)
            in_x1 = min(w, core_x1 + overlap)
            patch = rgb[in_y0:in_y1, in_x0:in_x1]
            with torch.inference_mode():
                result = descriptor(tensor_from_tile(patch)).clamp(0, 1)
            result_np = (result[0].permute(1, 2, 0).detach().cpu().numpy() * 255.0).round().astype(np.uint8)
            src_x0 = (core_x0 - in_x0) * scale
            src_y0 = (core_y0 - in_y0) * scale
            src_x1 = src_x0 + (core_x1 - core_x0) * scale
            src_y1 = src_y0 + (core_y1 - core_y0) * scale
            output[core_y0 * scale : core_y1 * scale, core_x0 * scale : core_x1 * scale] = result_np[src_y0:src_y1, src_x0:src_x1]
            if (xi + yi * len(xs)) % 20 == 0:
                print(f"UPSCALE_TILE {xi + yi * len(xs) + 1}/{len(xs) * len(ys)} {w}x{h}", flush=True)
    return output


def save_large_jpeg(path: Path, rgb: np.ndarray) -> None:
    Image.MAX_IMAGE_PIXELS = None
    Image.fromarray(rgb, "RGB").save(path, quality=92, subsampling=0, optimize=False)


def run_upscaler(metrics: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    from spandrel import ModelLoader

    descriptor = ModelLoader().load_from_file(TOOL_ROOT / "models" / "RealESRGAN_x4plus.pth").eval().to("cuda")
    for key, state in states.items():
        element: ElementSpec = state["element"]
        rgb = state["bleed_rgb"]
        geometry = state["crop_geometry"]
        ys, _ = np.where(geometry)
        source_height_px = int(ys.max() - ys.min() + 1)
        native_mm_per_px = element.target_height_cm * 10.0 / source_height_px
        out_dir = ROOT / element.example
        save_rgb(out_dir / f"stage4_{key}_native_rgb.jpg", rgb)
        save_rgba(out_dir / f"stage4_{key}_native_cut.png", rgb, geometry.astype(np.uint8) * 255)
        stage_metrics: dict[str, Any] = {
            "native_element_height_px": source_height_px,
            "target_height_cm": element.target_height_cm,
            "native_mm_per_pixel": round(native_mm_per_px, 6),
            "realesrgan_trigger_threshold_mm_per_pixel": 1.3,
            "realesrgan_required": native_mm_per_px > 1.3,
        }
        if native_mm_per_px > 1.3:
            cuda_begin()
            started = time.perf_counter()
            upscaled = upscale_tiled(descriptor, rgb)
            timing = cuda_end(started)
            up_mask = cv2.resize(geometry.astype(np.uint8), (upscaled.shape[1], upscaled.shape[0]), interpolation=cv2.INTER_NEAREST)
            save_large_jpeg(out_dir / f"stage4_{key}_realesrgan4x_rgb.jpg", upscaled)
            Image.fromarray(up_mask * 255, "L").save(out_dir / f"stage4_{key}_realesrgan4x_geometry.png", compress_level=9)
            preview, _ = resize_fit(upscaled, 1400)
            save_rgb(out_dir / f"stage4_{key}_realesrgan4x_preview.jpg", preview)
            stage_metrics.update(timing)
            stage_metrics.update(
                {
                    "realesrgan_architecture": str(descriptor.architecture.id),
                    "realesrgan_scale": int(descriptor.scale),
                    "upscaled_size_px": [int(upscaled.shape[1]), int(upscaled.shape[0])],
                    "upscaled_mm_per_pixel": round(native_mm_per_px / 4.0, 6),
                    "full_resolution_file": f"stage4_{key}_realesrgan4x_rgb.jpg",
                }
            )
            del upscaled, up_mask
            gc.collect()
        else:
            stage_metrics.update({"seconds": 0.0, "peak_vram_mib": 0.0, "upscaled_mm_per_pixel": None})
        metrics["examples"][element.example]["elements"][key]["stage4_resolution"] = stage_metrics
    del descriptor
    gc.collect()
    torch.cuda.empty_cache()


def dark_preview(rgb: np.ndarray, geometry: np.ndarray, max_side: int = 1600) -> np.ndarray:
    fg, scale = resize_fit(rgb, max_side)
    mask = cv2.resize(geometry.astype(np.uint8) * 255, (fg.shape[1], fg.shape[0]), interpolation=cv2.INTER_AREA)
    canvas = np.full_like(fg, STAGE_GREY, dtype=np.uint8)
    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    return np.clip(fg * alpha + canvas * (1 - alpha), 0, 255).astype(np.uint8)


def physical_one_metre_crop(rgb: np.ndarray, geometry: np.ndarray, cm_per_px: float) -> tuple[np.ndarray, dict[str, Any]]:
    side_px = max(16, round(100.0 / cm_per_px))
    ys, xs = np.where(geometry)
    cx = int(np.median(xs))
    cy = int(np.median(ys))
    x0 = max(0, min(rgb.shape[1] - side_px, cx - side_px // 2))
    y0 = max(0, min(rgb.shape[0] - side_px, cy - side_px // 2))
    crop = rgb[y0 : y0 + side_px, x0 : x0 + side_px]
    return crop, {"physical_size_cm": [100.0, 100.0], "native_crop_size_px": [int(crop.shape[1]), int(crop.shape[0])], "crop_xy": [x0, y0]}


def build_period_colours(ruisdael: np.ndarray, count: int = 7) -> tuple[np.ndarray, np.ndarray]:
    # Deterministic sample from the painting's central illuminated earth/foliage region.
    h, w = ruisdael.shape[:2]
    ref = ruisdael[int(h * 0.22) : int(h * 0.92), int(w * 0.12) : int(w * 0.88)]
    small = cv2.resize(ref, (220, 180), interpolation=cv2.INTER_AREA)
    data = small.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 80, 0.2)
    cv2.setRNGSeed(700415)
    _, labels, centers = cv2.kmeans(data, count, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=count)
    order = np.argsort(-counts)
    return centers[order].clip(0, 255).astype(np.uint8), ref


def colour_c_element(state: dict[str, Any], metrics: dict[str, Any]) -> None:
    rgb = state["crop_rgb"]
    geom = state["crop_geometry"]
    out_dir = ROOT / "C"
    ruisdael = read_rgb(SOURCES[0].source_path)
    palette, palette_ref = build_period_colours(ruisdael)
    # Order swatches from light to dark; reserve darkest for linework.
    lum = palette @ np.array([0.2126, 0.7152, 0.0722])
    palette = palette[np.argsort(lum)]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    paper = np.array([218, 199, 158], dtype=np.float32)
    ink = np.array([48, 39, 30], dtype=np.float32)
    line_strength = np.clip((0.82 - gray) / 0.72, 0, 1)
    tier1 = paper[None, None, :] * (1 - line_strength[..., None]) + ink[None, None, :] * line_strength[..., None]
    tier1 = np.clip(tier1, 0, 255).astype(np.uint8)

    small_rgb, scale = resize_fit(rgb, 1100)
    small_geom = cv2.resize(geom.astype(np.uint8), (small_rgb.shape[1], small_rgb.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    segments = slic(small_rgb, n_segments=110, compactness=18, sigma=1.0, start_label=0, mask=small_geom, channel_axis=2)
    wash_small = np.full_like(small_rgb, paper.astype(np.uint8))
    usable = palette[1:-1] if len(palette) > 3 else palette
    for label in np.unique(segments[small_geom]):
        region = segments == label
        cy, cx = np.mean(np.argwhere(region), axis=0)
        mean_gray = float(np.mean(cv2.cvtColor(small_rgb, cv2.COLOR_RGB2GRAY)[region]))
        index = int((label * 7 + round(cx / max(1, small_rgb.shape[1]) * 5) + round(mean_gray / 32))) % len(usable)
        color = usable[index].astype(np.float32)
        color = 0.68 * color + 0.32 * paper
        wash_small[region] = np.clip(color, 0, 255).astype(np.uint8)
    wash = cv2.resize(wash_small, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    lines = np.clip(1.0 - 0.78 * line_strength[..., None], 0.18, 1.0)
    tier2 = np.clip(wash.astype(np.float32) * lines, 0, 255).astype(np.uint8)

    low_max = 384
    low_w = max(1, round(rgb.shape[1] * low_max / max(rgb.shape[:2])))
    low_h = max(1, round(rgb.shape[0] * low_max / max(rgb.shape[:2])))
    wash_low = cv2.resize(wash, (low_w, low_h), interpolation=cv2.INTER_AREA)
    wash_smooth = cv2.resize(wash_low, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
    hybrid = np.clip(wash_smooth.astype(np.float32) * lines, 0, 255).astype(np.uint8)

    alpha = geom.astype(np.uint8) * 255
    save_rgba(out_dir / "colour_tier1_ink_aged_paper.png", tier1, alpha)
    save_rgba(out_dir / "colour_tier2_hand_tinted_flat_washes.png", tier2, alpha)
    save_rgb(out_dir / "colour_hybrid_lowres_wash.png", wash_low)
    save_rgba(out_dir / "colour_hybrid_fullres_lines.png", hybrid, alpha)
    save_rgb(out_dir / "palette_reference_crop.jpg", palette_ref)
    swatch = np.full((120, 120 * len(palette), 3), 240, dtype=np.uint8)
    for index, color in enumerate(palette):
        swatch[:, index * 120 : (index + 1) * 120] = color
    save_rgb(out_dir / "palette_sampled_swatches.png", swatch)
    state["tier1"] = tier1
    state["tier2"] = tier2
    state["hybrid"] = hybrid
    metrics["examples"]["C"]["colour_versions"] = {
        "method": "deterministic non-generative colour processing",
        "palette_source": "SMK-KMS3366 original, central foliage/earth crop",
        "palette_rgb_dark_to_light": palette.tolist(),
        "tier1": "duotone mapping from full-resolution line luminance to sampled aged-paper and ink colours",
        "tier2": "flat SLIC regions coloured with the sampled palette, with full-resolution lines multiplied above",
        "hybrid": f"wash reduced to {low_w}x{low_h}, bicubic-upscaled, then full-resolution line layer multiplied above",
        "ai_colour_or_generation_used": False,
    }

    pack = out_dir / "nano_banana_pack"
    pack_rgb = hybrid
    pack_alpha = alpha
    pack_image = Image.fromarray(np.dstack([pack_rgb, pack_alpha]), "RGBA")
    pack_image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    pack_image.save(pack / "cropped_element.png")
    ref_image = Image.fromarray(palette_ref)
    ref_image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    ref_image.save(pack / "palette_reference_crop.jpg", quality=94, subsampling=0)
    instruction = (
        "Manual Mac experiment only. Do not run automatically.\n\n"
        "Use cropped_element.png as the exact composition and silhouette. Preserve the original engraved linework, "
        "do not add objects, do not alter handedness, and do not change the cut edge. Apply restrained flat period "
        "washes using palette_reference_crop.jpg: deep umber/olive shadows, muted warm earths, and small cool blue-grey "
        "accents. Keep the aged paper visible. Return one PNG at no more than 2048 px with the same transparency.\n"
    )
    (pack / "INSTRUCTION.txt").write_text(instruction, encoding="utf-8")
    metrics["examples"]["C"]["nano_banana_pack"] = {
        "status": "prepared_only_not_run",
        "cropped_element_size_px": list(pack_image.size),
        "files": ["cropped_element.png", "palette_reference_crop.jpg", "INSTRUCTION.txt"],
    }


def seam_test_b(state: dict[str, Any], metrics: dict[str, Any]) -> None:
    rgb_full = state["bleed_rgb"]
    geom_full = state["crop_geometry"]
    active_columns = np.flatnonzero(np.any(geom_full, axis=0))
    active_rows = np.flatnonzero(np.any(geom_full, axis=1))
    x0, x1 = int(active_columns.min()), int(active_columns.max()) + 1
    y0, y1 = int(active_rows.min()), int(active_rows.max()) + 1
    rgb = rgb_full[y0:y1, x0:x1]
    geom = geom_full[y0:y1, x0:x1]
    h, w = geom.shape
    ys_left = np.flatnonzero(geom[:, 0])
    ys_right = np.flatnonzero(geom[:, -1])
    left_top = int(ys_left.min()) if ys_left.size else h - 1
    right_top = int(ys_right.min()) if ys_right.size else h - 1
    silhouette_gap_px = abs(left_top - right_top)
    seam_before = float(np.mean(np.abs(rgb[:, 0].astype(np.float32) - rgb[:, -1].astype(np.float32))))
    blend = max(8, round(w * 0.055))
    periodic = rgb.copy().astype(np.float32)
    common = (rgb[:, 0].astype(np.float32) + rgb[:, -1].astype(np.float32)) / 2.0
    common_top = round((left_top + right_top) / 2)
    periodic_geom = geom.copy()
    for offset in range(blend):
        t = 1.0 - offset / max(1, blend - 1)
        periodic[:, offset] = periodic[:, offset] * (1 - t) + common * t
        periodic[:, w - 1 - offset] = periodic[:, w - 1 - offset] * (1 - t) + common * t
        local_top_left = int(round((1 - t) * (np.flatnonzero(geom[:, offset]).min() if geom[:, offset].any() else common_top) + t * common_top))
        local_top_right = int(round((1 - t) * (np.flatnonzero(geom[:, w - 1 - offset]).min() if geom[:, w - 1 - offset].any() else common_top) + t * common_top))
        periodic_geom[:, offset] = False
        periodic_geom[local_top_left:, offset] = True
        periodic_geom[:, w - 1 - offset] = False
        periodic_geom[local_top_right:, w - 1 - offset] = True
    periodic = np.clip(periodic, 0, 255).astype(np.uint8)
    seam_after = float(np.mean(np.abs(periodic[:, 0].astype(np.float32) - periodic[:, -1].astype(np.float32))))
    repeated = np.tile(periodic, (1, 3, 1))
    repeated_mask = np.tile(periodic_geom, (1, 3))
    preview = dark_preview(repeated, repeated_mask, max_side=2000)
    out_dir = ROOT / "B"
    save_rgba(out_dir / "seam_periodic_single.png", periodic, periodic_geom.astype(np.uint8) * 255)
    save_rgb(out_dir / "seam_repeat_3x_preview.jpg", preview)
    diff = np.abs(periodic[:, 0].astype(np.int16) - periodic[:, -1].astype(np.int16)).astype(np.uint8)
    diff_image = np.repeat(diff[:, None, :], 90, axis=1)
    save_rgb(out_dir / "seam_edge_difference_after.png", diff_image)
    metrics["examples"]["B"]["seam_test"] = {
        "attempt": "5.5% wrap-edge colour and silhouette blend, then three repeats",
        "tested_active_crop_xyxy": [x0, y0, x1, y1],
        "blend_width_px": blend,
        "native_edge_rgb_mean_absolute_difference_before_0_to_255": round(seam_before, 4),
        "native_edge_rgb_mean_absolute_difference_after_0_to_255": round(seam_after, 4),
        "silhouette_height_gap_before_px": silhouette_gap_px,
        "silhouette_height_gap_before_cm": round(silhouette_gap_px * state["cm_per_px"], 4),
        "silhouette_height_gap_after_px": 0,
        "verdict": "numerically closed seam; visual review still required for the repeated motif and blended ghosting",
    }


def run_previews_and_variants(metrics: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    for key, state in states.items():
        started = time.perf_counter()
        element: ElementSpec = state["element"]
        out_dir = ROOT / element.example
        rgb = state["bleed_rgb"]
        geometry = state["crop_geometry"]
        save_rgb(out_dir / f"stage5_{key}_dark_stage_preview.jpg", dark_preview(rgb, geometry))
        one_m, one_m_metrics = physical_one_metre_crop(rgb, geometry, state["cm_per_px"])
        save_rgb(out_dir / f"stage5_{key}_one_metre_physical_crop.png", one_m)
        save_rgb(out_dir / f"stage5_{key}_outline_original.jpg", draw_outline(state["crop_rgb"], geometry, width=max(2, round(0.6 / state["cm_per_px"]))))
        stage_metrics = {
            "seconds": round(time.perf_counter() - started, 4),
            "peak_vram_mib": 0.0,
            "stage_background_rgb": list(STAGE_GREY),
            "one_metre_crop": one_m_metrics,
        }
        metrics["examples"][element.example]["elements"][key]["stage5_preview"] = stage_metrics
    seam_test_b(states["B_ROW"], metrics)
    colour_c_element(states["C_WING"], metrics)


def aggregate_example_timings(metrics: dict[str, Any]) -> None:
    for example, record in metrics["examples"].items():
        stages: dict[str, dict[str, float]] = {}
        stage1 = record.get("stage1_segmentation", {})
        stages["1_segmentation"] = {"seconds": stage1.get("seconds", 0.0), "peak_vram_mib": stage1.get("peak_vram_mib", 0.0)}
        for stage_key, element_stage in (
            ("2_jigsaw", "stage2_jigsaw"),
            ("3_lama", "stage3_lama"),
            ("4_resolution", "stage4_resolution"),
            ("5_preview", "stage5_preview"),
        ):
            rows = [e.get(element_stage, {}) for e in record["elements"].values()]
            stages[stage_key] = {
                "seconds": round(sum(float(row.get("seconds", 0.0)) for row in rows), 4),
                "peak_vram_mib": round(max([float(row.get("peak_vram_mib", 0.0)) for row in rows] or [0.0]), 3),
            }
        record["stage_totals"] = stages


def source_integrity(metrics: dict[str, Any]) -> None:
    for source in SOURCES:
        before = metrics["examples"][source.example]["source_sha256_before"]
        after = sha256(source.source_path)
        metrics["examples"][source.example]["source_sha256_after"] = after
        metrics["examples"][source.example]["source_read_only_integrity_pass"] = before == after


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def image_card(path: Path, caption: str) -> str:
    if not path.exists():
        return ""
    return f'<figure><a href="{html.escape(rel(path))}"><img loading="lazy" src="{html.escape(rel(path))}" alt="{html.escape(caption)}"></a><figcaption>{html.escape(caption)}</figcaption></figure>'


def build_html(metrics: dict[str, Any]) -> None:
    sections: list[str] = []
    for example in ("A", "B", "C"):
        folder = ROOT / example
        cards: list[str] = []
        for path in sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png")):
            if "realesrgan4x_rgb" in path.name or "realesrgan4x_geometry" in path.name:
                continue
            cards.append(image_card(path, path.stem.replace("_", " ")))
        full_links = []
        for path in sorted(folder.glob("stage4_*_realesrgan4x_rgb.jpg")):
            full_links.append(f'<li><a href="{html.escape(rel(path))}">{html.escape(path.name)} (full 4x)</a></li>')
        timing_rows = "".join(
            f"<tr><td>{html.escape(stage)}</td><td>{values['seconds']:.4f}</td><td>{values['peak_vram_mib']:.3f}</td></tr>"
            for stage, values in metrics["examples"][example]["stage_totals"].items()
        )
        sections.append(
            f"<section><h2>Example {example}</h2><table><thead><tr><th>Stage</th><th>Seconds</th><th>Peak allocated VRAM MiB</th></tr></thead><tbody>{timing_rows}</tbody></table>"
            + (f"<ul>{''.join(full_links)}</ul>" if full_links else "")
            + f'<div class="grid">{"".join(cards)}</div></section>'
        )
    css = """
    body{margin:0;background:#17191c;color:#eee;font:15px/1.45 system-ui,Segoe UI,sans-serif}main{max-width:1800px;margin:auto;padding:24px}a{color:#9fd3ff}h1,h2{font-weight:600}section{margin:36px 0;border-top:1px solid #555;padding-top:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}figure{margin:0;background:#25282d;padding:10px;border-radius:4px}img{width:100%;height:330px;object-fit:contain;background:#1f2226}figcaption{margin-top:8px;color:#ccc;overflow-wrap:anywhere}table{border-collapse:collapse;margin:12px 0 20px}td,th{border:1px solid #666;padding:6px 10px;text-align:left}code{background:#292c31;padding:2px 4px}
    """
    document = f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Flat V3 three-example cutout test</title><style>{css}</style></head><body><main><h1>Flat V3 — three-example cutout test</h1><p>Offline run. Click any image for its saved stage file. Full 4x files are linked separately because of their dimensions.</p><p><a href='REPORT.md'>REPORT.md</a> · <a href='metrics.json'>metrics.json</a></p>{''.join(sections)}</main></body></html>"
    (ROOT / "index.html").write_text(document, encoding="utf-8")


def initial_metrics() -> dict[str, Any]:
    examples = {}
    for source in SOURCES:
        metadata = json.loads(source.metadata_path.read_text(encoding="utf-8"))
        examples[source.example] = {
            "source_id": source.source_id,
            "source_path": str(source.source_path),
            "source_metadata_path": str(source.metadata_path),
            "source_declared_title": metadata["candidate_record"]["title"],
            "source_declared_artist": metadata["candidate_record"]["artist"],
            "source_declared_license": metadata["candidate_record"].get("license_text", metadata["candidate_record"].get("licence_text")),
            "elements": {},
        }
    return {
        "schema_version": 1,
        "run_started_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "offline": True,
        "network_used": False,
        "generation_used": False,
        "unreal_used": False,
        "blender_used": False,
        "tool_root": str(TOOL_ROOT),
        "output_root": str(ROOT),
        "examples": examples,
    }


def main() -> None:
    ensure_dirs()
    metrics = initial_metrics()
    states: dict[str, dict[str, Any]] = {}
    run_segmentation(metrics, states)
    save_json(ROOT / "metrics.partial.stage1.json", metrics)
    run_jigsaw(metrics, states)
    save_json(ROOT / "metrics.partial.stage2.json", metrics)
    run_lama(metrics, states)
    save_json(ROOT / "metrics.partial.stage3.json", metrics)
    run_upscaler(metrics, states)
    save_json(ROOT / "metrics.partial.stage4.json", metrics)
    run_previews_and_variants(metrics, states)
    aggregate_example_timings(metrics)
    source_integrity(metrics)
    metrics["run_finished_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_json(ROOT / "metrics.json", metrics)
    build_html(metrics)
    print("CUTOUT_TEST_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
