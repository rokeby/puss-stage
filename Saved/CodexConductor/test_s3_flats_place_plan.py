"""Offline positive and required negative controls for s3_flats_place.py."""
import copy
import sys

from s3_flats_place import PlanError, validate_plan


def fixture():
    rows = [
        {
            "kind": "wave", "label": "S3 Wave Row1 A",
            "landed_dock_aabb": {"min": [4184.0, -1000.0, -5.0], "max": [4196.0, 431.0, 115.0]},
        },
        {
            "kind": "wave", "label": "S3 Wave Row1 B",
            "landed_dock_aabb": {"min": [4184.0, -628.0, -5.0], "max": [4196.0, 1000.0, 115.0]},
        },
        {
            "kind": "wave", "label": "S3 Wave Row2 A",
            "landed_dock_aabb": {"min": [4984.0, -1000.0, -5.0], "max": [4996.0, 532.0, 175.0]},
        },
        {
            "kind": "wave", "label": "S3 Wave Row2 B",
            "landed_dock_aabb": {"min": [4984.0, -461.0, -5.0], "max": [4996.0, 1000.0, 175.0]},
        },
        {
            "kind": "wave", "label": "S3 Wave Row3 A",
            "landed_dock_aabb": {"min": [5784.0, -1000.0, -5.0], "max": [5797.0, 833.0, 255.0]},
        },
        {
            "kind": "wave", "label": "S3 Wave Row3 B",
            "landed_dock_aabb": {"min": [5784.0, -439.0, -5.0], "max": [5797.0, 1000.0, 255.0]},
        },
        {
            "kind": "backdrop", "label": "S3 Backdrop",
            "landed_dock_aabb": {"min": [6497.0, -1000.0, -5.0], "max": [6497.0, 1000.0, 2995.0]},
        },
    ]
    ring = {"min": [3100.0, -450.0, -30.0], "max": [3800.0, 450.0, 210.0]}
    labels = {row["label"]: 0 for row in rows}
    handedness = {
        "bounds_y_cm": [-1000.0, 1000.0],
        "bounds_z_cm": [0.0, 3000.0],
        "du_dY": 0.0005,
        "dv_dZ": -1.0 / 3000.0,
        "normal": [-1.0, 0.0, 0.0],
        "vertices": 4,
        "triangles": 2,
    }
    return rows, ring, labels, handedness


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
    rows, ring, labels, handedness = fixture()
    result = validate_plan(rows, ring, labels, handedness)
    if (result["du_dY"] > 0.0 and result["dv_dZ"] < 0.0 and
            all(row.get("ring_aabb_distance_cm", 0) >= 300.0
                for row in rows if row["kind"] == "wave")):
        print("PASS positive: landed layout, ring clearance, labels, and handedness are valid")
    else:
        print("FAIL positive: unexpected plan result %r" % result)
        failures += 1

    inside_rows, inside_ring, inside_labels, inside_handedness = fixture()
    inside_rows[0]["landed_dock_aabb"] = {"min": [4050.0, -100.0, 0.0], "max": [4100.0, 100.0, 100.0]}
    inside_ring["max"][0] = 3900.0
    failures += expect_failure(
        "wave inside ring zone",
        lambda: validate_plan(inside_rows, inside_ring, inside_labels, inside_handedness),
    )

    outside_rows, outside_ring, outside_labels, outside_handedness = fixture()
    outside_rows[2]["landed_dock_aabb"]["max"][1] = 1002.0
    failures += expect_failure(
        "outside box",
        lambda: validate_plan(outside_rows, outside_ring, outside_labels, outside_handedness),
    )

    flipped_rows, flipped_ring, flipped_labels, flipped_handedness = fixture()
    flipped_handedness["du_dY"] = -0.0005
    failures += expect_failure(
        "du/dY < 0",
        lambda: validate_plan(flipped_rows, flipped_ring, flipped_labels, flipped_handedness),
    )

    label_rows, label_ring, label_labels, label_handedness = fixture()
    label_labels["S3 Backdrop"] = 1
    failures += expect_failure(
        "label already present",
        lambda: validate_plan(label_rows, label_ring, label_labels, label_handedness),
    )

    if failures == 0:
        print("S3_FLATS_PLACE_HARNESS_OK|positive=1|negative=4")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
