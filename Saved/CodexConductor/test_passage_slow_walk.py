"""Offline positive and negative controls for passage_slow_walk.py."""

import copy
import sys

from passage_slow_walk import assert_protected_unchanged, plan_scaled_timing


def expect_failure(name, callback):
    try:
        callback()
    except AssertionError as error:
        print("PASS %s|%s" % (name, error))
        return True
    print("FAIL %s|did not refuse" % name)
    return False


def main():
    tick_rate = 24000
    # 48,000 + (22 * 48,000) + 34,344 = 1,138,344 ticks = 47.431 s.
    intervals = [48000] * 23
    plan = plan_scaled_timing(48000, intervals, 34344, 180 * tick_rate)
    positive = plan["old_ticks"] == 1138344 and plan["new_ticks"] == 4320000
    print(
        "%s positive_47p431_to_180|old_ticks=%d|new_ticks=%d|k=%.12f|residual=%d"
        % ("PASS" if positive else "FAIL", plan["old_ticks"], plan["new_ticks"], plan["k"], plan["rounding_residual_ticks"])
    )

    protected = {
        "cue_count": 23,
        "cue_indices": list(range(10, 33)),
        "cue_guids": ["C%02d" % value for value in range(23)],
        "occurrence_guids": ["O%02d" % value for value in range(23)],
        "meshes": [["L", "R", False, None] for _ in range(23)],
        "override_masks": [0] * 23,
        "lead_in_distance_cm": 250.0,
        "gap_to_next_cm": [500.0] * 23,
        "tail_distance_cm": 607.8345,
    }
    unchanged = assert_protected_unchanged(protected, copy.deepcopy(protected))
    print("PASS protected_unchanged" if unchanged else "FAIL protected_unchanged")

    changed_distance = copy.deepcopy(protected)
    changed_distance["gap_to_next_cm"][4] += 1.0
    distance_refuses = expect_failure(
        "negative_distance_change",
        lambda: assert_protected_unchanged(protected, changed_distance),
    )
    changed_count = copy.deepcopy(protected)
    changed_count["cue_count"] += 1
    changed_count["cue_indices"].append(33)
    count_refuses = expect_failure(
        "negative_count_change",
        lambda: assert_protected_unchanged(protected, changed_count),
    )
    ok = positive and unchanged and distance_refuses and count_refuses
    print("PASS SLOW_WALK_OFFLINE_HARNESS" if ok else "FAIL SLOW_WALK_OFFLINE_HARNESS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
