#!/usr/bin/env python3
"""Build the offline P20 Scene 3 chorus-sway plan and preview.

The measured FBX/JSON/WAV inputs are read from --source-root (the production
tree).  APPLY writes only a plan JSON and a review PNG in --project-root.
REVERT restores or parks those generated files; it never permanently deletes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shore_mocap_intensity as intensity  # noqa: E402

FPS = 24.0
TARGET_PERIOD_S = 3.6
WINDOW_SCENE = (3480, 4200)
SCENE_TO_CLAMS = 22
EASE_S = 1.5
LOOP_BLEND_S = 1.0
CHORUS_AUDIO_S = (128.0, 187.0)

FIGURES: list[dict[str, Any]] = [
    {"id": "Shore01_M56", "animation": "AS_Shore01_M56_shoreguy1_Full",
     "spans": [(5.7083, 12.0833), (25.6667, 32.8750)]},
    {"id": "Shore02_F52", "animation": "AS_Shore02_F52_shoreguy12_Full",
     "spans": [(4.3750, 13.2083)]},
    {"id": "Shore03_M59", "animation": "AS_Shore03_M59_shoreguy3_Full",
     "spans": [(1.1667, 19.1250)]},
    {"id": "Shore04_F55", "animation": "AS_Shore04_F55_shoreguy4_Full",
     "spans": [(71.7083, 89.5417)]},
    {"id": "Shore05_M53", "animation": "AS_Shore05_M53_shoreguy5_Full",
     "spans": [(18.3333, 32.3750)]},
    {"id": "Shore06_F25", "animation": "AS_Shore06_F25_shoreguy6_Full",
     "spans": [(78.1667, 91.4583)]},
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "plan": project_root / "Saved/CodexConductor/s3_chorus_sway_plan.json",
        "preview": project_root / "Docs/Conductor/Previews/P20_CHORUS_SWAY_preview.png",
    }


def selected_run(sway: dict[str, Any], figure_id: str, bounds: tuple[float, float]) -> dict[str, Any]:
    figure = next((row for row in sway["figures"] if row["id"] == figure_id), None)
    if figure is None:
        raise ValueError(f"FIGURE_MISSING|{figure_id}")
    hits = [row for row in figure["calm_runs"]
            if abs(float(row["source_in"]) - bounds[0]) < 0.06
            and abs(float(row["source_out"]) - bounds[1]) < 0.06]
    if len(hits) != 1:
        raise ValueError(f"CALM_RUN_NOT_UNIQUE|{figure_id}|{bounds}|hits={len(hits)}")
    row = dict(hits[0])
    for key in ("signal", "period_s_source", "periodicity"):
        if key not in row:
            raise ValueError(f"CALM_RUN_HAS_NO_SWAY|{figure_id}|{bounds}|missing={key}")
    row["source_in"] = bounds[0]
    row["source_out"] = bounds[1]
    row["play_rate"] = float(row["period_s_source"]) / TARGET_PERIOD_S
    validate_play_rate(row["play_rate"])
    return row


def validate_play_rate(rate: float, baseline: float = 0.6) -> None:
    lo, hi = 0.75 * baseline, 1.30 * baseline
    if not lo - 1e-9 <= rate <= hi + 1e-9:
        raise ValueError(f"PLAY_RATE_OUT_OF_BOUNDS|rate={rate:.6f}|allowed={lo:.6f}..{hi:.6f}")


def sample_signal(tracks: dict[str, Any], signal_name: str, seconds: np.ndarray) -> np.ndarray:
    bone, channel, axis = signal_name.split(".")
    ticks, values = tracks[bone][channel][axis]
    key_seconds = np.asarray(ticks, dtype=np.float64) / intensity.FBX_TICKS_PER_SECOND
    return np.interp(seconds, key_seconds, np.asarray(values, dtype=np.float64))


def fitted_phase(tracks: dict[str, Any], run: dict[str, Any]) -> tuple[float, float]:
    """Return phase in degrees (0 = fitted maximum) at run start, and fit R^2."""
    start, end = float(run["source_in"]), float(run["source_out"])
    period = float(run["period_s_source"])
    t = np.arange(start, end, 1.0 / FPS)
    if len(t) < 2 * FPS:
        raise ValueError("PHASE_WINDOW_TOO_SHORT")
    y = sample_signal(tracks, run["signal"], t)
    omega = 2.0 * math.pi / period
    design = np.column_stack((np.cos(omega * t), np.sin(omega * t), np.ones_like(t), t - t.mean()))
    coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coeff
    residual = float(np.sum((y - predicted) ** 2))
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - residual / total if total > 1e-12 else 0.0
    phi = math.atan2(-float(coeff[1]), float(coeff[0]))
    at_start = (omega * start + phi) % (2.0 * math.pi)
    return math.degrees(at_start), r2


def signed_phase_nudge(base_phase_deg: float, target_phase_deg: float, period_s: float = TARGET_PERIOD_S) -> float:
    delta_cycles = ((target_phase_deg - base_phase_deg + 180.0) % 360.0 - 180.0) / 360.0
    nudge = delta_cycles * period_s
    if abs(nudge) > period_s / 2.0 + 1e-8:
        raise AssertionError("NUDGE_EXCEEDS_HALF_PERIOD")
    return nudge


def build_schedule(window: tuple[int, int], fps: float, spans: list[dict[str, Any]],
                   nudge_s: float, loop_blend_s: float) -> list[dict[str, Any]]:
    if not spans or window[1] <= window[0] or loop_blend_s <= 0:
        raise ValueError("BAD_SCHEDULE_ARGUMENTS")
    if abs(nudge_s) > TARGET_PERIOD_S / 2.0 + 1e-8:
        raise ValueError("PHASE_NUDGE_EXCEEDS_HALF_PERIOD")
    overlap = int(round(loop_blend_s * fps))
    cursor = int(window[0])
    rows: list[dict[str, Any]] = []
    index = 0
    wrapped_advance_s = nudge_s % TARGET_PERIOD_S
    while cursor < window[1]:
        span = spans[index % len(spans)]
        source_in = float(span["source_in"])
        if not rows:
            source_in += wrapped_advance_s * float(span["play_rate"])
        source_out = float(span["source_out"])
        if source_in >= source_out - 0.1:
            raise ValueError("PHASE_ADVANCE_EXHAUSTS_SPAN")
        duration_frames = int(round((source_out - source_in) / float(span["play_rate"]) * fps))
        if duration_frames <= overlap * 2:
            raise ValueError("LOOP_TOO_SHORT_FOR_BLEND")
        end = min(window[1], cursor + duration_frames)
        rows.append({
            "scene_range": [cursor, end],
            "source_in": round(source_in, 6),
            "source_out_limit": source_out,
            "signal": span["signal"],
            "play_rate": round(float(span["play_rate"]), 8),
            "span_index": index % len(spans),
        })
        if end == window[1]:
            break
        cursor = end - overlap
        index += 1
        if len(rows) > 32:
            raise RuntimeError("SCHEDULE_DID_NOT_TERMINATE")
    for i, row in enumerate(rows):
        row["ease_in_frames"] = int(round((EASE_S if i == 0 else loop_blend_s) * fps))
        row["ease_out_frames"] = int(round((EASE_S if i == len(rows) - 1 else loop_blend_s) * fps))
    return rows


def _pcm_to_float(raw: bytes, width: int) -> np.ndarray:
    if width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if width == 3:
        data = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        values = data[:, 0].astype(np.int32) | (data[:, 1].astype(np.int32) << 8) | (data[:, 2].astype(np.int32) << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float64) / 8388608.0
    if width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"UNSUPPORTED_WAV_WIDTH|{width}")


def phrase_maxima(wav_path: Path, chorus: tuple[float, float] = CHORUS_AUDIO_S) -> dict[str, Any]:
    try:
        with wave.open(str(wav_path), "rb") as wav:
            rate, channels, width, count = wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
            raw = wav.readframes(count)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"WAV_READ_FAILED|{exc}") from exc
    samples = _pcm_to_float(raw, width)
    if channels < 1 or len(samples) % channels:
        raise ValueError("WAV_CHANNEL_LAYOUT")
    mono = samples.reshape(-1, channels).mean(axis=1)
    hop = max(1, int(round(rate * 0.05)))
    usable = len(mono) // hop * hop
    rms = np.sqrt(np.mean(mono[:usable].reshape(-1, hop) ** 2, axis=1) + 1e-12)
    times = (np.arange(len(rms)) + 0.5) * hop / float(rate)
    if not len(times) or times[-1] < chorus[1]:
        raise ValueError("CHORUS_WINDOW_NOT_IN_WAV")
    smooth_n = min(len(rms), max(3, int(round(1.4 / (hop / float(rate))))))
    if smooth_n < 3:
        raise ValueError("WAV_TOO_SHORT")
    kernel = np.hanning(smooth_n)
    kernel /= kernel.sum()
    envelope = np.convolve(rms, kernel, mode="same")
    mask = (times >= chorus[0]) & (times <= chorus[1])
    ct, ce = times[mask], envelope[mask]
    if len(ct) < 100:
        raise ValueError("CHORUS_WINDOW_NOT_IN_WAV")
    ce = (ce - ce.mean()) / (ce.std() + 1e-12)
    step_s = hop / float(rate)
    period_scores = []
    for candidate in np.arange(6.8, 7.6001, 0.02):
        shift = max(1, int(round(candidate / step_s)))
        corr = float(np.corrcoef(ce[:-shift], ce[shift:])[0, 1])
        period_scores.append((corr, float(candidate)))
    _, period = max(period_scores)
    best_phase: tuple[float, float] | None = None
    for phase_candidate in np.arange(0.0, period, 0.05):
        grid = np.arange(chorus[0] + phase_candidate, chorus[1] + 1e-6, period)
        if len(grid) < 7:
            continue
        score = float(np.mean(np.interp(grid, ct, ce)))
        if best_phase is None or score > best_phase[0]:
            best_phase = (score, float(phase_candidate))
    assert best_phase is not None
    phase = best_phase[1]
    predictions = np.arange(chorus[0] + phase, chorus[1] + 1e-6, period)
    maxima = []
    for predicted in predictions:
        local = (ct >= predicted - 1.0) & (ct <= predicted + 1.0)
        if not np.any(local):
            continue
        lt, le = ct[local], ce[local]
        maxima.append(float(lt[int(np.argmax(le))]))
    shift = max(1, int(round(period / step_s)))
    corr = float(np.corrcoef(ce[:-shift], ce[shift:])[0, 1]) if shift < len(ce) else 0.0
    return {
        "wav": str(wav_path).replace("\\", "/"), "sample_rate": rate, "channels": channels,
        "chorus_s": list(chorus), "period_s": round(period, 3), "autocorrelation": round(corr, 3),
        "maxima_s": [round(value, 3) for value in maxima],
        "method": "50 ms RMS, 1.4 s Hann smoothing, 6.8-7.6 s grid search, local +/-1 s refinement",
    }


def _preview_signal(figure: dict[str, Any], tracks: dict[str, Any], scene_times: np.ndarray) -> np.ndarray:
    values = np.zeros_like(scene_times)
    weights = np.zeros_like(scene_times)
    for row in figure["sections_scene"]:
        start, end = row["scene_range"]
        mask = (scene_times >= start / FPS) & (scene_times <= end / FPS)
        if not np.any(mask):
            continue
        local_frames = scene_times[mask] * FPS - start
        source_times = float(row["source_in"]) + local_frames / FPS * float(row["play_rate"])
        sample = sample_signal(tracks, row["signal"], source_times)
        weight = np.ones_like(sample)
        ease_in = int(row["ease_in_frames"])
        ease_out = int(row["ease_out_frames"])
        if ease_in:
            weight *= np.clip(local_frames / ease_in, 0.0, 1.0)
        if ease_out:
            weight *= np.clip((end - scene_times[mask] * FPS) / ease_out, 0.0, 1.0)
        values[mask] += sample * weight
        weights[mask] += weight
    good = weights > 1e-8
    values[good] /= weights[good]
    values[~good] = 0.0
    return values


def render_preview(plan: dict[str, Any], loaded_tracks: dict[str, dict[str, Any]]) -> bytes:
    width, height = 1800, 1180
    image = Image.new("RGB", (width, height), "#11151b")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    left, right, top = 180, 60, 100
    panel_h, gap = 145, 20
    w0, w1 = plan["window_scene_frames"]
    times = np.arange(w0 / FPS, w1 / FPS + 0.5 / FPS, 1.0 / FPS)
    draw.text((35, 24), "P20 - S3 chorus sway together (offline curve preview)", fill="#f5f7fa", font=font)
    draw.text((35, 48), "3.6 s sway grid (blue) | refined phrase maxima (gold) | 1.5 s section ease", fill="#aeb9c8", font=font)
    plot_w = width - left - right
    x_of = lambda seconds: left + int((seconds - w0 / FPS) / ((w1 - w0) / FPS) * plot_w)
    phrase = [value for value in plan["phrase"]["maxima_s"] if w0 / FPS <= value <= w1 / FPS]
    for idx, figure in enumerate(plan["figures"]):
        y0 = top + idx * (panel_h + gap)
        draw.rectangle((left, y0, width - right, y0 + panel_h), fill="#171e27", outline="#344052")
        for grid in np.arange(w0 / FPS, w1 / FPS + 0.01, TARGET_PERIOD_S):
            x = x_of(float(grid)); draw.line((x, y0, x, y0 + panel_h), fill="#294f72", width=1)
        for maximum in phrase:
            x = x_of(maximum); draw.line((x, y0, x, y0 + panel_h), fill="#aa7a24", width=2)
        signal = _preview_signal(figure, loaded_tracks[figure["id"]], times)
        lo, hi = np.percentile(signal, [2, 98])
        scale = max(float(hi - lo), 1e-6)
        normalized = np.clip((signal - (lo + hi) / 2.0) / scale, -0.6, 0.6)
        points = [(x_of(float(t)), int(y0 + panel_h / 2 - v * panel_h * 0.72)) for t, v in zip(times, normalized)]
        draw.line(points, fill="#70d6c3", width=3)
        draw.line((left, y0 + panel_h // 2, width - right, y0 + panel_h // 2), fill="#3c4654", width=1)
        draw.text((25, y0 + 10), figure["id"], fill="#f5f7fa", font=font)
        draw.text((25, y0 + 32), f"phase {figure['phase_at_window_start_deg']:.1f} deg", fill="#aeb9c8", font=font)
        draw.text((25, y0 + 50), f"nudge {figure['default_phase_nudge_s']:+.3f} s", fill="#aeb9c8", font=font)
        draw.text((25, y0 + 68), f"rate {figure['spans'][0]['play_rate']:.3f}", fill="#aeb9c8", font=font)
    for second in range(int(w0 / FPS), int(w1 / FPS) + 1, 5):
        x = x_of(second)
        draw.text((x - 12, height - 46), f"{second // 60}:{second % 60:02d}", fill="#b9c2cf", font=font)
    with tempfile.SpooledTemporaryFile() as handle:
        image.save(handle, format="PNG", optimize=True)
        handle.seek(0)
        return handle.read()


def build_plan(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    source_root = Path(args.source_root)
    seg_path = source_root / "DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json"
    sway_path = source_root / "DerivedAssets/S3MocapIntensity/s3_sway_runs.json"
    wav_path = source_root / "DerivedAssets/Audio/Scenes_20261006/S03_Shore_People_Stereo.wav"
    segments = json.loads(seg_path.read_text(encoding="utf-8"))
    sway = json.loads(sway_path.read_text(encoding="utf-8"))
    source_by_id = {row["id"]: Path(row["source_path"]) for row in segments["figures"]}
    loaded_tracks: dict[str, dict[str, Any]] = {}
    figures = []
    local_window = (args.window_start + SCENE_TO_CLAMS, args.window_end + SCENE_TO_CLAMS)
    for index, spec in enumerate(FIGURES):
        if spec["id"] not in source_by_id:
            raise ValueError(f"FIGURE_MISSING_FROM_SEGMENTS|{spec['id']}")
        tracks, _ = intensity.load_animation_tracks(source_by_id[spec["id"]])
        loaded_tracks[spec["id"]] = tracks
        spans = [selected_run(sway, spec["id"], bounds) for bounds in spec["spans"]]
        base_phase, r2 = fitted_phase(tracks, spans[0])
        target_phase = index * 360.0 / len(FIGURES)
        nudge = signed_phase_nudge(base_phase, target_phase, args.target_period)
        sections_local = build_schedule(local_window, FPS, spans, nudge, args.loop_blend)
        sections_scene = []
        for row in sections_local:
            converted = dict(row)
            converted["scene_range"] = [row["scene_range"][0] - SCENE_TO_CLAMS,
                                        row["scene_range"][1] - SCENE_TO_CLAMS]
            sections_scene.append(converted)
        figures.append({
            "id": spec["id"], "animation": spec["animation"],
            "source_fbx": str(source_by_id[spec["id"]]).replace("\\", "/"),
            "source_sha256": sha256_file(source_by_id[spec["id"]]),
            "spans": spans, "phase_fit_r2": round(r2, 4), "base_phase_deg": round(base_phase, 3),
            "target_phase_deg": round(target_phase, 3), "default_phase_nudge_s": round(nudge, 6),
            "phase_at_window_start_deg": round((base_phase + nudge / args.target_period * 360.0) % 360.0, 3),
            "sections_ls_clams": sections_local, "sections_scene": sections_scene,
        })
    plan = {
        "schema": "p20_chorus_sway/1", "run": args.run,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "evidence_tier": "measured curves/audio; phase and staging interpretation inferred",
        "sequence": "/Game/Scenes/LS_Clams", "scene_sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03",
        "window_scene_frames": [args.window_start, args.window_end], "window_ls_clams_frames": list(local_window),
        "fps": FPS, "scene_to_ls_clams_frames": SCENE_TO_CLAMS,
        "target_period_s": args.target_period, "ease_seconds": args.ease,
        "loop_blend_seconds": args.loop_blend,
        "phase_definition": "degrees of least-squares fitted dominant sinusoid; 0 degrees is fitted signal maximum",
        "inputs": {
            "segments": str(seg_path).replace("\\", "/"), "segments_sha256": sha256_file(seg_path),
            "sway": str(sway_path).replace("\\", "/"), "sway_sha256": sha256_file(sway_path),
            "wav": str(wav_path).replace("\\", "/"), "wav_sha256": sha256_file(wav_path),
        },
        "phrase": phrase_maxima(wav_path), "figures": figures,
        "extra_crowd": {"count": args.extra_crowd_count, "mode": "DESIGN_ONLY",
                        "apply_supported": False, "full_character_cost_units_each": 1.0},
    }
    return plan, loaded_tracks


def make_backup(project_root: Path, run: str, outputs: dict[str, Path]) -> Path:
    backup = project_root / f"Backups/PreS3ChorusSwayPlan-{run}"
    if backup.exists():
        raise RuntimeError(f"BACKUP_EXISTS|{backup}")
    backup.mkdir(parents=True)
    manifest = {"run": run, "outputs": []}
    for key, path in outputs.items():
        row = {"key": key, "target": path.relative_to(project_root).as_posix(), "existed": path.is_file()}
        if path.is_file():
            saved = backup / row["target"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
            row["backup_file"] = saved.relative_to(project_root).as_posix()
            row["sha256_before"] = sha256_file(path)
        manifest["outputs"].append(row)
    _atomic_write(backup / "backup_manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    return backup


def apply(args: argparse.Namespace, plan: dict[str, Any], tracks: dict[str, dict[str, Any]]) -> None:
    if args.confirm != "APPLY S3CHORUSSWAYPLAN":
        raise RuntimeError("CONFIRM_REQUIRED|APPLY S3CHORUSSWAYPLAN")
    root = Path(args.project_root).resolve()
    outputs = output_paths(root)
    backup = make_backup(root, args.run, outputs)
    plan["backup"] = backup.relative_to(root).as_posix()
    png = render_preview(plan, tracks)
    plan["preview_sha256"] = hashlib.sha256(png).hexdigest()
    _atomic_write(outputs["preview"], png)
    _atomic_write(outputs["plan"], (json.dumps(plan, indent=2) + "\n").encode("utf-8"))
    readback = json.loads(outputs["plan"].read_text(encoding="utf-8"))
    if readback["run"] != args.run or sha256_file(outputs["preview"]) != plan["preview_sha256"]:
        raise RuntimeError("OUTPUT_READBACK_FAILED")
    print(f"S3_CHORUS_SWAY_PLAN_APPLY_OK|run={args.run}|figures=6|preview={outputs['preview']}|backup={backup}")


def revert(args: argparse.Namespace) -> None:
    if args.confirm != "REVERT S3CHORUSSWAYPLAN":
        raise RuntimeError("CONFIRM_REQUIRED|REVERT S3CHORUSSWAYPLAN")
    root = Path(args.project_root).resolve()
    outputs = output_paths(root)
    if not outputs["plan"].is_file():
        raise RuntimeError("PLAN_RECORD_MISSING")
    plan = json.loads(outputs["plan"].read_text(encoding="utf-8"))
    if args.run and plan["run"] != args.run:
        raise RuntimeError("RUN_MISMATCH")
    backup = root / plan["backup"]
    manifest = json.loads((backup / "backup_manifest.json").read_text(encoding="utf-8"))
    parked = backup / "reverted_outputs"
    parked.mkdir(exist_ok=True)
    for row in manifest["outputs"]:
        target = root / row["target"]
        if row["existed"]:
            shutil.copy2(root / row["backup_file"], target)
            if sha256_file(target) != row["sha256_before"]:
                raise RuntimeError(f"REVERT_READBACK_FAILED|{target}")
        elif target.exists():
            destination = parked / row["target"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(destination))
    print(f"S3_CHORUS_SWAY_PLAN_REVERT_OK|run={plan['run']}|parked={parked}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    p.add_argument("--confirm", default="")
    p.add_argument("--run", default="P20-UNSET")
    p.add_argument("--project-root", default=str(HERE.parents[1]))
    p.add_argument("--source-root", default="E:/PussStage")
    p.add_argument("--window-start", type=int, default=WINDOW_SCENE[0])
    p.add_argument("--window-end", type=int, default=WINDOW_SCENE[1])
    p.add_argument("--target-period", type=float, default=TARGET_PERIOD_S)
    p.add_argument("--ease", type=float, default=EASE_S)
    p.add_argument("--loop-blend", type=float, default=LOOP_BLEND_S)
    p.add_argument("--extra-crowd-count", type=int, default=0)
    return p


def validate_args(args: argparse.Namespace) -> None:
    if args.window_end <= args.window_start or args.target_period <= 0 or args.ease <= 0 or args.loop_blend <= 0:
        raise ValueError("POSITIVE_WINDOW_AND_TIMING_REQUIRED")
    if args.extra_crowd_count < 0:
        raise ValueError("EXTRA_CROWD_COUNT_NEGATIVE")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_args(args)
    if args.mode == "REVERT":
        revert(args)
        return 0
    plan, tracks = build_plan(args)
    if args.mode == "DRY":
        maxima = ",".join(f"{value:.3f}" for value in plan["phrase"]["maxima_s"])
        print(f"S3_CHORUS_SWAY_PLAN_DRY_OK|run={args.run}|figures=6|writes=0|phrase_period={plan['phrase']['period_s']:.3f}|maxima={maxima}")
        for figure in plan["figures"]:
            rates = ",".join(f"{span['play_rate']:.4f}" for span in figure["spans"])
            print(f"{figure['id']}|phase={figure['base_phase_deg']:.2f}|target={figure['target_phase_deg']:.2f}|nudge={figure['default_phase_nudge_s']:+.3f}|rates={rates}|sections={len(figure['sections_ls_clams'])}")
        return 0
    apply(args, plan, tracks)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"S3_CHORUS_SWAY_PLAN_FAILED|{type(exc).__name__}|{str(exc).replace(chr(10), ' ')}", file=sys.stderr)
        raise
