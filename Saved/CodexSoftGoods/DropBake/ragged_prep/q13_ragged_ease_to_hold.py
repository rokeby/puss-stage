#!/usr/bin/env python3
"""Q13: post-process the ragged P02 vertex stream into an eased held cache.

DRY performs every offline measurement without writing outputs. APPLY requires
the literal confirmation below, writes additive worktree outputs, and invokes
Blender exactly once for Alembic export/read-back only. The preview is written
offline with OpenCV from the held numpy stream. REVERT never deletes: it
moves Q13 outputs into a timestamped Backups folder.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

APPLY_CONFIRM = "APPLY_RAGGED_EASE_TO_HOLD"
REVERT_CONFIRM = "REVERT_RAGGED_EASE_TO_HOLD"
RUN_SCHEMA = "pussstage.ragged_ease_to_hold.v1"
FPS = 30
BLEND_FRAMES = 30
STANDING_NAMES = {
    "Post L", "Post R",
    "Cat plinth L (Fixtures)", "Cat body L (Fixtures)",
    "Cat plinth R (Fixtures)", "Cat body R (Fixtures)",
    "Proscenium Wing L (paper side flat)",
    "Proscenium Wing R (paper side flat)",
}


def sha256(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                return h.hexdigest()
            h.update(data)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def input_paths(source_root: Path) -> dict[str, Path]:
    base = source_root / "Saved" / "CodexSoftGoods" / "DropBake"
    prep = base / "ragged_prep"
    return {
        "stream": base / "ragged_proscenium_p02_stream.f32",
        "sidecar": base / "ragged_proscenium_p02_stream.json",
        "record": base / "ragged_proscenium_p02.json",
        "abc": base / "ragged_proscenium_p02.abc",
        "colliders": prep / "StageFrontColliders_2026-10-08_proscenium.json",
    }


def output_paths(output_root: Path) -> dict[str, Path]:
    base = output_root / "Saved" / "CodexSoftGoods" / "DropBake"
    prep = base / "ragged_prep"
    return {
        "base": base,
        "stream": base / "ragged_proscenium_p02_held_stream.f32",
        "sidecar": base / "ragged_proscenium_p02_held_stream.json",
        "abc": base / "ragged_proscenium_p02_held.abc",
        "preview": base / "ragged_proscenium_p02_held_preview.mp4",
        "record": base / "ragged_proscenium_p02_held.json",
        "curve_csv": prep / "Q13_RAGGED_SPEED_CURVE.csv",
        "curve_png": prep / "Q13_RAGGED_SPEED_CURVE.png",
        "blender_report": prep / "Q13_BLENDER_EXPORT.json",
        "blender_script": prep / "q13_export_held_blender.py",
    }


def validate_inputs(paths: dict[str, Path]) -> tuple[dict, dict, dict]:
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise SystemExit("Missing input(s): " + ", ".join(missing))
    sidecar, record, collider_doc = (
        load_json(paths["sidecar"]), load_json(paths["record"]), load_json(paths["colliders"])
    )
    if sidecar.get("dtype") != "float32" or sidecar.get("layout") != "frame-major xyz":
        raise SystemExit("Unsupported stream sidecar")
    nverts = int(sidecar["vertices"])
    frames = int(record["frames"])
    expected = frames * nverts * 3 * np.dtype(np.float32).itemsize
    if paths["stream"].stat().st_size != expected:
        raise SystemExit(f"Stream size mismatch: expected {expected}, got {paths['stream'].stat().st_size}")
    if int(record["release_frame"]) != 480 or int(record["show_start"]) != 450 or frames != 1080:
        raise SystemExit("Q13 authority mismatch: expected release 480, show_start 450, frames 1080")
    return sidecar, record, collider_doc


def boxes_from_doc(collider_doc: dict) -> tuple[list[dict], list[dict]]:
    floors, standing = [], []
    for box in collider_doc["boxes"]:
        entry = {
            "name": box["name"],
            "lo": np.asarray(box["min_cm"], dtype=np.float32) / 100.0,
            "hi": np.asarray(box["max_cm"], dtype=np.float32) / 100.0,
        }
        if "floor" in box["name"].lower():
            floors.append(entry)
        if box["name"] in STANDING_NAMES:
            standing.append(entry)
    if {b["name"] for b in standing} != STANDING_NAMES:
        raise SystemExit("Standing-collider set does not match POSTBAKE_CHECK mapping")
    return floors, standing


def to_stage(points: np.ndarray) -> np.ndarray:
    # bake declaration: UE_X = 100*Blender_y, UE_Y = 100*Blender_x, UE_Z = 100*Blender_z
    return points[:, [1, 0, 2]]


def support_top(points: np.ndarray, floors: list[dict]) -> np.ndarray:
    stage = to_stage(points)
    support = np.full(len(points), -np.inf, dtype=np.float32)
    for box in floors:
        inside_xy = ((stage[:, 0] >= box["lo"][0]) & (stage[:, 0] <= box["hi"][0]) &
                     (stage[:, 1] >= box["lo"][1]) & (stage[:, 1] <= box["hi"][1]))
        support[inside_xy] = np.maximum(support[inside_xy], box["hi"][2])
    return support


def collision_counts(points: np.ndarray, floors: list[dict], standing: list[dict], tol_m=0.005):
    stage = to_stage(points)
    support = support_top(points, floors)
    supported = np.isfinite(support)
    floor_pen = supported & (stage[:, 2] < support - tol_m)
    standing_count = 0
    by_name = {}
    for box in standing:
        inside = np.all((stage > box["lo"] + tol_m) & (stage < box["hi"] - tol_m), axis=1)
        count = int(inside.sum())
        by_name[box["name"]] = count
        standing_count += count
    depth = float(np.max(support[floor_pen] - stage[floor_pen, 2])) if np.any(floor_pen) else 0.0
    return int(floor_pen.sum()), depth, standing_count, by_name


def boundary_vertices(faces: list[list[int]], nverts: int) -> np.ndarray:
    edge_counts: dict[tuple[int, int], int] = defaultdict(int)
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edge_counts[tuple(sorted((int(a), int(b))))] += 1
    boundary = sorted({v for e, count in edge_counts.items() if count == 1 for v in e})
    if not boundary or boundary[-1] >= nverts:
        raise SystemExit("Invalid face topology in sidecar")
    return np.asarray(boundary, dtype=np.int32)


def adjacency(faces: list[list[int]], nverts: int) -> list[set[int]]:
    out = [set() for _ in range(nverts)]
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            a, b = int(a), int(b)
            out[a].add(b)
            out[b].add(a)
    return out


def speed_curves(stream: np.memmap) -> tuple[np.ndarray, np.ndarray]:
    frames = stream.shape[0]
    vmax = np.zeros(frames, dtype=np.float64)
    p95 = np.zeros(frames, dtype=np.float64)
    prev = np.asarray(stream[0], dtype=np.float32)
    for i in range(1, frames):
        cur = np.asarray(stream[i], dtype=np.float32)
        step = np.linalg.norm(cur - prev, axis=1)
        vmax[i] = float(step.max())
        p95[i] = float(np.quantile(step, 0.95))
        prev = cur
    return vmax, p95


def rolling_median(values: np.ndarray, radius: int = 7) -> np.ndarray:
    out = np.empty_like(values)
    for i in range(len(values)):
        out[i] = np.median(values[max(0, i-radius):min(len(values), i+radius+1)])
    return out


def choose_landing(stream: np.memmap, faces: list[list[int]], record: dict,
                   floors: list[dict], vmax: np.ndarray, p95: np.ndarray) -> tuple[int, dict]:
    first = int(record.get("first_frame", 1))
    release = int(record["release_frame"])
    release_idx = release - first
    boundary = boundary_vertices(faces, stream.shape[1])
    pre = np.asarray(stream[release_idx - 1])
    # Ragged hem: boundary vertices below 3 m immediately before release. This includes torn lower
    # boundaries deliberately; holes higher in the sheet do not qualify.
    hem = boundary[pre[boundary, 2] < 3.0]
    if len(hem) < 100:
        raise SystemExit(f"Hem detection found only {len(hem)} vertices")
    tail_start = max(release_idx + 60, stream.shape[0] - 150)
    smooth_max = rolling_median(vmax, 7)
    smooth_p95 = rolling_median(p95, 7)
    plateau_max = float(np.quantile(smooth_max[tail_start:], 0.65))
    plateau_p95 = float(np.quantile(smooth_p95[tail_start:], 0.65))
    contact_curve = np.zeros(stream.shape[0], dtype=np.float64)
    candidates = []
    for i in range(release_idx + 1, stream.shape[0] - BLEND_FRAMES):
        pts = np.asarray(stream[i])
        support = support_top(pts[hem], floors)
        valid = np.isfinite(support)
        contact = valid & ((pts[hem, 2] - support) <= 0.08) & ((pts[hem, 2] - support) >= -0.005)
        ratio = float(contact.sum() / max(1, valid.sum()))
        contact_curve[i] = ratio
        # Require a material part of the torn hem to have reached support, then a 15-frame
        # sustained arrival at the measured late-run motion plateau.
        stop = min(stream.shape[0], i + 15)
        sustained = (np.quantile(smooth_max[i:stop], 0.8) <= plateau_max * 1.20 and
                     np.quantile(smooth_p95[i:stop], 0.8) <= plateau_p95 * 1.20)
        if ratio >= 0.10 and sustained:
            candidates.append(i)
    if not candidates:
        raise SystemExit("No landing frame satisfies hem-contact and sustained-plateau criteria")
    idx = candidates[0]
    return idx + first, {
        "hem_boundary_vertices": int(len(hem)),
        "contact_threshold_fraction": 0.10,
        "contact_tolerance_m": 0.08,
        "contact_fraction_at_L": float(contact_curve[idx]),
        "plateau_tail_frames": [tail_start + first, stream.shape[0] - 1 + first],
        "plateau_smoothed_max_m_per_frame": plateau_max,
        "plateau_smoothed_p95_m_per_frame": plateau_p95,
        "smoothed_max_at_L_m_per_frame": float(smooth_max[idx]),
        "smoothed_p95_at_L_m_per_frame": float(smooth_p95[idx]),
    }


def choose_hold(stream: np.memmap, first: int, L: int, floors: list[dict], standing: list[dict],
                vmax: np.ndarray, p95: np.ndarray) -> tuple[int, dict]:
    start = L - first
    local_max = rolling_median(vmax, 2)
    local_p95 = rolling_median(p95, 2)
    rows = []
    for i in range(start, stream.shape[0]):
        fp, depth, sp, _ = collision_counts(np.asarray(stream[i]), floors, standing)
        blend_fp = blend_sp = 0
        blend_depth = 0.0
        hold = np.asarray(stream[i])
        for frame in range(L, L + BLEND_FRAMES + 1):
            if frame >= L + BLEND_FRAMES:
                pts = hold
            else:
                w = smootherstep((frame - L) / BLEND_FRAMES)
                pts = np.asarray(stream[frame-first]) * (1.0 - w) + hold * w
            bfp, bdepth, bsp, _ = collision_counts(pts, floors, standing)
            blend_fp += bfp
            blend_sp += bsp
            blend_depth = max(blend_depth, bdepth)
        rows.append((blend_sp, blend_fp, blend_depth, sp, fp, depth,
                     local_p95[i], local_max[i], i))
    best = min(rows)
    blend_sp, blend_fp, blend_depth, sp, fp, depth, lp, lm, idx = best
    return idx + first, {
        "selection_order": ["blend_standing_aabb_vertex_frames", "blend_floor_penetrating_vertex_frames",
                            "blend_floor_penetration_depth_m", "standing_aabb_vertices",
                            "floor_penetration_vertices", "floor_penetration_depth_m",
                            "local_p95_m_per_frame", "local_max_m_per_frame"],
        "blend_standing_aabb_vertex_frames": int(blend_sp),
        "blend_floor_penetrating_vertex_frames": int(blend_fp),
        "blend_floor_penetration_depth_m": float(blend_depth),
        "standing_aabb_vertices": int(sp),
        "floor_penetration_vertices": int(fp),
        "floor_penetration_depth_m": float(depth),
        "local_p95_m_per_frame": float(lp),
        "local_max_m_per_frame": float(lm),
        "real_source_frame": True,
    }


def smootherstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def eased_frame(stream: np.memmap, first: int, L: int, H: int, frame: int) -> np.ndarray:
    if frame < L:
        return np.asarray(stream[frame-first])
    hold = np.asarray(stream[H-first])
    if frame >= L + BLEND_FRAMES:
        return hold
    w = smootherstep((frame - L) / BLEND_FRAMES)
    return np.asarray(stream[frame-first]) * (1.0 - w) + hold * w


def nonadjacent_proxy(points: np.ndarray, adj: list[set[int]], k: int = 12) -> float:
    distances, indices = cKDTree(points).query(points, k=k, workers=-1)
    best = math.inf
    for i in range(len(points)):
        for dist, j in zip(distances[i, 1:], indices[i, 1:]):
            if int(j) not in adj[i]:
                best = min(best, float(dist))
                break
    return best


def evaluate_blend(stream: np.memmap, faces: list[list[int]], first: int, L: int, H: int,
                   floors: list[dict], standing: list[dict]) -> dict:
    adj = adjacency(faces, stream.shape[1])
    floor_total = standing_total = 0
    max_floor_depth = max_speed = 0.0
    by_name_total = defaultdict(int)
    proxy_eased, proxy_original = [], []
    previous = None
    for frame in range(L, L + BLEND_FRAMES + 1):
        pts = eased_frame(stream, first, L, H, frame).astype(np.float32, copy=False)
        fp, depth, sp, by_name = collision_counts(pts, floors, standing)
        floor_total += fp
        standing_total += sp
        max_floor_depth = max(max_floor_depth, depth)
        for name, count in by_name.items():
            by_name_total[name] += count
        if previous is not None:
            max_speed = max(max_speed, float(np.linalg.norm(pts - previous, axis=1).max()) * FPS)
        previous = pts
        proxy_eased.append(nonadjacent_proxy(pts, adj))
        proxy_original.append(nonadjacent_proxy(np.asarray(stream[frame-first]), adj))
    hold_a = eased_frame(stream, first, L, H, L + BLEND_FRAMES)
    hold_b = eased_frame(stream, first, L, H, L + BLEND_FRAMES + 1)
    held_speed = float(np.linalg.norm(hold_b - hold_a, axis=1).max()) * FPS
    return {
        "floor_support": {
            "verdict": "PASS" if floor_total == 0 else "FAIL",
            "penetrating_vertex_frames": int(floor_total),
            "maximum_depth_m": max_floor_depth,
            "tolerance_m": 0.005,
        },
        "standing_collider_aabb": {
            "verdict": "PASS" if standing_total == 0 else "FAIL",
            "inside_vertex_frames": int(standing_total),
            "by_name_vertex_frames": dict(by_name_total),
        },
        "motion": {
            "verdict": "PASS" if held_speed == 0.0 else "FAIL",
            "max_blend_speed_m_per_s": max_speed,
            "max_speed_after_blend_m_per_s": held_speed,
        },
        "self_intersection_proxy": {
            "definition": "minimum cKDTree distance to one of 11 nearest vertices excluding mesh-edge neighbours",
            "blend_min_nonadjacent_distance_m": float(min(proxy_eased)),
            "original_same_window_min_nonadjacent_distance_m": float(min(proxy_original)),
            "ratio_eased_to_original": float(min(proxy_eased) / max(min(proxy_original), 1e-12)),
            "gate": "REPORT_ONLY",
        },
    }


def analysis(source_root: Path) -> tuple[dict, np.memmap, dict, dict[str, Path]]:
    paths = input_paths(source_root)
    sidecar, record, collider_doc = validate_inputs(paths)
    first = int(sidecar.get("first_frame", 1))
    frames, nverts = int(record["frames"]), int(sidecar["vertices"])
    stream = np.memmap(paths["stream"], dtype=np.float32, mode="r", shape=(frames, nverts, 3))
    faces = [[int(v) for v in face] for face in sidecar["faces"]]
    floors, standing = boxes_from_doc(collider_doc)
    vmax, p95 = speed_curves(stream)
    L, landing = choose_landing(stream, faces, record, floors, vmax, p95)
    H, hold = choose_hold(stream, first, L, floors, standing, vmax, p95)
    gates = evaluate_blend(stream, faces, first, L, H, floors, standing)
    curve = {
        "first_frame": first,
        "fps": FPS,
        "max_m_per_frame": vmax.tolist(),
        "p95_m_per_frame": p95.tolist(),
    }
    result = {
        "schema": RUN_SCHEMA,
        "mode": "DRY",
        "success_marker": None,
        "evidence": "measured",
        "inputs": {k: str(v) for k, v in paths.items()},
        "source": {"frames": frames, "vertices": nverts, "first_frame": first,
                   "release_frame": int(record["release_frame"]), "show_start": int(record["show_start"])},
        "landing_frame_L": L,
        "hold_frame_H": H,
        "landing_selection": landing,
        "hold_selection": hold,
        "blend": {"frames": [L, L + BLEND_FRAMES], "duration_frames": BLEND_FRAMES,
                  "duration_seconds": BLEND_FRAMES / FPS, "function": "smootherstep"},
        "gates": gates,
        "speed_curve": curve,
        "controls": {},
    }
    required = [gates["floor_support"]["verdict"], gates["standing_collider_aabb"]["verdict"],
                gates["motion"]["verdict"]]
    result["offline_gate_verdict"] = "PASS" if all(v == "PASS" for v in required) else "FAIL"
    return result, stream, sidecar, paths


def write_curve(result: dict, outputs: dict[str, Path]):
    curve = result["speed_curve"]
    first = curve["first_frame"]
    outputs["curve_csv"].parent.mkdir(parents=True, exist_ok=True)
    with outputs["curve_csv"].open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["frame", "max_m_per_frame", "p95_m_per_frame", "max_m_per_s", "p95_m_per_s"])
        for i, (mx, p) in enumerate(zip(curve["max_m_per_frame"], curve["p95_m_per_frame"])):
            writer.writerow([i + first, mx, p, mx * FPS, p * FPS])
    width, height, margin = 1200, 500, 50
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    start = result["source"]["release_frame"] - first
    ys = np.asarray(curve["max_m_per_frame"][start:]) * FPS
    ps = np.asarray(curve["p95_m_per_frame"][start:]) * FPS
    ymax = max(1e-6, float(np.quantile(ys, 0.99)))
    def xy(index, value):
        x = margin + index * (width - 2 * margin) / max(1, len(ys) - 1)
        y = height - margin - min(value, ymax) * (height - 2 * margin) / ymax
        return x, y
    draw.rectangle((margin, margin, width-margin, height-margin), outline="black")
    draw.line([xy(i, v) for i, v in enumerate(ys)], fill=(180, 40, 40), width=2)
    draw.line([xy(i, v) for i, v in enumerate(ps)], fill=(40, 80, 190), width=2)
    for frame, color in ((result["landing_frame_L"], (30, 140, 30)), (result["hold_frame_H"], (120, 30, 140))):
        i = frame - result["source"]["release_frame"]
        x, _ = xy(i, 0)
        draw.line((x, margin, x, height-margin), fill=color, width=2)
    draw.text((margin+8, margin+8), "max speed (red), p95 (blue), L (green), H (purple); m/s", fill="black")
    outputs["curve_png"].parent.mkdir(parents=True, exist_ok=True)
    image.save(outputs["curve_png"])


def write_stream(result: dict, stream: np.memmap, sidecar: dict, outputs: dict[str, Path]):
    outputs["base"].mkdir(parents=True, exist_ok=True)
    first = int(sidecar.get("first_frame", 1))
    L, H = result["landing_frame_L"], result["hold_frame_H"]
    tmp = outputs["stream"].with_suffix(".f32.tmp")
    with tmp.open("wb") as fh:
        for frame in range(first, first + stream.shape[0]):
            np.asarray(eased_frame(stream, first, L, H, frame), dtype=np.float32).tofile(fh)
    os.replace(tmp, outputs["stream"])
    held_sidecar = dict(sidecar)
    held_sidecar.update({"source": str(input_paths(Path(result["source_root"]))["stream"]),
                         "transform": "original before L; smootherstep original-to-H over L..L+30; exact H thereafter",
                         "landing_frame_L": L, "hold_frame_H": H})
    outputs["sidecar"].write_text(json.dumps(held_sidecar, indent=2), encoding="utf-8")


def write_offline_preview(outputs: dict[str, Path], start: int, end: int, fps: int,
                          landing: int, hold: int) -> dict:
    """Write a fixed-scale front/side point preview without invoking Blender."""
    import cv2

    sidecar = load_json(outputs["sidecar"])
    nverts = int(sidecar["vertices"])
    first = int(sidecar.get("first_frame", 1))
    frames = end - first + 1
    stream = np.memmap(outputs["stream"], dtype=np.float32, mode="r",
                       shape=(frames, nverts, 3))
    sample_step = max(1, nverts // 7000)
    sample = np.arange(0, nverts, sample_step, dtype=np.int32)
    # Fixed bounds avoid a visually misleading camera pump as the cloth settles.
    front_min = np.asarray([math.inf, math.inf], dtype=np.float64)
    front_max = np.asarray([-math.inf, -math.inf], dtype=np.float64)
    side_min = front_min.copy()
    side_max = front_max.copy()
    for frame in range(start, end + 1, 10):
        pts = np.asarray(stream[frame-first])[sample]
        front = pts[:, [0, 2]]
        side = pts[:, [1, 2]]
        front_min = np.minimum(front_min, front.min(axis=0))
        front_max = np.maximum(front_max, front.max(axis=0))
        side_min = np.minimum(side_min, side.min(axis=0))
        side_max = np.maximum(side_max, side.max(axis=0))

    width, height, panel, margin = 640, 360, 320, 18
    outputs["preview"].parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(outputs["preview"]), cv2.VideoWriter_fourcc(*"mp4v"),
                             float(fps), (width, height))
    if not writer.isOpened():
        raise SystemExit(f"Could not open offline MP4 writer: {outputs['preview']}")

    def pixels(values, lo, hi, x0):
        span = np.maximum(hi - lo, 1e-6)
        scale = min((panel - 2 * margin) / span[0], (height - 2 * margin) / span[1])
        used = span * scale
        offset = np.asarray([x0 + (panel-used[0])/2, (height-used[1])/2])
        xy = (values - lo) * scale + offset
        xy[:, 1] = height - 1 - xy[:, 1]
        return np.rint(xy).astype(np.int32)

    written = 0
    try:
        for frame in range(start, end + 1):
            pts = np.asarray(stream[frame-first])[sample]
            front_xy = pixels(pts[:, [0, 2]], front_min, front_max, 0)
            side_xy = pixels(pts[:, [1, 2]], side_min, side_max, panel)
            image = np.full((height, width, 3), (18, 17, 22), dtype=np.uint8)
            image[front_xy[:, 1], front_xy[:, 0]] = (95, 155, 235)
            image[side_xy[:, 1], side_xy[:, 0]] = (95, 155, 235)
            cv2.line(image, (panel, 0), (panel, height-1), (70, 70, 78), 1)
            cv2.putText(image, "FRONT", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (225, 225, 225), 1, cv2.LINE_AA)
            cv2.putText(image, "SIDE", (panel+12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (225, 225, 225), 1, cv2.LINE_AA)
            phase = "original" if frame < landing else ("ease" if frame < landing + BLEND_FRAMES else "hold")
            cv2.putText(image, f"frame {frame}  {phase}  L={landing} H={hold}", (12, height-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (210, 210, 215), 1, cv2.LINE_AA)
            writer.write(image)
            written += 1
    finally:
        writer.release()

    capture = cv2.VideoCapture(str(outputs["preview"]))
    try:
        readback = {
            "frames": int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))),
            "width": int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            "height": int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
            "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        }
    finally:
        capture.release()
    expected_frames = end - start + 1
    if (written != expected_frames or readback["frames"] != expected_frames or
            readback["width"] != width or readback["height"] != height or
            abs(readback["fps"] - fps) > 0.01):
        raise SystemExit(f"Offline preview read-back mismatch: written={written}, readback={readback}")
    return {
        "method": "OpenCV point plot from held float32 stream; Blender not used",
        "views": ["front_xz", "side_yz"],
        "resolution": [width, height],
        "frame_range": [start, end],
        "fps": fps,
        "sampled_vertices": int(len(sample)),
        "readback": readback,
    }


def validate_staged_continuation(result: dict, outputs: dict[str, Path]) -> dict:
    required = [outputs["stream"], outputs["sidecar"], outputs["record"],
                outputs["curve_csv"], outputs["curve_png"]]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Q13b continuation is missing staged first-run output(s): " + ", ".join(missing))
    sidecar = load_json(outputs["sidecar"])
    prior = load_json(outputs["record"])
    expected_size = (result["source"]["frames"] * result["source"]["vertices"] * 3 *
                     np.dtype(np.float32).itemsize)
    checks = {
        "stream_size": outputs["stream"].stat().st_size == expected_size,
        "sidecar_L_H": (sidecar.get("landing_frame_L"), sidecar.get("hold_frame_H")) ==
                       (result["landing_frame_L"], result["hold_frame_H"]),
        "record_L_H": (prior.get("landing_frame_L"), prior.get("hold_frame_H")) ==
                      (result["landing_frame_L"], result["hold_frame_H"]),
        "record_gate": prior.get("offline_gate_verdict") == "PASS",
    }
    if not all(checks.values()):
        raise SystemExit(f"Q13b staged continuation validation failed: {checks}")
    return {"verdict": "PASS", "checks": checks,
            "staged_sha256": {path.name: sha256(path) for path in required}}


def make_preapply_backup(output_root: Path, outputs: dict[str, Path], run_id: str) -> Path:
    backup = output_root / "Backups" / f"PreRaggedEaseToHold-{run_id}"
    backup.mkdir(parents=True, exist_ok=False)
    existing = [outputs[key] for key in ("stream", "sidecar", "record", "curve_csv", "curve_png")
                if outputs[key].is_file()]
    manifest = {"run_id": run_id, "evidence": "measured", "preexisting": [
        {"path": str(path), "size": path.stat().st_size, "sha256": sha256(path)} for path in existing
    ]}
    # Only the record is mutated by this continuation. The 560 MB staged stream and
    # other intermediates remain byte-for-byte fixed and are protected by hashes.
    if outputs["record"].is_file():
        shutil.copy2(outputs["record"], backup / outputs["record"].name)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return backup


def blender_running() -> list[str]:
    proc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blender.exe", "/FO", "CSV", "/NH"],
                          capture_output=True, text=True, check=False)
    return [line for line in proc.stdout.splitlines() if "blender.exe" in line.lower()]


def blender_export(blender: Path, inputs: dict[str, Path], outputs: dict[str, Path], result: dict):
    running = blender_running()
    if running:
        raise SystemExit("REFUSED: another blender.exe is running: " + " | ".join(running))
    cmd = [str(blender), "-b", "--factory-startup", "--python", str(outputs["blender_script"]), "--",
           "--source-abc", str(inputs["abc"]), "--held-stream", str(outputs["stream"]),
           "--sidecar", str(outputs["sidecar"]), "--output-abc", str(outputs["abc"]),
           "--report", str(outputs["blender_report"]),
           "--start", "450", "--end", "1080", "--fps", str(FPS),
           "--landing", str(result["landing_frame_L"]), "--hold", str(result["hold_frame_H"])]
    completed = subprocess.run(cmd, check=False)
    if completed.returncode:
        raise SystemExit(f"Blender export failed with exit code {completed.returncode}")
    # Blender can return zero even when a --python script raises. The report marker
    # and both material outputs are therefore the authoritative process result.
    required = [outputs["abc"], outputs["blender_report"]]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("Blender process returned without required output(s): " + ", ".join(missing))
    report = load_json(outputs["blender_report"])
    if report.get("success_marker") != "Q13_BLENDER_EXPORT_READBACK_OK":
        raise SystemExit("Blender report lacks Q13_BLENDER_EXPORT_READBACK_OK")


def run_harness() -> dict:
    # Positive: endpoints and exact post-blend hold. Negative: naive linear easing is distinguishable,
    # penetration and standing-AABB controls are detected.
    base = np.zeros((40, 4, 3), dtype=np.float32)
    for i in range(40):
        base[i, :, 0] = i
    class Fake:
        shape = base.shape
        def __getitem__(self, item): return base[item]
    fake = Fake()
    a = eased_frame(fake, 1, 5, 20, 5)
    b = eased_frame(fake, 1, 5, 20, 35)
    floor = [{"name": "floor", "lo": np.asarray([-1, -1, -0.05], dtype=np.float32),
              "hi": np.asarray([1, 1, 0], dtype=np.float32)}]
    standing = [{"name": "box", "lo": np.asarray([2, 2, 0], dtype=np.float32),
                 "hi": np.asarray([3, 3, 1], dtype=np.float32)}]
    safe = np.asarray([[0, 0, 0.1], [4, 4, 2]], dtype=np.float32)
    floor_bad = np.asarray([[0, 0, -0.1]], dtype=np.float32)
    standing_bad = np.asarray([[2.5, 2.5, 0.5]], dtype=np.float32)
    safe_counts = collision_counts(safe, floor, standing)[:3]
    floor_counts = collision_counts(floor_bad, floor, standing)[:3]
    standing_counts = collision_counts(standing_bad, floor, standing)[:3]
    pos = [bool(np.array_equal(a, base[4])), bool(np.array_equal(b, base[19])),
           smootherstep(0.5) == 0.5, safe_counts == (0, 0.0, 0)]
    neg = [not math.isclose(smootherstep(0.25), 0.25), APPLY_CONFIRM != REVERT_CONFIRM,
           floor_counts[0] == 1 and floor_counts[1] > 0, standing_counts[2] == 1]
    return {"positive": {"passed": sum(pos), "total": len(pos), "results": pos},
            "negative": {"passed": sum(neg), "total": len(neg), "results": neg}}


def revert(output_root: Path, confirm: str):
    if confirm != REVERT_CONFIRM:
        raise SystemExit(f"REVERT requires --confirm {REVERT_CONFIRM}")
    outputs = output_paths(output_root)
    present = [p for k, p in outputs.items() if k not in {"base", "blender_script"} and p.exists()]
    if not present:
        print("Q13_RAGGED_EASE_REVERTED|nothing-present")
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = output_root / "Backups" / f"RevertedRaggedEaseToHold-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    for path in present:
        shutil.move(str(path), str(backup / path.name))
    print(f"Q13_RAGGED_EASE_REVERTED|backup={backup}|moved={len(present)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["DRY", "APPLY", "REVERT"])
    parser.add_argument("--confirm", default="")
    parser.add_argument("--source-root", type=Path, default=Path(r"E:\PussStage"))
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--blender", type=Path, default=Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"))
    args = parser.parse_args()
    source_root, output_root = args.source_root.resolve(), args.output_root.resolve()
    if source_root == output_root:
        raise SystemExit("REFUSED: source and output roots must differ; main tree is read-only")
    if args.mode == "REVERT":
        revert(output_root, args.confirm)
        return
    result, stream, sidecar, inputs = analysis(source_root)
    result["source_root"] = str(source_root)
    result["output_root"] = str(output_root)
    result["controls"] = run_harness()
    if args.mode == "DRY":
        print(json.dumps({k: v for k, v in result.items() if k != "speed_curve"}, indent=2))
        print(f"Q13_RAGGED_EASE_DRY_OK|L={result['landing_frame_L']}|H={result['hold_frame_H']}|gates={result['offline_gate_verdict']}")
        return
    if args.confirm != APPLY_CONFIRM:
        raise SystemExit(f"APPLY requires --confirm {APPLY_CONFIRM}")
    if result["offline_gate_verdict"] != "PASS":
        raise SystemExit("REFUSED: offline gates did not pass")
    if not args.blender.is_file():
        raise SystemExit(f"Blender not found: {args.blender}")
    outputs = output_paths(output_root)
    # Q13b deliberately restores first-run offline intermediates. Only final products
    # from the failed Blender stage must be absent before this one-shot continuation.
    collisions = [str(outputs[k]) for k in ("abc", "preview", "blender_report") if outputs[k].exists()]
    if collisions:
        raise SystemExit("REFUSED: Q13b final output(s) already exist: " + ", ".join(collisions))
    result["continuation"] = validate_staged_continuation(result, outputs)
    run_id = time.strftime("Q13B-%Y%m%d-%H%M%S")
    result["run_id"] = run_id
    result["preapply_backup"] = str(make_preapply_backup(output_root, outputs, run_id))
    result["mode"] = "APPLY"
    result["inputs_sha256"] = {k: sha256(v) for k, v in inputs.items()}
    result["outputs"] = {k: str(v) for k, v in outputs.items() if k != "base"}
    result["preview"] = write_offline_preview(outputs, 450, 1080, FPS,
                                                result["landing_frame_L"], result["hold_frame_H"])
    outputs["record"].write_text(json.dumps(result, indent=2), encoding="utf-8")
    blender_export(args.blender, inputs, outputs, result)
    result["blender"] = load_json(outputs["blender_report"])
    result["outputs_sha256"] = {k: sha256(v) for k, v in outputs.items()
                                if k not in {"base", "record", "blender_script"} and v.is_file()}
    result["success_marker"] = f"Q13_RAGGED_EASE_APPLIED|L={result['landing_frame_L']}|H={result['hold_frame_H']}"
    outputs["record"].write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result["success_marker"])


if __name__ == "__main__":
    main()
