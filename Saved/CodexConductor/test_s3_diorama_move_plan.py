"""Offline positive and required negative controls for s3_diorama_move.py."""
import copy
import sys

from s3_diorama_move import (
    FIGURE_LABELS,
    GROUP_LABELS,
    PlanError,
    plan_diorama,
    validate_ring_boxes,
    validate_target_guards,
)


def fixture_targets():
    targets = {}
    pedestal = [1729.898, -137.546, 1.784]
    group_positions = (
        pedestal,
        [1729.898, -137.546, 90.0],
        [1740.0, -130.0, 92.0],
        [2062.875, -630.524, 450.515],
    )
    for label, location in zip(GROUP_LABELS, group_positions):
        targets[label] = {
            "label": label,
            "location": location,
            "rotation": [0.0, 0.0, 0.0],
            "local_bounds": {"min": [-30.0, -30.0, 0.0], "max": [30.0, 30.0, 80.0]},
        }
    figure_positions = (
        [2568.687, -219.720, -26.1],
        [2326.030, -143.074, -27.4],
        [2313.560, -14.703, -25.9],
        [2583.227, -61.820, -27.4],
        [2388.027, -328.757, -27.4],
        [2726.124, -178.593, -27.4],
    )
    for index, (label, location) in enumerate(zip(FIGURE_LABELS, figure_positions)):
        targets[label] = {
            "label": label,
            "location": location,
            "rotation": [0.0, 0.0, 15.0 * index],
            "local_bounds": {"min": [-38.0, -32.0, 0.0], "max": [38.0, 32.0, 190.0]},
        }
    return targets


def guards(show_label=None, parent_label=None):
    rows = []
    for label in GROUP_LABELS + FIGURE_LABELS:
        rows.append({
            "label": label,
            "count": 1,
            "parent": "Parent Actor" if label == parent_label else None,
            "show_references": ["cues[0] soft_path=/Game/Test"] if label == show_label else [],
        })
    return rows


def expect_failure(name, function):
    try:
        function()
    except PlanError:
        print("PASS negative %s: FAIL observed as required" % name)
        return 0
    print("FAIL negative %s: invalid case was accepted" % name)
    return 1


def main():
    failures = 0
    plan = plan_diorama(fixture_targets())
    figures = [row for row in plan["targets"] if row["kind"] == "ring_figure"]
    if len(figures) == 6 and len({row["slot_index"] for row in figures}) == 6:
        print("PASS positive: deterministic six-slot plan is valid")
    else:
        print("FAIL positive: plan did not produce six unique figure slots")
        failures += 1

    overlap = copy.deepcopy(figures)
    overlap[1]["planned_bounds"] = copy.deepcopy(overlap[0]["planned_bounds"])
    failures += expect_failure("overlap", lambda: validate_ring_boxes(overlap))

    outside = copy.deepcopy(figures)
    outside[0]["planned_bounds"]["max"][1] = 901.0
    failures += expect_failure("outside box", lambda: validate_ring_boxes(outside))

    failures += expect_failure(
        "Show-referenced target",
        lambda: validate_target_guards(guards(show_label=FIGURE_LABELS[0])),
    )
    failures += expect_failure(
        "attached target",
        lambda: validate_target_guards(guards(parent_label=FIGURE_LABELS[1])),
    )
    if failures == 0:
        print("S3_DIORAMA_HARNESS_OK|positive=1|negative=4")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
