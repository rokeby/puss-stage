"""Shared display-rate clip renderer for jointed shadow puppets.

A clip is ``[(seconds, pose, move_seconds, ease), ...]``.  Key times and every
moving in-between are placed on display frames.  Static holds remain byte
identical, so the atlas packer stores one cell for the whole hold.  No handheld
wobble is baked here; Unreal supplies that live.
"""
from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image


DEFAULT_DISPLAY_FPS = 25.0
DEFAULT_FACE_SWAP = 0.5
DEFAULT_QUANTUM = 0.01
MIN_BUDGET_MOVE_FRAMES = 4
DEFAULT_RENDER_SCALE = 2.0


def scaled_render_size(cell_inner_px: int, render_scale: float = DEFAULT_RENDER_SCALE) -> int:
    """Source-frame dimension for a target atlas-cell interior."""
    if cell_inner_px < 1:
        raise ValueError("cell_inner_px must be positive")
    if render_scale < 1.0:
        raise ValueError("render_scale must be at least 1")
    return int(math.ceil(float(cell_inner_px) * float(render_scale)))


@dataclass
class ClipResult:
    poses: list[dict]
    display_frames: list[int]
    move_frames: dict[int, int]
    original_move_frames: dict[int, int]
    reductions: list[dict]
    rendered_frames: int
    unique_cells: int | None = None


def display_frame(seconds: float, fps: float) -> int:
    return int(math.floor(float(seconds) * float(fps) + 0.5))


def ease_amount(name: str, amount: float) -> float:
    u = min(1.0, max(0.0, float(amount)))
    if name == "snap":
        return 1.0
    if name == "linear":
        return u
    if name == "ease_in_out":
        return u * u * (3.0 - 2.0 * u)
    if name == "ease_out":
        return 1.0 - (1.0 - u) ** 3
    raise ValueError("unknown ease %r" % name)


def _quantize(value, quantum: float):
    if isinstance(value, (float, np.floating)):
        return round(float(value) / quantum) * quantum
    if isinstance(value, np.ndarray):
        return tuple(_quantize(item, quantum) for item in value.tolist())
    if isinstance(value, tuple):
        return tuple(_quantize(item, quantum) for item in value)
    if isinstance(value, list):
        return [_quantize(item, quantum) for item in value]
    if isinstance(value, dict):
        return {key: _quantize(item, quantum) for key, item in value.items()}
    return value


def _lerp_value(start, end, amount: float):
    if isinstance(start, (int, float, np.number)) and isinstance(end, (int, float, np.number)):
        return float(start) + (float(end) - float(start)) * amount
    if isinstance(start, (tuple, list)) and isinstance(end, (tuple, list)) and len(start) == len(end):
        values = [_lerp_value(a, b, amount) for a, b in zip(start, end)]
        return tuple(values) if isinstance(end, tuple) else values
    return copy.deepcopy(end if amount >= 1.0 else start)


def interpolate_pose(
    start: dict,
    end: dict,
    amount: float,
    *,
    face_swap: float = DEFAULT_FACE_SWAP,
    point_keys: Iterable[str] = (),
    point_resolver: Callable[[dict, str], tuple[float, float]] | None = None,
    quantum: float = DEFAULT_QUANTUM,
) -> dict:
    """Interpolate numeric controls and point-valued IK targets.

    Replacement-card values (notably ``face``) switch at ``face_swap``.  A
    missing IK target is resolved from the pose's current joint angles, so the
    target can move continuously into or out of an IK-controlled pose.
    """
    if amount <= 0.0:
        return _quantize(copy.deepcopy(start), quantum)
    if amount >= 1.0:
        return _quantize(copy.deepcopy(end), quantum)
    point_keys = set(point_keys)
    result = copy.deepcopy(start)
    for key in set(start) | set(end):
        if key == "face":
            result[key] = copy.deepcopy(end[key] if amount >= face_swap else start[key])
            continue
        if key in point_keys:
            a = start.get(key)
            b = end.get(key)
            if a is None and point_resolver is not None:
                a = point_resolver(start, key)
            if b is None and point_resolver is not None:
                b = point_resolver(end, key)
            result[key] = _lerp_value(a, b, amount) if a is not None and b is not None else copy.deepcopy(b)
            continue
        if key in start and key in end:
            result[key] = _lerp_value(start[key], end[key], amount)
        elif amount >= 1.0 and key in end:
            result[key] = copy.deepcopy(end[key])
    return _quantize(result, quantum)


def _validated_keys(keys, fps: float):
    if not keys:
        raise ValueError("clip has no keys")
    normalized = []
    previous_time = -math.inf
    occupied = set()
    for index, item in enumerate(keys):
        if len(item) != 4:
            raise ValueError("key %d must be (seconds, pose, move_seconds, ease)" % index)
        seconds, pose, move_seconds, ease = item
        if seconds <= previous_time:
            raise ValueError("key times must be strictly increasing")
        frame = display_frame(seconds, fps)
        if frame in occupied:
            raise ValueError("key events collapse onto display frame %d" % frame)
        ease_amount(ease, 0.5)
        normalized.append((float(seconds), copy.deepcopy(pose), float(move_seconds), ease, frame))
        occupied.add(frame)
        previous_time = seconds
    return normalized


def _initial_move_frames(keys, fps: float) -> dict[int, int]:
    counts = {}
    for index, (_seconds, _pose, move_seconds, ease, _frame) in enumerate(keys):
        if index == 0:
            counts[index] = 0
        elif ease == "snap":
            counts[index] = 1
        else:
            counts[index] = max(MIN_BUDGET_MOVE_FRAMES, int(round(move_seconds * fps)))
    return counts


def reduce_longest_moves(move_frames: dict[int, int], amount: int) -> tuple[dict[int, int], list[dict]]:
    """Remove samples from currently longest moves first, never below four."""
    result = dict(move_frames)
    before = dict(move_frames)
    for _ in range(max(0, int(amount))):
        eligible = [index for index, count in result.items() if index > 0 and count > MIN_BUDGET_MOVE_FRAMES]
        if not eligible:
            break
        index = min(eligible, key=lambda item: (-result[item], item))
        result[index] -= 1
    reductions = [
        {"key_index": index, "from": before[index], "to": result[index]}
        for index in sorted(result) if result[index] != before[index]
    ]
    return result, reductions


def clip_frames(
    keys,
    length: float,
    *,
    fps: float = DEFAULT_DISPLAY_FPS,
    face_swap: float = DEFAULT_FACE_SWAP,
    tear_speed: float = 0.45,
    point_keys: Iterable[str] = (),
    point_resolver: Callable[[dict, str], tuple[float, float]] | None = None,
    quantum: float = DEFAULT_QUANTUM,
    move_frames: dict[int, int] | None = None,
) -> ClipResult:
    normalized = _validated_keys(keys, fps)
    counts = _initial_move_frames(normalized, fps) if move_frames is None else dict(move_frames)
    total_frames = int(round(float(length) * float(fps)))
    if total_frames <= 0:
        raise ValueError("clip length must be positive")

    for index in range(1, len(normalized)):
        available = (normalized[index + 1][4] - normalized[index][4]) if index + 1 < len(normalized) else total_frames - normalized[index][4]
        if counts[index] > available:
            raise ValueError("move at key %d overlaps the next key (%d > %d display frames)" %
                             (index, counts[index], available))

    poses = []
    active = 0
    for frame in range(total_frames):
        while active + 1 < len(normalized) and normalized[active + 1][4] <= frame:
            active += 1
        _seconds, target, _move_seconds, ease, key_frame = normalized[active]
        if active == 0:
            pose = copy.deepcopy(target)
        else:
            start = normalized[active - 1][1]
            offset = frame - key_frame
            count = counts[active]
            raw = 1.0 if offset >= count else (offset + 1) / float(count)
            pose = interpolate_pose(start, target, ease_amount(ease, raw), face_swap=face_swap,
                                    point_keys=point_keys, point_resolver=point_resolver, quantum=quantum)
        tears = pose.get("face", {}).get("tears")
        if tears:
            elapsed = max(0.0, (frame - key_frame) / float(fps))
            pose = copy.deepcopy(pose)
            pose["face"]["tears"] = [min(1.0, value + elapsed * tear_speed) for value in tears]
            pose = _quantize(pose, quantum)
        poses.append(pose)

    return ClipResult(poses=poses, display_frames=list(range(total_frames)), move_frames=counts,
                      original_move_frames=_initial_move_frames(normalized, fps), reductions=[],
                      rendered_frames=total_frames)


def render_clip(
    keys,
    length: float,
    out_dir: Path,
    render_pose: Callable[[dict], Image.Image],
    *,
    fps: float = DEFAULT_DISPLAY_FPS,
    max_cells: int | None = None,
    face_swap: float = DEFAULT_FACE_SWAP,
    tear_speed: float = 0.45,
    point_keys: Iterable[str] = (),
    point_resolver: Callable[[dict, str], tuple[float, float]] | None = None,
    quantum: float = DEFAULT_QUANTUM,
) -> ClipResult:
    """Render full display-frame source files, adapting longest moves to a cell budget."""
    result = clip_frames(keys, length, fps=fps, face_swap=face_swap, tear_speed=tear_speed,
                         point_keys=point_keys, point_resolver=point_resolver, quantum=quantum)
    all_reductions = []
    while True:
        images = [render_pose(pose) for pose in result.poses]
        hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
        unique = len(set(hashes))
        if max_cells is None or unique <= max_cells:
            break
        adjusted, reductions = reduce_longest_moves(result.move_frames, unique - max_cells)
        if not reductions:
            raise ValueError("max_cells=%d cannot be met; %d unique cells remain with every move at floor %d" %
                             (max_cells, unique, MIN_BUDGET_MOVE_FRAMES))
        all_reductions.extend(reductions)
        result = clip_frames(keys, length, fps=fps, face_swap=face_swap, tear_speed=tear_speed,
                             point_keys=point_keys, point_resolver=point_resolver, quantum=quantum,
                             move_frames=adjusted)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for frame, image in zip(result.display_frames, images):
        image.save(out_dir / ("f%04d.png" % frame))
    result.unique_cells = unique
    result.reductions = all_reductions
    return result
