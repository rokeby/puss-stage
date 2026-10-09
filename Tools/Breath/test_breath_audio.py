#!/usr/bin/env python3
"""Offline positive/negative harness for Tools/Breath/breath_audio.py."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile

import numpy as np
import soundfile as sf


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("breath_audio", HERE / "breath_audio.py")
BREATH = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BREATH)


class HarnessFailure(AssertionError):
    pass


checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        raise HarnessFailure(message)


def expect_error(label: str, fragment: str, function) -> None:
    global checks
    checks += 1
    try:
        function()
    except BREATH.BreathAudioError as error:
        if fragment not in str(error):
            raise HarnessFailure("%s raised %r, expected %r" % (label, str(error), fragment))
        return
    raise HarnessFailure("%s did not fail" % label)


def source_audio(sample_rate: int = 8000, seconds: float = 4.0, channels: int = 2) -> np.ndarray:
    time = np.arange(int(round(sample_rate * seconds)), dtype=np.float64) / sample_rate
    left = 0.42 * np.sin(2.0 * np.pi * 220.0 * time)
    if channels == 1:
        return left[:, None]
    right = 0.36 * np.sin(2.0 * np.pi * 330.0 * time)
    return np.stack((left, right), axis=1)


def base_timing() -> dict:
    return {
        "breath_time_seconds": 0.8,
        "wind_down_seconds": 0.4,
        "silence_seconds": 0.3,
        "wind_up_seconds": 0.0,
        "curve_shape": 4.5,
        "fade_ms": 8.0,
        "join_search_ms": 25.0,
        "expected_sample_rate_hz": 8000,
        "expected_channels": 2,
    }


def positive_no_wind_up() -> None:
    audio = source_audio()
    rendered, meta = BREATH.render_audio_array(audio, 8000, base_timing())
    expected = (
        audio.shape[0]
        + meta["silence_samples"]
        + meta["wind_down_output_samples"]
        - meta["wind_down_source_advance_samples"]
    )
    check(rendered.shape[0] == expected == meta["output_samples"], "positive length/offset maths is exact")
    resume_out, resume_src = meta["resume_output_sample"], meta["resume_source_sample"]
    check(np.array_equal(rendered[resume_out], audio[resume_src]), "first resumed sample is source-identical")
    check(
        np.array_equal(
            rendered[meta["unity_resume_output_sample"] :],
            audio[meta["unity_resume_source_sample"] :],
        ),
        "unity-rate suffix is source-identical after the short resume fade",
    )
    check(meta["join_from_wind_down_max_abs"] == 0.0, "wind-down fade reaches exact silence")
    check(meta["join_to_resume_max_abs"] < 0.02, "resume search chooses a near-zero click-free join")


def positive_wind_up_mono() -> None:
    audio = source_audio(channels=1)
    config = base_timing()
    config.update(expected_channels=1, wind_up_seconds=0.25)
    rendered, meta = BREATH.render_audio_array(audio, 8000, config)
    expected = (
        audio.shape[0]
        + meta["silence_samples"]
        + meta["wind_down_output_samples"]
        + meta["wind_up_output_samples"]
        - meta["wind_down_source_advance_samples"]
        - meta["wind_up_source_advance_samples"]
    )
    check(rendered.shape[0] == expected, "wind-up length delta includes exact source advancement")
    check(
        np.array_equal(rendered[meta["resume_output_sample"]], audio[meta["resume_source_sample"]]),
        "wind-up starts on the exact stopped source sample",
    )
    check(
        np.array_equal(
            rendered[meta["unity_resume_output_sample"] :],
            audio[meta["unity_resume_source_sample"] :],
        ),
        "post-wind-up unity suffix is source-identical",
    )


def positive_modes_and_previews() -> None:
    with tempfile.TemporaryDirectory(prefix="p36-breath-") as temp_text:
        root = Path(temp_text).resolve()
        (root / "Saved").mkdir()
        source = root / "source.wav"
        sf.write(source, source_audio(), 8000, subtype="FLOAT", format="WAV")
        raw = {
            "mode": "APPLY",
            "run_id": "BAUDIO-HARNESS-APPLY",
            "project_root": str(root),
            "input_wav": str(source),
            "breath_time_seconds": 0.8,
            "wind_down_seconds": 0.4,
            "silence_seconds": 0.3,
            "wind_up_seconds": 0.0,
            "expected_sample_rate_hz": 8000,
            "expected_channels": 2,
            "output_subtype": "FLOAT",
            "confirm": "APPLY_BREATH_AUDIO:BAUDIO-HARNESS-APPLY",
        }
        config = BREATH.resolve_apply_config(raw)
        plan, payloads = BREATH.build_plan(config)
        check(not any(Path(path).exists() for path in plan["targets"]), "DRY planning writes no targets")
        applied = BREATH.apply_render(config, plan, payloads)
        check(applied["status"] == "passed", "APPLY record passes")
        check(all(Path(path).is_file() for path in plan["targets"]), "APPLY writes only the three named media targets")
        check(config["record_json"].is_file(), "APPLY writes a read-back record")
        check((config["backup_dir"] / "pre_apply_record.json").is_file(), "APPLY creates its pre-change backup record")
        check(config["waveform_preview_png"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "waveform preview is a PNG")
        check(config["spectrogram_preview_png"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "spectrogram preview is a PNG")

        revert_raw = {
            "mode": "REVERT",
            "run_id": "BAUDIO-HARNESS-REVERT",
            "source_run_id": "BAUDIO-HARNESS-APPLY",
            "project_root": str(root),
            "source_record_json": str(config["record_json"]),
            "confirm": "REVERT_BREATH_AUDIO:BAUDIO-HARNESS-APPLY",
        }
        reverted = BREATH.revert_render(BREATH.resolve_revert_config(revert_raw))
        check(reverted["status"] == "passed", "REVERT record passes")
        check(not any(Path(path).exists() for path in plan["targets"]), "REVERT restores originally absent targets")
        check(
            len(list(Path(reverted["backup_dir"]).glob("applied/**/*.*"))) == 3,
            "REVERT archives all applied bytes instead of deleting them",
        )


def negative_controls() -> None:
    audio = source_audio()
    base = base_timing()

    beyond = copy.deepcopy(base)
    beyond["breath_time_seconds"] = 4.0
    expect_error("T beyond file", "BREATH_TIME_BEYOND_FILE", lambda: BREATH.render_audio_array(audio, 8000, beyond))

    negative_silence = copy.deepcopy(base)
    negative_silence["silence_seconds"] = -0.01
    expect_error("N below zero", "SILENCE_NEGATIVE", lambda: BREATH.render_audio_array(audio, 8000, negative_silence))

    long_wind = copy.deepcopy(base)
    long_wind["wind_down_seconds"] = 3.3
    expect_error("W too long", "WIND_DOWN_TOO_LONG", lambda: BREATH.render_audio_array(audio, 8000, long_wind))

    wrong_channels = copy.deepcopy(base)
    wrong_channels["expected_channels"] = 1
    expect_error("mono/stereo mismatch", "CHANNEL_MISMATCH", lambda: BREATH.render_audio_array(audio, 8000, wrong_channels))

    wrong_rate = copy.deepcopy(base)
    wrong_rate["expected_sample_rate_hz"] = 48000
    expect_error("sample-rate mismatch", "SAMPLE_RATE_MISMATCH", lambda: BREATH.render_audio_array(audio, 8000, wrong_rate))


def main() -> int:
    positive_no_wind_up()
    positive_wind_up_mono()
    positive_modes_and_previews()
    negative_controls()
    print("BREATH_AUDIO_HARNESS_OK|positive=3/3|negative=5/5|checks=%d" % checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
