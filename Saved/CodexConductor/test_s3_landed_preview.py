"""Offline positive and negative controls for the S3 landed-preview maths."""
import sys

from s3_landed_preview import (
    CHANNEL_AXES,
    PreviewError,
    transform_errors,
    transform_from_channel_values,
    validate_far_wall_inner_x,
    validate_pose_errors,
    validate_rest_composition,
)


def expect_failure(name, function):
    try:
        function()
    except PreviewError:
        print("PASS negative %s: refusal observed as required" % name)
        return 0
    print("FAIL negative %s: invalid case was accepted" % name)
    return 1


def main():
    failures = 0
    baseline = {
        "location": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
    }
    values = {
        "Location.X": 11421.97275,
        "Location.Y": 160000.0,
        "Location.Z": -120.0,
        "Rotation.X": 0.0,
        "Rotation.Y": 0.0,
        "Rotation.Z": 0.0,
        "Scale.X": 1.0,
        "Scale.Y": 1.0,
        "Scale.Z": 1.0,
    }
    landed = transform_from_channel_values(baseline, values)
    exact = transform_errors(landed, landed)
    pose = validate_pose_errors([exact])
    rest = validate_rest_composition([dict(exact, label="S3 Hangar Deck")])
    far_error = validate_far_wall_inner_x(6500.0)
    if (landed["rotation"][1] == 0.0 and pose["location_cm"] == 0.0 and
            rest["max_location_error_cm"] == 0.0 and far_error == 0.0):
        print("PASS positive: landed channels, pose readback, rest composition, and far wall are valid")
    else:
        print("FAIL positive: unexpected maths result")
        failures += 1

    missing = dict(values)
    missing.pop(CHANNEL_AXES[-1])
    failures += expect_failure(
        "missing transform channel",
        lambda: transform_from_channel_values(baseline, missing),
    )
    failures += expect_failure(
        "DOWN readback outside 0.01 cm",
        lambda: validate_pose_errors([{
            "location_cm": 0.011,
            "rotation_deg": 0.0,
            "scale": 0.0,
        }]),
    )
    failures += expect_failure(
        "rest composition outside 1 cm",
        lambda: validate_rest_composition([{
            "label": "S3 Hangar Deck",
            "location_cm": 1.001,
            "rotation_deg": 0.0,
            "scale": 0.0,
        }]),
    )
    failures += expect_failure(
        "far wall outside 1 cm",
        lambda: validate_far_wall_inner_x(6498.999),
    )
    if failures == 0:
        print("S3_LANDED_PREVIEW_HARNESS_OK|positive=1|negative=4")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
