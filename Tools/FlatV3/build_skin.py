#!/usr/bin/env python3
"""Build deterministic production Flat V3 skin maps and flap descriptors.

This is an offline CPU tool. Artwork luminance is never used for height. The
default production textures follow Docs/FlatV3Spec_2026-09-30.md: SkinColor is
2048x4096 sRGB; SkinMask and SkinNormal are 1024x2048 linear/normal data. Hero
backdrops may override the colour extent and physical width explicitly while
retaining the same packed skin-map sizes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage


SHEET_WIDTH_M = 1.0
SHEET_HEIGHT_M = 1.5
SHEET_OVERLAP_M = 0.025
ROW_OFFSET = 0.5
HEIGHT_RANGE_CM = 2.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
        raise RuntimeError(f"Could not write {path}")


def cover_resize(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Cover-resample directly from the supplied source, preserving its density."""
    source_h, source_w = image.shape[:2]
    scale = max(width / source_w, height / source_h)
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    resized = cv2.resize(
        image,
        (int(math.ceil(source_w * scale)), int(math.ceil(source_h * scale))),
        interpolation=interpolation,
    )
    y0 = (resized.shape[0] - height) // 2
    x0 = (resized.shape[1] - width) // 2
    return resized[y0 : y0 + height, x0 : x0 + width]


def registered_resize(
    image: np.ndarray,
    native_mask: np.ndarray,
    width: int,
    height: int,
    panel_h_cm: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Resample art and geometry over one shared, uncropped source extent.

    The A2 4x art is a pixel-aligned upscale of the jigsaw mask.  Cover-cropping
    either input destroys that registration because production SkinColor is a
    fixed 1:2 texture while a flat's physical silhouette is usually wider.
    """
    image_h, image_w = image.shape[:2]
    mask_h, mask_w = native_mask.shape
    scale_x = image_w / mask_w
    scale_y = image_h / mask_h
    if abs(scale_x - scale_y) > 1e-6:
        raise RuntimeError(
            "Artwork and cut mask do not share one pixel-aligned extent: "
            f"art={image_w}x{image_h}, mask={mask_w}x{mask_h}, "
            f"scale=({scale_x:.9f},{scale_y:.9f})"
        )
    interpolation = cv2.INTER_AREA if image_w >= width and image_h >= height else cv2.INTER_LANCZOS4
    art = cv2.resize(image, (width, height), interpolation=interpolation)
    geometry_mask = (native_mask > 0).astype(np.uint8)
    rows = np.flatnonzero(geometry_mask.any(axis=1))
    subject_h_px = int(rows[-1] - rows[0] + 1)
    scale_m_per_px = (panel_h_cm / 100.0) / subject_h_px
    minimum_hole_area_px = (0.03 / scale_m_per_px) ** 2
    contours, hierarchy = cv2.findContours(
        geometry_mask.copy(), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    filled_holes = 0
    if hierarchy is not None:
        for index, contour in enumerate(contours):
            if hierarchy[0, index, 3] >= 0 and abs(cv2.contourArea(contour)) < minimum_hole_area_px:
                cv2.drawContours(geometry_mask, [contour], -1, 1, thickness=cv2.FILLED)
                filled_holes += 1
    # The mesh contour is simplified by 0.55 cm and then independently
    # rasterised by the FBX coverage validator. Pad the SkinColor coverage well
    # inside the already-authored 5 cm colour bleed so wide/short rows cannot
    # expose a black texel at that simplified edge.
    coverage_padding_cm = 2.0
    padding_px = max(1, int(math.ceil(coverage_padding_cm / 100.0 / scale_m_per_px)))
    coverage_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (padding_px * 2 + 1, padding_px * 2 + 1)
    )
    geometry_mask = cv2.dilate(geometry_mask, coverage_kernel)
    # Keep every output texel touched by the authoritative source silhouette.
    # The mesh boundary is traced on the native pixel grid, so a half-coverage
    # threshold can shrink the downsampled validation alpha by one texel and
    # expose transparent/black texels beneath otherwise valid Front faces.
    base_mask = cv2.resize(
        (native_mask > 0).astype(np.float32),
        (width, height),
        interpolation=cv2.INTER_AREA,
    ) > 0.0
    mask = cv2.resize(
        geometry_mask.astype(np.float32),
        (width, height),
        interpolation=cv2.INTER_AREA,
    ) > 0.0
    padded_near_black = mask & ~base_mask & (np.max(art, axis=2) <= 6)
    repaired_texels = int(np.count_nonzero(padded_near_black))
    if repaired_texels:
        valid_colour = base_mask & (np.max(art, axis=2) > 6)
        if not valid_colour.any():
            raise RuntimeError("SkinColor source contains no non-black silhouette texels")
        nearest = ndimage.distance_transform_edt(
            ~valid_colour, return_distances=False, return_indices=True
        )
        art[padded_near_black] = art[nearest[0][padded_near_black], nearest[1][padded_near_black]]
    return art, mask, {
        "method": "shared full-extent resample; no cover crop, scale, or offset between art and cut mask",
        "art_to_mask_scale": round(scale_x, 9),
        "source_extent_px": [mask_w, mask_h],
        "output_extent_px": [width, height],
        "geometry_holes_filled_below_cm": 3.0,
        "geometry_holes_filled": filled_holes,
        "coverage_padding_cm": coverage_padding_cm,
        "padded_near_black_texels_repaired": repaired_texels,
    }


def native_density_fill(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Fill without upscaling: reflected copies preserve source-pixel density."""
    source_h, source_w = image.shape[:2]
    if source_w >= width and source_h >= height:
        x0 = (source_w - width) // 2
        y0 = (source_h - height) // 2
        return image[y0 : y0 + height, x0 : x0 + width].copy()
    repeat_x = int(math.ceil(width / source_w)) + 1
    repeat_y = int(math.ceil(height / source_h)) + 1
    rows = []
    for y_index in range(repeat_y):
        row = image if y_index % 2 == 0 else image[::-1]
        tiles = [row if x_index % 2 == 0 else row[:, ::-1] for x_index in range(repeat_x)]
        rows.append(np.concatenate(tiles, axis=1))
    tiled = np.concatenate(rows, axis=0)
    return tiled[:height, :width].copy()


def smooth_noise(
    rng: np.random.Generator,
    height: int,
    width: int,
    coarse: tuple[int, int],
    sigma: float,
) -> np.ndarray:
    small = rng.random((coarse[1], coarse[0]), dtype=np.float32)
    field = cv2.resize(small, (width, height), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), sigmaX=sigma, sigmaY=sigma)
    low, high = float(field.min()), float(field.max())
    return (field - low) / max(high - low, 1e-7)


def metric_distance(binary: np.ndarray, panel_w_cm: float, panel_h_cm: float) -> np.ndarray:
    """Distance inside a binary region in centimetres with square metric samples."""
    height, width = binary.shape
    px_per_cm = max(width / panel_w_cm, height / panel_h_cm)
    metric_width = max(2, int(round(panel_w_cm * px_per_cm)))
    metric = cv2.resize(binary.astype(np.uint8), (metric_width, height), interpolation=cv2.INTER_NEAREST)
    # A rectangular backdrop can fill the complete texture, unlike a cutout
    # silhouette. Padding supplies the physical panel edge to distanceTransform
    # and avoids its no-zero-pixel sentinel/overflow path.
    padded = np.pad(metric, ((1, 1), (1, 1)), mode="constant", constant_values=0)
    distance = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1] / px_per_cm
    return cv2.resize(distance, (width, height), interpolation=cv2.INTER_LINEAR)


def exact_top_mask(score: np.ndarray, valid: np.ndarray, count: int) -> np.ndarray:
    valid_indices = np.flatnonzero(valid.ravel())
    count = max(1, min(count, len(valid_indices)))
    values = score.ravel()[valid_indices]
    chosen_local = np.argpartition(values, len(values) - count)[-count:]
    chosen = valid_indices[chosen_local]
    result = np.zeros(valid.size, dtype=bool)
    result[chosen] = True
    return result.reshape(valid.shape)


def sheet_fields(
    width: int,
    height: int,
    panel_w_cm: float,
    panel_h_cm: float,
) -> dict[str, np.ndarray]:
    px_per_cm_x = width / panel_w_cm
    px_per_cm_y = height / panel_h_cm
    y_cm = (height - 1 - np.arange(height, dtype=np.float32))[:, None] / px_per_cm_y
    x_cm = np.arange(width, dtype=np.float32)[None, :] / px_per_cm_x
    sheet_w_cm = SHEET_WIDTH_M * 100.0
    sheet_h_cm = SHEET_HEIGHT_M * 100.0
    overlap_cm = SHEET_OVERLAP_M * 100.0
    step_x = sheet_w_cm - overlap_cm
    step_y = sheet_h_cm - overlap_cm
    row = np.floor(y_cm / step_y).astype(np.int32)
    row_shift = (row & 1).astype(np.float32) * sheet_w_cm * ROW_OFFSET
    local_x_global = x_cm - row_shift
    col = np.floor(local_x_global / step_x).astype(np.int32)
    local_x = np.mod(local_x_global, step_x)
    local_y = np.mod(y_cm, step_y)
    d_x = np.minimum(local_x, step_x - local_x)
    d_y = np.minimum(local_y, step_y - local_y)
    pair = np.broadcast_to(row, (height, width)).astype(np.int64) * 10000 + col.astype(np.int64) + 2000
    return {
        "x_cm": np.broadcast_to(x_cm, (height, width)),
        "y_cm": np.broadcast_to(y_cm, (height, width)),
        "row": np.broadcast_to(row, (height, width)),
        "col": col,
        "pair": pair,
        "seam_distance_cm": np.minimum(d_x, d_y),
        "vertical_seam_distance_cm": np.broadcast_to(d_x, (height, width)),
        "horizontal_seam_distance_cm": np.broadcast_to(d_y, (height, width)),
        "overlap": (local_x < overlap_cm) | (local_y < overlap_cm),
    }


def draw_torn_seed(
    seed: np.ndarray,
    points_cm: list[tuple[float, float]],
    panel_w_cm: float,
    panel_h_cm: float,
    rng: np.random.Generator,
) -> None:
    height, width = seed.shape
    pts = []
    for x_cm, y_cm in points_cm:
        x = int(round(x_cm / panel_w_cm * (width - 1)))
        y = int(round((1.0 - y_cm / panel_h_cm) * (height - 1)))
        pts.append((x, y))
    cv2.polylines(seed, [np.asarray(pts, np.int32)], False, 255, 1, cv2.LINE_AA)
    if len(pts) >= 3:
        for _ in range(2):
            anchor = pts[int(rng.integers(1, len(pts) - 1))]
            angle = float(rng.uniform(-math.pi, math.pi))
            length = float(rng.uniform(3.0, 6.0))
            dx = length / panel_w_cm * width * math.cos(angle)
            dy = length / panel_h_cm * height * math.sin(angle)
            end = (int(round(anchor[0] + dx)), int(round(anchor[1] + dy)))
            cv2.line(seed, anchor, end, 255, 1, cv2.LINE_AA)


def build_torn_peels(
    rng: np.random.Generator,
    mask: np.ndarray,
    fields: dict[str, np.ndarray],
    panel_w_cm: float,
    panel_h_cm: float,
    target_percent: float,
    profile: str = "pilot",
) -> tuple[np.ndarray, np.ndarray, dict]:
    height, width = mask.shape
    x_cm = fields["x_cm"]
    y_cm = fields["y_cm"]
    edge_distance = metric_distance(mask, panel_w_cm, panel_h_cm)
    ragged = smooth_noise(rng, height, width, (92, 118), 3.0)
    torn_fibre = smooth_noise(rng, height, width, (230, 180), 1.0)
    score = np.zeros((height, width), np.float32)

    def choose_centres(candidate: np.ndarray, wanted: int, minimum_distance_cm: float,
                       occupied: list[tuple[float, float]] | None = None) -> list[tuple[float, float]]:
        positions = np.argwhere(candidate)
        if len(positions) == 0:
            return []
        chosen: list[tuple[float, float]] = []
        occupied = occupied or []
        for _ in range(wanted):
            order = rng.permutation(len(positions))
            picked = None
            for position_index in order[: min(len(order), 4000)]:
                row, col = positions[position_index]
                point = (float(x_cm[row, col]), float(y_cm[row, col]))
                if all(math.hypot(point[0] - other[0], point[1] - other[1]) >= minimum_distance_cm
                       for other in occupied + chosen):
                    picked = point
                    break
            if picked is None:
                break
            chosen.append(picked)
        return chosen

    # The original fixed 110/80 cm exclusions overlap on the 180 cm wave rows,
    # making seam_candidate empty and guaranteeing only three of the required
    # five centres. Preserve those maxima on tall flats but scale them down for
    # short scenery.
    if panel_h_cm < 300.0:
        seam_bottom_margin_cm = panel_h_cm * 0.05
        seam_top_margin_cm = panel_h_cm * 0.10
    else:
        seam_bottom_margin_cm = 110.0
        seam_top_margin_cm = 80.0
    seam_candidate = (mask & (fields["seam_distance_cm"] < 1.4)
                      & (edge_distance > 18.0)
                      & (y_cm > seam_bottom_margin_cm)
                      & (y_cm < panel_h_cm - seam_top_margin_cm))
    corner_candidate = mask & (fields["seam_distance_cm"] < 5.0) & (edge_distance < 24.0) & (y_cm > 80.0)
    base_candidate = mask & (y_cm < 70.0)
    if profile == "bottom-heavy":
        # Backdrops need damage to stay subordinate to the image. Keep every
        # selected cluster at the base, away from the legible mid-beach action.
        base_candidate = mask & (y_cm < 110.0)
        seam_centres = []
        corner_centres = []
        base_centres = choose_centres(base_candidate, 9, 205.0)
    else:
        seam_centres = choose_centres(seam_candidate, 3, 150.0)
        corner_centres = choose_centres(corner_candidate, 1, 1.0)
        base_centres = choose_centres(base_candidate, 2, 120.0)
    centres = [(x, y, "seam") for x, y in seam_centres]
    centres += [(x, y, "corner") for x, y in corner_centres]
    centres += [(x, y, "base") for x, y in base_centres]
    if len(centres) < 5:
        # Short wave rows may expose only two widely separated sheet-seam
        # islands. Backfill deterministically from the same approved damage
        # zones, relaxing spacing to the panel's physical height while still
        # requiring five distinct clusters.
        fallback_candidate = mask & (
            (fields["seam_distance_cm"] < 5.0)
            | (edge_distance < 24.0)
            | (y_cm < 70.0)
        )
        for minimum_distance_cm in (max(30.0, panel_h_cm * 0.5), 30.0, 10.0):
            occupied = [(x, y) for x, y, _ in centres]
            additions = choose_centres(
                fallback_candidate, 5 - len(centres), minimum_distance_cm, occupied
            )
            for x, y in additions:
                row = int(np.clip(round((panel_h_cm - y) / panel_h_cm * (height - 1)), 0, height - 1))
                col = int(np.clip(round(x / panel_w_cm * (width - 1)), 0, width - 1))
                if fields["seam_distance_cm"][row, col] < 5.0:
                    kind = "seam"
                elif edge_distance[row, col] < 24.0:
                    kind = "corner"
                else:
                    kind = "base"
                centres.append((x, y, kind))
            if len(centres) >= 5:
                break
    if len(centres) < 5:
        raise RuntimeError(f"Could not place five clustered peel centres; got {len(centres)}")

    selected_seam_support = np.zeros((height, width), dtype=bool)
    for index, (cx, cy, kind) in enumerate(centres):
        selected_seam_support |= np.square(x_cm - cx) + np.square(y_cm - cy) <= 18.0 ** 2
        if kind == "seam":
            row = int(np.clip(round((panel_h_cm - cy) / panel_h_cm * (height - 1)), 0, height - 1))
            col = int(np.clip(round(cx / panel_w_cm * (width - 1)), 0, width - 1))
            horizontal = fields["horizontal_seam_distance_cm"][row, col] <= fields["vertical_seam_distance_cm"][row, col]
            if profile == "bottom-heavy":
                radius_x, radius_y = ((75.0, 105.0) if horizontal else (105.0, 75.0))
            else:
                radius_x, radius_y = ((24.0, 48.0) if horizontal else (48.0, 24.0))
            seam_pull = np.exp(-fields["seam_distance_cm"] / 4.5)
        elif kind == "corner":
            radius_x, radius_y = 56.0, 50.0
            seam_pull = np.maximum(np.exp(-fields["seam_distance_cm"] / 7.0), np.exp(-edge_distance / 7.0))
        else:
            radius_x, radius_y = ((150.0, 105.0) if profile == "bottom-heavy" else (82.0, 42.0))
            seam_pull = np.maximum(np.exp(-fields["seam_distance_cm"] / 8.0), np.exp(-y_cm / 16.0))
        dx = (x_cm - cx) / radius_x
        dy = (y_cm - cy) / radius_y
        radius = np.sqrt(dx * dx + dy * dy)
        envelope = np.clip(1.45 - radius, 0.0, 1.0)
        broken_edge = np.power(envelope, 1.35) * (0.22 + 0.78 * np.power(ragged, 1.7))
        if profile == "bottom-heavy":
            # Do not reuse the pilot's diagonal sinusoid here: on a pale,
            # rectilinear backdrop its breakup reads as printed hatching.
            split = 0.58 + 0.42 * torn_fibre
        else:
            split = 0.70 + 0.30 * np.sin((dx * 8.0 + dy * 5.0 + index * 1.9) * math.pi)
        cluster = broken_edge * split * (0.42 + 0.58 * seam_pull) * (0.72 + 0.28 * torn_fibre)
        score = np.maximum(score, cluster.astype(np.float32))

    score[(fields["seam_distance_cm"] < 2.0) & ~selected_seam_support] = 0.0
    score *= mask
    count = int(round(np.count_nonzero(mask) * target_percent / 100.0))
    if np.count_nonzero(score > 0.0) < count:
        raise RuntimeError("Clustered peel support is too small for requested coverage")
    peeled = exact_top_mask(score, mask, count)
    inside_distance = metric_distance(peeled, panel_w_cm, panel_h_cm)
    peel_amount = np.clip(inside_distance / 1.7, 0.0, 1.0)
    peel_amount[peeled] = np.maximum(peel_amount[peeled], 0.12)
    peel_amount[~mask] = 0.0
    return peeled, peel_amount.astype(np.float32), {
        "profile": profile,
        "selected_cluster_count": len(centres),
        "cluster_kinds": [kind for _, _, kind in centres],
        "cluster_centres_cm": [[round(x, 3), round(y, 3), kind] for x, y, kind in centres],
    }


def longest_seam_run_cm(
    peeled: np.ndarray,
    seam_distance_cm: np.ndarray,
    panel_w_cm: float,
    panel_h_cm: float,
) -> float:
    """Measure the largest axis extent of each seam-adjacent peel component."""
    seam_peel = (peeled & (seam_distance_cm < 2.0)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(seam_peel, 8)
    longest = 0.0
    for label in range(1, count):
        _, _, width, height, _ = stats[label]
        longest = max(longest, width / peeled.shape[1] * panel_w_cm, height / peeled.shape[0] * panel_h_cm)
    return float(longest)


def flap_descriptors(
    peeled: np.ndarray,
    seam_distance_cm: np.ndarray,
    panel_w_cm: float,
    panel_h_cm: float,
    asset_name: str,
) -> list[dict]:
    seam_peel = (peeled & (seam_distance_cm < 8.0)).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(seam_peel, 8)
    candidates = []
    for label in range(1, count):
        x, y, width, height, area = stats[label]
        if area >= 18:
            candidates.append((int(area), int(x), int(y), int(width), int(height), centroids[label], label))
    candidates.sort(reverse=True, key=lambda item: item[0])
    if len(candidates) < 3:
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(peeled.astype(np.uint8), 8)
        candidates = []
        for label in range(1, count):
            x, y, width, height, area = stats[label]
            if area >= 18:
                candidates.append((int(area), int(x), int(y), int(width), int(height), centroids[label], label))
        candidates.sort(reverse=True, key=lambda item: item[0])
    result = []
    image_h, image_w = peeled.shape
    for index, (area, x, y, width, height, _, label) in enumerate(candidates[:5], start=1):
        component = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        contour = cv2.approxPolyDP(contour, max(1.0, perimeter * 0.012), True).reshape(-1, 2)
        if len(contour) > 40:
            contour = contour[:: int(math.ceil(len(contour) / 40))]
        outline_uv = [[round(float(px / image_w), 8), round(float(1.0 - py / image_h), 8)] for px, py in contour]
        u0, u1 = x / image_w, (x + width) / image_w
        v0, v1 = 1.0 - (y + height) / image_h, 1.0 - y / image_h
        physical_w = (u1 - u0) * panel_w_cm
        physical_h = (v1 - v0) * panel_h_cm
        if physical_w >= physical_h:
            physical_w = float(np.clip(physical_w, 15.0, 65.0))
            centre_u = (u0 + u1) * 0.5
            u0, u1 = centre_u - physical_w / panel_w_cm * 0.5, centre_u + physical_w / panel_w_cm * 0.5
            physical_h = float(np.clip(physical_h, 6.0, 24.0))
            centre_v = (v0 + v1) * 0.5
            v0, v1 = centre_v - physical_h / panel_h_cm * 0.5, centre_v + physical_h / panel_h_cm * 0.5
            orientation = "horizontal"
        else:
            physical_w = float(np.clip(physical_w, 6.0, 24.0))
            centre_u = (u0 + u1) * 0.5
            u0, u1 = centre_u - physical_w / panel_w_cm * 0.5, centre_u + physical_w / panel_w_cm * 0.5
            physical_h = float(np.clip(physical_h, 15.0, 65.0))
            centre_v = (v0 + v1) * 0.5
            v0, v1 = centre_v - physical_h / panel_h_cm * 0.5, centre_v + physical_h / panel_h_cm * 0.5
            orientation = "vertical"
        result.append({
            "name": f"{asset_name}_Flap_{index}",
            "component_pixels": area,
            "uv_bounds_bottom_left": [round(float(u0), 8), round(float(v0), 8), round(float(u1), 8), round(float(v1), 8)],
            "orientation": orientation,
            "curl_cm": round(0.55 + 0.08 * index, 3),
            "outline_uv_bottom_left": outline_uv,
        })
    if not (3 <= len(result) <= 6):
        raise RuntimeError(f"Expected 3-6 seam-adjacent flap descriptors; got {len(result)}")
    return result


def age_colour(source: np.ndarray, ao: np.ndarray, displacement: np.ndarray,
               darkness: float, saturation: float) -> np.ndarray:
    source_f = source.astype(np.float32) / 255.0
    grey = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    ao_f = cv2.resize(ao, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    disp = cv2.resize(displacement, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    cavity = np.abs(cv2.Laplacian(disp, cv2.CV_32F, ksize=3))
    cavity /= max(float(np.quantile(cavity, 0.995)), 1e-5)
    dirt = np.clip((1.0 - ao_f) * 1.25 + cavity * 0.30, 0.0, 1.0)
    colour = grey[:, :, None] + (source_f - grey[:, :, None]) * saturation
    colour *= darkness * (1.0 - dirt[:, :, None] * 0.42)
    colour *= np.array([0.88, 0.94, 1.02], np.float32)[None, None, :]
    return np.clip(colour * 255.0, 0.0, 255.0).astype(np.uint8)


def build_aged_textures(args: argparse.Namespace, registered_art: np.ndarray,
                         rng: np.random.Generator) -> dict:
    root = args.texture_root.resolve()
    output = args.aged_output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def load_set(folder: Path, stem: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        colour = cv2.imread(str(folder / f"{stem}_Color.jpg"), cv2.IMREAD_COLOR)
        rough = cv2.imread(str(folder / f"{stem}_Roughness.jpg"), cv2.IMREAD_GRAYSCALE)
        normal = cv2.imread(str(folder / f"{stem}_NormalDX.jpg"), cv2.IMREAD_COLOR)
        ao = cv2.imread(str(folder / f"{stem}_AO.jpg"), cv2.IMREAD_GRAYSCALE)
        disp = cv2.imread(str(folder / f"{stem}_Displacement.jpg"), cv2.IMREAD_GRAYSCALE)
        if any(item is None for item in (colour, rough, normal, ao, disp)):
            raise FileNotFoundError(f"Incomplete texture set: {folder / stem}")
        return colour, rough, normal, ao, disp

    soft = load_set(root / "FrameTimber" / "AgedWoodSiding", "T_FrameTimber_AgedWoodSiding")
    ply = load_set(root / "BoardFace" / "Plywood", "T_BoardFace_Plywood")
    steel = load_set(root / "PoleSteel" / "BluePaintedPlate", "T_PoleSteel_BluePaintedPlate")
    aged_soft = age_colour(soft[0], soft[3], soft[4], 0.61, 0.30)
    aged_ply_square = age_colour(ply[0], ply[3], ply[4], 0.56, 0.24)
    aged_steel = age_colour(steel[0], steel[3], steel[4], 0.64, 0.32)

    # One non-tiling ply back per flat: dusty handling marks, front-colour
    # overspray at the perimeter, and one worn low-contrast stencil baked in.
    aged_ply = cover_resize(aged_ply_square, 2048, 4096)
    h, w = aged_ply.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce((xx, w - 1 - xx, yy, h - 1 - yy)).astype(np.float32)
    edge_alpha = np.clip(1.0 - edge / (0.055 * min(w, h)), 0.0, 1.0)
    edge_alpha *= (0.13 + 0.10 * smooth_noise(rng, h, w, (40, 70), 20.0))
    paint_colour = np.mean(registered_art.reshape(-1, 3), axis=0)
    aged_ply = np.clip(aged_ply.astype(np.float32) * (1.0 - edge_alpha[:, :, None]) + paint_colour[None, None, :] * edge_alpha[:, :, None], 0, 255).astype(np.uint8)
    for index in range(9):
        x0 = int(rng.uniform(0.08, 0.92) * w)
        y0 = int(rng.uniform(0.08, 0.92) * h)
        length = int(rng.uniform(0.03, 0.10) * h)
        overlay = aged_ply.copy()
        cv2.line(overlay, (x0, y0), (x0 + int(rng.uniform(-0.06, 0.06) * w), y0 + length), (42, 48, 52), max(2, w // 520), cv2.LINE_AA)
        aged_ply = cv2.addWeighted(aged_ply, 0.94, overlay, 0.06, 0.0)
    stencil = np.zeros((h, w), np.uint8)
    text = args.stencil_text.replace("·", ".")
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 1.45, 3
    text_size = cv2.getTextSize(text, font, scale, thickness)[0]
    origin = (int(w * 0.52 - text_size[0] * 0.5), int(h * 0.78))
    cv2.putText(stencil, text, origin, font, scale, 255, thickness, cv2.LINE_AA)
    wear = smooth_noise(rng, h, w, (160, 240), 1.2)
    stencil[wear > 0.63] = 0
    stencil_alpha = (stencil.astype(np.float32) / 255.0) * 0.10
    ink = np.array([38.0, 42.0, 44.0], np.float32)
    aged_ply = np.clip(aged_ply.astype(np.float32) * (1.0 - stencil_alpha[:, :, None]) + ink[None, None, :] * stencil_alpha[:, :, None], 0, 255).astype(np.uint8)

    files = {
        "softwood_color": "T_FlatV3_AgedSoftwood_Color.png",
        "softwood_roughness": "T_FlatV3_AgedSoftwood_Roughness.png",
        "softwood_normal": "T_FlatV3_AgedSoftwood_NormalDX.png",
        "plywood_color": "T_FlatV3_AgedPlywood_Stencil_Color.png",
        "plywood_roughness": "T_FlatV3_AgedPlywood_Roughness.png",
        "plywood_normal": "T_FlatV3_AgedPlywood_NormalDX.png",
        "steel_color": "T_FlatV3_AgedSteel_Color.png",
    }
    write_png(output / files["softwood_color"], aged_soft)
    write_png(output / files["softwood_roughness"], np.clip(soft[1].astype(np.float32) * 0.55 + 112.0, 0, 255).astype(np.uint8))
    write_png(output / files["softwood_normal"], soft[2])
    write_png(output / files["plywood_color"], aged_ply)
    write_png(output / files["plywood_roughness"], cv2.resize(np.clip(ply[1].astype(np.float32) * 0.48 + 126.0, 0, 255).astype(np.uint8), (1024, 2048), interpolation=cv2.INTER_AREA))
    write_png(output / files["plywood_normal"], cv2.resize(ply[2], (1024, 2048), interpolation=cv2.INTER_AREA))
    write_png(output / files["steel_color"], aged_steel)
    manifest = {"schema_version": 1, "asset": args.asset_name, "source_root": str(root), "grading": "desaturated, darkened, AO/cavity dirt, dust, sparse handling marks, perimeter front-colour overspray", "stencil": {"text": args.stencil_text, "contrast": 0.10, "worn": True, "baked_into": files["plywood_color"]}, "files": files}
    (output / "aged_texture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    native_mask = cv2.imread(str(args.mask), cv2.IMREAD_GRAYSCALE)
    if native_mask is None:
        raise FileNotFoundError(args.mask)
    native_h, native_w = native_mask.shape
    panel_h_cm = float(args.height_cm)
    panel_w_cm = float(args.width_cm) if args.width_cm is not None else panel_h_cm * native_w / native_h
    color_w, color_h = int(args.color_width), int(args.color_height)
    data_w, data_h = 1024, 2048
    mask = cv2.resize(native_mask, (data_w, data_h), interpolation=cv2.INTER_AREA) >= 127
    fields = sheet_fields(data_w, data_h, panel_w_cm, panel_h_cm)
    peeled, peel_amount, peel_layout = build_torn_peels(
        rng, mask, fields, panel_w_cm, panel_h_cm, args.peel_percent, args.peel_profile
    )
    edge_distance = metric_distance(mask, panel_w_cm, panel_h_cm)
    damage_zone = (fields["seam_distance_cm"] < 8.0) | (edge_distance < 12.0) | (fields["y_cm"] < 80.0)
    flaps = flap_descriptors(peeled, fields["seam_distance_cm"], panel_w_cm, panel_h_cm, args.asset_name)

    paper_disp = cv2.imread(str(args.paper_displacement), cv2.IMREAD_GRAYSCALE)
    paper_rough = cv2.imread(str(args.paper_roughness), cv2.IMREAD_GRAYSCALE)
    if paper_disp is None or paper_rough is None:
        raise FileNotFoundError("Paper displacement or roughness source is missing")
    tile_cm = 35.0
    map_x = np.mod(fields["x_cm"] / tile_cm * paper_disp.shape[1], paper_disp.shape[1]).astype(np.float32)
    map_y = np.mod(fields["y_cm"] / tile_cm * paper_disp.shape[0], paper_disp.shape[0]).astype(np.float32)
    fine = cv2.remap(paper_disp, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255.0
    fine = (fine - float(np.mean(fine[mask]))) * 0.035
    overlap_ridge = np.exp(-np.square(fields["seam_distance_cm"] / 0.65)).astype(np.float32) * 0.09
    wrinkles_a = smooth_noise(rng, data_h, data_w, (110, 80), 4.0)
    wrinkles_b = cv2.GaussianBlur(wrinkles_a, (0, 0), 16.0)
    wrinkles = np.clip(wrinkles_a - wrinkles_b, -0.5, 0.5) * 0.11
    bubbles = np.zeros((data_h, data_w), np.float32)
    valid_yx = np.argwhere(mask)
    for _ in range(9):
        cy, cx = valid_yx[int(rng.integers(0, len(valid_yx)))]
        radius_cm = float(rng.uniform(4.0, 10.0))
        rx, ry = radius_cm * data_w / panel_w_cm, radius_cm * data_h / panel_h_cm * float(rng.uniform(0.7, 1.25))
        yy = (np.arange(data_h, dtype=np.float32) - cy)[:, None] / max(ry, 1.0)
        xx = (np.arange(data_w, dtype=np.float32) - cx)[None, :] / max(rx, 1.0)
        rr = xx * xx + yy * yy
        bubbles += np.where(rr < 1.0, np.power(1.0 - np.clip(rr, 0.0, 1.0), 1.8) * 0.15, 0.0)
    distance_from_peel = metric_distance(~peeled, panel_w_cm, panel_h_cm)
    curl_lip = np.exp(-np.square(distance_from_peel / 2.2)) * (~peeled) * mask * 0.34
    height_cm = fine + overlap_ridge + wrinkles + bubbles + curl_lip
    height_cm -= float(height_cm[mask].min())
    height_cm = np.clip(height_cm, 0.0, 0.72)
    height_cm[~mask] = 0.0

    px_per_cm_x, px_per_cm_y = data_w / panel_w_cm, data_h / panel_h_cm
    dh_drow, dh_dx = np.gradient(height_cm, 1.0 / px_per_cm_y, 1.0 / px_per_cm_x)
    nx, ny, nz = -dh_dx, -dh_drow, np.ones_like(dh_dx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal_rgb = np.stack((nx / length, ny / length, nz / length), axis=2)
    normal_rgb = np.round((normal_rgb * 0.5 + 0.5) * 255.0).astype(np.uint8)
    normal_rgb[~mask] = (128, 128, 255)

    rough_fine = cv2.remap(paper_rough, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255.0
    weather = smooth_noise(rng, data_h, data_w, (54, 42), 13.0)
    roughness = np.clip(0.46 + (rough_fine - 0.5) * 0.08 + weather * 0.08, 0.44, 0.57)
    paste = (smooth_noise(rng, data_h, data_w, (38, 32), 18.0) > 0.70) & (fields["seam_distance_cm"] < 18.0) & mask
    roughness[paste] = 0.34 + 0.03 * weather[paste]
    roughness[peeled] = np.maximum(roughness[peeled], 0.58)
    roughness[~mask] = 0.0
    paste_gloss_ao = np.clip(0.88 - paste.astype(np.float32) * 0.30 - peel_amount * 0.12, 0.35, 1.0)
    paste_gloss_ao[~mask] = 0.0

    art_source = cv2.imread(str(args.art), cv2.IMREAD_COLOR)
    older_source = cv2.imread(str(args.older_poster), cv2.IMREAD_COLOR)
    if art_source is None or older_source is None:
        raise FileNotFoundError("Front artwork or full-resolution older poster is missing")
    art, color_mask, registration = registered_resize(
        art_source, native_mask, color_w, color_h, panel_h_cm
    )
    older = native_density_fill(older_source, color_w, color_h)
    older_gray = cv2.cvtColor(older, cv2.COLOR_BGR2GRAY).astype(np.float32)
    if args.substrate_profile == "pale-backdrop":
        older = np.clip(
            (older_gray[:, :, None] + (older.astype(np.float32) - older_gray[:, :, None]) * 0.34) * 0.90,
            0,
            255,
        ).astype(np.uint8)
    else:
        older = np.clip((older_gray[:, :, None] + (older.astype(np.float32) - older_gray[:, :, None]) * 0.42) * 0.62, 0, 255).astype(np.uint8)
    color_fields = sheet_fields(color_w, color_h, panel_w_cm, panel_h_cm)
    pairs = color_fields["pair"]
    unique_pairs = np.unique(pairs[color_mask])
    pair_to_id = {int(value): index + 1 for index, value in enumerate(unique_pairs.tolist())}
    sheet_id = np.zeros((color_h, color_w), np.int32)
    offsets = []
    dx_table = np.zeros(len(unique_pairs) + 1, np.float32)
    dy_table = np.zeros(len(unique_pairs) + 1, np.float32)
    substrate_table = np.zeros(len(unique_pairs) + 1, np.uint8)
    for value in unique_pairs:
        sheet = pair_to_id[int(value)]
        dx, dy = rng.uniform(-0.45, 0.45, 2).astype(float)
        dx_table[sheet], dy_table[sheet] = dx, dy
        hash_value = (sheet * 1103515245 + args.seed) & 0xFFFFFFFF
        substrate_table[sheet] = 1 if hash_value % 20 < 9 else (2 if hash_value % 20 < 17 else 3)
        sheet_id[pairs == value] = sheet
        offsets.append({"sheet_id": sheet, "pair": int(value), "uv_offset_cm": [round(dx, 4), round(dy, 4)], "substrate": {1: "dirty_grey_cream_backing", 2: "older_poster", 3: "grey_primer"}[int(substrate_table[sheet])]})
    remap_x = np.broadcast_to(np.arange(color_w, dtype=np.float32)[None, :], (color_h, color_w)).copy()
    remap_y = np.broadcast_to(np.arange(color_h, dtype=np.float32)[:, None], (color_h, color_w)).copy()
    remap_x -= dx_table[sheet_id] * color_w / panel_w_cm
    remap_y += dy_table[sheet_id] * color_h / panel_h_cm
    registered_art = cv2.remap(art, remap_x, remap_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    backing_noise = smooth_noise(rng, color_h, color_w, (70, 100), 15.0)
    stain_noise = smooth_noise(rng, color_h, color_w, (34, 50), 30.0)
    backing = np.empty((color_h, color_w, 3), np.float32)
    primer = np.empty_like(backing)
    if args.substrate_profile == "pale-backdrop":
        backing[:] = (184.0, 190.0, 194.0)
        backing -= backing_noise[:, :, None] * np.array([7.0, 9.0, 12.0], np.float32)
        backing -= np.power(stain_noise, 2.4)[:, :, None] * np.array([6.0, 8.0, 12.0], np.float32)
        primer[:] = (150.0, 154.0, 158.0)
    else:
        backing[:] = (98.0, 108.0, 114.0)
        backing -= backing_noise[:, :, None] * np.array([10.0, 13.0, 18.0], np.float32)
        backing -= np.power(stain_noise, 2.4)[:, :, None] * np.array([7.0, 11.0, 18.0], np.float32)
        primer[:] = (69.0, 73.0, 76.0)
    substrate = backing.copy()
    substrate_ids = substrate_table[sheet_id]
    substrate[substrate_ids == 2] = older[substrate_ids == 2]
    substrate[substrate_ids == 3] = primer[substrate_ids == 3]
    peel_color = cv2.resize(peel_amount, (color_w, color_h), interpolation=cv2.INTER_CUBIC)
    peel_color = np.clip(peel_color, 0.0, 1.0)[:, :, None]
    # Paper modulation is neutral around 1.0: it adds fibre variation without
    # applying another grade or darkening the A2 4x pixels.
    paper_modulation = 1.0 + cv2.resize(fine, (color_w, color_h), interpolation=cv2.INTER_CUBIC) * 0.45
    paper_modulation /= max(float(np.mean(paper_modulation[color_mask])), 1e-6)
    modulated_art = np.clip(registered_art.astype(np.float32) * paper_modulation[:, :, None], 0.0, 255.0)
    paper_off_color = registered_art.astype(np.float32) * (1.0 - peel_color) + substrate * peel_color
    skin_color = modulated_art * (1.0 - peel_color) + substrate * peel_color
    skin_color = np.clip(skin_color, 0.0, 255.0).astype(np.uint8)
    # Validation reserves linear <=0.002 (approximately sRGB <=6/255) as its
    # uncovered-background sentinel. Keep truly covered black paint visually
    # black while moving it just above that sentinel instead of weakening the
    # coverage gate.
    near_black_covered = color_mask & (np.max(skin_color, axis=2) <= 6)
    near_black_sentinel_texels_lifted = int(np.count_nonzero(near_black_covered))
    skin_color[near_black_covered] = np.maximum(skin_color[near_black_covered], 8)
    skin_color[~color_mask] = 0

    aged_manifest = None if args.skip_aged_textures else build_aged_textures(args, registered_art, rng)

    height_u8 = np.round(height_cm / HEIGHT_RANGE_CM * 255.0).astype(np.uint8)
    peel_u8 = np.round(peel_amount * 255.0).astype(np.uint8)
    rough_u8 = np.round(roughness * 255.0).astype(np.uint8)
    soak_u8 = np.round(paste_gloss_ao * 255.0).astype(np.uint8)
    skin_mask_bgra = cv2.merge((rough_u8, height_u8, peel_u8, soak_u8))

    color_name = f"T_{args.asset_name}_SkinColor.png"
    mask_name = f"T_{args.asset_name}_SkinMask.png"
    normal_name = f"T_{args.asset_name}_SkinNormal.png"
    # Carry the one authoritative silhouette in alpha even though the production
    # Front material is opaque.  It is validation metadata: FBX UV coverage can
    # now distinguish valid dark painting from masked-out canvas.
    skin_color_bgra = cv2.merge((skin_color[:, :, 0], skin_color[:, :, 1], skin_color[:, :, 2], color_mask.astype(np.uint8) * 255))
    write_png(output / color_name, skin_color_bgra)
    write_png(output / mask_name, skin_mask_bgra)
    write_png(output / normal_name, normal_rgb[:, :, ::-1])
    diagnostic_paper_off = None
    if args.diagnostics_output is not None:
        diagnostics_output = args.diagnostics_output.resolve()
        diagnostics_output.mkdir(parents=True, exist_ok=True)
        diagnostic_paper_off = f"T_{args.asset_name}_SkinColor_PaperOff.png"
        paper_off_u8 = np.clip(paper_off_color, 0.0, 255.0).astype(np.uint8)
        paper_off_bgra = cv2.merge((paper_off_u8[:, :, 0], paper_off_u8[:, :, 1], paper_off_u8[:, :, 2], color_mask.astype(np.uint8) * 255))
        write_png(diagnostics_output / diagnostic_paper_off, paper_off_bgra)

    flap_name = f"{args.asset_name}_flaps.json"
    (output / flap_name).write_text(json.dumps({"schema_version": 1, "asset": args.asset_name, "flaps": flaps}, indent=2), encoding="utf-8")
    sheet_name = f"{args.asset_name}_sheet_grid.json"
    sheet_grid = {"schema_version": 1, "SheetWidthM": SHEET_WIDTH_M, "SheetHeightM": SHEET_HEIGHT_M, "SheetOverlapM": SHEET_OVERLAP_M, "RowOffset": ROW_OFFSET, "sheets": offsets}
    (output / sheet_name).write_text(json.dumps(sheet_grid, indent=2), encoding="utf-8")

    peel_percent = 100.0 * np.count_nonzero(peeled) / np.count_nonzero(mask)
    zone_percent = 100.0 * np.count_nonzero(peeled & damage_zone) / max(np.count_nonzero(peeled), 1)
    seam_run_cm = longest_seam_run_cm(peeled, fields["seam_distance_cm"], panel_w_cm, panel_h_cm)
    if seam_run_cm > 40.0:
        raise RuntimeError(f"Continuous seam peel run is {seam_run_cm:.3f} cm; limit is 40 cm")
    manifest = {
        "schema_version": 2,
        "generator": "Tools/FlatV3/build_skin.py",
        "asset": args.asset_name,
        "deterministic_seed": args.seed,
        "panel_size_cm": [round(panel_w_cm, 6), panel_h_cm],
        "inputs": {
            "mask": str(args.mask.resolve()), "mask_sha256": sha256(args.mask),
            "art": str(args.art.resolve()), "art_sha256": sha256(args.art), "art_source_px": [int(art_source.shape[1]), int(art_source.shape[0])], "registration": registration,
            "older_poster": str(args.older_poster.resolve()), "older_poster_sha256": sha256(args.older_poster), "older_poster_source_px": [int(older_source.shape[1]), int(older_source.shape[0])], "sampling": "native source pixels at SkinColor texel density; reflected fill only, no low-res preview and no upscaling",
            "paper_displacement": str(args.paper_displacement.resolve()), "paper_displacement_sha256": sha256(args.paper_displacement),
            "paper_roughness": str(args.paper_roughness.resolve()), "paper_roughness_sha256": sha256(args.paper_roughness),
        },
        "textures": {
            "SkinColor": {"file": color_name, "size_px": [color_w, color_h], "srgb": True, "import_compression": "Default/BC7", "alpha": "authoritative cut-mask coverage for registration validation; opaque Front material does not use it"},
            "SkinMask": {"file": mask_name, "size_px": [data_w, data_h], "srgb": False, "import_compression": "TC_Masks", "channels": {"R": "continuous peel amount", "G": f"paper height 0..{HEIGHT_RANGE_CM} cm", "B": "roughness", "A": "paste-soak gloss/AO"}},
            "SkinNormal": {"file": normal_name, "size_px": [data_w, data_h], "srgb": False, "import_compression": "Normalmap/BC5-ready", "convention": "DirectX"},
        },
        "peel": {"target_percent": args.peel_percent, "measured_percent": round(peel_percent, 6), "in_damage_zone_percent": round(zone_percent, 6), "form": ("irregular torn clusters confined to the base; intact seams remain faint height ridges" if args.peel_profile == "bottom-heavy" else "irregular torn clusters at a few seams, corners and the base; intact seams remain faint height ridges"), **peel_layout, "longest_seam_run_cm": round(seam_run_cm, 6), "maximum_seam_run_cm": 40.0, "flap_count": len(flaps)},
        "front_colour": {"source_rule": "registered art over the exact shared mask extent, plus zero-mean paper modulation and peel substrate only; no colour grade or darkening", "substrate_profile": args.substrate_profile, "paper_modulation_range": [round(float(paper_modulation[color_mask].min()), 6), round(float(paper_modulation[color_mask].max()), 6)], "paper_modulation_mean": round(float(np.mean(paper_modulation[color_mask])), 6), "dirty_grey_cream_backing_bgr_range": [round(float(backing.min()), 3), round(float(backing.max()), 3)], "near_black_background_sentinel_srgb_max": 6, "covered_texel_floor_srgb": 8, "near_black_sentinel_texels_lifted": near_black_sentinel_texels_lifted, "diagnostic_paper_off": str((args.diagnostics_output.resolve() / diagnostic_paper_off)) if diagnostic_paper_off else None},
        "roughness": {"intact_target": 0.50, "measured_min": round(float(roughness[mask].min()), 6), "measured_max": round(float(roughness[mask].max()), 6)},
        "height": {"maximum_cm": round(float(height_cm.max()), 6), "source_rule": "paper displacement, overlaps, wrinkles, bubbles and peel curl lips only; never artwork luminance"},
        "sheet_grid": {"file": sheet_name, "SheetWidthM": SHEET_WIDTH_M, "SheetHeightM": SHEET_HEIGHT_M, "SheetOverlapM": SHEET_OVERLAP_M, "RowOffset": ROW_OFFSET},
        "halftone": "procedural in Unreal material; no per-asset halftone texture emitted",
        "flaps": flap_name,
        "aged_textures": None if aged_manifest is None else {"directory": str(args.aged_output.resolve()), "manifest": "aged_texture_manifest.json", "files": aged_manifest["files"]},
    }
    manifest_name = f"{args.asset_name}_skin_manifest.json"
    (output / manifest_name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    mi_params = {
        "schema_version": 1,
        "asset": args.asset_name,
        "parents": {"Front": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front", "Flap": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap"},
        "texture_parameters": {"SkinColor": color_name, "SkinMask": mask_name, "SkinNormal": normal_name},
        "scalar_parameters": {"SheetWidthM": SHEET_WIDTH_M, "SheetHeightM": SHEET_HEIGHT_M, "SheetOverlapM": SHEET_OVERLAP_M, "RowOffset": ROW_OFFSET},
        "uv_contract": "UV1 metres; Front/Flap U from mesh Y and V from mesh Z",
    }
    (output / f"{args.asset_name}_mi_params.json").write_text(json.dumps(mi_params, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--art", required=True, type=Path)
    parser.add_argument("--older-poster", required=True, type=Path)
    parser.add_argument("--paper-displacement", required=True, type=Path)
    parser.add_argument("--paper-roughness", required=True, type=Path)
    parser.add_argument("--texture-root", required=True, type=Path)
    parser.add_argument("--aged-output", required=True, type=Path)
    parser.add_argument("--stencil-text", required=True)
    parser.add_argument("--height-cm", type=float, required=True)
    parser.add_argument("--width-cm", type=float, help="Physical panel width; default derives it from the native mask aspect")
    parser.add_argument("--color-width", type=int, default=2048)
    parser.add_argument("--color-height", type=int, default=4096)
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics-output", type=Path)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--peel-percent", type=float, default=5.0)
    parser.add_argument("--peel-profile", choices=("pilot", "bottom-heavy"), default="pilot")
    parser.add_argument("--substrate-profile", choices=("pilot", "pale-backdrop"), default="pilot")
    parser.add_argument("--skip-aged-textures", action="store_true")
    args = parser.parse_args()
    if args.peel_profile == "pilot" and not (4.0 <= args.peel_percent <= 6.0):
        parser.error("--peel-percent must be 4..6 for the approved pilot look")
    if args.peel_profile == "bottom-heavy" and not (2.0 <= args.peel_percent <= 3.0):
        parser.error("--peel-percent must be 2..3 for the bottom-heavy backdrop look")
    if args.color_width <= 0 or args.color_height <= 0:
        parser.error("--color-width and --color-height must be positive")
    if args.width_cm is not None and args.width_cm <= 0:
        parser.error("--width-cm must be positive")
    return args


if __name__ == "__main__":
    built = build(parse_args())
    print("FLAT_V3_SKIN_OK")
    print(f"asset={built['asset']}")
    print(f"peel_percent={built['peel']['measured_percent']}")
    print(f"flaps={built['peel']['flap_count']}")
    print(f"textures={','.join(value['file'] for value in built['textures'].values())}")
