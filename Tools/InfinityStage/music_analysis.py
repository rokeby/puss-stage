#!/usr/bin/env python3
"""Deterministic, non-destructive Infinity Stage music-analysis provider.

It uses only Python's standard library and NumPy so the project does not silently
depend on an online service. Results are proposals with confidence/provenance;
this tool never edits an Unreal Show Asset or Cue Score.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ANALYZER_NAME = "InfinityStage Numpy Feature Provider"
ANALYZER_VERSION = "0.3.0"
# Expressive envelopes are phrase-scale; 10 Hz keeps the JSON small while still
# resolving swells, builds and drops far finer than anyone keyframes by hand.
CURVE_EXPORT_RATE_HZ = 10.0
TARGET_SAMPLE_RATE = 11025
HOP_LENGTH = 512
FFT_SIZE = 2048
MESH_ASSET_NAMES = {
    1: "/Game/InfinityStage/Audio/Passages/SW_P01_IntroWalking.SW_P01_IntroWalking",
    2: "/Game/InfinityStage/Audio/Passages/SW_P02_Walking.SW_P02_Walking",
    3: "/Game/InfinityStage/Audio/Passages/SW_P03_Walking.SW_P03_Walking",
    4: "/Game/InfinityStage/Audio/Passages/SW_P04_Walking.SW_P04_Walking",
    5: "/Game/InfinityStage/Audio/Passages/SW_P05_TennisBall.SW_P05_TennisBall",
    6: "/Game/InfinityStage/Audio/Passages/SW_P06_IntoVoid.SW_P06_IntoVoid",
}


@dataclass(frozen=True)
class WavInfo:
    channels: int
    sample_rate: int
    sample_width: int
    sample_format: int
    frame_count: int
    data_offset: int
    data_size: int

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate


def _read_wav_info(path: Path) -> WavInfo:
    with path.open("rb") as handle:
        if handle.read(4) not in (b"RIFF", b"RF64"):
            raise ValueError(f"{path.name}: not a RIFF/RF64 WAV")
        handle.read(4)
        if handle.read(4) != b"WAVE":
            raise ValueError(f"{path.name}: missing WAVE signature")
        fmt: tuple[int, int, int, int] | None = None
        data_offset = data_size = 0
        while True:
            header = handle.read(8)
            if len(header) != 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", header)
            chunk_start = handle.tell()
            if chunk_id == b"fmt ":
                raw = handle.read(chunk_size)
                if len(raw) < 16:
                    raise ValueError(f"{path.name}: short fmt chunk")
                format_tag, channels, sample_rate, _, block_align, bits = struct.unpack("<HHIIHH", raw[:16])
                if format_tag == 0xFFFE and len(raw) >= 26:
                    format_tag = struct.unpack("<H", raw[24:26])[0]
                fmt = (format_tag, channels, sample_rate, bits)
                if block_align != channels * (bits // 8):
                    raise ValueError(f"{path.name}: unsupported packed block alignment")
            elif chunk_id == b"data":
                data_offset = chunk_start
                data_size = chunk_size
            handle.seek(chunk_start + chunk_size + (chunk_size & 1))
        if fmt is None or not data_offset:
            raise ValueError(f"{path.name}: missing fmt or data chunk")
        format_tag, channels, sample_rate, bits = fmt
        sample_width = bits // 8
        frame_count = data_size // (channels * sample_width)
        return WavInfo(channels, sample_rate, sample_width, format_tag, frame_count, data_offset, data_size)


def decode_mono(path: Path, target_sample_rate: int = TARGET_SAMPLE_RATE) -> tuple[np.ndarray, int, WavInfo]:
    info = _read_wav_info(path)
    if info.sample_format == 3 and info.sample_width == 4:
        dtype = np.dtype("<f4")
        scale = 1.0
    elif info.sample_format == 3 and info.sample_width == 8:
        dtype = np.dtype("<f8")
        scale = 1.0
    elif info.sample_format == 1 and info.sample_width == 2:
        dtype = np.dtype("<i2")
        scale = 32768.0
    elif info.sample_format == 1 and info.sample_width == 4:
        dtype = np.dtype("<i4")
        scale = 2147483648.0
    else:
        raise ValueError(
            f"{path.name}: unsupported WAV encoding tag={info.sample_format}, width={info.sample_width}"
        )

    raw = np.memmap(path, mode="r", dtype=dtype, offset=info.data_offset, shape=(info.frame_count * info.channels,))
    interleaved = raw.reshape(info.frame_count, info.channels)
    decimation = max(1, int(round(info.sample_rate / target_sample_rate)))
    mono = np.asarray(interleaved[::decimation], dtype=np.float32).mean(axis=1, dtype=np.float32)
    if scale != 1.0:
        mono /= np.float32(scale)
    actual_rate = info.sample_rate // decimation
    mono = np.nan_to_num(mono, copy=False)
    mono -= np.float32(np.mean(mono, dtype=np.float64))
    return mono, actual_rate, info


def file_fingerprints(path: Path) -> dict[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
    return {"sha256": sha256.hexdigest(), "md5": md5.hexdigest()}


def _robust_unit(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    median = np.median(values)
    upper = np.percentile(values, 95)
    scale = max(upper - median, 1e-12)
    return np.clip((values - median) / scale, 0.0, 1.0)


def _peak_indices(values: np.ndarray, threshold: float, min_distance: int, limit: int) -> list[int]:
    if values.size < 3 or float(np.max(values)) <= 1e-12:
        return []
    candidates = np.flatnonzero(
        (values[1:-1] >= values[:-2])
        & (values[1:-1] > values[2:])
        & (values[1:-1] >= threshold)
    ) + 1
    selected: list[int] = []
    for index in sorted(candidates.tolist(), key=lambda i: float(values[i]), reverse=True):
        if all(abs(index - other) >= min_distance for other in selected):
            selected.append(index)
            if len(selected) >= limit:
                break
    return sorted(selected)


def _extract_features(samples: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if samples.size < FFT_SIZE:
        samples = np.pad(samples, (0, FFT_SIZE - samples.size))
    starts = np.arange(0, samples.size - FFT_SIZE + 1, HOP_LENGTH, dtype=np.int64)
    window = np.hanning(FFT_SIZE).astype(np.float32)
    band_edges = np.unique(np.geomspace(1, FFT_SIZE // 2 + 1, 25).astype(np.int32))
    if band_edges.size < 25:
        band_edges = np.linspace(1, FFT_SIZE // 2 + 1, 25, dtype=np.int32)
    features = np.empty((starts.size, 24), dtype=np.float32)
    rms = np.empty(starts.size, dtype=np.float32)
    flux = np.zeros(starts.size, dtype=np.float32)
    previous: np.ndarray | None = None
    offsets = np.arange(FFT_SIZE, dtype=np.int64)
    for batch_start in range(0, starts.size, 256):
        batch_starts = starts[batch_start : batch_start + 256]
        frames = samples[batch_starts[:, None] + offsets] * window
        rms[batch_start : batch_start + batch_starts.size] = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
        spectrum = np.log1p(np.abs(np.fft.rfft(frames, axis=1))).astype(np.float32)
        for band in range(24):
            left, right = int(band_edges[band]), int(band_edges[band + 1])
            features[batch_start : batch_start + batch_starts.size, band] = spectrum[:, left:right].mean(axis=1)
        for row in range(spectrum.shape[0]):
            if previous is not None:
                flux[batch_start + row] = np.maximum(spectrum[row] - previous, 0.0).mean()
            previous = spectrum[row]
    return features, rms, _robust_unit(flux).astype(np.float32)


def _tempo_candidates(onset: np.ndarray, feature_rate: float) -> list[dict[str, float]]:
    if onset.size < 8 or float(np.max(onset)) < 0.05:
        return []
    signal = onset.astype(np.float64) - np.mean(onset)
    size = 1 << int(math.ceil(math.log2(max(2, signal.size * 2))))
    spectrum = np.fft.rfft(signal, n=size)
    autocorrelation = np.fft.irfft(spectrum * np.conjugate(spectrum), n=size)[: signal.size]
    autocorrelation /= np.maximum(1, signal.size - np.arange(signal.size))
    min_lag = max(1, int(feature_rate * 60.0 / 220.0))
    max_lag = min(signal.size - 2, int(feature_rate * 60.0 / 40.0))
    if max_lag <= min_lag:
        return []
    lags = np.arange(min_lag, max_lag + 1)
    scores = autocorrelation[lags].copy()
    twice = lags * 2
    valid_twice = twice < autocorrelation.size
    scores[valid_twice] += 0.35 * autocorrelation[twice[valid_twice]]
    half = np.maximum(1, np.rint(lags / 2).astype(int))
    scores += 0.15 * autocorrelation[half]
    local = np.flatnonzero((scores[1:-1] >= scores[:-2]) & (scores[1:-1] > scores[2:])) + 1
    if local.size == 0:
        local = np.array([int(np.argmax(scores))])
    floor = float(np.median(scores))
    ceiling = float(np.max(scores))
    # A flat autocorrelation has no periodic evidence. Returning a zero-confidence
    # BPM would look authoritative in the Cue Desk even though it is only an
    # arbitrary lag selected from silence/noise.
    if not np.isfinite(ceiling) or ceiling <= floor + 1e-9:
        return []
    denom = max(ceiling - floor, 1e-12)
    candidates: list[dict[str, float]] = []
    for position in sorted(local.tolist(), key=lambda i: float(scores[i]), reverse=True):
        lag = float(lags[position])
        if 0 < position < scores.size - 1:
            y0, y1, y2 = scores[position - 1 : position + 2]
            curvature = y0 - 2.0 * y1 + y2
            if abs(curvature) > 1e-12:
                lag += float(np.clip(0.5 * (y0 - y2) / curvature, -0.5, 0.5))
        bpm = 60.0 * feature_rate / lag
        if any(abs(math.log2(bpm / item["bpm"])) < 0.035 for item in candidates):
            continue
        confidence = float(np.clip((scores[position] - floor) / denom, 0.0, 1.0))
        # Do not manufacture a BPM label from a local maximum with effectively
        # no periodic support. Ambiguous but real half/double-time alternatives
        # remain visible; unsupported candidates do not.
        if confidence < 0.05:
            continue
        candidates.append(
            {
                "bpm": round(float(bpm), 3),
                "confidence": round(confidence, 4),
            }
        )
        if len(candidates) == 5:
            break
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    return candidates


def _structural_changes(features: np.ndarray, rms: np.ndarray, feature_rate: float) -> tuple[np.ndarray, list[dict[str, Any]]]:
    count = features.shape[0]
    novelty = np.zeros(count, dtype=np.float32)
    context = max(4, int(round(3.0 * feature_rate)))
    if count <= context * 2 + 1:
        return novelty, []
    normalized = (features - np.mean(features, axis=0)) / (np.std(features, axis=0) + 1e-6)
    cumulative = np.vstack((np.zeros((1, normalized.shape[1])), np.cumsum(normalized, axis=0)))
    positions = np.arange(context, count - context)
    before = (cumulative[positions] - cumulative[positions - context]) / context
    after = (cumulative[positions + context] - cumulative[positions]) / context
    spectral_delta = np.sqrt(np.mean((after - before) ** 2, axis=1))
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-8))
    rms_cumulative = np.concatenate(([0.0], np.cumsum(rms_db)))
    loudness_delta = np.abs(
        (rms_cumulative[positions + context] - rms_cumulative[positions]) / context
        - (rms_cumulative[positions] - rms_cumulative[positions - context]) / context
    )
    raw = _robust_unit(spectral_delta) * 0.8 + _robust_unit(loudness_delta) * 0.2
    novelty[positions] = np.convolve(raw, np.ones(7) / 7.0, mode="same")
    threshold = max(0.22, float(np.percentile(novelty[positions], 78)))
    peaks = _peak_indices(novelty, threshold, max(1, int(5.0 * feature_rate)), 16)
    markers = [
        {
            "timeSeconds": round(index / feature_rate, 4),
            "strength": round(float(novelty[index]), 4),
            "label": "Major change suggestion",
            "state": "Suggested",
        }
        for index in peaks
    ]
    return novelty, markers


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size == 0:
        return np.asarray(values, dtype=np.float64)
    kernel = np.ones(int(window), dtype=np.float64) / float(window)
    return np.convolve(np.asarray(values, dtype=np.float64), kernel, mode="same")


def _resample(values: np.ndarray, duration: float, target_rate: float) -> np.ndarray:
    """Resample a per-frame feature onto a declared export rate.

    Expressive envelopes are phrase-scale, so exporting at the full feature rate
    would multiply the file size for detail no one keyframes against.
    """
    count = max(1, int(round(duration * target_rate)))
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return np.zeros(count, dtype=np.float64)
    if values.size == 1:
        return np.full(count, float(values[0]), dtype=np.float64)
    source = np.linspace(0.0, duration, values.size, endpoint=False)
    target = np.linspace(0.0, duration, count, endpoint=False)
    return np.interp(target, source, values)


def _brightness(features: np.ndarray) -> np.ndarray:
    """Band-index centroid: 0 is bass-weighted, 1 is treble-weighted."""
    if features.size == 0 or features.shape[1] < 2:
        return np.zeros(features.shape[0], dtype=np.float64)
    weights = np.arange(features.shape[1], dtype=np.float64)
    magnitudes = np.asarray(features, dtype=np.float64)
    total = magnitudes.sum(axis=1) + 1e-9
    return (magnitudes * weights).sum(axis=1) / total / float(features.shape[1] - 1)


def _band_split(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Low/mid/high energy from the bands the analyzer already computes."""
    if features.size == 0:
        empty = np.zeros(features.shape[0], dtype=np.float64)
        return empty, empty.copy(), empty.copy()
    groups = np.array_split(np.arange(features.shape[1]), 3)
    return tuple(  # type: ignore[return-value]
        _robust_unit(np.asarray(features, dtype=np.float64)[:, group].mean(axis=1))
        for group in groups
    )


def _rhythmic_density(onset_peaks: list[int], frame_count: int, feature_rate: float) -> np.ndarray:
    """Onsets per second over a two-second window: how busy the music is."""
    impulses = np.zeros(max(1, frame_count), dtype=np.float64)
    for index in onset_peaks:
        if 0 <= index < impulses.size:
            impulses[index] = 1.0
    window = max(1, int(round(2.0 * feature_rate)))
    return _moving_average(impulses, window) * float(feature_rate)


def _label_section(mean_intensity: float, slope: float) -> str:
    """Name the expressive character of a span.

    Direction wins over level: a quiet passage that is clearly growing is more
    usefully described as building than as quiet.
    """
    if slope >= 0.08:
        return "building"
    if slope <= -0.08:
        return "releasing"
    if mean_intensity >= 0.60:
        return "intense"
    if mean_intensity <= 0.30:
        return "quiet"
    return "sustained"


def _sections(
    intensity: np.ndarray,
    change_indices: list[int],
    feature_rate: float,
    duration: float,
) -> list[dict[str, Any]]:
    """Group the track into spans between structural changes and characterize each.

    A build is an interval, not an instant, so this is the part markers cannot
    express and the part expressive Wing timing actually needs.
    """
    if intensity.size == 0 or feature_rate <= 0.0:
        return []
    bounds = [0] + [int(index) for index in change_indices if 0 < int(index) < intensity.size]
    bounds.append(int(intensity.size))
    bounds = sorted(set(bounds))

    sections: list[dict[str, Any]] = []
    for start, end in zip(bounds[:-1], bounds[1:]):
        span = intensity[start:end]
        if span.size == 0:
            continue
        # Compare the last quarter against the first: robust to a single spike
        # in a way a raw endpoint difference is not.
        quarter = max(1, span.size // 4)
        slope = float(np.mean(span[-quarter:]) - np.mean(span[:quarter]))
        mean_intensity = float(np.mean(span))
        sections.append(
            {
                "startSeconds": round(start / feature_rate, 4),
                "endSeconds": round(min(end / feature_rate, duration), 4),
                "meanIntensity": round(mean_intensity, 4),
                "peakIntensity": round(float(np.max(span)), 4),
                "trend": round(slope, 4),
                "label": _label_section(mean_intensity, slope),
                "state": "Suggested",
            }
        )
    return sections


def _waveform_bins(samples: np.ndarray, count: int = 1400) -> list[dict[str, float]]:
    edges = np.linspace(0, samples.size, count + 1, dtype=np.int64)
    result: list[dict[str, float]] = []
    for left, right in zip(edges[:-1], edges[1:]):
        block = samples[left : max(left + 1, right)]
        result.append(
            {
                "min": round(float(np.min(block)), 5),
                "max": round(float(np.max(block)), 5),
                "rms": round(float(np.sqrt(np.mean(block * block) + 1e-12)), 5),
            }
        )
    return result


def analyze_samples(samples: np.ndarray, sample_rate: int, *, source_name: str = "synthetic") -> dict[str, Any]:
    samples = np.asarray(samples, dtype=np.float32)
    features, rms, onset = _extract_features(samples, sample_rate)
    feature_rate = sample_rate / HOP_LENGTH
    onset_threshold = max(0.28, float(np.percentile(onset, 82)))
    onset_peaks = _peak_indices(onset, onset_threshold, max(1, int(0.12 * feature_rate)), 600)
    tempos = _tempo_candidates(onset, feature_rate)
    novelty, changes = _structural_changes(features, rms, feature_rate)

    beats: list[dict[str, Any]] = []
    if tempos:
        best_bpm = tempos[0]["bpm"]
        lag = max(1, int(round(feature_rate * 60.0 / best_bpm)))
        phase_scores = [float(np.sum(onset[phase::lag])) for phase in range(min(lag, onset.size))]
        phase = int(np.argmax(phase_scores)) if phase_scores else 0
        for index in range(phase, onset.size, lag):
            beats.append(
                {
                    "timeSeconds": round(index / feature_rate, 4),
                    "confidence": round(float(0.35 + 0.65 * onset[index]), 4),
                    "state": "Suggested",
                }
            )

    duration_seconds = samples.size / sample_rate
    # Continuous expressive envelopes. The analyzer already computed everything
    # needed for these; previously it reduced them to timestamps and discarded
    # the shape, which is exactly what timing movement to musical expression
    # requires.
    intensity = _robust_unit(_moving_average(rms, max(1, int(round(0.35 * feature_rate)))))
    low_band, mid_band, high_band = _band_split(features)
    curves = {
        "intensity": intensity,
        "rhythmicDensity": _robust_unit(_rhythmic_density(onset_peaks, onset.size, feature_rate)),
        "brightness": _moving_average(_brightness(features), max(1, int(round(0.35 * feature_rate)))),
        "lowBand": low_band,
        "midBand": mid_band,
        "highBand": high_band,
        "novelty": np.asarray(novelty, dtype=np.float64),
    }
    change_indices = [int(round(marker["timeSeconds"] * feature_rate)) for marker in changes]

    return {
        "analysisSchemaVersion": 2,
        "analyzer": {"name": ANALYZER_NAME, "version": ANALYZER_VERSION},
        "sourceName": source_name,
        "analysisSampleRateHz": sample_rate,
        "hopLength": HOP_LENGTH,
        "durationSeconds": round(samples.size / sample_rate, 6),
        "tempoCandidates": tempos,
        "onsetProposals": [
            {
                "timeSeconds": round(index / feature_rate, 4),
                "strength": round(float(onset[index]), 4),
                "state": "Suggested",
            }
            for index in onset_peaks
        ],
        "beatProposals": beats,
        "majorChangeProposals": changes,
        "expressiveSections": _sections(intensity, change_indices, feature_rate, duration_seconds),
        "featureCurves": {
            "rateHz": CURVE_EXPORT_RATE_HZ,
            "sampleCount": max(1, int(round(duration_seconds * CURVE_EXPORT_RATE_HZ))),
            "range": {"minimum": 0.0, "maximum": 1.0},
            "curves": {
                name: [
                    round(float(value), 4)
                    for value in _resample(values, duration_seconds, CURVE_EXPORT_RATE_HZ)
                ]
                for name, values in curves.items()
            },
        },
        "waveform": _waveform_bins(samples),
        "summary": {
            "peak": round(float(np.max(np.abs(samples))), 6),
            "rmsDb": round(float(20.0 * np.log10(max(float(np.sqrt(np.mean(samples * samples))), 1e-8))), 3),
            "onsetCount": len(onset_peaks),
            "majorChangeCount": len(changes),
            "sectionLabels": ", ".join(
                f"{section['label']} {section['startSeconds']:.1f}-{section['endSeconds']:.1f}s"
                for section in _sections(intensity, change_indices, feature_rate, duration_seconds)
            ) or "none",
            "ambiguity": (
                "high" if len(tempos) > 1 and tempos[1]["confidence"] > tempos[0]["confidence"] * 0.82 else "normal"
            ),
        },
        "safety": {
            "cueScoreMutated": False,
            "requiresArtistApproval": True,
            "tempoIsProposalNotAuthority": True,
        },
    }


def analyze_file(path: Path, passage: int, expected_sha256: str | None = None) -> dict[str, Any]:
    fingerprints = file_fingerprints(path)
    if expected_sha256 and fingerprints["sha256"] != expected_sha256:
        raise ValueError(f"{path.name}: SHA-256 differs from the verified source manifest")
    samples, rate, wav = decode_mono(path)
    result = analyze_samples(samples, rate, source_name=path.name)
    result.update(
        {
            "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "passage": passage,
            "source": {
                "filename": path.name,
                "absolutePath": str(path.resolve()),
                "unrealSoundPath": MESH_ASSET_NAMES.get(passage, ""),
                "sha256": fingerprints["sha256"],
                "md5": fingerprints["md5"],
                "channels": wav.channels,
                "sourceSampleRateHz": wav.sample_rate,
                "sourceFrames": wav.frame_count,
                "sourceDurationSeconds": round(wav.duration_seconds, 6),
            },
        }
    )
    return result


def render_svg(result: dict[str, Any], output: Path) -> None:
    width, height = 1400, 430
    left, right, top, bottom = 64, 24, 72, 58
    plot_w, plot_h = width - left - right, height - top - bottom
    waveform = result["waveform"]
    duration = max(result["durationSeconds"], 1e-6)
    mid = top + plot_h * 0.45
    amplitude = plot_h * 0.34
    upper = []
    lower = []
    for index, item in enumerate(waveform):
        x = left + plot_w * index / max(1, len(waveform) - 1)
        upper.append(f"{x:.2f},{mid - item['max'] * amplitude:.2f}")
        lower.append(f"{x:.2f},{mid - item['min'] * amplitude:.2f}")
    area = " ".join(upper + list(reversed(lower)))
    tempo_text = ", ".join(f"{item['bpm']:.1f} BPM ({item['confidence']:.2f})" for item in result["tempoCandidates"][:3]) or "No stable tempo"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#11151b"/>',
        f'<text x="{left}" y="30" fill="#f0f4f8" font-family="sans-serif" font-size="20">Passage {result.get("passage", "—")} · {result["sourceName"]}</text>',
        f'<text x="{left}" y="53" fill="#91a4b7" font-family="sans-serif" font-size="13">{duration:.3f}s · tempo candidates: {tempo_text}</text>',
        f'<line x1="{left}" y1="{mid:.2f}" x2="{left + plot_w}" y2="{mid:.2f}" stroke="#34404d"/>',
        f'<polygon points="{area}" fill="#58a6ff" fill-opacity="0.48" stroke="#7dc0ff" stroke-width="0.7"/>',
    ]
    for marker in result["onsetProposals"]:
        x = left + plot_w * marker["timeSeconds"] / duration
        opacity = 0.08 + 0.25 * marker["strength"]
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#f0b35a" stroke-opacity="{opacity:.3f}"/>')
    for marker in result["majorChangeProposals"]:
        x = left + plot_w * marker["timeSeconds"] / duration
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#ff6b8a" stroke-width="2"/>')
        lines.append(f'<text x="{x + 4:.2f}" y="{top + 16}" fill="#ff9db1" font-family="sans-serif" font-size="11">{marker["timeSeconds"]:.1f}s</text>')
    for second in np.linspace(0, duration, 9):
        x = left + plot_w * second / duration
        lines.append(f'<line x1="{x:.2f}" y1="{top + plot_h}" x2="{x:.2f}" y2="{top + plot_h + 6}" stroke="#8190a0"/>')
        lines.append(f'<text x="{x:.2f}" y="{top + plot_h + 24}" text-anchor="middle" fill="#91a4b7" font-family="sans-serif" font-size="11">{second:.1f}s</text>')
    lines.append(f'<text x="{left}" y="{height - 12}" fill="#8190a0" font-family="sans-serif" font-size="11">Blue: waveform · amber: onset evidence · pink: unapproved major-change proposals · {ANALYZER_NAME} {ANALYZER_VERSION}</text>')
    lines.append("</svg>")
    output.write_text("\n".join(lines), encoding="utf-8")


def _write_summary(results: Iterable[dict[str, Any]], output: Path) -> None:
    rows = []
    for result in results:
        tempos = ", ".join(f"{item['bpm']:.1f} ({item['confidence']:.2f})" for item in result["tempoCandidates"][:3]) or "No stable candidate"
        changes = ", ".join(f"{item['timeSeconds']:.1f}s" for item in result["majorChangeProposals"]) or "None above threshold"
        rows.append(
            f"| {result['passage']} | `{result['sourceName']}` | {result['durationSeconds']:.3f}s | {tempos} | {changes} | {result['summary']['ambiguity']} |"
        )
    text = "\n".join(
        [
            "# Infinity Stage Music Analysis — Review Proposals",
            "",
            f"Provider: **{ANALYZER_NAME} {ANALYZER_VERSION}**. These are unapproved suggestions; no Cue Score data was changed.",
            "",
            "| Passage | Source | Duration | Top tempo candidates | Major-change suggestions | Ambiguity |",
            "| ---: | --- | ---: | --- | --- | --- |",
            *rows,
            "",
            "The provider deliberately retains competing half/double-time candidates when evidence is ambiguous. Pink markers in the SVG reviews are structural-change evidence, not automatic edit points.",
            "",
        ]
    )
    output.write_text(text, encoding="utf-8")


PASSAGE_PREFIX = re.compile(r"^[Pp](\d{1,2})[_\-. ]")


def _existing_passage_by_filename(output_dir: Path) -> dict[str, int]:
    """Passage numbers already recorded for a filename, so a redrop keeps its slot."""
    known: dict[str, int] = {}
    for path in sorted(output_dir.glob("*.analysis.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        filename = data.get("source", {}).get("filename")
        passage = data.get("passage")
        if isinstance(filename, str) and isinstance(passage, int):
            known[filename] = passage
    return known


def _existing_state(output_dir: Path) -> dict[str, tuple[str, str]]:
    """filename -> (sha256, providerVersion) from previous runs."""
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(output_dir.glob("*.analysis.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        source = data.get("source", {})
        filename = source.get("filename")
        if isinstance(filename, str):
            state[filename] = (
                str(source.get("sha256", "")),
                str(data.get("analyzer", {}).get("version", "")),
            )
    return state


def resolve_passages(sources: list[Path], output_dir: Path) -> list[tuple[Path, int, str]]:
    """Assign a Passage number to each dropped file, explaining every choice.

    Explicit `P03_` style prefixes win; otherwise a filename already analysed
    keeps the Passage it had, so redropping a corrected mix cannot silently
    reshuffle the Show. Anything left over fills the lowest free slot.
    """
    known = _existing_passage_by_filename(output_dir)
    assigned: dict[int, Path] = {}
    reasons: dict[Path, str] = {}
    pending: list[Path] = []

    for source in sources:
        match = PASSAGE_PREFIX.match(source.name)
        if match:
            passage = int(match.group(1))
            if passage in assigned:
                raise SystemExit(
                    f"Two files claim Passage {passage}: {assigned[passage].name} and {source.name}"
                )
            assigned[passage] = source
            reasons[source] = "filename prefix"
        else:
            pending.append(source)

    for source in list(pending):
        passage = known.get(source.name)
        if passage is not None and passage not in assigned:
            assigned[passage] = source
            reasons[source] = "previous analysis"
            pending.remove(source)

    next_free = 1
    for source in pending:
        while next_free in assigned:
            next_free += 1
        assigned[next_free] = source
        reasons[source] = "order fallback"

    return [
        (source, passage, reasons[source])
        for passage, source in sorted(assigned.items())
    ]


def analyze_drop_directory(
    drop_dir: Path,
    output_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Analyse every WAV in a drop folder, skipping ones already up to date."""
    if not drop_dir.is_dir():
        raise SystemExit(f"Drop directory does not exist: {drop_dir}")
    sources = sorted(
        path for path in drop_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".wav"
    )
    if not sources:
        raise SystemExit(
            f"No .wav files in {drop_dir}. The analyzer reads RIFF WAV only; "
            "export from your DAW rather than dropping MP3 or FLAC."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    previous = _existing_state(output_dir)
    plan = resolve_passages(sources, output_dir)

    results: list[dict[str, Any]] = []
    analyzed: list[str] = []
    skipped: list[str] = []
    for source, passage, reason in plan:
        fingerprints = file_fingerprints(source)
        was = previous.get(source.name)
        # Re-analyse when the audio changed or the provider moved on, so a
        # version bump cannot leave stale curves behind.
        up_to_date = (
            not force
            and was is not None
            and was[0] == fingerprints["sha256"]
            and was[1] == ANALYZER_VERSION
        )
        stem = f"P{passage:02d}_{source.stem}"
        if up_to_date:
            skipped.append(source.name)
            existing = output_dir / f"{stem}.analysis.json"
            if existing.is_file():
                results.append(json.loads(existing.read_text(encoding="utf-8")))
            continue

        print(f"  P{passage:02d}  {source.name}  ({reason})")
        result = analyze_file(source, passage)
        (output_dir / f"{stem}.analysis.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        render_svg(result, output_dir / f"{stem}.analysis.svg")
        results.append(result)
        analyzed.append(source.name)

    if results:
        _write_summary(results, output_dir / "README.md")
    # Keep a manifest so a run is reproducible without the drop folder.
    (output_dir / "music_manifest.json").write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "passage": passage,
                        "filename": source.name,
                        "sha256": file_fingerprints(source)["sha256"],
                    }
                    for source, passage, _ in plan
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "analyzed": analyzed,
        "skipped": skipped,
        "outputDirectory": str(output_dir),
        "providerVersion": ANALYZER_VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse Passage music. With no arguments, reads WAVs from "
        "Saved/InfinityStage/MusicDrop and writes review maps to Saved/InfinityStage/MusicAnalysis."
    )
    parser.add_argument("--manifest", type=Path, help="Explicit track list; omit to use the drop folder.")
    parser.add_argument("--source-dir", type=Path, help="Directory holding the manifest's files.")
    parser.add_argument("--drop-dir", type=Path, help="Folder of .wav files to analyse.")
    parser.add_argument("--output-dir", type=Path, help="Where review maps are written.")
    parser.add_argument("--force", action="store_true", help="Re-analyse even when nothing changed.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    output_dir = args.output_dir or (project_root / "Saved/InfinityStage/MusicAnalysis")

    if args.manifest:
        if not args.source_dir:
            raise SystemExit("--manifest requires --source-dir")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for track in manifest["tracks"]:
            source = args.source_dir / track["filename"]
            result = analyze_file(source, int(track["passage"]), track.get("sha256"))
            stem = f"P{int(track['passage']):02d}_{source.stem}"
            (output_dir / f"{stem}.analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            render_svg(result, output_dir / f"{stem}.analysis.svg")
            results.append(result)
        _write_summary(results, output_dir / "README.md")
        print(json.dumps({"analyzed": len(results), "outputDirectory": str(output_dir), "providerVersion": ANALYZER_VERSION}))
        return 0

    drop_dir = args.drop_dir or (project_root / "Saved/InfinityStage/MusicDrop")
    print(f"Reading {drop_dir}")
    summary = analyze_drop_directory(drop_dir, output_dir, force=args.force)
    print(json.dumps(summary, indent=2))
    if summary["skipped"]:
        print(f"{len(summary['skipped'])} track(s) already up to date; pass --force to redo them.")
    print("Now run Cue Desk > Actions > Link / Reimport Music Analysis in Unreal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
