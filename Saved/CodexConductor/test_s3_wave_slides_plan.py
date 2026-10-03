"""Offline positive and required negative controls for s3_wave_slides_apply.py."""
import copy
import sys

from s3_wave_slides_apply import (
    INTERPOLATION_TOLERANCE_CM,
    PlanError,
    ROW_DELAYS,
    ROW_DIRECTIONS,
    TARGET_LABELS,
    VAMP_RANGE,
    compute_strike_frame_gate,
    plan_wave_slides,
)


def fixture_state():
    strike = compute_strike_frame_gate(
        parent_fps=24.0,
        child_fps=30.0,
        section_start_frame=0,
        child_start_frame_offset=0,
        child_strike_frame=300,
        time_scale=1.0,
    )
    actors = []
    placed_bounds = {
        "S3 Wave Row1 A": [-884.2, -284.2],
        "S3 Wave Row1 B": [186.2, 786.2],
        "S3 Wave Row2 A": [-834.0, -234.0],
        "S3 Wave Row2 B": [269.6, 869.6],
        "S3 Wave Row3 A": [-683.3, -83.3],
        "S3 Wave Row3 B": [280.4, 880.4],
    }
    for index, label in enumerate(TARGET_LABELS):
        actors.append({
            "label": label,
            "actor_path": "/Game/Test.%s" % label.replace(" ", "_"),
            "parent_label": "S3 Hangar Root",
            "binding_count": index % 2,
            "transform_track_count": 0,
            "landed_dock_y_bounds_cm": placed_bounds[label],
        })
    return {
        "fps": 24.0,
        "playback": [0, 6240],
        "strike": strike,
        "actors": actors,
    }


def expect_failure(name, function, text=None):
    try:
        function()
    except PlanError as exc:
        if text is not None and text not in str(exc):
            print("FAIL negative %s: wrong refusal %s" % (name, exc))
            return 1
        print("PASS negative %s: FAIL observed as required" % name)
        return 0
    print("FAIL negative %s: invalid case was accepted" % name)
    return 1


def main():
    failures = 0
    plan = plan_wave_slides(fixture_state())
    rows = plan["rows"]
    actor_rows = {row: sorted(actor["label"] for actor in plan["actors"]
                              if actor["row"] == row)
                  for row in (1, 2, 3)}
    positive = (
        plan["period_frames"] == 360 and
        tuple(row["direction"] for row in rows) == ROW_DIRECTIONS and
        tuple(row["delay_frames"] for row in rows) == ROW_DELAYS and
        all(row["first_key"] == plan["strike"]["frame"] - 1 for row in rows) and
        all(row["last_key"] == 6240 for row in rows) and
        all(abs(row["keys"][0][1]) <= 1.0e-9 and
            abs(row["keys"][1][1]) <= 1.0e-9 for row in rows) and
        all(row["seam"]["frames"] == list(VAMP_RANGE) and
            row["seam"]["error_cm"] <= 0.01 for row in rows) and
        plan["linear_interpolation_error_bound_cm"] <= INTERPOLATION_TOLERANCE_CM and
        all(actor_rows[row] == ["S3 Wave Row%d A" % row, "S3 Wave Row%d B" % row]
            for row in (1, 2, 3)) and
        plan["strike"]["frame"] == 240
    )
    if positive:
        print("PASS positive: period=360 delays=0/24/48 directions=+/-/+ seam equal pre-strike hold")
    else:
        print("FAIL positive: unexpected wave plan %r" % plan)
        failures += 1

    wrong_period = copy.deepcopy(fixture_state())
    wrong_period["period_frames"] = 288
    failures += expect_failure("wrong period 288 gives unequal vamp seam",
                               lambda: plan_wave_slides(wrong_period), "vamp seam unequal")

    same_direction = copy.deepcopy(fixture_state())
    same_direction["directions"] = [1, 1, 1]
    failures += expect_failure("same direction on all rows",
                               lambda: plan_wave_slides(same_direction), "row directions")

    missing_actor = copy.deepcopy(fixture_state())
    missing_actor["actors"] = missing_actor["actors"][:-1]
    failures += expect_failure("missing actor", lambda: plan_wave_slides(missing_actor),
                               "exactly the six")

    existing_track = copy.deepcopy(fixture_state())
    existing_track["actors"][2]["transform_track_count"] = 1
    failures += expect_failure("existing transform track",
                               lambda: plan_wave_slides(existing_track),
                               "already has a transform track")

    failures += expect_failure(
        "computed strike 216 stops",
        lambda: compute_strike_frame_gate(
            parent_fps=24.0,
            child_fps=30.0,
            section_start_frame=0,
            child_start_frame_offset=0,
            child_strike_frame=270,
            time_scale=1.0,
        ),
        "computed strike 216",
    )

    if failures == 0:
        table = ";".join(
            "row%d:dir=%+d,delay=%d,first=%d,last=%d,seam=%.9f" %
            (row["row"], row["direction"], row["delay_frames"], row["first_key"],
             row["last_key"], row["seam"]["error_cm"])
            for row in rows
        )
        print("S3_WAVE_SLIDES_HARNESS_OK|positive=1|negative=5|strike=%d|source=%s|%s" %
              (plan["strike"]["frame"], plan["strike"]["source"], table))
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
