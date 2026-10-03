#!/usr/bin/env python3
"""Gate preferred orientation in Flat V3 peel edges and audit source fields.

The acceptance number is the doubled-angle resultant (equivalently the global
structure-tensor coherence) of SkinMask.R edge gradients inside the recorded
cluster windows.  A circle or a collection of torn islands with varied edge
directions approaches zero; repeated elongated edges approach one.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from argparse import Namespace
from pathlib import Path

import cv2
import numpy as np

import build_skin


FIELD_USAGE = {
    "pilot": {
        "ragged": True,
        "torn_fibre": True,
        "organic_fbm": False,
        "organic_breakup": False,
        "isotropic_breakup": False,
        "isotropic_fibre": False,
        "cluster_envelope": True,
        "peel_score": True,
        "paper_fine": False,
        "paper_modulation": False,
        "curl_lip": False,
        "skin_height": False,
        "skin_normal_xy": False,
    },
    "pilot-organic": {
        "ragged": True,
        "torn_fibre": True,
        "organic_fbm": True,
        "organic_breakup": True,
        "isotropic_breakup": False,
        "isotropic_fibre": False,
        "cluster_envelope": True,
        "peel_score": True,
        "paper_fine": False,
        "paper_modulation": False,
        "curl_lip": False,
        "skin_height": False,
        "skin_normal_xy": False,
    },
    "pilot-isotropic": {
        "ragged": False,
        "torn_fibre": False,
        "organic_fbm": False,
        "organic_breakup": False,
        "isotropic_breakup": True,
        "isotropic_fibre": True,
        "cluster_envelope": True,
        "peel_score": True,
        "paper_fine": False,
        "paper_modulation": False,
        "curl_lip": False,
        "skin_height": False,
        "skin_normal_xy": False,
    },
}


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_peel(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] < 3:
        raise RuntimeError(f"Could not read packed SkinMask: {path}")
    return image[:, :, 2].astype(np.float32) / 255.0


def tensor_result(gx: np.ndarray, gy: np.ndarray, valid: np.ndarray) -> dict:
    magnitude_sq = gx * gx + gy * gy
    selected = valid & np.isfinite(magnitude_sq) & (magnitude_sq > 1e-12)
    positive = magnitude_sq[selected]
    if positive.size < 32:
        raise RuntimeError("ANISOTROPY_TOO_FEW_GRADIENT_SAMPLES")
    cutoff = float(np.percentile(positive, 55.0))
    selected &= magnitude_sq >= cutoff
    jxx = float(np.sum(gx[selected] * gx[selected]))
    jyy = float(np.sum(gy[selected] * gy[selected]))
    jxy = float(np.sum(gx[selected] * gy[selected]))
    denominator = max(jxx + jyy, 1e-20)
    coherence = math.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2) / denominator
    angle = 0.5 * math.degrees(math.atan2(2.0 * jxy, jxx - jyy))
    return {
        "coherence": coherence,
        "dominant_gradient_orientation_deg": angle,
        "selected_gradient_samples": int(np.count_nonzero(selected)),
        "gradient_energy": denominator,
        "selection_percentile": 55.0,
    }


def scalar_field_anisotropy(field: np.ndarray, valid: np.ndarray | None = None) -> dict:
    value = field.astype(np.float32)
    gx = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    if valid is None:
        valid = np.ones(value.shape, dtype=bool)
    else:
        valid = valid.astype(bool)
    valid[:2, :] = False
    valid[-2:, :] = False
    valid[:, :2] = False
    valid[:, -2:] = False
    return tensor_result(gx, gy, valid)


def normal_field_anisotropy(nx: np.ndarray, ny: np.ndarray, valid: np.ndarray) -> dict:
    return tensor_result(nx.astype(np.float32), ny.astype(np.float32), valid.astype(bool))


def cluster_edge_anisotropy(mask_path: Path, manifest_path: Path, crop_cm: float = 128.0) -> dict:
    peel = load_peel(mask_path)
    manifest = load_manifest(manifest_path)
    panel_w_cm, panel_h_cm = manifest["panel_size_cm"]
    height, width = peel.shape
    color_path = manifest_path.parent / manifest["textures"]["SkinColor"]["file"]
    color = cv2.imread(str(color_path), cv2.IMREAD_UNCHANGED)
    if color is None or color.ndim != 3 or color.shape[2] < 4:
        raise RuntimeError(f"Could not read authoritative SkinColor alpha: {color_path}")
    panel_alpha = cv2.resize(
        color[:, :, 3], (width, height), interpolation=cv2.INTER_NEAREST
    ) >= 127
    # The gate is about peel edges *inside* the flat.  Excluding the outer four
    # centimetres prevents a narrow silhouette from being measured as hatching.
    panel_interior_cm = build_skin.metric_distance(panel_alpha, panel_w_cm, panel_h_cm)
    crop_w = max(16, int(round(crop_cm / panel_w_cm * width)))
    crop_h = max(16, int(round(crop_cm / panel_h_cm * height)))
    all_gx = []
    all_gy = []
    orientation_vector = 0.0j
    orientation_length = 0.0
    orientation_segments = 0
    clusters = []
    for centre_x_cm, centre_y_cm, kind in manifest["peel"]["cluster_centres_cm"]:
        centre_x = float(centre_x_cm) / panel_w_cm * (width - 1)
        centre_y = (1.0 - float(centre_y_cm) / panel_h_cm) * (height - 1)
        crop = cv2.getRectSubPix(peel, (crop_w, crop_h), (centre_x, centre_y))
        interior = cv2.getRectSubPix(
            panel_interior_cm, (crop_w, crop_h), (centre_x, centre_y)
        )
        crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
        interior = cv2.resize(interior, (256, 256), interpolation=cv2.INTER_LINEAR)
        crop = cv2.GaussianBlur(crop, (0, 0), 0.8)
        gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
        valid = interior > 4.0
        valid[:3, :] = valid[-3:, :] = False
        valid[:, :3] = valid[:, -3:] = False
        result = tensor_result(gx, gy, valid)
        cluster_vector = 0.0j
        cluster_length = 0.0
        cluster_segments = 0
        for level in (0.08, 0.25, 0.55):
            contours, _hierarchy = cv2.findContours(
                (crop >= level).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
            )
            for contour in contours:
                points = contour[:, 0, :].astype(np.float64)
                if len(points) < 4:
                    continue
                following = np.roll(points, -1, axis=0)
                delta = following - points
                lengths = np.linalg.norm(delta, axis=1)
                midpoints = np.rint((points + following) * 0.5).astype(np.int32)
                midpoints[:, 0] = np.clip(midpoints[:, 0], 0, 255)
                midpoints[:, 1] = np.clip(midpoints[:, 1], 0, 255)
                inside = valid[midpoints[:, 1], midpoints[:, 0]] & (lengths > 0.0)
                if not np.any(inside):
                    continue
                angles = np.arctan2(delta[:, 1], delta[:, 0])
                vector = np.sum(lengths[inside] * np.exp(2.0j * angles[inside]))
                length = float(np.sum(lengths[inside]))
                cluster_vector += vector
                cluster_length += length
                cluster_segments += int(np.count_nonzero(inside))
        cluster_anisotropy = float(abs(cluster_vector) / max(cluster_length, 1e-20))
        result.update({
            "kind": kind,
            "centre_cm": [centre_x_cm, centre_y_cm],
            "orientation_histogram_anisotropy": cluster_anisotropy,
            "orientation_histogram_segment_count": cluster_segments,
        })
        clusters.append(result)
        orientation_vector += cluster_vector
        orientation_length += cluster_length
        orientation_segments += cluster_segments
        magnitude_sq = gx * gx + gy * gy
        positive = magnitude_sq[valid & (magnitude_sq > 1e-12)]
        cutoff = float(np.percentile(positive, 55.0))
        select = valid & (magnitude_sq >= cutoff)
        all_gx.append(gx[select])
        all_gy.append(gy[select])
    gx = np.concatenate(all_gx)
    gy = np.concatenate(all_gy)
    tensor_secondary = tensor_result(gx, gy, np.ones(gx.shape, dtype=bool))
    anisotropy = float(abs(orientation_vector) / max(orientation_length, 1e-20))
    dominant = float(0.5 * math.degrees(math.atan2(
        orientation_vector.imag, orientation_vector.real
    )))
    aggregate = {
        "orientation_histogram_anisotropy": anisotropy,
        "dominant_edge_orientation_deg": dominant,
        "orientation_histogram_segment_count": orientation_segments,
        "orientation_histogram_total_length_px": orientation_length,
        "structure_tensor_secondary": tensor_secondary,
        "method": "doubled-angle contour-orientation anisotropy of SkinMask.R edges at levels 0.08/0.25/0.55 inside 128 cm cluster crops, excluding the outer 4 cm silhouette boundary",
        "cluster_crop_cm": crop_cm,
        "cluster_count": len(clusters),
        "clusters": clusters,
    }
    return aggregate


def build_capture(source_manifest_path: Path, profile: str) -> tuple[dict, dict[str, np.ndarray]]:
    source = load_manifest(source_manifest_path)
    fields: dict[str, np.ndarray] = {}
    with tempfile.TemporaryDirectory(prefix="fv3_anisotropy_") as temp:
        args = Namespace(
            mask=Path(source["inputs"]["mask"]),
            art=Path(source["inputs"]["art"]),
            older_poster=Path(source["inputs"]["older_poster"]),
            paper_displacement=Path(source["inputs"]["paper_displacement"]),
            paper_roughness=Path(source["inputs"]["paper_roughness"]),
            texture_root=Path(__file__).resolve().parents[2],
            aged_output=Path(temp) / "aged_unused",
            stencil_text=source["asset"],
            height_cm=float(source["panel_size_cm"][1]),
            width_cm=float(source["panel_size_cm"][0]),
            color_width=int(source["textures"]["SkinColor"]["size_px"][0]),
            color_height=int(source["textures"]["SkinColor"]["size_px"][1]),
            asset_name=source["asset"],
            output=Path(temp) / "skin",
            diagnostics_output=None,
            seed=int(source["deterministic_seed"]),
            peel_percent=float(source["peel"]["target_percent"]),
            peel_profile=profile,
            substrate_profile=source["front_colour"]["substrate_profile"],
            texture_suffix="_diag",
            skip_aged_textures=True,
            diagnostic_fields=fields,
        )
        generated = build_skin.build(args)
    return generated, fields


def field_audit(source_manifest_path: Path, profile: str) -> dict:
    generated, fields = build_capture(source_manifest_path, profile)
    panel_mask = fields["panel_mask"].astype(bool)
    values = {}
    for name in (
        "ragged", "torn_fibre", "organic_fbm", "organic_breakup",
        "isotropic_breakup", "isotropic_fibre", "cluster_envelope",
        "peel_score", "peel_amount", "paper_fine", "curl_lip", "skin_height",
    ):
        if name in fields:
            values[name] = scalar_field_anisotropy(fields[name], panel_mask.copy())
    if "paper_modulation" in fields:
        color_mask = cv2.resize(
            panel_mask.astype(np.uint8),
            (fields["paper_modulation"].shape[1], fields["paper_modulation"].shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
        values["paper_modulation"] = scalar_field_anisotropy(
            fields["paper_modulation"], color_mask
        )
    values["skin_normal_xy"] = normal_field_anisotropy(
        fields["skin_normal_x"], fields["skin_normal_y"], panel_mask
    )
    usage = FIELD_USAGE[profile]
    for name, result in values.items():
        result["feeds_peel_mask"] = bool(usage.get(name, False))
    panel_w_cm, panel_h_cm = generated["panel_size_cm"]
    return {
        "profile": profile,
        "fields": values,
        "directional_blur_audit": {
            "smooth_noise_sigma_pixels_equal_but_physical_sigma_ratio_x_over_y":
                (1024.0 / panel_w_cm) / (2048.0 / panel_h_cm),
            "pilot_isotropic_sigma_contract": "sigmaX and sigmaY are scaled by axis pixels/cm",
        },
        "cluster_shape": generated["peel"].get("cluster_shape"),
        "cluster_radii_cm": generated["peel"].get("cluster_radii_cm"),
        "legacy_cluster_axis_ratios": (
            [2.0, 2.0, 2.0, 1.12, 1.95, 1.95]
            if profile in ("pilot", "pilot-organic") else []
        ),
        "paper_and_normal_boundary": (
            "paper modulation, curl and skin normal do not feed SkinMask.R; measured because they can reinforce the visible read"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-mask", required=True, type=Path)
    parser.add_argument("--old-manifest", required=True, type=Path)
    parser.add_argument("--round1-mask", required=True, type=Path)
    parser.add_argument("--round1-manifest", required=True, type=Path)
    parser.add_argument("--round2-mask", required=True, type=Path)
    parser.add_argument("--round2-manifest", required=True, type=Path)
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    old = cluster_edge_anisotropy(args.old_mask, args.old_manifest)
    round1 = cluster_edge_anisotropy(args.round1_mask, args.round1_manifest)
    round2 = cluster_edge_anisotropy(args.round2_mask, args.round2_manifest)
    for value in (old, round1, round2):
        value["threshold"] = args.threshold
        value["passes"] = bool(
            value["orientation_histogram_anisotropy"] < args.threshold
        )
    report = {
        "schema_version": 1,
        "metric": "SkinMask.R cluster-edge contour-orientation histogram anisotropy",
        "calibration": "old pilot and round-1 organic must fail; round-2 isotropic must pass",
        "old_pilot": old,
        "round1_organic": round1,
        "round2_isotropic": round2,
        "field_anisotropy": {
            "old_pilot": field_audit(args.old_manifest, "pilot"),
            "round1_organic": field_audit(args.old_manifest, "pilot-organic"),
            "round2_isotropic": field_audit(args.old_manifest, "pilot-isotropic"),
        },
    }
    report["passes"] = bool(
        not old["passes"] and not round1["passes"] and round2["passes"]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "old_anisotropy": old["orientation_histogram_anisotropy"],
        "round1_anisotropy": round1["orientation_histogram_anisotropy"],
        "round2_anisotropy": round2["orientation_histogram_anisotropy"],
        "threshold": args.threshold,
        "check_passes": report["passes"],
    }))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
