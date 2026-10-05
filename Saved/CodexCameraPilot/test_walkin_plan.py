"""Offline controls for walkin_plan.py. Run with the system Python."""

import math
import json
import os
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
TRANSITIONS_PATH = os.path.join(os.path.dirname(__file__), "walkin_transitions.json")


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
    with open(TRANSITIONS_PATH, "r", encoding="utf-8") as handle:
        transitions = json.load(handle)

    expected_identity = {
        "OPENING": ("LS_Opening_Curtain_Baked", "Opening — Stalls Camera", "Passage 1", None),
        "I1": ("LS_Interaction_01_WashingTheBoy", "Interaction 1 — Stalls Camera", "Passage 2", "InfinityStage.Mouth.P02"),
        "I2": ("LS_Interaction_02_Turnips", "Interaction 2 — Stalls Camera", "Passage 3", "InfinityStage.Mouth.P03"),
        "I3": ("LS_Interaction_03_ForgetsHisName", "Interaction 3 — Stalls Camera", "Passage 4", "InfinityStage.Mouth.P04"),
        "I4": ("LS_Interaction_04_GetsAName", "Interaction 4 — Stalls Camera", "Passage 5", "InfinityStage.Mouth.P05"),
        "I5": ("LS_Interaction_05_BecomesKing", "Interaction 5 — Stalls Camera", "Passage 6", "InfinityStage.Mouth.P06"),
    }
    registry_problems = []
    if set(transitions) != set(expected_identity):
        registry_problems.append("ids=%r" % sorted(transitions))
    for transition_id, expected in expected_identity.items():
        row = transitions.get(transition_id, {})
        tags = row.get("camera_tags", [])
        actual = (
            str(row.get("sequence_path", "")).rsplit("/", 1)[-1],
            row.get("camera_label"), row.get("next_passage_label"),
            tags[-1] if tags else None,
        )
        if actual != expected:
            registry_problems.append("%s identity=%r" % (transition_id, actual))
        if transition_id != "OPENING" and row.get("camera_tags", [None])[0] != "InfinityStage.TransitionStalls":
            registry_problems.append("%s missing stalls tag" % transition_id)
    if transitions.get("I1", {}).get("minimum_end_frame") != 638:
        registry_problems.append("I1 minimum_end_frame")
    if transitions.get("I1", {}).get("landed_s") != LANDED_S:
        registry_problems.append("I1 landed_s")
    for transition_id in ("I2", "I3", "I4", "I5"):
        row = transitions.get(transition_id, {})
        # 5 Oct: I2-I5 made ready for curtain_sleight.py from live DRY WR-20261005-104423 (end 500, landed 20.3,
        # pile edge 203); the Soft goods steps are superseded by the sleight's own lengthening.
        if row.get("minimum_end_frame") != 500 or row.get("landed_s") != 20.3 or row.get("pile_edge_cm") != 203.0:
            registry_problems.append("%s readiness values" % transition_id)
        if row.get("soft_goods_steps") != [] or len(row.get("soft_goods_steps_superseded", [])) != 3:
            registry_problems.append("%s Soft goods steps superseded" % transition_id)
    opening = transitions.get("OPENING", {})
    opening_evidence = opening.get("file_evidence", {})
    opening_ready = (
        opening.get("minimum_end_frame") == 375
        and abs(opening.get("landed_s") - 6.326666666666666) <= 1.0e-12
        and opening.get("pile_edge_cm") == 203.0
        and opening_evidence.get("opening_playback_frames") == [0, 375]
        and opening_evidence.get("opening_camera_pose", {}).get("focus_cm") == 100000.0
        and opening_evidence.get("p01_start_pose", {}).get("location_cm") == [0.0, 0.0, 150.0]
        and opening_evidence.get("p01_start_focal_mm") == 25.0
        and opening_evidence.get("p01_start_focus_cm") == 600.0
        and abs(opening_evidence.get("p01_arrival_speed_cm_s") - 250.00000350317606) <= 1.0e-9
    )
    if not opening_ready:
        registry_problems.append("OPENING must be ready from the measured probe")
    results.append(run_case(
        "transition_registry",
        not registry_problems,
        "problems=%r" % registry_problems,
    ))

    opening_seat = {
        "x": -1400.0, "y": 0.0, "z": 150.0,
        "pitch": 14.0, "yaw": 0.0, "roll": 0.0,
    }
    opening_target = {
        "x": 0.0, "y": 0.0, "z": 150.0,
        "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
    }
    opening_keys, opening_report = plan_walk(
        opening_seat, opening_target, 250.00000350317606, EASE_S, 15.0, FPS,
        15.0, 25.0, 100000.0, 600.0,
        opening["landed_s"], opening["pile_edge_cm"],
    )
    opening_failures = check_plan(
        opening_keys, opening_report, opening_target, 250.00000350317606,
        opening["landed_s"], opening["pile_edge_cm"],
    )
    results.append(run_case(
        "opening_probe_values_plan",
        not opening_failures and opening_report["final_frame"] == 375,
        "failures=%r final_frame=%r start_s=%.6f keys=%d"
        % (opening_failures, opening_report["final_frame"], opening_report["start_s"], len(opening_keys)),
    ))

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

    i1 = transitions["I1"]
    configured_end_s = i1["minimum_end_frame"] / FPS
    configured_keys, configured_report = plan_walk(
        SEAT, TARGET, V_END, EASE_S, configured_end_s, FPS,
        FOCAL0, FOCAL1, FOCUS0, FOCUS1,
        i1["landed_s"], i1["pile_edge_cm"],
    )
    first_key_diff = next(
        (
            (index, current, configured)
            for index, (current, configured) in enumerate(zip(keys, configured_keys))
            if current != configured
        ),
        None,
    )
    exact_i1 = (
        len(configured_keys) == len(keys)
        and first_key_diff is None
        and configured_report == report
    )
    results.append(run_case(
        "i1_registry_reproduces_current_keys",
        exact_i1,
        "current=%d configured=%d first_diff=%r report_equal=%s"
        % (len(keys), len(configured_keys), first_key_diff, configured_report == report),
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
