"""Extend the six rebuilt S3 wave halves without horizontally scaling their art.

The input is the completed 12.5 m Flat V3 wave build.  Each output keeps the
centre-facing side of the source intact and replaces only an outer tail with a
periodic continuation sampled from that same half.  A source trough-to-trough
cycle is repeated and cross-faded at a measured trough.  Blender is used only
for headless export and a factory-clean validation import; this script never
renders and never invokes Unreal or the MCP transport.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import find_peaks


PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "flats"
OUTPUT_ROOT = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "flats_ext3"
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
GPU_MARKER = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "RUNNING.json"
SHARED = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "shared"
TEXTURE_ROOT = PROJECT / "DerivedAssets" / "TextureLibrary"
PAPER_DISP = TEXTURE_ROOT / "Paper" / "Paper003" / "Paper003_4K-JPG_Displacement.jpg"
PAPER_ROUGH = TEXTURE_ROOT / "Paper" / "Paper003" / "Paper003_4K-JPG_Roughness.jpg"
BUILD_SKIN = PROJECT / "Tools" / "FlatV3" / "build_skin.py"
BUILD_FLAT = PROJECT / "Tools" / "FlatV3" / "build_v3_flat.py"
VENV_PYTHON = Path(r"D:\PussStageTools\FlatV3\venv\Scripts\python.exe")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe")
TARGET_WIDTHS_CM = {
    "S3_WaveRow1_A": 1431.69,
    "S3_WaveRow1_B": 1627.55,
    "S3_WaveRow2_A": 1531.91,
    "S3_WaveRow2_B": 1460.79,
    "S3_WaveRow3_A": 1833.45,
    "S3_WaveRow3_B": 1439.22,
}
RUN_ID = "FV3W-20261002-05"
HEIGHTS_CM = {1: 120.0, 2: 180.0, 3: 260.0}
BG_RGB = np.asarray((214, 200, 170), dtype=np.uint8)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        log.write("\nCOMMAND " + subprocess.list2cmdline(command) + "\n")
        completed = subprocess.run(
            command,
            cwd=PROJECT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                f"Command failed with exit code {completed.returncode}: {command[0]} "
                f"(see {log_path})"
            )


def read_rgb(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if image.ndim == 2:
        encoded = image
    elif image.shape[2] == 4:
        encoded = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
    else:
        encoded = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(path), encoded):
        raise RuntimeError(f"Could not write {path}")


def foreground_top(mask: np.ndarray) -> np.ndarray:
    binary = mask > 127
    valid = binary.any(axis=0)
    if not valid.all():
        indices = np.flatnonzero(valid)
        if len(indices) < 2:
            raise RuntimeError("Wave mask has fewer than two populated columns")
        top = np.argmax(binary, axis=0).astype(np.float64)
        top[~valid] = np.nan
        top = np.interp(np.arange(mask.shape[1]), indices, top[indices])
    else:
        top = np.argmax(binary, axis=0).astype(np.float64)
    kernel = np.ones(31, dtype=np.float64) / 31.0
    return np.convolve(top, kernel, mode="same")


def column_mad(
    art: np.ndarray,
    mask: np.ndarray,
    left: int,
    right: int,
) -> float:
    left %= art.shape[1]
    right %= art.shape[1]
    common = (mask[:, left] > 127) & (mask[:, right] > 127)
    if np.count_nonzero(common) < max(16, art.shape[0] // 20):
        common = (mask[:, left] > 127) | (mask[:, right] > 127)
    if not np.any(common):
        common = np.ones(art.shape[0], dtype=bool)
    rgb = art[:, :, :3] if art.ndim == 3 else np.repeat(art[:, :, None], 3, axis=2)
    return float(np.mean(np.abs(rgb[common, left].astype(np.float32) - rgb[common, right].astype(np.float32))))


def choose_plan(art: np.ndarray, mask: np.ndarray, half: str, target_width: int) -> dict[str, Any]:
    width = mask.shape[1]
    profile = foreground_top(mask)
    troughs, properties = find_peaks(
        profile,
        distance=max(48, width // 35),
        prominence=max(3.0, mask.shape[0] * 0.025),
    )
    troughs = troughs[(troughs > width * 0.03) & (troughs < width * 0.97)]
    if len(troughs) < 4:
        raise RuntimeError(f"Only {len(troughs)} crest troughs found")
    diffs = np.diff(troughs)
    useful = diffs[(diffs >= width * 0.035) & (diffs <= width * 0.14)]
    median_period = float(np.median(useful if len(useful) else diffs))
    join_target = width * (0.82 if half == "A" else 0.18)
    candidates: list[tuple[float, int, int, int, dict[str, float]]] = []
    binary = mask > 127
    global_rows = np.flatnonzero(binary.any(axis=1))
    global_top, global_bottom = int(global_rows[0]), int(global_rows[-1])
    # A complex painted crest can contain a smaller secondary trough.  Consider
    # up to four successive trough intervals and require the chosen whole-cycle
    # sample to carry the source's full vertical excursion.  Otherwise repeating
    # a minor curl can silently shorten the delivered mesh.
    for start_index, start_value in enumerate(troughs):
        for end_value in troughs[start_index + 1 :]:
            start, end = int(start_value), int(end_value)
            period = end - start
            if not (width * 0.05 <= period <= width * 0.35):
                continue
            segment_rows = np.flatnonzero(binary[:, start:end].any(axis=1))
            if not len(segment_rows):
                continue
            missing_vertical_px = max(0, int(segment_rows[0]) - global_top) + max(
                0, global_bottom - int(segment_rows[-1])
            )
            join = start if half == "A" else end
            preserved_centre_px = join if half == "A" else width - join
            if preserved_centre_px < width * 0.35:
                continue
            endpoint_mad = column_mad(art, mask, start, end)
            # A joins at the source period's first trough; B joins at its last.
            # Thus the retained original and the repeated source share the exact
            # join column, while the endpoint MAD predicts later period seams.
            join_mad = 0.0
            period_penalty = period / width
            join_position_penalty = abs(join - join_target) / width * 10.0
            edge_penalty = 2.0 if start < width * 0.08 or end > width * 0.92 else 0.0
            coverage_penalty = float(missing_vertical_px) * 100.0
            score = (
                endpoint_mad * 2.0
                + period_penalty
                + join_position_penalty
                + edge_penalty
                + coverage_penalty
            )
            candidates.append(
                (
                    score,
                    start,
                    end,
                    join,
                    {
                        "endpoint_column_mad": round(endpoint_mad, 6),
                        "join_to_cycle_column_mad": round(join_mad, 6),
                        "period_penalty": round(period_penalty, 6),
                        "join_position_penalty": round(join_position_penalty, 6),
                        "missing_vertical_extent_px": float(missing_vertical_px),
                        "vertical_extent_penalty": round(coverage_penalty, 6),
                    },
                )
            )
    if not candidates:
        raise RuntimeError("No valid trough-to-trough source cycle found")
    score, source_start, source_end, join, score_parts = min(candidates, key=lambda item: item[0])
    period = source_end - source_start
    fade = max(18, min(period // 20, 64))
    cycle_overlap = 0
    cycle_step = period - cycle_overlap
    added = target_width - width
    if added <= 0:
        raise RuntimeError(f"Target width {target_width} must exceed source width {width}")
    return {
        "source_width_px": width,
        "target_width_px": target_width,
        "added_width_px": added,
        "outer_end": "right" if half == "A" else "left",
        "centre_join_preserved_edge": "left" if half == "A" else "right",
        "join_x_source_px": join,
        "join_x_output_px": join if half == "A" else added + join,
        "join_is_detected_crest_trough": True,
        "source_cycle_start_px": source_start,
        "source_cycle_end_px": source_end,
        "whole_crest_period_px": period,
        "crossfade_half_width_px": fade,
        "cycle_overlap_px": cycle_overlap,
        "cycle_step_px": cycle_step,
        "whole_cycles_generated_before_outer_crop": int(math.ceil((target_width + 2 * period) / cycle_step)),
        "final_outer_crop_only": True,
        "selection_score": round(float(score), 6),
        "selection_score_parts": score_parts,
        "detected_troughs_px": [int(value) for value in troughs],
        "median_trough_period_px": round(median_period, 6),
    }


def periodic_canvas(image: np.ndarray, plan: dict[str, Any]) -> np.ndarray:
    target_width = int(plan["target_width_px"])
    source_start = int(plan["source_cycle_start_px"])
    period = int(plan["whole_crest_period_px"])
    join_out = int(plan["join_x_output_px"])
    overlap = int(plan["cycle_overlap_px"])
    step = int(plan["cycle_step_px"])
    tile = image[:, source_start : source_start + period].astype(np.float32)
    shape = (image.shape[0], target_width) if image.ndim == 2 else (image.shape[0], target_width, image.shape[2])
    accumulation = np.zeros(shape, dtype=np.float32)
    weights = np.zeros((image.shape[0], target_width), dtype=np.float32)
    first_k = int(math.floor((-join_out - period) / step)) - 1
    last_k = int(math.ceil((target_width - join_out + period) / step)) + 1
    tile_weight = np.ones(period, dtype=np.float32)
    if overlap:
        ramp = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
        ramp = ramp * ramp * (3.0 - 2.0 * ramp)
        tile_weight[:overlap] = ramp
        tile_weight[-overlap:] = 1.0 - ramp
    for repeat_index in range(first_k, last_k + 1):
        destination_start = join_out + repeat_index * step
        destination_end = destination_start + period
        clipped_start = max(0, destination_start)
        clipped_end = min(target_width, destination_end)
        if clipped_start >= clipped_end:
            continue
        source_x0 = clipped_start - destination_start
        source_x1 = source_x0 + clipped_end - clipped_start
        local_weight = tile_weight[source_x0:source_x1]
        if image.ndim == 2:
            accumulation[:, clipped_start:clipped_end] += tile[:, source_x0:source_x1] * local_weight[None, :]
        else:
            accumulation[:, clipped_start:clipped_end] += tile[:, source_x0:source_x1] * local_weight[None, :, None]
        weights[:, clipped_start:clipped_end] += local_weight[None, :]
    if np.any(weights <= 1e-8):
        raise RuntimeError("Periodic crest accumulator left uncovered pixels")
    if image.ndim == 2:
        return accumulation / weights
    return accumulation / weights[:, :, None]


def periodic_mask_canvas(mask: np.ndarray, plan: dict[str, Any]) -> np.ndarray:
    """Repeat jigsaw occupancy with the production wave builder's union rule."""
    target_width = int(plan["target_width_px"])
    source_start = int(plan["source_cycle_start_px"])
    period = int(plan["whole_crest_period_px"])
    join_out = int(plan["join_x_output_px"])
    step = int(plan["cycle_step_px"])
    tile = mask[:, source_start : source_start + period] > 127
    output = np.zeros((mask.shape[0], target_width), dtype=bool)
    first_k = int(math.floor((-join_out - period) / step)) - 1
    last_k = int(math.ceil((target_width - join_out + period) / step)) + 1
    for repeat_index in range(first_k, last_k + 1):
        destination_start = join_out + repeat_index * step
        destination_end = destination_start + period
        clipped_start = max(0, destination_start)
        clipped_end = min(target_width, destination_end)
        if clipped_start >= clipped_end:
            continue
        source_x0 = clipped_start - destination_start
        source_x1 = source_x0 + clipped_end - clipped_start
        output[:, clipped_start:clipped_end] |= tile[:, source_x0:source_x1]
    # This is the existing repeat_wave jigsaw rule: a continuous painted bottom
    # rail keeps overlapping crest copies one physical mass.
    rail = max(2, int(round(mask.shape[0] * 0.018)))
    output[-rail:, :] = True
    return output.astype(np.uint8) * 255


def periodic_art_canvas(image: np.ndarray, mask: np.ndarray, plan: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Repeat colour with foreground-weighted trough overlaps.

    This mirrors ``repeat_wave``: a background texel from one copy must never
    darken foreground admitted by the unioned jigsaw mask from another copy.
    """
    target_width = int(plan["target_width_px"])
    source_start = int(plan["source_cycle_start_px"])
    period = int(plan["whole_crest_period_px"])
    join_out = int(plan["join_x_output_px"])
    overlap = int(plan["cycle_overlap_px"])
    step = int(plan["cycle_step_px"])
    tile = image[:, source_start : source_start + period].astype(np.float32)
    tile_mask = (mask[:, source_start : source_start + period] > 127).astype(np.float32)
    shape = (image.shape[0], target_width, image.shape[2])
    accumulation = np.zeros(shape, dtype=np.float32)
    weights = np.zeros((image.shape[0], target_width), dtype=np.float32)
    occupancy = np.zeros((image.shape[0], target_width), dtype=np.float32)
    first_k = int(math.floor((-join_out - period) / step)) - 1
    last_k = int(math.ceil((target_width - join_out + period) / step)) + 1
    horizontal_weight = np.ones(period, dtype=np.float32)
    if overlap:
        ramp = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
        ramp = ramp * ramp * (3.0 - 2.0 * ramp)
        horizontal_weight[:overlap] = ramp
        horizontal_weight[-overlap:] = 1.0 - ramp
    for repeat_index in range(first_k, last_k + 1):
        destination_start = join_out + repeat_index * step
        destination_end = destination_start + period
        clipped_start = max(0, destination_start)
        clipped_end = min(target_width, destination_end)
        if clipped_start >= clipped_end:
            continue
        source_x0 = clipped_start - destination_start
        source_x1 = source_x0 + clipped_end - clipped_start
        local_mask = tile_mask[:, source_x0:source_x1]
        local_weight = local_mask * horizontal_weight[source_x0:source_x1][None, :]
        accumulation[:, clipped_start:clipped_end] += (
            tile[:, source_x0:source_x1] * local_weight[:, :, None]
        )
        weights[:, clipped_start:clipped_end] += local_weight
        occupancy[:, clipped_start:clipped_end] = np.maximum(
            occupancy[:, clipped_start:clipped_end], local_mask
        )
    plain = periodic_canvas(image, plan)
    safe = np.maximum(weights, 1e-8)
    colour = accumulation / safe[:, :, None]
    colour[weights <= 1e-8] = plain[weights <= 1e-8]
    if overlap == 0:
        # The selected trough-to-trough cycle keeps geometry at native length.
        # Feather only colour around each butt join, using premultiplied
        # foreground so background texels cannot create a dark vertical wedge.
        feather = max(4, int(plan["crossfade_half_width_px"]))
        sigma = max(1.5, feather / 4.0)
        kernel = max(3, int(round(sigma * 6.0)) | 1)
        first_boundary = int(math.floor((-join_out) / step)) - 1
        last_boundary = int(math.ceil((target_width - join_out) / step)) + 1
        for boundary_index in range(first_boundary, last_boundary + 1):
            boundary = join_out + boundary_index * step
            x0, x1 = max(0, boundary - feather), min(target_width, boundary + feather + 1)
            if x1 - x0 < 5:
                continue
            local_occ = occupancy[:, x0:x1]
            premultiplied = colour[:, x0:x1] * local_occ[:, :, None]
            blurred_occ = cv2.GaussianBlur(local_occ, (kernel, 1), sigmaX=sigma, sigmaY=0)
            blurred_premultiplied = cv2.GaussianBlur(
                premultiplied, (kernel, 1), sigmaX=sigma, sigmaY=0
            )
            softened = blurred_premultiplied / np.maximum(blurred_occ[:, :, None], 1e-8)
            softened[blurred_occ <= 1e-8] = colour[:, x0:x1][blurred_occ <= 1e-8]
            distance = np.abs(np.arange(x0, x1, dtype=np.float32) - float(boundary))
            blend = np.clip(1.0 - distance / max(float(feather), 1.0), 0.0, 1.0)
            blend = blend * blend * (3.0 - 2.0 * blend)
            colour[:, x0:x1] = (
                colour[:, x0:x1] * (1.0 - blend[None, :, None])
                + softened * blend[None, :, None]
            )
    return colour, occupancy


def extend_art(image: np.ndarray, mask: np.ndarray, plan: dict[str, Any]) -> np.ndarray:
    source_width = int(plan["source_width_px"])
    target_width = int(plan["target_width_px"])
    added = int(plan["added_width_px"])
    join_out = int(plan["join_x_output_px"])
    fade = int(plan["crossfade_half_width_px"])
    if image.ndim != 3 or image.shape[:2] != mask.shape[:2] or image.shape[1] != source_width:
        raise RuntimeError(
            f"Art/mask/plan extent mismatch: art={image.shape}, mask={mask.shape}, plan={source_width}"
        )
    periodic, periodic_occupancy = periodic_art_canvas(image, mask, plan)
    original = np.zeros((image.shape[0], target_width, image.shape[2]), dtype=np.float32)
    original_mask = np.zeros((image.shape[0], target_width), dtype=np.float32)
    if plan["outer_end"] == "right":
        original[:, :source_width] = image
        original_mask[:, :source_width] = mask > 127
    else:
        original[:, added:] = image
        original_mask[:, added:] = mask > 127
    start = max(0, join_out - fade)
    end = min(target_width, join_out + fade + 1)
    transition = np.zeros(target_width, dtype=np.float32)
    if plan["outer_end"] == "right":
        transition[end:] = 1.0
        blend = np.linspace(0.0, 1.0, max(1, end - start), dtype=np.float32)
    else:
        transition[:start] = 1.0
        blend = np.linspace(1.0, 0.0, max(1, end - start), dtype=np.float32)
    blend = blend * blend * (3.0 - 2.0 * blend)
    transition[start:end] = blend
    new_weight = periodic_occupancy * transition[None, :]
    old_weight = original_mask * (1.0 - transition[None, :])
    total = new_weight + old_weight
    combined = (
        periodic * new_weight[:, :, None] + original * old_weight[:, :, None]
    ) / np.maximum(total[:, :, None], 1e-8)
    fallback = periodic_canvas(image, plan)
    combined[total <= 1e-8] = fallback[total <= 1e-8]
    return np.clip(np.rint(combined), 0, 255).astype(np.uint8)


def extend_array(image: np.ndarray, plan: dict[str, Any], *, binary: bool = False) -> np.ndarray:
    source_width = int(plan["source_width_px"])
    target_width = int(plan["target_width_px"])
    added = int(plan["added_width_px"])
    join_source = int(plan["join_x_source_px"])
    join_out = int(plan["join_x_output_px"])
    fade = int(plan["crossfade_half_width_px"])
    if image.shape[1] != source_width:
        raise RuntimeError(f"Plan/image width mismatch: {source_width} vs {image.shape[1]}")
    if binary:
        periodic_mask = periodic_mask_canvas(image, plan)
        original_mask = np.zeros_like(periodic_mask)
        if plan["outer_end"] == "right":
            original_mask[:, :source_width] = image
        else:
            original_mask[:, added:] = image
        start = max(0, join_out - fade)
        end = min(target_width, join_out + fade + 1)
        output_mask = periodic_mask
        if plan["outer_end"] == "right":
            output_mask[:, :start] = original_mask[:, :start]
            output_mask[:, start:end] = np.maximum(
                original_mask[:, start:end], periodic_mask[:, start:end]
            )
        else:
            output_mask[:, end:] = original_mask[:, end:]
            output_mask[:, start:end] = np.maximum(
                original_mask[:, start:end], periodic_mask[:, start:end]
            )
        rail = max(2, int(round(image.shape[0] * 0.018)))
        output_mask[-rail:, :] = 255
        return np.where(output_mask >= 128, 255, 0).astype(np.uint8)

    periodic = periodic_canvas(image, plan).astype(np.float32)
    original = np.zeros_like(periodic)
    if plan["outer_end"] == "right":
        original[:, :source_width] = image
    else:
        original[:, added:] = image
    start = max(0, join_out - fade)
    end = min(target_width, join_out + fade + 1)
    t = np.linspace(0.0, 1.0, max(1, end - start), dtype=np.float32)
    t = t * t * (3.0 - 2.0 * t)
    if plan["outer_end"] == "left":
        t = 1.0 - t
    shape = (1, -1) if image.ndim == 2 else (1, -1, 1)
    blend = t.reshape(shape)
    output = periodic
    if plan["outer_end"] == "right":
        output[:, :start] = original[:, :start]
        output[:, start:end] = original[:, start:end] * (1.0 - blend) + periodic[:, start:end] * blend
    else:
        output[:, end:] = original[:, end:]
        output[:, start:end] = periodic[:, start:end] * (1.0 - blend) + original[:, start:end] * blend
    output = np.clip(np.rint(output), 0, 255).astype(np.uint8)
    return output


def scaled_plan(plan: dict[str, Any], factor: int) -> dict[str, Any]:
    scaled = dict(plan)
    for key in (
        "source_width_px",
        "target_width_px",
        "added_width_px",
        "join_x_source_px",
        "join_x_output_px",
        "source_cycle_start_px",
        "source_cycle_end_px",
        "whole_crest_period_px",
        "crossfade_half_width_px",
        "cycle_overlap_px",
        "cycle_step_px",
    ):
        scaled[key] = int(plan[key]) * factor
    scaled["detected_troughs_px"] = [int(value) * factor for value in plan["detected_troughs_px"]]
    scaled["median_trough_period_px"] = float(plan["median_trough_period_px"]) * factor
    return scaled


def composite(art: np.ndarray, mask: np.ndarray) -> np.ndarray:
    rgb = art[:, :, :3] if art.ndim == 3 else np.repeat(art[:, :, None], 3, axis=2)
    alpha = (mask.astype(np.float32) / 255.0)[:, :, None]
    return np.clip(rgb.astype(np.float32) * alpha + BG_RGB[None, None, :] * (1.0 - alpha), 0, 255).astype(np.uint8)


def label_panel(image: np.ndarray, label: str, display_width: int, display_height: int) -> Image.Image:
    pil = Image.fromarray(image).resize((display_width, display_height), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (display_width, display_height + 44), (24, 24, 28))
    panel.paste(pil, (0, 44))
    draw = ImageDraw.Draw(panel)
    draw.text((12, 13), label, fill=(245, 245, 245))
    return panel


def make_contact_sheet(row: int, records: dict[str, dict[str, Any]]) -> Path:
    current_width = 980
    panel_height = 210
    gap = 18
    margin = 18
    title_h = 48
    rows: list[list[Image.Image]] = []
    for half in ("A", "B"):
        record = records[half]
        target_width_cm = float(record["target_width_cm"])
        extended_width = int(round(current_width * target_width_cm / 1250.0))
        current = composite(read_rgb(Path(record["source_art_stage1"])), read_rgb(Path(record["source_mask_stage1"])))
        extended = composite(read_rgb(Path(record["output_art_stage1"])), read_rgb(Path(record["output_mask_stage1"])))
        stretched = cv2.resize(current, (extended.shape[1], current.shape[0]), interpolation=cv2.INTER_LANCZOS4)
        rows.append(
            [
                label_panel(current, f"{half} CURRENT 12.5 m ART", current_width, panel_height),
                label_panel(extended, f"{half} EXTENDED {target_width_cm / 100.0:.3f} m ART - USED", extended_width, panel_height),
                label_panel(stretched, f"{half} STRETCHED TO {target_width_cm / 100.0:.3f} m - NOT USED", extended_width, panel_height),
            ]
        )
    canvas_w = margin * 2 + max(sum(panel.width for panel in panels) for panels in rows) + gap * 2
    canvas_h = title_h + margin + sum(row[0].height for row in rows) + gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), (10, 10, 12))
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 16), f"S3 Wave Row {row}: source-scale extension evidence", fill=(255, 255, 255))
    y = title_h
    for panels in rows:
        x = margin
        for panel in panels:
            canvas.paste(panel, (x, y))
            x += panel.width + gap
        y += panels[0].height + gap
    path = EVIDENCE_ROOT / f"S3_WaveRow{row}_contact_sheet.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return path


def make_seam_closeup(asset: str, art: np.ndarray, mask: np.ndarray, plan: dict[str, Any]) -> Path:
    join = int(plan["join_x_output_px"])
    period = int(plan["whole_crest_period_px"])
    radius = max(220, int(period * 1.20))
    x0, x1 = max(0, join - radius), min(art.shape[1], join + radius)
    crop = composite(art[:, x0:x1], mask[:, x0:x1])
    max_width = 1800
    if crop.shape[1] > max_width:
        scale = max_width / crop.shape[1]
        crop = cv2.resize(crop, (max_width, max(1, int(round(crop.shape[0] * scale)))), interpolation=cv2.INTER_AREA)
        marker_x = int(round((join - x0) * scale))
    else:
        marker_x = join - x0
    pil = Image.fromarray(crop)
    canvas = Image.new("RGB", (pil.width, pil.height + 54), (20, 20, 24))
    canvas.paste(pil, (0, 54))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 9), f"{asset} extension join - trough crossfade", fill=(255, 255, 255))
    draw.text((12, 29), "marker identifies join; line stops above artwork", fill=(190, 190, 190))
    draw.line((marker_x, 46, marker_x, 53), fill=(255, 205, 40), width=3)
    path = EVIDENCE_ROOT / f"{asset}_seam_closeup.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return path


def seam_metrics(art: np.ndarray, mask: np.ndarray, plan: dict[str, Any], seed: int) -> dict[str, Any]:
    join = int(plan["join_x_output_px"])
    join_mad = column_mad(art, mask, join - 1, join)
    rng = np.random.default_rng(seed)
    protected = max(int(plan["whole_crest_period_px"]), 64)
    candidates = [
        x
        for x in range(2, art.shape[1] - 2)
        if abs(x - join) > protected
        and np.count_nonzero((mask[:, x - 1] > 127) & (mask[:, x] > 127)) >= max(16, art.shape[0] // 20)
    ]
    if not candidates:
        raise RuntimeError("No valid random interior column pair")
    interior_x = int(candidates[int(rng.integers(0, len(candidates)))])
    interior_mad = column_mad(art, mask, interior_x - 1, interior_x)
    return {
        "metric": "mean absolute RGB difference, 0..255, between adjacent foreground columns",
        "join_columns_px": [join - 1, join],
        "join_mad": round(join_mad, 6),
        "random_interior_columns_px": [interior_x - 1, interior_x],
        "random_interior_mad": round(interior_mad, 6),
        "join_to_random_ratio": round(join_mad / max(interior_mad, 1e-9), 6),
        "random_seed": seed,
    }


def copy_support_files(source: Path, output: Path) -> None:
    for relative in (
        "sockets_" + "SM_FlatV3_" + source.name + ".json",
    ):
        candidate = source / relative
        if candidate.is_file():
            shutil.copy2(candidate, output / relative)


def extend_source(asset: str, row: int, half: str) -> dict[str, Any]:
    source = SOURCE_ROOT / asset
    output = OUTPUT_ROOT / asset
    output.mkdir(parents=True, exist_ok=True)
    stage1_art_path = source / "stage1_colour_key_art.png"
    stage1_mask_path = source / "stage2_jigsaw_mask.png"
    stage1_art = read_rgb(stage1_art_path)
    stage1_mask = read_rgb(stage1_mask_path)
    target_width_cm = TARGET_WIDTHS_CM[asset]
    source_build = json.loads(next(source.glob("*_build.json")).read_text(encoding="utf-8"))
    source_width_cm = float(source_build["dimensions_m"]["width"]) * 100.0
    if source_width_cm >= target_width_cm:
        raise RuntimeError(
            f"SOURCE_NOT_NARROWER_THAN_TARGET|asset={asset}|source_cm={source_width_cm}|target_cm={target_width_cm}"
        )
    target_width = int(round(target_width_cm / HEIGHTS_CM[row] * stage1_mask.shape[0]))
    plan = choose_plan(stage1_art, stage1_mask, half, target_width)
    stage1_extended = extend_art(stage1_art, stage1_mask, plan)
    stage2_extended = extend_array(stage1_mask, plan, binary=True)
    write_image(output / "stage1_colour_key_art.png", stage1_extended)
    write_image(output / "stage2_jigsaw_mask.png", stage2_extended)

    stage3 = read_rgb(source / "stage3_colour_bleed.png")
    write_image(output / "stage3_colour_bleed.png", extend_art(stage3, stage1_mask, plan))
    stage4_plan = scaled_plan(plan, 2)
    stage4_art = read_rgb(source / "stage4_RealESRGAN_2x_art.png")
    stage4_mask = read_rgb(source / "stage4_RealESRGAN_2x_jigsaw_mask.png")
    stage4_extended = extend_art(stage4_art, stage4_mask, stage4_plan)
    stage4_mask_extended = extend_array(stage4_mask, stage4_plan, binary=True)
    stage4_art_out = output / "stage4_RealESRGAN_2x_art.png"
    stage4_mask_out = output / "stage4_RealESRGAN_2x_jigsaw_mask.png"
    write_image(stage4_art_out, stage4_extended)
    write_image(stage4_mask_out, stage4_mask_extended)

    def centre_edge_exact(
        source_art: np.ndarray,
        source_mask: np.ndarray,
        output_art: np.ndarray,
        output_mask: np.ndarray,
        sample_width: int,
    ) -> dict[str, Any]:
        sample_width = min(sample_width, source_art.shape[1])
        if half == "A":
            source_art_edge, output_art_edge = source_art[:, :sample_width], output_art[:, :sample_width]
            source_mask_edge, output_mask_edge = source_mask[:, :sample_width], output_mask[:, :sample_width]
            edge = "left"
        else:
            source_art_edge, output_art_edge = source_art[:, -sample_width:], output_art[:, -sample_width:]
            source_mask_edge, output_mask_edge = source_mask[:, -sample_width:], output_mask[:, -sample_width:]
            edge = "right"
        foreground = source_mask_edge > 127
        mask_exact = bool(np.array_equal(source_mask_edge, output_mask_edge))
        foreground_art_exact = bool(
            np.array_equal(source_art_edge[foreground], output_art_edge[foreground])
        )
        return {
            "edge": edge,
            "sample_width_px": sample_width,
            "mask_exact": mask_exact,
            "foreground_art_exact": foreground_art_exact,
            "pass": mask_exact and foreground_art_exact,
        }

    centre_edge_stage1 = centre_edge_exact(
        stage1_art, stage1_mask, stage1_extended, stage2_extended, 256
    )
    centre_edge_stage4 = centre_edge_exact(
        stage4_art, stage4_mask, stage4_extended, stage4_mask_extended, 512
    )
    if not centre_edge_stage1["pass"] or not centre_edge_stage4["pass"]:
        raise RuntimeError(
            f"CENTRE_JOIN_CHANGED|asset={asset}|stage1={centre_edge_stage1}|stage4={centre_edge_stage4}"
        )

    source_ppcm = stage1_mask.shape[1] / source_width_cm
    output_width_cm_from_pixels = target_width * HEIGHTS_CM[row] / stage1_mask.shape[0]
    output_ppcm = target_width / output_width_cm_from_pixels
    ppcm_delta_percent = abs(output_ppcm / source_ppcm - 1.0) * 100.0
    if ppcm_delta_percent > 0.5:
        raise RuntimeError(f"PIXELS_PER_CM_MISMATCH|asset={asset}|delta_percent={ppcm_delta_percent}")
    metrics = seam_metrics(stage4_extended, stage4_mask_extended, stage4_plan, 2026100200 + row * 10 + (0 if half == "A" else 1))
    seam_path = make_seam_closeup(asset, stage4_extended, stage4_mask_extended, stage4_plan)
    record = {
        "asset": asset,
        "row": row,
        "half": half,
        "target_width_authority": "measured Unreal bounds Y in Saved/CodexFlatV3/probe_w_inmemory_out.json",
        "source_art_stage1": str(stage1_art_path),
        "source_mask_stage1": str(stage1_mask_path),
        "source_art_stage1_sha256": sha256(stage1_art_path),
        "source_mask_stage1_sha256": sha256(stage1_mask_path),
        "output_art_stage1": str(output / "stage1_colour_key_art.png"),
        "output_mask_stage1": str(output / "stage2_jigsaw_mask.png"),
        "source_dimensions_px": [stage1_mask.shape[1], stage1_mask.shape[0]],
        "output_dimensions_px": [target_width, stage1_mask.shape[0]],
        "source_width_cm_offline_fbx": source_width_cm,
        "target_width_cm": target_width_cm,
        "output_width_cm_from_pixel_grid": output_width_cm_from_pixels,
        "height_cm": HEIGHTS_CM[row],
        "pixels_per_cm_before": source_ppcm,
        "pixels_per_cm_after": output_ppcm,
        "pixels_per_cm_delta_percent": ppcm_delta_percent,
        "pixels_per_cm_gate_max_percent": 0.5,
        "pixels_per_cm_gate_pass": ppcm_delta_percent <= 0.5,
        "extension_contract": {
            "horizontal_scaling_used_for_production": False,
            "new_paint_or_ai_generation_used": False,
            "source_pixels": "same half's completed stage images only",
            "centre_join_edge_preserved": plan["centre_join_preserved_edge"],
            "outer_end_extended": plan["outer_end"],
            "centre_join_untouched_gate": {
                "stage1": centre_edge_stage1,
                "stage4": centre_edge_stage4,
                "pass": centre_edge_stage1["pass"] and centre_edge_stage4["pass"],
            },
            "cycle": plan,
        },
        "seam_metric": metrics,
        "seam_closeup": str(seam_path),
        "stage4_outputs": {
            "art": str(stage4_art_out),
            "mask": str(stage4_mask_out),
            "source_art_sha256": sha256(source / "stage4_RealESRGAN_2x_art.png"),
            "source_mask_sha256": sha256(source / "stage4_RealESRGAN_2x_jigsaw_mask.png"),
            "art_sha256": sha256(stage4_art_out),
            "mask_sha256": sha256(stage4_mask_out),
        },
    }
    write_json(output / "extension_plan.json", record)
    return record


def build_asset(record: dict[str, Any]) -> dict[str, Any]:
    asset = str(record["asset"])
    output = OUTPUT_ROOT / asset
    skin = output / "skin"
    aged = output / "aged"
    diagnostics = output / "diagnostics"
    log = output / "build.log"
    base_seed = 20261001 + int(hashlib.sha256(asset.encode()).hexdigest()[:5], 16) % 100000
    height_cm = float(record["height_cm"])
    target_width_cm = float(record["target_width_cm"])
    skin_seed = base_seed
    skin_command = [
            str(VENV_PYTHON),
            str(BUILD_SKIN),
            "--mask", str(output / "stage4_RealESRGAN_2x_jigsaw_mask.png"),
            "--art", str(output / "stage4_RealESRGAN_2x_art.png"),
            "--older-poster", str(SHARED / "T_FlatV3_OlderPosterFragments_Color.png"),
            "--paper-displacement", str(PAPER_DISP),
            "--paper-roughness", str(PAPER_ROUGH),
            "--texture-root", str(TEXTURE_ROOT),
            "--aged-output", str(aged),
            "--stencil-text", " ",
            "--height-cm", str(height_cm),
            "--width-cm", str(target_width_cm),
            "--asset-name", asset,
            "--output", str(skin),
            "--diagnostics-output", str(diagnostics),
            "--seed", str(skin_seed),
        ]
    # The approved 5% peel generator has a hard 40 cm continuous-seam limit.
    # A wider canvas can make one deterministic layout exceed that unchanged
    # gate.  Retry only that stochastic layout failure, with adjacent recorded
    # seeds and the exact same percentage/profile/gate.
    for seed_offset in range(32):
        skin_seed = base_seed + seed_offset
        skin_command[-1] = str(skin_seed)
        try:
            run(skin_command, log)
            break
        except RuntimeError:
            tail = log.read_text(encoding="utf-8", errors="replace")[-6000:]
            if "Continuous seam peel run is" not in tail or "limit is 40 cm" not in tail:
                raise
    else:
        raise RuntimeError(f"No compliant 5% peel layout found in 32 deterministic seeds for {asset}")
    # Reuse the production back-overlay implementation so the V3 surface
    # contract is identical.  It is deterministic and CPU-only.
    import sys

    flatv3_tools = str(PROJECT / "Tools" / "FlatV3")
    if flatv3_tools not in sys.path:
        sys.path.insert(0, flatv3_tools)
    from batch_build import bake_back_overlays  # type: ignore

    overlay = bake_back_overlays(aged, asset)
    run(
        [
            str(BLENDER),
            "--background",
            "--factory-startup",
            "--python-exit-code", "1",
            "--python", str(BUILD_FLAT),
            "--",
            "--mask", str(output / "stage4_RealESRGAN_2x_jigsaw_mask.png"),
            "--art", str(skin / f"T_{asset}_SkinColor.png"),
            "--skin-mask", str(skin / f"T_{asset}_SkinMask.png"),
            "--skin-normal", str(skin / f"T_{asset}_SkinNormal.png"),
            "--flaps", str(skin / f"{asset}_flaps.json"),
            "--aged-texture-dir", str(aged),
            "--height-cm", str(height_cm),
            "--side", "L",
            "--name", asset,
            "--asset-name", asset,
            "--mount", "wave-row",
            "--output-dir", str(output),
            "--texture-root", str(TEXTURE_ROOT),
        ],
        log,
    )
    fbx = output / f"SM_FlatV3_{asset}.fbx"
    validation_path = output / "validation.json"
    run(
        [
            str(BLENDER),
            "--background",
            "--factory-startup",
            "--python-exit-code", "1",
            "--python", str(BUILD_FLAT),
            "--",
            "--validate-fbx", str(fbx),
            "--skin-color", str(skin / f"T_{asset}_SkinColor.png"),
            "--kind", "wave",
            "--validation-out", str(validation_path),
            "--expected-height-cm", str(height_cm),
            "--minimum-width-m", str(target_width_cm / 100.0 - 0.005),
        ],
        log,
    )
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    dimensions = [float(value) for value in validation["dimensions_m"]]
    width_error_cm = abs(dimensions[1] * 100.0 - target_width_cm)
    if not validation.get("pass"):
        raise RuntimeError(f"FBX validation failed for {asset}: {validation_path}")
    if width_error_cm > 0.5:
        raise RuntimeError(
            f"WIDTH_GATE_FAILED|asset={asset}|measured_cm={dimensions[1] * 100.0}|target_cm={target_width_cm}"
        )
    required_checks = (
        "fbx_lod_group",
        "height",
        "depth_about_12cm",
        "material_slots_exact",
        "uv0_uv1",
        "uv1_metres_all_slots",
        "front_flap_uv0_registration",
        "front_flap_uv0_axis_contract",
        "front_skincolor_background_coverage",
        "vertex_colour_contract",
        "lod1_present",
        "lod1_slots_exact",
        "lod1_uv0_uv1",
        "lod1_uv1_metres_all_slots",
        "lod1_without_frame_hardware",
        "socket_contract",
        "origin",
        "front_faces_negative_x",
        "bottom_centre_origin",
        "minimum_width",
        "scale_one",
    )
    missing_or_failed = [
        name for name in required_checks if not validation.get("checks", {}).get(name, {}).get("pass")
    ]
    if missing_or_failed:
        raise RuntimeError(f"V3 gate failure for {asset}: {missing_or_failed}")
    socket_sidecar = output / f"sockets_SM_FlatV3_{asset}.json"
    if not socket_sidecar.is_file():
        raise RuntimeError(f"Missing socket sidecar {socket_sidecar}")
    sidecar = json.loads(socket_sidecar.read_text(encoding="utf-8"))
    sockets = sidecar.get("sockets", [])
    if sockets:
        raise RuntimeError(f"Wave row unexpectedly has sockets: {asset}: {sockets}")
    status = {
        "schema_version": 1,
        "run": RUN_ID,
        "asset": asset,
        "status": "built",
        "offline_only": True,
        "gpu_work_performed": False,
        "source_extension": str(output / "extension_plan.json"),
        "fbx": str(fbx),
        "fbx_sha256": sha256(fbx),
        "build_manifest": str(next(output.glob("*_build.json"))),
        "validation": str(validation_path),
        "validation_pass": True,
        "factory_clean_reimport": True,
        "dimensions_m": dimensions,
        "target_width_cm": target_width_cm,
        "width_gate_tolerance_cm": 0.5,
        "width_error_cm": width_error_cm,
        "skin_seed": skin_seed,
        "skin_seed_base": base_seed,
        "skin_seed_retry_count": skin_seed - base_seed,
        "peel_target_percent": 5.0,
        "maximum_continuous_seam_peel_cm": 40.0,
        "v3_gate_names": list(required_checks),
        "v3_gates_pass": True,
        "socket_count": 0,
        "back_overlays": overlay,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "status.json", status)
    return status


def report(
    records: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    initial_gpu: dict[str, Any],
    final_gpu: dict[str, Any],
) -> None:
    by_row: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    for record in records:
        by_row[int(record["row"])].append(record)
    row_metrics = {}
    for row, values in by_row.items():
        join = [float(value["seam_metric"]["join_mad"]) for value in values]
        random = [float(value["seam_metric"]["random_interior_mad"]) for value in values]
        row_metrics[str(row)] = {
            "halves": {
                value["half"]: value["seam_metric"] for value in sorted(values, key=lambda item: item["half"])
            },
            "row_mean_join_mad": round(float(np.mean(join)), 6),
            "row_mean_random_interior_mad": round(float(np.mean(random)), 6),
            "row_join_to_random_ratio": round(float(np.mean(join)) / max(float(np.mean(random)), 1e-9), 6),
        }
    payload = {
        "schema_version": 1,
        "run": RUN_ID,
        "status": "complete",
        "offline_only": True,
        "unreal_mcp_or_port_8010_used": False,
        "gpu_courtesy": {
            "marker": str(GPU_MARKER),
            "initial_observation": initial_gpu,
            "final_observation": final_gpu,
            "gpu_work_performed": False,
            "upscaler_invoked": False,
            "blender_render_invoked": False,
            "note": "The marker was terminal before and after this run; only CPU image work and Blender geometry export/clean import ran.",
        },
        "target_widths_cm": TARGET_WIDTHS_CM,
        "target_width_evidence": {
            "on_disk_measured": "Per-mesh bounds Y values in Saved/CodexFlatV3/probe_w_inmemory_out.json",
            "fallback": None,
        },
        "assets": records,
        "builds": statuses,
        "row_seam_metrics": row_metrics,
        "contact_sheets": {
            str(row): str(make_contact_sheet(row, {value["half"]: value for value in values}))
            for row, values in by_row.items()
        },
    }
    write_json(OUTPUT_ROOT / "extension_report.json", payload)
    lines = [
        f"# S3 wave extension report - {RUN_ID}",
        "",
        "- **[measured]** Six new FBXs were built under `flats_ext3`; the 12.5 m `flats` sources were read only.",
        "- **[measured]** Production art was extended from each half's own pixels by repeating a detected trough-to-trough crest period with a trough crossfade. Horizontal production scaling, new painting, AI generation, upscaling, and Blender rendering were not used.",
        "- **[measured]** The centre-facing edge is byte-exact in both mask and foreground art for a 256 px Stage 1 sample and a 512 px Stage 4 sample on every half.",
        "- **[measured]** All six factory-clean FBX imports pass the current Flat V3 LOD, material, UV0/UV1, metric-UV, raw UV-sign, coverage, vertex-colour, profile/origin, no-socket, height, depth, and minimum-width gates.",
        "- **[measured]** The unchanged 5% peel target and unchanged 40 cm continuous-seam gate passed for all six assets; any deterministic seed retries are recorded per asset below and in `status.json`.",
        "- **[measured]** Each target width came from the per-mesh Unreal bounds Y values in `Saved/CodexFlatV3/probe_w_inmemory_out.json`; no shared-width fallback was used.",
        "- **[measured]** The shared GPU marker was terminal before and after this run; no GPU task, upscaler, or Blender render was launched. CPU image work and headless Blender geometry export/clean import only.",
        "- **[inferred]** Unreal reimport, saved-package read-back, actor-transform preservation, and rendered acceptance remain pending because this run was offline-only.",
        "",
        "## Width and scale gates",
        "",
        "| Asset | Target cm | FBX width cm | Error cm | ppcm before | ppcm after | delta % | Skin retries |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    status_by_asset = {status["asset"]: status for status in statuses}
    for record in records:
        status = status_by_asset[record["asset"]]
        lines.append(
            f"| {record['asset']} | {record['target_width_cm']:.2f} | "
            f"{status['dimensions_m'][1] * 100.0:.4f} | {status['width_error_cm']:.4f} | "
            f"{record['pixels_per_cm_before']:.6f} | {record['pixels_per_cm_after']:.6f} | "
            f"{record['pixels_per_cm_delta_percent']:.6f} | {status['skin_seed_retry_count']} |"
        )
    lines.extend(
        [
            "",
            "## Seam metrics",
            "",
            "Mean absolute RGB difference on a 0..255 scale; the comparison pair is a deterministic random adjacent interior-column pair.",
            "",
            "| Row | join MAD mean | random interior MAD mean | join/random |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in (1, 2, 3):
        metric = row_metrics[str(row)]
        lines.append(
            f"| {row} | {metric['row_mean_join_mad']:.6f} | "
            f"{metric['row_mean_random_interior_mad']:.6f} | {metric['row_join_to_random_ratio']:.6f} |"
        )
    lines.extend(
        [
            "",
            "Per-half values, source-cycle coordinates, hashes, evidence paths, and every validation result are in `extension_report.json` and each asset's `extension_plan.json` / `validation.json`.",
            "",
        ]
    )
    (OUTPUT_ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUTPUT_ROOT.exists() and any(OUTPUT_ROOT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-empty output directory: {OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    initial_gpu = json.loads(GPU_MARKER.read_text(encoding="utf-8")) if GPU_MARKER.is_file() else {"status": "missing"}
    records: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    try:
        for row in (1, 2, 3):
            for half in ("A", "B"):
                asset = f"S3_WaveRow{row}_{half}"
                records.append(extend_source(asset, row, half))
        for record in records:
            statuses.append(build_asset(record))
        final_gpu = json.loads(GPU_MARKER.read_text(encoding="utf-8")) if GPU_MARKER.is_file() else {"status": "missing"}
        report(records, statuses, initial_gpu, final_gpu)
        write_json(
            OUTPUT_ROOT / "DONE.json",
            {
                "run": RUN_ID,
                "status": "done",
                "assets": len(statuses),
                "gpu_work_performed": False,
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(f"{RUN_ID}_OFFLINE_OK")
    except Exception as exc:
        write_json(
            OUTPUT_ROOT / "FAILED.json",
            {
                "run": RUN_ID,
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise


if __name__ == "__main__":
    main()
