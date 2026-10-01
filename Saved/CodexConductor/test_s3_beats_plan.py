"""Offline positive and required negative controls for s3_beats_apply.py."""
import copy
import sys

from s3_beats_apply import PlanError, plan_beats


def fixture_state():
    return {
        "fps": 24.0,
        "playback": [0, 6240],
        "markers": [(10, "Existing harmless marker")],
        "entry_source_available": True,
        "wide_binding_exists": False,
        "exit_cut": {"start": 6216, "end": 6240, "active": True},
        "root_clam_cut": {"start": 81, "end": 1501, "active": True},
        "nested_clam_cut": {"start": -2, "end": 12573, "active": True},
    }


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
    plan = plan_beats(fixture_state())
    if plan["wide_range"] == [95, 6216] and len(plan["markers"]) == 12:
        print("PASS positive: deterministic S3 beat plan is valid")
    else:
        print("FAIL positive: unexpected plan %r" % plan)
        failures += 1

    hidden = copy.deepcopy(fixture_state())
    hidden["markers"].append((375, "InfinityStage.HiddenChangeover"))
    failures += expect_failure("HiddenChangeover label", lambda: plan_beats(hidden))

    duplicate = copy.deepcopy(fixture_state())
    duplicate["markers"].append((360, "S3 B02 existing"))
    failures += expect_failure("existing S3 B marker", lambda: plan_beats(duplicate))

    late_clam = copy.deepcopy(fixture_state())
    late_clam["root_clam_cut"]["end"] = 6217
    failures += expect_failure("retired ClamCam1 ending after S3 Wide", lambda: plan_beats(late_clam))

    split = [
        {"op": "add_spawnable_from_instance", "target": "S3 Wide"},
        {"op": "set_start", "target": "S3 Wide cut", "value": 95},
        {"op": "set_end", "target": "S3 Wide cut", "value": 6216},
    ]
    failures += expect_failure("split set_start/set_end", lambda: plan_beats(fixture_state(), split))

    if failures == 0:
        print("S3_BEATS_HARNESS_OK|positive=1|negative=4")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
