"""Plain-Python positive and negative controls for the Scene 3 strike plan."""
import copy
import math
import sys

from s3_strike_apply import (
    LIGHT_SPECS,
    forward_vector,
    look_at_rotation,
    plan_intensity_keys,
    require_aim,
    root_relative_to_world,
    rotate_vector,
    validate_shadow_count,
)


LANDED_ROOT_LOCATION = (321.0, -654.0, 12.0)
LANDED_ROOT_ROTATION = (0.0, 0.0, 17.0)
REST_ROOT_ROTATION = (0.0, -90.0, 0.0)
REVEAL_S = 4.6261
STRIKE_S = 6.1261


def angle_degrees(dot_value):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot_value))))


def main():
    failures = 0
    worst_angle = 0.0
    try:
        for spec in LIGHT_SPECS:
            local_rotation = look_at_rotation(spec["location"], spec["target"])
            origin = root_relative_to_world(LANDED_ROOT_LOCATION, LANDED_ROOT_ROTATION, spec["location"])
            target = root_relative_to_world(LANDED_ROOT_LOCATION, LANDED_ROOT_ROTATION, spec["target"])
            forward = rotate_vector(LANDED_ROOT_ROTATION, forward_vector(local_rotation))
            aim_dot = require_aim(forward, origin, target)
            worst_angle = max(worst_angle, angle_degrees(aim_dot))
            keys = plan_intensity_keys(STRIKE_S, REVEAL_S, spec["intensity"])
            if keys[1][0] != STRIKE_S:
                raise ValueError(f"{spec['label']} did not start at STRIKE_S")
        validate_shadow_count(LIGHT_SPECS)
        if worst_angle >= 0.1:
            raise ValueError(f"worst aim error {worst_angle:.6f} degrees")
    except ValueError as exc:
        print(f"FAIL positive control: {exc}")
        failures += 1
    else:
        print(f"PASS positive control: all landed aims within 0.1 deg, keys start at STRIKE_S, one shadow (worst={worst_angle:.6f} deg)")

    # Cyc 2 has no lateral component, so the rest-pose error is the specified ~90 degrees exactly.
    sample = LIGHT_SPECS[4]
    rest_origin = root_relative_to_world((0.0, 0.0, 0.0), REST_ROOT_ROTATION, sample["location"])
    rest_target = root_relative_to_world((0.0, 0.0, 0.0), REST_ROOT_ROTATION, sample["target"])
    wrong_relative_rotation = look_at_rotation(rest_origin, rest_target)
    landed_origin = root_relative_to_world((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), sample["location"])
    landed_target = root_relative_to_world((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), sample["target"])
    wrong_forward = forward_vector(wrong_relative_rotation)
    try:
        require_aim(wrong_forward, landed_origin, landed_target)
    except ValueError:
        target_direction = tuple(landed_target[i] - landed_origin[i] for i in range(3))
        target_length = math.sqrt(sum(value * value for value in target_direction))
        wrong_dot = sum(wrong_forward[i] * target_direction[i] / target_length for i in range(3))
        print(f"PASS negative control a: FAIL observed as required (rest-pose aim misses by {angle_degrees(wrong_dot):.3f} deg)")
    else:
        print("FAIL negative control a: rest-pose aim unexpectedly passed at the landed pose")
        failures += 1

    try:
        plan_intensity_keys(REVEAL_S, REVEAL_S, 1000.0)
    except ValueError:
        print("PASS negative control b: FAIL observed as required (STRIKE_S <= REVEAL_S raised ValueError)")
    else:
        print("FAIL negative control b: STRIKE_S <= REVEAL_S did not raise")
        failures += 1

    two_shadowed = copy.deepcopy(LIGHT_SPECS)
    two_shadowed[1]["shadows"] = True
    try:
        validate_shadow_count(two_shadowed)
    except ValueError:
        print("PASS negative control c: FAIL observed as required (two shadowed lights raised ValueError)")
    else:
        print("FAIL negative control c: two shadowed lights did not raise")
        failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
