#!/usr/bin/env python3
"""Offline positive/negative harness for shore_mocap_intensity.py."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("shore_mocap_intensity", HERE / "shore_mocap_intensity.py")
S = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)

passed = 0
failed = 0


def check(name: str, condition: bool, control: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS|{control}|{name}")
    else:
        failed += 1
        print(f"FAIL|{control}|{name}")


def raises(fn, *args, contains: str = "", **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # expected by negative controls
        return contains in str(exc)
    return False


def fake_tracks(duration: float = 4.0, source_fps: float = 30.0, moving: bool = True):
    seconds = np.arange(0.0, duration + 0.5 / source_fps, 1.0 / source_fps)
    ticks = np.rint(seconds * S.FBX_TICKS_PER_SECOND).astype(np.int64)
    tracks = {}
    for i, bone in enumerate(S.ENERGY_BONES):
        axes = {}
        for axis_i, axis in enumerate(S.AXES):
            amplitude = (i + 1) * (axis_i + 1) * 0.2 if moving else 0.0
            values = amplitude * np.sin(seconds * (1.0 + 0.1 * i))
            axes[axis] = (ticks, values.astype(np.float64))
        tracks[bone] = {"rotation": axes}
    root = {}
    for axis_i, axis in enumerate(S.AXES):
        values = (seconds * (axis_i + 1) if moving else np.zeros_like(seconds)).astype(np.float64)
        root[axis] = (ticks, values)
    tracks["pelvis"] = {"translation": root}
    return tracks


def parser_args(**updates):
    args = S.build_parser().parse_args(["--mode", "DRY"])
    for key, value in updates.items():
        setattr(args, key, value)
    return args


def run(real_source_root: str) -> int:
    # POSITIVE: exact three-way threshold boundaries.
    labels = S.labels_for_energy(np.array([0.0, 0.33, 0.34, 0.66, 0.67, 1.0]), 0.33, 0.67)
    check("threshold boundaries", labels.tolist() == ["CALM", "CALM", "MEDIUM", "MEDIUM", "FRENZY", "FRENZY"], "POS")

    # POSITIVE: short isolated spike is debounced into its neighbours.
    noisy = np.array(["CALM"] * 20 + ["FRENZY"] * 2 + ["CALM"] * 20)
    values = np.array([0.1] * 20 + [0.9] * 2 + [0.1] * 20)
    cleaned = S.debounce_labels(noisy, values, 5)
    check("short run debounce", np.all(cleaned == "CALM"), "POS")

    # POSITIVE: known synthetic motion has finite, varying energy at 24 fps.
    energy = S.motion_energy_from_tracks(fake_tracks(), fps=24.0, smoothing_seconds=0.5, root_weight=4.0)
    check("synthetic motion sampled at 24 fps", len(energy["source_seconds"]) == 97, "POS")
    check("synthetic motion energy finite and varying", bool(np.isfinite(energy["normalized_energy"]).all()) and
          float(np.ptp(energy["normalized_energy"])) > 0.5, "POS")

    # POSITIVE: source->Scene mapping reflects play-rate stretch and -22 frame nesting.
    rows = S.segment_rows(np.array(["CALM"] * 24 + ["FRENZY"] * 24), np.arange(48) / 24.0,
                          play_rate=0.6, scene_offset_seconds=-22 / 24.0)
    check("scene mapping", abs(rows[1]["scene3_in_seconds"] - (1 / 0.6 - 22 / 24)) < 1e-4, "POS")

    # NEGATIVE: invalid threshold order is refused.
    check("bad thresholds refused", raises(S.labels_for_energy, np.array([0.5]), 0.8, 0.2,
                                            contains="THRESHOLDS_REQUIRE"), "NEG")

    # NEGATIVE: static tracks cannot fabricate a useful intensity range.
    check("static motion refused", raises(S.motion_energy_from_tracks, fake_tracks(moving=False), fps=24.0,
                                           smoothing_seconds=0.5, root_weight=4.0,
                                           contains="ENERGY_RANGE_TOO_SMALL"), "NEG")

    # NEGATIVE: absent required bone is refused before analysis.
    missing = fake_tracks()
    del missing["head"]
    check("missing required bone refused", raises(S.motion_energy_from_tracks, missing, fps=24.0,
                                                    smoothing_seconds=0.5, root_weight=4.0), "NEG")

    # NEGATIVE: non-FBX bytes are rejected by the real parser.
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.fbx"
        bad.write_bytes(b"not an fbx")
        check("invalid FBX refused", raises(S.index_fbx, bad, contains="NOT_BINARY_FBX"), "NEG")

    # NEGATIVE: APPLY/REVERT confirmation strings are exact.
    with tempfile.TemporaryDirectory() as td:
        args = parser_args(mode="APPLY", confirm="yes", project_root=td)
        check("APPLY confirm refused", raises(S.apply_outputs, args, {"run": "T"}, [],
                                              contains="CONFIRM_REQUIRED"), "NEG")
        args = parser_args(mode="REVERT", confirm="yes", project_root=td)
        check("REVERT confirm refused", raises(S.revert_outputs, args, contains="CONFIRM_REQUIRED"), "NEG")

    # POSITIVE: REVERT parks newly generated files in the backup instead of deleting them.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        outputs = S.output_paths(root)
        backup, _ = S.make_backup(root, "HARNESS-R", outputs)
        for path in outputs.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"generated")
        outputs["json"].write_text(json.dumps({"run": "HARNESS-R", "backup": backup.relative_to(root).as_posix()}),
                                   encoding="utf-8")
        args = parser_args(mode="REVERT", confirm="REVERT S3MOCAPINTENSITY", project_root=td, run="HARNESS-R")
        S.revert_outputs(args)
        parked = backup / "reverted_outputs"
        check("REVERT parks new outputs", all(not path.exists() for path in outputs.values()) and
              all((parked / path.relative_to(root)).is_file() for path in outputs.values()), "POS")

    # POSITIVE real-source structural control: one full FBX, including 16 named rotation bones.
    real = Path(real_source_root) / "DerivedAssets" / "S3Sackcloth" / "bodies" / "Shore01_M56" / "Shore01_M56_Anim.fbx"
    if real.is_file():
        tracks, meta = S.load_animation_tracks(real)
        check("real FBX version and model index", meta["fbx_version"] >= 7300 and meta["models"] >= 300, "POS")
        check("real FBX 16-bone coverage", meta["energy_bones"] == sorted(S.ENERGY_BONES), "POS")
        check("real FBX root translation", meta["root_motion_bone"] in S.ROOT_CANDIDATES and
              len(tracks[meta["root_motion_bone"]]["translation"]) == 3, "POS")
    else:
        check("real source exists", False, "POS")

    print(f"S3_MOCAP_INTENSITY_HARNESS|passed={passed}|failed={failed}|positive=9|negative=6")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="E:/PussStage")
    ns = parser.parse_args()
    raise SystemExit(run(ns.source_root))
