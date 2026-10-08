#!/usr/bin/env python3
"""Offline Shore cast motion-intensity analysis.

Reads UE-exported binary FBX animation curves without Blender or Unreal, builds a
24 fps body-motion energy curve, and writes the Scene 3 timing report, segment
JSON, and strip-chart preview requested by the conductor brief.

Modes:
  DRY     analyse and print the planned result; write nothing.
  APPLY   require ``--confirm "APPLY S3MOCAPINTENSITY"``; back up named outputs,
          write them atomically, read them back, and print a run-id marker.
  REVERT  require ``--confirm "REVERT S3MOCAPINTENSITY"``; restore the backup
          named by the JSON record. Newly created outputs are moved into that
          backup (never permanently deleted).

This tool is deliberately offline. Unreal dirty-package census and package saves
are not applicable, and the record says so explicitly.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


FBX_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"
FBX_TICKS_PER_SECOND = 46_186_158_000.0
FIGURES = (
    "Shore01_M56",
    "Shore02_F52",
    "Shore03_M59",
    "Shore04_F55",
    "Shore05_M53",
    "Shore06_F25",
)
TAKES = {
    "Shore01_M56": "shoreguy1",
    "Shore02_F52": "shoreguy12",
    "Shore03_M59": "shoreguy3",
    "Shore04_F55": "shoreguy4",
    "Shore05_M53": "shoreguy5",
    "Shore06_F25": "shoreguy6",
}
ENERGY_BONES = (
    "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
    "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
    "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
    "neck_01", "neck_02", "head",
)
ROOT_CANDIDATES = ("pelvis", "root")
AXES = ("X", "Y", "Z")
LABELS = ("CALM", "MEDIUM", "FRENZY")


class FbxError(RuntimeError):
    """A binary FBX did not satisfy the narrow animation contract."""


@dataclass(frozen=True)
class NodeHeader:
    start: int
    end: int
    property_count: int
    property_bytes: int
    name: str


@dataclass
class FbxIndex:
    version: int
    models: dict[int, str]
    curve_nodes: dict[int, str]
    curves: set[int]
    connections: list[tuple[str, int, int, str]]


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise FbxError(f"TRUNCATED_FBX|wanted={size}|got={len(data)}|offset={handle.tell()}")
    return data


def _read_header(handle: BinaryIO, version: int) -> NodeHeader | None:
    start = handle.tell()
    if version >= 7500:
        raw = _read_exact(handle, 25)
        end, count, prop_bytes, name_len = struct.unpack("<QQQB", raw)
    else:
        raw = _read_exact(handle, 13)
        end, count, prop_bytes, name_len = struct.unpack("<IIIB", raw)
    if end == count == prop_bytes == name_len == 0:
        return None
    if end <= start or name_len == 0:
        raise FbxError(f"BAD_NODE_HEADER|offset={start}|end={end}|name_len={name_len}")
    name = _read_exact(handle, name_len).decode("utf-8", "replace")
    return NodeHeader(start, int(end), int(count), int(prop_bytes), name)


def _read_array(handle: BinaryIO, code: str, decode: bool) -> np.ndarray | None:
    length, encoding, compressed = struct.unpack("<III", _read_exact(handle, 12))
    payload = _read_exact(handle, compressed)
    if not decode:
        return None
    if encoding == 1:
        payload = zlib.decompress(payload)
    elif encoding != 0:
        raise FbxError(f"ARRAY_ENCODING|{encoding}")
    dtypes = {"f": "<f4", "d": "<f8", "i": "<i4", "l": "<i8", "b": "i1"}
    itemsize = np.dtype(dtypes[code]).itemsize
    if len(payload) != length * itemsize:
        raise FbxError(f"ARRAY_LENGTH|type={code}|items={length}|bytes={len(payload)}")
    return np.frombuffer(payload, dtype=dtypes[code]).copy()


def _read_property(handle: BinaryIO, decode_arrays: bool = False) -> Any:
    code = _read_exact(handle, 1).decode("ascii")
    scalar = {
        "Y": ("<h", 2), "C": ("<?", 1), "I": ("<i", 4),
        "F": ("<f", 4), "D": ("<d", 8), "L": ("<q", 8),
    }
    if code in scalar:
        fmt, size = scalar[code]
        return struct.unpack(fmt, _read_exact(handle, size))[0]
    if code in "fdilb":
        return _read_array(handle, code, decode_arrays)
    if code in "SR":
        size = struct.unpack("<I", _read_exact(handle, 4))[0]
        raw = _read_exact(handle, size)
        return raw.decode("utf-8", "replace") if code == "S" else raw
    raise FbxError(f"PROPERTY_TYPE|{code!r}|offset={handle.tell() - 1}")


def _read_properties(handle: BinaryIO, header: NodeHeader, decode_arrays: bool = False) -> list[Any]:
    start = handle.tell()
    values = [_read_property(handle, decode_arrays) for _ in range(header.property_count)]
    consumed = handle.tell() - start
    if consumed != header.property_bytes:
        raise FbxError(
            f"PROPERTY_BYTES|node={header.name}|declared={header.property_bytes}|actual={consumed}"
        )
    return values


def _clean_object_name(value: Any) -> str:
    text = str(value)
    if "\x00\x01" in text:  # binary FBX stores "name<NUL><SOH>class"
        return text.split("\x00\x01", 1)[0]
    return text.split("::")[-1]


def _root_nodes(handle: BinaryIO, version: int) -> Iterable[NodeHeader]:
    terminator = 25 if version >= 7500 else 13
    file_size = os.fstat(handle.fileno()).st_size
    while handle.tell() + terminator <= file_size:
        header = _read_header(handle, version)
        if header is None:
            return
        yield header


def index_fbx(path: Path) -> FbxIndex:
    """First pass: index object ids and connections without inflating curve arrays."""
    with path.open("rb") as handle:
        if handle.read(len(FBX_MAGIC)) != FBX_MAGIC:
            raise FbxError(f"NOT_BINARY_FBX|{path}")
        version = struct.unpack("<I", _read_exact(handle, 4))[0]
        models: dict[int, str] = {}
        curve_nodes: dict[int, str] = {}
        curves: set[int] = set()
        connections: list[tuple[str, int, int, str]] = []
        terminator = 25 if version >= 7500 else 13
        for root in _root_nodes(handle, version):
            root_props = _read_properties(handle, root)
            del root_props
            if root.name == "Objects":
                while handle.tell() < root.end - terminator:
                    child = _read_header(handle, version)
                    if child is None:
                        break
                    props = _read_properties(handle, child)
                    if child.name == "Model" and len(props) >= 2:
                        models[int(props[0])] = _clean_object_name(props[1])
                    elif child.name == "AnimationCurveNode" and len(props) >= 2:
                        curve_nodes[int(props[0])] = _clean_object_name(props[1])
                    elif child.name == "AnimationCurve" and props:
                        curves.add(int(props[0]))
                    handle.seek(child.end)
            elif root.name == "Connections":
                while handle.tell() < root.end - terminator:
                    child = _read_header(handle, version)
                    if child is None:
                        break
                    props = _read_properties(handle, child)
                    if child.name == "C" and len(props) >= 3:
                        connections.append((str(props[0]), int(props[1]), int(props[2]),
                                            str(props[3]) if len(props) > 3 else ""))
                    handle.seek(child.end)
            handle.seek(root.end)
    if not models or not curve_nodes or not curves or not connections:
        raise FbxError(
            f"ANIMATION_INDEX_EMPTY|models={len(models)}|nodes={len(curve_nodes)}|"
            f"curves={len(curves)}|connections={len(connections)}"
        )
    return FbxIndex(version, models, curve_nodes, curves, connections)


def _curve_bindings(index: FbxIndex, wanted_bones: set[str]) -> dict[int, tuple[str, str, str]]:
    model_ids = {mid: name for mid, name in index.models.items() if name in wanted_bones}
    node_target: dict[int, tuple[str, str]] = {}
    for kind, child, parent, prop in index.connections:
        del kind
        if child in index.curve_nodes and parent in model_ids:
            channel = prop or index.curve_nodes[child]
            node_target[child] = (model_ids[parent], channel)
        elif parent in index.curve_nodes and child in model_ids:
            channel = prop or index.curve_nodes[parent]
            node_target[parent] = (model_ids[child], channel)
    bindings: dict[int, tuple[str, str, str]] = {}
    for kind, child, parent, prop in index.connections:
        del kind
        if child in index.curves and parent in node_target:
            bone, channel = node_target[parent]
            axis = prop.split("|")[-1].upper()
            if axis in AXES:
                bindings[child] = (bone, channel, axis)
        elif parent in index.curves and child in node_target:
            bone, channel = node_target[child]
            axis = prop.split("|")[-1].upper()
            if axis in AXES:
                bindings[parent] = (bone, channel, axis)
    return bindings


def read_selected_curves(path: Path, selected_ids: set[int], version: int) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Second pass: inflate only the curves connected to the requested bones."""
    result: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    with path.open("rb") as handle:
        _read_exact(handle, len(FBX_MAGIC) + 4)
        terminator = 25 if version >= 7500 else 13
        for root in _root_nodes(handle, version):
            _read_properties(handle, root)
            if root.name == "Objects":
                while handle.tell() < root.end - terminator:
                    child = _read_header(handle, version)
                    if child is None:
                        break
                    props = _read_properties(handle, child)
                    curve_id = int(props[0]) if child.name == "AnimationCurve" and props else None
                    if curve_id not in selected_ids:
                        handle.seek(child.end)
                        continue
                    key_time = key_value = None
                    while handle.tell() < child.end - terminator:
                        item = _read_header(handle, version)
                        if item is None:
                            break
                        decode = item.name in ("KeyTime", "KeyValueFloat")
                        item_props = _read_properties(handle, item, decode_arrays=decode)
                        if decode and item_props:
                            if item.name == "KeyTime":
                                key_time = item_props[0]
                            else:
                                key_value = item_props[0]
                        handle.seek(item.end)
                    if key_time is None or key_value is None or len(key_time) != len(key_value):
                        raise FbxError(f"CURVE_KEYS|id={curve_id}|times={None if key_time is None else len(key_time)}|"
                                       f"values={None if key_value is None else len(key_value)}")
                    result[curve_id] = (key_time, key_value)
                    handle.seek(child.end)
            handle.seek(root.end)
    missing = selected_ids - result.keys()
    if missing:
        raise FbxError(f"CURVES_MISSING|count={len(missing)}|first={sorted(missing)[:5]}")
    return result


def load_animation_tracks(path: Path) -> tuple[dict[str, dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]], dict[str, Any]]:
    wanted = set(ENERGY_BONES) | set(ROOT_CANDIDATES)
    index = index_fbx(path)
    bindings = _curve_bindings(index, wanted)
    if not bindings:
        raise FbxError("NO_WANTED_CURVE_BINDINGS")
    curves = read_selected_curves(path, set(bindings), index.version)
    tracks: dict[str, dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]] = {}
    for cid, (bone, raw_channel, axis) in bindings.items():
        channel_l = raw_channel.lower()
        if "rotation" in channel_l or raw_channel.upper().endswith("R"):
            channel = "rotation"
        elif "translation" in channel_l or raw_channel.upper().endswith("T"):
            channel = "translation"
        else:
            continue
        times, values = curves[cid]
        tracks.setdefault(bone, {}).setdefault(channel, {})[axis] = (times, values.astype(np.float64))
    used = sorted(b for b in ENERGY_BONES if len(tracks.get(b, {}).get("rotation", {})) == 3)
    missing = sorted(set(ENERGY_BONES) - set(used))
    if missing:
        raise FbxError(f"REQUIRED_ROTATION_BONES_MISSING|{','.join(missing)}")
    root = next((b for b in ROOT_CANDIDATES if len(tracks.get(b, {}).get("translation", {})) == 3), None)
    if root is None:
        raise FbxError("ROOT_TRANSLATION_MISSING|pelvis,root")
    meta = {
        "fbx_version": index.version,
        "models": len(index.models),
        "animation_curve_nodes": len(index.curve_nodes),
        "animation_curves": len(index.curves),
        "connections": len(index.connections),
        "energy_bones": used,
        "root_motion_bone": root,
        "selected_curves": len(bindings),
    }
    return tracks, meta


def _interp_axis(axis: tuple[np.ndarray, np.ndarray], target_seconds: np.ndarray, origin_tick: int) -> np.ndarray:
    ticks, values = axis
    seconds = (ticks.astype(np.float64) - float(origin_tick)) / FBX_TICKS_PER_SECOND
    order = np.argsort(seconds)
    seconds, values = seconds[order], values[order]
    unique, indices = np.unique(seconds, return_index=True)
    return np.interp(target_seconds, unique, values[indices])


def _smooth(values: np.ndarray, fps: float, seconds: float) -> np.ndarray:
    samples = max(1, int(round(fps * seconds)))
    if samples % 2 == 0:
        samples += 1
    if samples <= 1:
        return values.copy()
    window = np.hanning(samples)
    window /= window.sum()
    pad = samples // 2
    return np.convolve(np.pad(values, pad, mode="reflect"), window, mode="valid")


def motion_energy_from_tracks(
    tracks: dict[str, dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]],
    *, fps: float, smoothing_seconds: float, root_weight: float,
) -> dict[str, Any]:
    selected_axes = [a for b in ENERGY_BONES for a in tracks[b]["rotation"].values()]
    root_bone = next(b for b in ROOT_CANDIDATES if len(tracks.get(b, {}).get("translation", {})) == 3)
    selected_axes += list(tracks[root_bone]["translation"].values())
    origin_tick = min(int(np.min(t)) for t, _ in selected_axes)
    end_tick = max(int(np.max(t)) for t, _ in selected_axes)
    duration = (end_tick - origin_tick) / FBX_TICKS_PER_SECOND
    if duration < 1.0:
        raise FbxError(f"ANIMATION_TOO_SHORT|seconds={duration:.6f}")
    sample_times = np.arange(0.0, duration + 0.5 / fps, 1.0 / fps)
    angular_sum = np.zeros_like(sample_times)
    for bone in ENERGY_BONES:
        euler = np.column_stack([
            _interp_axis(tracks[bone]["rotation"][axis], sample_times, origin_tick) for axis in AXES
        ])
        radians = np.unwrap(np.deg2rad(euler), axis=0)
        velocity = np.gradient(radians, 1.0 / fps, axis=0)
        angular_sum += np.linalg.norm(np.rad2deg(velocity), axis=1)
    root_xyz = np.column_stack([
        _interp_axis(tracks[root_bone]["translation"][axis], sample_times, origin_tick) for axis in AXES
    ])
    root_speed = np.linalg.norm(np.gradient(root_xyz, 1.0 / fps, axis=0), axis=1)
    raw = angular_sum + root_weight * root_speed
    smoothed = _smooth(raw, fps, smoothing_seconds)
    q10, q90 = np.percentile(smoothed, [10.0, 90.0])
    if q90 - q10 < 1e-6:
        raise FbxError(f"ENERGY_RANGE_TOO_SMALL|q10={q10}|q90={q90}")
    normalized = np.clip((smoothed - q10) / (q90 - q10), 0.0, 1.0)
    return {
        "source_seconds": sample_times,
        "raw_energy": raw,
        "smoothed_energy": smoothed,
        "normalized_energy": normalized,
        "angular_speed_sum": angular_sum,
        "root_speed": root_speed,
        "duration_seconds": float(duration),
        "origin_tick": origin_tick,
        "root_motion_bone": root_bone,
        "energy_quantiles": {"p10": float(q10), "p50": float(np.median(smoothed)), "p90": float(q90)},
        "root_speed_quantiles_cm_s": {
            "p50": float(np.percentile(root_speed, 50)), "p90": float(np.percentile(root_speed, 90)),
        },
    }


def labels_for_energy(values: np.ndarray, calm: float, frenzy: float) -> np.ndarray:
    if not 0.0 < calm < frenzy < 1.0:
        raise ValueError("THRESHOLDS_REQUIRE|0<calm<frenzy<1")
    return np.where(values <= calm, "CALM", np.where(values >= frenzy, "FRENZY", "MEDIUM"))


def _runs(labels: np.ndarray) -> list[tuple[int, int, str]]:
    if len(labels) == 0:
        return []
    edges = np.flatnonzero(labels[1:] != labels[:-1]) + 1
    bounds = np.concatenate(([0], edges, [len(labels)]))
    return [(int(a), int(b), str(labels[a])) for a, b in zip(bounds[:-1], bounds[1:])]


def debounce_labels(labels: np.ndarray, values: np.ndarray, min_samples: int) -> np.ndarray:
    result = labels.copy()
    centres = {"CALM": 0.16, "MEDIUM": 0.50, "FRENZY": 0.84}
    for _ in range(64):
        short = next(((a, b, label) for a, b, label in _runs(result) if b - a < min_samples), None)
        if short is None:
            break
        a, b, _ = short
        neighbours = []
        if a > 0:
            neighbours.append(str(result[a - 1]))
        if b < len(result):
            neighbours.append(str(result[b]))
        if not neighbours:
            break
        mean = float(np.mean(values[a:b]))
        replacement = min(neighbours, key=lambda lab: abs(mean - centres[lab]))
        result[a:b] = replacement
    return result


def seconds_to_timecode(seconds: float, fps: float = 24.0) -> str:
    sign = "-" if seconds < 0 else ""
    frames = int(round(abs(seconds) * fps))
    ff = frames % int(round(fps))
    total_s = frames // int(round(fps))
    ss, mm = total_s % 60, total_s // 60
    return f"{sign}{mm:02d}:{ss:02d}:{ff:02d}"


def segment_rows(
    labels: np.ndarray, source_seconds: np.ndarray, *, play_rate: float, scene_offset_seconds: float,
) -> list[dict[str, Any]]:
    step = float(source_seconds[1] - source_seconds[0]) if len(source_seconds) > 1 else 0.0
    rows = []
    for start, stop, label in _runs(labels):
        source_in = float(source_seconds[start])
        source_out = float(source_seconds[min(stop - 1, len(source_seconds) - 1)] + step)
        scene_in = source_in / play_rate + scene_offset_seconds
        scene_out = source_out / play_rate + scene_offset_seconds
        rows.append({
            "class": label,
            "source_in_seconds": round(source_in, 4),
            "source_out_seconds": round(source_out, 4),
            "source_timecode_in": seconds_to_timecode(source_in),
            "source_timecode_out": seconds_to_timecode(source_out),
            "scene3_in_seconds": round(scene_in, 4),
            "scene3_out_seconds": round(scene_out, 4),
            "scene3_timecode_in": seconds_to_timecode(scene_in),
            "scene3_timecode_out": seconds_to_timecode(scene_out),
            "duration_scene_seconds": round(scene_out - scene_in, 4),
        })
    return rows


def collective_windows(
    figures: list[dict[str, Any]], *, fps: float, play_rate: float, scene_offset_seconds: float,
    minimum_seconds: float,
) -> dict[str, Any]:
    start = scene_offset_seconds
    end = min(f["analysis"]["duration_seconds"] / play_rate + scene_offset_seconds for f in figures)
    scene_times = np.arange(start, end + 0.5 / fps, 1.0 / fps)
    per_figure = []
    for figure in figures:
        source = np.clip((scene_times - scene_offset_seconds) * play_rate, 0.0,
                         figure["analysis"]["duration_seconds"])
        idx = np.clip(np.rint(source * figure["analysis"]["fps"]).astype(int), 0,
                      len(figure["labels"]) - 1)
        per_figure.append(figure["labels"][idx])
    matrix = np.vstack(per_figure)
    state = np.full(len(scene_times), "NONE", dtype="<U12")
    state[np.all(matrix == "CALM", axis=0)] = "ALL_CALM"
    state[np.all(matrix == "FRENZY", axis=0)] = "ALL_FRENZY"
    windows = []
    min_samples = int(math.ceil(minimum_seconds * fps))
    for a, b, label in _runs(state):
        if label == "NONE" or b - a < min_samples:
            continue
        out = float(scene_times[min(b - 1, len(scene_times) - 1)] + 1.0 / fps)
        windows.append({
            "class": label,
            "scene3_in_seconds": round(float(scene_times[a]), 4),
            "scene3_out_seconds": round(out, 4),
            "scene3_timecode_in": seconds_to_timecode(float(scene_times[a])),
            "scene3_timecode_out": seconds_to_timecode(out),
            "duration_seconds": round(out - float(scene_times[a]), 4),
        })
    return {
        "common_scene3_in_seconds": round(float(start), 4),
        "common_scene3_out_seconds": round(float(end), 4),
        "minimum_window_seconds": minimum_seconds,
        "counts": {
            "ALL_CALM": sum(1 for row in windows if row["class"] == "ALL_CALM"),
            "ALL_FRENZY": sum(1 for row in windows if row["class"] == "ALL_FRENZY"),
        },
        "windows": windows,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyse(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_root = Path(args.source_root)
    figure_data = []
    json_figures = []
    scene_offset_seconds = args.scene_offset_frames / args.scene_fps
    for figure in FIGURES:
        source = source_root / "DerivedAssets" / "S3Sackcloth" / "bodies" / figure / f"{figure}_Anim.fbx"
        if not source.is_file():
            raise FileNotFoundError(f"MOCAP_SOURCE_MISSING|{source}")
        tracks, fbx_meta = load_animation_tracks(source)
        energy = motion_energy_from_tracks(
            tracks, fps=args.fps, smoothing_seconds=args.smoothing_seconds, root_weight=args.root_weight,
        )
        labels = labels_for_energy(energy["normalized_energy"], args.calm_threshold, args.frenzy_threshold)
        labels = debounce_labels(labels, energy["normalized_energy"], max(1, int(round(args.min_segment_seconds * args.fps))))
        segments = segment_rows(labels, energy["source_seconds"], play_rate=args.play_rate,
                                scene_offset_seconds=scene_offset_seconds)
        runtime = {
            "id": figure,
            "labels": labels,
            "source_seconds": energy["source_seconds"],
            "normalized_energy": energy["normalized_energy"],
            "analysis": {"duration_seconds": energy["duration_seconds"], "fps": args.fps},
        }
        figure_data.append(runtime)
        json_figures.append({
            "id": figure,
            "take": TAKES[figure],
            "source_path": source.as_posix(),
            "source_bytes": source.stat().st_size,
            "source_sha256": sha256_file(source),
            "fbx": fbx_meta,
            "analysis": {
                "sample_fps": args.fps,
                "samples": len(energy["source_seconds"]),
                "duration_seconds": round(energy["duration_seconds"], 6),
                "energy_quantiles": {k: round(v, 6) for k, v in energy["energy_quantiles"].items()},
                "root_speed_quantiles_cm_s": {
                    k: round(v, 6) for k, v in energy["root_speed_quantiles_cm_s"].items()
                },
                "root_motion_bone": energy["root_motion_bone"],
            },
            "segments": segments,
        })
    collective = collective_windows(
        figure_data, fps=args.scene_fps, play_rate=args.play_rate,
        scene_offset_seconds=scene_offset_seconds, minimum_seconds=args.collective_min_seconds,
    )
    run = args.run or _dt.datetime.now(_dt.timezone.utc).strftime("S3MOCAP-%Y%m%d-%H%M%S")
    record = {
        "schema": "pussstage.s3_mocap_intensity.v1",
        "run": run,
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "evidence_tier": "measured",
        "method": {
            "energy": "sum of shortest-path Euler angular-speed magnitudes for 16 spine/arm/head bones, plus root_weight times pelvis/root translation speed",
            "normalization": "per-figure p10 -> 0 and p90 -> 1, clipped; preserves timing while compensating for performer/retarget amplitude",
            "classification": "CALM <= calm_threshold; FRENZY >= frenzy_threshold; MEDIUM otherwise; short runs merged to nearest adjacent class",
            "collective": "all six labels agree at the same current Scene 3 time for at least collective_min_seconds",
            "interpretation": "threshold labels are inferred aids for editorial placement, not visually accepted choreography",
        },
        "config": {
            "sample_fps": args.fps,
            "scene_fps": args.scene_fps,
            "smoothing_seconds": args.smoothing_seconds,
            "root_weight": args.root_weight,
            "calm_threshold": args.calm_threshold,
            "frenzy_threshold": args.frenzy_threshold,
            "min_segment_seconds": args.min_segment_seconds,
            "collective_min_seconds": args.collective_min_seconds,
            "play_rate": args.play_rate,
            "scene_offset_frames": args.scene_offset_frames,
            "scene_mapping": "scene3_seconds = source_seconds / play_rate + scene_offset_frames / scene_fps",
        },
        "dirty_package_census": {
            "status": "not_applicable",
            "reason": "offline-only FBX analysis; Unreal Editor access is forbidden by the brief",
            "content_packages_saved": [],
            "map_packages_saved": [],
        },
        "figures": json_figures,
        "collective": collective,
    }
    return record, figure_data


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_chart(record: dict[str, Any], figure_data: list[dict[str, Any]]) -> Image.Image:
    width, height = 1800, 1260
    left, right, top, row_h = 220, 50, 130, 165
    plot_w = width - left - right
    image = Image.new("RGB", (width, height), "#f7f3ea")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font, label_font, small_font = _font(32, True), _font(22, True), _font(18)
    draw.text((left, 28), "S3 Shore cast — motion intensity aligned to current Scene 3 time", fill="#1c2430", font=title_font)
    cfg = record["config"]
    draw.text((left, 76),
              f"24 fps source analysis · {cfg['smoothing_seconds']:.2f}s smoothing · relative p10–p90 scale · "
              f"CALM ≤ {cfg['calm_threshold']:.2f} · FRENZY ≥ {cfg['frenzy_threshold']:.2f}",
              fill="#4b5563", font=small_font)
    scene_start = record["collective"]["common_scene3_in_seconds"]
    scene_end = max(f["analysis"]["duration_seconds"] / cfg["play_rate"] + cfg["scene_offset_frames"] / cfg["scene_fps"]
                    for f in figure_data)

    def xpos(seconds: float) -> float:
        return left + (seconds - scene_start) / (scene_end - scene_start) * plot_w

    for second in np.arange(math.ceil(scene_start / 10) * 10, scene_end + 0.01, 10):
        x = xpos(float(second))
        draw.line((x, top - 12, x, top + row_h * 6), fill="#c9c2b5", width=1)
        draw.text((x - 24, top - 35), seconds_to_timecode(float(second))[:5], fill="#555", font=small_font)
    collective_colours = {"ALL_CALM": (68, 143, 92, 48), "ALL_FRENZY": (190, 52, 55, 52)}
    for window in record["collective"]["windows"]:
        x0, x1 = xpos(window["scene3_in_seconds"]), xpos(window["scene3_out_seconds"])
        draw.rectangle((x0, top - 10, x1, top + row_h * 6 - 15), fill=collective_colours[window["class"]])
    bg = {"CALM": (110, 176, 125, 55), "MEDIUM": (224, 178, 70, 42), "FRENZY": (210, 76, 80, 58)}
    for row, (figure, output) in enumerate(zip(figure_data, record["figures"])):
        y0 = top + row * row_h
        y1 = y0 + row_h - 25
        draw.text((24, y0 + 45), figure["id"], fill="#1f2937", font=label_font)
        for segment in output["segments"]:
            draw.rectangle((xpos(segment["scene3_in_seconds"]), y0, xpos(segment["scene3_out_seconds"]), y1),
                           fill=bg[segment["class"]])
        draw.line((left, y1, width - right, y1), fill="#777", width=1)
        scene = figure["source_seconds"] / cfg["play_rate"] + cfg["scene_offset_frames"] / cfg["scene_fps"]
        points = [(xpos(float(t)), y1 - float(v) * (row_h - 45))
                  for t, v in zip(scene, figure["normalized_energy"])]
        draw.line(points, fill="#202a36", width=3, joint="curve")
        draw.line((left, y1 - cfg["calm_threshold"] * (row_h - 45), width - right,
                   y1 - cfg["calm_threshold"] * (row_h - 45)), fill="#357a49", width=1)
        draw.line((left, y1 - cfg["frenzy_threshold"] * (row_h - 45), width - right,
                   y1 - cfg["frenzy_threshold"] * (row_h - 45)), fill="#a62f35", width=1)
    legend_y = top + row_h * 6 + 8
    draw.rectangle((left, legend_y, left + 25, legend_y + 18), fill=bg["CALM"])
    draw.text((left + 35, legend_y - 3), "CALM", fill="#273", font=small_font)
    draw.rectangle((left + 150, legend_y, left + 175, legend_y + 18), fill=bg["MEDIUM"])
    draw.text((left + 185, legend_y - 3), "MEDIUM", fill="#654", font=small_font)
    draw.rectangle((left + 330, legend_y, left + 355, legend_y + 18), fill=bg["FRENZY"])
    draw.text((left + 365, legend_y - 3), "FRENZY", fill="#722", font=small_font)
    counts = record["collective"]["counts"]
    draw.text((left + 540, legend_y - 3),
              f"Full-height bands = ALL six (found: {counts['ALL_CALM']} calm, {counts['ALL_FRENZY']} frenzy)",
              fill="#4b5563", font=small_font)
    draw.text((left, height - 50),
              "Measured from exported FBX curves. Classification is an inferred editorial guide; verify the look in motion.",
              fill="#5d6570", font=small_font)
    return image


def _json_line(rendered: str, needle: str) -> int:
    for number, line in enumerate(rendered.splitlines(), 1):
        if needle in line:
            return number
    return 1


def render_report(record: dict[str, Any], json_rel: str, json_text: str) -> str:
    lines = [
        "# Scene 3 shore mocap intensity — 8 October 2026",
        "",
        "## Outcome",
        "",
        "- **[declaration-proven]** The brief names six Shore figures, their full Animation Sequences, LS_Clams frame-zero section starts, and the `Scene = LS_Clams - 22` nesting (`Docs/Conductor/codex_briefs/p5_mocap_intensity.md:2-4`).",
        f"- **[measured]** All six UE-exported binary FBXs were found, hashed, structurally parsed, and sampled at {record['config']['sample_fps']:.0f} fps (`{json_rel}:{_json_line(json_text, chr(34) + 'source_path' + chr(34))}`).",
        f"- **[measured]** The parser used the same {len(record['figures'][0]['fbx']['energy_bones'])} spine/arm/head bones for every figure; source and curve counts are recorded per FBX (`{json_rel}:{_json_line(json_text, chr(34) + 'energy_bones' + chr(34))}`).",
        "- **[inferred]** CALM/MEDIUM/FRENZY are editorial labels, not rendered or choreographic acceptance. They identify relative intensity within each performer’s take and need Gary’s moving-image review.",
        "",
        "## Method and thresholds",
        "",
        f"- **[measured]** Energy is the sum of angular-speed magnitudes for spine, clavicles, arms, hands, neck and head, plus pelvis/root translation speed weighted by `{record['config']['root_weight']:.2f}`; it is Hann-smoothed over `{record['config']['smoothing_seconds']:.2f} s` (`{json_rel}:{_json_line(json_text, chr(34) + 'method' + chr(34))}`).",
        "- **[inferred]** Per-figure p10→0 / p90→1 normalization compensates for performer scale and retarget amplitude. Defaults are CALM ≤ "
        f"`{record['config']['calm_threshold']:.2f}`, FRENZY ≥ `{record['config']['frenzy_threshold']:.2f}`, MEDIUM between; runs shorter than `{record['config']['min_segment_seconds']:.2f} s` source time are merged. These are exposed as arguments, not creative authority.",
        f"- **[inferred]** Current Scene 3 time uses `source / {record['config']['play_rate']:.3f} + ({record['config']['scene_offset_frames']:.0f} / {record['config']['scene_fps']:.0f}) s`. The 0.6 rate comes from the original segment authoring (`Saved/CodexMocap/select_gentle_shore_segments.py:35`); the current -22-frame nesting is recorded by the retime probe (`Saved/CodexConductor/s3_retime.py:1-8`) and the section lengths in the brief are consistent with 0.6. This is not a fresh Unreal read-back; re-check after any Sequencer retime.",
        "",
        "Timecodes are `MM:SS:FF` at 24 fps. Source time is the FBX/Animation Sequence time; Scene 3 time is the current nested playback time.",
        "",
        "## Collective windows",
        "",
    ]
    windows = record["collective"]["windows"]
    if windows:
        lines += ["| State | Scene 3 in | Scene 3 out | Duration | Evidence |", "| --- | ---: | ---: | ---: | --- |"]
        for row in windows:
            lines.append(f"| {row['class']} | {row['scene3_timecode_in']} | {row['scene3_timecode_out']} | "
                         f"{row['duration_seconds']:.2f} s | **measured** label intersection; interpretation inferred |")
        if not any(row["class"] == "ALL_FRENZY" for row in windows):
            lines += ["", f"**[measured]** No all-six FRENZY window lasts at least "
                      f"{record['collective']['minimum_window_seconds']:.1f} s under the default thresholds. "
                      "Do not silently loosen them; use the per-figure rows to choose explicit retimes."]
    else:
        lines.append("**[measured]** No ≥1.0 s window has all six figures simultaneously CALM or FRENZY under the default thresholds. This is a useful negative result, not permission to loosen thresholds silently.")
    for figure in record["figures"]:
        lines += ["", f"## {figure['id']} / {figure['take']}", "",
                  f"**[measured]** `{figure['source_path']}`; {figure['analysis']['duration_seconds']:.3f} s; "
                  f"SHA-256 `{figure['source_sha256']}` (`{json_rel}:{_json_line(json_text, chr(34) + figure['id'] + chr(34))}`).",
                  "", "| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
        for row in figure["segments"]:
            lines.append(f"| {row['class']} | {row['source_timecode_in']} | {row['source_timecode_out']} | "
                         f"{row['scene3_timecode_in']} | {row['scene3_timecode_out']} | **measured** curve; class inferred |")
    lines += [
        "", "## Use and acceptance boundary", "",
        "1. **[declaration-proven]** Use the JSON segment boundaries or the aligned PNG as placement references; do not change the Animation Sequences (`Docs/Conductor/codex_briefs/p5_mocap_intensity.md:2-4`).",
        "2. **[inferred]** Prefer long CALM spans for first fabric checks, then the listed collective FRENZY spans for stress tests. Threshold changes must be explicit CLI arguments and produce a new preview.",
        "3. **[inferred]** Final acceptance remains a rendered motion/fabric review. Offline FBX analysis cannot prove cloth stability, staging readability, or whether the performance reads as calm/frenzied to Gary.",
        "", "## Reproduce", "",
        "```powershell",
        "python Tools/Mocap/test_shore_mocap_intensity.py",
        "python Tools/Mocap/shore_mocap_intensity.py --mode DRY --source-root E:/PussStage",
        f"python Tools/Mocap/shore_mocap_intensity.py --mode APPLY --confirm \"APPLY S3MOCAPINTENSITY\" --run {record['run']} --source-root E:/PussStage",
        "```", "",
    ]
    return "\n".join(lines)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def output_paths(project_root: Path) -> dict[str, Path]:
    return {
        "json": project_root / "DerivedAssets" / "S3MocapIntensity" / "s3_mocap_intensity_segments.json",
        "png": project_root / "DerivedAssets" / "S3MocapIntensity" / "s3_mocap_intensity_strip.png",
        "doc": project_root / "Docs" / "Conductor" / "S3_MOCAP_INTENSITY_2026-10-08.md",
    }


def make_backup(project_root: Path, run: str, outputs: dict[str, Path]) -> tuple[Path, dict[str, Any]]:
    backup = project_root / "Backups" / f"PreS3MocapIntensity-{run}"
    if backup.exists():
        raise RuntimeError(f"BACKUP_EXISTS|{backup}")
    backup.mkdir(parents=True)
    entries = []
    for key, path in outputs.items():
        relative = path.relative_to(project_root)
        item = {"key": key, "target": relative.as_posix(), "existed": path.is_file()}
        if path.is_file():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
            item["sha256_before"] = sha256_file(path)
            item["backup_file"] = saved.relative_to(project_root).as_posix()
        entries.append(item)
    manifest = {"run": run, "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(), "outputs": entries}
    manifest_path = backup / "backup_manifest.json"
    _atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return backup, manifest


def apply_outputs(args: argparse.Namespace, record: dict[str, Any], figure_data: list[dict[str, Any]]) -> None:
    if args.confirm != "APPLY S3MOCAPINTENSITY":
        raise RuntimeError("CONFIRM_REQUIRED|APPLY S3MOCAPINTENSITY")
    project_root = Path(args.project_root).resolve()
    outputs = output_paths(project_root)
    backup, manifest = make_backup(project_root, record["run"], outputs)
    record["mode"] = "APPLY"
    record["backup"] = backup.relative_to(project_root).as_posix()
    record["backup_manifest"] = manifest
    record["outputs"] = {key: path.relative_to(project_root).as_posix() for key, path in outputs.items()}
    chart = render_chart(record, figure_data)
    with tempfile.SpooledTemporaryFile() as image_file:
        chart.save(image_file, format="PNG", optimize=True)
        image_file.seek(0)
        png_bytes = image_file.read()
    record["png_sha256"] = hashlib.sha256(png_bytes).hexdigest()
    json_text = json.dumps(record, indent=2, sort_keys=False) + "\n"
    report = render_report(record, outputs["json"].relative_to(project_root).as_posix(), json_text)
    _atomic_write(outputs["json"], json_text.encode("utf-8"))
    _atomic_write(outputs["png"], png_bytes)
    _atomic_write(outputs["doc"], report.encode("utf-8"))
    parsed = json.loads(outputs["json"].read_text(encoding="utf-8"))
    if parsed["run"] != record["run"] or sha256_file(outputs["png"]) != record["png_sha256"]:
        raise RuntimeError("OUTPUT_READBACK_FAILED")
    if not outputs["doc"].read_text(encoding="utf-8").startswith("# Scene 3 shore mocap intensity"):
        raise RuntimeError("DOC_READBACK_FAILED")
    print(f"S3_MOCAP_INTENSITY_APPLY_OK|run={record['run']}|figures=6|"
          f"segments={sum(len(f['segments']) for f in record['figures'])}|"
          f"collective={len(record['collective']['windows'])}|backup={record['backup']}")


def revert_outputs(args: argparse.Namespace) -> None:
    if args.confirm != "REVERT S3MOCAPINTENSITY":
        raise RuntimeError("CONFIRM_REQUIRED|REVERT S3MOCAPINTENSITY")
    project_root = Path(args.project_root).resolve()
    outputs = output_paths(project_root)
    record_path = outputs["json"]
    if not record_path.is_file():
        raise RuntimeError(f"RECORD_MISSING|{record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if args.run and record.get("run") != args.run:
        raise RuntimeError(f"RUN_MISMATCH|record={record.get('run')}|requested={args.run}")
    backup = project_root / record["backup"]
    manifest_path = backup / "backup_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["run"] != record["run"]:
        raise RuntimeError("BACKUP_RUN_MISMATCH")
    parked = backup / "reverted_outputs"
    parked.mkdir(exist_ok=True)
    for item in manifest["outputs"]:
        target = project_root / item["target"]
        if item["existed"]:
            saved = project_root / item["backup_file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, target)
            if sha256_file(target) != item["sha256_before"]:
                raise RuntimeError(f"REVERT_READBACK|{target}")
        elif target.exists():
            destination = parked / item["target"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(destination))
    print(f"S3_MOCAP_INTENSITY_REVERT_OK|run={record['run']}|parked={parked.relative_to(project_root).as_posix()}")


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve()
    default_project = here.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--run", default="")
    parser.add_argument("--project-root", default=str(default_project))
    parser.add_argument("--source-root", default="E:/PussStage")
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--scene-fps", type=float, default=24.0)
    parser.add_argument("--smoothing-seconds", type=float, default=1.5)
    parser.add_argument("--root-weight", type=float, default=4.0)
    parser.add_argument("--calm-threshold", type=float, default=0.33)
    parser.add_argument("--frenzy-threshold", type=float, default=0.67)
    parser.add_argument("--min-segment-seconds", type=float, default=1.0)
    parser.add_argument("--collective-min-seconds", type=float, default=1.0)
    parser.add_argument("--play-rate", type=float, default=0.6)
    parser.add_argument("--scene-offset-frames", type=float, default=-22.0)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.fps <= 0 or args.scene_fps <= 0 or args.smoothing_seconds <= 0:
        raise ValueError("POSITIVE_RATE_AND_SMOOTHING_REQUIRED")
    if args.root_weight < 0 or args.min_segment_seconds <= 0 or args.collective_min_seconds <= 0:
        raise ValueError("NONNEGATIVE_WEIGHT_AND_POSITIVE_DURATIONS_REQUIRED")
    if args.play_rate <= 0:
        raise ValueError("POSITIVE_PLAY_RATE_REQUIRED")
    if not 0 < args.calm_threshold < args.frenzy_threshold < 1:
        raise ValueError("THRESHOLDS_REQUIRE|0<calm<frenzy<1")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args)
    if args.mode == "REVERT":
        revert_outputs(args)
        return 0
    record, figure_data = analyse(args)
    if args.mode == "DRY":
        print(f"S3_MOCAP_INTENSITY_DRY_OK|run={record['run']}|figures=6|"
              f"segments={sum(len(f['segments']) for f in record['figures'])}|"
              f"collective={len(record['collective']['windows'])}|writes=0")
        for figure in record["figures"]:
            counts = {label: sum(1 for s in figure["segments"] if s["class"] == label) for label in LABELS}
            print(f"{figure['id']}|seconds={figure['analysis']['duration_seconds']:.3f}|segments={counts}")
        return 0
    apply_outputs(args, record, figure_data)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # one stable failure marker for conductor logs
        print(f"S3_MOCAP_INTENSITY_FAILED|{type(exc).__name__}|{str(exc).replace(chr(10), ' ')}", file=sys.stderr)
        raise
