#!/usr/bin/env python3
"""Offline P11 music analysis and DRY-only Passage timing planner.

Analysis APPLY writes derived JSON/PNG files only. It never imports Unreal and
refuses to write inside E:/PussStage. Timing planning is DRY-only by design.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import math
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np


ANALYSIS_CONFIRM = {"DRY": "DRY MUSIC ANALYSIS", "APPLY": "APPLY MUSIC ANALYSIS", "REVERT": "REVERT MUSIC ANALYSIS"}
PLAN_CONFIRM = "DRY TIMING PLAN"
OUTPUT_NAMES = ("Opening", "P01", "P02", "P03", "P04", "P05", "P06")


class Refused(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_base_analyzer() -> Any:
    path = repo_root() / "Tools" / "InfinityStage" / "music_analysis.py"
    spec = importlib.util.spec_from_file_location("infinity_music_analysis", path)
    if spec is None or spec.loader is None:
        raise Refused(f"BASE_ANALYZER_UNAVAILABLE|{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def moving_average(values: np.ndarray, width: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if width <= 1 or values.size == 0:
        return values.copy()
    padded = np.pad(values, (width // 2, width - 1 - width // 2), mode="edge")
    return np.convolve(padded, np.ones(width, dtype=np.float64) / width, mode="valid")


def rms_at_fps(samples: np.ndarray, sample_rate: int, fps: int = 25) -> np.ndarray:
    count = int(math.ceil(samples.size * fps / sample_rate))
    out = np.zeros(count, dtype=np.float64)
    for frame in range(count):
        start = int(round(frame * sample_rate / fps))
        end = min(samples.size, int(round((frame + 1) * sample_rate / fps)))
        block = samples[start:max(start + 1, end)]
        out[frame] = math.sqrt(float(np.mean(block.astype(np.float64) ** 2)) + 1e-12)
    return out


def robust_unit(values: np.ndarray, low: float = 10.0, high: float = 95.0) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    lo, hi = np.percentile(values, [low, high]) if values.size else (0.0, 1.0)
    return np.clip((values - lo) / max(float(hi - lo), 1e-9), 0.0, 1.0)


def detect_flurries(rms: np.ndarray, fps: int, *, min_gap_s: float, rise_window_s: float,
                    slow_window_s: float, threshold: float, max_count: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Detect phrase-scale energy rises, keeping strongest separated peaks."""
    energy = robust_unit(20.0 * np.log10(np.maximum(rms, 1e-8)))
    fast = moving_average(energy, max(1, int(round(rise_window_s * fps))))
    slow = moving_average(energy, max(3, int(round(slow_window_s * fps))))
    rise = np.clip(fast - slow, 0.0, None)
    score = robust_unit(rise, 35.0, 98.0) * (0.55 + 0.45 * fast)
    local = np.flatnonzero((score[1:-1] > score[:-2]) & (score[1:-1] >= score[2:])) + 1
    local = [int(i) for i in local if score[i] >= threshold and fast[i] >= 0.18]
    gap = max(1, int(round(min_gap_s * fps)))
    selected: list[int] = []
    for index in sorted(local, key=lambda i: (float(score[i]), float(fast[i])), reverse=True):
        if all(abs(index - other) >= gap for other in selected):
            selected.append(index)
            if len(selected) >= max_count:
                break
    selected.sort()
    flurries: list[dict[str, Any]] = []
    for number, peak in enumerate(selected, 1):
        start = peak
        while start > 0 and peak - start < int(2.5 * fps) and (rise[start] > 0.025 or fast[start] > fast[peak] * 0.65):
            start -= 1
        end = peak
        while end + 1 < rms.size and end - peak < int(3.5 * fps) and (rise[end] > 0.015 or fast[end] > fast[peak] * 0.72):
            end += 1
        flurries.append({
            "number": number,
            "startSeconds": round(start / fps, 3),
            "peakSeconds": round(peak / fps, 3),
            "endSeconds": round(min((end + 1) / fps, rms.size / fps), 3),
            "strength": round(float(score[peak]), 4),
            "peakEnergy": round(float(fast[peak]), 4),
            "state": "Suggested"
        })
    return fast, flurries


def normalize_tempo_and_beats(tempos: list[dict[str, Any]], beats: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fold numerical edge candidates into the declared 40-220 BPM range."""
    normalized: list[dict[str, Any]] = []
    primary_divisor = 1
    for index, candidate in enumerate(tempos):
        bpm = float(candidate["bpm"])
        divisor = 1
        while bpm > 220.0:
            bpm /= 2.0
            divisor *= 2
        while bpm < 40.0:
            bpm *= 2.0
        if index == 0:
            primary_divisor = divisor
        if any(abs(math.log2(bpm / float(existing["bpm"]))) < 0.02 for existing in normalized):
            continue
        normalized.append({"bpm": round(bpm, 3), "confidence": candidate["confidence"], "rank": len(normalized)+1})
    return normalized, beats[::primary_divisor]


def validate_manifest(manifest: dict[str, Any]) -> None:
    tracks = manifest.get("tracks")
    if not isinstance(tracks, list) or [t.get("segment") for t in tracks] != list(OUTPUT_NAMES):
        raise Refused("MANIFEST_SEGMENTS|expected Opening,P01-P06 in order")
    files = [str(t.get("file", "")).lower() for t in tracks]
    if len(set(files)) != len(files):
        raise Refused("MANIFEST_DUPLICATE_SOURCE")
    for track in tracks:
        start = float(track.get("selectedStartSeconds", 0.0))
        end = float(track.get("selectedEndSeconds", 0.0))
        if start < 0.0 or end <= start:
            raise Refused(f"MANIFEST_RANGE|{track.get('segment')}|{start}|{end}")


def resolve_source_root(manifest: dict[str, Any], override: Path | None) -> Path:
    return (override or Path(str(manifest["sourceRoot"]))).resolve()


def analyze_track(track: dict[str, Any], source_root: Path, settings: dict[str, Any], base: Any) -> dict[str, Any]:
    source = (source_root / str(track["file"])).resolve()
    if not source.is_file():
        raise Refused(f"SOURCE_MISSING|{track['segment']}|{source}")
    actual_hash = sha256(source)
    if actual_hash != track["sha256"]:
        raise Refused(f"SOURCE_HASH|{track['segment']}|expected={track['sha256']}|actual={actual_hash}")
    samples, rate, wav = base.decode_mono(source)
    start_s, end_s = float(track["selectedStartSeconds"]), float(track["selectedEndSeconds"])
    if end_s > wav.duration_seconds + 1e-4:
        raise Refused(f"SELECTION_PAST_SOURCE|{track['segment']}|{end_s:.6f}>{wav.duration_seconds:.6f}")
    start = int(round(start_s * rate))
    end = min(samples.size, int(round(end_s * rate)))
    selected = np.asarray(samples[start:end], dtype=np.float32)
    base_result = base.analyze_samples(selected, rate, source_name=source.name)
    rms = rms_at_fps(selected, rate, 25)
    envelope, flurries = detect_flurries(
        rms, 25,
        min_gap_s=float(settings["flurryMinGapSeconds"]),
        rise_window_s=float(settings["flurryRiseWindowSeconds"]),
        slow_window_s=float(settings["flurryBaselineSeconds"]),
        threshold=float(settings["flurryThreshold"]),
        max_count=int(settings["flurryMaxCount"]),
    )
    duration = selected.size / rate
    tempos, beats = normalize_tempo_and_beats(base_result["tempoCandidates"], base_result["beatProposals"])
    return {
        "schema": "PussStage.P11MusicAnalysis.v1",
        "segment": track["segment"],
        "durationSeconds": round(duration, 6),
        "source": {
            "path": str(source), "sha256": actual_hash,
            "sourceDurationSeconds": round(wav.duration_seconds, 6),
            "selectedStartSeconds": start_s, "selectedEndSeconds": end_s,
            "selectionNote": track.get("selectionNote", "Full declared music interval")
        },
        "tempoCandidates": tempos,
        "beatGrid": beats,
        "onsets": base_result["onsetProposals"],
        "rmsEnvelope25Fps": {
            "rateHz": 25,
            "linear": [round(float(v), 6) for v in rms],
            "dbfs": [round(float(v), 3) for v in 20.0 * np.log10(np.maximum(rms, 1e-8))]
        },
        "sections": base_result["expressiveSections"],
        "flurries": flurries,
        "waveform": base_result["waveform"],
        "previewEnvelope": [round(float(v), 5) for v in envelope],
        "analysis": {
            "baseAnalyzer": base_result["analyzer"],
            "parameters": settings,
            "tempoBeatOnsetState": "Suggested",
            "sectionState": "Suggested",
            "flurryState": "Suggested",
            "artistApprovalRequired": True
        }
    }


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, image: np.ndarray) -> None:
    height, width, channels = image.shape
    if channels != 3 or image.dtype != np.uint8:
        raise ValueError("RGB uint8 image required")
    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(height))
    payload = b"\x89PNG\r\n\x1a\n"
    payload += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def draw_line(canvas: np.ndarray, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], width: int = 1) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for x, y in zip(np.rint(np.linspace(x0, x1, steps + 1)).astype(int), np.rint(np.linspace(y0, y1, steps + 1)).astype(int)):
        canvas[max(0, y-width):min(canvas.shape[0], y+width+1), max(0, x-width):min(canvas.shape[1], x+width+1)] = color


DIGITS = {
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"), "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"), "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"), "9": ("111", "101", "111", "001", "111")
}


def draw_number(canvas: np.ndarray, value: int, x: int, y: int, color: tuple[int, int, int], scale: int = 4) -> None:
    for char in str(value):
        for row, bits in enumerate(DIGITS[char]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    canvas[y+row*scale:y+(row+1)*scale, x+col*scale:x+(col+1)*scale] = color
        x += 4 * scale


def render_preview(result: dict[str, Any], output: Path) -> None:
    width, height = 1600, 720
    left, right, top, bottom = 70, 35, 55, 55
    plot_w, plot_h = width-left-right, height-top-bottom
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (14, 18, 25)
    duration = float(result["durationSeconds"])
    for flurry in result["flurries"]:
        x0 = left + int(plot_w * flurry["startSeconds"] / duration)
        x1 = left + int(plot_w * flurry["endSeconds"] / duration)
        image[top:top+plot_h, x0:max(x0+1, x1)] = (39, 31, 58)
        xp = left + int(plot_w * flurry["peakSeconds"] / duration)
        draw_line(image, xp, top, xp, top+plot_h, (236, 115, 255), 1)
        image[top+8:top+38, max(left, xp-16):min(width-right, xp+20)] = (82, 42, 105)
        draw_number(image, int(flurry["number"]), max(left+2, xp-10), top+13, (255, 238, 255), 3)
    for n in range(5):
        x = left + int(plot_w*n/4)
        draw_line(image, x, top, x, top+plot_h, (43, 51, 64))
    mid = top + int(plot_h*0.36)
    waveform = result["waveform"]
    amp = plot_h*0.28
    for i, item in enumerate(waveform):
        x = left + int(plot_w*i/max(1, len(waveform)-1))
        y0 = int(mid-item["max"]*amp)
        y1 = int(mid-item["min"]*amp)
        image[max(top, y0):min(top+plot_h, y1+1), x:x+1] = (76, 157, 255)
    env = np.asarray(result["previewEnvelope"], dtype=float)
    base_y = top + int(plot_h*0.92)
    env_h = int(plot_h*0.38)
    last = None
    for i, value in enumerate(env):
        x = left + int(plot_w*i/max(1, env.size-1))
        y = base_y-int(value*env_h)
        if last is not None:
            draw_line(image, last[0], last[1], x, y, (91, 231, 174), 2)
        last = (x, y)
    draw_line(image, left, top+plot_h, left+plot_w, top+plot_h, (121, 137, 158))
    write_png(output, image)


def analysis_settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "flurryMinGapSeconds": args.flurry_min_gap,
        "flurryRiseWindowSeconds": args.flurry_rise_window,
        "flurryBaselineSeconds": args.flurry_baseline,
        "flurryThreshold": args.flurry_threshold,
        "flurryMaxCount": args.flurry_max_count
    }


def guard_output(output: Path) -> None:
    resolved = str(output.resolve()).replace("\\", "/").lower().rstrip("/")
    if resolved == "e:/pussstage" or resolved.startswith("e:/pussstage/"):
        raise Refused(f"MAIN_TREE_WRITE_REFUSED|{output}")


def revert_analysis_record(record_path: Path, run_id: str, backup_root: Path | None = None) -> dict[str, Any]:
    if not run_id:
        raise Refused("RUN_ID_REQUIRED")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("mode") != "APPLY":
        raise Refused("REVERT_RECORD_MODE")
    output = Path(record["output"]).resolve()
    original_backup = Path(record["backup"]).resolve()
    guard_output(output)
    if not original_backup.is_dir():
        raise Refused(f"REVERT_BACKUP_MISSING|{original_backup}")
    pre_revert = (backup_root or (repo_root()/"Backups")) / f"PreMusicAnalysisRevert-{run_id}"
    if pre_revert.exists():
        raise Refused(f"BACKUP_EXISTS|{pre_revert}")
    pre_revert.mkdir(parents=True)
    moved = []
    if output.exists():
        for path in list(output.iterdir()):
            if path.is_file():
                shutil.move(str(path), str(pre_revert/path.name))
                moved.append(path.name)
    output.mkdir(parents=True, exist_ok=True)
    restored = []
    for name in record.get("oldFiles", []):
        source = original_backup/name
        if not source.is_file():
            raise Refused(f"REVERT_OLD_FILE_MISSING|{name}")
        shutil.copy2(source, output/name)
        restored.append(name)
    (pre_revert/"revert-manifest.json").write_text(json.dumps({"run": run_id, "record": str(record_path), "moved": moved, "restored": restored}, indent=2), encoding="utf-8")
    return {"mode": "REVERT", "run": run_id, "record": str(record_path), "preRevertBackup": str(pre_revert), "moved": moved, "restored": restored, "marker": f"P11_MUSIC_ANALYSIS_REVERT_OK|run={run_id}|restored={len(restored)}|recovery={pre_revert}"}


def apply_analysis(args: argparse.Namespace) -> dict[str, Any]:
    mode = args.mode.upper()
    if args.confirm != ANALYSIS_CONFIRM[mode]:
        raise Refused(f"CONFIRM|expected={ANALYSIS_CONFIRM[mode]!r}")
    if mode == "REVERT":
        if not args.record:
            raise Refused("REVERT_REQUIRES_RECORD")
        return revert_analysis_record(args.record, args.run_id)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    output = args.output_dir.resolve()
    guard_output(output)
    source_root = resolve_source_root(manifest, args.source_root)
    settings = analysis_settings(args)
    base = load_base_analyzer()
    results = [analyze_track(track, source_root, settings, base) for track in manifest["tracks"]]
    if mode == "DRY":
        return {"mode": mode, "run": args.run_id, "tracks": [{"segment": r["segment"], "durationSeconds": r["durationSeconds"], "flurries": len(r["flurries"])} for r in results], "writes": []}
    if not args.run_id:
        raise Refused("RUN_ID_REQUIRED")
    backup = repo_root() / "Backups" / f"PreMusicAnalysis-{args.run_id}"
    if backup.exists():
        raise Refused(f"BACKUP_EXISTS|{backup}")
    backup.mkdir(parents=True)
    old_files = []
    if output.exists():
        for path in output.iterdir():
            if path.is_file():
                shutil.copy2(path, backup / path.name)
                old_files.append(path.name)
    (backup / "manifest.json").write_text(json.dumps({"run": args.run_id, "output": str(output), "oldFiles": old_files}, indent=2), encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for result in results:
        result["runId"] = args.run_id
        json_path = output / f"{result['segment']}.json"
        png_path = output / f"{result['segment']}.png"
        json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        render_preview(result, png_path)
        written += [json_path.name, png_path.name]
    bundle = {
        "schema": "PussStage.P11MusicAnalysisBundle.v1", "runId": args.run_id,
        "tracks": [{"segment": r["segment"], "durationSeconds": r["durationSeconds"], "json": f"{r['segment']}.json", "png": f"{r['segment']}.png", "flurryCount": len(r["flurries"])} for r in results],
        "unrealDirtyPackagesBefore": "not-applicable-offline", "unrealDirtyPackagesAfter": "not-applicable-offline",
        "unrealPackagesSaved": [], "cueScoreMutated": False
    }
    (output / "manifest.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    written.append("manifest.json")
    record = {"run": args.run_id, "backup": str(backup), "output": str(output), "oldFiles": old_files, "written": written, "mode": "APPLY", "scope": "derived analysis files only"}
    record_path = output / f"record-{args.run_id}.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"mode": mode, "run": args.run_id, "backup": str(backup), "record": str(record_path), "written": written, "marker": f"P11_MUSIC_ANALYSIS_APPLY_OK|run={args.run_id}|tracks={len(results)}|dirty_packages=NA|cue_score_mutated=0"}


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    segments = snapshot.get("segments", [])
    if len(segments) != 19:
        raise Refused(f"SEGMENT_COUNT|{len(segments)}")
    for index, row in enumerate(segments):
        if len(row) != 3 or int(row[2]) <= int(row[1]):
            raise Refused(f"SEGMENT_RANGE|{index}|{row}")
        if index and int(row[1]) != int(segments[index-1][2]):
            raise Refused(f"SEGMENT_GAP|{segments[index-1][0]}->{row[0]}")
    for number in range(1, 7):
        if f"Passage {number}" not in snapshot.get("musicSeconds", {}):
            raise Refused(f"MUSIC_MISSING|Passage {number}")


def make_timing_plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    tick, fps = int(snapshot["tickRate"]), int(snapshot["displayRate"])
    ticks_per_frame = tick // fps
    if tick % fps:
        raise Refused("NON_INTEGRAL_TICKS_PER_FRAME")
    deltas: dict[str, int] = {}
    passages: dict[str, dict[str, Any]] = {}
    for label, start, end in snapshot["segments"]:
        if not label.startswith("Passage "):
            continue
        music_s = float(snapshot["musicSeconds"][label])
        target_frames = int(math.ceil(music_s * fps - 1e-9))
        target_ticks = target_frames * ticks_per_frame
        delta = target_ticks - (int(end)-int(start))
        deltas[label] = delta
        passages[label] = {"oldTicks": int(end)-int(start), "oldSeconds": (int(end)-int(start))/tick, "musicSeconds": music_s, "targetFrames": target_frames, "targetTicks": target_ticks, "targetSeconds": target_ticks/tick, "deltaTicks": delta, "deltaSeconds": delta/tick}
    shifts = []
    cumulative = 0
    old_by_label = {str(r[0]): (int(r[1]), int(r[2])) for r in snapshot["segments"]}
    for label, start, end in snapshot["segments"]:
        start_shift = cumulative
        if label in deltas:
            cumulative += deltas[label]
        end_shift = cumulative
        if start_shift or end_shift:
            shifts.append({"segment": label, "startShiftTicks": start_shift, "endShiftTicks": end_shift, "startShiftSeconds": start_shift/tick, "endShiftSeconds": end_shift/tick, "newStart": int(start)+start_shift, "newEnd": int(end)+end_shift})
    late = []
    for row in snapshot.get("keyedTracks", []):
        passage = row["passage"]
        old_start, _old_end = old_by_label[passage]
        new_end_in_old_coordinates = old_start + passages[passage]["targetTicks"]
        bad = [int(value) for value in row["absoluteTicks"] if int(value) >= new_end_in_old_coordinates]
        if bad:
            late.append({"passage": passage, "track": row["track"], "keysAtOrPastNewEnd": bad, "newEndInOldCoordinates": new_end_in_old_coordinates})
    return {"mode": "DRY", "rounding": "ceil to the next 25 fps display frame", "passages": passages, "tracksPastNewEnd": late, "downstreamSectionsMoved": shifts, "totalDeltaTicks": cumulative, "totalDeltaSeconds": cumulative/tick, "oldShowEnd": int(snapshot["segments"][-1][2]), "newShowEnd": int(snapshot["segments"][-1][2])+cumulative, "evidence": snapshot.get("evidence", {}), "applyPath": "DESIGN ONLY: resolve late keys; scale Passage timing fields; rebuild managed Master once; prove relative key carry; exact-save Show and Master only; reload/read back; never Save All."}


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode != "DRY":
        raise Refused("TIMING_PLAN_IS_DRY_ONLY|APPLY and REVERT are intentionally unavailable")
    if args.confirm != PLAN_CONFIRM:
        raise Refused(f"CONFIRM|expected={PLAN_CONFIRM!r}")
    return make_timing_plan(json.loads(args.snapshot.read_text(encoding="utf-8")))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    analysis = sub.add_parser("analysis")
    analysis.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    analysis.add_argument("--confirm", required=True)
    analysis.add_argument("--run-id")
    analysis.add_argument("--record", type=Path, help="APPLY record to revert; required for REVERT.")
    analysis.add_argument("--manifest", type=Path, default=Path(__file__).with_name("p11_sources.json"))
    analysis.add_argument("--source-root", type=Path)
    analysis.add_argument("--output-dir", type=Path, default=repo_root()/"DerivedAssets"/"MusicAnalysis")
    analysis.add_argument("--flurry-min-gap", type=float, default=6.0)
    analysis.add_argument("--flurry-rise-window", type=float, default=0.8)
    analysis.add_argument("--flurry-baseline", type=float, default=3.0)
    analysis.add_argument("--flurry-threshold", type=float, default=0.50)
    analysis.add_argument("--flurry-max-count", type=int, default=3)
    plan = sub.add_parser("plan")
    plan.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    plan.add_argument("--confirm", required=True)
    plan.add_argument("--snapshot", type=Path, default=Path(__file__).with_name("p11_timing_snapshot.json"))
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = apply_analysis(args) if args.command == "analysis" else run_plan(args)
    except (Refused, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P11_MUSIC_TIMING_STOPPED|{exc}")
        return 2
    print(json.dumps(result, indent=2))
    if args.command == "plan":
        print(f"P11_TIMING_PLAN_DRY_OK|passages=6|late_tracks={len(result['tracksPastNewEnd'])}|downstream={len(result['downstreamSectionsMoved'])}")
    elif result.get("marker"):
        print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
