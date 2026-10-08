#!/usr/bin/env python3
"""Recover a curtain Alembic and bake report from a complete streamed solve.

DRY and REVERT run in ordinary Python. APPLY must run in Blender 4.4 so it can
export and read back Alembic. No simulation is performed: a PC2 mesh cache
carries the already-solved vertex positions into Blender's Alembic exporter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
from pathlib import Path

import numpy as np


FPS = 30
SEAM_WIDTH_M = 1.37
APPLY_CONFIRM = "APPLY_STREAM_TO_ABC"
REVERT_CONFIRM = "REVERT_STREAM_TO_ABC"
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class RecoveryError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_sidecar(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"cannot read stream sidecar {path}: {exc}") from exc
    required = {"vertices", "first_frame", "dtype", "layout", "faces"}
    missing = sorted(required - set(value))
    if missing:
        raise RecoveryError(f"stream sidecar missing keys: {missing}")
    if value["dtype"] != "float32" or value["layout"] != "frame-major xyz":
        raise RecoveryError(
            f"unsupported stream encoding: dtype={value['dtype']!r}, layout={value['layout']!r}"
        )
    if int(value["first_frame"]) != 1:
        raise RecoveryError(f"first_frame must be 1, got {value['first_frame']!r}")
    if int(value["vertices"]) <= 0 or not isinstance(value["faces"], list):
        raise RecoveryError("sidecar vertices/faces are invalid")
    return value


def grid_shape(track_m: float, drop_m: float, fullness: float, quads_per_bolt: int) -> tuple[int, int, float, float]:
    quad_x = SEAM_WIDTH_M / quads_per_bolt
    cols = round(track_m * fullness / quad_x)
    pattern_width = cols * quad_x
    rows = round(drop_m / quad_x)
    return cols, rows, pattern_width, quad_x


def expected_faces(cols: int, rows: int) -> list[list[int]]:
    stride = cols + 1
    return [
        [r * stride + c, (r + 1) * stride + c, (r + 1) * stride + c + 1, r * stride + c + 1]
        for r in range(rows)
        for c in range(cols)
    ]


def validate_topology(sidecar: dict, *, track_m: float, drop_m: float, fullness: float, quads_per_bolt: int) -> dict:
    cols, rows, pattern_width, quad_x = grid_shape(track_m, drop_m, fullness, quads_per_bolt)
    want_vertices = (cols + 1) * (rows + 1)
    vertices = int(sidecar["vertices"])
    if vertices != want_vertices:
        raise RecoveryError(
            f"vertex count {vertices} does not match plain source grid {want_vertices} ({cols + 1}x{rows + 1})"
        )
    faces = sidecar["faces"]
    want_faces = expected_faces(cols, rows)
    if faces != want_faces:
        mismatch = next((i for i, pair in enumerate(zip(faces, want_faces)) if pair[0] != pair[1]), None)
        if mismatch is None and len(faces) != len(want_faces):
            mismatch = min(len(faces), len(want_faces))
        raise RecoveryError(f"sidecar topology does not match deterministic plain grid at face {mismatch}")
    return {
        "cols": cols,
        "rows": rows,
        "pattern_width_m": pattern_width,
        "quad_x_m": quad_x,
        "vertices": vertices,
        "faces": len(faces),
    }


def open_stream(path: Path, frames: int, vertices: int) -> np.memmap:
    expected = frames * vertices * 3 * np.dtype("<f4").itemsize
    actual = path.stat().st_size
    if actual != expected:
        raise RecoveryError(f"stream byte size {actual} != expected {expected} ({frames} frames x {vertices} vertices)")
    return np.memmap(path, dtype="<f4", mode="r", shape=(frames, vertices, 3))


def validate_stream(stream: np.memmap) -> dict:
    zero_frames: list[int] = []
    unchanged_frames: list[int] = []
    previous = None
    xyz_min = np.full(3, np.inf)
    xyz_max = np.full(3, -np.inf)
    for index in range(stream.shape[0]):
        frame = np.asarray(stream[index])
        if not np.isfinite(frame).all():
            raise RecoveryError(f"stream frame {index + 1} contains NaN or infinity")
        if not np.any(frame):
            zero_frames.append(index + 1)
        if previous is not None and np.array_equal(frame, previous):
            unchanged_frames.append(index + 1)
        xyz_min = np.minimum(xyz_min, frame.min(axis=0))
        xyz_max = np.maximum(xyz_max, frame.max(axis=0))
        previous = np.array(frame, copy=True)
    if zero_frames:
        raise RecoveryError(f"all-zero stream frames: {zero_frames[:10]}")
    if unchanged_frames:
        raise RecoveryError(f"unchanged consecutive stream frames: {unchanged_frames[:10]}")
    return {
        "frames_nonzero": int(stream.shape[0]),
        "frames_changing": int(stream.shape[0]),
        "world_aabb_m": {"min": xyz_min.tolist(), "max": xyz_max.tolist()},
    }


def pct(values: np.ndarray, fraction: float) -> float:
    index = min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))
    return float(np.partition(values, index)[index])


def frame_metrics(co: np.ndarray, top: np.ndarray, quad_x: float, pattern_width: float, drop_m: float) -> dict:
    low = co[co[:, 2] < 0.5]
    cell = 1.25 * quad_x
    below = co[co[:, 2] < 1.5]
    cells = {(math.floor(float(p[0]) / cell), math.floor(float(p[1]) / cell)) for p in below}
    out = {
        "height_m": round(pct(co[:, 2], 0.95), 3),
        "max_z_m": round(float(co[:, 2].max()), 3),
        "heading_mean_z_m": round(float(co[top, 2].mean()), 3),
        "low_fraction": round(len(low) / len(co), 3),
        "mean_z_m": round(float(co[:, 2].mean()), 3),
        "aabb_m": {
            "x": [round(float(co[:, 0].min()), 3), round(float(co[:, 0].max()), 3)],
            "y": [round(float(co[:, 1].min()), 3), round(float(co[:, 1].max()), 3)],
            "z": [round(float(co[:, 2].min()), 3), round(float(co[:, 2].max()), 3)],
        },
    }
    if cells:
        footprint = len(cells) * cell * cell
        out["footprint_m2"] = round(footprint, 2)
        out["layers"] = round(pattern_width * drop_m / footprint, 2)
    if len(low):
        out.update(
            {
                "depth_m": round(pct(low[:, 1], 0.95) - pct(low[:, 1], 0.05), 3),
                "width_m": round(pct(low[:, 0], 0.95) - pct(low[:, 0], 0.05), 3),
                "depth_centre_y_m": round(pct(low[:, 1], 0.5), 3),
            }
        )
    return out


def row_folds(row: np.ndarray) -> dict:
    values = row[:, 1]
    t = np.linspace(-1.0, 1.0, len(values))
    delta = values - np.polyval(np.polyfit(t, values, 3), t)
    lobes: list[float] = []
    state, peak = 0, 0.0
    for value in delta:
        sign = 1 if value > 0.03 else (-1 if value < -0.03 else 0)
        if sign and sign != state:
            if state:
                lobes.append(peak)
            state, peak = sign, 0.0
        peak = max(peak, abs(float(value)))
    if state:
        lobes.append(peak)
    return {
        "folds": round(len(lobes) / 2.0, 1),
        "mean_depth_m": round(2.0 * float(np.mean(lobes)), 3) if lobes else 0.0,
        "width_m": round(float(row[:, 0].max() - row[:, 0].min()), 3),
    }


def hang_profile(co: np.ndarray, rows: int, cols: int, opening_track_m: float = 17.77) -> dict:
    if len(co) != (rows + 1) * (cols + 1):
        return {"skipped": f"{len(co)} vertices is not a plain {rows + 1} x {cols + 1} grid"}
    array = np.asarray(co).reshape(rows + 1, cols + 1, 3)
    head, hem = array[0], array[-1]
    spread = [round(float(head[:, 0].min() - hem[:, 0].min()), 3), round(float(hem[:, 0].max() - head[:, 0].max()), 3)]
    out = {
        "flare_ratio": round(float(np.ptp(hem[:, 0]) / np.ptp(head[:, 0])), 3),
        "edge_spread_m": spread,
        "flare_at_opening_width": round((opening_track_m + max(0.0, spread[0]) + max(0.0, spread[1])) / opening_track_m, 3),
        "rows": {},
    }
    for label, fraction in (("heading", 0.0), ("75%", 0.25), ("50%", 0.5), ("25%", 0.75), ("hem", 1.0)):
        out["rows"][label] = row_folds(array[round(fraction * rows)])
    heading = out["rows"]["heading"]
    passed = out["flare_at_opening_width"] <= 1.15
    for label in ("75%", "50%", "25%"):
        row = out["rows"][label]
        row["count_kept"] = round(row["folds"] / heading["folds"], 2) if heading["folds"] else None
        row["depth_kept"] = round(row["mean_depth_m"] / heading["mean_depth_m"], 2) if heading["mean_depth_m"] else None
        passed = passed and (row["count_kept"] or 0) >= 0.75 and (row["depth_kept"] or 0) >= 0.5
    out["targets"] = {"flare_max": 1.15, "fold_count_kept_min": 0.75, "fold_depth_kept_min": 0.5}
    out["pass"] = bool(passed)
    return out


def max_move_mm(a: np.ndarray, b: np.ndarray) -> float:
    return round(1000.0 * float(np.linalg.norm(a - b, axis=1).max()), 2)


def reconstruct_report(args: argparse.Namespace, sidecar: dict, topology: dict, stream: np.memmap, validation: dict) -> dict:
    frames, release, show = args.frames, args.release_frame, args.show_start
    cols, rows = topology["cols"], topology["rows"]
    top = np.arange(cols + 1)
    hem = np.arange(rows * (cols + 1), (rows + 1) * (cols + 1))
    checkpoint_frames = sorted({release - 1, release + 5, release + 15, release + 30, frames - 30, frames})
    checkpoints = {
        str(frame): frame_metrics(
            np.asarray(stream[frame - 1]), top, topology["quad_x_m"], topology["pattern_width_m"], args.drop_m
        )
        for frame in checkpoint_frames
    }
    start = np.asarray(stream[0])
    hang_depth = round(pct(start[:, 1], 0.95) - pct(start[:, 1], 0.05), 3)
    final = checkpoints[str(frames)]
    if "depth_m" in final:
        final["depth_ratio"] = round(final["depth_m"] / max(hang_depth, 1e-6), 2)

    still_mm = []
    previous = None
    for frame in range(show - args.settle_probe, release):
        current = np.asarray(stream[frame - 1])
        if previous is not None:
            still_mm.append([frame, max_move_mm(current, previous)])
        previous = np.array(current, copy=True)
    visible_still = [move for frame, move in still_mm if frame >= show]

    extents = []
    for frame in range(show + 1, frames + 1):
        co = np.asarray(stream[frame - 1])
        portal = co[np.abs(co[:, 1]) <= 0.2]
        extents.append(
            [
                frame,
                round(float(co[:, 1].min()), 3),
                round(float(co[:, 1].max()), 3),
                round(float(np.abs(portal[:, 0]).max()), 3) if len(portal) else 0.0,
                round(float(portal[:, 2].max()), 3) if len(portal) else 0.0,
                round(float(co[:, 0].min()), 3),
                round(float(co[:, 0].max()), 3),
            ]
        )

    def worst(column: int, want_min: bool) -> dict:
        row = (min if want_min else max)(extents, key=lambda item: item[column])
        return {"value_m": row[column], "frame": row[0], "phase": "hang" if row[0] < release else "fall"}

    rig_limits = {
        "downstage_min_y": worst(1, True),
        "upstage_max_y": worst(2, False),
        "portal_abs_x_max": worst(3, False),
        "portal_z_max": worst(4, False),
        "unreal_cm": {
            "X_min": round(100 * min(row[1] for row in extents)),
            "X_max": round(100 * max(row[2] for row in extents)),
            "portal_absY_max": round(100 * max(row[3] for row in extents)),
            "portal_Z_max": round(100 * max(row[4] for row in extents)),
            "Y_min": round(100 * min(row[5] for row in extents)),
            "Y_max": round(100 * max(row[6] for row in extents)),
        },
    }

    hem_mean_z, heading_drift, moves = [], [], []
    previous = None
    top_z = args.drop_m + args.lift_m
    for frame in range(release - 1, frames + 1):
        co = np.asarray(stream[frame - 1])
        hem_mean_z.append([frame, round(float(co[hem, 2].mean()), 4)])
        drift = float(np.abs(co[top, 2] - top_z).max())
        heading_drift.append([frame, round(drift, 5)])
        if previous is not None:
            moves.append([frame, max_move_mm(co, previous)])
        previous = np.array(co, copy=True)
    post_release_moves = [row for row in moves if row[0] > release]
    end_co = np.asarray(stream[-1])
    hold_co = np.asarray(stream[release - 2])
    end = {
        "hem_min_z_m": round(float(end_co[hem, 2].min()), 3),
        "hem_mean_z_m": round(float(end_co[hem, 2].mean()), 4),
        "heading_mean_z_m": round(float(end_co[top, 2].mean()), 3),
    }
    end["stretch"] = round((end["heading_mean_z_m"] - end["hem_mean_z_m"]) / args.drop_m, 3)
    last_moves = [move for _, move in post_release_moves[-30:]]
    last_bad_release = max((frame for frame, move in post_release_moves if move >= 2.0), default=None)

    brail_rows = {}
    for key in range(1, args.brail_rows + 1):
        grid_row = round(key * rows / args.brail_rows)
        from_z = args.drop_m * (1.0 - grid_row / rows)
        to_z = args.drop_m - args.brail_top_gap_m - (key - 1) * args.brail_stack_m
        brail_rows[str(key)] = {
            "grid_row": grid_row,
            "from_z_m": round(from_z, 3),
            "to_z_m": round(to_z, 3),
            "vertices": cols + 1,
        }

    profile = hang_profile(end_co, rows, cols)
    unfurl = {
        "brail_rows": args.brail_rows,
        "brail_weight": args.brail_weight,
        "brail_from": args.brail_from,
        "brail_frames": args.brail_frames,
        "brail_top_gap_m": args.brail_top_gap_m,
        "brail_stack_m": args.brail_stack_m,
        "rows": brail_rows,
        "lower_frames": args.unfurl_lower_frames,
        "residual_stiffness": args.unfurl_residual_stiffness,
        "free_after": args.unfurl_free_after,
        "free_frames": args.unfurl_free_frames,
        "free_to": args.unfurl_free_to,
        "stagger": args.unfurl_stagger,
        "stagger_mode": args.unfurl_stagger_mode,
        "roll_ease": args.unfurl_roll_ease,
        "mid_row": 0,
        "centre_side": 1.0,
        "centre_only": 1.0,
        "two_stage_row": 0,
        "stage_pause": 0,
        "bounce_m": args.unfurl_bounce_m,
        "bounce_frames": args.unfurl_bounce_frames,
        "tension_damping": 5.0,
        "goal_friction": None,
        "bend_damping_after": "",
        "heading_vertices": len(top),
        "hem_vertices": len(hem),
        "heading_pin_weight": 1.0,
        "hem_mean_z": hem_mean_z,
        "heading_drift_m": heading_drift,
        "heading_drift_max_m": round(max(row[1] for row in heading_drift if row[0] >= release), 4),
        "bunch_at_hold": {
            "depth_below_heading_m": round(top_z - float(hold_co[:, 2].min()), 3),
            "hem_mean_z_m": hem_mean_z[0][1],
            "heading_drift_m": heading_drift[0][1],
        },
        "end": end,
        "end_still_max_mm": max(last_moves) if last_moves else None,
        "settle_to_2mm_after_release_s": round((last_bad_release + 1 - release) / FPS, 1) if last_bad_release else 0.0,
        "settle_to_2mm_reached": last_bad_release is None or last_bad_release < frames,
        "post_release_moves_mm": post_release_moves,
    }

    report = {
        "id": args.bake_id,
        "rest": "unfurl",
        "rest_switch_amount": None,
        "hem_guide_weight": 0.0,
        "hem_guide_rows": 1,
        "hem_guided_vertices": None,
        "fold_wavelength_m": args.fold_wavelength_m,
        "track_m": args.track_m,
        "drop_m": args.drop_m,
        "collider_origin_cm": None,
        "release_method": "stiffness",
        "colliders": args.colliders,
        "colliders_built": {"boxes": 19, "housings": 16},
        "posts_from": 0,
        "show_start": show,
        "bend_damping_ramp": "",
        "throw_m": 0.0,
        "throw_frames": 10,
        "render_style": "matte",
        "mass_per_vertex": 1.0,
        "pin_stiffness": 50.0,
        "fullness": args.fullness,
        "quad_m": round(topology["quad_x_m"], 3),
        "vertices": topology["vertices"],
        "vertex_mass": None,
        "bend": 5.0,
        "tension": 40.0,
        "compression": 0.1,
        "lift_m": args.lift_m,
        "self_dist_m": 0.03,
        "floor_friction": 10.0,
        "self_friction": 10.0,
        "air_damping": 1.0,
        "air_damping_applied": 1.0,
        "release_frame": release,
        "frames": frames,
        "fps": FPS,
        "quality": 20,
        "frame_seconds": [],
        "checkpoints": checkpoints,
        "colliders_sha256": args.colliders_sha256,
        "unfurl": unfurl,
        "self_dist_applied_m": 0.03,
        "self_dist_edge_ratio": round(0.03 / topology["quad_x_m"], 3),
        "collision_quality_applied": 8,
        "bending_damping_applied": 0.5,
        "self_impulse_clamp_applied": 0.0,
        "impulse_clamp_applied": 0.0,
        "hang_depth_m": hang_depth,
        "still_mm": still_mm,
        "extents": extents,
        "com_z": [round(float(np.asarray(stream[frame - 1])[:, 2].mean()), 4) for frame in range(release - 1, frames + 1)],
        "top_z": [round(float(np.asarray(stream[frame - 1])[:, 2].max()), 4) for frame in range(release - 1, frames + 1)],
        "hang_profile": profile,
        "rig_limits": rig_limits,
        "released": dict(hem_mean_z).get(release + 45, math.inf) < args.lift_m + 0.5 * args.drop_m,
        "settled": abs(checkpoints[str(frames - 30)].get("height_m", 0) - final.get("height_m", 0)) < 0.05
        and abs(checkpoints[str(frames - 30)].get("depth_m", 0) - final.get("depth_m", 0)) < 0.1,
        "solve_seconds_total": None,
        "still_window_max_mm": max(visible_still) if visible_still else None,
        "still_window_mean_mm": round(sum(visible_still) / len(visible_still), 2) if visible_still else None,
        "reconstructed_from_stream": {
            "value": True,
            "run_id": args.run_id,
            "stream_path": str(args.stream),
            "stream_sha256": sha256_file(args.stream),
            "sidecar_path": str(args.sidecar),
            "sidecar_sha256": sha256_file(args.sidecar),
            "method": "PC2 Mesh Cache -> Blender VIEWPORT Alembic export",
            "validation": validation,
            "unavailable_original_fields": ["frame_seconds", "solve_seconds_total", "final.fold_size_m"],
        },
    }
    last_bad_still = max((frame for frame, move in still_mm if move >= 2.0), default=None)
    report["settle_to_2mm_s"] = (
        round((last_bad_still + 1 - 41) / FPS, 1) if last_bad_still is not None else round((still_mm[0][0] - 41) / FPS, 1)
    )
    report["settle_to_2mm_reached"] = last_bad_still is None or last_bad_still < still_mm[-1][0]
    report["unfurl_gates"] = unfurl_gates(report, args)
    return report


def unfurl_gates(report: dict, args: argparse.Namespace) -> dict:
    unfurl = report["unfurl"]
    bunch = unfurl["bunch_at_hold"]
    end = unfurl["end"]
    hem_at = dict(unfurl["hem_mean_z"]).get(args.release_frame + 60)
    gates = {
        "U1_bunched": {
            "value_m": bunch["depth_below_heading_m"],
            "limit_m": round(max(0.6, 0.2 * args.drop_m), 3),
            "pass": bunch["depth_below_heading_m"] <= max(0.6, 0.2 * args.drop_m),
            "what": "lowest cloth below the heading at the held frame R-1",
        },
        "U2_still_before_release": {
            "value_mm": report["still_window_max_mm"],
            "limit_mm": 1.5,
            "pass": report["still_window_max_mm"] is not None and report["still_window_max_mm"] < 1.5,
        },
        "U3_heading_held": {
            "value_m": unfurl["heading_drift_max_m"],
            "limit_m": 0.01,
            "pass": unfurl["heading_drift_max_m"] <= 0.01,
            "what": "largest move of any heading vertex from its pinned height, release to end",
        },
        "U4_unrolled_in_time": {
            "value_m": hem_at,
            "limit_m": round(args.lift_m + 0.25 * args.drop_m, 3),
            "frames_after_release": 60,
            "pass": hem_at is not None and hem_at <= args.lift_m + 0.25 * args.drop_m,
            "what": "hem mean z",
        },
        "U5_hang_profile": {"pass": bool(report["hang_profile"].get("pass")), "what": "hang_profile at the LAST frame (flare, folds kept)"},
        "U6_hem_clear_and_stretch": {
            "hem_min_z_m": end["hem_min_z_m"],
            "stretch": end["stretch"],
            "limits": {"hem_min_z_m": 0.02, "stretch_max": 1.03},
            "pass": end["hem_min_z_m"] >= 0.02 and end["stretch"] <= 1.03,
        },
        "U7_settled_at_end": {
            "value_mm": unfurl["end_still_max_mm"],
            "limit_mm": 2.0,
            "pass": unfurl["end_still_max_mm"] is not None and unfurl["end_still_max_mm"] < 2.0,
        },
    }
    gates["pass"] = all(value["pass"] for value in gates.values())
    gates["top_z_m"] = round(args.drop_m + args.lift_m, 3)
    return gates


def write_pc2(path: Path, stream: np.memmap | np.ndarray, first_frame: int, object_location: tuple[float, float, float]) -> None:
    frames, vertices, axes = stream.shape
    if axes != 3:
        raise RecoveryError(f"stream has {axes} axes, expected 3")
    with path.open("wb") as handle:
        handle.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, vertices, float(first_frame), 1.0, frames))
        offset = np.asarray(object_location, dtype=np.float32)
        for index in range(frames):
            local = np.asarray(stream[index], dtype=np.float32) - offset
            handle.write(np.asarray(local, dtype="<f4").tobytes(order="C"))


def read_pc2_frame(path: Path, frame_index: int) -> np.ndarray:
    with path.open("rb") as handle:
        raw = handle.read(struct.calcsize("<12siiffi"))
        signature, version, vertices, _start, _sample, frames = struct.unpack("<12siiffi", raw)
        if signature != b"POINTCACHE2\0" or version != 1 or not 0 <= frame_index < frames:
            raise RecoveryError("invalid PC2 header or frame index")
        handle.seek(struct.calcsize("<12siiffi") + frame_index * vertices * 3 * 4)
        return np.frombuffer(handle.read(vertices * 3 * 4), dtype="<f4").reshape(vertices, 3).copy()


def uv_per_loop(faces: list[list[int]], cols: int, rows: int) -> np.ndarray:
    stride = cols + 1
    values = []
    for face in faces:
        for vertex in face:
            row, col = divmod(vertex, stride)
            values.append((col / cols, 1.0 - row / rows))
    return np.asarray(values, dtype=np.float32)


def blender_export_and_readback(
    args: argparse.Namespace, sidecar: dict, topology: dict, stream: np.memmap, pc2_path: Path, abc_path: Path
) -> dict:
    try:
        import bpy  # type: ignore
    except ImportError as exc:
        raise RecoveryError("APPLY must run under Blender 4.4") from exc
    if tuple(bpy.app.version[:2]) != (4, 4):
        raise RecoveryError(f"Blender 4.4 required, got {bpy.app.version_string}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, args.frames
    first_world = np.asarray(stream[0])
    first_local = first_world - np.asarray((0.0, 0.0, args.lift_m), dtype=np.float32)
    mesh = bpy.data.meshes.new(f"Curtain_{args.bake_id}")
    mesh.from_pydata(first_local.tolist(), [], sidecar["faces"])
    mesh.update(calc_edges=True)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_layer.data.foreach_set("uv", uv_per_loop(sidecar["faces"], topology["cols"], topology["rows"]).ravel())
    obj = bpy.data.objects.new(f"Curtain_{args.bake_id}", mesh)
    scene.collection.objects.link(obj)
    obj.location = (0.0, 0.0, args.lift_m)
    material = bpy.data.materials.new(f"M_Curtain_{args.bake_id}")
    material.diffuse_color = (0.45, 0.02, 0.04, 1.0)
    mesh.materials.append(material)

    cache = obj.modifiers.new("RecoveredStream", "MESH_CACHE")
    cache.cache_format = "PC2"
    cache.filepath = str(pc2_path)
    cache.factor = 1.0
    cache.deform_mode = "OVERWRITE"
    cache.interpolation = "NONE"
    cache.play_mode = "CUSTOM"
    cache.time_mode = "FRAME"
    cache.forward_axis = "POS_Y"
    cache.up_axis = "POS_Z"
    cache.eval_frame = 0.0
    cache.keyframe_insert(data_path="eval_frame", frame=1)
    cache.eval_frame = float(args.frames - 1)
    cache.keyframe_insert(data_path="eval_frame", frame=args.frames)
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        for fcurve in action.fcurves:
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    result = bpy.ops.wm.alembic_export(
        filepath=str(abc_path),
        start=args.abc_start,
        end=args.frames,
        selected=True,
        uvs=True,
        normals=True,
        face_sets=True,
        apply_subdiv=False,
        evaluation_mode="VIEWPORT",
    )
    if "FINISHED" not in result or not abc_path.is_file() or abc_path.stat().st_size == 0:
        raise RecoveryError(f"Alembic export failed: result={result}, path={abc_path}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.wm.alembic_import(
        filepath=str(abc_path), set_frame_range=True, validate_meshes=True, always_add_cache_reader=True, as_background_job=False
    )
    if "FINISHED" not in imported:
        raise RecoveryError(f"Alembic read-back import failed: {imported}")
    meshes = [candidate for candidate in bpy.context.scene.objects if candidate.type == "MESH"]
    if len(meshes) != 1:
        raise RecoveryError(f"Alembic read-back expected one mesh, found {[candidate.name for candidate in meshes]}")
    recovered = meshes[0]
    checks = []
    for frame in sorted({args.abc_start, args.release_frame - 1, args.frames}):
        bpy.context.scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = recovered.evaluated_get(depsgraph)
        coords = np.empty(len(evaluated.data.vertices) * 3, dtype=np.float32)
        evaluated.data.vertices.foreach_get("co", coords)
        coords = coords.reshape(-1, 3)
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float32)
        world = coords @ matrix[:3, :3].T + matrix[:3, 3]
        expected = np.asarray(stream[frame - 1])
        if world.shape != expected.shape:
            raise RecoveryError(f"Alembic frame {frame} vertex shape {world.shape} != {expected.shape}")
        error = float(np.abs(world - expected).max())
        if error > args.readback_tolerance:
            raise RecoveryError(f"Alembic frame {frame} max error {error} > {args.readback_tolerance}")
        checks.append({"frame": frame, "vertices": len(world), "max_abs_error_m": error})
    if not recovered.data.uv_layers or len(recovered.data.uv_layers.active.data) != len(sidecar["faces"]) * 4:
        raise RecoveryError("Alembic read-back UV layer is absent or has the wrong loop count")
    return {
        "object_name": recovered.name,
        "mesh_objects": 1,
        "fps": FPS,
        "frames": [args.abc_start, args.frames],
        "uv_layer": recovered.data.uv_layers.active.name,
        "uv_loops": len(recovered.data.uv_layers.active.data),
        "checks": checks,
        "tolerance_m": args.readback_tolerance,
    }


def output_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {"abc": args.out_dir / f"{args.bake_id}.abc", "json": args.out_dir / f"{args.bake_id}.json"}


def preflight(args: argparse.Namespace) -> tuple[dict, dict, np.memmap, dict, dict]:
    if not RUN_RE.fullmatch(args.run_id):
        raise RecoveryError("run id must use only letters, digits, dot, underscore, and hyphen")
    if not args.stream.is_file() or not args.sidecar.is_file():
        raise RecoveryError(f"missing stream or sidecar: {args.stream}, {args.sidecar}")
    if not (1 <= args.show_start < args.release_frame <= args.frames and args.show_start <= args.abc_start <= args.frames):
        raise RecoveryError("require 1 <= show_start < release_frame <= frames and show_start <= abc_start <= frames")
    sidecar = load_sidecar(args.sidecar)
    topology = validate_topology(
        sidecar,
        track_m=args.track_m,
        drop_m=args.drop_m,
        fullness=args.fullness,
        quads_per_bolt=args.quads_per_bolt,
    )
    stream = open_stream(args.stream, args.frames, topology["vertices"])
    validation = validate_stream(stream)
    report = reconstruct_report(args, sidecar, topology, stream, validation)
    return sidecar, topology, stream, validation, report


def apply(args: argparse.Namespace) -> None:
    expected_confirm = f"{APPLY_CONFIRM}:{args.bake_id}"
    if args.confirm != expected_confirm:
        raise RecoveryError(f"APPLY requires --confirm {expected_confirm}")
    sidecar, topology, stream, validation, report = preflight(args)
    paths = output_paths(args)
    backup = args.project_root / "Backups" / f"PreCurtainStreamToAbc-{args.run_id}"
    if backup.exists():
        raise RecoveryError(f"backup already exists: {backup}")
    backup.mkdir(parents=True)
    originals = backup / "original"
    originals.mkdir()
    preexisting = {}
    for label, path in paths.items():
        preexisting[label] = {"path": str(path), "existed": path.exists(), "sha256": sha256_file(path) if path.exists() else None}
        if path.exists():
            shutil.copy2(path, originals / path.name)
    record = {
        "run_id": args.run_id,
        "mode": "APPLY",
        "bake_id": args.bake_id,
        "preexisting": preexisting,
        "targets": {label: str(path) for label, path in paths.items()},
        "dirty_package_census": {
            "scope": "offline filesystem conversion; Unreal was not opened",
            "named_packages": [],
            "dirty_content": [],
            "dirty_maps": [],
            "status": "not-applicable: zero Unreal packages read or written",
        },
        "source": report["reconstructed_from_stream"],
        "status": "backed_up_before_output_change",
    }
    record_path = backup / "record.json"
    write_json_atomic(record_path, record)

    pc2 = backup / f"{args.bake_id}_world_to_local.pc2"
    staged_abc = backup / f"{args.bake_id}.abc"
    write_pc2(pc2, stream, 1, (0.0, 0.0, args.lift_m))
    sample_checks = []
    for frame in sorted({args.abc_start, args.release_frame - 1, args.frames}):
        local = read_pc2_frame(pc2, frame - 1)
        world = local + np.asarray((0.0, 0.0, args.lift_m), dtype=np.float32)
        error = float(np.abs(world - np.asarray(stream[frame - 1])).max())
        if error > args.readback_tolerance:
            raise RecoveryError(f"PC2 frame {frame} max error {error} > {args.readback_tolerance}")
        sample_checks.append({"frame": frame, "max_abs_error_m": error})
    report["reconstructed_from_stream"]["pc2_readback"] = sample_checks
    abc_readback = blender_export_and_readback(args, sidecar, topology, stream, pc2, staged_abc)
    report["reconstructed_from_stream"]["alembic_readback"] = abc_readback
    report["reconstructed_from_stream"]["object"] = {
        "name": f"Curtain_{args.bake_id}",
        "mesh": f"Curtain_{args.bake_id}",
        "location_m": [0.0, 0.0, args.lift_m],
        "rotation_rad": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
        "uv": "UVMap from the normalized flat pattern",
    }
    report["reconstructed_from_stream"]["abc_sha256"] = sha256_file(staged_abc)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    staged_json = backup / f"{args.bake_id}.json"
    write_json_atomic(staged_json, report)
    for label, staged in (("abc", staged_abc), ("json", staged_json)):
        tmp = paths[label].with_name(paths[label].name + f".{args.run_id}.tmp")
        shutil.copy2(staged, tmp)
        if sha256_file(tmp) != sha256_file(staged):
            raise RecoveryError(f"copy read-back hash mismatch for {label}")
        os.replace(tmp, paths[label])
    published = {label: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for label, path in paths.items()}
    record.update({"status": "applied_and_read_back", "published": published, "alembic_readback": abc_readback})
    write_json_atomic(record_path, record)
    print(
        f"CURTAIN_STREAM_TO_ABC_SUCCESS|run={args.run_id}|id={args.bake_id}|frames={args.abc_start}-{args.frames}|"
        f"vertices={topology['vertices']}|abc_sha256={published['abc']['sha256']}"
    )


def revert(args: argparse.Namespace) -> None:
    expected_confirm = f"{REVERT_CONFIRM}:{args.bake_id}"
    if args.confirm != expected_confirm:
        raise RecoveryError(f"REVERT requires --confirm {expected_confirm}")
    backup = args.project_root / "Backups" / f"PreCurtainStreamToAbc-{args.run_id}"
    record_path = backup / "record.json"
    if not record_path.is_file():
        raise RecoveryError(f"missing apply record: {record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("bake_id") != args.bake_id or record.get("run_id") != args.run_id:
        raise RecoveryError("record bake id/run id does not match requested revert")
    if record.get("status") != "applied_and_read_back":
        raise RecoveryError(f"record is not an applied run: status={record.get('status')}")
    paths = output_paths(args)
    for label, path in paths.items():
        published = record["published"][label]
        if not path.is_file() or sha256_file(path) != published["sha256"]:
            raise RecoveryError(f"refusing to revert changed or missing output: {path}")
    reverted = backup / "reverted_generated"
    reverted.mkdir(exist_ok=False)
    actions = {}
    for label, path in paths.items():
        shutil.move(str(path), str(reverted / path.name))
        before = record["preexisting"][label]
        if before["existed"]:
            original = backup / "original" / path.name
            shutil.copy2(original, path)
            if sha256_file(path) != before["sha256"]:
                raise RecoveryError(f"restored {label} hash mismatch")
            actions[label] = "restored preexisting file"
        else:
            actions[label] = f"moved generated file to recoverable {reverted}"
    record.update({"status": "reverted", "revert_actions": actions})
    write_json_atomic(record_path, record)
    print(f"CURTAIN_STREAM_TO_ABC_REVERT_SUCCESS|run={args.run_id}|id={args.bake_id}|recoverable={reverted}")


def dry(args: argparse.Namespace) -> None:
    _sidecar, topology, _stream, validation, report = preflight(args)
    paths = output_paths(args)
    summary = {
        "run_id": args.run_id,
        "id": args.bake_id,
        "source": {"stream": str(args.stream), "sidecar": str(args.sidecar)},
        "outputs": {label: str(path) for label, path in paths.items()},
        "topology": topology,
        "validation": validation,
        "export": {"object": f"Curtain_{args.bake_id}", "fps": FPS, "frames": [args.abc_start, args.frames], "scale": 1.0},
        "report_facts": {
            "show_start": report["show_start"],
            "release_frame": report["release_frame"],
            "checkpoints": sorted(report["checkpoints"], key=int),
            "unfurl_gates_pass": report["unfurl_gates"]["pass"],
        },
        "writes": [],
    }
    print(json.dumps(summary, indent=1))
    print(f"CURTAIN_STREAM_TO_ABC_DRY_OK|run={args.run_id}|id={args.bake_id}|writes=0")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    result.add_argument("--confirm", default="")
    result.add_argument("--run-id", required=True)
    result.add_argument("--id", dest="bake_id", default="unfurl_sleight_b1hop10_p02")
    result.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    result.add_argument("--stream", type=Path, required=True)
    result.add_argument("--sidecar", type=Path, required=True)
    result.add_argument("--out-dir", type=Path, required=True)
    result.add_argument("--frames", type=int, default=390)
    result.add_argument("--abc-start", type=int, default=210)
    result.add_argument("--show-start", type=int, default=210)
    result.add_argument("--release-frame", type=int, default=240)
    result.add_argument("--settle-probe", type=int, default=60)
    result.add_argument("--track-m", type=float, default=18.8)
    result.add_argument("--drop-m", type=float, default=10.0)
    result.add_argument("--fullness", type=float, default=2.0)
    result.add_argument("--quads-per-bolt", type=int, default=15)
    result.add_argument("--fold-wavelength-m", type=float, default=0.85)
    result.add_argument("--lift-m", type=float, default=0.2)
    result.add_argument("--brail-rows", type=int, default=8)
    result.add_argument("--brail-weight", type=float, default=0.99)
    result.add_argument("--brail-from", type=int, default=2)
    result.add_argument("--brail-frames", type=int, default=120)
    result.add_argument("--brail-top-gap-m", type=float, default=0.10)
    result.add_argument("--brail-stack-m", type=float, default=0.06)
    result.add_argument("--unfurl-lower-frames", type=int, default=45)
    result.add_argument("--unfurl-residual-stiffness", type=float, default=50.0)
    result.add_argument("--unfurl-free-after", type=int, default=55)
    result.add_argument("--unfurl-free-frames", type=int, default=30)
    result.add_argument("--unfurl-free-to", type=float, default=3.0)
    result.add_argument("--unfurl-stagger", type=int, default=1)
    result.add_argument("--unfurl-stagger-mode", default="mass")
    result.add_argument("--unfurl-roll-ease", default="smooth")
    result.add_argument("--unfurl-bounce-m", type=float, default=0.10)
    result.add_argument("--unfurl-bounce-frames", type=int, default=10)
    result.add_argument("--colliders", default="Docs/StageFrontColliders_2026-09-28.json|v2")
    result.add_argument("--colliders-sha256", default="e61feea4f3f8c8b9965bbc9695bbfbec58f915b79287060ec963bdf3ec7b67fa")
    result.add_argument("--readback-tolerance", type=float, default=1e-5)
    return result


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser().parse_args(argv)
    args.project_root = args.project_root.resolve()
    args.stream = args.stream.resolve()
    args.sidecar = args.sidecar.resolve()
    args.out_dir = args.out_dir.resolve()
    try:
        if args.mode == "DRY":
            dry(args)
        elif args.mode == "APPLY":
            apply(args)
        else:
            revert(args)
        return 0
    except (RecoveryError, OSError, ValueError, KeyError) as exc:
        print(f"CURTAIN_STREAM_TO_ABC_STOPPED|run={args.run_id}|mode={args.mode}|reason={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
