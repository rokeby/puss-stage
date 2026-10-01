"""Offline controls for walkin_plan.py. Run with the system Python."""

import math
import sys

from walkin_plan import check_plan, plan_walk


SEAT = {
    "x": -1289.59, "y": 79455.05, "z": 150.0,
    "pitch": 14.0, "yaw": 22.908, "roll": 0.0,
}
TARGET = {
    "x": 0.0, "y": 80000.0, "z": 180.0,
    "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
}
V_END = 250.0
EASE_S = 1.0
END_S = 25.52
FPS = 25.0
FOCAL0, FOCAL1 = 15.0, 35.0
FOCUS0, FOCUS1 = 1400.0, 100000.0
LANDED_S = 20.3
PILE_EDGE_CM = 190.0


def run_case(name, condition, detail):
    if condition:
        print("PASS %s" % name)
        return True
    print("FAIL %s: %s" % (name, detail))
    return False


def has_failure(failures, name):
    return any(failure.startswith(name + ":") for failure in failures)


def main():
    results = []
    keys, report = plan_walk(
        SEAT, TARGET, V_END, EASE_S, END_S, FPS,
        FOCAL0, FOCAL1, FOCUS0, FOCUS1, LANDED_S, PILE_EDGE_CM,
    )
    positive_failures = check_plan(keys, report, TARGET, V_END, LANDED_S, PILE_EDGE_CM)
    positive_ok = (
        not positive_failures
        and abs(report["start_s"] - 19.4) <= 0.2
        and abs(report["distance_cm"] - 1400.3) <= 1.0
    )
    results.append(run_case(
        "positive_control",
        positive_ok,
        "failures=%r start_s=%.6f distance_cm=%.6f"
        % (positive_failures, report["start_s"], report["distance_cm"]),
    ))

    shifted = list(keys)
    shifted[-1] = tuple(
        value + 10.0 if index == 1 else value
        for index, value in enumerate(shifted[-1])
    )
    shifted_failures = check_plan(
        shifted, report, TARGET, V_END, LANDED_S, PILE_EDGE_CM
    )
    results.append(run_case(
        "negative_end_pose",
        has_failure(shifted_failures, "end-pose"),
        "failures=%r" % shifted_failures,
    ))

    far_target = dict(TARGET)
    for axis in ("x", "y", "z"):
        far_target[axis] = SEAT[axis] + 3.0 * (TARGET[axis] - SEAT[axis])
    far_distance = math.sqrt(sum((far_target[axis] - SEAT[axis]) ** 2 for axis in ("x", "y", "z")))
    forced_speed = far_distance / report["duration_s"]
    fast_keys, fast_report = plan_walk(
        SEAT, far_target, forced_speed, 0.0, END_S, FPS,
        FOCAL0, FOCAL1, FOCUS0, FOCUS1, 0.0, PILE_EDGE_CM,
    )
    fast_failures = check_plan(
        fast_keys, fast_report, far_target, V_END, 0.0, PILE_EDGE_CM
    )
    same_duration = abs(fast_report["duration_s"] - report["duration_s"]) < 1.0e-9
    results.append(run_case(
        "negative_over_speed",
        same_duration and has_failure(fast_failures, "over-speed"),
        "same_duration=%s forced_speed=%.6f failures=%r"
        % (same_duration, forced_speed, fast_failures),
    ))

    pile_failures = check_plan(keys, report, TARGET, V_END, 25.0, PILE_EDGE_CM)
    results.append(run_case(
        "negative_pile_crossing",
        has_failure(pile_failures, "pile-crossing"),
        "failures=%r" % pile_failures,
    ))

    # Measured 30 Sep: the stalls camera holds 100000 cm and Passage 2 starts at
    # 600 cm, so focus racks far -> near during the walk. Mid-walk it must stay
    # near the stage (600 cm past the target plus the distance still to walk).
    # The old linear-in-time focus gave ~50300 cm here, about 37x the subject.
    rack_keys, rack_report = plan_walk(
        SEAT, TARGET, V_END, EASE_S, END_S, FPS,
        FOCAL0, FOCAL1, 100000.0, 600.0, LANDED_S, PILE_EDGE_CM,
    )
    mid_t = rack_report["start_s"] + 0.5 * rack_report["duration_s"]
    mid = min(rack_keys, key=lambda key: abs(key[0] - mid_t))
    remaining = math.sqrt(sum((TARGET[axis] - mid[1 + index]) ** 2 for index, axis in enumerate(("x", "y", "z"))))
    subject_cm = 600.0 + remaining
    focuses = [key[8] for key in rack_keys]
    rack_ok = (
        0.5 <= mid[8] / subject_cm <= 2.0
        and abs(focuses[0] - 100000.0) <= 1.0e-6 and abs(focuses[-1] - 600.0) <= 1.0e-9
        and all(b <= a + 1.0e-9 for a, b in zip(focuses, focuses[1:]))
    )
    results.append(run_case(
        "focus_tracks_subject",
        rack_ok,
        "mid t=%.3f focus=%.1fcm subject=%.1fcm first=%.1f last=%.1f"
        % (mid[0], mid[8], subject_cm, focuses[0], focuses[-1]),
    ))

    if not all(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

