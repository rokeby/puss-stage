"""Plain-Python positive and negative controls for s3_pit_deck_apply.py."""
import sys

from s3_pit_deck_apply import (
    bounds_intersect,
    measure_floor_top,
    plan_deck,
    plan_hole,
    plan_liner,
    plan_strips,
    reject_unknown_blockers,
    swing_check,
    validate_deck_relative,
    world_placed_relative_at_pitch,
)


FLOOR = {"x": [-150.0, 45144.0], "y": [-27490.0, 26070.0], "z": [-6.0, -5.0]}
HINGE_X = 500.0
HINGE_Z = -120.0
DEPTH = 6000.0
HALF_W = 1000.0
WALL_T = 50.0
REACH = 10979.0
FLOOR_TOP = -5.0


def main():
    failures = 0
    hole = plan_hole(FLOOR, HINGE_X, REACH, HALF_W, WALL_T)
    tiling = plan_strips(FLOOR, hole)
    liner = plan_liner(hole, FLOOR["z"][0], HINGE_Z, DEPTH, WALL_T)
    deck = plan_deck(FLOOR_TOP, HINGE_Z, DEPTH, HALF_W, 20.0)
    swing = swing_check(deck, HINGE_X, REACH)

    landed = validate_deck_relative(deck["relative_location"], deck, FLOOR_TOP, HINGE_Z)
    if abs(landed - FLOOR_TOP) <= 0.01:
        print(f"PASS positive deck: landed top {landed:.2f} cm")
    else:
        print(f"FAIL positive deck: landed top {landed:.2f} cm")
        failures += 1

    if abs(tiling["area_error_cm2"]) <= 1.0:
        print(
            "PASS positive strips: old plane minus hole tiled exactly "
            f"(area error {tiling['area_error_cm2']:.3f} cm^2)"
        )
    else:
        print(f"FAIL positive strips: area error {tiling['area_error_cm2']:.3f} cm^2")
        failures += 1

    if liner["clearance_cm"] >= 50.0:
        print(
            "PASS positive liner: hanging box clearance "
            f"{liner['clearance_cm']:.2f} cm"
        )
    else:
        print(f"FAIL positive liner: clearance {liner['clearance_cm']:.2f} cm")
        failures += 1

    print(
        "PASS positive swing: "
        f"minimum dock x {swing['minimum_x']:.2f} cm, deck reach {swing['deck_reach_cm']:.2f} cm"
    )

    try:
        wrong = world_placed_relative_at_pitch(deck, -90.0)
        validate_deck_relative(wrong, deck, FLOOR_TOP, HINGE_Z)
    except ValueError:
        print("PASS negative a: FAIL observed as required (world placement at root pitch -90 rejected)")
    else:
        print("FAIL negative a: world placement at root pitch -90 was accepted")
        failures += 1

    try:
        measure_floor_top([-5.0, -5.0, -5.0, -5.0, -5.0, 0.0])
    except ValueError:
        print("PASS negative b: FAIL observed as required (5 cm floor spread rejected)")
    else:
        print("FAIL negative b: 5 cm floor spread was accepted")
        failures += 1

    try:
        s1_floor_top = 0.0 - (DEPTH + WALL_T) - 250.0
        plan_liner(
            hole,
            FLOOR["z"][0],
            HINGE_Z,
            DEPTH,
            WALL_T,
            supplied_floor_top=s1_floor_top,
        )
    except ValueError:
        print("PASS negative c: FAIL observed as required (S1-depth liner rejected for S3)")
    else:
        print("FAIL negative c: S1-depth liner was accepted for S3")
        failures += 1

    try:
        unknown_bounds = {"x": [600.0, 700.0], "y": [-50.0, 50.0], "z": [-200.0, -100.0]}
        prism = {"x": hole["x"], "y": hole["y"], "z": [liner["floor_top_z"], FLOOR_TOP]}
        if not bounds_intersect(unknown_bounds, prism):
            raise AssertionError("negative fixture does not intersect the hole prism")
        reject_unknown_blockers([{"label": "Unknown Actor", "allowed": False}])
    except ValueError:
        print("PASS negative d: FAIL observed as required (unknown blocker rejected)")
    else:
        print("FAIL negative d: unknown blocker was accepted")
        failures += 1

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
