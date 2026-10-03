"""Offline positive and required negative controls for s3_walls_marble.py."""
import copy
import sys

from s3_walls_marble import (DISK_PLINTH_MI, EXPECTED_STEEL, FAR_WALL_LABEL,
                             PlanError, TARGETS, validate_strategy)


def fixture():
    rows = [{
        "wall_label": item["wall_label"],
        "liner_label": item["liner_label"],
        "interior_sign": item["interior_sign"],
        "strategy": "inner_face_liner",
        "liner_thickness_cm": 1.0,
        "mutates_wall_slots": False,
    } for item in TARGETS]
    wall_materials = {item["wall_label"]: [EXPECTED_STEEL] for item in TARGETS}
    return rows, wall_materials


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
    rows, materials = fixture()
    validate_strategy(rows, DISK_PLINTH_MI, materials)
    print("PASS positive: two inner liners, live plinth source, steel walls unchanged")

    far_rows, far_materials = fixture()
    far_rows[1]["wall_label"] = FAR_WALL_LABEL
    far_materials[FAR_WALL_LABEL] = [EXPECTED_STEEL]
    failures += expect_failure("far wall included",
                               lambda: validate_strategy(far_rows, DISK_PLINTH_MI, far_materials))

    slot_rows, slot_materials = fixture()
    slot_rows[0]["mutates_wall_slots"] = True
    failures += expect_failure("wall slot mutation",
                               lambda: validate_strategy(slot_rows, DISK_PLINTH_MI, slot_materials))

    thick_rows, thick_materials = fixture()
    thick_rows[0]["liner_thickness_cm"] = 5.0
    failures += expect_failure("liner too thick",
                               lambda: validate_strategy(thick_rows, DISK_PLINTH_MI, thick_materials))

    changed_rows, changed_materials = fixture()
    changed_materials[changed_rows[0]["wall_label"]] = ["/Game/Unexpected"]
    failures += expect_failure("wall baseline changed",
                               lambda: validate_strategy(changed_rows, DISK_PLINTH_MI, changed_materials))

    collision_rows, collision_materials = fixture()
    failures += expect_failure("liner label exists",
                               lambda: validate_strategy(collision_rows, DISK_PLINTH_MI,
                                                         collision_materials,
                                                         {collision_rows[0]["liner_label"]: 1}))

    if failures == 0:
        print("S3_WALLS_MARBLE_HARNESS_OK|positive=1|negative=5")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
