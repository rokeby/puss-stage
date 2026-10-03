"""Offline positive and required negative controls for s3_beach_place.py."""
import copy
import json
import os
import sys

from s3_beach_place import PlanError, validate_plan


HERE = os.path.dirname(os.path.abspath(__file__))


def fixture():
    with open(os.path.join(HERE, "s3_beach_plan.json"), encoding="utf-8") as handle:
        plan = json.load(handle)
    return copy.deepcopy(plan["placements"]), copy.deepcopy(plan["shot_cameras_dock_cm"])


def expect_failure(name, function):
    try:
        function()
    except PlanError:
        print("PASS negative %s: STOP observed as required" % name)
        return 0
    print("FAIL negative %s: invalid case was accepted" % name)
    return 1


def main():
    failures = 0
    rows, cameras = fixture()
    validate_plan(rows, cameras)
    if min(row["nearest_camera_clearance_cm"] for row in rows) >= 150.0:
        print("PASS positive: draft clears cameras, gap, wave bands, box, and labels")
    else:
        print("FAIL positive: camera clearance annotation is below 150 cm")
        failures += 1

    close_rows, close_cameras = fixture()
    close_rows[0]["estimated_aabb"] = {"min": [3370.0, -10.0, 90.0], "max": [3390.0, 10.0, 130.0]}
    failures += expect_failure("inside 150 cm camera clearance",
                               lambda: validate_plan(close_rows, close_cameras))

    wave_rows, wave_cameras = fixture()
    wave_rows[0]["estimated_aabb"]["max"][0] = 4110.0
    failures += expect_failure("wave travel band overlap",
                               lambda: validate_plan(wave_rows, wave_cameras))

    gap_rows, gap_cameras = fixture()
    gap_rows[0]["estimated_aabb"] = {"min": [3400.0, -20.0, -30.0], "max": [3500.0, 20.0, 0.0]}
    failures += expect_failure("camera-side gap overlap",
                               lambda: validate_plan(gap_rows, gap_cameras))

    label_rows, label_cameras = fixture()
    failures += expect_failure("planned label already exists",
                               lambda: validate_plan(label_rows, label_cameras,
                                                     {label_rows[0]["label"]: 1}))

    no_camera_rows, _ = fixture()
    failures += expect_failure("no live shot cameras",
                               lambda: validate_plan(no_camera_rows, []))

    if failures == 0:
        print("S3_BEACH_PLACE_HARNESS_OK|positive=1|negative=5")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
