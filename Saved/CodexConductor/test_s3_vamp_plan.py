"""Offline positive and required negative controls for s3_vamp_apply.py."""
import copy
import math
import sys

from s3_vamp_apply import (
    CLAM_CENTRE_DOCK,
    PlanError,
    RADIUS_CM,
    plan_vamp,
)


def fixture_state():
    return {
        "fps": 24.0,
        "playback": [0, 6240],
        "binding_count": 1,
        "binding_spawnable": True,
        "cut_range": [3480, 4200],
        "transform_track_count": 0,
        "markers": [[360, "S3.B02"], [3480, "S3.B07"], [4200, "S3.B08"]],
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
    plan = plan_vamp(fixture_state())
    radii = [math.hypot(
        row["dock_location_cm"][0] - CLAM_CENTRE_DOCK[0],
        row["dock_location_cm"][1] - CLAM_CENTRE_DOCK[1],
    ) for row in plan["keys"]]
    if (plan["key_count"] == 721 and plan["keys"][0]["frame"] == 3480 and
            plan["keys"][-1]["frame"] == 4200 and
            max(abs(radius - RADIUS_CM) for radius in radii) <= 0.5 and
            plan["seam"]["location_cm"] <= 0.01 and plan["seam"]["rotation_deg"] <= 0.01):
        print("PASS positive: seam equal, radius 200+/-0.5 cm, 721 keys")
    else:
        print("FAIL positive: unexpected vamp plan")
        failures += 1

    seam = copy.deepcopy(fixture_state())
    seam["pose_overrides"] = {4200: {"world_rotation_rpy_deg": [0.0, -4.289153, 1.0]}}
    failures += expect_failure("seam mismatch", lambda: plan_vamp(seam))

    drift = copy.deepcopy(fixture_state())
    drift["pose_overrides"] = {3840: {"dock_location_cm": [3701.0, 0.0, 120.0]}}
    failures += expect_failure("radius drift", lambda: plan_vamp(drift))

    marked = copy.deepcopy(fixture_state())
    marked["markers"].append([3480, "InfinityStage.VampStart"])
    failures += expect_failure("existing vamp marker", lambda: plan_vamp(marked))

    span = copy.deepcopy(fixture_state())
    span["requested_span"] = [3480, 4199]
    failures += expect_failure("wrong frame span", lambda: plan_vamp(span))

    if failures == 0:
        poses = plan["poses"]
        print("S3_VAMP_HARNESS_OK|positive=1|negative=4|first=%r|mid=%r|last=%r" %
              (poses["first"], poses["mid"], poses["last"]))
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
