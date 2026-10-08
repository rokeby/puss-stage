#!/usr/bin/env python3
"""Offline positive and negative controls for P11 music timing."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import numpy as np

import p11_music_timing as tool


passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def refuses(name, needle, function):
    try:
        function()
    except tool.Refused as exc:
        check(name, needle in str(exc))
    else:
        check(name, False)


def synthetic():
    rate, duration = 11025, 20.0
    t = np.arange(int(rate*duration))/rate
    audio = 0.03*np.sin(2*np.pi*220*t)
    for centre in (3.0, 9.0, 15.0):
        env = np.exp(-0.5*((t-centre)/0.45)**2)
        audio += 0.7*env*np.sin(2*np.pi*440*t)
    return audio.astype(np.float32), rate


samples, rate = synthetic()
rms = tool.rms_at_fps(samples, rate)
env, flurries = tool.detect_flurries(rms, 25, min_gap_s=3.0, rise_window_s=0.6, slow_window_s=2.5, threshold=0.35, max_count=8)
check("positive RMS is exactly 25 fps", len(rms) == 500)
check("positive three separated energy rises", len(flurries) == 3)
check("positive flurries chronological and numbered", [f["number"] for f in flurries] == [1, 2, 3] and [f["peakSeconds"] for f in flurries] == sorted(f["peakSeconds"] for f in flurries))
check("positive preview envelope bounded", float(env.min()) >= 0.0 and float(env.max()) <= 1.0)
tempos, beats = tool.normalize_tempo_and_beats([{"bpm": 258.398, "confidence": 1.0}], [{"timeSeconds": n} for n in range(6)])
check("positive tempo edge folds below 220 BPM", tempos[0]["bpm"] == 129.199 and len(beats) == 3)

with tempfile.TemporaryDirectory() as temp:
    png = Path(temp)/"test.png"
    result = {"durationSeconds": 20.0, "flurries": flurries, "waveform": [{"min": -0.5, "max": 0.5} for _ in range(100)], "previewEnvelope": env.tolist()}
    tool.render_preview(result, png)
    check("positive PNG signature", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp); output = root/"out"; old = root/"old"; backups = root/"backups"
    output.mkdir(); old.mkdir(); (output/"new.txt").write_text("new"); (old/"old.txt").write_text("old")
    record = root/"record.json"
    record.write_text(json.dumps({"mode": "APPLY", "output": str(output), "backup": str(old), "oldFiles": ["old.txt"]}))
    reverted = tool.revert_analysis_record(record, "TEST", backups)
    check("positive REVERT restores and retains recovery", (output/"old.txt").read_text() == "old" and (Path(reverted["preRevertBackup"])/"new.txt").read_text() == "new")

manifest = {"sourceRoot": "X:/", "tracks": [{"segment": name, "file": name+".wav", "selectedStartSeconds": 0, "selectedEndSeconds": 1, "sha256": "x"} for name in tool.OUTPUT_NAMES]}
tool.validate_manifest(manifest)
check("positive manifest order", True)
bad = copy.deepcopy(manifest); bad["tracks"][1]["file"] = bad["tracks"][0]["file"]
refuses("negative duplicate source", "DUPLICATE", lambda: tool.validate_manifest(bad))
bad = copy.deepcopy(manifest); bad["tracks"][3]["selectedEndSeconds"] = 0
refuses("negative empty selection", "MANIFEST_RANGE", lambda: tool.validate_manifest(bad))
bad = copy.deepcopy(manifest); bad["tracks"].reverse()
refuses("negative segment order", "MANIFEST_SEGMENTS", lambda: tool.validate_manifest(bad))
refuses("negative main-tree output", "MAIN_TREE_WRITE_REFUSED", lambda: tool.guard_output(Path("E:/PussStage/DerivedAssets/MusicAnalysis")))

snapshot = json.loads(Path(__file__).with_name("p11_timing_snapshot.json").read_text(encoding="utf-8"))
plan = tool.make_timing_plan(snapshot)
check("positive six passage plans", len(plan["passages"]) == 6)
check("positive P01 target is 73.52 s", plan["passages"]["Passage 1"]["targetSeconds"] == 73.52)
check("positive P05 late camera track found", plan["tracksPastNewEnd"] == [{"passage": "Passage 5", "track": "Camera.HeightOffsetCm", "keysAtOrPastNewEnd": [35426872, 35462872], "newEndInOldCoordinates": 31999105}])
check("positive all affected sections enumerated", len(plan["downstreamSectionsMoved"]) == 18)
check("positive total show shrink", abs(plan["totalDeltaSeconds"] - (-188.54079166666667)) < 1e-9)
check("positive Opening start remains fixed", plan["downstreamSectionsMoved"][0]["segment"] == "Passage 1" and plan["downstreamSectionsMoved"][0]["startShiftTicks"] == 0)
bad = copy.deepcopy(snapshot); bad["segments"][5][1] += 1
refuses("negative segment gap", "SEGMENT_GAP", lambda: tool.make_timing_plan(bad))
bad = copy.deepcopy(snapshot); del bad["musicSeconds"]["Passage 6"]
refuses("negative missing music", "MUSIC_MISSING", lambda: tool.make_timing_plan(bad))
bad = copy.deepcopy(snapshot); bad["segments"] = bad["segments"][:-1]
refuses("negative segment count", "SEGMENT_COUNT", lambda: tool.make_timing_plan(bad))

print(f"P11_OFFLINE_HARNESS|passed={passed}|failed={failed}")
raise SystemExit(1 if failed else 0)
