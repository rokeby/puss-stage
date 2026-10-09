#!/usr/bin/env python3
"""Offline authored-breath / tape-stop WAV renderer.

The renderer never touches Content/.  All creative timing values come from an
args JSON file.  Modes are deliberately explicit:

  python Tools/Breath/breath_audio.py --args <args.json>   # mode in JSON

DRY renders and validates in memory but writes nothing.  APPLY requires
``APPLY_BREATH_AUDIO:<run_id>`` and creates
``Backups/PreBreathAudio-<run_id>`` (including a pre-apply record) before it
writes the named WAV/PNG outputs.  REVERT requires
``REVERT_BREATH_AUDIO:<source_run_id>``; it moves the applied bytes into a
recoverable revert backup before restoring the pre-apply bytes.

T is the source time at which the wind-down starts.  The wind-down advances to
an integer source sample using an exponential-ish rate curve from 1 to 0,
silence is inserted, an optional mirrored wind-up advances from that same stop
sample, and unity-rate playback then continues.  The exact source advancement
and output-length delta are recorded in samples and seconds.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import zlib

import numpy as np
from scipy import signal
import soundfile as sf


TOOL = "breath_audio"
RUN_RE = re.compile(r"BAUDIO-[A-Za-z0-9_-]+$")
APPLY_PREFIX = "APPLY_BREATH_AUDIO:"
REVERT_PREFIX = "REVERT_BREATH_AUDIO:"
DEFAULT_WIND_DOWN_SECONDS = 2.5
DEFAULT_WIND_UP_SECONDS = 0.0
DEFAULT_CURVE_SHAPE = 4.5
DEFAULT_FADE_MS = 8.0
DEFAULT_JOIN_SEARCH_MS = 25.0


class BreathAudioError(RuntimeError):
    """A fail-closed validation or recovery error."""


def _utc_stamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _jsonable(value):
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_state(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "size": 0, "sha256": None}
    if not path.is_file():
        raise BreathAudioError("TARGET_NOT_FILE:%s" % path)
    return {"exists": True, "size": path.stat().st_size, "sha256": _sha256(path)}


def _write_json_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(_jsonable(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(_jsonable(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp, path)


def _resolve(root: Path, value: str, label: str) -> Path:
    if not value:
        raise BreathAudioError("MISSING_PATH:%s" % label)
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_output_path(path: Path, project_root: Path, label: str) -> None:
    if not _is_within(path, project_root):
        raise BreathAudioError("OUTPUT_OUTSIDE_PROJECT:%s:%s" % (label, path))
    content = (project_root / "Content").resolve()
    if path == content or _is_within(path, content):
        raise BreathAudioError("CONTENT_WRITE_REFUSED:%s:%s" % (label, path))


def load_args(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise BreathAudioError("ARGS_MUST_BE_OBJECT")
    return raw


def resolve_apply_config(raw: dict, args_path: Path | None = None) -> dict:
    root_value = raw.get("project_root") or (args_path.parent if args_path else Path.cwd())
    project_root = Path(root_value).resolve()
    run_id = str(raw.get("run_id") or ("BAUDIO-" + _utc_stamp()))
    if RUN_RE.fullmatch(run_id) is None:
        raise BreathAudioError("BAD_RUN_ID:%s" % run_id)
    mode = str(raw.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY"):
        raise BreathAudioError("MODE_REQUIRED:DRY|APPLY")

    run_dir = _resolve(project_root, str(raw.get("run_dir") or ("Saved/CodexBreath/" + run_id)), "run_dir")
    output = _resolve(project_root, str(raw.get("output_wav") or (run_dir / "breath.wav")), "output_wav")
    waveform = _resolve(
        project_root,
        str(raw.get("waveform_preview_png") or (run_dir / "breath_waveform.png")),
        "waveform_preview_png",
    )
    spectrogram = _resolve(
        project_root,
        str(raw.get("spectrogram_preview_png") or (run_dir / "breath_spectrogram.png")),
        "spectrogram_preview_png",
    )
    record = _resolve(project_root, str(raw.get("record_json") or (run_dir / "apply_record.json")), "record_json")
    source = _resolve(project_root, str(raw.get("input_wav") or ""), "input_wav")
    for label, path in (
        ("output_wav", output),
        ("waveform_preview_png", waveform),
        ("spectrogram_preview_png", spectrogram),
        ("record_json", record),
    ):
        _validate_output_path(path, project_root, label)
    if len({output, waveform, spectrogram, record}) != 4:
        raise BreathAudioError("OUTPUT_PATHS_MUST_BE_DISTINCT")
    if source in (output, waveform, spectrogram, record):
        raise BreathAudioError("INPUT_IS_OUTPUT")

    return {
        "schema_version": 1,
        "tool": TOOL,
        "mode": mode,
        "run_id": run_id,
        "confirm": str(raw.get("confirm") or ""),
        "project_root": project_root,
        "input_wav": source,
        "output_wav": output,
        "waveform_preview_png": waveform,
        "spectrogram_preview_png": spectrogram,
        "record_json": record,
        "backup_dir": (project_root / "Backups" / ("PreBreathAudio-" + run_id)).resolve(),
        "breath_time_seconds": float(raw.get("breath_time_seconds", -1.0)),
        "wind_down_seconds": float(raw.get("wind_down_seconds", DEFAULT_WIND_DOWN_SECONDS)),
        "silence_seconds": float(raw.get("silence_seconds", -1.0)),
        "wind_up_seconds": float(raw.get("wind_up_seconds", DEFAULT_WIND_UP_SECONDS)),
        "curve_shape": float(raw.get("curve_shape", DEFAULT_CURVE_SHAPE)),
        "fade_ms": float(raw.get("fade_ms", DEFAULT_FADE_MS)),
        "join_search_ms": float(raw.get("join_search_ms", DEFAULT_JOIN_SEARCH_MS)),
        "expected_sample_rate_hz": raw.get("expected_sample_rate_hz"),
        "expected_channels": raw.get("expected_channels"),
        "output_subtype": raw.get("output_subtype"),
        "creative_values": {
            "breath_time_seconds": float(raw.get("breath_time_seconds", -1.0)),
            "wind_down_seconds": float(raw.get("wind_down_seconds", DEFAULT_WIND_DOWN_SECONDS)),
            "silence_seconds": float(raw.get("silence_seconds", -1.0)),
            "wind_up_seconds": float(raw.get("wind_up_seconds", DEFAULT_WIND_UP_SECONDS)),
            "curve_shape": float(raw.get("curve_shape", DEFAULT_CURVE_SHAPE)),
            "fade_ms": float(raw.get("fade_ms", DEFAULT_FADE_MS)),
            "join_search_ms": float(raw.get("join_search_ms", DEFAULT_JOIN_SEARCH_MS)),
        },
    }


def _curve_area(shape: float) -> float:
    # Integral 0..1 of (exp(k*(1-u))-1)/(exp(k)-1).
    return 1.0 / shape - 1.0 / math.expm1(shape)


def _decay_cumulative(u: np.ndarray, shape: float) -> np.ndarray:
    denom = math.expm1(shape)
    raw = ((math.exp(shape) - np.exp(shape * (1.0 - u))) / shape - u) / denom
    return raw / _curve_area(shape)


def _rise_cumulative(u: np.ndarray, shape: float) -> np.ndarray:
    denom = math.expm1(shape)
    raw = ((np.exp(shape * u) - 1.0) / shape - u) / denom
    return raw / _curve_area(shape)


def _interp(audio: np.ndarray, positions: np.ndarray) -> np.ndarray:
    base = np.arange(audio.shape[0], dtype=np.float64)
    channels = [np.interp(positions, base, audio[:, index]) for index in range(audio.shape[1])]
    return np.stack(channels, axis=1)


def _low_amplitude_sample(audio: np.ndarray, nominal: int, radius: int, low: int, high: int) -> int:
    lo = max(low, nominal - radius)
    hi = min(high, nominal + radius)
    if hi < lo:
        raise BreathAudioError("NO_RESUME_SAMPLE_WINDOW")
    score = np.max(np.abs(audio[lo : hi + 1]), axis=1)
    return lo + int(np.argmin(score))


def validate_audio_request(audio: np.ndarray, sample_rate: int, config: dict) -> dict:
    if audio.ndim != 2 or audio.shape[1] not in (1, 2):
        raise BreathAudioError("CHANNELS_MUST_BE_MONO_OR_STEREO:%s" % (audio.shape[1] if audio.ndim == 2 else audio.ndim))
    if sample_rate <= 0 or audio.shape[0] < 4:
        raise BreathAudioError("INVALID_AUDIO_SHAPE_OR_RATE")
    expected_rate = config.get("expected_sample_rate_hz")
    expected_channels = config.get("expected_channels")
    if expected_rate is not None and int(expected_rate) != sample_rate:
        raise BreathAudioError("SAMPLE_RATE_MISMATCH:expected=%s:got=%s" % (expected_rate, sample_rate))
    if expected_channels is not None and int(expected_channels) != audio.shape[1]:
        raise BreathAudioError("CHANNEL_MISMATCH:expected=%s:got=%s" % (expected_channels, audio.shape[1]))

    values = {
        "breath_time_seconds": float(config["breath_time_seconds"]),
        "wind_down_seconds": float(config["wind_down_seconds"]),
        "silence_seconds": float(config["silence_seconds"]),
        "wind_up_seconds": float(config["wind_up_seconds"]),
        "curve_shape": float(config["curve_shape"]),
        "fade_ms": float(config["fade_ms"]),
        "join_search_ms": float(config["join_search_ms"]),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise BreathAudioError("NONFINITE_ARGUMENT")
    if values["breath_time_seconds"] < 0.0:
        raise BreathAudioError("BREATH_TIME_NEGATIVE")
    if values["breath_time_seconds"] >= audio.shape[0] / sample_rate:
        raise BreathAudioError("BREATH_TIME_BEYOND_FILE")
    if values["silence_seconds"] < 0.0:
        raise BreathAudioError("SILENCE_NEGATIVE")
    if values["wind_down_seconds"] <= 0.0:
        raise BreathAudioError("WIND_DOWN_NONPOSITIVE")
    if values["wind_up_seconds"] < 0.0:
        raise BreathAudioError("WIND_UP_NEGATIVE")
    if values["curve_shape"] <= 0.05 or values["curve_shape"] > 20.0:
        raise BreathAudioError("CURVE_SHAPE_OUT_OF_RANGE")
    if values["fade_ms"] < 0.0 or values["join_search_ms"] < 0.0:
        raise BreathAudioError("FADE_OR_SEARCH_NEGATIVE")

    start = int(round(values["breath_time_seconds"] * sample_rate))
    down_out = int(round(values["wind_down_seconds"] * sample_rate))
    silence = int(round(values["silence_seconds"] * sample_rate))
    up_out = int(round(values["wind_up_seconds"] * sample_rate))
    if down_out < 2:
        raise BreathAudioError("WIND_DOWN_TOO_SHORT")
    # A deliberately conservative gate: a W longer than the remaining source is
    # almost certainly an args mistake even though low-rate varispeed would consume less.
    if start + down_out >= audio.shape[0]:
        raise BreathAudioError("WIND_DOWN_TOO_LONG")
    return {
        "start_sample": start,
        "wind_down_output_samples": down_out,
        "silence_samples": silence,
        "wind_up_output_samples": up_out,
        "fade_samples": min(down_out, int(round(values["fade_ms"] * sample_rate / 1000.0))),
        "join_search_samples": int(round(values["join_search_ms"] * sample_rate / 1000.0)),
        **values,
    }


def render_audio_array(audio: np.ndarray, sample_rate: int, config: dict) -> tuple[np.ndarray, dict]:
    """Return rendered float64 audio and exact sample-domain metadata."""
    timing = validate_audio_request(audio, sample_rate, config)
    start = timing["start_sample"]
    down_count = timing["wind_down_output_samples"]
    area = _curve_area(timing["curve_shape"])
    nominal_advance = max(1, int(round(down_count * area)))
    nominal_stop = start + nominal_advance
    stop = _low_amplitude_sample(
        audio,
        nominal_stop,
        timing["join_search_samples"],
        start + 1,
        audio.shape[0] - 2,
    )
    down_advance = stop - start
    down_u = np.linspace(0.0, 1.0, down_count, dtype=np.float64)
    down_positions = start + down_advance * _decay_cumulative(down_u, timing["curve_shape"])
    down = _interp(audio, down_positions)
    fade = timing["fade_samples"]
    if fade > 0:
        weights = 0.5 * (1.0 + np.cos(np.linspace(0.0, math.pi, fade, dtype=np.float64)))
        down[-fade:] *= weights[:, None]

    silence = np.zeros((timing["silence_samples"], audio.shape[1]), dtype=np.float64)
    up_count = timing["wind_up_output_samples"]
    up_advance = max(0, int(round(up_count * area)))
    unity_resume = stop + up_advance
    if unity_resume >= audio.shape[0]:
        raise BreathAudioError("WIND_UP_CONSUMES_PAST_FILE_END")
    if up_count:
        # Endpoint excluded: the following unity-rate suffix begins at the exact
        # integer source sample `unity_resume` without duplicating that endpoint.
        up_u = np.arange(up_count, dtype=np.float64) / float(up_count)
        up_positions = stop + up_advance * _rise_cumulative(up_u, timing["curve_shape"])
        up = _interp(audio, up_positions)
    else:
        up = np.empty((0, audio.shape[1]), dtype=np.float64)

    prefix = audio[:start]
    suffix = audio[unity_resume:].copy()
    # Resume de-click: preserve the exact stopped source sample at k=0, then
    # fade the *difference from that near-zero anchor* into the varispeed/unity
    # signal.  This gives a short fade-in without changing the resume sample or
    # adding/removing samples.  The low-amplitude search above keeps the initial
    # silence-to-anchor step small.
    resume_fade = min(timing["fade_samples"], up.shape[0] if up_count else suffix.shape[0])
    if resume_fade > 0:
        weights = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, resume_fade, endpoint=False, dtype=np.float64)))
        anchor = audio[stop]
        if up_count:
            up[:resume_fade] = anchor + weights[:, None] * (up[:resume_fade] - anchor)
        else:
            suffix[:resume_fade] = anchor + weights[:, None] * (suffix[:resume_fade] - anchor)
    rendered = np.concatenate((prefix, down, silence, up, suffix), axis=0)
    resume_output = prefix.shape[0] + down.shape[0] + silence.shape[0]
    unity_output = resume_output + (up.shape[0] if up_count else resume_fade)
    unity_resume = stop + (up_advance if up_count else resume_fade)
    expected_samples = (
        audio.shape[0]
        + down_count
        + timing["silence_samples"]
        + up_count
        - down_advance
        - up_advance
    )
    if rendered.shape[0] != expected_samples:
        raise BreathAudioError("LENGTH_MATH_INTERNAL_ERROR")
    resume_error = float(np.max(np.abs(rendered[resume_output] - audio[stop])))
    identity_error = float(np.max(np.abs(rendered[unity_output] - audio[unity_resume])))
    if resume_error != 0.0 or identity_error != 0.0:
        raise BreathAudioError("RESUME_SAMPLE_NOT_IDENTICAL")

    silence_start = prefix.shape[0] + down.shape[0]
    silence_end = silence_start + silence.shape[0]
    before_silence_jump = float(np.max(np.abs(rendered[silence_start - 1]))) if silence_start else 0.0
    after_silence_jump = float(np.max(np.abs(rendered[resume_output])))
    meta = {
        "sample_rate_hz": sample_rate,
        "channels": audio.shape[1],
        "input_samples": audio.shape[0],
        "output_samples": rendered.shape[0],
        "input_seconds": audio.shape[0] / sample_rate,
        "output_seconds": rendered.shape[0] / sample_rate,
        "output_length_delta_samples": rendered.shape[0] - audio.shape[0],
        "output_length_delta_seconds": (rendered.shape[0] - audio.shape[0]) / sample_rate,
        "wind_down_output_samples": down_count,
        "wind_down_source_advance_samples": down_advance,
        "wind_down_time_stretch_delta_samples": down_count - down_advance,
        "silence_samples": timing["silence_samples"],
        "wind_up_output_samples": up_count,
        "wind_up_source_advance_samples": up_advance,
        "wind_up_time_stretch_delta_samples": up_count - up_advance,
        "resume_fade_samples": resume_fade,
        "breath_output_start_sample": start,
        "silence_output_start_sample": silence_start,
        "silence_output_end_sample": silence_end,
        "resume_source_sample": stop,
        "resume_output_sample": resume_output,
        "unity_resume_source_sample": unity_resume,
        "unity_resume_output_sample": unity_output,
        "resume_sample_max_abs_error": resume_error,
        "unity_resume_sample_max_abs_error": identity_error,
        "join_from_wind_down_max_abs": before_silence_jump,
        "join_to_resume_max_abs": after_silence_jump,
        "join_search_offset_samples": stop - nominal_stop,
        "formula": "input + silence + (wind_down_output-wind_down_source) + (wind_up_output-wind_up_source)",
    }
    return rendered, meta


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(rgb: np.ndarray) -> bytes:
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise BreathAudioError("PNG_EXPECTS_UINT8_RGB")
    height, width, _ = rgb.shape
    scanlines = b"".join(b"\x00" + rgb[row].tobytes() for row in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", zlib.compress(scanlines, 9)) + _png_chunk(b"IEND", b"")


def _draw_vline(image: np.ndarray, x: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < image.shape[1]:
        image[:, max(0, x - 1) : min(image.shape[1], x + 1)] = color


def waveform_preview(audio: np.ndarray, markers: list[int], width: int = 1200, height: int = 360) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (12, 15, 22)
    count = audio.shape[0]
    boundaries = np.linspace(0, count, width + 1, dtype=np.int64)
    colors = ((68, 203, 255), (255, 151, 74))
    lane = height / audio.shape[1]
    for channel in range(audio.shape[1]):
        center = int(round((channel + 0.5) * lane))
        scale = max(1.0, lane * 0.42)
        image[max(0, center - 1) : min(height, center + 1)] = (47, 53, 66)
        for x in range(width):
            a, b = int(boundaries[x]), int(boundaries[x + 1])
            if b <= a:
                b = min(count, a + 1)
            if a >= count:
                continue
            values = audio[a:b, channel]
            top = int(round(center - np.max(values) * scale))
            bottom = int(round(center - np.min(values) * scale))
            top, bottom = sorted((max(0, min(height - 1, top)), max(0, min(height - 1, bottom))))
            image[top : bottom + 1, x] = colors[channel]
    for marker, color in zip(markers, ((255, 220, 80), (255, 80, 120), (80, 255, 160), (195, 120, 255))):
        _draw_vline(image, int(round(marker / max(1, count - 1) * (width - 1))), color)
    return encode_png(image)


def spectrogram_preview(audio: np.ndarray, sample_rate: int, markers: list[int], width: int = 1200, height: int = 480) -> bytes:
    mono = np.mean(audio, axis=1)
    nperseg = min(2048, max(64, 2 ** int(math.floor(math.log2(max(64, min(len(mono), 2048)))))))
    noverlap = int(nperseg * 0.75)
    frequencies, times, power = signal.spectrogram(
        mono,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        scaling="spectrum",
        mode="magnitude",
    )
    if power.size == 0:
        raise BreathAudioError("SPECTROGRAM_EMPTY")
    db = 20.0 * np.log10(np.maximum(power, 1.0e-9))
    ceiling = float(np.percentile(db, 99.5))
    norm = np.clip((db - (ceiling - 80.0)) / 80.0, 0.0, 1.0)
    # Log-frequency rows retain low-frequency detail without a plotting dependency.
    f_index = np.geomspace(1.0, max(1.0, frequencies.shape[0] - 1), height).astype(np.int64)
    t_index = np.linspace(0, max(0, times.shape[0] - 1), width).astype(np.int64)
    values = np.flipud(norm[f_index][:, t_index])
    red = np.clip(255.0 * (1.7 * values - 0.25), 0, 255)
    green = np.clip(255.0 * (1.5 * values**1.5), 0, 255)
    blue = np.clip(255.0 * (0.2 + 1.8 * (1.0 - values) * values), 0, 255)
    image = np.stack((red, green, blue), axis=2).astype(np.uint8)
    count = audio.shape[0]
    for marker, color in zip(markers, ((255, 220, 80), (255, 80, 120), (80, 255, 160), (195, 120, 255))):
        _draw_vline(image, int(round(marker / max(1, count - 1) * (width - 1))), color)
    return encode_png(image)


def build_render(config: dict) -> tuple[np.ndarray, bytes, bytes, dict, sf.SoundFile]:
    source = config["input_wav"]
    if not source.is_file() or source.suffix.lower() != ".wav":
        raise BreathAudioError("INPUT_WAV_MISSING_OR_NOT_WAV:%s" % source)
    info = sf.info(source)
    audio, sample_rate = sf.read(source, dtype="float64", always_2d=True)
    rendered, timing = render_audio_array(audio, int(sample_rate), config)
    markers = [
        timing["breath_output_start_sample"],
        timing["silence_output_start_sample"],
        timing["silence_output_end_sample"],
        timing["unity_resume_output_sample"],
    ]
    waveform = waveform_preview(rendered, markers)
    spectrogram = spectrogram_preview(rendered, int(sample_rate), markers)
    subtype = config.get("output_subtype") or info.subtype
    if subtype not in sf.available_subtypes("WAV"):
        subtype = "PCM_24"
    timing.update(
        {
            "input_format": info.format,
            "input_subtype": info.subtype,
            "output_subtype": subtype,
            "input_sha256": _sha256(source),
        }
    )
    return rendered, waveform, spectrogram, timing, info


def build_plan(config: dict) -> tuple[dict, tuple[np.ndarray, bytes, bytes]]:
    rendered, waveform, spectrogram, timing, _info = build_render(config)
    targets = [config["output_wav"], config["waveform_preview_png"], config["spectrogram_preview_png"]]
    plan = {
        "schema_version": 1,
        "tool": TOOL,
        "run_id": config["run_id"],
        "mode": config["mode"],
        "input_wav": config["input_wav"],
        "targets": [path.as_posix() for path in targets],
        "record_json": config["record_json"],
        "backup_dir": config["backup_dir"],
        "dirty_package_census": {"content": [], "maps": [], "source": "offline_no_unreal"},
        "creative_values": config["creative_values"],
        "timing": timing,
        "target_before": {path.as_posix(): _file_state(path) for path in targets},
    }
    return plan, (rendered, waveform, spectrogram)


def _backup_name(project_root: Path, target: Path) -> Path:
    return Path("files") / target.relative_to(project_root)


def apply_render(config: dict, plan: dict, payloads: tuple[np.ndarray, bytes, bytes]) -> dict:
    expected = APPLY_PREFIX + config["run_id"]
    if config["confirm"] != expected:
        raise BreathAudioError("CONFIRM_REQUIRED:%s" % expected)
    backup = config["backup_dir"]
    record = config["record_json"]
    if backup.exists():
        raise BreathAudioError("BACKUP_ALREADY_EXISTS:%s" % backup)
    if record.exists():
        raise BreathAudioError("RECORD_ALREADY_EXISTS:%s" % record)
    backup.mkdir(parents=True, exist_ok=False)
    for target_text, state in plan["target_before"].items():
        target = Path(target_text)
        if state["exists"]:
            destination = backup / _backup_name(config["project_root"], target)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
    pre_record = {
        "status": "prepared",
        "created_utc": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        **plan,
    }
    _write_json_exclusive(backup / "pre_apply_record.json", pre_record)

    rendered, waveform, spectrogram = payloads
    output = config["output_wav"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_wav = output.with_name(output.name + ".tmp.wav")
    sf.write(temp_wav, rendered, plan["timing"]["sample_rate_hz"], subtype=plan["timing"]["output_subtype"], format="WAV")
    os.replace(temp_wav, output)
    for path, data in ((config["waveform_preview_png"], waveform), (config["spectrogram_preview_png"], spectrogram)):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(data)
        os.replace(temp, path)

    readback, rate = sf.read(output, dtype="float64", always_2d=True)
    if int(rate) != plan["timing"]["sample_rate_hz"] or readback.shape != rendered.shape:
        raise BreathAudioError("WAV_READBACK_SHAPE_OR_RATE")
    for preview in (config["waveform_preview_png"], config["spectrogram_preview_png"]):
        if preview.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise BreathAudioError("PNG_READBACK_FAILED:%s" % preview)
    after = {path: _file_state(Path(path)) for path in plan["targets"]}
    applied = {
        "schema_version": 1,
        "tool": TOOL,
        "mode": "APPLY",
        "status": "passed",
        "run_id": config["run_id"],
        "created_utc": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "project_root": config["project_root"],
        "input_wav": config["input_wav"],
        "backup_dir": backup,
        "record_json": record,
        "dirty_package_census_before": plan["dirty_package_census"],
        "dirty_package_census_after": plan["dirty_package_census"],
        "creative_values": plan["creative_values"],
        "timing": plan["timing"],
        "target_before": plan["target_before"],
        "target_after": after,
        "saved_files": plan["targets"],
        "readback": {
            "wav_samples": int(readback.shape[0]),
            "wav_channels": int(readback.shape[1]),
            "sample_rate_hz": int(rate),
            "png_signatures_ok": True,
        },
        "success_marker": "BREATH_AUDIO_APPLY_OK|run=%s" % config["run_id"],
    }
    _write_json_exclusive(record, applied)
    return applied


def resolve_revert_config(raw: dict, args_path: Path | None = None) -> dict:
    root_value = raw.get("project_root") or (args_path.parent if args_path else Path.cwd())
    project_root = Path(root_value).resolve()
    source_run = str(raw.get("source_run_id") or "")
    if RUN_RE.fullmatch(source_run) is None:
        raise BreathAudioError("BAD_SOURCE_RUN_ID:%s" % source_run)
    run_id = str(raw.get("run_id") or ("BAUDIO-REVERT-" + _utc_stamp()))
    if RUN_RE.fullmatch(run_id) is None:
        raise BreathAudioError("BAD_RUN_ID:%s" % run_id)
    source_record = _resolve(
        project_root,
        str(raw.get("source_record_json") or ("Saved/CodexBreath/%s/apply_record.json" % source_run)),
        "source_record_json",
    )
    revert_record = _resolve(
        project_root,
        str(raw.get("record_json") or ("Saved/CodexBreath/%s/revert_record.json" % run_id)),
        "record_json",
    )
    _validate_output_path(revert_record, project_root, "record_json")
    return {
        "mode": "REVERT",
        "run_id": run_id,
        "source_run_id": source_run,
        "confirm": str(raw.get("confirm") or ""),
        "project_root": project_root,
        "source_record_json": source_record,
        "record_json": revert_record,
        "backup_dir": (project_root / "Backups" / ("PreBreathAudioRevert-" + run_id)).resolve(),
    }


def revert_render(config: dict) -> dict:
    expected = REVERT_PREFIX + config["source_run_id"]
    if config["confirm"] != expected:
        raise BreathAudioError("CONFIRM_REQUIRED:%s" % expected)
    with config["source_record_json"].open("r", encoding="utf-8") as handle:
        applied = json.load(handle)
    if applied.get("tool") != TOOL or applied.get("mode") != "APPLY" or applied.get("status") != "passed":
        raise BreathAudioError("BAD_APPLY_RECORD")
    if applied.get("run_id") != config["source_run_id"]:
        raise BreathAudioError("SOURCE_RUN_MISMATCH")
    backup = config["backup_dir"]
    if backup.exists() or config["record_json"].exists():
        raise BreathAudioError("REVERT_BACKUP_OR_RECORD_EXISTS")
    targets = [Path(path).resolve() for path in applied["saved_files"]]
    for target in targets:
        _validate_output_path(target, config["project_root"], "revert_target")
        wanted = applied["target_after"][target.as_posix()]
        if _file_state(target) != wanted:
            raise BreathAudioError("REVERT_DRIFT:%s" % target)

    backup.mkdir(parents=True, exist_ok=False)
    pre = {
        "schema_version": 1,
        "tool": TOOL,
        "mode": "REVERT",
        "status": "prepared",
        "run_id": config["run_id"],
        "source_run_id": config["source_run_id"],
        "targets": [path.as_posix() for path in targets],
        "dirty_package_census": {"content": [], "maps": [], "source": "offline_no_unreal"},
    }
    _write_json_exclusive(backup / "pre_revert_record.json", pre)
    original_backup = Path(applied["backup_dir"])
    for target in targets:
        archive = backup / "applied" / target.relative_to(config["project_root"])
        archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target, archive)
        old = applied["target_before"][target.as_posix()]
        if old["exists"]:
            stored = original_backup / _backup_name(config["project_root"], target)
            if _file_state(stored) != old:
                raise BreathAudioError("ORIGINAL_BACKUP_DRIFT:%s" % stored)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stored, target)
        if _file_state(target) != old:
            raise BreathAudioError("REVERT_READBACK_FAILED:%s" % target)

    result = {
        "schema_version": 1,
        "tool": TOOL,
        "mode": "REVERT",
        "status": "passed",
        "run_id": config["run_id"],
        "source_run_id": config["source_run_id"],
        "created_utc": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "backup_dir": backup,
        "restored": {path.as_posix(): _file_state(path) for path in targets},
        "dirty_package_census_after": {"content": [], "maps": [], "source": "offline_no_unreal"},
        "success_marker": "BREATH_AUDIO_REVERT_OK|run=%s|source=%s" % (config["run_id"], config["source_run_id"]),
    }
    _write_json_exclusive(config["record_json"], result)
    return result


def run(raw: dict, args_path: Path | None = None) -> dict:
    mode = str(raw.get("mode", "DRY")).upper()
    if mode == "REVERT":
        config = resolve_revert_config(raw, args_path)
        result = revert_render(config)
        print(result["success_marker"] + "|record=" + config["record_json"].as_posix())
        return result
    config = resolve_apply_config(raw, args_path)
    plan, payloads = build_plan(config)
    if mode == "DRY":
        marker = "BREATH_AUDIO_DRY_OK|run=%s|delta_samples=%d|delta_s=%.9f|writes=0" % (
            config["run_id"],
            plan["timing"]["output_length_delta_samples"],
            plan["timing"]["output_length_delta_seconds"],
        )
        plan["success_marker"] = marker
        print(marker)
        print(json.dumps(_jsonable(plan), indent=2, sort_keys=True))
        return plan
    applied = apply_render(config, plan, payloads)
    print(
        applied["success_marker"]
        + "|delta_samples=%d|delta_s=%.9f|record=%s|backup=%s"
        % (
            applied["timing"]["output_length_delta_samples"],
            applied["timing"]["output_length_delta_seconds"],
            config["record_json"].as_posix(),
            config["backup_dir"].as_posix(),
        )
    )
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--args", required=True, type=Path, help="JSON args file")
    parsed = parser.parse_args(argv)
    try:
        raw = load_args(parsed.args)
        run(raw, parsed.args.resolve())
        return 0
    except Exception as error:  # fail closed with one searchable marker
        run_id = "unknown"
        try:
            run_id = str(raw.get("run_id") or raw.get("source_run_id") or "unknown")
        except Exception:
            pass
        print("BREATH_AUDIO_STOPPED|run=%s|reason=%s" % (run_id, error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
