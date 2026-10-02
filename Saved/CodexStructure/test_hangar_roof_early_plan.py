"""Unreal-free positive and negative controls for hangar_roof_early_apply."""
import copy
import sys

from hangar_roof_early_apply import (
    LANDING_S,
    NEW_LATTICE_END_S,
    NEW_LATTICE_START_S,
    NEW_ROOF_END_S,
    NEW_ROOF_START_S,
    STANDARD_LATTICE,
    STANDARD_ROOF,
    plan_scene,
)


ROOT_KEYS = [[-5.8739, -90.0], [4.1261, 0.0]]


def standard(has_roof=True):
    return {
        "root_pitch": copy.deepcopy(ROOT_KEYS),
        "roof_pitch": copy.deepcopy(STANDARD_ROOF) if has_roof else None,
        "lattice_fly_z": copy.deepcopy(STANDARD_LATTICE),
    }


def expect_raises(label, callback):
    try:
        callback()
    except ValueError as exc:
        print(f"PASS {label}: refusal observed as required ({exc})")
        return 0
    print(f"FAIL {label}: expected ValueError was not raised")
    return 1


def main():
    failures = 0
    for scene in (1, 2, 3, 4, 5):
        before = standard(has_roof=True)
        planned = plan_scene(before)
        expected_roof = [
            [0.0, -90.0],
            [NEW_ROOF_START_S, -90.0],
            [NEW_ROOF_END_S, 0.0],
        ]
        expected_lattice = [
            [0.0, 2800.0],
            [NEW_LATTICE_START_S, 2800.0],
            [NEW_LATTICE_END_S, 1200.0],
        ]
        if (
            planned["action"] == "include"
            and planned["after"]["roof_pitch"] == expected_roof
            and planned["after"]["lattice_fly_z"] == expected_lattice
            and planned["after"]["root_pitch"] == ROOT_KEYS
            and before["root_pitch"] == ROOT_KEYS
        ):
            print(
                f"PASS positive S{scene}: roof {NEW_ROOF_START_S}->{NEW_ROOF_END_S}, "
                f"lattice {NEW_LATTICE_START_S}->{NEW_LATTICE_END_S}, root unchanged"
            )
        else:
            print(f"FAIL positive S{scene}: unexpected plan {planned}")
            failures += 1

    no_roof = standard(has_roof=False)
    no_roof_plan = plan_scene(no_roof)
    if no_roof_plan["action"] == "skip" and no_roof_plan["after"] == no_roof:
        print("PASS no-roof S6: handled without error and left lattice/root unchanged")
    else:
        print(f"FAIL no-roof S6: unexpected plan {no_roof_plan}")
        failures += 1

    failures += expect_raises(
        "negative roof starts before landing",
        lambda: plan_scene(standard(), roof_start_s=LANDING_S - 0.1),
    )
    failures += expect_raises(
        "negative lattice overlaps roof",
        lambda: plan_scene(
            standard(),
            roof_end_s=NEW_ROOF_END_S,
            lattice_start_s=NEW_ROOF_END_S - 0.1,
        ),
    )
    stale = standard()
    stale["roof_pitch"][1][0] += 2.0 / 30.0
    failures += expect_raises(
        "negative current keys differ by more than one frame",
        lambda: plan_scene(stale),
    )
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
