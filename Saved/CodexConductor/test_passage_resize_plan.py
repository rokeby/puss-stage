"""Offline contract harness for the held Passage-resize editor API.

This deliberately imports no Unreal modules.  It mirrors the arithmetic and
refusal gates proposed in Scripts/patches/2026-10-02_PR_passage_resize.patch so
the risky cases can be reviewed and exercised while the editor is owned by
other streams.
"""

from __future__ import annotations

import math
import unittest
from dataclasses import dataclass, field


FRAME_EPSILON_SECONDS = 0.0005  # Exact at the requested three-decimal contract.
DISTANCE_EPSILON_CM = 0.01


class ResizeRefused(ValueError):
    """The dry plan found a condition that makes APPLY unsafe."""


@dataclass(frozen=True)
class NeighbourExtent:
    label: str
    start_cm: float
    end_cm: float


@dataclass(frozen=True)
class ResizeInput:
    old_count: int
    old_duration_seconds: float
    old_route_length_cm: float
    target_seconds: float
    speed_cm_per_second: float = 250.0
    spacing_cm: float = 500.0
    lead_distance_cm: float = 250.0
    exit_clearance_cm: float = 250.0
    tick_resolution: float = 24000.0
    route_spline_length_cm: float = 0.0
    route_is_shaped: bool = False
    auto_fit_straight_route: bool = True
    override_rows: tuple[str, ...] = ()
    accept_override_loss: bool = False
    world_start_cm: float = 0.0
    neighbours: tuple[NeighbourExtent, ...] = ()
    later_cues: tuple[tuple[str, int], ...] = ()
    artist_master_content: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResizePlan:
    old_count: int
    new_count: int
    pairs_appended: int
    old_duration_seconds: float
    new_duration_seconds: float
    old_route_length_cm: float
    new_route_length_cm: float
    route_spline_length_cm: float
    target_frames: int
    interval_frames: int
    lead_frames: int
    tail_frames: int
    residual_distance_absorbed_cm: float
    cue_index_shifts: tuple[tuple[str, int, int], ...] = field(default_factory=tuple)
    master_playback_delta_frames: int = 0
    managed_sections_move_frames: int = 0
    artist_master_content_not_rippled: tuple[str, ...] = field(default_factory=tuple)


def _rounded_frame(seconds: float, tick_resolution: float) -> int:
    # Match FMath::RoundToInt for the positive values accepted by this planner.
    return math.floor(seconds * tick_resolution + 0.5)


def plan_resize(values: ResizeInput) -> ResizePlan:
    """Plan PreserveSpeedAndSpacing or raise with the APPLY refusal reason."""

    if values.old_count < 1:
        raise ResizeRefused("the source Passage has no Wing Pairs")
    if min(
        values.target_seconds,
        values.speed_cm_per_second,
        values.spacing_cm,
        values.tick_resolution,
    ) <= 0.0:
        raise ResizeRefused("duration, speed, spacing and tick resolution must be positive")
    if min(values.lead_distance_cm, values.exit_clearance_cm) < 0.0:
        raise ResizeRefused("entry and exit clearances cannot be negative")

    target_frames = _rounded_frame(values.target_seconds, values.tick_resolution)
    represented_seconds = target_frames / values.tick_resolution
    if abs(represented_seconds - values.target_seconds) > FRAME_EPSILON_SECONDS:
        raise ResizeRefused(
            "target duration is not exactly representable to three decimals at this tick resolution"
        )

    travel_distance_cm = values.target_seconds * values.speed_cm_per_second
    usable_distance_cm = (
        travel_distance_cm - values.lead_distance_cm - values.exit_clearance_cm
    )
    if usable_distance_cm < -DISTANCE_EPSILON_CM:
        raise ResizeRefused("target route is shorter than its entry and exit clearances")

    new_count = 1 + math.floor(
        max(0.0, usable_distance_cm) / values.spacing_cm + 1.0e-12
    )
    interval_frames = _rounded_frame(
        values.spacing_cm / values.speed_cm_per_second,
        values.tick_resolution,
    )
    lead_frames = _rounded_frame(
        values.lead_distance_cm / values.speed_cm_per_second,
        values.tick_resolution,
    )
    tail_frames = target_frames - lead_frames - (new_count - 1) * interval_frames
    if interval_frames < 1 or tail_frames < 0:
        raise ResizeRefused("the frame residual cannot close in a non-negative TailFrames value")

    tail_distance_cm = (
        tail_frames / values.tick_resolution * values.speed_cm_per_second
    )
    new_route_length_cm = (
        values.lead_distance_cm
        + (new_count - 1) * values.spacing_cm
        + tail_distance_cm
    )
    new_duration_seconds = (
        lead_frames + (new_count - 1) * interval_frames + tail_frames
    ) / values.tick_resolution
    if abs(new_duration_seconds - values.target_seconds) > FRAME_EPSILON_SECONDS:
        raise ResizeRefused("the absorbed frame residual does not close on the target duration")

    if values.override_rows and not values.accept_override_loss:
        raise ResizeRefused(
            "local timing/layout overrides would be erased: " + ", ".join(values.override_rows)
        )

    route_short = (
        values.route_spline_length_cm + DISTANCE_EPSILON_CM < new_route_length_cm
    )
    if route_short and values.route_is_shaped:
        raise ResizeRefused(
            f"a shaped route would require Auto Fit to reach {new_route_length_cm:.3f} cm"
        )
    if route_short and not values.auto_fit_straight_route:
        raise ResizeRefused(
            f"route is too short ({values.route_spline_length_cm:.3f} cm; "
            f"{new_route_length_cm:.3f} cm required)"
        )

    world_end_cm = values.world_start_cm + new_route_length_cm
    proposed_min, proposed_max = sorted((values.world_start_cm, world_end_cm))
    overlaps = []
    for neighbour in values.neighbours:
        neighbour_min, neighbour_max = sorted((neighbour.start_cm, neighbour.end_cm))
        penetration = min(proposed_max, neighbour_max) - max(proposed_min, neighbour_min)
        if penetration > DISTANCE_EPSILON_CM:
            overlaps.append(neighbour.label)
    if overlaps:
        raise ResizeRefused("new world extent overlaps: " + ", ".join(overlaps))

    old_frames = _rounded_frame(values.old_duration_seconds, values.tick_resolution)
    appended = max(0, new_count - values.old_count)
    index_shifts = tuple(
        (guid, old_index, old_index + appended)
        for guid, old_index in values.later_cues
    )
    delta_frames = target_frames - old_frames
    return ResizePlan(
        old_count=values.old_count,
        new_count=new_count,
        pairs_appended=appended,
        old_duration_seconds=values.old_duration_seconds,
        new_duration_seconds=new_duration_seconds,
        old_route_length_cm=values.old_route_length_cm,
        new_route_length_cm=new_route_length_cm,
        route_spline_length_cm=values.route_spline_length_cm,
        target_frames=target_frames,
        interval_frames=interval_frames,
        lead_frames=lead_frames,
        tail_frames=tail_frames,
        residual_distance_absorbed_cm=tail_distance_cm - values.exit_clearance_cm,
        cue_index_shifts=index_shifts,
        master_playback_delta_frames=delta_frames,
        managed_sections_move_frames=delta_frames,
        artist_master_content_not_rippled=values.artist_master_content,
    )


class PassageResizePlanTests(unittest.TestCase):
    def test_47_4_seconds_23_pairs_to_exact_180(self) -> None:
        plan = plan_resize(
            ResizeInput(
                old_count=23,
                old_duration_seconds=47.4,
                old_route_length_cm=11850.0,
                target_seconds=180.0,
                route_spline_length_cm=46000.0,
                later_cues=(("scene-02", 31), ("passage-03-wing-001", 32)),
                artist_master_content=("Markers: DirectorNote@120000",),
            )
        )
        self.assertEqual(plan.new_count, 90)
        self.assertEqual(plan.pairs_appended, 67)
        self.assertEqual(plan.interval_frames, 48000)
        self.assertEqual(plan.tail_frames, 24000)
        self.assertEqual(plan.target_frames, 4_320_000)
        self.assertEqual(plan.new_duration_seconds, 180.0)
        self.assertEqual(plan.new_route_length_cm, 45000.0)
        self.assertEqual(
            plan.cue_index_shifts,
            (("scene-02", 31, 98), ("passage-03-wing-001", 32, 99)),
        )
        self.assertEqual(plan.artist_master_content_not_rippled, ("Markers: DirectorNote@120000",))

    def test_refuses_residual_that_cannot_close_exactly(self) -> None:
        with self.assertRaisesRegex(ResizeRefused, "not exactly representable"):
            plan_resize(
                ResizeInput(
                    old_count=1,
                    old_duration_seconds=1.0,
                    old_route_length_cm=250.0,
                    target_seconds=1.2,
                    tick_resolution=2.0,
                    lead_distance_cm=0.0,
                    exit_clearance_cm=0.0,
                    route_spline_length_cm=1000.0,
                )
            )

    def test_refuses_shaped_route_that_would_need_auto_fit(self) -> None:
        with self.assertRaisesRegex(ResizeRefused, "shaped route would require Auto Fit"):
            plan_resize(
                ResizeInput(
                    old_count=23,
                    old_duration_seconds=47.4,
                    old_route_length_cm=11850.0,
                    target_seconds=180.0,
                    route_spline_length_cm=12000.0,
                    route_is_shaped=True,
                )
            )

    def test_refuses_local_override_loss_without_acknowledgement(self) -> None:
        with self.assertRaisesRegex(ResizeRefused, "overrides would be erased"):
            plan_resize(
                ResizeInput(
                    old_count=23,
                    old_duration_seconds=47.4,
                    old_route_length_cm=11850.0,
                    target_seconds=180.0,
                    route_spline_length_cm=46000.0,
                    override_rows=("P02 Wing 007",),
                )
            )

    def test_refuses_overlap_with_neighbour(self) -> None:
        with self.assertRaisesRegex(ResizeRefused, "overlaps: Scene 02 hangar"):
            plan_resize(
                ResizeInput(
                    old_count=23,
                    old_duration_seconds=47.4,
                    old_route_length_cm=11850.0,
                    target_seconds=180.0,
                    route_spline_length_cm=46000.0,
                    neighbours=(NeighbourExtent("Scene 02 hangar", 44000.0, 47000.0),),
                )
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
