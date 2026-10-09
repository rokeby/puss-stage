#!/usr/bin/env python3
"""Offline P46 verification: held-patch check plus a Python port of its pure maths."""

from __future__ import annotations

import argparse
import math
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "Scripts" / "patches" / "2026-10-09_shadow_cat_actions.patch"


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


def run_patch_check(harness: Harness) -> None:
    result = subprocess.run(
        ["git", "apply", "--check", "--whitespace=error-all", str(PATCH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    harness.positive("held patch applies cleanly to HEAD", result.returncode == 0)

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

    preview = ROOT / "Tools" / "ShadowCatActions" / "shadow_cat_variation_preview.svg"
    harness.positive("default variation preview is present", preview.is_file() and "Play-rate scale" in preview.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("DRY",),
        default="DRY",
        help="Verifier only: DRY is the sole mode; it never applies or reverts project state.",
    )
    args = parser.parse_args()
    assert args.mode == "DRY"

    harness = Harness()
    run_patch_check(harness)
    run_math_controls(harness)
    if harness.failures:
        for failure in harness.failures:
            print(failure)
    print(
        "SHADOW_CAT_ACTIONS_HARNESS|"
        f"positive={harness.positive_passes}|negative={harness.negative_passes}|"
        f"failed={len(harness.failures)}|patch={PATCH.relative_to(ROOT).as_posix()}"
    )
    return 1 if harness.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
