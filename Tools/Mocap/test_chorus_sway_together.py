#!/usr/bin/env python3
"""Offline positive/negative harness for the P20 chorus-sway planner/editor helpers."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


P = load_module("chorus_sway_together", HERE / "chorus_sway_together.py")
E = load_module("s3_chorus_sway_editor", ROOT / "Saved/CodexConductor/s3_chorus_sway.py")
passed = 0
failed = 0
positive = 0
negative = 0


def check(name: str, condition: bool, control: str) -> None:
    global passed, failed, positive, negative
    if control == "POS":
        positive += 1
    else:
        negative += 1
    if condition:
        passed += 1
        print(f"PASS|{control}|{name}")
    else:
        failed += 1
        print(f"FAIL|{control}|{name}")


def raises(fn, *args, contains: str = "", **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        return contains in str(exc)
    return False


def run(source_root: str) -> int:
    # POSITIVE: the six selected source periods all stay inside 0.75x-1.30x of 0.6.
    sway = json.loads((Path(source_root) / "DerivedAssets/S3MocapIntensity/s3_sway_runs.json").read_text())
    selected = []
    for spec in P.FIGURES:
        selected.extend(P.selected_run(sway, spec["id"], bounds) for bounds in spec["spans"])
    check("selected rates within bound", all(0.45 <= row["play_rate"] <= 0.78 for row in selected), "POS")

    # POSITIVE: overlap schedule exactly covers the local window and overlaps repeats by 24 frames.
    spans = [selected[0], selected[1]]
    schedule = P.build_schedule((3502, 4222), 24.0, spans, -1.074, 1.0)
    check("schedule covers window", schedule[0]["scene_range"][0] == 3502 and
          schedule[-1]["scene_range"][1] == 4222, "POS")
    check("repeat overlap is one second", all(a["scene_range"][1] - b["scene_range"][0] == 24
                                                for a, b in zip(schedule, schedule[1:])), "POS")
    check("entry and exit easing are 36 frames", schedule[0]["ease_in_frames"] == 36 and
          schedule[-1]["ease_out_frames"] == 36, "POS")

    # POSITIVE: default phases are an even 60-degree spread after their bounded nudges.
    args = P.parser().parse_args(["--mode", "DRY", "--run", "HARNESS", "--source-root", source_root])
    plan, tracks = P.build_plan(args)
    phases = [row["phase_at_window_start_deg"] for row in plan["figures"]]
    check("default phase spread", all(abs(actual - expected) < 0.01
                                       for actual, expected in zip(phases, (0, 60, 120, 180, 240, 300))), "POS")
    check("phase nudges bounded", all(abs(row["default_phase_nudge_s"]) <= 1.8
                                       for row in plan["figures"]), "POS")
    check("phrase analysis in declared band", 6.8 <= plan["phrase"]["period_s"] <= 7.6 and
          len(plan["phrase"]["maxima_s"]) >= 7, "POS")
    png = P.render_preview(plan, tracks)
    check("preview is PNG", png.startswith(b"\x89PNG\r\n\x1a\n") and len(png) > 20000, "POS")

    # POSITIVE: continuation math handles both first-loop remainder and a wrapped loop.
    direct = E.continuation_first_loop_offset(0, 100, 24, 0.6, 2400000, 0, 0, 0, 24000)
    wrapped = E.continuation_first_loop_offset(0, 5000, 24, 0.6, 2400000, 0, 0, 0, 24000)
    check("continuation direct", direct == 60000, "POS")
    check("continuation wraps", wrapped == 600000, "POS")
    sample = {"name": "S", "range": [0, 1], "animation": "A", "start_offset": 0,
              "end_offset": 0, "first_loop_offset": 0, "play_rate": 0.6, "reverse": False,
              "row": 0, "active": True, "ease": {}, "weight": []}
    near = dict(sample, play_rate=0.60005)
    check("readback rate tolerance", E.snapshot_matches(near, sample)[0], "POS")

    # NEGATIVE controls: unsafe timings, stale evidence, and malformed inputs are refused.
    check("low play rate refused", raises(P.validate_play_rate, 0.449, contains="PLAY_RATE_OUT_OF_BOUNDS"), "NEG")
    check("high play rate refused", raises(P.validate_play_rate, 0.781, contains="PLAY_RATE_OUT_OF_BOUNDS"), "NEG")
    check("phase nudge refused", raises(E.validate_phase_nudge, 1.801, 3.6,
                                         contains="PHASE_NUDGE_EXCEEDS_HALF_PERIOD"), "NEG")
    too_short = [{"source_in": 0.0, "source_out": 1.0, "play_rate": 0.6, "signal": "x.y.z"}]
    check("short loop refused", raises(E.build_schedule, (0, 720), 24, too_short, 0.0, 1.0, 1.5, 3.6,
                                        contains="LOOP_TOO_SHORT_FOR_BLEND"), "NEG")
    check("missing figure refused", raises(P.selected_run, {"figures": []}, "missing", (0, 1),
                                            contains="FIGURE_MISSING"), "NEG")
    check("bad continuation refused", raises(E.continuation_first_loop_offset, 10, 0, 24, 0.6,
                                               1000, 0, 0, 0, 24000,
                                               contains="CONTINUATION_BEFORE_SECTION"), "NEG")
    mismatch = dict(sample, range=[0, 2])
    check("section mismatch detected", not E.snapshot_matches(mismatch, sample)[0], "NEG")
    with tempfile.TemporaryDirectory() as directory:
        bad = Path(directory) / "bad.wav"
        bad.write_bytes(b"not wav")
        check("malformed WAV refused", raises(P.phrase_maxima, bad, contains="WAV_READ_FAILED"), "NEG")
        silent = Path(directory) / "short.wav"
        with wave.open(str(silent), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
            wav.writeframes(np.zeros(2400, dtype="<i2").tobytes())
        check("missing chorus refused", raises(P.phrase_maxima, silent, contains="CHORUS_WINDOW_NOT_IN_WAV"), "NEG")

    print(f"S3_CHORUS_SWAY_HARNESS|passed={passed}|failed={failed}|positive={positive}|negative={negative}")
    return 1 if failed else 0


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "E:/PussStage"
    raise SystemExit(run(source))
