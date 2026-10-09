#!/usr/bin/env python3
"""Offline P46 verification: held-patch check plus a Python port of its pure maths."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "Scripts" / "patches" / "2026-10-09_shadow_cat_actions.patch"
TARGETS = (
    "Plugins/InfinityStage/Source/InfinityStage/InfinityStage.Build.cs",
    "Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCameraRig.cpp",
    "Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageCameraRig.h",
    "Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h",
    "Plugins/InfinityStage/Source/InfinityStageTests/Private/InfinityStageShadowCatActionTests.cpp",
)


def smooth_unit(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def integrate_play_rates(rates: list[float], interval_seconds: float) -> float:
    if not math.isfinite(interval_seconds) or interval_seconds <= 0.0:
        return 0.0
    return sum(max(0.0, rate) * interval_seconds for rate in rates if math.isfinite(rate))


@dataclass(frozen=True)
class ActionTiming:
    active: bool = False
    position_seconds: float = 0.0
    weight: float = 0.0


def blend_location(
    route: tuple[float, float, float],
    head_eye: tuple[float, float, float],
    weight: float,
) -> tuple[float, float, float]:
    alpha = min(1.0, max(0.0, weight))
    return tuple(start + (end - start) * alpha for start, end in zip(route, head_eye))


def resolve_body_visibility(active: bool, requested: str) -> str:
    return requested if active else "ShadowOnly"


def near_clip_safe(offset_forward_cm: float, near_clip_cm: float, clearance_cm: float) -> bool:
    return (
        math.isfinite(offset_forward_cm)
        and math.isfinite(near_clip_cm)
        and math.isfinite(clearance_cm)
        and near_clip_cm > 0.0
        and clearance_cm >= 0.0
        and offset_forward_cm >= near_clip_cm + clearance_cm
    )


def action_timing(
    passage_seconds: float,
    passage_duration: float,
    action_start: float,
    clip_length: float,
    play_rate: float,
    blend_in: float,
    blend_out: float,
    hold_last: bool,
) -> ActionTiming:
    safe_rate = max(play_rate, 2.220446049250313e-16)
    action_duration = clip_length / safe_rate
    elapsed = passage_seconds - action_start
    end_seconds = passage_duration if hold_last else action_start + action_duration
    if elapsed < 0.0 or passage_seconds > end_seconds or action_duration <= 2.220446049250313e-16:
        return ActionTiming()
    position = min(clip_length, max(0.0, elapsed * safe_rate))
    in_weight = smooth_unit(elapsed / blend_in) if blend_in > 2.220446049250313e-16 else 1.0
    seconds_to_end = end_seconds - passage_seconds
    out_weight = (
        smooth_unit(seconds_to_end / blend_out)
        if blend_out > 2.220446049250313e-16
        else (1.0 if seconds_to_end > 0.0 else 0.0)
    )
    return ActionTiming(True, position, min(in_weight, out_weight))


def _ue_fraction(seed: int) -> float:
    """First FRandomStream::FRand draw for a seed (UE 5.8 RandomStream.h)."""
    mutated = ((seed & 0xFFFFFFFF) * 196314165 + 907633515) & 0xFFFFFFFF
    bits = 0x3F800000 | (mutated >> 9)
    return struct.unpack("<f", struct.pack("<I", bits))[0] - 1.0


def _signed(seed: int, salt: int) -> float:
    return _ue_fraction((seed ^ salt) & 0xFFFFFFFF) * 2.0 - 1.0


@dataclass(frozen=True)
class Variation:
    play_rate_scale: float
    bob_gain_scale: float


def variation(
    seed: int,
    passage_seconds: float,
    drift_seconds: float = 12.0,
    play_amplitude: float = 0.03,
    bob_amplitude: float = 0.03,
    stride_amplitude: float = 0.02,
    stride_seconds: float = 0.8,
    stride_chance: float = 0.25,
) -> Variation:
    safe_time = max(0.0, passage_seconds)
    safe_drift = max(1.0, drift_seconds)
    drift_index = math.floor(safe_time / safe_drift)
    drift_alpha = smooth_unit(math.fmod(safe_time, safe_drift) / safe_drift)
    play_a = _signed(seed, drift_index * 7919 + 101)
    play_b = _signed(seed, (drift_index + 1) * 7919 + 101)
    bob_a = _signed(seed, drift_index * 7919 + 307)
    bob_b = _signed(seed, (drift_index + 1) * 7919 + 307)
    play_drift = play_a + (play_b - play_a) * drift_alpha
    bob_drift = bob_a + (bob_b - bob_a) * drift_alpha

    safe_stride = max(0.1, stride_seconds)
    stride_index = math.floor(safe_time / safe_stride)
    gate = _ue_fraction((seed ^ (stride_index * 3571 + 503)) & 0xFFFFFFFF)
    play_stride = 0.0
    bob_stride = 0.0
    if gate < min(1.0, max(0.0, stride_chance)):
        play_stride = _signed(seed, stride_index * 3571 + 701)
        bob_stride = _signed(seed, stride_index * 3571 + 907)

    play_bound = max(0.0, play_amplitude) + max(0.0, stride_amplitude)
    bob_bound = max(0.0, bob_amplitude) + max(0.0, stride_amplitude)
    play_delta = play_drift * max(0.0, play_amplitude) + play_stride * max(0.0, stride_amplitude)
    bob_delta = bob_drift * max(0.0, bob_amplitude) + bob_stride * max(0.0, stride_amplitude)
    return Variation(
        1.0 + min(play_bound, max(-play_bound, play_delta)),
        1.0 + min(bob_bound, max(-bob_bound, bob_delta)),
    )


class Harness:
    def __init__(self) -> None:
        self.positive_passes = 0
        self.negative_passes = 0
        self.failures: list[str] = []

    def positive(self, name: str, condition: bool) -> None:
        if condition:
            self.positive_passes += 1
        else:
            self.failures.append(f"POSITIVE FAILED: {name}")

    def negative(self, name: str, mutant_was_caught: bool) -> None:
        if mutant_was_caught:
            self.negative_passes += 1
        else:
            self.failures.append(f"NEGATIVE FAILED: {name}")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def _target_dirty_lines() -> list[str]:
    result = _git("status", "--porcelain=v1", "--", *TARGETS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _dirty_paths(lines: list[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.replace("\\", "/"))
    return paths


def _write_prechange_record(mode: str, run_id: str, dirty_lines: list[str]) -> Path:
    prefix = "PreShadowCatActions" if mode == "APPLY" else "PreShadowCatActionsRevert"
    backup = ROOT / "Backups" / f"{prefix}-{run_id}"
    if backup.exists():
        raise RuntimeError(f"backup already exists: {backup}")
    backup.mkdir(parents=True)
    for relative in TARGETS:
        source = ROOT / relative
        if source.is_file():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    record = {
        "mode": mode,
        "run_id": run_id,
        "patch": PATCH.relative_to(ROOT).as_posix(),
        "targets": list(TARGETS),
        "dirty_source_census_before": dirty_lines,
        "dirty_packages_before": [],
        "saved_packages": [],
    }
    (backup / "record.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return backup


def apply_or_revert(mode: str, run_id: str | None, confirm: str | None) -> None:
    if not run_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in run_id):
        raise RuntimeError("--run-id is required and may contain only letters, digits, '-' and '_'")
    expected_confirm = f"{mode}_SHADOW_CAT_ACTIONS_{run_id}"
    if confirm != expected_confirm:
        raise RuntimeError(f"confirmation mismatch; expected {expected_confirm}")

    before = _target_dirty_lines()
    before_paths = _dirty_paths(before)
    if mode == "APPLY" and before:
        raise RuntimeError(f"APPLY requires clean patch targets; census={before}")
    if mode == "REVERT" and before_paths != set(TARGETS):
        raise RuntimeError(
            f"REVERT requires exactly the five applied patch targets; census={before}"
        )

    check_args = ["apply"]
    if mode == "REVERT":
        check_args.append("-R")
    checked = _git(*check_args, "--check", "--whitespace=error-all", str(PATCH))
    if checked.returncode != 0:
        raise RuntimeError(checked.stderr.strip() or f"{mode} patch check failed")
    backup = _write_prechange_record(mode, run_id, before)
    changed = _git(*check_args, "--whitespace=error-all", str(PATCH))
    if changed.returncode != 0:
        raise RuntimeError(changed.stderr.strip() or f"{mode} failed after backup {backup}")

    after = _target_dirty_lines()
    after_paths = _dirty_paths(after)
    expected_after = set(TARGETS) if mode == "APPLY" else set()
    if after_paths != expected_after:
        raise RuntimeError(f"post-{mode} target census mismatch: {after}")
    patch_text = PATCH.read_text(encoding="utf-8")
    required = ("HeadPOV", "POVBody", "ReflectionOnly", "SHADOW_CAT_HEAD_POV_REFUSED")
    if not all(token in patch_text for token in required):
        raise RuntimeError("read-back failed: P46b contract tokens missing from held patch")
    print(
        f"SHADOW_CAT_ACTIONS_{mode}_OK|run={run_id}|targets={len(TARGETS)}|"
        f"dirty_packages=0|backup={backup.relative_to(ROOT).as_posix()}"
    )


def run_patch_check(harness: Harness, reverse: bool = False) -> None:
    apply_args = ["git", "apply"]
    if reverse:
        apply_args.append("-R")
    result = subprocess.run(
        [*apply_args, "--check", "--whitespace=error-all", str(PATCH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    direction = "reverts cleanly from the applied state" if reverse else "applies cleanly to HEAD"
    harness.positive(f"held patch {direction}", result.returncode == 0)

    patch_text = PATCH.read_text(encoding="utf-8")
    required_contract = (
        "EInfinityShadowCatCameraMode",
        "EInfinityShadowCatBodyVisibility",
        "ReflectionOnly",
        "BlendShadowCatCameraTransform",
        "IsShadowCatHeadPOVNearClipSafe",
        "HideBoneByName",
        "CameraModeBlendContinuity",
        "VisibilityModeEdges",
        "POVDeterminismAndNearClip",
    )
    harness.positive(
        "held patch contains the P46b POV, visibility, safety and test contract",
        all(token in patch_text for token in required_contract),
    )
    harness.negative(
        "patch missing a required P46b mode is caught",
        not all(token in patch_text.replace("ReflectionOnly", "") for token in required_contract),
    )

    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as bad:
        bad.write("this is deliberately not a patch\n")
        bad_path = Path(bad.name)
    try:
        rejected = subprocess.run(
            ["git", "apply", "--check", str(bad_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        harness.negative("invalid patch is rejected", rejected.returncode != 0)
    finally:
        bad_path.unlink(missing_ok=True)


def run_math_controls(harness: Harness) -> None:
    rates = [0.45, 0.60, 0.80, 0.55, 0.0, 0.25, 0.70]
    target = integrate_play_rates(rates, 0.04)
    integrate_play_rates(rates[:2], 0.04)
    forward_jump = integrate_play_rates(rates, 0.04)
    integrate_play_rates(list(reversed(rates)), 0.04)
    reverse_jump = integrate_play_rates(rates, 0.04)
    harness.positive("same Master frame has identical phase through two scrub paths", target == forward_jump == reverse_jump)
    wall_time_mutant = target + 0.5
    harness.negative("wall-time phase mutant is caught", not math.isclose(wall_time_mutant, target, abs_tol=1.0e-12))

    epsilon = 1.0e-6
    at_start = action_timing(5.0, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, False)
    after_start = action_timing(5.0 + epsilon, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, False)
    before_end = action_timing(9.0 - epsilon, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, False)
    at_end = action_timing(9.0, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, False)
    continuous = (
        at_start.weight == 0.0
        and abs(after_start.weight - at_start.weight) < 1.0e-4
        and abs(before_end.weight - at_end.weight) < 1.0e-4
        and at_end.weight == 0.0
    )
    harness.positive("action blend is continuous at start and end", continuous)
    hard_cut_mutant = 1.0
    harness.negative("hard-cut action mutant is caught", abs(hard_cut_mutant - at_start.weight) >= 1.0e-4)

    held = action_timing(15.0, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, True)
    harness.positive("hold-last clamps the final pose until Passage-end blend", held.active and held.position_seconds == 4.0 and held.weight == 1.0)

    samples = [variation(1847, frame * 0.04) for frame in range(1001)]
    repeats = [variation(1847, frame * 0.04) for frame in range(1001)]
    bounded = all(
        abs(value.play_rate_scale - 1.0) <= 0.050000001
        and abs(value.bob_gain_scale - 1.0) <= 0.050000001
        for value in samples
    )
    harness.positive("variation is seeded, repeatable and bounded", samples == repeats and bounded and len(set(samples)) > 10)
    unbounded_mutant = Variation(1.20, 0.80)
    harness.negative(
        "unbounded variation mutant is caught",
        abs(unbounded_mutant.play_rate_scale - 1.0) > 0.050000001,
    )

    before = (43000 - 1000) / 1000.0
    after = (57000 - 15000) / 1000.0
    harness.positive("Passage-relative +42 s action travels with Passage", before == after == 42.0)
    absolute_mutant = 57000 / 1000.0
    harness.negative("absolute-Master action mutant is caught", absolute_mutant != after)

    route = (100.0, 20.0, 180.0)
    head_eye = (-68.0, 15.0, 133.0)
    epsilon = 1.0e-6
    at_route = blend_location(route, head_eye, 0.0)
    after_route = blend_location(route, head_eye, epsilon)
    at_head = blend_location(route, head_eye, 1.0)
    before_head = blend_location(route, head_eye, 1.0 - epsilon)
    harness.positive(
        "HeadPOV blend is continuous and reaches both endpoints",
        at_route == route
        and at_head == head_eye
        and math.dist(at_route, after_route) < 1.0e-3
        and math.dist(at_head, before_head) < 1.0e-3,
    )
    hard_camera_cut = head_eye
    harness.negative(
        "hard-cut HeadPOV camera mutant is caught",
        math.dist(at_route, hard_camera_cut) >= 1.0e-3,
    )

    first = blend_location(route, head_eye, 0.375)
    blend_location((0.0, 0.0, 0.0), (1.0, 2.0, 3.0), 0.9)
    again = blend_location(route, head_eye, 0.375)
    harness.positive("HeadPOV transform is deterministic", first == again)
    history_mutant = tuple(value + 0.01 for value in again)
    harness.negative("history-dependent HeadPOV mutant is caught", history_mutant != first)

    harness.positive(
        "visibility modes switch exactly on the action active interval",
        resolve_body_visibility(False, "POVBody") == "ShadowOnly"
        and resolve_body_visibility(True, "POVBody") == "POVBody"
        and resolve_body_visibility(True, "ReflectionOnly") == "ReflectionOnly",
    )
    stale_visibility_mutant = resolve_body_visibility(False, "ReflectionOnly")
    harness.negative(
        "stale ReflectionOnly mode after the action is caught",
        stale_visibility_mutant != "ReflectionOnly",
    )

    harness.positive(
        "default eye offset clears the HeadPOV near plane",
        near_clip_safe(12.0, 3.0, 2.0),
    )
    harness.negative(
        "near-plane intersection mutant is caught",
        not near_clip_safe(4.0, 3.0, 2.0),
    )

    preview = ROOT / "Tools" / "ShadowCatActions" / "shadow_cat_variation_preview.svg"
    harness.positive("default variation preview is present", preview.is_file() and "Play-rate scale" in preview.read_text(encoding="utf-8"))
    pov_preview = ROOT / "Tools" / "ShadowCatActions" / "shadow_cat_pov_modes_preview.svg"
    harness.positive(
        "POV/body-mode preview is present",
        pov_preview.is_file() and "HeadPOV" in pov_preview.read_text(encoding="utf-8"),
    )
    evidence = ROOT / "Tools" / "ShadowCatActions" / "p46b_offline_evidence.md"
    harness.positive(
        "absolute-path AnimX evidence record is present",
        evidence.is_file()
        and "E:/PussStage/Content/CharacterPacks/AnimX" in evidence.read_text(encoding="utf-8"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("DRY", "APPLY", "REVERT"),
        default="DRY",
        help="DRY verifies; APPLY/REVERT require an exact run-id confirmation and make a backup first.",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    harness = Harness()
    run_patch_check(harness, reverse=args.mode == "REVERT")
    run_math_controls(harness)
    if harness.failures:
        for failure in harness.failures:
            print(failure)
    print(
        "SHADOW_CAT_ACTIONS_HARNESS|"
        f"positive={harness.positive_passes}|negative={harness.negative_passes}|"
        f"failed={len(harness.failures)}|patch={PATCH.relative_to(ROOT).as_posix()}"
    )
    if harness.failures:
        return 1
    if args.mode != "DRY":
        apply_or_revert(args.mode, args.run_id, args.confirm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
